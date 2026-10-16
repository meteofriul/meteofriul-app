# B01 — revoche CAMS durevoli

Data verifica: 13 settembre 2026

Revisione di partenza: `3518166f10835034c0dcf32395a3bb669ba22b7b`

Ambito: sola `localPilot`, autorità delle revoche della famiglia CAMS aria/pollini

Stato: corretto nei sorgenti e verificato localmente; non distribuito

## Esito

La decisione contenuta in un puntatore CAMS verificato raggiunge ora il runtime
prima del download della release sostitutiva. Se revoca una corsa già conservata,
il runtime:

1. registra subito la decisione monotona nello stato della sessione;
2. rende non presentabili aria e pollini della corsa revocata;
3. salva e rilegge byte per byte un journal separato dai bundle dati;
4. usa il journal come autorità a ogni successiva lettura, inclusa la riapertura
   offline;
5. prosegue separatamente con ICON e con l'eventuale candidato CAMS sostitutivo.

La sostituta non viene trattata come dato finché release, manifest e oggetti non
hanno superato i controlli già esistenti. La revoca, invece, è vincolante appena
il puntatore che la contiene ha superato schema, catalogo e transizione.

## Causa corretta

Alla revisione iniziale il client raw vedeva correttamente
`disabled_run_ids`, ma la notifica era un callback facoltativo i cui errori
venivano assorbiti. L'adapter teneva la decisione soltanto nella richiesta in
corso e il runtime la osservava solo quando riceveva un bundle CAMS terminale.
Una release pending o fallita, un errore ICON o l'interruzione prima del bundle
finale potevano quindi lasciare la vecchia corsa disponibile; alla riapertura
non esisteva un'autorità CAMS durevole equivalente a quella già presente per
ICON.

## Modifica nei sorgenti

### Confine client e adapter

- `weatherV1Client.js` consegna sempre al destinatario di safety la fotografia
  del puntatore famiglia già verificato. Un errore del destinatario non viene
  più ignorato. Anche se la bonifica della cache HTTP raw fallisce, la decisione
  verificata viene prima consegnata al runtime e l'errore di cache resta
  osservabile.
- `localWeatherV1Adapter.js` propaga `onCamsFamilyLatest` indipendentemente dal
  completamento di release e ICON. Nel percorso differito un errore di safety è
  distinto da un normale esito CAMS unavailable e raggiunge
  `onCamsFailure`, senza bloccare il primo rendering ICON.

### Journal e runtime

- `localWeatherV1Runtime.js` introduce un journal CAMS versione 1, separato da
  `active` e `candidate`, con scope legato all'URL del data plane e al catalogo.
  Il record contiene revisione, data di pubblicazione, run attivo, elenco
  cumulativo dei run disabilitati e SHA-256 del contenuto canonico.
- La scrittura è considerata durevole solo dopo rilettura esatta degli stessi
  byte. Revisioni o date regressive, perdita di revoche già osservate e rollback
  non autorizzati sono respinti.
- Il journal viene ripristinato prima di consultare memoria, bundle attivo o
  candidato. Una vecchia copia contenente il run revocato viene filtrata in
  lettura anche se la riscrittura opportunistica del bundle non era riuscita.
- Se l'interruzione lascia una sostituta completa nel formato compatto
  `cams-delta` sopra una base appena revocata, il runtime la ricostruisce prima
  di sanificare la base. La promuove soltanto se la sua decisione famiglia e il
  suo run attivo coincidono esattamente con l'autorità durevole corrente;
  candidati vecchi o estranei non possono prevalere sul journal.
- Le cache runtime già vive (`retainedBundles` e `recentlyVerifiedBundles`) sono
  sanificate subito. La notifica della revoca non attende ICON.
- Un journal corrotto o illeggibile mette in quarantena solo CAMS; ICON resta
  leggibile e i byte di `active`, `candidate` e UV non vengono alterati. Solo un
  nuovo puntatore verificato può riparare il journal.
- `weatherApi.js` e `homeDataController.js` propagano il canale di errore CAMS.
  Nella pilota il controller registra sempre il fallimento e può inoltrarlo al
  chiamante.

### Isolamento dei componenti

La revoca famiglia rimuove esclusivamente aria e pollini appartenenti ai run
indicati. Restano invariati:

- ICON, previsione oraria e giornaliera;
- cache e candidato UV;
- dati CAMS di corse non revocate;
- cache separate delle altre località, che saranno comunque filtrate dal
  journal globale della famiglia quando lette;
- soglie, finestre temporali, selezione del campione, scheduler e frequenze.

La cache Home storica non è un percorso alternativo nella `localPilot`:
`usesAutonomousWeatherProvider()` disabilita lettura e scrittura di
`weatherBootstrapCache:v3` e rende inerte il **prefetch legacy** collegato al
worker meteo condiviso. Il plugin nativo dedicato `PilotWeatherPrefetch`, invece,
resta attivo nella pilota: fornisce al client soltanto byte immutabili legati
all'hash atteso e non scrive bundle presentabili. Quei byte attraversano
validatore, adapter e runtime; il journal viene ripristinato prima che il runtime
possa restituire un bundle alla presentazione.

