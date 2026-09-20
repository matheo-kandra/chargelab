#!/usr/bin/env python3
"""Filet de securite local : ne collecte que si GitHub s'est tu.

La collecte nominale est assuree par GitHub Actions (workflow `Collecte`, une
boucle horaire qui tient la cadence de l'ADR 08). Faire tourner en plus une
collecte locale permanente dedouble les captures et fausse les statistiques de
cadence : deux fichiers de changements a une seconde d'ecart pour le meme
evenement.

Ce filet regarde donc l'heure du dernier passage reussi, quelle qu'en soit la
source. Tant qu'elle est recente, il ne fait rien. Si elle depasse le seuil,
il declenche une capture locale et la publie. On a la redondance sans la
pollution.

Usage : python collect/filet_local.py [--seuil-min 25] [--heures 50]
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

RACINE = Path(__file__).resolve().parent.parent
PYTHON = sys.executable
JOURNAL = RACINE / "data" / "collecte" / "journal" / "dynamique.csv"


def executer(cmd: list[str], etape: str) -> int:
    r = subprocess.run(cmd, cwd=RACINE, capture_output=True, text=True, timeout=900)
    for ligne in (r.stdout or "").strip().splitlines():
        print(f"  [{etape}] {ligne}", flush=True)
    if r.returncode != 0:
        for ligne in (r.stderr or "").strip().splitlines()[-3:]:
            print(f"  [{etape}] ERR {ligne}", flush=True)
    return r.returncode


def dernier_passage_reussi() -> datetime | None:
    if not JOURNAL.exists():
        return None
    d = pd.read_csv(JOURNAL, dtype=str, keep_default_na=False)
    ok = d[d["resultat"].str.startswith("ok")]
    if ok.empty:
        return None
    return pd.to_datetime(ok["capture_utc"], utc=True, format="mixed").max().to_pydatetime()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seuil-min", type=float, default=25.0,
                    help="silence tolere avant de prendre le relais, en minutes")
    ap.add_argument("--heures", type=float, default=50.0)
    ap.add_argument("--intervalle-min", type=float, default=5.0)
    args = ap.parse_args()

    fin = datetime.now(timezone.utc) + timedelta(hours=args.heures)
    print(f"filet local arme, seuil {args.seuil_min} min, jusqu'au {fin:%Y-%m-%d %H:%M} UTC",
          flush=True)
    while datetime.now(timezone.utc) < fin:
        executer(["git", "pull", "--rebase", "--autostash", "--quiet", "origin", "main"],
                 "recalage")
        dernier = dernier_passage_reussi()
        maintenant = datetime.now(timezone.utc)
        silence = (maintenant - dernier).total_seconds() / 60 if dernier else 1e9
        if silence > args.seuil_min:
            print(f"{maintenant:%H:%M} : silence de {silence:.0f} min, le filet prend le relais",
                  flush=True)
            executer([PYTHON, "collect/collecte_dynamique.py"], "dynamique")
            executer(["bash", "collect/publier.sh", "collecte filet",
                      "data/collecte/dynamique", "data/collecte/journal"], "publication")
        time.sleep(args.intervalle_min * 60)
    print("filet local desarme", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
