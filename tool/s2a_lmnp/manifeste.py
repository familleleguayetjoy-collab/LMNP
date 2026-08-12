"""Manifeste de suivi — idempotence du traitement.

Objectif : ne JAMAIS re-traiter une pièce déjà traitée (ne pas re-payer l'OCR,
ne pas repasser une écriture). Clé = **empreinte sha256 du contenu** : un fichier
renommé reste reconnu comme déjà traité. Persisté en JSON, propriété du cabinet.

RGPD : le manifeste ne stocke PAS le contenu des pièces — seulement leur
empreinte, le nom de fichier et la date de traitement (traçabilité NPMQ : quoi,
quand). C'est un fichier de suivi local, jamais commité avec des données client.
"""
from __future__ import annotations
import json
import os
from datetime import datetime


class Manifeste:
    def __init__(self, chemin: str | None = None):
        self.chemin = chemin
        self.entrees: dict[str, dict] = {}   # empreinte -> métadonnées
        if chemin and os.path.exists(chemin):
            self.charger()

    def charger(self):
        with open(self.chemin, "r", encoding="utf-8") as f:
            self.entrees = json.load(f)

    def sauver(self):
        if not self.chemin:
            raise ValueError("Manifeste sans chemin : impossible de sauvegarder")
        tmp = self.chemin + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.entrees, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.chemin)          # écriture atomique

    def est_traite(self, empreinte: str) -> bool:
        return empreinte in self.entrees

    def marquer(self, empreinte: str, nom: str = "", **meta):
        """Enregistre une pièce comme traitée. `meta` peut porter des repères de
        traçabilité (n° de pièce Quadra, journal...) mais jamais le contenu."""
        self.entrees[empreinte] = {
            "nom": nom,
            "traite_le": datetime.now().isoformat(timespec="seconds"),
            **meta,
        }

    def nouveaux(self, pieces):
        """Filtre une liste de pièces (objets portant `.empreinte`) : ne renvoie
        que celles jamais traitées. C'est le cœur de l'idempotence."""
        return [p for p in pieces if not self.est_traite(getattr(p, "empreinte", p))]

    def __len__(self):
        return len(self.entrees)
