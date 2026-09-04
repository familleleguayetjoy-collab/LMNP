"""Couche IA — INTERFACE (contrat JSON entrée/sortie + point de branchement).

AUCUNE CLÉ N'EST REQUISE ICI. Le moteur reste 100 % déterministe tant qu'aucun
client n'est injecté. Quand l'accès API sera fourni, il suffira d'écrire une
classe qui parle à l'API Claude en respectant le protocole `ClientIA` ci-dessous
et de la passer à ces fonctions — le reste du moteur ne change pas.

Deux tâches, et deux seulement, sont confiées à l'IA, et uniquement pour
PROPOSER (l'humain valide toujours) :

  A. OCR — lire une facture (image) -> champs structurés.
     Le montant extrait ne sert QU'À rapprocher/contrôler, JAMAIS à poster.

  B. Résolution du RÉSIDU ambigu — seules les opérations que les règles n'ont
     pas su trancher (a_revoir=True) sont regroupées en UN SEUL appel par
     dossier, en JSON structuré. L'IA propose un compte parmi les options déjà
     identifiées par les règles + une raison ; rien n'est validé sans humain.

C'est l'architecture « règles d'abord, IA sur le seul résidu, en lot, humain
valide » décrite dans la note d'architecture : elle minimise le coût
(≈ 0,10-0,25 €/dossier) en n'envoyant à l'IA que ce qui reste réellement ambigu,
et jamais un montant à décider.

────────────────────────────────────────────────────────────────────────────
CONTRAT JSON — B. Résolution du résidu
────────────────────────────────────────────────────────────────────────────
Entrée (une question par opération ambiguë) :
    {
      "id":       str,            # référence stable de l'opération (interne)
      "libelle":  str,            # libellé bancaire brut
      "montant":  float,          # TTC — INFORMATIF ; l'IA ne le renvoie jamais
      "sens":     "D" | "C",
      "options":  [str, ...],     # comptes candidats trouvés par les règles
      "contexte": str             # motif de la règle (ce qui coince)
    }
Sortie (une réponse par id) :
    {
      "id":       str,
      "compte":   str,            # DOIT appartenir à "options" (sinon ignoré)
      "confiance": float,         # 0..1
      "raison":   str
    }
Garde-fou : toute réponse dont "compte" n'est pas dans les options d'origine
est REJETÉE (on ne laisse pas l'IA inventer un compte hors du cadre des règles).
Aucune réponse ne peut porter de montant : le montant n'est pas dans le schéma
de sortie, donc l'IA ne peut structurellement pas le modifier.

────────────────────────────────────────────────────────────────────────────
CONTRAT JSON — A. OCR
────────────────────────────────────────────────────────────────────────────
Sortie (une entrée par facture trouvée dans le fichier ; un PDF peut en avoir
plusieurs) :
    {
      "fournisseur": str,         # nom commercial (EDF, BRICO DEPOT, ...)
      "date":        "AAAA-MM-JJ",
      "ttc":         float,
      "tva":         float,
      "ht":          float,
      "date_flux":   "AAAA-MM-JJ" | null,   # "prélevé le" si présent
      "adresse_bien": str | null,           # route la facture vers le bon bien
      "numero":      str | null,
      "confiance":   float                  # <seuil -> pièce « à revoir »
    }
Le détail des pièges (ticket thermique, TTC ≠ espèces remises, blocs
« EXEMPLE ») est documenté dans `ocr.py`.
"""
from __future__ import annotations
from datetime import date, datetime
from typing import Optional, Protocol, runtime_checkable

from .model import Operation, Facture

SEUIL_CONFIANCE_OCR = 0.75   # en dessous, la facture est marquée « à revoir »


