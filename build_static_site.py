import json
import html
import math
from pathlib import Path
from datetime import datetime

import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT
FLAT = ROOT
EURO_DATA = ROOT / 'euroleague_fantasy_data'
FPL_DATA = ROOT / 'fpl_fantasy_data'
TODAY = '2026-09-25'
SITE = 'https://www.fantasyedgeiq.com'

OUT.mkdir(exist_ok=True)


def clean_records(df: pd.DataFrame):
    def conv(v):
        try:
            if pd.isna(v):
                return None
        except Exception:
            pass
        if isinstance(v, (np.integer,)):
            return int(v)
        if isinstance(v, (np.floating, float)):
            if math.isnan(float(v)) or math.isinf(float(v)):
                return None
            return round(float(v), 4)
        if isinstance(v, (np.bool_, bool)):
            return bool(v)
        return v
    return [{k: conv(v) for k, v in row.items()} for row in df.to_dict(orient='records')]


def json_dumps(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def copy_if_exists(src, dst=None):
    src = Path(src)
    if dst is None:
        dst = OUT / src.name
    else:
        dst = OUT / dst
    if src.exists():
        dst.write_bytes(src.read_bytes())


def make_homepage():
    html_doc = f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Fantasy Edge IQ — EuroLeague Fantasy & FPL Analytics</title>
  <meta name="description" content="Fantasy Edge IQ is a free beta fantasy analytics platform for EuroLeague Fantasy and Fantasy Premier League managers. Compare player value, minutes, fixture difficulty, injuries, price changes, usage, pace and matchup context before every deadline.">
  <meta name="robots" content="index,follow,max-snippet:-1,max-image-preview:large,max-video-preview:-1">
  <link rel="canonical" href="{SITE}/">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="Fantasy Edge IQ">
  <meta property="og:title" content="Fantasy Edge IQ — EuroLeague Fantasy & FPL Analytics">
  <meta property="og:description" content="Free beta fantasy dashboards for EuroLeague Fantasy and Fantasy Premier League: player value, fixture runs, injuries, price changes, pace, usage and matchup context.">
  <meta property="og:url" content="{SITE}/">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="Fantasy Edge IQ — EuroLeague Fantasy & FPL Analytics">
  <meta name="twitter:description" content="Free beta fantasy analytics for EuroLeague Fantasy and FPL managers before every lock.">
  <script type="application/ld+json">{{"@context":"https://schema.org","@type":"WebSite","name":"Fantasy Edge IQ","url":"{SITE}/","description":"Fantasy analytics platform for EuroLeague Fantasy and Fantasy Premier League managers.","potentialAction":{{"@type":"SearchAction","target":"{SITE}/euroleague?search={{search_term_string}}","query-input":"required name=search_term_string"}}}}</script>
  <script type="application/ld+json">{{"@context":"https://schema.org","@type":"SoftwareApplication","name":"Fantasy Edge IQ","applicationCategory":"SportsApplication","operatingSystem":"Web","url":"{SITE}/","offers":{{"@type":"Offer","price":"0","priceCurrency":"EUR"}},"description":"Free beta fantasy analytics dashboards for EuroLeague Fantasy and Fantasy Premier League."}}</script>
  <style>
    :root{{--bg:#07101d;--bg2:#0d1b2f;--card:#111f34;--card2:#162b49;--txt:#eef6ff;--mut:#9fb1c9;--line:rgba(255,255,255,.11);--blue:#5bbcff;--green:#22c55e;--yellow:#ffd166;--red:#fb7185}}
    *{{box-sizing:border-box}} body{{margin:0;background:radial-gradient(circle at 18% 0%,#1c4f7d 0,#0b1a2e 36%,#07101d 72%);color:var(--txt);font-family:Inter,system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;line-height:1.55}} a{{color:inherit;text-decoration:none}} .wrap{{max-width:1180px;margin:0 auto;padding:0 22px}} .nav{{display:flex;justify-content:space-between;align-items:center;padding:20px 0;gap:18px}} .logo{{font-weight:950;font-size:23px;letter-spacing:-.04em}} .logo span{{color:var(--blue)}} .links{{display:flex;gap:18px;align-items:center;color:var(--mut);font-size:14px}} .links a:hover{{color:#fff}} .btn{{display:inline-flex;align-items:center;gap:8px;background:linear-gradient(135deg,#58c2ff,#22c55e);color:#06111f;font-weight:850;border-radius:14px;padding:12px 16px;border:0;box-shadow:0 12px 35px rgba(34,197,94,.14)}} .ghost{{border:1px solid var(--line);background:rgba(255,255,255,.045);color:var(--txt);box-shadow:none}} .hero{{padding:74px 0 48px}} .badge{{display:inline-flex;gap:8px;align-items:center;border:1px solid rgba(91,188,255,.35);background:rgba(91,188,255,.11);border-radius:999px;padding:7px 12px;color:#d8f1ff;font-size:13px;font-weight:800}} h1{{font-size:clamp(40px,6.2vw,76px);line-height:.96;margin:18px 0 18px;letter-spacing:-.065em;max-width:980px}} .lead{{font-size:20px;color:var(--mut);max-width:820px}} .cta{{display:flex;gap:12px;flex-wrap:wrap;margin-top:28px}} .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:16px;margin:28px 0}} .card{{background:linear-gradient(180deg,rgba(17,31,52,.92),rgba(12,24,42,.92));border:1px solid var(--line);border-radius:24px;padding:25px;box-shadow:0 24px 80px rgba(0,0,0,.24)}} .card h2{{margin:0 0 10px;font-size:27px;letter-spacing:-.035em}} .card p,.mut{{color:var(--mut)}} .features{{display:grid;gap:10px;margin:18px 0}} .features div{{display:flex;gap:9px;color:#e4f0ff}} .check{{color:var(--green);font-weight:950}} .section{{padding:38px 0}} .section h2{{font-size:36px;letter-spacing:-.045em;margin:0 0 10px}} .metrics{{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px;margin-top:16px}} .metric{{padding:18px;border-radius:18px;background:rgba(255,255,255,.05);border:1px solid var(--line)}} .metric b{{display:block;font-size:29px;letter-spacing:-.04em}} .steps{{counter-reset:s;display:grid;gap:12px}} .step{{display:flex;gap:14px;align-items:flex-start;background:rgba(255,255,255,.04);border:1px solid var(--line);border-radius:18px;padding:16px}} .step:before{{counter-increment:s;content:counter(s);display:grid;place-items:center;min-width:32px;height:32px;border-radius:50%;background:rgba(91,188,255,.16);color:#9adeff;font-weight:900}} .faq{{display:grid;gap:12px}} details{{background:rgba(255,255,255,.045);border:1px solid var(--line);border-radius:18px;padding:16px}} summary{{cursor:pointer;font-weight:850}} .footer{{border-top:1px solid var(--line);padding:28px 0;color:var(--mut);font-size:13px;margin-top:40px}} @media(max-width:760px){{.links{{display:none}}.hero{{padding-top:38px}}}}
  </style>
</head>
<body>
  <div class="wrap">
    <nav class="nav" aria-label="Main navigation">
      <a class="logo" href="/">Fantasy Edge <span>IQ</span></a>
      <div class="links">
        <a href="/euroleague">EuroLeague Fantasy</a>
        <a href="/premier-league">FPL</a>
        <a href="/pricing">Pricing</a>
        <a href="/methodology">Methodology</a>
      </div>
    </nav>

    <main>
      <section class="hero">
        <div class="badge">Free beta · EuroLeague Fantasy + Fantasy Premier League</div>
        <h1>Fantasy analytics that help you decide before every lock.</h1>
        <p class="lead">Fantasy Edge IQ turns public fantasy data into practical decision tools: player value, minutes, usage, fixture difficulty, injuries, price changes, team pace and matchup context for EuroLeague Fantasy and FPL managers.</p>
        <div class="cta">
          <a class="btn" href="/euroleague">Open EuroLeague dashboard</a>
          <a class="btn ghost" href="/premier-league">Open FPL dashboard</a>
        </div>
      </section>

      <section class="grid" aria-label="Fantasy tools">
        <article class="card">
          <h2>EuroLeague Fantasy tools</h2>
          <p>Find players with strong value, stable minutes, favorable next-five schedules, high shot volume and positive team environments.</p>
          <div class="features">
            <div><span class="check">✓</span> Next 5 fixture difficulty and matchup ease</div>
            <div><span class="check">✓</span> Team pace, FGA, rebounds allowed and PIR allowed</div>
            <div><span class="check">✓</span> Full player table with prices, minutes, PIR, shooting, rebounds, assists and model components</div>
            <div><span class="check">✓</span> Player option score for short-term decisions</div>
          </div>
          <div class="cta" style="margin-top:18px"><a class="btn" href="/euroleague/dashboard">Launch EuroLeague</a><a class="btn ghost" href="/euroleague/team-analyzer">Lineup IQ</a></div>
        </article>
        <article class="card">
          <h2>Fantasy Premier League tools</h2>
          <p>Track players, fixtures, injuries, ownership, transfers, price movement, recent form and expected points in one free beta dashboard.</p>
          <div class="features">
            <div><span class="check">✓</span> FPL player rankings and value metrics</div>
            <div><span class="check">✓</span> Price changes, transfers in/out and ownership</div>
            <div><span class="check">✓</span> Injury and news status</div>
            <div><span class="check">✓</span> Upcoming fixtures and next opponents</div>
          </div>
          <a class="btn" href="/premier-league/dashboard">Launch FPL</a>
        </article>
      </section>

      <section class="section">
        <h2>What Fantasy Edge IQ tracks</h2>
        <p class="mut">The goal is not to replace your judgment. The goal is to give you faster context before deadlines, transfers and captaincy decisions.</p>
        <div class="metrics">
          <div class="metric"><b>365+</b><span class="mut">EuroLeague fantasy player profiles monitored</span></div>
          <div class="metric"><b>650+</b><span class="mut">FPL players and public fixture data</span></div>
          <div class="metric"><b>Next 5</b><span class="mut">fixture run and matchup difficulty focus</span></div>
          <div class="metric"><b>Free</b><span class="mut">during beta while models improve</span></div>
        </div>
      </section>

      <section class="section">
        <h2>How to use it</h2>
        <div class="steps">
          <div class="step"><div><strong>Start with value and minutes.</strong><br><span class="mut">Filter by team or position and identify players with strong production per price and reliable playing time.</span></div></div>
          <div class="step"><div><strong>Check schedule context.</strong><br><span class="mut">Use next-five difficulty, opponent pace and defensive environment to avoid buying into a bad fixture run.</span></div></div>
          <div class="step"><div><strong>Confirm risk.</strong><br><span class="mut">Look at injury flags, bench indicators, price movement, popularity and form before making the transfer.</span></div></div>
        </div>
      </section>

      <section class="section faq">
        <h2>FAQ</h2>
        <details open><summary>Is Fantasy Edge IQ free?</summary><p class="mut">Yes. The platform is in free beta this season. A Pro version with watchlists, alerts and lineup tools may come later.</p></details>
        <details><summary>Is this affiliated with EuroLeague, Premier League or FPL?</summary><p class="mut">No. Fantasy Edge IQ is an independent analytics project and is not affiliated with Euroleague Basketball, the Premier League or Fantasy Premier League.</p></details>
        <details><summary>Does the dashboard give guaranteed picks?</summary><p class="mut">No model can guarantee fantasy outcomes. The dashboards provide context, rankings and risk indicators so managers can make better decisions.</p></details>
      </section>
    </main>

    <footer class="footer">
      <div>Fantasy Edge IQ is an independent fantasy analytics project. It is not affiliated with Euroleague Basketball, Premier League or Fantasy Premier League.</div>
      <div style="margin-top:8px"><a href="/about">About</a> · <a href="/methodology">Methodology</a> · <a href="/pricing">Pricing</a> · <a href="/disclaimer">Disclaimer</a> · <a href="/privacy">Privacy</a> · <a href="/terms">Terms</a></div>
    </footer>
  </div>
</body>
</html>
'''
    (OUT / 'index.html').write_text(html_doc, encoding='utf-8')


def euro_label(c):
    labels = {
        'name':'Player','team_abbr':'Team','pos_short':'Pos','price':'Price','price_base':'Base price','price_change':'Price Δ',
        'proj_pir_est':'Proj PIR','form_pir':'Form PIR','value_pir_per_credit':'PIR / Cr','fantasy_pts_current_md':'Fantasy pts','value_fantasy_per_credit':'Fantasy / Cr',
        'gp_current':'GP current','min_avg_best':'MIN avg','min_avg_source':'MIN source','min_avg_current':'MIN current','pts_avg_current':'PTS current','pir_avg_current':'PIR current','pir_25_26':'PIR 25-26','min_avg_25_26':'MIN 25-26',
        'floor_est':'Floor','ceiling_est':'Ceiling','price_gap_est':'Price gap','fg_made_pg_best':'FGM/G','fg_attempts_pg_best':'FGA/G','fg_pct_best':'FG%','fg_attempts_per_min_best':'FGA/min','fg_attempts_per40_best':'FGA/40','shooting_source':'Shot source',
        'fg_made_pg_current':'FGM/G current','fg_attempts_pg_current':'FGA/G current','fg_pct_current':'FG% current','fg_attempts_per_min_current':'FGA/min current','fg_attempts_per40_current':'FGA/40 current',
        '2p_current':'2P','2p_pct_current':'2P%','3p_current':'3P','3p_pct_current':'3P%','ft_current':'FT','ft_pct_current':'FT%','two_pa_per_min_best':'2PA/min','three_pa_per_min_best':'3PA/min','fta_per_min_best':'FTA/min',
        'reb_avg_current':'REB','oreb_avg_current':'OREB','dreb_avg_current':'DREB','pf_avg_current':'PF','fd_avg_current':'FD','stl_avg_current':'STL','tov_avg_current':'TOV','ast_avg_current':'AST','blk_avg_current':'BLK','blka_avg_current':'BLKA',
        'next_opponent':'Next opp','next_start_local':'Next tip','match_status':'Match status','opponent_abbr':'Opp','home_away':'H/A','is_injured':'Injured','started_from_bench':'Bench','popularity_pct':'Popularity %','player_id':'Player ID',
        'team_pace_possessions_pg':'Team pace','team_fga_for_pg':'Team FGA','team_fga_allowed_pg':'Team FGA allowed','team_oreb_allowed_pg':'OREB allowed','team_dreb_allowed_pg':'DREB allowed','team_pir_allowed_pg':'PIR allowed','team_defense_weakness_score':'Weakness+',
        'next5_count':'Next5 games','next5_opponents':'Next5 opps','next5_ease_score':'Next5 ease','next5_fdr_1_easy_5_hard':'Next5 FDR','proj_score_component':'Proj comp','value_score_component':'Value comp','minutes_score_component':'Minutes comp','usage_score_component':'Usage comp','price_gap_score_component':'Gap comp','form_score_component':'Form comp','schedule_score_component':'Schedule comp','option_score_next5':'Option score','next_period_rating':'Rating'
    }
    return labels.get(c, c.replace('_',' ').title())


def make_euro_team_analyzer():
    players = pd.read_csv(EURO_DATA / 'fantasheet_style_table_context.csv')
    cols = ['name','team_abbr','pos_short','price','option_score_next5','next_period_rating','next5_fdr_1_easy_5_hard','next5_opponents','proj_pir_est','form_pir','value_pir_per_credit','min_avg_best','fg_attempts_pg_best','fg_attempts_per_min_best','pir_avg_current','pir_25_26','is_injured','started_from_bench','popularity_pct','player_id']
    players = players[[c for c in cols if c in players.columns]].copy()
    if 'option_score_next5' in players.columns:
        players = players.sort_values(['option_score_next5','proj_pir_est'], ascending=[False, False], na_position='last')
    generated = datetime.now().strftime('%Y-%m-%d %H:%M CET')
    data = {'generated': generated, 'players': clean_records(players)}
    html_doc = f'''<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>EuroLeague Lineup IQ — Fantasy Edge IQ</title>
<meta name="description" content="EuroLeague Fantasy transfer analyzer. Select your current squad and get simple sell candidates, replacement options and captain shortlist based on next-five schedule, minutes, value and option score.">
<link rel="canonical" href="{SITE}/euroleague/team-analyzer"><meta name="robots" content="index,follow">
<style>
:root{{--bg:#07101d;--panel:#0f2139;--panel2:#132b4a;--line:rgba(255,255,255,.11);--txt:#eef6ff;--mut:#a9bad2;--blue:#5bbcff;--green:#22c55e;--yellow:#ffd166;--red:#fb7185}}*{{box-sizing:border-box}}body{{margin:0;background:linear-gradient(135deg,#07101d,#0f2946 60%,#07101d);color:var(--txt);font-family:Inter,system-ui,Segoe UI,Arial,sans-serif;font-size:14px}}a{{color:#8ed6ff;text-decoration:none}}header{{padding:24px 24px 18px;border-bottom:1px solid var(--line);background:rgba(7,16,29,.86);position:sticky;top:0;z-index:5;backdrop-filter:blur(8px)}}.nav{{display:flex;justify-content:space-between;gap:14px;align-items:center;margin-bottom:18px}}.brand{{font-weight:950;font-size:19px}}.brand span{{color:var(--blue)}}.links{{display:flex;gap:14px;color:var(--mut);font-size:13px}}h1{{margin:0 0 8px;font-size:clamp(28px,4vw,46px);letter-spacing:-.05em}}.sub{{color:var(--mut);font-size:16px;max-width:980px;line-height:1.45}}main{{padding:22px 24px 60px;max-width:1350px;margin:0 auto}}.layout{{display:grid;grid-template-columns:minmax(320px,1fr) minmax(360px,520px);gap:16px;align-items:start}}.box{{background:rgba(15,33,57,.88);border:1px solid var(--line);border-radius:18px;padding:16px;box-shadow:0 18px 60px rgba(0,0,0,.22)}}.box h2,.box h3{{margin:0 0 10px}}.mut{{color:var(--mut)}}.toolbar{{display:flex;gap:10px;flex-wrap:wrap;margin:12px 0}}input,select{{background:#0a192c;border:1px solid rgba(255,255,255,.13);color:var(--txt);border-radius:12px;padding:10px 12px}}button,.btn{{background:#14345a;color:#fff;border:1px solid rgba(91,188,255,.28);border-radius:12px;padding:9px 12px;font-weight:850;cursor:pointer}}button:hover,.btn:hover{{border-color:#7bd3ff}}.primary{{background:linear-gradient(135deg,#1588d2,#22c55e);color:#06111f;border:0}}.danger{{background:#3a1825;border-color:rgba(251,113,133,.35)}}.tablewrap{{overflow:auto;max-height:62vh;border:1px solid var(--line);border-radius:14px;background:#0a192c}}table{{border-collapse:collapse;width:100%;font-size:12px}}th,td{{padding:8px 9px;border-bottom:1px solid rgba(255,255,255,.08);white-space:nowrap;text-align:left}}th{{position:sticky;top:0;background:#193b63;z-index:2}}tr:hover td{{background:rgba(91,188,255,.08)}}.cards{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin:12px 0}}.metric{{background:rgba(255,255,255,.045);border:1px solid var(--line);border-radius:14px;padding:12px}}.metric b{{display:block;font-size:24px}}.squad{{display:grid;gap:8px;max-height:360px;overflow:auto;padding-right:4px}}.chip{{display:flex;justify-content:space-between;gap:12px;align-items:center;background:#0a192c;border:1px solid var(--line);border-radius:14px;padding:9px 10px}}.chip small{{color:var(--mut)}}.good{{color:#86efac;font-weight:900}}.warn{{color:#fde68a;font-weight:900}}.bad{{color:#fda4af;font-weight:900}}.ideas{{display:grid;gap:10px}}.idea{{background:#0a192c;border:1px solid var(--line);border-radius:14px;padding:12px;line-height:1.45}}.idea b{{color:#fff}}.note{{background:rgba(255,209,102,.08);border:1px solid rgba(255,209,102,.25);border-radius:16px;padding:13px;color:#ffe8a3;margin:0 0 14px;line-height:1.45}}@media(max-width:980px){{.layout{{grid-template-columns:1fr}}.links{{display:none}}}}
</style></head><body><header><div class="nav"><a class="brand" href="/">Fantasy Edge <span>IQ</span></a><nav class="links"><a href="/euroleague">EuroLeague dashboard</a><a href="/premier-league">FPL</a><a href="/methodology">Methodology</a></nav></div><h1>EuroLeague Lineup IQ</h1><div class="sub">Select your squad, set bank credits and get budget-safe transfer ideas. <b>EuroLeague numbers only.</b></div></header><main>
<div class="note">No login required. Suggestions only show same-position moves that fit your bank.</div>
<div class="layout"><section class="box"><h2>Player pool</h2><div class="toolbar"><input id="search" placeholder="Search player or team..." oninput="renderPool()"><select id="team" onchange="renderPool()"><option value="">All teams</option></select><select id="pos" onchange="renderPool()"><option value="">All positions</option></select></div><div class="tablewrap"><table id="pool"></table></div></section>
<aside class="box"><h2>Your squad</h2><div class="toolbar"><input id="bank" type="number" value="0" min="0" step="0.1" style="width:130px" onchange="analyze()"><label class="mut">bank credits</label><select id="style" onchange="analyze()"><option value="balanced">Balanced</option><option value="safe">Safe</option><option value="aggressive">Aggressive</option></select></div><div id="squad" class="squad"></div><div class="toolbar"><button class="primary" onclick="analyze()">Generate suggestions</button><button onclick="saveSquad()">Save</button><button onclick="loadSquad()">Load</button><button class="danger" onclick="clearSquad()">Clear</button></div><div id="summary"></div></aside></div>
<section class="box" style="margin-top:16px"><h2>Transfer IQ suggestions</h2><div id="ideas" class="ideas"><p class="mut">Add your players to generate suggestions.</p></div></section>
</main><script>const DATA={json_dumps(data)};let selected=[];function n(v){{v=Number(v);return Number.isFinite(v)?v:null}}function fmt(v,d=1){{let x=n(v);return x==null?'–':x.toFixed(d)}}function byId(id){{return DATA.players.find(p=>String(p.player_id)===String(id))}}function scoreClass(x){{x=n(x)||0;return x>=80?'good':x>=65?'warn':'bad'}}function playerLine(p){{return `${{p.name}} <small>${{p.team_abbr}} · ${{p.pos_short}} · ${{fmt(p.price)}} cr · <span class='${{scoreClass(p.option_score_next5)}}'>${{fmt(p.option_score_next5)}}</span></small>`}}function init(){{let teams=[...new Set(DATA.players.map(p=>p.team_abbr).filter(Boolean))].sort();let poss=[...new Set(DATA.players.map(p=>p.pos_short).filter(Boolean))].sort();teams.forEach(x=>team.innerHTML+=`<option>${{x}}</option>`);poss.forEach(x=>pos.innerHTML+=`<option>${{x}}</option>`);renderPool();loadSquad(false)}}function filterPool(){{let q=search.value.toLowerCase(),t=team.value,p=pos.value,sel=new Set(selected.map(String));return DATA.players.filter(r=>!sel.has(String(r.player_id))&&(!q||Object.values(r).join(' ').toLowerCase().includes(q))&&(!t||r.team_abbr===t)&&(!p||r.pos_short===p)).slice(0,160)}}function renderPool(){{let rows=filterPool();pool.innerHTML='<thead><tr><th>Player</th><th>Pos</th><th>Price</th><th>Score</th><th>FDR5</th><th></th></tr></thead><tbody>'+rows.map(p=>`<tr><td>${{p.name}} <span class='mut'>${{p.team_abbr}}</span></td><td>${{p.pos_short}}</td><td>${{fmt(p.price)}}</td><td class='${{scoreClass(p.option_score_next5)}}'>${{fmt(p.option_score_next5)}}</td><td>${{fmt(p.next5_fdr_1_easy_5_hard,2)}}</td><td><button onclick="addPlayer('${{p.player_id}}')">Add</button></td></tr>`).join('')+'</tbody>'}}function renderSquad(){{let rows=selected.map(byId).filter(Boolean);squad.innerHTML=rows.length?rows.map(p=>`<div class='chip'><div>${{playerLine(p)}}</div><button class='danger' onclick="removePlayer('${{p.player_id}}')">×</button></div>`).join(''):'<p class="mut">No players selected yet.</p>';renderPool()}}function addPlayer(id){{if(!selected.map(String).includes(String(id)))selected.push(String(id));renderSquad();analyze()}}function removePlayer(id){{selected=selected.filter(x=>String(x)!==String(id));renderSquad();analyze()}}function clearSquad(){{selected=[];localStorage.removeItem('feiq_euro_squad');renderSquad();analyze()}}function saveSquad(){{localStorage.setItem('feiq_euro_squad',JSON.stringify(selected));alert('Squad saved in this browser.')}}function loadSquad(show=true){{try{{selected=JSON.parse(localStorage.getItem('feiq_euro_squad')||'[]')}}catch(e){{selected=[]}}renderSquad();analyze();if(show)alert('Squad loaded.')}}function sellScore(p){{let sc=100-(n(p.option_score_next5)||50); if(p.is_injured)sc+=35; if(p.started_from_bench)sc+=8; let f=n(p.next5_fdr_1_easy_5_hard)||3; if(f>3.2)sc+=(f-3.2)*10; let mins=n(p.min_avg_best)||0; if(mins&&mins<15)sc+=8; let val=n(p.value_pir_per_credit)||0; if(val&&val<0.8)sc+=8; return sc}}function whySell(p){{let r=[];if(p.is_injured)r.push('injury flag');if(p.started_from_bench)r.push('bench risk');if((n(p.next5_fdr_1_easy_5_hard)||0)>3.2)r.push('hard next-five run');if((n(p.value_pir_per_credit)||9)<0.9)r.push('weak value');if((n(p.min_avg_best)||99)<15)r.push('low minutes');if(!r.length)r.push('lower option score than available alternatives');return r.join(', ')}}function candidates(out,bankVal,styleVal){{bankVal=n(bankVal)||0;let outPrice=n(out.price)||0,available=outPrice+bankVal,selectedSet=new Set(selected.map(String));let same=DATA.players.filter(p=>{{let inPrice=n(p.price);return !selectedSet.has(String(p.player_id))&&p.pos_short===out.pos_short&&(!p.is_injured)&&inPrice!==null&&inPrice<=available+0.001}});let current=n(out.option_score_next5)||0;return same.map(p=>{{let inPrice=n(p.price)||0;let gain=(n(p.option_score_next5)||0)-current;let priceDiff=inPrice-outPrice;let bankLeft=bankVal-priceDiff;let fdrBonus=3-(n(p.next5_fdr_1_easy_5_hard)||3);let riskPenalty=p.started_from_bench?4:0;let styleAdj=styleVal==='safe'?(n(p.min_avg_best)||0)*0.12:styleVal==='aggressive'?(n(p.fg_attempts_per_min_best)||0)*8:0;return {{p,gain,rank:gain+fdrBonus*2+styleAdj-riskPenalty,priceDiff,bankLeft,outPrice,inPrice}}}}).filter(x=>x.gain>0&&x.bankLeft>=-0.001).sort((a,b)=>b.rank-a.rank).slice(0,5)}}function analyze(){{let rows=selected.map(byId).filter(Boolean);if(!rows.length){{summary.innerHTML='';ideas.innerHTML='<p class="mut">Add your players to generate suggestions.</p>';return}}let avg=rows.reduce((s,p)=>s+(n(p.option_score_next5)||0),0)/rows.length;let price=rows.reduce((s,p)=>s+(n(p.price)||0),0);let inj=rows.filter(p=>p.is_injured).length;let hard=rows.filter(p=>(n(p.next5_fdr_1_easy_5_hard)||0)>3.3).length;summary.innerHTML=`<div class='cards'><div class='metric'><b>${{fmt(avg)}}</b><span class='mut'>avg option score</span></div><div class='metric'><b>${{fmt(price)}}</b><span class='mut'>squad credits</span></div><div class='metric'><b class='${{inj?'bad':'good'}}'>${{inj}}</b><span class='mut'>injury flags</span></div><div class='metric'><b class='${{hard?'warn':'good'}}'>${{hard}}</b><span class='mut'>hard FDR players</span></div></div>`;let bankEl=document.getElementById('bank'),styleEl=document.getElementById('style');let bankVal=Math.max(0,n(bankEl.value)||0), styleVal=styleEl.value;bankEl.value=bankVal;let sells=rows.map(p=>({{p,s:sellScore(p)}})).sort((a,b)=>b.s-a.s).slice(0,3);let html='';html+=`<div class='idea'><h3>Priority sells</h3>${{sells.map(x=>`<div style='margin:8px 0'><b>${{x.p.name}}</b> <span class='mut'>${{x.p.team_abbr}} · ${{x.p.pos_short}}</span><br><span class='bad'>Sell pressure ${{fmt(x.s,0)}}</span> — ${{whySell(x.p)}}</div>`).join('')}}</div>`;let moves=[];for(let x of sells){{for(let c of candidates(x.p,bankVal,styleVal))moves.push({{out:x.p,...c}})}}moves.sort((a,b)=>b.rank-a.rank);html+=`<div class='idea'><h3>Best 1-transfer ideas</h3>${{moves.slice(0,6).map(m=>`<div style='margin:10px 0'><b>OUT:</b> ${{m.out.name}} <span class='mut'>${{m.out.team_abbr}} · ${{fmt(m.outPrice)}} cr</span> → <b>IN:</b> ${{m.p.name}} <span class='mut'>${{m.p.team_abbr}} · ${{fmt(m.inPrice)}} cr</span><br><span class='good'>+${{fmt(m.gain)}} option score</span> · ${{m.priceDiff>0?'uses '+fmt(m.priceDiff)+' cr bank':'frees '+fmt(-m.priceDiff)+' cr'}} · bank after ${{fmt(m.bankLeft)}} cr · FDR5 ${{fmt(m.p.next5_fdr_1_easy_5_hard,2)}}</div>`).join('')||'<p class="mut">No affordable same-position upgrades with current bank.</p>'}}</div>`;let capt=rows.slice().sort((a,b)=>(n(b.option_score_next5)||0)-(n(a.option_score_next5)||0)).slice(0,4);html+=`<div class='idea'><h3>Captain / star shortlist</h3>${{capt.map((p,i)=>`<div>${{i+1}}. <b>${{p.name}}</b> <span class='mut'>${{p.team_abbr}} · score ${{fmt(p.option_score_next5)}} · projected PIR ${{fmt(p.proj_pir_est)}}</span></div>`).join('')}}</div>`;ideas.innerHTML=html}}init();</script></body></html>'''
    (OUT / 'euroleague-team-analyzer.html').write_text(html_doc, encoding='utf-8')


def make_euro_dashboard():
    players = pd.read_csv(EURO_DATA / 'fantasheet_style_table_context.csv')
    teams = pd.read_csv(EURO_DATA / 'team_context.csv')
    schedule = pd.read_csv(EURO_DATA / 'team_next5_schedule_detail.csv')
    # Sort players for default display.
    if 'option_score_next5' in players.columns:
        players = players.sort_values(['option_score_next5','proj_pir_est'], ascending=[False, False], na_position='last')
    # Exports
    players.to_csv(OUT / 'euroleague-players-full.csv', index=False)
    teams.to_csv(OUT / 'euroleague-team-context.csv', index=False)
    schedule.to_csv(OUT / 'euroleague-next5-schedule.csv', index=False)

    top_options = players.head(12).copy()
    value = players.sort_values('value_pir_per_credit', ascending=False, na_position='last').head(12)
    usage = players.sort_values('fg_attempts_per_min_best', ascending=False, na_position='last').head(12)
    pace = teams.sort_values('pace_possessions_pg', ascending=False, na_position='last').head(8)
    # Overview card should show the clubs/teams with the easiest next-five runs,
    # not individual players from those clubs.
    schedule_summary = pd.read_csv(EURO_DATA / 'team_next5_schedule_summary.csv')
    team_names = teams[['team_abbr', 'team_name']].drop_duplicates() if 'team_name' in teams.columns else pd.DataFrame({'team_abbr': [], 'team_name': []})
    easy = (schedule_summary.merge(team_names, on='team_abbr', how='left')
            .sort_values('next5_fdr_1_easy_5_hard', ascending=True, na_position='last')
            .head(12))
    generated = datetime.now().strftime('%Y-%m-%d %H:%M CET')

    pcols_main = ['name','team_abbr','pos_short','price','option_score_next5','next_period_rating','next5_fdr_1_easy_5_hard','next5_opponents','proj_pir_est','form_pir','value_pir_per_credit','fantasy_pts_current_md','min_avg_best','pir_avg_current','pir_25_26','fg_attempts_pg_best','fg_pct_best','fg_attempts_per_min_best','reb_avg_current','ast_avg_current','stl_avg_current','tov_avg_current','team_pace_possessions_pg','team_fga_for_pg','team_pir_allowed_pg','is_injured','started_from_bench','popularity_pct']
    pcols_main = [c for c in pcols_main if c in players.columns]
    pcols_full = list(players.columns)
    tcols = list(teams.columns)
    scols = list(schedule.columns)
    labels = {c: euro_label(c) for c in set(pcols_full + tcols + scols)}
    data = {
        'generated': generated,
        'players': clean_records(players),
        'teams': clean_records(teams),
        'schedule': clean_records(schedule),
        'topOptions': clean_records(top_options),
        'valueLeaders': clean_records(value),
        'usageLeaders': clean_records(usage),
        'paceLeaders': clean_records(pace),
        'easyRuns': clean_records(easy),
        'pcolsMain': pcols_main,
        'pcolsFull': pcols_full,
        'tcols': tcols,
        'scols': scols,
        'labels': labels,
    }

    html_doc = f'''<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>EuroLeague Fantasy Advanced Dashboard — Fantasy Edge IQ</title>
<meta name="description" content="EuroLeague Fantasy advanced dashboard with full player statistics, prices, PIR, minutes, shooting volume, rebounds, assists, next-five fixture difficulty, team pace and matchup context.">
<meta name="robots" content="index,follow,max-snippet:-1,max-image-preview:large">
<link rel="canonical" href="{SITE}/euroleague">
<meta property="og:type" content="website"><meta property="og:site_name" content="Fantasy Edge IQ"><meta property="og:title" content="EuroLeague Fantasy Advanced Dashboard"><meta property="og:description" content="Full EuroLeague Fantasy table with player value, schedule difficulty, team context, shooting usage and option scores."><meta property="og:url" content="{SITE}/euroleague">
<style>
:root{{--bg:#08111f;--panel:#0e2038;--panel2:#132b4a;--line:rgba(255,255,255,.1);--txt:#eef6ff;--mut:#aabbd2;--blue:#5bbcff;--green:#22c55e;--yellow:#ffd166;--red:#fb7185}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--txt);font-family:Inter,system-ui,Segoe UI,Arial,sans-serif;font-size:14px}}a{{color:#8ed6ff;text-decoration:none}}header{{padding:24px;background:linear-gradient(135deg,#07101d,#122b49);border-bottom:1px solid var(--line)}}.topnav{{display:flex;justify-content:space-between;align-items:center;gap:14px;margin-bottom:20px}}.brand{{font-weight:950;font-size:18px}}.brand span{{color:var(--blue)}}.navlinks{{display:flex;gap:14px;color:var(--mut);font-size:13px}}h1{{margin:0 0 8px;font-size:clamp(26px,4vw,44px);letter-spacing:-.05em}}.sub{{color:var(--mut);font-size:16px;max-width:1050px}}main{{padding:22px 24px 46px}}.tabs{{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 16px}}button,.btn{{background:#143052;color:#fff;border:1px solid rgba(91,188,255,.24);border-radius:12px;padding:10px 13px;font-weight:800;cursor:pointer}}button.active{{background:#0d75bd;border-color:#7bd3ff}}.btn{{display:inline-block}}.filters{{display:flex;gap:10px;flex-wrap:wrap;margin:12px 0 16px}}input,select{{background:#0b1b30;border:1px solid rgba(255,255,255,.12);color:#eef6ff;border-radius:12px;padding:10px 12px}}.panel{{display:none}}.panel.active{{display:block}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:14px;margin:16px 0 22px}}.card{{background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:16px;box-shadow:0 16px 50px rgba(0,0,0,.18)}}.card h3{{margin:0 0 12px;font-size:16px}}.row{{display:flex;justify-content:space-between;gap:12px;padding:7px 0;border-bottom:1px solid rgba(255,255,255,.07)}}.row:last-child{{border-bottom:0}}.row span{{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}.row b{{color:#fff}}.tablewrap{{overflow:auto;max-height:72vh;border:1px solid var(--line);border-radius:16px;background:#0b1b30}}table{{border-collapse:separate;border-spacing:0;min-width:100%;font-size:12px}}th,td{{padding:9px 10px;border-bottom:1px solid rgba(255,255,255,.08);white-space:nowrap;text-align:left}}th{{position:sticky;top:0;background:#193b63;color:#fff;z-index:3;cursor:pointer}}td:first-child,th:first-child{{position:sticky;left:0;background:inherit;z-index:2}}th:first-child{{z-index:4;background:#193b63}}tr:nth-child(even) td{{background:rgba(255,255,255,.018)}}tr:hover td{{background:rgba(91,188,255,.08)}}.pill{{display:inline-flex;border-radius:999px;padding:3px 8px;background:rgba(91,188,255,.12);border:1px solid rgba(91,188,255,.25)}}.bad{{color:#fecdd3}}.good{{color:#86efac}}.mut{{color:var(--mut)}}.downloads{{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0 16px}}.note{{background:rgba(255,209,102,.08);border:1px solid rgba(255,209,102,.25);border-radius:16px;padding:14px;color:#ffe8a3;margin:14px 0}}.method{{max-width:1050px;line-height:1.65;color:#d7e7fa}}.method li{{margin:7px 0}}@media(max-width:760px){{.navlinks{{display:none}}main,header{{padding-left:14px;padding-right:14px}}}}
</style></head><body><header><div class="topnav"><a class="brand" href="/">Fantasy Edge <span>IQ</span></a><nav class="navlinks"><a href="/">Home</a><a href="/euroleague/team-analyzer">Lineup IQ</a><a href="/premier-league">FPL</a><a href="/pricing">Pricing</a><a href="/methodology">Methodology</a></nav></div><h1>EuroLeague Fantasy Advanced Dashboard</h1><div class="sub">Full player table, player option score, next-five schedule difficulty, team pace, shot/rebound environments and matchup context. Generated: <b id="gen"></b></div></header><main>
<div class="tabs"><button class="tab active" data-tab="overview">Overview</button><button class="tab" data-tab="players">Player Options</button><button class="tab" data-tab="fullstats">Full Player Stats</button><button class="tab" data-tab="teams">Team Context</button><button class="tab" data-tab="schedule">Next 5 Schedule</button><button class="tab" data-tab="method">Method</button></div>
<section id="overview" class="panel active"><div class="note">Tip: The full EuroLeague table is now included under <b>Full Player Stats</b>. Use horizontal scroll for all columns or download the CSV.</div><div class="cards"><div class="card"><h3>Top option scores</h3><div id="topOptions"></div></div><div class="card"><h3>Best value PIR / credit</h3><div id="valueBox"></div></div><div class="card"><h3>Highest shot usage</h3><div id="usageBox"></div></div><div class="card"><h3>Easiest team next-five runs</h3><div id="easyBox"></div></div><div class="card"><h3>Fastest team environments</h3><div id="paceBox"></div></div></div></section>
<section id="players" class="panel"><h2>Player Options</h2><p class="mut">Decision-focused view with price, model score, schedule, projection, minutes, shooting, box-score context and risk flags.</p><div class="downloads"><a class="btn" href="/euroleague-players-full.csv">Download full player CSV</a><a class="btn" href="/euroleague-team-context.csv">Download team CSV</a><a class="btn" href="/euroleague-next5-schedule.csv">Download schedule CSV</a></div><div class="filters"><input id="pq" placeholder="Search player/team..." oninput="renderCurrent()"><select id="teamFilter" onchange="renderCurrent()"><option value="">All teams</option></select><select id="posFilter" onchange="renderCurrent()"><option value="">All positions</option></select><label class="pill"><input id="hideInj" type="checkbox" checked onchange="renderCurrent()"> hide injured</label></div><div class="tablewrap"><table id="playersTable"></table></div></section>
<section id="fullstats" class="panel"><h2>Full Player Stats</h2><p class="mut">Every available EuroLeague column from our current data table: fantasy prices, PIR, minutes, shooting, rebounds, assists, schedule, team context and model components.</p><div class="downloads"><a class="btn" href="/euroleague-players-full.csv">Download full player CSV</a></div><div class="filters"><input id="fq" placeholder="Search full table..." oninput="renderCurrent()"><select id="fullTeamFilter" onchange="renderCurrent()"><option value="">All teams</option></select><select id="fullPosFilter" onchange="renderCurrent()"><option value="">All positions</option></select><label class="pill"><input id="fullHideInj" type="checkbox" checked onchange="renderCurrent()"> hide injured</label></div><div class="tablewrap"><table id="fullTable"></table></div></section>
<section id="teams" class="panel"><h2>Team Context</h2><p class="mut">Team pace, FGA environment, rebounds allowed, PIR allowed and defensive matchup score.</p><div class="downloads"><a class="btn" href="/euroleague-team-context.csv">Download team CSV</a></div><div class="filters"><input id="tq" placeholder="Search team..." oninput="renderTeams()"></div><div class="tablewrap"><table id="teamsTable"></table></div></section>
<section id="schedule" class="panel"><h2>Next 5 Schedule</h2><p class="mut">Upcoming fixture-level matchup context by team. FDR scale: 1 easy, 5 hard.</p><div class="downloads"><a class="btn" href="/euroleague-next5-schedule.csv">Download schedule CSV</a></div><div class="filters"><input id="sq" placeholder="Search schedule..." oninput="renderSchedule()"></div><div class="tablewrap"><table id="scheduleTable"></table></div></section>
<section id="method" class="panel method"><h2>Method</h2><ul><li><b>Team pace</b>: estimated as FGA + 0.44 × FTA - OREB + TOV, blended with opponent possessions where available.</li><li><b>Next-five difficulty</b>: uses opponent pace, PIR allowed, points allowed, FGA allowed and rebounds allowed. Lower FDR is easier.</li><li><b>Option score</b>: combines projected PIR, value, minutes, shooting usage, price gap, form, schedule and risk penalties.</li><li><b>Full stats tab</b>: includes all 81 columns currently generated by the model, not only the short decision view.</li></ul><p class="mut">All metrics are beta estimates and should support, not replace, your own fantasy judgment.</p></section>
</main><script>const DATA={json_dumps(data)};
const numCols=new Set(['price','price_base','price_change','proj_pir_est','form_pir','value_pir_per_credit','fantasy_pts_current_md','value_fantasy_per_credit','gp_current','min_avg_best','min_avg_current','pts_avg_current','pir_avg_current','pir_25_26','min_avg_25_26','floor_est','ceiling_est','price_gap_est','fg_made_pg_best','fg_attempts_pg_best','fg_pct_best','fg_attempts_per_min_best','fg_attempts_per40_best','fg_made_pg_current','fg_attempts_pg_current','fg_pct_current','fg_attempts_per_min_current','fg_attempts_per40_current','reb_avg_current','oreb_avg_current','dreb_avg_current','pf_avg_current','fd_avg_current','stl_avg_current','tov_avg_current','ast_avg_current','blk_avg_current','blka_avg_current','popularity_pct','team_pace_possessions_pg','team_fga_for_pg','team_fga_allowed_pg','team_oreb_allowed_pg','team_dreb_allowed_pg','team_pir_allowed_pg','team_defense_weakness_score','next5_count','next5_ease_score','next5_fdr_1_easy_5_hard','option_score_next5','pace_possessions_pg','for_fga_pg','allowed_fga_pg','allowed_oreb_pg','allowed_dreb_pg','allowed_pir_pg','team_defense_fdr_1_easy_5_hard','fdr_1_easy_5_hard']);
let sortState={{}};function label(c){{return DATA.labels[c]||c}}function fmt(c,v){{if(v===null||v===undefined||Number.isNaN(v))return ''; if(typeof v==='boolean')return v?'Yes':'No'; if(numCols.has(c)&&!isNaN(Number(v))){{let n=Number(v);return Math.abs(n)>=100?String(Math.round(n*10)/10):String(Math.round(n*100)/100)}} return String(v)}}function ftext(r,q){{if(!q)return true;q=q.toLowerCase();return Object.values(r).some(v=>String(v??'').toLowerCase().includes(q))}}function cmp(a,b,c,dir){{let av=a[c],bv=b[c];let an=Number(av),bn=Number(bv);let res;if(av==null&&bv==null)res=0;else if(av==null)res=1;else if(bv==null)res=-1;else if(!Number.isNaN(an)&&!Number.isNaN(bn))res=an-bn;else res=String(av).localeCompare(String(bv));return dir==='asc'?res:-res}}function table(id,rows,cols,key){{let st=sortState[key]; if(st)rows=[...rows].sort((a,b)=>cmp(a,b,st.c,st.d));let h='<thead><tr>'+cols.map(c=>`<th onclick="setSort('${{key}}','${{c}}')">${{label(c)}}${{st&&st.c===c?(st.d==='asc'?' ↑':' ↓'):''}}</th>`).join('')+'</tr></thead>';let b='<tbody>'+rows.map(r=>'<tr>'+cols.map(c=>`<td>${{fmt(c,r[c])}}</td>`).join('')+'</tr>').join('')+'</tbody>';document.getElementById(id).innerHTML=h+b}}function setSort(k,c){{let s=sortState[k];sortState[k]={{c,d:s&&s.c===c&&s.d==='desc'?'asc':'desc'}};renderCurrent()}}function filtered(q,team,pos,hide){{return DATA.players.filter(r=>ftext(r,q)&&(!team||r.team_abbr===team)&&(!pos||r.pos_short===pos)&&(!hide||!r.is_injured))}}function renderPlayers(){{table('playersTable',filtered(pq.value,teamFilter.value,posFilter.value,hideInj.checked),DATA.pcolsMain,'players')}}function renderFull(){{table('fullTable',filtered(fq.value,fullTeamFilter.value,fullPosFilter.value,fullHideInj.checked),DATA.pcolsFull,'full')}}function renderTeams(){{table('teamsTable',DATA.teams.filter(r=>ftext(r,tq.value)),DATA.tcols,'teams')}}function renderSchedule(){{table('scheduleTable',DATA.schedule.filter(r=>ftext(r,sq.value)),DATA.scols,'schedule')}}function renderCurrent(){{let id=document.querySelector('.panel.active').id;if(id==='players')renderPlayers(); if(id==='fullstats')renderFull(); if(id==='teams')renderTeams(); if(id==='schedule')renderSchedule()}}function mini(el,rows,main,sub,extra){{document.getElementById(el).innerHTML=rows.map(r=>`<div class='row'><span>${{r[main]||''}}${{extra?` <span class='mut'>${{r[extra]||''}}</span>`:''}}</span><b>${{fmt(sub,r[sub])}}</b></div>`).join('')}}function init(){{gen.textContent=DATA.generated;let teams=[...new Set(DATA.players.map(r=>r.team_abbr).filter(Boolean))].sort();let poss=[...new Set(DATA.players.map(r=>r.pos_short).filter(Boolean))].sort();for(let x of teams){{teamFilter.innerHTML+=`<option>${{x}}</option>`;fullTeamFilter.innerHTML+=`<option>${{x}}</option>`}}for(let x of poss){{posFilter.innerHTML+=`<option>${{x}}</option>`;fullPosFilter.innerHTML+=`<option>${{x}}</option>`}}document.querySelectorAll('.tab').forEach(b=>b.onclick=()=>{{document.querySelectorAll('.tab,.panel').forEach(x=>x.classList.remove('active'));b.classList.add('active');document.getElementById(b.dataset.tab).classList.add('active');renderCurrent()}});mini('topOptions',DATA.topOptions,'name','option_score_next5','team_abbr');mini('valueBox',DATA.valueLeaders,'name','value_pir_per_credit','team_abbr');mini('usageBox',DATA.usageLeaders,'name','fg_attempts_per_min_best','team_abbr');mini('easyBox',DATA.easyRuns,'team_abbr','next5_fdr_1_easy_5_hard','team_name');mini('paceBox',DATA.paceLeaders,'team_abbr','pace_possessions_pg','team_name');sortState.players={{c:'option_score_next5',d:'desc'}};sortState.full={{c:'option_score_next5',d:'desc'}};renderPlayers()}}init();</script></body></html>'''
    (OUT / 'euroleague-dashboard.html').write_text(html_doc, encoding='utf-8')


def english_fpl_html(s: str) -> str:
    """Clean visible FPL dashboard text for the international English site."""
    import re
    replacements = {
        '<html lang="sr">': '<html lang="en">',
        '<title>Fantazi Premijer Liga — pro dashboard</title>': '<title>Fantasy Premier League Dashboard — Fantasy Edge IQ</title>',
        '<h1>Fantazi Premijer Liga — Pro dashboard</h1>': '<h1>Fantasy Premier League — Advanced Dashboard</h1>',
        'Dashboard za FPL: cijene, forma, value, minute, raspored, transferi i povrede. Generisano:': 'FPL dashboard: prices, form, value, minutes, fixtures, transfers and injuries. Generated:',
        'trenutni GW': 'current GW',
        'prosek PTS': 'average PTS',
        'najviše PTS': 'highest PTS',
        'sledeći deadline': 'next deadline',
        'igrača u bazi': 'players in database',
        'data-tab="players">Igrači</button>': 'data-tab="players">Players</button>',
        'data-tab="fixtures">Utakmice</button>': 'data-tab="fixtures">Fixtures</button>',
        'data-tab="injuries">Povrede</button>': 'data-tab="injuries">Injuries</button>',
        'data-tab="transfers">Transferi/Cijene</button>': 'data-tab="transfers">Transfers / Prices</button>',
        '<button class="tab" data-tab="business">Paid verzija</button>': '',
        'Igrač kola': 'Player of the Gameweek',
        'Najveće vlasništvo': 'Highest ownership',
        'Najviše kupovan': 'Most bought',
        'Najviše kapiten': 'Most captained',
        'Promjene cijena · GW': 'Price changes · GW',
        'Transferi in': 'Transfers in',
        'Povrede/news': 'Injuries/news',
        'placeholder="Pretraga igrača..."': 'placeholder="Search players..."',
        'Svi klubovi': 'All clubs',
        'Sve pozicije': 'All positions',
        'sakrij bez minuta': 'hide players with no minutes',
        'sakrij povrijeđene/suspendovane': 'hide injured/suspended',
        '<b>Value</b> = points per game / cijena. Dodatno imaš Form, EP next, min.avg, last3/last5 minute i FDR narednih 5 kola.': '<b>Value</b> = points per game divided by price. The table also includes form, expected points, average minutes, last 3/5 minute trends and next-five FDR.',
        'placeholder="Pretraga utakmica..."': 'placeholder="Search fixtures..."',
        'Sva kola': 'All gameweeks',
        'Najviše kupovani': 'Most bought',
        'Najviše prodavani': 'Most sold',
        'Promjene cijena': 'Price changes',
        "web_name:'Igrač'": "web_name:'Player'",
        "full_name:'Ime'": "full_name:'Name'",
        "team_short:'Klub'": "team_short:'Club'",
        "transfers_in_event:'Kupovina'": "transfers_in_event:'Transfers in'",
        "transfers_out_event:'Prodaja'": "transfers_out_event:'Transfers out'",
        "transfers_balance_event:'Balans'": "transfers_balance_event:'Transfer balance'",
        "kickoff_local:'Vrijeme'": "kickoff_local:'Time'",
        "result:'Rez'": "result:'Score'",
        "winner:'Pobj'": "winner:'Winner'",
        "if(typeof x==='boolean')return x?'DA':'NE';": "if(typeof x==='boolean')return x?'YES':'NO';",
    }
    for old, new in replacements.items():
        s = s.replace(old, new)
    s = re.sub(r'<div class="note">Ovo je prototip.*?</div>', '', s)
    s = re.sub(r'<section id="business" class="panel">.*?</section>', '', s)
    return s


def add_meta_to_fpl():
    src = (ROOT / 'fpl_fantasy_dashboard.html') if (ROOT / 'fpl_fantasy_dashboard.html').exists() else (FLAT / 'premier-league-dashboard.html')
    if not src.exists():
        return
    s = english_fpl_html(src.read_text(encoding='utf-8'))
    # Replace or enrich head after charset/title. Keep original body/dashboard intact.
    if '<link rel="canonical"' not in s:
        insert = f'''\n<meta name="description" content="Fantasy Premier League dashboard with FPL players, prices, ownership, transfers, injuries, value, form, minutes, expected points and upcoming fixtures.">\n<meta name="robots" content="index,follow,max-snippet:-1,max-image-preview:large">\n<link rel="canonical" href="{SITE}/premier-league">\n<meta property="og:type" content="website"><meta property="og:site_name" content="Fantasy Edge IQ"><meta property="og:title" content="Fantasy Premier League Dashboard — Fantasy Edge IQ"><meta property="og:description" content="Free FPL beta dashboard with value, fixtures, injuries, price changes and transfer trends."><meta property="og:url" content="{SITE}/premier-league">'''
        s = s.replace('<meta name="viewport" content="width=device-width, initial-scale=1">', '<meta name="viewport" content="width=device-width, initial-scale=1">' + insert, 1)
        s = s.replace('<meta name="viewport" content="width=device-width,initial-scale=1">', '<meta name="viewport" content="width=device-width,initial-scale=1">' + insert, 1)
    (OUT / 'premier-league-dashboard.html').write_text(s, encoding='utf-8')


def make_simple_pages():
    pages = {
        'about.html': ('About Fantasy Edge IQ', 'Fantasy Edge IQ is an independent fantasy analytics beta for managers who want clearer data before every lock. We currently cover EuroLeague Fantasy and Fantasy Premier League with free dashboards during beta.'),
        'pricing.html': ('Pricing', 'Fantasy Edge IQ is free during beta. EuroLeague and FPL dashboards are available while we test the platform and improve the models. Pro features such as saved watchlists, alerts, lineup builders and private projections may launch later.'),
        'methodology.html': ('Methodology', 'EuroLeague models combine projected PIR, value, minutes, shooting usage, next-five fixture difficulty, team pace and matchup context. FPL models use public player, fixture and element history data including price, ownership, form, minutes, transfers, news and expected points.'),
        'privacy.html': ('Privacy', 'Fantasy Edge IQ is a beta analytics website. We do not sell personal data. This policy will be expanded before a public commercial launch.'),
        'terms.html': ('Terms', 'Fantasy Edge IQ provides fantasy analytics for informational purposes only. Use the data as decision support, not as guaranteed advice.'),
        'disclaimer.html': ('Disclaimer', 'Fantasy Edge IQ is an independent project. It is not affiliated with Euroleague Basketball, Premier League or Fantasy Premier League. Fantasy outcomes are uncertain and all models are beta estimates.'),
    }
    for fn,(title,body) in pages.items():
        slug = fn.replace('.html','')
        desc = body[:155]
        doc = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)} — Fantasy Edge IQ</title><meta name="description" content="{html.escape(desc)}"><link rel="canonical" href="{SITE}/{slug}"><meta name="robots" content="index,follow"><style>body{{margin:0;background:#07101d;color:#eef6ff;font-family:system-ui,Segoe UI,Arial,sans-serif;line-height:1.6}}.wrap{{max-width:930px;margin:0 auto;padding:42px 22px}}a{{color:#5bbcff}}.card{{background:#111f34;border:1px solid rgba(255,255,255,.1);border-radius:20px;padding:24px;margin-top:18px}}.mut{{color:#9fb1c9}}</style></head><body><main class="wrap"><a href="/">← Home</a><h1>{html.escape(title)}</h1><div class="card"><p>{html.escape(body)}</p></div><p class="mut">Last updated: {TODAY}</p></main></body></html>'''
        (OUT / fn).write_text(doc, encoding='utf-8')


def make_robots_sitemap_package():
    urls = ['','euroleague','euroleague/dashboard','euroleague/team-analyzer','premier-league','premier-league/dashboard','pricing','methodology','about','privacy','terms','disclaimer']
    (OUT / 'robots.txt').write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE}/sitemap.xml\n", encoding='utf-8')
    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for u in urls:
        loc = SITE + ('/' + u if u else '/')
        priority = '1.0' if u=='' else ('0.9' if u in ['euroleague','premier-league'] else '0.7')
        sitemap += f"  <url><loc>{loc}</loc><lastmod>{TODAY}</lastmod><changefreq>daily</changefreq><priority>{priority}</priority></url>\n"
    sitemap += '</urlset>\n'
    (OUT / 'sitemap.xml').write_text(sitemap, encoding='utf-8')
    package = {
        'name':'fantasy-edge-iq','version':'0.2.0','private':True,
        'description':'Fantasy Edge IQ free beta dashboards for EuroLeague Fantasy and Fantasy Premier League.',
        'scripts':{
            'build':'rm -rf public && mkdir -p public/euroleague/dashboard public/euroleague/team-analyzer public/premier-league/dashboard public/pricing public/methodology public/about public/privacy public/terms public/disclaimer && cp *.html public/ && cp -f *.csv public/ 2>/dev/null || true && cp -f *.xml public/ 2>/dev/null || true && cp -f *.txt public/ 2>/dev/null || true && cp euroleague-dashboard.html public/euroleague/index.html && cp euroleague-dashboard.html public/euroleague/dashboard/index.html && cp euroleague-team-analyzer.html public/euroleague/team-analyzer/index.html && cp premier-league-dashboard.html public/premier-league/index.html && cp premier-league-dashboard.html public/premier-league/dashboard/index.html && cp pricing.html public/pricing/index.html && cp methodology.html public/methodology/index.html && cp about.html public/about/index.html && cp privacy.html public/privacy/index.html && cp terms.html public/terms/index.html && cp disclaimer.html public/disclaimer/index.html',
            'dev':'python3 -m http.server 3000'
        }
    }
    (OUT / 'package.json').write_text(json.dumps(package, indent=2), encoding='utf-8')
    vercel = {
        'cleanUrls': True,
        'trailingSlash': False,
        'headers': [{'source':'/(.*)','headers':[{'key':'X-Content-Type-Options','value':'nosniff'},{'key':'Referrer-Policy','value':'strict-origin-when-cross-origin'}]}]
    }
    (OUT / 'vercel.json').write_text(json.dumps(vercel, indent=2), encoding='utf-8')
    readme = '''# Fantasy Edge IQ v2 upload package

Upload all files in this folder to the GitHub repository root and commit.

This version includes:
- stronger homepage copy and SEO metadata
- robots.txt and sitemap.xml
- enhanced EuroLeague dashboard with a Full Player Stats tab
- CSV downloads for EuroLeague full player table, team context and next-five schedule
- package.json build script that creates the public output and clean route folders for Vercel

After commit, Vercel will automatically redeploy.
'''
    (OUT / 'README_DEPLOY.md').write_text(readme, encoding='utf-8')


def main():
    # Do not delete repository files; overwrite known site outputs only.
    make_homepage()
    make_euro_dashboard()
    make_euro_team_analyzer()
    add_meta_to_fpl()
    make_simple_pages()
    make_robots_sitemap_package()
    # Optional FPL exports for download/SEO freshness
    for name in ['fpl_players.csv','fpl_fixtures.csv','fpl_player_history.csv','fpl_upcoming_player_fixtures.csv']:
        src = FPL_DATA / name
        if src.exists(): copy_if_exists(src)
    print('Wrote', OUT)

if __name__ == '__main__':
    main()
