import json
import math
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from euroleague_api.team_stats import TeamStats

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'euroleague_fantasy_data'
DATA.mkdir(exist_ok=True)
LOCAL_TZ = ZoneInfo('Europe/Zagreb')
HTML_OUT = ROOT / 'euroleague_fantasheet_style_dashboard.html'
XLSX_OUT = ROOT / 'euroleague_fantasy_pregled_fantasheet.xlsx'

CODE_MAP = {
    # Official EuroLeague TV codes -> Fantasy/schedule abbreviations
    'FBB': 'FBT',  # Fenerbahce
    'EA7': 'MIL',  # Olimpia Milan
}


def n(x):
    try:
        if x is None or pd.isna(x):
            return np.nan
        return float(x)
    except Exception:
        return np.nan


def norm_code(c):
    if pd.isna(c):
        return c
    return CODE_MAP.get(str(c), str(c))


def pct_to_num(x):
    if pd.isna(x):
        return np.nan
    if isinstance(x, str):
        x = x.replace('%', '').strip()
    return n(x)


def get_team_stats_cached(season: int, endpoint: str) -> pd.DataFrame:
    cache = DATA / f'team_{endpoint}_{season}.csv'
    ts = TeamStats('E')
    try:
        df = ts.get_team_stats_single_season(endpoint, season, phase_type_code='RS', statistic_mode='PerGame')
        if df is not None and not df.empty:
            df.to_csv(cache, index=False)
            return df
    except Exception as e:
        print(f'API fail {endpoint} {season}: {e}')
    if cache.exists():
        return pd.read_csv(cache)
    return pd.DataFrame()


def build_team_metrics(season: int) -> pd.DataFrame:
    trad = get_team_stats_cached(season, 'traditional')
    opp = get_team_stats_cached(season, 'opponentsTraditional')
    adv = get_team_stats_cached(season, 'advanced')
    opp_adv = get_team_stats_cached(season, 'opponentsAdvanced')
    if trad.empty:
        return pd.DataFrame()

    def prep(df, prefix):
        d = df.copy()
        d['team_abbr'] = d['team.tvCodes'].map(norm_code)
        d = d.set_index('team_abbr')
        out = pd.DataFrame(index=d.index)
        out['team_name'] = d.get('team.name')
        out[f'{prefix}_gp'] = pd.to_numeric(d.get('gamesPlayed'), errors='coerce')
        out[f'{prefix}_points_pg'] = pd.to_numeric(d.get('pointsScored'), errors='coerce')
        out[f'{prefix}_2pa_pg'] = pd.to_numeric(d.get('twoPointersAttempted'), errors='coerce')
        out[f'{prefix}_3pa_pg'] = pd.to_numeric(d.get('threePointersAttempted'), errors='coerce')
        out[f'{prefix}_fga_pg'] = out[f'{prefix}_2pa_pg'] + out[f'{prefix}_3pa_pg']
        out[f'{prefix}_fta_pg'] = pd.to_numeric(d.get('freeThrowsAttempted'), errors='coerce')
        out[f'{prefix}_oreb_pg'] = pd.to_numeric(d.get('offensiveRebounds'), errors='coerce')
        out[f'{prefix}_dreb_pg'] = pd.to_numeric(d.get('defensiveRebounds'), errors='coerce')
        out[f'{prefix}_reb_pg'] = pd.to_numeric(d.get('totalRebounds'), errors='coerce')
        out[f'{prefix}_ast_pg'] = pd.to_numeric(d.get('assists'), errors='coerce')
        out[f'{prefix}_tov_pg'] = pd.to_numeric(d.get('turnovers'), errors='coerce')
        out[f'{prefix}_stl_pg'] = pd.to_numeric(d.get('steals'), errors='coerce')
        out[f'{prefix}_blk_pg'] = pd.to_numeric(d.get('blocks'), errors='coerce')
        out[f'{prefix}_pir_pg'] = pd.to_numeric(d.get('pir'), errors='coerce')
        out[f'{prefix}_fg_pct'] = (pd.to_numeric(d.get('twoPointersMade'), errors='coerce') + pd.to_numeric(d.get('threePointersMade'), errors='coerce')) / out[f'{prefix}_fga_pg'].replace({0: np.nan}) * 100
        out[f'{prefix}_poss_pg'] = out[f'{prefix}_fga_pg'] + 0.44 * out[f'{prefix}_fta_pg'] - out[f'{prefix}_oreb_pg'] + out[f'{prefix}_tov_pg']
        return out

    own = prep(trad, 'for')
    alw = prep(opp, 'allowed') if not opp.empty else pd.DataFrame(index=own.index)
    df = own.join(alw.drop(columns=['team_name'], errors='ignore'), how='outer')
    if 'for_poss_pg' in df and 'allowed_poss_pg' in df:
        df['pace_possessions_pg'] = ((df['for_poss_pg'] + df['allowed_poss_pg']) / 2).round(2)
    if not adv.empty:
        a = adv.copy(); a['team_abbr'] = a['team.tvCodes'].map(norm_code); a = a.set_index('team_abbr')
        df['for_eFG_pct'] = a.get('effectiveFieldGoalPercentage').map(pct_to_num) if 'effectiveFieldGoalPercentage' in a else np.nan
        df['for_TS_pct'] = a.get('trueShootingPercentage').map(pct_to_num) if 'trueShootingPercentage' in a else np.nan
    if not opp_adv.empty:
        oa = opp_adv.copy(); oa['team_abbr'] = oa['team.tvCodes'].map(norm_code); oa = oa.set_index('team_abbr')
        df['allowed_eFG_pct'] = oa.get('effectiveFieldGoalPercentage').map(pct_to_num) if 'effectiveFieldGoalPercentage' in oa else np.nan
        df['allowed_TS_pct'] = oa.get('trueShootingPercentage').map(pct_to_num) if 'trueShootingPercentage' in oa else np.nan
    df['season'] = season
    return df.reset_index()


