# Community nazionale: prove sulla pilota locale

Questa fase collega il browser pilota e il package Android
`com.meteofriul.app.localpilot` a un servizio Community temporaneo sul PC.
L'avvio normale conserva segnalazioni, quote, revisioni, ricevute delle
operazioni, conferme e moderazione in un database SQLite locale:
`.dev-logs/community-pilot/state.sqlite3`. L'adattatore in memoria resta per
i test isolati. Il servizio Community non usa archivi cloud e non genera push.

Il contratto corrente delle azioni è [PILOT_COMMUNITY_RULES.md](PILOT_COMMUNITY_RULES.md).
Le prove Samsung datate più avanti documentano la versione precedente: non
attestano l'installazione o il collaudo delle nuove regole sul telefono.

Il lavoro riguarda soltanto la pilota. Questo percorso non pubblica Web/APK,
non modifica main/beta e non abilita la Community nazionale nella versione
pubblicata. Gli altri moduli dell'app conservano i propri collegamenti già
configurati; il parametro Android `ApiBase` resta richiesto per quei moduli.

## Collegamenti e isolamento

| Componente | Indirizzo o identificativo |
| --- | --- |
| Preview browser autorizzata | `http://127.0.0.1:5174/`, avviata dal launcher del repository |
| Community sul PC | `http://127.0.0.1:8783/api/community/` |
| Proxy Community nel browser | `/__local-community/api` |
| Community nella APK pilota | `http://127.0.0.1:8783/api`, attraverso ADB reverse |
| Bundle meteo nazionale locale | `http://127.0.0.1:8782` |
| Package Android | `com.meteofriul.app.localpilot` |
| Namespace dello stato Community pilota | `localCommunityPilot:v1:` |

Il servizio ascolta esclusivamente su loopback. Controlla Host e Origin e
richiede `X-Meteo-Pilot-Community: local-only` nelle richieste che possono
modificare lo stato. Il frontend pilota aggiunge automaticamente l'header.
L'header identifica il protocollo locale: non è un sistema di autenticazione
adatto a esporre il servizio su Internet. Non cambiare il bind in `0.0.0.0`.

Cache delle segnalazioni, identità locale, consenso alle linee guida, stato
personale, operazioni pendenti e moderazione usano il namespace pilota. La cache delle
letture include inoltre Comune/coordinate e raggio, conservando al massimo
dodici zone. Una risposta di Pordenone non deve essere riutilizzata per Urbino.
Le risposte HTTP del servizio sono `Cache-Control: no-store`.

## Prerequisiti e avvio nel browser

Operare dalla radice canonica `F:\proggetto Meteo Friul App\meteo FRIUL`.
Devono essere disponibili Python con le dipendenze backend, Node e il file
`.dev-logs/local-weather-pilot/community-geography.sqlite3`. Il file geografico
viene verificato prima che il servizio apra la porta; dettagli e ricostruzione
sono in [PILOT_COMMUNITY_GEOGRAPHY.md](PILOT_COMMUNITY_GEOGRAPHY.md).

Il reader nazionale sulla porta **8782 deve essere già attivo** e servire un
bundle locale verificato. Il launcher lo controlla e lo riusa, non lo crea.
Nella sessione del 20 settembre 2026 il reader usa il bundle nazionale reale
preparato per quella data, conservato in una directory temporanea. Quel percorso
è un dettaglio della sessione: non è una posizione di installazione permanente
da copiare nelle configurazioni.

Controllo in sola lettura del pointer nazionale:

```powershell
Invoke-RestMethod 'http://127.0.0.1:8782/weather/v2/icon2i/pilot.json'
```

Il controllo del launcher richiede:

- `kind = meteofriul.weather.icon.national.local_pilot_pointer`;
- `contract = weather/v2/icon2i`;
- `status = experimental_local_pilot_only`;
- 7.894 Comuni e hash del catalogo nazionale canonico.

Questo controllo verifica l'identità del bundle. Per un test con dati correnti
verificare anche la corsa e gli orari mostrati nell'app; una risposta HTTP valida
da sola non prova la freschezza meteorologica.

Avviare e poi controllare i servizi:

```powershell
.\scripts\start-local-weather-pilot.ps1 -NationalOnly -CommunityPilot
.\scripts\start-local-weather-pilot.ps1 -NationalOnly -CommunityPilot -CheckOnly
Invoke-RestMethod 'http://127.0.0.1:8783/api/community/health'
```

