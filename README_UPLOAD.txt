Fantasy Edge IQ — Advanced Proj PIR full upload package

Upload everything in this folder to the GitHub repository root and commit.

This package fixes Proj PIR with the advanced formula:
Proj PIR = current PIR/min × projected minutes × matchup factor × risk factor

Current implementation:
- Uses current EuroLeague season only for player PIR/min and minutes.
- No previous-season PIR blend is used.
- Uses next opponent context: opponent PIR allowed, opponent pace, home/away.
- Uses Defense vs Position from real points allowed by position only, not fantasy points.
- Uses risk factor for injury flag, bench flag, small sample and low-minute volatility.
- Column name remains Proj PIR.
- Floor, ceiling, price gap and option score are recalculated from the advanced Proj PIR.

Also included:
- EuroLeague Dashboard EN / SR / EL.
- Defense vs Position EN / SR / EL, real points only.
- Mobile language selector EN / SR / EL.
- No Pricing page/links.
- No visible “free during beta” emphasis.
- FPL analyzer API function at /api/fpl-team-analyzer.js.
- package.json uses inline bash build; no /scripts folder is required.

Do NOT upload old public/ output or old scripts/ folders from previous packages.
Vercel will build public/ automatically after commit.
