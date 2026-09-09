"""Les réglages de Saisio, dans un simple fichier texte.

Un débutant ne devrait pas avoir à se battre avec `export` sous Mac et `setx`
sous Windows — et surtout pas à recommencer à chaque fenêtre de terminal. On lit
`saisio.env` à la racine du projet, une ligne par réglage, et on ne touche à
rien s'il n'existe pas.

Deux pièges de Windows sont absorbés ici plutôt que signalés dans une note que
personne ne lit : le Bloc-notes enregistre en `saisio.env.txt` sans le dire, et
préfixe le fichier d'un BOM qui collerait au nom du premier réglage.
"""
from __future__ import annotations

import os

NOMS = ("saisio.env", "saisio.env.txt")


def charger(racine: str = None):
    """Charge `saisio.env` dans l'environnement. Renvoie le fichier lu, ou None.

    Ne remplace jamais une variable déjà posée dans l'environnement : une valeur
    fournie par le serveur doit gagner sur le fichier local."""
    if racine is None:
        racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for nom in NOMS:
        fichier = os.path.join(racine, nom)
        if os.path.exists(fichier):
            break
    else:
        return None
    lus = 0
    with open(fichier, encoding="utf-8-sig") as f:
        for ligne in f:
            ligne = ligne.strip()
            if not ligne or ligne.startswith("#") or "=" not in ligne:
                continue
            cle, _, val = ligne.partition("=")
            val = val.strip().strip('"').strip("'")
            if val:
                os.environ.setdefault(cle.strip(), val)
                lus += 1
    return fichier if lus else None
