# Profil des données (étape 1)

Projet `chargelab`. Livrable §9.1 de `SPEC-recharge-lab.md`.

Date de collecte : **jeudi 17 septembre 2026**, téléchargements entre 20:23 et 20:34 UTC.
Tous les fichiers cités sont archivés dans `data/raw/`, avec leur taille et leur
empreinte SHA-256 dans `data/raw/MANIFESTE.csv`. Tous les chiffres de ce document
sont reproductibles avec les scripts de `profiling/` et les fichiers JSON de
`data/profiling/`. Aucun chiffre n'est saisi à la main.

Environnement : Python 3.12.13, pandas 2.x, shapely 2.1.2, dans `.venv/`.

---

## 1. Ce qu'il faut retenir avant de lire le détail

Sept constats mesurés qui contredisent ou précisent les hypothèses de la spec.

| # | Constat | Chiffre |
|---|---|---|
| 1 | Le parc n'est pas de 227 000 points de charge. 227 000 est un **nombre de lignes** du fichier historique, qui contient des doublons. | **168 600** PDC distincts, **49 081** stations |
| 2 | Le champ `tarification` est renseigné pour un cinquième du parc, et la majorité de ce qui est renseigné n'est pas un prix. | renseigné **21,47 %** ; porteur d'un prix €/kWh **8,61 %** du parc |
| 3 | Les PDC porteurs d'un prix sont très concentrés. Une médiane nationale de prix serait la médiane des grilles de cinq réseaux. | 5 enseignes = **69,5 %** des PDC tarifés |
| 4 | Le flux dynamique ne couvre pas tout le parc, et une grande partie de ce qu'il couvre est périmée. | **60,5 %** du parc présent ; **32,3 %** du parc avec un état de moins de 24 h |
| 5 | Le taux « hors service » dépend entièrement du seuil de fraîcheur retenu. Ce n'est pas un détail de méthode, c'est le chiffre du bandeau. | **2,28 %** (< 6 h) à **8,06 %** (sans filtre) |
| 6 | `code_insee_commune` est vide pour un quart du parc. Le rattachement départemental doit passer par les coordonnées. | INSEE **73,38 %** ; coordonnées **99,78 %** |
| 7 | `date_mise_en_service` est vide pour près de la moitié du parc. La section « Le mur » ne peut pas décrire le parc entier. | renseignée **51,26 %** |

---

## 2. Sources : ce qui a été testé, ce qui a bougé

### 2.1 Résolution des pointeurs de la spec

L'URL de jeu de données donnée en §2.1 de la spec est valide mais n'est pas
adressable par l'API (`/api/datasets/<slug>` répond 404). Les ressources ont été
retrouvées par la liste complète `https://transport.data.gouv.fr/api/datasets`
(793 jeux de données), en filtrant sur `irve`. Deux jeux correspondent :

- `5448d3e0c751df01f85d0572` « Base nationale des IRVE » (ancien, schéma v2)
- `685965d0ab901919e14a4a1b` « [BETA] Base Nationale des Points de Recharge »

Le second est bien celui de la spec. Il expose six ressources :

| id | rôle | format | taille | nom de fichier servi |
|---|---|---|---|---|
| 84013 | statique **dédoublonnée** (`main`) | CSV | 120 699 563 o | `consolidation_transport_irve_statique.csv` |
| 84011 | statique **non dédoublonnée** | CSV | 289 741 892 o | `consolidation_transport_avec_doublons_irve_statique.csv` |
| 84098 | **dynamique** (`main`) | CSV | 8 938 455 o | `consolidation-nationale-irve-dynamique-<horodatage>.csv` |
| 84012 | rapport de consolidation | CSV | 641 139 o | `consolidation_transport_irve_statique_rapport.csv` |
| 84010 | liste des jeux prioritaires | YAML | redirige vers GitHub `etalab/transport-site` | `irve_prioritary_datasets.yml` |
| 84009 | suivi du projet | lien GitHub | n/a | n/a |

**Écart à la spec, documenté ici** : la spec ne mentionnait que la ressource
« non dédoublonnée ». La ressource **dédoublonnée** (84013) existe, elle est
marquée `main`, et elle porte une colonne `deduplication_status` qui explicite
la règle appliquée pour chaque ligne. Elle est retenue comme source principale
(voir §6).

Chaque téléchargement de la ressource 84098 renvoie un nom de fichier horodaté à
la seconde de la requête (`...-2026-09-17T20:23:12.715508Z.csv`). Le fichier est
donc **régénéré à la demande** : cet horodatage ne dit rien de la fraîcheur des
données, il ne peut pas servir de marqueur de rafraîchissement. La cadence réelle
est mesurée en §7 à partir du contenu.

### 2.2 Schémas

Les deux schémas sont accessibles en Table Schema JSON et sont tous deux en
**version 2.3.0**.

- statique : `https://schema.data.gouv.fr/schemas/etalab/schema-irve-statique/latest/schema-statique.json`, 40 champs, 23 406 octets
- dynamique : `https://schema.data.gouv.fr/schemas/etalab/schema-irve-dynamique/latest/schema-dynamique.json`, 8 champs, 7 988 octets

L'URL dynamique était donnée « à confirmer » dans la spec : elle est confirmée,
au format ci-dessus (la page `documentation.html` est la version lisible).

Le schéma dynamique impose `id_pdc_itinerance` au motif `^[A-Z]{2}[A-Z0-9]{4,33}$`,
`etat_pdc` dans `{en_service, hors_service, inconnu}`, `occupation_pdc` dans
`{libre, occupe, reserve, inconnu}`, `horodatage` en datetime. Les quatre champs
`etat_prise_type_*` sont facultatifs.

### 2.3 Fichier historique data.gouv (schéma v2)

`https://www.data.gouv.fr/fr/datasets/r/2729b192-40ab-4454-904d-735084dca3a3`
répond 200, 157 436 717 octets, 52 colonnes, **222 936 lignes**.
Il porte deux colonnes utiles absentes de la consolidation PAN :
`consolidated_code_postal` et `consolidated_commune`.
Il contient **166 829 PDC distincts** pour 222 936 lignes, soit 55 989 lignes en
doublon. Il sera supprimé au 31/12/2026 : à ne pas mettre dans le chemin critique.

---

## 3. Volumétrie et identifiants

| | PAN dédoublonné | PAN non dédoublonné | data.gouv v2 |
|---|---:|---:|---:|
| lignes | 168 602 | 396 878 | 222 936 |
| `id_pdc_itinerance` distincts | 168 600 | 168 947 | 166 829 |
| `id_station_itinerance` distincts | 49 081 | 56 885 | 54 334 |
| conformes au motif du schéma | 168 602 (100 %) | 395 859 (99,74 %) | 222 817 (99,95 %) |
| conformes eMI3 strict `FR` + 3 + `E|P` | 167 233 (99,19 %) | 393 263 | 221 458 |
| valeur littérale `Non concerné` | 0 | 1 019 | 119 |

