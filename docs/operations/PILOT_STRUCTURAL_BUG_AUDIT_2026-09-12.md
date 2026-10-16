# Audit strutturale dell'app Meteo Eventi Friûl

Data dell'audit: **12 settembre 2026**

Revisione esaminata: **`3f517a8a2104bf1240af6f827793f47daabd54af`** (`3f517a8`)

Stato iniziale: worktree pulito; i soli file aggiunti durante l'audit sono questo
rapporto e prove diagnostiche opt-in.

Perimetro: frontend, backend, variant Android `localPilot`, persistenza locale,
contratti delle API, concorrenza, provenienza e metadati.

Esclusioni rispettate: nessuna modifica al comportamento, nessuna cancellazione
della cache del telefono, nessuna build/installazione Android, nessun deploy,
nessuna modifica a beta, Firebase, cloud, scheduler, frequenze o soglie.

## 1. Fonti e metodo

Sono state usate come mappe iniziali, non come prova conclusiva:

- `PILOT_APP_COMPLETE_ARCHITECTURE_2026-09-12.md`;
- `PILOT_WEATHER_DATA_ARCHITECTURE_2026-09-12.md`;
- `CAMS_MORNING_DIAGNOSIS_2026-09-10.md`;
- i verbali successivi CAMS/UV e dell'episodio di refresh dell'11 settembre.

Le due copie esterne indicate dall'utente sono byte per byte identiche a quelle
versionate nel repository. I loro SHA256 sono rispettivamente
`8A8A117F...EA5B9CA` ed `EF08B37A...E59506`. Le mappe descrivono però revisioni
precedenti (`0342eb0` e `bd68b93`): ogni indicazione rilevante è stata
quindi ricontrollata sui sorgenti di `3f517a8`.

Le conclusioni derivano da quattro tipi di riscontro:

1. lettura del percorso completo chiamante → controller/runtime → cache/API;
2. confronto tra producer, contratti, consumer e presentazione;
3. suite esistenti usate come regressioni;
4. prove diagnostiche separate, escluse dalla raccolta ordinaria, che esprimono
   il comportamento atteso e devono fallire sulla revisione auditata.

I test rossi non sono proposte di implementazione e non sono stati indeboliti
per farli passare. Dimostrano che la revisione corrente non soddisfa il relativo
contratto.

## 2. Topologia effettiva delle build

| Percorso | Meteo principale | Bollettino / radar | Eventi, Live e community | Push / posizione background |
|---|---|---|---|---|
| `localPilot` | reader autonomo ICON + famiglia CAMS + UV | API ordinaria per bollettino, allerte e radar | API ordinaria; scritture community richiedono App Check non disponibile nella variant | FCM e posizione background volutamente disabilitati |
| Android/web ordinari | backend con configurazione attuale Open-Meteo/OSMER | API ordinaria | API ordinaria | disponibili secondo piattaforma, permessi e preferenze |
| percorsi presenti ma non collegati | — | loader `bulletinLocalDataController` e gate OSMER-only remoto non sono usati dalla route attiva | endpoint speciale `pilot-events` non è selezionato dall'API base attiva | — |

Questa distinzione è essenziale: alcuni difetti incidono sulla pilota, altri solo
sulla build ordinaria, altri ancora su componenti backend che anche la pilota
usa fuori dal meteo autonomo.

### Copertura per area funzionale

| Area | Esito dell'audit corrente |
|---|---|
| Home | B02, B04.b, B09 e B12.a; conservazione attivo+candidato protetta |
| Meteo ICON/CAMS/UV | B01, B07 e B08; cambio d'ora e continuità offline protetti |
| Bollettino, allerte e radar | B02/B03; semantica fail-closed delle allerte protetta |
| Eventi | B02/B09; un drift test/UI da decidere, separato dai bug confermati |
| Live e webcam | B02 sulla persistenza; feed e filtri di scadenza protetti |
| Community | B05 e parte di B10; create strict e gate feed protetti |
| GPS e scelta località | B04; latest-wins foreground e selezione manuale protetti |
| Notifiche | B04.c, B06, B10 e B11; claim e rotazione token protetti |
| Scopri, calendario, “I perché”, memoria e territorio | nessun bug aperto dimostrato; selezione/rientro “I perché” protetti |
| Settings e cache dispositivo | B10; nessuna prova di perdita inter-località prodotta dal normale clear esplicito |

## 3. Sintesi ordinata per impatto

Non è stato trovato un difetto S0 che comporti perdita irreversibile certa di
dati utente o compromissione del sistema. Sono confermati i seguenti gruppi.

