# Pilota Samsung: refresh mattutino dell'11 settembre 2026

## Esito e perimetro

**È dimostrato e corretto un difetto di selezione della cache che impediva il
recupero di aria/pollini anche dopo download e validazione riusciti. Non era la
soglia delle 30 ore.** La riproduzione usa gli oggetti nativi conservati e un
record della cache del telefono con timestamp **05:24:42 CEST**, dentro la
finestra confermata dall'utente. Il ramo preciso che mostrò «fallito» non è
identificabile dai log storici disponibili: quel messaggio aggrega anche esiti
diversi da CAMS.

La prima fase ha conservato le evidenze senza modificare la cache del telefono.
L'implementazione successiva è nei commit **`8353705`** (CAMS) e **`e885143`**
(UV). Non cambia soglie, scheduler, frequenze, backend, beta o servizi cloud;
non sono state avviate acquisizioni ADS, pubblicazioni o deploy.

## 1. Build installata ed evidenze conservate

- Samsung A52 `SM-A525F`, Android 14, package `com.meteofriul.app.localpilot`.
  `lastUpdateTime=2026-09-10 16:55:57`, versione `1.0.1-local-pilot`, code `300012`.
- SHA256 della `base.apk` installata:
  `9a1dfb212343e412ff7b6df5477c51913d91fb7877d4d1c8be9aa487b5b13b57`.
  Coincide con l'APK archiviata e con il verbale del 10 settembre: sorgenti
  **`c54cdb9`**. `HEAD=25d2762` differisce solo per il verbale di installazione.
  Non è quindi una segnalazione riferita alla vecchia build.
- Alle **07:36 CEST** conservati dump package, logcat limitato all'UID della
  pilota e copia di cache nativa/Local Storage WebView. Nessuna apertura forzata,
  refresh, arresto o cancellazione dell'app durante la raccolta.
- Il logcat conservato parte dalle **07:16**: non contiene il gesto delle 05:22.
  Tentativo di lettura WebView non riuscito; inoltro ADB temporaneo rimosso.
- I blocchi dati e indice SST letti dalla copia LevelDB hanno CRC32C verificato;
  record decompressi e JSON decodificati. La copia è stata presa ad app avviata:
  **non è atomica**, né è stata ricostruita l'intera vista logica tramite manifest
  e tombstone. Un record integro non dimostra da solo tutta la schermata storica.

Evidenze private, escluse da Git, in
`.dev-logs/cams-episode-20260911-0500/`. Non pubblicare coordinate, identificativi
personali o l'intera cache. `capture-index.json` conserva hash e orari iniziali.
Riferimenti principali:

| Evidenza | SHA256 |
|---|---|
| `pilot-cache-snapshot.tar` | `b252dfe5b5e6ec8a8361b0b16a22df1aaacf99ab5b3490c9b253b3ac3e582070` |
| `pilot-logcat.txt` | `45966830ac7d85a3bc6a27fa670671fc4c839b8463ef65e179dbe58eade072d0` |
| `pilot-requests-0100-0530.json` | `afa0a43c3c00b9da79a9cc6df5e5c9138ca02ae59032ce53ab335257e1dd41ef` |

## 2. Richieste della finestra confermata

Letture limitate a **`meteofriul-pilot-20260906`**, regione `europe-west1`, reader
`pilot-weather`. Nessun uso del progetto predefinito. Ore italiane: UTC+02:00.

Tra **04:40 e 05:20 CEST** il reader non registra richieste. L'utente ha confermato
compatibile la successiva finestra **05:22–05:24**. In questa finestra:

- **102 richieste HTTP: 98 risposte 200, 2 OPTIONS 204, 2 risposte 304**;
  nessun 4xx/5xx. Comune richiesto esclusivamente **Pordenone, ISTAT 093033**.
- User-agent WebView Android 14/SM-A525F e Dalvik. Sono coerenti con il Samsung;
  i log non contengono seriale, package o token del gesto, quindi non identificano
  univocamente il telefono o ciascun refresh manuale.
- La località manuale conservata sul telefono è anch'essa Pordenone/093033.

