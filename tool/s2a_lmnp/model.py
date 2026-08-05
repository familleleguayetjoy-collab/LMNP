"""Modèle de données normalisé. Les adaptateurs (FEC, relevé Excel, OCR)
produisent ces objets ; tout le reste du moteur travaille dessus."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class Operation:
    """Une ligne du relevé bancaire à coder."""
    date: date
    libelle: str
    montant: float                 # toujours positif
    sens: str                      # 'D' = dépense (débit banque) / 'C' = recette
    amort: Optional[tuple] = None  # (interets, capital) si échéance de prêt connue

    # rempli par le codage :
    compte: Optional[str] = None
    origine: str = ""              # dict | near | fuzzy | regle | web | amort | inconnu
    confiance: float = 0.0
    a_revoir: bool = False
    motif: str = ""                # raison de la revue humaine
    options: list = field(default_factory=list)  # comptes candidats proposés
    split: Optional[tuple] = None  # (interets, capital) pour l'échéance

    # rempli par le rapprochement :
    facture: "Optional[Facture]" = None
    ecart: bool = False            # écart de montant facture/banque


@dataclass
class Facture:
    """Une pièce lue dans le Drive (OCR)."""
    fournisseur: str
    date: date
    ttc: float
    tva: float = 0.0
    fichier: str = ""              # chemin/nom dans le Drive
    confiance_ocr: float = 1.0     # confiance de l'extraction
    op: Optional[Operation] = None