@runtime_checkable
class ClientIA(Protocol):
    """Le seul objet à implémenter le jour du câblage API.

    Une implémentation réelle enveloppe le client Anthropic (vision pour l'OCR,
    sortie JSON structurée pour la résolution) et respecte les deux contrats
    ci-dessus. Tout le reste du moteur est déjà branché dessus."""

    def lire_facture(self, chemin: str, *, modele: str | None = None) -> list[dict]:
        """A. OCR d'un fichier -> liste de dicts (contrat A)."""
        ...

    def resoudre(self, questions: list[dict], *, modele: str | None = None) -> list[dict]:
        """B. Résolution en lot du résidu -> liste de dicts (contrat B)."""
        ...


# ---------------------------------------------------------------------------
# B. Résidu ambigu -> lot -> application des propositions (jamais de validation)
# ---------------------------------------------------------------------------

SEUIL_AUTO_IA = 0.85   # au-dessus, l'IA code AUTOMATIQUEMENT (doute faible) ;
                       # en dessous, elle propose et l'humain tranche (doute sérieux).


def _inconnu(o) -> bool:
    """Opération que les règles n'ont pas su qualifier (fournisseur inconnu)."""
    return getattr(o, "origine", "") == "inconnu" or (getattr(o, "compte", "") or "") == "471"


def residu(ops) -> list:
    """Le sous-ensemble envoyé à l'IA : les opérations « à revoir » qui gardent
    un vrai choix (≥2 comptes candidats) OU les fournisseurs inconnus (que l'IA
    va coder en raisonnant comme un comptable). Le reste est déjà tranché."""
    return [o for o in ops if getattr(o, "a_revoir", False)
            and (len(getattr(o, "options", []) or []) >= 2 or _inconnu(o))]


def _cle(op) -> str:
    return "op-%d" % id(op)


def questions_pour(ops) -> list[dict]:
    """Construit la charge utile JSON (contrat B, entrée) à partir du résidu.
    Le montant est joint à titre INFORMATIF uniquement."""
    q = []
    for o in residu(ops):
        q.append({
            "id": _cle(o),
            "libelle": o.libelle or "",
            "montant": round(float(o.montant), 2),   # informatif — jamais renvoyé
            "sens": o.sens,
            "options": list(o.options or []),
            "contexte": o.motif or "",
            "inconnu": _inconnu(o),   # True -> l'IA propose librement un compte PCG
        })
    return q


def appliquer_reponses(ops, reponses, *, seuil_auto=SEUIL_AUTO_IA) -> int:
    """Applique les réponses de l'IA au résidu. Automatise au maximum :

    - confiance ≥ seuil_auto  -> CODÉ AUTOMATIQUEMENT (a_revoir=False), tracé
      origine 'ia' + confiance (auditable NPMQ) ;
    - confiance < seuil_auto   -> proposition, a_revoir reste True (doute sérieux
      -> l'humain tranche).
    Garde-fous : on ne touche JAMAIS au montant ni au sens ; pour une opération
    à options connues, le compte doit être dans les options ; pour un fournisseur
    inconnu, l'IA peut proposer librement un compte du plan. Renvoie le nombre
    de réponses retenues."""
    par_cle = {_cle(o): o for o in ops}
    retenues = 0
    for r in reponses or []:
        o = par_cle.get(r.get("id"))
        if o is None:
            continue
        compte = str(r.get("compte") or "")
        if not compte:
            continue
        if not _inconnu(o) and compte not in (o.options or []):
            continue                              # hors cadre d'un choix connu -> ignoré
        conf = min(float(r.get("confiance") or 0.0), 0.99)
        raison = (r.get("raison") or "").strip()
        o.options = [compte] + [c for c in (o.options or []) if c != compte]
        if conf >= seuil_auto:
            o.compte = compte
            o.origine = "ia"
            o.confiance = conf
            o.a_revoir = False
            o.a_confirmer = ""
            o.motif = ("Codé automatiquement par l'IA (confiance %.2f) — montant inchangé%s"
                       % (conf, (" — " + raison) if raison else ""))
        else:
            o.confiance = max(float(o.confiance or 0.0), conf)
            o.motif = ("Proposition IA (à valider) : %s → %s%s"
                       % (o.motif or "ambigu", compte, (" — " + raison) if raison else ""))
            o.a_confirmer = "Compte proposé par l'IA : %s. À valider." % compte
        retenues += 1
    return retenues