| Passaggio osservato | Europe/Rome | Durata / significato |
|---|---|---|
| Primo GET ICON nativo | 05:22:21.248 | 200, 9,809 s; avvio reader osservato nello stesso intervallo |
| OPTIONS CAMS WebView | 05:22:21.438 | 204, 1,183 s |
| GET puntatore CAMS WebView | 05:22:24.746 | 304, 6,661 s; fine alle 05:22:31.407 |
| Catena nativa release/manifests/payload | 05:22:32.541–05:22:33.187 | Risposte 200 |
| Catena WebView completa CAMS/ICON | 05:22:44.935–05:22:45.539 | Risposte 200 |
| Ultima catena osservata nell'episodio | 05:24:40–05:24:41.677 | Risposte 200 |
| Record cache `3899`, `verifiedAt` | **05:24:42.439** | CAMS ancora unavailable, `adapt / EXPIRED` |

Ci sono altre catene riuscite fra quelle indicate. Non è possibile attribuirle
una per una a gesti, avvio nativo o trigger automatici. I tempi sono quelli
registrati dal server, non una misura completa del percorso sul telefono.
Tra inizio OPTIONS e fine primo GET CAMS passano circa **9,97 s**: compatibile
con il superamento del feedback generale da 8 s, ma non prova dell'istante del
gesto né di un timeout CAMS da 20 s.

## 3. Release, validità, campione e UV

Famiglia CAMS: revisione **5**, release **`20260910T000000Z`**, nessuna revoca
(`disabled_run_ids=[]`). SHA release:
`4a063cf415664a60538519f58b5610d1ae04a6392d3636aa0cf0e9bc6d5124ce`.
Puntatore GCS: generation `1789035002435738`, aggiornato il 10 settembre alle
**12:10:02 CEST**, ancora quella generazione alla lettura dell'11 settembre.

Distinzione mantenuta: **12:01:11 del 10 settembre è il timestamp d'intento**,
non la pubblicazione. Cambio puntatore **12:10:02.461**, verifica conclusiva
**12:10:37.202 CEST**, come già documentato nella diagnosi del 10 settembre.

Per entrambi i payload aria/pollini conservati:

| Campo | UTC | Europe/Rome |
|---|---|---|
| `run_at` | 10/09 00:00 | 10/09 02:00 |
| `fresh_until` | 11/09 00:00 | 11/09 02:00 |
| `usable_until` | 11/09 06:00 | 11/09 08:00 |
| Campione pertinente alle 05:22 | **11/09 03:00** | **11/09 05:00** |
| Copertura del payload | 10/09 00:00–14/09 00:00 | Non coincide con l'usabilità ammessa |

Età corsa circa **27 h 22 min**: `stale`, ma **utilizzabile**. I due campioni delle
03 UTC esistono. Il replay dei byte reali passa schema, hash, manifest, famiglia,
provenienza e freschezza; con cache vuota arriva correttamente al runtime.
Anche metadati e view model non trasformano il superamento delle 24 h in assenza.

UV: l'oggetto pubblico era già della corsa **10 settembre 00 UTC**, non del 9.
Generation `1789052603108352`, aggiornamento **10 settembre 17:03:23 CEST**;
SHA256 `c732d7344140d93fb81fd326bb78597937bc144e8e13aec1048fd835da640c48`.
GET UV 200 alle **05:22:26.874**, durata 0,123 s. La scadenza alle 02:00 di un
eventuale vecchio documento locale del 9 non spiega quindi l'indisponibilità
del documento servito, né quella di aria/pollini. Non è provato quale UV fosse
visibile prima di quel GET. Runtime e cache UV sono indipendenti da CAMS.

## 4. Causa riprodotta sullo stato conservato

Il record `3899` contiene ICON run 10/09 12 UTC, campione 11/09 03 UTC,
tramonto **19:29**, `location_scope=device_location`, aria nulla e pollini
indisponibili. `camsVerifiedAt=05:24:42.438 CEST`, un millisecondo prima di
`verifiedAt`: una verifica CAMS risulta registrata, ma i dati selezionati mancano.

La catena dimostrata:

1. L'adapter usa coordinate del dispositivo solo con precisione e timestamp GPS
   validi; altrimenti usa il punto comunale autorevole. La località conservata è
   manuale e non ha quei metadati.
2. Il riallineamento orario della cache usa invece qualsiasi `location.lat/lon`
   e le qualifica come posizione del dispositivo. Sugli input reali cambia il
   tramonto da **19:30 a 19:29**.
