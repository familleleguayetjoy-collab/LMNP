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
    if "-" in s:                                    # signe en tête OU en fin ('120,00-')
        neg = True
        s = s.replace("-", "")
    if not s or s in (".", ","):
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


def parse_date(v):
    """Date robuste -> datetime.date. Ne devine jamais : lève ValueError sinon.

    Accepte : date/datetime ; 'AAAA-MM-JJ', 'JJ/MM/AAAA', 'JJ/MM/AA', 'AAAAMMJJ',
    'JJ-MM-AAAA', 'JJ.MM.AAAA' ; et le **numéro de série Excel** (int/float ou
    petite chaîne de chiffres, base 1899-12-30) — fréquent dans les relevés Excel.
    """
    import datetime as _dt
    if v is None or v == "":
        raise ValueError("date vide")
    if isinstance(v, _dt.datetime):
        return v.date()
    if isinstance(v, _dt.date):
        return v
    if isinstance(v, (int, float)):
        n = int(v)
        if n >= 3_000_000:                       # trop grand pour Excel -> AAAAMMJJ
            return _dt.datetime.strptime(str(n), "%Y%m%d").date()
        return _dt.date(1899, 12, 30) + _dt.timedelta(days=n)
    s = str(v).strip()
    if s.isdigit():
        if len(s) == 8:                          # AAAAMMJJ (FEC)
            return _dt.datetime.strptime(s, "%Y%m%d").date()
        if len(s) <= 5:                          # n° de série Excel
            return _dt.date(1899, 12, 30) + _dt.timedelta(days=int(s))
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%d.%m.%Y"):
        try:
            return _dt.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError("date non parsable: %r" % (v,))


def cents(v: float) -> int:
    """Arrondi bancaire au centime, en entier (pour Quadra & contrôles d'équilibre)."""
    # arrondi 'half up' pour éviter les surprises float
    return int((abs(v) * 100) + 0.5) * (1 if v >= 0 else -1)