Le fichier dédoublonné contient encore **2 lignes en doublon** d'identifiant
(168 602 lignes pour 168 600 identifiants).

Préfixes pays observés dans `id_pdc_itinerance` du fichier dédoublonné :
`FR` 168 169, `ES` 326, `BE` 40, `DK` 36, `IT` 11, `NL` 9, `AT` 7, `RE` 3, `CH` 1.
Soit **433 PDC hors France** (0,26 %), qui sont bien dans le fichier national.
Vérification croisée par les coordonnées : 149 PDC tombent hors de toute zone
française connue (exemples : `ESDRVEAGNW1` à 40,03 N / 4,43 O en Espagne,
`ITDRVEASWX1` à 43,49 N / 13,49 E en Italie).

1 369 identifiants (0,81 %) sont conformes au schéma mais pas au format eMI3
strict décrit dans la spec. Ils sont comptés, pas corrigés.

Stations : médiane de **2 PDC** par station, p90 = 6, maximum 505.
12 849 stations n'ont qu'un seul PDC, 2 493 en ont au moins dix.
Le champ `nbre_pdc` déclaré par la station est **cohérent avec le nombre de PDC
réellement listés pour 39 414 stations sur 49 081 (80,3 %)** ; il surestime pour
6 780 stations et sous-estime pour 2 887. Il ne doit donc pas servir de compteur.

277 stations portent plusieurs couples de coordonnées différents.

---

## 4. Validation contre les schémas

Script : `profiling/valider_schema.py`. Sortie : `data/profiling/validation-schema.json`.
Contrôles appliqués champ par champ : `required`, `enum`, `pattern`, type
numérique et borne minimale, booléen, date, datetime, geopoint.

| fichier | lignes | lignes avec au moins une violation | motifs |
|---|---:|---:|---|
| PAN dédoublonné | 168 602 | **0** | néant |
| PAN non dédoublonné | 396 878 | **4** (0,001 %) | `adresse_station` requis mais vide : 4 |
| dynamique (capture 20:23:12 UTC) | 121 513 | **0** | néant |

La consolidation PAN filtre donc déjà les lignes non conformes en amont. Le
rejet a lieu au niveau de la **ressource**, pas de la ligne, et il est documenté
dans le rapport de consolidation (ressource 84012), qui suit 1 837 ressources :

| statut de consolidation | ressources | PDC estimés |
|---|---:|---:|
| `already_up_to_date` | 1 446 | 314 373 |
| `producer_not_an_organization` | 179 | 5 665 |
| `file_level_errors` | 115 | 3 854 |
| `not_compliant_with_schema` | 41 | 12 198 |
| `import_successful` | 24 | 93 160 |
| (vide) | 32 | 9 096 |

**16 052 PDC estimés sont perdus** pour cause d'erreur de fichier ou de non
conformité au schéma, et **5 665** de plus parce que le producteur n'est pas une
organisation. La plus grosse ressource rejetée à elle seule représente 9 369 PDC
estimés (« Public charging stations for electric cars from several CPOs »,
`not_compliant_with_schema`).

Motifs d'erreur les plus fréquents, tels qu'écrits par le consolidateur :
`content has no id_pdc_itinerance in first line` (36), `looks like a v1 irve` (29),
colonne `prise_type_ef` introuvable (18), `the content is likely to be a zip file` (2).

Le champ `error_type` est vide sur les 1 837 lignes : seul `error_message` est
exploitable.

---

## 5. Taux de remplissage, colonne par colonne (PAN dédoublonné, n = 168 602)

Source : `data/profiling/pan_dedoublonne_2026-09-17.profil.json`.

| colonne | rempli | distincts | remarque |
|---|---:|---:|---|
| `nom_amenageur` | 99,18 % | 4 343 | |
| `siren_amenageur` | 65,18 % | 1 049 | |
| `contact_amenageur` | 68,56 % | 656 | |
| `nom_operateur` | 99,75 % | **278** | cardinalité exploitable |
| `contact_operateur` | 100,00 % | 255 | |
| `telephone_operateur` | 75,20 % | 482 | |
| `nom_enseigne` | 100,00 % | **6 286** | normalisation lourde à prévoir |
| `id_station_itinerance` | 100,00 % | 49 081 | |
| `id_station_local` | 78,65 % | 45 128 | |
| `nom_station` | 100,00 % | 40 792 | |
| `implantation_station` | 100,00 % | 5 | enum respectée |
| `adresse_station` | 100,00 % | 39 909 | |
| `code_insee_commune` | **73,38 %** | 9 495 | voir §8 |
| `coordonneesXY` | 100,00 % | 38 740 | |
| `nbre_pdc` | 100,00 % | 109 | non fiable, voir §3 |
| `id_pdc_itinerance` | 100,00 % | 168 600 | |
| `id_pdc_local` | 67,14 % | 112 606 | |
| `puissance_nominale` | 100,00 % | 264 | voir §9 |
| `prise_type_ef` | 100,00 % | 2 | vrai pour 46 633 |
| `prise_type_2` | 100,00 % | 2 | vrai pour 116 535 |
| `prise_type_combo_ccs` | 100,00 % | 2 | vrai pour 45 943 |
| `prise_type_chademo` | 100,00 % | 2 | vrai pour 7 279 |
| `prise_type_autre` | 100,00 % | 2 | vrai pour 3 149 |
| `gratuit` | 77,35 % | 2 | vrai pour **669** seulement |
| `paiement_acte` | 100,00 % | 2 | vrai pour 125 174 |
| `paiement_cb` | 90,85 % | 2 | vrai pour 47 180 |
| `paiement_autre` | 79,90 % | 2 | vrai pour 94 487 |
| `tarification` | **21,47 %** | 439 | voir §6 |
| `condition_acces` | 100,00 % | 2 | libre 148 320, réservé 20 282 |
| `reservation` | 100,00 % | 2 | vrai pour 20 694 |
| `horaires` | 100,00 % | 1 311 | `24/7` pour 143 510 (85,1 %) |
| `accessibilite_pmr` | 100,00 % | 4 | « inconnue » pour 107 037 (63,5 %) |
| `restriction_gabarit` | 100,00 % | 172 | texte libre, inexploitable en l'état |
| `station_deux_roues` | 100,00 % | 2 | vrai pour 5 348 |
| `raccordement` | 72,27 % | 2 | direct 88 689, indirect 33 164 |
| `num_pdl` | 59,88 % | 16 903 | |
| `date_mise_en_service` | **51,26 %** | 2 385 | voir §9 |
| `observations` | 20,73 % | 125 | |
| `date_maj` | 100,00 % | 1 097 | voir §9 |
| `cable_t2_attache` | **0,00 %** | 0 | **colonne entièrement vide** |
| `consolidated_longitude` | 100,00 % | 37 589 | |
| `consolidated_latitude` | 100,00 % | 37 132 | |
| `consolidated_is_lon_lat_correct` | 100,00 % | 2 | faux pour **26 810** (15,9 %) |
| `deduplication_status` | 100,00 % | 5 | voir §6 |

