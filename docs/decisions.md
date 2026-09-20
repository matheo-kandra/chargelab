# Décisions de méthode (étape 2)

Projet `chargelab`. Livrable §9.2 de `SPEC-recharge-lab.md`.
Format ADR court : contexte, décision, chiffres qui la justifient, conséquence.

Chaque décision s'appuie sur une mesure de `docs/data-profile.md` ou sur une
mesure faite pour cette étape et consignée dans `data/profiling/`. Les décisions
qui **s'écartent de la spec** sont signalées par « **Écart à la spec** » avec la
raison chiffrée, comme exigé.

État au 19 septembre 2026. Les ADR marqués « provisoire » seront revus quand
l'historique le permettra, avec la date de revue indiquée.

---

## ADR 01. Source statique : consolidation PAN dédoublonnée

**Contexte.** La spec ne citait que la ressource « statique non dédoublonnée »
(84011). La ressource dédoublonnée (84013) existe, elle est marquée `main` et
porte une colonne `deduplication_status` qui explicite la règle ligne par ligne.

**Décision.** Source principale = ressource **84013**. La ressource 84011 est
téléchargée et conservée le même jour, uniquement pour auditer le dédoublonnage
et récupérer les PDC perdus (ADR 02).

**Chiffres.** 168 600 PDC distincts contre 168 947 dans le non dédoublonné.
37,4 % des PDC apparaissent plus d'une fois dans le non dédoublonné, jusqu'à
257 fois. Refaire nous-mêmes le dédoublonnage supposerait de reconstituer la
liste des jeux prioritaires ; la règle du PAN est publiée (ressource 84010),
appliquée en amont et vérifiable a posteriori via `deduplication_status`.
226 912 lignes en doublon sont résolues par cette règle.

**Conséquence.** La règle de dédoublonnage du projet est celle du PAN :
jeu de données prioritaire, puis `date_maj` la plus récente, puis ressource la
plus récente. Le build en journalise la répartition à chaque édition.

---

## ADR 02. Récupération des 347 PDC perdus par le dédoublonnage

**Contexte.** 347 PDC présents dans le fichier non dédoublonné sont absents du
fichier dédoublonné : toutes leurs occurrences portent un statut `removed_*`,
aucune un statut `kept_*`. C'est un défaut du consolidateur, pas une règle.

**Chiffres.** 347 PDC pour 3 023 lignes, soit 0,21 % du parc. Statuts :
`removed_because_resource_not_more_recent` 2 213,
`removed_because_no_rule_applies` 707,
`removed_because_date_maj_not_more_recent` 103. Ils se concentrent sur cinq
producteurs (Mobilize Power Solutions 1 694 lignes, Car2Plug 561,
Sorel Energies 446, Dream Energy 70).

**Décision.** Les récupérer depuis le fichier non dédoublonné en gardant la
ligne au `date_maj` le plus récent, puis, à égalité, la première dans l'ordre du
fichier. Les compter séparément et afficher le nombre dans la Méthode.

**Conséquence.** Parc de travail = 168 600 + 347 = **168 947 PDC** au 17/09.
Ne jamais corriger en silence : le compteur « PDC récupérés hors consolidation »
est un chiffre publié.

---

## ADR 03. Identifiants : ce qu'on garde, ce qu'on exclut

**Décision.** Le pivot est `id_pdc_itinerance`. Sont **exclus et comptés** :

| cas | règle | effectif au 17/09 |
|---|---|---|
| valeur littérale `Non concerné` | exclu | 0 au dédoublonné, 1 019 au non dédoublonné |
| préfixe pays différent de `FR` | exclu du parc France, compté | 433 (0,26 %) |
| non conforme au motif du schéma | exclu | 0 au dédoublonné |
| conforme au schéma mais pas au format eMI3 strict (`FR` + 3 + `E` ou `P`) | **conservé**, compté | 1 369 (0,81 %) |

**Justification du dernier cas.** 1 369 PDC, soit 0,81 %, sont conformes au
schéma publié mais pas à la convention eMI3 décrite dans la spec. Le schéma fait
foi : les exclure reviendrait à appliquer une règle plus stricte que la source.
Ils sont comptés et le compteur figure dans la Méthode.

**Écart à la spec.** La spec §2.1 dit « les identifiants non conformes sont
comptés et exclus ». Nous conservons ceux qui sont conformes au schéma. Raison
chiffrée : l'exclusion coûterait 1 369 PDC pour un motif de forme, alors que le
validateur officiel les accepte.

---

## ADR 04. Rattachement départemental par les coordonnées

**Contexte.** `code_insee_commune` est vide pour 26,62 % du parc.

**Chiffres.**

