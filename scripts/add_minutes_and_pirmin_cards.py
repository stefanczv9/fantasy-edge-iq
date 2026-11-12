"""
Dodaje current-season MIN/G kolonu + karticu i vraca PIR/min lidere u EN/SR/EL dashboard.

Pravila (po dogovoru):
- minutes_per_game = min_avg_current, SAMO ako gp_current > 0 i min_avg_current nije prazan.
  Nema fallbacka na min_avg_best / min_avg_25_26 / prosle sezone.
- minutesLeaders: gp_current > 0, min_avg_current != null, nije povrijedjen, nije Head Coach.
- pirPerMinLeaders: pir_per_min_current != null, min_avg_current >= 10, gp_current > 0,
  nije povrijedjen, nije Head Coach.
- Shane Larkin (i svako bez current minuta) ne smije se pojaviti ni u jednoj od te dvije liste.
- usageLeaders ("Highest shot usage"): isto pravilo kao PIR/min (current sezona, min. 10 MIN/G, gp_current > 0, bez HC i povrijedjenih).

Skripta je idempotentna: moze se pokrenuti vise puta bez dupliranja kartica/kolona.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT

MIN_MINUTES_FOR_PIR_PER_MIN = 10.0
TOP_N = 12

LANG = {
    "euroleague-dashboard.html": {
        "tab_label": "MIN/G",
        "pir_label": "PIR/min",
        "card_title": "Most minutes per game",
        "card_note": "Current season only",
        "usage_note": "Min 10 minutes per game, current season",
    },
    "sr-euroleague-dashboard.html": {
        "tab_label": "MIN/G",
        "pir_label": "PIR/min",
        "card_title": "Najvi\u0161e minuta po utakmici",
        "card_note": "Samo ova sezona",
        "usage_note": "Min. 10 minuta po utakmici, ova sezona",
    },
    "el-euroleague-dashboard.html": {
        "tab_label": "\u039c\u0399\u039d/\u03b1\u03b3",
        "pir_label": "PIR/\u03bb\u03b5\u03c0\u03c4\u03cc",
        "card_title": "\u03a0\u03b5\u03c1\u03b9\u03c3\u03c3\u03cc\u03c4\u03b5\u03c1\u03b1 \u03bb\u03b5\u03c0\u03c4\u03ac \u03b1\u03bd\u03ac \u03b1\u03b3\u03ce\u03bd\u03b1",
        "card_note": "\u039c\u03cc\u03bd\u03bf \u03c4\u03c1\u03ad\u03c7\u03bf\u03c5\u03c3\u03b1 \u03c3\u03b5\u03b6\u03cc\u03bd",
        "usage_note": "\u0395\u03bb\u03ac\u03c7\u03b9\u03c3\u03c4\u03bf 10 \u03bb\u03b5\u03c0\u03c4\u03ac \u03b1\u03bd\u03ac \u03b1\u03b3\u03ce\u03bd\u03b1, \u03c4\u03c1\u03ad\u03c7\u03bf\u03c5\u03c3\u03b1 \u03c3\u03b5\u03b6\u03cc\u03bd",
    },
}


def extract_json(text: str, marker: str = "const DATA="):
    i = text.find(marker)
    if i < 0:
        return None
    j = text.find("{", i)
    if j < 0:
        return None
    depth, k, instr, esc = 0, j, False, False
    while k < len(text):
        c = text[k]
        if instr:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                instr = False
        else:
            if c == '"':
                instr = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return json.loads(text[j : k + 1])
        k += 1
    return None


def dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), default=str)


def num(v):
    try:
        if v is None:
            return None
        f = float(v)
        if f != f:  # NaN
            return None
        return f
    except Exception:
        return None


def keep(p: dict) -> bool:
    if str(p.get("pos_short") or "").upper() == "HC":
        return False
    if bool(p.get("is_injured")):
        return False
    return True


def minutes_per_game(p: dict):
    gp = num(p.get("gp_current"))
    mins = num(p.get("min_avg_current"))
    if gp is None or gp <= 0 or mins is None:
        return None
    return round(mins, 1)


def patch_html(text: str, spec: dict) -> tuple[str, list[str]]:
    notes: list[str] = []

    # 1) sigurni mini(): ne pucaj ako liste nema ili element ne postoji
    old_mini = "function mini(el,rows,main,sub,extra){document.getElementById(el).innerHTML=rows.map("
    new_mini = ("function mini(el,rows,main,sub,extra){const box=document.getElementById(el);"
                "if(!box)return;rows=rows||[];box.innerHTML=rows.map(")
    if old_mini in text:
        text = text.replace(old_mini, new_mini, 1)
        notes.append("mini() safety")

    # 2) MIN/G kolona se formatira kao broj
    if "minutes_per_game" not in text.split("const numCols=")[1].split(");")[0]:
        text = re.sub(r"(const numCols=new Set\(\[[^\]]*?)(\]\);)", r"\1,'minutes_per_game'\2", text, count=1)

    # 3) kartica "Most minutes per game"
    if 'id="minutesBox"' not in text:
        anchor = '<div id="pirMinBox"></div></div>'
        card = (anchor
                + '<div class="card"><h3>' + spec["card_title"] + '</h3>'
                + '<div class="mut" style="font-size:12px;margin:-6px 0 8px">' + spec["card_note"] + '</div>'
                + '<div id="minutesBox"></div></div>')
        if anchor in text:
            text = text.replace(anchor, card, 1)
            notes.append("kartica MIN/G dodata")
        else:
            notes.append("UPOZORENJE: anchor za PIR/min karticu nije nadjen")

    # 4) mini() poziv za novu karticu
    if "mini('minutesBox'" not in text:
        pir_call = "mini('pirMinBox',DATA.pirPerMinLeaders,'name','pir_per_min_current','team_abbr');"
        if pir_call in text:
            text = text.replace(pir_call, pir_call + "mini('minutesBox',DATA.minutesLeaders,'name','minutes_per_game','team_abbr');", 1)

    # 5) "Highest shot usage": samo current sezona, min. 10 MIN/G (bez toga vode igraci sa 1-4 minute: 3 FGA u 3.85 min = 0.78/min)
    old_usage = "mini('usageBox',DATA.usageLeaders,'name','fg_attempts_per_min_best','team_abbr');"
    if old_usage in text:
        text = text.replace(old_usage, "mini('usageBox',DATA.usageLeaders,'name','fg_attempts_per_min_current','team_abbr');", 1)
        notes.append("usage kartica: current sezona")
    if spec.get("usage_note") and spec["usage_note"] not in text:
        text, n = re.subn(r'(<h3>[^<]*</h3>)(<div id="usageBox">)',
                          lambda m: m.group(1) + '<div class="mut" style="font-size:12px;margin:-6px 0 8px">' + spec["usage_note"] + '</div>' + m.group(2),
                          text, count=1)
        if n:
            notes.append("usage kartica: podnaslov")

    return text, notes


def main() -> None:
    # --- CSV: dodaj minutes_per_game (current season only) ---
    csv_path = SITE / "euroleague-players-full.csv"
    df = pd.read_csv(csv_path)
    if "minutes_per_game" in df.columns:
        df = df.drop(columns=["minutes_per_game"])
    df["minutes_per_game"] = [
        None if (num(g) is None or num(g) <= 0 or num(m) is None) else round(float(m), 1)
        for g, m in zip(df.get("gp_current"), df.get("min_avg_current"))
    ]
    df.to_csv(csv_path, index=False)
    print("CSV: minutes_per_game dodat u", csv_path.name)

    larkin_rows = df[df["name"].eq("Shane Larkin")]
    if len(larkin_rows):
        lk = larkin_rows.iloc[0]
        print(f"Larkin kontrol: gp_current={lk.get('gp_current')} "
              f"min_avg_current={lk.get('min_avg_current')} minutes_per_game={lk.get('minutes_per_game')}")

    for filename, spec in LANG.items():
        path = SITE / filename
        text = path.read_text(encoding="utf-8")
        data = extract_json(text)
        if data is None:
            print("PRESKACEM (nema DATA):", filename)
            continue

        players = data.get("players") or []
        for p in players:
            p["minutes_per_game"] = minutes_per_game(p)

        # kolone u tabeli
        for key in ("pcolsMain", "pcolsFull"):
            cols = data.get(key)
            if not isinstance(cols, list):
                cols = list(cols or [])
            cols = [c for c in cols if c != "minutes_per_game"]
            if key == "pcolsMain":
                if "pir_per_min_current" not in cols:
                    insert_at = cols.index("form_pir") + 1 if "form_pir" in cols else len(cols)
                    cols.insert(insert_at, "pir_per_min_current")
                insert_at = cols.index("form_pir") + 1 if "form_pir" in cols else 0
                cols.insert(insert_at + 1, "minutes_per_game")
            else:
                if "minutes_per_game" not in cols:
                    cols.append("minutes_per_game")
            data[key] = cols

        # labels
        labels = data.get("labels") or {}
        labels["minutes_per_game"] = spec["tab_label"]
        labels["pir_per_min_current"] = spec["pir_label"]
        data["labels"] = labels

        # lideri
        pool = [p for p in players if keep(p) and minutes_per_game(p) is not None]
        pir_pool = [p for p in pool
                    if num(p.get("pir_per_min_current")) is not None
                    and (num(p.get("min_avg_current")) or 0) >= MIN_MINUTES_FOR_PIR_PER_MIN]
        usage_pool = [p for p in players if keep(p) and (num(p.get("gp_current")) or 0) > 0
                      and (num(p.get("min_avg_current")) or 0) >= MIN_MINUTES_FOR_PIR_PER_MIN
                      and num(p.get("fg_attempts_per_min_current")) is not None]
        data["usageLeaders"] = sorted(usage_pool, key=lambda p: num(p.get("fg_attempts_per_min_current")), reverse=True)[:TOP_N]
        data["minutesLeaders"] = sorted(pool, key=lambda p: minutes_per_game(p), reverse=True)[:TOP_N]
        data["pirPerMinLeaders"] = sorted(pir_pool, key=lambda p: num(p.get("pir_per_min_current")), reverse=True)[:TOP_N]

        text = text.replace(
            re.search(r"const DATA=.*?;\nconst numCols=", text, flags=re.S).group(0),
            "const DATA=" + dumps(data) + ";\nconst numCols=",
            1,
        )
        text, notes = patch_html(text, spec)
        path.write_text(text, encoding="utf-8")

        top_min = data["minutesLeaders"][0] if data["minutesLeaders"] else {}
        top_ppm = data["pirPerMinLeaders"][0] if data["pirPerMinLeaders"] else {}
        larkin = [p["name"] for p in data["minutesLeaders"] if p.get("name") == "Shane Larkin"]
        print(f"{filename}: MIN/G lider {top_min.get('name')} {top_min.get('minutes_per_game')} | "
              f"PIR/min lider {top_ppm.get('name')} {top_ppm.get('pir_per_min_current')} | "
              f"Larkin u MIN/G: {bool(larkin)} | {', '.join(notes) if notes else 'bez promjena HTML'}")

    print("add_minutes_and_pirmin_cards.py finished")


if __name__ == "__main__":
    main()
