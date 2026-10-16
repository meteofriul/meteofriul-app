# Meteo Friul UI 3.0.0 - Import Log

Data: 2026-06-21
Stato: log operativo

## Regola

Ogni import dalla app attuale deve indicare:

- fonte;
- destinazione;
- motivo;
- dipendenze introdotte;
- test di protezione;
- cosa non e' stato importato.

Fonte validata:

```text
F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma
```

## Tranche 2 - Copy, API config, policy GPS

### API config

| Fonte | Destinazione | Motivo | Dipendenze | Test |
| --- | --- | --- | --- | --- |
| `frontend/src/utils/apiConfig.js` | `frontend/src/services/apiConfig.js` | Conservare contratto API `/api` dietro proxy Vite. | `import.meta.env` | `frontend/src/services/apiConfig.test.js` |

Note:

- nessuna fetch introdotta;
- nessun endpoint operativo chiamato dalla shell laboratorio.

### Copy IT/FUR

| Fonte | Destinazione | Motivo | Test |
| --- | --- | --- | --- |
| `frontend/src/utils/appShellCopy.js` | `frontend/src/copy/appShellCopy.js` | Microcopy shell validata. | `appShellCopy.test.js` |
| `frontend/src/utils/bulletinViewCopy.js` | `frontend/src/copy/bulletinViewCopy.js` | Microcopy Bollettino validata. | `bulletinViewCopy.test.js` |
| `frontend/src/utils/eventsViewCopy.js` | `frontend/src/copy/eventsViewCopy.js` | Microcopy Eventi e filtri validati. | `eventsViewCopy.test.js` |
| `frontend/src/utils/liveViewCopy.js` | `frontend/src/copy/liveViewCopy.js` | Microcopy Vedi validata. | `liveViewCopy.test.js` |
| `frontend/src/utils/discoverCopy.js` | `frontend/src/copy/discoverCopy.js` | Microcopy Scopri validata. | `discoverCopy.test.js` |
| `frontend/src/utils/almanacCopy.js` | `frontend/src/copy/almanacCopy.js` | Microcopy Almanacco validata. | `almanacCopy.test.js` |
| `frontend/src/utils/locationSelectorCopy.js` | `frontend/src/copy/locationSelectorCopy.js` | Microcopy localita/impostazioni validata. | `locationSelectorCopy.test.js` |
| `frontend/src/utils/dailySummaryCopy.js` | `frontend/src/copy/dailySummaryCopy.js` | Microcopy sintesi giornaliera validata. | `dailySummaryCopy.test.js` |

Adapter aggiunto:

| File | Motivo |
| --- | --- |
| `frontend/src/app/uiShellCopy.js` | Mappa il copy storico `navLabels.map` sulla tab UI 3 `bulletin`, senza modificare il copy importato. |

### Policy GPS/localita

| Fonte | Destinazione | Motivo | Dipendenze | Test |
| --- | --- | --- | --- | --- |
| `frontend/src/utils/autoLocationPolicy.js` | `frontend/src/domain/geo/autoLocationPolicy.js` | Riusa regole pure su posizione automatica/manuale. | nessuna | `autoLocationPolicy.test.js` |

Note:

- non e' stato importato il bridge GPS;
- non e' stato importato reverse geocoding;
- non e' stato importato codice Capacitor;
- non e' stato cambiato comportamento localita.

## Cosa non e' stato importato

- `App.jsx` legacy;
- `App.css` legacy;
- `WeatherMap.jsx`;
- `LiveView.jsx`;
- cache eventi;
- fetch meteo;
- fetch eventi;
- notifiche push;
- adapter OSMER.

## Tranche 3 - Dominio OSMER A1-A9

### Adapter e sintesi temporale

| Fonte | Destinazione | Motivo | Dipendenze | Test |
| --- | --- | --- | --- | --- |
| `frontend/src/weather/osmerAdapter.js` | `frontend/src/domain/weather/osmerAdapter.js` | Riusa mapping A1-A9, marker ufficiali e merge per `valid_date`. | nessuna | `osmerAdapter.test.js` |
| `frontend/src/weather/osmerTemporalSummary.js` | `frontend/src/domain/weather/osmerTemporalSummary.js` | Riusa sintesi tab giornaliera OSMER gia validata. | `osmerAdapter.js` | `osmerTemporalSummary.test.js` |
| `frontend/src/fixtures/PW20260606.normalized.json` | `frontend/src/tests/fixtures/PW20260606.normalized.json` | Fixture reale per regressioni A1-A9. | nessuna | usata dai test OSMER |

Adattamenti effettuati:

- aggiornati solo i percorsi fixture nei test, da `../fixtures/...` a `../../tests/fixtures/...`;
- nessuna aspettativa test modificata;
- nessuna funzione OSMER modificata.

Contratti protetti dai test:

- mapping ufficiale A1-A9 verso zone app;
- pioggia montana localizzata non si propaga a pianura/costa;
- costruzione di 9 zone strutturate dalla fixture;
- condizioni `official_projected` distinte da XML nativo;
- intensita pioggia OSMER conservata;
- temporale senza pioggia mantiene marker cielo con fulmine;
- vento non diventa marker meteo primario;
- merge forecast/OSMER per `valid_date`, non per indice;
- sintesi tab con temporali diffusi, temporali isolati, vento e residui notturni.

Non importato:

- `WeatherMap.jsx`;
- `WeatherMap.css`;
- logica di rendering marker;
- overlay vento/fulmini UI;
- fetch bollettino;
- backend OSMER.

Verifica tranche 3:

```text
npm run test
14 test file passati
62 test passati
npm run lint passato
npm run build passato
```

Guardrail aggiuntivi:

- nessun `fetch(` in `frontend/src`;
- nessun `App.css` in `frontend/src`;
- nessun `!important` in `frontend/src`;
- nessun import di `WeatherMap`, `LiveView` o `EventsView` legacy;
- nessun `/local/events`;
- nessun `navigator.geolocation`;
- nessun `Capacitor`.

Nota:

- un tentativo di test isolato con `npx vitest run ...` ha incontrato un errore Windows/Vite su `node_modules/.vite-temp`; la suite ordinaria `npm run test` e' passata subito dopo.

## Tranche 4 - Normalizzazione e semantica meteo

### Moduli importati

| Fonte | Destinazione | Motivo | Dipendenze | Test |
| --- | --- | --- | --- | --- |
| `frontend/src/utils/normalizedWeather.js` | `frontend/src/domain/weather/normalizedWeather.js` | Normalizza payload meteo in un contratto unico per Home/UI future. | `weatherClassification.js`, `weatherSemantics.js` | `normalizedWeather.test.js` |
| `frontend/src/utils/weatherSemantics.js` | `frontend/src/domain/weather/weatherSemantics.js` | Mantiene semantica meteo validata, incluse condizioni principali e overlay. | nessuna | `weatherSemantics.test.js` |
| `frontend/src/utils/weatherClassification.js` | `frontend/src/domain/weather/weatherClassification.js` | Mantiene classificazione meteo e fallback coerenti con la app attuale. | `weatherSemantics.js` | `weatherClassification.test.js` |
| `frontend/src/utils/weatherAdviceContext.js` | `frontend/src/domain/weather/weatherAdviceContext.js` | Costruisce il contesto meteo usato da consigli e copy contestuale. | `normalizedWeather.js` | `weatherAdviceContext.test.js` |
| `frontend/src/utils/weatherSemanticTags.js` | `frontend/src/domain/weather/weatherSemanticTags.js` | Espone contesto semantico/tag da dati normalizzati per contenuti futuri. | `normalizedWeather.js` | `weatherSemanticTags.test.js` |
| `frontend/src/utils/unitFormats.js` | `frontend/src/domain/weather/unitFormats.js` | Centralizza conversione e formattazione numerica metric/imperial. | nessuna | `unitFormats.test.js` |
| `frontend/src/utils/temperatureSeverity.js` | `frontend/src/domain/weather/temperatureSeverity.js` | Mantiene soglie caldo/freddo usate dalla presentazione meteo. | nessuna | `temperatureSeverity.test.js` |

Adattamenti effettuati:

- nessuna funzione importata e' stata modificata;
- i test originali sono stati copiati quando presenti;
- aggiunti test minimi per `weatherSemanticTags.js`, `unitFormats.js` e `temperatureSeverity.js`, per bloccare il comportamento reale della fonte senza inventare API nuove.

Non importato:

- `weatherSemanticsImpact.test.js`, perche' attraversa componenti/hook non ancora migrati;
- `weatherSceneType.js`;
- `weatherSceneTokens.js`;
- `weatherFlightScene*`;
- `eventWeatherFit.js`;
- `culturalDiscoverRanking.js`;
- `useAlmanacData.js`;
- componenti visuali Home, scenetta, mappa o Almanacco.

Contratti protetti dai test:

- la Home futura potra' leggere dati normalizzati senza reinterpretare testo nel JSX;
- vento e overlay restano semantica/effetto, non marker meteo principale;
- classificazione, advice context e formati numerici restano allineati alla app attuale;
- le soglie temperatura sono documentate da test e non da CSS o markup.

Verifica tranche 4:

```text
npm run test
21 test file passati
171 test passati
npm run lint passato
npm run build passato
smoke locale http://127.0.0.1:5174/ passato con HTTP 200
```

Guardrail aggiuntivi:

- nessun `fetch(` in `frontend/src`;
- nessun `App.css` in `frontend/src`;
- nessun `!important` in `frontend/src`;
- nessun import di `WeatherMap`, `LiveView` o `EventsView` legacy;
- nessun `/local/events`;
- nessun `navigator.geolocation`;
- nessun `Capacitor`.

## Tranche 5 - Contratti servizi meteo/eventi

### Servizi estratti

| Fonte audit | Destinazione | Motivo | Dipendenze | Test |
| --- | --- | --- | --- | --- |
| `frontend/src/App.jsx` fetch bootstrap meteo | `frontend/src/services/weatherApi.js` | Isola costruzione URL `/weather/bootstrap`, validazione payload e fetch iniettato. | `apiConfig.js` | `weatherApi.test.js` |
| `frontend/src/App.jsx` fetch eventi | `frontend/src/services/eventsApi.js` | Isola URL `/local/events`, promozione limite Home `8 -> 100` e stati cache backend. | `apiConfig.js` | `eventsApi.test.js` |

Adattamenti effettuati:

- nessun componente e nessuna view usa ancora questi servizi;
- nessuna chiamata rete reale nei test;
- `fetch` e' iniettato come `fetchImpl`, cosi i contratti sono testabili senza browser/API;
- la richiesta meteo conserva il formato legacy con `encodeURIComponent` per `city`;
- la richiesta eventi conserva `URLSearchParams` e la promozione `HOME_EVENTS_LIMIT` verso `FULL_EVENTS_LIMIT`.

Contratti protetti dai test:

- URL bootstrap meteo con city/lat/lon;
- cache buster `_=` e `cache: "no-store"` quando `force` e' attivo;
- mapping payload `official_alerts -> officialAlerts`;
- mapping payload `osmer_audit -> osmerAudit`;
- errore su meteo mancante o incompleto;
- lettura bollettino con completezza current rilassabile;
- Eventi Home richiede la raccolta canonica da 100 elementi;
- lat/lon eventi entrano solo quando entrambi finiti;
- stati backend `refreshing` e `partial` producono `shouldRetry`.

Non importato:

- cache `localStorage` meteo;
- cache `localStorage` eventi;
- retry con `setTimeout`;
- controlli active-location;
- reverse geocoding;
- bridge GPS;
- UI Home/Eventi;
- vecchio `App.jsx`.

Verifica tranche 5:

```text
npm run test
23 test file passati
181 test passati
npm run lint passato
npm run build passato
smoke locale http://127.0.0.1:5174/ passato con HTTP 200
```

Guardrail aggiornati:

- nessun import dei servizi dati dentro `frontend/src/app`, `frontend/src/features` o `frontend/src/ui`;
- nessun `fetch(` fuori da `frontend/src/services`;
- nessun `App.css` in `frontend/src`;
- nessun `!important` in `frontend/src`;
- nessun import di `WeatherMap`, `LiveView` o `EventsView` legacy;
- nessun `navigator.geolocation`;
- nessun `Capacitor`.

## Tranche 6 - Cache e chiavi localita

### Moduli estratti

| Fonte audit | Destinazione | Motivo | Dipendenze | Test |
| --- | --- | --- | --- | --- |
| `frontend/src/App.jsx` `getLocationCacheKey` | `frontend/src/domain/geo/locationCacheKey.js` | Isola la chiave localita usata da cache meteo/eventi. | nessuna | `locationCacheKey.test.js` |
| `frontend/src/App.jsx` `readJsonCache*` / `writeJsonCache` | `frontend/src/services/jsonCache.js` | Isola storage JSON con clock/storage iniettati. | nessuna | `jsonCache.test.js` |
| `frontend/src/App.jsx` cache bootstrap meteo | `frontend/src/services/weatherCache.js` | Isola chiavi/cache meteo e controllo presenza testo OSMER ufficiale. | `locationCacheKey.js`, `jsonCache.js` | `weatherCache.test.js` |
| `frontend/src/App.jsx` cache Eventi | `frontend/src/services/eventsCache.js` | Isola schema cache Eventi `single-source-v1`, limiti 8/100 e fallback legacy Home. | `locationCacheKey.js`, `eventsApi.js`, `jsonCache.js` | `eventsCache.test.js` |

Adattamenti effettuati:

- nessun componente e nessuna view usa ancora questi moduli;
- i test usano storage finto, non `localStorage` reale;
- `jsonCache` accetta `storage` e `now` iniettati per evitare side effect nei test;
- la chiave localita conserva il formato della app attuale: `city|lat|lon`, con `city` come marker quando le coordinate mancano;
- la cache meteo conserva prefisso `weatherBootstrapCache:v2`;
- la cache Eventi conserva prefisso `eventsCache:v10` e schema `single-source-v1`;
- la lettura Eventi continua a preferire la cache full `100` e usa la cache home `8` solo come fallback legacy.

Contratti protetti dai test:

- normalizzazione city lowercase/trim nella chiave cache;
- precisione coordinate a 4 decimali;
- lettura cache valida solo se non scaduta e con `savedAt` coerente;
- JSON rotto rimuove la voce senza rompere il flusso;
- scrittura cache non lancia errori se lo storage non e' disponibile;
- cache meteo scade dopo `WEATHER_CACHE_MAX_AGE_MS`;
- testo OSMER ufficiale viene rilevato da `current` o `forecast`;
- Eventi preferisce full cache `100`;
- Eventi cade su home cache `8` solo quando la full manca;
- payload Eventi viene marcato con schema `single-source-v1`.

Non importato:

- orchestrazione refresh meteo;
- orchestrazione refresh Eventi;
- retry Eventi con `setTimeout`;
- controlli `activeLocationKeyRef` / stale location;
- reverse geocoding;
- bridge GPS;
- pulizia massiva cache da impostazioni;
- collegamento alla Home o alla tab Eventi.

Verifica tranche 6:

```text
npm run test
27 test file passati
196 test passati
npm run lint passato
npm run build passato
smoke locale http://127.0.0.1:5174/ passato con HTTP 200
```

Guardrail aggiornati:

- nessun import cache dentro `frontend/src/app`, `frontend/src/features` o `frontend/src/ui`;
- nessun `fetch(` fuori da `frontend/src/services`;
- nessun `App.css` in `frontend/src`;
- nessun `!important` in `frontend/src`;
- nessun import di `WeatherMap`, `LiveView` o `EventsView` legacy;
- nessun `navigator.geolocation`;
- nessun `Capacitor`.

## Tranche 7 - Orchestratore dati Home

### Modulo creato

| Fonte audit | Destinazione | Motivo | Dipendenze | Test |
| --- | --- | --- | --- | --- |
| contratti estratti in tranche 4-6 | `frontend/src/features/home/homeDataController.js` | Compone meteo, cache, eventi e normalizzazione in uno stato dati per la futura Home. | `normalizedWeather.js`, `weatherApi.js`, `weatherCache.js`, `eventsApi.js`, `eventsCache.js` | `homeDataController.test.js` |

Decisioni:

- il controller non contiene JSX;
- nessuna view o shell importa ancora il controller;
- meteo ed Eventi sono caricati in parallelo quando serve;
- la cache fresca viene usata prima della rete;
- la rete viene chiamata solo se cache mancante/scaduta o se `force` e' attivo;
- la cache meteo stale puo' essere usata come fallback se il refresh fallisce;
- Eventi mantiene visibile la cache se un refresh forzato fallisce;
- payload Eventi `refreshing` o `partial` non vengono scritti in cache.

Contratti protetti dai test:

- cache meteo/Eventi evita chiamate servizio quando fresca;
- meteo fetchato viene normalizzato con `normalizeWeatherData`;
- `officialAlerts` e `osmerAudit` restano separati nello stato Home;
- Eventi Home continua a usare limite logico `8` e raccolta cache full `100`;
- cache meteo stale ritorna stato `stale` con errore, senza perdere il dato;
- cache Eventi resta visibile se refresh forzato fallisce;
- payload Eventi `refreshing` espone `shouldRetry` e non aggiorna la cache;
- cache legacy Eventi Home `8` resta fallback, non fonte preferita.

Non importato:

- UI Home definitiva;
- componenti Home legacy;
- scenetta meteo;
- ranking eventi;
- timer retry Eventi;
- active-location/stale-location guard runtime;
- pull-to-refresh;
- reverse geocoding;
- GPS bridge.

Verifica tranche 7:

```text
npm run test
28 test file passati
202 test passati
npm run lint passato
npm run build passato
smoke locale http://127.0.0.1:5174/ passato con HTTP 200
```

Guardrail aggiornati:

- nessun import di `homeDataController` dentro `frontend/src/app`, `frontend/src/ui` o `frontend/src/features/lab`;
- nessun `fetch(` fuori da `frontend/src/services`;
- nessun `App.css` in `frontend/src`;
- nessun `!important` in `frontend/src`;
- nessun import di `WeatherMap`, `LiveView` o `EventsView` legacy;
- nessun `navigator.geolocation`;
- nessun `Capacitor`.

## Tranche 8 - Home view model

### Modulo creato

| Fonte audit | Destinazione | Motivo | Dipendenze | Test |
| --- | --- | --- | --- | --- |
| contratti Home tranche 7 + copy/meteo esistenti | `frontend/src/features/home/homeViewModel.js` | Trasforma lo stato dati Home in dati gia pronti per i componenti visuali. | `normalizedWeather.js`, `unitFormats.js`, `temperatureSeverity.js`, `dailySummaryCopy.js`, `eventsViewCopy.js` | `homeViewModel.test.js` |

Decisioni:

- il view model non contiene JSX;
- nessuna view o shell importa ancora il view model;
- le label Home minime IT/FUR restano centralizzate nel modulo, non nel futuro JSX;
- il meteo viene presentato usando semantica e icon props esistenti;
- il vento resta overlay e non diventa condizione primaria;
- gli Eventi teaser vengono tagliati a un numero massimo configurabile;
- stati `cache`, `stale`, `error`, `refreshing`, `partial` diventano campi espliciti per la UI.

Contratti protetti dai test:

- temperatura, unita e severita sono gia formattate per la UI;
- dettagli Home sono ordinati e filtrano valori mancanti;
- condizione meteo localizzata usa la semantica esistente;
- vento forte su cielo sereno mantiene icona base sole e overlay vento;
- meteo stale conserva dati e messaggio di errore;
- meteo mancante produce modello vuoto, non eccezione;
- Eventi teaser mantiene item cache visibili se c'e' errore;
- Eventi `partial`/`refreshing` espone messaggio di aggiornamento e `shouldRetry`;
- FUR produce label localizzate nel contratto.

Non importato:

- Home UI definitiva;
- componenti Home legacy;
- scenetta meteo;
- CSS Home;
- hook React;
- chiamate rete;
- timer retry;
- collegamento runtime alla shell.

Verifica tranche 8:

```text
npm run test
29 test file passati
208 test passati
npm run lint passato
npm run build passato
smoke locale http://127.0.0.1:5174/ passato con HTTP 200
```

Guardrail aggiornati:

- nessun import di `homeViewModel` dentro `frontend/src/app`, `frontend/src/ui` o `frontend/src/features/lab`;
- nessun `fetch(` fuori da `frontend/src/services`;
- nessun `App.css` in `frontend/src`;
- nessun `!important` in `frontend/src`;
- nessun import di `WeatherMap`, `LiveView` o `EventsView` legacy;
- nessun `navigator.geolocation`;
- nessun `Capacitor`.

## Tranche 9 - Home UI statica laboratorio

### Componenti creati

| File | Ruolo | Dipendenze | Note |
| --- | --- | --- | --- |
| `frontend/src/features/home/homeFixture.js` | Fixture statica nel formato view model. | `homeViewModel.js` | Nessun dato live. |
| `frontend/src/features/home/HomeView.jsx` | Composizione Home UI. | fixture, componenti Home | Nessun fetch/hook dati. |
| `frontend/src/features/home/HomeWeatherHero.jsx` | Hero meteo/localita/stato. | `lucide-react`, `AppBadge` | Usa dati gia pronti. |
| `frontend/src/features/home/HomeDetailsGrid.jsx` | Dettagli meteo ordinati. | `lucide-react` | Renderizza `weather.details`. |
| `frontend/src/features/home/HomeEventsTeaser.jsx` | Teaser Eventi Home. | `lucide-react`, `AppButton` | Usa teaser gia preparati. |
| `frontend/src/features/home/home.css` | CSS feature Home. | token UI 3 | Classi `mf-home-*`, nessun `App.css`. |

Integrazioni effettuate:

- `frontend/src/features/lab/HomeLabView.jsx` ora renderizza `HomeView`;
- `frontend/src/ui/index.css` importa `features/home/home.css` nel layer `features`;
- `frontend/src/ui/components/components.css` aggiunge il tono badge `warning`;
- `frontend/src/ui/layout/layout.css` imposta shell a viewport height, scroll interno del `main` e bottom nav statica per evitare sovrapposizioni.

Decisioni:

- la Home e' una UI laboratorio statica;
- non usa `homeDataController`, cache, servizi o dati live;
- non importa componenti legacy;
- la fixture passa da `homeViewModel`, quindi la UI non interpreta meteo/eventi;
- CSS Home isolato nel file feature;
- nessuna scenetta meteo ancora importata.

Contratti protetti:

- hero mostra localita, condizione, temperatura, stato cache e alert ufficiali;
- dettagli meteo leggono il contratto `weather.details`;
- Eventi teaser mostra massimo 3 item dalla fixture;
- bottom nav non copre i contenuti dopo correzione shell;
- mobile 390px e desktop 920px senza overflow orizzontale.

Non importato:

- dati live;
- controller runtime;
- cache runtime;
- GPS;
- scenetta;
- componenti Home legacy;
- CSS legacy;
- pull-to-refresh;
- retry timer Eventi.

Verifica tranche 9:

```text
npm run test
29 test file passati
208 test passati
npm run lint passato
npm run build passato
smoke locale http://127.0.0.1:5174/ passato con HTTP 200
```

QA browser:

- Playwright con Edge di sistema;
- viewport mobile `390x844`: Home, dettagli ed Eventi teaser verificati;
- viewport desktop `920x900`: Home verificata;
- nessun overflow orizzontale;
- 3 Eventi e 7 dettagli renderizzati;
- unico log console: 404 di risorsa non critica, gia presente come asset/fav icon mancante, non legato alla Home.

Guardrail aggiornati:

- nessun `fetch(` fuori da `frontend/src/services`;
- nessun `App.css` in `frontend/src`;
- nessun `!important` in `frontend/src`;
- nessun import di `WeatherMap`, `LiveView` o `EventsView` legacy;
- nessun `navigator.geolocation`;
- nessun `Capacitor`;
- nessun import runtime di controller/cache/servizi dentro i componenti Home visuali o nel laboratorio Home.

## Tranche 10 - Ridisegno Home moderno

### Intervento visuale

| File | Ruolo | Note |
| --- | --- | --- |
| `frontend/src/features/home/HomeView.jsx` | Selezione gerarchia Home. | Mostra solo i 4 dettagli primari in Home: percepita, pioggia, vento, umidita. |
| `frontend/src/features/home/HomeWeatherHero.jsx` | Hero meteo ridisegnato. | Badge stato, temperatura forte, scena meteo code-native, insight aggiornamento/avvisi. |
| `frontend/src/features/home/HomeDetailsGrid.jsx` | Bento meteo. | Griglia pulita con classi per detail id. |
| `frontend/src/features/home/HomeEventsTeaser.jsx` | Teaser Eventi alleggerito. | Mostra 2 eventi in Home, senza cambiare il contratto dati. |
| `frontend/src/features/home/home.css` | Sistema visuale Home. | CSS feature scoped `mf-home-*`, micro-interazioni, bento e hero moderni. |
| `frontend/src/ui/layout/layout.css` | Rifinitura shell. | Scrollbar del `main` nascosta per resa piu app-like. |
| `frontend/src/features/home/homeViewModel.js` | Microcopy titolo dettagli. | `Dettagli` diventa `Oggi, in breve`; FUR allineato. |
| `frontend/index.html`, `frontend/public/favicon.svg` | Favicon. | Rimosso 404 browser su `/favicon.ico` usando favicon SVG collegato. |

Decisioni:

- nessuna logica meteo/eventi/GPS/notifiche/OSMER e' stata modificata;
- `homeDataController`, cache e servizi restano scollegati dalla Home laboratorio;
- i dettagli secondari restano nel modello, ma la Home non li mette in evidenza;
- il teaser Eventi alleggerisce la prima schermata senza cambiare fetch, cache o totale;
- la palette usa fondo freddo, blu Friul operativo e oro Friul come accento, senza tema monocolore;
- la preview e' stata verificata su mobile e desktop con screenshot locali.

Verifica tranche 10:

```text
npm run test
29 test file passati
208 test passati
npm run lint passato
npm run build passato
smoke locale http://127.0.0.1:5174/ passato con HTTP 200
```

QA browser:

- Browser integrato caricato su `http://127.0.0.1:5174/`, contenuto presente e console pulita;
- fallback Playwright con Edge di sistema per screenshot, per timeout tecnico del salvataggio immagini nel browser integrato;
- viewport mobile `390x844`: Home, hero, 4 bento meteo, teaser Eventi e bottom nav verificati;
- viewport desktop `1280x900`: layout centrato e leggibile verificato;
- interazione bottom nav: click su `Eventi` seleziona la tab e aggiorna heading a `Eventi`;
- nessun errore console e nessuna risposta 4xx dopo aggiunta favicon;
- controllo anti-overflow sul chip `Avvisi ufficiali: 1` passato.

Guardrail aggiornati:

- nessun `fetch(` fuori da `frontend/src/services`;
- nessun `App.css` in `frontend/src`;
- nessun `!important` in `frontend/src`;
- nessun import di `WeatherMap`, `LiveView` o `EventsView` legacy;
- nessun `navigator.geolocation`;
- nessun `Capacitor`;
- nessun import runtime di controller/cache/servizi dentro i componenti Home visuali o nel laboratorio Home.

## Tranche 11 - Personalita visuale Home

### Asset controllati

| Fonte | Destinazione | Motivo | Note |
| --- | --- | --- | --- |
| `frontend/public/logo-eagle-header.png` app attuale | `frontend/public/brand/logo-eagle-header.png` | Conservare un segno di brand gia presente nella app Meteo Friul. | Copia sorgente, non usata direttamente in UI. |
| `frontend/public/logo-eagle-header.png` app attuale | `frontend/public/brand/logo-eagle-mark.png` | Versione ritagliata per header piccolo. | Ritaglio non distruttivo. |
| `frontend/public/brand/logo-eagle-mark.png` | `frontend/public/brand/logo-eagle-mark.webp` | Asset servito ottimizzato. | Circa 14 KB. |
| asset generato per UI 3.0.0 | `frontend/public/backgrounds/home-friuli-landscape.png` | Sfondo territoriale Home. | Sorgente non servita direttamente in UI. |
| `home-friuli-landscape.png` | `frontend/public/backgrounds/home-friuli-landscape.webp` | Hero Home ottimizzata. | Circa 146 KB. |

### Intervento visuale

| File | Ruolo | Note |
| --- | --- | --- |
| `frontend/src/ui/layout/AppHeader.jsx` | Header brand. | Usa il marchio WebP ottimizzato. |
| `frontend/src/ui/layout/layout.css` | Trattamento brand. | Mark piu premium, meno placeholder. |
| `frontend/src/ui/base.css` | Sfondo app. | Motivo topografico leggero e carta alpina. |
| `frontend/src/ui/tokens/colors.css` | Token cromatici. | Aggiunti `deep-blue`, `river`, `alpine`, `stone`. |
| `frontend/src/features/home/HomeWeatherHero.jsx` | Hero Home. | Aggiunta fascia paesaggio decorativa code-native sopra asset. |
| `frontend/src/features/home/HomeDetailsGrid.jsx` | Bento dettagli. | Icone in medaglioni, layout piu compatto. |
| `frontend/src/features/home/home.css` | Personalita Home. | Hero territoriale, bento meno generico, eventi piu editoriali. |

Decisioni:

- la Home non deve piu sembrare una dashboard meteo generica;
- il marchio placeholder `M` viene sostituito da un segno brand controllato;
- il paesaggio vive come asset della Home, mentre testi e dati restano nativi;
- i WebP ottimizzati sono gli asset effettivamente serviti;
- nessuna logica dati, cache, GPS, notifiche, OSMER o Eventi e' stata modificata.

Verifica tranche 11:

```text
npm run test
29 test file passati
208 test passati
npm run lint passato
npm run build passato
```

QA browser:

- Browser integrato su `http://127.0.0.1:5174/`: contenuto presente e console pulita;
- screenshot integrato non salvabile per timeout CDP, fallback Playwright Edge usato per evidence visiva;
- viewport mobile `390x844`: hero, asset WebP, brand mark e 4 bento verificati;
- viewport desktop `1280x900`: layout centrato e leggibile verificato;
- click bottom nav `Eventi`: tab selezionata e heading aggiornato;
- nessun errore console e nessuna risposta 4xx;
- asset `home-friuli-landscape.webp` e `logo-eagle-mark.webp` caricati.

Guardrail aggiornati:

- nessun `fetch(` fuori da `frontend/src/services`;
- nessun `App.css` in `frontend/src`;
- nessun `!important` in `frontend/src`;
- nessun import di `WeatherMap`, `LiveView` o `EventsView` legacy;
- nessun `navigator.geolocation`;
- nessun `Capacitor`;
- nessun import runtime di controller/cache/servizi dentro i componenti Home visuali o nel laboratorio Home.

## Tranche 12 - Gerarchia informativa Home

### Intervento contenuto e UI

| File | Ruolo | Note |
| --- | --- | --- |
| `frontend/src/features/home/homeViewModel.js` | Contratto Home. | Aggiunti view model per `bulletin` e `almanac`; copy tecnico `cache/ora` reso piu leggibile. |
| `frontend/src/features/home/homeFixture.js` | Preview laboratorio. | Aggiunti contenuti statici per sintesi bollettino e Almanacco, con variante IT/FUR. |
| `frontend/src/features/home/HomeBulletinSummary.jsx` | Sezione Home. | Sintesi bollettino leggibile, senza interpretare OSMER. |
| `frontend/src/features/home/HomeAlmanacTeaser.jsx` | Sezione Home. | Teaser editoriale Almanacco. |
| `frontend/src/features/home/HomeView.jsx` | Composizione Home. | Ordine: hero, sintesi bollettino, dati rapidi, almanacco, eventi. |
| `frontend/src/features/home/HomeWeatherHero.jsx` | Hero meteo. | Nasconde badge cache/fresh; mostra stato solo per stale/error. |
| `frontend/src/features/home/home.css` | CSS feature. | Aggiunta famiglia `mf-home-feature-*`, senza CSS globale. |
| `frontend/src/ui/layout/layout.css` | Responsive shell. | Header mobile piu elastico sotto 420px, senza overflow orizzontale. |
| `frontend/src/app/App.jsx`, `frontend/src/app/AppRoutes.jsx`, `frontend/src/features/lab/HomeLabView.jsx` | Lingua laboratorio. | Passaggio lingua alla Home statica. |

Decisioni:

- `Dati da cache` non viene piu mostrato nella hero in stato normale;
- la formulazione generica dell'aggiornamento viene tolta dalla hero normale e rifinita in tranche 16 come tempo relativo;
- la sintesi bollettino e l'Almanacco sono sezioni visibili della Home;
- i nuovi contenuti sono fixture laboratorio, non dati live;
- nessuna logica meteo, cache, Eventi, GPS, notifiche o OSMER e' stata modificata.

Verifica tranche 12:

```text
npm run test
29 test file passati
209 test passati
npm run lint passato
npm run build passato
```

QA browser:

- Browser integrato su `http://127.0.0.1:5174/`: reload pulito, Home presente, console senza errori/warn successivi al reload;
- viewport Browser `390px`: `documentWidth` e `bodyWidth` pari a `390`, nessun overflow orizzontale;
- click bottom nav `Eventi`: tab selezionata e heading aggiornato a `Eventi`;
- fallback screenshot con Edge headless per timeout CDP screenshot del Browser integrato;
- screenshot preview a `500x844` e desktop `1280x900` salvati in `C:\tmp`.

Guardrail aggiornati:

- nessun `fetch(` fuori da `frontend/src/services`;
- nessun `App.css` in `frontend/src`;
- nessun `!important` in `frontend/src`;
- nessun import di `WeatherMap`, `LiveView` o `EventsView` legacy;
- nessun `navigator.geolocation`;
- nessun `Capacitor`;
- nessun import runtime di controller/cache/servizi dentro i componenti Home visuali o nel laboratorio Home.

## Tranche 13 - Rifinitura maturita Home

### Intervento strutturale

| File | Ruolo | Note |
| --- | --- | --- |
| `frontend/src/ui/layout/TabPage.jsx` | Titolo pagina. | Aggiunto `titleMode="hidden"` per mantenere H1 accessibile senza occupare spazio visivo. |
| `frontend/src/features/lab/HomeLabView.jsx` | Home laboratorio. | Usa titolo nascosto e classe `mf-tab-page--home`. |
| `frontend/src/features/home/HomeView.jsx` | Gerarchia Home. | Ordine aggiornato: hero, dettagli meteo, Eventi, sintesi bollettino, Almanacco. |
| `frontend/src/ui/layout/layout.css` | Shell responsive. | Header piu compatto, mark aquila meno pesante, bottom nav leggermente piu bassa. |
| `frontend/src/features/home/home.css` | Home visuale. | Hero piu bassa e meno cartolina, dettagli piu compatti, Eventi visibile nel primo viewport. |

Decisioni:

- il titolo `Home` resta per accessibilita ma non occupa piu spazio nella vista Home;
- la hero resta territoriale, ma con overlay piu meteo/brand e meno effetto cartolina;
- i quattro dati meteo restano subito dopo la hero;
- Eventi viene promosso sopra Bollettino/Almanacco per far capire nel primo impatto che l'app non e' solo meteo;
- Bollettino e Almanacco restano sezioni Home, ma come approfondimenti subito dopo il primo nucleo;
- nessuna logica meteo, cache, Eventi, GPS, notifiche o OSMER e' stata modificata.

Verifica tranche 13:

```text
npm run test
29 test file passati
209 test passati
npm run lint passato
npm run build passato
```

QA browser:

- Browser integrato su `http://127.0.0.1:5174/`: Home reload pulita, console senza errori/warn;
- viewport `390x844`: `documentWidth` 390, nessun overflow orizzontale;
- misure principali: hero 244px, dettagli chiusi a 530px, Eventi da 555px, prima card Eventi chiusa a 695px, bottom nav da 762px;
- click bottom nav `Eventi`: tab selezionata, heading `Eventi`, console pulita;
- screenshot Browser integrato riuscito;
- screenshot locali: `C:\tmp\meteo-friul-home-refined-compact.png`, `C:\tmp\meteo-friul-home-refined-desktop.png`.

