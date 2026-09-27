Fantasy Edge IQ build fix WITHOUT scripts folder

Use this because GitHub browser upload did not keep the scripts folder.

Upload/replace ONLY these files in the GitHub repository root:
- package.json
- euroleague-dashboard.html
- euroleague-defense-vs-position.html
- euroleague-defense-vs-position.csv
- euroleague-defense-vs-position-matchlog.csv
- sitemap.xml

Important:
- This fix does NOT need a scripts folder.
- Serbian/Greek language files are optional and can be uploaded later.
- The new package.json build command skips missing optional language files, so Vercel will not fail if you have not uploaded them yet.
- Do not delete api, data, public, or workflow files.

Commit message:
Fix build without scripts folder

After commit, Vercel should deploy. If it does not start automatically, click Redeploy.
Then check:
https://www.fantasyedgeiq.com/euroleague/defense-vs-position