3. Il vecchio campione CAMS viene correttamente tolto quando ha almeno 60 minuti:
   `withoutExpiredCams` produce `adapt / EXPIRED`. Qui scade il **campione**, non
   la corsa delle 27 ore.
4. Il candidato appena scaricato contiene CAMS valido delle 03 UTC, ma l'adapter
   ricalcola **19:30**. `preferBundle` confronta i campi visualizzati ICON,
   inclusi alba/tramonto, prima del miglioramento CAMS: il confronto diverso
   fa mantenere il vecchio bundle degradato.
5. `selectVerifiedBundle` aggiorna `camsVerifiedAt` sulla validità dell'incoming,
   pur persistendo il selected indisponibile. Il replay riproduce anche questa
   discordanza presente nel record telefonico.

Due test falliscono partendo dal record reale, verificato come effettivamente
caricato con chiave ISTAT corretta. Un terzo riproduce l'origine da cache vuota:
alle **02:22:44 UTC** CAMS disponibile/campione 02, poi alle **03:22:44 UTC**
refresh forzato, campione 03 valido ricevuto ma risultato ancora indisponibile.
Questa sequenza è una riproduzione controllata, non un gesto storico registrato.

**Controfattuale superato:** nel solo clone di test del record `3899`, cambiare
esclusivamente `current.sunset` da 19:29 a 19:30 permette la selezione del
candidato con aria/pollini disponibili. Nessuna modifica di finestre orarie,
hash, CAMS o provenienza; ripristinando quel campo il clone coincide integralmente
con l'originale, verificato con SHA256. Il minuto di differenza solare è quindi
sufficiente a impedire il recupero, non una semplice correlazione.

Riferimenti ai sorgenti invariati:

- [Adapter: scelta coordinate](<C:/Users/LOCAL_USER/.codex/worktrees/fb42/meteo friul - ui 3.0.0/frontend/src/services/localWeatherV1Adapter.js:146>).
- [Runtime: riallineamento cache](<C:/Users/LOCAL_USER/.codex/worktrees/fb42/meteo friul - ui 3.0.0/frontend/src/services/localWeatherV1Runtime.js:297>), rimozione campione alle righe 354–363.
- [Confronto che rifiuta il candidato](<C:/Users/LOCAL_USER/.codex/worktrees/fb42/meteo friul - ui 3.0.0/frontend/src/services/localWeatherV1Runtime.js:536>), fingerprint alla riga 422.
- [Timestamp verifica e bundle selezionato](<C:/Users/LOCAL_USER/.codex/worktrees/fb42/meteo friul - ui 3.0.0/frontend/src/services/localWeatherV1Runtime.js:1178>).

## 5. «Fallito», budget e problema distinto al cambio d'ora

Il percorso installato del gesto usa `force:true`, `source:pull`. Il supplemento
CAMS ha **20.000 ms complessivi**, comprese richieste preliminari e catena
famiglia/release/manifests/payload, non 20 secondi per richiesta. ICON procede
separatamente. Nessuna prova di `CAMS_TIMEOUT` nell'episodio conservato.

Il feedback generale ha invece **8.000 ms**. `timeout` e gesto sovrapposto
`skipped` diventano «fallito», senza necessariamente interrompere CAMS. Inoltre
le route Home/Meteo chiudono il proprio esito sull'iniziale ICON, non sul
supplemento deferred; il gate generale richiede anche allerte ufficiali fresche
e autorevoli. Può quindi fallire con CAMS riuscito, o terminare prima di CAMS.
UV ha una sottoscrizione separata, non cancella il bundle aria/pollini.

Riferimenti: `AppShell.jsx:171`; [App, gesto e timeout](<C:/Users/LOCAL_USER/.codex/worktrees/fb42/meteo friul - ui 3.0.0/frontend/src/app/App.jsx:533>);
[policy feedback/gate](<C:/Users/LOCAL_USER/.codex/worktrees/fb42/meteo friul - ui 3.0.0/frontend/src/domain/runtime/runtimeRefreshPolicy.js:24>);
`pullRefreshPolicy.js:129`, `AppRoutes.jsx:257` e `:423`;
[budget CAMS](<C:/Users/LOCAL_USER/.codex/worktrees/fb42/meteo friul - ui 3.0.0/frontend/src/services/localWeatherV1Adapter.js:797>);
`WeatherUvCard.jsx:94`, `uvForecastRuntime.js:50`.

