# Meteo Friul - Piano repository e migrazione produttiva

Data: 2026-08-10
Stato: piano operativo corrente

## Decisione principale

Il repository locale `meteo friul - ui 3.0.0` diventa la base della nuova
applicazione. La sua cronologia Git viene mantenuta e pubblicata in una nuova
repository remota.

Il repository storico `meteofriul-1.0.1` e' stato rimosso da GitHub il
19 agosto 2026, dopo il completamento e la verifica di un archivio locale.
Resta disponibile come sorgente legacy e rollback manuale tramite la copia
locale e il bundle completo; non viene copiato integralmente nella nuova
repository.

Regola:

```text
contratto necessario -> servizio isolato -> test -> integrazione -> dismissione legacy
```

Non sono ammessi:

- copia del vecchio frontend;
- copia del vecchio `App.jsx` o `App.css`;
- import del backend monolitico come blocco unico;
- dipendenze implicite fra CSS di feature diverse;
- endpoint legacy usati direttamente dalle view;
- segreti, cache, log o output di audit nel repository.

## Stato verificato

### Nuova UI

- repository Git locale autonomo, branch `main`;
- repository remota privata `meteofriul/meteofriul-app`, branch predefinito
  `main`;
- CI separata per frontend e backend su push e pull request;
- frontend React 19 + Vite 8;
- dipendenze runtime limitate a React, Leaflet e Lucide;
- dati, cache e fetch separati dalle view tramite `services`, controller e view model;
- CSS separato per token, componenti, layout e feature;
- test, lint e build eseguibili localmente;
- UI ancora modificabile: la pubblicazione della repository non congela il design.

### Repository storico

- remote storico `meteofriul/meteofriul-1.0.1` eliminato da GitHub il
  19 agosto 2026;
- copia di lavoro locale conservata in
  `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma`;
- archivio verificato conservato in
  `F:\proggetto Meteo Friul App\documentazione ed installer\archivio legacy github\meteofriul-1.0.1-2026-08-19`;
- il bundle contiene 877 commit e 29 riferimenti Git, verificati con ripristino
  mirror e `git fsck`; patch binaria, file non tracciati e metadati GitHub sono
  archiviati separatamente;
- contiene insieme vecchio frontend, backend FastAPI, Android/Capacitor,
  Firebase Hosting, Cloud Run, workflow e strumenti editoriali;
- `backend/main.py` resta monolitico e contiene molti endpoint non necessari
  alla UI3;
- resta disponibile soltanto come riferimento e rollback manuale: il runtime
  locale UI3 non lo avvia e non lo interroga piu' per impostazione predefinita.

## Contratto runtime realmente usato dalla UI3

| Area | Endpoint | Necessita |
| --- | --- | --- |
| Home | `GET /api/weather/bootstrap` | Corrente + forecast in una sola risposta reattiva |
| Bollettino | `GET /api/weather/forecast` | Bollettino OSMER dedicato |
| Allerte | `GET /api/weather/official-alerts` | Stato ufficiale FVG |
| Meteo locale | `GET /api/weather/current` | Umidita, pressione, vento, pioggia, ore e pollini |
| Radar | `GET /api/weather/radar` | Metadati e prodotti radar disponibili |
| Eventi | `GET /api/local/events` | Raccolta locale canonica |
| Immagini eventi | `GET /api/event-images/{filename}` | Asset restituiti dai record Eventi |
| Webcam | `GET /api/live/webcams` | Manifest delle webcam attive |
| Segnalazioni | `GET/POST /api/community/reports` | Mappa sociale e invio |
| Conferme | `POST /api/community/reports/{id}/confirmation` | Conferma o smentita sociale |
| Ricerca | `GET /api/location/search` | Supporto remoto al catalogo locale |
| Reverse | `GET /api/location/reverse` | Coordinate GPS -> Comune |

Gli endpoint di audit, debug, map proxy, discover remoto, multi-weather e push
non entrano automaticamente nella nuova API. Vengono migrati solo se una
funzione approvata della nuova app li richiede.

