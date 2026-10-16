# Diagnosi aria/pollini della pilota — 10 settembre 2026

## Esito e perimetro

Diagnosi e riproduzioni, non correzione funzionale. Base applicativa `cd3a4bf`.
Nessun intervento su sito, UI, testi, ICON, Firebase, notifiche, Android, scheduler,
servizi o dati cloud. Nessuna acquisizione ADS, ripubblicazione o distribuzione.
Le letture cloud sono limitate al progetto `meteofriul-pilot-20260906`,
regione `europe-west1`; nessun uso del progetto predefinito.
Sono aggiunti soltanto questo resoconto e una suite diagnostica esplicita, isolata
dalla normale selezione dei test. Il suo fallimento rimane visibile, non saltato.

Conclusioni:

1. Il limite CAMS di **30 ore dalla corsa** scartava previsioni ancora presenti.
   Non era la fine della copertura e non è una scadenza imposta da Copernicus.
2. Alle 07:00 la richiesta dei dati non era stata accettata né messa in coda:
   il controllo preliminare del catalogo fallì prima dell'acquisizione.
3. **12:01:11 non è la pubblicazione:** è il timestamp di intento congelato.
   Il puntatore pubblico cambiò alle **12:10:02.461 CEST**; pubblicazione/readback
   terminarono alle 12:10:34.721; aria e pollini furono `verified` alle 12:10:37.202.
4. La cache negativa dura 10 minuti, ma non avvia un tentativo alla scadenza.
   Il coordinamento con il controllo dell'app ogni 10 minuti può spostare il
   recupero al controllo dei 20 minuti nello scenario riprodotto.
5. I log A52 mostrano anche GET da 5,65–5,98 secondi: superano il budget CAMS di
   4 secondi. Questo è un ulteriore meccanismo concreto, non quattro ore di cache.
6. Una race distinta è riprodotta: rigettando una risposta vecchia il runtime
   può cancellare il bundle più nuovo. Non è dimostrato che sia accaduta sul telefono.

Non è quindi dimostrato che quattro ore senza dati fossero inevitabili, né che
la cache abbia causato tutto l'episodio.

## 1. Giornata, località, versione e cronologia

La giornata ricostruita è il **10 settembre 2026**, corroborata dai log CAMS e
dalle richieste con user-agent Android 14 / Samsung **SM-A525F**, non dedotta
dalla corsa UV. Nei download successivi compare **Pordenone, ISTAT 093033**.
Questi log non contengono seriale, package, schermata visualizzata o gesto di refresh:
l'attribuzione al telefono dell'utente è fortemente coerente, non un'identità univoca.

Versione pertinente documentata: `com.meteofriul.app.localpilot`,
`1.0.1-local-pilot`, versionCode `300012`, installata il 9 settembre alle
16:44:34 UTC / 18:44:34 CEST. L'APK locale conservata ha ancora SHA256
`e17ea2483f0cb7762f385c5fc70b873c8bf629ceed410c8a2d7df7b5a57054bf`,
identico al verbale di installazione. I file di validità/cache/adapter/resume
esaminati non differiscono da `afe0d87`; le differenze successive in App.jsx
riguardano “I perché”, non i meccanismi meteo qui descritti.
`adb devices -l` non rileva telefoni collegati: nessun dump della cache o logcat
mattutino è stato acquisito; nessuna reinstallazione o pulizia del telefono.

Tutte le ore italiane sotto sono Europe/Rome, **CEST = UTC+02:00**.
Le frazioni di secondo sono conservate dove distinguono intenti e pubblicazione.