| ID | Impatto | Ambito | Causa raggruppata |
|---|---|---|---|
| B01 | S1 alto | `localPilot`, CAMS | la revoca famiglia è osservata dal client raw ma non diventa subito autorità durevole del runtime |
| B02 | S1 alto | tutte le build / API usate anche dalla pilota | completamenti tardivi possono sovrascrivere cache e stato più nuovi |
| B03 | S1 alto | backend meteo ordinario | il lookup elimina lo stale e il refresh forzato invalida cache globali, senza generazioni per chiave |
| B04 | S1 alto | GPS, prefetch e push | manca una singola autorità versionata per identità ed evidenza della località |
| B05 | S1 alto | community | controlli e mutazioni non sono nella stessa transazione |
| B06 | S1 alto | push | opt-out/unregister non ha una revisione o tombstone che prevalga su richieste vecchie |
| B07 | S1 alto | `localPilot`, UV | il consumer accetta documenti più deboli del contratto del producer e conflitti same-run |
| B08 | S1 alto | refresh app, soprattutto pilota | token, timeout ed esito aggregato non descrivono un unico episodio |
| B09 | S2 medio | Home/Eventi | `source_unavailable` può sostituire eventi conservati con una lista vuota |
| B10 | S2 medio | `localPilot` | la UI espone funzioni che la variant disabilita tecnicamente |
| B11 | S2 medio | Android ordinario | il tipo push emesso dal backend non è riconosciuto dal deep link frontend |
| B12 | S2 medio | meteo ordinario | età e provenienza si perdono o vengono ringiovanite attraversando i livelli |

S1 significa che il difetto può mostrare dati ritirati, vecchi, di località
diversa, ricreare stato moderato o contraddire una scelta utente. S2 indica
feedback falso, dati incompleti o funzioni inutilizzabili senza una corruzione
necessaria dello stato autorevole.

## 4. Bug confermati aperti

### B01 — Revoche CAMS non propagate e ripristinate immediatamente

**Comportamento atteso.** Quando il puntatore famiglia verificato revoca la corsa
A, A deve cessare di essere presentabile e restare revocata dopo riapertura,
anche se la release B, ICON o il resto del download falliscono.

**Sequenza che viola il contratto.** A è il bundle attivo. Il client valida un
puntatore B con `disabled_run_ids=[A]`, applica la revoca alla propria cache raw e
notifica il callback. La release B resta pending/fallisce, oppure fallisce ICON,
oppure il processo termina prima del bundle finale. Il runtime non riceve una
decisione persistita e può continuare a usare A; al riavvio offline A può
riapparire.

**Causa strutturale.** `weatherV1Client.js:2284-2295` osserva la revoca e
`2395-2420` chiama `onFamilyLatest`, ma cattura e ignora gli errori del callback;
il latest raw viene persistito solo dopo una release valida (`2443-2453`).
`localWeatherV1Adapter.js:855-890` conserva la decisione in una variabile locale
e può uscire per errore ICON a `1082-1107`. Il runtime sanitizza la revoca soltanto
quando riceve un bundle terminale (`localWeatherV1Runtime.js:2069-2074`) e allo
startup ripristina le sole revoche ICON (`1182-1186`, `1827-1840`). Non esiste
un equivalente durevole di `readCachedIconLatest` per la famiglia CAMS.

**Impatto.** Aria/pollini di una corsa esplicitamente ritirata possono rimanere
nella memoria, nella persistenza e nella UI. Non è un semplice problema di dati
stale: una revoca deve prevalere su continuità e fallback.

**Prova.** I test raw esistenti dimostrano che, con release offline/pending, la
decisione di revoca è disponibile ma latest/release persistiti sono assenti;
il test runtime esistente copre soltanto una decisione già inclusa in un bundle
completato. La diagnostica opt-in aggiunta durante questo audit copre il confine
revoca → errore/interruzione → cold restart.

**Correzione minima proposta.** Introdurre un journal monotono, separato dai dati
candidati, per la decisione famiglia verificata; propagarlo con un callback di
safety raw → adapter → runtime, ripristinarlo prima di leggere bundle e rendere
gli errori di invalidazione visibili. Il puntatore senza release non deve mai
diventare candidato dati, ma la sua revoca verificata deve già essere vincolante.

### B02 — Scritture frontend regolate dall'ordine di completamento

**Comportamento atteso.** Per stessa risorsa e località, una risposta A avviata
prima non deve sovrascrivere B avviata dopo e già completata. La protezione deve
valere sia per lo stato React sia per la cache persistente.

**Sequenza che viola il contratto.** Caricamento iniziale A lento; refresh B
rapido. B aggiorna UI e cache, poi A completa e riscrive la cache con dati vecchi.
In Live il contatore `liveLoadSequenceRef` protegge la UI, ma non impedisce al
controller A di scrivere; alla successiva riapertura/offline riemerge A.

**Causa strutturale.** Più effect della stessa route possono chiamare in
concorrenza i controller (`AppRoutes.jsx`: Home `187-300`, Meteo `393-443`,
Bollettino `553-591`, Eventi `635-670`, Live `758-816`). I controller scrivono
prima di restituire e non ricevono una generazione/`AbortSignal` condivisa:
`homeDataController.js:381-510`, `bulletinDataController.js:190-217`,
`bulletinRadarDataController.js:118-125`, `eventsDataController.js:121-181`,
`liveDataController.js:133-206`. `jsonCache.js:37-42` assegna `savedAt` al
completamento, facendo apparire nuova anche una risposta logicamente vecchia.

**Impatto.** Meteo, eventi, bollettino, radar e webcam/community possono
regredire; il difetto può essere invisibile finché non avviene una riapertura.

**Prova riproducibile.** Due test opt-in fanno completare B prima di A. Il radar
termina con il payload A nella cache; Live mantiene B in React ma persiste A.
Entrambi falliscono su `3f517a8`.

