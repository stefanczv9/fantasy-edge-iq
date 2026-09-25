import json
import math
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
from rapidfuzz import process, fuzz

LOCAL_TZ = ZoneInfo("Europe/Zagreb")
ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / 'euroleague_fantasy_data'
OUT_XLSX = ROOT / 'euroleague_fantasy_pregled_fantasheet.xlsx'
OUT_HTML = ROOT / 'euroleague_fantasheet_style_dashboard.html'


def norm_name(s):
    s = str(s or '')
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii')
    s = s.lower()
    s = re.sub(r'\b(jr|jr\.|iii|ii|iv|sr|sr\.)\b', '', s)
    s = re.sub(r'[^a-z0-9]+', ' ', s).strip()
    return s


def official_name_to_full(n):
    n = str(n or '')
    if ',' in n:
        last, first = n.split(',', 1)
        return f'{first.strip()} {last.strip()}'.title()
    return n.title()


def safe_div(a, b):
    try:
        if b in (0, None) or pd.isna(b):
            return None
        return a / b
    except Exception:
        return None


def fmt_made_attempt(made, att):
    if made is None or att is None or pd.isna(made) or pd.isna(att):
        return None
    return f'{made:.1f}/{att:.1f}'


def load_players():
    profiles = json.load(open(ROOT / 'fantasy_profiles_active.json', encoding='utf-8'))
    rows = []
    for p in profiles:
        base = p.get('quotation')
        change = p.get('total_plus')
        current_price = None
        if base is not None:
            current_price = base + (change or 0)
        rows.append({
            'player_id': p.get('id'),
            'name': f"{p.get('first_name') or ''} {p.get('last_name') or ''}".strip(),
            'first_name': p.get('first_name'),
            'last_name': p.get('last_name'),
            'position': (p.get('position') or {}).get('name'),
            'pos_short': {'Guard':'G','Forward':'F','Center':'C','Head Coach':'HC'}.get((p.get('position') or {}).get('name'), ''),
            'team': (p.get('team') or {}).get('name'),
            'team_abbr': (p.get('team') or {}).get('abbreviation'),
            'team_id': (p.get('team') or {}).get('id'),
            'jersey': p.get('jersey'),
            'price_base': None if base is None else round(base, 1),
            'price_change': None if change is None else round(change, 1),
            'price': None if current_price is None else round(current_price, 1),
            'popularity_pct': None if p.get('popularity') is None else round(p.get('popularity') * 100, 2),
            'is_injured': p.get('is_injured'),
            'started_from_bench': p.get('started_from_bench'),
            'is_on_fire': p.get('is_on_fire'),
            'norm': norm_name(f"{p.get('first_name') or ''} {p.get('last_name') or ''}".strip()),
        })
    return pd.DataFrame(rows)


def fetch_official_traditional(season, current=False):
    from euroleague_api.player_stats import PlayerStats
    ps = PlayerStats('E')
    if current:
        df = ps.get_player_stats_single_season('traditional', season, phase_type_code='RS', statistic_mode='Accumulated')
    else:
        df = ps.get_player_stats_single_season('traditional', season, phase_type_code='RS', statistic_mode='Accumulated')
    if df.empty:
        cache = DATA_DIR / ('official_current_raw.csv' if current else 'official_2025_26_raw.csv')
        if cache.exists():
            df = pd.read_csv(cache)
        else:
            return df
    df = df.copy()
    df['official_name_full'] = df['player.name'].map(official_name_to_full)
    df['official_norm'] = df['official_name_full'].map(norm_name)
    df['team_abbr_official'] = df.get('player.team.tvCodes')
    gp = df['gamesPlayed'].replace({0: pd.NA})
    per_cols = {
        'minutesPlayed': 'min_avg', 'pointsScored': 'pts_avg', 'totalRebounds': 'reb_avg',
        'offensiveRebounds': 'oreb_avg', 'defensiveRebounds': 'dreb_avg', 'assists': 'ast_avg',
        'steals': 'stl_avg', 'turnovers': 'tov_avg', 'blocks': 'blk_avg', 'blocksAgainst': 'blka_avg',
        'foulsCommited': 'pf_avg', 'foulsDrawn': 'fd_avg', 'pir': 'pir_avg',
        'twoPointersMade':'2pm_avg', 'twoPointersAttempted':'2pa_avg',
        'threePointersMade':'3pm_avg', 'threePointersAttempted':'3pa_avg',
        'freeThrowsMade':'ftm_avg', 'freeThrowsAttempted':'fta_avg',
    }
    for c, new in per_cols.items():
        if c in df.columns:
            df[new] = (df[c] / gp).astype(float).round(2)

    # Shooting volume / efficiency. These are important for fantasy because they
    # show role and usage, not only final PIR: total FGM/FGA, percentages and
    # attempts per minute / per 40 minutes.
    required = ['twoPointersMade', 'threePointersMade', 'twoPointersAttempted', 'threePointersAttempted']
    if all(c in df.columns for c in required):
        df['fg_made_total'] = df['twoPointersMade'].fillna(0) + df['threePointersMade'].fillna(0)
        df['fg_attempts_total'] = df['twoPointersAttempted'].fillna(0) + df['threePointersAttempted'].fillna(0)
        fga = df['fg_attempts_total'].replace({0: pd.NA})
        minutes = df['minutesPlayed'].replace({0: pd.NA}) if 'minutesPlayed' in df.columns else pd.Series(pd.NA, index=df.index)
        df['fg_pct'] = pd.to_numeric(df['fg_made_total'] / fga * 100, errors='coerce').round(1)
        df['fg_made_pg'] = pd.to_numeric(df['fg_made_total'] / gp, errors='coerce').round(2)
        df['fg_attempts_pg'] = pd.to_numeric(df['fg_attempts_total'] / gp, errors='coerce').round(2)
        df['fg_made_per_min'] = pd.to_numeric(df['fg_made_total'] / minutes, errors='coerce').round(3)
        df['fg_attempts_per_min'] = pd.to_numeric(df['fg_attempts_total'] / minutes, errors='coerce').round(3)
        df['fg_attempts_per40'] = pd.to_numeric(df['fg_attempts_total'] / minutes * 40, errors='coerce').round(2)
        df['two_pa_per_min'] = pd.to_numeric(df['twoPointersAttempted'] / minutes, errors='coerce').round(3)
        df['three_pa_per_min'] = pd.to_numeric(df['threePointersAttempted'] / minutes, errors='coerce').round(3)
        if 'freeThrowsAttempted' in df.columns:
            df['fta_per_min'] = pd.to_numeric(df['freeThrowsAttempted'] / minutes, errors='coerce').round(3)
    return df


