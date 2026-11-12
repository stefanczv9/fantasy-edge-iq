#!/usr/bin/env python3
"""Refresh ALL existing EuroCup sections, EN/SR/EL, without modifying routes, home or workflows.

Official 2026-27 player and team statistics + public EuroCup fantasy prices/status,
all schedule matchdays, current-only shot share, model projections and real-points DvP.
Completed official results override a stale fantasy 'playing' flag. No future games are counted.

Run after eurocup_dvp.py (which creates the fantasy log):
  python3 scripts/eurocup/eurocup_dvp.py --no-pages
  python3 scripts/eurocup/refresh_eurocup.py
Development-only --cached reuses the saved sources; never re-labels old sources as a new fetch.
"""
from __future__ import annotations
import concurrent.futures as cf
import datetime as dt
import importlib.util
import json
import math
import re
import sys
import types
import warnings
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from euroleague_api.game_stats import GameStats
from euroleague_api.player_stats import PlayerStats

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
DATA=ROOT/'eurocup_fantasy_data'
DATA.mkdir(exist_ok=True)
sys.path.insert(0,str(HERE))
import eurocup_dvp as dv
TZ=ZoneInfo('Europe/Zagreb')
# Verified spellings of the same players within the same club, not fuzzy guesses.
NAME_ALIASES={'Gary Browne':'Gary Browne Ramirez','Stefan Dordevic':'Stefan Djordjevic','Elias Roedl':'Elias Rodl',
              'Ugo Doumbia Niang':'Ugo Doumbia','Raymond Somerville':'Raymond Sommerville','Blazej Kulikowski':'Blazej Kulikowksi'}
CACHE=DATA/'refresh_sources.json'


def load_module(name,path,source=None):
    m=types.ModuleType(name);m.__file__=str(path);sys.modules[name]=m
    exec(compile(source if source is not None else path.read_text(encoding='utf-8'),str(path),'exec'),m.__dict__)
    return m


def fetch_sources():
    cfg=dv.get_json(f'{dv.BASE}/leagues/11/config')['data']
    old=pd.read_csv(ROOT/'eurocup-players-full.csv')
    ids=sorted(set(int(x) for x in old.player_id.dropna()))
    def prof(pid):
        j=dv.get_json(f'{dv.BASE}/players/{pid}/profile',{'league':11})
        d=(j or {}).get('data') or {}
        if not d.get('team') or not d.get('position'):raise RuntimeError(f'Missing active profile {pid}; refusing partial export')
        return d
    with cf.ThreadPoolExecutor(18) as ex: profiles=list(ex.map(prof,ids))
    sid=cfg['current_schedule_id']
    def sched(md):
        j=dv.get_json(f'{dv.BASE}/schedules/{sid}/matchdays/{md["id"]}')
        if not j or 'data' not in j:raise RuntimeError(f'Missing matchday {md["number"]}')
        return j['data']
    with cf.ThreadPoolExecutor(8) as ex: rounds=list(ex.map(sched,cfg['matchdays']))
    ps=PlayerStats('U');official=ps.get_player_stats_single_season('traditional',2026,phase_type_code=None,statistic_mode='Accumulated')
    if official is None or official.empty:raise RuntimeError('Official current player data empty')
    official.to_csv(DATA/'official_current_raw.csv',index=False)
    gs=GameStats('U');codes=gs.get_gamecodes_season(2026);codes=codes[codes.played.astype(bool)].copy()
    codes.to_csv(DATA/'official_games.csv',index=False)
    cb=DATA/'official_boxscores_2026.json'; boxes=json.loads(cb.read_text()) if cb.exists() else {}
    # Always fetch current boxes. Revisions to old official games must not be hidden by a stale cache.
    def box(code):
        b=gs.get_game_stats(2026,int(code))
        if b is None or b.empty:raise RuntimeError(f'Missing official box {code}')
        return str(int(code)),b.to_dict('records')[0]
    with cf.ThreadPoolExecutor(5) as ex:
        for k,v in ex.map(box,codes.gameCode):boxes[k]=v
    cb.write_text(json.dumps(boxes,ensure_ascii=False,default=str),encoding='utf-8')
    raw={'config':cfg,'profiles':profiles,'rounds':rounds,'source_fetched':dt.datetime.now(TZ).isoformat()}
    CACHE.write_text(json.dumps(raw,ensure_ascii=False),encoding='utf-8')
    return raw,official,codes,boxes


