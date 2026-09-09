"""Rangement des pièces dans le dossier de sortie du Drive.

Le client dépose tout en vrac ; le cabinet a besoin de s'y retrouver un an plus
tard, et le client aussi. On range donc chaque pièce sous :

    Documents générés par l'application/
        Exercice 2026/
            2026-03/
                Traité/
                En attente de traitement/

Trois décisions, prises ici une bonne fois :

0. **L'exercice d'abord.** Une pièce appartient à un exercice avant d'appartenir
   à un mois. Sans ce niveau, une facture de janvier 2027 arrivée dans le dépôt
   d'un dossier 2026 se rangerait dans `2027-01` à côté des mois de l'exercice
   en cours, et personne ne verrait le mélange. Avec lui, elle tombe dans
   « Exercice 2027 » et saute aux yeux. L'exercice est celui **fourni par le
   dossier** (il peut être décalé : 01/07 → 30/06) ; à défaut, l'année civile de
   la date de règlement.

1. **Le mois est celui du RÈGLEMENT**, pas celui du dépôt du fichier ni celui de
   la facture. En comptabilité de trésorerie, c'est la date de règlement qui fait
   entrer la charge dans l'exercice : ranger par cette date, c'est ranger comme
   la comptabilité est tenue. Une facture de décembre réglée en janvier se
   retrouve dans `2026-01`, exactement là où l'écriture se trouve.
   À défaut de date de règlement, on retombe sur la date de facture, et la pièce
   est marquée comme telle (`mois_estime`) pour qu'on sache que le rangement est
   une hypothèse.

2. **Deux états, plus une sortie de côté.** Sous chaque mois : `Traité` (une
   écriture a été produite) et `En attente de traitement` (la pièce est du
   ressort de la comptabilité mais il manque quelque chose : un devis qui
   deviendra une facture, un scan illisible, des montants incohérents).
   Un état intermédiaire de plus serait un état que personne ne maintient.

3. **Ce qui n'a rien à voir avec la comptabilité sort du rangement par mois.**
   Une photo prise par erreur, un contrat de bail, un relevé bancaire que le
   cabinet a déjà : rien à comptabiliser, rien à réclamer, et surtout rien à
   revoir chaque mois. Ces pièces vont dans un dossier unique à la racine —
   `Autres éléments sans rapport avec la comptabilité` — au lieu d'encombrer
   les mois de l'exercice. On ne les perd pas, on cesse de les croiser.
"""
from __future__ import annotations
from datetime import date

RACINE = "Documents générés par l'application"
TRAITE = "Traité"
EN_ATTENTE = "En attente de traitement"
SANS_RAPPORT = "Autres éléments sans rapport avec la comptabilité"

# Catégories du classement qui n'appellent AUCUN traitement comptable : ni
# écriture, ni relance, ni revue. Un devis ou un bon de commande n'en font pas
# partie — ils peuvent devenir une facture, ils restent « en attente ».
CATEGORIES_SANS_RAPPORT = ("hors_sujet", "contrat", "releve_bancaire")


def sans_rapport(rejet) -> bool:
    """Vrai si la pièce refusée n'a rien à voir avec la comptabilité."""
    cat = (rejet.get("categorie")
           or (rejet.get("brut") or {}).get("categorie") or "").strip().lower()
    return cat in CATEGORIES_SANS_RAPPORT


class Exercice:
    """Les bornes d'un exercice. Un exercice décalé (01/07 → 30/06) porte le
    millésime de sa date de clôture, comme le fait l'administration."""

    def __init__(self, debut: date, fin: date, libelle: str = ""):
        if fin < debut:
            raise ValueError("exercice : la clôture précède l'ouverture")
        self.debut, self.fin = debut, fin
        self.libelle = libelle or ("Exercice %d" % fin.year)

    def contient(self, d) -> bool:
        return isinstance(d, date) and self.debut <= d <= self.fin

    @classmethod
    def civil(cls, annee: int) -> "Exercice":
        return cls(date(annee, 1, 1), date(annee, 12, 31))


def exercice_de(d, exercice=None) -> str:
    """Nom du dossier d'exercice pour une date.

    Avec un `exercice` fourni, une date hors bornes est rangée à part : c'est
    une pièce qui n'appartient PAS à l'exercice qu'on est en train de traiter,
    et le nom du dossier le dit."""
    if not isinstance(d, date):
        return "Exercice indéterminé"
    if exercice is None:
        return "Exercice %d" % d.year
    if exercice.contient(d):
        return exercice.libelle
    return "Hors exercice %d" % d.year


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


def chemin(facture, *, traite: bool, racine: str = RACINE, exercice=None) -> str:
    """Chemin de rangement d'une pièce, relatif au dossier du client."""
    mois, _ = mois_de(facture)
    d = getattr(facture, "date_reglement", None) or getattr(facture, "date", None)
    return "%s/%s/%s/%s" % (racine, exercice_de(d, exercice), mois,
                            TRAITE if traite else EN_ATTENTE)


def ranger(factures, rejets=None, *, racine: str = RACINE, exercice=None) -> dict:
    """Construit le plan de rangement complet d'un traitement.

    `factures` = pièces retenues (une écriture est produite) -> `Traité`.
    `rejets`   = pièces écartées par le classement. Celles qui n'ont rien à voir
                 avec la comptabilité (photo, contrat, relevé) partent dans
                 `Autres éléments sans rapport avec la comptabilité`, à la
                 racine ; les autres (devis, illisible, montants incohérents)
                 dans `En attente de traitement` du mois, avec leur motif.

    Renvoie `{chemin: [entrées]}`, chaque entrée portant le nom du fichier, son
    empreinte, et le motif quand la pièce est en attente. Aucune pièce n'est
    perdue : tout ce qui entre ressort dans le plan."""
    plan: dict[str, list] = {}
    for f in factures or []:
        c = chemin(f, traite=True, racine=racine, exercice=exercice)
        mois, estime = mois_de(f)
        plan.setdefault(c, []).append({
            "fichier": getattr(f, "fichier", "") or getattr(f, "fournisseur", ""),
            "empreinte": getattr(f, "empreinte", ""),
            "mois_estime": estime,
            "motif": "",
        })
    for r in rejets or []:
        if sans_rapport(r):
            # ni écriture, ni relance, ni revue : hors du rangement par mois
            plan.setdefault("%s/%s" % (racine, SANS_RAPPORT), []).append({
                "fichier": r.get("fichier", ""),
                "empreinte": r.get("empreinte", ""),
                "mois_estime": False,
                "motif": r.get("motif", ""),
            })
            continue
        # un rejet n'a pas d'objet Facture : on range sur ce qu'on sait de lui
        brut = r.get("brut") or {}
        faux = type("P", (), {"date_reglement": None, "date": _d(brut.get("date"))})()
        c = chemin(faux, traite=False, racine=racine, exercice=exercice)
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
