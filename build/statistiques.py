#!/usr/bin/env python3
"""Fonctions de calcul de l'edition : medianes, bandes, Theil-Sen, backtest.

Ecrites en Python pur, sans numpy, pour une raison precise : la page recalcule
un territoire dans le navigateur, en JavaScript, sur la matrice embarquee
(spec 3.2). Le meme algorithme doit tourner des deux cotes, sinon l'ecart entre
le chiffre France du build et celui du navigateur mesurerait une difference de
convention et non une propriete des donnees. Les tests de
tests/test_statistiques.py confrontent chaque fonction a numpy et scipy.

Conventions fixees ici, et pas heritees d'un defaut de bibliotheque :

  - quantile par interpolation lineaire entre les deux ordres encadrants
    (method="linear" de numpy, type 7 de R) ;
  - mediane = quantile a 0,5, donc moyenne des deux valeurs centrales sur un
    effectif pair ;
  - Theil-Sen : pente = mediane des pentes de toutes les paires d'abscisses
    distinctes ; ordonnee = mediane(y) moins pente fois mediane(x), ce que
    scipy appelle method="separate" ;
  - aucune fonction ne fabrique un jour manquant, sauf
    report_derniere_valeur, qui est bornee et rend le compte de ce qu'elle a
    reporte.

Les valeurs non finies et les None sont ecartes en entree de chaque fonction,
et n'entrent donc pas dans les effectifs annonces.
"""
from __future__ import annotations

import math

SEUIL_EFFECTIF = 30
QUANTILES_BANDE = (("p10", 0.10), ("p25", 0.25), ("p50", 0.50),
                   ("p75", 0.75), ("p90", 0.90))


def _propres(valeurs) -> list[float]:
    """Ne garde que des nombres finis. Ce qui n'est pas un nombre n'est pas une
    valeur manquante a imputer : c'est une valeur a ne pas compter."""
    out = []
    for v in valeurs:
        if v is None:
            continue
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if math.isfinite(f):
            out.append(f)
    return out


# ---------------------------------------------------------------------------
# Medianes et quantiles
# ---------------------------------------------------------------------------

def quantile(valeurs, q: float) -> float | None:
    """Quantile par interpolation lineaire, sur les valeurs finies.

    Identique a numpy.quantile(..., method="linear"). Renvoie None si aucune
    valeur exploitable : on prefere l'absence a un zero qui se ferait passer
    pour une mesure.
    """
    x = sorted(_propres(valeurs))
    n = len(x)
    if n == 0:
        return None
    if n == 1:
        return x[0]
    if not 0.0 <= q <= 1.0:
        raise ValueError(f"quantile hors de [0 ; 1] : {q}")
    h = (n - 1) * q
    bas = math.floor(h)
    haut = min(bas + 1, n - 1)
    frac = h - bas
    return x[bas] + frac * (x[haut] - x[bas])


def mediane(valeurs) -> float | None:
    return quantile(valeurs, 0.5)


def bande(valeurs) -> dict:
    """p10, p25, p50, p75, p90 et effectif.

    Sous le seuil d'effectif, l'effectif est rendu mais aucun quantile ne
    l'est : la spec interdit d'afficher une mediane sur une case trop mince,
    et c'est ici que le refus doit se decider, pas a l'affichage.
    """
    x = _propres(valeurs)
    sortie: dict = {"n": len(x)}
    assez = len(x) >= SEUIL_EFFECTIF
    for nom, q in QUANTILES_BANDE:
        sortie[nom] = quantile(x, q) if assez else None
    return sortie


def ecreter(valeurs, q_bas: float = 0.02, q_haut: float = 0.98):
    """Ramene les valeurs dans [q_bas ; q_haut] observes. Rend le compte.

    Les flux contiennent des valeurs bouchon, jusqu'a 160 000 kW declares pour
    une puissance nominale. Sans ecretage, une echelle de couleur devient
    illisible. On ne supprime rien : on borne, et on dit combien de valeurs ont
    ete touchees.
    """
    x = _propres(valeurs)
    if not x:
        return [], 0
    bas = quantile(x, q_bas)
    haut = quantile(x, q_haut)
    if bas > haut:
        bas, haut = haut, bas
    sortie = [min(max(v, bas), haut) for v in x]
    touchees = sum(1 for v in x if v < bas or v > haut)
    return sortie, touchees


# ---------------------------------------------------------------------------
# Theil-Sen
# ---------------------------------------------------------------------------

