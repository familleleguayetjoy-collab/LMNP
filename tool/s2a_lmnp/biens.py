"""Suivi par bien (LMNP/LMP/SCI à plusieurs biens).

Convention du cabinet : on distingue les biens par des SOUS-COMPTES de charge
(ex. 614 « Bonaparte », 6141 « Lépante »). Ce module tient la correspondance
compte ↔ bien :
  - on la **propose** depuis le FEC N-1 (le nom du bien figure dans le libellé),
  - on la **sauvegarde** (JSON) pour ne pas la refaire chaque année,
  - on peut la **modifier** et la **revoir** quand un compte a changé entre N-1
    et N (diff),
  - l'**adresse lue sur la facture** (OCR) route vers le bon bien, donc le bon
    sous-compte de charge.

Aucun montant ici : uniquement de l'affectation. stdlib only.
"""
from __future__ import annotations
from dataclasses import dataclass

from .normalize import tokens, strip_accents


@dataclass
class Bien:
    code: str          # identifiant court, ex. "bonaparte"
    nom: str           # libellé affiché, ex. "Bonaparte"
    adresse: str = ""  # adresse (sert à router les factures par l'OCR)


class MappingBiens:
    """Correspondance compte de charge ↔ bien, sauvegardable et révisable."""

    def __init__(self, biens=None, par_compte=None):
        self.biens = {b.code: b for b in (biens or [])}
        self.par_compte = dict(par_compte or {})   # compte -> code bien

    # --- édition ---
    def ajouter_bien(self, bien: Bien):
        self.biens[bien.code] = bien

    def affecter(self, compte: str, code: str):
        if code not in self.biens:
            raise ValueError("bien inconnu : %s" % code)
        self.par_compte[str(compte)] = code

    # --- lecture ---
    def bien_du_compte(self, compte):
        code = self.par_compte.get(str(compte))
        return self.biens.get(code) if code else None

    def comptes_du_bien(self, code):
        return sorted(c for c, v in self.par_compte.items() if v == code)

    def router_adresse(self, adresse):
        """Bien dont l'adresse/nom recoupe le mieux l'adresse lue sur la facture."""
        toks = set(tokens(adresse or ""))
        if not toks:
            return None
        best, score = None, 0
        for b in self.biens.values():
            bt = set(tokens((b.adresse or "") + " " + (b.nom or "")))
            inter = len(toks & bt)
            if inter > score:
                best, score = b, inter
        return best if score > 0 else None

    # --- persistance ---
    def to_json(self):
        return {
            "biens": [{"code": b.code, "nom": b.nom, "adresse": b.adresse}
                      for b in self.biens.values()],
            "par_compte": dict(self.par_compte),
        }

    @classmethod
    def from_json(cls, d):
        biens = [Bien(**x) for x in d.get("biens", [])]
        return cls(biens=biens, par_compte=d.get("par_compte", {}))

    # --- revue annuelle N vs N-1 ---
    def diff(self, precedent):
        """Compare les affectations à l'exercice précédent : comptes ajoutés,
        supprimés, ré-affectés. Sert à revoir le mapping quand le plan a bougé."""
        a = self.par_compte
        b = precedent.par_compte if isinstance(precedent, MappingBiens) else dict(precedent)
        return {
            "ajoutes": sorted(c for c in a if c not in b),
            "supprimes": sorted(c for c in b if c not in a),
            "modifies": sorted(c for c in a if c in b and a[c] != b[c]),
        }


def proposer_sous_compte(base, ordre: int):
    """Sous-compte proposé selon la convention du cabinet : 1er bien = compte de
    base, biens suivants = base suffixée d'un chiffre (614 → 6141 → 6142…).
    `ordre` = 0 pour le premier bien."""
    base = str(base)
    return base if ordre <= 0 else base + str(ordre)


def inferer_depuis_fec(lignes_fec, biens):
    """Propose une affectation compte → bien en cherchant le nom du bien dans le
    libellé (écriture ou compte) des lignes N-1. Résultat à confirmer / sauver."""
    prop = {}
    for l in lignes_fec:
        compte = l.compte or ""
        if not compte or compte[:1] not in ("6", "7", "2"):
            continue
        txt = strip_accents(l.libelle or "").lower()
        if getattr(l, "brute", None):
            txt += " " + strip_accents(" ".join(str(v) for v in l.brute.values())).lower()
        for b in biens:
            key = strip_accents(b.nom or "").lower()
            if key and key in txt and compte not in prop:
                prop[compte] = b.code
    return prop
