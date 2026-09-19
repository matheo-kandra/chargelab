#!/usr/bin/env python3
"""Profilage brut d'un fichier IRVE statique.

Sortie : un JSON par fichier dans data/profiling/, contenant pour chaque
colonne le taux de remplissage, le nombre de valeurs distinctes et, pour les
colonnes categorielles, la liste complete des valeurs avec leur frequence.
Aucune valeur n'est nettoyee : on decrit ce qui est reellement dans le fichier.
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "profiling"

# Colonnes dont on veut l'inventaire exhaustif des valeurs.
CATEGORIELLES = [
    "implantation_station", "condition_acces", "accessibilite_pmr", "raccordement",
    "prise_type_ef", "prise_type_2", "prise_type_combo_ccs", "prise_type_chademo",
    "prise_type_autre", "gratuit", "paiement_acte", "paiement_cb", "paiement_autre",
    "reservation", "station_deux_roues", "cable_t2_attache", "restriction_gabarit",
    "consolidated_is_lon_lat_correct", "deduplication_status", "horaires",
]
TOP_N = 60

RE_ID = re.compile(r"^[A-Z]{2}[A-Z0-9]{4,33}$")
RE_EMI3_PDC = re.compile(r"^FR[A-Z0-9]{3}[EP][A-Z0-9]{1,27}$")
RE_INSEE = re.compile(r"^([013-9]\d|2[AB1-9])\d{3}$")


def profile(path: Path, label: str) -> dict:
    df = pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[], low_memory=False)
    n = len(df)
    rep = {
        "fichier": path.name,
        "label": label,
        "octets": path.stat().st_size,
        "lignes": n,
        "colonnes": list(df.columns),
        "par_colonne": {},
    }
    for col in df.columns:
        s = df[col]
        vide = int((s.str.strip() == "").sum())
        nb_distinct = int(s.nunique(dropna=False))
        entry = {
            "renseigne": n - vide,
            "vide": vide,
            "taux_remplissage": round((n - vide) / n, 6) if n else 0.0,
            "distinct": nb_distinct,
        }
        non_vide = s[s.str.strip() != ""]
        if col in CATEGORIELLES or nb_distinct <= TOP_N:
            entry["valeurs"] = [[v, int(c)] for v, c in Counter(non_vide).most_common(TOP_N)]
            entry["valeurs_tronquees"] = nb_distinct > TOP_N
        else:
            entry["exemples"] = [[v, int(c)] for v, c in Counter(non_vide).most_common(12)]
        rep["par_colonne"][col] = entry

    # --- identifiants ---
    idp = df["id_pdc_itinerance"].str.strip()
    ids = df["id_station_itinerance"].str.strip()
    rep["identifiants"] = {
        "pdc_vide": int((idp == "").sum()),
        "pdc_non_concerne": int((idp == "Non concerné").sum()),
        "pdc_conforme_schema": int(idp.apply(lambda v: bool(RE_ID.match(v))).sum()),
        "pdc_conforme_emi3_FR": int(idp.apply(lambda v: bool(RE_EMI3_PDC.match(v))).sum()),
        "pdc_distinct": int(idp[idp != ""].nunique()),
        "pdc_doublons_lignes": int(len(idp[(idp != "") & (idp != "Non concerné")]) - idp[(idp != "") & (idp != "Non concerné")].nunique()),
        "station_vide": int((ids == "").sum()),
        "station_distinct": int(ids[ids != ""].nunique()),
        "prefixes_pays_top": [[v, int(c)] for v, c in Counter(idp[idp.str.len() >= 2].str[:2]).most_common(12)],
        "longueurs_top": [[int(k), int(v)] for k, v in Counter(idp.str.len()).most_common(15)],
    }

    # --- puissance ---
    pn = pd.to_numeric(df["puissance_nominale"].str.replace(",", ".", regex=False), errors="coerce")
    rep["puissance_nominale"] = {
        "non_numerique": int(pn.isna().sum()),
        "min": float(pn.min()) if pn.notna().any() else None,
        "max": float(pn.max()) if pn.notna().any() else None,
        "quantiles": {str(q): float(pn.quantile(q)) for q in (0.01, 0.1, 0.25, 0.5, 0.75, 0.9, 0.99)} if pn.notna().any() else {},
        "egal_0": int((pn == 0).sum()),
        "inf_1": int((pn < 1).sum()),
        "sup_400": int((pn > 400).sum()),
        "valeurs_frequentes": [[float(v), int(c)] for v, c in Counter(pn.dropna()).most_common(30)],
    }

    # --- geo ---
    lon = pd.to_numeric(df.get("consolidated_longitude", pd.Series(dtype=str)), errors="coerce")
    lat = pd.to_numeric(df.get("consolidated_latitude", pd.Series(dtype=str)), errors="coerce")
    rep["geo"] = {
        "lonlat_manquant": int((lon.isna() | lat.isna()).sum()),
        "hors_bbox_france_large": int(((lon < -63) | (lon > 56) | (lat < -22) | (lat > 52)).sum()),
        "lon_min": float(lon.min()) if lon.notna().any() else None,
        "lon_max": float(lon.max()) if lon.notna().any() else None,
        "lat_min": float(lat.min()) if lat.notna().any() else None,
        "lat_max": float(lat.max()) if lat.notna().any() else None,
    }

    # --- insee / departements ---
    insee = df["code_insee_commune"].str.strip()
    ok = insee.apply(lambda v: bool(RE_INSEE.match(v)))
    dept = insee.where(ok).apply(lambda v: (v[:3] if isinstance(v, str) and v[:2] == "97" else (v[:2] if isinstance(v, str) else None)))
    rep["insee"] = {
        "vide": int((insee == "").sum()),
        "conforme": int(ok.sum()),
        "non_conforme_non_vide": int(((~ok) & (insee != "")).sum()),
        "exemples_non_conformes": [[v, int(c)] for v, c in Counter(insee[(~ok) & (insee != "")]).most_common(20)],
        "departements_distinct": int(dept.dropna().nunique()),
        "departements": sorted(Counter(dept.dropna()).items()),
    }

    # --- dates ---
    for col in ("date_maj", "date_mise_en_service"):
        s = df[col].str.strip()
        d = pd.to_datetime(s, errors="coerce", format="mixed", utc=True)
        rep[col] = {
            "vide": int((s == "").sum()),
            "non_parsable": int((d.isna() & (s != "")).sum()),
            "exemples_non_parsables": [[v, int(c)] for v, c in Counter(s[d.isna() & (s != "")]).most_common(15)],
            "min": str(d.min()) if d.notna().any() else None,
            "max": str(d.max()) if d.notna().any() else None,
            "futur": int((d > pd.Timestamp.now(tz="UTC")).sum()),
            "par_annee": sorted(Counter(d.dt.year.dropna().astype(int)).items()),
        }

    # --- tarification (inventaire complet, ecrit a part) ---
    tar = df["tarification"]
    rep["tarification"] = {
        "vide": int((tar.str.strip() == "").sum()),
        "renseigne": int((tar.str.strip() != "").sum()),
        "distinct": int(tar[tar.str.strip() != ""].nunique()),
    }
    return rep, df


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    cibles = [
        ("data/raw/statique/pan_dedoublonne_2026-09-17.csv", "PAN beta, statique dedoublonne"),
        ("data/raw/statique/pan_avec_doublons_2026-09-17.csv", "PAN beta, statique non dedoublonne"),
        ("data/raw/statique/datagouv_consolide_v2_2026-09-17.csv", "data.gouv consolide v2 (historique)"),
    ]
    only = sys.argv[1] if len(sys.argv) > 1 else None
    for rel, label in cibles:
        if only and only not in rel:
            continue
        p = ROOT / rel
        print("profilage:", p.name, flush=True)
        rep, df = profile(p, label)
        dest = OUT / (p.stem + ".profil.json")
        dest.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
        print("  ->", dest.relative_to(ROOT), f"{rep['lignes']} lignes", flush=True)


if __name__ == "__main__":
    main()
