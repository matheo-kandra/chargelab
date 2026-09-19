#!/usr/bin/env python3
"""Archivage compact du fichier statique et reconstruction exacte (ADR 10).

Le fichier statique pese 6,2 Mo compresses mais 99,64 % de son contenu ne bouge
pas d'un jour a l'autre : sur deux jours, seuls 0,363 % des PDC voient un champ
autre que `date_maj` changer. L'archiver en entier chaque jour couterait 2 260 Mo
par an contre 385 Mo avec le schema ci-dessous, pour la meme information.

Schema d'archivage, par date :
  complet/AAAA-MM-JJ.csv.gz   photo complete, ecrite le lundi et au premier jour
  diff/AAAA-MM-JJ.csv.gz      lignes ajoutees ou dont un champ de CONTENU a change
  date_maj/AAAA-MM-JJ.csv.gz  lignes dont seuls date_maj et datagouv_last_modified
                              ont change (id, _occ, et les deux colonnes)
  sorties/AAAA-MM-JJ.csv      cles disparues ce jour-la

La cle est (id_pdc_itinerance, _occ) ou `_occ` est le rang d'apparition de l'id
dans le fichier : le fichier source contient quelques identifiants en double
(2 lignes au 19/09/2026) et la cle doit rester unique pour que la
reconstruction soit exacte.

`reconstruire(date)` rejoue la photo complete la plus recente puis les journaux
de chaque jour, et doit rendre octet pour octet la serialisation canonique du
fichier telecharge ce jour-la. Le collecteur verifie cette egalite a chaque
passage : si elle est fausse, le passage echoue.
"""
from __future__ import annotations

import gzip
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from commun import COLLECTE, df_vers_csv, ecrire_gz, sha256

BASE = COLLECTE / "statique"
COMPLET, DIFF, DATEMAJ, SORTIES = (BASE / n for n in ("complet", "diff", "date_maj", "sorties"))
CLE = ["id_pdc_itinerance", "_occ"]
COLS_MAJ = ["date_maj", "datagouv_last_modified"]


def cleifier(df: pd.DataFrame) -> pd.DataFrame:
    """Ajoute la colonne technique `_occ` et ordonne le tableau de facon stable."""
    df = df.copy()
    # zero-padde pour que le tri lexicographique reste correct au-dela de 10
    # occurrences d'un meme identifiant (le fichier non dedoublonne monte a 257)
    df["_occ"] = df.groupby("id_pdc_itinerance").cumcount().map("{:03d}".format)
    return df.sort_values(CLE, kind="stable").reset_index(drop=True)


def canonique(df: pd.DataFrame) -> bytes:
    """Serialisation deterministe, independante de l'ordre du fichier source."""
    autres = [c for c in df.columns if c not in CLE]
    return df_vers_csv(df.sort_values(CLE, kind="stable")[CLE + autres].reset_index(drop=True))


def _dates_disponibles(dossier: Path) -> list[date]:
    if not dossier.exists():
        return []
    out = []
    for p in dossier.iterdir():
        nom = p.name.split(".")[0]
        try:
            out.append(date.fromisoformat(nom))
        except ValueError:
            continue
    return sorted(out)


def derniere_photo(jusqu_a: date) -> date | None:
    d = [x for x in _dates_disponibles(COMPLET) if x <= jusqu_a]
    return d[-1] if d else None


