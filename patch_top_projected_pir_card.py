from pathlib import Path
import json, re

ROOT = Path(__file__).resolve().parents[1]

def update_dashboard(path: Path, title_old: str, title_new: str):
    text = path.read_text(encoding='utf-8')
    m = re.search(r'const DATA=(.*?);\nconst numCols=', text, flags=re.S)
    if not m:
        raise RuntimeError(f'Could not parse DATA in {path}')
    data = json.loads(m.group(1))
    players = data.get('players', [])
    projected = sorted(
        [p for p in players if p.get('proj_pir_est') is not None and not p.get('is_injured')],
        key=lambda p: float(p.get('proj_pir_est') or -999),
        reverse=True,
    )[:12]
    data['topOptions'] = projected
    text = text[:m.start(1)] + json.dumps(data, ensure_ascii=False, separators=(',', ':')) + text[m.end(1):]
    text = text.replace(title_old, title_new)
    text = text.replace("mini('topOptions',DATA.topOptions,'name','option_score_next5','team_abbr')", "mini('topOptions',DATA.topOptions,'name','proj_pir_est','team_abbr')")
    path.write_text(text, encoding='utf-8')
    print('updated', path.name, 'top projected first:', projected[0]['name'], projected[0]['proj_pir_est'])

update_dashboard(ROOT/'euroleague-dashboard.html', 'Top option scores', 'Top Projected PIR')
update_dashboard(ROOT/'sr-euroleague-dashboard.html', 'Najbolji option score', 'Najviši Proj PIR')
update_dashboard(ROOT/'el-euroleague-dashboard.html', 'Κορυφαία option scores', 'Κορυφαίο Proj PIR')
