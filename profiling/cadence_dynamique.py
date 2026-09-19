#!/usr/bin/env python3
"""Mesure de la cadence de rafraichissement reelle du flux IRVE dynamique.

Pour chaque couple de captures consecutives on mesure :
  - la part de PDC dont l'horodatage operateur a avance,
  - la part de PDC dont l'etat ou l'occupation a change,
  - la composition du parc present dans le flux (entrees / sorties).
On en deduit le pas de temps utile : en dessous, on paie du telechargement
pour une information qui n'a pas bouge.
"""
import gzip
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
COLS = ["id_pdc_itinerance", "etat_pdc", "occupation_pdc", "horodatage"]


def charger(p: Path) -> pd.DataFrame:
    df = pd.read_csv(p, dtype=str, keep_default_na=False, usecols=COLS)
    df["_h"] = pd.to_datetime(df["horodatage"], errors="coerce", utc=True, format="mixed")
    df = df.sort_values("_h").drop_duplicates("id_pdc_itinerance", keep="last")
    return df.set_index("id_pdc_itinerance")


def main():
    jour = sys.argv[1] if len(sys.argv) > 1 else "2026-09-17"
    fichiers = sorted((ROOT / "data" / "raw" / "dynamique" / jour).glob("*.csv.gz"))
    if len(fichiers) < 2:
        print("moins de deux captures, rien a comparer")
        return
    print(f"{len(fichiers)} captures, de {fichiers[0].stem} a {fichiers[-1].stem} (UTC)\n")
    print(f"{'de':>8s} {'a':>8s} {'dt_min':>7s} {'PDC':>7s} {'horod.+':>8s} {'%':>6s} "
          f"{'etat/occ chg':>12s} {'%':>6s} {'entrees':>8s} {'sorties':>8s}")
    prec = None
    lignes = []
    for f in fichiers:
        cur = charger(f)
        if prec is not None:
            t0 = pd.Timestamp(f"{jour}T{prec[0][:2]}:{prec[0][2:4]}:{prec[0][4:6]}Z")
            t1 = pd.Timestamp(f"{jour}T{f.stem[:2]}:{f.stem[2:4]}:{f.stem[4:6]}Z")
            dt = (t1 - t0).total_seconds() / 60
            a, b = prec[1], cur
            com = a.index.intersection(b.index)
            av = (b.loc[com, "_h"] > a.loc[com, "_h"]).sum()
            chg = ((b.loc[com, "etat_pdc"] != a.loc[com, "etat_pdc"]) |
                   (b.loc[com, "occupation_pdc"] != a.loc[com, "occupation_pdc"])).sum()
            n = len(com)
            print(f"{prec[0]:>8s} {f.stem:>8s} {dt:7.1f} {n:7d} {av:8d} {100*av/n:5.2f}% "
                  f"{chg:12d} {100*chg/n:5.2f}% {len(b.index.difference(a.index)):8d} "
                  f"{len(a.index.difference(b.index)):8d}")
            lignes.append((dt, 100 * av / n, 100 * chg / n))
        prec = (f.stem, cur)
    if lignes:
        d = pd.DataFrame(lignes, columns=["dt_min", "pct_horodatage_avance", "pct_etat_change"])
        print("\nmedianes sur %d intervalles : dt=%.1f min, horodatage avance=%.2f %%, etat change=%.2f %%"
              % (len(d), d.dt_min.median(), d.pct_horodatage_avance.median(), d.pct_etat_change.median()))


if __name__ == "__main__":
    main()
