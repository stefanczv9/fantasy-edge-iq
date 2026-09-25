Fantasy Edge IQ remove-pricing update

Why this update exists:
- The site is free during beta, so a public Pricing page is unnecessary now.
- Pricing has been removed from navigation, footer, sitemap and build output.
- Old /pricing and /pricing.html URLs now redirect to the homepage.

Upload/replace these files in the GitHub repository root:
- index.html
- euroleague-dashboard.html
- euroleague-team-analyzer.html
- premier-league-dashboard.html
- premier-league-team-analyzer.html
- about.html
- methodology.html
- privacy.html
- terms.html
- disclaimer.html
- sitemap.xml
- robots.txt
- package.json
- vercel.json
- requirements.txt
- og-image.png
- apple-touch-icon.png
- favicon.svg
- site.webmanifest
- scripts/build_static_site.py

Important:
- Do not upload this parent folder as a new folder. Upload the contents into the repository root.
- Keep scripts/build_static_site.py inside the existing scripts folder.
- Do not delete api, data, public, or workflow files.
- Optional cleanup: if GitHub still shows pricing.html in the repository root, you can delete it later. The live Vercel build already removes it from public output and redirects /pricing.
