// Fantasy Edge IQ — SEO profilne stranice (igraci + timovi) + indeks hubovi + prosireni sitemap.
// Generise se u public/ tokom Vercel build-a (poziva ga build.js). Nema novih zavisnosti.
// Rute: /euroleague/players/[slug], /euroleague/teams/[slug], /premier-league/..., /eurocup/...

const fs = require('fs');
const path = require('path');

const SITE = 'https://www.fantasyedgeiq.com';

// ---------- mali RFC4180 CSV parser ----------
function parseCSV(text) {
  const rows = [];
  let row = [], field = '', i = 0, inQ = false;
  const n = text.length;
  while (i < n) {
    const c = text[i];
    if (inQ) {
      if (c === '"') {
        if (text[i + 1] === '"') { field += '"'; i += 2; continue; }
        inQ = false; i++; continue;
      }
      field += c; i++; continue;
    }
    if (c === '"') { inQ = true; i++; continue; }
    if (c === ',') { row.push(field); field = ''; i++; continue; }
    if (c === '\r') { i++; continue; }
    if (c === '\n') { row.push(field); rows.push(row); row = []; field = ''; i++; continue; }
    field += c; i++;
  }
  if (field.length || row.length) { row.push(field); rows.push(row); }
  const head = rows.shift() || [];
  return rows.filter(r => r.length > 1 || (r.length === 1 && r[0] !== '')).map(r => {
    const o = {};
    head.forEach((h, k) => { o[h] = r[k] !== undefined ? r[k] : ''; });
    return o;
  });
}

const readCSV = (root, name) => {
  const p = path.join(root, name);
  if (!fs.existsSync(p)) return [];
  return parseCSV(fs.readFileSync(p, 'utf8'));
};

