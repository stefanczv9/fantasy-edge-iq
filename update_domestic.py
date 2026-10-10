#!/usr/bin/env python3
"""Azuriranje rubrike 'Domestic Competitions' (EN/SR/EL) za 20 EuroLeague klubova.

Tok:
 1. ucita postojece domestic-*.csv (to je ono sto je na sajtu)
 2. preko Rezultati/Flashscore stranica takmicenja nadje SVE zavrsene domace utakmice (liga, kup, superkup) sezone 2026/27
 3. za utakmice kojih nema u CSV-u povuce box score (zvanicni: ACB, LBA, Israel BSL; ostalo Flashscore, procijenjen PIR)
 4. francuske utakmice koje su imale samo rezultat dobijaju game-level box score
 5. vremena (date_local) se normalizuju na Europe/Zagreb iz Flashscore epoch-a
 6. preracuna prosjeke, top liste, coverage, DATA JSON i regenerise tri HTML stranice
Pokretanje:  python3 scripts/domestic/update_domestic.py [--dry]
"""
import os, re, sys, json, math, datetime, unicodedata
from pathlib import Path
from zoneinfo import ZoneInfo
import pandas as pd, numpy as np

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
ROOT=HERE.parent.parent
import fs_scan as FS, sources as SRC, fs_box as FSB

TZ=ZoneInfo("Europe/Zagreb")
SEASON="2026-27"; SEASON_START=datetime.datetime(2026,9,1,tzinfo=datetime.UTC)
EL=["ASV","BAR","BAY","BJK","CZV","DUB","EFS","FBT","HTA","KBA","MIL","MTA","OLY","PAO","PAR","PBB","RMB","VBC","VIR","ZAL"]
EL_NAME={"ASV":"ASVEL","BAR":"Barça","BAY":"FC Bayern Munich","BJK":"Beşiktaş","CZV":"Crvena zvezda Meridianbet","DUB":"Dubai Basketball","EFS":"Anadolu Efes",
 "FBT":"Fenerbahçe","HTA":"Hapoel IBI Tel Aviv","KBA":"Kosner Baskonia","MIL":"Armani Olimpia Milano","MTA":"Maccabi Rapyd Tel Aviv","OLY":"Olympiacos",
 "PAO":"Panathinaikos AKTOR","PAR":"Partizan Mozzart Bet","PBB":"Paris Basketball","RMB":"Real Madrid","VBC":"Valencia Basket","VIR":"Virtus Costa Bologna","ZAL":"Žalgiris"}
EL_FULL={"ASV":"ASVEL","BAR":"Barça","BAY":"FC Bayern Munich","BJK":"Beşiktaş","CZV":"Crvena zvezda Meridianbet","DUB":"Dubai Basketball","EFS":"Anadolu Efes","FBT":"Fenerbahçe",
 "HTA":"Hapoel IBI Tel Aviv","KBA":"Kosner Baskonia","MIL":"Armani Olimpia Milano","MTA":"Maccabi Rapyd Tel Aviv","OLY":"Olympiacos","PAO":"Panathinaikos AKTOR",
 "PAR":"Partizan Mozzart Bet","PBB":"Paris Basketball","RMB":"Real Madrid","VBC":"Valencia Basket","VIR":"Virtus Costa Bologna","ZAL":"Žalgiris"}
# neEL protivnici: Flashscore ime -> (kod, naziv). Kodovi se ne smiju sudarati sa vec koristenim (VER=Verona, NAN=Nancy ...)
OPP={"Roanne":("ROA","Chorale Roanne"),"Nanterre":("NNT","Nanterre 92"),"Bamberg":("BAM","Bamberg Baskets"),"Alba Berlin":("ALB","ALBA Berlin"),
     "Joventut":("JOV","Asisa Joventut"),"Venezia":("VEN","Umana Reyer Venezia"),"Oldenburg":("OLD","EWE Baskets Oldenburg"),"Nancy":("NAN","Nancy"),
     "Cholet":("CHO","Cholet"),"Gravelines-Dunkerque":("GRA","Gravelines-Dunkerque"),"Le Mans":("MSB","Le Mans Sarthe"),"Bahcesehir Kol.":("BKS","Bahçeşehir Koleji"),
     "Trabzonspor":("TRB","Trabzonspor"),"Korfez Basket":("KOR","Körfez Basket"),"Bordo Bandirma":("BOR","Bordo Bandırma")}
