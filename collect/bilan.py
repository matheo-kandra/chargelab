#!/usr/bin/env python3
"""Bilan de la collecte : couverture reelle, cadence obtenue, creneaux manques.

C'est la preuve demandee par la spec au §9.3 : « au moins 48 h de captures
reelles archivees avant de construire l'UI ». Le bilan se lit dans les journaux,
il ne suppose rien de la cadence planifiee.

Usage : python collect/bilan.py [depuis_iso]
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone

import pandas as pd

from commun import COLLECTE, JOURNAUX


def attendu(t: datetime) -> int:
    """Pas planifie en minutes a l'heure t (ADR 08)."""
    return 5 if 6 <= t.hour < 20 else 15


def main() -> int:
    j = JOURNAUX / "dynamique.csv"
    if not j.exists():
        print("aucun journal dynamique")
        return 1
    d = pd.read_csv(j, dtype=str, keep_default_na=False)
    d["t"] = pd.to_datetime(d["capture_utc"], utc=True, format="mixed")
    if len(sys.argv) > 1:
        d = d[d["t"] >= pd.Timestamp(sys.argv[1])]
    d = d.sort_values("t").reset_index(drop=True)
    if d.empty:
        print("aucun passage dans la fenetre demandee")
        return 1

    debut, fin = d["t"].iloc[0], d["t"].iloc[-1]
    duree = (fin - debut).total_seconds() / 3600
    ok = d[d["resultat"].str.startswith("ok")]
    echecs = d[d["resultat"] == "echec"]

    print("=" * 72)
    print(f"Fenetre        : {debut:%Y-%m-%d %H:%M} -> {fin:%Y-%m-%d %H:%M} UTC ({duree:.1f} h)")
    print(f"Passages       : {len(d)} au total, {len(ok)} reussis, {len(echecs)} en echec "
          f"({100*len(echecs)/len(d):.1f} %)")

    # creneaux attendus sur la fenetre, minute par minute
    n_attendus = 0
    t = debut.to_pydatetime().replace(second=0, microsecond=0, tzinfo=timezone.utc)
    while t <= fin.to_pydatetime():
        pas = attendu(t)
        if t.minute % pas == 0:
            n_attendus += 1
        t += timedelta(minutes=1)
    print(f"Creneaux prevus: {n_attendus} selon l'ADR 08 (5 min de 06h a 20h, 15 min sinon)")
    print(f"Couverture     : {100*len(ok)/n_attendus:.1f} % des creneaux prevus"
          if n_attendus else "Couverture     : fenetre trop courte pour etre evaluee")

    ecarts = ok["t"].diff().dt.total_seconds().dropna() / 60
    if len(ecarts):
        print(f"\nEcart entre deux passages reussis (minutes) :")
        print(f"  mediane {ecarts.median():.1f} | p10 {ecarts.quantile(.1):.1f} | "
              f"p90 {ecarts.quantile(.9):.1f} | max {ecarts.max():.1f}")
        print(f"  passages a plus de 20 min d'ecart : {int((ecarts > 20).sum())}")

    if len(echecs):
        print(f"\nMotifs d'echec :")
        for m, n in echecs["erreur"].value_counts().items():
            print(f"  {n:4d}  {m[:100]}")

    chg = pd.to_numeric(ok["changements"], errors="coerce")
    print(f"\nChangements d'etat enregistres : {int(chg.sum())} au total, "
          f"mediane {chg.median():.0f} par passage")
    print(f"Doublons intra-capture resolus : mediane {pd.to_numeric(ok['doublons_resolus'], errors='coerce').median():.0f} par passage")
    print(f"Etats contradictoires          : mediane {pd.to_numeric(ok['etats_contradictoires'], errors='coerce').median():.0f} par passage")
    print(f"Duree d'un passage (s)         : mediane {pd.to_numeric(ok['duree_s'], errors='coerce').median():.1f}")

    photos = sorted((COLLECTE / "dynamique" / "instantanes").glob("*.csv.gz"))
    fichiers = list((COLLECTE / "dynamique" / "changements").rglob("*.csv.gz"))
    octets = sum(p.stat().st_size for p in photos) + sum(p.stat().st_size for p in fichiers)
    print(f"\nArchive dynamique : {len(photos)} photos, {len(fichiers)} fichiers de "
          f"changements, {octets/1e6:.1f} Mo")

    js = JOURNAUX / "statique.csv"
    if js.exists():
        s = pd.read_csv(js, dtype=str, keep_default_na=False)
        print(f"Archive statique  : {len(s)} passages, "
              f"{(s['verification'] == 'ok').sum()} reconstructions verifiees, "
              f"{(s['resultat'] == 'echec').sum()} echecs")

    print("=" * 72)
    if duree >= 48:
        print(f"PREUVE ACQUISE : {duree:.1f} h de captures reelles archivees.")
    else:
        reste = 48 - duree
        print(f"En cours : {duree:.1f} h sur 48 h, il reste {reste:.1f} h "
              f"(fin prevue le {(debut + timedelta(hours=48)):%Y-%m-%d %H:%M} UTC).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
