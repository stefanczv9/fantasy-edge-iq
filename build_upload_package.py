#!/usr/bin/env python3
"""Pravi i strogo provjerava upload pakete za GitHub web upload.

  python3 scripts/build_upload_package.py            -> pravi oba ZIP-a
  python3 scripts/build_upload_package.py --overlay /tmp/sim   -> simulacija: kopira fajlove paketa preko mirror-a zivog sajta
                                                     kao sto bi to uradio 'npm run build' (korijen + rute iz package.json)

PAKET 1  fantasy-edge-iq-site-upload.zip      RAVAN (bez podfoldera): samo korijenski fajlovi sajta (.html/.csv/.txt).
         Upload: svi fajlovi u KORIJEN repoa. Vercel sam pravi public/ i rute iz korijenskih fajlova (npm run build).
         Zasto ravan: u ZIP-u nema nijednog fajla imena index*.html, pa ni pri 'spljostenom' uploadu ne moze prepisati pocetnu.
PAKET 2  fantasy-edge-iq-skripte-i-podaci.zip  neobavezno: scripts/, euroleague_fantasy_data/, runner (za osvjezavanja, sajt ih ne koristi)

Pocetne stranice (index, sr-index, el-index), sitemap, robots, package.json, vercel.json i EuroCup su ZASTICENI: nikad u paketu.
"""
import sys, re, json, ast, zipfile, shutil, argparse, hashlib
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
SITE_FILES=[
 "BUILD_VERSION.txt",
 "euroleague-dashboard.html","sr-euroleague-dashboard.html","el-euroleague-dashboard.html",
 "euroleague-defense-vs-position.html","sr-euroleague-defense-vs-position.html","el-euroleague-defense-vs-position.html",
 "euroleague-defense-vs-position.csv","euroleague-defense-vs-position-matchlog.csv",
 "euroleague-players-full.csv","euroleague-team-context.csv","euroleague-next5-schedule.csv","euroleague-shot-share.csv",
 "euroleague-team-analyzer.html",
 "euroleague-domestic-competitions.html","sr-euroleague-domestic-competitions.html","el-euroleague-domestic-competitions.html",
 "domestic-games.csv","domestic-player-boxscores.csv","domestic-team-boxscores.csv","domestic-player-averages.csv",
 "sr-euroleague.html","el-euroleague.html",
]
PROTECTED={"index.html","sr-index.html","el-index.html","sitemap.xml","robots.txt","package.json","vercel.json","favicon.svg","site.webmanifest","og-image.png","apple-touch-icon.png"}
DATA_DIR="euroleague_fantasy_data"
DATA_FILES=["fantasheet_style_table.csv","fantasheet_style_table_context.csv","fantasy_poeni_log.csv","igraci_fantasy.csv","igraci_fantasy_augmented.csv","league_config.json",
 "official_2025_26_raw.csv","official_current_raw.csv","official_euroleague_stats.csv","schedule_raw.json","team_advanced_2026.csv","team_context.csv","team_metrics_2026_current.csv",
 "team_next5_schedule_detail.csv","team_next5_schedule_summary.csv","team_opponentsAdvanced_2026.csv","team_opponentsTraditional_2026.csv","utakmice.csv"]
SCRIPTS=["scripts/run_euroleague_auto_refresh.py","scripts/add_minutes_and_pirmin_cards.py","scripts/add_shot_share_section.py","scripts/patch_average_pir_card.py",
         "scripts/patch_log_from_official_boxscore.py","scripts/site_audit.py","scripts/build_upload_package.py","scripts/domestic/fs_scan.py","scripts/domestic/fs_box.py",
         "scripts/domestic/sources.py","scripts/domestic/update_domestic.py","scripts/domestic/build_pages.py"]
FORBIDDEN=[".github",".git/","workflow","eurocup","node_modules","__pycache__",".pyc"]
SUPPORT_README="UPLOAD_UPUTSTVO_SR.md"

def read_stamp(name):
    t=(ROOT/name).read_text(encoding="utf-8")
    m=re.search(r'generated\W{1,3}([0-9-]{10} [0-9:]{5})',t); return m.group(1) if m else None

