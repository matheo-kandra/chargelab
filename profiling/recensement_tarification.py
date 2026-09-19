#!/usr/bin/env python3
"""Recensement descriptif des familles de valeurs de `tarification`.

Ce n'est PAS le parseur de production. C'est un denombrement, etabli apres
lecture des 438 valeurs distinctes, destine a montrer la repartition avant
tout calcul de prix. Chaque famille est definie par un marqueur litteral
observe dans les donnees, pas par une heuristique de prix.
"""
import csv
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs" / "tarification-valeurs.csv"
OUT = ROOT / "data" / "profiling" / "tarification-familles.csv"

# Formulations de non-information relevees telles quelles dans le fichier.
NON_INFO_EXACT = {
    "-", "inconnu", "payant", "true", "false", "null", "0 pour utilisateur",
    "non communiqué", "grille tarifaire en ligne", "au kwh", "fixe",
    "voir tarif gireve", "0 pour utilisateur zeborne", "15", "050 kwh",
}
RE_URL = re.compile(r"https?://")
RE_JSON = re.compile(r'^\s*\{.*"energyPrice"')
RE_STRUCT = re.compile(r"(par défaut\s*:|entre \d{1,2}:\d{2} et \d{1,2}:\d{2}\s*:)")
RE_KWH = re.compile(r"k\s*w\s*h|/\s*kw\b|par kwh|le kwh|kw/h", re.I)
RE_TEMPS = re.compile(r"/\s*min|par minute|à la minute|/\s*mn|€\s*/\s*h\b|par heure|/heure", re.I)
RE_GRATUIT = re.compile(r"\bgratuit|\bgratuite\b", re.I)
RE_NOMBRE_NU = re.compile(r"^\s*\d+([.,]\d+)?\s*€?\s*$")
RE_DISCLAIMER = re.compile(r"peuvent varier en fonction|frais de connexion éventuelles|supplément de ta?r?if à la minute", re.I)


def famille(v: str) -> str:
    s = v.strip()
    low = s.lower()
    if s == "":
        return "VIDE"
    if low in NON_INFO_EXACT:
        return "NON_INFO_MOT_CLE"
    if RE_URL.search(s):
        return "RENVOI_URL"
    if RE_DISCLAIMER.search(s):
        return "RENVOI_TEXTE"
    if RE_JSON.match(s):
        return "JSON_OPERATEUR"
    if RE_STRUCT.search(s):
        return "EXPORT_STRUCTURE"
    if RE_GRATUIT.search(s) and not RE_KWH.search(s):
        return "GRATUIT"
    if RE_KWH.search(s):
        return "PRIX_KWH_LIBRE"
    if RE_TEMPS.search(s):
        return "PRIX_TEMPS_SEUL"
    if RE_NOMBRE_NU.match(s):
        return "NOMBRE_NU_SANS_UNITE"
    return "AUTRE_NON_CLASSE"


rows = list(csv.DictReader(SRC.open(encoding="utf-8")))
par_famille = Counter()
valeurs_par_famille = defaultdict(int)
exemples = defaultdict(list)
total = sum(int(r["nb_pdc_dedoublonne"]) for r in rows)
for r in rows:
    f = famille(r["valeur_brute"])
    n = int(r["nb_pdc_dedoublonne"])
    par_famille[f] += n
    if r["valeur_brute"] != "":
        valeurs_par_famille[f] += 1
        if len(exemples[f]) < 4:
            exemples[f].append(r["valeur_brute"].replace("\n", " ")[:80])

renseigne = total - par_famille["VIDE"]
OUT.parent.mkdir(parents=True, exist_ok=True)
with OUT.open("w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["famille", "nb_pdc", "part_parc_pct", "part_renseigne_pct", "nb_valeurs_distinctes", "exemples"])
    for f, n in par_famille.most_common():
        w.writerow([f, n, round(100 * n / total, 3),
                    "" if f == "VIDE" else round(100 * n / renseigne, 3),
                    valeurs_par_famille[f], " || ".join(exemples[f])])

print(f"parc total (PDC) : {total}")
print(f"tarification renseignee : {renseigne} ({100*renseigne/total:.2f} % du parc)\n")
print(f"{'famille':22s} {'PDC':>7s} {'%parc':>7s} {'%rens.':>7s} {'valeurs':>8s}")
for f, n in par_famille.most_common():
    pr = "" if f == "VIDE" else f"{100*n/renseigne:6.2f}%"
    print(f"{f:22s} {n:7d} {100*n/total:6.2f}% {pr:>7s} {valeurs_par_famille[f]:8d}")
    for e in exemples[f][:2]:
        print(f"    ex. {e}")