**Correzione minima proposta.** Generazione per `resource + location`, condivisa
tra route e controller, oppure `AbortSignal` con commit compare-and-set. La
scrittura persistente deve avvenire solo se la richiesta è ancora l'ultima.
Riutilizzare il modello già presente in `officialAlertsRuntime`.

### B03 — Cache backend distruttiva, refresh globale e assenza di generazioni

**Comportamento atteso.** Superare il TTL fresco deve rendere il dato stale, non
cancellarlo prima che il fallback possa usarlo. Un force su Pordenone non deve
svuotare Udine. Un fetch vecchio non deve ripopolare la cache dopo uno nuovo.

**Sequenze che violano il contratto.** Una voce supera di un secondo il TTL
fresco ma è ancora nella finestra stale; il lookup la elimina, le fonti falliscono
e non resta alcun fallback. In parallelo, il parametro `_` aggiunto dal client
per un force induce il servizio a svuotare dizionari globali di tutte le
località; una richiesta già in volo può poi riscrivere un risultato precedente.

**Causa strutturale.** `forecast_engine.py:88-99` rimuove la voce scaduta al
lookup, mentre i fallback OSMER/forecast la cercano in seguito (`927-986`,
`2187-2296`); `radar_engine.py:183-233` usa lo stesso schema. Gli endpoint
`api/weather.py:69-148` trattano `_` come force e `WeatherService`
(`services/weather.py:43-97`, `126-137`) chiama clear globali in engine quali
`current_engine.py:577-581` e `forecast_engine.py:2377-2383`.

**Impatto.** Buchi evitabili in bollettino/radar/meteo, interferenza tra utenti e
località, picchi di traffico, possibile regressione della cache. Il bollettino e
radar della pilota usano queste API, quindi non è confinato alla build ordinaria.

**Prova.** Prove controllate con OSMER a TTL+1 e fonti indisponibili e forecast a
1801 s con finestra stale 3600 s restituiscono `None` e rimuovono la chiave. Un
test radar esistente maschera il caso usando `force=True`, che salta il lookup
distruttivo. Una suite diagnostica opt-in specifica è allegata all'audit.

**Correzione minima proposta.** Lookup non distruttivo fino alla fine della
finestra stale; bypass/invalidation per chiave e provider invece di `.clear()`;
single-flight/generazione per chiave e commit compare-and-set.

### B04 — Identità ed evidenza di località senza autorità/versione unica

Questo gruppo raccoglie quattro sintomi collegati dallo stesso difetto di
contratto: coordinate, Comune visibile, località persistita e destinazione push
non condividono una revisione monotona e una regola di identità unica.

#### B04.a — Split-brain GPS sotto soglia

`App.jsx:841-874` aggiorna sempre `activeLocationRef` e persistenza ma aggiorna
lo stato React solo se `haveDeviceCoordinatesChanged` supera 500 m
(`deviceLocation.js:192-240`). Movimenti L0→L1→L2 ciascuno inferiori a 500 m
rispetto al riferimento mobile possono lasciare la UI a L0 mentre ref/cache/push
sono a L2, anche quando L0→L2 supera 500 m.

Impatto: chiavi cache, intestazione, richieste e target push possono descrivere
località diverse. Il test diagnostico cumulativo fallisce.

#### B04.b — Prefetch di un Comune vicino rietichettato

`homeDataController.js:106-120` considera compatibile un prefetch entro 5 km
senza far prevalere nome/ISTAT disponibili; `155-212` rietichetta quindi, per
esempio, un payload Porcia come Pordenone e lo salva sotto la chiave Pordenone.
Il difetto riguarda il prefetch ordinario, non il reader autonomo localPilot.
Il test diagnostico Pordenone/Porcia fallisce.

#### B04.c — Evidenza push arrival-wins e registrazione non correlata

`repositories/push.py:504-563` aggiorna la destinazione senza confrontare
`captured_at`: una posizione vecchia, arrivata tardi da un worker distinto, può
sostituire quella nuova. `/register` (`306-342`) può inoltre dichiarare modalità
automatica e Comune usando nome, accuratezza e timestamp ma senza coordinate;
il contratto frontend/backend non consente il reverse check che `/location`
esegue. Una prova newer Udine → older Pordenone termina erroneamente a Pordenone.

#### B04.d — Timestamp browser futuro accettato

`deviceLocation.js:255-278` porta a zero un'età negativa e accetta quindi anche
timestamp arbitrariamente futuri; il percorso Capacitor, invece, applica già un
limite di skew. Il test con data molti anni nel futuro restituisce `ok:true`.

**Correzione minima proposta per il gruppo.** Separare “ultima evidenza GPS” da
“baseline che decide il cambio visibile”; usare identità ISTAT/nome canonica
prima della distanza; introdurre una revisione monotona condivisa e confronto
atomico di `captured_at`; trasmettere coordinate transitorie nel register
automatico o mantenerlo non eleggibile fino a `/location`; applicare lo stesso
future-skew su browser e Capacitor.

### B05 — Mutazioni community con controlli fuori transazione

**Comportamento atteso.** Confermare, segnalare o annullare deve operare sullo
stesso report e sulla stessa generazione controllati, senza ricreare documenti
rimossi né cancellare cooldown successivi.

**Sequenza violante 1.** Il service legge il report; la moderazione lo elimina;
una conferma tardiva esegue `merge=True` e ricrea un documento parziale, privo
anche del TTL originario. Lo stesso schema interessa il flag.

