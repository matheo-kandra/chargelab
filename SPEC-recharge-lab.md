# SPEC : « Le mouvement de la recharge électrique en France »

Adaptation à la recharge des véhicules électriques de la page https://fuel.powlisher.com/lab (PowlFuel, édition quotidienne des prix des carburants). Ce document est la référence unique du projet. Claude Code doit le lire en entier avant toute action, puis le respecter à la lettre. Ce qui n'est pas spécifié ici se décide par l'analyse des données réelles, jamais par supposition.

Nom de travail : `chargelab` (le nom définitif sera choisi plus tard, ne pas réutiliser la marque PowlFuel ni le domaine powlisher).

---

## 0. Principes non négociables (hérités de la page de référence)

La page de référence a une méthode explicite. On la reprend telle quelle, adaptée au sujet :

1. **Édition quotidienne.** Une date, un jeu de données figé, un titre « Édition du jeudi 17 septembre 2026 ». Les éditions précédentes restent consultables.
2. **Page = un fichier.** Aucune requête réseau à l'exécution. Toutes les données sont embarquées dans le HTML (ou dans un unique fichier JSON/binaire chargé une fois au démarrage si le budget l'impose, voir §7). Un territoire (région, département) est recalculé dans le navigateur à partir de la matrice embarquée.
3. **Médianes, jamais des moyennes.** Toute statistique de prix ou de taux est une médiane ; la dispersion est donnée par p25/p75, p10/p90, p1/p99.
4. **Les trous ne sont pas escamotés.** Un jour non collecté est marqué sur la courbe (point creux, hachure), jamais interpolé silencieusement.
5. **Imputation bornée et déclarée.** Une station/un point de charge muet un jour donné conserve sa dernière valeur connue pendant N jours au plus (N = 10 par défaut, à justifier par les données), sinon il disparaît du calcul du jour.
6. **Écrêtage déclaré.** Échelles de couleur et bandes bornées aux p2/p98 observés, parce que les flux contiennent des valeurs bouchon.
7. **Prévision honnête.** Pente Theil–Sen sur 30 jours ; la bande d'incertitude est un backtest (p10/p90 des erreurs réellement commises en rejouant la méthode depuis chaque origine passée), pas un résidu d'ajustement.
8. **Géolocalisation facultative et locale.** La position sert à trouver le département, puis elle est oubliée. Rien n'est envoyé, rien n'est enregistré, seul le code du département reste dans l'onglet.
9. **Section « Méthode » écrite en français clair**, chiffres à l'appui, qui dit exactement ce qui a été fait et ce qui n'a pas pu l'être.
10. **Aucun chiffre affiché n'est saisi à la main.** Tout ce que la page montre est produit par le script de construction et reproductible.

---

## 1. La différence fondamentale avec le carburant (à comprendre avant de coder)

Le carburant a un flux officiel de **prix quotidien par station**. La recharge électrique n'en a pas. Ce que l'État publie pour les bornes ouvertes au public, c'est :

- **Un flux statique** (schéma `etalab/schema-irve-statique`, version 2.3.x) : localisation, aménageur, opérateur, enseigne, puissance nominale, types de prises, `gratuit` (booléen facultatif), `paiement_acte`, `paiement_cb`, `tarification` (**texte libre, facultatif**), horaires, `date_mise_en_service`, `date_maj`.
- **Un flux dynamique** (schéma `etalab/schema-irve-dynamique`) : état du point de charge (en service / hors service / inconnu), occupation (libre / occupé / réservé / inconnu), état des prises, horodatage. C'est un instantané, pas un historique.

Conséquences pour le projet :

- Le **prix** ne peut être suivi que là où `tarification` est parsable. La couverture sera partielle et doit être **affichée comme telle** (taux de renseignement, taux de parsabilité), jamais extrapolée.
- Le **cœur quotidien** de la page n'est donc pas le prix mais **l'état du réseau** : parc (points de charge, stations, puissance installée), disponibilité (part hors service, part occupée aux heures de capture), croissance, et prix là où il existe.
- Le flux dynamique doit être **capturé plusieurs fois par jour** par nous, sinon aucune série temporelle n'existe. La collecte est donc un composant du projet, pas une option.

Si l'analyse des données montre que la couverture du champ `tarification` est trop faible pour produire une médiane fiable au niveau national, la section prix devient une section « Ce que les opérateurs déclarent » avec sa couverture en gros, et on ne fabrique pas de médiane nationale de prix. Ce point se tranche sur les chiffres, pas a priori.

