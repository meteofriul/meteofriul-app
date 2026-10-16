# Meteo Friul UI3 API

Nuova API modulare della UI3. Non importa il monolite storico e non espone
automaticamente route che la nuova app non usa.

## Sviluppo locale

```powershell
python -m venv venv
.\venv\Scripts\pip.exe install -r requirements-dev.txt
.\venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8002
```

Il frontend mantiene `/api` come base relativa. Durante la migrazione Vite
instrada `/api/location/*` a questa API e le famiglie non ancora trasferite al
backend storico sulla porta 8001.

Anche `/api/live/*`, `/api/community/*`, `/api/local/events`,
`/api/event-images/*`, `/api/weather/current`, `/api/weather/forecast`,
`/api/weather/bootstrap`, `/api/weather/official-alerts` e
`/api/weather/radar` appartengono alla nuova API. Le webcam
usano il manifest locale curato e, quando configurato, un manifest remoto con
fallback locale. Le segnalazioni community usano memoria nel profilo di
sviluppo e non inviano coordinate precise: il dato pubblicato e' ricondotto al
centro del Comune selezionato.

Eventi conserva le sei fonti gia collaudate, raccoglie anche i Comuni entro
20 km dalla localita attiva e applica poi filtri, deduplica, ranking e cache.
Le localita vicine vengono lette dal catalogo canonico dei 215 Comuni FVG;
non viene scaricato indiscriminatamente l'intero feed regionale.

Il Bollettino mantiene ARPA FVG OSMER come fonte primaria. Il motore importa
soltanto il parser, l'interpretazione e la composizione previsione necessari;
Open-Meteo completa date e temperature quando disponibile, ma non sostituisce
il testo o la struttura ufficiale. Le allerte usano come segnale positivo il
canale ufficiale `@ProtCivileFVG`, accettano soltanto PDF CFD scaricati e
verificati e confrontano la permanenza dei documenti sul pannello PCR
ARPA/OSMER. Un errore di rete restituisce uno stato `unavailable`, non una falsa
conferma di assenza. Soltanto un'allerta attiva ancora valida può essere servita
dalla cache dopo un refresh fallito.

Le condizioni locali mantengono la precedenza delle stazioni OSMER quando una
stazione coerente e disponibile. Open-Meteo completa i campi locali e
l'evoluzione oraria; CAMS fornisce la stima pollinica dichiarata. `bootstrap`
compone in parallelo condizioni correnti, previsione OSMER e allerte ufficiali,
senza importare audit o processi del monolite storico. Registrazione dispositivi,
push ufficiale Android e riconciliazione delle fonti ufficiali appartengono a
moduli UI3 dedicati e restano disabilitati per impostazione predefinita. Il
codice sperimentale delle soglie locali è isolato e non viene eseguito da job o
workflow.

Il radar espone soltanto metadati prodotto verificati e il contratto tile WebP
Radar-DPC V2. Le immagini restano servite dalla fonte e il client riproduce la
scala cromatica SRI ufficiale; il vecchio contratto WMS rimane nel payload solo
per compatibilita con i client gia installati. Un errore radar non modifica
Bollettino o allerte. Le richieste REST dichiarano l'origine come richiesto da
Radar-DPC; la cache condivisa evita polling ridondante e l'ultima sequenza resta
disponibile per non piu di trenta minuti.

Lo script `scripts/start-dev.ps1` usa `backend/venv` quando presente e il
Python di sistema come fallback. Non usa il virtualenv del backend storico per
avviare questa API.

## Dati Comuni

`app/data/fvg_municipalities.json` e' generato dalla fonte canonica UI3:

```powershell
node scripts/export-fvg-location-data.mjs
```

La ricerca manuale combina il catalogo locale FVG, mantenuto per primo, con
risultati nazionali italiani ottenuti dal geocoder pubblico Nominatim di
OpenStreetMap. Le risposte esterne sono filtrate fail-closed sul codice Paese
`IT`; il client usa un `User-Agent` identificabile, cache bounded e una corsia
serializzata di almeno un secondo condivisa con il reverse geocoding. La
ricerca localita' non dipende da Open-Meteo e non costituisce un'eccezione al
kill switch `METEOFRIUL_OPEN_METEO_ENABLED` della pilota meteo.
Dentro la regione il reverse runtime e' interamente offline: determina il Comune
esclusivamente con point-in-polygon sui confini comunali dettagliati ISTAT 2026
in `app/data/fvg_geography.json`, senza usare `county` o il centro comunale piu
vicino. Se il `POST` include `accuracyM`, puo' promuovere il toponimo IRDAT piu
vicino nello stesso Comune solo quando la distanza comprensiva del raggio GPS e
di 10 m di margine non supera 350 m, esiste un secondo nome e il relativo
distacco e' maggiore di due volte raggio piu margine. Senza accuratezza restituisce soltanto il
Comune. Soltanto fuori dai confini FVG usa Nominatim al livello citta' (`zoom=10`),
con coordinate arrotondate e cache in memoria, e restituisce un punto pubblico
canonico `nominatim_place`: il fix GPS preciso non viene salvato come punto meteo.
Lo script
`tools/build_fvg_geography.py` rigenera lo snapshot versionato, con URL,
licenze e SHA-256 delle fonti.
Le nuove integrazioni inviano coordinate e `accuracyM` nel body JSON di `POST
/api/location/reverse`, evitando di inserirle nella query URL; il precedente
endpoint `GET` resta temporaneamente disponibile ed e' deprecato e non
promuove localita per prossimita. La risposta mantiene il fix in `lat`/`lon`
per compatibilita e fornisce in `dataPoint` il punto pubblico canonico IRDAT o
comunale da usare nelle successive richieste meteo, senza ripetere le
coordinate GPS esatte.

## Territorio e persistenza community

Variabili opzionali:

- `LIVE_WEBCAMS_MANIFEST_URL`: manifest remoto delle webcam; il file locale
  resta il fallback pronto all'avvio;
- `COMMUNITY_STORAGE=memory`: default locale, senza servizi esterni;
- `COMMUNITY_STORAGE=firestore`: abilita la modalita produzione fail-closed;
  letture o scritture Firestore non disponibili restituiscono `503` senza
  degradare su memoria;