**Sequenza violante 2.** Due undo del report A superano il pre-check. Il primo
elimina A e cooldown; viene creato B con un nuovo cooldown; il secondo undo di A
elimina alla cieca il cooldown condiviso di B.

**Causa strutturale.** I pre-check sono in `services/community.py:495-586`, fuori
dalle transazioni di `repositories/community.py:390-810`.
`update_confirmation_strict` non legge report/moderazione nella propria
transazione e il service materializza con merge; `delete_report_and_cooldown_strict`
esegue un batch cieco senza confrontare il `report_id` del cooldown.

**Impatto.** Report moderati possono riapparire come “fantasmi”, contatori e gate
possono divergere, e un client può inviare un nuovo report prima del cooldown
previsto.

**Prova.** Due test backend opt-in ricreano il report cancellato e cancellano il
cooldown del report nuovo; entrambi falliscono su `3f517a8`.

**Correzione minima proposta.** Portare lettura di report, group gate,
moderazione, ownership e scadenza nella stessa transazione della mutazione;
usare update condizionale, non merge-set; cancellare il cooldown solo se contiene
il `report_id`/generation atteso.

### B06 — Revoca push senza barriera durevole

**Comportamento atteso.** Una revoca permesso o unregister più recente deve
prevalere su ogni register vecchio ancora in volo.

**Sequenza che viola il contratto.** Un register parte, poi l'utente revoca o
esegue unregister; la richiesta precedente arriva dopo e ricrea il dispositivo.
Sul native, il resume aggiorna la revisione solo quando il permesso è granted e
il relativo effect esce se non è granted senza inviare unregister.

**Causa strutturale.** I contratti register/unregister non hanno una state
revision; `repositories/push.py:306-502` non conserva una tombstone confrontabile.
La coda React serializza solo una singola istanza dell'app. Il record backend
attivo non ha un TTL che compensi il problema.

**Impatto.** Una preferenza/permissione revocata può non diventare stato
autorevole backend; il target può essere ricreato e restare eleggibile.

**Prova.** Il test diagnostico register → unregister → vecchio register termina
con il device nuovamente presente.

**Correzione minima proposta.** Unregister su permission denied, arresto del
worker background e revisione monotona/tombstone atomica comune a register,
location e unregister.

### B07 — Contratto UV più debole nel consumer che nel producer

**Comportamento atteso.** Il client deve accettare esclusivamente lo stesso
schema e la stessa identità che il producer pubblica; due documenti diversi con
lo stesso run devono essere un conflitto, non un aggiornamento ordinario.

**Sequenza che viola il contratto.** Un documento con `source='NOT CAMS'`, chiavi
extra, `run_at` non canonico, punto fuori FVG o griglia duplicata supera
`validateUvForecastDocument`; un documento mutato con lo stesso run può
sostituire quello attivo. La card lo attribuisce comunque a CAMS.

**Causa strutturale.** Il producer `experiments/weather_autonomy/uv_cloud.py:149-210`
impone chiavi esatte, source, mezzanotte UTC, griglia FVG e unicità e rifiuta
same-run con byte diversi. `uvForecast.js:4-16` controlla solo una parte; il
runtime `uvForecastRuntime.js:140-159` rifiuta solo run strettamente più vecchi.

**Impatto.** La pilota può persistere e mostrare dati UV con provenienza o area
non verificata, etichettandoli come Copernicus CAMS.

**Prova.** La prova Node con source arbitraria, run alle 00:30, chiave extra e 72
righe viene accettata. I casi di mutazione sono nella diagnostica meteo opt-in.

**Correzione minima proposta.** Contratto condiviso o generato producer/consumer,
schema esatto e identità/hash immutabile del run; conflitto same-run fail-closed.

### B08 — Il refresh non rappresenta un singolo episodio

**Comportamento atteso.** Il messaggio del gesto deve riferire in modo univoco
all'episodio avviato e distinguere completamento iniziale, supplemento CAMS,
allerte e sovrapposizioni. Un token chiuso non deve essere rigiocato dopo una
navigazione.

**Sequenze che violano il contratto.** Il feedback generale scade a 8 s mentre
CAMS ha un budget complessivo di 20 s e può promuovere a 12 s; il gesto mostra
“Fallito” pur con dati aggiornati. Viceversa la route può dichiararsi conclusa
sull'ICON iniziale prima del CAMS. Un gate allerte non autorevole produce
“Fallito” anche se CAMS riesce. Infine `refreshRequestToken` non viene consumato:
dopo il remount per tab/località la nuova route può interpretare il vecchio token
come un nuovo force.

**Causa strutturale.** `runtimeRefreshPolicy.js:23-25` e `App.jsx:531-572` usano
8 s; `localWeatherV1Adapter.js:31,855-890` usa 20 s per CAMS. Il gate generale
unisce esiti eterogenei (`runtimeRefreshPolicy.js:99-114`). Il resolver viene
rimosso ma il token resta (`App.jsx:215-216,303-317,562-571`); il remount è
legittimo perché la route è keyed per tab/località (`AppRoutes.jsx:1094-1098`).

**Impatto.** Feedback falso, force duplicati, invalidazioni backend inutili e
possibili concorrenze B02/B03. Non dimostra che aria/pollini abbiano fallito.

