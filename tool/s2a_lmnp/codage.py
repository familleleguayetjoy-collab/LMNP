"""Codage d'une opération bancaire — déterministe.

Principe (règle du cabinet) : on code automatiquement, SAUF trois cas qui
remontent systématiquement à l'humain :
  1. immobilisation (bien durable AU-DESSUS du seuil) ;
  2. fournisseur inconnu (absent du FEC N-1 et non résolu) ;
  3. fournisseur à imputations multiples en N-1 (ambigu).

TVA — LMNP non assujetti (≈90 % des dossiers) : on comptabilise le **TTC en
entier** en charge/immobilisation ; AUCUNE écriture de TVA n'est générée. La
TVA d'une facture ne sert qu'à apprécier le seuil d'immobilisation (en HT).

SEUIL D'IMMOBILISATION = 50 € HT : en dessous, un achat de nature durable est
passé directement en charge (auto) ; au-dessus, il est remonté « à trancher ».

Aucun montant n'est inventé : l'IA (resolver) ne sert qu'à *proposer un compte*
sur un libellé inconnu ; le montant vient toujours du relevé.
"""
from __future__ import annotations
import re
from typing import Callable, Optional

from .model import Operation
from .dico import Dictionnaire

IMMO = {"2135", "2184", "2313", "2131", "2181"}
SEUIL_IMMO_HT = 50.0  # € HT — sous ce seuil, un bien durable est passé en charge


def _base_ht(op: Operation) -> float:
    """Base d'appréciation du seuil d'immobilisation, en HT.

    On poste toujours le TTC en charge (LMNP non assujetti), mais le seuil
    s'apprécie en HT : si la facture donne la TVA, on retire la TVA ; sinon on
    compare le TTC (approche prudente, qui remonte un peu plus à l'humain)."""
    fac = getattr(op, "facture", None)
    if fac is not None and getattr(fac, "tva", 0):
        return max(op.montant - fac.tva, 0.0)
    return op.montant

_RE_TRAVAUX = re.compile(r"MENUISERIE|MACON|PLOMB|ELECTRICIEN|TRAVAUX|RENOV|CARRELAGE|PEINTURE|ISOLATION|TOITURE|RAVALEMENT")
_RE_APPELFONDS = re.compile(r"APPEL.*FONDS|FONDS.*TRAVAUX|COPRO.*TRAVAUX")
_RE_MOBILIER = re.compile(r"MOBILIER|CONFORAMA|IKEA|\bBUT\b|LITERIE|CANAPE|ELECTROMENAGER|DARTY|BOULANGER|MAISON DU MONDE")
_RE_BRICO = re.compile(r"LEROY MERLIN|CASTORAMA|BRICO|QUINCAILL|WELDOM|POINT P|MR BRICOLAGE")
_RE_FRAIS = re.compile(r"FRAIS.*(TENUE|COMPTE|BANCAIRE)|TENUE DE COMPTE|COMMISSION|AGIOS|COTISATION.*CARTE")
_RE_LOYER = re.compile(r"LOYER")
_RE_INDEMN = re.compile(r"INDEMNI|SINISTRE|REMB.*ASSURANCE")
_RE_APPORT = re.compile(r"APPORT|COMPTE COURANT")


def _set(op: Operation, compte, conf, origine, motif="", a_revoir=False, options=None):
    op.compte = compte
    op.confiance = conf
    op.origine = origine
    op.motif = motif
    op.a_revoir = a_revoir
    op.options = options or [compte]
    return op


