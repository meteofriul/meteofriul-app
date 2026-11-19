# Eventi: aggiornamento operativo del 19 novembre 2026

## Perché è servito un secondo intervento

Le [PR 48](https://github.com/meteofriul/meteofriul-app/pull/48),
[49](https://github.com/meteofriul/meteofriul-app/pull/49) e
[50](https://github.com/meteofriul/meteofriul-app/pull/50) hanno integrato in
`main` il recupero delle fonti, i monitor Attems/GiroFVG e la separazione
delle fonti in pausa dallo stato di errore del lettore API.

L'immagine combinata del job, `sha256:b967a8b19c24a362819da8bd464eaa9dc832c2ee8d46c90439b5cd0d8d332a56`,
è stata costruita da sorgente con tree identico al merge `d5b331ea`.
Cloud Build `be131ba3-4b8c-4fe1-bfd9-a60a1c7419dd` è riuscito e il job QA
`meteofriul-events-job-qa-20261119b` ha completato una raccolta di tutte le
14 fonti attive sul catalogo separato
`pilot/events/qa/job-recovery-combined-20261119/catalog.json`.
Il job QA è stato eliminato dopo il collaudo. Spazzapan è rimasta in pausa.

Il job pubblico `meteofriul-events-refresh` è passato dalla generazione 46
alla 47 con la sola sostituzione dell'immagine; Scheduler, identità, chiave
del catalogo, task, tentativi e timeout sono rimasti invariati. Una singola
esecuzione manuale, `meteofriul-events-refresh-528kj`, è **fallita** il 19
novembre alle 17:53 UTC: `Le Giornate del Cinema Muto` ha superato il limite
di 30 secondi. Il catalogo pubblico è stato comunque salvato alla generazione
`1795110829341783`: CSS Udine, Teatro Verdi Trieste, MESS e SagreFVG sono
stati recuperati, mentre Cinema Muto è rimasta `stale`. Questo salvataggio
parziale non è stato considerato un successo del job. Non è stato eseguito
un retry cieco e il lettore pubblico non ha ricevuto nuovo traffico.

## Correzione del budget Cinema Muto

La [PR 51](https://github.com/meteofriul/meteofriul-app/pull/51), commit
`b3374c85`, merge `0d32bf15`, legge le dieci pagine del calendario ufficiale
con al massimo quattro richieste contemporanee. Mantiene l'ordine delle date
e tutte le verifiche sul contenuto, sui redirect e sul lotto completo.
Non aumenta il limite di 30 secondi né il tempo complessivo di 900 secondi.

Una lettura diretta ha impiegato 14,61 secondi prima e 8,08 secondi dopo,
con 87 appuntamenti classificati su dieci pagine. I 803 test `test_pilot*.py`
sono passati (uno saltato); `compileall`, `git diff --check` e i tre job CI
della PR sono passati. L'archivio `git archive` del commit `b3374c85` ha
SHA256 `ad8bb1587a4aad0b99ac70177511ac9e98cf094b71620808cd22d520f275ffa1`.
Cloud Build `b3ece10c-f371-40d1-8211-70847dddae03` è riuscito e ha prodotto
il digest `sha256:fcf3a81c076bd2a0d50211b6e15c29012febb764575db2b644c5b2074fdf5fe4`.

Il job temporaneo `meteofriul-events-cinema-qa-20261119` ha riletto solo
Cinema Muto sul catalogo QA. L'esecuzione `...-bg7bw` è terminata con
`Completed=True`, un task riuscito, zero retry e catalogo QA generazione
`1795111599109012`. Il gate ha classificato la fonte `fresh`; le dieci
pagine sono complete. Nessuna scheda storica è comparsa come evento futuro.

## Collaudo complessivo e job pubblico

Il job temporaneo `meteofriul-events-full-qa-20261119`, senza pianificazione,
ha provato tutte le fonti sullo stesso catalogo QA con il digest
`sha256:fcf3a81c...`. La chiave del catalogo e gli argomenti vuoti sono stati
letti dalla configurazione prima dell'esecuzione `...-j2pkg`, completata
con un task riuscito alle 18:13 UTC. Catalogo QA generazione
`1795112000840707`: 14 fonti attive `fresh` o `partial`, 1.883 eventi di
fonte, Spazzapan in pausa. CSS Udine ha 130 schede, Verdi Trieste 56,
MESS 10 e SagreFVG 7. Cinema Muto ha 0 schede correnti: l'edizione 2026
è finita, ma le dieci pagine sono state lette e la fonte è `fresh`.
Palazzo Attems e GiroFVG restano `review_required` perché i loro inventari
non sono completi; il controllo annuale TurismoFVG è `checked`.

La CI di `main` per il merge `0d32bf15`, run `44584464920`, è riuscita nei
tre job. Il job pubblico è passato alla generazione 48 con la **sola immagine**
`sha256:fcf3a81c...`; chiave `pilot/events/v1/catalog.json`, un task,
zero retry, timeout 900 secondi e identità del job sono invariati. Scheduler
è ancora abilitato su `0 4 * * *` in `Etc/UTC`. La singola esecuzione pubblica
`meteofriul-events-refresh-c79k5` è terminata con `Completed=True`, un task
riuscito, alle 18:19 UTC. Catalogo pubblico generazione `1795112372655876`,
snapshot `2026-11-19T18:15:33.926906+00:00`: 14 fonti attive `fresh` o
`partial`, 1.882 eventi di fonte, Spazzapan in pausa. CSS Udine è `partial`
con 130 schede, Verdi Trieste `partial` con 56, Cinema Muto `fresh` con zero
eventi futuri. Attems e GiroFVG restano `review_required`; il controllo
annuale TurismoFVG è `checked`.

Il lettore Eventi è stato creato come revisione
`meteofriul-events-00024-vaz` a 0% del traffico, con lo stesso digest
`sha256:fcf3a81c...` e la chiave pubblica. Prima del cambio di traffico,
l'API di Udine e Trieste ha risposto HTTP 200 con snapshot aggiornato,
CSS e Verdi `partial`, Cinema Muto `fresh`, Spazzapan in `paused_sources`
e assente da `source_failure_tags`. `catalog_status=degraded` segnala le
singole schede in revisione (`quarantined_cards`), non una fonte scaduta.
La revisione `00024-vaz` ha poi ricevuto il 100% del traffico. L'endpoint
pubblico ha ripetuto gli stessi controlli con HTTP 200: 496 eventi composti
entro 20 km da Udine e 343 da Trieste. La precedente revisione pubblica
`00018-2vz` resta disponibile per rollback.

I job QA `meteofriul-events-cinema-qa-20261119` e
`meteofriul-events-full-qa-20261119` sono stati eliminati dopo la verifica
dei loro esiti `Completed=True`; i cataloghi QA e i log restano. Non sono
state aggiunte pianificazioni. Il pannello online e le policy di allarme
non sono stati attivati o modificati; l'app Web e Android non è stata
rigenerata o pubblicata. Va osservata la prima corsa ordinaria dello
Scheduler alle 04:00 UTC del 20 novembre: il successo manuale non la
sostituisce.
