# Moteur LMNP S2A — codage réel (cœur déterministe)

Début de l'implémentation réelle, séparée de la maquette de démonstration
(`index.html`). Ici, **tout ce qui touche aux montants est du code testé**,
jamais de l'IA. L'IA n'intervient que sur deux tâches, et seulement pour
*proposer* (l'humain valide) : lire une facture, proposer un compte sur un
fournisseur inconnu.

## Ce qui marche déjà (testé, `python3 tool/tests/selftest.py` → 36 contrôles OK)

| Module | Rôle | État |
|---|---|---|
| `normalize.py` | Normalisation des libellés + **parsing robuste des montants FR** | ✅ |
| `fec.py` | Lecture du FEC (délimiteur `|`/tab/`;`, encodage, débit/crédit ou montant+sens) | ✅ **éprouvé sur le vrai FEC (684 lignes)** |
| `dico.py` | Dictionnaire client + détection des imputations multiples N-1 | ✅ **+ exclusion des À-Nouveaux / amortissements (bug corrigé, voir + bas)** |
| `codage.py` | Règles de codage. Ne remonte à l'humain que **immo / inconnu / multi** | ✅ |
| `rapprochement.py` | Rapprochement facture↔banque, écarts, manquants | ✅ |
| `quadra.py` | **Lecture + export Quadratus ASCII (251 car., contrepartie en ligne)** | ✅ **calibré au format RÉEL du cabinet, aller-retour octet à octet vérifié** |
| `ocr.py` | Lecture des factures par l'API Claude | ⛔ interface (contrat enrichi par 3 vraies factures) |

## Éprouvé sur les vrais fichiers du cabinet

- **Quadra ASCII (dossier DUMDUM)** : format entièrement décodé et **ré-écrit à
  l'identique** (95/95 lignes M, au caractère près). Enregistrement M = 251 car.,
  **contrepartie en ligne** (champ 56-63) → une seule ligne par opération, Quadra
  génère l'écriture inverse. Positions exactes documentées dans `quadra.py`.
- **FEC N-1 (684 lignes)** : lu sans erreur (tab, UTF-8, 18 colonnes). A révélé un
  **vrai bug** : les lignes « À-Nouveaux » faisaient croire à des imputations
  multiples (l'immo *et* son amortissement partagent le même libellé). Corrigé :
  on exclut le journal AN et les comptes d'amortissement/dépréciation (28/29).
  16 faux « multi » → 0.
- **3 factures (EDF, Brico Dépôt, Bouygues)** : lues ; ont fixé le contrat OCR
  (travailler sur l'image et pas la couche texte d'un ticket thermique ; TTC ≠
  espèces remises ; ignorer les blocs « EXEMPLE »). Détail dans `ocr.py`.

## Règles du cabinet intégrées

- **TVA (LMNP non assujetti, ≈90 % des cas)** : on comptabilise le **TTC en
  entier** en charge/immobilisation ; aucune écriture de TVA n'est jamais
  générée. La TVA d'une facture ne sert qu'à apprécier le seuil (en HT).
- **Seuil d'immobilisation = 50 € HT** : en dessous, un achat de nature durable
  (mobilier, bricolage, travaux) est passé **directement en charge** (auto) ;
  au-dessus, il reste **« à trancher »**. Le seuil s'apprécie en HT lorsque la
  facture donne la TVA, sinon sur le TTC (prudent).
  → conséquence sur le dossier test : le ticket Brico Dépôt (59,23 € HT) est
  **au-dessus** du seuil, donc remonté « à trancher ». Quand l'OCR lira le
  détail des lignes, les consommables (peinture, etc.) pourront être passés en
  entretien automatiquement quel que soit le montant.

## Démonstrations (sans donnée client)

```bash
python3 tool/demo/demo_sans_banque.py   # FEC N-1 -> dico -> 3 factures -> codage (ctp 108) -> Quadra OD
python3 tool/demo/demo_avec_banque.py   # relevé Quadra ASCII : lecture -> ré-export équilibré (ctp 512)
```

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

Les fichiers d'exemple et le format Quadra sont **reçus et intégrés**. Il reste :

1. **Accès API Anthropic** (clé + DPA) — sans ça l'OCR reste une interface.
   C'est le seul vrai bloquant pour automatiser la lecture des factures.
2. **Doctrine d'immobilisation** : seuil (500 € HT ?) et règle entretien /
   amélioration. Aujourd'hui toute enseigne de bricolage/mobilier est remontée
   « à trancher » ; avec un seuil je pourrai auto-coder les petits achats
   (ex. le ticket Brico de 71 € → petit équipement) et ne garder en manuel que
   les vraies immo.
3. **Relevé bancaire non-Quadra** : si un client fournit un relevé Excel/CSV
   « brut » (et pas déjà au format Quadra), un exemplaire pour caler le lecteur.
4. **Deux décisions** : (a) forme finale (scripts + Skill dans Cowork, je pense) ;
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
