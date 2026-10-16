# Meteo Friul UI 3.0.0 - Migration Map

Data: 2026-06-21
Stato: bozza operativa iniziale

## Scopo

Questo documento serve a decidere cosa prendere dalla app attuale e cosa lasciare indietro.

Fonte app attuale:

```text
F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma
```

Progetto UI 3.0.0:

```text
F:\proggetto Meteo Friul App\meteo friul - ui 3.0.0
```

Regola principale:

```text
non copiare tutto: audit -> classificazione -> import controllato -> test
```

## Classi di migrazione

| Stato | Significato |
| --- | --- |
| RIUSARE | Codice gia pulito, testabile o centrale. Si puo importare/copiare con adattamenti minimi. |
| ESTRARRE | Codice valido ma mescolato alla UI. Va separato prima di riusarlo. |
| RISCRIVERE UI | La logica e' buona, ma il componente visuale va rifatto. |
| LASCIARE LEGACY | Non serve alla UI 3.0.0 o e' troppo stratificato. |
| AUDIT | Da studiare prima di decidere. |

## Mappa iniziale

| Area | File/cartella attuale | Ruolo | Decisione iniziale | Rischio | Test minimi |
| --- | --- | --- | --- | --- | --- |
| API config | `frontend/src/utils/apiConfig.js` | Base URL API locale/prod | RIUSARE | API sbagliata in APK/prod | verify assets, build, chiamata bootstrap |
| API weather | fetch in `App.jsx` | Carica bootstrap/meteo | ESTRARRE | Rompere cache/meteo/GPS | bootstrap Pordenone/Udine, stati errore |
| API eventi | fetch/cache in `App.jsx` e `EventsView.jsx` | Eventi locali | ESTRARRE | Conteggi diversi web/APK, cache stale | Pordenone limit 12/100, cache fresh |
| Copy shell | `frontend/src/utils/appShellCopy.js` | Brand/microcopy app | RIUSARE | Fallback IT in FUR | test copy IT/FUR |
| Copy bollettino | `frontend/src/utils/bulletinViewCopy.js` | Microcopy Bollettino | RIUSARE | Confondere fonte ufficiale/traduzione | test copy, audit Bollettino FUR |
| Copy Vedi | `frontend/src/utils/liveViewCopy.js` | Microcopy Vedi | RIUSARE | Label mancanti | test copy |
| Copy Eventi | `frontend/src/utils/eventsViewCopy.js` | Microcopy Eventi | RIUSARE | Filtri/stati vuoti errati | test copy + browser |
| Copy Scopri | `frontend/src/utils/discoverCopy.js` | Microcopy Scopri | RIUSARE | FUR incompleto | test copy |
| Copy impostazioni | `frontend/src/utils/locationSelectorCopy.js` | Microcopy localita/impostazioni | RIUSARE | GPS/notifiche confuse | test copy + pannello |
| Almanacco copy | `frontend/src/utils/almanacCopy.js` | Microcopy Almanacco | RIUSARE | Stati FUR in revisione sbagliati | test copy |
| Traduzioni base | `frontend/src/translations.js` | Label meteo e UI storiche | AUDIT/ESTRARRE | Duplicazioni con copy nuovi | test chiavi usate |
| Normalizzazione meteo | `frontend/src/utils/normalizedWeather.js` | Payload meteo normalizzato | RIUSARE/ESTRARRE | Icone/meteo Home divergenti | fixture meteo, Home |
| Classificazione meteo legacy | `frontend/src/utils/weatherClassification.js` | Vecchio classificatore | AUDIT | Reintrodurre vento come marker | test semantica vento |
| Meteo icon props | `frontend/src/utils/weatherIconMapping.js` o equivalente | Mappa icone Meteocon | RIUSARE | Icone incoerenti | test Meteocon |
| OSMER adapter | `frontend/src/weather/osmerAdapter.js` | A1-A9 -> marker | RIUSARE | Perdita fedelta OSMER | fixture A1-A9, Bollettino |
| OSMER temporal | `frontend/src/weather/osmerTemporalSummary.js` | Evoluzioni/FZ | RIUSARE | Overlay vento/fulmini errati | giorni con F/Z |
| WeatherMap | `frontend/src/components/WeatherMap.jsx` | UI + logica Bollettino | ESTRARRE/RISCRIVERE UI | Mescola UI e semantica | A1-A9, overlay, browser |
| MeteoconIcon | `frontend/src/components/MeteoconIcon.jsx` | Motore icone | RIUSARE | Parser fallback legacy | render test icone |
| WeatherCard | `frontend/src/components/WeatherCard.jsx` | Home hero/meteo | RISCRIVERE UI | Dati current mal collegati | Home IT/FUR, GPS |
| WeatherDetailsGrid | `frontend/src/components/WeatherDetailsGrid.jsx` | Griglia dettagli Home | RISCRIVERE UI/RIUSARE LOGICA | Dati e label sparse | dettagli Pordenone |
| DailySummary | `frontend/src/components/DailySummary.jsx` | Sintesi Home | RISCRIVERE UI | Interpretazione bollettino | testo ufficiale prudente |
| SmartAlerts | `frontend/src/components/SmartAlerts.jsx` | Toast/browser alerts | RIUSARE/ESTRARRE UI | Notifiche inutili o troppo brevi | smartToastTest |
| WeatherFlightScene | `frontend/src/components/WeatherFlightScene.jsx` | Scenetta | RIUSARE COME ENTITA | Influenza layout/logica | lab scenetta, day/night |
| Scene type | `frontend/src/utils/weatherSceneType.js` | Tipo meteo -> scena | RIUSARE | Vento marker primario | test scenetta |
| EventsView | `frontend/src/components/EventsView.jsx` | Tab Eventi | RISCRIVERE UI/ESTRARRE LOGICA | Cache/filtri rotti | Oggi/Prossimi/Immagini |
| Event ranking | `frontend/src/utils/eventWeatherFit.js` e ranking | Consiglio evento | RIUSARE | Evento consigliato errato | fixture eventi/meteo |
| LiveView | `frontend/src/components/LiveView.jsx` | Vedi/webcam/mappa/segnalazioni | RISCRIVERE UI/RIUSARE LOGICA | Segnalazioni/privacy | reports, webcam manifest |
| Webcam manifest | backend/tools/webcam | Webcam remote/local | RIUSARE | Fonte non aggiornata | health live sources |
| DiscoverView | `frontend/src/components/DiscoverView.jsx` | Scopri | RISCRIVERE UI/RIUSARE DATA | Ranking culturale alterato | discover tests |
| AlmanacView/Card | `frontend/src/components/AlmanacView.jsx`, `AlmanacCard.jsx` | Almanacco | RISCRIVERE UI/RIUSARE DATA | FUR revision state | almanac tests |
| LocationSelector | `frontend/src/components/LocationSelector.jsx` | Localita/impostazioni | RISCRIVERE UI/ESTRARRE LOGICA | GPS/default conflitto | auto location policy tests |
| Auto location policy | `frontend/src/utils/autoLocationPolicy.js` | Regole GPS | RIUSARE | Localita non aggiornata | unit tests |
| Push notifications | `frontend/src/utils/pushNotifications.js` | Registrazione push | RIUSARE | APK notifiche rotte | APK test dispositivo |
| Backend main | `backend/main.py` | API server | NON COPIARE IN UI, usare come API | Rompere servizi | health, bootstrap |
| Parser OSMER backend | `backend/parser_osmer.py` | Fonte ufficiale | RIUSARE COME BACKEND | Dato ufficiale perso | test parser |
| Eventi backend | backend eventi/sources | Fonti eventi | RIUSARE COME API | Conteggi diversi | local/events smoke |
| App.css | `frontend/src/App.css` | CSS legacy stratificato | LASCIARE LEGACY | Portarsi override e rumore | non copiare |
| App.jsx | `frontend/src/App.jsx` | Shell + molta logica | ESTRARRE, NON COPIARE | Big ball of mud | mappa funzioni |
| Assets | `frontend/src/assets`, `public` | Logo/icone/immagini | AUDIT/RIUSARE | Asset pesanti o non usati | build size |

## Prima fase concreta

1. Leggere `README.md` UI 3.0.0.
2. Creare scheletro progetto o branch laboratorio.
3. Preparare lista file da importare in ordine:
   - copy;
   - API config;
   - normalizzazione meteo;
   - OSMER adapter;
   - eventi/cache;
   - GPS policy;
   - notifiche;
   - scenetta;
   - asset.
4. Per ogni file importato, segnare:
   - perche serve;
   - quali dipendenze porta;
   - quale test lo protegge;
   - se e' temporaneo o definitivo.

## Regola anti-caos

Se un file attuale contiene insieme UI, fetch, cache e copy, non va copiato nella UI 3.0.0. Va prima scomposto.

## Audit iniziale 2026-06-21

Stato cartella UI 3.0.0:

- contiene solo documenti guida;
- non e' ancora un repository git;
- non contiene ancora `package.json`, `frontend/` o codice applicativo;
- nessun file della app attuale e' stato copiato durante questo audit.

Fonte attuale ispezionata:

```text
F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma
```

### Esito sintetico

| Area | Esito audit | Decisione aggiornata |
| --- | --- | --- |
| Setup frontend | La app attuale usa Vite, React, Capacitor, Vitest, Playwright e proxy `/api` verso backend locale. | RIUSARE COME BASE TECNICA, ma creare progetto pulito. |
| `frontend/src/App.jsx` | File di circa 3982 righe con shell, fetch meteo, cache, GPS, notifiche, pull-to-refresh e rendering. | ESTRARRE, NON COPIARE. |
| `frontend/src/App.css` | File di circa 24674 righe, CSS legacy stratificato. | LASCIARE LEGACY. |
| `frontend/src/utils/apiConfig.js` | Modulo piccolo: `API_BASE` da env o `/api`. | RIUSARE. |
| Copy in `frontend/src/utils/*Copy.js` | Moduli dedicati con test per shell, bollettino, eventi, Vedi, Scopri, Almanacco e localita. | RIUSARE. |
| Meteo normalizzato e semantica | `normalizedWeather.js`, `weatherSemantics.js`, `weatherClassification.js` hanno export e test dedicati. | RIUSARE/ESTRARRE con test. |
| OSMER | `weather/osmerAdapter.js` e `osmerTemporalSummary.js` sono moduli separati con fixture e test A1-A9. | RIUSARE. |
| `WeatherMap.jsx` | Circa 2053 righe: contiene mappa, UI, fallback testuale, marker e overlay. | ESTRARRE LOGICA, RISCRIVERE UI. |
| Eventi | `EventsView.cache.test.js` vieta fetch/cache dentro `EventsView.jsx`; la cache vive in `App.jsx`. | Mantenere contratto: view senza fetch/cache; estrarre service eventi da `App.jsx`. |
| `LiveView.jsx` | Circa 2340 righe: fetch webcam/report, MapLibre, localStorage, TTL/segnalazioni e markup insieme. | ESTRARRE servizi/policy prima; RISCRIVERE UI. |
| GPS/localita | `autoLocationPolicy.js` e' piccolo e testato; bridge GPS/reverse geocoding sta in `App.jsx`. | RIUSARE policy, ESTRARRE orchestrazione. |
| Notifiche | `pushNotifications.js` e' modulo separato, ma con endpoint backend e Capacitor dinamico. | RIUSARE con test Android quando coinvolto. |
| Scopri/Almanacco | Dati JSON, hook `useAlmanacData.js`, ranking culturale e test presenti. | RIUSARE dati/logica, RISCRIVERE UI. |
| Asset | Logo, mappa, splash, audio, sfondi e luoghi sono in `public/` e `src/assets`. | AUDIT asset per peso/uso, poi import selettivo. |

### Prima tranche consigliata

Ordine piu sicuro per creare il progetto UI 3.0.0:

1. setup frontend pulito con Vite/React e proxy `/api`;
2. token CSS e componenti base vuoti;
3. `apiConfig.js`;
4. moduli copy con relativi test;
5. semantica/normalizzazione meteo con test;
6. adapter OSMER e fixture con test;
7. policy localita/GPS senza bridge nativo;
8. services estratti da `App.jsx` per weather bootstrap ed eventi;
9. shell laboratorio `uiV3`, senza cambiare dati;
10. una tab alla volta.

### Contratti da proteggere subito

- Eventi: la view non deve fare fetch o scrivere cache direttamente.
- Bollettino: A1-A9 comandano la mappa quando presenti; vento e fulmini restano overlay.
- Home: usa dati normalizzati, non interpreta testo OSMER per decidere meteo.
- GPS: localita manuale e posizione automatica non devono contraddirsi.
- Notifiche: UI puo' rappresentarle, ma deduplica/registrazione restano in logica dedicata.
- CSS: nessun nuovo design definitivo in fondo a `App.css`.