// ---------- helperi ----------
function slugify(s) {
  return String(s || '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '')
    .toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
}
const esc = s => String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const num = (v, d = 1) => {
  const x = parseFloat(v);
  if (!isFinite(x)) return '—';
  return String(Math.round(x * 10 ** d) / 10 ** d);
};
const pct = v => { const x = parseFloat(v); return isFinite(x) ? (x > 1 ? num(x, 1) + '%' : num(x * 100, 1) + '%') : '—'; };
const bool = v => String(v) === 'True' || v === true || v === 'true';

function css() {
  return `:root{--bg:#07101d;--bg2:#0d1b2f;--card:#111f34;--card2:#162b49;--txt:#eef6ff;--mut:#9fb1c9;--line:rgba(255,255,255,.11);--blue:#5bbcff;--green:#22c55e;--yellow:#ffd166;--red:#fb7185}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 18% 0%,#1c4f7d 0,#0b1a2e 36%,#07101d 72%);color:var(--txt);font-family:Inter,system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;line-height:1.55}
a{color:var(--blue);text-decoration:none}a:hover{text-decoration:underline}.wrap{max-width:1080px;margin:0 auto;padding:0 20px}
.nav{display:flex;justify-content:space-between;align-items:center;gap:14px;padding:18px 0;flex-wrap:wrap}
.logo{font-weight:950;font-size:20px;letter-spacing:-.03em;color:var(--txt)}.logo span{color:var(--blue)}
.links{display:flex;gap:14px;flex-wrap:wrap;font-size:14px;color:var(--mut)}.links a{color:var(--mut)}
h1{font-size:clamp(26px,5vw,38px);letter-spacing:-.02em;margin:18px 0 6px}.sub{color:var(--mut);font-size:15px;margin:0 0 18px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px;margin:16px 0}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:12px 14px}
.card b{display:block;font-size:20px;margin-top:2px}.card span{color:var(--mut);font-size:11.5px;text-transform:uppercase;letter-spacing:.06em}
.box{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:16px 18px;margin:14px 0}
.box h2{font-size:16px;margin:0 0 10px}.mut{color:var(--mut);font-size:13px}
table{width:100%;border-collapse:collapse;font-size:13.5px}th,td{padding:7px 8px;text-align:left;border-bottom:1px solid var(--line)}th{color:var(--mut);font-size:11.5px;text-transform:uppercase;letter-spacing:.05em}
.pill{display:inline-block;border-radius:999px;padding:3px 10px;font-size:12px;font-weight:700;margin-right:6px}
.pill.red{background:rgba(251,113,133,.15);color:var(--red)}.pill.green{background:rgba(34,197,94,.15);color:var(--green)}.pill.yellow{background:rgba(255,209,102,.15);color:var(--yellow)}
ul.nl{margin:6px 0;padding-left:18px}footer{margin:34px 0 26px;color:var(--mut);font-size:12.5px;border-top:1px solid var(--line);padding-top:14px}
.search{width:100%;padding:10px 12px;border-radius:12px;border:1px solid var(--line);background:var(--bg2);color:var(--txt);font-size:15px;margin:8px 0}`;
}

function page({ title, desc, canonical, crumbs, body, jsonLd }) {
  const bc = {
    '@context': 'https://schema.org', '@type': 'BreadcrumbList',
    itemListElement: crumbs.map((c, i) => ({ '@type': 'ListItem', position: i + 1, name: c[0], item: SITE + c[1] }))
  };
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>${esc(title)}</title><meta name="description" content="${esc(desc)}">
<link rel="canonical" href="${canonical}"><meta name="robots" content="index,follow,max-snippet:-1,max-image-preview:large">
<meta property="og:type" content="profile"><meta property="og:site_name" content="Fantasy Edge IQ"><meta property="og:title" content="${esc(title)}"><meta property="og:description" content="${esc(desc)}"><meta property="og:url" content="${canonical}">
<link rel="icon" href="/favicon.svg" type="image/svg+xml"><meta name="theme-color" content="#07101d">
<script type="application/ld+json">${JSON.stringify(bc)}</script>${jsonLd ? `<script type="application/ld+json">${JSON.stringify(jsonLd)}</script>` : ''}
<style>${css()}</style></head><body><div class="wrap">
<nav class="nav"><a class="logo" href="/">Fantasy<span>Edge</span> IQ</a>
<div class="links"><a href="/euroleague/dashboard">EuroLeague</a><a href="/eurocup/dashboard">EuroCup</a><a href="/premier-league/dashboard">FPL</a><a href="/euroleague/defense-vs-position">DvP</a><a href="/methodology">Methodology</a></div></nav>
${body}
<footer>Fantasy Edge IQ — independent fantasy analytics. Not affiliated with Euroleague Basketball, the Premier League or FPL. Data: public fantasy & official stats. <a href="/">Home</a></footer>
</div></body></html>`;
}

const card = (label, value) => `<div class="card"><span>${esc(label)}</span><b>${value}</b></div>`;

function writeOut(pub, rel, html) {
  const dir = path.join(pub, rel);
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, 'index.html'), html, 'utf8');
}

// ---------- EuroLeague ----------
function buildEuroLeague(root, pub, stamp, urls) {
  const P = readCSV(root, 'euroleague-players-full.csv');
  const T = readCSV(root, 'euroleague-team-context.csv');
  const S = readCSV(root, 'euroleague-next5-schedule.csv');
  if (!P.length) return 0;
  const byTeam = {};
  P.forEach(p => { (byTeam[p.team_abbr] = byTeam[p.team_abbr] || []).push(p); });
  const seen = new Set();
  const slugOf = p => {
    let s = slugify(p.name);
    if (seen.has(s)) s = s + '-' + p.player_id;
    seen.add(s); return s;
  };
  const pslug = {};
  P.forEach(p => { pslug[p.player_id] = slugOf(p); });

  // player pages
  P.forEach(p => {
    const slug = pslug[p.player_id];
    const url = `/euroleague/players/${slug}`;
    const pills = [bool(p.is_injured) ? '<span class="pill red">Injured</span>' : '',
      bool(p.started_from_bench) ? '<span class="pill yellow">Bench risk</span>' : '',
      p.match_status === 'played' ? '' : '<span class="pill green">Available</span>'].join('');
    const next5 = (p.next5_opponents || '').split('·').map(s => s.trim()).filter(Boolean)
      .map(s => `<li>${esc(s)}</li>`).join('');
    const body = `
<h1>${esc(p.name)}</h1>
<p class="sub">${esc(p.team_name || p.team_abbr)} · ${esc(p.position || p.pos_short)} · EuroLeague Fantasy profile ${pills}</p>
<div class="cards">
${card('Price', num(p.price) + ' <span class="mut">cr</span>')}${card('Change', (parseFloat(p.price_change) > 0 ? '+' : '') + num(p.price_change))}
${card('Proj PIR', num(p.proj_pir_est))}${card('Option score', num(p.option_score_next5, 0))}
${card('MIN/G', num(p.min_avg_current))}${card('PIR/G', num(p.pir_avg_current))}
${card('PIR/min', num(p.pir_per_min_current, 3))}${card('Value PIR/cr', num(p.value_pir_per_credit, 2))}
${card('Popularity', pct(p.popularity_pct))}${card('GP', num(p.gp_current, 0))}
</div>
<div class="box"><h2>Next fixture & schedule</h2>
<p>Next: <b>${esc(p.next_opponent || '—')}</b> (${esc(p.home_away === 'H' ? 'home' : p.home_away === 'A' ? 'away' : p.home_away)}) · ${esc((p.next_start_local || '').slice(0, 16))} · matchup ease ${num(p.proj_matchup_ease_score, 0)} · FDR ${num(p.proj_fdr_1_easy_5_hard, 2)}</p>
<p class="mut">Next 5 (FDR 1 = easy, 5 = hard):</p><ul class="nl">${next5 || '<li>—</li>'}</ul></div>
<div class="box"><h2>Current season averages (official)</h2>
<table><tr><th>GP</th><th>MIN</th><th>PTS</th><th>PIR</th><th>REB</th><th>AST</th><th>STL</th><th>BLK</th><th>TOV</th><th>FGA/G</th><th>3P%</th><th>FT%</th></tr>
<tr><td>${num(p.gp_current, 0)}</td><td>${num(p.min_avg_current)}</td><td>${num(p.pts_avg_current)}</td><td>${num(p.pir_avg_current)}</td><td>${num(p.reb_avg_current)}</td><td>${num(p.ast_avg_current)}</td><td>${num(p.stl_avg_current)}</td><td>${num(p.blk_avg_current)}</td><td>${num(p.tov_avg_current)}</td><td>${num(p.fg_attempts_pg_current)}</td><td>${num(p['3p_pct_current'])}</td><td>${num(p.ft_pct_current)}</td></tr></table>
<p class="mut">2025-26 reference: ${num(p.min_avg_25_26)} MIN/G, ${num(p.pir_25_26)} PIR/G. Model: floor ${num(p.floor_est)} / ceiling ${num(p.ceiling_est)} PIR, role: ${esc(p.current_role_projection || '—')}.</p></div>
<p><a href="/euroleague/teams/${slugify(p.team_abbr)}">${esc(p.team_name || p.team_abbr)} team page</a> · <a href="/euroleague/players/">All EuroLeague fantasy players</a> · <a href="/euroleague/dashboard">EuroLeague dashboard</a> · <a href="/euroleague/defense-vs-position">Defense vs Position</a></p>`;
    const desc = `${p.name} (${p.team_abbr}) EuroLeague Fantasy: price ${num(p.price)} cr, projected PIR ${num(p.proj_pir_est)}, ${num(p.min_avg_current)} MIN/G, next ${p.next_opponent || '—'}. Value, minutes, usage and next-5 fixture difficulty.`;
    writeOut(pub, path.join('euroleague', 'players', slug), page({
      title: `${p.name} — EuroLeague Fantasy price, projection & stats | Fantasy Edge IQ`,
      desc, canonical: SITE + url,
      crumbs: [['Home', '/'], ['EuroLeague players', '/euroleague/players/'], [p.name, url]],
      body,
      jsonLd: { '@context': 'https://schema.org', '@type': 'Person', name: p.name, description: desc, memberOf: { '@type': 'SportsTeam', name: p.team_name || p.team_abbr } }
    }));
    urls.push([url, '0.6', 'weekly']);
  });

  // team pages
  T.forEach(t => {
    const slug = slugify(t.team_abbr);
    const url = `/euroleague/teams/${slug}`;
    const roster = (byTeam[t.team_abbr] || []).slice().sort((a, b) => (parseFloat(b.proj_pir_est) || 0) - (parseFloat(a.proj_pir_est) || 0));
    const rows = roster.map(p => `<tr><td><a href="/euroleague/players/${pslug[p.player_id]}">${esc(p.name)}</a></td><td>${esc(p.pos_short)}</td><td>${num(p.price)}</td><td>${num(p.min_avg_current)}</td><td>${num(p.pir_avg_current)}</td><td>${num(p.proj_pir_est)}</td></tr>`).join('');
    const sched = S.filter(s => s.team_abbr === t.team_abbr).slice(0, 5)
      .map(s => `<tr><td>MD ${esc(s.matchday)}</td><td>${esc(s.opponent)}</td><td>${esc(s.home_away)}</td><td>${esc((s.start_local || '').slice(0, 16))}</td><td>${num(s.matchup_ease_score, 0)}</td><td>${num(s.fdr_1_easy_5_hard, 2)}</td></tr>`).join('');
    const body = `
<h1>${esc(t.team_name)}</h1>
<p class="sub">EuroLeague fantasy team context: pace, shooting volume, defensive environment and schedule.</p>
<div class="cards">
${card('Pace', num(t.pace_possessions_pg))}${card('FGA/G', num(t.for_fga_pg))}${card('PIR allowed', num(t.allowed_pir_pg))}
${card('FGA allowed', num(t.allowed_fga_pg))}${card('OREB allowed', num(t.allowed_oreb_pg))}${card('Weakness score', num(t.team_defense_weakness_score, 0))}
</div>
<div class="box"><h2>Next five fixtures</h2><table><tr><th>Round</th><th>Opponent</th><th>H/A</th><th>Tip (local)</th><th>Matchup+</th><th>FDR</th></tr>${sched}</table></div>
<div class="box"><h2>Fantasy roster (by projected PIR)</h2><table><tr><th>Player</th><th>Pos</th><th>Price</th><th>MIN/G</th><th>PIR/G</th><th>Proj PIR</th></tr>${rows}</table></div>
<p><a href="/euroleague/players/">All players</a> · <a href="/euroleague/dashboard">Dashboard</a> · <a href="/euroleague/defense-vs-position">DvP</a></p>`;
    writeOut(pub, path.join('euroleague', 'teams', slug), page({
      title: `${t.team_name} — EuroLeague fantasy team context & fixtures | Fantasy Edge IQ`,
      desc: `${t.team_name}: pace ${num(t.pace_possessions_pg)}, FGA/G ${num(t.for_fga_pg)}, PIR allowed ${num(t.allowed_pir_pg)}, next-5 fixture difficulty and fantasy roster projections.`,
      canonical: SITE + url,
      crumbs: [['Home', '/'], ['EuroLeague players', '/euroleague/players/'], [t.team_name, url]], body
    }));
    urls.push([url, '0.7', 'weekly']);
  });

  // hub
  const rows = P.slice().sort((a, b) => (parseFloat(b.option_score_next5) || 0) - (parseFloat(a.option_score_next5) || 0))
    .map(p => `<tr><td><a href="/euroleague/players/${pslug[p.player_id]}">${esc(p.name)}</a></td><td>${esc(p.team_abbr)}</td><td>${esc(p.pos_short)}</td><td>${num(p.price)}</td><td>${num(p.min_avg_current)}</td><td>${num(p.pir_avg_current)}</td><td>${num(p.proj_pir_est)}</td></tr>`).join('');
  const teamLinks = T.map(t => `<a href="/euroleague/teams/${slugify(t.team_abbr)}">${esc(t.team_abbr)}</a>`).join(' · ');
  const body = `
<h1>EuroLeague Fantasy player profiles</h1>
<p class="sub">${P.length} player profiles and ${T.length} team pages: prices, minutes, PIR, projections, popularity and next-five fixture difficulty for the 2026-27 season.</p>
<input class="search" id="q" placeholder="Filter players or teams..." oninput="const v=this.value.toLowerCase();document.querySelectorAll('#tb tr').forEach(r=>{r.style.display=r.textContent.toLowerCase().includes(v)?'':'none'})">
<div class="box"><table><thead><tr><th>Player</th><th>Team</th><th>Pos</th><th>Price</th><th>MIN/G</th><th>PIR/G</th><th>Proj PIR</th></tr></thead><tbody id="tb">${rows}</tbody></table></div>
<p class="mut">Teams: ${teamLinks}</p>
<p><a href="/euroleague/dashboard">Open the full EuroLeague dashboard</a> · <a href="/euroleague/defense-vs-position">Defense vs Position</a></p>`;
  writeOut(pub, path.join('euroleague', 'players'), page({
    title: 'EuroLeague Fantasy player profiles & prices 2026-27 | Fantasy Edge IQ',
    desc: `Browse ${P.length} EuroLeague Fantasy player profiles: prices, minutes, PIR, projected PIR, popularity and next-5 schedule difficulty. Updated ${stamp}.`,
    canonical: SITE + '/euroleague/players/',
    crumbs: [['Home', '/'], ['EuroLeague players', '/euroleague/players/']], body
  }));
  urls.push(['/euroleague/players/', '0.8', 'daily']);
  return P.length + T.length + 1;
}

// ---------- FPL ----------
function buildFPL(root, pub, stamp, urls) {
  const P = readCSV(root, 'fpl_players.csv');
  if (!P.length) return 0;
  const teams = [...new Set(P.map(p => p.team_short))].sort();
  const byTeam = {};
  P.forEach(p => { (byTeam[p.team_short] = byTeam[p.team_short] || []).push(p); });
  const seen = new Set();
  const pslug = {};
  P.forEach(p => { let s = slugify(p.full_name || p.web_name); if (seen.has(s)) s += '-' + p.player_id; seen.add(s); pslug[p.player_id] = s; });

  P.forEach(p => {
    const slug = pslug[p.player_id];
    const url = `/premier-league/players/${slug}`;
    const pills = [p.status && p.status !== 'a' ? `<span class="pill red">${esc(p.status.toUpperCase())}</span>` : '',
      parseFloat(p.chance_next) < 75 ? `<span class="pill yellow">${num(p.chance_next, 0)}% next</span>` : ''].join('');
    const next5 = (p.next5 || '').split('·').map(s => s.trim()).filter(Boolean).map(s => `<li>${esc(s)}</li>`).join('');
    const body = `
<h1>${esc(p.full_name || p.web_name)}</h1>
<p class="sub">${esc(p.team)} · ${esc(p.position)} · FPL profile ${pills}</p>
<div class="cards">
${card('Price', '£' + num(p.price))}${card('GW change', (parseFloat(p.cost_change_gw) > 0 ? '+' : '') + num(p.cost_change_gw))}
${card('Form', num(p.form))}${card('PPG', num(p.points_per_game))}
${card('EP next', num(p.ep_next))}${card('Proj pts', num(p.proj_points_est))}
${card('Owned', num(p.selected_by_percent) + '%')}${card('MIN/GW', num(p.min_avg_gw))}
${card('ICT', num(p.ict_index))}${card('Pts', num(p.total_points, 0))}
</div>
<div class="box"><h2>Fixtures</h2><p>Next: <b>${esc(p.next_fixture || '—')}</b> · FDR ${num(p.next_fdr, 0)}</p>
<p class="mut">Next five (FDR):</p><ul class="nl">${next5 || '<li>—</li>'}</ul>
<p class="mut">Minutes trend: last 3 ${num(p.min_last3)} · last 5 ${num(p.min_last5)} per GW. ${p.news ? 'News: ' + esc(p.news) : ''}</p></div>
<div class="box"><h2>Season stats</h2>
<table><tr><th>Apps</th><th>Starts</th><th>Goals</th><th>Assists</th><th>CS</th><th>Bonus</th><th>xG</th><th>xA</th><th>xGI/90</th></tr>
<tr><td>${num(p.apps, 0)}</td><td>${num(p.starts, 0)}</td><td>${num(p.goals, 0)}</td><td>${num(p.assists, 0)}</td><td>${num(p.clean_sheets, 0)}</td><td>${num(p.bonus, 0)}</td><td>${num(p.xg, 2)}</td><td>${num(p.xa, 2)}</td><td>${num(p.xgi_per_90, 2)}</td></tr></table></div>
<p><a href="/premier-league/teams/${slugify(p.team_short)}">${esc(p.team)} squad</a> · <a href="/premier-league/players/">All FPL players</a> · <a href="/premier-league/dashboard">FPL dashboard</a></p>`;
    const desc = `${p.full_name || p.web_name} (${p.team}) FPL: £${num(p.price)}, form ${num(p.form)}, ${num(p.points_per_game)} PPG, ${num(p.selected_by_percent)}% owned, next ${p.next_fixture || '—'}. Minutes, xG/xA, fixtures and projections.`;
    writeOut(pub, path.join('premier-league', 'players', slug), page({
      title: `${p.full_name || p.web_name} FPL price, form, fixtures & stats | Fantasy Edge IQ`,
      desc, canonical: SITE + url,
      crumbs: [['Home', '/'], ['FPL players', '/premier-league/players/'], [p.full_name || p.web_name, url]],
      body,
      jsonLd: { '@context': 'https://schema.org', '@type': 'Person', name: p.full_name || p.web_name, description: desc, memberOf: { '@type': 'SportsTeam', name: p.team } }
    }));
    urls.push([url, '0.6', 'weekly']);
  });

  teams.forEach(ts => {
    const slug = slugify(ts);
    const url = `/premier-league/teams/${slug}`;
    const squad = (byTeam[ts] || []).slice().sort((a, b) => (parseFloat(b.total_points) || 0) - (parseFloat(a.total_points) || 0));
    const rows = squad.map(p => `<tr><td><a href="/premier-league/players/${pslug[p.player_id]}">${esc(p.web_name)}</a></td><td>${esc(p.pos)}</td><td>£${num(p.price)}</td><td>${num(p.points_per_game)}</td><td>${num(p.selected_by_percent)}%</td><td>${esc(p.next_fixture || '—')}</td></tr>`).join('');
    const body = `
<h1>${esc(squad[0] ? squad[0].team : ts)} — FPL squad overview</h1>
<p class="sub">All Fantasy Premier League options from ${esc(ts)}, sorted by total points, with prices, ownership and next fixtures.</p>
<div class="box"><table><tr><th>Player</th><th>Pos</th><th>Price</th><th>PPG</th><th>Owned</th><th>Next</th></tr>${rows}</table></div>
<p><a href="/premier-league/players/">All FPL players</a> · <a href="/premier-league/dashboard">FPL dashboard</a></p>`;
    writeOut(pub, path.join('premier-league', 'teams', slug), page({
      title: `${squad[0] ? squad[0].team : ts} FPL players: prices, ownership, fixtures | Fantasy Edge IQ`,
      desc: `Every ${squad[0] ? squad[0].team : ts} Fantasy Premier League option: price, points per game, ownership and next fixture. Updated ${stamp}.`,
      canonical: SITE + url,
      crumbs: [['Home', '/'], ['FPL players', '/premier-league/players/'], [ts, url]], body
    }));
    urls.push([url, '0.7', 'weekly']);
  });

  const rows = P.slice().sort((a, b) => (parseFloat(b.total_points) || 0) - (parseFloat(a.total_points) || 0))
    .map(p => `<tr><td><a href="/premier-league/players/${pslug[p.player_id]}">${esc(p.web_name)}</a></td><td>${esc(p.team_short)}</td><td>${esc(p.pos)}</td><td>£${num(p.price)}</td><td>${num(p.points_per_game)}</td><td>${num(p.selected_by_percent)}%</td></tr>`).join('');
  const body = `
<h1>Fantasy Premier League player profiles</h1>
<p class="sub">${P.length} FPL player profiles: prices, form, ownership, minutes, xG/xA and fixture difficulty for GW planning.</p>
<input class="search" id="q" placeholder="Filter players or clubs..." oninput="const v=this.value.toLowerCase();document.querySelectorAll('#tb tr').forEach(r=>{r.style.display=r.textContent.toLowerCase().includes(v)?'':'none'})">
<div class="box"><table><thead><tr><th>Player</th><th>Club</th><th>Pos</th><th>Price</th><th>PPG</th><th>Owned</th></tr></thead><tbody id="tb">${rows}</tbody></table></div>
<p><a href="/premier-league/dashboard">Open the FPL dashboard</a></p>`;
  writeOut(pub, path.join('premier-league', 'players'), page({
    title: 'FPL player profiles, prices & ownership 2026-27 | Fantasy Edge IQ',
    desc: `Browse ${P.length} Fantasy Premier League player profiles: price, form, PPG, ownership, minutes and next fixtures. Updated ${stamp}.`,
    canonical: SITE + '/premier-league/players/',
    crumbs: [['Home', '/'], ['FPL players', '/premier-league/players/']], body
  }));
  urls.push(['/premier-league/players/', '0.8', 'daily']);
  return P.length + teams.length + 1;
}

// ---------- EuroCup ----------
function buildEuroCup(root, pub, stamp, urls) {
  const P = readCSV(root, 'eurocup-players-full.csv');
  const T = readCSV(root, 'eurocup-team-context.csv');
  if (!P.length) return 0;
  const byTeam = {};
  P.forEach(p => { (byTeam[p.team_abbr] = byTeam[p.team_abbr] || []).push(p); });
  const seen = new Set(); const pslug = {};
  P.forEach(p => { let s = slugify(p.name); if (seen.has(s)) s += '-' + p.player_id; seen.add(s); pslug[p.player_id] = s; });

  P.forEach(p => {
    const slug = pslug[p.player_id];
    const url = `/eurocup/players/${slug}`;
    const body = `
<h1>${esc(p.name)}</h1>
<p class="sub">${esc(p.team_name || p.team_abbr)} · ${esc(p.pos_short || p.position)} · EuroCup Fantasy profile ${bool(p.is_injured) ? '<span class="pill red">Injured</span>' : ''}</p>
<div class="cards">
${card('Price', num(p.price) + ' <span class="mut">cr</span>')}${card('Change', (parseFloat(p.price_change) > 0 ? '+' : '') + num(p.price_change))}
${card('MIN/G', num(p.min_avg_current))}${card('PIR/G', num(p.pir_avg_current))}
${card('PTS/G', num(p.pts_avg_current))}${card('Popularity', pct(p.popularity_pct))}
${card('GP', num(p.gp_current, 0))}${card('Proj PIR', num(p.proj_pir_est))}
</div>
<div class="box"><h2>Schedule & model</h2><p>Next: <b>${esc(p.next_opponent || '—')}</b> (${esc(p.home_away)}) · ${esc((p.next_start_local || '').slice(0, 16))} · FDR ${num(p.next5_fdr_1_easy_5_hard, 2)}</p>
<p class="mut">Next 5: ${esc(p.next5_opponents || '—')}</p>
<p class="mut">Model: projected PIR ${num(p.proj_pir_est)} (role ${esc(p.current_role_projection || '—')}), floor ${num(p.floor_est)} / ceiling ${num(p.ceiling_est)}.</p></div>
<p><a href="/eurocup/players/">All EuroCup players</a> · <a href="/eurocup/dashboard">EuroCup dashboard</a> · <a href="/eurocup/defense-vs-position">EuroCup DvP</a></p>`;
    const desc = `${p.name} (${p.team_abbr}) EuroCup Fantasy: price ${num(p.price)} cr, ${num(p.min_avg_current)} MIN/G, ${num(p.pir_avg_current)} PIR/G, projected PIR ${num(p.proj_pir_est)}, next ${p.next_opponent || '—'}.`;
    writeOut(pub, path.join('eurocup', 'players', slug), page({
      title: `${p.name} — EuroCup Fantasy price & stats | Fantasy Edge IQ`,
      desc, canonical: SITE + url,
      crumbs: [['Home', '/'], ['EuroCup players', '/eurocup/players/'], [p.name, url]],
      body,
      jsonLd: { '@context': 'https://schema.org', '@type': 'Person', name: p.name, description: desc, memberOf: { '@type': 'SportsTeam', name: p.team_name || p.team_abbr } }
    }));
    urls.push([url, '0.6', 'weekly']);
  });

  (T || []).forEach(t => {
    const slug = slugify(t.team_abbr);
    const url = `/eurocup/teams/${slug}`;
    const roster = (byTeam[t.team_abbr] || []).slice().sort((a, b) => (parseFloat(b.pir_avg_current) || 0) - (parseFloat(a.pir_avg_current) || 0)).slice(0, 20);
    const rows = roster.map(p => `<tr><td><a href="/eurocup/players/${pslug[p.player_id]}">${esc(p.name)}</a></td><td>${esc(p.pos_short)}</td><td>${num(p.price)}</td><td>${num(p.min_avg_current)}</td><td>${num(p.pir_avg_current)}</td></tr>`).join('');
    const body = `
<h1>${esc(t.team_name)}</h1>
<p class="sub">EuroCup fantasy team context: scoring volume, defensive environment and fantasy roster.</p>
<div class="cards">
${card('Points/G', num(t.for_points_pg))}${card('Pace', num(t.for_poss_pg))}${card('PIR allowed', num(t.allowed_pir_pg))}${card('FGA allowed', num(t.allowed_fga_pg))}
</div>
<div class="box"><h2>Fantasy options</h2><table><tr><th>Player</th><th>Pos</th><th>Price</th><th>MIN/G</th><th>PIR/G</th></tr>${rows}</table></div>
<p><a href="/eurocup/players/">All players</a> · <a href="/eurocup/dashboard">Dashboard</a></p>`;
    writeOut(pub, path.join('eurocup', 'teams', slug), page({
      title: `${t.team_name} — EuroCup fantasy team context | Fantasy Edge IQ`,
      desc: `${t.team_name}: pace, points and PIR allowed plus every EuroCup Fantasy option with prices and minutes.`,
      canonical: SITE + url,
      crumbs: [['Home', '/'], ['EuroCup players', '/eurocup/players/'], [t.team_name, url]], body
    }));
    urls.push([url, '0.7', 'weekly']);
  });

  const rows = P.slice().sort((a, b) => (parseFloat(b.pir_avg_current) || 0) - (parseFloat(a.pir_avg_current) || 0))
    .map(p => `<tr><td><a href="/eurocup/players/${pslug[p.player_id]}">${esc(p.name)}</a></td><td>${esc(p.team_abbr)}</td><td>${esc(p.pos_short)}</td><td>${num(p.price)}</td><td>${num(p.min_avg_current)}</td><td>${num(p.pir_avg_current)}</td></tr>`).join('');
  const body = `
<h1>EuroCup Fantasy player profiles</h1>
<p class="sub">${P.length} EuroCup Fantasy profiles with official current-season minutes, PIR and projections for 2026-27.</p>
<input class="search" id="q" placeholder="Filter players or clubs..." oninput="const v=this.value.toLowerCase();document.querySelectorAll('#tb tr').forEach(r=>{r.style.display=r.textContent.toLowerCase().includes(v)?'':'none'})">
<div class="box"><table><thead><tr><th>Player</th><th>Club</th><th>Pos</th><th>Price</th><th>MIN/G</th><th>PIR/G</th></tr></thead><tbody id="tb">${rows}</tbody></table></div>
<p><a href="/eurocup/dashboard">Open the EuroCup dashboard</a></p>`;
  writeOut(pub, path.join('eurocup', 'players'), page({
    title: 'EuroCup Fantasy player profiles & prices 2026-27 | Fantasy Edge IQ',
    desc: `Browse ${P.length} EuroCup Fantasy player profiles: prices, minutes, PIR and projections. Updated ${stamp}.`,
    canonical: SITE + '/eurocup/players/',
    crumbs: [['Home', '/'], ['EuroCup players', '/eurocup/players/']], body
  }));
  urls.push(['/eurocup/players/', '0.8', 'daily']);
  return P.length + (T ? T.length : 0) + 1;
}

// ---------- glavni ulaz ----------
function run(root, pub) {
  const stamp = new Date().toISOString().slice(0, 10);
  const urls = [];
  const nEL = buildEuroLeague(root, pub, stamp, urls);
  const nFPL = buildFPL(root, pub, stamp, urls);
  const nEC = buildEuroCup(root, pub, stamp, urls);

  // prosireni sitemap: baza iz root + nove rute
  const base = path.join(root, 'sitemap.xml');
  if (fs.existsSync(base)) {
    let sm = fs.readFileSync(base, 'utf8');
    const add = urls.map(([u, pr, cf]) => `<url><loc>${SITE}${u}</loc><lastmod>${stamp}</lastmod><changefreq>${cf}</changefreq><priority>${pr}</priority></url>`).join('\n');
    sm = sm.replace('</urlset>', add + '</urlset>');
    // dedupe: svaki <loc> se pojavljuje tacno jednom (baza + generisane rute se preklapaju)
    const seenLoc = new Set();
    const entries = sm.match(/<url>[\s\S]*?<\/url>/g) || [];
    const uniq = entries.filter(e => {
      const m = e.match(/<loc>([^<]*)<\/loc>/);
      const u = m ? m[1] : e;
      if (seenLoc.has(u)) return false;
      seenLoc.add(u); return true;
    });
    sm = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + uniq.join('\n') + '\n</urlset>\n';
    fs.writeFileSync(path.join(pub, 'sitemap.xml'), sm, 'utf8');
  }
  console.log(`player pages: EL ${nEL} | FPL ${buildFPLCount(nFPL)} | EC ${nEC} | sitemap +${urls.length} URL`);
  return urls.length;
}
const buildFPLCount = n => n;

module.exports = { run };