La health Community deve riportare `ok: true`,
`kind: meteofriul.community.local-pilot.v1`, `storage: sqlite`, `scope: IT` e
`published: false`. Il launcher verifica inoltre processo riconoscibile e
ascolto loopback. Se la porta 8783 appartiene a un processo non conforme,
l'avvio si ferma senza terminarlo.

Se il browser sta ancora usando il precedente profilo della preview, riavviare
soltanto il frontend tramite il launcher:

```powershell
.\scripts\start-local-weather-pilot.ps1 -NationalOnly -CommunityPilot -RestartFrontend
```

Dopo una modifica al backend Community usare `-RestartCommunity` nello stesso
comando. Il launcher verifica la proprietà del processo prima di riavviarlo.
Il database SQLite e le protezioni persistenti restano conservati; i dati del
vecchio processo esclusivamente in memoria non vengono migrati automaticamente.

Aprire quindi `http://127.0.0.1:5174/`. Non utilizzare `start-dev.ps1` o la porta
5173 per validare questa pilota. `-NationalOnly` usa l'orologio reale e non è
compatibile con `-WeatherTestNow` o `-WeatherCloud`.

## Build protetta e collegamento al Samsung

Usare il builder locale già esistente con `-CommunityPilot`, senza
`-WeatherCloud` e senza un orologio di prova. Il valore seguente è il tagged
endpoint già documentato per gli altri moduli della pilota; Community e meteo
nazionale mantengono gli indirizzi locali indicati sopra.

```powershell
$pilotTaggedApiBase = 'https://cfweb-bcee09e---meteofriul-api-bx24xqvcda-ew.a.run.app/api'
.\scripts\build-android-local-weather-pilot.ps1 `
  -ApiBase $pilotTaggedApiBase `
  -CommunityPilot
```

Quando eseguita da Codex, questa build va lanciata fuori dal sandbox come
richiesto dalle istruzioni Windows del workspace. Il builder prepara gli asset
in una directory temporanea, applica i guard e produce esclusivamente
`frontend/android/app/build/outputs/apk/localPilot/app-localPilot.apk`.
Controlla package `com.meteofriul.app.localpilot`, configurazione Capacitor,
branding già approvato e collegamenti della build pilota. Non installa l'APK
automaticamente.

Collegare il telefono via USB, autorizzare il debug e identificare il seriale:

```powershell
$pilotAdb = Join-Path $env:LOCALAPPDATA 'Android\Sdk\platform-tools\adb.exe'
& $pilotAdb devices -l
$pilotDeviceSerial = 'SOSTITUIRE_CON_IL_SERIALE_DEL_SAMSUNG'
& $pilotAdb -s $pilotDeviceSerial reverse tcp:8782 tcp:8782
& $pilotAdb -s $pilotDeviceSerial reverse tcp:8783 tcp:8783
& $pilotAdb -s $pilotDeviceSerial reverse --list
& $pilotAdb -s $pilotDeviceSerial install -r 'frontend/android/app/build/outputs/apk/localPilot/app-localPilot.apk'
```

8782 collega il meteo nazionale e 8783 la Community. Il lettore storico 8781,
se già usato da altre prove locali, è distinto: non sostituire il reverse 8782
con un reindirizzamento verso 8781. Questa prova nazionale richiede il reader
nazionale reale su 8782.

`install -r` aggiorna lo stesso package preservandone i dati. Non disinstallare
l'app e non usare `pm clear`. Dopo l'aggiornamento controllare che località,
preferenze e alias del telefono siano rimasti disponibili. La nuova Community
mantiene il proprio stato locale nel namespace separato della pilota.

Il telefono dipende dal PC acceso e dal collegamento USB per questi due
servizi locali. Dopo una riconnessione controllare `reverse --list` e ripetere
i due reverse se necessario.

## Regole da verificare

La località selezionata determina **quali segnalazioni leggere**, entro 30 km
dal punto comunale o dalle coordinate della località attiva. L'API ammette
raggi fra 1 e 100 km e applica il limite del feed dopo il filtro geografico.

L'invio richiede invece una posizione GPS con età fra 0 e 120.000 ms e
accuratezza dichiarata maggiore di 0 e non superiore a 500 m. Il backend
riconosce il Comune tramite i poligoni ISTAT italiani, comprese le isole;
rifiuta estero, mare fuori dai confini comunali e attribuzioni ambigue.
Selezionare manualmente Urbino mentre il telefono è a Pordenone permette di
consultare Urbino, ma non dimostra una presenza fisica a Urbino.