Guardrail aggiornati:

- nessun `fetch(` fuori da `frontend/src/services`;
- nessun `App.css` in `frontend/src`;
- nessun `!important` in `frontend/src`;
- nessun import di `WeatherMap`, `LiveView` o `EventsView` legacy;
- nessun `navigator.geolocation`;
- nessun `Capacitor`;
- nessun import runtime di controller/cache/servizi dentro i componenti Home visuali o nel laboratorio Home.

## Tranche 14 - Eventi Home e copy avvisi

### Intervento mirato

| File | Ruolo | Note |
| --- | --- | --- |
| `frontend/src/features/home/HomeEventsTeaser.jsx` | Teaser Eventi Home. | Renderizza un solo evento in evidenza invece di due card compresse. |
| `frontend/src/features/home/homeViewModel.js` | Copy/contratto Home. | Trasforma `Avvisi ufficiali: 1` in un testo utente, poi rifinito in tranche 17. |
| `frontend/src/features/home/homeViewModel.test.js` | Test contratto. | Blocca singolare e plurale del testo avvisi. |
| `frontend/src/features/home/home.css` | Stile Home. | Aggiunge la variante `mf-home-event--featured`, senza CSS globale. |

Decisioni:

- la Home deve dare un assaggio degli Eventi, non provare a essere una lista;
- il totale eventi resta visibile nel sottotitolo e il CTA porta alla tab Eventi;
- il testo avvisi deve parlare da UI utente, non da diagnostica tecnica;
- il dato `officialAlerts` non viene modificato o filtrato, cambia solo la label di presentazione;
- nessuna logica meteo, cache, Eventi, GPS, notifiche o OSMER e' stata modificata.

Verifica tranche 14:

```text
npm run test
29 test file passati
210 test passati
npm run lint passato
npm run build passato
```

Guardrail aggiornati:

- nessun `fetch(` in `frontend/src`;
- nessun `App.css` in `frontend/src`;
- nessun `!important` in `frontend/src`;
- nessun import di `WeatherMap`, `LiveView` o `EventsView` legacy;
- nessun `navigator.geolocation`;
- nessun `Capacitor`;
- nessun vecchio testo `Avvisi ufficiali:`, `Dati da cache` o `Aggiornamento recente`.

## Tranche 15 - Header senza badge laboratorio

### Intervento mirato

| File | Ruolo | Note |
| --- | --- | --- |
| `frontend/src/ui/layout/AppHeader.jsx` | Header app. | Rimosso il badge visibile `Lab UI 3`. |
| `frontend/src/ui/layout/AppShell.jsx` | Shell app. | Non passa piu `labEnabled` all'header. |
| `frontend/src/app/uiShellCopy.js` | Copy shell. | Rimossa `labLabel`, non piu usata. |
| `frontend/src/ui/layout/layout.css` | CSS layout. | Rimossa regola mobile dedicata al badge header. |

Decisioni:

- il badge `Lab UI 3` era utile internamente, ma non aveva valore per l'utente;
- lo stato laboratorio resta nella shell come classe interna `is-lab`;
- l'header deve mostrare brand, lingua e impostazioni senza rumore tecnico;
- nessuna logica dati, cache, GPS, notifiche, routing o OSMER e' stata modificata.

Verifica tranche 15:

```text
npm run test
29 test file passati
210 test passati
npm run lint passato
npm run build passato
```

Guardrail aggiornati:

- nessun testo `Lab UI 3` in `frontend/src`;
- nessuna `labLabel` in `frontend/src`;
- nessun `fetch(` in `frontend/src`;
- nessun `App.css` in `frontend/src`;
- nessun `!important` in `frontend/src`;
- nessun import legacy `WeatherMap`, `LiveView` o `EventsView`;
- nessun `navigator.geolocation`;
- nessun `Capacitor`.

## Tranche 16 - Microtesto aggiornamento Home

### Intervento mirato

| File | Ruolo | Note |
| --- | --- | --- |
| `frontend/src/features/home/HomeWeatherHero.jsx` | Hero meteo. | L'aggiornamento non usa piu una pill e non mostra icona. |
| `frontend/src/features/home/homeViewModel.js` | Contratto Home. | Aggiunto formato relativo: `Aggiornato 5 minuti fa`, con fallback e plurali. |
| `frontend/src/features/home/homeViewModel.test.js` | Test contratto. | Bloccato il formato relativo con `now` iniettato e preview statica. |
| `frontend/src/features/home/homeFixture.js` | Preview Home. | Aggiunto `updatedAgoMinutes: 5` per la demo laboratorio. |
| `frontend/src/features/home/home.css` | Stile Home. | Aggiunto `mf-home-updated-text` senza background, bordo o radius. |

Decisioni:

- l'aggiornamento e' informazione secondaria e non deve competere con l'avviso meteo;
- l'avviso meteo resta l'unica pill nella riga inferiore della hero;
- il dato temporale resta nel view model, non viene calcolato nel JSX;
- nessuna logica meteo, cache, Eventi, GPS, notifiche o OSMER e' stata modificata.

Verifica tranche 16:

```text
npm run test
29 test file passati
211 test passati
npm run lint passato
npm run build passato
```

Browser QA:

- Browser integrato su `http://127.0.0.1:5174/`;
- viewport `390x844`: testo `Aggiornato 5 minuti fa`, background trasparente, border `0px`, radius `0px`;
- viewport `698x930`: stesso controllo superato, console senza warn/error;
- nessun overflow orizzontale.

Guardrail aggiornati:

- nessun `fetch(` in `frontend/src`;
- nessun `App.css` in `frontend/src`;
- nessun `!important` in `frontend/src`;
- nessun import legacy `WeatherMap`, `LiveView` o `EventsView`;
- nessun `navigator.geolocation`;
- nessun `Capacitor`;
- nessun vecchio testo `Aggiornamento recente`.

## Tranche 17 - Microtesto allerta Home

### Intervento mirato

| File | Ruolo | Note |
| --- | --- | --- |
| `frontend/src/features/home/HomeWeatherHero.jsx` | Hero meteo. | L'allerta non usa piu pill, sfondo, bordo o icona. |
| `frontend/src/features/home/homeViewModel.js` | Contratto Home. | Fallback `Allerta ufficiale`; label specifiche supportate, es. `Caldo intenso`. |
| `frontend/src/features/home/homeViewModel.test.js` | Test contratto. | Coperti singolare, plurale e label specifica. |
| `frontend/src/features/home/home.css` | Stile Home. | Rimosse classi `mf-home-insight`; aggiunta `mf-home-alert-text`. |

Decisioni:

- l'allerta resta visibile nella hero, ma non deve sembrare un bottone o una pill;
- `Allerta ufficiale` e' il fallback quando l'app riceve una singola allerta ufficiale senza label specifica;
- se il dato fornisce una label esplicita, la Home puo' mostrare un testo piu concreto come `Caldo intenso`;
- nessuna logica meteo, cache, Eventi, GPS, notifiche o OSMER e' stata modificata.

Verifica tranche 17:

```text
npm run test
29 test file passati
212 test passati
npm run lint passato
npm run build passato
```

Guardrail aggiornati:

- nessun `Avviso meteo` in `frontend/src`;
- nessuna classe `mf-home-insight` in `frontend/src`;
- nessun `fetch(` in `frontend/src`;
- nessun `App.css` in `frontend/src`;
- nessun `!important` in `frontend/src`;
- nessun import legacy `WeatherMap`, `LiveView` o `EventsView`;
- nessun `navigator.geolocation`;
- nessun `Capacitor`.

## Tranche 18 - Allerta ufficiale azionabile

### Intervento mirato

| File | Ruolo | Note |
| --- | --- | --- |
| `frontend/src/features/home/HomeWeatherHero.jsx` | Hero meteo. | Aggiunta icona triangolare `TriangleAlert`; elemento `button` solo per allerte ufficiali. |
| `frontend/src/features/home/HomeView.jsx` | Coordinamento Home. | Traduce l'azione ufficiale in navigazione verso `Bollettino`. |
| `frontend/src/features/lab/HomeLabView.jsx` | Preview laboratorio. | Propaga `onNavigate` alla Home. |
| `frontend/src/app/AppRoutes.jsx` | Routing app. | Propaga `onNavigate` alle view. |
| `frontend/src/app/App.jsx` | Shell app. | Passa `setActiveTab` alle route. |
| `frontend/src/features/home/homeViewModel.js` | Contratto Home. | Espone `alertSummary` con policy `isOfficial` e destinazione `official-alerts`. |
| `frontend/src/features/home/homeViewModel.test.js` | Test contratto. | Coperto fallback ufficiale, plurale, label specifica e action. |
| `frontend/src/features/home/home.css` | Stile Home. | Testo azionabile trasparente, senza pill, con focus visibile. |

Decisioni:

- la Home mostra `Allerta ufficiale` come richiamo sintetico, con icona di attenzione;
- il testo e' cliccabile solo quando arriva da `officialAlerts`;
- il click apre `Bollettino`, perche' la fonte autorevole dell'allerta vive nel bollettino;
- avvisi non ufficiali o messaggi informativi non devono diventare pulsanti;
- nessuna logica meteo, cache, Eventi, GPS, notifiche o OSMER e' stata modificata.

Verifica tranche 18:

```text
npm run test
29 test file passati
212 test passati
npm run lint passato
npm run build passato
Browser QA mobile 390x844 passato
```

Browser QA:

- `.mf-home-alert-text` e' `button` solo per `Allerta ufficiale`;
- sfondo trasparente, bordo `0`, radius `0`;
- icona SVG presente;
- vecchie classi `mf-home-insight` assenti;
- click su `Allerta ufficiale` porta al tab `Bollettino`;
- console senza warning/error.

## Tranche 19 - Label brevi per allerte Home

### Intervento mirato

| File | Ruolo | Note |
| --- | --- | --- |
| `frontend/src/features/home/homeViewModel.js` | Contratto Home. | Priorita' a colore ufficiale, poi fenomeno corto, poi fallback. |
| `frontend/src/features/home/homeViewModel.test.js` | Test contratto. | Coperti gialla/arancione/rossa, livello piu' alto e headline prolisse. |
| `README.md` | Decisione progetto. | Documentata la regola di sintesi Home. |
| `IMPORT_LOG.md` | Log import. | Tracciata la passata. |
| `MIGRATION_MAP.md` | Mappa migrazione. | Documentato confine Home/Bollettino. |
| `AUDIT_CHECKLIST.md` | Checklist audit. | Aggiunti controlli specifici sulle label corte. |

Decisioni:

- la Home deve usare label molto brevi: `Allerta gialla`, `Allerta arancione`, `Allerta rossa`;
- se sono presenti piu' allerte con livelli diversi, vince il livello piu' alto;
- fenomeni senza colore diventano label sintetiche, ad esempio `Allerta temporali`;
- titoli, headline e descrizioni ufficiali lunghe restano materia del Bollettino;
- nessuna logica meteo, cache, Eventi, GPS, notifiche o OSMER e' stata modificata.

Verifica tranche 19:

```text
npm run test -- homeViewModel
1 test file passato
13 test passati
npm run test
29 test file passati
215 test passati
npm run lint passato
npm run build passato
Browser QA mobile 390x844 passato
```

Browser QA:

- preview Home mostra `Allerta gialla` con icona triangolare;
- testo trasparente, senza pill;
- click su `Allerta gialla` porta al tab `Bollettino`;
- console senza warning/error.

## Tranche 20 - Colore livello allerta Home

### Intervento mirato

| File | Ruolo | Note |
| --- | --- | --- |
| `frontend/src/features/home/homeViewModel.js` | Contratto Home. | Aggiunti `level` e `tone` in `alertSummary`. |
| `frontend/src/features/home/HomeWeatherHero.jsx` | Hero meteo. | Applica solo classi tono controllate: `yellow`, `orange`, `red`, `neutral`. |
| `frontend/src/features/home/home.css` | Stile Home. | Colori dedicati per triangolo/testo allerta senza pill. |
| `frontend/src/features/home/homeViewModel.test.js` | Test contratto. | Coperti tono neutro e toni colore dai livelli ufficiali. |

Decisioni:

- il triangolo indica che il richiamo e' un'allerta ufficiale cliccabile;
- il colore indica il livello solo se il dato ufficiale contiene giallo/arancione/rosso;
- le allerte ufficiali senza livello colore usano `neutral`, cioe' ambra/oro, non giallo ufficiale;
- la UI non ricava il colore dalla label visibile;
- nessuna logica meteo, cache, Eventi, GPS, notifiche o OSMER e' stata modificata.

Verifica tranche 20:

```text
npm run test -- homeViewModel
1 test file passato
13 test passati
npm run test
29 test file passati
215 test passati
npm run lint passato
npm run build passato
Browser QA mobile 390x844 passato
```

Browser QA:

- preview Home mostra `Allerta gialla` con classe `mf-home-alert-text--yellow`;
- colore calcolato: `rgb(255, 228, 93)`;
- icona triangolare presente;
- nessuna pill: background trasparente, bordo `0`, radius `0`;
- click su `Allerta gialla` porta al tab `Bollettino`;
- console senza warning/error.

Guardrail aggiornati:

- nessun `Avviso meteo` in `frontend/src` runtime;
- nessuna classe `mf-home-insight` in `frontend/src` runtime;
- nessun `fetch(` in `frontend/src` runtime;
- nessun `App.css` in `frontend/src` runtime;
- nessun `!important` in `frontend/src` runtime;
- nessun import legacy `WeatherMap`, `LiveView` o `EventsView`;
- nessun `navigator.geolocation`;
- nessun `Capacitor`.

## Tranche 21 - Hero Home con immagine piu' pulita

### Intervento mirato

| File | Ruolo | Note |
| --- | --- | --- |
| `frontend/src/features/home/HomeWeatherHero.jsx` | Hero meteo. | Rimossi i nodi decorativi `mf-home-hero__landscape`, `ridge`, `river`. |
| `frontend/src/features/home/home.css` | Stile Home. | Background foto diretto; overlay ridotto a scrim leggero senza texture/radial. |

Decisioni:

- la foto deve restare visibile e pulita, non sembrare una cartolina filtrata;
- la leggibilita' del testo resta protetta da uno scrim minimo;
- niente elementi decorativi disegnati sopra il paesaggio;
- la barra superiore blu/fiume/oro resta come firma Meteo Friul;
- nessuna logica meteo, cache, Eventi, GPS, notifiche o OSMER e' stata modificata.

Verifica tranche 21:

```text
npm run test
29 test file passati
215 test passati
npm run lint passato
npm run build passato
Browser QA mobile 390x844 passato
```

Browser QA:

- `backgroundImage` della hero e' la sola foto `home-friuli-landscape.webp`;
- overlay `::after` senza `repeating-linear-gradient` e senza `radial-gradient`;
- nodi `mf-home-hero__landscape`, `ridge`, `river` assenti;
- temperatura, aggiornamento e allerta restano leggibili;
- click su `Allerta gialla` porta al tab `Bollettino`;
- console senza warning/error.

## Tranche 22 - Varianti meteo Home

### Intervento mirato

| File | Ruolo | Note |
| --- | --- | --- |
| `frontend/src/features/home/homeViewModel.js` | Contratto Home. | Espone `weatherVariant` da semantica/icona normalizzata. |
| `frontend/src/features/home/HomeWeatherHero.jsx` | Hero meteo. | Applica `data-weather-variant` e icona meteo coerente. |
| `frontend/src/features/home/home.css` | Stile Home. | Varianti `clear`, `partly`, `cloud`, `rain`, `storm`, `snow`, `fog`, `night` via variabili. |
| `frontend/src/features/home/homeViewModel.test.js` | Test contratto. | Coperti mapping varianti e notte trasversale. |

Decisioni:

- le varianti non cambiano la logica meteo, usano solo dati gia normalizzati;
- si parte con una sola immagine pulita e differenze atmosferiche sobrie;
- niente immagini multiple finche' il sistema base non e' stabile;
- la dark mode viene tracciata come fase progettuale successiva, non implementata in questa tranche;
- nessuna logica meteo, cache, Eventi, GPS, notifiche o OSMER e' stata modificata.

Verifica tranche 22:

```text
npm run test -- homeViewModel
1 test file passato
15 test passati
npm run test
29 test file passati
217 test passati
npm run lint passato
npm run build passato
Browser QA mobile 390x844 passato
```

Browser QA:

- stato reale preview: `data-weather-variant="clear"`;
- icona hero reale: `lucide-sun`;
- foto pulita con tint/scrim variante `clear`;
- overlay senza texture/radial;
- click su `Allerta gialla` porta al tab `Bollettino`;
- console senza warning/error.

## Tranche 23 - Preview laboratorio varianti meteo Home

### Intervento mirato

| File | Ruolo | Note |
| --- | --- | --- |
| `frontend/src/features/lab/homeVariantPreview.js` | Modelli demo varianti. | Costruisce modelli statici per confrontare le varianti senza dati live. |
| `frontend/src/features/lab/homeVariantPreview.test.js` | Test laboratorio. | Blocca id varianti e coerenza di rain/night. |
| `frontend/src/features/lab/HomeLabView.jsx` | Preview Home laboratorio. | Aggiunge selettore varianti e passa `model` a `HomeView`. |
| `frontend/src/features/lab/lab.css` | Stile laboratorio. | Stile scoped del controllo preview, senza CSS globale. |

Decisioni:

- la preview e' un telecomando di laboratorio, non una feature finale;
- le opzioni disponibili sono `clear`, `partly`, `cloud`, `rain`, `storm`, `snow`, `fog`, `night`;
- ogni opzione aggiorna condizione, icona, temperatura e dettagli principali per evitare preview incoerenti;
- nessuna logica meteo reale viene riscritta o interpretata nel JSX;
- nessun servizio, cache, GPS, notifiche o OSMER viene collegato.

Verifica tranche 23:

```text
npm run test -- homeVariantPreview
1 test file passato
3 test passati
npm run test
30 test file passati
220 test passati
npm run lint passato
npm run build passato
Browser QA interattiva passata
```

Browser QA:

- stato iniziale: `Sole`, `data-weather-variant="clear"`, icona `lucide-sun`;
- click `Pioggia`: `data-weather-variant="rain"`, icona `lucide-cloud-rain`, pioggia `6 mm`;
- click `Temporale`: `data-weather-variant="storm"`, icona `lucide-cloud-lightning`, pioggia `14 mm`;
- click `Neve`: `data-weather-variant="snow"`, icona `lucide-snowflake`;
- click `Notte`: `data-weather-variant="night"`, icona `lucide-moon`;
- console senza warning/error rilevanti.

## Tranche 24 - Background meteo dedicati Home

### Intervento mirato

| File | Ruolo | Note |
| --- | --- | --- |
| `frontend/src/features/home/home.css` | Sfondi hero. | Mappa le varianti a WebP dedicati e mantiene scrim per leggibilita'. |
| `frontend/src/features/home/homeViewModel.js` | Contratto varianti. | Aggiunge varianti combinate notturne. |
| `frontend/src/features/home/HomeWeatherHero.jsx` | Icona hero. | DÃ  priorita a pioggia/neve/temporale prima della luna generica. |
| `frontend/src/features/home/homeViewModel.test.js` | Test contratto. | Copre `rain-night`, `storm-night`, `snow-night`. |
| `frontend/src/features/lab/homeVariantPreview.js` | Preview laboratorio. | Aggiunge opzioni notturne combinate. |
| `frontend/src/features/lab/homeVariantPreview.test.js` | Test preview. | Copre opzioni e `snow-night`. |

Asset WebP generati da PNG sorgenti:

- `nebbia.webp`;
- `neve.webp`;
- `notte.webp`;
- `notte_e_neve.webp`;
- `notte_e_nuvoloso.webp`;
- `notte_e_pioggia.webp`;
- `notte_e_temporale.webp`;
- `nuvoloso.webp`;
- `pioggia.webp`;
- `temporale.webp`.

Decisioni:

- usare immagini meteo dedicate per evitare che neve/pioggia/nebbia sembrino solo filtri;
- mantenere la foto base solo per sole e poco nuvoloso;
- notte resta trasversale, ma con asset specifici quando il meteo e' pioggia, temporale, neve o nuvoloso;
- nessun servizio, cache, GPS, notifiche o OSMER viene collegato.

Verifica tranche 24:

```text
npm run test -- homeViewModel homeVariantPreview
2 test file passati
20 test passati
npm run test
30 test file passati
222 test passati
npm run lint passato
npm run build passato
Browser QA interattiva passata
```

Browser QA:

- `Sole`: background `home-friuli-landscape.webp`;
- `Neve`: background `neve.webp`, variante `snow`, icona `lucide-snowflake`;
- `Neve notte`: background `notte_e_neve.webp`, variante `snow-night`, icona `lucide-snowflake`;
- `Pioggia`: background `pioggia.webp`, variante `rain`, icona `lucide-cloud-rain`;
- `Temporale notte`: background `notte_e_temporale.webp`, variante `storm-night`, icona `lucide-cloud-lightning`;
- `Nebbia`: background `nebbia.webp`, variante `fog`, icona `lucide-cloud-fog`;
- console senza warning/error rilevanti.

## Tranche 25 - Scrim leggero sui background meteo

### Intervento mirato

| File | Ruolo | Note |
| --- | --- | --- |
| `frontend/src/features/home/home.css` | Leggibilita' hero. | Riduce lo scrim globale e lo concentra su testo/fondo. |

Decisioni:

- le immagini meteo devono restare leggibili come asset, non essere oscurate da un velo uniforme;
- lo scrim resta solo come protezione di leggibilita';
- niente maschere CSS, niente filtri pesanti, niente modifica ai file immagine;
- nessuna logica meteo, cache, GPS, notifiche, OSMER o Eventi modificata.

Verifica tranche 25:

```text
npm run build passato
Browser QA interattiva passata
```

Browser QA:

- `Neve`: background `neve.webp` piu' visibile, testo ancora leggibile;
- `Neve notte`: background `notte_e_neve.webp`, scrim ridotto ma contrasto preservato;
- `Nebbia`: background `nebbia.webp` leggibile, velatura meteo visibile;
- console senza warning/error rilevanti.

## Tranche 26 - Header brand da vecchia UX a UI 3

### Intervento mirato

| File | Ruolo | Note |
| --- | --- | --- |
| `frontend/src/app/uiShellCopy.js` | Copy shell UI. | Espone `brandTagline` e aggiorna il secondo termine del brand a `FriÃ»l`. |
| `frontend/src/ui/layout/AppHeader.jsx` | Header app. | Aggiunge stack titolo/sottotitolo, aria-label dinamico, azioni invariate. |
| `frontend/src/ui/layout/layout.css` | Stile layout. | Marchio aquila libero, titolo bi-colore e sottotitolo compatto. |

Decisioni:

- recuperare l'autorevolezza della vecchia UX senza tornare a un header datato;
- mantenere il sottotitolo come promessa di prodotto: meteo + idee per scoprire il Friuli;
- non modificare lingua/impostazioni in questa tranche;
- nessuna logica meteo, cache, GPS, notifiche, OSMER o Eventi modificata.

Verifica tranche 26:

```text
npm run test -- uiShellCopy passato
npm run lint passato
npm run build passato
Browser QA desktop/mobile passata
```

Browser QA:

- viewport 698x930: aquila visibile senza box, titolo/sottotitolo senza overflow, pulsanti invariati, console pulita;
- viewport 390x844: nessuna collisione brand/azioni, nessun overflow titolo/sottotitolo, hero non sovrapposta;
- screenshot header desktop acquisito con esito coerente alla direzione scelta.

## Tranche 27 - Preview varianti fuori dalla Home normale

### Intervento mirato

| File | Ruolo | Note |
| --- | --- | --- |
| `frontend/src/app/App.jsx` | Composizione shell/routes. | Passa `labEnabled` alle route. |
| `frontend/src/app/AppRoutes.jsx` | Routing UI 3. | Usa `HomeView` per Home normale e `HomeLabView` solo con lab attivo. |
| `frontend/src/app/labFlags.js` | Flag laboratorio. | Default lab disattivato. |
| `frontend/src/app/labFlags.test.js` | Regressione flag. | Aggiunti default off e storage esplicito. |

Decisioni:

- la preview `Varianti meteo` e' utile per QA, ma non e' parte della UX finale;
- la Home normale deve comunicare app reale: header, hero, meteo, eventi, bollettino, almanacco;
- il laboratorio resta disponibile con `?uiV3=1`;
- nessuna logica meteo, cache, GPS, notifiche, OSMER o Eventi modificata.

Verifica tranche 27:

```text
npm run test -- labFlags homeVariantPreview passato
npm run lint passato
npm run build passato
Browser QA desktop/mobile passata
```

Browser QA:

- `http://127.0.0.1:5174/`: preview assente, testo `Varianti meteo` assente, header e hero in cima;
- `http://127.0.0.1:5174/?uiV3=1`: preview presente e funzionante come lab;
- viewport 390x844: nessuna collisione header/hero/dettagli/Eventi, console pulita.

## Tranche 28 - Card meteo principali senza effetto multicolore

### Intervento mirato

| File | Ruolo | Note |
| --- | --- | --- |
| `frontend/src/features/home/home.css` | Stile Home. | Accento e icone delle quattro card meteo resi uniformi. |

Decisioni:

- evitare quattro colori diversi nello stesso gruppo informativo;
- usare un unico accento blu/fiume coerente con la marca;
- lasciare alle icone la distinzione semantica;
- nessuna logica meteo, cache, GPS, notifiche, OSMER o Eventi modificata.

Verifica tranche 28:

```text
npm run lint passato
npm run build passato
Browser QA mirata passata
```

Browser QA:

- tutte le card meteo principali hanno lo stesso accento `linear-gradient(90deg, blue, river)`;
- tutte le icone hanno stesso background, bordo e colore;
- nessun overflow sulle quattro card;
- console senza warning/error rilevanti.

## Tranche 29 - Mini-background allerta hero

### Intervento mirato

| File | Ruolo | Note |
| --- | --- | --- |
| `frontend/src/features/home/home.css` | Stile allerta Home. | Aggiunge fondo/ombra/bordo leggeri alla label allerta. |

Decisioni:

- migliorare contrasto e cliccabilita percepita dell'allerta sopra immagine;
- evitare ritorno a una pill piena e dominante;
- mantenere severity colore su testo/bordo;
- nessuna logica meteo, cache, GPS, notifiche, OSMER o Eventi modificata.

Verifica tranche 29:

```text
npm run lint passato
npm run build passato
Browser QA mirata passata
```

Browser QA:

- `Allerta gialla` mantiene testo compatto;
- background `rgba(2, 21, 36, 0.3)`, bordo severity e min-height 34px;
- nessun overflow;
- console senza warning/error rilevanti.

## Tranche 30 - Palette light morbida e dark mode a token

### Intervento mirato

| File | Ruolo | Note |
| --- | --- | --- |
| `frontend/src/app/themePreference.js` | Contratto tema. | Legge `?theme=light/dark/system`, storage e fallback light. |
| `frontend/src/app/themePreference.test.js` | Regressione tema. | Copre normalizzazione, query override, system e default. |
| `frontend/src/app/App.jsx` | Applicazione tema. | Imposta `document.documentElement.dataset.theme`. |
| `frontend/src/ui/layout/AppShell.jsx` | Shell. | Espone `data-theme` e classe `theme-*`. |
| `frontend/src/ui/tokens/colors.css` | Palette. | Light ammorbidita e dark tokens. |
| `frontend/src/ui/tokens/shadows.css` | Ombre. | Ombre dark dedicate. |
| `frontend/src/ui/base.css` | Background app. | Usa token di background. |
| `frontend/src/ui/layout/layout.css` | Bottom nav. | Usa `--mf-nav-bg`. |
| `frontend/src/features/home/home.css` | Superfici Home. | Card e feature card leggono token tema. |

Decisioni:

- non copiare la palette scura della reference come default;
- rendere la light meno fredda e piu' territoriale;
- usare la reference come direzione per una dark mode blu notte/oro caldo;
- mantenere default light e preview dark con `?theme=dark`;
- nessuna logica meteo, cache, GPS, notifiche, OSMER o Eventi modificata.

Verifica tranche 30:

```text
npm run test -- themePreference labFlags passato
npm run lint passato
npm run build passato
Browser QA light/dark passata
```

Browser QA:

- `http://127.0.0.1:5174/`: tema `light`, body `#f3f7f4`, preview lab assente;
- `http://127.0.0.1:5174/?theme=dark`: tema `dark`, body `#061a2e`, bottom nav navy, card scure leggibili;
- console senza warning/error rilevanti.

## Tranche 31 - Iniziale oro sui titoli pagina FUR

### Intervento mirato

| File | Ruolo | Note |
| --- | --- | --- |
| `frontend/src/ui/layout/TabPage.jsx` | Titoli schermata. | Renderizza iniziale oro solo con `language="fur"`. |
| `frontend/src/ui/layout/layout.css` | Stile titolo. | Colora solo `.mf-tab-page__title-initial`. |
| viste lab | Passaggio lingua. | Passano `language` a `TabPage`. |

Decisioni:

- recuperare il dettaglio identitario FUR sui titoli pagina, non sulla bottom nav;
- lasciare la copy invariata;
- mantenere testo semanticamente compatto (`Boletin`);
- nessuna logica meteo, cache, GPS, notifiche, OSMER o Eventi modificata.

Verifica tranche 31:

```text
npm run lint passato
npm run build passato
Browser QA dark/FUR passata
```

Browser QA:

- in dark/FUR il titolo `Boletin` ha iniziale `B` oro `rgb(242, 201, 76)`;
- bottom nav non contiene classi di accento sulle label;
- testo titolo compatto `Boletin`;
- console senza warning/error rilevanti.

## Tranche 32 - Titoli pagina blu in light, chiari in dark

### Intervento mirato

| File | Ruolo | Note |
| --- | --- | --- |
| `frontend/src/ui/layout/layout.css` | Colore titoli pagina. | `h1` blu Friul in light, chiaro in dark. |

Decisioni:

- in light/default mode i titoli schermata devono essere blu Friul e non neri;
- in FUR l'iniziale oro resta un micro-accento identitario sopra il titolo blu;
- in dark mode il titolo resta chiaro per coerenza notturna;
- nessuna modifica alla bottom nav;
- nessuna logica meteo, cache, GPS, notifiche, OSMER o Eventi modificata.

Verifica tranche 32:

```text
npm run lint passato
npm run build passato
Browser QA light/dark IT/FUR passata
```

Browser QA:

- light IT `Bollettino`: titolo `rgb(0, 115, 207)`;
- light FUR `Boletin`: titolo `rgb(0, 115, 207)`, iniziale `rgb(212, 175, 55)`;
- dark IT `Bollettino`: titolo `rgb(244, 248, 252)`;
- dark FUR `Boletin`: titolo `rgb(244, 248, 252)`, iniziale `rgb(242, 201, 76)`;
- console senza warning/error rilevanti.

## Tranche 33 - Accento bottom nav light/dark

File modificati:

| File | Ruolo | Note |
| --- | --- | --- |
| `frontend/src/ui/tokens/colors.css` | Token nav attiva. | Aggiunge `--mf-nav-active-*` per light/dark. |
| `frontend/src/ui/layout/layout.css` | Stato nav attivo. | Mini-barra oro, bordo e fondo tokenizzati. |

Decisioni:

- reintrodurre l'oro nella bottom nav solo come accento dello stato attivo;
- evitare pulsanti pieni oro per non appesantire un elemento permanente;
- usare token light/dark dedicati invece di sovrascritture locali;
- nessuna logica meteo, cache, GPS, notifiche, OSMER o Eventi modificata.

Verifica tranche 33:

```text
npm run lint passato
npm run build passato
Browser QA light/dark navbar passata
```

Browser QA:

- light: tab `Eventi` attiva con accento `rgb(212, 175, 55)` e bordo `rgba(212, 175, 55, 0.7)`;
- dark: tab `Eventi` attiva con accento `rgb(242, 201, 76)` e bordo `rgba(242, 201, 76, 0.58)`;
- click navbar `Eventi` verificato in light e dark;
- console senza warning/error rilevanti.

## Tranche 34 - Oro identitario unico

File modificati:

| File | Ruolo | Note |
| --- | --- | --- |
| `frontend/src/ui/tokens/colors.css` | Token oro. | Aggiunge `--mf-gold-rgb` e deriva bordi/fondi alpha dallo stesso oro. |
| `frontend/src/ui/layout/layout.css` | Brand/titoli. | `Friul` e iniziali FUR usano entrambi `--mf-gold`. |
| `frontend/src/features/home/home.css` | Fondi oro alpha. | Almanacco e linee decorative usano `--mf-gold-rgb`. |
| `frontend/src/features/lab/lab.css` | Fondo lab. | Gradiente oro alpha derivato da `--mf-gold-rgb`. |

Decisioni:

- `--mf-gold` e' il token identitario per brand, iniziali FUR e accenti principali;
- `--mf-gold-rgb` serve solo per alpha coerenti;
- `--mf-gold-700` resta un token di contrasto secondario, non un oro brand alternativo;
- nessuna logica meteo, cache, GPS, notifiche, OSMER o Eventi modificata.

Verifica tranche 34:

```text
npm run lint passato
npm run build passato
Browser QA light/dark oro passata
```

Browser QA:

- light: brand `Friul`, iniziali `Boletin/Cjale/Evenis/Scuvierc` e accento navbar `rgb(212, 175, 55)`;
- dark: brand `Friul`, iniziali `Boletin/Cjale/Evenis/Scuvierc` e accento navbar `rgb(242, 201, 76)`;
- console senza warning/error rilevanti.

## Verifica tranche 2

Comandi:

```text
npm run test
npm run lint
npm run build
```

Esito:

```text
12 test file passati
44 test passati
lint passato
build passato
```

Guardrail aggiuntivi:

- nessun `fetch(` in `frontend/src`;
- nessun `App.css` in `frontend/src`;
- nessun `!important` in `frontend/src`;
- nessun import di `WeatherMap`, `LiveView` o `EventsView` legacy;
- unico `localStorage` presente: lettura flag laboratorio `uiV3`.

## Tranche 35 - Prima pagina Bollettino con mappa Meteo Friul

File modificati:

| File | Ruolo | Note |
| --- | --- | --- |
| `frontend/src/features/bulletin/BulletinView.jsx` | Vista Bollettino. | Fonte, allerta, mappa, tab giorni, sintesi e dati utili. |
| `frontend/src/features/bulletin/BulletinMap.jsx` | Mappa interna. | SVG base FVG, overlay icone e badge Meteo Friul. |
| `frontend/src/features/bulletin/bulletinFixture.js` | Fixture UI. | Punti, icone, badge e copy; nessuna fetch. |
| `frontend/src/features/bulletin/bulletin.css` | Stile feature. | Card e mappa isolate su token UI 3. |
| `frontend/src/app/AppRoutes.jsx` | Routing UI. | Route `bulletin` collegata alla nuova vista. |
| `frontend/src/ui/index.css` | Import CSS. | Import del CSS Bollettino nel layer `features`. |

Decisioni:

- il Bollettino non replica la Home: priorita' a fonte ARPA/OSMER e mappa;
- la base mappa e' interna, SVG, e non dipende da provider tile esterni;
- la maschera non usa immagini OSMER: e' overlay dati proprietario con icone Meteo Friul;
- se l'overlay dati manca, viene mostrato un avviso sopra la mappa senza nascondere la base;
- Google Maps e OpenStreetMap runtime non sono usati nella vista Bollettino;
- fonte dati visibile nella card `OSMER ARPA FVG`;
- nessuna logica meteo, cache, GPS, notifiche, OSMER o Eventi modificata.