def match_current_official(players, current_df):
    # Official current stats -> fantasy player by same team + fuzzy name.
    matched = []
    if current_df.empty:
        return pd.DataFrame()
    by_team = {t: g.reset_index(drop=True) for t, g in players.groupby('team_abbr')}
    for _, row in current_df.iterrows():
        team = row.get('team_abbr_official')
        cand = by_team.get(team)
        player_id = None; fantasy_name = None; score = None
        if cand is not None and not cand.empty:
            choices = cand['norm'].tolist()
            res = process.extractOne(row['official_norm'], choices, scorer=fuzz.token_sort_ratio)
            if res and res[1] >= 80:
                _, score, idx = res
                player_id = cand.iloc[idx]['player_id']
                fantasy_name = cand.iloc[idx]['name']
        rec = {'player_id': player_id, 'fantasy_name_current_match': fantasy_name, 'current_match_quality': score}
        rec.update(row.to_dict())
        matched.append(rec)
    return pd.DataFrame(matched)


def match_previous_to_players(players, prev_df):
    # Previous season stats -> each fantasy player by name only (transfers allowed).
    if prev_df.empty:
        return pd.DataFrame({'player_id': players['player_id']})
    # If duplicate names, keep row with most games/minutes.
    prev = prev_df.sort_values(['gamesPlayed', 'minutesPlayed'], ascending=[False, False]).drop_duplicates('official_norm')
    choices = prev['official_norm'].tolist()
    recs = []
    for _, p in players.iterrows():
        out = {'player_id': p.player_id, 'prev_match_quality': None}
        if p.position == 'Head Coach':
            recs.append(out); continue
        res = process.extractOne(p['norm'], choices, scorer=fuzz.token_sort_ratio)
        if res and res[1] >= 86:
            _, score, idx = res
            r = prev.iloc[idx]
            out.update({
                'prev_match_quality': score,
                'prev_official_name': r.get('official_name_full'),
                'prev_team_abbr': r.get('team_abbr_official'),
                'gp_25_26': r.get('gamesPlayed'),
                'min_avg_25_26': r.get('min_avg'),
                'pir_25_26': r.get('pir_avg'),
                'pts_25_26': r.get('pts_avg'),
                'reb_25_26': r.get('reb_avg'),
                'ast_25_26': r.get('ast_avg'),
                'fg_made_pg_25_26': r.get('fg_made_pg'),
                'fg_attempts_pg_25_26': r.get('fg_attempts_pg'),
                'fg_pct_25_26': r.get('fg_pct'),
                'fg_made_per_min_25_26': r.get('fg_made_per_min'),
                'fg_attempts_per_min_25_26': r.get('fg_attempts_per_min'),
                'fg_attempts_per40_25_26': r.get('fg_attempts_per40'),
                'two_pa_per_min_25_26': r.get('two_pa_per_min'),
                'three_pa_per_min_25_26': r.get('three_pa_per_min'),
                'fta_per_min_25_26': r.get('fta_per_min'),
            })
        recs.append(out)
    return pd.DataFrame(recs)


