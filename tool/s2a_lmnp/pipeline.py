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
    if avec_banque:
        ops = list(ops_banque or [])
        for o in ops:
            coder(o, dico, resolver, assujetti_tva=assujetti_tva)
        rapprocher(ops, list(factures or []))
        a_reclamer = manquants(ops)
    else:
        from .rapprochement import operations_od_factures
        ops = operations_od_factures(list(factures or []), dico, resolver)
        if assujetti_tva:
            for o in ops:
                coder(o, dico, resolver, assujetti_tva=True)
        a_reclamer = []

    n_ia = resoudre_residu(ops, client_ia) if client_ia is not None else 0

    quadra = to_quadratus(ops, avec_banque=avec_banque, compte_banque=compte_banque,
                          journal=journal, source=source_quadra)
    return {
        "operations": ops,
        "a_trancher": [o for o in ops if o.a_revoir],
        "a_reclamer": a_reclamer,
        "ecarts": [o for o in ops if getattr(o, "ecart", False)],
        "residu_resolu_par_ia": n_ia,
        "quadra": quadra,
    }
