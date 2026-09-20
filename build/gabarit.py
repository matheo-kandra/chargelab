"""Gabarit de la page. Separe de build/page.py pour rester lisible.

Aucune accolade Python ici : le gabarit contient du CSS et du JavaScript, et
les substitutions se font par remplacement de jetons %%NOM%%.
"""

GABARIT = r"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>La recharge, là où vous êtes. Édition du %%DATE_LONGUE%%</title>
<meta name="description" content="État quotidien de la recharge électrique publique en France : %%N_PDC%% points de charge, %%N_STATIONS%% stations, disponibilité déclarée et tarifs publiés. Édition du %%DATE_LONGUE%%.">
<link rel="canonical" href="https://chargelab.example/">
<meta name="theme-color" content="#101418">
<meta property="og:type" content="website">
<meta property="og:title" content="La recharge, là où vous êtes.">
<meta property="og:image" content="https://chargelab.example/%%OG_IMAGE%%">
<meta property="og:image:type" content="image/svg+xml">
<meta property="og:description" content="Édition du %%DATE_LONGUE%% : %%N_PDC%% points de charge, %%N_STATIONS%% stations.">
<style>
:root{
  --fond:#fbfaf7; --encre:#14181c; --encre-douce:#4a5560; --trait:#d9d5cd;
  --accent:#1a5e63; --rouge:#a4303f; --orange:#b36b00; --vert:#2e6f40;
  --gris:#8a9099; --surlignage:#f0ece3;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--fond);color:var(--encre);
  font:16px/1.55 ui-serif,Georgia,"Times New Roman",serif;}
.enveloppe{max-width:62rem;margin:0 auto;padding:0 1.25rem 5rem}
h1,h2,h3,.chiffre,.controles,table,.legende{font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}
h1{font-size:clamp(2rem,5.2vw,3.1rem);line-height:1.08;letter-spacing:-.02em;margin:2.5rem 0 .6rem;font-weight:700}
h2{font-size:1.35rem;letter-spacing:-.01em;margin:3.2rem 0 .3rem;font-weight:700}
h2 .numero{color:var(--gris);font-weight:400;margin-right:.5rem}
h3{font-size:1rem;margin:1.6rem 0 .4rem;font-weight:600}
p{margin:.6rem 0}
a{color:var(--accent)}
.chapeau{color:var(--encre-douce);font-size:1.05rem;max-width:44rem}
.bandeau{display:flex;flex-wrap:wrap;gap:.4rem 1.6rem;margin:1.1rem 0 0;
  padding:.85rem 0;border-top:1px solid var(--trait);border-bottom:1px solid var(--trait);
  font-family:ui-sans-serif,system-ui,sans-serif;font-size:.875rem;color:var(--encre-douce)}
.bandeau b{color:var(--encre);font-variant-numeric:tabular-nums}
.controles{position:sticky;top:0;z-index:5;background:var(--fond);
  border-bottom:1px solid var(--trait);padding:.7rem 0;margin-bottom:.5rem;
  display:flex;flex-wrap:wrap;gap:.5rem;align-items:center;font-size:.875rem}
.controles label{color:var(--encre-douce)}
select,button{font:inherit;font-family:ui-sans-serif,system-ui,sans-serif;
  background:#fff;color:var(--encre);border:1px solid var(--trait);
  border-radius:.25rem;padding:.35rem .5rem}
button{cursor:pointer}
button:hover,select:hover{border-color:var(--accent)}
button:focus-visible,select:focus-visible,a:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.resume{font-family:ui-sans-serif,system-ui,sans-serif;font-size:.85rem;
  color:var(--encre-douce);border-left:3px solid var(--trait);padding:.15rem 0 .15rem .75rem;margin:.7rem 0 0}
.insuffisant{background:var(--surlignage);border-left:3px solid var(--orange);
  padding:.7rem .9rem;margin:.9rem 0;font-family:ui-sans-serif,system-ui,sans-serif;font-size:.875rem}
.insuffisant b{color:var(--orange)}
.grand{font-size:clamp(1.6rem,4vw,2.3rem);font-weight:700;font-variant-numeric:tabular-nums;
  font-family:ui-sans-serif,system-ui,sans-serif;line-height:1.1}
.cartouche{display:flex;flex-wrap:wrap;gap:1.6rem;margin:1rem 0}
.cartouche div{min-width:9rem}
.cartouche span{display:block;font-size:.8rem;color:var(--encre-douce);
  font-family:ui-sans-serif,system-ui,sans-serif}
table{border-collapse:collapse;width:100%;font-size:.85rem;margin:.9rem 0}
th,td{text-align:right;padding:.32rem .5rem;border-bottom:1px solid var(--trait);
  font-variant-numeric:tabular-nums}
