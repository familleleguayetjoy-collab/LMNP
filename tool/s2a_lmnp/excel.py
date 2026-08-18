"""Export Excel (.xlsx) du journal de banque — stdlib pure (zipfile + XML).

Le journal de banque est destiné à être VÉRIFIÉ / MODIFIÉ à la main dans le
logiciel comptable : on le sort en tableau Excel (une ligne par opération,
triées par date), là où les écritures FERMES (OD contrepartie 108) partent en
ASCII prêt à importer. Gère plusieurs banques (une colonne Journal : BQ1, BQ2…).
"""
from __future__ import annotations
import datetime
import io
import zipfile
from xml.sax.saxutils import escape

_ENTETES = ["Journal", "Date", "Compte", "Libellé", "Débit", "Crédit", "Contrepartie", "Pièce"]

_CT = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
       '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
       '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
       '<Default Extension="xml" ContentType="application/xml"/>'
       '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
       '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
       '</Types>')
_RELS = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
         '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
         '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
         '</Relationships>')
_WB = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
       '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
       'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
       '<sheets><sheet name="Journal banque" sheetId="1" r:id="rId1"/></sheets></workbook>')
_WBR = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        '</Relationships>')


def _colref(n):                          # 0 -> A, 1 -> B ...
    s, n = "", n + 1
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def _cell(ref, val):
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        return '<c r="%s"><v>%s</v></c>' % (ref, repr(round(float(val), 2)))
    return ('<c r="%s" t="inlineStr"><is><t xml:space="preserve">%s</t></is></c>'
            % (ref, escape(str(val))))


def _sheet(lignes):
    rows = []
    for i, row in enumerate(lignes, 1):
        cells = "".join(_cell(_colref(j) + str(i), v) for j, v in enumerate(row))
        rows.append('<row r="%d">%s</row>' % (i, cells))
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetData>%s</sheetData></worksheet>' % "".join(rows))


def journaux_banque_depuis_fec(lignes_fec):
    """Map {compte 512 -> code journal} déduite du FEC du dossier.

    Le journal de banque n'est pas toujours « BQ1/BQ2 » : chaque banque est une
    variante d'un compte 512 rattachée à SON code journal. On le lit tel quel
    dans le FEC (le journal qui porte les mouvements de ce 512) — aucune
    convention inventée. Utile pour l'export Excel et le routage multi-banque."""
    m = {}
    for l in lignes_fec:
        c = (getattr(l, "compte", "") or "").strip()
        j = (getattr(l, "journal", "") or "").strip()
        if c.startswith("512") and j and c not in m:
            m[c] = j
    return m


def _jr(o, journaux):
    """Journal de l'opération : dérivé de son compte bancaire 512 (multi-banque).
    À défaut de correspondance, on retombe sur un code générique « BQ »."""
    return journaux.get(getattr(o, "compte_bancaire", "") or "", "BQ")


def lignes_journal_banque(ops, journaux=None, compte_banque="512"):
    """Tableau (liste de lignes) du journal de banque, trié par (journal, date)."""
    journaux = journaux or {}
    ordre = sorted(ops, key=lambda o: (_jr(o, journaux), o.date or datetime.date.min))
    out = [list(_ENTETES)]
    for o in ordre:
        deb = round(o.montant, 2) if o.sens == "D" else ""
        cred = round(o.montant, 2) if o.sens == "C" else ""
        d = o.date.strftime("%d/%m/%Y") if isinstance(o.date, (datetime.date, datetime.datetime)) else str(o.date or "")
        out.append([_jr(o, journaux), d, o.compte or "471", o.libelle or "",
                    deb, cred, compte_banque, getattr(o, "piece", "") or ""])
    return out


def journal_banque_xlsx(ops, chemin=None, journaux=None, compte_banque="512"):
    """Écrit (ou renvoie les octets) d'un .xlsx du journal de banque. Les
    montants sont des nombres (modifiables), les opérations triées par date."""
    lignes = lignes_journal_banque(ops, journaux, compte_banque)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", _CT)
        z.writestr("_rels/.rels", _RELS)
        z.writestr("xl/workbook.xml", _WB)
        z.writestr("xl/_rels/workbook.xml.rels", _WBR)
        z.writestr("xl/worksheets/sheet1.xml", _sheet(lignes))
    data = buf.getvalue()
    if chemin:
        with open(chemin, "wb") as f:
            f.write(data)
    return data