def build():
    players = load_players()
    logs = pd.read_csv(DATA_DIR / 'fantasy_poeni_log.csv')
    matches = pd.read_csv(DATA_DIR / 'utakmice.csv')

    # Current fantasy line: one row per player for current MD.
    current_logs = logs.sort_values('matchday').groupby('player_id').tail(1)
    cur_cols = ['player_id', 'fantasy_pts', 'match_status', 'opponent_abbr', 'home_away', 'start_local', 'pts', 'reb', 'ast', 'stl', 'blk', 'tov', 'fd', 'pf', 'fg_missed', 'ft_missed']
    current_logs = current_logs[[c for c in cur_cols if c in current_logs.columns]].rename(columns={
        'fantasy_pts':'fantasy_pts_current_md',
        'pts':'fantasy_pts_stat_pts',
        'reb':'fantasy_pts_stat_reb',
        'ast':'fantasy_pts_stat_ast',
    })
    players = players.merge(current_logs, on='player_id', how='left')

    # Next match from existing CSV if present in old generated players file.
    old_players_path = DATA_DIR / 'igraci_fantasy.csv'
    if old_players_path.exists():
        oldp = pd.read_csv(old_players_path)
        next_cols = [c for c in ['player_id','next_matchday','next_start_local','next_home_away','next_opponent','next_match'] if c in oldp.columns]
        players = players.merge(oldp[next_cols], on='player_id', how='left')

    current_off = fetch_official_traditional(2026, current=True)
    previous_off = fetch_official_traditional(2025, current=False)
    current_matched = match_current_official(players, current_off)
    prev_matched = match_previous_to_players(players, previous_off)

    # Select current stat columns and suffix.
    cur_keep = ['player_id','current_match_quality','gamesPlayed','gamesStarted','minutesPlayed','pointsScored','totalRebounds','offensiveRebounds','defensiveRebounds','assists','steals','turnovers','blocks','blocksAgainst','foulsCommited','foulsDrawn','pir','min_avg','pts_avg','reb_avg','oreb_avg','dreb_avg','ast_avg','stl_avg','tov_avg','blk_avg','blka_avg','pf_avg','fd_avg','pir_avg','2pm_avg','2pa_avg','3pm_avg','3pa_avg','ftm_avg','fta_avg','fg_made_pg','fg_attempts_pg','fg_pct','fg_made_per_min','fg_attempts_per_min','fg_attempts_per40','two_pa_per_min','three_pa_per_min','fta_per_min','twoPointersPercentage','threePointersPercentage','freeThrowsPercentage','official_name_full']
    if 'player_id' not in current_matched.columns:
        cur_stats = pd.DataFrame({'player_id': []})
    else:
        cur_keep = [c for c in cur_keep if c in current_matched.columns]
        cur_stats = current_matched[cur_keep].copy()
    cur_stats = cur_stats.rename(columns={
        'gamesPlayed':'gp_current','gamesStarted':'gs_current','minutesPlayed':'min_total_current','pointsScored':'pts_total_current','totalRebounds':'reb_total_current','offensiveRebounds':'oreb_total_current','defensiveRebounds':'dreb_total_current','assists':'ast_total_current','steals':'stl_total_current','turnovers':'tov_total_current','blocks':'blk_total_current','blocksAgainst':'blka_total_current','foulsCommited':'pf_total_current','foulsDrawn':'fd_total_current','pir':'pir_total_current','min_avg':'min_avg_current','pts_avg':'pts_avg_current','reb_avg':'reb_avg_current','oreb_avg':'oreb_avg_current','dreb_avg':'dreb_avg_current','ast_avg':'ast_avg_current','stl_avg':'stl_avg_current','tov_avg':'tov_avg_current','blk_avg':'blk_avg_current','blka_avg':'blka_avg_current','pf_avg':'pf_avg_current','fd_avg':'fd_avg_current','pir_avg':'pir_avg_current','2pm_avg':'2pm_avg_current','2pa_avg':'2pa_avg_current','3pm_avg':'3pm_avg_current','3pa_avg':'3pa_avg_current','ftm_avg':'ftm_avg_current','fta_avg':'fta_avg_current','fg_made_pg':'fg_made_pg_current','fg_attempts_pg':'fg_attempts_pg_current','fg_pct':'fg_pct_current','fg_made_per_min':'fg_made_per_min_current','fg_attempts_per_min':'fg_attempts_per_min_current','fg_attempts_per40':'fg_attempts_per40_current','two_pa_per_min':'two_pa_per_min_current','three_pa_per_min':'three_pa_per_min_current','fta_per_min':'fta_per_min_current','twoPointersPercentage':'2p_pct_current','threePointersPercentage':'3p_pct_current','freeThrowsPercentage':'ft_pct_current','official_name_full':'official_current_name'
    })
    players = players.merge(cur_stats, on='player_id', how='left')
    players = players.merge(prev_matched, on='player_id', how='left')

    # Best available minutes average.
    players['min_avg_best'] = players['min_avg_current'].combine_first(players['min_avg_25_26'])
    players['min_avg_source'] = players.apply(lambda r: '2026-27 current' if pd.notna(r.get('min_avg_current')) else ('2025-26' if pd.notna(r.get('min_avg_25_26')) else ('N/A' if r.get('position') != 'Head Coach' else 'Coach')), axis=1)

    # Best available shooting sample: current season first, previous EL season if
    # the player has not played yet. This keeps the table useful for almost all players.
    shot_pairs = [
        ('fg_made_pg', 'FGM/G'), ('fg_attempts_pg', 'FGA/G'), ('fg_pct', 'FG%'),
        ('fg_made_per_min', 'FGM/min'), ('fg_attempts_per_min', 'FGA/min'),
        ('fg_attempts_per40', 'FGA/40'), ('two_pa_per_min', '2PA/min'),
        ('three_pa_per_min', '3PA/min'), ('fta_per_min', 'FTA/min')
    ]
    for base, _label in shot_pairs:
        cur = f'{base}_current'
        prev = f'{base}_25_26'
        best = f'{base}_best'
        if cur in players.columns or prev in players.columns:
            players[best] = players[cur] if cur in players.columns else pd.NA
            if prev in players.columns:
                players[best] = players[best].combine_first(players[prev])
    players['shooting_source'] = players.apply(lambda r: '2026-27 current' if pd.notna(r.get('fg_attempts_pg_current')) else ('2025-26' if pd.notna(r.get('fg_attempts_pg_25_26')) else ('N/A' if r.get('position') != 'Head Coach' else 'Coach')), axis=1)

    # Fantasheet-style derived metrics.
    players['value_pir_per_credit'] = (players['pir_avg_current'] / players['price']).round(2)
    players['value_fantasy_per_credit'] = (players['fantasy_pts_current_md'] / players['price']).round(2)
    players['proj_pir_est'] = players.apply(lambda r: round(0.65*r['pir_25_26'] + 0.35*r['pir_avg_current'], 1) if pd.notna(r.get('pir_25_26')) and pd.notna(r.get('pir_avg_current')) else (round(r['pir_25_26'],1) if pd.notna(r.get('pir_25_26')) else (round(r['pir_avg_current']*0.75,1) if pd.notna(r.get('pir_avg_current')) else None)), axis=1)
    players['form_pir'] = players['pir_avg_current']
    players['floor_est'] = players['proj_pir_est'].apply(lambda x: None if pd.isna(x) else round(max(-5, x*0.55), 1))
    players['ceiling_est'] = players['proj_pir_est'].apply(lambda x: None if pd.isna(x) else round(x*1.45 + 2, 1))
    # Fair price heuristic: 1.4 PIR per credit as a rough fantasy value baseline.
    players['fair_price_est'] = players['proj_pir_est'].apply(lambda x: None if pd.isna(x) else round(x / 1.4, 1))
    players['price_gap_est'] = (players['fair_price_est'] - players['price']).round(1)
    players['2p_current'] = players.apply(lambda r: fmt_made_attempt(r.get('2pm_avg_current'), r.get('2pa_avg_current')), axis=1)
    players['3p_current'] = players.apply(lambda r: fmt_made_attempt(r.get('3pm_avg_current'), r.get('3pa_avg_current')), axis=1)
    players['ft_current'] = players.apply(lambda r: fmt_made_attempt(r.get('ftm_avg_current'), r.get('fta_avg_current')), axis=1)

    # Main table columns, Serbian labels are applied in output.
    fanta_cols = [
        'name','team_abbr','pos_short','price','price_base','price_change','proj_pir_est','form_pir','value_pir_per_credit','fantasy_pts_current_md','value_fantasy_per_credit',
        'gp_current','min_avg_best','min_avg_source','min_avg_current','pts_avg_current','pir_avg_current','pir_25_26','min_avg_25_26','floor_est','ceiling_est','price_gap_est',
        'fg_made_pg_best','fg_attempts_pg_best','fg_pct_best','fg_attempts_per_min_best','fg_attempts_per40_best','shooting_source','fg_made_pg_current','fg_attempts_pg_current','fg_pct_current','fg_attempts_per_min_current','fg_attempts_per40_current',
        '2p_current','2p_pct_current','3p_current','3p_pct_current','ft_current','ft_pct_current','two_pa_per_min_best','three_pa_per_min_best','fta_per_min_best','reb_avg_current','oreb_avg_current','dreb_avg_current','pf_avg_current','fd_avg_current','stl_avg_current','tov_avg_current','ast_avg_current','blk_avg_current','blka_avg_current',
        'next_opponent','next_start_local','match_status','opponent_abbr','home_away','is_injured','started_from_bench','popularity_pct','player_id'
    ]
    fanta = players[[c for c in fanta_cols if c in players.columns]].copy()
    fanta = fanta.sort_values(['value_pir_per_credit','pir_avg_current','price'], ascending=[False,False,False], na_position='last')

    # Save data artifacts.
    DATA_DIR.mkdir(exist_ok=True)
    players.to_csv(DATA_DIR / 'igraci_fantasy_augmented.csv', index=False)
    fanta.to_csv(DATA_DIR / 'fantasheet_style_table.csv', index=False)
    current_off.to_csv(DATA_DIR / 'official_current_raw.csv', index=False)
    previous_off.to_csv(DATA_DIR / 'official_2025_26_raw.csv', index=False)

    write_excel(fanta, players, matches, logs, current_off, previous_off)
    write_html(fanta, matches, logs)
    return fanta, players