## Fondamenta create 2026-06-21

La prima tranche implementativa ha creato solo lo scheletro frontend pulito:

```text
frontend/
  package.json
  index.html
  vite.config.js
  eslint.config.js
  src/
    app/
    ui/
      tokens/
      components/
      layout/
    features/
      lab/
```

File guida aggiunto:

```text
CSS_ARCHITECTURE.md
```

Decisioni prese:

- il codice applicativo vive in `frontend/`, i documenti guida restano alla radice;
- non e' stato creato `App.css`;
- non e' stato importato il CSS legacy della app attuale;
- i CSS nuovi usano cascade layers: `tokens`, `base`, `layout`, `components`, `features`;
- le classi condivise usano prefisso `mf-*`;
- le viste create sono solo laboratorio temporaneo `features/lab`;
- nessuna logica meteo/eventi/GPS/notifiche/OSMER e' stata importata o riscritta;
- nessun endpoint dati viene chiamato dalla shell laboratorio;
- il flag `uiV3` e' presente come lettura di laboratorio, senza cambiare dati.

### Prossima tranche consentita

Procedere in questo ordine:

1. importare OSMER adapter e fixture solo dopo avere confermato la posizione definitiva in `domain/weather` o `weather`;
2. importare semantica/normalizzazione meteo con test;
3. estrarre services weather/events da `App.jsx`, senza collegarli alle view finche' non hanno test;
4. creare la Home laboratorio usando solo dati fixture o dati gia normalizzati.

Non procedere ancora con:

- `App.jsx` attuale;
- `App.css` attuale;
- `WeatherMap.jsx` intero;
- `LiveView.jsx` intero;
- fetch eventi dentro una view;
- MapLibre o Capacitor prima della tranche dedicata.

## Import controllato 2026-06-21

Dettaglio completo in `IMPORT_LOG.md`.

Import eseguiti:

- `frontend/src/services/apiConfig.js`;
- `frontend/src/copy/appShellCopy.js` e test;
- `frontend/src/copy/bulletinViewCopy.js` e test;
- `frontend/src/copy/eventsViewCopy.js` e test;
- `frontend/src/copy/liveViewCopy.js` e test;
- `frontend/src/copy/discoverCopy.js` e test;
- `frontend/src/copy/almanacCopy.js` e test;
- `frontend/src/copy/locationSelectorCopy.js` e test;
- `frontend/src/copy/dailySummaryCopy.js` e test;
- `frontend/src/domain/geo/autoLocationPolicy.js` e test.

Adapter aggiunto:

- `frontend/src/app/uiShellCopy.js` per usare il copy shell validato senza rinominare il copy storico `map`.

Verifica:

- `npm run test`: 12 file passati, 44 test passati.
- `npm run lint`: passato.
- `npm run build`: passato.
- guardrail sorgenti: nessun `fetch(`, nessun `App.css`, nessun `!important`, nessuna view legacy importata.

Non importati in questa tranche:

- fetch meteo;
- cache eventi;
- bridge GPS;
- reverse geocoding;
- notifiche;
- OSMER adapter;
- view legacy.

## Import OSMER dominio 2026-06-21

Dettaglio completo in `IMPORT_LOG.md`.

Import eseguiti:

- `frontend/src/domain/weather/osmerAdapter.js`;
- `frontend/src/domain/weather/osmerAdapter.test.js`;
- `frontend/src/domain/weather/osmerTemporalSummary.js`;
- `frontend/src/domain/weather/osmerTemporalSummary.test.js`;
- `frontend/src/tests/fixtures/PW20260606.normalized.json`.

Adattamento:

- solo percorsi fixture nei test.

Verifica:

- `npm run test`: 14 file passati, 62 test passati.
- `npm run lint`: passato.
- `npm run build`: passato.
- guardrail sorgenti: nessun fetch, nessun CSS legacy, nessuna view legacy, nessun GPS/Capacitor.

Contratti protetti:

- A1-A9 restano fonte primaria dei marker quando presenti;
- vento non diventa marker principale;
- `valid_date` guida il merge OSMER/forecast;
- residui notturni non sporcano la sintesi del giorno quando il testo indica miglioramento;
- niente `WeatherMap.jsx` e niente UI mappa importata.

## Import normalizzazione meteo 2026-06-21

Dettaglio completo in `IMPORT_LOG.md`.

Import eseguiti:

- `frontend/src/domain/weather/normalizedWeather.js`;
- `frontend/src/domain/weather/weatherSemantics.js`;
- `frontend/src/domain/weather/weatherClassification.js`;
- `frontend/src/domain/weather/weatherAdviceContext.js`;
- `frontend/src/domain/weather/weatherSemanticTags.js`;
- `frontend/src/domain/weather/unitFormats.js`;
- `frontend/src/domain/weather/temperatureSeverity.js`;
- test associati in `frontend/src/domain/weather`.

Adattamenti:

- nessuna funzione importata modificata;
- aggiunti solo test minimi per moduli puri che non avevano test dedicato nella fonte.

Verifica:

- `npm run test`: 21 file passati, 171 test passati.
- `npm run lint`: passato.
- `npm run build`: passato.
- smoke locale `http://127.0.0.1:5174/`: HTTP 200.
- guardrail sorgenti: nessun fetch, nessun CSS legacy, nessuna view legacy, nessun GPS/Capacitor.

Contratti protetti:

- normalizzazione meteo separata dalla UI;
- semantica e classificazione non vivono in JSX o CSS;
- formati unita e soglie temperatura restano moduli testati;
- la scenetta e le view restano fuori fino alla tranche dedicata.

Non importati:

- scenetta meteo;
- componenti Home;
- `weatherSemanticsImpact.test.js`;
- ranking eventi/discover;
- hook Almanacco;
- servizi fetch.

## Estrazione servizi dati 2026-06-21

Dettaglio completo in `IMPORT_LOG.md`.

Servizi creati:

- `frontend/src/services/weatherApi.js`;
- `frontend/src/services/weatherApi.test.js`;
- `frontend/src/services/eventsApi.js`;
- `frontend/src/services/eventsApi.test.js`.

Decisione:

- i servizi sono estratti da `App.jsx`, ma non sono ancora collegati alla UI;
- `fetch` resta dietro `fetchImpl` iniettato, quindi i test non chiamano la rete;
- la UI laboratorio continua a non caricare dati reali.

Contratti protetti:

- `/weather/bootstrap` usa city obbligatoria, lat/lon quando presenti e cache buster solo con `force`;
- payload meteo deve contenere `current` e `forecast`;
- `official_alerts` e `osmer_audit` vengono normalizzati in nomi frontend stabili;
- `/local/events` mantiene la regola Home `8 -> 100` per evitare raccolte divergenti;
- coordinate eventi entrano solo se entrambe finite;
- stati backend eventi `refreshing` e `partial` restano visibili al chiamante.

Verifica:

- `npm run test`: 23 file passati, 181 test passati.
- `npm run lint`: passato.
- `npm run build`: passato.
- smoke locale `http://127.0.0.1:5174/`: HTTP 200.
- guardrail: nessun servizio dati importato da app/features/ui.

Non ancora migrato:

- cache meteo `localStorage`;
- cache eventi `localStorage`;
- orchestrazione refresh;
- controlli stale-location;
- retry timer eventi;
- collegamento alla Home o alla tab Eventi.

## Estrazione cache e chiavi 2026-06-21

Dettaglio completo in `IMPORT_LOG.md`.

Moduli creati:

- `frontend/src/domain/geo/locationCacheKey.js`;
- `frontend/src/domain/geo/locationCacheKey.test.js`;
- `frontend/src/services/jsonCache.js`;
- `frontend/src/services/jsonCache.test.js`;
- `frontend/src/services/weatherCache.js`;
- `frontend/src/services/weatherCache.test.js`;
- `frontend/src/services/eventsCache.js`;
- `frontend/src/services/eventsCache.test.js`.

Decisione:

- la cache e' stata estratta come infrastruttura pura, non collegata alla UI;
- storage e clock sono iniettati nei test;
- la chiave localita conserva il formato della app attuale;
- la cache Eventi mantiene `eventsCache:v10`, `single-source-v1` e preferenza per la raccolta canonica `100`.

Contratti protetti:

- city trim/lowercase nelle chiavi cache;
- coordinate a 4 decimali;
- cache JSON valida solo se fresca;
- JSON corrotto rimosso senza errori utente;
- cache meteo con prefisso `weatherBootstrapCache:v2`;
- rilevamento testo ufficiale OSMER in cache meteo;
- cache Eventi full `100` preferita alla home `8`;
- fallback alla home `8` mantenuto solo per compatibilita;
- payload Eventi sempre marcato con schema.

Verifica:

- `npm run test`: 27 file passati, 196 test passati.
- `npm run lint`: passato.
- `npm run build`: passato.
- smoke locale `http://127.0.0.1:5174/`: HTTP 200.
- guardrail: nessun modulo cache importato da app/features/ui.

Non ancora migrato:

- timer retry Eventi;
- active-location/stale-location guard;
- refresh foreground;
- pull-to-refresh;
- reverse geocoding;
- reset cache da impostazioni;
- collegamento servizi/cache alle view.

## Orchestratore dati Home 2026-06-21

Dettaglio completo in `IMPORT_LOG.md`.

Modulo creato:

- `frontend/src/features/home/homeDataController.js`;
- `frontend/src/features/home/homeDataController.test.js`.

Decisione:

- nasce il contratto dati della futura Home, ma non la UI;
- il controller compone cache, servizi e normalizzazione;
- nessuna view laboratorio o shell importa ancora il controller;
- il caricamento meteo/Eventi usa `Promise.all` per evitare waterfall quando entrambi servono.

Contratti protetti:

- cache fresca prima della rete;
- fallback meteo stale se refresh fallisce;
- Eventi da cache se disponibili;
- refresh Eventi forzato non svuota la cache visibile se fallisce;
- payload Eventi `refreshing`/`partial` non viene scritto in cache;
- stato Home mantiene separati `current`, `forecast`, `officialAlerts`, `osmerAudit`, `events`, `error`, `fromCache`, `isStale`.

Verifica:

- `npm run test`: 28 file passati, 202 test passati.
- `npm run lint`: passato.
- `npm run build`: passato.
- smoke locale `http://127.0.0.1:5174/`: HTTP 200.
- guardrail: nessun import del controller da app/ui/lab.

Non ancora migrato:

- visual Home;
- scenetta;
- card dettagli;
- eventi teaser;
- pull-to-refresh;
- retry timer;
- collegamento runtime alla shell.

## Home view model 2026-06-21

Dettaglio completo in `IMPORT_LOG.md`.

Modulo creato:

- `frontend/src/features/home/homeViewModel.js`;
- `frontend/src/features/home/homeViewModel.test.js`.

Decisione:

- il view model e' il contratto di presentazione fra `homeDataController` e la futura Home UI;
- non contiene JSX, hook o CSS;
- non e' ancora importato dalla shell o dal laboratorio;
- concentra label, formati, dettagli e stati in un posto testato.

Contratti protetti:

- meteo pronto per UI con condizione, temperatura, unita, severita, icona e overlay;
- vento resta overlay, non condizione primaria;
- dettagli Home ordinati e senza valori mancanti;
- stato stale/error/cache visibile senza perdere dati utili;
- Eventi teaser tagliato e pronto da renderizzare;
- messaggi Eventi coerenti con cache, errori e aggiornamento parziale;
- FUR rappresentato nel contratto.

Verifica:

- `npm run test`: 29 file passati, 208 test passati.
- `npm run lint`: passato.
- `npm run build`: passato.
- smoke locale `http://127.0.0.1:5174/`: HTTP 200.
- guardrail: nessun import del view model da app/ui/lab.

Non ancora migrato:

- Home UI;
- scenetta;
- layout responsive definitivo;
- CSS Home;
- binding runtime a dati reali;
- visual QA browser/mobile della Home.

## Home UI statica 2026-06-21

Dettaglio completo in `IMPORT_LOG.md`.

File creati:

- `frontend/src/features/home/homeFixture.js`;
- `frontend/src/features/home/HomeView.jsx`;
- `frontend/src/features/home/HomeWeatherHero.jsx`;
- `frontend/src/features/home/HomeDetailsGrid.jsx`;
- `frontend/src/features/home/HomeEventsTeaser.jsx`;
- `frontend/src/features/home/home.css`.

File modificati:

- `frontend/src/features/lab/HomeLabView.jsx`;
- `frontend/src/ui/index.css`;
- `frontend/src/ui/components/components.css`;
- `frontend/src/ui/layout/layout.css`.

Decisione:

- prima Home visuale reale, ma statica e in laboratorio;
- la Home usa una fixture generata dal view model, non dati live;
- i componenti visuali non importano controller/cache/servizi;
- il CSS resta nella feature Home;
- la shell usa `main` scrollabile e bottom nav statica per evitare sovrapposizioni.

