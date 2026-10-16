# Meteo Friul UI 3.0.0 - Inventario runtime e sorgenti dati

Data: 2026-08-10
Stato: audit operativo UI 3.0.0

## Scopo

Questo documento chiarisce cosa nella UI 3.0.0 e' gia collegato a dati reali, cosa usa cache o fallback, cosa e' ancora laboratorio e cosa va recuperato dalla vecchia app.

La regola di lavoro resta:

```text
audit -> contratto dati -> collegamento controllato -> test -> UI
```

Non si deve migliorare la grafica mentre i flussi dati restano ambigui.

## Avvio locale controllato

La UI 3.0.0 usa uno script locale dedicato per evitare di confondere la nuova interfaccia con il vecchio frontend:

```powershell
scripts\start-dev.ps1 -CheckOnly
scripts\start-dev.ps1 -Restart
scripts\start-dev.ps1 -Stop
```

Contratto operativo corrente:

- nuova API modulare UI3: cartella `backend`, porta `8002`;
- frontend UI3: cartella `frontend`, porta `5173`;
- tutto `/api/*` e' proxato alla nuova API UI3 `8002`;
- il backend storico sulla porta `8001` e' spento per default e si avvia soltanto
  per confronto o rollback con `scripts\start-dev.ps1 -WithLegacyBackend`;
- non esiste piu un fallback implicito dal frontend UI3 al backend storico;
- log locali: `.dev-logs\ui3-backend.log`, `.dev-logs\ui3-api.log` e `.dev-logs\ui3-frontend.log`.

Questo assetto mantiene il rollback disponibile senza copiare il vecchio
frontend o il backend monolitico dentro UI3.

## Legenda

| Stato | Significato |
| --- | --- |
| Reale | Legge endpoint o dominio dati gia collegato. |
| Cache | Legge localStorage o ultimo payload salvato prima della rete. |
| Fallback controllato | Tiene la UI viva senza fingere dato ufficiale. |
| Dato locale curato | JSON o archivio interno revisionabile. |
| Fixture/lab | Dato dimostrativo, non valido come produzione. |
| UI only | Schermata o riga visiva non ancora collegata. |
| Audit required | Va confrontato con vecchia app o backend prima di promuoverlo. |

## Sintesi netta

La UI 3.0.0 usa la nuova API modulare per tutte le route web runtime attive:
localita, Territorio, Eventi, meteo locale, Bollettino, allerte e radar. Scopri
e Almanacco usano archivi locali curati.

Pero' non e' ancora la app completa:

- Territorio (`tab=live`) usa la nuova API modulare per webcam e mappa sociale;
- Eventi usa la nuova API, cache, filtri e ranking testato; fonti e qualita dati
  restano sotto manutenzione editoriale;
- GPS browser con consenso esplicito e reverse sono collegati in Opzioni solo come flusso laboratorio/web;
- il gate Android finale e' stato auditato dalla vecchia app: prompt GPS nativo all'apertura, poi prompt notifiche nativo dopo localita risolta/scelta;
- la ricerca localita ha ora registry comuni FVG completo; il comune visualizzato resta separato dalla posizione dispositivo;
- il Bollettino separa fonte ufficiale OSMER, dati locali Open-Meteo e radar;
- l'Almanacco usa dati locali, non sorgenti live;
- ogni fallback statico deve essere confinato al laboratorio o reso neutro.

## Inventario per area

