FANTASY EDGE IQ — UPDATE PAKET 2026-10-22 (nocno izdanje)
===========================================================

Sta je azurirano (audit: 0 gresaka, 0 upozorenja — lokalno provjereno):

  - EuroLeague: KOLO 7 — 7 od 10 utakmica odigrano i ukljuceno
    (BAY-DUB 91-107, EFS-BJK 89-80, HTA-VIR 90-81, MIL-BAR 81-89,
     MTA-RMB 99-113, PAO-KBA 85-79, PAR-CZV 85-82).
    Preostala 3 meca (OLY-FBT, PBB-VBC, ZAL-ASV) su na rasporedu —
    nakon njih javi se za novi refresh (tada se generise i Round 8 preview).
    Cijene, popularnost, povrede, projekcije, DvP (uzorak 67 utakmica,
    kola 1-7), Shot Share, next-5 raspored — EN/SR/EL.
  - EuroCup: kola 1-4 kompletna (64 utakmice), kolo 5 u toku.
    557 igraca, 388 sa zvanicnim stats-om. Zvanicna korekcija rezultata
    jedne utakmice (61-100 umjesto 60-101 iz fantasy feeda).
  - FPL: GW7 KONACNI brojevi + GW8 najava.
    Deadline za GW8: petak 23.10. u 19:30 (CEST). 668 igraca, 380 utakmica.
  - Domaca takmicenja: +2 nove utakmice (ABA: DUB 108-90 STU;
    BSL: ESE 73-70 EFS). EL klubovi: 88 utakmica / 9 zemalja;
    EuroCup klubovi: 136 / 14 zemalja.
  - Svi CSV fajlovi (players-full, team-context, next5, shot-share,
    DvP, matchlog, FPL) svjezi.

NOVO — POPRAVLJENI LINKOVI (ovaj paket sadrzi popravljene build skripte):
  - SR/EL stranice su linkovale nepostojece /sr/.../players/ i
    /el/.../players/ hubove — sada svi jezici linkuju engleske
    profilne stranice (jedine koje postoje).
  - Round preview chip je na sajtu bio zaglavljen na "Round 3"
    (stari league_config u repou) — sada se kolo cita iz next5
    rasporeda i uvijek se poklapa sa generisanim preview clankom.
    Preview postoji na EN i SR; EL stranice linkuju EN verziju.
  - FPL stranice vise ne dobijaju chipove ka nepostojecim
    /premier-league/defense-vs-position i domestic-competitions.
  - <html lang> na /sr/ i /el/ team-analyzer sada je sr/el (bio en).
  - Poslije deploy-a ponovi audit: python3 scripts/site_audit.py
    (ili javi meni da provjerim live sajt).

KAKO UPLOADOVATI (GitHub web, ~3 minute):
  1. Raspakuj FEIQ-UPDATE-2026-10-22.zip na racunar.
  2. Otvori svoj repo na github.com -> "Add file" -> "Upload files".
  3. Prevuci SVE fajlove iz raspakovanog foldera (README ne moras).
     GitHub pita za overwrite -> potvrdi.
  4. "Commit changes" -> Commit directly to the main branch -> Commit.
  5. Vercel sam pokrece build i deploy (1-2 minuta).
  6. Provjeri sajt (incognito ili ?v=4):
     /euroleague/dashboard -> "Generated: 2026-10-23 01:xx CEST" (nocni refresh)
     /eurocup/dashboard    -> "2026-10-23 00:44 CEST"
     /premier-league/dashboard -> GW7 konacni + GW8 deadline 23.10. 19:30
     Pocetne stranice: zuti "Round 7 preview" chip NA VRHU.

PREPORUCENO (da repo ostane zdrav za sledece refresh-eve):
  7. FEIQ-skripte-data-2026-10-22.zip: raspakuj i uploaduj SADRZAJ
     (folderi scripts/, euroleague_fantasy_data/, eurocup_fantasy_data/
      + root fajlovi iz zipa). Ovo sada sadrzi i POPRAVLJENE skripte
     (refresh_eurocup.py tolerise ... nije diran; build skripte su u
     site zipu).
  8. FEIQ-fpl-data-2026-10-22.zip: uploaduj folder fpl_fantasy_data/
     i fajl create_fantasheet_style_dashboard.py.
     (Bez ovoga ce Vercel build i dalje raditi — root CSV-ovi iz
      site zipa su dovoljni za stranice — ali sledeci refresh iz
      repoa nece imati svjeze FPL podatke.)

NAPOMENE:
  - NEMOJ uploadovati public/ folder — Vercel ga sam regenerise.
  - sitemap.xml/robots.txt/index.html u repo-u NISU dirani.
  - Ko-fi i Telegram: i dalje samo config prekidač (feiq-config.json,
    kofi_url/telegram_url prazni) — nema vidljivih dugmadi dok ne upises linkove.
  - Kad se odigraju preostala 3 meca MD7 (OLY-FBT, PBB-VBC, ZAL-ASV):
    javi se -> novi paket sa Round 8 preview-om i svim brojkama.
