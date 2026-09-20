#!/usr/bin/env python3
"""Tests des referentiels du build : territoire, courant, classe, reseau.

Les points de controle geographiques sont des lieux verifiables, pas des
coordonnees inventees. Les cas de classe de puissance reprennent les valeurs
qui ont motive l'ADR 06 : 22,00 et 22,08 kW sont du courant alternatif a plus
de 98 %, 24 et 25 kW sont du continu a plus de 80 %, et un decoupage par
puissance seule les rangerait tous du mauvais cote.

Lancement : python tests/test_referentiels.py
"""
from __future__ import annotations

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

echecs: list[str] = []


def verifier(nom: str, condition: bool, detail: str = "") -> None:
    if not condition:
        echecs.append(f"{nom}{' : ' + detail if detail else ''}")


def tester_territoire(m) -> None:
    reperes = [
        ("Paris, place de la Concorde", 2.3212, 48.8656, "75"),
        ("Marseille, gare Saint-Charles", 5.3805, 43.3028, "13"),
        ("Ajaccio", 8.7369, 41.9192, "2A"),
        ("Bastia", 9.4509, 42.7003, "2B"),
        ("Lille", 3.0573, 50.6292, "59"),
        ("Saint-Denis de La Reunion", 55.4504, -20.8823, "974"),
        ("Pointe-a-Pitre", -61.5314, 16.2411, "971"),
        ("Fort-de-France", -61.0742, 14.6161, "972"),
        ("Cayenne", -52.3333, 4.9333, "973"),
        ("Mamoudzou", 45.2280, -12.7806, "976"),
    ]
    for nom, lon, lat, attendu in reperes:
        obtenu = m.departement(lon, lat)
        verifier(f"departement de {nom}", obtenu == attendu,
                 f"attendu {attendu}, obtenu {obtenu}")

    hors = [("plein Atlantique", -20.0, 45.0), ("Madrid", -3.7038, 40.4168),
            ("Noumea", 166.4572, -22.2758), ("Papeete", -149.5665, -17.5516),
            # un plan d'eau enclave n'appartient a aucun contour terrestre :
            # 195 des 378 points non rattaches sont dans ce cas
            ("Marseille, plan d'eau du Vieux-Port", 5.3698, 43.2951)]
    for nom, lon, lat in hors:
        verifier(f"hors nomenclature departementale : {nom}",
                 m.departement(lon, lat) is None,
                 f"obtenu {m.departement(lon, lat)}")

    verifier("coordonnees absentes", m.departement(None, None) is None)
    verifier("longitude absente", m.departement(None, 48.85) is None)

    # version groupee : meme resultat, un seul test par couple distinct
    points = [(2.3212, 48.8656), (2.3212, 48.8656), (5.3805, 43.3028), (None, None)]
    verifier("rattachement groupe",
             m.departements_par_points(points) == ["75", "75", "13", None],
             f"obtenu {m.departements_par_points(points)}")

    # controle par le code INSEE
    for code, attendu in [("75056", "75"), ("2A004", "2A"), ("97411", "974"),
                          ("", None), (None, None), ("99999", None), ("ABCDE", None)]:
        verifier(f"departement INSEE de {code!r}", m.departement_insee(code) == attendu,
                 f"attendu {attendu}, obtenu {m.departement_insee(code)}")


def tester_courant_et_classe(m) -> None:
    for ccs, chad, t2, ef, attendu in [
        ("false", "false", "true", "false", "AC"),
        ("false", "false", "false", "true", "AC"),
        ("true", "false", "false", "false", "DC"),
        ("false", "true", "false", "false", "DC"),
        ("true", "false", "true", "false", "DC"),      # mixte : le continu prime
        ("false", "false", "false", "false", "indetermine"),
        ("TRUE", "false", "false", "false", "DC"),     # graphies rencontrees
        ("1", "0", "0", "0", "DC"),
    ]:
        obtenu = m.courant(ccs, chad, t2, ef)
        verifier(f"courant({ccs},{chad},{t2},{ef})", obtenu == attendu,
                 f"attendu {attendu}, obtenu {obtenu}")

    cas = [
        ("AC", 3.7, "AC <= 7 kW"), ("AC", 7.0, "AC <= 7 kW"),
        ("AC", 7.4, "AC 7 a 22,9 kW"),
        ("AC", 22.0, "AC 7 a 22,9 kW"),      # 63 507 PDC, dont 1,4 % de prises DC
        ("AC", 22.08, "AC 7 a 22,9 kW"),     # 14 649 PDC, aucune prise DC
        ("AC", 22.8, "AC 7 a 22,9 kW"),
        ("AC", 43.0, "AC > 22,9 kW"),
        ("DC", 24.0, "DC < 50 kW"),          # 2 862 PDC, 80,9 % de prises DC
        ("DC", 25.0, "DC < 50 kW"),
        ("DC", 50.0, "DC 50 a 150 kW"),
        ("DC", 149.9, "DC 50 a 150 kW"),
        ("DC", 150.0, "DC >= 150 kW"),
        ("DC", 400.0, "DC >= 150 kW"),
        ("AC", 0.0, "non classable"),
        ("AC", None, "non classable"),
        ("indetermine", 50.0, "non classable"),
        ("AC", -5.0, "non classable"),
    ]
    for c, p, attendu in cas:
        obtenu = m.classe_puissance(c, p)
        verifier(f"classe({c}, {p})", obtenu == attendu,
                 f"attendu {attendu}, obtenu {obtenu}")

    verifier("toutes les classes produites sont declarees",
             all(m.classe_puissance(c, p) in m.CLASSES for c, p, _ in cas))


