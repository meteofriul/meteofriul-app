# Piano di rollout nazionale della Community

Stato: **piano tecnico; nessuna attivazione nazionale autorizzata da questo documento**  
Data: 20 settembre 2026  
Perimetro: segnalazioni meteo strutturate della sezione Territorio, dalla
risoluzione geografica alla lettura pubblica, scrittura, cache, storage e
moderazione.

## 1. Obiettivo

Rendere disponibili in tutta Italia le segnalazioni effimere di fenomeni
meteo senza trasformare il feed in una raccolta nazionale indistinta e senza
indebolire il contratto privacy e UGC approvato per la pilota FVG.

L'obiettivo finale è questo:

- una persona può inviare una segnalazione da qualunque Comune italiano
  riconosciuto dal registry canonico;
- la posizione GPS serve soltanto a verificare il luogo e non viene pubblicata
  né conservata come coordinata grezza;
- l'app legge soltanto le celle necessarie alla mappa o alla località attiva;
- località omonime, Comuni confinanti e cambi di regione non possono
  contaminare gruppi, cache o moderazione;
- un errore di identità geografica disabilita la mutazione in modo esplicito,
  senza fallback basati sul nome;
- capacità e costi crescono con le celle effettivamente lette e con le
  segnalazioni attive, non con una scansione dell'intera Italia.

Questo piano non introduce testo libero, fotografie, video, profili pubblici o
messaggi tra utenti.

## 2. Stato reale al punto di partenza

### 2.1 Policy e interfaccia

La policy territoriale dichiara già la lettura Community con scope Italia, ma
abilita la scrittura soltanto nella regione `IT-36` (Friuli Venezia Giulia).
Il frontend ripete la stessa decisione: in Italia il feed può essere letto,
mentre fuori FVG il comando di invio è disabilitato con il motivo stabile
`community_region_not_enabled`.

Questa è una separazione utile, ma **non significa che il feed sia già
nazionale**. Oggi tutte le segnalazioni accettabili nascono dal catalogo e dai
confini FVG.

### 2.2 Risoluzione geografica e scrittura

Il backend corrente:

- usa un catalogo canonico di 215 Comuni FVG;
- verifica che il punto sia nei limiti geografici FVG;
- conferma il Comune tramite il resolver di confine FVG;
- accetta la correzione manuale soltanto verso un nome presente nel catalogo;
- richiede che il punto sia entro 5 km dalla zona canonica selezionata;
- pubblica il punto canonico comunale/zonale, non le coordinate GPS ricevute;
- costruisce il `group_id` da fenomeno, nome del luogo e bucket temporale.

Il motore di ricerca nazionale può restituire località italiane tramite
Nominatim, ma fuori FVG il codice ISTAT può essere assente. Il risultato del
geocoder non è quindi un'identità sufficiente per autorizzare una scrittura.

Il solo nome non può diventare la chiave nazionale: esistono omonimi e il nome
può cambiare forma, lingua o punteggiatura.

### 2.3 Lettura e cache

`GET /api/community/reports` non riceve oggi località, celle, raggio o bounding
box. Il repository legge al massimo 200 report attivi e il client conserva una
sola cache globale `liveCommunityReports:v1`.

Questa soluzione è bounded per la pilota, ma non è adatta a un feed nazionale:

- i 200 report più recenti d'Italia potrebbero escludere completamente una
  regione poco attiva;
- un utente caricherebbe dati lontani che non vede;
- la cache di una zona potrebbe essere mostrata dopo un cambio di località;
- refresh e moderazione dipenderebbero da scansioni globali.

### 2.4 Safety e moderazione già riutilizzabili

Il contratto esistente offre una base forte:

- App Check sulle mutazioni;
- identità di installazione pseudonima;
- otto tipi di segnalazione chiusi;
- nessun testo libero o media;
- accettazione obbligatoria delle linee guida correnti;
- durata pubblica di 60 minuti;
- cooldown di 45 minuti;
- conferme, flag, nascondi fonte e annullamento;
- nessun occultamento globale automatico causato da una soglia di flag;
- TTL e retention bounded per le collection private;
- nessuna coordinata GPS o chiave privata nel payload pubblico.

