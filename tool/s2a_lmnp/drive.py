"""Connecteur Google Drive — même interface que `DossierLocal`.

Le moteur ne sait pas d'où viennent les pièces : il liste, calcule une
empreinte, écarte ce qu'il a déjà vu, et remet le reste à l'OCR. Ce module
fournit la même chose depuis un Drive partagé, pour que rien d'autre ne change.

Trois décisions, prises ici une bonne fois :

1. **Compte de service, pas connexion individuelle.** Le cabinet partage deux
   dossiers Drive au compte de service ; celui-ci n'a accès à rien d'autre. Pas
   de consentement à renouveler, pas de jeton qui expire la nuit, et le
   périmètre est visible dans les partages Drive plutôt que caché dans un
   fichier de configuration. Chaque collaborateur garde son accès humain
   habituel : Saisio ne se substitue pas à lui, il travaille à côté.

2. **On ne touche JAMAIS au dossier d'entrée.** Saisio lit, télécharge, et écrit
   ailleurs. Un collaborateur qui déplace un fichier pendant un traitement ne
   perd rien ; une pièce n'est jamais renommée ni supprimée sous ses pieds.
   `SANS_ECRITURE` le rappelle, et il n'existe aucune méthode d'écriture sur la
   source dans ce module.

3. **L'empreinte est le sha256 du CONTENU téléchargé**, pas le `md5Checksum` de
   Drive. Drive ne le fournit pas pour les fichiers natifs (Docs, Sheets), il
   change quand le fichier est ré-uploadé à l'identique, et surtout le manifeste
   du moteur parle déjà sha256 : deux empreintes différentes pour la même pièce
   feraient re-payer l'OCR. Une seule vérité.

La dépendance Google est **optionnelle et non silencieuse** : sans elle, la
construction de l'objet lève une erreur qui dit quoi installer. Le cœur du
moteur reste sans dépendance.

    pip install google-api-python-client google-auth

    from s2a_lmnp import DriveGoogle
    src = DriveGoogle(dossier_id="1AbC…", cles="/etc/saisio/compte-service.json")
    for ref in src.lister():
        chemin = src.ouvrir(ref)      # fichier temporaire local, lisible par l'OCR
"""
from __future__ import annotations

import os
import tempfile

from .sources import PieceRef, empreinte_bytes

# Rappel tenu par le code, pas seulement par la documentation : la source est en
# lecture seule. Le seul périmètre demandé à Google est `drive.readonly`.
SANS_ECRITURE = True
PORTEE = ("https://www.googleapis.com/auth/drive.readonly",)

# Types MIME que l'OCR sait lire. Le reste est ignoré à la source : inutile de
# télécharger un tableur pour découvrir ensuite qu'on n'en fait rien.
MIME_LISIBLES = (
    "application/pdf",
    "image/png", "image/jpeg", "image/webp", "image/tiff", "image/heic",
)

# Google renvoie les listes par pages ; 1000 est le maximum accepté.
PAR_PAGE = 1000


class DependanceManquante(RuntimeError):
    """Levée quand la bibliothèque Google n'est pas installée. Explicite, parce
    qu'un connecteur Drive qui échoue en silence rendrait un dossier vide — et
    « aucune nouvelle pièce » est un message parfaitement crédible."""


def _google():
    # On attrape toute défaillance d'import, pas seulement ImportError : une
    # installation abîmée (cryptography sans son backend, par exemple) remonte
    # une panique de la couche native, et une trace Rust n'aide personne.
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except BaseException as e:                    # pragma: no cover
        raise DependanceManquante(
            "Connecteur Drive indisponible (%s : %s). Installez ou réparez "
            "`pip install --force-reinstall google-api-python-client google-auth "
            "cffi cryptography`. Le moteur fonctionne sans, mais uniquement sur "
            "un dossier local." % (type(e).__name__, e)
        ) from e
    return service_account, build