Verifica:

- `npm run test`: 29 file passati, 208 test passati.
- `npm run lint`: passato.
- `npm run build`: passato.
- smoke locale `http://127.0.0.1:5174/`: HTTP 200.
- QA browser Edge: mobile `390x844`, desktop `920x900`, mobile scroll Eventi.

Non ancora migrato:

- binding runtime a `homeDataController`;
- stati live loading/error reali;
- scenetta meteo;
- pull-to-refresh;
- GPS;
- dati produzione;
- visual QA su telefono reale/APK.

## Ridisegno Home moderno 2026-06-21

Dettaglio completo in `IMPORT_LOG.md`.

File modificati:

- `frontend/src/features/home/HomeView.jsx`;
- `frontend/src/features/home/HomeWeatherHero.jsx`;
- `frontend/src/features/home/HomeDetailsGrid.jsx`;
- `frontend/src/features/home/HomeEventsTeaser.jsx`;
- `frontend/src/features/home/home.css`;
- `frontend/src/features/home/homeViewModel.js`;
- `frontend/src/ui/layout/layout.css`;
- `frontend/index.html`;
- `frontend/public/favicon.svg`.

Decisione:

- la Home adotta una gerarchia mobile moderna: hero meteo forte, bento 2x2 essenziale, Eventi secondari;
- i dettagli tecnici secondari restano nel modello ma non nella prima gerarchia Home;
- la UI non modifica servizi, cache, normalizzazione, OSMER, GPS o notifiche;
- il CSS resta feature-scoped e non introduce `App.css`;
- la shell nasconde la scrollbar interna per una resa piu app-like;
- il favicon SVG elimina il 404 console su browser.

Verifica:

- `npm run test`: 29 file passati, 208 test passati.
- `npm run lint`: passato.
- `npm run build`: passato.
- smoke locale `http://127.0.0.1:5174/`: HTTP 200.
- QA browser: mobile `390x844`, desktop `1280x900`, console pulita, bottom nav Eventi funzionante.

Non ancora migrato:

- dati live nella Home;
- stati runtime loading/error reali;
- scenetta meteo definitiva;
- sheet/modale cambio localita;
- pull-to-refresh;
- telefono reale/APK.

## Personalita visuale Home 2026-06-21

Dettaglio completo in `IMPORT_LOG.md`.

Asset aggiunti:

- `frontend/public/brand/logo-eagle-header.png`;
- `frontend/public/brand/logo-eagle-mark.png`;
- `frontend/public/brand/logo-eagle-mark.webp`;
- `frontend/public/backgrounds/home-friuli-landscape.png`;
- `frontend/public/backgrounds/home-friuli-landscape.webp`.

File modificati:

- `frontend/src/ui/layout/AppHeader.jsx`;
- `frontend/src/ui/layout/layout.css`;
- `frontend/src/ui/base.css`;
- `frontend/src/ui/tokens/colors.css`;
- `frontend/src/features/home/HomeWeatherHero.jsx`;
- `frontend/src/features/home/HomeDetailsGrid.jsx`;
- `frontend/src/features/home/home.css`.

Decisione:

- la Home precedente era ordinata ma ancora troppo generica;
- il nuovo passaggio introduce un segno brand controllato e una hero territoriale;
- i dati restano code-native e leggibili sopra l'asset;
- gli asset serviti sono WebP ottimizzati;
- nessun modulo dati o servizio e' stato collegato o cambiato.

Verifica:

- `npm run test`: 29 file passati, 208 test passati.
- `npm run lint`: passato.
- `npm run build`: passato.
- QA browser: mobile `390x844`, desktop `1280x900`, console pulita, asset WebP caricati, bottom nav Eventi funzionante.

Non ancora migrato:

- scenetta meteo definitiva;
- personalizzazione per condizioni diverse da sereno;
- asset specifici per pioggia/neve/notte;
- telefono reale/APK;
- binding live al controller Home.

## Gerarchia informativa Home 2026-06-21

Dettaglio completo in `IMPORT_LOG.md`.

File aggiunti:

- `frontend/src/features/home/HomeBulletinSummary.jsx`;
- `frontend/src/features/home/HomeAlmanacTeaser.jsx`.

File modificati:

- `frontend/src/features/home/homeViewModel.js`;
- `frontend/src/features/home/homeFixture.js`;
- `frontend/src/features/home/HomeView.jsx`;
- `frontend/src/features/home/HomeWeatherHero.jsx`;
- `frontend/src/features/home/home.css`;
- `frontend/src/ui/layout/layout.css`;
- `frontend/src/app/App.jsx`;
- `frontend/src/app/AppRoutes.jsx`;
- `frontend/src/features/lab/HomeLabView.jsx`.

Decisione:

- la Home non deve esporre termini tecnici come `cache` nella hero;
- la Home deve avere una sintesi bollettino e una sezione Almanacco gia nella gerarchia primaria;
- i componenti nuovi sono presentazionali e ricevono testo gia pronto dal view model;
- la lingua IT/FUR passa alla Home laboratorio, ma resta dentro dati statici;
- la sintesi bollettino non interpreta testo OSMER e non sostituisce la vista Bollettino.

Verifica:

- `npm run test`: 29 file passati, 209 test passati.
- `npm run lint`: passato.
- `npm run build`: passato.
- Browser integrato: reload Home pulito, console pulita dopo reload, click `Eventi` funzionante.
- Browser viewport `390px`: nessun overflow orizzontale.
- Screenshot Edge headless: preview `500x844` e desktop `1280x900`.

Non ancora migrato:

- bollettino live dentro la Home;
- almanacco live dentro la Home;
- azioni reali dei CTA Home;
- stati loading/error reali per le due sezioni;
- telefono reale/APK.

## Rifinitura maturita Home 2026-06-21

Dettaglio completo in `IMPORT_LOG.md`.

File modificati:

- `frontend/src/ui/layout/TabPage.jsx`;
- `frontend/src/features/lab/HomeLabView.jsx`;
- `frontend/src/features/home/HomeView.jsx`;
- `frontend/src/ui/layout/layout.css`;
- `frontend/src/features/home/home.css`.

Decisione:

- la Home non mostra piu il titolo visuale `Home`, ma mantiene l'H1 accessibile;
- la hero resta identitaria, ma viene disciplinata in altezza e trattamento immagine;
- i dati meteo primari restano subito sotto la hero;
- Eventi sale prima di Bollettino e Almanacco per essere visibile nel primo viewport;
- Bollettino e Almanacco restano sezioni Home, non vengono rimossi;
- il mark aquila viene reso meno pesante tramite trattamento CSS, senza cambiare asset.

Verifica:

- `npm run test`: 29 file passati, 209 test passati.
- `npm run lint`: passato.
- `npm run build`: passato.
- Browser integrato: reload Home pulito, console pulita, click `Eventi` funzionante.
- Browser viewport `390x844`: nessun overflow orizzontale, prima card Eventi sopra la bottom nav.
- Screenshot locali: mobile compatto `500x844`, desktop `1280x900`.

Non ancora migrato:

- varianti meteo;
- mark/logo semplificato come nuovo asset vettoriale;
- binding live a dati reali;
- telefono reale/APK.

## Rifinitura Eventi e avvisi Home 2026-06-21

Dettaglio completo in `IMPORT_LOG.md`.

File modificati:

- `frontend/src/features/home/HomeEventsTeaser.jsx`;
- `frontend/src/features/home/homeViewModel.js`;
- `frontend/src/features/home/homeViewModel.test.js`;
- `frontend/src/features/home/home.css`.

Decisione:

- la Home deve mostrare Eventi come anteprima editoriale, non come mini-lista che finisce sotto la navigazione;
- il componente renderizza un solo evento in evidenza, mantenendo totale e CTA verso la tab Eventi;
- gli avvisi ufficiali restano gli stessi dati, ma il chip Home usa copy leggibile e compatto;
- il CSS resta nella feature Home e aggiunge solo la variante `mf-home-event--featured`.

Verifica:

- `npm run test`: 29 file passati, 210 test passati.
- `npm run lint`: passato.
- `npm run build`: passato.
- guardrail: nessun fetch fuori controllo, nessun `App.css`, nessun `!important`, nessun import legacy.

Non ancora migrato:

- binding live a dati reali;
- navigazione reale dei CTA Home;
- telefono reale/APK.

## Header senza badge laboratorio 2026-06-21

Dettaglio completo in `IMPORT_LOG.md`.

File modificati:

- `frontend/src/ui/layout/AppHeader.jsx`;
- `frontend/src/ui/layout/AppShell.jsx`;
- `frontend/src/app/uiShellCopy.js`;
- `frontend/src/ui/layout/layout.css`.

Decisione:

- l'indicazione `Lab UI 3` e' una nota di sviluppo, non un elemento utile per l'utente;
- la shell puo' mantenere lo stato laboratorio internamente, senza esporlo nell'header;
- l'header resta concentrato su brand, lingua e impostazioni.

Verifica:

- `npm run test`: 29 file passati, 210 test passati.
- `npm run lint`: passato.
- `npm run build`: passato.
- guardrail: nessun `Lab UI 3`, nessuna `labLabel`, nessun fetch fuori controllo, nessun CSS legacy.

## Microtesto aggiornamento Home 2026-06-21

Dettaglio completo in `IMPORT_LOG.md`.

File modificati:

- `frontend/src/features/home/HomeWeatherHero.jsx`;
- `frontend/src/features/home/homeViewModel.js`;
- `frontend/src/features/home/homeViewModel.test.js`;
- `frontend/src/features/home/homeFixture.js`;
- `frontend/src/features/home/home.css`.

Decisione:

- l'aggiornamento e' un'informazione secondaria e non deve apparire come pill;
- la Home mostra `Aggiornato 5 minuti fa` come microtesto semplice;
- il calcolo del testo relativo vive nel view model, non nel componente visuale;
- l'avviso meteo resta l'unico elemento evidenziato nella riga inferiore della hero.

Verifica:

- `npm run test`: 29 file passati, 211 test passati.
- `npm run lint`: passato.
- `npm run build`: passato.
- Browser integrato mobile/desktop: testo senza background, bordo o radius da pill.

## Microtesto allerta Home 2026-06-21

Dettaglio completo in `IMPORT_LOG.md`.

File modificati:

- `frontend/src/features/home/HomeWeatherHero.jsx`;
- `frontend/src/features/home/homeViewModel.js`;
- `frontend/src/features/home/homeViewModel.test.js`;
- `frontend/src/features/home/home.css`.

Decisione:

- l'allerta deve richiamare attenzione senza sembrare un controllo o una pill;
- fallback Home: `Allerta ufficiale`;
- label specifiche future, come `Caldo intenso`, possono arrivare dal dato senza logica nel JSX;
- l'alert text resta presentazione, non cambia fonte o policy delle allerte.

Verifica:

- `npm run test`: 29 file passati, 212 test passati.
- `npm run lint`: passato.
- `npm run build`: passato.
- guardrail: nessun `Avviso meteo`, nessuna classe `mf-home-insight`, nessun CSS legacy.

## Allerta ufficiale azionabile Home 2026-06-21

Dettaglio completo in `IMPORT_LOG.md`.

File modificati:

- `frontend/src/features/home/HomeWeatherHero.jsx`;
- `frontend/src/features/home/HomeView.jsx`;
- `frontend/src/features/lab/HomeLabView.jsx`;
- `frontend/src/app/AppRoutes.jsx`;
- `frontend/src/app/App.jsx`;
- `frontend/src/features/home/homeViewModel.js`;
- `frontend/src/features/home/homeViewModel.test.js`;
- `frontend/src/features/home/home.css`.

Decisione:

- l'allerta ufficiale in Home e' un richiamo con icona, non una pill;
- e' azionabile solo se proviene da `officialAlerts`;
- il target e' `Bollettino`, con destinazione semantica `official-alerts`;
- label specifiche future, come `Caldo intenso`, restano dati di view model;
- avvisi non ufficiali non devono diventare CTA.

Verifica:

- `npm run test`: 29 file passati, 212 test passati.
- `npm run lint`: passato.
- `npm run build`: passato.
- Browser mobile `390x844`: click su `Allerta ufficiale` -> tab `Bollettino`, console pulita.

## Label brevi allerta Home 2026-06-21

Dettaglio completo in `IMPORT_LOG.md`.

File modificati:

- `frontend/src/features/home/homeViewModel.js`;
- `frontend/src/features/home/homeViewModel.test.js`.

Decisione:

- Home mostra prima il livello colore: `Allerta gialla`, `Allerta arancione`, `Allerta rossa`;
- se ci sono piu' allerte, Home mostra il livello piu' alto disponibile;
- se manca il colore, Home usa fenomeni corti come `Allerta temporali`;
- Home non mostra headline lunghe o formule prolisse tipo `Allerta ufficiale: ...`;
- il dettaglio testuale ufficiale resta nel Bollettino.

