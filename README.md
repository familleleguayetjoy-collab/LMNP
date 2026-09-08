# Saisio — préparation comptable LMNP / LMP / SCI / BNC

**Cabinet S2A · Sud Alpes Audit.** Outil interne qui prépare les dossiers de
location meublée : il lit les pièces déposées par le client, code le relevé
bancaire, ne remonte au collaborateur que ce qui demande un jugement, rédige la
relance des justificatifs manquants et produit le fichier d'import Quadratus.

Le dépôt contient **deux choses distinctes** :

| | quoi | où |
|---|---|---|
| **La maquette** | l'interface, complète et cliquable, sur un jeu de données fictif | `index.html` (généré depuis `build/template.html`) |
| **Le moteur** | le code réel qui calcule les écritures, testé, sans dépendance | `tool/s2a_lmnp/` |

La règle qui gouverne les deux : **les montants sont du code, jamais de l'IA.**
L'IA lit les pièces et propose ; elle ne décide d'aucun chiffre.

---

## La règle comptable de fond

On tient ces dossiers en **comptabilité de trésorerie**. Deux conséquences, qui
expliquent presque tout le comportement de l'outil :

1. **Le relevé bancaire fait foi.** C'est lui qui définit ce qui est comptabilisé
   et à quelle date. Une facture retrouvée en banque prend la date du mouvement,
   même si la pièce en annonçait une autre.