Verifica tranche 35:

```text
npm run lint passato
npm run build passato
Browser QA mobile light passata
```

Browser QA:

- mappa SVG interna renderizzata correttamente;
- overlay icone/badge renderizzato da fixture dati;
- fallback maschera mancante verificato con preview dev `?bulletinMask=missing`;
- fonte `OSMER ARPA FVG` visibile nella card dedicata;
- nessun overflow orizzontale;
- bottom nav non copre la card mappa.

Aggiornamento successivo:

- rimossa la lista `Zone del bollettino`;
- aggiunta griglia `Dati utili` con alba, tramonto, umidita, pollini, UV e vento;
- i dati sono ancora fixture UI e andranno collegati al data controller reale.

Aggiornamento successivo:

- rimossa la didascalia/link sotto la mappa;
- inserita la firma `Mappa Meteo Friul` direttamente dentro l'SVG, sull'area azzurra;
- evitata duplicazione dei riferimenti ARPA/OSMER sotto la mappa, gia' presenti nella card fonte.

Aggiornamento successivo:

- rimossa la riga separata `Aggiornato` dalla card fonte;
- spostato l'orario di aggiornamento accanto al titolo `OSMER ARPA FVG`;
- rimossa la card `Testo ARPA`, per evitare duplicazione del testo gia' presente nella sintesi;
- la card fonte resta concentrata su nome fonte, aggiornamento compatto e link.

Aggiornamento successivo:

- aumentata la scala visuale della mappa Bollettino su mobile;
- ridotto leggermente il padding della cornice mappa;
- invariati geometria SVG, overlay, marker, badge e fixture dati.

Aggiornamento successivo:

- rimossa la card fonte autonoma `OSMER ARPA FVG`;
- spostati fonte, aggiornamento e link `www.meteo.fvg.it` dentro la sintesi del bollettino, subito sotto titolo/data;
- la fonte resta disponibile come metadato del bollettino, non come blocco separato sopra la mappa.

## Nota progettuale Almanacco - Astro Friul

Decisione annotata:

- possibile rubrica futura `Astro Friul` / `Consiglio lunare`;
- tono ironico, locale e dichiaratamente editoriale, non oroscopo serio;
- input possibili: data, segno zodiacale del periodo, fase lunare, meteo del giorno;
- output: consiglio pratico o battuta breve, senza predizioni assolute;
- posizione: Almanacco, non Bollettino;
- implementare solo dopo audit dei dati Almanacco/luna e senza mescolare la logica meteo ufficiale.

## Nota progettuale Scopri - Accadde oggi / Pillole di Friuli

Decisione annotata:

- rubrica futura consigliata e prioritaria per la tab `Scopri`;
- nomi possibili: `Accadde oggi`, `Pillola friulana`, `Oggi in Friuli`, `Memoria del giorno`;
- contenuto breve, 1-2 righe, su storia locale, cultura, lingua, tradizioni, stagioni e territorio;
- gestione tramite archivio controllato, non scraping automatico;
- schema dati proposto: `date`, `title`, `body`, `area`, `source`, `tags`;
- partire da 50-100 pillole curate e prevedere rotazione giornaliera quando non c'e' un evento specifico;
- posizione: `Scopri`, con eventuale teaser in Almanacco se serve collegare giorno e territorio.

## Tranche 36 - Chiusura Bollettino e prima pagina Almanacco

File modificati:

| File | Ruolo | Note |
| --- | --- | --- |
| `frontend/src/app/appConfig.js` | Routing UI. | Aggiunge `APP_ROUTE_IDS` con route interna `almanac`, senza cambiare bottom nav. |
| `frontend/src/app/App.jsx` | Stato route/shell. | Accetta route interne e mantiene Home attiva in bottom nav per Almanacco. |
| `frontend/src/app/AppRoutes.jsx` | Routing UI. | Collega `AlmanacView`. |
| `frontend/src/ui/layout/AppShell.jsx` | Scroll shell. | Riporta lo scroll del main a inizio pagina a ogni cambio route. |
| `frontend/src/app/uiShellCopy.js` | Copy placeholder. | Aggiunge titolo/body placeholder IT per Almanacco. |
| `frontend/src/features/home/HomeAlmanacTeaser.jsx` | CTA Home. | Rende azionabile il bottone Almanacco. |
| `frontend/src/features/home/HomeView.jsx` | Composizione Home. | Collega la CTA alla route `almanac`. |
| `frontend/src/features/almanac/AlmanacView.jsx` | Vista Almanacco. | Prima UI fixture/editoriale con Santo, sole, luna, tradizione, proverbio, terra e ponte Scopri. |
| `frontend/src/features/almanac/almanacFixture.js` | Fixture Almanacco. | Dati statici IT/FUR per disegno, senza fetch o controller reale. |
| `frontend/src/features/almanac/almanac.css` | Stile Almanacco. | CSS dedicato e tokenizzato. |
| `frontend/src/ui/index.css` | Import CSS. | Import del CSS Almanacco nel layer `features`. |
| `AUDIT_CHECKLIST.md` | Traccia audit. | Aggiunta sezione di chiusura Bollettino/avvio Almanacco. |

Decisioni:

- il Bollettino e' stato ricontrollato prima di aprire il cantiere Almanacco;
- la pagina Almanacco nasce come approfondimento raggiungibile dalla Home, non come sesto item in bottom nav;
- `Accadde oggi` resta destinato a `Scopri`, con eventuale teaser futuro;
- il Santo del giorno e' elemento primario dell'Almanacco, subito dopo la hero;
- i dati Almanacco sono fixture controllate per disegno, non import live;
- nessuna logica meteo, cache, GPS, notifiche, Eventi o OSMER e' stata modificata.

Verifica tranche 36:

```text
npm run lint passato
npm run build passato
npm run test
31 test file passati
228 test passati
Browser QA Bollettino light/dark/mobile passato con DOM/interazioni
Browser QA Almanacco 390x844 light/dark passato con DOM/interazioni
```

Note QA:

- il canale screenshot del browser integrato ha restituito timeout `Page.captureScreenshot`; la verifica visuale e' stata quindi basata su DOM, misure, scroll, overflow e interazioni;
- l'Almanacco a `390x844` non ha overflow orizzontale;
- il Santo del giorno e' visibile nel primo viewport;
- le icone Sole nella griglia alba/luce/tramonto restano 18x18;
- lo scroll del main torna a `0` passando da Home ad Almanacco e viceversa.

Aggiornamento successivo Almanacco:

- tradizione e proverbio sono stati accorpati in un unico blocco culturale;
- i contenuti pratici restano consecutivi: sole/luna, poi consigli della terra;
- rimosse le linee decorative sfumate inferiori dalle card Almanacco principali;
- nessun dato live e nessuna logica meteo/Eventi/GPS/notifiche/OSMER modificata.

Aggiornamento UI Sole/Luna Almanacco:

- rimossa la hero editoriale con titolo/frase/bottone Home;
- introdotta riga compatta con data, stagione e giorno dell'anno;
- Sole e Luna restano in colonna anche su viewport largo della shell mobile;
- Sole ridisegnato come schema elegante, con arco sottile e senza paesaggio/illustrazione pesante;
- Luna riallineata allo schema storico: icona fase, barra, illuminazione, ciclo lunare, prossima fase e tradizione;
- verificati lint, build, test e browser QA light/dark/mobile.

Aggiornamento gerarchia Almanacco:

- spostata `Tradizione del giorno` subito dopo `Santo del giorno`, per tenere vicini calendario, santorale e cultura popolare;
- mantenuto `Proverbio` dentro la card Tradizione come nota secondaria;
- ripristinati i titoli `SOLE` e `LUNA` come label rubrica compatte, con icone blu e testo nero per evitare oro poco leggibile su card chiara.
- sostituito `--mf-blue-600` con il token reale `--mf-blue` negli accenti Almanacco interessati.
- allineate `Santo del giorno` e `Tradizione del giorno` alla gerarchia editoriale storica: icona blu, label oro, titolo nero e fonte/testo sotto.
- sostituita l'icona calendario del Santo con `Church`, mantenendo il calendario nella riga data.

Aggiornamento successivo Sole Almanacco:

- eliminato il residuo di paesaggio SVG nella card Sole;
- ridotta la parte grafica a traiettoria sottile, marker alba/tramonto/mezzogiorno e punto luce;
- verificata preview browser `390x844`: Sole prima di Luna, nessun overflow, console pulita.

Aggiornamento integrazione dati Sole:

- rimossi i tre riquadri dati sotto lo schema Sole;
- integrati `Alba`, `Luce` e `Tramonto` direttamente nello schema SVG;
- card Sole ridotta a circa `208px` nel viewport `390x844`;
- verificata preview browser: nessun overflow, console pulita.

Correzione geometria curva Sole:

- ridimensionato l'arco nel viewBox per evitare il taglio superiore/centrale;
- spostato il punto sole fuori dalla porzione critica della curva;
- verificata preview browser `390x844` con screenshot, nessun overflow e console pulita.

Passaggio intermedio arco Sole, poi superato:

- sostituito il semicerchio alto con un arco ellittico ribassato (`A88 54`);
- l'arco resta interamente visibile nella card e non viene piu' tagliato in alto;
- verificati screenshot browser, lint, build e test prima della successiva decisione di abbandonare l'arco.

Sostituzione schema Sole:

- abbandonato lo schema ad arco dopo review visuale: era fragile, decorativo e meno coerente con la Luna;
- introdotta rappresentazione solare parallela alla Luna: orb, durata luce, barra di avanzamento, alba e tramonto;
- rimossi residui dell'arco e del punto luce centrale;
- verificata preview browser `390x844` light con screenshot, nessun overflow e console pulita.

Riorganizzazione dati Sole/Luna:

- sostituita la label tecnica `Altezza max` con la frase leggibile `Sole alto - 67 gradi sopra l'orizzonte`;
- la card Sole ora segue gerarchia: durata luce, label, barra, frase interpretativa, alba/tramonto;
- la card Luna ora segue la stessa grammatica: fase, eta lunare, barra, sintesi `61% illuminata - ciclo 29%`, prossima fase e tradizione;
- rimossi i box Luna `Illuminazione` e `Ciclo lunare`, per evitare duplicazione della sintesi sotto la barra;
- rimosso dall'orb Sole il `conic-gradient` che in piccolo sembrava una striscia/raggio giallo;
- rimosso dall'orb Luna il radial-gradient decorativo: la fase resta pulita, senza puntini/crateri che sporcano in piccolo;
- rimossa l'eccezione oro dalla riga data Almanacco: i metadati ordinari restano neutri, l'oro rimane per brand/accenti significativi;
- evitata label tecnica come `declinazione solare`, troppo specialistica per la card principale;
- barre ancora alimentate da percentuali fixture UI: calcolo live Sole/Luna da collegare solo dopo audit del data controller Almanacco;
- nessuna logica meteo, cache, GPS, notifiche, Eventi o OSMER modificata.

Chiusura placeholder Almanacco:

- rimosso dal render Almanacco il ponte `Pillole di Friuli` verso `Scopri`, per evitare un contenuto di servizio senza valore editoriale;
- mantenuta la destinazione progettuale: `Pillole di Friuli` / `Accadde oggi` andra' disegnata dentro `Scopri` con archivio e fonti controllate;
- resa piu' chiara la riga data: `Inizio estate` diventa `Estate, giorno 3`;
- corretti accenti IT fixture visibili in `Martedi`, `Eta lunare` e `umidita`;
- alleggerita la lista `Consigli della terra`, senza cambiare contenuto o dati;
- rifinita la lista `Consigli della terra` come sequenza editoriale numerata, eliminando l'effetto mini-card;
- nessuna logica meteo, cache, GPS, notifiche, Eventi o OSMER modificata.

Rigerarchizzazione Home meteo:

- rimossa dalla Home la griglia tecnica `Percepita` / `Pioggia` / `Vento` / `Umidita`;
- spostata `Percepita` sotto la temperatura principale nella hero, come dato immediato di comfort;
- ordinata la Home dopo la hero come `Sintesi bollettino`, `Almanacco`, `Eventi`;
- aggiunta `Pioggia` ai `Dati utili` del Bollettino, dove gia' vivono `Umidita` e `Vento`;
- eliminata la componente `HomeDetailsGrid` e le relative regole CSS non piu' usate;
- nessuna logica meteo, cache, GPS, notifiche, Eventi o OSMER modificata.

## Tranche 37 - Contratto dati reale Almanacco

File importati dalla app attuale:

| Fonte | Destinazione | Motivo | Note |
| --- | --- | --- | --- |
| `frontend/src/data/almanac/saints.json` | `frontend/src/data/almanac/saints.json` | Calendario santi offline controllato. | Normalizzato BOM; nessun cambio contenuto. |
| `frontend/src/data/almanac/proverbs.json` | `frontend/src/data/almanac/proverbs.json` | Proverbi giornalieri e fallback deterministico. | Normalizzato BOM; nessun cambio contenuto. |
| `frontend/src/data/almanac/earthTips.json` | `frontend/src/data/almanac/earthTips.json` | Consigli mensili della terra. | Normalizzato BOM; nessun cambio contenuto. |
| `frontend/src/data/almanac/schedule.json` | `frontend/src/data/almanac/schedule.json` | Proverbi fissati per date speciali. | Normalizzato BOM; nessun cambio contenuto. |
| `frontend/src/data/ostermannCulturalDiscover.json` | `frontend/src/data/ostermannCulturalDiscover.json` | Tradizioni `section: almanacco` da Ostermann. | Importato intero per evitare selezioni manuali non tracciate. |

File creati:

| File | Ruolo |
| --- | --- |
| `frontend/src/domain/almanac/moonPhase.js` | Calcolo fase lunare, eta lunare, ciclo e illuminazione. |
| `frontend/src/domain/almanac/sunCycle.js` | Calcolo alba, tramonto, durata luce, progresso luce e altezza massima del sole. |
| `frontend/src/domain/almanac/almanacData.js` | Selezione controllata di santo, tradizione, proverbio e consigli della terra. |
| `frontend/src/features/almanac/almanacViewModel.js` | Adattatore dati -> contratto visuale della pagina Almanacco. |
| `frontend/src/domain/almanac/*.test.js` | Test dati/sole/luna/selezione. |
| `frontend/src/features/almanac/almanacViewModel.test.js` | Test del contratto UI Almanacco. |

File rimossi/aggiornati:

| File | Decisione |
| --- | --- |
| `frontend/src/features/almanac/almanacFixture.js` | Rimossa: non serve piu' una seconda fonte statica. |
| `frontend/src/features/almanac/AlmanacView.jsx` | Ora legge `buildAlmanacViewModel`, non fixture. |
| `frontend/src/app/AppRoutes.jsx` | Route Almanacco in lazy loading per non appesantire il bundle principale. |

Decisioni:

- non e' stato importato il vecchio componente `AlmanacView.jsx`;
- non e' stato importato il vecchio hook `useAlmanacData.js` intero, perche' mescola ranking culturale, meteo e view concern;
- la selezione `Tradizione del giorno` usa solo record Ostermann con `section: almanacco`, non la futura rubrica `Accadde oggi` destinata a `Scopri`;
- il Santo del giorno usa il calendario offline importato e non fa scraping;
- Sole e Luna sono calcolati localmente con funzioni pure;
- i consigli della terra usano mese e tag meteo semplici, senza interpretare OSMER;
- i dati Almanacco sono locali e testati, senza fetch/backend/API.

Verifica tranche 37:

```text
npm run test -- almanac
4 test file passati
13 test passati
npm run build passato
bundle principale ridotto: index ~288 kB, AlmanacView lazy chunk ~462 kB
```

## Tranche 38 - Readiness proverbi Ostermann

File creati:

| File | Ruolo |
| --- | --- |
| `frontend/src/data/almanac/ostermannProverbSources.json` | Piano sorgenti Ostermann per ampliare l'archivio proverbi senza inserire candidati grezzi nella UI. |
| `frontend/src/domain/almanac/proverbArchiveReadiness.js` | Guardrail dati per misurare copertura 366 giorni, archivio minimo e record da revisione encoding. |
| `frontend/src/domain/almanac/proverbArchiveReadiness.test.js` | Test copertura attuale e comportamento del guardrail. |

Audit dati prima della promozione controllata:

- Ostermann culturale importato: 59 record totali, 49 destinati ad Almanacco.
- Proverbi attuali: 40 record, 31 `homeEligible`.
- Slot giornalieri fissati: 5 date piu' fallback.
- Obiettivo corretto: 366 slot datati, con archivio consigliato di almeno 500 record per evitare rotazioni troppo rigide.
- 21 record dei proverbi legacy mostravano caratteri sospetti/mojibake e vanno rivisti prima di promozione stabile.

Decisioni:

- Ostermann va integrato come fonte editoriale primaria di `Scopri`; l'Almanacco usa solo un sottoinsieme giornaliero/teaser.
- Non si riempie `proverbs.json` con estrazioni grezze.
- Ogni proverbio promosso dovra' avere fonte/pagina, stato revisione, FUR normalizzato e traduzione IT controllata.
- Nessuna modifica a UI, meteo, Eventi, GPS, notifiche o OSMER.

Aggiornamento fondazione editoriale:

- creato `frontend/src/data/almanac/proverbCandidates.json` come archivio di lavoro separato dalla UI;
- lo stato `candidate` non e' pubblicabile;
- un candidato diventa promuovibile solo con stato `ready`, testo FUR/IT, fonte con pagina e nessun mojibake rilevato;
- il guardrail ora conta anche candidati totali e candidati pronti alla promozione.

Prima tranche candidati:

- estratti candidati da Ostermann pagine 103, 105, 190 e 193;
- ogni record contiene `furOriginal`, `fur`, `it`, pagina PDF/testo, path fonte, tag, stagione/date anchor e note revisione;
- tutti i record restano `source_checked` e `homeEligible: false`;
- nessun candidato entra nella UI finche' non viene promosso manualmente a `proverbs.json`.

Prima review editoriale:

- creato `frontend/src/data/almanac/proverbCandidateReview.json`;
- creato `frontend/src/domain/almanac/proverbCandidateReview.js` con test;
- separati i giudizi editoriali dai record sorgente;
- individuata shortlist di candidati forti da promuovere solo dopo revisione FUR/IT;
- corretta la regex del guardrail encoding: `Ã¢` e' una lettera valida, non mojibake; restano sospette sequenze come `Ãƒ`, `Ã…`, `Ã‚`, `Ã¢â‚¬`.

Prima promozione controllata:

- promossi 8 record Ostermann da `proverbCandidates.json` a `proverbs.json`;
- tutti i record promossi restano `normalizationStatus: lab_ready` e `humanReviewRequired: true`;
- ogni record promosso conserva pagina Ostermann, pagina testo, path normalizzato e path clean verificato;
- aggiunto lo slot datato `03-19` per `ostermann-190-san-josef-biel`;
- `proverbs.json` passa da 40 a 48 record;
- i proverbi `homeEligible` passano da 31 a 39;
- gli slot datati passano da 5 a 6;
- il calendario quotidiano resta non pronto: mancano ancora 360 slot datati;
- il guardrail ora segnala anche record `lab_ready`, record con review umana richiesta e schedule che puntano a id inesistenti;
- nessuna modifica a UI, meteo, Eventi, GPS, notifiche o OSMER.

Seconda tranche candidati:

- estratte pagine Ostermann 49 e 54 dalle cartelle `normalized-pages` e `pages`;
- aggiunti 13 candidati a `proverbCandidates.json`;
- temi coperti: luna/pioggia, luna sabatina, luna di novembre, Epifania, Sant'Antonio, San Biagio, San Valentino, San Mattia, freddo e luce di febbraio;
- tutti i nuovi record restano `review.status: source_checked`, `homeEligible: false` e fuori dalla UI;
- aggiornato `ostermannProverbSources.json`: pagine 49, 54, 103, 105, 190 e 193 segnate `candidate_extracted`;
- `proverbCandidates.json` passa da 31 a 44 record;
- il guardrail ora espone `extractedCandidateSourcePages`;
- nessuna promozione in `proverbs.json` e nessuna modifica a UI, meteo, Eventi, GPS, notifiche o OSMER.

Backlog Scopri Ostermann:

- creato `frontend/src/data/discover/ostermannDiscoverBacklog.json`;
- creato `frontend/src/domain/discover/ostermannDiscoverBacklog.js` con test;
- preparati 28 record, uno per ogni pagina sorgente del piano Ostermann;
- ogni record ha uso primario `discover`, FUR `pending_review`, stato `backlog_extracted` e fonte pagina;
- i record non sono letti dalla UI e non sono copy finale;
- `ostermannProverbSources.json` ora distingue `candidate_extracted` da `discover_backlog_extracted`;
- le pagine con candidati proverbiali restano 6; le altre 22 sono pronte come backlog Scopri;
- decisione progettuale: Scopri sara' il contenitore principale di Ostermann, Almanacco usera' solo selezioni brevi e giornaliere.

## Tranche 39 - Catalogo ed estratti granulari Ostermann

File creati:

| File | Ruolo |
| --- | --- |
| `frontend/src/data/ostermann/sourceCatalog.json` | Catalogo operativo delle pagine Ostermann prioritarie, separato da dati UI e da proverbi pubblicabili. |
| `frontend/src/data/ostermann/extracts.json` | Estratti granulari con bozza IT, FUR `pending_review`, fonte e stato editoriale. |
| `frontend/src/domain/ostermann/ostermannArchive.js` | Guardrail dati per riepilogo e problemi del nuovo archivio. |
| `frontend/src/domain/ostermann/ostermannArchive.test.js` | Test per bloccare duplicati, riferimenti a pagine sconosciute e promozioni UI involontarie. |

Audit sorgente:

- indice normalizzato Ostermann letto da `reports/normalized-theme-index.json`;
- indice totale: 683 pagine;
- prima soglia utile: 21 pagine con `score >= 40` su temi meteo/proverbi/luna/calendario/agricoltura/vento/luoghi;
- catalogo ampliato a 27 pagine includendo pagine P1 gia previste dal piano sorgenti;
- estratti granulari creati: 26;
- pagine sorgente coperte dagli estratti: 24;
- record con uso primario `discover`: 26;
- possibili ponti Almanacco: 20;
- record `archive_context`: 3;
- record pronti UI: 0.

Decisioni:

- questo livello non sostituisce `ostermannDiscoverBacklog.json`: il backlog resta pagina/tema, gli estratti sono un livello piu fine;
- Scopri resta la destinazione primaria di Ostermann;
- Almanacco potra' usare solo micro-teaser o record selezionati dopo review;
- nessuna traduzione FUR e' stata approvata in automatico;
- le traduzioni IT sono `it_draft`, non copy finale;
- pagine con OCR/layout incerti sono marcate `needs_source_check`;
- contenuti folklorici delicati o superstiziosi sono marcati `archive_context`;
- nessun estratto viene importato da componenti, view o route.

Verifica tranche 39:

```text
npm run test -- ostermann
2 test file passati
6 test passati
```

## Tranche 40 - Source-check estratti granulari Ostermann

File aggiornati:

| File | Ruolo |
| --- | --- |
| `frontend/src/data/ostermann/extracts.json` | Aggiornati stati fonte per gli estratti gia marcati `needs_source_check`. |
| `frontend/src/domain/ostermann/ostermannArchive.js` | Aggiunti contatori per source-check clean, source-check inconclusivi e residui `needs_source_check`. |
| `frontend/src/domain/ostermann/ostermannArchive.test.js` | Aggiunti test sui nuovi contatori e sui record ancora bloccati. |

Pagine clean controllate:

- `pages/page-044.txt`;
- `pages/page-060.txt`;
- `pages/page-063.txt`;
- `pages/page-097.txt`;
- `pages/page-104.txt`;
- `pages/page-131.txt`.

Esito:

- `ost-extract-097-vento-date`: nucleo San Valentino verificabile; rimosse dipendenze da San Gregorio finche' non viene controllato su PDF.
- `ost-extract-060-santi-vendemmia`: nucleo San Bartolomeo/vendemmie verificabile; parte pagina resta frammentaria.
- `ost-extract-063-san-zuan-sant-egidi`: nucleo San Zuan/Sant'Egidio verificabile; parte bassa resta frammentaria.
- `ost-extract-104-monti-cappello-nubi`: nucleo monti col cappello/nubi/rane verificabile; parte bassa resta sporca.
- `ost-extract-131-santi-neve`: nucleo Santa Caterina/San Bastiano verificabile; riga Natale con data OCR discordante da non promuovere come slot.
- `ost-extract-044-luna-lavori-campi`: clean page testuale inconcludente, ma immagine `ocr-pages/page-044.png` e OCR alternativo `page-044-psm4.txt` confermano il nucleo dell'estratto.

Decisioni:

- sei record passano a `translated_it_draft`, ma restano `uiReadiness: not_ready`;
- nessun FUR e' stato approvato;
- nessun record e' stato promosso ad Almanacco/Scopri UI;
- pagina 44 e' stata verificata con asset locali gia presenti; Unlimited-OCR non e' stato usato ne installato.

Verifica tranche 40:

```text
npm run test -- ostermann
2 test file passati
7 test passati
```

## Tranche 41 - Seconda estrazione granulare Ostermann

File aggiornati:

| File | Ruolo |
| --- | --- |
| `frontend/src/data/ostermann/sourceCatalog.json` | Catalogate 20 nuove pagine Ostermann prioritarie per Scopri/Almanacco. |
| `frontend/src/data/ostermann/extracts.json` | Aggiunti 20 nuovi estratti granulari con bozza IT, FUR pending e fonte pagina. |
| `frontend/src/domain/ostermann/ostermannArchive.test.js` | Aggiornati i guardrail quantitativi del nuovo archivio. |

Pagine aggiunte:

- 40, 43, 57, 58, 59, 68, 87, 96, 119, 121, 122, 129, 141, 146, 189, 192, 234, 608, 609 e 674.

Filoni coperti:

- luna, lunari e lavori dei campi;
- durata delle giornate e calendario dei santi;
- Candelora, Venerdi Santo, Pasqua e Ascensione;
- fumo del Midili, Epifania e presagi dell'annata;
- Garbin, vento delle Palme e durata dei venti;
- campane, grandine, nubi temporalesche e fulmini come archivio storico;
- arcobaleno e aloni lunari;
- vigna, vendemmia, San Barnaba, Sant'Ermacora e bufere;
- erbe e nomi locali, con cautela per usi medico-popolari;
- giochi di neve, slitte e memoria invernale.

Esito:

- `sourceCatalog.json` passa da 27 a 47 pagine catalogate;
- `extracts.json` passa da 26 a 46 estratti;
- pagine sorgente coperte dagli estratti: 44;
- record con uso primario `discover`: 46;
- possibili ponti Almanacco: 32;
- record `archive_context`: 8;
- record pronti UI: 0;
- FUR approvato: 0;
- traduzioni IT definitive: 0.

Decisioni:

- pagina 122 non e' stata promossa come testo pulito: il normalizzato e' rumoroso, l'OCR alternativo locale e' solo controllo parziale;
- i blocchi su grandine, fulmini, riti e usi erboristici restano archivio culturale, non consigli pratici;
- Unlimited-OCR non e' stato usato;
- nessuna modifica a UI, meteo, Eventi, GPS, notifiche o OSMER.

Verifica tranche 41:

```text
npm run test -- ostermann
2 test file passati
7 test passati
```

## Tranche 42 - Recupero archivio curato Ostermann precedente

Fonti controllate:

- `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\docs\almanacco\ostermann-cultural-discover-final.json`;
- `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\docs\almanacco\ostermann-cultural-discover-final-summary.md`;
- `frontend/src/data/ostermannCulturalDiscover.json`.

Esito confronto:

- il nuovo progetto contiene gia' i 59 record curati del lavoro precedente;
- nessun ID del vecchio archivio risulta mancante nel nuovo progetto;
- il nuovo progetto conserva 58 record con FUR `approved` e 1 record `short_ready`;
- il vecchio JSON ispezionato ha la stessa struttura/ID, ma i campi FUR risultano meno avanzati rispetto al file gia presente nel nuovo progetto;
- quindi il recupero corretto e' censire e proteggere il lavoro gia importato, non riscriverlo.

File aggiornati:

| File | Ruolo |
| --- | --- |
| `frontend/src/data/ostermann/sourceCatalog.json` | Aggiunte le pagine curate non ancora catalogate e collegati record recuperati. |
| `frontend/src/domain/ostermann/ostermannArchive.js` | Aggiunto audit del corpus curato recuperato. |
| `frontend/src/domain/ostermann/ostermannArchive.test.js` | Aggiunti guardrail su 59 record curati, FUR e copertura catalogo. |

Pagine recuperate nel catalogo:

- aggiunte come `curated_recovered`: 28, 45, 46, 67, 69, 70, 98, 106, 111, 145, 227, 233, 299, 541, 545 e 604;
- pagine 190 e 193 gia presenti: collegate ai record curati recuperati senza cambiarne il ruolo di candidati.

Nuovi contatori guardrail:

- record curati recuperati: 59;
- pagine curate recuperate: 54;
- record FUR `approved`: 58;
- record FUR `short_ready`: 1;
- record curati con IT pronto: 58;
- pagine curate mancanti dal catalogo: 0;
- pagine curate ancora senza estratto granulare: 18.

Decisioni:

- `ostermannCulturalDiscover.json` resta fonte curata gia recuperata;
- `sourceCatalog.json` ora sa quali pagine arrivano dal lavoro precedente;
- `extracts.json` non viene riempito automaticamente con duplicati dei 59 record;
- le 18 pagine mancanti dal livello granulare restano una scelta progettuale successiva: trasformarle in estratti oppure mantenerle come record curati legacy;
- nessuna modifica a UI, meteo, Eventi, GPS, notifiche o OSMER.

Verifica tranche 42:

```text
npm run test -- ostermann
2 test file passati
7 test passati
```

## Tranche 43 - Estratti granulari da archivio curato recuperato

File aggiornati:

| File | Ruolo |
| --- | --- |
| `frontend/src/data/ostermann/extracts.json` | Aggiunti 18 estratti recuperati dal corpus curato precedente. |
| `frontend/src/data/ostermann/sourceCatalog.json` | Collegati gli `extractIds` alle 18 pagine recuperate. |
| `frontend/src/domain/ostermann/ostermannArchive.js` | Aggiunti contatori e problemi per link catalogo/estratti/record curati. |
| `frontend/src/domain/ostermann/ostermannArchive.test.js` | Aggiornati i guardrail quantitativi e relazionali. |

Pagine trasformate in estratti:

- 28, 45, 46, 67, 69, 70, 98, 106, 111, 145, 190, 193, 227, 233, 299, 541, 545 e 604.

Decisione dati:

- ogni nuovo estratto conserva `curatedRecordId`;
- il FUR approvato non viene duplicato in `extracts.json`;
- i campi FUR degli estratti recuperati puntano al record curato in `ostermannCulturalDiscover.json`;
- tutti i nuovi estratti restano `uiReadiness: not_ready`;
- i temi sensibili restano `archive_context`;
- il record `ost-0013-luna-uccelli-bucato` resta l'unico recupero con review FUR ancora richiesta, perche' la fonte e' `short_ready`.

Nuovi contatori:

- estratti totali: 64;
- pagine sorgente coperte dagli estratti: 62;
- record con uso primario `discover`: 64;
- possibili ponti Almanacco: 43;
- record `archive_context`: 15;
- estratti recuperati da record curati: 18;
- estratti recuperati con review FUR richiesta: 1;
- pagine curate mancanti dal livello granulare: 0;
- record pronti UI: 0.

Nuovi guardrail relazionali:

- `catalogExtractIdsMissing`: segnala se una pagina catalogata punta a un estratto inesistente;
- `recoveredExtractsMissingCuratedRecord`: segnala se un estratto recuperato punta a un record curato inesistente.

Verifica tranche 43:

```text
npm run test -- ostermann
2 test file passati
7 test passati
```

## Tranche 44 - Collegamenti estratti granulari e corpus Ostermann curato

File creati:

| File | Ruolo |
| --- | --- |
| `frontend/src/data/ostermann/curatedLinks.json` | Mappa editoriale tra estratti granulari e record gia curati in `ostermannCulturalDiscover.json`. |

File aggiornati:

| File | Ruolo |
| --- | --- |
| `frontend/src/domain/ostermann/ostermannArchive.js` | Aggiunti accesso, contatori e problemi per i collegamenti estratti-record curati. |
| `frontend/src/domain/ostermann/ostermannArchive.test.js` | Aggiunti guardrail su conteggi e integrita dei collegamenti. |

Esito:

- collegamenti creati: 38;
- estratti granulari collegati: 38;
- riferimenti a record curati: 43;
- estratti mancanti: 0;
- record curati mancanti: 0.

Decisione dati:

- `curatedLinks.json` non sostituisce `extracts.json` e non sostituisce `ostermannCulturalDiscover.json`;
- serve a dichiarare che alcuni estratti nuovi coprono temi gia presenti nel corpus curato precedente;
- il FUR approvato resta nel corpus curato e non viene duplicato negli estratti granulari;
- la futura pagina `Scopri` dovra usare questi collegamenti per evitare card doppie sullo stesso nucleo culturale;
- nessun collegamento e' letto dalla UI;
- nessuna modifica a meteo, Eventi, GPS, notifiche o OSMER.

Nuovi guardrail:

- `curatedLinkRecords`;
- `curatedLinkedExtracts`;
- `curatedLinkedRecordRefs`;
- `duplicateCuratedLinkExtractIds`;
- `curatedLinksMissingExtract`;
- `curatedLinksMissingCuratedRecord`.

Verifica tranche 44:

```text
npm run test -- ostermann
2 test file passati
7 test passati
```

## Tranche 45 - Dorsale dati Bollettino OSMER

File creati:

| File | Ruolo |
| --- | --- |
| `frontend/src/domain/alerts/officialAlerts.js` | Policy unica per riconoscere, filtrare e sintetizzare le allerte ufficiali. |
| `frontend/src/domain/alerts/officialAlerts.test.js` | Guardrail su allerte gialle/arancioni/rosse, stato verde e label compatte. |
| `frontend/src/features/bulletin/bulletinDataController.js` | Controller dati Bollettino: carica bootstrap e restituisce stati `fresh`, `stale`, `empty`, `error`. |
| `frontend/src/features/bulletin/bulletinDataController.test.js` | Verifica che il controller non interpreti forecast/allerta e richieda bootstrap adatto al Bollettino. |
| `frontend/src/features/bulletin/bulletinViewModel.js` | View model Bollettino: trasforma payload meteo in fonte, allerta, giorni, testo OSMER e overlay A1-A9. |
| `frontend/src/features/bulletin/bulletinViewModel.test.js` | Regressioni su fixture OSMER, mancanza A1-A9 e stato allerta. |

File aggiornati:

| File | Ruolo |
| --- | --- |
| `frontend/src/features/home/homeViewModel.js` | La Home usa la stessa policy ufficiale delle allerte, senza parser duplicato. |
| `frontend/src/features/home/homeViewModel.test.js` | Coperti payload backend `official_alerts` a oggetto e stato verde non azionabile. |
| `frontend/src/features/bulletin/BulletinView.jsx` | La vista legge un modello gia preparato e non decide fetch, cache o interpretazione dati. |
| `frontend/src/app/AppRoutes.jsx` | Collegamento laboratorio al data controller Bollettino, con localita temporanea `Udine`. |

Decisioni dati:

- `officialAlerts` resta il canale delle allerte ufficiali: verde/green/non attiva non genera banner, click o notifica.
- Home e Bollettino condividono la stessa policy, cosi `Allerta gialla`, `Allerta arancione`, `Allerta rossa` non divergono.
- Il dettaglio ufficiale dell'allerta appartiene al Bollettino; la Home mostra solo una label breve.
- `forecast.osmer_structured.days[*].areas9` e' la fonte primaria dei marker mappa.
- Se A1-A9 mancano, la mappa non inventa marker: la base resta visibile con stato dati non disponibile.
- Il testo ufficiale OSMER viene letto dal payload ufficiale e non sostituito da una traduzione.
- Il canale previsioni FUR resta previsto dal contratto, ma la mappatura/traduzione FUR e' rimandata a una passata dedicata.
- Le notifiche non vengono importate nel frontend: questa tranche prepara solo policy e dati, non invio push.
- La localita `Udine` in `AppRoutes.jsx` e' un aggancio laboratorio temporaneo, da sostituire con la sorgente posizione/localita reale.

Verifica tranche 45:

```text
npm run test -- officialAlerts homeViewModel bulletinViewModel bulletinDataController weatherApi
5 test file passati
35 test passati

npm run lint
passato

npm run build
passato
```

## Tranche 50 - Collaudo scenario pipeline dati

File creati:

| File | Ruolo |
| --- | --- |
| `frontend/src/domain/pipeline/bulletinPipelineScenario.test.js` | Simulatore test-only del ciclo dati completo: transizione allerte + transizione OSMER + proiezione contratto app minimo. |

File aggiornati:

| File | Ruolo |
| --- | --- |
| `OSMER_DATA_PIPELINE_AUDIT.md` | Documentato il collaudo scenario e l'audit infrastrutturale necessario prima del collegamento live. |

Decisioni dati:

- Il collaudo verifica il film degli stati, non solo singoli payload isolati.
- Home distingue banner fresco, banner trattenuto e assenza banner.
- Bollettino distingue notice allerta, mappa nativa e stato bollettino.
- Le azioni operative restano esplicite per audit/log futuri.
- Il collegamento reale richiede audit separato su Cloud Run, Firebase Hosting, GitHub Actions, Firestore/storage e notifiche push.

Verifica tranche 50:

```text
npm run test -- bulletinPipelineScenario
1 test file passato
2 test passati

npm run test
46 test file passati
296 test passati

npm run lint
passato

npm run build
passato
```

## Tranche 51 - Audit infrastruttura dati Bollettino e allerte

File creati:

| File | Ruolo |
| --- | --- |
| `INFRA_DATA_PIPELINE_AUDIT.md` | Audit read-only della filiera vecchia Cloud Run/Firebase/GitHub Actions/Firestore per Bollettino, allerte e notifiche. |

File letti dalla vecchia app:

| File | Ruolo |
| --- | --- |
| `firebase.json` | Hosting Firebase, rewrite `/api/**` verso Cloud Run e `pinTag`. |
| `backend/Dockerfile` | Packaging Cloud Run e moduli backend copiati. |
| `backend/main.py` | Lettura allerte, override Firestore, bootstrap, push ufficiali, OSMER strutturato. |
| `backend/osmer_audit_storage.py` | Storage audit OSMER file/Firestore. |
| `.github/workflows/sync-official-alerts.yml` | Sync esterno allerte e trigger push check. |
| `.github/workflows/send-local-weather-notices.yml` | Avvisi locali meteo manuali/dry-run. |
| `.github/workflows/send-manual-app-notice.yml` | Comunicazioni manuali separate dai test tecnici. |
| `scripts/sync-protezione-civile-alert-override.py` | Fetch pagina/widget FVG e fallback DPC nazionale. |
| Documenti operativi vecchi | Firebase/Cloud Run, GitHub fetcher, push readiness e note operative. |

Decisioni dati:

- Nessun collegamento live e nessuna modifica backend/UI.
- Il problema principale resta la distinzione tra osservazione, transizione, stato app e stato notifica.
- `active=false` non basta: puo significare quiete certificata, fonte non disponibile, diagnostica DPC o allerta scaduta.
- GitHub Actions resta candidato come lettore esterno, ma va trattato come best-effort e non timer realtime.
- Cloud Run non deve fare fetch bloccante Protezione Civile nel bootstrap normale.
- Firestore futuro deve separare osservazioni grezze, stato finale e audit transizioni.
- Le notifiche devono partire solo da un'azione finale del motore di transizione, non da `alerts.length`.

Verifica tranche 51:

```text
Modifica solo documentale.
Test applicativi non eseguiti.
```

## Tranche 52 - Raffinamento notifiche motore allerte

File aggiornati:

| File | Ruolo |
| --- | --- |
| `frontend/src/domain/alerts/officialAlertTransition.js` | Aggiunta firma stabile dell'allerta e azioni esplicite `NOTIFY_NEW_OFFICIAL_ALERT` / `SUPPRESS_DUPLICATE_NOTIFICATION`. |
| `frontend/src/domain/alerts/officialAlertTransition.test.js` | Coperti primo invio, conferma duplicata e allerta cambiata. |
| `OSMER_DATA_PIPELINE_AUDIT.md` | Documentato che `state=active` da solo non autorizza notifiche: serve l'azione di transizione. |

Decisioni dati:

- La notifica futura non nasce da `alerts.length` e nemmeno dal solo `state=active`.
- Una allerta attiva nuova o cambiata produce `NOTIFY_NEW_OFFICIAL_ALERT`.
- La stessa allerta ancora attiva mantiene banner/Home/Bollettino, ma produce `SUPPRESS_DUPLICATE_NOTIFICATION`.
- `stale_held_active` conserva gli alert precedenti per la UI, ma resta senza nuove notifiche.
- Nessun collegamento live, nessuna modifica a Firebase/Cloud Run/GitHub Actions, nessuna UI/CSS.

Verifica tranche 52:

```text
npm run test -- officialAlertTransition bulletinPipelineScenario
2 test file passati
8 test passati

npm run test -- officialAlerts officialAlertContract officialAlertTransition osmerBulletinTransition bulletinPipelineScenario
5 test file passati
28 test passati

npm run test
46 test file passati
299 test passati

npm run lint
passato

npm run build
passato
```

## Tranche 53 - Contratto backend stato dati

File creati:

| File | Ruolo |
| --- | --- |
| `BACKEND_DATA_STATE_CONTRACT.md` | Contratto architetturale per stati backend futuri di allerte ufficiali, Bollettino OSMER, transizioni, storage ed endpoint. |

File aggiornati:

| File | Ruolo |
| --- | --- |
| `README.md` | Registrati i documenti dati/infra nello stato implementativo UI 3.0.0. |

Decisioni dati:

- Il backend futuro deve esporre stati finali, non payload grezzi da interpretare in UI.
- La pipeline e' definita come `fonte esterna -> osservazione grezza -> transizione -> stato finale app -> azione/notifica`.
- `official_alert_state/current` e `osmer_bulletin_state/current` sono i contratti candidati per la UI.
- Osservazioni, stati finali e transizioni devono vivere in strutture separate.
- L'endpoint push deve leggere azioni di transizione, non dedurre invio da `active=true`.
- Nessun collegamento live, nessuna modifica backend, nessuna UI/CSS.

Verifica tranche 53:

```text
Modifica solo documentale/architetturale.
Test applicativi non eseguiti.
```

## Tranche 54 - Banco prova locale contratto backend

File creati:

| File | Ruolo |
| --- | --- |
| `frontend/src/domain/pipeline/backendDataStateContract.js` | Simulatore JS puro del contratto backend: trasforma osservazioni/stati precedenti in documenti `official_alert_*` e `osmer_bulletin_*`. |
| `frontend/src/domain/pipeline/backendDataStateContract.test.js` | Test del contratto backend-like su fixture allerta e OSMER. |

File aggiornati:

| File | Ruolo |
| --- | --- |
| `BACKEND_DATA_STATE_CONTRACT.md` | Documentato il banco prova locale e le regole gia verificate. |

Decisioni dati:

- Il banco prova non e' backend, non chiama servizi e non scrive storage.
- Le osservazioni grezze, gli stati finali e le transizioni vengono proiettati in documenti separati.
- `NOTIFY_NEW_OFFICIAL_ALERT` e `SUPPRESS_DUPLICATE_NOTIFICATION` sono azioni contrattuali verificabili.
- OSMER lookback e merge sanato producono stati espliciti con warning/provenienza.
- Nessun collegamento live, nessuna modifica backend, nessuna UI/CSS.

Verifica tranche 54:

```text
npm run test -- backendDataStateContract
1 test file passato
10 test passati

npm run test -- backendDataStateContract bulletinPipelineScenario officialAlertTransition osmerBulletinTransition
4 test file passati
20 test passati

npm run test
47 test file passati
309 test passati

npm run lint
passato

npm run build
passato
```

## Tranche 55 - Trasposizione dry-run nel backend sorgente

File creati nel backend sorgente:

| File | Ruolo |
| --- | --- |
| `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\backend\data_state_contract.py` | Modulo Python puro equivalente al banco prova JS: stati/azioni per allerte e OSMER, senza FastAPI/Firestore/FCM. |
| `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\backend\test_data_state_contract.py` | Test unittest dry-run del contratto dati backend. |

File aggiornati in UI 3.0.0:

| File | Ruolo |
| --- | --- |
| `BACKEND_DATA_STATE_CONTRACT.md` | Registrata la prima trasposizione backend dry-run e le verifiche. |

Decisioni dati:

- Il backend sorgente riceve solo moduli/test nuovi, nessuna modifica a `main.py`.
- Per "backend sorgente" si intende `meteo friul 13 - Nuova UI con Figma`, cioe' la base attuale da auditare/importare in modo controllato.
- Nessuna rotta pubblica, cache, Firestore, GitHub Actions o notifica viene collegata.
- La logica dry-run verifica: nuova allerta, duplicato, DPC diagnostico, expired senza rete, verde regionale, lookback OSMER e merge sanato.
- Il modulo Python e' volutamente isolato: potra essere collegato in seguito solo dopo ulteriori test.

Verifica tranche 55:

```text
python -m unittest test_data_state_contract
7 test passati

python -m unittest test_data_state_contract test_parser_osmer
13 test passati

python -m py_compile data_state_contract.py test_data_state_contract.py
passato
```

Nota test non collegato:

```text
python -m unittest test_data_state_contract test_parser_osmer test_local_weather_pushes
```

fallisce in `test_local_weather_pushes.test_heat_notice_uses_current_or_next_hours_temperature`: il test aspetta la vecchia copy "Oggi caldo a Pordenone", mentre il backend corrente produce "Caldo intenso nelle ore piÃ¹ calde.". Da trattare separatamente.

## Tranche 56 - Parita' documenti transition backend dry-run

File aggiornati nel backend sorgente:

| File | Ruolo |
| --- | --- |
| `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\backend\data_state_contract.py` | Aggiunte funzioni pure per documenti `official_alert_transition`, `osmer_bulletin_observation` e `osmer_bulletin_transition`. |
| `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\backend\test_data_state_contract.py` | Aggiunti test su transition allerta, observation OSMER e transition OSMER lookback. |

File aggiornati in UI 3.0.0:

| File | Ruolo |
| --- | --- |
| `BACKEND_DATA_STATE_CONTRACT.md` | Aggiornata la trasposizione backend dry-run con i documenti `observation -> state -> transition`. |
| `IMPORT_LOG.md` | Registrata questa tranche. |

Decisioni dati:

- Il backend sorgente ora ha parita' concettuale con il banco prova JS UI3 per i tre livelli del contratto.
- Le funzioni restano pure: nessun endpoint, nessuna chiamata HTTP, nessuna scrittura Firestore, nessun FCM.
- Il test allerta usa `now` esplicito per evitare che una fixture scaduta cambi comportamento in base alla data reale del PC.
- Il problema della copy caldo locale resta separato: copy desiderata futura "Oggi caldo a {localita}".

Verifica tranche 56:

```text
python -B -m py_compile data_state_contract.py test_data_state_contract.py
passato

python -B -m unittest test_data_state_contract
10 test passati

python -B -m unittest test_data_state_contract test_parser_osmer
16 test passati
```

## Tranche 57 - Fixture e casi dati backend dry-run

File aggiornati nel backend sorgente:

| File | Ruolo |
| --- | --- |
| `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\backend\data_state_contract.py` | Resi espliciti gli stati OSMER `partial` e `projected`, oltre a `ready`, `partial_healed`, `stale_from_cache` e `unavailable`. |
| `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\backend\test_data_state_contract.py` | Refactor dei test per leggere fixture/matrici e coprire allerte e OSMER come casi dichiarati. |
| `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\backend\fixtures\data_state\README.md` | Spiega scopo e limiti delle fixture dry-run. |
| `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\backend\fixtures\data_state\official_alert_cases.json` | Matrice casi allerta e risultati attesi. |
| `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\backend\fixtures\data_state\official_alerts\*.json` | Payload allerta rappresentativi: gialla, arancione, rossa, verde, stale, expired, DPC e unavailable. |
| `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\backend\fixtures\data_state\osmer_cases.json` | Matrice scenari OSMER: completo, A1-A9 incompleto, F1-F4 incompleto, lookback, healing, projected. |

File aggiornati in UI 3.0.0:

| File | Ruolo |
| --- | --- |
| `BACKEND_DATA_STATE_CONTRACT.md` | Aggiornata copertura fixture, stati OSMER dry-run e stato criteri di accettazione. |
| `IMPORT_LOG.md` | Registrata questa tranche. |

Decisioni dati:

- Le fixture allerta regionali arancione/rossa sono rappresentative per dry-run, non letture live.
- La fixture OSMER reale resta `PW20260606.normalized.json`; gli scenari incompleti sono derivazioni controllate in test.
- `A1-A9` incompleto produce `partial` e non abilita la mappa nativa.
- `F1-F4` incompleto produce `partial`, ma con `A1-A9` completi puo ancora abilitare la mappa nativa.
- `official_projected` resta usabile come fallback, ma non come mappa nativa XML.
- Nessun endpoint, Firestore, Cloud Run, GitHub Actions, FCM o UI e' stato collegato.

Verifica tranche 57:

```text
python -B -m py_compile data_state_contract.py test_data_state_contract.py
passato

python -B -m unittest test_data_state_contract
12 test passati

python -B -m unittest test_data_state_contract test_parser_osmer
18 test passati
```

## Tranche 58 - Endpoint dry-run protetti per data pipeline

File aggiornati nel backend sorgente:

| File | Ruolo |
| --- | --- |
| `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\backend\main.py` | Aggiunti endpoint protetti per dry-run `official-alerts` e `osmer`, con helper fixture/scenario read-only. |
| `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\backend\test_weather_engine.py` | Aggiunti test su protezione secret e risposta dry-run `observation -> state -> transition`. |

File aggiornati in UI 3.0.0:

| File | Ruolo |
| --- | --- |
| `BACKEND_DATA_STATE_CONTRACT.md` | Registrati endpoint effettivi, garanzie e stato criteri di accettazione. |
| `IMPORT_LOG.md` | Registrata questa tranche. |

Endpoint aggiunti:

```text
POST /api/weather/data-pipeline/dry-run/official-alerts
POST /api/weather/data-pipeline/dry-run/osmer
```

Decisioni dati:

- Le route usano `require_push_secret(request)`, come gli audit OSMER e le route push protette.
- La route allerta accetta payload diretto oppure fixture `fixtures/data_state/official_alerts/*.json`.
- La route OSMER accetta payload diretto oppure scenario dichiarato in `fixtures/data_state/osmer_cases.json`.
- Le route restituiscono solo `dry_run`, `kind`, `observation`, `state`, `transition`.
- Nessuna chiamata live, nessuna scrittura Firestore, nessun invio FCM, nessun collegamento UI.
- La lettura fixture e' limitata alla cartella `fixtures/data_state` con nome file sanificato.

Verifica tranche 58:

```text
python -B -m py_compile main.py test_weather_engine.py data_state_contract.py test_data_state_contract.py
passato

python -B -m unittest test_data_state_contract
12 test passati

python -B -m unittest test_weather_engine.DataPipelineDryRunEndpointTest
2 test passati

python -B -m unittest test_data_state_contract test_parser_osmer test_weather_engine.DataPipelineDryRunEndpointTest
20 test passati
```

Smoke HTTP locale:

```text
POST /api/weather/data-pipeline/dry-run/official-alerts
fixture active-yellow-regional.json
state=active
source_authority=regional_fvg
transition_actions=NOTIFY_NEW_OFFICIAL_ALERT

POST /api/weather/data-pipeline/dry-run/osmer
scenario missing_area
state=partial
requested_date=2026-06-25
valid_dates=2026-06-25
warnings=osmer_partial_snapshot
```

Micro-correzione emersa dal collaudo:

- gli scenari OSMER derivati dalla fixture base ora impostano anche `requested_date` sulla data scenario, non solo `days[0].valid_date`;
- aggiunto test sul campo `requested_date` per evitare regressioni.

## Tranche 59 - Audit sorgenti reali allerte verso contratto

File creati in UI 3.0.0:

| File | Ruolo |
| --- | --- |
| `REAL_SOURCE_TO_CONTRACT_AUDIT.md` | Matrice read-only del percorso reale allerte dal backend sorgente al contratto `observation -> state -> transition`. |

File aggiornati in UI 3.0.0:

| File | Ruolo |
| --- | --- |
| `BACKEND_DATA_STATE_CONTRACT.md` | Collegato l'audit reale e registrato il gap `manual_verified` / `manual_official_override`. |
| `IMPORT_LOG.md` | Registrata questa tranche. |

Percorsi auditati nel backend sorgente:

| File | Elementi letti |
| --- | --- |
| `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\backend\main.py` | Parser pagina/widget FVG, override, stale inactive, unavailable fallback, fetch read path, push ufficiali. |
| `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\scripts\sync-protezione-civile-alert-override.py` | Sync GitHub pagina/widget, fallback DPC attivo storico, DPC no-active diagnostico, protezione da sovrascrittura di fonte regionale. Da Tranche 73 DPC resta solo diagnostica. |
| `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\backend\test_weather_engine.py` | Test esistenti su widget verde, direct fetch disabilitato, DPC fallback, stale source metadata. |
| `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\backend\test_data_state_contract.py` | Matrice fixture dry-run del contratto backend. |

Decisioni dati:

- `alerts=[]` non basta per dire "nessuna allerta".
- Solo `inactive_confirmed` da fonte regionale fresca puo spegnere una vecchia allerta.
- Nota aggiornata in Tranche 73: DPC active non accende piu una decisione app; resta diagnostica interna come DPC no-active.
- `stale_no_alert_override` e cache stale non possono diventare verde confermato.
- Il push corrente nel backend sorgente non usa ancora `transition_actions`; questo resta un gap prima del live.
- L'override manuale reale usa `manual_official_override`, mentre il contratto parlava di `manual_verified`: va normalizzato prima del collegamento.

Verifica tranche 59:

```text
solo documentazione/audit
nessun test necessario
nessuna modifica a endpoint, parser, Firestore, FCM o UI
```

## Tranche 60 - Fixture manual/stale per contratto allerte backend

File aggiornati nel backend sorgente:

| File | Ruolo |
| --- | --- |
| `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\backend\data_state_contract.py` | `manual_official_override` viene classificato come autorita semantica `manual_verified`; puo produrre `active` o `inactive_confirmed` nel dry-run. |
| `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\backend\fixtures\data_state\official_alert_cases.json` | Aggiunti casi manual active, manual inactive e stale no-alert override. |
| `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\backend\fixtures\data_state\README.md` | Documentata la nuova copertura fixture. |
| `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\backend\fixtures\data_state\official_alerts\manual-official-override-active.json` | Override manuale verificato attivo. |
| `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\backend\fixtures\data_state\official_alerts\manual-official-override-inactive.json` | Override manuale verificato inattivo. |
| `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\backend\fixtures\data_state\official_alerts\stale-no-alert-override.json` | Override no-active stale che non puo spegnere una vecchia allerta. |

File aggiornati in UI 3.0.0:

| File | Ruolo |
| --- | --- |
| `REAL_SOURCE_TO_CONTRACT_AUDIT.md` | Aggiornata la matrice reale: `manual_official_override` resta source mode reale, `manual_verified` diventa autorita semantica. |
| `BACKEND_DATA_STATE_CONTRACT.md` | Registrata la nuova copertura fixture e lo stato dell'allineamento manuale. |
| `IMPORT_LOG.md` | Registrata questa tranche. |

Decisioni dati:

- L'override manuale verificato non viene finto come fonte regionale automatica.
- `manual_official_override` resta il nome reale del payload backend.
- `source_authority=manual_verified` distingue la decisione protetta/auditata da pagina/widget FVG.
- Manual active puo notificare in dry-run.
- Manual inactive puo spegnere in dry-run.
- `stale_no_alert_override` resta `stale`, quindi non spegne mai una vecchia allerta.

Verifica tranche 60:

```text
python -B -m unittest test_data_state_contract
12 test passati

python -B -m unittest test_data_state_contract test_parser_osmer test_weather_engine.DataPipelineDryRunEndpointTest
20 test passati

python -B -c "compile(open('data_state_contract.py', encoding='utf-8').read(), 'data_state_contract.py', 'exec'); compile(open('test_data_state_contract.py', encoding='utf-8').read(), 'test_data_state_contract.py', 'exec'); print('compile in-memory OK')"
compile in-memory OK
```

Smoke diretto sui casi critici:

```text
manual-official-override-inactive.json inactive_confirmed manual_verified True ['CLEAR_ALL_ALERTS_AND_BANNERS', 'RESET_STATE_ENGINE']
stale-no-alert-override.json stale unknown False ['DISABLE_NEW_NOTIFICATIONS']
```

Nota:

- `python -B -m py_compile data_state_contract.py test_data_state_contract.py` non e' stato usato come verifica finale perche' prova comunque a scrivere in `__pycache__` e il sandbox lo ha bloccato con `Permission denied`.

## Tranche 61 - Harness locale payload allerta -> effetto utente

File creati in UI 3.0.0:

| File | Ruolo |
| --- | --- |
| `backend_dryrun_staging/official_alert_payload_dryrun.py` | Comando locale read-only: prende un payload allerta salvato e produce `observation`, `state`, `transition` e `user_effect`. |
| `backend_dryrun_staging/README.md` | Uso del comando e lettura rapida di `user_effect`. |

File aggiornati in UI 3.0.0:

| File | Ruolo |
| --- | --- |
| `REAL_SOURCE_TO_CONTRACT_AUDIT.md` | Il prossimo passo ora punta al nuovo harness locale per payload reali salvati. |
| `BACKEND_DATA_STATE_CONTRACT.md` | Registrato il nuovo harness read-only. |
| `IMPORT_LOG.md` | Registrata questa tranche. |

Decisioni dati:

- Il comando accetta solo payload allerta completi, non il semplice riassunto `--dry-run` dello script sync.
- Il comando non importa `backend/main.py`, quindi non puo chiamare FastAPI, fetcher, Firestore o FCM.
- `user_effect` traduce lo stato tecnico in effetto utente: Home, Bollettino, notifica ammessa, pulizia vecchia allerta.
- Una notifica `can_notify=true` resta solo ammessa in laboratorio, non inviata.

Verifica tranche 61:

```text
python -B backend_dryrun_staging\official_alert_payload_dryrun.py "...manual-official-override-inactive.json"
user_effect.home.show_alert=false
user_effect.notification.can_notify=false
user_effect.clears_previous_alert=true

python -B backend_dryrun_staging\official_alert_payload_dryrun.py "...stale-no-alert-override.json"
user_effect.home.show_alert=false
user_effect.bulletin.notice="Nota tecnica: dati allerta non aggiornati"
user_effect.notification.can_notify=false
user_effect.clears_previous_alert=false

python -B backend_dryrun_staging\official_alert_payload_dryrun.py "...active-yellow-regional.json" --now 2026-06-24T13:00:00+02:00
user_effect.home.show_alert=true
user_effect.home.label="Allerta gialla"
user_effect.notification.can_notify=true

python -B -c "compile(open('backend_dryrun_staging/official_alert_payload_dryrun.py', encoding='utf-8').read(), 'backend_dryrun_staging/official_alert_payload_dryrun.py', 'exec'); print('compile in-memory OK')"
compile in-memory OK
```

## Tranche 62 - Export payload contratto dallo script sync allerte

File aggiornati nel backend sorgente:

| File | Ruolo |
| --- | --- |
| `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\scripts\sync-protezione-civile-alert-override.py` | Aggiunta opzione `--export-payload`, ammessa solo con `--dry-run`, per scrivere un payload completo compatibile col contratto. |
| `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\backend\test_weather_engine.py` | Aggiunti test helper per export payload attivo e scrittura file. |

File creati/aggiornati in UI 3.0.0:

| File | Ruolo |
| --- | --- |
| `backend_dryrun_staging/samples/widget-yellow-alert.jsonp` | Sample widget locale per testare parser -> export -> user_effect senza rete. |
| `backend_dryrun_staging/README.md` | Documentato export dallo script sync e catena di valutazione. |
| `REAL_SOURCE_TO_CONTRACT_AUDIT.md` | Aggiornato il prossimo passo: usare `--dry-run --export-payload`. |
| `BACKEND_DATA_STATE_CONTRACT.md` | Registrata modalita export sicura. |
| `IMPORT_LOG.md` | Registrata questa tranche. |

Decisioni dati:

- L'export non scrive il payload override "ridotto", ma una forma completa compatibile con il contratto (`alerts[]`, `source_mode`, `cache`, `fetched_at`, `expires_at`).
- `--export-payload` senza `--dry-run` viene rifiutato prima di ogni post al backend.
- Il flusso GitHub/live resta invariato finche l'opzione non viene usata.
- Il file esportato e' un artefatto temporaneo di laboratorio, non runtime app.

Verifica tranche 62:

```text
python -B -m unittest test_weather_engine.OfficialAlertPushHardeningTest
14 test passati

python -B -m unittest test_data_state_contract test_parser_osmer test_weather_engine.DataPipelineDryRunEndpointTest test_weather_engine.OfficialAlertPushHardeningTest
34 test passati

python -B scripts\sync-protezione-civile-alert-override.py --dry-run --sample-file "...widget-yellow-alert.jsonp" --sample-parser widget --export-payload "...widget-yellow-alert.contract.json"
dry_run=true
alerts_found=1
source_mode=github_actions_official_widget
export_payload=...widget-yellow-alert.contract.json

python -B backend_dryrun_staging\official_alert_payload_dryrun.py "...widget-yellow-alert.contract.json" --now 2026-06-24T13:00:00+02:00
user_effect.home.show_alert=true
user_effect.home.label="Allerta gialla"
user_effect.notification.can_notify=true

python -B scripts\sync-protezione-civile-alert-override.py --sample-file "...widget-yellow-alert.jsonp" --sample-parser widget --export-payload "...should-not-write.json"
exit=1
error="--export-payload richiede --dry-run per evitare scritture live ambigue"
should-not-write.json non creato
```

## Tranche 63 - Caso nessuna allerta confermata in harness dry-run

File creati in UI 3.0.0:

| File | Ruolo |
| --- | --- |
| `backend_dryrun_staging/samples/widget-no-alerts.jsonp` | Sample widget regionale con `alerts=[]` per simulare fonte letta e nessuna allerta attiva. |

File aggiornati in UI 3.0.0:

| File | Ruolo |
| --- | --- |
| `backend_dryrun_staging/README.md` | Documentato il caso no-alert confermato e l'effetto utente atteso. |
| `IMPORT_LOG.md` | Registrata questa tranche. |

Decisioni dati:

- Il caso no-alert confermato deve arrivare da fonte regionale fresca (`github_actions_official_widget` o equivalente regionale).
- `alerts=[]` con fonte regionale letta diventa `inactive_confirmed`.
- L'utente non vede banner Home, non vede nota Bollettino e non riceve notifica.
- Il sistema puo spegnere una vecchia allerta: `clears_previous_alert=true`.
- Questo resta diverso da `stale`, `diagnostic`, `expired` e `unavailable`.

Verifica tranche 63:

```text
python -B scripts\sync-protezione-civile-alert-override.py --dry-run --sample-file "...widget-no-alerts.jsonp" --sample-parser widget --export-payload "...widget-no-alerts.contract.json"
dry_run=true
alerts_found=0
action=record_no_active_alerts
source_mode=github_actions_official_widget

python -B backend_dryrun_staging\official_alert_payload_dryrun.py "...widget-no-alerts.contract.json" --now 2026-06-25T10:00:00+02:00
state=inactive_confirmed
user_effect.home.show_alert=false
user_effect.bulletin.show_notice=false
user_effect.notification.can_notify=false
user_effect.clears_previous_alert=true
```

## Tranche 64 - Film transizioni allerta precedente attiva

File creati in UI 3.0.0:

| File | Ruolo |
| --- | --- |
| `backend_dryrun_staging/samples/previous-active-yellow-state.json` | Stato precedente rappresentativo: allerta gialla attiva gia vista. |
| `backend_dryrun_staging/official_alert_transition_film.py` | Harness locale che verifica il film degli stati da precedente gialla attiva a casi successivi. |

File aggiornati in UI 3.0.0:

| File | Ruolo |
| --- | --- |
| `backend_dryrun_staging/README.md` | Documentata la matrice del film stati. |
| `REAL_SOURCE_TO_CONTRACT_AUDIT.md` | Collegato il film dry-run al percorso sorgenti reali -> contratto. |
| `BACKEND_DATA_STATE_CONTRACT.md` | Registrata la verifica del film transizioni. |
| `IMPORT_LOG.md` | Registrata questa tranche. |

Decisioni dati:

- Una stessa allerta gia attiva resta visibile ma non rinotifica.
- Una fonte regionale fresca che dice no-alert diventa `inactive_confirmed` e spegne la vecchia allerta.
- Uno stale no-alert non spegne.
- Un DPC no-active diagnostico trattiene la precedente allerta in stato `stale_held_active` e non notifica.
- Un fallback unavailable non spegne, non notifica e mostra solo nota prudenziale nel Bollettino.

Verifica tranche 64:

```text
python -B backend_dryrun_staging\official_alert_transition_film.py
ok=true

same_active_yellow -> active, SUPPRESS_DUPLICATE_NOTIFICATION, home_show_alert=true, can_notify=false, clears_previous_alert=false
confirmed_no_alert -> inactive_confirmed, CLEAR_ALL_ALERTS_AND_BANNERS, home_show_alert=false, can_notify=false, clears_previous_alert=true
stale_no_alert -> stale, DISABLE_NEW_NOTIFICATIONS, home_show_alert=false, can_notify=false, clears_previous_alert=false
dpc_no_active_diagnostic -> stale_held_active, KEEP_BULLETIN_NOTICE, home_show_alert=true, can_notify=false, clears_previous_alert=false
unavailable -> unavailable, DISABLE_NEW_NOTIFICATIONS, home_show_alert=false, can_notify=false, clears_previous_alert=false

python -B -c "compile(open('backend_dryrun_staging/official_alert_transition_film.py', encoding='utf-8').read(), 'backend_dryrun_staging/official_alert_transition_film.py', 'exec'); print('compile in-memory OK')"
compile in-memory OK
```

## Tranche 65 - Primo dry-run reale fonte allerte FVG

File generati in UI 3.0.0:

| File | Ruolo |
| --- | --- |
| `backend_dryrun_staging/exports/live-official-alerts.contract.json` | Payload reale esportato dallo script sync in modalita `--dry-run --export-payload`. |

Comando eseguito sul backend sorgente:

```text
python -B scripts\sync-protezione-civile-alert-override.py --dry-run --export-payload "F:\proggetto Meteo Friul App\meteo friul - ui 3.0.0\backend_dryrun_staging\exports\live-official-alerts.contract.json"
```

Nota ambiente:

- primo tentativo bloccato dal sandbox rete Windows con `WinError 10013`;
- secondo tentativo autorizzato con accesso rete per lo script dry-run;
- nessun post al backend;
- nessuna scrittura Firestore;
- nessuna notifica.

Risultato sync reale:

```text
dry_run=true
ok=true
alerts_found=0
parser=page
action=record_no_active_alerts
level=verde
source_mode=github_actions_official_page
source_url=https://www.protezionecivile.fvg.it/it/allerte
```

Valutazione contratto senza stato precedente:

```text
state=inactive_confirmed
source_authority=regional_fvg
can_show_home_banner=false
can_show_bulletin_notice=false
can_notify=false
can_clear_previous_alert=true
transition_actions=CLEAR_ALL_ALERTS_AND_BANNERS, RESET_STATE_ENGINE
```

Valutazione contratto con precedente gialla attiva:

```text
from_state=active
to_state=inactive_confirmed
alert_signature_before=precedente gialla
alert_signature_after=
user_effect.home.show_alert=false
user_effect.bulletin.show_notice=false
user_effect.notification.can_notify=false
user_effect.clears_previous_alert=true
```

Decisione dati:

- la fonte reale pagina FVG e' stata letta con successo;
- al momento della prova non risultano allerte attive;
- il contratto interpreta il payload come `inactive_confirmed`, quindi e' un no-alert confermato;
- se ci fosse una vecchia allerta, il sistema sarebbe autorizzato a pulirla;
- resta tutto in laboratorio, non collegato alla UI o alle notifiche.

## Tranche 49 - Motori di transizione dati

File creati:

| File | Ruolo |
| --- | --- |
| `frontend/src/domain/alerts/officialAlertTransition.js` | Motore puro `previousState + observation + context -> finalState + actions` per allerte ufficiali. |
| `frontend/src/domain/alerts/officialAlertTransition.test.js` | Test su flapping DPC, expired senza rete e spegnimento regionale certificato. |
| `frontend/src/domain/weather/osmerBulletinTransition.js` | Motore puro per lookback OSMER e merge sanato da snapshot precedente. |
| `frontend/src/domain/weather/osmerBulletinTransition.test.js` | Test su lookback a mezzanotte e recupero A9 da snapshot precedente. |

File aggiornati:

| File | Ruolo |
| --- | --- |
| `OSMER_DATA_PIPELINE_AUDIT.md` | Documentati motori di transizione, stati e azioni operative. |

Decisioni dati:

- Il DPC nazionale puo aiutare ad accendere una criticita, ma non spegne una recente allerta regionale.
- `stale_held_active` non e' allerta fresca: niente nuove notifiche, niente verde certificato, ma memoria dell'allerta precedente preservata.
- Un'allerta scaduta senza fonte regionale fresca diventa `expired`, non `inactive_confirmed`.
- Una quiete e' certificata solo da fonte regionale FVG letta con successo.
- Il lookback OSMER a 36 ore puo usare uno snapshot precedente se contiene la `valid_date` richiesta.
- Il merge sanato OSMER conserva tracce esplicite di `source_mix` e aree recuperate.
- Nessuna chiamata live nuova, nessuna UI/CSS, nessun DB.

Verifica tranche 49:

```text
npm run test -- officialAlertTransition osmerBulletinTransition
2 test file passati
5 test passati

npm run test
45 test file passati
294 test passati

npm run lint
passato

npm run build
passato
```

## Tranche 48 - Contratto OSMER strutturato

File creati:

| File | Ruolo |
| --- | --- |
| `frontend/src/domain/weather/osmerStructuredContract.js` | Classifica snapshot/giorni OSMER in `ready`, `partial`, `stale`, `unavailable` e distingue XML nativo da `official_projected`. |
| `frontend/src/domain/weather/osmerStructuredContract.test.js` | Matrice su fixture reale e varianti minime: completo, A1-A9 incompleto, F1-F4 incompleto, stale, unavailable, projected. |

File aggiornati:

| File | Ruolo |
| --- | --- |
| `frontend/src/features/bulletin/bulletinViewModel.js` | La mappa del Bollettino e' considerata strutturata solo se il contratto dice `canRenderNativeMap=true`. |
| `frontend/src/features/bulletin/bulletinViewModel.test.js` | Aggiunte regressioni su OSMER stale e `official_projected`. |
| `OSMER_DATA_PIPELINE_AUDIT.md` | Documentato il contratto OSMER strutturato. |

Decisioni dati:

- A1-A9 complete sono il requisito per rappresentare una mappa.
- F1-F4 mancanti rendono il bollettino parziale, anche se la geometria A1-A9 resta rappresentabile.
- `official_projected` puo essere utile come proiezione, ma non e' XML OSMER nativo.
- Snapshot stale/source unavailable non vengono usati come mappa nativa corrente.
- Nessuna chiamata live nuova e nessuna modifica CSS/UI.

Verifica tranche 48:

```text
npm run test -- osmerStructuredContract osmerAdapter bulletinViewModel
3 test file passati
24 test passati

npm run test
43 test file passati
289 test passati

npm run lint
passato

npm run build
passato
```

Verifica browser locale:

- backend locale raggiunto su `http://127.0.0.1:8001/api/weather/bootstrap?city=Udine`;
- payload confermato con `forecast.osmer_structured.days` e 9 aree A1-A9 nel primo giorno;
- pagina `?tab=bulletin` renderizzata con 9 marker mappa;
- nessun banner allerta mostrato quando `official_alerts.active=false`.

## Tranche 46 - Stati semantici allerte ufficiali

File aggiornati:

| File | Ruolo |
| --- | --- |
| `OSMER_DATA_PIPELINE_AUDIT.md` | Aggiunta sezione sui test di comportamento per stati allerta. |
| `frontend/src/domain/alerts/officialAlerts.js` | Aggiunta classificazione pura `classifyOfficialAlertState` per distinguere allerta attiva, inattiva confermata, non disponibile, stale, scaduta e diagnostica. |
| `frontend/src/domain/alerts/officialAlerts.test.js` | Aggiunti test sui casi critici del contratto allerta. |
| `frontend/src/features/home/homeViewModel.js` | La Home passa alla policy il payload `officialAlerts` intero, senza perdere `source_mode/cache/error`. |
| `frontend/src/features/home/homeViewModel.test.js` | Coperti `unavailable` e `stale` in Home. |
| `frontend/src/features/bulletin/bulletinViewModel.test.js` | Coperti `unavailable` e `stale` in Bollettino. |

Decisioni dati:

- `active=false` non viene trattato come "nessuna allerta" se la fonte non e' stata letta.
- `inactive_confirmed` e' l'unico stato che puo spegnere una vecchia allerta.
- `unavailable`, `stale`, `expired` e `diagnostic` non generano banner Home/Bollettino e non autorizzano notifiche future.
- La classificazione avviene sul payload ufficiale completo, non sull'array `alerts` gia filtrato.
- Nessun collegamento live nuovo e nessuna modifica UI/CSS.

Verifica tranche 46:

```text
npm run test -- officialAlerts homeViewModel bulletinViewModel
3 test file passati
35 test passati

npm run test
41 test file passati
274 test passati

npm run lint
passato

npm run build
passato
```

## Tranche 47 - Fixture contratto allerte ufficiali

File creati:

| File | Ruolo |
| --- | --- |
| `frontend/src/tests/fixtures/officialAlerts/active-yellow-regional.json` | Fonte regionale FVG con allerta gialla attiva. |
| `frontend/src/tests/fixtures/officialAlerts/inactive-confirmed-regional.json` | Fonte regionale FVG letta e nessuna allerta/verde. |
| `frontend/src/tests/fixtures/officialAlerts/unavailable-fast-fallback.json` | Backend fallback quando la fonte non e' stata letta. |
| `frontend/src/tests/fixtures/officialAlerts/stale-regional-cache.json` | Cache regionale vecchia con allerta non piu affidabile. |
| `frontend/src/tests/fixtures/officialAlerts/expired-regional-alert.json` | Allerta regionale scaduta. |
| `frontend/src/tests/fixtures/officialAlerts/diagnostic-dpc-no-active-fvg.json` | Fallback DPC senza criticita FVG, non verde regionale verificato. |
| `frontend/src/tests/fixtures/officialAlerts/active-orange-dpc-fallback.json` | Fallback DPC con criticita FVG attiva. |
| `frontend/src/domain/alerts/officialAlertContract.test.js` | Matrice fixture -> stato semantico atteso. |

File aggiornati:

| File | Ruolo |
| --- | --- |
| `OSMER_DATA_PIPELINE_AUDIT.md` | Documentata la matrice fixture/test. |

Decisioni dati:

- Le fixture sono payload sintetici rappresentativi, non collegamenti live.
- Il contratto verifica `state`, `sourceAuthority`, `confidence`, `canShowBanner`, `canClearPreviousAlert`, `canNotify` e label UI quando ammessa.
- Nota aggiornata in Tranche 73: il caso DPC attivo va trattato come diagnostica non decisionale, non come stato finale `active` della UI.
- Il caso DPC senza criticita resta `diagnostic`, non spegne una vecchia allerta.

Verifica tranche 47:

```text
npm run test -- officialAlertContract officialAlerts
2 test file passati
18 test passati

npm run test
42 test file passati
281 test passati

npm run lint
passato

npm run build
passato
```

## Tranche 66 - Comando unico dry-run allerte ufficiali

File creati:

| File | Ruolo |
| --- | --- |
| `backend_dryrun_staging/official_alert_live_report.py` | Comando di laboratorio: fonte allerta -> export payload -> contratto dati -> effetto utente. |

File aggiornati:

| File | Ruolo |
| --- | --- |
| `backend_dryrun_staging/README.md` | Documentato il comando unico e il significato pratico del risultato. |
| `BACKEND_DATA_STATE_CONTRACT.md` | Registrato il comando unico nella sezione dry-run. |
| `REAL_SOURCE_TO_CONTRACT_AUDIT.md` | Aggiornato il prossimo passo e registrato il primo esito live. |

Decisioni:

- Il comando resta laboratorio: solo `--dry-run`, nessun post backend, nessuna scrittura Firestore, nessuna notifica.
- L'output `reading` traduce il contratto in effetto utente: Home, Bollettino, notifiche e spegnimento vecchia allerta.
- La lettura live del 2026-06-26 dalla pagina Protezione Civile FVG ha trovato zero allerte attive e ha prodotto `inactive_confirmed`.

Verifiche:

```text
python -B -c "compile(open('backend_dryrun_staging/official_alert_live_report.py', encoding='utf-8').read(), 'backend_dryrun_staging/official_alert_live_report.py', 'exec'); print('compile OK')"
compile OK

python -B backend_dryrun_staging\official_alert_transition_film.py
ok=true

python -B backend_dryrun_staging\official_alert_live_report.py --sample-file backend_dryrun_staging\samples\widget-no-alerts.jsonp --sample-parser widget --export-payload backend_dryrun_staging\exports\widget-no-alerts.live-report.contract.json --assume-previous-yellow --now 2026-06-26T10:00:00+02:00
state=inactive_confirmed
home=nessuna allerta in Home
bollettino=nessun avviso allerta nel Bollettino
notifiche=non inviata: fonte verificata senza allerta
stato_precedente=spegne una vecchia allerta

python -B backend_dryrun_staging\official_alert_live_report.py --export-payload backend_dryrun_staging\exports\live-official-alerts.contract.json --assume-previous-yellow
parser=page
alerts_found=0
state=inactive_confirmed
```

## Tranche 67 - Tabella leggibile casi allerta

File creati:

| File | Ruolo |
| --- | --- |
| `backend_dryrun_staging/official_alert_case_table.py` | Legge la matrice fixture allerta e produce una tabella scenario -> effetto utente. |

File aggiornati:

| File | Ruolo |
| --- | --- |
| `backend_dryrun_staging/README.md` | Documentata la tabella casi e la differenza tra controllo base e lettura con stato precedente. |
| `REAL_SOURCE_TO_CONTRACT_AUDIT.md` | Aggiunto il banco prova tabellare al percorso prima del live. |

Decisioni:

- Senza stato precedente, la tabella confronta i 12 casi con gli attesi di `official_alert_cases.json`.
- Con `--assume-previous-yellow`, la tabella non usa gli attesi base: mostra una lettura di transizione, perche' alcuni risultati cambiano correttamente.
- Questo evita di confondere un cambio corretto di comportamento con un errore del motore.

Verifiche:

```text
python -B -c "compile(open('backend_dryrun_staging/official_alert_case_table.py', encoding='utf-8').read(), 'backend_dryrun_staging/official_alert_case_table.py', 'exec'); print('compile OK')"
compile OK

python -B backend_dryrun_staging\official_alert_case_table.py --format markdown
12 casi su 12 ok

python -B backend_dryrun_staging\official_alert_case_table.py --assume-previous-yellow --format markdown
lettura transizioni con vecchia gialla completata
```

## Tranche 68 - Audit locale fonte allerte

File creati:

| File | Ruolo |
| --- | --- |
| `backend_dryrun_staging/official_alert_source_audit.py` | Legge fonte/campione, salva raw hash/snapshot, payload contratto, stato e lettura utente in JSONL. |
| `backend_dryrun_staging/audit_log/README.md` | Spiega cosa contengono audit log, raw snapshot e payload. |

File aggiornati:

| File | Ruolo |
| --- | --- |
| `backend_dryrun_staging/README.md` | Documentato il comando audit fonte. |
| `REAL_SOURCE_TO_CONTRACT_AUDIT.md` | Messo l'audit fonte come primo passo prima del live. |

File generati da audit:

| File | Ruolo |
| --- | --- |
| `backend_dryrun_staging/audit_log/official-alerts.audit.jsonl` | Registro append-only delle letture. |
| `backend_dryrun_staging/audit_log/raw/*.html|*.jsonp` | Snapshot grezzo delle fonti lette. |
| `backend_dryrun_staging/audit_log/payloads/*.contract.json` | Payload normalizzati passati al contratto. |

Decisioni:

- Zero alert non basta: il registro conserva anche raw hash e snapshot.
- Un no-alert regionale confermato puo spegnere una vecchia allerta solo se il contratto produce `inactive_confirmed`.
- Stale, unavailable, diagnostic o parse error non devono spegnere vecchie allerte.

Verifiche:

```text
python -B -c "compile(open('backend_dryrun_staging/official_alert_source_audit.py', encoding='utf-8').read(), 'backend_dryrun_staging/official_alert_source_audit.py', 'exec'); print('compile OK')"
compile OK

python -B backend_dryrun_staging\official_alert_source_audit.py --sample-file backend_dryrun_staging\samples\widget-no-alerts.jsonp --sample-parser widget --assume-previous-yellow --now 2026-06-26T10:00:00+02:00
state=inactive_confirmed
raw_sha256=f368c8d90bd551de75e78cded314242791d0f6fb340f78cbec01607c20f669fb

python -B backend_dryrun_staging\official_alert_source_audit.py --assume-previous-yellow
parser=page
alerts_found=0
state=inactive_confirmed
raw_sha256=9896e9c639d325d0fe913fdbc2566bc01f1f737760ccf986b16ad23b329b689c
```

## Tranche 69 - Audit locale fonte OSMER

File creati:

| File | Ruolo |
| --- | --- |
| `backend_dryrun_staging/osmer_source_audit.py` | Legge XML OSMER reali o fixture, salva raw hash/snapshot, snapshot strutturato e stato contratto. |
| `backend_dryrun_staging/audit_log/osmer/README.md` | Spiega registro, raw XML e snapshot strutturati OSMER. |

File aggiornati:

| File | Ruolo |
| --- | --- |
| `backend_dryrun_staging/README.md` | Documentato il comando audit OSMER. |
| `BACKEND_DATA_STATE_CONTRACT.md` | Registrato l'audit OSMER locale e il primo esito reale. |

File generati da audit:

| File | Ruolo |
| --- | --- |
| `backend_dryrun_staging/audit_log/osmer/osmer-bulletin.audit.jsonl` | Registro append-only delle letture OSMER. |
| `backend_dryrun_staging/audit_log/osmer/raw/*.xml` | XML OSMER grezzi letti. |
| `backend_dryrun_staging/audit_log/osmer/snapshots/*.structured.json` | Snapshot strutturati/merged passati al contratto. |
| `backend_dryrun_staging/audit_log/osmer/invalidated_audits.json` | Marca audit da ignorare per blocchi locali non sorgente. |

Decisioni:

- Il registro OSMER deve salvare hash e raw XML, non solo `ready/unavailable`.
- Un blocco rete locale del sandbox (`WinError 10013`) non va registrato come fonte OSMER non disponibile.
- Lo script e' stato corretto per fallire esplicitamente in quel caso.
- L'audit `osmer-2026-06-26T103623p0200` e' invalidato: era sandbox/network block, non indisponibilita OSMER.

Verifiche:

```text
python -B -c "compile(open('backend_dryrun_staging/osmer_source_audit.py', encoding='utf-8').read(), 'backend_dryrun_staging/osmer_source_audit.py', 'exec'); print('compile OK')"
compile OK

python -B backend_dryrun_staging\osmer_source_audit.py --sample-file "F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\backend\fixtures\osmer\PW20260606.xml" --requested-date 2026-06-07 --now 2026-06-07T10:00:00+02:00
state=ready
can_render_native_map=true
valid_dates=2026-06-07, 2026-06-08

python -B backend_dryrun_staging\osmer_source_audit.py
state=ready
can_render_native_map=true
valid_dates=2026-06-26, 2026-06-27, 2026-06-28, 2026-06-29
fetched_xml=NW20260627, PW20260625, PW20260624
```

## Tranche 70 - Report unico audit Allerte + OSMER

File creati:

| File | Ruolo |
| --- | --- |
| `backend_dryrun_staging/data_pipeline_status_report.py` | Legge audit locali salvati e produce un report congiunto Allerte + OSMER, senza rete e senza scritture. |

File aggiornati:

| File | Ruolo |
| --- | --- |
| `backend_dryrun_staging/README.md` | Documentato il comando report, `--scope live`, `--scope sample` e `--format json`. |
| `BACKEND_DATA_STATE_CONTRACT.md` | Registrata la decisione architetturale del report congiunto prima di qualunque collegamento live. |

Decisioni:

- Il report usa `--scope live` di default, cosi' non confonde fixture generate dopo con prove reali precedenti.
- Le fixture restano leggibili con `--scope sample`.
- Gli audit OSMER invalidati in `audit_log/osmer/invalidated_audits.json` vengono ignorati.
- Il report non chiama rete, non scrive file, non collega backend runtime, Firestore, FCM o UI.

Esito report live:

```text
Allerte ufficiali:
state=inactive_confirmed
alerts_found=0
home=nessuna allerta in Home
bollettino=nessun avviso allerta nel Bollettino
notifiche=non inviata: fonte verificata senza allerta
clears_previous_alert=true

OSMER:
state=ready
valid_dates=2026-06-26, 2026-06-27, 2026-06-28, 2026-06-29
can_render_native_map=true
fetched_xml=NW20260627, PW20260625, PW20260624
non_blocking_404=NW20260628, PW20260626

Decisione:
overall=ready_for_review
can_show_bulletin=true
can_render_map=true
can_clear_previous_alert=true
notification_dry_run_allowed=false
notification_live_connected=false
```

Verifiche:

```text
python -B -c "compile(open('backend_dryrun_staging/data_pipeline_status_report.py', encoding='utf-8').read(), 'backend_dryrun_staging/data_pipeline_status_report.py', 'exec'); print('compile OK')"
compile OK

python -B backend_dryrun_staging\data_pipeline_status_report.py
stato complessivo: ready_for_review

python -B backend_dryrun_staging\data_pipeline_status_report.py --format json
JSON valido generato

python -B backend_dryrun_staging\data_pipeline_status_report.py --scope sample
fixture locali lette separatamente
```

## Tranche 71 - Matrice casi e test non regressione data pipeline

File creati:

| File | Ruolo |
| --- | --- |
| `backend_dryrun_staging/data_pipeline_case_matrix.json` | Matrice dichiarativa dei casi minimi Allerte + OSMER da non rompere. |
| `backend_dryrun_staging/test_data_pipeline_status_report.py` | Test locali read-only sul report e sulle decisioni `ready_for_review` / `needs_review`. |

File aggiornati:

| File | Ruolo |
| --- | --- |
| `backend_dryrun_staging/data_pipeline_status_report.py` | Reso piu stretto il criterio `ready_for_review`: stati allerta dubbi non sono piu considerati pronti. |
| `backend_dryrun_staging/README.md` | Documentati matrice, test e semantica di `ready_for_review`. |
| `BACKEND_DATA_STATE_CONTRACT.md` | Registrata la regola architetturale: solo `active` e `inactive_confirmed` possono chiudere la decisione app. |

Decisioni:

- `ready_for_review` non significa solo "report generato".
- Serve una decisione app affidabile:
  - allerta `active` oppure `inactive_confirmed`;
  - OSMER usabile;
  - mappa A1-A9 renderizzabile.
- Stati allerta `diagnostic`, `expired`, `stale`, `stale_held_active` e `unavailable` producono `needs_review`.
- Le notifiche restano solo dry-run: `notification_live_connected=false`.

Copertura matrice:

```text
Allerte:
- no_alert_confirmed
- yellow_alert
- orange_alert
- red_alert
- source_unavailable
- page_changed_parse_error
- stale_data

OSMER:
- xml_complete
- xml_404_recovered_from_window
- missing_a1_a9
- text_without_map
- source_unavailable
```

Verifiche:

```text
python -B -c "compile(open('backend_dryrun_staging/data_pipeline_status_report.py', encoding='utf-8').read(), 'backend_dryrun_staging/data_pipeline_status_report.py', 'exec'); compile(open('backend_dryrun_staging/test_data_pipeline_status_report.py', encoding='utf-8').read(), 'backend_dryrun_staging/test_data_pipeline_status_report.py', 'exec'); print('compile OK')"
compile OK

python -B backend_dryrun_staging\test_data_pipeline_status_report.py
Ran 5 tests
OK

python -B backend_dryrun_staging\data_pipeline_status_report.py
stato complessivo: ready_for_review
```

## Tranche 72 - Caso portale FVG irraggiungibile con allerta precedente valida

File aggiornati:

| File | Ruolo |
| --- | --- |
| `backend_dryrun_staging/data_pipeline_case_matrix.json` | Aggiunto `primary_unreachable_keep_previous_alert`. |
| `backend_dryrun_staging/test_data_pipeline_status_report.py` | Aggiunto test dedicato su mantenimento allerta precedente e diagnostica non decisionale. |
| `backend_dryrun_staging/README.md` | Documentato comportamento utente e ruolo diagnostico di Telegram/DPC. |
| `BACKEND_DATA_STATE_CONTRACT.md` | Registrata la regola architetturale. |

Decisioni:

- Se il portale/widget FVG primario non e' raggiungibile e l'allerta precedente e' ancora valida, l'app mantiene l'allerta precedente.
- La UI mostra l'allerta e la sua scadenza senza testo "da verificare" e senza messaggi tecnici.
- Telegram ufficiale FVG e DPC nazionale sono diagnostica interna.
- Telegram/DPC non possono:
  - spegnere l'allerta;
  - dichiarare "nessuna allerta";
  - generare notifiche live;
  - sostituire la fonte primaria FVG.
- Il report resta `needs_review` perche' la fonte primaria non ha confermato lo stato corrente, ma l'effetto utente mantiene l'allerta precedente.

Verifiche:

```text
python -B -c "compile(open('backend_dryrun_staging/data_pipeline_status_report.py', encoding='utf-8').read(), 'backend_dryrun_staging/data_pipeline_status_report.py', 'exec'); compile(open('backend_dryrun_staging/test_data_pipeline_status_report.py', encoding='utf-8').read(), 'backend_dryrun_staging/test_data_pipeline_status_report.py', 'exec'); print('compile OK')"
compile OK

python -B backend_dryrun_staging\test_data_pipeline_status_report.py
Ran 6 tests
OK

python -B backend_dryrun_staging\data_pipeline_status_report.py
stato complessivo: ready_for_review
```

## Tranche 73 - Motore puro transizione allerte ufficiali

File creati:

| File | Ruolo |
| --- | --- |
| `backend_dryrun_staging/official_alert_transition_policy.py` | Motore puro per decidere effetto utente e stato finale da stato precedente, fonte primaria FVG e diagnostiche opzionali. |
| `backend_dryrun_staging/test_official_alert_transition_policy.py` | Test unitari del motore, incluso allineamento con `data_pipeline_case_matrix.json`. |

File aggiornati:

| File | Ruolo |
| --- | --- |
| `backend_dryrun_staging/README.md` | Documentato il comando demo e le regole protette. |
| `BACKEND_DATA_STATE_CONTRACT.md` | Registrato il motore puro e corretto il ruolo di DPC nazionale a diagnostica non decisionale. |

Decisioni:

- Solo la fonte primaria FVG puo decidere `active` o `inactive_confirmed`.
- `inactive_confirmed` e' l'unico stato che puo spegnere una vecchia allerta.
- Se la fonte primaria FVG e' irraggiungibile e una vecchia allerta e' ancora valida, l'app mantiene la vecchia allerta con la normale scadenza.
- Telegram FVG e DPC nazionale sono diagnostica interna: non accendono, non spengono, non dichiarano "nessuna allerta" e non notificano.
- In Home e Bollettino non compare copy tecnico tipo "da verificare" per questo caso.
- Il modulo non chiama rete, non scrive file, non collega backend runtime, Firestore, FCM o UI.

Verifiche:

```text
python -B -c "compile(open('backend_dryrun_staging\\official_alert_transition_policy.py', encoding='utf-8').read(), 'backend_dryrun_staging/official_alert_transition_policy.py', 'exec'); compile(open('backend_dryrun_staging\\test_official_alert_transition_policy.py', encoding='utf-8').read(), 'backend_dryrun_staging/test_official_alert_transition_policy.py', 'exec'); print('compile OK')"
compile OK

python -B backend_dryrun_staging\test_official_alert_transition_policy.py
Ran 7 tests
OK

python -B backend_dryrun_staging\test_data_pipeline_status_report.py
Ran 6 tests
OK

python -B backend_dryrun_staging\official_alert_transition_policy.py --format markdown
tabella scenari generata
```

## Tranche 74 - Policy cadenza controllo fonte FVG

File aggiornati:

| File | Ruolo |
| --- | --- |
| `BACKEND_DATA_STATE_CONTRACT.md` | Aggiunta la policy architetturale di controllo fonte FVG. |
| `backend_dryrun_staging/README.md` | Aggiunto promemoria operativo della cadenza futura. |

Decisioni:

- Nessuna allerta confermata: controllo FVG ogni 30 minuti.
- Allerta attiva: controllo FVG ogni 10-15 minuti.
- Fonte FVG irraggiungibile: retry a 5 minuti, poi 10, poi 20-30.
- Ultima ora prima della scadenza: controllo ogni 5-10 minuti.
- Telegram FVG e DPC nazionale restano diagnostica, non scheduler decisionale.
- La policy non collega job live, rete, Firestore, FCM o UI.

## Tranche 75 - Motore puro cadenza controllo FVG

File creati:

| File | Ruolo |
| --- | --- |
| `backend_dryrun_staging/official_alert_polling_policy.py` | Funzione pura che trasforma stato allerta/fonte/errori/scadenza in prossimo controllo FVG. |
| `backend_dryrun_staging/test_official_alert_polling_policy.py` | Test unitari su 30 min, 15 min, ultima ora, backoff 5/10/20/30 e diagnostica non decisionale. |

File aggiornati:

| File | Ruolo |
| --- | --- |
| `backend_dryrun_staging/README.md` | Documentato comando demo e test della policy polling. |
| `BACKEND_DATA_STATE_CONTRACT.md` | Collegata la policy architetturale al banco prova locale. |

Decisioni:

- `inactive_confirmed` -> prossimo controllo FVG a 30 minuti.
- `active` -> prossimo controllo FVG a 15 minuti.
- `active` in ultima ora di validita -> prossimo controllo FVG a 5 minuti.
- FVG irraggiungibile -> backoff 5, 10, 20, 30 minuti.
- Dopo almeno 2 errori FVG consecutivi, Telegram/DPC possono essere consultati solo come diagnostica.
- Il modulo espone `scheduler_connected=false` e `live_connected=false`.

Verifiche:

```text
python -B -c "compile(open('backend_dryrun_staging\\official_alert_polling_policy.py', encoding='utf-8').read(), 'backend_dryrun_staging/official_alert_polling_policy.py', 'exec'); compile(open('backend_dryrun_staging\\test_official_alert_polling_policy.py', encoding='utf-8').read(), 'backend_dryrun_staging/test_official_alert_polling_policy.py', 'exec'); print('compile OK')"
compile OK

python -B backend_dryrun_staging\test_official_alert_polling_policy.py
Ran 7 tests
OK

python -B backend_dryrun_staging\official_alert_polling_policy.py --format markdown
tabella scenari generata
```

## Tranche 76 - Report unico con prossimo controllo FVG

File aggiornati:

| File | Ruolo |
| --- | --- |
| `backend_dryrun_staging/data_pipeline_status_report.py` | Integra `official_alert_polling_policy.py` nel report Allerte + OSMER. |
| `backend_dryrun_staging/test_data_pipeline_status_report.py` | Aggiunti test su `polling`, testo report e caso fonte FVG irraggiungibile con errori consecutivi. |
| `backend_dryrun_staging/README.md` | Documentato che il report espone prossimo controllo FVG e diagnostica. |
| `BACKEND_DATA_STATE_CONTRACT.md` | Registrato il blocco `polling` nel report locale congiunto. |

Decisioni:

- Il report unico ora mostra anche `Prossimo controllo FVG`.
- Il blocco `polling` contiene `next_check_minutes`, `reason`, `source_unreachable`, `consecutive_failures`, diagnostica Telegram/DPC e flag `scheduler_connected=false`.
- Per il report live corrente con `inactive_confirmed`, il prossimo controllo FVG e' tra 30 minuti.
- Per fonte FVG irraggiungibile con due errori consecutivi, il report pianifica retry a 10 minuti e abilita Telegram/DPC solo come diagnostica.
- Nessun job live, scheduler, rete, Firestore, FCM o UI collegato.

Verifiche:

```text
python -B -c "compile(open('backend_dryrun_staging\\data_pipeline_status_report.py', encoding='utf-8').read(), 'backend_dryrun_staging/data_pipeline_status_report.py', 'exec'); compile(open('backend_dryrun_staging\\test_data_pipeline_status_report.py', encoding='utf-8').read(), 'backend_dryrun_staging/test_data_pipeline_status_report.py', 'exec'); print('compile OK')"
compile OK

python -B backend_dryrun_staging\test_data_pipeline_status_report.py
Ran 7 tests
OK

python -B backend_dryrun_staging\data_pipeline_status_report.py
Prossimo controllo FVG: 30 minuti
```

## Tranche 77 - Matrice notifiche ufficiali

File creati:

| File | Ruolo |
| --- | --- |
| `backend_dryrun_staging/official_alert_notification_policy.py` | Motore puro `previous_alert_state + final_alert_state -> notification_decision`. |
| `backend_dryrun_staging/test_official_alert_notification_policy.py` | Test su nuova allerta, duplicato, cambio colore, cambio testo, diagnostiche e stati non notificabili. |

File aggiornati:

| File | Ruolo |
| --- | --- |
| `backend_dryrun_staging/data_pipeline_case_matrix.json` | Aggiunta sezione `notification_cases`. |
| `backend_dryrun_staging/official_alert_transition_policy.py` | La transizione usa la nuova policy notifiche invece della vecchia mini-regola interna. |
| `backend_dryrun_staging/test_official_alert_transition_policy.py` | Aggiornati test per nuova allerta e cambio stesso livello non importante. |
| `backend_dryrun_staging/README.md` | Documentata policy notifiche e comando demo. |
| `BACKEND_DATA_STATE_CONTRACT.md` | Aggiunta matrice notifiche allerte. |

Decisioni:

- Nuova allerta gialla/arancione/rossa da fonte primaria FVG: notifica ammessa.
- Stessa allerta gia nota: nessuna notifica.
- Cambio colore: notifica ammessa.
- Cambio testo a parita di livello: nessuna notifica, salvo cambio marcato importante.
- Fonte FVG irraggiungibile con vecchia allerta mantenuta: nessuna notifica.
- FVG conferma nessuna allerta: nessuna notifica.
- Allerta scaduta senza conferma FVG: nessuna notifica.
- Telegram FVG e DPC nazionale diagnostici: mai notifica.
- Il modulo produce `live_connected=false`.

Verifiche:

```text
python -B -c "import json; json.loads(open('backend_dryrun_staging\\data_pipeline_case_matrix.json', encoding='utf-8').read()); compile(open('backend_dryrun_staging\\official_alert_notification_policy.py', encoding='utf-8').read(), 'backend_dryrun_staging/official_alert_notification_policy.py', 'exec'); compile(open('backend_dryrun_staging\\test_official_alert_notification_policy.py', encoding='utf-8').read(), 'backend_dryrun_staging/test_official_alert_notification_policy.py', 'exec'); print('compile/json OK')"
compile/json OK

python -B backend_dryrun_staging\test_official_alert_notification_policy.py
Ran 11 tests
OK

python -B backend_dryrun_staging\test_official_alert_transition_policy.py
Ran 8 tests
OK
```

## Tranche 78 - Report unico con decisione notifica dettagliata

File aggiornati:

| File | Ruolo |
| --- | --- |
| `backend_dryrun_staging/data_pipeline_status_report.py` | Aggiunto blocco `notification_decision` calcolato con `official_alert_notification_policy.py`. |
| `backend_dryrun_staging/test_data_pipeline_status_report.py` | Aggiunti test su report live, testo renderizzato e nuova allerta FVG notificabile in dry-run. |
| `backend_dryrun_staging/README.md` | Documentato il blocco `Decisione notifica`. |
| `BACKEND_DATA_STATE_CONTRACT.md` | Registrato `notification_decision` nel report locale congiunto. |

Decisioni:

- Il report non usa piu solo il vecchio campo sintetico dell'audit per spiegare la notifica.
- La sezione `Decisione notifica` espone `can_notify`, `reason`, `severity`, `dedupe_key` e `live_connected=false`.
- Il report live corrente produce `inactive_confirmed_does_not_notify`.
- Un caso artificiale di nuova allerta FVG gialla da payload salvato produce `new_fvg_alert` e `can_notify=true` in dry-run.
- Nessun FCM, scheduler, rete, Firestore o UI collegato.

Verifiche:

```text
python -B -c "compile(open('backend_dryrun_staging\\data_pipeline_status_report.py', encoding='utf-8').read(), 'backend_dryrun_staging/data_pipeline_status_report.py', 'exec'); compile(open('backend_dryrun_staging\\test_data_pipeline_status_report.py', encoding='utf-8').read(), 'backend_dryrun_staging/test_data_pipeline_status_report.py', 'exec'); print('compile OK')"
compile OK

python -B backend_dryrun_staging\test_data_pipeline_status_report.py
Ran 8 tests
OK

python -B backend_dryrun_staging\data_pipeline_status_report.py
Decisione notifica: inactive_confirmed_does_not_notify
```

## Tranche 79 - Gate read-only ponte backend live

File aggiornati:

| File | Ruolo |
| --- | --- |
| `backend_dryrun_staging/backend_live_bridge_readiness.py` | Nuovo controllo locale read-only sui blocchi prima di qualunque collegamento live. |
| `backend_dryrun_staging/test_backend_live_bridge_readiness.py` | Test del gate con sorgenti temporanee pulite e casi bloccanti. |
| `BACKEND_LIVE_BRIDGE_PLAN.md` | Piano ordinato per risolvere i 5 blocker senza collegare live. |
| `backend_dryrun_staging/README.md` | Documentato comando, regole e blocchi attesi. |
| `INFRA_DATA_PIPELINE_AUDIT.md` | Registrato esito del gate sul vecchio sorgente. |
| `BACKEND_DATA_STATE_CONTRACT.md` | Inserito il gate come requisito prima del live. |
| `README.md` | Aggiunto riferimento al piano ponte backend. |
| `STARTUP_PROMPT.md` | Aggiunti i documenti dati/backend tra i file operativi. |
| `AUDIT_CHECKLIST.md` | Aggiunto il gate tra i controlli prima del collegamento live. |

Decisioni:

- Il vecchio sorgente deve risultare `ready` nel gate prima di toccare Cloud Run, GitHub Actions, Firestore finale o FCM.
- Il gate non chiama rete, non scrive Firestore, non invia FCM e non modifica file del vecchio progetto.
- Al 2026-06-26 il vecchio sorgente risulta correttamente `blocked`.
- I blocchi trovati sono: Dockerfile senza `data_state_contract.py`, push ancora guidato da `alerts[]`, storage `official_alert_state/current` assente, workflow con push reale `dry_run:false`, fallback DPC attivo storico.

Verifiche:

```text
python -B backend_dryrun_staging\test_backend_live_bridge_readiness.py
Ran 5 tests
OK

python -B -m unittest discover backend_dryrun_staging
Ran 39 tests
OK

python -B backend_dryrun_staging\backend_live_bridge_readiness.py
Overall: blocked
Blockers: 5
```

## Tranche 80 - Packaging sicuro backend sorgente

File aggiornati:

| File | Ruolo |
| --- | --- |
| `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\backend\Dockerfile` | Aggiunto `COPY data_state_contract.py .` per includere il contratto dati nella futura immagine backend. |
| `BACKEND_LIVE_BRIDGE_PLAN.md` | Tranche A marcata come completata; blocker correnti ridotti da 5 a 4. |
| `INFRA_DATA_PIPELINE_AUDIT.md` | Audit aggiornato con esito gate post-Tranche A. |
| `BACKEND_DATA_STATE_CONTRACT.md` | Gate live aggiornato: Dockerfile risolto, restano i blocchi decisione/push/storage/DPC. |
| `backend_dryrun_staging/README.md` | Documentato stato gate dopo packaging. |

Decisioni:

- Questa tranche non collega Cloud Run, Firebase, GitHub Actions, Firestore, FCM, scheduler o UI.
- Il cambio e' solo packaging: evita una futura immagine backend incompleta.
- Il gate resta correttamente `blocked`: non siamo pronti al live.
- I blocker residui sono workflow push reale, fallback DPC storico, storage finale allerta e dispatcher push ancora guidato da `alerts[]`.

Verifiche:

```text
python -B backend_dryrun_staging\backend_live_bridge_readiness.py --format json
overall=blocked
blockers=4
dockerfile_copies_data_state_contract=pass

python -B -m unittest discover backend_dryrun_staging
Ran 39 tests
OK

python -B -c "<parse sintattico read-only backend main/data_state_contract/test_data_state_contract>"
syntax ok
```

## Tranche 81 - Workflow sync allerte senza push reale automatico

File aggiornati:

| File | Ruolo |
| --- | --- |
| `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\.github\workflows\sync-official-alerts.yml` | Il workflow sincronizza ancora le allerte, ma il controllo `/push/alerts/check` e' solo `dry_run:true`. |
| `BACKEND_LIVE_BRIDGE_PLAN.md` | Tranche B marcata come completata; blocker correnti ridotti da 4 a 3. |
| `INFRA_DATA_PIPELINE_AUDIT.md` | Audit aggiornato con esito gate post-Tranche B. |
| `BACKEND_DATA_STATE_CONTRACT.md` | Gate live aggiornato: workflow push reale risolto, restano DPC/storage/dispatcher. |
| `backend_dryrun_staging/README.md` | Documentato stato gate dopo neutralizzazione workflow. |

Decisioni:

- Il workflow non si chiama piu "Sync and send official FVG alerts".
- La chiamata a `/push/alerts/check` resta solo per simulare la decisione.
- Payload cambiato da `{"force":false,"dry_run":false}` a `{"force":false,"dry_run":true}`.
- Nessun workflow eseguito, nessun deploy, nessun FCM, nessuno scheduler collegato.
- Il gate resta correttamente `blocked`: non siamo pronti al live.
- I blocker residui sono fallback DPC storico, storage finale allerta e dispatcher push ancora guidato da `alerts[]`.