def write_excel(fanta, players, matches, logs, current_off, previous_off):
    labels = {
        'name':'Player','team_abbr':'Team','pos_short':'Pos','price':'Price current','price_base':'Base price','price_change':'Δ price','proj_pir_est':'Proj PIR*','form_pir':'Form PIR','value_pir_per_credit':'Value PIR/Cr','fantasy_pts_current_md':'Fantasy pts MD','value_fantasy_per_credit':'Fantasy/Cr','gp_current':'GP','min_avg_best':'MIN avg','min_avg_source':'MIN source','min_avg_current':'MIN 26-27','pts_avg_current':'PTS','pir_avg_current':'PIR','pir_25_26':'PIR 25-26','min_avg_25_26':'MIN 25-26','floor_est':'Floor*','ceiling_est':'Ceiling*','price_gap_est':'Price gap*','fg_made_pg_best':'FGM/G','fg_attempts_pg_best':'FGA/G','fg_pct_best':'FG%','fg_attempts_per_min_best':'FGA/min','fg_attempts_per40_best':'FGA/40','shooting_source':'Shot source','fg_made_pg_current':'FGM/G 26-27','fg_attempts_pg_current':'FGA/G 26-27','fg_pct_current':'FG% 26-27','fg_attempts_per_min_current':'FGA/min 26-27','fg_attempts_per40_current':'FGA/40 26-27','2p_current':'2P','2p_pct_current':'2P%','3p_current':'3P','3p_pct_current':'3P%','ft_current':'FT','ft_pct_current':'FT%','two_pa_per_min_best':'2PA/min','three_pa_per_min_best':'3PA/min','fta_per_min_best':'FTA/min','reb_avg_current':'REB','oreb_avg_current':'OREB','dreb_avg_current':'DREB','pf_avg_current':'PF','fd_avg_current':'FD','stl_avg_current':'STL','tov_avg_current':'TOV','ast_avg_current':'AST','blk_avg_current':'BLK','blka_avg_current':'BLKA','next_opponent':'Next opp','next_start_local':'Next time','match_status':'MD status','opponent_abbr':'MD opp','home_away':'H/A','is_injured':'Inj','started_from_bench':'Bench','popularity_pct':'Pick %','player_id':'ID'
    }
    out = fanta.rename(columns=labels)
    info = pd.DataFrame([
        ['Generated', datetime.now(LOCAL_TZ).strftime('%Y-%m-%d %H:%M %Z')],
        ['Important', 'Price current = EuroLeague Fantasy quotation + total_plus (after price move).'],
        ['MIN avg', 'Uses current EuroLeague season if the player has official stats; otherwise previous EuroLeague season 2025-26; N/A if no EuroLeague minute sample was available.'],
        ['Projection columns', 'Proj/Floor/Ceiling/Price gap are simple estimates for overview, not paid FantaSheet model outputs.'],
        ['Source', 'EuroLeague Fantasy Challenge API + public EuroLeague Basketball stats API.'],
    ], columns=['Field','Value'])
    with pd.ExcelWriter(OUT_XLSX, engine='xlsxwriter') as writer:
        info.to_excel(writer, sheet_name='INFO', index=False)
        out.to_excel(writer, sheet_name='FantaSheet-style', index=False)
        players.to_excel(writer, sheet_name='Players augmented', index=False)
        matches.to_excel(writer, sheet_name='Utakmice', index=False)
        logs.to_excel(writer, sheet_name='Fantasy log', index=False)
        current_off.to_excel(writer, sheet_name='Official current raw', index=False)
        previous_off.to_excel(writer, sheet_name='Official 25-26 raw', index=False)
        wb = writer.book
        header = wb.add_format({'bold': True, 'bg_color': '#16365c', 'font_color': 'white', 'border': 1})
        good = wb.add_format({'bg_color': '#C6EFCE', 'font_color': '#006100'})
        bad = wb.add_format({'bg_color': '#FFC7CE', 'font_color': '#9C0006'})
        for sheet, df in [('INFO', info), ('FantaSheet-style', out), ('Players augmented', players), ('Utakmice', matches), ('Fantasy log', logs), ('Official current raw', current_off), ('Official 25-26 raw', previous_off)]:
            ws = writer.sheets[sheet]
            ws.freeze_panes(1, 0)
            ws.autofilter(0, 0, max(len(df), 1), max(len(df.columns)-1, 0))
            for i, col in enumerate(df.columns):
                ws.write(0, i, col, header)
                sample = df[col].head(300).fillna('').astype(str).tolist() if col in df else []
                width = max(10, min(28, max([len(str(col))] + [len(x) for x in sample])))
                ws.set_column(i, i, width)
            if sheet == 'FantaSheet-style':
                if 'Value PIR/Cr' in df.columns:
                    c = df.columns.get_loc('Value PIR/Cr')
                    ws.conditional_format(1, c, len(df), c, {'type':'cell','criteria':'>=','value':1.5,'format':good})
                if 'Inj' in df.columns:
                    c = df.columns.get_loc('Inj')
                    ws.conditional_format(1, c, len(df), c, {'type':'text','criteria':'containing','value':'TRUE','format':bad})


