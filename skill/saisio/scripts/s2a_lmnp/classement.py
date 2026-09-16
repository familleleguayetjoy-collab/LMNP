"""Classement du document AVANT toute extraction comptable — garde-fou d'entrée.

Le client dépose dans son Drive tout ce qui lui tombe sous la main : devis, bons
de commande, relevés bancaires, contrats, photos floues, captures prises par
erreur. Sans cette étape, un devis est extrait comme une facture (fournisseur,
date, TTC) et finit par produire une écriture. La règle du cabinet est nette :
**un devis ne devient jamais une facture**.

Trois garde-fous, appliqués dans cet ordre :

  1. `categorie` est le PREMIER champ du schéma de sortie. En génération
     structurée le modèle produit les champs dans l'ordre déclaré : s'il extrait
     le fournisseur et le montant avant de se prononcer sur la nature de la
     pièce, il a déjà raisonné « facture » et ne fait plus que confirmer. En
     plaçant la catégorie d'abord, il s'engage avant d'extraire.
  2. Une catégorie non comptable DOIT venir avec des champs comptables vides.
     Tout objet qui viole ça est rejeté : c'est le signe que le modèle a extrait
     d'abord et classé ensuite (cf. 1), donc que son classement ne vaut rien.
  3. Une écriture n'est proposée que si la catégorie est comptable, que les
     champs obligatoires sont présents, et que HT + TVA = TTC au centime près.

Rien n'est jamais écarté en silence : chaque pièce refusée sort avec un motif,
et le pipeline la remonte dans le rapport de fin de traitement.
"""
from __future__ import annotations

from .normalize import cents

# --- catégories -------------------------------------------------------------
# Seules ces trois catégories déclenchent une extraction et une écriture.
CAT_ACHAT = "facture_achat"
CAT_VENTE = "facture_vente"
CAT_AVOIR = "avoir"
CATEGORIES_COMPTABLES = (CAT_ACHAT, CAT_VENTE, CAT_AVOIR)

# Catégories reconnues mais non comptables -> `À_vérifier/`, aucune écriture.
CATEGORIES_AUTRES = (
    "devis", "bon_commande", "releve_bancaire", "contrat",
    "illisible", "hors_sujet",
)
CATEGORIES = CATEGORIES_COMPTABLES + CATEGORIES_AUTRES

# Sous ce seuil de confiance de CLASSEMENT, on rejoue sur le modèle fort ;
# si le doute persiste, remontée humaine (jamais d'écriture au doute).
SEUIL_CLASSEMENT = 0.80

# Champs qui doivent être vides quand la catégorie n'est pas comptable.
CHAMPS_COMPTABLES = ("fournisseur", "date", "ttc", "tva", "ht", "numero")

# Tolérance du contrôle HT + TVA = TTC (en centimes) : couvre les arrondis
# de TVA ligne à ligne d'un fournisseur, pas une incohérence réelle.
TOLERANCE_TTC_CENTIMES = 2


def est_comptable(categorie: str) -> bool:
    """Vrai si la catégorie autorise une extraction et une écriture."""
    return (categorie or "").strip().lower() in CATEGORIES_COMPTABLES


def _vide(v) -> bool:
    """Un champ comptable est « vide » s'il est absent, chaîne vide, ou zéro."""
    if v is None:
        return True
    if isinstance(v, str):
        return not v.strip()
    if isinstance(v, (int, float)):
        return cents(v) == 0
    return False


def coherence_ttc(ht, tva, ttc, tolerance=TOLERANCE_TTC_CENTIMES) -> bool:
    """HT + TVA = TTC, au centime près. Si HT et TVA sont absents (cas courant
    d'un ticket sans détail), le contrôle ne s'applique pas — on ne rejette pas
    une pièce pour une information que le fournisseur n'a pas imprimée."""
    if _vide(ht) and _vide(tva):
        return True
    return abs(cents(ht) + cents(tva) - cents(ttc)) <= tolerance