`restriction_gabarit` est nominalement obligatoire mais c'est du texte libre :
les valeurs les plus fréquentes sont « Restriction de gabarit non précisée »
(28 514), « inconnu » (23 802), « Aucune Restriction » (22 403), « xx » (13 994),
« NA » (5 303). Ce champ ne sera pas exploité.

---

## 6. Dédoublonnage

Le fichier non dédoublonné contient 168 947 PDC distincts répartis sur 396 878
lignes. **63 228 PDC (37,4 %)** apparaissent plus d'une fois, jusqu'à **257 fois**
pour le même identifiant.

Ce que les doublons se contredisent entre eux :

| champ | PDC en doublon en désaccord | part des PDC en doublon |
|---|---:|---:|
| `date_maj` | 55 352 | 87,5 % |
| `nom_enseigne` | 33 033 | 52,2 % |
| **`tarification`** | **21 703** | **34,3 %** |
| `puissance_nominale` | 5 535 | 8,8 % |

Un tiers des PDC en doublon déclarent **deux tarifications différentes** selon la
source. Le choix de la règle de dédoublonnage a donc un effet direct sur les prix.

La colonne `deduplication_status` expose la règle déjà appliquée par le PAN,
dans cet ordre de priorité, avec les effectifs sur le fichier non dédoublonné :

| statut | lignes |
|---|---:|
| `removed_because_not_in_prioritary_dataset` | 176 623 |
| `unique` | 105 719 |
| `kept_because_in_prioritary_dataset` | 52 397 |
| `removed_because_resource_not_more_recent` | 34 574 |
| `removed_because_date_maj_not_more_recent` | 15 154 |
| `kept_because_date_maj_more_recent` | 6 505 |
| `kept_because_resource_more_recent` | 3 878 |
| `removed_because_no_rule_applies` | 773 |
| `removed_because_exact_duplicate_in_same_file` | 133 |
| `kept_because_exact_duplicate_in_same_file` | 103 |

La règle est : jeu de données prioritaire d'abord, puis `date_maj` la plus
récente, puis ressource la plus récente. Elle est publiée (ressource 84010) et
reproductible. **228 276 lignes sont écartées, soit 226 912 doublons résolus.**

**347 PDC présents dans le fichier non dédoublonné sont absents du fichier
dédoublonné** (168 947 contre 168 600), ce qui correspond à l'ordre de grandeur
des 773 lignes `removed_because_no_rule_applies`. Ce point est à trancher en
étape 2 : soit on accepte cette perte de 0,21 %, soit on récupère ces PDC depuis
le fichier non dédoublonné avec une règle explicite.

---

## 7. Flux dynamique

### 7.1 Contenu d'une capture

Capture de référence : 2026-09-17 20:23:12 UTC, 8 938 441 octets, 1 567 299 octets
compressés, **121 513 lignes** pour **110 759 PDC distincts**.

| colonne | rempli | valeurs |
|---|---:|---|
| `id_pdc_itinerance` | 100 % | 110 759 distincts, 10 754 lignes en doublon |
| `etat_pdc` | 100 % | `en_service` 107 409, `hors_service` 9 560, `inconnu` 4 544 |
| `occupation_pdc` | 100 % | `libre` 99 887, `inconnu` 11 977, `occupe` 9 639, `reserve` 10 |
| `horodatage` | 100 % | 99 503 valeurs distinctes, 0 illisible |
| `etat_prise_type_2` | 27,36 % | fonctionnel 23 287, inconnu 9 122, hors service 841 |
| `etat_prise_type_combo_ccs` | 26,29 % | fonctionnel 21 097, inconnu 9 459, hors service 1 392 |
| `etat_prise_type_chademo` | 15,56 % | inconnu 10 461, fonctionnel 8 231, hors service 215 |
| `etat_prise_type_ef` | 16,31 % | fonctionnel 10 693, inconnu 8 875, hors service 245 |

**10 735 PDC apparaissent plusieurs fois dans la même capture, dont 1 574 avec
des `etat_pdc` contradictoires.** Une règle de résolution intra-capture est
nécessaire (proposition en étape 2 : garder la ligne au `horodatage` le plus
récent, ce que fait déjà le dépôt cité en §10).

### 7.2 Recouvrement avec le parc statique

| | PDC |
|---|---:|
| parc statique dédoublonné | 168 600 |
| PDC distincts dans le flux dynamique | 110 759 |
| intersection | **101 919 (60,45 % du parc)** |
| présents en dynamique, absents du statique | 8 840 |
| présents au statique, sans aucune donnée dynamique | **66 681 (39,55 %)** |

### 7.3 Fraîcheur de l'horodatage opérateur

Âge de `horodatage` au moment de la capture (17/09 20:23 UTC) :

| âge | lignes | part |
|---|---:|---:|
| < 1 h | 11 567 | 9,52 % |
| 1 à 6 h | 26 817 | 22,07 % |
| 6 à 24 h | 23 550 | 19,38 % |
| 1 à 3 j | 10 201 | 8,39 % |
| 3 à 7 j | 3 638 | 2,99 % |
| 7 à 30 j | 4 751 | 3,91 % |
| 30 à 90 j | 4 366 | 3,59 % |
| **> 90 j** | **36 623** | **30,14 %** |

Valeur la plus ancienne : 2020-12-29. Aucun horodatage dans le futur.

**Trente pour cent des lignes du flux « temps réel » portent un horodatage de
plus de trois mois.** Un `occupation_pdc = libre` daté de 94 jours n'est pas une
information sur aujourd'hui. Le croisement le confirme : sur les lignes de moins
de 24 h, 3,45 % sont `hors_service` ; sur les lignes plus anciennes, 12,46 %.

### 7.4 Conséquence directe sur le chiffre affiché

Taux de PDC hors service au 17/09 20:23 UTC, selon le seuil de fraîcheur retenu,
restreint aux PDC présents dans le parc statique :

| seuil | PDC retenus | part du parc | hors service | occupé | occupation inconnue |
|---|---:|---:|---:|---:|---:|
| horodatage < 6 h | 36 424 | 21,60 % | **2,28 %** | 13,18 % | 3,25 % |
| horodatage < 24 h | 54 435 | 32,29 % | **3,55 %** | 9,79 % | 5,20 % |
| horodatage < 72 h | 63 797 | 37,84 % | **3,90 %** | 8,73 % | 5,58 % |
| aucun filtre | 101 919 | 60,45 % | **8,06 %** | n/a | n/a |