| Evento | UTC | Europe/Rome | Evidenza / significato |
|---|---|---|---|
| Corsa precedente aria/pollini | 09/09 00:00:00 | 09/09 02:00:00 | `20260909T000000Z` |
| Riuso automatico riuscito | 09/09 20:01:39.922 | 09/09 22:01:39.922 | `pilot-cams-stwp5`: air/pollen/UV separatamente verified, senza nuova acquisizione |
| Nuova corsa richiesta | 10/09 00:00:00 | 10/09 02:00:00 | `20260910T000000Z`; non è l'ora di disponibilità |
| Creazione esecuzione mattutina | 10/09 05:00:16.961 | 10/09 07:00:16.961 | `pilot-cams-8xdbl`, autore Scheduler |
| Fallimento catalogo | 10/09 05:01:01.432 | 10/09 07:01:01.432 | `constraints_no_compatible_rows`, nessuna acquisizione inviata |
| Fine esecuzione mattutina | 10/09 05:01:05.392 | 10/09 07:01:05.392 | exit 2, non successo |
| Fine usabilità applicativa corsa precedente | 10/09 06:00:00 | 10/09 08:00:00 | ammessa all'istante esatto; respinta immediatamente dopo |
| Creazione esecuzione di mezzogiorno | 10/09 10:00:31.741 | 10/09 12:00:31.741 | `pilot-cams-dwskx` |
| Inizio worker / timestamp intento | 10/09 10:01:11.762 / 10:01:11 | 10/09 12:01:11.762 / 12:01:11 | origine del precedente “pubblicato alle 12:01” |
| Catalogo completo verificato | 10/09 10:01:13.486 | 10/09 12:01:13.486 | 1 riga compatibile, 97 lead, nessun lead mancante |
| Intento acquisizione persistito | 10/09 10:01:16.209 | 10/09 12:01:16.209 | una sola richiesta regionale logica |
| Riferimento remoto persistito | 10/09 10:01:17.483 | 10/09 12:01:17.483 | `submitted.json`; ADS osservato accepted alle 10:01:19.069 UTC |
| Attese bounded, riferimento conservato | 10/09 10:02:01.118 e 10:03:50.334 | 10/09 12:02:01.118 e 12:03:50.334 | remote_pending, non pubblicato, complete=false |
| ADS osservato successful | 10/09 10:06:54.305 | 10/09 12:06:54.305 | osservazione del completamento remoto, non suo timestamp esatto |
| Download concluso / checkpoint | 10/09 10:06:56.202 / 10:06:57.561 | 10/09 12:06:56.202 / 12:06:57.561 | downloaded_pending_decode_validation, poi artefatti persistiti |
| Decodifica/validazione | 10/09 10:07:00.846–10:07:20.965 | 10/09 12:07:00.846–12:07:20.965 | checkpoint validato 215 comuni alle 10:07:55.066 UTC |
| Manifest core / pollini salvati | 10/09 10:08:54.060 / 10:09:44.924 | 10/09 12:08:54.060 / 12:09:44.924 | staging, non ancora cambio di famiglia |
| Release creata / cambio puntatore atomico | 10/09 10:10:02.051 / 10:10:02.461 | 10/09 12:10:02.051 / 12:10:02.461 | metadata GCS, generation puntatore `1789035002435738` |
| Fine pubblicazione/readback | 10/09 10:10:34.721 | 10/09 12:10:34.721 | non coincide con l'istante del cambio puntatore |
| Aria e pollini verified | 10/09 10:10:37.202 | 10/09 12:10:37.202 | esito persistito, 215 comuni per componente |
| Fine job complessivo | 10/09 10:10:39.874 | 10/09 12:10:39.874 | fallito per UV, non per la release aria/pollini |

### Letture compatibili con l'A52, separate dai controlli dell'agente

I timestamp dei request log indicano **inizio richiesta al server**; la durata
non include tutto il percorso di rete né prova ricezione/visualizzazione nel client.
Le richieste Python e Windows delle sonde sono state escluse dalla tabella.

| UTC 10/09 | CEST 10/09 | Client / risultato |
|---|---|---|
| 08:02:24.967 | 10:02:24.967 | WebView GET famiglia, 304, durata 5,770 s; famiglia ancora del 9 |
| 10:07:14.448 | 12:07:14.448 | WebView GET famiglia, 304, durata 5,984 s; prima del cambio puntatore |
| 11:34:32.962 | 13:34:32.962 | WebView GET famiglia, 200, durata 5,645 s; nessun seguito release/payload WebView in quel gruppo |
| 11:34:38.945–11:34:39.547 | 13:34:38.945–13:34:39.547 | client nativo Dalvik scarica famiglia, release, due manifest e payload 093033 della corsa 10 |
| 12:10:02.714–12:10:03.996 | 14:10:02.714–14:10:03.996 | WebView scarica la stessa catena completa, 200; GET famiglia 0,0027 s |

