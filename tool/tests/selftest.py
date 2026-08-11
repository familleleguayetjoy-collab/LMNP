"""Auto-test du moteur (stdlib only) : python3 tool/tests/selftest.py

Couvre les cas sensibles : parsing des montants FR, lecture FEC (délimiteurs/
encodage/débit-crédit), imputations multiples N-1, règles de codage (immo /
inconnu / multi = les 3 seuls cas remontés), rapprochement (exact/écart/
manquant), export Quadra équilibré à 256 caractères.
"""
import sys, os, datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from s2a_lmnp import (parse_montant, parse_fec, construire, Operation, Facture,
                      coder, rapprocher, manquants, to_quadratus, verifier_equilibre,
                      doublons, operations_od_factures,
                      Bien, MappingBiens, proposer_sous_compte, inferer_depuis_fec,
                      associer_factures, associer_reglements, detecter_virements_internes,
                      marquer_perso, doublons_factures, chercher_dans_fec,
                      residu, questions_pour, appliquer_reponses, resoudre_residu,
                      resolver_depuis_client, facture_depuis_ocr)

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

print("3bis) Seuil d'immobilisation = 50 € HT (sous le seuil -> charge auto)")
petit = op("CB LEROY MERLIN VISSERIE", 42.0)      # bricolage < 50 -> charge auto
coder(petit, dico)
check(not petit.a_revoir and petit.compte == "606", "petit bricolage 42 € -> 606 auto")
gros = op("CB LEROY MERLIN PARQUET", 640.0)        # bricolage >= 50 -> à trancher
coder(gros, dico)
check(gros.a_revoir, "bricolage 640 € -> à trancher (immo possible)")
petit_meuble = op("CB IKEA TABOURET", 39.0)        # mobilier < 50 -> charge auto
coder(petit_meuble, dico)
check(not petit_meuble.a_revoir and petit_meuble.compte == "606", "petit mobilier 39 € -> 606 auto")
# le seuil s'apprécie en HT quand la facture donne la TVA (on poste le TTC)
from s2a_lmnp import Facture
o_ht = op("CB CASTORAMA ETAGERE", 58.0)            # 58 TTC mais 48,33 HT -> sous le seuil
o_ht.facture = Facture("Castorama", D(2026, 3, 18), 58.0, 9.67)
coder(o_ht, dico)
check(not o_ht.a_revoir and o_ht.compte == "606",
      "58 € TTC = 48,33 € HT < 50 -> charge auto (seuil apprécié en HT)")

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

print("7) Ligne déjà codée à l'export bancaire : on ne recode pas, pas de revue")
precode = Operation(date=D(2026, 1, 5), libelle="TOTALENERGIES", montant=197.92, sens="D")
precode.compte = "60611000"; precode.origine = "quadra"
coder(precode, dico)
check(precode.compte == "60611000" and not precode.a_revoir and precode.origine == "banque",
      "compte bancaire pré-affecté conservé (déjà codé)")

print("8) Anti-doublon : même date + montant + compte + libellé")
o1 = Operation(date=D(2026, 2, 1), libelle="EDF", montant=96.4, sens="D"); o1.compte = "606100"
o2 = Operation(date=D(2026, 2, 1), libelle="EDF", montant=96.4, sens="D"); o2.compte = "606100"
check(len(doublons([o1, o2])) == 1, "un doublon détecté sur deux lignes identiques")

print("9) Facture sans ligne bancaire -> écriture OD, contrepartie 108")
ops_bq = [Operation(date=D(2026, 3, 1), libelle="PRLV SYNDIC AZUR", montant=438.0, sens="D")]
facs = [Facture("EDF", D(2026, 1, 5), 69.34, 11.55),          # aucune ligne banque -> OD
        Facture("Syndic Azur", D(2026, 3, 1), 438.0, 0.0)]     # celle-ci se rapproche
