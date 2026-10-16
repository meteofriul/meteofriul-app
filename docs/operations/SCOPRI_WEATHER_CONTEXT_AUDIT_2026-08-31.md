# Scopri — audit tecnico del contesto meteo e lunare

Data: 2026-08-31. Ambito: lettura del codice e dei cataloghi locali, senza nuove API, richieste meteo, modifiche a backend, Home o Almanacco.

## Esito e decisione del lotto

**Non attivare il contesto meteo runtime di Scopri in questo passaggio.** I dati già disponibili consentono di costruire un futuro adattatore, ma il contratto attuale non distingue sempre in modo sufficiente origine del singolo campo, istante osservato e momento di recupero. Collegare direttamente i tag editoriali alla presentazione di Home produrrebbe associazioni non giustificate.

Il lotto editoriale procede separatamente:

- **8 testi storici** recuperati tramite overlay specifico di Scopri, senza convertirli in osservazioni o suggerimenti riferiti al tempo attuale;
- **18 voci escluse** dal recupero, con motivazione nel manifest `frontend/src/data/discover/weatherContextReview.json`;
- nessuna riattivazione generale di `recurrence: "weather"`, nessun fetch aggiuntivo e nessuna modifica del comportamento di Home o Almanacco;
- i 18 esclusi sono candidati valutati nel manifest, non 18 nuove schede visibili; gli 8 recuperati sono contenuti culturali, non 8 nuove misurazioni.

Il manifest del lotto è la fonte delle decisioni per singolo ID e delle restrizioni temporali. Documenta il riuso delle copie IT/FUR esistenti senza nuove traduzioni, promozioni linguistiche o verifiche storiche. Questo documento descrive il motivo tecnico per cui il recupero storico resta indipendente dal meteo. Non sostituisce l'audit delle fonti storiche e non formula valutazioni sui diritti di riuso o affermazioni meteorologiche tratte da fonti esterne.

## 1. Percorso dei dati oggi

| Punto | Dati effettivamente disponibili | Limite per Scopri |
| --- | --- | --- |
| `frontend/src/app/AppRoutes.jsx`, `HomeRouteView` | Stato locale `homeData.weather`, caricato con `readInitialHomeData` e `loadHomeWeather`; bollettino separato | Non è uno stato meteo posseduto e distribuito centralmente da `App` |
| `AlmanacRouteView` nello stesso file | Stato meteo locale caricato con le stesse funzioni; passa solo `current` dopo `getUsableAlmanacWeather` | Nel parametro passato all'Almanacco si perdono `updatedAt`, `fromCache`, `status` e l'identità completa della cache |
| `HomeRouteView` → `buildAlmanacViewModel` | Passa direttamente `homeData.weather.current` | Non applica lo stesso filtro di `getUsableAlmanacWeather`; è un comportamento preesistente non modificato da questo lotto |
| Home → `buildBulletinLocalViewModel` | Usa l'intero stato meteo per cinque indicatori e previsioni orarie | I valori osservati e quelli modellistici possono convivere nello stesso oggetto |
| `BulletinRouteView` | Bollettino ufficiale e radar con controller distinti | Previsione regionale e precipitazione radar non sono una classificazione locale osservata già pronta per Scopri |
| `DiscoverView` | `activeLocation`, `language`, `today`; il modello riceve località e data | Oggi non riceve `weather`, stato della cache o dati lunari |

In `AppRoutes.jsx`, la chiave della vista contiene già `getLocationCacheKey(activeLocation)`: il cambio della località ricrea la route. Scopri non appartiene a `ROUTES_WITH_RUNTIME_REFRESH`; aggiungerlo a quel gruppo non sarebbe una modifica puramente editoriale.

`frontend/src/services/weatherApi.js` usa l'endpoint esistente `/weather/bootstrap`. La normalizzazione restituisce `current`, `forecast`, `officialAlerts`, `osmerAudit`, `city` e il payload originale. Il controller Home conserva in cache un sottoinsieme di questi dati. Non occorre e non si propone un nuovo endpoint in questo lotto.