Verifica:

- `npm run test -- homeViewModel`: 1 file passato, 13 test passati.
- `npm run test`: 29 file passati, 215 test passati.
- `npm run lint`: passato.
- `npm run build`: passato.
- Browser mobile `390x844`: `Allerta gialla` visibile, click verso `Bollettino`, console pulita.

## Tono colore allerta Home 2026-06-21

Dettaglio completo in `IMPORT_LOG.md`.

File modificati:

- `frontend/src/features/home/homeViewModel.js`;
- `frontend/src/features/home/HomeWeatherHero.jsx`;
- `frontend/src/features/home/home.css`;
- `frontend/src/features/home/homeViewModel.test.js`.

Decisione:

- il triangolo segnala allerta ufficiale;
- `yellow`, `orange`, `red` rappresentano solo livelli colore ufficiali;
- `neutral` rappresenta un'allerta ufficiale senza livello colore disponibile;
- la Home non inventa un colore giallo quando il dato contiene solo fenomeni come temporali/vento/caldo;
- il colore e' un tono di presentazione derivato dal view model, non dal testo visibile.

Verifica:

- `npm run test -- homeViewModel`: 1 file passato, 13 test passati.
- `npm run test`: 29 file passati, 215 test passati.
- `npm run lint`: passato.
- `npm run build`: passato.
- Browser mobile `390x844`: `Allerta gialla` con classe `mf-home-alert-text--yellow`, click verso `Bollettino`, console pulita.

## Hero Home immagine pulita 2026-06-21

Dettaglio completo in `IMPORT_LOG.md`.

File modificati:

- `frontend/src/features/home/HomeWeatherHero.jsx`;
- `frontend/src/features/home/home.css`.

Decisione:

- rimuovere effetti decorativi sopra la foto prima di creare le varianti meteo;
- usare la foto come segnale visivo principale;
- mantenere solo uno scrim leggero per leggibilita';
- non usare texture diagonali, bagliori radiali o forme sceniche finte nella hero.

Verifica:

- `npm run test`: 29 file passati, 215 test passati.
- `npm run lint`: passato.
- `npm run build`: passato.
- Browser mobile `390x844`: foto pulita, no texture/radial/river/ridge, testo leggibile, console pulita.

## Varianti meteo Home 2026-06-21

Dettaglio completo in `IMPORT_LOG.md`.

File modificati:

- `frontend/src/features/home/homeViewModel.js`;
- `frontend/src/features/home/HomeWeatherHero.jsx`;
- `frontend/src/features/home/home.css`;
- `frontend/src/features/home/homeViewModel.test.js`.

Decisione:

- varianti Home supportate: `clear`, `partly`, `cloud`, `rain`, `storm`, `snow`, `fog`, `night`;
- mapping nel view model, rendering tramite `data-weather-variant`;
- CSS a variabili, senza sovrascritture sparse;
- icona hero coerente con `weather.icon.type`;
- dark mode annotata come fase successiva dopo varianti.

Verifica:

- `npm run test -- homeViewModel`: 1 file passato, 15 test passati.
- `npm run test`: 29 file passati, 217 test passati.
- `npm run lint`: passato.
- `npm run build`: passato.
- Browser mobile `390x844`: `clear` reale verificato, icona `lucide-sun`, click allerta verso `Bollettino`.

## Preview laboratorio varianti meteo Home 2026-06-21

Dettaglio completo in `IMPORT_LOG.md`.

File aggiunti:

- `frontend/src/features/lab/homeVariantPreview.js`;
- `frontend/src/features/lab/homeVariantPreview.test.js`.

File modificati:

- `frontend/src/features/lab/HomeLabView.jsx`;
- `frontend/src/features/lab/lab.css`.

Decisione:

- la preview serve solo a confrontare le varianti meteo gia implementate;
- il controllo resta nel laboratorio e passa un modello statico demo a `HomeView`;
- non vengono chiamati servizi, cache, GPS, notifiche o OSMER;
- i dati demo rendono coerenti icona, temperatura e quattro dettagli principali;
- il CSS resta scoped a `features/lab`.

Verifica:

- `npm run test -- homeVariantPreview`: 1 file passato, 3 test passati.
- `npm run test`: 30 file passati, 220 test passati.
- `npm run lint`: passato.
- `npm run build`: passato.
- Browser QA: click su `Pioggia`, `Temporale`, `Neve`, `Notte` aggiorna variante, icona e dettagli.

## Background meteo hero Home 2026-06-21

Dettaglio completo in `IMPORT_LOG.md`.

File modificati:

- `frontend/src/features/home/home.css`;
- `frontend/src/features/home/homeViewModel.js`;
- `frontend/src/features/home/HomeWeatherHero.jsx`;
- `frontend/src/features/home/homeViewModel.test.js`;
- `frontend/src/features/lab/homeVariantPreview.js`;
- `frontend/src/features/lab/homeVariantPreview.test.js`.

Asset generati:

- `frontend/public/backgrounds/nebbia.webp`;
- `frontend/public/backgrounds/neve.webp`;
- `frontend/public/backgrounds/notte.webp`;
- `frontend/public/backgrounds/notte_e_neve.webp`;
- `frontend/public/backgrounds/notte_e_nuvoloso.webp`;
- `frontend/public/backgrounds/notte_e_pioggia.webp`;
- `frontend/public/backgrounds/notte_e_temporale.webp`;
- `frontend/public/backgrounds/nuvoloso.webp`;
- `frontend/public/backgrounds/pioggia.webp`;
- `frontend/public/backgrounds/temporale.webp`.

Decisione:

- usare asset meteo reali invece di sole variabili/tinte;
- mantenere la foto base solo per `clear` e `partly`;
- supportare notte come dimensione combinata per nuvoloso, pioggia, temporale e neve;
- mantenere la logica nel view model e la resa nel CSS.

Verifica:

- `npm run test -- homeViewModel homeVariantPreview`: 2 file passati, 20 test passati.
- `npm run test`: 30 file passati, 222 test passati.
- `npm run lint`: passato.
- `npm run build`: passato.
- Browser QA: `Neve` usa `neve.webp`, `Neve notte` usa `notte_e_neve.webp`, console pulita.

## Header brand UI 3

Intervento mirato 2026-06-21:

- recuperata la gerarchia della vecchia UX: aquila, titolo bi-colore, sottotitolo;
- titolo visibile `Meteo Friûl`;
- sottotitolo letto da `appShellCopy.brandTagline`, senza nuova copy hardcoded nel componente;
- azioni header a destra non modificate;
- stile confinato a `frontend/src/ui/layout/layout.css`;
- nessun `App.css`, nessun `!important`, nessuna logica dati modificata.

## Separazione Home normale / Home laboratorio

Intervento mirato 2026-06-22:

- la route Home normale usa `HomeView` dentro `TabPage`, senza il controllo tecnico `Varianti meteo`;
- `HomeLabView` resta la superficie di prova per le varianti meteo;
- `AppRoutes` sceglie `HomeLabView` solo quando `labEnabled` e' esplicitamente attivo;
- `readUiV3LabFlag` torna `false` di default;
- `?uiV3=1` continua a permettere QA delle varianti;
- nessuna fetch, cache, GPS, notifica, OSMER o logica Eventi modificata.

## Palette e tema dark

Intervento mirato 2026-06-22:

- palette light resa meno fredda tramite token in `frontend/src/ui/tokens/colors.css`;
- dark mode introdotta come set di token `html[data-theme="dark"]`;
- tema risolto da `frontend/src/app/themePreference.js`;
- `?theme=dark` abilita la preview dark, default light;
- superfici Home e bottom nav leggono token dedicati, evitando sovrascritture locali;
- bottom nav attiva usa token `--mf-nav-active-*`: oro come accento di stato, non come pulsante pieno;
- oro identitario unico: brand, iniziali FUR e accenti principali usano `--mf-gold`; gli alpha derivano da `--mf-gold-rgb`;
- nessuna logica dati modificata.

## Tabella da completare durante l'audit

| File | Dipendenze | Output | Stato | Note |
| --- | --- | --- | --- | --- |
| `frontend/src/utils/apiConfig.js` | `import.meta.env` | `API_BASE` | RIUSARE | Serve subito per servizi API. |
| `frontend/src/utils/*Copy.js` | nessuna o dipendenze minime | copy IT/FUR | RIUSARE | Importare con test dedicati. |
| `frontend/src/utils/normalizedWeather.js` | `weatherClassification`, `weatherSemantics` | meteo normalizzato/icon props | RIUSARE/ESTRARRE | Portare anche test e dipendenze semantiche. |
| `frontend/src/weather/osmerAdapter.js` | fixture OSMER, test | A1-A9, merge by `valid_date`, marker | RIUSARE | Protegge regole bollettino gia validate. |
| `frontend/src/weather/osmerTemporalSummary.js` | `osmerAdapter` | sintesi temporale | RIUSARE | Portare insieme ai test. |
| `frontend/src/App.jsx` | molte utility, componenti, storage, fetch | orchestrazione app | ESTRARRE | Non copiare come base. |
| `frontend/src/App.css` | globale | stile legacy | LASCIARE LEGACY | Non usare come fondazione UI 3.0.0. |
| `frontend/src/components/EventsView.jsx` | copy eventi, API base per immagini | lista/filtri eventi | RISCRIVERE UI | Mantenere view senza fetch/cache. |
| `frontend/src/components/WeatherMap.jsx` | OSMER adapter, UI mappa | mappa bollettino | ESTRARRE/RISCRIVERE UI | Separare zone/marker/overlay dalla presentazione. |
| `frontend/src/components/LiveView.jsx` | API, MapLibre, localStorage | Vedi/webcam/report | ESTRARRE/RISCRIVERE UI | Prima servizi e policy, poi UI. |
| `frontend/src/utils/autoLocationPolicy.js` | nessuna | regole auto-location | RIUSARE | Bridge GPS e reverse geocoding restano da estrarre. |
| `frontend/src/utils/pushNotifications.js` | Capacitor dinamico, backend API | registrazione push | RIUSARE | Test APK solo quando notifiche sono coinvolte. |
| `frontend/src/hooks/useAlmanacData.js` | JSON almanacco, ranking, moon/semantic tags | dati Almanacco/Scopri | RIUSARE | UI editoriale da riscrivere separatamente. |

## Tabella import realizzati