class DriveGoogle:
    """Source = un dossier Google Drive partagé au compte de service.

    `dossier_id` est l'identifiant qui apparaît dans l'URL du dossier :
    https://drive.google.com/drive/folders/**1AbC…**

    `cles` est le chemin du fichier JSON du compte de service. À défaut, on lit
    la variable d'environnement `GOOGLE_APPLICATION_CREDENTIALS`.

    `recursif` descend dans les sous-dossiers — c'est le cas normal : le dossier
    d'entrée est organisé par client puis par année."""

    def __init__(self, dossier_id: str, cles: str = None, *,
                 recursif: bool = True, extensions_mime=MIME_LISIBLES,
                 service=None):
        if not dossier_id:
            raise ValueError("DriveGoogle : identifiant de dossier manquant")
        self.dossier_id = dossier_id
        self.recursif = recursif
        self.mimes = tuple(extensions_mime)
        self._tmp = {}                    # empreinte -> fichier temporaire
        if service is not None:
            self.service = service        # injection : tests et bouchons
            return
        service_account, build = _google()
        chemin = cles or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if not chemin:
            raise ValueError(
                "DriveGoogle : aucune clé de compte de service. Passez `cles=` "
                "ou renseignez GOOGLE_APPLICATION_CREDENTIALS.")
        creds = service_account.Credentials.from_service_account_file(
            chemin, scopes=list(PORTEE))
        self.service = build("drive", "v3", credentials=creds,
                             cache_discovery=False)

    # -- lecture ------------------------------------------------------------
    def _enfants(self, parent_id: str) -> list:
        """Contenu direct d'un dossier, toutes pages confondues."""
        out, page = [], None
        champs = ("nextPageToken, files(id, name, mimeType, size, "
                  "modifiedTime, parents)")
        while True:
            rep = self.service.files().list(
                q="'%s' in parents and trashed = false" % parent_id,
                fields=champs, pageSize=PAR_PAGE, pageToken=page,
                supportsAllDrives=True, includeItemsFromAllDrives=True,
            ).execute()
            out.extend(rep.get("files", []))
            page = rep.get("nextPageToken")
            if not page:
                return out

    def _parcourir(self, parent_id: str, prefixe: str = "") -> list:
        """Descend l'arborescence et renvoie les fichiers lisibles, avec le
        chemin relatif dans le nom : on veut savoir de quel client et de quelle
        année vient la pièce sans avoir à réinterroger Drive."""
        fichiers = []
        for f in self._enfants(parent_id):
            if f.get("mimeType") == "application/vnd.google-apps.folder":
                if self.recursif:
                    fichiers += self._parcourir(
                        f["id"], prefixe + f.get("name", "") + "/")
                continue
            if f.get("mimeType") not in self.mimes:
                continue                  # ni téléchargé, ni payé à l'OCR
            f["_chemin"] = prefixe + f.get("name", "")
            fichiers.append(f)
        return fichiers

    def lister(self) -> list:
        """Toutes les pièces lisibles du dossier partagé, avec leur empreinte.

        L'empreinte impose de télécharger le contenu — c'est le prix de
        l'idempotence, et il est sans commune mesure avec le coût d'un OCR
        refait pour rien. Le contenu est gardé en fichier temporaire pour que
        `ouvrir()` n'ait pas à le retélécharger."""
        out = []
        for f in self._parcourir(self.dossier_id):
            data = self._telecharger(f["id"])
            emp = empreinte_bytes(data)
            out.append(PieceRef(
                id=f["id"],
                nom=f.get("_chemin") or f.get("name", ""),
                empreinte=emp,
                taille=int(f.get("size") or len(data)),
                chemin=self._poser(emp, f.get("name", "piece"), data),
                meta={"mime": f.get("mimeType", ""),
                      "modifie": f.get("modifiedTime", ""),
                      "drive_id": f["id"]},
            ))
        return out

    def ouvrir(self, ref: PieceRef) -> str:
        """Chemin local lisible par l'OCR. Retélécharge si le temporaire a
        disparu (nettoyage du système, redémarrage)."""
        if ref.chemin and os.path.exists(ref.chemin):
            return ref.chemin
        data = self._telecharger(ref.meta.get("drive_id") or ref.id)
        ref.chemin = self._poser(ref.empreinte or empreinte_bytes(data),
                                 ref.nom or "piece", data)
        return ref.chemin

    # -- outillage ----------------------------------------------------------
    def _telecharger(self, file_id: str) -> bytes:
        return self.service.files().get_media(
            fileId=file_id, supportsAllDrives=True).execute()

    def _poser(self, empreinte: str, nom: str, data: bytes) -> str:
        """Écrit le contenu dans un fichier temporaire, une fois par empreinte."""
        deja = self._tmp.get(empreinte)
        if deja and os.path.exists(deja):
            return deja
        ext = os.path.splitext(nom)[1] or ".bin"
        d = os.path.join(tempfile.gettempdir(), "saisio-pieces")
        os.makedirs(d, exist_ok=True)
        chemin = os.path.join(d, empreinte[:16] + ext)
        with open(chemin, "wb") as fh:
            fh.write(data)
        self._tmp[empreinte] = chemin
        return chemin

    def nettoyer(self) -> int:
        """Supprime les fichiers temporaires de cette session. À appeler en fin
        de traitement : ce sont des pièces de clients sur un disque partagé."""
        n = 0
        for c in list(self._tmp.values()):
            try:
                os.remove(c)
                n += 1
            except OSError:
                pass
        self._tmp.clear()
        return n


def resoudre_chemin(source: "DriveGoogle", chemin: str) -> str:
    """Identifiant du sous-dossier `CLIENT/2026` sous le dossier d'entrée.

    Lecture seule : on ne crée rien. Renvoie "" si un segment est introuvable —
    traiter tout le dossier d'entrée parce qu'un nom de client est mal
    orthographié coûterait un OCR sur toutes les pièces de tous les clients.

    Le nom est comparé sans tenir compte de la casse ni des espaces de bord :
    « LMNP POLO TEST » et « lmnp polo test  » désignent le même dossier pour un
    humain, et le rappeler à chaque frappe n'apprend rien à personne."""
    courant = source.dossier_id
    for seg in [s for s in (chemin or "").split("/") if s.strip()]:
        cible = seg.strip().lower()
        trouve = ""
        for f in source._enfants(courant):
            if (f.get("mimeType") == "application/vnd.google-apps.folder"
                    and (f.get("name") or "").strip().lower() == cible):
                trouve = f["id"]
                break
        if not trouve:
            return ""
        courant = trouve
    return courant


def verifier_acces(dossier_id: str, cles: str = None) -> dict:
    """Diagnostic de branchement, à lancer avant tout traitement.

    Renvoie ce que le compte de service voit réellement — plutôt que de laisser
    « 0 pièce » passer pour un dossier vide alors que c'est un partage oublié."""
    src = DriveGoogle(dossier_id, cles)
    try:
        meta = src.service.files().get(
            fileId=dossier_id, fields="id, name, mimeType",
            supportsAllDrives=True).execute()
    except Exception as e:                        # pragma: no cover
        return {"ok": False, "erreur": str(e),
                "conseil": "Le dossier est-il partagé avec l'adresse du compte "
                           "de service (…@….iam.gserviceaccount.com) ?"}
    pieces = src.lister()
    src.nettoyer()
    return {
        "ok": True,
        "dossier": meta.get("name", ""),
        "pieces_lisibles": len(pieces),
        "exemples": [p.nom for p in pieces[:5]],
        "lecture_seule": SANS_ECRITURE,
    }