## 2. Stato, cache e freschezza non sono equivalenti

### Cache del dispositivo

`frontend/src/services/weatherCache.js` definisce:

- chiave `weatherBootstrapCache:v2:<locationKey>`;
- `WEATHER_CACHE_MAX_AGE_MS = WEATHER_VERIFY_INTERVAL_MS = 5 * 60 * 1000`;
- `readWeatherDeviceCacheEntry`, che restituisce `{ data, age, savedAt }` attraverso `jsonCache.js`.

`savedAt` misura quando il dispositivo ha salvato il pacchetto. `data.updatedAt`, assegnato da `loadHomeWeather`, misura il recupero del pacchetto. **Nessuno dei due è necessariamente l'istante dell'osservazione o del campo modellistico.**

`jsonCache.js` controlla anche età negativa e superamento del limite. Questo rende la lettura dell'entry, con limite esplicito, preferibile al solo controllo di una stringa `status`.

### Rischio concreto nella lettura iniziale Home

`frontend/src/features/home/homeDataController.js` consente alla Home di mostrare l'ultimo dato mentre si aggiorna:

- `HOME_INITIAL_STALE_MAX_AGE_MS` e il fallback di refresh sono infiniti;
- `readInitialHomeData` prova prima la cache di cinque minuti, poi quella meno recente;
- anche quando viene recuperata la seconda, costruisce lo stato con `fromCache: true, isStale: false`;
- lo stato risultante può quindi essere `status: "cache"` senza essere recente.

È una policy di continuità della Home, non una garanzia utilizzabile per l'attivazione di contenuti contestuali. Il solo `getUsableAlmanacWeather` di `AppRoutes.jsx` esclude `empty/error/stale` e `isStale`, ma non ricalcola l'età: riusarlo senza ulteriori verifiche non risolve il problema.

### Backend e pacchetti di fallback

In `backend/app/weather/current_engine.py` il pacchetto corrente ha una cache di cinque minuti. In caso di indisponibilità può essere recuperato un dato precedente, contrassegnato da `data_quality.status: "stale"` e certezza `cached_verified` tramite `forecast_engine.add_data_quality`.

L'adattatore futuro dovrà controllare **anche** `current.data_quality` e `current.cache`: una risposta HTTP riuscita o una cache dispositivo appena scritta non rendono nuovo il contenuto del server.

`cache.generated_at` e `data_quality.generated_at` sono attualmente prodotti con `datetime.now().isoformat()` senza offset esplicito. Non devono essere interpretati come un timestamp universale di osservazione: il client non può attribuire silenziosamente un fuso a un valore privo di fuso. Inoltre `add_data_quality` può assegnare un nuovo `generated_at` al dato stale: il timestamp del metadato non ringiovanisce la misura.

## 3. Provenienza dei singoli campi

`frontend/src/domain/weather/normalizedWeather.js` conserva in `raw` il payload originale e normalizza tra gli altri:

- `code`/`weathercode`, `condition`, `temperature`, `windSpeed`, `windGusts`;
- `precipitation`, `rain`, `showers`, `snowfall`, `cloudCover`;
- `source`, `dataQuality`, `station`, `official` e le serie orarie.

La normalizzazione è utile per la presentazione, ma non crea una nuova attestazione della provenienza. Per un adattatore di controllo va mantenuto l'accesso a `rawCurrent` o `current.raw`; rinormalizzare indiscriminatamente un oggetto già normalizzato può anche perdere campi con nomi diversi, per esempio `windSpeed` rispetto a `wind_speed`.

### Il pacchetto corrente può essere ibrido

In `backend/app/weather/current_engine.py`:

1. codice meteo, temperatura, pioggia, neve e vento vengono inizialmente letti da Open-Meteo;
2. quando presenti, temperatura, umidità, pressione, precipitazione e vento sono sovrascritti con valori della stazione OSMER;
3. `condition` può provenire dalla stazione;
4. **se manca il codice corrente**, `condition` può anche essere inferita dal testo del bollettino ufficiale;
5. `source.primary_source` indica l'origine principale del pacchetto, non la provenienza di ogni singolo campo.

