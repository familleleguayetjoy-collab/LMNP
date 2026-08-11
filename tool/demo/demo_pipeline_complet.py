"""Démonstration BOUT-EN-BOUT du pipeline complet — OCR → moteur → Quadra.

Reproduit tout le parcours d'un dossier LMNP avec banque, en montrant les 5
étapes de la maquette :
  Importer -> À trancher -> À réclamer -> (résolution IA) -> Le fichier Quadra

Tout est SYNTHÉTIQUE (aucune donnée client, RGPD) et la couche IA est simulée
par un client factice en mémoire : la démo tourne sans clé API et sans réseau.
En production, `FauxIA` est remplacé par `ClientAnthropic` (Haiku 4.5) — rien
d'autre ne change dans le code.

Lancer :  python3 tool/demo/demo_pipeline_complet.py
"""
import sys, os, datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from s2a_lmnp import (construire, parse_fec, Operation, coder, rapprocher,
                      manquants, to_quadratus, facture_depuis_ocr,
                      residu, resoudre_residu)

D = datetime.date

# ---------------------------------------------------------------------------
# IA SIMULÉE — remplace ClientAnthropic pour que la démo tourne sans clé.
# Respecte le contrat : choisit un compte PARMI les options, ne touche à rien
# d'autre. En prod : `from s2a_lmnp import ClientAnthropic; client = ClientAnthropic()`
# ---------------------------------------------------------------------------
class FauxIA:
    REGLES = {"BRICO": "615", "CONFORAMA": "2184"}   # proposition par mot-clé
    def resoudre(self, questions, *, modele=None):
        rep = []
        for q in questions:
            for cle, compte in self.REGLES.items():
                if cle in (q["libelle"] or ""):
                    rep.append({"id": q["id"], "compte": compte, "confiance": 0.82,
                                "raison": "meublé — nature durable, à amortir"
                                          if compte == "2184" else
                                          "consommable d'entretien, charge directe"})
        return rep


# ---------------------------------------------------------------------------
# 0) FEC N-1 synthétique -> dictionnaire client
# ---------------------------------------------------------------------------
FEC = (
    "JournalCode\tCompteNum\tCompteLib\tEcritureDate\tEcritureLib\tDebit\tCredit\n"
    "AN\t213150\tConstructions\t20250101\tGros oeuvre - A Nouveaux\t34833,34\t0,00\n"
    "AN\t281315\tAmort. constructions\t20250101\tGros oeuvre - A Nouveaux\t0,00\t3200,00\n"
    "BQ\t606100\tEnergie\t20250210\tEDF energie electricite\t57,79\t0,00\n"
    "BQ\t626000\tTelecom\t20250215\tBouygues Telecom fibre\t37,49\t0,00\n"
    "BQ\t615200\tEntretien\t20250620\tEntretien et reparations\t120,00\t0,00\n"
)
dico = construire(parse_fec(FEC))

# ---------------------------------------------------------------------------
# 1) IMPORTER — les factures viennent de l'OCR (ici : dicts synthétiques au
#    format exact du contrat A, comme les renverrait ClientAnthropic.lire_facture)
# ---------------------------------------------------------------------------
OCR = [
    {"fournisseur": "EDF", "date": "05/01/2026", "ttc": 69.34, "tva": 11.55,
     "ht": 57.79, "numero": "DEMO-EDF", "adresse_bien": "Studio Bonaparte", "confiance": 0.95},
    {"fournisseur": "BRICO DEPOT", "date": "09/01/2026", "ttc": 71.07, "tva": 11.84,
     "ht": 59.23, "numero": "DEMO-BRICO", "adresse_bien": "Studio Bonaparte", "confiance": 0.95},
    {"fournisseur": "BOUYGUES TELECOM", "date": "16/01/2026", "ttc": 44.99, "tva": 7.50,
     "ht": 37.49, "numero": "DEMO-BYG", "adresse_bien": "Studio Bonaparte", "confiance": 0.95},
]
factures = [facture_depuis_ocr(b) for b in OCR]