**Prova.** `App.manualRefreshEpisode.test.jsx` riproduce timeout a 8 s con CAMS
promosso a 12 s, vero timeout CAMS a 20 s, gate allerte separato e gesto
sovrapposto. Nella prova reale del Samsung del 12 settembre, tutte le richieste
osservate erano HTTP 200 e CAMS veniva promosso, ma il pull mostrava “Fallito”
dopo circa 2,42 s. Il ramo preciso dell'episodio storico non è conservato.

**Correzione minima proposta.** Modellare un episodio `{id, active, componenti}`;
consumare/chiudere il token una sola volta; distinguere nell'esito route, allerte
e supplementi; non usare il timeout UI come cancellazione del lavoro valido e
non prolungare artificialmente l'interfaccia per nascondere il problema.

### B09 — `source_unavailable` azzera gli eventi conservati

**Comportamento atteso.** “Sorgente indisponibile” non equivale a “sorgente
consultata e nessun evento”: la cache precedente deve restare visibile come
stale.

**Sequenza che viola il contratto.** Home ha eventi in cache; il backend torna
`events=[]`, `cache.status=source_unavailable`; il controller salva e presenta
lista vuota come fresh. La pagina Eventi conserva il dato solo quando riceve
esplicitamente `pilot=true`, mentre Home non applica il guard neppure in pilota.

**Causa strutturale.** Il backend distingue correttamente `source_empty` e
`source_unavailable` (`services/events.py:95-110`, `events/engine.py:6147-6166`),
ma `homeDataController.js:440-510` perde la distinzione;
`eventsDataController.js:130-137` la usa solo nel ramo pilot.

**Impatto.** Apparente sparizione degli eventi durante un guasto della fonte.

**Prova.** Il test opt-in con evento cached e risposta unavailable fallisce:
ritorna `fresh`, `fromCache:false`, `items:[]`.

**Correzione minima proposta.** Unificare la semantica dei due status nel
controller condiviso: unavailable conserva stale in ogni build; source_empty è
l'unico vuoto autorevole.

### B10 — Capability `localPilot` non allineate alla UI

**Comportamento atteso.** Una funzione disabilitata dalla variant deve essere
nascosta o esplicitamente read-only, non presentata come azione completabile.

**Sequenza che viola il contratto.** La pilota mostra azioni community, flusso
GPS background e toggle push. La variant non installa App Check, rimuove il
permesso background e restituisce `null` per l'adapter push. Le azioni arrivano
quindi a errori inevitabili o a prompt senza capacità corrispondente.

**Causa strutturale.** Il capability state è dedotto in punti separati:
`firebaseAppCheckAdapter.js:24-70`, installer no-op
`android/app/src/localPilot/.../PilotAppCheckProviderInstaller.java`, manifest
localPilot e `nativePushAdapter.js:92-106`. Settings disabilita solo lo stato
`readOnly`, che l'assenza plugin non imposta.

**Impatto.** Esperienza contraddittoria e false aspettative nella sola pilota.

**Prova.** Una diagnostica incrocia gli adapter reali: App Check è presente come
bridge ma il token termina in `firebase_app_check_not_configured`/
`firebase_app_check_token_failed`, il push localPilot restituisce correttamente
plugin nullo, mentre `isPilotCommunityReportingAvailable()` restituisce ancora
`true`. Il test fallisce sul contratto `reporting=false`. Prompt e toggle restano
evidenza statica: testarli oggi richiederebbe mock autoreferenziali in assenza di
un capability model unico.

**Correzione minima proposta.** Un unico oggetto capability derivato dalla
variant e consumato da startup, Settings, Live e community; mantenere le
disabilitazioni tecniche esistenti.

### B11 — Deep link della notifica meteo non riconosciuto

**Comportamento atteso.** Il tap su una notifica locale meteo apre Bollettino.

**Sequenza che viola il contratto.** Il backend invia
`type='local_weather_notice'`; il parser frontend non lo riconosce e restituisce
`null`; `App.jsx` non cambia tab.

**Causa strutturale.** Producer in `services/local_notice_delivery.py:714-726` e
allowlist consumer in `pushDeepLink.js:3-8` non condividono il contratto.

**Impatto.** Android ordinario apre l'app nella schermata corrente. Non riguarda
la pilota, dove push è volutamente disabilitato.

**Prova.** Il test diagnostico con il payload reale atteso fallisce
`null !== {tab:'bulletin'}`.

**Correzione minima proposta.** Aggiungere il tipo al contratto condiviso e una
regressione producer/consumer; non introdurre un alias solo in UI senza testare
il payload backend.

### B12 — Freschezza e provenienza perse nel meteo ordinario

#### B12.a — Cache Home arbitrariamente vecchia marcata non stale

`HOME_INITIAL_STALE_MAX_AGE_MS` è `Infinity` e `readInitialHomeData` forza
`isStale:false` (`homeDataController.js:24-25,292-327`). Un record di 24 ore è
presentato come cache corrente e può alimentare anche ranking eventi e almanacco.
La continuità è corretta; sono errate etichetta e uso contestuale senza limite.
Il test diagnostico fallisce mostrando `status:'cache', isStale:false`.

#### B12.b — Bootstrap backend ringiovanisce i child

