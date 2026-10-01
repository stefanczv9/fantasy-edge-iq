from pathlib import Path
import pandas as pd, numpy as np, json
from html import escape
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
EURO=ROOT/'euroleague_fantasy_data'
OUT=ROOT
SITE='https://www.fantasyedgeiq.com'
log=pd.read_csv(EURO/'fantasy_poeni_log.csv')
positions=[('Guard','guard'),('Forward','forward'),('Center','center')]
for c in ['pts','reb','ast','stl','blk','tov']:
    log[c]=pd.to_numeric(log.get(c,0),errors='coerce').fillna(0)
log['team_score']=pd.to_numeric(log['team_score'],errors='coerce')
log=log[(log['match_status']=='played') & log['opponent_abbr'].notna() & log['team_abbr'].notna() & log['position'].isin([p[0] for p in positions])]
rows=[]
for (match_id, defense, offense), g in log.groupby(['match_id','opponent_abbr','team_abbr'], dropna=True):
    row={'match_id':int(match_id),'team_abbr':defense,'opponent_abbr':offense}
    for c in ['home_abbr','away_abbr','start_local','team_score','opponent_score']:
        if c in g.columns: row[c]=g[c].iloc[0]
    row['box_score_pts_allowed']=float(g['team_score'].iloc[0])
    for pos,key in positions:
        pg=g[g['position']==pos]
        row[f'{key}_pts_allowed']=float(pg['pts'].sum())
        row[f'{key}_reb_allowed']=float(pg['reb'].sum())
        row[f'{key}_ast_allowed']=float(pg['ast'].sum())
        row[f'{key}_stl_allowed']=float(pg['stl'].sum())
        row[f'{key}_blk_allowed']=float(pg['blk'].sum())
        row[f'{key}_tov_forced']=float(pg['tov'].sum())
    row['position_pts_allowed']=sum(row[f'{key}_pts_allowed'] for _,key in positions)
    row['validation_diff']=row['position_pts_allowed']-row['box_score_pts_allowed']
    row['validation_ok']=abs(row['validation_diff'])<=0.1
    rows.append(row)
match=pd.DataFrame(rows).sort_values(['match_id','team_abbr'])
# keep matchlog as audit source
match.to_csv(OUT/'euroleague-defense-vs-position-matchlog.csv',index=False)
valid=match[match.validation_ok].copy()
if valid.empty: valid=match.copy()
agg=valid.groupby('team_abbr').agg(
    games_sample=('match_id','nunique'),
    box_score_pts_allowed_total=('box_score_pts_allowed','sum'),
    position_pts_allowed_total=('position_pts_allowed','sum'),
    validation_diff_total=('validation_diff','sum'),
).reset_index()
for _,key in positions:
    for metric in ['pts_allowed','reb_allowed','ast_allowed','stl_allowed','blk_allowed','tov_forced']:
        col=f'{key}_{metric}'
        sums=valid.groupby('team_abbr')[col].sum().reset_index(name=col+'_total')
        agg=agg.merge(sums,on='team_abbr',how='left')
        agg[col+'_pg']=agg[col+'_total']/agg['games_sample'].replace(0,np.nan)
agg['box_score_pts_allowed_pg']=agg['box_score_pts_allowed_total']/agg['games_sample'].replace(0,np.nan)
agg['position_pts_allowed_pg']=agg['position_pts_allowed_total']/agg['games_sample'].replace(0,np.nan)
agg['validation_diff_pg']=agg['validation_diff_total']/agg['games_sample'].replace(0,np.nan)
agg['validation_ok']=agg['validation_diff_total'].abs()<=0.1
agg['sample_confidence']=np.select([agg.games_sample<2, agg.games_sample<5, agg.games_sample<10], ['very low','low','medium'], default='high')
team_name=None
for p in [EURO/'team_context.csv', OUT/'euroleague-team-context.csv']:
    if p.exists():
        tmp=pd.read_csv(p)
        if {'team_abbr','team_name'}.issubset(tmp.columns):
            team_name=tmp[['team_abbr','team_name']].drop_duplicates(); break
