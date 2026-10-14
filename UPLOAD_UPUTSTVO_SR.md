# EuroLeague + EuroCup — osvježavanje poslije 13. oktobra 2026.

## Šta ide na sajt

`EL-EC-sajt-2026-10-14.zip` sadrži 38 ravnih fajlova. Prvo raspakuj ZIP, pa prevuci njegov sadržaj u **korijen repoa** i klikni Commit changes.

- **EuroLeague:** svih 7 sinoć završenih utakmica, ukupno 47 završenih utakmica. Ažurirani EN/SR/EL dashboardi, prosjeci, projekcije, cijene/statusi, DvP, full stats, shot share, timski kontekst, narednih pet utakmica i postojeći Lineup IQ.
- **EuroCup:** svih 5 sinoć završenih utakmica, ukupno 37. EN/SR/EL dashboardi sada imaju popunjene sve iste statističke tabove: igrači, cijene/statusi, prosjeci, projekcije, kompletna statistika, shot share, timski kontekst i narednih pet utakmica. DvP je ažuriran na 37 utakmica.
- **Domaća takmičenja:** provjerena ponovo, nema novih završenih domaćih utakmica u izvorima nakon prethodnog osvježavanja. Ostaje 69 utakmica za EuroLeague klubove i 110 za EuroCup klubove. Evropske utakmice nisu ubačene u domaće prosjeke.
- **BCL:** nije dio web paketa. Zasebna interaktivna tabela `BCL-interaktivna-tabela.html` služi za pregled ovdje u chatu ili lokalno u pregledniku.

Nema `index.html`, `sr-index.html`, `el-index.html`, `build.js`, `package.json`, `vercel.json`, sitemap-a ni `.github/workflows`. Postojeće rute i početna stranica se ne mijenjaju. **Ne uploaduj public/**.

## Skripte i izvori

`EL-EC-skripte-2026-10-14.zip` je zaseban paket sa skriptama i provjerenim ulaznim podacima. Raspakuj ga i sačuvaj strukturu foldera prilikom GitHub uploada. Posebno je bitno sačuvati `scripts/` i oba `*_fantasy_data/` foldera. Nijedan workflow nije mijenjan.

Za budući ručni refresh:

```
python3 scripts/run_euroleague_auto_refresh.py
python3 scripts/eurocup/eurocup_dvp.py --no-pages
python3 scripts/eurocup/refresh_eurocup.py
python3 scripts/domestic/update_domestic.py
python3 scripts/domestic/build_pages.py
python3 scripts/patch_average_pir_card.py
python3 scripts/audit_el_vs_official.py
python3 scripts/eurocup/audit_eurocup.py
python3 scripts/build_upload_package.py
```

Datumi: EuroLeague podaci 2026-10-14 12:09 CEST; EuroCup presjek izvora 2026-10-14 12:13 CEST; domaći izvori provjereni oko 12:08 CEST. Peto kolo EuroLeague i treće EuroCup još nisu završeni. Večerašnje/buduće utakmice nisu uračunate kao završene.

## Važna ispravka izvora

Fantasy API i dalje prikazuje ROM–BLK 77–72 od 13. oktobra kao `playing`. Zvanični EuroCup zapis (U2026, utakmica 48) potvrđuje konačan rezultat, pa je utakmica u svim tabelama pravilno računata kao završena. Starija utakmica BLK–BKS iz drugog kola koristi zvaničnih 61–100, ne zastarjelih 60–101 iz fantasy API-ja.

## Provjere

- EuroLeague: 263 fantasy igrača sa ostvarenim minutima, svi provjereni naspram zvaničnih box scoreova; DvP 94/94 timska reda, razlika nula.
- EuroCup: 557 fantasy profila/cijena, 372 igrača sa ostvarenim minutima, svi provjereni naspram zvaničnih box scoreova; DvP 74/74 timska reda, razlika nula.
- Šest EuroCup igrača sa zvaničnim nastupima nije u fantasy cjenovniku. Njihovi poeni su uključeni u DvP, ali im nisu izmišljene cijene.
- Svi novi podaci u EN/SR/EL stranicama su isti, osim prevoda. Browser testovi prolaze za tabove, pretragu, sortiranje i tabele.
- Proj PIR i FDR su procjene modela, ne ostvareni rezultati. EuroCup timski kontekst je samo iz tekuće sezone; EuroLeague zadržava postojeću dokumentovanu kombinaciju tekućeg i prethodnog timskog konteksta.
- Za dio domaćih utakmica PIR je procijenjen jer izvor nema sve komponente grešaka; to je označeno uz utakmice. Nijedan rezultat niti nedostajući individualni broj nije izmišljen.

## Poslije deploya

Provjeri `/euroleague/dashboard`, `/eurocup/dashboard`, obje `/defense-vs-position` i obje `/domestic-competitions`, i SR/EL verzije. Početna, FPL, istorijski tekstovi i BCL web rute ostaju nepromijenjeni.

Dodatno provjereno: EuroLeague Shot Share koristi isključivo zvanični FGA/G tima iz tekuće sezone, a ne 40/60 kombinaciju koja ostaje samo u timskom kontekstu.