| méthode | PDC rattachés | couverture |
|---|---:|---:|
| `code_insee_commune` seul | 123 713 | 73,38 % |
| point dans polygone sur `consolidated_lat/lon` | **168 224** | **99,78 %** |
| récupération INSEE via le fichier historique data.gouv | +3 484 | négligeable |

Accord entre les deux méthodes là où les deux existent : **98,27 %**
(121 374 PDC sur 123 513), désaccord sur 2 139 PDC (1,73 %).

**Décision.** Département calculé par point dans polygone sur
`departements-avec-outre-mer.geojson` (france-geojson, dérivé d'Admin Express
IGN, Licence ouverte, 101 entités). `code_insee_commune` sert de contrôle. Les
2 139 désaccords sont comptés et le chiffre figure dans la Méthode. Les 378 PDC
non rattachés (0,22 %) sont exclus des agrégats départementaux et comptés.

**Conséquence.** Le build embarque une version simplifiée des contours. Le
fichier brut fait 3,72 Mo, à ramener sous 0,3 Mo (ADR 20).

---

## ADR 05. Corse, DOM, COM

**Chiffres** (rattachement par coordonnées, 17/09) :

| territoire | PDC |
|---|---:|
| Corse 2A | 544 |
| Corse 2B | 438 |
| 974 La Réunion | 424 |
| 971 Guadeloupe | 109 |
| 972 Martinique | 34 |
| 973 Guyane | **2** |
| 976 Mayotte | **0** |
| 975, 977, 978 | absents |
| Nouvelle-Calédonie | 4 |
| Polynésie française | 30 |
| hors France | 149 |

**Décision.**

1. **Corse** : 2A et 2B traités comme des départements ordinaires. Les deux
   dépassent largement le seuil de 30 (ADR 17). Sans cet ADR 04 ils n'auraient
   eu que 161 et 133 PDC par l'INSEE, soit 70 % de moins.
2. **DOM** : inclus dans tous les totaux France. **974** a sa case
   départementale (424 PDC). **971** (109) apparaît avec son effectif entre
   parenthèses. **972** (34) et **973** (2) sont listés mais toute statistique
   dérivée y affiche « effectif insuffisant (n = 34) » et « (n = 2) ».
   **976** n'apparaît pas : zéro PDC dans la source.
3. **Carte** : les DOM ne sont pas dans la carte principale. Ils sont accessibles
   par le sélecteur de département, et leur absence de la carte est écrite dans
   la Méthode avec leur effectif total (569 PDC, 0,34 % du parc).
4. **COM** (Nouvelle-Calédonie 4, Polynésie 30) : hors nomenclature
   départementale du GeoJSON. Exclus des agrégats départementaux, inclus dans le
   total France, comptés dans la Méthode.
5. **Hors France** (149 PDC) : exclus du total France, comptés.

---

## ADR 06. Classes de puissance : courant déduit croisé avec la puissance

**Contexte.** La spec propose des classes nommées « AC ≤ 7, AC 7 à 22,
DC 22 à 50, DC 50 à 150, DC ≥ 150 », c'est-à-dire un découpage par puissance
seule, avec une frontière AC/DC implicite à 22 kW. Aucun champ ne dit si un
point est AC ou DC.

**Chiffres qui invalident le découpage par puissance seule.**

| puissance exacte | PDC | dont une prise DC déclarée |
|---|---:|---:|
| 22,00 kW | 63 507 | 882 (**1,4 %**) |
| 22,08 kW | 14 649 | 4 (**0,0 %**) |
| 22,80 kW | 568 | 2 (0,4 %) |
| 24,00 kW | 2 862 | 2 314 (**80,9 %**) |
| 25,00 kW | 981 | 917 (**93,5 %**) |
| 36,00 kW | 729 | 308 (42,2 %) |
| 43,00 kW | 629 | 18 (2,9 %) |
| 50,00 kW | 6 976 | 6 798 (97,4 %) |

22,08 kW est la puissance d'une prise triphasée 32 A (3 × 32 × 230 V). Un
découpage par puissance seule rangerait **78 156 PDC en courant alternatif dans
une classe intitulée « DC 22 à 50 »**. Inversement, 24 et 25 kW sont des bornes
DC anciennes que le même découpage rangerait en dessous du seuil DC.

**Décision.** Le courant est déduit des types de prise :

- **DC** si `prise_type_combo_ccs` ou `prise_type_chademo` est vrai,
- **AC** si ni l'un ni l'autre et si `prise_type_2` ou `prise_type_ef` est vrai,
- **indéterminé** sinon.

