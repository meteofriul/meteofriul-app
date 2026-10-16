# Meteo autonomo nell'app locale — 3 settembre 2026

Questa guida avvia una preview locale e reversibile dell'app con ICON-2I e CAMS sul contratto `weather/v1`. Il launcher non costruisce Web o Android; una sezione separata permette di generare un APK locale affiancato. Nessuno dei due percorsi modifica servizi cloud o distribuisce aggiornamenti.

## Aggiornamento verificato — 5 settembre 2026

Il launcher accetta ora percorsi espliciti per i quattro artefatti e per un database
nuovo. Non cerca automaticamente il file “più recente”: run, dimensioni, SHA-256,
catalogo, 215 Comuni e timeline vengono ricavati e verificati dai file selezionati.

La preview attualmente provata usa:

- ICON-2I `20260904T000000Z`, 215 Comuni, 73 istanti, fresh fino alle
  `18:00Z` e utilizzabile dal client fino al 5 settembre alle `00:00Z`;
- CAMS `20260904T000000Z`, 215 Comuni, 90 celle, 28 variabili e 97 istanti,
  fresh fino al 5 settembre alle `00:00Z` e utilizzabile fino alle `06:00Z`;
- database separato del pilot atomico
  `.dev-logs/weather-v1/weather-v1-objects-20260905-v6-readonly-split.sqlite3`.

Il primo gate anonimo CAMS del 4 settembre ha rilevato solo 73/97 lead (`0..72`) e
si è fermato prima di credenziali e `POST`. Il controllo successivo ha trovato la
matrice completa e ha prodotto il piano verificato con SHA-256
`51009a1a32d12afd1888641be26bfb9ef2203095bd959d629ae839ef082cb0fa` e la
richiesta con SHA-256
`3512829bf323f8518477394cf25706b1da32cd2dbe801c1e4207f2cac08f0143`.
Acquisizione e decodifica del nuovo snapshot sono riuscite; tempi, dimensioni e
hash sono registrati in `CAMS_FRESH_SNAPSHOT_RUNBOOK.md`.

Comando locale verificato:

```powershell
scripts\start-local-weather-pilot.ps1 `
  -IconPayload '.dev-logs\weather-v1\icon_payload_precipitation_semantics_v3_20260904.json' `
  -IconReport '.dev-logs\weather-v1\icon_report_precipitation_semantics_v3_20260904.json' `
  -CamsPayload '.dev-logs\weather-v1\cams_fvg_authoritative_20260904.json' `
  -CamsReport '.dev-logs\weather-v1\cams_fvg_authoritative_report_20260904.json' `
  -ObjectDatabase '.dev-logs\weather-v1\weather-v1-objects-20260905-v6-readonly-split.sqlite3' `
  -WeatherTestNow '2026-09-04T21:00:00Z'
```

Verifica live: Pordenone più tutti i 215 oggetti ICON attraverso
latest → manifest → payload, 73 ore e 36 aggregati bi-orari, superata. Sono stati
inoltre riletti via HTTP tutti i 215 payload CAMS completi (28 variabili × 97 ore)
e tutti i 215 payload della proiezione pollini (6 variabili × 97 ore): 645/645
oggetti hanno rispettato gli hash del manifest e sono risultati identici attraverso
il proxy Vite. Pordenone espone 72/73 intervalli di precipitazione; il solo primo
è nullo perché non ha un'ora precedente. Il run CAMS
del 4 settembre rientra nella finestra di freschezza dichiarata e non viene
presentato come osservazione di stazione. Anche suite Web completa (395 file e
2.855 test superati, 1 file e 3 test saltati), lint, build e service worker sono
verdi; la suite backend passa 854/854 test. La suite offline completa del
laboratorio autonomo passa 590/590 test, inclusi acquisizione, decodifica,
idempotenza, crash recovery, pubblicazione atomica e revoca del precedente
prototipo per provider, oltre al data plane HTTP. Questi conteggi storici non
sono attribuiti al successivo puntatore atomico di famiglia CAMS.
Open-Meteo risponde 503 nel solo pilot; bollettino OSMER e allerte mantengono le
rotte e le fonti esistenti. Nessun deploy è stato eseguito.

