"""Auto-test du moteur (stdlib only) : python3 tool/tests/selftest.py

Couvre les cas sensibles : parsing des montants FR, lecture FEC (délimiteurs/
encodage/débit-crédit), imputations multiples N-1, règles de codage (immo /
inconnu / multi = les 3 seuls cas remontés), rapprochement (exact/écart/
manquant), export Quadra équilibré à 256 caractères.
"""
import sys, os, datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from s2a_lmnp import (parse_montant, parse_fec, construire, Operation, Facture,
                      coder, rapprocher, manquants, to_quadratus, verifier_equilibre)

ok = 0
def check(cond, label):
    global ok
    assert cond, "ÉCHEC: " + label
    ok += 1
    print("  ok -", label)

D = datetime.date

print("1) parse_montant (formats FR/EU)")
check(parse_montant("1 234,56") == 1234.56, "espace + virgule")
check(parse_montant("1.234,56") == 1234.56, "point millier + virgule")
check(parse_montant("1234.56") == 1234.56, "point décimal")
check(parse_montant("(1 200,00)") == -1200.0, "parenthèses = négatif")
check(parse_montant("438") == 438.0, "entier")
try:
    parse_montant("abc"); check(False, "abc doit lever")
except ValueError:
    check(True, "montant illisible -> ValueError (pas de valeur inventée)")

print("2) FEC : délimiteur |, débit/crédit, montants FR, imputation multiple")
FEC = (
    "JournalCode|CompteNum|CompteLib|EcritureDate|EcritureLib|Debit|Credit\n"
    "AC|614000|Charges copro|20250108|SYNDIC AZUR SA T1|438,00|0,00\n"
    "AC|606100|Energie|20250110|EDF|96,40|0,00\n"
    "AC|615000|Entretien|20250312|SARL DUBOIS|300,00|0,00\n"
    "AC|213500|Agencements|20250920|SARL DUBOIS|1 200,00|0,00\n"   # même fournisseur, autre compte
    "VE|706000|Loyers|20250105|LOYER MARTIN|0,00|850,00\n"
)
lignes = parse_fec(FEC)
check(len(lignes) == 5, "5 lignes lues")
dico = construire(lignes)
check(dico.exact("PRLV SYNDIC AZUR SA T1") is not None, "syndic reconnu (variante préfixe/T1)")
e = dico.exact("SARL DUBOIS")
check(e is not None and e.multi and set(e.comptes) == {"615000", "213500"},
      "DUBOIS = imputations multiples N-1 détectées")

print("3) Codage : seuls immo / inconnu / multi remontent")
def op(lib, m, sens="D", amort=None):
    return Operation(date=D(2026, 3, 18), libelle=lib, montant=m, sens=sens, amort=amort)

cas = {
    "syndic": (op("PRLV SYNDIC AZUR SA T2", 438.0), False),   # connu simple -> auto
    "edf": (op("PRLV EDF CLIENTS", 96.4), False),             # connu -> auto
    "loyer": (op("VIR LOYER MARTIN", 850.0, "C"), False),     # recette -> auto
    "apport": (op("VIR M DUPONT APPORT CC", 2500.0, "C"), False),  # AUTO (pas immo/inconnu/multi)
    "indemnite": (op("VIR AXA INDEMNISATION SINISTRE", 640.0, "C"), False),  # AUTO
    "pret": (op("PRLV ECH PRET IMMO", 1030.64, "D", (387.35, 643.29)), False),  # AUTO (ventilé)
    "menuiserie": (op("CHQ MENUISERIE DES CIMES", 3480.0), True),  # immo -> revue
    "mobilier": (op("CB BOULANGER ELECTROMENAGER", 890.0), True),  # immo -> revue
    "inconnu": (op("PRLV CLINK ABONNEMENT", 12.9), True),          # inconnu -> revue
    "multi": (op("PRLV SARL DUBOIS", 540.0), True),                # multi N-1 -> revue
}
for nom, (o, attendu) in cas.items():
    coder(o, dico)
    check(o.a_revoir == attendu, "%s : a_revoir=%s (compte %s)" % (nom, o.a_revoir, o.compte))
