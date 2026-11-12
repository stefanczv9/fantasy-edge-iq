// FAZA 3: automatski "Round X preview" clanak (EN + SR) + social pack (post text + IG story SVG)
// Generise se pri svakom Vercel build-u iz euroleague_fantasy_data/ — bez rucnog rada.
const fs = require('fs');
const path = require('path');
const SITE = 'https://www.fantasyedgeiq.com';

const slugify = s => String(s).toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/g, 'd').replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const num = (v, d = 1) => { const n = parseFloat(v); return isFinite(n) ? n.toFixed(d) : '–'; };

// Slug mapa mora biti IDENTICNA onoj iz build_player_pages.js (dedupe + '-<player_id>' sufiks),
// inace preview linkuje na /players/<ime> koji ne postoji (404).
function playerSlugMap(root, comp) {
  const files = comp === 'eurocup' ? ['eurocup-players-full.csv'] : ['euroleague-players-full.csv', 'euroleague_fantasy_data/fantasheet_style_table.csv'];
  let rows = [];
  for (const f of files) { rows = csv(path.join(root, f)); if (rows.length) break; }
  const seen = new Set(), map = {};
  rows.forEach(p => {
    const name = p.name || p.full_name || '';
    if (!name) return;
    let s = slugify(name);
    if (seen.has(s)) s = s + '-' + (p.player_id || '');
    seen.add(s);
    map[name] = s;
  });
  return { map, fallback: (n) => (map[n] || slugify(n)) };
}

function csv(file) {
  try {
    const lines = fs.readFileSync(file, 'utf8').split(/\r?\n/).filter(l => l.trim());
    if (lines.length < 2) return [];
    const hdr = lines[0].split(',');
    return lines.slice(1).map(l => { const c = l.split(','); const o = {}; hdr.forEach((h, i) => o[h.trim()] = (c[i] || '').trim()); return o; });
  } catch (e) { return []; }
}

