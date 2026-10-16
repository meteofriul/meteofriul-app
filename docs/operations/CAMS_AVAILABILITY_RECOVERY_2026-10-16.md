# CAMS: disponibilità ADS, pianificazione e recupero

Questa modifica riguarda solo il job `meteofriul-cams` e il suo scheduler.
La configurazione attesa è versionata in
`experiments/weather_autonomy/production-runtime.json`; le costanti operative
del worker sono in `cams_runtime.py`.

## Evidenza e orari

Il 16 ottobre 2026 alle 04:54 UTC il gate pubblico ha trovato solo 25 lead
(0..24) per il ciclo del giorno. Non è stata inviata una richiesta ADS.

La [scheda ADS](https://ads.atmosphere.copernicus.eu/datasets/cams-europe-air-quality-forecasts?tab=overview)
indica 06:45 UTC per 0..48 e 08:30 UTC per 49..96. La
[documentazione ECMWF](https://confluence.ecmwf.int/spaces/CKB/pages/202173092/CAMS%2BRegional%2BEuropean%2Bair%2Bquality%2Banalysis%2Band%2Bforecast%2Bdata%2Bdocumentation)
garantisce l'orizzonte completo entro le 10:00 UTC e ammette disponibilità precedente.
Gli orari documentati non sostituiscono il gate: servono tutte le 28 variabili
e tutti i 97 lead, con partizioni disgiunte e le selezioni approvate.

La configurazione obiettivo è `0 9,10,11,15,20 * * *`, `Etc/UTC`:
- 09 UTC: primo tentativo dopo la finestra nominale ADS;
- 10 UTC: tentativo alla scadenza documentata;
- 11 UTC: recupero di ritardi;
- 15 e 20 UTC: passaggi esistenti, con UV nelle stesse due finestre.

Sono cinque invocazioni al giorno, tre più della configurazione live precedente.
In estate corrispondono alle 11, 12, 13, 17 e 22 italiane; in inverno alle
10, 11, 12, 16 e 21. La richiesta ADS è identificata per giorno e hash:
i passaggi successivi riprendono la stessa acquisizione, o verificano la famiglia
già pubblicata. Non avviano cinque richieste ADS diverse.

## Disponibilità attesa e guasti

Prima delle 10 UTC, solo assenza della data o lead incompleti, con motivazione
strutturata esplicita, possono produrre `source_pending`. Il job termina come
sonda riuscita, con `complete=false`, evento `publication_result/deferred`
e prossimo slot indicato. Nessun dato è pubblicato o reso fresco da quel risultato.
Lo stato Cloud Run SUCCESS, da solo, non prova che il ciclo sia stato pubblicato.

Alle 10 UTC e dopo, la stessa mancanza resta un errore con recupero limitato.
Righe ambigue, catalogo disabilitato, schema cambiato, errori di trasporto o UV
fallito non vengono trasformati in un rinvio riuscito. Il confronto con le
10 UTC include il tempo trascorso nel worker, anche attraversando la scadenza.

## Tempi e checkpoint

- Timeout Cloud Run: 1200 secondi; maxRetries: 0.
- Budget per decidere ulteriori passaggi: 900 secondi.
- Attesa ADS per passaggio: 120 secondi; pause: 30, 60, 120 secondi.
- Riserva prima di un'altra ripresa: 480 secondi per aria/pollini e altri
  180 se anche UV deve essere ripreso.
- Margine tra budget decisionale e timeout del task: 300 secondi.
- Retry dello scheduler: 0; il POST dello scheduler accoda un'esecuzione,
  non attende il suo esito. I passaggi successivi sono il recupero pianificato.

La riserva è un criterio prudente per ammettere una nuova ripresa, non una
garanzia sui tempi di ADS/GCS. Un'operazione lenta può ancora arrivare al timeout;
restano i checkpoint durevoli e i controlli che impediscono nuovi POST ambigui.
La pubblicazione atomica e la verifica di tutti i comuni restano obbligatorie.
Un fallimento di readback HTTP resta un fallimento, anche se la scrittura è riuscita.

Per applicare la configurazione, dopo i test dell'immagine e il salvataggio
della configurazione corrente, aggiornare esclusivamente il job CAMS con il
digest verificato e `--task-timeout=1200s --max-retries=0`, quindi lo scheduler
CAMS con gli orari indicati e `--max-retry-attempts=0`. Conservare target HTTP,
identità OAuth, deadline di invocazione, ambiente e segreti esistenti.
Non aggiornare il reader, gli altri job o i client.

## Limite che questo intervento non elimina

La policy attuale ammette CAMS fino a 30 ore dalla corsa. Il ciclo precedente
scade alle 06 UTC, prima della disponibilità ordinaria del nuovo orizzonte
completo. Il nuovo scheduler riduce il ritardo ulteriore, ma non elimina questo
intervallo. Non cambiare timestamp, non estendere la freschezza sul server e non
pubblicare un orizzonte parziale per aggirare i controlli. L'eventuale revisione
del contratto/client è separata da questa modifica operativa.

## Verifica

Test mirati: `test_cams_availability`, `test_cams_worker_recovery`,
`test_cams_request_plan`, `test_production_runtime_contract`, `test_cloud_worker`.
La build di produzione include il nuovo modulo di test ed esegue il container
senza rete. Dopo il deploy distinguere:
1. configurazione applicata e digest del codice;
2. eventuale sonda source_pending, senza nuova pubblicazione;
3. famiglia effettivamente pubblicata e verificata via HTTP, con ciclo,
   revisione, 215 comuni, 97 campioni e corrispondenza fra le due viste.

I risultati effettivi di rilascio vanno registrati nel rapporto esterno:
questo documento descrive il contratto operativo, non certifica un'esecuzione futura.
