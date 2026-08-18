"""Orchestrateur bout-en-bout — le point d'entrée unique du traitement.

`traiter_dossier(...)` enchaîne tout ce qui est déterministe, et n'appelle l'IA
qu'une fois sur le résidu ambigu :

  codage (règles + dico) -> adaptation au plan du dossier -> rapprochement
  facture/banque -> résolution IA du résidu (1 appel) -> export Quadra
  + liste des pièces à réclamer.

Renvoie un dict de résultats prêt pour l'écran de validation (on n'y montre que
`a_trancher`, `a_reclamer`, `ecarts`) et pour l'import (`quadra`). L'humain ne
voit que ce qui a besoin d'une décision ; le reste est déjà tranché.

`ingerer(...)` fait l'amont : ne lit/‌OCR que les pièces NEUVES d'une source
(Drive/dossier), via le manifeste d'idempotence.
"""
from __future__ import annotations

from .codage import coder
from .rapprochement import rapprocher, manquants
from .quadra import to_quadratus
from .ia import resoudre_residu, facture_depuis_ocr
from .sources import pieces_neuves


def ingerer(source, manifeste, client_ia, *, modele=None):
    """Amont : OCR des seules pièces NEUVES de la source, marquées ensuite dans
    le manifeste (on ne re-paye jamais l'OCR). Renvoie la liste des `Facture`.
    Sans client IA -> lève (rien à inventer côté OCR)."""
    neuves = pieces_neuves(source, manifeste)
    factures = []
    for p in neuves:
        chemin = source.ouvrir(p)
        for brut in client_ia.lire_facture(chemin, modele=modele):
            factures.append(facture_depuis_ocr(brut))
        manifeste.marquer(p.empreinte, p.nom)
    return factures


def traiter_dossier(factures, ops_banque, dico, *, client_ia=None, resolver=None,
                    assujetti_tva=False, avec_banque=True,
                    compte_banque="512", journal=None, source_quadra="_IMP"):
    """Traite un dossier de bout en bout. `factures` = pièces lues (OCR) ;
    `ops_banque` = lignes du relevé (ignoré si avec_banque=False)."""
    from .rapprochement import operations_od_factures
    od_ops = []
    if avec_banque:
        ops = list(ops_banque or [])
        for o in ops:
            coder(o, dico, resolver, assujetti_tva=assujetti_tva)
        rapprocher(ops, list(factures or []))
        a_reclamer = manquants(ops)
        # facture PAYÉE mais absente du relevé -> payée en perso -> écriture d'OD,
        # contrepartie 108 (compte de l'exploitant).
        orphelines = [f for f in (factures or []) if getattr(f, "op", None) is None]
        od_ops = operations_od_factures(orphelines, dico, resolver)
        if od_ops and client_ia is not None:
            resoudre_residu(od_ops, client_ia)
    else:
        ops = operations_od_factures(list(factures or []), dico, resolver)
        if assujetti_tva:
            for o in ops:
                coder(o, dico, resolver, assujetti_tva=True)
        a_reclamer = []

    n_ia = resoudre_residu(ops, client_ia) if client_ia is not None else 0

    quadra = to_quadratus(ops, avec_banque=avec_banque, compte_banque=compte_banque,
                          journal=journal, source=source_quadra)
    # journal d'OD (factures payées hors banque) : ASCII ferme, contrepartie 108
    od_ascii = to_quadratus(od_ops, avec_banque=False, journal="OD",
                            source=source_quadra) if od_ops else ""
    tous = list(ops) + list(od_ops)
    return {
        "operations": ops,
        "operations_od": od_ops,           # factures payées en perso (ctp 108)
        "nb_factures": len(factures or []),
        "a_trancher": [o for o in tous if o.a_revoir],
        "a_reclamer": a_reclamer,
        "ecarts": [o for o in ops if getattr(o, "ecart", False)],
        "residu_resolu_par_ia": n_ia,
        "quadra": quadra,
        "od_ascii": od_ascii,              # OD 108 (ASCII) — à importer tel quel
    }


def traiter_lot(dossiers):
    """Traite plusieurs dossiers d'affilée (ex. tous les dossiers du cabinet, la
    nuit) et produit un **tableau de bord de pilotage**.

    `dossiers` = liste de dicts : {nom, factures, ops_banque, dico, ...} (les
    autres clés sont passées telles quelles à `traiter_dossier`).

    Renvoie {resultats, tableau_de_bord, totaux}. Le tableau de bord donne, par
    dossier : statut (prêt / à valider / en attente de pièces), taux d'auto-codage,
    nb à trancher / à réclamer, et une **estimation** du coût IA — la vue dont
    Paul a besoin pour piloter et chiffrer la marge."""
    resultats, tableau = {}, []
    tot = {"dossiers": 0, "operations": 0, "factures": 0, "a_trancher": 0,
           "a_reclamer": 0, "cout_ia_estime_eur": 0.0, "prets": 0}
    for d in dossiers:
        d = dict(d)
        nom = d.pop("nom", "sans-nom")
        factures = d.pop("factures", [])
        ops_banque = d.pop("ops_banque", None)
        dico = d.pop("dico")
        res = traiter_dossier(factures, ops_banque, dico, **d)
        resultats[nom] = res

        nb_ops = len(res["operations"])
        nb_tr, nb_rc = len(res["a_trancher"]), len(res["a_reclamer"])
        taux = round(100 * (1 - nb_tr / nb_ops)) if nb_ops else 100
        if nb_rc:
            statut = "en attente de pièces"
        elif nb_tr or res["ecarts"]:
            statut = "à valider"
        else:
            statut = "prêt"
        # estimation grossière : ~0,8 c / facture OCR + ~0,2 c / item résolu par l'IA
        cout = round(0.008 * res["nb_factures"] + 0.002 * res["residu_resolu_par_ia"], 3)

        tableau.append({
            "dossier": nom, "operations": nb_ops, "factures": res["nb_factures"],
            "a_trancher": nb_tr, "a_reclamer": nb_rc, "taux_auto_pct": taux,
            "statut": statut, "cout_ia_estime_eur": cout,
        })
        tot["dossiers"] += 1
        tot["operations"] += nb_ops
        tot["factures"] += res["nb_factures"]
        tot["a_trancher"] += nb_tr
        tot["a_reclamer"] += nb_rc
        tot["cout_ia_estime_eur"] += cout
        tot["prets"] += (statut == "prêt")
    tot["cout_ia_estime_eur"] = round(tot["cout_ia_estime_eur"], 2)
    return {"resultats": resultats, "tableau_de_bord": tableau, "totaux": tot}
