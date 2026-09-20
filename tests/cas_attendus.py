# -*- coding: utf-8 -*-
"""Resultats attendus du parseur de `tarification`, ecrits a la main.

Ces valeurs sont AUTORISEES A LA LECTURE, pas produites par un programme : si
elles sortaient du parseur, le test ne prouverait rien. Chaque entree a ete
decidee en lisant la valeur brute correspondante dans
docs/tarification-valeurs.csv, inventaire fige du 17 septembre 2026.

La cle est le rang dans cet inventaire, trie par nombre de PDC decroissant.
Le texte brut n'est jamais recopie ici : tests/construire_cas.py va le chercher
dans l'inventaire, ce qui supprime tout risque de faute de transcription.

Valeur : (code, kwh, minute, heure_charge, session, occupation_h, ht_converti, motif)
  code           KWH, MIN, SESSION, MIXTE, GRATUIT, RENVOI, VIDE, INCONNU
  kwh            euros par kWh, TTC
  minute         euros par minute de charge, TTC
  heure_charge   euros par heure de charge, TTC
  session        euros fixes par session, TTC
  occupation_h   euros par heure d'occupation hors charge, TTC (informatif,
                 n'entre pas dans le code : ce n'est pas un prix de recharge)
  ht_converti    True si la source declarait HT et que la valeur a ete portee
                 a TTC au taux de 20 % (ADR 17)
  motif          obligatoire pour INCONNU et RENVOI, facultatif sinon

Regles appliquees, toutes issues de docs/decisions.md ADR 17 :
  - tarif differencie par plage horaire : on garde le dernier
    « par defaut : X par kwh de charge » ; a defaut, la plage la plus longue ;
    a egalite de duree, la premiere plage du texte ;
  - « par heure de charge » et « /min » pendant la charge font un MIXTE ;
    « occupation hors charge » est une penalite d'immobilisation, elle est
    relevee mais ne change pas le code ;
  - nombre nu sans unite, « cts » suivi d'un decimal, prix libelle au kW :
    INCONNU, on ne devine pas ;
  - hors de [0,05 ; 1,50] euro par kWh : INCONNU ;
  - booleen fuite dans le champ texte : RENVOI.
"""

K, M, X, S, G, R, I = "KWH", "MIN", "MIXTE", "SESSION", "GRATUIT", "RENVOI", "INCONNU"

