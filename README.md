# S2A — Lecture de clôture

Application mono-fichier (navigateur, sans serveur) qui lit un **FEC** (Fichier des
Écritures Comptables) et en produit une lecture de clôture prête à présenter en
rendez-vous client. Tout le traitement se fait dans le navigateur ; le fichier
n'est jamais transmis à un serveur.

Ouvrez simplement `index.html` (ou déposez-le sur un hébergement statique).

## Import du FEC

Le FEC est, par la loi, un fichier **texte plat** (ASCII/ANSI). Le parser accepte
`.txt` / `.csv`, les délimiteurs tabulation / `;` / `|` / `,`, et l'encodage
UTF-8 comme windows-1252. Un export ASCII fonctionne donc sans réglage
particulier.

Un jeu de démonstration (données fictives) est disponible sur l'écran d'accueil.

## Deux interfaces

### Espace expert-comptable (avant l'entretien)

- **Feuille de route** — la page à lire en 2-3 minutes avant le rendez-vous :
  verdict de l'exercice, chiffres clés, et **points à aborder** (cases à cocher
  pour dérouler l'entretien). Elle inclut des **contrôles de cohérence à
  l'import** (équilibre débit = crédit, actif = passif, résultat net = produits −
  charges via les SIG, taux de TVA) pour vérifier que les montants calculés
  correspondent aux documents remis avant de les présenter au client.
- **Recommandations** — pistes de travail par thème (trésorerie, activité,
  structure financière, social, fiscal), calculées localement.
- **Le dossier en détail** — synthèse, compte de résultat, trésorerie, bilan,
  ratios et **soldes intermédiaires de gestion (SIG)**.

### Espace client (pendant le rendez-vous)

- **Vue client** masque les éléments techniques et agrandit la présentation.
- **Présentation client** déroule un jeu de diapositives. La comparaison N/N-1
  s'appuie pour l'instant sur des données de démonstration (le comparatif réel
  sera branché lorsque l'exercice N-1 sera fourni).

## Analyse par IA (optionnelle)

Les boutons « **Enrichir avec l'IA** » de la feuille de route et des
recommandations appellent l'API Claude pour produire une analyse approfondie et
davantage de sujets à aborder.

Renseignez votre clé dans **Réglages IA** (barre latérale) :

- **Clé API Claude** — stockée uniquement dans ce navigateur (`localStorage`),
  transmise seulement à l'API Anthropic.
- **Modèle** — Opus 5 par défaut (qualité maximale) ; Sonnet 5 ou Haiku 4.5 pour
  réduire le coût. Comptez de l'ordre de 0,10 à 0,50 € par génération.
- **Point d'accès (avancé)** — laissez vide pour l'API directe, ou indiquez l'URL
  d'un proxy de cabinet (la clé n'est alors plus exposée dans le navigateur).

En l'absence de clé, l'application reste entièrement fonctionnelle : la feuille de
route et les recommandations sont générées localement, sans coût.

## Notes

- Chart.js est embarqué localement (aucun appel réseau) ; seules les polices
  Google Fonts sont chargées depuis le web pour la typographie.
- Le bilan et les SIG sont reconstitués à partir des soldes du FEC, à titre
  d'analyse indicative ; ils ne se substituent pas à la liasse fiscale déposée.
