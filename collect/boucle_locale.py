#!/usr/bin/env python3
"""Boucle de collecte a cadence garantie.

Le planificateur de GitHub s'est revele inutilisable pour une cadence de cinq
minutes : un seul declenchement obtenu en quatre heures la ou cinquante etaient
attendus. Cette boucle resout le probleme en inversant la logique : GitHub ne
declenche plus chaque passage, il declenche une fois par heure une boucle qui
tient elle-meme la cadence jusqu'au creneau horaire suivant (--jusqu-a). Un
declenchement horaire retarde de vingt minutes coute vingt minutes de collecte,
pas la journee entiere.

Le meme script sert en local (--heures) et dans GitHub Actions (--jusqu-a).
Chaque passage est etiquete `local` ou `github` dans le journal, et la
publication se rejoue sur la tete distante en cas de course.

Ce qu'il fait a chaque creneau :
  1. recale le depot sur la tete distante,
  2. lance le collecteur dynamique dans un processus isole,
  3. lance le collecteur statique s'il n'a pas deja tourne pour le jour courant,
  4. publie.

Il ne rattrape jamais un creneau manque : un trou reste un trou.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
# L'interpreteur qui fait tourner la boucle, et non un chemin code en dur :
# le venv local n'existe pas sur un runner GitHub.
PYTHON = sys.executable
JOURNAL_STATIQUE = RACINE / "data" / "collecte" / "journal" / "statique.csv"

MINUTES_JOUR = list(range(2, 60, 5))          # 02, 07, 12 ... 57, de 06h a 20h UTC
MINUTES_NUIT = [7, 22, 37, 52]                # toutes les 15 minutes sinon
HEURE_STATIQUE = 3                            # le statique tourne apres 03h UTC


def maintenant() -> datetime:
    return datetime.now(timezone.utc)


def prochain_creneau(apres: datetime) -> datetime:
    t = apres.replace(second=0, microsecond=0) + timedelta(minutes=1)
    for _ in range(24 * 60):
        minutes = MINUTES_JOUR if 6 <= t.hour < 20 else MINUTES_NUIT
        if t.minute in minutes:
            return t
        t += timedelta(minutes=1)
    raise RuntimeError("aucun creneau trouve")


def executer(cmd: list[str], etape: str) -> int:
    r = subprocess.run(cmd, cwd=RACINE, capture_output=True, text=True, timeout=900)
    sortie = (r.stdout or "").strip()
    if sortie:
        for ligne in sortie.splitlines():
            print(f"  [{etape}] {ligne}", flush=True)
    if r.returncode != 0:
        err = (r.stderr or "").strip().splitlines()
        for ligne in err[-4:]:
            print(f"  [{etape}] ERR {ligne}", flush=True)
    return r.returncode


def statique_deja_fait(jour) -> bool:
    if not JOURNAL_STATIQUE.exists():
        return False
    texte = JOURNAL_STATIQUE.read_text(encoding="utf-8", errors="replace")
    return any(f",{jour}," in ligne and ",ok," in ligne for ligne in texte.splitlines())


def passage(publier: bool) -> None:
    t = maintenant()
    if publier:
        executer(["git", "pull", "--rebase", "--autostash", "--quiet", "origin", "main"],
                 "recalage")
    code = executer([PYTHON, "collect/collecte_dynamique.py"], "dynamique")
    chemins = ["data/collecte/dynamique", "data/collecte/journal"]
    if t.hour >= HEURE_STATIQUE and not statique_deja_fait(t.date()):
        if executer([PYTHON, "collect/collecte_statique.py"], "statique") == 0:
            chemins.append("data/collecte/statique")
    if publier:
        executer(["bash", "collect/publier.sh", "collecte locale", *chemins], "publication")
    return code


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--heures", type=float, default=50.0,
                    help="duree totale de supervision, en heures")
    ap.add_argument("--jusqu-a", dest="jusqu_a", default=None,
                    help="instant d'arret en ISO 8601 UTC, prioritaire sur --heures. "
                         "Utilise par GitHub Actions : chaque passage horaire collecte "
                         "jusqu'au creneau suivant, ce qui rend la cadence independante "
                         "du planificateur.")
    ap.add_argument("--sans-publication", action="store_true",
                    help="collecter sans pousser sur le depot")
    args = ap.parse_args()

    if executer([PYTHON, "collect/verifier.py"], "verification") != 0:
        print("superviseur non demarre : la verification de sante a echoue", flush=True)
        return 1

    debut = maintenant()
    if args.jusqu_a:
        fin = datetime.fromisoformat(args.jusqu_a)
        if fin.tzinfo is None:
            fin = fin.replace(tzinfo=timezone.utc)
    else:
        fin = debut + timedelta(hours=args.heures)
    if fin <= debut:
        print("instant d'arret deja passe, rien a faire", flush=True)
        return 0
    print(f"superviseur local demarre le {debut:%Y-%m-%d %H:%M:%S} UTC, "
          f"jusqu'au {fin:%Y-%m-%d %H:%M} UTC", flush=True)
    print(f"cadence ADR 08 : minutes {MINUTES_JOUR} de 06h a 20h UTC, "
          f"minutes {MINUTES_NUIT} sinon", flush=True)

    passage(not args.sans_publication)
    while maintenant() < fin:
        cible = prochain_creneau(maintenant())
        attente = (cible - maintenant()).total_seconds()
        if attente > 0:
            time.sleep(attente)
        if maintenant() >= fin:
            break
        try:
            passage(not args.sans_publication)
        except Exception as exc:                                   # noqa: BLE001
            print(f"  [superviseur] passage en erreur : {type(exc).__name__}: {exc}",
                  flush=True)
    print(f"superviseur arrete le {maintenant():%Y-%m-%d %H:%M:%S} UTC", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