- `COMMUNITY_STORAGE=auto`: usa Firestore soltanto quando trova credenziali;
- `COMMUNITY_APP_CHECK_MODE=off`: esclusivamente sviluppo locale; le mutazioni
  community non richiedono App Check. Il valore viene rifiutato quando e'
  presente `K_SERVICE` o `COMMUNITY_STORAGE=firestore`;
- `COMMUNITY_APP_CHECK_MODE=enforce`: modalita del pilota; creazione,
  cancellazione, conferma e flag di moderazione richiedono un token Firebase
  App Check valido nell'header `X-Firebase-AppCheck`. Token assente o non
  valido viene rifiutato e un verificatore non disponibile restituisce `503`,
  senza aprire un fallback non protetto;
- `COMMUNITY_APP_CHECK_ALLOWED_APP_IDS`: allowlist separata da virgole degli
  App ID Firebase Android autorizzati. E' obbligatoria in `enforce`;
- `FIREBASE_SERVICE_ACCOUNT_JSON`, `FIREBASE_SERVICE_ACCOUNT_B64`,
  `FIREBASE_CREDENTIALS_PATH` o `GOOGLE_APPLICATION_CREDENTIALS`: credenziali
  supportate per la persistenza;
- `FIREBASE_PROJECT_ID`: progetto esplicito quando necessario.

### Controllo amministrativo anteprime webcam

Il backend espone `GET` e `PUT /api/admin/webcams/state` per sospendere o
riattivare le anteprime senza cambiare il contratto pubblico di
`GET /api/live/webcams`. Le operazioni richiedono il claim Firebase separato
`webcamAdmin: true`; `adsAdmin` non concede accesso alle webcam. Lo stato è
conservato in `webcam_admin_state/current` quando Firestore è disponibile.

Per il solo sviluppo locale sono supportate:

- `WEBCAM_ADMIN_AUTH_MODE=local`;
- `WEBCAM_ADMIN_LOCAL_TOKEN=<token locale>`.

La modalità locale è rifiutata su Cloud Run. Dettagli, payload e comportamento
fail-closed sono documentati in
`docs/operations/WEBCAM_CONTROL_PLANE.md`.

Il valore di `COMMUNITY_APP_CHECK_MODE` e' intenzionalmente stretto: sono
accettati soltanto `off` ed `enforce`; un valore sconosciuto blocca le
mutazioni con `503`. Per il pilota la configurazione backend prevista e':

```text
COMMUNITY_STORAGE=firestore
COMMUNITY_APP_CHECK_MODE=enforce
COMMUNITY_APP_CHECK_ALLOWED_APP_IDS=1:1234567890:android:abcdef0123456789
FIREBASE_PROJECT_ID=meteo-friul
```

Se `COMMUNITY_APP_CHECK_MODE` manca, il backend usa `enforce` automaticamente
su Cloud Run (`K_SERVICE`) o con storage Firestore; soltanto un processo locale
con storage non persistente usa `off` come default. Gli elementi della
allowlist sono gli **App ID Firebase Android** nel formato
`1:numero-progetto:android:identificatore`, non il package Android come
`com.meteofriul.app` e non i token debug.

I token debug dei singoli APK pilota si registrano in Firebase App Check e non
devono essere salvati nelle variabili backend, nel repository o condivisi tra
dispositivi. La lettura `GET /api/community/reports` e tutte le altre letture
pubbliche restano accessibili senza App Check.

Il CORS consente come origini cross-site `https://localhost`, l'origine
predefinita della WebView Capacitor, e `https://meteofriul.app`, origine
canonica della Web App. Anteprime temporanee possono essere aggiunte soltanto
come origini HTTPS esatte tramite `CORS_ADDITIONAL_ORIGINS`; wildcard, path,
query e fragment sono rifiutati all'avvio. Sono ammessi gli header
`Content-Type` e `X-Firebase-AppCheck` e i metodi necessari a letture e
mutazioni. Il CORS non e' un controllo di autenticazione: richieste senza
header `Origin` possono comunque raggiungere l'API, mentre il gate App Check
resta la protezione fail-closed delle mutazioni community.

Le collezioni di base restano compatibili con il backend precedente:
`community_reports`, `community_report_cooldowns` e
`community_report_confirmations`. La moderazione aggiunge
`community_report_flags`, `community_report_moderation` e
`community_source_blocks`. Il rango Community aggiunge i ledger privati
`community_reputation` e `community_reputation_awards`: conservano soltanto
chiavi pseudonime, totali e riferimenti di episodio hashati, mai il
`client_id` grezzo. Tutti i documenti temporanei espongono
`expires_at_timestamp`; le policy TTL Firestore elencate in
`docs/operations/COMMUNITY_MODERATION_GATE.md` devono risultare `ACTIVE` prima
della distribuzione. La creazione usa una transazione atomica per cooldown
anonimo, report e budget globale (`community_report_rate_limits`):
massimo 20 segnalazioni al minuto sull'intero servizio, con documento a
scadenza. È un circuit breaker indipendente dal `client_id`, non un limite per
IP: dietro Firebase Hosting e Cloud Run `request.client.host` non è documentato
qui come identità affidabile dell'utente finale e gli header inoltrati non
vengono considerati attendibili. App Check e/o Cloud Armor restano il livello
anti-abuso da aggiungere prima di aumentare questo budget. Questo limite è un
circuit breaker per contenere costo e carico, non sostituisce una protezione
anti-abuso per dispositivo o identità attendibile.

La lettura production non esegue uno stream completo: filtra in Firestore i
soli report non scaduti, ordina prima per `expires_at_timestamp` (lo stesso
campo usato dalla disuguaglianza, come richiesto da Firestore) e limita la query
a 200 documenti. Poiché ogni report ha TTL fisso di 60 minuti, l'ordine di
scadenza coincide con quello di creazione; il repository applica comunque
l'ordinamento locale canonico prima della risposta.

Le conferme `yes/no` hanno un circuito separato di 60 richieste al minuto e un
massimo di 500 votanti anonimi per gruppo. Il voto identico resta idempotente:
ritorna prima di consumare nuovamente il budget o riscrivere i contatori. I
contatori sono materializzati sui report del gruppo nella stessa operazione,
cosi' la lettura pubblica non esegue una query aggiuntiva per ogni gruppo.

