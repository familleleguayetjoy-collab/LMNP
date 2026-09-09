#!/usr/bin/env python3
"""Connecter Saisio à votre compte Google — une seule fois.

    python3 tool/connexion_google.py            # se connecter
    python3 tool/connexion_google.py --etat     # où en est-on ?
    python3 tool/connexion_google.py --oublier  # effacer la connexion locale

À quoi ça sert : un compte de service Google ne possède aucun octet de stockage.
Il crée des dossiers, il ne peut pas y déposer de fichier. Sur Google Workspace
on règle ça avec un Drive partagé ; sur un compte Gmail gratuit, ils n'existent
pas. Saisio dépose alors **en votre nom**, dans votre espace à vous.

Ce que ça ne change pas : la LECTURE du dossier d'entrée continue de passer par
le compte de service. C'est le partage Drive — visible par tout le monde,
révocable en un clic — qui délimite ce que l'outil peut lire, et cette
garantie-là ne se troque pas contre une commodité.

Avant de lancer cette commande, il faut un fichier d'identifiants OAuth, à
récupérer une fois dans la console Cloud (voir DEPLOIEMENT.md, partie D0).
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from reglages import charger as charger_reglages

charger_reglages()

VERT, ROUGE, JAUNE, GRIS, FIN = "\033[32m", "\033[31m", "\033[33m", "\033[90m", "\033[0m"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--etat", action="store_true", help="afficher l'état, sans rien changer")
    ap.add_argument("--oublier", action="store_true", help="effacer la connexion locale")
    a = ap.parse_args()

    from s2a_lmnp import oauth_google as og

    print("\nSAISIO — connexion Google")
    print("=" * 34)

    if a.oublier:
        if og.oublier():
            print("  %s✓%s connexion locale effacée" % (VERT, FIN))
            print("  %spour révoquer aussi l'accès côté Google : "
                  "myaccount.google.com/permissions%s" % (GRIS, FIN))
        else:
            print("  %saucune connexion enregistrée%s" % (GRIS, FIN))
        print()
        return 0

    if a.etat:
        if og.jeton_present():
            print("  %s✓%s connecté %s(%s)%s"
                  % (VERT, FIN, GRIS, og.compte_connecte() or "compte inconnu", FIN))
            print("  %sjeton : %s%s" % (GRIS, og.JETON, FIN))
        else:
            print("  %s✗%s aucune connexion — lancez la commande sans option"
                  % (ROUGE, FIN))
        print()
        return 0 if og.jeton_present() else 1

    client = og.chemin_client()
    if not client:
        print("  %s✗%s fichier d'identifiants OAuth introuvable" % (ROUGE, FIN))
        print("    %s→ console.cloud.google.com → APIs et services → "
              "Identifiants → Créer des identifiants → ID client OAuth →"
              % JAUNE)
        print("      type « Application de bureau ». Téléchargez le JSON,")
        print("      renommez-le client_oauth.json et posez-le dans :")
        print("      %s%s%s" % (FIN + GRIS, og.DOSSIER_ETAT, FIN))
        print()
        return 1
    print("  %sidentifiants OAuth : %s%s" % (GRIS, client, FIN))
    print("  %sune fenêtre de navigateur va s'ouvrir. Choisissez le compte "
          "Google qui porte le Drive du cabinet.%s" % (JAUNE, FIN))
    print("  %sSi Google affiche « Google n'a pas validé cette application », "
          "c'est normal : c'est VOTRE application. Cliquez sur "
          "« Paramètres avancés » puis « Accéder à … ».%s" % (GRIS, FIN))
    try:
        og.identifiants(interactif=True)
    except Exception as e:
        print("\n  %s✗%s connexion refusée" % (ROUGE, FIN))
        print("    %s→ %s%s" % (JAUNE, e, FIN))
        print()
        return 1
    print("\n  %s✓%s connecté %s(%s)%s"
          % (VERT, FIN, GRIS, og.compte_connecte() or "compte enregistré", FIN))
    print("  %sjeton rangé dans %s — il vaut un mot de passe, il ne quitte "
          "pas cette machine.%s" % (GRIS, og.JETON, FIN))
    print("\n  Saisio déposera désormais en votre nom. Vous pouvez lancer :")
    print("  %spython tool/traiter.py --client \"…\" --exercice 2026 --deposer%s"
          % (GRIS, FIN))
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
