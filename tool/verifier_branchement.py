#!/usr/bin/env python3
"""Vérification de branchement — À LANCER AVANT TOUT TRAITEMENT RÉEL.

Ce script ne modifie rien, nulle part. Il répond à une seule question :
« est-ce que Saisio voit ce qu'il doit voir, et produirait ce qu'il doit
produire ? ». Il s'arrête au premier obstacle, en disant quoi faire.

    python3 tool/verifier_branchement.py                      # tout
    python3 tool/verifier_branchement.py --etape drive        # une étape

Étapes, dans l'ordre où elles peuvent casser :

  1. moteur    — le cœur tourne (aucune dépendance, aucun réseau)
  2. cle       — la clé API Anthropic est là et fonctionne
  3. drive     — le compte de service voit le dossier d'entrée
  4. bout      — une pièce réelle traverse toute la chaîne, SANS RIEN ÉCRIRE

L'étape 4 est la seule qui coûte de l'argent (un appel OCR par pièce, quelques
centimes) et la seule qui compte vraiment : elle lit une vraie pièce, la classe,
l'impute, la range et sort le fichier Quadra — dans un dossier temporaire.
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

VERT, ROUGE, JAUNE, GRIS, FIN = "\033[32m", "\033[31m", "\033[33m", "\033[90m", "\033[0m"


def ok(t, d=""):
    print("  %s✓%s %s %s%s%s" % (VERT, FIN, t, GRIS, d, FIN))
    return True


def ko(t, quoi_faire):
    print("  %s✗%s %s" % (ROUGE, FIN, t))
    print("    %s→ %s%s" % (JAUNE, quoi_faire, FIN))
    return False


def titre(n, t):
    print("\n%d) %s" % (n, t))
    print("   " + "─" * (len(t) + 2))


# ---------------------------------------------------------------------------
def etape_moteur() -> bool:
    titre(1, "Le moteur")
    try:
        from s2a_lmnp import (construire, parse_fec, coder, to_quadratus,
                              Operation, ranger, Exercice)
    except Exception as e:
        return ko("import du moteur", "dépôt incomplet ? %s" % e)
    ok("moteur importé", "bibliothèque standard seule")

    import datetime
    fec = ("JournalCode\tCompteNum\tCompteLib\tEcritureDate\tEcritureLib\tDebit\tCredit\n"
           "BQ\t606100\tEnergie\t20250210\tEDF energie\t57,79\t0,00\n")
    dico = construire(parse_fec(fec))
    op = Operation(datetime.date(2026, 1, 20), "EDF ENERGIE", 69.34, "D")
    coder(op, dico)
    if op.compte != "606100":
        return ko("codage depuis le FEC", "le dictionnaire N-1 ne s'applique pas")
    ok("le FEC N-1 code une ligne", "EDF → %s" % op.compte)

    lignes = to_quadratus([op], avec_banque=True, compte_banque="51210010",
                          journal="BQ").split("\r\n")
    if not lignes or len(lignes[0]) != 251:
        return ko("export Quadratus", "longueur d'enregistrement inattendue")
    return ok("export Quadratus", "%d caractères par ligne" % len(lignes[0]))


def etape_cle() -> bool:
    titre(2, "La clé API Anthropic")
    cle = os.environ.get("ANTHROPIC_API_KEY", "")
    if not cle:
        return ko("ANTHROPIC_API_KEY absente",
                  "export ANTHROPIC_API_KEY='sk-ant-…' (ou dans le service systemd)")
    ok("clé présente", "…%s" % cle[-6:])
    try:
        import anthropic          # noqa: F401
    except ImportError:
        return ko("bibliothèque anthropic absente", "pip install anthropic")
    ok("bibliothèque anthropic installée")

    from s2a_lmnp import ClientAnthropic
    try:
        c = ClientAnthropic()
        rep = c.resoudre([{"id": "t", "libelle": "TEST DE BRANCHEMENT",
                           "montant": 1.0, "options": ["606", "615"]}])
    except Exception as e:
        return ko("appel à l'API refusé", "clé invalide, quota, ou réseau : %s" % e)
    ok("appel à l'API accepté", "%d réponse(s)" % len(rep or []))
    if getattr(c, "compteur", None):
        print("    %scoût de ce test : %.4f €%s" % (GRIS, c.compteur.cout_eur, FIN))
    return True


def etape_drive(dossier_id: str, cles: str) -> bool:
    titre(3, "Le Drive du cabinet")
    if not dossier_id:
        return ko("identifiant du dossier d'entrée manquant",
                  "--drive <id>  (l'id est dans l'URL du dossier Drive)")
    from s2a_lmnp import verifier_acces, DependanceManquante
    try:
        r = verifier_acces(dossier_id, cles)
    except DependanceManquante as e:
        return ko("connecteur indisponible", str(e))
    except Exception as e:
        return ko("accès refusé", "%s" % e)
    if not r.get("ok"):
        return ko("dossier illisible", r.get("conseil", r.get("erreur", "")))
    ok("dossier atteint", "« %s »" % r["dossier"])
    ok("lecture seule", "portée drive.readonly, aucune écriture possible")
    n = r["pieces_lisibles"]
    if n == 0:
        return ko("aucune pièce lisible",
                  "dossier vide, ou partage limité à un sous-dossier ? "
                  "Vérifiez que le partage porte bien sur la racine.")
    ok("%d pièce(s) lisible(s)" % n, " · ".join(r["exemples"]))
    return True


def etape_bout(dossier_id: str, cles: str, local: str, limite: int) -> bool:
    titre(4, "Bout en bout, sans rien écrire")
    from s2a_lmnp import (DossierLocal, DriveGoogle, Manifeste, pieces_neuves,
                          ranger, resume_rangement, Exercice, RACINE)
    import datetime

    if local:
        if not os.path.isdir(local):
            return ko("dossier local introuvable", "vérifiez le chemin : %s" % local)
        source, quoi = DossierLocal(local), "dossier local %s" % local
    elif dossier_id:
        try:
            source, quoi = DriveGoogle(dossier_id, cles), "Drive %s" % dossier_id[:12]
        except Exception as e:
            return ko("source Drive indisponible", str(e))
    else:
        return ko("aucune source", "--drive <id> ou --local <dossier>")

    travail = tempfile.mkdtemp(prefix="saisio-verif-")
    man = Manifeste(os.path.join(travail, "manifeste.json"))
    neuves = pieces_neuves(source, man)[:limite]
    if not neuves:
        return ko("aucune pièce à traiter", "la source est vide")
    ok("%d pièce(s) retenue(s) pour l'essai" % len(neuves),
       "sur %s" % quoi)

    from s2a_lmnp import factures_depuis_ocr
    try:
        from s2a_lmnp import ClientAnthropic
        client = ClientAnthropic()
    except ImportError:
        return ko("bibliothèque anthropic absente", "pip install anthropic")
    except Exception as e:
        return ko("client IA indisponible",
                  "l'étape 2 doit passer d'abord (%s)" % e)
    bruts = []
    for ref in neuves:
        try:
            bruts.append(client.lire_facture(source.ouvrir(ref)))
        except Exception as e:
            return ko("lecture de « %s »" % ref.nom, str(e))
    ok("%d pièce(s) lue(s) par l'OCR" % len(bruts))

    factures, rejets = factures_depuis_ocr(bruts)
    ok("classement", "%d retenue(s), %d écartée(s)" % (len(factures), len(rejets)))
    for r in rejets:
        print("    %s· %s : %s%s" % (GRIS, r.get("fichier", "?"), r.get("motif", ""), FIN))

    an = datetime.date.today().year
    plan = ranger(factures, rejets, exercice=Exercice.civil(an))
    ok("plan de rangement", "%d dossier(s)" % len(plan))
    for l in resume_rangement(plan):
        print("    %s%s → %d pièce(s)%s" % (GRIS, l["chemin"], l["pieces"], FIN))

    if getattr(client, "compteur", None):
        c = client.compteur
        print("\n    %scoût réel de cet essai : %.4f € (%d appel(s))%s"
              % (GRIS, c.cout_eur, c.appels, FIN))
        alerte = c.alerte(nb_factures=len(neuves))
        if alerte:
            print("    %s⚠ %s%s" % (JAUNE, alerte, FIN))

    print("\n  %sRIEN n'a été écrit : ni sur le Drive, ni dans le dossier "
          "d'entrée.%s" % (GRIS, FIN))
    print("  %sTravail temporaire : %s%s" % (GRIS, travail, FIN))
    if hasattr(source, "nettoyer"):
        source.nettoyer()
    return True


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--etape", choices=["moteur", "cle", "drive", "bout"],
                    help="ne lancer qu'une étape")
    ap.add_argument("--drive", default=os.environ.get("SAISIO_DRIVE_ENTREE", ""),
                    help="identifiant du dossier Drive d'entrée")
    ap.add_argument("--cles", default=os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", ""),
                    help="fichier JSON du compte de service")
    ap.add_argument("--local", default="",
                    help="dossier local, à la place du Drive")
    ap.add_argument("--limite", type=int, default=3,
                    help="nombre de pièces lues à l'étape 4 (défaut : 3)")
    a = ap.parse_args()

    print("\nSAISIO — vérification de branchement")
    print("=" * 44)

    etapes = [
        ("moteur", lambda: etape_moteur()),
        ("cle",    lambda: etape_cle()),
        ("drive",  lambda: etape_drive(a.drive, a.cles)),
        ("bout",   lambda: etape_bout(a.drive, a.cles, a.local, a.limite)),
    ]
    if a.etape:
        etapes = [e for e in etapes if e[0] == a.etape]

    for nom, f in etapes:
        if not f():
            print("\n%sArrêt à l'étape « %s ». Corrigez ce point avant la "
                  "suite.%s\n" % (ROUGE, nom, FIN))
            return 1

    print("\n%sTout est branché.%s Prochaine étape : les trois dossiers de "
          "contrôle.\n" % (VERT, FIN))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
