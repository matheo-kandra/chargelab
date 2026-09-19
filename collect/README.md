# `collect/` : collecte et historisation

Trois scripts, deux workflows, deux journaux. Tout ce qui est collecté est
archivé brut ou reconstructible à l'octet près ; rien n'est lissé, rien n'est
reconstruit après coup.

## Scripts

| fichier | rôle |
|---|---|
| `commun.py` | téléchargement avec reprise, écriture gzip déterministe, journalisation, résolution des doublons intra-capture (ADR 11) |
| `collecte_dynamique.py` | capture du flux dynamique, archivage des seuls changements d'état |
| `collecte_statique.py` | téléchargement quotidien du fichier statique, archivage compact, vérification de la reconstruction |
| `archive_statique.py` | schéma d'archivage compact et reconstruction exacte (ADR 10) |
| `publier.sh` | commit et push, avec reprise sur conflit |

## Cadence

Mesurée, pas supposée (`docs/data-profile.md` §8, `docs/decisions.md` ADR 08) :
la part du parc qui change d'état passe de 0,21 % par créneau de 5 minutes à
02h UTC à 1,89 % à 10h UTC, soit un rapport de 1 à 9.

- **dynamique** : toutes les 5 minutes de 06:00 à 20:00 UTC, toutes les
  15 minutes sinon, soit 208 passages par jour.
- **statique** : une fois par jour à 03:10 UTC.

GitHub décale fréquemment les déclenchements planifiés. La cadence réellement
obtenue se lit dans le journal, elle n'est jamais supposée.

## Ce qui est archivé

```
data/collecte/
  dynamique/
    instantanes/AAAA-MM-JJ.csv.gz        photo complète, une par jour (1,5 Mo)
    changements/AAAA/MM/AAAA-MM-JJ_HHMMSS.csv.gz
                                         uniquement les PDC dont etat_pdc ou
                                         occupation_pdc a changé, avec
                                         l'horodatage opérateur ET celui de capture
  statique/
    complet/AAAA-MM-JJ.csv.gz            photo complète, le lundi (6,3 Mo)
    diff/AAAA-MM-JJ.csv.gz               lignes ajoutées ou dont un champ de
                                         contenu a changé (28 ko environ)
    date_maj/AAAA-MM-JJ.csv.gz           lignes dont seuls date_maj et
                                         datagouv_last_modified ont bougé (141 ko)
    sorties/AAAA-MM-JJ.csv               clés disparues ce jour-là
  journal/
    dynamique.csv                        une ligne par passage, réussi ou non
    statique.csv                         une ligne par jour, réussi ou non
```

Il n'y a **pas de fichier d'état** pour le dynamique : l'état connu est
reconstitué à chaque passage depuis la dernière photo et les fichiers de
changements postérieurs. Un fichier d'état de 1,5 Mo réécrit 208 fois par jour
ferait enfler le dépôt de 312 Mo par jour pour une information déjà présente.

## Vérification de la reconstruction

`collecte_statique.py` reconstruit le jour qu'il vient d'archiver et compare
l'empreinte SHA-256 de la sérialisation canonique à celle du fichier téléchargé.
Si les deux diffèrent, le passage échoue et rien n'est considéré comme archivé.
Vérifié sur données réelles les 17 et 19 septembre 2026 : reconstruction exacte,
6,26 Mo pour la photo complète, 0,31 Mo pour le journal de deux jours.

## Colonnes des journaux

`dynamique.csv` : `capture_utc`, `resultat`, `octets`, `sha256`, `lignes_flux`,
`pdc_distincts`, `doublons_resolus`, `etats_contradictoires`, `etat_reference`,
`changements`, `entrees`, `sorties`, `photo_du_jour`, `duree_s`, `erreur`.

`statique.csv` : `collecte_utc`, `jour`, `resultat`, `octets`,
`sha256_telechargement`, `lignes`, `pdc_distincts`, `mode`, `octets_archives`,
`entrees`, `sorties`, `contenu_modifie`, `date_maj_seule`, `verification`,
`sha256_canonique`, `duree_s`, `erreur`, plus les colonnes d'audit du
dédoublonnage le lundi.

Un passage en échec est un créneau manqué : il est écrit dans le journal avec
son motif, et il reste manquant. Il n'est jamais reconstruit.

## Exécution locale

```bash
pip install -r collect/requirements.txt
python collect/collecte_dynamique.py
python collect/collecte_statique.py
```

Les scripts écrivent dans `data/collecte/` à la racine du dépôt, où qu'ils
soient lancés depuis.