Queste invarianti devono restare. Tuttavia, il contratto di sicurezza contiene
anche assunzioni FVG esplicite, incluso il conteggio del catalogo pari a 215.
La coda/digest di moderazione è inoltre bounded a 200 gruppi azionabili
complessivi. Prima dell'apertura nazionale servono una nuova versione del
contratto e una capacità partizionata.

Lo stato effettivo di job, scheduler, indici e TTL nel progetto cloud non viene
dedotto dal solo codice: va verificato con i relativi audit LIVE prima di ogni
rilascio.

## 3. Invarianti privacy e safety nazionali

Il rollout nazionale deve conservare questi vincoli come condizioni bloccanti.

1. **GPS transitorio.** Latitudine, longitudine, accuratezza e istante della
   posizione servono alla richiesta corrente; non diventano campi pubblici e
   non devono entrare in log, analytics, digest o messaggi di errore.
2. **Posizione pubblica zonale.** Il report pubblico espone il centro di una
   cella privacy-safe o un altro punto rappresentativo approvato, mai il punto
   ricevuto dal dispositivo.
3. **Identità territoriale canonica.** Regione, provincia e Comune derivano dal
   registry versionato e dal point-in-polygon server-side. Il nome inviato dal
   client è solo presentazione, non autorizzazione.
4. **Nessun fallback permissivo.** Registry mancante, versione incompatibile,
   punto fuori Italia, confine ambiguo o cella non risolta producono un rifiuto
   esplicito; non si ripiega sul Comune più vicino o su Nominatim.
5. **Contenuto chiuso.** Restano vietati testo libero, media, profili e
   comunicazioni dirette.
6. **Retenzione invariata salvo nuovo audit.** I report pubblici durano 60
   minuti; cooldown, flag, blocchi e ledger rispettano le retention già
   documentate. Un'estensione richiede una nuova decisione privacy.
7. **Moderazione azionabile.** Ogni gruppo deve poter essere ricondotto, nello
   strumento privato, ai report e alle fonti che lo compongono senza esporre
   chiavi private al client o nei log.
8. **Fail closed sul client e sul backend.** Il gate UI migliora la chiarezza,
   ma il backend resta l'autorità per tutte le mutazioni.

## 4. Registry geografico nazionale

### 4.1 Un'unica identità comunale condivisa

Va introdotto un registry nazionale versionato, usato in modo coerente da
ricerca, Community, previsioni e targeting delle allerte. Ogni Comune deve
avere almeno:

```text
istatCode
name
provinceCode
provinceName
regionCode
regionName
countryCode = IT
centroidLat
centroidLon
registryVersion
```

Il registry pubblico compatto può contenere identità e punti rappresentativi.
I poligoni amministrativi, più pesanti, restano un asset backend versionato per
il point-in-polygon e non devono essere scaricati dall'app per autorizzare una
segnalazione.

Il conteggio dei Comuni non va codificato come costante eterna. Contratto e
audit devono fissare `registryVersion`, conteggio e hash attesi per una release,
così fusioni o variazioni ISTAT diventano una migrazione esplicita.

### 4.2 Arricchimento della ricerca nazionale

Un risultato Nominatim privo di ISTAT non può essere inviato direttamente alla
Community. Coordinate e metadati del risultato vanno risolti contro il registry
nazionale; soltanto il record canonico risultante può essere salvato tra le
località e usato per una mutazione.

La ricerca resta utile come discovery, mentre l'identità amministrativa viene
dal dataset controllato dall'app.

### 4.3 Resolver nazionale

Il resolver backend deve:

1. verificare che il punto sia in Italia;
2. determinare il poligono comunale contenente il punto;
3. restituire codice ISTAT, regione e provincia dalla stessa versione del
   registry;
4. rilevare punti su confini o geometrie non risolte senza scegliere in modo
   arbitrario;
5. produrre una cella Community privacy-safe;
6. scartare le coordinate grezze al termine della richiesta.

