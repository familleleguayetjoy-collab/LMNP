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


def doublons(ops):
    """Détecte les écritures en double (même date + montant + compte + libellé).
    Utile quand le relevé pré-codé et une saisie manuelle se recoupent : on ne
    veut pas passer deux fois la même écriture."""
    from .normalize import normalize, cents
    vus, dups = {}, []
    for o in ops:
        cle = (o.date, cents(o.montant), o.compte or "", normalize(o.libelle))
        if cle in vus:
            dups.append(o)
        else:
            vus[cle] = o
    return dups


def operations_od_factures(factures, dico, resolver=None):
    """Cas : une facture existe mais AUCUNE ligne bancaire ne lui correspond
    (paiement hors banque, dossier sans banque, ou banque incomplète).
    On passe alors une écriture au journal d'OD : le compte de charge codé
    depuis le fournisseur, en contrepartie du compte 108 (décidé par le
    cabinet). Le montant vient de la facture (seul cas où on n'a pas la banque)."""
    from .model import Operation
    from .codage import coder
    ops = []
    for f in factures:
        if getattr(f, "op", None) is not None:
            continue                      # déjà rapprochée à une ligne banque
        o = Operation(date=f.date, libelle=f.fournisseur, montant=f.ttc, sens="D")
        o.facture = f
        coder(o, dico, resolver)
        ops.append(o)
    return ops
