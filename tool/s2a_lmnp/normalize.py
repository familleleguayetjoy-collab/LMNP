"""Normalisation des libellés et des montants — briques partagées.

Aucune dépendance externe. Tout ce qui touche aux montants est ici (jamais
laissé à une IA) : parsing robuste des nombres au format français.
"""
from __future__ import annotations
import re
import unicodedata

# Mots d'opération / formes juridiques à retirer pour comparer des libellés.
_STOP = re.compile(
    r"\b(VIR|VIRT|VIREMENT|PRLV|PRELEVEMENT|PRELEV|CB|CHQ|CHEQUE|ECH|ECHEANCE|"
    r"RECU|SEPA|CLIENTS?|PARTICULIERS?|SA|SAS|SARL|EURL|SCI|PRO|GESTION|INTERV|"
    r"MENSUALITE|FACTURE|FACT|REF|MANDAT|ID)\b"
)


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def normalize(libelle: str) -> str:
    """Libellé -> clé comparable : majuscules, sans accents, sans mots d'opération,
    sans chiffres/dates/ponctuation. Ex. 'PRLV SYNDIC AZUR SA T1' -> 'SYNDIC AZUR'."""
    s = strip_accents(str(libelle or "")).upper()
    s = _STOP.sub(" ", s)
    s = re.sub(r"T[1-4]\b", " ", s)          # trimestres
    s = re.sub(r"[^A-Z ]", " ", s)            # retire chiffres, ponctuation, dates
    s = re.sub(r"\s+", " ", s).strip()
    return s


def tokens(libelle: str) -> list[str]:
    return [t for t in normalize(libelle).split(" ") if len(t) > 2]


_NUM = re.compile(r"[^\d,.\-]")


def parse_montant(v) -> float:
    """Parse un montant au format FR/EU de façon robuste.

    Gère : '1 234,56'  '1.234,56'  '1234.56'  '-1 200,00'  '(1 200,00)'  '1200'
    Retourne un float. Lève ValueError si non parsable (jamais de valeur inventée).
    """
    if v is None:
        raise ValueError("montant vide")
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if not s:
        raise ValueError("montant vide")
    neg = s.startswith("(") and s.endswith(")")   # comptable : (1 200,00) = négatif
    s = s.strip("()")
    s = _NUM.sub("", s)                             # ne garde que chiffres , . -
    if not s or s in ("-", ".", ","):
        raise ValueError(f"montant non parsable: {v!r}")
    # Déterminer le séparateur décimal = le dernier ',' ou '.' rencontré.
    last_c, last_d = s.rfind(","), s.rfind(".")
    dec = max(last_c, last_d)
    if dec == -1:
        num = s.replace(",", "").replace(".", "")
    else:
        ent = re.sub(r"[.,]", "", s[:dec])
        frac = re.sub(r"[.,]", "", s[dec + 1:])
        num = ent + "." + frac
    val = float(num)
    return -val if neg and val > 0 else val


def cents(v: float) -> int:
    """Arrondi bancaire au centime, en entier (pour Quadra & contrôles d'équilibre)."""
    # arrondi 'half up' pour éviter les surprises float
    return int((abs(v) * 100) + 0.5) * (1 if v >= 0 else -1)
