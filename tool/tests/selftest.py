"""Auto-test du moteur (stdlib only) : python3 tool/tests/selftest.py

Couvre les cas sensibles : parsing des montants FR, lecture FEC (délimiteurs/
encodage/débit-crédit), imputations multiples N-1, règles de codage (immo /
inconnu / multi = les 3 seuls cas remontés), rapprochement (exact/écart/
manquant), export Quadra équilibré à 256 caractères.
"""
import sys, os, datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from s2a_lmnp import (parse_montant, parse_date, parse_fec, construire, Operation, Facture,
                      coder, rapprocher, manquants, to_quadratus, verifier_equilibre,
                      comptes_absents, doublons, operations_od_factures,
                      Manifeste, DossierLocal, pieces_neuves,
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
check(not petit.a_revoir and petit.compte.startswith("606"), "petit bricolage 42 € -> 606x auto (adapté au plan)")
gros = op("CB LEROY MERLIN PARQUET", 640.0)        # bricolage >= 50 -> à trancher
coder(gros, dico)
check(gros.a_revoir, "bricolage 640 € -> à trancher (immo possible)")
petit_meuble = op("CB IKEA TABOURET", 39.0)        # mobilier < 50 -> charge auto
coder(petit_meuble, dico)
check(not petit_meuble.a_revoir and petit_meuble.compte.startswith("606"), "petit mobilier 39 € -> 606x auto (adapté au plan)")
# le seuil s'apprécie en HT quand la facture donne la TVA (on poste le TTC)
from s2a_lmnp import Facture
o_ht = op("CB CASTORAMA ETAGERE", 58.0)            # 58 TTC mais 48,33 HT -> sous le seuil
o_ht.facture = Facture("Castorama", D(2026, 3, 18), 58.0, 9.67)
coder(o_ht, dico)
check(not o_ht.a_revoir and o_ht.compte.startswith("606"),
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

print("20) Durcissement LMNP — 30 cas à risque anticipés")

def _c(lib, sens="D", montant=100.0, amort=None, assujetti=False):
    o = Operation(date=D(2026, 5, 1), libelle=lib, montant=montant, sens=sens, amort=amort)
    coder(o, construire([]), assujetti_tva=assujetti)
    return o

# -- recettes piégeuses --------------------------------------------------------
check(_c("VIR DEPOT DE GARANTIE LOCATAIRE", "C").compte == "165",
      "dépôt de garantie reçu -> 165 (dette), PAS 706")
check(_c("CAUTION LOYER STUDIO", "C").compte == "165",
      "'caution loyer' -> 165 malgré le mot LOYER")
check(_c("VIR CAF ALLOCATION LOGEMENT", "C").compte == "706",
      "APL versée par la CAF -> loyer 706 (pas une subvention)")
o = _c("VIREMENT AIRBNB PAYMENTS", "C", 742.0)
check(o.compte == "706" and o.a_revoir and "622" in o.options,
      "recette Airbnb -> 706 mais NET de commission (ventiler 622), à confirmer")
check(_c("AVOIR FOURNISSEUR MATERIAUX", "C").a_revoir,
      "avoir/remboursement reçu -> à rattacher (à confirmer)")

# -- emprunt / prêt ------------------------------------------------------------
o = _c("ECHEANCE PRET IMMOBILIER", "D", 650.0)
check(o.compte == "661" and o.a_revoir and "164" in o.options,
      "échéance de prêt sans tableau -> à ventiler 661/164 (jamais 100 % en charge)")
o = _c("ECHEANCE PRET", "D", 650.0, amort=(120.0, 530.0))
check(o.split == (120.0, 530.0) and not o.a_revoir,
      "échéance AVEC tableau -> ventilée automatiquement 661 + 164")

# -- charges récurrentes LMNP --------------------------------------------------
check(_c("TAXE FONCIERE 2026 TRESOR PUBLIC").compte == "63512", "taxe foncière -> 63512")
check(_c("PRLV CFE TRESOR PUBLIC").compte == "63511", "CFE -> 63511")
check(_c("HONORAIRES GESTION LOCATIVE AGENCE").compte == "622", "honoraires gestion -> 622")
check(_c("HONORAIRES EXPERT COMPTABLE").compte == "622", "honoraires comptable -> 622")
check(_c("ASSURANCE PNO APPARTEMENT").compte == "616", "assurance PNO -> 616")
check(_c("PRLV GLI LOYERS IMPAYES").compte == "616", "assurance GLI -> 616")
check(_c("PRLV SYNDIC COPROPRIETE T2").compte == "614", "charges de copro courantes -> 614")
o = _c("SYNDIC HONORAIRES DE GESTION")
check(o.compte == "622", "'syndic honoraires' -> 622 (honoraires avant copro)")
check(_c("VEOLIA EAU ASSAINISSEMENT").compte == "606", "eau/assainissement -> 606")
check(_c("GRDF GAZ").compte == "606", "gaz -> 606")
check(_c("FRAIS OFFICE NOTARIAL ACTE").a_revoir, "frais de notaire -> à trancher (immo/charge)")

# -- garde-fou : une BANQUE nommée 'CREDIT ...' n'est pas un prêt --------------
check(not _c("CB CREDIT MUTUEL PARIS", "D", 30.0).compte == "661",
      "'CREDIT MUTUEL' (banque) n'est pas confondu avec une échéance de prêt")

# -- TVA para-hôtelier : garde-fou anti-comptabilisation TTC ------------------
o = _c("BRICO DEPOT PEINTURE", "D", 71.07, assujetti=True)
check(o.a_revoir and "TVA" in (o.a_confirmer or ""),
      "dossier assujetti TVA -> ne PAS poster le TTC en charge (remonté)")
o2 = _c("BRICO DEPOT PEINTURE", "D", 71.07, assujetti=False)
check(not o2.a_confirmer or "TVA" not in o2.a_confirmer,
      "dossier NON assujetti -> pas de note TVA (TTC en charge, cas courant)")

# -- montants : formats bancaires piégeux -------------------------------------
check(parse_montant("120,00-") == -120.00, "signe négatif en fin de montant (relevé)")
check(parse_montant("1 234,56 €") == 1234.56, "symbole € et espace insécable")
check(parse_montant("-1 200,00") == -1200.00, "signe négatif en tête")
check(parse_montant("(89,90)") == -89.90, "parenthèses comptables = négatif")

# -- dates : formats hétérogènes des relevés ----------------------------------
check(parse_date("2026-01-05") == D(2026, 1, 5), "date ISO")
check(parse_date("05/01/2026") == D(2026, 1, 5), "date FR JJ/MM/AAAA")
check(parse_date("20260105") == D(2026, 1, 5), "date compacte AAAAMMJJ (FEC)")
check(parse_date(46027) == D(2026, 1, 5), "n° de série Excel -> date")
check(parse_date(datetime.datetime(2026, 1, 5, 9, 0)) == D(2026, 1, 5), "datetime -> date")

# -- Quadra : garde-fous export ------------------------------------------------
try:
    to_quadratus([Operation(D(2026, 1, 1), "TROP GROS", 99_999_999_999.0, "D")])
    check(False, "montant hors capacité Quadra doit lever")
except ValueError:
    check(True, "montant > 12 chiffres -> rejeté (jamais tronqué en silence)")
ligne = to_quadratus([Operation(D(2026, 1, 1), "ÉLECTRICITÉ DÉCEMBRE — 1er étage", 50.0, "D")])
check("É" not in ligne and "—" not in ligne, "libellé nettoyé (accents/caractères spéciaux) pour Quadra")
opx = Operation(D(2026, 1, 1), "EDF", 69.34, "D"); opx.compte = "606100"
opy = Operation(D(2026, 1, 1), "FOURNISSEUR X", 10.0, "D"); opy.compte = "628000"
check(comptes_absents([opx, opy], ["606100", "512000"]) == ["62800000"],
      "compte absent du plan comptable du dossier -> signalé avant import")

print("21) Le FEC du dossier fait loi — adaptation au plan comptable")
FECP = ("JournalCode|CompteNum|CompteLib|EcritureDate|EcritureLib|Debit|Credit\n"
        "BQ|626100|Telecom|20250210|SFR fibre|30,00|0,00\n"          # télécom codé 626100 ici
        "BQ|706000|Loyers|20250210|Loyer janvier|0,00|800,00\n"
        "BQ|614100|Copro Bonaparte|20250210|Charges copro Bonaparte|100,00|0,00\n"
        "BQ|614200|Copro Lepante|20250210|Charges copro Lepante|120,00|0,00\n")
dp = construire(parse_fec(FECP))
# loyer : règle générique 706 -> le dossier a un seul 706xxx -> adopté en silence
olo = Operation(date=D(2026, 5, 1), libelle="VIREMENT LOYER", montant=800.0, sens="C")
coder(olo, dp)
check(olo.compte == "706000" and not olo.a_revoir,
      "loyer 706 -> adopte le 706000 réel du dossier (adaptation silencieuse)")
# copro : le dossier a DEUX comptes 614 (par bien) -> à choisir, pas d'auto
ocp = Operation(date=D(2026, 5, 1), libelle="PRLV SYNDIC COPROPRIETE", montant=150.0, sens="D")
coder(ocp, dp)
check(ocp.a_revoir and {"614100", "614200"}.issubset(set(ocp.options)),
      "compte 614 -> le dossier a 614100/614200 -> à choisir (quel bien)")
# taxe foncière : aucune racine 635 mouvementée -> compte générique conservé
# (le vrai contrôle "compte inexistant" est comptes_absents sur le plan Quadra)
otf = Operation(date=D(2026, 5, 1), libelle="TAXE FONCIERE", montant=500.0, sens="D")
coder(otf, dp)
check(otf.compte == "63512", "racine absente du FEC -> compte générique conservé (pas de faux 'à créer')")
# fournisseur connu du FEC -> compte du dossier direct (dico), pas d'adaptation
osfr = Operation(date=D(2026, 5, 1), libelle="SFR FIBRE", montant=30.0, sens="D")
coder(osfr, dp)
check(osfr.compte == "626100" and osfr.origine in ("dict", "fuzzy"),
      "fournisseur connu du FEC -> compte du dossier (dico), adaptation non nécessaire")
# plan vide (pas de FEC) -> l'adaptation ne casse rien (no-op)
ovide = Operation(date=D(2026, 5, 1), libelle="TAXE FONCIERE", montant=500.0, sens="D")
coder(ovide, construire([]))
check(ovide.compte == "63512", "sans FEC : compte générique conservé (adaptation no-op)")

print("22) Ingestion & idempotence — on ne re-traite jamais une pièce (ni re-OCR)")
import tempfile, shutil
with tempfile.TemporaryDirectory() as tmp:
    for nom, contenu in (("edf.pdf", b"FACTURE EDF 69.34"),
                         ("brico.pdf", b"TICKET BRICO 71.07"),
                         ("bouygues.pdf", b"FACTURE BYG 44.99")):
        with open(os.path.join(tmp, nom), "wb") as f:
            f.write(contenu)
    src = DossierLocal(tmp)
    pieces = src.lister()
    check(len(pieces) == 3 and len({p.empreinte for p in pieces}) == 3,
          "3 pièces listées, empreintes distinctes")

    man = Manifeste()
    check(len(pieces_neuves(src, man)) == 3, "manifeste vide -> les 3 pièces sont neuves")

    # on 'traite' EDF et Brico (1er passage)
    for p in pieces:
        if p.nom in ("edf.pdf", "brico.pdf"):
            man.marquer(p.empreinte, p.nom)
    check(len(pieces_neuves(src, man)) == 1, "après traitement de 2 -> 1 seule pièce neuve")

    # un fichier RENOMMÉ (même contenu) n'est PAS re-traité (empreinte = contenu)
    shutil.copy(os.path.join(tmp, "edf.pdf"), os.path.join(tmp, "EDF_janvier_RENOMME.pdf"))
    neuves = pieces_neuves(src, man)
    check(len(neuves) == 1 and neuves[0].nom == "bouygues.pdf",
          "fichier renommé (même contenu) -> non re-traité (anti re-OCR)")

    # persistance du manifeste (le cabinet le garde d'une période à l'autre)
    chemin = os.path.join(tmp, "manifeste.json")
    man.chemin = chemin
    man.sauver()
    man2 = Manifeste(chemin)
    check(len(man2) == 2 and all(man2.est_traite(p.empreinte)
          for p in pieces if p.nom in ("edf.pdf", "brico.pdf")),
          "manifeste sauvegardé puis rechargé -> mémoire des pièces traitées conservée")

print("23) Orchestrateur bout-en-bout (traiter_dossier)")
from s2a_lmnp import traiter_dossier

class _FauxIA23:
    def resoudre(self, questions, *, modele=None):
        return [{"id": q["id"], "compte": q["options"][0], "confiance": 0.8, "raison": "t"}
                for q in questions]
    def lire_facture(self, chemin, *, modele=None):
        return []

FEC23 = ("JournalCode|CompteNum|CompteLib|EcritureDate|EcritureLib|Debit|Credit\n"
         "BQ|606100|Energie|20250210|EDF energie|57,79|0,00\n"
         "BQ|706000|Loyers|20250105|Loyer|0,00|800,00\n")
d23 = construire(parse_fec(FEC23))
facs = [Facture("EDF", D(2026, 1, 5), 69.34, 11.55), Facture("BRICO DEPOT", D(2026, 1, 9), 71.07, 11.84)]
ops23 = [
    Operation(D(2026, 1, 5), "VIREMENT LOYER", 800.0, "C"),
    Operation(D(2026, 1, 20), "EDF ENERGIE", 69.34, "D"),
    Operation(D(2026, 1, 9), "BRICO DEPOT NICE", 71.07, "D"),
    Operation(D(2026, 1, 12), "MOBILIER INCONNU SARL", 900.0, "D"),
]
res = traiter_dossier(facs, ops23, d23, client_ia=_FauxIA23(),
                      compte_banque="51210010", journal="BQ")
check(res["quadra"].count("\r\n") == 4, "orchestrateur : 4 lignes M produites")
check(res["residu_resolu_par_ia"] >= 1, "orchestrateur : résidu ambigu résolu par l'IA")
check(any(o.compte == "606100" for o in res["operations"]), "orchestrateur : EDF adapté au plan (606100)")
check(len(res["a_reclamer"]) == 1 and res["a_reclamer"][0].montant == 900.0,
      "orchestrateur : mobilier 900 € sans facture -> à réclamer")
# sans banque -> écriture d'OD, contrepartie 108 (factures neuves : un autre dossier)
facs_od = [Facture("EDF", D(2026, 1, 5), 69.34, 11.55), Facture("BRICO DEPOT", D(2026, 1, 9), 71.07, 11.84)]
res_od = traiter_dossier(facs_od, None, d23, avec_banque=False)
check(res_od["quadra"].count("\r\n") == 2 and "10800000" in res_od["quadra"],
      "orchestrateur sans banque -> OD contrepartie 108")

print("\n%d contrôles OK — moteur cohérent." % ok)