def make_matches(raw,official,codes):
    # Official game codes and official player TV codes refer to the same team. Do not guess by abbreviations.
    cmap={}
    for _,p in official.iterrows():
        for code,ab in zip(str(p['player.team.code']).split(';'),str(p['player.team.tvCodes']).split(';')):
            cmap[code]=ab
    code_rows=[]
    for _,g in codes.iterrows():
        code_rows.append({'official_game':int(g.gameCode),'date':pd.to_datetime(g.date,format='%b %d, %Y').date(),
                          'home_abbr':cmap[g.homecode],'away_abbr':cmap[g.awaycode],'hs':int(g.homescore),'as':int(g.awayscore)})
    rows=[];reconciled=[];covered=set()
    for rd in raw['rounds']:
        for turn in rd.get('rounds',[]):
            for m in turn.get('matches',[]):
                h,a=m.get('home_team') or {},m.get('away_team') or {}
                loc=dv.to_local(m.get('started_at'))
                r={'match_id':int(m['id']),'matchday':int(rd['number']),'matchday_id':rd['id'],'status':m.get('status'),
                   'start_utc':m.get('started_at'),'start_local':loc,'home_abbr':h.get('abbreviation'),'away_abbr':a.get('abbreviation'),
                   'home_team':h.get('name'),'away_team':a.get('name'),'home_score':h.get('score'),'away_score':a.get('score'),
                   'official_game':None,'source_status':'fantasy'}
                d=dt.date.fromisoformat(loc[:10]) if loc else None
                cand=[x for x in code_rows if x['home_abbr']==r['home_abbr'] and x['away_abbr']==r['away_abbr'] and abs((x['date']-d).days)<=1]
                if len(cand)>1:raise RuntimeError(f'Ambiguous official match for {r}')
                if cand:
                    o=cand[0];covered.add(o['official_game'])
                    if r['status']!='played' or r['home_score']!=o['hs'] or r['away_score']!=o['as']:
                        reconciled.append({'match_id':r['match_id'],'old_status':r['status'],'old_score':[r['home_score'],r['away_score']],
                                           'official_game':o['official_game'],'official_score':[o['hs'],o['as']]})
                    r.update(status='played',home_score=o['hs'],away_score=o['as'],official_game=o['official_game'],source_status='official EuroCup final')
                elif r['status']=='played':
                    raise RuntimeError(f'Fantasy game {r["match_id"]} is played but no official final was found')
                rows.append(r)
    if covered!=set(codes.gameCode.astype(int)):raise RuntimeError(f'Missing official games from schedule: {set(codes.gameCode.astype(int))-covered}')
    (DATA/'reconciled-results.json').write_text(json.dumps(reconciled,ensure_ascii=False,indent=2),encoding='utf-8')
    for r in reconciled:print('OFFICIAL result/status correction:',r,flush=True)
    matches=pd.DataFrame(rows).sort_values(['start_local','match_id']);matches.to_csv(DATA/'utakmice.csv',index=False)
    return matches


