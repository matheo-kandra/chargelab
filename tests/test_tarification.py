#!/usr/bin/env python3
"""Tests du parseur de `tarification`, ecrits AVANT l'implementation.

Ce fichier definit le contrat que le parseur devra respecter. Il est cense
echouer tant que build/parser_tarification.py n'existe pas : c'est l'etat
normal au moment ou il est ecrit.

Contrat attendu :

    from build.parser_tarification import analyser
    r = analyser("0,29€ / kWh")
    r.code               -> "KWH"
    r.prix_kwh           -> 0.29        (euros TTC par kWh, None si absent)
    r.prix_kwh_ac        -> None        (rempli seulement si AC et DC sont
    r.prix_kwh_dc        -> None         distingues dans la meme chaine)
    r.prix_min           -> None        (euros TTC par minute de charge)
    r.prix_heure_charge  -> None        (euros TTC par heure de charge)
    r.prix_session       -> None        (euros TTC, forfait par session)
    r.prix_occupation_h  -> None        (euros TTC par heure d'occupation hors
                                         charge ; releve, sans effet sur le code)
    r.ht_converti        -> False       (True si la source declarait HT et que
                                         la valeur a ete portee a TTC)
    r.motif              -> ""          (obligatoire quand le code est INCONNU)

Codes possibles : KWH, MIN, SESSION, MIXTE, GRATUIT, RENVOI, VIDE, INCONNU.

Deux controles, tous deux bloquants pour le build :

  1. chaque cas de tests/tarification_cases.csv doit etre rendu exactement ;
  2. toute valeur de l'inventaire pesant plus de 0,5 % des points de charge
     tarifes et absente des cas fait echouer le test, avec la liste. Le seuil
     porte sur les lignes tarifees, pas sur le parc entier : c'est la lecture
     stricte du 4.1.4 de la spec.

Lancement : python tests/test_tarification.py
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

CAS_CSV = RACINE / "tests" / "tarification_cases.csv"
INVENTAIRE = RACINE / "docs" / "tarification-valeurs.csv"
TOLERANCE = 1e-6
SEUIL_COUVERTURE = 0.005  # 0,5 % des points de charge tarifes

CHAMPS_NUM = [
    ("prix_kwh", "prix_kwh"), ("prix_kwh_ac", "prix_kwh_ac"),
    ("prix_kwh_dc", "prix_kwh_dc"), ("prix_min", "prix_min"),
    ("prix_heure_charge", "prix_heure_charge"), ("prix_session", "prix_session"),
    ("prix_occupation_h", "prix_occupation_h"),
]


def lire_cas() -> list[dict]:
    with CAS_CSV.open(encoding="utf-8") as fh:
        return list(csv.DictReader(l for l in fh if not l.startswith("#")))


def nombre(s: str):
    return None if s == "" else float(s)


def proche(attendu, obtenu) -> bool:
    if attendu is None:
        return obtenu is None
    if obtenu is None:
        return False
    return abs(attendu - obtenu) <= TOLERANCE


def controler_couverture(cas: list[dict]) -> list[str]:
    lignes = [r for r in csv.DictReader(INVENTAIRE.open(encoding="utf-8"))
              if r["valeur_brute"] != ""]
    total = sum(int(r["nb_pdc_dedoublonne"]) for r in lignes)
    seuil = SEUIL_COUVERTURE * total
    couverts = {r["valeur_brute"] for r in cas}
    manquants = []
    for r in lignes:
        n = int(r["nb_pdc_dedoublonne"])
        if n > seuil and r["valeur_brute"] not in couverts:
            manquants.append(f"{n} PDC ({100*n/total:.2f} %) : "
                             f"{r['valeur_brute'][:120]!r}")
    return manquants


def main() -> int:
    cas = lire_cas()
    print(f"{len(cas)} cas reels charges depuis {CAS_CSV.relative_to(RACINE)}")

    manquants = controler_couverture(cas)
    if manquants:
        print(f"\nECHEC : {len(manquants)} valeur(s) au-dela de "
              f"{100*SEUIL_COUVERTURE} % des lignes tarifees ne sont pas couvertes :",
              file=sys.stderr)
        for m in manquants:
            print(f"  {m}", file=sys.stderr)
        return 1
    print(f"couverture : aucune valeur au-dela de {100*SEUIL_COUVERTURE} % "
          f"des lignes tarifees n'est laissee de cote")

    try:
        from build.parser_tarification import analyser
    except ImportError as exc:
        print(f"\nPARSEUR ABSENT : {exc}", file=sys.stderr)
        print("Les cas sont prets, l'implementation ne l'est pas. "
              "C'est l'etat attendu tant que build/parser_tarification.py "
              "n'a pas ete ecrit.", file=sys.stderr)
        return 2

    echecs = []
    for r in cas:
        obtenu = analyser(r["valeur_brute"])
        ecarts = []
        if obtenu.code != r["code_attendu"]:
            ecarts.append(f"code attendu {r['code_attendu']}, obtenu {obtenu.code}")
        for col, attr in CHAMPS_NUM:
            a, o = nombre(r[col]), getattr(obtenu, attr, None)
            if not proche(a, o):
                ecarts.append(f"{col} attendu {a}, obtenu {o}")
        ht_attendu = r["ht_converti"] == "oui"
        if bool(getattr(obtenu, "ht_converti", False)) != ht_attendu:
            ecarts.append(f"ht_converti attendu {ht_attendu}, "
                          f"obtenu {getattr(obtenu, 'ht_converti', None)}")
        if r["code_attendu"] == "INCONNU" and not getattr(obtenu, "motif", ""):
            ecarts.append("motif obligatoire et absent pour un code INCONNU")
        if ecarts:
            echecs.append((r, ecarts))

    if echecs:
        print(f"\nECHEC : {len(echecs)} cas sur {len(cas)}", file=sys.stderr)
        for r, ecarts in echecs[:40]:
            print(f"\n  rang {r['rang']} ({r['nb_pdc']} PDC) : "
                  f"{r['valeur_brute'][:100]!r}", file=sys.stderr)
            for e in ecarts:
                print(f"      {e}", file=sys.stderr)
        if len(echecs) > 40:
            print(f"\n  ... et {len(echecs)-40} autres", file=sys.stderr)
        return 1

    print(f"OK : {len(cas)} cas rendus exactement")
    return 0


if __name__ == "__main__":
    sys.exit(main())
