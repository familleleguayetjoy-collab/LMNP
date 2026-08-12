"""Démo sur les 3 VRAIES factures du dossier test (EDF / Brico Dépôt / Bouygues).

Valeurs = ce que l'OCR Haiku 4.5 a réellement extrait des 3 PDF (au centime) :
  EDF        69,34 TTC (HT 57,79 / TVA 11,55)
  BRICO      71,07 TTC (HT 59,23 / TVA 11,84)  -> ticket thermique, espèces 81,07 ignorées
  BOUYGUES   44,99 TTC (HT 37,49 / TVA  7,50)  -> bloc "EXEMPLE" ignoré
On ne stocke NI les PDF NI l'adresse du bien (RGPD) — juste enseigne + montants.

Montre le parcours complet dans les deux configurations du cabinet :
  A) dossier AVEC banque  -> rapprochement facture/banque + export Quadra (journal BQ)
  B) dossier SANS banque  -> écriture d'OD, contrepartie 108 (compte de l'exploitant)

Lancer :  python3 tool/demo/demo_3_factures.py
"""
import sys, os, datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from s2a_lmnp import (construire, parse_fec, Operation, coder, rapprocher,
                      to_quadratus, facture_depuis_ocr, operations_od_factures,
                      SEUIL_IMMO_HT)

D = datetime.date

# FEC N-1 : EDF et Bouygues déjà connus (codés l'an dernier) -> auto-codage.
FEC = (
    "JournalCode\tCompteNum\tCompteLib\tEcritureDate\tEcritureLib\tDebit\tCredit\n"
    "BQ\t606100\tEnergie\t20250210\tEDF energie electricite\t57,79\t0,00\n"
    "BQ\t626000\tTelecom\t20250215\tBouygues Telecom fibre\t37,49\t0,00\n"
)
dico = construire(parse_fec(FEC))

# Les 3 factures telles que l'OCR les renvoie (contrat A).
OCR = [
    {"fournisseur": "EDF", "date": "05/01/2026", "ttc": 69.34, "tva": 11.55, "ht": 57.79,
     "numero": "EDF-2026-01", "confiance": 0.95},
    {"fournisseur": "BRICO DEPOT", "date": "09/01/2026", "ttc": 71.07, "tva": 11.84, "ht": 59.23,
     "numero": "BRICO-2026-01", "confiance": 0.95},
    {"fournisseur": "BOUYGUES TELECOM", "date": "16/01/2026", "ttc": 44.99, "tva": 7.50, "ht": 37.49,
     "numero": "BYG-2026-01", "confiance": 0.95},
]

print("=" * 64)
print("LES 3 FACTURES (extraction OCR Haiku 4.5)")
print("=" * 64)
factures = [facture_depuis_ocr(b) for b in OCR]
for f in factures:
    print("  %-18s %s  TTC %7.2f  (HT %6.2f / TVA %5.2f)  n° %s"
          % (f.fournisseur, f.date, f.ttc, f.ht, f.tva, f.numero))
print("  Rappel : le TTC est comptabilisé en charge (LMNP non assujetti TVA).")

# --- Scénario A : dossier AVEC banque -------------------------------------
print("\n" + "=" * 64)
print("A) DOSSIER AVEC BANQUE — rapprochement + Quadra (journal BQ)")
print("=" * 64)
ops = [
    Operation(D(2026, 1, 20), "EDF ENERGIE ELECTRICITE", 69.34, "D"),
    Operation(D(2026, 1, 12), "BRICO DEPOT NICE",        71.07, "D"),
    Operation(D(2026, 1, 30), "BOUYGUES TELECOM FIBRE",  44.99, "D"),
]
for o in ops:
    coder(o, dico)
rapprocher(ops, [facture_depuis_ocr(b) for b in OCR])
for o in ops:
    etat = "À TRANCHER (immo ?)" if o.a_revoir else "codé"
    rappro = "rapproché ✓" if o.facture else "sans facture"
    print("  %-24s -> %-6s %-18s %s" % (o.libelle[:24], o.compte, etat, rappro))
print("  Note seuil : Brico HT 59,23 € > %.0f € HT -> reste à trancher (immo ou charge)."
      % SEUIL_IMMO_HT)
ascii_bq = to_quadratus(ops, avec_banque=True, compte_banque="51210010",
                        journal="BQ", source="_3FAC")
print("  --- Quadratus (aperçu) ---")
for line in ascii_bq.split("\r\n"):
    if line:
        print("    %s | %s | %-18s | %s | %s c | ctp %s"
              % (line[1:9], line[14:20], line[21:39], line[41], line[43:55], line[55:63]))

# --- Scénario B : dossier SANS banque -> OD contrepartie 108 --------------
print("\n" + "=" * 64)
print("B) DOSSIER SANS BANQUE — écriture d'OD, contrepartie 108 (exploitant)")
print("=" * 64)
od = operations_od_factures([facture_depuis_ocr(b) for b in OCR], dico)
ascii_od = to_quadratus(od, avec_banque=False, journal="OD", source="_3FAC")
for line in ascii_od.split("\r\n"):
    if line:
        print("    %s | %s | %-18s | %s | %s c | ctp %s"
              % (line[1:9], line[14:20], line[21:39], line[41], line[43:55], line[55:63]))
print("    (montant = celui de la facture — seul cas où la banque manque)")

print("\nDémo terminée — 3 vraies factures, du PDF à l'écriture Quadra.")
