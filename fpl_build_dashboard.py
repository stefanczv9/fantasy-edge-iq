#!/usr/bin/env python3
"""FEIQ — FPL CSV + dashboard generator.
Cita fpl_fantasy_data/{bootstrap_static,fixtures_raw,element_summaries,summary}.json
i gradi: 4 CSV-a (fpl_players/fixtures/player_history/upcoming_player_fixtures)
+ azurira DATA blok u premier-league-dashboard.html + kopira CSV-e u root.
"""
import json, csv, re
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / 'fpl_fantasy_data'
TZ = ZoneInfo('Europe/Zagreb')

bs = json.load(open(D / 'bootstrap_static.json'))
fx_raw = json.load(open(D / 'fixtures_raw.json'))
sums = json.load(open(D / 'element_summaries.json'))

teams = {t['id']: t for t in bs['teams']}
team_short = {t['id']: t['short_name'] for t in bs['teams']}
team_name = {t['id']: t['name'] for t in bs['teams']}
types = {t['id']: t for t in bs['element_types']}
pos_map = {t['id']: t['singular_name_short'] for t in bs['element_types']}
pos_full = {t['id']: t['singular_name'] for t in bs['element_types']}
els = bs['elements']
el_by_id = {e['id']: e for e in els}

def stamp_now():
    now = datetime.now(TZ)
    return now.strftime('%Y-%m-%d %H:%M ') + ('CEST' if now.dst() else 'CET')

def fnum(v, nd=None):
    """float format: 6 -> '6.0' ... kao stari csv"""
    if v is None or v == '':
        return ''
    x = float(v)
    return f'{x:.{nd}f}' if nd is not None else f'{x:.1f}'

def to_local(iso):
    if not iso:
        return ''
    return datetime.fromisoformat(iso.replace('Z', '+00:00')).astimezone(TZ).strftime('%Y-%m-%d %H:%M')

# ---------- 1) fpl_fixtures.csv ----------
fx_rows = []
for f in sorted(fx_raw, key=lambda x: (x.get('kickoff_time') or '9999', x['id'])):
    hs, as_ = f.get('team_h_score'), f.get('team_a_score')
    fin = bool(f.get('finished'))
    res, winner = '', ''
    if fin and hs is not None:
        res = f'{hs}-{as_}'
        winner = team_short[f['team_h']] if hs > as_ else (team_short[f['team_a']] if as_ > hs else '')
    fx_rows.append([f['id'], f.get('event') or '', f.get('kickoff_time') or '', to_local(f.get('kickoff_time')),
                    bool(f.get('started')), fin, f.get('minutes') or 0,
                    team_name[f['team_h']], team_short[f['team_h']], team_name[f['team_a']], team_short[f['team_a']],
                    fnum(hs) if hs is not None else '', fnum(as_) if as_ is not None else '',
                    res, winner, f.get('team_h_difficulty'), f.get('team_a_difficulty')])
with open(D / 'fpl_fixtures.csv', 'w', newline='', encoding='utf8') as fh:
    w = csv.writer(fh)
    w.writerow(['fixture_id','event','kickoff_utc','kickoff_local','started','finished','minutes',
                'home_team','home_short','away_team','away_short','home_score','away_score','result','winner',
                'home_difficulty','away_difficulty'])
    w.writerows(fx_rows)

# ---------- 2) fpl_player_history.csv ----------
HIST_COLS = ['element','fixture','opponent_team','total_points','was_home','kickoff_time','team_h_score',
             'team_a_score','round','modified','minutes','goals_scored','assists','clean_sheets','goals_conceded',
             'own_goals','penalties_saved','penalties_missed','yellow_cards','red_cards','saves','bonus','bps',
             'influence','creativity','threat','ict_index','clearances_blocks_interceptions','recoveries','tackles',
             'defensive_contribution','starts','expected_goals','expected_assists','expected_goal_involvements',
             'expected_goals_conceded','value','transfers_balance','selected','transfers_in','transfers_out']
hist_rows = []
for e in els:
    s = sums.get(str(e['id'])) or {}
    for h in s.get('history', []):
        row = []
        for c in HIST_COLS:
            v = h.get(c, '' if c in ('selected',) else 0)
            if v is None: v = ''
            if c in ('team_h_score', 'team_a_score') and isinstance(v, (int, float)):
                v = fnum(v)
            elif c in ('expected_goals', 'expected_assists', 'expected_goal_involvements', 'expected_goals_conceded'):
                try: v = f'{float(v):.2f}'
                except (TypeError, ValueError): v = '0.00'
            elif c in ('influence', 'creativity', 'threat', 'ict_index'):
                try: v = f'{float(v):.1f}'
                except (TypeError, ValueError): v = '0.0'
            row.append(v)
        opp = h.get('opponent_team')
        row += [e['id'], e['web_name'], team_short.get(e['team'], ''), pos_map.get(e['element_type'], ''),
                team_short.get(opp, ''), to_local(h.get('kickoff_time'))]
        hist_rows.append(row)
