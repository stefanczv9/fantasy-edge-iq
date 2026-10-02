"""
Popunjava fantasy_poeni_log.csv iz zvanicnog EuroLeague box score feeda.

Zasto: Fantaking fantasy API ponekad vrati nepotpun mec - za nekog igraca nema poena
(pts=None) ili igrac uopste ne postoji u tom mecu (npr. Bryant Dunston u VIR-OLY).
Tada zbir poena po pozicijama ne odgovara zvanicnom rezultatu, DvP validacija padne i
ta utakmica se izbacuje iz uzorka (games_sample 2 umjesto 3).

Sta radi:
  1. Uzme sve odigrane meceve iz fantasy_poeni_log.csv.
  2. Nadje odgovarajucu zvanicnu utakmicu (datum + rezultat + preklapanje imena).
  3. Iz zvanicnog box scorea procita statistiku igraca koji su igrali (timePlayed > 0).
  4. Spari igrace po timu u tri prolaza:
        a) identicno normalizovano ime,
        b) jedinstveno prezime na obje strane,
        c) najbolje poklapanje >= 0.75.
  5. Postojecem igracu popuni SAMO prazne (NaN) vrijednosti.
  6. Igraca kojeg u logu uopste nema doda kao novi red (sa pozicijom iz zvanicnog feeda).
  7. Na kraju ispise kontrolu: zbir poena u logu vs zvanicni rezultat, po timu.

Bezopasno ako feed ne radi: prijavi i izadje bez promjena.
"""
from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "euroleague_fantasy_data"
LOG_PATH = DATA / "fantasy_poeni_log.csv"
SEASON = 2026

STAT_MAP = {
    "points": "pts",
    "totalRebounds": "reb",
    "assistances": "ast",
    "steals": "stl",
    "blocksFavour": "blk",
    "turnovers": "tov",
}
POSITIONS = ("Guard", "Forward", "Center")


SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}


def norm_text(s) -> str:
    if s is None:
        return ""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().replace("-", " ").replace(".", " ").replace("'", " ").replace("´", " ")
    return re.sub(r"\s+", " ", s).strip()


def official_to_full(name: str) -> str:
    """"BAUGH, DAMION DE'VON" -> "Damion De'von Baugh"."""
    if not name or "," not in name:
        return name or ""
    surname, given = name.split(",", 1)
    return f"{given.strip().title()} {surname.strip().title()}"


def tokens(s) -> frozenset:
    """Tokeni bez sufiksa (jr/sr/ii/iii/iv/v) - 'Wade Baldwin Iv' == 'Wade Baldwin'."""
    ts = [t for t in norm_text(s).split() if len(t) > 1]
    core = [t for t in ts if t not in SUFFIXES]
    return frozenset(core or ts)


def surname(s) -> str:
    ts = [t for t in norm_text(s).split() if t not in SUFFIXES]
    return ts[-1] if ts else ""


def match_score(a, b) -> float:
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(len(ta), len(tb))