| File target | Origine | Stato | Note |
| --- | --- | --- | --- |
| `frontend/src/services/apiConfig.js` | `frontend/src/utils/apiConfig.js` | RIUSATO | Contratto `/api`, nessuna fetch. |
| `frontend/src/copy/appShellCopy.js` | `frontend/src/utils/appShellCopy.js` | RIUSATO | Shell via adapter UI 3. |
| `frontend/src/copy/bulletinViewCopy.js` | `frontend/src/utils/bulletinViewCopy.js` | RIUSATO | Copy Bollettino. |
| `frontend/src/copy/eventsViewCopy.js` | `frontend/src/utils/eventsViewCopy.js` | RIUSATO | Copy Eventi e filtri. |
| `frontend/src/copy/liveViewCopy.js` | `frontend/src/utils/liveViewCopy.js` | RIUSATO | Copy Vedi. |
| `frontend/src/copy/discoverCopy.js` | `frontend/src/utils/discoverCopy.js` | RIUSATO | Copy Scopri. |
| `frontend/src/copy/almanacCopy.js` | `frontend/src/utils/almanacCopy.js` | RIUSATO | Copy Almanacco. |
| `frontend/src/copy/locationSelectorCopy.js` | `frontend/src/utils/locationSelectorCopy.js` | RIUSATO | Copy localita/impostazioni. |
| `frontend/src/copy/dailySummaryCopy.js` | `frontend/src/utils/dailySummaryCopy.js` | RIUSATO | Copy sintesi giornaliera. |
| `frontend/src/domain/geo/autoLocationPolicy.js` | `frontend/src/utils/autoLocationPolicy.js` | RIUSATO | Policy pura, senza GPS bridge. |
| `frontend/src/domain/weather/osmerAdapter.js` | `frontend/src/weather/osmerAdapter.js` | RIUSATO | Dominio A1-A9, nessuna UI. |
| `frontend/src/domain/weather/osmerTemporalSummary.js` | `frontend/src/weather/osmerTemporalSummary.js` | RIUSATO | Sintesi tab OSMER, nessuna UI. |
| `frontend/src/tests/fixtures/PW20260606.normalized.json` | `frontend/src/fixtures/PW20260606.normalized.json` | RIUSATO | Fixture regressione A1-A9. |
| `frontend/src/domain/weather/normalizedWeather.js` | `frontend/src/utils/normalizedWeather.js` | RIUSATO | Normalizzazione payload meteo, nessuna UI. |
| `frontend/src/domain/weather/weatherSemantics.js` | `frontend/src/utils/weatherSemantics.js` | RIUSATO | Semantica meteo pura. |
| `frontend/src/domain/weather/weatherClassification.js` | `frontend/src/utils/weatherClassification.js` | RIUSATO | Classificazione meteo pura. |
| `frontend/src/domain/weather/weatherAdviceContext.js` | `frontend/src/utils/weatherAdviceContext.js` | RIUSATO | Contesto consigli meteo. |
| `frontend/src/domain/weather/weatherSemanticTags.js` | `frontend/src/utils/weatherSemanticTags.js` | RIUSATO | Tag/contesto semantico da meteo normalizzato. |
| `frontend/src/domain/weather/unitFormats.js` | `frontend/src/utils/unitFormats.js` | RIUSATO | Formati numerici e label unita. |
| `frontend/src/domain/weather/temperatureSeverity.js` | `frontend/src/utils/temperatureSeverity.js` | RIUSATO | Soglie temperatura. |
| `frontend/src/services/weatherApi.js` | `frontend/src/App.jsx` | ESTRATTO | Client bootstrap meteo testato, non collegato alla UI. |
| `frontend/src/services/eventsApi.js` | `frontend/src/App.jsx` | ESTRATTO | Client Eventi testato, mantiene limite canonico 100. |
| `frontend/src/domain/geo/locationCacheKey.js` | `frontend/src/App.jsx` | ESTRATTO | Chiave cache localita legacy-compatible. |
| `frontend/src/services/jsonCache.js` | `frontend/src/App.jsx` | ESTRATTO | Storage JSON con storage/clock iniettati. |
| `frontend/src/services/weatherCache.js` | `frontend/src/App.jsx` | ESTRATTO | Cache bootstrap meteo e rilevamento testo OSMER. |
| `frontend/src/services/eventsCache.js` | `frontend/src/App.jsx` | ESTRATTO | Cache Eventi schema `single-source-v1`, preferenza full 100. |
| `frontend/src/features/home/homeDataController.js` | contratti tranche 4-6 | CREATO | Orchestratore dati Home testato, non collegato alla UI. |
| `frontend/src/features/home/homeViewModel.js` | contratti tranche 7 + copy/meteo | CREATO | Contratto presentazione Home testato, non collegato alla UI. |
| `frontend/src/features/home/HomeView.jsx` | `homeViewModel` fixture | CREATO | Prima Home UI statica laboratorio. |
| `frontend/src/features/home/home.css` | token UI 3 | CREATO | CSS feature Home isolato. |
| `frontend/public/favicon.svg` | nuovo asset UI 3 | CREATO | Favicon SVG minimale per console pulita e identita base. |
| `frontend/public/brand/logo-eagle-mark.webp` | `logo-eagle-header.png` fonte attuale | RIUSATO/OTTIMIZZATO | Marchio header UI 3. |
| `frontend/public/backgrounds/home-friuli-landscape.webp` | asset generato UI 3 | CREATO/OTTIMIZZATO | Hero territoriale Home. |
| `frontend/src/ui/layout/AppHeader.jsx` | `uiShellCopy` + logo aquila | AGGIORNATO | Header brand con titolo, sottotitolo e azioni invarianti. |
| `frontend/src/app/AppRoutes.jsx` | `labEnabled`, Home/Lab views | AGGIORNATO | Home normale separata dalla preview varianti meteo. |
| `frontend/src/app/themePreference.js` | query/storage/system theme | CREATO | Contratto tema UI 3 light/dark, default light. |
| `frontend/src/ui/tokens/colors.css` | token tema | AGGIORNATO | Token `--mf-nav-active-*` per navbar attiva light/dark. |
| `frontend/src/ui/tokens/colors.css` | token oro | AGGIORNATO | `--mf-gold` unico per brand/accenti, `--mf-gold-rgb` per alpha. |
| `frontend/src/features/bulletin/BulletinView.jsx` | nuova vista UI 3 | CREATO | Prima pagina Bollettino autonoma con mappa Meteo Friul. |
| `frontend/src/features/bulletin/BulletinMap.jsx` | mappa SVG UI 3 | CREATO | Base cartografica interna e overlay dati proprietario. |
| `frontend/src/features/bulletin/bulletinFixture.js` | fixture overlay UI | CREATO | Punti, icone e badge mappa; nessuna fetch. |
| `frontend/src/features/bulletin/bulletin.css` | token UI 3 | CREATO | CSS feature Bollettino isolato. |
| `frontend/src/data/almanac/*.json` | `frontend/src/data/almanac/*.json` | RIUSATO | Santi, proverbi, consigli terra e schedule importati come archivi controllati. |
| `frontend/src/data/ostermannCulturalDiscover.json` | `frontend/src/data/ostermannCulturalDiscover.json` | RIUSATO | Tradizioni filtrate per `section: almanacco`; Scopri usera' la stessa base piu' avanti. |
| `frontend/src/data/almanac/ostermannProverbSources.json` | audit Ostermann locale | CREATO | Piano pagine sorgenti per ampliare i proverbi senza promuovere candidati grezzi nella UI. |
| `frontend/src/data/almanac/proverbCandidates.json` | nuovo archivio editoriale | CREATO | Staging area per candidati Ostermann non pubblicabili automaticamente. |
| `frontend/src/data/almanac/proverbCandidateReview.json` | review editoriale UI 3 | CREATO | Giudizi editoriali separati dai candidati grezzi: promo, varianti, archivio, hold. |
| `frontend/src/data/ostermann/sourceCatalog.json` | indice normalizzato Ostermann + piano P1 | CREATO | Catalogo pagine prioritarie per Scopri/Almanacco, non letto dalla UI. |
| `frontend/src/data/ostermann/extracts.json` | estrazione controllata Ostermann | CREATO | 26 estratti granulari con IT draft, FUR pending review e fonte pagina. |
| `frontend/src/data/ostermann/curatedLinks.json` | audit incrociato estratti/corpus curato | CREATO | 38 collegamenti verso record gia curati, per evitare duplicazioni future in Scopri. |
| `frontend/src/domain/almanac/moonPhase.js` | `frontend/src/utils/moonPhase.js` | ESTRATTO/RIUSATO | Calcolo lunare puro, senza emoji/mojibake e senza UI. |
| `frontend/src/domain/almanac/sunCycle.js` | nuovo modulo UI 3 | CREATO | Calcolo alba/tramonto/durata luce/altezza sole. |
| `frontend/src/domain/almanac/almanacData.js` | `useAlmanacData.js` auditato | ESTRATTO | Selezione santo, tradizione, proverbio e consigli senza importare la vecchia view. |
| `frontend/src/domain/almanac/proverbArchiveReadiness.js` | nuovo guardrail dati | CREATO | Misura se l'archivio proverbi e' pronto per 366 giorni e segnala record da revisione encoding. |
| `frontend/src/domain/almanac/proverbCandidateReview.js` | nuovo guardrail editoriale | CREATO | Riassume la review dei candidati e isola la shortlist promuovibile dopo revisione FUR. |
| `frontend/src/domain/ostermann/ostermannArchive.js` | nuovo guardrail editoriale | CREATO | Misura catalogo/estratti Ostermann e segnala duplicati, pagine sconosciute o UI readiness impropria. |
| `frontend/src/features/almanac/almanacViewModel.js` | nuovo adattatore UI 3 | CREATO | Mappa il dominio Almanacco sul contratto visuale della pagina. |
| `frontend/src/app/AppRoutes.jsx` | routing UI 3 | AGGIORNATO | Almanacco in lazy loading per isolare gli archivi dal bundle Home. |

## Prima pagina Bollettino

Intervento mirato 2026-06-22:

- `frontend/src/features/bulletin/BulletinView.jsx` crea la vista Bollettino autonoma;
- `frontend/src/features/bulletin/bulletinFixture.js` mantiene solo fixture/UI, senza fetch o data controller reale;
- `frontend/src/features/bulletin/bulletin.css` isola lo stile feature senza usare `App.css`;
- `frontend/src/app/AppRoutes.jsx` collega la route `bulletin` alla nuova vista;
- `frontend/src/ui/index.css` importa il CSS feature nel layer `features`;
- le mappe usano base SVG Meteo Friul interna e overlay dati proprietario;
- tile OpenStreetMap, Google Maps e layer immagine OSMER `_t` non vengono usati nella vista;
- se l'overlay dati manca, la base mappa resta visibile e mostra un avviso controllato;
- l'attribution resta riferita ai dati `ARPA FVG - OSMER e GRN`;
- nessuna logica dati modificata.

## Note progettuali Almanacco

Import controllato 2026-06-24:

- la pagina Almanacco non usa piu' fixture statiche;
- `almanacFixture.js` e' stato rimosso;
- il dominio vive in `frontend/src/domain/almanac`;
- gli archivi vivono in `frontend/src/data/almanac` e `frontend/src/data/ostermannCulturalDiscover.json`;
- `AlmanacView.jsx` resta solo presentazione e legge `buildAlmanacViewModel`;
- il vecchio `useAlmanacData.js` non e' stato copiato integralmente: sono stati estratti dati e funzioni pure;
- la route `almanac` e' lazy-loaded per non appesantire Home;
- restano da fare revisione FUR umana e collegamento futuro con posizione/meteo reali quando la shell dati sara' pronta;
- i proverbi quotidiani non sono ancora completi: `proverbs.json` contiene 48 record, di cui 8 `lab_ready` con revisione umana richiesta; l'obiettivo editoriale resta 366 slot datati e preferibilmente 500+ record verificati;
- `ostermannProverbSources.json` definisce le pagine Ostermann da cui estrarre nuovi candidati, separando backlog editoriale e dati pubblicabili;
- `proverbCandidates.json` e' il tavolo di lavoro: la UI non lo legge e un record passa a `proverbs.json` solo con promozione manuale tracciata;
- `proverbCandidateReview.json` tiene separate le decisioni editoriali dai testi sorgente: utile per varianti, duplicati, hold e promozioni future;
- prima promozione controllata: 8 candidati P1 sono stati inseriti in `proverbs.json` come `lab_ready`, con fonte pagina e `humanReviewRequired`, piu' slot `03-19` per San Giuseppe.
- seconda tranche candidati: pagine Ostermann 49 e 54 aggiunte allo staging, per un totale di 44 candidati su 6 pagine sorgente estratte; nessun nuovo candidato e' pubblicato in UI.
- Ostermann va pensato soprattutto per `Scopri`: creato `ostermannDiscoverBacklog.json` con 28 record/pagine, tutti `backlog_extracted` e non pronti UI.
- Per preparare Scopri senza bruciare tappe, aggiunto livello granulare in `frontend/src/data/ostermann`: 63 pagine catalogate e 64 estratti, con nessuna readiness UI.
- Prima source-check sul livello granulare: 6 estratti incerti controllati; 5 sbloccati da pagine clean, 1 sbloccato tramite immagine/OCR locale gia disponibile; nessun uso di Unlimited-OCR.
- Seconda tranche granulare: aggiunte 20 pagine su luna, calendario, Garbin, arcobaleno, aloni lunari, grandine/fulmini, vigna, erbe, Sant'Ermacora e giochi di neve; i contenuti sensibili restano `archive_context`.
- Recupero lavoro precedente: `ostermannCulturalDiscover.json` contiene gia' 59 record curati, 54 pagine sorgente, 58 FUR approvati e 1 record `short_ready`; il catalogo Ostermann ora copre tutte queste pagine.
- Il catalogo operativo passa a 63 pagine: 47 dalla nuova estrazione/proverbi e 16 recuperate dal precedente archivio curato, piu' 2 pagine gia presenti collegate ai record curati.
- Le 18 pagine curate prima mancanti dal livello granulare sono state trasformate in estratti `curated_recovered` collegati con `curatedRecordId`; il FUR approvato resta in `ostermannCulturalDiscover.json`, non duplicato.
- Il livello granulare ora copre tutte le 54 pagine del corpus curato precedente; resta da revisionare solo il singolo recupero `short_ready`.
- `curatedLinks.json` collega 38 estratti granulari a 43 record gia curati: e' una mappa anti-doppioni per la futura UX di Scopri, non una nuova fonte UI.
- Almanacco non deve diventare archivio Ostermann completo: usa solo proverbio del giorno, tradizione breve o teaser verso Scopri.

Rubrica `Astro Friul` / `Consiglio lunare`:

- possibile contenuto editoriale leggero per la futura pagina Almanacco;
- non trattarlo come oroscopo serio o predittivo;
- generare frasi brevi combinando segno zodiacale del periodo, fase lunare, meteo del giorno e tono locale;
- mantenere tono ironico/pratico: caffè, ombrello, orto, camminate, vento, caldo, piccole situazioni quotidiane;
- non inserirlo nel Bollettino, per non indebolire la percezione istituzionale/meteo della pagina;
- prima dell'implementazione auditare `useAlmanacData`, copy Almanacco e possibili dati lunari reali; in assenza di dati, trattarlo come fixture/editoriale controllata.

