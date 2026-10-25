FANTASY EDGE IQ — UPDATE PAKET 2026-10-24 (subota)
====================================================

Sta je azurirano (audit: 0 gresaka, 0 upozorenja):

  - EuroLeague: KOLO 7 KOMPLETNO — svih 10 utakmica, ukljucujuci
    cetvrtak: ZAL 105-85 ASV, OLY 61-64 FBT, PBB 93-104 VBC.
    Nove cijene i popularnost poslije cijelog kola, DvP uzorak
    70 utakmica (kola 1-7), projekcije i next-5 raspored sada
    pokazuju KOLO 8. Stamp: 2026-10-24 15:12 CEST.
  - NOVO: "Round 8 preview" clanak + social pack su se automatski
    generisali i stoje NA VRHU pocetnih stranica (EN + SR).
  - EuroCup: kola 1-4 (64 utakmice) + 388 igraca sa zvanicnim
    stats-om; kolo 5 se igra naredne sedmice. Stamp: 15:15 CEST.
  - FPL: GW8 u toku — petak vece uracunato, subota/nedelja mecovi
    ulaze u sledeci refresh. GW9 deadline: 31.10. u 12:00.
    Stamp: 2026-10-24 15:11 CEST.
  - Domaca takmicenja: +2 utakmice od 23.10. (YAM 73-84 BLK,
    UBT 100-78 STU) -> baza 206 utakmica.
  - Svi CSV fajlovi svjezi (players-full, team-context, next5,
    shot-share, DvP, matchlog, FPL).

AUTOMATSKI REFRESH (NOVO — detalji u chat poruci):
  - FEIQ-skripte-data-2026-10-24.zip sadrzi .github/workflows/
    feiq-refresh.yml + scripts/fpl_fetch.py + popravljene skripte.
  - Kad se uploaduje, GitHub Actions SAM refresh-uje sajt svaki dan
    u 00:30 i 09:00 (CEST) poslije utakmica i commit-uje -> Vercel
    deploy-uje. Vise nije potreban rucni zip (osim za velike izmjene).
  - OBAVEZNO poslije upload-a: GitHub repo -> Settings -> Actions ->
    General -> Workflow permissions -> "Read and write permissions"
    (bez toga bot ne moze commit-ovati).

KAKO UPLOADOVATI (GitHub web, ~3 minute):
  1. Raspakuj FEIQ-UPDATE-2026-10-24.zip.
  2. github.com -> tvoj repo -> "Add file" -> "Upload files".
  3. Prevuci SVE fajlove (README ne moras) -> potvrdi overwrite.
  4. Commit directly to the main branch -> Commit changes.
  5. Vercel sam deploy-uje (1-2 minuta).
  6. Provjeri (incognito ili ?v=5):
     /euroleague/dashboard -> "2026-10-24 15:12 CEST"
     /eurocup/dashboard    -> "2026-10-24 15:15 CEST"
     /premier-league/dashboard -> GW8 u toku (subota 13:00 CEST mecovi uracunati)
     Pocetna: zuti "Round 8 preview" chip NA VRHU.

PREPORUCENO:
  7. FEIQ-skripte-data-2026-10-24.zip: raspakuj i uploaduj SADRZAJ
     (scripts/, euroleague_fantasy_data/, eurocup_fantasy_data/,
      .github/ + root fajlovi iz zipa). Ovo ukljucuje AUTOMATIKU.
  8. FEIQ-fpl-data-2026-10-24.zip: fpl_fantasy_data/ + 
     create_fantasheet_style_dashboard.py.

NAPOMENE:
  - NEMOJ uploadovati public/ folder — Vercel ga sam regenerise.
  - sitemap.xml/robots.txt/index.html u repo-u NISU dirani.
  - Ko-fi/Telegram: i dalje config prekidač (feiq-config.json) —
    upisi linkove kad budes spreman, automatika ih pokupi sama.
  - Prvi automatski run mozes pokrenuti i rucno: GitHub repo ->
    Actions -> "FEIQ auto-refresh" -> Run workflow.
