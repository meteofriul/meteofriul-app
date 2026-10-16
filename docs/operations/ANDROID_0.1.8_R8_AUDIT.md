# Android 0.1.8 - audit R8

Stato: audit e refactoring R8 completati sul ramo isolato
`codex/android-0.1.8-r8-hardening`; smoke test dell'APK minificata completato
su emulatore Android 16/API 36. Restano il collaudo su installazione Play e,
se disponibile, il telefono reale.

Baseline del ramo: `70296c52`, sopra la pianificazione `f760a33d` e i due
commit separati per contratto sponsor e consiglio Home. La `0.1.7 (300024)`
resta immutata. Durante audit e refactoring non e' stata generata una nuova
AAB.

## Evidenze riproducibili

L'audit usa come fonti il codice tracciato, il manifest release unificato e il
grafo Gradle effettivamente risolto. I comandi diagnostici eseguiti sono:

```powershell
cd frontend\android
.\gradlew.bat :app:dependencies --configuration releaseRuntimeClasspath
.\gradlew.bat :app:processReleaseMainManifest
```

Il secondo comando genera soltanto il manifest unificato e non produce APK o
AAB. Il manifest verificato e' quello sotto
`app/build/intermediates/merged_manifest/release/`.

Versioni risolte rilevanti:

- Android Gradle Plugin `8.13.0`, Gradle `8.14.3`, Java `21`;
- Capacitor Android/Core `8.5.0`;
- plugin App `8.1.1`, App Launcher `8.0.1`, Geolocation `8.2.2`, Push
  Notifications `8.1.2` e Share `8.0.2`;
- Firebase BoM `34.16.0`, App Check/Play Integrity `19.3.0` e Messaging
  risolto a `25.1.1`;
- WorkManager `2.11.2`, Play Services Location `21.3.0` e
  `iongeolocation-android 2.2.2`.

Il grafo si risolve senza conflitti bloccanti. Gradle segnala l'uso storico di
`flatDir` per il modulo Cordova e funzionalita' deprecate rispetto a Gradle 9;
sono rilievi separati, non una ragione per ampliare il refactoring R8.

## Configurazione verificata

Il solo build type `release` ora usa:

- `minifyEnabled true` e `shrinkResources true`;
- `proguard-android-optimize.txt`;
- conservazione di `SourceFile` e `LineNumberTable`, senza keep/dontwarn
  globali applicativi;
- conservazione mirata del campo `PluginHandle.pluginAnnotation` e del relativo
  getter, lasciando la classe e gli altri membri offuscabili;
- `ndk.debugSymbolLevel 'SYMBOL_TABLE'`.

`privateTest` eredita la release e costituisce quindi l'APK di collaudo
minificata. Il percorso Play richiede il `mapping.txt`, verifica che il suo
SHA-256 coincida con `proguard.map` incorporato nell'AAB e archivia mapping,
hash e stato dei simboli nativi nel manifest append-only schema 3. Il lettore
del ledger mantiene compatibilita' con i manifest storici schema 2 e rende
obbligatori i campi R8 per lo schema 3.

L'unica libreria nativa osservata nella release corrente e'
`libdatastore_shared_counter.so`, fornita transitivamente da AndroidX
DataStore per le quattro ABI. Non esiste codice NDK proprietario nel progetto.

## Mappa di raggiungibilita'