`services/weather.py:126-163` dichiara il bootstrap top-level fresh e usa l'ora
di packaging anche se current/forecast child sono stale. Il consumer conserva
il raw ma non deriva uno stato aggregato coerente.

#### B12.c — Pollini ordinari disponibili ma valori/provenienza perduti

Il backend ordinario acquisisce variabili dall'endpoint Open-Meteo AQ e restituisce
un `pollen_data` generico privo di source/run/valid/unit
(`current_engine.py:141-194`, `contracts/weather.py:96-104`).
`bulletinLocalViewModel.js:457-488` calcola le entries ma restituisce available
senza `values`; il view model successivo accetta solo un array e produce
`available` con `values=[]`. `WeatherCamsCard` viene comunque montata e mostra
un footer CAMS hardcoded.

**Impatto del gruppo.** Dato vecchio presentato come corrente, metadati aggregati
inaffidabili e card pollini formalmente disponibile ma priva delle concentrazioni;
attribuzione non dimostrabile dal payload.

**Correzione minima proposta.** Propagare `savedAt`/stato del peggiore child;
marcare stale e impedire l'uso contestuale oltre un TTL dichiarato; tipizzare
pollini con source/provider/run/valid/unit e propagare davvero i valori, oppure
non presentare la card CAMS nel percorso ordinario.

## 5. Difetti già corretti da proteggere

Questi comportamenti non sono bug aperti su `3f517a8`; devono restare nella suite
quando si correggono i problemi sopra.

| Area protetta | Stato verificato |
|---|---|
| CAMS attivo + candidato | staging, rilettura e promozione atomica; un candidato incompleto o un errore di storage non svuota l'attivo (`8353705` e commit successivi) |
| risposta vecchia whole-bundle | il rifiuto di A non cancella B più nuovo (`64241f3`) |
| ICON/CAMS indipendenti | il primo rendering non attende CAMS; un supplemento CAMS non rinnova o cancella ICON |
| cambio d'ora CAMS | viene scelto dalla serie persistita il campione pertinente all'ora reale del completamento; oltre la copertura resta solo un `last_known` timestampato, non un valore inventato |
| età CAMS | 24 h di freschezza e 30 h di adottabilità non sono confuse con la disponibilità di una serie attiva già verificata; il difetto dell'11 settembre non era la soglia 30 h |
| UV attivo + candidato | download fallito, notte o fine copertura non cancellano la serie verificata (`e885143`) |
| allerte ufficiali | `unavailable` non diventa `inactive`; solo `inactive_confirmed` cancella; latest-wins protegge risposte tardive |
| route/località | la key `${tab}:${locationCacheKey}` rimonta le view al cambio località e impedisce stato React trasversale tra Comuni |
| “I perché” | la domanda scelta resta aperta finché si rimane in Scopri e torna quella giornaliera dopo uscita/rientro |
| GPS foreground | la generazione locale impedisce a una lettura foreground vecchia di vincere su una nuova; la selezione manuale è serializzata |
| creazione community | la transazione strict legge blocchi, gate, conferme, cooldown e rate limit prima di creare |
| feed community | gate globale e scadenza filtrano report/gruppi; la scadenza feed non viene presentata come cancellazione fisica |
| invio push | il claim rilegge device, enrollment, preferenze, target, modalità ed evidenza; il CAS per token invalido protegge una rotazione nuova |

## 6. Ipotesi da verificare

Questi punti hanno indizi concreti ma manca ancora una prova end-to-end sufficiente.
Non sono conteggiati tra i bug confermati.

### H01 — Dedup localPilot per ISTAT e punto solare del primo caller

`localWeatherV1Runtime` deduplica in-flight per identità comunale, mentre adapter
e route distinguono coordinate precise per alba/tramonto. Due richieste nello
stesso Comune ma con punti diversi potrebbero condividere la presentazione solare
del primo caller. Serve un test concorrente, vicino ad alba/tramonto, con due
coordinate verificate nello stesso ISTAT.

### H02 — Provenienza reale dei pollini Open-Meteo

È confermato che il payload non prova la fonte e che la UI hardcode CAMS; manca
un contratto/provider statement conservato per affermare che ogni risposta
Open-Meteo usata qui non derivi da CAMS. La misattribuzione effettiva resta
quindi ipotesi; il difetto di provenienza è già B12.c.

### H03 — Revoca consenso durante il worker Android

Il worker controlla il consenso all'avvio, ma non è ancora provato con un test
WorkManager che una revoca durante una richiesta impedisca sempre l'upload
finale. Serve un test strumentato con barriera prima dell'invio.

### H04 — Cache reverse geocoding per cella

La chiave non include accuratezza/versione del resolver, ma il chiamante attivo
usa attualmente `cacheEnabled:false`. È un rischio disconnesso, non un bug utente
attuale.

### H05 — Ramo storico preciso del “Fallito” sul Samsung

Il contratto B08 e il messaggio errato sono verificati; non è conservato il token
o log console che distingua nell'episodio reale gate allerte, timeout, skipped o
altro componente. Non va attribuito retroattivamente a CAMS.

### H06 — Compatibilità legacy dei termini community

Il percorso di conferma senza termini è limitato a una forma/versione Play
legacy specifica. Manca una decisione prodotto sulla data di rimozione; non è
possibile classificarlo come bug solo dal codice.