def resoudre_residu(ops, client: Optional[ClientIA], *, modele: str | None = None) -> int:
    """Orchestration B : un seul appel pour tout le résidu du dossier.
    Sans client (pas de clé), no-op : le moteur reste déterministe. Renvoie le
    nombre de propositions appliquées."""
    if client is None:
        return 0
    questions = questions_pour(ops)
    if not questions:
        return 0
    reponses = client.resoudre(questions, modele=modele)
    return appliquer_reponses(ops, reponses)


def resolver_depuis_client(client: Optional[ClientIA], *, modele: str | None = None):
    """Adapte un `ClientIA` au paramètre `resolver` déjà accepté par `coder()`
    (résolution unitaire d'un fournisseur inconnu). Renvoie None sans client, ce
    qui laisse `coder()` en mode purement déterministe."""
    if client is None:
        return None

    def _resolver(libelle: str) -> Optional[dict]:
        q = [{"id": "u", "libelle": libelle, "montant": 0.0, "sens": "D",
              "options": [], "contexte": "Fournisseur inconnu"}]
        rep = client.resoudre(q, modele=modele) or []
        for r in rep:
            if r.get("compte"):
                return {"compte": str(r["compte"]), "note": r.get("raison", "")}
        return None

    return _resolver


# ---------------------------------------------------------------------------
# A. OCR -> objets Facture (le montant ne sert qu'au rapprochement)
# ---------------------------------------------------------------------------

def _d(v):
    if not v:
        return None
    if isinstance(v, date):
        return v
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(str(v).strip(), fmt).date()
        except ValueError:
            continue
    return None


def facture_depuis_ocr(brut: dict) -> Facture:
    """Construit une `Facture` à partir d'un dict conforme au contrat A.
    La catégorie et sa confiance sont conservées : elles tracent POURQUOI la
    pièce a été retenue (auditable), et `sens` en découle (avoir -> inverse)."""
    return Facture(
        fournisseur=str(brut.get("fournisseur") or "").strip(),
        date=_d(brut.get("date")),
        ttc=float(brut.get("ttc") or 0.0),
        tva=float(brut.get("tva") or 0.0),
        ht=float(brut.get("ht") or 0.0),
        numero=str(brut.get("numero") or ""),
        confiance_ocr=float(brut.get("confiance") or 0.0),
        categorie=str(brut.get("categorie") or "").strip().lower(),
        confiance_classement=float(brut.get("confiance_classement") or 0.0),
    )


def factures_depuis_ocr(bruts) -> tuple[list, list]:
    """Tri d'entrée : `(factures, rejets)`.

    Seules les pièces classées comptables, complètes et cohérentes (HT+TVA=TTC)
    deviennent des `Facture`. Tout le reste sort dans `rejets` AVEC SON MOTIF —
    aucune pièce n'est écartée en silence. C'est ici qu'un devis est arrêté."""
    from .classement import trier
    retenus, rejets = trier(bruts)
    return [facture_depuis_ocr(b) for b in retenus], rejets


def lire_factures(chemins, client: Optional[ClientIA], *, modele: str | None = None) -> list:
    """Orchestration A : lit chaque fichier via le client et renvoie des
    `Facture`. Sans client, lève (rien à inventer) — voir ocr.lire_facture."""
    if client is None:
        from .ocr import lire_facture
        # délègue à l'interface stub, qui lève NotImplementedError explicite
        out = []
        for c in chemins:
            out.extend(lire_facture(c))
        return out
    out = []
    for c in chemins:
        for brut in client.lire_facture(c, modele=modele):
            out.append(facture_depuis_ocr(brut))
    return out
