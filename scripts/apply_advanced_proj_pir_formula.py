from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json, math, re
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'euroleague_fantasy_data'
SITE = ROOT
LOCAL_TZ = ZoneInfo('Europe/Zagreb')

POS_DVP_COL = {
    'G': 'guard_pts_allowed_pg',
    'F': 'forward_pts_allowed_pg',
    'C': 'center_pts_allowed_pg',
    'Guard': 'guard_pts_allowed_pg',
    'Forward': 'forward_pts_allowed_pg',
    'Center': 'center_pts_allowed_pg',
}

EXTRA_LABELS = {
    'pir_per_min_current': 'PIR/min current',
    'current_role_projection': 'Current role PIR',
    'market_pir_baseline': 'Market PIR baseline',
    'proj_sample_weight': 'Sample weight',
    'projected_minutes': 'Projected MIN',
    'next_matchup_factor': 'Matchup factor',
    'risk_factor': 'Risk factor',
    'proj_next_opponent': 'Proj next opp',
    'proj_home_away': 'Proj H/A',
    'proj_opponent_pace': 'Opp pace',
    'proj_opponent_pir_allowed_pg': 'Opp PIR allowed',
    'proj_dvp_real_pts_allowed_pg': 'DvP real PTS allowed/G',
}

def clean_records(df: pd.DataFrame):
    def conv(v):
        try:
            if pd.isna(v):
                return None
        except Exception:
            pass
        if isinstance(v, (np.integer,)):
            return int(v)
        if isinstance(v, (np.floating, float)):
            vf = float(v)
            if math.isnan(vf) or math.isinf(vf):
                return None
            return round(vf, 4)
        if isinstance(v, (np.bool_, bool)):
            return bool(v)
        return v
    return [{k: conv(v) for k, v in row.items()} for row in df.to_dict(orient='records')]

def dumps(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(',', ':'))

def percentile(series):
    s = pd.to_numeric(series, errors='coerce')
    return s.rank(pct=True, na_option='keep') * 100

def boolish(x):
    return str(x).strip().lower() in {'true','1','yes','da'}

def clip(x, lo, hi):
    try:
        if pd.isna(x):
            return np.nan
        return min(max(float(x), lo), hi)
    except Exception:
        return np.nan

def load_dvp():
    # Prefer the already validated real-points-only DvP CSV.
    p = SITE / 'euroleague-defense-vs-position.csv'
    if p.exists():
        dvp = pd.read_csv(p)
        return dvp
    # Fallback from raw match log: real points only; no fantasy points.
    log = pd.read_csv(DATA / 'fantasy_poeni_log.csv')
    log = log[(log['match_status'] == 'played') & log['position'].isin(['Guard','Forward','Center'])]
    log['pts'] = pd.to_numeric(log['pts'], errors='coerce').fillna(0)
    rows = []
    for (mid, defense, offense), g in log.groupby(['match_id','opponent_abbr','team_abbr'], dropna=True):
        row = {'team_abbr': defense, 'match_id': mid}
        for pos, key in [('Guard','guard'),('Forward','forward'),('Center','center')]:
            row[f'{key}_pts_allowed_pg'] = g.loc[g['position']==pos, 'pts'].sum()
        rows.append(row)
    m = pd.DataFrame(rows)
    return m.groupby('team_abbr', as_index=False)[['guard_pts_allowed_pg','forward_pts_allowed_pg','center_pts_allowed_pg']].mean()