def blend_team_context(schedule_teams) -> pd.DataFrame:
    cur = build_team_metrics(2026)
    prev = build_team_metrics(2025)
    cur.to_csv(DATA / 'team_metrics_2026_current.csv', index=False)
    prev.to_csv(DATA / 'team_metrics_2025_26.csv', index=False)
    cur_i = cur.set_index('team_abbr') if not cur.empty else pd.DataFrame()
    prev_i = prev.set_index('team_abbr') if not prev.empty else pd.DataFrame()
    numeric_cols = sorted(set(cur.select_dtypes(include=[np.number]).columns if not cur.empty else []) | set(prev.select_dtypes(include=[np.number]).columns if not prev.empty else []))
    numeric_cols = [c for c in numeric_cols if c != 'season']
    rows = []
    league_avg = prev_i[numeric_cols].mean(numeric_only=True) if not prev_i.empty else cur_i[numeric_cols].mean(numeric_only=True)
    for team in sorted(schedule_teams):
        has_cur = team in cur_i.index
        has_prev = team in prev_i.index
        row = {'team_abbr': team}
        if has_cur:
            row['team_name'] = cur_i.loc[team].get('team_name') if 'team_name' in cur_i.columns else team
        elif has_prev:
            row['team_name'] = prev_i.loc[team].get('team_name') if 'team_name' in prev_i.columns else team
        else:
            row['team_name'] = team
        for col in numeric_cols:
            cv = cur_i.loc[team, col] if has_cur and col in cur_i.columns else np.nan
            pv = prev_i.loc[team, col] if has_prev and col in prev_i.columns else np.nan
            if pd.notna(cv) and pd.notna(pv):
                val = 0.40 * cv + 0.60 * pv
                src = 'blend 40% current / 60% 25-26'
            elif pd.notna(cv):
                val = cv
                src = 'current only'
            elif pd.notna(pv):
                val = pv
                src = '2025-26 only'
            else:
                val = league_avg.get(col, np.nan)
                src = 'league average fallback'
            row[col] = round(float(val), 3) if pd.notna(val) else np.nan
            row['context_source'] = src if 'context_source' not in row else row['context_source']
        # Confidence label
        if has_cur and has_prev:
            row['sample_confidence'] = 'medium/high'
        elif has_prev:
            row['sample_confidence'] = 'medium'
        elif has_cur:
            row['sample_confidence'] = 'low current sample'
        else:
            row['sample_confidence'] = 'low fallback'
        rows.append(row)
    ctx = pd.DataFrame(rows)

    # Opponent weakness/ease scores: high = good matchup for fantasy.
    def percentile(series):
        s = pd.to_numeric(series, errors='coerce')
        return s.rank(pct=True, na_option='keep') * 100
    ctx['pace_score'] = percentile(ctx['pace_possessions_pg'])
    ctx['pir_allowed_score'] = percentile(ctx['allowed_pir_pg'])
    ctx['points_allowed_score'] = percentile(ctx['allowed_points_pg'])
    ctx['fga_allowed_score'] = percentile(ctx['allowed_fga_pg'])
    ctx['reb_allowed_score'] = percentile(ctx['allowed_oreb_pg'] + ctx['allowed_dreb_pg'])
    ctx['team_defense_weakness_score'] = (
        0.25 * ctx['pir_allowed_score'] +
        0.20 * ctx['points_allowed_score'] +
        0.20 * ctx['fga_allowed_score'] +
        0.20 * ctx['reb_allowed_score'] +
        0.15 * ctx['pace_score']
    ).round(1)
    ctx['team_defense_fdr_1_easy_5_hard'] = (1 + 4 * (100 - ctx['team_defense_weakness_score']) / 100).round(2)
    ctx.to_csv(DATA / 'team_context.csv', index=False)
    return ctx


