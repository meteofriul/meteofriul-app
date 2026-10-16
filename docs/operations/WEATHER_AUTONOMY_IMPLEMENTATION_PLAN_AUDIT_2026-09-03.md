# Audit del piano di implementazione meteo autonomo — 3 settembre 2026

## Stato del documento

Questo documento sottopone a red-team il piano di passaggio da Open-Meteo a una
pipeline autonoma basata su ICON-2I e CAMS. Integra, senza sostituirli, i risultati
già raccolti in:

- `WEATHER_AUTONOMY_FEASIBILITY_2026-09-02.md`;
- `WEATHER_AUTONOMY_INTEGRATED_PILOT_2026-09-03.md`;
- `WEATHER_AUTONOMY_LOCAL_APP_2026-09-03.md`.

Il pilot locale dimostra la fattibilità tecnica. Non autorizza ancora il cutover
pubblico, perché non misura continuità operativa, affidabilità stagionale,
accuratezza territoriale o costo reale nel cloud.

Il presente audit non attiva job, scheduler, storage, deploy o modifiche ai flussi
OSMER e allerte.

Le decisioni approvate il 4 settembre 2026 e lo stato reale del pilot sono
registrati in `WEATHER_AUTONOMY_APPROVED_DECISIONS_2026-09-04.md`. Quel documento
costituisce il punto di ripartenza operativo e distingue quanto e gia verificato
in locale da cio che manca per l'ambiente reale.

Aggiornamento del 5 settembre 2026: il riferimento seguente a un singolo
`cams/latest.json` descriveva il piano originario. Il checkpoint locale ora usa
due collezioni CAMS immutabili (core e pollini), una release che le lega e un
solo `weather/v1/families/cams/latest.json`. I due `latest` di provider CAMS non
sono un percorso pubblico autorizzato. Dettagli e limiti aggiornati sono nel
documento delle decisioni approvate citato sopra.

## Verdetto

La direzione è corretta, ma il piano deve essere rafforzato prima dello shadow
cloud. Il rischio principale non è il costo di calcolo: sono l'accoppiamento fra
ICON e CAMS, le possibili richieste CAMS duplicate e la pubblicazione di un run
parziale o precedente a quello già esposto.

La decisione architetturale raccomandata è usare due circuiti indipendenti:

```text
Scheduler ICON -> Job ICON -> validazione -> oggetti ICON -> icon2i/latest.json
Scheduler CAMS -> Job CAMS -> staging core + pollini -> release -> families/cams/latest.json

Client compatibile -> compone localmente i due feed
OSMER e allerte    -> continuano sul circuito corrente, invariato
```

Due scheduler costano circa 0,10 USD/mese in più rispetto a un solo nuovo
scheduler, considerando che la quota gratuita corrente è già occupata dai tre
scheduler attivi. Questa differenza è giustificata dall'eliminazione di un punto
singolo di guasto e di una coda condivisa.