La regola attuale dei 5 km dal centro comunale non è trasferibile a tutta
Italia: Comuni estesi o con forma irregolare produrrebbero falsi rifiuti e
concentrerebbero tutte le segnalazioni nello stesso centro urbano.

## 5. Cella Community privacy-safe

La cella Community è distinta sia dal Comune ISTAT sia dalla cella ICON usata
per le previsioni.

- `municipalityIstat` descrive l'amministrazione;
- `forecastCellId` identifica una cella del modello meteo;
- `communityCellId` identifica la zona pubblica e interrogabile delle
  segnalazioni.

Confondere questi tre concetti renderebbe fragile privacy, cache e grouping.

La prima versione della griglia Community deve avere:

- copertura completa del territorio italiano;
- ID deterministico e versionato;
- dimensione adatta a mostrare un fenomeno locale senza ricostruire il punto
  dell'utente; il diametro finale va approvato con un test privacy/utilità,
  indicativamente nell'ordine di più chilometri e non di isolato;
- punto pubblico rappresentativo deterministico;
- mapping bounded `bbox -> cellIds`;
- relazione deterministica con Comune, provincia e regione;
- nessun ID derivato da lat/lon in chiaro o reversibile a precisione GPS.

Il payload persistito deve contenere il punto pubblico della cella e
`location_precision = zone`. Le coordinate ricevute dal dispositivo non devono
essere incluse nel documento Firestore, neppure come campo privato di comodo.

Il grouping nazionale deve usare almeno:

```text
reportType + communityCellId + timeBucket
```

e non `reportType + placeName + timeBucket`. Il Comune ISTAT resta nel report
per display, filtri e audit, ma la cella impedisce che un grande Comune diventi
un unico episodio meteorologico.

## 6. Contratto di scrittura v2

Il comando client deve sostituire `selected_place` testuale con un riferimento
canonico, per esempio:

```json
{
  "type_id": "rain",
  "lat": 43.7262,
  "lon": 12.6363,
  "selected_municipality_istat": "041067",
  "registry_version": "istat-municipalities-v1",
  "accepted_terms": true,
  "policy_version": "community-guidelines-v2",
  "client_id": "..."
}
```

Lat/lon restano necessari per provare la presenza corrente, ma il backend deve
risolverli autonomamente. L'eventuale Comune selezionato è accettabile soltanto
se coerente con il punto e con le regole esplicite di correzione di confine.

Il documento interno sanitizzato dovrebbe aggiungere almeno:

```text
country_code
region_code
province_code
municipality_istat
municipality_name_snapshot
community_cell_id
community_cell_version
public_lat
public_lon
```

I nomi sono snapshot di presentazione; codici e versioni sono le identità.

Durante la transizione il backend deve accettare il contratto legacy soltanto
per client e località FVG supportati. Il client nazionale non deve poter
cadere silenziosamente sul writer v1.

## 7. Lettura per bounding box e celle

### 7.1 API bounded

La lettura pubblica deve richiedere un perimetro. Un contratto possibile è:

```text
GET /api/community/reports?bbox=minLon,minLat,maxLon,maxLat&zoom=Z&cursor=...
```

Il backend:

1. valida dimensione e coordinate della bbox;
2. limita estensione e numero massimo di celle;
3. converte la bbox in `communityCellId` della versione corrente;
4. interroga soltanto quelle celle e i report non scaduti;
5. restituisce un cursore bounded se il limite viene raggiunto;
6. dichiara celle e versione coperte nella risposta.

Un endpoint a celle esplicite può essere aggiunto per il client nativo, ma deve
accettare un numero massimo di ID validi. Nessuna variante può significare
"senza parametri = tutta Italia" dopo il cutover v2.

Le query Firestore su più celle vanno suddivise in batch entro i limiti del
provider e riunite con ordinamento deterministico. Non si deve affidare la
correttezza a una singola query nazionale limitata ai record più recenti.

### 7.2 Vista locale e vista larga