Rubrica `Accadde oggi` / `Pillole di Friuli`:

- contenuto consigliato per la futura tab `Scopri`, piu' coerente e prioritario della rubrica astrologica ironica;
- campo editoriale breve: storia locale, cultura friulana, lingua, tradizioni, stagioni, territorio;
- non usare scraping automatico;
- creare un archivio curato con campi `date`, `title`, `body`, `area`, `source`, `tags`;
- prevedere 50-100 pillole iniziali e rotazione giornaliera quando non esiste un evento specifico per la data;
- mostrare note di 1-2 righe, non schede enciclopediche;
- posizione consigliata: tab `Scopri`, con eventuale teaser in Almanacco se serve collegare giorno e territorio;
- richiede fonti o note editoriali controllate prima dell'uso in UI reale.

## Dorsale dati Bollettino OSMER

Import controllato 2026-06-24:

- `frontend/src/domain/alerts/officialAlerts.js` sostituisce le euristiche sparse sulle allerte con una policy unica;
- `frontend/src/features/bulletin/bulletinDataController.js` isola fetch e stati dati Bollettino;
- `frontend/src/features/bulletin/bulletinViewModel.js` prepara il contratto visuale per `BulletinView.jsx`;
- `frontend/src/features/bulletin/BulletinView.jsx` resta presentazione: riceve `model` e non decide fetch, cache o semantica;
- `frontend/src/app/AppRoutes.jsx` collega la route al controller con localita laboratorio `Udine`, da sostituire con la sorgente reale;
- `frontend/src/features/home/homeViewModel.js` usa la stessa policy allerta del Bollettino, evitando divergenze.

Confini preservati:

- `forecast.osmer_structured` resta la fonte primaria per A1-A9;
- senza `areas9` non si generano marker finti;
- il testo ufficiale OSMER resta testo ufficiale, non viene tradotto in automatico;
- il canale FUR delle previsioni viene lasciato previsto ma non lavorato in questa tranche;
- le notifiche push non vengono importate nel frontend e non vengono attivate dalla vista;
- lo stato verde/nessuna allerta non genera banner, click o azione.

Origine logica:

- dal vecchio progetto si recupera il principio gia validato: A1-A9 comandano la mappa quando presenti;
- da `official_alerts` si recupera solo la policy di presentazione breve e azionabilita;
- non viene copiato `WeatherMap.jsx` intero;
- non viene copiato `App.jsx` intero;
- non viene copiato il vecchio flusso notifiche.

Prossimo passo consentito:

1. sostituire la localita laboratorio con la sorgente localita/GPS della shell UI 3;
2. completare la parita runtime con la vecchia app prima di dichiarare la UI 3 pronta;
3. solo dopo, progettare notifiche e previsioni FUR come tranche separate e testabili.

## Runtime readiness in attesa 2026-06-28

Questa sezione e' un promemoria vincolante: la UI piu bella non deve far perdere flussi gia risolti nella vecchia app.

Gia recuperato / collegato:

- cache meteo bootstrap `weatherBootstrapCache:v2`;
- Home: cache fresca prima della rete e fallback stale;
- Bollettino: ultimo payload OSMER ufficiale valido letto subito dalla cache;
- Bollettino: refresh live dopo render iniziale, senza schermata `Caricamento bollettino`;
- Bollettino: se refresh fallisce e la cache ufficiale esiste, la vista resta leggibile;
- componenti visuali Home/Bollettino senza decisioni fetch/cache dirette.

In attesa, da non dimenticare:

- pull-to-refresh completo dalla vecchia app (`handlePullRefreshTouchStart/Move/End/Cancel`);
- orchestratore refresh manuale (`handleRefreshNow`) con meteo, Eventi, Bollettino e auto-location;
- refresh su foreground, focus e ritorno online (`visibilitychange`, `focus`, `online`);
- timer retry Eventi e stati `refreshing`/`partial` senza svuotare la lista;
- active-location/stale-location guard per evitare dati della localita precedente;
- bridge GPS/reverse geocoding e fallback manuale;
- reset cache da impostazioni;
- notifiche push solo dopo audit dedicato backend/APK/policy.

Gate prima della promozione:

- nessun loading iniziale visibile se esiste ultimo dato valido;
- nessun falso `Dati OSMER non disponibili` durante fetch;
- pull-to-refresh non deve partire dentro modali, menu, bottom sheet o scroll interni;
- refresh fallito non deve cancellare dati, eventi o bollettino gia leggibili;
- cambio localita/GPS non deve mischiare cache o payload di localita diverse.

## Inventario runtime UI 3 2026-06-28

Documento operativo aggiunto:

```text
UI3_RUNTIME_DATA_INVENTORY.md
```

Motivo:

- distinguere dati reali, cache, fallback, fixture e viste ancora laboratorio;
- evitare di continuare la UX come se tutte le sezioni fossero gia collegate;
- decidere cosa importare dalla vecchia app prima di disegnare altre pagine;
- mantenere visibile il fatto che Eventi, Vedi, Scopri, GPS, pull-to-refresh, reset cache e notifiche non sono ancora runtime completi in UI 3.0.0.

Correzione piccola applicata durante l'inventario:

- la Home non usa piu `staticData.bulletin` come fallback quando il Bollettino reale non e' disponibile;
- la sintesi bollettino in Home deve derivare da `buildBulletinViewModel()` oppure degradare con copy neutra;
- una sintesi statica non puo sembrare un dato OSMER corrente.

## Audit/import Eventi runtime 2026-06-28

Obiettivo:

- sostituire `EventsLabView` con una pagina Eventi reale;
- importare dalla vecchia app solo la logica utile, separando dati e presentazione;
- mantenere il contratto storico: nessun fetch/cache dentro `EventsView`.

Import/estrazione:

- `frontend/src/features/events/eventsDataController.js`: cache full/home, fetch full, fallback stale, gestione `refreshing`/`partial`;
- `frontend/src/features/events/eventsViewModel.js`: filtri temporali, categorie, date chip, immagini/API base e copy;
- `frontend/src/features/events/EventsView.jsx`: view presentazionale, filtri, lista, fallback immagine, cambio localita via callback;
- `frontend/src/features/events/events.css`: stile dedicato senza dipendere da `App.css`;
- route Eventi collegata in `frontend/src/app/AppRoutes.jsx`.

Guardrail confermati:

- `EventsView.jsx` non contiene `fetch(`;
- `EventsView.jsx` non contiene `localStorage`;
- `EventsView.jsx` non contiene `/local/events`;
- cache e fetch restano nel controller e nei service.
- la cache e' usata per render immediato, ma il load Eventi prova comunque il refresh dati;
- una cache vuota non puo impedire la comparsa di eventi freschi appena disponibili.

Verifica:

- test mirati Eventi/cache/Home: 7 file, 48 test passati;
- `npm run lint` passato;
- `npm run build` passato;
- browser integrato: `/?tab=events&probe=events-audit` mostra pagina non vuota, 20 eventi, tab Oggi/Weekend/Prossimi, categorie e immagini;
- browser integrato: Weekend -> 5 eventi, Prossimi -> 16 visibili con load-more, Cambia -> bottom sheet localita.
- audit comuni rapidi: Gorizia ha esposto un bug cache vuota -> 0 eventi; corretto e riverificato con 18 eventi visibili.

Restano da auditare:

- ranking geografico e `eventWeatherFit`;
- coerenza conteggio Home vs pagina su piu comuni;
- database comuni/coordinate definitivo;
- pull-to-refresh completo, foreground refresh esteso e reset cache da Opzioni.

## Audit qualita Eventi rapidi 2026-06-28

Controllo successivo al commit runtime:

- auditati Udine, Pordenone, Trieste, Gorizia, Tarvisio e Lignano Sabbiadoro;
- payload API tutti `fresh`, senza fonti pending;
- Home Gorizia e pagina Eventi allineate su `18 eventi`;
- la Home riusa `buildEventRecord()` per luogo e data compatta del teaser, evitando divergenze con la pagina Eventi.
- la Home applica un ranking dedicato al teaser: eventi puntuali di oggi/prossimi prima degli intervalli lunghi, mantenendo comunque le mostre lunghe quando sono l'unico contenuto utile.
- verifica browser su Gorizia: il teaser passa dalla mostra lunga iniziata ad aprile a `Piccolo Opera Festival -Da Ponte Cafe: Vienna` con data `28 GIU`.

Debito rimasto:

- `eventWeatherFit` e' stato riprogettato come modulo puro in UI 3: ranking nascosto del teaser Home, nessun testo meteo visibile nella card Evento e nessuna notifica.

## Audit eventWeatherFit 2026-06-28

Esito:

- vecchio file auditato, ma non copiato integralmente;
- vecchie copy IT/FUR del fit lasciate fuori per evitare rumore nella Home;
- criterio conservato: eventi riparati/culturali favoriti in meteo delicato, eventi outdoor/sagre/mercati/sport/natura piu sensibili;
- integrazione limitata a `buildHomeEventsViewModel`, come score di ranking;
- pagina Eventi, notifiche e SmartAlerts restano fuori.

File UI 3:

- `frontend/src/features/events/eventWeatherFit.js`;
- `frontend/src/features/events/eventWeatherFit.test.js`;
- `frontend/src/features/home/homeViewModel.js`;
- `frontend/src/features/home/homeViewModel.test.js`.

## Audit localita manuale UI 3 2026-06-28

Import/estrazione:

- `frontend/src/app/appLocation.js`: contratto storage legacy `defaultLocation` e `recentLocations`;
- `frontend/src/domain/geo/locationCacheKey.js`: chiave cache coerente con city/coordinate;
- `frontend/src/services/locationSearch.js`: ricerca FVG locale + endpoint `/api/location/search`, con filtro regione;
- `frontend/src/features/location/LocationSearchSheet.jsx`: bottom sheet cambio localita manuale.

Guardrail confermati:

- il cambio localita manuale passa dalla shell, non dalle view;
- `AppRoutes` rimonta la route con `getLocationCacheKey(activeLocation)`, evitando stato React della localita precedente;
- i recenti sono deduplicati, limitati a 6 e rimossi senza cambiare localita attiva;
- il bottom sheet rilegge i recenti a ogni apertura;
- copy localita normalizzata in ASCII per evitare fragilita di encoding.

Restano da importare/auditare:

- registry comuni FVG definitivo con coordinate complete;
- GPS/reverse geocoding e policy auto-location;
- pull-to-refresh completo, foreground/online refresh e reset cache.

## Registry comuni FVG UI 3 2026-06-29

Fonte:

- ISTAT `Elenco-comuni-italiani.xlsx`, foglio `CODICI al 21_02_2026`, per elenco/codici comuni;
- endpoint locale `/api/location/search` per geocoding operativo;
- alias/componenti annotati per i comuni fusi non risolti dal nome ISTAT esatto.

Import/estrazione:

- `frontend/src/data/fvgPlaces.js` passa da lista ridotta a registry completo da 215 comuni FVG;
- ogni record conserva `province`, `provinceName`, `istatCode`, `cadastralCode`, `nuts3`, `latitude`, `longitude`, `coordinateSource`;
- i 13 record non risolti direttamente dal geocoding hanno `coordinateNote`;
- `LocationSearchSheet.jsx` usa lo stesso registry per i comuni rapidi.

Guardrail:

- nessuna coordinata senza fonte;
- test anti-mojibake sulle denominazioni;
- test su conteggio 215 e coordinate finite;
- ricerca locale aggiornata per accettare liste multi-risultato.

Restano fuori:

- GPS/reverse geocoding dalla vecchia app;
- pull-to-refresh/cache runtime;
- verifica visuale browser se il runtime integrato resta instabile.

## GPS/reverse geocoding UI 3 2026-06-29

Vecchia app auditata:

- `frontend/src/App.jsx`: `autoLocationEnabled`, `locationReverseCache:v1`, `getReverseLocationCacheKey()`, `resolveDetectedLocation()`, `tryNativeAutoDetect()`, `handleAutoDetect()`;
- `frontend/src/utils/autoLocationPolicy.js`: policy su failure, foreground e confronto comune;
- `backend/main.py`: endpoint `/api/location/reverse`.

Import controllato:

- non copiato `handleAutoDetect()` dentro `App.jsx` UI 3;
- estratta solo la decisione qualita GPS in `frontend/src/domain/geo/autoLocationPolicy.js`;
- aggiunto `frontend/src/services/reverseLocation.js` come servizio separato e testabile;
- mantenuta la cache legacy `locationReverseCache:v1` con precisione coordinate a 3 decimali;
- aggiunto storage flag `autoLocationEnabled` in `frontend/src/app/appLocation.js`.

