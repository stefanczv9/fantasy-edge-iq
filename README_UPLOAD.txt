Fantasy Edge IQ homepage beta polish update

This update improves the homepage after removing Pricing:
- stronger free public beta positioning
- clear no-payment / no-password message
- trust bar: Free during beta, No passwords, Independent project
- better mobile CTA behavior
- keeps Pricing removed from sitemap/build output

Upload/replace these files in the GitHub repository root:
- index.html
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
