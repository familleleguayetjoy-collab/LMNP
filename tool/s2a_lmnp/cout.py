"""Mesure du coût API — tokens réellement consommés, pas une estimation.

Le moteur affichait jusqu'ici `cout_ia_estime_eur` calculé par une constante
écrite à la main (`0,008 × nb_factures`). C'était pire qu'un vide : ça donnait
l'illusion d'une mesure, donc la dérive serait passée inaperçue. Ce module lit
`response.usage` à chaque appel et calcule le coût réel.

Tarifs publics Anthropic, en dollars par million de tokens. Le cache se facture
à l'écriture (majorée) et à la lecture (~10 % du tarif d'entrée) : c'est
exactement ce qu'on veut voir chiffré, puisque le taux de lecture de cache est
l'indicateur de santé du dossier.
"""
from __future__ import annotations
from dataclasses import dataclass, field

# $ / million de tokens : (entrée, sortie). Écriture de cache = entrée × 1,25 ;
# lecture de cache = entrée × 0,10.
TARIFS = {
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-sonnet-5":  (2.00, 10.00),
    "claude-opus-5":    (5.00, 25.00),
}
MULT_ECRITURE_CACHE = 1.25
MULT_LECTURE_CACHE = 0.10
USD_EUR = 0.92                      # ordre de grandeur ; le pilotage se fait en €

# Un dossier normal de 200 factures doit coûter 0,50 à 0,80 €. Au-delà de ce
# plafond, il y a un problème (cache invalidé, images non réduites, escalade
# massive) et il faut le voir tout de suite.
ALERTE_DOSSIER_EUR = 3.00
# Sous ce taux de lecture de cache sur un dossier de 200 factures, il y a un bug.
CIBLE_LECTURE_CACHE = 0.90


def _n(usage, *noms):
    """Lit un champ d'usage quel que soit son nom exact, 0 si absent."""
    for nom in noms:
        v = getattr(usage, nom, None)
        if v is None and isinstance(usage, dict):
            v = usage.get(nom)
        if v is not None:
            return int(v)
    return 0


@dataclass
class Compteur:
    """Accumule l'usage réel de tous les appels d'un dossier."""
    entree: int = 0
    sortie: int = 0
    cache_ecriture: int = 0
    cache_lecture: int = 0
    appels: int = 0
    par_modele: dict = field(default_factory=dict)

    def enregistrer(self, modele: str, usage) -> None:
        """Enregistre l'usage d'un appel. Tolère un usage absent (tests)."""
        self.appels += 1
        if usage is None:
            return
        e = _n(usage, "input_tokens")
        s = _n(usage, "output_tokens")
        ce = _n(usage, "cache_creation_input_tokens")
        cl = _n(usage, "cache_read_input_tokens")
        self.entree += e
        self.sortie += s
        self.cache_ecriture += ce
        self.cache_lecture += cl
        m = self.par_modele.setdefault(
            modele, {"appels": 0, "entree": 0, "sortie": 0,
                     "cache_ecriture": 0, "cache_lecture": 0})
        m["appels"] += 1
        m["entree"] += e
        m["sortie"] += s
        m["cache_ecriture"] += ce
        m["cache_lecture"] += cl

    # -- coût ---------------------------------------------------------------
    @staticmethod
    def _cout_usd(modele, entree, sortie, cache_ecriture, cache_lecture) -> float:
        t_in, t_out = TARIFS.get(modele, TARIFS["claude-sonnet-5"])
        return (entree / 1e6 * t_in
                + sortie / 1e6 * t_out
                + cache_ecriture / 1e6 * t_in * MULT_ECRITURE_CACHE
                + cache_lecture / 1e6 * t_in * MULT_LECTURE_CACHE)

    @property
    def cout_usd(self) -> float:
        if self.par_modele:
            return sum(self._cout_usd(m, d["entree"], d["sortie"],
                                      d["cache_ecriture"], d["cache_lecture"])
                       for m, d in self.par_modele.items())
        return 0.0

    @property
    def cout_eur(self) -> float:
        return self.cout_usd * USD_EUR

    @property
    def taux_lecture_cache(self) -> float:
        """Taux de RÉUTILISATION DU PRÉFIXE : part des présentations du préfixe
        servies par le cache plutôt que réécrites.

        C'est la bonne mesure de santé, et elle diffère de « part des tokens
        d'entrée servis par le cache ». Sur un dossier de 200 factures, le
        préfixe (~2 500 tokens) est écrit une fois puis relu 199 fois -> 99,5 %
        ici, alors que la part des tokens d'entrée plafonnerait vers 60 % parce
        que les IMAGES, non cachables et variables par nature, dominent le
        volume. Viser 90 % sur ce second ratio serait inatteignable même avec un
        cache parfait, et masquerait le vrai signal.
        """
        presentations = self.cache_lecture + self.cache_ecriture
        return (self.cache_lecture / presentations) if presentations else 0.0

    @property
    def part_entree_cachee(self) -> float:
        """Part des tokens d'entrée servis par le cache — informatif seulement
        (dominé par les images, cf. `taux_lecture_cache`)."""
        total = self.entree + self.cache_ecriture + self.cache_lecture
        return (self.cache_lecture / total) if total else 0.0

    def alerte(self, *, plafond=ALERTE_DOSSIER_EUR, nb_factures=0) -> str:
        """Message d'alerte si le dossier dérive, sinon ''."""
        msgs = []
        if self.cout_eur > plafond:
            msgs.append("coût %.2f € > plafond %.2f €" % (self.cout_eur, plafond))
        if nb_factures >= 50 and self.taux_lecture_cache < CIBLE_LECTURE_CACHE:
            msgs.append("réutilisation du préfixe %.0f %% < %.0f %% attendus "
                        "(préfixe invalidé : horodatage, identifiant ou compteur "
                        "dans le prompt système ?)"
                        % (100 * self.taux_lecture_cache, 100 * CIBLE_LECTURE_CACHE))
        return ("ALERTE coût : " + " ; ".join(msgs)) if msgs else ""

    def resume(self, *, nb_factures=0) -> dict:
        """Vue exposée au tableau de bord — chiffres mesurés, pas estimés."""
        return {
            "appels": self.appels,
            "tokens_entree": self.entree,
            "tokens_sortie": self.sortie,
            "tokens_cache_ecriture": self.cache_ecriture,
            "tokens_cache_lecture": self.cache_lecture,
            "taux_lecture_cache": round(self.taux_lecture_cache, 4),
            "part_entree_cachee": round(self.part_entree_cachee, 4),
            "cout_usd": round(self.cout_usd, 4),
            "cout_eur": round(self.cout_eur, 4),
            "cout_eur_par_facture": (round(self.cout_eur / nb_factures, 5)
                                     if nb_factures else 0.0),
            "par_modele": {m: dict(d) for m, d in self.par_modele.items()},
            "alerte": self.alerte(nb_factures=nb_factures),
        }