# ... et le relevé bancaire (format Quadra en prod ; ici saisi en dur) :
ops = [
    Operation(D(2026, 1, 5),  "VIREMENT LOYER JANVIER",   800.00, "C"),
    Operation(D(2026, 1, 20), "EDF ENERGIE ELECTRICITE",   69.34, "D"),
    Operation(D(2026, 1, 30), "BOUYGUES TELECOM FIBRE",    44.99, "D"),
    Operation(D(2026, 1, 9),  "BRICO DEPOT NICE",          71.07, "D"),
    Operation(D(2026, 1, 12), "CONFORAMA CANAPE ANGLE",   899.00, "D"),
    Operation(D(2026, 1, 31), "FRAIS TENUE DE COMPTE",     12.00, "D"),
    Operation(D(2026, 1, 18), "STUDIO PIXEL SAS",          60.00, "D"),
]

print("=" * 66)
print("1) IMPORTER  —  %d factures (OCR) + %d lignes bancaires" % (len(factures), len(ops)))
print("=" * 66)
for o in ops:
    coder(o, dico)
rapprocher(ops, factures)

# ---------------------------------------------------------------------------
# 2) À TRANCHER — le résidu ambigu (ce que les règles n'ont pas su décider)
# ---------------------------------------------------------------------------
print("\n" + "=" * 66)
print("2) À TRANCHER  —  résidu envoyé à l'IA (en UN seul appel) :")
print("=" * 66)
for o in residu(ops):
    print("  • %-26s montant %8.2f €   options %s"
          % (o.libelle, o.montant, o.options))

n = resoudre_residu(ops, FauxIA())     # en prod : resoudre_residu(ops, ClientAnthropic())
print("  -> %d proposition(s) IA (à VALIDER par l'humain, jamais auto) :" % n)
for o in residu(ops):
    print("     %-26s propose %-6s | %s" % (o.libelle, o.options[0], o.a_confirmer))

# --- [revue humaine] le comptable valide (ou corrige) les propositions ------
for o in ops:
    if o.a_revoir and len(o.options) >= 2:     # une proposition IA existe
        o.compte = o.options[0]                # le comptable accepte la tête de liste
        o.a_revoir = False

# ---------------------------------------------------------------------------
# 3) À RÉCLAMER — dépenses justifiables sans facture (mail de relance)
# ---------------------------------------------------------------------------
print("\n" + "=" * 66)
print("3) À RÉCLAMER  —  dépenses > 150 € sans justificatif :")
print("=" * 66)
mq = manquants(ops)
if not mq:
    print("  (aucune)")
for o in mq:
    print("  • %-26s %8.2f €  -> demander la facture au client" % (o.libelle, o.montant))

# ---------------------------------------------------------------------------
# 4) SYNTHÈSE du codage (auto / proposé-IA-validé / à qualifier)
# ---------------------------------------------------------------------------
print("\n" + "=" * 66)
print("4) CODAGE  —  synthèse par opération :")
print("=" * 66)
a_reclamer = {id(o) for o in mq}
print("  %-26s %-6s %-8s %-9s %s" % ("libellé", "compte", "sens", "origine", "justif."))
for o in ops:
    if o.facture:
        just = "facture OK"
    elif o.sens == "C":
        just = "—"
    elif id(o) in a_reclamer:
        just = "à réclamer"
    else:
        just = "sous seuil"
    etat = "471 À QUALIFIER" if o.compte == "471" else o.origine
    print("  %-26s %-6s %-8s %-9s %s"
          % (o.libelle[:26], o.compte, o.sens, etat, just))

# ---------------------------------------------------------------------------
# 5) LE FICHIER — export Quadra ASCII (251 car., journal BQ, ctp 512)
# ---------------------------------------------------------------------------
print("\n" + "=" * 66)
print("5) LE FICHIER  —  export Quadratus (journal BQ, contrepartie 51210010) :")
print("=" * 66)
ascii_out = to_quadratus(ops, avec_banque=True, compte_banque="51210010",
                         journal="BQ", source="_DEMO")
for line in ascii_out.split("\r\n"):
    if line:
        # aperçu : compte(2-9) date(15-20) libellé(22-41) sens(42) montant(44-55) ctp(56-63)
        print("  %s | date %s | %-20s | %s | %s c | ctp %s"
              % (line[1:9], line[14:20], line[21:41], line[41], line[43:55], line[55:63]))
print("\n  (%d octets, %d lignes M — prêt à importer dans Quadra)"
      % (len(ascii_out), ascii_out.count("\r\n")))
print("\nDémo terminée. En prod : FauxIA -> ClientAnthropic, factures en dur -> OCR Drive.")
