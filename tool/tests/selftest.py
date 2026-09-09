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

print("3bis) Seuil d'immobilisation = 500 € HT (sous le seuil -> charge auto)")
petit = op("CB LEROY MERLIN VISSERIE", 42.0)      # bricolage < 50 -> charge auto
coder(petit, dico)
check(not petit.a_revoir and petit.compte.startswith("606"), "petit bricolage 42 € -> 606x auto (adapté au plan)")
gros = op("CB LEROY MERLIN PARQUET", 640.0)        # bricolage >= 500 -> à trancher
coder(gros, dico)
check(gros.a_revoir, "bricolage 640 € -> à trancher (immo possible)")
petit_meuble = op("CB IKEA TABOURET", 39.0)        # mobilier < 50 -> charge auto
coder(petit_meuble, dico)
check(not petit_meuble.a_revoir and petit_meuble.compte.startswith("606"), "petit mobilier 39 € -> 606x auto (adapté au plan)")
# le seuil s'apprécie en HT quand la facture donne la TVA (on poste le TTC)
from s2a_lmnp import Facture
o_ht = op("CB CASTORAMA ETAGERE", 540.0)           # 540 TTC mais 450 HT -> sous le seuil
o_ht.facture = Facture("Castorama", D(2026, 3, 18), 540.0, 90.0)
coder(o_ht, dico)
check(not o_ht.a_revoir and o_ht.compte.startswith("606"),
      "540 € TTC = 450 € HT < 500 -> charge auto (seuil apprécié en HT)")

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

class _FauxConf(FauxIA):
    def __init__(self, regle, conf):
        super().__init__(regle); self.conf = conf
    def resoudre(self, questions, *, modele=None):
        self.recu = questions
        rep = []
        for q in questions:
            compte = None
            for cle, c in self.regle.items():
                if cle in (q["libelle"] or ""):
                    compte = c
            if compte is not None:
                rep.append({"id": q["id"], "compte": compte, "confiance": self.conf, "raison": "t"})
        return rep

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

# confiance élevée (0.9 ≥ seuil) -> CODÉ AUTOMATIQUEMENT (automatisation max)
ia = FauxIA({"CONFORAMA": "2184"})
avant_montant, avant_sens = op_amb.montant, op_amb.sens
n = resoudre_residu(lot, ia)
check(n == 1 and op_amb.compte == "2184" and op_amb.origine == "ia" and not op_amb.a_revoir,
      "confiance élevée -> l'IA code automatiquement (doute faible)")
check(op_amb.montant == avant_montant and op_amb.sens == avant_sens,
      "l'IA ne touche NI au montant NI au sens")
check(ia.recu[0]["montant"] == 900.0 and set(ia.recu[0]) ==
      {"id", "libelle", "montant", "sens", "options", "contexte", "inconnu"},
      "la question porte le montant à titre informatif (l'IA ne décide pas d'un montant)")

# confiance faible -> proposition, l'humain tranche (doute sérieux)
op_faible = Operation(date=D(2026, 3, 5), libelle="CONFORAMA TABLE", montant=850.0, sens="D")
coder(op_faible, construire([]))
resoudre_residu([op_faible], _FauxConf({"CONFORAMA": "2184"}, 0.55))
check(op_faible.a_revoir and op_faible.a_confirmer, "confiance faible -> proposition à valider (doute sérieux)")

# fournisseur INCONNU -> l'IA propose librement un compte (raisonne comme un comptable)
op_inc2 = Operation(date=D(2026, 3, 6), libelle="STUDIO CREATIF SASU", montant=60.0, sens="D")
coder(op_inc2, construire([]))
check(op_inc2.compte == "471" and len(residu([op_inc2])) == 1, "inconnu -> envoyé à l'IA (pas laissé en 471)")
resoudre_residu([op_inc2], _FauxConf({"STUDIO": "6226"}, 0.9))
check(op_inc2.compte == "6226" and op_inc2.origine == "ia" and not op_inc2.a_revoir,
      "inconnu codé auto par l'IA (compte PCG proposé hors options)")

# garde-fou : compte hors options rejeté quand les options SONT connues
op_amb2 = Operation(date=D(2026, 3, 3), libelle="CONFORAMA LIT", montant=700.0, sens="D")
coder(op_amb2, construire([]))
rej = appliquer_reponses([op_amb2], [{"id": "op-%d" % id(op_amb2), "compte": "701",
                                      "confiance": 0.9, "raison": "hors cadre"}])
check(rej == 0 and "701" not in op_amb2.options, "compte hors options (choix connu) -> rejeté")

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

print("24) Revue analytique N vs N-1 (contrôles de cohérence)")
from s2a_lmnp import revue_analytique, reference, preparer_relances, traiter_lot

FEC_N1 = (
    "JournalCode|CompteNum|CompteLib|EcritureDate|EcritureLib|Debit|Credit\n"
    # EDF récurrent : 8 mois en N-1
    + "".join("BQ|606100|Energie|202503%02d|EDF energie|58,00|0,00\n" % (i + 1) for i in range(8))
    + "BQ|616000|Assurance|20250310|Assurance PNO|180,00|0,00\n"
)
ln1 = parse_fec(FEC_N1)
ref = reference(ln1)
check(ref.get("EDF ENERGIE", {}).get("count") == 8, "référence N-1 : EDF vu 8 fois")

# cette année : EDF a disparu, l'assurance a doublé
ops24 = [
    Operation(D(2026, 3, 10), "ASSURANCE PNO", 380.00, "D"),   # 180 -> 380 : hausse
    Operation(D(2026, 4, 1), "ACHAT PONCTUEL", 90.00, "D"),
]
for o in ops24:
    coder(o, construire(ln1))
anos = revue_analytique(ops24, ln1)
types = {a["type"] for a in anos}
check("recurrent_manquant" in types, "revue : EDF récurrent disparu -> signalé")
check("ecart_montant" in types, "revue : assurance qui double -> écart signalé")
check(anos[0]["gravite"] in ("alerte", "attention"), "revue : anomalies triées par gravité")

print("25) Relance client — verrou de certitude (ne relancer que le sûr)")
op_connu = Operation(D(2026, 5, 1), "ASSURANCE PNO", 380.00, "D"); coder(op_connu, construire(ln1))
op_gros = Operation(D(2026, 5, 2), "GROS ACHAT FOURNISSEUR X", 900.00, "D"); coder(op_gros, construire([]))
op_petit = Operation(D(2026, 5, 3), "PETIT FOURNISSEUR PONCTUEL", 160.00, "D"); coder(op_petit, construire([]))
rel = preparer_relances([op_connu, op_gros, op_petit], ref, seuil=150.0)
noms_certain = {o.libelle for o in rel["certain"]}
check("ASSURANCE PNO" in noms_certain, "relance certaine : fournisseur récurrent N-1")
check("GROS ACHAT FOURNISSEUR X" in noms_certain, "relance certaine : montant important")
check(any(o.libelle == "PETIT FOURNISSEUR PONCTUEL" for o in rel["a_verifier"]),
      "petit fournisseur ponctuel -> à vérifier avant de relancer (pas d'envoi auto)")