I primi tre GET erano preceduti da preflight OPTIONS di circa 1,5–2,1 s.
Le durate dei GET da sole superano il timeout applicativo CAMS di 4 s.
Il timeout sul telefono è quindi una spiegazione fortemente supportata e
riprodotta, ma non una misura diretta del suo stato JavaScript.
Il prefetch nativo può aver riempito artefatti senza aggiornare la schermata:
non rende autorevole la propria cache, non salta il controllo di latest e non
invalida la finestra di verifica del runtime.

“Dopo le 12” rimane la testimonianza dell'utente. Non possiamo associare uno di
questi gruppi al gesto manuale, stabilire quando la UI ha mostrato il dato, né
presumere che l'app sia rimasta aperta/visibile nelle pause tra le richieste.

## 2. Perché le 08:00 non erano la fine delle previsioni

Fonte effettiva: ADS API, dataset `cams-europe-air-quality-forecasts`, ensemble
regionale, superficie, corsa 00 UTC. Il piano del 9 chiede GRIB, area
N46.7/W12.2/S45.5/E14.0, **lead 0…96 inclusi: 97 istanti, 28 variabili**
(22 non polliniche e 6 polliniche). Il core conserva le 28 variabili; il prodotto
pollini ne proietta le sei pertinenti. Nessun taglio a 24/30 ore nei payload.

I due manifest e i JSON Pordenone del 9 contengono:

- `valid_from`: 09/09 00:00 UTC / 02:00 CEST;
- `valid_to`: 13/09 00:00 UTC / 02:00 CEST;
- `fresh_until`: 10/09 00:00 UTC / 02:00 CEST (24 ore dalla corsa);
- `usable_until`: 10/09 06:00 UTC / 08:00 CEST (30 ore dalla corsa).

| Ora italiana del 10 | Istante previsionale presente, UTC | Età corsa | Copertura residua | PM2.5 µg/m³ | Ambrosia grani/m³ | Esito |
|---|---|---|---|---:|---:|---|
| 08:01 | 06:00 | 30h 1m | 65h 59m | 1,4008763 | 0,375 | EXPIRED |
| 09:00 | 07:00 | 31h | 65h | 1,3646289 | 6,666015625 | EXPIRED |
| 11:00 | 09:00 | 33h | 63h | 1,4728854 | 10,8759765625 | EXPIRED |

I tre campioni hanno valori numerici per aria e pollini senza flag missing.
Alle 08:01 non esiste un nuovo campione al minuto: `currentRow` seleziona quello
delle 08:00 (un minuto prima), non interpola né spaccia una vecchia misura per nuova.

Responsabilità precise nel codice:

- `experiments/weather_autonomy/local_pipeline/contract_v1.py:538`:
  produttore, `usable = min(run + 30h, end)` per CAMS.
- `frontend/src/services/weatherV1Client.js:83` e `:107`: medesima policy
  24h/30h per i due componenti; requisito di copertura futura **0h**.
  `assessFreshness`, `:624`, rifiuta con `current > usableUntil` (`:635`).
  La policy alternativa ICON è limitata esplicitamente al provider ICON (`:630`).
- `frontend/src/services/localWeatherV1Runtime.js:388`: ulteriore controllo
  età CAMS ≤30h e campione corrente con ritardo <60 minuti.
  `withoutExpiredCams`, `:257`, rimuove il supplemento non più utilizzabile.
- `frontend/src/services/localWeatherV1Adapter.js:202`: `currentRow` sceglie
  l'ultimo istante ≤adesso. Il limite di un'ora sul campione conservato non è
  la copertura completa del JSON originale.

