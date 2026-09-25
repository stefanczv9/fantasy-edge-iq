import asyncio
import aiohttp
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / 'fpl_fantasy_data'
OUT_DIR.mkdir(exist_ok=True)
HTML_OUT = ROOT / 'fpl_fantasy_dashboard.html'
XLSX_OUT = ROOT / 'fpl_fantasy_pregled.xlsx'
BASE = 'https://fantasy.premierleague.com/api'
HEADERS = {'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36', 'accept': 'application/json'}
LOCAL_TZ = ZoneInfo('Europe/Zagreb')


def get_json(url):
    r = requests.get(url, headers=HEADERS, timeout=60)
    r.raise_for_status()
    return r.json()


async def fetch_json(session, url, tries=3):
    for attempt in range(tries):
        try:
            async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=25)) as resp:
                if resp.status == 429:
                    await asyncio.sleep(2 + attempt * 2)
                    continue
                if resp.status >= 400:
                    return None
                return await resp.json(content_type=None)
        except Exception:
            if attempt == tries - 1:
                return None
            await asyncio.sleep(0.5 + attempt)
    return None


async def fetch_summaries(ids, concurrency=40):
    sem = asyncio.Semaphore(concurrency)
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=concurrency)) as session:
        async def one(pid):
            async with sem:
                return pid, await fetch_json(session, f'{BASE}/element-summary/{pid}/')
        return await asyncio.gather(*[one(pid) for pid in ids])


def to_local(iso):
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso.replace('Z', '+00:00')).astimezone(LOCAL_TZ).strftime('%Y-%m-%d %H:%M')
    except Exception:
        return iso


def pct_to_float(x):
    try:
        return float(x)
    except Exception:
        return None


def fnum(x):
    try:
        if x in ('', None):
            return None
        return float(x)
    except Exception:
        return None


def safe_div(a, b):
    try:
        if b is None or b == 0 or pd.isna(b):
            return None
        return a / b
    except Exception:
        return None