L'écart entre 2,28 % et 8,06 % vient entièrement d'une règle de méthode. Le choix
du seuil doit être un ADR chiffré en étape 2 et il doit figurer dans la Méthode.

---

## 8. Cadence de rafraîchissement mesurée

### 8.1 Mesure de contrôle sur 24 h archivées par un tiers

Première mesure, faite le 17/09 sur une **journée déjà archivée** par le dépôt
`Valentinafry/irve-collecte` (voir §13), le **2026-08-20**, qui compte
**144 créneaux sur 144 attendus**, sans trou. Elle sert désormais de contrôle
de notre propre mesure (§8.2), avec laquelle elle est recoupée en §8.3.
Script : `profiling/cadence_24h.py`.

Ce dépôt appartient à un tiers et ne porte aucune licence. Les fichiers bruts
téléchargés pour cette mesure **ont été supprimés du projet** après calcul.
Seuls les agrégats par créneau sont conservés, dans
`data/profiling/cadence-24h-2026-08-20.csv`. Aucune donnée de ce dépôt n'entre
dans le projet.

Ces archives ne contiennent que les **changements** d'`etat_pdc` ou
d'`occupation_pdc` entre deux passages de 10 minutes, avec l'horodatage opérateur
et l'horodatage de collecte. Parc présent dans le flux ce jour-là : 103 759 PDC.

| indicateur | valeur |
|---|---|
| changements par créneau de 10 min | médiane **2 114**, p10 466, p90 4 104, min 326, max 4 457 |
| part du parc par créneau (médiane) | **2,04 %** |
| changements sur 24 h | 326 521, soit 3,15 par PDC |
| PDC ayant changé au moins une fois dans la journée | 44 173 (**42,6 %**) |
| PDC n'ayant jamais changé | 59 586 (**57,4 %**) |

Délai entre l'horodatage opérateur et la détection par la collecte :

| quantile | minutes |
|---|---:|
| p10 | 1,5 |
| p25 | 3,2 |
| **p50** | **6,0** |
| p75 | 8,7 |
| p90 | 10,3 |
| p99 | 34,0 |

**87,2 % des changements sont détectés moins de 10 minutes après l'horodatage
opérateur.** Autrement dit, le flux est publié quasiment en continu : le facteur
limitant est la cadence de collecte, pas la source.

Profil horaire, changements moyens par créneau de 10 minutes (UTC) :

```
00h   502   06h  1851   12h  3674   18h  2558
01h   554   07h  2386   13h  3760   19h  1950
02h   383   08h  3056   14h  3974   20h  1506
03h   409   09h  3745   15h  4110   21h  1155
04h   623   10h  4163   16h  4070   22h   867
05h  1084   11h  3945   17h  3461   23h   631
```

Rapport creux/pointe de 1 à 11 entre 02h et 10h UTC. Une cadence uniforme
sur-échantillonne la nuit et sous-échantillonne l'après-midi.

### 8.2 Mesure sur notre propre collecte, 24 h complètes

