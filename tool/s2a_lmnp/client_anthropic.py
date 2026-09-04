"""Implémentation réelle de `ClientIA` sur l'API Claude (le SEUL point où le
moteur parle à Anthropic). Tout le reste du moteur ignore Anthropic.

Sûreté (rappel, appliqué ici) :
  - Le montant extrait par OCR ne sert QU'À rapprocher : jamais posté.
  - La résolution ne choisit un compte QUE parmi les options des règles ; le
    schéma de sortie n'a pas de champ montant → l'IA ne peut pas en décider un.
  - Modèle par défaut Haiku 4.5 (coût), escalade Sonnet 5 si confiance faible.

La clé API est lue depuis l'environnement (`ANTHROPIC_API_KEY`) — jamais écrite
dans le code ni commitée. Le paquet `anthropic` est importé paresseusement pour
que le cœur du moteur (stdlib pur) reste importable sans lui.

RGPD : les factures/relevés envoyés ici sont des données personnelles de clients
→ DPA signé + rétention zéro / opt-out entraînement côté console Anthropic.
"""
from __future__ import annotations
import base64
import json
import os
from typing import Optional

from .classement import CATEGORIES, SEUIL_CLASSEMENT, est_comptable

MODELE_DEFAUT = "claude-haiku-4-5"
MODELE_ESCALADE = "claude-sonnet-5"
SEUIL_ESCALADE = 0.60          # sous cette confiance, on repasse sur Sonnet

_MEDIA = {
    ".pdf": ("document", "application/pdf"),
    ".png": ("image", "image/png"),
    ".jpg": ("image", "image/jpeg"),
    ".jpeg": ("image", "image/jpeg"),
    ".webp": ("image", "image/webp"),
    ".gif": ("image", "image/gif"),
}

# --- schémas de sortie structurée (garde-fous du contrat, cf. ia.py) ---------

