#!/usr/bin/env python3
"""Generation de site/index.html a partir d'une edition construite.

    python build/page.py --date 2026-09-19

Un seul fichier, aucune requete au moment de l'affichage, aucune police ni
carte externe. Les donnees sont embarquees : coordonnees des stations en
tableaux typas encodes en base64, le reste en JSON compact.

Ce que la page refuse de faire, et qui est le sujet du projet :
  - afficher une mediane sous le seuil d'effectif ;
  - tracer une serie quand il n'y a qu'un jour de releves ;
  - projeter une tendance avant d'avoir de quoi la mesurer ;
  - presenter un taux hors service comme portant sur le parc entier alors
    qu'il ne porte que sur les points qui se declarent.

Chaque section indique son effectif entre parentheses et dit ce qui lui
manque. Les chiffres viennent tous de data/editions/<date>/.
"""
from __future__ import annotations

import argparse
import base64
import gzip
import json
import struct
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
from build.statistiques import SEUIL_EFFECTIF, bande, mediane  # noqa: E402

EDITIONS = RACINE / "data" / "editions"
CONTOURS = RACINE / "data" / "raw" / "departements-version-simplifiee.geojson"
SORTIE = RACINE / "site" / "index.html"

JOURS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
MOIS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet",
        "août", "septembre", "octobre", "novembre", "décembre")
ORDRE_CLASSES = ["AC <= 7 kW", "AC 7 a 22,9 kW", "AC > 22,9 kW",
                 "DC < 50 kW", "DC 50 a 150 kW", "DC >= 150 kW", "non classable"]
LIBELLE_CLASSES = {
    "AC <= 7 kW": "AC jusqu'à 7 kW", "AC 7 a 22,9 kW": "AC 7 à 22 kW",
    "AC > 22,9 kW": "AC au-delà de 22 kW", "DC < 50 kW": "DC sous 50 kW",
    "DC 50 a 150 kW": "DC 50 à 150 kW", "DC >= 150 kW": "DC 150 kW et plus",
    "non classable": "non classable"}
ETATS = ["en_service", "hors_service", "inconnu", "muet", "absent du flux"]


def date_longue(j: date) -> str:
    return f"{JOURS[j.weekday()]} {j.day} {MOIS[j.month - 1]} {j.year}"


def b64_int32(valeurs) -> str:
    return base64.b64encode(struct.pack(f"<{len(valeurs)}i",
                                        *[int(v) for v in valeurs])).decode()


def b64_uint8(valeurs) -> str:
    return base64.b64encode(struct.pack(f"<{len(valeurs)}B",
                                        *[int(v) for v in valeurs])).decode()


def agreger_stations(pdc: pd.DataFrame) -> dict:
    """Une station par point sur la carte, comme le prevoit le budget.

    L'etat de la station est le plus severe de ses points de charge : une
    station dont un point est hors service n'est pas une station en service.
    """
    pdc = pdc.copy()
    pdc["cls_i"] = pdc["classe"].map({c: i for i, c in enumerate(ORDRE_CLASSES)})
    severite = {"hors_service": 0, "inconnu": 1, "en_service": 2, "muet": 3,
                "absent du flux": 4}
    pdc["sev"] = pdc["etat_jour"].map(severite).fillna(4)
    pdc["prix"] = pd.to_numeric(pdc["prix_retenu"], errors="coerce")
    lat = pd.to_numeric(pdc["consolidated_latitude"], errors="coerce")
    lon = pd.to_numeric(pdc["consolidated_longitude"], errors="coerce")
    pdc["lat"], pdc["lon"] = lat, lon

    g = pdc.groupby("id_station_itinerance")
    st = g.agg(lat=("lat", "first"), lon=("lon", "first"),
               dep=("departement", "first"), cls=("cls_i", "max"),
               sev=("sev", "min"), pdc=("id_pdc_itinerance", "size"),
               prix=("prix", "median")).reset_index()
    st = st[st["lat"].notna() & st["lon"].notna()]
    st = st[st["lat"].between(41.0, 51.5) & st["lon"].between(-5.5, 10.0)]

    deps = sorted({d for d in st["dep"].dropna().unique()})
    idx_dep = {d: i for i, d in enumerate(deps)}
    severite_inv = ["hors_service", "inconnu", "en_service", "muet", "absent"]
    return {
        "lat": b64_int32((st["lat"] * 10000).round()),
        "lon": b64_int32((st["lon"] * 10000).round()),
        "dep": b64_uint8(st["dep"].map(idx_dep).fillna(255)),
        "cls": b64_uint8(st["cls"].fillna(len(ORDRE_CLASSES) - 1)),
        "etat": b64_uint8(st["sev"]),
        "pdc": b64_uint8(st["pdc"].clip(upper=255)),
        "prix": b64_int32((st["prix"].fillna(-1) * 1000).round()),
        "codes_dep": deps,
        "codes_etat": severite_inv,
        "n": len(st),
    }


