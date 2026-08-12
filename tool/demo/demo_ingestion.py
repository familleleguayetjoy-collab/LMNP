"""Démo : ingestion d'un 'Drive' + idempotence (jamais deux fois la même pièce).

Simule le dossier du client par un répertoire local (`DossierLocal`) — le vrai
connecteur Google Drive se branchera sur la MÊME interface. Montre l'idée clé
qui tient ton budget : on OCR **uniquement les pièces neuves**.

Scénario :
  1er passage  : 3 pièces déposées  -> 3 à OCR
  2e passage   : rien de neuf        -> 0 à OCR (aucun coût)
  puis 1 nouvelle pièce + 1 renommée -> 1 seule à OCR (le renommé est reconnu)

Aucune donnée client, aucune clé, aucun réseau.

Lancer :  python3 tool/demo/demo_ingestion.py
"""
import sys, os, tempfile, shutil
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from s2a_lmnp import DossierLocal, Manifeste, pieces_neuves


def deposer(dossier, nom, contenu):
    with open(os.path.join(dossier, nom), "wb") as f:
        f.write(contenu)


def passage(src, man, label):
    neuves = pieces_neuves(src, man)
    print("%s : %d pièce(s) à OCR%s" % (
        label, len(neuves), ("  -> " + ", ".join(p.nom for p in neuves)) if neuves else ""))
    for p in neuves:                       # en prod : OCR de la pièce ici
        man.marquer(p.empreinte, p.nom)    # puis on la marque traitée
    return len(neuves)


with tempfile.TemporaryDirectory() as drive:
    src = DossierLocal(drive)
    man = Manifeste(os.path.join(drive, "manifeste.json"))

    print("=" * 60)
    deposer(drive, "edf.pdf", b"FACTURE EDF 69.34")
    deposer(drive, "brico.pdf", b"TICKET BRICO 71.07")
    deposer(drive, "bouygues.pdf", b"FACTURE BYG 44.99")
    passage(src, man, "1er passage (3 pièces déposées)")
    man.sauver()

    print("-" * 60)
    passage(src, man, "2e passage (rien de neuf)")

    print("-" * 60)
    deposer(drive, "syndic.pdf", b"APPEL CHARGES SYNDIC 210.00")     # vraiment nouvelle
    shutil.copy(os.path.join(drive, "edf.pdf"),
                os.path.join(drive, "EDF_copie_renommee.pdf"))       # renommé, même contenu
    passage(src, man, "3e passage (+1 nouvelle, +1 renommée)")
    man.sauver()

    print("=" * 60)
    print("Manifeste : %d pièces traitées, mémorisées d'une période à l'autre." % len(man))
    print("Conséquence budget : sur 200 factures, seules les NEUVES sont OCR — "
          "on ne re-paye jamais une pièce déjà lue.")
