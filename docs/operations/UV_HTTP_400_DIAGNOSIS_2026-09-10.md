# UV HTTP 400 del 10 settembre 2026 — diagnosi specifica

## Esito e limite della prova

Base: `CAMS_MORNING_DIAGNOSIS_2026-09-10.md`, sezione 5. Questo controllo
aggiunge letture puntuali dei log e degli artefatti esistenti; non riapre
l'audit generale e non modifica codice UV, validità, richieste o servizi.

**Provato:** il percorso interno `uv_cloud.enrich` ha ricevuto un `HTTPError`
con stato **400** durante `stage=submission`, nel job `pilot-cams-dwskx`,
alle **2026-09-10 10:02:02.863367 UTC / 12:02:02.863367 Europe/Rome (CEST)**.
L'esito persistito è `permanent_failure / uv_http_failure`, non pending né successo.

**Non ricostruibile dagli artefatti conservati:** il messaggio del provider,
il campo eventualmente rifiutato e il metodo HTTP che ha restituito 400.
Non è corretto attribuirlo con certezza a `date`, `leadtime_hour`, `area`,
`data_format`, licenza, credenziali o indisponibilità temporanea della corsa.
Non è neppure dimostrato che il 400 sia la risposta al POST di esecuzione:
il metodo SDK `submit` comprende prima una GET del processo.

Nessuna nuova acquisizione, reinvio ADS, riconciliazione autenticata ADS,
modifica di validità, pubblicazione, deploy o installazione Android.
Il problema sul Samsung non è dichiarato risolto.

## Evidenze rilette

Cloud limitato esplicitamente a progetto `meteofriul-pilot-20260906`, regione
`europe-west1` per il job. Tutti gli orari locali qui sono UTC+02:00.

| Evidenza | UTC 10 settembre | Europe/Rome | Contenuto |
|---|---|---|---|
| Progress `submitting` persistito | 10:02:01.843926 | 12:02:01.843926 | `uv_submission_starting` |
| Log della stessa fase | 10:02:02.007453 | 12:02:02.007453 | Emesso dopo scrittura/readback del progress |
| Intento originale | 10:02:02.007120 | 12:02:02.007120 | Timestamp nel documento, prima della chiamata SDK |
| Log del fallimento | 10:02:02.863367 | 12:02:02.863367 | `HTTPError`, `400`, `stage=submission` |
| Progress del fallimento persistito | 10:02:02.863014 | 12:02:02.863014 | `permanent_failure`, senza dettagli del provider |
| Esito componenti persistito/loggato | 10:02:03.013630 / 10:02:03.167142 | 12:02:03.013630 / 12:02:03.167142 | UV fallito, aria/pollini ancora pending, `complete=false` |

L'ordine dei millisecondi tra timestamp del documento e log è coerente con
la scrittura/readback prima di `emit`: non sono timestamp remoti ADS.

Il listing completo del prefisso
`gs://meteofriul-pilot-20260906-state/pilot/state/uv/2026-09-10/`
ha restituito **soltanto tre oggetti** al momento del controllo:

- `intent.json`, 734 byte, generation `1789034522086302`;
- `progress/20260910T100201-7a9071f616ca4d269bb1d5ea1c615432.json`;
- `progress/20260910T100202-d3d399edb20745c59890d12e8e294a0f.json`.

Nessun `job.json`, selettore di tentativo, storico di sostituzione, source GRIB,
decoded JSON o diagnostico con response body è presente in quel prefisso.
L'assenza di un riferimento remoto persistito **non autorizza a reinviare**
e, da sola, non prova l'assenza di qualunque lavoro sul fornitore.

La query di tutti i log del job nella finestra 10:01:55–10:02:10 UTC non
contiene traceback/testo SDK aggiuntivo. Il log `uv_failure` conserva soltanto
il riassunto controllato `exception details withheld; inspect the typed error
and local source location`, tipo e stato: il body originale non è recuperabile
da questo messaggio sanitizzato. Non compare neppure una source location UV.

## Richiesta identificata, non campo colpevole identificato

L'intento schema 2 lega dataset e richiesta al fingerprint
`19520f643413bf2d8a39852921a0b0276dcb0d84d4722d294b75ee6c174df227`:

| Campo | Valore persistito |
|---|---|
| dataset | `cams-global-atmospheric-composition-forecasts` |
| variable | `uv_biologically_effective_dose` |
| date | `2026-09-10` |
| time | `00:00` |
| leadtime_hour | Tutti gli interi 0…71, serializzati come stringhe |
| type | `forecast` |
| area | `[46.8, 12.0, 45.2, 14.4]`, N/W/S/E |
| data_format | `grib` |

`uv_cloud.py:229–233` seleziona la data corrente dalle 10 UTC e quella
precedente prima delle 10. Il worker ha quindi chiesto intenzionalmente la
corsa del 10; **questa scelta di orario nel codice non prova che ADS avesse
già reso disponibile quella selezione completa**.

È stato riletto anche `pilot/state/uv/2026-09-09/intent.json`: rispetto alla
richiesta del 10 cambia soltanto `date`. La recovery riuscita del 9 è attestata
nel resoconto `CAMS_UV_RECOVERY_2026-09-09.md`. Questo rende poco fondata
l'attribuzione immediata a un errore statico negli altri campi, ma non esclude
una risposta contingente o nuovi vincoli lato fornitore. Nessuno snapshot dei
vincoli UV all'ora del fallimento è conservato nel prefisso del 10.

`submit_uv_pilot.py` è uno script locale diverso: controlla i vincoli pubblici
prima del suo invio e usa la richiesta locale ridotta (lead 24…47, altra area).
Il worker non lo richiama. Non è la fonte della richiesta fallita e non è stato
eseguito per questa diagnosi.

