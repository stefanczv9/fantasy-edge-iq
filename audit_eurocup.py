#!/usr/bin/env python3
"""Independent EuroCup release check against the saved OFFICIAL per-game box scores.
Does not use season aggregate player stats for the comparison. Exits nonzero on any discrepancy.
It validates real-points DvP by position, each published player's GP/MIN/PIR/PTS/REB/AST/FGA,
current-only card eligibility, current price snapshot, and the finished ROM-BLK match.
"""
from pathlib import Path
import json,sys,importlib.util
import pandas as pd
import numpy as np

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];DATA=ROOT/'eurocup_fantasy_data'
sys.path.insert(0,str(HERE));import refresh_eurocup as R
patch=R.load_module('ec_audit_pair',ROOT/'scripts/patch_log_from_official_boxscore.py')


def main():
    P=pd.read_csv(ROOT/'eurocup-players-full.csv');boxes=json.loads((DATA/'official_boxscores_2026.json').read_text());M=pd.read_csv(DATA/'utakmice.csv')
    ML=pd.read_csv(ROOT/'eurocup-defense-vs-position-matchlog.csv');D=pd.read_csv(ROOT/'eurocup-defense-vs-position.csv')
    assert P.player_id.is_unique and len(P)>0
    assert M[M.status.eq('played')].shape[0]==len(ML)//2==len(pd.read_csv(DATA/'official_games.csv'))
    assert ML.validation_ok.all() and D.validation_ok.all()
    p_lookup=P.set_index('player_id'); by_off={}
    for p in P[P.gp_current.gt(0)].itertuples():
        assert isinstance(p.official_name_full,str)
        k=(p.team_abbr,patch.tokens(p.official_name_full));assert k not in by_off,k;by_off[k]=p.player_id
    by_name={}
    samples={};missing=[]; checked=0
    for g in M[M.status.eq('played')].itertuples():
        b=boxes[str(int(g.official_game))]
        for side,ab,defab,score in [('local.players',g.home_abbr,g.away_abbr,g.home_score),('road.players',g.away_abbr,g.home_abbr,g.away_score)]:
            allpts=0;pospts={k:0 for k in ['Guard','Forward','Center']}
            for e in b.get(side) or []:
                s=e.get('stats') or {};pp=e.get('player') or {};sec=float(s.get('timePlayed') or 0)
                if sec<=0:continue
                name=patch.official_to_full((pp.get('person') or {}).get('name') or '')
                k=(ab,patch.tokens(name));pid=by_off.get(k)
                # Source aggregate and per-game names occasionally insert/remove spaces, e.g. Mc Creary.
                if pid is None:
                    cand=[p.player_id for p in P[(P.team_abbr==ab)&P.gp_current.gt(0)].itertuples() if patch.squash(p.official_name_full)==patch.squash(name)]
                    if len(cand)==1:pid=cand[0]
                if pid is None:
                    same=[p.player_id for p in P[(P.team_abbr==ab)&P.gp_current.gt(0)].itertuples() if patch.tokens(R.NAME_ALIASES.get(name,name))==patch.tokens(p.name)]
                    if len(same)==1:pid=same[0]
                stats={'game':g.match_id,'min':sec/60,'pir':s.get('valuation') or 0,'pts':s.get('points') or 0,'reb':s.get('totalRebounds') or 0,'ast':s.get('assistances') or 0,
                       'fga':(s.get('fieldGoalsAttempted2') or 0)+(s.get('fieldGoalsAttempted3') or 0)}
                if pid is not None:samples.setdefault(pid,[]).append(stats)
                else:missing.append((ab,name))
                position=p_lookup.loc[pid,'position'] if pid is not None else pp.get('positionName')
                assert position in pospts,(ab,name,position)
                pospts[position]+=stats['pts'];allpts+=stats['pts']
            assert allpts==score,('Official team points do not sum',ab,allpts,score)
            row=ML[(ML.match_id==g.match_id)&(ML.team_abbr==defab)]
            assert len(row)==1,(g.match_id,defab)
            r=row.iloc[0]
            for pos,col in [('Guard','guard_pts_allowed'),('Forward','forward_pts_allowed'),('Center','center_pts_allowed')]:
                assert pospts[pos]==r[col],(g.match_id,defab,pos,pospts[pos],r[col])
            checked+=1
    bad=[]
    for p in P[P.gp_current.gt(0)].itertuples():
        s=pd.DataFrame(samples.get(p.player_id,[]))
        if s.empty:bad.append((p.name,'no official box sample'));continue
        expected={'gp_current':s.game.nunique(),'min_avg_current':s['min'].mean(),'pir_avg_current':s.pir.mean(),'pts_avg_current':s.pts.mean(),'reb_avg_current':s.reb.mean(),'ast_avg_current':s.ast.mean(),'fg_attempts_pg_current':s.fga.mean(),'fg_attempts_per_min_current':s.fga.sum()/s['min'].sum()}
        for col,v in expected.items():
            actual=getattr(p,col);tol=.0006 if col=='fg_attempts_per_min_current' else .011
            if pd.isna(actual) or abs(float(actual)-v)>tol:bad.append((p.name,col,actual,v))
    print('Official per-game player comparisons:',P.gp_current.gt(0).sum(),'players | issues',len(bad))
    for b in bad[:20]:print('ERROR',b)
    assert not bad,bad
    print('Independent real-PTS DvP comparisons:',checked,'defense rows | all match official box scores')
    raw=json.loads((DATA/'refresh_sources.json').read_text());pr={int(p['id']):p for p in raw['profiles']}
    for p in P.itertuples():assert abs(float(p.price)-float(pr[p.player_id]['quotation']))<.001
    print('Fantasy prices:',len(P),'all match fetched profile prices')
    for pre in ['','sr-','el-']:
        text=(ROOT/f'{pre}eurocup-dashboard.html').read_text();a=text.index('const DATA=')+len('const DATA=');d=json.JSONDecoder().raw_decode(text[a:])[0]
        assert len(d['players'])==len(P) and len(d['teams'])==32 and len(d['schedule'])==len(pd.read_csv(ROOT/'eurocup-next5-schedule.csv')) and len(d['shotShareLeaders'])==P.gp_current.gt(0).sum()
        for key in ['pirPerMinLeaders','usageLeaders']:
            for p in d[key]:assert p['gp_current']>0 and p['min_avg_current']>=10 and p['pos_short']!='HC' and not p['is_injured']
        for p in d['minutesLeaders']:assert p['gp_current']>0 and p['min_avg_current']>0 and p['pos_short']!='HC' and not p['is_injured']
        assert 'Shane Larkin' not in json.dumps(d.get('minutesLeaders',[]))
    assert M.loc[M.match_id.eq(12341),'status'].eq('played').all()
    print('EN/SR/EL data, all card eligibility and stale live-status correction: PASS')
    print('Official players without fantasy price kept in DvP, not fabricated as priced players:',sorted(set(missing)))
    print('OK')

if __name__=='__main__':main()
