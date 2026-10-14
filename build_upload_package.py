#!/usr/bin/env python3
"""Create and VERIFY a flat EuroLeague + EuroCup static upload and a separate source/data archive.

BCL is a standalone in-chat table, NOT a website update. Never include BCL, home/index,
build.js, package.json, vercel.json, sitemap or workflows in either release archive.
Run only after the refresh and source-validation scripts have passed.
"""
from pathlib import Path
import argparse,ast,hashlib,json,re,shutil,sys,zipfile

ROOT=Path(__file__).resolve().parents[1]
SITE_FILES=['BUILD_VERSION.txt']
for comp in ['euroleague','eurocup']:
    for page in ['dashboard','defense-vs-position','domestic-competitions']:
        SITE_FILES += [f'{prefix}{comp}-{page}.html' for prefix in ['', 'sr-', 'el-']]
    SITE_FILES += [f'{comp}-{name}.csv' for name in ['defense-vs-position','defense-vs-position-matchlog','players-full','team-context','next5-schedule','shot-share']]
SITE_FILES += ['euroleague-team-analyzer.html','sr-euroleague.html','el-euroleague.html',
               'domestic-games.csv','domestic-player-boxscores.csv','domestic-team-boxscores.csv','domestic-player-averages.csv']
PROTECTED={'index.html','sr-index.html','el-index.html','build.js','package.json','vercel.json','sitemap.xml','robots.txt',
           'favicon.svg','site.webmanifest','og-image.png','apple-touch-icon.png'}
FORBIDDEN=['.github','.git/','workflow','bcl','node_modules','__pycache__','.pyc','.bak']
SCRIPTS=['scripts/run_euroleague_auto_refresh.py','scripts/add_minutes_and_pirmin_cards.py','scripts/add_shot_share_section.py',
         'scripts/patch_average_pir_card.py','scripts/patch_log_from_official_boxscore.py','scripts/site_audit.py','scripts/build_upload_package.py',
         'scripts/domestic/fs_scan.py','scripts/domestic/fs_box.py','scripts/domestic/sources.py','scripts/domestic/update_domestic.py','scripts/domestic/build_pages.py',
         'scripts/eurocup/eurocup_dvp.py','scripts/eurocup/refresh_eurocup.py','scripts/eurocup/audit_eurocup.py',
         'scripts/create_fantasheet_style_dashboard_fixed.py','scripts/audit_el_vs_official.py',
         # Explicit dependencies for the EuroCup-only refresh (also restored by the existing EuroLeague runner).
         'scripts/create_euroleague_advanced_context.py','scripts/apply_advanced_proj_pir_formula.py']
EL_DATA=['fantasheet_style_table.csv','fantasheet_style_table_context.csv','fantasy_poeni_log.csv','igraci_fantasy.csv',
         'igraci_fantasy_augmented.csv','league_config.json','official_2025_26_raw.csv','official_current_raw.csv','official_euroleague_stats.csv',
         'schedule_raw.json','team_advanced_2026.csv','team_context.csv','team_metrics_2026_current.csv','team_next5_schedule_detail.csv',
         'team_next5_schedule_summary.csv','team_opponentsAdvanced_2026.csv','team_opponentsTraditional_2026.csv','utakmice.csv']
EC_DATA=['fantasy_poeni_log.csv','official_current_raw.csv','official_games.csv','official_boxscores_2026.json','refresh_sources.json',
         'reconciled-results.json','official-players-not-in-fantasy.json','players_current_matched.csv','team_context.csv',
         'team_next5_schedule_detail.csv','team_next5_schedule_summary.csv','utakmice.csv','refresh-summary.json','fantasheet_style_table_context.csv']
README='UPLOAD_UPUTSTVO_SR.md'


def SUPPORT_FILES():
    return ['run_euroleague_auto_refresh.py','requirements.txt',README]+SCRIPTS+['euroleague_fantasy_data/'+n for n in EL_DATA]+['eurocup_fantasy_data/'+n for n in EC_DATA]


def read_stamp(name):
    text=(ROOT/name).read_text(encoding='utf-8')
    m=re.search(r'"generated":"([^"]+)"',text)
    return m.group(1) if m else None