def coder(op: Operation, dico: Dictionnaire,
          resolver: Optional[Callable[[str], Optional[dict]]] = None) -> Operation:
    # 0) ligne DÉJÀ codée à l'export bancaire : le logiciel comptable a déjà
    #    pré-affecté le compte (fournisseur paramétré). On lui fait confiance,
    #    on ne recode pas et on ne remonte pas à l'humain. Le rapprochement
    #    avec la facture reste fait par ailleurs (contrôle + anti-doublon).
    if op.compte and getattr(op, "origine", "") in ("quadra", "banque"):
        return _set(op, op.compte, 0.99, "banque",
                    "Déjà codé à l'export bancaire — rapproché, non recodé")

    lib = (op.libelle or "").upper()

    # 1) recettes
    if op.sens == "C":
        if _RE_LOYER.search(lib):
            return _set(op, "706", 0.99, "regle", "Loyer (recette récurrente)")
        if _RE_INDEMN.search(lib):
            return _set(op, "758", 0.80, "regle", "Indemnité d'assurance",
                        options=["758", "791", "616"])          # AUTO (non immo/inconnu/multi)
        if _RE_APPORT.search(lib):
            return _set(op, "108", 0.80, "regle", "Apport de l'exploitant",
                        options=["108", "455"])                 # AUTO
        return _set(op, "471", 0.0, "inconnu", "Recette non identifiée",
                    a_revoir=True, options=["471", "706", "758"])

    # 2) échéance de prêt : ventilée par le tableau d'amortissement (fourni)
    if op.amort:
        op.split = (op.amort[0], op.amort[1])
        return _set(op, "661", 0.97, "amort",
                    "Échéance de prêt : intérêts (661) + capital (164) selon tableau d'amortissement",
                    options=["661"])

    # 3) travaux / appel de fonds -> IMMO à trancher (au-dessus du seuil)
    if _RE_APPELFONDS.search(lib):
        if _base_ht(op) < SEUIL_IMMO_HT:
            return _set(op, "614", 0.85, "regle",
                        "Appel de fonds copropriété — charge (sous le seuil d'immo)")
        return _set(op, "614", 0.55, "regle",
                    "Appel de fonds travaux copropriété — charge (614) ou immobilisation ?",
                    a_revoir=True, options=["614", "615", "2135", "2313"])
    if _RE_TRAVAUX.search(lib):
        if _base_ht(op) < SEUIL_IMMO_HT:
            return _set(op, "615", 0.85, "regle",
                        "Petits travaux d'entretien (sous le seuil d'immo)")
        return _set(op, "2135", 0.55, "regle",
                    "Travaux — entretien (615) ou amélioration à immobiliser (2135) ?",
                    a_revoir=True, options=["615", "2135", "2313"])

    # 4) dictionnaire N-1
    e = dico.exact(op.libelle)
    if e is None:
        best, cov, inter = dico.meilleur_flou(op.libelle)
        if best is not None and cov >= 0.999 and (inter >= 2 or len(best.toks) == 1):
            e = best
        elif best is not None and cov >= 0.6 and inter >= 1:
            # rapprochement flou : proposé mais à confirmer si multi
            if best.multi:
                return _set(op, best.principal, 0.60, "fuzzy",
                            "Plusieurs imputations en N-1 (%s) — à trancher" % ", ".join(best.comptes),
                            a_revoir=True, options=list(best.comptes))
            return _set(op, best.principal, 0.80, "fuzzy",
                        "Rapproché d'un libellé proche du N-1 — à confirmer", options=[best.principal])
    if e is not None:
        if e.multi:
            return _set(op, e.principal, 0.60, "dict",
                        "Ce fournisseur avait plusieurs imputations en N-1 (%s) — à trancher"
                        % ", ".join(sorted(e.comptes)),
                        a_revoir=True, options=list(sorted(e.comptes)))
        compte = e.principal
        rev = compte in IMMO
        return _set(op, compte, 0.97, "dict",
                    ("Immobilisation — à valider" if rev else "Identique au FEC N-1"),
                    a_revoir=rev, options=[compte])

    # 5) frais bancaires (libellés variables)
    if _RE_FRAIS.search(lib):
        return _set(op, "627", 0.92, "regle", "Frais bancaires")

    # 6) immobilisations / arbitrages identifiables mais à trancher (au-dessus du seuil)
    if _RE_MOBILIER.search(lib):
        if _base_ht(op) < SEUIL_IMMO_HT:
            return _set(op, "606", 0.85, "regle",
                        "Petit équipement (sous le seuil d'immo)")
        return _set(op, "2184", 0.60, "regle",
                    "Achat de mobilier — immobilisation (2184) à amortir ?",
                    a_revoir=True, options=["2184", "606", "615"])
    if _RE_BRICO.search(lib):
        if _base_ht(op) < SEUIL_IMMO_HT:
            return _set(op, "606", 0.85, "regle",
                        "Petit équipement de bricolage (sous le seuil d'immo)")
        return _set(op, "615", 0.60, "regle",
                    "Grande surface de bricolage — entretien (615) ou immobilisation ?",
                    a_revoir=True, options=["615", "2135", "2184"])

    # 7) fournisseur inconnu -> resolver (recherche web / IA) qui PROPOSE un compte
    if resolver is not None:
        r = resolver(op.libelle)
        if r and r.get("compte"):
            # proposé par l'IA : on remonte quand même à l'humain (fournisseur inconnu)
            return _set(op, r["compte"], 0.70, "web",
                        "Fournisseur inconnu — proposition par recherche : %s" % r.get("note", ""),
                        a_revoir=True, options=[r["compte"], "471"])

    # 8) vraiment inconnu
    return _set(op, "471", 0.0, "inconnu", "Fournisseur inconnu — à qualifier",
                a_revoir=True, options=["471"])
