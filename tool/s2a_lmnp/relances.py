"""Relance client des pièces manquantes — avec VERROU DE CERTITUDE.

Objectif : automatiser la relance des justificatifs manquants, mais ne relancer
QUE ce dont on est sûr. Une relance à tort agace le client et fait perdre en
crédibilité — donc on sépare :

  - `certain`   : dépense justifiable, matérielle, sans facture, ET dont on sait
                  qu'un justificatif est attendu (fournisseur déjà vu en N-1, ou
                  poste qui appelle toujours une facture). -> relance automatique.
  - `a_verifier`: dépense sans facture mais fournisseur inconnu / ponctuel : peut
                  être normal, ou la pièce peut juste être en retard. -> l'humain
                  regarde avant de relancer.

On ne GÉNÈRE que le brouillon ; l'envoi passe par un connecteur mail (déploiement).
"""
from __future__ import annotations

from .normalize import normalize
from .rapprochement import manquants


def preparer_relances(ops, reference_n1=None, *, seuil=150.0, client="", cabinet="S2A"):
    """Répartit les dépenses sans justificatif en 'certain' / 'a_verifier' et
    prépare le brouillon de mail pour les certaines. `reference_n1` = dict issu
    de `controles.reference` (fournisseurs vus l'an dernier)."""
    ref = reference_n1 or {}
    certain, a_verifier = [], []
    for o in manquants(ops, seuil):
        connu_n1 = normalize(o.libelle) in ref
        # on est SÛR de relancer si le fournisseur avait déjà un justificatif en
        # N-1 (récurrent), ou si le montant est important (matérialité forte).
        if connu_n1 or o.montant >= 3 * seuil:
            certain.append(o)
        else:
            a_verifier.append(o)

    return {
        "certain": certain,
        "a_verifier": a_verifier,
        "brouillon": _brouillon(certain, client, cabinet) if certain else "",
    }


def _brouillon(ops, client, cabinet):
    lignes = "\n".join(
        "  - %s  %s  %.2f €" % (o.date.strftime("%d/%m/%Y") if o.date else "date ?",
                                o.libelle, o.montant)
        for o in sorted(ops, key=lambda o: -o.montant)
    )
    dest = (" " + client) if client else ""
    return (
        "Bonjour%s,\n\n"
        "Dans le cadre de la préparation de votre dossier, il nous manque le ou les "
        "justificatif(s) correspondant aux dépenses suivantes, relevées sur votre "
        "compte :\n\n"
        "%s\n\n"
        "Pourriez-vous nous transmettre ces factures (ou nous préciser leur nature) "
        "afin que nous puissions finaliser votre comptabilité ?\n\n"
        "Vous pouvez simplement répondre à ce message en joignant les documents.\n\n"
        "Bien cordialement,\n"
        "%s"
    ) % (dest, lignes, cabinet)
