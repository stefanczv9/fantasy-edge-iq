#!/usr/bin/env python3
"""Isti korak kao create_fantasheet_style_dashboard.py, ali sa popravljenim uparivanjem zvanicnih statistika i fantasy igraca.

Problem: originalno uparivanje trazi poklapanje imena >= 80 (token_sort_ratio) unutar istog tima. Igraci cije se ime u zvanicnom
feedu razlikuje od fantasy imena ('Olek Balcerowski' / 'Aleksander Balcerowski', 'PJ Dozier' / 'Perry Dozier') nisu uparivani,
pa su im ovosezonski GP/MIN/PIR u dashboardu ostajali prazni iako su odigrali sve utakmice.

Popravka (samo dodatni prolaz za neuparene): u istom timu, isto prezime, jedinstveno sa obje strane (jedan neupareni zvanicni igrac
i jedan neupareni fantasy igrac sa tim prezimenom) -> upari. Sve ostalo ostaje kako jeste.

Original (create_fantasheet_style_dashboard.py) se ne mijenja jer ga runner pri svakom pokretanju vraca iz paketa; ovaj korak ga
ucita kao modul, zamijeni samo funkciju match_current_official i pokrene isti build().
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("cfs_original", ROOT / "scripts" / "create_fantasheet_style_dashboard.py")
cfs = importlib.util.module_from_spec(spec)
sys.modules["cfs_original"] = cfs
spec.loader.exec_module(cfs)

_original_match = cfs.match_current_official


def _surname(norm: str) -> str:
    toks = str(norm or "").split()
    return toks[-1] if toks else ""


def match_current_official_fixed(players, current_df):
    out = _original_match(players, current_df)
    if out is None or out.empty or "player_id" not in out.columns:
        return out
    used = set(out["player_id"].dropna())
    by_team = {t: g.reset_index(drop=True) for t, g in players.groupby("team_abbr")}
    unmatched = out[out["player_id"].isna()]
    fixed = []
    for i, row in unmatched.iterrows():
        team = row.get("team_abbr_official")
        cand = by_team.get(team)
        sur = _surname(row.get("official_norm"))
        if cand is None or cand.empty or not sur:
            continue
        gp = row.get("gamesPlayed")
        try:
            if gp is None or float(gp) <= 0:
                continue          # samo igraci koji su stvarno igrali
        except Exception:
            continue
        c2 = cand[(~cand["player_id"].isin(used)) & (cand["position"] != "Head Coach")
                  & (cand["norm"].map(_surname) == sur)]
        same_off = unmatched[(unmatched["team_abbr_official"] == team) & (unmatched["official_norm"].map(_surname) == sur)]
        if len(c2) == 1 and len(same_off) == 1:
            pid = c2.iloc[0]["player_id"]
            out.loc[i, "player_id"] = pid
            out.loc[i, "fantasy_name_current_match"] = c2.iloc[0]["name"]
            out.loc[i, "current_match_quality"] = 79.0
            used.add(pid)
            fixed.append(f"{row.get('official_name_full')} ({team}, gp={gp}) -> {c2.iloc[0]['name']}")
    print(f"dodatno uparivanje po prezimenu (isti tim, jedinstveno): {len(fixed)}")
    for f in fixed:
        print("   +", f)
    return out


cfs.match_current_official = match_current_official_fixed

if __name__ == "__main__":
    fanta, players = cfs.build()
    print("Wrote", cfs.OUT_HTML, cfs.OUT_XLSX)
    print("Players:", len(players), "with current minutes:", players["min_avg_current"].notna().sum(),
          "with prev minutes:", players["min_avg_25_26"].notna().sum(), "with any minutes:", players["min_avg_best"].notna().sum())
