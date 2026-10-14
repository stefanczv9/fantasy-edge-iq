#!/usr/bin/env python3
"""EuroCup 'Real Points Allowed by Position' (DvP) - sva odigrana kola EuroCup 2026-27.

Izvori:
  * Fantaking/Dunkest EuroCup fantasy API (league 11): pozicije igraca (Guard/Forward/Center), timovi, utakmice, fantasy log
  * zvanicni EuroCup box score (euroleague_api, takmicenje 'U'): popunjava prazne vrijednosti i igrace kojih nema u fantasy logu
    (isti postupak kao scripts/patch_log_from_official_boxscore.py za EuroLeague)

Izlaz (u korijen repoa):
  eurocup-defense-vs-position.csv, eurocup-defense-vs-position-matchlog.csv
  eurocup-defense-vs-position.html, sr-..., el-...  (postojece stranice sa sajta sluze kao sablon; mijenjaju se samo podaci i tekstovi uzorka)

Pokretanje:  python3 scripts/eurocup/eurocup_dvp.py [--no-pages] [--compare-live]
Ulaz:       eurocup-players-full.csv (lista player_id; ako ga nema u repou, skida se sa sajta)
Ne dira:    index*.html, sitemap, package.json, vercel.json, EuroCup dashboard, workflow fajlove.
"""
from __future__ import annotations

import concurrent.futures as cf
import datetime
import importlib.util
import json
import re
import sys
import time
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SITE = "https://www.fantasyedgeiq.com"
BASE = "https://fantaking-api.dunkest.com/api/v1"
LEAGUE_ID = 11          # EuroCup fantasy
SEASON = 2026           # EuroCup 2026-27 (zvanicni feed: U2026)
HEADERS = {
    "origin": "https://euroleaguefantasy.euroleaguebasketball.net",
    "referer": "https://euroleaguefantasy.euroleaguebasketball.net/",
    "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
    "accept": "application/json",
}
TZ = ZoneInfo("Europe/Zagreb")
DATA_DIR = ROOT / "eurocup_fantasy_data"
POSITIONS = [("Guard", "guard"), ("Forward", "forward"), ("Center", "center")]
PAGES = {"en": "eurocup-defense-vs-position.html", "sr": "sr-eurocup-defense-vs-position.html", "el": "el-eurocup-defense-vs-position.html"}
LIVE_ROUTE = {"en": "/eurocup-defense-vs-position", "sr": "/sr-eurocup-defense-vs-position", "el": "/el-eurocup-defense-vs-position"}


def get_json(url, params=None, tries=5):
    for a in range(tries):
        try:
            r = requests.get(url, headers=HEADERS, params=params, timeout=30)
            if r.status_code == 429:
                time.sleep(2 + 2 * a)
                continue
            if r.status_code >= 400:
                return None
            return r.json()
        except Exception:
            time.sleep(0.5 + a)
    return None


def to_local(iso):
    if not iso:
        return None
    try:
        return datetime.datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(TZ).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return iso


def player_ids():
    p = ROOT / "eurocup-players-full.csv"
    if p.exists():
        ids = pd.read_csv(p, usecols=["player_id"])["player_id"]
    else:
        r = requests.get(SITE + "/eurocup-players-full.csv", timeout=60)
        r.raise_for_status()
        p.write_bytes(r.content)
        ids = pd.read_csv(p, usecols=["player_id"])["player_id"]
    return sorted({int(x) for x in ids.dropna()})


def fetch_profiles(ids):
    def one(pid):
        js = get_json(f"{BASE}/players/{pid}/profile", {"league": LEAGUE_ID})
        d = (js or {}).get("data") or {}
        if not d.get("team") or not d.get("position"):
            return None
        return {"player_id": pid, "name": f"{d.get('first_name') or ''} {d.get('last_name') or ''}".strip(),
                "position": d["position"]["name"], "team_abbr": d["team"]["abbreviation"], "team_id": d["team"]["id"],
                "credits": d.get("quotation")}
    with cf.ThreadPoolExecutor(20) as ex:
        rows = [r for r in ex.map(one, ids) if r]
    return pd.DataFrame(rows)