def build_next5_schedule(matches: pd.DataFrame, ctx: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    now = datetime.now(LOCAL_TZ)
    m = matches.copy()
    m['dt'] = pd.to_datetime(m['start_local'], errors='coerce')
    # Treat all non-played matches as future; if start time already passed but API says scheduled, keep it.
    future = m[m['status'].ne('played')].copy().sort_values(['dt', 'match_id'])
    ctx_i = ctx.set_index('team_abbr')
    rows = []
    summary = []
    teams = sorted(set(matches.home_abbr.dropna()) | set(matches.away_abbr.dropna()))
    for team in teams:
        tm = future[(future.home_abbr == team) | (future.away_abbr == team)].head(5).copy()
        ease_values = []
        fdr_values = []
        opp_texts = []
        for _, r in tm.iterrows():
            is_home = r.home_abbr == team
            opp = r.away_abbr if is_home else r.home_abbr
            ha = 'H' if is_home else 'A'
            opp_ctx = ctx_i.loc[opp] if opp in ctx_i.index else pd.Series(dtype=object)
            base_ease = float(opp_ctx.get('team_defense_weakness_score', 50)) if pd.notna(opp_ctx.get('team_defense_weakness_score', np.nan)) else 50
            # Small home/away adjustment: home slightly better, away slightly tougher.
            ease = max(0, min(100, base_ease + (3 if is_home else -3)))
            fdr = 1 + 4 * (100 - ease) / 100
            ease_values.append(ease)
            fdr_values.append(fdr)
            opp_texts.append(f'{opp}({ha},FDR {fdr:.1f})')
            rows.append({
                'team_abbr': team,
                'matchday': r.matchday,
                'start_local': r.start_local,
                'home_away': ha,
                'opponent': opp,
                'fixture': f"{r.home_abbr}-{r.away_abbr}",
                'opponent_pace': opp_ctx.get('pace_possessions_pg', np.nan),
                'opponent_allowed_pir_pg': opp_ctx.get('allowed_pir_pg', np.nan),
                'opponent_allowed_points_pg': opp_ctx.get('allowed_points_pg', np.nan),
                'opponent_allowed_fga_pg': opp_ctx.get('allowed_fga_pg', np.nan),
                'opponent_allowed_oreb_pg': opp_ctx.get('allowed_oreb_pg', np.nan),
                'opponent_allowed_dreb_pg': opp_ctx.get('allowed_dreb_pg', np.nan),
                'matchup_ease_score': round(ease, 1),
                'fdr_1_easy_5_hard': round(fdr, 2),
            })
        summary.append({
            'team_abbr': team,
            'next5_count': len(tm),
            'next5_opponents': ' · '.join(opp_texts),
            'next5_ease_score': round(float(np.mean(ease_values)), 1) if ease_values else np.nan,
            'next5_fdr_1_easy_5_hard': round(float(np.mean(fdr_values)), 2) if fdr_values else np.nan,
        })
    detail = pd.DataFrame(rows)
    summ = pd.DataFrame(summary)
    detail.to_csv(DATA / 'team_next5_schedule_detail.csv', index=False)
    summ.to_csv(DATA / 'team_next5_schedule_summary.csv', index=False)
    return detail, summ


def percentile(series):
    s = pd.to_numeric(series, errors='coerce')
    return s.rank(pct=True, na_option='keep') * 100


def build_player_options(fanta: pd.DataFrame, team_ctx: pd.DataFrame, next5: pd.DataFrame) -> pd.DataFrame:
    ctx_cols = ['team_abbr','pace_possessions_pg','for_fga_pg','allowed_fga_pg','allowed_oreb_pg','allowed_dreb_pg','allowed_pir_pg','team_defense_weakness_score']
    ctx = team_ctx[[c for c in ctx_cols if c in team_ctx.columns]].rename(columns={
        'pace_possessions_pg':'team_pace_possessions_pg',
        'for_fga_pg':'team_fga_for_pg',
        'allowed_fga_pg':'team_fga_allowed_pg',
        'allowed_oreb_pg':'team_oreb_allowed_pg',
        'allowed_dreb_pg':'team_dreb_allowed_pg',
        'allowed_pir_pg':'team_pir_allowed_pg',
    })
    df = fanta.merge(ctx, on='team_abbr', how='left').merge(next5, on='team_abbr', how='left')
    # Percentile components among players. Missing values receive 35 (low but not zero).
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
    # Penalties
    if 'is_injured' in df.columns:
        df.loc[df['is_injured'].astype(str).str.lower().isin(['true','1','yes','da']), 'option_score_next5'] -= 20
    df.loc[(df.get('pos_short') != 'HC') & (pd.to_numeric(df.get('min_avg_best'), errors='coerce').isna()), 'option_score_next5'] -= 10
    df['option_score_next5'] = df['option_score_next5'].clip(0, 100).round(1)
    def label(x):
        if pd.isna(x): return 'N/A'
        if x >= 80: return 'Elite'
        if x >= 70: return 'Strong'
        if x >= 60: return 'Good'
        if x >= 50: return 'Punt/Watchlist'
        return 'Risky/Avoid'
    df['next_period_rating'] = df['option_score_next5'].map(label)
    df = df.sort_values(['option_score_next5','value_pir_per_credit'], ascending=[False, False], na_position='last')
    df.to_csv(DATA / 'fantasheet_style_table_context.csv', index=False)
    return df


def clean_records(df, cols=None, nrows=None):
    if cols:
        df = df[[c for c in cols if c in df.columns]]
    if nrows:
        df = df.head(nrows)
    rows = []
    for rec in df.to_dict('records'):
        out = {}
        for k, v in rec.items():
            if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))) or pd.isna(v):
                out[k] = None
            elif hasattr(v, 'item'):
                out[k] = v.item()
            else:
                out[k] = v
        rows.append(out)
    return rows


