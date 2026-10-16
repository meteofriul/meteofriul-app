# Registro delle pendenze strutturali della pilota

Data del controllo: 13 settembre 2026  
Revisione iniziale esaminata: `1c0b09829ab7cecaac56173284367048fb9cc75b`  
Integrazione circoscritta REG-03/REG-05: grafo di produzione misurato su
`ef8adec`; prova dell'avvio ordinario aggiunta in `c6eef12` e affinata senza
rilettura aggiuntiva in `74f67e5`. Confronto B05 avviato dalla revisione
`baef353`; terza diagnostica opt-in aggiunta in `b851b09` e fixture affinato
in `ce8cd3f`. Correzione B05 avviata dalla revisione
`04bb13af428f21b9048be0cc6c2b6979f1645ea3`.

Ambito: tracciamento delle pendenze già emerse, chiarimenti documentali e prove
locali mirate. Questo documento non è un nuovo audit generale.

Riferimenti verificati sui sorgenti correnti:

- `docs/operations/PILOT_STRUCTURAL_BUG_AUDIT_2026-09-12.md`;
- `docs/operations/B01_CAMS_DURABLE_REVOCATION_FIX_2026-09-13.md`;
- `docs/operations/PILOT_WEATHER_DATA_ARCHITECTURE_2026-09-12.md`;
- `docs/operations/PILOT_APP_COMPLETE_ARCHITECTURE_2026-09-12.md`;
- `docs/operations/CAMS_MANUAL_REFRESH_EPISODE_2026-09-11.md`;
- `docs/operations/PILOT_ANDROID_PREFETCH_2026-09-08.md`.

## Stato sintetico

Gli identificativi `B01`–`B12` dell'audit non vengono rinumerati. Le nuove voci
`REG-*` sono identificativi stabili del presente registro, non nuovi bug
automaticamente confermati.

| ID | Classificazione | Stato al 13 settembre | Ambito |
| --- | --- | --- | --- |
| `B01` | bug confermato | **corretto e verificato localmente, non distribuito** | revoche CAMS durevoli |
| `B08` | bug confermato | aperto, separato e fuori incarico | ciclo e feedback del refresh generale |
| `REG-01` | contratto ricostruito; test obsoleto | chiuso localmente dal commit `a0c38e0` | descrizione nelle card Eventi |
| `REG-02` | topologia di caricamento inefficace | aperto; nessun refactoring applicato | lazy import della vista Almanacco |
| `REG-05` | caricamento statico confermato e quantificato prima della minificazione | aperto; nessun caricamento differito applicato | cataloghi Scopri/Almanacco nell'entry iniziale |
| `REG-03` | ambiguità documentale e prova di sequenza | coperta localmente sulle rotte dirette e sull'avvio ordinario Home → Meteo; nessun bypass trovato | prefetch pilota, journal e presentazione iniziale |
| `REG-04` | diagnosi quantitativa/collaudo ancora da eseguire | aperto | quota Web Storage e persistenza sul dispositivo |
| `B05` | bug confermato nel percorso Firestore condiviso | **corretto e verificato localmente, non distribuito** | conferma, flag e undo concorrenti |

Inserire una voce nel registro non la chiude: per ogni elemento sono indicati
evidenza, lacune e criterio di chiusura.

## Checkpoint distributivo del 14 settembre 2026

**Stato dei tre livelli.** Il browser locale su `http://127.0.0.1:5174/` usa
già i sorgenti correnti fino a `9c72c6b`. La correzione del worker cloud delle
allerte (`aa4f58c`) non è stata distribuita e sul Samsung A52 non è stata
compilata o installata una nuova APK `com.meteofriul.app.localpilot` contenente
le correzioni del 14 settembre. La beta ufficiale `com.meteofriul.app` resta
invariata.

**Gate per la sostituzione della pilota.** La correzione non è considerata
arrivata sul telefono finché non sono stati completati il deploy esplicitamente
autorizzato del worker allerte e, successivamente, l'aggiornamento conservativo
della sola pilota. Subito dopo occorre una verifica end-to-end sul Samsung:
identità e hash della build installata, Home e Bollettino con allerta
attiva/assente/scaduta, pull-to-refresh ed esiti separati dei componenti,
riapertura/offline e conferma finale che `com.meteofriul.app` non sia stata
modificata. La checklist completa è in
[`PILOT_NEXT_REPLACEMENT_CHECKPOINT_2026-09-14.md`](./PILOT_NEXT_REPLACEMENT_CHECKPOINT_2026-09-14.md).

## B01 — Revoche CAMS durevoli

**Stato.** Corretto e verificato localmente, non distribuito. La correzione è il
commit `1c0b098`; non è stata compilata o installata una nuova APK durante questo
incarico.

**Evidenza.** Il puntatore famiglia verificato raggiunge il runtime prima della
release sostitutiva; il journal monotono viene scritto e riletto esattamente,
ripristinato prima di memoria, `active` e `candidate`, e applicato anche agli
oggetti già conservati. Le prove B01 sono elencate nel rapporto dedicato. Il test
del commit `df72c5a`, esteso alla tab di atterraggio dai commit `f248c5c` e
`0ea2574`, copre il confine fra avvio JS, sanitizzazione iniziale e prima
mutazione/snapshot DOM osservata sia per Meteo sia per Home. Il successivo
`c6eef12` attraversa anche
l'avvio ordinario di `App` su Home e la navigazione reale Home → Meteo nella
stessa sessione.

**Impatto dimostrato della correzione.** Una corsa revocata non ritorna
presentabile se la sostituta resta pending o fallisce, se ICON fallisce o se il
processo viene riaperto offline dopo che il journal è stato salvato. ICON e UV
restano indipendenti.

**Limite di persistenza, da non omettere.** Se non vengono salvati né il journal
né una versione sanificata dei bundle, la quarantena della sessione corrente non
può garantire che una nuova sessione conosca una decisione mai resa durevole. Il
runtime non dichiara riuscita la persistenza in questo caso. Questo limite non è
risolvibile cambiando una descrizione o contando test verdi.

**Criterio di chiusura distributiva.** Distribuzione separata e autorizzata della
pilota, seguita da prova sul dispositivo che distingua identità build, journal,
stato prima/dopo riapertura e assenza della corsa revocata. Non eseguito qui.

`B08` resta aperto: il messaggio generale del refresh può chiudersi in un momento
diverso dall'esito CAMS. Nessun file di `B08` è stato modificato.

## B05 — Mutazioni community con controlli fuori transazione

**Stato.** Corretto e verificato localmente, non distribuito. La correzione è
stata sviluppata dalla revisione `04bb13a` nel backend community condiviso. Non
è stata eseguita una nuova verifica Play/cloud e nessuna variante specifica
della pilota è stata introdotta. Il rapporto completo è
`docs/operations/B05_COMMUNITY_LEGACY_COMPARISON_2026-09-13.md`.