2. **Une seule exception** : une facture portant la mention « payée » qu'on ne
   retrouve **pas** en banque (réglée par l'exploitant à titre personnel). On
   passe alors une écriture dans le **journal d'OD**, contrepartie **108
   (compte de l'exploitant)**, **datée du jour du règlement** — pas de la facture.
   Quand la date de règlement est absente de la pièce, l'outil retombe sur la
   date de facture **et le signale** ; il n'invente jamais une date en silence.

C'est aussi cette date qui range la pièce dans le Drive (voir « Rangement »).

---

## La maquette

Ouvrir `index.html` dans un navigateur. Aucun serveur, aucune installation,
aucun appel externe.

**Connexion** (email + mot de passe, session conservée localement), puis
**Mes dossiers** : un tableau — dossier, type, nouvelles pièces, statut —
avec une recherche, un filtre par type et trois onglets, *Nouveaux éléments*,
*À jour*, *Tous*. **Nouveau dossier** demande le nom, le type et **les bornes
de l'exercice** — c'est l'exercice qui range les pièces, il est donc saisi dès
la création. Un dossier qui attend affiche son **nombre de pièces neuves
en rouge** ; un dossier à jour affiche sa **date de dernière mise à jour**.
Rien d'autre : le reste se découvre en entrant dedans.

Le parcours d'un dossier tient en cinq écrans, un par décision :

1. **Importer** — période, type (LMNP / LMP / SCI / BNC), assujettissement à la
   TVA, tenue de banque, FEC N‑1, relevé bancaire. Un bouton **Règles de
   contrôle** ouvre le paramétrage complet du cabinet : **32 règles** en six
   familles — montant et significativité, fiabilité de l'affectation, anomalies
   documentaires et règlements, opérations sensibles, cohérence avec l'activité,
   doublons.
   Chaque règle se règle sur **trois niveaux** : *Automatique* (l'outil impute
   seul), *À contrôler* (la ligne remonte), *Validation obligatoire* (la ligne
   remonte **et** ne peut pas être traitée en série avec les autres lignes du
   même fournisseur). Quatre règles portent un seuil.
   **Huit règles sont branchées aujourd'hui** et pilotent réellement l'écran
   suivant : les passer en automatique fait disparaître ce qu'elles produisent.
   Les autres portent la mention *à brancher* : elles se paramètrent dès
   maintenant mais attendent la donnée qui les fait vivre — historique
   pluriannuel par fournisseur, balance du dossier, schémas d'écriture (prêt,
   crédit-bail, dépôt de garantie). L'écran le dit en toutes lettres : mieux
   vaut une case honnête qu'une case qui ment.
2. **Traitement** — l'écran de travail, en trois colonnes sur toute la hauteur :
   **le relevé**, **la pièce**, **la décision**. Rien en haut de l'écran : la
   navigation est un rail vertical d'icônes, tout le reste va au travail.
   Les quatre onglets — **Tout**, **À traiter**, **Traité**, **Hors relevé** —
   ne coiffent que la liste, à laquelle ils appartiennent.
   Le relevé est triable par date, libellé, montant ou statut, en-tête figée au
   défilement, montants en noir (le signe suffit), libellés tronqués sans jamais
   passer à la ligne. **Un seul statut par ligne** — le plus grave — avec une
   pastille de couleur : *À qualifier*, *Immobilisé*, *Acompte*, *Multi-règl.*,
   *Montant élevé*, *Sans pièce*, *Nouveau*. Une ligne qu'aucune règle ne
   retient est **Traité** : la décision a été prise seule, il n'y a rien à
   regarder.
   La pièce occupe toute la hauteur au centre. Tant qu'aucun fichier n'est
   rattaché, un **aperçu schématique** en tient lieu — rendu différemment selon
   qu'il s'agit d'une facture ou d'un ticket de caisse ; dès qu'une image est
   là, c'est **le vrai document** qui s'affiche. Le dossier de démonstration
   `LMNP_POLO_TEST` porte cinq vraies factures : leurs PDF sont rendus en image
   à la construction (`build/rendu_pieces.py`), parce que le lecteur PDF du
   navigateur n'est pas garanti dans un cadre isolé — dans l'artifact,
   `<embed type="application/pdf">` n'affichait qu'un rectangle noir. À droite la décision, dans
   l'ordre où elle se prend : ce que dit la banque (en lecture seule — le relevé fait foi), ce
   que dit la pièce, puis le compte, décomposable sur plusieurs comptes ou
   complétable par un compte saisi à la main. Une facture ventilée n'a plus de
   compte unique : la répartition remplace le sélecteur, et « Modifier la
   répartition » passe sous les comptes. Puis **trois sorties**, dans un
   seul bloc, codées par la couleur : **Valider et suivant** (vert),
   **Laisser en attente (471)** (ambre — ça trace au lieu d'oublier), et
   **Appliquer aux N autres lignes** du même fournisseur (gris).
   Deux autres choses font la vitesse : le clavier (↑ ↓ pour parcourir, Entrée
   pour valider) et le fait que les lignes sans statut soient déjà imputées.
   Le quatrième onglet est **l'exception de trésorerie** : les factures
   acquittées qu'on ne retrouve pas au relevé. On y saisit la date portée par
   la pièce, qui datera l'écriture d'OD ; sans date, un bouton l'ajoute à la
   liste des demandes au client.
3. **Justificatifs à demander** — deux onglets : *Pièce manquante* et
   *Règlement à justifier*, alimentés depuis l'écran précédent.
4. **Le mail** — brouillon prêt, en deux sections correspondant aux deux
   onglets, synchronisé avec les cases cochées.
5. **Le fichier** — journal de banque Excel (si banque tenue) et écritures
   ASCII Quadratus, horodatés, avec le nombre de lignes produites.

**Remise à zéro.** Le bouton ⟲ en bas du rail efface le travail en cours et
l'historique d'import : tous les dossiers repartent avec l'intégralité de leurs
opérations à traiter. Utile entre deux démonstrations ; la session reste ouverte.

**Reprise et anti‑doublon.** Chaque import est enregistré (empreinte + date).
À la réouverture d'un dossier déjà traité, l'outil affiche ce qui restait ouvert,
confronté aux pièces déposées depuis, et laisse cocher « Régularisé hors Saisio ».
Les imputations, ventilations, dates saisies et réglages de règles sont conservés
d'une session à l'autre.

### Reconstruire la maquette

`index.html` est **généré** (polices et logos intégrés en base64, fichier
autonome) :

```bash
python3 build/build.py     # -> index.html + dist/app.html
```

- `build/template.html` — la source (HTML / CSS / JS) et le jeu de démonstration ;
- `build/assets/` — polices `.woff2`, logos, favicon ;
- `build/assets/pieces/` — les cinq factures de démonstration : le PDF d'origine
  et son rendu `.jpg`, produit par `build/rendu_pieces.py` (à relancer seulement
  quand on ajoute une pièce ; les JPEG sont versionnés pour que `build.py`
  n'ait aucune dépendance) ;
- `build/build.py` — injecte les assets.

Les données fictives sont regroupées en tête du bloc `<script>` : `DEFAULT_OPS`
(le relevé), `DEFAULT_HORS` (les factures acquittées hors relevé),
`DEFAULT_RECLAM`, `DOSSIERS`, `REGLES`, `PLAN` (le plan comptable affiché) et
`NB_PIECES`. Une ligne de relevé s'écrit
`O(date, libellé, montant, sens, compte, pièce, options, drapeaux)` — pour jouer
un autre scénario, il suffit d'en ajouter et de reconstruire.

---

## Le moteur

Python 3, **bibliothèque standard uniquement** pour le cœur. Deux dépendances
optionnelles (Pillow, pypdfium2) servent au seul prétraitement des images et leur
absence est **signalée**, jamais silencieuse.

```bash
python3 tool/tests/selftest.py        # 212 contrôles
python3 tool/demo/demo_pipeline_complet.py
```

Voir `tool/README.md` pour le détail des modules. En résumé :

- `fec.py` / `dico.py` — le FEC N‑1 fait le dictionnaire comptable du client ;
- `classement.py` — **avant** toute extraction, la pièce est classée : un devis,
  un bon de commande ou un document illisible ne devient jamais une facture ;
- `codage.py` — affectation déterministe, seuil d'immobilisation **500 € HT** ;
- `rapprochement.py` — facture ↔ relevé, écarts signalés, OD 108 pour le payé
  perso, virements internes, doublons ;
- `quadra.py` — export ASCII 251 caractères, contrepartie en ligne ;
- `rangement.py` — le plan de classement des pièces dans le Drive : exercice,
  puis mois de règlement, puis statut ;
- `cout.py` — coût réel mesuré sur `response.usage`, avec alerte par dossier ;
- `manifeste.py` / `sources.py` — empreintes sha256 : une pièce n'est jamais
  relue ni recomptabilisée deux fois.

### Rangement des sorties

Dans le dossier du client, l'outil écrit sous
`Documents générés par l'application/` :

```
Documents générés par l'application/
    Exercice 2026/
        2026-01/
            Traité/                    (une écriture a été produite)
            En attente de traitement/  (non comptable, incomplet, en attente client)
        2026-03/
            ...
    Hors exercice 2027/
        2027-01/
            ...
```

**L'exercice d'abord.** Une pièce appartient à un exercice avant d'appartenir à
un mois. Sans ce niveau, une facture de janvier 2027 tombée dans le dépôt d'un
dossier 2026 se rangerait dans `2027-01` à côté des mois en cours et personne ne
verrait le mélange ; avec lui, elle atterrit dans « Hors exercice 2027 » et saute
aux yeux. Un exercice décalé (01/07 → 30/06) porte le millésime de sa clôture,
comme le fait l'administration.

Le mois, ensuite, est celui du **règlement** — donc celui de l'écriture. Une
facture de décembre réglée en janvier est rangée en `2026-01`, exactement là où
se trouve son écriture. À défaut de date de règlement connue, la date de facture
sert de repli et le rangement est marqué comme estimé.

---

## Tests

| suite | ce qu'elle couvre |
|---|---|
| `tool/tests/selftest.py` | 212 contrôles sur le moteur — normalisation, FEC, codage, rapprochement, IA simulée, idempotence, classement, coût, trésorerie, rangement |
| `tool/tests/ui/` | 136 contrôles d'interface pilotés dans un vrai navigateur, dont la vérification **du fichier ASCII réellement produit** et le fait que chacune des 8 règles pilote vraiment quelque chose (voir `tool/tests/ui/LISEZMOI.md`) |

---

## Ce qui reste à câbler avant la mise en service

- le **connecteur Google Drive** (Picker + `drive.file` en première intention) ;
- le **connecteur Gmail** pour déposer les brouillons de relance ;
- la **clé API** dans l'environnement de déploiement ;
- la **campagne de calibrage** du classement sur 50 pièces réelles (objectif :
  ≥ 95 % sur les devis).

---

*Déploiement subordonné à la signature du DPA Anthropic et à la mise à jour des
lettres de mission (dépôt des pièces + recours à un sous-traitant technique).*