`POST /api/community/reputation`, protetta da App Check, legge il solo riepilogo
dell'installazione chiamante. Una segnalazione vale un punto per l'autore una
sola volta quando un'altra installazione la conferma o invia un secondo report
nello stesso episodio. `quiet` e i voti dei confermatori non assegnano punti;
il cap e' tre punti per giorno `Europe/Rome`. Una smentita successiva indica
cessazione e conserva il punto gia' convalidato. Solo `hide`/`remove`
amministrativi per inesattezza o abuso revocano il punto in modo idempotente.
Le soglie, definite soltanto dal backend, sono `Osservadôr dal Cîl` 0-4,
`Vuaite dal Timp` 5-19 e `Sentinele dal Teritori` da 20 punti. Il riepilogo
espone anche `total_reports`, incrementato per ogni invio accettato e mai
ricostruito sommando stati effimeri. Il riepilogo scade logicamente e via TTL
365 giorni dopo l'ultimo invio, convalida o revoca; ogni assegnazione scade 365
giorni dopo l'evento relativo.

Ogni fonte mantiene nell'API una chiave pubblica opaca, ruotata ogni giorno.
I client aggiornati possono inoltre inviare con una nuova segnalazione lo
snapshot pubblico `identity` v1, che viene copiato nel documento e non cambia
se l'alias locale viene rigenerato in seguito:

```json
{
  "version": 1,
  "alias": "Clâf dal Fogolâr",
  "subject_id": "claf",
  "avatar": {
    "palette_id": "sky",
    "pattern_id": "diagonal",
    "variant": 2,
    "angle": 135
  }
}
```

Alias, soggetto, palette, pattern, variante e angolo sono validati tramite
allowlist/range; campi aggiuntivi sono rifiutati. In particolare lo snapshot
non accetta e non pubblica `client_id`, `owner_key`, account o dati personali.
L'alias usa un epiteto friulano non geografico ed e' indipendente sia dalla
localita' meteo attiva sia dal luogo della segnalazione. Il backend continua ad
accettare gli alias storici nel formato `<soggetto> di <localita'>`, cosi' i
report gia' pubblicati e i client precedenti restano compatibili.
`GET /api/community/reports` restituisce lo snapshot sul singolo report e, nei
gruppi, `identities` ordinate dal report più recente e deduplicate per
`sourceKey`. Ogni elemento contiene `{sourceKey, identity}`; `identity` è nullo
per una fonte legacy, così il client può generare il vecchio pseudonimo senza
duplicazioni. I report creati da client precedenti restano validi. La chiave
non e' un account e non espone l'`owner_key` privato. Un flag valido
nasconde subito il gruppo soltanto sul dispositivo del segnalante e crea una
voce idempotente nella coda privata. Non esiste una soglia di hide globale
automatico, perche' il `client_id` pseudonimo e' rigenerabile. Hide, restore,
remove e blocco fonte sono quindi decisioni esplicite del moderatore.

Lo strumento privato e' `tools/moderate_community_reports.py`. Senza `--apply`
le azioni mutanti sono dry-run. Comandi disponibili:

```powershell
.\venv\Scripts\python.exe tools\moderate_community_reports.py list
.\venv\Scripts\python.exe tools\moderate_community_reports.py inspect GROUP_ID
.\venv\Scripts\python.exe tools\moderate_community_reports.py hide GROUP_ID --apply
.\venv\Scripts\python.exe tools\moderate_community_reports.py restore GROUP_ID --apply
.\venv\Scripts\python.exe tools\moderate_community_reports.py remove GROUP_ID --apply
.\venv\Scripts\python.exe tools\moderate_community_reports.py block-source REPORT_ID --hours 24 --apply
.\venv\Scripts\python.exe tools\moderate_community_reports.py block-group-sources GROUP_ID --hours 24 --apply
.\venv\Scripts\python.exe tools\moderate_community_reports.py unblock-source REPORT_ID --apply
```

L'output ordinario non stampa chiavi private delle fonti o dei segnalanti. Il
blocco fonte della prima beta non puo' superare 24 ore. La rimozione conserva
per lo stesso orizzonte soltanto lo snapshot privato minimo necessario ad audit
e gestione dell'abuso; non esiste una route amministrativa pubblica.
`hide` e `remove` marcano l'episodio come rifiutato e revocano una sola volta
gli eventuali punti. `restore` riporta la validita' a non verificata ma, per
scelta fail-closed, non riassegna automaticamente un punto revocato.

## Stato persistente delle allerte ufficiali

La route `/api/weather/official-alerts` legge l'ultimo stato confermato dalla
collezione Firestore `official_alert_snapshots/current`. Il documento viene
aggiornato soltanto quando la fonte ufficiale risponde direttamente con uno
stato fresco. Un errore di rete non puo quindi trasformarsi in una falsa
assenza di allerte.

Le letture Firestore hanno un timeout di cinque secondi senza retry automatici,
vengono accorpate durante i picchi concorrenti e riusate per trenta secondi.
In Cloud Run il parametro pubblico di aggiornamento rilegge lo snapshot, ma non
puo avviare scraping o scritture upstream. La sincronizzazione reale resta
riservata al job esplicito qui sotto. I due intervalli sono configurabili con
`OFFICIAL_ALERTS_FIRESTORE_TIMEOUT_SECONDS` e
`OFFICIAL_ALERTS_FIRESTORE_READ_TTL_SECONDS`.

Il job pianificabile usa lo stesso codice dell'API:

```powershell
.\venv\Scripts\python.exe -m app.jobs.sync_official_alerts
```

Il comando termina con codice `0` solo dopo una lettura fresca confermata e
salvata. In produzione richiede `COMMUNITY_STORAGE=firestore` e
`FIREBASE_PROJECT_ID=meteo-friul`. Può valutare il push ufficiale soltanto
secondo le modalità esplicite descritte sotto; il default `off` non invia
nulla. Gli avvisi meteo locali restano indipendenti: questo job non esegue il
runner Open-Meteo né il relativo dispatcher.