COMP={ # kljuc iz fs_scan.COMPS -> (country, league, competition)
 "ESP ACB":("Spain","ACB","Liga Endesa"),"ESP Supercopa":("Spain","ACB","Supercopa Endesa"),
 "ITA LBA":("Italy","LBA","LBA Serie A"),"ITA Supercoppa":("Italy","LBA","Supercoppa LBA"),
 "GRE GBL":("Greece","GBL","Stoiximan GBL"),"GRE SuperCup":("Greece","GBL","Stoiximan Super Cup"),
 "TUR BSL":("Turkey","BSL","Türkiye Sigorta BSL"),"TUR SuperCup":("Turkey","BSL","Presidential Cup"),
 "FRA LNB":("France","Betclic Elite","Betclic Elite"),"FRA SuperCup":("France","Betclic Elite","LNB Supercup"),
 "GER BBL":("Germany","BBL","easyCredit BBL"),
 "LTU LKL":("Lithuania","LKL","LKL"),
 "ISR SuperCup":("Israel","IBSL","Winner Supercup"),"ISR LeagueCup":("Israel","IBSL","Winner Cup"),
 "EUR ABA":("Regional","ABA","AdmiralBet ABA League"),"EUR ABA2":("Regional","ABA","AdmiralBet ABA League")}
PHASE={"Polufinale":("Semifinal","SF"),"Finale":("Final","Final"),"Četvrtfinale":("Quarterfinal","QF")}
GAME_COLS=["country","league","competition","season","phase","round","game_id","date_local","venue","home_team","home_abbr","away_team","away_abbr","home_score","away_score",
 "q1_home","q1_away","q2_home","q2_away","q3_home","q3_away","q4_home","q4_away","status","source_quality","source_note","source_url"]
BOX_COLS=["country","league","competition","season","phase","round","game_id","date_local","status","source_quality","source_note","source_url","team_abbr","team_name","opponent_abbr","opponent_name",
 "home_away","team_score","opponent_score","player","is_total","is_team_bench","pts","reb","dreb","oreb","ast","blk","blka","fouls_drawn","fouls_committed","stl","tov","minutes_raw","minutes","rank",
 "two_made","two_att","three_made","three_att","ft_made","ft_att","fg_made","fg_att","fg_pct","fga_per_min","rank_per_min"]
AVG_COLS=["country","league","team_abbr","team_name","player","games_played","rank_games","avg_minutes","avg_pir","avg_pts","avg_reb","avg_ast","avg_fg_att","avg_fga_per_min","avg_pir_per_min","last_game_date"]
NOTE={"acb":"{comp} final official ACB Live box score.","lba":"Official LBA game page JSON/tabellini.",
 "ibsl":"Official IBSL box score. Cup and Super Cup rows are marked separately from regular-season league games.",
 "fs_tur":"Rezultati.com/Flashscore final/player stats used because official TBF/BSL public box score was unavailable; PIR/RANK is estimated from available player stats (fouls omitted).",
 "fs_fra":"Final score verified; game-level player stats from Rezultati.com/Flashscore because the official LNB box score is not publicly accessible. PIR/RANK is estimated (fouls omitted).",
 "fs_ger":"Rezultati.com/Flashscore final/player stats used because the official easyCredit BBL box score was not accessible. PIR/RANK is estimated (fouls omitted).",
 "fs":"Rezultati.com/Flashscore final/player stats; PIR/RANK is estimated from available player stats (fouls omitted)."}

def norm(s):
    s=unicodedata.normalize("NFKD",str(s or "")).replace("ı","i").replace("İ","I")
    return re.sub(r"[^a-z0-9 ]"," ",s.encode("ascii","ignore").decode().lower()).split()
def zagreb(epoch):
    return datetime.datetime.fromtimestamp(int(epoch),datetime.UTC).astimezone(TZ).strftime("%Y-%m-%d %H:%M")
