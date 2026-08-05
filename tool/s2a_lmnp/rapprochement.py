"""Rapprochement factures <-> lignes bancaires, et liste des manquants.

Le montant de la facture (issu de l'OCR) ne sert QU'À rapprocher/contrôler :
il n'est jamais posté. Un écart facture/banque est signalé, jamais corrigé.
"""
from __future__ import annotations
from datetime import date

# comptes qui n'appellent pas de facture fournisseur
_SANS_FACTURE = {"627", "661", "164", "108", "512", "455"}


def justifiable(op) -> bool:
    return op.sens == "D" and (op.compte or "") not in _SANS_FACTURE


def _proche(a: float, b: float):
    """(exact, proche) : exact = même montant (±0,5% ou 2c) ; proche = ±8%."""
    diff = abs(a - b)
    return diff <= max(0.02, b * 0.005), diff <= b * 0.08


def rapprocher(ops, factures, jours: int = 25):
    """Associe chaque facture à une opération débit (montant + date proche).
    Marque op.facture / op.ecart. Retourne (rapprochees, factures_orphelines)."""
    debits = [o for o in ops if o.sens == "D"]
    used = set()
    for fac in factures:
        fac.op = None
        best, bestdelta, best_exact = None, 10 ** 9, False
        for o in debits:
            if id(o) in used:
                continue
            if not (o.date and fac.date):
                continue
            dd = abs((o.date - fac.date).days)
            exact, proche = _proche(fac.ttc, o.montant)
            if (exact or proche) and dd <= jours and dd < bestdelta:
                best, bestdelta, best_exact = o, dd, exact
        if best is not None:
            used.add(id(best))
            best.facture = fac
            best.ecart = not best_exact
            fac.op = best
    orphelines = [f for f in factures if f.op is None]
    return debits, orphelines


def manquants(ops, seuil: float = 150.0):
    """Dépenses justifiables, sans facture, au-dessus du seuil de matérialité."""
    return sorted(
        [o for o in ops if justifiable(o) and o.facture is None and o.montant > seuil],
        key=lambda o: -o.montant,
    )


def sous_seuil(ops, seuil: float = 150.0):
    return [o for o in ops if justifiable(o) and o.facture is None and o.montant <= seuil]
