#!/usr/bin/env python3
"""Construction d'une edition : de l'archive brute aux matrices du jour.

    python build/edition.py --date 2026-09-19

Le script ne lit que l'archive de data/collecte, jamais un telechargement
frais : c'est ce qui rend une edition passee reconstructible a l'identique.
Il ecrit dans data/editions/<date>/ :

    pdc.csv.gz      un point de charge par ligne, avec tout ce qui a servi
                    a le classer. C'est la colonne vertebrale de la
                    tracabilite : chaque chiffre affiche doit pouvoir etre
                    retrouve en filtrant ce fichier.
    M_parc.csv      parc par departement et classe de puissance
    M_etat.csv      etat du jour par departement
    M_prix.csv      prix par classe de puissance et par reseau, avec effectif
    M_reseaux.csv   parc et etat par reseau
    edition.json    l'objet racine, compteurs et parametres
    MANIFESTE.csv   taille et empreinte de chaque fichier produit

Aucun chiffre n'est arrondi a la main et aucune mediane n'est publiee sous le
seuil d'effectif : la case rend son effectif et rien d'autre.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import sys
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
# Les collecteurs s'importent entre eux par leur nom simple, parce qu'ils sont
# lances comme des scripts. On leur ouvre le chemin plutot que de les
# transformer en paquet, ce qui casserait leur usage dans les workflows.
sys.path.insert(0, str(RACINE / "collect"))

from build.etat_jour import (SEUIL_DOMINANCE, SEUIL_FRAICHEUR_H,  # noqa: E402
                             etat_du_jour, creneaux_du_jour)
from build.parser_tarification import analyser  # noqa: E402
from build.referentiels import (CLASSES, classe_puissance, courant,  # noqa: E402
                                departement_insee, departements_par_points,
                                noms_par_prefixe, prefixe_emi3)
from build.statistiques import SEUIL_EFFECTIF, bande  # noqa: E402
from archive_statique import cleifier, reconstruire  # noqa: E402

SORTIE = RACINE / "data" / "editions"
BORNES_PRIX = (0.05, 1.50)
N_REPORT_JOURS = 10


def _nombre(serie: pd.Series) -> pd.Series:
    return pd.to_numeric(serie.str.replace(",", ".", regex=False), errors="coerce")


def enrichir(jour: date) -> tuple[pd.DataFrame, dict]:
    """Reconstruit le statique du jour et lui attache tous les rattachements."""
    brut = reconstruire(jour)
    df = cleifier(brut)
    compteurs = {"lignes_statique": len(df),
                 "pdc_distincts": int(df["id_pdc_itinerance"].nunique())}

    df["puissance"] = _nombre(df["puissance_nominale"])
    df["courant"] = [courant(a, b, c, d) for a, b, c, d in zip(
        df["prise_type_combo_ccs"], df["prise_type_chademo"],
        df["prise_type_2"], df["prise_type_ef"])]
    df["classe"] = [classe_puissance(c, p) for c, p in zip(df["courant"], df["puissance"])]

    lon = pd.to_numeric(df["consolidated_longitude"], errors="coerce")
    lat = pd.to_numeric(df["consolidated_latitude"], errors="coerce")
    df["departement"] = departements_par_points(
        zip(lon.where(lon.notna(), None), lat.where(lat.notna(), None)))
    df["departement_insee"] = [departement_insee(c) for c in df["code_insee_commune"]]
    compare = df["departement"].notna() & df["departement_insee"].notna()
    compteurs["departement_par_coordonnees"] = int(df["departement"].notna().sum())
    # Deux sortes de non-rattachement, qui ne veulent pas dire la meme chose :
    # un point sur un plan d'eau ou en frontiere reste francais, un point a
    # Madrid ne l'est pas. Aucun n'est rapproche du departement le plus proche.
    non_rattache = df["departement"].isna()
    dans_metropole = (lon.between(-5.3, 9.7) & lat.between(41.3, 51.2))
    compteurs["departement_non_rattache"] = int(non_rattache.sum())
    compteurs["non_rattache_dans_boite_metropole"] = int((non_rattache & dans_metropole).sum())
    compteurs["non_rattache_hors_france"] = int((non_rattache & ~dans_metropole).sum())
    compteurs["departement_desaccord_insee"] = int(
        (compare & (df["departement"] != df["departement_insee"])).sum())

    df["prefixe"] = [prefixe_emi3(i) for i in df["id_pdc_itinerance"]]
    noms = noms_par_prefixe(df["prefixe"], df["nom_operateur"])
    df["reseau"] = [noms.get(p, "inconnu") if p else "inconnu" for p in df["prefixe"]]
    compteurs["prefixes_distincts"] = int(df["prefixe"].nunique())
    compteurs["libelles_enseigne_distincts"] = int(df["nom_enseigne"].nunique())

    # Prix : une analyse par valeur distincte, puis report.
    table = {v: analyser(v) for v in df["tarification"].unique()}
    res = df["tarification"].map(table)
    df["code_prix"] = [r.code for r in res]
    df["prix_kwh"] = [r.prix_kwh for r in res]
    df["prix_kwh_ac"] = [r.prix_kwh_ac for r in res]
    df["prix_kwh_dc"] = [r.prix_kwh_dc for r in res]
    df["prix_ht_converti"] = [r.ht_converti for r in res]
    # Un tarif differencie est rattache a la classe du point, pas a une moyenne.
    # Attention : une colonne pandas rend NaN, pas None, pour une absence. Le
    # test doit donc porter sur pd.isna et non sur `is None`, sinon toutes les
    # lignes basculent dans la branche AC/DC et le prix disparait.
    def _retenu(kwh, ac, dc, classe):
        if not pd.isna(ac) or not pd.isna(dc):
            v = ac if classe.startswith("AC") else dc
            return None if pd.isna(v) else float(v)
        return None if pd.isna(kwh) else float(kwh)

    df["prix_retenu"] = [_retenu(k, a, d, c) for k, a, d, c in zip(
        df["prix_kwh"], df["prix_kwh_ac"], df["prix_kwh_dc"], df["classe"])]
    compteurs["codes_prix"] = dict(Counter(df["code_prix"]))
    compteurs["pdc_avec_prix"] = int(df["prix_retenu"].notna().sum())
    compteurs["prix_ht_convertis"] = int(df["prix_ht_converti"].sum())
    return df, compteurs


def joindre_etat(df: pd.DataFrame, jour: date) -> tuple[pd.DataFrame, dict]:
    etat = etat_du_jour(jour)
    df = df.join(etat, on="id_pdc_itinerance")
    df["etat_jour"] = df["etat_jour"].fillna("absent du flux")
    df["frais"] = df["frais"].fillna(False)
    c = Counter(df["etat_jour"])
    compteurs = {
        "creneaux_captures": len(creneaux_du_jour(jour)),
        "etats_du_jour": dict(c),
        "pdc_avec_etat_frais": int(df["frais"].sum()),
    }
    frais = df[df["frais"]]
    compteurs["taux_hors_service_sur_frais"] = (
        round(float((frais["etat_jour"] == "hors_service").mean()), 6) if len(frais) else None)
    return df, compteurs


def matrices(df: pd.DataFrame, dossier: Path) -> dict:
    """Ecrit les matrices du jour et rend les effectifs qu'elles portent."""
    infos = {}

    parc = (df.groupby(["departement", "classe"], dropna=False)
              .agg(pdc=("id_pdc_itinerance", "size"),
                   stations=("id_station_itinerance", "nunique"),
                   puissance_totale_kw=("puissance", "sum"))
              .reset_index())
    parc.to_csv(dossier / "M_parc.csv", index=False)
    infos["M_parc_lignes"] = len(parc)

    etat = (df.groupby("departement", dropna=False)
              .agg(pdc=("id_pdc_itinerance", "size"),
                   frais=("frais", "sum"),
                   hors_service=("etat_jour", lambda s: int((s == "hors_service").sum())),
                   muet=("etat_jour", lambda s: int((s == "muet").sum())),
                   inconnu=("etat_jour", lambda s: int((s == "inconnu").sum())))
              .reset_index())
    # Le taux n'est calcule que la ou l'effectif frais atteint le seuil ; le
    # denominateur est masque ailleurs, ce qui evite a la fois une division
    # par zero et un taux publie sur trois points de charge.
    denominateur = etat["frais"].astype(float).where(etat["frais"] >= SEUIL_EFFECTIF)
    etat["taux_hors_service"] = etat["hors_service"] / denominateur
    etat.to_csv(dossier / "M_etat.csv", index=False)
    infos["M_etat_lignes"] = len(etat)
    infos["departements_sous_seuil_etat"] = int((etat["frais"] < SEUIL_EFFECTIF).sum())

    lignes = []
    for (classe, reseau), g in df.dropna(subset=["prix_retenu"]).groupby(["classe", "reseau"]):
        b = bande(g["prix_retenu"].tolist())
        lignes.append({"classe": classe, "reseau": reseau, **b})
    prix = pd.DataFrame(lignes, columns=["classe", "reseau", "n", "p10", "p25",
                                         "p50", "p75", "p90"])
    prix.to_csv(dossier / "M_prix.csv", index=False)
    infos["M_prix_cases"] = len(prix)
    infos["M_prix_cases_publiables"] = int(prix["p50"].notna().sum()) if len(prix) else 0

    reseaux = (df.groupby("reseau")
                 .agg(pdc=("id_pdc_itinerance", "size"),
                      stations=("id_station_itinerance", "nunique"),
                      frais=("frais", "sum"),
                      hors_service=("etat_jour", lambda s: int((s == "hors_service").sum())),
                      avec_prix=("prix_retenu", "count"),
                      puissance_mediane_kw=("puissance", "median"),
                      part_paiement_cb=("paiement_cb", lambda s: float((s == "true").mean())),
                      part_gratuit=("gratuit", lambda s: float((s == "true").mean())))
                 .sort_values("pdc", ascending=False).reset_index())
    reseaux.to_csv(dossier / "M_reseaux.csv", index=False)
    infos["M_reseaux_lignes"] = len(reseaux)
    return infos


