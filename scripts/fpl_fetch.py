#!/usr/bin/env python3
"""FPL refresh: bootstrap-static + fixtures (svih 380) + element-summary po igracu + summary.json"""
import json, time, sys
import concurrent.futures as cf
import urllib.request
from pathlib import Path

D = Path(__file__).resolve().parents[1] / 'fpl_fantasy_data'
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64) AppleWebKit/537.36 Chrome/120 Safari/537.36',
      'Accept': 'application/json'}

def get(url, tries=4):
    for a in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:
            if a == tries - 1:
                print('FAIL', url, e, flush=True)
                return None
            time.sleep(1.2 * (a + 1))

bs = get('https://fantasy.premierleague.com/api/bootstrap-static/')
assert bs and 'elements' in bs, 'bootstrap-static nije skinut'
print('bootstrap OK: elements', len(bs['elements']), 'events', len(bs['events']), flush=True)

fx = get('https://fantasy.premierleague.com/api/fixtures/') or []
print('fixtures direktan:', len(fx), flush=True)
if len(fx) < 380:
    seen = {f['id'] for f in fx} if fx and isinstance(fx[0], dict) and 'id' in fx[0] else set()
    allfx = list(fx)
    for gw in range(1, 39):
        part = get(f'https://fantasy.premierleague.com/api/fixtures/?event={gw}') or []
        for f in part:
            if f.get('id') not in seen:
                seen.add(f.get('id')); allfx.append(f)
    fx = allfx
    print('fixtures po gw-ovima:', len(fx), flush=True)

ids = [e['id'] for e in bs['elements']]
def fetch_sum(i):
    return i, get(f'https://fantasy.premierleague.com/api/element-summary/{i}/', tries=3)
summaries = {}
t0 = time.time()
with cf.ThreadPoolExecutor(max_workers=8) as ex:
    for n, (i, v) in enumerate(ex.map(fetch_sum, ids)):
        if v: summaries[str(i)] = v
        if n % 200 == 0: print(f'  summaries {n}/{len(ids)} ({time.time()-t0:.0f}s)', flush=True)
missing = [i for i in ids if str(i) not in summaries]
if missing:
    print('retry', len(missing), 'missing', flush=True)
    with cf.ThreadPoolExecutor(max_workers=4) as ex:
        for i, v in ex.map(fetch_sum, missing):
            if v: summaries[str(i)] = v
print('summaries gotovo:', len(summaries), '/', len(ids), flush=True)
assert len(summaries) >= len(ids) * 0.95, 'previse summaries failed'

json.dump(bs, open(D / 'bootstrap_static.json', 'w'))
json.dump(fx, open(D / 'fixtures_raw.json', 'w'))
json.dump(summaries, open(D / 'element_summaries.json', 'w'))

ev = {e['id']: e for e in bs['events']}
cur = next((e for e in bs['events'] if e.get('is_current')), None)
nxt = next((e for e in bs['events'] if e.get('is_next')), None)
prev = next((e for e in bs['events'] if e.get('is_previous')), None)
els = bs['elements']
top_el = max(els, key=lambda e: e.get('event_points') or 0)
most_sel = max(els, key=lambda e: float(e.get('selected_by_percent') or 0))
most_ti = max(els, key=lambda e: e.get('transfers_in_event') or 0)
from datetime import datetime
from zoneinfo import ZoneInfo
now = datetime.now(ZoneInfo('Europe/Zagreb'))
stamp = now.strftime('%Y-%m-%d %H:%M ') + ('CEST' if now.dst() else 'CET')
old = json.load(open(D / 'summary.json')) if (D / 'summary.json').exists() else {}
summary = {
    'generated': stamp,
    'total_fpl_managers': old.get('total_fpl_managers'),
    'current_gw': cur['id'] if cur else (prev['id'] if prev else None),
    'current_gw_name': f"Gameweek {cur['id']}" if cur else None,
    'current_avg_score': cur.get('average_entry_score') if cur else None,
    'current_highest_score': cur.get('highest_score') if cur else None,
    'next_gw': nxt['id'] if nxt else None,
    'next_deadline_utc': nxt.get('deadline_time') if nxt else None,
    'next_deadline_local': (datetime.fromisoformat(nxt['deadline_time'].replace('Z', '+00:00')).astimezone(ZoneInfo('Europe/Zagreb')).strftime('%Y-%m-%d %H:%M')) if nxt and nxt.get('deadline_time') else None,
    'previous_gw': prev['id'] if prev else None,
    'top_element': top_el['web_name'],
    'top_element_points': top_el.get('event_points'),
    'most_selected': most_sel['web_name'],
    'most_transferred_in': most_ti['web_name'],
    'most_captained': old.get('most_captained', most_sel['web_name']),
    'transfers_made_current': (cur or {}).get('transfers_made', old.get('transfers_made_current')),
    'players_count': len(els),
    'fixtures_count': len(fx),
}
json.dump(summary, open(D / 'summary.json', 'w'), ensure_ascii=False, indent=2)
print('FPL FETCH DONE', json.dumps({k: summary[k] for k in ('generated','current_gw','next_gw','previous_gw','fixtures_count')}), flush=True)
