"""Dictionnaire client construit à partir du FEC N-1.

Pour chaque libellé (normalisé) rencontré l'an dernier sur un compte de
charge / produit / immobilisation (classes 6, 7, 2), on mémorise le(s)
compte(s) utilisé(s). Un libellé associé à PLUSIEURS comptes en N-1 est marqué
'multi' : il devra être tranché par l'humain (règle demandée par le cabinet).
"""
from __future__ import annotations
from collections import Counter
from dataclasses import dataclass, field

from .normalize import normalize, tokens


def _codable(compte: str) -> bool:
    return bool(compte) and compte[0] in ("6", "7", "2")


@dataclass
class Entree:
    cle: str
    comptes: Counter            # compte -> nb d'occurrences
    libelles: set = field(default_factory=set)
    toks: list = field(default_factory=list)

    @property
    def principal(self) -> str:
        return self.comptes.most_common(1)[0][0]

    @property
    def multi(self) -> bool:
        return len(self.comptes) > 1


class Dictionnaire:
    def __init__(self):
        self.par_cle: dict[str, Entree] = {}

    def ajouter(self, libelle: str, compte: str):
        cle = normalize(libelle)
        if not cle:
            return
        e = self.par_cle.get(cle)
        if e is None:
            e = Entree(cle=cle, comptes=Counter(), toks=tokens(libelle))
            self.par_cle[cle] = e
        e.comptes[compte] += 1
        e.libelles.add(libelle)

    def exact(self, libelle: str) -> Entree | None:
        return self.par_cle.get(normalize(libelle))

    def meilleur_flou(self, libelle: str):
        """Meilleure entrée par recouvrement de tokens. Retourne (entree, couverture, inter)."""
        toks = tokens(libelle)
        if not toks:
            return None, 0.0, 0
        sett = set(toks)
        best, bcov, binter = None, 0.0, 0
        for e in self.par_cle.values():
            if not e.toks:
                continue
            inter = len(sett & set(e.toks))
            cov = inter / min(len(e.toks), len(toks))
            if cov > bcov or (cov == bcov and inter > binter):
                best, bcov, binter = e, cov, inter
        return best, bcov, binter

    def __len__(self):
        return len(self.par_cle)


def construire(lignes_fec) -> Dictionnaire:
    d = Dictionnaire()
    for l in lignes_fec:
        if _codable(l.compte) and l.libelle:
            d.ajouter(l.libelle, l.compte)
    return d
