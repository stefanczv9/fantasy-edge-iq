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

// ---- 3b) FAZA 3: auto Round X preview clanak + social pack ------------------------------------
try {
  require('./build_round_preview.js').run(root, pub);
} catch (e) {
  console.log('round preview skip: ' + (e && e.message ? e.message : e));
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
    const chip = lang === 'sr' ? 'NOVO' : lang === 'el' ? '\u039d\u0395\u039f' : 'NEW';
    const navA = `<a id="player-profiles-nav" href="${isHome ? HUBS[0][1] : '/' + m[1] + '/players/'}" style="background:linear-gradient(90deg,#0ea5e9,#22d3ee);color:#04121f;padding:6px 14px;border-radius:999px;font-weight:800;text-decoration:none;margin-left:8px;box-shadow:0 0 0 1px rgba(125,211,252,.45),0 4px 14px rgba(14,165,233,.35)">${t.nav} <span style="background:#facc15;color:#111827;border-radius:999px;padding:1px 7px;font-size:10px;font-weight:800;margin-left:4px">${chip}</span></a>`;
    if (!html.includes('player-profiles-nav')) {
      const navEnd = html.indexOf('</nav>');
      if (navEnd > 0) {
        const navSeg = html.slice(0, navEnd);
        let ai = -1;
        for (const key of ['defense-vs-position', 'premier-league']) {
          const mm = navSeg.match(new RegExp('<a[^>]*href="[^"]*' + key + '[^"]*"[^>]*>[\\s\\S]*?</a>'));
          if (mm) { ai = navSeg.indexOf(mm[0]) + mm[0].length; break; }
        }
        if (ai < 0) ai = navEnd;
        html = html.slice(0, ai) + navA + html.slice(ai);
        n++;
      }
    }
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

// ---- 5) FAZA 2: countdown baner + cross-linkovi + (opciono) Telegram/Ko-fi iz feiq-config.json --
(function phase2() {
  let CFG = {};
  try { CFG = JSON.parse(fs.readFileSync(path.join(root, 'feiq-config.json'), 'utf8')); } catch (e) {}
  const L2 = {
    '':  { lock: 'lineup lock', closes: 'closes in', wd: ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'], next: 'Next →', dom: 'Domestic', ctaEL: 'Open Lineup IQ', ctaDash: 'Open dashboard', tgT: 'Picks & injury alerts before every round', tgP: 'Value picks, late price changes and a 2h-before-deadline reminder on Telegram — free, no email, no passwords.', tgB: 'Join the channel →' },
    sr: { lock: 'zaključavanje postave', closes: 'zatvara se za', wd: ['ned','pon','uto','sri','čet','pet','sub'], next: 'Dalje →', dom: 'Domaća', ctaEL: 'Otvori Lineup IQ', ctaDash: 'Otvori dashboard', tgT: 'Pickovi i injury alertovi prije svakog kola', tgP: 'Vrijednosni pickovi, kasne promjene cijena i podsjetnik 2h prije deadline-a na Telegramu — besplatno, bez maila i šifri.', tgB: 'Pridruži se kanalu →' },
    el: { lock: 'lock διαθεσιμότητας', closes: 'κλείνει σε', wd: ['Κυρ','Δευ','Τρι','Τετ','Πεμ','Παρ','Σαβ'], next: 'Επόμενο →', dom: 'Εγχώρια', ctaEL: 'Άνοιξε Lineup IQ', ctaDash: 'Άνοιξε το dashboard', tgT: 'Πικς και ειδοποιήσεις τραυματισμών πριν από κάθε γύρο', tgP: 'Πικς αξίας, αλλαγές τιμών και υπενθύμιση 2 ώρες πριν το deadline στο Telegram — δωρεάν, χωρίς email και κωδικούς.', tgB: 'Γίνε μέλος →' }
  };
  const csvOf = f => { try { return fs.readFileSync(path.join(root, f), 'utf8'); } catch (e) { return ''; } };
  const minISO = csv => {
    if (!csv) return null;
    const lines = csv.split(/\r?\n/); if (lines.length < 2) return null;
    const hdr = lines[0].split(',');
    const ci = hdr.findIndex(h => /date|start/i.test(h)); if (ci < 0) return null;
    let best = null;
    for (let r = 1; r < lines.length; r++) {
      const c = lines[r].split(',')[ci];
      const m = c && c.match(/\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}/);
      if (m && (!best || m[0] < best)) best = m[0];
    }
    return best;
  };
  // FPL deadline iz bootstrap-a
  let fplIso = null, fplName = 'FPL';
  try {
    const b = JSON.parse(fs.readFileSync(path.join(root, 'fpl_fantasy_data', 'bootstrap_static.json'), 'utf8'));
    const ev = (b.events || []).find(e => e.is_next) || (b.events || []).find(e => e.is_current);
    if (ev && ev.deadline_time) { fplIso = ev.deadline_time; fplName = 'FPL ' + (ev.name || '').replace('Gameweek', 'GW'); }
  } catch (e) {}
  // EL: broj kola + datum iz next5 detalja
  let elNum = '';
  try { elNum = ' MD' + (JSON.parse(fs.readFileSync(path.join(root, 'euroleague_fantasy_data', 'league_config.json'), 'utf8')).current_matchday || {}).number; } catch (e) {}
  const elIso = minISO(csvOf('euroleague_fantasy_data/team_next5_schedule_detail.csv'));
  const ecIso = minISO(csvOf('eurocup_fantasy_data/team_next5_schedule_detail.csv'));
  const fmt = (iso, lang) => {
    const d = new Date(iso.replace(' ', 'T') + (/[Zz]|[+-]\d{2}:?\d{2}$/.test(iso) ? '' : 'Z'));
    const ce = new Date(d.getTime() + 2 * 3600000);
    const t = L2[lang].wd[ce.getUTCDay()];
    const dd = String(ce.getUTCDate()).padStart(2, '0'), mm = String(ce.getUTCMonth() + 1).padStart(2, '0');
    const hh = String(ce.getUTCHours()).padStart(2, '0'), mi = String(ce.getUTCMinutes()).padStart(2, '0');
    return `${t} ${dd}.${mm}. ${hh}:${mi}`;
  };
  const SCRIPT = `<script>(function(){var el=document.getElementById('lock-banner');if(!el)return;var dl=new Date(el.getAttribute('data-deadline'));function u(){var ms=dl-new Date();if(ms<=0){el.remove();return;}var d=Math.floor(ms/864e5),h=Math.floor(ms/36e5)%24,m=Math.floor(ms/6e4)%60;var c=el.querySelector('.cd');if(c)c.textContent=d+'d '+String(h).padStart(2,'0')+'h '+String(m).padStart(2,'0')+'m';}u();setInterval(u,30000);})();</script>`;
  const walk = d => fs.readdirSync(d, { withFileTypes: true }).flatMap(e => e.isDirectory() ? walk(path.join(d, e.name)) : [path.join(d, e.name)]);
  let nb = 0, nx = 0, ntg = 0, nk = 0;
  for (const f of walk(pub)) {
    if (!f.endsWith('.html')) continue;
    const rel = path.relative(pub, f).split(path.sep).join('/');
    const lang = rel.startsWith('sr/') ? 'sr' : rel.startsWith('el/') ? 'el' : '';
    const t = L2[lang];
    const pfx = lang ? '/' + lang : '';
    const sec = rel.includes('eurocup') ? 'eurocup' : rel.includes('premier-league') ? 'premier-league' : rel.includes('euroleague') ? 'euroleague' : null;
    const isCore = /(dashboard|defense-vs-position|domestic-competitions|players)\/index\.html$/.test(rel) || ['index.html','sr/index.html','el/index.html'].includes(rel);
    if (!isCore) continue;
    let html = fs.readFileSync(f, 'utf8');
    // countdown baner
    const nowB = Date.now();
    const fut = x => x && new Date(x.replace(' ', 'T') + (/[Zz]|[+-]\d{2}:?\d{2}$/.test(x) ? '' : 'Z')).getTime() > nowB;
    const ALLD = [['euroleague', elIso], ['eurocup', ecIso], ['premier-league', fplIso]];
    const own = !sec ? elIso : (ALLD.find(a => a[0] === sec) || [null, null])[1];
    let iso = null, useSec = null;
    if (fut(own)) { iso = own; useSec = sec || 'euroleague'; } else { const nx = ALLD.find(a => fut(a[1])); if (nx) { iso = nx[1]; useSec = nx[0]; } }
    const comp = useSec === 'eurocup' ? (lang === 'sr' ? 'EuroCup sljedeće kolo' : lang === 'el' ? 'EuroCup επόμενος γύρος' : 'EuroCup next round') : useSec === 'premier-league' ? fplName : 'EuroLeague' + elNum;
    if (iso && !html.includes('lock-banner')) {
      let ni = html.indexOf('<nav');
      if (ni < 0) { const bi = html.indexOf('<body'); ni = bi > 0 ? html.indexOf('>', bi) + 1 : -1; }
      if (ni > 0) {
        const cta = useSec === 'euroleague' ? pfx + '/euroleague/team-analyzer' : pfx + '/' + useSec;
        const ban = `<div id="lock-banner" data-deadline="${iso.replace(' ', 'T')}Z" style="display:flex;gap:12px;align-items:center;justify-content:center;flex-wrap:wrap;padding:9px 16px;background:linear-gradient(90deg,#7c3aed,#db2777);color:#fff;font-size:13.5px;font-weight:600"><span>⏰ ${comp} ${t.lock}: ${fmt(iso, lang)} CEST</span><span>${t.closes} <b class="cd" style="font-family:ui-monospace,Menlo,Consolas,monospace;background:rgba(0,0,0,.35);padding:2px 9px;border-radius:7px">…</b></span><a href="${cta}" style="background:#fff;color:#7c3aed;padding:4px 13px;border-radius:999px;font-weight:800;text-decoration:none;font-size:12.5px">${useSec === 'euroleague' ? t.ctaEL : t.ctaDash}</a></div>` + SCRIPT;
        html = html.slice(0, ni) + ban + html.slice(ni); nb++;
      }
    }
    // cross-link traka
    if (sec && !html.includes('xlinks-strip')) {
      const chips = [];
      chips.push([pfx + '/' + sec + '/players/', lang === 'sr' ? 'Igrači' : lang === 'el' ? 'Παίκτες' : 'Players']);
      if (sec === 'euroleague') { try { const NN = (JSON.parse(fs.readFileSync(path.join(root, 'euroleague_fantasy_data', 'league_config.json'), 'utf8')).current_matchday || {}).number; if (NN) chips.push([pfx + '/euroleague/round-' + NN + '-preview/', (lang === 'sr' ? 'Kolo ' : lang === 'el' ? 'Γύρος ' : 'Round ') + NN + ' preview']); } catch (e) {} }
      if (!rel.includes('defense-vs-position')) chips.push([pfx + '/' + sec + '/defense-vs-position', 'Defense vs Position']);
      if (!rel.includes('domestic-competitions')) chips.push([pfx + '/' + sec + '/domestic-competitions', t.dom]);
      for (const [k, lab] of [['euroleague', 'EuroLeague Fantasy'], ['eurocup', 'EuroCup Fantasy'], ['premier-league', 'FPL']]) if (k !== sec) chips.push([pfx + '/' + k, lab]);
      const strip = `<div id="xlinks-strip" style="display:flex;gap:10px;flex-wrap:wrap;align-items:center;padding:8px 22px 20px"><span style="color:#64748b;font-size:12.5px">${t.next}</span>` + chips.map(([h, l]) => `<a href="${h}" style="border:1px solid rgba(125,211,252,.4);color:#7dd3fc;padding:6px 14px;border-radius:999px;font-size:13px;text-decoration:none;font-weight:600">${l}</a>`).join('') + `</div>`;
      const fi = html.search(/<footer/i);
      if (fi > 0) html = html.slice(0, fi) + strip + html.slice(fi); else html = html.replace('</body>', strip + '</body>');
      nx++;
    }
    // Telegram capture (samo ako je upisan u config)
    if (CFG.telegram_url && !html.includes('tg-capture')) {
      const tg = `<div id="tg-capture" style="margin:26px 22px;padding:22px 24px;border-radius:16px;background:linear-gradient(120deg,rgba(34,211,238,.14),rgba(167,139,250,.14));border:1px solid rgba(125,211,252,.35);display:flex;gap:18px;align-items:center;flex-wrap:wrap"><div style="font-size:32px">📣</div><div><strong style="display:block;font-size:17px;color:#f1f5f9;margin-bottom:4px">${t.tgT}</strong><span style="color:#94a3b8;font-size:13.5px">${t.tgP}</span></div><a href="${CFG.telegram_url}" style="margin-left:auto;background:#22d3ee;color:#083344;padding:10px 20px;border-radius:999px;font-weight:800;text-decoration:none;font-size:14px">${t.tgB}</a></div>`;
      const fi = html.search(/<footer/i);
      if (fi > 0) html = html.slice(0, fi) + tg + html.slice(fi);
      ntg++;
    }
    // Ko-fi plutajuce dugme (samo ako je upisano u config)
    if (CFG.kofi_url && !html.includes('kofi-float')) {
      html = html.replace('</body>', `<a id="kofi-float" href="${CFG.kofi_url}" style="position:fixed;right:18px;bottom:16px;background:#ff5e5b;color:#fff;padding:10px 18px;border-radius:999px;font-weight:800;text-decoration:none;box-shadow:0 8px 24px rgba(255,94,91,.4);font-size:14px;z-index:99">☕ Ko-fi</a></body>`);
      nk++;
    }
    fs.writeFileSync(f, html);
  }
  console.log(`faza2: baneri ${nb} | cross-link ${nx} | telegram ${ntg} | kofi ${nk}`);
})();

// ---- provjera --------------------------------------------------------------------------------
for (const must of ['index.html', 'euroleague/dashboard/index.html', 'sr/index.html', 'el/index.html']) {
  if (!fs.existsSync(path.join(pub, must))) fail(`public/${must} nije napravljen`);
}
console.log(`korijenskih fajlova: ${rootCount} | ruta napravljeno: ${made}/${ROUTES.length}` + (skipped.length ? ` | bez izvora: ${[...new Set(skipped)].join(', ')}` : ''));
console.log('build-ok');