if team_name is not None: agg=agg.merge(team_name,on='team_abbr',how='left')
else: agg['team_name']=agg.team_abbr

def fdr(series):
    s=pd.to_numeric(series,errors='coerce')
    if s.notna().sum()<2 or float(s.max())==float(s.min()): return pd.Series([3.0]*len(s),index=s.index)
    return 1+4*((s.max()-s)/(s.max()-s.min()))
for _,key in positions:
    agg[f'{key}_real_pts_fdr_1_easy_5_hard']=fdr(agg[f'{key}_pts_allowed_pg']).round(2)
ordered=['team_abbr','team_name','games_sample','sample_confidence','validation_ok','validation_diff_pg','box_score_pts_allowed_pg','position_pts_allowed_pg']
for _,key in positions:
    ordered += [f'{key}_pts_allowed_pg', f'{key}_real_pts_fdr_1_easy_5_hard', f'{key}_reb_allowed_pg', f'{key}_ast_allowed_pg', f'{key}_stl_allowed_pg', f'{key}_blk_allowed_pg', f'{key}_tov_forced_pg']
agg=agg[[c for c in ordered if c in agg.columns]].copy()
for c in agg.columns:
    if pd.api.types.is_numeric_dtype(agg[c]): agg[c]=agg[c].round(2)
