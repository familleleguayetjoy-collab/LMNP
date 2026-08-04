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

### Les deux sources

- **Le client** partage son **Drive** et y scanne / photographie ses factures au
  fil de l'eau (`01_Factures/`).
- **Le cabinet** ajoute le **FEC N-1** et le **relevé bancaire annuel** (Excel) à
  coder.

### La chaîne, jouée sur un dossier fictif (`LMNP_DUPONT_2026`)

1. **Temps 1 — apprentissage.** L'outil lit le FEC 2025 (N-1) et en tire le
   dictionnaire comptable propre au client (« *SYNDIC AZUR* → 614 »).
2. **Temps 2 — codage du relevé.** Chaque ligne reçoit un compte proposé et un
   **niveau de confiance**. Les **fournisseurs inconnus** sont identifiés par
   **recherche en ligne** puis affectés automatiquement (Orange → 626, Chubb → 616).
3. **Temps 3 — lecture & rapprochement des factures.** Chaque pièce (date,
   fournisseur, HT, TVA, TTC) est rapprochée de la ligne bancaire correspondante
   (même montant, date proche). Les écarts sont signalés, pas corrigés en silence.
4. **Temps 4 — les livrables :**
   - le **journal de banque codé** (exportable en CSV) ;
   - l'**écran d'arbitrage** : uniquement les lignes qui demandent un jugement
     humain (travaux, immobilisations, apports), triées par montant, avec la
     **raison du doute** affichée ;
   - la **liste des justificatifs manquants** et le **mail de relance** déjà rédigé
     (copiable).

### Les règles d'affectation & de relance

| Cas | Action |
|---|---|
| Fournisseur **connu** (FEC N-1) | Affectation directe, même sans facture |
| Fournisseur **inconnu** | Recherche en ligne (sur le seul nom) → affectation auto |
| Dépense **> seuil** (150 €) sans justificatif | Relance client par mail |
| Dépense **≤ seuil** sans justificatif | Affectée, **non** réclamée |
| **Travaux / immobilisation** | **Toujours** remonté à l'humain, quel que soit le montant |

### La cadence de relance (double passe)

- **15 janvier** — 1er scan du Drive, email de relance dans la foulée.
- **31 janvier** — 2ᵉ scan, uniquement les **nouveaux éléments** ; 2ᵉ email sur ce
  qu'il reste (ton plus ferme). Démontré par le sélecteur *Passe 1 / Passe 2*.

Une section **« Ce qu'il faut, et quand »** résume les quatre briques
(Claude Code · Skill · Cowork · Drive), le calendrier de déploiement (août 2026 →
avril 2027) et le périmètre (ce que l'outil fait / ne fera jamais).

---

## Réel vs simulé — à dire aux associés

Pour ne pas survendre : cette page est une **démonstration**, pas encore l'outil.

| Réel dans la maquette | Simulé / à construire |
|---|---|
| Le **moteur de codage** est du vrai code déterministe : dictionnaire tiré du FEC, application par recouvrement de libellés, niveaux de confiance, seuil de matérialité, rapprochement par montant + date, calcul des manquants, double passe et mail. | La **lecture des PDF/photos par IA** (OCR + extraction) est pré-remplie : les factures sont fournies déjà lues. Dans la version réelle, c'est l'API Claude qui lit les pièces. |
| Les **montants et totaux** sont calculés, jamais « devinés ». | La **recherche en ligne** des fournisseurs inconnus est ici une table de correspondance figée. Dans la version réelle, c'est une vraie recherche web de Claude sur le seul nom du fournisseur. |
| La logique **auto / arbitrage humain** avec raison du doute. | Le **connecteur Google Drive** et le **Skill** (mode d'emploi permanent) restent à câbler. Le FEC et le relevé sont un jeu de démonstration. |

Principe qui reste vrai dans la version réelle : l'IA n'intervient que là où
l'erreur est visible et rattrapable — **lire une facture** et **identifier un
fournisseur inconnu** (recherche en ligne, sur le seul nom, aucune donnée client
transmise). Les vrais **arbitrages** — travaux entretien/amélioration,
immobilisations — **restent remontés à l'humain**. Tout le reste est du code.
L'outil prépare ; la revue du collaborateur reste l'acte professionnel qui engage
le cabinet.

Le jeu de démonstration est un **relevé d'année pleine** (57 lignes : loyers,
échéances de prêt ventilées par le tableau d'amortissement, énergie avec bascule
de fournisseur en cours d'année, eau, syndic trimestriel, assurances, taxe
foncière, CFE, honoraires, mobilier, travaux, appel de fonds copropriété, apport
en compte courant, indemnité de sinistre…). La maquette produit : **88 %** de
lignes codées seules (dont l'identification en ligne des fournisseurs inconnus),
**78 %** de dépenses déjà justifiées, **7** lignes à arbitrer et **4** relances à
envoyer au-dessus du seuil de 150 € (deux pièces sous le seuil, affectées sans
relancer). Ces taux sont illustratifs — ils devront être **confirmés par le pilote
de septembre** (point d'arrêt : si < 60 %, on ajuste ou on arrête).

---

## Le dossier de démonstration

Les données fictives sont regroupées, lisibles et modifiables en tête du bloc
`<script>` de `build/template.html` :

- `FEC` — les libellés déjà codés en 2025 (source du dictionnaire) ;
- `BANK` — les 57 lignes du relevé 2026 à coder (les échéances de prêt portent le
  champ `amort:[intérêts, capital]`, ventilation issue du tableau d'amortissement) ;
- `INVOICES` — les 21 factures déposées (volontairement incomplètes, pour faire
  apparaître la liste de relance ; une facture Boulanger diverge du montant bancaire
  pour illustrer la détection d'écart) ;
- `COMPTES` — le plan comptable LMNP utilisé pour les intitulés ;
- `SEUIL` — le seuil de matérialité (€) qui déclenche la relance ;
- `RECU_P2` — les pièces réputées transmises par le client entre les deux passes ;
- `webSearch()` — la table de correspondance « fournisseur inconnu → compte ».

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
