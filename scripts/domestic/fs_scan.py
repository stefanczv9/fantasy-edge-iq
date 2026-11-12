"""Skeniranje Flashscore/Rezultati stranica takmičenja: nalazi zavrsene domace utakmice 20 EuroLeague klubova."""
import requests, re, json, datetime, sys
H={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36","Accept-Language":"en"}
COMPS={
 "ESP ACB":"spanjolska/acb","ESP Supercopa":"spanjolska/supercopa-acb","ESP CopaRey":"spanjolska/copa-del-rey",
 "ITA LBA":"italija/lega-a","ITA Supercoppa":"italija/lega-a-super-cup","ITA CoppaItalia":"italija/kup",
 "GRE GBL":"grcka/basket-league","GRE SuperCup":"grcka/super-cup","GRE Cup":"grcka/kup",
 "TUR BSL":"turska/super-lig","TUR SuperCup":"turska/super-cup","TUR Cup":"turska/kup",
 "FRA LNB":"francuska/lnb","FRA SuperCup":"francuska/lnb-super-cup","FRA Cup":"francuska/french-cup",
 "GER BBL":"njemacka/bbl","GER Cup":"njemacka/kup",
 "LTU LKL":"litva/lkl","LTU KingMindaugas":"litva/king-mindaugas-cup",
 "ISR SuperLeague":"izrael/super-league","ISR SuperCup":"izrael/super-cup","ISR LeagueCup":"izrael/league-cup","ISR Cup":"izrael/israel-cup",
 "SRB Superleague":"srbija/superleague",
 "EUR ABA":"europa/admiralbet-aba-league","EUR ABA2":"europa/aba-league","EUR ABASuper":"europa/aba-supercup",
 # EuroCup klubovi
 "POL PLK":"poljska/basket-liga","POL SuperCup":"poljska/super-cup","POL Cup":"poljska/kup",
 "GBR SLB":"ujedinjeno-kraljevstvo/slb","GBR SLBCup":"ujedinjeno-kraljevstvo/slb-cup",
 "LAT-EST LEBL":"europa/latvian-estonian-league",
 "BUL NBL":"bugarska/nbl","BUL SuperCup":"bugarska/super-cup","BUL Cup":"bugarska/bulgarian-cup",
 "SLO Liga":"slovenija/liga-otp-banka","SLO Cup":"slovenija/slovenian-cup","SLO SuperCup":"slovenija/supercup",
 "ROU Divizia":"rumunjska/divizia-a","ROU Cup":"rumunjska/romanian-cup","ROU SuperCup":"rumunjska/super-cup",
 "MNE Prva":"crna-gora/prva-a-liga",
}
KEY={"ASV":["lyon-villeurbanne","asvel"],"BAR":["barcelona","barca"],"BAY":["bayern"],"BJK":["besiktas"],"CZV":["crvena-zvezda"],"DUB":["dubai"],
"EFS":["anadolu-efes","efes"],"FBT":["fenerbahce"],"HTA":["hapoel-tel-aviv","hapoel-ibi"],"KBA":["baskonia"],"MIL":["olimpia-milano","armani","milan"],
"MTA":["maccabi-tel-aviv","maccabi-rapyd"],"OLY":["olympiacos","olympiakos"],"PAO":["panathinaikos"],"PAR":["partizan"],"PBB":["paris"],"RMB":["real-madrid"],
"VBC":["valencia"],"VIR":["virtus-bologna","virtus"],"ZAL":["zalgiris"]}
# EuroCup klubovi (kodovi = fantasy EuroCup API). Redoslijed je bitan: EL kljucevi se provjeravaju prvi ('paris' prije 'aris').
KEY.update({"ARI":["aris"],"BKS":["bahcesehir"],"BLK":["balkan"],"BOS":["kk-bosna"],"BUD":["buducnost"],"BUR":["burgos"],"CHE":["chemnitz"],
 "COL":["cedevita"],"DER":["derthona"],"JLB":["jl-bourg","bourg"],"JLM":["hapoel-jerusalem","hapoel-midtown"],"LDN":["london-lions"],
 "LIE":["lietkabelis"],"LLT":["tenerife"],"MAN":["manresa"],"MSB":["le-mans"],"NAP":["basket-napoli","napoli-basket"],"NEP":["neptunas"],
 "PBC":["paok"],"RIG":["rigas-zelli"],"RMA":["maxima-roma"],"ROM":["bc-roma"],"ROS":["rostock"],"SIA":["siauliai"],"SKY":["frankfurt"],
 "TOF":["tofas"],"TRE":["trento"],"TTA":["turk-telekom"],"UBT":["cluj"],"ULM":["ulm"],"URV":["venezia","reyer"],"WKS":["slask"]})
def which(slug):
    s=(slug or "").lower()
    for ab,ks in KEY.items():
        if any(k in s for k in ks): return ab
    return None
def parse(u):
    r=requests.get(u,headers=H,timeout=40)
    if r.status_code!=200: return None,[]
    t=r.text; out=[]
    title=re.search(r"<title>(.*?)</title>",t); title=title.group(1) if title else ""
    for m in re.finditer(r"AA÷([A-Za-z0-9]{8})¬(.*?)(?=¬~AA÷|¬~ZA÷|¬~\s*$|$)",t,flags=re.S):
        d=dict(kv.split("÷",1) for kv in m.group(2).split("¬") if "÷" in kv)
        d["mid"]=m.group(1); out.append(d)
    return title,out
if __name__=="__main__":
    found=[]
    for name,path in COMPS.items():
        title,rows=parse(f"https://www.rezultati.com/kosarka/{path}/rezultati/")
        if title is None: print(f"{name:20s} HTTP greska"); continue
        n=0
        for d in rows:
            a=which(d.get("WU")); b=which(d.get("WV"))
            if not (a or b): continue
            if d.get("AB")!="3": continue
            ts=int(d.get("AD","0")); dt=datetime.datetime.fromtimestamp(ts,datetime.UTC).strftime("%Y-%m-%d %H:%M")
            found.append((dt,name,d["mid"],d.get("ER",""),d.get("AE"),d.get("AG"),d.get("AH"),d.get("AF"),a,b)); n+=1
        print(f"{name:20s} zapisa={len(rows):4d}  zavrsenih EL-utakmica={n}   | {title[:60]}")
    found=sorted(set(found))
    import os; os.makedirs("/tmp/dom",exist_ok=True)
    json.dump(found,open("/tmp/dom/fs_found.json","w"))
    print("\nUKUPNO:",len(found))
    for f in found: print(f)
