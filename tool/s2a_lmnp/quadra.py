"""Export / lecture au format Quadratus ASCII (Cegid Quadra).

Format calibré sur un vrai fichier Quadra du cabinet (dossier DUMDUM,
journal BQ). Enregistrement 'Mouvement' (type M), largeur fixe **251**,
contrepartie **en ligne** (champ 56-63) : Quadra génère l'écriture inverse,
on ne produit donc **qu'une seule ligne M par opération**.

Positions (1-based, inclusives) — vérifiées par aller-retour octet à octet :
  1     (1)  type 'M'
  2-9   (8)  compte (cadré à gauche, complété d'espaces)
  10-11 (2)  code journal (BQ, OD, AC, VE...)
  12-14 (3)  folio ('000')
  15-20 (6)  date JJMMAA
  21    (1)  espace
  22-41 (20) libellé court
  42    (1)  sens 'D'/'C'
  43    (1)  signe ('+')
  44-55 (12) montant en centimes (cadré à droite, zéros)
  56-63 (8)  compte de contrepartie EN LIGNE (vide = mode relevé importé)
  64-69 (6)  constante '000000'
  108-110 (3) devise 'EUR'
  111-113 (3) code journal étendu ('BQ1')
  117-203 (87) libellé long
  204-213 (10) n° de pièce
  214-217 (4)  source ('_ASC', 'PL  '...)
  218-231 (14) horodatage JJMMAAAAHHMMSS
  232-251 (20) espaces de fin

Tout ce qui touche aux montants reste du code (jamais l'IA). Contrôle
d'équilibre par construction : chaque ligne porte sa contrepartie.
"""
from __future__ import annotations
import datetime
from .normalize import strip_accents, cents

LARGEUR = 251

# Bornes des champs (1-based, inclusives) -> tranches Python (a-1, b)
_CH = {
    "type":    (1, 1),
    "compte":  (2, 9),
    "journal": (10, 11),
    "folio":   (12, 14),
    "date":    (15, 20),
    "libelle": (22, 41),
    "sens":    (42, 42),
    "signe":   (43, 43),
    "montant": (44, 55),
    "contrep": (56, 63),
    "cst64":   (64, 69),
    "devise":  (108, 110),
    "journal3":(111, 113),
    "liblong": (117, 203),
    "piece":   (204, 213),
    "source":  (214, 217),
    "horodate":(218, 231),
}


def _sl(pos):
    a, b = _CH[pos]
    return slice(a - 1, b)


def _clean(s):
    s = strip_accents(str(s or ""))
    s = "".join(c if (c.isalnum() or c in " &-.'/,") else " " for c in s)
    return " ".join(s.split())


def _txt(s, n, upper=False):
    s = _clean(s)
    if upper:
        s = s.upper()
    return s[:n].ljust(n)


def _num(v, n):
    c = str(cents(v))
    if len(c) > n:
        raise ValueError("montant trop grand pour %d chiffres: %s" % (n, c))
    return c.rjust(n, "0")


def _date(d):
    return "%02d%02d%02d" % (d.day, d.month, d.year % 100)


def format_mouvement(compte, journal, date, libelle, sens, montant,
                     contrepartie="", piece=1, source="_IMP", horodate=None,
                     folio="000", journal3=None, libelle_long=None):
    """Construit une ligne M de 251 caractères, positionnellement exacte."""
    if sens not in ("D", "C"):
        raise ValueError("sens doit etre 'D' ou 'C', recu %r" % sens)
    if horodate is None:
        horodate = datetime.datetime.now()
    if isinstance(horodate, (datetime.datetime, datetime.date)):
        hh = horodate if isinstance(horodate, datetime.datetime) else \
            datetime.datetime(horodate.year, horodate.month, horodate.day)
        horodate = "%02d%02d%04d%02d%02d%02d" % (
            hh.day, hh.month, hh.year, hh.hour, hh.minute, hh.second)
    if journal3 is None:
        journal3 = (_txt(journal, 2).strip() + "1")
    if libelle_long is None:
        libelle_long = libelle

    b = [" "] * LARGEUR

    def put(name, s):
        a = _CH[name][0] - 1
        for i, ch in enumerate(s):
            b[a + i] = ch

    put("type", "M")
    put("compte", _txt(compte, 8))
    put("journal", _txt(journal, 2, upper=True))
    put("folio", _txt(folio, 3))
    put("date", _date(date))
    put("libelle", _txt(libelle, 20))
    put("sens", sens)
    put("signe", "+")
    put("montant", _num(montant, 12))
    put("contrep", _txt(contrepartie, 8))
    put("cst64", "000000")
    put("devise", "EUR")
    put("journal3", _txt(journal3, 3, upper=True))
    put("liblong", _txt(libelle_long, 87))
    put("piece", str(int(piece)).rjust(10, "0"))
    put("source", str(source)[:4].ljust(4))
    put("horodate", horodate[:14].ljust(14))
    return "".join(b)