## Dove si perde il dettaglio

Nel codice pertinente al job:

1. `uv_cloud.py:419–440`: assegna `stage=submission`, salva l'intento e chiama
   `client.submit(DATASET, request)`.
2. `uv_cloud.py:249–252`: il callback di log SDK è silenzioso; warning catturati,
   nessuna serializzazione del messaggio del fornitore.
3. Il catch finale registra `error_type`, `http_status` e un reason code locale.
   `_http_status` legge lo stato dall'eccezione, non il motivo del 400.
4. `operational_diagnostics.py:error_fields` esclude testo arbitrario,
   URL, body e credenziali. La selezione dei file di traceback ammette
   `cloud_worker.py`, `cams_request_plan.py`, `retrieve_cams.py` e
   `local_pipeline`, ma non `uv_cloud.py` né i moduli SDK.

Il Dockerfile pinna `ecmwf-datastores-client==0.5.3`. Nel sorgente ufficiale
di quella versione `Client.submit` delega a `Processing.submit`, che esegue
`get_process(collection_id).submit(request)`: una GET del processo precede
il POST a `.../execution`, con i campi della richiesta sotto `inputs`.
Il suo gestore HTTP conserva normalmente `title`, `traceback`, `detail`
nell'eccezione e vi allega la risposta. Quei dettagli erano quindi potenzialmente
disponibili al catch, ma il nostro percorso non li ha conservati.
[Client SDK 0.5.3](https://raw.githubusercontent.com/ecmwf/ecmwf-datastores-client/0.5.3/ecmwf/datastores/client.py),
[Processing SDK 0.5.3](https://raw.githubusercontent.com/ecmwf/ecmwf-datastores-client/0.5.3/ecmwf/datastores/processing.py).

Si può localizzare il percorso al confine della chiamata SDK, non scegliere
retroattivamente una delle due operazioni HTTP o un campo colpevole. Cambiare
la richiesta ora sulla base del solo 400 sarebbe una correzione per ipotesi.

## Diagnostica minima proposta, non implementata

Per un futuro tentativo **già autorizzato**, senza aggiungere invii o retry:

- Allegare al catch una descrizione strutturata, con method e route **enumerati**
  (`process_metadata_get`, `execution_post`, `unknown`), stato HTTP, dataset,
  data/corsa e request SHA256. Non salvare URL completi, query, header o request
  preparata; il documento di intento contiene già i campi scientifici necessari.
- Aggiungere una source location locale esplicita UV, senza traceback SDK grezzo.
- Leggere un eventuale JSON di errore con limite finito, per esempio 8 KiB,
  senza serializzarlo integralmente. Emettere soltanto codici mappati a un
  vocabolario locale controllato e nomi di campo presenti nella safelist della
  richiesta. Non rendere pubblici `detail`, `traceback`, messaggi arbitrari,
  valori riflessi della richiesta, token, cookie o link firmati.
- Per risposte non classificabili, conservare solo tipo, dimensione e SHA256
  del body oltre a `unclassified_provider_error`; la classificazione richiederà
  un canale diagnostico riservato approvato, con redazione preventiva. Un hash
  da solo non svela il motivo e non va presentato come una diagnosi completa.
- Se serve dimostrare la disponibilità della selezione, associare a quel
  tentativo uno snapshot dei **metadati pubblici** (timestamp e hash dei vincoli,
  campi/lead compatibili), senza chiamare l'endpoint di esecuzione. Una lettura
  pubblica fatta oggi non ricostruisce i vincoli delle 10:02 del 10 settembre.
- Testare offline la sanitizzazione con credenziali sintetiche in messaggi,
  URL, body e header; nessun campo non ammesso deve passare ai log.

Tale strumentazione richiede un successivo cambiamento di sorgenti e una
distribuzione autorizzata prima di poter osservare un nuovo errore reale.
Non può recuperare il body storico perduto, non giustifica un reinvio adesso
e non deve trasformare errori permanenti o pending in successo.

## Comandi e distinzione delle verifiche

Letture live eseguite con il `gcloud.py` installato localmente, Python 3.13:

```powershell
py -3.13 '<Google Cloud SDK>/lib/gcloud.py' logging read 'resource.type="cloud_run_job" AND resource.labels.job_name="pilot-cams" AND resource.labels.location="europe-west1" AND labels."run.googleapis.com/execution_name"="pilot-cams-dwskx" AND timestamp>="2026-09-10T10:01:55Z" AND timestamp<="2026-09-10T10:02:10Z"' --project=meteofriul-pilot-20260906 --limit=100 --format=json
py -3.13 '<Google Cloud SDK>/lib/gcloud.py' storage ls 'gs://meteofriul-pilot-20260906-state/pilot/state/uv/2026-09-10/**' --project=meteofriul-pilot-20260906
```

Inoltre `storage cat` dei tre oggetti elencati e dell'intento del 9,
`storage objects describe` dell'intento del 10, sempre con progetto esplicito.
Sorgente SDK pubblico letto in sola lettura, non eseguito. Nessun test live ADS,
nessun test sintetico aggiuntivo e nessun controllo sul telefono in questa
sotto-attività; nessuna credenziale ADS letta o mostrata.

Questi orari riguardano **UV**, non la pubblicazione della famiglia aria/pollini:
per quest'ultima restano distinti l'intento 12:01:11 CEST, il cambio del puntatore
**12:10:02.461 CEST / 10:10:02.461 UTC** e la verifica componenti conclusiva
12:10:37.202 CEST / 10:10:37.202 UTC, come nel rapporto base.
