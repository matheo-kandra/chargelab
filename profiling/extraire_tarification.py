#!/usr/bin/env python3
"""Inventaire exhaustif des valeurs du champ `tarification`.

Produit docs/tarification-valeurs.csv : une ligne par valeur brute distincte,
avec le nombre de points de charge et de stations concernes dans le fichier
statique dedoublonne, et le rappel du compte dans le fichier non dedoublonne.
Aucune normalisation n'est appliquee ici : c'est le texte brut, tel quel.
"""
import csv
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATE = "2026-09-17"
DEDUP = ROOT / "data" / "raw" / "statique" / f"pan_dedoublonne_{DATE}.csv"
BRUT = ROOT / "data" / "raw" / "statique" / f"pan_avec_doublons_{DATE}.csv"
OUT = ROOT / "docs" / "tarification-valeurs.csv"

cols = ["tarification", "id_pdc_itinerance", "id_station_itinerance", "puissance_nominale", "nom_enseigne"]
d = pd.read_csv(DEDUP, dtype=str, keep_default_na=False, usecols=cols, low_memory=False)
b = pd.read_csv(BRUT, dtype=str, keep_default_na=False, usecols=["tarification"], low_memory=False)

n_pdc = len(d)
pdc_par_valeur = Counter(d["tarification"])
sta_par_valeur = d.groupby("tarification")["id_station_itinerance"].nunique().to_dict()
ens_par_valeur = d.groupby("tarification")["nom_enseigne"].nunique().to_dict()
brut_par_valeur = Counter(b["tarification"])

OUT.parent.mkdir(parents=True, exist_ok=True)
with OUT.open("w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["valeur_brute", "nb_pdc_dedoublonne", "part_pdc_pct", "nb_stations",
                "nb_enseignes", "nb_pdc_non_dedoublonne", "longueur"])
    for val, n in pdc_par_valeur.most_common():
        w.writerow([val, n, round(100 * n / n_pdc, 4), sta_par_valeur.get(val, 0),
                    ens_par_valeur.get(val, 0), brut_par_valeur.get(val, 0), len(val)])

vides = pdc_par_valeur.get("", 0)
print(f"lignes PDC (dedoublonne)      : {n_pdc}")
print(f"tarification vide             : {vides} ({100*vides/n_pdc:.2f} %)")
print(f"tarification renseignee       : {n_pdc-vides} ({100*(n_pdc-vides)/n_pdc:.2f} %)")
print(f"valeurs distinctes non vides  : {len(pdc_par_valeur)-1}")
print(f"ecrit                         : {OUT}")