Verifiche:

```text
python -B backend_dryrun_staging\backend_live_bridge_readiness.py --format json
overall=blocked
blockers=3
official_alert_workflow_no_real_push_after_sync=pass

python -B -m unittest discover backend_dryrun_staging
Ran 39 tests
OK
```

## Tranche 82 - DPC nazionale solo diagnostico nel sync sorgente

File aggiornati:

| File | Ruolo |
| --- | --- |
| `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\scripts\sync-protezione-civile-alert-override.py` | DPC nazionale declassato a diagnostica `skip_backend_update`; non produce piu override attivo/no-alert. |
| `backend_dryrun_staging/official_alert_source_audit.py` | I campioni DPC vengono esportati come payload diagnostici/skipped. |
| `BACKEND_LIVE_BRIDGE_PLAN.md` | Tranche C marcata come completata; blocker correnti ridotti da 3 a 2. |
| `INFRA_DATA_PIPELINE_AUDIT.md` | Audit aggiornato con esito gate post-Tranche C. |
| `BACKEND_DATA_STATE_CONTRACT.md` | Gate live aggiornato: DPC risolto, restano storage finale e dispatcher push. |
| `backend_dryrun_staging/README.md` | Documentato stato gate dopo declassamento DPC. |

Decisioni:

- Pagina/widget FVG restano le sole fonti decisionali per `active` e `inactive_confirmed`.
- DPC nazionale puo essere letto solo come diagnostica quando le fonti FVG non rispondono.
- DPC non puo accendere allerta, spegnere allerta, dichiarare no-alert o notificare.
- Se DPC viene letto, lo script produce `skip_backend_update`.
- Nessun deploy, nessun workflow eseguito, nessun FCM, nessuno scheduler collegato.
- Il gate resta correttamente `blocked`: non siamo pronti al live.
- I blocker residui sono storage finale `official_alert_state/current` e dispatcher push ancora guidato da `alerts[]`.

Verifiche:

```text
python -B -c "<parse sintattico read-only script sync + tool audit>"
syntax ok

python -B sync-protezione-civile-alert-override.py --dry-run --sample-parser national_criticity
action=skip_backend_update
reason=regional_source_unreachable_dpc_diagnostic_only
source_mode=github_actions_dpc_national_criticity_diagnostic

python -B backend_dryrun_staging\official_alert_payload_dryrun.py backend_dryrun_staging\exports\tranche-c-dpc-diagnostic.contract.json
state=unavailable
can_notify=false
can_clear_previous_alert=false

python -B backend_dryrun_staging\official_alert_payload_dryrun.py backend_dryrun_staging\exports\tranche-c-widget-no-alerts.contract.json
state=inactive_confirmed
can_notify=false
can_clear_previous_alert=true

python -B backend_dryrun_staging\backend_live_bridge_readiness.py --format json
overall=blocked
blockers=2
sync_script_dpc_is_not_decision_source=pass

python -B -m unittest discover backend_dryrun_staging
Ran 39 tests
OK
```

## Tranche 83 - Piano storage dry-run per `official_alert_state/current`

File aggiornati:

| File | Ruolo |
| --- | --- |
| `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\backend\data_state_contract.py` | Aggiunto `build_official_alert_storage_plan()` e costanti logiche per stato, osservazioni, transizioni e audit push. |
| `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\backend\test_data_state_contract.py` | Aggiunto test per garantire che il piano storage resti dry-run e senza scritture. |
| `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\backend\main.py` | Il dry-run ufficiale restituisce `storage_plan`; nessun endpoint live o push reale collegato. |
| `BACKEND_LIVE_BRIDGE_PLAN.md` | Tranche D marcata come completata; blocker correnti ridotti da 2 a 1. |
| `INFRA_DATA_PIPELINE_AUDIT.md` | Audit aggiornato con esito gate post-Tranche D. |
| `BACKEND_DATA_STATE_CONTRACT.md` | Contratto aggiornato con `storage_plan` e stato residuo del gate. |
| `backend_dryrun_staging/README.md` | Documentato stato gate dopo introduzione del piano storage. |

Decisioni:

- Il piano storage e' solo dichiarativo e dry-run.
- Percorsi previsti:
  - `official_alert_state/current`;
  - `official_alert_observations/{observation_id}`;
  - `official_alert_transitions/{transition_id}`;
  - `push_decision_audit/{transition_id}`.
- `write_enabled=false`: nessuna scrittura Firestore, nessuno storage reale, nessun deploy.
- La UI, scheduler, GitHub Actions e FCM restano scollegati.
- Il blocker residuo e' il dispatcher push ufficiale ancora guidato da `alerts[]` / `actionable_official_alerts`.

Verifiche:

```text
python -B -c "<parse sintattico read-only backend main/data_state_contract/test_data_state_contract>"
syntax ok

python -B -m unittest test_data_state_contract
Ran 13 tests
OK

python -B backend_dryrun_staging\backend_live_bridge_readiness.py --format json
overall=blocked
blockers=1
final_state_storage_not_implemented=pass

python -B -m unittest discover backend_dryrun_staging
Ran 39 tests
OK
```

## Tranche 84 - Push ufficiali guidati da transizione

File aggiornati:

| File | Ruolo |
| --- | --- |
| `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\backend\main.py` | Aggiunto `build_official_alert_push_decision()`; `dispatch_official_alert_pushes()` invia solo se il contratto produce `NOTIFY_NEW_OFFICIAL_ALERT`. |
| `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\backend\data_state_contract.py` | DPC nazionale attivo/no-active classificato come diagnostica non notificabile. |
| `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\backend\fixtures\data_state\official_alert_cases.json` | Caso DPC active fallback aggiornato a `diagnostic`, senza Home banner e senza notifica. |
| `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\backend\test_weather_engine.py` | Aggiunti test mirati per dispatcher push ufficiale: fonte regionale attiva, DPC diagnostico, metadati fonte. |
| `BACKEND_LIVE_BRIDGE_PLAN.md` | Tranche E marcata come completata; gate locale `ready`. |
| `INFRA_DATA_PIPELINE_AUDIT.md` | Audit aggiornato con esito gate post-Tranche E. |
| `BACKEND_DATA_STATE_CONTRACT.md` | Contratto aggiornato: push ufficiale non guidato piu da `alerts[]` come decisore diretto. |
| `backend_dryrun_staging/README.md` | Documentato stato `ready` del gate read-only. |

Decisioni:

- La fonte FVG resta l'unica fonte decisionale per nuove notifiche ufficiali.
- DPC nazionale resta diagnostica, anche se contiene una criticita: non accende notifiche Meteo Friul.
- `dispatch_official_alert_pushes()` conserva deduplica e `PUSH_DRY_RUN`.
- Nessun deploy, nessun workflow eseguito, nessun Firestore reale collegato, nessun FCM reale.
- Il gate locale passa `overall=ready`, ma il live richiede ancora una tranche dedicata con rollback e approvazione esplicita.

Verifiche:

```text
python -B -m unittest test_data_state_contract
Ran 13 tests
OK

python -B -m unittest test_weather_engine.OfficialAlertPushHardeningTest.test_official_push_response_exposes_alert_source_metadata test_weather_engine.OfficialAlertPushHardeningTest.test_official_push_suppresses_diagnostic_dpc_source test_weather_engine.OfficialAlertPushHardeningTest.test_official_push_uses_transition_decision_for_regional_alert
Ran 3 tests
OK

python -B backend_dryrun_staging\backend_live_bridge_readiness.py --format json
overall=ready
blockers=0
official_push_uses_transition_decision=pass

python -B -m unittest discover backend_dryrun_staging
Ran 39 tests
OK

python -B -c "<parse sintattico read-only backend main/data_state_contract/test_data_state_contract/test_weather_engine>"
syntax ok
```

## Tranche 85 - Audit test legacy e piano collegamento protetto

File aggiornati:

| File | Ruolo |
| --- | --- |
| `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\backend\test_weather_engine.py` | Test legacy DPC aggiornati: DPC nazionale ora verifica diagnostica `skip_backend_update`, non fallback decisionale. |
| `BACKEND_LIVE_BRIDGE_PLAN.md` | Aggiunta Tranche F futura: collegamento protetto con rollback, dry-run e nessun FCM reale senza approvazione. |
| `INFRA_DATA_PIPELINE_AUDIT.md` | Audit aggiornato con suite legacy verde e test DPC riallineati. |

Decisioni:

- I 4 errori della suite legacy erano test obsoleti, non regressioni runtime.
- Non sono state reintrodotte costanti DPC decisionali rimosse.
- DPC nazionale resta diagnostica anche nei test legacy.
- Il prossimo passaggio live richiede una tranche dedicata: snapshot configurazioni, rollback, `PUSH_DRY_RUN`, deploy controllato, smoke test read-only.
- Nessun deploy, nessun workflow eseguito, nessun Firestore reale collegato, nessun FCM reale.

Verifiche:

```text
python -B -m unittest test_weather_engine.OfficialAlertPushHardeningTest
Ran 16 tests
OK

python -B -m unittest test_weather_engine
Ran 65 tests
OK

python -B -m unittest test_data_state_contract
Ran 13 tests
OK

python -B -m unittest discover backend_dryrun_staging
Ran 39 tests
OK

python -B backend_dryrun_staging\backend_live_bridge_readiness.py --format json
overall=ready
blockers=0

python -B -c "<parse sintattico read-only backend test_weather_engine/main/data_state_contract>"
syntax ok
```

## Tranche 86 - Audit visualizzazione Bollettino e previsioni

File aggiornati:

| File | Ruolo |
| --- | --- |
| `frontend/src/features/bulletin/bulletinViewModel.js` | Rimossa la fixture come fallback reale implicito; fixture abilitate solo con `allowFixtureFallback:true`; stato senza dati reali ora `unavailable`. |
| `frontend/src/features/bulletin/BulletinView.jsx` | Nasconde attendibilita', focus e dati utili quando non arrivano da modello reale. |
| `frontend/src/features/bulletin/bulletinViewModel.test.js` | Test guardrail: niente previsioni fixture quando mancano OSMER/testo ufficiale; fixture solo lab esplicito. |
| `BULLETIN_DATA_DISPLAY_AUDIT.md` | Documento dedicato alla regola di visualizzazione Bollettino/previsioni/allerta. |
| `BACKEND_DATA_STATE_CONTRACT.md` | Aggiunta regola UI 3.0.0: nessuna alternativa mascherata a OSMER. |
| `INFRA_DATA_PIPELINE_AUDIT.md` | Audit aggiornato con verifica locale read-only e regole di prodotto. |

Decisioni:

- La mappa nativa si mostra solo con `source_kind=structured_xml`, A1-A9 complete e dato non stale.
- `official_projected` resta diagnostica/audit: non e' mappa nativa e non sostituisce XML OSMER.
- Fixture e dati laboratorio non possono riempire il Bollettino reale.
- Dati utili/focus restano nascosti finche' non hanno fonte reale dichiarata.
- DPC nazionale/no-active resta diagnostico e non produce avviso UI.

Verifica locale read-only:

```text
frontend: http://127.0.0.1:5173/?tab=bulletin
backend: http://127.0.0.1:8001

GET /api/health/data-sources
status=ok

GET /api/weather/bootstrap?city=Udine
forecast.osmer_structured=true
source_status=merged_xml_window
days=5
source_kind=structured_xml per 5 giorni
A1-A9 complete e F1-F4 complete
official_alerts.source_mode=github_actions_dpc_national_criticity_no_active_fvg_unverified
```

Verifiche:

```text
npx vitest run --configLoader native src/features/bulletin/bulletinViewModel.test.js src/features/bulletin/bulletinDataController.test.js src/domain/weather/osmerStructuredContract.test.js
Test Files 3 passed
Tests 17 passed

npx vitest run --configLoader native src/domain/alerts/officialAlerts.test.js src/features/bulletin/bulletinViewModel.test.js
Test Files 2 passed
Tests 19 passed

npm run build
build OK
```

## Tranche 87 - Audit notifiche meteo locali

File aggiornati:

| File | Ruolo |
| --- | --- |
| `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\backend\main.py` | Copy caldo locale riallineato alla localita: `Caldo previsto oggi a {city}.`. |
| `LOCAL_WEATHER_NOTICE_ENGINE_AUDIT.md` | Audit e contratto candidato per notifiche meteo locali non-allerta. |
| `BACKEND_DATA_STATE_CONTRACT.md` | Aggiunta sezione `local_weather_notice_*`, distinta da allerte e OSMER. |
| `INFRA_DATA_PIPELINE_AUDIT.md` | Audit aggiornato con stato endpoint/workflow push meteo locali. |

Decisioni:

- Le notifiche meteo locali sono un terzo motore, distinto da Allerte ufficiali e Bollettino OSMER.
- Devono essere localizzate per citta dell'utente.
- Frasi macro-area come `temporali sui monti` o `caldo in pianura` non sono adatte a una push personale.
- Nessuna parola `Allerta`, nessun colore giallo/arancione/rosso, nessun tono Protezione Civile.
- Se un'allerta ufficiale copre la stessa categoria, la notifica locale viene soppressa.
- Il workflow esistente `send-local-weather-notices.yml` resta manuale; non viene schedulato.

Stato audit:

- il backend vecchio raggruppa i device per `city`;
- `build_local_weather_notices_for_city(city)` genera pioggia, temporali, grandine, neve, ghiaccio, vento/Bora e caldo;
- il motore usa anche `hourly_next_12h` e supporto modello, quindi non e' ancora il contratto definitivo UI 3.0.0;
- prima di promuoverlo servono `source_inputs`, `confidence`, stato finale e dry-run controllato.

Verifiche:

```text
python -B -m unittest test_local_weather_pushes
Ran 4 tests
OK

python -B -m unittest test_weather_engine.LocalWeatherPushTest
Ran 10 tests
OK
```

## Tranche 88 - Copy caldo locale asciutta

File aggiornati:

| File | Ruolo |
| --- | --- |
| `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\backend\main.py` | Copy caldo locale resa breve e non prescrittiva: `Caldo previsto oggi a {city}.`. |
| `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\backend\test_local_weather_pushes.py` | Test aggiornato sulla nuova frase IT/FUR. |
| `LOCAL_WEATHER_NOTICE_ENGINE_AUDIT.md` | Contratto esempi aggiornato: push locale informativa, senza consigli comportamentali. |
| `BACKEND_DATA_STATE_CONTRACT.md` | Nota sul vecchio mismatch copy marcata come risolta. |
| `INFRA_DATA_PIPELINE_AUDIT.md` | Audit aggiornato con la frase definitiva. |

Decisione:

- Le push meteo locali devono rimanere brevi e informative.
- La localita resta nella frase.
- I consigli comportamentali non entrano nella copy automatica.

Verifiche:

```text
python -B -m unittest test_local_weather_pushes test_weather_engine.LocalWeatherPushTest
Ran 14 tests
OK

python -B -m unittest discover backend_dryrun_staging
Ran 39 tests
OK
```

## Tranche 89 - Dry-run notifiche locali con priorita e tempo

File aggiornati:

| File | Ruolo |
| --- | --- |
| `backend_dryrun_staging/local_weather_notice_dryrun.py` | Report dry-run per notifiche meteo locali su fixture dichiarate, senza rete/storage/FCM/workflow. |
| `backend_dryrun_staging/test_local_weather_notice_dryrun.py` | Test della politica candidato -> notifica finale. |
| `LOCAL_WEATHER_NOTICE_ENGINE_AUDIT.md` | Scritta la politica anti-rumore ragionata. |
| `BACKEND_DATA_STATE_CONTRACT.md` | Contratto locale aggiornato con `candidate_can_notify`, `can_notify` e `notification_policy`. |
| `backend_dryrun_staging/README.md` | Documentato il comando dry-run locale. |

Decisioni:

- Non vale la regola cieca "una sola push".
- Ogni fenomeno nasce come candidato.
- L'allerta ufficiale coerente sopprime il candidato locale.
- La priorita candidata e': grandine, temporali, ghiaccio, neve, Bora, vento forte, pioggia, caldo.
- Fenomeni entro 4 ore non devono produrre doppia push.
- Il caldo viene trattenuto se entro 8 ore c'e' un fenomeno piu importante.
- Fenomeni separati mattina/sera possono restare entrambi notificabili.

Verifiche:

```text
python -B backend_dryrun_staging\local_weather_notice_dryrun.py
Report OK

python -B -m unittest backend_dryrun_staging.test_local_weather_notice_dryrun
Ran 3 tests
OK

python -B -m unittest discover backend_dryrun_staging
Ran 42 tests
OK
```

## Tranche 90 - Guardrail finestra temporale globale notifiche locali

File aggiornati:

| File | Ruolo |
| --- | --- |
| `backend_dryrun_staging/local_weather_notice_dryrun.py` | La selezione candidati ordina per priorita globale e usa il tempo solo come spareggio. |
| `backend_dryrun_staging/test_local_weather_notice_dryrun.py` | Test espliciti: grandine dopo pioggia vince entro 4 ore; a pari priorita vince l'evento prima. |
| `LOCAL_WEATHER_NOTICE_ENGINE_AUDIT.md` | Regola documentata: la finestra 4 ore e' un confronto globale, non una scansione solo in avanti. |
| `BACKEND_DATA_STATE_CONTRACT.md` | Contratto aggiornato con il criterio globale di finestra. |
| `backend_dryrun_staging/README.md` | Documentato il caso pioggia prima/grandine dopo. |

Decisioni:

- La selezione non deve dipendere dall'ordine cronologico di lettura.
- Dentro la finestra di 4 ore vince sempre la priorita piu alta.
- Se il fenomeno piu importante arriva dopo, puo eliminare retroattivamente un candidato meno importante.
- A pari priorita entro la finestra, vince l'evento piu vicino nel tempo.

Verifiche:

```text
python -B backend_dryrun_staging\local_weather_notice_dryrun.py
Report OK

python -B -m unittest backend_dryrun_staging.test_local_weather_notice_dryrun
Ran 5 tests
OK

python -B -m unittest discover backend_dryrun_staging
Ran 44 tests
OK
```

## Tranche 91 - Policy pura notifiche meteo locali

File aggiornati:

| File | Ruolo |
| --- | --- |
| `backend_dryrun_staging/local_weather_notification_policy.py` | Modulo puro `candidate notices -> final notification decision`, senza backend/rete/storage/FCM/fixture. |
| `backend_dryrun_staging/test_local_weather_notification_policy.py` | Test unitari della policy pura: priorita globale, parita temporale, caldo bloccato, finestre separate, input non mutato. |
| `backend_dryrun_staging/local_weather_notice_dryrun.py` | Il report usa il modulo puro e resta responsabile solo di fixture/osservazione/stampa. |
| `backend_dryrun_staging/test_local_weather_notice_dryrun.py` | Test aggiornati per importare la policy pura. |
| `LOCAL_WEATHER_NOTICE_ENGINE_AUDIT.md` | Registrata estrazione del modulo puro. |
| `BACKEND_DATA_STATE_CONTRACT.md` | Registrato il modulo puro come policy di laboratorio. |
| `backend_dryrun_staging/README.md` | Documentata la separazione tra report e policy. |

Decisioni:

- La policy notifiche locali non deve restare dentro il report.
- Il report puo usare fixture e backend sorgente; la policy pura no.
- `apply_notification_policy()` restituisce copie annotate e non muta i candidati in input.
- Il prossimo eventuale passaggio verso backend reale dovra portare questo modulo, non il report di laboratorio.

Verifiche:

```text
python -B backend_dryrun_staging\local_weather_notice_dryrun.py
Report OK

python -B -m unittest backend_dryrun_staging.test_local_weather_notification_policy backend_dryrun_staging.test_local_weather_notice_dryrun
Ran 10 tests
OK

python -B -m unittest discover backend_dryrun_staging
Ran 49 tests
OK
```

## Tranche 92 - Normalizzatore candidati meteo locali

File aggiornati:

| File | Ruolo |
| --- | --- |
| `backend_dryrun_staging/local_weather_notice_normalizer.py` | Modulo puro `raw notice -> normalized candidate`, con validazione localita/copy/fonte/evento/confidenza. |
| `backend_dryrun_staging/test_local_weather_notice_normalizer.py` | Test su copy senza localita, macro-zone, lessico allerta, fonte sconosciuta e soppressione da allerta ufficiale. |
| `backend_dryrun_staging/local_weather_notice_dryrun.py` | Il report ora passa da generatore vecchio -> normalizzatore -> policy pura. |
| `backend_dryrun_staging/local_weather_notification_policy.py` | La policy calcola la priorita se il candidato non la porta gia. |
| `backend_dryrun_staging/test_local_weather_notice_dryrun.py` | Aggiornato per copy normalizzata con localita e tracciamento `inserted_city`. |
| `LOCAL_WEATHER_NOTICE_ENGINE_AUDIT.md` | Documentato il normalizzatore candidati. |
| `BACKEND_DATA_STATE_CONTRACT.md` | Aggiunto contratto `local_weather_notice_candidate`. |
| `backend_dryrun_staging/README.md` | Documentata la catena raw -> normalizer -> policy. |

Decisioni:

- Il backend vecchio puo produrre frasi grezze; la UI 3.0.0 deve lavorare su candidati normalizzati.
- Macro-zone come `monti`, `pianura`, `costa`, `FVG` non sono localita valide per push personali.
- Le formule note del backend vecchio senza citta vengono normalizzate con `copy_normalizations=["inserted_city"]`.
- Le formule sconosciute senza citta vengono bloccate con `body_missing_city`.
- Fonti sconosciute diventano `low_confidence` e non entrano nella policy notificabile.
- Il normalizzatore non decide la notifica finale: produce solo `candidate_can_notify`.

Verifiche:

```text
python -B -m unittest backend_dryrun_staging.test_local_weather_notice_normalizer backend_dryrun_staging.test_local_weather_notification_policy backend_dryrun_staging.test_local_weather_notice_dryrun
Ran 16 tests
OK

python -B -m unittest discover backend_dryrun_staging
Ran 55 tests
OK

python -B backend_dryrun_staging\local_weather_notice_dryrun.py --format json
Report JSON OK
```

## Tranche 93 - Detector puro soglie meteo locali

File aggiornati:

| File | Ruolo |
| --- | --- |
| `backend_dryrun_staging/local_weather_notice_detector.py` | Modulo puro `city + weather snapshot -> raw notice candidate`, con soglie, evento, evidenza e supporto soppressione allerta ufficiale. |
| `backend_dryrun_staging/test_local_weather_notice_detector.py` | Test su caldo, pioggia, temporali/grandine, neve, ghiaccio, Bora/vento e sotto-soglia. |
| `backend_dryrun_staging/local_weather_notice_dryrun.py` | Il report non importa piu il backend sorgente: usa detector -> normalizzatore -> policy. |
| `backend_dryrun_staging/test_local_weather_notice_dryrun.py` | Test aggiornato per verificare la sorgente del report pure-detector. |
| `LOCAL_WEATHER_NOTICE_ENGINE_AUDIT.md` | Documentato il detector candidati e la catena fixture -> detector -> normalizzatore -> policy. |
| `BACKEND_DATA_STATE_CONTRACT.md` | Aggiunto contratto `local_weather_notice_detection` con soglie ed evidenza. |
| `backend_dryrun_staging/README.md` | Documentato detector, soglie e catena del dry-run locale. |

Decisioni:

- La lettura soglie non deve restare nascosta nel backend sorgente o nel report.
- Ogni candidato locale nasce da una soglia esplicita e porta `threshold` + `evidence`.
- Il detector non decide se notificare: produce solo raw candidate.
- Il normalizzatore resta responsabile di localita, copy, fonte e confidenza.
- La policy resta responsabile della decisione finale `can_notify`.
- Il dry-run locale ora e' ripetibile senza importare `main.py` del backend vecchio.

Verifiche:

```text
python -B -m unittest backend_dryrun_staging.test_local_weather_notice_detector backend_dryrun_staging.test_local_weather_notice_normalizer backend_dryrun_staging.test_local_weather_notification_policy backend_dryrun_staging.test_local_weather_notice_dryrun
Ran 26 tests
OK

python -B -m unittest discover backend_dryrun_staging
Ran 65 tests
OK

python -B backend_dryrun_staging\local_weather_notice_dryrun.py
Report OK
```

## Tranche 94 - Dry-run payload reali/read-only notifiche locali

File aggiornati:

| File | Ruolo |
| --- | --- |
| `backend_dryrun_staging/local_weather_payload_adapter.py` | Adattatore puro `payload bootstrap/snapshot -> city + weather + gap + segnali testuali`. |
| `backend_dryrun_staging/local_weather_real_payload_dryrun.py` | Dry-run da file JSON o URL read-only: adapter -> detector -> normalizzatore -> policy. |
| `backend_dryrun_staging/test_local_weather_payload_adapter.py` | Test su shape bootstrap reale, gap dati, segnali testuali e snapshot diretto. |
| `backend_dryrun_staging/test_local_weather_real_payload_dryrun.py` | Test end-to-end su payload con solo testo regionale, pioggia localizzata e soppressione da allerta ufficiale. |
| `LOCAL_WEATHER_NOTICE_ENGINE_AUDIT.md` | Documentata verifica payload reali/read-only e regola text signals diagnostici. |
| `BACKEND_DATA_STATE_CONTRACT.md` | Aggiunto contratto `local_weather_payload_audit`. |
| `backend_dryrun_staging/README.md` | Documentato comando dry-run per JSON salvati e URL read-only. |

Decisioni:

- Il testo regionale OSMER puo essere letto come segnale diagnostico, ma non genera push locale da solo.
- La push locale nasce solo da soglia numerica/localizzata passata dal detector.
- Il report mostra gap dati come `missing_hourly_next_12h` senza inventare fallback silenziosi.
- L'URL read-only e' ammesso solo per audit manuale: nessuna scrittura, nessun FCM, nessun workflow.
- Le allerte ufficiali presenti nel payload sopprimono i candidati locali coerenti.

Verifiche:

```text
python -B -m unittest backend_dryrun_staging.test_local_weather_payload_adapter backend_dryrun_staging.test_local_weather_real_payload_dryrun
Ran 7 tests
OK

python -B -m unittest discover backend_dryrun_staging
Ran 72 tests
OK

python -B backend_dryrun_staging\local_weather_real_payload_dryrun.py --url "http://127.0.0.1:5173/api/weather/bootstrap?city=Pordenone"
Report OK: payload Pordenone letto in sola lettura; segnali testuali diagnostici; candidato caldo generato da soglia numerica `feels_like >= 34 C`.
```

## Tranche 95 - Audit multi-citta payload meteo locali

File aggiornati:

| File | Ruolo |
| --- | --- |
| `backend_dryrun_staging/local_weather_real_payload_dryrun.py` | Aggiunti `--city`, `--base-url` e sintesi aggregata del report. |
| `backend_dryrun_staging/test_local_weather_real_payload_dryrun.py` | Test URL city encoding e sintesi report. |
| `backend_dryrun_staging/README.md` | Documentato comando multi-citta. |
| `LOCAL_WEATHER_NOTICE_ENGINE_AUDIT.md` | Registrato audit read-only su Pordenone, Udine, Trieste, Tarvisio e Lignano Sabbiadoro. |
| `BACKEND_DATA_STATE_CONTRACT.md` | Aggiornato output `local_weather_payload_audit` con `summary`. |

Decisioni:

- Il comando operativo per audit multi-citta e' `--city`, non una lista manuale di URL.
- La sintesi del report deve mostrare subito quanti payload, candidati e notificabili dry-run sono emersi.
- I segnali testuali regionali ripetuti tra localita restano diagnostici e non cambiano la decisione locale.

Verifiche:

```text
python -B backend_dryrun_staging\local_weather_real_payload_dryrun.py --city Pordenone --city Udine --city Trieste --city Tarvisio --city "Lignano Sabbiadoro"
Sintesi: payload=5, con candidati=1, senza notice=4, notice=1, notificabili dry-run=1

python -B -m unittest backend_dryrun_staging.test_local_weather_real_payload_dryrun backend_dryrun_staging.test_local_weather_payload_adapter
Ran 9 tests
OK
```

## Tranche 96 - Trigger caldo e numeri locali nel dry-run

File aggiornati:

| File | Ruolo |
| --- | --- |
| `backend_dryrun_staging/local_weather_notice_detector.py` | Aggiunti `trigger_source`, `trigger_value`, `trigger_unit` sui candidati caldo; evento corrente separato da picco orario futuro. |
| `backend_dryrun_staging/local_weather_notice_normalizer.py` | Il normalizzatore preserva i metadati trigger. |
| `backend_dryrun_staging/local_weather_payload_adapter.py` | Aggiunti `observed_at` e `numeric_snapshot` per spiegare soglie superate/non superate. |
| `backend_dryrun_staging/local_weather_real_payload_dryrun.py` | Report testuale con numeri locali e trigger candidato. |
| `backend_dryrun_staging/local_weather_notice_dryrun.py` | Report fixture con trigger candidato. |
| `backend_dryrun_staging/test_local_weather_notice_detector.py` | Test su caldo da percepita corrente e caldo da picco orario. |
| `backend_dryrun_staging/test_local_weather_notice_normalizer.py` | Test preservazione trigger. |
| `backend_dryrun_staging/test_local_weather_payload_adapter.py` | Test `observed_at` e `numeric_snapshot`. |
| `backend_dryrun_staging/test_local_weather_real_payload_dryrun.py` | Test che percepita corrente usa l'orario osservato, non lo slot futuro. |
| `LOCAL_WEATHER_NOTICE_ENGINE_AUDIT.md` | Aggiornata osservazione multi-citta: nessuna soglia locale numerica superata nel payload corrente. |
| `BACKEND_DATA_STATE_CONTRACT.md` | Documentati `trigger_*` e `numeric_snapshot`. |
| `backend_dryrun_staging/README.md` | Documentata regola trigger caldo. |

Decisioni:

- Una notifica caldo deve spiegare se nasce da `current_feels_like`, `current_temperature` o `hourly_temperature`.
- Se nasce dal dato corrente, l'evento usa `observed_at`; non deve ereditare l'orario dello slot futuro piu caldo.
- Il report deve mostrare i numeri locali anche quando non escono candidate.
- Nel giro read-only corrente nessuna delle cinque citta supera le soglie numeriche locali.

Verifiche:

```text
python -B -m unittest backend_dryrun_staging.test_local_weather_notice_detector backend_dryrun_staging.test_local_weather_notice_normalizer backend_dryrun_staging.test_local_weather_payload_adapter backend_dryrun_staging.test_local_weather_real_payload_dryrun backend_dryrun_staging.test_local_weather_notice_dryrun
Ran 33 tests
OK

python -B -m unittest discover backend_dryrun_staging
Ran 77 tests
OK

python -B backend_dryrun_staging\local_weather_real_payload_dryrun.py --city Pordenone --city Udine --city Trieste --city Tarvisio --city "Lignano Sabbiadoro"
Sintesi: payload=5, con candidati=0, senza notice=5, notice=0, notificabili dry-run=0
```

## Tranche 97 - Audit campi UI Bollettino da payload

File aggiornati:

| File | Ruolo |
| --- | --- |
| `backend_dryrun_staging/bulletin_display_payload_audit.py` | Audit read-only `payload bootstrap -> campi UI Bollettino`, con tabella fonte/stato/show/no-show. |
| `backend_dryrun_staging/test_bulletin_display_payload_audit.py` | Test su payload strutturato pronto, proiezione non XML, A1-A9 incompleto, fonte stale e allerta DPC diagnostica. |
| `BULLETIN_DATA_DISPLAY_AUDIT.md` | Documentata verifica campo per campo e risultato read-only Pordenone. |
| `BACKEND_DATA_STATE_CONTRACT.md` | Aggiunto contratto `bulletin_display_field_audit`. |
| `backend_dryrun_staging/README.md` | Documentato comando per payload salvati, URL read-only e `--city`. |

Decisioni:

- Il Bollettino deve essere verificabile campo per campo prima di qualunque collegamento live.
- Ogni riga audit porta `payload_path`, `source`, `state`, `safe_to_show` e `reason`.
- Il testo ufficiale puo essere mostrato se arriva da OSMER official/normalizzato.
- La mappa nativa si mostra solo con `structured_xml`, A1-A9 complete e dato non stale.
- `official_projected` resta fuori dalla mappa nativa.
- DPC/no-active diagnostico non produce banner allerta.
- L'attendibilita si mostra solo se la mappa nativa dello stesso giorno e' usabile.

Verifiche:

```text
python -B -m unittest backend_dryrun_staging.test_bulletin_display_payload_audit
Ran 7 tests
OK

python -B backend_dryrun_staging\bulletin_display_payload_audit.py --city Pordenone
righe=24, show=23, no-show=1, testi=5, mappe=5
no-show corretto: alert.banner diagnostico DPC/no-active non verificato come verde regionale FVG
```

## Tranche 98 - Confronto audit dati e UI reale Bollettino

File aggiornati:

| File | Ruolo |
| --- | --- |
| `frontend/src/features/bulletin/bulletinViewModel.js` | Gating UI allineato all'audit: `reliability`, badge mappa, marker e summary strutturata usano dati strutturati solo se `canRenderNativeMap=true`. |
| `frontend/src/features/bulletin/bulletinViewModel.test.js` | Test anti-regressione per stale, `official_projected` e A1-A9 parziale: niente attendibilita o mappa quando la mappa nativa non e' ammessa. |
| `BULLETIN_DATA_DISPLAY_AUDIT.md` | Documentato confronto audit dati/UI e limite QA sul browser integrato. |

Decisioni:

- La UI non deve mostrare `Attendibilita` quando la mappa nativa non e' renderizzabile.
- Un giorno strutturato non renderizzabile puo restare nel modello come diagnostica, ma non deve alimentare campi visibili.
- `official_projected`, stale/unavailable e A1-A9 parziale restano fuori da mappa, badge e attendibilita.
- DPC/no-active diagnostico resta senza banner allerta, coerente con Tranche 97.

Verifica read-only payload:

```text
python -B backend_dryrun_staging\bulletin_display_payload_audit.py --city Pordenone
righe=24, show=23, no-show=1, testi=5, mappe=5
```

Verifiche:

```text
npm run test
47 file, 311 test OK

npm run lint
OK

npm run build
OK

python -B -m unittest discover backend_dryrun_staging
Ran 84 tests
OK
```


## Tranche 99 - Correzione tab giorni Bollettino

File aggiornati:

| File | Ruolo |
| --- | --- |
| `frontend/src/features/bulletin/bulletinViewModel.js` | Aggiunta `tabLabel` derivata dalla data reale del giorno; le tab non dipendono piu' dai weekday della fixture. |
| `frontend/src/features/bulletin/BulletinView.jsx` | La tab bar usa `day.tabLabel` quando presente, mantenendo fallback solo per compatibilita. |
| `frontend/src/features/bulletin/bulletinViewModel.test.js` | Test anti-regressione su date reali 27/06-01/07 e weekday IT/FUR. |
| `BULLETIN_DATA_DISPLAY_AUDIT.md` | Documentata verifica browser dopo riavvio del browser integrato. |

Decisioni:

- "Oggi" resta label funzionale.
- Le tab successive usano il weekday calcolato da `forecastDate`, non la fixture.
- La UI visualizza solo la label gia risolta dal view model.

Verifica browser:

```text
URL: http://127.0.0.1:5173/?tab=bulletin
tab: Oggi, Domenica, Lunedi, Martedi, Mercoledi
console error/warn: 0
Oggi -> sabato 27 giugno -> Poco nuvoloso
Domenica -> domenica 28 giugno -> Poco nuvoloso
Lunedi -> lunedi 29 giugno -> Poco nuvoloso
Martedi -> tendenza per martedi 30 giugno -> Temporale
Mercoledi -> tendenza per mercoledi 01 luglio -> Coperto
```

Verifiche:

```text
npx vitest run --configLoader native src/features/bulletin/bulletinViewModel.test.js
1 file, 11 test OK

npm run test
47 file, 313 test OK

npm run lint
OK

npm run build
OK

python -B -m unittest discover backend_dryrun_staging
Ran 84 tests
OK
```

## Tranche 100 - Coerenza sintesi e mappa Bollettino

File aggiornati:

| File | Ruolo |
| --- | --- |
| `frontend/src/features/bulletin/bulletinViewModel.js` | Allineamento per data tra giorni ufficiali OSMER e giorni modellistici; sintesi visibile prioritaria da OSMER/testo ufficiale. |
| `frontend/src/features/bulletin/bulletinViewModel.test.js` | Test anti-regressione su modello slittato e mappa agganciata per data. |
| `BULLETIN_DATA_DISPLAY_AUDIT.md` | Documentato audit browser sui cinque giorni del Bollettino. |

Problema trovato:

- `forecast.forecast` puo essere slittato di un giorno rispetto a `forecast.official.it.forecasts`;
- la UI usava `modelDay.condition` per indice;
- questo poteva produrre titolo/sintesi incoerente, ad esempio `Coperto` su un testo OSMER con temporali.

Decisioni:

- Il Bollettino e' guidato da OSMER: testo ufficiale e mappa strutturata hanno priorita.
- Il dato modellistico locale puo integrare solo se la `date` coincide con il giorno ufficiale.
- La mappa nativa si aggancia a `forecastDate`, non alla posizione dell'array.

Verifica browser:

```text
URL: http://127.0.0.1:5173/?tab=bulletin
console error/warn: 0
Oggi -> sabato 27 giugno -> Tempo stabile -> Attendibilita 73%
Domenica -> domenica 28 giugno -> Sole e nubi -> Attendibilita 73%
Lunedi -> lunedi 29 giugno -> Sole e nubi -> Attendibilita 73%
Martedi -> tendenza per martedi 30 giugno -> Sole e nubi -> Attendibilita 69%
Mercoledi -> tendenza per mercoledi 01 luglio -> Temporali possibili -> Attendibilita 60%
```

Verifiche:

```text
npx vitest run --configLoader native src/features/bulletin/bulletinViewModel.test.js
1 file, 13 test OK

npm run test
47 file, 315 test OK

npm run lint
OK

npm run build
OK

python -B -m unittest discover backend_dryrun_staging
Ran 84 tests
OK
```

## Tranche 101 - Label Oggi vincolata alla data corrente

File aggiornati:

| File | Ruolo |
| --- | --- |
| `frontend/src/features/bulletin/bulletinViewModel.js` | `tabLabel` della prima tab calcolata confrontando `forecastDate` con la data locale corrente. |
| `frontend/src/features/bulletin/bulletinViewModel.test.js` | Test su avanzamento giorno e payload vecchio dopo mezzanotte. |
| `BULLETIN_DATA_DISPLAY_AUDIT.md` | Documentata regola anti-stale per `Oggi`. |

Decisioni:

- `Oggi` non e' piu' legato all'indice 0.
- Se la prima previsione e' del giorno corrente, resta `Oggi`.
- Se la prima previsione e' del giorno precedente o di un'altra data, mostra il weekday reale.
- Il view model accetta `now` per testare il passaggio di giorno senza alterare l'orologio del browser.

Verifiche mirate:

```text
now=2026-06-28, forecastDate=2026-06-28 -> Oggi
now=2026-06-28, forecastDate=2026-06-27 -> Sabato
npx vitest run --configLoader native src/features/bulletin/bulletinViewModel.test.js
1 file, 15 test OK

npm run test
47 file, 317 test OK

npm run lint
OK

npm run build
OK

python -B -m unittest discover backend_dryrun_staging
Ran 84 tests
OK
```

Verifica browser:

```text
URL: http://127.0.0.1:5173/?tab=bulletin
tab attiva: Oggi
data riepilogo: sabato 27 giugno
console error/warn: 0
```

Limite QA:

- screenshot browser non acquisito: il browser integrato ha fallito con `failed to write kernel assets: Impossibile trovare il percorso specificato`;
- controllo effettuato con confronto deterministico payload -> view model -> test.

## Tranche 102 - Audit giorno per giorno Bollettino e strumento display

File aggiornati:

| File | Ruolo |
| --- | --- |
| `backend_dryrun_staging/bulletin_display_payload_audit.py` | Allineata la lettura `source.updatedLabel` alla priorita' effettiva della UI. |
| `backend_dryrun_staging/test_bulletin_display_payload_audit.py` | Aggiunto test anti-regressione su fallback `osmer_structured.data_emissione`. |
| `BULLETIN_DATA_DISPLAY_AUDIT.md` | Documentato audit giorno per giorno e falso disallineamento corretto nello strumento. |

Audit browser:

```text
URL: http://127.0.0.1:5173/?tab=bulletin
console error/warn: 0

Oggi -> Tempo stabile -> Attendibilita 73% -> mappa 9/9
Domenica -> Sole e nubi -> Attendibilita 73% -> mappa 9/9
Lunedi -> Sole e nubi -> Attendibilita 73% -> mappa 9/9
Martedi -> Sole e nubi -> Attendibilita 69% -> mappa 9/9
Mercoledi -> Temporali possibili -> Attendibilita 60% -> mappa 9/9
```

Decisione:

- nessuna modifica UI;
- nessuna modifica parser;
- il problema trovato era nello strumento di audit, che leggeva `forecast.official.it.forecasts[0].emission` mentre la UI usa `osmer_structured.data_emissione` quando non ci sono `updated_at/updatedAt` ufficiali.

Verifiche:

```text
python -B -m unittest backend_dryrun_staging.test_bulletin_display_payload_audit
Ran 8 tests
OK

python -B -m unittest discover backend_dryrun_staging
Ran 85 tests
OK

git diff --check
OK
```

## Tranche 103 - Quinto giorno Bollettino non ancora emesso

File aggiornati:

| File | Ruolo |
| --- | --- |
| `frontend/src/features/bulletin/bulletinViewModel.js` | Riserva il quinto slot di calendario OSMER e lo marca `pending_official` se non e' ancora emesso. |
| `frontend/src/features/bulletin/bulletinViewModel.test.js` | Test anti-regressione: il quinto giorno resta Giovedi 02/07/2026 e non viene sostituito dal modello locale. |
| `frontend/src/features/bulletin/BulletinMap.jsx` | Stato pending mappa con copy semplice, senza warning tecnico. |
| `frontend/src/features/bulletin/BulletinView.jsx` | Copy mappa pending IT/FUR. |
| `frontend/src/features/bulletin/bulletin.css` | Variante visiva discreta per mappa pending. |
| `backend_dryrun_staging/bulletin_display_payload_audit.py` | Audit allineato: quinto giorno pending, non modellistico. |
| `backend_dryrun_staging/test_bulletin_display_payload_audit.py` | Test dry-run sul quinto giorno non ancora emesso. |
| `BULLETIN_DATA_DISPLAY_AUDIT.md` | Documentata la regola di prodotto e le verifiche. |

Decisioni:

- il quinto giorno puo' esistere come tab anche quando OSMER non lo ha ancora emesso;
- in quel caso si mostra `Non ancora emesso`, non una previsione modellistica;
- mappa, icone e attendibilita del giorno pending restano spente;
- questa e' una condizione normale "in giornata", non un errore fonte.

Verifica browser:

```text
URL: http://127.0.0.1:5173/?tab=bulletin
tab visibili: Oggi, Lunedi, Martedi, Mercoledi, Giovedi
Giovedi:
  titolo: Non ancora emesso
  testo: Bollettino non ancora emesso.
  warning mappa: Non ancora emesso
  icone mappa: 0
console error/warn: 0
```

Verifiche:

```text
npx vitest run --configLoader native src/features/bulletin/bulletinViewModel.test.js
1 file, 16 test OK

npx vitest run --configLoader native
47 file, 318 test OK

npm run lint
OK

npm run build
OK

python -B -m unittest backend_dryrun_staging.test_bulletin_display_payload_audit
Ran 9 tests
OK

python -B -m unittest discover backend_dryrun_staging
Ran 86 tests
OK
```

## Tranche 104 - Calendario FUR Bollettino allineato a OSMER

File aggiornati:

| File | Ruolo |
| --- | --- |
| `frontend/src/features/bulletin/bulletinViewModel.js` | Separato calendario IT/OSMER da testi localizzati FUR. |
| `frontend/src/features/bulletin/bulletinViewModel.test.js` | Test su payload FUR con campo `date` sfalsato e quinto giorno pending. |
| `backend_dryrun_staging/bulletin_display_payload_audit.py` | Audit allineato alla stessa regola calendario/testo. |
| `backend_dryrun_staging/test_bulletin_display_payload_audit.py` | Test dry-run FUR sul calendario OSMER e quinto giorno pending. |
| `BULLETIN_DATA_DISPLAY_AUDIT.md` | Documentata diagnosi, decisione e verifica browser. |

Decisioni:

- FUR non decide il calendario del Bollettino;
- la finestra giorni deriva da IT/OSMER strutturato;
- i testi FUR sono localizzazione parallela e vengono usati per posizione quando presenti;
- il quinto giorno in FUR resta visibile come `Joibe` con stato `No ancjemò publicât`.

Verifica browser:

```text
lingua: FUR
tab visibili: Vuê, Lunis, Martars, Miercus, Joibe
Vuê: domenie 28 Jugn, testo FUR corretto
Joibe: Joibe 2 Lui, No ancjemò publicât, 0 icone mappa
console error/warn: 0
```

Verifiche:

```text
npx vitest run --configLoader native
47 file, 319 test OK

npm run lint
OK

npm run build
OK

python -B -m unittest discover backend_dryrun_staging
Ran 87 tests
OK
```

## Tranche 105 - eventWeatherFit come ranking nascosto Home

File aggiornati:

| File | Ruolo |
| --- | --- |
| `frontend/src/features/events/eventWeatherFit.js` | Modulo puro per fit meteo-evento, senza copy utente. |
| `frontend/src/features/events/eventWeatherFit.test.js` | Regressioni su pioggia, temporale, vento/Bora, indoor/outdoor e no-weather. |
| `frontend/src/features/home/homeViewModel.js` | Usa il fit solo come score nel ranking del teaser Eventi. |
| `frontend/src/features/home/homeViewModel.test.js` | Verifica che il ranking cambi senza esporre reason/copy nella UI. |
| `AUDIT_CHECKLIST.md` | Tracciato audit Eventi/meteo. |
| `MIGRATION_MAP.md` | Tracciata decisione: criterio riusato, vecchio file non copiato. |

Decisioni:

- il vecchio `eventWeatherFit.js` non viene copiato integralmente;
- la card Eventi in Home resta un teaser, non una sintesi meteo;
- la pagina Eventi non riceve pill o consigli meteo;
- notifiche Eventi escluse da questa tranche;
- vento/Bora e meteo delicato influenzano solo il ranking interno.

Verifica mirata:

```text
npm run test -- --run src/features/events/eventWeatherFit.test.js src/features/home/homeViewModel.test.js
2 file, 29 test OK
```

## Tranche 106 - Audit GPS/reverse geocoding

File aggiornati:

| File | Ruolo |
| --- | --- |
| `frontend/src/domain/geo/autoLocationPolicy.js` | Aggiunta decisione qualita GPS/native come funzione pura. |
| `frontend/src/domain/geo/autoLocationPolicy.test.js` | Regressioni su fast, confirm, stale/imprecise e payload incompleti. |
| `frontend/src/app/appLocation.js` | Aggiunta lettura/scrittura flag legacy `autoLocationEnabled`. |
| `frontend/src/app/appLocation.test.js` | Test storage auto-location. |
| `frontend/src/services/reverseLocation.js` | Nuovo servizio reverse geocoding con cache device e normalizzazione FVG. |
| `frontend/src/services/reverseLocation.test.js` | Test URL, cache, fetch, FVG e fallback errore. |
| `AUDIT_CHECKLIST.md` | Tracciato audit GPS/reverse e limiti della tranche. |
| `MIGRATION_MAP.md` | Mappato cosa viene dalla vecchia app e cosa resta fuori. |
| `UI3_RUNTIME_DATA_INVENTORY.md` | Inventario aggiornato: moduli pronti, UI/permessi non collegati. |

Decisioni:

- non copiato il flusso `handleAutoDetect()` dentro la shell UI 3;
- reverse geocoding separato in servizio testabile;
- cache legacy `locationReverseCache:v1` mantenuta con coordinate a 3 decimali;
- risultati fuori FVG espliciti con `insideFvg: false`;
- errore reverse esplicito con `ok: false`, senza fingere un comune valido;
- nessun permesso GPS richiesto e nessun cambio automatico localita in questa tranche.

Verifica mirata:

```text
npm run test -- --run src/domain/geo/autoLocationPolicy.test.js src/app/appLocation.test.js src/services/reverseLocation.test.js
3 file, 21 test OK
```

## Tranche 107 - UX consenso GPS e reverse live

File aggiornati:

| File | Ruolo |
| --- | --- |
| `frontend/src/services/deviceLocation.js` | Servizio coordinate browser dietro chiamata esplicita. |
| `frontend/src/services/deviceLocation.test.js` | Test su unsupported, coordinate finite, errori e missing coordinates. |
| `frontend/src/app/App.jsx` | Orchestrazione tap posizione -> coordinate -> reverse -> update localita se FVG. |
| `frontend/src/app/AppRoutes.jsx` | Passaggio stato posizione e handler alla route settings. |
| `frontend/src/features/settings/SettingsView.jsx` | Riga `Posizione dispositivo` con azione `Usa posizione` e stati. |
| `frontend/src/features/settings/settings.css` | Stato busy/spinner per azione posizione. |
| `AUDIT_CHECKLIST.md` | Tracciato consenso GPS e guardrail. |
| `MIGRATION_MAP.md` | Mappato import controllato dal flusso vecchio. |

Decisioni:

- la posizione non parte in Home e non parte all'avvio;
- il permesso posizione viene chiesto solo dopo tap su `Usa posizione`;
- se reverse fallisce o la posizione non e' FVG, la localita attiva resta invariata;
- `autoLocationEnabled` viene salvato `true` solo dopo reverse FVG riuscito;
- Android bridge e auto-check foreground restano fuori.

Verifica mirata:

```text
npm run test -- --run src/services/deviceLocation.test.js src/services/reverseLocation.test.js src/app/appLocation.test.js
3 file, 18 test OK

npm run lint
OK

npm run test -- --run
59 file, 411 test OK

npm run build
OK
```

Verifica browser/proxy:

```text
Browser Opzioni:
Posizione dispositivo / Non attiva / Usa posizione

Reverse proxy:
GET http://127.0.0.1:5173/api/location/reverse?lat=45.9415&lon=13.6221
-> Gorizia / Friuli-Venezia Giulia

Nota:
permesso GPS reale non accettato nel browser; richiede consenso esplicito utente.
```

## Tranche 108 - Separazione localita visualizzata e GPS dispositivo

File aggiornati:

| File | Ruolo |
| --- | --- |
| `frontend/src/app/App.jsx` | Cambio manuale comune non cancella piu l'ultima posizione dispositivo rilevata. |
| `frontend/src/features/settings/SettingsView.jsx` | In Opzioni la localita viene mostrata come `Comune visualizzato`; il GPS resta `Posizione dispositivo`. |

Decisioni:

- `Comune visualizzato` e' il contesto che l'utente sta guardando nell'app;
- `Posizione dispositivo` e' dove si trova il telefono, utile anche per funzioni future;
- se l'utente e' a Pordenone ma sceglie Trieste, il GPS non deve riportare automaticamente la app a Pordenone;
- il cambio manuale spegne solo la modalita `meteo segue GPS`, non invalida il dato GPS gia rilevato;
- il GPS non interviene in automatico su Eventi, Home o Bollettino.

Verifica mirata:

```text
npm run test -- --run src/services/deviceLocation.test.js src/services/reverseLocation.test.js src/app/appLocation.test.js
3 file, 18 test OK

npm run lint
OK
```

## Tranche 118 - Localita globale: ingresso UX contestuale

File aggiornati:

| File | Ruolo |
| --- | --- |
| `frontend/src/ui/components/LocationContext.jsx` | Nuovo componente condiviso per mostrare localita + azione testuale `Cambia`. |
| `frontend/src/ui/layout/AppHeader.jsx` | Rimossa la lente generica dalla testata: restano lingua e impostazioni. |
| `frontend/src/ui/layout/layout.css` | Stile condiviso per il contesto localita e placeholder Scopri. |
| `frontend/src/app/AppRoutes.jsx` | Passa `onLocationSearchOpen` alla Home, mantenendo la localita globale nella shell. |
| `frontend/src/features/home/HomeView.jsx` | Collega l'apertura del bottom sheet localita alla hero. |
| `frontend/src/features/home/HomeWeatherHero.jsx` | Mostra `Cambia` accanto alla localita nella hero meteo. |
| `frontend/src/features/home/homeViewModel.js` | Copy IT/FUR `Cambia` / `Cambie` per la Home. |
| `frontend/src/features/home/home.css` | Stile testuale leggero per `Cambia` sulla hero. |
| `frontend/src/features/lab/DiscoverLabView.jsx` | Predispone `A Pordenone · Cambia` nel placeholder Scopri. |

Decisioni:

- la localita resta una sola e globale per tutta l'app;
- il pulsante `Cambia` apre sempre lo stesso bottom sheet globale;
- Home, Eventi e Scopri mostrano la localita perche' dipendono chiaramente dal comune attivo;
- il Bollettino non mostra ancora la localita: la sezione e' OSMER ufficiale FVG e l'eventuale localizzazione va ragionata dopo, senza far sembrare il bollettino "di Pordenone";
- Open-Meteo resta fuori da questa tranche.

Verifica:

```text
Browser integrato:
- Home: header senza lente, `Pordenone` + `Cambia`, click apre `Cambia localita`.
- Eventi: `Vicino a Pordenone` + `Cambia`, click apre `Cambia localita`.
- Scopri: `A Pordenone` + `Cambia`, click apre `Cambia localita`.
- Bollettino: nessun contesto localita visibile.

npm run lint
OK

npm run test
59 file, 411 test OK
```

## Tranche 109 - Audit permessi GPS e notifiche

File aggiornati:

| File | Ruolo |
| --- | --- |
| `PERMISSIONS_GPS_PUSH_AUDIT.md` | Documento audit dedicato per gate Android GPS/notifiche. |
| `AUDIT_CHECKLIST.md` | Tracciato audit e decisione UX corretta. |

Fonti lette nella vecchia app:

- `frontend/src/App.jsx`;
- `frontend/src/utils/autoLocationPolicy.js`;
- `frontend/src/utils/pushNotifications.js`;
- `frontend/android/app/src/main/java/com/meteofriul/app/MainActivity.java`;
- `frontend/android/app/src/main/AndroidManifest.xml`;
- `frontend/capacitor.config.json`;
- `backend/main.py`;
- `docs/codex-startup-note.md`;
- `docs/manuale-operativo-tab.md`.

Decisioni:

- per APK/Android questa tranche supera il precedente flusso laboratorio `Usa posizione` da Opzioni come gate iniziale;
- apertura Android: prompt posizione nativo come primo gate;
- dopo posizione accettata/rifiutata e localita risolta/scelta: prompt notifiche nativo;
- nessuna finestra custom per consenso GPS/notifiche;
- nessun push reale collegato in questa tranche;
- il flusso `Usa posizione` browser in UI3 resta laboratorio/web, non gate Android finale.

Verifica:

```text
Audit read-only: nessun test runtime necessario, nessun invio push, nessuna modifica backend.
```

## Tranche 110 - Contratto startup Android GPS/notifiche

File aggiornati:

| File | Ruolo |
| --- | --- |
| `frontend/src/domain/startup/androidPermissionGate.js` | Modulo puro per decidere stati/azioni del gate Android GPS -> localita -> notifiche. |
| `frontend/src/domain/startup/androidPermissionGate.test.js` | Regressioni su primo GPS, localita manuale, GPS negato, fallimenti temporanei e notifiche. |
| `AUDIT_CHECKLIST.md` | Tracciato contratto e limiti della tranche. |

Decisioni:

- il contratto non chiede permessi reali e non importa Capacitor;
- il contratto non registra token e non invia push;
- localita gia presente non salta davanti al prompt GPS nativo: su Android il GPS resta il primo gate;
- notifiche native ammesse solo dopo localita risolta da GPS o localita manuale scelta;
- `startupNotificationsAsked:v1` e `weatherAlertsEnabled` restano guardrail anti-richiesta ripetuta;
- `autoLocationEnabled` su primo avvio Android resta attivo salvo valore storage esplicito `false`.

Verifica mirata:

```text
npm run test -- --run src/domain/startup/androidPermissionGate.test.js src/domain/geo/autoLocationPolicy.test.js src/services/deviceLocation.test.js src/services/reverseLocation.test.js src/app/appLocation.test.js
5 file, 37 test OK
```

## Tranche 111 - Audit runtime cache e refresh

File aggiornati:

| File | Ruolo |
| --- | --- |
| `RUNTIME_REFRESH_CACHE_AUDIT.md` | Audit dedicato su cache, refresh, pull-to-refresh, foreground e stati non raggiungibili. |
| `AUDIT_CHECKLIST.md` | Tracciato audit e limiti della tranche. |

Fonti lette:

- vecchia app `frontend/src/App.jsx`;
- vecchia app `frontend/src/App.css`;
- UI3 `frontend/src/features/home/homeDataController.js`;
- UI3 `frontend/src/features/bulletin/bulletinDataController.js`;
- UI3 `frontend/src/features/events/eventsDataController.js`;
- test UI3 dei controller Home/Bollettino/Eventi.

Decisioni:

- la app deve idratarsi da cache prima della rete;
- il refresh non deve svuotare dati validi;
- `Dati non raggiungibili` serve solo quando manca una cache utile;
- il Bollettino accetta cache solo se contiene testo ufficiale OSMER;
- Eventi non scrive in cache payload backend `refreshing` o `partial`;
- pull-to-refresh va progettato dopo un modulo refresh puro, non copiando la gesture vecchia dentro la shell.

Verifica:

```text
Audit/documentazione: nessun collegamento runtime, nessun test runtime necessario in questa tranche.
```

## Tranche 112 - Contratto runtime refresh/cache

File aggiornati:

| File | Ruolo |
| --- | --- |
| `frontend/src/domain/runtime/runtimeRefreshPolicy.js` | Modulo puro per decisioni cache, refresh, stale, unreachable, foreground e Eventi pending. |
| `frontend/src/domain/runtime/runtimeRefreshPolicy.test.js` | Test sulle regole runtime prima del collegamento shell. |
| `AUDIT_CHECKLIST.md` | Tracciato contratto e limiti della tranche. |

Decisioni:

- la cache utile idrata prima della rete;
- un refresh fallito non svuota dati visibili;
- `Dati non raggiungibili` si usa solo senza dati utili;
- una risposta di localita non corrente viene ignorata;
- payload Eventi `refreshing` o `partial` non entra in cache;
- foreground refresh resta throttled e inattivo con pagina nascosta.

Verifica mirata:

```text
npm run test -- --run src/domain/runtime/runtimeRefreshPolicy.test.js src/features/home/homeDataController.test.js src/features/bulletin/bulletinDataController.test.js src/features/events/eventsDataController.test.js
4 file, 33 test OK
```

## Tranche 113 - Collegamento shell runtime refresh/cache

File aggiornati:

| File | Ruolo |
| --- | --- |
| `frontend/src/app/App.jsx` | Usa la policy runtime per timer, foreground, online, focus e refresh forzati. |
| `frontend/src/domain/runtime/runtimeRefreshPolicy.js` | Aggiunge `shouldRunRuntimeRefresh()` e costante intervallo verifica meteo. |
| `frontend/src/domain/runtime/runtimeRefreshPolicy.test.js` | Copre force refresh, throttle e input non valido. |
| `AUDIT_CHECKLIST.md` | Traccia collegamento e limiti rimasti. |

Decisioni:

- `App.jsx` non decide piu a mano il throttle foreground;
- `force=true` resta ammesso per timer, cambio localita e GPS;
- pagina nascosta blocca i refresh non forzati;
- le route non cambiano modello: continuano a idratarsi da cache e a refreshare tramite controller;
- pull-to-refresh, reset cache e feedback UI restano fuori.

Verifica mirata:

```text
npm run test -- --run src/domain/runtime/runtimeRefreshPolicy.test.js
1 file, 11 test OK

npm run lint
OK
```

## Tranche 114 - Pull-to-refresh controllato

File aggiornati:

| File | Ruolo |
| --- | --- |
| `frontend/src/domain/runtime/pullRefreshPolicy.js` | Modulo puro per soglie, target esclusi e decisione refresh. |
| `frontend/src/domain/runtime/pullRefreshPolicy.test.js` | Regressioni su top scroll, target protetti, swipe orizzontale e trigger. |
| `frontend/src/ui/layout/AppShell.jsx` | Collega la gesture allo scroll principale e chiama il refresh shell. |
| `frontend/src/ui/layout/layout.css` | Indicatore pull-to-refresh a overlay senza spostare contenuti. |
| `frontend/src/app/App.jsx` | Passa il refresh controllato alla shell. |
| `frontend/src/app/uiShellCopy.js` | Microcopy IT/FUR per indicatore. |
| `AUDIT_CHECKLIST.md` | Traccia collegamento e limiti rimasti. |

Decisioni:

- il gesto parte solo con scroll principale in alto;
- non parte su header, bottom nav, bottoni, input, tab, mappa bollettino o location sheet;
- lo swipe orizzontale viene cancellato;
- il rilascio oltre soglia emette `requestRuntimeRefresh({ force: true, source: "pull" })`;
- i dati visibili restano nelle route e nei controller, non vengono svuotati dalla gesture;
- l'indicatore e' temporaneo e non modifica il layout.

Verifica mirata:

```text
npm run test -- --run src/domain/runtime/pullRefreshPolicy.test.js src/domain/runtime/runtimeRefreshPolicy.test.js src/app/uiShellCopy.test.js
3 file, 19 test OK

npm run lint
OK
```

## Tranche 115 - Feedback pull-to-refresh leggibile

File aggiornati:

| File | Ruolo |
| --- | --- |
| `frontend/src/ui/layout/AppShell.jsx` | Attende il completamento del refresh route prima di chiudere l'indicatore. |
| `frontend/src/ui/layout/layout.css` | Usa icona refresh classica e stato visivo piu stabile. |
| `frontend/src/app/App.jsx` | Espone una promise di refresh con timeout guardrail. |
| `frontend/src/app/AppRoutes.jsx` | Segnala alla shell quando Home, Bollettino o Eventi hanno finito il refresh. |
| `frontend/src/app/uiShellCopy.js` | Copy IT/FUR `Sto aggiornando` / `O soi daûr a inzornâ`. |
| `frontend/src/app/uiShellCopy.test.js` | Regressioni copy. |
| `frontend/src/domain/runtime/pullRefreshPolicy.js` | Feedback minimo 1400ms e distanza rilasciata stabile. |
| `frontend/src/domain/runtime/pullRefreshPolicy.test.js` | Regressione distanza post-rilascio. |
| `frontend/src/domain/runtime/runtimeRefreshPolicy.js` | Timeout completamento refresh 8000ms. |
| `AUDIT_CHECKLIST.md` | Tracciato UX e limiti rimasti. |

Decisioni:

- l'indicatore non sparisce piu subito dopo il rilascio;
- resta in `Sto aggiornando` finche la route attiva segnala completamento, con minimo visivo;
- sulle route senza refresh dati viene chiuso subito, ma sempre con minimo visivo;
- il timeout evita indicatori bloccati se una route non risponde;
- resta fuori il messaggio finale esplicito `Aggiornato` o `Dati non raggiungibili`.

Verifica:

```text
npm run test -- --run src/domain/runtime/pullRefreshPolicy.test.js src/domain/runtime/runtimeRefreshPolicy.test.js src/app/uiShellCopy.test.js
3 file, 19 test OK

npm run lint
OK

Browser: markup pull-to-refresh presente, icona RefreshCw presente, copy a riposo "Trascina per aggiornare".
```

## Tranche 116 - Esito pull-to-refresh esplicito

File aggiornati:

| File | Ruolo |
| --- | --- |
| `frontend/src/domain/runtime/pullRefreshPolicy.js` | Aggiunti stati `success`/`failed`, durata risultato e mapping puro da esito refresh a feedback UI. |
| `frontend/src/domain/runtime/pullRefreshPolicy.test.js` | Regressioni su mapping `settled` -> `success` e `timeout` -> `failed`. |
| `frontend/src/ui/layout/AppShell.jsx` | Mostra `Caricamento`, poi `Aggiornato` o `Fallito` per un tempo leggibile. |
| `frontend/src/ui/layout/layout.css` | Rotazione solo in caricamento, colore success/failure dai token esistenti. |
| `frontend/src/app/App.jsx` | Risolve la promise runtime refresh come `settled` o `failed` in base all'esito route. |
| `frontend/src/app/AppRoutes.jsx` | Home, Bollettino ed Eventi propagano `{ ok }` alla shell invece di chiudere sempre come successo. |
| `frontend/src/app/uiShellCopy.js` | Copy IT/FUR dei tre stati finali. |
| `frontend/src/app/uiShellCopy.test.js` | Regressioni copy IT/FUR. |
| `AUDIT_CHECKLIST.md` | Tracciata chiusura dello stato finale esplicito. |
| `MIGRATION_MAP.md` | Aggiornato il contratto runtime refresh UI 3. |

Decisioni:

- l'utente vede sempre una sequenza comprensibile: caricamento, esito, rientro;
- `Aggiornato` non viene mostrato se la route ritorna errore senza dati utili o se scatta il timeout;
- `Fallito` resta una parola corta, standard e traducibile;
- la distinzione futura tra `Aggiornato` e `Gia aggiornato` richiede un esito `changed` non ancora disponibile.

Verifica:

```text
npm run test -- --run src/domain/runtime/pullRefreshPolicy.test.js src/domain/runtime/runtimeRefreshPolicy.test.js src/app/uiShellCopy.test.js
3 file, 20 test OK

npm run test -- --run
59 file, 409 test OK

npm run lint
OK

npm run build
OK

Browser integrato:
pagina impostazioni montata, nessun warning/error console, indicatore a riposo presente.
Il drag desktop del browser non emette eventi touch, quindi il gesto reale resta da verificare su APK/emulatore.
```

## Tranche 117 - Esito refresh senza demolire cache utile

File aggiornati:

| File | Ruolo |
| --- | --- |
| `frontend/src/domain/runtime/runtimeRefreshPolicy.js` | Policy centralizzata per distinguere errore vuoto da errore con dati visibili non stale. |
| `frontend/src/domain/runtime/runtimeRefreshPolicy.test.js` | Regressioni: cache fresca visibile non fallisce, cache `isStale` non viene trattata come successo. |
| `frontend/src/app/AppRoutes.jsx` | Usa la policy runtime invece di una scorciatoia locale sugli errori. |

Decisioni:

- assenza rete + bollettino utile gia scaricato oggi: feedback non distruttivo;
- assenza rete + bollettino passato/scaduto (`isStale`): non viene considerato dato buono;
- `Fallito` resta riservato a timeout, promise respinta o refresh senza dati utili visibili.

Verifica:

```text
npm run test -- --run src/domain/runtime/runtimeRefreshPolicy.test.js src/domain/runtime/pullRefreshPolicy.test.js src/app/uiShellCopy.test.js
3 file, 22 test OK

npm run lint
OK
```

## Tranche 119 - Ripresa audit permessi Android GPS/notifiche

File aggiornati:

| File | Ruolo |
| --- | --- |
| `PERMISSIONS_GPS_PUSH_AUDIT.md` | Ripresa audit 2026-06-30: stato UI3 corrente, vecchia app riletta, decisione aggiornata e prossima tranche. |
| `AUDIT_CHECKLIST.md` | Tracciata ripresa audit permessi Android GPS/notifiche. |

Fonti rilette nella vecchia app:

- `frontend/android/app/src/main/AndroidManifest.xml`;
- `frontend/android/app/src/main/java/com/meteofriul/app/MainActivity.java`;
- `frontend/src/App.jsx`;
- `frontend/src/utils/autoLocationPolicy.js`;
- `frontend/src/utils/pushNotifications.js`;
- `frontend/capacitor.config.json`;
- `frontend/package.json`;
- `docs/push-notifications-readiness.md`;
- `docs/local-weather-notifications.md`.

Decisioni:

- UI3 ha gia il contratto puro `androidPermissionGate`, ma non ha ancora Android/Capacitor collegato;
- il flusso `Usa posizione` in Opzioni resta laboratorio/web, non gate Android finale;
- la vecchia app usa bridge `MeteoAndroid` per stato/coordinate rapide e `navigator.geolocation` come parte del prompt posizione nel WebView;
- le notifiche native passano da `@capacitor/push-notifications`;
- nessun push reale, token FCM, backend register/unregister, workflow o APK e' stato collegato in questa tranche.

Prossimo passo tecnico:

```text
nativeLocationAdapter -> nativePushAdapter -> orchestratore startup Android -> test APK/emulatore
```

Verifica:

```text
Audit read-only + documentazione.
Nessun test runtime eseguito: nessun codice applicativo modificato.
```

## Tranche 120 - Adapter GPS nativo esplicito

File aggiornati:

| File | Ruolo |
| --- | --- |
| `frontend/src/services/nativeLocationAdapter.js` | Adapter puro per parlare con un bridge Android esplicito, senza collegarlo ancora allo startup. |
| `frontend/src/services/nativeLocationAdapter.test.js` | Regressioni su bridge assente, status, richiesta permesso, request id, timeout e payload normalizzato. |
| `PERMISSIONS_GPS_PUSH_AUDIT.md` | Documentato il contratto esplicito `MeteoAndroid` futuro. |
| `AUDIT_CHECKLIST.md` | Tracciata tranche adapter GPS nativo esplicito. |

Decisioni:

- il prompt GPS non deve restare un effetto collaterale del flusso WebView/geolocation;
- UI3 definisce un metodo esplicito futuro `requestLocationPermission(requestId)`;
- UI3 usa un evento esplicito nuovo `meteo-native-location`;
- il legacy `meteo-fast-location` della vecchia app non viene importato come contratto definitivo;
- l'adapter non decide qualita GPS: normalizza soltanto, poi lascia la decisione a `autoLocationPolicy`;
- nessun Android project, prompt reale, push, token FCM, backend o `App.jsx` e' stato collegato.

Contratto bridge futuro:

```text
window.MeteoAndroid.getLocationStatus()
window.MeteoAndroid.requestLocationPermission(requestId)
window.MeteoAndroid.requestFastLocation(requestId)
window.MeteoAndroid.requestBalancedLocation(requestId, timeoutMs)
window.dispatchEvent(new CustomEvent("meteo-native-location", { detail: payload }))
```

Verifica:

```text
npm run test -- --run src/services/nativeLocationAdapter.test.js src/domain/startup/androidPermissionGate.test.js src/domain/geo/autoLocationPolicy.test.js
3 file, 26 test OK
```

## Tranche 121 - Adapter notifiche native esplicito

File aggiornati:

| File | Ruolo |
| --- | --- |
| `frontend/src/services/nativePushAdapter.js` | Adapter puro per permessi/canale/register/unregister/listener Capacitor Push, senza backend. |
| `frontend/src/services/nativePushAdapter.test.js` | Regressioni su plugin mancante, prompt, canale Android, register/unregister e callback token. |
| `PERMISSIONS_GPS_PUSH_AUDIT.md` | Documentato contratto notifiche native UI3 e guardrail anti-token/backend. |
| `AUDIT_CHECKLIST.md` | Tracciata tranche adapter notifiche native esplicito. |

