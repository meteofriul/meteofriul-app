# PR #1: correzioni della candidata TEST

La prima APK della PR #1 (`47661e20`) è stata collaudata sul Galaxy A52 con
Android 14. Il collaudo ha individuato errori di configurazione API/CARTO,
duplicati nella ricerca comuni e una richiesta CAMS non supportata dal reader
pubblicato. Questa revisione ha preparato una nuova APK, successivamente installata con
autorizzazione esplicita. Il collaudo runtime del 16 ottobre è riportato sotto;
nessuna promozione, AAB, Play o deploy.

## Correzioni e configurazione

- Il builder controlla `/healthz` e `/weather/official-alerts`, risposta JSON
  e CORS per `https://localhost`, prima della compilazione. Il tag ritirato
  `cfweb-bcee09e` viene rifiutato senza modificare l'APK esistente.
- La candidata usa l'API già attiva `natistat-da3e711d`; nessun tag o servizio
  cloud viene creato o modificato. Health, allerte, ricerca ISTAT, webcam e
  promozioni sono stati verificati in sola lettura con HTTP 200 e CORS valido.
- La chiave CARTO locale è caricata nel solo ambiente ignorato della TEST.
  Il builder verifica configurazione e bundle con il guard CARTO esistente.
  Il proprietario ha autorizzato esplicitamente il riuso della chiave client
  nella nuova APK e la verifica sul servizio CARTO. Chiave esclusa dal Git e
  dai log. Una tile reale è stata verificata senza watermark.
- I risultati italiani con codice ISTAT valido vengono deduplicati per codice,
  conservando il primo punto meteo verificato; denominazioni regionali e
  identificatori di provider non generano più duplicati dello stesso comune.
- Le richieste Eventi della località iniziale senza GPS usano il punto del
  catalogo FVG identificato dal suo ISTAT, senza cambiare lo stato della
  località o dichiarare una posizione GPS.
- Home ed Eventi non mostrano più l'avviso tecnico sul catalogo incompleto.
  Diagnostica, scadenze, esclusioni delle fonti e cache restano operative.
  Un risultato incompleto e vuoto mantiene uno stato di indisponibilità,
  senza dichiarare che in zona non esistono eventi.
- Il builder TEST usa per default il contratto CAMS a **30 ore** del reader
  attuale, senza richiedere il sidecar non supportato. `-CamsContinuity` resta
  un opt-in per reader che pubblicano il sidecar validabile a 36 ore.
  Non viene estesa artificialmente la validità dei dati e non viene effettuato
  alcun deploy per abilitare l'estensione.

## Identità e branding

Il pacchetto resta `com.meteofriul.app.localpilot`, con versione
`0.1.14-local-pilot-r8-pr1.2` e nome launcher **Meteo Friûl TEST PR1**.
La versione ufficiale non cambia. Si riusa il colore `#F4B536` della precedente
TEST sidecar, mantenendo separati i due pacchetti.

`scripts/package-pilot-launcher-layers.ps1 -TestOrange` gestisce insieme
background adattivo, livelli colore/monocromatico, splash e marchio Home/Settings.
Il pacchetto `pilot-test-orange-v1` ha un inventario di 19 asset con hash fissato;
il marchio Web ha un percorso nuovo. I raster del logo approvato sono riusati
senza ridisegno. Risorse main/beta, launcher legacy, PWA e notifiche non sono
destinazioni del packaging. Le icone a tema Android restano monocromatiche e
possono usare il colore deciso dal sistema.

## Validazione e limiti

- Suite frontend: **4.937 PASS**, 13 test intenzionalmente saltati in 5 file.
- Lint: PASS. Guard release/API/CARTO: 9 PASS. Guard localPilot: 7 PASS.
- Contratti R8: PASS. Canonical workspace cleanliness e diff: PASS.
- Guard API negativa: il tag ritirato viene respinto con HTTP 404 prima del build.
- Hash APK, firma e resoconto della compilazione sono negli artefatti locali
  ignorati in `build/android-test/2026-10-16`, senza chiavi o mapping nel Git.

Le quattro aree Android restano distinte: test automatici su barre/inset e
orientamento superati; nessuna modifica ai setter delle barre o al manifest
di orientamento; minificazione/resource shrinking verificati nel build.
Il runtime della nuova APK è stato collaudato sul Galaxy A52 dopo
l'autorizzazione del proprietario; esiti e limiti sono riportati sotto. Non si
riusano come PASS le prove del precedente artefatto. Android 15/16, gesti,
tablet e multi-window non sono certificati. Nessuna dichiarazione di rilascio pronto.