La cache raw conserva JSON/ETag verificati; il bundle conserva anche un campione
adattato. `fetchManifest` e `fetchMunicipality` rivalidano freschezza (`:2074`,
`:2106`) dopo cache/304/fallback: rileggere o forzare non cambia `run_at`.
Senza dump non sappiamo quali byte fossero nella cache A52 alle 08:01.

Evidenza della decodifica originale: registro persistito
`pilot/state/runs/b4bc62dcf04dae30fdf38403df3568203c4111da2c6d03c214516cd259353b4c.sqlite`,
letto in memoria: PUBLISHED, 215 comuni, 28 variabili, 97 ore.
GRIB 2.223.700 byte, SHA256
`01435a4ee2418efbe030f5a6ba9cd89ffd3f6b9158e99939eaaa67b9f1b0627c`;
decodificato 10.294.047 byte, SHA256
`08b7530f1f17c0bf9ad52f80dc08e7b49025fb61245b5c772857d8ea68bbcd5a`;
report SHA256 `0181e69158b97f8ab7774b0f291aa9d8516cf375afdd06c4fcce7cf3a03c8198`.
I byte originali GRIB/report del 9 non sono nei checkpoint recuperabili né nei
file locali cercati: questa è un'attestazione persistita, non una nuova decodifica
indipendente dell'originale. I 97 campioni pubblicati sono stati letti realmente.

## 3. Disponibilità ufficiale, tentativi e riuso