check("Bonjour" in rel["brouillon"] and "ASSURANCE PNO" in rel["brouillon"],
      "brouillon de mail généré pour les pièces certaines")

print("26) Traitement en lot + tableau de bord cabinet")
d1 = {"nom": "DUPONT", "factures": [Facture("EDF", D(2026, 1, 5), 58.0, 9.6)],
      "ops_banque": [Operation(D(2026, 1, 6), "EDF ENERGIE", 58.0, "D")],
      "dico": construire(ln1), "compte_banque": "512", "journal": "BQ"}
d2 = {"nom": "MARTIN", "factures": [],
      "ops_banque": [Operation(D(2026, 1, 8), "MOBILIER INCONNU", 900.0, "D")],
      "dico": construire([]), "compte_banque": "512", "journal": "BQ"}
lot = traiter_lot([d1, d2])
check(lot["totaux"]["dossiers"] == 2, "lot : 2 dossiers traités")
tb = {r["dossier"]: r for r in lot["tableau_de_bord"]}
check(tb["DUPONT"]["statut"] == "prêt", "tableau de bord : DUPONT prêt (tout codé, rapproché)")
check(tb["MARTIN"]["statut"] in ("à valider", "en attente de pièces"),
      "tableau de bord : MARTIN à traiter (mobilier à trancher, facture manquante)")
check(isinstance(lot["totaux"]["cout_ia_eur"], float), "tableau de bord : coût IA agrégé")
check(all(l["cout_mesure"] is False and l["cout_ia_eur"] == 0.0
          for l in lot["tableau_de_bord"]),
      "sans client IA : coût à 0 et marqué non mesuré (plus d'estimation inventée)")

print("27) Avec banque : facture payée hors relevé -> OD 108 ; banque -> Excel ; multi-banque")
from s2a_lmnp import journal_banque_xlsx, lignes_journal_banque
import zipfile as _zip, io as _io

FEC27 = ("JournalCode|CompteNum|CompteLib|EcritureDate|EcritureLib|Debit|Credit\n"
         "BQ|606100|Energie|20250210|EDF energie|57,79|0,00\n")
d27 = construire(parse_fec(FEC27))
# une facture est reprise en banque, l'autre a été payée en perso (absente du relevé)
facs27 = [Facture("EDF", D(2026, 1, 5), 69.34, 11.55),
          Facture("PLOMBERIE PERSO", D(2026, 1, 8), 240.00, 40.0)]
ops27 = [Operation(D(2026, 1, 6), "EDF ENERGIE", 69.34, "D")]   # seule EDF est en banque
res27 = traiter_dossier(facs27, ops27, d27, compte_banque="512", journal="BQ")
check(len(res27["operations_od"]) == 1, "facture payée hors banque -> écriture d'OD")
check(res27["od_ascii"] and "10800000" in res27["od_ascii"], "OD 108 sorti en ASCII séparé")
check("EDF" in res27["quadra"], "les opérations de banque restent au journal BQ")

# export Excel du journal de banque = un vrai .xlsx (zip lisible), trié, montants nombres
xlsx = journal_banque_xlsx(res27["operations"])
zf = _zip.ZipFile(_io.BytesIO(xlsx))
check("xl/worksheets/sheet1.xml" in zf.namelist() and "[Content_Types].xml" in zf.namelist(),
      "journal de banque -> .xlsx valide (ouvrable dans Excel)")

# multi-banque : deux comptes bancaires -> deux journaux (BQ1, BQ2), un seul tableau
a = Operation(D(2026, 2, 1), "OP BANQUE A", 100.0, "D"); a.compte = "606"; a.compte_bancaire = "CPTE_A"
b = Operation(D(2026, 2, 2), "OP BANQUE B", 200.0, "D"); b.compte = "615"; b.compte_bancaire = "CPTE_B"
lignes = lignes_journal_banque([b, a], journaux={"CPTE_A": "BQ1", "CPTE_B": "BQ2"})
journaux_vus = [l[0] for l in lignes[1:]]
check(journaux_vus == ["BQ1", "BQ2"], "multi-banque : chaque banque dans son journal (BQ1/BQ2), trié")

# le code journal de banque se DÉDUIT du FEC (512 variante -> son journal), pas d'invention
from s2a_lmnp import journaux_banque_depuis_fec
FECJ = ("JournalCode|CompteNum|EcritureLib|Debit|Credit|EcritureDate\r\n"
        "BQ1|51210010|VIR|10,00|0,00|20260101\r\n"
        "BQ2|51200002|VIR|0,00|10,00|20260101\r\n"
        "OD|60611000|EDF|10,00|0,00|20260101\r\n")
mj = journaux_banque_depuis_fec(parse_fec(FECJ))
check(mj == {"51210010": "BQ1", "51200002": "BQ2"},
      "code journal de banque déduit du FEC (chaque 512 -> son journal réel)")

print("28) Classement d'entrée : un devis ne devient jamais une facture")
from s2a_lmnp import (valider, trier, est_comptable, coherence_ttc,
                      sens_ecriture, factures_depuis_ocr, CATEGORIES)

def _piece(**kw):
    """Objet brut conforme au contrat A (tous les champs présents)."""
    b = {"categorie": "facture_achat", "confiance_classement": 0.95,
         "fournisseur": "EDF", "date": "2026-01-05", "ttc": 69.34, "tva": 11.55,
         "ht": 57.79, "numero": "F1", "adresse_bien": "", "date_flux": "",
         "confiance": 0.95}
    b.update(kw)
    return b

# -- le cas qui motive tout le chantier --------------------------------------
devis = _piece(categorie="devis", fournisseur="", date="", ttc=0, tva=0, ht=0, numero="")
okd, motif = valider(devis)
check(not okd and "non comptable" in motif, "devis propre -> rejeté, aucune écriture")

devis_chiffre = _piece(categorie="devis")     # devis AVEC montants remplis
okdc, motifdc = valider(devis_chiffre)
check(not okdc and "champs comptables remplis" in motifdc,
      "devis chiffré -> rejeté (le modèle a extrait avant de classer)")