Il controllo successivo `AppRoutes.coldStartRevocation.test.jsx` protegge anche
la finestra più stretta dell'avvio a freddo sulle rotte dirette Meteo e Home.
Con un `active` A già persistito, un journal durevole che revoca A e una lettura
nativa lasciata pendente, prova che la lettura del journal segue l'invocazione
del render e precede sia la prima mutazione/snapshot DOM non vuota osservata sia la
lettura dell'oggetto nativo. Sulla Home intercetta inoltre la vera
`readInitialHomeData` e verifica che lo stato iniziale sia già sanificato:
aria assente, pollini `unavailable` senza valori e diagnostica `RUN_DISABLED`,
mentre la sintesi ICON resta presentabile. Non è emerso un varco temporale
nelle sequenze DOM/jsdom esercitate quando il journal esiste; la sua assenza per
mancata persistenza resta il limite distinto documentato sotto.

Il successivo `App.coldStartRevocation.test.jsx` del commit `c6eef12` copre
separatamente l'avvio ordinario di `App` senza override di tab: atterra su Home,
mantiene ICON presentabile e passa a Meteo nella stessa sessione. Il caso
revocato resta sanificato con la sostituta pending; il caso di controllo senza
revoca presenta gli stessi dati CAMS validi. Sono snapshot DOM jsdom, non una
traccia distinta di ogni commit React né frame fisici della WebView o del
Samsung.

## File modificati

Codice applicativo:

- `frontend/src/services/weatherV1Client.js`;
- `frontend/src/services/localWeatherV1Adapter.js`;
- `frontend/src/services/localWeatherV1Runtime.js`;
- `frontend/src/services/weatherApi.js`;
- `frontend/src/features/home/homeDataController.js`.

Prove e configurazione diagnostica:

- `frontend/src/app/AppRoutes.coldStartRevocation.test.jsx`;
- `frontend/src/services/localWeatherV1Runtime.revocation.test.js`;
- `frontend/src/services/localWeatherV1Runtime.test.js`;
- `frontend/src/services/localWeatherV1Adapter.test.js`;
- `frontend/src/services/weatherV1Client.test.js`;
- `frontend/src/services/weatherApi.test.js`;
- `frontend/src/services/localConditionsApi.test.js`;
- `frontend/src/features/home/homeDataController.test.js`;
- `frontend/cams-family-revocation.diagnostic.config.js`.

Documentazione:

- `docs/operations/B01_CAMS_DURABLE_REVOCATION_FIX_2026-09-13.md`.

## Fallimento della persistenza

Il caso è trattato esplicitamente e non viene dichiarato come successo.

### Garanzia nella sessione corrente

La decisione verificata è applicata allo stato di sessione prima del tentativo
di persistenza. Se la scrittura o la rilettura del journal fallisce, il run resta
quindi in quarantena nella sessione corrente e `durableRevision` non viene
avanzata. Nel percorso differito la UI riceve il bundle CAMS sanificato e
l'errore `CAMS_REVOCATION_PERSIST_FAILED` percorre `onCamsFailure`; nel percorso
sincrono la richiesta rigetta e la quarantena resta osservabile nelle letture
successive della stessa sessione.

### Garanzia alla riapertura

- Se il journal è stato scritto e riletto esattamente, la riapertura resta
  protetta anche se il processo termina prima della sostituta o se i vecchi byte
  di `active` e `candidate` sono ancora presenti.
- Se la scrittura riesce ma la rilettura immediata fallisce, quella chiamata non
  dichiara la decisione durevole. Una riapertura successiva può applicarla solo
  se riesce finalmente a rileggere e verificare integralmente quei byte.
- Se non è possibile provare il journal ma la riscrittura mirata dei bundle è
  riuscita, i dati revocati non sono più nei bundle salvati; l'operazione resta
  comunque segnalata come errore perché la decisione durevole non è dimostrata.
- Se falliscono sia il journal sia la riscrittura dei bundle, una nuova sessione
  non può conoscere una decisione mai salvata. Il test documenta volutamente
  che la vecchia corsa può ricomparire dopo un vero riavvio: la sessione corrente
  resta fail-closed, ma non viene promessa una durabilità inesistente.

Il feedback generale del gesto di refresh può già essersi concluso dopo il
primo rendering ICON. Quella aggregazione temporale è il B08 dell'audit e non è
stata modificata in questo intervento B01; l'errore CAMS resta comunque
osservabile nel canale runtime/controller.

## Prove B01

La nuova raccolta ordinaria
`src/services/localWeatherV1Runtime.revocation.test.js` copre in modo
deterministico:

- revoca con release sostitutiva pending e riapertura offline;
- revoca notificata prima della conclusione ICON e successivo errore ICON;
- interruzione dopo il journal, lasciando intenzionalmente vecchi `active` e
  `candidate` nello storage;
- interruzione con sostituta B già salvata come `cams-delta` sopra la base A
  revocata, recuperata alla riapertura sostituendo atomicamente `active` e
  rimuovendo `candidate` soltanto dopo;
