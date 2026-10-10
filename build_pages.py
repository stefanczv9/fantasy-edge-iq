#!/usr/bin/env python3
"""Sklapa DATA (EL klubovi) iz domestic-*.csv i regenerise 3 stranice rubrike Domestic Competitions (EN/SR/EL)."""
import re, sys, json, math, datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import pandas as pd, numpy as np

HERE=Path(__file__).resolve().parent; sys.path.insert(0,str(HERE)); ROOT=HERE.parent.parent
import update_domestic as U
EL=U.EL
PAGES={"en":"euroleague-domestic-competitions.html","sr":"sr-euroleague-domestic-competitions.html","el":"el-euroleague-domestic-competitions.html"}

TXT={
 "en":{"desc":"Domestic league and cup results and box-score stats for EuroLeague clubs, kept separate from European competition numbers.",
       "avg":"Grouped by player/team across all imported domestic games (league, cup and Super Cup rows combined). Rows from Rezultati.com/Flashscore (Turkey, France and part of Germany) carry an estimated Avg PIR: the foul components are not available there.",
       "method":"Sources: official ESAKE/GBL, ACB Live, LKL API, LBA game pages, ABA League game pages and Israel Basketball game-zone pages where available. Turkey, France and most of Germany use Rezultati.com/Flashscore game-level box scores because the official TBF/BSL, LNB and easyCredit BBL box scores are not publicly accessible; minutes and shots are captured, while PIR/RANK is estimated from available stats with the foul components omitted. Cup and Super Cup games (Supercopa Endesa, Supercoppa LBA, Greek, Israeli and LNB Super Cups, Turkish Presidential Cup, Winner Cup) are marked separately from league games. Times are shown in Central European Time (CET/CEST)."},
 "sr":{"desc":"Rezultati i box score statistika iz domaćih liga i kupova za EuroLeague klubove, odvojeno od evropskih takmičenja.",
       "avg":"Prosjeci su grupisani po igraču i timu kroz sve ubačene domaće utakmice (liga, kup i superkup zajedno). Redovi iz Rezultati.com/Flashscore (Turska, Francuska i dio Njemačke) imaju procijenjen prosječan PIR jer tamo nema komponenti ličnih grešaka.",
       "method":"Izvori: zvanični ESAKE/GBL, ACB Live, LKL API, LBA game page, ABA League game page i Israel Basketball game-zone gdje je dostupno. Za Tursku, Francusku i većinu Njemačke korišćeni su Rezultati.com/Flashscore box scoreovi po utakmici jer zvanični TBF/BSL, LNB i easyCredit BBL box scoreovi nisu javno dostupni; minute i šutevi su preuzeti, a PIR/RANK je procjena iz dostupnih statistika bez komponenti ličnih grešaka. Kup i superkup utakmice (Supercopa Endesa, Supercoppa LBA, grčki, izraelski i LNB superkup, turski Predsjednički kup, Winner Cup) označene su posebno od ligaških. Vremena su prikazana po srednjoevropskom vremenu (CET/CEST)."},
 "el":{"desc":"Αποτελέσματα και box-score στατιστικά από εγχώριες λίγκες και κύπελλα για συλλόγους της EuroLeague, ξεχωριστά από τις ευρωπαϊκές διοργανώσεις.",
       "avg":"Μέσοι όροι ανά παίκτη/ομάδα για όλα τα imported domestic games (λίγκα, κύπελλο και Super Cup μαζί). Οι γραμμές από Rezultati.com/Flashscore (Τουρκία, Γαλλία και μέρος της Γερμανίας) έχουν estimated Avg PIR, επειδή εκεί δεν υπάρχουν τα fouls components.",
       "method":"Πηγές: official ESAKE/GBL, ACB Live, LKL API, LBA game pages, ABA League game pages και Israel Basketball game-zone όπου υπάρχει. Για Τουρκία, Γαλλία και το μεγαλύτερο μέρος της Γερμανίας χρησιμοποιούνται game-level box scores από Rezultati.com/Flashscore, γιατί τα official TBF/BSL, LNB και easyCredit BBL box scores δεν είναι δημόσια διαθέσιμα· λεπτά και σουτ καταγράφονται, ενώ το PIR/RANK είναι εκτίμηση χωρίς τα fouls components. Cup και Super Cup αγώνες (Supercopa Endesa, Supercoppa LBA, ελληνικό, ισραηλινό και LNB Super Cup, τουρκικό Presidential Cup, Winner Cup) σημειώνονται ξεχωριστά από τους αγώνες λίγκας. Οι ώρες εμφανίζονται σε ώρα Κεντρικής Ευρώπης (CET/CEST)."},
}

def clean(v):
    if v is None: return None
    if isinstance(v,(np.integer,)): return int(v)
    if isinstance(v,(np.floating,float)):
        return None if (math.isnan(v) or math.isinf(v)) else float(v)
    if isinstance(v,(np.bool_,bool)): return bool(v)
    return v
def recs(df): return [{k:clean(v) for k,v in r.items()} for r in df.to_dict("records")]