I test dell'App montata riproducono: feedback timeout a 8 s con CAMS riuscito a
12 s; vero abort CAMS a 20 s e rifiuto del completamento tardivo; fallimento delle
allerte indipendente; deduplicazione del gesto sovrapposto; UV scaduto indipendente.
**Manca il token/console storico per scegliere quale ramo produsse la scritta
del gesto segnalato.** Non dedurre durata del fallimento dal timestamp EXPIRED:
quel diagnostico può essere conservato da un tentativo precedente.

Era inoltre presente un difetto separato al cambio d'ora: con ICON completato
alle **02:59:59 UTC** e CAMS alle **03:00:04**, veniva scelto il campione 02 UTC.
Non spiegava le richieste delle 03:22, ma è stato corretto facendo valutare CAMS
con l'orologio del proprio completamento. I test deferred e whole-bundle ora
selezionano entrambi il campione 03 UTC.

## 6. Correzione applicata

### CAMS aria/pollini (`8353705`)

1. Adapter e runtime usano la stessa regola per il punto di presentazione:
   coordinate del dispositivo soltanto con precisione e timestamp GPS validi,
   altrimenti punto comunale autorevole. Alba e tramonto sono calcolati sul punto
   reale selezionato; nessun orario viene alterato per superare i confronti.
2. Il bundle attivo resta separato dal candidato. Il candidato viene scritto in
   una chiave di staging, riletto esattamente, promosso con una singola scrittura
   atomica e rimosso solo dopo il readback dell'attivo. Un'interruzione lascia
   quindi il vecchio attivo oppure il nuovo record completo.
3. Ogni cache è vincolata all'identità ISTAT della località. Il cambio comune non
   riusa dati dell'altro comune, ma le rispettive cache restano disponibili.
4. Il bundle conserva una serie oraria CAMS compatta, con schema e SHA256. Al
   cambio d'ora il runtime seleziona offline il campione reale pertinente; se non
   esiste, mantiene l'ultimo campione verificato e lo marca `last_known` con il
   proprio timestamp, senza presentarlo come attuale.
5. Le 24 ore restano la soglia di freschezza e le 30 ore la soglia per adottare
   un nuovo candidato. Un attivo già verificato non viene cancellato allo scadere:
   resta ultimo dato noto. Un primo candidato oltre 30 ore non viene invece
   promosso come dato CAMS disponibile.
6. ICON e CAMS vengono selezionati e persistiti per componente. Timeout, rete,
   pacchetto incompleto o errore di salvataggio del nuovo CAMS non cancellano
   quello attivo; un nuovo ICON valido non attende CAMS.
7. Una revoca CAMS sanitizza atomicamente attivo, candidato e memoria: rimuove
   solo aria/pollini e conserva ICON. Integrità, provenienza, famiglia, revoche e
   controlli di catalogo/località restano fail-closed.

### UV (`e885143`)

1. Anche UV usa attivo e candidato con staging, readback e promozione atomica.
2. Un nuovo documento deve essere strutturalmente valido e dentro la finestra
   ammessa per diventare attivo. Un documento locale già verificato resta invece
   conservato se il nuovo download fallisce.
3. Dopo la copertura oraria viene mostrato soltanto l'ultimo campione realmente
   presente, con riferimento temporale e stato non attuale; nessun valore viene
   ricostruito. Giorno/notte riguarda solo la presentazione e non cancella cache,
   non blocca download e non modifica alba o tramonto.
4. La cache UV è indipendente dal bundle aria/pollini.

## 7. Verifiche finali

Comandi principali eseguiti dalla cartella `frontend`, sempre con configurazione
Vite/Vitest caricata nativamente:

```powershell
npx vitest --configLoader native run src/services/localWeatherV1Runtime.test.js src/services/localWeatherV1Runtime.generation.test.js
npx vitest --configLoader native run src/services/localWeatherV1Adapter.test.js
npx vitest --configLoader native --config cams.diagnostic.config.js
npx vitest --configLoader native --config cams.hour-boundary.diagnostic.config.js
npx vitest --configLoader native run src/app/App.manualRefreshEpisode.test.jsx src/app/AppRoutes.camsEpisode.test.jsx src/app/AppRoutes.activeCandidate.test.jsx src/features/weather/uvForecast.test.js src/features/weather/uvForecastRuntime.test.js src/features/weather/WeatherUvCard.test.jsx src/features/weather/weatherForecastViewModel.test.js src/features/weather/WeatherCamsCard.test.jsx
npm test
npm run lint
npm run build
```