---

## 2. Sources de données (à vérifier une par une avant utilisation)

Toute URL ci-dessous doit être ouverte, testée, et son contenu réel décrit dans `docs/data-profile.md` (voir §9). Si une source a bougé, la retrouver via transport.data.gouv.fr et documenter le changement.

### 2.1 Sources primaires (obligatoires)

| Source | Rôle | Pointeur connu au 17/09/2026 |
|---|---|---|
| Base nationale IRVE, consolidation PAN (beta), **statique non dédoublonnée** | Parc, puissances, enseignes, tarification texte | https://transport.data.gouv.fr/datasets/beta-bases-nationales-des-points-de-recharge-pour-vehicules-electriques-en-france-irve |
| Base nationale IRVE, consolidation PAN (beta), **dynamique** | États et occupation, instantané | même jeu de données, ressource « données dynamiques » |
| Fichier consolidé historique data.gouv (schéma v2) | Backfill et contrôle croisé ; supprimé au 31/12/2026, ne pas en dépendre | https://www.data.gouv.fr/fr/datasets/r/2729b192-40ab-4454-904d-735084dca3a3 |
| Schéma statique | Dictionnaire des champs, types, valeurs autorisées | https://schema.data.gouv.fr/etalab/schema-irve-statique/latest/documentation.html |
| Schéma dynamique | idem | https://schema.data.gouv.fr/etalab/schema-irve-dynamique/latest/documentation.html (à confirmer) |

Points d'attention :
- La consolidation PAN est marquée **beta** et remonte régulièrement des erreurs de validation sur le flux dynamique. Le script doit valider chaque fichier contre le schéma (Validata ou validation locale équivalente) et **consigner le nombre de lignes rejetées** par motif.
- Le fichier « non dédoublonné » contient des doublons d'`id_pdc_itinerance`. La règle de dédoublonnage (dernier `date_maj` gagne ? source prioritaire ?) doit être choisie, testée et documentée avec le nombre de doublons résolus.
- L'identifiant pivot est `id_pdc_itinerance` (format eMI3 : `FR` + 3 caractères opérateur + `E` ou `P` + suite). Vérifier sa conformité ; les identifiants non conformes sont comptés et exclus, pas corrigés à la main.

### 2.2 Sources secondaires (optionnelles, à activer seulement si utiles et vérifiées)

| Source | Usage envisagé |
|---|---|
| Dépôt GitHub `Valentinafry/irve-collecte` (historisation des statuts dynamiques France) | Backfill possible de l'historique dynamique avant notre propre collecte. Vérifier licence, format, continuité. Ne l'utiliser que si la méthode de collecte y est documentée et compatible avec la nôtre. |
| ODRÉ (odre.opendatasoft.com, jeu `bornes-irve`) | Miroir du fichier consolidé, API filtrable. Utile pour contrôle croisé, pas comme source de vérité. |
| INSEE : population légale par département ; IGN/INSEE : superficie | Densité de points de charge (pour 10 000 habitants, pour 100 km²). |
| Contours des départements (GeoJSON simplifié, licence ouverte) | Carte ; rester sous une taille budgetée (voir §7). |
| RTE / éCO2mix, calendrier Tempo, TRV électricité (CRE) | Section optionnelle « Le socle » : prix domicile de référence et signal Tempo du jour. Ne pas mélanger avec les prix bornes. |
| Chiffres Avere-France / baromètres | Uniquement en contexte dans la Méthode, jamais comme donnée calculée. |

Licence : les données IRVE sont sous Licence Ouverte / Etalab. La page doit porter la mention de source et la date de génération.

---

## 3. Collecte et historisation

### 3.1 Cadence

- **Statique** : 1 téléchargement par jour, horodaté, conservé brut (compressé) dans `data/raw/statique/YYYY-MM-DD.csv.gz`.
- **Dynamique** : capture toutes les **15 minutes** (à ajuster après mesure du taux de rafraîchissement réel du flux, documenté), conservée brute dans `data/raw/dynamique/YYYY-MM-DD/HHMM.csv.gz`. On ne stocke ensuite que les **changements d'état** par `id_pdc_itinerance` (compaction), avec l'horodatage de l'opérateur ET l'horodatage de capture.
- Orchestration : GitHub Actions (cron) ou équivalent, avec **journal d'exécution** par run (succès/échec, nombre de lignes, hash du fichier). Un run manqué est un jour/créneau marqué manquant, jamais reconstruit.

### 3.2 Matrice de construction

