"""Prétraitement des pièces avant envoi au modèle — premier poste de coût.

Une facture scannée en 300 DPI coûte 3 à 4 fois une facture à 1 500 px de large,
sans être plus lisible pour le modèle : le nombre de tokens d'une image est
proportionnel à sa surface (≈ largeur × hauteur / 750).

Ce module est le SEUL endroit du moteur qui a des dépendances externes
(Pillow pour les images, pypdfium2 pour rasteriser un PDF). Le cœur reste
importable sans elles : si elles manquent, on envoie la pièce brute.

MAIS le repli n'est jamais silencieux — c'est une exigence explicite du cabinet.
Un repli silencieux reproduit exactement la dérive que l'instrumentation doit
détecter : si Pillow manque en production, le coût triple sans que personne ne
le voie. Donc chaque repli :
  - émet un `warnings.warn` ;
  - est compté dans le `Journal` (exposé au tableau de bord) ;
  - déclenche `alerte()` au-delà de 5 % des pièces d'un lot.
"""
from __future__ import annotations
import io
import os
import warnings
from dataclasses import dataclass, field

# Cible : 1 500 px sur le plus grand côté, JPEG qualité 80. Configurable.
COTE_MAX = 1500
QUALITE_JPEG = 80
SEUIL_ALERTE_REPLI = 0.05      # au-delà de 5 % de replis dans un lot -> alerte
_TOKENS_PAR_PIXELS = 750.0     # ≈ tokens d'une image = surface / 750


def tokens_image(largeur: int, hauteur: int) -> int:
    """Estimation du coût en tokens d'une image, pour la journalisation."""
    if largeur <= 0 or hauteur <= 0:
        return 0
    return int(round((largeur * hauteur) / _TOKENS_PAR_PIXELS))


@dataclass
class Journal:
    """Compteurs de prétraitement d'un lot, remontés au tableau de bord."""
    pieces: int = 0
    reduites: int = 0
    replis: int = 0
    motifs_replis: dict = field(default_factory=dict)
    tokens_avant: int = 0
    tokens_apres: int = 0

    def _repli(self, motif: str):
        self.replis += 1
        self.motifs_replis[motif] = self.motifs_replis.get(motif, 0) + 1
        warnings.warn("prétraitement ignoré (%s) : la pièce partira en pleine "
                      "résolution, à surcoût" % motif, RuntimeWarning, stacklevel=3)

    @property
    def taux_repli(self) -> float:
        return (self.replis / self.pieces) if self.pieces else 0.0

    @property
    def economie_tokens(self) -> int:
        return max(0, self.tokens_avant - self.tokens_apres)

    def alerte(self) -> str:
        """Message d'alerte si le taux de repli dépasse le seuil, sinon ''."""
        if self.pieces and self.taux_repli > SEUIL_ALERTE_REPLI:
            return ("ALERTE prétraitement : %d/%d pièces (%.0f %%) envoyées en pleine "
                    "résolution — surcoût. Motifs : %s"
                    % (self.replis, self.pieces, 100 * self.taux_repli,
                       ", ".join("%s×%d" % (m, n)
                                 for m, n in sorted(self.motifs_replis.items()))))
        return ""

    def resume(self) -> dict:
        return {
            "pieces": self.pieces, "reduites": self.reduites, "replis": self.replis,
            "taux_repli": round(self.taux_repli, 4),
            "tokens_avant": self.tokens_avant, "tokens_apres": self.tokens_apres,
            "economie_tokens": self.economie_tokens,
            "motifs_replis": dict(self.motifs_replis),
            "alerte": self.alerte(),
        }


def _pillow():
    try:
        from PIL import Image           # noqa: F401
        return Image
    except Exception:
        return None