| Area | Sorgente attuale UI 3 | Stato | Rischio | Prossima azione |
| --- | --- | --- | --- | --- |
| Comune visualizzato | `defaultLocation` in localStorage, `DEFAULT_APP_LOCATION` come fallback | Cache / fallback controllato | E' il contesto che l'utente sta guardando, non per forza dove si trova | Mantenerlo separato dalla posizione dispositivo |
| Recenti localita | `recentLocations` in localStorage | Cache locale | Lista utile ma non e' fonte ufficiale comuni | Mantenere; aggiungere reset solo in Opzioni quando progettato |
| Ricerca localita | Catalogo canonico dei 215 Comuni + `GET /api/location/search` sulla API UI3 | Reale + fallback locale | Alias e toponimi FUR non sono ancora completi | Mantenere un solo catalogo generato e versionato |
| Posizione dispositivo GPS/reverse web | `deviceLocation` + `GET /api/location/reverse` sulla API UI3 | Reale web | Non e' il gate Android definitivo; non deve sovrascrivere un comune scelto manualmente | Conservare cache 7 giorni e collegare in seguito il bridge Android esplicito |
| Gate Android GPS/notifiche | `PERMISSIONS_GPS_PUSH_AUDIT.md` + `frontend/src/domain/startup/androidPermissionGate.js` | Contratto puro / non collegato | Va collegato senza finestre custom: prompt GPS nativo all'apertura, poi notifiche native dopo localita risolta/scelta | Importare orchestratore startup Android e test APK/emulatore prima del push live |
| Home meteo corrente | `GET /api/weather/bootstrap` via `fetchWeatherBootstrap` | Reale + cache | Se cache vecchia o rete KO va comunicato senza bloccare | Collegare esito refresh reale a feedback non invasivo |
| Home hero fallback | `homeFixture` solo come fallback visuale controllato | Fixture/lab | Non deve fingere dati per localita diversa | Tenere confinato; eliminare fallback produttivi non necessari |
| Home sintesi bollettino | `buildBulletinViewModel()` su stesso payload bootstrap | Reale quando OSMER c'e | Il fallback statico poteva mostrare vecchia sintesi | Corretto: niente piu sintesi statica se il Bollettino reale manca |
| Home almanacco teaser | `buildAlmanacViewModel()` sul giorno corrente | Dato locale curato | Deve restare coerente con la pagina Almanacco | Conservare un solo modello dati per Home e Almanacco |
| Home eventi teaser | `GET /api/local/events` + `eventsCache:v11` | Reale + cache | Deve restare coerente con la pagina Eventi completa | Verificare periodicamente conteggio Home vs pagina |
| Bollettino | `GET /api/weather/bootstrap`, `forecast.official`, `forecast.osmer_structured` | Reale + cache | Fonte non raggiungibile o stale non deve sembrare bollettino corrente | Continuare audit giorno per giorno e stato fonte |
| Bollettino mappa | SVG Meteo Friul + A1-A9 da `osmer_structured` | Reale se A1-A9 complete | Non inventare marker se mancano aree | Mantenere regola: base mappa senza marker se dato ufficiale manca |
| Quinto giorno | Slot calendario derivato da date ufficiali/strutturate | Reale / pending controllato | Mostrare testo sbagliato se si usa indice invece di data | Continuare binding per `forecastDate`, non per posizione array |
| FUR bollettino | Seconda faccia del giorno IT quando presente | Audit required | Alcuni payload FUR possono avere date tecniche incoerenti | Usare calendario IT come asse; passata FUR separata |
| Allerte ufficiali | Nuova API UI3 + snapshot Firestore confermato dalla Protezione Civile FVG | Reale quando la fonte regionale e' raggiungibile; indisponibilita esplicita negli altri casi | La sorgente FVG non e' raggiungibile in modo affidabile da Cloud Run/GitHub; DPC resta diagnostica | Definire un canale di ingestione ufficiale affidabile prima del cutover; nessun falso stato verde |
| Avvisi locali meteo | Dominio candidate/local notices in audit, non UI live | Audit required | Rumore push se la priorita temporale e' sbagliata | Continuare con algoritmo candidato e finestre temporali testate |
| Almanacco | `domain/almanac`, JSON santi, proverbi, Ostermann, sole/luna | Dato locale curato | Proverbi e Ostermann non completi, FUR da revisionare | Completare archivio e collegare teaser Home al dato reale |
| Eventi pagina | `GET /api/local/events` + `eventsDataController` + `buildEventsViewModel()` | Reale + cache / backend modulare | Va mantenuta la separazione: controller/cache fuori dalla view | Manutenzione fonti, immagini e qualita editoriale |
| Territorio (`tab=live`) | `LiveView` + nuova API UI3 `/api/live` e `/api/community` | Reale + cache / backend modulare | UGC strutturato ed effimero: otto fenomeni e Comune canonico pubblici per 60 min; `client_id` casuale locale trasmesso solo nelle mutazioni, hash server scoped e `sourceKey` pubblica rotante; App Check, flag con hide locale, blocco fonte e intervento globale manuale eventuale; retention 45 min/60 min/2 h/24 h; digest/outbox, log ready, scheduler ed email esclusi dal runtime della prima beta, con collection TTL dormiente ammessa | Verificare `COMMUNITY_STORAGE=firestore`, gate effimero e TTL; applicare `COMMUNITY_PRIVACY_DATA_SAFETY_HANDOFF.md` prima dell'AAB senza attivare il digest dormiente |
| Scopri pagina | `DiscoverView` + archivi editoriali locali curati | Dato locale curato | Copertura e revisione editoriale restano da mantenere | Conservare dati locali separati dai servizi runtime |
| Opzioni | Lingua, tema, comune, GPS web esplicito, preferenze notifiche e reset cache | Reale web / nativo parziale | Le preferenze notifiche non equivalgono al permesso o al push Android | Collegare gate e push soltanto nel wrapper Android |
| Refresh/cache runtime | Controller dati + `runtimeRefreshPolicy.js` + `pullRefreshPolicy.js` + shell | Reale web | Resta da collaudare su APK/emulatore | Conservare dati validi durante refresh e rifiutare cache oltre la finestra del dominio |
| Cache reset | Azione in Opzioni per cache meteo Home, Eventi e Territorio | Reale | Non deve cancellare preferenze, Bollettino ufficiale o contenuti editoriali locali | Mantenere il perimetro esplicito e testato |
| Notifiche push | Dominio e documenti pronti, nessuna UI/live push | Audit required | Mai attivare da componente visuale | Tranche separata backend/APK/permessi |

