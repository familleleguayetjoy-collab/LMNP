"""Démonstration bout-en-bout — dossier SANS banque.

Scénario réel du cabinet : le client n'a pas de tenue de banque. On dispose
du FEC N-1 (pour construire le dictionnaire) et des factures du Drive (lues
par OCR). Chaque dépense est passée avec pour contrepartie le compte 108
(compte de l'exploitant), puis exportée au format Quadra ASCII (journal OD).

Données : FEC N-1 synthétique + 3 factures saisies en dur (les VRAIES valeurs
lues sur les PDF EDF / Brico Dépôt / Bouygues du dossier test). Aucune donnée
client réelle n'est stockée ici (RGPD).

Lancer :  python3 tool/demo/demo_sans_banque.py
"""
import sys, os, datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from s2a_lmnp import parse_fec, construire, Operation, Facture, coder, to_quadratus

D = datetime.date

# --- FEC N-1 synthétique (mêmes idées que le vrai : libellés préfixés du bien) ---
FEC = (
    "JournalCode\tCompteNum\tCompteLib\tEcritureDate\tEcritureLib\tDebit\tCredit\n"
    "AN\t213150\tConstructions\t20250101\tGros oeuvre - A Nouveaux\t34833,34\t0,00\n"
    "AN\t281315\tAmort. constructions\t20250101\tGros oeuvre - A Nouveaux\t0,00\t3200,00\n"
    "BQ\t606100\tEnergie\t20250210\tRuelle Boucherie - Energie EDF fev\t57,79\t0,00\n"
    "BQ\t606100\tEnergie\t20250312\tRuelle Boucherie - Energie EDF mar\t61,20\t0,00\n"
    "BQ\t626000\tTelecom\t20250215\tRuelle Boucherie - Bouygues Telecom fibre\t37,49\t0,00\n"
    "BQ\t606320\tPetit equipement\t20250308\tRuelle Boucherie - Autres equipements\t42,10\t0,00\n"
    "BQ\t615200\tEntretien\t20250620\tRuelle Boucherie - Entretien et reparations\t120,00\t0,00\n"
)

# --- Les 3 factures du Drive : VALEURS RÉELLES lues sur les PDF du dossier test.
#     (En production, cette liste sera produite par ocr.lire_facture — vision.) ---
FACTURES = [
    Facture("EDF",              D(2026, 1, 5),  69.34, 11.55, "EDF_Facture_2026_01_05.pdf"),
    Facture("BRICO DEPOT",      D(2026, 1, 9),  71.07, 11.84, "BRICODEPOT_2026_01_09.pdf"),
    Facture("BOUYGUES TELECOM", D(2026, 1, 16), 44.99,  7.50, "Bouyguestelecom_Facture_20260116.pdf"),
]


def main():
    dico = construire(parse_fec(FEC))
    print("Dictionnaire N-1 :", len(dico.par_cle), "entrées\n")

    ops = []
    a_trancher = []
    for f in FACTURES:
        # une facture sans banque = une dépense à passer (contrepartie 108)
        op = Operation(date=f.date, libelle=f.fournisseur, montant=f.ttc, sens="D")
        op.facture = f
        coder(op, dico)
        ops.append(op)
        flag = "  ⚠ À TRANCHER" if op.a_revoir else ""
        print("  %-18s %7.2f €  ->  compte %-7s  (%s)%s"
              % (f.fournisseur, f.ttc, op.compte, op.motif, flag))
        if op.a_revoir:
            a_trancher.append(op)

    print("\n%d écriture(s) automatique(s), %d à trancher (immo / inconnu / multi)."
          % (len(ops) - len(a_trancher), len(a_trancher)))

    txt = to_quadratus(ops, avec_banque=False)      # journal OD, contrepartie 108
    lignes = [l for l in txt.split("\r\n") if l]
    print("\nExport Quadra ASCII (journal OD, contrepartie 108) — %d lignes de %d car. :"
          % (len(lignes), len(lignes[0]) if lignes else 0))
    for l in lignes:
        # aperçu lisible : compte | date | sens | montant | contrepartie
        print("   ", l[1:9], l[14:20], l[41], l[43:55], "ctp", l[55:63].strip() or "(rien)")


if __name__ == "__main__":
    main()