**Causa corretta.** I pre-check del service restano utili per risposta e
validazione, ma non sono più l'autorità finale su oggetti che possono cambiare
prima del commit. Conferma e flag rileggono target, appartenenza, scadenza e
gate di moderazione nella stessa transazione delle scritture; i report esistenti
sono modificati con `transaction.update`, non con un merge-set capace di
ricrearli. L'undo legge insieme report e cooldown e cancella quest'ultimo solo
se l'associazione al `report_id` coincide. I cooldown nuovi registrano tale
associazione; quelli legacy senza associazione seguono una regola fail-safe.

**Contratti fissati.** Una conferma o un flag ordinario il cui target non è più
attivo produce `404` e non consuma voto/flag/rate limit. Se il flag incontra un
target già eliminato ma un gate amministrativo nascosto ancora valido, ritorna
il successo idempotente già previsto con `hidden_global=true`, senza ricreare
documenti o riscrivere il gate. Un retry undo di A lascia invariati report B e
cooldown B. I mirror successivi alla transazione usano soltanto payload e ID
verificati/committati.

**Prove.** Le tre diagnostiche repository, le tre corse attraverso il vero
`CommunityService` e quattro casi positivi sono verdi: **10/10** nel modulo
diagnostico. Gli stessi casi sono raccolti ordinariamente da
`test_community_b05_regressions.py`: **10/10**. La raccolta backend pertinente
community/API/moderazione/sicurezza è **160/160**, più **29/29 subtest**; le
regressioni frontend di chiamante e App Check sono **76/76**. Nessun test B05 è
saltato o indebolito.

**Compatibilità e limiti.** Il payload legacy `300011`, i contratti API e i gate
App Check restano invariati. `report_id` è un campo interno additivo. Il fake
dimostra letture e scritture nello stesso confine transazionale ma non emula il
retry/conflitto del vero Firestore; emulator e prove live non sono stati
eseguiti. Un cooldown legacy ambiguo con A già assente viene conservato fino al
TTL invece di rischiare la cancellazione di un cooldown più nuovo.
La regola contro self-confirm/self-flag resta nel pre-check del service e non è
stata estesa a una query transazionale di report aggiunti al gruppo dopo lo
snapshot; quella corsa distinta non faceva parte delle tre riproduzioni B05
chiuse qui.

## REG-01 — Contratto della descrizione Eventi

**Classificazione.** Contratto ricostruito con elevata certezza e test obsoleto;
non è un bug della UI corrente.

**Revisione esaminata.** Contratto e sorgenti verificati su `1c0b098`; test
riallineato nel successivo commit dedicato `a0c38e0`.

**Ambito.**
`frontend/src/features/events/EventsView.test.jsx`, `EventsView.jsx`,
`eventsViewModel.js`, `eventsApi.js` e relativa cronologia Git. Il componente è
condiviso: non è stata introdotta una variante grafica della sola pilota.

**Evidenza disponibile.**

1. Nella conversazione progettuale archiviata
   `01a0759a-4264-7611-b9e2-d7906869bb1c`, la proposta provvisoria di una
   descrizione su due righe compare nel turn
   `01a07c9c-d9c9-7c80-ab03-f86f200aae70`.
2. Nei turn `01a07cfe-a997-7f03-a780-f7534c133ac5` e
   `01a07d08-11b0-7d13-b71c-531b36df70ee` l'utente identifica quelle
   informazioni come rumore; la decisione finale è esplicita: descrizione e
   giornate complete nel dettaglio, non nell'elenco.
3. Il commit `098c26a` aveva già introdotto il dettaglio in-app e il recupero
   della descrizione all'apertura mantenendo compatta la lista.
4. Il successivo `5dda222` aggiunge insieme campo `excerpt`, CSS e test, ma non
   aggiunge mai il markup `.mf-events-card__excerpt` alla card. Il test conserva
   quindi la variante provvisoria già respinta.
5. `UI_COMPONENTS_CONTRACT.md` descrive `EventCard` con titolo, data, luogo,
   distanza, fonte e fallback immagine; la mappa completa descrive la
   descrizione nel dialog di dettaglio.

**Impatto dimostrato.** Prima della correzione, la raccolta completa aveva un
solo test fallito:
`filtered event heading count > shows available descriptions in the list without fetching a detail`.
Il test SSR non eseguiva effetti e non verificava realmente l'assenza di una
richiesta di dettaglio. La UI corrente rispettava già il contratto approvato.

**Intervento minimo eseguito.** Il commit `a0c38e0` modifica soltanto il test:
verifica che la descrizione resti fuori dalla lista, che il modello non perda il
testo e che il medesimo testo compaia nel pannello di dettaglio. I test esistenti
di `eventsApi` continuano a verificare costruzione e normalizzazione della
richiesta di dettaglio; `EventsView.preview.test.jsx` protegge lo stato di attesa
TurismoFVG. Nessun testo, CSS, markup o comportamento applicativo è cambiato.

**Verifica mancante.** Nessuna per riallineare questo specifico test. La futura
eliminazione del campo `excerpt` e del CSS inutilizzato è pulizia distinta e non
necessaria alla chiusura del contratto; non è stata eseguita.

**Criterio di chiusura.** Contratto documentato, test della lista e del dettaglio
verde, suite completa senza il precedente fallimento. Soddisfatto localmente;
vedere la sezione verifiche finali.

## REG-02 — Lazy import inefficace di AlmanacView

**Classificazione.** Problema di topologia del caricamento con possibile impatto
prestazionale. Il warning è reale, ma non dimostra da solo un guasto funzionale
né un rallentamento misurato sul Samsung. La soglia Vite non è un requisito
Google Play. Il peso dei cataloghi dati è tracciato indipendentemente in
`REG-05`.

**Revisione e comando.** Su `1c0b098`, Node `22.17.1`, npm `10.9.2`, Vite
`8.0.16`, è stato eseguito da `frontend`:

```powershell
npm run build
```

Lo script usa `vite build --configLoader native` con `vite.config.js` in
production, poi una build separata del service worker con
`vite.sw.config.js` e `emptyOutDir: false`. Le sole modifiche successive sono
test e documentazione, quindi non cambiano il grafo di produzione.

**Misure riprodotte.** La baseline B01 è riprodotta esattamente.

| Artefatto | Minificato | gzip indicato da Vite | Ruolo |
| --- | ---: | ---: | --- |
| `main-Bal1Nfm2.js` | 3.681,92 kB | 836,43 kB | entry iniziale |
| otto chunk dinamici | 219,46 kB | 66,38 kB | caricamento condizionale |
| tutto il JS app, SW escluso | 3.901,38 kB | 902,81 kB | non tutto iniziale |
| CSS | 277,64 kB | 49,98 kB | iniziale |
| service worker separato | 52,89 kB | 16,59 kB | caricato dal proprio ciclo |

`index.html` riferisce inizialmente soltanto main e CSS, senza
`modulepreload`; l'entry è il 94,37% del JS minificato app. La dimensione gzip
di build non è una misura del trasferimento sul sito pubblicato.

**Causa del warning.** `AppRoutes.jsx` importa dinamicamente
`AlmanacView.jsx`, ma `WeatherSkyCard.jsx` importa staticamente `SkyCard` dallo
stesso file. La catena statica è:

```text
AlmanacView.jsx
→ WeatherSkyCard.jsx
→ WeatherForecastView.jsx
→ AppRoutes.jsx
→ App.jsx
→ main.jsx
```

`WeatherSkyCard` usa `SkyCard`, `buildAlmanacViewModel` e `SunMoon`. Non usa il
resto della vista Almanacco: `TabPage`, stato e timer, contenuti dei santi e
delle tradizioni, navigazione. L'import statico vale anche nella build web,
sebbene la card sia resa soltanto nella pilota.

**Proposta minima, non applicata.** Estrarre `SkyCard`, `SunVisual` e
`MoonVisual` in un modulo condiviso importato sia da `WeatherSkyCard` sia da
`AlmanacView`. Questo rende effettivo il lazy chunk della vista e rimuove il
warning. Non promette però una grande riduzione dell'entry: nel grafo corrente
`AppRoutes` continua a importare e a eseguire `buildAlmanacViewModel` e
`buildDiscoverViewModel` per Home, mentre `HomeQuickGrid` importa direttamente
il catalogo di “I perché”. Una parte di questi dati serve davvero alle anteprime
Home; gran parte è soltanto trascinata o elaborata e poi non presentata nella
Home pilota. Separare tali responsabilità è l'intervento distinto registrato in
`REG-05`.

**APK e web.** Il `dist` web completo misurato contiene 519 file per
81.674.779 byte non compressi; i gruppi maggiori sono `municipalities`
43.263.824, `backgrounds` 24.518.942, `brand` 8.345.444 e `assets` 4.204.607.
È la dimensione dell'artefatto, non il payload iniziale. Capacitor usa
`webDir: dist` e origine `https://localhost`: dopo un sync autorizzato, il JS
dell'app installata è incluso negli asset Android. Incide su installazione,
lettura e parse/evaluate della WebView, non costituisce un download dalla rete
mobile a ogni apertura. La copia Android locale presente durante il controllo è
obsoleta e non è stata usata come misura dell'APK corrente.

**Verifica mancante e criterio di chiusura.** Dopo un futuro intervento:

1. ripetere la stessa build e confrontare entry, somma chunk, CSS e SW;
2. provare l'assenza del warning e la presenza di un chunk Almanacco distinto;
3. verificare che la Home non scarichi immediatamente quel chunk sul web;
4. rieseguire le regressioni di Home, Meteo e Almanacco in IT/FUR e offline.

L'estrazione e la scomparsa del warning possono chiudere questa voce, ma non
`REG-05`: cataloghi e costo dei dati hanno evidenze e criteri di chiusura
separati. Nessun beneficio prestazionale viene assunto dalla sola correzione
topologica. Il punto resta aperto; nessuna soglia o regola è stata alzata o
soppressa.

## REG-05 — Cataloghi dati statici nell'entry iniziale

**Classificazione.** Problema prestazionale strutturale da progettare e
misurare, separato da `REG-02`. L'inclusione statica dei cataloghi nel grafo
iniziale è confermata e quantificata nella metrica pre-minificazione disponibile;
non sono invece ancora dimostrati il contributo esatto ai byte minificati/gzip,
il costo in memoria a runtime o un rallentamento percepibile sul web o sul
Samsung. Non è un bug funzionale e non coincide con il warning sull'import
dinamico inefficace di `AlmanacView`.

**Stato.** Aperto. Non è stato applicato alcun partizionamento dei cataloghi,
caricamento differito o formato dati alternativo. La baseline e il comando di
produzione sono quelli riprodotti in `REG-02`; nessuna soglia Vite è stata
modificata.

### Misura riproducibile e significato

**Revisione e configurazione.** Misura eseguita su `ef8adec`, la cui sola
modifica rispetto al grafo applicativo precedente è documentale; il successivo
`c6eef12` aggiunge soltanto un test. Ambiente: Node `22.17.1`, npm `10.9.2`,
Vite `8.0.16`, `frontend/vite.config.js`, modalità production predefinita,
config loader nativo e `build.write: false`. Da `frontend` è stato eseguito:

```powershell
node --input-type=module -e "import fs from 'node:fs'; import { build } from 'vite'; const result=await build({configFile:'vite.config.js',configLoader:'native',logLevel:'silent',build:{write:false}}); const outputs=Array.isArray(result)?result.flatMap(x=>x.output||[]):result.output||[]; const main=outputs.find(x=>x.type==='chunk'&&x.isEntry); const rows=Object.entries(main.modules).filter(([id])=>id.replaceAll('\\','/').includes('/src/data/')).map(([id,v])=>({id,renderedLength:v.renderedLength,sourceBytes:fs.statSync(id).size})); const core=rows.filter(x=>/[/\\]fvg(?:Places\.js|PlaceNamesFur\.json)$/.test(x.id)); const sum=(xs,key)=>xs.reduce((n,x)=>n+x[key],0); console.log(JSON.stringify({entryModules:Object.keys(main.modules).length,entryRenderedLength:sum(Object.values(main.modules),'renderedLength'),allData:{modules:rows.length,renderedLength:sum(rows,'renderedLength'),sourceBytes:sum(rows,'sourceBytes')},discoverAlmanac:{modules:rows.length-core.length,renderedLength:sum(rows,'renderedLength')-sum(core,'renderedLength'),sourceBytes:sum(rows,'sourceBytes')-sum(core,'sourceBytes')}}));"
```

Risultato:

| Insieme | Moduli | Sorgente su disco | Contributo `renderedLength` | Denominatore | Quota |
| --- | ---: | ---: | ---: | ---: | ---: |
| tutti i moduli `src/data` dell'entry | 20 | 3.528.999 byte UTF-8 su disco | 3.077.495 caratteri | 5.132.082 caratteri, somma dei 377 moduli dell'entry | 59,9658% |
| soli 18 moduli Scopri/Almanacco | 18 | 3.442.091 byte UTF-8 su disco | 2.999.483 caratteri | lo stesso denominatore dell'entry | 58,4457% |
| geografia condivisa esclusa dalla seconda riga | 2 | 86.908 byte UTF-8 su disco | 78.012 caratteri | lo stesso denominatore dell'entry | 1,5201% |

I due moduli esclusi dal sottoinsieme editoriale sono `fvgPlaces.js` e
`fvgPlaceNamesFur.json`: sono condivisi da località, meteo, community e resa
friulana, quindi non vanno etichettati automaticamente come cataloghi
editoriali differibili.

Le unità non sono intercambiabili:

- `sourceBytes` è la dimensione fisica dei file sorgente, non il loro peso
  nell'output;
- Rollup `RenderedModule.renderedLength` conta caratteri attribuiti a ciascun
  modulo dopo il tree-shaking e prima della minificazione finale; non è byte
  trasferito né gzip;
- la build di produzione scritta da `npm run build` resta la misura separata:
  `main-Bal1Nfm2.js` è 3.681,92 kB minificati e 836,43 kB gzip secondo Vite;
