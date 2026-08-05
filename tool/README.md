# Moteur LMNP S2A — codage réel (cœur déterministe)

Début de l'implémentation réelle, séparée de la maquette de démonstration
(`index.html`). Ici, **tout ce qui touche aux montants est du code testé**,
jamais de l'IA. L'IA n'intervient que sur deux tâches, et seulement pour
*proposer* (l'humain valide) : lire une facture, proposer un compte sur un
fournisseur inconnu.

## Ce qui marche déjà (testé, `python3 tool/tests/selftest.py` → 28 contrôles OK)

| Module | Rôle | État |
|---|---|---|
| `normalize.py` | Normalisation des libellés + **parsing robuste des montants FR** | ✅ |
| `fec.py` | Lecture du FEC (délimiteur `|`/tab/`;`, encodage, débit/crédit ou montant+sens) | ✅ (à éprouver sur un vrai FEC) |
| `dico.py` | Dictionnaire client + **détection des imputations multiples N-1** | ✅ |
| `codage.py` | Règles de codage. Ne remonte à l'humain que **immo / inconnu / multi** | ✅ |
| `rapprochement.py` | Rapprochement facture↔banque, écarts, manquants | ✅ |
| `quadra.py` | Export Quadratus ASCII, **partie double équilibrée, 256 car.** | ✅ (positions à valider) |
| `ocr.py` | Lecture des factures par l'API Claude | ⛔ interface seulement |

## Architecture proposée

```
FEC N-1 ─┐
         ├─► dico (dictionnaire client) ─┐
Relevé  ─┘                               ├─► codage ─► [revue humaine] ─► quadra ─► fichier d'import
Factures Drive ─► ocr (API Claude) ──────┘   rapprochement ─► manquants ─► mail de relance
```

Le **cœur est agnostique de la forme finale** (script en lot, Skill lancé dans
Claude Cowork, ou petite appli). Je recommande : **scripts Python + un Skill**
que Claude exécute dans Cowork — les collaborateurs ne voient que le résultat,
et les parties « montants » restent du code.

## Ce dont j'ai besoin de toi pour continuer

1. **Un vrai jeu de fichiers anonymisé** (le plus important) pour éprouver les
   lecteurs face à la réalité :
   - un **FEC N-1** (`.txt`) tel qu'exporté ;
   - un **relevé bancaire annuel** (Excel/CSV) tel que tu le récupères ;
   - **2–3 factures** (PDF/photo) du même client.
2. **Paramètres Quadra** : le cahier des charges exact de ton import ASCII
   (positions des champs) + tes **codes journaux** (BQ, OD, AC, VE…). Ça me
   permet de verrouiller `quadra.py` (aujourd'hui : format standard, à valider).
3. **Plan comptable LMNP** du cabinet + **seuil d'immobilisation** + doctrine
   entretien/amélioration (ça alimente les règles + le futur Skill).
4. **Accès API Anthropic** (clé + DPA) — sans ça l'OCR reste une interface.
5. **Deux décisions** : (a) forme finale (scripts+Skill dans Cowork, je pense) ;
   (b) modèle OCR par défaut (je propose Haiku 4.5, escalade Sonnet si doute).

## Les cas qui peuvent faire buguer (ce à quoi je fais déjà attention)

**Montants (zéro tolérance)** — séparateurs `,`/`.`/espace, négatifs, format
comptable `( )`, arrondis au centime. → `parse_montant` lève plutôt que
d'inventer ; contrôle d'équilibre débit=crédit à l'export.

**FEC** — délimiteur et encodage variables ; débit/crédit en 2 colonnes *ou*
montant+sens ; ordre des colonnes ; lignes A-Nouveau à exclure ; **le libellé
du FEC ≠ le libellé bancaire** (risque n°1 du rapprochement du dictionnaire).

**Relevé bancaire** — un format par banque ; montant signé *ou* deux colonnes ;
dates en série Excel *ou* texte ; lignes de totaux ; libellés tronqués.

**Codage** — fournisseur à imputations multiples en N-1 (géré : remonté) ;
immobilisation vs charge (remonté) ; échéance de prêt = **une** ligne bancaire à
ventiler 661/164 (nécessite le tableau d'amortissement en entrée) ; TVA ;
dépense mixte privé/pro (non déductible → à signaler).

**Rapprochement** — **un virement pour plusieurs factures**, paiement partiel,
remboursement (négatif), doublons (même montant 2×), **décalage de date**
facture/paiement, erreur d'OCR sur le montant → écart signalé, jamais corrigé.

**OCR** — photo floue/pivotée, plusieurs factures par PDF, multi-pages, ticket
thermique, langue étrangère, document qui n'est pas une facture, doublon,
**hallucination du montant** → le montant OCR ne sert qu'à rapprocher, jamais à
poster ; en dessous d'un seuil de confiance, la pièce est marquée « à revoir ».

**Quadra** — positions de champs à valider ; **compte inexistant** dans le
dossier → rejet ; folio déséquilibré → rejet ; encodage ISO-8859-1 ; caractères
spéciaux dans le libellé (nettoyés).

**Robustesse générale** — fichiers vides/mauvais type ; **idempotence /
pièces déjà traitées** (via un manifeste de suivi, pas en renommant les
fichiers du client) ; traçabilité (journaliser chaque décision + confiance +
qui a validé, pour la NPMQ) ; RGPD (données transmises à Anthropic → DPA) ;
locale `fr_FR`.

## Lancer les tests

```bash
python3 tool/tests/selftest.py
```