check(valider(_piece())[0], "facture d'achat complète et cohérente -> retenue")

# -- contrôle HT + TVA = TTC -------------------------------------------------
check(coherence_ttc(57.79, 11.55, 69.34), "HT + TVA = TTC -> cohérent")
check(not coherence_ttc(50.00, 11.55, 69.34), "HT + TVA ≠ TTC -> incohérent")
check(coherence_ttc(0, 0, 71.07), "ticket sans détail de TVA -> contrôle non applicable")
inc = valider(_piece(ht=50.0))
check(not inc[0] and "incohérence des montants" in inc[1],
      "montants incohérents -> rejeté avec motif")

# -- seuils (la confiance OCR était du code mort avant ce chantier) ----------
check(not valider(_piece(confiance=0.40))[0], "extraction peu sûre -> rejetée")
check(not valider(_piece(confiance_classement=0.50))[0], "classement peu sûr -> rejeté")

# -- catégories --------------------------------------------------------------
check(est_comptable("facture_achat") and est_comptable("avoir")
      and not est_comptable("releve_bancaire"), "catégories comptables vs autres")
check(not valider(_piece(categorie="bidon"))[0], "catégorie inconnue -> rejetée")
check(not valider(_piece(categorie=""))[0], "catégorie absente -> rejetée")
check(sens_ecriture("avoir") == "C" and sens_ecriture("facture_achat") == "D",
      "un avoir produit une écriture de sens inverse")

# -- tri : rien n'est écarté en silence -------------------------------------
lot = [_piece(), devis, _piece(categorie="releve_bancaire", fournisseur="", date="",
                               ttc=0, tva=0, ht=0, numero=""), _piece(numero="F2")]
gardes, rejets = trier(lot)
check(len(gardes) == 2 and len(rejets) == 2, "tri : 2 retenues, 2 rejetées")
check(all(r["motif"] for r in rejets), "chaque rejet porte un motif explicite")
facs28, rej28 = factures_depuis_ocr(lot)
check(len(facs28) == 2 and facs28[0].categorie == "facture_achat"
      and facs28[0].confiance_classement == 0.95,
      "factures_depuis_ocr : catégorie et confiance tracées sur la Facture")

# -- le schéma déclare bien la catégorie en PREMIER --------------------------
import s2a_lmnp.client_anthropic as _ca
_props = list(_ca._SCHEMA_FACTURE["properties"]["factures"]["items"]["properties"])
check(_props[0] == "categorie" and _props[1] == "confiance_classement",
      "schéma : categorie en premier champ (le modèle s'engage avant d'extraire)")
check(set(_ca._SCHEMA_FACTURE["properties"]["factures"]["items"]
          ["properties"]["categorie"]["enum"]) == set(CATEGORIES),
      "schéma : enum des catégories aligné sur classement.py")

# -- escalade OCR (absente avant ce chantier) --------------------------------
check(_ca.ClientAnthropic._doute([_piece(confiance_classement=0.50)]),
      "escalade : classement peu sûr -> modèle fort")
check(_ca.ClientAnthropic._doute([]), "escalade : rien lu -> modèle fort")
check(_ca.ClientAnthropic._doute([_piece(categorie="devis")]),
      "escalade : non comptable avec un TTC -> modèle fort")
check(not _ca.ClientAnthropic._doute([_piece()]),
      "facture nette -> pas d'escalade (on ne paye pas Sonnet pour rien)")

print("29) Prétraitement des images : gain de coût, et repli JAMAIS silencieux")
import warnings as _w
from s2a_lmnp.pretraitement import (Journal, reduire_image, tokens_image,
                                    COTE_MAX, SEUIL_ALERTE_REPLI)

# le gain visé : une A4 scannée en 300 DPI vs réduite à 1 500 px
check(tokens_image(2480, 3508) > 3 * tokens_image(1060, COTE_MAX),
      "A4 300 DPI coûte >3× la même page réduite à 1 500 px")
check(tokens_image(0, 0) == 0, "image de taille nulle -> 0 token")

# repli : il doit AVERTIR, être COMPTÉ, et ne rien casser
j29 = Journal()
with _w.catch_warnings(record=True) as capt:
    _w.simplefilter("always")
    data29, media29 = reduire_image(b"ceci n'est pas une image", journal=j29)
check(data29 == b"ceci n'est pas une image" and media29 is None,
      "repli : la pièce brute est renvoyée telle quelle")
check(len(capt) == 1 and issubclass(capt[0].category, RuntimeWarning),
      "repli : un avertissement est émis (pas de silence)")
check(j29.replis == 1 and j29.pieces == 1 and j29.motifs_replis,
      "repli : compté dans le journal, avec son motif")

# seuil d'alerte à 5 % d'un lot
j_ok = Journal(); j_ok.pieces, j_ok.replis = 100, 3
j_ko = Journal(); j_ko.pieces, j_ko.replis = 100, 6
j_ko.motifs_replis = {"pillow_absent": 6}
check(not j_ok.alerte(), "3 %% de replis -> pas d'alerte (seuil %.0f %%)" % (100 * SEUIL_ALERTE_REPLI))
check("ALERTE" in j_ko.alerte() and "6/100" in j_ko.alerte(),
      "6 % de replis -> alerte chiffrée avec les motifs")
r29 = j_ko.resume()
check(r29["taux_repli"] == 0.06 and r29["alerte"],
      "le journal expose taux_repli et alerte au tableau de bord")

print("30) Coût mesuré (response.usage) et cache du préfixe")
from s2a_lmnp import Compteur, TARIFS, CIBLE_LECTURE_CACHE

class _U:                       # imite un objet usage de l'API
    def __init__(self, e=0, s=0, ce=0, cl=0):
        self.input_tokens, self.output_tokens = e, s
        self.cache_creation_input_tokens, self.cache_read_input_tokens = ce, cl

c30 = Compteur()
c30.enregistrer("claude-haiku-4-5", _U(e=1000, s=200, ce=2500, cl=0))   # 1er appel
for _ in range(199):
    c30.enregistrer("claude-haiku-4-5", _U(e=1000, s=200, ce=0, cl=2500))
check(c30.appels == 200, "200 appels enregistrés")
# tarif Haiku : 1 $/M entrée, 5 $/M sortie ; écriture 1,25× ; lecture 0,10×
attendu = (200_000/1e6*1.0 + 40_000/1e6*5.0 + 2_500/1e6*1.0*1.25
           + 497_500/1e6*1.0*0.10)