def check_site():
    bad=[]
    for f in SITE_FILES:
        p=ROOT/f; low=f.lower()
        if "/" in f or "\\" in f: bad.append(f"podfolder u ravnom paketu: {f}")
        if f in PROTECTED or re.match(r"^index",low): bad.append(f"zasticen fajl u paketu: {f}")
        if not f.endswith((".html",".csv",".txt")): bad.append(f"nedozvoljena ekstenzija: {f}")
        if any(x in low for x in FORBIDDEN): bad.append(f"zabranjeno: {f}")
        if not p.exists() or p.stat().st_size==0: bad.append(f"nedostaje/prazan: {f}")
    if len(set(SITE_FILES))!=len(SITE_FILES): bad.append("duplikati u popisu")
    stamps={f:read_stamp(f) for f in ("euroleague-dashboard.html","sr-euroleague-dashboard.html","el-euroleague-dashboard.html","euroleague-team-analyzer.html") if (ROOT/f).exists()}
    if len(set(stamps.values()))!=1: bad.append(f"razliciti pecati u dashboardima/analyzeru: {stamps}")
    bv=(ROOT/"BUILD_VERSION.txt").read_text(encoding="utf-8")
    if stamps and next(iter(stamps.values())) not in bv: bad.append("BUILD_VERSION ne sadrzi pecat dashboarda")
    return bad,stamps

def check_support():
    bad=[]
    for f in SUPPORT_FILES():
        p=ROOT/f
        if not p.exists() or p.stat().st_size==0: bad.append(f"nedostaje/prazan: {f}")
        if any(x in f.lower() for x in FORBIDDEN): bad.append(f"zabranjeno: {f}")
        if f.endswith(".py") and p.exists():
            try: ast.parse(p.read_text(encoding="utf-8"))
            except SyntaxError as e: bad.append(f"sintaksna greska u {f}: {e}")
    return bad
def SUPPORT_FILES(): return ["run_euroleague_auto_refresh.py"]+SCRIPTS+[f"{DATA_DIR}/{n}" for n in DATA_FILES]

def route_map():
    b=json.load(open(ROOT/"package.json"))["scripts"]["build"]; m={}
    for a,dst in re.findall(r"copy ([^\s;]+) ([^\s;]+);",b): m.setdefault(a,[]).append(dst)
    return m

def zip_files(out,items,readme=None):
    tmp=out.with_suffix(".tmp.zip")
    with zipfile.ZipFile(tmp,"w",zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for arc,src in items: z.write(src,arcname=arc)
        if readme: z.writestr(SUPPORT_README,readme)
    with zipfile.ZipFile(tmp) as z:
        names=z.namelist(); assert z.testzip() is None,"ZIP ostecen"
        assert len(names)==len(set(names)),"duplikati u ZIP-u"
        for n in names:
            assert not any(x in n.lower() for x in FORBIDDEN),f"zabranjeno u ZIP-u: {n}"
            assert z.getinfo(n).file_size>0,f"prazan fajl: {n}"
        for arc,src in items: assert hashlib.md5(z.read(arc)).hexdigest()==hashlib.md5(Path(src).read_bytes()).hexdigest(),f"razlika: {arc}"
    assert tmp.stat().st_size>0; tmp.replace(out); return len(names)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--site-zip",default="/home/user/fantasy-edge-iq-site-upload.zip"); ap.add_argument("--support-zip",default="/home/user/fantasy-edge-iq-skripte-i-podaci.zip"); ap.add_argument("--overlay"); a=ap.parse_args()
    bad,stamps=check_site(); bad+=check_support()
    if bad:
        print("GRESKE:"); [print("  -",b) for b in bad]; sys.exit(1)
    if a.overlay:
        dst=Path(a.overlay); rm=route_map(); n=0
        for f in SITE_FILES:
            (dst/f).parent.mkdir(parents=True,exist_ok=True); shutil.copy2(ROOT/f,dst/f); n+=1
            for r in rm.get(f,[]):
                (dst/r).parent.mkdir(parents=True,exist_ok=True); shutil.copy2(ROOT/f,dst/r); n+=1
        print(f"overlay (kao build): {len(SITE_FILES)} korijenskih fajlova + rute = {n} kopija preko {dst}"); return
    site=Path(a.site_zip); sup=Path(a.support_zip)
    n1=zip_files(site,[(f,ROOT/f) for f in SITE_FILES])
    readme=(ROOT/"UPLOAD_UPUTSTVO_SR.md").read_text(encoding="utf-8") if (ROOT/"UPLOAD_UPUTSTVO_SR.md").exists() else "Skripte i podaci za osvjezavanje. Sajt ih ne koristi."
    n2=zip_files(sup,[(f,ROOT/f) for f in SUPPORT_FILES()],readme=readme)
    print(f"PAKET 1 (ravan, sajt): {site} | {site.stat().st_size/1e6:.2f} MB | {n1} fajlova | pecat {next(iter(stamps.values()))}")
    print(f"PAKET 2 (skripte+podaci): {sup} | {sup.stat().st_size/1e6:.2f} MB | {n2} fajlova")

if __name__=="__main__": main()