## Struttura obiettivo

La migrazione mantiene inizialmente i percorsi correnti per evitare movimento
meccanico inutile:

```text
frontend/                 applicazione React e asset runtime
backend/                  nuova API FastAPI modulare
  app/
    api/                  route sottili per dominio
    contracts/            modelli request/response
    services/             accesso fonti, cache e normalizzazione
    repositories/         persistenza dove necessaria
  tests/
android/                  wrapper nativo, senza copia del frontend
infra/                    Firebase, Cloud Run e workflow dichiarativi
scripts/                  strumenti ripetibili di build e contenuto
docs/                     contratti e audit ancora attivi
```

I dati editoriali usati dall'app restano versionati. Materiale sorgente,
estrazioni OCR, fogli di selezione e output intermedi non devono essere
inclusi nel bundle o nella repository produttiva; possono vivere in un
archivio editoriale separato.

## Sequenza di migrazione

### Fase 0 - Baseline

Stato: completata.

- commit UI3 funzionale;
- commit backend sociale separato;
- test frontend e test mirati backend verdi;
- vecchie modifiche non correlate lasciate fuori dai commit.

### Fase 1 - Nuova repository remota

Stato: completata. La protezione server-side di `main` e' bloccata dal piano
GitHub corrente per repository private; e' attivo un guardrail locale
compensativo in attesa di GitHub Pro.

1. [x] Creare una repository privata nell'organizzazione `meteofriul`.
2. [x] Collegarla come `origin` del repository UI3 locale.
3. [x] Pubblicare `main` mantenendo tutta la cronologia UI3.
4. [ ] Attivare protezione server-side di `main` dopo l'abilitazione di
   GitHub Pro; fino ad allora usare `.githooks/pre-push`.
5. [x] Aggiungere una CI minima: test, lint e build frontend/backend.

Nome proposto: `meteofriul-app`.

La repository resta privata durante la migrazione. La visibilita pubblica si
decide solo dopo l'audit di asset, licenze e segreti.

### Fase 2 - Contratti API

Stato: completata per tutte le route runtime attualmente consumate dalla UI3.
Le fixture condivise versionate coprono `location` e `live`; `events` e
`weather` usano contratti Pydantic backend e test equivalenti nei client
frontend.

1. Congelare per ogni endpoint solo i campi consumati dalla UI3.
2. Salvare fixture di risposta valide, stale, parziali e non raggiungibili.
3. Generare ed esaminare OpenAPI dal nuovo backend.
4. Aggiungere test di contratto frontend/backend sugli stessi payload.
5. Vietare nuovi accessi rete fuori da `frontend/src/services`.

Completato per `location`:

- contratto v1 condiviso in `contracts/runtime-api/v1/location`;
- fixture comuni a test frontend e backend;
- OpenAPI della nuova API disponibile su `/api/openapi.json`;
- catalogo canonico locale dei 215 Comuni FVG;
- errore sorgente reverse esplicito, senza localita inventate.

Completato per `live`:

- contratto v1 condiviso in `contracts/runtime-api/v1/live`;
- manifest locale curato di 20 webcam, con remoto opzionale e fallback pronto;
- segnalazioni, cooldown, annullamento e conferme estratti dal monolite;
- coordinate precise non pubblicate: la mappa riceve il centro del Comune;
- catalogo unico dei 215 Comuni riusato dalla famiglia `location`;
- persistenza Firestore compatibile e memoria come fallback esplicito;
- confronto reale vecchio/nuovo senza differenze su webcam e localita.

Completato inoltre per `events` e `weather`:

- eventi e immagini, meteo corrente/bootstrap, bollettino OSMER, allerte
  ufficiali e radar sono serviti dalla nuova API modulare;
- payload e cache sono coperti da test frontend/backend;
- Open-Meteo non sostituisce il Bollettino ufficiale OSMER;
- nessuna view interroga direttamente il backend storico.

