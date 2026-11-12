FANTASY EDGE IQ — PAKET POPRAVKI (2026-11-12)
=============================================

Sta ovaj paket rjesava:
 1) Auto-refresh workflow je padao odmah na prvoj naredbi jer su svi skriptovi bili
    u korijenu repoa, a workflow ih trazi u scripts/ (fpl_fetch.py, fpl_build_dashboard.py,
    build_static_site.py, site_audit.py, scripts/eurocup/*, scripts/domestic/*).
    -> Zato FPL podaci nisu osvjezeni od GW5 (sajt je prikazivao Gameweek 8).
 2) scripts/run_euroleague_auto_refresh.py je bio nekorumpiran (SyntaxError na liniji 46)
    -> EuroLeague pipeline nije mogao da se pokrene.
 3) build.js je preskakao ubacivanje lock-banera ako u HTML-u vec postoji stari
    -> sajt je trajno prikazivao "EuroLeague MD8 lock: Tue 27.10.".
 4) build.js je pravio linkove na /euroleague/round-8-preview/ i /eurocup/round-8-preview/
    koji ne postoje (404), a EuroCup chip je vodio na EuroLeague preview.
 5) Preview clanak je linkovao /players/carlik-jones umjesto /players/carlik-jones-3791 (404).
 6) sitemap.xml je imao 3 duplirana URL-a.
 7) Nije bilo nijednog hreflang taga (EN/SR/EL) — dodato na 50 stranica.

Kako primijeniti (u korijenu repoa fantasy-edge-iq):
   unzip feiq-fixes.zip -d /tmp/feiq-fixes
   bash /tmp/feiq-fixes/apply-fixes.sh /tmp/feiq-fixes
   git add -A && git commit -m "Fix refresh pipeline + stale banners + 404 preview links" && git push

Nakon pusha:
   GitHub -> Actions -> "FEIQ auto-refresh" -> Run workflow
   Workflow ce sam: skinuti FPL (GW), pokrenuti EuroLeague pipeline (fantaking + official
   box scores), EuroCup, domaca takmicenja, rebuildovati public/ i commitovati.
   Vercel zatim deployuje.

Napomena: podaci su vec jednom osvjezeni rucno u ovom paketu (vidi UPDATE-2026-11-12.md),
tako da workflow poslije ovoga samo odrzava stanje.
