#!/usr/bin/env python3
"""Pregled cijelog sajta: linkovi, resursi, naslovi, canonical/hreflang, jezicki prekidac, tekstovi, JS greske (jsdom).

Upotreba:
    python3 scripts/site_audit.py https://www.fantasyedgeiq.com  [izlaz.json]
    python3 scripts/site_audit.py http://127.0.0.1:3000          [izlaz.json]   (lokalni public/ preko http.server)
JS provjera trazi node + jsdom u /tmp/jsd (npm i jsdom); ako ga nema, preskace se.
"""
import sys, re, json, subprocess, concurrent.futures as cf
from urllib.parse import urljoin, urlparse, urldefrag
from pathlib import Path
import requests
from bs4 import BeautifulSoup

BASE=(sys.argv[1] if len(sys.argv)>1 else "https://www.fantasyedgeiq.com").rstrip("/")
OUT=sys.argv[2] if len(sys.argv)>2 else "/tmp/audit/site_audit.json"
UA={"User-Agent":"Mozilla/5.0 FEIQ-audit"}
HOST=urlparse(BASE).netloc
sess=requests.Session(); sess.headers.update(UA)
_cache={}
def fetch(url, want_body=False):
    key=(url,want_body)
    if key in _cache: return _cache[key]
    try:
        r=sess.get(url,timeout=40,allow_redirects=True)
        res=(r.status_code,r.headers.get("content-type",""),r.text if want_body and "text" in r.headers.get("content-type","") or (want_body and "xml" in r.headers.get("content-type","")) else "",r.url,len(r.content))
    except Exception as e:
        res=(0,"",str(e)[:100],url,0)
    _cache[key]=res; return res
def norm(u): return urldefrag(u)[0].rstrip("/") if urlparse(u).path not in("","/") else urldefrag(u)[0].rstrip("/")+"/"

issues=[]; pages={}
def add(sev,page,msg): issues.append({"sev":sev,"page":page,"msg":msg})

# 1) pocetne stranice: sitemap + osnovne rute
start={BASE+"/",BASE+"/sr",BASE+"/el"}
code,ct,body,_,_=fetch(BASE+"/sitemap.xml",True)
sitemap_urls=re.findall(r"<loc>([^<]+)</loc>",body) if code==200 else []
if code!=200: add("ERROR","/sitemap.xml",f"HTTP {code}")
for u in sitemap_urls:
    u2=u.replace("https://www.fantasyedgeiq.com",BASE); start.add(u2)
todo=list(start); seen=set()
while todo:
    u=todo.pop()
    nu=norm(u)
    if nu in seen: continue
    seen.add(nu)
    code,ct,body,final,size=fetch(u,True)
    pages[nu]={"status":code,"final":final,"size":size,"ctype":ct}
    if code!=200: add("ERROR",u.replace(BASE,"") or "/",f"HTTP {code}"); continue
    if "html" not in ct: continue
    s=BeautifulSoup(body,"lxml"); p=pages[nu]
    p["title"]=(s.title.get_text(strip=True) if s.title else "")
    p["lang"]=(s.html.get("lang") if s.html else None)
    p["h1"]=[h.get_text(" ",strip=True) for h in s.find_all("h1")]
    md=s.find("meta",attrs={"name":"description"}); p["desc"]=md.get("content","") if md else ""
    cn=s.find("link",rel="canonical"); p["canonical"]=cn.get("href") if cn else None
    p["hreflang"]={l.get("hreflang"):l.get("href") for l in s.find_all("link",rel="alternate") if l.get("hreflang")}
    path=urlparse(u).path or "/"
    if not p["title"]: add("WARN",path,"nema <title>")
    if not p["desc"]: add("WARN",path,"nema meta description")
    if not p["h1"]: add("WARN",path,"nema <h1>")
    if len(p["h1"])>1: add("INFO",path,f"vise <h1>: {len(p['h1'])}")
    if not p["canonical"]: add("WARN",path,"nema canonical")
    # jezik vs putanja
    exp="sr" if path.startswith("/sr") else "el" if path.startswith("/el") else "en"
    if p["lang"] and p["lang"]!=exp and not path.endswith((".csv",".xml")): add("WARN",path,f"html lang={p['lang']} a putanja je {exp}")
    # tekstovi
    low=body
    for pat,sev,msg in [(r"EuroCup","INFO","spominje EuroCup (EuroCup sekcija postoji na sajtu)"),(r"\bundefined\b(?![\w'(])","INFO","tekst 'undefined' u HTML-u")]:
        if re.search(pat,re.sub(r"<script.*?</script>","",body,flags=re.S)): add(sev,path,msg)
    # linkovi
    links=set()
    for a in s.find_all("a",href=True):
        h=a["href"].strip()
        if not h or h.startswith(("mailto:","tel:","javascript:","#")): continue
        full=urljoin(u,h)
        links.add(full)
    assets=set()
    for tag,attr in [("link","href"),("script","src"),("img","src"),("source","src")]:
        for el in s.find_all(tag):
            if el.get(attr) and not (tag=="link" and el.get("rel") and any(r in ("canonical","alternate") for r in el.get("rel"))):
                assets.add(urljoin(u,el[attr]))
    for m in s.find_all("meta",property=re.compile(r"^og:image$")):
        if m.get("content"): assets.add(urljoin(u,m["content"]))
    p["links"]=sorted(links); p["assets"]=sorted(assets)
    for l in links:
        pu=urlparse(l)
        if pu.netloc in(HOST,"www.fantasyedgeiq.com","fantasyedgeiq.com") or (BASE.startswith("http://127") and pu.netloc==HOST):
            l2=l.replace("https://www.fantasyedgeiq.com",BASE)
            if norm(l2) not in seen and not re.search(r"\.(csv|png|jpg|svg|xml|txt|webmanifest|ico|zip|xlsx)$",pu.path): todo.append(l2)