function run(root, pub) {
  let N = null;
  try { N = (JSON.parse(fs.readFileSync(path.join(root, 'euroleague_fantasy_data', 'league_config.json'), 'utf8')).current_matchday || {}).number; } catch (e) {}
  if (!N) { console.log('round preview: nema matchday podatka, preskacem'); return null; }
  let P = csv(path.join(root, 'euroleague-players-full.csv'));
  if (!P.length) P = csv(path.join(root, 'euroleague_fantasy_data', 'fantasheet_style_table.csv'));
  let S = csv(path.join(root, 'euroleague-next5-schedule.csv'));
  if (!S.length) S = csv(path.join(root, 'euroleague_fantasy_data', 'team_next5_schedule_detail.csv'));
  if (S.length && S[0].matchday) { const mds = S.map(r => parseInt(r.matchday, 10)).filter(v => isFinite(v)); if (mds.length) N = Math.min(...mds); }
  if (!P.length) { console.log('round preview: nema tabele, preskacem'); return null; }
  const pSlug = playerSlugMap(root, 'euroleague').fallback;   // isti slugovi kao /euroleague/players/*
  const fdrCol = (Object.keys(S[0] || {}).find(k => k.startsWith('fdr')) || 'fdr_');
  // FDR po timu: naredci mec (matchday >= N) + FDR sledeceg meca
  const teamFdr = {}, teamNext = {};
  for (const r of S) {
    const md = parseInt(r.matchday, 10);
    if (!isFinite(md)) continue;
    if (md === N) teamNext[r.team_abbr] = { opp: r.opponent || r.opponent_abbr, fdr: parseFloat(r[fdrCol]), ha: r.home_away, when: r.start_local };
    if (md >= N && md < N + 5) { (teamFdr[r.team_abbr] = teamFdr[r.team_abbr] || []).push(parseFloat(r[fdrCol])); }
  }
  const fdr5 = t => { const a = teamFdr[t] || []; return a.length ? a.reduce((x, y) => x + y, 0) / a.length : null; };
  const ok = p => p && !/^(true|1)$/i.test(p.is_injured || '') && parseFloat(p.min_avg_current || 0) > 0 && parseFloat(p.price || 0) > 0;
  const rows = P.filter(ok).map(p => ({
    name: p.name, team: p.team_abbr, price: parseFloat(p.price), proj: parseFloat(p.proj_pir_est), val: parseFloat(p.value_pir_per_credit),
    pop: parseFloat(p.popularity_pct || 0), min: parseFloat(p.min_avg_current || 0), pir: parseFloat(p.pir_avg_current || 0),
    next: (teamNext[p.team_abbr] || {}).opp || p.next_opponent || '–', nfdr: (teamNext[p.team_abbr] || {}).fdr, f5: fdr5(p.team_abbr)
  })).filter(r => isFinite(r.proj) && isFinite(r.val));
  if (!rows.length) return null;
  const picks = [...rows].sort((a, b) => b.val - a.val).slice(0, 5);
  const starts = [...rows].sort((a, b) => b.proj - a.proj).slice(0, 3);
  const medVal = [...rows].map(r => r.val).sort((a, b) => a - b)[Math.floor(rows.length / 2)];
  const traps = rows.filter(r => r.pop >= 10 && r.val < medVal).sort((a, b) => b.pop - a.pop).slice(0, 2);
  const stamp = new Date().toISOString().slice(0, 10);
  const url = `/euroleague/round-${N}-preview`;
  const fdrChip = f => f == null || !isFinite(f) ? '' : `<span style="background:${f < 2.5 ? '#14532d' : f < 3.5 ? '#854d0e' : '#7f1d1d'};color:#fff;border-radius:6px;padding:2px 8px;font-size:11.5px;font-weight:700">FDR ${num(f, 1)}</span>`;

  const T = {
    '': { title: `Round ${N} preview: value picks, must-starts and traps`, h1: `Round ${N} preview`, sub: 'value picks · must-starts · traps · next-5 FDR',
      intro: `Auto-generated from the latest EuroLeague Fantasy data (${stamp}): projections, minutes, price and next-five fixture difficulty for every tracked player. Round ${N} locks are listed on the dashboard banner.`,
      hp: 'Value picks (PIR per credit)', hs: 'Must-starts (projected PIR)', ht: 'Traps (popular but overpriced)', hn: 'Next opponent & FDR',
      c1: 'Player', c2: 'Team', c3: 'Price', c4: 'Proj PIR', c5: 'Value', c6: 'Next (FDR)',
      noteP: 'Value = projected PIR divided by price. Minimum minutes filter applied; injured players excluded.',
      noteT: 'High ownership + below-median value = the rounds where differential picks win.',
      pack: 'Social pack (copy-paste ready)', packP: 'Post texts and an IG story graphic for this round, generated with the article:',
      rel: 'Related', relL: ['Player profiles', 'Advanced dashboard', 'Defense vs Position', 'Lineup IQ'] },
    sr: { title: `Kolo ${N}: vrijednosni pickovi, obavezni startovi i zamke`, h1: `Kolo ${N} — preview`, sub: 'vrijednosni pickovi · obavezni startovi · zamke · FDR narednih 5',
      intro: `Automatski generisano iz najsvježijih EuroLeague Fantasy podataka (${stamp}): projekcije, minute, cijena i težina rasporeda u narednih 5 kola za svakog praćenog igrača. Zaključavanje postave za kolo ${N} prikazuje baner na dashboard-u.`,
      hp: 'Vrijednosni pickovi (PIR po kreditu)', hs: 'Obavezni startovi (projekcija PIR)', ht: 'Zamke (popularni a preskupi)', hn: 'Sljedeći protivnik i FDR',
      c1: 'Igrač', c2: 'Tim', c3: 'Cijena', c4: 'Proj PIR', c5: 'Value', c6: 'Sljedeći (FDR)',
      noteP: 'Value = projekcija PIR podijeljena sa cijenom. Filter minimalnih minuta; povrijeđeni isključeni.',
      noteT: 'Velika popularnost + value ispod medijane = kola u kojima diferencijalni pickovi donose prednost.',
      pack: 'Social paket (spreman za copy-paste)', packP: 'Tekstovi za objavu i IG story grafika za ovo kolo, generisani uz članak:',
      rel: 'Vezano', relL: ['Profili igrača', 'Napredni dashboard', 'Odbrana po pozicijama', 'Lineup IQ'] }
  };
  const relH = { '': ['/euroleague/players/', '/euroleague/dashboard', '/euroleague/defense-vs-position', '/euroleague/team-analyzer'], sr: ['/euroleague/players/', '/sr/euroleague/dashboard', '/sr/euroleague/defense-vs-position', '/sr/euroleague/team-analyzer'] };

  const table = (list, lang) => { const t = T[lang]; return `<table style="width:100%;border-collapse:collapse;font-size:14px;margin:10px 0 6px"><tr>${[t.c1, t.c2, t.c3, t.c4, t.c5, t.c6].map((h, i) => `<th style="text-align:${i > 1 && i < 5 ? 'right' : 'left'};color:#7dd3fc;font-size:11px;letter-spacing:.05em;text-transform:uppercase;padding:9px 10px;border-bottom:1px solid rgba(148,163,184,.25)">${h}</th>`).join('')}</tr>` + list.map(r => `<tr><td style="padding:9px 10px;border-bottom:1px solid rgba(148,163,184,.12)"><a href="/euroleague/players/${pSlug(r.name)}" style="color:#e2e8f0;text-decoration:none;font-weight:600">${esc(r.name)}</a></td><td style="padding:9px 10px;border-bottom:1px solid rgba(148,163,184,.12);color:#94a3b8">${esc(r.team)}</td><td style="padding:9px 10px;border-bottom:1px solid rgba(148,163,184,.12);text-align:right;color:#dbe4ee">${num(r.price)}</td><td style="padding:9px 10px;border-bottom:1px solid rgba(148,163,184,.12);text-align:right;color:#dbe4ee">${num(r.proj)}</td><td style="padding:9px 10px;border-bottom:1px solid rgba(148,163,184,.12);text-align:right;color:#4ade80;font-weight:700">${num(r.val, 2)}</td><td style="padding:9px 10px;border-bottom:1px solid rgba(148,163,184,.12);color:#94a3b8">${esc(r.next)} ${fdrChip(r.nfdr)}</td></tr>`).join('') + '</table>'; };

  const page = lang => { const t = T[lang]; const pfx = lang ? '/' + lang : '';
    const body = `<div style="max-width:860px;margin:0 auto;padding:26px 20px 60px">
<p style="font-size:12.5px;color:#64748b"><a href="${pfx}/" style="color:#7dd3fc;text-decoration:none">Home</a> / <a href="${pfx}/euroleague" style="color:#7dd3fc;text-decoration:none">EuroLeague Fantasy</a> / Round ${N} preview</p>
<h1 style="font-size:32px;margin:10px 0 6px;color:#f8fafc">${t.h1}</h1>
<p style="color:#7dd3fc;font-size:13px;margin:0 0 14px">${t.sub} · ${stamp}</p>
<p style="color:#94a3b8;line-height:1.7;font-size:14.5px">${t.intro}</p>
<h2 style="font-size:20px;color:#f1f5f9;margin:26px 0 4px">1) ${t.hp}</h2><p style="color:#64748b;font-size:12.5px;margin:0 0 6px">${t.noteP}</p>${table(picks, lang)}
<h2 style="font-size:20px;color:#f1f5f9;margin:26px 0 4px">2) ${t.hs}</h2>${table(starts, lang)}
<h2 style="font-size:20px;color:#f1f5f9;margin:26px 0 4px">3) ${t.ht}</h2><p style="color:#64748b;font-size:12.5px;margin:0 0 6px">${t.noteT}</p>${traps.length ? table(traps, lang) : '<p style="color:#64748b;font-size:13.5px">—</p>'}
<h2 style="font-size:20px;color:#f1f5f9;margin:26px 0 4px">4) ${t.hn}</h2><table style="width:100%;border-collapse:collapse;font-size:14px;margin:10px 0 6px"><tr><th style="text-align:left;color:#7dd3fc;font-size:11px;letter-spacing:.05em;text-transform:uppercase;padding:9px 10px;border-bottom:1px solid rgba(148,163,184,.25)">${t.c1}</th><th style="text-align:left;color:#7dd3fc;font-size:11px;text-transform:uppercase;padding:9px 10px;border-bottom:1px solid rgba(148,163,184,.25)">${t.c2}</th><th style="text-align:left;color:#7dd3fc;font-size:11px;text-transform:uppercase;padding:9px 10px;border-bottom:1px solid rgba(148,163,184,.25)">${t.c6}</th><th style="text-align:right;color:#7dd3fc;font-size:11px;text-transform:uppercase;padding:9px 10px;border-bottom:1px solid rgba(148,163,184,.25)">FDR next 5</th></tr>${picks.map(r => `<tr><td style="padding:9px 10px;border-bottom:1px solid rgba(148,163,184,.12)"><a href="/euroleague/players/${pSlug(r.name)}" style="color:#e2e8f0;text-decoration:none;font-weight:600">${esc(r.name)}</a></td><td style="padding:9px 10px;border-bottom:1px solid rgba(148,163,184,.12);color:#94a3b8">${esc(r.team)}</td><td style="padding:9px 10px;border-bottom:1px solid rgba(148,163,184,.12);color:#94a3b8">${esc(r.next)} ${fdrChip(r.nfdr)}</td><td style="padding:9px 10px;border-bottom:1px solid rgba(148,163,184,.12);text-align:right;color:#dbe4ee;font-weight:700">${r.f5 == null ? '–' : num(r.f5, 1)}</td></tr>`).join('')}</table>
<p style="color:#64748b;font-size:12.5px;margin:6px 0 0">${lang === 'sr' ? 'FDR next 5 = prosjek težine narednih 5 utakmica tima (niže = lakše).' : 'FDR next 5 = average difficulty of the team next five games (lower = easier).'}</p>
<h2 style="font-size:20px;color:#f1f5f9;margin:30px 0 4px">📣 ${t.pack}</h2><p style="color:#94a3b8;font-size:13.5px;margin:0 0 10px">${t.packP}</p>
${copyBox('post-en.txt', post(''))}${copyBox('post-sr.txt', post('sr'))}<div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center"><a href="/social/md${N}-preview/story.svg" style="border:1px solid rgba(125,211,252,.4);color:#7dd3fc;padding:7px 14px;border-radius:999px;font-size:13px;text-decoration:none;font-weight:600">⬇ story.svg (IG 1080×1920)</a><span style="color:#64748b;font-size:12px">tekstovi ostaju i kao fajlovi: /social/md${N}-preview/post-en.txt · post-sr.txt</span></div>
<h2 style="font-size:18px;color:#f1f5f9;margin:30px 0 8px">${t.rel}</h2><div style="display:flex;gap:10px;flex-wrap:wrap">${t.relL.map((l, i) => `<a href="${relH[lang][i]}" style="border:1px solid rgba(148,163,184,.35);color:#cbd5e1;padding:7px 14px;border-radius:999px;font-size:13px;text-decoration:none">${l}</a>`).join('')}</div>
</div>`;
    return `<!doctype html><html lang="${lang || 'en'}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>${esc(t.title)} | Fantasy Edge IQ</title><meta name="description" content="${esc(t.intro.slice(0, 150))}">
<link rel="canonical" href="${SITE}${pfx}${url}"><meta name="robots" content="index,follow">
<meta property="og:type" content="article"><meta property="og:title" content="${esc(t.title)}"><meta property="og:url" content="${SITE}${pfx}${url}"><meta property="og:site_name" content="Fantasy Edge IQ">
<script type="application/ld+json">${JSON.stringify({ '@context': 'https://schema.org', '@type': 'Article', headline: t.title, datePublished: stamp, publisher: { '@type': 'Organization', name: 'Fantasy Edge IQ' }, mainEntityOfPage: SITE + pfx + url })}</script>
<style>body{margin:0;background:#0b1220;color:#e2e8f0;font-family:-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}a:hover{text-decoration:underline!important}</style>
</head><body>${body}</body></html>`; };

  const post = lang => { const lines = [];
    lines.push(lang ? `EL Fantasy MD${N} — vrijednosna tabla 🏀` : `MD${N} value board 🏀 (EuroLeague Fantasy)`);
    picks.slice(0, 3).forEach((r, i) => lines.push(`${i + 1}) ${r.name} ${r.team} ${num(r.price)} → proj ${num(r.proj)} PIR (value ${num(r.val, 2)})`));
    lines.push(lang ? `Kompletan preview + FDR narednih 5: ${SITE}/sr${url}` : `Full preview + next-5 FDR: ${SITE}${url}`);
    lines.push(lang ? '#EuroLeague #EuroLeagueFantasy #fantasy' : '#EuroLeague #EuroLeagueFantasy #fantasy');
    return lines.join('\n') + '\n'; };
  const copyBox = (label, txt) => `<div style="margin:10px 0 18px"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px"><strong style="color:#bbf7d0;font-size:13px">${label}</strong><button onclick="navigator.clipboard.writeText(this.parentNode.nextElementSibling.innerText);this.textContent='\u2713 kopirano';setTimeout(()=>this.textContent='Kopiraj / Copy',1600)" style="background:#22d3ee;color:#083344;border:0;border-radius:999px;padding:6px 14px;font-weight:800;cursor:pointer;font-size:12px">Kopiraj / Copy</button></div><pre style="margin:0;background:#0d1526;border:1px solid rgba(148,163,184,.25);border-radius:12px;padding:14px 16px;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12.5px;color:#a5f3fc;white-space:pre-wrap;line-height:1.55">${esc(txt)}</pre></div>`;
  const write = (rel, content) => { const d = path.join(pub, rel); fs.mkdirSync(d, { recursive: true }); fs.writeFileSync(path.join(d, 'index.html'), content); };
  write(url.slice(1), page(''));
  write('sr' + url, page('sr'));
  // social pack
  const sp = path.join(pub, 'social', `md${N}-preview`);
  fs.mkdirSync(sp, { recursive: true });
  fs.writeFileSync(path.join(sp, 'post-en.txt'), post(''));
  fs.writeFileSync(path.join(sp, 'post-sr.txt'), post('sr'));
  const tp = picks[0];
  fs.writeFileSync(path.join(sp, 'story.svg'), `<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#0ea5e9"/><stop offset=".6" stop-color="#7c3aed"/><stop offset="1" stop-color="#db2777"/></linearGradient></defs><rect width="1080" height="1920" fill="url(#g)"/><text x="80" y="260" fill="#fff" font-family="Arial" font-size="44" font-weight="700" letter-spacing="6">FANTASY EDGE IQ · MD${N}</text><text x="80" y="820" fill="#fff" font-family="Arial" font-size="110" font-weight="900">${esc(tp.name.toUpperCase())}</text><text x="80" y="960" fill="#e0f2fe" font-family="Arial" font-size="64" font-weight="700">proj. ${num(tp.proj)} PIR</text><text x="80" y="1060" fill="#e0f2fe" font-family="Arial" font-size="48">value ${num(tp.val, 2)} · next: ${esc(tp.next)}${isFinite(tp.nfdr) ? ' (FDR ' + num(tp.nfdr, 1) + ')' : ''}</text><text x="80" y="1700" fill="#f0f9ff" font-family="Arial" font-size="40">fantasyedgeiq.com/euroleague/round-${N}-preview</text></svg>`);
  // sitemap dodaci
  try {
    const sm = path.join(pub, 'sitemap.xml');
    if (fs.existsSync(sm)) {
      let x = fs.readFileSync(sm, 'utf8');
      const add = [`<url><loc>${SITE}${url}</loc><lastmod>${stamp}</lastmod><changefreq>weekly</changefreq><priority>0.9</priority></url>`, `<url><loc>${SITE}/sr${url}</loc><lastmod>${stamp}</lastmod><changefreq>weekly</changefreq><priority>0.8</priority></url>`].join('\n');
      if (!x.includes(`${url}</loc>`)) x = x.replace('</urlset>', add + '\n</urlset>');
      fs.writeFileSync(sm, x);
    }
  } catch (e) {}
  console.log(`round preview: MD${N} | picks ${picks.length} | starts ${starts.length} | traps ${traps.length} | social pack OK`);
  return N;
}
module.exports = { run };