def abbr_for(fs_name, fs_code):
    if fs_code: return fs_code, EL_NAME[fs_code]
    if fs_name in OPP: return OPP[fs_name]
    return (re.sub(r"[^A-Z]","",fs_name.upper())[:3] or "UNK"), fs_name

def resolve_name(short, slug, known):
    """'Dada Fodzo M. O.' + '/igrac/dada-fodzo-marc-owen/ID/' -> 'Marc-Owen Fodzo Dada'.
    1) trazi poklapanje u vec postojecim imenima tima (prezime + pocetno slovo), 2) inace rekonstruise iz slug-a."""
    parts=str(short).split()
    inits=[]
    while len(parts)>1 and re.fullmatch(r"[A-Za-zÀ-ž]\.?(-[A-Za-zÀ-ž]\.?)?",parts[-1]):
        inits.insert(0,parts.pop())
    sur=norm(" ".join(parts)); init=norm(inits[0])[0] if inits and norm(inits[0]) else ""
    best=None
    for k in known:
        kt=norm(k)
        if not sur or not set(sur)<=set(kt): continue
        extra=[t for t in kt if t not in sur]
        ok=(not extra) or (init and (extra[0][0]==init or kt[0][0]==init))
        if ok and (best is None or len(kt)<len(norm(best))): best=k
    if best: return best
    m=re.search(r"/igrac/([^/]+)/",slug or "")
    if m:
        st=m.group(1).split("-"); n=len(sur)
        given=st[n:]
        if given: return " ".join(t.capitalize() for t in given)+" "+" ".join(t.capitalize() for t in st[:n])
    if inits:   # nerazrijesen skraceni oblik -> 'D. Boungou-Colo'
        return " ".join(i if i.endswith(".") else i+"." for i in inits)+" "+" ".join(parts)
    return str(short)

def rowfix(v):
    return None if (v is None or (isinstance(v,float) and math.isnan(v))) else v

def build_rows(game, box, el_only=True, known_names=None):
    """game: dict (GAME_COLS vrijednosti), box: adapter rezultat. Vraca (player_rows, total_rows)."""
    prow=[]; trow=[]
    sides={"H":(game["home_abbr"],game["home_team"],game["away_abbr"],game["away_team"],int(game["home_score"]),int(game["away_score"])),
           "A":(game["away_abbr"],game["away_team"],game["home_abbr"],game["home_team"],int(game["away_score"]),int(game["home_score"]))}
    base={k:game[k] for k in ["country","league","competition","season","phase","round","game_id","date_local","status","source_quality","source_note","source_url"]}
    for side,(ta,tn,oa,on,ts,os_) in sides.items():
        if el_only and ta not in EL: continue
        pl=[p for p in box["players"] if p["team"]==side]
        if not pl: continue
        known=(known_names or {}).get(ta,[])
        tot=dict(pts=0,reb=0,dreb=0,oreb=0,ast=0,blk=0,blka=0,fd=0,pf=0,stl=0,tov=0,rank=0,m2=0,a2=0,m3=0,a3=0,ftm=0,fta=0); fd_any=False
        for p in pl:
            name=p["name"]
            if p.get("slug") is not None: name=resolve_name(p["name"],p.get("slug",""),known)
            fgm=p["m2"]+p["m3"]; fga=p["a2"]+p["a3"]; mins=p["minutes"]
            rk=p["rank"]
            r=dict(base); r.update(team_abbr=ta,team_name=tn,opponent_abbr=oa,opponent_name=on,home_away=side,team_score=ts,opponent_score=os_,player=name,is_total=False,is_team_bench=False,
              pts=float(p["pts"]),reb=float(p["reb"]),dreb=float(p["dreb"]),oreb=float(p["oreb"]),ast=float(p["ast"]),blk=float(p["blk"]),blka=float(p["blka"]),
              fouls_drawn=(float(p["fd"]) if p["fd"] is not None else np.nan),fouls_committed=float(p["pf"]),stl=float(p["stl"]),tov=float(p["tov"]),
              minutes_raw=p["minutes_raw"] or ("00:00" if mins is None else ""),minutes=(round(mins,6) if mins is not None else 0.0),rank=float(rk),
              two_made=float(p["m2"]),two_att=float(p["a2"]),three_made=float(p["m3"]),three_att=float(p["a3"]),ft_made=float(p["ftm"]),ft_att=float(p["fta"]),
              fg_made=float(fgm),fg_att=float(fga),fg_pct=(round(fgm/fga*100,1) if fga>0 else np.nan),
              fga_per_min=(round(fga/mins,3) if (fga>0 and mins) else np.nan),rank_per_min=(round(rk/mins,3) if mins else (0.0 if rk==0 else np.nan)))
            prow.append(r)
            for k,src in [("pts","pts"),("reb","reb"),("dreb","dreb"),("oreb","oreb"),("ast","ast"),("blk","blk"),("blka","blka"),("pf","pf"),("stl","stl"),("tov","tov"),("rank","rank"),
                          ("m2","m2"),("a2","a2"),("m3","m3"),("a3","a3"),("ftm","ftm"),("fta","fta")]: tot[k]+=p[src]
            if p["fd"] is not None: tot["fd"]+=p["fd"]; fd_any=True
        fgm=tot["m2"]+tot["m3"]; fga=tot["a2"]+tot["a3"]
        t=dict(base); t.update(team_abbr=ta,team_name=tn,opponent_abbr=oa,opponent_name=on,home_away=side,team_score=ts,opponent_score=os_,player="TOTAL",is_total=True,is_team_bench=False,
          pts=float(tot["pts"]),reb=float(tot["reb"]),dreb=float(tot["dreb"]),oreb=float(tot["oreb"]),ast=float(tot["ast"]),blk=float(tot["blk"]),blka=float(tot["blka"]),
          fouls_drawn=(float(tot["fd"]) if fd_any else np.nan),fouls_committed=float(tot["pf"]),stl=float(tot["stl"]),tov=float(tot["tov"]),minutes_raw=np.nan,minutes=np.nan,rank=float(tot["rank"]),
          two_made=float(tot["m2"]),two_att=float(tot["a2"]),three_made=float(tot["m3"]),three_att=float(tot["a3"]),ft_made=float(tot["ftm"]),ft_att=float(tot["fta"]),
          fg_made=float(fgm),fg_att=float(fga),fg_pct=(round(fgm/fga*100,1) if fga>0 else np.nan),fga_per_min=np.nan,rank_per_min=np.nan)
        trow.append(t)
    return prow,trow