check(abs(c30.cout_usd - attendu) < 1e-6, "coût calculé au tarif public exact")
# réutilisation du préfixe : écrit 1 fois, relu 199 fois -> 99,5 %
check(c30.taux_lecture_cache > 0.99, "préfixe réutilisé sur ~199 appels sur 200")
# la part des tokens d'ENTRÉE cachés plafonne bien plus bas : les images dominent
check(0.60 < c30.part_entree_cachee < 0.80,
      "part des tokens d'entrée cachés ~70 % (les images ne sont pas cachables)")
check(not c30.alerte(nb_factures=200), "dossier normal -> pas d'alerte")

# sans cache : le taux s'effondre et l'alerte tombe (c'est le bug à détecter)
c31 = Compteur()
for _ in range(200):
    c31.enregistrer("claude-haiku-4-5", _U(e=3500, s=200))
check(c31.taux_lecture_cache == 0.0, "préfixe non caché -> réutilisation nulle")
check("réutilisation du préfixe" in c31.alerte(nb_factures=200),
      "cache invalidé sur 200 factures -> alerte explicite")
check(c31.cout_usd > c30.cout_usd, "sans cache, le dossier coûte plus cher")

# plafond de dérive
c32 = Compteur(); c32.enregistrer("claude-sonnet-5", _U(e=3_000_000, s=100_000))
check("plafond" in c32.alerte(nb_factures=200), "dossier au-delà de 3 € -> alerte plafond")

# le résumé exposé au tableau de bord
r30 = c30.resume(nb_factures=200)
check(r30["cout_eur_par_facture"] > 0 and r30["appels"] == 200
      and "claude-haiku-4-5" in r30["par_modele"],
      "résumé : coût par facture et ventilation par modèle")
check(set(TARIFS) >= {"claude-haiku-4-5", "claude-sonnet-5"},
      "tarifs Haiku et Sonnet présents")
check(c30.enregistrer("claude-haiku-4-5", None) is None,
      "usage absent (hors API) -> toléré, pas de plantage")

# le préfixe système est bien marqué en cache dans l'appel
import inspect as _i
_src = _i.getsource(_ca.ClientAnthropic._json)
check('"cache_control"' in _src and '"ephemeral"' in _src,
      "le prompt système est marqué cache_control ephemeral")
check("self.compteur.enregistrer" in _src,
      "chaque appel enregistre son usage réel")

print("31) Trésorerie : le relevé fait foi ; l'OD est datée du JOUR DU RÈGLEMENT")
from s2a_lmnp import operations_od_factures, factures_depuis_ocr

# facture de décembre, réglée en janvier : en trésorerie l'écriture tombe en JANVIER
f31 = Facture("PLOMBERIE DURAND", D(2025, 12, 28), 240.0, 40.0)
f31.date_reglement = D(2026, 1, 12)
ops31 = operations_od_factures([f31], d23)
check(len(ops31) == 1 and ops31[0].date == D(2026, 1, 12),
      "OD datée du règlement (12/01/2026), pas de la facture (28/12/2025)")
check(not ops31[0].a_confirmer, "date de règlement connue -> aucune confirmation demandée")

# sans date de règlement : repli sur la date de facture, mais signalé
f32 = Facture("PLOMBERIE DURAND", D(2025, 12, 28), 240.0, 40.0)
ops32 = operations_od_factures([f32], d23)
check(ops32[0].date == D(2025, 12, 28), "sans date de règlement -> repli sur la facture")
check("Date de règlement absente" in ops32[0].a_confirmer,
      "le repli est signalé à l'humain, jamais silencieux")

# une facture DÉJÀ rapprochée au relevé ne produit pas d'OD (le relevé fait foi)
f33 = Facture("EDF", D(2026, 1, 5), 69.34, 11.55)
f33.op = Operation(D(2026, 1, 6), "EDF ENERGIE", 69.34, "D")
check(operations_od_factures([f33], d23) == [], "facture rapprochée en banque -> pas d'OD")

# la date de règlement remonte de l'OCR (« prélevé le ») jusqu'à la Facture
brut31 = {"categorie": "facture_achat", "confiance_classement": 0.95,
          "fournisseur": "EDF", "date": "2025-12-28", "ttc": 69.34, "tva": 11.55,
          "ht": 57.79, "numero": "F9", "adresse_bien": "", "date_flux": "2026-01-12",
          "payee": True, "confiance": 0.95}
fac31, rej31 = factures_depuis_ocr([brut31])
check(fac31[0].date_reglement == D(2026, 1, 12) and fac31[0].payee,
      "OCR : « prélevé le » -> date_reglement et pièce acquittée")

print("32) Rangement du dossier de sortie : exercice, mois de RÈGLEMENT, statut")
from s2a_lmnp import (ranger, chemin, mois_de, resume_rangement, Exercice,
                      exercice_de, sans_rapport, RACINE, TRAITE, EN_ATTENTE,
                      SANS_RAPPORT)

# facture de décembre réglée en janvier -> rangée en 2026-01 (comme l'écriture)
fr1 = Facture("EDF", D(2025, 12, 28), 69.34); fr1.date_reglement = D(2026, 1, 12)
fr1.fichier = "edf.pdf"
check(mois_de(fr1) == ("2026-01", False), "mois = date de règlement, pas de facture")
check(chemin(fr1, traite=True) == RACINE + "/Exercice 2026/2026-01/" + TRAITE,
      "chemin complet racine/exercice/mois/Traité")

# sans date de règlement -> repli sur la facture, marqué comme estimé
fr2 = Facture("BRICO", D(2026, 3, 9), 71.07); fr2.fichier = "brico.pdf"
check(mois_de(fr2) == ("2026-03", True), "sans règlement -> mois estimé depuis la facture")

# une pièce sans aucune date ne fait pas planter le rangement
fr3 = Facture("SANS DATE", None, 10.0)
check(mois_de(fr3) == ("sans-date", True), "pièce sans date -> dossier « sans-date »")

# les rejets partent en attente, avec leur motif
rej32 = [{"brut": {"date": "2026-03-15"}, "fichier": "devis.pdf",
          "empreinte": "abc", "motif": "document « devis » : non comptable"}]
plan = ranger([fr1, fr2], rej32)
vue = {l["chemin"]: l["pieces"] for l in resume_rangement(plan)}
E26 = RACINE + "/Exercice 2026"
check(vue.get(E26 + "/2026-01/" + TRAITE) == 1, "EDF -> 2026-01/Traité")
check(vue.get(E26 + "/2026-03/" + TRAITE) == 1, "Brico -> 2026-03/Traité")
check(vue.get(E26 + "/2026-03/" + EN_ATTENTE) == 1, "devis -> 2026-03/En attente")
attente = plan[E26 + "/2026-03/" + EN_ATTENTE][0]
check(attente["motif"] and attente["fichier"] == "devis.pdf",
      "la pièce en attente garde son motif et son nom de fichier")
