#!/usr/bin/env python3
"""Rend la première page de chaque PDF de démonstration en JPEG.

Pourquoi une image plutôt que le PDF : le lecteur PDF du navigateur n'est pas
garanti dans un cadre isolé — dans l'artifact, `<embed type="application/pdf">`
n'affichait qu'un rectangle noir. Une image s'affiche partout.

À relancer seulement quand on ajoute ou remplace une pièce de démonstration ;
les JPEG produits sont versionnés pour que `build.py` n'ait aucune dépendance.

    pip install pypdfium2 Pillow
    python3 build/rendu_pieces.py
"""
import pathlib
import pypdfium2 as pdfium

LARGEUR = 950          # assez pour lire une facture à l'écran, sans excès
QUALITE = 72

pieces = pathlib.Path(__file__).resolve().parent / "assets" / "pieces"
for pdf in sorted(pieces.glob("*.pdf")):
    page = pdfium.PdfDocument(str(pdf))[0]
    img = page.render(scale=LARGEUR / page.get_width()).to_pil().convert("RGB")
    jpg = pdf.with_suffix(".jpg")
    img.save(jpg, "JPEG", quality=QUALITE, optimize=True)
    print("%-24s %s  %d Ko" % (jpg.name, img.size, jpg.stat().st_size // 1024))