Le script `build/` produit, pour chaque édition :

- `M_parc[jour]` : nombre de points de charge (PDC) et de stations valides, par classe de puissance, par département, par enseigne, par type de prise.
- `M_etat[jour]` : pour chaque PDC, l'état dominant du jour (en service / hors service / inconnu) et la part du temps « occupé » sur les créneaux capturés. Règle de dominance à définir et documenter (ex. : hors service si ≥ 50 % des créneaux capturés le disent).
- `M_prix[jour]` : pour chaque PDC dont `tarification` est parsable, le prix €/kWh (et éventuellement €/min, €/session) extrait, avec un code de parsing (voir §4).
- `M_nouveautes[semaine]` : mises en service par semaine d'après `date_mise_en_service`, et disparitions (PDC présent en J-1, absent en J pendant plus de N jours).

Deux niveaux de calcul, comme dans la page de référence :
- Les chiffres **France** viennent de la matrice brute du script.
- Les chiffres **territoire** sont recalculés dans le navigateur sur la matrice embarquée (avec report de la dernière valeur, N jours au plus). L'écart entre les deux sur la médiane nationale doit être **mesuré et affiché** dans la Méthode.

---

## 4. Parsing du champ `tarification` (le morceau difficile)

Objectif : extraire un prix structuré depuis un texte libre hétérogène, sans jamais deviner.

### 4.1 Démarche imposée

1. Extraire toutes les valeurs distinctes de `tarification` avec leur fréquence. Les écrire dans `docs/tarification-valeurs.csv`.
2. Construire une **grammaire de motifs** (regex + normalisation) couvrant, par ordre de fréquence : `x,xx €/kWh`, `x.xx€/kWh`, `x,xx € par kWh`, `x € HT/TTC`, `gratuit`, `x €/min`, `x €/h`, `forfait x €`, `x €/kWh + y €/min`, `selon opérateur / voir application` (= non renseigné), tarifs différenciés jour/nuit ou AC/DC (= plusieurs prix, on garde la structure).
3. Chaque valeur reçoit un **code de parsing** : `KWH`, `MIN`, `SESSION`, `MIXTE`, `GRATUIT`, `RENVOI` (renvoie vers un tiers), `VIDE`, `INCONNU`. Ces codes sont comptés et affichés.
4. **Tests unitaires obligatoires** : un fichier `tests/tarification_cases.csv` avec au moins 200 cas réels tirés des données, valeur attendue à côté, exécuté à chaque build. Tout nouveau motif fréquent (> 0,5 % des lignes) non couvert fait échouer le build avec un message listant les cas.
5. Bornes de plausibilité déclarées : un €/kWh hors [0,05 ; 1,50] est classé `INCONNU` et compté, pas corrigé.
6. HT/TTC : si non précisé, on suppose TTC et on le dit dans la Méthode.

### 4.2 Ce qu'on affiche

- Taux de renseignement (`tarification` non vide) et taux de parsabilité (`KWH` ou `MIXTE` avec composante kWh), au national et par territoire.
- Médiane €/kWh **par classe de puissance** (AC ≤ 7 kW, AC 7 à 22 kW, DC 22 à 50 kW, DC 50 à 150 kW, DC ≥ 150 kW) et par enseigne, **uniquement** si l'effectif parsable est ≥ 30 PDC dans la case ; sinon la case affiche « effectif insuffisant (n = …) ».
- Jamais une médiane nationale « tous types confondus » sans la classe de puissance à côté : elle serait dominée par la répartition AC/DC, pas par les prix.

---

## 5. Sections de la page (miroir de la référence, sujet par sujet)

Même ordre, même ton, mêmes contrôles (France / Ma région / Mon département / Me localiser / Choisir). Le sélecteur de carburant devient un sélecteur de **classe de puissance** (Toutes, AC ≤ 7, AC 7 à 22, DC 22 à 50, DC 50 à 150, DC ≥ 150) et, en second niveau, de **type de prise** (T2, Combo CCS, CHAdeMO, EF).

