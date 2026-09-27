Fantasy Edge IQ EuroLeague dashboard translation update

This update translates the EuroLeague dashboard UI into Serbian and Greek.

Routes after deployment:
- /euroleague/dashboard
- /sr/euroleague/dashboard
- /el/euroleague/dashboard

Included:
- euroleague-dashboard.html with EN/SR/EL selector pointing to dashboard routes
- sr-euroleague-dashboard.html
- el-euroleague-dashboard.html
- sr-euroleague.html and el-euroleague.html updated with localized dashboard links
- package.json no-scripts build updated to publish localized dashboard routes
- sitemap.xml updated with localized dashboard URLs

What is translated:
- page title/description
- navigation and language selector
- tabs
- section titles
- notes/download buttons/search placeholders
- table column labels inside the dashboard

Player names, team names and basketball abbreviations stay as original data.

Upload/replace the CONTENTS of this folder in the GitHub repository root.
Do NOT upload the parent folder as a folder.
No scripts folder is needed.

Commit message:
Add translated EuroLeague dashboards

After deploy, check:
- https://www.fantasyedgeiq.com/euroleague/dashboard
- https://www.fantasyedgeiq.com/sr/euroleague/dashboard
- https://www.fantasyedgeiq.com/el/euroleague/dashboard