| Sessione finale | Superati | Falliti | Saltati | Esito |
|---|---:|---:|---:|---|
| Runtime CAMS + generazioni concorrenti | 92 | 0 | 0 | Pass |
| Adapter locale | 31 | 0 | 0 | Pass |
| Recovery CAMS esplicito | 13 | 0 | 0 | Pass |
| Confini 24/30 h e cambio d'ora | 10 | 0 | 0 | Pass |
| App/route + UV + presentazione CAMS | 75 | 0 | 0 | Pass |
| Replay privato dei byte/cache conservati | 8 | 0 | 0 | Pass; test locale non versionato perché dipende da evidenze private |
| Suite generale finale | 3471 | **1** | **11** | Un solo guasto preesistente estraneo; tutti gli skip sono live opt-in |

La prima esecuzione generale, prima di adeguare due test double di Web Storage
al readback atomico, aveva 3469 superati e 3 falliti. Rieseguita sullo stato
finale: i due test meteo passano; resta soltanto
`EventsView.test.jsx > shows available descriptions in the list without fetching a detail`,
che pretende un excerpt non renderizzato già in `HEAD` e non è stato modificato
in questo intervento.

I **11 test saltati** appartengono esclusivamente alle quattro suite live opt-in:
3 contratto pilota completo, 5 fallback ICON, 2 aria locale e 1 benchmark tempi.
Nessuno è stato eseguito né contato come prova. Le suite finali verdi usano clock,
latenze e rete controllati; nessun test sintetico equivale a una verifica sul
telefono. Il replay usa soltanto gli artefatti già conservati, senza traffico.

Lint generale: pass. Build frontend di produzione: pass. Avvisi non modificati:

- `[INEFFECTIVE_DYNAMIC_IMPORT] src/features/almanac/AlmanacView.jsx is dynamically imported by src/app/AppRoutes.jsx but also statically imported by src/features/weather/WeatherSkyCard.jsx, dynamic import will not move module into another chunk.`
- `Some chunks are larger than 500 kB after minification`; il chunk principale
  misurato è 3.661,22 kB (831,11 kB gzip).
- `[PLUGIN_TIMINGS]` segnala tempo prevalente in `vite:asset` (81%), seguito da
  `rolldown:vite-resolve` (5%) e `vite:css` (5%).

Non sono stati disattivati controlli, alzate soglie, modificati import o bundle
per nascondere gli avvisi.

Le letture live dell'episodio restano quelle già conservate: ADB diagnostico e
Cloud Logging/Storage del solo progetto `meteofriul-pilot-20260906`. Nessuna
acquisizione ADS, suite live provider, modifica cloud o deploy è stata eseguita.
L'installazione della nuova APK pilota e la verifica sul Samsung sono registrate
nella sezione successiva.

## 8. Installazione pilota

Build protetta eseguita con:

```powershell
.\scripts\build-android-local-weather-pilot.ps1 -ApiBase 'https://cfweb-bcee09e---meteofriul-api-bx24xqvcda-ew.a.run.app/api' -WeatherCloud
```

Esito: `BUILD SUCCESSFUL`; package verificato
`com.meteofriul.app.localpilot`, API ufficiale taggata corretta, reader meteo
`https://pilot-weather-335641913741.europe-west1.run.app`, nessun orologio di
test e `Published=False`. Il controllo launcher ha confrontato 82.944 pixel e
11 asset della sola pilota con il riferimento approvato. APK:

`frontend/android/app/build/outputs/apk/localPilot/app-localPilot.apk`

SHA256: `a70ce8d69305f8a43f966e5849942fa163375d0bf9f60dd9c9baffb473b63acc`.

**Non installata al momento di questo verbale:** `adb devices -l` non elencava
il Samsung `OWNER_DEVICE_SERIAL`, anche dopo l'avvio del server ADB. La beta non è stata
toccata. I commit nei sorgenti e l'APK pronta non sono quindi presentati come
aggiornamento effettivamente installato o come verifica del difetto sul telefono.
L'installazione dovrà usare `adb install -r`, senza cancellare dati/cache, quando
il dispositivo sarà nuovamente collegato e autorizzato.