- `index.html` carica quel main come asset iniziale e tutti i 20 moduli compaiono
  in `main.modules`: i loro letterali sono quindi inglobati nell'asset iniziale,
  senza richieste JSON separate. Non sono stati però misurati residency in
  memoria, tempi di parse per singolo catalogo o byte minificati/gzip attribuiti
  a ciascun modulo.

I maggiori contributori dati osservati sono:

| Modulo | `renderedLength` |
| --- | ---: |
| `discover/localMemory.json` | 947.765 |
| `discover/municipalityProfiles.json` | 472.035 |
| `almanac/saints.json` | 455.404 |
| `discover/pilotWhyCatalog.json` | 309.007 |
| `almanac/proverbs.json` | 224.211 |
| `almanac/saintProfiles.json` | 217.810 |
| `discover/institutionalArchive.json` | 111.018 |
| `ostermannCulturalDiscover.json` | 94.370 |

### Dati necessari alla Home e dati trascinati

La verifica dei chiamanti distingue appartenenza all'entry, esecuzione nel
percorso Home e necessità semantica per ciò che la Home presenta:

| Gruppo | Percorso corrente | Necessità nella Home corrente |
| --- | --- | --- |
| `localMemory.json` (581 record) | `localMemory.js → discoverViewModel.js → AppRoutes.HomeRouteView → selectHomeDiscoverPreview` | la Home mostra una sola “Memoria del giorno” selezionata; il file completo e le sezioni alternative vengono comunque importati e scanditi |
| `pilotWhyCatalog.json` (366 record/366 chiavi di calendario) e `pilotWhyPalmanova.json` | `pilotWhyContent.js → HomeQuickGrid.jsx` | necessari direttamente alla card “I perché” della Home pilota, oltre che alla continuità Home → Scopri; non entrano soltanto attraverso `DiscoverView` |
| `municipalityProfiles`, `municipalityMilestoneSources`, archivi/rituali/cultura meteo e Ostermann, detti tradizionali e riuso dei proverbi | `buildDiscoverViewModel` costruisce il modello completo prima che `selectHomeDiscoverPreview` scelga la memoria primaria | caricati ed elaborati, ma non contribuiscono alla card Home quando la memoria primaria corrente è disponibile; servono alle superfici complete di Scopri e ai fallback da preservare |
| `saints`, `saintProfiles`, `proverbs`, `earthTips`, `schedule` e cultura condivisa | `almanacData → buildAlmanacViewModel → buildHomeAlmanacStateFromModel` | il modello è costruito su Home, ma la Home pilota sostituisce la card Almanacco con “I perché”; nella build ordinaria resta necessario soltanto il riepilogo compatto concordato, non l'intero dettaglio editoriale |
| `municipalityPhotos.json` e `municipalityVisuals.json` | mappe costruite all'import di `municipalityVisuals.js`, raggiunto dall'import statico di `DiscoverView.jsx` | usate dalla rotta Scopri, non dalla presentazione Home |
| `fvgPlaces.js` e `fvgPlaceNamesFur.json` | dipendenze condivise di località e denominazioni | dati core: un'eventuale ottimizzazione va provata senza rompere GPS, selezione Comune, IT/FUR, meteo o community |

“Non necessario subito” non significa “eliminabile”: i fallback editoriali, la
navigazione diretta e l'offline continuano a far parte del contratto. Inoltre
rendere differita la sola pagina `DiscoverView` non differisce automaticamente
i dati: `AppRoutes` importa ancora i builder usati dalla Home e
`HomeQuickGrid` importa direttamente `pilotWhyContent`.

**Impatto dimostrato.** I cataloghi completi fanno parte dell'entry iniziale e
costituiscono il 58,4457% del `renderedLength` pre-minificazione dell'entry nella
misura riprodotta. Estrarre i componenti condivisi di `AlmanacView` può rendere
effettivo il relativo chunk, ma non sposta automaticamente questi dati. La
scomparsa di `[INEFFECTIVE_DYNAMIC_IMPORT]` o il rientro sotto una soglia di
warning non dimostra quindi una riduzione materiale del carico iniziale. Sul web
questi moduli possono incidere su trasferimento e parse/evaluate; nell'app
Capacitor sono asset locali, non un download mobile a ogni apertura. Il solo
code splitting non riduce necessariamente la dimensione totale di `dist` o APK.

**Prova mancante.** Mancano l'attribuzione per catalogo dopo minificazione e
compressione, il waterfall della Home a cache fredda e calda, tempi di
decompressione/parse/evaluate, FCP/LCP e long task, una misura separata del cold
start sul Samsung e la definizione del payload minimo per le anteprime Home.
Manca inoltre la prova che un eventuale caricamento differito conservi selezione
per data e Comune, IT/FUR, navigazione diretta, “I perché”, aggiornamento del
service worker e funzionamento offline.

**Relazione con REG-02.** `REG-02` traccia la topologia del codice della vista
Almanacco e il warning dovuto al doppio import. `REG-05` traccia la topologia e
il costo dei dati. Possono condividere parte dell'implementazione, ma chiudere
una voce non chiude l'altra. Reciprocamente, un futuro partizionamento dei dati
non chiuderà `REG-02` finché il doppio import di `AlmanacView` resterà presente.

### Proposta separata, non applicata

1. Mantenere sincrono un indice Home versionato e minimo: geografia realmente
   condivisa; campi della memoria giornaliera necessari all'anteprima; per “I
   perché” ID stabile, chiave data, categoria, domanda/CTA IT e FUR; soltanto il
   riepilogo santo/data e il fallback `tradition.label` richiesti dalla Home
   ordinaria, se quel contratto resta.
2. Spostare in asset o chunk di rotta i corpi completi e le fonti di “I perché”,
   profili/timeline/visual dei Comuni, memorie secondarie e locali, archivi,
   rituali, detti, proverbi, biografie dei santi e contenuti della Terra.
3. Conservare lo stesso ID fra card Home e dettaglio Scopri, la selezione per
   data e località e i fallback editoriali; il caricamento differito non può
   cambiare quale contenuto viene scelto.
4. Definire esplicitamente l'offline prima del refactoring. Nell'APK Capacitor
   gli asset differiti possono restare inclusi nel pacchetto. Sul web il service
   worker corrente non dimostra un precache completo di nuovi asset di rotta:
   va specificato e provato almeno il caso “installazione già calda, poi
   offline”, senza promettere una prima visita offline impossibile.

**Criterio di chiusura.** Prima dell'intervento vanno registrati un obiettivo
quantitativo e il payload minimo ammesso per Home. La voce si chiude soltanto
quando:

1. una tabella omogenea prima/dopo separa byte sorgente, `renderedLength`, entry
   minificata/gzip, asset inizialmente richiesti e tempi di parse/evaluate;
2. un obiettivo concordato di riduzione del carico iniziale è soddisfatto e i
   cataloghi completi non appartengono più al main/critical path Home, salvo
   indici iniziali giustificati e misurati;
