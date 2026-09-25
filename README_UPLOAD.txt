Fantasy Edge IQ brand + SEO polish update

Upload/replace these files in the GitHub repository root:
- index.html
- euroleague-dashboard.html
- euroleague-team-analyzer.html
- premier-league-dashboard.html
- premier-league-team-analyzer.html
- about.html
- methodology.html
- pricing.html
- privacy.html
- terms.html
- disclaimer.html
- og-image.png
- apple-touch-icon.png
- favicon.svg
- site.webmanifest
- package.json
- requirements.txt
- scripts/build_static_site.py

Important:
- Do not upload the parent folder as a new folder. Upload the contents into the repository root.
- Keep scripts/build_static_site.py inside the existing scripts folder.
- Do not delete api, data, public, or workflow files.
- package.json now copies PNG/SVG/webmanifest files into the Vercel public output.
- requirements.txt includes Pillow so the scheduled automation can regenerate the social preview/icon assets.
