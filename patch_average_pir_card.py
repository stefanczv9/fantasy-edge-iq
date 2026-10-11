#!/usr/bin/env python3
"""Kartica 'Average PIR so far' umjesto 'Top Projected PIR' u EN, SR i EL dashboardu.

- vrijednost: pir_avg_current (prosjecan zvanicni PIR, SAMO tekuca sezona), prvih 12
- kvalifikacija: gp_current > 0 i najmanje pola odigranih utakmica (max(1, ceil(max_gp/2))), bez trenera (HC)
- 'Proj PIR' ostaje kolona u tabelama; mijenja se samo kartica na pocetnoj stranici
- pokrece se POSLIJE finalize_euroleague_refresh.py (finalize vraca naslov i mini() poziv na proj_pir_est)
- idempotentno; azurira i BUILD_VERSION.txt (finalize ga prepisuje)
"""
import re, json, math
from pathlib import Path
import pandas as pd, numpy as np

ROOT=Path(__file__).resolve().parent.parent
PAGES={ # fajl: (stari naslovi, novi naslov, podnaslov)
 "euroleague-dashboard.html":(["Top Projected PIR","Top option scores"],"Average PIR so far","Min. half of the games played"),
 "sr-euroleague-dashboard.html":(["Najviši Proj PIR","Najbolji option score"],"Prosječan PIR do sada","Min. pola odigranih utakmica"),
 "el-euroleague-dashboard.html":(["Κορυφαίο Proj PIR","Κορυφαία option scores"],"Μέσος PIR μέχρι τώρα","Ελάχιστο οι μισοί αγώνες"),
}
SUB='<div class="mut" style="font-size:12px;margin:-6px 0 8px">{}</div>'

def leaders():
    pf=pd.read_csv(ROOT/"euroleague-players-full.csv")
    d=pf[(pf["gp_current"].fillna(0)>0)&pf["pir_avg_current"].notna()].copy()
    if "pos_short" in d.columns: d=d[d["pos_short"].astype(str).str.upper()!="HC"]
    if "is_head_coach" in d.columns: d=d[~d["is_head_coach"].fillna(False).astype(bool)]
    max_gp=int(d["gp_current"].max()) if len(d) else 0
    min_gp=max(1,math.ceil(max_gp/2))
    d=d[d["gp_current"]>=min_gp]
    d=d.sort_values(["pir_avg_current","min_avg_current"],ascending=[False,False],kind="mergesort").head(12)
    rows=[]
    for r in d.to_dict("records"):
        rows.append({"name":r["name"],"team_abbr":r["team_abbr"],"pos_short":r.get("pos_short"),"gp_current":int(r["gp_current"]),
                     "min_avg_current":(None if pd.isna(r.get("min_avg_current")) else float(r["min_avg_current"])),"pir_avg_current":float(r["pir_avg_current"])})
    return rows,min_gp,max_gp

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

def patch(fname,olds,new,sub,rows):
    f=ROOT/fname; t=f.read_text(encoding="utf-8")
    D,a,b=extract_data(t); D["avgPirLeaders"]=rows
    t=t[:a]+json.dumps(D,ensure_ascii=False,separators=(",",":")).replace("</","<\\/")+t[b:]
    # --- kartica: <h3>naslov</h3> [podnaslov] <div id="topOptions|avgPirBox"></div>
    pat=re.compile(r'<h3>(?:%s)</h3>(?:<div class="mut"[^>]*>[^<]*</div>)?<div id="(?:topOptions|avgPirBox)"></div>'%"|".join(re.escape(x) for x in olds+[new]))
    t,n=pat.subn(f'<h3>{new}</h3>{SUB.format(sub)}<div id="avgPirBox"></div>',t,count=1)
    assert n==1,f"kartica nije nadjena u {fname}"
    # --- JS: izvor i vrijednost
    t,n=re.subn(r"mini\('(?:topOptions|avgPirBox)',DATA\.(?:topOptions|avgPirLeaders),'name','[a-z_]+','team_abbr'\)","mini('avgPirBox',DATA.avgPirLeaders,'name','pir_avg_current','team_abbr')",t,count=1)
    assert n==1,f"mini() poziv nije nadjen u {fname}"
    f.write_text(t,encoding="utf-8")
    return D.get("generated")

def build_version(stamp,min_gp,max_gp):
    p=ROOT/"BUILD_VERSION.txt"; old=p.read_text(encoding="utf-8").splitlines() if p.exists() else []
    dvp=next((l for l in old if l.startswith("DvP:")),"DvP: real-points-only by Guard/Forward/Center.")
    lines=["Fantasy Edge IQ EuroLeague auto-refresh",f"Generated: {stamp}",
           'Dashboard: current prices/next opponents; overview card "Average PIR so far" uses pir_avg_current (current season, min. half of the games); Proj PIR stays a table column.',dvp]
    if (ROOT/"euroleague-shot-share.csv").exists():
        lines.append("Shot Share: euroleague-shot-share.csv + tab in EN/SR/EL dashboards (current season, FGA/G divided by team FGA/G).")
    dom=ROOT/"euroleague-domestic-competitions.html"
    if dom.exists():
        try:
            D,_,_=extract_data(dom.read_text(encoding="utf-8"))
            lines.append(f"Domestic competitions: {len(D['games'])} completed games of 20 EuroLeague clubs in {len({g['country'] for g in D['games']})} countries, generated {D['generated']} (EN/SR/EL).")
        except Exception: pass
    lines.append("No EuroCup site routes/files included.")
    p.write_text("\n".join(lines)+"\n",encoding="utf-8")

def main():
    rows,min_gp,max_gp=leaders()
    stamp=None
    for fname,(olds,new,sub) in PAGES.items():
        stamp=patch(fname,olds,new,sub,rows) or stamp
        print(f"patched {fname}: '{new}' | prvi: {rows[0]['name']} {rows[0]['team_abbr']} {rows[0]['pir_avg_current']}")
    print(f"min. utakmica za kvalifikaciju: {min_gp} (max gp = {max_gp}) | u kartici: {len(rows)} igraca")
    build_version(stamp,min_gp,max_gp)
    print("BUILD_VERSION azuriran")

if __name__=="__main__": main()