Riferimento: [prezzi Cloud Scheduler](https://cloud.google.com/scheduler/pricing).

## Confine non negoziabile: OSMER e allerte

Il nuovo sistema riguarda soltanto i dati numerici ICON e CAMS. Restano invariati:

- bollettino ufficiale OSMER;
- allerte ufficiali e relativo aggiornamento;
- cache e TTL delle allerte;
- scheduler esistenti;
- ruoli Firestore e FCM;
- contratti e rotte pubbliche ufficiali.

La separazione deve essere anche infrastrutturale: nuova immagine, nuovi job,
service account dedicati e privi di permessi Firestore/FCM, nuovi namespace di
cache e storage. Il nuovo client può comporre i feed soltanto nella presentazione.

Il bootstrap esistente non deve diventare un file statico con cache lunga. La
nuova versione legge ICON/CAMS dai feed versionati e interroga le rotte ufficiali
esistenti separatamente. Le versioni precedenti sono dichiarate non supportate:
il vecchio endpoint può restare soltanto come risposta controllata di aggiornamento
obbligatorio, senza una nuova pipeline meteo di compatibilità.

## P0 — bloccanti prima dello shadow cloud

### 1. Indipendenza completa tra ICON e CAMS

L'adapter locale corrente considera inutilizzabile l'intero pilot quando uno solo
dei due provider è assente o scaduto. In produzione devono essere separati:

- job e scheduler;
- puntatori di visibilita (`icon2i/latest.json` e il singolo family latest CAMS);
- stato di freschezza;
- cache client;
- fallback e kill switch;
- monitor e allarmi.

Un ritardo CAMS non può spegnere temperatura, condizione e previsione ICON. Un
problema ICON non può nascondere un dataset CAMS ancora valido.

### 2. Idempotenza e semantica dello scheduler

Cloud Scheduler ha semantica almeno-una-volta: una stessa scadenza può avviare più
esecuzioni. L'accettazione di `jobs:run` non equivale inoltre al completamento del
container. L'esito Cloud Run deve essere monitorato separatamente.

Ogni esecuzione deve avere una chiave stabile:

```text
provider + source_run_id + request_hash
```

Sono obbligatori:

- claim separati per provider e run, creati condizionalmente;
- rifiuto di due elaborazioni simultanee dello stesso run;
- avanzamento monotono: un run più vecchio non sostituisce quello pubblicato;
- verifica dell'ownership prima del commit pubblico;
- recovery basato sullo stato durevole, non su un nuovo tentativo cieco.

Riferimento: [Cloud Scheduler overview](https://cloud.google.com/scheduler/docs/overview).

### 3. Macchina a stati durevole per CAMS

Il `request_id` CAMS e l'intento di submission non possono risiedere soltanto nel
filesystem effimero del container. La macchina a stati minima è:

```text
INTENT -> SUBMITTED -> READY -> DOWNLOADED -> VALIDATED -> PUBLISHED
```

L'intento, comprensivo dell'hash esatto della richiesta, deve essere persistito
prima del POST. Il job parte con `maxRetries=0`, perché Cloud Run Jobs usa retry
automatici per impostazione predefinita.

Il caso ambiguo `POST accettato, ma crash prima di ricevere/salvare request_id`
deve essere provato contro l'API ADS. Se ADS consente di riconciliare le richieste
per account, orario e parametri, il job recupera quella esistente. Se non lo
consente, quello stato non deve generare automaticamente un secondo POST: richiede
un gate operativo o l'attesa del run successivo.

Riferimento: [creazione e configurazione dei Cloud Run Jobs](https://cloud.google.com/run/docs/create-jobs).

### 4. Scoperta di un run sorgente completo

Il run più recente non è necessariamente già completo. La discovery ICON deve
verificare la disponibilità stabile di tutti i campi e lead-time necessari e, se
il run è parziale, cercare a ritroso l'ultimo run completo.

La discovery CAMS deve distinguere:

- sorgente non ancora pubblicata;
- richiesta in coda;
- download fallito;
- decodifica fallita;
- validazione fallita;
- pubblicazione fallita.

Questi stati non devono essere riassunti in un generico errore del job.

### 5. Pubblicazione atomica e rollback

Per ICON il flusso di pubblicazione è:

1. produrre gli artefatti sotto un prefisso immutabile per `run_id`;
2. validarli localmente;
3. caricarli con semantica create-only (`If-None-Match`);
4. verificare direttamente dimensione, hash e metadati;
5. confermare la presenza del 100% del catalogo comunale versionato;
6. rileggere campioni attraverso il dominio pubblico;
7. aggiornare `latest.json` per ultimo con `ETag`/`If-Match`;
8. su conflitto `412`, rileggere e ripetere il confronto monotono;
9. conservare il riferimento al run precedente.

ICON e CAMS hanno manifest separati, così non possono sovrascriversi. Dentro
CAMS, core e pollini vengono messi in staging senza visibilita e una release
immutabile lega i due manifest dello stesso run; soltanto una CAS sul family
latest li rende visibili insieme. Un semplice lock non è sufficiente: un worker
può perdere la lease e proseguire comunque. La correttezza finale dipende dal
compare-and-swap del puntatore di visibilita.

Il rollback deve prevedere:

- pausa dello scheduler interessato;
- controllo e, se necessario, arresto delle esecuzioni ancora attive;
- ripristino condizionale del puntatore precedente;
- lista `disabled_run_ids` per revocare run immutabili errati;
- smoke test pubblico;
- purge mirato della sola cache del manifest, se necessario.

Riferimenti:

- [compatibilità S3 di R2](https://developers.cloudflare.com/r2/api/s3/api/);
- [consistenza di R2](https://developers.cloudflare.com/r2/reference/consistency/).

### 6. Identità stabile e catalogo comunale

La chiave canonica deve essere il codice ISTAT, non il nome, lo slug o le
coordinate GPS. Nome e slug restano alias di presentazione.

Prima di ogni pubblicazione sono necessari questi gate:

- codici ISTAT unici;
- crosswalk completo frontend/backend;
- copertura del 100% del catalogo versionato, attualmente 215 Comuni;
- hash e versione del catalogo inclusi nel manifest;
- revisione esplicita quando il catalogo amministrativo cambia.

Per Comuni molto estesi non va rifiutato automaticamente un utente distante oltre
10 km dal centroide. Il contratto deve chiarire che il dato rappresenta il punto
modello associato al Comune oppure usare un'associazione geografica autorevole.

### 7. Contratto JSON v1 e compatibilità delle app installate

Il nuovo endpoint/feed è consumato soltanto da client compatibili. Non si cambia
silenziosamente la semantica del bootstrap corrente.

Il contratto v1 deve includere:

- `schema_version`;
- `provider` e versione del modello;
- `istat_code`, nome e punto rappresentativo;
- `source_run_id`, `run_at`, `generated_at`;
- `valid_from`, `valid_to` e timezone;
- unità esplicite;
- intervallo rappresentato da pioggia e raffiche;
- regole di nullabilità;
- qualità e motivazione di eventuali campi mancanti;
- tassonomia esplicita per condizione, testo, icona e scenetta;
- provenienza della temperatura percepita;
- hash del contenuto canonico.

Il client deve rifiutare schema sconosciuto, `NaN`, Comune errato, timeline non
ordinata o discontinua, run futuro, unità sconosciute e hash non corrispondente.

La temperatura valida per l'ora corrente resta una previsione del modello, non
un'osservazione misurata. Fonte e orario del run devono essere disponibili nella
UI informativa.

### 8. Cache del dispositivo

La cache autonoma non riusa quella del bootstrap. La chiave consigliata è:

```text
provider:schema_version:istat_code:run_id
```

La freschezza deriva da `run_at`, `valid_from` e `valid_to`, non dall'ora in cui il
telefono ha salvato il file. Risalvare un run vecchio non deve ringiovanirlo.

Sono richiesti:

- limite massimo di Comuni e byte;
- espulsione LRU;
- ultimo run valido conservato per uso offline;
- divieto di usare dati oltre la scadenza assoluta;
- sostituzione atomica del dataset soltanto dopo download e validazione completi;
- cache e kill switch separati per ICON e CAMS.

Le 96 ore di copertura CAMS non equivalgono a 96 ore di freschezza. Anche le 48
ore ICON si riducono con l'età del run: ogni superficie deve dichiarare la propria
copertura minima residua.

### 9. Checkpoint per evitare riscaricamenti costosi

Un errore di upload non deve obbligare a riscaricare circa 1,09 GB ICON. È
raccomandato un piccolo bucket Cloud Storage privato in `europe-west1`, distinto
dal data plane pubblico R2, per:

- claim e stato CAMS;
- checkpoint del risultato ICON già estratto e validato;
- report di run e hash;
- ripresa dell'upload senza nuova acquisizione.

Il lifecycle può eliminare i checkpoint dopo 24-48 ore. I GRIB nazionali completi
non vanno conservati stabilmente. Questa soluzione non richiede Firestore né
modifiche a Firebase.

### 10. Licenze, credenziali e monetizzazione

Prima dell'unico rilascio pubblico devono essere chiusi e documentati:

- condizioni di uso schedulato e commerciale di ADS/CAMS;
- attribuzioni obbligatorie per CAMS e ICON-2I;
- proprietà operativa dell'account ADS;
- token CAMS in Secret Manager e procedura di rotazione;
- limiti, fair use e comportamento in caso di sospensione del servizio;
- fallback legalmente utilizzabile dopo l'introduzione della pubblicità;
- versione minima supportata e risposta di aggiornamento obbligatorio.

La licenza aperta del dato non dimostra da sola che ogni modalità di accesso API
possa essere automatizzata senza limiti. Questo punto rimane aperto finché non è
verificato sulle condizioni ufficiali applicabili all'account e al dataset.

## P1 — necessari prima dell'unico rilascio pubblico

### Immagini e risorse di esecuzione

- creare un'immagine job separata dal backend API;
- includere e pin-nare ecCodes, NumPy e client ADS;
- partire con 1 vCPU, 1 GiB e timeout 20-30 minuti;
- usare timeout interni inferiori per rete, coda, decodifica e upload;
- misurare picco memoria e P95/P99 su Linux prima di scendere a 512 MiB;
- eseguire ICON e CAMS in container distinti, evitando memoria nativa condivisa.

Cloud Run Jobs fattura ogni esecuzione per almeno un minuto. I controlli frequenti
che terminano senza lavoro vanno quindi conteggiati e, dopo il primo periodo di
osservazione, programmati sugli orari reali di pubblicazione delle fonti.

Riferimento: [prezzi Cloud Run](https://cloud.google.com/run/pricing).

### Archivio completo e payload pubblico distinti

Il requisito "acquisire tutto CAMS" significa acquisire e analizzare tutte le
variabili autorizzate; non significa inviarle tutte a ogni telefono.

Sono necessari almeno due livelli:

- archivio/analisi completo, privato;
- prodotto pubblico `core`, limitato ai campi effettivamente usati e validati.

Campi estesi o sperimentali non devono impedire la pubblicazione di quelli core.
Pollini e campi sperimentali rimangono store-only o beta fino a una validazione
stagionale adeguata.

### Cache HTTP e dominio pubblico

- manifest: `ETag`, TTL breve, per esempio 5 minuti;
- oggetti per run: immutabili e TTL lungo;
- Cache Rule "Cache Everything" limitata al solo prefisso meteo;
- Smart Tiered Cache, se disponibile nel piano usato;
- CORS configurato prima del riempimento della cache;
- origini Web e Capacitor testate realmente;
- `Content-Type`, `Content-Encoding`, `Vary` ed `ETag` verificati end-to-end;
- prova esplicita di `CF-Cache-Status: HIT` e risposta `304`;
- query string non necessarie ignorate o rifiutate per evitare cache busting;
- checksum definito sul JSON canonico decodificato;
- hard cap sugli artefatti caricabili, per impedire per errore l'upload dei GRIB.

Cloudflare non applica necessariamente la cache CDN ai JSON R2 senza una regola
esplicita.

Riferimento: [interazione R2 e cache Cloudflare](https://developers.cloudflare.com/cache/interaction-cloudflare-products/r2/).

### Inventario completo dei consumatori

La migrazione deve censire e testare almeno:

- hero: temperatura, percepita, condizione, icona e scenetta;
- riepilogo corrente;
- evoluzione a 48 ore;
- aggregazioni biorarie di pioggia e raffiche;
- notifiche meteo locali;
- worker Android in background;
- widget e service worker/offline cache;
- contesto meteo di Scopri/Eventi;
- eventuali superfici che oggi richiedono cinque giorni.

Il pilot ICON copre 48 ore. Oltre quell'orizzonte la UI deve dichiarare una fonte
separata, ridurre l'orizzonte oppure non mostrare il dato; non deve inventare una
previsione a cinque giorni.

### Divisione del lavoro tra backend e dispositivi

Il dispositivo può svolgere senza impatto percepibile:

- selezione del Comune e dell'ora;
- giorno/notte astronomico;
- conversioni di unità e preferenze;
- formattazione, icone e accessibilità;
- cache offline e scelta dell'ultimo run valido.

Restano centrali:

- download e decodifica GRIB;
- mapping geografico e controlli territoriali;
- temperatura percepita;
- vere aggregazioni biorarie;
- controlli meteorologici e di qualità;
- produzione, firma/hash e pubblicazione del JSON.

Nessuna credenziale ADS e nessun GRIB devono raggiungere il client.

### Osservabilità e limiti di costo

Una sola riga strutturata per fase deve registrare:

- provider e run;
- stato della macchina a stati;
- byte scaricati e caricati;
- durata di discovery, coda, download, decodifica, QA e upload;
- memoria massima;
- numero atteso/prodotto/rifiutato di Comuni;
- conflitti CAS;
- motivo di un no-op o fallimento;
- run effettivamente pubblicato.

Non vanno registrati token, URL firmati, header sensibili, valori completi 215 x 97
o coordinate precise. Comune e `run_id` possono comparire nei log di errore, ma
non come etichette metriche ad alta cardinalità.

Il budget deve distinguere uso lordo e fattura netta e includere:

- Cloud Run e relativo minimo per esecuzione;
- scheduler;
- Cloud Storage temporaneo;
- Secret Manager;
- Artifact Registry e build;
- log e metriche;
- egress Google verso R2 dei soli JSON compatti;
- richieste e storage R2.

## P2 — ottimizzazioni successive

- deduplicare le celle CAMS condivise da più Comuni, dopo aver stabilizzato il
  contratto;
- risolvere localmente il codice ISTAT e non inviare coordinate GPS esatte al CDN;
- aggiungere firma del manifest e, se utile, retention protetta dei run recenti;
- introdurre WAF/rate limiting contro scraping patologico soltanto sulla base di
  misure reali;
- predisporre un cold standby manuale, evitando active-active che potrebbe
  duplicare richieste CAMS;
- valutare giurisdizione EU/location hint del bucket R2 prima della creazione;
- ottimizzare compressione e concorrenza degli upload solo dopo misure cloud.

## Piano di implementazione revisionato

### Fase 0 — decisioni e contratti

- [ ] Chiudere condizioni commerciali, attribuzioni e accesso ADS automatizzato.
- [ ] Definire contratto JSON v1 e tassonomia delle condizioni.
- [ ] Rendere ISTAT la chiave canonica e versionare il catalogo.
- [ ] Inventariare tutte le superfici Web/Android interessate.
- [ ] Definire prodotto pubblico CAMS core e archivio esteso.
- [ ] Definire comportamento oltre le 48 ore ICON.
- [ ] Definire fallback commerciale e versione minima supportata.

### Fase 1 — pipeline riproducibili e isolate

- [ ] Creare immagine ICON separata.
- [ ] Creare immagine CAMS separata.
- [ ] Creare service account senza ruoli OSMER, Firestore o FCM.
- [ ] Implementare discovery di run completi.
- [ ] Implementare claim idempotenti per provider/run.
- [ ] Implementare macchina a stati CAMS durevole.
- [ ] Impostare inizialmente `maxRetries=0`.
- [ ] Aggiungere checkpoint compatti con lifecycle 24-48 ore.

### Fase 2 — pubblicazione e cache

- [ ] Creare prefissi R2 versionati separati per ICON e CAMS.
- [ ] Implementare upload create-only e verifica hash/metadati.
- [ ] Implementare manifest separati con CAS e ordine monotono.
- [ ] Aggiungere puntatore precedente e revoca dei run errati.
- [ ] Configurare custom domain, cache rule, CORS e header.
- [ ] Verificare cache `MISS -> HIT`, `304`, gzip e Android/Web.
- [ ] Definire lifecycle per artefatti orfani e run storici.

### Fase 3 — client compatibili

- [ ] Aggiungere una nuova base URL dati con release guard.
- [ ] Validare rigorosamente schema, identità, timeline, hash e scadenza.
- [ ] Implementare cache per provider/run con LRU.
- [ ] Comporre ICON e CAMS senza modificare OSMER/allerte.
- [ ] Aggiungere feature flag e kill switch indipendenti.
- [ ] Verificare hero, scenetta, percepita, 48 ore e background Android.
- [ ] Restituire un aggiornamento obbligatorio ai client non supportati.

### Fase 4 — CI e prove di guasto

- [ ] Fixture GRIB/NetCDF piccole e riproducibili, senza rete in CI.
- [ ] Test di contratto sul 100% del catalogo comunale.
- [ ] Build e smoke Linux amd64 con ecCodes.
- [ ] Scansione dipendenze e immagine pin-nata per digest.
- [ ] Test crash prima/dopo l'intento CAMS.
- [ ] Test crash subito prima/dopo il POST CAMS.
- [ ] Test upload parziale dei Comuni.
- [ ] Test crash prima/dopo il commit del manifest.
- [ ] Test di due esecuzioni simultanee dello stesso run.
- [ ] Test di tentativo di pubblicazione di un run più vecchio.
- [ ] Test R2 `412`, `5xx`, timeout e hash incompatibile.
- [ ] Test rollback, run revocato, CORS, cache e compressione.
- [ ] Test UTC/Europe-Rome e cambi d'ora.

### Fase 5 — shadow cloud e misure

- [ ] Eseguire almeno 7 giorni per misurare costo e ritardi delle fonti.
- [ ] Registrare separatamente acquisition, coda, decode, QA e publish.
- [ ] Calibrare gli orari degli scheduler sui ritardi reali.
- [ ] Proseguire almeno 30 giorni per affidabilità operativa.
- [ ] Mantenere il prodotto invisibile agli utenti durante lo shadow.
- [ ] Verificare che OSMER e allerte non mostrino alcuna regressione.

I 7 giorni non sono un test di accuratezza. I 30 giorni non rappresentano tutte le
stagioni e non dimostrano un SLA annuale.

### Fase 6 — validazione meteorologica

- [ ] Definire una fonte osservativa legalmente riutilizzabile per la validazione.
- [ ] Pre-registrare stazioni, matching temporale/spaziale e metriche.
- [ ] Separare montagna, pianura e costa.
- [ ] Raccogliere almeno 7.000 coppie orarie su almeno 10 stazioni.
- [ ] Misurare bias/RMSE temperatura, errori vento, pressione e umidità.
- [ ] Validare pioggia su finestre esatte e un numero sufficiente di eventi.
- [ ] Validare separatamente pollini e fenomeni stagionali.
- [ ] Estendere idealmente l'osservazione ad almeno 90 giorni e più regimi meteo.

Le osservazioni OSMER possono essere usate per confronto privato soltanto dopo la
verifica dei termini applicabili; non diventano per questo una dipendenza runtime
o una nuova fonte pubblica dell'app.

### Fase 7 — unico rilascio pubblico

- [ ] Completare prima tutti i test deterministici sul PC.
- [ ] Provare Web mobile e APK debug via USB/ADB, senza distribuzione.
- [ ] Eseguire lo shadow cloud invisibile agli utenti per i soli aspetti che non
  possono essere misurati localmente.
- [ ] Produrre insieme la build Web e la nuova versione Android sul contratto v1.
- [ ] Impostare la nuova sorgente come predefinita per tutti al rilascio.
- [ ] Impostare `minimum_supported_version` per rifiutare le versioni obsolete.
- [ ] Conservare Open-Meteo nel codice come kill switch d'emergenza disattivato.
- [ ] Effettuare un solo rilascio pubblico, senza canary o gruppi intermedi.

## Gate di avanzamento

### Gate A — autorizzazione allo shadow cloud

Tutti i P0 devono essere chiusi. Devono passare i test di idempotenza, crash,
pubblicazione atomica, rollback e isolamento OSMER/allerte.

### Gate B — autorizzazione all'unico rilascio pubblico

- zero pubblicazioni parziali o con hash errato;
- zero regressioni del manifest a un run più vecchio;
- zero hard-expiry causate dalla pipeline nel periodo di osservazione;
- nessuna doppia submission CAMS non riconciliata;
- copertura del 100% del catalogo versionato;
- cache e CORS verificati sul percorso realmente usato dall'app;
- costo mensile proiettato entro il budget concordato;
- contratto e kill switch provati su Web e Android;
- affidabilità operativa osservata per il periodo deciso prima del test;
- soglie meteorologiche concordate e superate per i campi pubblicati;
- fallback commerciale e versione minima obbligatoria verificati;
- attribuzioni visibili e credenziali con rotazione documentata;
- rollback eseguito almeno una volta come esercitazione;
- approvazione esplicita dell'operatore.

## Decisioni ancora aperte

Prima dell'implementazione vanno fissate esplicitamente:

1. quali variabili CAMS costituiscono il prodotto pubblico `core`;
2. quale copertura residua minima è accettabile per ciascuna schermata;
3. cosa mostrare oltre le 48 ore ICON;
4. quale fonte osservativa usare per la validazione;
5. quale fallback sia ammesso dopo la monetizzazione;
6. come gestire la finestra ambigua CAMS se ADS non consente la riconciliazione;
7. durata di conservazione di run, checkpoint e report;
8. budget massimo mensile e soglie di arresto automatico.

## Conclusione

Si può procedere senza ripetere il pilot locale già completato. Contratto v1 con
identità ISTAT, macchina a stati CAMS e pubblicazione atomica della famiglia
core-pollini, compresi revoca e rollback atomici, sono ora completati e
verificati nel gate locale. Il prossimo lavoro non è il deploy: sono gli adapter
durevoli di stato/object store e l'hardening di lease, fencing e tolleranza allo
scarto dell'orologio prima di qualsiasi definizione cloud attiva.

Fino al superamento del Gate B, ICON e CAMS restano locali o in shadow e non
sostituiscono i dati numerici visibili agli utenti. Il passaggio pubblico avviene
una sola volta con la nuova versione; le versioni obsolete non ricevono un nuovo
servizio meteo. OSMER e allerte restano fuori dal perimetro in ogni fase.
