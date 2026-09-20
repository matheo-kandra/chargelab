#!/usr/bin/env python3
"""Parseur du champ libre `tarification` de la base IRVE statique.

Le contrat et les 355 cas de reference sont dans tests/, ecrits avant ce
fichier. Les regles appliquees viennent de docs/decisions.md, ADR 17 :

  - tarif differencie par plage horaire : on garde le dernier
    « par defaut : X par kwh de charge » ; a defaut, la clause dont la plage
    horaire est la plus longue ; a egalite, la premiere clause du texte ;
  - un prix au temps PENDANT la charge fait un MIXTE ; un prix d'occupation
    hors charge est releve mais ne change pas le code ;
  - nombre nu sans unite, « cts » suivi d'un decimal, prix libelle au kW :
    INCONNU, on ne devine pas ;
  - hors de [0,05 ; 1,50] euro par kWh : INCONNU ;
  - prix declare HT : porte a TTC au taux de 20 %, et signale ;
  - booleen fuite dans le champ texte : RENVOI.

Rien n'est corrige en silence : tout ce qui n'est pas lisible ressort en
INCONNU avec un motif, pour etre compte.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

TVA = 1.20
BORNE_BASSE = 0.05
BORNE_HAUTE = 1.50

KWH, MIN, SESSION, MIXTE, GRATUIT, RENVOI, VIDE, INCONNU = (
    "KWH", "MIN", "SESSION", "MIXTE", "GRATUIT", "RENVOI", "VIDE", "INCONNU")


@dataclass
class Resultat:
    code: str = INCONNU
    prix_kwh: float | None = None
    prix_kwh_ac: float | None = None
    prix_kwh_dc: float | None = None
    prix_min: float | None = None
    prix_heure_charge: float | None = None
    prix_session: float | None = None
    prix_occupation_h: float | None = None
    ht_converti: bool = False
    motif: str = ""


# --- normalisation ---------------------------------------------------------

# Deux encodages fautifs coexistent dans la source : l'UTF-8 double encode
# (« â‚¬ ») et l'octet euro de cp1252 laisse tel quel (0x80).
MOJIBAKE = {"â‚¬": "€", "\x80": "€", "Ã©": "é", "Ã¨": "è", "Ãª": "ê", "Ã ": "à", "Â": ""}

NON_INFO = {
    "-", "--", "inconnu", "payant", "true", "false", "null", "n/a", "na",
    "non communique", "grille tarifaire en ligne", "au kwh", "fixe",
    "voir tarif gireve", "0 pour utilisateur", "0 pour utilisateur zeborne",
    "non renseigne", "a definir",
}
RENVOI_MOTIFS = (
    "peuvent varier en fonction",
    "frais de connexion eventuelles",
    "consulter directement les informations tarifaires",
)
RE_URL = re.compile(r"https?://")
RE_ABONNE = re.compile(r"pour\s+(?:les\s+|l'|un\s+)?(?:abonn|utilisateur|adherent)", re.I)
RE_NON_ABONNE = re.compile(r"non[\s-]*abonn", re.I)
RE_APRES_CHARGE = re.compile(
    r"(?:apr[eè]s\s+(?:la\s+)?(?:recharge|charge)|en\s+dehors\s+des\s+sessions"
    r"|une\s+fois\s+la\s+charge\s+termin|hors\s+charge)", re.I)


def sans_accent(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")


def normaliser(valeur: str) -> str:
    """Met la chaine dans une forme ou les unites sont reconnaissables.

    On ne change jamais les nombres : on rapproche seulement les graphies
    d'unites, pour que « 0,42€KWHHT » et « 0,42 € HT / kWh » soient lus pareil.
    """
    s = valeur
    for faux, vrai in MOJIBAKE.items():
        s = s.replace(faux, vrai)
    s = s.replace("’", "'").replace(" ", " ")
    s = re.sub(r"\s+", " ", s).strip().lower()
    # « e » et « E » employes pour l'euro, uniquement colles a un nombre ou a une unite
    s = re.sub(r"(?<=\d)\s*e(?=\s*/\s*k?w?h?)", "€", s)
    s = re.sub(r"(?<=\d)\s*e(?=/|\s*k?wh)", "€", s)
    s = re.sub(r"(?<=\d)\s*e\b(?=\s+de\s+cout)", "€", s)
    # unites collees
    s = s.replace("kw h", "kwh").replace("k w h", "kwh")
    s = re.sub(r"kwh\s*ttc", "kwh ttc", s)
    s = re.sub(r"kwhttc", "kwh ttc", s)
    s = re.sub(r"kwhht(?:va)?", "kwh ht", s)
    s = re.sub(r"€\s*kwh", "€/kwh", s)
    s = re.sub(r"(\d)\s*kwh", r"\1 kwh", s)
    return s


NB = r"(\d+(?:[.,]\d+)?)"


def val(txt: str) -> float:
    return float(txt.replace(",", "."))


# --- decoupage en clauses horaires ----------------------------------------

# La plage horaire n'est pas toujours introduite par « entre » ou « de » :
# « 8h a 22h = ... » est une forme rencontree. On exige en revanche le marqueur
# d'heure des deux cotes, sinon « 0,05 a 0,10 » passerait pour une plage.
RE_PLAGE = re.compile(
    r"(?:entre|de|from)?\s*(\d{1,2})\s*(?:h(\d{2})?|:(\d{2}))\s*(?:et|[àa]|-|/|=)\s*"
    r"(\d{1,2})\s*(?:h(\d{2})?|:(\d{2}))", re.I)
RE_PLAGE_AMPM = re.compile(r"(\d{1,2})\s*(am|pm)\s*/\s*(\d{1,2})\s*(am|pm)", re.I)


def duree_plage(clause: str) -> float:
    """Duree en heures de la plage horaire d'une clause, 0 si aucune."""
    m = RE_PLAGE_AMPM.search(clause)
    if m:
        h1 = int(m.group(1)) % 12 + (12 if m.group(2).lower() == "pm" else 0)
        h2 = int(m.group(3)) % 12 + (12 if m.group(4).lower() == "pm" else 0)
        return (h2 - h1) % 24 or 24.0
    m = RE_PLAGE.search(clause)
    if not m:
        return 0.0
    mn1 = m.group(2) or m.group(3)
    mn2 = m.group(5) or m.group(6)
    h1 = int(m.group(1)) + (int(mn1) / 60 if mn1 else 0)
    h2 = int(m.group(4)) + (int(mn2) / 60 if mn2 else 0)
    d = (h2 - h1) % 24
    return d or 24.0


