#!/usr/bin/env python3
"""Nezavisna provjera EuroLeague dashboarda i DvP-a naspram zvanicnih box scoreova (euroleague_api, takmicenje 'E').

  1) Dashboard (euroleague-players-full.csv): GP, MIN/G, PIR/G, PTS/G, REB/G, AST/G, FGA/min po igracu vs zvanicni box scoreovi
  2) DvP (euroleague-defense-vs-position*.csv): poeni primljeni po poziciji (G/F/C, fantasy pozicije) preracunati iz box scoreova
  3) Fantasy igraci koji su igrali, a nemaju stats u dashboardu (greska uparivanja imena)

Pokretanje:  python3 scripts/audit_el_vs_official.py            (cita fajlove iz korijena repoa)
             python3 scripts/audit_el_vs_official.py --live     (cita CSV-ove sa sajta)
Izlaz: 'OK' ili spisak odstupanja; exit kod 1 ako ima odstupanja.
"""
from __future__ import annotations

import io
import re
import sys
import unicodedata
import warnings
from pathlib import Path

import pandas as pd
import requests

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
LIVE = "--live" in sys.argv
SUF = {"jr", "sr", "ii", "iii", "iv", "v"}


def rd(name):
    if LIVE:
        return pd.read_csv(io.StringIO(requests.get(f"https://www.fantasyedgeiq.com/{name}", timeout=60).text))
    return pd.read_csv(ROOT / name)


def key(s):
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return frozenset(x for x in re.sub(r"[^a-z0-9 ]", " ", s.replace("-", " ")).split() if len(x) > 1 and x not in SUF)


def full(n):
    if n and "," in n:
        a, b = n.split(",", 1)
        return f"{b.strip()} {a.strip()}".title()
    return (n or "").title()


def surname(s):
    t = [x for x in key(s)]
    return sorted(t, key=len)[-1] if t else ""


def official_boxes():
    from euroleague_api.game_stats import GameStats
    gs = GameStats("E")
    codes = gs.get_gamecodes_season(2026)
    codes = codes[codes["played"].astype(bool)]
    rows = []
    for _, c in codes.iterrows():
        box = gs.get_game_stats(2026, int(c.gameCode)).iloc[0]
        for side, team in (("local.players", c.homecode), ("road.players", c.awaycode)):
            for e in box.get(side) or []:
                st = e.get("stats") or {}
                per = (e.get("player") or {}).get("person") or {}
                sec = float(st.get("timePlayed") or 0)
                rows.append(dict(game=int(c.gameCode), team=team, name=per.get("name"), pos=(e.get("player") or {}).get("positionName"),
                                 sec=sec, pts=st.get("points") or 0, reb=st.get("totalRebounds") or 0, ast=st.get("assistances") or 0,
                                 val=st.get("valuation"), fga=(st.get("fieldGoalsAttempted2") or 0) + (st.get("fieldGoalsAttempted3") or 0)))
    return pd.DataFrame(rows), codes