def finalize_log(matches,codes,boxes):
    p=DATA/'fantasy_poeni_log.csv'
    if not p.exists():raise RuntimeError('Run eurocup_dvp.py --no-pages first to obtain the raw fantasy log')
    log=pd.read_csv(p)
    for g in matches[matches.status.eq('played')].itertuples():
        ix=log.match_id.eq(g.match_id);home=log.home_away.eq('H')
        if not ix.any():raise RuntimeError(f'No fantasy log for completed match {g.match_id}')
        log.loc[ix,'match_status']='played';log.loc[ix,'home_score']=g.home_score;log.loc[ix,'away_score']=g.away_score
        log.loc[ix&home,'team_score']=g.home_score;log.loc[ix&home,'opponent_score']=g.away_score
        log.loc[ix&~home,'team_score']=g.away_score;log.loc[ix&~home,'opponent_score']=g.home_score
    log.to_csv(p,index=False)
    patch=load_module('ec_official_patch',ROOT/'scripts/patch_log_from_official_boxscore.py')
    patch.LOG_PATH=p
    class CachedOfficial:
        def get_gamecodes_season(self,season):return codes.copy()
        def get_game_stats(self,season,code):return pd.DataFrame([boxes[str(int(code))]])
    import euroleague_api.game_stats as gm
    orig=gm.GameStats;gm.GameStats=lambda comp='E':CachedOfficial()
    try:patch.main()
    finally:gm.GameStats=orig
    log=pd.read_csv(p)
    ml,d=dv.compute_dvp(log,{t['abbreviation']:t['name'] for t in json.loads(CACHE.read_text())['config']['teams']})
    if len(ml)!=2*len(codes) or not ml.validation_ok.all():
        raise RuntimeError('EuroCup DvP does not validate every official final; refusing publication')
    d.to_csv(ROOT/'eurocup-defense-vs-position.csv',index=False);ml.to_csv(ROOT/'eurocup-defense-vs-position-matchlog.csv',index=False)
    return log,d,ml


