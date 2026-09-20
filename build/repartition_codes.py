#!/usr/bin/env python3
"""Repartition des codes de parsing sur le parc entier.

Cette sortie precede tout calcul de prix : la spec interdit d'afficher une
mediane avant d'avoir montre ce que le parseur sait lire et ce qu'il ecarte.
Elle est ecrite dans data/profiling/tarification-codes-reels.txt.
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import pandas as pd

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
from build.parser_tarification import analyser  # noqa: E402

FICHIER = RACINE / "data" / "raw" / "statique" / "pan_dedoublonne_2026-09-19.csv"


def classe_puissance(p, ccs, chademo, t2, ef) -> str:
    dc = ccs == "true" or chademo == "true"
    ac = t2 == "true" or ef == "true"
    if pd.isna(p) or p <= 0:
        return "non classable"
    if dc:
        return "DC < 50 kW" if p < 50 else ("DC 50 a 150 kW" if p < 150 else "DC >= 150 kW")
    if ac:
        return "AC <= 7 kW" if p <= 7 else ("AC 7 a 22,9 kW" if p <= 22.9 else "AC > 22,9 kW")
    return "non classable"


def main() -> int:
    cols = ["id_pdc_itinerance", "tarification", "puissance_nominale",
            "prise_type_combo_ccs", "prise_type_chademo", "prise_type_2", "prise_type_ef"]
    df = pd.read_csv(FICHIER, dtype=str, keep_default_na=False, usecols=cols, low_memory=False)
    n = len(df)

    # une seule analyse par valeur distincte, puis report
    distinctes = df["tarification"].unique()
    table = {v: analyser(v) for v in distinctes}
    res = df["tarification"].map(table)

    codes = Counter(r.code for r in res)
    print(f"Parc analyse : {n} lignes, {len(distinctes)} valeurs distinctes de tarification\n")
    print(f"{'code':10s} {'PDC':>8s} {'% parc':>8s}")
    for c, k in codes.most_common():
        print(f"{c:10s} {k:8d} {100*k/n:7.2f}%")

    kwh = pd.Series([r.prix_kwh for r in res], index=df.index, dtype="float64")
    ac = pd.Series([r.prix_kwh_ac for r in res], index=df.index, dtype="float64")
    dc = pd.Series([r.prix_kwh_dc for r in res], index=df.index, dtype="float64")
    porteur = kwh.notna() | ac.notna() | dc.notna()
    print(f"\nPDC porteurs d'un prix a l'energie : {int(porteur.sum())} "
          f"({100*porteur.mean():.2f} % du parc)")
    print(f"dont prix HT convertis en TTC : {sum(1 for r in res if r.ht_converti)}")
    print(f"dont tarifs AC et DC distingues : {int((ac.notna() | dc.notna()).sum())}")

    p = pd.to_numeric(df["puissance_nominale"].str.replace(",", ".", regex=False), errors="coerce")
    cl = [classe_puissance(a, b, c, d, e) for a, b, c, d, e in
          zip(p, df["prise_type_combo_ccs"], df["prise_type_chademo"],
              df["prise_type_2"], df["prise_type_ef"])]
    t = pd.DataFrame({"classe": cl, "porteur": porteur})
    g = t.groupby("classe")["porteur"].agg(["size", "sum"])
    g.columns = ["parc", "porteurs"]
    g["couverture_%"] = (100 * g["porteurs"] / g["parc"]).round(2)
    g["seuil_30_atteint"] = g["porteurs"] >= 30
    print("\nEffectifs porteurs d'un prix, par classe de puissance (ADR 06) :")
    print(g.sort_values("parc", ascending=False).to_string())
    print("\nAucune mediane n'est calculee ici : ce fichier ne montre que ce que "
          "le parseur sait lire.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