Prima di installare: verificare hash e firma, confrontare lo stato dei tre
pacchetti, chiedere conferma e aggiornare esclusivamente `localpilot` con
`adb install -r`. Non disinstallare o cancellare dati di alcuna TEST né dell'app
ufficiale. I servizi locali e ADB reverse restano necessari per questa variante.

## Collaudo runtime del 16 ottobre 2026

Candidata `4f37c49c4bae701cd6b3cde934ef82a06e56208c`, pacchetto
`com.meteofriul.app.localpilot`, versione `0.1.14-local-pilot-r8-pr1.2`:
SHA-256 APK `ddd9fa43fa767b3fabbf142ca8e73cdaddc64414d4fd4cf52bf665899f9d9597`.
Galaxy A52 SM-A525F, Android 14/API 34, 1080×2400 pixel, densità 420,
viewport 411×914 CSS, tre tasti, sistema scuro, WebView 155.0.8059.43.
L'APK minificata installata corrisponde all'artefatto verificato; nessuna nuova build.

| Scenario | Esito | Evidenza locale |
| --- | --- | --- |
| Launcher, splash aperto dall'icona, marchio Home/Settings arancioni | PASS | `02-launcher.png`, `launcher-cold-1.png`, `14-final-home.png`, `12-settings-light.png` |
| CARTO, ricerca comuni e tastiera | PASS | `08-carto-map.png`, `map-runtime.json`, `05-pordenone-search.png` |
| Eventi iniziali senza GPS, lista, filtri e dettaglio; avviso tecnico assente | PASS | `map-runtime.json`, `09-events.png`, `10-event-detail.png`, `15-events-filter.png` |
| ICON-2I, CAMS, UV, webcam e Scopri | PASS nei percorsi eseguiti | `07-weather.png`, `11-discover.png`, `ui-actions.jsonl`, `weather-requests.jsonl` |
| Bollettino con comune esplicitamente selezionato | PASS | `bulletin-reproduction.json`, `14-final-home.png` |
| Bollettino alla prima configurazione con coordinate mancanti | FAIL | `01-home.png`, `map-runtime.json`, `bulletin-reproduction.json` |
| Tema chiaro/scuro, tastiera, scorrimento e barre sul telefono | PASS nei percorsi eseguiti | `05-pordenone-search.png`, `12-settings-light.png`, `13-settings-bottom.png` |
| Background/ripresa, reload WebView e riavvio a freddo | PASS | `state-before-lifecycle.json`, `state-after-resume.json`, `state-after-reload.json`, `state-after-final-cold.json`, `state-final.json` |
| Bridge App/permessi e stabilità R8 | PASS nei percorsi eseguiti; nessun crash/ANR osservato | `native-bridge-result.json`, `native-final.json` |
| Android 15/16, gesti, tablet, multi-window e rotazione fisica | NON VERIFICATO | Matrice non completata; nessuna equivalenza dichiarata |
| Push end-to-end e posizione GPS/background | NON VERIFICATO | `localPilot` non ha identità Firebase Android; permessi rimasti non concessi |

**Difetto aperto PR1-TEST-01:** `bulletinApi.js` converte `lat: null` e
`lon: null` con `Number()`, producendo `lat=0&lon=0`. La richiesta iniziale
di Udine restituisce HTTP 503 (`official_forecast_unavailable`); la stessa
richiesta senza coordinate oppure con `46.0693,13.23715` restituisce HTTP 200.
La selezione manuale di un comune aggira il problema. Il difetto non è stato
corretto in questa attività di collaudo e impedisce di dichiarare la candidata pronta.

Il proprietario ha confermato di avere reimpostato la TEST durante la pausa:
la ricomparsa dell'onboarding e l'assenza delle vecchie preferenze sono attese.
Le preferenze impostate durante questa prova hanno hash identico nei cinque
controlli del ciclo di vita. App ufficiale e APK TEST hanno mantenuto versioni,
hash dei componenti APK, date e inode dei dati; nessuna lettura integrale dei
dati privati dell'app ufficiale. La vecchia TEST era già assente prima della prova.

Area API deprecate: nessuna modifica al codice o alla toolchain; valutazione
statica precedente mantenuta, senza certificare eliminate le chiamate AndroidX
di compatibilità o risolti avvisi Play. Area orientamento: layout verticale
osservato e policy nativa portrait sul telefono; rotazione fisica e adattività
su schermi grandi non verificate. Queste limitazioni non sono trasformate in PASS.

Evidenze private durevoli in `build/android-test/2026-10-16/runtime-4f37c49c/`;
resoconti e inventario hash degli screenshot in `PR1-4f37c49c-TEST-runtime.json`
e `.txt` nella cartella superiore. File esclusi dal Git: contengono schermate
del dispositivo. Chiave CARTO oscurata nei log; seriale e alias esclusi da questo
documento. Nessun deploy, AAB, Play, merge, reinstallazione, cancellazione dati
o pubblicazione di segnalazioni. Servizi locali riavviati conservando SQLite;
telefono lasciato sulla Home con Udine, Italiano e tema Sistema.

