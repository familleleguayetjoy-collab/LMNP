#!/usr/bin/env python3
"""Moteur de traitement d'un dossier — tout ce qui touche à un montant.

    python3 saisio.py dossier.json                      # traiter
    python3 saisio.py dossier.json --sortie ./resultats # écrire les fichiers

La règle qui gouverne ce fichier : **les montants sont du code, jamais de l'IA.**
Le modèle lit les pièces et propose ; il ne calcule rien, ne rapproche rien, ne
date rien. Tout ce qui suit est déterministe et rejouable : mêmes entrées, même
sortie, à la virgule.

Ce que le script fait, dans l'ordre :

  1. **Contrôle du relevé.** Somme des mouvements = solde final − solde initial ?
     Si la transcription du relevé est fausse, tout le reste l'est aussi, et
     personne ne le verra en relisant des écritures. On s'arrête là.
  2. **Codage** de chaque ligne (dictionnaire du FEC N-1, puis règles).
  3. **Rapprochement** facture / mouvement : c'est le mouvement qui date
     l'écriture, jamais la facture.
  4. **Factures payées hors banque** → journal d'OD, contrepartie 108, datée du
     jour du règlement porté par la pièce. Sans date de règlement : rien.
  5. **Sortie** : ce qui est tranché, ce qui ne l'est pas, ce qui manque, et le
     fichier Quadratus.

Format d'entrée — un seul fichier JSON :

    {
      "dossier": "LMNP POLO TEST",
      "exercice": 2026,
      "avec_banque": true,
      "assujetti_tva": false,
      "compte_banque": "512000",
      "releve": {"solde_initial": 1204.55, "solde_final": 2890.12},
      "operations": [
        {"date": "2026-08-03", "libelle": "EDF ENERGIE", "montant": 57.79, "sens": "D"}
      ],
      "factures": [
        {"fournisseur": "EDF", "date": "2026-08-01", "ttc": 57.79,
         "ht": 48.16, "tva": 9.63, "fichier": "edf.pdf",
         "payee": true, "date_reglement": "2026-08-03"}
      ],
      "fec_n1": "chemin/vers/fec.txt",
      "decisions": {"OP007": "615000"}
    }

`sens` : "D" = dépense (sortie de banque), "C" = recette. `montant` toujours
positif. `decisions` associe l'identifiant stable d'une ligne au compte choisi
par le collaborateur — c'est ainsi qu'on referme une question sans retoucher
le reste : on relance le script, rien d'autre ne bouge.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from s2a_lmnp import (Operation, Facture, construire, parse_fec, Dictionnaire,
                      traiter_dossier, to_quadratus, verifier_equilibre,
                      doublons_factures, cents)

TOLERANCE_SOLDE = 0.01          # un centime : au-delà, la transcription a un trou


def _date(v):
    if not v:
        return None
    if isinstance(v, datetime.date):
        return v
    return datetime.datetime.strptime(str(v).strip()[:10], "%Y-%m-%d").date()


# ---------------------------------------------------------------------------
def controler_releve(d) -> dict:
    """Somme des mouvements contre les soldes annoncés par le relevé.

    C'est le seul garde-fou possible quand le relevé est un PDF recopié à la
    main ou par un modèle : une ligne oubliée, un chiffre inversé, et le
    contrôle tombe. Sans soldes fournis, on le dit — on ne fait pas semblant
    d'avoir vérifié."""
    if not d.get("avec_banque", True):
        return {"fait": False, "mouvements": 0.0,
                "message": "dossier sans banque : il n'y a pas de relevé à "
                           "contrôler, toutes les pièces partent en OD 108."}
    rel = d.get("releve") or {}
    si, sf = rel.get("solde_initial"), rel.get("solde_final")
    mouv = sum((1 if o.get("sens") == "C" else -1) * float(o.get("montant") or 0)
               for o in d.get("operations") or [])
    if si is None or sf is None:
        return {"fait": False, "mouvements": round(mouv, 2),
                "message": "soldes du relevé non fournis : la transcription "
                           "n'a PAS été contrôlée. Ajoutez solde_initial et "
                           "solde_final pour qu'elle le soit."}
    attendu = round(float(sf) - float(si), 2)
    ecart = round(mouv - attendu, 2)
    return {"fait": True, "mouvements": round(mouv, 2), "attendu": attendu,
            "ecart": ecart, "ok": abs(ecart) <= TOLERANCE_SOLDE,
            "message": ("relevé équilibré" if abs(ecart) <= TOLERANCE_SOLDE else
                        "ÉCART DE %.2f € entre la somme des mouvements (%.2f) "
                        "et la variation de solde (%.2f) : il manque ou il y a "
                        "en trop une ou plusieurs lignes."
                        % (ecart, mouv, attendu))}


