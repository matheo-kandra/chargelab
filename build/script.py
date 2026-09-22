"""JavaScript de la page. Aucune dependance, aucune requete."""

SCRIPT = r"""
const $ = s => document.querySelector(s);
const nf = new Intl.NumberFormat('fr-FR');
const pf = (x, d = 2) => x === null || x === undefined || !isFinite(x)
  ? '…' : new Intl.NumberFormat('fr-FR', {minimumFractionDigits: d, maximumFractionDigits: d}).format(x);
const euro = x => x === null || !isFinite(x) ? '…' : pf(x, 3).replace('.', ',') + ' €';

function debase(b64, type) {
  const bin = atob(b64), n = bin.length, oct = new Uint8Array(n);
  for (let i = 0; i < n; i++) oct[i] = bin.charCodeAt(i);
  return type === 'i32' ? new Int32Array(oct.buffer) : oct;
}

const S = {
  lat: debase(D.stations.lat, 'i32'), lon: debase(D.stations.lon, 'i32'),
  dep: debase(D.stations.dep, 'u8'), cls: debase(D.stations.cls, 'u8'),
  etat: debase(D.stations.etat, 'u8'), pdc: debase(D.stations.pdc, 'u8'),
  prix: debase(D.stations.prix, 'i32'), n: D.stations.n
};

const COULEURS_ETAT = {hors_service: '#a4303f', inconnu: '#b36b00',
  en_service: '#2e6f40', muet: '#8a9099', absent: '#c9ccd1'};
const LIB_ETAT = {hors_service: 'hors service déclaré', inconnu: 'inconnu persistant',
  en_service: 'en service', muet: 'muet depuis plus de 24 h', absent: 'absent du flux'};
const COULEURS_CLASSE = ['#9ec5c7', '#5a9ea3', '#1a5e63', '#e3b778', '#c98b2e', '#8a4b10', '#c9ccd1'];

let territoire = 'FR', classe = '*', couleur = 'etat';

/* ---------- selecteurs ---------- */
const deps = D.departements.filter(d => d.departement).sort((a, b) =>
  String(a.departement).localeCompare(String(b.departement), 'fr'));
const selT = $('#territoire');
for (const d of deps) {
  const o = document.createElement('option');
  o.value = d.departement;
  o.textContent = d.departement + ' (' + nf.format(d.pdc) + ' points)';
  selT.appendChild(o);
}
const selC = $('#classe');
for (const c of D.ordre_classes) {
  const o = document.createElement('option');
  o.value = c; o.textContent = D.libelles_classes[c];
  selC.appendChild(o);
}

/* ---------- agregats recalcules dans le navigateur ---------- */
function lignesEtat() {
  const src = classe === '*' ? D.etat_par_classe.filter(r => r.classe === '*')
                             : D.etat_par_classe.filter(r => r.classe === classe);
  return territoire === 'FR' ? src : src.filter(r => r.departement === territoire);
}
function cumul() {
  const t = {pdc: 0, frais: 0, hors_service: 0, muet: 0, absent: 0, inconnu: 0,
             avec_prix: 0, renseigne: 0};
  for (const r of lignesEtat())
    for (const k in t) t[k] += (r[k] || 0);
  t.taux = t.frais ? t.hors_service / t.frais : null;
  return t;
}
function stationsVisibles() {
  const idx = [];
  const iDep = territoire === 'FR' ? -1 : D.stations.codes_dep.indexOf(territoire);
  const iCls = classe === '*' ? -1 : D.ordre_classes.indexOf(classe);
  for (let i = 0; i < S.n; i++) {
    if (iDep >= 0 && S.dep[i] !== iDep) continue;
    if (iCls >= 0 && S.cls[i] !== iCls) continue;
    idx.push(i);
  }
  return idx;
}

/* ---------- carte ---------- */
const cv = $('#carte'), cx = cv.getContext('2d');
const BB = {lon0: -5.2, lon1: 9.7, lat0: 41.3, lat1: 51.1};
function proj(lon, lat) {
  const k = Math.cos((BB.lat0 + BB.lat1) / 2 * Math.PI / 180);
  const x = (lon - BB.lon0) / (BB.lon1 - BB.lon0) * cv.width;
  const y = cv.height - (lat - BB.lat0) / (BB.lat1 - BB.lat0) * cv.height * k / 0.72;
  return [x, y];
}
function dessinerCarte() {
  cx.clearRect(0, 0, cv.width, cv.height);
  cx.lineWidth = 1.2; cx.strokeStyle = '#c5c0b5';
  for (const code in D.contours) {
    const surligne = territoire !== 'FR' && code === territoire;
    cx.beginPath();
    for (const poly of D.contours[code]) {
      const anneaux = typeof poly[0][0] === 'number' ? [poly] : poly;
      for (const anneau of anneaux) {
        anneau.forEach((p, i) => {
          const [x, y] = proj(p[0], p[1]);
          i ? cx.lineTo(x, y) : cx.moveTo(x, y);
        });
        cx.closePath();
      }
    }
    if (surligne) { cx.fillStyle = '#f0ece3'; cx.fill(); }
    cx.stroke();
  }
  const idx = stationsVisibles();
  for (const i of idx) {
    const [x, y] = proj(S.lon[i] / 1e4, S.lat[i] / 1e4);
    let c;
    if (couleur === 'etat') c = COULEURS_ETAT[D.stations.codes_etat[S.etat[i]]];
    else if (couleur === 'classe') c = COULEURS_CLASSE[S.cls[i]] || '#c9ccd1';
    else {
      const p = S.prix[i] / 1000;
      c = p < 0 ? '#e8e5de' : p < 0.30 ? '#2e6f40' : p < 0.40 ? '#7fa05a'
        : p < 0.50 ? '#c98b2e' : '#a4303f';
    }
    cx.fillStyle = c;
    const r = Math.min(3.2, 1.1 + Math.log2(1 + S.pdc[i]) * 0.5);
    cx.beginPath(); cx.arc(x, y, r, 0, 6.2832); cx.fill();
  }
  const leg = $('#legende-carte');
  if (couleur === 'etat')
    leg.innerHTML = D.stations.codes_etat.map(e =>
      '<span><i style="background:' + COULEURS_ETAT[e] + '"></i>' + LIB_ETAT[e] + '</span>').join('');
  else if (couleur === 'classe')
    leg.innerHTML = D.ordre_classes.map((c, i) =>
      '<span><i style="background:' + COULEURS_CLASSE[i] + '"></i>' + D.libelles_classes[c] + '</span>').join('');
  else
    leg.innerHTML = ['#2e6f40 sous 0,30 €', '#7fa05a 0,30 à 0,40 €', '#c98b2e 0,40 à 0,50 €',
      '#a4303f au-delà de 0,50 €', '#e8e5de aucun tarif publié'].map(s => {
      const [c, ...t] = s.split(' ');
      return '<span><i style="background:' + c + '"></i>' + t.join(' ') + '</span>';
    }).join('');
  const avecPrix = idx.filter(i => S.prix[i] >= 0).length;
  $('#resume-carte').textContent = nf.format(idx.length) + ' stations affichées sur '
    + nf.format(S.n) + ' en métropole. ' + nf.format(avecPrix) + ' publient un tarif au kWh, soit '
    + pf(100 * avecPrix / Math.max(1, idx.length), 1) + ' %.';
}

/* ---------- sections ---------- */
function bloc(html) { return html; }
function insuffisant(texte) { return '<div class="insuffisant">' + texte + '</div>'; }

function rendreMaree() {
  const t = cumul();
  const couv = t.pdc ? 100 * t.frais / t.pdc : 0;
  // Le seuil d'effectif vaut ici comme ailleurs : un taux calcule sur une
  // poignee de points ne se publie pas, meme en gros caracteres.
  const assez = t.frais >= D.seuil;
  const valeur = !assez ? 'effectif insuffisant'
    : (t.taux === null ? '…' : pf(100 * t.taux, 2) + ' %');
  $('#maree').innerHTML = bloc(
    '<div class="cartouche"><div><span>Points hors service aujourd\'hui</span>'
    + '<b class="grand"' + (assez ? '' : ' style="font-size:1.05rem;color:var(--orange)"') + '>' + valeur + '</b></div>'
    + '<div><span>Calculé sur</span><b class="grand">' + nf.format(t.frais) + '</b></div>'
    + '<div><span>Soit du territoire</span><b class="grand">' + pf(couv, 1) + ' %</b></div></div>'
    + courbeMaree()
    + '<p class="resume">' + (assez
      ? 'Ce taux ne porte pas sur le parc mais sur les ' + nf.format(t.frais)
        + ' points dont l\'état déclaré a moins de 24 heures, soit ' + pf(couv, 1)
        + ' % du territoire choisi. Les ' + nf.format(t.pdc - t.frais)
        + ' autres ne disent rien : voir la section 6.'
      : 'Seuls ' + nf.format(t.frais) + ' points de ce territoire déclarent un état de moins '
        + 'de 24 heures, en dessous du seuil de ' + D.seuil + '. Aucun taux n\'est publié : '
        + 'il serait calculé sur trop peu de points pour vouloir dire quelque chose.')
    + '</p>');
}

function courbeMaree() {
  const pts = D.serie.points, manq = D.serie.jours_sans_edition;
  if (pts.length < 2)
    return insuffisant('<b>Pas encore de courbe : ' + pts.length + ' édition construite sur '
      + D.serie.jours_collectes + ' jours de relevés.</b> Une série demande au moins deux '
      + 'points, et relier deux points par-dessus un trou sans le dire est interdit ici.');
  // Un jour ou la collecte a mal tourne produit un taux calcule sur trop peu
  // de creneaux. Il reste sur la courbe, mais en point creux, et il n'entre
  // pas dans l'etendue annoncee : sinon un incident de collecte se lirait
  // comme une variation du reseau.
  const creneaux = pts.map(p => p.creneaux).sort((a, b) => a - b);
  const medCren = creneaux[Math.floor(creneaux.length / 2)];
  const partiel = p => p.creneaux < 0.5 * medCren;
  const complets = pts.filter(p => p.taux !== null && !partiel(p));
  const taux = pts.filter(p => p.taux !== null).map(p => 100 * p.taux);
  const tauxComplets = complets.map(p => 100 * p.taux);
  const bas = Math.min(...taux), haut = Math.max(...taux);
  const etendue = Math.max(0.2, haut - bas);
  const l = 640, h = 150, m = 28;
  const x = i => m + i * (l - 2 * m) / Math.max(1, pts.length - 1);
  const y = v => h - m - (v - bas + etendue * 0.15) / (etendue * 1.3) * (h - 2 * m);
  let chemin = '', points = '';
  pts.forEach((p, i) => {
    if (p.taux === null) return;
    const vx = x(i), vy = y(100 * p.taux);
    chemin += (chemin ? 'L' : 'M') + vx.toFixed(1) + ' ' + vy.toFixed(1);
    const creux = partiel(p);
    points += '<circle cx="' + vx.toFixed(1) + '" cy="' + vy.toFixed(1)
      + '" r="' + (creux ? 4.5 : 3.5) + '" fill="' + (creux ? '#fbfaf7' : '#1a5e63')
      + '" stroke="#1a5e63" stroke-width="' + (creux ? 1.5 : 0) + '"'
      + (creux ? ' stroke-dasharray="2 2"' : '') + '><title>' + p.date + ' : '
      + pf(100 * p.taux, 2) + ' % sur ' + nf.format(p.frais) + ' points, '
      + p.creneaux + ' créneaux' + (creux ? ', relevé partiel' : '')
      + '</title></circle>';
  });
  const dates = pts.map((p, i) => '<text x="' + x(i).toFixed(1) + '" y="' + (h - 6)
    + '" text-anchor="middle" font-size="10" fill="#4a5560">'
    + p.date.slice(8) + '/' + p.date.slice(5, 7) + '</text>').join('');
  const svg = '<svg viewBox="0 0 ' + l + ' ' + h + '" width="100%" height="' + h
    + '" role="img" aria-label="Taux de points hors service, jour par jour">'
    + '<path d="' + chemin + '" fill="none" stroke="#1a5e63" stroke-width="2"/>'
    + points + dates + '</svg>';
  const alerte = manq.length
    ? insuffisant('<b>' + manq.length + ' jour' + (manq.length > 1 ? 's' : '')
      + ' de relevés sans édition construite : ' + manq.join(', ') + '.</b> '
      + 'Ces jours ne sont pas sur la courbe et ne sont pas interpolés. Ils le seront '
      + 'quand leur édition sera construite.')
    : '';
  const creuxListe = pts.filter(partiel);
  const etendueTxt = tauxComplets.length >= 2
    ? 'Écart entre le plus bas et le plus haut, jours complets seulement : '
      + pf(Math.max(...tauxComplets) - Math.min(...tauxComplets), 2) + ' point.'
    : 'Trop peu de jours complets pour annoncer une étendue.';
  const creuxTxt = creuxListe.length
    ? ' <b>' + creuxListe.length + ' point' + (creuxListe.length > 1 ? 's creux' : ' creux')
      + '</b> : ' + creuxListe.map(p => p.date + ' (' + p.creneaux + ' créneaux contre '
        + medCren + ' en médiane)').join(', ')
      + '. Le taux y est calculé sur trop peu de relevés pour être comparable, il est '
      + 'affiché mais exclu de l\'étendue.'
    : '';
  return svg + '<p class="resume">' + pts.length + ' éditions, du ' + pts[0].date + ' au '
    + pts[pts.length - 1].date + '. ' + etendueTxt + creuxTxt
    + ' La bande p25 et p75 entre départements demande encore plusieurs jours.</p>' + alerte;
}

function rendreMur() {
  const m = D.mur, max = Math.max(1, ...m.semaines.map(s => s[1]));
  const barres = m.semaines.map(s =>
    '<div style="height:' + (100 * s[1] / max) + '%" title="' + s[0] + ' : ' + s[1] + '"></div>').join('');
  const total = m.semaines.reduce((a, s) => a + s[1], 0);
  $('#mur').innerHTML = bloc(
    '<div class="barres">' + barres + '</div>'
    + '<p class="resume">' + m.semaines.length + ' semaines, ' + nf.format(total)
    + ' mises en service déclarées sur l\'année écoulée, soit une médiane de '
    + nf.format(Math.round(m.mediane_21)) + ' par semaine sur les 21 dernières.</p>'
    + insuffisant('<b>Cette section ne décrit que la moitié du parc.</b> La date de mise en '
      + 'service est renseignée pour ' + nf.format(m.couverture) + ' points de charge, soit '
      + pf(100 * m.part, 1) + ' % du parc. Le creux visible en 2018 dans les données complètes '
      + 'est un défaut de déclaration, pas un creux d\'installation. Les retraits par semaine '
      + 'demandent un suivi jour à jour qui commence avec ce projet.'));
}

function rendreDepartements() {
  const lignes = D.departements.filter(d => d.departement)
    .map(d => ({...d, taux: d.frais >= D.seuil ? 100 * d.hors_service / d.frais : null}))
    .sort((a, b) => (b.pdc || 0) - (a.pdc || 0));
  const sansTaux = lignes.filter(l => l.taux === null).length;
  const corps = lignes.map(l =>
    '<tr><td>' + l.departement + '</td><td>' + nf.format(l.pdc) + '</td><td>'
    + nf.format(l.frais) + '</td><td>'
    + (l.taux === null ? '<span class="vide">effectif insuffisant (n = ' + nf.format(l.frais) + ')</span>'
       : pf(l.taux, 2) + ' %') + '</td><td>' + nf.format(l.muet) + '</td></tr>').join('');
  $('#departements').innerHTML = bloc(
    '<table><thead><tr><th>Département</th><th>Points</th><th>Se déclarent</th>'
    + '<th>Hors service</th><th>Muets</th></tr></thead><tbody>' + corps + '</tbody></table>'
    + '<p class="resume">' + lignes.length + ' départements. ' + sansTaux
    + ' n\'ont pas assez de points qui se déclarent pour qu\'un taux soit affiché, '
    + 'le seuil étant de ' + D.seuil + '.</p>');
}

function rendreEnseignes() {
  const r = D.reseaux.slice(0, 8);
  const corps = r.map(x =>
    '<tr><td>' + x.reseau + '</td><td>' + nf.format(x.pdc) + '</td><td>' + nf.format(x.stations)
    + '</td><td>' + nf.format(x.frais) + '</td><td>'
    + (x.frais >= D.seuil ? pf(100 * x.hors_service / x.frais, 2) + ' %'
       : '<span class="vide">n = ' + nf.format(x.frais) + '</span>')
    + '</td><td>' + pf(x.puissance_mediane_kw, 0) + ' kW</td><td>'
    + (x.avec_prix ? nf.format(x.avec_prix) : '<span class="vide">aucun</span>')
    + '</td><td>' + pf(100 * x.part_paiement_cb, 0) + ' %</td></tr>').join('');
  const muets = D.reseaux.filter(x => x.frais === 0);
  $('#enseignes').innerHTML = bloc(
    '<table><thead><tr><th>Réseau</th><th>Points</th><th>Stations</th><th>Se déclarent</th>'
    + '<th>Hors service</th><th>Puissance médiane</th><th>Tarif publié</th><th>Paiement CB</th>'
    + '</tr></thead><tbody>' + corps + '</tbody></table>'
    + '<p class="resume">Sur les ' + D.reseaux.length + ' réseaux les plus présents, '
    + muets.length + ' ne publient aucun état de moins de 24 heures, dont '
    + (muets[0] ? muets[0].reseau + ' et ses ' + nf.format(muets[0].pdc) + ' points de charge'
       : 'aucun') + '.</p>');
}

function rendreMuettes() {
  const t = cumul();
  const cat = [
    ['Hors service déclaré', t.hors_service, 'l\'exploitant dit que le point ne fonctionne pas'],
    ['Inconnu persistant', t.inconnu, 'l\'exploitant répond, mais dit ne pas savoir'],
    ['Muet', t.muet, 'présent dans le flux, mais son dernier horodatage a plus de 24 heures'],
    ['Absent du flux', t.absent, 'l\'exploitant ne publie rien du tout pour ce point']
  ];
  const corps = cat.map(c =>
    '<tr><td>' + c[0] + '</td><td>' + nf.format(c[1]) + '</td><td>'
    + pf(100 * c[1] / Math.max(1, t.pdc), 2) + ' %</td><td style="text-align:left" class="vide">'
    + c[2] + '</td></tr>').join('');
  const silencieux = t.muet + t.absent;
  $('#muettes').innerHTML = bloc(
    '<div class="cartouche"><div><span>Points qui ne disent rien</span><b class="grand">'
    + pf(100 * silencieux / Math.max(1, t.pdc), 1) + ' %</b></div>'
    + '<div><span>Soit</span><b class="grand">' + nf.format(silencieux) + '</b></div></div>'
    + '<table><thead><tr><th>Situation</th><th>Points</th><th>Part</th><th style="text-align:left">Ce que cela veut dire</th></tr></thead><tbody>'
    + corps + '</tbody></table>'
    + '<p class="resume">Ces quatre situations ne sont jamais confondues. Un point muet '
    + 'n\'est pas un point retiré : un retrait se constate par sa disparition du fichier '
    + 'pendant plusieurs jours, ce qui demande un historique que ce projet commence à peine.</p>');
}

function rendrePrix() {
  const t = cumul();
  const cases = D.prix.filter(p => p.n >= D.seuil && p.p50 !== '' && p.p50 !== null);
  const lignesCls = D.classes.map(c => {
    const p = c.pdc ? 100 * c.avec_prix / c.pdc : 0;
    return '<tr><td>' + D.libelles_classes[c.classe] + '</td><td>' + nf.format(c.pdc)
      + '</td><td>' + nf.format(c.avec_prix) + '</td><td>' + pf(p, 2)
      + ' %</td><td style="width:8rem"><span class="piste"><i style="width:'
      + Math.min(100, p * 4) + '%"></i></span></td></tr>';
  }).join('');
  const tri = cases.slice().sort((a, b) => b.n - a.n).slice(0, 12);
  const corps = tri.map(c =>
    '<tr><td>' + D.libelles_classes[c.classe] + '</td><td style="text-align:left">' + c.reseau
    + '</td><td>' + nf.format(c.n) + '</td><td>' + euro(c.p25) + '</td><td><b>' + euro(c.p50)
    + '</b></td><td>' + euro(c.p75) + '</td></tr>').join('');
  $('#prix').innerHTML = bloc(
    '<div class="cartouche"><div><span>Champ tarifaire renseigné</span><b class="grand">'
    + pf(100 * t.renseigne / Math.max(1, t.pdc), 1) + ' %</b></div>'
    + '<div><span>Dont un prix au kWh lisible</span><b class="grand">'
    + pf(100 * t.avec_prix / Math.max(1, t.pdc), 1) + ' %</b></div>'
    + '<div><span>Soit</span><b class="grand">' + nf.format(t.avec_prix) + ' points</b></div></div>'
    + insuffisant('<b>Aucune médiane nationale n\'est publiée, et ce n\'est pas un oubli.</b> '
      + 'Un prix au kWh n\'est lisible que pour ' + pf(100 * t.avec_prix / Math.max(1, t.pdc), 2)
      + ' % des points, et ces points sont concentrés sur une poignée de réseaux. Une médiane '
      + 'calculée là-dessus mesurerait la grille tarifaire de quelques exploitants, pas le prix '
      + 'de la recharge en France.')
    + '<h3>Couverture par classe de puissance</h3>'
    + '<table><thead><tr><th>Classe</th><th>Points</th><th>Avec un tarif</th><th>Couverture</th><th></th></tr></thead><tbody>'
    + lignesCls + '</tbody></table>'
    + '<h3>Les grilles publiées, par classe et par réseau</h3>'
    + '<table><thead><tr><th>Classe</th><th style="text-align:left">Réseau</th><th>Effectif</th>'
    + '<th>p25</th><th>Médiane</th><th>p75</th></tr></thead><tbody>' + corps + '</tbody></table>'
    + '<p class="resume">' + cases.length + ' cases sur ' + D.prix.length
    + ' atteignent le seuil de ' + D.seuil + ' points et peuvent être publiées. '
    + 'Dans plusieurs d\'entre elles p25, médiane et p75 sont identiques : ce sont des grilles '
    + 'tarifaires uniformes, pas des prix qui varient d\'une borne à l\'autre.</p>');
}

function rendreApres() {
  $('#apres').innerHTML = insuffisant(
    '<b>Aucune projection n\'est affichée.</b> La pente de Theil-Sen demande 30 jours de '
    + 'relevés, la bande d\'incertitude en demande 60, parce qu\'elle est mesurée en rejouant '
    + 'la méthode depuis chaque origine passée et non estimée sur un résidu. Avec '
    + D.serie.jours_collectes + ' jour de relevés, une projection serait une droite tracée à travers '
    + 'un seul point. Les fonctions sont écrites et testées contre scipy, elles attendent '
    + 'les données.');
}

function rendreRecords() {
  $('#records').innerHTML = insuffisant(
    '<b>Rien à comparer.</b> Les records sont des variations d\'un jour au suivant : points '
    + 'ajoutés ou retirés par département, bascules massives d\'un réseau, changements de tarif '
    + 'déclaré. Il faut deux éditions pour la première comparaison.');
}

function rendreEditions() {
  const pts = D.serie.points.slice().reverse();
  const corps = pts.map((p, i) => {
    const prec = pts[i + 1];
    const delta = prec && p.pdc !== null && prec.pdc !== null ? p.pdc - prec.pdc : null;
    return '<tr><td>' + p.date + '</td><td>' + nf.format(p.pdc) + '</td><td>'
      + (delta === null ? '<span class="vide">première édition</span>'
         : (delta >= 0 ? '+' : '') + nf.format(delta) + ' depuis le ' + prec.date)
      + '</td><td>' + (p.taux === null ? '<span class="vide">…</span>'
         : pf(100 * p.taux, 2) + ' %') + '</td><td>' + nf.format(p.creneaux) + '</td></tr>';
  }).join('');
  $('#editions').innerHTML =
    '<table><thead><tr><th>Date</th><th>Points de charge</th><th>Variation</th>'
    + '<th>Hors service</th><th>Créneaux capturés</th></tr></thead><tbody>'
    + corps + '</tbody></table>'
    + (D.serie.jours_sans_edition.length
      ? '<p class="resume">' + D.serie.jours_sans_edition.length + ' jour(s) collecté(s) '
        + 'sans édition construite : ' + D.serie.jours_sans_edition.join(', ') + '.</p>' : '');
}

function rendreMethode() {
  const c = D.edition.counts, p = D.edition.parametres, n = D.national;
  const nav = cumul();
  const ecart = Math.abs(nav.hors_service / Math.max(1, nav.frais) - n.taux_hors_service) * 1000;
  $('#methode').innerHTML =
    '<h3>Ce que compte cette édition</h3><dl>'
    + '<dt>Points de charge</dt><dd>' + nf.format(n.pdc) + '</dd>'
    + '<dt>Stations</dt><dd>' + nf.format(n.stations) + '</dd>'
    + '<dt>Réseaux distincts</dt><dd>' + nf.format(n.reseaux) + '</dd>'
    + '<dt>Jours de relevés</dt><dd>' + D.serie.jours_collectes + '</dd>'
    + '<dt>Créneaux capturés ce jour</dt><dd>' + nf.format(c.creneaux_captures) + '</dd>'
    + '</dl>'
    + '<h3>Territoire</h3><p>Le département vient des coordonnées, par test du point dans le '
    + 'contour, et non du code commune qui est vide pour un quart du parc. '
    + nf.format(c.departement_par_coordonnees) + ' points sont rattachés ainsi, '
    + nf.format(c.departement_non_rattache) + ' ne le sont pas : '
    + nf.format(c.non_rattache_dans_boite_metropole) + ' tombent en France mais hors de tout '
    + 'contour, plans d\'eau et bordures compris, et ' + nf.format(c.non_rattache_hors_france)
    + ' sont à l\'étranger. Aucun n\'est rapproché du département le plus proche. '
    + 'Le code commune, quand il existe, est en désaccord avec les coordonnées pour '
    + nf.format(c.departement_desaccord_insee) + ' points.</p>'
    + '<h3>État du jour</h3><p>Un point compte pour la journée si son horodatage a moins de '
    + p.seuil_fraicheur_heures + ' heures. Il est déclaré hors service si au moins '
    + pf(100 * p.seuil_dominance, 0) + ' % des créneaux capturés le disent. '
    + nf.format(n.frais) + ' points sur ' + nf.format(n.pdc) + ' remplissent la condition de '
    + 'fraîcheur, soit ' + pf(100 * n.frais / n.pdc, 1) + ' % du parc. Le taux affiché porte sur '
    + 'eux seuls, jamais sur le parc.</p>'
    + '<h3>Prix</h3><p>Le champ tarifaire est renseigné pour ' + nf.format(n.tarification_renseignee)
    + ' points, soit ' + pf(100 * n.tarification_renseignee / n.pdc, 2) + ' % du parc, mais la '
    + 'majorité de ce qui est renseigné n\'est pas un prix. Répartition des codes de lecture : '
    + Object.entries(c.codes_prix).sort((a, b) => b[1] - a[1])
        .map(x => x[0] + ' ' + nf.format(x[1])).join(', ') + '. '
    + nf.format(n.avec_prix) + ' points portent un prix au kWh exploitable. '
    + nf.format(c.prix_ht_convertis) + ' valeurs déclarées hors taxes ont été portées à TTC au '
    + 'taux de ' + pf(100 * p.taux_tva_conversion_ht, 0) + ' %. Un prix hors de l\'intervalle '
    + euro(p.bornes_prix_kwh[0]) + ' à ' + euro(p.bornes_prix_kwh[1]) + ' par kWh est écarté et '
    + 'compté, jamais corrigé.</p>'
    + '<h3>Écart entre le calcul du build et le recalcul de la page</h3>'
    + '<p>Les chiffres France de cette page sont recalculés dans votre navigateur en '
    + 'additionnant les départements. Le build, lui, les calcule sur la matrice brute. '
    + 'L\'écart sur le taux hors service est de ' + pf(ecart, 3) + ' milli-point. '
    + 'Il vient des ' + nf.format(c.departement_non_rattache) + ' points sans département, '
    + 'qui entrent dans le total du build et pas dans la somme des territoires.</p>'
    + '<h3>Ce qui n\'est pas dans cette page</h3><p>Les prix réellement payés, qui dépendent du '
    + 'badge ou de l\'abonnement et ne sont publiés nulle part. L\'occupation réelle, que la '
    + 'cadence de capture ne permet pas de mesurer honnêtement. Les séries temporelles, les '
    + 'projections et les records, qui attendent l\'historique. Les territoires d\'outre-mer sur '
    + 'la carte, faute de place, mais ils sont dans tous les totaux.</p>'
    + '<h3>Vie privée</h3><p>La page ne fait aucune requête réseau après son chargement. Si vous '
    + 'utilisez le bouton de localisation, votre position sert à trouver votre département dans '
    + 'les contours embarqués, puis elle est oubliée : rien n\'est envoyé, rien n\'est '
    + 'enregistré.</p>'
    + '<h3>Sources et reproductibilité</h3><p>Données du Point d\'Accès National '
    + 'transport.data.gouv.fr sous Licence Ouverte Etalab. Édition générée le '
    + D.edition.generated_at + ', empreinte des données '
    + D.edition.empreinte_donnees.slice(0, 16) + '. Cette empreinte ne change pas d\'une '
    + 'reconstruction à l\'autre : la même commande sur les mêmes archives rend la même '
    + 'édition.</p>';
}

/* ---------- localisation ---------- */
function dansPolygone(lon, lat, coords) {
  let dedans = false;
  const anneaux = typeof coords[0][0][0] === 'number' ? [coords] : coords;
  for (const poly of anneaux) {
    const a = poly[0];
    for (let i = 0, j = a.length - 1; i < a.length; j = i++) {
      const xi = a[i][0], yi = a[i][1], xj = a[j][0], yj = a[j][1];
      if ((yi > lat) !== (yj > lat) && lon < (xj - xi) * (lat - yi) / (yj - yi) + xi)
        dedans = !dedans;
    }
  }
  return dedans;
}
$('#localiser').addEventListener('click', () => {
  if (!navigator.geolocation) { $('#portee').textContent = 'localisation indisponible'; return; }
  $('#portee').textContent = 'recherche du département…';
  navigator.geolocation.getCurrentPosition(pos => {
    const lon = pos.coords.longitude, lat = pos.coords.latitude;
    let trouve = null;
    for (const code in D.contours)
      if (dansPolygone(lon, lat, D.contours[code])) { trouve = code; break; }
    if (trouve) { selT.value = trouve; majTout(); $('#portee').textContent = 'position oubliée'; }
    else $('#portee').textContent = 'hors de France métropolitaine';
  }, () => { $('#portee').textContent = 'localisation refusée'; });
});

/* ---------- orchestration ---------- */
function majTout() {
  territoire = selT.value; classe = selC.value; couleur = $('#couleur').value;
  const t0 = performance.now();
  dessinerCarte();
  rendreMaree(); rendreMur(); rendreDepartements(); rendreEnseignes();
  rendreMuettes(); rendrePrix(); rendreApres(); rendreRecords();
  rendreEditions(); rendreMethode();
  const ms = Math.round(performance.now() - t0);
  const t = cumul();
  $('#portee').textContent = (territoire === 'FR' ? 'France entière' : 'département ' + territoire)
    + ', ' + nf.format(t.pdc) + ' points, recalcul en ' + ms + ' ms';
}
selT.addEventListener('change', majTout);
selC.addEventListener('change', majTout);
$('#couleur').addEventListener('change', majTout);
majTout();
"""
