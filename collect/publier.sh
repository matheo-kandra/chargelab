#!/usr/bin/env bash
# Valide les fichiers produits par un passage de collecte.
#
# Le premier argument est le message de commit, les suivants sont les chemins a
# publier. On ne passe JAMAIS `data/collecte` en entier : les workflows
# utilisent un sparse-checkout partiel, et un `git add` sur un chemin absent du
# cone risquerait d'indexer la suppression des fichiers de l'autre collecteur.
#
# Le depot peut etre ecrit par plusieurs collecteurs. En cas de course, on
# rejoue le commit sur la tete distante. Les journaux sont fusionnes en union
# (voir .gitattributes) : deux lignes ajoutees au meme creneau sont conservees
# toutes les deux. Avant tout commit, on refuse un fichier contenant des
# marqueurs de conflit : un rebase avorte laisse un arbre sale, et sans ce
# garde-fou le passage suivant committerait le fichier abime.
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
git config merge.union.driver "git merge-file --union %A %O %B" 2>/dev/null || true

marqueurs() {
  grep -rlE '^(<<<<<<< |=======$|>>>>>>> )' -- "${chemins[@]}" 2>/dev/null
}

sales="$(marqueurs)"
if [ -n "$sales" ]; then
  echo "REFUS : marqueurs de conflit dans :" >&2
  echo "$sales" >&2
  exit 3
fi

git add -A -- "${chemins[@]}"
if git diff --cached --quiet; then
  echo "rien a publier"
  exit 0
fi

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
  if git rebase -q "origin/${branche}"; then
    sales="$(marqueurs)"
    if [ -n "$sales" ]; then
      echo "REFUS apres rebase : marqueurs de conflit dans $sales" >&2
      git reset -q --hard "origin/${branche}"
      exit 3
    fi
  else
    git rebase --abort 2>/dev/null || git rebase --quit 2>/dev/null || true
    git reset -q --hard HEAD
  fi
  sleep $((essai * 4))
done

echo "publication impossible apres 5 essais" >&2
exit 1
