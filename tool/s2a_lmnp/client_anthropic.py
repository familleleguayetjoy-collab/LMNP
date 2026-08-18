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
                "properties": {
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
                "required": ["fournisseur", "date", "ttc", "tva", "ht",
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
    "Tu lis des factures/justificatifs pour un cabinet comptable. Règles impératives, "
    "tirées de vraies pièces :\n"
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
        ext = os.path.splitext(chemin)[1].lower()
        genre, media = _MEDIA.get(ext, ("document", "application/pdf"))
        with open(chemin, "rb") as f:
            data = base64.standard_b64encode(f.read()).decode("ascii")
        bloc = {
            "type": genre,
            "source": {"type": "base64", "media_type": media, "data": data},
        }
        contenu = [
            bloc,
            {"type": "text",
             "text": "Lis cette pièce et renvoie les factures qu'elle contient "
                     "(une entrée par facture ; un PDF peut en contenir plusieurs)."},
        ]
        out = self._json(mod, _SYS_OCR, contenu, _SCHEMA_FACTURE, max_tokens=3000)
        return out.get("factures", [])
