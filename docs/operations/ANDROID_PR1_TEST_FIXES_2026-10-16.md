# PR #1: correzioni della candidata TEST

La prima APK della PR #1 (`47661e20`) è stata collaudata sul Galaxy A52 con
Android 14. Il collaudo ha individuato errori di configurazione API/CARTO,
duplicati nella ricerca comuni e una richiesta CAMS non supportata dal reader
pubblicato. Questa revisione prepara una nuova APK, senza installazione,
promozione, AAB, Play o deploy.

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
Il runtime della **nuova** APK, inclusi launcher, splash e Home, resta da
collaudare dopo l'autorizzazione del proprietario. Non si riusano come PASS
le prove del precedente artefatto. Android 15/16, gesti, tablet e multi-window
non sono certificati per questa candidata. Nessuna dichiarazione di rilascio pronto.

Prima di installare: verificare hash e firma, confrontare lo stato dei tre
pacchetti, chiedere conferma e aggiornare esclusivamente `localpilot` con
`adb install -r`. Non disinstallare o cancellare dati di alcuna TEST né dell'app
ufficiale. I servizi locali e ADB reverse restano necessari per questa variante.