### Fase 3 - Estrazione backend per famiglie

Stato: completata per il runtime web corrente. Tutto `/api/*` viene instradato
alla nuova API UI3 sulla porta `8002`. Il backend storico `8001` non e' piu' un
fallback implicito e puo' essere avviato solo esplicitamente per confronto o
rollback con `scripts/start-dev.ps1 -WithLegacyBackend`.

Ordine consigliato:

1. [x] `location`: ricerca e reverse geocoding;
2. [x] `live`: webcam, segnalazioni e conferme;
3. [x] `events`: eventi e immagini;
4. [x] `weather-local`: current e bootstrap;
5. [x] `bulletin`: forecast OSMER e allerte ufficiali;
6. [x] `radar`: prodotti osservativi e cache;
7. `push`: dispositivi e notifiche, soltanto dopo test Android.

Per ogni famiglia:

- copiare solo parser o funzioni necessarie;
- spezzare route, servizio e persistenza;
- mantenere lo stesso URL finche la UI non richiede una versione nuova;
- confrontare nuova e vecchia risposta su casi reali;
- spostare il traffico solo dopo test di rete assente e cache presente;
- mantenere rollback verso il backend storico.

### Fase 4 - Android

Stato: rinviata. Il wrapper Android non deve essere generato finche' il web non
e' considerato completo e il proprietario dell'app non fornisce una nuova
conferma esplicita.

Asset launcher precedente: la preparazione `icon_launcher_3.0` e' superata e
non va riutilizzata. Dal 22 agosto 2026 l'unica sorgente autorizzata e'
`android/launcher-assets/approved-082026`, verificata tramite inventario e hash;
il wrapper UI3 usa le relative risorse runtime sincronizzate.

1. Creare un solo wrapper Capacitor per la build UI3.
2. Portare il bridge posizione esplicito gia coperto dai test frontend.
3. Applicare il flusso nativo startup: GPS, poi notifiche.
4. Bloccare l'orientamento verticale.
5. Integrare registrazione push senza attivare invii reali.
6. Verificare installazione pulita, upgrade, rifiuto permessi e riapertura.

Il vecchio progetto Android e' una fonte da auditare, non una cartella da
copiare integralmente.

### Fase 5 - Infrastruttura

Stato: in corso.

1. Ambiente `local`: proxy Vite verso API locale.
2. Ambiente `staging`: revisione Cloud Run UI3 con tag e traffico zero;
   frontend Hosting di anteprima attivo e collaudato.
3. Ambiente `production`: UI3 web attivata dopo smoke test e rollback scritto.
4. Segreti esclusivamente nei secret store della piattaforma.
5. Workflow separati per test, deploy web, deploy API e job pianificati.
6. Push reale disattivo fino ad approvazione esplicita.

### Fase 6 - Cutover

Stato web: completato l'11 agosto 2026. Il collaudo Android resta separato e
rinviato.

1. [x] Eseguire audit completo Home, Bollettino, Territorio, Eventi, Scopri e Almanacco.
2. [x] Verificare IT/FUR, light/dark e mobile sul web.
3. [x] Simulare rete assente con cache valida e cache scaduta.
4. [x] Verificare fonti ufficiali, timestamp e messaggi di indisponibilita.
5. [x] Pubblicare sul live lo stesso pacchetto verificato in anteprima.
6. [x] Conservare frontend e backend precedenti per la finestra di rollback.
7. [ ] Collaudare Android reale solo dopo autorizzazione esplicita.

## Dati e asset

Il repository UI3 contiene attualmente una quota importante di fotografie,
sfondi e archivi editoriali. Prima del primo rilascio pubblico occorre:

- distinguere asset runtime da sorgenti editoriali;
- ottimizzare gli sfondi meteo piu pesanti;
- mantenere nel bundle solo i JSON letti dall'app;
- spostare backlog, OCR, CSV/XLSX e audit generati fuori dal runtime;
- verificare attribuzioni e licenze prima di rendere pubblica la repository.

