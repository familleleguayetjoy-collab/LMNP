"""Rapprochement factures <-> lignes bancaires, et liste des manquants.

Le montant de la facture (issu de l'OCR) ne sert QU'À rapprocher/contrôler :
il n'est jamais posté. Un écart facture/banque est signalé, jamais corrigé.
"""
from __future__ import annotations
from datetime import date

from .normalize import cents

# comptes qui n'appellent pas de facture fournisseur
_SANS_FACTURE = {"627", "661", "164", "108", "512", "455"}


def justifiable(op) -> bool:
    return op.sens == "D" and (op.compte or "") not in _SANS_FACTURE


def _proche(a: float, b: float):
    """(exact, proche) : exact = même montant (±0,5% ou 2c) ; proche = ±8%."""
    diff = abs(a - b)
    return diff <= max(0.02, b * 0.005), diff <= b * 0.08


def rapprocher(ops, factures, jours: int = 25, jours_cheque: int = 60):
    """Associe chaque facture à une opération débit (montant + date proche).

    Tient compte du **mode de règlement** (cas 7) : un chèque cherche sur une
    fenêtre de dates plus large (décalage d'encaissement) ; espèces / autre =
    aucune correspondance bancaire attendue (ce n'est pas une anomalie).
    Marque op.facture / op.ecart. Retourne (débits, factures_orphelines)."""
    debits = [o for o in ops if o.sens == "D"]
    used = set()
    for fac in factures:
        fac.op = None
        mode = getattr(fac, "mode", "banque")
        if mode in ("especes", "autre"):
            continue                          # pas de ligne bancaire attendue
        fenetre = jours_cheque if mode == "cheque" else jours
        best, bestdelta, best_exact = None, 10 ** 9, False
        for o in debits:
            if id(o) in used:
                continue
            if not (o.date and fac.date):
                continue
            dd = abs((o.date - fac.date).days)
            exact, proche = _proche(fac.ttc, o.montant)
            if (exact or proche) and dd <= fenetre and dd < bestdelta:
                best, bestdelta, best_exact = o, dd, exact
        if best is not None:
            used.add(id(best))
            best.facture = fac
            best.ecart = not best_exact
            fac.op = best
    orphelines = [f for f in factures if f.op is None]
    return debits, orphelines


# --------------------------------------------------------------------------
# Cas particuliers de rapprochement (le rapprochement JUSTIFIE les flux ; il
# ne détermine JAMAIS à lui seul la règle de comptabilisation).
# --------------------------------------------------------------------------

def _ecart(total, cible, tol=0.02):
    return abs(total - cible) > max(tol, cible * 0.005)


def associer_factures(op, factures, tol=0.02):
    """Cas 1 — un règlement pour PLUSIEURS factures. Le total des justificatifs
    est comparé au mouvement : 'exact' -> validable ; sinon 'ecart' -> à vérifier."""
    total = round(sum(f.ttc for f in factures), 2)
    op.factures = list(factures)
    op.facture = factures[0] if factures else None
    for f in factures:
        f.op = op
        if op not in f.ops:
            f.ops.append(op)
    op.ecart = _ecart(total, op.montant, tol)
    if op.ecart:
        op.a_confirmer = ("Total des justificatifs %.2f € ≠ mouvement %.2f € — à vérifier"
                          % (total, op.montant))
    return ("ecart" if op.ecart else "exact", total)


def associer_reglements(facture, ops, tol=0.02):
    """Cas 2 & 3 — une facture réglée par PLUSIEURS mouvements, ou un règlement
    partiel. Conserve la relation, empêche de réutiliser un mouvement déjà
    affecté ailleurs, et calcule le reste. Statut : 'solde' | 'partiel' | 'ecart'.
    N.B. : sert uniquement à justifier les flux, jamais à changer la compta."""
    libres = [o for o in ops if not o.factures or facture in o.factures]
    total = round(sum(o.montant for o in libres), 2)
    facture.ops = list(libres)
    for o in libres:
        o.facture = facture
        if facture not in o.factures:
            o.factures.append(facture)
    reste = round(facture.ttc - total, 2)
    facture.reste = max(0.0, reste)
    if not _ecart(total, facture.ttc, tol):
        statut = "solde"
    elif reste > 0:
        statut = "partiel"
    else:
        statut = "ecart"
    for o in libres:
        o.partiel = (statut == "partiel")
        if statut != "solde":
            o.a_confirmer = ("Règlement partiel ? Facture %.2f €, réglé %.2f €, reste %.2f €"
                             % (facture.ttc, total, facture.reste))
    return (statut, total, facture.reste)


def detecter_virements_internes(ops, jours=3, tol=0.01):
    """Cas 4 — virement interne entre deux comptes bancaires de l'entreprise :
    même montant, sens opposé, date proche, comptes DIFFÉRENTS. On PROPOSE
    (a_confirmer), on ne valide jamais automatiquement ; si un mouvement a
    plusieurs correspondances possibles, on ne marque rien (ambigu)."""
    from collections import Counter
    cands = []
    for i, a in enumerate(ops):
        for b in ops[i + 1:]:
            if a.sens == b.sens:
                continue
            if (a.compte_bancaire or "") == (b.compte_bancaire or ""):
                continue
            if abs(a.montant - b.montant) > max(tol, a.montant * 0.005):
                continue
            if not (a.date and b.date) or abs((a.date - b.date).days) > jours:
                continue
            cands.append((a, b))
    freq = Counter()
    for a, b in cands:
        freq[id(a)] += 1
        freq[id(b)] += 1
    for a, b in cands:
        a.a_confirmer = b.a_confirmer = "Virement interne détecté entre deux comptes bancaires. Confirmer ?"
        if freq[id(a)] == 1 and freq[id(b)] == 1:      # pas d'ambiguïté -> proposé
            a.interne = b.interne = True
    return cands


def marquer_perso(op, forme="exploitant"):
    """Cas 5 — dépense personnelle confirmée : contrepartie selon la forme
    (108 compte de l'exploitant, ou 455 compte courant d'associé)."""
    op.traitement = "perso"
    op.compte = "455" if forme in ("sci", "sarl", "associe", "455") else "108"
    op.a_revoir = False
    op.a_confirmer = ""
    return op


def doublons_factures(factures):
    """Cas 6 (justificatifs) — même fichier réimporté (hash) même renommé, ou
    même (n°, fournisseur, date, TTC, HT). Signale, ne supprime pas."""
    from .normalize import normalize
    vus, dups = {}, []
    for f in factures:
        if getattr(f, "empreinte", ""):
            cle = ("h", f.empreinte)
        else:
            cle = ("m", (f.numero or "").strip().lower(), normalize(f.fournisseur),
                   f.date, cents(f.ttc), cents(getattr(f, "ht", 0.0)))
        if cle in vus:
            dups.append(f)
        else:
            vus[cle] = f
    return dups


def chercher_dans_fec(op, lignes_fec, jours=5):
    """Cas 8 — l'écriture existe-t-elle déjà dans le FEC importé ? Correspondance
    forte : même montant/sens, compte de même racine, date proche. Retourne la
    ligne FEC trouvée (à confirmer), ou None. Évite la double comptabilisation."""
    m = cents(op.montant)
    for l in lignes_fec:
        lm = cents(l.debit if op.sens == "D" else l.credit)
        if lm != m:
            continue
        if op.compte and l.compte and l.compte[:3] != op.compte[:3]:
            continue
        if op.date and l.date and abs((op.date - l.date).days) > jours:
            continue
        return l
    return None


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