Il Comune rilevato può essere corretto soltanto verso un Comune della stessa
regione il cui punto pubblico sia entro 5 km dal GPS. Il Comune che contiene
effettivamente il GPS resta valido anche quando il suo punto rappresentativo
è più lontano, per esempio in un Comune molto esteso. Le identità sono basate
sul codice ISTAT, così i Comuni omonimi rimangono distinti.

Le coordinate rese pubbliche sono quelle fisse del Comune. Il GPS grezzo non
viene salvato nel repository Community né restituito come posizione del report.

Le regole temporali della pilota sono:

- durata pubblica della segnalazione: **60 minuti**;
- intervallo minimo fra nuovi invii indipendenti: **2 minuti**;
- massimo **4 negli ultimi 60 minuti** e **12 nelle ultime 24 ore**, con
  finestre mobili calcolate dal server e quote conservate dopo il ritiro;
- unicità per **installazione + codice ISTAT + fenomeno**;
- **Correggi** entro **5 minuti**, stesso contributo e scadenza invariata;
- **Ritira e sostituisci** una volta per sequenza, senza l'attesa minima ma
  consumando una quota e rispettando i massimali;
- nessuna restituzione della quota tramite il vecchio annullamento di 60 secondi;
- **45 minuti** soltanto come intervallo interno per premi/reputazione;
- limiti di frequenza, conferme e moderazione già applicati dal servizio;
- limite locale di 10.000 report attivi, con rifiuto esplicito a capacità piena.

### Significato di «Aggiorna situazione»

> **Aggiorna situazione**
>
> Conferma che il fenomeno è ancora presente e rinnova la visibilità
> dell’osservazione per un’ora, nel rispetto delle smentite e delle altre
> condizioni di visibilità. Non crea un nuovo contributo e non modifica il
> tipo di fenomeno.

Questa funzione non corregge un fenomeno scelto per errore e non sostituisce
un’osservazione con un’altra. Le azioni **Correggi** e **Ritira e sostituisci**
hanno contratti separati, riportati nel documento delle regole.

Il rispetto delle smentite è conservativo e atomico:

- nel repository SQLite locale della pilota, aggiornamento e smentita sono
  serializzati in transazioni; l'adattatore in memoria per i test usa lo stesso
  confine atomico. Le regressioni verificano entrambi gli ordini seriali;
- se l’aggiornamento viene accettato per primo, la smentita successiva viene
  associata alla nuova scadenza del gruppo e continua a nasconderlo sulla mappa
  dell’installazione che l’ha espressa;
- se una o due smentite sono già registrate, lo stato temporale è `ceased` e
  l’aggiornamento viene rifiutato con
  `community_observation_not_updateable`, senza modificare report, conteggi o
  identità dei voti;
- con tre smentite il gruppo è ritirato dalla mappa e non può essere riattivato
  tramite «Aggiorna situazione».

Le regressioni corrispondenti sono:

- `test_update_before_expiry_renews_same_observation_atomically`: stesso ID,
  `group_id`, `type_id`, Comune e `created_at`; cambiano soltanto revisione,
  aggiornamento e scadenza;
- `test_update_after_subthreshold_denials_is_rejected_without_mutation`: con
  una o due smentite l’aggiornamento è rifiutato e report più stato delle
  conferme restano identici;
- `test_denial_after_update_uses_renewed_expiry_and_blocks_later_update`: se
  l’aggiornamento avviene per primo, il «no» successivo conserva la nuova
  scadenza e impedisce ulteriori rinnovi;
- `hides a group from this installation after its local no vote`: il «no»
  locale continua a escludere il gruppo dai marker di quella installazione;
- `test_update_cannot_revive_an_observation_withdrawn_by_denials`: tre
  smentite rendono il ritiro non riattivabile.

Il riavvio del **processo Community sul PC** conserva lo stato nel database
SQLite, incluse quote, smentite e ricevute delle operazioni già accettate.
Un errore di apertura o scrittura impedisce di dichiarare un successo; non
avvia automaticamente un archivio vuoto. Dopo il riavvio attendere la rilettura
del feed: la cache del telefono non sostituisce lo stato autorevole del server.
Questa persistenza locale non rende la pilota indipendente dal PC.

## Sequenza di prove manuali

Annotare versione APK, corsa meteo, località selezionata, risultato e dispositivo.
I test con coordinate simulate vanno eseguiti solo sulla preview 5174 o contro
l'API locale 8783, indicando esplicitamente che sono prove.