def current_players(raw,official,log,matches):
    p_rows=[]
    for x in raw['profiles']:
        t=x['team'];pos=x['position']['name']
        p_rows.append({'player_id':int(x['id']),'name':f"{x.get('first_name') or ''} {x.get('last_name') or ''}".strip(),
         'first_name':x.get('first_name'),'last_name':x.get('last_name'),'position':pos,'pos_short':{'Guard':'G','Forward':'F','Center':'C','Head Coach':'HC'}.get(pos),
         'team_abbr':t['abbreviation'],'team_name':t['name'],'team_id':t['id'],'jersey':x.get('jersey'),'price':x.get('quotation'),
         'price_change':x.get('total_plus'),'popularity_pct':None if x.get('popularity') is None else round(100*x['popularity'],2),
         'is_injured':bool(x.get('is_injured')),'started_from_bench':bool(x.get('started_from_bench')),'is_on_fire':x.get('is_on_fire')})
    p=pd.DataFrame(p_rows);patch=load_module('ec_name_pairing',ROOT/'scripts/patch_log_from_official_boxscore.py')
    off=official.copy();off['full']=off['player.name'].map(patch.official_to_full)
    mapping={};unmatched=[]
    for ab,g in p[p.pos_short.ne('HC')].groupby('team_abbr'):
        oo=off[off['player.team.tvCodes'].str.split(';').map(lambda codes:ab in codes)]
        lp=[{'name':r['name'],'stats':{},'index':i} for i,r in g.iterrows()]
        op=[{'full_name':NAME_ALIASES.get(r['full'],r['full']),'minutes':r['minutesPlayed'],'position':'','stats':{},'index':i} for i,r in oo.iterrows()]
        pairs,_,uo=patch.pair_players(lp,op)
        for a,b in pairs:mapping[lp[a]['index']]=op[b]['index']
        unmatched += [{'team':ab,'name':op[j]['full_name']} for j in uo]
    print('EuroCup official player matching:',len(mapping),'matched;',len(unmatched),'not in fantasy list',unmatched,flush=True)
    (DATA/'official-players-not-in-fantasy.json').write_text(json.dumps(unmatched,ensure_ascii=False,indent=2),encoding='utf-8')
    stats={
     'gamesPlayed':'gp_current','minutesPlayed':'min_total_current','pir':'pir_total_current','pointsScored':'pts_total_current',
     'totalRebounds':'reb_total_current','offensiveRebounds':'oreb_total_current','defensiveRebounds':'dreb_total_current','assists':'ast_total_current',
     'steals':'stl_total_current','turnovers':'tov_total_current','blocks':'blk_total_current','blocksAgainst':'blka_total_current','foulsCommited':'pf_total_current','foulsDrawn':'fd_total_current',
     'twoPointersMade':'2pm_total_current','twoPointersAttempted':'2pa_total_current','threePointersMade':'3pm_total_current','threePointersAttempted':'3pa_total_current','freeThrowsMade':'ftm_total_current','freeThrowsAttempted':'fta_total_current'}
    for idx,oi in mapping.items():
        s=off.loc[oi]
        p.loc[idx,'official_name_full']=s['full'];p.loc[idx,'official_match_quality']=100 if patch.tokens(s['full'])==patch.tokens(p.loc[idx,'name']) else 85
        for src,dst in stats.items():p.loc[idx,dst]=s[src]
    for c in stats.values():
        if c not in p:p[c]=np.nan
    p['gp_current']=p.gp_current.fillna(0).astype(int)
    gp=p.gp_current.replace(0,np.nan)
    for total,avg in [('min','min_avg_current'),('pir','pir_avg_current'),('pts','pts_avg_current'),('reb','reb_avg_current'),('oreb','oreb_avg_current'),('dreb','dreb_avg_current'),('ast','ast_avg_current'),('stl','stl_avg_current'),('tov','tov_avg_current'),('blk','blk_avg_current'),('blka','blka_avg_current'),('pf','pf_avg_current'),('fd','fd_avg_current')]:
        p[avg]=(p[f'{total}_total_current']/gp).round(2)
    p['fg_made_total_current']=p['2pm_total_current']+p['3pm_total_current'];p['fg_attempts_total_current']=p['2pa_total_current']+p['3pa_total_current']
    p['fg_made_pg_current']=(p.fg_made_total_current/gp).round(2);p['fg_attempts_pg_current']=(p.fg_attempts_total_current/gp).round(2)
    p['fg_pct_current']=(100*p.fg_made_total_current/p.fg_attempts_total_current.replace(0,np.nan)).round(1)
    for short in ['2p','3p','ft']:
        made=p[short+'m_total_current'];att=p[short+('a_total_current')]
        p[short+'_current']=[None if not g else f'{m/g:.1f}/{a/g:.1f}' for m,a,g in zip(made,att,p.gp_current)]
        p[short+'_pct_current']=(100*made/att.replace(0,np.nan)).round(1)
    p['fg_attempts_per_min_current']=(p.fg_attempts_total_current/p.min_total_current.replace(0,np.nan)).round(3)
    p['fg_attempts_per40_current']=(40*p.fg_attempts_total_current/p.min_total_current.replace(0,np.nan)).round(2)
    p['pir_per_min_current']=(p.pir_total_current/p.min_total_current.replace(0,np.nan)).round(3)
    p['minutes_per_game']=p.min_avg_current.round(1);p['min_avg_best']=p.min_avg_current;p['min_avg_source']=np.where(p.gp_current.gt(0),'2026-27 current','No current-season sample')
    for key in ['fg_made_pg','fg_attempts_pg','fg_pct','fg_attempts_per_min','fg_attempts_per40']:p[key+'_best']=p[key+'_current']
    p['value_pir_per_credit']=(p.pir_avg_current/p.price.replace(0,np.nan)).round(2)
    current=int(raw['config']['current_matchday']['number'])
    r=log[(log.matchday==current)&log.player_id.notna()].copy().drop_duplicates('player_id',keep='first').set_index('player_id')
    for key,src in [('fantasy_pts_current_md','fantasy_pts'),('match_status','match_status'),('opponent_abbr','opponent_abbr'),('home_away','home_away'),('start_local','start_local')]:
        p[key]=p.player_id.map(r[src]) if src in r else None
    p['value_fantasy_per_credit']=(p.fantasy_pts_current_md/p.price.replace(0,np.nan)).round(2)
    # No previous-season playing time is used anywhere in these EuroCup tables.
    p.to_csv(DATA/'players_current_matched.csv',index=False)
    return p