def build_log(config, players):
    sid = config["current_schedule_id"]
    cur = config["current_matchday"]["number"]
    mds = [m for m in config["matchdays"] if m["number"] <= cur]
    matches = []
    for md in mds:
        js = get_json(f"{BASE}/schedules/{sid}/matchdays/{md['id']}")
        data = (js or {}).get("data") or {}
        for rnd in data.get("rounds", []):
            for m in rnd.get("matches", []):
                matches.append({"matchday_id": md["id"], "matchday": md["number"], "match_id": m["id"], "status": m.get("status")})
    mt = pd.DataFrame(matches)
    played_mds = sorted(mt[mt["status"] == "played"]["matchday"].unique())
    md_by_num = {m["number"]: m for m in mds}
    tasks = [(int(p.player_id), md_by_num[n]) for p in players.itertuples() for n in played_mds]

    def one(t):
        pid, md = t
        js = get_json(f"{BASE}/players/{pid}/fantasy-pts", {"league": LEAGUE_ID, "matchday": md["id"]})
        return pid, md, ((js or {}).get("data") or {})
    rows = []
    with cf.ThreadPoolExecutor(20) as ex:
        results = list(ex.map(one, tasks))
    info = players.set_index("player_id")
    for pid, md, d in results:
        match = d.get("match") or {}
        if not match:
            continue
        home, away = match.get("home_team") or {}, match.get("away_team") or {}
        team_abbr = info.at[pid, "team_abbr"]
        team_id = info.at[pid, "team_id"]
        if home.get("id") == team_id or home.get("abbreviation") == team_abbr:
            ha, opp, ts, os_ = "H", away, home.get("score"), away.get("score")
        elif away.get("id") == team_id or away.get("abbreviation") == team_abbr:
            ha, opp, ts, os_ = "A", home, away.get("score"), home.get("score")
        else:      # igrac je u medjuvremenu promijenio tim - utakmica nije njegova
            continue
        stats = {i.get("name"): i.get("value") for i in (d.get("stats_items") or [])}
        row = {"player_id": pid, "matchday_id": md["id"], "matchday": md["number"], "match_id": match.get("id"),
               "match_status": match.get("status"), "start_utc": match.get("started_at"), "start_local": to_local(match.get("started_at")),
               "home_abbr": home.get("abbreviation"), "away_abbr": away.get("abbreviation"), "home_score": home.get("score"),
               "away_score": away.get("score"), "home_away": ha, "opponent_abbr": opp.get("abbreviation"), "opponent_name": opp.get("name"),
               "team_score": ts, "opponent_score": os_, "fantasy_pts": d.get("fantasy_pts"), "label": d.get("label")}
        row.update(stats)
        rows.append(row)
    log = pd.DataFrame(rows)
    log = log.merge(players[["player_id", "name", "position", "team_abbr", "credits"]], on="player_id", how="left")
    for c in ["pts", "reb", "ast", "stl", "blk", "tov", "fd", "pf", "fg_missed", "ft_missed"]:
        if c not in log.columns:
            log[c] = pd.NA
    return log


def official_patch(log_path: Path):
    """Isti postupak kao za EuroLeague, ali nad zvanicnim EuroCup feedom ('U')."""
    spec = importlib.util.spec_from_file_location("plb", ROOT / "scripts" / "patch_log_from_official_boxscore.py")
    plb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(plb)
    plb.LOG_PATH = log_path
    plb.SEASON = SEASON
    import euroleague_api.game_stats as gsmod
    Orig = gsmod.GameStats
    gsmod.GameStats = lambda comp="E": Orig("U")
    try:
        plb.main()
    finally:
        gsmod.GameStats = Orig


