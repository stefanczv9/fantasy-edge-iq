AUTOMATSKI EUROLeague REFRESH

Ovaj paket dodaje GitHub Actions workflow:
.github/workflows/euroleague-auto-refresh.yml

Sta radi:
- automatski pokrece refresh EuroLeague podataka 3 puta dnevno poslije game-night termina
- osvjezava cijene, dashboard, Proj PIR, Lineup IQ podatke i DvP
- DvP ostaje real-points-only po Guard/Forward/Center
- ako ima promjena, bot napravi commit i push
- Vercel deployment se onda pokrece preko GitHub integracije

Manualno pokretanje:
GitHub repo -> Actions -> EuroLeague auto refresh -> Run workflow

Bitno:
Ako workflow nije vidljiv poslije uploada, .github folder nije uploadovan. Tada u GitHubu rucno napravi fajl:
.github/workflows/euroleague-auto-refresh.yml
sa sadrzajem iz ovog paketa.

Ako Vercel ne deployuje commit koji napravi bot, u Vercelu napravi Deploy Hook i dodaj ga kao GitHub secret:
VERCEL_DEPLOY_HOOK_URL
