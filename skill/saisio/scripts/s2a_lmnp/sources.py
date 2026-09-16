"""Sources de pièces (factures / justificatifs) — interface + dossier local.

Le moteur d'ingestion travaille sur une **abstraction de source** : il liste des
pièces, calcule leur empreinte, écarte celles déjà traitées (manifeste), et remet
les nouvelles à l'OCR. Peu importe d'où elles viennent.

  - `DossierLocal` : un dossier du disque. Sert aux tests et aux dossiers « posés
    dans un répertoire ». C'est aussi ce qui simule le Drive tant qu'on n'a pas
    le connecteur.
  - `SourceDrive` (à câbler) : Google Drive du client. Même interface exactement
    (`lister()` -> PieceRef, `ouvrir(ref)` -> chemin lisible par l'OCR), donc le
    reste du pipeline ne change pas. On y branchera le connecteur Drive + une
    empreinte = md5Checksum fourni par Drive (ou sha256 du contenu téléchargé).
"""
from __future__ import annotations
import hashlib
import os
from dataclasses import dataclass, field
from typing import Optional, Protocol, runtime_checkable

_EXT_DEFAUT = (".pdf", ".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff")


@dataclass
class PieceRef:
    """Référence d'une pièce dans une source, indépendante de l'origine."""
    id: str                       # identifiant dans la source (chemin, id Drive...)
    nom: str                      # nom de fichier affichable
    empreinte: str = ""           # sha256 du contenu -> idempotence, anti-doublon
    taille: int = 0
    chemin: Optional[str] = None  # chemin local lisible par l'OCR (si applicable)
    meta: dict = field(default_factory=dict)


def empreinte_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def empreinte_fichier(chemin: str) -> str:
    h = hashlib.sha256()
    with open(chemin, "rb") as f:
        for bloc in iter(lambda: f.read(65536), b""):
            h.update(bloc)
    return h.hexdigest()


@runtime_checkable
class SourcePieces(Protocol):
    def lister(self) -> list: ...            # -> list[PieceRef]
    def ouvrir(self, ref: PieceRef) -> str: ...  # -> chemin local lisible


class DossierLocal:
    """Source = un dossier du disque (récursif). Empreinte = sha256 du contenu,
    donc un fichier renommé n'est pas re-traité (cf. manifeste)."""

    def __init__(self, dossier: str, extensions=_EXT_DEFAUT):
        self.dossier = dossier
        self.extensions = tuple(e.lower() for e in extensions)

    def lister(self) -> list:
        out = []
        for racine, _dirs, fichiers in os.walk(self.dossier):
            for nom in sorted(fichiers):
                if not nom.lower().endswith(self.extensions):
                    continue
                chemin = os.path.join(racine, nom)
                out.append(PieceRef(
                    id=chemin, nom=nom,
                    empreinte=empreinte_fichier(chemin),
                    taille=os.path.getsize(chemin),
                    chemin=chemin,
                ))
        return out

    def ouvrir(self, ref: PieceRef) -> str:
        return ref.chemin or ref.id


def pieces_neuves(source: SourcePieces, manifeste):
    """Liste les pièces de la source jamais vues dans le manifeste. C'est le
    filtre qui garantit qu'on ne re-paye jamais l'OCR : seules les pièces neuves
    passent à la suite du pipeline."""
    return [p for p in source.lister() if not manifeste.est_traite(p.empreinte)]