def parse_mouvement(ligne):
    """Lit une ligne M en dict de champs bruts (chaînes, non nettoyées)."""
    if not ligne or ligne[0] != "M":
        raise ValueError("pas une ligne de mouvement (M)")
    ligne = ligne.rstrip("\r\n")
    return {k: ligne[_sl(k)] for k in _CH}


def _compte_pad(compte, n=8):
    """Compte comptable cadré comme dans Quadra (droite complétée de zéros)."""
    c = "".join(ch for ch in str(compte) if ch.isdigit())
    return (c + "0" * n)[:n]


def to_quadratus(ops, avec_banque: bool = True, compte_banque: str = "512",
                 journal: str = None, source: str = "_IMP",
                 horodate=None, piece_depart: int = 1) -> str:
    """Journal d'import Quadra à partir d'opérations codées.

    avec_banque=True  -> journal BQ, contrepartie = compte banque (512...)
    avec_banque=False -> journal OD, contrepartie = 108 (compte exploitant)

    Une ligne M par mouvement ; la contrepartie est en ligne (Quadra génère
    l'écriture inverse). Le prêt (op.split) donne 2 lignes 661 + 164.
    """
    jr = journal or ("BQ" if avec_banque else "OD")
    contrep = _compte_pad(compte_banque if avec_banque else "108")
    out, p = [], piece_depart
    for op in ops:
        d, lib, m = op.date, op.libelle, op.montant
        if op.split:  # échéance de prêt : intérêts (661) + capital (164)
            interets, capital = op.split
            out.append(format_mouvement("661", jr, d, lib + " INTERETS", "D",
                                        interets, contrep, p, source, horodate))
            out.append(format_mouvement("164", jr, d, lib + " CAPITAL", "D",
                                        capital, contrep, p, source, horodate))
            p += 1
            continue
        compte = _compte_pad(op.compte or "471")
        out.append(format_mouvement(compte, jr, d, lib, op.sens, m,
                                    contrep, p, source, horodate))
        p += 1
    return "\r\n".join(out) + "\r\n"


def decoder_fichier(raw) -> list:
    """Décode un fichier Quadra ASCII en lignes (bytes -> texte cp1252)."""
    if isinstance(raw, bytes):
        for enc in ("cp1252", "latin-1"):
            try:
                raw = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            raw = raw.decode("latin-1", errors="replace")
    return [l for l in raw.replace("\r", "").split("\n") if l.strip()]


def lire_comptes(raw) -> dict:
    """Plan comptable du dossier depuis les enregistrements 'C' : compte -> libellé."""
    out = {}
    for l in decoder_fichier(raw):
        if l and l[0] == "C":
            num = l[1:9].strip()
            lib = l[9:38].strip()
            if num:
                out[num] = lib
    return out


def lire_mouvements(raw, annee_pivot: int = 2000):
    """Lit les enregistrements 'M' d'un journal Quadra en objets Operation.

    Les lignes sont DÉJÀ codées (compte en position 2-9) : on reconstitue
    l'opération telle qu'elle a été saisie, montant en euros depuis les
    centimes, date depuis JJMMAA. Utile pour relire un relevé bancaire fourni
    au format ASCII, ou contrôler un export.
    """
    import datetime
    from .model import Operation
    ops = []
    for l in decoder_fichier(raw):
        if not l or l[0] != "M":
            continue
        f = parse_mouvement(l)
        jj, mm, aa = int(f["date"][0:2]), int(f["date"][2:4]), int(f["date"][4:6])
        d = datetime.date(annee_pivot + aa, mm, jj)
        montant = int(f["montant"]) / 100.0
        op = Operation(date=d, libelle=f["libelle"].strip(),
                       montant=montant, sens=f["sens"])
        op.compte = f["compte"].strip()
        op.origine = "quadra"
        ops.append(op)
    return ops


def verifier_equilibre(texte: str):
    """Contrôle d'équilibre.

    Chaque ligne porte sa contrepartie en ligne : le mouvement principal
    (débit/crédit selon le sens) est compensé par la contrepartie inverse.
    On vérifie que chaque ligne a bien une contrepartie non vide, et on
    renvoie (débit_principal, crédit_principal, équilibré).
    """
    deb = cred = 0
    ok = True
    for ln in texte.splitlines():
        if not ln or ln[0] != "M":
            continue
        f = parse_mouvement(ln)
        c = int(f["montant"])
        if f["sens"] == "D":
            deb += c
        else:
            cred += c
        if not f["contrep"].strip():
            ok = False  # ligne sans contrepartie en ligne -> non équilibrée seule
    return deb, cred, ok