def choisir_clause(s: str) -> str:
    """Decoupe en clauses et retient celle dont la plage horaire est la plus longue."""
    clauses = [c for c in re.split(r"\s*(?:,(?!\d)|\||\.\s)\s*", s) if c.strip()]
    if len(clauses) < 2:
        return s
    durees = [duree_plage(c) for c in clauses]
    if max(durees) == 0:
        return s
    meilleure = max(range(len(clauses)), key=lambda i: (durees[i], -i))
    return clauses[meilleure]


# --- export structure ------------------------------------------------------

RE_STRUCT = re.compile(r"par d[ée]faut\s*:|entre \d{1,2}:\d{2} et \d{1,2}:\d{2}\s*:")
RE_DEFAUT_KWH = re.compile(r"par d[ée]faut\s*:\s*" + NB + r"\s*€?\s*par kwh de charge")
RE_PLAGE_KWH = re.compile(
    r"entre (\d{1,2}):(\d{2}) et (\d{1,2}):(\d{2})\s*:\s*" + NB + r"\s*€?\s*par kwh de charge")
RE_H_CHARGE = re.compile(NB + r"\s*€?\s*par heure de charge")
RE_H_OCCUP = re.compile(NB + r"\s*€?\s*par heure d'occupation")
RE_DEPART = re.compile(r"prix de d[ée]part\s*:?\s*" + NB)


RE_SEGMENT = re.compile(r"par d[ée]faut\s*:|entre \d{1,2}:\d{2} et \d{1,2}:\d{2}\s*:")
RE_KWH_CHARGE = re.compile(NB + r"\s*€?\s*par kwh de charge")


def _segments(s: str) -> list[tuple[str, str]]:
    """Decoupe l'export en segments (etiquette, contenu).

    Un segment commence a « par defaut : » ou a « entre HH:MM et HH:MM : » et
    court jusqu'au suivant. Le prix au kWh n'est pas forcement le premier
    montant du segment : « par defaut : 6.0€ par heure d'occupation hors
    charge, 0.42€ par kwh de charge » est une forme courante.
    """
    bornes = [(m.start(), m.group(0)) for m in RE_SEGMENT.finditer(s)]
    out = []
    for i, (debut, etiquette) in enumerate(bornes):
        fin = bornes[i + 1][0] if i + 1 < len(bornes) else len(s)
        out.append(("defaut" if etiquette.startswith("par d") else "plage",
                    s[debut:fin]))
    return out


