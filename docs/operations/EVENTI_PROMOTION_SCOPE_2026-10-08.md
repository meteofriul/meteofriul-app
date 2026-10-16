# Ramo Eventi isolato per la promozione, 8 ottobre 2026

Il ramo `codex/events-promotion-only` parte da `origin/main` al commit
`d67ef933`. Trasporta lo stato Eventi del ramo di audit al commit `fb9000bf`:
adapter delle fonti, catalogo e deduplicazione, controlli automatici,
API di lettura, programma scorrevole e filtro Sagre. Include i test, i fixture,
gli strumenti di audit e i documenti operativi Eventi. I colori dei pulsanti
scuri nell'anteprima sono definiti nel solo foglio Eventi.

Restano fuori dal ramo l'APK tester separata, il tunnel temporaneo di review,
le modifiche a meteo, notifiche, selettori di altre sezioni e pulsanti globali.
Non sono stati modificati il job cloud, il catalogo online, l'APK ufficiale o
`main` durante la preparazione del ramo.

Controlli locali del ramo:

- 648 test `test_pilot_*.py`: passati, uno saltato;
- 50 test aggiuntivi per Palazzo Attems e il motore Eventi: passati;
- 118 test frontend Eventi, API e programma: passati;
- build Vite in una directory temporanea: riuscita;
- controllo del workspace canonico e `git diff --check`: passati.

Verifiche cloud dell'8 ottobre:

- il ciclo completo `meteofriul-events-refresh-j7ztp` ha aggiornato 14 fonti,
  ma Teatro Verdi Pordenone e' fallita su link di paginazione con parametri
  newsletter di ActiveCampaign; il catalogo degradato l'ha esclusa dalla lista;
- il commit `660bee60` accetta esclusivamente i quattro parametri newsletter
  verificati, poi li rimuove dall'URL. La lettura locale di tutte le sei pagine
  ufficiali ha trovato 88 repliche future, senza revisioni;
- il primo retry cloud `meteofriul-events-refresh-lrxpr` non ha avviato Python:
  l'argomento `--retry-failed` ha sostituito il `CMD` del contenitore. Il commit
  `7f92e743` usa `ENTRYPOINT` e lascia l'opzione come argomento;
- il retry `meteofriul-events-refresh-ghjdv` e' riuscito. L'API espone
  `catalog_status=complete`, 15 fonti `fresh` e nessun `source_failure_tags`.

Sul telefono Samsung con la 0.1.13-tester sono state controllate la Sagra del
Rosario nel filtro Sagre e l'anteprima delle Giornate del Cinema Muto con
immagine e programma scorrevole. La tester installata proviene dal precedente
ramo di audit: questi controlli coprono il contenuto online e la UI Eventi
trasportata, non un APK costruito da questo ramo isolato.

Il ciclo completo `meteofriul-events-refresh-748h7` ha aggiornato le 15
fonti ma si e' fermato al monitor Palazzo Attems: la notizia 233783 sugli
orari della biblioteca, gia' esclusa dagli eventi, non compare piu' nelle
notizie correnti. L'API ufficiale ora ne elenca 154 e non contiene quell'ID.
La baseline e' stata aggiornata solo per questa rimozione: una ricomparsa
tornera' a richiedere revisione. Il monitor locale ha ancora tre blocchi
noti, `source_complete=false`, ma nessuna nuova variazione. In lettura locale
Pro Loco FVG ha 58 schede su 6 pagine, senza nuovi candidati; Anteprima
Sagre ha 419 articoli, nessuna nuova data futura e un caso senza anno gia'
noto; GiroFVG non ha nuove variazioni e conserva un errore di pagina noto.

Un altro ciclo completo (`meteofriul-events-refresh-96gx8`) ha aggiornato
le 15 fonti e poi ha ricevuto HTTP 502 dalla homepage di Palazzo Attems.
Il lettore ora ritenta solo HTTP 502/503/504 due volte, con pause limitate.
Inoltre il job registra e valuta tutti e quattro i monitor prima di riportare
eventuali errori, cosi' un errore del primo non oscura quelli successivi.
I 7 test Palazzo Attems e i 647 test pilota passano con queste modifiche.

L'immagine `events-monitors-20261008-5e82414b` ha superato Cloud Build
`017b074b-db62-4503-8a31-6355d78a0053` ed e' installata nel job ufficiale.
Il ciclo `meteofriul-events-refresh-wjkdf` ha pubblicato 15 fonti `fresh`.
Ha verificato Palazzo Attems (27 record API, 3 blocchi noti, nessuna variazione),
Pro Loco FVG (58 schede, nessuna variazione) e GiroFVG (nessuna variazione,
un errore di pagina gia' noto). Il monitor Anteprima Sagre ha ricevuto una
risposta API inattesa dal cloud e il job ha quindi terminato con errore.
Il monitor locale, eseguito lo stesso giorno, ha invece letto 419 articoli su
5 pagine, senza nuovi candidati datati. Diagnostiche cloud precedenti avevano
ricevuto HTTP 202/HTML anche su API, feed, sitemap e homepage: la pausa fra
le pagine non risolve un blocco gia' presente sulla prima richiesta.

L'utente ha scelto di promuovere le 15 fonti verificate mantenendo Anteprima
Sagre segnalata come monitor non verificato. Il commit `e25ae249` registra
nel catalogo lo stato separato dei quattro monitor e lo espone nell'API come
`monitor_status`. Un'eccezione del monitor Anteprima viene etichettata
`unverified / upstream_unavailable`, senza schede pubblicate e senza far
fallire il job delle 15 fonti. Nuovi candidati trovati da Anteprima restano
un blocco di revisione; gli altri tre monitor mantengono il loro gate. Il
retry di una singola fonte conserva lo stato precedente dei monitor senza
dichiararli ricontrollati.

La build Cloud Build `272d618a-2ddd-425e-b9ae-c55ce88df542` ha installato
l'immagine `events-monitor-status-20261008-e25ae249` nel job e nel servizio
API (`meteofriul-events-00010-6fl`). Il ciclo completo
`meteofriul-events-refresh-rfscv` e' riuscito in 5m46.6s. L'API pubblica
`catalog_status=complete`, 15 fonti `fresh`, nessun `source_failure_tags` e
`Anteprima Sagre: unverified / upstream_unavailable`. Palazzo Attems, Pro Loco
FVG e GiroFVG risultano `checked`; i loro blocchi storici restano distinti
dalle variazioni nuove. Nessuna scheda di Anteprima viene pubblicata.

La CI della PR e la review del perimetro precedono il merge in `main`. Le prove
locali di Anteprima non attestano ancora la raggiungibilita' dal job cloud;
questo monitor richiede una soluzione separata in un secondo momento.