3. Home, Scopri e Almanacco restano corretti in IT/FUR, per tutte le chiavi data
   rilevanti (incluso 29 febbraio) e per località/Comuni rappresentativi;
4. la card “I perché” apre lo stesso contenuto completo, navigazione diretta e
   fallback restano validi, e l'offline è provato separatamente per web caldo e
   app impacchettata;
5. ogni beneficio dichiarato per l'app installata è confermato da un cold start
   comparabile sul Samsung.

Il criterio di `REG-02` resta invece circoscritto: import statico della card
condivisa eliminato, warning assente, chunk Almanacco distinto e regressioni
Home/Meteo/Almanacco verdi. Soddisfarlo non chiude `REG-05`; la sola assenza dei
warning Vite non è criterio di chiusura della voce cataloghi.

## REG-03 — Prefetch effettivo, journal e finestra di avvio a freddo

**Classificazione.** Ambiguità documentale corretta e prova integrata aggiunta.
Non è emerso un bypass permanente né una finestra temporale nelle sequenze
locali/jsdom esercitate quando esiste un journal durevole valido; la prova non
si estende ai frame fisici del dispositivo.

**Revisione esaminata.** Topologia e ordine runtime verificati su `1c0b098`;
prova Meteo aggiunta in `df72c5a`, prova della Home reale aggiunta in `f248c5c`
e rinforzata semanticamente in `0ea2574`. Il commit `c6eef12` aggiunge la prova
distinta dell'avvio ordinario di `App` su Home e del passaggio Home → Meteo,
senza modifica al codice applicativo. Il commit `74f67e5` affina l'osservazione
dello stato iniziale senza aggiungere una seconda lettura del runtime.

### Catena attiva e condizioni

| Passaggio | Chiamanti e condizioni di attivazione | Controlli prima della presentazione |
| --- | --- | --- |
| bootstrap/cache Home legacy | `AppRoutes` inizializza Home e Meteo con `readInitialHomeData`; negli effect chiama anche `hydrateHomeWeatherFromBackgroundPrefetch`. In `localPilot`, `usesAutonomousWeatherProvider()` rende inerti `weatherBootstrapCache:v3` e `readBackgroundWeatherPrefetch`; il worker meteo condiviso è cancellato dal ramo `BuildConfig.LOCAL_WEATHER_PILOT` | nessun dato legacy può diventare il meteo della pilota |
| staging nativo ICON/CAMS dedicato | `getPilotWeatherPrefetchReader` è disponibile soltanto con localPilot reale, Android Capacitor, plugin registrato, origine pilota ammessa, ISTAT a sei cifre e senza orologio simulato. Configurazione massima 1.000 ms, singola lettura massima 500 ms | `PilotWeatherPrefetchStore` conserva byte raw in `AtomicFile` distinti; non scrive localStorage o bundle display. Selezione/generazione, percorso e SHA richiesto devono coincidere |
| oggetti immutabili nel client | `localWeatherV1Adapter` inietta il reader nel client; il native non fornisce `latest.json`, ma soltanto oggetti immutabili dopo che un parent ha indicato percorso e hash | limite dimensione, SHA-256, UTF-8/canonical JSON, schema, catalogo, Comune, provenienza, manifest/release e freschezza vengono ricontrollati da `weatherV1Client` |
| runtime | `fetchLocalWeatherV1RuntimeBundle` configura il reader senza attendere I/O; il puntatore famiglia CAMS verificato percorre `onFamilyLatest` prima della release sostitutiva | identità comunale, revisioni monotone, active+candidato, revoche ICON/CAMS e selezione campione |
| journal | `readPersistedBundle` ripristina il journal CAMS prima di leggere `active` o `candidate`; il fetch runtime lo ripristina prima di memoria, persistenza o rete | bundle revocati vengono sanificati o messi in quarantena; un journal illeggibile rende indisponibile soltanto CAMS |
| presentazione | `AppRoutes` usa un inizializzatore `useState` sincrono. Il root HTML iniziale è vuoto e non contiene meteo server-rendered; la prima mutazione DOM osservata segue `readInitialHomeData` | la UI riceve soltanto l'output già filtrato dal runtime; gli effect successivi non possono usare il prefetch legacy nella pilota |

### Prova diretta delle rotte

Il commit `df72c5a` aggiunge
`src/app/AppRoutes.coldStartRevocation.test.jsx`; `f248c5c` applica lo stesso
harness alla rotta `home`, e `0ea2574` verifica anche il risultato sanificato
restituito alla Home. Queste due prove montano direttamente `AppRoutes` con
`activeTab="weather"` oppure `activeTab="home"`: proteggono entrambe le
superfici, ma non dimostrano da sole che l'avvio ordinario di `App` scelga e
attraversi Home. Le prove partono
con:

- bundle `active` A persistito e riconoscibile da marker aria/pollini;
- journal durevole che revoca A e indica B;
- stato runtime non ancora consultato per quello scope;
- reader nativo predisposto, con lettura dell'oggetto immutabile lasciata
  intenzionalmente pending;
- caricamenti indipendenti di Eventi e bollettino lasciati pending nella prova
  Home, così non interferiscono con il confine meteo osservato;
- `MutationObserver` attivato prima di `root.render`.

Per entrambe le rotte la prova richiede `render invocato → journal letto` e
verifica che il journal preceda sia la prima mutazione/snapshot DOM non vuota
osservata sia la lettura
nativa. Non impone un ordine artificiale fra questi ultimi due eventi. Sulla
rotta Meteo nessuno snapshot DOM, neppure transitorio, contiene i marker A;
aria/pollini sono indisponibili e la card ICON resta presentabile.

Sulla rotta Home la sola assenza dei marker dal DOM non sarebbe una prova
sufficiente: nella `localPilot`, per scelta attuale, `HomeView` non rende
`HomeLocalMetrics`, mentre temperatura e sintesi dipendono da ICON e devono
restare visibili. Il test intercetta quindi senza sostituirla la vera
`readInitialHomeData` e dimostra l'ordine
`journal letto → stato Home iniziale costruito → prima mutazione/snapshot DOM
osservata`. Verifica inoltre
che lo stato consegnato alla Home abbia `air_quality_data: null`, pollini
`unavailable` senza valori e diagnostica `RUN_DISABLED` della sola famiglia
CAMS. La superficie reale Home (`mf-home-view`, hero e temperatura ICON) rimane
presentabile. Il test è parte della raccolta ordinaria.

### Prova dell'avvio ordinario Home → Meteo

Il commit `c6eef12` aggiunge
`src/app/App.coldStartRevocation.test.jsx`. La prova monta il vero `<App />`
senza prop e con URL `/`, quindi senza override di tab; usa `AppShell`,
`AppRoutes`, i controller Home, il runtime e il journal reali. Il controllo
negativo prepara, prima del mount:

- `active` e `candidate` persistiti, entrambi contenenti la vecchia corsa A e
  marker CAMS riconoscibili (`91,7` aria e `92,7` pollini);
- journal durevole, integro e coerente con catalogo/scope, che revoca A e indica
  la sostituta B;