def recompute_averages(rows, teams):
    """Prosjeci iz redova igraca (ista formula kao postojeci: omjer prosjeka)."""
    df=rows[(rows["team_abbr"].isin(teams))&(~rows["is_total"].astype(bool))]
    out=[]
    for (c,l,ta,tn,pl),g in df.groupby(["country","league","team_abbr","team_name","player"],dropna=False,sort=False):
        mins=g["minutes"].astype(float); am=mins.mean(); ap=g["rank"].astype(float).mean(); fga=g["fg_att"].astype(float).mean()
        out.append(dict(country=c,league=l,team_abbr=ta,team_name=tn,player=pl,games_played=int(g["game_id"].nunique()),rank_games=int(g["rank"].notna().sum()),
          avg_minutes=round(am,2),avg_pir=round(ap,2),avg_pts=round(g["pts"].astype(float).mean(),2),avg_reb=round(g["reb"].astype(float).mean(),2),avg_ast=round(g["ast"].astype(float).mean(),2),
          avg_fg_att=round(fga,2),avg_fga_per_min=round(fga/am,3) if am else np.nan,avg_pir_per_min=round(ap/am,3) if am else np.nan,last_game_date=g["date_local"].astype(str).max()))
    return pd.DataFrame(out,columns=AVG_COLS)

# --------------------------------------------------------------------------------------------------- otkrivanje
def fs_records():
    recs={}
    for key,path in FS.COMPS.items():
        if key not in COMP: continue
        title,rows=FS.parse(f"https://www.rezultati.com/kosarka/{path}/rezultati/")
        for d in rows or []:
            a=FS.which(d.get("WU")); b=FS.which(d.get("WV"))
            if not(a or b) or d.get("AB")!="3": continue
            ts=int(d.get("AD","0")); dt=datetime.datetime.fromtimestamp(ts,datetime.UTC)
            if dt<SEASON_START: continue
            if d["mid"] in recs: continue
            recs[d["mid"]]=dict(mid=d["mid"],key=key,epoch=ts,rnd=d.get("ER",""),home=d.get("AE"),away=d.get("AF"),hs=int(d["AG"]),as_=int(d["AH"]),ha=a,aa=b,
                                wu=d.get("WU"),wv=d.get("WV"),ja=d.get("JA"),jb=d.get("JB"))
    return recs