- A zoom locale si caricano le celle visibili più un piccolo margine di
  prefetch.
- A zoom regionale si possono restituire gruppi aggregati per cella.
- Una bbox nazionale intera non restituisce report individuali: usa aggregati
  bounded oppure viene rifiutata.
- Il cambio di località o viewport annulla/ignora le risposte tardive della
  richiesta precedente.

La risposta deve includere `queryId`, `cellVersion`, `coveredCellIds`,
`generatedAt` e `nextCursor` quando necessario. In questo modo il client può
dimostrare che il contenuto appartiene alla viewport corrente.

## 8. Cache client e server

La cache globale corrente va sostituita da cache partizionate. Una chiave
client minima deve includere:

```text
schemaVersion + communityCellVersion + hash(cellIds) + zoomBand
```

Regole:

- non usare città o etichetta visuale come chiave;
- non riutilizzare una cache se la versione della griglia è cambiata;
- unire entry soltanto se cella e versione coincidono;
- rimuovere report scaduti prima della visualizzazione, anche se la cache
  dispositivo non è ancora scaduta;
- impedire che una risposta tardiva scriva nella cache della viewport nuova;
- conservare un limite LRU di entry/celle per evitare crescita illimitata;
- mantenere la cache webcam separata dalla cache Community.

Anche il backend può usare una cache breve per insieme di celle, ma la scadenza
non può superare il primo report in scadenza contenuto nella risposta.

## 9. Firestore e indici

Il modello di lettura nazionale deve essere progettato prima di creare gli
indici. Gli indici minimi da valutare e verificare con query reali sono:

| Collection | Campi | Uso |
| --- | --- | --- |
| `community_reports` | `community_cell_id ASC`, `expires_at_timestamp DESC` | feed di celle attive |
| `community_reports` | `region_code ASC`, `expires_at_timestamp DESC` | audit e fallback operativo regionale bounded |
| `community_reports` | `group_id ASC`, `expires_at_timestamp DESC` | conferme, flag e ricostruzione gruppo |
| `community_report_moderation` | `moderation_shard ASC`, `expires_at_timestamp DESC` | code di moderazione partizionate |
| `community_report_flags` | `moderation_shard ASC`, `expires_at_timestamp DESC` | triage privato per shard |

Gli indici esatti dipendono dalle query finali e vanno generati e testati in un
progetto staging. Non vanno aggiunti indici globali inutilizzati "per
sicurezza".

Ogni writer deve continuare a produrre `expires_at_timestamp` col tipo corretto.
Il gate di rilascio deve verificare policy TTL, indici `READY`, query explain o
smoke equivalente e assenza di documenti non conformi.

I report legacy FVG scadono in 60 minuti. È preferibile un periodo breve di
dual-read/dual-contract controllato rispetto a un backfill permanente di dati
effimeri già prossimi alla scadenza.

## 10. Rate limit e capacità

Un limite globale unico che funzionava in una pilota regionale può bloccare
utenti legittimi durante un temporale nazionale. Restano necessari:

- cooldown per installazione;
- limite per installazione e finestra;
- limite di emergenza per progetto;
- limite partizionato per `region_code` o `community_cell_id`;
- protezione da hot spot sulla stessa cella/gruppo;
- idempotenza di retry e mutazioni.

I limiti non devono essere calibrati soltanto sui test sintetici. Prima del
rollout completo vanno provati con scenari di picco, incluse molte celle attive
nello stesso minuto e una singola cella con elevata partecipazione.

## 11. Moderazione nazionale sharded

Il comportamento pubblico resta invariato:

- il flag nasconde subito il contenuto al segnalante;
- nessuna soglia di flag nasconde automaticamente il contenuto per tutti;
- il blocco locale della fonte resta temporaneo;
- l'intervento globale resta una decisione operatore auditabile.

La capacità privata deve però essere partizionata. Ogni report, flag e stato di
moderazione riceve un `moderation_shard` deterministico, derivato da regione e
un numero bounded di partizioni tecniche. Il valore non contiene GPS.

Il collector nazionale deve:

1. leggere uno shard alla volta con cursore;
2. fallire chiuso se uno shard supera il limite previsto, senza dichiarare
   completa una lettura parziale;
3. conservare `group_ref` opachi nei log e nei digest;
4. consentire allo strumento privato di risolvere il riferimento nel relativo
   shard;
5. misurare backlog, età del flag più vecchio e capacità per regione;
6. evitare un unico limite nazionale di 200 gruppi azionabili.

L'attivazione di job, scheduler, digest o recapito esterno richiede un audit
separato su privacy, Data Safety, retention dei log e identità cloud. Il piano
nazionale non li abilita implicitamente.

Prima dell'apertura in produzione va ripetuto il gate UGC: il documento
attuale approva esplicitamente la creazione in FVG e non può essere interpretato
come autorizzazione automatica nazionale.

## 12. Contratto di sicurezza v2

La risposta Community deve esporre un contratto macchina aggiornato, per
esempio `community-ephemeral-safety-v2`, contenente almeno:

- versione e hash del registry comunale;
- versione della griglia Community;
- precisione pubblica `zone`;
- tipi consentiti;
- TTL e cooldown;
- capacità massima della query;
- schema bbox/celle;
- assenza di testo, media e account;
- versione delle linee guida;
- regioni abilitate alla scrittura o stato nazionale.

Il frontend deve confrontare il contratto atteso prima di abilitare l'invio.
Un client vecchio può continuare a operare nella corsia FVG legacy soltanto
finché il backend la dichiara compatibile; non può creare report nazionali.

## 13. Rollout fail-closed

### Fase A — dataset e test offline

- creare registry, hash e poligoni nazionali versionati;
- verificare unicità ISTAT, regione/provincia e punti rappresentativi;
- confrontare ricerca manuale e reverse GPS su campioni di tutte le regioni,
  confini, isole e Comuni omonimi;
- definire e sottoporre a review la griglia privacy-safe;
- nessun writer nazionale attivo.

### Fase B — backend v2 in shadow

- risolvere le richieste di test in Comune e cella senza persistere report;
- confrontare decisioni con fixture controllate;
- creare indici staging e misurare latenza/costo delle query a celle;
- verificare che nessun log contenga GPS o identificatori privati;
- lasciare `COMMUNITY_WRITE_REGIONS` limitato al FVG.

### Fase C — lettura nazionale bounded

- pubblicare endpoint bbox/celle e cache v2;
- mantenere i writer non FVG chiusi;
- testare viewport, cambio località, risposte tardive, offline e paginazione;
- dimostrare che nessuna richiesta senza scope restituisce il feed nazionale.

### Fase D — canary di scrittura

- abilitare una allowlist di regioni o cohort di test tramite configurazione
  backend, mai solo tramite frontend;
- verificare TTL LIVE, App Check, rate limit, flag, blocchi e operatività della
  moderazione per ogni shard coinvolto;
- mantenere un kill switch che chiuda nuove scritture senza eliminare i report
  ancora validi o rompere la lettura.

### Fase E — Italia

- abilitare tutte le regioni soltanto dopo il superamento dei gate;
- osservare error rate, latenza, query/document reads, hot spot, backlog di
  moderazione e rifiuti geografici;
- non aumentare precisione, retention o tipi di contenuto durante lo stesso
  cutover;
- mantenere rollback alla precedente allowlist territoriale.

Ordine di distribuzione: backend compatibile, indici e TTL, smoke LIVE, poi
frontend web/Android. Il client nazionale non deve precedere il writer
autoritativo.

## 14. Codici di errore stabili

Oltre ai codici esistenti, il contratto v2 dovrebbe distinguere almeno:

```text
community_country_not_supported
community_registry_version_mismatch
community_municipality_unresolved
community_municipality_mismatch
community_boundary_ambiguous
community_cell_unresolved
community_query_scope_required
community_query_scope_too_large
community_schema_upgrade_required
```

Questi casi non sono errori di rete. La UI deve spiegare il limite e non
ritentare automaticamente una mutazione territorialmente non valida.