def pair_players(log_players: list, off_players: list) -> tuple[list, list, list]:
    """Vrati (parovi, nepovezani_log, nepovezani_official)."""
    pairs, used_off = [], set()
    # prolaz 1: identicni skupovi tokena
    by_key = {}
    for j, off in enumerate(off_players):
        by_key.setdefault(tokens(off["full_name"]), []).append(j)
    remaining = []
    for i, lp in enumerate(log_players):
        key = tokens(lp["name"])
        cand = [j for j in by_key.get(key, []) if j not in used_off]
        if cand:
            used_off.add(cand[0])
            pairs.append((i, cand[0]))
        else:
            remaining.append(i)
    # prolaz 2: jedinstveno prezime na obje strane
    if remaining:
        log_by_sur, off_by_sur = {}, {}
        for i in remaining:
            log_by_sur.setdefault(surname(log_players[i]["name"]), []).append(i)
        for j, off in enumerate(off_players):
            if j in used_off:
                continue
            off_by_sur.setdefault(surname(off["full_name"]), []).append(j)
        still = []
        for i in remaining:
            sur = surname(log_players[i]["name"])
            cand = [j for j in off_by_sur.get(sur, []) if j not in used_off]
            if sur and len(log_by_sur.get(sur, [])) == 1 and len(cand) == 1:
                used_off.add(cand[0])
                pairs.append((i, cand[0]))
            else:
                still.append(i)
        remaining = still
    # prolaz 3: najbolje poklapanje >= 0.75
    scored = []
    for i in remaining:
        for j, off in enumerate(off_players):
            if j in used_off:
                continue
            s = match_score(log_players[i]["name"], off["full_name"])
            if s >= 0.75:
                scored.append((s, i, j))
    scored.sort(reverse=True)
    taken_log = set()
    for s, i, j in scored:
        if i in taken_log or j in used_off:
            continue
        taken_log.add(i)
        used_off.add(j)
        pairs.append((i, j))
    remaining = [i for i in remaining if i not in taken_log]
    unmatched_off = [j for j in range(len(off_players)) if j not in used_off]
    return pairs, remaining, unmatched_off


