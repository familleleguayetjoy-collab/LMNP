"""Moteur LMNP S2A — cœur déterministe (aucun montant laissé à l'IA)."""
from .normalize import normalize, parse_montant, cents
from .fec import parse_fec, LigneFEC
from .dico import construire, Dictionnaire
from .model import Operation, Facture
from .codage import coder, IMMO, SEUIL_IMMO_HT
from .rapprochement import (rapprocher, manquants, sous_seuil, justifiable,
                            doublons, operations_od_factures,
                            associer_factures, associer_reglements,
                            detecter_virements_internes, marquer_perso,
                            doublons_factures, chercher_dans_fec)
from .quadra import to_quadratus, verifier_equilibre
from .biens import Bien, MappingBiens, proposer_sous_compte, inferer_depuis_fec
from .ia import (ClientIA, SEUIL_CONFIANCE_OCR, residu, questions_pour,
                 appliquer_reponses, resoudre_residu, resolver_depuis_client,
                 facture_depuis_ocr, lire_factures)
from .client_anthropic import ClientAnthropic

__all__ = [
    "normalize", "parse_montant", "cents", "parse_fec", "LigneFEC",
    "construire", "Dictionnaire", "Operation", "Facture", "coder", "IMMO",
    "SEUIL_IMMO_HT",
    "rapprocher", "manquants", "sous_seuil", "justifiable",
    "doublons", "operations_od_factures",
    "associer_factures", "associer_reglements", "detecter_virements_internes",
    "marquer_perso", "doublons_factures", "chercher_dans_fec",
    "to_quadratus", "verifier_equilibre",
    "Bien", "MappingBiens", "proposer_sous_compte", "inferer_depuis_fec",
    "ClientIA", "SEUIL_CONFIANCE_OCR", "residu", "questions_pour",
    "appliquer_reponses", "resoudre_residu", "resolver_depuis_client",
    "facture_depuis_ocr", "lire_factures", "ClientAnthropic",
]
