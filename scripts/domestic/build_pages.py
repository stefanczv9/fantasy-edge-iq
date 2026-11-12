#!/usr/bin/env python3
"""Sklapa DATA iz domestic-*.csv i regenerise stranice rubrike Domestic Competitions (EN/SR/EL) za EuroLeague I EuroCup klubove.

Sablon svake stranice je ona ista stranica iz repoa/sa sajta; mijenja se samo DATA JSON i tekstovi uzorka/izvora.
EuroCup stranice se citaju iz repoa; ako ih nema, skidaju se sa sajta.
Pokretanje:  python3 scripts/domestic/build_pages.py [el|ec]      (bez argumenta: oba)
"""
import re, sys, json, math, datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import pandas as pd, numpy as np, requests

HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE)); ROOT = HERE.parent.parent
import update_domestic as U

SITE = "https://www.fantasyedgeiq.com"
MIN_GAMES_AVG = 2
MING_TXT = {"en": " (min. 2 games)", "sr": " (min. 2 utakmice)", "el": " (min. 2 αγώνες)"}
SITES = {
    "el": dict(teams=U.EL, names=U.EL_NAME, label="EuroLeague",
               pages={"en": "euroleague-domestic-competitions.html", "sr": "sr-euroleague-domestic-competitions.html", "el": "el-euroleague-domestic-competitions.html"}),
    "ec": dict(teams=U.EC, names=U.EC_NAME, label="EuroCup",
               pages={"en": "eurocup-domestic-competitions.html", "sr": "sr-eurocup-domestic-competitions.html", "el": "el-eurocup-domestic-competitions.html"}),
}
DESC = {
    "en": "Domestic league and cup results and box-score stats for {club} clubs, kept separate from European competition numbers.",
    "sr": "Rezultati i box score statistika iz domaćih liga i kupova za {club} klubove, odvojeno od evropskih takmičenja.",
    "el": "Αποτελέσματα και box-score στατιστικά από εγχώριες λίγκες και κύπελλα για συλλόγους της {club}, ξεχωριστά από τις ευρωπαϊκές διοργανώσεις.",
}
TXT = {
    "en": {"avg": "Grouped by player/team across all imported domestic games (league, cup and Super Cup rows combined). Rows sourced from Rezultati.com/Flashscore (for example Turkey, France, Germany, Greece and Poland) carry an estimated Avg PIR: the foul components are not available there.",
           "method": "Sources: official ACB Live, LBA game pages, Israel Basketball game-zone pages, ABA League, LKL and ESAKE/GBL data where available. Other games use Rezultati.com/Flashscore game-level box scores because the official box scores are not publicly accessible; minutes and shots are captured, while PIR/RANK is estimated from available stats with the foul components omitted. Games with only a verified final score are marked as result-only and no player rows are fabricated. Cup and Super Cup games are marked separately from league games. Times are shown in Central European Time (CET/CEST)."},
    "sr": {"avg": "Prosjeci su grupisani po igraču i timu kroz sve ubačene domaće utakmice (liga, kup i superkup zajedno). Redovi iz Rezultati.com/Flashscore (npr. Turska, Francuska, Njemačka, Grčka i Poljska) imaju procijenjen prosječan PIR jer tamo nema komponenti ličnih grešaka.",
           "method": "Izvori: zvanični ACB Live, LBA game page, Israel Basketball game-zone, ABA League, LKL i ESAKE/GBL podaci gdje su dostupni. Ostale utakmice koriste Rezultati.com/Flashscore box scoreove po utakmici jer zvanični box scoreovi nisu javno dostupni; minute i šutevi su preuzeti, a PIR/RANK je procjena iz dostupnih statistika bez komponenti ličnih grešaka. Utakmice sa potvrđenim samo konačnim rezultatom označene su kao result-only i igrački redovi se ne izmišljaju. Kup i superkup utakmice označene su posebno od ligaških. Vremena su prikazana po srednjoevropskom vremenu (CET/CEST)."},
    "el": {"avg": "Μέσοι όροι ανά παίκτη/ομάδα για όλα τα imported domestic games (λίγκα, κύπελλο και Super Cup μαζί). Οι γραμμές από Rezultati.com/Flashscore (π.χ. Τουρκία, Γαλλία, Γερμανία, Ελλάδα και Πολωνία) έχουν estimated Avg PIR, επειδή εκεί δεν υπάρχουν τα fouls components.",
           "method": "Πηγές: official ACB Live, LBA game pages, Israel Basketball game-zone, ABA League, LKL και ESAKE/GBL όπου υπάρχει. Οι υπόλοιποι αγώνες χρησιμοποιούν game-level box scores από Rezultati.com/Flashscore, γιατί τα official box scores δεν είναι δημόσια διαθέσιμα· λεπτά και σουτ καταγράφονται, ενώ το PIR/RANK είναι εκτίμηση χωρίς τα fouls components. Αγώνες με επιβεβαιωμένο μόνο τελικό σκορ σημειώνονται ως result-only και δεν δημιουργούνται στατιστικά παικτών. Cup και Super Cup αγώνες σημειώνονται ξεχωριστά από τους αγώνες λίγκας. Οι ώρες εμφανίζονται σε ώρα Κεντρικής Ευρώπης (CET/CEST)."},
}


