#!/usr/bin/env python3
"""Collecte quotidienne du fichier statique IRVE (ressource 84013).

Telecharge la consolidation dedoublonnee, l'archive selon le schema compact de
l'ADR 10, puis VERIFIE que la reconstruction du jour redonne exactement le
fichier telecharge. Si la verification echoue, le passage est en echec et rien
n'est considere comme archive : le probleme doit etre vu, pas absorbe.

Le fichier non dedoublonne (84011, 290 Mo) n'est telecharge que le lundi, en
meme temps que la photo complete, pour l'audit du dedoublonnage et la
recuperation des PDC perdus (ADR 02). Il n'est pas archive : seuls ses
compteurs le sont.
"""
from __future__ import annotations

import io
import sys
from collections import Counter
from datetime import date

import pandas as pd

from archive_statique import archiver, verifier
from commun import journaliser, maintenant, sha256, telecharger

URL_DEDUP = "https://transport.data.gouv.fr/resources/84013/download"
URL_BRUT = "https://transport.data.gouv.fr/resources/84011/download"


def audit_dedoublonnage() -> dict:
    """Compte les doublons resolus et les PDC perdus par la consolidation."""
    brut, err = telecharger(URL_BRUT)
    if brut is None:
        return {"audit": "echec", "audit_erreur": err}
    df = pd.read_csv(io.BytesIO(brut), dtype=str, keep_default_na=False,
                     usecols=["id_pdc_itinerance", "deduplication_status"], low_memory=False)
    ids = df["id_pdc_itinerance"].str.strip()
    df = df[(ids != "") & (ids != "Non concerné")]
    statuts = Counter(df["deduplication_status"])
    gardes = {i for i, s in zip(df["id_pdc_itinerance"], df["deduplication_status"])
              if s.startswith("kept_") or s == "unique"}
    perdus = set(df["id_pdc_itinerance"]) - gardes
    return {
        "audit": "ok",
        "audit_lignes": len(df),
        "audit_pdc_distincts": df["id_pdc_itinerance"].nunique(),
        "audit_doublons_resolus": len(df) - df["id_pdc_itinerance"].nunique(),
        "audit_pdc_perdus": len(perdus),
        "audit_statuts": " | ".join(f"{k}={v}" for k, v in statuts.most_common()),
    }


def main() -> int:
    t0 = maintenant()
    jour = t0.date()
    ligne = {
        "collecte_utc": t0.isoformat(timespec="seconds"), "jour": str(jour),
        "source": SOURCE,
        "resultat": "", "octets": "", "sha256_telechargement": "",
        "lignes": "", "pdc_distincts": "", "mode": "", "octets_archives": "",
        "entrees": "", "sorties": "", "contenu_modifie": "", "date_maj_seule": "",
        "verification": "", "sha256_canonique": "", "duree_s": "", "erreur": "",
    }

    brut, err = telecharger(URL_DEDUP)
    if brut is None:
        ligne["resultat"] = "echec"
        ligne["erreur"] = err
        ligne["duree_s"] = f"{(maintenant() - t0).total_seconds():.1f}"
        journaliser("statique", ligne)
        print(f"jour manque : {err}", flush=True)
        return 0

    ligne["octets"] = len(brut)
    ligne["sha256_telechargement"] = sha256(brut)
    df = pd.read_csv(io.BytesIO(brut), dtype=str, keep_default_na=False, low_memory=False)
    ligne["lignes"] = len(df)
    ligne["pdc_distincts"] = df["id_pdc_itinerance"].nunique()

    infos = archiver(jour, df)
    ligne.update({k: infos.get(k, "") for k in
                  ("mode", "entrees", "sorties", "contenu_modifie", "date_maj_seule")})
    ligne["octets_archives"] = infos["octets_gz"]

    ok, attendu, obtenu = verifier(jour, df)
    ligne["verification"] = "ok" if ok else "ECHEC"
    ligne["sha256_canonique"] = attendu
    ligne["duree_s"] = f"{(maintenant() - t0).total_seconds():.1f}"

    if jour.weekday() == 0:
        ligne.update(audit_dedoublonnage())

    ligne["resultat"] = "ok" if ok else "echec"
    journaliser("statique", ligne)
    print(f"{jour} : {ligne['lignes']} lignes, mode {infos['mode']}, "
          f"{infos['octets_gz']} o archives, verification {ligne['verification']}", flush=True)
    if not ok:
        print(f"RECONSTRUCTION NON CONFORME\n  attendu {attendu}\n  obtenu  {obtenu}",
              file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
