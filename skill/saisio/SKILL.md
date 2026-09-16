---
name: saisio
description: >
  Prépare un dossier de location meublée (LMNP, LMP, SCI, BNC) tenu en
  comptabilité de trésorerie : lit le relevé bancaire et les factures, rapproche
  les pièces des mouvements, impute les comptes du plan du cabinet S2A, signale
  ce qui demande une décision humaine, et produit le fichier d'import Quadratus
  ainsi que la liste des justificatifs à réclamer au client. Utilise ce skill dès
  qu'un relevé bancaire, des factures de charges locatives, un FEC ou un dossier
  meublé apparaissent dans la conversation — et aussi quand la demande est
  partielle : « quel compte pour cette facture », « est-ce que ça s'immobilise »,
  « fais-moi le fichier Quadra », « qu'est-ce qui manque comme justificatif »,
  « passe l'OD pour cette facture payée en perso », « rapproche ces factures du
  relevé ». Déclenche aussi sur : compta de trésorerie, écriture d'OD,
  contrepartie 108, compte 471, seuil d'immobilisation, taxe foncière 63512,
  échéance de prêt à ventiler 661/164, dépôt de garantie 165.
---

# Saisio — préparer un dossier meublé en comptabilité de trésorerie

## La règle qui gouverne tout

**Les montants sont du code, jamais de l'IA.**

Vous lisez les pièces et vous proposez. Vous ne calculez aucun total, ne
rapprochez aucune facture, ne datez aucune écriture, n'additionnez aucune
colonne. Tout cela se passe dans `scripts/saisio.py`, qui est testé et
déterministe : mêmes entrées, même sortie, à la virgule.

Ce n'est pas une précaution de principe. Un rapprochement fait « de tête » est
invérifiable : il paraît juste, il ne laisse aucune trace, et personne ne le
relira. Le collaborateur qui reprend le dossier dans six mois doit pouvoir
refaire tourner le même script sur les mêmes données et retomber sur le même
fichier.

Votre travail, lui, est irremplaçable : **lire** une facture mal scannée,
**reconnaître** qu'un libellé bancaire obscur est un syndic, **repérer** qu'une
dépense de 1 800 € en meubles s'immobilise, et **dire** ce dont vous n'êtes pas
sûr. C'est beaucoup, et c'est exactement ce que le code ne sait pas faire.

## La règle comptable de fond

On tient ces dossiers en **comptabilité de trésorerie**. Deux conséquences qui
expliquent presque tout :

1. **Le relevé bancaire fait foi.** C'est lui qui décide de ce qui est
   comptabilisé et à quelle date. Une facture retrouvée en banque prend la date
   du mouvement, même si la pièce en annonce une autre.

2. **Une seule exception** : une facture qui se déclare payée et qu'on ne
   retrouve **pas** au relevé — réglée par l'exploitant à titre personnel. On
   passe alors une écriture au **journal d'OD, contrepartie 108**, **datée du
   jour du règlement**, pas de la facture.

Et le corollaire, celui qu'on oublie : **pas de flux, pas d'écriture.** Une
facture sans mouvement bancaire et sans mention de règlement n'a jamais été
payée. Elle ne produit rien, elle reste ouverte, et on interroge le client. Lui
passer une écriture créerait une charge que personne n'a décaissée.

## Le déroulé

### 1. Rassembler ce qu'il y a

Demandez ce qui manque plutôt que de faire avec :

- le **relevé bancaire** de la période (indispensable, sauf dossier sans banque) ;
- les **factures** ;
- le **FEC N-1** si le dossier existait — il code tout seul ce qui revient
  chaque année, et c'est ce qui fait passer le nombre de lignes à trancher de
  quarante à cinq ;
- les **bornes de l'exercice** et le **type** (LMNP, LMP, SCI, BNC).

### 2. Transcrire le relevé — et le faire contrôler

Si le relevé est en **CSV ou Excel**, ne le recopiez pas : lisez-le avec du
code et construisez les opérations à partir des cellules. Aucune main entre le
fichier de la banque et les données, c'est autant d'erreurs impossibles.

Si c'est un **PDF ou une image**, vous devez le transcrire — et c'est le seul
moment où des montants passent par vous. Relevez donc aussi le **solde
d'ouverture et le solde de clôture** : le script vérifie que la somme des
mouvements égale la variation de solde et refuse d'aller plus loin si ça ne
tombe pas. Une ligne sautée ne se voit plus une fois les écritures passées ;
là, elle se voit tout de suite.