La documentazione ufficiale distingue la produzione nominale dei pacchetti
D0/D1 alle 05:50/05:55 UTC e D2/D3 alle 07:30/08:00 UTC, dalla disponibilità
garantita: lead 0–48 entro le 08 UTC, lead 49–96 entro le 10 UTC; possono comparire prima.
In settembre sono rispettivamente 07:50/07:55/09:30/10:00 CEST e garanzie
10:00/12:00 CEST. Le finestre attuali 07/12/17/22 CEST corrispondono a
05/10/15/20 UTC: la prima precede anche la produzione nominale D0; quella delle
12 coincide con la garanzia dell'intero orizzonte richiesto. Questi orari non
provano l'istante di disponibilità effettivo del 10 settembre.
[Documentazione ECMWF/CAMS](https://confluence.ecmwf.int/spaces/CKB/pages/202173092/CAMS%2BRegional%2BEuropean%2Bair%2Bquality%2Banalysis%2Band%2Bforecast%2Bdata%2Bdocumentation).

Il canale realmente usato è ADS API autenticata, non SFTP/HTTPS Data Portal.
Il secondo è un canale distinto, indicato per applicazioni time-critical e con
accesso da concordare: non è attivo né viene proposto come cambio implicito.
[Canali ECMWF](https://confluence.ecmwf.int/spaces/CKB/pages/599163953/SFTP%2Band%2BHTTPS%2Baccess%2Bto%2BCAMS%2BEuropean%2Bair%2Bquality%2Bforecast%2Bdata).

Alle 07:01 il controllo vedeva 93 righe di vincoli, 20 pertinenti alla data e
**zero** righe compatibili con la selezione completa; non dimostra assenza di
qualsiasi dato parziale o di ogni singolo file. A mezzogiorno vedeva 101 righe,
29 per la data e una riga completa. La disponibilità completa è osservata entro
12:01:13, non monitorata continuamente nell'intervallo precedente.

C'è anche un difetto nel percorso di errore del worker:
`cloud_worker.py:86` chiama il `main` CLI di `cams_request_plan.py`;
quest'ultimo trasforma `PublicMetadataUnavailable` in `SystemExit(2)` (`:903`).
Il recupero in `_run_cams` intercetta `Exception` (`:210`), non `SystemExit`:
alle 07 termina senza esiti componenti persistiti e senza raggiungere UV.
Il job è correttamente rosso, ma l'indisponibilità preliminare non segue il
normale percorso di attesa/recovery. Non basta correggerlo per garantire una
pubblicazione mattutina: il budget interno è 480 s, non copre ore di attesa.

A mezzogiorno una sola acquisizione condivisa:
request hash `55c4ee9004fed4d210a14971daf1824b70a131694a8f3712993ddea9931c0780`,
remote ID `74955b2c-dd72-4f51-a519-30628d90789b`, `post_retries=0`.
Intent/submitted/download/decoded/prepared hanno identità coerenti.
I passaggi delle 12:03 e 12:06 riprendono lo stesso ID, non creano nuove richieste.
Alle 07 non esisteva un ID accettato da riprendere. I checkpoint sono indicizzati
per data/hash, non per finestra: al successivo slot dello stesso giorno il codice
riusa riferimento e artefatti validati; un giorno nuovo è una corsa nuova.
Le prove coprono riuso nello stesso job e test di ripresa; non una nuova
acquisizione di produzione avviata per questa diagnosi.

`_persist_cams_outcome` (`cloud_worker.py:178`) considera completo solo ogni
componente verified/disabled. `phase_completed` della fase acquisition può
significare uscita con pending: non è il completamento del dataset.
Ultimo tentativo verificato nel periodo dell'episodio: job del 10 alle 12,
fallito complessivamente per UV. Ultimo successo aria/pollini: medesimo job,
release del 10. Ultimo successo complessivo: riuso automatico del 9 alle 22.
Scheduler/immagine/autore già verificati: scheduler ENABLED, service account
`pilot-scheduler`, immagine `sha256:da7cfe7bdef04967ad5209ef6f1e9d5acb1ea5e75578b812e4b187c19126cda7`.

## 4. Cache, aggiornamento normale, forzato e risposte tardive

“Cache negativa” non è una cache separata del server: un bundle ICON valido
con supplemento CAMS unavailable può essere conservato dal runtime in memoria
e localStorage, prefisso `meteofriul:weather-v1:bundle:v4`, separato per
endpoint/catalogo/comune, con `verifiedAt`.
`readRecentlyVerifiedBundle` (`localWeatherV1Runtime.js:1115`) usa
`elapsed = verificationNow - verifiedAt`; se `elapsed >= verifyWindowMs`, il
record non soddisfa più la finestra, predefinita 600.000 ms (`:32`).
Le semplici letture non rinnovano verifiedAt. La scadenza non installa un timer:
rende possibile il prossimo tentativo. Validità ICON, ora del campione e
revoche possono far invalidare il bundle anche prima della finestra nominale.

Un supplemento unavailable può derivare da timeout di 4 s, trasporto/HTTP fallito,
assenza del dato, schema/hash/provenienza non validi, corsa scaduta/revocata.
Gli errori non vanno equiparati: in presenza di un supplemento precedente
ancora utilizzabile, il runtime può conservarlo; una violazione di integrità
non autorizza a ignorare i controlli. Un valore di polline zero non è assenza.

Percorsi esistenti:

- permanenza visibile: timer dell'app di 10 min (`App.jsx:673`), gate di 10 min (`:531`);
- focus, visibilitychange e online: normale richiesta, soggetta allo stesso
  gate (`:685`); in background non è promesso polling JavaScript;
- resume Android: sequenza Capacitor esistente (`:1711`); controllo posizione
  ogni 3 min non equivale a una richiesta meteo;
- le route rivalutano anche al cambio d'ora (`AppRoutes.jsx:177`, `:386`).

Il gate dell'app aggiorna il proprio timestamp prima di sapere che la richiesta è
servita dalla cache. Riproduzione: t0 avvio, t0 + 4 s verifica negativa; tick a 10 min
trova la cache ancora valida per 4 s e aggiorna il gate; evento online/focus a
10 min e 4 s è bloccato dal gate; tick a 20 min recupera. Questo non è un'attesa minima
universale, né prova presenza continua o gli stessi tempi sul telefono.

Refresh forzato: supera gate temporale/verify-window (non il blocco di una
richiesta dell'app già pendente), propaga force al trasporto, usa `cache:no-store`,
non usa If-None-Match o prefetch immutabile, ma mantiene schema/hash/freschezza,
revoche e timeout di 4 s. Normale: `cache:no-cache`, If-None-Match quando disponibile,
riusa solo oggetti immutabili autenticati. `verifyWindowMs:0` è un'opzione
diagnostica che supera solo la finestra runtime; non è stata configurata nell'app.

Cache intermedie effettive: reader `CachedReadOnlyStore` (`cloud_reader.py:20`)
30 s per latest, 3.600 s per oggetti immutabili; risposte CAMS
`Cache-Control: public, max-age=30, must-revalidate`, ETag, errori 404/503 no-store.
Il client normale richiede rivalidazione. I 304 precedenti al cambio puntatore
sono coerenti con la vecchia release, non prova di una cache HTTP ferma per ore.
Le durate lente sono misurate; cold start/verifiche storage/contesa del reader
sono possibili contributi, non profilati né attribuiti con certezza.

Difetto distinto riprodotto: due richieste per lo stesso comune/endpoint, A forzata
partita prima, B normale completata dopo con corsa più nuova. Quando A arriva,
`observeCamsFamily` rigetta correttamente `CAMS_FAMILY_REGRESSION`; il catch
(`localWeatherV1Runtime.js:1376`) esegue però `purgeScopedBundles` (`:757`)
per l'intero comune, cancellando anche B. Il test mantiene l'assertion fallita.
È il percorso whole-bundle `deferCams:false`, disponibile anche tramite
`localConditionsApi.js:122`; il test supplemento deferred usato dalla Home
non riproduce questa cancellazione. Non si attribuisce la race all'episodio.

## 5. UV resta un caso separato

Dataset `cams-global-atmospheric-composition-forecasts`, variabile
`uv_biologically_effective_dose`, corsa del 9 settembre alle 00 UTC,
72 istanti 0…71, 35 punti; copertura fino all'11 settembre alle 23 UTC /
12 settembre alle 01 CEST. Il client impone età della corsa ≤48 h
(`uvForecast.js:2–7`): fino all'11 settembre alle 00 UTC / 02 CEST,
indipendentemente dalla fine delle 72 ore. Il refresh di 15 min non estende tale validità.
Il 9 la recovery aveva verificato dati reali; il 10 alle 10:02:02.863 UTC /
12:02:02.863 CEST la nuova submission UV ha ricevuto HTTP 400. Il vecchio documento
resta disponibile e valido durante l'episodio; il motivo dettagliato del 400
non è provato dai log sanitizzati. Il 403 dell'anteprima 5174, corretto in
`cd3a4bf`, non è questo guasto e non riguardava l'origine Android.

## 6. Verifiche eseguite e limiti

Da `frontend`:

```powershell
npx vitest run --configLoader native --config cams.diagnostic.config.js
# 12 test: 11 superati, 1 fallito, 0 saltati. Exit 1, risultato diagnostico.

npm run test -- src/services/localWeatherV1Runtime.test.js src/services/localWeatherV1Adapter.test.js src/services/weatherV1Client.test.js src/services/capacitorAppResume.test.js src/domain/runtime/runtimeRefreshPolicy.test.js src/services/pilotWeatherPrefetch.test.js
# 271 superati, 0 falliti, 0 saltati, sei file una sola volta nella sessione finale.

npm run lint
# Exit 0: nessun errore o avviso.
```

Da `experiments/weather_autonomy`:

```powershell
py -3.13 -B -m unittest test_cams_request_plan test_retrieve_remote_cams test_cams_worker_recovery test_cams_readback
# Primo tentativo: 34 test superati + 1 errore di importazione del modulo worker. Exit 1.

py -3.13 -B -m unittest test_cams_request_plan test_retrieve_remote_cams test_cams_readback
# 34 superati, 0 falliti, 0 saltati.
```

Il primo tentativo includeva anche `test_cams_worker_recovery`: 34 test passarono,
ma il modulo worker non fu caricato per `ImportError: cannot import name 'storage'
from 'google.cloud'`. I suoi 7 test **non sono eseguiti** in questa diagnosi, non
contati come successi. Nessuna dipendenza è installata e nessun test è disabilitato.
Il secondo comando esegue esplicitamente i tre moduli disponibili; i 34 non
vanno sommati al primo tentativo. Neppure i 161 test preliminari del collaboratore
vanno sommati ai 271 finali: sono inclusi in essi.

Suite diagnostica, prove specifiche:

| Test / scenario | Esito |
|---|---|
| Letture a 1/5/quasi 10 min non rinnovano verifiedAt; normale a 10 min recupera | PASS |
| Scadenza senza chiamata non avvia rete | PASS |
| Risposta di 5,65 s contro budget di 4 s, risposta tardiva ignorata, successivo recupero | PASS |
| Tick a 10 min prima della scadenza, gate online/focus, recupero al tick di 20 min | PASS |
| Force e bypass verify-window, distinti | 2 PASS |
| Errore rete totale conserva dati utilizzabili e non rinnova verifica | PASS |
| Errore solo CAMS conserva supplemento utilizzabile | PASS |
| Vecchia risposta whole-bundle non deve cancellare B | **FAIL: cache B diventa null** |
| Errore deferred tardivo non sovrascrive B | PASS |
| Assenza distinta da sei zeri pollinici reali nella fixture | PASS |
| Resume Capacitor riporta a richiesta normale dopo gate | PASS |

Queste prove usano adapter/runtime/gate/resume reali, orologio controllato e
provider sintetico pollini; non montano App.jsx, non sono test end-to-end sul
telefono e non sostituiscono la verifica HTTP atomica completa. I 271 esistenti
includono il validatore HTTP/contratto, adapter e guardie. Nessun test live opt-in
è stato abilitato; nessun Java/Gradle/Android test o build eseguito.

Controlli live READ-ONLY effettuati separatamente: Cloud Logging (job del 10 e
richieste reader Android del 10), GCS GET/list di piani, checkpoint, registro,
manifest, metadata e due payload Pordenone già pubblicati; lettura documentazione
ufficiale pubblica; inventario ADB senza dispositivo. Nessuna richiesta di
acquisizione al fornitore. Riutilizzata la precedente verifica delle 15:29 CEST:
430 payload storage (215+215), HTTP campione 093033 e UV intero con hash coerenti;
non presentata come una seconda validazione integrale eseguita in questa fase.

## 7. Proposte minime, non implementate

1. **Scadenza di 30 h:** formalizzare una policy CAMS specifica che concili età
   massima scientificamente accettata, valid-time reale e finestre documentate;
   poi allineare produttore, validatore e runtime. Mantenere distinzione di corsa
   precedente e nessun riuso di ore passate. Non scegliere 48/96 h arbitrariamente:
   cambiare solo il manifest produrrebbe FRESHNESS_MISMATCH.
2. **Errore delle 07:** non usare il main CLI dentro il worker; mantenere
   l'eccezione tipizzata e classificarla pending/retryable entro il budget già
   previsto, persistendo l'esito e lasciando proseguire UV. Nessun nuovo scheduler.
   Questo migliora gestione/esiti, non rende disponibili dati che non ci sono.
3. **Orari fuorvianti:** distinguere intento immutabile da timestamp di commit
   del puntatore e da verified-at nei resoconti/log; non riscrivere le release.
4. **Timeout/recovery:** separare l'attesa del primo rendering dalla conclusione
   del supplemento CAMS già deferred; dimensionare il limite complessivo su
   misure mobile comprensive di preflight, evitando l'abort a 4 s di risposte
   valide più lente. Non cambiare Cloud Run o introdurre background/push.
5. **Doppia attesa:** non registrare unavailable come verifica riuscita da
   bloccare per 10 min; coordinare il gate dell'app con l'ultima vera verifica CAMS,
   così la normale occasione già esistente può riprovare il componente fallito
   senza rifare i componenti validi. Mantenere deduplicazione e nessun tight loop.
6. **Race distinta:** rendere invalidazione/commit condizionati alla generazione
   della richiesta; il rifiuto di A non deve eliminare B. Non indebolire controlli
   di revoca o integrità. Usare il test rosso come gate per l'eventuale correzione.

Queste proposte richiedono un successivo mandato: in questa fase non è applicata
nessuna modifica funzionale o operativa. Il difetto riprodotto non è dichiarato risolto.
