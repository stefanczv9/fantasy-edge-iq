FIX ZA GITHUB ACTIONS MAIN.YML

Tvoj screenshot pokazuje da pada workflow file: main.yml.
Zato ovaj paket namjerno dodaje/zamjenjuje:
.github/workflows/main.yml

To je bitno jer upload prethodnog paketa nije obrisao stari main.yml.
Stari main.yml je ostao aktivan i zato workflow i dalje pada / moze vracati stare fajlove.

Nakon uploada:
1. Otvori GitHub repo -> .github/workflows/main.yml
2. Provjeri da main.yml u sebi ima:
   - python scripts/run_euroleague_auto_refresh.py
   - npm run build
   - cron: "55 18,19,20,21,22,23 * * 2-5"
3. GitHub -> Actions -> Update fantasy dashboards -> Run workflow

Ako padne na "git push" ili "Permission denied":
GitHub repo -> Settings -> Actions -> General -> Workflow permissions -> Read and write permissions -> Save.

Ako padne na nekom Python/API koraku:
Otvori failed run -> klikni job update -> klikni crveni step -> kopiraj prvu crvenu gresku.