check(sum(len(v) for v in plan.values()) == 3, "aucune pièce perdue dans le plan")

# L'exercice passe AVANT le mois : deux années ne se mélangent jamais.
ex26 = Exercice(D(2026, 1, 1), D(2026, 12, 31))
hors = Facture("EDF JANVIER 2027", D(2026, 12, 30), 71.0)
hors.date_reglement = D(2027, 1, 8); hors.fichier = "edf-janv.pdf"
check(chemin(hors, traite=True, exercice=ex26)
      == RACINE + "/Hors exercice 2027/2027-01/" + TRAITE,
      "pièce hors de l'exercice traité -> rangée à part, pas noyée")
check(chemin(fr1, traite=True, exercice=ex26)
      == RACINE + "/Exercice 2026/2026-01/" + TRAITE,
      "pièce de l'exercice -> dossier de l'exercice")

# Un exercice décalé porte le millésime de sa clôture.
ex_dec = Exercice(D(2026, 7, 1), D(2027, 6, 30))
check(ex_dec.libelle == "Exercice 2027", "exercice décalé -> millésime de clôture")
f_dec = Facture("SEPTEMBRE", D(2026, 9, 2), 100.0); f_dec.date_reglement = D(2026, 9, 5)
check(chemin(f_dec, traite=True, exercice=ex_dec)
      == RACINE + "/Exercice 2027/2026-09/" + TRAITE,
      "exercice décalé : septembre 2026 appartient à l'exercice 2027")
check(exercice_de(None) == "Exercice indéterminé", "sans date -> exercice indéterminé")
try:
    Exercice(D(2026, 12, 31), D(2026, 1, 1)); ko = False
except ValueError:
    ko = True
check(ko, "un exercice qui se ferme avant de s'ouvrir est refusé")

# Ce qui n'a rien à voir avec la comptabilité sort du rangement par mois.
hors_compta = [
    {"brut": {"date": "2026-04-02"}, "categorie": "hors_sujet",
     "fichier": "photo_chat.jpg", "empreinte": "c4t",
     "motif": "document « hors_sujet » : non comptable"},
    {"brut": {"date": "2026-01-15"}, "categorie": "contrat",
     "fichier": "bail_signe.pdf", "empreinte": "b41l",
     "motif": "document « contrat » : non comptable"},
    {"brut": {"date": "2026-02-01"}, "categorie": "releve_bancaire",
     "fichier": "releve_fevrier.pdf", "empreinte": "r3l",
     "motif": "document « releve_bancaire » : non comptable"},
]
check(all(sans_rapport(r) for r in hors_compta), "photo, contrat, relevé : sans rapport")
check(not sans_rapport(rej32[0]), "un devis A un rapport : il peut devenir une facture")

plan34 = ranger([fr1], hors_compta + rej32, exercice=ex26)
dossier_autres = RACINE + "/" + SANS_RAPPORT
check(len(plan34.get(dossier_autres, [])) == 3,
      "les trois pièces hors comptabilité vont dans un dossier unique")
check(all("/2026-" not in dossier_autres for _ in [0]),
      "ce dossier n'est PAS rangé par mois")
check(len(plan34.get(RACINE + "/Exercice 2026/2026-03/" + EN_ATTENTE, [])) == 1,
      "le devis reste en attente, dans son mois")
check(sum(len(v) for v in plan34.values()) == 5, "aucune pièce perdue")
check(plan34[dossier_autres][0]["motif"], "chaque pièce écartée garde son motif")

print("33) Connecteur Drive : même interface, lecture seule, empreinte du contenu")
from s2a_lmnp import (DriveGoogle, DependanceManquante, PORTEE, SANS_ECRITURE,
                      SourcePieces, empreinte_bytes)

check(SANS_ECRITURE and PORTEE == ("https://www.googleapis.com/auth/drive.readonly",),
      "le connecteur ne demande QUE la lecture")
check(not any(n.startswith(("supprimer", "ecrire", "televerser", "renommer"))
              for n in dir(DriveGoogle)),
      "aucune méthode d'écriture sur la source")
try:
    DriveGoogle(""); ko = False
except ValueError:
    ko = True
check(ko, "un identifiant de dossier vide est refusé")

# --- Drive bouché : on vérifie le comportement, pas l'API de Google ---------
class FauxDrive:
    """Reproduit le strict nécessaire de l'API v3 : arborescence + contenu."""
    ARBRE = {
        "racine": [
            {"id": "d1", "name": "DUPONT", "mimeType": "application/vnd.google-apps.folder"},
            {"id": "f9", "name": "notes.txt", "mimeType": "text/plain"},
        ],
        "d1": [
            {"id": "d2", "name": "2026", "mimeType": "application/vnd.google-apps.folder"},
        ],
        "d2": [
            {"id": "f1", "name": "edf.pdf", "mimeType": "application/pdf", "size": "12"},
            {"id": "f2", "name": "brico.jpg", "mimeType": "image/jpeg", "size": "9"},
            {"id": "f3", "name": "copie.pdf", "mimeType": "application/pdf", "size": "12"},
        ],
    }
    CONTENU = {"f1": b"facture-edf", "f2": b"photo-bric", "f3": b"facture-edf"}
    def __init__(self): self.appels = 0
    def files(self): return self
    def list(self, q="", **kw):
        parent = q.split("'")[1]
        self._rep = {"files": list(self.ARBRE.get(parent, []))}
        return self
    def get_media(self, fileId=None, **kw):
        self.appels += 1
        self._rep = self.CONTENU[fileId]
        return self
    def get(self, fileId=None, **kw):
        self._rep = {"id": fileId, "name": "Input compta tréso"}
        return self
    def execute(self): return self._rep

faux = FauxDrive()
src = DriveGoogle("racine", service=faux)
check(isinstance(src, SourcePieces), "DriveGoogle respecte l'interface SourcePieces")
refs = src.lister()
check(len(refs) == 3, "les 3 pièces lisibles sont vues, le .txt est ignoré")
check(sorted(r.nom for r in refs)
      == ["DUPONT/2026/brico.jpg", "DUPONT/2026/copie.pdf", "DUPONT/2026/edf.pdf"],
      "le chemin client/année est conservé dans le nom")
edf = [r for r in refs if r.nom.endswith("edf.pdf")][0]
copie = [r for r in refs if r.nom.endswith("copie.pdf")][0]
check(edf.empreinte == empreinte_bytes(b"facture-edf"),
      "l'empreinte est le sha256 du CONTENU, pas un identifiant Drive")