def valider(brut: dict, *, seuil_classement=SEUIL_CLASSEMENT,
            seuil_ocr=None) -> tuple[bool, str]:
    """Contrôle un objet brut renvoyé par l'OCR.

    Renvoie `(retenu, motif)`. `retenu=True` -> la pièce peut produire une
    écriture. Sinon `motif` dit pourquoi, en clair, pour le rapport de fin de
    traitement et le déplacement vers `À_vérifier/`.
    """
    if seuil_ocr is None:                     # import tardif : évite un cycle
        from .ia import SEUIL_CONFIANCE_OCR
        seuil_ocr = SEUIL_CONFIANCE_OCR

    cat = (brut.get("categorie") or "").strip().lower()
    if not cat:
        return False, "catégorie absente : le document n'a pas été classé"
    if cat not in CATEGORIES:
        return False, "catégorie inconnue « %s »" % cat

    conf_cl = float(brut.get("confiance_classement") or 0.0)

    # -- catégorie non comptable : aucune écriture, jamais ------------------
    if not est_comptable(cat):
        remplis = [c for c in CHAMPS_COMPTABLES if not _vide(brut.get(c))]
        if remplis:
            # Le modèle a extrait avant de classer -> son classement n'est pas
            # fiable, et surtout on refuse de laisser passer un devis chiffré.
            return False, ("document « %s » avec des champs comptables remplis (%s) : "
                           "extraction refusée" % (cat, ", ".join(remplis)))
        return False, "document « %s » : non comptable, aucune écriture" % cat

    # -- catégorie comptable : classement sûr ? ----------------------------
    if conf_cl < seuil_classement:
        return False, ("classement « %s » peu sûr (%.2f < %.2f) : "
                       "vérification humaine" % (cat, conf_cl, seuil_classement))

    # -- champs obligatoires ------------------------------------------------
    manquants = [c for c in ("fournisseur", "date", "ttc") if _vide(brut.get(c))]
    if manquants:
        return False, "champs obligatoires manquants : %s" % ", ".join(manquants)

    # -- confiance d'extraction --------------------------------------------
    conf_ocr = float(brut.get("confiance") or 0.0)
    if conf_ocr < seuil_ocr:
        return False, ("extraction peu sûre (%.2f < %.2f) : vérification humaine"
                       % (conf_ocr, seuil_ocr))

    # -- cohérence des montants --------------------------------------------
    if not coherence_ttc(brut.get("ht"), brut.get("tva"), brut.get("ttc")):
        return False, ("incohérence des montants : HT %.2f + TVA %.2f ≠ TTC %.2f"
                       % (float(brut.get("ht") or 0), float(brut.get("tva") or 0),
                          float(brut.get("ttc") or 0)))

    return True, ""


def trier(bruts, *, seuil_classement=SEUIL_CLASSEMENT) -> tuple[list, list]:
    """Sépare les objets bruts de l'OCR en `(retenus, rejets)`.

    `retenus` : les dicts qui peuvent devenir des `Facture`.
    `rejets`  : `{"brut": dict, "categorie": str, "motif": str}` — destinés au
                rapport de fin de traitement et à `À_vérifier/`. Aucune pièce
                n'est perdue en silence."""
    retenus, rejets = [], []
    for b in bruts or []:
        ok, motif = valider(b, seuil_classement=seuil_classement)
        if ok:
            retenus.append(b)
        else:
            rejets.append({
                "brut": b,
                "categorie": (b.get("categorie") or "").strip().lower(),
                "motif": motif,
            })
    return retenus, rejets


def sens_ecriture(categorie: str) -> str:
    """Sens de l'écriture selon la catégorie. Un AVOIR produit une écriture de
    sens inverse d'une facture d'achat — c'est la règle demandée."""
    cat = (categorie or "").strip().lower()
    if cat == CAT_AVOIR:
        return "C"        # avoir fournisseur : recette / annulation de charge
    if cat == CAT_VENTE:
        return "C"        # facture de vente : produit
    return "D"            # facture d'achat : charge