def context_and_projection(p,matches):
    mod=load_module('ec_context_functions',ROOT/'scripts/create_euroleague_advanced_context.py')
    mod.DATA=DATA
    from euroleague_api.team_stats import TeamStats as TS
    mod.TeamStats=lambda competition='E':TS('U')
    ctx=mod.build_team_metrics(2026)
    if len(ctx)!=32:raise RuntimeError(f'Expected 32 official EuroCup teams, got {len(ctx)}')
    ctx['context_source']='2026-27 current, official EuroCup'
    ctx['sample_confidence']='low current sample'
    # Same weakness/FDR weights used by the existing EuroLeague tools; no invented results.
    for field,name in [('pace_possessions_pg','pace_score'),('allowed_pir_pg','pir_allowed_score'),('allowed_points_pg','points_allowed_score'),('allowed_fga_pg','fga_allowed_score')]:
        ctx[name]=mod.percentile(ctx[field])
    ctx['reb_allowed_score']=mod.percentile(ctx.allowed_oreb_pg+ctx.allowed_dreb_pg)
    ctx['team_defense_weakness_score']=(.25*ctx.pir_allowed_score+.20*ctx.points_allowed_score+.20*ctx.fga_allowed_score+.20*ctx.reb_allowed_score+.15*ctx.pace_score).round(1)
    ctx['team_defense_fdr_1_easy_5_hard']=(1+4*(100-ctx.team_defense_weakness_score)/100).round(2)
    ctx.to_csv(DATA/'team_context.csv',index=False)
    detail,summ=mod.build_next5_schedule(matches,ctx)
    rename={'pace_possessions_pg':'team_pace_possessions_pg','for_fga_pg':'team_fga_for_pg','allowed_fga_pg':'team_fga_allowed_pg','allowed_oreb_pg':'team_oreb_allowed_pg','allowed_dreb_pg':'team_dreb_allowed_pg','allowed_pir_pg':'team_pir_allowed_pg'}
    p=p.merge(ctx[['team_abbr',*rename,'team_defense_weakness_score']].rename(columns=rename),on='team_abbr',how='left').merge(summ,on='team_abbr',how='left')
    # Reuse the exact, already documented current-season EuroLeague projection formula in a EuroCup-only namespace.
    path=ROOT/'scripts/apply_advanced_proj_pir_formula.py'
    source=path.read_text(encoding='utf-8').split('\n# Load current context,')[0]
    source=source.replace("'euroleague-defense-vs-position", "'eurocup-defense-vs-position")
    proj=load_module('ec_projection_functions',path,source);proj.DATA=DATA;proj.SITE=ROOT
    p=proj.add_advanced_projection(p);p=proj.recalc_option_score(p)
    # Full upcoming game fields for the cards and downloaded player table.
    first=detail.sort_values('start_local').drop_duplicates('team_abbr').set_index('team_abbr')
    for dest,src in [('next_opponent','opponent'),('next_start_local','start_local'),('next_matchday','matchday'),('next_home_away','home_away')]:
        p[dest]=p.team_abbr.map(first[src])
    p['player_fga_pg']=p.fg_attempts_pg_current;p['team_fga_pg']=p.team_fga_for_pg
    p['shot_share_pct']=(100*p.player_fga_pg/p.team_fga_pg.replace(0,np.nan)).round(1)
    return p,ctx,detail,summ,proj