## CSS e manutenibilita

La struttura a feature viene mantenuta. Prima del cutover:

- nessun file CSS globale aggiuntivo;
- nessun import CSS fra feature;
- nessun `!important` non documentato;
- token per colori e misure condivise;
- componenti condivisi solo quando il pattern e' davvero comune;
- controllo browser delle feature modificate, non solo test del codice.

I file CSS grandi non vengono spezzati per numero di righe: vengono divisi
solo quando emergono responsabilita autonome e verificabili.

## Criteri di completamento

La migrazione e' conclusa quando:

- la UI3 usa esclusivamente la nuova API;
- nessuna route produttiva dipende dal vecchio frontend;
- ogni endpoint usato ha contratto e test;
- cache e indisponibilita non svuotano dati ancora validi;
- Android usa una sola build UI3;
- CI e deploy sono ripetibili;
- esiste rollback documentato;
- il repository storico remoto e' stato rimosso e l'archivio locale non riceve
  piu nuove funzioni applicative.

## Collaudo indipendenza backend storico

Eseguito il 10 agosto 2026:

- Home, Bollettino, Territorio, Eventi, Scopri, Almanacco e Impostazioni
  verificate nel browser con la porta `8001` spenta;
- nessun caricamento bloccato, errore fatale, contenuto indisponibile o errore
  console durante il percorso completo;
- con API UI3 spenta e cache gia' presente, Home, Bollettino, Territorio ed
  Eventi mantengono i dati salvati senza svuotare le schermate;
- i test di dominio rifiutano le cache oltre la rispettiva finestra quando la
  fonte e' assente: Home meteo, Bollettino ufficiale, dati meteo locali, radar,
  Eventi, webcam e segnalazioni community;
- il proxy generico verso `8001` e' stato rimosso dopo il collaudo.

## Collaudo Cloud Run senza traffico

Eseguito l'11 agosto 2026 sulla revisione
`meteofriul-api-ui3-6ff34ce`, tag `ui3-6ff34ce`:

- traffico produttivo lasciato al 100% sulla revisione legacy;
- tutte le route runtime UI3 verificate direttamente: meteo, Bollettino,
  Eventi, webcam, segnalazioni, ricerca/reverse localita e radar;
- frontend completo verificato contro la revisione Cloud tramite proxy di
  collaudo: Home, Bollettino, Territorio, Eventi, Scopri, Almanacco e
  Impostazioni;
- controllo IT/light e FUR/dark senza errori fatali, caricamenti bloccati o
  overflow orizzontali;
- Firestore verificato con creazione, rilettura e cancellazione di una
  segnalazione temporanea;
- lettura allerte resa immediata quando lo snapshot persistente manca: nessun
  tentativo diretto lento durante una normale richiesta utente;
- sincronizzazione programmata allerte lasciata manuale perche' la fonte
  regionale non e' raggiungibile in modo affidabile da Cloud Run o GitHub
  Actions;
- vecchio workflow GitHub `Sync official FVG alerts` disattivato nel
  repository `meteofriul-1.0.1` prima della successiva rimozione del remoto;
  i job Cloud Scheduler push legacy restano sospesi.

La revisione di collaudo e' stata poi sostituita, sempre a traffico zero, da
`meteofriul-api-ui3-clean-1530ad0`, tag `ui3-clean-1530ad0`. Il nuovo template
contiene soltanto `FIREBASE_PROJECT_ID`, `COMMUNITY_STORAGE` e
`OFFICIAL_ALERTS_DIRECT_FETCH_ON_READ`: i riferimenti ereditati ai segreti
legacy push e santo sono stati rimossi.

Durante la stabilizzazione il tag `ui3-clean-1530ad0` e' stato spostato, dopo
collaudo a traffico zero, sulla revisione
`meteofriul-api-ui3-hotfix-643096d`. Il fix impedisce alle letture Firestore e
ai refresh pubblici delle allerte di saturare i worker. Hosting, versione del
frontend e traffico Cloud Run non taggato sono rimasti invariati.

