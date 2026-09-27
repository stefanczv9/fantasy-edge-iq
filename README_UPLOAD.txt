Fantasy Edge IQ — Role/Usage Projected PIR full upload package

Upload everything in this folder to the GitHub repository root and commit.

Projected PIR model:
Projected PIR = Projected Minutes × Base PIR/min × Matchup Factor × Risk Factor

Base PIR/min model:
- Season PIR/min is regressed for small samples.
- Last10 and Last5 are included as model fields; until enough reliable game-level PIR/min data exists, they fall back to the regressed season PIR/min.
- Role/Usage PIR/min adjusts the regressed rate with FGA/min usage, capped so one hot game does not dominate.
- Formula structure: 0.40 Season + 0.25 L10 + 0.15 L5 + 0.20 Role/Usage.

Small sample realism:
- One game does not become the full projection.
- Raw PIR/min is regressed toward a prior built from player price and position league average.
- After 1 game, sample weight is 20%; after 5+ games, current-season data gets full weight.

Projected minutes:
- Uses current minutes plus a price-based minutes baseline, also sample weighted.
- Starter/bench signal applies a mild adjustment.

Matchup context:
- Opponent PIR allowed / league average.
- Pace factor.
- Home/away factor.
- Real-points-only Defense vs Position by player position. No fantasy-points-allowed DvP is used.

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
