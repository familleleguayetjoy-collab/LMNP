"""Modèle de données normalisé. Les adaptateurs (FEC, relevé Excel, OCR)
produisent ces objets ; tout le reste du moteur travaille dessus."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class Operation:
    """Une ligne du relevé bancaire à coder.

    `montant` est le montant réellement mouvementé, donc TTC. En LMNP non
    assujetti à la TVA (cas courant), c'est ce montant TTC qui est comptabilisé
    en charge/produit ; aucune écriture de TVA n'est générée."""
    date: date
    libelle: str
    montant: float                 # toujours positif, TTC
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
    compte_bancaire: str = ""      # identifiant du compte (dossiers multi-banques)
    factures: list = field(default_factory=list)   # plusieurs justificatifs -> 1 mouvement
    interne: bool = False          # virement interne entre comptes de l'entreprise (proposé)
    partiel: bool = False          # règlement partiel
    traitement: str = ""           # "perso" = dépense personnelle, etc.
    a_confirmer: str = ""          # motif d'une confirmation demandée à l'humain


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
    numero: str = ""               # n° de facture (détection de doublon)
    ht: float = 0.0                # montant HT (sert au doublon, jamais posté seul)
    empreinte: str = ""            # hash du fichier -> doublon même si renommé
    mode: str = "banque"           # banque | cheque | especes | autre
    ops: list = field(default_factory=list)   # plusieurs règlements -> 1 facture
    reste: float = 0.0             # solde non réglé (règlement partiel)
    # classement d'entrée (cf. classement.py) : trace pourquoi la pièce a été
    # retenue. Un 'avoir' produit une écriture de sens inverse.
    categorie: str = ""            # facture_achat | facture_vente | avoir
    confiance_classement: float = 0.0