- ICON B valido e con previsione oraria non vuota;
- fetcher del candidato e `fetch` generico lasciati pending, così nessuna nuova
  release può mascherare lo stato iniziale.

La costruzione del fixture usa l'adapter soltanto per produrre i dati da
persistire; usa base URL e storage univoci e non consulta il runtime dello scope
prima del mount. Il test accerta anche che nessuna lettura di journal/active sia
avvenuta prima di `root.render` e osserva l'ordine
`render App → lettura journal → lettura active → prima mutazione/snapshot DOM
Home osservata`.

Nell'affinamento `74f67e5`, il wrapper già presente di
`readWeatherBootstrapCache` intercetta la lettura realmente effettuata da
`readInitialHomeData`: delega una sola volta alla funzione reale, copia
immediatamente soltanto i primitivi necessari e restituisce all'app lo stesso
oggetto originale, senza modificarlo e senza introdurre attese. La lettura
pertinente viene identificata per ISTAT Pordenone, risultato presente e indice
evento precedente al primo snapshot Home; la prova non dipende dal numero
esatto di invocazioni. Non vengono conservati riferimenti a `current`,
`data_quality`, aria o pollini che possano mutare successivamente.

Nella stessa sessione il test:

1. osserva nel DOM che la rotta iniziale e la voce attiva sono Home e che la
   temperatura ICON è concreta, non `--`;
2. verifica sulla copia della lettura iniziale già compiuta dall'app che soltanto
   CAMS sia sanificato (`RUN_DISABLED`, aria `null`, pollini `unavailable`),
   mentre ICON B e le ore previste restano utilizzabili;
3. seleziona il vero pulsante inferiore “Meteo”, attraversando
   `App.handleRouteChange`, e verifica una card oraria non vuota;
4. verifica nella vista Meteo e in tutti gli snapshot DOM osservati che i marker
   A non compaiano prima dell'arrivo di una sostituta.

Il caso gemello, con bundle altrimenti identico ma senza revoca, percorre lo
stesso avvio Home → Meteo e richiede CAMS `available` e la presenza dei marker
nel DOM Meteo. Dimostra quindi che il controllo negativo non passa perché la
vista rimane sempre vuota o perché CAMS è incondizionatamente disabilitato.

**Confini controllati.** Sono simulate l'identità della build pilota e il suo
endpoint, la località Pordenone già selezionata, l'assenza di una risposta dei
trasporti e i sottosistemi estranei alla decisione meteo (allerte ufficiali,
push web, onboarding e flag laboratorio). Il wrapper di `weatherApi` delega
alle implementazioni reali iniettando soltanto clock, storage e fetcher
deterministici; osserva il risultato già richiesto dall'app senza effettuare una
seconda lettura. Non sono sostituiti `App`, `AppShell`, `AppRoutes`, controller
Home, journal, validatore o runtime.

**Tre livelli di evidenza.** Nel DOM jsdom sono osservati Home, temperatura ICON,
navigazione e stato delle card Meteo. Nella copia primitiva del risultato reale
di `readWeatherBootstrapCache`, acquisita durante l'inizializzazione Home, sono
verificati run CAMS/ICON, sanitizzazione e ore ICON. `MutationObserver` registra
mutazioni e snapshot DOM jsdom, ma non garantisce una callback distinta per ogni
commit React e non misura frame WebView, tempi di pittura o flash sul Samsung.

Riferimenti principali: `AppRoutes.jsx` (`HomeRouteView` e
`ForecastRouteView`), `homeDataController.js`
(`hydrateHomeWeatherFromBackgroundPrefetch`, `readInitialHomeData`),
`weatherCache.js`, `pilotWeatherPrefetch.js`, `localWeatherV1Adapter.js`,
`weatherV1Client.js` (`prefetchedSnapshot`, client famiglia CAMS) e
`localWeatherV1Runtime.js` (`readPersistedBundle`,
`restoreCamsFamilyDecision`, `fetchLocalWeatherV1RuntimeBundle`). Sul lato
Android: `MeteoBackgroundWeatherScheduler.java` e
`PilotWeatherPrefetchStore.java`.

**Impatto dimostrato.** La frase precedente “anche il prefetch nativo viene
ignorato” confondeva due meccanismi. È ignorato il prefetch legacy; il plugin
`PilotWeatherPrefetch` resta attivo come sorgente non autorevole di byte e non
aggira validatore, runtime o journal. Il rapporto B01 è stato corretto.

**Verifica mancante.** Non è stata eseguita una prova WorkManager, WebView o
telefono. Restano quindi non misurati i frame fisici del Samsung, i tempi reali
di bootstrap e il beneficio del prefetch nativo. La prova diretta di
`AppRoutes` esercita l'interfaccia reader simulata e il percorso reale
adapter/runtime con oggetto immutabile pending; non esercita il plugin nativo o
il codice Java. La prova ordinaria di `App` tiene pending il confine provider
iniettato. Se il journal non è mai stato salvato, resta il limite B01 già
descritto, non un bypass di un journal esistente.

**Stato della copertura.** Le rotte dirette Home/Meteo e l'avvio ordinario
Home → Meteo sono protetti localmente per journal durevole valido, sostituta
pending, controllo senza revoca e ICON utilizzabile. È un ampliamento della
copertura, non una riapertura di B01 e non una dichiarazione sui frame del
dispositivo. Un eventuale collaudo del worker su dispositivo dovrà registrare
build, selezione/generazione, oggetto letto e tempi senza cambiare worker,
frequenza, push o localizzazione.

## REG-04 — Diagnosi quantitativa dello storage

**Classificazione.** Problema quantitativo confermato nell'episodio precedente,
ma causa di occupazione totale e margine del dispositivo ancora da misurare. Il
fallback `cams-delta` ha conservato il servizio; non dimostra che la quota sia
stata risolta.

**Revisione esaminata.** Contenitori e algoritmi verificati su `1c0b098`; le
misure reali provengono dal verbale del Samsung dell'11/12 settembre citato
sopra, non da un nuovo accesso al dispositivo.

### Contenitori e copie effettive

| Contenitore | Utilizzatore e limite corrente | Copie durante l'aggiornamento |
| --- | --- | --- |
| cache raw `meteofriul:weather-v1:v4:*` | `weatherV1Client`; per scope e provider: 1 latest, 2 release, 2 manifest e 4 municipality, con budget dei soli body interni pari a 1.792 KiB per provider | il body JSON è inserito come stringa in un record JSON esterno; chiavi, metadati ed escaping non rientrano nel budget dei body |
| bundle `meteofriul:weather-v1:bundle:v4:*` | `localWeatherV1Runtime`; massimo 8 bundle indicizzati globalmente, senza budget byte complessivo | `active` e `:candidate` completi coesistono fino alla sostituzione atomica; su quota può coesistere il più piccolo `cams-delta` |
| journal `meteofriul:weather-v1:cams-family-decision:v1:*` | autorità B01 per scope origine e catalogo | una sostituzione Web Storage atomica, poi rilettura esatta; non dipende dal completamento del bundle |
| UV `meteofriul:pilot:uv:v1` | `uvForecastRuntime` | `active` e `:candidate` UV distinti e indipendenti da CAMS |
| altri dati Web Storage | località, eventi, bollettino/radar, webcam, community, preferenze e notifiche | condividono la quota dell'origine WebView; non sono stati misurati sul telefono in questo incarico |
| staging nativo `pilot_weather_prefetch_v1_icon.json` e `_cams.json` | `PilotWeatherPrefetchStore`; snapshot core massimo 6 MiB per famiglia, file letto con limite 16 MiB | `AtomicFile` può mantenere file base/backup durante una sostituzione; è filesystem privato nativo, non la quota `localStorage` della WebView |
| preferenze native `pilot_weather_prefetch_v1` | selezione ISTAT e generazione | record piccolo in `SharedPreferences`, separato dai due snapshot |