rapprocher(ops_bq, facs)
od = operations_od_factures(facs, dico)
check(len(od) == 1 and od[0].facture.fournisseur == "EDF", "seule la facture non rapprochée part en OD")
txt_od = to_quadratus(od, avec_banque=False)
from s2a_lmnp.quadra import parse_mouvement
fod = parse_mouvement([l for l in txt_od.split("\r\n") if l][0])
check(fod["journal"] == "OD" and fod["contrep"].strip() == "10800000", "journal OD + contrepartie 108")

print("10) Suivi par bien : sous-comptes, routage par adresse, revue N-1")
b1 = Bien("bonaparte", "Bonaparte", "12 rue Bonaparte 06000 Nice")
b2 = Bien("lepante", "Lépante", "5 avenue Lépante 06000 Nice")
mp = MappingBiens(biens=[b1, b2])
mp.affecter("614", "bonaparte"); mp.affecter("6141", "lepante")
check(mp.bien_du_compte("6141").nom == "Lépante", "compte 6141 -> bien Lépante")
check(proposer_sous_compte("614", 0) == "614" and proposer_sous_compte("614", 1) == "6141",
      "convention sous-comptes 614 -> 6141")
check(mp.router_adresse("Facture — 5 avenue Lepante, Nice").code == "lepante",
      "adresse facture routée vers le bon bien")
mp2 = MappingBiens.from_json(mp.to_json())
check(mp2.par_compte == mp.par_compte, "mapping sauvegardé/relu à l'identique (JSON)")
ancien = MappingBiens(biens=[b1], par_compte={"614": "bonaparte"})
check(mp.diff(ancien)["ajoutes"] == ["6141"], "revue N-1 : compte 6141 ajouté cette année")
FEC_B = ("JournalCode|CompteNum|CompteLib|EcritureDate|EcritureLib|Debit|Credit\n"
         "AC|614000|Charges|20250110|Charges copro Bonaparte|100,00|0,00\n"
         "AC|614100|Charges|20250110|Charges copro Lepante|120,00|0,00\n")
prop = inferer_depuis_fec(parse_fec(FEC_B), [b1, b2])
check(prop.get("614000") == "bonaparte" and prop.get("614100") == "lepante",
      "affectation compte->bien proposée depuis le libellé N-1")

print("11) Un règlement = plusieurs factures (2 430 = 800 + 630 + 1 000)")
vir = Operation(date=D(2026, 4, 10), libelle="VIR FOURNISSEURS", montant=2430.0, sens="D")
fa = Facture("A", D(2026, 4, 8), 800.0); fb = Facture("B", D(2026, 4, 9), 630.0); fc = Facture("C", D(2026, 4, 7), 1000.0)
st, tot = associer_factures(vir, [fa, fb, fc])
check(st == "exact" and tot == 2430.0 and not vir.ecart, "3 factures associées, total = mouvement")
st2, _ = associer_factures(Operation(date=D(2026,4,10), libelle="X", montant=2400.0, sens="D"), [fa, fb, fc])
check(st2 == "ecart", "total ≠ mouvement -> à vérifier")

print("12) Une facture = plusieurs règlements (3 000 = 1 000 + 2 000)")
f3000 = Facture("Gros", D(2026, 5, 1), 3000.0)
r1 = Operation(date=D(2026, 5, 2), libelle="ACOMPTE 1", montant=1000.0, sens="D")
r2 = Operation(date=D(2026, 5, 20), libelle="ACOMPTE 2", montant=2000.0, sens="D")
st, tot, reste = associer_reglements(f3000, [r1, r2])
check(st == "solde" and tot == 3000.0 and reste == 0.0, "2 règlements soldent la facture")

print("13) Règlement partiel (facture 1 200, mouvement 800 -> reste 400)")
f1200 = Facture("Partiel", D(2026, 6, 1), 1200.0)
p1 = Operation(date=D(2026, 6, 3), libelle="PAIEMENT", montant=800.0, sens="D")
st, tot, reste = associer_reglements(f1200, [p1])
check(st == "partiel" and reste == 400.0 and p1.partiel, "partiel détecté, reste 400 €, à confirmer")