Collecte du **17/09 20:23 UTC au 18/09 23:24 UTC**, pas de 5 minutes, script
`collect/capture_dynamique.py`. Journal : `data/raw/journal_dynamique.csv`, une
ligne par sondage (horodatage, code HTTP, taille, SHA-256, en-têtes, chemin
d'archive, erreur). Résultats par intervalle : `data/profiling/cadence-propre-24h.csv`.

| | valeur |
|---|---|
| sondages tentés | 327 |
| captures réussies et archivées | **244** |
| sondages en échec | **83 (25,4 %)**, tous `URLError: nodename nor servname provided` |
| intervalles exploitables | 243, dont **239 de 5 minutes pleines** |
| créneaux de 5 minutes manqués | 83 |

Les 83 échecs sont des pertes de résolution DNS de la machine de collecte, pas
des erreurs du serveur : aucun sondage n'a reçu de code HTTP autre que 200. Ils
sont concentrés en deux blocs (08:40 à 08:50 et 15:10 à 19:55 UTC le 18/09).
**Un quart de créneaux perdus sur un poste de travail est en soi l'argument
principal pour externaliser le cron** (voir `docs/decisions.md`).

Sur les 239 intervalles de 5 minutes pleines :

| indicateur | médiane | p10 | p90 |
|---|---:|---:|---:|
| PDC dont l'horodatage opérateur a avancé | **1,39 %** | 0,87 % | 2,85 % |
| PDC dont l'état ou l'occupation a changé | **0,55 %** | 0,23 % | 1,85 % |

Parc présent dans le flux : min 110 759, médiane 110 766, max 110 777. Entrées et
sorties par intervalle : médiane 0, maximum 7 entrées et 5 sorties. **La
composition du flux est donc quasiment figée d'un créneau à l'autre.**

Profil horaire UTC, part du parc changeant d'état par créneau de 5 minutes :

```
00h 0,22 %   06h 1,21 %   12h 1,65 %   20h 0,49 %
01h 0,24 %   07h 1,30 %   13h 1,80 %   21h 0,37 %
02h 0,21 %   08h 1,44 %   14h 1,81 %   22h 0,34 %
03h 0,25 %   09h 1,62 %   15h 2,47 %   23h 0,25 %
04h 0,42 %   10h 1,89 %   (16h à 19h manquants, panne réseau)
05h 0,69 %   11h 1,81 %
```

Rapport creux/pointe de **1 à 9** entre 02h et 10h UTC.

### 8.3 Recoupement des deux mesures

Les deux mesures sont indépendantes (collecteurs différents, jours différents,
pas de 5 et de 10 minutes). Ramenées à la même base, changements par créneau de
10 minutes sur un parc de 110 766 PDC :

| h UTC | nous, 17 au 18/09 | archive tierce, 20/08 | écart |
|---|---:|---:|---:|
| 00h | 496 | 502 | -1,2 % |
| 01h | 537 | 554 | -3,1 % |
| 02h | 474 | 383 | +23,8 % |
| 03h | 545 | 409 | +33,3 % |
| 04h | 931 | 623 | +49,4 % |
| 05h | 1 532 | 1 084 | +41,3 % |
| 06h | 2 682 | 1 851 | +44,9 % |
| 07h | 2 880 | 2 386 | +20,7 % |
| 08h | 3 181 | 3 056 | +4,1 % |
| 09h | 3 598 | 3 745 | -3,9 % |
| 10h | 4 194 | 4 163 | +0,7 % |
| 11h | 4 008 | 3 945 | +1,6 % |
| 12h | 3 664 | 3 674 | -0,3 % |
| 13h | 3 977 | 3 760 | +5,8 % |
| 14h | 4 002 | 3 974 | +0,7 % |
| 15h | 5 478 | 4 110 | +33,3 % (1 seul intervalle chez nous) |
| 20h | 1 082 | 1 506 | -28,2 % |
| 21h | 826 | 1 155 | -28,5 % |
| 22h | 764 | 867 | -11,9 % |
| 23h | 560 | 631 | -11,2 % |

**Écart moyen sur les heures comparables : +7,2 %.** Les heures de pointe, qui
portent l'essentiel du volume, concordent à moins de 2 %. Les écarts en heures
creuses portent sur des effectifs faibles et sur un mois d'intervalle.

Une médiane brute des deux séries n'est pas comparable (1 263 changements par
créneau de 10 min chez nous contre 2 114 dans l'archive tierce) parce que notre
échantillon est déséquilibré par la panne réseau : il sur-représente la nuit.
Les extrêmes, eux, se superposent : minimum 312 contre 326, p90 3 775 contre
4 104, maximum 4 275 contre 4 457. **Les deux collectes mesurent la même chose.**

### 8.4 Ce que ces chiffres imposent

1. Le fichier servi n'est jamais identique d'une requête à l'autre : le hash du
   fichier complet ne peut pas servir de détecteur de changement. On compare
   ligne à ligne.
2. Le délai médian de 6 minutes entre horodatage opérateur et détection dit que
   **le facteur limitant est notre cadence, pas la source**.
3. Le rapport de 1 à 9 entre 02h et 10h UTC dit qu'une cadence uniforme
   sur-échantillonne la nuit d'un facteur 9.

---

## 9. Géographie

### 9.1 `code_insee_commune`

Rempli pour **123 713 PDC (73,38 %)**, vide pour 44 889. Aucune valeur non vide
n'enfreint le motif du schéma. 100 codes départementaux distincts, plus un
pseudo-code **`99` (104 PDC)** qui correspond à l'étranger.

Récupération des INSEE manquants par jointure sur `id_pdc_itinerance` avec le
fichier historique data.gouv : **3 484 PDC seulement** sont récupérables, dont
3 388 avec un code postal consolidé. Ce n'est pas une solution.

### 9.2 Rattachement par les coordonnées

`consolidated_longitude` et `consolidated_latitude` sont remplis à 100 %, pour
38 740 couples distincts. Test point dans polygone avec
`departements-avec-outre-mer.geojson` (france-geojson, dérivé d'Admin Express IGN,
Licence ouverte, 101 départements, 3 722 544 octets) :

| | PDC | part |
|---|---:|---:|
| rattachés à un département par les coordonnées | **168 224** | **99,78 %** |
| non rattachés | 378 | 0,22 % |
| gain net par rapport à INSEE seul | 44 711 | |

Là où les deux méthodes existent (123 513 PDC), elles sont **d'accord à 98,27 %**
(121 374 PDC) et en désaccord sur 2 139 PDC (1,73 %), qui sont soit des communes
limitrophes, soit des coordonnées fausses.

**Recommandation** : rattachement départemental par les coordonnées, INSEE en
contrôle, désaccords comptés et affichés.

### 9.3 Couverture territoriale réelle

Par les coordonnées, 100 départements sont représentés. Effectifs les plus faibles :

| département | PDC |
|---|---:|
| 973 Guyane | **2** |
| 972 Martinique | **34** |
| 971 Guadeloupe | **109** |
| 48 Lozère | 210 |
| 70 Haute-Saône | 315 |
| 90 Territoire de Belfort | 324 |
| 23 Creuse | 329 |
| 15 Cantal | 332 |
| 09 Ariège | 336 |
| 32 Gers | 336 |

- **Corse** : 2A = 544, 2B = 438. Les deux départements tiennent largement le
  seuil de 30. Par le code INSEE seul ils n'auraient eu que 161 et 133 PDC.
- **DOM** : 974 La Réunion 424, 971 Guadeloupe 109, 972 Martinique 34,
  973 Guyane 2, **976 Mayotte 0**. 975, 977, 978 absents.
- **COM** hors nomenclature départementale : Nouvelle-Calédonie 4,
  Polynésie française 30. Ils n'ont pas de code département dans le GeoJSON.
- **Hors France** : 149 PDC (Espagne, Italie, Belgique, Danemark, Pays-Bas...).

Classement par boîte englobante, avant point dans polygone : métropole 167 850,
DOM et COM 603, hors zones connues 149.

`consolidated_is_lon_lat_correct` est **faux pour 26 810 PDC (15,9 %)**. La
signification exacte de ce drapeau reste à établir avec le consolidateur ; il ne
s'agit pas d'une coordonnée absente puisque les deux colonnes sont remplies à 100 %.

---

## 10. Puissance et dates

### 10.1 `puissance_nominale`

Remplie à 100 %, toujours numérique, 264 valeurs distinctes.
Minimum 0, maximum **160 000**, ce qui est une confusion kW/W non corrigée à la
source. Quantiles : p1 = 0, p10 = 7,36, p25 = 22, **p50 = 22**, p75 = 50,
p90 = 200, p99 = 400.

- **2 748 PDC (1,63 %) à 0 kW**, 2 750 sous 1 kW.
- 458 PDC au-dessus de 400 kW.

Valeurs les plus fréquentes : 22 (63 464), 22,08 (14 635), 7,4 (13 249),
150 (8 022), 50 (6 975), 300 (6 838), 7 (6 695), 7,36 (4 899), 250 (3 999),
200 (3 440), 120 (3 164), 24 (2 851), 100 (2 796), **0 (2 748)**, 3,7 (2 692).

Répartition par classe de puissance de la spec :

| classe | PDC | part |
|---|---:|---:|
| AC ≤ 7 kW | 11 705 | 6,94 % |
| AC 7 à 22 kW (exclu) | 22 491 | 13,34 % |
| 22 à 50 kW (exclu) | **85 625** | **50,78 %** |
| 50 à 150 kW (exclu) | 15 144 | 8,98 % |
| ≥ 150 kW | 30 889 | 18,32 % |
| inconnue ou 0 | 2 748 | 1,63 % |

La classe « 22 à 50 » concentre la moitié du parc parce que 22 kW est la valeur
modale et que 22,08 kW l'accompagne. La frontière AC/DC de la spec est posée à
22 kW, mais le champ ne dit pas si un point est AC ou DC : il faudra le déduire
des types de prise (`prise_type_2` seul = AC probable, `combo_ccs` ou `chademo`
= DC). Point à trancher en étape 2.

### 10.2 `date_maj`

Remplie à 100 %, toujours lisible. Minimum 2012-09-10, maximum **2026-12-30**,
soit **56 dates dans le futur**.

| année | PDC | | année | PDC |
|---|---:|---|---|---:|
| 2012 | 1 | | 2022 | 2 577 |
| 2017 | 365 | | 2023 | 3 216 |
| 2018 | 28 | | 2024 | 6 069 |
| 2019 | 26 | | 2025 | 30 517 |
| 2020 | 176 | | **2026** | **124 240** |
| 2021 | 1 387 | | | |

**26,3 % du parc n'a pas été mis à jour en 2026.**

### 10.3 `date_mise_en_service`

Remplie pour **86 428 PDC (51,26 %)**, vide pour 82 174. Toujours lisible quand
elle est remplie. Minimum **1900-01-01** (4 PDC), maximum **2028-08-27** (1 PDC).

| année | PDC | | année | PDC |
|---|---:|---|---|---:|
| 1900 | 4 | | 2021 | 9 306 |
| 2002 | 1 | | 2022 | 11 323 |
| 2012 à 2016 | 501 | | 2023 | 15 825 |
| 2017 | 775 | | 2024 | 17 299 |
| 2018 | 297 | | 2025 | 18 237 |
| 2019 | 1 603 | | 2026 | 9 358 |
| 2020 | 1 898 | | 2028 | 1 |

La section « Le mur » (mises en service par semaine) ne peut donc décrire que la
moitié du parc, et le creux visible en 2018 est un artefact de déclaration, pas
un creux d'installation. Ce point doit être écrit dans la Méthode.

---

## 11. Le champ `tarification`

### 11.1 Inventaire brut

Fichier produit : **`docs/tarification-valeurs.csv`**, une ligne par valeur brute
distincte, avec nombre de PDC, part du parc, nombre de stations, nombre
d'enseignes, nombre de PDC dans le fichier non dédoublonné, longueur du texte.
Aucune normalisation n'est appliquée dans ce fichier.

| | valeur |
|---|---:|
| PDC total | 168 602 |
| `tarification` vide | **132 406 (78,53 %)** |
| `tarification` renseignée | **36 196 (21,47 %)** |
| valeurs distinctes non vides | **438** |

Les 438 valeurs ont été lues une par une avant toute écriture de motif.

### 11.2 Répartition par famille, avant tout calcul de prix

Script : `profiling/recensement_tarification.py`, sortie
`data/profiling/tarification-familles.csv`. Ce recensement est **descriptif** :
chaque famille est définie par un marqueur littéral observé dans les données, pas
par une heuristique de prix. Ce n'est pas encore le parseur de production.

| famille | PDC | % parc | % des renseignés | valeurs distinctes |
|---|---:|---:|---:|---:|
| `VIDE` | 132 406 | 78,53 % | | 0 |
| `RENVOI_TEXTE` | **14 134** | 8,38 % | **39,05 %** | 4 |
| `EXPORT_STRUCTURE` | 9 381 | 5,56 % | 25,92 % | 128 |
| `PRIX_KWH_LIBRE` | 5 068 | 3,01 % | 14,00 % | 220 |
| `NON_INFO_MOT_CLE` | 4 231 | 2,51 % | 11,69 % | 17 |
| `RENVOI_URL` | 2 748 | 1,63 % | 7,59 % | 10 |
| `NOMBRE_NU_SANS_UNITE` | 490 | 0,29 % | 1,35 % | 36 |
| `PRIX_TEMPS_SEUL` | 71 | 0,04 % | 0,20 % | 8 |
| `GRATUIT` | 42 | 0,02 % | 0,12 % | 2 |
| `JSON_OPERATEUR` | 18 | 0,01 % | 0,05 % | 6 |
| `AUTRE_NON_CLASSE` | 13 | 0,01 % | 0,04 % | 7 |

Correspondance avec les codes de la spec §4.3 : `RENVOI_TEXTE`, `RENVOI_URL` et
`NON_INFO_MOT_CLE` relèvent de `RENVOI`, `VIDE` de `VIDE`, `NOMBRE_NU_SANS_UNITE`
et `AUTRE_NON_CLASSE` de `INCONNU`, `PRIX_TEMPS_SEUL` de `MIN`,
`EXPORT_STRUCTURE`, `PRIX_KWH_LIBRE` et `JSON_OPERATEUR` de `KWH` ou `MIXTE`.

**58,33 % de ce qui est renseigné n'est pas un prix.** La valeur la plus fréquente
du fichier, à elle seule 10 340 PDC soit 28,6 % des valeurs renseignées, est ce
texte, qui ne contient aucun chiffre :

> « Les tarifs de recharge peuvent varier en fonction de plusieurs facteurs, y
> compris le fournisseur de services, l'emplacement de la borne, la puissance de
> charge, et les éventuelles promotions en cours. Il est recommandé de consulter
> directement les informations tarifaires auprès du gestionnaire de la borne ou
> via l'application mobile associée pour obtenir les détails les plus récents et
> précis. »

Les deuxième et troisième formulations de renvoi les plus fréquentes sont
« Tarification au kWh plus frais de connexion éventuelles en fonction de l
abonnement détenu » (2 594 PDC) et sa variante avec apostrophe et mention du
roaming (1 037 + 163 PDC).

### 11.3 Les familles qui portent réellement un prix €/kWh

| famille | PDC |
|---|---:|
| `EXPORT_STRUCTURE` | 9 381 |
| `PRIX_KWH_LIBRE` | 5 068 |
| `GRATUIT` | 42 |
| `JSON_OPERATEUR` | 18 |
| **total** | **14 509, soit 8,61 % du parc** |

`EXPORT_STRUCTURE` est un export machine, très régulier, de la forme :

```
entre 08:00 et 20:00 : 0.30916667€ par kwh de charge, 3.75€ par heure
d'occupation hors charge, entre 20:00 et 08:00 : 0.30916667€ par kwh de charge...
```
```
par défaut : 0.4667€ par kwh de charge, par défaut : 6.6667€ par heure
d'occupation hors charge, 6.6667€ par heure de charge...
```

Il porte à la fois un prix au kWh, un prix horaire de charge et un prix
d'occupation hors charge, parfois différenciés par plage horaire, souvent
répétés. C'est la famille la plus fiable à parser, et aussi celle qui impose de
choisir quoi garder (le kWh « par défaut », ou par plage horaire).

`PRIX_KWH_LIBRE` est du texte humain, 220 formes pour 5 068 PDC :
`AC 36cts/KWh`, `0,29€ / kWh`, `59 cts/kWh`, `0.45€TTC/kWh`, `0,55€KWH HT`,
`0,35€/kWh + 0,03€/min entre 6h et 18h, 15€ la session entre 18h et 6h`,
`Price per kWh (billed per 1 Wh): 0.5190 EUR`, `0,35cts/KWH HT`...

`JSON_OPERATEUR` est un blob JSON avec un champ `energyPrice` directement lisible.

### 11.4 Pièges relevés à la lecture, à traiter explicitement

- **Booléens fuités dans le champ texte** : `TRUE` (171 PDC), `true` (63),
  `false` (4), `null` (9). Ce sont probablement des `gratuit` mal mappés.
- **Nombres nus sans unité** : `0.4583`, `0,22`, `0.39`, `0`, `15`, `050 kWh`,
  `5€`, `1,23€`. 490 PDC. Rien ne dit que l'unité est le kWh. À classer `INCONNU`.
- **Ambiguïté « cts »** : `0,35cts/KWh`, `0,40cts/KWh`, `0,60cts/KWh TTC`.
  Lu littéralement cela ferait 0,0035 €/kWh. C'est une écriture fautive de
  0,35 €/kWh. Ne pas deviner : classer `INCONNU` et compter.
- **HT explicite** : `0,55€KWH HT`, `0,42 € HT / kWh`, `1,25€/KWH HT`,
  `0.21€/kWh HTVA pour l'itinérance`. La spec impose de supposer TTC quand ce
  n'est pas précisé ; ici c'est précisé et c'est du HT. Il faudra soit convertir
  avec un taux déclaré, soit exclure, soit afficher à part.
- **Valeurs hors bornes de plausibilité [0,05 ; 1,50] €/kWh** :
  `2.5€ à la connexion et 2€/Kwh`, `AC 1€/kWh - DC 5€/kWh`, `2 AC- DC €/kWh`,
  `0,0417€/kWh entre 6h et 21h`, `0.98/kW`. À classer `INCONNU` et compter.
- **Mojibake UTF-8 doublement encodé** : 3 valeurs, 44 PDC
  (`0,55 â‚¬/ kwh`, `1â‚¬/kWh`, `2,09 â‚¬HT/h`).
- **Retours à la ligne dans la valeur** : plusieurs valeurs contiennent des sauts
  de ligne (`lorsque la voitutre est branché:\n on applique 0.32€/Kwh...`).
  Le lecteur CSV doit les gérer, `wc -l` ne donne pas le nombre de lignes.
- **Prix au kW et non au kWh** : `0.32€ / kW`, `0.35€ /kW`, `0.36€ AC /KW`,
  `0.50€ /kW`, `0.98/kW`. Faute d'unité fréquente ; à traiter comme kWh ou à
  exclure, décision à documenter.
- **Tarifs différenciés AC/DC dans la même chaîne** : `AC 36cts/KWh`,
  `HPC 49cts/Kwh`, `0.30€/kwh + 0.025€/min pour point 22AC - 0.50€/kwh +
  0.025€/min pour point de charge 50DC`. La structure doit être conservée.
- **Fautes de frappe conservées** : `voitutre`, `traif`, `Aprè`, `0;10€/min`,
  `2.5€ par heure ,'occupation hors charge`.

### 11.5 Effectifs disponibles pour une médiane de prix

Nombre de PDC porteurs d'un prix, par classe de puissance :

| classe | parc | candidats | couverture |
|---|---:|---:|---:|
| AC ≤ 7 kW | 11 705 | **85** | 0,73 % |
| AC 7 à 22 kW | 22 491 | **266** | 1,18 % |
| 22 à 50 kW | 85 625 | 10 606 | 12,39 % |
| 50 à 150 kW | 15 144 | 1 889 | 12,47 % |
| ≥ 150 kW | 30 889 | 1 604 | 5,19 % |
| inconnue ou 0 | 2 748 | 59 | 2,15 % |

Concentration des 14 509 candidats : **397 enseignes, 80 opérateurs**, mais

| enseigne | PDC candidats |
|---|---:|
| eborn | 3 650 |
| CPO CITEOS Mobive | 2 534 |
| Carrefour Energies | 1 571 |
| Easy Charge Services | 1 505 |
| CPO CITEOS Region-Bfc | 823 |
| LIDL | 739 |
| CPO CITEOS SMOYS | 345 |
| CPO CITEOS Vaucluse | 248 |
| GreenToWheel | 239 |
| ALLEGO | 235 |

**Les 5 premières enseignes portent 69,5 % des PDC tarifés, les 10 premières
81,9 %.** Une « médiane nationale du prix de la recharge » calculée là-dessus
serait la médiane des grilles tarifaires d'une poignée de réseaux, dont trois
entités CITEOS et deux enseignes de grande distribution. Elle ne mesurerait pas
le marché.

Par département (rattachement INSEE seul, à recalculer par coordonnées) :
97 départements ont au moins un candidat, **76 en ont au moins 30**, 44 en ont au
moins 100.

**Conclusion de mesure, à acter en étape 2** : la condition posée au §1 de la spec
(« si la couverture du champ `tarification` est trop faible pour produire une
médiane fiable au niveau national ») est remplie. Deux classes de puissance sur
cinq sont sous le seuil de 30 PDC dès le niveau national. La section prix doit
devenir « Ce que les opérateurs déclarent », avec la couverture en gros, et sans
médiane nationale toutes classes confondues.

---

## 12. Enseignes et opérateurs

- `nom_enseigne` : **6 286 valeurs distinctes** pour 168 602 PDC.
- `nom_operateur` : **278 valeurs distinctes**, rempli à 99,75 %.
- Préfixe eMI3 opérateur (5 premiers caractères de `id_pdc_itinerance`) :
  **281 valeurs distinctes**.

Les trois cardinalités disent la même chose : `nom_enseigne` est du texte libre
saisi par le producteur, `nom_operateur` et le préfixe eMI3 sont des référentiels.

Premières enseignes par nombre de PDC : Freshmile France 15 035,
Power Dot France 7 662, Réseau de recharge du groupe Indigo 7 649,
Lidl France 5 127, Tesla 4 805, ENGIE Vianeo 4 219, QOVOLTIS 3 793,
DRIVECO 3 673, eborn 3 650, ALDI 3 068.

Premiers opérateurs : Bouygues Energies & Services 14 194, IZIVIA 11 871,
Freshmile | FR*FR1 9 438, Power Dot France 7 662, GROUPE INDIGO 7 649,
TotalEnergies Marketing France 6 329, EASYCHARGE 5 278, Lidl France 5 127,
Allego 4 954, Tesla 4 805.

Les doublons de graphie sont visibles dès le sommet de la liste : `IZIVIA` et
`Izivia` (11 871 et 2 869), `TotalEnergies Marketing France` /
`TotalEnergies Charging Services` / `TotalEnergies Charge Rapide` /
`TotalEnergies - Metpark`, `ALDI` et `ALDI SARL`, `LIDL` et `Lidl France`.
Le préfixe eMI3 tranche ces cas sans arbitrage manuel : **281 préfixes contre
6 286 libellés**. `build/enseignes.yml` devra partir du préfixe et non du libellé.

---

## 13. Sources secondaires vérifiées

| source | testé | verdict |
|---|---|---|
| `Valentinafry/irve-collecte` | API GitHub, arbre complet, un jour téléchargé le 17/09 puis supprimé | **Écarté.** Dépôt tiers, **aucun fichier LICENSE**, collecte arrêtée depuis le 01/09 à 09:40 UTC. Méthode voisine de la nôtre (10 min effectives, compaction par changement d'état, horodatage opérateur conservé), historique continu du 2026-08-12 au 2026-09-01. Il a servi une seule fois, comme mesure de contrôle de la cadence (§8.1), avant recoupement avec notre propre collecte (§8.3). Les fichiers bruts ont été supprimés du projet, seuls les agrégats par créneau sont conservés. **Aucun backfill n'en est tiré : l'historique du projet commence le 2026-09-17.** |
| ODRÉ `bornes-irve` | API Explore v2.1, 200 | Miroir du fichier historique data.gouv, **227 007 enregistrements**. C'est de là que vient le chiffre de 227 000 de la spec : c'est un nombre de lignes avec doublons, pas un nombre de PDC. Porte un champ `departement` déjà calculé. Contrôle croisé uniquement. |
| `france-geojson` départements avec outre-mer | téléchargé, 101 entités | **Retenu.** Licence ouverte, dérivé d'Admin Express IGN. 3 722 544 octets en version pleine, 569 299 octets en version simplifiée métropole seule. Une version simplifiée incluant l'outre-mer devra être produite au build pour tenir le budget. |
| `geo.api.gouv.fr` départements | 200, 101 départements | Référentiel code/nom/région. **Le champ `population` n'est plus servi au niveau département** (renvoie vide). |
| `geo.api.gouv.fr` communes | 200 | Population disponible au niveau commune (Paris 2 103 778). Agrégeable par département en 101 requêtes au build, à mettre en cache. |
| INSEE populations légales | non testé | À faire en étape 2 si l'agrégation communale ne suffit pas. |
| RTE / éCO2mix, Tempo, TRV CRE | non testé | Section « Le socle » optionnelle, hors périmètre de l'étape 1. |

---

## 14. Budget : premières mesures

Mesures réelles, pas des estimations, sur les 49 081 stations du fichier
dédoublonné (latitude et longitude seules) :

| encodage | brut | gzip niveau 9 |
|---|---:|---:|
| JSON compact, 4 décimales | 0,83 Mo | **0,25 Mo** |
| `Float32Array` binaire | 0,39 Mo | **0,27 Mo** |
| entiers 32 bits quantifiés au millième de degré | 0,39 Mo | **0,18 Mo** |

La géométrie de la carte au niveau station tient donc dans 0,2 à 0,3 Mo
compressés. Le budget de 4 Mo de la spec n'est pas menacé par la carte. Les
postes lourds seront les séries temporelles jour × département × classe et les
contours départementaux (3,7 Mo bruts avant simplification, à ramener sous
0,3 Mo). Chiffrage complet en étape 4.

---

## 15. Ce que je n'ai pas pu faire, et pourquoi

1. ~~La mesure de cadence sur 24 h avec notre propre collecteur.~~ **Fait.**
   Collecte du 17/09 20:23 au 18/09 23:24 UTC, 244 captures, résultats en §8.2
   et recoupement avec la mesure de contrôle en §8.3. Réserve : 83 sondages sur
   327 ont échoué par perte de DNS de la machine de collecte, ce qui laisse un
   trou de 16h à 19h UTC le 18/09. Les heures de pointe 08h à 15h sont couvertes.
2. **La signification exacte de `consolidated_is_lon_lat_correct`** (faux pour
   15,9 % du parc). Elle n'est pas documentée dans le schéma. Il faudra soit lire
   le code du consolidateur, soit poser la question au PAN.
3. **La distinction AC/DC.** Aucun champ ne la porte. Elle devra être déduite des
   types de prise et de la puissance, avec une règle documentée et un compte des
   cas ambigus.
4. **La validation par Validata en ligne.** La validation a été faite localement
   contre le Table Schema (§4), ce qui donne le même résultat sur les contraintes
   exprimées dans le schéma. Les contrôles supplémentaires propres à Validata
   (unicité, cohérence inter-champs) n'ont pas été rejoués.
5. **Le contenu des jeux de données prioritaires** (ressource 84010) n'a pas été
   analysé jeu par jeu. Le fait que la règle de dédoublonnage s'y appuie est
   acquis, la liste exacte sera nécessaire en étape 2 si nous reprenons la règle.
6. **La licence du dépôt `irve-collecte`** est absente. Tant qu'elle n'est pas
   établie, l'historique du 12/08 au 01/09 est cité comme mesure, pas intégré
   comme donnée du projet.

---

## 16. Fichiers produits par cette étape

| fichier | contenu |
|---|---|
| `docs/tarification-valeurs.csv` | 439 lignes, inventaire exhaustif des valeurs brutes de `tarification` |
| `docs/data-profile.md` | ce document |
| `data/raw/MANIFESTE.csv` | taille et SHA-256 des fichiers sources téléchargés |
| `data/raw/journal_dynamique.csv` | journal de collecte, une ligne par sondage |
| `data/profiling/*.profil.json` | profil colonne par colonne des trois fichiers statiques |
| `data/profiling/validation-schema.json` | violations de schéma par motif |
| `data/profiling/tarification-familles.csv` | recensement des familles de tarification |
| `data/profiling/pdc_departement_2026-09-17.csv` | département calculé par point dans polygone, par PDC |
| `data/profiling/cadence-propre-24h.csv` | cadence par intervalle sur notre collecte, 243 lignes |
| `data/profiling/cadence-24h-2026-08-20.csv` | agrégats par créneau de la mesure de contrôle, 144 lignes |
| `profiling/profil_statique.py` | profilage générique d'un fichier statique |
| `profiling/valider_schema.py` | validation locale contre Table Schema |
| `profiling/extraire_tarification.py` | production de l'inventaire de tarification |
| `profiling/recensement_tarification.py` | recensement descriptif des familles |
| `profiling/cadence_dynamique.py` | cadence mesurée sur nos propres captures |
| `profiling/cadence_24h.py` | cadence de contrôle sur 24 h archivées par un tiers, non rejouable |
| `profiling/cadence_propre_24h.py` | cadence mesurée sur notre propre collecte |
| `collect/capture_dynamique.py` | collecteur du flux dynamique |

Licence des données : Licence Ouverte / Etalab v2.0.
Source : Point d'Accès National transport.data.gouv.fr, consolidation beta IRVE.
