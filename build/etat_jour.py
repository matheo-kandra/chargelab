#!/usr/bin/env python3
"""Etat du jour de chaque point de charge, reconstruit depuis les captures.

La collecte n'archive qu'une photo complete par jour et les changements d'etat
(ADR 10). L'etat au creneau t se reconstitue donc en partant de la photo et en
appliquant les changements dont l'horodatage de capture precede t. On compte
ensuite, pour chaque point, la part de creneaux passes dans chaque etat.

Trois regles, toutes chiffrees dans docs/decisions.md :

  ADR 12  seuil de fraicheur a 24 heures. Un point dont l'horodatage operateur
          depasse 24 heures n'a pas d'etat pour la journee : il est muet, pas
          en service. Trente pour cent des lignes du flux portent un
          horodatage de plus de trois mois.
  ADR 13  dominance a 50 % des creneaux. La variable est quasi binaire :
          87,78 % des points ne sont jamais hors service, 6,73 % le sont
          toujours, et passer le seuil de 25 % a 75 % ne deplace le taux que
          de 1,64 point.
  ADR 14  trois etats distincts, jamais confondus : hors service declare,
          inconnu persistant, muet.

Un creneau manque reste manque : aucune interpolation entre deux captures.
"""
from __future__ import annotations

import bisect
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

RACINE = Path(__file__).resolve().parent.parent
BASE = RACINE / "data" / "collecte" / "dynamique"
JOURNAL = RACINE / "data" / "collecte" / "journal" / "dynamique.csv"

SEUIL_FRAICHEUR_H = 24
SEUIL_DOMINANCE = 0.50
COLS = ["id_pdc_itinerance", "etat_pdc", "occupation_pdc", "horodatage"]


def creneaux_du_jour(jour: date) -> list[datetime]:
    """Instants de capture reussis ce jour-la, lus dans le journal."""
    if not JOURNAL.exists():
        return []
    d = pd.read_csv(JOURNAL, dtype=str, keep_default_na=False)
    t = pd.to_datetime(d["capture_utc"], utc=True, format="mixed")
    garde = d["resultat"].str.startswith("ok") & (t.dt.date == jour)
    return sorted(t[garde].dt.to_pydatetime())


def _fichiers_changements(jour: date) -> list[tuple[datetime, Path]]:
    dossier = BASE / "changements" / f"{jour:%Y}" / f"{jour:%m}"
    if not dossier.is_dir():
        return []
    out = []
    for p in dossier.glob(f"{jour:%Y-%m-%d}_*.csv.gz"):
        t = datetime.strptime(p.name.split(".")[0], "%Y-%m-%d_%H%M%S").replace(
            tzinfo=timezone.utc)
        out.append((t, p))
    return sorted(out)


def etat_du_jour(jour: date) -> pd.DataFrame:
    """Un tableau par point de charge : parts d'etat, fraicheur, etat retenu.

    Colonnes : creneaux, hors_service, inconnu, occupe, part_hors_service,
    part_inconnu, part_occupe, horodatage_max, frais, etat_jour.
    """
    photo_p = BASE / "instantanes" / f"{jour}.csv.gz"
    creneaux = creneaux_du_jour(jour)
    if not photo_p.exists() or not creneaux:
        return pd.DataFrame(columns=[
            "creneaux", "hors_service", "inconnu", "occupe", "part_hors_service",
            "part_inconnu", "part_occupe", "horodatage_max", "frais", "etat_jour"])

    photo = pd.read_csv(photo_p, dtype=str, keep_default_na=False,
                        usecols=lambda c: c in COLS, low_memory=False)
    h = pd.to_datetime(photo["horodatage"], errors="coerce", utc=True, format="mixed")
    photo = (photo.assign(_h=h).sort_values("_h").drop_duplicates(
        "id_pdc_itinerance", keep="last"))

    n = len(creneaux)
    etat0 = dict(zip(photo["id_pdc_itinerance"], photo["etat_pdc"]))
    occ0 = dict(zip(photo["id_pdc_itinerance"], photo["occupation_pdc"]))
    horo = {i: t for i, t in zip(photo["id_pdc_itinerance"], photo["_h"])
            if pd.notna(t)}

    # Par defaut, un point garde l'etat de la photo sur tous les creneaux.
    compte_hs = Counter()
    compte_inc = Counter()
    compte_occ = Counter()
    for pdc, e in etat0.items():
        if e == "hors_service":
            compte_hs[pdc] = n
        elif e == "inconnu":
            compte_inc[pdc] = n
    for pdc, o in occ0.items():
        if o == "occupe":
            compte_occ[pdc] = n

    # Puis on rejoue les changements, point par point.
    evenements: dict[str, list[tuple[datetime, str, str]]] = {}
    for t, p in _fichiers_changements(jour):
        ev = pd.read_csv(p, dtype=str, keep_default_na=False)
        hh = pd.to_datetime(ev["horodatage"], errors="coerce", utc=True, format="mixed")
        for pdc, e, o, ho in zip(ev["id_pdc_itinerance"], ev["etat_pdc"],
                                 ev["occupation_pdc"], hh):
            evenements.setdefault(pdc, []).append((t, e, o))
            if pd.notna(ho) and (pdc not in horo or ho > horo[pdc]):
                horo[pdc] = ho

    for pdc, evs in evenements.items():
        bornes = [creneaux[0]] + [t for t, _, _ in evs]
        etats = [etat0.get(pdc, "inconnu")] + [e for _, e, _ in evs]
        occs = [occ0.get(pdc, "inconnu")] + [o for _, _, o in evs]
        hs = inc = occ = 0
        for k in range(len(bornes)):
            debut = bornes[k]
            fin = bornes[k + 1] if k + 1 < len(bornes) else None
            i = bisect.bisect_left(creneaux, debut)
            j = bisect.bisect_left(creneaux, fin) if fin else n
            nb = max(0, j - i)
            if etats[k] == "hors_service":
                hs += nb
            elif etats[k] == "inconnu":
                inc += nb
            if occs[k] == "occupe":
                occ += nb
        compte_hs[pdc] = hs
        compte_inc[pdc] = inc
        compte_occ[pdc] = occ

    tous = sorted(set(etat0) | set(evenements))
    fin_jour = creneaux[-1]
    limite = fin_jour - timedelta(hours=SEUIL_FRAICHEUR_H)
    lignes = []
    for pdc in tous:
        hs, inc, occ = compte_hs.get(pdc, 0), compte_inc.get(pdc, 0), compte_occ.get(pdc, 0)
        hmax = horo.get(pdc)
        frais = hmax is not None and hmax >= limite
        if not frais:
            etat = "muet"
        elif hs / n >= SEUIL_DOMINANCE:
            etat = "hors_service"
        elif inc / n >= SEUIL_DOMINANCE:
            etat = "inconnu"
        else:
            etat = "en_service"
        lignes.append((pdc, n, hs, inc, occ, hs / n, inc / n, occ / n, hmax, frais, etat))

    return pd.DataFrame(lignes, columns=[
        "id_pdc_itinerance", "creneaux", "hors_service", "inconnu", "occupe",
        "part_hors_service", "part_inconnu", "part_occupe", "horodatage_max",
        "frais", "etat_jour"]).set_index("id_pdc_itinerance")