print("14) Virement interne entre deux comptes (-5 000 / +5 000)")
va = Operation(date=D(2026, 7, 1), libelle="VIR COMPTE B", montant=5000.0, sens="D"); va.compte_bancaire = "A"
vb = Operation(date=D(2026, 7, 1), libelle="VIR COMPTE A", montant=5000.0, sens="C"); vb.compte_bancaire = "B"
autre = Operation(date=D(2026, 7, 3), libelle="LOYER", montant=850.0, sens="C"); autre.compte_bancaire = "A"
cands = detecter_virements_internes([va, vb, autre])
check(len(cands) == 1 and va.interne and vb.interne, "paire interne proposée (à confirmer), le loyer ignoré")

print("15) Dépense personnelle confirmée -> contrepartie 108 / 455")
perso = Operation(date=D(2026, 8, 1), libelle="ACHAT PRIVE", montant=300.0, sens="D")
marquer_perso(perso, "exploitant")
check(perso.traitement == "perso" and perso.compte == "108", "perso LMNP -> 108")
perso2 = Operation(date=D(2026, 8, 1), libelle="ACHAT PRIVE", montant=300.0, sens="D")
marquer_perso(perso2, "sci")
check(perso2.compte == "455", "perso SCI/associé -> 455")

print("16) Doublon de facture : même fichier réimporté renommé (hash)")
d1 = Facture("EDF", D(2026, 1, 5), 69.34, fichier="edf.pdf"); d1.empreinte = "abc123"
d2 = Facture("EDF", D(2026, 1, 5), 69.34, fichier="edf_renomme.pdf"); d2.empreinte = "abc123"
d3 = Facture("EDF", D(2026, 2, 5), 71.20, fichier="edf_fev.pdf"); d3.empreinte = "zzz999"
check(len(doublons_factures([d1, d2, d3])) == 1, "doublon détecté malgré le renommage")

print("17) Écriture déjà présente dans le FEC (anti double comptabilisation)")
FECX = ("JournalCode|CompteNum|CompteLib|EcritureDate|EcritureLib|Debit|Credit\n"
        "BQ|606100|Energie|20260105|EDF|69,34|0,00\n")
lignes_x = parse_fec(FECX)
opx = Operation(date=D(2026, 1, 6), libelle="EDF", montant=69.34, sens="D"); opx.compte = "606100"
trouve = chercher_dans_fec(opx, lignes_x)
check(trouve is not None and trouve.compte == "606100", "écriture retrouvée dans le FEC -> ne pas recréer")

print("17b) EDF électricité ≠ travaux (faux positif regex corrigé)")
FECE = ("JournalCode|CompteNum|CompteLib|EcritureDate|EcritureLib|Debit|Credit\n"
        "BQ|606100|Energie|20250210|EDF energie electricite|57,79|0,00\n")
oedf = Operation(date=D(2026, 1, 20), libelle="EDF ENERGIE ELECTRICITE", montant=69.34, sens="D")
coder(oedf, construire(parse_fec(FECE)))
check(oedf.compte == "606100" and not oedf.a_revoir, "EDF électricité -> énergie 606100, pas travaux")
oelec = Operation(date=D(2026, 1, 20), libelle="TRAVAUX ELECTRICITE SALLE DE BAIN", montant=1200.0, sens="D")
coder(oelec, construire([]))
check(oelec.a_revoir and "615" in oelec.options, "vrais travaux (mot TRAVAUX) restent à trancher")

print("18) Couche IA — le résidu ambigu, en lot, sans clé (client factice)")