def mises_en_service(pdc: pd.DataFrame, jour: date) -> dict:
    d = pd.to_datetime(pdc["date_mise_en_service"], errors="coerce", format="mixed")
    valide = d.notna() & (d >= pd.Timestamp("2012-01-01")) & (d <= pd.Timestamp(jour))
    semaines = d[valide].dt.to_period("W").dt.start_time.dt.date
    compte = semaines.value_counts().sort_index()
    limite = (pd.Timestamp(jour) - pd.Timedelta(weeks=52)).date()
    recent = compte[compte.index >= limite]
    return {
        "couverture": int(valide.sum()),
        "part": round(float(valide.mean()), 4),
        "semaines": [[str(k), int(v)] for k, v in recent.items()],
        "mediane_21": float(mediane(list(compte.tail(21).values)) or 0),
    }


def contours() -> dict:
    g = json.loads(CONTOURS.read_text(encoding="utf-8"))

    def arrondir(o, n=3):
        if isinstance(o, float):
            return round(o, n)
        if isinstance(o, list):
            return [arrondir(x, n) for x in o]
        if isinstance(o, dict):
            return {k: arrondir(v, n) for k, v in o.items()}
        return o

    return {f["properties"]["code"]: arrondir(f["geometry"]["coordinates"])
            for f in g["features"]}


def etat_par_classe(pdc: pd.DataFrame) -> list[dict]:
    """Etat agrege par departement et par classe, plus une ligne toutes classes.

    C'est la matrice que la page additionne pour recalculer un territoire. Elle
    ne contient que des departements reels : les points non rattaches n'y sont
    pas, et c'est precisement ce qui fait l'ecart entre le chiffre du build et
    celui recalcule par la page, ecart que la Methode affiche.
    """
    d = pdc.copy()
    d["frais_b"] = d["frais"] == "True"
    d["prix_b"] = pd.to_numeric(d["prix_retenu"], errors="coerce").notna()
    d["renseigne_b"] = d["code_prix"] != "VIDE"
    d = d[d["departement"].astype(str) != ""]

    def agrege(g):
        frais = g[g["frais_b"]]
        return pd.Series({
            "pdc": len(g),
            "frais": int(g["frais_b"].sum()),
            "hors_service": int((frais["etat_jour"] == "hors_service").sum()),
            "inconnu": int((frais["etat_jour"] == "inconnu").sum()),
            "muet": int((g["etat_jour"] == "muet").sum()),
            "absent": int((g["etat_jour"] == "absent du flux").sum()),
            "avec_prix": int(g["prix_b"].sum()),
            "renseigne": int(g["renseigne_b"].sum()),
        })

    lignes = []
    for (dep, cls), g in d.groupby(["departement", "classe"]):
        lignes.append({"departement": dep, "classe": cls, **agrege(g).to_dict()})
    for dep, g in d.groupby("departement"):
        lignes.append({"departement": dep, "classe": "*", **agrege(g).to_dict()})
    return lignes


def construire_donnees(jour: date) -> dict:
    dossier = EDITIONS / str(jour)
    edition = json.loads((dossier / "edition.json").read_text(encoding="utf-8"))
    pdc = pd.read_csv(dossier / "pdc.csv.gz", dtype=str, keep_default_na=False)

    parc = pd.read_csv(dossier / "M_parc.csv")
    etat = pd.read_csv(dossier / "M_etat.csv")
    prix = pd.read_csv(dossier / "M_prix.csv")
    reseaux = pd.read_csv(dossier / "M_reseaux.csv")

    frais = pdc[pdc["frais"] == "True"]
    national = {
        "pdc": len(pdc),
        "stations": int(pdc["id_station_itinerance"].nunique()),
        "reseaux": int(pdc["reseau"].nunique()),
        "frais": len(frais),
        "hors_service": int((frais["etat_jour"] == "hors_service").sum()),
        "muet": int((pdc["etat_jour"] == "muet").sum()),
        "absent": int((pdc["etat_jour"] == "absent du flux").sum()),
        "inconnu": int((frais["etat_jour"] == "inconnu").sum()),
        "avec_prix": int(pd.to_numeric(pdc["prix_retenu"], errors="coerce").notna().sum()),
        "tarification_renseignee": int((pdc["code_prix"] != "VIDE").sum()),
    }
    national["taux_hors_service"] = (national["hors_service"] / national["frais"]
                                     if national["frais"] else None)

    par_classe = (pdc.groupby("classe")
                  .agg(pdc=("id_pdc_itinerance", "size"),
                       avec_prix=("prix_retenu", "count"))
                  .reindex(ORDRE_CLASSES).fillna(0).astype(int).reset_index())

    return {
        "edition": edition,
        "national": national,
        "stations": agreger_stations(pdc),
        "departements": etat.fillna("").to_dict(orient="records"),
        "parc": parc.fillna("").to_dict(orient="records"),
        "classes": par_classe.to_dict(orient="records"),
        "prix": prix.fillna("").to_dict(orient="records"),
        "reseaux": reseaux.head(40).fillna("").to_dict(orient="records"),
        "etat_par_classe": etat_par_classe(pdc),
        "seuil": SEUIL_EFFECTIF,
        "mur": mises_en_service(pdc, jour),
        "contours": contours(),
        "libelles_classes": LIBELLE_CLASSES,
        "ordre_classes": ORDRE_CLASSES,
        "jours_de_releves": 1,
    }