def main() -> None:
    if not LOG_PATH.exists():
        print("nema fantasy_poeni_log.csv - preskacem patch")
        return
    log = pd.read_csv(LOG_PATH)
    if log.empty or "match_id" not in log.columns:
        print("log je prazan - preskacem patch")
        return
    ORIG_COLS = list(log.columns)

    try:
        from euroleague_api.game_stats import GameStats
        gs = GameStats("E")
        codes = gs.get_gamecodes_season(SEASON)
    except Exception as exc:
        print(f"UPOZORENJE: zvanicni feed nije dostupan ({exc}); preskacem patch")
        return
    if codes is None or codes.empty:
        print("UPOZORENJE: zvanicni feed vratio prazno; preskacem patch")
        return

    codes = codes[codes["played"].astype(bool)].copy()
    codes["date_norm"] = pd.to_datetime(codes["date"], format="%b %d, %Y", errors="coerce").dt.date

    played = log[log["match_status"].eq("played")]
    if played.empty:
        print("nema odigranih meceva u logu - preskacem patch")
        return

    filled_total = 0
    added_total = 0
    games_checked = 0
    new_rows: list[dict] = []

    for match_id, g in played.groupby("match_id"):
        dates = pd.to_datetime(g["start_local"].astype(str).str[:10], errors="coerce").dt.date.dropna()
        if dates.empty:
            continue
        date = dates.iloc[0]
        hs_all = pd.to_numeric(g.get("home_score"), errors="coerce").dropna()
        as_all = pd.to_numeric(g.get("away_score"), errors="coerce").dropna()
        if hs_all.empty or as_all.empty:
            continue
        hs, as_ = float(hs_all.iloc[0]), float(as_all.iloc[0])

        cand = codes[(codes["date_norm"] == date)
                     & (((codes["homescore"] == hs) & (codes["awayscore"] == as_))
                        | ((codes["homescore"] == as_) & (codes["awayscore"] == hs)))]
        if cand.empty:
            continue

        log_names = [str(n) for n in g["name"]]
        best_box, best_overlap = None, -1
        for _, row in cand.iterrows():
            try:
                box = gs.get_game_stats(SEASON, int(row["gameCode"]))
            except Exception:
                continue
            if box is None or box.empty:
                continue
            names = []
            for side in ("local.players", "road.players"):
                for entry in (box.iloc[0].get(side) or []):
                    person = (entry.get("player") or {}).get("person") or {}
                    names.append(official_to_full(person.get("name") or ""))
            overlap = sum(1 for n in names
                          if n and max((match_score(n, ln) for ln in log_names), default=0) >= 0.55)
            if overlap > best_overlap:
                best_box, best_overlap = box, overlap
        if best_box is None:
            continue

        games_checked += 1
        box = best_box.iloc[0]

        # domaci tim u nasem logu
        home_team = None
        for _, r in g.iterrows():
            if str(r.get("home_away")) == "H":
                home_team = str(r.get("team_abbr"))
                break
        teams_in_game = list({str(t) for t in g["team_abbr"].dropna()})
        if home_team is None and teams_in_game:
            home_team = teams_in_game[0]
        away_team = next((t for t in teams_in_game if t != home_team), None)

        for side, is_home in (("local.players", True), ("road.players", False)):
            team = home_team if is_home else away_team
            if not team:
                continue
            rows_idx = [idx for idx, r in g.iterrows()
                        if str(r.get("team_abbr")) == team and str(r.get("position")) in POSITIONS]
            if not rows_idx:
                continue
            log_players = [{"idx": idx, "name": str(log.at[idx, "name"])} for idx in rows_idx]

            off_players = []
            for entry in (box.get(side) or []):
                player = entry.get("player") or {}
                person = player.get("person") or {}
                stats = entry.get("stats") or {}
                try:
                    minutes = float(stats.get("timePlayed") or 0)
                except Exception:
                    minutes = 0.0
                pos = str(player.get("positionName") or "")
                off_players.append({
                    "full_name": official_to_full(person.get("name") or ""),
                    "position": pos,
                    "minutes": minutes,
                    "stats": stats,
                })

            pairs, unmatched_log, unmatched_off = pair_players(log_players, off_players)

            for i, j in pairs:
                off = off_players[j]
                if off["minutes"] <= 0:
                    continue
                idx = log_players[i]["idx"]
                for src, dst in STAT_MAP.items():
                    val = off["stats"].get(src)
                    if val is None:
                        continue
                    if dst in log.columns and pd.isna(log.at[idx, dst]):
                        log.at[idx, dst] = float(val)
                        filled_total += 1

            for j in unmatched_off:
                off = off_players[j]
                if off["minutes"] <= 0 or off["position"] not in POSITIONS:
                    continue
                template = dict(g[g["team_abbr"].astype(str) == team].iloc[0])
                for c in ORIG_COLS:
                    template.setdefault(c, None)
                template.update({
                    "player_id": None,
                    "name": off["full_name"],
                    "position": off["position"],
                    "fantasy_pts": None,
                    "credits": None,
                    "label": None,
                })
                for src, dst in STAT_MAP.items():
                    template[dst] = off["stats"].get(src)
                for c in ORIG_COLS:
                    if c.startswith("fp_") or re.match(r"^(win|loss)_", c):
                        template[c] = None
                new_rows.append(template)
                added_total += 1

    if new_rows:
        log = pd.concat([log, pd.DataFrame(new_rows)], ignore_index=True)

    # kontrola po timu
    for c in ("pts", "reb", "ast", "stl", "blk", "tov", "team_score"):
        log[c] = pd.to_numeric(log[c], errors="coerce")
    chk = log[(log["match_status"].eq("played")) & (log["position"].isin(POSITIONS))]
    problems = []
    for (match_id, team), g in chk.groupby(["match_id", "team_abbr"]):
        official = g["team_score"].dropna()
        if official.empty:
            continue
        diff = g["pts"].fillna(0).sum() - float(official.iloc[0])
        if abs(diff) > 0.1:
            problems.append(f"   match {match_id} {team}: zbir={g['pts'].fillna(0).sum():.0f} vs zvanicno={float(official.iloc[0]):.0f} (diff {diff:+.0f})")

    log.to_csv(LOG_PATH, index=False)
    print(f"official box score patch: popunjeno {filled_total} vrijednosti, dodano {added_total} igraca, "
          f"provjereno {games_checked} utakmica")
    if problems:
        print(f"   {len(problems)} timskih redova i dalje ne prolazi kontrolu (DvP ce ih preskociti):")
        for line in problems[:12]:
            print(line)
    else:
        print("   svi timski redovi se poklapaju sa zvanicnim rezultatom")


if __name__ == "__main__":
    sys.exit(main())