## Push Android/Web e avvisi locali per owner e beta Play

Le route `POST /api/push/devices/register` e
`POST /api/push/devices/unregister` accettano Android e Web e sono protette da
Firebase App Check. `POST /api/push/devices/location` e' invece riservata ad
Android: riceve un fix effimero gia' limitato a 250 m, lo risolve offline e
aggiorna atomicamente soltanto il target canonico di un dispositivo gia'
registrato. Android mantiene il contratto legacy con `token`; Web usa
`registration.kind=firebase_installation_id` e viene consegnato da Firebase
Admin tramite `fid`. Gli App ID Firebase sono associati esplicitamente alla
piattaforma, quindi un'attestazione Web non può registrare un target Android e
viceversa.
Le preferenze client iniziali sono `official_alerts=true` e
`weather_notices=true`. Il dispatcher locale è separato da quello ufficiale e
supporta sia il pilot con un solo hash owner esplicito, sia la coorte Android
beta Play e la Web App/PWA ufficiale, entrambe attestate e legate a una
generazione server.

Variabili push:

- `PUSH_APP_CHECK_MODE=enforce`: gate App Check delle due route; in ambiente
  persistente o Cloud Run il valore `off` è rifiutato;
- `PUSH_APP_CHECK_ANDROID_APP_IDS`: allowlist degli App ID Firebase Android;
  per compatibilità, se assente usa `PUSH_APP_CHECK_ALLOWED_APP_IDS` e poi
  `COMMUNITY_APP_CHECK_ALLOWED_APP_IDS`;
- `PUSH_APP_CHECK_WEB_APP_IDS`: allowlist separata e obbligatoriamente
  esplicita degli App ID Firebase Web; non eredita l'allowlist Android;
- `PUSH_OFFICIAL_ALERTS_MODE=off|dry_run|send`: `off` è il default;
  `dry_run` conta i dispositivi eleggibili ma non chiama FCM;
- `PUSH_PILOT_MAX_DEVICES`: nei pilot storici resta il limite delle
  installazioni (`1`–`10`). In `play_beta` è la dimensione delle pagine
  Firestore e dei lotti FCM (`1`–`500`, default `200`), non un tetto sul
  numero complessivo di dispositivi;
- `PUSH_PILOT_ENROLLMENT_MODE=owner_allowlist|private_test|play_beta`: il default
  `owner_allowlist` conserva il pilot manuale; `private_test` ammette soltanto
  APK Android attestati da App Check/Play Integrity e li registra
  automaticamente fino al limite configurato; `play_beta` accetta soltanto
  installazioni Android della beta Play e registrazioni Web/PWA dell'App ID Web
  ufficiale, attestate e appartenenti alla generazione server corrente;
- `PUSH_ENROLLMENT_GENERATION`: identificatore server-side obbligatorio in
  `play_beta`, per esempio `play-beta-v1`. Non fa parte del payload client:
  viene salvato dal backend nel record `push_devices` e deve coincidere nei
  dispatcher e nel controllo transazionale finale;
- `PUSH_PLAY_BETA_MIN_VERSION_CODE=300029`: codice Android minimo supportato
  dalla registrazione e da tutti i dispatcher `play_beta`. Sono ammesse
  `0.1.12+300029` e le release successive con `versionCode` crescente;
  le build precedenti vengono escluse. Il valore non ha un limite superiore,
  così una nuova release Play non richiede di aggiornare i job. Il client deve
  inviare `versionName+versionCode` valido; Web/PWA resta autorizzata tramite
  il proprio App ID attestato, senza soglia Android;
- `PUSH_PLAY_BETA_ALLOWED_APP_VERSIONS`: lista esatta storica delle identità
  `versionName+versionCode`, ancora supportata per rollback. In `play_beta`
  impostare **una sola** tra lista e soglia; la presenza contemporanea è un
  errore di configurazione. La versione dichiarata dal client è soltanto un
  controllo di compatibilità, non prova crittografica della distribuzione;
- `PUSH_PILOT_ALLOWED_INSTALLATION_HASHES`: hash SHA-256 separati da virgola;
  è obbligatoria e non può essere vuota in modalità `send` con enrollment
  `owner_allowlist`; deve essere vuota in `private_test` e `play_beta`;
- `PUSH_WEB_APP_URL=https://meteofriul.app`: origin HTTPS usata dal click
  della notifica Web; il backend aggiunge `/?tab=bulletin` e rifiuta URL con
  path, query o fragment;
- `PUSH_OFFICIAL_ALERTS_REQUIRED=true|false`: rende il job fallibile se è
  richiesto `send` ma il modo è ancora `off` o `dry_run`;
- `PUSH_PILOT_TEST_MODE=send`: gate aggiuntivo temporaneo per il solo comando
  di test owner; va rimosso dopo la prova.

La sintesi del mattino usa lo stesso consenso `weather_notices` e lo stesso
canale Android degli avvisi meteo locali, così è compatibile con le versioni
Play già installate. Il job `app.jobs.send_morning_forecast` produce una sola
notifica al giorno e per dispositivo, con deduplica persistente per data,
località salvata e dati ICON verificati. Il tap apre il Bollettino. Le variabili
dedicate sono `MORNING_FORECAST_DELIVERY_MODE=off|dry_run|send` e
`MORNING_FORECAST_REQUIRE_SINGLE_TARGET=true|false`; il secondo gate è
obbligatorio per il collaudo circoscritto a una sola versione/dispositivo.

L'anticipazione serale e' un percorso distinto, predisposto ma spento finche'
non viene completato il collaudo owner. Il job
`app.jobs.send_evening_forecast` seleziona la giornata civile successiva in
`Europe/Rome`, richiede una copertura ICON quasi completa dalla notte alla
sera e usa codice meteo, precipitazioni, neve e raffiche. Il testo resta breve
anche nella notifica non espansa, viene prodotto in italiano o friulano usando
la lingua registrata dal dispositivo e apre il Bollettino. Le variabili sono
`EVENING_FORECAST_DELIVERY_MODE=off|dry_run|send` e
`EVENING_FORECAST_REQUIRE_SINGLE_TARGET=true|false`. Dopo il collaudo reale
italiano e friulano del 30 settembre 2026, la configurazione di produzione
versionata usa `send` senza gate singolo. Durante il solo collaudo owner,
`EVENING_FORECAST_TEST_INSTALLATION_HASH` puo' restringere l'esecuzione a un
singolo `device_id` SHA-256 gia' registrato. Il valore non e' un token FCM, va
passato soltanto come override temporaneo dell'esecuzione e non deve essere
salvato nella configurazione permanente del job.

