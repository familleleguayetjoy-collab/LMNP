# S2A — Présentation des comptes

Application mono-fichier (navigateur, sans serveur) qui prépare et déroule le
**rendez-vous annuel de présentation des comptes**. Elle lit un **FEC** (Fichier
des Écritures Comptables, contenant N et N-1) et en tire, d'un côté, une
préparation express pour l'expert-comptable et, de l'autre, une présentation
claire à dérouler devant le client. Tout le traitement se fait dans le
navigateur ; le fichier n'est jamais transmis à un serveur.

Ouvrez simplement `index.html` (ou déposez-le sur un hébergement statique).

## Parcours

1. **Préparer le dossier** — on importe le **FEC** (écritures N et N-1) et,
   éventuellement, le **PDF des comptes annuels** (SIG, compte de résultat,
   bilan N/N-1). La date d'arrêté est détectée automatiquement.
2. **Choix de l'interface** — **Préparer le rendez-vous** (expert-comptable) ou
   **Présenter au client**, clairement séparées.

Un jeu de démonstration (Atelier Lumen, données fictives) est disponible sur
l'écran d'accueil.

## Interface expert-comptable — à lire avant l'entretien

Deux écrans, rien de plus :

- **L'essentiel** — les indicateurs clés de l'exercice (CA, marge, EBE,
  résultat, trésorerie, délais clients/fournisseurs) avec la comparaison N-1, et
  une synthèse « à retenir ».
- **Recommandations IA** — exactement trois recommandations, chacune structurée
  en *problème identifié* (chiffré, N/N-1), *correctif précis* (actionnable) et
  *scénario N+1* (fourchette de gain estimé).

## Interface client — pendant le rendez-vous

Pensée pour être projetée simultanément sur un grand écran et sur la tablette
posée devant le client : numéros très lisibles, textes courts, graphiques
simples, navigation horizontale.

- **Synthèse de l'exercice** — les soldes intermédiaires de gestion en clair
  (CA, marge, valeur ajoutée, EBE, résultat courant, résultat net) avec %CA,
  variation N-1 et courbe de tendance. Un bouton **Ajustements** ouvre un tiroir
  de *simulation en direct* (produits à recevoir, stocks / en-cours) qui
  recalcule instantanément le résultat et le bilan — sans toucher à la
  trésorerie.
- **Activité** — chiffre d'affaires, répartition et évolution mensuelle N/N-1.
- **Charges** — charges d'exploitation, évolution mensuelle et détail par
  catégorie, jusqu'au suivi mensuel de chaque compte de charge.
- **Charges récurrentes** — comparaison N-1 des postes récurrents (assurances,
  loyers, énergie, télécoms…) et détail des contrats.
- **Bilan** — structure (postes clés en % de l'actif / du passif) et ratios
  essentiels (délais, BFR, trésorerie nette, capacité de remboursement…).
- **Trésorerie** — trésorerie de clôture, évolution mensuelle N/N-1, points
  haut/bas et variation annuelle.

Chaque écran répond à trois questions : quel est le chiffre, comment évolue-t-il
par rapport à N-1, et qu'est-ce que cela veut dire concrètement. La rubrique
« ce qu'il faut retenir » propose une lecture pédagogique, enrichie par l'IA
lorsqu'une clé est configurée.

## Import du FEC

Le FEC est, par la loi, un fichier **texte plat** (ASCII/ANSI). Le parser accepte
`.txt` / `.csv`, les délimiteurs tabulation / `;` / `|` / `,`, et l'encodage
UTF-8 comme windows-1252. Un export ASCII fonctionne donc sans réglage
particulier. Le comparatif N-1 est reconstitué à partir du FEC, qui contient les
deux exercices.

## Analyse par IA (optionnelle)

L'IA n'effectue aucun calcul : le code produit tous les chiffres (SIG, ratios,
variations, séries mensuelles, délais, BFR, trésorerie), et l'IA se contente de
les interpréter, de les hiérarchiser et d'en tirer recommandations et
commentaires pédagogiques.

- **Clé API Claude** — stockée uniquement dans ce navigateur (`localStorage`),
  transmise seulement à l'API Anthropic.
- **Modèle** — Opus par défaut (qualité maximale). Comptez de l'ordre de 3 € par
  dossier au maximum.

En l'absence de clé, l'application reste entièrement fonctionnelle : synthèses et
recommandations sont générées localement, sans coût.

## Notes

- Chart.js est embarqué localement (aucun appel réseau).
- Le bilan et les SIG sont reconstitués à partir des soldes du FEC, à titre
  d'analyse indicative ; ils ne se substituent pas à la liasse fiscale déposée.
