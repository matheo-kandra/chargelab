#!/usr/bin/env python3
"""Referentiels du build : territoire, courant et classe de puissance, reseau.

Trois rattachements, tous decides dans docs/decisions.md :

  ADR 04  le departement vient des coordonnees, par test point dans polygone.
          Le code INSEE, vide pour 26,6 % du parc, ne sert que de controle.
  ADR 06  le courant se deduit des types de prise, jamais de la puissance :
          un decoupage par puissance seule rangerait 78 156 points en
          courant alternatif dans une classe intitulee « DC 22 a 50 ».
  ADR 07  la cle de reseau est le prefixe eMI3, pas `nom_enseigne`, qui
          compte 6 289 graphies pour 281 prefixes et sert souvent de nom de
          site plutot que de nom de reseau.

Aucune de ces fonctions ne corrige une donnee : ce qui n'est pas rattachable
ressort comme tel et sera compte.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
CONTOURS = RACINE / "data" / "raw" / "departements-avec-outre-mer.geojson"
FUSIONS = RACINE / "build" / "enseignes.yml"

RE_INSEE = re.compile(r"^([013-9]\d|2[AB1-9])\d{3}$")
RE_PREFIXE = re.compile(r"^([A-Z]{2}[A-Z0-9]{3})")

CLASSES = ("AC <= 7 kW", "AC 7 a 22,9 kW", "AC > 22,9 kW",
           "DC < 50 kW", "DC 50 a 150 kW", "DC >= 150 kW", "non classable")


# --- territoire ------------------------------------------------------------

@lru_cache(maxsize=1)
def _index_departements():
    from shapely.geometry import shape
    from shapely.strtree import STRtree
    g = json.loads(CONTOURS.read_text(encoding="utf-8"))
    geoms = [shape(f["geometry"]) for f in g["features"]]
    codes = [f["properties"]["code"] for f in g["features"]]
    return STRtree(geoms), geoms, codes


def departement(lon: float | None, lat: float | None) -> str | None:
    """Departement contenant le point, ou None. Ne devine jamais le plus proche."""
    if lon is None or lat is None:
        return None
    from shapely.geometry import Point
    arbre, geoms, codes = _index_departements()
    p = Point(lon, lat)
    for i in arbre.query(p):
        if geoms[i].contains(p):
            return codes[i]
    return None


def departements_par_points(points) -> list[str | None]:
    """Version groupee : un seul test par couple de coordonnees distinct.

    Le parc compte 168 674 lignes pour 38 740 couples distincts ; faire le test
    ligne par ligne coute quatre fois le necessaire.
    """
    cache: dict[tuple, str | None] = {}
    out = []
    for lon, lat in points:
        cle = (lon, lat)
        if cle not in cache:
            cache[cle] = departement(lon, lat)
        out.append(cache[cle])
    return out


def departement_insee(code: str | None) -> str | None:
    """Departement lu dans le code commune, pour le controle croise.

    Le pseudo-code 99 designe l'etranger dans la nomenclature INSEE et porte
    104 points de charge au 17/09/2026. Ce n'est pas un departement : il rend
    None, comme n'importe quel code illisible, et sera compte a part.
    """
    if not code or not RE_INSEE.match(code.strip()):
        return None
    c = code.strip()
    if c.startswith("99"):
        return None
    return c[:3] if c.startswith("97") else c[:2]


# --- courant et classe de puissance ---------------------------------------

def courant(combo_ccs: str, chademo: str, type_2: str, type_ef: str) -> str:
    """AC, DC ou indetermine, deduit des seuls types de prise (ADR 06)."""
    vrai = {"true", "True", "TRUE", "1"}
    dc = combo_ccs in vrai or chademo in vrai
    ac = type_2 in vrai or type_ef in vrai
    if dc:
        return "DC"
    if ac:
        return "AC"
    return "indetermine"


def classe_puissance(courant_deduit: str, puissance: float | None) -> str:
    """Classe de l'ADR 06 : le courant d'abord, la puissance ensuite."""
    if puissance is None or puissance <= 0:
        return "non classable"
    if courant_deduit == "AC":
        if puissance <= 7:
            return "AC <= 7 kW"
        if puissance <= 22.9:
            return "AC 7 a 22,9 kW"
        return "AC > 22,9 kW"
    if courant_deduit == "DC":
        if puissance < 50:
            return "DC < 50 kW"
        if puissance < 150:
            return "DC 50 a 150 kW"
        return "DC >= 150 kW"
    return "non classable"


# --- reseau ----------------------------------------------------------------

def prefixe_emi3(id_pdc: str | None) -> str | None:
    """Les cinq premiers caracteres de l'identifiant d'itinerance."""
    if not id_pdc:
        return None
    m = RE_PREFIXE.match(id_pdc.strip().upper())
    return m.group(1) if m else None


@lru_cache(maxsize=1)
def _fusions() -> dict[str, str]:
    """Regroupements explicites de prefixes, lus dans build/enseignes.yml.

    Le fichier ne contient que des decisions prises a la main et justifiees :
    aucune regle automatique ne rapproche deux prefixes.
    """
    if not FUSIONS.exists():
        return {}
    table: dict[str, str] = {}
    nom = None
    for ligne in FUSIONS.read_text(encoding="utf-8").splitlines():
        ligne = ligne.split("#")[0].rstrip()
        if not ligne.strip():
            continue
        if not ligne.startswith((" ", "\t", "-")):
            nom = ligne.rstrip(":").strip()
        elif nom:
            for p in ligne.strip().lstrip("-").split(","):
                p = p.strip()
                if p:
                    table[p] = nom
    return table


def noms_par_prefixe(prefixes, operateurs) -> dict[str, str]:
    """Nom affiche de chaque prefixe : l'operateur majoritaire, sauf fusion.

    Le libelle majoritaire couvre 94,37 % des points de son prefixe ; le reste
    est du bruit de saisie que le prefixe absorbe deja.
    """
    par_prefixe: dict[str, Counter] = {}
    for p, op in zip(prefixes, operateurs):
        if not p:
            continue
        par_prefixe.setdefault(p, Counter())[(op or "").strip()] += 1
    fusions = _fusions()
    sortie = {}
    for p, compte in par_prefixe.items():
        if p in fusions:
            sortie[p] = fusions[p]
            continue
        candidats = [(n, k) for n, k in compte.items() if n]
        sortie[p] = max(candidats, key=lambda x: (x[1], x[0]))[0] if candidats else p
    return sortie
