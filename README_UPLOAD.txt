Fantasy Edge IQ mobile QA polish update

This update improves mobile usability across the live site:
- better dashboard/analyzer spacing on phones
- horizontal tab scrolling without broken wrapping
- full-width filters/forms where useful on mobile
- large stat tables show a "Swipe sideways" hint
- first table column stays visible while horizontally scrolling
- safer touch target height for buttons/inputs
- Pricing remains removed and redirected
- Vercel Analytics and brand/social tags remain in all pages

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
