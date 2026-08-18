"""Démonstration bout-en-bout — dossier AVEC banque (relevé au format Quadra).

Scénario : le relevé bancaire arrive au format Quadra ASCII (comme le fichier
DUMDUM du cabinet). On sait :
  - le RELIRE (enregistrements C = plan comptable, M = mouvements) ;
  - le RÉ-EXPORTER à l'identique au centime près (contrepartie 512 en ligne) ;
  - contrôler que chaque ligne porte sa contrepartie.

Le journal ci-dessous est synthétique mais au FORMAT RÉEL vérifié (251 car.).

Lancer :  python3 tool/demo/demo_avec_banque.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from s2a_lmnp.quadra import (lire_comptes, lire_mouvements, format_mouvement,
                             to_quadratus, verifier_equilibre)

# --- Journal Quadra synthétique, format réel (C = comptes, M = mouvements) ---
def _c(num, lib):
    return ("C" + num.ljust(8) + lib.ljust(29)).ljust(200)

JOURNAL = "\r\n".join([
    _c("70600000", "Prestations de services"),
    _c("60611000", "Fournitures Electricite"),
    _c("62600000", "Free"),
    _c("51210010", "Credit Agricole"),
    # mouvements (contrepartie 512 en ligne) :
    format_mouvement("70600000", "BQ", __import__("datetime").date(2026, 1, 2),
                     "VIREMENT AIRBNB", "C", 1597.53, "51200000", 1, "_IMP"),
    format_mouvement("60611000", "BQ", __import__("datetime").date(2026, 1, 5),
                     "TOTALENERGIES", "D", 197.92, "51200000", 2, "_IMP"),
    format_mouvement("62600000", "BQ", __import__("datetime").date(2026, 1, 7),
                     "FREE TELECOM", "D", 44.98, "51200000", 3, "_IMP"),
]) + "\r\n"


def main():
    comptes = lire_comptes(JOURNAL)
    print("Plan comptable lu :", len(comptes), "comptes")
    for num, lib in comptes.items():
        print("   ", num, lib)

    ops = lire_mouvements(JOURNAL)
    print("\nMouvements lus :", len(ops))
    for op in ops:
        print("   %s  %-16s %8.2f € %s -> compte %s"
              % (op.date, op.libelle, op.montant, op.sens, op.compte))

    # Ré-export : une ligne par opération, contrepartie banque en ligne
    txt = to_quadratus(ops, avec_banque=True, compte_banque="51210010")
    lignes = [l for l in txt.split("\r\n") if l]
    deb, cred, ok = verifier_equilibre(txt)
    print("\nRé-export Quadra : %d lignes de %d car." % (len(lignes), len(lignes[0])))
    print("   somme débits principaux : %.2f € | crédits : %.2f €" % (deb / 100, cred / 100))
    print("   chaque ligne porte sa contrepartie en ligne :", "OUI ✓" if ok else "NON ✗")

    # --- Workflow complet : rapprochement facture <-> banque, Excel + OD 108 ---
    import datetime as _dt
    from s2a_lmnp import (Dictionnaire, Facture, Operation, traiter_dossier,
                          journal_banque_xlsx)
    dico = Dictionnaire()
    for num, lib in comptes.items():
        dico.ajouter(lib, num)
    # 3 factures : 2 rapprochées avec la banque, 1 payée EN PERSO (absente du relevé)
    factures = [
        Facture("TOTALENERGIES", _dt.date(2026, 1, 5), 197.92, 32.99),
        Facture("FREE",          _dt.date(2026, 1, 7), 44.98,   7.50),
        Facture("PLOMBERIE DURAND", _dt.date(2026, 1, 9), 240.00, 40.0),  # payée perso
    ]
    ops_bq = [
        Operation(_dt.date(2026, 1, 5), "TOTALENERGIES", 197.92, "D"),
        Operation(_dt.date(2026, 1, 7), "FREE TELECOM", 44.98, "D"),
    ]
    res = traiter_dossier(factures, ops_bq, dico, compte_banque="51210010", journal="BQ")

    print("\n--- Dossier AVEC banque : sortie en 2 fichiers ---")
    print("  Opérations de banque :", len(res["operations"]),
          "  |  Écritures d'OD (payées perso) :", len(res["operations_od"]))
    # 1) le journal de BANQUE -> Excel modifiable, trié par date
    xlsx = journal_banque_xlsx(res["operations"], journaux={"51210010": "BQ"},
                               compte_banque="51210010")
    chemin = os.path.join(os.path.dirname(__file__), "journal_banque.xlsx")
    with open(chemin, "wb") as f:
        f.write(xlsx)
    print("  1) journal de banque -> Excel :", os.path.basename(chemin),
          "(%d octets, modifiable dans le logiciel comptable)" % len(xlsx))
    # 2) les factures payées perso -> OD ASCII, contrepartie 108
    od = [l for l in res["od_ascii"].split("\r\n") if l]
    print("  2) factures payées en perso -> OD ASCII : %d écriture(s), contrepartie 108"
          % len(od), "✓" if "10800000" in res["od_ascii"] else "✗")


if __name__ == "__main__":
    main()