def charger(d):
    ops = []
    for i, o in enumerate(d.get("operations") or []):
        op = Operation(date=_date(o["date"]), libelle=str(o.get("libelle") or ""),
                       montant=abs(float(o["montant"])),
                       sens=(o.get("sens") or "D").upper()[:1])
        op.cle = "OP%03d" % (i + 1)
        ops.append(op)
    facs = []
    for i, f in enumerate(d.get("factures") or []):
        fa = Facture(fournisseur=str(f.get("fournisseur") or ""),
                     date=_date(f.get("date")), ttc=float(f.get("ttc") or 0),
                     tva=float(f.get("tva") or 0), ht=float(f.get("ht") or 0),
                     fichier=str(f.get("fichier") or ""),
                     numero=str(f.get("numero") or ""),
                     categorie=str(f.get("categorie") or "facture_achat"),
                     date_reglement=_date(f.get("date_reglement")),
                     payee=bool(f.get("payee")) or bool(f.get("date_reglement")))
        fa.cle = "FA%03d" % (i + 1)
        facs.append(fa)
    return ops, facs


def dictionnaire(d) -> Dictionnaire:
    chemin = d.get("fec_n1") or ""
    if not chemin:
        return Dictionnaire()
    with open(chemin, "rb") as f:
        return construire(parse_fec(f.read()))


def appliquer_decisions(ops, decisions) -> list:
    """Le collaborateur tranche : sa décision l'emporte, y compris sur un compte
    absent des options proposées — c'est le cas du compte saisi à la main, et
    c'est lui l'autorité, pas le modèle. On refuse seulement ce qui ne ressemble
    pas à un compte du plan, et on ne touche ni au montant ni au sens."""
    par_cle = {getattr(o, "cle", ""): o for o in ops}
    faits = []
    for cle, compte in (decisions or {}).items():
        o = par_cle.get(cle)
        compte = str(compte or "").strip()
        if o is None:
            faits.append({"cle": cle, "etat": "ligne inconnue"})
            continue
        if not compte.isdigit() or not (3 <= len(compte) <= 8):
            faits.append({"cle": cle, "etat": "compte invalide : %s" % compte})
            continue
        o.compte, o.origine, o.confiance = compte, "humain", 1.0
        o.a_revoir, o.motif, o.a_confirmer = False, "", ""
        faits.append({"cle": cle, "etat": "imputé en %s" % compte})
    return faits


def traiter(d) -> dict:
    ctrl = controler_releve(d)
    ops, facs = charger(d)
    avec_banque = bool(d.get("avec_banque", True))
    res = traiter_dossier(
        facs, ops, dictionnaire(d), client_ia=None,
        assujetti_tva=bool(d.get("assujetti_tva")),
        avec_banque=avec_banque,
        compte_banque=str(d.get("compte_banque") or "512000"),
        source_quadra=str(d.get("source") or "_IMP"))

    # Les écritures d'OD naissent dans le moteur, elles n'ont donc pas encore
    # d'identifiant. Sans lui, le collaborateur ne pourrait pas trancher une
    # facture payée hors banque — et c'est justement le cas qui demande le plus
    # souvent un arbitrage. L'ordre est déterministe : même dossier, mêmes clés.
    for i, o in enumerate(res["operations_od"]):
        o.cle = "OD%03d" % (i + 1)

    # Les décisions s'appliquent APRÈS le codage : elles corrigent ce que le
    # moteur a proposé, elles ne le devancent pas. On réécrit donc le fichier.
    faits = appliquer_decisions(res["operations"] + res["operations_od"],
                                d.get("decisions"))
    if faits:
        res["quadra"] = to_quadratus(
            res["operations"], avec_banque=avec_banque,
            compte_banque=str(d.get("compte_banque") or "512000"),
            source=str(d.get("source") or "_IMP"))
        if res["operations_od"]:
            res["od_ascii"] = to_quadratus(res["operations_od"],
                                           avec_banque=False, journal="OD",
                                           source=str(d.get("source") or "_IMP"))
        tous = res["operations"] + res["operations_od"]
        res["a_trancher"] = [o for o in tous if o.a_revoir]

    # Factures sans aucun règlement identifié : en trésorerie, aucune écriture.
    # Sans banque, la question ne se pose pas : il n'y a pas de relevé pour
    # contredire les pièces, elles produisent toutes leur OD.
    sans_reglement = [f for f in facs
                      if getattr(f, "op", None) is None and not f.date_reglement
                      and not f.payee] if avec_banque else []
    return {"controle_releve": ctrl, "resultat": res, "decisions": faits,
            "factures": facs, "sans_reglement": sans_reglement}


