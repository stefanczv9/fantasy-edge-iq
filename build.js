// Fantasy Edge IQ — static build (Vercel: "npm run build" -> "node build.js", output: public/)
//
// 1) kopira korijenske fajlove (.html .csv .xml .txt .png .svg .webmanifest) u public/
// 2) pravi "clean" rute (npr. /sr/euroleague/dashboard) iz korijenskih fajlova po tabeli ISPOD
// 3) cuva sajt od pokvarene pocetne: ako index.html / sr-index.html / el-index.html izgleda kao dashboard,
//    build staje (exit 1) i Vercel ostavlja prethodni ispravan deployment.
// Nova stranica = jedan red u tabeli ROUTES.

const fs = require('fs');
const path = require('path');

const root = process.cwd();
const pub = path.join(root, 'public');

function fail(msg) { console.error('BUILD STOP: ' + msg); process.exit(1); }

// ---- zastita pocetnih stranica -------------------------------------------------------------
for (const home of ['index.html', 'sr-index.html', 'el-index.html']) {
  const p = path.join(root, home);
  if (!fs.existsSync(p)) fail(`nedostaje ${home}`);
  const size = fs.statSync(p).size;
  const head = fs.readFileSync(p, 'utf8').slice(0, 4000);
  const title = (head.match(/<title>([\s\S]*?)<\/title>/i) || [, ''])[1];
  if (size > 300 * 1024 || /advanced dashboard|napredni dashboard|αναλυτικό dashboard/i.test(title)) {
    fail(`${home} izgleda kao dashboard (naslov "${title.trim()}", ${size} B) - pocetna je pokvarena, build prekinut`);
  }
}

// ---- 1) korijenski fajlovi -> public/ -------------------------------------------------------
fs.rmSync(pub, { recursive: true, force: true });
fs.mkdirSync(pub, { recursive: true });

function copy(src, dst) {
  const from = path.join(root, src);
  const to = path.join(pub, dst);
  if (!fs.existsSync(from)) { console.log(`skip missing ${src}`); return false; }
  fs.mkdirSync(path.dirname(to), { recursive: true });
  fs.copyFileSync(from, to);
  return true;
}

let rootCount = 0;
for (const file of fs.readdirSync(root)) {
  if (!fs.statSync(path.join(root, file)).isFile()) continue;
  if (/\.(html|csv|xml|txt|png|svg|webmanifest)$/i.test(file) && file !== 'pricing.html') {
    copy(file, file); rootCount++;
  }
}

// ---- 2) rute ---------------------------------------------------------------------------------
const ROUTES = [];
const add = (src, ...dests) => dests.forEach((d) => ROUTES.push([src, d]));
const L = [['', ''], ['sr-', 'sr/'], ['el-', 'el/']];            // [prefiks fajla, prefiks rute]

// EuroLeague
add('euroleague-dashboard.html', 'euroleague/index.html', 'euroleague/dashboard/index.html');
add('sr-euroleague-dashboard.html', 'sr/euroleague/dashboard/index.html');
add('el-euroleague-dashboard.html', 'el/euroleague/dashboard/index.html');
for (const [f, r] of L) {
  add(`${f}euroleague-defense-vs-position.html`, `${r}euroleague/defense-vs-position/index.html`);
  add(`${f}euroleague-domestic-competitions.html`, `${r}euroleague/domestic-competitions/index.html`);
}
// Lineup IQ postoji samo na engleskom; SR/EL rute pokazuju isti fajl (na njih vode linkovi sa EuroCup stranica)
add('euroleague-team-analyzer.html', 'euroleague/team-analyzer/index.html', 'sr/euroleague/team-analyzer/index.html', 'el/euroleague/team-analyzer/index.html');
add('euroleague-round2-value-picks.html', 'euroleague/round2-top-3-value-picks/index.html');
add('sr-euroleague-round2-value-picks.html', 'sr/euroleague/top-3-value-igraca-drugo-kolo/index.html');
add('el-euroleague-round2-value-picks.html', 'el/euroleague/round2-top-3-value-picks/index.html');
add('sr-euroleague.html', 'sr/euroleague/index.html');
add('el-euroleague.html', 'el/euroleague/index.html');

