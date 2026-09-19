#!/usr/bin/env python3
"""Cadence de rafraichissement du flux dynamique mesuree sur 24 h completes.

ATTENTION : ce script a servi une fois, le 17/09/2026, comme mesure de controle.
Le depot source appartient a un tiers et ne porte aucune licence. Les fichiers
bruts telecharges ont ete supprimes du projet apres calcul ; seuls les agregats
par creneau subsistent dans data/profiling/cadence-24h-2026-08-20.csv. Le script
est conserve pour documenter la provenance des chiffres du §8.1, pas pour etre
rejoue. La mesure de reference du projet est celle de cadence_propre_24h.py.

Source : archive de changements d'etat du depot Valentinafry/irve-collecte,
journee du 2026-08-20 (144 passages de 10 minutes, aucun creneau manquant).
Chaque fichier ne contient que les PDC dont `etat_pdc` ou `occupation_pdc` a
change depuis le passage precedent. On en tire :
  - le nombre de changements par creneau de 10 minutes,
  - la part du parc concernee,
  - le delai entre l'horodatage operateur et l'horodatage de collecte,
  - le nombre de PDC qui ne changent jamais de la journee.
"""
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
JOUR = "2026-08-20"
EV = ROOT / "data" / "externe" / "irve-collecte" / JOUR
SNAP = ROOT / "data" / "externe" / "irve-collecte" / f"instantane-{JOUR}.csv.gz"

snap = pd.read_csv(SNAP, dtype=str, keep_default_na=False)
parc = snap["id_pdc_itinerance"].nunique()
print(f"parc present dans le flux le {JOUR} : {parc} PDC distincts ({len(snap)} lignes)\n")

fichiers = sorted(EV.glob("*.csv.gz"))
print(f"creneaux archives : {len(fichiers)} sur 144 attendus (pas de 10 min)")
lignes, vus = [], Counter()
retards = []
for f in fichiers:
    df = pd.read_csv(f, dtype=str, keep_default_na=False)
    lignes.append((f.name.split("_")[1][:6], len(df)))
    vus.update(df["id_pdc_itinerance"].unique())
    h = pd.to_datetime(df["horodatage"], errors="coerce", utc=True, format="mixed")
    c = pd.to_datetime(df["horodatage_collecte"], errors="coerce", utc=True, format="mixed")
    retards.extend(((c - h).dt.total_seconds() / 60).dropna().tolist())

s = pd.Series([n for _, n in lignes])
print(f"changements par creneau de 10 min : mediane {s.median():.0f}, "
      f"p10 {s.quantile(.1):.0f}, p90 {s.quantile(.9):.0f}, min {s.min()}, max {s.max()}")
print(f"soit {100*s.median()/parc:.2f} % du parc par creneau (mediane)")
print(f"total de changements sur 24 h : {s.sum()} ({s.sum()/parc:.2f} par PDC en moyenne)")
print(f"\nPDC ayant change au moins une fois dans la journee : {len(vus)} ({100*len(vus)/parc:.1f} % du parc)")
print(f"PDC n'ayant jamais change : {parc-len(vus)} ({100*(parc-len(vus))/parc:.1f} %)")

r = pd.Series(retards)
print("\ndelai horodatage operateur -> horodatage de collecte (minutes) :")
for q in (0.1, 0.25, 0.5, 0.75, 0.9, 0.99):
    print(f"   p{int(q*100):<3d} {r.quantile(q):10.1f}")
print(f"   part des changements detectes moins de 10 min apres l'horodatage operateur : "
      f"{100*(r<10).mean():.1f} %")
print(f"   part au-dela de 24 h : {100*(r>1440).mean():.1f} %")

print("\nprofil horaire (changements par creneau, moyenne par heure) :")
par_heure = {}
for hhmmss, n in lignes:
    par_heure.setdefault(hhmmss[:2], []).append(n)
for h in sorted(par_heure):
    v = par_heure[h]
    print(f"   {h}h : {sum(v)/len(v):7.0f}")
