"""Lecture des factures (OCR + extraction) via l'API Claude — INTERFACE.

À CÂBLER quand on aura : (1) l'accès API (clé Anthropic / DPA signé),
(2) le modèle par défaut confirmé.

Règles de sûreté NON négociables côté implémentation :
  - Le montant extrait par l'IA ne sert QU'À rapprocher/contrôler, JAMAIS à
    poster une écriture. Le montant posté vient toujours du relevé bancaire.
  - Toujours renvoyer une confiance ; en dessous d'un seuil -> pièce marquée
    "à revoir" (l'IA ne devine pas en silence).
  - Un PDF peut contenir plusieurs factures / pages -> renvoyer une liste.

CE QUE LES 3 FACTURES RÉELLES DU DOSSIER SANS-BANQUE NOUS ONT APPRIS
(EDF, Brico Dépôt, Bouygues Telecom — cas à gérer impérativement) :
  1. TRAVAILLER SUR L'IMAGE, PAS LA COUCHE TEXTE. Le ticket Brico Dépôt est
     un scan thermique : sa couche texte PDF est illisible ("MASWIAHI...") ;
     seule l'image est exploitable. -> toujours envoyer la/les page(s) en
     image au modèle vision, ne pas se fier au texte extractible.
  2. MONTANT FACTURÉ ≠ MONTANT PAYÉ. Sur le ticket, "Espèces 81,07 / Rendu
     10,00" ; le TTC de la facture est 71,07. Extraire le TOTAL de la facture,
     jamais l'espèce remise ni le rendu.
  3. IGNORER LES BLOCS "EXEMPLE". La facture Bouygues p.3 contient un
     récapitulatif fictif filigrané "EXEMPLE" (11,49 / 3,49 / 8,00…) : ne
     jamais en tirer de montant. Ancrer l'extraction sur le total de la
     page 1 ("Montant de la facture soumis à TVA" / "Facture TTC").
  4. CHAMPS À REMONTER : fournisseur, date de facture, TTC, TVA (et HT),
     et si présent le "prélevé le" (date de flux) + l'adresse du bien
     (rapproche la facture au bon dossier : ici "4 Ruelle de la Boucherie").
  5. Le libellé fournisseur pour le dictionnaire vient du nom commercial
     (EDF, BRICO DEPOT, BOUYGUES TELECOM), pas de l'adresse du bien.
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