## Correzioni consolidate

La route Home non usa `staticData.bulletin` come fallback se
`buildHomeBulletinFromData()` non produce un Bollettino reale e costruisce il
teaser Almanacco dallo stesso view model della pagina completa.

Motivo:

- una sintesi statica puo sembrare un dato ufficiale corrente;
- se OSMER non e' raggiungibile la Home deve restare prudente;
- il fallback corretto e' copy neutra tipo "Bollettino in preparazione" o stato non raggiungibile, non un testo datato.

File:

```text
frontend/src/app/AppRoutes.jsx
```

## Debiti tecnici da non dimenticare

### Dati e reattivita

- verificare pull-to-refresh UI3 su APK/emulatore;
- importare orchestratore refresh manuale;
- mantenere i test cache valida/scaduta e fonte non raggiungibile per ogni dominio runtime;
- non svuotare dati validi durante refresh;
- Home meteo: refresh fallito non deve recuperare cache meteo oltre la finestra controllata;
- Home Eventi: refresh fallito con cache disponibile resta visibile come `stale`, non come errore vuoto;
- Bollettino: refresh fallito non deve cancellare cache OSMER ufficiale ancora entro finestra controllata;
- Bollettino: cache OSMER troppo vecchia non deve essere mostrata come dato corrente;
- non mischiare cache fra localita diverse.

### Localita

- mantenere registry comuni FVG unico;
- mantenere coordinate con fonte e note;
- includere alias e forme FUR dove utili;
- mappare provincia e zona meteo;
- distinguere sempre comune visualizzato e posizione dispositivo;
- se l'utente sceglie manualmente un comune, il GPS non deve intervenire automaticamente;
- GPS in Opzioni usa consenso esplicito solo per laboratorio/web;
- su APK il primo avvio deve usare prompt GPS nativo, poi prompt notifiche nativo dopo localita risolta/scelta;
- fuori FVG non cambia localita attiva;
- Android bridge e auto-check foreground restano da auditare.

### Eventi

- pagina reale importata con filtri tempo/categoria e cache;
- confermare periodicamente conteggio Home vs pagina Eventi;
- continuare audit fonti, ranking, categorie e immagini;
- mantenere stati `refreshing` e `partial` senza lista vuota durante refresh.

### Bollettino

- mantenere audit giorno per giorno;
- mantenere `Non ancora emesso` solo quando manca davvero il dato ufficiale;
- non usare fixture o proiezioni come dato utente;
- continuare controllo IT/FUR per data, testo, mappa e attendibilita.

### Opzioni

- ogni riga deve diventare azione reale o restare informativa chiara;
- GPS nativo e notifiche push richiedono tranche Android dedicate;
- nessuna UI custom deve sostituire i prompt nativi Android per GPS/notifiche.

## Ordine consigliato da ora

1. Chiudere il collaudo web con API assente e cache valida/scaduta per ogni dominio runtime.
2. [x] Provare la nuova API su una revisione Cloud Run senza traffico con
   `COMMUNITY_STORAGE=firestore` e collaudare tutte le route runtime.
3. [x] Creare un canale Hosting di anteprima collegato alla revisione UI3 e
   ripetere l'audit conclusivo IT/FUR e light/dark sul dominio remoto.
   Canale `ui3-beta` collaudato l'11 agosto 2026 senza modificare il sito live.
4. Solo dopo creare il wrapper Android e collegare il gate nativo GPS -> notifiche.
5. Attivare il push reale soltanto dopo test APK/emulatore e policy di invio approvata.
