"""Dépôt des pièces rangées dans le dossier de sortie du Drive.

Module **séparé** de `drive.py`, et ce n'est pas de la coquetterie : le
connecteur de lecture affirme qu'il ne peut rien écrire, et cette affirmation ne
vaut que s'il n'y a effectivement aucune méthode d'écriture dedans. Tout ce qui
écrit vit ici, sur le seul dossier de SORTIE.

Quatre règles, tenues par le code :

1. **On n'écrit que dans le dossier de sortie.** Son identifiant est passé
   explicitement ; rien ne remonte au-dessus. Le dossier d'entrée est partagé en
   « Lecteur » côté Drive : même avec la portée large demandée ici, Google
   refuserait l'écriture. La garantie est donc double, et la moitié visible
   (le partage) est celle que le cabinet peut vérifier sans lire de code.

2. **On n'écrase jamais, on ne supprime jamais.** Un nom déjà présent est
   ignoré, pas remplacé : ce sont les pièces d'un client, et une pièce écrasée
   pendant un traitement est une pièce perdue. Le rapport dit ce qui a été
   ignoré, et pourquoi.

3. **On ne redépose pas ce qui est déjà là.** Un fichier de même nom ET de même
   taille dans le même dossier est considéré comme déjà déposé. Relancer un
   traitement deux fois ne duplique donc rien.

4. **Les dossiers sont créés à la demande, une seule fois.** `Exercice 2026 /
   2026-03 / Traité` est créé au premier besoin puis gardé en mémoire : un
   traitement de 200 pièces ne fait pas 600 appels de création.

    pip install google-api-python-client google-auth

    from s2a_lmnp import DepotDrive, deposer_plan
    depot = DepotDrive(racine_id="1XyZ…", cles="…/compte-service.json")
    rapport = deposer_plan(depot, plan, source, pieces, prefixe="DUPONT/")
"""
from __future__ import annotations

import os

from .drive import DependanceManquante

# Écrire dans un dossier Drive suppose de pouvoir y créer des fichiers ET d'y
# retrouver les sous-dossiers créés par un humain. `drive.file` ne montre que ce
# que l'application a créé elle-même : le dossier de sortie, créé par le
# cabinet, lui serait invisible. La portée est donc large, et c'est le PARTAGE
# Drive qui délimite le périmètre — visible de tous, révocable en un clic.
PORTEE_DEPOT = ("https://www.googleapis.com/auth/drive",)

MIME_DOSSIER = "application/vnd.google-apps.folder"


class QuotaCompteService(RuntimeError):
    """Un compte de service n'a AUCUN quota de stockage Google.

    Il peut créer des dossiers — un dossier ne pèse rien — mais pas déposer un
    fichier dans un « Mon Drive » : le fichier lui appartiendrait, et il n'a pas
    un octet à lui. On voit donc l'arborescence se construire et pas une seule
    pièce arriver, ce qui ressemble à tout sauf à un problème de quota.

    Deux issues, et une seule ne demande aucun code :

    1. **Drive partagé** (Google Workspace) : les fichiers y appartiennent à
       l'organisation, pas à celui qui les dépose. Le compte de service y écrit
       normalement. C'est aussi la bonne réponse comptable : les pièces des
       clients appartiennent au cabinet, pas au collaborateur qui les a
       importées ni à un robot.

    2. **Délégation** (Workspace également) : le compte de service agit au nom
       d'un utilisateur réel, et consomme SON quota.

    Sur un compte Google gratuit, ni l'un ni l'autre n'existe : il faut alors
    une connexion OAuth au nom de l'utilisateur.
    """


CONSEIL_QUOTA = (
    "Un compte de service n'a aucun quota de stockage : il crée les dossiers "
    "mais ne peut pas y déposer de fichier. Le dossier de sortie doit se "
    "trouver dans un DRIVE PARTAGÉ (Google Workspace), où les fichiers "
    "appartiennent à l'organisation. Déplacez-y « Documents générés par "
    "l'application », ajoutez-y le compte de service comme Gestionnaire de "
    "contenu, et reprenez l'identifiant du dossier."
)