def render(p,ctx,detail,summ,proj,raw,matches,dvp):
    stamp=dt.datetime.fromisoformat(raw['source_fetched']).astimezone(TZ).strftime('%Y-%m-%d %H:%M %Z')
    shots=load_module('ec_shot_cols',ROOT/'scripts/add_shot_share_section.py')
    sh=p[p.gp_current.gt(0)&p.min_avg_current.gt(0)&p.pos_short.ne('HC')&p.shot_share_pct.notna()].copy()
    sh=sh.sort_values(['shot_share_pct','name'],ascending=[False,True]);sh['shot_share_rank']=sh.shot_share_pct.rank(method='min',ascending=False).astype(int)
    for c in shots.COLS:
        if c not in sh:sh[c]=np.nan
    sh=sh[shots.COLS];sh.to_csv(ROOT/'eurocup-shot-share.csv',index=False)
    p=p.sort_values(['option_score_next5','name'],ascending=[False,True]).reset_index(drop=True)
    p.to_csv(ROOT/'eurocup-players-full.csv',index=False);ctx.to_csv(ROOT/'eurocup-team-context.csv',index=False);detail.to_csv(ROOT/'eurocup-next5-schedule.csv',index=False)
    p.to_csv(DATA/'fantasheet_style_table_context.csv',index=False)
    D,_=proj.update_dashboard_data(p,ctx,detail);D['generated']=stamp
    pool=p[p.gp_current.gt(0)&p.pos_short.ne('HC')&~p.is_injured]
    avgpool=p[p.gp_current.ge(max(1,math.ceil(p.gp_current.max()/2)))&p.pos_short.ne('HC')]
    def leaders(df,col,n=12):return proj.clean_records(df[df[col].notna()].sort_values([col,'name'],ascending=[False,True]).head(n))
    D['avgPirLeaders']=leaders(avgpool,'pir_avg_current');D['avgMinLeaders']=leaders(pool,'min_avg_current');D['minutesLeaders']=leaders(pool,'minutes_per_game')
    m10=pool[pool.min_avg_current.ge(10)]
    D['pirPerMinLeaders']=leaders(m10,'pir_per_min_current');D['usageLeaders']=leaders(m10,'fg_attempts_per_min_current');D['valueLeaders']=leaders(m10,'value_pir_per_credit')
    D['shotShareLeaders']=proj.clean_records(sh);D['shotShareCols']=shots.COLS
    # Drop obsolete previous-season display columns from the overview table.
    D['pcolsMain']=[c for c in ['name','team_abbr','pos_short','price','price_change','option_score_next5','proj_pir_est','pir_avg_current','form_pir','value_pir_per_credit','pir_per_min_current','minutes_per_game','gp_current','pts_avg_current','reb_avg_current','ast_avg_current','stl_avg_current','blk_avg_current','tov_avg_current','fg_pct_current','fg_attempts_per_min_current','fantasy_pts_current_md','next_opponent','next_start_local','next5_fdr_1_easy_5_hard','next5_opponents','is_injured','started_from_bench','popularity_pct'] if c in p]
    D['pcolsFull']=[c for c in p.columns if c not in ['first_name','last_name']]
    count=int(matches.status.eq('played').sum());maxmd=int(matches.loc[matches.status.eq('played'),'matchday'].max())
    sample={'en':f'Updated after the games on 13 October 2026: {count} completed EuroCup games; Round {maxmd} is still in progress. Season averages use official completed-game data only. Proj PIR, matchup difficulty and option score are model estimates, not actual results. Team context is current-season only.',
            'sr':f'Ažurirano poslije utakmica 13. oktobra 2026: {count} završenih EuroCup utakmica; {maxmd}. kolo još traje. Prosjeci koriste samo zvanične završene utakmice. Proj PIR, težina rasporeda i option score su procjene modela, ne ostvareni rezultati. Timski kontekst je samo iz ove sezone.',
            'el':f'Ενημέρωση μετά τους αγώνες της 13ης Οκτωβρίου 2026: {count} ολοκληρωμένοι αγώνες EuroCup· η αγωνιστική {maxmd} συνεχίζεται. Οι μέσοι όροι αφορούν μόνο επίσημα ολοκληρωμένους αγώνες. Proj PIR και δυσκολία προγράμματος είναι εκτιμήσεις μοντέλου. Το πλαίσιο ομάδων είναι μόνο της τρέχουσας σεζόν.'}
    last_date=str(matches.loc[matches.status.eq('played'),'start_local'].max())[:10]
    sample={k:v.replace('13 October 2026',last_date).replace('13. oktobra 2026',last_date).replace('13ης Οκτωβρίου 2026',last_date) for k,v in sample.items()}
    methods={
      'en': '<h2>Method</h2><div class="note">GP, minutes, PIR, points, shooting, rebounds and assists are observed statistics from official completed EuroCup games. Prices, ownership and injury status are the current public fantasy snapshot. Players with no current-season minutes have no projection or playing-time fallback.</div><div class="note">Proj PIR is a model, not an actual score. It combines current PIR/min × projected current minutes, a price-based small-sample prior (weight fades by 5 games), next-opponent pace, real-points DvP, home/away and risk adjustments. No previous-season player statistics enter this calculation.</div><div class="note">Team context uses only the current EuroCup season. Pace estimates possessions as FGA + 0.44×FTA − OREB + TOV, averaged with the opponent. Shot Share = player FGA/game ÷ team FGA/game × 100. DvP shows real points, grouped by fantasy G/F/C positions (official positions only for players missing from the fantasy list). Samples of two or three games are very small.</div>',
      'sr': '<h2>Metod</h2><div class="note">Utakmice, minute, PIR, poeni, šut, skokovi i asistencije su ostvarena statistika iz zvaničnih završenih EuroCup utakmica. Cijene, vlasništvo i povrede su presjek fantasy servisa. Igrači bez minuta ove sezone nemaju projekciju niti zamjenu podacima iz prošle sezone.</div><div class="note">Proj PIR je procjena modela, ne ostvaren rezultat. Kombinuje tekući PIR/min × projektovane tekuće minute, cjenovni oslonac za mali uzorak (uticaj nestaje nakon 5 utakmica), tempo protivnika, DvP u stvarnim poenima, domaći/gostujući teren i rizik. Statistika igrača iz prošle sezone ne ulazi u račun.</div><div class="note">Timski kontekst je samo iz tekuće EuroCup sezone. Tempo procjenjuje posjede kao FGA + 0,44×FTA − OREB + TOV, usrednjeno sa protivnikom. Shot Share = FGA igrača po utakmici ÷ FGA tima po utakmici × 100. DvP su stvarni poeni po fantasy G/F/C pozicijama (zvanične pozicije samo za igrače koji nedostaju u fantasy listi). Uzorak od dvije ili tri utakmice je vrlo mali.</div>',
      'el': '<h2>Μέθοδος</h2><div class="note">Αγώνες, λεπτά, PIR, πόντοι, σουτ, ριμπάουντ και ασίστ είναι πραγματικά στατιστικά από επίσημους ολοκληρωμένους αγώνες EuroCup. Τιμές, ιδιοκτησία και τραυματισμοί είναι το στιγμιότυπο της υπηρεσίας fantasy. Παίκτες χωρίς λεπτά φέτος δεν έχουν προβολή ή δεδομένα προηγούμενης σεζόν ως υποκατάστατο.</div><div class="note">Το Proj PIR είναι εκτίμηση μοντέλου, όχι πραγματικό σκορ. Συνδυάζει φετινό PIR/λεπτό × προβλεπόμενα φετινά λεπτά, προσαρμογή βάσει τιμής για μικρά δείγματα μέχρι 5 αγώνες, ρυθμό αντιπάλου, DvP πραγματικών πόντων, έδρα και κίνδυνο. Δεν χρησιμοποιούνται στατιστικά παικτών προηγούμενης σεζόν.</div><div class="note">Το πλαίσιο ομάδων αφορά μόνο τη φετινή EuroCup. Ρυθμός = FGA + 0,44×FTA − OREB + TOV, μέσος όρος με τον αντίπαλο. Shot Share = FGA παίκτη/αγώνα ÷ FGA ομάδας/αγώνα × 100. DvP: πραγματικοί πόντοι ανά fantasy θέση G/F/C (επίσημες θέσεις μόνο για παίκτες εκτός fantasy λίστας). Δύο ή τρεις αγώνες είναι πολύ μικρό δείγμα.</div>'}
    for lang,prefix,title in [('en','','Average PIR so far'),('sr','sr-','Prosječan PIR do sada'),('el','el-','Μέσος PIR μέχρι τώρα')]:
        # Existing EuroLeague sections are reused as UI only; all embedded records are the EuroCup dataset above.
        text=(ROOT/f'{prefix}euroleague-dashboard.html').read_text(encoding='utf-8')
        text=text.replace('EuroLeague','EuroCup').replace('euroleague','eurocup')
        # No new routes or analyzer section are introduced by this update.
        text=re.sub(r'<a[^>]+href="[^"]*/eurocup/team-analyzer"[^>]*>.*?</a>','',text,flags=re.S)
        text=re.sub(r'<a[^>]+href="[^"]*/eurocup/(?:round2[^"/]*|top-3-value-igraca-drugo-kolo)"[^>]*>.*?</a>','',text,flags=re.S)
        marker='const DATA=';a=text.index(marker)+len(marker);old,end=json.JSONDecoder().raw_decode(text[a:])
        loc=json.loads(json.dumps(D,ensure_ascii=False));loc['labels']={**D['labels'],**old.get('labels',{}),**shots.T[lang]['lab']}
        loc['labels'].update({'min_avg_best':{'en':'MIN/G current','sr':'MIN/G ova sezona','el':'ΛΕΠ/Α τρέχουσα'}[lang]})
        text=text[:a]+json.dumps(loc,ensure_ascii=False,separators=(',',':'),allow_nan=False).replace('</','<\\/')+text[a+end:]
        # Replace the overview help note, not the overview cards.
        text=re.sub(r'(<section id="overview"[^>]*>\s*<div class="note">).*?(</div>)',lambda m:m.group(1)+sample[lang]+m.group(2),text,count=1,flags=re.S)
        # EuroLeague team-context template describes a 40/60 prior; EuroCup is intentionally all current season.
        for oldtxt in ['40% current season and 60% 2025-26','40% current / 60% 25-26','40% current + 60% 2025-26','40% tekuće sezone + 60% 2025-26','40% current + 60% 25-26']:
            text=text.replace(oldtxt,'100% current EuroCup season')
        method=f'<section id="method" class="panel"><div class="note">{sample[lang]}</div>'+methods[lang]+'</section>'
        text=re.sub(r'<section id="method"[^>]*>.*?</section>',lambda m:method,text,count=1,flags=re.S)
        # All pages and cards must have the same factual cutoff.
        if title not in text:raise RuntimeError(f'Missing average PIR card in {lang}')
        (ROOT/f'{prefix}eurocup-dashboard.html').write_text(text,encoding='utf-8')
    dv.build_pages(dvp,maxmd,count,stamp)
    (DATA/'refresh-summary.json').write_text(json.dumps({'generated':stamp,'games':count,'matchdays':maxmd,'round_in_progress':True,'players':len(p),'players_with_minutes':int(p.gp_current.gt(0).sum()),'dvp_defense_rows':int(2*count),'dvp_all_valid':True},ensure_ascii=False,indent=2),encoding='utf-8')
    print('EUROCUP READY:',stamp,'games',count,'players',len(p),'with official current stats',int(p.gp_current.gt(0).sum()),'team-context',len(ctx),'next5',len(detail),'shot-share',len(sh),flush=True)


def main():
    if '--cached' in sys.argv:
        raw=json.loads(CACHE.read_text());official=pd.read_csv(DATA/'official_current_raw.csv');codes=pd.read_csv(DATA/'official_games.csv');boxes=json.loads((DATA/'official_boxscores_2026.json').read_text())
    else:raw,official,codes,boxes=fetch_sources()
    matches=make_matches(raw,official,codes)
    log,dvp,ml=finalize_log(matches,codes,boxes)
    p=current_players(raw,official,log,matches)
    p,ctx,detail,summ,proj=context_and_projection(p,matches)
    render(p,ctx,detail,summ,proj,raw,matches,dvp)

if __name__=='__main__':main()
