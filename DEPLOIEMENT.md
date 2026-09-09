# Brancher Saisio — lundi

Quatre étapes, dans cet ordre. Après chacune, une commande vérifie qu'elle est
bien passée : ne passez à la suivante que si elle est verte.

```bash
python3 tool/verifier_branchement.py            # les quatre d'un coup
python3 tool/verifier_branchement.py --etape cle  # une seule
```

Le script **ne modifie rien, nulle part**. Il s'arrête au premier obstacle en
disant quoi faire.

---

## 1. Le moteur (5 minutes, rien à installer)

```bash
git clone <dépôt> && cd LMNP
python3 tool/verifier_branchement.py --etape moteur
```

Le cœur n'a aucune dépendance. Si cette étape échoue, le dépôt est incomplet.

---

## 2. La clé API Anthropic (10 minutes)

1. **console.anthropic.com** → *Settings* → *API keys* → *Create key*.
   Nommez-la `saisio-production` : on saura quoi révoquer le jour venu.
2. Copiez-la immédiatement — elle ne s'affiche qu'une fois.
3. Mettez-la dans l'environnement du serveur, **jamais dans le dépôt** :

   ```bash
   sudo install -d -m 750 /etc/saisio
   printf 'ANTHROPIC_API_KEY=sk-ant-…\n' | sudo tee /etc/saisio/env > /dev/null
   sudo chmod 600 /etc/saisio/env
   ```

4. Fixez un **plafond de dépense** dans la console (*Settings* → *Limits*).
   Un dossier de 200 factures coûte environ 0,80 € : un plafond à 50 €/mois
   laisse largement la place et vous protège d'une boucle folle.

```bash
pip install anthropic
set -a && . /etc/saisio/env && set +a
python3 tool/verifier_branchement.py --etape cle
```

Le test consomme moins d'un centime et vous affiche son coût réel.

---

## 3. Le compte de service Google (20 minutes)

Un compte de service est un « utilisateur robot » : il n'a accès qu'à ce qu'on
lui partage explicitement, et son accès n'expire pas. Pas de connexion
individuelle à renouveler, pas de consentement à re-donner chaque semaine.

### a. Créer le projet et le compte

1. **console.cloud.google.com** → en haut, sélecteur de projet →
   *Nouveau projet* → nom `saisio` → *Créer*.
2. Menu ☰ → *API et services* → *Bibliothèque* → cherchez **Google Drive API**
   → *Activer*.
3. Menu ☰ → *IAM et administration* → *Comptes de service* →
   **+ Créer un compte de service**.
   - Nom : `saisio-drive`
   - *Créer et continuer* → **ne donnez AUCUN rôle** (l'accès viendra du
     partage Drive, pas d'un rôle projet) → *OK*.
4. Cliquez le compte créé → onglet **Clés** → *Ajouter une clé* →
   *Créer une clé* → **JSON** → la clé se télécharge.

### b. Poser la clé sur le serveur

```bash
sudo cp ~/Téléchargements/saisio-*.json /etc/saisio/compte-service.json
sudo chmod 600 /etc/saisio/compte-service.json
printf 'GOOGLE_APPLICATION_CREDENTIALS=/etc/saisio/compte-service.json\n' \
  | sudo tee -a /etc/saisio/env > /dev/null
```

Ce fichier vaut un mot de passe. Il ne va **jamais** dans le dépôt, jamais dans
un mail, jamais sur un Drive partagé.

### c. Partager les deux dossiers

Ouvrez le JSON et repérez `"client_email"` — une adresse en
`saisio-drive@saisio-….iam.gserviceaccount.com`. C'est elle qu'on partage.

Dans le Drive du cabinet :

| dossier | partagé au compte de service en | pourquoi |
|---|---|---|
| **Input compta tréso** | **Lecteur** | Saisio lit les pièces et n'y touche jamais |
| **Documents générés par l'application** | **Éditeur** | c'est là qu'il range les sorties |

Faites le partage **sur le dossier racine**, pas sur un sous-dossier : Saisio
descend l'arborescence `client/année/` tout seul.

### d. Relever l'identifiant du dossier d'entrée

Ouvrez `Input compta tréso` dans le navigateur. L'URL se termine par
l'identifiant :

```
https://drive.google.com/drive/folders/1AbCdEfGhIjKlMnOpQrStUvWxYz
                                       └──────── c'est ça ────────┘
```

```bash
pip install google-api-python-client google-auth
printf 'SAISIO_DRIVE_ENTREE=1AbCdEf…\n' | sudo tee -a /etc/saisio/env > /dev/null
set -a && . /etc/saisio/env && set +a
python3 tool/verifier_branchement.py --etape drive
```

Le script vous dit ce que le compte de service **voit réellement** : le nom du
dossier et les premières pièces. Zéro pièce ne veut pas dire « dossier vide » —
c'est presque toujours un partage posé au mauvais endroit, et le message le
rappelle.

---

## 4. Un dossier réel, de bout en bout (30 minutes)

Choisissez **un dossier client dont la comptabilité est déjà faite** : on
connaît la bonne réponse, c'est le seul essai qui apprend quelque chose.

```bash
python3 tool/verifier_branchement.py --etape bout --limite 5
```

Ce que fait le script, dans l'ordre : il liste les pièces neuves, en lit cinq
par l'OCR, les classe, les impute, calcule le plan de rangement, et affiche le
coût réel. **Il n'écrit rien** — ni sur le Drive, ni dans le dossier d'entrée.
Tout va dans un dossier temporaire dont il donne le chemin.

Regardez trois choses :

1. **Le classement.** Les devis, contrats et photos sont-ils écartés, avec un
   motif juste ? Une facture prise pour un devis est plus grave qu'un devis pris
   pour une facture.
2. **Le plan de rangement.** L'exercice est-il le bon ? Les mois correspondent-
   ils aux dates de règlement ?
3. **Le coût.** Il doit tourner autour de 0,4 centime par pièce. Nettement plus
   veut dire que les images ne sont pas réduites — vérifiez que Pillow et
   pypdfium2 sont installés (`pip install Pillow pypdfium2`), leur absence est
   signalée dans les avertissements.

Quand c'est vert : on passe aux trois dossiers de contrôle, et là on compare
ligne à ligne avec ce que vos collaborateurs ont saisi à la main.

---

## Ce qu'il ne faut pas faire

- **Ne pas donner de rôle projet au compte de service.** Son périmètre doit
  venir des partages Drive, visibles par tout le monde, pas d'une case cochée
  dans une console que personne ne rouvre.
- **Ne pas partager le Drive d'un client au compte de service tant que la
  lettre de mission n'est pas à jour** (dépôt des pièces + recours à un
  sous-traitant technique).
- **Ne pas laisser Saisio écrire dans le dossier d'entrée.** Le code s'y refuse
  (`drive.readonly`), et c'est ce qui garantit qu'un collaborateur ne perdra
  jamais un fichier pendant un traitement.
- **Ne pas importer dans Quadra** avant que les trois dossiers de contrôle
  soient passés.

---

## Récapitulatif de ce qu'il me faut de vous

| quoi | pour |
|---|---|
| l'adresse Google qui portera le projet Cloud | créer le compte de service |
| les identifiants des deux dossiers Drive | brancher l'entrée et la sortie |
| la clé API Anthropic posée sur le serveur | faire tourner l'OCR |
| **trois dossiers clients déjà bouclés** | mesurer la justesse, pas seulement le fonctionnement |
| la liste Excel client / email / société | adresser les mails de relance |
