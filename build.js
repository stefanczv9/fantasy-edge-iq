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

// ---- provjera --------------------------------------------------------------------------------
for (const must of ['index.html', 'euroleague/dashboard/index.html', 'sr/index.html', 'el/index.html']) {
  if (!fs.existsSync(path.join(pub, must))) fail(`public/${must} nije napravljen`);
}
console.log(`korijenskih fajlova: ${rootCount} | ruta napravljeno: ${made}/${ROUTES.length}` + (skipped.length ? ` | bez izvora: ${[...new Set(skipped)].join(', ')}` : ''));
console.log('build-ok');