Decisioni:

- il prompt notifiche resta dopo GPS/localita e viene governato dal gate startup;
- l'adapter push non genera `installation_id`;
- l'adapter push non salva token;
- l'adapter push non chiama `/devices/register` o `/devices/unregister`;
- l'adapter push prepara solo il livello nativo: `checkPermissions`, `requestPermissions`, canale Android, `register`, `unregister`, listener callback;
- nessun Android project, prompt reale, token FCM, backend, workflow o `App.jsx` e' stato collegato.

Canale Android previsto:

```text
id: weather_alerts
name: Avvisi Meteo
importance: 4
visibility: 1
lights: true
vibration: true
```

Verifica:

```text
npm run test -- --run src/services/nativePushAdapter.test.js src/domain/startup/androidPermissionGate.test.js
2 file, 19 test OK
```

## Tranche 122 - Terminologia posizione dispositivo

File aggiornati:

| File | Ruolo |
| --- | --- |
| `frontend/src/features/settings/SettingsView.jsx` | Microcopy visibile: `Usa posizione`, `Ricerca posizione`, fallback FUR per stati posizione. |
| `PERMISSIONS_GPS_PUSH_AUDIT.md` | Chiarita la differenza fra GPS tecnico e posizione dispositivo utente. |
| `MIGRATION_MAP.md` | Tracciata la decisione UX/tecnica senza collegamenti runtime. |
| `AUDIT_CHECKLIST.md` | Aggiunta tranche dedicata e aggiornati i riferimenti UX. |

Decisioni:

- in UI non si parla piu di `Usa GPS`;
- per l'utente la funzione e' `Usa posizione`;
- Android puo risolvere la posizione da GPS satellitare, rete mobile, Wi-Fi, celle o ultima posizione nota;
- se servizi posizione o permesso non sono disponibili, resta la localita manuale;
- i nomi `gps_*` restano interni/storici finche non serve un refactor piu ampio del gate.

Guardrail:

- nessun prompt posizione reale collegato;
- nessun Android project aggiunto;
- nessun push, token, backend, meteo, OSMER o Eventi modificato.

## Tranche 123 - Audit copertura Almanacco 365

File aggiornati:

| File | Ruolo |
| --- | --- |
| `ALMANAC_365_COVERAGE_AUDIT.md` | Audit leggibile della copertura annuale di santi, proverbi, tradizioni, consigli terra e Ostermann. |
| `frontend/src/domain/almanac/almanacCoverageAudit.test.js` | Test di guardrail su copertura 366 santi, 12 mesi consigli terra, pool proverbi, tradizioni esatte e backlog Ostermann fuori UI. |

Risultati audit:

- santi: 366/366 giorni coperti + default;
- consigli terra: 12/12 mesi coperti, 2 consigli per mese + default;
- proverbi: 48 totali, 39 `homeEligible`, 6 date fisse + default;
- tradizioni Ostermann Almanacco: 49 record eleggibili;
- tradizioni con data esatta: 9 giorni;
- tradizioni con intervalli: 8 record;
- backlog Ostermann Discover: non pronto per UI, resta escluso.

Decisione:

- Almanacco puo funzionare ogni giorno con fallback controllati;
- non abbiamo ancora 365 proverbi/tradizioni uniche;
- Scopri non va forzato a coprire il calendario;
- il prossimo contratto corretto e `dailyEditorialCalendar`, separato da Scopri.

## Tranche 124 - Audit reperimento proverbi giornalieri

File aggiornati:

| File | Ruolo |
| --- | --- |
| `PROVERB_DAILY_REPERTOIRE_AUDIT.md` | Piano operativo per reperire i proverbi mancanti senza usare fonti casuali. |
| `frontend/src/domain/almanac/proverbDailyRepertoireAudit.test.js` | Guardrail su candidati promuovibili, pagine Ostermann da lavorare e fonte primaria. |

Risultati:

- proverbi pubblicati: 48;
- proverbi `homeEligible`: 39;
- candidati proverbiali: 44;
- candidati gia recensiti: 31;
- candidati consigliati per promozione: 13;
- pagine Ostermann candidate: 28;
- pagine gia estratte come candidati: 6;
- pagine backlog da trasformare in candidati: 22.

Decisione:

- i proverbi mancanti si reperiscono prima da Ostermann gia mappato;
- primo passo: promuovere i 13 candidati dopo revisione FUR/IT;
- secondo passo: estrarre candidati dalle 22 pagine P1/P2 gia individuate;
- fonti esterne solo dopo, con licenza/stato d'uso tracciato.

## Tranche 125 - Primo batch estrazione candidati proverbi Ostermann

File aggiornati:

| File | Ruolo |
| --- | --- |
| `frontend/src/data/almanac/proverbCandidates.json` | Aggiunti 6 candidati da pagine Ostermann 97 e 102, senza pubblicazione in UI. |
| `frontend/src/data/almanac/ostermannProverbSources.json` | Pagine 97 e 102 marcate `candidate_extracted`. |
| `PROVERB_DAILY_REPERTOIRE_AUDIT.md` | Conteggi e metodo aggiornati dopo il batch. |
| `frontend/src/domain/almanac/proverbDailyRepertoireAudit.test.js` | Guardrail su 50 candidati, 8 pagine estratte, backlog residuo 20. |
| `AUDIT_CHECKLIST.md` | Tracciata tranche batch estrazione. |

Risultati:

- candidati proverbiali: 44 -> 50;
- pagine gia estratte come candidati: 6 -> 8;
- pagine backlog residue: 22 -> 20;
- pagina 97: aggiunti candidati su vento di San Gregorio e rugiade di marzo;
- pagina 102: aggiunti due candidati FUR sul cuculo e due pronostici lunari italiani mantenuti come `candidate`.

Guardrail:

- nessun record nuovo e stato promosso in `proverbs.json`;
- nessun record nuovo e `homeEligible`;
- i pronostici italiani restano senza `fur` e non sono promuovibili automaticamente;
- righe OCR rovinate della pagina 97 escluse dal batch.

## Tranche 126 - Secondo batch estrazione candidati proverbi Ostermann

File aggiornati:

| File | Ruolo |
| --- | --- |
| `frontend/src/data/almanac/proverbCandidates.json` | Aggiunti 8 candidati da pagine Ostermann 99 e 104. |
| `frontend/src/data/almanac/ostermannProverbSources.json` | Pagine 99 e 104 marcate `candidate_extracted`. |
| `PROVERB_DAILY_REPERTOIRE_AUDIT.md` | Conteggi e note batch aggiornati. |
| `frontend/src/domain/almanac/proverbDailyRepertoireAudit.test.js` | Guardrail su 58 candidati, 10 pagine estratte, backlog residuo 18. |
| `frontend/src/domain/almanac/proverbArchiveReadiness.test.js` | Aggiornato conteggio pagine estratte. |
| `AUDIT_CHECKLIST.md` | Tracciata tranche secondo batch estrazione. |

Risultati:

- candidati proverbiali: 50 -> 58;
- pagine gia estratte come candidati: 8 -> 10;
- pagine backlog residue: 20 -> 18;
- pagina 99: aggiunti candidati su nebbia e pioggia;
- pagina 104: aggiunti candidati su monti, nubi, pioggia e rane.

Guardrail:

- nessun record nuovo e stato promosso in `proverbs.json`;
- nessun record nuovo e `homeEligible`;
- nota diaristica di Del Negro esclusa dal batch;
- righe OCR rovinate della pagina 104 escluse dal batch.

## Tranche 127 - Batch calendario santi Ostermann

File aggiornati:

| File | Ruolo |
| --- | --- |
| `frontend/src/data/almanac/proverbCandidates.json` | Aggiunti 14 candidati da pagine Ostermann 59, 60, 61 e 63. |
| `frontend/src/data/almanac/ostermannProverbSources.json` | Pagine 59, 60, 61 e 63 marcate `candidate_extracted`. |
| `PROVERB_DAILY_REPERTOIRE_AUDIT.md` | Conteggi e note batch aggiornati. |
| `frontend/src/domain/almanac/proverbDailyRepertoireAudit.test.js` | Guardrail su 72 candidati, 14 pagine estratte, backlog residuo 14. |
| `frontend/src/domain/almanac/proverbArchiveReadiness.test.js` | Aggiornato conteggio pagine estratte. |
| `AUDIT_CHECKLIST.md` | Tracciata tranche calendario santi. |

Risultati:

- candidati proverbiali: 58 -> 72;
- pagine gia estratte come candidati: 10 -> 14;
- pagine backlog residue: 18 -> 14;
- pagina 59: Venerdi Santo e Ascensione;
- pagina 60: Sant'Anna, San Lorenzo, San Bartolomeo e agosto/monti;
- pagina 61: San Gorgone, San Maurizio, San Simone e foglie tardive;
- pagina 63: San Giovanni, Sant'Egidio e relazione ottobre/febbraio.

Guardrail:

- Candelora non duplicata perche gia presente in `proverbs.json`;
- San Blas non duplicato perche gia candidato;
- frasi annotate come contraddittorie o dubbie restano con nota di cautela;
- nessun record nuovo e stato promosso in `proverbs.json`;
- nessun record nuovo e `homeEligible`.

## Tranche 128 - Batch meteo, vento e temporali Ostermann

File aggiornati:

| File | Ruolo |
| --- | --- |
| `frontend/src/data/almanac/proverbCandidates.json` | Aggiunti 10 candidati da pagine Ostermann 94, 96, 101 e 126. |
| `frontend/src/data/almanac/ostermannProverbSources.json` | Pagine 94, 96, 101 e 126 marcate `candidate_extracted`. |
| `PROVERB_DAILY_REPERTOIRE_AUDIT.md` | Conteggi e note batch aggiornati. |
| `frontend/src/domain/almanac/proverbDailyRepertoireAudit.test.js` | Guardrail su 82 candidati, 18 pagine estratte, backlog residuo 10. |
| `frontend/src/domain/almanac/proverbArchiveReadiness.test.js` | Aggiornato conteggio pagine estratte. |
| `AUDIT_CHECKLIST.md` | Tracciata tranche meteo, vento e temporali. |

Risultati:

- candidati proverbiali: 72 -> 82;
- pagine gia estratte come candidati: 14 -> 18;
- pagine backlog residue: 14 -> 10;
- pagina 94: un detto su pioggia lunga;
- pagina 96: garbino, bora e arie rosse;
- pagina 101: proverbio del gallo fuori orario;
- pagina 126: grandine e temporali.

Guardrail:

- pagina 94 usata con parsimonia perche soprattutto lessico dei venti;
- pagina 101 non duplica i proverbi gia presenti su sole rosso/nebbia;
- credenze narrative su lampi, demoni e grandine escluse dal batch;
- nessun record nuovo e stato promosso in `proverbs.json`;
- nessun record nuovo e `homeEligible`.

## Tranche 129 - Batch neve e arcobaleno Ostermann

File aggiornati:

| File | Ruolo |
| --- | --- |
| `frontend/src/data/almanac/proverbCandidates.json` | Aggiunti 10 candidati da pagine Ostermann 130, 131, 132, 140 e 141. |
| `frontend/src/data/almanac/ostermannProverbSources.json` | Pagine 130, 131, 132, 140 e 141 marcate `candidate_extracted`. |
| `PROVERB_DAILY_REPERTOIRE_AUDIT.md` | Conteggi e note batch aggiornati. |
| `frontend/src/domain/almanac/proverbDailyRepertoireAudit.test.js` | Guardrail su 92 candidati, 23 pagine estratte, backlog residuo 5. |
| `frontend/src/domain/almanac/proverbArchiveReadiness.test.js` | Aggiornato conteggio pagine estratte. |
| `AUDIT_CHECKLIST.md` | Tracciata tranche neve e arcobaleno. |

Risultati:

- candidati proverbiali: 82 -> 92;
- pagine gia estratte come candidati: 18 -> 23;
- pagine backlog residue: 10 -> 5;
- pagina 130: proverbio neve/pioggia/raccolto;
- pagina 131: calendario neve e inverno;
- pagina 132: Natale, prima neve e segni vegetali;
- pagina 140: pronostico in prosa sui colori del primo arcobaleno;
- pagina 141: San Marco, arcobaleno e pioggia.

Guardrail:

- pronostico di pagina 140 tenuto come traccia Scopri, non come proverbio FUR pubblicabile;
- varianti con calendario mobile o testo incerto restano `candidate`;
- nessun record nuovo e stato promosso in `proverbs.json`;
- nessun record nuovo e `homeEligible`.

## Tranche 130 - Chiusura backlog Ostermann P1/P2

File aggiornati:

| File | Ruolo |
| --- | --- |
| `frontend/src/data/almanac/proverbCandidates.json` | Aggiunti 8 candidati da pagine Ostermann 189, 192, 609 e 674; pagina 608 lavorata senza duplicare San Barnaba. |
| `frontend/src/data/almanac/ostermannProverbSources.json` | Pagine 189, 192, 608, 609 e 674 marcate `candidate_extracted`. |
| `PROVERB_DAILY_REPERTOIRE_AUDIT.md` | Backlog P1/P2 individuato portato a zero. |
| `frontend/src/domain/almanac/proverbDailyRepertoireAudit.test.js` | Guardrail su 100 candidati, 28 pagine estratte, backlog residuo 0. |
| `frontend/src/domain/almanac/proverbArchiveReadiness.test.js` | Aggiornato conteggio pagine estratte. |
| `AUDIT_CHECKLIST.md` | Tracciata chiusura backlog Ostermann. |

Risultati:

- candidati proverbiali: 92 -> 100;
- pagine gia estratte come candidati: 23 -> 28;
- pagine backlog residue: 5 -> 0;
- pagina 189: gennaio, febbraio, pioggia e granaio;
- pagina 192: San Barnaba, Assunta e vendemmia;
- pagina 608: lavorata come controllo, senza doppione su San Barnaba;
- pagina 609: Sant'Ermacora e bufere come memoria culturale;
- pagina 674: giochi di neve come candidato culturale.

Guardrail:

- nessun record nuovo e stato promosso in `proverbs.json`;
- nessun record nuovo e `homeEligible`;
- pagina 608 non duplica il nucleo gia estratto da pagina 192;
- i record in prosa restano `candidate` e non sono usabili come proverbio quotidiano senza riscrittura editoriale.

## Tranche 131 - Promozione candidati Ostermann gia revisionati

File aggiornati:

| File | Ruolo |
| --- | --- |
| `frontend/src/data/almanac/proverbs.json` | Promossi i 5 candidati Ostermann residui gia recensiti e sostituito il vecchio record sporco su umidita/glace. |
| `frontend/src/domain/almanac/proverbArchiveReadiness.test.js` | Aggiornati i guardrail sui conteggi pubblicati. |
| `PROVERB_DAILY_REPERTOIRE_AUDIT.md` | Aggiornato stato repertorio dopo la promozione controllata. |
| `AUDIT_CHECKLIST.md` | Tracciata la tranche di promozione separata dall'estrazione. |

Risultati:

- candidati gia recensiti: 31;
- candidati consigliati per promozione/sostituzione: 13;
- candidati gia promossi prima di questa tranche: 8;
- candidati residui promossi in questa tranche: 5;
- proverbi pubblicati: 48 -> 52;
- proverbi `homeEligible`: 39 -> 43;
- proverbi `lab_ready`: 8 -> 13;
- proverbi con `humanReviewRequired`: 8 -> 13.

Record promossi o sostituiti:

- `ostermann-103-umiditat-glazze`;
- `ostermann-103-bon-timp-buine-int`;
- `ostermann-190-plois-marz-brosiz-avril`;
- `ostermann-190-mai-jugn-pan-vin`;
- `ostermann-190-pluv-avost`.

Guardrail:

- nessun candidato non recensito e stato promosso;
- nessun record nuovo e stato agganciato a `schedule.json`;
- i 13 record promossi restano `lab_ready` e richiedono review umana finale;
- il lavoro successivo non e nuova estrazione cieca, ma classificazione dei candidati non ancora recensiti.

## Tranche 132 - Routing candidati Ostermann rimanenti

File aggiornati:

| File | Ruolo |
| --- | --- |
| `frontend/src/domain/almanac/proverbCandidateRouting.js` | Modulo puro per instradare i candidati non recensiti in code operative. |
| `frontend/src/domain/almanac/proverbCandidateRouting.test.js` | Guardrail su conteggi, esempi e assenza di duplicati nel routing. |
| `PROVERB_DAILY_REPERTOIRE_AUDIT.md` | Documentata la fase 1b di classificazione. |
| `AUDIT_CHECKLIST.md` | Tracciata la tranche di routing. |

Risultati:

- candidati totali: 100;
- candidati gia recensiti: 31;
- candidati non recensiti: 69;
- candidati non recensiti `source_checked`: 55;
- candidati non recensiti `candidate`: 14;
- coda Review Almanacco: 23;
- coda Contesto o sospensione: 32;
- coda Scopri/archivio: 14.

Guardrail:

- il routing non pubblica record in `proverbs.json`;
- il routing non modifica `homeEligible`;
- i record senza FUR pronto o in prosa restano fuori dall'Almanacco quotidiano;
- l'uso reale resta bloccato finche non viene fatta review FUR/IT o disegno dati Scopri.

## Tranche 133 - Review FUR/IT candidati Almanacco pagina 54

File aggiornati:

| File | Ruolo |
| --- | --- |
| `frontend/src/data/almanac/proverbCandidateReview.json` | Aggiunte 4 review pagina 54 con testo FUR/IT consigliato e fonte tracciata. |
| `frontend/src/domain/almanac/proverbCandidateReview.test.js` | Guardrail su conteggi e record San Blas. |
| `frontend/src/domain/almanac/proverbCandidateRouting.test.js` | Guardrail su coda residua dopo review. |
| `frontend/src/domain/almanac/proverbDailyRepertoireAudit.test.js` | Guardrail sui nuovi conteggi della review. |
| `PROVERB_DAILY_REPERTOIRE_AUDIT.md` | Documentato batch pagina 54. |
| `AUDIT_CHECKLIST.md` | Tracciata tranche pagina 54. |

Record revisionati:

- `ostermann-054-epifanie-fred`;
- `ostermann-054-febrar-soreli`;
- `ostermann-054-san-blas-fred`;
- `ostermann-054-san-valantin-fin-inviar`.

Risultati:

- record recensiti: 31 -> 35;
- candidati consigliati/promossi: 13 -> 17;
- candidati non recensiti: 69 -> 65;
- coda Review Almanacco residua: 23 -> 19;
- coda Contesto o sospensione: 32;
- coda Scopri/archivio: 14.

Guardrail:

- nessun record pagina 54 e stato pubblicato in `proverbs.json`;
- nessun record pagina 54 diventa `homeEligible`;
- gli agganci calendario restano sospesi fino alla promozione controllata;
- le forme FUR consigliate sono tracciate ma richiedono review finale.

## Tranche 134 - Review FUR/IT candidati Almanacco pagina 60

File aggiornati:

| File | Ruolo |
| --- | --- |
| `frontend/src/data/almanac/proverbCandidateReview.json` | Aggiunte 3 review pagina 60 con testo FUR/IT consigliato e fonte tracciata. |
| `frontend/src/domain/almanac/proverbCandidateReview.test.js` | Guardrail su conteggi e record San Bartolomeo. |
| `frontend/src/domain/almanac/proverbCandidateRouting.test.js` | Guardrail su coda residua dopo review. |
| `frontend/src/domain/almanac/proverbDailyRepertoireAudit.test.js` | Guardrail sui nuovi conteggi della review. |
| `PROVERB_DAILY_REPERTOIRE_AUDIT.md` | Documentato batch pagina 60. |
| `AUDIT_CHECKLIST.md` | Tracciata tranche pagina 60. |

Record revisionati:

- `ostermann-060-sant-ane-furmiar`;
- `ostermann-060-san-lurinz-seren`;
- `ostermann-060-san-bortolomio-bon-timp`.

Risultati:

- record recensiti: 35 -> 38;
- candidati consigliati/promossi: 17 -> 20;
- candidati non recensiti: 65 -> 62;
- coda Review Almanacco residua: 19 -> 16;
- coda Contesto o sospensione: 32;
- coda Scopri/archivio: 14.

Guardrail:

- nessun record pagina 60 e stato pubblicato in `proverbs.json`;
- nessun record pagina 60 diventa `homeEligible`;
- `ostermann-060-avost-monz-fumin` resta fuori perche richiede contesto sul tema dei monti fumanti;
- le forme FUR consigliate sono tracciate ma richiedono review finale.

## Tranche 135 - Review FUR/IT candidati Almanacco pagina 61

File aggiornati:

| File | Ruolo |
| --- | --- |
| `frontend/src/data/almanac/proverbCandidateReview.json` | Aggiunte 3 review pagina 61 con testo FUR/IT consigliato e fonte tracciata. |
| `frontend/src/domain/almanac/proverbCandidateReview.test.js` | Guardrail su conteggi e record pagina 61. |
| `frontend/src/domain/almanac/proverbCandidateRouting.test.js` | Guardrail su coda residua dopo review. |
| `frontend/src/domain/almanac/proverbDailyRepertoireAudit.test.js` | Guardrail sui nuovi conteggi della review. |
| `PROVERB_DAILY_REPERTOIRE_AUDIT.md` | Documentato batch pagina 61. |
| `AUDIT_CHECKLIST.md` | Tracciata tranche pagina 61. |

Record revisionati:

- `ostermann-061-san-maurizi-seren`;
- `ostermann-061-san-simon-unviar`;
- `ostermann-061-fueis-tardis`.

Risultati:

- record recensiti: 38 -> 41;
- candidati consigliati/promossi: 20 -> 23;
- candidati non recensiti: 62 -> 59;
- coda Review Almanacco residua: 16 -> 13;
- coda Contesto o sospensione: 32;
- coda Scopri/archivio: 14.

Guardrail:

- nessun record pagina 61 e stato pubblicato in `proverbs.json`;
- nessun record pagina 61 diventa `homeEligible`;
- `ostermann-061-fueis-tardis` resta stagionale/autunnale e non viene trattato come slot calendario;
- le forme FUR consigliate sono tracciate ma richiedono review finale.

## Tranche 136 - Review FUR/IT candidati Almanacco pagina 192

File aggiornati:

| File | Ruolo |
| --- | --- |
| `frontend/src/data/almanac/proverbCandidateReview.json` | Aggiunte 2 review pagina 192 con testo FUR/IT consigliato e fonte tracciata. |
| `frontend/src/domain/almanac/proverbCandidateReview.test.js` | Guardrail su conteggi e record pagina 192. |
| `frontend/src/domain/almanac/proverbCandidateRouting.test.js` | Guardrail su coda residua dopo review. |
| `frontend/src/domain/almanac/proverbDailyRepertoireAudit.test.js` | Guardrail sui nuovi conteggi della review. |
| `PROVERB_DAILY_REPERTOIRE_AUDIT.md` | Documentato batch pagina 192. |
| `AUDIT_CHECKLIST.md` | Tracciata tranche pagina 192. |

Record revisionati:

- `ostermann-192-san-barnaba-vin`;
- `ostermann-192-assunte-vin`.

Risultati:

- record recensiti: 41 -> 43;
- candidati consigliati/promossi: 23 -> 25;
- candidati non recensiti: 59 -> 57;
- coda Review Almanacco residua: 13 -> 11;
- coda Contesto o sospensione: 32;
- coda Scopri/archivio: 14.

Guardrail:

- nessun record pagina 192 e stato pubblicato in `proverbs.json`;
- nessun record pagina 192 diventa `homeEligible`;
- il record San Barnaba mantiene una cautela esplicita sulla lettura OCR della data;
- le forme FUR consigliate sono tracciate ma richiedono review finale.

## Tranche 137 - Review FUR/IT candidati Almanacco pagina 126

File aggiornati:

| File | Ruolo |
| --- | --- |
| `frontend/src/data/almanac/proverbCandidateReview.json` | Aggiunte 2 review pagina 126 con testo FUR/IT consigliato e fonte tracciata. |
| `frontend/src/domain/almanac/proverbCandidateReview.test.js` | Guardrail su conteggi e record pagina 126. |
| `frontend/src/domain/almanac/proverbCandidateRouting.test.js` | Guardrail su coda residua dopo review. |
| `frontend/src/domain/almanac/proverbDailyRepertoireAudit.test.js` | Guardrail sui nuovi conteggi della review. |
| `PROVERB_DAILY_REPERTOIRE_AUDIT.md` | Documentato batch pagina 126. |
| `AUDIT_CHECKLIST.md` | Tracciata tranche pagina 126. |

Record revisionati:

- `ostermann-126-tone-ploe-tempieste`;
- `ostermann-126-mai-tempieste`.

Risultati:

- record recensiti: 43 -> 45;
- candidati consigliati/promossi: 25 -> 27;
- candidati non recensiti: 57 -> 55;
- coda Review Almanacco residua: 11 -> 9;
- coda Contesto o sospensione: 32;
- coda Scopri/archivio: 14.

Guardrail:

- nessun record pagina 126 e stato pubblicato in `proverbs.json`;
- nessun record pagina 126 diventa `homeEligible`;
- i record pagina 126 revisionati sono stagionali/mensili, non slot giornalieri;
- gli altri record pagina 126 restano fuori per contesto, tono o cautela editoriale.

## Tranche 138 - Review FUR/IT candidato Almanacco pagina 130

File aggiornati:

| File | Ruolo |
| --- | --- |
| `frontend/src/data/almanac/proverbCandidateReview.json` | Aggiunta 1 review pagina 130 con testo FUR/IT consigliato e fonte tracciata. |
| `frontend/src/domain/almanac/proverbCandidateReview.test.js` | Guardrail su conteggi e record pagina 130. |
| `frontend/src/domain/almanac/proverbCandidateRouting.test.js` | Guardrail su coda residua dopo review. |
| `frontend/src/domain/almanac/proverbDailyRepertoireAudit.test.js` | Guardrail sui nuovi conteggi della review. |
| `PROVERB_DAILY_REPERTOIRE_AUDIT.md` | Documentato batch pagina 130. |
| `AUDIT_CHECKLIST.md` | Tracciata tranche pagina 130. |

Record revisionato:

- `ostermann-130-sot-nev-pan`.

Risultati:

- record recensiti: 45 -> 46;
- candidati consigliati/promossi: 27 -> 28;
- candidati non recensiti: 55 -> 54;
- coda Review Almanacco residua: 9 -> 8;
- coda Contesto o sospensione: 32;
- coda Scopri/archivio: 14.

Guardrail:

- nessun record pagina 130 e stato pubblicato in `proverbs.json`;
- nessun record pagina 130 diventa `homeEligible`;
- il record revisionato e stagionale/invernale, non uno slot giornaliero;
- la pagina ha layout OCR disturbato, quindi resta richiesta review finale FUR prima della pubblicazione.

## Tranche 139 - Review FUR/IT candidati Almanacco pagina 104

File aggiornati:

| File | Ruolo |
| --- | --- |
| `frontend/src/data/almanac/proverbCandidateReview.json` | Aggiunte 2 review pagina 104 con testo FUR/IT consigliato e fonte tracciata. |
| `frontend/src/domain/almanac/proverbCandidateReview.test.js` | Guardrail su conteggi e record pagina 104. |
| `frontend/src/domain/almanac/proverbCandidateRouting.test.js` | Guardrail su coda residua dopo review. |
| `frontend/src/domain/almanac/proverbDailyRepertoireAudit.test.js` | Guardrail sui nuovi conteggi della review. |
| `PROVERB_DAILY_REPERTOIRE_AUDIT.md` | Documentato batch pagina 104. |
| `AUDIT_CHECKLIST.md` | Tracciata tranche pagina 104. |

Record revisionati:

- `ostermann-104-monts-chapiel`;
- `ostermann-104-cil-lane`.

Risultati:

- record recensiti: 46 -> 48;
- candidati consigliati/promossi: 28 -> 30;
- candidati non recensiti: 54 -> 52;
- coda Review Almanacco residua: 8 -> 6;
- coda Contesto o sospensione: 32;
- coda Scopri/archivio: 14.

Guardrail:

- nessun record pagina 104 e stato pubblicato in `proverbs.json`;
- nessun record pagina 104 diventa `homeEligible`;
- i record revisionati sono segni meteo non datati;
- i record con riferimento locale specifico o resa meno stabile restano fuori.

## Tranche 140 - Review FUR/IT candidati Almanacco pagina 49

File aggiornati:

| File | Ruolo |
| --- | --- |
| `frontend/src/data/almanac/proverbCandidateReview.json` | Aggiunte 2 review pagina 49 con testo FUR/IT consigliato e fonte tracciata. |
| `frontend/src/domain/almanac/proverbCandidateReview.test.js` | Guardrail su conteggi e record pagina 49. |
| `frontend/src/domain/almanac/proverbCandidateRouting.test.js` | Guardrail su coda residua dopo review. |
| `frontend/src/domain/almanac/proverbDailyRepertoireAudit.test.js` | Guardrail sui nuovi conteggi della review. |
| `PROVERB_DAILY_REPERTOIRE_AUDIT.md` | Documentato batch pagina 49. |
| `AUDIT_CHECKLIST.md` | Tracciata tranche pagina 49. |

Record revisionati:

- `ostermann-049-prin-martars-lune-pluv`;
- `ostermann-049-lune-brume`.

Risultati:

- record recensiti: 48 -> 50;
- candidati consigliati/promossi: 30 -> 32;
- candidati non recensiti: 52 -> 50;
- coda Review Almanacco residua: 6 -> 4;
- coda Contesto o sospensione: 32;
- coda Scopri/archivio: 14.

Guardrail:

- nessun record pagina 49 e stato pubblicato in `proverbs.json`;
- nessun record pagina 49 diventa `homeEligible`;
- i record revisionati sono lunari/mensili, non slot giornalieri;
- gli altri record lunari pagina 49 restano fuori per tono, spiegazione o oscurita editoriale.

## Tranche 141 - Chiusura coda Review Almanacco Ostermann

File aggiornati:

| File | Ruolo |
| --- | --- |
| `frontend/src/data/almanac/proverbCandidateReview.json` | Aggiunte 4 review finali della coda Almanacco con testo FUR/IT consigliato e fonte tracciata. |
| `frontend/src/domain/almanac/proverbCandidateReview.test.js` | Guardrail su conteggi e record finali della coda. |
| `frontend/src/domain/almanac/proverbCandidateRouting.test.js` | Guardrail su coda Review Almanacco a zero. |
| `frontend/src/domain/almanac/proverbDailyRepertoireAudit.test.js` | Guardrail sui nuovi conteggi della review. |
| `PROVERB_DAILY_REPERTOIRE_AUDIT.md` | Documentata chiusura della coda Review Almanacco. |
| `AUDIT_CHECKLIST.md` | Tracciata chiusura coda Review Almanacco. |

Record revisionati:

- `ostermann-096-garbin-timp`;
- `ostermann-097-rosadis-marz-bueris-avril`;
- `ostermann-099-tre-fumatis-ploe`;
- `ostermann-102-cuch-ploe-sut`.

Risultati:

- record recensiti: 50 -> 54;
- candidati consigliati/promossi: 32 -> 36;
- candidati non recensiti: 50 -> 46;
- coda Review Almanacco residua: 4 -> 0;
- coda Contesto o sospensione: 32;
- coda Scopri/archivio: 14.

Guardrail:

- nessun record e stato pubblicato in `proverbs.json`;
- nessun record diventa `homeEligible`;
- i record revisionati sono mensili, stagionali, lunari o segni meteo, non slot giornalieri;
- le code `Contesto o sospensione` e `Scopri/archivio` restano da trattare separatamente.

## Tranche 142 - Piano promozione controllata Almanacco

File aggiornati:

| File | Ruolo |
| --- | --- |
| `frontend/src/domain/almanac/proverbCandidateReview.js` | Esporta il predicato `isPromotionRecommendation` per riusare la policy senza duplicarla. |
| `frontend/src/domain/almanac/proverbPromotionPlan.js` | Nuovo modulo puro per costruire la matrice di promozione dai record revisionati. |
| `frontend/src/domain/almanac/proverbPromotionPlan.test.js` | Guardrail su conteggi, gruppi, schedule potenziale e candidati gia pubblicati. |
| `PROVERB_DAILY_REPERTOIRE_AUDIT.md` | Aggiornati conteggi correnti e piano di promozione. |
| `AUDIT_CHECKLIST.md` | Tracciata la tranche di piano promozione. |

Risultati:

- candidati revisionati: 54;
- candidati promuovibili: 36;
- candidati gia pubblicati in laboratorio: 13;
- candidati pendenti: 23;
- candidati pendenti datati: 10;
- candidati pendenti mensili: 4;
- candidati pendenti stagionali: 4;
- candidati pendenti segni meteo: 4;
- candidati pendenti ciclo lunare: 1.

Guardrail:

- nessuna modifica a `proverbs.json`;
- nessuna modifica a `schedule.json`;
- nessuna pubblicazione automatica;
- i 13 candidati `published_proverb` devono restare non duplicati;
- solo i record `almanac_dated` con `dateAnchors` possono diventare slot giornalieri;
- mensili, stagionali, lunari e segni meteo richiedono regole dedicate e non entrano nello schedule fisso.

## Tranche 143 - Promozione controllata proverbi datati

File aggiornati:

| File | Ruolo |
| --- | --- |
| `frontend/src/data/almanac/proverbs.json` | Aggiunti i 10 candidati datati come record `lab_ready` con fonte tracciata. |
| `frontend/src/data/almanac/schedule.json` | Agganciate solo le 10 date fisse ai nuovi record. |
| `frontend/src/domain/almanac/almanacData.test.js` | Verifica che `pickDailyProverb` scelga i nuovi record nelle date previste. |
| `frontend/src/domain/almanac/almanacCoverageAudit.test.js` | Aggiornati i guardrail di copertura. |
| `frontend/src/domain/almanac/proverbArchiveReadiness.test.js` | Aggiornati i conteggi archivio/schedule. |
| `frontend/src/domain/almanac/proverbPromotionPlan.js` | Il piano ora separa i record gia presenti in archivio dai pendenti reali. |
| `frontend/src/domain/almanac/proverbPromotionPlan.test.js` | Guardrail aggiornati dopo la promozione dei datati. |
| `PROVERB_DAILY_REPERTOIRE_AUDIT.md` | Documentata la promozione dei datati. |
| `AUDIT_CHECKLIST.md` | Tracciata la tranche di promozione datata. |

Record promossi:

- `ostermann-054-epifanie-fred` -> 01-06;
- `ostermann-054-san-blas-fred` -> 02-03;
- `ostermann-054-san-valantin-fin-inviar` -> 02-14;
- `ostermann-192-san-barnaba-vin` -> 06-11;
- `ostermann-060-sant-ane-furmiar` -> 07-26;
- `ostermann-060-san-lurinz-seren` -> 08-10;
- `ostermann-192-assunte-vin` -> 08-15;
- `ostermann-060-san-bortolomio-bon-timp` -> 08-24;
- `ostermann-061-san-maurizi-seren` -> 09-22;
- `ostermann-061-san-simon-unviar` -> 10-28.

Risultati:

- proverbi pubblicati: 52 -> 62;
- `homeEligible`: 43 -> 53;
- `lab_ready`: 13 -> 23;
- `humanReviewRequired`: 13 -> 23;
- date fisse in `schedule.json`: 6 -> 16;
- candidati promuovibili gia presenti in archivio: 13 -> 23;
- candidati pendenti reali: 23 -> 13.

Guardrail:

- nessun candidato mensile, stagionale, lunare o segno meteo e stato promosso;
- nessun candidato non reviewato e stato promosso;
- nessun record e stato marcato come definitivo;
- tutti i nuovi record restano `humanReviewRequired: true`;
- lo schedule e stato aggiornato solo per date fisse senza conflitti preesistenti.
