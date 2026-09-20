#!/usr/bin/env python3
"""Tests des fonctions de calcul, ecrits AVANT l'implementation.

Ce fichier definit le contrat de build/statistiques.py et le confronte a
numpy et scipy, comme l'exige le 9.4 de la spec. Il echoue tant que le module
n'existe pas : c'est l'etat normal au moment ou il est ecrit.

Pourquoi reimplementer ce que numpy sait deja faire
---------------------------------------------------
Parce que la page recalcule un territoire dans le navigateur, en JavaScript,
sur la matrice embarquee (spec 3.2). Si le build appelait numpy et que le
navigateur appelait autre chose, l'ecart entre les deux chiffres France serait
un artefact de convention de quantile, pas une propriete des donnees. Les
fonctions sont donc ecrites en Python pur, avec une convention explicite, et
ces tests verifient qu'elles rendent exactement ce que numpy rend. Le meme
algorithme sera transpose en JavaScript et compare aux memes references.

Convention de quantile : interpolation lineaire entre les deux ordres les plus
proches, ce que numpy appelle method="linear" et R le type 7. C'est le defaut
de numpy ; il est fixe ici pour ne pas dependre d'un defaut.

Contrat attendu
---------------
    from build.statistiques import (
        SEUIL_EFFECTIF, mediane, quantile, bande, ecreter,
        theil_sen, projeter, backtest, report_derniere_valeur)

    mediane(valeurs)                  -> float | None
    quantile(valeurs, q)              -> float | None
    bande(valeurs)                    -> dict avec p10 p25 p50 p75 p90 et n
    ecreter(valeurs, 0.02, 0.98)      -> (valeurs_ecretees, nb_ecretes)
    theil_sen(x, y)                   -> (pente, ordonnee)
    projeter(serie, horizons, fenetre)-> dict horizon -> valeur projetee
    backtest(serie, horizons, fenetre)-> dict horizon -> (p10, p90, n)
    report_derniere_valeur(serie, n)  -> (serie_completee, nb_reports)

Les series sont des dictionnaires {jour_entier: valeur}. Un jour absent est
absent : aucune fonction n'a le droit de le fabriquer, sauf
report_derniere_valeur, qui ne le fait que dans la limite de n jours et rend
le compte de ce qu'elle a reporte.

Trois points du contrat de report, qui se lisent dans les assertions :
  - un trou est comble depuis la derniere valeur connue, au plus n jours ;
  - au-dela de n jours, le trou reste un trou, il n'est pas interpole depuis
    la valeur suivante ;
  - rien n'est reporte apres le dernier jour observe : prolonger la serie
    dans le futur serait une prevision deguisee, pas une imputation.

Couverture : la spec exige 100 % des fonctions de calcul. Elle se mesure avec
    python -m coverage run tests/test_statistiques.py && python -m coverage report
une fois build/statistiques.py ecrit.

Lancement : python tests/test_statistiques.py
"""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

import numpy as np
from scipy import stats

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

TOL = 1e-9
echecs: list[str] = []


def verifier(nom: str, condition: bool, detail: str = "") -> None:
    if not condition:
        echecs.append(f"{nom}{' : ' + detail if detail else ''}")


def proche(a, b, tol=TOL) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) <= tol * max(1.0, abs(a), abs(b))


# ---------------------------------------------------------------------------
# Jeux d'essai
# ---------------------------------------------------------------------------

def echantillons() -> list[tuple[str, list[float]]]:
    rng = random.Random(20260917)
    jeux = [
        ("impair court", [3.0, 1.0, 2.0]),
        ("pair court", [4.0, 1.0, 3.0, 2.0]),
        ("un seul element", [0.42]),
        ("deux elements", [0.30, 0.50]),
        ("valeurs identiques", [0.33] * 17),
        ("beaucoup d'ex aequo", [0.22, 0.22, 0.22, 0.45, 0.45, 0.90]),
        ("negatifs et zero", [-3.0, -1.0, 0.0, 2.0, 5.0]),
        ("tres disperse", [0.05, 0.06, 0.07, 1.40, 1.50]),
        ("deja trie", [float(i) / 10 for i in range(1, 41)]),
        ("trie a l'envers", [float(i) / 10 for i in range(40, 0, -1)]),
    ]
    for n in (30, 31, 100, 101, 1000):
        jeux.append((f"aleatoire n={n}",
                     [round(rng.uniform(0.05, 1.5), 6) for _ in range(n)]))
    # distribution realiste de prix au kWh, avec une queue longue
    jeux.append(("prix realistes", [round(rng.gauss(0.42, 0.09), 6) for _ in range(400)]
                 + [1.45, 1.48, 0.051, 0.052]))
    return jeux