_SCHEMA_RESOLUTION = {
    "type": "object",
    "properties": {
        "reponses": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "compte": {"type": "string"},
                    "confiance": {"type": "number"},
                    "raison": {"type": "string"},
                },
                "required": ["id", "compte", "confiance", "raison"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["reponses"],
    "additionalProperties": False,
}

_SCHEMA_FACTURE = {
    "type": "object",
    "properties": {
        "factures": {
            "type": "array",
            "items": {
                "type": "object",
                # ORDRE VOLONTAIRE : `categorie` et `confiance_classement` en
                # PREMIER. En génération structurée le modèle produit les champs
                # dans l'ordre déclaré ; s'il extrayait le fournisseur et le
                # montant d'abord, il aurait déjà raisonné « facture » et ne
                # ferait plus que confirmer. Il doit s'engager avant d'extraire.
                "properties": {
                    "categorie": {"type": "string", "enum": list(CATEGORIES)},
                    "confiance_classement": {"type": "number"},
                    "fournisseur": {"type": "string"},
                    "date": {"type": "string"},
                    "ttc": {"type": "number"},
                    "tva": {"type": "number"},
                    "ht": {"type": "number"},
                    "numero": {"type": "string"},
                    "adresse_bien": {"type": "string"},
                    "date_flux": {"type": "string"},
                    "confiance": {"type": "number"},
                },
                "required": ["categorie", "confiance_classement",
                             "fournisseur", "date", "ttc", "tva", "ht",
                             "numero", "adresse_bien", "date_flux", "confiance"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["factures"],
    "additionalProperties": False,
}

_SYS_RESOLUTION = (
    "Tu es assistant d'un cabinet d'expertise comptable (dossiers LMNP/LMP/SCI). "
    "On te donne des opérations bancaires que des règles automatiques n'ont pas su "
    "trancher. Pour CHAQUE opération, choisis le compte du plan comptable français "
    "le plus probable. Si 'options' est non vide, choisis STRICTEMENT dans cette "
    "liste. Si 'inconnu' est vrai (fournisseur non identifié par les règles), "
    "propose le compte du plan comptable le plus probable en raisonnant comme un "
    "expert-comptable expérimenté (fournisseur, nature de la dépense). Donne une "
    "confiance 0-1 : élevée (>0,85) seulement si tu es réellement sûr — sous ce "
    "seuil l'écriture sera revue par un humain. Ne raisonne jamais sur le montant : il "
    "est donné à titre informatif et ne doit pas influencer le compte au-delà de "
    "l'ordre de grandeur. Donne une confiance entre 0 et 1 et une raison courte. "
    "Réponds uniquement via le format structuré demandé."
)

_SYS_OCR = (
    "Tu lis des pièces déposées par un client dans le Drive d'un cabinet comptable. "
    "Le client dépose souvent autre chose qu'une facture : devis, bon de commande, "
    "relevé bancaire, contrat, photo floue, capture prise par erreur.\n"
    "\n"
    "ÉTAPE 1 — CLASSE LA PIÈCE AVANT DE L'EXTRAIRE. Renseigne 'categorie' en premier, "
    "parmi : facture_achat, facture_vente, avoir, devis, bon_commande, "
    "releve_bancaire, contrat, illisible, hors_sujet. Donne 'confiance_classement' "
    "entre 0 et 1.\n"
    "  - Un DEVIS n'est pas une facture, même s'il porte un total et un fournisseur. "
    "Indices : « Devis », « Proposition », « Offre », « Estimation », « valable "
    "jusqu'au », « bon pour accord », absence de numéro de facture.\n"
    "  - Un BON DE COMMANDE n'est pas une facture (« Commande n° », « à livrer »).\n"
    "  - Un AVOIR est une facture négative (« Avoir », « Note de crédit », "
    "« Remboursement ») : classe-le 'avoir', jamais 'facture_achat'.\n"
    "\n"
    "ÉTAPE 2 — N'EXTRAIS LES CHAMPS COMPTABLES QUE SI la catégorie est "
    "facture_achat, facture_vente ou avoir. Pour TOUTE autre catégorie, laisse "
    "fournisseur/numero/adresse_bien/date/date_flux à '' et ttc/tva/ht à 0. "
    "C'est impératif : un devis dont tu remplis le montant sera rejeté en bloc.\n"
    "\n"
    "Règles d'extraction, tirées de vraies pièces :\n"
    "1. Travaille sur l'IMAGE, pas une couche texte (les tickets thermiques ont une "
    "couche texte illisible).\n"
    "2. Extrais le TOTAL TTC de la facture — jamais l'espèce remise ni le rendu "
    "(ex. 'Espèces 81,07 / Rendu 10,00' alors que le TTC est 71,07).\n"
    "3. Ignore tout bloc filigrané ou marqué 'EXEMPLE' : ancre-toi sur le total réel "
    "en page 1 ('Facture TTC', 'Montant soumis à TVA').\n"
    "4. Le fournisseur = le nom commercial (EDF, BRICO DEPOT, BOUYGUES TELECOM), pas "
    "l'adresse du bien loué.\n"
    "5. Remonte l'adresse du bien si présente (elle sert à router vers le bon "
    "sous-compte), la date de facture, la TVA et le HT si donnés, le 'prélevé le' si "
    "présent. Mets des champs vides ('' ou 0) si une info est absente — n'invente rien.\n"
    "Le montant que tu lis sert UNIQUEMENT au rapprochement, jamais à décider seul "
    "d'une écriture. Donne une confiance d'extraction entre 0 et 1."
)


class ClientAnthropic:
    """Client réel conforme au protocole `ClientIA` (voir ia.py)."""

    def __init__(self, api_key: Optional[str] = None,
                 modele: str = MODELE_DEFAUT,
                 modele_escalade: str = MODELE_ESCALADE):
        import anthropic  # import paresseux : le cœur du moteur n'en dépend pas
        cle = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not cle:
            raise RuntimeError(
                "Clé API absente : exporte ANTHROPIC_API_KEY (jamais en dur dans le code)."
            )
        self._client = anthropic.Anthropic(api_key=cle)
        self.modele = modele
        self.modele_escalade = modele_escalade
        # Journal du prétraitement : compte les replis (dépendance absente,
        # échec de rasterisation) et l'économie de tokens. Exposé au tableau
        # de bord ; alerte au-delà de 5 % de replis sur un lot.
        from .pretraitement import Journal
        self.journal_pretraitement = Journal()

    # -- appel bas niveau : messages + sortie JSON structurée ---------------
    def _json(self, modele, systeme, contenu, schema, max_tokens=2000):
        rep = self._client.messages.create(
            model=modele,
            max_tokens=max_tokens,
            system=systeme,
            output_config={"format": {"type": "json_schema", "schema": schema}},
            messages=[{"role": "user", "content": contenu}],
        )
        txt = next((b.text for b in rep.content if b.type == "text"), "{}")
        return json.loads(txt)

    # -- B. résolution du résidu (contrat B) --------------------------------
    def resoudre(self, questions, *, modele: str | None = None):
        if not questions:
            return []
        mod = modele or self.modele
        contenu = ("Opérations à trancher (JSON) :\n"
                   + json.dumps(questions, ensure_ascii=False, indent=2))
        out = self._json(mod, _SYS_RESOLUTION, contenu, _SCHEMA_RESOLUTION)
        reponses = out.get("reponses", [])

        # escalade : les réponses peu sûres sont rejouées sur un modèle plus fort
        if mod != self.modele_escalade:
            faibles = {r["id"] for r in reponses
                       if float(r.get("confiance", 0)) < SEUIL_ESCALADE}
            if faibles:
                rejouees = self.resoudre(
                    [q for q in questions if q["id"] in faibles],
                    modele=self.modele_escalade,
                )
                par_id = {r["id"]: r for r in reponses}
                for r in rejouees:
                    par_id[r["id"]] = r
                reponses = list(par_id.values())
        return reponses

    # -- A. OCR d'une facture (contrat A) -----------------------------------
    def lire_facture(self, chemin: str, *, modele: str | None = None):
        mod = modele or self.modele
        # Prétraitement : réduction à 1 500 px / JPEG 80 (÷3 à ÷4 sur le coût).
        # Un PDF est rasterisé page par page. Si les dépendances manquent, on
        # envoie brut ET le repli est journalisé (jamais silencieux).
        from .pretraitement import preparer
        blocs = [
            {"type": genre,
             "source": {"type": "base64", "media_type": media,
                        "data": base64.standard_b64encode(data).decode("ascii")}}
            for genre, media, data in preparer(chemin, journal=self.journal_pretraitement)
        ]
        contenu = [
            *blocs,
            {"type": "text",
             "text": "Classe cette pièce, puis extrais les factures qu'elle contient "
                     "(une entrée par facture ; un PDF peut en contenir plusieurs)."},
        ]
        out = self._json(mod, _SYS_OCR, contenu, _SCHEMA_FACTURE, max_tokens=3000)
        factures = out.get("factures", [])

        # Escalade OCR (absente jusqu'ici) : on rejoue sur le modèle fort dès
        # qu'un DOUTE porte sur la nature de la pièce ou sur l'extraction. Un
        # classement incertain est le cas le plus coûteux à laisser passer :
        # c'est celui qui transforme un devis en écriture.
        if mod != self.modele_escalade and self._doute(factures):
            return self.lire_facture(chemin, modele=self.modele_escalade)
        return factures

    @staticmethod
    def _doute(factures) -> bool:
        """Critères explicites d'escalade — cible < 15 % des pièces."""
        if not factures:
            return True                        # rien lu : pièce peut-être illisible
        for f in factures:
            if float(f.get("confiance_classement") or 0.0) < SEUIL_CLASSEMENT:
                return True
            if float(f.get("confiance") or 0.0) < SEUIL_ESCALADE:
                return True
            cat = (f.get("categorie") or "").strip().lower()
            if not cat or cat not in CATEGORIES:
                return True
            # incohérence structurelle : non comptable mais des montants remplis
            if not est_comptable(cat) and float(f.get("ttc") or 0.0):
                return True
        return False