def clean_records(df):
    out = []
    for rec in df.to_dict('records'):
        nr = {}
        for k, v in rec.items():
            if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))) or pd.isna(v):
                nr[k] = None
            elif hasattr(v, 'item'):
                nr[k] = v.item()
            else:
                nr[k] = v
        out.append(nr)
    return out


def write_html(fanta, matches, logs):
    cols = ['name','team_abbr','pos_short','price','proj_pir_est','form_pir','value_pir_per_credit','fantasy_pts_current_md','gp_current','min_avg_best','min_avg_source','pts_avg_current','pir_avg_current','pir_25_26','floor_est','ceiling_est','price_gap_est','fg_made_pg_best','fg_attempts_pg_best','fg_pct_best','fg_attempts_per_min_best','fg_attempts_per40_best','shooting_source','2p_current','2p_pct_current','3p_current','3p_pct_current','ft_current','ft_pct_current','two_pa_per_min_best','three_pa_per_min_best','fta_per_min_best','reb_avg_current','oreb_avg_current','dreb_avg_current','pf_avg_current','fd_avg_current','stl_avg_current','tov_avg_current','ast_avg_current','blk_avg_current','blka_avg_current','next_opponent','next_start_local','is_injured','popularity_pct']
    fanta_small = fanta[[c for c in cols if c in fanta.columns]].copy()
    match_cols = ['matchday','round','start_local','status','home_abbr','away_abbr','result','winner']
    top_value = fanta_small.dropna(subset=['value_pir_per_credit']).head(8)
    payload = {
        'players': clean_records(fanta_small),
        'matches': clean_records(matches[[c for c in match_cols if c in matches.columns]]),
        'top': clean_records(top_value),
        'meta': {'generated': datetime.now(LOCAL_TZ).strftime('%Y-%m-%d %H:%M %Z'), 'players': len(fanta_small), 'matches': len(matches)}
    }
    js = json.dumps(payload, ensure_ascii=False)
    html = f"""<!doctype html><html lang="sr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>EuroLeague FantaSheet-style pregled</title>
<style>
:root{{--bg:#070f1e;--card:#111e33;--line:rgba(255,255,255,.09);--txt:#edf4ff;--mut:#9eb0cc;--blue:#5bbcff;--green:#22c55e;--red:#fb7185;--yellow:#ffd166}}*{{box-sizing:border-box}}body{{margin:0;background:radial-gradient(circle at top left,#17365e,#070f1e 52%);color:var(--txt);font-family:Inter,system-ui,Segoe UI,Arial,sans-serif}}header{{padding:26px 30px;border-bottom:1px solid var(--line);position:sticky;top:0;background:rgba(7,15,30,.94);backdrop-filter:blur(8px);z-index:5}}h1{{margin:0 0 8px;font-size:28px}}.mut{{color:var(--mut)}}main{{padding:24px 30px 60px}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-top:18px}}.card{{background:rgba(17,30,51,.86);border:1px solid var(--line);border-radius:16px;padding:14px}}.card b{{font-size:24px;display:block}}.tabs{{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 16px}}button{{background:#132640;color:var(--txt);border:1px solid var(--line);border-radius:10px;padding:9px 13px;cursor:pointer}}button.active,button:hover{{border-color:var(--blue)}}.panel{{display:none}}.panel.active{{display:block}}.note{{background:rgba(255,255,255,.055);border:1px solid var(--line);border-radius:14px;padding:13px;margin:0 0 14px;line-height:1.45}}.toolbar{{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:0 0 12px}}input,select{{background:#0c1728;color:var(--txt);border:1px solid var(--line);border-radius:10px;padding:9px 10px}}.tablewrap{{max-height:73vh;overflow:auto;border:1px solid var(--line);border-radius:14px;background:rgba(17,30,51,.72)}}table{{width:100%;border-collapse:collapse;font-size:13px}}th,td{{padding:8px 10px;border-bottom:1px solid var(--line);white-space:nowrap;text-align:left}}th{{position:sticky;top:0;background:#18304f;z-index:2;cursor:pointer}}tr:hover td{{background:rgba(91,188,255,.07)}}.pos{{display:inline-block;border-radius:999px;padding:2px 8px;font-weight:700;background:#203b62}}.price{{color:var(--yellow);font-weight:800}}.good{{color:var(--green);font-weight:800}}.bad{{color:var(--red);font-weight:800}}.topgrid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px;margin-bottom:16px}}.mini{{padding:12px;border-radius:14px;background:var(--card);border:1px solid var(--line)}}.mini .rank{{color:var(--blue);font-weight:800}}</style></head>
<body><header><h1>EuroLeague Fantasy — FantaSheet-style pregled</h1><div class="mut">Cijene poslije promjene, PIR value, prosjek minuta i kompletna tabela za izbor tima. Generisano: <b id="gen"></b></div><div class="cards"><div class="card"><b id="pcount"></b><span class="mut">igrača + trenera</span></div><div class="card"><b id="mcount"></b><span class="mut">utakmica</span></div><div class="card"><b>MIN avg</b><span class="mut">current ili 25-26 sezona</span></div></div></header>
<main><div class="tabs"><button class="tab active" data-tab="main">Tabela igrača</button><button class="tab" data-tab="best">Best value</button><button class="tab" data-tab="matches">Utakmice</button><button class="tab" data-tab="info">Info</button></div>
<section id="main" class="panel active"><div class="note"><b>Kao FantaSheet tabela:</b> Price = osnovna cijena + promjena cijene; Value = official PIR / kredit. <b>MIN avg</b> je prosjek minuta za igrača: prvo trenutna sezona ako je odigrao, inače EuroLeague 2025-26 ako postoji uzorak. Proj/Floor/Ceiling su jednostavne procjene, nisu plaćeni FantaSheet model.</div><div class="toolbar"><input id="q" placeholder="Pretraga igrača..." oninput="renderPlayers()"><select id="team" onchange="renderPlayers()"><option value="">Svi timovi</option></select><select id="pos" onchange="renderPlayers()"><option value="">Sve pozicije</option></select><label class="mut"><input type="checkbox" id="hideNoMin" onchange="renderPlayers()"> sakrij bez minuta</label><label class="mut"><input type="checkbox" id="hideInj" onchange="renderPlayers()"> sakrij povrijeđene</label></div><div id="ptable" class="tablewrap"></div></section>
<section id="best" class="panel"><div class="topgrid" id="topcards"></div><div id="besttable" class="tablewrap"></div></section>
<section id="matches" class="panel"><div class="toolbar"><input id="mq" placeholder="Pretraga utakmica..." oninput="renderMatches()"></div><div id="mtable" class="tablewrap"></div></section>
<section id="info" class="panel"><div class="note">Podaci su iz EuroLeague Fantasy Challenge API-ja i javnog EuroLeague Basketball stats API-ja. Ako igrač nema EuroLeague minute ni ove ni prošle sezone, MIN avg ostaje N/A. Za potpunu FantaSheet funkcionalnost tipa injury news sa izvorima, napredne projekcije i preseason izvore, potreban je njihov Pro nalog; ovdje je napravljena javno dostupna verzija za pregled i selekciju tima.</div></section></main>
<script>const DATA={js}; let sort={{players:{{col:'value_pir_per_credit',dir:-1}},best:{{col:'value_pir_per_credit',dir:-1}},matches:{{col:'start_local',dir:1}}}};
const labels={{name:'Player',team_abbr:'Team',pos_short:'Pos',price:'Price',proj_pir_est:'Proj*',form_pir:'Form',value_pir_per_credit:'Value',fantasy_pts_current_md:'Fantasy MD',gp_current:'GP',min_avg_best:'MIN avg',min_avg_source:'MIN src',pts_avg_current:'PTS',pir_avg_current:'PIR',pir_25_26:'PIR 25-26',floor_est:'Floor*',ceiling_est:'Ceiling*',price_gap_est:'Price gap*',fg_made_pg_best:'FGM/G',fg_attempts_pg_best:'FGA/G',fg_pct_best:'FG%',fg_attempts_per_min_best:'FGA/min',fg_attempts_per40_best:'FGA/40',shooting_source:'Shot src','2p_current':'2P','2p_pct_current':'2P%','3p_current':'3P','3p_pct_current':'3P%','ft_current':'FT','ft_pct_current':'FT%',two_pa_per_min_best:'2PA/min',three_pa_per_min_best:'3PA/min',fta_per_min_best:'FTA/min',reb_avg_current:'REB',oreb_avg_current:'OREB',dreb_avg_current:'DREB',pf_avg_current:'PF',fd_avg_current:'FD',stl_avg_current:'STL',tov_avg_current:'TOV',ast_avg_current:'AST',blk_avg_current:'BLK',blka_avg_current:'BLKA',next_opponent:'Next',next_start_local:'Next time',is_injured:'Inj',popularity_pct:'Pick%',matchday:'MD',round:'R',start_local:'Time',status:'Status',home_abbr:'Home',away_abbr:'Away',result:'Result',winner:'Winner'}};
function v(x){{return x===null||x===undefined?'':x}} function n(x){{let y=parseFloat(x);return isNaN(y)?null:y}} function fmt(k,x){{if(x===null||x===undefined||x==='')return '<span class="mut">–</span>'; if(k==='pos_short')return `<span class="pos">${{x}}</span>`; if(k==='price')return `<span class="price">${{Number(x).toFixed(1)}}</span>`; if(['value_pir_per_credit','pir_avg_current','fantasy_pts_current_md','proj_pir_est','form_pir'].includes(k)){{let y=Number(x);return `<span class="${{y>=15||k==='value_pir_per_credit'&&y>=1.5?'good':(y<0?'bad':'')}}">${{Number.isInteger(y)?y:y.toFixed(2)}}</span>`}} if(k==='is_injured')return x?'<span class="bad">DA</span>':'NE'; if(typeof x==='number')return Number.isInteger(x)?x:x.toFixed(2); return String(x)}}
function table(el, rows, cols, key){{let st=sort[key]; let rs=rows.slice(); if(st&&st.col)rs.sort((a,b)=>{{let av=a[st.col],bv=b[st.col],an=n(av),bn=n(bv); if(an!==null&&bn!==null)return (an-bn)*st.dir; return String(v(av)).localeCompare(String(v(bv)))*st.dir}}); let h='<table><thead><tr>'+cols.map(c=>`<th data-col="${{c}}">${{labels[c]||c}}</th>`).join('')+'</tr></thead><tbody>'+rs.map(r=>'<tr>'+cols.map(c=>`<td>${{fmt(c,r[c])}}</td>`).join('')+'</tr>').join('')+'</tbody></table>'; document.getElementById(el).innerHTML=h; document.querySelectorAll(`#${{el}} th`).forEach(th=>th.onclick=()=>{{let c=th.dataset.col; sort[key].dir=sort[key].col===c?-sort[key].dir:1; sort[key].col=c; renderCurrent()}})}}
function ftext(r,q){{return !q||Object.values(r).join(' ').toLowerCase().includes(q.toLowerCase())}} const pcols=['name','team_abbr','pos_short','price','proj_pir_est','form_pir','value_pir_per_credit','fantasy_pts_current_md','gp_current','min_avg_best','min_avg_source','pts_avg_current','pir_avg_current','pir_25_26','floor_est','ceiling_est','price_gap_est','fg_made_pg_best','fg_attempts_pg_best','fg_pct_best','fg_attempts_per_min_best','fg_attempts_per40_best','shooting_source','2p_current','2p_pct_current','3p_current','3p_pct_current','ft_current','ft_pct_current','two_pa_per_min_best','three_pa_per_min_best','fta_per_min_best','reb_avg_current','oreb_avg_current','dreb_avg_current','pf_avg_current','fd_avg_current','stl_avg_current','tov_avg_current','ast_avg_current','blk_avg_current','blka_avg_current','next_opponent','next_start_local','is_injured','popularity_pct'];
function renderPlayers(){{let qq=q.value,t=team.value,p=pos.value;let rows=DATA.players.filter(r=>ftext(r,qq)&&(!t||r.team_abbr===t)&&(!p||r.pos_short===p)&&(!hideNoMin.checked||r.min_avg_best!==null)&&(!hideInj.checked||!r.is_injured));table('ptable',rows,pcols,'players')}}
function renderBest(){{table('besttable',DATA.players.filter(r=>r.value_pir_per_credit!==null),pcols.slice(0,23),'best')}} function renderMatches(){{table('mtable',DATA.matches.filter(r=>ftext(r,mq.value)),['matchday','round','start_local','status','home_abbr','away_abbr','result','winner'],'matches')}} function renderCurrent(){{let id=document.querySelector('.panel.active').id; if(id==='main')renderPlayers(); if(id==='best')renderBest(); if(id==='matches')renderMatches();}}
function init(){{gen.textContent=DATA.meta.generated;pcount.textContent=DATA.meta.players;mcount.textContent=DATA.meta.matches;[...new Set(DATA.players.map(r=>r.team_abbr).filter(Boolean))].sort().forEach(x=>team.innerHTML+=`<option>${{x}}</option>`);[...new Set(DATA.players.map(r=>r.pos_short).filter(Boolean))].sort().forEach(x=>pos.innerHTML+=`<option>${{x}}</option>`);topcards.innerHTML=DATA.top.map((r,i)=>`<div class="mini"><span class="rank">#${{i+1}}</span><b>${{r.name}}</b><div class="mut">${{r.team_abbr}} · ${{r.pos_short}} · Price ${{fmt('price',r.price)}} </div><div>Value <b class="good">${{r.value_pir_per_credit}}</b> · PIR ${{r.pir_avg_current}} · MIN ${{r.min_avg_best??'N/A'}}</div></div>`).join('');document.querySelectorAll('.tab').forEach(b=>b.onclick=()=>{{document.querySelectorAll('.tab,.panel').forEach(x=>x.classList.remove('active'));b.classList.add('active');document.getElementById(b.dataset.tab).classList.add('active');renderCurrent()}});renderPlayers();renderBest();renderMatches()}} init();</script></body></html>"""
    OUT_HTML.write_text(html, encoding='utf-8')

if __name__ == '__main__':
    fanta, players = build()
    print('Wrote', OUT_HTML, OUT_XLSX)
    print('Players:', len(players), 'with current minutes:', players['min_avg_current'].notna().sum(), 'with prev minutes:', players['min_avg_25_26'].notna().sum(), 'with any minutes:', players['min_avg_best'].notna().sum())
