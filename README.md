# Assistant de préparation LMNP — S2A · Sud Alpes Audit

**Prototype interne · version bêta.** Maquette fonctionnelle de l'outil décrit dans
la note *« Automatisation des dossiers LMNP / LMP »* (P. Leguay, 3 août 2026),
destinée à être montrée à Thierry Bozzola et Julien Lesnes avant le pilote de
septembre.

Un seul fichier HTML autonome : ouvrir `index.html` dans un navigateur, cliquer
**« Lancer la préparation »**. Aucune installation, aucun serveur, aucun appel
externe.

---

## Ce que montre la maquette

La chaîne en quatre temps de la note, jouée sur un **dossier fictif**
(`LMNP_DUPONT_2026`) :

1. **Temps 1 — apprentissage.** L'outil lit le FEC 2025 (N-1) et en tire le
   dictionnaire comptable propre au client (« *SYNDIC AZUR* → 614 »).
2. **Temps 2 — codage du relevé.** Chaque ligne bancaire reçoit un compte proposé
   et un **niveau de confiance**. Les libellés inconnus sont mis de côté.
3. **Temps 3 — lecture & rapprochement des factures.** Chaque pièce (date,
   fournisseur, HT, TVA, TTC) est rapprochée de la ligne bancaire correspondante
   (même montant, date proche). Les écarts sont signalés, pas corrigés en silence.
4. **Temps 4 — les livrables :**
   - le **journal de banque codé** (exportable en CSV) ;
   - l'**écran de revue** : uniquement les lignes qui posent question, triées par
     montant décroissant, avec la **raison du doute** affichée ;
   - la **liste des justificatifs manquants** et le **mail de relance** déjà rédigé
     (copiable) — le livrable productible dès le 2 janvier.

Une section **« Ce qu'il faut, et quand »** résume les quatre briques
(Claude Code · Skill · Cowork · Drive), le calendrier de déploiement (août 2026 →
avril 2027) et le périmètre (ce que l'outil fait / ne fera jamais).

---

## Réel vs simulé — à dire aux associés

Pour ne pas survendre : cette page est une **démonstration**, pas encore l'outil.

| Réel dans la maquette | Simulé / à construire |
|---|---|
| Le **moteur de codage** est du vrai code déterministe : dictionnaire tiré du FEC, application par recouvrement de libellés, niveaux de confiance, rapprochement par montant + date, calcul des manquants et du mail. | La **lecture des PDF/photos par IA** (OCR + extraction) est ici pré-remplie : les factures sont fournies déjà lues. Dans la version réelle, c'est l'API Claude qui lit les pièces. |
| Les **montants et totaux** sont calculés, jamais « devinés ». | Le **FEC et le relevé** sont un jeu de démonstration, pas un vrai dossier. |
| La logique **80 % auto / 20 % remonté à l'humain** avec raison du doute. | Le **connecteur Google Drive** et le **Skill** (mode d'emploi permanent) restent à câbler. |

Principe qui reste vrai dans la version réelle : l'IA n'intervient que sur deux
tâches où l'erreur est visible et rattrapable — **lire une facture** et **proposer
un compte sur un libellé jamais vu**. Tout le reste est du code. L'outil prépare ;
la revue du collaborateur reste l'acte professionnel qui engage le cabinet.

Sur ce jeu de démonstration, la maquette produit : **76 %** de lignes codées
seules, **71 %** de dépenses déjà justifiées, **6** lignes à revoir et **4**
justificatifs à réclamer. Ces taux sont illustratifs — ils devront être
**confirmés par le pilote de septembre** (point d'arrêt : si < 60 %, on ajuste ou
on arrête).

---

## Le dossier de démonstration

Les données fictives sont regroupées, lisibles et modifiables en tête du bloc
`<script>` de `build/template.html` :

- `FEC` — les libellés déjà codés en 2025 (source du dictionnaire) ;
- `BANK` — les 25 lignes du relevé 2026 à coder ;
- `INVOICES` — les 10 factures déposées (volontairement incomplètes, pour faire
  apparaître la liste de relance) ;
- `COMPTES` — le plan comptable LMNP utilisé pour les intitulés.

Pour tester un autre scénario devant les associés, il suffit de modifier ces
tableaux et de reconstruire.

---

## Identité de marque

Couleurs (navy / or), typographies (Poppins / Montserrat) et logo repris du
simulateur LMNP du cabinet, pour une continuité visuelle. Thème clair/sombre et
export **Imprimer / PDF** (mise en page adaptée pour un tirage de réunion).

---

## Reconstruire

`index.html` est **généré** : polices et logos y sont intégrés en base64 pour un
fichier 100 % autonome.

```bash
python3 build/build.py
```

- `build/template.html` — code source (HTML / CSS / JS) avec jetons `__…__` et le
  jeu de données de démonstration ;
- `build/assets/` — polices `.woff2`, logos `.webp`, favicon `.svg` ;
- `build/build.py` — injecte les assets et produit `index.html` + `dist/app.html`.

---

*Le déploiement réel est subordonné à la signature du DPA Anthropic et à la mise à
jour des lettres de mission (dépôt des pièces + recours à un sous-traitant
technique). Taux et gains de temps à confirmer par le pilote avant tout engagement.*
