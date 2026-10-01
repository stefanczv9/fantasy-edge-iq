from __future__ import annotations

import json
import math
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "euroleague_fantasy_data"
TZ = ZoneInfo("Europe/Zagreb")
STAMP = datetime.now(TZ).strftime("%Y-%m-%d %H:%M %Z")

DASHBOARDS = {
    "euroleague-dashboard.html": ("Top option scores", "Top Projected PIR"),
    "sr-euroleague-dashboard.html": ("Najbolji option score", "Najviši Proj PIR"),
    "el-euroleague-dashboard.html": ("Κορυφαία option scores", "Κορυφαίο Proj PIR"),
}


def _json_default(v):
    try:
        if pd.isna(v):
            return None
    except Exception:
        pass
    if hasattr(v, "item"):
        return v.item()
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    return v


def update_dashboard(path: Path, old_title: str, new_title: str) -> None:
    text = path.read_text(encoding="utf-8")
    m = re.search(r"const DATA=(.*?);\nconst numCols=", text, flags=re.S)
    if not m:
        raise RuntimeError(f"Could not parse DATA in {path}")
    data = json.loads(m.group(1))
    data["generated"] = STAMP
    players = data.get("players", [])
    projected = sorted(
        [p for p in players if p.get("proj_pir_est") is not None and not p.get("is_injured")],
        key=lambda p: float(p.get("proj_pir_est") or -999),
        reverse=True,
    )[:12]
    if projected:
        data["topOptions"] = projected
    new_json = json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=_json_default)
    text = text[: m.start(1)] + new_json + text[m.end(1) :]
    text = text.replace(old_title, new_title)
    text = text.replace(
        "mini('topOptions',DATA.topOptions,'name','option_score_next5','team_abbr')",
        "mini('topOptions',DATA.topOptions,'name','proj_pir_est','team_abbr')",
    )
    path.write_text(text, encoding="utf-8")
    print("final dashboard", path.name, STAMP, projected[0]["name"] if projected else "no players")


def update_team_analyzer() -> None:
    path = ROOT / "euroleague-team-analyzer.html"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    m = re.search(r"const DATA=(.*?);let selected=", text, flags=re.S)
    if not m:
        # Older files have a newline before let selected.
        m = re.search(r"const DATA=(.*?);\nlet selected=", text, flags=re.S)
    if not m:
        print("team analyzer DATA not found; skipped")
        return
    data = json.loads(m.group(1))
    data["generated"] = STAMP
    text = text[: m.start(1)] + json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=_json_default) + text[m.end(1) :]
    path.write_text(text, encoding="utf-8")
    print("final team analyzer", STAMP)


def sample_label() -> tuple[int | None, int | None]:
    played_games = None
    max_matchday = None
    matches = DATA_DIR / "utakmice.csv"
    if matches.exists():
        m = pd.read_csv(matches)
        if "status" in m.columns:
            played = m[m["status"].eq("played")]
            played_games = int(len(played))
            if "matchday" in played.columns and not played.empty:
                max_matchday = int(pd.to_numeric(played["matchday"], errors="coerce").max())
    if played_games is None:
        csv = ROOT / "euroleague-defense-vs-position.csv"
        if csv.exists():
            d = pd.read_csv(csv)
            if "games_sample" in d.columns:
                played_games = int(pd.to_numeric(d["games_sample"], errors="coerce").fillna(0).sum() / 2)
    return played_games, max_matchday


def update_dvp_page(filename: str, message: str) -> None:
    path = ROOT / filename
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    text = re.sub(r'<div class="dvp-generated"[^>]*>.*?</div>', "", text)
    repl = r'\g<0><div class="dvp-generated" style="margin-top:8px;color:#aabbd2;font-size:13px;font-weight:800">' + message + "</div>"
    text, n = re.subn(r'<div class="sub">[^<]*</div>', repl, text, count=1)
    if n != 1:
        raise RuntimeError(f"Could not insert DvP generated label in {filename}")
    path.write_text(text, encoding="utf-8")
    print("final dvp", filename, message)


def main() -> None:
    for filename, titles in DASHBOARDS.items():
        update_dashboard(ROOT / filename, *titles)
    update_team_analyzer()

    played_games, max_matchday = sample_label()
    if played_games and max_matchday:
        en_sample = f"Sample: {played_games} completed games, Matchdays 1–{max_matchday}"
        sr_sample = f"Uzorak: {played_games} odigranih utakmica, kola 1–{max_matchday}"
        el_sample = f"Δείγμα: {played_games} ολοκληρωμένοι αγώνες, αγωνιστικές 1–{max_matchday}"
    elif played_games:
        en_sample = f"Sample: {played_games} completed games"
        sr_sample = f"Uzorak: {played_games} odigranih utakmica"
        el_sample = f"Δείγμα: {played_games} ολοκληρωμένοι αγώνες"
    else:
        en_sample = "Sample: completed EuroLeague games"
        sr_sample = "Uzorak: odigrane EuroLeague utakmice"
        el_sample = "Δείγμα: ολοκληρωμένοι αγώνες EuroLeague"

    update_dvp_page("euroleague-defense-vs-position.html", f"Generated: {STAMP} · {en_sample}")
    update_dvp_page("sr-euroleague-defense-vs-position.html", f"Ažurirano: {STAMP} · {sr_sample}")
    update_dvp_page("el-euroleague-defense-vs-position.html", f"Ενημέρωση: {STAMP} · {el_sample}")

    (ROOT / "BUILD_VERSION.txt").write_text(
        "Fantasy Edge IQ EuroLeague auto-refresh\n"
        f"Generated: {STAMP}\n"
        "Dashboard: current prices/next opponents; Top Projected PIR uses proj_pir_est.\n"
        f"DvP: real-points-only by Guard/Forward/Center; {en_sample}.\n"
        "No EuroCup site routes/files included.\n",
        encoding="utf-8",
    )
    print("final BUILD_VERSION", STAMP)


if __name__ == "__main__":
    main()