hist_rows.sort(key=lambda r: (r[0], r[8]))
with open(D / 'fpl_player_history.csv', 'w', newline='', encoding='utf8') as fh:
    w = csv.writer(fh)
    w.writerow(HIST_COLS + ['player_id','web_name','team_short','pos','opponent_short','kickoff_local'])
    w.writerows(hist_rows)

# ---------- 3) fpl_upcoming_player_fixtures.csv ----------
UP_COLS = ['id','code','team_h','team_h_score','team_a','team_a_score','event','finished','minutes',
           'provisional_start_time','kickoff_time','event_name','is_home','difficulty']
up_rows = []
for e in els:
    s = sums.get(str(e['id'])) or {}
    for g in s.get('fixtures', []):
        row = []
        for c in UP_COLS:
            v = g.get(c, '')
            row.append('' if v is None else v)
        opp = g['team_a'] if g.get('is_home') else g['team_h']
        row += [e['id'], e['web_name'], team_short.get(e['team'], ''), team_short.get(opp, ''),
                'H' if g.get('is_home') else 'A', to_local(g.get('kickoff_time'))]
        up_rows.append(row)
up_rows.sort(key=lambda r: (r[14], r[10] or '9999'))
with open(D / 'fpl_upcoming_player_fixtures.csv', 'w', newline='', encoding='utf8') as fh:
    w = csv.writer(fh)
    w.writerow(UP_COLS + ['player_id','web_name','team_short','opponent_short','home_away','kickoff_local'])
    w.writerows(up_rows)

# ---------- 4) fpl_players.csv ----------
finished_events = sorted([ev['id'] for ev in bs['events'] if ev.get('finished')])
gw_done = len(finished_events) or 1

# sljedeca utakmica + next5 po timu
team_fix = {tid: [] for tid in teams}
for f in sorted(fx_raw, key=lambda x: x.get('kickoff_time') or '9999'):
    if f.get('finished'):
        continue
    for side, me, opp, diff, ha in (('h', f['team_h'], f['team_a'], f['team_h_difficulty'], 'H'),
                                    ('a', f['team_a'], f['team_h'], f['team_a_difficulty'], 'A')):
        team_fix[me].append((team_short.get(opp, '?'), ha, diff, f.get('event') or 0))

def next5_str(tid):
    parts = [f'{o}({ha},{d})' for o, ha, d, _ in team_fix.get(tid, [])[:5]]
    return ' · '.join(parts)

def next_fixture(tid):
    tf = team_fix.get(tid, [])
    return f'{tf[0][0]}({tf[0][1]},{tf[0][2]})' if tf else ''

def next_fdr(tid):
    tf = team_fix.get(tid, [])
    return tf[0][2] if tf else ''

def fdr_next5(tid):
    tf = team_fix.get(tid, [])[:5]
    return round(sum(d for _, _, d, _ in tf) / len(tf), 1) if tf else ''

PCOLS = ['player_id','code','web_name','full_name','team','team_short','position','pos','price','cost_change_gw',
         'cost_change_start','price_change_percent','form','ep_next','event_points','total_points','points_per_game',
         'value_ppg_per_m','value_total_per_m','selected_by_percent','transfers_in_event','transfers_out_event',
         'transfers_balance_event','transfers_in_total','transfers_out_total','status','news','chance_next',
         'can_select','minutes_total','apps','starts','min_avg_app','min_avg_gw','min_last3','min_last5',
         'points_last3_avg','points_last5_avg','goals','assists','clean_sheets','goals_conceded','saves','bonus',
         'bps','yellow_cards','red_cards','defensive_contribution','starts_per_90','clean_sheets_per_90','xg','xa',
         'xgi','xg_per_90','xa_per_90','xgi_per_90','xgc','xgc_per_90','influence','creativity','threat','ict_index',
         'next_fixture','next_fdr','fdr_next5','next5','proj_points_est','floor_est','ceiling_est',
         'fair_price_est','price_gap_est']

def fl(v):
    try: return float(v)
    except (TypeError, ValueError): return 0.0

