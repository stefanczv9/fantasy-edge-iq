import asyncio
import aiohttp
import json
import math
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
from rapidfuzz import process, fuzz

BASE = "https://fantaking-api.dunkest.com/api/v1"
HEADERS = {
    "origin": "https://euroleaguefantasy.euroleaguebasketball.net",
    "referer": "https://euroleaguefantasy.euroleaguebasketball.net/",
    "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
    "accept": "application/json",
}
LEAGUE_ID = 10
SEASON = 2026
LOCAL_TZ = ZoneInfo("Europe/Zagreb")
NOW_LOCAL = datetime.now(LOCAL_TZ)
NOW_UTC = NOW_LOCAL.astimezone(timezone.utc)
ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "euroleague_fantasy_data"
OUT_DIR.mkdir(exist_ok=True)


def get_json_sync(url, params=None):
    import requests
    r = requests.get(url, headers=HEADERS, params=params, timeout=40)
    r.raise_for_status()
    return r.json()


async def fetch_json(session, url, params=None, tries=3):
    for attempt in range(tries):
        try:
            async with session.get(url, headers=HEADERS, params=params, timeout=aiohttp.ClientTimeout(total=25)) as resp:
                txt = await resp.text()
                if resp.status == 429:
                    await asyncio.sleep(2 + attempt * 3)
                    continue
                if resp.status >= 400:
                    return None
                return json.loads(txt)
        except Exception:
            if attempt == tries - 1:
                return None
            await asyncio.sleep(0.5 + attempt)
    return None


async def fetch_many(urls, concurrency=25):
    sem = asyncio.Semaphore(concurrency)
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=concurrency)) as session:
        async def _one(key_url):
            key, url, params = key_url
            async with sem:
                return key, await fetch_json(session, url, params=params)
        return await asyncio.gather(*[_one(u) for u in urls])


def to_local(iso):
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.astimezone(LOCAL_TZ).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return iso


def parse_dt_utc(iso):
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def flatten_schedule(config):
    schedule_id = config["current_schedule_id"]
    urls = []
    for md in config["matchdays"]:
        urls.append((md["id"], f"{BASE}/schedules/{schedule_id}/matchdays/{md['id']}", None))
    results = asyncio.run(fetch_many(urls, concurrency=15))
    matches = []
    raw = {}
    for md_id, js in results:
        if not js or "data" not in js:
            continue
        data = js["data"]
        raw[md_id] = data
        for rnd in data.get("rounds", []):
            for m in rnd.get("matches", []):
                home = m.get("home_team") or {}
                away = m.get("away_team") or {}
                hs, aw = home.get("score"), away.get("score")
                winner = None
                if hs is not None and aw is not None:
                    if hs > aw:
                        winner = home.get("abbreviation")
                    elif aw > hs:
                        winner = away.get("abbreviation")
                    else:
                        winner = "TIE"
                matches.append({
                    "matchday_id": data.get("id"),
                    "matchday": data.get("number"),
                    "round_id": rnd.get("id"),
                    "round": rnd.get("number"),
                    "match_id": m.get("id"),
                    "status": m.get("status"),
                    "ot": m.get("ot"),
                    "start_utc": m.get("started_at"),
                    "start_local": to_local(m.get("started_at")),
                    "home_team_id": home.get("id"),
                    "home_team": home.get("name"),
                    "home_abbr": home.get("abbreviation"),
                    "home_score": hs,
                    "away_team_id": away.get("id"),
                    "away_team": away.get("name"),
                    "away_abbr": away.get("abbreviation"),
                    "away_score": aw,
                    "winner": winner,
                    "result": "" if hs is None or aw is None else f"{hs}-{aw}",
                })
    return pd.DataFrame(matches).sort_values(["matchday", "round", "start_utc", "match_id"]), raw


def profiles_df_from_json(path):
    profiles = json.load(open(path, encoding="utf-8"))
    rows = []
    for p in profiles:
        rows.append({
            "player_id": p.get("id"),
            "first_name": p.get("first_name"),
            "last_name": p.get("last_name"),
            "name": (str(p.get("first_name") or "") + " " + str(p.get("last_name") or "")).strip(),
            "position": (p.get("position") or {}).get("name"),
            "position_id": (p.get("position") or {}).get("id"),
            "team": (p.get("team") or {}).get("name"),
            "team_abbr": (p.get("team") or {}).get("abbreviation"),
            "team_id": (p.get("team") or {}).get("id"),
            "jersey": p.get("jersey"),
            "credits": p.get("quotation"),
            "avg_fantasy_pts_api": p.get("avg_fantasy_pts"),
            "total_plus": p.get("total_plus"),
            "popularity_pct": None if p.get("popularity") is None else round(p.get("popularity") * 100, 2),
            "is_on_fire": p.get("is_on_fire"),
            "is_injured": p.get("is_injured"),
            "started_from_bench": p.get("started_from_bench"),
            "face_path": p.get("face_path"),
        })
    df = pd.DataFrame(rows)
    return df.sort_values(["position", "team_abbr", "credits", "name"], ascending=[True, True, False, True])