def reduire_image(data: bytes, *, cote_max=COTE_MAX, qualite=QUALITE_JPEG,
                  journal: Journal | None = None):
    """Réduit une image à `cote_max` sur le plus grand côté, JPEG `qualite`,
    niveaux de gris si le document est monochrome.

    Renvoie `(data, media_type)`. En cas d'impossibilité, renvoie l'original et
    journalise un repli (jamais en silence)."""
    if journal is not None:
        journal.pieces += 1
    Image = _pillow()
    if Image is None:
        if journal is not None:
            journal._repli("pillow_absent")
        return data, None
    try:
        im = Image.open(io.BytesIO(data))
        im.load()
        larg, haut = im.size
        if journal is not None:
            journal.tokens_avant += tokens_image(larg, haut)

        cote = max(larg, haut)
        if cote > cote_max:
            ech = cote_max / float(cote)
            im = im.resize((max(1, int(larg * ech)), max(1, int(haut * ech))),
                           Image.LANCZOS)

        # niveaux de gris si l'image est de fait monochrome (scan N&B)
        if im.mode not in ("L", "RGB"):
            im = im.convert("RGB")
        if im.mode == "RGB" and _est_monochrome(im):
            im = im.convert("L")

        buf = io.BytesIO()
        im.convert("L" if im.mode == "L" else "RGB").save(
            buf, format="JPEG", quality=qualite, optimize=True)
        out = buf.getvalue()
        if journal is not None:
            journal.tokens_apres += tokens_image(*im.size)
            journal.reduites += 1
        return out, "image/jpeg"
    except Exception as e:
        if journal is not None:
            journal._repli("echec_%s" % type(e).__name__)
        return data, None


def _est_monochrome(im, echantillon=2000) -> bool:
    """Vrai si l'image n'a de fait pas de couleur (scan noir et blanc)."""
    try:
        pts = im.resize((40, 50)).getdata()
        for r, g, b in list(pts)[:echantillon]:
            if abs(r - g) > 12 or abs(g - b) > 12:
                return False
        return True
    except Exception:
        return False


def _pdfium():
    try:
        import pypdfium2                # noqa: F401
        return pypdfium2
    except Exception:
        return None


def pages_pdf(data: bytes, *, cote_max=COTE_MAX, qualite=QUALITE_JPEG,
              journal: Journal | None = None):
    """Rasterise un PDF page par page en JPEG réduit.

    Renvoie une liste de `(data, "image/jpeg")`, une entrée par page — ce qui
    permet de traiter chaque page séparément (segmentation, axe 4.1) au lieu
    d'envoyer tout le PDF dans un seul appel. Liste vide si la rasterisation
    est impossible : l'appelant enverra alors le PDF brut, et le repli est
    journalisé."""
    pdfium = _pdfium()
    if pdfium is None:
        if journal is not None:
            journal.pieces += 1
            journal._repli("pypdfium2_absent")
        return []
    try:
        doc = pdfium.PdfDocument(data)
        out = []
        for i in range(len(doc)):
            page = doc[i]
            # échelle visée : ~1500 px sur le plus grand côté (72 pt = 1 pouce)
            larg_pt, haut_pt = page.get_size()
            ech = cote_max / float(max(larg_pt, haut_pt)) if max(larg_pt, haut_pt) else 2.0
            img = page.render(scale=max(0.5, min(ech, 4.0))).to_pil()
            buf = io.BytesIO()
            img.convert("RGB").save(buf, format="JPEG", quality=qualite, optimize=True)
            if journal is not None:
                journal.pieces += 1
                journal.reduites += 1
                journal.tokens_avant += tokens_image(int(larg_pt * 300 / 72),
                                                     int(haut_pt * 300 / 72))
                journal.tokens_apres += tokens_image(*img.size)
            out.append((buf.getvalue(), "image/jpeg"))
        return out
    except Exception as e:
        if journal is not None:
            journal.pieces += 1
            journal._repli("echec_pdf_%s" % type(e).__name__)
        return []


def preparer(chemin: str, *, cote_max=COTE_MAX, qualite=QUALITE_JPEG,
             journal: Journal | None = None):
    """Prépare une pièce pour l'envoi. Renvoie une liste de blocs
    `(genre, media_type, data)` : une entrée par page pour un PDF rasterisé,
    une seule sinon. Le repli renvoie la pièce brute, journalisée."""
    ext = os.path.splitext(chemin)[1].lower()
    with open(chemin, "rb") as f:
        brut = f.read()

    if ext == ".pdf":
        pages = pages_pdf(brut, cote_max=cote_max, qualite=qualite, journal=journal)
        if pages:
            return [("image", media, data) for data, media in pages]
        return [("document", "application/pdf", brut)]   # repli déjà journalisé

    data, media = reduire_image(brut, cote_max=cote_max, qualite=qualite,
                                journal=journal)
    if media is None:
        from .client_anthropic import _MEDIA
        _genre, media_brut = _MEDIA.get(ext, ("document", "application/pdf"))
        return [(_genre, media_brut, data)]              # repli déjà journalisé
    return [("image", media, data)]