prows = []
for e in els:
    price = fl(e.get('now_cost')) / 10
    ccg = fl(e.get('cost_change_event')) / 10
    ccs = fl(e.get('cost_change_start')) / 10
    form = fl(e.get('form')); ep = fl(e.get('ep_next'))
    tp = e.get('total_points') or 0
    ppg = fl(e.get('points_per_game'))
    m = e.get('minutes') or 0
    hist = (sums.get(str(e['id'])) or {}).get('history', [])
    play = [h for h in hist if (h.get('minutes') or 0) > 0]
    apps = len(play)
    l3, l5 = hist[-3:], hist[-5:]
    min_l3 = round(sum(h.get('minutes') or 0 for h in l3) / (len(l3) or 1), 1)
    min_l5 = round(sum(h.get('minutes') or 0 for h in l5) / (len(l5) or 1), 1)
    pts_l3 = round(sum(h.get('total_points') or 0 for h in l3) / (len(l3) or 1), 1)
    pts_l5 = round(sum(h.get('total_points') or 0 for h in l5) / (len(l5) or 1), 1)
    xg, xa = fl(e.get('expected_goals')), fl(e.get('expected_assists'))
    xgi = round(xg + xa, 2)
    xgc = fl(e.get('expected_goals_conceded'))
    per90 = lambda v: round(v / m * 90, 2) if m else 0.0
    proj = round(form + 0.5 * ep + (0.4 if (next_fdr(e['team']) or 3) <= 2 else 0), 1)
    floor = round(proj * 0.44, 1); ceil = round(proj * 2.09, 1)
    fair = round(max(3.5, min(16.0, form + 0.5 * ep + 0.5 * pts_l5)), 1)
    vp = round(ppg / price, 2) if price else 0
    vt = round(tp / price, 2) if price else 0
    chance = e.get('chance_of_playing_next_round')
    row = {
        'player_id': e['id'], 'code': e.get('code'), 'web_name': e['web_name'],
        'full_name': f"{e.get('first_name','')} {e.get('second_name','')}".strip(),
        'team': team_name.get(e['team'], ''), 'team_short': team_short.get(e['team'], ''),
        'position': pos_full.get(e['element_type'], ''), 'pos': pos_map.get(e['element_type'], ''),
        'price': round(price, 1), 'cost_change_gw': round(ccg, 1), 'cost_change_start': round(ccs, 1),
        'price_change_percent': round(ccs / max(price - ccs, 0.1) * 100, 1) if price else 0,
        'form': form, 'ep_next': ep, 'event_points': e.get('event_points') or 0, 'total_points': tp,
        'points_per_game': ppg, 'value_ppg_per_m': vp, 'value_total_per_m': vt,
        'selected_by_percent': fl(e.get('selected_by_percent')),
        'transfers_in_event': e.get('transfers_in_event') or 0, 'transfers_out_event': e.get('transfers_out_event') or 0,
        'transfers_balance_event': (e.get('transfers_in_event') or 0) - (e.get('transfers_out_event') or 0),
        'transfers_in_total': e.get('transfers_in') or 0, 'transfers_out_total': e.get('transfers_out') or 0,
        'status': e.get('status') or '', 'news': e.get('news') or '',
        'chance_next': fl(chance) if chance is not None else 100.0,
        'can_select': bool(e.get('can_select')),
        'minutes_total': m, 'apps': apps, 'starts': e.get('starts') or 0,
        'min_avg_app': round(m / apps, 1) if apps else 0.0, 'min_avg_gw': round(m / gw_done, 1),
        'min_last3': min_l3, 'min_last5': min_l5, 'points_last3_avg': pts_l3, 'points_last5_avg': pts_l5,
        'goals': e.get('goals_scored') or 0, 'assists': e.get('assists') or 0,
        'clean_sheets': e.get('clean_sheets') or 0, 'goals_conceded': e.get('goals_conceded') or 0,
        'saves': e.get('saves') or 0, 'bonus': e.get('bonus') or 0, 'bps': e.get('bps') or 0,
        'yellow_cards': e.get('yellow_cards') or 0, 'red_cards': e.get('red_cards') or 0,
        'defensive_contribution': e.get('defensive_contribution') or 0,
        'starts_per_90': per90(e.get('starts') or 0), 'clean_sheets_per_90': per90(e.get('clean_sheets') or 0),
        'xg': xg, 'xa': xa, 'xgi': xgi,
        'xg_per_90': per90(xg), 'xa_per_90': per90(xa), 'xgi_per_90': per90(xgi),
        'xgc': xgc, 'xgc_per_90': per90(xgc),
        'influence': fl(e.get('influence')), 'creativity': fl(e.get('creativity')),
        'threat': fl(e.get('threat')), 'ict_index': fl(e.get('ict_index')),
        'next_fixture': next_fixture(e['team']), 'next_fdr': next_fdr(e['team']),
        'fdr_next5': fdr_next5(e['team']), 'next5': next5_str(e['team']),
        'proj_points_est': proj, 'floor_est': floor, 'ceiling_est': ceil,
        'fair_price_est': fair, 'price_gap_est': round(fair - price, 1),
    }
    prows.append(row)

