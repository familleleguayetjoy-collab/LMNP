"""Lecture du FEC (Fichier des Écritures Comptables) — format normalisé DGFiP.

Le FEC est un texte à 18 colonnes, séparateur variable (| ou tab ou ;),
encodage souvent Windows-1252, montants au format français. On lit par NOM
de colonne (robuste à l'ordre) et on tolère les variantes.

Sortie : liste de LigneFEC. Aucune valeur inventée : une ligne illisible est
signalée, pas devinée.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable
import io

from .normalize import parse_montant

# Colonnes officielles du FEC (on matche sur une version normalisée du nom).
_ALIASES = {
    "journalcode": "journal", "jour nalcode": "journal",
    "comptenum": "compte", "comptelib": "compte_lib",
    "compauxnum": "aux", "compauxlib": "aux_lib",
    "ecriturelib": "libelle", "ecrituredate": "date",
    "pieceref": "piece", "piecedate": "piece_date",
    "debit": "debit", "credit": "credit",
    "montant": "montant", "sens": "sens",
}


@dataclass
class LigneFEC:
    compte: str
    libelle: str
    debit: float
    credit: float
    date: date | None
    journal: str = ""
    aux: str = ""
    brute: dict | None = None

    @property
    def montant(self) -> float:
        return self.debit if self.debit else self.credit

    @property
    def sens(self) -> str:
        return "D" if self.debit else "C"


def _decode(raw: bytes) -> str:
    if isinstance(raw, str):
        return raw
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace")


def _detect_delim(header: str) -> str:
    best, bestn = "\t", 0
    for d in ("\t", "|", ";", ","):
        n = header.count(d)
        if n > bestn:
            best, bestn = d, n
    return best


def _norm_col(name: str) -> str:
    key = "".join(ch for ch in name.strip().lower() if ch.isalnum())
    return _ALIASES.get(key, key)


def _parse_date(s: str) -> date | None:
    s = (s or "").strip()
    for fmt in ("%Y%m%d", "%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def parse_fec(raw: bytes | str) -> list[LigneFEC]:
    text = _decode(raw)
    # première ligne non vide = en-tête
    lines = [l for l in text.splitlines() if l.strip()]
    if not lines:
        return []
    delim = _detect_delim(lines[0])
    header = [_norm_col(c) for c in lines[0].split(delim)]
    idx = {name: i for i, name in enumerate(header)}
    has_debit = "debit" in idx and "credit" in idx
    has_montant = "montant" in idx and "sens" in idx
    if "compte" not in idx or ("libelle" not in idx):
        raise ValueError("FEC : colonnes CompteNum / EcritureLib introuvables — en-tête inattendu : %r" % header)

    out: list[LigneFEC] = []
    for ln in lines[1:]:
        parts = ln.split(delim)
        if len(parts) < len(header):
            parts += [""] * (len(header) - len(parts))  # tolère colonnes manquantes en fin

        def col(name, default=""):
            return parts[idx[name]] if name in idx else default

        try:
            if has_debit:
                deb = _safe_montant(col("debit"))
                cred = _safe_montant(col("credit"))
            elif has_montant:
                m = _safe_montant(col("montant"))
                sens = col("sens").strip().upper()[:1]
                deb, cred = (m, 0.0) if sens == "D" else (0.0, m)
            else:
                raise ValueError("ni (Debit/Credit) ni (Montant/Sens)")
        except ValueError:
            # ligne au montant illisible : on la garde marquée (à ne pas ignorer silencieusement)
            deb = cred = 0.0
        out.append(LigneFEC(
            compte=col("compte").strip(),
            libelle=col("libelle").strip(),
            debit=deb, credit=cred,
            date=_parse_date(col("date")),
            journal=col("journal").strip(),
            aux=col("aux").strip(),
            brute={header[i]: parts[i] for i in range(len(header))},
        ))
    return out


def _safe_montant(v) -> float:
    v = (v or "").strip()
    if not v:
        return 0.0
    return parse_montant(v)
