# Fantasy Edge IQ automatic update pack

This pack adds a GitHub Actions workflow that refreshes the EuroLeague and FPL dashboards automatically and commits the updated static files back to the repository. Vercel will then redeploy from the new commit.

## What it updates

- EuroLeague fantasy profiles/prices for known active players
- EuroLeague schedule, fantasy points log, player value table and advanced matchup context
- EuroLeague full player CSV, team context CSV and next-five schedule CSV
- FPL players, fixtures, player history and dashboard
- Homepage/SEO pages, sitemap and robots file

## How to install

Upload the contents of this pack to the root of your GitHub repository. It contains folders, so the easiest safe method is:

1. In GitHub, create a new file named `.github/workflows/update-dashboards.yml` and paste the workflow content from this pack.
2. Upload the `scripts` folder, `requirements.txt`, `.gitignore`, `fantasy_profiles_active.json` and `euroleague_fantasy_data` folder.
3. Commit changes.
4. Go to GitHub → Actions → `Update fantasy dashboards` → Run workflow.

If the workflow succeeds, it will commit refreshed files and Vercel will redeploy automatically.

## Notes

The first run can take several minutes because it fetches FPL element summaries and EuroLeague player/stat data. If EuroLeague official current-season stats are temporarily empty, the scripts use cached official CSV files as fallback.
