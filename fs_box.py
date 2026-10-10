"""Flashscore/Rezultati feed: statistika igraca (df_psn) i rezultat po cetvrtinama (df_sui)."""
import requests, re, datetime
FEED="https://14.flashscore.ninja/14/x/feed/"
HDR={"User-Agent":"Mozilla/5.0","x-fsign":"SW9D1eZo","Referer":"https://www.rezultati.com/"}
COLS=["pts","reb","ast","min","fgm","fga","m2","a2","m3","a3","ftm","fta","pm","oreb","dreb","pf","stl","tov","blk","blka","tech"]
def _get(feed,mid,retries=3):
    for i in range(retries):
        try:
            r=requests.get(f"{FEED}{feed}_1_{mid}",headers=HDR,timeout=30)
            if r.status_code==200: return r.text
        except Exception: pass
    return ""
def _i(v):
    v=(v or "").strip()
    if v in("","-"): return 0
    try: return int(float(v))
    except: return 0
def _min(v):
    v=(v or "").strip()
    if v in("","-"): return None
    if ":" in v:
        m,s=v.split(":")[:2]; return float(m)+float(s)/60.0
    try: return float(v)
    except: return None
def player_stats(mid):
    """Vraca {'teams':[ime1,ime2],'players':[dict...]} — igraci grupisani po sekciji (domaci prvi)."""
    t=_get("df_psn",mid)
    if not t: return {"teams":[],"players":[]}
    recs=t.split("¬~")
    teams=[]; players=[]; cur=None; first_section_done=False
    for r in recs:
        d=dict(kv.split("÷",1) for kv in r.split("¬") if "÷" in kv)
        if "PA" in d:
            cur=d["PA"]
            if cur!="Sve zajedno" and cur not in teams: teams.append(cur)
            continue
        if "PJ" in d and cur and cur!="Sve zajedno" and "PC" in d:
            vals=d["PC"].split("|")
            vals+=["-"]*(len(COLS)-len(vals))
            row=dict(zip(COLS,vals))
            players.append(dict(team=cur,name=d["PJ"],slug=d.get("PK",""),code=d.get("PN",""),
                minutes_raw=row["min"] if row["min"]!="-" else "",minutes=_min(row["min"]),
                **{k:_i(row[k]) for k in COLS if k!="min"}))
    # sekcije se ponavljaju (ukupno / po timu) — ukloni duplikate po (team,slug)
    seen=set(); out=[]
    for p in players:
        k=(p["team"],p["slug"] or p["name"])
        if k in seen: continue
        seen.add(k); out.append(p)
    return {"teams":teams,"players":out}
def quarters(mid):
    t=_get("df_sui",mid); q=[]
    for r in t.split("¬~"):
        d=dict(kv.split("÷",1) for kv in r.split("¬") if "÷" in kv)
        if "AC" in d and "IG" in d and re.match(r"^\d",d["AC"]):
            q.append((int(d["IG"]),int(d["IH"])))
    return q
if __name__=="__main__":
    import sys
    for mid in sys.argv[1:]:
        ps=player_stats(mid); print(mid,ps["teams"],len(ps["players"]),"igraca | cetvrtine:",quarters(mid))
        for tm in ps["teams"]:
            s=sum(p["pts"] for p in ps["players"] if p["team"]==tm); print("   ",tm,"zbir poena:",s,"| igraca:",sum(1 for p in ps["players"] if p["team"]==tm))
