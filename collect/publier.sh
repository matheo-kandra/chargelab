#!/usr/bin/env bash
# Valide les fichiers produits par un passage de collecte.
#
# Le premier argument est le message de commit, les suivants sont les chemins a
# publier. On ne passe JAMAIS `data/collecte` en entier : les workflows
# utilisent un sparse-checkout partiel, et un `git add` sur un chemin absent du
# cone risquerait d'indexer la suppression des fichiers de l'autre collecteur.
#
# Le depot est ecrit par deux workflows : en cas de course, on rejoue le commit
# sur la tete distante plutot que d'ecraser.
set -uo pipefail
message="${1:?message de commit attendu}"
shift
chemins=("$@")
if [ ${#chemins[@]} -eq 0 ]; then
  echo "aucun chemin a publier" >&2
  exit 2
fi

git config user.name  "collecte-chargelab"
git config user.email "collecte@users.noreply.github.com"

git add -A -- "${chemins[@]}"
if git diff --cached --quiet; then
  echo "rien a publier"
  exit 0
fi

echo "fichiers indexes :"
git diff --cached --name-status

horodatage="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
git commit -q -m "${message} ${horodatage}"

branche="${GITHUB_REF_NAME:-main}"
for essai in 1 2 3 4 5; do
  if git push -q origin "HEAD:${branche}" 2>/dev/null; then
    echo "publie (essai ${essai})"
    exit 0
  fi
  echo "conflit de publication, essai ${essai}"
  git fetch -q origin "${branche}" || true
  if ! git rebase -q "origin/${branche}"; then
    git rebase --abort || true
  fi
  sleep $((essai * 4))
done

echo "publication impossible apres 5 essais" >&2
exit 1