## 9. Rettifica del 12 settembre: installazione e prova sul Samsung

Questa sezione supera esclusivamente lo stato operativo «non installata» della
sezione 8. Non modifica la ricostruzione storica dell'episodio dell'11 settembre.

### Correzione residua

La riproduzione con l'ordine reale dei `capability_gaps` ha rivelato altri due
motivi per cui il fallback compatto poteva fermarsi prima dello staging:

1. con la stessa identità ICON, il supplemento CAMS conservava la vista ICON
   scorrevole della richiesta invece di usare, quando diversa, la vista
   ricostruibile dal record attivo persistito;
2. target e ricostruzione venivano preparati in istanti distinti di `Date.now`,
   rendendo diversi `run_age_hours` e `coverage_hours` nel confronto canonico.

Il commit `1fe35fc` congela un solo istante per l'intera transazione delta e usa
il record durevole come base quando la vista ICON differisce. Restano invariati
identità del Comune, hash, provenienza, famiglia CAMS, revoche e confronto
canonico. Il supplemento conserva il timestamp di verifica ICON dell'attivo:
verifica CAMS, non rinnova implicitamente ICON.

Il commit di soli test `7ce8384` rende esplicito un confine già previsto dal
runtime: all'istante esatto dei dieci minuti ICON viene riverificato una volta;
focus, ritorno rete e `visibilitychange` coincidenti restano deduplicati. Non è
stata cambiata alcuna frequenza o logica di aggiornamento.

### Verifiche automatiche sullo stato finale

Da `frontend`:

```powershell
npx vitest --configLoader native run src/services/localWeatherV1Runtime.test.js src/services/localWeatherV1Runtime.generation.test.js
npx vitest --configLoader native --config cams.diagnostic.config.js
npx vitest --configLoader native --config cams.hour-boundary.diagnostic.config.js
npx vitest --configLoader native run src/services/camsHourlyCache.test.js src/services/localWeatherV1Adapter.test.js src/services/localWeatherV1Runtime.test.js src/services/localWeatherV1Runtime.generation.test.js src/services/localWeatherV1Runtime.camsRecovery.test.js src/services/weatherV1Client.test.js src/services/weatherApi.test.js src/services/localWeatherPilotHome.test.js src/services/capacitorAppResume.test.js src/services/pilotWeatherPrefetch.test.js src/domain/runtime/runtimeRefreshPolicy.test.js src/features/home/homeDataController.test.js src/app/App.camsRecovery.test.jsx src/app/App.manualRefreshEpisode.test.jsx src/app/AppRoutes.test.jsx src/app/AppRoutes.weatherSwipe.test.jsx src/app/AppRoutes.camsEpisode.test.jsx src/app/AppRoutes.activeCandidate.test.jsx src/app/App.officialAlertWiring.test.jsx src/features/weather/WeatherUvCard.test.jsx src/features/weather/uvForecast.test.js src/features/weather/uvForecastRuntime.test.js src/features/weather/weatherForecastViewModel.test.js src/features/weather/WeatherCamsCard.test.jsx
npm run lint
npm run build
```

| Sessione | Superati | Falliti | Saltati |
|---|---:|---:|---:|
| Runtime + generazioni | 108 | 0 | 0 |
| Diagnostica recovery CAMS | 13 | 0 | 0 |
| Confini temporali/cambio d'ora | 10 | 0 | 0 |
| Unione di 24 file app/runtime/CAMS/UV | 469 | 0 | 0 |

Lint e build di produzione: pass. La build conserva gli avvisi non bloccanti
preesistenti: import dinamico inefficace di `AlmanacView`, chunk principale oltre
500 kB e riepilogo `PLUGIN_TIMINGS`. Nessuna regola o soglia è stata modificata.
Le suite live opt-in dei provider non sono state abilitate; la prova ADB descritta
sotto è una verifica reale separata, non un test sintetico.

### APK installata senza cancellazione

Build protetta:

```powershell
.\scripts\build-android-local-weather-pilot.ps1 -ApiBase 'https://cfweb-bcee09e---meteofriul-api-bx24xqvcda-ew.a.run.app/api' -WeatherCloud
```