Una raffica diagnostica non rappresentativa da 12 richieste simultanee ha prodotto
un singolo `502` del proxy Vite su 215 oggetti; con concorrenza 3 sono passati
645/645. Il client normale legge un solo Comune e non usa quel profilo di raffica:
il dato resta annotato come limite del proxy di sviluppo, non del data plane.

## Architettura locale effettiva

- L'API ordinaria su `127.0.0.1:8002` continua a servire bollettino OSMER, allerte ufficiali ed eventuali funzioni non meteo. Il launcher le assegna due switch locali fail-closed: identifica esplicitamente il pilot e disabilita Open-Meteo. OSMER e allerte non cambiano fonte, dati o cadenza.
- Prima di avviare servizi, il writer monouso verifica i quattro artefatti sorgente, materializza le tre collezioni `icon2i`, `cams_europe` e `cams_europe_pollen` per tutti i 215 Comuni nel database SQLite locale selezionato e chiude store e capacita di scrittura. Non apre socket.
- Solo dopo l'esito canonico `ready` del writer, il data plane su `127.0.0.1:8781` apre lo stesso database con l'adapter SQLite sola-lettura. Il processo HTTP possiede esclusivamente `head/get` e non riceve payload, report o porte di pubblicazione. Il database predefinito del pilot e `.dev-logs/weather-v1/weather-v1-objects-20260905-v6-readonly-split.sqlite3`.
- ICON espone il proprio `latest.json`. CAMS core e pollini hanno payload e manifest immutabili separati, ma diventano visibili insieme attraverso la release immutabile del run e il solo `weather/v1/families/cams/latest.json`; i due `latest` CAMS di provider usati dal prototipo sono bloccati.
- Manifest, release di famiglia e client verificano dimensione, SHA-256, schema, catalogo, identita del run e freschezza prima di usare i payload. Il reader aggiorna insieme le due slice CAMS e conserva la coppia valida gia in cache se un normale refresh fallisce; se un puntatore valido revoca il run attivo e il target non e verificabile, elimina invece la coppia revocata e rende CAMS indisponibile.
- Vite su `127.0.0.1:5174` inoltra `/__local-weather-pilot/weather/v1/...` al data plane `8781`; `/api/...` resta diretto all'API ordinaria `8002`.
- Con l'opt-in browser `-WeatherCloud`, lo stesso prefisso Vite viene invece
  inoltrato al reader pilota HTTPS esistente e sola-lettura. In questa modalità
  il launcher non verifica né pubblica artefatti locali e non avvia la porta
  `8781`; backend e frontend restano locali e soggetti agli stessi record di
  proprietà.
- In modalità `local-pilot`, Home e condizioni locali usano il percorso ICON-2I/CAMS. Open-Meteo non viene chiamato come fallback automatico; il percorso ordinario rimane nel codice e torna disponibile uscendo dalla modalità pilota.
- Home e Meteo condividono il bundle gia verificato: una navigazione tra le due viste non ripete la catena manifest/payload entro 60 secondi. La finestra usa l'orologio reale anche quando il pilot usa un'ora meteorologica fissa; un refresh esplicito la bypassa e resta condizionale tramite ETag.
- La configurazione pilota browser è ammessa soltanto con il server di sviluppo Vite. L'unica build consentita è la variante Android dedicata `localPilot`, autorizzata dallo script protetto; le build Web, Android ordinarie e Play rifiutano o escludono il binding locale.

## Dati verificati caricati

Il catalogo è `istat-2026-irdat-2006-representative-points-v1`, contiene 215 Comuni e ha SHA-256 `d5cb6f9efdf10151caa0508b07ed910488db01dc29de45b293ac9eb05652eca4`.

- **ICON-2I:** run `20260904T000000Z`, 215 Comuni, 73 istanti orari dal 4 settembre 2026 alle 00:00 UTC al 7 settembre alle 00:00 UTC. La vista derivata contiene 36 finestre biorarie; pioggia e raffiche sono aggregate, non ottenute eliminando una riga sì e una no.
- **CAMS Europe:** run `20260904T000000Z`, 215 Comuni, 97 istanti orari dal 4 settembre 2026 alle 00:00 UTC all'8 settembre alle 00:00 UTC, tutte le 28 variabili disponibili e 90 celle di modello uniche. Il payload pesa 10.229.423 byte (4.478.578 byte nella proiezione gzip) e ha SHA-256 `77c9b9181e95797ea7f380a7bd91bc6fdc7133412708a253268de36ab82825f0`.

