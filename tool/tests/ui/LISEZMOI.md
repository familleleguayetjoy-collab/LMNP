# Tests d'interface de la maquette Saisio

Le moteur (`tool/tests/selftest.py`) garantit les montants ; ces cinq scripts
garantissent que l'interface les respecte. Ils pilotent un vrai navigateur et
vérifient ce que le collaborateur voit et obtient, pas ce que le code prétend.

| script       | ce qu'il vérifie |
|--------------|------------------|
| `audit.mjs`  | le parcours complet : connexion, accueil, les 5 étapes, l'anti-doublon au 2ᵉ passage, et que chaque écran tient dans un seul écran |
| `poste.mjs`  | **le poste de travail** (étape 2) : tri, onglets, imputation en série, « Valider et suivant », mise en attente en 471, factures réglées hors relevé, clavier, persistance |
| — | `audit.mjs` vérifie en plus la forme : montants jamais colorés, un seul statut par ligne, aucune cellule sur deux lignes, en-tête figée au défilement |
| `regles.mjs` | chacune des 8 règles de contrôle pilote réellement un statut ou l'onglet des factures hors relevé — décocher une règle fait disparaître ce qu'elle produit |
| `audit2.mjs` | les cas limites : dossier sans banque, changement de dossier (aucune fuite d'état), décomposition annulée / rouverte, mail sans justificatif |
| `export.mjs` | **le fichier réellement produit** : 251 caractères par ligne, journal BQ contrepartie 512 pour le relevé, journal OD contrepartie 108 pour l'exception, une ligne de plus par ventilation, écriture datée du jour du règlement |

## Lancer

```sh
cd tool/tests/ui
npm install playwright-core        # une seule fois
node audit.mjs && node poste.mjs && node regles.mjs && node audit2.mjs && node export.mjs
```

Chaque script affiche une ligne par contrôle (`OK` / `KO`) puis les erreurs
JavaScript rencontrées — il ne doit y en avoir aucune. Au total : **131
contrôles**.

Deux variables d'environnement permettent de changer de cible :

- `CHROME` : chemin de l'exécutable Chromium (défaut : celui du conteneur) ;
- `SAISIO` : URL de la page à tester (défaut : `index.html` à la racine du dépôt).

Les tests écrivent dans le `localStorage` de la page (session, travail en cours,
historique d'import) : c'est voulu, c'est ce qu'ils vérifient. Chaque script
démarre sur un profil neuf, ils sont donc indépendants les uns des autres.
