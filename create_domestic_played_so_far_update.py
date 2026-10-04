from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json, math, re, html as htmlmod
from io import StringIO
from urllib.parse import unquote

import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup

ROOT = Path('/home/user')
SITE = ROOT / 'fantasy-edge-iq-v2'
DATA = ROOT / 'euroleague_fantasy_data'
LOCAL_TZ = ZoneInfo('Europe/Zagreb')

EL_CLUBS = {
    'ASV','BAR','BAY','BJK','CZV','DUB','EFS','FBT','HTA','KBA','MIL','MTA','OLY','PAO','PAR','PBB','RMB','VBC','VIR','ZAL'
}

STD_COLS = [
    'country','league','competition','season','phase','round','game_id','date_local','status','source_quality','source_note','source_url',
    'team_abbr','team_name','opponent_abbr','opponent_name','home_away','team_score','opponent_score',
    'player','is_total','is_team_bench','pts','reb','dreb','oreb','ast','blk','blka','fouls_drawn','fouls_committed','stl','tov',
    'minutes_raw','minutes','rank','two_made','two_att','three_made','three_att','ft_made','ft_att','fg_made','fg_att','fg_pct','fga_per_min','rank_per_min'
]
GAME_COLS = [
    'country','league','competition','season','phase','round','game_id','date_local','venue','home_team','home_abbr','away_team','away_abbr',
    'home_score','away_score','q1_home','q1_away','q2_home','q2_away','q3_home','q3_away','q4_home','q4_away','status','source_quality','source_note','source_url'
]


def to_num(x):
    if x is None:
        return np.nan
    try:
        if pd.isna(x):
            return np.nan
    except Exception:
        pass
    s = str(x).strip().replace('%','').replace(',', '.')
    if s in ['', '-', 'nan', 'None', '--:--:--']:
        return np.nan
    try:
        return float(s)
    except Exception:
        return np.nan


def parse_made_attempt(x):
    if x is None:
        return (np.nan, np.nan)
    s = str(x).strip().replace('–','-').replace('—','-')
    if s in ['', '-', 'nan', '--']:
        return (np.nan, np.nan)
    m = re.search(r'(\d+)\s*[-/]\s*(\d+)', s)
    if not m:
        return (np.nan, np.nan)
    return (int(m.group(1)), int(m.group(2)))


def minutes_to_float(s):
    if s is None:
        return np.nan
    try:
        if pd.isna(s):
            return np.nan
    except Exception:
        pass
    st = str(s).strip()
    if st in ['', '-', 'nan', '--:--:--']:
        return np.nan
    if ':' in st:
        parts = st.split(':')
        try:
            if len(parts) == 3:
                h, m, sec = [int(float(p)) for p in parts]
                return h*60 + m + sec/60
            if len(parts) == 2:
                m, sec = [int(float(p)) for p in parts]
                return m + sec/60
        except Exception:
            return np.nan
    try:
        return float(st.replace(',', '.'))
    except Exception:
        return np.nan