def compute_dvp(log: pd.DataFrame, team_names: dict):
    for c in ["pts", "reb", "ast", "stl", "blk", "tov"]:
        log[c] = pd.to_numeric(log.get(c, 0), errors="coerce").fillna(0)
    log["team_score"] = pd.to_numeric(log["team_score"], errors="coerce")
    log = log[(log["match_status"] == "played") & log["opponent_abbr"].notna() & log["team_abbr"].notna()
              & log["position"].isin([p[0] for p in POSITIONS])]
    rows = []
    for (match_id, defense, offense), g in log.groupby(["match_id", "opponent_abbr", "team_abbr"], dropna=True):
        row = {"match_id": int(match_id), "team_abbr": defense, "opponent_abbr": offense}
        for c in ["home_abbr", "away_abbr", "start_local", "team_score", "opponent_score"]:
            row[c] = g[c].iloc[0]
        row["box_score_pts_allowed"] = float(g["team_score"].iloc[0])
        for pos, key in POSITIONS:
            pg = g[g["position"] == pos]
            row[f"{key}_pts_allowed"] = float(pg["pts"].sum())
            row[f"{key}_reb_allowed"] = float(pg["reb"].sum())
            row[f"{key}_ast_allowed"] = float(pg["ast"].sum())
            row[f"{key}_stl_allowed"] = float(pg["stl"].sum())
            row[f"{key}_blk_allowed"] = float(pg["blk"].sum())
            row[f"{key}_tov_forced"] = float(pg["tov"].sum())
        row["position_pts_allowed"] = sum(row[f"{k}_pts_allowed"] for _, k in POSITIONS)
        row["unclassified_pts_allowed"] = max(0.0, row["box_score_pts_allowed"] - row["position_pts_allowed"])
        row["validation_diff"] = row["position_pts_allowed"] - row["box_score_pts_allowed"]
        row["validation_ok"] = abs(row["validation_diff"]) <= 0.1
        rows.append(row)
    match = pd.DataFrame(rows).sort_values(["match_id", "team_abbr"]).reset_index(drop=True)
    ml_cols = ["match_id", "team_abbr", "opponent_abbr", "home_abbr", "away_abbr", "start_local", "team_score", "opponent_score", "box_score_pts_allowed"]
    for _, k in POSITIONS:
        ml_cols += [f"{k}_pts_allowed", f"{k}_reb_allowed", f"{k}_ast_allowed", f"{k}_stl_allowed", f"{k}_blk_allowed", f"{k}_tov_forced"]
    ml_cols += ["position_pts_allowed", "unclassified_pts_allowed", "validation_diff", "validation_ok"]
    match = match[ml_cols]

    agg = match.groupby("team_abbr").agg(games_sample=("match_id", "nunique"),
                                         box_total=("box_score_pts_allowed", "sum"), pos_total=("position_pts_allowed", "sum"),
                                         uncl_total=("unclassified_pts_allowed", "sum"), diff_total=("validation_diff", "sum")).reset_index()
    for _, k in POSITIONS:
        for metric in ["pts_allowed", "reb_allowed", "ast_allowed", "stl_allowed", "blk_allowed", "tov_forced"]:
            col = f"{k}_{metric}"
            s = match.groupby("team_abbr")[col].sum().reset_index(name=col + "_t")
            agg = agg.merge(s, on="team_abbr", how="left")
            agg[col + "_pg"] = agg[col + "_t"] / agg["games_sample"]
    g = agg["games_sample"]
    agg["box_score_pts_allowed_pg"] = agg["box_total"] / g
    agg["position_pts_allowed_pg"] = agg["pos_total"] / g
    agg["unclassified_pts_allowed_pg"] = agg["uncl_total"] / g
    agg["validation_diff_pg"] = agg["diff_total"] / g
    agg["validation_ok"] = agg["diff_total"].abs() <= 0.1
    agg["sample_confidence"] = np.select([g < 2, g < 5, g < 10], ["very low", "low", "medium"], default="high")
    agg["team_name"] = agg["team_abbr"].map(team_names).fillna(agg["team_abbr"])

    def fdr(s):
        s = pd.to_numeric(s, errors="coerce")
        if s.notna().sum() < 2 or float(s.max()) == float(s.min()):
            return pd.Series([3.0] * len(s), index=s.index)
        return 1 + 4 * ((s.max() - s) / (s.max() - s.min()))
    for _, k in POSITIONS:
        agg[f"{k}_real_pts_fdr_1_easy_5_hard"] = fdr(agg[f"{k}_pts_allowed_pg"]).round(2)
    ordered = ["team_abbr", "team_name", "games_sample", "sample_confidence", "validation_ok", "validation_diff_pg",
               "box_score_pts_allowed_pg", "position_pts_allowed_pg", "unclassified_pts_allowed_pg"]
    for _, k in POSITIONS:
        ordered += [f"{k}_pts_allowed_pg", f"{k}_real_pts_fdr_1_easy_5_hard", f"{k}_reb_allowed_pg", f"{k}_ast_allowed_pg",
                    f"{k}_stl_allowed_pg", f"{k}_blk_allowed_pg", f"{k}_tov_forced_pg"]
    agg = agg[ordered].copy()
    for c in agg.columns:
        if pd.api.types.is_float_dtype(agg[c]):
            agg[c] = agg[c].round(2)
    agg = agg.sort_values(["guard_pts_allowed_pg", "team_abbr"], ascending=[False, True]).reset_index(drop=True)
    return match, agg


# ---------------------------------------------------------------------------------------------- stranice
TXT = {
    "en": {"desc": "Real points allowed to guards, forwards and centers. Sample: EuroCup rounds 1-{k} ({n} games).",
           "note": "Real points only. Guard + Forward + Center points are validated against box-score points allowed. Small sample: {k} EuroCup rounds ({n} games) so far."},
    "sr": {"desc": "Realni poeni primljeni od bekova, krila i centara. Uzorak: EuroCup kola 1-{k} ({n} utakmica).",
           "note": "Samo realni poeni. Poeni bekova + krila + centara validiraju se u odnosu na box-score poene koje je ekipa primila. Mali uzorak: {k} EuroCup kola ({n} utakmica) do sada."},
    "el": {"desc": "Πραγματικοί πόντοι που δέχεται κάθε ομάδα από guards, forwards και centers. Δείγμα: γύροι 1-{k} του EuroCup ({n} αγώνες).",
           "note": "Μόνο πραγματικοί πόντοι. Οι πόντοι Guards + Forwards + Centers επικυρώνονται με τους πόντους του box score. Μικρό δείγμα: {k} γύροι EuroCup ({n} αγώνες) μέχρι τώρα."},
}