def clean(v):
    if v is None: return None
    if isinstance(v, (np.integer,)): return int(v)
    if isinstance(v, (np.floating, float)):
        return None if (math.isnan(v) or math.isinf(v)) else float(v)
    if isinstance(v, (np.bool_, bool)): return bool(v)
    return v
def recs(df): return [{k: clean(v) for k, v in r.items()} for r in df.to_dict("records")]


def build_data(site):
    S = SITES[site]; TEAMS = S["teams"]
    g = pd.read_csv(ROOT / "domestic-games.csv", dtype={"round": str}); p = pd.read_csv(ROOT / "domestic-player-boxscores.csv", dtype={"round": str})
    t = pd.read_csv(ROOT / "domestic-team-boxscores.csv", dtype={"round": str}); a = pd.read_csv(ROOT / "domestic-player-averages.csv")
    gl = g[g["home_abbr"].isin(TEAMS) | g["away_abbr"].isin(TEAMS)].sort_values(["date_local", "league", "game_id"], kind="mergesort").reset_index(drop=True)
    pl = p[p["team_abbr"].isin(TEAMS) & (~p["is_total"].astype(bool))].reset_index(drop=True)
    tl = t[t["team_abbr"].isin(TEAMS)].reset_index(drop=True)
    al = a[a["team_abbr"].isin(TEAMS)].reset_index(drop=True)
    srt = lambda df, c: df.sort_values(c, ascending=False, kind="mergesort").head(12)
    # liste lidera po prosjeku: igraci sa 1 utakmicom (npr. 32 PIR u jednoj utakmici) ne smiju voditi -> min. 2 utakmice
    qual = al[al["games_played"] >= MIN_GAMES_AVG]; pool = qual if len(qual) >= 12 else al
    cov = []
    for ab in TEAMS:
        n_g = int(((gl["home_abbr"] == ab) | (gl["away_abbr"] == ab)).sum()); n_r = int((pl["team_abbr"] == ab).sum())
        gids = set(gl[(gl["home_abbr"] == ab) | (gl["away_abbr"] == ab)]["game_id"]); with_rows = set(pl[pl["team_abbr"] == ab]["game_id"])
        no_rows = len(gids - with_rows); n_avg = int((al["team_abbr"] == ab).sum())
        if n_g == 0: st, note = "pending", "No completed domestic games yet."
        elif n_r == 0 and n_avg:
            st = "average-only"; note = f"Result + season averages imported ({int(al[al['team_abbr'] == ab]['games_played'].max())} games in averages table); no fabricated game-level rows."
        elif n_r == 0: st, note = "result-only", f"{n_g} verified completed domestic result(s) imported; no player rows because a complete/static boxscore was not available."
        else:
            st = "extracted"; note = f"{n_g} completed game(s), {n_r} player rows imported."
            if no_rows: st = "partial"; note += f" {no_rows} game(s) have result only."
        cov.append({"team": f"{ab} — {S['names'][ab]}", "status": st, "note": note})
    base = {"games": recs(gl[U.GAME_COLS]), "players": recs(pl[U.BOX_COLS]), "totals": recs(tl[U.BOX_COLS]), "averages": recs(al[U.AVG_COLS]),
            "topAvgMin": recs(srt(pool, "avg_minutes")), "topAvgPir": recs(srt(pool, "avg_pir")),
            "topRank": recs(srt(pl, "rank")[U.BOX_COLS]), "topPoints": recs(srt(pl, "pts")[U.BOX_COLS]), "topMinutes": recs(srt(pl, "minutes")[U.BOX_COLS]),
            "coverage": cov, "targetTeams": TEAMS, "elTeams": TEAMS}
    return base, len(gl), len(pl), gl


