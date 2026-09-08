"""Rangement des pièces dans le dossier de sortie du Drive.

Le client dépose tout en vrac ; le cabinet a besoin de s'y retrouver un an plus
tard, et le client aussi. On range donc chaque pièce sous :

    Documents générés par l'application/
        2026-03/
            Traité/
            En attente de traitement/

Deux décisions, prises ici une bonne fois :

1. **Le mois est celui du RÈGLEMENT**, pas celui du dépôt du fichier ni celui de
   la facture. En comptabilité de trésorerie, c'est la date de règlement qui fait
   entrer la charge dans l'exercice : ranger par cette date, c'est ranger comme
   la comptabilité est tenue. Une facture de décembre réglée en janvier se
   retrouve dans `2026-01`, exactement là où l'écriture se trouve.
   À défaut de date de règlement, on retombe sur la date de facture, et la pièce
   est marquée comme telle (`mois_estime`) pour qu'on sache que le rangement est
   une hypothèse.

2. **Deux états seulement** : `Traité` (une écriture a été produite) et
   `En attente de traitement` (tout le reste : pièce non comptable, incomplète,
   en attente d'une information du client). Un état intermédiaire de plus serait
   un état que personne ne maintient.
"""
from __future__ import annotations
from datetime import date

RACINE = "Documents générés par l'application"
TRAITE = "Traité"
EN_ATTENTE = "En attente de traitement"


def mois_de(facture) -> tuple[str, bool]:
    """Renvoie `(AAAA-MM, estime)` pour une pièce.

    `estime=True` quand on a dû retomber sur la date de facture faute de date de
    règlement : le rangement est alors une hypothèse, pas un fait."""
    d = getattr(facture, "date_reglement", None)
    estime = d is None
    if d is None:
        d = getattr(facture, "date", None)
    if not isinstance(d, date):
        return "sans-date", True
    return "%04d-%02d" % (d.year, d.month), estime


def chemin(facture, *, traite: bool, racine: str = RACINE) -> str:
    """Chemin de rangement d'une pièce, relatif au dossier du client."""
    mois, _ = mois_de(facture)
    return "%s/%s/%s" % (racine, mois, TRAITE if traite else EN_ATTENTE)


def ranger(factures, rejets=None, *, racine: str = RACINE) -> dict:
    """Construit le plan de rangement complet d'un traitement.

    `factures` = pièces retenues (une écriture est produite) -> `Traité`.
    `rejets`   = pièces écartées par le classement (devis, illisible, montants
                 incohérents...) -> `En attente de traitement`, avec leur motif.

    Renvoie `{chemin: [entrées]}`, chaque entrée portant le nom du fichier, son
    empreinte, et le motif quand la pièce est en attente. Aucune pièce n'est
    perdue : tout ce qui entre ressort dans le plan."""
    plan: dict[str, list] = {}
    for f in factures or []:
        c = chemin(f, traite=True, racine=racine)
        mois, estime = mois_de(f)
        plan.setdefault(c, []).append({
            "fichier": getattr(f, "fichier", "") or getattr(f, "fournisseur", ""),
            "empreinte": getattr(f, "empreinte", ""),
            "mois_estime": estime,
            "motif": "",
        })
    for r in rejets or []:
        # un rejet n'a pas d'objet Facture : on range sur ce qu'on sait de lui
        brut = r.get("brut") or {}
        faux = type("P", (), {"date_reglement": None, "date": _d(brut.get("date"))})()
        c = chemin(faux, traite=False, racine=racine)
        mois, estime = mois_de(faux)
        plan.setdefault(c, []).append({
            "fichier": r.get("fichier", ""),
            "empreinte": r.get("empreinte", ""),
            "mois_estime": estime,
            "motif": r.get("motif", ""),
        })
    return plan


def _d(v):
    """Date ISO d'un dict brut d'OCR -> date, ou None (jamais d'exception)."""
    from datetime import datetime
    if not v:
        return None
    try:
        return datetime.strptime(str(v).strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def resume(plan: dict) -> list:
    """Vue à plat du plan, triée, pour l'affichage et les tests."""
    out = []
    for c in sorted(plan):
        out.append({"chemin": c, "pieces": len(plan[c]),
                    "estimees": sum(1 for e in plan[c] if e["mois_estime"])})
    return out
