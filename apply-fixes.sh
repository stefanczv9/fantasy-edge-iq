#!/usr/bin/env bash
# Fantasy Edge IQ — primjena popravki na tvoj lokalni klon / repo.
# Upotreba (iz korijena repoa fantasy-edge-iq):
#   unzip feiq-fixes.zip -d /tmp/feiq-fixes
#   bash /tmp/feiq-fixes/apply-fixes.sh /tmp/feiq-fixes
# Zatim: git add -A && git commit && git push
set -euo pipefail

SRC="${1:-$(cd "$(dirname "$0")" && pwd)}"
REPO="$(pwd)"

if [ ! -f "$REPO/build.js" ] || [ ! -d "$REPO/.github/workflows" ]; then
  echo "GRESKA: pokreni ovu skriptu iz korijena repoa fantasy-edge-iq (tamo gdje je build.js)."
  exit 1
fi

echo "== 1) uklanjam stare (pogresno postavljene) kopije skriptova iz korijena"
for f in fpl_fetch.py fpl_build_dashboard.py build_static_site.py site_audit.py \
         patch_log_from_official_boxscore.py add_minutes_and_pirmin_cards.py \
         add_shot_share_section.py patch_average_pir_card.py refresh_eurocup.py \
         eurocup_dvp.py audit_eurocup.py update_domestic.py build_pages.py \
         sources.py fs_scan.py fs_box.py; do
  if [ -f "$REPO/$f" ]; then
    git rm -q --cached "$f" 2>/dev/null || true
    rm -f "$REPO/$f"
    echo "   - $f"
  fi
done

echo "== 2) kopiram skriptove na putanje koje .github/workflows/feiq-refresh.yml ocekuje"
mkdir -p "$REPO/scripts/eurocup" "$REPO/scripts/domestic"
(cd "$SRC" && find . -type f \( -name '*.py' -o -name '*.js' \) ! -name 'apply-fixes.sh' -print0) |
  while IFS= read -r -d '' f; do
    rel="${f#./}"
    mkdir -p "$REPO/$(dirname "$rel")"
    cp "$SRC/$rel" "$REPO/$rel"
    echo "   + $rel"
  done

echo "== 3) sintaksna provjera"
python3 - <<'PY'
import ast, pathlib, sys
bad = []
for p in pathlib.Path('scripts').rglob('*.py'):
    try: ast.parse(p.read_text())
    except SyntaxError as e: bad.append((p, e))
print('python OK' if not bad else bad)
sys.exit(1 if bad else 0)
PY
for f in build.js build_round_preview.js build_player_pages.js; do node --check "$f" && echo "node OK $f"; done

echo
echo "== Gotovo. Sljedece:"
echo "   git add -A && git commit -m 'Fix refresh pipeline paths + build fixes' && git push"
echo "   Zatim na GitHubu: Actions -> 'FEIQ auto-refresh' -> Run workflow"
echo "   (workflow sada radi: FPL fetch + EL pipeline + EuroCup + domaca + build + commit)"