prows.sort(key=lambda r: -r['value_ppg_per_m'])
with open(D / 'fpl_players.csv', 'w', newline='', encoding='utf8') as fh:
    w = csv.DictWriter(fh, fieldnames=PCOLS)
    w.writeheader()
    w.writerows(prows)
for c in ('fpl_players.csv', 'fpl_fixtures.csv', 'fpl_player_history.csv', 'fpl_upcoming_player_fixtures.csv'):
    (ROOT / c).write_text((D / c).read_text(encoding='utf8'), encoding='utf8')

# ---------- 5) DATA blok u premier-league-dashboard.html ----------
DB_COLS = [c for c in PCOLS if c not in ('code','team','position','price_change_percent','transfers_in_total',
           'transfers_out_total','can_select','yellow_cards','red_cards','starts_per_90','clean_sheets_per_90',
           'xgc','xgc_per_90','fair_price_est')]
def jrow(r): return {k: r[k] for k in DB_COLS}

summ = json.load(open(D / 'summary.json'))
summ['generated'] = stamp_now()
players = [jrow(r) for r in prows]
injuries = sorted(({'web_name': r['web_name'], 'team_short': r['team_short'], 'pos': r['pos'], 'price': r['price'],
                    'selected_by_percent': r['selected_by_percent'], 'status': r['status'],
                    'chance_next': r['chance_next'], 'news': r['news'], 'player_id': r['player_id']}
                   for r in prows if r['status'] != 'a'), key=lambda x: -x['selected_by_percent'])
def trow(r, key):
    return {'web_name': r['web_name'], 'team_short': r['team_short'], 'pos': r['pos'], 'price': r['price'],
            'transfers_in_event': r['transfers_in_event'], 'transfers_out_event': r['transfers_out_event'],
            'selected_by_percent': r['selected_by_percent'], 'player_id': r['player_id']}
t_in = [trow(r, 'in') for r in sorted(prows, key=lambda x: -x['transfers_in_event'])[:30]]
t_out = [trow(r, 'out') for r in sorted(prows, key=lambda x: -x['transfers_out_event'])[:30]]
pchg = ({'web_name': r['web_name'], 'team_short': r['team_short'], 'pos': r['pos'], 'price': r['price'],
         'cost_change_gw': r['cost_change_gw'], 'cost_change_start': r['cost_change_start'],
         'selected_by_percent': r['selected_by_percent'], 'player_id': r['player_id']}
        for r in prows if abs(r['cost_change_gw']) > 0.001)
pchg = sorted(pchg, key=lambda x: -abs(x['cost_change_gw']))
fixtures = [{'event': fr[1] if fr[1] != '' else None, 'kickoff_local': fr[3], 'started': fr[4], 'finished': fr[5],
             'home_short': fr[8], 'away_short': fr[10], 'result': fr[13], 'winner': fr[14],
             'home_difficulty': fr[15], 'away_difficulty': fr[16]} for fr in fx_rows]
DATA = {'summary': summ, 'players': players, 'fixtures': fixtures, 'injuries': injuries,
        'transfersIn': t_in, 'transfersOut': t_out, 'priceChanges': pchg, 'bestValue': players[:100]}

ht = (ROOT / 'premier-league-dashboard.html').read_text(encoding='utf8', errors='ignore')
m = re.search(r'(?:const|var)\s+DATA\s*=', ht)
assert m, 'DATA blok nije naden'
i = ht.index('{', m.end() - 1)
depth = 0
end = None
for j in range(i, len(ht)):
    if ht[j] == '{': depth += 1
    elif ht[j] == '}':
        depth -= 1
        if depth == 0:
            end = j + 1; break
assert end, 'DATA kraj nije naden'
new_json = json.dumps(DATA, ensure_ascii=False, separators=(',', ':'))
ht = ht[:i] + new_json + ht[end:]
# stamp u headeru, ako postoji vidljiv tekst
(ROOT / 'premier-league-dashboard.html').write_text(ht, encoding='utf8')
print('FPL BUILD OK:', len(players), 'igraca |', len(fixtures), 'fixtures | injuries', len(injuries),
      '| pchg', len(pchg), '| stamp', summ['generated'])