| Area | Entrata e raggiungibilita' | Protezione R8 gia' disponibile | Azione proposta |
| --- | --- | --- | --- |
| Activity e splash | `MainActivity` e' dichiarata nel manifest e deriva da `BridgeActivity`; installa splash e WebView listener | I componenti manifest sono radici R8 | Nessuna keep rule applicativa |
| Plugin Capacitor pubblicati | App, App Launcher, Geolocation, Push e Share sono elencati nel `capacitor.plugins.json` generato; `PluginManager` li carica con `Class.forName` | Capacitor espone regole consumer che mantengono le classi `@CapacitorPlugin`, le sottoclassi di `Plugin` e i metodi `@PluginMethod` | Non duplicare regole generiche; verificare il bridge nella build minificata |
| Plugin Meteo Friul | `MeteoFirebaseAppCheck`, `MeteoBackgroundLocation`, `MeteoNotificationSettings` e `MeteoSystemBars` sono registrati con class literal in `MainActivity`; i metodi sono invocati per annotazione | Le stesse regole consumer Capacitor coprono classi e metodi | Nessuna keep rule aggiuntiva iniziale |
| Plugin pilot | `PilotWeatherPrefetch` e' caricato per classpath testuale solo nel source set `localPilot` | Regole Capacitor; non entra nella release Play | Tenerlo fuori dal cambiamento Play e collaudarlo solo nel pilot |
| Firebase bootstrap | `FirebaseInitProvider` e `ComponentDiscoveryService` sono nel manifest unificato; i registrar sono nomi in `meta-data` | `firebase-components` mantiene tutte le implementazioni di `ComponentRegistrar`; le librerie Firebase/Google mantengono le proprie entry point annotate | Nessuna regola `-keep com.google.firebase.**` |
| App Check | Il provider release/privateTest e' Play Integrity; debug usa Debug App Check. `MeteoFirebaseAppCheckPlugin` e il worker posizione richiedono token | Installer e API sono referenziati direttamente; discovery Firebase e' coperta dalle regole consumer | Smoke test reale del token e di una API protetta |
| Notifiche | Il manifest contiene il `MessagingService` Capacitor, `FirebaseMessagingService`, `FirebaseInstanceIdReceiver`, canale e icona | Componenti manifest e regole Firebase/Capacitor | Provare registrazione, foreground, background, processo terminato e tap |
| WorkManager | `WorkManagerInitializer` e componenti AndroidX sono nel manifest; i Worker Meteo sono passati come class literal e poi istanziati dal nome salvato | `work-runtime` mantiene i nomi delle sottoclassi di `ListenableWorker`, i costruttori e `WorkerParameters`; AndroidX Startup mantiene gli `Initializer` | Nessuna keep rule manuale; obbligatoria prova di aggiornamento con lavoro gia' pianificato |
| Geolocalizzazione | Foreground tramite plugin Capacitor; background tramite plugin custom, due Worker, geofence receiver e boot receiver | Plugin coperto da Capacitor; Worker da WorkManager; receiver dal manifest | Collaudare tutti gli stati permesso, geofence, boot e aggiornamento app |
| Fotocamera | Non risultano plugin Camera, permesso `CAMERA`, `getUserMedia` o input file/capture nel runtime attuale | Non applicabile a R8 nella versione corrente | Segnalare il test come non applicabile; rivalutarlo se viene aggiunto l'upload fotografico |
| Mappe | Territorio e radar usano Leaflet caricato nel bundle JavaScript/WebView; non e' presente Google Maps SDK nativo | Il codice JavaScript non viene offuscato da R8 | Verificare che resource shrinking non rimuova asset Web e che mappe/radar aprano correttamente |
| Deep link | Non esiste un intent filter Android `VIEW` e non c'e' listener `appUrlOpen`; i link correnti sono route validate provenienti dal tap su notifica | Il percorso dipende dal plugin Push e dal bundle JavaScript | Testare i deep link da notifica; trattare gli App Link di sistema come funzionalita' separata |
| Sponsor | Catalogo, selezione per placement, timer e rendering sono JavaScript; le chiamate evento usano App Check | R8 non modifica il bundle JavaScript; resta il rischio indiretto di bridge/App Check e resource shrinking | Testare Home/Eventi/Scopri, esclusiva, rotazione, cache e assenza di lampeggi |
| Share/FileProvider | Share e' un plugin Capacitor; `FileProvider` e' dichiarato nel manifest | Regole Capacitor e radice manifest | Smoke test di condivisione dalla build minificata |

Non sono state trovate reflection o registrazioni dinamiche proprietarie ulteriori
(`Class.forName`, `ServiceLoader`, `DexClassLoader` o accesso riflessivo a membri)
nel codice dell'app. Le occorrenze effettive appartengono ai framework descritti
nella tabella.

## Refactoring R8 applicato

Il cambiamento deve restare in un commit Android dedicato e non deve includere
edge-to-edge, orientamento o layout large-screen.

1. E' stato modificato soltanto il build type `release`:
   - `minifyEnabled true`;
   - `shrinkResources true`;
   - `getDefaultProguardFile('proguard-android-optimize.txt')`.
2. `proguard-rules.pro` conserva gli attributi utili agli stack trace
   (`SourceFile` e `LineNumberTable`) senza introdurre keep globali per
   Capacitor, Firebase, Google Play Services o WorkManager.
3. La prima build minificata privata si e' chiusa alla chiamata
   `PushNotifications.checkPermissions`: il bytecode R8 aveva eliminato
   `PluginHandle.pluginAnnotation` e trasformato il percorso dei permessi in
   un `throw null`. Il guasto e' stato riprodotto, ricondotto al bytecode e
   corretto con una sola regola `-keepclassmembers,allowobfuscation` sul campo
   e sul getter coinvolti. Mapping e DEX della build successiva confermano che
   il campo resta presente. Non sono state aggiunte regole globali; restano
   vietati come scorciatoia `-dontwarn **` e `-keep class ** { *; }`.
4. Il percorso fail-closed di `scripts/build-play-aab.ps1` ora:
   - richiedere il `mapping.txt` della stessa build;
   - copiarlo con nome versionato accanto all'AAB;
   - verificarne SHA-256 e registrarlo nel manifest di release;
   - fallire se AAB, mapping e identita' versione non sono coerenti;
   - verificare la presenza dei metadati di offuscamento nell'AAB.
5. `ndk.debugSymbolLevel = 'SYMBOL_TABLE'` e' attivo sul solo build type
   release. Il gate distingue `embedded`, `not-applicable` e
   `unavailable-transitive-native-libraries`; quest'ultimo copre in modo
   esplicito la `.so` AndroidX priva di simboli proprietari disponibili.