Home e condizioni locali possono quindi leggere da ICON-2I condizione, temperatura, percepita, umidità derivata, pressione MSLP, vento, raffiche, nuvolosità e precipitazioni, con qualità e provenienza esplicite. CAMS conserva tutti gli inquinanti e i sei pollini nel payload; i pollini restano previsioni sperimentali e non vengono trasformati in soglie cliniche inventate.

Questi sono dati di modello, non misure di stazione. Il run fisso serve per verificare integrazione, contratto e interfaccia: riavviare i processi non scarica dati nuovi e, quando il run non soddisfa più la politica di freschezza/copertura, il client restituisce un errore esplicito senza passare silenziosamente a Open-Meteo.

Per questa coppia di snapshot, CAMS è fresco fino al **5 settembre 2026 alle 00:00 UTC** e utilizzabile fino alle **06:00 UTC**: dopo la prima soglia il client segnala il degrado di aria e pollini, mentre dopo la seconda non presenta il dato come utilizzabile. ICON-2I è fresco fino al **4 settembre alle 18:00 UTC** e utilizzabile fino al **5 settembre alle 00:00 UTC**; soltanto la scadenza ICON blocca `-CheckOnly` e l'avvio. Il launcher continua in ogni caso a verificare run, manifest, hash e catalogo, senza attivare un fallback Open-Meteo.

## Launcher consigliato

Eseguire dalla worktree:

```powershell
Set-Location '<radice-worktree>'
scripts\start-local-weather-pilot.ps1 `
  -CheckOnly `
  -WeatherTestNow '2026-09-04T21:00:00Z'
scripts\start-local-weather-pilot.ps1 -WeatherTestNow '2026-09-04T21:00:00Z'
```

Per verificare l'interfaccia browser con i dati correnti già pubblicati dal
reader cloud pilota, senza rigenerare snapshot locali:

```powershell
scripts\start-local-weather-pilot.ps1 -CheckOnly -WeatherCloud
scripts\start-local-weather-pilot.ps1 -WeatherCloud
```

`-WeatherCloud` è un opt-in: il comando senza switch conserva integralmente il
percorso offline precedente. La modalità cloud usa esclusivamente richieste
`GET` al reader `https://pilot-weather-335641913741.europe-west1.run.app`, non
esegue writer, non apre il data plane locale e non modifica servizi cloud. Non
può essere combinata con `-WeatherTestNow`, perché il reader espone dati
correnti. `-CheckOnly -WeatherCloud` non avvia né ferma processi e dichiara la
porta `8781` come non necessaria, riportandone soltanto l'eventuale listener;
prima di riuscire verifica direttamente che latest e manifest del reader cloud
siano raggiungibili, integri e ancora utilizzabili. La modalità Vite cloud
riusa le impostazioni pubbliche `VITE_*` di `.env.local-pilot.local` (inclusa
la chiave CARTO), senza duplicare il file locale; il launcher neutralizza nel
processo figlio eventuali clock di test o flag Android ereditati.
Per passare tra profilo offline e cloud, arrestare prima la preview posseduta:
`-Stop` resta volutamente indipendente dal profilo e considera tutti e tre i
servizi registrati dal launcher.

`-CheckOnly` controlla prerequisiti e stato delle tre porte senza avviare o fermare processi. L'avvio normale:

1. acquisisce un mutex nominato specifico della worktree: una seconda invocazione concorrente viene rifiutata prima che possa sovrascrivere un record di proprietà;
2. rileva qualunque listener sulle tre porte e rifiuta bind wildcard o LAN;
3. riusa soltanto un servizio loopback di cui possa stabilire l'identità dalla riga di comando oppure da un record di proprietà esatto creato dal launcher;
4. esegue il writer monouso e pretende un'unica risposta canonica `ready`, con ICON, CAMS aria e CAMS pollini correlati e nessun socket aperto;
5. avvia o riusa soltanto dopo tale chiusura il reader HTTP sola-lettura, poi verifica `latest` ICON e famiglia CAMS, release, manifest, run, catalogo, 215 oggetti per collezione, dimensione e SHA-256; la finestra ICON è obbligatoria, mentre CAMS diventa uno stato degradato non bloccante;
6. considera il backend sano soltanto se `/api/healthz` conferma contemporaneamente pilot locale attivo e Open-Meteo disattivato; considera il frontend sano soltanto se quel marker e l'identità OpenAPI attraversano `5174` e se le tre collezioni ICON-2I/CAMS attraversano correttamente il proxy Vite;
7. se uno stadio di avvio fallisce, arresta in ordine inverso soltanto i processi creati nella stessa invocazione;
8. non ferma mai un listener estraneo trovato soltanto tramite la porta.