def tester_reseau(m) -> None:
    for identifiant, attendu in [
        ("FRS37E12345", "FRS37"), ("frs37e12345", "FRS37"),
        (" FRFR1P998 ", "FRFR1"), ("ESDRVEAGNW1", "ESDRV"),
        ("", None), (None, None), ("FR", None), ("1234567", None),
    ]:
        obtenu = m.prefixe_emi3(identifiant)
        verifier(f"prefixe de {identifiant!r}", obtenu == attendu,
                 f"attendu {attendu}, obtenu {obtenu}")

    prefixes = ["FRAAA", "FRAAA", "FRAAA", "FRBBB", "FRBBB", None, "FRCCC"]
    operateurs = ["Reseau A", "Reseau A", "reseau a", "Reseau B", "", "X", ""]
    noms = m.noms_par_prefixe(prefixes, operateurs)
    verifier("libelle majoritaire retenu", noms.get("FRAAA") == "Reseau A",
             f"obtenu {noms.get('FRAAA')}")
    verifier("libelle unique non vide retenu", noms.get("FRBBB") == "Reseau B")
    verifier("sans libelle, le prefixe fait office de nom",
             noms.get("FRCCC") == "FRCCC")
    verifier("prefixe absent ignore", None not in noms)

    # a egalite d'effectif, le nom est choisi de facon deterministe
    a = m.noms_par_prefixe(["FRXXX", "FRXXX"], ["Beta", "Alpha"])
    b = m.noms_par_prefixe(["FRXXX", "FRXXX"], ["Alpha", "Beta"])
    verifier("egalite tranchee de facon deterministe", a == b, f"{a} contre {b}")

    # le marqueur d'itinerance suffixe au nom d'operateur est une annotation
    # technique, pas une partie du nom
    for entree, attendu in [("Freshmile | FR*FR1", "Freshmile"),
                            ("E.Leclerc | FR*LE2", "E.Leclerc"),
                            ("WAAT SAS | FR*WA2", "WAAT SAS"),
                            ("Road | FR*EFL", "Road"),
                            ("Izivia", "Izivia")]:
        obtenu = m.noms_par_prefixe(["FRZZZ"], [entree]).get("FRZZZ")
        verifier(f"marqueur retire de {entree!r}", obtenu == attendu,
                 f"attendu {attendu!r}, obtenu {obtenu!r}")


def tester_enseignes_yml(m) -> None:
    """Le fichier de noms doit etre lisible, non contradictoire et justifie."""
    table = m._fusions()
    verifier("enseignes.yml n'est pas vide", len(table) > 0,
             "la verification prefixe par prefixe doit s'y retrouver")

    texte = m.FUSIONS.read_text(encoding="utf-8")
    lignes = [l for l in texte.splitlines()
              if l.strip().startswith("-") and not l.strip().startswith("- #")]
    sans_justification = [l.strip() for l in lignes if "#" not in l]
    verifier("chaque ligne de prefixes porte sa justification",
             not sans_justification,
             f"lignes sans commentaire : {sans_justification[:3]}")

    verifier("aucun prefixe nomme deux fois",
             len(table) == len({p for p in table}),
             "un prefixe ne peut appartenir qu'a un reseau")

    for prefixe in table:
        verifier(f"prefixe {prefixe} bien forme",
                 m.prefixe_emi3(prefixe + "E1") == prefixe,
                 f"{prefixe} n'est pas un prefixe eMI3 valide")

    # quelques decisions structurantes, qui ne doivent pas se perdre
    for prefixe, attendu in [("FRQPK", "QPARK"), ("FRH01", "Pass pass électrique"),
                             ("FRV75", "Belib'"), ("FREBN", "eborn"),
                             ("FRHPC", "TotalEnergies"), ("FRTCB", "TotalEnergies")]:
        verifier(f"{prefixe} nomme {attendu}", table.get(prefixe) == attendu,
                 f"obtenu {table.get(prefixe)!r}")

    # Belib' est exploite par TotalEnergies mais reste un reseau distinct
    verifier("un reseau tiers n'est pas absorbe par son exploitant",
             table.get("FRV75") != table.get("FRHPC"))

    # une surcharge prime sur le libelle majoritaire
    noms = m.noms_par_prefixe(["FRQPK", "FRQPK"], ["IZIVIA", "IZIVIA"])
    verifier("la surcharge prime sur l'operateur majoritaire",
             noms.get("FRQPK") == "QPARK", f"obtenu {noms.get('FRQPK')!r}")


def main() -> int:
    try:
        from build import referentiels as m
    except ImportError as exc:
        print(f"MODULE ABSENT : {exc}", file=sys.stderr)
        return 2
    tester_territoire(m)
    tester_courant_et_classe(m)
    tester_reseau(m)
    tester_enseignes_yml(m)
    if echecs:
        print(f"ECHEC : {len(echecs)} verification(s)", file=sys.stderr)
        for e in echecs:
            print(f"  {e}", file=sys.stderr)
        return 1
    print("OK : territoire, courant, classe de puissance et reseau verifies")
    return 0


if __name__ == "__main__":
    sys.exit(main())
