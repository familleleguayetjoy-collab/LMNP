"""Moteur LMNP S2A — cœur déterministe (aucun montant laissé à l'IA)."""
from .normalize import normalize, parse_montant, cents
from .fec import parse_fec, LigneFEC
from .dico import construire, Dictionnaire
from .model import Operation, Facture
from .codage import coder, IMMO
from .rapprochement import rapprocher, manquants, sous_seuil, justifiable
from .quadra import to_quadratus, verifier_equilibre

__all__ = [
    "normalize", "parse_montant", "cents", "parse_fec", "LigneFEC",
    "construire", "Dictionnaire", "Operation", "Facture", "coder", "IMMO",
    "rapprocher", "manquants", "sous_seuil", "justifiable",
    "to_quadratus", "verifier_equilibre",
]
