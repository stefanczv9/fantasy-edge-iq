"""Adapteri izvora za domaca takmicenja EuroLeague klubova.

Svaki adapter vraca isti oblik:
    {"home":{...}, "away":{...}, "players":[...], "meta":{...}}
Igrac (dict): name, team ('H'|'A'), pts, reb, dreb, oreb, ast, blk, blka, fd (None ako izvor nema), pf, stl, tov,
              minutes_raw, minutes, rank (None -> procjena), m2,a2,m3,a3,ftm,fta
Zvanicni izvori: ACB Live, LBA (Next.js JSON), Israel BSL game-zone. Ostalo: Flashscore/Rezultati feed (procijenjen PIR).
"""
import re, json, requests
from bs4 import BeautifulSoup
import fs_box as fsb

UA={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36","Accept-Language":"en"}

def get(url, retries=3, **kw):
    last=None
    for _ in range(retries):
        try:
            r=requests.get(url, headers=UA, timeout=40, **kw)
            if r.status_code==200: return r
            last=r
        except Exception as e:
            last=e
    return last if isinstance(last, requests.Response) else None

def _i(v):
    v=str(v).strip()
    if v in("","-","None","nan"): return 0
    try: return int(float(v))
    except: return 0

def _mmss(v):
    v=str(v or "").strip()
    if not v or v in("-",): return None
    if v.count(":")==2:
        h,m,s=v.split(":"); return int(h)*60+int(m)+int(s)/60.0
    if ":" in v:
        m,s=v.split(":"); return int(m)+int(s)/60.0
    try: return float(v)
    except: return None

def est_pir(p):
    """PIR bez PF i FD (izvor ih ne daje): PTS+REB+AST+STL+BLK-promasaji-TOV-BLKA"""
    fga=p["a2"]+p["a3"]; fgm=p["m2"]+p["m3"]
    return p["pts"]+p["reb"]+p["ast"]+p["stl"]+p["blk"]-(fga-fgm)-(p["fta"]-p["ftm"])-p["tov"]-p["blka"]

# ---------------------------------------------------------------- ACB (live.acb.com)
def acb_box(game_url):
    """game_url: https://live.acb.com/en/partidos/<slug>-<id>/estadisticas"""
    r=get(game_url)
    if r is None or r.status_code!=200: return None
    return acb_box_html(r.text)

def acb_box_html(html):
    s=BeautifulSoup(html,"lxml")
    title=s.title.get_text() if s.title else ""
    m=re.match(r"(.+?) vs (.+?) (\w{3} \d{1,2}, \d{4})",title)
    home_name,away_name=(m.group(1),m.group(2)) if m else (None,None)
    tabs=[t for t in s.find_all("table") if t.find("tr") and "Player" in [c.get_text(strip=True) for c in t.find("tr").find_all(["th","td"])]]
    if len(tabs)<2: return None
    players=[]; totals={}
    for side,tb in zip(("H","A"),tabs[:2]):
        head=[c.get_text(strip=True) for c in tb.find("tr").find_all(["th","td"])]
        ix={h:i for i,h in enumerate(head)}
        for tr in tb.find_all("tr")[1:]:
            c=[x.get_text(" ",strip=True) for x in tr.find_all(["th","td"])]
            if len(c)<len(head) or not c[0]: continue
            name=re.sub(r"^\d+\s+","",c[0]).strip()
            def ma(k):
                a=c[ix[k]].split("/"); return _i(a[0]),_i(a[1]) if len(a)>1 else 0
            m2,a2=ma("T2"); m3,a3=ma("T3"); ftm,fta=ma("TL")
            row=dict(name=name,team=side,pts=_i(c[ix["Pts"]]),reb=_i(c[ix["TR"]]),dreb=_i(c[ix["DR"]]),oreb=_i(c[ix["OR"]]),
                     ast=_i(c[ix["As"]]),blk=_i(c[ix["B"]]),blka=_i(c[ix["BR"]]),fd=_i(c[ix["FD"]]),pf=_i(c[ix["PF"]]),
                     stl=_i(c[ix["Stl"]]),tov=_i(c[ix["TO"]]),minutes_raw=c[ix["Min"]],minutes=_mmss(c[ix["Min"]]),
                     rank=_i(c[ix["Val"]]),m2=m2,a2=a2,m3=m3,a3=a3,ftm=ftm,fta=fta)
            if re.fullmatch(r"(?i)(total|totals|equipo|team|coach|entrenador).*",name): continue
            if row["minutes"] is None and not any([row["pts"],row["reb"],row["ast"],row["stl"],row["tov"],row["pf"]]): continue
            players.append(row)
    return {"home_name":home_name,"away_name":away_name,"players":players,"meta":{"title":title}}

def acb_index(lo=105681, hi=105800):
    """live.acb.com otvara utakmicu i samo po ID-u (slug se ignorise). Skenira ID-eve i vraca
    {id: (datum 'Mon DD, YYYY', home, away, home_pts, away_pts)} za odigrane utakmice."""
    import concurrent.futures as cf, datetime
    def one(i):
        r=get(f"https://live.acb.com/en/partidos/x-{i}/estadisticas", retries=2)
        if r is None or r.status_code!=200 or "no encontrado" in r.text.lower(): return None
        b=acb_box_html(r.text)
        if not b or not b["players"]: return None
        hs=sum(p["pts"] for p in b["players"] if p["team"]=="H"); as_=sum(p["pts"] for p in b["players"] if p["team"]=="A")
        if hs+as_==0: return None
        m=re.match(r"(.+?) vs (.+?) (\w{3} \d{1,2}, \d{4})",b["meta"]["title"])
        if not m: return None
        return i,(m.group(3),m.group(1),m.group(2),hs,as_)
    out={}
    with cf.ThreadPoolExecutor(12) as ex:
        for res in ex.map(one,range(lo,hi)):
            if res: out[res[0]]=res[1]
    return out

def acb_supercopa_links():
    """Vraca [(url_estadisticas, home_slug_text)] sa acb.com/es/supercopa"""
    r=get("https://acb.com/es/supercopa")
    out=[]
    if r is None: return out
    for h in sorted(set(re.findall(r'https://live\.acb\.com/partidos/[a-z0-9\-]+-\d+/(?:resumen|estadisticas)',r.text))):
        base=h.rsplit("/",1)[0].replace("https://live.acb.com/","https://live.acb.com/en/")
        out.append(base+"/estadisticas")
    return out

# ---------------------------------------------------------------- LBA (legabasket.it)
def lba_box(game_id):
    r=get(f"https://www.legabasket.it/game/{game_id}/x/tabellini")
    if r is None or r.status_code!=200: return None
    m=re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',r.text,flags=re.S)
    if not m: return None
    g=json.loads(m.group(1))["props"]["pageProps"]["game"]; mt=g["match"]; sc=g["scores"]
    players=[]
    for side,key in (("H","ht"),("A","vt")):
        for p in sc[key]["rows"]:
            sec=p.get("sec") or 0
            mins=sec/60.0 if sec else (p.get("min") or 0)
            name=f'{(p.get("player_name") or "").strip()} {(p.get("player_surname") or "").strip().title()}'.strip()
            players.append(dict(name=name,team=side,pts=_i(p["pun"]),reb=_i(p["rimbalzi_t"]),dreb=_i(p["rimbalzi_d"]),oreb=_i(p["rimbalzi_o"]),
                ast=_i(p["ass"]),blk=_i(p["stoppate_dat"]),blka=_i(p["stoppate_sub"]),fd=_i(p["falli_sf"]),pf=_i(p["falli_c"]),
                stl=_i(p["palle_r"]),tov=_i(p["palle_p"]),minutes_raw=f"{int(sec//60):02d}:{int(sec%60):02d}" if sec else "",minutes=mins if sec else None,
                rank=_i(p["val_lega"]),m2=_i(p["t2_r"]),a2=_i(p["t2_t"]),m3=_i(p["t3_r"]),a3=_i(p["t3_t"]),ftm=_i(p["tl_r"]),fta=_i(p["tl_t"])))
    players=[p for p in players if p["minutes"] or any([p["pts"],p["reb"],p["ast"],p["stl"],p["tov"],p["pf"]])]
    return {"home_name":mt["h_team_name"],"away_name":mt["v_team_name"],"players":players,
            "meta":{"competition":mt.get("competition_name"),"datetime":mt.get("match_datetime"),"venue":mt.get("plant_name"),
                    "hs":mt["home_final_score"],"as":mt["visitor_final_score"],
                    "q":[(mt.get(f"q{i}_hs"),mt.get(f"q{i}_vs")) for i in (1,2,3,4)]}}

def lba_index(lo=25357, hi=25960):
    """Skenira LBA ID-eve i vraca {id: (datetime, home, away, hs, vs, competition)} za zavrsene utakmice."""
    import concurrent.futures as cf
    def one(i):
        r=get(f"https://www.legabasket.it/game/{i}/x/tabellini", retries=2)
        if r is None or r.status_code!=200: return None
        m=re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',r.text,flags=re.S)
        if not m: return None
        try: mt=json.loads(m.group(1))["props"]["pageProps"]["game"]["match"]
        except Exception: return None
        if not (mt.get("home_final_score") or mt.get("visitor_final_score")): return None
        return i,(mt["match_datetime"],mt["h_team_name"],mt["v_team_name"],mt["home_final_score"],mt["visitor_final_score"],mt.get("competition_name"))
    out={}
    with cf.ThreadPoolExecutor(16) as ex:
        for res in ex.map(one,range(lo,hi)):
            if res: out[res[0]]=res[1]
    return out

# ---------------------------------------------------------------- Israel BSL (basket.co.il)
def ibsl_box(game_id):
    r=get(f"https://basket.co.il/game-zone.asp?GameId={game_id}&lang=en")
    if r is None or r.status_code!=200: return None
    s=BeautifulSoup(r.text,"lxml")
    tabs=[t for t in s.find_all("table",class_="stats_tbl") if any("Player Name" in c.get_text() for c in t.find_all("td")+t.find_all("th"))]
    players=[]; names=[]
    for side,tb in zip(("H","A"),tabs[:2]):
        rows=tb.find_all("tr")
        names.append(rows[0].get_text(" ",strip=True))
        for tr in rows:
            c=[x.get_text(" ",strip=True) for x in tr.find_all(["th","td"])]
            if len(c)<22 or c[1] in("Player Name","Total","") or not re.fullmatch(r"\d+",c[0] or "x"): continue
            def ma(v):
                a=v.split("/"); return _i(a[0]),(_i(a[1]) if len(a)>1 else 0)
            m2,a2=ma(c[5]); m3,a3=ma(c[7]); ftm,fta=ma(c[9])
            mins=_mmss(c[3])
            players.append(dict(name=c[1],team=side,pts=_i(c[4]),reb=_i(c[13]),dreb=_i(c[11]),oreb=_i(c[12]),ast=_i(c[18]),blk=_i(c[19]),blka=_i(c[20]),
                fd=_i(c[15]),pf=_i(c[14]),stl=_i(c[16]),tov=_i(c[17]),minutes_raw=c[3],minutes=mins,rank=_i(c[21]),
                m2=m2,a2=a2,m3=m3,a3=a3,ftm=ftm,fta=fta))
    players=[p for p in players if p["minutes"] or any([p["pts"],p["reb"],p["ast"],p["stl"],p["tov"],p["pf"]])]
    return {"home_name":names[0] if names else None,"away_name":names[1] if len(names)>1 else None,"players":players,"meta":{}}

# ---------------------------------------------------------------- Flashscore (procijenjen PIR, bez FD)
def fs_boxscore(mid):
    d=fsb.player_stats(mid)
    if not d["players"] or len(d["teams"])<2: return None
    t=d["teams"]; players=[]
    for p in d["players"]:
        side="H" if p["team"]==t[0] else "A"
        row=dict(name=p["name"],slug=p["slug"],team=side,pts=p["pts"],reb=p["reb"],dreb=p["dreb"],oreb=p["oreb"],ast=p["ast"],blk=p["blk"],blka=p["blka"],
                 fd=None,pf=p["pf"],stl=p["stl"],tov=p["tov"],minutes_raw=p["minutes_raw"],minutes=p["minutes"],rank=None,
                 m2=p["m2"],a2=p["a2"],m3=p["m3"],a3=p["a3"],ftm=p["ftm"],fta=p["fta"])
        row["rank"]=est_pir(row)
        players.append(row)
    players=[p for p in players if p["minutes"] or any([p["pts"],p["reb"],p["ast"],p["stl"],p["tov"],p["pf"]])]
    return {"home_name":t[0],"away_name":t[1],"players":players,"meta":{"q":fsb.quarters(mid)}}
