# Job Eventi e anticipazione serale — stato del 23 novembre 2026

## Codice integrato

La [PR Eventi 59](https://github.com/meteofriul/meteofriul-app/pull/59) è
integrata in `main` al commit `66d534c6efc259a3f2ee9bec837ce9f8b3adb7f1`.
La CI di PR e la CI `main` `45204377532` sono verdi. Il backend del merge
coincide con l'albero `2546a2d3063657a0688294232b899dcf964795e7` usato
per costruire l'immagine QA Eventi. La correzione legge Azalea a coppie e
permette un recupero più lungo al calendario Barcolana, mantenendo invariati
i budget complessivi e il rifiuto di fonti incomplete.

La [PR serale 58](https://github.com/meteofriul/meteofriul-app/pull/58) è
integrata in `main` al commit `5db7b5a81372f8e64e05a28730b62f21e12c7383`.
La CI di PR, 99 test mirati del ramo combinato e la CI `main`
`45205924026` sono verdi. Il backend del merge coincide con
l'albero `c656133734c35821b6fec60bc1afb93af11eb704` usato per
l'immagine candidata serale. Il testo ridotto descrive solo le temperature
verificate su tutte le ore del giorno successivo; non interpreta la pioggia
assente come zero.

## Prove isolate

Il job Eventi QA ha letto tutte le 14 fonti attive con una copia del catalogo
pubblico sotto chiave QA: tutte `fresh` o `partial`, Azalea `partial` con
9 schede e 2 cambi da rivedere, Barcolana `fresh` con 1 scheda. Spazzapan
resta in pausa. La prima prova completa senza checkpoint era fallita per
Pordenonelegge e TurismoFVG; la seconda, con gli stessi checkpoint del
pubblico, è riuscita. I job QA sono stati rimossi.

Il replay serale sul ciclo ICON immutabile `20261122T120000Z` ha verificato
24 ore del 23 novembre, temperature 5–11 °C e pioggia incerta in sei ore.
Un job QA filtrato al solo Android owner ha registrato prima `dry_run` con
`attempted=1`, `sent=0`, poi una sola esecuzione TEST con `sent=1`, `failed=0`.
Il proprietario ha confermato ricezione e apertura del Bollettino al tocco.
Il job QA, con il filtro del dispositivo autorizzato temporaneamente, è stato
eliminato. Il modulo di replay non è nell'immagine distribuita in produzione.

## Deploy delle sole immagini

Il proprietario ha autorizzato i due deploy con «Facciamolo». Sono cambiate
solo le immagini dei job Cloud Run, una alla volta. Non sono state avviate
esecuzioni manuali: l'ultima Eventi è quella programmata del 23 novembre alle
04:00 UTC e l'ultima serale quella del 22 novembre alle 20:45 ora italiana.

| Job | Digest precedente | Digest ora distribuito | Pianificazione invariata |
| --- | --- | --- | --- |
| `meteofriul-events-refresh` | `sha256:fcf3a81c076bd2a0d50211b6e15c29012febb764575db2b644c5b2074fdf5fe4` | `sha256:d6ff27f255a0d969883beacb485fffdb4fdfcaa715c93f4f2744e6502a7952b7` | `0 4 * * *`, `Etc/UTC`, attiva |
| `meteofriul-evening-forecast` | `sha256:3811ae86d2026d43869b0869e52c225e3c32e57b06783c5aae80567e31bb2b38` | `sha256:7d4596aef2b75d77ef26ef2a750ed3e7c3c6fc3d62e2e4379c26fc9f6a27495f` | `45 20 * * *`, `Europe/Rome`, attiva |

Il readback Eventi mostra generazione 49, chiave pubblica
`pilot/events/v1/catalog.json`, bucket `meteo-friul-weather-data`, account
writer Eventi, un task e zero retry invariati. Lo Scheduler resta `ENABLED`
alle 04:00 UTC. Il readback serale mostra generazione 8, account runtime,
modalità `send`, coorte `play_beta`, un task e zero retry invariati. Lo
Scheduler resta `ENABLED` alle 20:45 `Europe/Rome`.

Il catalogo pubblico Eventi, riletto dopo il deploy, conserva lo snapshot
del 23 novembre alle 05:00 italiane: Azalea e Barcolana sono ancora `stale`.
L'immagine nuova agirà alla prossima corsa ordinaria, il 24 novembre alle
05:00 italiane. Il job serale userà l'immagine nuova alla corsa del 23
novembre alle 20:45 italiane. Entrambe le corse con dati correnti restano da
verificare; la riuscita delle prove QA non le sostituisce. Nessun nuovo
artefatto Web/Android, versione app o AAB è stato prodotto.
