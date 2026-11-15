# Eventi: comandi per fonte (preparazione, 15 novembre 2026)

## Stato

Ramo `codex/events-source-controls-20261115`, basato su `main` `b225c296`.
La correzione XML del Teatro Verdi Trieste resta nel ramo dedicato
`codex/events-xml-recovery-20261115` (`2fa82145`) ed è stata integrata nel
ramo controlli con merge `740fa1d6`. [PR Eventi #48](https://github.com/meteofriul/meteofriul-app/pull/48)
in bozza, CI `43702113612` PASS nei job backend, frontend e
hosting-preview-tool sul commit `aec1c806`. La
[PR Pannello #2](https://github.com/meteofriul/meteofriul-inserzioni/pull/2)
è in bozza sulla base `codex/markets-weekly-audit-20261113`, così il diff
contiene soltanto i comandi Eventi; 223 test, lint e build locali PASS, nessun
workflow CI configurato nel repository del pannello. Le revisioni cloud di
prova sono descritte sotto. Il job pianificato, i servizi che servono il
traffico ordinario, il pannello online e l'app Web/Android non sono cambiati.

## Comportamento

- Un file JSON piccolo e revisionato nel bucket Eventi conserva per fonte
  attivazione, pausa temporanea o indefinita, motivo e autore. Il salvataggio
  usa la generazione GCS come controllo di concorrenza.
- Il job giornaliero legge il file prima della raccolta e salta le fonti in
  pausa. Non vengono create nuove pianificazioni. Una fonte in pausa resta una
  copertura ridotta; non viene dichiarata verificata. La pausa temporanea vale
  fino alla data indicata, inclusa, nel fuso `Europe/Rome`.
- L'API pubblica Eventi legge lo stesso controllo e nasconde entro la sua
  cache di 60 secondi le schede di fonti in pausa, anche prima del job seguente.
- L'API amministrativa richiede il token Firebase dell'account verificato
  `meteofriul@gmail.com`. Il comando `Verifica ora` accetta solo i 15 nomi
  registrati, riserva una richiesta per 10 minuti e avvia il job esistente con
  `--source NAME`. L'esito del job aggiorna il catalogo; il clic da solo non
  cambia lo stato in «verificata». La verifica non riattiva una fonte in pausa.
- Una risposta incerta dell'API Cloud Run può aver avviato comunque il job:
  la riserva di 10 minuti resta attiva per evitare invii doppi. L'operatore
  controlla l'esito prima di riprovare.

## Ordine di attivazione

### Provenienza online riletta il 15 novembre

Il job `meteofriul-events-refresh` usa il digest `1923bb40…`, prodotto dal
build `2fb529b6` per il commit `045079a0` del 26 ottobre. Il lettore
`meteofriul-events` usa `529d93d1…`, attestato nel verbale del 15 ottobre.
Nel servizio API generale, la revisione più recente
`meteofriul-api-00255-yuz` usa il digest `f4b1a2ee…`, prodotto dal build
`2477efb3` etichettato con il commit editoriale `7a1f188a`; è raggiungibile
solo con il tag `editorial-7a1f188a`. Il traffico API ordinario al 100% usa
invece `meteofriul-api-play-b6fbe4d-001`, digest `3e5c6014…`.
La revisione più recente non va scambiata con quella che serve l'app.
Il ramo Eventi non contiene il modulo editoriale del commit `7a1f188a`:
la nuova API amministrativa deve quindi avere un tag distinto e zero traffico
ordinario. Il pannello usa direttamente l'URL del tag `events-sources-v1`.

### Revisioni isolate di collaudo

Dal commit esatto `aec1c806` sono state costruite due immagini, senza
modificare i digest in produzione:

- Worker Eventi `sha256:5497430f4b3287e88e72a442389913e230602159548490958fa011553eda96f3`,
  build `214cc190-b647-4c79-a1e8-40fcd57c36a1` riuscito.
- API amministrativa `sha256:5a19ea01b689c16878166788c06b043298010f9f4ba269e5e39ccc8e557ee1c9`,
  build `8cf1fb03-ad26-46a3-a47c-6c00c91e7e66` riuscito.

Il job **temporaneo, senza pianificazione**
`meteofriul-events-source-qa-20261115` ha usato il nuovo worker e scritto soltanto
sotto `pilot/events/qa/`. La prima esecuzione `...-tfgdd`, limitata a
Teatro Verdi Trieste, è riuscita: 59 schede fresche, revisione controlli 0,
catalogo QA generazione `1794737374272991`. Una seconda esecuzione
`...-v6dvf` verifica tutte le 15 fonti nel catalogo QA separato
`pilot/events/qa/source-controls-20261115-all.json`: è fallita perché la
partenza da zero non contiene il checkpoint delle 2636 pagine TurismoFVG né
la prova dell'edizione conclusa di Pordenonelegge. Non rappresenta il giro
quotidiano. Il risultato da zero ha comunque confermato Teatro Verdi Trieste
`fresh` con 59 schede e CSS Udine `partial` con 129 schede, mentre Barcolana
era in timeout e l'inventario Spazzapan era cambiato.

Il catalogo pubblico è stato **copiato**, mai modificato, nel nuovo oggetto
`pilot/events/qa/source-controls-20261115-baseline.json`. La simulazione
completa `...-shmlm` da questa copia è terminata il 15 novembre alle 10:32
UTC. Il job ha segnalato correttamente l'esito complessivo fallito e ha
salvato la diagnosi nella sola copia QA. Confronto con il catalogo pubblico
del 15 novembre alle 05:00 UTC:

| Fonte | Prima | Dopo nel QA | Esito |
| --- | --- | --- | --- |
| Teatro Verdi Trieste | `stale`, 61 schede trattenute | `fresh`, 59 | XML recuperato; 59 schede utilizzabili |
| Barcolana | `stale`, 1 scheda trattenuta | `fresh`, 1 | sito raggiunto al secondo tentativo |
| TurismoFVG | `partial`, 1452 | `partial`, 1457 | checkpoint conservato, 16 elementi da rivedere |
| Pordenonelegge | `fresh`, 0 | `fresh`, 0 | edizione conclusa riconosciuta |
| CSS Udine | `stale`, 146 trattenute | `stale`, 146 trattenute | nuova lettura rifiutata dal confronto completo |
| Galleria Spazzapan | `stale`, 1 trattenuta | `stale`, 1 trattenuta | inventario ufficiale cambiato |

Le altre nove fonti hanno mantenuto lo stato precedente (`fresh` o `partial`).
Per CSS il confronto ha individuato quattro occorrenze future precedentemente
verificate e assenti dalla nuova lettura: *SDENG!* (22 novembre), *La foresta
dei no* (23 novembre), *I Sette a Tebe* (19 e 20 marzo 2027). Le tre pagine
ufficiali rispondevano HTTP 200 al controllo del 15 novembre; il sito ufficiale
conferma ancora le date. Il blocco evita di presentare una nuova raccolta
incompleta come verificata. Occorre correggere l'adattatore CSS con un ramo
dedicato e ricontrollare le quattro occorrenze; l'inventario Spazzapan richiede
una revisione separata della fonte ufficiale.

Pagine CSS controllate: [SDENG!](https://www.cssudine.it/stagione-tig-in-famiglia/2026/2919/sdeng-storia-di-un-inventore-che-non-riesce-a-stare-fermo),
[La foresta dei no](https://www.cssudine.it/stagione-tig/2026/2846/la-foresta-dei-no),
[I Sette a Tebe](https://www.cssudine.it/stagione-contatto/2026/2905/i-sette-a-tebe).
Il job QA temporaneo è stato eliminato dopo il collaudo; non esiste una nuova
pianificazione. I cataloghi QA restano per la revisione e il tag QA li legge.

Il lettore `meteofriul-events` ha la revisione taggata
`meteofriul-events-00020-qig` (`events-reader-qa-v1`), che legge il catalogo
QA aggiornato dalla copia pubblica. Alla richiesta di prova vicino Trieste
restituisce `ready`, 315 eventi, 59 di Verdi Trieste, nessuno di CSS o
Spazzapan (entrambe `stale`). La revisione pubblica
`meteofriul-events-00018-2vz` conserva
il 100% del traffico. La revisione taggata dell'API amministrativa
`meteofriul-api-00256-rif` (`events-sources-v1`) ha 0% del traffico;
`meteofriul-api-play-b6fbe4d-001` conserva il 100% del traffico API ordinario.
Sul tag amministrativo `/api/healthz` risponde 200, l'elenco senza login 401,
il preflight CORS dall'origine del pannello 200. L'accesso con il login del
titolare e i comandi di scrittura richiedono ancora il collaudo nel pannello.
La lettura pubblica del 15 novembre alle 10:20 UTC risultava `degraded`:
`Barcolana`, `CSS Udine`, `Galleria Spazzapan` e `Teatro Verdi Trieste`
erano `stale`; il suo snapshot era del 15 novembre alle 05:00 UTC anche dopo
le prove. Nessuna scheda QA è entrata nell'app.

### Passi ancora necessari per la promozione

1. Correggere CSS e Spazzapan in rami propri dopo confronto con i siti
   ufficiali. Ripetere una verifica QA mirata e il giro completo dalla copia
   del catalogo. Non ridurre i controlli di qualità per forzare un esito verde.
2. Provare il tag amministrativo con il login del titolare: elenco, errore
   senza permessi, salvataggio e ripristino di una pausa di prova. Il ruolo
   `roles/editor` dell'identità API include `run.jobs.runWithOverrides`, ma
   l'invocazione reale non è ancora verificata. Il job pubblico deve ricevere
   il nuovo worker **prima** del comando `Verifica ora` nel pannello.
3. Solo dopo il collaudo, promuovere tramite PR e CI la correzione XML e il
   controllo fonti; aggiornare job e lettore pubblico in quest'ordine,
   verificando digest e traffico. Distribuire poi il pannello e provare
   l'intero percorso sul telefono; ripristinare qualsiasi pausa di prova.
4. Aggiornare le evidenze di deployment e Web/Android. Nessuna AAB è
   richiesta da questi cambi server; non attribuire alle revisioni QA lo
   stato di pubblicazione dell'app.

## Verifiche locali

`python -m unittest tests.test_event_source_controls tests.test_events_admin_sources
tests.test_pilot_cloud tests.test_pilot_http -q`: 52 test passati.
Suite combinata con XML e catalogo: 98 test PASS; CI PR #48 PASS.
`python -m compileall -q app/events/source_controls.py app/events/pilot_cloud.py
app/events/pilot_http.py app/api/events_admin.py`: passato.

Contratto Cloud Run: [jobs.run v2](https://docs.cloud.google.com/run/docs/reference/rest/v2/projects.locations.jobs/run)
richiede `run.jobs.runWithOverrides` quando passa `containerOverrides.args`.