def build():
    bootstrap = get_json(f'{BASE}/bootstrap-static/')
    fixtures = get_json(f'{BASE}/fixtures/')
    with open(OUT_DIR / 'bootstrap_static.json', 'w', encoding='utf-8') as f:
        json.dump(bootstrap, f, ensure_ascii=False, indent=2)
    with open(OUT_DIR / 'fixtures_raw.json', 'w', encoding='utf-8') as f:
        json.dump(fixtures, f, ensure_ascii=False, indent=2)

    teams = {t['id']: t for t in bootstrap['teams']}
    team_short = {tid: t['short_name'] for tid, t in teams.items()}
    pos = {et['id']: et for et in bootstrap['element_types']}
    pos_short = {pid: p['singular_name_short'] for pid, p in pos.items()}
    events = bootstrap['events']
    current_event = next((e for e in events if e.get('is_current')), None) or next((e for e in events if e.get('is_previous')), None)
    next_event = next((e for e in events if e.get('is_next')), None)
    previous_event = next((e for e in events if e.get('is_previous')), None)

    # Fetch per-player history for accurate average minutes and next fixtures.
    ids = [e['id'] for e in bootstrap['elements']]
    summary_pairs = asyncio.run(fetch_summaries(ids))
    summaries = {pid: js for pid, js in summary_pairs if js}
    with open(OUT_DIR / 'element_summaries.json', 'w', encoding='utf-8') as f:
        json.dump(summaries, f, ensure_ascii=False)

    player_rows = []
    history_rows = []
    upcoming_rows = []
    for e in bootstrap['elements']:
        s = summaries.get(e['id'], {})
        hist = s.get('history', []) or []
        fut = s.get('fixtures', []) or []
        hist_df = pd.DataFrame(hist)
        apps = int((hist_df['minutes'] > 0).sum()) if not hist_df.empty and 'minutes' in hist_df else 0
        starts_hist = int(hist_df['starts'].sum()) if not hist_df.empty and 'starts' in hist_df else int(e.get('starts') or 0)
        min_avg_app = round(float(hist_df.loc[hist_df['minutes'] > 0, 'minutes'].mean()), 1) if apps else None
        min_avg_gw = round(float(hist_df['minutes'].mean()), 1) if not hist_df.empty and 'minutes' in hist_df else None
        last3_min = round(float(hist_df.tail(3)['minutes'].mean()), 1) if len(hist_df) else None
        last5_min = round(float(hist_df.tail(5)['minutes'].mean()), 1) if len(hist_df) else None
        last3_pts = round(float(hist_df.tail(3)['total_points'].mean()), 1) if len(hist_df) and 'total_points' in hist_df else None
        last5_pts = round(float(hist_df.tail(5)['total_points'].mean()), 1) if len(hist_df) and 'total_points' in hist_df else None
        next5 = fut[:5]
        next_fixture = None
        next_fdr = None
        fdr_next5 = None
        next_fixtures_txt = None
        if next5:
            def fixture_label(ff):
                opp = ff['team_a'] if ff.get('is_home') else ff['team_h']
                ha = 'H' if ff.get('is_home') else 'A'
                return f"{team_short.get(opp, opp)}({ha},{ff.get('difficulty')})"
            next_fixture = fixture_label(next5[0])
            next_fdr = next5[0].get('difficulty')
            fdrs = [ff.get('difficulty') for ff in next5 if ff.get('difficulty') is not None]
            fdr_next5 = round(sum(fdrs)/len(fdrs), 2) if fdrs else None
            next_fixtures_txt = ' · '.join(fixture_label(ff) for ff in next5)
        price = (e.get('now_cost') or 0) / 10
        ppg = fnum(e.get('points_per_game'))
        form = fnum(e.get('form'))
        ep_next = fnum(e.get('ep_next'))
        total_points = e.get('total_points')
        xg = fnum(e.get('expected_goals'))
        xa = fnum(e.get('expected_assists'))
        xgi = fnum(e.get('expected_goal_involvements'))
        mins = e.get('minutes') or 0
        row = {
            'player_id': e.get('id'),
            'code': e.get('code'),
            'web_name': e.get('web_name'),
            'full_name': f"{e.get('first_name') or ''} {e.get('second_name') or ''}".strip(),
            'team': teams[e['team']]['name'],
            'team_short': teams[e['team']]['short_name'],
            'position': pos[e['element_type']]['singular_name'],
            'pos': pos_short[e['element_type']],
            'price': round(price, 1),
            'cost_change_gw': (e.get('cost_change_event') or 0) / 10,
            'cost_change_start': (e.get('cost_change_start') or 0) / 10,
            'price_change_percent': fnum(e.get('price_change_percent')),
            'form': form,
            'ep_next': ep_next,
            'event_points': e.get('event_points'),
            'total_points': total_points,
            'points_per_game': ppg,
            'value_ppg_per_m': round(ppg / price, 2) if ppg is not None and price else None,
            'value_total_per_m': round(total_points / price, 2) if total_points is not None and price else None,
            'selected_by_percent': pct_to_float(e.get('selected_by_percent')),
            'transfers_in_event': e.get('transfers_in_event'),
            'transfers_out_event': e.get('transfers_out_event'),
            'transfers_balance_event': (e.get('transfers_in_event') or 0) - (e.get('transfers_out_event') or 0),
            'transfers_in_total': e.get('transfers_in'),
            'transfers_out_total': e.get('transfers_out'),
            'status': e.get('status'),
            'news': e.get('news'),
            'chance_next': e.get('chance_of_playing_next_round'),
            'can_select': e.get('can_select'),
            'minutes_total': mins,
            'apps': apps,
            'starts': starts_hist,
            'min_avg_app': min_avg_app,
            'min_avg_gw': min_avg_gw,
            'min_last3': last3_min,
            'min_last5': last5_min,
            'points_last3_avg': last3_pts,
            'points_last5_avg': last5_pts,
            'goals': e.get('goals_scored'),
            'assists': e.get('assists'),
            'clean_sheets': e.get('clean_sheets'),
            'goals_conceded': e.get('goals_conceded'),
            'saves': e.get('saves'),
            'bonus': e.get('bonus'),
            'bps': e.get('bps'),
            'yellow_cards': e.get('yellow_cards'),
            'red_cards': e.get('red_cards'),
            'defensive_contribution': e.get('defensive_contribution'),
            'starts_per_90': fnum(e.get('starts_per_90')),
            'clean_sheets_per_90': fnum(e.get('clean_sheets_per_90')),
            'xg': xg,
            'xa': xa,
            'xgi': xgi,
            'xg_per_90': fnum(e.get('expected_goals_per_90')),
            'xa_per_90': fnum(e.get('expected_assists_per_90')),
            'xgi_per_90': fnum(e.get('expected_goal_involvements_per_90')),
            'xgc': fnum(e.get('expected_goals_conceded')),
            'xgc_per_90': fnum(e.get('expected_goals_conceded_per_90')),
            'influence': fnum(e.get('influence')),
            'creativity': fnum(e.get('creativity')),
            'threat': fnum(e.get('threat')),
            'ict_index': fnum(e.get('ict_index')),
            'next_fixture': next_fixture,
            'next_fdr': next_fdr,
            'fdr_next5': fdr_next5,
            'next5': next_fixtures_txt,
        }
        # simple projection and floor/ceiling from public metrics
        base_proj = None
        vals = [v for v in [ep_next, form, ppg, last3_pts] if v is not None]
        if vals:
            base_proj = round(0.4*(ep_next if ep_next is not None else sum(vals)/len(vals)) + 0.25*(form if form is not None else sum(vals)/len(vals)) + 0.2*(ppg if ppg is not None else sum(vals)/len(vals)) + 0.15*(last3_pts if last3_pts is not None else sum(vals)/len(vals)), 1)
        row['proj_points_est'] = base_proj
        row['floor_est'] = round(max(0, base_proj * 0.45), 1) if base_proj is not None else None
        row['ceiling_est'] = round(base_proj * 1.65 + 2, 1) if base_proj is not None else None
        row['fair_price_est'] = round(base_proj / 0.9, 1) if base_proj is not None else None
        row['price_gap_est'] = round(row['fair_price_est'] - price, 1) if row['fair_price_est'] is not None else None
        player_rows.append(row)
        for h in hist:
            rr = h.copy()
            rr['player_id'] = e['id']
            rr['web_name'] = e.get('web_name')
            rr['team_short'] = teams[e['team']]['short_name']
            rr['pos'] = pos_short[e['element_type']]
            rr['opponent_short'] = team_short.get(h.get('opponent_team'))
            rr['kickoff_local'] = to_local(h.get('kickoff_time'))
            history_rows.append(rr)
        for ff in fut:
            rr = ff.copy()
            rr['player_id'] = e['id']
            rr['web_name'] = e.get('web_name')
            rr['team_short'] = teams[e['team']]['short_name']
            opp = ff['team_a'] if ff.get('is_home') else ff['team_h']
            rr['opponent_short'] = team_short.get(opp)
            rr['home_away'] = 'H' if ff.get('is_home') else 'A'
            rr['kickoff_local'] = to_local(ff.get('kickoff_time'))
            upcoming_rows.append(rr)

    players_df = pd.DataFrame(player_rows).sort_values(['value_ppg_per_m', 'points_per_game', 'price'], ascending=[False, False, True], na_position='last')
    hist_df = pd.DataFrame(history_rows)
    upcoming_df = pd.DataFrame(upcoming_rows)

    fixture_rows = []
    for f in fixtures:
        h, a = teams.get(f['team_h'], {}), teams.get(f['team_a'], {})
        hs, as_ = f.get('team_h_score'), f.get('team_a_score')
        result = '' if hs is None or as_ is None else f'{hs}-{as_}'
        winner = ''
        if hs is not None and as_ is not None:
            winner = h.get('short_name') if hs > as_ else (a.get('short_name') if as_ > hs else 'DRAW')
        fixture_rows.append({
            'fixture_id': f.get('id'), 'event': f.get('event'), 'kickoff_utc': f.get('kickoff_time'),
            'kickoff_local': to_local(f.get('kickoff_time')), 'started': f.get('started'), 'finished': f.get('finished'),
            'minutes': f.get('minutes'), 'home_team': h.get('name'), 'home_short': h.get('short_name'),
            'away_team': a.get('name'), 'away_short': a.get('short_name'), 'home_score': hs, 'away_score': as_,
            'result': result, 'winner': winner,
            'home_difficulty': f.get('team_h_difficulty'), 'away_difficulty': f.get('team_a_difficulty'),
        })
    fixtures_df = pd.DataFrame(fixture_rows).sort_values(['event', 'kickoff_utc', 'fixture_id'])

    # KPI rows / widgets
    def player_name(pid):
        if pid is None:
            return None
        r = players_df[players_df['player_id'] == pid]
        return None if r.empty else r.iloc[0]['web_name']
    summary = {
        'generated': datetime.now(LOCAL_TZ).strftime('%Y-%m-%d %H:%M %Z'),
        'total_fpl_managers': bootstrap.get('total_players'),
        'current_gw': current_event.get('id') if current_event else None,
        'current_gw_name': current_event.get('name') if current_event else None,
        'current_avg_score': current_event.get('average_entry_score') if current_event else None,
        'current_highest_score': current_event.get('highest_score') if current_event else None,
        'next_gw': next_event.get('id') if next_event else None,
        'next_deadline_utc': next_event.get('deadline_time') if next_event else None,
        'next_deadline_local': to_local(next_event.get('deadline_time')) if next_event else None,
        'previous_gw': previous_event.get('id') if previous_event else None,
        'top_element': player_name(current_event.get('top_element')) if current_event else None,
        'top_element_points': (current_event.get('top_element_info') or {}).get('points') if current_event else None,
        'most_selected': player_name(current_event.get('most_selected')) if current_event else None,
        'most_transferred_in': player_name(current_event.get('most_transferred_in')) if current_event else None,
        'most_captained': player_name(current_event.get('most_captained')) if current_event else None,
        'transfers_made_current': current_event.get('transfers_made') if current_event else None,
        'players_count': len(players_df),
        'fixtures_count': len(fixtures_df),
    }
    with open(OUT_DIR / 'summary.json', 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # Save CSVs.
    players_df.to_csv(OUT_DIR / 'fpl_players.csv', index=False)
    fixtures_df.to_csv(OUT_DIR / 'fpl_fixtures.csv', index=False)
    hist_df.to_csv(OUT_DIR / 'fpl_player_history.csv', index=False)
    upcoming_df.to_csv(OUT_DIR / 'fpl_upcoming_player_fixtures.csv', index=False)

    write_excel(summary, players_df, fixtures_df, hist_df, upcoming_df)
    write_html(summary, players_df, fixtures_df)
    return summary, players_df, fixtures_df


def write_excel(summary, players, fixtures, hist, upcoming):
    dashboard_info = pd.DataFrame(list(summary.items()), columns=['Polje', 'Vrijednost'])
    injuries = players[(players['status'] != 'a') | (players['news'].fillna('') != '')].sort_values(['selected_by_percent'], ascending=False)
    transfers_in = players.sort_values('transfers_in_event', ascending=False).head(50)
    transfers_out = players.sort_values('transfers_out_event', ascending=False).head(50)
    price_changes = players[players['cost_change_gw'] != 0].sort_values('cost_change_gw', ascending=False)
    best_value = players.sort_values(['value_ppg_per_m', 'points_per_game'], ascending=[False, False]).head(100)
    with pd.ExcelWriter(XLSX_OUT, engine='xlsxwriter') as writer:
        dashboard_info.to_excel(writer, sheet_name='INFO', index=False)
        players.to_excel(writer, sheet_name='Players dashboard', index=False)
        best_value.to_excel(writer, sheet_name='Best value', index=False)
        fixtures.to_excel(writer, sheet_name='Fixtures', index=False)
        hist.to_excel(writer, sheet_name='Player GW history', index=False)
        upcoming.to_excel(writer, sheet_name='Upcoming fixtures', index=False)
        injuries.to_excel(writer, sheet_name='Injuries-news', index=False)
        transfers_in.to_excel(writer, sheet_name='Transfers in', index=False)
        transfers_out.to_excel(writer, sheet_name='Transfers out', index=False)
        price_changes.to_excel(writer, sheet_name='Price changes', index=False)
        wb = writer.book
        header = wb.add_format({'bold': True, 'bg_color': '#174a7c', 'font_color': 'white', 'border': 1})
        good = wb.add_format({'bg_color': '#C6EFCE', 'font_color': '#006100'})
        bad = wb.add_format({'bg_color': '#FFC7CE', 'font_color': '#9C0006'})
        for sheet, df in [('INFO', dashboard_info), ('Players dashboard', players), ('Best value', best_value), ('Fixtures', fixtures), ('Player GW history', hist), ('Upcoming fixtures', upcoming), ('Injuries-news', injuries), ('Transfers in', transfers_in), ('Transfers out', transfers_out), ('Price changes', price_changes)]:
            ws = writer.sheets[sheet]
            ws.freeze_panes(1, 0)
            ws.autofilter(0, 0, max(len(df), 1), max(len(df.columns)-1, 0))
            for i, col in enumerate(df.columns):
                ws.write(0, i, col, header)
                sample = df[col].head(300).fillna('').astype(str).tolist() if col in df.columns else []
                width = max(9, min(30, max([len(str(col))] + [len(x) for x in sample])))
                ws.set_column(i, i, width)
            if sheet in ('Players dashboard', 'Best value'):
                for colname in ['value_ppg_per_m', 'form', 'ep_next']:
                    if colname in df.columns:
                        c = df.columns.get_loc(colname)
                        ws.conditional_format(1, c, len(df), c, {'type': 'cell', 'criteria': '>=', 'value': 0.8, 'format': good})
                if 'status' in df.columns:
                    c = df.columns.get_loc('status')
                    ws.conditional_format(1, c, len(df), c, {'type': 'text', 'criteria': 'not containing', 'value': 'a', 'format': bad})


def clean_records(df, cols=None, nrows=None):
    if cols is not None:
        df = df[[c for c in cols if c in df.columns]]
    if nrows is not None:
        df = df.head(nrows)
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


def english_clean_html(s: str) -> str:
    import re
    replacements = {
        '<html lang="sr">': '<html lang="en">',
        '<title>Fantazi Premijer Liga — pro dashboard</title>': '<title>Fantasy Premier League Dashboard — Fantasy Edge IQ</title>',
        '<h1>Fantazi Premijer Liga — Pro dashboard</h1>': '<h1>Fantasy Premier League — Advanced Dashboard</h1>',
        'Dashboard za FPL: cijene, forma, value, minute, raspored, transferi i povrede. Generisano:': 'FPL dashboard: prices, form, value, minutes, fixtures, transfers and injuries. Generated:',
        'trenutni GW': 'current GW', 'prosek PTS': 'average PTS', 'najviše PTS': 'highest PTS', 'sledeći deadline': 'next deadline', 'igrača u bazi': 'players in database',
        'data-tab="players">Igrači</button>': 'data-tab="players">Players</button>',
        'data-tab="fixtures">Utakmice</button>': 'data-tab="fixtures">Fixtures</button>',
        'data-tab="injuries">Povrede</button>': 'data-tab="injuries">Injuries</button>',
        'data-tab="transfers">Transferi/Cijene</button>': 'data-tab="transfers">Transfers / Prices</button>',
        '<button class="tab" data-tab="business">Paid verzija</button>': '',
        'Igrač kola': 'Player of the Gameweek', 'Najveće vlasništvo': 'Highest ownership', 'Najviše kupovan': 'Most bought', 'Najviše kapiten': 'Most captained',
        'Promjene cijena · GW': 'Price changes · GW', 'Transferi in': 'Transfers in', 'Povrede/news': 'Injuries/news',
        'placeholder="Pretraga igrača..."': 'placeholder="Search players..."', 'Svi klubovi': 'All clubs', 'Sve pozicije': 'All positions',
        'sakrij bez minuta': 'hide players with no minutes', 'sakrij povrijeđene/suspendovane': 'hide injured/suspended',
        '<b>Value</b> = points per game / cijena. Dodatno imaš Form, EP next, min.avg, last3/last5 minute i FDR narednih 5 kola.': '<b>Value</b> = points per game divided by price. The table also includes form, expected points, average minutes, last 3/5 minute trends and next-five FDR.',
        'placeholder="Pretraga utakmica..."': 'placeholder="Search fixtures..."', 'Sva kola': 'All gameweeks',
        'Najviše kupovani': 'Most bought', 'Najviše prodavani': 'Most sold', 'Promjene cijena': 'Price changes',
        "web_name:'Igrač'": "web_name:'Player'", "full_name:'Ime'": "full_name:'Name'", "team_short:'Klub'": "team_short:'Club'",
        "transfers_in_event:'Kupovina'": "transfers_in_event:'Transfers in'", "transfers_out_event:'Prodaja'": "transfers_out_event:'Transfers out'", "transfers_balance_event:'Balans'": "transfers_balance_event:'Transfer balance'",
        "kickoff_local:'Vrijeme'": "kickoff_local:'Time'", "result:'Rez'": "result:'Score'", "winner:'Pobj'": "winner:'Winner'",
        "if(typeof x==='boolean')return x?'DA':'NE';": "if(typeof x==='boolean')return x?'YES':'NO';",
    }
    for old, new in replacements.items():
        s = s.replace(old, new)
    s = re.sub(r'<div class="note">Ovo je prototip.*?</div>', '', s)
    s = re.sub(r'<section id="business" class="panel">.*?</section>', '', s)
    return s


def write_html(summary, players, fixtures):
    player_cols = ['web_name','full_name','team_short','pos','price','cost_change_gw','cost_change_start','form','ep_next','proj_points_est','floor_est','ceiling_est','price_gap_est','total_points','event_points','points_per_game','value_ppg_per_m','value_total_per_m','selected_by_percent','transfers_in_event','transfers_out_event','transfers_balance_event','status','news','chance_next','minutes_total','apps','starts','min_avg_app','min_avg_gw','min_last3','min_last5','points_last3_avg','points_last5_avg','goals','assists','clean_sheets','goals_conceded','saves','bonus','bps','defensive_contribution','xg','xa','xgi','xg_per_90','xa_per_90','xgi_per_90','influence','creativity','threat','ict_index','next_fixture','next_fdr','fdr_next5','next5','player_id']
    fixture_cols = ['event','kickoff_local','started','finished','home_short','away_short','result','winner','home_difficulty','away_difficulty']
    injuries = players[(players['status'] != 'a') | (players['news'].fillna('') != '')].sort_values(['selected_by_percent'], ascending=False)
    payload = {
        'summary': summary,
        'players': clean_records(players.sort_values(['value_ppg_per_m','points_per_game'], ascending=[False,False]), player_cols),
        'fixtures': clean_records(fixtures, fixture_cols),
        'injuries': clean_records(injuries, ['web_name','team_short','pos','price','selected_by_percent','status','chance_next','news','player_id']),
        'transfersIn': clean_records(players.sort_values('transfers_in_event', ascending=False), ['web_name','team_short','pos','price','transfers_in_event','transfers_out_event','selected_by_percent','player_id'], 30),
        'transfersOut': clean_records(players.sort_values('transfers_out_event', ascending=False), ['web_name','team_short','pos','price','transfers_in_event','transfers_out_event','selected_by_percent','player_id'], 30),
        'priceChanges': clean_records(players[players['cost_change_gw'] != 0].sort_values('cost_change_gw', ascending=False), ['web_name','team_short','pos','price','cost_change_gw','cost_change_start','selected_by_percent','player_id'], 50),
        'bestValue': clean_records(players.sort_values(['value_ppg_per_m','points_per_game'], ascending=[False,False]), player_cols, 100),
    }
    js = json.dumps(payload, ensure_ascii=False)
    html = f"""<!doctype html><html lang="sr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Fantazi Premijer Liga — pro dashboard</title>
<style>
:root{{--bg:#06111f;--card:#111f34;--card2:#152945;--txt:#edf6ff;--mut:#9cafca;--line:rgba(255,255,255,.09);--blue:#5ab7ff;--green:#23c55e;--red:#fb7185;--yellow:#ffd166;--purple:#b48cff}}*{{box-sizing:border-box}}body{{margin:0;background:linear-gradient(135deg,#06111f,#102340 55%,#07111f);color:var(--txt);font-family:Inter,system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif}}header{{padding:24px 30px;border-bottom:1px solid var(--line);position:sticky;top:0;z-index:5;background:rgba(6,17,31,.94);backdrop-filter:blur(8px)}}h1{{margin:0 0 8px;font-size:28px}}.mut{{color:var(--mut)}}main{{padding:22px 30px 70px}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(155px,1fr));gap:12px;margin-top:16px}}.card{{background:rgba(17,31,52,.88);border:1px solid var(--line);border-radius:16px;padding:13px}}.card b{{font-size:24px;display:block}}.tabs{{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 16px}}button{{background:#142842;color:var(--txt);border:1px solid var(--line);border-radius:10px;padding:9px 12px;cursor:pointer}}button.active,button:hover{{border-color:var(--blue);color:white}}.panel{{display:none}}.panel.active{{display:block}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px;margin-bottom:16px}}.box{{background:rgba(17,31,52,.75);border:1px solid var(--line);border-radius:16px;padding:14px}}.box h3{{margin:0 0 10px;font-size:16px}}.minirow{{display:flex;justify-content:space-between;gap:10px;padding:7px 0;border-bottom:1px solid var(--line)}}.minirow:last-child{{border-bottom:0}}.note{{background:rgba(255,255,255,.055);border:1px solid var(--line);border-radius:14px;padding:13px;margin:0 0 14px;line-height:1.45}}.toolbar{{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin:0 0 12px}}input,select{{background:#0c182a;color:var(--txt);border:1px solid var(--line);border-radius:10px;padding:9px 10px}}.tablewrap{{overflow:auto;max-height:72vh;border:1px solid var(--line);border-radius:14px;background:rgba(17,31,52,.72)}}table{{width:100%;border-collapse:collapse;font-size:13px}}th,td{{padding:8px 10px;border-bottom:1px solid var(--line);white-space:nowrap;text-align:left}}th{{position:sticky;top:0;z-index:2;background:#193253;cursor:pointer}}tr:hover td{{background:rgba(90,183,255,.07)}}.pos{{display:inline-block;border-radius:999px;padding:2px 8px;background:#203b62;font-weight:800}}.price{{color:var(--yellow);font-weight:800}}.good{{color:var(--green);font-weight:800}}.bad{{color:var(--red);font-weight:800}}.warn{{color:var(--yellow);font-weight:800}}.pill{{display:inline-block;padding:2px 8px;border-radius:999px;background:#1e375a}}@media(max-width:700px){{header,main{{padding-left:15px;padding-right:15px}}}}
</style></head><body><header><h1>Fantazi Premijer Liga — Pro dashboard</h1><div class="mut">Dashboard za FPL: cijene, forma, value, minute, raspored, transferi i povrede. Generisano: <b id="gen"></b></div><div class="cards"><div class="card"><b id="gw"></b><span class="mut">trenutni GW</span></div><div class="card"><b id="avg"></b><span class="mut">prosek PTS</span></div><div class="card"><b id="high"></b><span class="mut">najviše PTS</span></div><div class="card"><b id="deadline"></b><span class="mut">sledeći deadline</span></div><div class="card"><b id="pcnt"></b><span class="mut">igrača u bazi</span></div></div></header>
<main><div class="tabs"><button class="tab active" data-tab="dash">Dashboard</button><button class="tab" data-tab="players">Igrači</button><button class="tab" data-tab="value">Best value</button><button class="tab" data-tab="fixtures">Utakmice</button><button class="tab" data-tab="injuries">Povrede</button><button class="tab" data-tab="transfers">Transferi/Cijene</button><button class="tab" data-tab="business">Paid verzija</button></div>
<section id="dash" class="panel active"><div class="grid"><div class="box"><h3>Igrač kola</h3><div class="minirow"><b id="topEl"></b><span id="topPts" class="good"></span></div><div class="minirow"><span>Najveće vlasništvo</span><b id="mostSel"></b></div><div class="minirow"><span>Najviše kupovan</span><b id="mostIn"></b></div><div class="minirow"><span>Najviše kapiten</span><b id="mostCap"></b></div></div><div class="box"><h3>Promjene cijena · GW</h3><div id="priceMini"></div></div><div class="box"><h3>Transferi in</h3><div id="tinMini"></div></div><div class="box"><h3>Povrede/news</h3><div id="injMini"></div></div></div><div class="note">Ovo je prototip koji može biti osnova za plaćenu verziju: svi podaci su iz javnog FPL API-ja, prikazani kao Fantazi Masteri/FantaSheet stil. Za komercijalnu prodaju treba provjeriti prava/licence i uslove korišćenja podataka.</div></section>
<section id="players" class="panel"><div class="toolbar"><input id="pq" placeholder="Pretraga igrača..." oninput="renderPlayers()"><select id="team"><option value="">Svi klubovi</option></select><select id="pos"><option value="">Sve pozicije</option></select><label class="mut"><input type="checkbox" id="hideNoMin" onchange="renderPlayers()"> sakrij bez minuta</label><label class="mut"><input type="checkbox" id="hideUnavailable" onchange="renderPlayers()"> sakrij povrijeđene/suspendovane</label></div><div id="playerTable" class="tablewrap"></div></section>
<section id="value" class="panel"><div class="note"><b>Value</b> = points per game / cijena. Dodatno imaš Form, EP next, min.avg, last3/last5 minute i FDR narednih 5 kola.</div><div id="valueTable" class="tablewrap"></div></section>
<section id="fixtures" class="panel"><div class="toolbar"><input id="fq" placeholder="Pretraga utakmica..." oninput="renderFixtures()"><select id="fgw" onchange="renderFixtures()"><option value="">Sva kola</option></select></div><div id="fixtureTable" class="tablewrap"></div></section>
<section id="injuries" class="panel"><div id="injTable" class="tablewrap"></div></section>
<section id="transfers" class="panel"><div class="grid"><div class="box"><h3>Najviše kupovani</h3><div id="tinBox" class="tablewrap"></div></div><div class="box"><h3>Najviše prodavani</h3><div id="toutBox" class="tablewrap"></div></div><div class="box"><h3>Promjene cijena</h3><div id="priceBox" class="tablewrap"></div></div></div></section>
<section id="business" class="panel"><div class="note"><b>Kako ovo pretvoriti u paid verziju:</b><br>1) Login + Stripe pretplata, 2) baza podataka sa istorijom cijena/ownershipa po danu, 3) cron refresh poslije utakmica i svaki sat za promjene cijena, 4) premium alati: team builder, captain picker, fixture ticker, watchlist, price-change alert, injury report, mini-league analysis. <br><br><b>Bitno:</b> za javnu prodaju treba provjeriti FPL/Premier League prava, naziv, logo i komercijalnu upotrebu podataka. Najsigurnije je koristiti vlastiti brend i/ili licencirani sports-data provider za dio podataka.</div></section></main>
<script>const DATA={js};let sort={{players:{{col:'value_ppg_per_m',dir:-1}},value:{{col:'value_ppg_per_m',dir:-1}},fixtures:{{col:'kickoff_local',dir:1}},injuries:{{col:'selected_by_percent',dir:-1}},tin:{{col:'transfers_in_event',dir:-1}},tout:{{col:'transfers_out_event',dir:-1}},price:{{col:'cost_change_gw',dir:-1}}}};const labels={{web_name:'Igrač',full_name:'Ime',team_short:'Klub',pos:'Poz',price:'£',cost_change_gw:'ΔGW',cost_change_start:'ΔStart',form:'Form',ep_next:'EP next',proj_points_est:'Proj*',floor_est:'Floor*',ceiling_est:'Ceiling*',price_gap_est:'Gap*',total_points:'PTS',event_points:'GW pts',points_per_game:'PPG',value_ppg_per_m:'Value',value_total_per_m:'Season value',selected_by_percent:'Own%',transfers_in_event:'Kupovina',transfers_out_event:'Prodaja',transfers_balance_event:'Balans',status:'St',news:'News',chance_next:'Chance%',minutes_total:'MIN',apps:'Apps',starts:'Starts',min_avg_app:'MIN avg',min_avg_gw:'MIN/GW',min_last3:'MIN L3',min_last5:'MIN L5',points_last3_avg:'PTS L3',points_last5_avg:'PTS L5',goals:'G',assists:'A',clean_sheets:'CS',goals_conceded:'GC',saves:'Saves',bonus:'Bonus',bps:'BPS',defensive_contribution:'DefC',xg:'xG',xa:'xA',xgi:'xGI',xg_per_90:'xG90',xa_per_90:'xA90',xgi_per_90:'xGI90',influence:'Infl',creativity:'Creat',threat:'Threat',ict_index:'ICT',next_fixture:'Next',next_fdr:'FDR',fdr_next5:'FDR5',next5:'Next5',event:'GW',kickoff_local:'Vrijeme',started:'Started',finished:'Done',home_short:'Home',away_short:'Away',result:'Rez',winner:'Pobj',home_difficulty:'H FDR',away_difficulty:'A FDR'}};function val(x){{return x===null||x===undefined?'':x}}function num(x){{let n=parseFloat(x);return isNaN(n)?null:n}}function fmt(k,x){{if(x===null||x===undefined||x==='')return '<span class="mut">–</span>';if(k==='pos')return `<span class="pos">${{x}}</span>`;if(k==='price')return `<span class="price">${{Number(x).toFixed(1)}}</span>`;if(k==='status')return x==='a'?'<span class="good">OK</span>':`<span class="bad">${{x}}</span>`;if(['value_ppg_per_m','points_per_game','form','ep_next','proj_points_est'].includes(k)){{let n=Number(x);return `<span class="${{n>=5?'good':(n<2?'warn':'')}}">${{Number.isInteger(n)?n:n.toFixed(2)}}</span>`}}if(k==='cost_change_gw'){{let n=Number(x);return `<span class="${{n>0?'good':(n<0?'bad':'mut')}}">${{n>0?'+':''}}${{n.toFixed(1)}}</span>`}}if(typeof x==='boolean')return x?'DA':'NE';if(typeof x==='number')return Number.isInteger(x)?x:x.toFixed(2);return String(x)}}function filterText(r,q){{return !q||Object.values(r).join(' ').toLowerCase().includes(q.toLowerCase())}}function table(el,rows,cols,key){{let st=sort[key];let rs=rows.slice();if(st&&st.col)rs.sort((a,b)=>{{let av=a[st.col],bv=b[st.col],an=num(av),bn=num(bv);if(an!==null&&bn!==null)return(an-bn)*st.dir;return String(val(av)).localeCompare(String(val(bv)))*st.dir}});let h='<table><thead><tr>'+cols.map(c=>`<th data-col="${{c}}">${{labels[c]||c}}</th>`).join('')+'</tr></thead><tbody>'+rs.map(r=>'<tr>'+cols.map(c=>`<td>${{fmt(c,r[c])}}</td>`).join('')+'</tr>').join('')+'</tbody></table>';document.getElementById(el).innerHTML=h;document.querySelectorAll(`#${{el}} th`).forEach(th=>th.onclick=()=>{{let c=th.dataset.col;sort[key].dir=sort[key].col===c?-sort[key].dir:1;sort[key].col=c;renderCurrent()}})}}
const pcols=['web_name','team_short','pos','price','cost_change_gw','form','ep_next','proj_points_est','floor_est','ceiling_est','price_gap_est','total_points','event_points','points_per_game','value_ppg_per_m','selected_by_percent','transfers_in_event','transfers_out_event','status','news','chance_next','minutes_total','apps','starts','min_avg_app','min_avg_gw','min_last3','min_last5','points_last3_avg','points_last5_avg','goals','assists','clean_sheets','bonus','bps','defensive_contribution','xg','xa','xgi','xgi_per_90','ict_index','next_fixture','next_fdr','fdr_next5','next5'];function renderPlayers(){{let q=pq.value,t=team.value,p=pos.value;let rows=DATA.players.filter(r=>filterText(r,q)&&(!t||r.team_short===t)&&(!p||r.pos===p)&&(!hideNoMin.checked||r.min_avg_app!==null)&&(!hideUnavailable.checked||r.status==='a'));table('playerTable',rows,pcols,'players')}}function renderValue(){{table('valueTable',DATA.bestValue,pcols,'value')}}function renderFixtures(){{let q=fq.value,g=fgw.value;table('fixtureTable',DATA.fixtures.filter(r=>filterText(r,q)&&(!g||String(r.event)===g)),['event','kickoff_local','started','finished','home_short','away_short','result','winner','home_difficulty','away_difficulty'],'fixtures')}}function renderInjuries(){{table('injTable',DATA.injuries,['web_name','team_short','pos','price','selected_by_percent','status','chance_next','news','player_id'],'injuries')}}function renderTransfers(){{table('tinBox',DATA.transfersIn,['web_name','team_short','pos','price','transfers_in_event','transfers_out_event','selected_by_percent'],'tin');table('toutBox',DATA.transfersOut,['web_name','team_short','pos','price','transfers_out_event','transfers_in_event','selected_by_percent'],'tout');table('priceBox',DATA.priceChanges,['web_name','team_short','pos','price','cost_change_gw','cost_change_start','selected_by_percent'],'price')}}function renderCurrent(){{let id=document.querySelector('.panel.active').id;if(id==='players')renderPlayers();if(id==='value')renderValue();if(id==='fixtures')renderFixtures();if(id==='injuries')renderInjuries();if(id==='transfers')renderTransfers()}}function mini(el,rows,cols){{document.getElementById(el).innerHTML=rows.map(r=>`<div class="minirow"><span>${{r.web_name}} <span class="mut">${{r.team_short}} ${{r.pos}}</span></span><b>${{cols.map(c=>fmt(c,r[c])).join(' / ')}}</b></div>`).join('')}}function init(){{let s=DATA.summary;gen.textContent=s.generated;gw.textContent=s.current_gw_name||s.current_gw;avg.textContent=s.current_avg_score??'–';high.textContent=s.current_highest_score??'–';deadline.textContent=s.next_deadline_local||'–';pcnt.textContent=s.players_count;topEl.textContent=s.top_element||'–';topPts.textContent=(s.top_element_points||'–')+' pts';mostSel.textContent=s.most_selected||'–';mostIn.textContent=s.most_transferred_in||'–';mostCap.textContent=s.most_captained||'–';mini('priceMini',DATA.priceChanges.slice(0,6),['cost_change_gw']);mini('tinMini',DATA.transfersIn.slice(0,6),['transfers_in_event']);mini('injMini',DATA.injuries.slice(0,6),['status']);[...new Set(DATA.players.map(r=>r.team_short).filter(Boolean))].sort().forEach(x=>team.innerHTML+=`<option>${{x}}</option>`);[...new Set(DATA.players.map(r=>r.pos).filter(Boolean))].sort().forEach(x=>pos.innerHTML+=`<option>${{x}}</option>`);[...new Set(DATA.fixtures.map(r=>r.event).filter(x=>x!==null&&x!==undefined))].sort((a,b)=>a-b).forEach(x=>fgw.innerHTML+=`<option>${{x}}</option>`);document.querySelectorAll('.tab').forEach(b=>b.onclick=()=>{{document.querySelectorAll('.tab,.panel').forEach(x=>x.classList.remove('active'));b.classList.add('active');document.getElementById(b.dataset.tab).classList.add('active');renderCurrent()}});renderPlayers();renderValue();renderFixtures();renderInjuries();renderTransfers()}}init();</script></body></html>"""
    HTML_OUT.write_text(english_clean_html(html), encoding='utf-8')


if __name__ == '__main__':
    summary, players, fixtures = build()
    print('Wrote', HTML_OUT, XLSX_OUT)
    print('players', len(players), 'fixtures', len(fixtures))
    print('current_gw', summary.get('current_gw'), 'next_deadline', summary.get('next_deadline_local'))