def write_outputs(players: pd.DataFrame, team_ctx: pd.DataFrame, next_detail: pd.DataFrame, next_summary: pd.DataFrame, matches: pd.DataFrame):
    # Excel
    with pd.ExcelWriter(XLSX_OUT, engine='xlsxwriter') as writer:
        info = pd.DataFrame([
            ['Generated', datetime.now(LOCAL_TZ).strftime('%Y-%m-%d %H:%M %Z')],
            ['PACE', 'Estimated possessions per game: FGA + 0.44*FTA - OREB + TOV, averaged with opponent possessions.'],
            ['Schedule FDR', '1 = easier, 5 = harder. Based on opponent pace + points/PIR/FGA/rebounds allowed.'],
            ['Option score', '0-100 estimate for next period: projection, value, minutes, shot usage, next5 schedule, price gap, form, injury penalty.'],
            ['Warning', 'Early season samples are small. Blended team context uses 40% current season and 60% 2025-26 where both exist.'],
        ], columns=['Field','Value'])
        info.to_excel(writer, sheet_name='INFO', index=False)
        players.to_excel(writer, sheet_name='Players next5 options', index=False)
        team_ctx.to_excel(writer, sheet_name='Team context pace', index=False)
        next_summary.to_excel(writer, sheet_name='Team next5 summary', index=False)
        next_detail.to_excel(writer, sheet_name='Team next5 detail', index=False)
        matches.to_excel(writer, sheet_name='All fixtures', index=False)
        # Ranking sheets
        rankings = {
            'Pace leaders': team_ctx.sort_values('pace_possessions_pg', ascending=False),
            'Most FGA teams': team_ctx.sort_values('for_fga_pg', ascending=False),
            'Allow OREB': team_ctx.sort_values('allowed_oreb_pg', ascending=False),
            'Allow DREB': team_ctx.sort_values('allowed_dreb_pg', ascending=False),
            'Allow FGA': team_ctx.sort_values('allowed_fga_pg', ascending=False),
        }
        for name, df in rankings.items():
            df.to_excel(writer, sheet_name=name[:31], index=False)
        wb = writer.book
        header = wb.add_format({'bold': True, 'bg_color': '#17365d', 'font_color': 'white', 'border': 1})
        good = wb.add_format({'bg_color': '#C6EFCE', 'font_color': '#006100'})
        bad = wb.add_format({'bg_color': '#FFC7CE', 'font_color': '#9C0006'})
        for sheet, df in [('INFO', info), ('Players next5 options', players), ('Team context pace', team_ctx), ('Team next5 summary', next_summary), ('Team next5 detail', next_detail), ('All fixtures', matches)] + [(k[:31], v) for k,v in rankings.items()]:
            ws = writer.sheets[sheet]
            ws.freeze_panes(1,0)
            ws.autofilter(0,0,max(len(df),1),max(len(df.columns)-1,0))
            for i,col in enumerate(df.columns):
                ws.write(0,i,col,header)
                sample = df[col].head(300).fillna('').astype(str).tolist() if col in df.columns else []
                width = max(9, min(30, max([len(str(col))]+[len(x) for x in sample])))
                ws.set_column(i,i,width)
            if sheet == 'Players next5 options' and 'option_score_next5' in df.columns:
                c = list(df.columns).index('option_score_next5')
                ws.conditional_format(1,c,len(df),c,{'type':'cell','criteria':'>=','value':70,'format':good})
                ws.conditional_format(1,c,len(df),c,{'type':'cell','criteria':'<','value':50,'format':bad})

    # HTML
    player_cols = ['name','team_abbr','pos_short','price','option_score_next5','next_period_rating','next5_fdr_1_easy_5_hard','next5_ease_score','next5_opponents','proj_pir_est','form_pir','value_pir_per_credit','fantasy_pts_current_md','min_avg_best','fg_attempts_pg_best','fg_pct_best','fg_attempts_per_min_best','fg_attempts_per40_best','pir_avg_current','pir_25_26','team_pace_possessions_pg','team_fga_for_pg','team_oreb_allowed_pg','team_dreb_allowed_pg','is_injured','popularity_pct','player_id']
    team_cols = ['team_abbr','team_name','pace_possessions_pg','for_fga_pg','allowed_fga_pg','allowed_oreb_pg','allowed_dreb_pg','allowed_pir_pg','team_defense_weakness_score','team_defense_fdr_1_easy_5_hard','context_source','sample_confidence']
    detail_cols = ['team_abbr','matchday','start_local','home_away','opponent','fixture','opponent_pace','opponent_allowed_pir_pg','opponent_allowed_fga_pg','opponent_allowed_oreb_pg','opponent_allowed_dreb_pg','matchup_ease_score','fdr_1_easy_5_hard']
    payload = {
        'generated': datetime.now(LOCAL_TZ).strftime('%Y-%m-%d %H:%M %Z'),
        'players': clean_records(players, player_cols),
        'teams': clean_records(team_ctx, team_cols),
        'next5': clean_records(next_summary),
        'detail': clean_records(next_detail, detail_cols),
        'paceLeaders': clean_records(team_ctx.sort_values('pace_possessions_pg', ascending=False), team_cols, 10),
        'fgaLeaders': clean_records(team_ctx.sort_values('for_fga_pg', ascending=False), team_cols, 10),
        'orebAllowed': clean_records(team_ctx.sort_values('allowed_oreb_pg', ascending=False), team_cols, 10),
        'drebAllowed': clean_records(team_ctx.sort_values('allowed_dreb_pg', ascending=False), team_cols, 10),
        'topOptions': clean_records(players, player_cols, 12),
    }
    js = json.dumps(payload, ensure_ascii=False)
    html = f"""<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'><title>EuroLeague Fantasy Advanced Matchup Dashboard</title>
<style>:root{{--bg:#07101d;--card:#111f34;--line:rgba(255,255,255,.09);--txt:#eef6ff;--mut:#9fb1c9;--blue:#5bbcff;--green:#22c55e;--red:#fb7185;--yellow:#ffd166}}*{{box-sizing:border-box}}body{{margin:0;background:linear-gradient(135deg,#07101d,#10233d 55%,#07101d);color:var(--txt);font-family:Inter,system-ui,Segoe UI,Arial,sans-serif}}header{{padding:24px 30px;border-bottom:1px solid var(--line);position:sticky;top:0;background:rgba(7,16,29,.94);backdrop-filter:blur(8px);z-index:5}}h1{{margin:0 0 8px;font-size:28px}}.mut{{color:var(--mut)}}main{{padding:22px 30px 70px}}.tabs{{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px}}button{{background:#142842;color:var(--txt);border:1px solid var(--line);border-radius:10px;padding:9px 12px;cursor:pointer}}button.active,button:hover{{border-color:var(--blue)}}.panel{{display:none}}.panel.active{{display:block}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:12px;margin-bottom:16px}}.box{{background:rgba(17,31,52,.82);border:1px solid var(--line);border-radius:16px;padding:14px}}.box h3{{margin:0 0 10px;font-size:16px}}.row{{display:flex;justify-content:space-between;gap:10px;padding:7px 0;border-bottom:1px solid var(--line)}}.row:last-child{{border-bottom:0}}.note{{background:rgba(255,255,255,.055);border:1px solid var(--line);border-radius:14px;padding:13px;margin:0 0 14px;line-height:1.45}}.toolbar{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:12px}}input,select{{background:#0c182a;color:var(--txt);border:1px solid var(--line);border-radius:10px;padding:9px 10px}}.tablewrap{{overflow:auto;max-height:72vh;border:1px solid var(--line);border-radius:14px;background:rgba(17,31,52,.72)}}table{{width:100%;border-collapse:collapse;font-size:13px}}th,td{{padding:8px 10px;border-bottom:1px solid var(--line);white-space:nowrap;text-align:left}}th{{position:sticky;top:0;z-index:2;background:#193253;cursor:pointer}}tr:hover td{{background:rgba(91,188,255,.07)}}.good{{color:var(--green);font-weight:800}}.bad{{color:var(--red);font-weight:800}}.warn{{color:var(--yellow);font-weight:800}}.price{{color:var(--yellow);font-weight:800}}.pill{{display:inline-block;border-radius:999px;background:#203b62;padding:2px 8px;font-weight:700}}</style></head><body>
<header><h1>EuroLeague Fantasy Advanced Matchup Dashboard</h1><div class='mut'>Next-five schedule difficulty, pace, rebound/shot environments and player option score. Generated: <b id='gen'></b></div></header>
<main><div class='tabs'><button class='tab active' data-tab='overview'>Overview</button><button class='tab' data-tab='players'>Player Options</button><button class='tab' data-tab='teams'>Team Context</button><button class='tab' data-tab='schedule'>Next 5 Schedule</button><button class='tab' data-tab='method'>Method</button></div>
<section id='overview' class='panel active'><div class='grid'><div class='box'><h3>Top next-period options</h3><div id='topOptions'></div></div><div class='box'><h3>Fastest pace</h3><div id='paceBox'></div></div><div class='box'><h3>Most FGA per game</h3><div id='fgaBox'></div></div><div class='box'><h3>Most OREB allowed</h3><div id='orebBox'></div></div><div class='box'><h3>Most DREB allowed</h3><div id='drebBox'></div></div></div><div class='note'>Higher player option score = better next-period fantasy profile based on role, value, usage and the next five opponents. FDR: 1 is easy, 5 is hard.</div></section>
<section id='players' class='panel'><div class='toolbar'><input id='pq' placeholder='Search player/team...' oninput='renderPlayers()'><select id='teamFilter' onchange='renderPlayers()'><option value=''>All teams</option></select><select id='posFilter' onchange='renderPlayers()'><option value=''>All positions</option></select><label class='mut'><input type='checkbox' id='hideInj' onchange='renderPlayers()'> hide injured</label></div><div id='playersTable' class='tablewrap'></div></section>
<section id='teams' class='panel'><div class='toolbar'><input id='tq' placeholder='Search team...' oninput='renderTeams()'></div><div id='teamsTable' class='tablewrap'></div></section>
<section id='schedule' class='panel'><div class='toolbar'><input id='sq' placeholder='Search team/opponent...' oninput='renderSchedule()'></div><div id='scheduleTable' class='tablewrap'></div></section>
<section id='method' class='panel'><div class='note'><b>PACE</b> = estimated possessions per game: FGA + 0.44×FTA - OREB + TOV, averaged with opponent possessions.<br><br><b>Opponent environment</b> uses opponent PIR allowed, points allowed, FGA allowed, rebounds allowed and pace. High environment score is good for fantasy attackers.<br><br><b>FDR</b>: 1 easy / 5 hard. Home games get a small positive adjustment, away games a small negative adjustment.<br><br><b>Option score</b> combines projected PIR, PIR per credit, minutes, FGA per minute, next-five schedule, price gap and form. Injury flag subtracts points. Early-season sample is small, so team context blends current season with 2025-26 where possible.</div></section></main>
<script>const DATA={js};let sort={{players:{{col:'option_score_next5',dir:-1}},teams:{{col:'pace_possessions_pg',dir:-1}},schedule:{{col:'team_abbr',dir:1}}}};const labels={{name:'Player',team_abbr:'Team',pos_short:'Pos',price:'Price',option_score_next5:'Option',next_period_rating:'Rating',next5_fdr_1_easy_5_hard:'Next5 FDR',next5_ease_score:'Sched+',next5_opponents:'Next5',proj_pir_est:'Proj',form_pir:'Form',value_pir_per_credit:'Value',fantasy_pts_current_md:'Fantasy MD',min_avg_best:'MIN',fg_attempts_pg_best:'FGA/G',fg_pct_best:'FG%',fg_attempts_per_min_best:'FGA/min',fg_attempts_per40_best:'FGA/40',pir_avg_current:'PIR',pir_25_26:'PIR 25-26',team_pace_possessions_pg:'Team Pace',team_fga_for_pg:'Team FGA',team_oreb_allowed_pg:'Team OREB allowed',team_dreb_allowed_pg:'Team DREB allowed',is_injured:'Inj',popularity_pct:'Pick%',team_name:'Team name',pace_possessions_pg:'Pace',for_fga_pg:'FGA for',allowed_fga_pg:'FGA allowed',allowed_oreb_pg:'OREB allowed',allowed_dreb_pg:'DREB allowed',allowed_pir_pg:'PIR allowed',team_defense_weakness_score:'Weakness+',team_defense_fdr_1_easy_5_hard:'Defense FDR',context_source:'Source',sample_confidence:'Confidence',matchday:'MD',start_local:'Time',home_away:'H/A',opponent:'Opp',fixture:'Fixture',opponent_pace:'Opp pace',opponent_allowed_pir_pg:'Opp PIR allowed',opponent_allowed_fga_pg:'Opp FGA allowed',opponent_allowed_oreb_pg:'Opp OREB allowed',opponent_allowed_dreb_pg:'Opp DREB allowed',matchup_ease_score:'Matchup+',fdr_1_easy_5_hard:'FDR'}};function val(x){{return x===null||x===undefined?'':x}}function num(x){{let n=parseFloat(x);return isNaN(n)?null:n}}function fmt(k,x){{if(x===null||x===undefined||x==='')return '<span class="mut">–</span>';if(k==='pos_short')return `<span class='pill'>${{x}}</span>`;if(k==='price')return `<span class='price'>${{Number(x).toFixed(1)}}</span>`;if(k==='option_score_next5'){{let n=Number(x);return `<span class='${{n>=70?'good':(n<50?'bad':'warn')}}'>${{n.toFixed(1)}}</span>`}}if(k==='is_injured')return x?'<span class="bad">YES</span>':'NO';if(typeof x==='number')return Number.isInteger(x)?x:x.toFixed(2);return String(x)}}function ftext(r,q){{return !q||Object.values(r).join(' ').toLowerCase().includes(q.toLowerCase())}}function table(el,rows,cols,key){{let st=sort[key];let rs=rows.slice();if(st&&st.col)rs.sort((a,b)=>{{let av=a[st.col],bv=b[st.col],an=num(av),bn=num(bv);if(an!==null&&bn!==null)return(an-bn)*st.dir;return String(val(av)).localeCompare(String(val(bv)))*st.dir}});let h='<table><thead><tr>'+cols.map(c=>`<th data-col="${{c}}">${{labels[c]||c}}</th>`).join('')+'</tr></thead><tbody>'+rs.map(r=>'<tr>'+cols.map(c=>`<td>${{fmt(c,r[c])}}</td>`).join('')+'</tr>').join('')+'</tbody></table>';document.getElementById(el).innerHTML=h;document.querySelectorAll(`#${{el}} th`).forEach(th=>th.onclick=()=>{{let c=th.dataset.col;sort[key].dir=sort[key].col===c?-sort[key].dir:1;sort[key].col=c;renderCurrent()}})}}
const pcols=['name','team_abbr','pos_short','price','option_score_next5','next_period_rating','next5_fdr_1_easy_5_hard','next5_opponents','proj_pir_est','form_pir','value_pir_per_credit','fantasy_pts_current_md','min_avg_best','fg_attempts_pg_best','fg_pct_best','fg_attempts_per_min_best','fg_attempts_per40_best','pir_avg_current','pir_25_26','team_pace_possessions_pg','team_fga_for_pg','team_oreb_allowed_pg','team_dreb_allowed_pg','is_injured','popularity_pct'];
const tcols=['team_abbr','team_name','pace_possessions_pg','for_fga_pg','allowed_fga_pg','allowed_oreb_pg','allowed_dreb_pg','allowed_pir_pg','team_defense_weakness_score','team_defense_fdr_1_easy_5_hard','context_source','sample_confidence'];
const scols=['team_abbr','matchday','start_local','home_away','opponent','fixture','opponent_pace','opponent_allowed_pir_pg','opponent_allowed_fga_pg','opponent_allowed_oreb_pg','opponent_allowed_dreb_pg','matchup_ease_score','fdr_1_easy_5_hard'];
function renderPlayers(){{let q=pq.value,t=teamFilter.value,p=posFilter.value;table('playersTable',DATA.players.filter(r=>ftext(r,q)&&(!t||r.team_abbr===t)&&(!p||r.pos_short===p)&&(!hideInj.checked||!r.is_injured)),pcols,'players')}}function renderTeams(){{table('teamsTable',DATA.teams.filter(r=>ftext(r,tq.value)),tcols,'teams')}}function renderSchedule(){{table('scheduleTable',DATA.detail.filter(r=>ftext(r,sq.value)),scols,'schedule')}}function renderCurrent(){{let id=document.querySelector('.panel.active').id;if(id==='players')renderPlayers();if(id==='teams')renderTeams();if(id==='schedule')renderSchedule()}}function mini(el,rows,main,sub){{document.getElementById(el).innerHTML=rows.map(r=>`<div class='row'><span>${{r[main]}}</span><b>${{fmt(sub,r[sub])}}</b></div>`).join('')}}function init(){{gen.textContent=DATA.generated;[...new Set(DATA.players.map(r=>r.team_abbr).filter(Boolean))].sort().forEach(x=>teamFilter.innerHTML+=`<option>${{x}}</option>`);[...new Set(DATA.players.map(r=>r.pos_short).filter(Boolean))].sort().forEach(x=>posFilter.innerHTML+=`<option>${{x}}</option>`);document.querySelectorAll('.tab').forEach(b=>b.onclick=()=>{{document.querySelectorAll('.tab,.panel').forEach(x=>x.classList.remove('active'));b.classList.add('active');document.getElementById(b.dataset.tab).classList.add('active');renderCurrent()}});mini('topOptions',DATA.topOptions,'name','option_score_next5');mini('paceBox',DATA.paceLeaders,'team_abbr','pace_possessions_pg');mini('fgaBox',DATA.fgaLeaders,'team_abbr','for_fga_pg');mini('orebBox',DATA.orebAllowed,'team_abbr','allowed_oreb_pg');mini('drebBox',DATA.drebAllowed,'team_abbr','allowed_dreb_pg');renderPlayers();renderTeams();renderSchedule()}}init();</script></body></html>"""
    HTML_OUT.write_text(html, encoding='utf-8')


def main():
    matches = pd.read_csv(DATA / 'utakmice.csv')
    fanta_path = DATA / 'fantasheet_style_table.csv'
    if not fanta_path.exists():
        raise FileNotFoundError('Run create_fantasheet_style_dashboard.py first')
    fanta = pd.read_csv(fanta_path)
    schedule_teams = sorted(set(matches.home_abbr.dropna()) | set(matches.away_abbr.dropna()))
    team_ctx = blend_team_context(schedule_teams)
    next_detail, next_summary = build_next5_schedule(matches, team_ctx)
    players = build_player_options(fanta, team_ctx, next_summary)
    write_outputs(players, team_ctx, next_detail, next_summary, matches)
    print('Wrote', HTML_OUT, XLSX_OUT)
    print('Top options:')
    print(players[['name','team_abbr','price','option_score_next5','next_period_rating','next5_fdr_1_easy_5_hard','next5_opponents']].head(12).to_string(index=False))
    print('\nTeam pace leaders:')
    print(team_ctx[['team_abbr','pace_possessions_pg','for_fga_pg','allowed_oreb_pg','allowed_dreb_pg']].sort_values('pace_possessions_pg', ascending=False).head(10).to_string(index=False))

if __name__ == '__main__':
    main()
