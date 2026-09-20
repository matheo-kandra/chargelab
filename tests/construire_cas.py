#!/usr/bin/env python3
"""Materialise tests/tarification_cases.csv depuis l'inventaire et les attendus.

Le texte brut n'est jamais recopie a la main : il est lu dans
docs/tarification-valeurs.csv, inventaire fige du 17 septembre 2026, par son
rang. Les colonnes attendues viennent de tests/cas_attendus.py, ecrites a la
lecture. Le fichier produit est l'artefact que le build consomme.

L'empreinte de l'inventaire est inscrite dans l'en-tete du CSV : si l'inventaire
change, la correspondance rang vers texte n'est plus garantie et il faut
reconstruire les cas.
"""
from __future__ import annotations

import csv
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cas_attendus import CAS, CAS_AC_DC  # noqa: E402

RACINE = Path(__file__).resolve().parent.parent
INVENTAIRE = RACINE / "docs" / "tarification-valeurs.csv"
SORTIE = RACINE / "tests" / "tarification_cases.csv"

COLONNES = [
    "rang", "nb_pdc", "part_pct", "valeur_brute", "code_attendu",
    "prix_kwh", "prix_kwh_ac", "prix_kwh_dc", "prix_min", "prix_heure_charge",
    "prix_session", "prix_occupation_h", "ht_converti", "motif",
]


def fmt(x) -> str:
    if x is None:
        return ""
    return f"{x:.8g}"


def main() -> int:
    brut = INVENTAIRE.read_bytes()
    empreinte = hashlib.sha256(brut).hexdigest()
    lignes = [r for r in csv.DictReader(INVENTAIRE.open(encoding="utf-8"))
              if r["valeur_brute"] != ""]
    total = sum(int(r["nb_pdc_dedoublonne"]) for r in lignes)

    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    with SORTIE.open("w", newline="", encoding="utf-8") as fh:
        fh.write(f"# inventaire source : docs/tarification-valeurs.csv\n")
        fh.write(f"# sha256 de l'inventaire : {empreinte}\n")
        fh.write(f"# {len(CAS)} cas sur {len(lignes)} valeurs distinctes\n")
        w = csv.writer(fh)
        w.writerow(COLONNES)
        couvert = 0
        for rang in sorted(CAS):
            src = lignes[rang - 1]
            code, kwh, mn, hc, sess, occ, ht, motif = CAS[rang]
            ac, dc = CAS_AC_DC.get(rang, (None, None))
            n = int(src["nb_pdc_dedoublonne"])
            couvert += n
            w.writerow([
                rang, n, round(100 * n / total, 4), src["valeur_brute"], code,
                fmt(kwh), fmt(ac), fmt(dc), fmt(mn), fmt(hc), fmt(sess), fmt(occ),
                "oui" if ht else "non", motif,
            ])

    print(f"{len(CAS)} cas ecrits dans {SORTIE.relative_to(RACINE)}")
    print(f"couverture : {couvert} / {total} PDC tarifes = {100*couvert/total:.2f} %")
    print(f"empreinte de l'inventaire : {empreinte[:16]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
