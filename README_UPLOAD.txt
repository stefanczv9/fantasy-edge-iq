Fantasy Edge IQ Defense vs Position update

This update adds a validated EuroLeague Defense vs Position page:
- /euroleague/defense-vs-position

Files included:
- euroleague-defense-vs-position.html
- euroleague-defense-vs-position.csv
- euroleague-defense-vs-position-matchlog.csv
- euroleague-dashboard.html
- sitemap.xml
- package.json
- scripts/build_static_site.py

What the feature does:
- Real PTS allowed by position: Guards / Forwards / Centers
- Fantasy PTS allowed by position: Guards / Forwards / Centers
- Validation: real position points are checked against the official box-score points allowed
- Matchlog CSV is included so validation can be audited
- Early sample / beta warning is shown because the season sample is still small

Important:
- Do not upload this parent folder as a folder. Upload the contents into the repository root.
- Keep scripts/build_static_site.py inside the existing scripts folder.
- Do not delete api, data, public, or workflow files.
- This keeps Pricing removed.

After deployment, check:
https://www.fantasyedgeiq.com/euroleague/defense-vs-position
