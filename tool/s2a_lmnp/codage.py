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

# --- charges & recettes récurrentes spécifiques LMNP/LMP/SCI -----------------
_RE_DEPOT   = re.compile(r"DEPOT DE GARANTIE|DEPOT GARANTIE|\bCAUTION\b")
_RE_CAF     = re.compile(r"\bCAF\b|\bAPL\b|ALLOCATION LOGEMENT|ALLOCATIONS FAMILIALES")
_RE_PLATE   = re.compile(r"AIRBNB|BOOKING|ABRITEL|EXPEDIA")
_RE_AVOIR   = re.compile(r"\bAVOIR\b|NOTE DE CREDIT|REMBOURSEMENT")
_RE_EMPRUNT = re.compile(r"EMPRUNT|\bPRET\b|ECHEANCE.*PRET|CREDIT IMMO|CREDIT LOGEMENT|CREDIT HABITAT")
_RE_TXFONC  = re.compile(r"TAXE FONCIERE|TAXE FONC|TX FONC")
_RE_CFE     = re.compile(r"\bCFE\b|COTISATION FONCIERE")
_RE_HONOR   = re.compile(r"HONORAIRE|GESTION LOCATIVE|AGENCE IMMO|EXPERT.?COMPTABLE|\bCOMPTABLE\b")
_RE_ASSUR   = re.compile(r"ASSURANCE|\bPNO\b|\bGLI\b|\bMRH\b|MULTIRISQUE|\bADI\b")
_RE_COPRO   = re.compile(r"SYNDIC|COPROPRIETE|CHARGES COPRO|APPEL DE CHARGES")
_RE_EAU     = re.compile(r"\bEAU\b|VEOLIA|\bSUEZ\b|\bSAUR\b|ASSAINISSEMENT")
_RE_GAZ     = re.compile(r"\bGAZ\b|GRDF|\bGDF\b")
_RE_NOTAIRE = re.compile(r"NOTAIRE|OFFICE NOTARIAL|ACTE AUTHENTIQUE")

# Comptes qui n'appellent jamais de TVA déductible (garde-fou para-hôtelier).
_SANS_TVA = {"165", "108", "455", "512", "51210010", "661", "164", "627", "706", "758"}


def _set(op: Operation, compte, conf, origine, motif="", a_revoir=False, options=None):
    op.compte = compte
    op.confiance = conf
    op.origine = origine
    op.motif = motif
    op.a_revoir = a_revoir
    op.options = options or [compte]
    return op


def coder(op: Operation, dico: Dictionnaire,
          resolver: Optional[Callable[[str], Optional[dict]]] = None,
          assujetti_tva: bool = False) -> Operation:
    """Code une opération. `assujetti_tva=True` (LMNP para-hôtelier, SCI à l'IS,
    meublé de tourisme classé...) : on ne comptabilise PAS le TTC en charge — on
    remonte pour saisie HT + TVA déductible. Par défaut False (LMNP non assujetti,
    ~90 % des dossiers) : le TTC est passé en charge, aucune écriture de TVA."""
    r = _coder(op, dico, resolver)
    # Le FEC du dossier fait loi : on confronte le compte générique au plan RÉEL.
    adapter_au_plan(op, dico)
    if assujetti_tva and op.sens == "D" and (op.compte or "") not in _SANS_TVA:
        note = ("Dossier ASSUJETTI à la TVA : comptabiliser le HT + la TVA déductible "
                "(44566) ; ne pas passer le TTC en charge — à saisir.")
        op.a_confirmer = (op.a_confirmer + " " + note) if op.a_confirmer else note
        op.a_revoir = True
    return r


