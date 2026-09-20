#!/usr/bin/env python3
"""Verification de sante des collecteurs, a lancer avant toute collecte.

Une erreur d'import dans collecte_statique.py est passee inapercue pendant
34 heures : le superviseur ecrivait l'erreur dans sa sortie, mais aucune ligne
de journal n'etait ecrite, donc le bilan ne voyait rien. Un collecteur qui ne
demarre pas doit echouer bruyamment, pas silencieusement.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

MODULES = ["commun", "archive_statique", "collecte_dynamique", "collecte_statique", "bilan"]
RACINE = Path(__file__).resolve().parent.parent


def main() -> int:
    erreurs = []
    for nom in MODULES:
        try:
            importlib.import_module(nom)
        except Exception as exc:                                  # noqa: BLE001
            erreurs.append(f"{nom} : {type(exc).__name__}: {exc}")

    # marqueurs de conflit oublies dans les donnees deja collectees
    base = RACINE / "data" / "collecte"
    if base.exists():
        for p in base.rglob("*.csv"):
            try:
                tete = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for ligne in tete.splitlines():
                if ligne.startswith(("<<<<<<< ", ">>>>>>> ")) or ligne == "=======":
                    erreurs.append(f"marqueur de conflit dans {p.relative_to(RACINE)}")
                    break

    if erreurs:
        for e in erreurs:
            print(f"ECHEC : {e}", file=sys.stderr)
        return 1
    print(f"verification ok : {len(MODULES)} modules importes, aucun marqueur de conflit")
    return 0


if __name__ == "__main__":
    sys.exit(main())