def theil_sen(x, y):
    """Pente et ordonnee a l'origine par la mediane des pentes par paires.

    Les paires de meme abscisse sont ignorees : leur pente serait infinie.
    Renvoie (None, None) s'il n'y a pas au moins deux abscisses distinctes.

    Cout en O(n^2) paires, assume : les fenetres du projet font 30 points,
    soit 435 paires.
    """
    xs, ys = [], []
    for a, b in zip(x, y):
        a, b = _propres([a]), _propres([b])
        if a and b:
            xs.append(a[0])
            ys.append(b[0])
    n = len(xs)
    if n < 2:
        return None, None

    pentes = []
    for i in range(n):
        for j in range(i + 1, n):
            dx = xs[j] - xs[i]
            if dx != 0.0:
                pentes.append((ys[j] - ys[i]) / dx)
    if not pentes:
        return None, None

    pente = quantile(pentes, 0.5)
    ordonnee = quantile(ys, 0.5) - pente * quantile(xs, 0.5)
    return pente, ordonnee


# ---------------------------------------------------------------------------
# Projection et backtest
# ---------------------------------------------------------------------------

def _fenetre(serie: dict, origine: int, fenetre: int) -> list[int]:
    """Jours presents dans les `fenetre` jours qui precedent `origine`, inclus.

    Un jour absent reste absent : la fenetre peut donc contenir moins de
    `fenetre` points, et c'est a l'appelant de decider si cela suffit.
    """
    return sorted(j for j in serie if origine - fenetre < j <= origine)


def projeter(serie: dict, horizons, fenetre: int = 30) -> dict:
    """Prolonge la tendance des `fenetre` derniers jours aux horizons demandes.

    C'est une extrapolation de pente, pas un modele : elle ne vaut que
    accompagnee de la bande de backtest.
    """
    if not serie:
        return {h: None for h in horizons}
    dernier = max(serie)
    jours = _fenetre(serie, dernier, fenetre)
    pente, ordonnee = theil_sen(jours, [serie[j] for j in jours])
    if pente is None:
        return {h: None for h in horizons}
    return {h: ordonnee + pente * (dernier + h) for h in horizons}


def backtest(serie: dict, horizons, fenetre: int = 30) -> dict:
    """Bande d'incertitude mesuree, pas estimee.

    Pour chaque horizon, on rejoue la methode depuis chaque origine passee ou
    la fenetre est complete et ou la valeur cible est connue, et on releve
    l'erreur reellement commise. La bande est le p10 et le p90 de ces erreurs,
    accompagnes de leur effectif. Quand aucune origine ne remplit ces
    conditions, la reponse est None : on n'affiche pas de bande faute de
    pouvoir en mesurer une.
    """
    sortie = {}
    jours = sorted(serie)
    for h in horizons:
        erreurs = []
        for origine in jours:
            fen = _fenetre(serie, origine, fenetre)
            if len(fen) < fenetre or (origine + h) not in serie:
                continue
            pente, ordonnee = theil_sen(fen, [serie[j] for j in fen])
            if pente is None:
                continue
            prevu = ordonnee + pente * (origine + h)
            erreurs.append(serie[origine + h] - prevu)
        if not erreurs:
            sortie[h] = None
            continue
        sortie[h] = (quantile(erreurs, 0.10), quantile(erreurs, 0.90), len(erreurs))
    return sortie


# ---------------------------------------------------------------------------
# Imputation bornee
# ---------------------------------------------------------------------------

def report_derniere_valeur(serie: dict, n_jours: int):
    """Comble les trous depuis la derniere valeur connue, au plus n_jours.

    Trois limites, qui sont le sujet meme de la fonction :
      - au-dela de n_jours, le trou reste un trou ;
      - rien n'est interpole depuis la valeur suivante, seule la precedente
        est reportee ;
      - rien n'est ajoute apres le dernier jour observe, prolonger la serie
        serait une prevision deguisee en imputation.

    Rend la serie completee et le nombre de jours reellement fabriques.
    """
    if not serie:
        return {}, 0
    sortie = dict(serie)
    if n_jours <= 0:
        return sortie, 0
    jours = sorted(serie)
    reportes = 0
    for precedent, suivant in zip(jours, jours[1:]):
        limite = min(precedent + n_jours, suivant - 1)
        for j in range(precedent + 1, limite + 1):
            sortie[j] = serie[precedent]
            reportes += 1
    return sortie, reportes
