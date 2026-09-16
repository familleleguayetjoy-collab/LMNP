# Les 36 règles de contrôle du cabinet

Le niveau dit ce que l'outil fait de la ligne :

| niveau | effet |
|---|---|
| **Automatique** | l'outil impute seul, la ligne ne remonte pas |
| **À contrôler** | la ligne remonte, un humain la regarde |
| **Validation obligatoire** | la ligne remonte **et** ne peut pas être traitée en série |

Les règles marquées *(à brancher)* se paramètrent dans la maquette mais
attendent une donnée qui n'existe pas dans une conversation — historique
pluriannuel par fournisseur, balance du dossier, schémas d'écriture. Elles
restent utiles à lire : ce sont les endroits où un œil humain doit se poser,
même quand le moteur n'a rien signalé.


## Montant et significativité

- **Immobilisation détectée** · *Validation obligatoire*
  L'erreur vit plusieurs exercices dans le tableau d'amortissement.
- **Dépense non immobilisable au-delà de** — seuil 1500 € · *À contrôler*
  Au-dessus, l'enjeu dépasse le coût du contrôle.
- **Paiement sans facture disponible au-delà de** — seuil 150 € · *À contrôler*
  En dessous, on impute sans réclamer : la relance coûte plus que l'enjeu.
- **Montant inhabituel pour le fournisseur ou le dossier** · *À contrôler* *(à brancher)*
  Demande deux exercices d'historique par fournisseur.
- **Montant significatif au regard du CA, du résultat ou du bilan** · *À contrôler* *(à brancher)*
  Demande la balance du dossier.

## Fiabilité de l'affectation comptable

- **Confiance de l'IA sous le seuil** — seuil 95 € · *Validation obligatoire*
  Aucun compte proposé avec certitude : la ligne reste en 471 sans un humain.
- **Compte jamais utilisé auparavant sur le dossier** · *À contrôler*
  Aujourd'hui adossé au FEC N-1 : sans précédent, le compte est une hypothèse.
- **Affectation différente de l'habitude pour ce fournisseur** · *À contrôler* *(à brancher)*
  Demande l'historique des imputations par fournisseur.
- **Plusieurs traitements plausibles aux conséquences distinctes** · *Validation obligatoire* *(à brancher)*
  Entretien ou amélioration, charge ou immobilisation : l'écart se chiffre.
- **Traitement incohérent avec la nature de l'opération** · *Validation obligatoire* *(à brancher)*
  Contrôle croisé nature / compte, à écrire avec le cabinet.

## Anomalies documentaires et règlements

- **Doublon potentiel** · *Validation obligatoire* *(à brancher)*
  Écran de comparaison des deux pièces à construire (voir « Doublons »).
- **Écart entre le montant facturé et le montant payé** · *À contrôler* *(à brancher)*
  Le moteur sait déjà le calculer ; reste à le remonter à l'écran.
- **Paiement fractionné d'une même facture** · *À contrôler*
  La charge ne doit être comptabilisée qu'une fois.
- **Facture peut-être réglée plusieurs fois** · *Validation obligatoire* *(à brancher)*
  Le vrai risque : un double décaissement.
- **Plusieurs factures sur un même paiement, avec incohérence** · *À contrôler* *(à brancher)*
  Le moteur gère le rapprochement groupé ; l'écart doit remonter.
- **Facture sans règlement identifié après** — seuil 90 € · *À contrôler* *(à brancher)*
  Soit la pièce est en double, soit le règlement est ailleurs.
- **Règlement sans facture ni justificatif associé** · *À contrôler*
  Soit payée en perso (OD 108), soit hors dossier.
- **Acompte ou situation de travaux** · *À contrôler*
  Risque de double comptabilisation avec la facture de solde.

## Opérations sensibles

- **Dépense personnelle potentielle** · *Validation obligatoire* *(à brancher)*
  Nature de dépense étrangère à une location meublée.
- **Opération impliquant le dirigeant ou un associé** · *Validation obligatoire* *(à brancher)*
  À rapprocher du nom de l'exploitant.
- **Mouvement sur compte courant d'associé ou de l'exploitant** · *Validation obligatoire* *(à brancher)*
  Comptes 455 et 108 : détectable sur le compte proposé, à brancher.
- **Prêt ou emprunt** · *Validation obligatoire* *(à brancher)*
  Schéma d'écriture 661 / 164, pas un simple contrôle.
- **Crédit** · *Validation obligatoire* *(à brancher)*
  Découvert, crédit renouvelable, échéancier fournisseur.
- **Leasing** · *Validation obligatoire* *(à brancher)*
  Location financière sans option d'achat : redevance en 612.
- **Crédit-bail** · *Validation obligatoire* *(à brancher)*
  Redevance en 612 et engagement hors bilan. Recouvre le leasing en droit français.
- **Dépôt de garantie ou caution** · *Validation obligatoire* *(à brancher)*
  Compte 165, jamais une charge.
- **Opération sur capital** · *Validation obligatoire* *(à brancher)*
  Rare en LMNP, structurante en SCI.
- **Acquisition ou cession de titres** · *Validation obligatoire* *(à brancher)*
  Comptes 26x et plus-values : hors du champ courant.
- **Opération exceptionnelle ou non courante** · *Validation obligatoire* *(à brancher)*
  Tout ce qui ne ressemble à rien de connu sur le dossier.

## Cohérence avec l'activité

- **Nouveau fournisseur inhabituel pour l'activité** · *À contrôler* *(à brancher)*
  Demande une nomenclature d'activité par type de dossier.
- **Dépense incohérente ou atypique pour l'activité** · *À contrôler* *(à brancher)*
  Même besoin que la précédente.
- **Fournisseur connu, nature de dépense inhabituelle** · *À contrôler* *(à brancher)*
  Demande l'historique des imputations.
- **Montant très différent des montants habituels du fournisseur** · *À contrôler* *(à brancher)*
  Recoupe « montant inhabituel » plus haut : à fusionner ou à distinguer au pilote.
- **Libellé bancaire insuffisant ou ambigu** · *À contrôler* *(à brancher)*
  Recouvre en partie « confiance sous le seuil » ; à distinguer au pilote.

## Doublons

- **Doublon certain — écarté d'office** · *Automatique* *(à brancher)*
  Uniquement sur critères objectifs forts : même fournisseur, même numéro, même date, même montant — ou même empreinte de fichier. Le moteur calcule déjà les empreintes.
- **Doublon probable — comparaison obligatoire** · *Validation obligatoire* *(à brancher)*
  Les deux pièces côte à côte : Supprimer A, Supprimer B, ou « ce ne sont pas des doublons ».