// EuroCup
for (const [f, r] of L) {
  add(`${f}eurocup-dashboard.html`, `${r}eurocup/index.html`, `${r}eurocup/dashboard/index.html`);
  add(`${f}eurocup-defense-vs-position.html`, `${r}eurocup/defense-vs-position/index.html`);
  add(`${f}eurocup-domestic-competitions.html`, `${r}eurocup/domestic-competitions/index.html`);
}

// FPL
add('premier-league-dashboard.html', 'premier-league/index.html', 'premier-league/dashboard/index.html');
add('premier-league-team-analyzer.html', 'premier-league/team-analyzer/index.html');
add('sr-premier-league.html', 'sr/premier-league/index.html');
add('el-premier-league.html', 'el/premier-league/index.html');

// pocetne + staticne stranice
add('sr-index.html', 'sr/index.html');
add('el-index.html', 'el/index.html');
for (const page of ['methodology', 'about', 'privacy', 'terms', 'disclaimer']) {
  for (const [f, r] of L) add(`${f}${page}.html`, `${r}${page}/index.html`);
}

let made = 0, skipped = [];
for (const [src, dst] of ROUTES) { if (copy(src, dst)) made++; else skipped.push(src); }

// ---- 3) SEO profilne stranice (igraci/timovi/hubovi) + prosireni sitemap u public/ -----------
try {
  require('./build_player_pages.js').run(root, pub);
} catch (e) {
  fail('SEO player pages generator: ' + (e && e.message ? e.message : e));
}

