"""Dépôt dans un dossier de l'ordinateur — même interface que `DepotDrive`.

Le Drive impose un compte de service, un partage, une portée OAuth et, sur un
compte gratuit, un contournement complet parce qu'un compte de service ne
possède aucun octet de stockage. Un dossier local n'impose rien : il est là, on
écrit dedans, et le collaborateur voit le résultat dans son explorateur.

Les mêmes règles qu'au Drive, parce qu'elles ne tiennent pas à la destination :

1. **On n'écrase et on ne supprime jamais.** Un nom déjà présent est laissé tel
   quel et signalé. Ce sont les pièces d'un client ; une pièce écrasée pendant
   un traitement est une pièce perdue.
2. **On ne redépose pas ce qui est déjà là** — même nom, même taille, on passe.
   Relancer un traitement ne duplique donc rien.
3. **On n'écrit que sous la racine donnée.** Les noms venus des pièces sont
   nettoyés : un nom de fichier qui remonterait d'un cran (`../`) écrirait
   ailleurs que là où le collaborateur regarde.
"""
from __future__ import annotations

import os
import shutil

# Caractères que Windows refuse dans un nom de fichier. Les remplacer plutôt que
# de laisser l'écriture échouer au milieu d'un traitement de 200 pièces.
INTERDITS = '<>:"/\\|?*'


def nom_sur(nom: str) -> str:
    """Nom de fichier sûr : pas de séparateur, pas de remontée de dossier."""
    nom = os.path.basename(str(nom or "piece").strip())
    for c in INTERDITS:
        nom = nom.replace(c, "-")
    nom = nom.strip(" .")
    return nom or "piece"


class DepotLocal:
    """Le dossier de sortie sur le disque, et rien d'autre."""

    def __init__(self, racine: str):
        if not racine:
            raise ValueError("DepotLocal : dossier de sortie manquant")
        self.racine = os.path.abspath(os.path.expanduser(racine))
        self.mode = "local"

    def verifier(self) -> dict:
        """Peut-on écrire ici ? On crée le dossier s'il manque — c'est le cas
        normal au premier traitement, et demander à l'utilisateur de le créer
        d'abord ne lui apprendrait rien."""
        try:
            os.makedirs(self.racine, exist_ok=True)
            essai = os.path.join(self.racine, ".saisio-essai")
            with open(essai, "w") as f:
                f.write("")
            os.remove(essai)
        except OSError as e:
            return {"ok": False, "dossier": self.racine, "ecriture": False,
                    "mode": "local", "drive_partage": False,
                    "conseil": "dossier inaccessible en écriture (%s). Choisissez "
                               "un dossier de vos Documents plutôt qu'un dossier "
                               "système." % e}
        return {"ok": True, "dossier": self.racine, "ecriture": True,
                "mode": "local", "drive_partage": False, "conseil": ""}

    def assurer_chemin(self, chemin: str) -> str:
        cible = self.racine
        for seg in (chemin or "").split("/"):
            seg = nom_sur(seg) if seg.strip() else ""
            if seg:
                cible = os.path.join(cible, seg)
        os.makedirs(cible, exist_ok=True)
        return cible

    def deja_la(self, nom: str, dossier: str, taille=None) -> bool:
        c = os.path.join(dossier, nom_sur(nom))
        if not os.path.exists(c):
            return False
        return taille is None or os.path.getsize(c) == int(taille)

    def deposer(self, chemin_local: str, nom: str, dossier: str) -> dict:
        nom = nom_sur(nom)
        taille = os.path.getsize(chemin_local) if os.path.exists(chemin_local) else None
        if self.deja_la(nom, dossier, taille):
            return {"etat": "deja", "nom": nom}
        cible = os.path.join(dossier, nom)
        if os.path.exists(cible):
            # même nom, taille différente : deux pièces distinctes. On garde les
            # deux — choisir laquelle écraser n'est pas au programme de le faire.
            base, ext = os.path.splitext(nom)
            n = 2
            while os.path.exists(os.path.join(dossier, "%s (%d)%s" % (base, n, ext))):
                n += 1
            nom = "%s (%d)%s" % (base, n, ext)
            cible = os.path.join(dossier, nom)
        shutil.copy2(chemin_local, cible)
        return {"etat": "depose", "nom": nom, "id": cible}