check(edf.empreinte == copie.empreinte,
      "deux fichiers au contenu identique ont la même empreinte -> un seul OCR")
check(os.path.exists(src.ouvrir(edf)), "ouvrir() rend un chemin local lisible")

avant = faux.appels
src.ouvrir(edf); src.ouvrir(copie)
check(faux.appels == avant, "ouvrir() ne retélécharge pas ce qui est déjà là")

# le manifeste filtre : une pièce déjà traitée ne repasse pas
from s2a_lmnp import Manifeste, pieces_neuves
man = Manifeste(os.path.join(tempfile.mkdtemp(), "m.json"))
check(len(pieces_neuves(src, man)) == 3, "au 1er passage, tout est neuf")
man.marquer(edf.empreinte, edf.nom)
restant = pieces_neuves(src, man)
check(len(restant) == 1 and all(not r.nom.endswith(".pdf") for r in restant),
      "la pièce traitée ET son doublon de contenu sont écartés")
check(src.nettoyer() >= 1, "les pièces temporaires sont effaçables en fin de traitement")

print("34) Le relevé fixe la date de règlement de la facture (trésorerie)")
# la pièce annonce le 28/12 ; la banque dit le 12/01 -> c'est la banque qui gagne
f33 = Facture("EDF ENERGIE", D(2025, 12, 28), 69.34)
f33.date_reglement = D(2025, 12, 28)          # ce que prétendait la pièce
o33 = Operation(D(2026, 1, 12), "EDF ENERGIE ELECTRICITE", 69.34, "D")
rapprocher([o33], [f33])
check(f33.op is o33 and f33.date_reglement == D(2026, 1, 12),
      "facture retrouvée en banque -> date du mouvement, pas celle de la pièce")
check(mois_de(f33) == ("2026-01", False), "et elle se range dans le mois du mouvement")

# facture jamais retrouvée : sa date de règlement n'est pas inventée
f33b = Facture("HORS BANQUE", D(2026, 5, 4), 42.0)
rapprocher([Operation(D(2026, 5, 4), "AUTRE CHOSE", 999.0, "D")], [f33b])
check(f33b.op is None and f33b.date_reglement is None,
      "facture non rapprochée -> aucune date de règlement inventée")

# un seul règlement pour deux factures : les deux sont datées du mouvement
fa = Facture("A", D(2026, 2, 1), 60.0); fb = Facture("B", D(2026, 2, 2), 40.0)
oc = Operation(D(2026, 3, 5), "PAIEMENT GROUPE", 100.0, "D")
associer_factures(oc, [fa, fb])
check(fa.date_reglement == D(2026, 3, 5) and fb.date_reglement == D(2026, 3, 5),
      "un règlement pour plusieurs factures -> toutes datées du mouvement")

# une facture réglée en trois fois : elle est soldée au DERNIER mouvement
f3x = Facture("EN TROIS FOIS", D(2026, 1, 10), 300.0)
o3x = [Operation(D(2026, 1, 15), "ACOMPTE 1", 100.0, "D"),
       Operation(D(2026, 3, 15), "SOLDE", 100.0, "D"),
       Operation(D(2026, 2, 15), "ACOMPTE 2", 100.0, "D")]
associer_reglements(f3x, o3x)
check(f3x.date_reglement == D(2026, 3, 15),
      "règlements multiples -> la facture est datée du dernier")
check(mois_de(f3x) == ("2026-03", False), "et rangée dans le mois du solde")

print("36) L'ingestion et le script de vérification, sur une vraie boucle OCR")
# Ce que la maison n'avait pas : le script que lance le débutant n'était couvert
# par aucun test. Il refaisait à la main la boucle de `ingerer` — et se trompait :
# `lire_facture` rend une LISTE de factures par fichier (un PDF peut en contenir
# plusieurs), pas une facture. La liste de listes cassait le classement, chez
# l'utilisateur, sur sa première pièce réelle.
import contextlib, io, shutil, tempfile
import s2a_lmnp as _S
from s2a_lmnp import ingerer
import verifier_branchement as _VB


class FauxOCR:
    """Respecte le contrat réel de ClientAnthropic.lire_facture : une LISTE."""

    def lire_facture(self, chemin, modele=None):
        nom = os.path.basename(chemin).lower()
        if "devis" in nom:
            return [{"categorie": "devis", "confiance_classement": 0.95}]
        # un seul PDF, deux factures dedans : le cas qui a cassé
        return [{"categorie": "facture_achat", "confiance_classement": 0.96,
                 "confiance": 0.95, "fournisseur": "EDF",
                 "date": "2026-03-01", "ttc": 57.79, "ht": 48.16, "tva": 9.63},
                {"categorie": "facture_achat", "confiance_classement": 0.96,
                 "confiance": 0.95, "fournisseur": "EDF",
                 "date": "2026-04-01", "ttc": 61.20, "ht": 51.00, "tva": 10.20}]


_bac = tempfile.mkdtemp(prefix="saisio-test-")
for _n in ("edf.pdf", "devis-toiture.pdf"):
    with open(os.path.join(_bac, _n), "wb") as _fh:
        _fh.write(_n.encode())

_src = DossierLocal(_bac)
_man = Manifeste(os.path.join(_bac, "manifeste.json"))
_fact, _rej = ingerer(_src, _man, FauxOCR())
check(len(_fact) == 2, "un PDF qui contient deux factures en produit deux")
check(all(f.fournisseur == "EDF" for f in _fact),
      "les factures sont bien construites, pas des listes imbriquées")
check(all(f.fichier == "edf.pdf" for f in _fact),
      "chaque facture sait de quel fichier elle vient")
check(all(f.empreinte for f in _fact), "et porte l'empreinte de ce fichier")
check(len(_rej) == 1 and _rej[0]["fichier"] == "devis-toiture.pdf",
      "le devis est écarté, avec son fichier d'origine")
check("devis" in _rej[0]["motif"], "et avec un motif en clair")

# deuxième passage : le manifeste a fait son travail, aucun OCR n'est repayé
_f2, _r2 = ingerer(_src, _man, FauxOCR())
check(_f2 == [] and _r2 == [], "au second passage, plus rien n'est relu")

# `limite` et `pieces` : l'essai de branchement ne lit que N pièces, et ne
# reliste pas la source (sur un Drive, lister télécharge : relister coûte).
_man3 = Manifeste(os.path.join(_bac, "m3.json"))
_f3, _r3 = ingerer(_src, _man3, FauxOCR(), limite=1)
_vus = {f.fichier for f in _f3} | {r["fichier"] for r in _r3}
check(_vus == {"devis-toiture.pdf"},
      "limite=1 n'ouvre qu'un seul fichier — un seul OCR payé")
