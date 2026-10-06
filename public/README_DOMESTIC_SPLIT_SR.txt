Fantasy Edge IQ — RAZDVOJEN domestic update
Generated: 2026-10-06 Europe/Zagreb

Upload/replace files preserving folders. Paket nema .github/workflows.

Šta je razdvojeno:
1) EuroLeague domestic sekcija
   - /euroleague/domestic-competitions/
   - /sr/euroleague/domestic-competitions/
   - /el/euroleague/domestic-competitions/
   - CSV: domestic-euroleague-*.csv
   - Samo EuroLeague target klubovi.
   - Counts: 38 games, 381 player rows, 33 team totals, 258 averages, 20/20 EL teams covered.

2) EuroCup domestic sekcija
   - /eurocup/domestic-competitions/
   - /sr/eurocup/domestic-competitions/
   - /el/eurocup/domestic-competitions/
   - CSV: domestic-eurocup-*.csv
   - Samo EuroCup target klubovi.
   - Counts: 56 games, 368 player rows, 33 team totals, 312 averages, 32/32 EC teams covered.

Build/nav:
- package.json build script sada kopira EuroCup domestic rute.
- EuroCup dashboard i homepage imaju linkove ka zasebnoj EuroCup domestic sekciji.

Bitno:
- EuroLeague domestic i EuroCup domestic više nisu ista kombinovana stranica.
- Player/average rows su filtrirani po sekciji: EL stranice nemaju EC player/average rows, EC stranice nemaju EL player/average rows.
- Fizička utakmica može biti prikazana u obje sekcije samo ako igraju EL i EC klub jedan protiv drugog; player/average podaci ostaju filtrirani po svojoj sekciji.
- Domaća/nacionalna statistika ostaje odvojena od EuroLeague/EuroCup projekcija i ne ulazi u Proj PIR logiku.
