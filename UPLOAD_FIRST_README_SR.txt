PROCITAJ PRVO

Ovo je paket ispod 100 fajlova. Dodaje dvije stvari:
1. trenutni EuroLeague dashboard + DvP refresh
2. automatski GitHub Actions refresh poslije game-night termina

Upload:
- Raspakuj ZIP.
- U GitHub repo root /fantasy-edge-iq/ uploaduj SADRZAJ ovog foldera.
- Prihvati overwrite/replace.
- Commit message: Add EuroLeague auto refresh

Provjera poslije commita:
- GitHub repo -> Actions -> treba da postoji "EuroLeague auto refresh".
- Klikni "Run workflow" jednom da testiraš odmah.
- Ako prođe, ubuduće se sam pokreće po rasporedu.

Ako "EuroLeague auto refresh" nije vidljiv, .github folder nije uploadovan.
Tada ručno napravi fajl u GitHubu:
.github/workflows/euroleague-auto-refresh.yml
sa sadržajem iz paketa.