## 7. Scelte intenzionali che non sono bug

- La variant `localPilot` usa il meteo autonomo ICON/CAMS/UV e non Open-Meteo per
  quel percorso. Bollettino, radar, eventi e Live restano API ordinarie.
- Push FCM, posizione background e App Check sono disabilitati nella pilota.
  L'incoerenza UI è B10; la disabilitazione tecnica non è un guasto.
- Il percorso OSMER-only remoto è presente ma non collegato perché il relativo
  gate richiede header/policy/loopback che Android remoto non soddisfa. Diventa
  bug solo se viene stabilito il requisito “zero Open-Meteo in ogni schermata”.
- I report community scadono dal feed dopo 60 minuti; ciò non significa che ogni
  dato sia fisicamente cancellato allo stesso istante.
- “Nascondi fonte” è personale. La chiave fonte ruota giornalmente, quindi la
  durata effettiva può essere inferiore alle 24 ore attraversando la rotazione;
  la UI lo dichiara.
- Il flag personale e l'oscuramento pubblico da moderazione sono operazioni
  diverse.
- Non si usano topic FCM: l'outbox è per dispositivo.
- Le coordinate raw di `/location` sono usate transitoriamente per la
  riconciliazione e non persistite; viene conservato il target canonico.
- La soglia CAMS delle 30 ore è una policy deliberata e non è stata modificata.
  Non spiega da sola l'episodio delle 05:22 con run di circa 27 ore.
- La modalità “fuori FVG: solo meteo” e le allerte nazionali sono proposte di
  prodotto non ancora implementate, non regressioni del codice corrente.
- Radar espone più prodotti del sottoinsieme oggi visualizzato: finché il
  requisito UI resta SRI, l'assenza di SRT1 non è un bug.

## 8. Drift di test o contratto da decidere

`EventsView.test.jsx > shows available descriptions in the list without fetching
a detail` pretende `.mf-events-card__excerpt`, ma la lista corrente mostra la
descrizione nel dettaglio e non renderizza l'excerpt. Il test e la UI furono
introdotti nello stesso cambiamento già incoerenti. Non è corretto dichiarare
automaticamente bug la UI o correggere il test: serve scegliere se ripristinare
l'anteprima nella lista oppure aggiornare il contratto.

Il timeout di `AppRoutes.camsEpisode.test.jsx` è comparso una volta nella suite
completa sotto carico; la stessa prova passa sia nella sessione mirata da 110
test sia isolata. È instabilità temporale del test da rendere meno dipendente dal
carico, non prova di un fallimento CAMS reale.

## 9. Prove diagnostiche opt-in aggiunte

Le configurazioni dedicate impediscono che i rossi intenzionali contaminino la
suite ordinaria.

### Frontend strutturale generale

```powershell
cd frontend
npx vitest --configLoader native --config structural-audit.diagnostic.config.js run
```

Esito: **0 superati, 7 falliti attesi, 0 saltati**.

Contratti: deep link meteo, schema/identità UV, startup weather stale, prefetch
altro Comune, ritenzione eventi unavailable, radar latest-wins, persistenza Live
latest-wins.

### Frontend social/GPS

```powershell
cd frontend
npx vitest --configLoader native --config social-geo-structural-audit.diagnostic.config.js run
```

Esito: **0 superati, 2 falliti attesi, 0 saltati**.

Contratti: movimento cumulativo rispetto alla baseline visibile e rifiuto di un
timestamp browser oltre il future skew.

### Backend community/push

```powershell
cd backend
python -m pytest -q -c pytest.social-geo-diagnostics.ini
```

Esito: **0 superati, 4 falliti attesi, 0 saltati**.

Contratti: report cancellato non ricreato, cooldown nuovo non eliminato da undo
vecchio, evidenza posizione push monotona, unregister dominante su register
logicamente precedente.

### Revoche CAMS

```powershell
cd frontend
npx vitest --configLoader native --config cams-family-revocation.diagnostic.config.js run
```

Esito: **0 superati, 2 falliti attesi, 0 saltati**, con **6 soft assertion**
pertinenti. Il puntatore raw B, revisione 2, revoca correttamente A; tuttavia
risultato runtime, bundle persistito e cold read mantengono tutti A come
`available`, sia mentre la release B è pending sia dopo fallimento di release e
ICON.

### Ciclo di vita del refresh

```powershell
cd frontend
npx vitest --configLoader native run --config weather-refresh-lifecycle.diagnostic.config.js
```

Esito: **0 superati, 1 fallito atteso, 0 saltati**. Un token già concluso viene
osservato tre volte attraversando Home → Bollettino → Home, anziché una sola.

### Cache radar backend nella finestra stale

```powershell
cd backend
py -3 -m pytest -p no:cacheprovider -c pytest.weather-stale-diagnostics.ini -q
```

Esito: **0 superati, 1 fallito atteso, 0 saltati**. A
`RADAR_CACHE_TTL + 1 s`, ancora prima di `RADAR_STALE_TTL`, un errore di rete
produce `available:false` invece di riusare il payload stale.

### Contratto meteo ordinario

```powershell
cd backend
python -m pytest -q -c pytest.ordinary-weather-contract-diagnostics.ini

cd frontend
npx vitest --configLoader native --config ordinary-weather-contract.diagnostic.config.js run
```

