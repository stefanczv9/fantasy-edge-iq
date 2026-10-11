# Upload — EuroLeague poslije 4. kola, Domaća takmičenja, Average PIR so far

Stanje u paketu: **2026-10-10 12:32 CEST** (domaća takmičenja 12:08) · 40 utakmica, DvP 40/40 validirano · 50 domaćih utakmica.

## PAKET 1 — `fantasy-edge-iq-site-upload.zip` (obavezno)

23 fajla, **svi idu u KORIJEN repoa**. U ZIP-u nema podfoldera i nema nijednog `index.html`, pa ne može prepisati početnu stranicu.

1. Raspakuj ZIP.
2. GitHub → *Add file* → *Upload files*.
3. Prevuci svih 23 fajla odjednom → *Commit changes*.
4. Sačekaj Vercel deploy (1–2 min).

**Ne uploaduj folder `public/`** — Vercel ga sam pravi iz korijenskih fajlova (`npm run build`). Stari paket je imao 13 fajlova
`index.html` u `public/` podfolderima; spljošten upload ih je slivao u korijen i zadnji je postajao početna stranica.

Provjera poslije deploya:
- `/` , `/sr` , `/el` — ostaju kao prije (početna sa EuroCup menijem)
- `/euroleague/dashboard` (+ `/sr`, `/el`) — gore piše 2026-10-10 12:32 CEST, prva kartica je „Average PIR so far"
- `/euroleague/domestic-competitions` (+ `/sr`, `/el`) — 50 utakmica
- `/euroleague-shot-share.csv` — otvara se

## Ako se početna ikad pokvari

`popravka-pocetne.zip` sadrži samo `index.html` (kopija ispravne početne sa sajta, 2026-10-10). Uploaduj ga u korijen repoa uz *overwrite*.

## PAKET 2 — `fantasy-edge-iq-skripte-i-podaci.zip` (neobavezno)

`scripts/`, `euroleague_fantasy_data/` i runner. Sajt ih ne koristi; potrebni su samo za sljedeće osvježavanje.
Osvježavanje: `python3 scripts/run_euroleague_auto_refresh.py` → `python3 scripts/domestic/update_domestic.py` →
`python3 scripts/domestic/build_pages.py` → `python3 scripts/site_audit.py <URL>`.

## Napomene

- Paket ne sadrži početne stranice, sitemap, robots, `package.json`, `vercel.json` ni EuroCup stranice.
- `domestic-*.csv` dijele se sa EuroCup rubrikom: postojeći redovi su ostali, dodane su samo utakmice EuroLeague klubova.
- Poznato (van paketa): SR i EL EuroCup stranice domaćih takmičenja linkuju `/sr|el/euroleague/team-analyzer` (404). Rješenje: u
  `vercel.json` redirect `/sr/euroleague/team-analyzer` i `/el/euroleague/team-analyzer` na `/euroleague/team-analyzer`.
