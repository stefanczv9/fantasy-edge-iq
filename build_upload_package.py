#!/usr/bin/env python3
"""Sklapa i provjerava upload paket (ZIP) za GitHub web upload.

  python3 scripts/build_upload_package.py [--zip /home/user/fantasy-edge-iq-refresh-upload.zip] [--overlay /tmp/sim]

--overlay: ne pravi ZIP nego kopira fajlove paketa preko mirror-a zivog sajta (simulacija stanja poslije uploada).
Pravila: bez .github/.git/workflow/eurocup/node_modules; svaki fajl mora postojati i biti neprazan; ZIP se provjerava poslije pravljenja.
"""
import sys, re, json, ast, zipfile, shutil, argparse
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
ROOT_FILES=[
 "BUILD_VERSION.txt","UPLOAD_UPUTSTVO_SR.txt",
 "euroleague-dashboard.html","sr-euroleague-dashboard.html","el-euroleague-dashboard.html",
 "euroleague-defense-vs-position.html","sr-euroleague-defense-vs-position.html","el-euroleague-defense-vs-position.html",
 "euroleague-defense-vs-position.csv","euroleague-defense-vs-position-matchlog.csv",
 "euroleague-players-full.csv","euroleague-team-context.csv","euroleague-next5-schedule.csv","euroleague-shot-share.csv",
 "euroleague-team-analyzer.html",
 "euroleague-domestic-competitions.html","sr-euroleague-domestic-competitions.html","el-euroleague-domestic-competitions.html",
 "domestic-games.csv","domestic-player-boxscores.csv","domestic-team-boxscores.csv","domestic-player-averages.csv",
 "sr-euroleague.html","el-euroleague.html",
 "run_euroleague_auto_refresh.py",
]
DATA_DIR="euroleague_fantasy_data"
DATA_FILES=["fantasheet_style_table.csv","fantasheet_style_table_context.csv","fantasy_poeni_log.csv","igraci_fantasy.csv","igraci_fantasy_augmented.csv","league_config.json",
 "official_2025_26_raw.csv","official_current_raw.csv","official_euroleague_stats.csv","schedule_raw.json","team_advanced_2026.csv","team_context.csv","team_metrics_2026_current.csv",
 "team_next5_schedule_detail.csv","team_next5_schedule_summary.csv","team_opponentsAdvanced_2026.csv","team_opponentsTraditional_2026.csv","utakmice.csv"]
SCRIPTS=["scripts/run_euroleague_auto_refresh.py","scripts/add_minutes_and_pirmin_cards.py","scripts/add_shot_share_section.py","scripts/patch_log_from_official_boxscore.py",
         "scripts/site_audit.py","scripts/build_upload_package.py","scripts/domestic/fs_scan.py","scripts/domestic/fs_box.py","scripts/domestic/sources.py",
         "scripts/domestic/update_domestic.py","scripts/domestic/build_pages.py"]
FORBIDDEN=[".github",".git/","workflow","eurocup","node_modules","__pycache__",".pyc"]

def public_routes():
    """Parsira 'copy A B' iz package.json build skripte -> {A:[B,...]}"""
    pkg=json.load(open(ROOT/"package.json")); b=pkg["scripts"]["build"]
    m={}
    for a,dst in re.findall(r"copy ([^\s;]+) ([^\s;]+);",b): m.setdefault(a,[]).append(dst)
    return m

def manifest():
    files=list(ROOT_FILES)
    files+=[f"{DATA_DIR}/{n}" for n in DATA_FILES]
    files+=SCRIPTS
    routes=public_routes(); pub=[]
    for f in ROOT_FILES:
        if f.endswith((".html",".csv",".txt")) and not f.startswith("run_"):
            pub.append(f"public/{f}")
            for dst in routes.get(f,[]): pub.append(f"public/{dst}")
    # public/ kopije podataka koje paket mijenja
    return files, sorted(set(pub))

def check_files(files):
    bad=[]
    for f in files:
        p=ROOT/f
        if not p.exists() or p.stat().st_size==0: bad.append(f"nedostaje/prazan: {f}")
        low=f.lower()
        for fb in FORBIDDEN:
            if fb in low: bad.append(f"zabranjen sadrzaj ({fb}): {f}")
        if f.endswith(".py"):
            try: ast.parse((ROOT/f).read_text(encoding="utf-8"))
            except SyntaxError as e: bad.append(f"sintaksna greska u {f}: {e}")
    return bad

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--zip",default="/home/user/fantasy-edge-iq-refresh-upload.zip"); ap.add_argument("--overlay"); a=ap.parse_args()
    files,pub=manifest(); allf=files+pub
    bad=check_files(allf)
    if bad:
        print("GRESKE:"); [print("  -",b) for b in bad]; sys.exit(1)
    if a.overlay:
        dst=Path(a.overlay)
        for f in allf:
            if f.startswith(("scripts/","euroleague_fantasy_data/")) or f in("run_euroleague_auto_refresh.py","UPLOAD_UPUTSTVO_SR.txt"): continue
            rel=f[len("public/"):] if f.startswith("public/") else f
            (dst/rel).parent.mkdir(parents=True,exist_ok=True); shutil.copy2(ROOT/f,dst/rel)
        print(f"overlay: {len(allf)} fajlova kopirano preko {dst}"); return
    out=Path(a.zip); tmp=out.with_suffix(".tmp.zip")
    with zipfile.ZipFile(tmp,"w",zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for f in allf: z.write(ROOT/f,arcname=f)
    # provjera nakon pravljenja
    with zipfile.ZipFile(tmp) as z:
        names=z.namelist(); assert z.testzip() is None,"ZIP ostecen"
        assert len(names)==len(set(names))==len(allf),"broj fajlova u ZIP-u ne odgovara manifestu"
        for n in names:
            low=n.lower()
            for fb in FORBIDDEN: assert fb not in low,f"zabranjeno u ZIP-u: {n}"
            assert z.getinfo(n).file_size>0,f"prazan fajl u ZIP-u: {n}"
    assert tmp.stat().st_size>0
    tmp.replace(out)
    print(f"ZIP OK: {out} | {out.stat().st_size/1e6:.2f} MB | {len(allf)} fajlova ({len(files)} korijen/podaci/skripte + {len(pub)} public/)")

if __name__=="__main__": main()