L'attivazione è divisa in due fasi:

1. distribuire un nuovo endpoint Cloud Run tagged, impostare `dry_run`, App
   Check `enforce` e un limite coerente con le installazioni previste;
2. per il pilot owner, verificare ogni `device_id` hash, inserirlo in
   `PUSH_PILOT_ALLOWED_INSTALLATION_HASHES` e soltanto allora passare a `send`;
3. prima di impostare `play_beta` o accettare la prima registrazione, richiedere
   nel provider App Check Play Integrity i verdict `PLAY_RECOGNIZED` e
   `LICENSED`; se questa separazione non è verificabile, creare un Firebase
   Android App ID distinto per la beta Play;
4. soltanto dopo questo gate, usare `play_beta`, impostare una nuova
   `PUSH_ENROLLMENT_GENERATION`, configurare esplicitamente
    `PUSH_APP_CHECK_ANDROID_APP_IDS`, `PUSH_APP_CHECK_WEB_APP_IDS` e
   una sola policy per le versioni Android (soglia minima nelle release correnti,
   lista esatta soltanto nei cutover storici), iniziando con cap `1`;
5. verificare prima una singola installazione proveniente dal track Play in
   `dry_run`, quindi
   abilitare `send` senza riutilizzare record dei pilot precedenti.

La policy permissiva usata dal vecchio sideload `private_test` per APK non
riconosciuti o non licenziati deve essere disattivata prima del cutover Play e
non può coesistere con `play_beta`, nemmeno con cap `1`, in `dry_run` o prima di
`send`. L'identità release inviata dal client è soltanto difesa in profondità e
non può sostituire i verdict Play o un Firebase Android App ID distinto.

`send` senza allowlist owner è una configurazione invalida; `private_test` o
`play_beta` con una allowlist manuale sono ugualmente rifiutati per evitare
configurazioni ambigue. In `play_beta` sono inoltre obbligatori App Check della
piattaforma valido e generazione; per Android serve anche l'identità release
esatta. I record schema `1.x`,
`2.0`, privi di App ID, con versione non ammessa o appartenenti a generazioni
precedenti restano esclusi anche se ancora attivi in Firestore. Il record
corrente usa schema `2.1`; la capacità viene contabilizzata in un documento
distinto per generazione. La registrazione di un dispositivo può consegnare una
sola volta un'allerta ufficiale già attiva; il normale job applica deduplica,
collapse key, TTL e disabilitazione dei token FCM non validi.

Il workflow GitHub `sync-official-alerts.yml` è un percorso alternativo e resta
disabilitato sia nella UI sia tramite il gate repository
`OFFICIAL_ALERT_SYNC_WORKFLOW_ENABLED=false`. Se venisse riabilitato, esporta
App ID, generazione e versioni ammesse dalle repository variables; in
`play_beta` l'assenza di uno solo di questi valori arresta il job.

La proprietà globale dei target FCM è registrata in
`push_target_owners`: registrazione, rotazione, unregister e disabilitazione di
un token non valido aggiornano indice e dispositivo nella stessa transazione.
Un target già posseduto da un'altra installazione attiva viene rifiutato; un
indice stantio può essere riparato soltanto dopo il controllo del relativo
record dispositivo. Prima di aumentare il cap va comunque eseguito l'audit di
coerenza `target_hash -> installation_id`. Il cap `1` resta il gate prudenziale
del primo collaudo Play, non una compensazione per l'assenza dell'indice.

L'ID installazione casuale vive nello storage dell'APK o della Web App. Gli
aggiornamenti Android con `adb install -r` e gli aggiornamenti del service
worker lo preservano. Disinstallazione/cancellazione dati dell'app o dei dati
del sito lo eliminano; un FID Web revocato viene disattivato al primo rifiuto di
Firebase.

Il runner locale separato valuta esclusivamente la posizione registrata del
telefono owner:

```powershell
.\venv\Scripts\python.exe -m app.jobs.run_local_notice_shadow
```

Richiede `LOCAL_NOTICE_SHADOW_MODE=shadow`, persistenza Firestore e un target
Android attivo con Comune canonico e preferenza `weather_notices=true`. Quando
e' presente una localita IRDAT validata, la previsione usa le sue coordinate
canoniche pubbliche e non il centro del Comune; l'identita della localita entra
anche nella deduplica. Il
risultato conserva per 14 giorni soltanto evidenza allowlistata. Ogni candidato
ha `can_notify=false`, il riepilogo non contiene token, device ID o coordinate e
il modulo non importa alcun sender FCM. Il job ufficiale resta indipendente e
non invoca questo runner.

Il dispatcher locale usa invece:

```powershell
.\venv\Scripts\python.exe -m app.jobs.send_local_weather_notices
```

Variabili dedicate:

- `LOCAL_NOTICE_DELIVERY_MODE=off|dry_run|send`, con default `off`;
- `LOCAL_NOTICE_ENROLLMENT_MODE=owner_allowlist|play_beta`, con default
  `owner_allowlist`;
- `LOCAL_NOTICE_ALLOWED_INSTALLATION_HASHES`, obbligatoriamente un solo SHA-256
  in `owner_allowlist` quando la modalità non è `off`; deve essere vuota in
  `play_beta`;
- `PUSH_ENROLLMENT_GENERATION`, obbligatoria in `play_beta` e identica alla
  generazione usata dalla registrazione push;
- `PUSH_APP_CHECK_ANDROID_APP_IDS`, allowlist degli App ID Android attestati;
  il dispatcher locale conserva il fallback storico a
  `PUSH_APP_CHECK_ALLOWED_APP_IDS`;
