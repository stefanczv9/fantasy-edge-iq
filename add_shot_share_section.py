#!/usr/bin/env python3
"""Shot Share = FGA/G igraca / FGA/G tima * 100 (samo tekuca sezona).

Dodaje u EN, SR i EL dashboard: tab + sekciju + tabelu (DATA.shotShareLeaders) i pise euroleague-shot-share.csv.
Idempotentno: moze se pokretati vise puta (sekcija se prepisuje, ne dupliра).
Pokretanje poslije add_minutes_and_pirmin_cards.py, prije finalize_euroleague_refresh.py.
"""
import re, json, math
from pathlib import Path
import pandas as pd, numpy as np

ROOT=Path(__file__).resolve().parent.parent
PAGES={"en":"euroleague-dashboard.html","sr":"sr-euroleague-dashboard.html","el":"el-euroleague-dashboard.html"}
COLS=["shot_share_rank","name","team_abbr","pos_short","price","player_fga_pg","team_fga_pg","shot_share_pct","minutes_per_game","pir_per_min_current","proj_pir_est","form_pir",
      "pir_avg_current","pts_avg_current","fg_attempts_per_min_current","fg_attempts_per40_current","fantasy_pts_current_md","value_pir_per_credit",
      "next5_fdr_1_easy_5_hard","next5_opponents","is_injured","started_from_bench","popularity_pct"]
NUM=["shot_share_rank","player_fga_pg","team_fga_pg","shot_share_pct"]
T={"en":dict(tab="Shot Share",h2="Player Shot Share",p="Share of the team's field-goal attempts taken by the player per game (current season only). Formula: player FGA/G ÷ team FGA/G × 100.",
             btn="Download shot share CSV",ph="Search shot share...",
             lab={"shot_share_rank":"Shot Share Rank","player_fga_pg":"Player FGA/G","team_fga_pg":"Team FGA/G","shot_share_pct":"Shot Share %"}),
   "sr":dict(tab="Shot Share",h2="Shot Share igrača",p="Udio šuteva iz igre cijelog tima koje igrač uzme po utakmici (samo tekuća sezona). Formula: FGA/G igrača ÷ FGA/G tima × 100.",
             btn="Preuzmi shot share CSV",ph="Pretraži shot share...",
             lab={"shot_share_rank":"Shot Share rang","player_fga_pg":"FGA/G igrača","team_fga_pg":"FGA/G tima","shot_share_pct":"Shot Share %"}),
   "el":dict(tab="Shot Share",h2="Shot Share παικτών",p="Ποσοστό των field-goal attempts του παίκτη σε σχέση με τα συνολικά field-goal attempts της ομάδας ανά αγώνα (μόνο τρέχουσα σεζόν). Formula: player FGA/G ÷ team FGA/G × 100.",
             btn="Download shot share CSV",ph="Αναζήτηση shot share...",
             lab={"shot_share_rank":"Shot Share Rank","player_fga_pg":"Player FGA/G","team_fga_pg":"Team FGA/G","shot_share_pct":"Shot Share %"})}

def compute():
    pf=pd.read_csv(ROOT/"euroleague-players-full.csv")
    d=pf[(pf["gp_current"].fillna(0)>0)&pf["fg_attempts_pg_current"].notna()&pf["team_fga_for_pg"].notna()&(pf["team_fga_for_pg"]>0)&(pf["min_avg_current"].fillna(0)>0)].copy()
    if "is_head_coach" in d.columns: d=d[~d["is_head_coach"].fillna(False).astype(bool)]
    if "pos_short" in d.columns: d=d[d["pos_short"].astype(str).str.upper()!="HC"]
    d["player_fga_pg"]=d["fg_attempts_pg_current"].astype(float).round(2)
    d["team_fga_pg"]=d["team_fga_for_pg"].astype(float).round(2)
    d["shot_share_pct"]=(d["player_fga_pg"]/d["team_fga_pg"]*100).round(1)
    d=d.sort_values(["shot_share_pct","player_fga_pg"],ascending=[False,False],kind="mergesort")
    d["shot_share_rank"]=d["shot_share_pct"].rank(method="min",ascending=False).astype(int)
    for c in COLS:
        if c not in d.columns: d[c]=np.nan
    return d[COLS].reset_index(drop=True)