def parser_structure(s: str) -> Resultat:
    r = Resultat()
    segs = _segments(s)
    defauts = [RE_KWH_CHARGE.search(c) for e, c in segs if e == "defaut"]
    defauts = [m.group(1) for m in defauts if m]
    if defauts:
        r.prix_kwh = val(defauts[-1])
    else:
        plages = [(((int(c) + int(d) / 60) - (int(a) + int(b) / 60)) % 24 or 24.0, val(p))
                  for a, b, c, d, p in RE_PLAGE_KWH.findall(s)]
        if plages:
            r.prix_kwh = max(plages, key=lambda x: x[0])[1]
    # Premiere valeur strictement positive : certaines grilles se terminent par
    # un « par defaut : 0.0€ par heure de charge » qui annule tout.
    hc = [val(x) for x in RE_H_CHARGE.findall(s) if val(x) > 0]
    if hc:
        r.prix_heure_charge = hc[0]
    oc = [val(x) for x in RE_H_OCCUP.findall(s) if val(x) > 0]
    if oc:
        r.prix_occupation_h = oc[0]
    dep = [val(x) for x in RE_DEPART.findall(s)]
    if dep and dep[0] > 0:
        r.prix_session = dep[0]
    return r


# --- texte libre -----------------------------------------------------------

RE_JSON = re.compile(r'"energyprice"\s*:\s*' + NB)
RE_KW_SEUL = re.compile(r"/\s*kw(?![ /]*h)|€\s*/\s*kw\b|kw/h", re.I)
RE_CTS_DECIMAL = re.compile(NB.replace(r"\d+(?:[.,]\d+)?", r"\d+[.,]\d+") + r"\s*cts?\b")
RE_CTS = re.compile(r"(\d+)\s*cts?\b")

RE_KWH = [
    re.compile(NB + r"\s*€?\s*(?:ttc|ht)?\s*(?:/|par|le|au|:)?\s*(?:au\s+)?kwh"),
    re.compile(NB + r"\s*€?\s*(?:ttc|ht)?\s*/\s*(?:au\s+)?kwh"),
    re.compile(r"per kwh[^:]*:\s*" + NB),
    re.compile(NB + r"\s*€?\s*(?:ttc)?\s*(?:le|par)\s+kwh"),
]
RE_PRIX_AU_KWH = re.compile(NB + r"\s*€?\s*:\s*prix au kwh")
RE_MINUTE = re.compile(
    NB + r"\s*(?:€\s*(?:ht)?\s*)?(?:/|par\s+|[àa]\s+la\s+|la\s+|:\s*)\s*"
    r"(?:min\b|mn\b|minute)", re.I)
RE_HEURE = re.compile(NB + r"\s*€?\s*(?:ht)?\s*/\s*h(?:eure)?\b|" + NB + r"\s*€\s*(?:ht)?\s*/\s*h\b")
RE_HEURE2 = re.compile(NB + r"\s*€?\s*(?:ht)?\s*(?:/|par)\s*heure")
RE_SESSION = [
    re.compile(NB + r"\s*€?\s*(?:de\s+)?(?:cout|coût)\s+fixe"),
    re.compile(NB + r"\s*€?\s*(?:/|\s+la\s+|\s+par\s+)session"),
    re.compile(NB + r"\s*€?\s*(?:à|a)\s+la\s+connexion"),
    re.compile(r"activation\s+(?:à|a)\s+" + NB),
    re.compile(r"frais de lancement[^:]*:\s*" + NB),
    re.compile(NB + r"\s*€\s*(?:ht\s*)?lancement"),
    re.compile(NB + r"\s*€\s*tarif de d[ée]part"),
    re.compile(r"(?:^|:\s*)" + NB + r"\s*€\s*\+"),
]


def premier(regexes, s: str) -> float | None:
    for rx in regexes if isinstance(regexes, list) else [regexes]:
        m = rx.search(s)
        if m:
            g = [x for x in m.groups() if x is not None]
            if g:
                return val(g[0])
    return None


def retirer_apres_charge(s: str) -> tuple[str, str]:
    """Separe ce qui precede d'un marqueur « apres la recharge » de ce qui suit."""
    m = RE_APRES_CHARGE.search(s)
    if not m:
        return s, ""
    return s[:m.start()], s[m.start():]


def prix_kwh_brut(s: str) -> float | None:
    m = RE_CTS.search(s)
    if m and re.search(r"kwh", s):
        avant = s[:m.start()]
        if not RE_CTS_DECIMAL.search(s):
            return int(m.group(1)) / 100
    p = premier(RE_KWH, s)
    if p is None:
        p = premier(RE_PRIX_AU_KWH, s)
    return p


def parser_libre(s: str) -> Resultat:
    r = Resultat()
    charge, apres = retirer_apres_charge(s)

    r.prix_kwh = prix_kwh_brut(s)
    r.prix_session = premier(RE_SESSION, s)
    r.prix_min = premier(RE_MINUTE, charge)
    r.prix_heure_charge = premier([RE_HEURE, RE_HEURE2], charge)
    if apres:
        occ = premier([RE_HEURE, RE_HEURE2], apres)
        if occ is not None:
            r.prix_occupation_h = occ
    return r


# --- assemblage ------------------------------------------------------------