## Revisione TEST PR1.3: bollettino al primo avvio

La successiva revisione `0.1.14-local-pilot-r8-pr1.3` corregge nel codice
PR1-TEST-01: la richiesta include latitudine e longitudine solo quando entrambe
sono numeri finiti o stringhe numeriche non vuote. Valori mancanti, vuoti o di
altro tipo non vengono convertiti in zero; gli zeri esplicitamente forniti
restano validi. Senza coordinate il bollettino usa il nome del comune, come
previsto dall'API. La località iniziale e le preferenze non vengono modificate.

Il test con `DEFAULT_APP_LOCATION` e richiesta di aggiornamento forzato
riproduceva il rifiuto del bollettino prima della correzione e ora passa.
I controlli coprono anche una sola coordinata mancante, valori non validi,
coordinate numeriche/stringa e zero esplicito. Suite mirata bollettino,
località, Home, allerte e contratti UI Android: **120 PASS in 13 file**.
Il modulo corretto, eseguito con la vera località iniziale contro l'API attiva,
ha prodotto `weather/forecast?city=Udine`, HTTP 200, CORS valido e contenuto
ufficiale presente, senza modificare la località. Evidenza locale:
`build/android-test/2026-10-16/PR1-pr1.3-first-run-live.json`.

La nuova APK mantiene package, firma TEST, version code, branding arancione
e servizi della PR1.2. Preparazione e verifiche dell'artefatto non autorizzano
l'installazione: è richiesta una nuova conferma esplicita del proprietario.
I dati della TEST installata e l'app ufficiale non vengono toccati dalla build.
Il difetto è corretto e verificato nel modulo/API; il collaudo del nuovo APK
sul telefono rimane **NON VERIFICATO** fino all'installazione autorizzata.
La matrice Android 15/16, gesti, tablet e multi-window e i limiti Firebase
rimangono quelli dichiarati sopra; nessuna promozione a main, AAB, Play o deploy.

## Collaudo autorizzato TEST PR1.3: regressione bollettino risolta

Artefatto installato e verificato sul Galaxy A52, Android 14 / API 34:
commit `fc6fd1621b25304f62017fbf3bcfa77f608d58de`, versione
`0.1.14-local-pilot-r8-pr1.3`, APK minificata R8 SHA-256
`d44c01b969ce5588985b720b3da32077c07cb84f5c525c92de7fab29c6be6cc9`.

**PR1-TEST-01 risolto nel caso verificato sul dispositivo.** Nella WebView
della APK installata, una sostituzione temporanea di localStorage solo in
memoria ha riprodotto la precondizione del difetto: località salvata assente,
coordinate iniziali null e nessuna cache del bollettino. Sono rimaste attive
la lingua e l'onboarding esistenti: non si tratta di una reinstallazione
pulita o di un azzeramento dei dati. La richiesta normale e quella forzata
hanno usato `weather/forecast?city=Udine` senza lat/lon e ottenuto HTTP 200
reali, senza cache HTTP o service worker. Sintesi Home e testo ufficiale
OSMER visibili. Archivio reale identico durante la prova; sostituzione
temporanea rimossa e sessione normale ripristinata.

PASS anche avvio normale/a freddo, cambio giorno del bollettino,
sospensione/ripresa, mappa CARTO con 12 tessere valide, lista Eventi senza
avviso di catalogo incompleto e bridge nativi App/lettura permessi.
Undici valori persistenti di preferenze, identità e località recenti
rimangono identici; nessuna chiave rimossa. Le normali letture aggiornano
cache e timestamp. Metadati e hash delle APK ufficiale e TEST invariati;
nessuna cancellazione dati, disinstallazione, modifica permessi o scrittura
nell'app ufficiale. Nessun crash/ANR osservato nei controlli acquisiti.

Insets e assenza di overflow verificati nelle viste ispezionate su Android 14
in portrait con navigazione a tre pulsanti. API barre di sistema invariate;
nessuna nuova certificazione delle chiamate transitive. R8 esercitato
sull'artefatto esatto nei percorsi provati. Android 15/16, gesti, tablet,
multi-window, rotazione fisica e GPS restano non verificati; limite Firebase
e push invariato. Nessun AAB, Play, deploy, merge o promozione.

Rapporto e schermate locali ignorati da Git:
`build/android-test/2026-10-16/PR1-fc6fd162-TEST-runtime.json` e
`build/android-test/2026-10-16/runtime-fc6fd162/`.
Telefono lasciato sulla Home TEST con Udine e preferenze preesistenti.