def build_data(labels_by_lang):
    g=pd.read_csv(ROOT/"domestic-games.csv",dtype={"round":str}); p=pd.read_csv(ROOT/"domestic-player-boxscores.csv",dtype={"round":str})
    t=pd.read_csv(ROOT/"domestic-team-boxscores.csv",dtype={"round":str}); a=pd.read_csv(ROOT/"domestic-player-averages.csv")
    gl=g[g["home_abbr"].isin(EL)|g["away_abbr"].isin(EL)].sort_values(["date_local","league","game_id"],kind="mergesort").reset_index(drop=True)
    pl=p[p["team_abbr"].isin(EL)&(~p["is_total"].astype(bool))].reset_index(drop=True)
    tl=t[t["team_abbr"].isin(EL)].reset_index(drop=True)
    al=a[a["team_abbr"].isin(EL)].reset_index(drop=True)
    srt=lambda df,c: df.sort_values(c,ascending=False,kind="mergesort").head(12)
    cov=[]
    for ab in EL:
        n_g=int(((gl["home_abbr"]==ab)|(gl["away_abbr"]==ab)).sum()); n_r=int((pl["team_abbr"]==ab).sum())
        gids=set(gl[(gl["home_abbr"]==ab)|(gl["away_abbr"]==ab)]["game_id"]); with_rows=set(pl[pl["team_abbr"]==ab]["game_id"])
        no_rows=len(gids-with_rows)
        if n_g==0: st,note="pending","No completed domestic games yet."
        elif n_r==0: st,note="result-only",f"{n_g} completed game(s); results only, no player rows."
        else:
            st="extracted"; note=f"{n_g} completed game(s), {n_r} player rows imported."
            if no_rows: st="partial"; note+=f" {no_rows} game(s) have result only."
        cov.append({"team":f"{ab} — {U.EL_NAME[ab]}","status":st,"note":note})
    base={"games":recs(gl[U.GAME_COLS]),"players":recs(pl[U.BOX_COLS]),"totals":recs(tl[U.BOX_COLS]),"averages":recs(al[U.AVG_COLS]),
          "topAvgMin":recs(srt(al,"avg_minutes")),"topAvgPir":recs(srt(al,"avg_pir")),
          "topRank":recs(srt(pl,"rank")[U.BOX_COLS]),"topPoints":recs(srt(pl,"pts")[U.BOX_COLS]),"topMinutes":recs(srt(pl,"minutes")[U.BOX_COLS]),
          "coverage":cov,"targetTeams":EL,"elTeams":EL}
    return base,len(gl),len(pl),gl

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
    raise ValueError("DATA not found")

def main():
    now=datetime.datetime.now(ZoneInfo("Europe/Zagreb")); stamp=now.strftime("%Y-%m-%d %H:%M ")+("CEST" if now.dst() else "CET")
    labels={}; htmls={}
    for lg,f in PAGES.items():
        t=(ROOT/f).read_text(encoding="utf-8"); d,_,_=extract_data(t); labels[lg]=d["labels"]; htmls[lg]=t
    base,ng,npl,gl=build_data(labels)
    for lg,f in PAGES.items():
        t=htmls[lg]; _,a,b=extract_data(t)
        data={"generated":stamp,**{k:base[k] for k in ["games","players","totals","averages","topAvgMin","topAvgPir","topRank","topPoints","topMinutes","coverage"]},
              "labels":{**labels[lg],"averages_note":TXT[lg]["avg"],"method_text":TXT[lg]["method"]},"targetTeams":EL,"elTeams":EL}
        js=json.dumps(data,ensure_ascii=False,separators=(",",":")).replace("</","<\\/")
        t=t[:a]+js+t[b:]
        # staticki tekstovi
        t=re.sub(r'(<meta name="description" content=")[^"]*(")',lambda m:m.group(1)+TXT[lg]["desc"]+m.group(2),t,count=1)
        t=re.sub(r'(<section[^>]*id="averages"[^>]*>\s*<h2>[^<]*</h2><div class="note">)(.*?)(</div>)',lambda m:m.group(1)+TXT[lg]["avg"]+m.group(3),t,count=1,flags=re.S)
        t=re.sub(r'(<section[^>]*id="method"[^>]*>.*?<div class="note">)(.*?)(</div>)',lambda m:m.group(1)+TXT[lg]["method"]+m.group(3),t,count=1,flags=re.S)
        t=t.replace('href="/sr/euroleague/team-analyzer"','href="/euroleague/team-analyzer"').replace('href="/el/euroleague/team-analyzer"','href="/euroleague/team-analyzer"')
        (ROOT/f).write_text(t,encoding="utf-8")
        print(f"{f}: {len(t)//1024} KB | generated {stamp}")
    cov=pd.DataFrame(base["coverage"]); print(cov["status"].value_counts().to_dict()); print(f"EL utakmica: {ng} | redova igraca: {npl} | zemalja: {gl['country'].nunique()}")
    print("latest:",[(r.date_local,r.home_abbr,r.home_score,r.away_score,r.away_abbr) for r in gl.sort_values('date_local',ascending=False).head(3).itertuples()])

if __name__=="__main__": main()
