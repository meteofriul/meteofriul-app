# CAMS pilota — correzioni nei sorgenti, 10 settembre 2026

Base: `CAMS_MORNING_DIAGNOSIS_2026-09-10.md`, conservato come diagnosi storica.
Questo intervento non ricostruisce nuovamente l'episodio e **non dichiara risolto
il problema sul Samsung**. Nessun deploy, build/installazione Android, acquisizione
ADS, modifica di scheduler, frequenze, configurazioni cloud, sito, UI o testi.

## Correzioni separate

| Commit | Responsabilità |
|---|---|
| `34a4e29` | Budget complessivo del supplemento CAMS |
| `64241f3` | Rifiuto della richiesta vecchia senza cancellare il bundle nuovo |
| `7da153e` | API interna worker, indisponibilità tipizzata del catalogo e recovery |
| `eb2e177` | Coordinamento cache negativa / gate dell'App e integrazione montata |

### Timeout e primo rendering

Il budget CAMS passa da 4 a **20 secondi complessivi**, non 20 secondi per ogni
richiesta. Comprende il percorso preliminare e la catena famiglia/release,
manifest e payload. Le misure disponibili mostrano preflight di circa 1,5–2,1 s
e GET di 5,65–5,98 s: già una coppia può richiedere circa 8,1 s. I restanti
circa 12 s sono un margine limitato per gli altri passaggi, non uno SLA né un
percentile misurato sul telefono. Alla scadenza si abortisce e si ignorano i
risultati tardivi del supplemento.

Il percorso differito consegna ICON e il primo rendering senza aspettare CAMS.
Nessuna modifica alla policy, alle ore o ai dati ICON. I controlli dei contratti,
hash, provenienza, freschezza e revoca rimangono attivi.

### Cache negativa e gate

Un'occasione di aggiornamento già accettata dal gate dell'App può riprovare il
solo CAMS indisponibile, senza essere bloccata dalla finestra negativa iniziata
al completamento del tentativo precedente. Se ICON è ancora verificato e valido,
ne riusa il bundle senza scaricarne di nuovo puntatore, manifest o payload; se
non lo è, resta necessaria la normale rivalidazione.

`camsVerifiedAt` è separato dalla verifica ICON: unavailable non diventa una
verifica CAMS riuscita. Il retry CAMS non rinnova la verifica ICON. Restano il
gate esistente e la deduplicazione in-flight: nessun timer periodico aggiunto,
polling continuo, push o refresh forzato artificiale.

Nello scenario diagnostico il controllo a 10 minuti recupera senza aspettare
quello a 20, anche quando focus, online, visibility e richiesta della route
coincidono. È una prova controllata, non una misurazione sul Samsung.

### Risposta vecchia e revoche

Una richiesta superata da un commit verificato dello stesso comune/cache non
può eliminare il bundle più nuovo nel proprio catch. A continua a essere
rifiutata: non la si converte in successo. Le revoche autorevoli e i rollback
verificati continuano invece a invalidare i dati interessati.

L'aspettativa del test whole-bundle originariamente rosso è mantenuta. Le
ulteriori prove coprono errori di integrità, documento invalido, run disabilitata,
revoca ICON e rollback CAMS sovrapposti. Questo difetto rimane separato dalla
ricostruzione dell'episodio Home, per il quale manca una traccia sul dispositivo.

### Worker e catalogo

Il worker usa `create_verified_request_plan`, non il `main` CLI. La CLI conserva
il proprio comportamento, mentre l'API interna propaga `PublicMetadataUnavailable`.
Il worker persiste `retryable_failure` con stage `public_metadata_plan`; metadata
invalidi restano terminali. Aria/pollini e UV sono valutati separatamente: il
catalogo regionale indisponibile non impedisce la valutazione UV.

Budget totale **480 s**, ritardi esistenti **60/180/300 s** e attesa bounded
dell'acquisizione **45 s** invariati. Piano/riferimento remoto salvati vengono
riusati; pending non è successo e una componente già verificata non viene
nuovamente acquisita. Questa modifica è soltanto nei sorgenti, non nel worker cloud.

## Decisioni ancora aperte

- **Soglia CAMS invariata a 30 ore.** La proposta separata
  `CAMS_AGE_POLICY_PROPOSAL_2026-09-10.md` valuta un massimo di 35 ore per continuità
  della corsa precedente, con campione corrente reale e dentro copertura. Non è
  una certificazione di accuratezza: mancano validazioni locali ai lead 30–35.
  Occorre approvazione prima di allineare produttore, validatore e runtime per
  nuove release, con compatibilità dei contratti e test ai confini. Nessuna
  estensione retroattiva delle release esistenti, nessun trasferimento della policy ICON.