async def fetch_fantasy_logs(players_df, matchdays):
    urls = []
    for _, p in players_df.iterrows():
        for md in matchdays:
            urls.append(((int(p.player_id), int(md["id"]), int(md["number"]), p.team_abbr, p.team_id),
                         f"{BASE}/players/{int(p.player_id)}/fantasy-pts",
                         {"league": LEAGUE_ID, "matchday": int(md["id"])}))
    results = await fetch_many(urls, concurrency=30)
    logs = []
    for key, js in results:
        player_id, md_id, md_num, team_abbr, team_id = key
        if not js or "data" not in js:
            continue
        d = js["data"] or {}
        match = d.get("match") or {}
        home = match.get("home_team") or {}
        away = match.get("away_team") or {}
        ha = None
        opponent_abbr = None
        opponent_name = None
        team_score = None
        opp_score = None
        if home.get("id") == team_id or home.get("abbreviation") == team_abbr:
            ha = "H"
            opponent_abbr = away.get("abbreviation")
            opponent_name = away.get("name")
            team_score, opp_score = home.get("score"), away.get("score")
        elif away.get("id") == team_id or away.get("abbreviation") == team_abbr:
            ha = "A"
            opponent_abbr = home.get("abbreviation")
            opponent_name = home.get("name")
            team_score, opp_score = away.get("score"), home.get("score")
        stats = {item.get("name"): item.get("value") for item in (d.get("stats_items") or [])}
        stats_fp = {"fp_" + str(item.get("name")): item.get("fantasy_pts") for item in (d.get("stats_items") or [])}
        row = {
            "player_id": player_id,
            "matchday_id": md_id,
            "matchday": md_num,
            "round_id": (d.get("round") or {}).get("id"),
            "round": (d.get("round") or {}).get("number"),
            "match_id": match.get("id"),
            "match_status": match.get("status"),
            "start_utc": match.get("started_at"),
            "start_local": to_local(match.get("started_at")),
            "home_abbr": home.get("abbreviation"),
            "away_abbr": away.get("abbreviation"),
            "home_score": home.get("score"),
            "away_score": away.get("score"),
            "home_away": ha,
            "opponent_abbr": opponent_abbr,
            "opponent_name": opponent_name,
            "team_score": team_score,
            "opponent_score": opp_score,
            "fantasy_pts": d.get("fantasy_pts"),
            "label": d.get("label"),
        }
        row.update(stats)
        row.update(stats_fp)
        logs.append(row)
    return pd.DataFrame(logs)


def add_next_matches(players_df, matches_df):
    future = matches_df.copy()
    future["dt_utc"] = future["start_utc"].map(parse_dt_utc)
    future = future[(future["dt_utc"].notna()) & (future["dt_utc"] >= NOW_UTC) & (future["status"].isin(["scheduled", "playing", "pre-game"]))]
    out = {}
    for abbr in pd.concat([future["home_abbr"], future["away_abbr"]]).dropna().unique():
        team_matches = future[(future.home_abbr == abbr) | (future.away_abbr == abbr)].sort_values("dt_utc")
        if team_matches.empty:
            continue
        m = team_matches.iloc[0]
        ha = "H" if m.home_abbr == abbr else "A"
        opp = m.away_abbr if ha == "H" else m.home_abbr
        out[abbr] = {
            "next_matchday": m.matchday,
            "next_start_local": m.start_local,
            "next_home_away": ha,
            "next_opponent": opp,
            "next_match": f"{m.home_abbr} - {m.away_abbr}",
        }
    next_df = pd.DataFrame.from_dict(out, orient="index").reset_index().rename(columns={"index":"team_abbr"})
    return players_df.merge(next_df, on="team_abbr", how="left")


def norm_name(s):
    s = str(s or "")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = s.lower()
    s = re.sub(r"\b(jr|jr\.|iii|ii|iv)\b", "", s)
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    return s


def official_name_to_full(n):
    # "LAST, FIRST" -> "first last"
    n = str(n or "")
    if "," in n:
        last, first = n.split(",", 1)
        return f"{first.strip()} {last.strip()}".title()
    return n.title()