Conseguenze:

- `source.primary_source: "arpa_fvg_osmer"` non significa che anche il codice meteo sia un'osservazione OSMER;
- `fallback_used: "open_meteo"` può indicare il normale supporto modellistico del pacchetto ibrido, non necessariamente un errore o dato stale;
- una `condition` leggibile non basta a dimostrare che il fenomeno sia in corso nella località selezionata;
- la sola `precipitation` non dimostra pioggia nell'istante corrente: per il valore stazione manca nel contratto un periodo di misura esplicito;
- `pop` e gli slot futuri sono previsione, non prova di un fenomeno già presente.

### Timestamp osservati mancanti o incompleti

`backend/app/weather/forecast_engine.py`, nel parser della stazione OSMER, espone `station.time` dalla tabella, tipicamente un orario, ma non una data completa dell'osservazione. Espone inoltre `requested_city`, `station_scope`, `station_distance_km` e `station_resolution`.

`current_engine.py` legge i valori Open-Meteo, ma il contratto `WeatherCurrentResponse` non conserva il `current.time` originale. Le serie orarie hanno invece timestamp propri: usarle come sostituto silenzioso del dato corrente trasformerebbe l'operazione in una selezione da previsione.

Non si può quindi promettere una verifica rigorosa dell'età di ogni fenomeno partendo soltanto dal payload attuale. L'eventuale versione successiva dovrà parlare di **contesto tratto dal dato disponibile** o da una **stima**, oppure rendere più esplicita la provenienza temporale del contratto, con un intervento distinto e testato.

## 4. Identità geografica

`frontend/src/domain/geo/locationCacheKey.js` costruisce la chiave da città, eventuale località e coordinate arrotondate a quattro decimali. È il punto corretto per evitare il riuso accidentale della cache di un'altra località.

Un eventuale adattatore deve:

- ricevere la località richiesta e l'entry letta per quella esatta chiave;
- confrontare `data.city`/`current.city` con il comune richiesto usando l'identità geografica applicativa, non il nome tradotto in UI;
- invalidarsi al cambio città, frazione o coordinate;
- mantenere distinti luogo richiesto e stazione di riferimento: la stazione può essere vicina o riferita all'area, non coincidere con il punto dell'utente;
- non usare il solo fatto che entrambi i dati riguardino il Friuli Venezia Giulia come criterio di equivalenza.

Queste verifiche riguardano il contesto meteo. Le `areas` dei testi storici descrivono il loro ambito culturale e non vanno presentate come coordinate dell'utente.

## 5. Classificazione e testi esaminati

`getWeatherSemanticTagContext` in `frontend/src/domain/weather/weatherSemanticTags.js` riconosce anche il caso di coperto generico senza evidenza. È una base migliore del parsing del testo mostrato in UI, ma non sostituisce la verifica di provenienza: il backend può già avere scritto `condition: "Coperto"` o una condizione ricavata dal bollettino.

`classifyCurrentWeather` in `weatherSemantics.js` dà precedenza alla condizione testuale. Un futuro adattatore conservativo dovrà definire quali campi siano accettabili prima della classificazione, senza modificare per questo la semantica globale di Home.

`getWeatherAlmanacTags` in `almanacData.js` è orientato alla selezione editoriale esistente e usa parole, temperatura e vento. Ad esempio associa sole/sereno anche ai tag caldo e irrigazione. Non è un contratto di osservazioni da trasferire in Scopri senza revisione.

