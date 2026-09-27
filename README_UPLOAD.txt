Fantasy Edge IQ — Realistic Proj PIR full upload package

Upload everything in this folder to the GitHub repository root and commit.

This package updates Proj PIR to be more realistic early in the season:
Proj PIR = stabilized base PIR × matchup factor × risk factor

Stabilized base PIR:
- current role PIR = current PIR/min × projected minutes
- market baseline = player price × 1.35
- sample weight = current games played / 5, capped at 1.0
- stabilized base = sample weight × current role PIR + (1 - sample weight) × market baseline

This means a player with 30 PIR in Round 1 is NOT projected for 30 again automatically.
After one game, only 20% of the projection comes from that game and 80% comes from the market/price baseline.
As more rounds are played, current-season performance gets more weight.

Matchup/risk factors:
- next opponent PIR allowed
- opponent pace
- home/away
- Defense vs Position using real points by position only, not fantasy points
- injury flag, bench flag and low-minute volatility

Also included:
- Column name remains Proj PIR.
- Recalculated floor, ceiling, price gap and option score.
- EuroLeague Dashboard EN / SR / EL.
- Defense vs Position EN / SR / EL, real points only.
- Mobile language selector EN / SR / EL.
- No Pricing page/links.
- No visible “free during beta” emphasis.
- FPL analyzer API function at /api/fpl-team-analyzer.js.
- package.json uses inline bash build; no /scripts folder is required.

Do NOT upload old public/ output or old scripts/ folders from previous packages.
Vercel will build public/ automatically after commit.