def extract_data(t):
    i = t.find("const DATA="); j = t.find("{", i); d = 0; ins = False; esc = False; k = j
    while k < len(t):
        c = t[k]
        if ins:
            if esc: esc = False
            elif c == "\\": esc = True
            elif c == '"': ins = False
        else:
            if c == '"': ins = True
            elif c == "{": d += 1
            elif c == "}":
                d -= 1
                if d == 0: return json.loads(t[j:k + 1]), j, k + 1
        k += 1
    raise ValueError("DATA not found")


def read_template(fn, lang):
    p = ROOT / fn
    if p.exists(): return p.read_text(encoding="utf-8")
    r = requests.get(SITE + "/" + fn[:-5], timeout=60)
    r.raise_for_status()
    return r.text


def main(which):
    now = datetime.datetime.now(ZoneInfo("Europe/Zagreb")); stamp = now.strftime("%Y-%m-%d %H:%M ") + ("CEST" if now.dst() else "CET")
    for site in which:
        S = SITES[site]
        htmls = {}; labels = {}
        for lg, f in S["pages"].items():
            t = read_template(f, lg); d, _, _ = extract_data(t); labels[lg] = d["labels"]; htmls[lg] = t
        base, ng, npl, gl = build_data(site)
        for lg, f in S["pages"].items():
            t = htmls[lg]; _, a, b = extract_data(t)
            data = {"generated": stamp, **{k: base[k] for k in ["games", "players", "totals", "averages", "topAvgMin", "topAvgPir", "topRank", "topPoints", "topMinutes", "coverage"]},
                    "labels": {**labels[lg], "averages_note": TXT[lg]["avg"], "method_text": TXT[lg]["method"]}, "targetTeams": S["teams"], "elTeams": S["teams"]}
            js = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
            t = t[:a] + js + t[b:]
            desc = DESC[lg].format(club=S["label"])
            t = re.sub(r'(<meta name="description" content=")[^"]*(")', lambda m: m.group(1) + desc + m.group(2), t, count=1)
            t = re.sub(r'(<section[^>]*id="averages"[^>]*>\s*<h2>[^<]*</h2><div class="note">)(.*?)(</div>)', lambda m: m.group(1) + TXT[lg]["avg"] + m.group(3), t, count=1, flags=re.S)
            t = re.sub(r'(<section[^>]*id="method"[^>]*>.*?<div class="note">)(.*?)(</div>)', lambda m: m.group(1) + TXT[lg]["method"] + m.group(3), t, count=1, flags=re.S)
            for box in ("rankBox", "pointsBox"):
                t = re.sub(r'(<h3>)([^<]*?)(?: \(min\. 2 [^)]*\))?(</h3><div id="' + box + '">)', lambda m: m.group(1) + m.group(2) + MING_TXT[lg] + m.group(3), t, count=1)
            t = t.replace('href="/sr/euroleague/team-analyzer"', 'href="/euroleague/team-analyzer"').replace('href="/el/euroleague/team-analyzer"', 'href="/euroleague/team-analyzer"')
            (ROOT / f).write_text(t, encoding="utf-8")
            print(f"{f}: {len(t) // 1024} KB | generated {stamp}")
        cov = pd.DataFrame(base["coverage"]); print(site.upper(), cov["status"].value_counts().to_dict(), f"| utakmica: {ng} | redova igraca: {npl} | zemalja: {gl['country'].nunique()}")
        print("latest:", [(r.date_local, r.home_abbr, r.home_score, r.away_score, r.away_abbr) for r in gl.sort_values('date_local', ascending=False).head(3).itertuples()])


if __name__ == "__main__":
    arg = [a for a in sys.argv[1:] if a in SITES]
    main(arg or ["el", "ec"])
