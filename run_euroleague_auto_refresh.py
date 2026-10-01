from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = [
    "update_active_profiles_prices.py",
    "create_euroleague_fantasy_dashboard.py",
    "create_fantasheet_style_dashboard.py",
    "create_euroleague_advanced_context.py",
    "create_real_dvp_fix.py",
    "create_trilingual_dvp_pages.py",
    "apply_advanced_proj_pir_formula.py",
    "patch_top_projected_pir_card.py",
    "finalize_euroleague_refresh.py",
]


def main() -> None:
    for script in SCRIPTS:
        path = ROOT / "scripts" / script
        print(f"\n=== Running {script} ===", flush=True)
        subprocess.run([sys.executable, str(path)], cwd=str(ROOT), check=True)
    print("\nEuroLeague auto-refresh pipeline finished.")


if __name__ == "__main__":
    main()