Per aprire anche il browser si può aggiungere `-Open`. Per fermare i soli processi avviati e registrati dal launcher:

```powershell
scripts\start-local-weather-pilot.ps1 -Stop
```

Il record di proprietà versione 2 lega servizio, porta, identità attesa, wrapper e listener/figli verificati tramite la catena parentale nativa di Windows. PID, istante di avvio ed eseguibile devono coincidere: non basta che una porta sia occupata. Questo controllo non dipende da CIM/WMI. Durante `-Stop` il record viene eliminato soltanto dopo avere verificato che tutti i processi esatti posseduti siano terminati; se il record è ambiguo o l'arresto è incompleto, resta su disco per l'ispezione e il launcher non seleziona altri PID. Un processo sano già esistente può essere riusato se la sua riga di comando è verificabile e coerente, ma se non è stato registrato dal launcher `-Stop` non lo termina.

## Verifica sicura del launcher

Con una preview già attiva, i controlli non distruttivi sono:

```powershell
$tokens = $null
$errors = $null
[System.Management.Automation.Language.Parser]::ParseFile(
  (Resolve-Path 'scripts\start-local-weather-pilot.ps1'),
  [ref]$tokens,
  [ref]$errors
) | Out-Null
if ($errors.Count -ne 0) { $errors; throw 'Errore di sintassi nel launcher.' }

scripts\start-local-weather-pilot.ps1 `
  -CheckOnly `
  -WeatherTestNow '2026-09-04T21:00:00Z'
& "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
  -NoProfile -ExecutionPolicy Bypass `
  -File (Resolve-Path 'scripts\start-local-weather-pilot.ps1') -CheckOnly