def fetch_official_stats():
    try:
        from euroleague_api.player_stats import PlayerStats
        ps = PlayerStats("E")
        # For the fresh 2026/27 season the public API currently returns traditional
        # stats only when phaseTypeCode=RS is supplied, while advanced/misc work
        # more reliably without phase filtering. Keep this defensive.
        trad = ps.get_player_stats_single_season("traditional", SEASON, phase_type_code="RS", statistic_mode="Accumulated")
        adv = ps.get_player_stats_single_season("advanced", SEASON, phase_type_code=None, statistic_mode="PerGame")
        misc = ps.get_player_stats_single_season("misc", SEASON, phase_type_code=None, statistic_mode="PerGame")
    except Exception as e:
        print("Official stats fetch failed:", e)
        return pd.DataFrame()
    if trad.empty:
        return pd.DataFrame()
    # Keep useful advanced/misc columns and avoid repeated player/team cols.
    idcol = "player.code"
    df = trad.copy()
    if not adv.empty and idcol in adv.columns:
        adv_cols = [idcol] + [c for c in adv.columns if c not in trad.columns and not c.startswith("player.") and not c.startswith("player.team.")]
        df = df.merge(adv[adv_cols], on=idcol, how="left")
    if not misc.empty and idcol in misc.columns:
        misc_cols = [idcol] + [c for c in misc.columns if c not in trad.columns and not c.startswith("player.") and not c.startswith("player.team.")]
        df = df.merge(misc[misc_cols], on=idcol, how="left")
    df["official_name_full"] = df["player.name"].map(official_name_to_full)
    df["official_team_abbr"] = df.get("player.team.tvCodes")
    # Per-game calculated from accumulated traditional stats.
    gp = df["gamesPlayed"].replace({0: pd.NA})
    for col, new in [
        ("minutesPlayed", "min_pg"), ("pointsScored", "pts_pg"), ("totalRebounds", "reb_pg"),
        ("assists", "ast_pg"), ("steals", "stl_pg"), ("turnovers", "tov_pg"),
        ("blocks", "blk_pg"), ("pir", "pir_pg")
    ]:
        if col in df.columns:
            df[new] = (df[col] / gp).round(2)
    return df


def fuzzy_attach_prices(official_df, players_df):
    if official_df.empty:
        return official_df
    players_df = players_df.copy()
    players_df["norm"] = players_df["name"].map(norm_name)
    official_df = official_df.copy()
    official_df["norm"] = official_df["official_name_full"].map(norm_name)
    # Index fantasy profiles by team.
    by_team = {team: grp for team, grp in players_df.groupby("team_abbr")}
    matches = []
    for _, row in official_df.iterrows():
        team = row.get("official_team_abbr")
        candidates = by_team.get(team)
        best = None
        if candidates is not None and not candidates.empty:
            choices = candidates["norm"].tolist()
            res = process.extractOne(row["norm"], choices, scorer=fuzz.token_sort_ratio)
            if res:
                cand_norm, score, idx = res
                cand = candidates.iloc[idx]
                best = {
                    "player_id": cand.player_id,
                    "fantasy_name": cand["name"],
                    "credits": cand.credits,
                    "position": cand.position,
                    "popularity_pct": cand.popularity_pct,
                    "match_quality": score,
                }
        matches.append(best or {"player_id": None, "fantasy_name": None, "credits": None, "position": None, "popularity_pct": None, "match_quality": None})
    return pd.concat([official_df.reset_index(drop=True), pd.DataFrame(matches)], axis=1)