def template_html(lang):
    p = ROOT / PAGES[lang]
    if p.exists():
        return p.read_text(encoding="utf-8")
    r = requests.get(SITE + LIVE_ROUTE[lang], timeout=60)
    r.raise_for_status()
    return r.text


def build_pages(agg, k, n, stamp):
    rows = json.loads(agg.to_json(orient="records"))
    arr = json.dumps(rows, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    for lang, fn in PAGES.items():
        t = template_html(lang)
        tag = "const DATA={summary:"
        i = t.find(tag)
        if i < 0:
            raise SystemExit(f"{fn}: nema 'const DATA={{summary:' u sablonu")
        a = i + len(tag)
        _, end = json.JSONDecoder().raw_decode(t[a:])
        t = t[:a] + arr + t[a + end:]
        desc = TXT[lang]["desc"].format(k=k, n=n)
        note = TXT[lang]["note"].format(k=k, n=n)
        t = re.sub(r'(<meta name="description" content=")[^"]*(")', lambda m: m.group(1) + desc + m.group(2), t, count=1)
        t = re.sub(r'(<div class="sub">)(.*?)( Generated: <b>)[^<]*(</b></div>)', lambda m: m.group(1) + desc + m.group(3) + stamp + m.group(4), t, count=1, flags=re.S)
        t = re.sub(r'(<div class="note">)(.*?)(</div>)', lambda m: m.group(1) + note + m.group(3), t, count=1, flags=re.S)
        (ROOT / fn).write_text(t, encoding="utf-8")
        print(f"{fn}: {len(t) // 1024} KB | {len(rows)} timova | generated {stamp}")


def main():
    now = datetime.datetime.now(TZ)
    stamp = now.strftime("%Y-%m-%d %H:%M ") + ("CEST" if now.dst() else "CET")
    DATA_DIR.mkdir(exist_ok=True)
    if "--pages-only" in sys.argv:       # samo stranice iz vec izracunatih CSV-ova
        agg = pd.read_csv(ROOT / "eurocup-defense-vs-position.csv")
        match = pd.read_csv(ROOT / "eurocup-defense-vs-position-matchlog.csv")
        log = pd.read_csv(DATA_DIR / "fantasy_poeni_log.csv", usecols=["match_status", "matchday"])
        build_pages(agg, int(log[log.match_status.eq("played")]["matchday"].max()), int(match["match_id"].nunique()), stamp)
        return
    cfg = (get_json(f"{BASE}/leagues/{LEAGUE_ID}/config") or {}).get("data")
    if not cfg:
        raise SystemExit("EuroCup fantasy config nije dostupan")
    team_names = {t["abbreviation"]: t["name"] for t in cfg["teams"]}
    ids = player_ids()
    print(f"EuroCup: {len(cfg['teams'])} timova | trenutni MD {cfg['current_matchday']['number']} | igraca u listi: {len(ids)}")
    players = fetch_profiles(ids)
    print(f"profila sa timom/pozicijom: {len(players)}")
    log = build_log(cfg, players)
    log_path = DATA_DIR / "fantasy_poeni_log.csv"
    log.to_csv(log_path, index=False)
    print(f"fantasy log: {len(log)} redova | odigrane utakmice: {log[log.match_status.eq('played')].match_id.nunique()}")
    official_patch(log_path)
    log = pd.read_csv(log_path)
    match, agg = compute_dvp(log, team_names)
    match.to_csv(ROOT / "eurocup-defense-vs-position-matchlog.csv", index=False)
    agg.to_csv(ROOT / "eurocup-defense-vs-position.csv", index=False)
    n = int(match["match_id"].nunique())
    k = int(log[log.match_status.eq("played")]["matchday"].max())
    bad = agg[~agg["validation_ok"]]
    print(f"DvP: {len(agg)} timova | {n} utakmica | kola 1-{k} | validirano {int(agg['validation_ok'].sum())}/{len(agg)}"
          + (f" | NE PROLAZI: {list(bad.team_abbr)}" if len(bad) else ""))
    if "--no-pages" not in sys.argv:
        build_pages(agg, k, n, stamp)


if __name__ == "__main__":
    main()
