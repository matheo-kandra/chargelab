#!/usr/bin/env python3
"""Fonctions partagees par les collecteurs.

Regles appliquees ici, toutes issues de docs/decisions.md :
  ADR 11 : dans une meme capture dynamique, un id_pdc_itinerance vu plusieurs
           fois est resolu par l'horodatage le plus recent, puis par la
           derniere ligne du fichier.
Aucune donnee n'est corrigee : on resout, on compte, on journalise.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import io
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

RACINE = Path(__file__).resolve().parent.parent
COLLECTE = RACINE / "data" / "collecte"
JOURNAUX = COLLECTE / "journal"
AGENT = "chargelab/0.1 (collecte IRVE, contact via le depot)"


def maintenant() -> datetime:
    return datetime.now(timezone.utc)


def telecharger(url: str, essais: int = 3, attente: int = 20) -> tuple[bytes | None, str]:
    """Renvoie (corps, message). Ne leve pas : un echec est un creneau manque."""
    dernier = ""
    for i in range(essais):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": AGENT})
            with urllib.request.urlopen(req, timeout=180) as resp:
                if resp.status != 200:
                    dernier = f"HTTP {resp.status}"
                    continue
                return resp.read(), ""
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            dernier = f"{type(exc).__name__}: {exc}"
        if i + 1 < essais:
            time.sleep(attente)
    return None, dernier


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def ecrire_gz(chemin: Path, contenu: bytes) -> None:
    """Ecrit un .gz deterministe : mtime a zero, sinon deux archives du meme
    contenu auraient des empreintes differentes et le depot enflerait pour rien."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with chemin.open("wb") as fh:
        with gzip.GzipFile(filename="", mode="wb", compresslevel=9, fileobj=fh, mtime=0) as gz:
            gz.write(contenu)


def lire_csv_gz(chemin: Path, **kw) -> pd.DataFrame:
    return pd.read_csv(chemin, dtype=str, keep_default_na=False, **kw)


def df_vers_csv(df: pd.DataFrame) -> bytes:
    buf = io.StringIO()
    df.to_csv(buf, index=False, lineterminator="\n")
    return buf.getvalue().encode("utf-8")


def journaliser(nom: str, ligne: dict) -> None:
    """Ajoute une ligne au journal `nom`. L'en-tete est ecrit une seule fois."""
    dest = JOURNAUX / f"{nom}.csv"
    dest.parent.mkdir(parents=True, exist_ok=True)
    existe = dest.exists()
    with dest.open("a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(ligne.keys()))
        if not existe:
            w.writeheader()
        w.writerow(ligne)


def resoudre_doublons_dynamique(df: pd.DataFrame) -> tuple[pd.DataFrame, int, int]:
    """ADR 11. Renvoie (df resolu, nb doublons resolus, nb etats contradictoires)."""
    n0 = len(df)
    distincts = df["id_pdc_itinerance"].nunique()
    doublons = n0 - distincts
    contradictoires = 0
    if doublons:
        g = df.groupby("id_pdc_itinerance")["etat_pdc"].nunique()
        contradictoires = int((g > 1).sum())
    h = pd.to_datetime(df["horodatage"], errors="coerce", utc=True, format="mixed")
    df = (df.assign(_h=h, _i=range(n0))
            .sort_values(["_h", "_i"], na_position="first")
            .drop_duplicates("id_pdc_itinerance", keep="last")
            .drop(columns=["_h", "_i"])
            .sort_values("id_pdc_itinerance")
            .reset_index(drop=True))
    return df, doublons, contradictoires