## 15. Osservabilità senza dati sensibili

Metriche ammesse e utili:

- conteggi per regione/cella tecnica aggregata;
- esito del resolver per codice motivo;
- latenze point-in-polygon e query;
- numero di celle richieste e documenti letti;
- rate-limit, cooldown e App Check rifiutati;
- backlog di moderazione per shard;
- report attivi e scaduti aggregati.

Sono vietati nei log applicativi e nelle metriche:

- coordinate GPS ricevute;
- `client_id`, installation ID, owner key o hash non scoped destinati alla
  correlazione privata;
- payload completi di mutazione;
- mapping pubblico tra `group_ref` e fonte interna.

## 16. Criteri di accettazione

Il rollout nazionale non è pronto finché non sono vere tutte le condizioni:

- due Comuni omonimi producono identità, celle, gruppi e cache distinti;
- un punto fuori Italia o su confine irrisolto non crea alcun report;
- il documento persistito e i log non contengono il GPS ricevuto;
- la mappa di Urbino non scarica report di Pordenone se le viewport non si
  sovrappongono;
- cambiando rapidamente località, una risposta tardiva non ripristina i dati
  della località precedente;
- una bbox oltre il limite è rifiutata e non degrada a feed globale;
- un picco in una regione non esaurisce il limite funzionale delle altre;
- conferma, flag, nascondi fonte, undo e reputazione funzionano con ID v2;
- lo strumento privato ricostruisce tutti i report di un gruppo senza mostrare
  chiavi private nei log;
- TTL e indici risultano conformi da read-back LIVE;
- il kill switch regionale/nazionale è provato;
- client legacy FVG e client v2 non contaminano rispettivamente dati e cache;
- il nuovo gate UGC nazionale è approvato prima della distribuzione.

## 17. Confini con gli altri prodotti

Queste funzioni condividono la località dell'app, ma non vanno fuse con la
Community.

### Webcam

Il manifest attuale è un catalogo editoriale FVG. Può essere reso consultabile
anche da una località fuori regione, ma deve restare etichettato come
**Webcam dal Friuli Venezia Giulia** e non come webcam vicine alla località
nazionale. Non usa bbox/celle Community. Permessi, attribuzioni e gate per
provider restano bloccanti e indipendenti da questo rollout.

### Scopri e Almanacco

Restano contenuti editoriali FVG con un `editorialContext` indipendente dalla
località meteo. La scheda comunale compare soltanto per un Comune FVG
riconosciuto. Fuori regione l'interfaccia deve rendere esplicita l'edizione FVG,
senza attribuire a Urbino, Roma o Palermo racconti comunali friulani.

Gli elementi astronomici dipendenti dalla posizione, come alba e tramonto,
possono seguire la località meteo nazionale; proverbi, memoria e cultura
restano nel contesto editoriale. Questa separazione non modifica la Community.

### OSMER e allerte

Il bollettino OSMER resta una fonte regionale FVG. Può essere consultabile
fuori regione come contenuto informativo con scope e fonte visibili, ma non
deve essere presentato come previsione locale della città selezionata.

La consultazione del bollettino non iscrive automaticamente alle allerte FVG.
Le allerte ufficiali per una località nazionale richiedono un adapter e un
resolver di zona dedicati; non derivano dalle segnalazioni Community e non
possono usare conferme o reputazione degli utenti come fonte ufficiale.

## 18. Decisione architetturale

Si può procedere verso la copertura nazionale, ma la sequenza corretta è:

```text
registry ISTAT + poligoni
        -> cella Community privacy-safe
        -> writer v2 fail-closed
        -> query bbox/celle + cache v2
        -> Firestore/index/TTL staging
        -> moderazione sharded e nuovo gate UGC
        -> canary
        -> Italia
```

Cambiare soltanto `COMMUNITY_WRITE_REGIONS` da FVG a Italia esporrebbe
collisioni tra omonimi, letture globali incomplete, cache contaminate e una
coda di moderazione non dimensionata. Quel cambio deve essere l'ultimo passo,
non il primo.
