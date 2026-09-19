#!/usr/bin/env python3
"""Cadence du flux dynamique mesuree sur notre propre collecte, sur 24 h.

Fenetre : du 2026-09-17 20:23 UTC au 2026-09-18 23:24 UTC, pas de 5 minutes.
Pour chaque couple de captures consecutives on mesure la part de PDC dont
l'horodatage operateur a avance et la part dont l'etat ou l'occupation a change.
Les creneaux manques (panne reseau locale) sont comptes, jamais reconstruits.
Sortie : data/profiling/cadence-propre-24h.csv, une ligne par intervalle.
"""
import csv
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "dynamique"
OUT = ROOT / "data" / "profiling" / "cadence-propre-24h.csv"
COLS = ["id_pdc_itinerance", "etat_pdc", "occupation_pdc", "horodatage"]


def charger(p: Path) -> pd.DataFrame:
    df = pd.read_csv(p, dtype=str, keep_default_na=False, usecols=COLS)
    df["_h"] = pd.to_datetime(df["horodatage"], errors="coerce", utc=True, format="mixed")
    df = df.sort_values("_h").drop_duplicates("id_pdc_itinerance", keep="last")
    return df.set_index("id_pdc_itinerance")


fichiers = sorted(RAW.glob("*/*.csv.gz"))
print(f"{len(fichiers)} captures archivees")
lignes = []
prec = None
for f in fichiers:
    t = datetime.strptime(f.parent.name + f.stem[:6], "%Y-%m-%d%H%M%S").replace(tzinfo=timezone.utc)
    cur = charger(f)
    if prec is not None:
        t0, a = prec
        dt = (t - t0).total_seconds() / 60
        com = a.index.intersection(cur.index)
        n = len(com)
        av = int((cur.loc[com, "_h"] > a.loc[com, "_h"]).sum())
        chg = int(((cur.loc[com, "etat_pdc"] != a.loc[com, "etat_pdc"]) |
                   (cur.loc[com, "occupation_pdc"] != a.loc[com, "occupation_pdc"])).sum())
        lignes.append({
            "debut_utc": t0.isoformat(), "fin_utc": t.isoformat(),
            "dt_min": round(dt, 2), "pdc_communs": n,
            "horodatage_avance": av, "pct_horodatage_avance": round(100 * av / n, 4),
            "etat_ou_occupation_change": chg, "pct_change": round(100 * chg / n, 4),
            "entrees": len(cur.index.difference(a.index)),
            "sorties": len(a.index.difference(cur.index)),
            "pdc_flux": len(cur),
        })
    prec = (t, cur)

OUT.parent.mkdir(parents=True, exist_ok=True)
with OUT.open("w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(lignes[0].keys()))
    w.writeheader()
    w.writerows(lignes)

d = pd.DataFrame(lignes)
d["debut"] = pd.to_datetime(d["debut_utc"])
reg = d[(d["dt_min"] > 4.5) & (d["dt_min"] < 5.5)]
print(f"\nintervalles : {len(d)} au total, dont {len(reg)} de 5 minutes pleines")
print(f"creneaux de 5 min manques (panne reseau locale) : "
      f"{int(((d["dt_min"] - 5) / 5).round().clip(lower=0).sum())}")
print(f"\nsur les intervalles de 5 minutes :")
print(f"  horodatage avance : mediane {reg["pct_horodatage_avance"].median():.2f} %, "
      f"p10 {reg["pct_horodatage_avance"].quantile(.1):.2f} %, p90 {reg["pct_horodatage_avance"].quantile(.9):.2f} %")
print(f"  etat ou occupation change : mediane {reg["pct_change"].median():.2f} %, "
      f"p10 {reg["pct_change"].quantile(.1):.2f} %, p90 {reg["pct_change"].quantile(.9):.2f} %")
print(f"  soit, ramene a 10 minutes : {2*reg["pct_change"].median():.2f} % du parc du flux")
print(f"\ntaille du parc present dans le flux : min {d["pdc_flux"].min()}, "
      f"median {int(d["pdc_flux"].median())}, max {d["pdc_flux"].max()}")
print(f"entrees par intervalle : median {int(d["entrees"].median())}, max {d["entrees"].max()}")
print(f"sorties par intervalle : median {int(d["sorties"].median())}, max {d["sorties"].max()}")

print("\nprofil horaire UTC (mediane du % de changement, intervalles de 5 min) :")
reg = reg.assign(h=reg["debut"].dt.strftime("%H"))
g = reg.groupby("h")["pct_change"].agg(["median", "size"])
for h, r in g.iterrows():
    print(f"   {h}h : {r['median']:5.2f} %   ({int(r['size'])} intervalles)")