def empreinte_donnees(dossier: Path) -> str:
    """Empreinte des fichiers de donnees, edition.json exclu.

    edition.json porte l'heure de generation, qui change a chaque execution.
    Cette empreinte-la ne change pas : c'est elle qui atteste que
    `make edition DATE=...` regenere bien la meme edition.
    """
    h = hashlib.sha256()
    for p in sorted(dossier.iterdir()):
        if p.name in ("MANIFESTE.csv", "edition.json"):
            continue
        h.update(p.name.encode("utf-8"))
        h.update(hashlib.sha256(p.read_bytes()).digest())
    return h.hexdigest()


def manifeste(dossier: Path) -> None:
    with (dossier / "MANIFESTE.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["fichier", "octets", "sha256"])
        for p in sorted(dossier.iterdir()):
            if p.name == "MANIFESTE.csv":
                continue
            w.writerow([p.name, p.stat().st_size,
                        hashlib.sha256(p.read_bytes()).hexdigest()])


def construire(jour: date) -> dict:
    debut = datetime.now(timezone.utc)
    dossier = SORTIE / str(jour)
    dossier.mkdir(parents=True, exist_ok=True)

    df, c1 = enrichir(jour)
    df, c2 = joindre_etat(df, jour)

    colonnes = ["id_pdc_itinerance", "id_station_itinerance", "nom_enseigne",
                "nom_operateur", "prefixe", "reseau", "puissance", "courant",
                "classe", "departement", "departement_insee",
                "consolidated_longitude", "consolidated_latitude",
                "code_prix", "prix_retenu", "prix_ht_converti",
                "etat_jour", "frais", "part_hors_service", "part_occupe",
                "date_mise_en_service", "date_maj"]
    # gzip deterministe : sans mtime a zero, deux constructions du meme jour
    # produiraient des fichiers differents et la reproductibilite exigee par la
    # spec ne serait pas verifiable.
    corps = df[colonnes].to_csv(index=False, lineterminator="\n").encode("utf-8")
    with (dossier / "pdc.csv.gz").open("wb") as fh:
        with gzip.GzipFile(filename="", mode="wb", compresslevel=9,
                           fileobj=fh, mtime=0) as gz:
            gz.write(corps)

    c3 = matrices(df, dossier)

    edition = {
        "date": str(jour),
        "generated_at": debut.isoformat(timespec="seconds"),
        "sources": {
            "statique": "consolidation PAN beta, ressource 84013, archive locale",
            "dynamique": "consolidation PAN beta, ressource 84098, captures archivees",
            "contours": "france-geojson, derive d'Admin Express IGN, Licence ouverte",
            "licence": "Licence Ouverte / Etalab v2.0",
        },
        "parametres": {
            "seuil_fraicheur_heures": SEUIL_FRAICHEUR_H,
            "seuil_dominance": SEUIL_DOMINANCE,
            "seuil_effectif": SEUIL_EFFECTIF,
            "bornes_prix_kwh": list(BORNES_PRIX),
            "report_derniere_valeur_jours": N_REPORT_JOURS,
            "classes_puissance": list(CLASSES),
            "taux_tva_conversion_ht": 0.20,
        },
        "counts": {**c1, **c2, **c3},
    }
    edition["empreinte_donnees"] = empreinte_donnees(dossier)
    (dossier / "edition.json").write_text(
        json.dumps(edition, ensure_ascii=False, indent=1), encoding="utf-8")
    manifeste(dossier)
    edition["duree_s"] = round((datetime.now(timezone.utc) - debut).total_seconds(), 1)
    return edition


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True, help="jour de l'edition, AAAA-MM-JJ")
    args = ap.parse_args()
    jour = date.fromisoformat(args.date)
    e = construire(jour)
    c = e["counts"]
    print(f"edition du {jour} construite en {e['duree_s']} s")
    print(f"  parc          : {c['pdc_distincts']} PDC, {c['lignes_statique']} lignes")
    print(f"  territoire    : {c['departement_par_coordonnees']} rattaches par coordonnees, "
          f"{c['departement_non_rattache']} non rattaches, "
          f"{c['departement_desaccord_insee']} en desaccord avec l'INSEE")
    print(f"  reseaux       : {c['prefixes_distincts']} prefixes pour "
          f"{c['libelles_enseigne_distincts']} libelles d'enseigne")
    print(f"  prix          : {c['pdc_avec_prix']} PDC avec un prix, "
          f"{c['M_prix_cases_publiables']} cases publiables sur {c['M_prix_cases']}")
    print(f"  etat du jour  : {c['creneaux_captures']} creneaux, "
          f"{c['pdc_avec_etat_frais']} PDC avec un etat de moins de "
          f"{SEUIL_FRAICHEUR_H} h")
    print(f"  codes de prix : {c['codes_prix']}")
    print(f"  etats         : {c['etats_du_jour']}")
    print(f"  empreinte     : {e['empreinte_donnees'][:16]}")
    print(f"  ecrit dans    : data/editions/{jour}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