def match_baseline(g, recs):
    """g: red iz domestic-games (EL). Vraca FS zapis po skoru + datumu (+-1 dan) + EL kodu."""
    try: d0=datetime.datetime.strptime(str(g["date_local"])[:10],"%Y-%m-%d")
    except Exception: return None
    for r in recs.values():
        if r["hs"]!=int(g["home_score"]) or r["as_"]!=int(g["away_score"]): continue
        if abs((datetime.datetime.fromtimestamp(r["epoch"],datetime.UTC).replace(tzinfo=None)-d0).days)>1: continue
        codes={r["ha"],r["aa"]}-{None}
        if codes & {g["home_abbr"],g["away_abbr"]}: return r
    return None

def fs_url(r):
    return f"https://www.rezultati.com/utakmica/kosarka/{r['wu']}-{r['ja']}/{r['wv']}-{r['jb']}/detalji/statistika-igraca/ukupno/?mid={r['mid']}"

_cache={}
def official_box(r):
    """Pokusa zvanicni izvor za novu utakmicu; vraca (box, quality, note, url, venue, game_id) ili None."""
    key=r["key"]
    names=norm(r["home"])+norm(r["away"])
    if key=="ESP Supercopa" or key=="ESP ACB":
        links=_cache.setdefault("acb",SRC.acb_supercopa_links() if key=="ESP Supercopa" else [])
        for u in links:
            slug=u.split("/partidos/")[1].split("/")[0]
            h,_,a=slug.rpartition("-vs-"); a=re.sub(r"-\d+$","",a)
            ALIAS={"barcelona":"barca","kosner":"baskonia"}
            tk=lambda n:{ALIAS.get(x,x) for x in norm(n)}|set(norm(n))
            if (tk(r["home"])&set(norm(h.replace("-"," ")))) and (tk(r["away"])&set(norm(a.replace("-"," ")))):
                b=SRC.acb_box(u)
                if b:
                    hs=sum(p["pts"] for p in b["players"] if p["team"]=="H"); as_=sum(p["pts"] for p in b["players"] if p["team"]=="A")
                    if (hs,as_)==(r["hs"],r["as_"]):
                        gid=re.search(r"-(\d+)/",u).group(1)
                        return b,"official_boxscore",NOTE["acb"].format(comp=COMP[key][2]),u,None,f"ACB-{gid}"
    if key in("ITA Supercoppa","ITA LBA"):
        idx=_cache.setdefault("lba",SRC.lba_index())
        for gid,(dt,h,a,hs,vs,comp) in idx.items():
            if (hs,vs)==(r["hs"],r["as_"]) and abs(datetime.datetime.fromisoformat(dt).timestamp()-r["epoch"])<86400:
                b=SRC.lba_box(gid)
                if b:
                    u=f"https://www.legabasket.it/game/{gid}/x/tabellini"
                    return b,"official_boxscore",NOTE["lba"],u,b["meta"].get("venue"),f"LBA-{gid}"
    if key in("ISR SuperCup","ISR LeagueCup"):
        board={"ISR SuperCup":34,"ISR LeagueCup":10}[key]
        rr=SRC.get("https://basket.co.il/results.asp",params={"cYear":2027,"Board":board,"RoundNumber":0,"TeamId":0,"lang":"en"})
        if rr is not None:
            for gid in sorted(set(re.findall(r"game-zone\.asp\?GameId=(\d+)",rr.text))):
                b=SRC.ibsl_box(gid)
                if b and (sum(p["pts"] for p in b["players"] if p["team"]=="H"),sum(p["pts"] for p in b["players"] if p["team"]=="A"))==(r["hs"],r["as_"]):
                    for k in("home_name","away_name"): b[k]=re.sub(r"\s*\(.*?\)\s*$","",b[k] or "")
                    return b,"official_boxscore",NOTE["ibsl"],f"https://basket.co.il/game-zone.asp?GameId={gid}&lang=en",None,f"ISR-{gid}"
    return None