def main():
    box, codes = official_boxes()
    box["full"] = box["name"].map(full)
    box["key"] = box["full"].map(key)
    dash = rd("euroleague-players-full.csv")
    dash["key"] = dash["name"].map(key)
    bad = 0
    # --- 1) igrac po igrac
    pl = box[box.sec > 0]
    agg = pl.groupby("key").agg(gp=("game", "nunique"), min=("sec", lambda s: s.sum() / 60), pir=("val", "mean"), pts=("pts", "mean"),
                                reb=("reb", "mean"), ast=("ast", "mean"), fga=("fga", "sum")).reset_index()
    agg["min_avg"] = agg["min"] / agg["gp"]
    agg["fga_min"] = agg["fga"] / agg["min"]
    # neupareni zvanicni igraci: pokusaj po prezimenu (jedinstveno) medju fantasy igracima koji nemaju par
    unmatched_off = agg[~agg.key.isin(dash.key)]
    surn = dash[~dash.key.isin(agg.key)].assign(s=lambda d: d["name"].map(surname)).groupby("s")["key"].apply(list).to_dict()
    remap = {}
    for _, r in unmatched_off.iterrows():
        cand = surn.get(surname(" ".join(r.key)), [])
        if len(cand) == 1:
            remap[r.key] = cand[0]
    agg["key"] = agg["key"].map(lambda k: remap.get(k, k))
    box["key"] = box["key"].map(lambda k: remap.get(k, k))
    m = dash[dash.gp_current.fillna(0) > 0].merge(agg, on="key", how="left")
    print(f"dashboard: {len(m)} igraca sa utakmicama | bez zvanicnog para: {int(m.gp.isna().sum())}")
    for a, b, tol in (("gp_current", "gp", 0.01), ("min_avg_current", "min_avg", 0.06), ("pir_avg_current", "pir", 0.06), ("pts_avg_current", "pts", 0.06),
                      ("reb_avg_current", "reb", 0.06), ("ast_avg_current", "ast", 0.06), ("fg_attempts_per_min_current", "fga_min", 0.01)):
        if a not in m.columns:
            continue
        d = (m[a].astype(float) - m[b].astype(float)).abs()
        n = int((d > tol).sum())
        bad += n
        print(f"  {a:30s} max razlika {d.max():.3f} | odstupanja > {tol}: {n}")
    # --- 3) fantasy igraci koji su igrali, a nemaju stats
    nf = dash[(dash.gp_current.fillna(0) == 0) & dash.key.isin(set(agg.key))]
    print(f"fantasy igraci koji su igrali a nemaju stats u dashboardu: {len(nf)} {list(nf['name'])}")
    bad += len(nf)
    # --- 2) DvP
    ml = rd("euroleague-defense-vs-position-matchlog.csv")
    dv = rd("euroleague-defense-vs-position.csv")
    mt = ml[ml.team_abbr == ml.home_abbr][["home_abbr", "away_abbr", "start_local", "opponent_score", "team_score"]].rename(columns={"opponent_score": "hs", "team_score": "as_"})
    mt["d"] = pd.to_datetime(mt.start_local.str[:10])
    codes = codes.assign(d=pd.to_datetime(codes["date"], format="%b %d, %Y"))
    cm = {}
    for g in codes.itertuples():
        x = mt[(mt.hs == g.homescore) & (mt.as_ == g.awayscore) & ((mt.d - g.d).abs() <= pd.Timedelta(days=1))]
        if len(x) == 1:
            cm[g.homecode] = x.iloc[0].home_abbr
            cm[g.awaycode] = x.iloc[0].away_abbr
    posmap = {"G": "Guard", "F": "Forward", "C": "Center"}
    fp = dash[dash.pos_short.isin(posmap)]
    fpos = dict(zip(fp.key, fp.pos_short.map(posmap)))
    # pozicija: fantasy; ako nema (igrac nije u fantasy listi), zvanicna
    pl = box[box.sec > 0].copy()          # box["key"] je vec preslikan na fantasy zapis imena gdje je upareno po prezimenu
    pl["pos_used"] = pl.key.map(fpos)
    pl["pos_used"] = pl.pos_used.fillna(pl.pos)
    games = codes[["gameCode", "homecode", "awaycode"]]
    rows = []
    for g in games.itertuples():
        for off, deff in ((g.homecode, g.awaycode), (g.awaycode, g.homecode)):
            b = pl[(pl.game == g.gameCode) & (pl.team == off)]
            rows.append({"def": cm.get(deff), "off": cm.get(off), **{p: float(b[b.pos_used == p].pts.sum()) for p in ("Guard", "Forward", "Center")}})
    A = pd.DataFrame(rows).merge(ml.rename(columns={"team_abbr": "def", "opponent_abbr": "off"}), on=["def", "off"], how="left")
    nd = 0
    for p, c in (("Guard", "guard_pts_allowed"), ("Forward", "forward_pts_allowed"), ("Center", "center_pts_allowed")):
        nd += int(((A[p] - A[c]).abs() > 0.01).sum())
    print(f"DvP: {len(A)} tim-utakmica | odstupanja po poziciji (G/F/C): {nd} | games_sample: {sorted(set(dv.games_sample))} | validation_ok: {bool(dv.validation_ok.all())}")
    bad += nd
    print("OK" if bad == 0 else f"ODSTUPANJA: {bad}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