// ---- 4) vidljivi linkovi ka profilnim stranicama (nav + sekcija na pocetnim) -------------------
(function injectPlayerLinks() {
  const HUBS = [['euroleague', '/euroleague/players/'], ['eurocup', '/eurocup/players/'], ['premier-league', '/premier-league/players/']];
  const T = {
    '':  { nav: 'Players', h2: 'Player profiles', p: 'Searchable profiles for every tracked player: price and price change, minutes, PIR/PPG, projections, popularity and next-five fixture difficulty.',
           c: ['EuroLeague Fantasy', 'EuroCup Fantasy', 'Fantasy Premier League'], s: ['player & team profiles, A-Z search', 'player & team profiles, A-Z search', 'player & team profiles, A-Z search'] },
    sr: { nav: 'Igra\u010di', h2: 'Profili igra\u010da', p: 'Pretra\u017eivi profili svih pra\u0107enih igra\u010da: cijena i promjena, minute, PIR/PPG, projekcije, popularnost i te\u017eina rasporeda u narednih 5 kola.',
           c: ['EuroLeague igra\u010di', 'EuroCup igra\u010di', 'FPL igra\u010di'], s: ['profili igra\u010da i timova, A-\u017d pretraga', 'profili igra\u010da i timova, A-\u017d pretraga', 'profili igra\u010da i klubova, A-\u017d pretraga'] },
    el: { nav: '\u03a0\u03b1\u03af\u03ba\u03c4\u03b5\u03c2', h2: '\u03a0\u03c1\u03bf\u03c6\u03af\u03bb \u03c0\u03b1\u03b9\u03ba\u03c4\u03ce\u03bd', p: '\u03a0\u03c1\u03bf\u03c6\u03af\u03bb \u03b3\u03b9\u03b1 \u03ba\u03ac\u03b8\u03b5 \u03c0\u03b1\u03af\u03ba\u03c4\u03b7: \u03c4\u03b9\u03bc\u03ae \u03ba\u03b1\u03b9 \u03bc\u03b5\u03c4\u03b1\u03b2\u03bf\u03bb\u03ae, \u03bb\u03b5\u03c0\u03c4\u03ac, PIR/PPG, \u03c0\u03c1\u03bf\u03b2\u03bf\u03bb\u03ad\u03c2, \u03b4\u03b7\u03bc\u03bf\u03c3\u03b9\u03cc\u03c4\u03b7\u03c4\u03b1 \u03ba\u03b1\u03b9 \u03b4\u03c5\u03c3\u03ba\u03bf\u03bb\u03af\u03b1 \u03b5\u03c0\u03cc\u03bc\u03b5\u03c6\u03c9\u03bd 5 \u03b1\u03b3\u03c9\u03bd\u03b9\u03c3\u03c4\u03b9\u03ba\u03ce\u03bd.',
           c: ['\u03a0\u03b1\u03af\u03ba\u03c4\u03b5\u03c2 EuroLeague', '\u03a0\u03b1\u03af\u03ba\u03c4\u03b5\u03c2 EuroCup', '\u03a0\u03b1\u03af\u03ba\u03c4\u03b5\u03c2 FPL'], s: ['\u03c0\u03c1\u03bf\u03c6\u03af\u03bb \u03c0\u03b1\u03b9\u03ba\u03c4\u03ce\u03bd \u03ba\u03b1\u03b9 \u03bf\u03bc\u03ac\u03b4\u03c9\u03bd', '\u03c0\u03c1\u03bf\u03c6\u03af\u03bb \u03c0\u03b1\u03b9\u03ba\u03c4\u03ce\u03bd \u03ba\u03b1\u03b9 \u03bf\u03bc\u03ac\u03b4\u03c9\u03bd', '\u03c0\u03c1\u03bf\u03c6\u03af\u03bb \u03c0\u03b1\u03b9\u03ba\u03c4\u03ce\u03bd \u03ba\u03b1\u03b9 \u03bf\u03bc\u03ac\u03b4\u03c9\u03bd'] }
  };
  const card = (hub, title, sub) => `<a href="${hub}" style="display:block;padding:16px 18px;border:1px solid rgba(148,163,184,.25);border-radius:12px;background:rgba(15,23,42,.55);color:#e2e8f0;text-decoration:none"><strong style="display:block;color:#7dd3fc;margin-bottom:6px">${title}</strong><span style="color:#94a3b8;font-size:14px">${sub}</span></a>`;
  const walk = d => fs.readdirSync(d, { withFileTypes: true }).flatMap(e => e.isDirectory() ? walk(path.join(d, e.name)) : [path.join(d, e.name)]);
  let n = 0;
  for (const f of walk(pub)) {
    if (!f.endsWith('.html')) continue;
    const rel = path.relative(pub, f).split(path.sep).join('/');
    const lang = rel.startsWith('sr/') ? 'sr' : rel.startsWith('el/') ? 'el' : '';
    const t = T[lang];
    const isHome = ['index.html', 'sr/index.html', 'el/index.html'].includes(rel);
    const m = rel.match(/(?:^|\/)(euroleague|eurocup|premier-league)\/dashboard\/index\.html$/);
    if (!isHome && !m) continue;
    let html = fs.readFileSync(f, 'utf8');
    const navA = `<a href="${isHome ? HUBS[0][1] : '/' + m[1] + '/players/'}" style="color:#7dd3fc;text-decoration:none;font-weight:600">${t.nav}</a>`;
    const ni = html.indexOf('</nav>');
    if (ni > 0 && !html.includes('player-profiles-nav')) { html = html.slice(0, ni) + `<span id="player-profiles-nav"></span>` + navA + html.slice(ni); n++; }
    if (isHome && !html.includes('id="player-profiles"')) {
      const cards = HUBS.map(([k, hub], j) => card(hub, t.c[j], t.s[j])).join('');
      const sec = `<section id="player-profiles" style="max-width:1100px;margin:40px auto;padding:0 22px"><h2 style="font-size:26px;margin:0 0 8px;color:#f1f5f9">${t.h2}</h2><p style="margin:0 0 18px;color:#94a3b8">${t.p}</p><div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:14px">${cards}</div></section>`;
      const fi = html.search(/<footer/i);
      if (fi > 0) html = html.slice(0, fi) + sec + html.slice(fi); else html = html.replace('</body>', sec + '</body>');
    }
    fs.writeFileSync(f, html);
  }
  console.log('player-links injected into', n, 'pages');
})();

// ---- provjera --------------------------------------------------------------------------------
for (const must of ['index.html', 'euroleague/dashboard/index.html', 'sr/index.html', 'el/index.html']) {
  if (!fs.existsSync(path.join(pub, must))) fail(`public/${must} nije napravljen`);
}
console.log(`korijenskih fajlova: ${rootCount} | ruta napravljeno: ${made}/${ROUTES.length}` + (skipped.length ? ` | bez izvora: ${[...new Set(skipped)].join(', ')}` : ''));
console.log('build-ok');
