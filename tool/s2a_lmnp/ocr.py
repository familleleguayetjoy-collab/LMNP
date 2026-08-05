"""Lecture des factures (OCR + extraction) via l'API Claude — INTERFACE.

À CÂBLER quand on aura : (1) l'accès API (clé Anthropic / DPA signé),
(2) quelques factures réelles anonymisées pour calibrer.

Règles de sûreté NON négociables côté implémentation :
  - Le montant extrait par l'IA ne sert QU'À rapprocher/contrôler, JAMAIS à
    poster une écriture. Le montant posté vient toujours du relevé bancaire.
  - Toujours renvoyer une confiance ; en dessous d'un seuil -> pièce marquée
    "à revoir" (l'IA ne devine pas en silence).
  - Un PDF peut contenir plusieurs factures / pages -> renvoyer une liste.
  - Cas à gérer : photo floue/pivotée, ticket thermique pâle, facture
    étrangère, doublon, document qui n'est pas une facture (relevé, courrier).
  - Modèle : Haiku 4.5 par défaut (coût), escalade vers Sonnet si confiance
    faible. (IDs de modèle à confirmer via la ref API au moment du câblage.)
"""
from __future__ import annotations
from .model import Facture


def lire_facture(chemin: str, *, client=None, modele: str | None = None) -> list[Facture]:
    """Lit un fichier (PDF/image) et renvoie les factures extraites.

    Non implémenté : nécessite l'accès à l'API Claude et des pièces d'exemple.
    """
    raise NotImplementedError(
        "OCR à câbler : fournir l'accès API Anthropic + des factures d'exemple. "
        "Voir tool/README.md § 'Ce dont j'ai besoin'."
    )