### 3. Lire les factures

Pour chaque pièce : fournisseur, date, TTC, HT, TVA, numéro. Et surtout, la
question qui décide de tout : **est-ce que la pièce dit qu'elle a été payée, et
quand ?** Un « payé le 25/08 », un « réglé par CB », un ticket de caisse. Ne
mettez `payee: true` que si la pièce le dit — c'est une affirmation sur le
monde, pas une hypothèse de travail.

Écartez ce qui n'est pas comptable en disant pourquoi : devis, bon de commande,
contrat de bail, relevé bancaire, photo. Un devis pris pour une facture crée une
charge fictive ; une facture prise pour un devis fait perdre une charge réelle.
Le second est moins grave, parce qu'il remonte en contrôle.

### 4. Lancer le moteur

Écrivez le JSON d'entrée (voir `references/format_entree.md`) puis :

```bash
python3 scripts/saisio.py dossier.json
```

Le script rend : le contrôle du relevé, ce qui est imputé seul, **ce qui reste à
trancher avec les comptes candidats**, ce qui est à réclamer au client, les
écarts de montant, les factures sans règlement, les doublons.

### 5. Présenter les décisions — c'est là que vous êtes utile

Ne rendez pas le JSON brut. Pour chaque ligne à trancher, présentez : la date,
le libellé, le montant, la pièce s'il y en a une, **votre proposition et
pourquoi**. Puis laissez trancher.

Une bonne proposition ressemble à ça :

> **OP004 — 11/09 · FNAC NICE CAP 3000 · 450,00 €** — aucune facture.
> Je propose **606** (petit équipement) : le montant est sous le seuil
> d'immobilisation de 500 € HT et l'enseigne vend surtout du consommable. Mais
> sans la pièce on ne sait pas si c'est un téléviseur, qui s'immobiliserait en
> 2183. **À réclamer au client.**

Une mauvaise proposition, c'est « 606 ». Le compte sans le raisonnement ne se
vérifie pas.

Regroupez ce qui se ressemble — quinze lignes du même syndic, c'est une
décision, pas quinze. Et signalez franchement ce dont vous doutez : un doute
exprimé coûte trente secondes, un doute tu coûte une révision de liasse.

Consultez `references/regles_controle.md` : ce sont les 36 points où le cabinet
veut un œil humain. Et `references/plan_comptable.md` pour les comptes.

### 6. Refermer et produire le fichier

Les décisions retournent dans le JSON, sous `decisions`, par clé de ligne :

```json
"decisions": {"OP001": "2184", "OP002": "2184", "OD001": "615"}
```

Puis :

```bash
python3 scripts/saisio.py dossier.json --sortie ./resultats
```

Vous obtenez le fichier Quadratus du journal de banque, celui des OD s'il y en
a, et un rapport. Annoncez le nombre de lignes, le total débit et le total
crédit, et **ce qui reste ouvert** — les justificatifs à réclamer, les factures
sans règlement. Un dossier n'est pas fini parce qu'un fichier est produit.

## Trois choses à ne pas faire

**Ne comblez pas un trou par une hypothèse.** Un montant illisible, une date
absente, un libellé incompréhensible : dites-le. Le compte **471** existe pour
ça, et une ligne en 471 assumée vaut mieux qu'une imputation plausible et
fausse — la première se retrouve, la seconde se découvre trois ans plus tard.

**Ne produisez pas le fichier tant que le relevé n'est pas équilibré.** Le
script refuse déjà ; ne le forcez pas avec `--forcer` sans que le collaborateur
ait compris et accepté l'écart.

**Ne transformez pas la demande.** Si on vous demande le compte d'une seule
facture, répondez sur cette facture. Le déroulé complet sert quand il y a un
dossier à faire, pas quand il y a une question à laquelle répondre.

## Fichiers du skill

| fichier | quand le lire |
|---|---|
| `references/format_entree.md` | avant d'écrire le JSON — le format, et les pièges de transcription |
| `references/plan_comptable.md` | pour choisir un compte : les comptes réellement utilisés par le cabinet |
| `references/regles_controle.md` | pour savoir ce qui mérite un contrôle humain : les 36 règles, par famille |
| `scripts/saisio.py` | le moteur — à lancer, pas à réécrire |
| `scripts/s2a_lmnp/` | le code comptable testé (bibliothèque standard seule) |
