"""Revue analytique — contrôles de cohérence N vs N-1 (le travail à valeur
ajoutée du collaborateur, automatisé).

Compare l'exercice en cours au FEC N-1 et signale ce qui cloche AVANT la clôture :
  - une charge récurrente de l'an dernier a disparu (abonnement oublié ?) ;
  - un montant très différent de l'an dernier (charge qui double, erreur) ;
  - un doublon d'écriture ;
  - des loyers incomplets sur l'année.

Ne décide rien : produit des **anomalies** à regarder (info / attention / alerte).
Tout est déterministe (aucune IA) et le montant n'est jamais corrigé, seulement
signalé — c'est l'humain qui tranche.
"""
from __future__ import annotations

from .normalize import normalize
from .dico import _codable, _est_a_nouveau
from .rapprochement import doublons


def reference(lignes_fec) -> dict:
    """Repères N-1 par libellé normalisé : nb d'occurrences (≈ récurrence),
    total, sens dominant, comptes utilisés. Exclut les à-nouveaux et les comptes
    non codables (amortissements...)."""
    ref: dict[str, dict] = {}
    for l in lignes_fec:
        if not l.libelle or not _codable(l.compte) or _est_a_nouveau(l):
            continue
        cle = normalize(l.libelle)
        if not cle:
            continue
        e = ref.setdefault(cle, {"count": 0, "total": 0.0, "comptes": set(), "sens": l.sens})
        e["count"] += 1
        e["total"] += l.montant
        e["comptes"].add(l.compte)
    for e in ref.values():
        e["moyenne"] = e["total"] / e["count"] if e["count"] else 0.0
    return ref


def _anomalie(type_, gravite, message, cle=""):
    return {"type": type_, "gravite": gravite, "message": message, "cle": cle}


def revue_analytique(ops, lignes_fec_n1, *, recurrence_min=6, ecart_rel=0.4,
                     ecart_min=200.0, mois_attendus=12):
    """Compare les opérations de l'exercice au FEC N-1. Retourne une liste
    d'anomalies triées (alerte d'abord)."""
    ref = reference(lignes_fec_n1)

    # agrégats de l'exercice en cours, par libellé normalisé
    cur: dict[str, dict] = {}
    for o in ops:
        cle = normalize(o.libelle)
        e = cur.setdefault(cle, {"count": 0, "total": 0.0})
        e["count"] += 1
        e["total"] += o.montant

    anomalies = []

    # 1) charge récurrente N-1 absente cette année
    for cle, e in ref.items():
        if e["count"] >= recurrence_min and cle and cle not in cur:
            anomalies.append(_anomalie(
                "recurrent_manquant", "attention",
                "« %s » apparaissait %d fois en N-1 (%s) et est absent cette année — "
                "abonnement/charge oublié ?" % (cle, e["count"], ", ".join(sorted(e["comptes"]))),
                cle))

    # 2) montant très différent de N-1 (même libellé présent des deux côtés)
    for cle, e in cur.items():
        r = ref.get(cle)
        if not r or not cle:
            continue
        diff = e["total"] - r["total"]
        if abs(diff) >= ecart_min and r["total"] and abs(diff) / r["total"] >= ecart_rel:
            sens = "hausse" if diff > 0 else "baisse"
            anomalies.append(_anomalie(
                "ecart_montant", "attention",
                "« %s » : %.2f € cette année contre %.2f € en N-1 (%s de %.0f %%) — à vérifier."
                % (cle, e["total"], r["total"], sens, 100 * abs(diff) / r["total"]),
                cle))

    # 3) doublons d'écriture (même date + montant + compte + libellé)
    for d in doublons(ops):
        anomalies.append(_anomalie(
            "doublon", "alerte",
            "Doublon probable : %s le %s pour %.2f € (compte %s)."
            % (d.libelle, d.date, d.montant, d.compte or "?"),
            normalize(d.libelle)))

    # 4) loyers incomplets sur l'année
    n_loyers = sum(1 for o in ops if o.sens == "C" and (o.compte or "").startswith("706"))
    if 0 < n_loyers < mois_attendus:
        anomalies.append(_anomalie(
            "loyers_incomplets", "attention",
            "%d encaissements de loyer sur %d attendus — vérifier les mois manquants."
            % (n_loyers, mois_attendus), "706"))

    ordre = {"alerte": 0, "attention": 1, "info": 2}
    anomalies.sort(key=lambda a: ordre.get(a["gravite"], 3))
    return anomalies