Il budget raw è applicato separatamente alle namespace `icon2i`, famiglia CAMS,
CAMS core e CAMS pollini. Esso somma `body_bytes`, non la dimensione realmente
serializzata nel Web Storage; non è quindi un tetto globale dell'origine.
I riferimenti principali sono le costanti e `ConditionalJsonTransport` in
`weatherV1Client.js`, le funzioni `writePersistedBundle`,
`writePersistedCamsDelta`, `persistCamsFamilyDecision` e `readPersistedBundle`
in `localWeatherV1Runtime.js`, `uvForecastRuntime.js` e
`PilotWeatherPrefetchStore.java`.

### Evidenza quantitativa disponibile

**Misura reale precedente sul Samsung, in caratteri JavaScript.** Il verbale
dell'11/12 settembre registra un `active` Pordenone di 81.517 caratteri. Due
candidati completi da 81.241 e 77.277 caratteri sono stati respinti con
`QuotaExceededError`; un `cams-delta` di 22.719 caratteri è stato salvato e ha
prodotto un nuovo `active` di 81.532 caratteri.

Da quelle lunghezze si ricavano, senza convertirle impropriamente in byte:

- primo picco teorico `active + candidate`: 162.758 caratteri di valore;
- secondo picco teorico: 158.794 caratteri;
- picco `active + cams-delta`: 104.236 caratteri;
- il delta richiede il 64,04% dei caratteri del primo picco e ne evita 58.522.

Il candidato completo respinto non è rimasto memorizzato. Queste somme escludono
chiavi, indice, cache raw, journal, UV e ogni altro dato dell'origine. Dimostrano
che in quel momento il record ridotto entrava dove il completo non entrava; non
misurano la quota complessiva né il suo algoritmo di conteggio.

**Misura locale controllata, non dispositivo.** Una prova temporanea basata su
`camsRecoveryTestFixtures` ha registrato il ciclo completo senza rete o telefono:

- `active` sintetico iniziale: 58.434 caratteri / 58.438 byte UTF-8;
- `active` sostitutivo: 58.488 caratteri / 58.492 byte UTF-8;
- picco durante `active + candidate + indice`: 117.081 caratteri di valore,
  117.089 byte UTF-8 di valore e 117.294 byte UTF-8 includendo le chiavi.

Il file diagnostico temporaneo è stato rimosso dopo la prova. Il fixture inietta
i provider e quindi non misura la cache raw né la quota Chromium. Serve soltanto
a confermare la duplicazione transitoria del percorso runtime. Un record journal
sintetico conforme allo schema corrente, con una revoca, occupa 430 caratteri e
430 byte UTF-8; il record reale cresce con l'elenco cumulativo delle revoche.

**Diagnosi strutturale attuale.** Il punto quantitativo non è la sola dimensione
del bundle: l'origine condivide bundle, cache raw e altri domini; il budget raw
non include l'overhead della serializzazione; il runtime limita il numero dei
bundle ma non i byte complessivi. Il momento della scrittura del candidato è il
trigger osservato, non ancora la spiegazione dell'occupazione totale. Ridurre il
bundle JavaScript di produzione non dimostrerebbe la risoluzione di
`QuotaExceededError`, perché quegli asset non sono valori `localStorage`.

### Procedura futura sul Samsung, non distruttiva

Da eseguire soltanto in un incarico separato e autorizzato:

1. registrare seriale, package, versione, `lastUpdateTime`, hash APK e località;
2. collegare DevTools alla WebView della sola pilota e identificare l'origine
   effettiva (`https://localhost`) senza cancellare dati;
3. acquisire `Storage.getUsageAndQuota`; se non disponibile, registrare
   separatamente `navigator.storage.estimate()` come stima, non misura della
   sola localStorage;
4. enumerare le sole chiavi, `String.length`, byte UTF-8 e SHA-256 dei valori,
   raggruppandoli per raw, bundle active/candidate, journal, UV e altri domini;
   non stampare i contenuti;
5. con `run-as com.meteofriul.app.localpilot`, leggere soltanto dimensioni e hash
   dei due `AtomicFile`, eventuali file di backup e preferenze native;
6. predisporre in DevTools un wrapper temporaneo e ripristinabile di
   `Storage.setItem/removeItem` che registri timestamp, chiave, lunghezze,
   occupazione prima/dopo ed eccezione senza alterare gli argomenti o assorbire
   errori;
7. acquisire snapshot prima, durante e dopo un solo refresh normale: hash
   `active`, presenza/dimensione `candidate`, journal e punto esatto
   dell'eventuale quota;
8. rimuovere sempre l'instrumentazione in `finally`; non usare `clear`,
   reinstallazione, riduzione delle serie o migrazione come prerequisito;
9. solo se autorizzato, chiudere e riaprire offline per verificare separatamente
   journal durevole, active ritrovato e assenza di stati parziali.

**Verifica mancante.** Occupazione/quota reale WebView, overhead effettivo dei
record, distribuzione per namespace, picco fisico `AtomicFile` e persistenza
dopo processo/riavvio sulla build corrente.

**Criterio di chiusura.** Una tabella prima/durante/dopo con quota e uso reali,
dimensioni per contenitore, write che fallisce o riesce, identità dei byte
promossi e riapertura senza svuotamento. Solo dopo questa misura si potrà
scegliere una correzione minima senza cancellazioni indiscriminate o migrazioni
preventive.

## Verifiche di questo incarico

Le suite live opt-in non sono state abilitate. Nessun comando ha contattato
provider live, telefono, cloud o Firebase.

La riga `npm run build` sotto è la baseline di produzione già eseguita nella
tranche precedente sul medesimo grafo applicativo. In questa integrazione, che
aggiunge soltanto test e documenti, non è stata ripetuta la scrittura di
`dist`; è stata eseguita la build diagnostica Vite `write:false` riportata in
`REG-05`.

