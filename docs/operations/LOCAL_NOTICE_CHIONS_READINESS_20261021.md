# Avvisi locali: regressione Chions e stato del consumatore

21 ottobre 2026. **Verifica locale conclusa; job operativo non aggiornato.**
Ramo `codex/local-notice-runtime-readiness`, base main
`057f3e816432107451ff45ab5d7a72f50b074505`.
In questo ramo sono aggiunti regressione, fixture pubblica e documentazione;
non è necessaria un'altra modifica alla logica dei rilevatori per questo caso.
Nessun commit, promozione, push, deploy, job manuale, invio, AAB o installazione.

## Causa verificata

Nell'audit del 21 ottobre, le esecuzioni delle 17:00 e 18:00 italiane hanno
rifiutato Chions (093013) con `future_slots_not_hourly`. Il documento pubblicato
per la corsa `20261021T000000Z` contiene alle 22:00 italiane (20:00 UTC) umidità
e temperatura percepita non disponibili, motivo `invalid_T_Td_for_RH_no_clipping`.
L'adattatore precedente elimina quell'ora incompleta: rimangono cinque ore,
e il controllo strutturale rifiuta l'intera valutazione.

Il job operativo letto durante l'audit usa ancora il digest
`7af9d579cdc135b1823e226ae99aec7fb3ec93276d5aa0af80910923b363fe04`.
Il codice nuovo è su main ma la pubblicazione del produttore ICON non ha
aggiornato anche il consumatore degli avvisi. Questo caso riguarda T/Td;
non è causato dalla tolleranza degli accumuli.

## Replay degli stessi dati e istanti

Riutilizzati i documenti e sidecar già salvati dal controllo del produttore:
nessuna nuova acquisizione meteo. La fixture conserva i corpi originali e il
descrittore; il test verifica SHA-256 del documento contro il manifest.
Istanti: `2026-10-21T15:00:50+00:00` e `2026-10-21T16:01:17+00:00`.

| Finestra | Consumatore su main | Fenomeni valutabili | Non valutabili | Candidati |
| --- | --- | --- | --- | --- |
| 17:00 | sidecar verificato | 5/6 | caldo | 0 |
| 17:00 | sidecar disabilitato o hash non valido | 3/6 | caldo, pioggia, neve | 0 |
| 18:00 | sidecar verificato | 5/6 | caldo | 0 |

La valutazione con sidecar usa una tolleranza nella finestra delle 17:00;
in quella delle 18:00 non serve. In entrambi i casi l'ora incompleta resta
nella sequenza e la temperatura percepita resta null. Nessuna normalizzazione
Td=T, conversione di mancanti in zero o deduzione di assenza di rischio.
Il risultato è `partial_evaluation`, con causa e denominatore espliciti.
La cancellazione di un'ora reale viene ancora rifiutata con `future_slots_not_hourly`.

**182 test e 108 sottocasi passati**, suite avvisi locali, comando del job e
consegna dei riepiloghi mattutino/serale, con connessioni socket bloccate.
I tre test della [regressione reale](../../backend/tests/test_local_notice_chions_regression.py)
usano la [fixture pubblica](../../backend/tests/fixtures/icon_chions_20261021.json).
Questi sono controlli locali: nessun nuovo messaggio, record outbox o esecuzione cloud.

## Cosa rimane aperto

1. **Consumatore operativo.** Manca il passaggio alla versione per fenomeno con
   sidecar abilitato, nell'ordine del [piano coordinato](ICON2I_COORDINATED_ROLLOUT_20261019.md).
   Conservare un rollback compatibile e verificare prima la configurazione
   effettiva del job. Non modificare produttore, app o destinatari per questo caso.
2. **Allarmi sui parziali.** Il codice mantiene gli exit code attuali: il
   risultato degradato può ancora portare a exit 1. Le policy usano il successo
   del job; recuperare cinque fenomeni non fa sparire automaticamente l'allarme.
   Un eventuale exit 0 per il solo parziale richiede insieme un segnale operativo
   di degrado per fenomeno e causa, con denominatore. Non basta avere un log.
   Nessuna policy, soglia o codice di uscita cambiato in questo intervento.
3. **Pordenone, ore 06:00.** Il `security_failed=1` è separato: il log aggregato
   non conserva il controllo puntuale fallito. Non è provato un attacco, un
   errore FCM o lo stesso difetto di Chions; non viene dichiarato risolto.
4. **Riepilogo serale.** L'ultimo fallimento, del 20 ottobre, è `source_failed=12/12`.
   I test locali dei riepiloghi passano, ma non dimostrano il recupero operativo.
   La corsa ordinaria odierna delle 20:45 non è inclusa nell'audit concluso
   alle 18:55; nessuna esecuzione o automazione aggiunta per anticiparla.

Evidenze operative originali sotto `.tmp/job-audit-20261021` della radice
canonica, fuori da Git. Dati pubblici per il replay sotto
`.tmp/icon-payload-limit-deploy-20261020/new-run-http`; la fixture versionata
rende il caso ripetibile senza accesso al cloud e senza dati personali.

## Passaggio operativo autorizzato successivamente

Il proprietario ha autorizzato commit separati, promozione su main e aggiornamento
dei job, con verifica delle corse ordinarie. Si conserva exit 1 anche per
`data_degraded`: nessun errore viene convertito in successo. La configurazione
versionata di due allarmi avvisi viene chiarita nel titolo e nella documentazione,
con le istruzioni per leggere i tassi per fenomeno e causa. Soglie, finestre,
destinatari e invii ordinari rimangono invariati. Non è un nuovo allarme numerico
sulla qualità e non elimina automaticamente le email per i parziali.

Il rollback del consumatore deve conservare la nuova logica senza null→zero:
immagine candidata verificata con sidecar disabilitato è il ripiego conservativo
provato (Chions 17:00, 3/6 valutabili). La vecchia immagine operativa è conservata
come evidenza, non proposta come ritorno silenzioso alla conversione dei null.
Il verbale di deploy registrerà digest, configurazione e stato effettivamente applicati.