- **UV HTTP 400 non attribuibile a un campo preciso.** Il dettaglio del provider,
  metodo e route non sono stati conservati. Il SDK esegue una GET prima del POST:
  `stage=submission` da solo non identifica l'operazione colpevole. Vedere
  `UV_HTTP_400_DIAGNOSIS_2026-09-10.md` per evidenze e strumentazione minima sicura
  proposta, non implementata. Nessun reinvio ADS né estensione della validità UV.

## Cronologia corretta della release aria/pollini

Orari del 10 settembre, Europe/Rome (CEST, UTC+02:00):

- **12:01:11**: intento congelato, non pubblicazione.
- **12:10:02.461**: cambio atomico del puntatore pubblico della famiglia.
- **12:10:34.721**: fine pubblicazione/readback.
- **12:10:37.202**: verifica conclusiva delle componenti aria/pollini.

## Verifiche finali

Sorgenti finali dei quattro commit sopra; nessun test rosso saltato o aspettativa
indebolita. `git diff --check` pulito. Test temporali con orologio controllato,
non ritardi aggiunti alla logica dell'app.

### Frontend: unione di 18 file, diagnostici, lint

Da `frontend`, un'unica selezione finale senza duplicazioni o filtri di nome:

```powershell
npx vitest run --configLoader native src/services/localWeatherV1Adapter.test.js src/services/localWeatherV1Runtime.test.js src/services/localWeatherV1Runtime.generation.test.js src/services/localWeatherV1Runtime.camsRecovery.test.js src/services/weatherV1Client.test.js src/services/weatherApi.test.js src/services/localWeatherPilotHome.test.js src/features/home/homeDataController.test.js src/services/capacitorAppResume.test.js src/domain/runtime/runtimeRefreshPolicy.test.js src/services/pilotWeatherPrefetch.test.js src/app/App.camsRecovery.test.jsx src/app/AppRoutes.test.jsx src/app/AppRoutes.weatherSwipe.test.jsx src/app/App.officialAlertWiring.test.jsx src/features/weather/WeatherUvCard.test.jsx src/features/weather/uvForecast.test.js src/features/weather/uvForecastRuntime.test.js
npx vitest run --configLoader native --config cams.diagnostic.config.js
npm run lint
```

| Comando | Esito finale |
|---|---|
| Unione regressioni, 18 file | **397 superati, 0 falliti, 0 saltati** |
| Suite diagnostica esplicita, 1 file | **13 superati, 0 falliti, 0 saltati** |
| Lint generale | Exit 0, nessun errore o avviso |

La selezione diagnostica è separata dal glob ordinario: i 13 non sono inclusi
nei 397. Le selezioni parziali durante lo sviluppo non vanno sommate.

Coperture aggiunte/pertinenti:

- `App.camsRecovery.test.jsx`: **2 test con App montata in ReactDOM/jsdom**,
  gate e listener reali; controller Home, API, runtime e adapter reali. La route
  visuale è sostituita da un probe; provider sintetici e fetch live proibita nel
  test. Primo tick dei 10 minuti, eventi coincidenti e ritorno da background/rete.
- `localWeatherV1Runtime.camsRecovery.test.js`: **6 test** per verifica CAMS
  non riuscita, nessun download dei componenti ancora verificati, scadenza della
  verifica ICON, perdita di copertura durante il retry, revoca tardiva e rilascio
  della richiesta condivisa dopo errore interno.
- `localWeatherV1Runtime.generation.test.js`: **5 test** per rifiuto vecchio A,
  conservazione di B e revoche autorevoli. Il test diagnostico whole-bundle
  originariamente rosso conserva la stessa aspettativa su B persistito.
- Adapter/diagnostici: rendering ICON immediato con CAMS oltre 4 s, completamento
  entro il budget e abort con risposta tardiva ignorata; client/runtime ordinari
  coprono integrità, schema, famiglia atomica, freschezza, revoca e fallback.

`jsdom==26.1.0` è una dipendenza **solo di sviluppo**, installata con
`--ignore-scripts` per l'integrazione montata. Nessuna dipendenza operativa Android/cloud.

### Build frontend di produzione

Eseguite le tre fasi equivalenti allo script frontend `build`, con destinazione
temporanea esplicita invece di `frontend/dist`; loader nativo, nessuna modalità
Android e nessuna configurazione aggirata:

```powershell
$camsBuildDirectory = Join-Path $env:TEMP ('meteofriul-cams-source-verification-' + [guid]::NewGuid().ToString('N'))
npx vite build --configLoader native --outDir "$camsBuildDirectory"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
npx vite build --config vite.sw.config.js --configLoader native --outDir "$camsBuildDirectory"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
node scripts/assert-web-push-service-worker.mjs "$camsBuildDirectory"
```

**Tutte le fasi exit 0.** Destinazione effettiva:
`C:\Users\LOCALU~1\AppData\Local\Temp\meteofriul-cams-source-verification-b3119d527bc146e6acf877053710e22b`.
Assertion: `firebase-messaging-sw.js: standalone; enrollment Web disabilitato.`
È una compilazione e un controllo offline del worker Web esistente, non un cambio
Firebase/notifiche o una build APK. Nessun asset Android copiato o sincronizzato.

Avvisi prestazionali preesistenti, riportati integralmente e non corretti:

1. `[INEFFECTIVE_DYNAMIC_IMPORT] src/features/almanac/AlmanacView.jsx is dynamically imported by src/app/AppRoutes.jsx but also statically imported by src/features/weather/WeatherSkyCard.jsx, dynamic import will not move module into another chunk.`

2. Messaggio completo del reporter:

   ```text
   [plugin builtin:vite-reporter]
   (!) Some chunks are larger than 500 kB after minification. Consider:
   - Using dynamic import() to code-split the application
   - Use build.rolldownOptions.output.codeSplitting to improve chunking: https://rolldown.rs/reference/OutputOptions.codeSplitting
   - Adjust chunk size limit for this warning via build.chunkSizeWarningLimit.
   ```

Nessun import, suddivisione bundle, soglia o regola modificato per nasconderli.
Vite segnala inoltre che la destinazione esterna non viene svuotata:
`(!) outDir C:\Users\LOCALU~1\AppData\Local\Temp\meteofriul-cams-source-verification-b3119d527bc146e6acf877053710e22b is not inside project root and will not be emptied.`
`Use --emptyOutDir to override.` È atteso per una nuova directory temporanea;
non è stato usato l'override né eliminato alcun output precedente.

### Python e i sette test worker

Ambiente di test temporaneo con dipendenze reali, incluse le versioni del
Dockerfile `google-cloud-storage==3.13.1`, `ecmwf-datastores-client==0.5.3`,
`eccodes==2.48.0` e `numpy==2.5.2`. Nessuna modifica alle dipendenze operative.
Da `experiments/weather_autonomy`:

```powershell
& 'C:\Users\LOCAL_USER\AppData\Local\Temp\meteofriul-cams-worker-tests-36c4afeae1784e629991cea4e37412fc\Scripts\python.exe' -B -m unittest test_cams_worker_recovery test_cams_request_plan test_retrieve_remote_cams test_cams_readback test_cloud_worker test_operational_diagnostics test_uv_recovery test_uv_replacement test_uv_conversion test_uv_cloud
```

**128 superati, 0 falliti, 0 saltati.** Inclusi tutti i **sette worker originali**
e quattro nuovi test worker, oltre a due nuovi test dell'API del piano.
Le sessioni parziali precedenti (47 e 11 test) sono incluse, non da sommare.
Il primo tentativo della suite estesa aveva 45 errori ambientali su 126 test per
dipendenze mancanti: completato il venv, la sessione finale estesa a 128 passa.

Sono test offline con SQLite/file temporanei e confini remoti controllati; le
librerie sono reali, le risposte ADS/cloud sono simulate. Non sono acquisizioni
live né verifiche sul telefono.

### Letture live e controlli non eseguiti

Eseguite soltanto letture puntuali di log e oggetti già presenti per la diagnosi
UV nel progetto `meteofriul-pilot-20260906`, regione `europe-west1`, e lettura delle
fonti pubbliche ECMWF/SDK. Comandi e limiti sono nel rapporto UV. Non è stata
riavviata una pipeline né ripetuto il controllo generale.

Non eseguiti test live ADS/acquisizione, deploy o verifiche end-to-end Samsung.
L'attivazione opt-in dei test live non è modificata. Per una verifica reale
serviranno successive distribuzioni autorizzate del frontend pilota sul telefono
e del worker, quindi osservazione di un ciclo automatico e del recupero senza
refresh manuale. La soglia di 30 ore e il 400 UV restano limiti distinti.