```

L'esito atteso è `endpoint-healthy:True` per i tre servizi; un processo privo sia di riga di comando leggibile sia di record del launcher rimane prudentemente `recognizable:False`. Per data plane e frontend registrati, `recognizable:True` conferma anche senza CIM che i listener loopback discendono dai wrapper esatti salvati. Questi comandi non cambiano i record e non chiamano `-Stop`.

Il mutex si può verificare senza toccare i servizi con questo test: il processo esterno tiene il mutex, mentre il secondo processo tenta soltanto `-CheckOnly`.

```powershell
$repo = [System.IO.Path]::GetFullPath((Get-Location).Path).ToUpperInvariant()
$sha = [System.Security.Cryptography.SHA256]::Create()
try {
  $digest = [System.BitConverter]::ToString(
    $sha.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($repo))
  ).Replace('-', '').ToLowerInvariant()
} finally {
  $sha.Dispose()
}
$name = "Local\MeteoFriul.LocalWeatherPilot.$($digest.Substring(0, 32))"
$mutex = [System.Threading.Mutex]::new($false, $name)
$held = $false
try {
  $held = $mutex.WaitOne(0)
  if (-not $held) { throw 'Mutex già occupato prima del test.' }
  & "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
    -NoProfile -ExecutionPolicy Bypass `
    -File (Resolve-Path 'scripts\start-local-weather-pilot.ps1') -CheckOnly
  if ($LASTEXITCODE -eq 0) { throw 'Il launcher concorrente non è stato rifiutato.' }
} finally {
  if ($held) { $mutex.ReleaseMutex() }
  $mutex.Dispose()
}
```

Il secondo processo deve terminare con codice diverso da zero e il messaggio `Un'altra invocazione del launcher locale e gia attiva`. Il test reale di `-Stop` va riservato alla fine della sessione, quando si vuole davvero terminare la preview: non va usato come controllo diagnostico mentre altre prove dipendono dai listener correnti.

## Avvio manuale equivalente

### Terminale 1 — API ordinaria, porta 8002

```powershell
Set-Location '<radice-worktree>'
$env:METEOFRIUL_LOCAL_WEATHER_PILOT = '1'
$env:METEOFRIUL_OPEN_METEO_ENABLED = '0'
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8002
```

Entrambi gli switch sono obbligatori: l'header del proxy non può attivare da solo la modalità pilot e `/healthz` deve riportare `local_weather_pilot_ready: true` e `open_meteo_enabled: false`.

### Terminale 2 — writer monouso e data plane `weather/v1`, porta 8781

```powershell
Set-Location '<radice-worktree>'
$pilotPython = '<percorso-ambiente-python>\Scripts\python.exe'
& $pilotPython .\experiments\weather_autonomy\publish_snapshots_v1.py `
  --icon-payload .\.dev-logs\weather-v1\icon_payload_precipitation_semantics_v3_20260904.json `
  --icon-report .\.dev-logs\weather-v1\icon_report_precipitation_semantics_v3_20260904.json `
  --cams-payload .\.dev-logs\weather-v1\cams_fvg_authoritative_20260904.json `
  --cams-report .\.dev-logs\weather-v1\cams_fvg_authoritative_report_20260904.json `
  --object-db .\.dev-logs\weather-v1\weather-v1-objects-20260905-v6-readonly-split.sqlite3

& $pilotPython .\experiments\weather_autonomy\serve_published_contract_v1.py `
  --object-db .\.dev-logs\weather-v1\weather-v1-objects-20260905-v6-readonly-split.sqlite3 `
  --port 8781
```

Il primo comando termina dopo avere pubblicato e chiuso lo store. Il secondo accetta solo il loopback, apre il database in sola lettura, non scarica dati e non legge OSMER o allerte. Le sole rotte dati ammesse sono:

- `/weather/v1/icon2i/latest.json`;
- `/weather/v1/families/cams/latest.json`;
- `/weather/v1/families/cams/runs/{run-id}/release.json`;
- `/weather/v1/{provider}/runs/{run-id}/manifest.json`;
- `/weather/v1/{provider}/runs/{run-id}/municipalities/{codice-istat}.json`.

I provider validi per gli oggetti immutabili sono `icon2i`, `cams_europe` e
`cams_europe_pollen`. Le rotte `latest.json` di `cams_europe` e
`cams_europe_pollen` non sono piu ammesse: una loro lettura separata potrebbe
ricostruire una coppia appartenente a due run diversi.

### Terminale 3 — app Vite dedicata, porta 5174

```powershell
Set-Location '<radice-worktree>\frontend'
npm run dev:local-pilot
```

Aprire `http://127.0.0.1:5174/`. La modalità resta vincolata al loopback; il normale sviluppo dell'app continua invece su `5173` con `npm run dev`.

## Controlli locali prima del telefono

Verificare nell'ordine:

1. `http://127.0.0.1:8002/healthz` restituisce l'API ordinaria sana;
2. `http://127.0.0.1:8781/weather/v1/icon2i/latest.json` seleziona `20260904T000000Z`;
3. `http://127.0.0.1:8781/weather/v1/families/cams/latest.json` seleziona una release che lega core e pollini allo stesso `20260904T000000Z`;
4. il `latest` ICON, il `latest` CAMS di famiglia, la release e i relativi oggetti immutabili rispondono attraverso `http://127.0.0.1:5174/__local-weather-pilot/weather/v1/...`; i due `latest` CAMS legacy restano negati;
5. nel browser, cambio Comune, Home, evoluzione a 48 ore, fonte ICON-2I e disponibilità CAMS sono coerenti per almeno un Comune di pianura, uno montano e uno costiero;
6. bollettino OSMER e allerte continuano a provenire dalle loro rotte ordinarie.

Per una prova successiva in Chrome sul telefono, con debug USB autorizzato, basta inoltrare la porta Vite:

```powershell
adb reverse tcp:5174 tcp:5174
```

Sul telefono si apre `http://127.0.0.1:5174/`. È una prova browser locale via USB, non una build Capacitor e non una distribuzione.

## APK Android locale affiancato

Quando i controlli browser sono verdi, si può costruire un APK che convive con
l'app installata da Play. Non usa la cartella asset della release e non esegue
`cap sync`: gli asset sperimentali finiscono soltanto nel source set Android
`localPilot` ignorato da Git.

Il comando richiede l'endpoint Cloud Run HTTPS tagged già usato dall'app per
bollettino OSMER, allerte ufficiali e funzioni non meteo:

```powershell
Set-Location '<radice-worktree>'
.\scripts\build-android-local-weather-pilot.ps1 `
  -ApiBase 'https://<tagged-host>.a.run.app/api' `
  -WeatherTestNow '2026-09-04T21:00:00Z'
```

Lo script:

1. genera il Web bundle in una directory temporanea con provider autonomo e nessun fallback automatico Open-Meteo;
2. verifica che nel bundle compaiano sia l'API ufficiale HTTPS sia il solo data plane meteo `http://127.0.0.1:8781`;
3. copia il bundle esclusivamente in `android/app/src/localPilot/assets/public`;
4. costruisce `assembleLocalPilot` con marker monouso;
5. verifica che l'APK sia debuggable e abbia application ID `com.meteofriul.app.localpilot`.

Il telefono va collegato soltanto dopo la build:

```powershell
adb devices
adb reverse tcp:8781 tcp:8781
adb install -r .\frontend\android\app\build\outputs\apk\localPilot\app-localPilot.apk
```

La build locale verificata del 5 settembre è stata installata sul dispositivo di
prova senza pubblicazione. L'APK risultante ha SHA-256
`0ee42f541973683737198a874f87415d803195d40604251b980749cfb49cc5e2`;
l'identità controllata è `com.meteofriul.app.localpilot`.

La porta `5174` non serve all'APK. Il data plane `8781` deve invece restare
attivo sul PC durante la prova; `adb reverse` rende quel solo listener
raggiungibile come loopback del telefono. La navigazione Home/condizioni usa
ICON-2I e CAMS, mentre bollettino OSMER e allerte continuano sull'API HTTPS
passata alla build.

La variante rimuove il permesso di posizione in background, annulla il worker
di prefetch meteo legacy e forza `weather_notices: false` in ogni eventuale
registrazione push. La preferenza e il codice restano intatti nelle build
ordinarie. Le allerte ufficiali visualizzate nell'app non cambiano; la consegna
push FCM non fa parte di questo APK perché il package affiancato non possiede
un'identità Firebase dedicata. Questo evita di riutilizzare impropriamente il
`google-services.json` di produzione.

Il WebView pilota usa l'origine `https://localhost`, la stessa ammessa dall'API
ufficiale. Il mixed content è abilitato soltanto nel source set debug
`localPilot` per raggiungere il data plane USB; la configurazione cleartext ha
base negata e aperture esclusivamente per `localhost`/`127.0.0.1`. Il manifest e
il Capacitor config di produzione restano HTTPS, senza mixed content e senza
WebView debug. Il guard delle release rifiuta inoltre un bundle che contenga il
binding `http://127.0.0.1:8781`, e Gradle vieta di richiedere `localPilot` e
`release` nello stesso task graph.

### Verifica end-to-end Web e Android — 5 settembre 2026

Nel browser pilota, il cambio Pordenone → Udine → Pordenone ha caricato per
ciascun Comune le slice ICON e CAMS complete. I passaggi Home → Scopri → Home e
IT → FUR → IT hanno conservato i dati visualizzati; anche la dicitura friulana
`Meteo, events e teritori` è risultata corretta.

Sul dispositivo Samsung SM_A525F (seriale ADB `OWNER_DEVICE_SERIAL`) risultavano
installati e distinti `com.meteofriul.app` e
`com.meteofriul.app.localpilot`. Nell'APK pilota, i percorsi Home → Scopri →
Home e Home → Bollettino → Home sono rimasti stabili e hanno conservato i dati
visualizzati. Reso temporaneamente irraggiungibile il solo data plane locale
rimuovendo l'inoltro ADB, un arresto forzato seguito dal riavvio ha mostrato
ancora l'ultimo bundle ICON/CAMS verificato presente nella cache persistente;
l'inoltro è stato poi ripristinato. Non sono state osservate eccezioni fatali
nei percorsi provati.

Il cambio manuale di Comune è stato poi reso atomico e verificato con un target
non ancora in cache. Nel browser, la Home è rimasta su Pordenone mentre il
foglio preparava Lignano Sabbiadoro e ha commutato località e valori soltanto a
dati ICON pronti. Sul telefono, con il data plane locale reso irraggiungibile,
la selezione di Trieste ha lasciato Pordenone attivo e mostrato un errore
riprovabile; ripristinato l'inoltro ADB, lo stesso tentativo è riuscito senza
passare da una Home con `--`. Pordenone è stato infine ripristinato.

Open-Meteo era disattivato nella sola configurazione pilota. Rotte e
implementazione del bollettino OSMER e delle allerte ufficiali non sono state
modificate. La temporanea indisponibilità della fonte allerte osservata durante
la prova non è stata trattata come esito positivo. Nessun push, deploy,
scheduler cloud o aggiornamento pubblico è stato eseguito; questa verifica non
certifica gli orari naturali di pubblicazione dei provider né run ricorrenti.

## Ritorno all'app locale normale

Arrestare `5174` e `8781` con `Ctrl+C` se avviati a mano, oppure usare `scripts\start-local-weather-pilot.ps1 -Stop` per i processi posseduti dal launcher. Fermare `8002` solo se non serve più l'API locale. Poi:

```powershell
adb reverse --remove tcp:8781
Set-Location '<radice-worktree>\frontend'
npm run dev
```

Aprire `http://127.0.0.1:5173/`. Le cache del percorso ordinario non vengono cancellate dal pilota.

Quando la prova fisica è definitivamente conclusa, l'APK affiancato si rimuove
senza toccare l'app Play con:

```powershell
adb uninstall com.meteofriul.app.localpilot
```

## Limiti

- Il launcher non acquisisce nuovi run e non attiva scheduler, monitor o job ricorrenti. Il motore scheduler SQLite locale e testabile separatamente con orari UTC espliciti, lease/fencing e retry limitati; nessuna sua definizione e attiva in produzione.
- Il reader CAMS pubblico autorizza soltanto le release `current` e `previous`.
  Revoca e rollback operano sul solo puntatore di famiglia; i comandi legacy
  dei singoli provider sono rifiutati anche se nello store esistono vecchi
  puntatori separati.
- Un crash prima della CAS di famiglia lascia staging immutabile invisibile e
  riutilizzabile; un crash dopo la CAS viene completato idempotentemente dal
  richiamo senza esporre una coppia core/pollini parziale.
- Il percorso predefinito non migra ne riutilizza il database oggetti `v3` o
  state DB sperimentali gia arrivati a `PUBLISHED` con
  `core_latest_etag`/`pollen_latest_etag`: il formato atomico usa il database
  `v5` e checkpoint `family_*`. Il nome del database predefinito `v6-readonly-split`
  identifica il nuovo confine writer/reader, non una migrazione automatica dello
  schema. Un override manuale di `-ObjectDatabase` resta
  responsabilita dell'operatore e deve indicare uno store nuovo o gia conforme
  allo schema `v5`, incluso `disabled_run_ids`; il data plane rifiuta comunque i
  due `latest` CAMS legacy.
  Gli snapshot e i report sorgente restano validi e non vengono riscaricati.
- Il launcher riconosce il data plane soltanto se il valore argv di
  `--object-db` coincide esattamente con il database selezionato; un path con lo
  stesso prefisso non e sufficiente. Dopo un riavvio pulito puo rimuovere un
  record di proprieta `v4` obsoleto soltanto se wrapper, listener e processi
  registrati non esistono piu e la porta e libera.
- Il client usa una cache raw e una cache bundle `v4`; all'avvio elimina le
  corrispondenti cache `v2` e `v3`. Un bundle CAMS persistito e riutilizzabile
  soltanto se conserva la provenienza dalla release familiare verificata e non
  appartiene a `disabled_run_ids`. La revoca viene applicata a tutti i Comuni
  prima di rendere disponibile il run di rollback.
- Il test di un run dimostra integrazione tecnica, non accuratezza meteorologica, affidabilità su più giorni o costo cloud.
- Probabilità di precipitazione, visibilità e orizzonti oltre quelli nativi restano assenti se la fonte non li fornisce.
- Nessun push, deploy o aggiornamento pubblico fa parte di questa procedura.

Per origine, misure e limiti dei dataset consultare `WEATHER_AUTONOMY_INTEGRATED_PILOT_2026-09-03.md`, `CAMS_FVG_PILOT_2026-09-03.md` e `CAMS_DATA_CAPABILITIES_2026-09-03.md` nella stessa cartella.