## Evidenza della build privata minificata

Sono stati eseguiti fuori sandbox, nell'ordine previsto da `AGENTS.md`:

```powershell
cd frontend
npm run android:sync
cd android
.\gradlew.bat :app:assemblePrivateTest -PMETEO_API_BASE=https://<tagged-host>/api
```

Esito: `BUILD SUCCESSFUL`; eseguiti `minifyPrivateTestWithR8` e
`optimizePrivateTestResources`. L'APK ignorata da Git contiene un solo DEX,
quattro copie ABI della libreria nativa transitiva, il bundle Web, la
configurazione Capacitor e l'inventario plugin. Sono stati prodotti i report
R8 `mapping.txt`, `configuration.txt`, `seeds.txt`, `usage.txt` e
`resources.txt`. La build corretta produce:

- APK SHA-256
  `c4afbf8245bf5fa168bd4c943f920edf8df00d60740dc4cb06fe6a50c4477107`;
- mapping SHA-256
  `ce13856a7b8aa403ca279201cf25658df7a7b70d8ff997dc82a6eb82d3c67bd0`.

I seed reali confermano la conservazione di `MainActivity`, plugin custom,
receiver e dei due Worker; Firebase Init/Messaging, WorkManager Initializer e
i registrar Firebase risultano raggiungibili tramite manifest o regole
consumer. L'unica regola applicativa aggiunta e' il bordo di metadati Capacitor
descritto sopra e coperto dal contract test.

## Evidenza del collaudo su emulatore

Il collaudo e' stato eseguito su un Pixel 9 virtuale Android 16/API 36 con
immagine Google Play, accelerazione AEHD, 2 core e 3 GB di RAM. Dopo la regola
mirata:

- avvio a freddo e WebView restano attivi; il buffer crash e' vuoto;
- i prompt Android per posizione precisa e notifiche vengono aperti e risolti;
- Home, Eventi, Scopri e la mappa Leaflet/Tempo reale si aprono senza crash;
- Firebase Init e WorkManager Initializer partono; Play Integrity riceve
  richieste reali di token;
- una seconda installazione con `adb install -r` conserva lingua, permessi e
  stato locale e riapre l'app senza onboarding.

Limiti registrati, da non confondere con regressioni R8:

- la firma privata e l'installazione fuori Play non permettono di considerare
  provata l'accettazione App Check da parte del backend; l'interfaccia mostra
  il retry della registrazione;
- il flusso di posizione dell'emulatore non ha concesso il permesso background
  e ha terminato la ricerca automatica in timeout, quindi esecuzione dei due
  Worker, geofence e persistenza del lavoro pianificato restano da provare;
- ricezione push in foreground/background/processo chiuso, tap-notifica e
  condivisione restano test funzionali aperti;
- nelle tre pagine non era presente una card sponsor valida: navigazione e
  bundle sono verificati, ma esclusiva, rotazione e timer indipendenti devono
  attendere il catalogo/backend allineato al nuovo contratto.

## Test prima di qualsiasi AAB

### Gate statici e contrattuali

- aggiungere test per i tre flag Gradle R8 e per il profilo ottimizzato;
- verificare che le regole consumer Capacitor, WorkManager, Firebase Components
  e AndroidX Startup siano ancora presenti dopo ogni aggiornamento dipendenze;
- aggiungere test fail-closed per archiviazione, hash e associazione del
  `mapping.txt` alla versione;
- verificare il manifest release unificato e il `capacitor.plugins.json`
  generato;
- vietare keep/dontwarn globali tramite contract test.

### Build privata minificata e smoke test reale

La compilazione APK e i report R8 sono completati. Prima della AAB installare
questa variante sul telefono di prova e controllare:

- avvio a freddo, splash e caricamento WebView;
- presenza dei plugin nel bridge e chiamata di ogni plugin custom;
- token App Check accettato da un endpoint protetto;
- registrazione push e ricezione in foreground, background e processo chiuso;
- tap notifica con navigazione alla route ammessa;
- posizione foreground e background, geofence, riavvio dispositivo;
- esecuzione dei due Worker Meteo e persistenza di un lavoro pianificato
  attraverso `adb install -r`;
- mappa territorio, radar Leaflet, condivisione e apertura impostazioni;
- catalogo sponsor sulle tre pagine con timer indipendenti.

### Verifiche di shrinking

- ispezionare `mapping.txt`, `usage.txt`, `seeds.txt` e la configurazione R8;
- usare `-whyareyoukeeping` solo come diagnostica temporanea per eventuali
  classi inattese, senza lasciarlo nella configurazione finale;
- confrontare conteggio DEX e dimensione della variante prima/dopo;
- controllare che gli asset Web necessari siano presenti nell'APK;
- rieseguire frontend, backend, contract test Android e installazione reale con
  dati locali conservati.

Solo dopo questi gate, e con autorizzazione esplicita, si potra' eseguire
`scripts/build-play-aab.ps1`. Edge-to-edge e large-screen devono rimanere in
commit e cicli di collaudo successivi e separati.