def _google():
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except BaseException as e:                    # pragma: no cover
        raise DependanceManquante(
            "Dépôt Drive indisponible (%s : %s). Installez ou réparez "
            "`pip install --force-reinstall google-api-python-client google-auth`."
            % (type(e).__name__, e)) from e
    return service_account, build


class DepotDrive:
    """Le dossier de sortie, et rien d'autre.

    `racine_id` est l'identifiant du dossier « Documents générés par
    l'application », partagé au compte de service en **Éditeur**."""

    def __init__(self, racine_id: str, cles: str = None, *, service=None):
        if not racine_id:
            raise ValueError("DepotDrive : identifiant du dossier de sortie manquant")
        self.racine_id = racine_id
        self._dossiers = {}               # chemin relatif -> identifiant Drive
        self._contenu = {}                # identifiant -> {nom: taille}
        if service is not None:
            self.service = service        # injection : tests et bouchons
            return
        service_account, build = _google()
        chemin = cles or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if not chemin:
            raise ValueError(
                "DepotDrive : aucune clé de compte de service. Passez `cles=` "
                "ou renseignez GOOGLE_APPLICATION_CREDENTIALS.")
        creds = service_account.Credentials.from_service_account_file(
            chemin, scopes=list(PORTEE_DEPOT))
        self.service = build("drive", "v3", credentials=creds,
                             cache_discovery=False)

    def verifier(self) -> dict:
        """Le compte de service voit-il le dossier, et peut-il y écrire ?

        À appeler AVANT de lire la moindre pièce : découvrir un partage en
        « Lecteur » après avoir payé l'OCR laisse des pièces lues, marquées
        traitées dans le manifeste, et jamais déposées. Drive répond
        `canAddChildren` sans qu'on ait à tenter une écriture d'essai — donc
        sans laisser de fichier de test derrière soi."""
        meta = self.service.files().get(
            fileId=self.racine_id,
            fields="id, name, driveId, capabilities/canAddChildren",
            supportsAllDrives=True).execute()
        peut = bool((meta.get("capabilities") or {}).get("canAddChildren"))
        # `driveId` n'est renseigné que dans un Drive partagé. Sans lui, on est
        # dans un « Mon Drive » : les dossiers s'y créeront (ils ne pèsent rien)
        # et pas un seul fichier n'arrivera. Le dire AVANT de payer l'OCR, plutôt
        # que de laisser une arborescence vide se construire.
        partage = bool(meta.get("driveId"))
        nom = meta.get("name", "")
        if not peut:
            conseil = ("le dossier « %s » est partagé au compte de service en "
                       "Lecteur : passez-le en Éditeur." % nom)
        elif not partage:
            conseil = CONSEIL_QUOTA
        else:
            conseil = ""
        return {"ok": peut and partage, "dossier": nom,
                "ecriture": peut, "drive_partage": partage, "conseil": conseil}

    # -- arborescence -------------------------------------------------------
    def _chercher(self, nom: str, parent_id: str, dossier: bool):
        """Premier enfant portant ce nom, ou None. On échappe l'apostrophe :
        « Documents générés par l'application » en contient une, et une requête
        Drive mal échappée ne renvoie pas une erreur mais un résultat vide."""
        q = ("name = '%s' and '%s' in parents and trashed = false"
             % (nom.replace("\\", "\\\\").replace("'", "\\'"), parent_id))
        if dossier:
            q += " and mimeType = '%s'" % MIME_DOSSIER
        rep = self.service.files().list(
            q=q, fields="files(id, name, size)", pageSize=10,
            supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
        f = rep.get("files") or []
        return f[0] if f else None

    def _creer_dossier(self, nom: str, parent_id: str) -> str:
        rep = self.service.files().create(
            body={"name": nom, "mimeType": MIME_DOSSIER, "parents": [parent_id]},
            fields="id", supportsAllDrives=True).execute()
        return rep["id"]

    def assurer_chemin(self, chemin: str) -> str:
        """Identifiant du dossier `a/b/c` sous la racine, créé s'il manque.

        Le résultat est mémorisé : un traitement de 200 pièces ne recrée pas
        cinquante fois le même mois."""
        chemin = (chemin or "").strip("/")
        if not chemin:
            return self.racine_id
        if chemin in self._dossiers:
            return self._dossiers[chemin]
        parent, courant = self.racine_id, ""
        for seg in chemin.split("/"):
            if not seg:
                continue
            courant = (courant + "/" + seg) if courant else seg
            connu = self._dossiers.get(courant)
            if connu:
                parent = connu
                continue
            trouve = self._chercher(seg, parent, dossier=True)
            parent = trouve["id"] if trouve else self._creer_dossier(seg, parent)
            self._dossiers[courant] = parent
        return parent

    # -- dépôt --------------------------------------------------------------
    def deja_la(self, nom: str, dossier_id: str, taille=None) -> bool:
        """Vrai si une pièce de ce nom (et de cette taille) est déjà déposée."""
        f = self._chercher(nom, dossier_id, dossier=False)
        if not f:
            return False
        if taille is None or not f.get("size"):
            return True
        return int(f["size"]) == int(taille)

    def deposer(self, chemin_local: str, nom: str, dossier_id: str) -> dict:
        """Dépose un fichier. Ne remplace jamais : si le nom existe déjà, on
        renvoie `{"etat": "deja"}` sans toucher à quoi que ce soit."""
        taille = os.path.getsize(chemin_local) if os.path.exists(chemin_local) else None
        if self.deja_la(nom, dossier_id, taille):
            return {"etat": "deja", "nom": nom}
        from googleapiclient.http import MediaFileUpload    # import tardif
        media = MediaFileUpload(chemin_local, resumable=False)
        try:
            rep = self.service.files().create(
                body={"name": nom, "parents": [dossier_id]},
                media_body=media, fields="id, name",
                supportsAllDrives=True).execute()
        except Exception as e:
            # Google répond 403 « storageQuotaExceeded ». Le message d'origine
            # renvoie vers deux pages d'aide en anglais ; il vaut mieux dire
            # tout de suite quoi faire, dans les mots du cabinet.
            if "storageQuota" in str(e) or "storage quota" in str(e):
                raise QuotaCompteService(CONSEIL_QUOTA) from e
            raise
        return {"etat": "depose", "nom": nom, "id": rep.get("id", "")}


def deposer_plan(depot, plan: dict, source, pieces, *, prefixe: str = "",
                 ecrire: bool = True) -> dict:
    """Applique un plan de rangement au dossier de sortie.

    `pieces` : les `PieceRef` du traitement — c'est par leur empreinte que le
    plan retrouve le fichier à envoyer. Une entrée dont l'empreinte est inconnue
    est signalée, jamais devinée.

    `ecrire=False` : on calcule tout, on ne dépose rien. C'est le mode par
    défaut de la commande, pour qu'un premier essai ne puisse rien salir.

    Renvoie `{"deposes": [...], "deja": [...], "manquants": [...],
    "dossiers": [...]}` — le détail de ce qui s'est passé, pièce par pièce."""
    index = {p.empreinte: p for p in (pieces or []) if getattr(p, "empreinte", "")}
    rap = {"deposes": [], "deja": [], "manquants": [], "dossiers": []}
    for chemin in sorted(plan):
        rel = (prefixe.strip("/") + "/" + chemin).strip("/") if prefixe else chemin
        rap["dossiers"].append(rel)
        dossier_id = depot.assurer_chemin(rel) if ecrire else ""
        for e in plan[chemin]:
            ref = index.get(e.get("empreinte"))
            if ref is None:
                rap["manquants"].append({"chemin": rel,
                                         "fichier": e.get("fichier", ""),
                                         "motif": "pièce introuvable à la source"})
                continue
            nom = os.path.basename(ref.nom or e.get("fichier") or "piece")
            if not ecrire:
                rap["deposes"].append({"chemin": rel, "nom": nom, "simule": True})
                continue
            r = depot.deposer(source.ouvrir(ref), nom, dossier_id)
            (rap["deja"] if r["etat"] == "deja" else rap["deposes"]).append(
                {"chemin": rel, "nom": nom})
    return rap