Guardrail:

- nessun permesso posizione chiesto in questa tranche;
- nessun cambio automatico localita collegato alla shell;
- risultati fuori FVG marcati con `insideFvg: false`;
- errore reverse marcato con `ok: false`, senza fingere dati FVG.

Prossimo collegamento:

- UX consenso GPS in Opzioni;
- collegare browser geolocation dietro tap utente;
- collegare native bridge solo dopo test su percorso Android;
- decidere comportamento fuori FVG prima di mostrare la posizione come localita attiva.

## UX consenso GPS e reverse live UI 3 2026-06-29

Vecchia app auditata:

- flusso `handleAutoDetect()` e `resolveDetectedLocation()` usati come riferimento;
- non copiato il blocco in `App.jsx` UI 3;
- mantenuta la separazione nuova: coordinate browser, reverse service, stato shell.

Import controllato:

- `frontend/src/services/deviceLocation.js`: richiede coordinate browser solo quando chiamato;
- `frontend/src/app/App.jsx`: aggiunge handler `handleDeviceLocationRequest()`;
- `frontend/src/features/settings/SettingsView.jsx`: riga `Posizione dispositivo` con azione esplicita `Usa posizione`;
- `frontend/src/features/settings/settings.css`: stato busy del pulsante GPS.

Guardrail:

- nessuna richiesta GPS all'avvio;
- nessuna richiesta GPS dalla Home;
- localita attiva invariata se permesso negato, GPS non disponibile, reverse fallito o posizione fuori FVG;
- `autoLocationEnabled` viene salvato `true` solo dopo reverse FVG riuscito.

Restano fuori:

- Android bridge;
- auto-check in foreground della posizione automatica;
- privacy/permessi estesi;
- passata copy/codifica FUR.

## Separazione comune visualizzato / posizione dispositivo UI 3 2026-06-29

Decisione:

- il comune visualizzato e' il contesto che l'utente sta guardando in Home, Bollettino ed Eventi;
- la posizione dispositivo e' dove si trova il telefono e puo servire ad altre funzioni future;
- se l'utente e' fisicamente a Pordenone ma sceglie Trieste, il GPS non deve riportare automaticamente la app a Pordenone;
- il cambio manuale spegne il legame `meteo segue GPS`, ma non cancella l'ultima posizione dispositivo rilevata;
- in Opzioni la riga manuale viene prima: `Comune visualizzato`, poi `Posizione dispositivo`.

Guardrail:

- la posizione dispositivo resta una risorsa esplicita, non un trigger automatico;
- Eventi vicino a me dovra decidere separatamente se usare comune visualizzato o posizione dispositivo;
- nessun foreground auto-check finche questa distinzione non e' testata su Android.

## Permessi GPS/notifiche Android UI 3 2026-06-29

Fonte auditata:

- vecchia app `App.jsx` per startup gate;
- `MainActivity.java` per bridge Android `MeteoAndroid`;
- `pushNotifications.js` per `PushNotifications.checkPermissions/requestPermissions/register`;
- `AndroidManifest.xml` per permessi e portrait lock;
- `backend/main.py` per registrazione device.

Decisione:

- questa decisione vale per APK/Android e supera, per il gate iniziale Android, il precedente flusso laboratorio `Usa posizione` da Opzioni;
- il gate Android finale non usa pulsanti/card custom per chiedere consenso;
- all'apertura APK si chiede prima posizione nativa;
- dopo accettazione/rifiuto posizione e localita risolta/scelta si chiede notifica nativa;
- `startupNotificationsAsked:v1` impedisce richieste ripetute;
- `weatherAlertsEnabled` resta la preferenza utente;
- nessun invio push reale in UI 3 finche il modulo non e' importato e testato su APK.

Da importare dopo:

- bridge Android fast/balanced location;
- policy fallimenti temporanei;
- modulo push nativo;
- contratto register/unregister device;
- test Android/emulatore.

## Contratto startup Android GPS/notifiche UI 3 2026-06-29

Creato:

- `frontend/src/domain/startup/androidPermissionGate.js`;
- `frontend/src/domain/startup/androidPermissionGate.test.js`.

Ruolo:

- definisce stati e azioni del gate Android senza chiedere permessi reali;
- mantiene l'ordine corretto: posizione nativa -> localita risolta/scelta -> notifiche native;
- impedisce che una localita manuale gia presente faccia saltare il prompt GPS iniziale;
- separa fallimenti temporanei GPS da negazione/unsupported;
- tiene fuori push live, token FCM, backend e APK.

Prossimo collegamento, non ancora fatto:

- orchestratore startup UI3 che usa il modulo;
- bridge Android `MeteoAndroid`;
- modulo native push;
- test APK/emulatore.

## Runtime cache/refresh UI 3 2026-06-29

Audit creato:

- `RUNTIME_REFRESH_CACHE_AUDIT.md`.

Recuperare dalla vecchia app:

- cache meteo `weatherBootstrapCache:v2`;
- cache Eventi `eventsCache:v10` con schema `single-source-v1`;
- idratazione immediata da cache prima della rete;
- refresh manuale `handleRefreshNow()`;
- pull-to-refresh con soglie e blocchi su mappe/modali/scroll interni;
- refresh foreground/focus/online con intervallo minimo;
- guardia anti-risposte per localita non corrente.

Gia presente in UI3:

- cache services puri;
- controller Home, Bollettino, Eventi;
- fallback stale senza svuotare dati;
- Bollettino idratabile solo da cache OSMER ufficiale.

Da fare dopo:

- modulo puro `runtimeRefreshPolicy`;
- orchestratore shell UI3;
- reset cache in Opzioni;
- pull-to-refresh visivo.

## Contratto runtime refresh/cache UI 3 2026-06-29

Creato:

- `frontend/src/domain/runtime/runtimeRefreshPolicy.js`;
- `frontend/src/domain/runtime/runtimeRefreshPolicy.test.js`.

Ruolo:

- definisce come la shell deve trattare cache, refresh, fallimenti e risposte di localita vecchia;
- non fa fetch, non legge storage, non modifica UI;
- conferma che `Dati non raggiungibili` si mostra solo quando non c'e' dato utile;
- conferma che Eventi pending non va scritto in cache.

Prossimo collegamento, non ancora fatto:

- orchestratore shell UI3;
- gesture pull-to-refresh;
- reset cache in Opzioni;
- feedback refresh nel linguaggio UI definitivo.

## Collegamento shell runtime refresh/cache UI 3 2026-06-29

Collegato:

- `frontend/src/app/App.jsx`;
- `frontend/src/domain/runtime/runtimeRefreshPolicy.js`;
- `frontend/src/domain/runtime/runtimeRefreshPolicy.test.js`.

Ruolo:

- la shell usa `shouldRunRuntimeRefresh()` per decidere i refresh da timer, focus, online e visibility;
- l'intervallo verifica meteo e il throttle foreground sono definiti nel dominio runtime;
- `force=true` resta il canale per cambio localita, GPS e timer controllato;
- le route continuano a idratarsi da cache attraverso i controller esistenti.

Restano da fare:

- verifica pull-to-refresh su APK/emulatore;
- reset cache in Opzioni;
- feedback utente per refresh completato/non cambiato;
- orchestratore unico con esito `{ ok, changed, source }`;
- foreground GPS Android-safe.

## Pull-to-refresh controllato UI 3 2026-06-29

Collegato:

- `frontend/src/domain/runtime/pullRefreshPolicy.js`;
- `frontend/src/domain/runtime/pullRefreshPolicy.test.js`;
- `frontend/src/ui/layout/AppShell.jsx`;
- `frontend/src/ui/layout/layout.css`;
- `frontend/src/app/App.jsx`;
- `frontend/src/app/uiShellCopy.js`.

Ruolo:

- recupera le soglie della vecchia app in un modulo puro;
- collega la gesture solo allo scroll principale;
- protegge header, nav, bottoni, input, tab, mappa bollettino e location sheet;
- chiama il refresh shell gia esistente senza svuotare route o dati;
- mostra un indicatore leggero con icona refresh classica;
- dopo il rilascio resta in `Sto aggiornando` finche la route attiva completa il refresh, con tempo minimo leggibile.
- chiude il feedback con esito esplicito `Caricamento` / `Aggiornato` / `Fallito`;
- le route Home, Bollettino ed Eventi propagano alla shell un esito `{ ok }` invece di chiudere sempre come successo.
- un errore rete non demolisce cache utile/non stale gia visibile;
- un bollettino passato/scaduto marcato `isStale` non viene trattato come successo.

Restano da fare:

- verificare su APK/emulatore;
- distinguere in futuro `Aggiornato` da `Gia aggiornato` quando avremo `changed`;
- progettare reset cache in Opzioni;
- rifinire microcopy FUR con revisione dedicata.

## Localita globale e ingresso Cambia contestuale UI 3 2026-06-30

Collegato:

- `frontend/src/ui/components/LocationContext.jsx`;
- `frontend/src/ui/layout/AppHeader.jsx`;
- `frontend/src/app/AppRoutes.jsx`;
- `frontend/src/features/home/HomeView.jsx`;
- `frontend/src/features/home/HomeWeatherHero.jsx`;
- `frontend/src/features/lab/DiscoverLabView.jsx`.

Ruolo:

- mantiene una sola localita attiva globale per tutta l'app;
- sostituisce la lente generica in header con azioni testuali contestuali;
- porta `Cambia` vicino alla localita nelle sezioni che dipendono chiaramente dal comune;
- evita di introdurre localita visibile nel Bollettino finche' non esiste una sezione localizzata progettata.

Decisione progettuale:

- Home: localita protagonista nella hero, con `Cambia`;
- Eventi: `Vicino a {comune}` resta la forma corretta;
- Scopri: `A {comune}` e' predisposto per contenuti territoriali;
- Bollettino: resta OSMER FVG ufficiale senza localita in testata; l'eventuale `Evoluzione locale` andra' dopo il contenuto OSMER e con fonte separata.

Restano da fare:

- decidere la UX di eventuale sezione localizzata in Bollettino;
- auditare eventuale fonte evoluzione locale senza mescolarla alle allerte ufficiali;
- verificare su mobile reale/APK la leggibilita' di `Cambia` nella hero.

## Terminologia posizione dispositivo UI 3 2026-07-01

Decisione:

- nella UI si usa `Usa posizione`, non `Usa GPS`;
- `Posizione dispositivo` indica una posizione stimata dal sistema, non solo il GPS satellitare;
- Android puo usare GPS, rete mobile, Wi-Fi, celle o ultima posizione nota tramite Fused Location Provider;
- se i servizi posizione sono spenti o il permesso viene negato, l'app resta sulla localita manuale.

Aggiornato:

- `frontend/src/features/settings/SettingsView.jsx`: azione `Usa posizione`, stato `Ricerca posizione`, fallback FUR specifici;
- `PERMISSIONS_GPS_PUSH_AUDIT.md`: nota tecnica sui provider Android e sul lessico utente;
- `AUDIT_CHECKLIST.md`: tracciata la decisione come tranche dedicata.

Guardrail:

- nessun collegamento a prompt reale;
- nessun Android project;
- nessuna modifica a push, token, backend, meteo, OSMER o Eventi.

## Orchestratore startup Android GPS/notifiche UI 3 2026-07-02

Collegato:

- `frontend/src/domain/startup/androidStartupPromptFlow.js`;
- `frontend/src/domain/startup/androidStartupPromptFlow.test.js`.

Ruolo:

- usa `androidPermissionGate` come policy di stato;
- formalizza una sequenza eseguibile e testata: GPS/posizione dispositivo prima, notifiche dopo;
- usa funzioni iniettate per posizione e notifiche, quindi non apre prompt reali in test;
- produce passi espliciti (`gps_requested`, `gps_resolved`, `gps_failed`, `notifications_requested`, `ready`);
- restituisce `storagePatch` per notifiche, ma non scrive localStorage direttamente;
- lascia fuori registrazione device/backend e token FCM.

Decisione:

- se Android risolve la posizione, si puo passare alle notifiche;
- se Android nega la posizione e non c'e localita manuale, si ferma alla scelta localita;
- se Android nega la posizione ma esiste una localita manuale, si puo chiedere notifiche;
- se il GPS fallisce temporaneamente, il flow resta retryable e non apre notifiche;
- se le notifiche sono gia state chieste o abilitate, il prompt non si ripete.

Restano da fare:

- collegamento ad `App.jsx` completato nella sezione `Collegamento runtime startup Android in App`;
- collegare plugin Capacitor reale;
- decidere persistenza storage definitiva;
- test APK/emulatore dell'ordine prompt.

## Collegamento runtime startup Android in App UI 3 2026-07-02

Collegato:

- `frontend/src/app/androidStartupRuntime.js`;
- `frontend/src/app/androidStartupRuntime.test.js`;
- `frontend/src/app/App.jsx`.

