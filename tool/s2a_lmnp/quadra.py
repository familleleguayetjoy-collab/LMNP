"""Export au format Quadratus ASCII (Cegid Quadra).

Enregistrement 'Mouvement' (type M), largeur fixe 256, écritures en PARTIE
DOUBLE et équilibrées. Positions (standard Quadratus — À VALIDER avec le
paramétrage d'import du cabinet) :
  1 (1) 'M' | 2-9 (8) compte | 10-11 (2) journal | 12-14 (3) folio '000'
  15-20 (6) date JJMMAA | 21 (1) code libellé '0' | 22-41 (20) libellé
  42 (1) sens D/C | 43-55 (13) montant en centimes | 182-193 (12) n° pièce
Texte cadré à gauche (espaces), numérique cadré à droite (zéros).
"""
from __future__ import annotations
from .normalize import strip_accents, cents


def _txt(s, n):
    s = strip_accents(str(s or "")).upper()
    s = "".join(c if (c.isalnum() or c == " ") else " " for c in s)
    s = " ".join(s.split())
    return (s[:n]).ljust(n)


def _num(v, n):
    c = str(cents(v))
    return c[-n:] if len(c) >= n else c.rjust(n, "0")


def _date(d):
    return "%02d%02d%02d" % (d.day, d.month, d.year % 100)


def _ligne(compte, journal, d, libelle, sens, montant, piece):
    b = [" "] * 256

    def put(pos, s):
        for i, ch in enumerate(s):
            b[pos - 1 + i] = ch
    put(1, "M"); put(2, _txt(compte, 8)); put(10, _txt(journal, 2)); put(12, "000")
    put(15, _date(d)); put(21, "0"); put(22, _txt(libelle, 20))
    put(42, sens); put(43, _num(montant, 13)); put(182, _txt(piece, 12))
    return "".join(b)


def to_quadratus(ops, avec_banque: bool = True) -> str:
    journal = "BQ" if avec_banque else "OD"
    cp = "512" if avec_banque else "108"
    out, p = [], 0
    for op in ops:
        p += 1
        piece = "P%04d" % p
        d, lib, m = op.date, op.libelle, op.montant
        if op.split:                       # échéance de prêt : 661 + 164 / contrepartie
            i, k = op.split
            out.append(_ligne("661", journal, d, lib + " INTERETS", "D", i, piece))
            out.append(_ligne("164", journal, d, lib + " CAPITAL", "D", k, piece))
            out.append(_ligne(cp, journal, d, lib, "C", m, piece))
            continue
        s = "D" if op.sens == "D" else "C"
        os = "C" if op.sens == "D" else "D"
        out.append(_ligne(op.compte or "471", journal, d, lib, s, m, piece))
        out.append(_ligne(cp, journal, d, lib, os, m, piece))
    return "\r\n".join(out) + "\r\n"


def verifier_equilibre(texte: str):
    """Contrôle interne : somme des débits == somme des crédits (en centimes)."""
    deb = cred = 0
    for ln in texte.splitlines():
        if not ln:
            continue
        c = int(ln[42:55])
        if ln[41] == "D":
            deb += c
        else:
            cred += c
    return deb, cred, deb == cred