def build_datasets():
    config = get_json_sync(f"{BASE}/leagues/{LEAGUE_ID}/config")["data"]
    with open(OUT_DIR / "league_config.json", "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    matches_df, schedule_raw = flatten_schedule(config)
    matches_df.to_csv(OUT_DIR / "utakmice.csv", index=False)
    with open(OUT_DIR / "schedule_raw.json", "w", encoding="utf-8") as f:
        json.dump(schedule_raw, f, ensure_ascii=False, indent=2)

    profiles_path = ROOT / "fantasy_profiles_active.json"
    players_df = profiles_df_from_json(profiles_path)
    players_df = add_next_matches(players_df, matches_df)

    # Matchdays with at least started/played games up to current matchday. Current only early season.
    current_md_num = config["current_matchday"]["number"]
    mds_to_fetch = [m for m in config["matchdays"] if m["number"] <= current_md_num]
    logs_df = asyncio.run(fetch_fantasy_logs(players_df, mds_to_fetch))
    logs_df = logs_df.merge(players_df[["player_id", "name", "position", "team_abbr", "credits"]], on="player_id", how="left")
    # Ensure common fantasy stat columns exist.
    for col in ["pts", "reb", "ast", "stl", "blk", "tov", "fd", "pf", "fg_missed", "ft_missed", "win_1-10", "win_11-20", "win_21+"]:
        if col not in logs_df.columns:
            logs_df[col] = pd.NA

    current_logs = logs_df[logs_df["matchday"] == current_md_num].copy()
    current_cols = [
        "player_id", "fantasy_pts", "match_status", "opponent_abbr", "home_away", "start_local", "team_score", "opponent_score",
        "pts", "reb", "ast", "stl", "blk", "tov", "fd", "pf", "fg_missed", "ft_missed",
        "win_1-10", "win_11-20", "win_21+"
    ]
    current_logs = current_logs[current_cols].rename(columns={
        "fantasy_pts": "current_md_fantasy_pts",
        "match_status": "current_md_status",
        "opponent_abbr": "current_md_opp",
        "home_away": "current_md_HA",
        "start_local": "current_md_time",
        "team_score": "current_md_team_score",
        "opponent_score": "current_md_opp_score",
    })
    players_df = players_df.merge(current_logs, on="player_id", how="left")
    players_df["value_current_md"] = (players_df["current_md_fantasy_pts"] / players_df["credits"]).round(2)
    players_df["credits_rank"] = players_df["credits"].rank(method="min", ascending=False).astype(int)
    players_df["played_current_md"] = players_df["current_md_status"].eq("played")

    official = fetch_official_stats()
    official = fuzzy_attach_prices(official, players_df)

    # Save CSVs.
    players_df.to_csv(OUT_DIR / "igraci_fantasy.csv", index=False)
    logs_df.to_csv(OUT_DIR / "fantasy_poeni_log.csv", index=False)
    official.to_csv(OUT_DIR / "official_euroleague_stats.csv", index=False)

    return config, matches_df, players_df, logs_df, official


def write_excel(config, matches_df, players_df, logs_df, official_df, out_path):
    # Serbian-friendly column order/labels.
    players_view = players_df[[
        "player_id", "name", "position", "team_abbr", "team", "jersey", "credits", "credits_rank",
        "current_md_fantasy_pts", "value_current_md", "current_md_status", "current_md_opp", "current_md_HA", "current_md_time",
        "pts", "reb", "ast", "stl", "blk", "tov", "fd", "pf", "fg_missed", "ft_missed",
        "avg_fantasy_pts_api", "total_plus", "popularity_pct", "is_injured", "started_from_bench", "is_on_fire",
        "next_matchday", "next_start_local", "next_home_away", "next_opponent", "next_match",
    ]].sort_values(["position", "credits"], ascending=[True, False])

    prices_view = players_df[["player_id", "name", "position", "team_abbr", "credits", "popularity_pct", "is_injured", "started_from_bench", "next_matchday", "next_opponent", "next_start_local"]].sort_values("credits", ascending=False)

    logs_view = logs_df.sort_values(["matchday", "fantasy_pts", "credits"], ascending=[True, False, False])

    info = pd.DataFrame([
        ["Generisano", datetime.now(LOCAL_TZ).strftime("%Y-%m-%d %H:%M %Z")],
        ["Lokalna zona", "Europe/Zagreb"],
        ["Liga", "EuroLeague Fantasy Challenge / EuroLeague"],
        ["Current competition ID", config.get("current_competition_id")],
        ["Current schedule ID", config.get("current_schedule_id")],
        ["Current players list ID", config.get("current_players_list_id")],
        ["Current matchday", config.get("current_matchday", {}).get("number")],
        ["Broj igrača/trenera", len(players_df)],
        ["Broj utakmica", len(matches_df)],
        ["Napomena", "Cijene, popularnost, fantasy poeni i raspored su iz EuroLeague Fantasy Challenge API-ja; official statistika je iz javnog EuroLeague Basketball stats API-ja."],
        ["Fantazi Masteri", "Euroleague dashboard trenutno prikazuje USKORO, pa podaci nisu mogli biti preuzeti odatle."],
    ], columns=["Polje", "Vrijednost"])

    with pd.ExcelWriter(out_path, engine="xlsxwriter") as writer:
        info.to_excel(writer, sheet_name="INFO", index=False)
        players_view.to_excel(writer, sheet_name="Igraci dashboard", index=False)
        prices_view.to_excel(writer, sheet_name="Cijene", index=False)
        logs_view.to_excel(writer, sheet_name="Fantasy poeni log", index=False)
        matches_df.to_excel(writer, sheet_name="Utakmice", index=False)
        if not official_df.empty:
            official_df.to_excel(writer, sheet_name="Official EL stats", index=False)

        wb = writer.book
        header_fmt = wb.add_format({"bold": True, "bg_color": "#1f4e78", "font_color": "white", "border": 1})
        money_fmt = wb.add_format({"num_format": "0.0"})
        pct_fmt = wb.add_format({"num_format": "0.00"})
        good_fmt = wb.add_format({"bg_color": "#C6EFCE", "font_color": "#006100"})
        bad_fmt = wb.add_format({"bg_color": "#FFC7CE", "font_color": "#9C0006"})
        for sheet_name, df in [("Igraci dashboard", players_view), ("Cijene", prices_view), ("Fantasy poeni log", logs_view), ("Utakmice", matches_df), ("Official EL stats", official_df), ("INFO", info)]:
            if sheet_name not in writer.sheets:
                continue
            ws = writer.sheets[sheet_name]
            ws.freeze_panes(1, 0)
            ws.autofilter(0, 0, max(len(df), 1), max(len(df.columns)-1, 0))
            for col_idx, col in enumerate(df.columns):
                ws.write(0, col_idx, col, header_fmt)
                width = max(10, min(28, max([len(str(col))] + [len(str(x)) for x in df[col].head(200).fillna("")])))
                ws.set_column(col_idx, col_idx, width)
            # conditional formatting for dashboard.
            if sheet_name == "Igraci dashboard":
                if "current_md_fantasy_pts" in df.columns:
                    c = df.columns.get_loc("current_md_fantasy_pts")
                    ws.conditional_format(1, c, len(df), c, {"type":"cell", "criteria":">=", "value":20, "format":good_fmt})
                    ws.conditional_format(1, c, len(df), c, {"type":"cell", "criteria":"<", "value":0, "format":bad_fmt})
                if "is_injured" in df.columns:
                    c = df.columns.get_loc("is_injured")
                    ws.conditional_format(1, c, len(df), c, {"type":"text", "criteria":"containing", "value":"TRUE", "format":bad_fmt})


def df_to_records(df, cols):
    records = []
    for _, row in df[cols].iterrows():
        rec = {}
        for c in cols:
            v = row[c]
            if pd.isna(v):
                rec[c] = None
            elif isinstance(v, (pd.Timestamp, datetime)):
                rec[c] = v.isoformat()
            elif isinstance(v, float):
                if math.isfinite(v):
                    rec[c] = round(v, 3)
                else:
                    rec[c] = None
            else:
                rec[c] = v.item() if hasattr(v, "item") else v
        records.append(rec)
    return records


def write_html(config, matches_df, players_df, logs_df, official_df, out_path):
    # Make compact records for HTML.
    players_cols = [
        "player_id", "name", "position", "team_abbr", "credits", "current_md_fantasy_pts", "value_current_md",
        "current_md_status", "current_md_opp", "current_md_HA", "current_md_time", "pts", "reb", "ast", "stl", "blk", "tov", "fd", "pf", "fg_missed", "ft_missed",
        "popularity_pct", "is_injured", "started_from_bench", "next_opponent", "next_start_local", "next_home_away"
    ]
    players_rec = df_to_records(players_df.sort_values(["credits"], ascending=False), players_cols)
    matches_rec = df_to_records(matches_df, ["matchday", "round", "start_local", "status", "home_abbr", "away_abbr", "result", "winner", "home_team", "away_team"])
    logs_cols = ["matchday", "name", "position", "team_abbr", "credits", "fantasy_pts", "opponent_abbr", "home_away", "match_status", "start_local", "pts", "reb", "ast", "stl", "blk", "tov", "fd", "pf", "fg_missed", "ft_missed", "win_1-10", "win_11-20", "win_21+"]
    logs_rec = df_to_records(logs_df.sort_values(["matchday", "fantasy_pts"], ascending=[True, False]), logs_cols)
    official_cols = []
    official_rec = []
    if not official_df.empty:
        wanted = ["official_name_full", "official_team_abbr", "position", "credits", "gamesPlayed", "minutesPlayed", "pointsScored", "totalRebounds", "assists", "steals", "turnovers", "blocks", "pir", "pts_pg", "reb_pg", "ast_pg", "pir_pg", "effectiveFieldGoalPercentage", "trueShootingPercentage", "fantasy_name", "match_quality"]
        official_cols = [c for c in wanted if c in official_df.columns]
        official_rec = df_to_records(official_df.sort_values(["pir_pg"], ascending=False, na_position="last"), official_cols)

    payload = {
        "players": players_rec,
        "matches": matches_rec,
        "logs": logs_rec,
        "official": official_rec,
        "officialCols": official_cols,
        "meta": {
            "generated": datetime.now(LOCAL_TZ).strftime("%Y-%m-%d %H:%M %Z"),
            "currentMatchday": config.get("current_matchday", {}).get("number"),
            "players": len(players_df),
            "matches": len(matches_df),
        }
    }
    js = json.dumps(payload, ensure_ascii=False)
    html = f"""<!doctype html>
<html lang="sr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>EuroLeague Fantasy pregled</title>
<style>
:root {{ --bg:#08111f; --card:#101d31; --card2:#13233b; --txt:#eaf1fb; --muted:#9db0cc; --accent:#58b6ff; --green:#18c27a; --red:#ff5d73; --yellow:#ffd166; }}
* {{ box-sizing:border-box; }} body {{ margin:0; font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; background:linear-gradient(135deg,#07101d,#101d31 45%,#08111f); color:var(--txt); }}
header {{ padding:24px 28px; border-bottom:1px solid rgba(255,255,255,.08); position:sticky; top:0; background:rgba(8,17,31,.94); backdrop-filter:blur(8px); z-index:5; }}
h1 {{ margin:0 0 8px; font-size:26px; }} .subtitle {{ color:var(--muted); font-size:14px; }}
.stats {{ display:flex; gap:12px; flex-wrap:wrap; margin-top:16px; }} .stat {{ background:var(--card); border:1px solid rgba(255,255,255,.08); border-radius:14px; padding:10px 14px; min-width:140px; }} .stat b {{ display:block; font-size:22px; }} .stat span {{ color:var(--muted); font-size:12px; }}
main {{ padding:22px 28px 60px; }} .tabs {{ display:flex; gap:8px; flex-wrap:wrap; margin-bottom:16px; }} button {{ background:var(--card2); color:var(--txt); border:1px solid rgba(255,255,255,.1); border-radius:10px; padding:9px 12px; cursor:pointer; }} button.active, button:hover {{ border-color:var(--accent); color:white; }}
.panel {{ display:none; }} .panel.active {{ display:block; }} .toolbar {{ display:flex; gap:10px; flex-wrap:wrap; margin:0 0 12px; align-items:center; }} input, select {{ background:#0b1628; color:var(--txt); border:1px solid rgba(255,255,255,.13); border-radius:10px; padding:9px 10px; }} input::placeholder {{ color:#7588a5; }}
.tablewrap {{ overflow:auto; border:1px solid rgba(255,255,255,.08); border-radius:14px; background:rgba(16,29,49,.8); max-height:72vh; }}
table {{ width:100%; border-collapse:collapse; font-size:13px; }} th,td {{ padding:9px 10px; border-bottom:1px solid rgba(255,255,255,.07); white-space:nowrap; }} th {{ position:sticky; top:0; background:#182945; color:#dcecff; cursor:pointer; z-index:2; text-align:left; }} tr:hover td {{ background:rgba(88,182,255,.07); }}
.badge {{ display:inline-block; border-radius:999px; padding:3px 8px; font-size:12px; font-weight:700; }} .Guard {{ background:#173f71; }} .Forward {{ background:#315027; }} .Center {{ background:#5c3922; }} .HeadCoach {{ background:#53436d; }}
.good {{ color:var(--green); font-weight:700; }} .bad {{ color:var(--red); font-weight:700; }} .muted {{ color:var(--muted); }} .price {{ color:var(--yellow); font-weight:700; }}
.note {{ background:rgba(255,255,255,.06); border:1px solid rgba(255,255,255,.08); border-radius:14px; padding:14px; color:#cbd8ee; line-height:1.45; margin:12px 0 16px; }}
.small {{ font-size:12px; color:var(--muted); }}
</style>
</head>
<body>
<header>
  <h1>EuroLeague Fantasy pregled za izbor tima</h1>
  <div class="subtitle">Cijene, fantasy poeni, raspored utakmica i statistika igrača/trenera. Generisano: <b id="gen"></b></div>
  <div class="stats">
    <div class="stat"><b id="sPlayers"></b><span>igrača + trenera</span></div>
    <div class="stat"><b id="sMatches"></b><span>utakmica u rasporedu</span></div>
    <div class="stat"><b id="sMd"></b><span>trenutno kolo</span></div>
  </div>
</header>
<main>
  <div class="tabs">
    <button class="tab active" data-tab="players">Igrači dashboard</button>
    <button class="tab" data-tab="matches">Utakmice</button>
    <button class="tab" data-tab="logs">Fantasy poeni / box</button>
    <button class="tab" data-tab="official">Official EL stats</button>
    <button class="tab" data-tab="info">Info</button>
  </div>

  <section id="players" class="panel active">
    <div class="note">Klikni na zaglavlje kolone za sortiranje. Koristi filtre za poziciju, tim i pretragu. <b>Value</b> = fantasy poeni u trenutnom kolu / cijena. Za igrače koji još nisu odigrali meč u kolu, poeni su prazni/null.</div>
    <div class="toolbar">
      <input id="pSearch" placeholder="Pretraga igrača..." oninput="renderPlayers()">
      <select id="pTeam" onchange="renderPlayers()"><option value="">Svi timovi</option></select>
      <select id="pPos" onchange="renderPlayers()"><option value="">Sve pozicije</option></select>
      <select id="pStatus" onchange="renderPlayers()"><option value="">Svi statusi meča</option><option value="played">Odigrali</option><option value="scheduled">Tek igraju</option></select>
      <label class="small"><input type="checkbox" id="hideInj" onchange="renderPlayers()"> sakrij povrijeđene</label>
    </div>
    <div id="playersTable" class="tablewrap"></div>
  </section>

  <section id="matches" class="panel">
    <div class="toolbar"><input id="mSearch" placeholder="Pretraga timova/kola..." oninput="renderMatches()"></div>
    <div id="matchesTable" class="tablewrap"></div>
  </section>

  <section id="logs" class="panel">
    <div class="toolbar"><input id="lSearch" placeholder="Pretraga loga..." oninput="renderLogs()"><select id="lTeam" onchange="renderLogs()"><option value="">Svi timovi</option></select></div>
    <div id="logsTable" class="tablewrap"></div>
  </section>

  <section id="official" class="panel">
    <div class="note">Official statistika je iz javnog EuroLeague Basketball stats API-ja. Cijene su spojene fuzzy-matchingom na fantasy listu; kolona match_quality pokazuje kvalitet spajanja.</div>
    <div class="toolbar"><input id="oSearch" placeholder="Pretraga official stats..." oninput="renderOfficial()"></div>
    <div id="officialTable" class="tablewrap"></div>
  </section>

  <section id="info" class="panel">
    <div class="note">
      <b>Izvori:</b><br>
      – EuroLeague Fantasy Challenge API za cijene, profile, fantasy poene i raspored.<br>
      – EuroLeague Basketball javni stats API za official statistiku.<br><br>
      Fantazi Masteri Euroleague dashboard koji si poslao trenutno prikazuje “USKORO”, zato sam pregled napravio direktno iz dostupnih javnih EuroLeague/Fantasy podataka. Za novo stanje poslije sljedećeg kola treba ponovo osvježiti fajl.
    </div>
  </section>
</main>
<script>
const DATA = {js};
let sortState = {{}};
function val(x) {{ return x===null || x===undefined ? '' : x; }}
function asNum(x) {{ const n = parseFloat(x); return isNaN(n) ? -Infinity : n; }}
function clsPos(p) {{ return String(p||'').replace(/\s+/g,''); }}
function fmt(c,v) {{
  if (v===null || v===undefined || v==='') return '<span class="muted">–</span>';
  if (c==='position') return `<span class="badge ${{clsPos(v)}}">${{v}}</span>`;
  if (c==='credits') return `<span class="price">${{Number(v).toFixed(1)}}</span>`;
  if (['current_md_fantasy_pts','fantasy_pts','value_current_md','pir_pg','pts_pg','reb_pg','ast_pg'].includes(c)) {{ const n=Number(v); return `<span class="${{n>=15?'good':(n<0?'bad':'')}}">${{Number.isInteger(n)?n:n.toFixed(2)}}</span>`; }}
  if (c==='is_injured' && v) return '<span class="bad">DA</span>';
  if (typeof v === 'boolean') return v ? 'DA' : 'NE';
  return String(v);
}}
function table(el, rows, cols, labels, key) {{
  const st = sortState[key] || {{col:null, dir:1}};
  let rs = rows.slice();
  if (st.col) rs.sort((a,b)=>{{ let av=a[st.col], bv=b[st.col]; let an=parseFloat(av), bn=parseFloat(bv); if(!isNaN(an)&&!isNaN(bn)) return (an-bn)*st.dir; return String(val(av)).localeCompare(String(val(bv)))*st.dir; }});
  let html = '<table><thead><tr>' + cols.map(c=>`<th data-col="${{c}}">${{labels[c]||c}}</th>`).join('') + '</tr></thead><tbody>';
  html += rs.map(r=>'<tr>'+cols.map(c=>`<td>${{fmt(c,r[c])}}</td>`).join('')+'</tr>').join('');
  html += '</tbody></table>';
  document.getElementById(el).innerHTML = html;
  document.querySelectorAll(`#${{el}} th`).forEach(th=> th.onclick = () => {{ const c=th.dataset.col; if(!sortState[key]) sortState[key]={{}}; sortState[key].dir = sortState[key].col===c ? -sortState[key].dir : 1; sortState[key].col=c; renderAllCurrent(); }});
}}
function filterText(row, q) {{ return !q || Object.values(row).join(' ').toLowerCase().includes(q.toLowerCase()); }}
const labels = {{player_id:'ID', name:'Igrač', position:'Pozicija', team_abbr:'Tim', credits:'Cijena', current_md_fantasy_pts:'MD poeni', value_current_md:'Value', current_md_status:'Status', current_md_opp:'Protiv', current_md_HA:'H/A', current_md_time:'Vrijeme', pts:'PTS', reb:'REB', ast:'AST', stl:'STL', blk:'BLK', tov:'TOV', fd:'FD', pf:'PF', fg_missed:'FG-', ft_missed:'FT-', popularity_pct:'Pick %', is_injured:'Povr.', started_from_bench:'Bench', next_opponent:'Slj. protiv', next_start_local:'Slj. vrijeme', next_home_away:'Slj. H/A', matchday:'Kolo', round:'Runda', start_local:'Vrijeme', status:'Status', home_abbr:'Domaćin', away_abbr:'Gost', result:'Rez.', winner:'Pobj.', fantasy_pts:'Fantasy', opponent_abbr:'Protiv', home_away:'H/A', match_status:'Status', official_name_full:'Igrač', official_team_abbr:'Tim', gamesPlayed:'GP', minutesPlayed:'MIN', pointsScored:'PTS', totalRebounds:'REB', assists:'AST', steals:'STL', turnovers:'TOV', blocks:'BLK', pir:'PIR', pts_pg:'PTS/G', reb_pg:'REB/G', ast_pg:'AST/G', pir_pg:'PIR/G', effectiveFieldGoalPercentage:'eFG%', trueShootingPercentage:'TS%', fantasy_name:'Fantasy match', match_quality:'Match %'}};
function renderPlayers() {{
  const q=pSearch.value, team=pTeam.value, pos=pPos.value, st=pStatus.value, hide=hideInj.checked;
  let rows=DATA.players.filter(r=>filterText(r,q) && (!team||r.team_abbr===team) && (!pos||r.position===pos) && (!st||r.current_md_status===st) && (!hide||!r.is_injured));
  table('playersTable', rows, ['name','position','team_abbr','credits','current_md_fantasy_pts','value_current_md','current_md_status','current_md_opp','current_md_HA','current_md_time','pts','reb','ast','stl','blk','tov','fd','pf','fg_missed','ft_missed','popularity_pct','is_injured','started_from_bench','next_opponent','next_start_local'], labels, 'players');
}}
function renderMatches() {{ let q=mSearch.value; table('matchesTable', DATA.matches.filter(r=>filterText(r,q)), ['matchday','round','start_local','status','home_abbr','away_abbr','result','winner','home_team','away_team'], labels, 'matches'); }}
function renderLogs() {{ let q=lSearch.value, team=lTeam.value; table('logsTable', DATA.logs.filter(r=>filterText(r,q)&&(!team||r.team_abbr===team)), ['matchday','name','position','team_abbr','credits','fantasy_pts','opponent_abbr','home_away','match_status','start_local','pts','reb','ast','stl','blk','tov','fd','pf','fg_missed','ft_missed','win_1-10','win_11-20','win_21+'], labels, 'logs'); }}
function renderOfficial() {{ let q=oSearch.value; table('officialTable', DATA.official.filter(r=>filterText(r,q)), DATA.officialCols, labels, 'official'); }}
function renderAllCurrent() {{ const active=document.querySelector('.panel.active').id; if(active==='players')renderPlayers(); if(active==='matches')renderMatches(); if(active==='logs')renderLogs(); if(active==='official')renderOfficial(); }}
function init() {{
  gen.textContent=DATA.meta.generated; sPlayers.textContent=DATA.meta.players; sMatches.textContent=DATA.meta.matches; sMd.textContent=DATA.meta.currentMatchday;
  const teams=[...new Set(DATA.players.map(r=>r.team_abbr).filter(Boolean))].sort(); teams.forEach(t=>{{ pTeam.innerHTML+=`<option>${{t}}</option>`; lTeam.innerHTML+=`<option>${{t}}</option>`; }});
  const pos=[...new Set(DATA.players.map(r=>r.position).filter(Boolean))].sort(); pos.forEach(p=>pPos.innerHTML+=`<option>${{p}}</option>`);
  document.querySelectorAll('.tab').forEach(b=>b.onclick=()=>{{ document.querySelectorAll('.tab,.panel').forEach(x=>x.classList.remove('active')); b.classList.add('active'); document.getElementById(b.dataset.tab).classList.add('active'); renderAllCurrent(); }});
  renderPlayers(); renderMatches(); renderLogs(); renderOfficial();
}}
init();
</script>
</body>
</html>"""
    Path(out_path).write_text(html, encoding="utf-8")


if __name__ == "__main__":
    config, matches_df, players_df, logs_df, official_df = build_datasets()
    xlsx_path = str(ROOT / "euroleague_fantasy_pregled.xlsx")
    html_path = str(ROOT / "euroleague_fantasy_dashboard.html")
    write_excel(config, matches_df, players_df, logs_df, official_df, xlsx_path)
    write_html(config, matches_df, players_df, logs_df, official_df, html_path)
    print("Wrote", xlsx_path, html_path)
    print("players", len(players_df), "matches", len(matches_df), "logs", len(logs_df), "official", len(official_df))
