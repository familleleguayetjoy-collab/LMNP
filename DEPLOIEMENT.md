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
| **D** | Se servir de l'outil, et le mettre à jour | terminal, une commande | 10 min |
| **E** | Plus tard : les 15 postes du cabinet | un technicien | — |

Une règle avant de commencer : **jusqu'à la fin de la partie C, rien n'écrit
quoi que ce soit**, ni sur le Drive, ni dans vos dossiers clients. Saisio lit.
Vous ne pouvez pas casser quelque chose en essayant. La seule commande qui
dépose des fichiers est en partie D, et il faut le lui demander explicitement.

---

# A. Ce que vous faites seul, dans votre navigateur

À la fin de cette partie vous aurez **trois informations** notées quelque part.
Ce sont elles qui font tout marcher :

1. une **clé API Anthropic** — une longue suite de caractères qui commence par `sk-ant-`
2. un **fichier JSON** téléchargé depuis Google — le laissez-passer du robot
3. les **identifiants des deux dossiers Drive** — un bout de leur adresse

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

   Copiez ce qui suit `folders/` dans votre fichier texte.

5. **Refaites la même chose sur « Documents générés par l'application ».**
   Notez bien lequel est lequel : c'est le dossier d'entrée que Saisio lit, et
   le dossier de sortie où il dépose. Les intervertir est l'erreur la plus
   naturelle du branchement — et la plus déroutante, parce que le dossier de
   sortie est vide et ressemble alors trait pour trait à un partage raté.

**Fin de la partie A.** Vous avez : la clé `sk-ant-…`, le fichier JSON dans
*Documents/Saisio*, et les identifiants des deux dossiers Drive.

---

# B. Installer Saisio sur votre ordinateur

Pour le pilote, on installe sur **votre** poste, pas sur le serveur du cabinet.
Deux raisons : vous n'avez besoin de personne, et si quelque chose ne va pas,
ça n'affecte personne d'autre. Le serveur, ce sera la partie E.

> ### À lire avant de copier quoi que ce soit
>
> Les commandes de ce guide sont encadrées par des lignes de trois accents
> graves. **Ces lignes ne se copient pas** : ce sont des marques de mise en
> page, pas des commandes. Seule la ligne du milieu se copie.
>
> ```
> ```powershell        ← ne pas copier
> python --version     ← copier seulement ceci
> ```                  ← ne pas copier
> ```
>
> Si vous collez une ligne d'accents graves, le terminal répond
> `Le terme «```powershell» n'est pas reconnu…`. Ce n'est pas une panne :
> il vous dit qu'il ne connaît pas cette commande, parce que ce n'en est pas
> une. Ignorez et copiez la bonne ligne.

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