# Un faux ClientIA en mémoire : il ne fait AUCUN appel réseau. Il sert à prouver
# le câblage et les garde-fous, pas la qualité des propositions.
class FauxIA:
    def __init__(self, regle):
        self.regle = regle          # dict {libelle_substr: compte_proposé}
        self.recu = None            # dernière charge utile reçue (contrôle)
    def resoudre(self, questions, *, modele=None):
        self.recu = questions
        rep = []
        for q in questions:
            compte = None
            for cle, c in self.regle.items():
                if cle in (q["libelle"] or ""):
                    compte = c
            if compte is not None:
                rep.append({"id": q["id"], "compte": compte, "confiance": 0.9,
                            "raison": "test"})
        return rep
    def lire_facture(self, chemin, *, modele=None):
        return [{"fournisseur": "EDF", "date": "2026-01-05", "ttc": 69.34,
                 "tva": 11.56, "ht": 57.78, "numero": "F1", "confiance": 0.95}]

# fabrique un résidu réaliste : mobilier au-dessus du seuil (2184/606/615)
op_amb = Operation(date=D(2026, 3, 1), libelle="CONFORAMA CANAPE", montant=900.0, sens="D")
coder(op_amb, construire([]))
check(op_amb.a_revoir and len(op_amb.options) >= 2, "mobilier > seuil = résidu ambigu à trancher")
op_clair = Operation(date=D(2026, 3, 2), libelle="LOYER APPART", montant=800.0, sens="C")
coder(op_clair, construire([]))
lot = [op_amb, op_clair]
check([o.libelle for o in residu(lot)] == ["CONFORAMA CANAPE"], "seul l'ambigu part à l'IA (le loyer reste local)")

q = questions_pour(lot)
check(len(q) == 1 and "montant" in q[0] and q[0]["options"] == op_amb.options,
      "question construite avec les options des règles + montant informatif")

# garde-fou 1 : sans client injecté, no-op total (moteur déterministe)
check(resoudre_residu(lot, None) == 0, "sans clé : couche IA = no-op")

# proposition dans le cadre des options -> retenue mais NON validée
ia = FauxIA({"CONFORAMA": "2184"})
avant_montant, avant_sens = op_amb.montant, op_amb.sens
n = resoudre_residu(lot, ia)
check(n == 1 and op_amb.options[0] == "2184", "proposition IA remontée en tête des options")
check(op_amb.a_revoir is True, "proposition ≠ validation : l'humain tranche toujours")
check(op_amb.montant == avant_montant and op_amb.sens == avant_sens,
      "l'IA ne touche NI au montant NI au sens")
check(ia.recu[0]["montant"] == 900.0 and set(ia.recu[0]) == {"id", "libelle", "montant", "sens", "options", "contexte"},
      "la question porte le montant à titre informatif, dans un schéma figé (l'IA ne décide pas d'un montant)")

# garde-fou 2 : une proposition hors options est rejetée
op_amb2 = Operation(date=D(2026, 3, 3), libelle="CONFORAMA LIT", montant=700.0, sens="D")
coder(op_amb2, construire([]))
rej = appliquer_reponses([op_amb2], [{"id": "op-%d" % id(op_amb2), "compte": "701",
                                      "confiance": 0.9, "raison": "hors cadre"}])
check(rej == 0 and "701" not in op_amb2.options, "compte hors des options -> rejeté")

print("19) Couche IA — adaptateur resolver (fournisseur inconnu) + OCR->Facture")
resolver = resolver_depuis_client(FauxIA({"WEBTECH": "606"}))
op_inc = Operation(date=D(2026, 3, 4), libelle="WEBTECH SASU", montant=40.0, sens="D")
coder(op_inc, construire([]), resolver)
check(op_inc.origine == "web" and op_inc.a_revoir, "resolver IA propose un compte, remonté à l'humain")
fac = facture_depuis_ocr(ia.lire_facture("edf.pdf")[0])
check(fac.fournisseur == "EDF" and fac.ttc == 69.34 and fac.confiance_ocr == 0.95,
      "OCR -> Facture (montant sert au rapprochement, jamais posté seul)")

print("\n%d contrôles OK — moteur cohérent." % ok)