def add_advanced_projection(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    detail = pd.read_csv(DATA / 'team_next5_schedule_detail.csv')
    detail = detail.sort_values(['team_abbr','start_local'])
    first = detail.drop_duplicates('team_abbr', keep='first').copy()
    first_cols = ['team_abbr','opponent','home_away','opponent_pace','opponent_allowed_pir_pg','opponent_allowed_fga_pg','opponent_allowed_oreb_pg','opponent_allowed_dreb_pg','matchup_ease_score','fdr_1_easy_5_hard']
    first = first[[c for c in first_cols if c in first.columns]].rename(columns={
        'opponent': 'proj_next_opponent',
        'home_away': 'proj_home_away',
        'opponent_pace': 'proj_opponent_pace',
        'opponent_allowed_pir_pg': 'proj_opponent_pir_allowed_pg',
        'opponent_allowed_fga_pg': 'proj_opponent_fga_allowed_pg',
        'opponent_allowed_oreb_pg': 'proj_opponent_oreb_allowed_pg',
        'opponent_allowed_dreb_pg': 'proj_opponent_dreb_allowed_pg',
        'matchup_ease_score': 'proj_matchup_ease_score',
        'fdr_1_easy_5_hard': 'proj_fdr_1_easy_5_hard',
    })
    df = df.drop(columns=[c for c in first.columns if c != 'team_abbr' and c in df.columns], errors='ignore')
    df = df.merge(first, on='team_abbr', how='left')

    # Real-points-only DvP by next opponent and player position.
    dvp = load_dvp()
    for c in ['guard_pts_allowed_pg','forward_pts_allowed_pg','center_pts_allowed_pg']:
        if c in dvp.columns:
            dvp[c] = pd.to_numeric(dvp[c], errors='coerce')
    dvp_map = dvp.set_index('team_abbr').to_dict(orient='index') if 'team_abbr' in dvp.columns else {}
    dvp_avgs = {c: pd.to_numeric(dvp[c], errors='coerce').mean() for c in ['guard_pts_allowed_pg','forward_pts_allowed_pg','center_pts_allowed_pg'] if c in dvp.columns}

    avg_opp_pir = pd.to_numeric(detail.get('opponent_allowed_pir_pg'), errors='coerce').mean()
    avg_opp_pace = pd.to_numeric(detail.get('opponent_pace'), errors='coerce').mean()

    new_vals = {k: [] for k in ['pir_per_min_current','current_role_projection','market_pir_baseline','proj_sample_weight','projected_minutes','next_matchup_factor','risk_factor','proj_dvp_real_pts_allowed_pg','proj_pir_est']}

    for _, r in df.iterrows():
        pir = pd.to_numeric(pd.Series([r.get('pir_avg_current')]), errors='coerce').iloc[0]
        mins = pd.to_numeric(pd.Series([r.get('min_avg_current')]), errors='coerce').iloc[0]
        gp = pd.to_numeric(pd.Series([r.get('gp_current')]), errors='coerce').iloc[0]
        pos = r.get('pos_short')
        opp = r.get('proj_next_opponent')
        inj = boolish(r.get('is_injured'))
        bench = boolish(r.get('started_from_bench'))

        if pd.isna(pir) or pd.isna(mins) or mins <= 0 or pd.isna(gp) or gp <= 0 or str(pos) == 'HC':
            for k in new_vals:
                new_vals[k].append(np.nan)
            continue

        pir_per_min = pir / mins

        # Projected minutes: current-season minutes only, adjusted lightly for role.
        role_min_factor = 0.97 if bench else (1.01 if mins >= 18 else 1.00)
        projected_minutes = min(max(mins * role_min_factor, 0), 35)

        # Matchup factor: next opponent context + pace + real-points DvP + H/A.
        opp_pir = pd.to_numeric(pd.Series([r.get('proj_opponent_pir_allowed_pg')]), errors='coerce').iloc[0]
        opp_pace = pd.to_numeric(pd.Series([r.get('proj_opponent_pace')]), errors='coerce').iloc[0]
        pir_adj = 0 if pd.isna(opp_pir) or pd.isna(avg_opp_pir) or avg_opp_pir == 0 else clip(((opp_pir - avg_opp_pir) / avg_opp_pir) * 0.35, -0.06, 0.06)
        pace_adj = 0 if pd.isna(opp_pace) or pd.isna(avg_opp_pace) or avg_opp_pace == 0 else clip(((opp_pace - avg_opp_pace) / avg_opp_pace) * 0.30, -0.035, 0.035)

        dvp_col = POS_DVP_COL.get(pos)
        dvp_pts = np.nan
        dvp_adj = 0
        if dvp_col and opp in dvp_map and dvp_col in dvp_map[opp]:
            dvp_pts = pd.to_numeric(pd.Series([dvp_map[opp].get(dvp_col)]), errors='coerce').iloc[0]
            avg_pos = dvp_avgs.get(dvp_col, np.nan)
            if pd.notna(dvp_pts) and pd.notna(avg_pos) and avg_pos:
                # DvP sample is still very small, so cap its influence.
                dvp_adj = clip(((dvp_pts - avg_pos) / avg_pos) * 0.15, -0.05, 0.05)

        ha = str(r.get('proj_home_away') or '').upper()
        home_adj = 0.02 if ha == 'H' else (-0.02 if ha == 'A' else 0)
        matchup_factor = clip(1 + pir_adj + pace_adj + dvp_adj + home_adj, 0.85, 1.15)

        # Risk factor: injury, bench role and low-minute volatility.
        # Small-sample risk is handled separately through regression to a market baseline.
        risk = 1.0
        if inj:
            risk *= 0.35
        if bench:
            risk *= 0.95
        if projected_minutes < 10:
            risk *= 0.80
        elif projected_minutes < 15:
            risk *= 0.90
        elif projected_minutes < 20:
            risk *= 0.96
        risk = clip(risk, 0.25, 1.03)

        # Current-role projection can be too optimistic after one hot game.
        # Regress it toward a conservative market/price baseline until the current
        # season sample grows. This keeps a 30 PIR in Round 1 from automatically
        # becoming a 30 PIR expectation in Round 2.
        current_role_projection = pir_per_min * projected_minutes
        price = pd.to_numeric(pd.Series([r.get('price')]), errors='coerce').iloc[0]
        market_baseline = price * 1.35 if pd.notna(price) and price > 0 else current_role_projection
        sample_weight = clip(gp / 5, 0.0, 1.0)
        stabilized_base = sample_weight * current_role_projection + (1 - sample_weight) * market_baseline

        # Matchup context is useful, but early-season team/DvP samples are noisy,
        # so keep the total matchup swing modest.
        matchup_factor = clip(matchup_factor, 0.90, 1.10)
        proj = stabilized_base * matchup_factor * risk

        new_vals['pir_per_min_current'].append(round(pir_per_min, 3))
        new_vals['current_role_projection'].append(round(current_role_projection, 1))
        new_vals['market_pir_baseline'].append(round(market_baseline, 1))
        new_vals['proj_sample_weight'].append(round(sample_weight, 2))
        new_vals['projected_minutes'].append(round(projected_minutes, 1))
        new_vals['next_matchup_factor'].append(round(matchup_factor, 3))
        new_vals['risk_factor'].append(round(risk, 3))
        new_vals['proj_dvp_real_pts_allowed_pg'].append(None if pd.isna(dvp_pts) else round(float(dvp_pts), 1))
        new_vals['proj_pir_est'].append(round(float(proj), 1))

    for k, vals in new_vals.items():
        df[k] = vals
    df['form_pir'] = pd.to_numeric(df.get('pir_avg_current'), errors='coerce')
    df['floor_est'] = pd.to_numeric(df['proj_pir_est'], errors='coerce').apply(lambda x: np.nan if pd.isna(x) else round(max(-5, x * 0.55), 1))
    df['ceiling_est'] = pd.to_numeric(df['proj_pir_est'], errors='coerce').apply(lambda x: np.nan if pd.isna(x) else round(x * 1.45 + 2, 1))
    fair = pd.to_numeric(df['proj_pir_est'], errors='coerce').apply(lambda x: np.nan if pd.isna(x) else round(x / 1.4, 1))
    if 'fair_price_est' in df.columns:
        df['fair_price_est'] = fair
    if 'price' in df.columns:
        df['price_gap_est'] = (fair - pd.to_numeric(df['price'], errors='coerce')).round(1)
    return df

def recalc_option_score(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    components = {
        'proj_score_component': percentile(df.get('proj_pir_est')),
        'value_score_component': percentile(df.get('value_pir_per_credit')),
        'minutes_score_component': percentile(df.get('min_avg_best')),
        'usage_score_component': percentile(df.get('fg_attempts_per_min_best')),
        'price_gap_score_component': percentile(df.get('price_gap_est')),
        'form_score_component': percentile(df.get('form_pir')),
    }
    for k, v in components.items():
        df[k] = v.fillna(35)
    df['schedule_score_component'] = pd.to_numeric(df.get('next5_ease_score'), errors='coerce').fillna(50)
    df['option_score_next5'] = (
        0.25 * df['proj_score_component'] +
        0.18 * df['value_score_component'] +
        0.15 * df['minutes_score_component'] +
        0.15 * df['usage_score_component'] +
        0.12 * df['schedule_score_component'] +
        0.10 * df['price_gap_score_component'] +
        0.05 * df['form_score_component']
    )
    if 'is_injured' in df.columns:
        df.loc[df['is_injured'].astype(str).str.lower().isin(['true','1','yes','da']), 'option_score_next5'] -= 20
    df.loc[(df.get('pos_short') != 'HC') & (pd.to_numeric(df.get('min_avg_best'), errors='coerce').isna()), 'option_score_next5'] -= 10
    df['option_score_next5'] = df['option_score_next5'].clip(0, 100).round(1)
    def label(x):
        if pd.isna(x): return 'N/A'
        if x >= 80: return 'Elite'
        if x >= 70: return 'Strong'
        if x >= 60: return 'Good'
        if x >= 50: return 'Watch'
        return 'Risk'
    df['next_period_rating'] = df['option_score_next5'].apply(label)
    return df

def euro_label(c):
    labels = {
        'name':'Player','team_abbr':'Team','pos_short':'Pos','price':'Price','price_base':'Base price','price_change':'Price Δ',
        'proj_pir_est':'Proj PIR','form_pir':'Form PIR','value_pir_per_credit':'PIR / Cr','fantasy_pts_current_md':'Fantasy pts','value_fantasy_per_credit':'Fantasy / Cr',
        'gp_current':'GP current','min_avg_best':'MIN avg','min_avg_source':'MIN source','min_avg_current':'MIN current','pts_avg_current':'PTS current','pir_avg_current':'PIR current','pir_25_26':'PIR 25-26','min_avg_25_26':'MIN 25-26',
        'floor_est':'Floor','ceiling_est':'Ceiling','price_gap_est':'Price gap','fg_made_pg_best':'FGM/G','fg_attempts_pg_best':'FGA/G','fg_pct_best':'FG%','fg_attempts_per_min_best':'FGA/min','fg_attempts_per40_best':'FGA/40','shooting_source':'Shot source',
        'fg_made_pg_current':'FGM/G current','fg_attempts_pg_current':'FGA/G current','fg_pct_current':'FG% current','fg_attempts_per_min_current':'FGA/min current','fg_attempts_per40_current':'FGA/40 current',
        '2p_current':'2P','2p_pct_current':'2P%','3p_current':'3P','3p_pct_current':'3P%','ft_current':'FT','ft_pct_current':'FT%','two_pa_per_min_best':'2PA/min','three_pa_per_min_best':'3PA/min','fta_per_min_best':'FTA/min',
        'reb_avg_current':'REB','oreb_avg_current':'OREB','dreb_avg_current':'DREB','pf_avg_current':'PF','fd_avg_current':'FD','stl_avg_current':'STL','tov_avg_current':'TOV','ast_avg_current':'AST','blk_avg_current':'BLK','blka_avg_current':'BLKA',
        'next_opponent':'Next opp','next_start_local':'Next tip','match_status':'Match status','opponent_abbr':'Opp','home_away':'H/A','is_injured':'Injured','started_from_bench':'Bench','popularity_pct':'Popularity %','player_id':'Player ID',
        'team_pace_possessions_pg':'Team pace','team_fga_for_pg':'Team FGA','team_fga_allowed_pg':'Team FGA allowed','team_oreb_allowed_pg':'OREB allowed','team_dreb_allowed_pg':'DREB allowed','team_pir_allowed_pg':'PIR allowed','team_defense_weakness_score':'Weakness+',
        'next5_count':'Next5 games','next5_opponents':'Next5 opps','next5_ease_score':'Next5 ease','next5_fdr_1_easy_5_hard':'Next5 FDR','proj_score_component':'Proj comp','value_score_component':'Value comp','minutes_score_component':'Minutes comp','usage_score_component':'Usage comp','price_gap_score_component':'Gap comp','form_score_component':'Form comp','schedule_score_component':'Schedule comp','option_score_next5':'Option score','next_period_rating':'Rating',
        'team_name':'Team name','pace_possessions_pg':'Pace','for_fga_pg':'FGA for','allowed_fga_pg':'FGA allowed','allowed_oreb_pg':'OREB allowed','allowed_dreb_pg':'DREB allowed','allowed_pir_pg':'PIR allowed','team_defense_fdr_1_easy_5_hard':'Defense FDR','context_source':'Source','sample_confidence':'Confidence',
        'matchday':'MD','start_local':'Time','home_away':'H/A','opponent':'Opp','fixture':'Fixture','opponent_pace':'Opp pace','opponent_allowed_pir_pg':'Opp PIR allowed','opponent_allowed_fga_pg':'Opp FGA allowed','opponent_allowed_oreb_pg':'Opp OREB allowed','opponent_allowed_dreb_pg':'Opp DREB allowed','matchup_ease_score':'Matchup+','fdr_1_easy_5_hard':'FDR',
    }
    labels.update(EXTRA_LABELS)
    return labels.get(c, c.replace('_',' ').title())

def update_dashboard_data(players, teams, schedule):
    schedule_summary = pd.read_csv(DATA / 'team_next5_schedule_summary.csv')
    players_sorted = players.sort_values(['option_score_next5','proj_pir_est'], ascending=[False, False], na_position='last')
    teams = teams.copy()
    team_names = teams[['team_abbr','team_name']].drop_duplicates() if 'team_name' in teams.columns else pd.DataFrame({'team_abbr': [], 'team_name': []})
    easy = (schedule_summary.merge(team_names, on='team_abbr', how='left')
            .sort_values('next5_fdr_1_easy_5_hard', ascending=True, na_position='last')
            .head(12))
    pcols_main = ['name','team_abbr','pos_short','price','option_score_next5','next_period_rating','next5_fdr_1_easy_5_hard','next5_opponents','proj_pir_est','form_pir','value_pir_per_credit','fantasy_pts_current_md','min_avg_best','pir_avg_current','pir_25_26','fg_attempts_pg_best','fg_pct_best','fg_attempts_per_min_best','reb_avg_current','ast_avg_current','stl_avg_current','tov_avg_current','team_pace_possessions_pg','team_fga_for_pg','team_pir_allowed_pg','is_injured','started_from_bench','popularity_pct']
    pcols_main = [c for c in pcols_main if c in players_sorted.columns]
    pcols_full = list(players_sorted.columns)
    tcols = list(teams.columns)
    scols = list(schedule.columns)
    data = {
        'generated': datetime.now(LOCAL_TZ).strftime('%Y-%m-%d %H:%M %Z'),
        'players': clean_records(players_sorted),
        'teams': clean_records(teams),
        'schedule': clean_records(schedule),
        'topOptions': clean_records(players_sorted.head(12).copy()),
        'valueLeaders': clean_records(players_sorted.sort_values('value_pir_per_credit', ascending=False, na_position='last').head(12)),
        'usageLeaders': clean_records(players_sorted.sort_values('fg_attempts_per_min_best', ascending=False, na_position='last').head(12)),
        'paceLeaders': clean_records(teams.sort_values('pace_possessions_pg', ascending=False, na_position='last').head(8)),
        'easyRuns': clean_records(easy),
        'pcolsMain': pcols_main,
        'pcolsFull': pcols_full,
        'tcols': tcols,
        'scols': scols,
        'labels': {c: euro_label(c) for c in set(pcols_full + tcols + scols)},
    }
    return data, players_sorted

def replace_json(path: Path, data, pattern):
    text = path.read_text(encoding='utf-8')
    new_text, n = re.subn(pattern, lambda m: m.group(1) + dumps(data) + m.group(3), text, count=1, flags=re.S)
    if n != 1:
        raise RuntimeError(f'could not replace DATA in {path}')
    path.write_text(new_text, encoding='utf-8')
    print('updated DATA in', path.name)

# Load current context, apply advanced projection and recalc scores.
players = pd.read_csv(DATA / 'fantasheet_style_table_context.csv')
players = add_advanced_projection(players)
players = recalc_option_score(players)

# Save context and sync base table columns.
players.to_csv(DATA / 'fantasheet_style_table_context.csv', index=False)
base_path = DATA / 'fantasheet_style_table.csv'
if base_path.exists():
    base = pd.read_csv(base_path)
    sync_cols = ['player_id','proj_pir_est','form_pir','floor_est','ceiling_est','price_gap_est','pir_per_min_current','current_role_projection','market_pir_baseline','proj_sample_weight','projected_minutes','next_matchup_factor','risk_factor','proj_next_opponent','proj_home_away','proj_opponent_pace','proj_opponent_pir_allowed_pg','proj_dvp_real_pts_allowed_pg']
    sync = players[[c for c in sync_cols if c in players.columns]].copy()
    if 'player_id' in base.columns and 'player_id' in sync.columns:
        base = base.drop(columns=[c for c in sync.columns if c != 'player_id' and c in base.columns], errors='ignore').merge(sync, on='player_id', how='left')
        base.to_csv(base_path, index=False)

# Update site CSVs and embedded JSON.
teams = pd.read_csv(DATA / 'team_context.csv')
schedule = pd.read_csv(DATA / 'team_next5_schedule_detail.csv')
data, players_sorted = update_dashboard_data(players, teams, schedule)
players_sorted.to_csv(SITE / 'euroleague-players-full.csv', index=False)
teams.to_csv(SITE / 'euroleague-team-context.csv', index=False)
schedule.to_csv(SITE / 'euroleague-next5-schedule.csv', index=False)
replace_json(SITE / 'euroleague-dashboard.html', data, r'(const DATA=)(.*?)(;\nconst numCols=)')

# Team analyzer data.
line_cols = ['name','team_abbr','pos_short','price','option_score_next5','next_period_rating','next5_fdr_1_easy_5_hard','next5_opponents','proj_pir_est','form_pir','value_pir_per_credit','min_avg_best','fg_attempts_pg_best','fg_attempts_per_min_best','pir_avg_current','pir_25_26','is_injured','started_from_bench','popularity_pct','player_id']
line_players = players_sorted[[c for c in line_cols if c in players_sorted.columns]].copy()
line_data = {'generated': data['generated'], 'players': clean_records(line_players)}
replace_json(SITE / 'euroleague-team-analyzer.html', line_data, r'(const DATA=)(.*?)(;let selected=)')

# Localized dashboards keep translated labels; data is synced from English.
for fn in ['sr-euroleague-dashboard.html','el-euroleague-dashboard.html']:
    p = SITE / fn
    text = p.read_text(encoding='utf-8')
    m = re.search(r'const DATA=(.*?);\nconst numCols=', text, flags=re.S)
    old_labels = {}
    if m:
        try:
            old_labels = json.loads(m.group(1)).get('labels', {})
        except Exception:
            old_labels = {}
    loc_data = json.loads(dumps(data))
    # Preserve existing localized labels where present; add English labels for new technical fields.
    loc_data['labels'] = {**loc_data.get('labels', {}), **old_labels}
    new_text, n = re.subn(r'(const DATA=)(.*?)(;\nconst numCols=)', lambda mm: mm.group(1) + dumps(loc_data) + mm.group(3), text, count=1, flags=re.S)
    if n != 1:
        raise RuntimeError(f'could not replace localized DATA in {fn}')
    p.write_text(new_text, encoding='utf-8')
    print('updated DATA in', fn)

print('\nAdvanced Proj PIR examples:')
cols = ['name','team_abbr','pos_short','pir_avg_current','min_avg_current','pir_per_min_current','projected_minutes','proj_next_opponent','proj_home_away','next_matchup_factor','risk_factor','proj_pir_est','option_score_next5']
print(players_sorted[cols].head(15).to_string(index=False))