check(cas["multi"][0].compte in ("615000", "213500"), "multi : compte principal proposé + options")
check(len(cas["multi"][0].options) == 2, "multi : 2 options proposées")
check(cas["pret"][0].split == (387.35, 643.29), "prêt : ventilation intérêts/capital conservée")

print("4) Rapprochement : exact / écart / manquant")
ops = [cas["syndic"][0], cas["mobilier"][0], cas["menuiserie"][0]]
facts = [
    Facture("Syndic Azur", D(2026, 3, 17), 438.0, 73.0),
    Facture("Boulanger", D(2026, 2, 21), 899.0, 149.83),   # 899 vs 890 -> écart
]
rapprocher(ops, facts)
check(cas["syndic"][0].facture is not None and not cas["syndic"][0].ecart, "syndic rapproché sans écart")
check(cas["mobilier"][0].facture is not None and cas["mobilier"][0].ecart, "boulanger rapproché AVEC écart")
manq = manquants(ops, seuil=150.0)
check(cas["menuiserie"][0] in manq, "menuiserie (3480, sans facture) dans les manquants")

print("5) Export Quadra ASCII : format réel du cabinet (251 car., contrepartie en ligne)")
allops = [cas[k][0] for k in ("loyer", "syndic", "pret", "menuiserie", "apport")]
txt = to_quadratus(allops, avec_banque=True, compte_banque="51210010")
lignes_q = [l for l in txt.split("\r\n") if l]
check(all(len(l) == 251 for l in lignes_q), "toutes les lignes = 251 caractères")
check(lignes_q[0][0] == "M", "type d'enregistrement 'M'")
deb, cred, equilibre = verifier_equilibre(txt)
check(equilibre, "chaque ligne porte sa contrepartie en ligne (équilibrée par construction)")
# le prêt donne 2 lignes (661 + 164), les 4 autres opérations 1 ligne -> 6 lignes
check(len(lignes_q) == 6, "prêt ventilé en 2 lignes 661/164 -> 6 lignes au total")
from s2a_lmnp.quadra import parse_mouvement, format_mouvement
f0 = parse_mouvement(lignes_q[0])
check(f0["contrep"].strip() == "51210010", "contrepartie = compte banque (51210010)")
check(f0["devise"] == "EUR" and f0["journal"] == "BQ", "devise EUR + journal BQ")

print("6) Aller-retour sur une VRAIE ligne Quadra (dossier DUMDUM) : identité octet à octet")
REELLE = ("M62600100BQ000010126 NETFLIX             D+00000000219951200000000000"
          "                                      EURBQ1   NETFLIX"
          "                                                                                "
          "0000000132PL  12062026104255                    ")
check(len(REELLE) == 251, "ligne de référence = 251 caractères")
f = parse_mouvement(REELLE)
check(int(f["montant"]) == 2199, "montant relu = 2199 c (21,99 €)")
check(f["compte"] == "62600100" and f["sens"] == "D", "compte 62600100, sens D")
check(f["contrep"].strip() == "51200000", "contrepartie en ligne = 51200000")
import datetime as _dt
rebuilt = format_mouvement(
    compte=f["compte"], journal=f["journal"],
    date=_dt.date(2000 + int(f["date"][4:6]), int(f["date"][2:4]), int(f["date"][0:2])),
    libelle=f["libelle"], sens=f["sens"], montant=int(f["montant"]) / 100.0,
    contrepartie=f["contrep"], piece=int(f["piece"]), source=f["source"],
    horodate=f["horodate"], folio=f["folio"], journal3=f["journal3"],
    libelle_long=f["liblong"])
check(rebuilt == REELLE, "réécriture identique à l'original (positions exactes)")

print("\n%d contrôles OK — moteur cohérent." % ok)