Ruolo:

- esegue `androidStartupPromptFlow` solo se il runtime e' Android nativo;
- lascia il browser fuori dal flusso, quindi nessun prompt web viene aperto all'avvio;
- riusa la stessa risoluzione posizione gia usata dal pulsante `Usa posizione`;
- interpreta lo storage startup con default `autoLocationEnabled=true`, cosi il primo avvio Android puo chiedere la posizione;
- non persiste patch notifiche quando il gestore notifiche e' ancora un dry-run `unsupported`.

Guardrail:

- nessun plugin push reale collegato;
- nessun token FCM salvato;
- nessuna chiamata backend device;
- nessun Android project aggiunto;
- nessuna modifica a OSMER, Eventi, Home o cache meteo.

Restano da fare:

- collegare plugin push reale solo quando ci sara' Android project UI3;
- test APK/emulatore dell'ordine prompt nativo;
- decidere registrazione device/backend in tranche separata.

## Audit localita e ricerca comuni UI 3 2026-07-03

Collegato/verificato:

- `frontend/src/data/fvgPlaces.js`;
- `frontend/src/data/fvgPlaces.test.js`;
- `frontend/src/services/locationSearch.js`;
- `frontend/src/services/locationSearch.test.js`;
- `frontend/src/features/location/LocationSearchSheet.jsx`;
- `frontend/src/features/location/locationSheetLists.js`.

Ruolo:

- il registro locale contiene 215 comuni FVG, senza duplicati e senza coordinate mancanti;
- la ricerca usa subito il registro locale mentre il backend viene interrogato solo dopo debounce;
- la ricerca per sigla provincia (`UD`, `PN`, `GO`, `TS`) mantiene prima il capoluogo;
- la localita attiva viene esclusa dalle liste per evitare ripetizioni;
- recenti e comuni rapidi vengono deduplicati;
- una localita recente puo essere rimossa e torna disponibile nei comuni rapidi se prevista.

Verifica browser:

- Home -> `Cambia` apre il bottom sheet;
- digitando `gori` compare subito `Gorizia`;
- digitando `pord` con Pordenone attiva non viene ripetuta Pordenone e restano i comuni secondari;
- rimozione recente verificata nel bottom sheet.

Restano fuori:

- reverse geocoding live completo;
- audit local weather per tutte le localita;
- test Android/APK della stessa UX localita.

## Catalogo profili comunali Scopri UI 3 2026-07-19

Collegato:

- `frontend/src/data/fvgPlaces.js` come unica anagrafica canonica dei 215 comuni FVG;
- `frontend/src/data/discover/municipalityProfiles.json` come archivio dei profili storici editoriali;
- `frontend/src/domain/discover/municipalityProfiles.js` come compositore del catalogo completo;
- `frontend/src/domain/discover/municipalityProfiles.test.js` e `frontend/src/features/discover/DiscoverView.test.jsx` come guardrail.

Contratto:

- ogni comune del registro ISTAT riceve una card comunale IT/FUR in Scopri;
- il match usa prima il codice ISTAT e poi il nome normalizzato;
- i 4 profili di Pordenone, Udine, Gorizia e Trieste restano approfondimenti pilota `editorial`;
- gli altri 211 sono profili `editorial` revisionati in IT e FUR, con fatti, fonte HTTPS e tappe storiche quando disponibili;
- il fallback `registry` resta nel compositore solo come protezione per eventuali future variazioni del registro, ma non e usato dai 215 comuni attuali;
- in assenza di fotografia revisionata, la card resta testuale; gli stemmi comunali sono ora disponibili per tutti i 215 profili.

Stato:

- copertura comunale runtime: 215/215;
- lingue disponibili: IT 215/215, FUR 215/215;
- profili storici editoriali: 215/215;
- profili pilota: 4/215;
- profili bilingui promossi dopo review: 211/215;
- fallback anagrafici attivi: 0/215.
- stemmi locali collegati per codice ISTAT: 215/215;
- fallback marker geografico usati dai profili attuali: 0/215.

Restano da fare, come arricchimento visivo e non come requisito di copertura:

- fotografie comunali opzionali;
- eventuale sostituzione dei riferimenti enciclopedici residui con fonti istituzionali migliori, senza cambiare i contenuti gia approvati alla cieca.

## Stemmi comunali Scopri 2026-07-19

Collegato:

- `scripts/sync-municipality-coats.mjs` come processo ripetibile di audit e download;
- `scripts/data/municipality-coat-sources.json` come catalogo sorgente completo con pagina file e repository;
- `frontend/src/data/discover/municipalityVisuals.json` come manifest runtime leggero;
- `frontend/public/municipalities/coats/` come archivio locale, senza dipendenze di rete a runtime;
- `frontend/src/features/discover/municipalityVisuals.js` come lookup unico per codice ISTAT.

Contratto:

- uno stemma locale per ciascuno dei 215 profili comunali;
- 150 associazioni derivate dal campo `Stemma` dell'infobox comunale e 65 da Wikidata P94;
- nessuna associazione basata soltanto su somiglianza del nome;
- ogni file viene verificato come immagine prima del salvataggio;
- le tappe storiche restano dati editoriali separati dagli asset visuali e vengono mostrate nel profilo comunale solo quando il record contiene fatti bilingui gia revisionati.

## Raccolta fonti per i 211 profili comunali 2026-07-19

Preparato come archivio di revisione separato dal catalogo runtime:

- cinque archivi candidati separati per territorio in `frontend/src/data/discover/municipalityProfileCandidates.*.json`;
- copertura esatta dei 211 comuni ancora `registry`: GO 24, TS 5, PN 49, UD 133;
- per ogni comune: identita ISTAT, titolo e sintesi IT, eventuali tappe storiche e una fonte HTTPS classificata;
- fonti raccolte: 72 comunali, 45 regionali, 39 culturali e 55 riferimenti Wikipedia da sottoporre alla stessa revisione editoriale;
- `scripts/audit-municipality-profile-candidates.mjs` come controllo di copertura, unicita, schema, stato editoriale, fonte e integrita Unicode;
- `scripts/promote-municipality-profile-review.mjs` come unico passaggio ammesso verso l'archivio runtime bilingue.

Stati ammessi:

1. `source_collected`: fonte e testo IT candidati, nessuna pubblicazione;
2. `it_reviewed`: testo IT approvato, FUR ancora da lavorare, nessuna pubblicazione;
3. `reviewed`: IT e FUR approvati, `readyForUi: true`, profilo promuovibile.

Regole:

- la raccolta completa non equivale a pubblicazione;
- non si traduce in FUR un profilo scartato o non approvato in italiano;
- nessun candidato sostituisce il fallback `registry` finche entrambe le lingue non sono approvate;
- la promozione avviene per codice ISTAT e non puo sovrascrivere alla cieca il catalogo.

Revisione italiana conclusa:

- 211/211 profili in stato `it_reviewed`;
- gate ripetibile: `node scripts/audit-municipality-profile-candidates.mjs --strict --require-it-reviewed`;
- fonti dopo la revisione: 79 comunali, 53 regionali, 40 culturali, 4 nazionali e 35 riferimenti Wikipedia;
- corretti errori di cronologia, fonti non raggiungibili, formulazioni promozionali e affermazioni troppo assolute;
- nessun profilo candidato e ancora collegato alla UI: il fallback `registry` resta attivo fino all'approvazione FUR.

Revisione bilingue conclusa:

- 211/211 profili in stato `reviewed`, con IT e FUR approvati e `readyForUi: true`;
- gate pre-promozione: `node scripts/audit-municipality-profile-candidates.mjs --strict --require-bilingual-reviewed`;
- gate post-promozione: `node scripts/audit-municipality-profile-candidates.mjs --strict --require-bilingual-reviewed --allow-promoted`;
- controllo differenziale ripetibile: `node scripts/audit-municipality-profile-fur-diff.mjs --baseline-ref=a284d81`;
- il controllo differenziale certifica che la passata FUR non ha modificato identita, fatti, date, fonti o testi italiani;
- il controllo post-promozione richiede che i 211 candidati coincidano esattamente con i rispettivi record runtime.

Promozione runtime conclusa:

- i cinque archivi sono stati importati in sequenza per codice ISTAT tramite `scripts/promote-municipality-profile-review.mjs`;
- `municipalityProfiles.json` contiene ora 215/215 profili editoriali bilingui, senza duplicati;
- il contratto runtime accetta solo gli stati e i tipi di fonte gia ammessi dall'audit editoriale;
- audit post-promozione: 211/211 corrispondenze esatte, zero divergenze;
- test mirati Scopri: 16/16 passati dopo l'ultimo riallineamento FUR;
- suite frontend completa: 208 file e 1139 test passati;
- lint e build passati; resta il preesistente avviso Vite sulla dimensione del chunk principale;
- browser verificato su Pordenone, Cordenons e Sappada, in IT/FUR, light/dark e viewport mobile 390x844;
- nessun overflow mobile e nessun errore o warning console rilevato durante il controllo.

## Tappe storiche dei profili comunali 2026-07-19

Collegato:

- `milestones` del profilo comunale alla card iniziale di Scopri;
- titolo bilingue `Tappe storiche` / `Tapis storichis`;
- lista semantica ordinata, con periodo separato dal fatto e senza pill;
- rendering condizionale: nessun titolo o spazio vuoto se il Comune non ha tappe verificate.

Copertura corrente:

- 147 profili comunali con almeno una tappa;
- 206 tappe bilingui complessive;
- massimo tre tappe per profilo;
- 68 profili senza tappe, lasciati invariati invece di aggiungere fatti non verificati.

Verifica:

- Pordenone con tre tappe;
- Aquileia con periodo antico `181 a.C.`;
- Amaro senza blocco vuoto;
- IT/FUR, light/dark e mobile 390x844 senza overflow o errori console.

## Pilot fotografie comunali Scopri 2026-07-19

Collegato come tranche visuale separata dagli stemmi:

- `frontend/src/data/discover/municipalityPhotos.json` come manifest runtime delle sole fotografie revisionate;
- `frontend/src/data/discover/municipalityPhotoCredits.json` come catalogo unico per autore, licenza, pagina sorgente, asset originale e modifiche, condiviso con la UI;
- `frontend/public/municipalities/photos/` come archivio WebP locale, senza dipendenze Wikimedia a runtime;
- `scripts/validate-municipality-photos.mjs` come controllo di codici ISTAT, duplicati, metadati, file locali e copertura.

Perimetro pilot:

- Pordenone, Udine, Gorizia e Trieste;
- quattro immagini revisionate, 431328 byte complessivi;
- foto decorativa limitata alla testata della card, con posizione focale dichiarata per Comune;
- stemma e nome restano l'identita accessibile; i 211 profili senza fotografia mantengono invariata la card blu con stemma;
- la sincronizzazione degli stemmi non puo sovrascrivere il manifest fotografico separato.

Verifica:

- caricamento locale riuscito per i quattro capoluoghi;
- nessuna sovrapposizione con le tappe storiche e nessun overflow orizzontale;
- light/dark, layout largo e mobile 390x844 verificati nel browser senza errori o warning console;
- la superficie compatta `Impostazioni > Informazioni e crediti` espone autore, origine e licenza senza immagini duplicate, collegamenti esterni o sovrapposizioni sulle card comunali.

## Periodi storici leggibili nelle card comunali 2026-07-19

- l'archivio storico conserva secoli e ordinali nella forma editoriale originale;
- il modello UI converte i numeri romani soltanto in fase di presentazione;
- le tappe sintetiche usano numeri arabi (`18°-19° sec.` in IT, `Secui 18-19` in FUR);
- titoli, sintesi e descrizioni delle tappe convertono anche gli ordinali storici, senza alterare nomi, date o fonti nell'archivio;
- un test attraversa tutti i 215 profili in entrambe le lingue e impedisce la ricomparsa di numeri romani nelle card renderizzate.

## Autonomia runtime UI3 dal backend storico 2026-08-10

Stato:

- tutte le route usate dal frontend sono disponibili nella nuova API modulare `backend/` sulla porta locale `8002`;
- Vite instrada l'intero spazio `/api/*` esclusivamente verso UI3, senza fallback implicito alla porta `8001`;
- `scripts/start-dev.ps1` avvia per default soltanto API UI3 e frontend;
- il backend storico resta avviabile esclusivamente con `-WithLegacyBackend` per confronto o rollback manuale.

Collaudo browser con `8001` spento:

- Home, Bollettino, Territorio, Eventi, Scopri, Almanacco e Impostazioni funzionanti;
- nessun errore o warning console e nessuno stato di caricamento bloccato;
- con `8002` spento e cache presente, i dati salvati restano visibili in Home, Bollettino, Territorio ed Eventi;
- Android e push reale restano fuori da questa tranche.