Nota di nomenclatura: dal passaggio dell'11 agosto alle 21:35 circa il nome del
tag `ui3-clean-1530ad0` non corrisponde piu' alla revisione che risolve. Il
nome e' mantenuto temporaneamente per stabilita' del rewrite Hosting; nei
controlli occorre verificare la revisione effettiva
`meteofriul-api-ui3-hotfix-643096d`. Un tag allineato andra' valutato soltanto
dopo la stabilizzazione, con modifica controllata del rewrite e smoke test.

## Collaudo Firebase Hosting di anteprima

Eseguito l'11 agosto 2026 sul canale temporaneo `ui3-beta`:

- URL di collaudo:
  `https://meteo-friul--ui3-beta-yamdts9p.web.app`;
- sito pubblico `https://meteo-friul.web.app` lasciato invariato;
- rewrite `/api/**` collegato alla revisione UI3 di Cloud Run tramite il
  `pinTag` `ui3-clean-1530ad0`: al momento del collaudo risolveva la revisione
  omonima; dalle 21:35 circa risolve
  `meteofriul-api-ui3-hotfix-643096d`;
- Home, Bollettino, Territorio, Eventi, Scopri, Almanacco e Impostazioni
  verificate sul dominio remoto in IT/light e FUR/dark;
- nessun errore fatale, caricamento bloccato o overflow orizzontale;
- meteo, Eventi, 20 webcam, segnalazioni Firestore e radar verificati
  attraverso Hosting;
- CI del commit di configurazione Hosting completata con esito positivo;
- assenza dello snapshot regionale delle allerte esposta dall'API come
  `official_alerts_unavailable`; la UI non costruisce un'allerta attiva e non
  deduce un falso stato verde.

Prima del cutover il canale Hosting live stabile e' stato copiato nel canale
temporaneo `pre-ui3`, URL
`https://meteo-friul--pre-ui3-vmis6dza.web.app`. Il backup conserva il frontend
precedente e il tag Cloud Run `ui3-71f9d49`. Un successivo workflow legacy di
aggiornamento webcam aveva ridistribuito automaticamente il vecchio frontend
sul live; il workflow e' stato disattivato prima del cutover e il backup stabile
non e' stato sovrascritto.

## Cutover web UI3

Eseguito l'11 agosto 2026:

- il canale `ui3-beta` e' stato clonato su `live` senza ricostruire il bundle;
- al momento del cutover `live` e `ui3-beta` usavano la versione Hosting
  `4da1ae23ee87b142` e il tag API `ui3-clean-1530ad0`, allora risolto alla
  revisione `meteofriul-api-ui3-clean-1530ad0`;
- tutte le route runtime hanno risposto correttamente attraverso il dominio
  pubblico;
- le sette sezioni sono state verificate in IT/light e FUR/dark, anche su
  viewport mobile, senza errori console, immagini interrotte o overflow;
- ricerca localita', card Eventi, mappa Territorio e webcam sono state provate
  direttamente;
- il traffico Cloud Run non taggato non e' stato spostato;
- il canale `pre-ui3` resta disponibile per il rollback.

## Prossima azione

Monitorare il live UI3 fino al 17 agosto ed eseguire la verifica formale il 18
agosto, secondo `PRODUCTION_CUTOVER_RUNBOOK.md` e
`PRODUCTION_AUTOMATION_AUDIT.md`. Chiudere poi i due lavori infrastrutturali rimasti:
migrare l'aggiornamento webcam senza deploy implicito del frontend e rendere
affidabile l'ingestione delle allerte FVG. L'API resta prudente quando manca lo
snapshot ufficiale e non deduce un falso stato verde da fonti nazionali
diagnostiche. Il wrapper Android e il push reale restano esclusi: la loro
generazione richiedera' una conferma esplicita successiva.