| Comando | Esito |
| --- | --- |
| `npm run build` | build frontend e SW completata; baseline bundle riprodotta; restano i due warning prestazionali descritti in `REG-02`; `REG-05` resta indipendente dai warning |
| `npx vitest --configLoader native run src/features/weather/WeatherSkyCard.test.jsx src/features/almanac/AlmanacView.test.jsx` | 2 file, 3/3 test superati, 0 falliti, 0 saltati |
| `npx vitest --configLoader native run src/features/events/EventsView.test.jsx src/features/events/EventsView.preview.test.jsx src/services/eventsApi.test.js --reporter=verbose` | 3 file, 17/17 test superati, 0 falliti, 0 saltati |
| `npx vitest --configLoader native run src/app/AppRoutes.coldStartRevocation.test.jsx --reporter=verbose` | 1 file, 2/2 test superati, 0 falliti, 0 saltati; copre separatamente Meteo e Home |
| `npx eslint src/app/AppRoutes.coldStartRevocation.test.jsx` | superato, nessun messaggio |
| `npx vitest --configLoader native run src/app/App.coldStartRevocation.test.jsx src/app/AppRoutes.coldStartRevocation.test.jsx --reporter=verbose` | 2 file, 4/4 test superati, 0 falliti, 0 saltati; comprende avvio ordinario Home → Meteo negativo e controllo positivo; dopo `74f67e5` usa la lettura già effettuata dall'app |
| `npx eslint src/app/App.coldStartRevocation.test.jsx src/app/AppRoutes.coldStartRevocation.test.jsx` | superato, nessun messaggio |
| diagnostiche B05 repository prima della correzione | 0 superati, 3 falliti, 0 saltati; i tre fallimenti attesi sono stati conservati come baseline rossa |
| diagnostiche B05 service prima della correzione | 3 corse fallite come atteso; 4 controlli positivi superati; esecuzioni mirate separate |
| `& $backendPython -m pytest -q -c pytest.social-geo-diagnostics.ini <i 10 node-id B05>` | 10 superati, 0 falliti, 0 saltati; include repository, service, corse controllate e casi positivi |
| `& $backendPython -m pytest -q tests/test_community_b05_regressions.py` | 10 superati, 0 falliti, 0 saltati; B05 integrato nella raccolta ordinaria |
| `& $backendPython -m pytest -q tests/test_community_repository.py tests/test_community_service.py tests/test_live_api.py tests/test_community_moderation_tool.py tests/test_community_moderation_logging.py tests/test_community_moderation_digest.py tests/test_emit_community_moderation_digest_job.py tests/test_community_ttl_evidence_seed.py tests/test_pilot_security.py tests/test_community_b05_regressions.py` | 160 superati, 0 falliti, 0 saltati, 29 subtest; un warning Starlette/httpx preesistente |
| `& $backendPython -m pytest -q tests/test_community_service.py::CommunityServiceTests::test_confirmation_accepts_the_exact_play_300011_legacy_contract tests/test_live_api.py::LiveApiTests::test_confirmation_accepts_the_exact_play_300011_legacy_payload tests/test_pilot_security.py` | 23 superati, 0 falliti, 0 saltati, 13 subtest; stesso warning preesistente |
| `npx vitest --configLoader native run src/services/liveApi.test.js src/features/live/liveReportController.test.js src/features/live/LiveView.test.jsx src/services/firebaseAppCheckAdapter.test.js --reporter=dot` | 4 file, 76/76 test superati, 0 falliti, 0 saltati |
| prova temporanea `storageFootprint.measurement.test.js` | 1/1 test superato; file rimosso dopo avere registrato le sole misure locali sopra |
| `npx vitest --configLoader native run src/app/App.coldStartRevocation.test.jsx src/app/AppRoutes.coldStartRevocation.test.jsx src/services/localWeatherV1Runtime.revocation.test.js src/services/localWeatherV1Runtime.test.js src/services/weatherV1Client.test.js src/services/pilotWeatherPrefetch.test.js src/services/localWeatherPilotHome.test.js src/features/weather/uvForecastRuntime.test.js --reporter=dot` | 8 file, 280/280 test superati, 0 falliti, 0 saltati; 11,87 s |
| `npm test -- --maxWorkers=2` | 449 file superati, 4 saltati, 0 falliti; 3.524 test superati, 11 saltati, 0 falliti su 3.535; 95,21 s |
| `npm run lint` | superato, nessun errore o warning |
| `git diff --check` | superato |

Nelle raccolte finali pertinenti non compare alcun nuovo fallimento. Le tre
diagnostiche B05 prima rosse sono ora verdi e sono state collegate alla raccolta
ordinaria senza includere automaticamente le diagnostiche degli altri bug
ancora aperti. Una prima esecuzione dopo il nuovo vincolo transazionale ha
rilevato tre fixture repository che non creavano il target che pretendevano di
mutare: le fixture sono state rese realistiche e la raccolta finale è verde;
non era una regressione del comportamento applicativo.

Durante la prima esecuzione isolata del nuovo test una nuova asserzione cercava
il campo inesistente `icon_status`. Era un errore della prova, non un difetto
applicativo: l'asserzione è stata riallineata ai campi di contratto
`data_quality.run_utc`, `primary_source` e `hourly_forecast`; le esecuzioni finali
mirata e completa sopra sono verdi.

La raccolta mirata emette messaggi diagnostici attesi per il plugin Capacitor
già registrato e per lo snapshot pilota deliberatamente indisponibile nelle
prove negative. Non corrispondono a test falliti o saltati.

Gli 11 test saltati sono tutti opt-in e non sono stati eseguiti:

- 5 in `iconFallback.live.test.js`, richiedono
  `METEOFRIUL_RUN_ICON_FALLBACK_LIVE=1`;
- 3 in `localWeatherPilot.live.test.js` e 2 in
  `localWeatherAir.live.test.js`, richiedono
  `METEOFRIUL_RUN_LOCAL_PILOT_LIVE=1`;
- 1 benchmark in `weatherTiming.live.test.js`, richiede
  `METEOFRIUL_TIMING=1`.

I due messaggi prestazionali della build restano separati e non sono stati
nascosti:

1. `[INEFFECTIVE_DYNAMIC_IMPORT] src/features/almanac/AlmanacView.jsx is dynamically imported by src/app/AppRoutes.jsx but also statically imported by src/features/weather/WeatherSkyCard.jsx, dynamic import will not move module into another chunk.`
2. Il secondo messaggio completo è:

   ```text
   (!) Some chunks are larger than 500 kB after minification. Consider:
   - Using dynamic import() to code-split the application
   - Use build.rolldownOptions.output.codeSplitting to improve chunking: https://rolldown.rs/reference/OutputOptions.codeSplitting
   - Adjust chunk size limit for this warning via build.chunkSizeWarningLimit.
   ```

Nessuna delle proposte è stata applicata in questo incarico.

## Esclusioni rispettate

Nessun deploy o push remoto; nessuna build/sync/installazione Android; nessun
intervento sul Samsung; nessuna modifica a cloud, Firebase, App Check, worker,
push, localizzazione, scheduler, frequenze o soglie. Le modifiche funzionali
sono limitate al backend community condiviso richiesto da B05. `B06`, `B08`,
B01, REG-03, bundle e UI non sono stati modificati.
