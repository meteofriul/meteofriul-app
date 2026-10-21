# Meteo Friûl

**Prima di preparare una release Android:** leggere le [regole obbligatorie di preparazione e recupero dagli errori](docs/operations/ANDROID_BUILD_PREVENTION_RULES.md), insieme al [runbook Play](docs/operations/PLAY_AAB_RUNBOOK.md).

Meteo Friûl è un'app indipendente dedicata al Friuli-Venezia Giulia. Riunisce
meteo locale, bollettino regionale, allerte ufficiali, radar, webcam, eventi e
contenuti culturali; l'interfaccia è disponibile in italiano e friulano.

> Stato Web verificato il 20 ottobre 2026: il sito pubblico espone `0.1.14`,
> ma non contiene ancora tutte le modifiche approvate nella TEST e integrate
> in `main`. È in preparazione il candidato Web dalla stessa base Android;
> preparazione e pubblicazione sono fasi distinte.
>
> La Web App deve seguire la release Android: è anche il canale per chi usa
> iPhone dal browser. Il [percorso di allineamento Web/Android](docs/operations/WEB_ANDROID_RELEASE_PARITY.md)
> richiede sorgenti e funzionalità coerenti, oltre alla verifica Safari/iPhone.

**Web — verifica locale del 20 ottobre 2026:** candidata verificata su Brave
del Galaxy, incluse le correzioni a Indietro nel dettaglio Eventi e al doppio
comando di cancellazione nella ricerca. Superati 56 test mirati e i controlli
italiano/chiaro e friulano/scuro. Commit e integrazione locale autorizzati;
nessuna pubblicazione. Evidenze e limiti nel
[verbale Web sul Galaxy](docs/operations/WEB_APP_BROWSER_FIXES_20261020.md).

**Stato aggiornato al 21 ottobre 2026:** la AAB **0.1.15 / 300033** è nel
test interno personale. La verifica del pacchetto ufficiale sul Galaxy è
conclusa con rilievi aperti: configurazione nativa assente, posizione segnalata
spenta dopo l'aggiornamento e sovrapposizione nella mappa. Il codice della
release resta nella PR 11 in bozza; l'aggiornamento documentale di main non
ne autorizza la promozione. [Stato, rami e prossimi passi](docs/operations/RELEASE_0.1.15_STATUS_20261021.md).

**Job meteo ICON-2I — verifica del 21 ottobre 2026:** nuova corsa pubblicata,
checkpoint schema 2, 215 documenti e sidecar e campione nazionale verificati.
Le tolleranze sono esercitate nei dati reali. Il 21 ottobre sono stati aggiornati
anche il job avvisi (valutazione per fenomeno e sidecar abilitato) e il job Eventi
(Spazzapan e recupero dei timeout). Deploy verificati; le prime corse ordinarie
successive restano da controllare. [Stato, rollback e verifiche pianificate](docs/operations/JOBS_RECOVERY_DEPLOY_20261021.md).
[Verifica del produttore e limiti](docs/operations/ICON2I_PAYLOAD_LIMIT_DEPLOY_20261020.md).

**Allerte FVG e Community:** aggiornamenti già distribuiti e verificati nei
rispettivi [verbali allerte](docs/operations/FVG_ALERTS_DEPLOY_20261020.md) e
[Community](docs/operations/COMMUNITY_0.1.15_DEPLOY_20261021.md).
Sponsor, pannello e allineamento dati sponsor restano disattivati.

**Storico TEST — verifica locale del 19 ottobre 2026:** il candidato integrato con testi
IT/FUR, Indietro Android, conferma/ricevuta Community, aggiornamento FVG e nuovi
temi delle previsioni ha superato le verifiche sulla TEST `.6` (`300037`) del
Galaxy A52. Il lavoro approvato è integrato in main; le impostazioni speciali
della TEST restano escluse. Questa prova storica precede la AAB ufficiale 300033
e non sostituisce la sua verifica. Evidenze e limiti nel [verbale sul telefono](docs/operations/APP_INTEGRATED_TEST_DEVICE_20261019.md).