th:first-child,td:first-child{text-align:left;font-variant-numeric:normal}
th{font-weight:600;color:var(--encre-douce);font-size:.78rem;white-space:nowrap}
tbody tr:hover{background:var(--surlignage)}
.vide{color:var(--gris);font-variant-numeric:normal}
canvas{display:block;width:100%;height:auto;background:#fff;border:1px solid var(--trait);border-radius:.25rem}
.legende{display:flex;flex-wrap:wrap;gap:.35rem 1rem;font-size:.78rem;color:var(--encre-douce);margin:.5rem 0}
.legende i{display:inline-block;width:.7rem;height:.7rem;border-radius:50%;margin-right:.3rem;vertical-align:-1px}
.barres{display:flex;align-items:flex-end;gap:1px;height:8rem;margin:.9rem 0 .2rem;
  border-bottom:1px solid var(--trait)}
.barres div{flex:1;background:var(--accent);min-height:1px}
.barres div.creux{background:var(--gris)}
.piste{height:.55rem;background:var(--surlignage);border-radius:.3rem;overflow:hidden;margin:.15rem 0}
.piste i{display:block;height:100%;background:var(--accent)}
footer{margin-top:4rem;padding-top:1.2rem;border-top:1px solid var(--trait);
  font-size:.8rem;color:var(--encre-douce);font-family:ui-sans-serif,system-ui,sans-serif}
.methode{font-size:.9rem}
.methode h3{margin-top:1.4rem}
.methode dl{display:grid;grid-template-columns:auto 1fr;gap:.2rem .9rem;margin:.5rem 0}
.methode dt{color:var(--encre-douce);font-family:ui-sans-serif,system-ui,sans-serif;font-size:.82rem}
.methode dd{margin:0;font-variant-numeric:tabular-nums}
@media (max-width:40rem){
  .bandeau{gap:.3rem 1rem;font-size:.82rem}
  table{font-size:.8rem}
  th,td{padding:.28rem .3rem}
}
</style>
</head>
<body>
<div class="enveloppe">

<h1>La recharge, là où vous êtes.</h1>
<p class="chapeau">Ce que les exploitants déclarent de la recharge électrique publique en France, relevé chaque jour, sans rien lisser. Là où la donnée manque, la page le dit et donne l'effectif.</p>

<div class="bandeau">
  <span>Édition du <b>%%DATE_LONGUE%%</b></span>
  <span><b>%%N_STATIONS%%</b> stations</span>
  <span><b>%%N_PDC%%</b> points de charge</span>
  <span><b>%%N_JOURS%%</b> jour de relevés</span>
  <span>parution quotidienne</span>
</div>

<div class="controles">
  <label for="territoire">Territoire</label>
  <select id="territoire"><option value="FR">France entière</option></select>
  <button id="localiser" type="button">Me localiser</button>
  <label for="classe">Classe de puissance</label>
  <select id="classe"><option value="*">Toutes</option></select>
  <span id="portee" class="vide"></span>
</div>

<h2><span class="numero">1</span>La carte</h2>
<p>Une station, un point. La couleur dit l'état du jour, la puissance maximale ou le tarif publié, au choix. Les stations d'outre-mer ne sont pas sur cette carte : elles sont dans tous les totaux, et leurs effectifs sont donnés dans la Méthode.</p>
<div class="controles" style="position:static;border:0;padding:.2rem 0">
  <label for="couleur">Couleur</label>
  <select id="couleur">
    <option value="etat">État du jour</option>
    <option value="classe">Classe de puissance</option>
    <option value="prix">Tarif publié au kWh</option>
  </select>
</div>
<canvas id="carte" width="1240" height="1180" role="img" aria-label="Carte des stations de recharge en France métropolitaine"></canvas>
<div class="legende" id="legende-carte"></div>
<p class="resume" id="resume-carte"></p>

<h2><span class="numero">2</span>La marée</h2>
<p>La part des points de charge déclarés hors service, jour après jour. Il faut plusieurs jours pour qu'une courbe veuille dire quelque chose.</p>
<div id="maree"></div>

<h2><span class="numero">3</span>Le mur</h2>
<p>Les mises en service semaine par semaine, d'après la date déclarée par l'exploitant. Une crête, une semaine.</p>
<div id="mur"></div>

<h2><span class="numero">4</span>Les départements</h2>
<p>Le parc et la disponibilité déclarée, département par département. Un département dont moins de %%SEUIL%% points se déclarent n'a pas de taux affiché.</p>
<div id="departements"></div>

<h2><span class="numero">5</span>Les enseignes</h2>
<p>Les huit réseaux les plus présents dans le territoire choisi. Le réseau est identifié par son préfixe d'itinérance, pas par le nom d'enseigne saisi sur chaque borne.</p>
<div id="enseignes"></div>

<h2><span class="numero">6</span>Les bornes muettes</h2>
<p>Un point de charge qui ne dit rien n'est pas un point de charge en service. Quatre situations, comptées séparément.</p>
<div id="muettes"></div>

<h2><span class="numero">7</span>Ce que les opérateurs déclarent</h2>
<p>Le champ tarifaire est du texte libre et facultatif. Cette section ne montre pas un prix de marché : elle montre ce qu'une minorité d'exploitants publie, et à quel point c'est peu.</p>
<div id="prix"></div>

<h2><span class="numero">8</span>Et après</h2>
<div id="apres"></div>

<h2><span class="numero">9</span>Les records</h2>
<div id="records"></div>

<h2><span class="numero">10</span>Éditions précédentes</h2>
<div id="editions"></div>

<h2><span class="numero">11</span>Méthode</h2>
<div class="methode" id="methode"></div>

<footer>
  <p>Source : Point d'Accès National transport.data.gouv.fr, consolidation beta de la base nationale des points de recharge. Contours départementaux dérivés d'Admin Express IGN. Données sous Licence Ouverte / Etalab v2.0.</p>
  <p>Page générée le %%GENERE_LE%%. Aucune requête réseau à l'affichage, aucune police externe, aucune mesure d'audience. La géolocalisation, si vous l'utilisez, sert à trouver votre département puis est oubliée.</p>
  <p>Méthode reprise de la page <i>lab</i> de PowlFuel, dont seul le principe éditorial est emprunté.</p>
</footer>
</div>

<script>
const D = %%DONNEES%%;
%%SCRIPT%%
</script>
</body>
</html>
"""