Si vous voyez `Python 3.13.2` (ou n'importe quel numéro qui commence par 3),
c'est bon, passez à B3.

### Si Python n'est pas installé

**Sur Windows**, le message est : *« Python est introuvable ; exécutez sans
arguments à installer à partir du Microsoft Store »*. Faites exactement ce
qu'il dit — tapez la commande **sans rien derrière** :

```powershell
python
```

Le Microsoft Store s'ouvre sur la page Python. Cliquez **Obtenir**, prenez la
version la plus récente proposée, attendez la fin de l'installation.

C'est la voie la plus simple sous Windows : le Store règle tout seul le
réglage que l'installateur classique de python.org fait rater à tout le monde
(la case « Add Python to PATH », qu'il faut cocher au bon moment sur le premier
écran, sinon rien ne fonctionne ensuite).

**Sur Mac**, allez sur **python.org/downloads** et installez la version
proposée.

Dans les deux cas, **fermez complètement la fenêtre du terminal et rouvrez-en
une neuve** avant de refaire `python --version`. Une fenêtre déjà ouverte ne
voit pas ce qui vient d'être installé — c'est l'erreur classique à cette étape,
et elle donne exactement le même message qu'avant, ce qui laisse croire que
l'installation a échoué.

## B3. Télécharger Saisio

Pas besoin d'installer git : le code se télécharge comme n'importe quel fichier,
depuis votre navigateur.

1. Cliquez sur ce lien — le téléchargement démarre tout seul :

   **https://github.com/familleleguayetjoy-collab/LMNP/archive/refs/heads/claude/s2a-intelligent-prototype-uv1peq.zip**

   *(Si vous préférez passer par la page du projet : allez sur
   github.com/familleleguayetjoy-collab/LMNP, cliquez sur le **sélecteur de
   branche** en haut à gauche de la liste des fichiers, choisissez
   `claude/s2a-intelligent-prototype-uv1peq`, puis bouton vert **Code** →
   **Download ZIP**. Cette branche-là et pas une autre : celle qui s'affiche par
   défaut est un autre projet.)*

2. Ouvrez le fichier `.zip` téléchargé (double-clic) : il produit un dossier
   nommé `LMNP-claude-s2a-intelligent-prototype-uv1peq`.
3. **Renommez-le en `LMNP`** (clic droit → Renommer) et **déplacez-le dans le
   dossier `Saisio`** que vous avez créé en A2. Vous devez donc avoir :

   ```
   Documents/
     Saisio/
       saisio-123456.json          ← le laissez-passer Google
       LMNP/                       ← le code
         README.md
         DEPLOIEMENT.md
         saisio.env.exemple
         tool/
   ```

4. Retournez dans le terminal et placez-vous dans ce dossier :

   ```bash
   cd ~/Documents/Saisio/LMNP
   ```

   *(Sur Windows : `cd $HOME\Documents\Saisio\LMNP`)*

   Vérifiez que vous êtes au bon endroit : tapez `ls` (Mac) ou `dir` (Windows).
   Vous devez voir `README.md`, `DEPLOIEMENT.md` et `tool`. Si vous voyez autre
   chose ou une erreur, c'est le nom du dossier qui ne correspond pas — revenez
   à l'étape 3.

> **Pour mettre à jour plus tard** : retéléchargez le ZIP, remplacez le dossier
> `LMNP` par le nouveau, et **recopiez votre `saisio.env`** dedans — il n'est pas
> dans le ZIP, c'est voulu, il contient vos secrets.

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
- `SAISIO_DRIVE_SORTIE` ne sert qu'en partie D, au moment de déposer ; vous
  pouvez le remplir tout de suite, ça ne déclenche rien.

Enregistrez, fermez.

> `saisio.env` contient vos secrets, et **le dépôt GitHub du projet est
> public** : n'importe qui peut lire le code. Le fichier est déjà exclu du
> dépôt (`.gitignore`), il ne partira donc jamais tout seul — mais ne le
> recopiez pas ailleurs, et ne mettez jamais de vraie pièce client dans le
> dossier du projet.

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
| `aucune pièce lisible dans « … »` | regardez **le nom du dossier** que le script affiche : si c'est *Documents générés par l'application*, `SAISIO_DRIVE_ENTREE` pointe sur le dossier de sortie, qui est vide | reprenez l'identifiant dans l'URL de **Input compta tréso** ; sinon déposez un PDF de test à sa racine et relancez |

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

# D. Se servir de l'outil

`verifier_branchement.py` vérifie ; il ne travaille pas. La commande de tous
les jours est **`traiter.py`**.

## D0. Autoriser Saisio à déposer (compte Gmail gratuit)

**À faire une seule fois, et seulement si votre Drive est un compte Gmail
gratuit.** Sur Google Workspace, sautez cette étape : mettez simplement le
dossier de sortie dans un **Drive partagé** et ajoutez-y le compte de service
comme *Gestionnaire de contenu*.

Pourquoi c'est nécessaire : **un compte de service ne possède aucun octet de
stockage.** Il crée les dossiers — un dossier ne pèse rien — et ne peut déposer
aucun fichier dans un « Mon Drive », parce que le fichier lui appartiendrait.
Vous verriez l'arborescence se construire et pas une seule facture arriver.
Google règle ça par les Drive partagés, qui n'existent pas sur un compte
gratuit. Saisio doit donc déposer **en votre nom**, dans votre espace à vous.

> **La lecture ne change pas.** Le dossier d'entrée reste lu par le compte de
> service, en Lecteur. Ce qui borne ce que l'outil peut lire, c'est le partage
> Drive — visible par tout le monde, révocable en un clic. On ne troque pas
> cette garantie contre une commodité.

### a. Créer l'identifiant OAuth

1. **console.cloud.google.com**, projet `saisio` (vérifiez le sélecteur en haut).
2. Menu ☰ → *APIs et services* → **Écran de consentement OAuth**. S'il n'est pas
   configuré : type **Externe** → nom de l'application `Saisio` → votre adresse
   comme e-mail d'assistance et de contact → *Enregistrer*.
3. Toujours dans l'écran de consentement, section **Utilisateurs test** :
   ajoutez votre propre adresse Google.
4. Puis **Publier l'application** (bouton *Publier* / *Passer en production*).
   C'est important : tant que l'application reste en *Test*, Google fait expirer
   l'autorisation **au bout de 7 jours** et il faudrait se reconnecter chaque
   semaine. En production non vérifiée, elle n'expire pas. Google affichera un
   écran « application non validée » — c'est normal, c'est la vôtre.
5. Menu ☰ → *APIs et services* → **Identifiants** → *Créer des identifiants* →
   **ID client OAuth** → type **Application de bureau** → *Créer* → **Télécharger
   le JSON**.

### b. Poser le fichier et se connecter

Renommez le fichier téléchargé en `client_oauth.json` et posez-le dans
`C:\Users\<vous>\.saisio`. Si le dossier n'existe pas, créez-le :

```powershell
New-Item -ItemType Directory -Force "$HOME\.saisio" | Out-Null ; explorer "$HOME\.saisio"
```

Puis, une seule fois :

```powershell
cd $HOME\Documents\Saisio\LMNP ; python tool\connexion_google.py
```

Une fenêtre de navigateur s'ouvre. Choisissez le compte Google qui porte le
Drive. À l'écran « Google n'a pas validé cette application », cliquez
**Paramètres avancés** puis **Accéder à Saisio**.

Pour vérifier plus tard : `python tool\connexion_google.py --etat`.
Pour couper : `--oublier` en local, et *myaccount.google.com/permissions* côté
Google.

> Le jeton produit vaut un mot de passe : il ouvre votre Drive. Il reste dans
> `~/.saisio`, ne part jamais sur GitHub, et ne quitte pas votre machine.

## D1. Ranger le Drive d'entrée

```
Input compta tréso/
  LMNP POLO TEST/
    2026/
      facture-edf.pdf
      ...
```

Un dossier par client, un sous-dossier par année. C'est ce que la commande
attend, et c'est ce que le Drive de sortie reproduira.

## D2. Le premier passage, à blanc

```powershell
cd $HOME\Documents\Saisio\LMNP ; python tool\traiter.py --client "LMNP POLO TEST" --exercice 2026
```

**Rien n'est écrit.** C'est le comportement par défaut, et il n'y a pas de
raison d'en changer tant que vous n'êtes pas d'accord avec ce que la commande
annonce. Elle affiche : les pièces neuves, le classement avec le motif de
chaque pièce écartée, le plan de rangement complet, ce qu'elle aurait déposé,
et ce que l'OCR a coûté.

## D3. Le dépôt réel

Quand le plan vous convient, ajoutez `--deposer` :

```powershell
cd $HOME\Documents\Saisio\LMNP ; python tool\traiter.py --client "LMNP POLO TEST" --exercice 2026 --deposer
```

Les pièces arrivent alors dans le Drive de sortie, sous :

```
Documents générés par l'application/
  LMNP POLO TEST/
    Exercice 2026/
      2026-03/
        Traité/
        En attente de traitement/
    Autres éléments sans rapport avec la comptabilité/
```

Une pièce déjà lue n'est jamais relue ni repayée. Pour rejouer un dossier
entier pendant la phase de calage :

```powershell
python tool\traiter.py --client "LMNP POLO TEST" --exercice 2026 --refaire --deposer
```

L'OCR est alors repayé, mais le dépôt ne duplique rien : les pièces déjà
présentes dans le Drive de sortie sont reconnues et laissées en place.

Il faut pour cela que **`SAISIO_DRIVE_SORTIE`** soit renseigné dans
`saisio.env` (l'identifiant du dossier de sortie, pris dans son URL comme pour
l'entrée), et que ce dossier soit partagé au compte de service en **Éditeur**,
pas en Lecteur.

Trois garanties tenues par le code, pas par la consigne :

- **rien n'est jamais écrasé ni supprimé.** Un nom déjà présent est laissé tel
  quel et signalé ;
- **relancer ne duplique rien.** Une pièce déjà déposée est reconnue ;
- **le dossier d'entrée n'est jamais modifié.** Il est partagé en Lecteur, et
  le connecteur de lecture ne contient aucune méthode d'écriture.

## D4. Ce que la commande ne fait pas encore

Elle **ne produit aucune écriture comptable**, et c'est volontaire. En
comptabilité de trésorerie, c'est le relevé bancaire qui décide de ce qui est
comptabilisé et à quelle date. Produire des écritures à partir des seules
factures donnerait des dates fausses et des charges peut-être jamais payées.

Le moteur sait tenir tout le chemin — il est testé — il lui manque **un lecteur
de relevé bancaire**. Pour le construire, il me faut un export réel de votre
banque (CSV ou Excel, anonymisé si vous préférez) et le FEC N‑1 du dossier
pilote.

## D5. Mettre à jour l'outil

```powershell
cd $HOME\Documents\Saisio\LMNP ; .\maj.ps1
```

Le script retélécharge la dernière version et la pose par-dessus. **Votre
`saisio.env` n'est pas touché** — il ne fait pas partie du téléchargement. Les
manifestes non plus : ils vivent dans `~/.saisio`, hors du projet, précisément
pour qu'une mise à jour ne fasse pas repayer l'OCR de tout l'historique.

Si Windows refuse d'exécuter le script (« l'exécution de scripts est désactivée
sur ce système »), autorisez-le une fois pour votre compte :

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

---

# E. Plus tard : le cabinet

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
