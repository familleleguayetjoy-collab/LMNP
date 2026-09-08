# Tests d'interface de la maquette Saisio

Le moteur (`tool/tests/selftest.py`) garantit les montants ; ces cinq scripts
garantissent que l'interface les respecte. Ils pilotent un vrai navigateur et
vérifient ce que le collaborateur voit et obtient, pas ce que le code prétend.

| script       | ce qu'il vérifie |
|--------------|------------------|
| `audit.mjs`  | le parcours complet : connexion, accueil, les 5 étapes, l'anti-doublon au 2ᵉ passage, et que chaque écran tient dans un seul écran |
| `audit2.mjs` | les cas limites : dossier sans banque, changement de dossier (aucune fuite d'état), décomposition annulée / rouverte, mail sans justificatif |
| `audit3.mjs` | les points relevés en audit : relevé bancaire remis à zéro, nombre de lignes annoncé à l'export, motifs cohérents sur un dossier sans banque |
| `verif.mjs`  | les règles de contrôle pilotent bien les onglets, le travail survit au rechargement, les deux onglets de réclamation, le mail en deux sections |
| `export.mjs` | **le fichier réellement produit** : 251 caractères par ligne, journal OD, contrepartie 108, une ligne de plus par ventilation, et l'écriture datée du jour du règlement |

## Lancer

```sh
cd tool/tests/ui
npm install playwright-core        # une seule fois
node audit.mjs && node audit2.mjs && node audit3.mjs && node verif.mjs && node export.mjs
```

Chaque script affiche une ligne par contrôle (`OK` / `KO`) puis les erreurs
JavaScript rencontrées — il ne doit y en avoir aucune.

Deux variables d'environnement permettent de changer de cible :

- `CHROME` : chemin de l'exécutable Chromium (défaut : celui du conteneur) ;
- `SAISIO` : URL de la page à tester (défaut : `index.html` à la racine du dépôt).

Les tests écrivent dans le `localStorage` de la page (session, travail en cours,
historique d'import) : c'est voulu, c'est ce qu'ils vérifient. Chaque script
démarre sur un profil neuf, ils sont donc indépendants les uns des autres.
