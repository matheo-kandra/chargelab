#!/usr/bin/env bash
# Lance toutes les suites et mesure la couverture des fonctions de calcul.
# La spec exige 100 % sur build/statistiques.py : le script echoue en dessous.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
PY=${PYTHON:-.venv/bin/python}
code=0

echo "=== parsing de tarification ==="
"$PY" tests/test_tarification.py || code=1

echo
echo "=== fonctions de calcul ==="
"$PY" -m coverage run --source=build.statistiques tests/test_statistiques.py || code=1
"$PY" -m coverage report -m --fail-under=100 || { echo "couverture insuffisante" >&2; code=1; }

echo
echo "=== sante des collecteurs ==="
"$PY" collect/verifier.py || code=1

exit $code