def check_paths(names,flat=False):
    errors=[]
    if len(names)!=len(set(names)):errors.append('Duplicate filenames')
    for n in names:
        p=ROOT/n
        if flat and '/' in n:errors.append('Not flat: '+n)
        if n in PROTECTED or Path(n).name in PROTECTED:errors.append('Protected file: '+n)
        if '..' in Path(n).parts or Path(n).is_absolute():errors.append('Unsafe archive name: '+n)
        if any(x in n.lower() for x in FORBIDDEN):errors.append('Forbidden file: '+n)
        if not p.is_file() or p.stat().st_size==0:errors.append('Missing/empty: '+n)
        elif n.endswith('.py'):
            try:ast.parse(p.read_text(encoding='utf-8'))
            except SyntaxError as e:errors.append(str(e))
    return errors


def check_site():
    errors=check_paths(SITE_FILES,flat=True)
    el={read_stamp(f'{p}euroleague-dashboard.html') for p in ['', 'sr-', 'el-']}
    el.add(read_stamp('euroleague-team-analyzer.html'))
    ec={read_stamp(f'{p}eurocup-dashboard.html') for p in ['', 'sr-', 'el-']}
    if len(el)!=1 or None in el:errors.append('EuroLeague timestamp mismatch')
    if len(ec)!=1 or None in ec:errors.append('EuroCup timestamp mismatch')
    version=(ROOT/'BUILD_VERSION.txt').read_text()
    for s in list(el)+list(ec):
        if s and s not in version:errors.append('BUILD_VERSION missing '+s)
    # Every embedded data blob must be valid strict JSON, including localized pages.
    for n in SITE_FILES:
        if not n.endswith('.html'):continue
        t=(ROOT/n).read_text();i=t.find('const DATA=')
        if i<0:continue
        i+=len('const DATA=')
        if t[i:].startswith('{summary:'):i+=len('{summary:')
        try:json.JSONDecoder(parse_constant=lambda x:(_ for _ in ()).throw(ValueError(x))).raw_decode(t[i:])
        except (ValueError,json.JSONDecodeError) as e:errors.append(f'Invalid embedded JSON in {n}: {e}')
    # Current-season Shot Share may not silently use the blended team context denominator.
    import pandas as pd
    for comp,src in [('euroleague','euroleague_fantasy_data/team_metrics_2026_current.csv'),('eurocup','eurocup_fantasy_data/team_context.csv')]:
        sh=pd.read_csv(ROOT/f'{comp}-shot-share.csv');tm=pd.read_csv(ROOT/src)
        j=sh.merge(tm[['team_abbr','for_fga_pg']],on='team_abbr',how='left')
        if len(j)!=len(sh) or j.for_fga_pg.isna().any() or (j.team_fga_pg-j.for_fga_pg).abs().max()>.011:
            errors.append(comp+' Shot Share denominator is not current-season team FGA')
        if (sh.shot_share_pct-(100*sh.player_fga_pg/sh.team_fga_pg).round(1)).abs().max()>.001:
            errors.append(comp+' Shot Share formula mismatch')
    return errors,{n:read_stamp(n) for n in ['euroleague-dashboard.html','eurocup-dashboard.html']}


def zip_files(out,names):
    out=Path(out);tmp=out.with_suffix('.tmp.zip');out.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for n in names:z.write(ROOT/n,arcname=n)
    with zipfile.ZipFile(tmp) as z:
        assert z.testzip() is None,'ZIP CRC failure'
        assert z.namelist()==names and len(names)==len(set(names))
        for n in names:
            assert hashlib.sha256(z.read(n)).digest()==hashlib.sha256((ROOT/n).read_bytes()).digest(),n
    tmp.replace(out);return out.stat().st_size


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--site-zip',default='/home/user/EL-EC-sajt-2026-10-14.zip')
    ap.add_argument('--support-zip',default='/home/user/EL-EC-skripte-2026-10-14.zip')
    a=ap.parse_args()
    bad,stamps=check_site();bad+=check_paths(SUPPORT_FILES())
    if bad:
        print('STOP:',*bad,sep='\n');sys.exit(1)
    for dest,names in [(a.site_zip,SITE_FILES),(a.support_zip,SUPPORT_FILES())]:
        size=zip_files(dest,names);print(f'VERIFIED {dest} | {len(names)} files | {size/1e6:.2f} MB')
    print('Timestamps:',stamps)
    print('No BCL website files, indexes/home, build or workflows.')

if __name__=='__main__':main()