Classes retenues, effectifs au 19/09 sur les 168 674 lignes du fichier
(168 672 PDC distincts, 2 lignes en doublon d'identifiant) :

| classe | PDC | part |
|---|---:|---:|
| AC ≤ 7 kW | 11 034 | 6,54 % |
| AC 7 à 22,9 kW | **99 232** | 58,83 % |
| AC > 22,9 kW (déclaration à vérifier) | 3 403 | 2,02 % |
| DC < 50 kW | 5 723 | 3,39 % |
| DC 50 à 150 kW | 14 458 | 8,57 % |
| DC ≥ 150 kW | 29 010 | 17,20 % |
| non classable | 5 814 | 3,45 % |

**96,55 % du parc est classable.**

**Écart à la spec.** Les libellés et les bornes des classes changent. Raison
chiffrée : le découpage de la spec mal classerait 78 156 PDC. Le sélecteur de la
page propose donc : Toutes, AC ≤ 7, AC 7 à 22, DC < 50, DC 50 à 150, DC ≥ 150.

**Incohérences déclaratives comptées et publiées** : 1 282 PDC « AC seul » à
50 kW ou plus dont 966 à 150 kW ou plus, 517 PDC « DC seul » à 22 kW ou moins,
1 275 PDC sans aucune prise déclarée, 1 795 avec `prise_type_autre` seule,
2 748 à 0 kW. Ils vont dans « non classable », ils ne sont pas corrigés.

---

## ADR 07. Normalisation des enseignes par le préfixe eMI3

**Contexte.** `nom_enseigne` compte **6 289 libellés** pour 168 672 PDC. Il sert
souvent de nom de site (« Electra Mions - Grand Frais », « Hotel Brit Florimont
B-2 ») et non de nom de réseau.

**Chiffres.**

| clé | valeurs distinctes |
|---|---:|
| `nom_enseigne` | 6 289 |
| `nom_operateur` | 278 |
| préfixe eMI3 (5 premiers caractères de `id_pdc_itinerance`) | **281** |

Normaliser à la main les libellés pour couvrir 95 % du parc demanderait de
traiter **2 369 libellés distincts**. Les 50 premiers préfixes couvrent 73,2 %
du parc, les 100 premiers 90,8 %.

Le préfixe porte un `nom_operateur` unique dans 204 cas sur 281 (72,6 %), et le
libellé opérateur majoritaire d'un préfixe couvre **94,37 % des PDC** de ce
préfixe (moyenne pondérée).

**Décision.** La clé de réseau est le **préfixe eMI3**. Le libellé affiché est
le `nom_operateur` majoritaire du préfixe, surchargeable dans
`build/enseignes.yml` pour les cas connus (fusions de graphies du type `IZIVIA`
et `Izivia`, les quatre entités `TotalEnergies`, `ALDI` et `ALDI SARL`).
`build/enseignes.yml` est versionné et ne contient que des surcharges
explicites, jamais de règle automatique.

**Conséquence.** La section « Les enseignes » classe par préfixe, pas par
libellé. Le nombre de surcharges appliquées est publié dans la Méthode.

---

## ADR 08. Cadence de collecte du flux dynamique

**Chiffres.** Part du parc changeant d'état par créneau de 5 minutes, mesurée
sur nos 239 intervalles pleins du 17 au 18/09 :

```
02h 0,21 %   ...   10h 1,89 %   ...   23h 0,25 %
```

Rapport creux/pointe de **1 à 9** entre 02h et 10h UTC. Mesure de contrôle
indépendante sur 24 h archivées : même profil, écart moyen de +7,2 % sur les
heures comparables, concordance à moins de 2 % aux heures de pointe.

Délai médian entre l'horodatage opérateur et la détection : **6,0 minutes**,
p90 à 10,3 minutes, 87,2 % des changements détectés en moins de 10 minutes. Le
flux est publié en continu : le facteur limitant est notre cadence.

**Décision.** Cadence adaptative :

- **5 minutes de 06:00 à 20:00 UTC** (168 captures),
- **15 minutes de 20:00 à 06:00 UTC** (40 captures),
- soit **208 captures par jour**.

**Écart à la spec.** La spec §3.1 prévoit 15 minutes uniformes, « à ajuster
après mesure du taux de rafraîchissement réel du flux, documenté ». C'est
exactement cet ajustement. Raison chiffrée : à 15 minutes uniformes on manquerait
la moitié des transitions aux heures de pointe, et on paierait 40 captures par
nuit pour 0,2 % de changement par créneau.

---

## ADR 09. Hébergement de la collecte

**Contexte.** La collecte de profilage a tourné sur un poste de travail.

**Chiffres.** 327 sondages tentés, **83 en échec (25,4 %)**, tous par perte de
résolution DNS de la machine, aucun code HTTP autre que 200 côté serveur. Deux
blocs perdus, dont 16h à 19h UTC le 18/09, c'est-à-dire en pleine période de
pointe.

**Décision.** GitHub Actions, un workflow par plage de cadence (ADR 08), avec
journal d'exécution par run : horodatage, code HTTP, nombre de lignes, SHA-256
du corps, nombre de changements enregistrés, durée. Un run manqué est un créneau
marqué manquant, jamais reconstruit.

**Conséquence.** Le taux de créneaux manqués est un indicateur publié dans la
Méthode. Objectif : moins de 2 %. La collecte locale reste possible en secours,
avec le même script et le même journal.

**Coût, mesuré sur les premiers passages réels.** Un passage dure **35 secondes**
de bout en bout (récupération du dépôt, installation, capture, publication).
GitHub facture à la minute entamée, donc 1 minute par passage :

| | minutes par mois |
|---|---:|
| 208 passages par jour | **6 240** |
| quota gratuit d'un dépôt **privé** | 2 000 |
| quota d'un dépôt **public** | illimité |

Le dépôt `matheo-kandra/chargelab` est créé **privé**. Les 48 heures de preuve
demandées par la spec coûtent environ **416 minutes**, ce qui tient largement
dans le quota gratuit. Au-delà, le quota privé est épuisé en **9,6 jours**.
Passer le dépôt en public rend la collecte gratuite et sans limite ; les données
collectées sont sous Licence Ouverte Etalab, rien n'y est confidentiel. La
décision appartient au propriétaire du dépôt et n'est pas prise ici.

**Cadence réellement obtenue, mesurée.** Le cron `*/5` a été essayé, puis
décalé hors des minutes rondes, et mesuré :

| | |
|---|---:|
| passages planifiés attendus entre 09:49 et 14:20 UTC le 19/09 | environ 50 |
| passages planifiés réellement déclenchés | **1** |

Un seul déclenchement, à 14:00:10, après quatre heures de silence complet.
Workflows actifs, Actions activé, `main` par défaut, dépôt non forké, droits
d'écriture confirmés par trois passages manuels réussis : rien ne bloquait de
notre côté. GitHub abandonne les passages planifiés en période de charge, et
les fréquences courtes sont les premières sacrifiées.

**Décision revue le 20/09 : le planificateur ne déclenche plus chaque passage.**
Il déclenche **une fois par heure** une boucle qui tient elle-même la cadence de
l'ADR 08 jusqu'au créneau horaire suivant (`collect/boucle_locale.py --jusqu-a`).
Un déclenchement horaire retardé de vingt minutes coûte vingt minutes de
collecte, pas la journée entière. Le même script sert en local et dans Actions.

Ce choix consomme environ **1 400 minutes par jour** au lieu de 208, ce qui est
sans objet depuis que le dépôt est **public** : les minutes y sont illimitées.
Le tableau de coût ci-dessus reste valable pour un dépôt privé, où cette
solution serait inapplicable.

**Deuxième mesure, côté collecte locale.** Le poste de travail a échoué deux
fois en deux jours : 27 passages perdus sur coupure DNS le 19/09, puis un arrêt
complet de **17,6 heures** dans la nuit du 19 au 20 parce que la machine s'est
endormie puis a redémarré. `caffeinate -i` n'empêche ni la fermeture du capot ni
l'extinction. La collecte locale reste un secours, pas une source principale.

Le journal mesure le pas réel à chaque passage et `collect/bilan.py` en fait la
synthèse. La cadence annoncée dans la Méthode sera celle qui est mesurée, pas
celle qui est programmée.

---

## ADR 10. Stockage et rétention

**Contexte.** La spec §3.1 demande une copie brute quotidienne du fichier
statique. Le fichier fait 120,8 Mo bruts, **6,2 Mo compressés**.

**Chiffres.**

| poste | volume annuel |
|---|---:|
| statique complet quotidien, comme le demande la spec | **2 260 Mo** |
| photo complète quotidienne du dynamique (1,56 Mo) | 570 Mo |
| changements d'état du dynamique (208 captures × 3,9 ko) | 290 Mo |

Or, entre le 17/09 et le 19/09, sur 168 596 PDC communs :

| ce qui change | PDC | part |
|---|---:|---:|
| `date_maj` ou `datagouv_last_modified` seuls | 88 554 | 52,52 % |
| **un champ de contenu** (puissance, tarification, enseigne, station, date de mise en service) | **612** | **0,363 %** |

Le fichier statique est donc quasi immobile : **99,64 % du parc n'a aucun
changement de contenu en deux jours.**

**Décision.** Pour le statique :

- **copie complète hebdomadaire** (lundi), 6,2 Mo,
- **diff quotidien de contenu** (lignes dont un champ autre que `date_maj` et
  `datagouv_last_modified` a changé, plus les entrées et sorties), environ 30 ko,
- **journal quotidien `date_maj`**, deux colonnes, environ 140 ko.

Total : **385 Mo par an contre 2 260 Mo**, avec reconstruction exacte de
n'importe quel jour à partir de la copie hebdomadaire et des diffs.

Pour le dynamique : photo complète quotidienne conservée, changements d'état
conservés, conformément à la spec.

**Écart à la spec.** Le statique n'est plus archivé en entier chaque jour.
Raison chiffrée : 2 260 Mo par an pour 0,363 % de contenu qui bouge. La
propriété exigée par la spec, « `make edition DATE=...` régénère à l'identique à
partir des fichiers bruts archivés », est conservée puisque la reconstruction
est exacte. Un test de non régression rejoue la reconstruction d'une date passée
et compare le SHA-256 au fichier complet correspondant.

---

## ADR 11. Doublons à l'intérieur d'une capture dynamique

**Chiffres.** Dans la capture du 17/09 20:23 UTC : 121 513 lignes pour
**110 759 PDC distincts**, soit 10 735 PDC présents plusieurs fois, dont
**1 574 avec des `etat_pdc` contradictoires**.

**Décision.** Pour chaque `id_pdc_itinerance`, garder la ligne au `horodatage`
le plus récent. À égalité d'horodatage, garder la dernière ligne du fichier.
Le nombre de conflits résolus et le nombre de contradictions d'état sont
journalisés à chaque capture.

---

## ADR 12. Seuil de fraîcheur de l'état : 24 heures

**Contexte.** 30,14 % des lignes du flux portent un horodatage de plus de
90 jours. La valeur `occupation_pdc` d'une ligne vieille de trois mois ne dit
rien de la journée en cours.

**Chiffres.** Taux de PDC hors service au 17/09, selon le seuil :

| seuil | PDC retenus | part du parc | hors service |
|---|---:|---:|---:|
| < 6 h | 36 424 | 21,60 % | 2,28 % |
| **< 24 h** | **54 435** | **32,29 %** | **3,55 %** |
| < 72 h | 63 797 | 37,84 % | 3,90 % |
| aucun filtre | 101 919 | 60,45 % | 8,06 % |

Sur une journée complète de captures, 44,84 % des PDC du flux ont un horodatage
de moins de 24 h à chaque créneau, **40,61 % n'en ont jamais**, 14,55 % parfois.

**Décision.** Seuil à **24 heures**. Un PDC dont l'horodatage opérateur dépasse
24 heures n'a pas d'état pour la journée : il est classé « muet », pas « en
service ». Les trois autres seuils sont recalculés à chaque édition et publiés
dans la Méthode, pour que le lecteur voie l'effet de la règle.

**Conséquence.** Le bandeau annonce un taux hors service calculé sur environ un
tiers du parc, et **le dit avec l'effectif entre parenthèses**. C'est le prix de
l'honnêteté : il n'existe pas d'état du jour pour les deux autres tiers.

---

## ADR 13. Règle de dominance « hors service du jour » : 50 %

**Chiffres.** Distribution, par PDC, de la part de créneaux déclarés
`hors_service` sur une journée complète (66 créneaux du 18/09, pas de 15 min) :

| part de créneaux hors service | PDC | part |
|---|---:|---:|
| exactement 0 % | 97 243 | 87,78 % |
| 0 à 25 % | 3 714 | 3,35 % |
| 25 à 50 % | 983 | 0,89 % |
| 50 à 75 % | 837 | 0,76 % |
| 75 à 100 % | 556 | 0,50 % |
| **exactement 100 %** | **7 452** | **6,73 %** |

**La variable est quasi binaire : 94,5 % des PDC sont à 0 % ou à 100 %.**
Sensibilité au seuil :

| seuil | PDC classés hors service | taux |
|---|---:|---:|
| 25 % | 9 828 | 8,87 % |
| **50 %** | **8 845** | **7,98 %** |
| 75 % | 8 008 | 7,23 % |

**Décision.** Seuil à **50 %**, comme proposé par la spec. Justification : l'écart
entre les seuils extrêmes est de 1,64 point, contre 5,78 points pour le seuil de
fraîcheur (ADR 12). Ce n'est pas le paramètre sensible du modèle, et le seuil de
la spec est conservé sans discussion.

`inconnu` suit la même logique : 95,24 % des PDC ne sont jamais `inconnu`,
3,54 % le sont toujours. Un PDC `inconnu` sur au moins 50 % des créneaux est
classé « inconnu persistant ».

---

## ADR 14. Définitions de « muet », « disparu », « retiré »

**Décision.** Trois états distincts, jamais confondus, chacun avec son compteur :

| terme | définition exacte | effectif au 17/09 |
|---|---|---:|
| **hors service déclaré** | présent au statique, présent au dynamique avec un horodatage de moins de 24 h, `etat_pdc = hors_service` sur au moins 50 % des créneaux | 1 930 |
| **inconnu persistant** | mêmes conditions, `etat_pdc = inconnu` sur au moins 50 % des créneaux | 781 |
| **muet** | présent au statique, mais sans aucune ligne dynamique de moins de 24 h dans la journée (absent du flux, ou présent avec un horodatage périmé) | **114 165 (67,7 %)** |
| **disparu** | absent du fichier statique pendant plus de N jours consécutifs après y avoir figuré (ADR 15) | à mesurer, voir ci-dessous |

**Chiffres sur la disparition.** Entre le 17/09 et le 19/09 : 76 entrées et
**4 sorties** sur 168 600 PDC, soit environ 38 entrées et 2 sorties par jour.
Sur les 244 captures dynamiques, les entrées et sorties du flux ont une médiane
de 0 par intervalle et un maximum de 7. La composition des deux fichiers est
donc très stable, et une absence n'est presque jamais un clignotement.

**Conséquence.** « Muet » est l'état majoritaire du parc. La section
« Les bornes muettes » doit donc distinguer visuellement les trois catégories et
afficher d'emblée que les deux tiers du parc ne disent rien, sinon elle laisserait
croire à une panne généralisée.

---

## ADR 15. Report de la dernière valeur : N = 10 jours (provisoire)

**Contexte.** La spec fixe N = 10 par défaut, « à justifier par les données ».

**Ce que les données permettent de dire aujourd'hui.** Deux jours d'historique
statique et 27 heures de collecte dynamique. Les entrées et sorties sont rares
(2 sorties par jour au statique, médiane 0 par intervalle au dynamique), donc
une absence est plutôt une vraie absence qu'un trou de collecte. Mais **la
distribution de la durée des absences ne peut pas être mesurée sur deux jours.**

**Décision.** N = **10 jours**, valeur de la spec, explicitement **provisoire**.
Revue le **19 octobre 2026**, quand 30 jours d'historique permettront de mesurer
la distribution des durées d'absence et de choisir N sur le p95 observé.

**Conséquence.** La Méthode écrit « report limité à 10 jours, valeur provisoire
non encore justifiée par les données, révision prévue après 30 jours de
collecte ». Pas de phrase générique sans le dire.

---

## ADR 16. Section prix : pas de médiane nationale

**Chiffres.**

| | valeur |
|---|---:|
| `tarification` renseignée | 36 196 PDC, **21,47 %** |
| dont porteuse d'un prix €/kWh | 14 509 PDC, **8,61 % du parc** |
| part des valeurs renseignées qui ne sont pas un prix | **58,33 %** |
| enseignes portant les PDC tarifés | 397, mais **5 en portent 69,5 %**, 10 en portent 81,9 % |
| classes de puissance sous le seuil de 30 au national | **2 sur 5** (AC ≤ 7 : 85 PDC ; AC 7 à 22 : 266 PDC) |

De plus, entre le 17/09 et le 19/09, **8 PDC sur 168 596 ont vu leur
`tarification` changer**, soit 0,005 %. Le champ est immobile.

**Décision.**

1. La section devient **« Ce que les opérateurs déclarent »**, pas « le prix de
   la recharge ». Elle s'ouvre sur les deux taux, en gros : renseignement
   21,47 %, parsabilité 8,61 %.
2. **Aucune médiane nationale**, ni toutes classes confondues, ni par classe.
3. Les médianes ne sont affichées que par couple **(classe de puissance ×
   réseau)** et seulement si l'effectif parsable atteint 30 PDC. Chaque case
   porte son effectif.
4. La concentration est affichée : « ces prix proviennent de N réseaux, dont les
   cinq premiers représentent X % des points tarifés ».
5. **Écart à la spec §5** : l'onglet « médiane €/kWh par classe » de la section
   « La marée » est supprimé. Raison chiffrée : 8 changements de tarif en deux
   jours donneraient une courbe plate, qui laisserait croire à une mesure de
   marché stable alors qu'il s'agit de l'immobilité d'un champ déclaratif. Les
   changements de tarif restent visibles dans « Les records », en événements
   datés, avec leur effectif.

---

## ADR 17. Codes de parsing de `tarification` et bornes

**Décision.** Huit codes, conformes à la spec §4.3 : `KWH`, `MIN`, `SESSION`,
`MIXTE`, `GRATUIT`, `RENVOI`, `VIDE`, `INCONNU`. Correspondance avec les familles
recensées dans `data/profiling/tarification-familles.csv` :

| famille observée | code | PDC |
|---|---|---:|
| `VIDE` | `VIDE` | 132 406 |
| `RENVOI_TEXTE`, `RENVOI_URL`, `NON_INFO_MOT_CLE` | `RENVOI` | 21 113 |
| `EXPORT_STRUCTURE`, `PRIX_KWH_LIBRE`, `JSON_OPERATEUR` | `KWH` ou `MIXTE` | 14 467 |
| `GRATUIT` | `GRATUIT` | 42 |
| `PRIX_TEMPS_SEUL` | `MIN` | 71 |
| `NOMBRE_NU_SANS_UNITE`, `AUTRE_NON_CLASSE` | `INCONNU` | 503 |

**Règles de classement décidées après lecture des 438 valeurs distinctes :**

| cas | décision | raison |
|---|---|---|
| nombre nu sans unité (`0.4583`, `0,22`, `15`) | `INCONNU` | rien ne dit que l'unité est le kWh. 490 PDC |
| `cts` avec une valeur décimale (`0,35cts/KWh`) | `INCONNU` | lu littéralement : 0,0035 €/kWh. Ne pas deviner 0,35 |
| prix libellé au `kW` au lieu du `kWh` | `INCONNU` | faute d'unité, pas d'interprétation |
| booléen fuité (`TRUE`, `true`, `false`, `null`) | `RENVOI` | 247 PDC, champ mal mappé à la source |
| hors de [0,05 ; 1,50] €/kWh | `INCONNU` | borne de plausibilité de la spec |
| mojibake (`0,55 â‚¬/ kwh`) | décodé si le décodage est déterministe, sinon `INCONNU` | 3 valeurs, 44 PDC |
| tarif différencié par plage horaire | on garde le prix `par défaut` s'il existe, sinon la plage la plus longue | structure conservée dans le champ brut |
| tarif différencié AC/DC dans la même chaîne | deux prix conservés, rattachés à la classe du PDC | |

**HT et TTC.** La spec impose de supposer TTC quand ce n'est pas précisé. Quand
c'est précisé HT (`0,55€KWH HT`, `0,42 € HT / kWh`, `0.21€/kWh HTVA`), la valeur
est **convertie en TTC au taux de 20 %**, marquée comme convertie, et le nombre
de valeurs converties est publié. Les valeurs marquées TTC sont prises telles
quelles.

**Écart à la spec.** La spec ne prévoyait pas le cas HT explicite. Convertir est
préférable à exclure : sans conversion, on écarterait des réseaux entiers qui
déclarent proprement en HT, ce qui biaiserait la comparaison entre réseaux.

**Tests.** `tests/tarification_cases.csv` contiendra au moins 200 cas réels tirés
de `docs/tarification-valeurs.csv`, couvrant les 438 valeurs par famille. Tout
motif représentant plus de 0,5 % des lignes et non couvert fait échouer le build.
Les tests sont écrits avant l'implémentation, comme demandé.

---

## ADR 18. Seuil d'effectif : 30

**Décision.** Aucune médiane, aucun taux dérivé n'est affiché sur moins de
**30 PDC**. La case affiche « effectif insuffisant (n = …) ».

**Chiffres.** Au niveau départemental, sur les PDC porteurs d'un prix,
76 départements sur 97 atteignent 30, 44 atteignent 100. Sur le parc entier,
tous les départements sauf 973 (2 PDC) et 972 (34 PDC, tout juste au seuil)
dépassent 200 PDC.

---

## ADR 19. Écrêtage p2/p98

**Décision.** Toutes les échelles de couleur et toutes les bandes sont bornées
aux **p2 et p98 observés le jour de l'édition**, jamais à des bornes fixes. Les
bornes retenues sont écrites dans la Méthode à chaque édition, avec le nombre de
valeurs écrêtées.

**Justification.** `puissance_nominale` va de 0 à **160 000 kW**, valeur qui est
une confusion kW/W non corrigée à la source. 2 748 PDC sont à 0 kW, 458 au-dessus
de 400 kW. Sans écrêtage, l'échelle de couleur de la carte serait illisible.

---

## ADR 20. Stack de build : Python et pandas

**Décision.** Build en Python 3.12, pandas pour la manipulation, numpy et scipy
pour les implémentations de référence des tests, shapely pour le point dans
polygone. Pas de framework côté page : HTML, CSS et JavaScript natifs.

**Justification.** Le profilage a traité un fichier de 290 Mo et 396 878 lignes
sans difficulté. La spec §9.4 exige que chaque fonction de calcul soit comparée
à une implémentation de référence numpy ou scipy : les avoir dans le même
processus supprime toute question de portage.

---

## ADR 21. Budget : cible 1,5 Mo, plafond 4 Mo

**Chiffres mesurés.** Les 49 081 stations, latitude et longitude quantifiées au
millième de degré en entiers 32 bits : 0,39 Mo brut, **0,18 Mo compressé**.
Les contours départementaux bruts font 3,72 Mo, à simplifier.

**Décision.** Cible **1,5 Mo compressés** pour la vue nationale toutes classes,
plafond 4 Mo de la spec inchangé. Ordre de dégradation si la cible est dépassée,
décidé d'avance pour ne pas improviser :

1. simplification plus agressive des contours départementaux,
2. quantification des séries temporelles en `Uint16` au lieu de `Float32`,
3. agrégation de la carte au niveau station au lieu du PDC (déjà le cas),
4. réduction de la profondeur d'historique embarquée, en le disant sur la page.

Le budget réellement obtenu est écrit dans la Méthode, comme sur la référence.

---

## ADR 22. Historique : pas de backfill, la série commence le 17/09/2026

**Contexte.** Le dépôt tiers `Valentinafry/irve-collecte` contient 20 jours
d'historique dynamique continu (12/08 au 01/09) au pas de 10 minutes.

**Chiffres.** Aucun fichier LICENSE dans le dépôt. Collecte arrêtée depuis le
01/09 à 09:40 UTC, soit un trou de 16 jours jusqu'au démarrage de la nôtre.

**Décision.** Aucun backfill. L'historique du projet commence au
**17 septembre 2026**. Le dépôt a servi une seule fois, comme mesure de contrôle
de la cadence (data-profile §8.1) ; les fichiers bruts téléchargés ont été
**supprimés du projet**, seuls les agrégats par créneau sont conservés dans
`data/profiling/cadence-24h-2026-08-20.csv`.

**Conséquence.** Les sections qui demandent une profondeur d'historique ne
peuvent pas être servies tout de suite :

| section | profondeur requise | disponible le 17/09 | date de disponibilité |
|---|---|---|---|
| « La marée » (courbe quotidienne) | quelques jours | 1 jour | dès la 2e édition |
| « Le mur » (21 semaines de médiane hebdomadaire) | 21 semaines | voir ADR 23 | février 2027 pour la médiane glissante |
| « Et après » (Theil-Sen 30 j) | 30 jours | 1 jour | **17 octobre 2026** |
| bande de backtest | 30 jours d'origines passées | 0 | **16 novembre 2026** |
| « Éditions précédentes » | variable | 0 | dès la 2e édition |

Tant que la profondeur n'est pas atteinte, la section affiche ce dont elle
dispose avec le nombre de jours entre parenthèses, et la projection n'est pas
affichée du tout. Pas de courbe lissée sur trois points.

---

## ADR 23. « Le mur » : périmètre limité et affiché

**Chiffres.** `date_mise_en_service` est renseignée pour **51,26 % du parc**
(86 428 PDC sur 168 602). Valeurs aberrantes : 4 PDC au 01/01/1900, 1 au
27/08/2028. Répartition par année : 2021 : 9 306, 2022 : 11 323, 2023 : 15 825,
2024 : 17 299, 2025 : 18 237, 2026 : 9 358, mais seulement 297 en 2018 contre
1 603 en 2019.

**Décision.** La section « Le mur » est construite sur les seuls PDC dont
`date_mise_en_service` est renseignée et comprise entre le 01/01/2012 et la date
de l'édition. Elle porte en titre l'effectif et la couverture. Le creux de 2018
est signalé comme un artefact de déclaration, pas comme un creux d'installation.

Les **retraits par semaine** ne viennent pas de `date_mise_en_service` mais de
notre propre suivi jour à jour du fichier statique, qui commence le 17/09
(ADR 22). Mesure de référence : 2 sorties par jour entre le 17 et le 19/09.

---

## ADR 24. Écart France brut contre France recalculé

**Décision.** Comme le demande la spec §3.2, le build calcule les chiffres France
sur la matrice brute, et la page les recalcule dans le navigateur sur la matrice
embarquée. L'écart entre les deux est mesuré à chaque édition et publié dans la
Méthode en milli-points, avec le détail par indicateur. Un écart supérieur à
1 milli-point sur le taux hors service fait échouer le build.

---

## Journal des mesures faites pour cette étape

| mesure | fichier produit |
|---|---|
| cadence sur notre collecte, 243 intervalles | `data/profiling/cadence-propre-24h.csv` |
| cadence de contrôle, 144 créneaux | `data/profiling/cadence-24h-2026-08-20.csv` |
| comparaison du parc 17/09 contre 19/09 | mesures reportées ici, fichiers bruts dans `data/raw/statique/` |
| distribution du taux hors service par PDC sur une journée | mesures reportées ici |
| préfixe eMI3 contre libellé d'enseigne et d'opérateur | mesures reportées ici |
| déduction AC/DC et classes de puissance | mesures reportées ici |
| volumétrie de stockage | mesures reportées ici |

Les mesures marquées « reportées ici » sont issues de scripts ponctuels. Elles
seront figées en scripts versionnés dans `build/` à l'étape 4, avec leurs tests,
conformément à l'exigence de traçabilité de la spec.
