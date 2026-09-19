#!/usr/bin/env python3
"""Collecte du flux IRVE dynamique (consolidation PAN beta, ressource 84098).

A chaque passage :
  1. telecharge le flux,
  2. resout les doublons intra-capture (ADR 11 : horodatage le plus recent),
  3. reconstitue l'etat connu au passage precedent,
  4. n'archive QUE les changements d'`etat_pdc` ou d'`occupation_pdc`, avec
     l'horodatage operateur ET l'horodatage de capture,
  5. ecrit une photo complete par jour,
  6. journalise le passage, reussi ou non.

L'etat precedent n'est PAS stocke dans un fichier d'etat : il est reconstitue a
chaque passage depuis la derniere photo complete et les fichiers de changements
posterieurs. Un fichier d'etat de 1,5 Mo reecrit 208 fois par jour ferait enfler
le depot de 312 Mo par jour, pour une information deja contenue ailleurs.

Le premier passage d'une histoire vierge n'ecrit aucun changement : il pose la
photo de reference. Un passage en echec est un creneau manque, jamais reconstruit.

Cadence prevue (ADR 08) : 5 minutes de 06:00 a 20:00 UTC, 15 minutes sinon.
"""
from __future__ import annotations

import io
import sys
from datetime import date, datetime, timedelta

import pandas as pd

from commun import (COLLECTE, RACINE, df_vers_csv, ecrire_gz, journaliser,
                    lire_csv_gz, maintenant, resoudre_doublons_dynamique,
                    sha256, telecharger)

URL = "https://transport.data.gouv.fr/resources/84098/download"
COLS = ["id_pdc_itinerance", "etat_pdc", "occupation_pdc", "horodatage"]
ETAT_COLS = ["id_pdc_itinerance", "etat_pdc", "occupation_pdc"]
BASE = COLLECTE / "dynamique"
PHOTOS = BASE / "instantanes"
CHANGEMENTS = BASE / "changements"


def _photos() -> list[date]:
    if not PHOTOS.exists():
        return []
    out = []
    for p in PHOTOS.glob("*.csv.gz"):
        try:
            out.append(date.fromisoformat(p.name.split(".")[0]))
        except ValueError:
            continue
    return sorted(out)


def _fichiers_changements(depuis: datetime) -> list:
    """Fichiers de changements posterieurs a `depuis`.

    On ne parcourt que les dossiers AAAA/MM concernes : un rglob sur tout
    l'historique couterait un parcours de dizaines de milliers de fichiers a
    chaque passage, 208 fois par jour, pour n'en lire qu'une poignee.
    """
    if not CHANGEMENTS.exists():
        return []
    mois = {(depuis.year, depuis.month)}
    fin = maintenant()
    mois.add((fin.year, fin.month))
    candidats = []
    for an, m in sorted(mois):
        d = CHANGEMENTS / f"{an:04d}" / f"{m:02d}"
        if d.is_dir():
            candidats.extend(d.glob("*.csv.gz"))
    out = []
    for p in candidats:
        try:
            t = datetime.strptime(p.name.split(".")[0], "%Y-%m-%d_%H%M%S")
        except ValueError:
            continue
        t = t.replace(tzinfo=depuis.tzinfo)
        if t > depuis:
            out.append((t, p))
    return [p for _, p in sorted(out)]


def etat_connu() -> tuple[pd.DataFrame | None, str]:
    """Reconstitue l'etat au dernier passage : derniere photo + changements."""
    photos = _photos()
    if not photos:
        return None, "aucune photo"
    jour = photos[-1]
    df = lire_csv_gz(PHOTOS / f"{jour}.csv.gz", usecols=lambda c: c in COLS,
                     low_memory=False)
    df, _, _ = resoudre_doublons_dynamique(df)
    df = df[ETAT_COLS].set_index("id_pdc_itinerance")
    origine = datetime.combine(jour, datetime.min.time(), tzinfo=maintenant().tzinfo)
    fichiers = _fichiers_changements(origine)
    for p in fichiers:
        ev = lire_csv_gz(p)
        ev = ev.drop_duplicates("id_pdc_itinerance", keep="last").set_index("id_pdc_itinerance")
        df = pd.concat([df.drop(index=ev.index, errors="ignore"), ev[ETAT_COLS[1:]]])
    return df, f"photo {jour} + {len(fichiers)} fichiers de changements"


def main() -> int:
    t0 = maintenant()
    ligne = {
        "capture_utc": t0.isoformat(timespec="seconds"), "resultat": "",
        "octets": "", "sha256": "", "lignes_flux": "", "pdc_distincts": "",
        "doublons_resolus": "", "etats_contradictoires": "", "etat_reference": "",
        "changements": "", "entrees": "", "sorties": "", "photo_du_jour": "",
        "duree_s": "", "erreur": "",
    }

    brut, err = telecharger(URL)
    if brut is None:
        ligne["resultat"] = "echec"
        ligne["erreur"] = err
        ligne["duree_s"] = f"{(maintenant() - t0).total_seconds():.1f}"
        journaliser("dynamique", ligne)
        print(f"creneau manque : {err}", flush=True)
        return 0

    ligne["octets"] = len(brut)
    ligne["sha256"] = sha256(brut)
    df = pd.read_csv(io.BytesIO(brut), dtype=str, keep_default_na=False,
                     usecols=lambda c: c in COLS, low_memory=False)
    ligne["lignes_flux"] = len(df)
    df, doublons, contradictoires = resoudre_doublons_dynamique(df)
    ligne["pdc_distincts"] = len(df)
    ligne["doublons_resolus"] = doublons
    ligne["etats_contradictoires"] = contradictoires

    photo = PHOTOS / f"{t0:%Y-%m-%d}.csv.gz"
    premiere_du_jour = not photo.exists()

    etat, origine = etat_connu()
    ligne["etat_reference"] = origine
    if etat is not None:
        cur = df.set_index("id_pdc_itinerance")
        communs = cur.index.intersection(etat.index)
        chg = communs[(cur.loc[communs, "etat_pdc"].values != etat.loc[communs, "etat_pdc"].values) |
                      (cur.loc[communs, "occupation_pdc"].values != etat.loc[communs, "occupation_pdc"].values)]
        ev = cur.loc[chg].reset_index()[COLS]
        ev["horodatage_capture"] = t0.isoformat(timespec="seconds")
        ligne["changements"] = len(ev)
        ligne["entrees"] = len(cur.index.difference(etat.index))
        ligne["sorties"] = len(etat.index.difference(cur.index))
        if len(ev):
            dest = (CHANGEMENTS / f"{t0:%Y}" / f"{t0:%m}" / f"{t0:%Y-%m-%d_%H%M%S}.csv.gz")
            ecrire_gz(dest, df_vers_csv(ev))
        ligne["resultat"] = "ok"
    else:
        ligne["changements"] = 0
        ligne["entrees"] = len(df)
        ligne["sorties"] = 0
        ligne["resultat"] = "ok (photo de reference)"

    if premiere_du_jour:
        ecrire_gz(photo, brut)
        ligne["photo_du_jour"] = str(photo.relative_to(RACINE))

    ligne["duree_s"] = f"{(maintenant() - t0).total_seconds():.1f}"
    journaliser("dynamique", ligne)
    print(f"{ligne['capture_utc']} : {ligne['pdc_distincts']} PDC, "
          f"{ligne['changements']} changements, {doublons} doublons resolus "
          f"({contradictoires} contradictoires), base sur {origine}, "
          f"{ligne['duree_s']} s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