# 2) provjera svih internih linkova i resursa (status)
checked={}
def check(url):
    if "/_vercel/" in url: return url,None   # postoji samo na Vercel-u
    u=url.replace("https://www.fantasyedgeiq.com",BASE) if urlparse(url).netloc in("www.fantasyedgeiq.com","fantasyedgeiq.com") else url
    if urlparse(u).netloc!=HOST: return u,None
    c,ct,b,final,size=fetch(u,False); return u,(c,size)
all_urls=set()
for nu,p in pages.items():
    for l in p.get("links",[])+p.get("assets",[]): all_urls.add(l)
with cf.ThreadPoolExecutor(12) as ex:
    for u,res in ex.map(check,sorted(all_urls)):
        if res: checked[u]=res
broken=[(u,r) for u,r in checked.items() if r[0]!=200 or (r[0]==200 and r[1]==0)]
for u,r in broken:
    src=[nu.replace(BASE,"") or "/" for nu,p in pages.items() if u in p.get("links",[])+p.get("assets",[]) or u.replace(BASE,"https://www.fantasyedgeiq.com") in p.get("links",[])+p.get("assets",[])]
    add("ERROR",", ".join(src[:3]),f"neispravan link/resurs: {u.replace(BASE,'')} -> HTTP {r[0]}")

# 3) hreflang / canonical konzistentnost
for nu,p in pages.items():
    if "canonical" not in p: continue
    path=urlparse(nu).path or "/"
    for lang,href in p["hreflang"].items():
        h=href.replace("https://www.fantasyedgeiq.com",BASE)
        c=fetch(h,False)[0]
        if c!=200: add("ERROR",path,f"hreflang {lang} -> {href} vraca HTTP {c}")
    if p["canonical"]:
        ch=p["canonical"].replace("https://www.fantasyedgeiq.com",BASE)
        if norm(ch)!=nu and not (path=="/euroleague" and ch.endswith("/euroleague/dashboard")):
            add("INFO",path,f"canonical {p['canonical']} != putanja")

# 4) JS izvrsavanje (jsdom) za sve html stranice sa skriptama
js_results={}
if Path("/tmp/jsd/node_modules/jsdom").exists():
    import tempfile,os
    def js_check(item):
        nu,p=item
        if p.get("status")!=200 or "html" not in p.get("ctype",""): return nu,None
        code,ct,body,_,_=fetch(nu,True)
        f=tempfile.NamedTemporaryFile("w",suffix=".html",delete=False,encoding="utf-8"); f.write(body); f.close()
        try:
            r=subprocess.run(["node","/tmp/jsd/click_tabs.js",f.name],capture_output=True,text=True,timeout=120,cwd="/tmp/jsd")
            out=json.loads(r.stdout.strip().splitlines()[-1]) if r.stdout.strip() else {"errors":["nema izlaza: "+r.stderr[:150]]}
        except Exception as e:
            out={"errors":[str(e)[:150]]}
        finally: os.unlink(f.name)
        return nu,out
    items=[(nu,p) for nu,p in pages.items() if p.get("ctype","").startswith("text/html") and p.get("size",0)>50000]
    with cf.ThreadPoolExecutor(3) as ex:
        for nu,out in ex.map(js_check,items):
            if out is None: continue
            js_results[nu]=out
            path=urlparse(nu).path or "/"
            for e in out.get("errors",[]): add("ERROR",path,"JS greska: "+e)
            for tab,v in out.get("tabs",{}).items():
                if v["tableRows"] and all(r==0 for r in v["tableRows"]): add("WARN",path,f"tab '{tab}': tabela prazna")

res={"base":BASE,"pages":{k:{x:y for x,y in v.items() if x not in("links","assets")} for k,v in pages.items()},"issues":issues,"js":{k:{"errors":v.get("errors"),"tabs":v.get("tabs")} for k,v in js_results.items()},
     "counts":{"stranica":len(pages),"provjerenih_linkova_resursa":len(checked)}}
Path(OUT).parent.mkdir(parents=True,exist_ok=True); json.dump(res,open(OUT,"w"),ensure_ascii=False,indent=1)
print(f"BASE {BASE} | stranica: {len(pages)} | provjerenih linkova/resursa: {len(checked)} | JS provjera: {len(js_results)} stranica")
order={"ERROR":0,"WARN":1,"INFO":2}
for it in sorted(issues,key=lambda x:(order[x['sev']],x['page'])): print(f"[{it['sev']:5s}] {it['page']:48s} {it['msg']}")
print("\nSAZETAK:",{s:sum(1 for i in issues if i['sev']==s) for s in ("ERROR","WARN","INFO")})
