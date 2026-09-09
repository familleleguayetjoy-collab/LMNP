"""Connexion Google au nom de l'utilisateur — pour déposer sur un Drive gratuit.

Un compte de service ne possède aucun octet de stockage. Sur Google Workspace on
contourne par un **Drive partagé**, où les fichiers appartiennent à
l'organisation. Sur un compte Gmail gratuit, les Drive partagés n'existent pas :
la seule issue est que Saisio dépose **au nom de l'utilisateur**, et consomme
son espace à lui.

Ce module ne sert QUE pour l'écriture. La lecture du dossier d'entrée continue
de passer par le compte de service : c'est le partage Drive, visible de tous,
qui délimite ce que l'outil peut lire, et cette garantie-là ne se troque pas
contre une commodité.

Comment ça marche, une fois pour toutes :

  1. l'utilisateur se connecte dans son navigateur, une seule fois ;
  2. Google rend un **jeton de rafraîchissement**, rangé dans `~/.saisio` ;
  3. les traitements suivants s'en servent sans rien redemander.

Le jeton vaut un mot de passe : il ouvre le Drive de celui qui s'est connecté.
Il est écrit en 0600 quand le système le permet, et ne quitte jamais la machine.

    pip install google-auth-oauthlib

    python3 tool/connexion_google.py      # une fois
"""
from __future__ import annotations

import json
import os

from .drive import DependanceManquante

# Écrire dans un dossier créé par un humain suppose de le voir : `drive.file` ne
# montre que ce que l'application a créé elle-même, le dossier de sortie lui
# serait donc invisible. La portée est large ; ce qui la borne, c'est que
# l'utilisateur se l'accorde à lui-même, sur son propre Drive, et peut la
# révoquer d'un clic depuis myaccount.google.com/permissions.
PORTEE_UTILISATEUR = ("https://www.googleapis.com/auth/drive",)

DOSSIER_ETAT = os.path.join(os.path.expanduser("~"), ".saisio")
JETON = os.path.join(DOSSIER_ETAT, "jeton_google.json")

# Le fichier d'identifiants OAuth téléchargé depuis la console Cloud
# (« ID client OAuth », type Application de bureau).
NOMS_CLIENT = ("client_oauth.json", "client_secret.json")


def chemin_client() -> str:
    """Où trouver le fichier d'identifiants OAuth. Vide s'il n'y en a pas."""
    donne = os.environ.get("SAISIO_OAUTH_CLIENT", "")
    if donne and os.path.exists(donne):
        return donne
    projet = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    for base in (DOSSIER_ETAT, projet):
        for nom in NOMS_CLIENT:
            c = os.path.join(base, nom)
            if os.path.exists(c):
                return c
    return ""


def jeton_present() -> bool:
    return os.path.exists(JETON)


def _modules(avec_flux: bool):
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        flux = None
        if avec_flux:
            from google_auth_oauthlib.flow import InstalledAppFlow
            flux = InstalledAppFlow
    except BaseException as e:                    # pragma: no cover
        raise DependanceManquante(
            "Connexion Google indisponible (%s : %s). "
            "Installez `pip install google-auth-oauthlib`."
            % (type(e).__name__, e)) from e
    return Credentials, Request, flux


def _ecrire_jeton(creds):
    os.makedirs(DOSSIER_ETAT, exist_ok=True)
    with open(JETON, "w", encoding="utf-8") as f:
        f.write(creds.to_json())
    try:
        os.chmod(JETON, 0o600)                    # sans effet sous Windows
    except OSError:
        pass


def identifiants(interactif: bool = False):
    """Renvoie des identifiants Google valides au nom de l'utilisateur.

    `interactif=False` (le cas des traitements) : on se contente du jeton déjà
    obtenu, quitte à le rafraîchir. S'il n'y en a pas, on lève — un traitement
    de nuit n'a pas à ouvrir un navigateur sur un poste que personne ne regarde.

    `interactif=True` (la commande de connexion) : on ouvre le navigateur.
    """
    Credentials, Request, InstalledAppFlow = _modules(avec_flux=interactif)
    creds = None
    if os.path.exists(JETON):
        creds = Credentials.from_authorized_user_file(JETON, list(PORTEE_UTILISATEUR))
    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _ecrire_jeton(creds)
        return creds
    if not interactif:
        raise RuntimeError(
            "aucune connexion Google enregistrée — lancez une fois : "
            "python tool/connexion_google.py")
    client = chemin_client()
    if not client:
        raise RuntimeError(
            "fichier d'identifiants OAuth introuvable. Téléchargez-le depuis la "
            "console Cloud (Identifiants → ID client OAuth → Application de "
            "bureau) et posez-le dans %s sous le nom client_oauth.json"
            % DOSSIER_ETAT)
    flow = InstalledAppFlow.from_client_secrets_file(client, list(PORTEE_UTILISATEUR))
    creds = flow.run_local_server(port=0, prompt="consent",
                                  authorization_prompt_message="")
    _ecrire_jeton(creds)
    return creds


def compte_connecte() -> str:
    """Adresse du compte dont le jeton est enregistré, pour l'afficher. Ne
    contacte pas Google : on lit ce que le jeton contient déjà."""
    if not os.path.exists(JETON):
        return ""
    try:
        with open(JETON, encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        return ""
    return d.get("account") or d.get("client_id", "")[:20]


def oublier() -> bool:
    """Efface le jeton local. Ne révoque rien côté Google — pour cela,
    myaccount.google.com/permissions."""
    if not os.path.exists(JETON):
        return False
    os.remove(JETON)
    return True