- `PUSH_PLAY_BETA_MIN_VERSION_CODE`, soglia Android condivisa con API e tutti
  i dispatcher, oppure la lista esatta storica
  `PUSH_PLAY_BETA_ALLOWED_APP_VERSIONS`, mai entrambe;
- `LOCAL_NOTICE_RETENTION_DAYS`, compreso tra 1 e 30, default 14;
- `LOCAL_NOTICE_OPEN_METEO_TIMEOUT_SECONDS`, compreso tra 1 e 15;
- `PUSH_PILOT_MAX_DEVICES`, dimensione da 1 a 500 delle pagine Firestore e dei
  lotti FCM in `play_beta` (default `200`); in owner mode resta un limite e non
  amplia l'allowlist esplicita.

Prima della prima installazione dal canale Play il backend resta privato con
entrambi gli enrollment in `owner_allowlist`, cap `1` e rispettive allowlist
owner. Prima di cambiare uno dei due enrollment, App Check deve già richiedere
`PLAY_RECOGNIZED` e `LICENSED`, oppure la beta deve disporre di un Firebase
Android App ID distinto; la policy permissiva del vecchio sideload non deve più
autenticare queste route. Il passaggio beta deve quindi essere atomico:
impostare entrambi gli enrollment su `play_beta`, svuotare le allowlist owner,
creare una nuova `PUSH_ENROLLMENT_GENERATION`, configurare l'App ID Android e
partire con delivery `dry_run`. Dopo la registrazione e il controllo della
prima installazione Play si abilita `send`; la dimensione pagina/lotti resta
indipendente dal numero totale delle installazioni.

Il detector resta puro e non notificabile. Il servizio di delivery promuove al
massimo un candidato per punto canonico ed esecuzione, richiede corroborazione
per i temporali,
ricontrolla transazionalmente target e preferenza `weather_notices`, usa un
  outbox separato e il canale Android `mf_weather_notices_v1`. Sono eleggibili
  registrazioni Android oppure Web/PWA con Comune canonico e modalita di
  posizione. Sul Web la posizione persistita è sempre una scelta comunale
  esplicita: non viene simulata una prova GPS in background. In `play_beta`
  servono inoltre record schema `2.1`, generazione esatta e App ID della
  piattaforma attestato; Android richiede anche una versione release ammessa. I
  dispositivi sullo stesso Comune/localita condividono una
sola acquisizione ICON-2I, ma claim, deduplica e risultato restano separati per
installazione. Firestore viene letto a pagine e FCM usa lotti fino a 500
messaggi. Un errore di una fonte, di una pagina, di un punto canonico o di un
token non viene nascosto: il riepilogo aggrega pagine, lotti, dispositivi,
gruppi ed errori e rende rosso il job in caso di esito parziale. In `dry_run`
non vengono creati claim e FCM non viene invocato. La
localita IRDAT e' usata quando disponibile; altrimenti la previsione usa il
punto pubblico del catalogo comunale e il testo dichiara esplicitamente
`nel Comune di ...`, senza inventare una frazione. In modalita automatica FVG
serve una prova GPS ricevuta negli ultimi 60 minuti, precisione non superiore a
250 m; una scelta manuale canonica e' invece persistente per esplicita volonta
dell'utente. Fuori FVG gli Avvisi sono disponibili per il Comune scelto
manualmente sui 7.894 Comuni del catalogo ISTAT; il GPS nazionale resta
fail-closed finche non e' disponibile nel backend un resolver di confini
comunali di produzione. La transazione finale ricontrolla Comune, ID localita opzionale,
modalita e prova GPS per impedire un invio calcolato sulla posizione precedente.
Firestore conserva timestamp/precisione della prova, ma non le coordinate GPS
o un `dataPoint` fornito dal client. I record audit in
`local_notice_pilot_runs` non contengono token, ID installazione o coordinate e
scadono tramite TTL Firestore dopo 14 giorni. Due localita dello stesso Comune
usano documenti audit distinti, evitando che una sovrascriva l'altra nello
stesso quarto d'ora.

La policy conservativa `production-2026-09-24-icon2i-v1` legge sei ore di
previsione per poter validare fenomeni prolungati, ma produce un candidato
soltanto quando l'inizio previsto dista al massimo un'ora. I segnali più lontani
restano osservazioni diagnostiche e non sono promuovibili. Le soglie in
`dry_run` sono:

- temporale: solo codici WMO `95`, `96` o `99`, con probabilita almeno `70%` e
  precipitazione liquida nello stesso intervallo; `96` e `99` aggiungono la
  specificazione prudente `con grandine`;
- pioggia intensa: almeno `15 mm` in tre ore, almeno una delle ore da `5 mm` e
  probabilita almeno `70%` sulla stessa ora intensa;
- raffiche forti: almeno `70 km/h`;
- neve: codice esplicito moderato/forte `73`, `75` o `86`, oppure almeno
  `2 cm` in tre ore con probabilita almeno `70%` in una fascia nevosa;
- precipitazioni gelate: esclusivamente i codici espliciti `56`, `57`, `66` o
  `67`, senza dedurre ghiaccio sulle strade;
- caldo intenso: almeno `35 °C` reali oppure `38 °C` percepiti per due ore
  consecutive, con deduplica giornaliera.

Pioggia debole, schiarite, neve debole, freddo ordinario, nuvolosita e nebbia
non generano candidati. I testi restano probabilistici e non usano mai
`allerta`, `pericolo` o `criticita`, termini riservati alle fonti ufficiali.

Cloud Scheduler e' l'unico percorso pianificato. Il Cloud Run Job
`meteofriul-official-alert-sync` resta invocato alle ore pari
`00:00, 02:00, ... 22:00`, con cron `0 */2 * * *`; il job
`meteofriul-local-notice` viene invocato ogni ora con cron `0 * * * *`. Entrambi
usano il fuso `Europe/Rome`. La sintesi quotidiana usa il job e scheduler
`meteofriul-morning-forecast` alle `07:30`, con cron `30 7 * * *`. I tre
percorsi hanno scheduler omonimi, accesso owner-only e circuiti distinti; i
vecchi scheduler con suffisso `pilot` sono stati disattivati. Il workflow
GitHub e' soltanto manuale e mantiene il push su `off` se la relativa variabile
non viene configurata.