Esito `BUILD SUCCESSFUL`, `ApplicationId=com.meteofriul.app.localpilot`,
`Published=False`; controllo launcher-r3 superato su 19 asset della sola pilota.
APK SHA256:
`6518d91d9606a5a290927a2337e6951aaacc8ede75e993a24e625bfbb6b6e186`.

Installazione con `adb install -r`: `Success`. L'hash di `base.apk` letto dal
Samsung coincide con quello sopra. Identità installata:

- dispositivo `OWNER_DEVICE_SERIAL`, modello `SM_A525F`;
- versione `1.0.1-local-pilot`, versionCode `300012`;
- `lastUpdateTime=2026-09-12 18:16:18`;
- `firstInstallTime=2026-09-04 11:11:31`, quindi dati applicativi conservati.

I quattro hash registrati prima e dopo l'installazione sono identici:

- prefetch ICON: `7cb565c92a62f952d7954b4b3bb85bcfb9048815a47a8131d3c9e81f9450823c`;
- prefetch CAMS: `ba0733f9f03e4bd7b1522d84b4001a1e9fea249179bd0f3056770aed0656a31a`;
- preferenze prefetch: `f708db81dce41beb9bc5a596be0571f86a2b3bf9bcfa2b0187389ab63a088959`;
- preferenze Capacitor: `95622e8f8bdd6d1de6161184b706b5acddb687c490ce1aa42ecc21543696f022`.

La beta `com.meteofriul.app` è rimasta `1.0.1`/`300012`, con
`lastUpdateTime=2026-08-30 00:41:28`.

### Prova reale attivo + candidato

Prima della prova, l'attivo WebView di Pordenone (`istat:093033`) era lungo
81.517 caratteri, SHA256
`216c4fa6dae0771b46dc2a5526caffafbec6a39f4ef94cd06c68ad5856efeef9`,
con ICON e CAMS della corsa `2026-09-12T00:00:00Z`, campione CAMS delle 11:00,
cache v2 da 97 campioni e nessun candidato.

Con rete disattivata:

- la riapertura ha conservato lo stesso hash e la stessa località;
- le tre card UV, aria e pollini erano tutte presenti, nessuna vuota;
- dalla serie già salvata è stato selezionato il campione pertinente delle 18:00
  locali, senza download e senza congelare il valore delle 11:00;
- un pull-to-refresh reale è passato da `refreshing` a `failed` in circa 1,27 s,
  mantenendo sempre 3 card e 0 card vuote; attivo invariato e candidato assente.

Con rete ripristinata, il pull-to-refresh ha ricevuto HTTP 200 per tutte le
richieste ICON, CAMS e avvisi osservate. Due candidati completi (81.241 e 77.277
caratteri) hanno ricevuto `QuotaExceededError`; il runtime ha quindi salvato e
verificato un candidato `cams-delta` da 22.719 caratteri e promosso un nuovo
attivo da 81.532 caratteri. Durante l'intera sequenza: minimo 3 card, massimo 0
card vuote.

Nuovo attivo:

- SHA256 `f2574d9a460d16334dd2261ef40a849105656ee2867aad9a389cc059fd83499b`;
- ICON invariato: corsa 00 UTC, campione persistito 11 UTC;
- CAMS aggiornato atomicamente al campione 16 UTC (18:00 locali);
- cache v2/97 e relativo SHA immutabile invariati;
- nessun candidato residuo.

Una successiva chiusura e riapertura senza rete ha ritrovato esattamente il nuovo
hash, CAMS 16 UTC, 3 card presenti e nessun candidato: mai uno stato vuoto o
parziale. Wi-Fi e dati mobili sono stati infine ripristinati allo stato iniziale.

### Punto ancora aperto: feedback generale

Il feedback generale **non è corretto** da questi commit. Nella prova online,
nonostante la promozione CAMS riuscita e tutte le risposte HTTP osservate a 200,
il pull-to-refresh ha mostrato `Fallito` dopo circa 2,42 s. È quindi un esito
dell'aggregazione generale separato dalla persistenza CAMS; questa prova non ne
stabilisce ancora il componente responsabile. Non è stato modificato durante la
correzione attivo + candidato.

Nessun deploy, modifica cloud, scheduler, frequenza, Firebase o acquisizione ADS
è stato eseguito.
