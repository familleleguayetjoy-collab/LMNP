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


if __name__ == "__main__":
    main()