| ID esaminato | Significato del testo | Vincolo se un domani diventasse contestuale |
| --- | --- | --- |
| `ost-0001-nubi-pioggia` | Lettura popolare delle forme delle nubi, in forma storica | Tema nubi/pioggia/temporali; non prova che oggi le nubi osservate preannuncino un fenomeno. Segnalato anche il preesistente `sourceStatus: da_controllare`: il recupero dipende dalla revisione editoriale, non dalla disponibilità meteo |
| `ost-0005-lessico-venti` | Lessico dei venti | Il vento può essere un contesto tematico, ma una misura o una direzione non autorizza a dedurre automaticamente bora, garbino, turbine o tromba |
| `ost-0007-grandine-temporale` | Proverbi di tuoni, grandine e temporale | La semplice pioggia non basta, benché compaia nei tag originali. Non trasformare il riferimento rituale in indicazione di protezione o efficacia attuale |
| `ost-0041-neve-abbondanza` | Detto storico sul rapporto neve/raccolti | Il freddo da solo non significa neve. Stagione invernale e fenomeno nevoso non dimostrano un raccolto futuro |
| `ost-0048-palle-neve-slitte` | Giochi invernali e memoria del divieto udinese del 1348 | Il freddo o un codice di nevicata non attestano neve al suolo o condizioni adatte alle slitte. Il testo può essere recuperato come storia, senza invito operativo |
| `ost-0009-luna-lavori-agricoli` | Uso storico delle fasi lunari come calendario dei lavori | Non contiene una fase specifica da usare come trigger. Collegarlo arbitrariamente alla crescente o alla calante aggiungerebbe una regola non presente |
| `ost-0014-proverbi-lunari-pioggia` | Primo martedì di luna e credenze sulla pioggia | Un tag `pioggia` in OR con `luna` non ricostruisce il primo martedì di lunazione; serve una regola distinta verificata rispetto al testo |

La tabella non è una seconda lista di promozione: l'esito definitivo degli otto recuperi e dei diciotto esclusi resta nel manifest del lotto. Il criterio condiviso è non aggiungere al testo un'affermazione sul tempo o sul cielo presenti.

## 6. Luna: dato calcolato locale, non feed meteo

`frontend/src/domain/almanac/moonPhase.js` calcola `age`, `cyclePercent`, `id`, `illuminationPercent` ed etichette IT/FUR dalla data, con mese sinodico medio e riferimento interno di luna nuova. Non esegue richieste di rete e non dipende dalla posizione dell'utente.

`buildAlmanacData` chiama `getMoonPhase(effectiveDate)`; `buildAlmanacViewModel` ne ricava la presentazione. Riutilizzare la funzione di dominio eviterebbe un nuovo servizio, ma:

- il risultato è una stima calcolata dal modello locale, non una certificazione di un'ora astronomica esatta;
- l'etichetta di fase rappresenta un intervallo, non necessariamente il momento preciso di novilunio o plenilunio;
- vanno controllati data valida, giorno civile e coerenza del fuso quando una regola coinvolge il giorno della settimana;
- una data invalida non va lasciata ricadere nella fase di default della funzione;
- `almanacData.js` ha una regola `first_tuesday_of_lunation` per alcuni proverbi, ma la presenza di quella funzione non autorizza ad attribuirla automaticamente a qualsiasi scheda con tag `luna`;
- soprattutto, il contenuto storico non deve diventare una raccomandazione agronomica o una previsione della pioggia basata sulla fase.

Per questo passaggio non viene forzata alcuna fase lunare per le schede di Scopri.

## 7. Adattatore futuro minimo, fuori da questo lotto

Se si riprenderà il contesto runtime, il perimetro minimo consigliato è un adattatore puro, per esempio `buildDiscoverWeatherContext({ cacheEntry, requestedLocation, now })`, separato dai selettori di calendario e dalla presentazione di Home.

Output proposto:

- `eligible` e `reason` espliciti, con default non idoneo;
- identità della località e della chiave richiesta;
- `retrievedAt`, `savedAt`, `cacheAgeMs`, senza chiamarli `observedAt`;
- provenienza complessiva e per campo quando disponibile, qualità server e stato cache;
- soli tag motivati da evidenze ammesse, senza interpretare valori mancanti come sole, assenza di pioggia, freddo o neve;
- provenienza lunare separata, eventualmente `local_calculation`, con data di riferimento e nessun tag attivato finché non esiste la regola editoriale appropriata.

