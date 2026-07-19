# Simulateur LMNP — S2A · Sud Alpes Audit

Outil web autonome (un seul fichier HTML) d'aide à la décision pour l'investissement
en location meublée non professionnelle (LMNP). Conçu pour être mis en favori sur
téléphone ou ordinateur et rempli en quelques minutes.

## Ce que fait l'outil

- **Multi-biens** : on démarre avec 1 bien, on ajoute les suivants avec « Ajouter un bien »,
  puis on lance le calcul avec « Simuler ».
- **Comparaison Micro-BIC vs Réel** : résultat fiscal, IR, prélèvements sociaux, coût fiscal
  et **net dans la poche**, par bien et consolidé, avec recommandation automatique.
- **Cash-flow réel** : loyers − charges − impôt − capital remboursé, en annuel et mensuel,
  plus l'enrichissement net (cash-flow + capital constitué).
- **Impact à la revente (plus-value LMNP)** : calcul de la plus-value imposable, des
  abattements pour durée de détention (IR/PS), de la surtaxe, et surtout de la
  **réintégration des amortissements** introduite par la **loi de finances 2025** —
  la « big picture » qui met l'avantage fiscal annuel en regard du coût à la revente.
- **Points de vigilance** : dépassement des seuils micro (77 700 € / 15 000 €), bascule
  possible en LMP (> 23 000 €), rendements brut/net/net-net, et rappel des éléments à
  intégrer (revalorisation, vacance, IFI, transmission…).
- **Explication client** en langage clair, prête à présenter.
- Fonctionne **hors-ligne**, sauvegarde automatique des saisies (localStorage),
  thème clair/sombre, et export **Imprimer / PDF**.

Le moteur reprend fidèlement la mécanique du classeur `LMNP_Simulateur_v4.xlsx`
(abattements, plafonnement de l'amortissement déductible, déficits reportables,
stock d'amortissements différés) et l'étend au cash-flow et à la revente.

## Utilisation

Ouvrir `index.html` dans un navigateur — c'est tout. Aucune dépendance, aucun serveur.
Pour l'installer en favori sur mobile : ouvrir la page, puis « Ajouter à l'écran d'accueil ».

## Identité de marque

Couleurs, typographies (Poppins / Montserrat) et logo repris du site du cabinet
Sud Alpes Audit. Le branding est centralisé dans les variables CSS en tête de
`build/template.html` (bloc `:root`).

## Reconstruire

Le fichier `index.html` est généré : les polices et logos sont intégrés en base64
pour un fichier 100 % autonome.

```bash
python3 build/build.py
```

- `build/template.html` — code source (HTML/CSS/JS) avec jetons `__…__`
- `build/assets/` — polices `.woff2` et logos `.webp` / favicon `.svg`
- `build/build.py` — injecte les assets et produit `index.html` + `dist/app.html`

## Avertissement

Outil à vocation pédagogique. Les résultats sont des estimations fondées sur les
hypothèses saisies et la réglementation en vigueur ; ils ne constituent pas un conseil
fiscal personnalisé. Toute décision doit être validée avec le cabinet.
