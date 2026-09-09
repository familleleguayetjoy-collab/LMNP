# Brancher Saisio — guide pas à pas

Ce guide est écrit pour quelqu'un qui n'a **jamais** ouvert un terminal. Rien
n'est à savoir à l'avance. Chaque fois qu'il faut taper quelque chose, la ligne
exacte est donnée : vous la copiez, vous la collez, vous appuyez sur Entrée.

Comptez **une heure et demie** en tout, en une ou deux fois. L'ordre compte :
chaque partie vérifie la précédente.

| | quoi | où | durée |
|---|---|---|---|
| **A** | Créer les deux comptes et récupérer trois informations | dans votre navigateur | 45 min |
| **B** | Installer Saisio sur **votre** ordinateur | terminal, copier-coller | 20 min |
| **C** | Le premier vrai test, sur un vrai dossier | terminal, une commande | 30 min |
| **D** | Plus tard : les 15 postes du cabinet | un technicien | — |

Une règle avant de commencer : **rien de ce que vous allez faire n'écrit quoi
que ce soit**, ni sur le Drive, ni dans vos dossiers clients. Saisio lit. Vous
ne pouvez pas casser quelque chose en essayant.

---

# A. Ce que vous faites seul, dans votre navigateur

À la fin de cette partie vous aurez **trois informations** notées quelque part.
Ce sont elles qui font tout marcher :

1. une **clé API Anthropic** — une longue suite de caractères qui commence par `sk-ant-`
2. un **fichier JSON** téléchargé depuis Google — le laissez-passer du robot
3. l'**identifiant du dossier Drive d'entrée** — un bout de l'adresse du dossier

Gardez-les de côté au fur et à mesure. On les rassemblera en partie B.

## A1. La clé Anthropic (10 minutes)

C'est ce qui permet à Saisio de lire les factures.

1. Allez sur **console.anthropic.com** et connectez-vous (créez le compte si
   vous n'en avez pas — c'est le compte du cabinet, pas un compte personnel).
2. En bas à gauche, cliquez sur votre nom → **Settings**.
3. Dans le menu de gauche : **API keys** → bouton **Create Key** en haut à droite.
4. Dans *Name*, tapez `saisio-production`. Ce nom ne sert qu'à vous : le jour où
   vous voudrez couper l'accès, vous saurez laquelle supprimer. → **Add**.
5. **La clé s'affiche une seule fois.** Cliquez sur l'icône « copier » et
   collez-la tout de suite dans un fichier texte sur votre bureau. Si vous
   fermez la fenêtre sans copier, ce n'est pas grave : supprimez la clé et
   refaites l'étape 3.

> **Ne mettez pas cette clé dans un mail, ni dans un document partagé.** C'est
> l'équivalent d'un moyen de paiement : qui l'a, dépense sur le compte du
> cabinet.

6. Toujours dans *Settings*, allez dans **Limits** et fixez un plafond mensuel
   de **50 €**. Vos 168 dossiers coûteront environ 10 € par mois au total : un
   plafond à 50 € laisse largement la place, et vous protège si quelque chose
   tourne en boucle.
7. Enfin, **Billing** → ajoutez une carte et créditez 20 €. Sans crédit, la clé
   existe mais ne répond pas.

## A2. Le robot Google (25 minutes)

C'est la partie la plus longue, et la seule où les écrans sont un peu austères.
Suivez les clics, ne cherchez pas à comprendre chaque écran.

Ce qu'on fabrique ici s'appelle un **compte de service**. Voyez-le comme un
salarié robot du cabinet : il a sa propre adresse mail, et il ne voit **que** ce
que vous lui partagez explicitement. Il ne peut pas fouiller votre Drive.

### a. Créer le projet

1. Allez sur **console.cloud.google.com**, connecté avec le compte Google du
   cabinet (celui qui possède le Drive).
2. Tout en haut, à côté de « Google Cloud », il y a un **sélecteur de projet**
   (souvent écrit *Sélectionner un projet*). Cliquez dessus → **Nouveau projet**.
3. Nom du projet : `saisio`. → **Créer**. Attendez 10 secondes, puis
   **vérifiez que le sélecteur en haut affiche bien « saisio »**. C'est l'erreur
   n°1 : faire la suite dans le mauvais projet.

### b. Autoriser l'accès à Drive

4. Cliquez sur le menu **☰** en haut à gauche → **API et services** →
   **Bibliothèque**.
5. Dans la barre de recherche, tapez `Google Drive API`. Cliquez sur le résultat
   du même nom, puis sur le gros bouton **Activer**. Attendez la fin.

### c. Créer le robot