CAS = {
    # --- renvois et non-information -------------------------------------
    1:  (R, None, None, None, None, None, False, "texte de renvoi vers l'application, aucun chiffre"),
    3:  (R, None, None, None, None, None, False, "annonce une tarification au kWh sans donner de prix"),
    4:  (R, None, None, None, None, None, False, "mot cle sans information"),
    6:  (R, None, None, None, None, None, False, "renvoi vers un site tiers"),
    7:  (R, None, None, None, None, None, False, "annonce une tarification au kWh sans donner de prix"),
    9:  (R, None, None, None, None, None, False, "tiret seul"),
    11: (R, None, None, None, None, None, False, "renvoi vers une grille externe"),
    13: (R, None, None, None, None, None, False, "renvoi vers un site tiers"),
    16: (R, None, None, None, None, None, False, "renvoi vers un site tiers"),
    24: (R, None, None, None, None, None, False, "renvoi vers un site tiers"),
    25: (R, None, None, None, None, None, False, "renvoi vers un site tiers"),
    29: (R, None, None, None, None, None, False, "mot cle sans information"),
    30: (R, None, None, None, None, None, False, "booleen fuite dans le champ texte"),
    33: (R, None, None, None, None, None, False, "annonce une tarification au kWh sans donner de prix"),
    36: (R, None, None, None, None, None, False, "mot cle sans information"),
    39: (R, None, None, None, None, None, False, "renvoi vers des conditions generales"),
    48: (R, None, None, None, None, None, False, "annonce une unite sans donner de prix"),
    51: (R, None, None, None, None, None, False, "formulation ambigue, ne dit pas si la recharge est gratuite pour tous"),
    55: (R, None, None, None, None, None, False, "booleen fuite dans le champ texte"),
    64: (R, None, None, None, None, None, False, "mot cle sans information"),
    70: (R, None, None, None, None, None, False, "renvoi vers un site tiers"),
    71: (R, None, None, None, None, None, False, "renvoi vers un site tiers"),

    # --- gratuit ---------------------------------------------------------
    74: (G, 0.0, None, None, None, None, False, "gratuite declaree sans condition"),

    # --- export structure, prix au kWh seul ------------------------------
    2:  (K, 0.30916667, None, None, None, 3.75, False, ""),
    18: (K, 0.39, None, None, None, 3.2, False, ""),
    23: (K, 0.33334, None, None, None, 15.0, False, ""),
    14: (K, 0.42, None, None, None, 6.0, False, ""),
    49: (K, 0.33334, None, None, None, 10.0, False, ""),
    52: (K, 0.41667, None, None, None, 20.0, False, ""),
    67: (K, 0.3342, None, None, None, 2.5, False, "aucun « par defaut », les deux plages donnent le meme prix"),
    68: (K, 0.2667, None, None, None, 6.0, False, ""),
    69: (K, 0.3917, None, None, None, 7.5, False, ""),
    83: (K, 0.42, None, None, None, 6.6667, False, ""),
    87: (K, 0.30916667, None, None, None, 2.5, False,
         "deux grilles concatenees ; le tarif d'occupation retenu est le premier de la chaine"),
    89: (K, 0.30916667, None, None, None, 3.75, False, "deux grilles concatenees, le « par defaut » kWh est unique"),
    92: (K, 0.333, None, None, None, None, False, ""),
    93: (K, 0.5, None, None, None, 10.0, False, ""),
    103: (K, 0.30916667, None, None, None, 3.75, False, "le « par defaut » final ne porte qu'un prix de depart a zero"),
    118: (K, 0.5416667, None, None, None, 6.0, False, ""),
    119: (K, 0.325, None, None, None, None, False, ""),
    130: (K, 0.1667, None, None, None, None, False, ""),
    134: (X, 0.3333, None, 3.0, None, 6.0, False,
          "deux grilles concatenees, le dernier « par defaut » kWh fait foi ; "
          "la seconde grille porte un tarif horaire de charge"),

    # --- export structure, prix au kWh plus temps de charge --------------
    5:  (X, 0.3333, None, 5.0, None, 5.0, False, ""),
    10: (X, 0.4667, None, 6.6667, None, 6.6667, False, ""),
    17: (X, 0.4167, None, 6.0, None, 6.0, False, ""),
    20: (X, 0.4667, None, 6.6667, None, 6.6667, False, ""),
    22: (X, 0.45833, None, 4.5, None, 4.5, False, ""),
    31: (X, 0.33334, None, 2.5, None, 2.5, False, ""),
    35: (X, 0.325, None, 6.6667, None, 6.6667, False, ""),
    38: (X, 0.4583, None, 6.0, None, 6.0, False, ""),
    42: (X, 0.325, None, 6.6667, None, 6.6667, False, ""),
    44: (X, 0.5, None, 1.0, None, 1.0, False, ""),
    45: (X, 0.20834, None, 4.0, None, 4.0, False,
         "le « par defaut » porte ici le tarif de nuit, plus bas que celui de jour : la regle est appliquee telle quelle"),
    46: (X, 0.3583, None, 6.6667, None, 6.6667, False, ""),
    53: (X, 0.49167, None, 6.667, None, 6.667, False,
         "le dernier « par defaut » ne porte pas de prix au kWh, on retient le dernier qui en porte un"),
    54: (X, 0.33334, None, 1.0, None, 1.0, False, ""),
    57: (X, 0.33334, None, 0.25, 1.25, 0.25, False, "« prix de depart » traite comme un forfait de session"),
    62: (X, 0.3333, None, 5.0, None, 5.0, False, "montants sans symbole euro"),
    66: (X, 0.33334, None, 2.5, None, 2.5, False, ""),
    82: (X, 0.4667, None, 6.6667, None, 6.6667, False, ""),
    85: (X, 0.333, None, 3.5, None, 3.5, False, "aucun « par defaut », les deux plages donnent le meme prix"),
    98: (X, 0.5667, None, 6.0, None, 6.0, False, ""),
    101: (X, 0.29167, None, 4.0, None, 4.0, False, "le « par defaut » porte le tarif de nuit"),
    107: (X, 0.43333334, None, 6.667, None, 6.667, False, ""),
    109: (X, 0.4583, None, 6.0, None, 6.0, False, "montants sans symbole euro"),
    112: (X, 0.4167, None, 6.0, None, 6.0, False, "montants sans symbole euro"),
    113: (X, 0.41667, None, 1.25, 1.66667, 1.25, False, "« prix de depart » traite comme un forfait de session"),
    117: (X, 0.5, None, 2.5, None, 2.5, False, ""),
    122: (X, 0.3333, None, 5.0, None, 5.0, False, "montants sans symbole euro"),

    # --- prix au kWh en texte libre --------------------------------------
    8:  (K, 0.36, None, None, None, None, False, "« cts » avec un entier : 36 centimes"),
    12: (K, 0.29, None, None, None, None, False, ""),
    15: (K, 0.49, None, None, None, None, False, "« cts » avec un entier"),
    19: (K, 0.59, None, None, None, None, False, "« cts » avec un entier"),
    21: (K, 0.59, None, None, None, None, False, "« cts » avec un entier"),
    26: (K, 0.39, None, None, None, None, False, ""),
    28: (K, 0.49, None, None, None, None, False, "« cts » avec un entier"),
    37: (K, 0.49, None, None, None, None, False, "« cts » avec un entier"),
    40: (K, 0.69, None, None, None, None, False, ""),
    41: (K, 0.59, None, None, None, None, False, "« cts » avec un entier"),
    43: (K, 0.45, None, None, None, None, False, ""),
    60: (K, 0.25, None, None, None, None, False, "« cts » avec un entier"),
    61: (K, 0.66, None, None, None, None, False, "TTC explicite"),
    63: (K, 0.75, None, None, None, None, False, "« e » mis pour euro"),
    65: (K, 0.40, None, None, None, None, False, "tarif non abonne, c'est le prix public"),
    76: (K, 0.42, None, None, None, None, False, "unite presente, symbole euro absent"),
    77: (K, 0.45, None, None, None, None, False, "TTC explicite"),
    78: (K, 0.54, None, None, None, None, False, ""),
    80: (K, 0.55, None, None, None, None, False, ""),
    81: (K, 0.55, None, None, None, None, False, "mojibake UTF-8 double, decodage deterministe de â‚¬ vers €"),
    88: (K, 0.55, None, None, None, None, False, ""),
    90: (K, 0.399, None, None, None, None, False, "« e » mis pour euro"),
    96: (K, 0.54, None, None, None, None, False, "TTC explicite"),
    97: (K, 0.38, None, None, None, None, False, ""),
    100: (K, 0.64, None, None, None, None, False, ""),
    104: (K, 0.25, None, None, None, None, False, ""),
    125: (K, 0.29, None, None, None, None, False,
          "le tarif a la minute ne court qu'en dehors des sessions de recharge, il est ignore"),
    127: (K, 0.42, None, None, None, None, False, "TTC explicite"),
    128: (K, 0.36, None, None, None, None, False, ""),
    129: (K, 0.39, None, None, None, None, False, ""),
    131: (K, 0.50, None, None, None, None, False, "« cts » avec un entier"),
    133: (K, 0.39, None, None, None, None, False, "tarif non abonne, c'est le prix public"),
    137: (K, 0.30, None, None, None, 2.4, False, "le tarif horaire ne court qu'apres la recharge"),
    138: (K, 0.47, None, None, None, None, False, "tarif non abonne, c'est le prix public"),
    140: (K, 0.38, None, None, None, None, False, ""),

    # --- prix HT, portes a TTC au taux de 20 % ---------------------------
    110: (K, 0.66, None, None, None, None, True, "0,55 HT"),
    114: (K, 0.504, None, None, None, None, True, "0,42 HT"),
    123: (K, 0.60, None, None, None, None, True, "0,50 HT"),
    135: (K, 1.50, None, None, None, None, True, "1,25 HT, exactement a la borne haute de plausibilite"),
    105: (X, 0.504, None, None, 0.60, None, True, "0,42 HT au kWh et 0,50 HT de frais de lancement"),
    139: (X, 0.504, None, None, 0.60, None, True, "0,42 HT au kWh et 0,50 HT de frais de lancement"),

    # --- mixtes en texte libre -------------------------------------------
    27: (X, 0.59, None, None, 2.0, None, False, "forfait de mise en route plus prix au kWh"),
    34: (X, 0.35, 0.03, None, None, None, False,
         "deux plages de douze heures, egalite de duree : on garde la premiere du texte"),
    50: (X, 0.32, 0.1, None, None, None, False,
         "deux prix au kWh dans le texte, 0.32 puis 0.032 ; on garde le premier et on le declare"),
    56: (X, 0.39, None, None, 1.0, None, False, "« E » mis pour euro"),
    58: (X, 0.32, 0.1, None, None, None, False, ""),
    72: (X, 0.32, 0.1, None, None, None, False, ""),
    73: (X, 0.32, 0.1, None, None, None, False, ""),
    75: (X, 0.32, 0.1, None, None, None, False, ""),
    79: (X, 0.50, 0.025, None, None, None, False, "tarif a la minute de la premiere heure"),
    91: (X, 0.30, None, None, 0.50, None, False, "forfait plus prix au kWh"),
    102: (X, 0.49, None, None, 1.0, None, False, "« E » mis pour euro, forfait de session"),
    106: (X, 0.32, 0.1, None, None, None, False, ""),
    111: (X, 0.299, 0.023, None, None, None, False, ""),
    116: (X, 0.17, 0.125, None, None, None, False, "unites presentes, symbole euro absent"),
    121: (X, 0.72, None, None, 2.0, None, False, "forfait de mise en route plus prix au kWh"),
    124: (X, 0.35, None, None, 0.25, None, False, "forfait plus prix au kWh"),

    # --- prix au temps seul ----------------------------------------------
    59: (M, None, 0.025, None, None, None, False, ""),

    # --- inconnus ---------------------------------------------------------
    32: (I, None, None, None, None, None, False, "nombre nu sans unite"),
    47: (I, None, None, None, None, None, False, "nombre nu sans unite"),
    84: (I, None, None, None, None, None, False, "nombre nu sans unite"),
    86: (I, None, None, None, None, None, False, "nombre nu sans unite"),
    94: (I, None, None, None, None, None, False, "nombre nu sans unite"),
    95: (I, None, None, None, None, None, False, "nombre nu sans unite"),
    99: (I, None, None, None, None, None, False, "nombre nu sans unite, et zero hors bornes de plausibilite"),
    108: (I, None, None, None, None, None, False, "nombre nu sans unite"),
    115: (I, None, None, None, None, None, False, "nombre nu sans unite"),
    120: (I, None, None, None, None, None, False, "nombre nu sans unite"),
    126: (I, None, None, None, None, None, False, "2 euros par kWh, hors bornes de plausibilite"),
    132: (I, None, None, None, None, None, False, "nombre nu sans unite"),
    136: (I, None, None, None, None, None, False, "nombre nu sans unite"),
}