def clean_player_name(s):
    s = str(s or '').replace('\xa0',' ').replace('<br>',' ').strip()
    # Remove markdown/link leftovers and jersey prefix.
    s = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', s)
    s = re.sub(r'^\s*#?\d+\s*[-.]?\s*', '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    # ESAKE renders many names in all caps; title-case those for readability while leaving ACB/LKL initials intact.
    if s and s.upper() == s:
        s = s.title()
    return s


def calc_derived(row):
    tm = row.get('two_made')
    ta = row.get('two_att')
    thm = row.get('three_made')
    tha = row.get('three_att')
    fgm = (0 if pd.isna(tm) else tm) + (0 if pd.isna(thm) else thm)
    fga = (0 if pd.isna(ta) else ta) + (0 if pd.isna(tha) else tha)
    row['fg_made'] = fgm if not (pd.isna(tm) and pd.isna(thm)) else np.nan
    row['fg_att'] = fga if not (pd.isna(ta) and pd.isna(tha)) else np.nan
    row['fg_pct'] = None if not fga or pd.isna(fga) else round(100*fgm/fga, 1)
    mins = row.get('minutes')
    rank = row.get('rank')
    row['fga_per_min'] = None if not mins or pd.isna(mins) or not fga or pd.isna(fga) else round(fga/mins, 3)
    row['rank_per_min'] = None if not mins or pd.isna(mins) or pd.isna(rank) else round(rank/mins, 3)
    return row


def rec(**kwargs):
    r = {c: None for c in STD_COLS}
    r.update(kwargs)
    return calc_derived(r)


def game_rec(**kwargs):
    r = {c: None for c in GAME_COLS}
    r.update(kwargs)
    return r


def flatten_columns(df):
    cols=[]
    for c in df.columns:
        if isinstance(c, tuple):
            vals=[str(x) for x in c if str(x) and not str(x).startswith('Unnamed')]
            cols.append(vals[-1] if vals else str(c[-1]))
        else:
            cols.append(str(c))
    df=df.copy(); df.columns=cols; return df


def parse_esake_team_table(table, game, team_abbr, team_name, opp_abbr, opp_name, ha):
    df=flatten_columns(table)
    rows=[]; total=None
    for _, rr in df.iterrows():
        raw=str(rr.get('ΠΑΙΚΤΗΣ','')).strip()
        if not raw or raw.lower()=='nan':
            continue
        is_total='ΣΥΝΟΛΟ' in raw
        is_bench='ΟΜΑΔΙΚΑ' in raw or 'ΠΑΓΚΟΣ' in raw
        two=parse_made_attempt(rr.get('2PM-A'))
        three=parse_made_attempt(rr.get('3PM-A'))
        ft=parse_made_attempt(rr.get('FTM-A'))
        row=rec(
            country='Greece', league='GBL', competition=game['competition'], season=game['season'], phase=game['phase'], round=game['round'],
            game_id=game['game_id'], date_local=game['date_local'], status='played', source_quality='official_boxscore', source_note='Official ESAKE/GBL box score.', source_url=game['source_url'],
            team_abbr=team_abbr, team_name=team_name, opponent_abbr=opp_abbr, opponent_name=opp_name, home_away=ha,
            team_score=game['home_score'] if ha=='H' else game['away_score'], opponent_score=game['away_score'] if ha=='H' else game['home_score'],
            player='TOTAL' if is_total else ('TEAM BENCH' if is_bench else clean_player_name(raw)), is_total=is_total, is_team_bench=is_bench,
            pts=to_num(rr.get('P')), reb=to_num(rr.get('REBS')), dreb=to_num(rr.get('D.REBS')), oreb=to_num(rr.get('O.REBS')),
            ast=to_num(rr.get('AST')), blk=to_num(rr.get('BLK')), blka=to_num(rr.get('BLK-A')), fouls_drawn=to_num(rr.get('FOULS F')),
            fouls_committed=to_num(rr.get('FOULS M')), stl=to_num(rr.get('STL')), tov=to_num(rr.get('TO')),
            minutes_raw=None if is_total or is_bench else str(rr.get('TIM.PL.','')).strip(), minutes=np.nan if is_total or is_bench else minutes_to_float(rr.get('TIM.PL.')),
            rank=to_num(rr.get('RANK')), two_made=two[0], two_att=two[1], three_made=three[0], three_att=three[1], ft_made=ft[0], ft_att=ft[1]
        )
        if is_total:
            total=row
        elif not is_bench:
            rows.append(row)
    return rows, total


def add_greek(games, players, totals):
    base='https://www.esake.gr/el/action/EsakegameView?idgame={game_id}&mode=3'
    greek_games=[
        dict(competition='Stoiximan Super Cup', season='2026-27', phase='Semifinal', round='01', game_id='A35F72D9', date_local='2026-09-26 16:45', venue='K.G. Peristeriou Andreas Papandreou', home_team='Olympiacos', home_abbr='OLY', away_team='AEK', away_abbr='AEK', home_score=93, away_score=80, q1_home=28, q1_away=18, q2_home=18, q2_away=19, q3_home=28, q3_away=25, q4_home=19, q4_away=18, source_url=base.format(game_id='A35F72D9')),
        dict(competition='Stoiximan Super Cup', season='2026-27', phase='Semifinal', round='01', game_id='43A0A50E', date_local='2026-09-26 21:00', venue='K.G. Peristeriou Andreas Papandreou', home_team='Panathinaikos AKTOR', home_abbr='PAO', away_team='PAOK', away_abbr='PAOK', home_score=82, away_score=84, q1_home=15, q1_away=24, q2_home=19, q2_away=14, q3_home=24, q3_away=17, q4_home=24, q4_away=29, source_url=base.format(game_id='43A0A50E')),
        dict(competition='Stoiximan Super Cup', season='2026-27', phase='Final', round='02', game_id='04920552', date_local='2026-09-27 20:00', venue='K.G. Peristeriou Andreas Papandreou', home_team='Olympiacos', home_abbr='OLY', away_team='PAOK', away_abbr='PAOK', home_score=101, away_score=96, q1_home=25, q1_away=17, q2_home=25, q2_away=19, q3_home=24, q3_away=29, q4_home=27, q4_away=31, source_url=base.format(game_id='04920552')),
    ]
    for g in greek_games:
        games.append(game_rec(country='Greece', league='GBL', status='played', source_quality='official_boxscore', source_note='Official ESAKE/GBL finished Super Cup box score.', **g))
        try:
            tables=pd.read_html(g['source_url'])
            home_rows, home_total = parse_esake_team_table(tables[1], g, g['home_abbr'], g['home_team'], g['away_abbr'], g['away_team'], 'H')
            away_rows, away_total = parse_esake_team_table(tables[2], g, g['away_abbr'], g['away_team'], g['home_abbr'], g['home_team'], 'A')
            for r in home_rows + away_rows:
                if r['team_abbr'] in EL_CLUBS:
                    players.append(r)
            for r in [home_total, away_total]:
                if r and r['team_abbr'] in EL_CLUBS:
                    totals.append(r)
        except Exception as e:
            print('Greek parse failed', g['game_id'], e)


def parse_acb_table(table, game, team_abbr, team_name, opp_abbr, opp_name, ha):
    rows=[]; total=None
    for _, rr in table.iterrows():
        name=str(rr.get('Player','')).strip()
        if not name or name.lower()=='nan':
            continue
        is_total=name.lower()=='totals'
        is_team=name.lower()=='team'
        two=parse_made_attempt(rr.get('T2'))
        three=parse_made_attempt(rr.get('T3'))
        ft=parse_made_attempt(rr.get('TL'))
        row=rec(
            country='Spain', league='ACB', competition=game['competition'], season=game['season'], phase=game['phase'], round=game['round'],
            game_id=game['game_id'], date_local=game['date_local'], status='played', source_quality='official_boxscore', source_note='Official ACB Live box score. ACB Val is mapped to PIR/RANK.', source_url=game['source_url'],
            team_abbr=team_abbr, team_name=team_name, opponent_abbr=opp_abbr, opponent_name=opp_name, home_away=ha,
            team_score=game['home_score'] if ha=='H' else game['away_score'], opponent_score=game['away_score'] if ha=='H' else game['home_score'],
            player='TOTAL' if is_total else ('TEAM BENCH' if is_team else clean_player_name(name)), is_total=is_total, is_team_bench=is_team,
            pts=to_num(rr.get('Pts')), reb=to_num(rr.get('TR')), dreb=to_num(rr.get('DR')), oreb=to_num(rr.get('OR')),
            ast=to_num(rr.get('As')), blk=to_num(rr.get('B')), blka=to_num(rr.get('BR')), fouls_drawn=to_num(rr.get('FD')),
            fouls_committed=to_num(rr.get('PF')), stl=to_num(rr.get('Stl')), tov=to_num(rr.get('TO')),
            minutes_raw=None if is_total or is_team else str(rr.get('Min','')).strip(), minutes=np.nan if is_total or is_team else minutes_to_float(rr.get('Min')),
            rank=to_num(rr.get('Val')), two_made=two[0], two_att=two[1], three_made=three[0], three_att=three[1], ft_made=ft[0], ft_att=ft[1]
        )
        if is_total:
            total=row
        elif not is_team:
            rows.append(row)
    return rows, total


def add_acb(games, players, totals):
    acb_games=[
        dict(competition='Liga Endesa', season='2026-27', phase='Regular Season', round='01', game_id='ACB-105377', date_local='2026-09-26', venue='', home_team='Barça', home_abbr='BAR', away_team='Leyma Coruña', away_abbr='COR', home_score=119, away_score=101, q1_home=22, q1_away=18, q2_home=30, q2_away=29, q3_home=33, q3_away=32, q4_home=34, q4_away=22, source_url='https://live.acb.com/en/partidos/barca-vs-leyma-coruna-105377/estadisticas'),
        dict(competition='Liga Endesa', season='2026-27', phase='Regular Season', round='01', game_id='ACB-105379', date_local='2026-09-27 10:30', venue='', home_team='Recoletas Salud San Pablo Burgos', home_abbr='BUR', away_team='Kosner Baskonia', away_abbr='KBA', home_score=97, away_score=98, q1_home=24, q1_away=30, q2_home=21, q2_away=19, q3_home=30, q3_away=16, q4_home=22, q4_away=33, source_url='https://live.acb.com/en/partidos/recoletas-salud-san-vs-kosner-baskonia-105379/estadisticas'),
        dict(competition='Liga Endesa', season='2026-27', phase='Regular Season', round='01', game_id='ACB-105382', date_local='2026-09-27', venue='', home_team='Valencia Basket', home_abbr='VBC', away_team='iLERNA Lleida', away_abbr='ILE', home_score=100, away_score=105, q1_home=20, q1_away=26, q2_home=33, q2_away=24, q3_home=19, q3_away=26, q4_home=28, q4_away=29, source_url='https://live.acb.com/en/partidos/valencia-basket-vs-ilerna-lleida-105382/estadisticas'),
        dict(competition='Liga Endesa', season='2026-27', phase='Regular Season', round='01', game_id='ACB-105383', date_local='2026-09-27', venue='', home_team='Real Madrid', home_abbr='RMB', away_team='Unicaja', away_abbr='UNI', home_score=89, away_score=87, q1_home=23, q1_away=22, q2_home=23, q2_away=25, q3_home=19, q3_away=24, q4_home=24, q4_away=16, source_url='https://live.acb.com/en/partidos/real-madrid-vs-unicaja-105383/estadisticas'),
    ]
    for g in acb_games:
        games.append(game_rec(country='Spain', league='ACB', status='played', source_quality='official_boxscore', source_note='Liga Endesa final official ACB Live box score.', **g))
        try:
            tables=pd.read_html(g['source_url'])
            home_rows, home_total = parse_acb_table(tables[0], g, g['home_abbr'], g['home_team'], g['away_abbr'], g['away_team'], 'H')
            away_rows, away_total = parse_acb_table(tables[1], g, g['away_abbr'], g['away_team'], g['home_abbr'], g['home_team'], 'A')
            for r in home_rows + away_rows:
                if r['team_abbr'] in EL_CLUBS:
                    players.append(r)
            for r in [home_total, away_total]:
                if r and r['team_abbr'] in EL_CLUBS:
                    totals.append(r)
        except Exception as e:
            print('ACB parse failed', g['game_id'], e)


def lkl_val(cell):
    if isinstance(cell, dict):
        return cell.get('value')
    return cell


def parse_lkl_side(j, game, side, team_abbr, team_name, opp_abbr, opp_name, ha):
    rows=[]
    team=j['boxscore'][side]['team']
    def ma(key): return parse_made_attempt(lkl_val(team.get(key)))
    two=ma('fg2'); three=ma('fg3'); ft=ma('ft')
    total=rec(
        country='Lithuania', league='LKL', competition=game['competition'], season=game['season'], phase=game['phase'], round=game['round'],
        game_id=game['game_id'], date_local=game['date_local'], status='played', source_quality='official_api', source_note='Official LKL live box-score API.', source_url=game['source_url'],
        team_abbr=team_abbr, team_name=team_name, opponent_abbr=opp_abbr, opponent_name=opp_name, home_away=ha,
        team_score=game['home_score'] if ha=='H' else game['away_score'], opponent_score=game['away_score'] if ha=='H' else game['home_score'],
        player='TOTAL', is_total=True, is_team_bench=False,
        pts=to_num(lkl_val(team.get('points'))), reb=to_num(lkl_val(team.get('total_rebounds'))), dreb=to_num(lkl_val(team.get('defensive_rebounds'))), oreb=to_num(lkl_val(team.get('offensive_rebounds'))),
        ast=to_num(lkl_val(team.get('assists'))), blk=to_num(lkl_val(team.get('blocks'))), blka=to_num(lkl_val(team.get('blocks_received'))), fouls_drawn=to_num(lkl_val(team.get('fouls_on'))), fouls_committed=to_num(lkl_val(team.get('fouls'))), stl=to_num(lkl_val(team.get('steals'))), tov=to_num(lkl_val(team.get('turnovers'))),
        minutes_raw=None, minutes=np.nan, rank=to_num(lkl_val(team.get('efficiency'))), two_made=two[0], two_att=two[1], three_made=three[0], three_att=three[1], ft_made=ft[0], ft_att=ft[1]
    )
    for rr in j['boxscore'][side]['players']:
        two=parse_made_attempt(lkl_val(rr.get('fg2'))); three=parse_made_attempt(lkl_val(rr.get('fg3'))); ft=parse_made_attempt(lkl_val(rr.get('ft')))
        rows.append(rec(
            country='Lithuania', league='LKL', competition=game['competition'], season=game['season'], phase=game['phase'], round=game['round'],
            game_id=game['game_id'], date_local=game['date_local'], status='played', source_quality='official_api', source_note='Official LKL live box-score API.', source_url=game['source_url'],
            team_abbr=team_abbr, team_name=team_name, opponent_abbr=opp_abbr, opponent_name=opp_name, home_away=ha,
            team_score=game['home_score'] if ha=='H' else game['away_score'], opponent_score=game['away_score'] if ha=='H' else game['home_score'],
            player=clean_player_name(lkl_val(rr.get('name'))), is_total=False, is_team_bench=False,
            pts=to_num(lkl_val(rr.get('points'))), reb=to_num(lkl_val(rr.get('total_rebounds'))), dreb=to_num(lkl_val(rr.get('defensive_rebounds'))), oreb=to_num(lkl_val(rr.get('offensive_rebounds'))),
            ast=to_num(lkl_val(rr.get('assists'))), blk=to_num(lkl_val(rr.get('blocks'))), blka=to_num(lkl_val(rr.get('blocks_received'))), fouls_drawn=to_num(lkl_val(rr.get('fouls_on'))), fouls_committed=to_num(lkl_val(rr.get('fouls'))), stl=to_num(lkl_val(rr.get('steals'))), tov=to_num(lkl_val(rr.get('turnovers'))),
            minutes_raw=str(lkl_val(rr.get('time'))), minutes=minutes_to_float(lkl_val(rr.get('time'))), rank=to_num(lkl_val(rr.get('efficiency'))),
            two_made=two[0], two_att=two[1], three_made=three[0], three_att=three[1], ft_made=ft[0], ft_att=ft[1]
        ))
    return rows, total


def add_lkl(games, players, totals):
    lkl_games=[
        dict(competition='LKL', season='2026-27', phase='Regular Season', round='01', game_id='LKL-11578', date_local='2026-09-17 18:30', venue='Gargždų SC arena', home_team='Gargždai', home_abbr='GAR', away_team='Žalgiris', away_abbr='ZAL', home_score=77, away_score=98, source_url='https://lkl.lt/rungtynes/11578'),
        dict(competition='LKL', season='2026-27', phase='Regular Season', round='01', game_id='LKL-11581', date_local='2026-09-20 16:30', venue='Švyturio arena', home_team='Neptūnas', home_abbr='NEP', away_team='Žalgiris', away_abbr='ZAL', home_score=69, away_score=93, source_url='https://lkl.lt/rungtynes/11581'),
        dict(competition='LKL', season='2026-27', phase='Regular Season', round='02', game_id='LKL-11587', date_local='2026-09-27 16:50', venue='Žalgirio arena', home_team='Žalgiris', home_abbr='ZAL', away_team='Šiauliai', away_abbr='SIA', home_score=101, away_score=82, source_url='https://lkl.lt/rungtynes/11587'),
    ]
    headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'}
    for g in lkl_games:
        gid=g['game_id'].split('-')[1]
        try:
            j=requests.get(f'https://lkl.lt/api/livestream/boxscore/{gid}',headers=headers,timeout=20).json()
            # Fill quarters from official API.
            ids=list(j['gameStatistics'].keys())
            # home and away order follows boxscore sides; use team stats quarter_scores.
            home_stats=j['gameStatistics'][ids[0]]; away_stats=j['gameStatistics'][ids[1]]
            for q in [1,2,3,4]:
                g[f'q{q}_home']=home_stats['quarter_scores'].get(str(q))
                g[f'q{q}_away']=away_stats['quarter_scores'].get(str(q))
            games.append(game_rec(country='Lithuania', league='LKL', status='played', source_quality='official_api', source_note='Official LKL finished game/API.', **g))
            if g['home_abbr']=='ZAL':
                rows,total=parse_lkl_side(j,g,'home',g['home_abbr'],g['home_team'],g['away_abbr'],g['away_team'],'H')
            else:
                rows,total=parse_lkl_side(j,g,'away',g['away_abbr'],g['away_team'],g['home_abbr'],g['home_team'],'A')
            players.extend(rows); totals.append(total)
        except Exception as e:
            print('LKL parse failed', g['game_id'], e)


def add_lba_milano(games, players, totals):
    g=dict(country='Italy', league='LBA', competition='LBA Serie A', season='2026-27', phase='Regular Season', round='01', game_id='LBA-25600', date_local='2026-09-27 10:00', venue='Unipol Forum', home_team='Armani Olimpia Milano', home_abbr='MIL', away_team='Pallacanestro Trieste', away_abbr='TRI', home_score=83, away_score=79, q1_home=17, q1_away=19, q2_home=21, q2_away=22, q3_home=19, q3_away=23, q4_home=26, q4_away=15, status='played', source_quality='official_boxscore', source_note='Official LBA game page. LBA Lega valuation is mapped to PIR/RANK.', source_url='https://www.legabasket.it/game/25600/armani-olimpia-milano-pallacanestro-trieste/tabellini')
    games.append(game_rec(**g))
    # Values copied from official LBA tabellini table for Milano.
    rows = [
        ('Jason Burnell',20,26,5,2,4,7,3,6,3,4,4,6,10,3,1,0,0,1,29,9),
        ('R.J. Cole',11,24,1,5,1,4,3,4,0,0,0,0,0,1,0,0,0,0,4,4),
        ('Moses Wright',16,22,6,3,6,13,0,0,4,4,5,2,7,2,0,2,0,3,16,13),
        ('Ousmane Diop',5,13,1,4,2,6,0,0,1,2,4,1,5,3,0,1,0,1,3,-4),
        ('Stefano Tonut',0,16,0,1,0,1,0,1,0,0,2,5,7,3,0,0,0,1,6,-3),
        ('Leandro Bolmaro',11,25,2,1,4,5,0,2,3,4,0,5,5,2,0,0,0,3,12,4),
        ('Darius Thompson',9,18,2,3,1,3,1,2,4,4,3,0,3,1,0,0,2,0,11,1),
        ('Giampaolo Ricci',2,14,1,2,1,1,0,2,0,0,1,5,6,0,1,0,1,0,7,-4),
        ('Diego Flaccadori',2,11,1,0,1,4,0,0,0,2,0,0,0,0,0,1,0,0,-3,-7),
        ('Devon Hall',7,26,2,2,1,3,1,4,2,2,0,3,3,2,1,0,1,2,7,12),
        ('Marko Guduric',0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0),
        ('Nicola Akele',0,5,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,-5),
    ]
    # tuple: player, pts,min, fd,pf,2m,2a,3m,3a,ftm,fta,oreb,dreb,reb,ast,blk,blka,stl,tov,rank,plusminus
    for name,pts,mins,fd,pf,two_m,two_a,th_m,th_a,ft_m,ft_a,oreb,dreb,reb,ast,blk,blka,stl,tov,rank,pm in rows:
        players.append(rec(country='Italy', league='LBA', competition=g['competition'], season=g['season'], phase=g['phase'], round=g['round'], game_id=g['game_id'], date_local=g['date_local'], status='played', source_quality='official_boxscore', source_note=g['source_note'], source_url=g['source_url'], team_abbr='MIL', team_name='Armani Olimpia Milano', opponent_abbr='TRI', opponent_name='Pallacanestro Trieste', home_away='H', team_score=83, opponent_score=79, player=name, is_total=False, is_team_bench=False, pts=pts, reb=reb, dreb=dreb, oreb=oreb, ast=ast, blk=blk, blka=blka, fouls_drawn=fd, fouls_committed=pf, stl=stl, tov=tov, minutes_raw=str(mins), minutes=float(mins), rank=rank, two_made=two_m, two_att=two_a, three_made=th_m, three_att=th_a, ft_made=ft_m, ft_att=ft_a))
    totals.append(rec(country='Italy', league='LBA', competition=g['competition'], season=g['season'], phase=g['phase'], round=g['round'], game_id=g['game_id'], date_local=g['date_local'], status='played', source_quality='official_boxscore', source_note=g['source_note'], source_url=g['source_url'], team_abbr='MIL', team_name='Armani Olimpia Milano', opponent_abbr='TRI', opponent_name='Pallacanestro Trieste', home_away='H', team_score=83, opponent_score=79, player='TOTAL', is_total=True, is_team_bench=False, pts=83, reb=49, dreb=30, oreb=19, ast=17, blk=3, blka=4, fouls_drawn=23, fouls_committed=21, stl=4, tov=11, minutes_raw=None, minutes=np.nan, rank=95, two_made=21, two_att=47, three_made=8, three_att=21, ft_made=17, ft_att=22))


def extract_next_data(url):
    headers={'User-Agent':'Mozilla/5.0','Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}
    html=requests.get(url,headers=headers,timeout=30).text
    m=re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, flags=re.S)
    if not m:
        raise ValueError('NEXT_DATA not found')
    return json.loads(htmlmod.unescape(m.group(1)))


def add_lba_virtus(games, players, totals):
    url='https://www.legabasket.it/game/25606/openjobmetis-varese-virtus-costa-bologna/tabellini'
    try:
        data=extract_next_data(url)
        game=data['props']['pageProps']['game']
        match=game['match']
        g=dict(country='Italy', league='LBA', competition='LBA Serie A', season='2026-27', phase='Regular Season', round=f"{match.get('day_serial') or 1:02d}", game_id='LBA-25606', date_local='2026-09-27 19:00', venue=match.get('plant_name') or 'Itelyum Arena', home_team=match.get('h_team_name') or 'Openjobmetis Varese', home_abbr='VAR', away_team=match.get('v_team_name') or 'Virtus Costa Bologna', away_abbr='VIR', home_score=match.get('home_final_score'), away_score=match.get('visitor_final_score'), q1_home=match.get('q1_hs'), q1_away=match.get('q1_vs'), q2_home=match.get('q2_hs'), q2_away=match.get('q2_vs'), q3_home=match.get('q3_hs'), q3_away=match.get('q3_vs'), q4_home=match.get('q4_hs'), q4_away=match.get('q4_vs'), status='played', source_quality='official_boxscore', source_note='Official LBA game page JSON/tabellini. LBA Lega valuation is mapped to PIR/RANK.', source_url=url)
        games.append(game_rec(**g))
        rows=game['scores']['vt']['rows']
        for rr in rows:
            mins = to_num(rr.get('sec')) / 60 if not pd.isna(to_num(rr.get('sec'))) else to_num(rr.get('min'))
            if pd.isna(mins):
                minutes_raw = None
            else:
                total_sec = int(round(float(mins)*60))
                minutes_raw = f"{total_sec//60}:{total_sec%60:02d}"
            players.append(rec(country='Italy', league='LBA', competition=g['competition'], season=g['season'], phase=g['phase'], round=g['round'], game_id=g['game_id'], date_local=g['date_local'], status='played', source_quality=g['source_quality'], source_note=g['source_note'], source_url=g['source_url'], team_abbr='VIR', team_name=g['away_team'], opponent_abbr='VAR', opponent_name=g['home_team'], home_away='A', team_score=g['away_score'], opponent_score=g['home_score'], player=clean_player_name(f"{rr.get('player_name','').title()} {rr.get('player_surname','').title()}"), is_total=False, is_team_bench=False, pts=to_num(rr.get('pun')), reb=to_num(rr.get('rimbalzi_t')), dreb=to_num(rr.get('rimbalzi_d')), oreb=to_num(rr.get('rimbalzi_o')), ast=to_num(rr.get('ass')), blk=to_num(rr.get('stoppate_dat')), blka=to_num(rr.get('stoppate_sub')), fouls_drawn=to_num(rr.get('falli_sf')), fouls_committed=to_num(rr.get('falli_c')), stl=to_num(rr.get('palle_r')), tov=to_num(rr.get('palle_p')), minutes_raw=minutes_raw, minutes=mins, rank=to_num(rr.get('val_lega')), two_made=to_num(rr.get('t2_r')), two_att=to_num(rr.get('t2_t')), three_made=to_num(rr.get('t3_r')), three_att=to_num(rr.get('t3_t')), ft_made=to_num(rr.get('tl_r')), ft_att=to_num(rr.get('tl_t'))))
        tt=game['scores']['vt']['totals']
        totals.append(rec(country='Italy', league='LBA', competition=g['competition'], season=g['season'], phase=g['phase'], round=g['round'], game_id=g['game_id'], date_local=g['date_local'], status='played', source_quality=g['source_quality'], source_note=g['source_note'], source_url=g['source_url'], team_abbr='VIR', team_name=g['away_team'], opponent_abbr='VAR', opponent_name=g['home_team'], home_away='A', team_score=g['away_score'], opponent_score=g['home_score'], player='TOTAL', is_total=True, is_team_bench=False, pts=to_num(tt.get('pun')), reb=to_num(tt.get('rimbalzi_t')), dreb=to_num(tt.get('rimbalzi_d')), oreb=to_num(tt.get('rimbalzi_o')), ast=to_num(tt.get('ass')), blk=to_num(tt.get('stoppate_dat')), blka=to_num(tt.get('stoppate_sub')), fouls_drawn=to_num(tt.get('falli_sf')), fouls_committed=to_num(tt.get('falli_c')), stl=to_num(tt.get('palle_r')), tov=to_num(tt.get('palle_p')), minutes_raw=None, minutes=np.nan, rank=to_num(tt.get('val_lega')), two_made=to_num(tt.get('t2_r')), two_att=to_num(tt.get('t2_t')), three_made=to_num(tt.get('t3_r')), three_att=to_num(tt.get('t3_t')), ft_made=to_num(tt.get('tl_r')), ft_att=to_num(tt.get('tl_t'))))
    except Exception as e:
        print('LBA Virtus parse failed', e)


def resultati_num(x):
    if x is None:
        return 0
    s=str(x).strip()
    if s in ('', '-', '–', '—'):
        return 0
    try:
        return float(s.replace(',','.'))
    except Exception:
        return 0



def estimate_resultati_pir(d):
    """Available-stat PIR/EFF estimate for Rezultati rows.

    Rezultati/Flashscore exposes points, rebounds, assists, steals, blocks,
    missed shots, turnovers and blocks-against, but not fouls drawn. To avoid
    pretending the official European PIR is present, the foul component is
    omitted rather than guessed.
    """
    pts=resultati_num(d.get('pts'))
    reb=resultati_num(d.get('reb'))
    ast=resultati_num(d.get('ast'))
    stl=resultati_num(d.get('stl'))
    blk=resultati_num(d.get('blk'))
    two_m=resultati_num(d.get('two_made')); two_a=resultati_num(d.get('two_att'))
    th_m=resultati_num(d.get('three_made')); th_a=resultati_num(d.get('three_att'))
    ft_m=resultati_num(d.get('ft_made')); ft_a=resultati_num(d.get('ft_att'))
    tov=resultati_num(d.get('tov'))
    blka=resultati_num(d.get('blka'))
    fg_miss=max(0, (two_a-two_m) + (th_a-th_m))
    ft_miss=max(0, ft_a-ft_m)
    val=pts+reb+ast+stl+blk-fg_miss-ft_miss-tov-blka
    return round(val, 1)

def resultati_player_name(label, url):
    m=re.search(r'/igrac/([^/]+)/', url or '')
    if not m:
        return clean_player_name(label)
    slug=m.group(1)
    fixes={
        'horton-tucker-talen':'Talen Horton-Tucker','shields-shavon':'Shavon Shields','key-braxton':'Braxton Key','forrest-trent':'Trent Forrest','mahmutoglu-melih':'Melih Mahmutoğlu','melli-nicolo':'Nicolò Melli','bitim-onuralp':'Onuralp Bitim','sanli-sertac':'Sertaç Şanlı','baldwin-wade':'Wade Baldwin','silva-chris':'Chris Silva','yanci-kadir':'Kadir Yancı',
        'saric-dario':'Dario Šarić','brown-anthony':'Anthony Brown','zizic-ante':'Ante Žižić','dejulius-david':'David DeJulius','james-mike':'Mike James','loyd-jordan':'Jordan Loyd','strazel-matthew':'Matthew Strazel','ugurlu-berk':'Berk Uğurlu','gabriel-wenyen':'Wenyen Gabriel','mutaf-david':'David Mutaf','osmani-erxhan':'Ercan Osmani','russell-daron':'Daron Russell','korkmaz-furkan':'Furkan Korkmaz','morgan-conor':'Conor Morgan','yusta-santigo':'Santi Yusta','birsen-james-metecan':'James Metecan Birsen','fernando-bruno':'Bruno Fernando','yilmaz-erkan':'Erkan Yılmaz','nowell-jaylen':'Jaylen Nowell','karutasu-darius':'Darius Karutaşu','omoruyi-eugene':'Eugene Omoruyi','wilbekin-scottie':'Scottie Wilbekin','yildizli-burak':'Burak Yıldızlı'
    }
    if slug in fixes:
        return fixes[slug]
    parts=slug.split('-')
    if len(parts)>=2:
        first=parts[-1].title()
        surname='-'.join(parts[:-1]).title().replace('-', ' ')
        return f'{first} {surname}'
    return clean_player_name(label)


def parse_resultati_players(md, game, abbr_map, name_map):
    idx=md.find('Igrač')
    if idx < 0:
        return []
    end=md.find('Tečajevi', idx)
    section=md[idx:end if end>idx else None]
    matches=list(re.finditer(r'\[([^\]]+)\]\((https://www\.rezultati\.com/igrac/[^\)]+)\)', section))
    rows=[]
    stat_cols=['pts','reb','ast','minutes_raw','fg_made','fg_att','two_made','two_att','three_made','three_att','ft_made','ft_att','plus_minus','oreb','dreb','fouls_committed','stl','tov','blk','blka','technical']
    for i,m in enumerate(matches):
        raw=section[m.end(): matches[i+1].start() if i+1<len(matches) else len(section)]
        toks=[x.strip() for x in raw.splitlines() if x.strip()]
        if len(toks) < 22:
            continue
        src_team=toks[0]
        if src_team not in abbr_map:
            continue
        vals=toks[1:22]
        d=dict(zip(stat_cols, vals))
        team_abbr=abbr_map[src_team]
        ha='H' if team_abbr==game['home_abbr'] else 'A'
        opp_abbr=game['away_abbr'] if ha=='H' else game['home_abbr']
        opp_name=game['away_team'] if ha=='H' else game['home_team']
        est_pir=estimate_resultati_pir(d)
        rows.append(rec(country='Turkey', league='BSL', competition=game['competition'], season=game['season'], phase=game['phase'], round=game['round'], game_id=game['game_id'], date_local=game['date_local'], status='played', source_quality='third_party_boxscore_est_pir', source_note='Rezultati.com/Flashscore player box score used because the official TBF/BSL page did not expose a public box score. Minutes and shooting are captured; PIR/RANK is estimated from available box-score stats with the foul-drawn/foul-committed component omitted because fouls drawn are unavailable.', source_url=game['source_url'], team_abbr=team_abbr, team_name=name_map[team_abbr], opponent_abbr=opp_abbr, opponent_name=opp_name, home_away=ha, team_score=game['home_score'] if ha=='H' else game['away_score'], opponent_score=game['away_score'] if ha=='H' else game['home_score'], player=resultati_player_name(m.group(1), m.group(2)), is_total=False, is_team_bench=False, pts=resultati_num(d['pts']), reb=resultati_num(d['reb']), dreb=resultati_num(d['dreb']), oreb=resultati_num(d['oreb']), ast=resultati_num(d['ast']), blk=resultati_num(d['blk']), blka=resultati_num(d['blka']), fouls_drawn=np.nan, fouls_committed=resultati_num(d['fouls_committed']), stl=resultati_num(d['stl']), tov=resultati_num(d['tov']), minutes_raw=d['minutes_raw'], minutes=minutes_to_float(d['minutes_raw']), rank=est_pir, two_made=resultati_num(d['two_made']), two_att=resultati_num(d['two_att']), three_made=resultati_num(d['three_made']), three_att=resultati_num(d['three_att']), ft_made=resultati_num(d['ft_made']), ft_att=resultati_num(d['ft_att'])))
    return rows


def add_resultati_totals(game, players, totals, name_map):
    note='Summed from Rezultati.com player rows; team rebounds may differ from official team-total rebounds where team rebounds are tracked separately. PIR/RANK is estimated from available player stats; foul component omitted because fouls drawn are unavailable.'
    for team_abbr, team_name in name_map.items():
        team_rows=[r for r in players if r.get('game_id')==game['game_id'] and r.get('team_abbr')==team_abbr]
        if not team_rows:
            continue
        ha='H' if team_abbr==game['home_abbr'] else 'A'
        opp_abbr=game['away_abbr'] if ha=='H' else game['home_abbr']
        opp_name=game['away_team'] if ha=='H' else game['home_team']
        def sm(c):
            vals=[r.get(c) for r in team_rows]
            nums=[float(v) for v in vals if v is not None and not pd.isna(v)]
            return sum(nums) if nums else np.nan
        totals.append(rec(country='Turkey', league='BSL', competition=game['competition'], season=game['season'], phase=game['phase'], round=game['round'], game_id=game['game_id'], date_local=game['date_local'], status='played', source_quality='third_party_boxscore_est_pir', source_note=note, source_url=game['source_url'], team_abbr=team_abbr, team_name=team_name, opponent_abbr=opp_abbr, opponent_name=opp_name, home_away=ha, team_score=game['home_score'] if ha=='H' else game['away_score'], opponent_score=game['away_score'] if ha=='H' else game['home_score'], player='TOTAL', is_total=True, is_team_bench=False, pts=sm('pts'), reb=sm('reb'), dreb=sm('dreb'), oreb=sm('oreb'), ast=sm('ast'), blk=sm('blk'), blka=sm('blka'), fouls_drawn=np.nan, fouls_committed=sm('fouls_committed'), stl=sm('stl'), tov=sm('tov'), minutes_raw=None, minutes=np.nan, rank=sm('rank'), two_made=sm('two_made'), two_att=sm('two_att'), three_made=sm('three_made'), three_att=sm('three_att'), ft_made=sm('ft_made'), ft_att=sm('ft_att')))


def add_turkey_resultati(games, players, totals):
    turkish_games=[
        dict(country='Turkey', league='BSL', competition='Türkiye Sigorta BSL', season='2026-27', phase='Regular Season', round='01', game_id='BSL-2g3UzXo1', date_local='2026-09-27 11:00', venue='Sinan Erdem Dome', home_team='Bahçeşehir Koleji', home_abbr='BAH', away_team='Fenerbahçe', away_abbr='FBT', home_score=98, away_score=83, q1_home=28, q1_away=16, q2_home=23, q2_away=27, q3_home=23, q3_away=22, q4_home=24, q4_away=18, status='played', source_quality='third_party_boxscore', source_note='Rezultati.com/Flashscore final/player stats used because official TBF/BSL public box score was unavailable; PIR/RANK is estimated from available player stats.', source_url='https://www.rezultati.com/utakmica/kosarka/bahcesehir-koleji-AJURGI1d/fenerbahce-rDhoZR1l/detalji/statistika-igraca/ukupno/?mid=2g3UzXo1'),
        dict(country='Turkey', league='BSL', competition='Türkiye Sigorta BSL', season='2026-27', phase='Regular Season', round='01', game_id='BSL-AJ6xZAGD', date_local='2026-09-27 13:30', venue='Basketbol Gelisim Merkezi', home_team='Anadolu Efes', home_abbr='EFS', away_team='Beşiktaş', away_abbr='BJK', home_score=95, away_score=81, q1_home=20, q1_away=16, q2_home=26, q2_away=21, q3_home=29, q3_away=22, q4_home=20, q4_away=22, status='played', source_quality='third_party_boxscore', source_note='Rezultati.com/Flashscore final/player stats used because official TBF/BSL public box score was unavailable; PIR/RANK is estimated from available player stats.', source_url='https://www.rezultati.com/utakmica/kosarka/anadolu-efes-ny4KlAOf/besiktas-hE4Gkj9l/detalji/statistika-igraca/ukupno/?mid=AJ6xZAGD'),
    ]
    for g in turkish_games:
        games.append(game_rec(**g))
        try:
            jina='https://r.jina.ai/http://'+g['source_url']
            md=requests.get(jina,headers={'User-Agent':'Mozilla/5.0'},timeout=35).text
            if g['game_id']=='BSL-2g3UzXo1':
                abbr_map={'FEN':'FBT'}
                name_map={'FBT':'Fenerbahçe'}
            else:
                abbr_map={'EFE':'EFS','BES':'BJK'}
                name_map={'EFS':'Anadolu Efes','BJK':'Beşiktaş'}
            new_rows=parse_resultati_players(md, g, abbr_map, name_map)
            players.extend(new_rows)
            add_resultati_totals(g, players, totals, name_map)
        except Exception as e:
            print('Turkey Resultati parse failed', g['game_id'], e)


def parse_israel_stat_table(table, game, team_abbr, team_name, opp_abbr, opp_name, ha):
    rows=[]; total=None
    df=table.copy()
    for _, rr in df.iloc[3:].iterrows():
        name=str(rr.iloc[1]).strip()
        if not name or name.lower()=='nan':
            continue
        is_team = name.lower()=='team'
        is_total = name.lower()=='total'
        two=parse_made_attempt(rr.iloc[5])
        three=parse_made_attempt(rr.iloc[7])
        ft=parse_made_attempt(rr.iloc[9])
        row=rec(country='Israel', league='IBSL', competition=game['competition'], season=game['season'], phase=game['phase'], round=game['round'], game_id=game['game_id'], date_local=game['date_local'], status='played', source_quality='official_boxscore', source_note='Official Israel Basketball Super League game-zone box score. Winner Cup is domestic cup, not regular league. VAL is mapped to PIR/RANK.', source_url=game['source_url'], team_abbr=team_abbr, team_name=team_name, opponent_abbr=opp_abbr, opponent_name=opp_name, home_away=ha, team_score=game['home_score'] if ha=='H' else game['away_score'], opponent_score=game['away_score'] if ha=='H' else game['home_score'], player='TOTAL' if is_total else ('TEAM' if is_team else clean_player_name(name)), is_total=is_total, is_team_bench=is_team, pts=to_num(rr.iloc[4]), reb=to_num(rr.iloc[13]), dreb=to_num(rr.iloc[11]), oreb=to_num(rr.iloc[12]), ast=to_num(rr.iloc[18]), blk=to_num(rr.iloc[19]), blka=to_num(rr.iloc[20]), fouls_drawn=to_num(rr.iloc[15]), fouls_committed=to_num(rr.iloc[14]), stl=to_num(rr.iloc[16]), tov=to_num(rr.iloc[17]), minutes_raw=None if is_total or is_team else str(rr.iloc[3]).strip(), minutes=np.nan if is_total or is_team else minutes_to_float(rr.iloc[3]), rank=to_num(rr.iloc[21]), two_made=two[0], two_att=two[1], three_made=three[0], three_att=three[1], ft_made=ft[0], ft_att=ft[1])
        if is_total:
            total=row
        elif not is_team:
            rows.append(row)
    return rows,total


def add_israel_winner_cup(games, players, totals):
    israel_games=[
        dict(country='Israel', league='IBSL', competition='Winner Cup', season='2026-27', phase='Quarterfinal', round='QF', game_id='ISR-26841', date_local='2026-09-26 20:55', venue='Hadera', home_team='Hapoel IBI Tel Aviv', home_abbr='HTA', away_team='Hapoel Beer Sheva/Dimona', away_abbr='BSD', home_score=85, away_score=67, q1_home=27, q1_away=19, q2_home=15, q2_away=10, q3_home=19, q3_away=15, q4_home=24, q4_away=23, status='played', source_quality='official_boxscore', source_note='Official IBSL Winner Cup box score. Winner Cup is marked separately from regular-season league games.', source_url='https://basket.co.il/game-zone.asp?GameId=26841&lang=en'),
        dict(country='Israel', league='IBSL', competition='Winner Cup', season='2026-27', phase='Quarterfinal', round='QF', game_id='ISR-26842', date_local='2026-09-27 19:00', venue='Hadera', home_team='Maccabi Rapyd Tel Aviv', home_abbr='MTA', away_team='Ironi Kiryat Ata', away_abbr='KYA', home_score=109, away_score=61, q1_home=18, q1_away=18, q2_home=36, q2_away=18, q3_home=25, q3_away=8, q4_home=30, q4_away=17, status='played', source_quality='official_boxscore', source_note='Official IBSL Winner Cup box score. Winner Cup is marked separately from regular-season league games.', source_url='https://basket.co.il/game-zone.asp?GameId=26842&lang=en'),
    ]
    headers={'User-Agent':'Mozilla/5.0'}
    for g in israel_games:
        games.append(game_rec(**g))
        try:
            html=requests.get(g['source_url'],headers=headers,timeout=30).text
            tables=pd.read_html(html)
            # Table 4 is home team; table 5 is away team on IBSL game-zone pages.
            home_rows, home_total = parse_israel_stat_table(tables[4], g, g['home_abbr'], g['home_team'], g['away_abbr'], g['away_team'], 'H')
            away_rows, away_total = parse_israel_stat_table(tables[5], g, g['away_abbr'], g['away_team'], g['home_abbr'], g['home_team'], 'A')
            for r in home_rows + away_rows:
                if r['team_abbr'] in EL_CLUBS:
                    players.append(r)
            for r in [home_total, away_total]:
                if r and r['team_abbr'] in EL_CLUBS:
                    totals.append(r)
        except Exception as e:
            print('Israel Winner Cup parse failed', g['game_id'], e)



def add_greek_regular_season(games, players, totals):
    """Add completed Stoiximan GBL regular-season games for Greek EuroLeague clubs."""
    base='https://www.esake.gr/el/action/EsakegameView?idgame={game_id}&mode=3'
    greek_games=[
        dict(competition='Stoiximan GBL', season='2026-27', phase='Regular Season', round='01', game_id='GBL-FDBBC910', esake_id='FDBBC910', date_local='2026-10-04 13:00', venue='Telekom Center Athens', home_team='Panathinaikos AKTOR', home_abbr='PAO', away_team='Vikos Falcons', away_abbr='VIK', home_score=103, away_score=74, q1_home=32, q1_away=20, q2_home=23, q2_away=17, q3_home=24, q3_away=11, q4_home=24, q4_away=26),
        dict(competition='Stoiximan GBL', season='2026-27', phase='Regular Season', round='01', game_id='GBL-4A03748D', esake_id='4A03748D', date_local='2026-10-04 17:30', venue='Ivanofeio', home_team='Iraklis', home_abbr='IRA', away_team='Olympiacos', away_abbr='OLY', home_score=68, away_score=78, q1_home=25, q1_away=15, q2_home=11, q2_away=31, q3_home=14, q3_away=18, q4_home=18, q4_away=14),
    ]
    for g0 in greek_games:
        g=dict(g0)
        esake_id=g.pop('esake_id')
        g['source_url']=base.format(game_id=esake_id)
        games.append(game_rec(country='Greece', league='GBL', status='played', source_quality='official_boxscore', source_note='Official ESAKE/GBL finished regular-season box score.', **g))
        try:
            tables=pd.read_html(g['source_url'])
            home_rows, home_total = parse_esake_team_table(tables[1], g, g['home_abbr'], g['home_team'], g['away_abbr'], g['away_team'], 'H')
            away_rows, away_total = parse_esake_team_table(tables[2], g, g['away_abbr'], g['away_team'], g['home_abbr'], g['home_team'], 'A')
            for r in home_rows + away_rows:
                if r['team_abbr'] in EL_CLUBS:
                    players.append(r)
            for r in [home_total, away_total]:
                if r and r['team_abbr'] in EL_CLUBS:
                    totals.append(r)
        except Exception as e:
            print('Greek regular parse failed', g['game_id'], e)


def add_acb_round2(games, players, totals):
    acb_games=[
        dict(competition='Liga Endesa', season='2026-27', phase='Regular Season', round='02', game_id='ACB-105389', date_local='2026-10-04', venue='Pabellón Multiusos Fontes do Sar', home_team='Monbus Obradoiro', home_abbr='MOB', away_team='Real Madrid', away_abbr='RMB', home_score=107, away_score=114, source_url='https://live.acb.com/en/partidos/monbus-obradoiro-vs-real-madrid-105389/estadisticas'),
        dict(competition='Liga Endesa', season='2026-27', phase='Regular Season', round='02', game_id='ACB-105390', date_local='2026-10-04', venue='Pabellón Príncipe Felipe', home_team='Casademont Zaragoza', home_abbr='CAZ', away_team='Valencia Basket', away_abbr='VBC', home_score=82, away_score=97, source_url='https://live.acb.com/en/partidos/casademont-zaragoza-vs-valencia-basket-105390/estadisticas'),
        dict(competition='Liga Endesa', season='2026-27', phase='Regular Season', round='02', game_id='ACB-105391', date_local='2026-10-04', venue='Buesa Arena', home_team='Kosner Baskonia', home_abbr='KBA', away_team='FIATC Girona', away_abbr='GIR', home_score=118, away_score=78, source_url='https://live.acb.com/en/partidos/kosner-baskonia-vs-fiatc-girona-105391/estadisticas'),
        dict(competition='Liga Endesa', season='2026-27', phase='Regular Season', round='02', game_id='ACB-105392', date_local='2026-10-04', venue='Palacio de los Deportes de Murcia', home_team='UCAM Murcia', home_abbr='UCM', away_team='Barça', away_abbr='BAR', home_score=100, away_score=94, source_url='https://live.acb.com/en/partidos/ucam-murcia-vs-barca-105392/estadisticas'),
    ]
    for g in acb_games:
        games.append(game_rec(country='Spain', league='ACB', status='played', source_quality='official_boxscore', source_note='Liga Endesa final official ACB Live box score.', **g))
        try:
            tables=pd.read_html(g['source_url'])
            home_rows, home_total = parse_acb_table(tables[0], g, g['home_abbr'], g['home_team'], g['away_abbr'], g['away_team'], 'H')
            away_rows, away_total = parse_acb_table(tables[1], g, g['away_abbr'], g['away_team'], g['home_abbr'], g['home_team'], 'A')
            for r in home_rows + away_rows:
                if r['team_abbr'] in EL_CLUBS:
                    players.append(r)
            for r in [home_total, away_total]:
                if r and r['team_abbr'] in EL_CLUBS:
                    totals.append(r)
        except Exception as e:
            print('ACB R2 parse failed', g['game_id'], e)


def add_lkl_latest(games, players, totals):
    g=dict(competition='LKL', season='2026-27', phase='Regular Season', round='03', game_id='LKL-11593', date_local='2026-10-04 16:50', venue='Žalgirio arena', home_team='Žalgiris', home_abbr='ZAL', away_team='Lietkabelis', away_abbr='LIE', home_score=97, away_score=68, q1_home=20, q1_away=21, q2_home=29, q2_away=17, q3_home=23, q3_away=12, q4_home=25, q4_away=16, source_url='https://lkl.lt/rungtynes/11593')
    headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'}
    try:
        j=requests.get('https://lkl.lt/api/livestream/boxscore/11593',headers=headers,timeout=20).json()
        games.append(game_rec(country='Lithuania', league='LKL', status='played', source_quality='official_api', source_note='Official LKL finished game/API.', **g))
        rows,total=parse_lkl_side(j,g,'home',g['home_abbr'],g['home_team'],g['away_abbr'],g['away_team'],'H')
        players.extend(rows); totals.append(total)
    except Exception as e:
        print('LKL latest parse failed', g['game_id'], e)


def add_lba_virtus_round2(games, players, totals):
    url='https://www.legabasket.it/game/25368/virtus-costa-bologna-maxima-roma/tabellini'
    try:
        data=extract_next_data(url)
        game=data['props']['pageProps']['game']
        match=game['match']
        g=dict(country='Italy', league='LBA', competition='LBA Serie A', season='2026-27', phase='Regular Season', round=f"{match.get('number') or 2:02d}", game_id='LBA-25368', date_local='2026-10-04 18:15', venue=match.get('plant_name') or 'PalaDozza', home_team=match.get('h_team_name') or 'Virtus Costa Bologna', home_abbr='VIR', away_team=match.get('v_team_name') or 'Maxima Roma', away_abbr='MXR', home_score=match.get('home_final_score'), away_score=match.get('visitor_final_score'), q1_home=match.get('q1_hs'), q1_away=match.get('q1_vs'), q2_home=match.get('q2_hs'), q2_away=match.get('q2_vs'), q3_home=match.get('q3_hs'), q3_away=match.get('q3_vs'), q4_home=match.get('q4_hs'), q4_away=match.get('q4_vs'), status='played', source_quality='official_boxscore', source_note='Official LBA game page JSON/tabellini. LBA Lega valuation is mapped to PIR/RANK.', source_url=url)
        games.append(game_rec(**g))
        for rr in game['scores']['ht']['rows']:
            mins = to_num(rr.get('sec')) / 60 if not pd.isna(to_num(rr.get('sec'))) else to_num(rr.get('min'))
            if pd.isna(mins):
                minutes_raw = None
            else:
                total_sec = int(round(float(mins)*60))
                minutes_raw = f"{total_sec//60}:{total_sec%60:02d}"
            players.append(rec(country='Italy', league='LBA', competition=g['competition'], season=g['season'], phase=g['phase'], round=g['round'], game_id=g['game_id'], date_local=g['date_local'], status='played', source_quality=g['source_quality'], source_note=g['source_note'], source_url=g['source_url'], team_abbr='VIR', team_name=g['home_team'], opponent_abbr='MXR', opponent_name=g['away_team'], home_away='H', team_score=g['home_score'], opponent_score=g['away_score'], player=clean_player_name(f"{rr.get('player_name','').title()} {rr.get('player_surname','').title()}"), is_total=False, is_team_bench=False, pts=to_num(rr.get('pun')), reb=to_num(rr.get('rimbalzi_t')), dreb=to_num(rr.get('rimbalzi_d')), oreb=to_num(rr.get('rimbalzi_o')), ast=to_num(rr.get('ass')), blk=to_num(rr.get('stoppate_dat')), blka=to_num(rr.get('stoppate_sub')), fouls_drawn=to_num(rr.get('falli_sf')), fouls_committed=to_num(rr.get('falli_c')), stl=to_num(rr.get('palle_r')), tov=to_num(rr.get('palle_p')), minutes_raw=minutes_raw, minutes=mins, rank=to_num(rr.get('val_lega')), two_made=to_num(rr.get('t2_r')), two_att=to_num(rr.get('t2_t')), three_made=to_num(rr.get('t3_r')), three_att=to_num(rr.get('t3_t')), ft_made=to_num(rr.get('tl_r')), ft_att=to_num(rr.get('tl_t'))))
        tt=game['scores']['ht']['totals']
        totals.append(rec(country='Italy', league='LBA', competition=g['competition'], season=g['season'], phase=g['phase'], round=g['round'], game_id=g['game_id'], date_local=g['date_local'], status='played', source_quality=g['source_quality'], source_note=g['source_note'], source_url=g['source_url'], team_abbr='VIR', team_name=g['home_team'], opponent_abbr='MXR', opponent_name=g['away_team'], home_away='H', team_score=g['home_score'], opponent_score=g['away_score'], player='TOTAL', is_total=True, is_team_bench=False, pts=to_num(tt.get('pun')), reb=to_num(tt.get('rimbalzi_t')), dreb=to_num(tt.get('rimbalzi_d')), oreb=to_num(tt.get('rimbalzi_o')), ast=to_num(tt.get('ass')), blk=to_num(tt.get('stoppate_dat')), blka=to_num(tt.get('stoppate_sub')), fouls_drawn=to_num(tt.get('falli_sf')), fouls_committed=to_num(tt.get('falli_c')), stl=to_num(tt.get('palle_r')), tov=to_num(tt.get('palle_p')), minutes_raw=None, minutes=np.nan, rank=to_num(tt.get('val_lega')), two_made=to_num(tt.get('t2_r')), two_att=to_num(tt.get('t2_t')), three_made=to_num(tt.get('t3_r')), three_att=to_num(tt.get('t3_t')), ft_made=to_num(tt.get('tl_r')), ft_att=to_num(tt.get('tl_t'))))
    except Exception as e:
        print('LBA Virtus R2 parse failed', e)


def add_turkey_resultati_round2(games, players, totals):
    turkish_games=[
        dict(country='Turkey', league='BSL', competition='Türkiye Sigorta BSL', season='2026-27', phase='Regular Season', round='02', game_id='BSL-KWz0vR9j', date_local='2026-10-04 08:30', venue='Ülker Sports and Event Hall', home_team='Fenerbahçe', home_abbr='FBT', away_team='Körfez Basket', away_abbr='KOR', home_score=85, away_score=84, q1_home=25, q1_away=18, q2_home=20, q2_away=26, q3_home=23, q3_away=11, q4_home=17, q4_away=29, status='played', source_quality='third_party_boxscore', source_note='Rezultati.com/Flashscore final/player stats used because official TBF/BSL public box score was unavailable; PIR/RANK is estimated from available player stats.', source_url='https://www.rezultati.com/utakmica/kosarka/fenerbahce-rDhoZR1l/korfez-basket-pbAAjuKU/detalji/statistika-igraca/ukupno/?mid=KWz0vR9j'),
        dict(country='Turkey', league='BSL', competition='Türkiye Sigorta BSL', season='2026-27', phase='Regular Season', round='02', game_id='BSL-jHpUqmnT', date_local='2026-10-04 11:00', venue='', home_team='Bordo Bandırma', home_abbr='BOR', away_team='Anadolu Efes', away_abbr='EFS', home_score=79, away_score=85, q1_home=20, q1_away=19, q2_home=18, q2_away=26, q3_home=15, q3_away=16, q4_home=26, q4_away=24, status='played', source_quality='third_party_boxscore', source_note='Rezultati.com/Flashscore final/player stats used because official TBF/BSL public box score was unavailable; PIR/RANK is estimated from available player stats.', source_url='https://www.rezultati.com/utakmica/kosarka/anadolu-efes-ny4KlAOf/bordo-bandirma-vyggx7kG/detalji/statistika-igraca/ukupno/?mid=jHpUqmnT'),
    ]
    for g in turkish_games:
        games.append(game_rec(**g))
        try:
            jina='https://r.jina.ai/http://'+g['source_url']
            md=requests.get(jina,headers={'User-Agent':'Mozilla/5.0'},timeout=35).text
            if g['game_id']=='BSL-KWz0vR9j':
                abbr_map={'FEN':'FBT'}
                name_map={'FBT':'Fenerbahçe'}
            else:
                abbr_map={'EFE':'EFS'}
                name_map={'EFS':'Anadolu Efes'}
            new_rows=parse_resultati_players(md, g, abbr_map, name_map)
            players.extend(new_rows)
            add_resultati_totals(g, players, totals, name_map)
        except Exception as e:
            print('Turkey R2 Resultati parse failed', g['game_id'], e)


def aba_full_name_from_link(a):
    href=a.get('href') or ''
    m=re.search(r'/player/\d+/26/1/([^/]+)/', href)
    if m:
        parts=[p for p in unquote(m.group(1)).replace('-', ' ').split() if p]
        return ' '.join(w.capitalize() for w in parts)
    return clean_player_name(a.get_text(' ', strip=True).replace('*',''))


def parse_aba_player_table(table, game, team_abbr, team_name, opp_abbr, opp_name, ha):
    df=pd.read_html(StringIO(str(table)))[0]
    links=table.find_all('a')
    rows=[]
    for i,(_, rr) in enumerate(df.iterrows()):
        mins=minutes_to_float(rr.iloc[2])
        pts=to_num(rr.iloc[3]); rank=to_num(rr.iloc[28])
        # Skip clear DNP rows that ABA renders with 00:00 and empty stat cells.
        if (pd.isna(mins) or mins == 0) and pd.isna(pts) and pd.isna(rank):
            continue
        name=aba_full_name_from_link(links[i]) if i < len(links) else clean_player_name(rr.iloc[1])
        rows.append(rec(country='Regional', league='ABA', competition=game['competition'], season=game['season'], phase=game['phase'], round=game['round'], game_id=game['game_id'], date_local=game['date_local'], status='played', source_quality='official_boxscore', source_note='Official ABA League game-page box score. ABA Val is mapped to PIR/RANK.', source_url=game['source_url'], team_abbr=team_abbr, team_name=team_name, opponent_abbr=opp_abbr, opponent_name=opp_name, home_away=ha, team_score=game['home_score'] if ha=='H' else game['away_score'], opponent_score=game['away_score'] if ha=='H' else game['home_score'], player=name, is_total=False, is_team_bench=False, pts=pts, reb=to_num(rr.iloc[16]), dreb=to_num(rr.iloc[14]), oreb=to_num(rr.iloc[15]), ast=to_num(rr.iloc[17]), blk=to_num(rr.iloc[20]), blka=to_num(rr.iloc[21]), fouls_drawn=to_num(rr.iloc[23]), fouls_committed=to_num(rr.iloc[22]), stl=to_num(rr.iloc[18]), tov=to_num(rr.iloc[19]), minutes_raw=str(rr.iloc[2]).strip(), minutes=mins, rank=rank, two_made=to_num(rr.iloc[5]), two_att=to_num(rr.iloc[6]), three_made=to_num(rr.iloc[8]), three_att=to_num(rr.iloc[9]), ft_made=to_num(rr.iloc[11]), ft_att=to_num(rr.iloc[12])))
    return rows


def parse_aba_total_row(rr, game, team_abbr, team_name, opp_abbr, opp_name, ha):
    return rec(country='Regional', league='ABA', competition=game['competition'], season=game['season'], phase=game['phase'], round=game['round'], game_id=game['game_id'], date_local=game['date_local'], status='played', source_quality='official_boxscore', source_note='Official ABA League team total from game-page box score. ABA Val is mapped to PIR/RANK.', source_url=game['source_url'], team_abbr=team_abbr, team_name=team_name, opponent_abbr=opp_abbr, opponent_name=opp_name, home_away=ha, team_score=game['home_score'] if ha=='H' else game['away_score'], opponent_score=game['away_score'] if ha=='H' else game['home_score'], player='TOTAL', is_total=True, is_team_bench=False, pts=to_num(rr.iloc[3]), reb=to_num(rr.iloc[16]), dreb=to_num(rr.iloc[14]), oreb=to_num(rr.iloc[15]), ast=to_num(rr.iloc[17]), blk=to_num(rr.iloc[20]), blka=to_num(rr.iloc[21]), fouls_drawn=to_num(rr.iloc[23]), fouls_committed=to_num(rr.iloc[22]), stl=to_num(rr.iloc[18]), tov=to_num(rr.iloc[19]), minutes_raw=None, minutes=np.nan, rank=to_num(rr.iloc[28]), two_made=to_num(rr.iloc[5]), two_att=to_num(rr.iloc[6]), three_made=to_num(rr.iloc[8]), three_att=to_num(rr.iloc[9]), ft_made=to_num(rr.iloc[11]), ft_att=to_num(rr.iloc[12]))


def add_aba_official(games, players, totals):
    aba_games=[
        dict(country='Regional', league='ABA', competition='AdmiralBet ABA League', season='2026-27', phase='Regular Season - Group A', round='02', game_id='ABA-11-26', date_local='2026-10-04 18:00', venue='Arena KK FMP', home_team='FMP', home_abbr='FMP', away_team='Crvena zvezda Meridianbet', away_abbr='CZV', home_score=90, away_score=89, q1_home=23, q1_away=18, q2_home=27, q2_away=23, q3_home=18, q3_away=24, q4_home=22, q4_away=24, status='played', source_quality='official_boxscore', source_note='Official ABA League final/player box score. Partizan ABA game on 2026-10-05 is scheduled and excluded until final.', source_url='https://www.aba-liga.com/match/11/26/1/Overview/q1/1/home/fmp-crvena-zvezda-meridianbet/'),
        dict(country='Regional', league='ABA', competition='AdmiralBet ABA League', season='2026-27', phase='Regular Season - Group B', round='02', game_id='ABA-17-26', date_local='2026-10-04 20:00', venue='Mala dvorana Tivoli', home_team='Perspektiva Ilirija', home_abbr='ILI', away_team='Dubai Basketball', away_abbr='DUB', home_score=70, away_score=85, q1_home=15, q1_away=25, q2_home=12, q2_away=22, q3_home=15, q3_away=19, q4_home=28, q4_away=19, status='played', source_quality='official_boxscore', source_note='Official ABA League final/player box score. Partizan ABA game on 2026-10-05 is scheduled and excluded until final.', source_url='https://www.aba-liga.com/match/17/26/1/Overview'),
    ]
    headers={'User-Agent':'Mozilla/5.0'}
    for g in aba_games:
        games.append(game_rec(**g))
        try:
            html=requests.get(g['source_url'],headers=headers,timeout=30).text
            soup=BeautifulSoup(html,'html.parser')
            team_tables=soup.find_all('table', class_=lambda c: c and 'match_boxscore_team_table' in c)
            compare_tables=soup.find_all('table', class_=lambda c: c and 'match_boxscore_teams_compare_table' in c)
            if len(team_tables) >= 2:
                if g['home_abbr'] in EL_CLUBS:
                    players.extend(parse_aba_player_table(team_tables[0], g, g['home_abbr'], g['home_team'], g['away_abbr'], g['away_team'], 'H'))
                if g['away_abbr'] in EL_CLUBS:
                    players.extend(parse_aba_player_table(team_tables[1], g, g['away_abbr'], g['away_team'], g['home_abbr'], g['home_team'], 'A'))
            if compare_tables:
                cdf=pd.read_html(StringIO(str(compare_tables[0])))[0]
                if g['home_abbr'] in EL_CLUBS:
                    totals.append(parse_aba_total_row(cdf.iloc[0], g, g['home_abbr'], g['home_team'], g['away_abbr'], g['away_team'], 'H'))
                if g['away_abbr'] in EL_CLUBS:
                    totals.append(parse_aba_total_row(cdf.iloc[1], g, g['away_abbr'], g['away_team'], g['home_abbr'], g['home_team'], 'A'))
        except Exception as e:
            print('ABA parse failed', g['game_id'], e)


def add_israel_winner_cup_latest(games, players, totals):
    israel_games=[
        dict(country='Israel', league='IBSL', competition='Winner Cup', season='2026-27', phase='Semifinal', round='SF', game_id='ISR-26847', date_local='2026-10-03 20:55', venue='Toto Arena, Holon', home_team='Hapoel IBI Tel Aviv', home_abbr='HTA', away_team='Ironi Hai Motors Ness Ziona', away_abbr='INZ', home_score=79, away_score=76, q1_home=19, q1_away=23, q2_home=21, q2_away=14, q3_home=24, q3_away=20, q4_home=15, q4_away=19, status='played', source_quality='official_boxscore', source_note='Official IBSL Winner Cup semifinal box score. Winner Cup is marked separately from regular-season league games.', source_url='https://basket.co.il/game-zone.asp?GameId=26847&lang=en'),
        dict(country='Israel', league='IBSL', competition='Winner Cup', season='2026-27', phase='Semifinal', round='SF', game_id='ISR-26844', date_local='2026-10-04 19:00', venue='Toto Arena, Holon', home_team='Maccabi Rapyd Tel Aviv', home_abbr='MTA', away_team='Hapoel Midtown Jerusalem', away_abbr='JER', home_score=88, away_score=71, q1_home=15, q1_away=16, q2_home=16, q2_away=16, q3_home=28, q3_away=22, q4_home=29, q4_away=17, status='played', source_quality='official_boxscore', source_note='Official IBSL Winner Cup semifinal box score. Winner Cup is marked separately from regular-season league games.', source_url='https://basket.co.il/game-zone.asp?GameId=26844&lang=en'),
    ]
    headers={'User-Agent':'Mozilla/5.0'}
    for g in israel_games:
        games.append(game_rec(**g))
        try:
            html=requests.get(g['source_url'],headers=headers,timeout=30).text
            tables=pd.read_html(StringIO(html))
            home_rows, home_total = parse_israel_stat_table(tables[4], g, g['home_abbr'], g['home_team'], g['away_abbr'], g['away_team'], 'H')
            away_rows, away_total = parse_israel_stat_table(tables[5], g, g['away_abbr'], g['away_team'], g['home_abbr'], g['home_team'], 'A')
            for r in home_rows + away_rows:
                if r['team_abbr'] in EL_CLUBS:
                    players.append(r)
            for r in [home_total, away_total]:
                if r and r['team_abbr'] in EL_CLUBS:
                    totals.append(r)
        except Exception as e:
            print('Israel Winner Cup latest parse failed', g['game_id'], e)


def add_bayern_bbl(games, players, totals):
    g=dict(country='Germany', league='BBL', competition='easyCredit BBL', season='2026-27', phase='Regular Season', round='04', game_id='BBL-866697', date_local='2026-10-04', venue='SAP Garden', home_team='FC Bayern Munich', home_abbr='BAY', away_team='EWE Baskets Oldenburg', away_abbr='OLD', home_score=113, away_score=60, q1_home=17, q1_away=18, q2_home=40, q2_away=13, q3_home=32, q3_away=18, q4_home=24, q4_away=11, status='played', source_quality='third_party_boxscore', source_note='Proballers full BBL box score used because the official easyCredit BBL box score was not accessible in the workspace. Minutes, shooting and Eff are imported; Eff is mapped to PIR/RANK for domestic context only.', source_url='https://www.proballers.com/basketball/game/866697/fc-bayern-munich-ewe-baskets-oldenburg-2026-10-04')
    games.append(game_rec(**g))
    rows=[
        ('Oscar Da Silva',17,26,7,6,1,2,1,0,4,2,0,7,9,0,1,3,4,25),
        ('Johannes Thiemann',15,13,4,2,2,3,0,0,2,0,0,3,4,0,0,9,9,21),
        ('Duane Washington',19,15,3,3,0,1,0,0,3,1,0,3,4,4,7,1,1,20),
        ('Johannes Voigtmann',7,14,9,5,4,2,0,0,1,1,0,3,5,0,0,1,1,17),
        ('Justinian Jessup',10,18,3,3,0,3,0,1,0,3,0,2,3,2,6,0,0,13),
        ('Vladimir Lucic',7,14,2,1,1,3,0,0,0,1,0,1,1,1,2,2,2,12),
        ('Tobias Jensen',6,15,2,2,0,3,1,0,2,0,0,2,2,0,0,2,2,12),
        ('Rokas Jokubaitis',10,15,1,1,0,3,0,3,2,0,0,3,3,1,3,1,1,9),
        ('Kamar Baldwin',2,13,3,2,1,3,0,0,3,1,0,0,0,0,0,2,2,9),
        ('Niels Giffey',10,22,0,0,0,0,1,1,2,0,0,1,3,2,3,2,2,7),
        ('Justus Hollatz',5,16,1,1,0,3,0,0,2,2,0,2,5,0,0,1,2,7),
        ('Andreas Obst',5,18,1,1,0,3,0,1,0,0,0,1,2,1,4,0,0,4),
    ]
    for name,pts,mins,reb,dreb,oreb,ast,blk,tov,pf,stl,blka,two_m,two_a,three_m,three_a,ft_m,ft_a,rank in rows:
        players.append(rec(country='Germany', league='BBL', competition=g['competition'], season=g['season'], phase=g['phase'], round=g['round'], game_id=g['game_id'], date_local=g['date_local'], status='played', source_quality=g['source_quality'], source_note=g['source_note'], source_url=g['source_url'], team_abbr='BAY', team_name='FC Bayern Munich', opponent_abbr='OLD', opponent_name='EWE Baskets Oldenburg', home_away='H', team_score=113, opponent_score=60, player=name, is_total=False, is_team_bench=False, pts=pts, reb=reb, dreb=dreb, oreb=oreb, ast=ast, blk=blk, blka=blka, fouls_drawn=np.nan, fouls_committed=pf, stl=stl, tov=tov, minutes_raw=str(mins), minutes=float(mins), rank=rank, two_made=two_m, two_att=two_a, three_made=three_m, three_att=three_a, ft_made=ft_m, ft_att=ft_a))
    totals.append(rec(country='Germany', league='BBL', competition=g['competition'], season=g['season'], phase=g['phase'], round=g['round'], game_id=g['game_id'], date_local=g['date_local'], status='played', source_quality=g['source_quality'], source_note=g['source_note'], source_url=g['source_url'], team_abbr='BAY', team_name='FC Bayern Munich', opponent_abbr='OLD', opponent_name='EWE Baskets Oldenburg', home_away='H', team_score=113, opponent_score=60, player='TOTAL', is_total=True, is_team_bench=False, pts=113, reb=36, dreb=27, oreb=9, ast=29, blk=3, blka=np.nan, fouls_drawn=np.nan, fouls_committed=21, stl=11, tov=6, minutes_raw=None, minutes=np.nan, rank=156, two_made=28, two_att=41, three_made=11, three_att=26, ft_made=24, ft_att=26))


def add_france_summary(games, players, totals):
    note='Official LNB/Betclic Elite final score from the league calendar. Full game-level player boxscore was not exposed in the static match-center export, so France is imported as official result + season-average minutes/index rows in the averages table.'
    french_games=[
        dict(country='France', league='Betclic Elite', competition='Betclic Elite', season='2026-27', phase='Regular Season', round='01', game_id='FRA-LNB-9c79420c', date_local='2026-09-27 10:30', venue='', home_team='Nancy', home_abbr='NAN', away_team='Paris Basketball', away_abbr='PBB', home_score=73, away_score=78, status='played', source_quality='official_result_average_only', source_note=note, source_url='https://lnb.fr/fr/match-center/9c79420c-a543-11f1-aaad-b9515c5be892'),
        dict(country='France', league='Betclic Elite', competition='Betclic Elite', season='2026-27', phase='Regular Season', round='01', game_id='FRA-LNB-390be9fd', date_local='2026-09-27 13:00', venue='', home_team='Cholet', home_abbr='CHO', away_team='ASVEL', away_abbr='ASV', home_score=85, away_score=97, status='played', source_quality='official_result_average_only', source_note=note, source_url='https://lnb.fr/fr/match-center/390be9fd-a542-11f1-8a78-5392b5a73941'),
        dict(country='France', league='Betclic Elite', competition='Betclic Elite', season='2026-27', phase='Regular Season', round='02', game_id='FRA-LNB-9d0c328d', date_local='2026-10-04 10:30', venue='Sportica, Gravelines', home_team='Gravelines-Dunkerque', home_abbr='GRA', away_team='ASVEL', away_abbr='ASV', home_score=65, away_score=70, status='played', source_quality='official_result_average_only', source_note=note, source_url='https://lnb.fr/fr/calendar/betclicelite?did=1&abbrev=PROA&yid=2026&cid=317'),
        dict(country='France', league='Betclic Elite', competition='Betclic Elite', season='2026-27', phase='Regular Season', round='02', game_id='FRA-LNB-9d196005', date_local='2026-10-04 12:50', venue='Antarès', home_team='Le Mans', home_abbr='LEM', away_team='Paris Basketball', away_abbr='PBB', home_score=101, away_score=103, q1_home=21, q1_away=17, q2_home=20, q2_away=29, q3_home=33, q3_away=25, q4_home=27, q4_away=32, status='played', source_quality='official_result_average_only', source_note=note, source_url='https://lnb.fr/fr/match-center/9d196005-a543-11f1-9c31-b9515c5be892'),
    ]
    for g in french_games:
        games.append(game_rec(**g))


def _mmss_to_min(v):
    if v in (None, '', '-'):
        return np.nan
    if isinstance(v, (int, float)):
        return float(v)
    txt=str(v).strip().replace('’', ':').replace("'", ':').replace('″','').replace('"','')
    if ':' in txt:
        a,b=txt.split(':',1)
        return round(float(a)+float(b)/60.0, 2)
    return float(txt)


def france_average_rows():
    # Betclic Elite 2026-27 season averages for the two EuroLeague clubs, after R2.
    # Minutes + Eval are the important scouting columns requested by the user.
    # Sources checked: official LNB team/player season-stat pages; BeBasket team statistic pages provide the same table in one static export.
    rows=[
        # ASVEL / Lyon-Villeurbanne
        ('ASV','ASVEL','Patty Mills',1,'21:26',16.0,17.0,1.0,0.0,9.0,'2026-10-04'),
        ('ASV','ASVEL','Jae Crowder',1,'22:05',19.0,16.0,3.0,4.0,11.0,'2026-10-04'),
        ('ASV','ASVEL','Tremont Waters',2,'19:33',17.5,15.0,1.0,4.5,7.0,'2026-10-04'),
        ('ASV','ASVEL','Hugo Besson',2,'21:16',10.0,10.5,2.0,5.5,8.0,'2026-10-04'),
        ('ASV','ASVEL','Both Gach',2,'23:05',7.5,8.5,3.5,1.0,7.0,'2026-10-04'),
        ('ASV','ASVEL','Marc-Owen Fodzo Dada',2,'21:30',9.5,8.5,6.0,2.5,6.0,'2026-10-04'),
        ('ASV','ASVEL','Nate Sestina',2,'18:15',3.0,6.5,1.5,0.0,6.5,'2026-10-04'),
        ('ASV','ASVEL','Joel Bolomboy',2,'24:13',15.0,6.0,7.0,2.5,2.5,'2026-10-04'),
        ('ASV','ASVEL','Bodian Massa',2,'12:46',6.5,4.5,3.0,0.5,3.0,'2026-10-04'),
        ('ASV','ASVEL','Yves Pons',2,'13:44',5.5,4.5,2.0,0.0,2.5,'2026-10-04'),
        ('ASV','ASVEL','Myles Cale',1,'11:57',2.0,4.0,2.0,0.0,4.0,'2026-10-04'),
        ('ASV','ASVEL','David Lighty',1,'06:46',1.0,2.0,0.0,0.0,1.0,'2026-10-04'),
        ('ASV','ASVEL','Edwin Jackson',2,'14:33',-1.0,0.0,2.0,1.5,4.0,'2026-10-04'),
        # Paris Basketball
        ('PBB','Paris Basketball','Nadir Hifi',2,'26:05',25.0,28.0,2.0,5.5,18.5,'2026-10-04'),
        ('PBB','Paris Basketball','Tyson Etienne',1,'22:49',20.0,23.0,2.0,2.0,15.0,'2026-10-04'),
        ('PBB','Paris Basketball','Jared Rhoden',1,'23:38',17.0,15.0,3.0,2.0,9.0,'2026-10-04'),
        ('PBB','Paris Basketball','T.J. Warren',1,'19:19',13.0,14.0,6.0,1.0,14.0,'2026-10-04'),
        ('PBB','Paris Basketball','Sebastian Herrera',2,'21:38',9.0,10.0,1.5,2.0,8.0,'2026-10-04'),
        ('PBB','Paris Basketball','Daulton Hommes',1,'16:25',5.0,7.0,1.0,1.0,5.0,'2026-10-04'),
        ('PBB','Paris Basketball','Alize Johnson',2,'15:20',6.5,5.0,6.0,2.0,6.0,'2026-10-04'),
        ('PBB','Paris Basketball','Allan Dokossi',2,'18:54',13.0,5.0,8.5,2.5,3.0,'2026-10-04'),
        ('PBB','Paris Basketball','Terry Tarpey',2,'18:33',12.0,4.5,6.5,2.0,3.0,'2026-10-04'),
        ('PBB','Paris Basketball','Léopold Cavaliere',2,'22:34',5.0,4.0,3.5,0.0,3.5,'2026-10-04'),
        ('PBB','Paris Basketball','Joël Ayayi',2,'08:49',4.0,3.0,1.5,1.0,1.5,'2026-10-04'),
        ('PBB','Paris Basketball','Mãozinha Pereira',2,'07:20',0.0,1.0,0.0,0.0,2.0,'2026-10-04'),
        ('PBB','Paris Basketball','Frank Ntilikina',2,'14:54',-1.5,0.5,1.5,1.0,3.0,'2026-10-04'),
        ('PBB','Paris Basketball','Mouhamed Faye',1,'09:40',1.0,0.0,1.0,0.0,1.0,'2026-10-04'),
    ]
    out=[]
    for team_abbr, team_name, player, gp, mins, eval_avg, pts, reb, ast, fga, last in rows:
        m=_mmss_to_min(mins)
        out.append({
            'country':'France','league':'Betclic Elite','team_abbr':team_abbr,'team_name':team_name,'player':player,
            'games_played':int(gp),'rank_games':int(gp),'avg_minutes':round(float(m),2),'avg_pir':float(eval_avg),
            'avg_pts':float(pts),'avg_reb':float(reb),'avg_ast':float(ast),'avg_fg_att':float(fga),
            'avg_fga_per_min':round(float(fga)/float(m),3) if m else np.nan,
            'avg_pir_per_min':round(float(eval_avg)/float(m),3) if m else np.nan,
            'last_game_date':last,
        })
    return pd.DataFrame(out)


def append_france_averages(averages_df):
    fr=france_average_rows()
    if averages_df is None or averages_df.empty:
        return fr
    base=averages_df[~averages_df['team_abbr'].isin(['ASV','PBB'])].copy()
    out=pd.concat([base, fr], ignore_index=True)
    out=out[averages_df.columns].sort_values(['team_abbr','avg_pir','avg_minutes'], ascending=[True,False,False])
    return out

def clean_records(df):
    def conv(v):
        try:
            if pd.isna(v):
                return None
        except Exception:
            pass
        if isinstance(v,(np.integer,)):
            return int(v)
        if isinstance(v,(np.floating,float)):
            if math.isnan(float(v)) or math.isinf(float(v)):
                return None
            # avoid 7.0 in JSON but fine
            return round(float(v),4)
        if isinstance(v,(np.bool_,bool)):
            return bool(v)
        return v
    return [{k:conv(v) for k,v in row.items()} for row in df.to_dict(orient='records')]


def compute_player_averages(players_df):
    avg_cols=['country','league','team_abbr','team_name','player','games_played','rank_games','avg_minutes','avg_pir','avg_pts','avg_reb','avg_ast','avg_fg_att','avg_fga_per_min','avg_pir_per_min','last_game_date']
    if players_df is None or players_df.empty:
        return pd.DataFrame(columns=avg_cols)
    df=players_df.copy()
    df=df[(df['team_abbr'].isin(EL_CLUBS)) & (~df['is_total'].fillna(False).astype(bool)) & (~df['is_team_bench'].fillna(False).astype(bool))]
    if df.empty:
        return pd.DataFrame(columns=avg_cols)
    for c in ['minutes','rank','pts','reb','ast','fg_att']:
        df[c]=pd.to_numeric(df[c], errors='coerce')
    grouped=[]
    for keys,g in df.groupby(['country','league','team_abbr','team_name','player'], dropna=False):
        games_played=int(g['game_id'].nunique())
        rank_games=int(g['rank'].notna().sum())
        min_sum=g['minutes'].sum(skipna=True)
        rank_sum=g['rank'].sum(skipna=True)
        fg_sum=g['fg_att'].sum(skipna=True)
        avg={
            'country':keys[0], 'league':keys[1], 'team_abbr':keys[2], 'team_name':keys[3], 'player':keys[4],
            'games_played':games_played, 'rank_games':rank_games,
            'avg_minutes':round(float(g['minutes'].mean()),2) if g['minutes'].notna().any() else np.nan,
            'avg_pir':round(float(g['rank'].mean()),2) if g['rank'].notna().any() else np.nan,
            'avg_pts':round(float(g['pts'].mean()),2) if g['pts'].notna().any() else np.nan,
            'avg_reb':round(float(g['reb'].mean()),2) if g['reb'].notna().any() else np.nan,
            'avg_ast':round(float(g['ast'].mean()),2) if g['ast'].notna().any() else np.nan,
            'avg_fg_att':round(float(g['fg_att'].mean()),2) if g['fg_att'].notna().any() else np.nan,
            'avg_fga_per_min':round(float(fg_sum/min_sum),3) if min_sum and not pd.isna(min_sum) else np.nan,
            'avg_pir_per_min':round(float(rank_sum/min_sum),3) if min_sum and rank_games and not pd.isna(rank_sum) else np.nan,
            'last_game_date':str(g['date_local'].max()) if 'date_local' in g else None,
        }
        grouped.append(avg)
    out=pd.DataFrame(grouped)
    if out.empty:
        return pd.DataFrame(columns=avg_cols)
    out=out[avg_cols].sort_values(['team_abbr','avg_pir','avg_minutes'], ascending=[True,False,False])
    return out


def build_data():
    games=[]; players=[]; totals=[]
    add_greek(games, players, totals)
    add_greek_regular_season(games, players, totals)
    add_acb(games, players, totals)
    add_acb_round2(games, players, totals)
    add_lkl(games, players, totals)
    add_lkl_latest(games, players, totals)
    add_lba_milano(games, players, totals)
    add_lba_virtus(games, players, totals)
    add_lba_virtus_round2(games, players, totals)
    add_turkey_resultati(games, players, totals)
    add_turkey_resultati_round2(games, players, totals)
    add_aba_official(games, players, totals)
    add_israel_winner_cup(games, players, totals)
    add_israel_winner_cup_latest(games, players, totals)
    add_bayern_bbl(games, players, totals)
    add_france_summary(games, players, totals)
    games_df=pd.DataFrame(games)
    players_df=pd.DataFrame(players)
    totals_df=pd.DataFrame(totals)
    for col in GAME_COLS:
        if col not in games_df.columns: games_df[col]=None
    for col in STD_COLS:
        if col not in players_df.columns: players_df[col]=None
        if col not in totals_df.columns: totals_df[col]=None
    games_df=games_df[GAME_COLS]
    players_df=players_df[STD_COLS]
    totals_df=totals_df[STD_COLS]
    averages_df=append_france_averages(compute_player_averages(players_df))
    DATA.mkdir(exist_ok=True)
    players_df.to_csv(DATA / 'domestic_player_boxscores.csv', index=False)
    totals_df.to_csv(DATA / 'domestic_team_boxscores.csv', index=False)
    games_df.to_csv(DATA / 'domestic_games.csv', index=False)
    averages_df.to_csv(DATA / 'domestic_player_averages.csv', index=False)
    players_df.to_csv(SITE / 'domestic-player-boxscores.csv', index=False)
    totals_df.to_csv(SITE / 'domestic-team-boxscores.csv', index=False)
    games_df.to_csv(SITE / 'domestic-games.csv', index=False)
    averages_df.to_csv(SITE / 'domestic-player-averages.csv', index=False)
    return games_df, players_df, totals_df, averages_df


def make_page(lang, filename, route, title, subtitle, labels):
    games, players, totals, averages = make_page.games, make_page.players, make_page.totals, make_page.averages
    generated = datetime.now(LOCAL_TZ).strftime('%Y-%m-%d %H:%M CET')
    rankable = players[(players['team_abbr'].isin(EL_CLUBS)) & (pd.to_numeric(players['rank'], errors='coerce').notna())].copy()
    rankable['rank_num'] = pd.to_numeric(rankable['rank'], errors='coerce')
    top_rank = rankable.sort_values('rank_num', ascending=False).head(12).drop(columns=['rank_num'], errors='ignore')
    top_pts = players[players['team_abbr'].isin(EL_CLUBS)].sort_values('pts', ascending=False).head(12)
    top_min = players[players['team_abbr'].isin(EL_CLUBS)].sort_values('minutes', ascending=False).head(12)
    avg_rankable = averages[pd.to_numeric(averages['avg_pir'], errors='coerce').notna()].copy() if not averages.empty else averages
    avg_minable = averages[pd.to_numeric(averages['avg_minutes'], errors='coerce').notna()].copy() if not averages.empty else averages
    top_avg_pir = avg_rankable.sort_values('avg_pir', ascending=False).head(12) if not avg_rankable.empty else avg_rankable
    top_avg_min = avg_minable.sort_values('avg_minutes', ascending=False).head(12) if not avg_minable.empty else avg_minable
    coverage = [
        {'team':'Žalgiris','status':'extracted','note':'4 LKL league games through 2026-10-04'},
        {'team':'Barcelona','status':'extracted','note':'Liga Endesa R1 + R2 finals'},
        {'team':'Baskonia','status':'extracted','note':'Liga Endesa R1 + R2 finals'},
        {'team':'Valencia','status':'extracted','note':'Liga Endesa R1 + R2 finals'},
        {'team':'Real Madrid','status':'extracted','note':'Liga Endesa R1 + R2 finals'},
        {'team':'Olimpia Milano','status':'extracted','note':'LBA R1 final; R2 is scheduled for 2026-10-05 and excluded'},
        {'team':'Virtus Bologna','status':'extracted','note':'LBA R1 + R2 finals'},
        {'team':'Fenerbahçe','status':'extracted','note':'BSL R1 + R2 via Rezultati.com with player minutes/shots; PIR estimated from available stats'},
        {'team':'Anadolu Efes','status':'extracted','note':'BSL R1 + R2 via Rezultati.com with player minutes/shots; PIR estimated from available stats'},
        {'team':'Beşiktaş','status':'extracted','note':'BSL R1 via Rezultati.com; R2 is scheduled for 2026-10-05 and excluded'},
        {'team':'Crvena zvezda','status':'extracted','note':'ABA League R2 final official box score'},
        {'team':'Partizan','status':'pending','note':'ABA League game vs Mega is scheduled for 2026-10-05 and excluded until final'},
        {'team':'Dubai Basketball','status':'extracted','note':'ABA League R2 final official box score'},
        {'team':'Olympiacos','status':'extracted','note':'Greek Super Cup semifinal + final and Stoiximan GBL R1 final'},
        {'team':'Panathinaikos','status':'extracted','note':'Greek Super Cup semifinal and Stoiximan GBL R1 final'},
        {'team':'Maccabi Tel Aviv','status':'extracted','note':'Israel Winner Cup quarterfinal + semifinal; regular-season Winner League is still GP 0'},
        {'team':'Hapoel Tel Aviv','status':'extracted','note':'Israel Winner Cup quarterfinal + semifinal; regular-season Winner League is still GP 0'},
        {'team':'Bayern Munich','status':'extracted','note':'BBL final via Proballers full box score because official BBL box score was not accessible'},
        {'team':'ASVEL','status':'average-only','note':'Betclic Elite R1 + R2 results imported from LNB; player season averages include official minutes and Eval/index through 2 games'},
        {'team':'Paris Basketball','status':'average-only','note':'Betclic Elite R1 + R2 results imported from LNB; player season averages include official minutes and Eval/index through 2 games'},
    ]
    payload = {
        'generated': generated,
        'games': clean_records(games),
        'players': clean_records(players),
        'totals': clean_records(totals),
        'averages': clean_records(averages),
        'topAvgMin': clean_records(top_avg_min),
        'topAvgPir': clean_records(top_avg_pir),
        'topRank': clean_records(top_rank),
        'topPoints': clean_records(top_pts),
        'topMinutes': clean_records(top_min),
        'coverage': coverage,
        'labels': labels,
        'elTeams': sorted(EL_CLUBS),
    }
    js = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
    lang_links = '<div class="feiq-language-switcher"><a href="/euroleague/domestic-competitions">EN</a><a href="/sr/euroleague/domestic-competitions">SR</a><a href="/el/euroleague/domestic-competitions">EL</a></div>'
    nav_text = {
        'en': ('Dashboard','Lineup IQ','Defense vs Position','Domestic'),
        'sr': ('Dashboard','Lineup IQ','Defense vs Position','Domaća'),
        'el': ('Dashboard','Lineup IQ','Defense vs Position','Εγχώρια')
    }[lang]
    nav_prefix = '' if lang=='en' else '/' + lang
    css = r'''
:root{--bg:#08111f;--panel:#0e2038;--line:rgba(255,255,255,.1);--txt:#eef6ff;--mut:#aabbd2;--blue:#5bbcff;--green:#22c55e;--yellow:#ffd166;--red:#fb7185}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at top left,#173a63,#08111f 55%);color:var(--txt);font-family:Inter,system-ui,Segoe UI,Arial,sans-serif;font-size:14px}a{color:#8ed6ff;text-decoration:none}.feiq-language-switcher{position:sticky;top:0;z-index:9999;display:flex;justify-content:flex-end;gap:8px;padding:8px 14px;background:rgba(7,16,29,.92);backdrop-filter:blur(8px);border-bottom:1px solid rgba(255,255,255,.08)}.feiq-language-switcher a{color:#d8f1ff;border:1px solid rgba(91,188,255,.35);border-radius:999px;padding:5px 10px;font-size:12px;font-weight:900;background:rgba(91,188,255,.08)}header{padding:24px;background:linear-gradient(135deg,#07101d,#122b49);border-bottom:1px solid var(--line)}.topnav{display:flex;justify-content:space-between;gap:14px;align-items:center;margin-bottom:20px}.brand{font-weight:950;font-size:18px}.brand span{color:var(--blue)}.navlinks{display:flex;gap:14px;color:var(--mut);font-size:13px;flex-wrap:wrap}h1{margin:0 0 8px;font-size:clamp(26px,4vw,44px);letter-spacing:-.05em}.sub{color:var(--mut);font-size:16px;max-width:1050px;line-height:1.5}main{padding:22px 24px 46px}.tabs{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 16px}button,.btn{background:#143052;color:#fff;border:1px solid rgba(91,188,255,.24);border-radius:12px;padding:10px 13px;font-weight:800;cursor:pointer}button.active{background:#0d75bd;border-color:#7bd3ff}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:14px;margin:16px 0 22px}.card{background:rgba(14,32,56,.92);border:1px solid var(--line);border-radius:18px;padding:16px;box-shadow:0 16px 50px rgba(0,0,0,.18)}.card h3{margin:0 0 12px;font-size:16px}.row{display:flex;justify-content:space-between;gap:12px;padding:7px 0;border-bottom:1px solid rgba(255,255,255,.07)}.row:last-child{border-bottom:0}.row span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.row b{color:#fff}.panel{display:none}.panel.active{display:block}.filters{display:flex;gap:10px;flex-wrap:wrap;margin:12px 0 16px}input,select{background:#0b1b30;border:1px solid rgba(255,255,255,.12);color:#eef6ff;border-radius:12px;padding:10px 12px}.tablewrap{overflow:auto;max-height:72vh;border:1px solid var(--line);border-radius:16px;background:#0b1b30}table{border-collapse:separate;border-spacing:0;min-width:100%;font-size:12px}th,td{padding:9px 10px;border-bottom:1px solid rgba(255,255,255,.08);white-space:nowrap;text-align:left}th{position:sticky;top:0;background:#193b63;color:#fff;z-index:3;cursor:pointer}td:first-child,th:first-child{position:sticky;left:0;background:inherit;z-index:2}th:first-child{z-index:4;background:#193b63}.note{background:rgba(255,209,102,.08);border:1px solid rgba(255,209,102,.25);border-radius:16px;padding:14px;color:#ffe8a3;margin:14px 0;line-height:1.55}.mut{color:var(--mut)}.good{color:#86efac;font-weight:800}.warn{color:#fde68a;font-weight:800}.bad{color:#fecdd3;font-weight:800}.pill{display:inline-flex;border-radius:999px;padding:3px 8px;background:rgba(91,188,255,.12);border:1px solid rgba(91,188,255,.25);align-items:center;gap:6px}.statgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px;margin:14px 0}.stat{background:rgba(91,188,255,.08);border:1px solid rgba(91,188,255,.18);border-radius:14px;padding:12px}.stat b{display:block;font-size:22px}@media(max-width:760px){header,main{padding-left:14px;padding-right:14px}.topnav{display:block}.navlinks{display:flex;gap:8px;overflow-x:auto;white-space:nowrap;margin-top:10px;padding-bottom:6px}.navlinks a{flex:0 0 auto;border:1px solid rgba(91,188,255,.25);border-radius:999px;padding:7px 10px;background:rgba(91,188,255,.08)}.tabs{display:flex;flex-wrap:nowrap;overflow-x:auto;padding-bottom:6px}.tabs button{flex:0 0 auto}.filters{display:grid;grid-template-columns:1fr}.tablewrap{max-height:68vh}.tablewrap:before{content:'Swipe sideways to see all columns';display:block;position:sticky;left:0;top:0;z-index:6;background:#0b1b30;color:#9fd8ff;border-bottom:1px solid rgba(255,255,255,.1);padding:8px 10px;font-size:12px;font-weight:800}table{min-width:980px}.cards{grid-template-columns:1fr}}
'''
    template = r'''<!doctype html><html lang="__LANG__"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>__TITLE__ — Fantasy Edge IQ</title><meta name="description" content="Domestic league and Greek Super Cup results and box-score stats for EuroLeague clubs, kept separate from EuroLeague numbers."><link rel="canonical" href="https://www.fantasyedgeiq.com__ROUTE__"><link rel="alternate" hreflang="en" href="https://www.fantasyedgeiq.com/euroleague/domestic-competitions"><link rel="alternate" hreflang="sr" href="https://www.fantasyedgeiq.com/sr/euroleague/domestic-competitions"><link rel="alternate" hreflang="el" href="https://www.fantasyedgeiq.com/el/euroleague/domestic-competitions"><link rel="alternate" hreflang="x-default" href="https://www.fantasyedgeiq.com/euroleague/domestic-competitions"><meta name="robots" content="index,follow"><script defer src="/_vercel/insights/script.js"></script><style>__CSS__</style></head><body>__LANG_LINKS__<header><div class="topnav"><a class="brand" href="/">Fantasy Edge <span>IQ</span></a><nav class="navlinks"><a href="__NAV_PREFIX__/euroleague/dashboard">__NAV1__</a><a href="__NAV_PREFIX__/euroleague/team-analyzer">__NAV2__</a><a href="__NAV_PREFIX__/euroleague/defense-vs-position">__NAV3__</a><a href="__NAV_PREFIX__/euroleague/domestic-competitions">__NAV4__</a></nav></div><h1>__TITLE__</h1><div class="sub">__SUBTITLE__ <b id="gen"></b></div></header><main><div class="tabs"><button class="tab active" data-tab="overview">__L_OVERVIEW__</button><button class="tab" data-tab="results">__L_RESULTS__</button><button class="tab" data-tab="players">__L_PLAYERS__</button><button class="tab" data-tab="averages">__L_AVERAGES__</button><button class="tab" data-tab="teams">__L_TEAMS__</button><button class="tab" data-tab="coverage">__L_COVERAGE__</button><button class="tab" data-tab="method">__L_METHOD__</button></div><section id="overview" class="panel active"><div class="note">__L_NOTE__</div><div class="statgrid"><div class="stat"><span>__L_GAMES_EXTRACTED__</span><b id="statGames"></b></div><div class="stat"><span>__L_CLUB_ROWS__</span><b id="statPlayers"></b></div><div class="stat"><span>__L_COUNTRIES__</span><b id="statCountries"></b></div><div class="stat"><span>__L_POINTS_ONLY__</span><b id="statPartial"></b></div></div><div class="cards"><div class="card"><h3>__L_LATEST__</h3><div id="latestBox"></div></div><div class="card"><h3>__L_TOP_AVG_MIN__</h3><div id="rankBox"></div></div><div class="card"><h3>__L_TOP_AVG_PIR__</h3><div id="pointsBox"></div></div></div></section><section id="results" class="panel"><h2>__L_RESULTS__</h2><div class="filters"><select id="gameCountry" onchange="renderCurrent()"><option value="">__L_ALL_COUNTRIES__</option></select><select id="gameLeague" onchange="renderCurrent()"><option value="">__L_ALL_LEAGUES__</option></select></div><div class="tablewrap"><table id="gamesTable"></table></div></section><section id="players" class="panel"><h2>__L_PLAYERS__</h2><div class="filters"><input id="pq" placeholder="__L_SEARCH__" oninput="renderCurrent()"><select id="countryFilter" onchange="renderCurrent()"><option value="">__L_ALL_COUNTRIES__</option></select><select id="leagueFilter" onchange="renderCurrent()"><option value="">__L_ALL_LEAGUES__</option></select><select id="teamFilter" onchange="renderCurrent()"><option value="">__L_ALL_TEAMS__</option></select><label class="pill"><input id="onlyEl" type="checkbox" checked onchange="renderCurrent()"> __L_ONLY_EL__</label></div><div class="tablewrap"><table id="playersTable"></table></div></section><section id="averages" class="panel"><h2>__L_AVERAGES__</h2><div class="note">__L_AVERAGES_NOTE__</div><div class="filters"><input id="avgQ" placeholder="__L_SEARCH__" oninput="renderCurrent()"><select id="avgCountry" onchange="renderCurrent()"><option value="">__L_ALL_COUNTRIES__</option></select><select id="avgLeague" onchange="renderCurrent()"><option value="">__L_ALL_LEAGUES__</option></select><select id="avgTeam" onchange="renderCurrent()"><option value="">__L_ALL_TEAMS__</option></select><label class="pill"><input id="avgOnlyEl" type="checkbox" checked onchange="renderCurrent()"> __L_ONLY_EL__</label></div><div class="tablewrap"><table id="averagesTable"></table></div></section><section id="teams" class="panel"><h2>__L_TEAMS__</h2><div class="tablewrap"><table id="teamsTable"></table></div></section><section id="coverage" class="panel"><h2>__L_COVERAGE__</h2><div class="note">__L_COVERAGE_NOTE__</div><div class="tablewrap"><table id="coverageTable"></table></div></section><section id="method" class="panel"><div class="note">__L_METHOD_TEXT__</div></section></main><script>const DATA=__DATA__;
const numCols=new Set(['home_score','away_score','q1_home','q1_away','q2_home','q2_away','q3_home','q3_away','q4_home','q4_away','team_score','opponent_score','pts','two_made','two_att','three_made','three_att','ft_made','ft_att','fg_made','fg_att','fg_pct','reb','dreb','oreb','ast','blk','blka','fouls_drawn','fouls_committed','stl','tov','minutes','rank','fga_per_min','rank_per_min','games_played','rank_games','avg_minutes','avg_pir','avg_pts','avg_reb','avg_ast','avg_fg_att','avg_fga_per_min','avg_pir_per_min']);
const elTeams=new Set(DATA.elTeams);let sortState={};function label(c){return DATA.labels[c]||c}function fmt(c,v){if(v===null||v===undefined||Number.isNaN(v))return '';if(typeof v==='boolean')return v?'Yes':'No';if(c==='status')return v==='played'?'<span class="good">played</span>':String(v);if(c==='source_quality'){let cls=(String(v).includes('summary')||String(v).includes('third_party')||String(v).includes('average_only'))?'warn':'good';return `<span class="${cls}">${v}</span>`}if(c==='status'&&v==='pending')return '<span class="warn">pending</span>';if(numCols.has(c)&&!isNaN(Number(v))){let n=Number(v);return Number.isInteger(n)?String(n):String(Math.round(n*100)/100)}return String(v)}function ftext(r,q){if(!q)return true;q=q.toLowerCase();return Object.values(r).some(v=>String(v??'').toLowerCase().includes(q))}function cmp(a,b,c,dir){let av=a[c],bv=b[c],an=Number(av),bn=Number(bv);let res;if(av==null&&bv==null)res=0;else if(av==null)res=1;else if(bv==null)res=-1;else if(!Number.isNaN(an)&&!Number.isNaN(bn))res=an-bn;else res=String(av).localeCompare(String(bv));return dir==='asc'?res:-res}function table(id,rows,cols,key){let st=sortState[key];if(st)rows=[...rows].sort((a,b)=>cmp(a,b,st.c,st.d));let h='<thead><tr>'+cols.map(c=>`<th onclick="setSort('${key}','${c}')">${label(c)}${st&&st.c===c?(st.d==='asc'?' ↑':' ↓'):''}</th>`).join('')+'</tr></thead>';let b='<tbody>'+rows.map(r=>'<tr>'+cols.map(c=>`<td>${fmt(c,r[c])}</td>`).join('')+'</tr>').join('')+'</tbody>';document.getElementById(id).innerHTML=h+b}function setSort(k,c){let s=sortState[k];sortState[k]={c,d:s&&s.c===c&&s.d==='desc'?'asc':'desc'};renderCurrent()}function mini(el,rows,main,sub,extra){document.getElementById(el).innerHTML=rows.map(r=>`<div class='row'><span>${r[main]||''}${extra?` <span class='mut'>${r[extra]||''}</span>`:''}</span><b>${fmt(sub,r[sub])}</b></div>`).join('')||'<span class="mut">—</span>'}
const gameCols=['date_local','country','competition','round','home_abbr','home_score','away_score','away_abbr','source_quality'];const avgCols=['player','team_abbr','avg_minutes','avg_pir','games_played','rank_games','country','league','avg_pts','avg_reb','avg_ast','avg_fg_att','avg_fga_per_min','avg_pir_per_min','last_game_date'];const playerCols=['player','team_abbr','country','competition','opponent_abbr','home_away','minutes','rank','pts','fg_made','fg_att','fg_pct','two_made','two_att','three_made','three_att','ft_made','ft_att','reb','dreb','oreb','ast','stl','blk','blka','tov','fouls_drawn','fouls_committed','fga_per_min','rank_per_min','source_quality'];const teamCols=['team_abbr','country','competition','opponent_abbr','home_away','team_score','opponent_score','rank','pts','fg_made','fg_att','fg_pct','reb','dreb','oreb','ast','stl','blk','tov','source_quality'];const coverageCols=['team','status','note'];
function renderGames(){let c=gameCountry.value,l=gameLeague.value;table('gamesTable',DATA.games.filter(r=>(!c||r.country===c)&&(!l||r.league===l)),gameCols,'games')}function renderPlayers(){let q=pq.value,c=countryFilter.value,l=leagueFilter.value,t=teamFilter.value;let rows=DATA.players.filter(r=>ftext(r,q)&&(!c||r.country===c)&&(!l||r.league===l)&&(!t||r.team_abbr===t)&&(!onlyEl.checked||elTeams.has(r.team_abbr)));table('playersTable',rows,playerCols,'players')}function renderAverages(){let q=avgQ.value,c=avgCountry.value,l=avgLeague.value,t=avgTeam.value;let rows=DATA.averages.filter(r=>ftext(r,q)&&(!c||r.country===c)&&(!l||r.league===l)&&(!t||r.team_abbr===t)&&(!avgOnlyEl.checked||elTeams.has(r.team_abbr)));table('averagesTable',rows,avgCols,'averages')}function renderTeams(){table('teamsTable',DATA.totals,teamCols,'teams')}function renderCoverage(){table('coverageTable',DATA.coverage,coverageCols,'coverage')}function renderCurrent(){let id=document.querySelector('.panel.active').id;if(id==='results')renderGames();if(id==='players')renderPlayers();if(id==='averages')renderAverages();if(id==='teams')renderTeams();if(id==='coverage')renderCoverage()}function fillSelect(sel,vals){[...new Set(vals.filter(Boolean))].sort().forEach(x=>sel.innerHTML+=`<option>${x}</option>`)}function init(){gen.textContent=DATA.generated;fillSelect(countryFilter,DATA.players.map(r=>r.country));fillSelect(leagueFilter,DATA.players.map(r=>r.league));fillSelect(teamFilter,DATA.players.map(r=>r.team_abbr));fillSelect(avgCountry,DATA.averages.map(r=>r.country));fillSelect(avgLeague,DATA.averages.map(r=>r.league));fillSelect(avgTeam,DATA.averages.map(r=>r.team_abbr));fillSelect(gameCountry,DATA.games.map(r=>r.country));fillSelect(gameLeague,DATA.games.map(r=>r.league));document.querySelectorAll('.tab').forEach(b=>b.onclick=()=>{document.querySelectorAll('.tab,.panel').forEach(x=>x.classList.remove('active'));b.classList.add('active');document.getElementById(b.dataset.tab).classList.add('active');renderCurrent()});statGames.textContent=DATA.games.length;statPlayers.textContent=DATA.players.length;statCountries.textContent=[...new Set(DATA.games.map(r=>r.country))].length;statPartial.textContent=DATA.games.filter(r=>String(r.source_quality).includes('summary')||String(r.source_quality).includes('average_only')).length;mini('latestBox',[...DATA.games].sort((a,b)=>String(b.date_local).localeCompare(String(a.date_local))).slice(0,8),'team','team_score','competition');document.getElementById('latestBox').innerHTML=[...DATA.games].sort((a,b)=>String(b.date_local).localeCompare(String(a.date_local))).slice(0,8).map(r=>`<div class='row'><span>${r.home_abbr} ${r.home_score}-${r.away_score} ${r.away_abbr} <span class='mut'>${r.competition}</span></span><b>${r.date_local}</b></div>`).join('');mini('rankBox',DATA.topAvgMin,'player','avg_minutes','team_abbr');mini('pointsBox',DATA.topAvgPir,'player','avg_pir','team_abbr');sortState.players={c:'rank',d:'desc'};sortState.averages={c:'avg_minutes',d:'desc'};sortState.games={c:'date_local',d:'desc'};renderGames();renderPlayers();renderAverages();renderTeams();renderCoverage()}init();</script></body></html>'''
    html = template.replace('__LANG__', lang).replace('__TITLE__', htmlmod.escape(title)).replace('__ROUTE__', route).replace('__CSS__', css).replace('__LANG_LINKS__', lang_links).replace('__NAV_PREFIX__', nav_prefix).replace('__NAV1__', nav_text[0]).replace('__NAV2__', nav_text[1]).replace('__NAV3__', nav_text[2]).replace('__NAV4__', nav_text[3]).replace('__SUBTITLE__', htmlmod.escape(subtitle)).replace('__DATA__', js)
    for key, value in labels.items():
        html = html.replace('__L_' + key.upper() + '__', str(value))
    (SITE / filename).write_text(html, encoding='utf-8')


def patch_sitemap():
    sm=SITE/'sitemap.xml'
    if sm.exists():
        t=sm.read_text(encoding='utf-8')
        add=''
        for url in ['https://www.fantasyedgeiq.com/euroleague/domestic-competitions','https://www.fantasyedgeiq.com/sr/euroleague/domestic-competitions','https://www.fantasyedgeiq.com/el/euroleague/domestic-competitions']:
            if url not in t:
                add += f'  <url><loc>{url}</loc><lastmod>2026-09-27</lastmod><changefreq>daily</changefreq><priority>0.7</priority></url>\n'
        if add:
            sm.write_text(t.replace('</urlset>', add+'</urlset>'), encoding='utf-8')


def main():
    games, players, totals, averages = build_data()
    make_page.games, make_page.players, make_page.totals, make_page.averages = games, players, totals, averages
    common = {'date_local':'Date','country':'Country','league':'League','competition':'Competition','phase':'Phase','round':'Round','home_abbr':'Home','away_abbr':'Away','home_score':'Home PTS','away_score':'Away PTS','player':'Player','team_abbr':'Team','opponent_abbr':'Opp','home_away':'H/A','minutes':'MIN','rank':'PIR/RANK','pts':'PTS','fg_made':'FGM','fg_att':'FGA','fg_pct':'FG%','two_made':'2PM','two_att':'2PA','three_made':'3PM','three_att':'3PA','ft_made':'FTM','ft_att':'FTA','reb':'REB','dreb':'DREB','oreb':'OREB','ast':'AST','stl':'STL','blk':'BLK','blka':'BLKA','tov':'TOV','fouls_drawn':'FD','fouls_committed':'PF','fga_per_min':'FGA/min','rank_per_min':'PIR/min','team_score':'Team PTS','opponent_score':'Opp PTS','source_quality':'Source','team':'Team','status':'Status','note':'Note','games_played':'Games','rank_games':'PIR games','avg_minutes':'Avg MIN','avg_pir':'Avg PIR','avg_pts':'Avg PTS','avg_reb':'Avg REB','avg_ast':'Avg AST','avg_fg_att':'Avg FGA','avg_fga_per_min':'Avg FGA/min','avg_pir_per_min':'Avg PIR/min','last_game_date':'Last game'}
    labels_en = {**common, **{'overview':'Overview','results':'Results','players':'Player Stats','averages':'Averages','teams':'Team Totals','coverage':'Coverage','method':'Method','latest':'Latest played results','top_rank':'Top PIR/RANK — EL clubs','top_points':'Top points — EL clubs','top_minutes':'Top minutes — EL clubs','top_avg_min':'Top avg MIN/G — domestic','top_avg_pir':'Top avg Index/PIR — domestic','averages_note':'Grouped by player/team across all imported domestic games. Example: Žalgiris players now show averages across their 3 LKL games. Turkey has average minutes/shots and an estimated Avg PIR calculated from available Rezultati.com stats; the official foul-drawn component is unavailable.','note':'Played domestic games only. Domestic stats stay separate from EuroLeague data and are not mixed into Proj PIR. Greek rows include Super Cup plus GBL regular season; Israeli rows are Winner Cup; ABA, ACB, LKL, LBA, BSL and BBL rows are domestic/regional league games. France rows use official LNB final results plus season-average minutes and Eval/index in the Averages table; game-level player boxscores remain average-only. All listed current games are final; domestic data remains separate from EuroLeague projections.','method_text':'Sources: official ESAKE/GBL, ACB Live, LKL API, LBA game pages, ABA League game pages, LNB/Betclic Elite pages and Israel Basketball game-zone pages where available. Turkey uses Rezultati.com/Flashscore fallback because the official TBF/BSL public box score was unavailable; minutes and shots are captured, while PIR/RANK is an estimate from available box-score stats with the foul component omitted because fouls drawn are unavailable.','search':'Search player/team...','all_teams':'All teams','all_countries':'All countries','all_leagues':'All leagues','only_el':'EuroLeague clubs only','games_extracted':'Games extracted','club_rows':'Player rows','countries':'Countries','points_only':'No game boxscore rows','coverage_note':'This table shows why some EuroLeague clubs are not yet imported: only completed games are included.'}}
    labels_sr = {**common, **{'overview':'Pregled','results':'Rezultati','players':'Statistika igrača','averages':'Prosjeci','teams':'Timski totals','coverage':'Pokrivenost','method':'Metod','latest':'Završeni rezultati','top_rank':'Najviši PIR/RANK — EL klubovi','top_points':'Najviše poena — EL klubovi','top_minutes':'Najviše minuta — EL klubovi','top_avg_min':'Najviše MIN/G — domaće','top_avg_pir':'Najviši prosječan indeks/PIR — domaće','averages_note':'Prosjeci su grupisani po igraču i timu kroz sve ubačene domaće utakmice. Na primjer, igrači Žalgirisa sada imaju prosjek kroz 3 LKL utakmice. Za Tursku postoje prosječne minute/šutevi i procijenjen prosječan PIR iz dostupnih Rezultati.com statistika; zvanični foul-drawn dio nije dostupan.','note':'Ubačene su samo utakmice koje su završene. Domaća statistika ostaje odvojena od EuroLeague brojeva i ne miješa se u Proj PIR. Grci imaju Super Cup i GBL regularnu sezonu; Izraelci su Winner Cup; ABA, ACB, LKL, LBA, BSL i BBL su domaće/regionalne lige. Francuska sada ima LNB final rezultate i prosječne minute + indeks/Eval u tabu Prosjeci; game-level player boxscore ostaje average-only. Live/neodigrano se ne uvozi dok ne bude final.','method_text':'Izvori: zvanični ESAKE/GBL, ACB Live, LKL API, LBA game page, ABA League game page, LNB/Betclic Elite stranice i Israel Basketball game-zone gdje je dostupno. Za Tursku je korišten Rezultati.com/Flashscore jer zvanični TBF/BSL boxscore nije bio javno izložen; minute i šutevi su ubačeni, a PIR/RANK je procjena iz dostupnih box-score statistika bez faul-komponente jer fauli nad igračem nisu dostupni.','search':'Pretraži igrača/tim...','all_teams':'Svi timovi','all_countries':'Sve države','all_leagues':'Sve lige','only_el':'samo EuroLeague klubovi','games_extracted':'Utakmica','club_rows':'Redova igrača','countries':'Država','points_only':'Bez game boxscore rowova','coverage_note':'Ovdje se vidi zašto neki EuroLeague klubovi nisu još ubačeni: uvoze se samo završene utakmice.'}}
    labels_el = {**common, **{'overview':'Επισκόπηση','results':'Αποτελέσματα','players':'Στατιστικά παικτών','averages':'Μέσοι όροι','teams':'Team totals','coverage':'Κάλυψη','method':'Μέθοδος','latest':'Τελευταία τελικά αποτελέσματα','top_rank':'Κορυφαίο PIR/RANK — EL clubs','top_points':'Πόντοι — EL clubs','top_minutes':'Λεπτά — EL clubs','top_avg_min':'Top avg MIN/G — domestic','top_avg_pir':'Top average Index/PIR — domestic','averages_note':'Μέσοι όροι ανά παίκτη/ομάδα για όλα τα imported domestic games. Οι Žalgiris players έχουν averages σε 3 LKL games. Για Turkey, Avg PIR είναι estimated από τα διαθέσιμα Rezultati.com stats· το official foul-drawn component δεν είναι διαθέσιμο.','note':'Μόνο αγώνες που έχουν τελειώσει. Τα domestic stats μένουν ξεχωριστά από EuroLeague data και δεν μπαίνουν στο Proj PIR. Οι ελληνικές ομάδες έχουν Super Cup και GBL regular season, οι ισραηλινές Winner Cup, ενώ ABA/ACB/LKL/LBA/BSL/BBL είναι domestic/regional league games. France rows έχουν LNB τελικά αποτελέσματα και season-average minutes + Eval/index στο Averages table· game-level player boxscore μένει average-only.','method_text':'Πηγές: official ESAKE/GBL, ACB Live, LKL API, LBA game pages, ABA League game pages, LNB/Betclic Elite pages και Israel Basketball game-zone όπου υπάρχει. Για την Τουρκία χρησιμοποιείται Rezultati.com/Flashscore fallback επειδή το official TBF/BSL public box score δεν ήταν διαθέσιμο· minutes/shots έχουν περαστεί και PIR/RANK είναι estimate από διαθέσιμα box-score stats χωρίς foul component επειδή fouls drawn δεν υπάρχουν.','search':'Αναζήτηση παίκτη/ομάδας...','all_teams':'Όλες οι ομάδες','all_countries':'Όλες οι χώρες','all_leagues':'Όλες οι λίγκες','only_el':'μόνο EuroLeague clubs','games_extracted':'Αγώνες','club_rows':'Player rows','countries':'Χώρες','points_only':'No game boxscore rows','coverage_note':'Ο πίνακας δείχνει γιατί κάποια EuroLeague clubs δεν έχουν εισαχθεί ακόμη: μόνο completed games.'}}
    make_page('en','euroleague-domestic-competitions.html','/euroleague/domestic-competitions','EuroLeague Domestic Competitions','Played domestic league / Greek Super Cup stats for EuroLeague clubs, generated:', labels_en)
    make_page('sr','sr-euroleague-domestic-competitions.html','/sr/euroleague/domestic-competitions','Domaća takmičenja EuroLeague klubova','Završene utakmice iz domaćih liga / grčkog Super Cupa, odvojeno od EuroLeague brojeva. Generisano:', labels_sr)
    make_page('el','el-euroleague-domestic-competitions.html','/el/euroleague/domestic-competitions','Εγχώριες διοργανώσεις EuroLeague clubs','Completed domestic league / Greek Super Cup stats, ξεχωριστά από EuroLeague data. Δημιουργήθηκε:', labels_el)
    patch_sitemap()
    print('Wrote played domestic update')
    print('Games:', games.shape, 'Players:', players.shape, 'Totals:', totals.shape, 'Averages:', averages.shape)
    print(games[['country','competition','game_id','home_abbr','home_score','away_score','away_abbr']].to_string(index=False))
    print('Top rank:')
    print(players.sort_values('rank', ascending=False)[['player','team_abbr','competition','minutes','pts','reb','ast','rank','source_quality']].head(15).to_string(index=False))

if __name__ == '__main__':
    main()