def fr(n: int) -> str:
    """Separateur de milliers insecable fin, comme dans la page."""
    return f"{n:,}".replace(",", "\u202f")


def image_og(jour: date, donnees: dict) -> Path:
    """Vignette de partage. SVG, sans police ni image externe.

    La spec demande la courbe nationale du jour. Avec un seul jour de releves
    il n'y a pas de courbe : la vignette porte les chiffres, et la courbe la
    remplacera des qu'une serie existera. Mieux vaut une vignette qui dit la
    verite qu'une courbe tracee a travers un point.
    """
    n = donnees["national"]
    taux = 100 * n["taux_hors_service"]
    part_prix = 100 * n["avec_prix"] / n["pdc"]
    part_muets = 100 * (n["muet"] + n["absent"]) / n["pdc"]
    sans = "system-ui,sans-serif"
    serif = "Georgia,serif"
    lignes_svg = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">',
        '<rect width="1200" height="630" fill="#fbfaf7"/>',
        '<rect width="1200" height="8" fill="#1a5e63"/>',
        f'<text x="72" y="140" font-family="{serif}" font-size="60" font-weight="700" fill="#14181c">La recharge, la ou vous etes.</text>',
        f'<text x="72" y="196" font-family="{sans}" font-size="26" fill="#4a5560">Edition du {date_longue(jour)}</text>',
        '<line x1="72" y1="240" x2="1128" y2="240" stroke="#d9d5cd" stroke-width="2"/>',
        f'<text x="72" y="332" font-family="{sans}" font-size="66" font-weight="700" fill="#14181c">{fr(n["pdc"])}</text>',
        f'<text x="72" y="370" font-family="{sans}" font-size="23" fill="#4a5560">points de charge</text>',
        f'<text x="460" y="332" font-family="{sans}" font-size="66" font-weight="700" fill="#14181c">{fr(n["stations"])}</text>',
        f'<text x="460" y="370" font-family="{sans}" font-size="23" fill="#4a5560">stations</text>',
        f'<text x="820" y="332" font-family="{sans}" font-size="66" font-weight="700" fill="#a4303f">{taux:.2f} %</text>',
        f'<text x="820" y="370" font-family="{sans}" font-size="23" fill="#4a5560">hors service, sur {fr(n["frais"])} qui se declarent</text>',
        f'<text x="72" y="474" font-family="{serif}" font-size="30" fill="#14181c">{part_prix:.1f} % des points publient un tarif au kWh lisible.</text>',
        f'<text x="72" y="520" font-family="{serif}" font-size="30" fill="#14181c">{part_muets:.0f} % ne disent rien du tout.</text>',
        f'<text x="72" y="582" font-family="{sans}" font-size="19" fill="#8a9099">Source : Point d\'Acces National transport.data.gouv.fr, Licence Ouverte Etalab</text>',
        '</svg>',
    ]
    chemin = SORTIE.parent / f"og-{jour}.svg"
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text("\n".join(lignes_svg) + "\n", encoding="utf-8")
    return chemin



def assembler(jour: date) -> Path:
    from build.gabarit import GABARIT
    from build.script import SCRIPT

    donnees = construire_donnees(jour)
    og = image_og(jour, donnees)
    html = GABARIT
    remplacements = {
        "%%DATE_LONGUE%%": date_longue(jour),
        "%%N_PDC%%": f"{donnees['national']['pdc']:,}".replace(",", "\u202f"),
        "%%N_STATIONS%%": f"{donnees['national']['stations']:,}".replace(",", "\u202f"),
        "%%N_JOURS%%": str(donnees["jours_de_releves"]),
        "%%SEUIL%%": str(SEUIL_EFFECTIF),
        "%%GENERE_LE%%": datetime.now(timezone.utc).strftime("%d/%m/%Y à %H:%M UTC"),
        "%%DONNEES%%": json.dumps(donnees, separators=(",", ":"), ensure_ascii=False),
        "%%SCRIPT%%": SCRIPT,
        "%%OG_IMAGE%%": og.name,
    }
    for jeton, valeur in remplacements.items():
        html = html.replace(jeton, valeur)
    if "—" in html:
        raise SystemExit("la page contient un tiret cadratin")
    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    SORTIE.write_text(html, encoding="utf-8")
    return SORTIE


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True)
    args = ap.parse_args()
    jour = date.fromisoformat(args.date)
    chemin = assembler(jour)
    brut = chemin.stat().st_size
    comprime = len(gzip.compress(chemin.read_bytes(), 9))
    print(f"page ecrite : {chemin.relative_to(RACINE)}")
    print(f"  taille : {brut/1e6:.2f} Mo brut, {comprime/1e6:.2f} Mo compresse")
    print(f"  budget : cible 1,5 Mo, plafond 4 Mo -> "
          f"{'tenu' if comprime <= 1.5e6 else 'DEPASSE'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
