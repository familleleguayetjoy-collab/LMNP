#!/usr/bin/env python3
"""Traiter un dossier client — la commande de tous les jours.

    python3 tool/traiter.py --client "LMNP POLO TEST" --exercice 2026
    python3 tool/traiter.py --client "LMNP POLO TEST" --exercice 2026 --deposer

Ce que fait la commande, dans l'ordre : elle liste les pièces NEUVES du dossier
d'entrée du client, les lit, écarte ce qui n'est pas comptable en disant
pourquoi, calcule où chaque pièce doit être rangée, et — avec `--deposer` — les
dépose dans le dossier de sortie du Drive.

**Sans `--deposer`, rien n'est écrit nulle part.** C'est le mode par défaut :
un premier essai sur un vrai dossier ne peut rien salir. La commande affiche
alors exactement ce qu'elle ferait.

Ce qu'elle ne fait PAS, et il faut le savoir avant de s'en servir : elle ne
produit **aucune écriture comptable**. En comptabilité de trésorerie, c'est le
relevé bancaire qui définit ce qui est comptabilisé et à quelle date ; tant que
le relevé n'est pas lu, produire des écritures depuis les seules factures
donnerait des dates fausses et des charges qui n'ont peut-être jamais été
payées. Le moteur sait faire (`traiter_dossier`), il lui manque le relevé.

Le manifeste garantit qu'une pièce déjà lue n'est jamais relue : il vit dans le
dossier personnel de l'utilisateur, pas dans le projet, pour qu'une mise à jour
de l'outil ne fasse pas repayer tout l'OCR. `--refaire` passe outre — utile en
phase de calage, et l'OCR est alors repayé.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from reglages import charger as charger_reglages

FICHIER_REGLAGES = charger_reglages()

VERT, ROUGE, JAUNE, GRIS, FIN = "\033[32m", "\033[31m", "\033[33m", "\033[90m", "\033[0m"

# Le manifeste hors du projet : `maj.ps1` recopie le dépôt par-dessus l'existant,
# et une réinstallation propre effacerait un manifeste rangé dans le projet — on
# repaierait alors l'OCR de tout l'historique du client.
DOSSIER_ETAT = os.path.join(os.path.expanduser("~"), ".saisio", "manifestes")


def ligne(sym, coul, t, d=""):
    print("  %s%s%s %s %s%s%s" % (coul, sym, FIN, t, GRIS, d, FIN))


def ok(t, d=""):
    ligne("✓", VERT, t, d)


def stop(t, quoi_faire):
    ligne("✗", ROUGE, t)
    print("    %s→ %s%s" % (JAUNE, quoi_faire, FIN))
    return 1


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--client", required=True,
                    help="nom du sous-dossier client dans le dossier d'entrée")
    ap.add_argument("--exercice", type=int, required=True,
                    help="millésime de l'exercice (année de clôture)")
    ap.add_argument("--sous-dossier", default="",
                    help="chemin sous le client, par défaut l'année de l'exercice")
    ap.add_argument("--deposer", action="store_true",
                    help="déposer réellement dans le Drive de sortie "
                         "(sans ce drapeau, rien n'est écrit)")
    ap.add_argument("--limite", type=int, default=0,
                    help="ne lire que N pièces (0 = toutes)")
    ap.add_argument("--refaire", action="store_true",
                    help="rejouer des pièces déjà traitées (l'OCR est repayé)")
    ap.add_argument("--entree", default=os.environ.get("SAISIO_DRIVE_ENTREE", ""))
    ap.add_argument("--sortie", default=os.environ.get("SAISIO_DRIVE_SORTIE", ""))
    ap.add_argument("--cles", default=os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", ""))
    a = ap.parse_args()

    from s2a_lmnp import (DriveGoogle, DepotDrive, deposer_plan, resoudre_chemin,
                          Manifeste, pieces_neuves, ingerer, ranger,
                          resume_rangement, Exercice, ClientAnthropic)

    print("\nSAISIO — %s, exercice %d" % (a.client, a.exercice))
    print("=" * 54)
    if FICHIER_REGLAGES:
        print("%sréglages lus dans %s%s" % (GRIS, FICHIER_REGLAGES, FIN))
    if not a.deposer:
        print("%sessai à blanc : RIEN ne sera écrit. Ajoutez --deposer pour "
              "déposer réellement.%s" % (JAUNE, FIN))

    if not a.entree:
        return stop("dossier d'entrée inconnu",
                    "renseignez SAISIO_DRIVE_ENTREE dans saisio.env")

    # -- 0. le dépôt est-il possible ? AVANT de payer le moindre OCR ---------
    # L'ordre compte : une lecture réussie marque les pièces dans le manifeste.
    # Échouer sur le dossier de sortie APRÈS la lecture laissait des pièces
    # payées, marquées traitées, et jamais déposées — il fallait alors --refaire
    # pour les rattraper. On vérifie donc d'abord, on lit ensuite.
    depot = None
    if a.deposer:
        if not a.sortie:
            return stop("dossier de sortie inconnu",
                        "renseignez SAISIO_DRIVE_SORTIE dans saisio.env "
                        "(l'identifiant est dans l'URL du dossier de sortie)")
        try:
            depot = DepotDrive(a.sortie, a.cles)
            v = depot.verifier()
        except Exception as e:
            return stop("Drive de sortie inaccessible",
                        "le dossier est-il partagé au compte de service "
                        "(adresse en …iam.gserviceaccount.com) ? %s" % e)
        if not v["ok"]:
            titre = ("écriture refusée sur « %s »" % v["dossier"]
                     if not v["ecriture"] else
                     "« %s » est dans un Mon Drive, pas dans un Drive partagé"
                     % v["dossier"])
            return stop(titre, v["conseil"])
        ok("dossier de sortie", "« %s », Drive partagé, accessible en écriture"
           % v["dossier"])

    # -- 1. le dossier du client -------------------------------------------
    try:
        racine = DriveGoogle(a.entree, a.cles)
    except Exception as e:
        return stop("Drive d'entrée indisponible", str(e))
    sous = a.sous_dossier or str(a.exercice)
    chemin_client = "%s/%s" % (a.client, sous)
    id_client = resoudre_chemin(racine, chemin_client)
    if not id_client:
        return stop("dossier « %s » introuvable dans le Drive d'entrée" % chemin_client,
                    "vérifiez l'orthographe du client et qu'un sous-dossier "
                    "« %s » existe (ou passez --sous-dossier)" % sous)
    source = DriveGoogle(id_client, a.cles)
    ok("dossier d'entrée", chemin_client)

    # -- 2. ce qui est neuf -------------------------------------------------
    os.makedirs(DOSSIER_ETAT, exist_ok=True)
    cle_etat = "".join(c if c.isalnum() else "_" for c in chemin_client)
    man = Manifeste(os.path.join(DOSSIER_ETAT, cle_etat + ".json"))
    if a.refaire:
        neuves = source.lister()
        print("  %s⚠ --refaire : les pièces déjà lues sont relues, et l'OCR est "
              "repayé.%s" % (JAUNE, FIN))
    else:
        neuves = pieces_neuves(source, man)
    if a.limite:
        neuves = neuves[:a.limite]
    if not neuves:
        ok("aucune pièce neuve", "tout a déjà été traité — --refaire pour rejouer")
        print()
        return 0
    ok("%d pièce(s) %s" % (len(neuves), "à rejouer" if a.refaire else "neuve(s)"),
       " · ".join(p.nom for p in neuves[:4]) + (" …" if len(neuves) > 4 else ""))

    # -- 3. lecture et classement ------------------------------------------
    try:
        client = ClientAnthropic()
    except ImportError:
        return stop("bibliothèque anthropic absente", "pip install anthropic")
    except Exception as e:
        return stop("clé API indisponible",
                    "lancez d'abord : python tool/verifier_branchement.py --etape cle (%s)" % e)
    try:
        factures, rejets = ingerer(source, man, client, pieces=neuves)
    except Exception as e:
        return stop("lecture des pièces", str(e))
    ok("classement", "%d retenue(s), %d écartée(s)" % (len(factures), len(rejets)))
    for r in rejets:
        print("    %s· %s : %s%s" % (GRIS, r.get("fichier", "?"),
                                     r.get("motif", ""), FIN))

    # -- 4. plan de rangement ----------------------------------------------
    # `racine=""` : le plan est RELATIF au dossier de sortie, puisqu'on dépose
    # dedans. Avec la racine, on recréerait « Documents générés par
    # l'application » à l'intérieur de « Documents générés par l'application ».
    plan = ranger(factures, rejets, racine="", exercice=Exercice.civil(a.exercice))
    ok("plan de rangement", "%d dossier(s)" % len(plan))
    for l in resume_rangement(plan):
        est = (" — mois estimé, pas de date de règlement sur la pièce"
               if l["estimees"] else "")
        print("    %s%s/%s → %d pièce(s)%s%s"
              % (GRIS, a.client, l["chemin"], l["pieces"], est, FIN))

    # -- 5. dépôt ------------------------------------------------------------
    if depot is not None:
        from s2a_lmnp import QuotaCompteService
        try:
            rap = deposer_plan(depot, plan, source, neuves,
                               prefixe=a.client, ecrire=True)
        except QuotaCompteService as e:
            return stop("dépôt impossible", str(e))
        ok("déposé", "%d fichier(s)" % len(rap["deposes"]))
        if rap["deja"]:
            ok("déjà présent, laissé tel quel", "%d fichier(s)" % len(rap["deja"]))
        for m in rap["manquants"]:
            ligne("!", JAUNE, "non déposé : %s" % m["fichier"], m["motif"])
    else:
        rap = deposer_plan(None, plan, source, neuves, prefixe=a.client, ecrire=False)
        print("\n  %sÀ blanc : %d fichier(s) auraient été déposés. Relancez avec "
              "--deposer.%s" % (JAUNE, len(rap["deposes"]), FIN))

    # -- 6. ce que ça a coûté, et ce qui manque -----------------------------
    if getattr(client, "compteur", None):
        c = client.compteur
        print("\n  %scoût de ce traitement : %.4f € (%d appel(s))%s"
              % (GRIS, c.cout_eur, c.appels, FIN))
    print("  %sAucune écriture comptable produite : le relevé bancaire n'est pas "
          "encore lu, et c'est lui qui fait foi en trésorerie.%s" % (GRIS, FIN))
    if hasattr(source, "nettoyer"):
        source.nettoyer()
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