Esito backend: **0 superati, 1 fallito atteso, 0 saltati**; il bootstrap dichiara
`fresh` con child current `stale`.

Esito frontend: **0 superati, 2 falliti attesi, 0 saltati**, con 3 assertion
pertinenti; concentrazioni, provider e `validAt` vengono persi e la UI dichiara
CAMS/Copernicus senza provenienza nel payload.

### Capability della pilota

```powershell
cd frontend
npx vitest --configLoader native --config pilot-capability-mismatch.diagnostic.config.js run
```

Esito: **0 superati, 1 fallito atteso, 0 saltati**. L'invio community è
dichiarato disponibile nonostante l'adapter App Check reale dimostri che la
variant non può produrre il token richiesto.

In totale l'audit consegna **21 test diagnostici rossi di primo livello**, più
le **8 verifiche soft** interne ai due scenari CAMS e al contratto di propagazione
dei pollini. I file diagnostici restano fuori dai glob ordinari.

## 10. Regressioni eseguite

### Frontend mirato

```powershell
cd frontend
npx vitest --configLoader native run src/app/App.manualRefreshEpisode.test.jsx src/app/AppRoutes.activeCandidate.test.jsx src/app/AppRoutes.camsEpisode.test.jsx src/services/pushDeepLink.test.js src/features/home/homeDataController.test.js src/features/bulletin/bulletinRadarDataController.test.js src/features/bulletin/bulletinDataController.test.js src/features/events/eventsDataController.test.js src/features/live/liveDataController.test.js src/features/discover/DiscoverView.test.jsx
```

Esito: **10 file, 110 test superati, 0 falliti, 0 saltati**.

Riesecuzione isolata del test CAMS che aveva avuto timeout sotto carico:
**1/1 superato**.

### Frontend completo

```powershell
cd frontend
npm test
```

Esito: **444 file superati, 2 falliti, 4 file saltati; 3499 test superati,
2 falliti, 11 saltati, totale 3512**.

I due fallimenti sono i due casi della sezione 8: test Eventi incoerente e timeout
CAMS occasionale. I **11 saltati sono esclusivamente test live opt-in**: non sono
stati eseguiti e non sono conteggiati come prova.

### Frontend social/GPS correlato

Set mirato su posizione, App Check, Live, startup Android, registrazione push e
selezione località: **7 file, 71 test superati**. La suite ordinaria specifica
`deviceLocation` è stata rieseguita anche dopo l'aggiunta diagnostica: **22
superati**.

### Backend social/push correlato

Le suite di repository/service community, push e location hanno prodotto **152
test superati e 56 subtest superati**. Tre casi separati non sono partiti nel
runtime locale per incompatibilità della fake con
`google.cloud.firestore_v1.base_query.FieldFilter`; è un limite dell'ambiente
di test, non un esito live né una prova di correttezza. Tre regressioni repository
selezionate sono state poi eseguite con il relativo harness: **3 superate**.

### Meteo/CAMS correlato

Le sessioni mirate eseguite sullo stato auditato comprendono runtime/adapter,
generazioni, recovery, app/presentation e contratti meteo: **304 + 13 + 51 test
superati**, senza fallimenti nelle sessioni mirate. Un ulteriore gruppo
App/allerte ha dato **35/35**; backend allerte **27 test + 8 subtest superati**.

Queste sono prove controllate con clock, fake storage e rete simulata. Non sono
presentate come verifica sul telefono.

### Lint

```powershell
cd frontend
npm run lint
```

Esito: **superato, nessun errore o avviso**.

## 11. Limiti dell'audit

- Non è stata eseguita rete live provider, acquisizione ADS o lettura cloud
  nuova. Gli 11 test live sono rimasti disabilitati.
- Non è stata modificata o letta distruttivamente la cache del Samsung.
- Le prove di concorrenza dimostrano i meccanismi e due controller
  rappresentativi; l'elenco dei controller affetti deriva poi dal medesimo
  schema di commit senza generation verificato nel codice.
- La validità legale dei testi, le basi giuridiche e i tempi di conservazione
  richiedono valutazione legale e non sono oggetto di questo audit tecnico.
- Nessun numero di test superati è usato come spiegazione dell'episodio reale
  dell'11 settembre.

## 12. Ordine di correzione raccomandato

Ogni voce dovrebbe avere un commit separato per responsabilità e una regressione
che dal rosso diventa verde, senza migrazioni generali preventive:

1. B01, revoche CAMS come autorità durevole di safety;
2. B05 e B06, transazioni community e barriera opt-out push;
3. B04, identità/versione della località e dell'evidenza;
4. B02 e B03, generazioni e cache non distruttive frontend/backend;
5. B07, contratto UV condiviso;
6. B08, ciclo di vita e feedback del refresh;
7. B09, semantica eventi unavailable;
8. B10 e B11, capability UI e deep link;
9. B12, freschezza/provenienza del percorso ordinario.

Prima di qualunque distribuzione sul Samsung, la suite attivo+candidato, cambio
d'ora, cambio località, riapertura offline, revoche e salvataggio interrotto deve
restare integralmente verde. Nessuna delle correzioni richiede di cambiare la
soglia delle 30 ore, gli scheduler o le frequenze.
