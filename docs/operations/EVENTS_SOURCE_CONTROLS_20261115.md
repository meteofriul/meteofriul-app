# Eventi: comandi per fonte (preparazione, 15 novembre 2026)

## Stato

Ramo `codex/events-source-controls-20261115`, basato su `main` `b225c296`.
La correzione XML del Teatro Verdi Trieste resta nel ramo dedicato
`codex/events-xml-recovery-20261115` (`2fa82145`) ed è stata integrata nel
ramo controlli con merge `740fa1d6`. [PR Eventi #48](https://github.com/meteofriul/meteofriul-app/pull/48)
in bozza, CI `43700360903` PASS nei job backend, frontend e
hosting-preview-tool sul codice `c7551e53`. La
[PR Pannello #2](https://github.com/meteofriul/meteofriul-inserzioni/pull/2)
è in bozza sulla base `codex/markets-weekly-audit-20261113`, così il diff
contiene soltanto i comandi Eventi; 222 test, lint e build locali PASS, nessun
workflow CI configurato nel repository del pannello. Nessun job è stato
eseguito, nessun servizio online è stato modificato, nessuna app Web/Android
è stata pubblicata.

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

1. Integrare la correzione XML su `main`, controllare CI e creare un'immagine
   Eventi contenente entrambe le modifiche. Eseguire il preflight dei ruoli:
   il lettore Eventi deve poter leggere il controllo GCS, l'API amministrativa
   deve poterlo scrivere, e l'identità dell'API deve avere
   `run.jobs.runWithOverrides` sul solo job `meteofriul-events-refresh`.
   Il controllo in sola lettura del 15 novembre ha confermato che il ruolo
   `roles/editor` già assegnato all'identità API contiene il permesso;
   l'invocazione effettiva resta da collaudare dopo il deploy.
2. Aggiornare **prima** il job Eventi con `--source` e il controllo delle pause;
   poi il servizio Eventi pubblico. Distribuire l'API amministrativa come
   revisione taggata `events-sources-v1` **senza spostare il traffico API
   principale**: la revisione editoriale attuale `editorial-7a1f188a` è già
   separata dal traffico dell'app nello stesso modo. Verificare revisione,
   digest e URL del tag. Evitare test su fonti
   già segnalate come guaste per non generare allarmi di prova.
3. Solo dopo i controlli API, distribuire il pannello con la chiamata HTTPS
   al tag `events-sources-v1` e CSP limitata a quell'host. Provare con login:
   elenco, pausa e
   riattivazione di una fonte di prova autorizzata, controllo che l'app non
   mostri una fonte in pausa, verifica mirata e relativo esito. Ripristinare
   lo stato della fonte al termine.
4. Aggiornare le evidenze di deployment, CI e Web/Android. Nessuna AAB è
   richiesta da questi cambi server; l'app deve comunque essere verificata
   come client del catalogo prima di promuovere la modifica.

## Verifiche locali

`python -m unittest tests.test_event_source_controls tests.test_events_admin_sources
tests.test_pilot_cloud tests.test_pilot_http -q`: 52 test passati.
Suite combinata con XML e catalogo: 98 test PASS; CI PR #48 PASS.
`python -m compileall -q app/events/source_controls.py app/events/pilot_cloud.py
app/events/pilot_http.py app/api/events_admin.py`: passato.

Contratto Cloud Run: [jobs.run v2](https://docs.cloud.google.com/run/docs/reference/rest/v2/projects.locations.jobs/run)
richiede `run.jobs.runWithOverrides` quando passa `containerOverrides.args`.