Il percorso serale proposto usa il job e scheduler separati
`meteofriul-evening-forecast`, alle `20:45` nel fuso `Europe/Rome`, con cron
`45 20 * * *`. Non fa parte dello stato Cloud attivo finche' lo script
`scripts/deploy-evening-forecast-job.ps1` non viene eseguito esplicitamente in
modalita' `Apply`; anche dopo la creazione resta innocuo mentre
`EVENING_FORECAST_DELIVERY_MODE=off`. Il job usa esclusivamente il service
account least-privilege
`meteofriul-runtime@meteo-friul.iam.gserviceaccount.com`, non il Compute
default.

Gli adapter ICON degli avvisi locali e della sintesi mattutina usano un timeout
di produzione di 30 secondi, con limite applicativo di 45 secondi. Un timeout
esegue un solo retry immediato della stessa GET idempotente, utile quando il
servizio Cloud Run sta completando un cold start. Connessioni o risposte HTTP
non valide, payload non verificabili e il secondo timeout restano fail-closed:
il gruppo interessato non produce notifiche e conserva un audit sanitizzato.
Un errore del puntatore/manifest FVG o del resolver nazionale condiviso viene
memorizzato soltanto per l'esecuzione corrente, evitando di moltiplicare due
timeout per ogni comune quando la sorgente è indisponibile.

Le snapshot ufficiali inattive restano leggibili per 150 minuti, configurabili
con `OFFICIAL_ALERTS_INACTIVE_SNAPSHOT_TTL_SECONDS`. La finestra copre il ciclo
biorario con 30 minuti di margine per ritardi e cold start, ma rende ancora
visibile un'esecuzione saltata prima del ciclo successivo.

Il job ufficiale confronta il widget Protezione Civile FVG con il pannello PCR
ARPA/OSMER. Se il widget è indisponibile, può usare i metadati della pagina
ufficiale `/it/allerte` o del canale `@ProtCivileFVG`, sempre corroborati dal
pannello PCR. Numero/anno del PDF, livello, zone e validità devono coincidere
prima di autorizzare un push; un dato mancante o discordante resta
`official_alerts_unavailable`, non `no_candidate`. Il download dei PDF resta
una verifica opzionale più forte, ma non è richiesto quando il dominio
documentale non è raggiungibile da Cloud Run. La deduplicazione è persistita
in Firestore.
Cloud Monitoring segnala a `info@meteofriul.it` almeno due esecuzioni fallite
nella finestra di 5 ore; un singolo timeout non apre un incidente.
La policy deve filtrare il job canonico `meteofriul-official-alert-sync` e il
canale email condiviso usa il nome neutro `Meteo Friul - notifiche operative`.
Il contratto e il read-back live si verificano con:

```powershell
.\scripts\official-alert-monitoring-audit.contract.tests.ps1
.\scripts\audit-official-alert-monitoring.ps1
```

Le policy dei job pianificati sono dichiarate atomicamente in
`scripts/cloud-run-job-monitoring-policies.json`. Oltre ai contatori di errore,
il catalogo controlla l'assenza di vere esecuzioni riuscite per Avvisi locali,
ICON FVG e ICON nazionale. Le finestre sono rispettivamente 3, 18 e 18 ore; una
policy di assenza si chiude soltanto quando ricompare la metrica `succeeded`.
Le policy rapide di errore di Avvisi locali e ICON FVG notificano l'apertura ma
non la chiusura temporale, così un fallimento che esce dalla finestra non viene
presentato come guarigione. Il catalogo comprende inoltre sintesi mattutina,
Allerte FVG, Allerte DPC nazionali, CAMS ed Eventi. Il read-back e
l'applicazione idempotente si eseguono rispettivamente con:

```powershell
.\scripts\sync-cloud-run-job-monitoring.ps1 -Mode Audit
.\scripts\sync-cloud-run-job-monitoring.ps1 -Mode Apply
```

Il job DPC nazionale e' separato da quello FVG: usa l'entrypoint
`app.jobs.sync_national_official_alerts`, non invia push e scrive soltanto le
snapshot nazionali. Lo script di deploy prevede il minuto 35 ogni due ore nel
fuso `Europe/Rome`, lasciando margine alla pubblicazione del bollettino DPC ed
evitando la contemporaneita con il job regionale. Finche la correzione non e'
distribuita, verificare l'orario dello Scheduler live separatamente. La sua
configurazione di deploy e' custodita in
`scripts/deploy-national-official-alert-job.ps1`. L'account di Cloud Scheduler
deve avere `roles/run.invoker` sul solo job nazionale: lo script assegna il
binding in `Apply` e ne verifica la presenza in `Audit`. Se manca su un job gia'
distribuito, e' sufficiente ripristinare quel binding IAM; non occorre
ricostruire l'immagine backend, avviare manualmente il job o modificare gli
altri writer delle notifiche. Dopo il ripristino, verificare il successivo run
pianificato e la freschezza della snapshot nazionale.

Il job CAMS usa soltanto le due finestre sorgente utili delle `15:00` e `20:00`
UTC, equivalenti alle `17:00` e `22:00` durante l'ora legale. La precedente
esecuzione delle `10:00` UTC e' stata rimossa per evitare un'acquisizione priva
di nuovi dati.

Il job locale e' stato attivato in `send` il 20 agosto 2026 esclusivamente per
l'hash owner, dopo la verifica della revisione `902548c` in `dry_run`. Il primo
ciclo automatico e' terminato `no_eligible_device`: nessun invio e' possibile
finche il worker Android non rinnova una prova GPS valida negli ultimi 30
minuti. Qualunque estensione oltre l'owner richiede ancora il collaudo E2E di
App Check, fix foreground/background, geofence, controllo periodico, riavvio,
revoca del permesso e CAS finale. Il backend non persiste le coordinate
ricevute dalla route location.

## Controllo automatico delle fonti Villa Manin ed ERPAC

Le due fonti ufficiali aggiuntive usano un job separato e inizialmente solo in ombra:

```powershell
.\venv\Scripts\python.exe -m app.jobs.sync_event_sources
```

Variabili:

- `EVENT_SOURCE_AUTOMATION_MODE=off|shadow`, default `off`;
- `EVENT_SOURCE_CONFIRMATIONS_REQUIRED=2|3`, default `2`;
- `EVENT_SOURCE_ALERT_FAILURE_THRESHOLD=2..5`, default `2`;
- `EVENT_SOURCE_ALERT_EMAIL_TO`, default `info@meteofriul.it`;
- `EVENT_SOURCE_ACTIVE_LIMIT=1..100`, default `100`;
- `EVENT_SOURCE_LOCAL_STATE_PATH`, ammessa soltanto fuori da Cloud Run per le prove
  locali;
- `EVENT_SOURCE_FEED_MODE=off|preview|active`, default `off`.

Il job confronta l'intero catalogo candidato con tutte le fonti Eventi già attive,
compresa la paginazione e la ricerca mirata TurismoFVG. Sono necessarie due scansioni
complete e identiche per approvare un record. Doppioni, conflitti e campi critici
incompleti non entrano nel feed; cambi di data, luogo, orario o stato riaprono la
conferma. Lo stato Firestore nasce con `publication_enabled=false` e il feed `active`
resta quindi vuoto finché l'abilitazione non viene effettuata separatamente dopo il
collaudo. Le scansioni successive conservano un gate già abilitato, ma non possono
abilitarlo autonomamente.

Le richieste di audit a Villa Manin, ERPAC e alle pagine TurismoFVG in modalità
`strict` eseguono al massimo un solo retry, dopo 0,5 secondi, esclusivamente per
timeout, errori di connessione e HTTP `408`, `429`, `500`, `502`, `503` o `504`.
Un secondo fallimento resta fail-closed. Non vengono ritentati `404`, altri `4xx`,
errori del parser o cambi di struttura; inoltre un errore di rete nel catalogo
località TurismoFVG non viene salvato come cache vuota valida.

Un incidente confermato produce un record JSON `ERROR` e codice di uscita `1`. La
notifica email è affidata a Cloud Monitoring sul destinatario
`info@meteofriul.it`; il backend non conserva credenziali SMTP. I codici diagnostici
`issues` permettono di distinguere cambio di struttura, catalogo attivo incompleto,
scheda inattesa e problemi di configurazione o persistenza.

Configurazione cloud ombra attuale:

- Cloud Run Job `meteofriul-event-source-shadow`;
- Cloud Scheduler `event-source-shadow-monitor`, alle `06:20` e `18:20` nel fuso
  `Europe/Rome`;
- policy Cloud Monitoring `Meteo Friul - fonti Eventi shadow` con canale email
  condiviso `Meteo Friul - notifiche operative`;
- `EVENT_SOURCE_FEED_MODE=off`, quindi il job controlla e conserva lo stato ma non
  pubblica eventi nell'app.

Per mostrare il catalogo protetto esclusivamente nell'ambiente locale:

```powershell
.\scripts\start-dev.ps1 -Restart -EventSourcePreview
```

La modalità `preview` viene rifiutata automaticamente quando è presente `K_SERVICE`.

Il gate pubblico viene modificato soltanto dal job manuale
`app.jobs.control_event_source_publication`. L'azione `enable` richiede conferma
esplicita e il numero esatto di eventi approvati; rifiuta stati oltre 24 ore,
incidenti attivi, candidati pendenti e quarantene inattese. L'azione `status` è
soltanto diagnostica e `disable` consente un arresto manuale immediato. Questo job
non deve avere uno scheduler.

### Aggiornamento immagine e recovery dei job Eventi

L'aggiornamento non deve usare `latest` e non deve cambiare incidentalmente comando,
variabili, account di servizio o risorse. La sequenza obbligatoria è:

1. test backend completi e audit reale `ready_for_manual_review`;
2. commit e push del codice verificato;
3. build con tag univoco legato al commit;
4. risoluzione del digest immutabile `@sha256:...`;
5. snapshot della configurazione di entrambi i job;
6. aggiornamento del solo campo `image`;
7. nuovo confronto integrale della configurazione;
8. esecuzione shadow e verifica del payload JSON;
9. esecuzione del publication-control con la sola azione predefinita `status`.

Esempio, dopo aver verificato account `meteofriul@gmail.com` e progetto
`meteo-friul`:

```powershell
$cloudGcloud = (Get-Command gcloud.cmd -ErrorAction Stop).Source
$cloudRegion = 'europe-west1'
$cloudProject = 'meteo-friul'
$cloudCommit = 'COMMIT_BREVE_VERIFICATO'
$cloudTag = "eventmon-$cloudCommit"
$cloudImage = "europe-west1-docker.pkg.dev/$cloudProject/cloud-run-source-deploy/meteofriul-api:$cloudTag"

& $cloudGcloud builds submit backend --tag=$cloudImage `
  --project=$cloudProject --region=$cloudRegion --quiet

# Risolvere il tag nel digest restituito dalla build e usare soltanto il riferimento
# europe-west1-docker.pkg.dev/.../meteofriul-api@sha256:...
$cloudDigest = 'RIFERIMENTO_IMMUTABILE_VERIFICATO'

foreach ($cloudJob in @(
  'meteofriul-event-source-shadow',
  'meteofriul-event-source-publication-control'
)) {
  & $cloudGcloud run jobs update $cloudJob --image=$cloudDigest `
    --region=$cloudRegion --project=$cloudProject --quiet
}

& $cloudGcloud run jobs execute meteofriul-event-source-shadow `
  --region=$cloudRegion --project=$cloudProject --wait
& $cloudGcloud run jobs execute meteofriul-event-source-publication-control `
  --region=$cloudRegion --project=$cloudProject --wait
```

Nel primo log sono obbligatori `event=event_source_automation_completed`,
`status=completed`, `incident_active=false`, `issues=[]` e copertura completa. Dopo
un incidente precedente è atteso `alert_transition=recovered`. `pending` può essere
maggiore di zero quando un nuovo candidato sano attende la seconda scansione: non va
forzato con una seconda esecuzione immediata. Nel secondo log sono obbligatori
`event=event_source_publication_control`, `action=status` e gate invariato. Durante
questo collaudo non usare mai `enable`, `disable` o override delle variabili.

## Test

```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests -v
```
