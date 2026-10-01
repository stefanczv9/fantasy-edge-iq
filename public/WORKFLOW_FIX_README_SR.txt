BITNO - ZASTO SE VRACALO NA STARO

Na GitHub Actions vec postoji workflow "Update fantasy dashboards". Ako taj workflow koristi stari generator, on moze ujutru pregaziti rucno uploadovane svjeze fajlove i vratiti dashboard/DvP na staro.

Ovaj paket dodaje/zamjenjuje:
.github/workflows/update-fantasy-dashboards.yml

Novi workflow:
- pokrece EuroLeague refresh poslije utakmica: utorak-petak, vise puta uvece/nocu
- ima backup refresh u 00:20, 02:20 i 05:20 UTC
- refreshuje cijene, Proj PIR, dashboard, Lineup IQ i real-points DvP
- pravi commit samo ako postoje promjene
- Vercel treba sam da deployuje taj commit

NAKON UPLOADA PROVJERI:
1. GitHub -> Actions -> Update fantasy dashboards
2. Otvori najnoviji run i klikni "Run workflow" jednom rucno.
3. Ako workflow prodje, gledaj da li bot napravi commit "Auto refresh EuroLeague dashboard and DvP" ili kaze "No EuroLeague changes to commit".
4. Ako poslije runa Vercel ne deployuje, dodaj Vercel deploy hook kao secret: VERCEL_DEPLOY_HOOK_URL.

AKO I DALJE POSTOJI STARI WORKFLOW:
Ako u Actions vidis jos jedan stari workflow koji radi samo ujutru i pregazi fajlove, moras ga disable/delete.
Najlakse:
Actions -> stari workflow -> tri tacke -> Disable workflow.
Ili u repo obrisati stari fajl iz .github/workflows/ koji nije ovaj novi update-fantasy-dashboards.yml.