# ---------------------------------------------------------------------------
def rendre(d, out) -> dict:
    """Vue lisible : ce qui est tranché, ce qui attend une décision, ce qui
    manque. C'est ce tableau que le collaborateur regarde, pas le JSON brut."""
    res, ctrl = out["resultat"], out["controle_releve"]
    a_trancher = []
    for o in res["a_trancher"]:
        a_trancher.append({
            "cle": getattr(o, "cle", ""),
            "date": o.date.strftime("%d/%m/%Y") if o.date else "",
            "libelle": o.libelle, "montant": round(o.montant, 2), "sens": o.sens,
            "propose": o.compte or "", "options": list(o.options or []),
            "motif": o.motif or o.a_confirmer or "",
            "piece": (o.facture.fichier if o.facture else ""),
        })
    return {
        "dossier": d.get("dossier", ""),
        "exercice": d.get("exercice"),
        "controle_releve": ctrl,
        "compte": {
            "operations": len(res["operations"]),
            "od_hors_banque": len(res["operations_od"]),
            "factures_lues": res["nb_factures"],
            "a_trancher": len(res["a_trancher"]),
            "a_reclamer": len(res["a_reclamer"]),
            "ecarts": len(res["ecarts"]),
            "sans_reglement": len(out["sans_reglement"]),
        },
        "a_trancher": a_trancher,
        "a_reclamer": [{"date": o.date.strftime("%d/%m/%Y") if o.date else "",
                        "libelle": o.libelle, "montant": round(o.montant, 2)}
                       for o in res["a_reclamer"]],
        "ecarts": [{"libelle": o.libelle, "banque": round(o.montant, 2),
                    "facture": round(o.facture.ttc, 2) if o.facture else None}
                   for o in res["ecarts"]],
        "sans_reglement": [{"fournisseur": f.fournisseur, "ttc": round(f.ttc, 2),
                            "date": f.date.strftime("%d/%m/%Y") if f.date else "",
                            "fichier": f.fichier}
                           for f in out["sans_reglement"]],
        "doublons": [{"a": a.fichier or a.fournisseur, "b": b.fichier or b.fournisseur,
                      "ttc": round(a.ttc, 2)}
                     for a, b in doublons_factures(out["factures"])],
        "decisions_appliquees": out["decisions"],
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dossier_json")
    ap.add_argument("--sortie", default="", help="dossier où écrire les fichiers")
    ap.add_argument("--forcer", action="store_true",
                    help="produire le fichier malgré un relevé déséquilibré")
    a = ap.parse_args()

    with open(a.dossier_json, encoding="utf-8") as f:
        d = json.load(f)

    ctrl = controler_releve(d)
    if ctrl.get("fait") and not ctrl["ok"] and not a.forcer:
        print(json.dumps({"arret": "relevé déséquilibré",
                          "controle_releve": ctrl,
                          "quoi_faire": "reprenez la transcription du relevé "
                                        "avant toute écriture : une ligne "
                                        "manquante ne se voit plus une fois "
                                        "les écritures passées."},
                         ensure_ascii=False, indent=2))
        return 2

    out = traiter(d)
    vue = rendre(d, out)
    res = out["resultat"]

    if a.sortie:
        os.makedirs(a.sortie, exist_ok=True)
        base = "".join(c if c.isalnum() else "_" for c in str(d.get("dossier", "dossier")))
        ecrits = []
        if res["quadra"]:
            p = os.path.join(a.sortie, base + "_BQ.txt")
            with open(p, "w", encoding="cp1252", errors="replace", newline="") as f:
                f.write(res["quadra"])
            ecrits.append({"fichier": p, "lignes": res["quadra"].count("\r\n"),
                           "journal": "BQ" if d.get("avec_banque", True) else "OD"})
        if res["od_ascii"]:
            p = os.path.join(a.sortie, base + "_OD.txt")
            with open(p, "w", encoding="cp1252", errors="replace", newline="") as f:
                f.write(res["od_ascii"])
            ecrits.append({"fichier": p, "lignes": res["od_ascii"].count("\r\n"),
                           "journal": "OD", "contrepartie": "108"})
        vue["fichiers"] = ecrits
        p = os.path.join(a.sortie, base + "_rapport.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(vue, f, ensure_ascii=False, indent=2)

    eq = verifier_equilibre(res["quadra"]) if res["quadra"] else None
    vue["equilibre_quadra"] = eq
    print(json.dumps(vue, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