def clean(v):
    if isinstance(v,(np.bool_,bool)): return bool(v)
    if isinstance(v,(np.integer,)): return int(v)
    if isinstance(v,(np.floating,float)): return None if (math.isnan(v) or math.isinf(v)) else float(v)
    return v
def extract_data(t):
    i=t.find("const DATA="); j=t.find("{",i); d=0; ins=False; esc=False; k=j
    while k<len(t):
        c=t[k]
        if ins:
            if esc: esc=False
            elif c=="\\": esc=True
            elif c=='"': ins=False
        else:
            if c=='"': ins=True
            elif c=="{": d+=1
            elif c=="}":
                d-=1
                if d==0: return json.loads(t[j:k+1]),j,k+1
        k+=1
    raise ValueError("DATA nije nadjen")

def patch(lg,rows):
    f=ROOT/PAGES[lg]; t=f.read_text(encoding="utf-8"); tx=T[lg]
    D,a,b=extract_data(t)
    D["shotShareLeaders"]=rows; D["shotShareCols"]=COLS; D["labels"].update(tx["lab"])
    t=t[:a]+json.dumps(D,ensure_ascii=False,separators=(",",":")).replace("</","<\\/")+t[b:]
    # --- tab dugme (poslije 'players')
    btn=f'<button class="tab" data-tab="shotshare">{tx["tab"]}</button>'
    t=re.sub(r'<button class="tab" data-tab="shotshare">.*?</button>','',t)
    t=re.sub(r'(<button class="tab" data-tab="players">.*?</button>)',lambda m:m.group(1)+btn,t,count=1)
    # --- sekcija (poslije sekcije players)
    sec=(f'<section id="shotshare" class="panel"><h2>{tx["h2"]}</h2><p class="mut">{tx["p"]}</p>'
         f'<div class="downloads"><a class="btn" href="/euroleague-shot-share.csv">{tx["btn"]}</a></div>'
         f'<div class="filters"><input id="shq" placeholder="{tx["ph"]}" oninput="renderShotShare()"></div>'
         f'<div class="tablewrap"><table id="shotShareTable"></table></div></section>')
    t=re.sub(r'<section id="shotshare" class="panel">.*?</section>\s*','',t,flags=re.S)
    m=re.search(r'<section id="players" class="panel[^"]*">.*?</section>',t,flags=re.S)
    assert m,"sekcija players nije nadjena"
    t=t[:m.end()]+" "+sec+t[m.end():]
    # --- JS
    if "function renderShotShare" not in t:
        t=t.replace("function renderTeams(){","function renderShotShare(){table('shotShareTable',DATA.shotShareLeaders.filter(r=>ftext(r,shq.value)),DATA.shotShareCols,'shotshare')}function renderTeams(){",1)
    if "id==='shotshare'" not in t:
        t=t.replace("if(id==='fullstats')renderFull();","if(id==='fullstats')renderFull(); if(id==='shotshare')renderShotShare();",1)
    if "sortState.shotshare" not in t:
        t=t.replace("sortState.full={c:'option_score_next5',d:'desc'};","sortState.full={c:'option_score_next5',d:'desc'};sortState.shotshare={c:'shot_share_pct',d:'desc'};",1)
    m=re.search(r"const numCols=new Set\(\[(.*?)\]\)",t,flags=re.S)
    if m:
        cur=m.group(1); add="".join(f",'{c}'" for c in NUM if f"'{c}'" not in cur)
        if add: t=t[:m.start(1)]+cur+add+t[m.end(1):]
    f.write_text(t,encoding="utf-8")
    return f.name

def main():
    d=compute()
    d.to_csv(ROOT/"euroleague-shot-share.csv",index=False)
    rows=[{k:clean(v) for k,v in r.items()} for r in d.to_dict("records")]
    for lg in PAGES: print("patched",patch(lg,rows))
    print(f"shot share: {len(d)} igraca | prvi: {d.iloc[0]['name']} {d.iloc[0]['team_abbr']} {d.iloc[0]['shot_share_pct']}% | csv: euroleague-shot-share.csv")

if __name__=="__main__": main()