def adapter_au_plan(op: Operation, dico) -> Operation:
    """Adapte un compte proposé par une RÈGLE GÉNÉRIQUE au plan comptable réel du
    dossier (issu du FEC N-1). Le FEC fait loi — on n'impose jamais notre
    numérotation standard :

      - compte proposé présent dans le plan          -> on garde ;
      - absent, UN seul compte de même racine (3 ch.) -> on l'adopte en silence
        (le dossier code cette nature sur ce compte-là) ;
      - absent, PLUSIEURS candidats de la racine      -> à choisir (souvent :
        quel bien, ex. 614100 Bonaparte / 614200 Lépante) ;
      - aucun compte de la racine                     -> on garde le compte
        générique tel quel. (Le FEC ne liste que les comptes MOUVEMENTÉS en
        classes 6/7/2 ; son silence ne prouve pas l'absence du compte. Le vrai
        contrôle « compte inexistant dans le dossier » est `comptes_absents`,
        qui lit le plan comptable complet de Quadra.)

    N'agit que sur les codages 'regle' : un compte issu du dico (déjà propre au
    dossier), de l'amortissement, de la banque ou proposé par l'IA n'est pas
    retouché. No-op si le plan est vide (pas de FEC)."""
    comptes = dico.comptes if hasattr(dico, "comptes") else set(dico)
    if not comptes:
        return op
    c = op.compte or ""
    if not c or op.origine != "regle" or c in comptes:
        return op
    cands = sorted(x for x in comptes if x[:3] == c[:3])
    if len(cands) == 1:
        op.compte = cands[0]
        op.options = [cands[0]] + [o for o in (op.options or []) if o != cands[0]]
        op.motif = (op.motif or "") + " [compte adapté au plan du dossier : %s→%s]" % (c, cands[0])
    elif len(cands) >= 2:
        op.a_revoir = True
        op.options = cands + [o for o in (op.options or []) if o not in cands]
        op.a_confirmer = ("Plusieurs comptes de racine %s dans ce dossier (%s) — à choisir "
                          "(souvent : quel bien)" % (c[:3], ", ".join(cands)))
    return op


def _coder(op: Operation, dico: Dictionnaire,
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
        # dépôt de garantie reçu : DETTE (165), surtout PAS un produit. Testé
        # avant le loyer car un libellé "CAUTION LOYER" contient le mot LOYER.
        if _RE_DEPOT.search(lib):
            return _set(op, "165", 0.85, "regle",
                        "Dépôt de garantie reçu : dette (165), ne compte PAS en recette",
                        options=["165"])
        # recette encaissée via une plateforme : le montant reçu est NET de
        # commission -> la recette brute + la commission (622) doivent être
        # rétablies. On propose, on ne tranche pas.
        if _RE_PLATE.search(lib):
            return _set(op, "706", 0.60, "regle",
                        "Recette plateforme (Airbnb/Booking...) : montant NET de commission — "
                        "rétablir la recette brute et la commission en 622",
                        a_revoir=True, options=["706", "622"])
        if _RE_LOYER.search(lib) or _RE_CAF.search(lib):
            return _set(op, "706", 0.99, "regle", "Loyer / aide au logement (recette récurrente)")
        if _RE_INDEMN.search(lib):
            return _set(op, "758", 0.80, "regle", "Indemnité d'assurance",
                        options=["758", "791", "616"])          # AUTO (non immo/inconnu/multi)
        if _RE_AVOIR.search(lib):
            return _set(op, "471", 0.0, "regle",
                        "Avoir / remboursement reçu : rattacher au compte de charge d'origine",
                        a_revoir=True, options=["471", "606", "615", "616"])
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
    # échéance de prêt SANS tableau d'amortissement : on ne peut pas ventiler
    # intérêts/capital nous-mêmes -> remonté (surtout ne pas passer 100 % en charge).
    if _RE_EMPRUNT.search(lib):
        return _set(op, "661", 0.50, "regle",
                    "Échéance de prêt : ventiler intérêts (661) / capital (164) — "
                    "tableau d'amortissement requis",
                    a_revoir=True, options=["661", "164", "616"])

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

    # 4b) charges récurrentes LMNP/SCI (fournisseur non connu du FEC N-1).
    #     Ordre : honoraires avant copro (un 'SYNDIC HONORAIRES' = 622, pas 614).
    if _RE_TXFONC.search(lib):
        return _set(op, "63512", 0.90, "regle", "Taxe foncière")
    if _RE_CFE.search(lib):
        return _set(op, "63511", 0.85, "regle", "CFE (cotisation foncière des entreprises)")
    if _RE_HONOR.search(lib):
        return _set(op, "622", 0.85, "regle", "Honoraires (gestion locative / agence / comptable)")
    if _RE_ASSUR.search(lib):
        return _set(op, "616", 0.85, "regle", "Assurance (PNO / GLI / emprunteur)")
    if _RE_COPRO.search(lib):
        return _set(op, "614", 0.80, "regle",
                    "Charges de copropriété courantes (syndic)", options=["614", "615"])
    if _RE_EAU.search(lib):
        return _set(op, "606", 0.80, "regle", "Eau / assainissement")
    if _RE_GAZ.search(lib):
        return _set(op, "606", 0.80, "regle", "Gaz / énergie")
    if _RE_NOTAIRE.search(lib):
        return _set(op, "6226", 0.55, "regle",
                    "Frais de notaire : coût d'acquisition à immobiliser, ou charge sur option — à trancher",
                    a_revoir=True, options=["6226", "2115", "213"])

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