def main(dry=False):
    now=datetime.datetime.now(TZ); stamp=now.strftime("%Y-%m-%d %H:%M ")+("CEST" if now.dst() else "CET")
    games=pd.read_csv(ROOT/"domestic-games.csv",dtype={"round":str}); box=pd.read_csv(ROOT/"domestic-player-boxscores.csv",dtype={"round":str})
    tot=pd.read_csv(ROOT/"domestic-team-boxscores.csv",dtype={"round":str}); avg=pd.read_csv(ROOT/"domestic-player-averages.csv")
    print(f"baza: {len(games)} utakmica | {len(box)} redova igraca | {len(tot)} totala | {len(avg)} prosjeka")
    recs=fs_records(); print(f"Flashscore: {len(recs)} zavrsenih domacih utakmica EL klubova (sezona {SEASON})")
    is_el=lambda r: r["home_abbr"] in EL or r["away_abbr"] in EL
    # --- 1) sta vec imamo
    matched={}                                          # game_id -> fs zapis
    for _,g in games[games.apply(is_el,axis=1)].iterrows():
        r=match_baseline(g,recs)
        if r: matched[g["game_id"]]=r
    used={r["mid"] for r in matched.values()}
    new=[r for r in sorted(recs.values(),key=lambda x:x["epoch"]) if r["mid"] not in used]
    print(f"vec u bazi: {len(used)} | nove: {len(new)}")
    known={ta:sorted(set(box[box["team_abbr"]==ta]["player"])|set(avg[avg["team_abbr"]==ta]["player"])) for ta in EL}
    new_games=[]; new_box=[]; new_tot=[]; log=[]
    for r in new:
        country,league,comp=COMP[r["key"]]
        ph,rd=PHASE.get(r["rnd"],("Regular Season",None))
        if rd is None:
            m=re.match(r"(\d+)\.",r["rnd"]); rd=f"{int(m.group(1)):02d}" if m else ""
        ha,hn=abbr_for(r["home"],r["ha"]); aa,an=abbr_for(r["away"],r["aa"])
        ob=official_box(r) if r["key"] in("ESP Supercopa","ESP ACB","ITA Supercoppa","ITA LBA","ISR SuperCup","ISR LeagueCup") else None
        if ob:
            b,q,note,url,venue,gid=ob
            if r["key"].startswith(("ESP","ITA")) : ha,hn=(r["ha"],EL_NAME[r["ha"]]) if r["ha"] else (ha,b["home_name"] or hn); aa,an=(r["aa"],EL_NAME[r["aa"]]) if r["aa"] else (aa,b["away_name"] or an)
            if r["key"]=="ISR SuperCup": ha,hn,aa,an=r["ha"],EL_NAME[r["ha"]],r["aa"],EL_NAME[r["aa"]]
        else:
            b=SRC.fs_boxscore(r["mid"]); q="third_party_boxscore_est_pir"; url=fs_url(r); venue=None
            note={"TUR":NOTE["fs_tur"],"FRA":NOTE["fs_fra"],"GER":NOTE["fs_ger"]}.get(r["key"][:3],NOTE["fs"]); gid=f"{ {'TUR':'BSL','FRA':'FRA-FS','GER':'BBL'}.get(r['key'][:3],'FS') }-{r['mid']}"
        if not b: log.append(f"!! nema box score: {r}"); continue
        qs=(b.get("meta",{}).get("q") or [])
        if len(qs)<4 or any(x is None for t in qs for x in t): qs=FSB.quarters(r["mid"])
        if r["key"]=="GER BBL" and r["rnd"].startswith("23"): note+=" Round 23 fixture played early (rescheduled)."
        g=dict(country=country,league=league,competition=comp,season=SEASON,phase=ph,round=rd,game_id=gid,date_local=zagreb(r["epoch"]),venue=venue,home_team=hn,home_abbr=ha,away_team=an if False else None,away_abbr=aa)
        g.update(away_team=an,home_score=r["hs"],away_score=r["as_"],status="played",source_quality=q,source_note=note,source_url=url)
        for i in range(4):
            g[f"q{i+1}_home"]=float(qs[i][0]) if i<len(qs) else np.nan; g[f"q{i+1}_away"]=float(qs[i][1]) if i<len(qs) else np.nan
        pr,tr=build_rows(g,b,known_names=known)
        new_games.append(g); new_box+=pr; new_tot+=tr
        log.append(f"+ {g['date_local']} {league:13s} {comp:22s} {ha} {r['hs']}-{r['as_']} {aa} | {q} | igraca EL strane: {len(pr)}")
    # --- 2) francuske utakmice koje su imale samo rezultat -> game-level box score
    upgrade=0
    for _,g in games[games.apply(is_el,axis=1)].iterrows():
        if g["source_quality"]!="official_result_average_only" or g["game_id"] not in matched: continue
        r=matched[g["game_id"]]; b=SRC.fs_boxscore(r["mid"])
        if not b: continue
        gd=g.to_dict(); gd["source_quality"]="third_party_boxscore_est_pir"; gd["source_note"]=NOTE["fs_fra"]
        qs=b["meta"]["q"]
        for i in range(4):
            if i<len(qs): gd[f"q{i+1}_home"]=float(qs[i][0]); gd[f"q{i+1}_away"]=float(qs[i][1])
        pr,tr=build_rows(gd,b,known_names=known)
        games.loc[games["game_id"]==g["game_id"],["source_quality","source_note"]+[f"q{i}_{s}" for i in (1,2,3,4) for s in ("home","away")]]=[gd["source_quality"],gd["source_note"]]+[gd[f"q{i}_{s}"] for i in (1,2,3,4) for s in ("home","away")]
        new_box+=pr; new_tot+=tr; upgrade+=1; log.append(f"^ nadogradnja {g['date_local'][:10]} {g['home_abbr']} {g['home_score']}-{g['away_score']} {g['away_abbr']}: {len(pr)} redova igraca")
    print("\n".join(log))
    if dry: print("--dry: nista nije upisano"); return
    # --- 3) spoji
    games=pd.concat([games,pd.DataFrame(new_games)],ignore_index=True)[GAME_COLS]
    box=pd.concat([box,pd.DataFrame(new_box)],ignore_index=True)[BOX_COLS]; tot=pd.concat([tot,pd.DataFrame(new_tot)],ignore_index=True)[BOX_COLS]
    # --- 4) vremena: Europe/Zagreb iz Flashscore epoch-a
    allmatch=dict(matched); 
    for r in new:
        for gg in new_games:
            if gg["home_score"]==r["hs"] and gg["away_score"]==r["as_"] and gg["date_local"]==zagreb(r["epoch"]): allmatch[gg["game_id"]]=r
    for gid,r in allmatch.items():
        d=zagreb(r["epoch"])
        for df in (games,box,tot): df.loc[df["game_id"]==gid,"date_local"]=d
    # --- 5) prosjeci: preracunaj za timove sa izmjenama
    changed=sorted({p["team_abbr"] for p in new_box}); print("preracunati prosjeci za:",changed)
    box_for_avg=box.copy()
    newavg=recompute_averages(box_for_avg,changed)
    avg=pd.concat([avg[~avg["team_abbr"].isin(changed)],newavg],ignore_index=True)[AVG_COLS]
    games=games.sort_values(["date_local","league","game_id"],kind="mergesort").reset_index(drop=True)
    box=box.sort_values(["date_local","game_id","team_abbr"],kind="mergesort",ignore_index=True) if False else box
    games.to_csv(ROOT/"domestic-games.csv",index=False); box.to_csv(ROOT/"domestic-player-boxscores.csv",index=False)
    tot.to_csv(ROOT/"domestic-team-boxscores.csv",index=False); avg.to_csv(ROOT/"domestic-player-averages.csv",index=False)
    print(f"upisano: {len(games)} utakmica | {len(box)} redova igraca | {len(tot)} totala | {len(avg)} prosjeka")
    try:
        Path("/tmp/dom").mkdir(parents=True,exist_ok=True)
        json.dump({"stamp":stamp,"new_games":len(new_games),"upgraded":upgrade},open("/tmp/dom/last_run.json","w"))
    except OSError: pass

if __name__=="__main__":
    main(dry="--dry" in sys.argv)
