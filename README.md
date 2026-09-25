# FPL API fix

Upload the `api` folder to the root of the GitHub repository.

Expected GitHub path:

`api/fpl-team-analyzer.js`

After commit, Vercel will redeploy. Then test:

`https://fantasyedgeiq.com/api/fpl-team-analyzer?teamId=6744933`

It should return JSON, not 404.