- download della release sostitutiva fallito;
- risposta più vecchia successiva a una decisione durevole più recente;
- puntatore non valido che non può produrre una revoca;
- journal corrotto o illeggibile, con quarantena CAMS e conservazione ICON/UV;
- riparazione solo tramite un nuovo puntatore verificato;
- storage durevole assente;
- scrittura/rilettura della revoca fallita nel percorso sincrono e differito;
- differenza dimostrata fra sicurezza della sessione e garanzia alla riapertura.

Le prove esistenti continuano a coprire attivo+candidato, risposta CAMS tardiva,
cambio d'ora, cambio località, identità comunale e mancata regressione di un
bundle più recente.

## Prima e dopo

### Prima della modifica, sulla base `3518166`

```powershell
cd frontend
npx vitest --configLoader native --config cams-family-revocation.diagnostic.config.js run
```

Esito: **0 superati, 2 falliti, 0 saltati**, con sei verifiche pertinenti
fallite: la corsa A rimaneva disponibile nel risultato, nel bundle persistito e
nella cold read.

### Stato finale

| Comando | Esito |
| --- | --- |
| `npx vitest --configLoader native --config cams-family-revocation.diagnostic.config.js run` | 1 file, **2/2 test superati**, 0 falliti, 0 saltati |
| `npx vitest --configLoader native run src/services/localWeatherV1Runtime.revocation.test.js src/services/localWeatherV1Runtime.test.js src/services/localWeatherV1Adapter.test.js src/services/weatherV1Client.test.js src/services/weatherApi.test.js src/services/localConditionsApi.test.js src/features/home/homeDataController.test.js` | 7 file, **323/323 test superati**, 0 falliti, 0 saltati |
| `npx vitest --configLoader native --config cams.diagnostic.config.js run` | 1 file, **13/13 test superati**, 0 falliti, 0 saltati |
| `npx vitest --configLoader native --config cams.hour-boundary.diagnostic.config.js run` | 1 file, **10/10 test superati**, 0 falliti, 0 saltati |
| `npx vitest --configLoader native run src/services/localWeatherV1Runtime.camsRecovery.test.js src/services/localWeatherV1Runtime.generation.test.js src/services/camsHourlyCache.test.js src/app/AppRoutes.activeCandidate.test.jsx src/app/AppRoutes.camsEpisode.test.jsx src/app/App.camsRecovery.test.jsx` | 6 file, **28/28 test superati**, 0 falliti, 0 saltati |
| `npx vitest --configLoader native run src/services/weatherCache.test.js src/services/weatherProviderRuntime.test.js src/services/localWeatherPilotHome.test.js` | 3 file, **15/15 test superati**, 0 falliti, 0 saltati |
| `npm run lint` | **superato**, nessun errore o avviso |
| `npm run build` | **superato**, inclusi service worker e controllo push |
| `npm test` | 451 file: 446 superati, 4 saltati, 1 fallito; 3.531 test: **3.519 superati, 11 saltati, 1 fallito** |

L'unico fallimento della raccolta completa è estraneo e non introdotto da B01:
`src/features/events/EventsView.test.jsx`, test
`shows available descriptions in the list without fetching a detail`, attende
la classe `mf-events-card__excerpt`, assente nel markup corrente. Né il test né
la UI Eventi sono stati modificati in questo intervento.

Gli 11 test saltati sono le quattro raccolte live opt-in già esistenti:

- 5 test ICON fallback reale, richiedono
  `METEOFRIUL_RUN_ICON_FALLBACK_LIVE=1`;
- 5 test data plane pilota reale, richiedono
  `METEOFRIUL_RUN_LOCAL_PILOT_LIVE=1`;
- 1 benchmark reale, richiede `METEOFRIUL_TIMING=1`.

Non sono stati eseguiti test live, richieste cloud o prove sul Samsung. I test
indicati come superati sono locali e deterministici.

## Avvisi build invariati

La build conserva due avvisi preesistenti e non pertinenti a B01:

1. `AlmanacView.jsx` è importato sia dinamicamente da `AppRoutes.jsx` sia
   staticamente da `WeatherSkyCard.jsx`; l'import dinamico non crea un chunk
   separato.
2. Il chunk principale minificato supera 500 kB
   (`3,681.92 kB`, gzip `836.43 kB`). Nessuna soglia è stata cambiata.

## Limiti e dipendenze residue

- Nessun sistema può garantire una revoca dopo un riavvio se il dispositivo non
  ha salvato né il journal né una copia sanificata del bundle. Il runtime rende
  questa condizione visibile e non la etichetta come durevole.
- Il B08 sul feedback complessivo del refresh resta separato.
- L'effetto su un dispositivo reale richiederà una futura build e installazione
  della pilota, esplicitamente escluse da questo intervento.

Non sono stati modificati beta ufficiale, Firebase, backend, scheduler,
frequenze, soglie, pipeline o configurazioni cloud. Non è stato eseguito alcun
deploy né alcuna installazione Android.