| Référence | Adaptation | Ce qu'on trace |
|---|---|---|
| Titre : « Le prix du carburant, là où vous êtes. » | « La recharge, là où vous êtes. » | Bandeau : édition du jour · n stations · n points de charge · n jours de relevés · parution quotidienne |
| **La carte** (chaque point une station ; couleur = prix) | La carte | Chaque point une station ; couleur au choix : puissance max, état du jour (en service / hors service), prix parsé (gris si non parsable). Échelle bornée p2/p98. |
| **La marée** (médiane et bande p25/p75 des prix) | La marée | Courbe quotidienne du **taux de PDC hors service** (médiane des taux départementaux, bande p25/p75 et p10/p90 entre départements). Second onglet : médiane €/kWh parsé par classe de puissance sélectionnée, avec la couverture affichée sous le titre. |
| **Le mur** (une crête = une semaine) | Le mur | Mises en service par semaine (`date_mise_en_service`) et retraits par semaine ; trait rouge = niveau hebdomadaire médian sur les 21 dernières semaines. |
| **Les départements** (écart au national) | Les départements | Un point par département : taux hors service, densité (PDC pour 10 000 habitants), et médiane €/kWh parsé si effectif suffisant. Trié du meilleur au moins bon selon la métrique choisie. |
| **Les enseignes** (huit réseaux) | Les enseignes | Les huit enseignes les plus présentes dans le territoire (par nombre de PDC) : part hors service, puissance médiane, part `paiement_cb`, part `gratuit`, médiane €/kWh parsée (ou « non déclaré »). |
| **Les cuves vides** (stations à sec) | **Les bornes muettes** | Rouge = PDC hors service ou muet depuis > N jours ; gris = en service. Distinguer « hors service déclaré », « inconnu persistant » et « disparu du flux ». Ne jamais confondre avec un retrait définitif. |
| **Et après** (pente 30 j + bande backtest) | Et après | Projection à 30 jours de : taille du parc (PDC), taux hors service, et médiane €/kWh parsée (si couverture stable). Theil–Sen 30 j, bande = backtest. |
| **Les records** (variation d'un jour au suivant) | Les records | Plus fortes variations quotidiennes : PDC ajoutés/retirés par département, bascules hors service massives (une enseigne, un département), changements de tarif déclaré. |
| **Éditions précédentes** | idem | Liste : date · parc · variation 7 j · PDC hors service. |
| **Méthode** | Méthode | Voir §8. |

Section optionnelle, uniquement si les sources sont vérifiées : **« Le socle »** : prix domicile de référence (TRV base et heures creuses, €/kWh TTC), couleur Tempo du jour, et le ratio « prix borne médian / prix domicile » par classe de puissance. Séparée visuellement, avec sa propre source.

Fonction utile à conserver : un petit calculateur « ce que coûte un plein » : capacité batterie saisie par l'utilisateur (défaut 60 kWh, réglable), rendement de charge 90 % déclaré, résultat par classe de puissance à la médiane du territoire. Aucun chiffre stocké côté serveur.

---

## 6. Modèle de données embarqué

- Un objet racine `edition` : `{ date, generated_at, sources: [...], counts: {...}, parametres: { N_report_jours, seuil_effectif, bornes_prix } }`.
- Tableaux typés (Float32Array / Uint16Array encodés en base64 ou fichier binaire) pour les séries jour × territoire × classe, jamais des JSON verbeux par PDC.
- Pour la carte : une station = `[lat, lon, dept, puissance_max_code, etat_code, prix_code]` quantifiés (lat/lon sur 4 décimales suffisent).
- Les identifiants opérateurs (`FRxxx`) sont mappés vers un index d'enseignes normalisées ; la table de normalisation (`build/enseignes.yml`) est versionnée et documentée (ex. : « TotalEnergies Charging Services », « Total Energies », « TOTALENERGIES » → une seule enseigne).
- Départements : Corse 2A/2B, DOM inclus (971 à 976) avec un traitement cartographique explicite (encarts) ou une exclusion **déclarée** dans la Méthode.

---

## 7. Contraintes techniques

- **Stack** : HTML + CSS + JavaScript vanilla, un seul fichier `index.html` (données inline ou un unique `data-YYYY-MM-DD.bin` chargé au démarrage), pas de framework, pas de CDN au runtime. Le build peut être en Python (pandas ou polars) ou Node ; choisir et justifier en une phrase dans le README.
- **Budget** : page complète (HTML + données) ≤ 4 Mo compressés pour la vue nationale toutes classes. Si le parc (≈ 227 000 PDC) fait exploser le budget, agréger au niveau station pour la carte et ne garder les séries par PDC que côté build. Le budget réel obtenu est écrit dans la Méthode (comme « 2,15 Mo pour les six carburants » sur la référence).
- **Performance** : premier rendu < 1,5 s sur mobile milieu de gamme ; recalcul d'un territoire < 200 ms. Mesuré, pas estimé.
- **Accessibilité** : contraste AA, navigation clavier des sélecteurs, textes alternatifs des graphiques (résumé chiffré sous chaque graphique, comme sur la référence : « X €/L d'écart p25–p75 »).
- **Métadonnées** : `<title>`, description, Open Graph avec une image du jour générée au build (courbe nationale), `canonical`, `theme-color`, PWA-friendly (comme la référence).
- **Reproductibilité** : `make edition DATE=2026-09-17` régénère à l'identique à partir des fichiers bruts archivés. Le hash du fichier produit est journalisé.
- **Typographie** : aucun tiret cadratin (—) dans les textes de la page, des libellés et de la Méthode ; utiliser la virgule, le deux-points, la parenthèse ou une phrase séparée. Les « — » d'attente pour valeurs non calculées sont remplacés par « … » ou par un tiret court « – » réservé à cet usage.

---

## 8. Contenu obligatoire de la section « Méthode »

À rédiger en français, au même niveau de précision que la référence, avec les chiffres réels du build :

1. Volumes : n PDC, n stations, n enseignes, n jours de relevés, n captures dynamiques par jour, n jours collectés sur n (les manquants listés).
2. Règles : dédoublonnage (nombre résolu), validation schéma (nombre rejeté par motif), report de la dernière valeur (N jours), écrêtage p2/p98, seuil d'effectif.
3. Prix : taux de renseignement, taux de parsabilité, répartition des codes de parsing, hypothèse TTC, bornes de plausibilité et nombre de valeurs écartées.
4. État : définition exacte de « hors service du jour », de « muet », de « disparu » ; nombre de PDC dans chaque catégorie.
5. Écart France (matrice brute) vs France (recalcul navigateur), en milli-points ou milli-euros.
6. Prévision : Theil–Sen 30 j, description du backtest, largeur observée de la bande.
7. Ce qui n'est **pas** dans la page et pourquoi (ex. : prix réels payés via badges tiers, occupation réelle si la cadence de capture est insuffisante).
8. Vie privée : géolocalisation locale, aucune requête au runtime.
9. Sources, licences, date et heure de génération, taille du fichier.

---

## 9. Livrables et ordre de travail

Ordre imposé. Ne pas passer à l'étape suivante sans avoir produit l'artefact de l'étape en cours.

1. **`docs/data-profile.md`** : pour chaque source, URL testée, schéma réel (colonnes, types, taux de remplissage par colonne, valeurs distinctes des colonnes catégorielles), anomalies observées (chiffrées), taux de rafraîchissement du flux dynamique mesuré sur au moins 24 h. Y inclure `docs/tarification-valeurs.csv`.
2. **`docs/decisions.md`** : chaque choix de méthode (N jours de report, règle de dominance, seuils, dédoublonnage, normalisation des enseignes) avec la justification chiffrée. Format ADR court.
3. **`collect/`** : scripts de collecte + workflow cron + journal. Preuve : au moins 48 h de captures réelles archivées avant de construire l'UI.
4. **`build/`** : script de construction + tests (parsing tarification, dédoublonnage, médianes vs implémentation de référence numpy, Theil–Sen, backtest). Couverture des fonctions de calcul : 100 %.
5. **`site/index.html`** + génération d'image OG.
6. **`docs/METHODE.md`** : texte de la section Méthode, source de vérité, injecté dans la page au build avec les chiffres substitués.
7. **`README.md`** : installation, `make collect`, `make edition`, `make test`, structure du dépôt.

Définition de « terminé » : le build tourne de bout en bout sur une date passée depuis les bruts archivés, tous les tests passent, la page respecte le budget, chaque chiffre affiché peut être retrouvé dans un fichier intermédiaire du build, et la Méthode ne contient aucune phrase générique (« les données sont nettoyées ») sans chiffre à côté.

---

## 10. Interdits

- Inventer, arrondir « à la main » ou reporter un chiffre externe comme s'il était calculé.
- Interpoler un jour manquant, lisser une série, remplacer une médiane par une moyenne.
- Afficher une médiane de prix sur un effectif < seuil, ou toutes classes de puissance confondues.
- Corriger silencieusement une donnée source (identifiant, coordonnée, prix aberrant) : on exclut et on compte.
- Appeler une API au runtime, charger une police, une carte ou un script externe.
- Envoyer ou stocker la position de l'utilisateur.
- Utiliser des tirets cadratins.
- Réutiliser le nom, le logo ou les visuels de PowlFuel ; seule la méthode est reprise, et la référence est citée dans le README comme inspiration.