6. Menu **☰** → **IAM et administration** → **Comptes de service**.
7. En haut : **+ Créer un compte de service**.
   - *Nom du compte de service* : `saisio-drive`
   - Cliquez **Créer et continuer**.
8. L'écran suivant demande un rôle. **Ne mettez aucun rôle.** Cliquez
   directement **Continuer**, puis **OK**.

   *Pourquoi ? Parce que les droits du robot viendront des partages Drive, que
   tout le monde peut voir et retirer d'un clic. Un rôle coché ici serait
   invisible et personne ne le retrouverait dans six mois.*

9. Le robot apparaît dans la liste, avec une adresse du genre
   `saisio-drive@saisio-123456.iam.gserviceaccount.com`. **Copiez cette adresse**
   dans votre fichier texte : on va la partager au Drive juste après.

### d. Télécharger son laissez-passer

10. Cliquez sur le robot que vous venez de créer → onglet **Clés** →
    **Ajouter une clé** → **Créer une clé** → choisissez **JSON** → **Créer**.
11. Un fichier se télécharge (`saisio-123456-abcdef.json`). Il part dans votre
    dossier *Téléchargements*.
12. Rangez-le : créez un dossier `Saisio` dans vos **Documents**, et déplacez le
    fichier dedans.

> **Ce fichier est un mot de passe.** Il ne va jamais dans un mail, jamais sur
> un Drive partagé, jamais sur GitHub. S'il fuite, revenez sur cet écran,
> supprimez la clé, créez-en une autre : l'ancienne cesse instantanément de
> fonctionner.

## A3. Les deux dossiers Drive (10 minutes)

1. Dans le Drive du cabinet, créez deux dossiers à la racine, s'ils n'existent
   pas déjà :
   - **Input compta tréso** — là où arriveront les pièces des clients
   - **Documents générés par l'application** — là où Saisio rangera ses sorties

2. Clic droit sur **Input compta tréso** → **Partager** → collez l'adresse du
   robot (celle en `…iam.gserviceaccount.com`) → dans le menu déroulant à
   droite, choisissez **Lecteur** → décochez *Envoyer une notification* (le
   robot ne lit pas ses mails) → **Partager**.

3. Même chose sur **Documents générés par l'application**, mais en **Éditeur**
   cette fois : c'est là qu'il doit pouvoir écrire.

| dossier | droit à donner | pourquoi |
|---|---|---|
| Input compta tréso | **Lecteur** | Saisio lit les pièces et n'y touche jamais |
| Documents générés par l'application | **Éditeur** | c'est sa zone de dépôt |

> Partagez bien **le dossier racine**, pas un sous-dossier. Saisio descend tout
> seul dans `client / année /`. Un partage posé trop bas est la cause n°1 du
> message « aucune pièce trouvée ».

4. Ouvrez **Input compta tréso** en double-cliquant. Regardez la barre
   d'adresse du navigateur :

   ```
   https://drive.google.com/drive/folders/1AbCdEfGhIjKlMnOpQrStUvWxYz
                                          └────── copiez ceci ──────┘
   ```

   Copiez ce qui suit `folders/` dans votre fichier texte. C'est la troisième
   information.

**Fin de la partie A.** Vous avez : la clé `sk-ant-…`, le fichier JSON dans
*Documents/Saisio*, et l'identifiant du dossier d'entrée.

---

# B. Installer Saisio sur votre ordinateur

Pour le pilote, on installe sur **votre** poste, pas sur le serveur du cabinet.
Deux raisons : vous n'avez besoin de personne, et si quelque chose ne va pas,
ça n'affecte personne d'autre. Le serveur, ce sera la partie D.

## B1. Ouvrir le terminal

C'est une fenêtre où l'on tape des commandes au lieu de cliquer.

- **Mac** : `Cmd + Espace`, tapez `Terminal`, Entrée.
- **Windows** : touche Windows, tapez `PowerShell`, Entrée.

Une fenêtre s'ouvre avec du texte et un curseur qui clignote. À partir d'ici :
vous **copiez** une ligne de ce guide, vous la **collez** dans cette fenêtre
(`Cmd+V` sur Mac, clic droit sur Windows), vous appuyez sur **Entrée**, et vous
attendez que le curseur revienne avant la ligne suivante.

## B2. Vérifier que Python est là

Python est le langage dans lequel Saisio est écrit. Copiez :

**Mac**
```bash
python3 --version
```

**Windows**
```powershell
python --version
```

