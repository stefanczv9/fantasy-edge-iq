#!/usr/bin/env python3
"""Azuriranje rubrike 'Domestic Competitions' (EN/SR/EL) za 20 EuroLeague i 32 EuroCup kluba.

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
EC=["ARI","BKS","BLK","BOS","BUD","BUR","CHE","COL","DER","JLB","JLM","LDN","LIE","LLT","MAN","MSB","NAP","NEP","PBC","RIG","RMA","ROM","ROS","SIA","SKY","TOF","TRE","TTA","UBT","ULM","URV","WKS"]
EC_NAME={"ARI":"Aris Betsson","BKS":"Bahçeşehir Koleji","BLK":"Balkan Botevgrad","BOS":"Bosna BH Telecom","BUD":"Budućnost VOLI","BUR":"Recoletas Salud San Pablo Burgos",
 "CHE":"NINERS Chemnitz","COL":"Cedevita Olimpija","DER":"Bertram Derthona Tortona","JLB":"Bourg-en-Bresse","JLM":"Hapoel Midtown Jerusalem","LDN":"London Lions",
 "LIE":"Lietkabelis","LLT":"La Laguna Tenerife","MAN":"Kids&Us Manresa","MSB":"Le Mans","NAP":"Napoli Basketball","NEP":"Neptūnas","PBC":"PAOK","RIG":"Rigas Zelli",
 "RMA":"Maxima Roma","ROM":"BC Roma","ROS":"Rostock Seawolves","SIA":"Šiauliai","SKY":"SKYLINERS Frankfurt","TOF":"Tofas Bursa","TRE":"Dolomiti Energia Trentino",
 "TTA":"Turk Telekom","UBT":"U-BT Cluj-Napoca","ULM":"ratiopharm Ulm","URV":"Umana Reyer Venezia","WKS":"Śląsk Wrocław"}
TARGET=EL+EC; NAMES={**EL_NAME,**EC_NAME}
# stari/sporedni kodovi -> kanonski (isti klub, dva koda): VEN->URV (Reyer Venezia je EuroCup klub), RNA->REG (UNA Hotels Reggio Emilia)
ALIAS={"VEN":"URV","RNA":"REG"}
def apply_alias(df, cols):
    for c in cols:
        if c in df.columns: df[c]=df[c].replace(ALIAS)
    return df
# neEL protivnici: Flashscore ime -> (kod, naziv). Kodovi se ne smiju sudarati sa vec koristenim (VER=Verona, NAN=Nancy ...)
OPP={"Roanne":("ROA","Chorale Roanne"),"Nanterre":("NNT","Nanterre 92"),"Bamberg":("BAM","Bamberg Baskets"),"Alba Berlin":("ALB","ALBA Berlin"),
     "Joventut":("JOV","Asisa Joventut"),"Oldenburg":("OLD","EWE Baskets Oldenburg"),"Nancy":("NAN","Nancy"),
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
 "EUR ABA":("Regional","ABA","AdmiralBet ABA League"),"EUR ABA2":("Regional","ABA","AdmiralBet ABA League"),
 "ISR SuperLeague":("Israel","IBSL","Winner League"),
 "POL PLK":("Poland","PLK","Orlen Basket Liga"),"POL SuperCup":("Poland","PLK","Polish Super Cup"),"POL Cup":("Poland","PLK","Polish Cup"),
 "GBR SLB":("United Kingdom","SLB","Super League Basketball"),"GBR SLBCup":("United Kingdom","SLB","SLB Cup"),
 "LAT-EST LEBL":("Latvia/Estonia","Lat-Est BL","Latvian-Estonian Basketball League"),
 "BUL NBL":("Bulgaria","NBL","NBL"),"BUL SuperCup":("Bulgaria","Super Cup","Bulgarian Super Cup"),"BUL Cup":("Bulgaria","NBL","Bulgarian Cup"),
 "SLO Liga":("Slovenia","Liga OTP banka","Liga OTP banka"),"SLO Cup":("Slovenia","Liga OTP banka","Slovenian Cup"),"SLO SuperCup":("Slovenia","Liga OTP banka","Slovenian Super Cup"),
 "ROU Divizia":("Romania","Divizia A","Liga Națională"),"ROU Cup":("Romania","Divizia A","Romanian Cup"),"ROU SuperCup":("Romania","Divizia A","Romanian Super Cup"),
 "MNE Prva":("Montenegro","Prva A liga","Prva A liga")}
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
class CodeBook:
    """Kodovi protivnika. Prvo postojeci kod iz baze (po imenu), zatim OPP, na kraju novi kod koji se ne sudara ni sa cim."""
    def __init__(self, games):
        self.rows=[]; self.used=set(TARGET)|{v[0] for v in OPP.values()}; self.new={}
        for _,g in games.iterrows():
            for ab,nm in ((g["home_abbr"],g["home_team"]),(g["away_abbr"],g["away_team"])):
                if ab in NAMES or not isinstance(ab,str): continue
                self.rows.append((frozenset(norm(nm)),ab,str(nm))); self.used.add(ab)
    def lookup(self, fs_name):
        if fs_name in OPP: return OPP[fs_name]
        if fs_name in self.new: return self.new[fs_name]
        toks=set(norm(fs_name)); best=None; bs=0
        for ts,ab,nm in self.rows:
            if not toks or not ts: continue
            inter=toks&ts
            if not inter or not any(len(x)>=4 for x in inter): continue
            if toks<=ts or ts<=toks:
                s=len(inter)/len(toks|ts)
                if s>bs: best,bs=(ab,nm),s
        if best: return best
        words=[w for w in re.sub(r"[^A-Za-z ]","",unicodedata.normalize("NFKD",fs_name).encode("ascii","ignore").decode()).upper().split() if w]
        cands=[]
        if words:
            w0=words[0]; cands+=[w0[:3],(w0[:2]+words[-1][0]) if len(words)>1 else "",("".join(x[0] for x in words))[:3],w0[0]+w0[-2:],w0[:1]+w0[2:4]]
        for c in cands:
            if len(c)==3 and c not in self.used:
                self.used.add(c); self.new[fs_name]=(c,fs_name); return self.new[fs_name]
        for i in range(10,100):
            c=(words[0][:1] if words else "X")+str(i)
            if c not in self.used: self.used.add(c); self.new[fs_name]=(c,fs_name); return self.new[fs_name]
def abbr_for(fs_name, fs_code, book=None):
    if fs_code: return fs_code, NAMES[fs_code]
    if book is not None: return book.lookup(fs_name)
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

def build_rows(game, box, targets=None, known_names=None):
    """game: dict (GAME_COLS vrijednosti), box: adapter rezultat. Vraca (player_rows, total_rows)."""
    prow=[]; trow=[]
    sides={"H":(game["home_abbr"],game["home_team"],game["away_abbr"],game["away_team"],int(game["home_score"]),int(game["away_score"])),
           "A":(game["away_abbr"],game["away_team"],game["home_abbr"],game["home_team"],int(game["away_score"]),int(game["home_score"]))}
    base={k:game[k] for k in ["country","league","competition","season","phase","round","game_id","date_local","status","source_quality","source_note","source_url"]}
    for side,(ta,tn,oa,on,ts,os_) in sides.items():
        if targets is not None and ta not in targets: continue
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
    """g: red iz domestic-games (EL/EC). Vraca FS zapis po skoru + datumu (+-1 dan) + kodu kluba.
    Isti par timova (domaci i gost) sa istim rezultatom poklapa se i kad se datum razlikuje do 5 dana."""
    try: d0=datetime.datetime.strptime(str(g["date_local"])[:10],"%Y-%m-%d")
    except Exception: return None
    best=None
    for r in recs.values():
        if r["hs"]!=int(g["home_score"]) or r["as_"]!=int(g["away_score"]): continue
        days=abs((datetime.datetime.fromtimestamp(r["epoch"],datetime.UTC).replace(tzinfo=None)-d0).days)
        codes={r["ha"],r["aa"]}-{None}
        same_pair=(r["ha"]==g["home_abbr"] and r["aa"]==g["away_abbr"])
        if days<=1 and (codes & {g["home_abbr"],g["away_abbr"]}): return r
        if same_pair and days<=5 and best is None: best=r
    return best

def fs_url(r):
    return f"https://www.rezultati.com/utakmica/kosarka/{r['wu']}-{r['ja']}/{r['wv']}-{r['jb']}/detalji/statistika-igraca/ukupno/?mid={r['mid']}"

_cache={}
def _near(epoch, date_str, days=1.6):
    """Datum iz naslova ACB-a ('Oct 10, 2026') u odnosu na Flashscore epoch."""
    try: d=datetime.datetime.strptime(date_str,"%b %d, %Y").replace(tzinfo=datetime.UTC)
    except Exception: return False
    return abs(d.timestamp()-epoch)<days*86400

def official_box(r):
    """Pokusa zvanicni izvor za novu utakmicu; vraca (box, quality, note, url, venue, game_id) ili None."""
    key=r["key"]
    if key in("ESP Supercopa","ESP ACB"):
        idx=_cache.setdefault("acb",SRC.acb_index())
        for gid,(dt,hn,an,hs,as_) in idx.items():
            if (hs,as_)==(r["hs"],r["as_"]) and _near(r["epoch"],dt):
                u=f"https://live.acb.com/en/partidos/x-{gid}/estadisticas"
                b=SRC.acb_box(u)
                if b:
                    return b,"official_boxscore",NOTE["acb"].format(comp=COMP[key][2]),u,None,f"ACB-{gid}"
    if key in("ITA Supercoppa","ITA LBA"):
        idx=_cache.setdefault("lba",SRC.lba_index())
        for gid,(dt,h,a,hs,vs,comp) in idx.items():
            if (hs,vs)==(r["hs"],r["as_"]) and abs(datetime.datetime.fromisoformat(dt).timestamp()-r["epoch"])<86400:
                b=SRC.lba_box(gid)
                if b:
                    u=f"https://www.legabasket.it/game/{gid}/x/tabellini"
                    return b,"official_boxscore",NOTE["lba"],u,b["meta"].get("venue"),f"LBA-{gid}"
    if key in("ISR SuperCup","ISR LeagueCup","ISR SuperLeague"):
        board={"ISR SuperCup":34,"ISR LeagueCup":10,"ISR SuperLeague":5}[key]
        ids=_cache.setdefault(("ibsl",board),None)
        if ids is None:
            rr=SRC.get("https://basket.co.il/results.asp",params={"cYear":2027,"Board":board,"RoundNumber":0,"TeamId":0,"lang":"en"})
            ids=sorted(set(re.findall(r"game-zone\.asp\?GameId=(\d+)",rr.text))) if rr is not None else []
            _cache[("ibsl",board)]=ids
        for gid in ids:
            bk=("ibslbox",gid)
            if bk not in _cache: _cache[bk]=SRC.ibsl_box(gid)
            b=_cache[bk]
            if b and (sum(p["pts"] for p in b["players"] if p["team"]=="H"),sum(p["pts"] for p in b["players"] if p["team"]=="A"))==(r["hs"],r["as_"]):
                b=dict(b)
                for k in("home_name","away_name"): b[k]=re.sub(r"\s*\(.*?\)\s*$","",b[k] or "")
                return b,"official_boxscore",NOTE["ibsl"],f"https://basket.co.il/game-zone.asp?GameId={gid}&lang=en",None,f"ISR-{gid}"
    return None

OFFICIAL_KEYS=("ITA Supercoppa","ITA LBA","ISR SuperCup","ISR LeagueCup","ISR SuperLeague")   # ACB: live.acb.com po ID-u vraca druge utakmice nego Rezultati -> nema poklapanja, pa Flashscore
LOW_Q=("official_result_average_only","third_party_result_average_only","third_party_result_only","official_result_only")

INIT=re.compile(r"^((?:[A-Z]\.\s?)+)\s*(\S.*)$")
def fantasy_names():
    """Imena igraca iz fantasy listi (EuroLeague/EuroCup) po klubu: koriste se da se 'T. Maledon' razrijesi u puno ime."""
    out={}
    for f in ("euroleague-players-full.csv","eurocup-players-full.csv"):
        p=ROOT/f
        if p.exists():
            d=pd.read_csv(p,usecols=["name","team_abbr"])
            for ab,nm in zip(d["team_abbr"],d["name"]): out.setdefault(ab,set()).add(str(nm))
    return {k:sorted(v) for k,v in out.items()}

def fix_initial_names(box, fnames):
    """Redovi sa skracenim imenom ('T. Maledon') -> puno ime ako ga fantasy lista tog kluba jednoznacno daje. Vraca skup timova sa izmjenama."""
    mapping={}
    for ta,pl in set(zip(box["team_abbr"],box["player"])):
        m=INIT.match(str(pl))
        if not m or ta not in fnames: continue
        cand=resolve_name(f"{m.group(2)} {' '.join(m.group(1).split())}","",fnames[ta])
        if cand and cand!=pl and not INIT.match(cand): mapping[(ta,pl)]=cand
    changed=set()
    for (ta,pl),new in mapping.items():
        mask=(box["team_abbr"]==ta)&(box["player"]==pl); box.loc[mask,"player"]=new; changed.add(ta)
    return changed,len(mapping)

SUFFIXES={"jr","sr","ii","iii","iv","v"}
def name_seq(s):
    """Normalizovani tokeni imena po redu (bez dijakritika, interpunkcije i sufiksa Jr/Sr/II...)."""
    s=unicodedata.normalize("NFKD",str(s or "")); s="".join(c for c in s if not unicodedata.combining(c)).lower().replace("ı","i")
    return [x for x in re.sub(r"[^a-z0-9 ]"," ",s.replace("-"," ")).split() if x not in SUFFIXES and len(x)>1]

def canonical_names(box, fnames):
    """Jedan igrac = jedno ime. Varijante koje se odnose na istog fantasy igraca kluba (isti tokeni u drugom redoslijedu, npr.
    'Hayes-Davis Nigel', ili skraceno/prosireno ime, npr. 'Anthony Dewayne Cowan') svode se na fantasy ime; razlike samo u
    dijakriticima/velikim slovima se ne diraju. Vraca (skup izmijenjenih timova, broj preimenovanja)."""
    groups={}
    for ta,pl in set(zip(box["team_abbr"],box["player"])):
        if ta not in fnames or str(pl).upper()=="TOTAL": continue
        k=name_seq(pl)
        if len(k)<2: continue
        ks=set(k)
        eq=[f for f in fnames[ta] if set(name_seq(f))==ks]
        if eq: tgt=eq[0]
        else:
            sub=[f for f in fnames[ta] if len(set(name_seq(f))&ks)>=2 and (set(name_seq(f))<=ks or ks<=set(name_seq(f)))]
            if len(sub)!=1: continue
            tgt=sub[0]
        groups.setdefault((ta,tgt),set()).add(pl)
    changed=set(); n=0
    for (ta,tgt),variants in groups.items():
        for v in variants:
            reorder=name_seq(v)!=name_seq(tgt)
            if v!=tgt and (len(variants)>1 or reorder):
                box.loc[(box["team_abbr"]==ta)&(box["player"]==v),"player"]=tgt; changed.add(ta); n+=1
    return changed,n

def annotate_partial(games, box):
    """Ako zbir poena igraca tima ne odgovara rezultatu (izvor izostavlja neke igrace), to se upisuje u source_note utakmice."""
    pl=box[~box["is_total"].astype(bool)]
    s=pl.groupby(["game_id","team_abbr"]).agg(pts=("pts","sum"),score=("team_score","first")).reset_index()
    n=0
    for r in s[(s["pts"]-s["score"]).abs()>0.1].itertuples():
        m=games["game_id"]==r.game_id
        if not m.any(): continue
        note=str(games.loc[m,"source_note"].iloc[0]); tag=f" Player rows for {r.team_abbr} sum to {int(r.pts)} of {int(r.score)} team points (the source omits some players)."
        if f"Player rows for {r.team_abbr} sum" in note: continue
        games.loc[m,"source_note"]=note+tag; n+=1
    return n

def parse_round(rnd):
    s=str(rnd or "")
    if s in PHASE: return PHASE[s]
    m=re.search(r"(\d+)",s)
    return ("Regular Season",f"{int(m.group(1)):02d}") if m else ("Regular Season","")

def names_only():
    box=pd.read_csv(ROOT/"domestic-player-boxscores.csv",dtype={"round":str}); avg=pd.read_csv(ROOT/"domestic-player-averages.csv")
    fnames=fantasy_names(); ch,n=fix_initial_names(box,fnames); print(f"skracena imena razrijesena: {n} igraca u {len(ch)} timova")
    ch2,n2=canonical_names(box,fnames); ch|=ch2; print(f"imena svedena na jedan zapis: {n2} (timova: {len(ch2)})")
    if not ch: return
    newavg=recompute_averages(box.copy(),sorted(ch)); avg=pd.concat([avg[~avg["team_abbr"].isin(ch)],newavg],ignore_index=True)[AVG_COLS]
    box.to_csv(ROOT/"domestic-player-boxscores.csv",index=False); avg.to_csv(ROOT/"domestic-player-averages.csv",index=False)
    print(f"upisano: {len(box)} redova igraca | {len(avg)} prosjeka")

def main(dry=False):
    now=datetime.datetime.now(TZ); stamp=now.strftime("%Y-%m-%d %H:%M ")+("CEST" if now.dst() else "CET")
    games=pd.read_csv(ROOT/"domestic-games.csv",dtype={"round":str}); box=pd.read_csv(ROOT/"domestic-player-boxscores.csv",dtype={"round":str})
    tot=pd.read_csv(ROOT/"domestic-team-boxscores.csv",dtype={"round":str}); avg=pd.read_csv(ROOT/"domestic-player-averages.csv")
    games=apply_alias(games,["home_abbr","away_abbr"]); box=apply_alias(box,["team_abbr","opponent_abbr"]); tot=apply_alias(tot,["team_abbr","opponent_abbr"]); avg=apply_alias(avg,["team_abbr"])
    # deduplikacija: ista utakmica (game_id) ne smije postojati dva puta, ni njeni redovi
    dup_ids=set(games[games.duplicated("game_id",keep=False)]["game_id"]); dedup_teams=set()
    for gid in dup_ids: dedup_teams|=set(games[games["game_id"]==gid][["home_abbr","away_abbr"]].values.ravel())
    dedup_teams&=set(TARGET)
    n0=(len(games),len(box),len(tot))
    games=games.drop_duplicates("game_id",keep="first").reset_index(drop=True)
    box=box.drop_duplicates(["game_id","team_abbr","player","is_total"],keep="first").reset_index(drop=True)
    tot=tot.drop_duplicates(["game_id","team_abbr"],keep="first").reset_index(drop=True)
    if n0!=(len(games),len(box),len(tot)): print(f"deduplikacija: utakmica {n0[0]}->{len(games)}, redova igraca {n0[1]}->{len(box)}, totala {n0[2]}->{len(tot)} | timovi: {sorted(dedup_teams)}")
    print(f"baza: {len(games)} utakmica | {len(box)} redova igraca | {len(tot)} totala | {len(avg)} prosjeka")
    book=CodeBook(games)
    recs=fs_records(); print(f"Flashscore: {len(recs)} zavrsenih domacih utakmica EL+EuroCup klubova (sezona {SEASON})")
    is_t=lambda r: r["home_abbr"] in TARGET or r["away_abbr"] in TARGET
    # --- 1) sta vec imamo
    matched={}                                          # game_id -> fs zapis
    for _,g in games[games.apply(is_t,axis=1)].iterrows():
        r=match_baseline(g,recs)
        if r: matched[g["game_id"]]=r
    used={r["mid"] for r in matched.values()}
    new=[r for r in sorted(recs.values(),key=lambda x:x["epoch"]) if r["mid"] not in used]
    print(f"vec u bazi: {len(used)} | nove: {len(new)}")
    fnames=fantasy_names()
    known={ta:sorted(set(box[box["team_abbr"]==ta]["player"])|set(avg[avg["team_abbr"]==ta]["player"])|set(fnames.get(ta,[]))) for ta in TARGET}
    new_games=[]; new_box=[]; new_tot=[]; log=[]
    for r in new:
        country,league,comp=COMP[r["key"]]
        ph,rd=parse_round(r["rnd"])
        ha,hn=abbr_for(r["home"],r["ha"],book); aa,an=abbr_for(r["away"],r["aa"],book)
        ob=official_box(r) if r["key"] in OFFICIAL_KEYS else None
        if ob:
            b,q,note,url,venue,gid=ob
            if r["key"].startswith(("ESP","ITA")) or r["key"]=="ISR SuperCup":
                ha,hn=(r["ha"],NAMES[r["ha"]]) if r["ha"] else (book.lookup(b["home_name"]) if b["home_name"] else (ha,hn))
                aa,an=(r["aa"],NAMES[r["aa"]]) if r["aa"] else (book.lookup(b["away_name"]) if b["away_name"] else (aa,an))
        else:
            b=SRC.fs_boxscore(r["mid"]); q="third_party_boxscore_est_pir"; url=fs_url(r); venue=None
            note={"TUR":NOTE["fs_tur"],"FRA":NOTE["fs_fra"],"GER":NOTE["fs_ger"]}.get(r["key"][:3],NOTE["fs"]); gid=f"{ {'TUR':'BSL','FRA':'FRA-FS','GER':'BBL'}.get(r['key'][:3],'FS') }-{r['mid']}"
        if gid in set(games["game_id"])|{x["game_id"] for x in new_games}:
            log.append(f"= vec postoji (isti izvor/game_id {gid}): {ha} {r['hs']}-{r['as_']} {aa} - preskoceno"); continue
        if not b:
            # nema player statistike nigdje: samo rezultat (bez izmisljenih redova)
            q="third_party_result_only"; note="Final score verified from Rezultati.com/Flashscore; no player rows because a complete player box score was not available."
            gid=f"FS-{r['mid']}"; url=fs_url(r); venue=None
            g=dict(country=country,league=league,competition=comp,season=SEASON,phase=ph,round=rd,game_id=gid,date_local=zagreb(r["epoch"]),venue=venue,home_team=hn,home_abbr=ha,away_team=an,away_abbr=aa,
                   home_score=r["hs"],away_score=r["as_"],status="played",source_quality=q,source_note=note,source_url=url)
            qs=FSB.quarters(r["mid"])
            for i in range(4):
                g[f"q{i+1}_home"]=float(qs[i][0]) if i<len(qs) else np.nan; g[f"q{i+1}_away"]=float(qs[i][1]) if i<len(qs) else np.nan
            new_games.append(g); log.append(f"+ {g['date_local']} {league:13s} {comp:24s} {ha} {r['hs']}-{r['as_']} {aa} | {q}"); continue
        qs=(b.get("meta",{}).get("q") or [])
        if len(qs)<4 or any(x is None for t_ in qs for x in t_): qs=FSB.quarters(r["mid"])
        if r["key"]=="GER BBL" and r["rnd"].startswith("23"): note+=" Round 23 fixture played early (rescheduled)."
        g=dict(country=country,league=league,competition=comp,season=SEASON,phase=ph,round=rd,game_id=gid,date_local=zagreb(r["epoch"]),venue=venue,home_team=hn,home_abbr=ha,away_team=None,away_abbr=aa)
        g.update(away_team=an,home_score=r["hs"],away_score=r["as_"],status="played",source_quality=q,source_note=note,source_url=url)
        for i in range(4):
            g[f"q{i+1}_home"]=float(qs[i][0]) if i<len(qs) else np.nan; g[f"q{i+1}_away"]=float(qs[i][1]) if i<len(qs) else np.nan
        pr,tr=build_rows(g,b,targets=set(TARGET),known_names=known)
        new_games.append(g); new_box+=pr; new_tot+=tr
        log.append(f"+ {g['date_local']} {league:13s} {comp:24s} {ha} {r['hs']}-{r['as_']} {aa} | {q} | igraca ciljnih klubova: {len(pr)}")
    # --- 2) utakmice koje su imale samo rezultat/prosjeke -> game-level box score (Flashscore, procijenjen PIR)
    upgrade=0; upgraded_ids=set()
    for _,g in games[games.apply(is_t,axis=1)].iterrows():
        if g["source_quality"] not in LOW_Q or g["game_id"] not in matched: continue
        r=matched[g["game_id"]]; b=SRC.fs_boxscore(r["mid"])
        if not b: continue
        gd=g.to_dict(); gd["source_quality"]="third_party_boxscore_est_pir"
        gd["source_note"]={"FRA":NOTE["fs_fra"],"GER":NOTE["fs_ger"],"TUR":NOTE["fs_tur"]}.get(r["key"][:3],NOTE["fs"])
        gd["source_url"]=fs_url(r)
        qs=b["meta"]["q"]
        for i in range(4):
            if i<len(qs): gd[f"q{i+1}_home"]=float(qs[i][0]); gd[f"q{i+1}_away"]=float(qs[i][1])
        pr,tr=build_rows(gd,b,targets=set(TARGET),known_names=known)
        cols=["source_quality","source_note","source_url"]+[f"q{i}_{s}" for i in (1,2,3,4) for s in ("home","away")]
        games.loc[games["game_id"]==g["game_id"],cols]=[gd[c] for c in cols]
        new_box+=pr; new_tot+=tr; upgrade+=1; upgraded_ids.add(g["game_id"]); log.append(f"^ nadogradnja {str(g['date_local'])[:10]} {g['home_abbr']} {g['home_score']}-{g['away_score']} {g['away_abbr']}: {len(pr)} redova igraca")
    # --- 2b) utakmice u kojima jedna ciljna strana nema player redove (npr. raniji prolaz samo za EuroLeague) -> dopuni samo tu stranu
    have=set(zip(box["game_id"],box["team_abbr"]))|{(x["game_id"],x["team_abbr"]) for x in new_box}; filled=0
    for _,g in games[games.apply(is_t,axis=1)].iterrows():
        if g["game_id"] in upgraded_ids or g["source_quality"] in LOW_Q or g["game_id"] not in matched: continue
        missing=[ab for ab in (g["home_abbr"],g["away_abbr"]) if ab in TARGET and (g["game_id"],ab) not in have]
        if not missing: continue
        r=matched[g["game_id"]]; ob=official_box(r) if r["key"] in OFFICIAL_KEYS else None
        b=ob[0] if ob else SRC.fs_boxscore(r["mid"])
        if not b: continue
        pr,tr=build_rows(g.to_dict(),b,targets=set(missing),known_names=known)
        if not pr: continue
        new_box+=pr; new_tot+=tr; filled+=1
        if not ob and str(g["source_quality"]).startswith("official"):
            games.loc[games["game_id"]==g["game_id"],"source_note"]=str(g["source_note"])+f" Rows for {', '.join(missing)} from Rezultati.com/Flashscore (estimated PIR)."
        log.append(f"~ dopuna {str(g['date_local'])[:10]} {g['home_abbr']} {g['home_score']}-{g['away_score']} {g['away_abbr']}: {len(pr)} redova za {','.join(missing)}")
    print("\n".join(log))
    print(f"\nSAZETAK: nove utakmice {len(new_games)} (sa player redovima: {sum(1 for g in new_games if g['source_quality']!='third_party_result_only')}), nadogradnje {upgrade}")
    if dry: print("--dry: nista nije upisano"); return
    # --- 3) spoji
    games=pd.concat([games,pd.DataFrame(new_games)],ignore_index=True)[GAME_COLS]
    box=pd.concat([box,pd.DataFrame(new_box)],ignore_index=True)[BOX_COLS]; tot=pd.concat([tot,pd.DataFrame(new_tot)],ignore_index=True)[BOX_COLS]
    # --- 4) vremena: Europe/Zagreb iz Flashscore epoch-a
    allmatch=dict(matched)
    for r in new:
        for gg in new_games:
            if gg["home_score"]==r["hs"] and gg["away_score"]==r["as_"] and gg["date_local"]==zagreb(r["epoch"]): allmatch[gg["game_id"]]=r
    for gid,r in allmatch.items():
        d=zagreb(r["epoch"])
        for df in (games,box,tot): df.loc[df["game_id"]==gid,"date_local"]=d
    # --- 5) prosjeci: preracunaj za timove sa novim/nadogradjenim redovima
    ch_names,n_names=fix_initial_names(box,fnames); print(f"skracena imena razrijesena: {n_names} igraca u {len(ch_names)} timova")
    ch2,n2=canonical_names(box,fnames); ch_names|=ch2; print(f"imena svedena na jedan zapis: {n2} (timova: {len(ch2)})")
    changed=sorted({p["team_abbr"] for p in new_box}|ch_names|dedup_teams); print("preracunati prosjeci za:",changed)
    newavg=recompute_averages(box.copy(),changed)
    avg=pd.concat([avg[~avg["team_abbr"].isin(changed)],newavg],ignore_index=True)[AVG_COLS]
    games=games.sort_values(["date_local","league","game_id"],kind="mergesort").reset_index(drop=True)
    print("bilješke o nepotpunim player redovima:",annotate_partial(games,box))
    games.to_csv(ROOT/"domestic-games.csv",index=False); box.to_csv(ROOT/"domestic-player-boxscores.csv",index=False)
    tot.to_csv(ROOT/"domestic-team-boxscores.csv",index=False); avg.to_csv(ROOT/"domestic-player-averages.csv",index=False)
    print(f"upisano: {len(games)} utakmica | {len(box)} redova igraca | {len(tot)} totala | {len(avg)} prosjeka")
    try:
        Path("/tmp/dom").mkdir(parents=True,exist_ok=True)
        json.dump({"stamp":stamp,"new_games":len(new_games),"upgraded":upgrade},open("/tmp/dom/last_run.json","w"))
    except OSError: pass

if __name__=="__main__":
    if "--names-only" in sys.argv: names_only()
    else: main(dry="--dry" in sys.argv)