_f3b, _r3b = ingerer(_src, _man3, FauxOCR(), limite=1)
check({f.fichier for f in _f3b} == {"edf.pdf"},
      "le passage suivant reprend là où le précédent s'était arrêté")


class _SrcCompteuse(DossierLocal):
    def __init__(self, d):
        DossierLocal.__init__(self, d)
        self.listages = 0

    def lister(self):
        self.listages += 1
        return DossierLocal.lister(self)


_sc = _SrcCompteuse(_bac)
_man4 = Manifeste(os.path.join(_bac, "m4.json"))
ingerer(_sc, _man4, FauxOCR(), pieces=pieces_neuves(_sc, _man4))
check(_sc.listages == 1, "pieces= évite de relister la source une seconde fois")

# --- le script que lance l'utilisateur, en entier ---------------------------
_vrai_client = _S.ClientAnthropic
_S.ClientAnthropic = FauxOCR
try:
    _sortie = io.StringIO()
    with contextlib.redirect_stdout(_sortie):
        _vert = _VB.etape_bout("", "", _bac, 3)
finally:
    _S.ClientAnthropic = _vrai_client
_txt = _sortie.getvalue()
check(_vert is True, "verifier_branchement --etape bout va au bout sur un dossier réel")
check("2 retenue(s), 1 écartée(s)" in _txt,
      "il annonce le bon classement (2 factures, 1 devis écarté)")
check("RIEN n'a été écrit" in _txt, "et il rappelle qu'il n'a rien écrit")
shutil.rmtree(_bac, ignore_errors=True)

print("37) Le dépôt dans le Drive de sortie")
from s2a_lmnp import (DepotDrive, deposer_plan, resoudre_chemin,
                      QuotaCompteService)


class FauxDepot:
    """Reproduit ce que Saisio demande à l'API v3 côté écriture, et rien de plus.

    Tient une vraie arborescence en mémoire : c'est le seul moyen de vérifier
    qu'on ne recrée pas dix fois le même mois et qu'on n'écrase jamais rien."""

    def __init__(self):
        self.noeuds = {"sortie": {"nom": "SORTIE", "parent": None,
                                  "dossier": True, "taille": 0}}
        self.creations, self.uploads, self.listages = 0, 0, 0
        self.editeur = True
        self.drive_partage = True
        self.quota = True

    def files(self):
        return self

    @staticmethod
    def _litteral(q):
        """Lit la chaîne échappée qui suit `name = '`, comme le fait Drive :
        un `\\'` est une apostrophe, pas une fin de chaîne. Un bouchon qui
        couperait au premier guillemet validerait une requête que Drive
        refuserait — le test ne prouverait plus rien."""
        i, out, ech = q.index("name = '") + 8, [], False
        while i < len(q):
            c = q[i]
            if ech:
                out.append(c); ech = False
            elif c == "\\":
                ech = True
            elif c == "'":
                break
            else:
                out.append(c)
            i += 1
        return "".join(out)

    def list(self, q="", **kw):
        self.listages += 1
        nom = self._litteral(q)
        parent = q.split("' in parents")[0].rsplit("'", 1)[-1]
        veut_dossier = "mimeType = 'application/vnd.google-apps.folder'" in q
        out = []
        for i, n in self.noeuds.items():
            if (n["nom"] == nom and n["parent"] == parent
                    and n["dossier"] == veut_dossier):
                out.append({"id": i, "name": nom, "size": str(n["taille"])})
        self._rep = {"files": out}
        return self

    def get(self, fileId=None, **kw):
        self._rep = {"id": fileId, "name": "SORTIE",
                     "capabilities": {"canAddChildren": self.editeur}}
        if self.drive_partage:
            self._rep["driveId"] = "0AShared"
        return self

    def create(self, body=None, media_body=None, **kw):
        dossier = body.get("mimeType") == "application/vnd.google-apps.folder"
        if dossier:
            self.creations += 1
        else:
            if not self.quota:
                # ce que Google renvoie vraiment : 403 storageQuotaExceeded.
                raise RuntimeError(
                    "<HttpError 403 …> Service Accounts do not have storage "
                    "quota. … 'reason': 'storageQuotaExceeded'")
            self.uploads += 1
        i = "n%d" % len(self.noeuds)
        self.noeuds[i] = {"nom": body["name"], "parent": body["parents"][0],
                          "dossier": dossier, "taille": 7}
        self._rep = {"id": i, "name": body["name"]}
        return self

    def execute(self):
        return self._rep


_fd = FauxDepot()
_dep = DepotDrive("sortie", service=_fd)
_id1 = _dep.assurer_chemin("DUPONT/Exercice 2026/2026-03/Traité")
check(_fd.creations == 4, "l'arborescence manquante est créée, segment par segment")
_id2 = _dep.assurer_chemin("DUPONT/Exercice 2026/2026-03/Traité")
check(_id2 == _id1 and _fd.creations == 4,
      "le même chemin redemandé ne recrée rien")
_avant = _fd.creations
_dep.assurer_chemin("DUPONT/Exercice 2026/2026-04/Traité")
check(_fd.creations == _avant + 2,
      "un mois voisin ne recrée que ce qui manque, pas la branche entière")

# l'apostrophe de « Documents générés par l'application » : une requête Drive
# mal échappée ne lève pas, elle renvoie zéro résultat — et on recrée un dossier
# en double à chaque passage, sans que rien ne le signale.
_dep2 = DepotDrive("sortie", service=_fd)
_a1 = _dep2.assurer_chemin("L'ATELIER")
_dep3 = DepotDrive("sortie", service=_fd)
check(_dep3.assurer_chemin("L'ATELIER") == _a1,
      "un nom de dossier contenant une apostrophe est retrouvé, pas dupliqué")

_bac2 = tempfile.mkdtemp(prefix="saisio-depot-")
_p1 = os.path.join(_bac2, "edf.pdf")
with open(_p1, "wb") as _fh:
    _fh.write(b"1234567")
_r = _dep.deposer(_p1, "edf.pdf", _id1)
check(_r["etat"] == "depose" and _fd.uploads == 1, "la pièce est déposée")
_r2 = _dep.deposer(_p1, "edf.pdf", _id1)
check(_r2["etat"] == "deja" and _fd.uploads == 1,
      "relancée, elle n'est ni redéposée ni écrasée")

