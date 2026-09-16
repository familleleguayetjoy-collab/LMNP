# Le fichier d'entrée, et comment le remplir sans se tromper

`scripts/saisio.py` lit un seul fichier JSON. Tout ce qui touche à un montant se
passe ensuite dans le code : le rapprochement, les dates, le fichier Quadratus.
Ce fichier est donc le seul endroit où une erreur de lecture peut entrer — d'où
les précautions ci-dessous.

## Le fichier complet

```json
{
  "dossier": "LMNP POLO TEST",
  "exercice": 2026,
  "avec_banque": true,
  "assujetti_tva": false,
  "compte_banque": "512000",
  "releve": {"solde_initial": 1204.55, "solde_final": 2890.12},
  "operations": [
    {"date": "2026-08-03", "libelle": "EDF ENERGIE", "montant": 57.79, "sens": "D"}
  ],
  "factures": [
    {"fournisseur": "EDF", "date": "2026-08-01", "ttc": 57.79,
     "ht": 48.16, "tva": 9.63, "numero": "F2026-114", "fichier": "edf.pdf",
     "payee": false, "date_reglement": null}
  ],
  "fec_n1": "chemin/vers/fec_2025.txt",
  "decisions": {}
}
```

| champ | ce qu'il fait |
|---|---|
| `avec_banque` | `false` = dossier sans relevé : tout part en OD, contrepartie 108 |
| `assujetti_tva` | presque toujours `false` en LMNP : on comptabilise le TTC |
| `releve` | les soldes d'ouverture et de clôture — ils servent au contrôle |
| `fec_n1` | le FEC de l'exercice précédent : il code seul tout ce qui revient |
| `decisions` | `{"OP007": "615000"}` — ce que le collaborateur a tranché |

## Les opérations

`sens` vaut `"D"` pour une sortie de banque, `"C"` pour une entrée. `montant`
est **toujours positif** : c'est `sens` qui porte le signe. Un relevé qui
affiche `-57,79` donne donc `{"montant": 57.79, "sens": "D"}`.

Reprenez le **libellé brut du relevé**, sans le nettoyer. `PRLV SEPA EDF
ENERGIE 2408` est plus utile que `EDF` : c'est ce libellé qui se retrouve dans
le FEC de l'an prochain, et c'est sur lui que le dictionnaire apprend.

## Le contrôle qui rattrape une transcription ratée

Quand le relevé est un PDF, quelqu'un le recopie — et une ligne sautée ne se
voit plus une fois les écritures passées. D'où `releve.solde_initial` et
`releve.solde_final` : le script vérifie que la somme des mouvements égale la
variation de solde, et **refuse de produire le fichier** si ça ne tombe pas.

Renseignez-les toujours. Sans eux le script le dit en toutes lettres — « la
transcription n'a PAS été contrôlée » — plutôt que de laisser croire qu'elle
l'a été.

Quand le relevé arrive en CSV ou en Excel, ne le recopiez pas : lisez-le avec
du code (`csv`, ou `openpyxl` s'il est disponible) et construisez les opérations
à partir des cellules. Aucune main humaine ni aucun modèle entre le fichier de
la banque et le JSON, c'est autant d'erreurs impossibles.

## Les factures

`payee` et `date_reglement` décident de tout ce qui n'est pas au relevé :

| ce que dit la pièce | ce qui se passe |
|---|---|
| retrouvée au relevé | écriture au journal BQ, **datée du mouvement** |
| « payée le 25/08 », absente du relevé | OD contrepartie 108, **datée du 25/08** |
| « payée », sans date | OD datée de la facture, **signalée à confirmer** |
| rien : ni banque, ni mention | **aucune écriture** — on interroge le client |

Ce dernier cas est le plus facile à rater. Une facture sans règlement identifié
n'est pas une charge de l'exercice : elle reste ouverte et tombera dans
l'exercice où elle sera payée. Ne mettez `payee: true` que si la pièce le dit.

`ht` et `tva` ne servent qu'aux contrôles de cohérence et à la détection de
doublons. En LMNP non assujetti, c'est le TTC qui est comptabilisé.

## Ce que le script renvoie

```json
{
  "controle_releve": {"ok": true, "message": "relevé équilibré"},
  "compte": {"operations": 42, "a_trancher": 5, "a_reclamer": 3},
  "a_trancher": [{"cle": "OP007", "libelle": "...", "options": ["615", "606"]}],
  "a_reclamer": [...],
  "sans_reglement": [...],
  "doublons": [...],
  "equilibre_quadra": [debit, credit, true]
}
```

`cle` est l'identifiant stable d'une ligne : `OP001` pour les mouvements de
banque dans l'ordre du fichier, `OD001` pour les factures payées hors banque.
C'est cette clé qu'on met dans `decisions` pour refermer une question, et on
relance le script — rien d'autre ne bouge.