Per evitare nuove richieste, una route Scopri potrebbe leggere soltanto `readWeatherDeviceCacheEntry` con limite esplicito di cinque minuti. Se Home/Almanacco non hanno alimentato una cache valida per quel luogo, il contesto non c'è: **resta il normale archivio**, non si deve avviare un fetch nascosto per riempirlo.

Servono anche invalidazione allo scadere dell'entry e al ritorno in primo piano; altrimenti uno snapshot valido al mount resterebbe apparentemente valido dopo una lunga permanenza su Scopri. Le eventuali riletture locali non devono cancellare bozze, causare caricamenti di rete o modificare le scelte di calendario esatte.

Prima dell'implementazione restano da decidere, in modo circoscritto:

1. Se basti un contesto esplicitamente modellistico/tematico o servano vere osservazioni temporizzate; il payload attuale non garantisce queste ultime per ogni campo.
2. Quali evidenze accettare per ciascuna scheda, con allowlist di ID e rispetto di stagione, lingua e stato editoriale.
3. Se aggiungere al contratto corrente timestamp con offset e provenienza dei singoli campi. È un eventuale lavoro separato, non autorizzato né eseguito da questo documento.
4. Come mantenere il contesto in una singola card di archivio, senza aumentare il numero di blocchi né duplicare una memoria già selezionata.

## 8. Test necessari quando si riaprirà il runtime

I test vanno aggiunti in un modulo dedicato al contesto e nei punti di integrazione Scopri, lasciando indipendenti gli attuali test meteo di Home/Bollettino.

- Cache assente, corrotta, scaduta, con `savedAt` futuro; confini esatti dei cinque minuti.
- Cache appena salvata contenente `data_quality.status: stale`; qualità sconosciuta e timestamp senza fuso non promossi a osservazione fresca.
- Cambio città, frazione o coordinate; stazione di area distinta dalla località richiesta; niente cache del comune precedente.
- Payload nullo, codice mancante, soli valori null, `condition` generica di fallback e condition derivata da bollettino senza codice corrente.
- Provenienza ibrida OSMER/Open-Meteo, fallback modellistico ordinario distinto da errore, nessuna classificazione dalla sola fonte principale del pacchetto.
- Pioggia non equivalente a temporale; freddo non equivalente a neve; previsione futura e probabilità non equivalenti a osservazione.
- Vento generico non trasformato in un nome geografico specifico; nessuna deduzione di neve al suolo.
- Invarianza di primarie, riti e intervalli di calendario; deduplicazione per `contentKey`; esclusione delle voci non approvate e dei diciotto candidati non recuperati.
- IT/FUR coerenti; fonte del testo storico distinta dalla fonte dell'eventuale dato meteo; nessuna dicitura «ora» o «osservato» senza evidenza adeguata.
- Luna: data invalida, confini del giorno civile, fusi/DST, passaggio di lunazione e martedì; niente attivazione arbitraria di `ost-0009` o OR pioggia/luna per `ost-0014`.
- Integrazione senza fetch: apertura Scopri, cambio località, ritorno in primo piano e scadenza della cache non devono invocare API meteo.

I risultati globali di test, build e lint di questo lotto sono registrati nel piano di completamento generale, non duplicati qui.

## 9. Addendum 1 settembre 2026 — contesto storico senza runtime

La quinta passata d'archivio aggiunge tre racconti documentati: le prime previsioni regionali del Centro Meteorologico ERSA diffuse via fax nel 1991, l'organizzazione dell'alpeggio e della scorta di fieno in Carnia e le ghiacciaie di pietra del Carso. Le fonti e le cautele sono registrate in `frontend/src/data/discover/archiveResearchWave05.json`.

Queste schede parlano del rapporto storico fra clima, lavoro e comunicazione, ma **non usano il meteo corrente**: hanno rotazione annuale ordinaria, non ricevono trigger, non leggono la cache di Home e non presentano il 25 giugno come ricorrenza. Di conseguenza non modificano la decisione sui 26 record Ostermann esaminati: otto restano reinterpretati per Scopri, diciotto restano esclusi e `runtimeWeatherIntegration` resta `false`.