def _hors_bornes(p: float | None) -> bool:
    return p is not None and not (BORNE_BASSE <= p <= BORNE_HAUTE)


def analyser(valeur: str) -> Resultat:
    if valeur is None:
        return Resultat(code=VIDE)
    s = normaliser(valeur)
    if s == "":
        return Resultat(code=VIDE)

    nu = sans_accent(s).strip(" .")
    if nu in NON_INFO or RE_URL.search(s):
        return Resultat(code=RENVOI, motif="renvoi ou mot cle sans information")
    if any(m in nu for m in RENVOI_MOTIFS):
        return Resultat(code=RENVOI, motif="texte de renvoi sans chiffre")
    if RE_ABONNE.search(s) and not RE_NON_ABONNE.search(s):
        return Resultat(code=RENVOI, motif="tarif reserve aux abonnes ou a un reseau")

    ht = bool(re.search(r"\bht\b|htva", s)) and not re.search(r"\bttc\b", s)

    if RE_STRUCT.search(s):
        r = parser_structure(s)
    elif RE_JSON.search(s):
        r = Resultat(prix_kwh=val(RE_JSON.search(s).group(1)))
    else:
        r = _analyser_libre_complet(s)

    r.ht_converti = False
    if ht:
        for champ in ("prix_kwh", "prix_kwh_ac", "prix_kwh_dc", "prix_min",
                      "prix_heure_charge", "prix_session", "prix_occupation_h"):
            v = getattr(r, champ)
            if v is not None:
                setattr(r, champ, round(v * TVA, 10))
                r.ht_converti = True

    ecartes = []
    for champ in ("prix_kwh", "prix_kwh_ac", "prix_kwh_dc"):
        if _hors_bornes(getattr(r, champ)):
            ecartes.append(f"{champ}={getattr(r, champ)}")
            setattr(r, champ, None)
    if ecartes and not any((r.prix_kwh, r.prix_kwh_ac, r.prix_kwh_dc)):
        return Resultat(code=INCONNU,
                        motif="prix au kWh hors bornes de plausibilite : " + ", ".join(ecartes))

    energie = any(v is not None for v in (r.prix_kwh, r.prix_kwh_ac, r.prix_kwh_dc))
    temps = r.prix_min is not None or r.prix_heure_charge is not None
    if energie and (temps or r.prix_session is not None):
        r.code = MIXTE
    elif energie:
        r.code = KWH
    elif temps:
        r.code = MIN
    elif r.prix_session is not None:
        r.code = SESSION
    elif re.search(r"\bgratuit", s):
        if sans_accent(s).strip(" .") in ("gratuit", "gratuite", "recharge gratuite"):
            return Resultat(code=GRATUIT, prix_kwh=0.0)
        return Resultat(code=RENVOI, motif="gratuite conditionnelle, pas un tarif public")
    else:
        return Resultat(code=INCONNU, motif="aucun prix lisible avec son unite")
    if ecartes:
        r.motif = "composante ecartee, hors bornes : " + ", ".join(ecartes)
    return r


RE_SPLIT_ACDC = re.compile(r"\s+-\s+|\s-\s")


def _analyser_libre_complet(s: str) -> Resultat:
    """Texte libre : tente d'abord une separation AC / DC, sinon clause unique."""
    parts = RE_SPLIT_ACDC.split(s)
    if len(parts) >= 2:
        ac = [p for p in parts if re.search(r"\bac\b|\d+ac\b", p) and not re.search(r"\bdc\b|\d+dc\b", p)]
        dc = [p for p in parts if re.search(r"\bdc\b|\d+dc\b", p) and not re.search(r"\bac\b|\d+ac\b", p)]
        if ac and dc:
            pac = prix_kwh_brut(_sans_acdc(ac[0]))
            pdc = prix_kwh_brut(_sans_acdc(dc[0]))
            if pac is not None and pdc is not None:
                r = Resultat(prix_kwh_ac=pac, prix_kwh_dc=pdc)
                r.prix_min = premier(RE_MINUTE, _sans_acdc(ac[0]))
                return r

    clause = choisir_clause(s)
    r = parser_libre(_sans_acdc(clause))
    if r.prix_kwh is None and re.search(r"kwh", s):
        # cas « 6ct from 6am/10pm | 3ct/kwh ... » : l'unite n'est que dans l'autre clause
        m = RE_CTS.search(clause)
        if m and not RE_CTS_DECIMAL.search(clause):
            r.prix_kwh = int(m.group(1)) / 100
    if r.prix_kwh is None and RE_KW_SEUL.search(s):
        return Resultat(code=INCONNU, motif="prix libelle au kW, pas au kWh")
    return r


def _sans_acdc(s: str) -> str:
    return re.sub(r"\b(?:ac|dc)\b|(?<=\d)(?:ac|dc)\b", " ", s)