agg=agg.sort_values(['guard_pts_allowed_pg','team_abbr'],ascending=[False,True])
agg.to_csv(OUT/'euroleague-defense-vs-position.csv',index=False)
# HTML real-only
cols=['team_abbr','team_name','games_sample','sample_confidence','validation_ok','validation_diff_pg','box_score_pts_allowed_pg','position_pts_allowed_pg','guard_pts_allowed_pg','forward_pts_allowed_pg','center_pts_allowed_pg','guard_real_pts_fdr_1_easy_5_hard','forward_real_pts_fdr_1_easy_5_hard','center_real_pts_fdr_1_easy_5_hard','guard_reb_allowed_pg','forward_reb_allowed_pg','center_reb_allowed_pg','guard_ast_allowed_pg','forward_ast_allowed_pg','center_ast_allowed_pg']
cols=[c for c in cols if c in agg.columns]
labels={
 'team_abbr':'Team','team_name':'Club','games_sample':'Games','sample_confidence':'Sample','validation_ok':'Validated','validation_diff_pg':'Diff/G','box_score_pts_allowed_pg':'Box PTS allowed/G','position_pts_allowed_pg':'Position total/G',
 'guard_pts_allowed_pg':'Real PTS vs Guards/G','forward_pts_allowed_pg':'Real PTS vs Forwards/G','center_pts_allowed_pg':'Real PTS vs Centers/G',
 'guard_real_pts_fdr_1_easy_5_hard':'Guard real-PTS FDR','forward_real_pts_fdr_1_easy_5_hard':'Forward real-PTS FDR','center_real_pts_fdr_1_easy_5_hard':'Center real-PTS FDR',
 'guard_reb_allowed_pg':'REB vs Guards/G','forward_reb_allowed_pg':'REB vs Forwards/G','center_reb_allowed_pg':'REB vs Centers/G',
 'guard_ast_allowed_pg':'AST vs Guards/G','forward_ast_allowed_pg':'AST vs Forwards/G','center_ast_allowed_pg':'AST vs Centers/G'
}
data={'generated':datetime.now(ZoneInfo('Europe/Zagreb')).strftime('%Y-%m-%d %H:%M %Z'), 'summary': json.loads(agg.to_json(orient='records'))}
css=":root{--bg:#08111f;--panel:#0e2038;--line:rgba(255,255,255,.1);--txt:#eef6ff;--mut:#aabbd2;--blue:#5bbcff;--green:#22c55e;--yellow:#ffd166;--red:#fb7185}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at top left,#173a63,#08111f 58%);color:var(--txt);font-family:Inter,system-ui,Segoe UI,Arial,sans-serif;font-size:14px;line-height:1.55}a{color:#8ed6ff;text-decoration:none}header,main{max-width:1220px;margin:0 auto;padding:24px}.topnav{display:flex;justify-content:space-between;gap:14px;align-items:center;margin-bottom:24px}.brand{font-weight:950;font-size:19px;color:#fff}.brand span{color:var(--blue)}.navlinks{display:flex;gap:14px;color:var(--mut);font-size:13px}h1{margin:0 0 10px;font-size:clamp(32px,5vw,56px);letter-spacing:-.055em;line-height:1}.sub{color:var(--mut);font-size:17px;max-width:980px}.note{background:rgba(255,209,102,.08);border:1px solid rgba(255,209,102,.25);border-radius:16px;padding:14px;color:#ffe8a3;margin:18px 0}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px;margin:18px 0}.card{background:rgba(14,32,56,.9);border:1px solid var(--line);border-radius:18px;padding:16px;box-shadow:0 16px 50px rgba(0,0,0,.18)}.card h3{margin:0 0 12px}.row{display:flex;justify-content:space-between;gap:12px;padding:7px 0;border-bottom:1px solid rgba(255,255,255,.07)}.row:last-child{border-bottom:0}.row span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.row b{color:#fff}.downloads{display:flex;gap:8px;flex-wrap:wrap;margin:18px 0}.btn,button{display:inline-flex;background:#143052;color:#fff;border:1px solid rgba(91,188,255,.24);border-radius:12px;padding:10px 13px;font-weight:850;cursor:pointer}input{background:#0b1b30;border:1px solid rgba(255,255,255,.12);color:#eef6ff;border-radius:12px;padding:10px 12px;min-width:260px}.tablewrap{overflow:auto;max-height:72vh;border:1px solid var(--line);border-radius:16px;background:#0b1b30}table{border-collapse:separate;border-spacing:0;min-width:1100px;width:100%;font-size:12px}th,td{padding:9px 10px;border-bottom:1px solid rgba(255,255,255,.08);white-space:nowrap;text-align:left}th{position:sticky;top:0;background:#193b63;color:#fff;z-index:3;cursor:pointer}td:first-child,th:first-child{position:sticky;left:0;background:#0b1b30;z-index:2}th:first-child{z-index:4;background:#193b63}.good{color:#86efac;font-weight:900}.warn{color:#fde68a;font-weight:900}.bad{color:#fda4af;font-weight:900}.mut{color:var(--mut)}@media(max-width:760px){header,main{padding-left:14px;padding-right:14px}.navlinks{display:none}input{width:100%;min-width:0}}"
html=f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>EuroLeague Real Points Allowed by Position - Fantasy Edge IQ</title><meta name="description" content="Validated EuroLeague defense vs position table showing real points allowed to guards, forwards and centers."><link rel="canonical" href="{SITE}/euroleague/defense-vs-position"><meta name="robots" content="index,follow"><script defer src="/_vercel/insights/script.js"></script><style>{css}</style><link rel="icon" href="/favicon.svg" type="image/svg+xml"><link rel="apple-touch-icon" href="/apple-touch-icon.png"><link rel="manifest" href="/site.webmanifest"><meta name="theme-color" content="#07101d"><meta property="og:image" content="{SITE}/og-image.png"><meta name="twitter:card" content="summary_large_image"><meta name="twitter:image" content="{SITE}/og-image.png"></head><body><header><div class="topnav"><a class="brand" href="/">Fantasy Edge <span>IQ</span></a><nav class="navlinks"><a href="/euroleague">Dashboard</a><a href="/euroleague/team-analyzer">Lineup IQ</a><a href="/methodology">Methodology</a></nav></div><h1>EuroLeague Real Points Allowed by Position</h1><div class="sub">Validated table for how many real basketball points each team allows to guards, forwards and centers. No fantasy-point totals are shown here.</div></header><main><div class="note"><b>Important:</b> this page shows <b>real points only</b>. For every team, Guard PTS + Forward PTS + Center PTS is validated against the official box-score points allowed. The current sample is still early, so use it as context, not as a guarantee.</div><div class="downloads"><a class="btn" href="/euroleague-defense-vs-position.csv">Download real DvP CSV</a><a class="btn" href="/euroleague-defense-vs-position-matchlog.csv">Download validation matchlog</a><a class="btn" href="/euroleague">Back to EuroLeague dashboard</a></div><section class="cards"><div class="card"><h3>Real PTS allowed vs Guards</h3><div id="guardBox"></div></div><div class="card"><h3>Real PTS allowed vs Forwards</h3><div id="forwardBox"></div></div><div class="card"><h3>Real PTS allowed vs Centers</h3><div id="centerBox"></div></div></section><div class="downloads"><input id="q" placeholder="Search team..." oninput="render()"></div><div class="tablewrap"><table id="tbl"></table></div></main><script>const DATA={json.dumps(data,separators=(',',':'))};const COLS={json.dumps(cols,separators=(',',':'))};const LABELS={json.dumps(labels,separators=(',',':'))};let sort={{c:'guard_pts_allowed_pg',d:'desc'}};function fmt(v){{if(v===null||v===undefined)return ''; if(typeof v==='boolean')return v?'Yes':'No'; let n=Number(v); if(Number.isFinite(n))return Math.abs(n)>=100?String(Math.round(n*10)/10):String(Math.round(n*100)/100); return String(v)}}function cls(c,v){{if(c.includes('fdr')){{let n=Number(v);return n<=2.25?'good':n>=3.75?'bad':'warn'}} if(c==='validation_ok')return v?'good':'bad'; return ''}}function cmp(a,b,c){{let av=a[c],bv=b[c],an=Number(av),bn=Number(bv),r;if(av==null&&bv==null)r=0;else if(av==null)r=1;else if(bv==null)r=-1;else if(Number.isFinite(an)&&Number.isFinite(bn))r=an-bn;else r=String(av).localeCompare(String(bv));return sort.d==='asc'?r:-r}}function setSort(c){{sort={{c,d:sort.c===c&&sort.d==='desc'?'asc':'desc'}};render()}}function render(){{let rows=DATA.summary.filter(r=>!q.value||Object.values(r).join(' ').toLowerCase().includes(q.value.toLowerCase())).sort((a,b)=>cmp(a,b,sort.c));tbl.innerHTML='<thead><tr>'+COLS.map(c=>`<th onclick="setSort('${{c}}')">${{LABELS[c]||c}}${{sort.c===c?(sort.d==='asc'?' ↑':' ↓'):''}}</th>`).join('')+'</tr></thead><tbody>'+rows.map(r=>'<tr>'+COLS.map(c=>`<td class="${{cls(c,r[c])}}">${{fmt(r[c])}}</td>`).join('')+'</tr>').join('')+'</tbody>'}}function mini(id,col){{let rows=[...DATA.summary].sort((a,b)=>(Number(b[col])||0)-(Number(a[col])||0)).slice(0,6);document.getElementById(id).innerHTML=rows.map(r=>`<div class='row'><span>${{r.team_abbr}} <span class='mut'>${{r.team_name||''}}</span></span><b>${{fmt(r[col])}}</b></div>`).join('')}}mini('guardBox','guard_pts_allowed_pg');mini('forwardBox','forward_pts_allowed_pg');mini('centerBox','center_pts_allowed_pg');render();</script></body></html>'''
(OUT/'euroleague-defense-vs-position.html').write_text(html,encoding='utf-8')
print('written real-only DvP')
print(agg[['team_abbr','box_score_pts_allowed_pg','position_pts_allowed_pg','validation_diff_pg','guard_pts_allowed_pg','forward_pts_allowed_pg','center_pts_allowed_pg']].head(10).to_string(index=False))
