#!/usr/bin/env python3
"""Validation locale d'un fichier IRVE contre son Table Schema (v2.3.0).

On ne corrige rien : on compte les violations, champ par champ et motif par
motif, et on compte les lignes ayant au moins une violation bloquante
(contrainte `required`, `enum`, `pattern`, type numerique, borne).
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
BOOLS = {"true", "false", "True", "False", "TRUE", "FALSE", "1", "0"}


def valider(csv_path: Path, schema_path: Path) -> dict:
    schema = json.load(schema_path.open(encoding="utf-8"))
    df = pd.read_csv(csv_path, dtype=str, keep_default_na=False, low_memory=False)
    n = len(df)
    motifs = Counter()
    lignes_ko = pd.Series(False, index=df.index)

    for f in schema["fields"]:
        col, typ = f["name"], f.get("type", "string")
        c = f.get("constraints", {})
        if col not in df.columns:
            motifs[f"{col}: colonne absente"] = n
            continue
        s = df[col].astype(str).str.strip()
        vide = s == ""
        if c.get("required"):
            k = int(vide.sum())
            if k:
                motifs[f"{col}: requis mais vide"] = k
                lignes_ko |= vide
        nv = ~vide
        if "enum" in c:
            bad = nv & ~s.isin(c["enum"])
            if bad.any():
                motifs[f"{col}: hors enum"] = int(bad.sum())
                lignes_ko |= bad
        if "pattern" in c:
            rx = re.compile(c["pattern"])
            bad = nv & ~s.apply(lambda v: bool(rx.match(v)))
            if bad.any():
                motifs[f"{col}: motif non respecte"] = int(bad.sum())
                lignes_ko |= bad
        if typ in ("number", "integer"):
            num = pd.to_numeric(s.str.replace(",", ".", regex=False), errors="coerce")
            bad = nv & num.isna()
            if bad.any():
                motifs[f"{col}: non numerique"] = int(bad.sum())
                lignes_ko |= bad
            if c.get("minimum") is not None:
                b2 = nv & num.notna() & (num < c["minimum"])
                if b2.any():
                    motifs[f"{col}: < minimum {c['minimum']}"] = int(b2.sum())
                    lignes_ko |= b2
        if typ == "boolean":
            bad = nv & ~s.isin(BOOLS)
            if bad.any():
                motifs[f"{col}: booleen non reconnu"] = int(bad.sum())
                lignes_ko |= bad
        if typ == "date":
            d = pd.to_datetime(s.where(nv), errors="coerce", format="mixed")
            bad = nv & d.isna()
            if bad.any():
                motifs[f"{col}: date illisible"] = int(bad.sum())
                lignes_ko |= bad
        if typ == "datetime":
            d = pd.to_datetime(s.where(nv), errors="coerce", format="mixed", utc=True)
            bad = nv & d.isna()
            if bad.any():
                motifs[f"{col}: datetime illisible"] = int(bad.sum())
                lignes_ko |= bad
        if typ == "geopoint":
            bad = nv & ~s.apply(lambda v: bool(re.match(r"^\[?\s*-?\d+(\.\d+)?\s*,\s*-?\d+(\.\d+)?\s*\]?$", v)))
            if bad.any():
                motifs[f"{col}: geopoint illisible"] = int(bad.sum())
                lignes_ko |= bad

    return {
        "fichier": csv_path.name,
        "schema": f"{schema['name']} {schema.get('version')}",
        "lignes": n,
        "lignes_avec_au_moins_une_violation": int(lignes_ko.sum()),
        "part_lignes_ko": round(100 * lignes_ko.sum() / n, 3),
        "violations_par_motif": dict(motifs.most_common()),
    }


if __name__ == "__main__":
    cibles = [
        ("data/raw/statique/pan_dedoublonne_2026-09-17.csv", "data/raw/schema-irve-statique.json"),
        ("data/raw/statique/pan_avec_doublons_2026-09-17.csv", "data/raw/schema-irve-statique.json"),
        ("data/raw/dynamique/2026-09-17/202312.csv.gz", "data/raw/schema-irve-dynamique.json"),
    ]
    out = []
    for csvp, schp in cibles:
        r = valider(ROOT / csvp, ROOT / schp)
        out.append(r)
        print("=" * 78)
        print(r["fichier"], "|", r["schema"], "|", r["lignes"], "lignes")
        print(f"  lignes avec >= 1 violation : {r['lignes_avec_au_moins_une_violation']} ({r['part_lignes_ko']} %)")
        for m, k in r["violations_par_motif"].items():
            print(f"    {k:8d}  {m}")
    (ROOT / "data" / "profiling" / "validation-schema.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