# ---------------------------------------------------------------------------
# Queue de distribution : rangs 141 a 438. Ces valeurs pesent peu en nombre de
# PDC mais portent l'essentiel des pieges. Elles sont choisies pour couvrir
# chaque motif au moins une fois, pas pour leur frequence.
# ---------------------------------------------------------------------------

CAS.update({
    # renvois
    146: (R, None, None, None, None, None, False, "renvoi vers un site tiers"),
    147: (R, None, None, None, None, None, False, "booleen fuite dans le champ texte"),
    158: (R, None, None, None, None, None, False, "gratuite reservee a certains usagers, pas un tarif public"),
    181: (R, None, None, None, None, None, False, "renvoi vers un site tiers"),
    205: (R, None, None, None, None, None, False, "booleen fuite dans le champ texte"),
    233: (R, None, None, None, None, None, False, "renvoi vers un operateur d'itinerance"),
    272: (R, None, None, None, None, None, False, "mot cle sans information"),
    343: (R, None, None, None, None, None, False, "tarif reserve aux abonnes, pas le prix public"),
    345: (R, None, None, None, None, None, False, "tarif reserve aux usagers d'un reseau, pas le prix public"),
    346: (R, None, None, None, None, None, False, "tarif reserve aux usagers d'un reseau, pas le prix public"),
    349: (R, None, None, None, None, None, False, "tarif reserve aux abonnes, pas le prix public"),

    # prix au kWh, formes variees
    148: (K, 0.45, None, None, None, None, False, ""),
    150: (K, 0.35, None, None, None, None, False, "symbole euro absent, unite presente"),
    152: (K, 0.3917, None, None, None, None, False, ""),
    155: (K, 0.06, None, None, None, None, False, "« ct » avec un entier ; plage la plus longue, 6h a 22h"),
    156: (K, 1.0, None, None, None, None, False, "mojibake UTF-8 double"),
    161: (K, 0.519, None, None, None, None, False, "libelle en anglais"),
    164: (K, 0.55, None, None, None, None, False, "« cts » avec un entier"),
    167: (K, 0.40, None, None, None, None, False, "symbole euro absent"),
    168: (K, 0.42, None, None, None, None, False, "TTC explicite"),
    170: (K, 0.50, None, None, None, None, False, ""),
    172: (K, 0.45, None, None, None, None, False, "symbole euro absent"),
    173: (K, 0.54, None, None, None, None, False, "TTC explicite"),
    174: (K, 0.59, None, None, None, None, False, ""),
    179: (K, 0.375, None, None, None, None, False, ""),
    281: (X, 0.375, None, 25.0, None, 25.0, False,
          "le tarif horaire precede le prix au kWh dans la chaine"),
    185: (K, 0.79, None, None, None, None, False, ""),
    186: (K, 0.20, None, None, None, None, False, "mention AC sans tarif DC en face"),
    187: (K, 0.80, None, None, None, None, False, ""),
    188: (K, 0.36, None, None, None, None, False, ""),
    191: (K, 0.42, None, None, None, 6.0, False, ""),
    199: (K, 0.58, None, None, None, None, False, "tarif non abonne, c'est le prix public"),
    204: (K, 0.40, None, None, None, None, False, ""),
    207: (K, 0.40, None, None, None, None, False, ""),
    210: (K, 0.5, None, None, None, None, False, "plage la plus longue, 6h a 21h"),
    213: (K, 0.49, None, None, None, None, False, ""),
    222: (K, 0.42, None, None, None, None, False, "tarif non abonne"),
    228: (K, 0.30, None, None, None, None, False, "tarif non abonne"),
    229: (K, 0.30, None, None, None, None, False, ""),
    230: (K, 0.36, None, None, None, None, False, ""),
    231: (K, 0.45, None, None, None, None, False, "unite presente, symbole euro absent"),
    234: (K, 0.67, None, None, None, None, False, "TTC explicite"),
    235: (K, 0.50, None, None, None, None, False, ""),
    238: (K, 0.34, None, None, None, None, False, "symbole euro absent"),
    240: (K, 0.55, None, None, None, None, False, "deux plages de douze heures, on garde la premiere"),
    242: (K, 0.30, None, None, None, None, False, "TTC explicite"),
    250: (K, 0.43, None, None, None, None, False, ""),
    254: (K, 0.50, None, None, None, None, False, ""),
    256: (K, 0.66, None, None, None, None, False, "TTC explicite"),
    257: (K, 0.50, None, None, None, None, False, "TTC explicite"),
    259: (K, 0.78, None, None, None, None, False, "TTC explicite"),
    264: (K, 0.30, None, None, None, None, False, "mention AC sans tarif DC en face"),
    266: (K, 0.32, None, None, None, None, False, ""),
    267: (K, 0.40, None, None, None, None, False, ""),
    273: (K, 0.67, None, None, None, None, False, ""),
    274: (K, 0.45, None, None, None, None, False, ""),
    276: (K, 0.60, None, None, None, 3.6, False, "le tarif horaire ne court qu'apres la recharge"),
    277: (K, 0.22, None, None, None, None, False, "espace en tete de chaine"),
    282: (K, 0.37, None, None, None, None, False, "TTC explicite"),
    283: (K, 0.39, None, None, None, None, False, ""),
    285: (K, 0.46, None, None, None, None, False, ""),
    286: (K, 0.30, None, None, None, None, False, "tarif non abonne"),
    289: (K, 0.30, None, None, None, None, False, "tarif non abonne"),
    292: (K, 0.39, None, None, None, None, False, "« cts » avec un entier"),
    296: (K, 0.70, None, None, None, None, False, ""),
    299: (K, 0.348, None, None, None, None, False, "TTC explicite"),
    300: (K, 0.42, None, None, None, None, False, "TTC explicite"),
    302: (K, 0.60, None, None, None, None, False, ""),
    307: (K, 0.45, None, None, None, 10.0, False, ""),
    318: (K, 0.25, None, None, None, None, False, "« cts » avec un entier"),
    319: (K, 0.55, None, None, None, None, False, "symbole euro absent"),
    320: (K, 0.35, None, None, None, None, False, "symbole euro absent"),
    321: (K, 0.50, None, None, None, None, False, "symbole euro absent"),
    325: (K, 0.32, None, None, None, None, False, "tarif non abonne"),
    326: (K, 0.66, None, None, None, None, False, "unite collee au nombre"),
    333: (K, 1.20, None, None, None, None, False, "TTC explicite"),
    340: (K, 0.15, None, None, None, None, False, "tarif non abonne"),
    341: (K, 0.20, None, None, None, None, False, ""),
    344: (K, 0.2668, None, None, None, None, False, "symbole euro absent"),
    350: (K, 0.50, None, None, None, None, False, "formulation fautive, unite presente"),
    352: (K, 0.32, None, None, None, None, False, ""),
    354: (K, 0.20, None, None, None, None, False, "mention AC sans tarif DC en face"),
    357: (K, 0.30, None, None, None, None, False, "zeros parasites en fin de chaine"),
    362: (K, 0.38, None, None, None, None, False, ""),
    364: (K, 0.40, None, None, None, None, False, "tarif non abonne"),
    368: (K, 0.35, None, None, None, None, False, ""),
    369: (K, 0.51, None, None, None, None, False, ""),
    375: (K, 0.43, None, None, None, None, False, ""),
    380: (K, 0.3475, None, None, None, None, False, ""),
    381: (K, 0.3475, None, None, None, None, False, ""),
    382: (K, 0.40, None, None, None, None, False, "symbole euro absent"),
    383: (K, 0.30, None, None, None, None, False, ""),
    384: (K, 0.40, None, None, None, None, False, "« cts » avec un entier, libelle « par kWh »"),
    387: (K, 0.50, None, None, None, None, False, ""),
    388: (K, 0.50, None, None, None, None, False, ""),
    390: (K, 0.42, None, None, None, None, False, ""),
    391: (K, 0.38, None, None, None, None, False, ""),
    392: (K, 0.06, None, None, None, None, False, "« ct » avec un entier ; plage la plus longue"),
    396: (K, 0.16, None, None, None, None, False, "plage la plus longue, 6h30 a 20h30"),
    397: (K, 0.13, None, None, None, None, False, "plage la plus longue, 7h30 a 21h30"),
    398: (K, 0.13, None, None, None, None, False, ""),
    399: (K, 0.35, None, None, None, None, False,
          "la plage la plus longue est celle de nuit, 17h a 8h : la regle est appliquee telle quelle"),
    400: (K, 0.50, None, None, None, None, False, ""),
    404: (K, 0.384, None, None, None, None, False, "TTC explicite"),
    408: (K, 0.35, None, None, None, None, False, ""),
    418: (K, 0.42, None, None, None, 6.0, False, ""),
    419: (K, 0.42, None, None, None, 6.0, False, ""),
    434: (K, 0.35, None, None, None, 6.6667, False, ""),
    437: (K, 0.25, None, None, None, None, False, "« kW h » normalise en kWh avant d'appliquer la regle du kW"),

    # prix HT portes a TTC
    145: (K, 0.504, None, None, None, None, True, "0,42 HT"),
    154: (K, 0.54, None, None, None, None, True, "0,45 HT"),
    182: (K, 0.60, None, None, None, None, False, "TTC explicite malgre l'absence d'espace"),
    183: (K, 1.20, None, None, None, None, True, "1 HT"),
    184: (K, 0.444, None, None, None, None, True, "0,37 HT"),
    197: (K, 0.384, None, None, None, None, True, "0,32 HT"),
    198: (K, 0.42, None, None, None, None, True, "0,35 HT"),
    226: (K, 0.552, None, None, None, None, True, "0,46 HT"),
    227: (K, 0.47, None, None, None, None, False, "TTC explicite"),
    258: (K, 0.504, None, None, None, None, True, "0,42 HT"),
    260: (K, 0.636, None, None, None, None, True, "0,53 HT"),
    269: (K, 0.252, None, None, None, None, True, "0,21 HT, « HTVA » lu comme hors taxes"),
    270: (K, 0.60, None, None, None, None, True, "0,5 HT, « HTVA » lu comme hors taxes"),
    334: (K, 1.50, None, None, None, None, True, "1,25 HT, exactement a la borne haute"),
    335: (K, 0.996, None, None, None, None, True, "0,83 HT"),
    336: (K, 0.804, None, None, None, None, True, "0,67 HT"),
    337: (K, 0.47, None, None, None, None, False, "TTC explicite"),
    338: (K, 0.60, None, None, None, None, True, "0,50 HT"),
    438: (K, 0.66, None, None, None, None, True, "0,55 HT"),

    # mixtes
    149: (X, 0.30, 0.10, None, None, None, False, "tarif non abonne"),
    190: (X, 0.50, 0.02, None, None, None, False, "symbole euro absent"),
    200: (X, 0.29, None, None, 1.0, None, False, "symbole euro absent"),
    211: (X, 0.60, 0.03, None, None, None, False, "deux plages de douze heures, on garde la premiere"),
    223: (X, 0.20, 0.01, None, None, None, False, "premiere heure gratuite, non modelisee"),
    224: (X, 0.35, None, None, 0.25, None, False, "frais de connexion plus prix au kWh"),
    236: (X, 0.504, 0.096, None, None, None, True, "0,42 HT au kWh et 0,08 HT a la minute"),
    239: (X, 0.35, 0.03, None, None, None, False, "plage la plus longue, 6h a 21h"),
    241: (X, 0.30, 0.03, None, None, None, False, "plages incoherentes dans la source, on garde la premiere"),
    243: (X, 0.19, 0.03, None, None, None, False, ""),
    262: (X, 0.27, 0.10, None, None, None, False, "tarif non abonne"),
    268: (X, 0.48, 0.05, None, 0.99, None, False, "plage la plus longue, 8h a 22h ; frais d'activation"),
    271: (X, 0.30, None, None, 0.50, None, False, ""),
    288: (X, 0.50, 0.10, None, None, None, False, "tarif a la minute au-dela de soixante minutes"),
    290: (X, 0.35, 0.05, None, None, None, False, "symbole euro absent"),
    293: (X, 0.26, 0.03, None, None, None, False, "deux plages de douze heures, on garde la premiere"),
    295: (X, 0.60, 0.03, None, None, None, False, "plage la plus longue, 6h a 19h"),
    363: (X, 0.40, 0.06, None, None, None, False, "« e » mis pour euro"),
    393: (X, 0.40, 0.03, None, None, None, False, "deux plages de douze heures, on garde la premiere"),
    394: (X, 0.25, None, None, 2.0, None, False, "deux plages de douze heures, on garde la premiere"),
    395: (X, 0.35, 0.03, None, None, None, False, ""),
    407: (X, 0.19, 0.03, None, None, None, False, ""),

    # prix au temps seul
    160: (M, None, None, 1.0, None, 1.0, False, "aucun prix au kWh, seulement un tarif horaire de charge"),
    169: (M, None, None, 2.508, None, None, True, "2,09 HT par heure, mojibake UTF-8 double"),
    203: (M, None, 0.0417, None, None, None, False, ""),
    237: (M, None, 0.06, None, None, None, False, "symbole euro absent"),
    263: (M, None, 0.05, None, None, None, False, "mention AC"),
    342: (M, None, None, 2.508, None, None, True, "2,09 HT par heure"),
    355: (M, None, None, 3.0, None, None, False, ""),
    356: (M, None, 0.04, None, None, None, False, ""),
    358: (M, None, 0.10, None, None, None, False, ""),
    374: (M, None, 0.12, None, None, None, False, "symbole euro absent"),
    402: (M, None, 0.14, None, None, None, False, ""),

    # forfait de session seul
    339: (S, None, None, None, 10.0, None, False, "forfait de depart, aucun prix a l'energie"),

    # inconnus
    151: (I, None, None, None, None, None, False, "aucun prix a l'energie, seulement un prix de depart nul"),
    153: (I, None, None, None, None, None, False, "« cts » suivi d'un decimal, lecture litterale implausible"),
    162: (I, None, None, None, None, None, False, "nombre nu sans unite"),
    163: (I, None, None, None, None, None, False, "nombre nu sans unite"),
    196: (I, None, None, None, None, None, False, "« cts » suivi d'un decimal"),
    201: (I, None, None, None, None, None, False, "prix libelle au kW, pas au kWh"),
    202: (I, None, None, None, None, None, False, "nombre nu sans unite"),
    206: (I, None, None, None, None, None, False, "montant sans unite"),
    208: (I, None, None, None, None, None, False, "prix libelle au kW, pas au kWh"),
    209: (I, None, None, None, None, None, False, "0,0417 par kWh, sous la borne basse de plausibilite"),
    214: (I, None, None, None, None, None, False, "nombre nu sans unite"),
    225: (I, None, None, None, None, None, False, "« cts » suivi d'un decimal"),
    232: (I, None, None, None, None, None, False, "nombre nu sans unite"),
    255: (I, None, None, None, None, None, False, "chaine inexploitable"),
    261: (I, None, None, None, None, None, False, "nombre nu sans unite"),
    265: (I, None, None, None, None, None, False, "prix libelle au kW, pas au kWh"),
    278: (I, None, None, None, None, None, False, "nombre nu sans unite"),
    279: (I, None, None, None, None, None, False, "montant sans unite"),
    294: (I, None, None, None, None, None, False, "0,0417 par kWh, sous la borne basse"),
    301: (I, None, None, None, None, None, False, "montant sans unite"),
    309: (I, None, None, None, None, None, False, "aucun prix a l'energie"),
    322: (I, None, None, None, None, None, False, "prix libelle au kW, pas au kWh"),
    323: (I, None, None, None, None, None, False, "nombre nu sans unite"),
    324: (I, None, None, None, None, None, False, "2 euros par kWh, hors bornes de plausibilite"),
    327: (I, None, None, None, None, None, False, "« cts » suivi d'un decimal"),
    328: (I, None, None, None, None, None, False, "« cts » suivi d'un decimal"),
    329: (I, None, None, None, None, None, False, "« cts » suivi d'un decimal"),
    330: (I, None, None, None, None, None, False, "« cts » suivi d'un decimal"),
    331: (I, None, None, None, None, None, False, "« cts » suivi d'un decimal"),
    332: (I, None, None, None, None, None, False, "« cts » suivi d'un decimal"),
    353: (I, None, None, None, None, None, False, "2 euros par kWh, hors bornes de plausibilite"),
    359: (I, None, None, None, None, None, False, "montant sans unite"),
    360: (I, None, None, None, None, None, False, "nombre nu sans unite"),
    361: (I, None, None, None, None, None, False, "nombre nu sans unite"),
    365: (I, None, None, None, None, None, False, "nombre nu sans unite"),
    367: (I, None, None, None, None, None, False, "nombre nu sans unite"),
    370: (I, None, None, None, None, None, False, "unite « kw/h » ambigue"),
    371: (I, None, None, None, None, None, False, "nombre nu sans unite"),
    372: (I, None, None, None, None, None, False, "nombre nu sans unite"),
    373: (I, None, None, None, None, None, False, "montant sans unite"),
    376: (I, None, None, None, None, None, False, "prix libelle au kW, pas au kWh"),
    377: (I, None, None, None, None, None, False, "nombre nu sans unite exploitable"),
    378: (I, None, None, None, None, None, False, "montant sans unite"),
    385: (I, None, None, None, None, None, False, "nombre nu sans unite"),
    401: (I, None, None, None, None, None, False, "nombre nu sans unite"),
    405: (I, None, None, None, None, None, False, "prix libelle au kW, pas au kWh"),
    406: (I, None, None, None, None, None, False, "prix libelle au kW, pas au kWh"),
    436: (I, None, None, None, None, None, False, "montant sans unite"),
})

# Tarifs differencies AC et DC dans la meme chaine (ADR 17 : on garde la
# structure, le rattachement se fait plus tard selon la classe du PDC).
# Valeur : (prix_kwh_ac, prix_kwh_dc), None quand la valeur est hors bornes.
CAS.update({
    193: (K, 0.39, None, None, None, None, False, "blob JSON d'operateur, champ energyPrice"),
    194: (K, 0.51, None, None, None, None, False, "blob JSON d'operateur, champ energyPrice"),
    195: (K, 0.55, None, None, None, None, False, "blob JSON d'operateur, champ energyPrice"),
})

CAS_AC_DC = {
    351: (1.0, None),   # « AC 1€/kWh - DC 5€/kWh » : 5 hors bornes, ecarte et compte
    403: (0.30, 0.50),  # « 0.30€/kwh ... pour point 22AC - 0.50€/kwh ... 50DC »
}
CAS.update({
    351: (K, None, None, None, None, None, False,
          "tarifs AC et DC distincts ; le tarif DC de 5 euros est hors bornes, ecarte et compte"),
    403: (X, None, 0.025, None, None, None, False,
          "tarifs AC et DC distincts, meme tarif a la minute"),
})
