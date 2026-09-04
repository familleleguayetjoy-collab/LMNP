"""Démo : revue analytique + relance + tableau de bord cabinet (idées 3, 6, 10).

Données synthétiques, aucune clé, aucun réseau.
Lancer :  python3 tool/demo/demo_pilotage.py
"""
import sys, os, datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from s2a_lmnp import (parse_fec, construire, Operation, Facture, coder,
                      revue_analytique, reference, preparer_relances, traiter_lot)

D = datetime.date

# FEC N-1 : EDF récurrent (8 mois) + une assurance PNO
FEC_N1 = ("JournalCode|CompteNum|CompteLib|EcritureDate|EcritureLib|Debit|Credit\n"
          + "".join("BQ|606100|Energie|202503%02d|EDF energie|58,00|0,00\n" % (i + 1) for i in range(8))
          + "BQ|616000|Assurance|20250310|Assurance PNO|180,00|0,00\n")
ln1 = parse_fec(FEC_N1)

# Exercice en cours : EDF a disparu, l'assurance a doublé, un gros achat sans facture
ops = [
    Operation(D(2026, 3, 10), "ASSURANCE PNO", 380.00, "D"),
    Operation(D(2026, 5, 2), "GROS ACHAT FOURNISSEUR X", 900.00, "D"),
    Operation(D(2026, 1, 5), "VIREMENT LOYER JANVIER", 800.00, "C"),
]
for o in ops:
    coder(o, construire(ln1))

print("=" * 62)
print("REVUE ANALYTIQUE (N vs N-1) — ce que le collaborateur devait repérer")
print("=" * 62)
for a in revue_analytique(ops, ln1):
    print("  [%-9s] %s" % (a["gravite"].upper(), a["message"]))

print("\n" + "=" * 62)
print("RELANCE CLIENT — verrou de certitude")
print("=" * 62)
rel = preparer_relances(ops, reference(ln1), seuil=150.0, client="M. Dupont")
print("  Sûres (relance auto)   :", [o.libelle for o in rel["certain"]])
print("  À vérifier (pas d'envoi):", [o.libelle for o in rel["a_verifier"]])
print("\n  --- Brouillon de mail ---")
for l in rel["brouillon"].splitlines():
    print("   " + l)

print("\n" + "=" * 62)
print("TABLEAU DE BORD CABINET — traitement en lot")
print("=" * 62)
dossiers = [
    {"nom": "DUPONT", "factures": [Facture("EDF", D(2026, 1, 5), 58.0, 9.6)],
     "ops_banque": [Operation(D(2026, 1, 6), "EDF ENERGIE", 58.0, "D")],
     "dico": construire(ln1), "journal": "BQ"},
    {"nom": "MARTIN", "factures": [],
     "ops_banque": [Operation(D(2026, 1, 8), "MOBILIER INCONNU", 900.0, "D")],
     "dico": construire([]), "journal": "BQ"},
    {"nom": "DURAND", "factures": [Facture("EDF", D(2026, 1, 5), 58.0, 9.6)],
     "ops_banque": [Operation(D(2026, 1, 6), "EDF ENERGIE", 58.0, "D"),
                    Operation(D(2026, 1, 7), "VIREMENT LOYER", 700.0, "C")],
     "dico": construire(ln1), "journal": "BQ"},
]
lot = traiter_lot(dossiers)
print("  %-8s %4s %4s %9s %9s %6s  %-20s %s"
      % ("dossier", "ops", "fac", "à trancher", "à réclam.", "auto%", "statut", "coût IA"))
for r in lot["tableau_de_bord"]:
    print("  %-8s %4d %4d %9d %9d %5d%%  %-20s ~%.3f €"
          % (r["dossier"], r["operations"], r["factures"], r["a_trancher"],
             r["a_reclamer"], r["taux_auto_pct"], r["statut"], r["cout_ia_eur"]))
t = lot["totaux"]
print("  " + "-" * 74)
print("  %d dossiers, %d prêts, %d opérations — coût IA total estimé ~%.2f €"
      % (t["dossiers"], t["prets"], t["operations"], t["cout_ia_eur"]))