Si vous voyez `Python 3.11.5` (ou n'importe quel numéro qui commence par 3),
c'est bon, passez à B3.

Si vous voyez une erreur : allez sur **python.org/downloads**, téléchargez la
version proposée, installez-la. **Sur Windows, à la première fenêtre de
l'installateur, cochez la case « Add Python to PATH » en bas** — sans elle, la
commande ne sera pas trouvée. Fermez le terminal, rouvrez-en un, recommencez.

## B3. Récupérer Saisio

```bash
cd ~/Documents/Saisio
git clone https://github.com/familleleguayetjoy-collab/LMNP.git
cd LMNP
```

Si `git` n'est pas reconnu : sur Mac, la commande vous propose elle-même de
l'installer, acceptez. Sur Windows, installez **git-scm.com/download/win** en
laissant toutes les options par défaut, puis rouvrez PowerShell.

## B4. Le premier test, tout de suite

Avant même de brancher quoi que ce soit, vérifiez que le cœur tourne :

**Mac**
```bash
python3 tool/verifier_branchement.py --etape moteur
```

**Windows**
```powershell
python tool\verifier_branchement.py --etape moteur
```

Vous devez voir trois lignes vertes avec des ✓, puis `Tout est branché.`
Le moteur n'a besoin de rien d'autre que Python. Si cette étape passe, la suite
n'est plus qu'une affaire de branchements.

## B5. Le fichier de réglages

C'est ici qu'on range les trois informations de la partie A. **Un simple fichier
texte**, à la racine du projet.

```bash
cp saisio.env.exemple saisio.env
```

*(Sur Windows : `copy saisio.env.exemple saisio.env`)*

Puis ouvrez-le :

- **Mac** : `open -e saisio.env`
- **Windows** : `notepad saisio.env`

Remplissez les trois lignes. Voici à quoi ça doit ressembler une fois complété :

```
ANTHROPIC_API_KEY=sk-ant-api03-VotreVraieCléIci
GOOGLE_APPLICATION_CREDENTIALS=/Users/paul/Documents/Saisio/saisio-123456.json
SAISIO_DRIVE_ENTREE=1AbCdEfGhIjKlMnOpQrStUvWxYz
```

Trois pièges, les seuls :

- **Pas d'espace** autour du `=`, pas de guillemets.
- Le chemin du JSON doit être **complet**. Pour l'obtenir sans se tromper : sur
  Mac, glissez-déposez le fichier depuis le Finder directement dans la fenêtre
  du terminal, le chemin s'écrit tout seul. Sur Windows, clic droit sur le
  fichier → *Copier en tant que chemin d'accès*, et **retirez les guillemets**
  que Windows ajoute.
- Ne mettez rien dans `SAISIO_DRIVE_SORTIE` pour l'instant : on ne fait que lire.

Enregistrez, fermez.

> `saisio.env` contient vos secrets. Il est déjà exclu de GitHub : même en
> lançant une sauvegarde du projet, il ne partira pas. Ne le copiez pas
> ailleurs.

## B6. Installer les trois compléments

Le moteur seul n'a besoin de rien, mais pour lire les factures et parler à
Drive il faut trois bibliothèques :

**Mac**
```bash
python3 -m pip install anthropic google-api-python-client google-auth Pillow pypdfium2
```

**Windows**
```powershell
python -m pip install anthropic google-api-python-client google-auth Pillow pypdfium2
```

Ça défile pendant une minute et se termine par `Successfully installed …`.
`Pillow` et `pypdfium2` ne sont pas décoratifs : ce sont eux qui réduisent les
images avant de les envoyer. Sans eux, chaque facture coûte plusieurs fois son
prix.

## B7. Vérifier la clé, puis le Drive

Une étape à la fois, dans cet ordre. **Ne passez à la suivante que si la
précédente est verte.**

```bash
python3 tool/verifier_branchement.py --etape cle
```

Le script fait un vrai appel à l'API et vous affiche ce qu'il a coûté — de
l'ordre de deux millièmes d'euro. Puis :

```bash
python3 tool/verifier_branchement.py --etape drive
```

Là, le script vous dit ce que le robot **voit réellement** : le nom du dossier
et les premières pièces. C'est le moment de vérité du partage.

### Si ça coince

| ce que vous lisez | ce qui se passe | ce que vous faites |
|---|---|---|
| `clé API absente` | le fichier n'est pas lu | il doit s'appeler exactement `saisio.env`, à la racine du projet, à côté de `README.md`. Windows a pu l'enregistrer en `saisio.env.txt` |
| `appel à l'API refusé` | clé fausse ou compte sans crédit | recopiez la clé sans espace avant/après ; vérifiez *Billing* dans la console |
| `connecteur indisponible` | les bibliothèques Google manquent | refaites B6 et lisez la fin du message |
| `accès refusé` | le robot ne voit pas le dossier | le partage a été fait à la mauvaise adresse. Rouvrez le JSON, cherchez `"client_email"`, c'est **cette** adresse-là qu'il faut partager |
| `aucune pièce lisible` | le dossier est vide **ou** le partage est sur un sous-dossier | déposez un PDF de test à la racine de *Input compta tréso* et relancez |

Le script s'arrête toujours au premier obstacle et dit quoi faire. Il ne
continue jamais en silence.

---

# C. Le premier vrai test

Maintenant on fait passer de vraies pièces dans toute la chaîne.

**Choisissez un dossier client dont la comptabilité est déjà bouclée.** C'est
essentiel : on connaît la bonne réponse. Un essai sur un dossier neuf montre
que ça tourne, pas que c'est juste — et c'est la justesse qui nous intéresse.

Déposez ses pièces dans *Input compta tréso*, puis :

```bash
python3 tool/verifier_branchement.py --etape bout --limite 5
```

Le script lit 5 pièces, les classe, les impute, calcule où elles iraient, et
affiche le coût. **Il n'écrit rien** — ni sur le Drive, ni dans le dossier
d'entrée. Tout part dans un dossier temporaire dont il vous donne le chemin.

Regardez trois choses, dans cet ordre :

1. **Le classement.** Les devis, contrats et photos sont-ils écartés, avec un
   motif juste ? Une facture prise pour un devis est bien plus grave qu'un devis
   pris pour une facture : dans un cas on perd une charge, dans l'autre on la
   voit passer en contrôle.
2. **Le plan de rangement.** L'exercice est-il le bon ? Les mois correspondent-
   ils aux **dates de règlement**, pas aux dates de facture ?
3. **Le coût.** Environ 0,4 centime par pièce. Nettement plus veut dire que les
   images ne sont pas réduites : relisez les avertissements, c'est presque
   toujours Pillow ou pypdfium2 qui manque.

Quand ces trois points sont bons, montez à `--limite 30`, puis passez aux
**trois dossiers de contrôle** : là, on compare ligne à ligne avec ce que vos
collaborateurs ont saisi à la main. C'est ce qui décide si on met l'outil entre
leurs mains.

---

# D. Plus tard : le cabinet

Rien de ce qui suit n'est nécessaire pour le pilote. C'est la liste à donner à
un technicien le jour où les 15 postes doivent y accéder.

- **Sortir des postes.** Aujourd'hui la clé et le JSON sont sur votre
  ordinateur. Sur le serveur du cabinet, ils vont dans un dossier à accès
  restreint, et personne d'autre ne les recopie.
- **Un traitement programmé.** Une fois par nuit, ou deux fois par jour :
  Saisio relève le dossier d'entrée, traite ce qui est nouveau, et dépose. Le
  manifeste garantit qu'une pièce déjà lue n'est jamais repayée.
- **Le travail simultané.** Tant que vous êtes seul, aucun problème. À
  plusieurs sur un même dossier, il faut un verrou — c'est prévu, pas encore
  branché.
- **La lettre de mission.** Avant de partager le Drive d'un **client** au
  robot, la lettre doit mentionner le dépôt des pièces et le recours à un
  traitement automatisé. C'est un préalable, pas une formalité.

---

## Les quatre choses à ne jamais faire

- **Ne donnez aucun rôle projet au compte de service.** Ses droits doivent
  venir des partages Drive, visibles et révocables par tout le monde.
- **Ne partagez pas le Drive d'un client** au robot avant que la lettre de
  mission soit à jour.
- **Ne laissez pas Saisio écrire dans le dossier d'entrée.** Le code s'y refuse
  (il ne demande à Google qu'un droit de lecture), et c'est ce qui garantit
  qu'un collaborateur ne perdra jamais un fichier pendant un traitement.
- **N'importez rien dans Quadra** avant que les trois dossiers de contrôle
  soient passés.

---

## Ce qu'il me faut de vous

| quoi | pour |
|---|---|
| l'adresse Google du cabinet | c'est elle qui portera le projet Cloud |
| l'identifiant du dossier d'entrée | brancher la lecture |
| la clé Anthropic, posée dans `saisio.env` | faire tourner la lecture des factures |
| **trois dossiers clients déjà bouclés** | mesurer la justesse, pas seulement le fonctionnement |
| la liste Excel client / email / société | adresser les mails de relance |

Les trois dossiers bouclés sont le point important. Le reste, c'est du
branchement : ça marche ou ça ne marche pas, et le script le dit. Eux seuls
disent si l'outil a le droit d'aller entre les mains des collaborateurs.