def series() -> list[tuple[str, dict[int, float]]]:
    rng = random.Random(4242)
    droite = {j: 100.0 + 0.5 * j for j in range(60)}
    bruitee = {j: 100.0 + 0.5 * j + rng.gauss(0, 1.5) for j in range(60)}
    trouee = {j: 100.0 + 0.5 * j + rng.gauss(0, 1.5) for j in range(60) if j % 7 != 3}
    aberrante = dict(bruitee)
    for j in (5, 17, 41):
        aberrante[j] = aberrante[j] + 60.0        # valeurs bouchon
    plate = {j: 7.98 for j in range(60)}
    descendante = {j: 300.0 - 1.2 * j + rng.gauss(0, 2.0) for j in range(60)}
    return [
        ("droite exacte", droite),
        ("droite bruitee", bruitee),
        ("serie trouee", trouee),
        ("serie avec valeurs bouchon", aberrante),
        ("serie plate", plate),
        ("serie descendante", descendante),
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def tester_mediane_et_quantiles(m) -> None:
    for nom, x in echantillons():
        a = np.asarray(x, dtype=float)
        verifier(f"mediane [{nom}]", proche(m.mediane(x), float(np.median(a))),
                 f"attendu {float(np.median(a))!r}, obtenu {m.mediane(x)!r}")
        for q in (0.01, 0.02, 0.10, 0.25, 0.50, 0.75, 0.90, 0.98, 0.99):
            attendu = float(np.quantile(a, q, method="linear"))
            obtenu = m.quantile(x, q)
            verifier(f"quantile p{q} [{nom}]", proche(obtenu, attendu),
                     f"attendu {attendu!r}, obtenu {obtenu!r}")

    verifier("mediane d'une liste vide", m.mediane([]) is None)
    verifier("quantile d'une liste vide", m.quantile([], 0.5) is None)

    # l'ordre d'entree ne doit rien changer
    rng = random.Random(7)
    x = [round(rng.uniform(0, 1), 6) for _ in range(99)]
    y = x[:]
    rng.shuffle(y)
    verifier("mediane insensible a l'ordre", proche(m.mediane(x), m.mediane(y)))

    # une valeur extreme ne deplace pas la mediane de plus d'un cran
    base = [0.40, 0.41, 0.42, 0.43, 0.44]
    verifier("mediane robuste a une valeur bouchon",
             proche(m.mediane(base + [999.0]), (0.42 + 0.43) / 2))

    # jamais de moyenne deguisee : sur une serie asymetrique les deux different
    asym = [1.0] * 9 + [100.0]
    verifier("la mediane n'est pas la moyenne",
             proche(m.mediane(asym), 1.0) and abs(float(np.mean(asym)) - 1.0) > 1)


def tester_bande(m) -> None:
    rng = random.Random(11)
    x = [round(rng.uniform(0.05, 1.5), 6) for _ in range(250)]
    a = np.asarray(x, dtype=float)
    b = m.bande(x)
    for cle, q in (("p10", 0.10), ("p25", 0.25), ("p50", 0.50),
                   ("p75", 0.75), ("p90", 0.90)):
        attendu = float(np.quantile(a, q, method="linear"))
        verifier(f"bande {cle}", proche(b.get(cle), attendu),
                 f"attendu {attendu!r}, obtenu {b.get(cle)!r}")
    verifier("bande n", b.get("n") == 250)
    verifier("bande ordonnee",
             b["p10"] <= b["p25"] <= b["p50"] <= b["p75"] <= b["p90"])

    # sous le seuil d'effectif, la bande refuse de conclure
    petit = m.bande(x[:m.SEUIL_EFFECTIF - 1])
    verifier("bande sous le seuil d'effectif",
             petit.get("p50") is None and petit.get("n") == m.SEUIL_EFFECTIF - 1,
             f"obtenu {petit!r}")
    juste = m.bande(x[:m.SEUIL_EFFECTIF])
    verifier("bande juste au seuil", juste.get("p50") is not None)


def tester_ecretage(m) -> None:
    x = [0.40] * 100 + [0.001, 0.002, 9.0, 12.0]
    a = np.asarray(x, dtype=float)
    bas = float(np.quantile(a, 0.02, method="linear"))
    haut = float(np.quantile(a, 0.98, method="linear"))
    sortie, n = m.ecreter(x, 0.02, 0.98)
    verifier("ecretage : rien n'est hors bornes",
             min(sortie) >= bas - TOL and max(sortie) <= haut + TOL)
    verifier("ecretage : longueur conservee", len(sortie) == len(x))
    verifier("ecretage : nombre de valeurs touchees compte", n == 4,
             f"attendu 4, obtenu {n}")
    inchange, n0 = m.ecreter([0.4] * 50, 0.02, 0.98)
    verifier("ecretage : serie homogene intacte", n0 == 0)


def tester_theil_sen(m) -> None:
    for nom, serie in series():
        xs = sorted(serie)
        ys = [serie[j] for j in xs]
        ref = stats.theilslopes(ys, xs)
        pente, ordonnee = m.theil_sen(xs, ys)
        verifier(f"theil-sen pente [{nom}]", proche(pente, float(ref[0]), 1e-9),
                 f"attendu {float(ref[0])!r}, obtenu {pente!r}")
        verifier(f"theil-sen ordonnee [{nom}]", proche(ordonnee, float(ref[1]), 1e-9),
                 f"attendu {float(ref[1])!r}, obtenu {ordonnee!r}")

    # droite exacte : la pente doit etre exacte, pas approchee
    xs = list(range(40))
    ys = [3.0 + 0.25 * j for j in xs]
    pente, ordonnee = m.theil_sen(xs, ys)
    verifier("theil-sen sur droite exacte", proche(pente, 0.25) and proche(ordonnee, 3.0))

    # resistance aux valeurs bouchon : moins de 29 % de contamination ne doit
    # pas emporter la pente, la ou une regression des moindres carres cede
    ys2 = ys[:]
    for j in range(0, 40, 5):                      # 8 points sur 40, soit 20 %
        ys2[j] += 500.0
    pente2, _ = m.theil_sen(xs, ys2)
    mc = float(np.polyfit(xs, ys2, 1)[0])
    verifier("theil-sen resiste ou les moindres carres cedent",
             abs(pente2 - 0.25) < 0.05 and abs(mc - 0.25) > 0.5,
             f"theil-sen {pente2!r}, moindres carres {mc!r}")

    # abscisses en double : les paires de meme x sont ignorees, comme scipy
    xs3 = [0, 0, 1, 2, 2, 3]
    ys3 = [1.0, 2.0, 3.0, 5.0, 4.0, 7.0]
    ref3 = stats.theilslopes(ys3, xs3)
    p3, o3 = m.theil_sen(xs3, ys3)
    verifier("theil-sen avec abscisses en double",
             proche(p3, float(ref3[0])) and proche(o3, float(ref3[1])),
             f"attendu {(float(ref3[0]), float(ref3[1]))!r}, obtenu {(p3, o3)!r}")

    verifier("theil-sen refuse moins de deux points", m.theil_sen([1], [2.0]) == (None, None))


def tester_projection_et_backtest(m) -> None:
    rng = random.Random(99)
    serie = {j: 1000.0 + 2.0 * j + rng.gauss(0, 4.0) for j in range(120)}
    horizons = [1, 7, 30]

    # projection : meme resultat qu'un theil-sen sur la fenetre, prolonge
    proj = m.projeter(serie, horizons, fenetre=30)
    dernier = max(serie)
    xs = [j for j in sorted(serie) if dernier - 30 < j <= dernier]
    ys = [serie[j] for j in xs]
    ref = stats.theilslopes(ys, xs)
    for h in horizons:
        attendu = float(ref[1]) + float(ref[0]) * (dernier + h)
        verifier(f"projection h={h}", proche(proj.get(h), attendu, 1e-9),
                 f"attendu {attendu!r}, obtenu {proj.get(h)!r}")

    # backtest : p10 et p90 des erreurs reellement commises, rejouees depuis
    # chaque origine passee ou la fenetre est complete et la cible connue
    bt = m.backtest(serie, horizons, fenetre=30)
    for h in horizons:
        erreurs = []
        for origine in sorted(serie):
            fen = [j for j in sorted(serie) if origine - 30 < j <= origine]
            if len(fen) < 30 or (origine + h) not in serie:
                continue
            r = stats.theilslopes([serie[j] for j in fen], fen)
            prevu = float(r[1]) + float(r[0]) * (origine + h)
            erreurs.append(serie[origine + h] - prevu)
        a = np.asarray(erreurs, dtype=float)
        p10 = float(np.quantile(a, 0.10, method="linear"))
        p90 = float(np.quantile(a, 0.90, method="linear"))
        obtenu = bt.get(h)
        verifier(f"backtest h={h} p10", obtenu is not None and proche(obtenu[0], p10, 1e-9),
                 f"attendu {p10!r}, obtenu {obtenu!r}")
        verifier(f"backtest h={h} p90", obtenu is not None and proche(obtenu[1], p90, 1e-9),
                 f"attendu {p90!r}, obtenu {obtenu!r}")
        verifier(f"backtest h={h} effectif", obtenu is not None and obtenu[2] == len(erreurs),
                 f"attendu {len(erreurs)}, obtenu {obtenu[2] if obtenu else None}")
        verifier(f"backtest h={h} bande ordonnee", obtenu is not None and obtenu[0] <= obtenu[1])

    # la bande s'elargit avec l'horizon : c'est la propriete qu'on affiche
    verifier("la bande de backtest s'elargit avec l'horizon",
             (bt[30][1] - bt[30][0]) > (bt[1][1] - bt[1][0]),
             f"h=1 : {bt[1][1]-bt[1][0]:.3f}, h=30 : {bt[30][1]-bt[30][0]:.3f}")

    # historique trop court : pas de bande inventee
    court = {j: 1.0 * j for j in range(20)}
    vide = m.backtest(court, [7], fenetre=30)
    verifier("backtest sans historique suffisant", vide.get(7) is None,
             f"obtenu {vide.get(7)!r}")


def tester_report(m) -> None:
    serie = {0: 10.0, 1: 11.0, 5: 12.0, 20: 13.0}
    complete, reports = m.report_derniere_valeur(serie, 3)
    verifier("report : les jours d'origine sont intacts",
             all(proche(complete[j], serie[j]) for j in serie))
    verifier("report : borne respectee",
             all(proche(complete.get(j), 11.0) for j in (2, 3, 4)),
             f"obtenu {[complete.get(j) for j in (2, 3, 4)]!r}")
    verifier("report : au-dela de la borne, rien",
             all(j not in complete for j in (9, 10, 19)),
             "des jours ont ete fabriques au-dela de la limite")
    verifier("report : jours 6, 7, 8 reportes depuis le 5",
             all(proche(complete.get(j), 12.0) for j in (6, 7, 8)))
    verifier("report : compte rendu", reports == 6, f"attendu 6, obtenu {reports}")

    intacte, zero = m.report_derniere_valeur({0: 1.0, 1: 2.0}, 10)
    verifier("report : serie sans trou inchangee", intacte == {0: 1.0, 1: 2.0} and zero == 0)
    verifier("report N=0 ne fabrique rien",
             m.report_derniere_valeur(serie, 0) == (dict(serie), 0))


def main() -> int:
    try:
        from build import statistiques as m
    except ImportError as exc:
        print(f"MODULE ABSENT : {exc}", file=sys.stderr)
        print("Les tests sont prets, l'implementation ne l'est pas. "
              "C'est l'etat attendu tant que build/statistiques.py n'a pas ete ecrit.",
              file=sys.stderr)
        return 2

    tester_mediane_et_quantiles(m)
    tester_bande(m)
    tester_ecretage(m)
    tester_theil_sen(m)
    tester_projection_et_backtest(m)
    tester_report(m)

    if echecs:
        print(f"ECHEC : {len(echecs)} verification(s)", file=sys.stderr)
        for e in echecs[:60]:
            print(f"  {e}", file=sys.stderr)
        if len(echecs) > 60:
            print(f"  ... et {len(echecs)-60} autres", file=sys.stderr)
        return 1

    print("OK : mediane, quantiles, bande, ecretage, Theil-Sen, projection, "
          "backtest et report verifies contre numpy et scipy")
    return 0


if __name__ == "__main__":
    sys.exit(main())