def reconstruire(jour: date) -> pd.DataFrame:
    """Rejoue la photo complete puis les journaux quotidiens jusqu'a `jour`."""
    base = derniere_photo(jour)
    if base is None:
        raise FileNotFoundError(f"aucune photo complete disponible avant le {jour}")
    df = pd.read_csv(COMPLET / f"{base}.csv.gz", dtype=str, keep_default_na=False,
                     low_memory=False)
    if "_occ" not in df.columns:
        df = cleifier(df)
    df = df.set_index(CLE)

    d = base + timedelta(days=1)
    while d <= jour:
        f = SORTIES / f"{d}.csv"
        if f.exists():
            s = pd.read_csv(f, dtype=str, keep_default_na=False)
            if len(s):
                df = df.drop(index=pd.MultiIndex.from_frame(s[CLE]), errors="ignore")
        f = DIFF / f"{d}.csv.gz"
        if f.exists():
            a = pd.read_csv(f, dtype=str, keep_default_na=False, low_memory=False).set_index(CLE)
            df = pd.concat([df.drop(index=a.index, errors="ignore"), a])
        f = DATEMAJ / f"{d}.csv.gz"
        if f.exists():
            m = pd.read_csv(f, dtype=str, keep_default_na=False).set_index(CLE)
            communs = df.index.intersection(m.index)
            for c in COLS_MAJ:
                if c in m.columns:
                    df.loc[communs, c] = m.loc[communs, c]
        d += timedelta(days=1)
    return df.reset_index()


def archiver(jour: date, courant: pd.DataFrame, forcer_complet: bool = False) -> dict:
    """Ecrit les fichiers du jour. Renvoie le detail des volumes et des comptes."""
    courant = cleifier(courant)
    veille = jour - timedelta(days=1)
    complet = forcer_complet or jour.weekday() == 0 or derniere_photo(veille) is None

    if complet:
        octets = df_vers_csv(courant)
        ecrire_gz(COMPLET / f"{jour}.csv.gz", octets)
        return {"mode": "complet", "lignes": len(courant),
                "octets_gz": (COMPLET / f"{jour}.csv.gz").stat().st_size,
                "entrees": "", "sorties": "", "contenu_modifie": "", "date_maj_seule": ""}

    avant = cleifier(reconstruire(veille)).set_index(CLE)
    apres = courant.set_index(CLE)
    communs = avant.index.intersection(apres.index)
    entrees = apres.index.difference(avant.index)
    sorties = avant.index.difference(apres.index)

    cols_contenu = [c for c in apres.columns if c not in COLS_MAJ]
    a, b = avant.loc[communs, cols_contenu], apres.loc[communs, cols_contenu]
    modif_contenu = communs[(a.values != b.values).any(axis=1)]
    reste = communs.difference(modif_contenu)
    ma, mb = avant.loc[reste, COLS_MAJ], apres.loc[reste, COLS_MAJ]
    modif_maj = reste[(ma.values != mb.values).any(axis=1)]

    lignes_diff = apres.loc[modif_contenu.union(entrees)].reset_index()
    ecrire_gz(DIFF / f"{jour}.csv.gz", df_vers_csv(lignes_diff))
    ecrire_gz(DATEMAJ / f"{jour}.csv.gz",
              df_vers_csv(apres.loc[modif_maj, COLS_MAJ].reset_index()))
    (SORTIES).mkdir(parents=True, exist_ok=True)
    df_sorties = sorties.to_frame(index=False) if len(sorties) else pd.DataFrame(columns=CLE)
    (SORTIES / f"{jour}.csv").write_text(df_vers_csv(df_sorties).decode("utf-8"), encoding="utf-8")

    return {"mode": "diff", "lignes": len(courant),
            "octets_gz": ((DIFF / f"{jour}.csv.gz").stat().st_size
                          + (DATEMAJ / f"{jour}.csv.gz").stat().st_size
                          + (SORTIES / f"{jour}.csv").stat().st_size),
            "entrees": len(entrees), "sorties": len(sorties),
            "contenu_modifie": len(modif_contenu), "date_maj_seule": len(modif_maj)}


def verifier(jour: date, courant: pd.DataFrame) -> tuple[bool, str, str]:
    """Reconstruit `jour` et compare a la serialisation canonique du telechargement."""
    attendu = sha256(canonique(cleifier(courant)))
    obtenu = sha256(canonique(cleifier(reconstruire(jour))))
    return attendu == obtenu, attendu, obtenu
