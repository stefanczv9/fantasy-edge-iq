FANTASY EDGE IQ — UPDATE PAKET 2026-10-19
==========================================

Sta je azurirano (sve provjereno audit skriptama, 0 gresaka):
  - EuroLeague: cijene, popularnost, povrede, next-5 raspored (kolo 7, od 21.10.),
    projekcije, DvP, Shot Share, Lineup IQ — EN/SR/EL. Generisano: 2026-10-19 18:15 CEST
  - EuroCup: 557 igraca, 380 sa zvanicnim stats-om, cijene za kolo 4 — EN/SR/EL.
    Generisano: 2026-10-19 18:17 CEST
  - FPL: GW7, GW8 najava, deadline 23.10. 19:30. 668 igraca, 380 utakmica.
    Generisano: 2026-10-19 18:17 CEST
  - Domaca takmicenja: +38 novih utakmica iz vikenda 17-19.10.
    (EL klubovi: 86 utakmica / 9 zemalja; EuroCup klubovi: 136 / 14 zemalja).
    Generisano: 2026-10-19 18:12 CEST
  - Svi CSV fajlovi (players-full, team-context, next5, shot-share, DvP, matchlog, FPL)

KAKO UPLOADOVATI (GitHub web, ~3 minute):
  1. Raspakuj FEIQ-UPDATE-2026-10-19.zip na racunar.
  2. Otvori svoj repo na github.com -> "Add file" -> "Upload files".
  3. Prevuci SVE fajlove iz raspakovanog foldera (README ne moras).
     GitHub pita za overwrite -> potvrdi.
  4. "Commit changes" -> Commit directly to the main branch -> Commit changes.
  5. Vercel sam pokrece build i deploy (1-2 minuta).
  6. Provjeri sajt: /euroleague/dashboard treba da pise "2026-10-19 18:15 CEST",
     /eurocup/dashboard "18:17", /premier-league/dashboard "18:17".

PREPORUCENO (da repo ostane zdrav za sledece refresh-eve):
  7. FEIQ-skripte-data-2026-10-19.zip: raspakuj i uploaduj SADRZAJ
     (folderi scripts/, euroleague_fantasy_data/, eurocup_fantasy_data/ + root fajlovi).
  8. FEIQ-fpl-data-2026-10-19.zip: uploaduj folder fpl_fantasy_data/
     i fajl create_fantasheet_style_dashboard.py.

STA JE POPRAVLJENO U SKRIPTAMA (trajno, u ovom paketu):
  - scripts/run_euroleague_auto_refresh.py: sintaksna greska + stariji payload
    sa 9 koraka (umjesto 13) — sinhronizovan sa popravljenim korijenskim verzijama.
  - U scripts/ dodati fajlovi koji su nedostajali (patch_log_from_official_boxscore.py,
    add_minutes_and_pirmin_cards.py, add_shot_share_section.py, patch_average_pir_card.py,
    create_fantasheet_style_dashboard_fixed.py, site_audit.py, build_static_site.py,
    build_upload_package.py + podfolderi scripts/eurocup/ i scripts/domestic/).
  - Zvanicni feed je promijenio imena: "PJ Dozier" i "Olek Balcerowski" — dodata
    tabela verifikovanih aliasa (CURRENT_NAME_ALIASES) u create_fantasheet_style_dashboard.py
    i u payload runner-a; audit sada 268/268 igraca, 0 odstupanja.


NOVO U OVOM PAKETU — SEO MASINA (faza 1):
  - build.js + build_player_pages.js: Vercel build sada SAM generise 1.665 profilnih
    stranica iz tvojih CSV podataka:
      /euroleague/players/  + 365 stranica igraca + 20 timova
      /premier-league/players/ + 668 stranica + 20 klubova
      /eurocup/players/ + 557 stranica + 32 tima
    Svaka stranica: cijena, promjena, minute, PIR/PPG, projekcije, popularnost,
    next-5 raspored sa FDR, JSON-LD schema, canonical, meta opis (engleski).
  - sitemap.xml u public/ automatski dobija svih 1.665 URL-ova (ukupno 1.694).
  - NISTA ne uploadujes rucno za ovo: dovoljno je da build.js i build_player_pages.js
    stignu u repo (jesu u ovom zipu) — Vercel ih pokrece pri svakom deploy-u.

POSLE UPLOAD-A (SEO):
  - Otvori Google Search Console (search.google.com/search-console) -> dodaj sajt
    (Domain ili URL prefix) -> Sitemaps -> posalji: https://www.fantasyedgeiq.com/sitemap.xml
    (Ako vec imas GSC povezan, samo sacekaj dan-dva da Google obidje nove stranice.)
  - Provjeri npr. /euroleague/players/sasha-vezenkov i /euroleague/players/ (hub sa pretragom).

NAPOMENE:
  - NEMOJ uploadovati public/ folder — Vercel ga sam regenerise.
  - FPL GW7 se zavrsava veceras/sutra (ponedjeljak). Za konacne GW7 brojke prije
    GW8 deadline-a (petak 23.10. 19:30) — javi se da ponovim FPL refresh.
  - EuroLeague kolo 7 pocinje u utorak 21.10. — cijene se mogu jos pomjeriti do
    fantasy deadline-a; paket se moze ponovo generisati istim postupkom.
  - Pocetna stranica, sitemap, vercel.json, package.json i workflow NISU dirani.