[Apri l'app web](https://meteofriul.app) ·
[Sostieni il progetto](https://ko-fi.com/meteofriul)

## Canali — Web verificato il 20 ottobre, candidata Android e Console il 21 ottobre 2026

| Canale | Stato |
| --- | --- |
| Web | `0.1.14` pubblicata su `meteofriul.app`; aggiornamento dalla base approvata in preparazione, non ancora pubblicato |
| API | FastAPI su Cloud Run, chiamata direttamente via HTTPS da Web e Android |
| Android | `0.1.15` (`300033`) nel test interno personale; verificata sul Galaxy Android 14, con difetto di configurazione nativa nel bundle da correggere prima della promozione. [Esito e limiti](docs/operations/RELEASE_0.1.15_STATUS_20261021.md) |
| Google Play | Produzione `0.1.14` (`300031`) nell’ultima lettura del 21 ottobre; `0.1.15` (`300033`) solo nel test interno, una lista con un utente. Sponsor disattivati |
| Landing `meteofriul.it` | Gestita e distribuita da un progetto separato |
| Push | Generazione `play-beta-v1`, App Check in enforce, Android/Web abilitati e lotti Firestore/FCM da 200 elementi |
| Sintesi mattutina | Una notifica quotidiana alle 07:30 `Europe/Rome`, con apertura diretta del Bollettino |
| Sostegno | Link Ko-fi esterno attivo, senza funzioni riservate |

L'app è gratuita e può includere contenuti pubblicitari, promozionali o
sponsorizzati. Il sostegno è volontario e non cambia le funzionalità
disponibili. Ko-fi si apre all'esterno: non sono presenti SDK di pagamento, IAP
o entitlement.

## Funzionalità

| Sezione | Contenuto |
| --- | --- |
| Home | Meteo locale, scena illustrata, sintesi del bollettino, almanacco ed eventi vicini |
| Bollettino | Testo ARPA FVG-OSMER, dati locali, allerte ufficiali e radar nazionale Radar-DPC |
| Territorio | Webcam regionali e segnalazioni community anonime, limitate e moderate |
| Eventi | Eventi locali raccolti da fonti territoriali con collegamento alla fonte |
| Scopri | Località selezionata, ricorrenze, storia, santi, proverbi e contenuti editoriali |
| Impostazioni | Lingua, tema, posizione, preferenze di notifica Web/Android, fonti, crediti e cache |

La ricerca manuale usa un catalogo canonico di 215 Comuni FVG. Con il GPS, il
Comune viene determinato dai confini ISTAT 2026 e la localita visibile viene
accettata solo se corroborata dal catalogo toponomastico IRDAT della Regione
FVG; per esempio Vigonovo resta visualizzato come localita del Comune di
Fontanafredda. La registrazione push conserva Comune, identita canonica della
localita, istante e fascia di precisione del fix; non conserva le coordinate
GPS. Gli Avvisi locali richiedono una posizione recente e precisa e falliscono
chiusi quando tale prova manca; un Comune o una localita canonica scelti
manualmente restano invece un target esplicito finche l'utente non li cambia.
Le fonti ufficiali e di terzi restano attribuite: Meteo Friûl non rappresenta
ARPA FVG, OSMER, Protezione Civile FVG, Regione o gli altri enti citati.

## Impostazioni predefinite

| Impostazione | Valore iniziale |
| --- | --- |
| Lingua | Italiano; friulano selezionabile e persistente |
| Tema | Sistema; chiaro e scuro selezionabili |
| Località web | Udine è il placeholder iniziale finché non viene scelta o rilevata una località |
| Primo avvio Web | Due azioni esplicite: richiesta GPS, poi richiesta notifiche; entrambe rinviabili |
| Posizione automatica | Proposta al primo avvio e attivata solo dopo il consenso del browser o di Android |
| Primo avvio Android | Richiesta GPS, poi richiesta notifiche |
| Allerte ufficiali Web/Android | Preferenza attiva; consegna soltanto alle registrazioni attestate ed eleggibili |
| Avvisi meteo locali Web/Android | Preferenza attiva; richiedono una località canonica e i gate di eleggibilità |
| Sintesi meteo mattutina | Invio quotidiano alle 07:30 per le registrazioni eleggibili; tap verso il Bollettino |

La posizione Android in primo piano usa un percorso rapido a tre stadi: fix
recente validato, fix bilanciato e, solo se necessario, alta precisione. Viene
controllata all'avvio, al ritorno in primo piano e, mentre l'app resta visibile,
al massimo ogni 3 minuti. Per mantenere aggiornato il target degli Avvisi anche
con app chiusa, l'utente puo concedere separatamente `Consenti sempre`:
Android usa allora un geofence di uscita e un controllo periodico WorkManager.
Non esiste un servizio GPS continuo ne' una notifica permanente di posizione.
La scelta manuale di un Comune disattiva la posizione automatica. Sul Web GPS
e notifiche richiedono due gesti separati perché il browser consente di aprire
ciascun prompt di permesso solo dopo un'azione dell'utente; Android mantiene
l'ordine GPS → notifiche.

Le preferenze `Allerte` e `Avvisi` sono entrambe attive per impostazione
predefinita su Web e Android. `Allerte` rende la registrazione eleggibile agli
invii ufficiali regionali e non è una sottoscrizione comunale. Gli `Avvisi`
meteo locali usano una pipeline separata, conservativa e comunale. Android è
ammesso soltanto con una release Play riconosciuta e licenziata; il Web usa il
proprio App ID attestato. Il valore operativo `200` è la dimensione dei lotti
Firestore/FCM, non un tetto al numero complessivo di registrazioni, e non
sostituisce i gate App Check, versione e preferenza. Le allerte mostrate dentro
l'app restano visibili indipendentemente dalle preferenze push.

Il fix preciso viene inviato soltanto nel body HTTPS della route App Check
dedicata e viene risolto subito contro confini ISTAT e localita IRDAT. Firestore
conserva Comune/localita canonici, orario e accuratezza, ma non latitudine o
longitudine GPS. Senza il permesso in background gli Avvisi automatici
falliscono chiusi quando l'evidenza scade; le Allerte ufficiali regionali non
dipendono da questo target.

## Web e Android Play

In produzione il browser usa una base API HTTPS assoluta e chiama direttamente
Cloud Run: Cloudflare Pages serve soltanto gli asset statici. In sviluppo Vite
mantiene il proxy relativo `/api`. La release Android incorpora a sua volta
una base HTTPS esplicita, verificata dal gate AAB insieme al worker nativo.

Nella release Android corrente:

- package: `com.meteofriul.app`;
- orientamento: solo verticale;
- localizzazione: one-shot in primo piano; geofence e WorkManager in background
  soltanto dopo il consenso separato `Consenti sempre`, senza servizio GPS
  permanente;
- splash screen: sfondo Blu Friuli e icona centrale;
- link Ko-fi: aperto esternamente;
- `Segnala`: App Check Debug soltanto nel preflight locale; Play Integrity nella
  release;
- registrazione push: token FCM nativo protetto da App Check/Play Integrity e
  ammesso soltanto per identità Play consentite;
- allerte ufficiali push: implementate con modalità fail-closed
  `off`/`dry_run`/`send`;
- avvisi locali: pipeline meteo separata e deduplicata in modalità `send`, con
  sorgenti ICON e comportamento fail-closed quando manca l'evidenza di
  località richiesta; log sanitizzati con TTL di 14 giorni;
- sintesi mattutina: notifica quotidiana deduplicata alle 07:30
  `Europe/Rome`, con deep link al Bollettino;
- release R8: `minifyEnabled` e `shrinkResources` attivi, profilo ottimizzato e
  `mapping.txt` verificato e archiviato dal gate Play;
- debug WebView: ammesso esclusivamente nel preflight owner e disattivato nella
  release;
- firma e distribuzione Play: configurate; la AAB `0.1.8` è stata accettata nel
  test interno e l'upload resta sempre un'azione esplicita.

Il runtime Web pubblicato usa:

- onboarding in due passaggi espliciti, prima GPS e poi notifiche;
- Firebase Cloud Messaging tramite Firebase Installation ID (FID) e service
  worker locale `/firebase-messaging-sw.js`;
- Firebase App Check con reCAPTCHA Enterprise;
- `Segnala` e mutazioni push abilitate soltanto quando App Check Web è
  configurato nella build e l'App ID Web è autorizzato dal backend;
- preferenze e semantica degli avvisi uguali all'APK.

La chiave pubblica VAPID è stata generata ed è versionata nella configurazione
di produzione; `VITE_FIREBASE_VAPID_KEY` consente un override locale esplicito.
Il codice Web non inizializza
Analytics. La lettura delle segnalazioni community resta pubblica; creazione,
conferma, annullamento, flag di moderazione e registrazione/revoca push sono
fail-closed senza un token App Check valido. La `0.1.8` pubblica è stata
verificata con service worker, registrazione push e API HTTPS correnti.

Le segnalazioni Territorio sono UGC strutturati ed effimeri: otto fenomeni
predefiniti, nessun testo, foto, profilo o nome, posizione pubblica sul Comune
canonico e scadenza di 60 minuti. Il client permette di segnalare il contenuto e
di nascondere localmente una fonte anonima fino al rinnovo della sua `sourceKey`
opaca giornaliera, comunque per non piu' di 24 ore. La chiave genera sul
dispositivo uno pseudonimo friulano amichevole e non espone identificatori
interni. Il `client_id` casuale nasce e resta memorizzato localmente, viene
trasmesso soltanto con le mutazioni e il backend ne conserva chiavi/hash
pseudonimi scoped: non e' un account o una registrazione pubblica del dispositivo,
ma non va descritto come assenza totale di identificatori. Report e fonte interna
scadono dopo 60 minuti, cooldown dopo 45 minuti, conferme entro la scadenza
dell'ultimo report attivo del gruppo, contatori antiabuso entro 2 ore e flag o
blocchi amministrativi eventuali entro 24 ore. La cancellazione fisica TTL
Firestore e' asincrona. Ogni flag nasconde subito il contenuto al segnalante e
crea un record privato temporaneo; non esiste un hide globale automatico basato
sul numero di flag. Un operatore conserva uno strumento privato per un'eventuale
rimozione o blocco temporaneo. Per la prima beta non sono richiesti ne' attivi
job, scheduler o email automatiche di moderazione. Il gate completo e' in
`docs/operations/COMMUNITY_MODERATION_GATE.md`; l'handoff privacy/Data Safety
e' in `docs/operations/COMMUNITY_PRIVACY_DATA_SAFETY_HANDOFF.md`.

Il rango personale e' separato dal feed pubblico effimero. Il backend conserva
un riepilogo pseudonimo per 365 giorni dall'ultima convalida o revoca e
assegnazioni idempotenti per episodio per 365 giorni dal relativo evento:
nessun `client_id` grezzo e nessun punto sono
pubblicati. Un punto va soltanto all'autore dopo corroborazione indipendente;
`Tutto tranquillo` e i votanti sono esclusi, con cap di tre punti al giorno
`Europe/Rome`. Questo nuovo trattamento riapre il gate privacy/Data Safety e
richiede due ulteriori policy TTL `ACTIVE` prima di un rilascio ufficiale.

Le registrazioni push supportano Android e Web/PWA. Il backend opera in modalità
`play_beta`, con App ID separati, generazione `play-beta-v1`, versioni Android
ammesse fino a `0.1.8+300025` e lotti Firestore/FCM da 200 elementi, senza un
tetto complessivo implicito. Il job degli Avvisi locali gira ogni ora, quello
delle Allerte ufficiali ogni due ore e la Sintesi mattutina ogni giorno alle
07:30, sempre nel fuso `Europe/Rome`.
La consegna FCM e il tap verso il Bollettino sono stati verificati con Android
in primo piano, in background e con processo normalmente chiuso, oltre che sul
Web. Un vero `Forza arresto` Android blocca invece FCM finché l'app non viene
riaperta, come previsto dal sistema operativo. Build HTTPS e test E2E restano
gate obbligatori per qualunque nuova release o modifica alla consegna.

Gli aggiornamenti sullo stesso telefono si installano con `adb install -r`,
così da preservare dati applicativi e ID installazione. Una disinstallazione o
la cancellazione dei dati genera un nuovo ID: prima di una nuova registrazione
va rimossa manualmente dal backend la precedente installazione owner.

Le allerte ufficiali della Protezione Civile FVG usano una cache regionale
separata da meteo e bollettino comunali: restano immediatamente visibili dopo un
avvio a freddo o un cambio località fino alla scadenza ufficiale, anche durante
un errore temporaneo delle fonti. Solo una scadenza o una conferma regionale di
assenza allerta può rimuoverle.

Il provider App Check Play Integrity è stato validato attraverso la build
firmata `0.1.8` distribuita nel test interno Google Play. I token Debug sono
individuali per dispositivo e non devono essere salvati nel repository,
nell'APK, nei documenti o negli screenshot.

## Architettura

```text
frontend/          React 19, Vite 8, UI web e wrapper Capacitor
frontend/android/  progetto Android del pilot privato
backend/           API modulare FastAPI
contracts/         fixture e invarianti dei contratti runtime
scripts/           avvio locale, export dati e guardrail di rilascio
firebase.json      Hosting, SPA e rewrite /api
```

Flusso web principale previsto:

```text
Browser -> Cloudflare Pages (asset statici)
Browser -> Cloud Run API -> fonti/cache/Firestore/Firebase
```

Il backend UI3 è autonomo dal monolite storico. La persistenza community in
produzione è fail-closed: non degrada silenziosamente su memoria locale. Le
allerte conservano l'ultimo stato confermato ancora valido e dichiarano sempre
fonte e modalità, senza trasformare un errore in una falsa assenza.

## Sviluppo locale

Prerequisiti:

- Node.js `22.17.1`;
- npm `10.9.2`;
- Python `3.13`;
- PowerShell su Windows;
- Android Studio con JBR 21 soltanto per il wrapper Android.

Preparazione iniziale:

```powershell
python -m venv backend\venv
backend\venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
npm --prefix frontend ci
```

Avvio tecnico ordinario dalla radice del repository:

```powershell
.\scripts\start-dev.ps1 -Restart
```

Servizi avviati:

- frontend Vite: `http://localhost:5173`;
- API UI3: `http://127.0.0.1:8002`;
- health API: `http://127.0.0.1:8002/healthz`.

Comandi utili:

```powershell
.\scripts\start-dev.ps1 -CheckOnly
.\scripts\start-dev.ps1 -Stop
```

Questo launcher è autonomo e non cerca più backend o repository storici in
cartelle adiacenti. Serve ai test tecnici ordinari; non rappresenta la variante
pilota.

Per vedere e validare la app pilota usare invece esclusivamente:

```powershell
.\scripts\start-local-weather-pilot.ps1 -WeatherCloud
```

La pilota è esposta su `http://127.0.0.1:5174/`. Se il reader cloud non è
disponibile, il launcher può usare uno snapshot locale soltanto con un
`-WeatherTestNow` esplicito e compatibile con la finestra dichiarata dallo
snapshot. `STARTUP_PROMPT.md` contiene la procedura breve e il percorso
canonico del progetto.

Il runtime normale usa il flag assente oppure `?uiV3=0`. `?uiV3=1` sostituisce
soltanto la Home con il laboratorio dimostrativo e non va usato per validare i
dati reali.

## Test e qualità

Frontend:

```powershell
Push-Location frontend
npm test
npm run lint
Remove-Item Env:VITE_ANDROID_API_BASE -ErrorAction SilentlyContinue
$env:VITE_API_BASE = "/api"
npm run build
Pop-Location
```

Backend:

```powershell
Push-Location backend
.\venv\Scripts\python.exe -m unittest discover -s tests -v
.\venv\Scripts\python.exe -m compileall -q app
Pop-Location
```

Guardrail dello strumento di preview Hosting:

```powershell
.\scripts\deploy-hosting-preview-rest.contract.tests.ps1
.\scripts\deploy-hosting-preview-rest.tests.ps1
```

La CI esegue test, lint e build frontend; test e compilazione backend; test del
tool di preview Hosting. La compilazione Gradle Android resta un controllo
locale descritto nel runbook del pilot.

## Build e rilascio: web e Android restano separati

`npm run build` e `npm run build:android` scrivono entrambi in `frontend/dist`.
Non distribuire mai sul web un `dist` generato in modalità Android.

Per una build web locale, `VITE_API_BASE` resta `/api`. La build Cloudflare
deve invece ricevere come `VITE_API_BASE` l'URL HTTPS assoluto della revisione
Cloud Run approvata, comprensivo di `/api`; `VITE_ANDROID_API_BASE` non deve
essere presente nell'ambiente Web. Il valore incorporato va verificato nel
bundle prima di collegare il dominio pubblico.

Il deploy di produzione non va eseguito direttamente da `frontend/dist`. Usare
il comando fail-closed, che costruisce in una cartella temporanea, verifica il
binding nel bundle e controlla l'account Wrangler prima di pubblicare:

```powershell
.\scripts\deploy-cloudflare-app.ps1 `
  -ApiBase "https://<TAG>---<SERVIZIO>-<HASH>.a.run.app/api" `
  -ExpectedRevision "meteofriul-api-<SCOPO>-<COMMIT7>" `
  -ExpectedBackendCommit "<COMMIT_BACKEND_40>"
```

Il comando rifiuta `/api`, endpoint Cloud Run non tagged, variabili Android
presenti nella build Web, worktree non committati e account Cloudflare diversi
da quello Meteo Friûl. Prima della build risolve realmente il tag tramite
Google Cloud, verifica revisione attesa, commit backend identificato nel nome,
stato `Ready`, digest dell'immagine e `/api/healthz`; ripete il controllo prima
e dopo il deploy per intercettare spostamenti del tag durante la procedura. Un
deploy reale richiede inoltre che `HEAD` coincida con il branch remoto.
`-BuildOnly` esegue i controlli Cloud Run e del bundle senza pubblicare.

La parità Web richiede inoltre le variabili pubbliche `VITE_FIREBASE_*`
documentate in `frontend/.env.example`. App Check usa la site key reCAPTCHA
Enterprise; FCM Web richiede anche `VITE_FIREBASE_VAPID_KEY`. La chiave VAPID è
configurazione pubblica del bundle, non una credenziale server, ed è versionata
nella configurazione di produzione. Una build incompleta deve restare fail-closed e
mostrare la funzione come non configurata.

La mappa `Territorio` della sola pilota usa CARTO Positron quando la build
riceve `VITE_TERRITORY_CARTO_API_KEY`; senza chiave, o al primo errore di
caricamento delle tessere CARTO, conserva OpenStreetMap come fallback senza
rimontare Leaflet. La chiave CARTO è client-side e deve essere limitata e
monitorata. Le tessere sono richieste direttamente al provider: non introdurre
proxy/cache server, cache applicative o pacchetti offline. Le attribuzioni
CARTO e OpenStreetMap restano visibili sulla mappa.

Per la build Android locale della pilota, configurare la chiave in
`frontend/.env.android-local-pilot.local`. Vite compila quella variante con
la modalità `android-local-pilot`, quindi il file della pilota Web
`frontend/.env.local-pilot.local` non viene caricato automaticamente.

Nella pilota Web, il meteo FVG continua a usare il data-plane autonomo. Le
località italiane esplicitamente fuori FVG usano invece il prefisso Vite
dedicato `/__national-weather-api`, inoltrato all'API Cloud ordinaria senza
l'header della pilota. Il target predefinito è la revisione tagged pubblica
usata dall'app; per un collaudo controllato può essere sostituito con
`VITE_NATIONAL_WEATHER_PROXY_TARGET`, che deve essere una sola origine HTTPS
senza path, query o credenziali. La pilota Android usa direttamente
`VITE_ANDROID_API_BASE`. Questa selezione è preventiva e non introduce fallback
automatici tra provider.

`VITE_TERRITORY_BASEMAP_URL` permette un futuro provider alternativo e ha
precedenza sulla chiave CARTO. Prima di attivare CARTO in produzione vanno
verificati con la chiave reale gli header di cache, le restrizioni Web/Android
e l'assenza di watermark: una risposta grafica con chiave invalida potrebbe
non generare `tileerror` e quindi non attivare il fallback automatico.

Per il solo preflight debug owner, `VITE_ANDROID_API_BASE` deve essere l'URL
HTTPS tagged approvato. Su questa postazione Codex deve eseguire
`npm run android:sync` e Gradle direttamente fuori dal sandbox per evitare i
falsi `EPERM` Windows su `frontend/dist`. Il preflight non e' distribuibile e
non dimostra Play Integrity. La procedura completa e il fallback unico sono in
`ANDROID_PILOT_RUNBOOK.md`.

Per i tester usare esclusivamente il candidato AAB protetto di Google Play,
senza eseguire prima un `android:sync` manuale:

```powershell
pwsh -NoProfile -File .\scripts\build-play-aab.ps1 `
  -ApiBase "https://<TAG>---<SERVIZIO>-<HASH>.a.run.app/api" `
  -CommunityApiBase "https://meteofriul-community-49007668366.europe-west1.run.app/api" `
  -ExpectedRevision "meteofriul-api-<SCOPO>-<COMMIT7>" `
  -ExpectedBackendCommit "<COMMIT_BACKEND_40>" `
  -ExpectedLatestPlayVersionCode <ULTIMO_VERSION_CODE_PLAY_O_0> `
  -BundletoolPath "C:\secure\bundletool-all.jar" `
  -ExpectedBundletoolSha256 "<SHA256_BUNDLETOOL_ATTESO>" `
  -ExpectedUploadCertificateSha256 "<SHA256_UPLOAD_KEY>"
```

La build protetta richiede PowerShell 7 e il supporto
`ConvertFrom-Json -DateKind`; Windows PowerShell 5.1 viene rifiutato prima dei
preflight. Lo script Play costruisce gli asset in `%TEMP%`, incorpora e verifica
separatamente l'API meteo generale e l'API Community ufficiale, mantiene
allineati React e worker nativo dove previsto, verifica tag–revisione–commit,
firma e identita', riserva la versione nel ledger append-only e archivia AAB e
manifesto senza upload automatico. Firebase App Distribution e
`build-private-test-apk.ps1` sono congelati come storico e non sono un canale
tester corrente.

Il gate Community combina un read-back LIVE fresco, nel quale le collection
vuote sono ammesse, con evidenza storica LIVE aggregata e append-only che deve
coprire tutte le dieci collection. I due producer temporanei, il recorder
esplicito e la sequenza seed -> recorder -> cleanup sono documentati in
`release-history/firestore-community-ttl/README.md`; non si assumono report
reali e nessun producer viene eseguito durante la build AAB.
La policy della collection digest puo' restare attiva e vuota come contingenza
dormiente: non prova ne' richiede un job. La build verifica invece il contratto
effimero dell'API pubblica prima della compilazione e prima della copia
dell'artefatto: otto tipi chiusi, Comuni canonici, TTL di 60 minuti, posizione
zonale e nessun identificatore interno o contenuto libero nelle risposte. Dettagli e
diagnostica sono in
`ANDROID_PILOT_RUNBOOK.md` e
`docs/operations/COMMUNITY_MODERATION_GATE.md`.

I rilasci web seguono sempre questa sequenza:

1. commit pulito, inviato al remoto e CI verde;
2. revisione Cloud Run nominata con il commit backend, tagged a 0% traffico e
   collaudata direttamente;
3. risoluzione automatica del tag, revisione `Ready`, digest e health coerenti;
4. build web verificata con lo stesso endpoint assoluto;
5. nuova verifica del tag subito prima del deploy Cloudflare Pages;
6. smoke test di dati, GPS, App Check, `Segnala` e service worker;
7. collegamento di `meteofriul.app` soltanto dopo esito verde;
8. verifica finale del tag, smoke test sul dominio e rollback disponibile.

## Fonti, crediti e privacy

La schermata `Fonti e crediti` collega le principali fonti e licenze: ARPA
FVG-OSMER, Protezione Civile FVG, Open-Meteo, CAMS, Radar-DPC, OpenStreetMap,
NASA, Ostermann e le principali librerie open source.

Restano attività aperte prima di una distribuzione pubblica più ampia:

- pubblicare sulla futura landing il catalogo pubblico completo dei crediti
  delle 215 fotografie comunali già censite nel progetto;
- definire un contatto per rettifiche e richieste di rimozione;
- verificare autorizzazione e provenienza delle immagini Eventi e Webcam;
- verificare e documentare i termini d'uso delle osservazioni recenti e delle
  webcam OSMER, richiedendo un chiarimento scritto se i termini non coprono il
  riuso previsto;
- pubblicare privacy, crediti e disclaimer nella futura landing.

Un link o un'attribuzione non sostituiscono un'autorizzazione quando una fonte
o un'immagine è soggetta a condizioni ulteriori.

## Documentazione operativa

### Runtime e operazioni

- [API UI3](backend/README.md): avvio, route, fonti, Firestore, App Check e test.
- [Osservazioni test chiuso Google Play](docs/operations/PLAY_CLOSED_BETA_OBSERVATIONS.md):
  problemi rilevati e miglioramenti da pianificare durante la beta Alpha.
- [Runbook pilot owner Android/Web](ANDROID_PILOT_RUNBOOK.md): target ammessi,
  matrici di prova, build e gestione delle attestazioni.
- [Wrapper Android](frontend/android/README-PILOT.md): identità, runtime e
  configurazione esclusa dal repository.
- [Hardening Android 0.1.8](docs/operations/ANDROID_0.1.8_TECHNICAL_HARDENING.md):
  obiettivi, gate e stato del lavoro R8.
- [Audit R8 Android 0.1.8](docs/operations/ANDROID_0.1.8_R8_AUDIT.md):
  mappatura nativa, refactoring, prove e artefatti di deoffuscazione.
- [Architettura CSS](CSS_ARCHITECTURE.md): layer, ownership e naming.
- [Contratto API Live](contracts/runtime-api/v1/live/README.md): fixture e
  invarianti delle risposte Territorio.
- [Contratto località](contracts/runtime-api/v1/location/README.md): ricerca e
  reverse geocoding.
- [Runbook del cutover web](PRODUCTION_CUTOVER_RUNBOOK.md): baseline storica,
  rollback e criteri di smoke test; non è lo stato live corrente.
- [Audit automazioni](PRODUCTION_AUTOMATION_AUDIT.md): fotografia operativa
  datata 11 agosto, da riverificare dopo la stabilizzazione.

### Contenuti e asset

- [Contratto Almanacco e Scopri](ALMANAC_DISCOVER_CONTENT_CONTRACT.md).
- [Asset launcher Android](android/launcher-assets/README.md).
- [Asset astronomici](frontend/public/astronomy/README.md).
- [Foto e stemmi comunali](frontend/public/municipalities/README.md).
- [Archivio Ostermann](scripts/data/ostermann-proverbs-1876/README.md).
- [Profili dei santi](scripts/data/saint-profiles/README.md).

Gli altri file `*_AUDIT.md`, i piani di migrazione e i documenti di importazione
sono evidenze datate del percorso di sviluppo. Non devono essere interpretati
come descrizione dello stato corrente senza una nuova verifica.

## Lavoro ancora aperto

- completare privacy/Data Safety e ottenere verdi i gate effimeri e TTL della
  Community, senza attivare il digest dormiente;
- custodire la upload key Play, mantenere aggiornate le dichiarazioni manuali e
  completare le evidenze richieste dalla Play Console;
- decidere e collaudare separatamente qualunque estensione del test Play oltre
  il telefono owner, senza confonderla con un rollout pubblico;
- mantenere l'osservazione delle soglie Open-Meteo e del comportamento
  geofence/WorkManager durante il closed test;
- consolidare coordinate, health e autorizzazioni del catalogo Webcam prima di
  ampliarlo o aggiungere una mappa;
- affrontare edge-to-edge e large-screen in cicli separati dalla pipeline R8;
- completare i gate di fonti, crediti, privacy e contatti.

## Regole di contribuzione

- Leggere e rispettare [AGENTS.md](AGENTS.md) prima di iniziare un intervento.
- Non committare `google-services.json`, keystore, password, token App Check
  Debug, token FCM o Firebase Installation ID. Le chiavi pubbliche di build
  Firebase/reCAPTCHA/VAPID non sostituiscono mai credenziali server.
- Non includere coordinate GPS precise nei log o nei documenti di test.
- Non mascherare un errore di fonte con dati vuoti o attribuzioni diverse.
- Conservare attribuzioni e collegamenti alle fonti nei cambi di UI.
- Tenere separati build web, build Android e deploy backend.
- Partire dal `main` verificato con un ramo dedicato al workstream; più build
  dello stesso lavoro restano sullo stesso ramo.
- Eseguire i controlli pertinenti e promuovere su `main` soltanto dopo la
  verifica, tramite pull request oppure avanzamento esplicitamente autorizzato.
- Prima di una promozione importante, verificare se le affermazioni di stato di
  questo README richiedono un aggiornamento.