# le plan complet, avec une pièce dont l'empreinte n'est dans aucune source
_src2 = DossierLocal(_bac2)
_refs = _src2.lister()
_plan = {"Exercice 2026/2026-03/Traité": [
             {"fichier": "edf.pdf", "empreinte": _refs[0].empreinte, "motif": ""}],
         "Exercice 2026/2026-03/En attente de traitement": [
             {"fichier": "perdu.pdf", "empreinte": "inconnue", "motif": "devis"}]}
_fdn = FauxDepot()
_depn = DepotDrive("sortie", service=_fdn)
_rap = deposer_plan(_depn, _plan, _src2, _refs, prefixe="DUPONT", ecrire=True)
check([d["chemin"] for d in _rap["deposes"]]
      == ["DUPONT/Exercice 2026/2026-03/Traité"],
      "le plan dépose chaque pièce dans son dossier, préfixé par le client")
check(len(_rap["manquants"]) == 1 and _rap["manquants"][0]["fichier"] == "perdu.pdf",
      "une pièce introuvable à la source est signalée, jamais devinée")
# relancer le même traitement ne duplique rien : c'est ce qui rend une commande
# de tous les jours rejouable sans crainte.
_rap2 = deposer_plan(_depn, _plan, _src2, _refs, prefixe="DUPONT", ecrire=True)
check(_rap2["deposes"] == [] and len(_rap2["deja"]) == 1 and _fdn.uploads == 1,
      "le même traitement relancé ne dépose rien une seconde fois")

_fd2 = FauxDepot()
_dep4 = DepotDrive("sortie", service=_fd2)
_rapb = deposer_plan(_dep4, _plan, _src2, _refs, prefixe="DUPONT", ecrire=False)
check(_fd2.creations == 0 and _fd2.uploads == 0,
      "sans --deposer, aucun dossier créé et aucun fichier envoyé")
check(len(_rapb["deposes"]) == 1 and _rapb["deposes"][0]["simule"],
      "et l'essai à blanc dit quand même ce qu'il aurait déposé")

try:
    DepotDrive(""); _v = False
except ValueError:
    _v = True
check(_v, "un dossier de sortie vide est refusé")

# Le partage en « Lecteur » doit se voir AVANT de payer le moindre OCR : sinon
# les pièces sont lues, marquées traitées, et jamais déposées.
check(DepotDrive("sortie", service=FauxDepot()).verifier()["ok"],
      "un dossier partagé en Éditeur est déclaré accessible en écriture")
_lect = FauxDepot(); _lect.editeur = False
_vl = DepotDrive("sortie", service=_lect).verifier()
check(not _vl["ok"] and "Éditeur" in _vl["conseil"],
      "un dossier partagé en Lecteur est refusé, en disant quoi corriger")
check(_lect.creations == 0 and _lect.uploads == 0,
      "et le constat se fait sans écrire un fichier d'essai")

# Le piège Google : un compte de service n'a pas de quota. Dans un « Mon Drive »
# il crée les dossiers (qui ne pèsent rien) et pas un seul fichier n'arrive.
# Le préalable doit le voir AVANT l'OCR ; sinon on paie la lecture pour rien.
_mydrive = FauxDepot(); _mydrive.drive_partage = False
_vm = DepotDrive("sortie", service=_mydrive).verifier()
check(not _vm["ok"] and _vm["ecriture"],
      "un Mon Drive est refusé alors même que l'écriture y semble autorisée")
check("DRIVE PARTAGÉ" in _vm["conseil"],
      "et le conseil nomme la seule issue qui ne demande pas de code")
_vp = DepotDrive("sortie", service=FauxDepot()).verifier()
check(_vp["ok"] and _vp["drive_partage"], "un Drive partagé, lui, passe")

# et si on y arrive quand même (contrôle contourné, droits changés en route),
# l'erreur de Google sort en français, pas en trace Python.
_sq = FauxDepot(); _sq.quota = False
_dsq = DepotDrive("sortie", service=_sq)
_dq = _dsq.assurer_chemin("Exercice 2026")
try:
    _dsq.deposer(_p1, "edf.pdf", _dq); _vq = False
except QuotaCompteService as _e:
    _vq = "Drive partagé" in str(_e) or "DRIVE PARTAGÉ" in str(_e)
check(_vq, "le 403 « pas de quota » devient un conseil, pas une trace Python")

# racine="" : on dépose DANS le dossier de sortie, le plan doit donc être
# relatif. Avec la racine, on recréait « Documents générés par l'application »
# à l'intérieur de « Documents générés par l'application ».
_fac = Facture("EDF", D(2026, 8, 3), 57.79)
_fac.date_reglement = D(2026, 8, 20)
check(chemin(_fac, traite=True, racine="") == "Exercice 2026/2026-08/Traité",
      "racine vide -> chemin relatif, sans le nom du dossier de sortie")
check(chemin(_fac, traite=True).startswith(RACINE + "/"),
      "et par défaut le chemin porte toujours la racine")
_planr = ranger([], [{"categorie": "hors_sujet", "fichier": "photo.jpg",
                      "empreinte": "e", "motif": "photo"}], racine="")
check(list(_planr) == [SANS_RAPPORT],
      "les pièces sans rapport aussi : pas de racine en double")

# la composition telle que la fait `traiter.py` : plan relatif + nom du client,
# déposé dans le dossier de sortie. C'est le chemin final vu par le cabinet.
_fac.fichier, _fac.empreinte = "9ubucda.pdf", _refs[0].empreinte
_fd3 = FauxDepot()
_rapc = deposer_plan(DepotDrive("sortie", service=_fd3),
                     ranger([_fac], racine="", exercice=Exercice.civil(2026)),
                     _src2, _refs, prefixe="LMNP POLO TEST", ecrire=True)
check(_rapc["dossiers"] == ["LMNP POLO TEST/Exercice 2026/2026-08/Traité"],
      "chemin final : client/exercice/mois/statut, sous le dossier de sortie")

# résolution CLIENT/année côté lecture : on ne crée rien, et on ne devine rien
_srcd = DriveGoogle("racine", service=FauxDrive())
check(resoudre_chemin(_srcd, "DUPONT/2026") == "d2",
      "le sous-dossier client/année est retrouvé dans le Drive d'entrée")
check(resoudre_chemin(_srcd, " dupont / 2026 ") == "d2",
      "la casse et les espaces de bord ne font pas échouer la recherche")
check(resoudre_chemin(_srcd, "DUPONT/2027") == "",
      "un client mal orthographié ne retombe PAS sur tout le dossier d'entrée")
shutil.rmtree(_bac2, ignore_errors=True)

print("\n%d contrôles OK — moteur cohérent." % ok)