| Prova | Operazione | Risultato atteso |
| --- | --- | --- |
| Pordenone, lettura | Selezionare Pordenone e aprire Meteo → Tempo reale | Pulsante e flusso Community pilota disponibili; feed limitato alla zona |
| Urbino, lettura | Selezionare Urbino, quindi tornare a Pordenone | Nessun messaggio di regione non attiva per Urbino; nessun riciclo del feed di Pordenone; cambio sezione reattivo |
| Report reale dal telefono | Consentire GPS, accettare le linee guida e inviare un fenomeno di prova dalla posizione effettiva | Comune determinato dal GPS, report nel relativo feed, coordinate pubbliche comunali; il test resta nel PC |
| Invio nazionale simulato | Nella sola preview locale usare un GPS di prova a Urbino e inviare un report di prova | ISTAT `041067`; report visibile nel feed Urbino e assente da quello Pordenone |
| GPS negato | Negare il permesso e aprire il flusso di invio | Nessun invio; spiegazione del permesso necessario; mappa e consultazione restano utilizzabili |
| GPS vecchio o impreciso | Nel test locale inviare a `/resolve` un `age_ms` maggiore di 120.000 o `accuracy_m` maggiore di 500 | Errore `community_fresh_gps_required`; nessuna segnalazione creata |
| GPS estero | Nel test locale provare Lubiana, San Marino o Vaticano | Invio/rilevamento rifiutato; nessuna attribuzione automatica al Comune italiano più vicino |
| Comune manuale incoerente | GPS a Pordenone, tentativo di attribuire l'invio a Urbino | Rifiuto; una selezione manuale distante non sostituisce il GPS |
| Quote e unicità | Inviare fenomeni diversi, poi un doppione; provare i confini delle finestre mobili | Attesa 2 minuti, massimo 4/60 minuti e 12/24 ore; doppione limitato ad autore+Comune+fenomeno |
| Correzione | Correggere tipo o Comune nei primi 5 minuti con GPS valido | Stesso ID e scadenza, nessuna nuova quota o punto; le protezioni restano |
| Sostituzione | Ritirare per sostituire, poi inviare esplicitamente; tentare un'altra sostituzione della stessa sequenza | Una sola deroga all'attesa; massimali rispettati, nessuna catena e nessun invio automatico |
| Aggiornamento ordinario | Annotare ID, revisione e scadenza; aggiornare prima della scadenza con GPS fresco | Stesso ID, revisione incrementata una volta e nuova scadenza di 60 minuti; nessun nuovo contributo |
| Risposta persa dopo il commit | Interporre un proxy locale one-shot: inoltrare la PATCH, attendere il `200 updated` del server e trattenere integralmente la risposta per oltre 12 secondi | Timeout visibile; `operation_id` e revisione attesa restano persistiti; il server ha già una sola revisione aggiuntiva |
| Replay dopo timeout | Prima di navigare o aggiornare il feed, usare l'azione esplicita di verifica/riprova | Stesso `operation_id` e stessa revisione attesa; risposta `idempotent_replay=true`; `revision`, `updated_at` ed `expiresAt` non cambiano una seconda volta |
| Riapertura dopo risposta persa | In una prova separata, forzare la chiusura dopo il timeout e riaprire l'app con il proxy tornato trasparente | Il GET fresco riconcilia la revisione avanzata, elimina l'operazione pendente e non invia automaticamente una seconda PATCH |
| Aggiornamento alla scadenza | Far valutare la PATCH dal server esattamente alla scadenza o dopo | `community_observation_expired`; nessun rinnovo, revisione, punto o consumo di quota; percorso esplicito verso una nuova osservazione |
| Servizio irraggiungibile | Rimuovere temporaneamente solo il reverse 8783, tentare un invio, poi ripristinarlo | Errore visibile, nessun falso successo e nessun ripiego sulla Community pubblicata |
| Riavvio servizio | Riavviare il processo pilota e rileggere il feed, riprovare un'operazione accettata | Report non scaduti, quote, voti, smentite, moderazione e ricevute conservati; nessun doppione |
| Fluidità e regressioni | Passare fra Home, Meteo, Previsioni, Bollettino, Tempo reale, Eventi e Scopri | Navigazione utilizzabile durante caricamento o errore Community; radar e meteo continuano il proprio ciclo |

Per la prova di indisponibilità USB, senza fermare processi:

```powershell
& $pilotAdb -s $pilotDeviceSerial reverse --remove tcp:8783
# Eseguire il tentativo nell'app e controllare l'errore.
& $pilotAdb -s $pilotDeviceSerial reverse tcp:8783 tcp:8783
```

La prova di risposta persa deve essere distinta da una semplice assenza di
rete: il proxy deve prima ricevere dal backend una risposta riuscita alla
PATCH, senza inoltrarne al telefono né le intestazioni né il corpo. Dopo il
timeout il proxy torna trasparente. Registrare per entrambe le richieste
`report_id`, `operation_id`, revisione attesa, `revision`, `updated_at` ed
`expiresAt`. Ripristinare sempre `tcp:8783 -> tcp:8783` al termine, anche se
la prova fallisce. Non usare questo fault injector sulla versione pubblicata.

Per una verifica locale del GPS vecchio che non crea report:

```powershell
$pilotHeaders = @{ 'X-Meteo-Pilot-Community' = 'local-only' }
$pilotStaleGps = @{ lat = 45.9567; lon = 12.6605; accuracy_m = 30; age_ms = 120001 } | ConvertTo-Json
Invoke-RestMethod 'http://127.0.0.1:8783/api/community/resolve' `
  -Method Post -Headers $pilotHeaders -ContentType 'application/json' `
  -Body $pilotStaleGps
```

L'errore HTTP 400 è l'esito atteso di quest'ultima prova. Un catalogo geografico
mancante o alterato deve bloccare l'avvio, oppure produrre un errore esplicito
di indisponibilità; non si introduce un resolver approssimativo per superarlo.

## Verifica eseguita il 20 settembre 2026

- Checkpoint prima dell'ultimo collaudo di rete: `8d829ec`, nessun push.
- Frontend: suite completa 4.312 test superati, 13 saltati; 15 test mirati
  superati sul recupero dell'aggiornamento e sui relativi testi. ESLint pulito.
- Backend: la validazione precedente resta a 137 test e 41 subtest superati;
  la chiusura mirata sulle smentite porta `test_pilot_community.py` a 40 test
  e 8 subtest superati. Nessun codice backend di produzione è stato modificato.
- Guard browser/Android: 14 test superati; contratto launcher PowerShell verde.
- Browser: Pordenone e Urbino mostrano il pulsante pilota; GPS non disponibile
  lascia l'invio disabilitato senza bloccare la consultazione.
- API locale: risoluzione Urbino, creazione di una segnalazione sintetica,
  filtro geografico Pordenone/Urbino e annullamento; feed puliti dopo la prova.
- Samsung: APK localpilot installata con `install -r`; hash dello storage
  WebView invariati prima/dopo. L'utente conferma Pordenone con GPS acceso.
- Samsung, risposta persa reale: il proxy ha trattenuto la risposta dopo il
  `200 updated` fino al timeout client di circa 12 secondi. Il replay esplicito
  ha riutilizzato lo stesso `operation_id` e la stessa revisione attesa; il
  server ha risposto `idempotent_replay=true` senza cambiare una seconda volta
  `revision`, `updated_at` o `expiresAt`.
- Samsung, riapertura dopo risposta persa: l'operazione era ancora presente
  prima di aprire Tempo reale; il GET fresco l'ha riconciliata e rimossa senza
  emettere un'altra PATCH. Simbolo, proprietà e nuova scadenza sono risultati
  allineati alla revisione restituita dal server.
- Samsung: invio dal modulo Android, comparsa del marker, aggiornamento,
  risposta persa, replay idempotente, chiusura forzata e riapertura sono stati
  verificati sul dispositivo reale. Il backend temporaneo di collaudo e il
  proxy sono stati arrestati; il collegamento ordinario `8783 -> 8783` è stato
  ripristinato.

- Regressione visiva individuata dall'utente: il paragrafo informativo aggiunto
  alla griglia compatta sottraeva altezza alla mappa. Rimosso completamente:
  `LiveView.jsx` e `live.css` tornano identici al checkpoint. L'indicazione di
  prova resta nel modulo d'invio. Verifica screenshot e DOM browser 626×930:
  un solo figlio nella griglia, area mappa/dock alta 657 px a partire da y=184,
  nessuno spazio vuoto aggiunto. Test strutturale dedicato alla regressione.

APK finale con layout ripristinato SHA-256:
`7e6d72eb120e2bee69747c494566eb99709b4c5d9b815c28a74369ca1bd429ca`.
La Community resta temporanea e dipendente dal PC: nessun backend cloud,
pubblicazione o archivio pubblico è stato modificato.
