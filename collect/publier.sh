#!/usr/bin/env bash
# Valide les fichiers produits par un passage de collecte.
# Le depot est ecrit par plusieurs workflows : en cas de course, on rejoue le
# commit sur la tete distante plutot que d'ecraser. Un echec de publication est
# journalise comme tel, il ne fait pas echouer la capture deja archivee.
set -uo pipefail
message="${1:-collecte}"

git config user.name  "collecte-chargelab"
git config user.email "collecte@users.noreply.github.com"

git add -A data/collecte
if git diff --cached --quiet; then
  echo "rien a publier"
  exit 0
fi

horodatage="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
git commit -q -m "${message} ${horodatage}"

for essai in 1 2 3 4 5; do
  if git push -q origin HEAD 2>/dev/null; then
    echo "publie (essai ${essai})"
    exit 0
  fi
  echo "conflit de publication, essai ${essai}"
  git fetch -q origin "${GITHUB_REF_NAME:-main}" || true
  git rebase -q "origin/${GITHUB_REF_NAME:-main}" || { git rebase --abort || true; sleep $((essai * 5)); continue; }
  sleep $((essai * 3))
done

echo "publication impossible apres 5 essais" >&2
exit 1
