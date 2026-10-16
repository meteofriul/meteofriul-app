# Pilot tutto Google — decisione e preparazione

Stato operativo più recente: [WEATHER_PILOT_CLOUD_ACTIVE_2026-09-06.md](WEATHER_PILOT_CLOUD_ACTIVE_2026-09-06.md). Le sezioni sottostanti sono cronologiche e includono blocchi poi risolti.

La richiesta dell'utente sostituisce la proposta R2: usare Cloud Run e Cloud Storage, senza attivare abbonamenti Cloudflare. Budget aggiuntivo massimo 5 EUR/mese; beta invariata.

## Verificato nell'account

- Progetto app `meteo-friul`: Cloud Run `meteofriul-api` in europe-west1.
- Firestore `(default)`, FIRESTORE_NATIVE, nam5: non destinato ai nuovi oggetti meteo.
- Bucket esistenti `meteo-friul_cloudbuild` e `run-sources-meteo-friul-europe-west1`: non riutilizzare per il pilot.
- Non esiste ancora un progetto identificato come pilot dedicato.

## Preparazione locale

Adapter `local_pipeline/gcs_object_store.py`, non ancora collegato ai runner cloud: creazione solo se assente (generation=0), aggiornamento condizionale sulla generazione, lettura vincolata alla generazione e verifica SHA-256, limite 16 MiB, nessun overwrite incondizionato o delete. Client Google iniettato; timeout 30 secondi, nessun retry SDK implicito. Nome bucket obbligatoriamente dedicato `meteofriul-pilot-*`, namespace `pilot/`; servono comunque IAM restrittive reali. Sei test unitari superati con SDK simulato, non test remoti.

L'adapter S3 precedente rimane sperimentale e inattivo; non è una dipendenza dell'opzione Google.

## Calcolo preliminare, non preventivo completo

Tariffe pubbliche consultate il 6 settembre: Cloud Run Jobs 0,000018 USD/vCPU-secondo e 0,000002 USD/GiB-secondo per la tariffa Tier 1 mostrata. Non applicare quote gratuite: sono aggregate per account di fatturazione.

Scenario da validare, non configurazione attivata: quattro esecuzioni complessive al giorno (due ICON, due CAMS), 1 vCPU e 1 GiB, massimo 20 minuti ciascuna, 31 giorni, nessun retry:

`4 * 31 * 1200 * (0,000018 + 0,000002) = 2,976 USD/mese`

Questo importo comprende soltanto il calcolo delle esecuzioni ipotizzate, non tutto il pilot. Non garantisce quattro nuove corse pubblicate al giorno. Restano scheduler, storage/operazioni, build/registry, secret, log, letture dei dispositivi, trasferimenti, eventuali altri tentativi, conversione EUR e imposte. Il tempo in coda CAMS va persistito e ripreso, non mantenuto indefinitamente in un container fatturato.

Prima di attivare: confermare SKU regionali/EUR applicabili, misurare runtime Linux, stabilire frequenza sufficiente alla freschezza, completare preventivo end-to-end e limiti di esecuzione/accesso/retention. Non basta un budget alert per garantire 5 EUR.

## Stato operativo

Nessun progetto, bucket, job o scheduler nuovo creato; nessuna fatturazione attivata. Telefono ancora collegato al reader PC. Mancano integrazione dei runner, stato remoto durevole, test Linux e reali Cloud Storage, servizio HTTPS pilot e attivazione della schedulazione.

Fonti: https://cloud.google.com/run/pricing ; https://cloud.google.com/storage/pricing ; https://cloud.google.com/scheduler/pricing ; https://docs.cloud.google.com/storage/docs/request-preconditions .

## Avanzamento successivo: progetto isolato e integrazione ICON

Creato `meteofriul-pilot-20260906` (nome Meteo Friul Pilot) con `--no-set-as-default`, senza collegamento alla fatturazione. Il CLI abilita automaticamente l'API di base cloudapis durante la creazione; non sono stati creati bucket, job, scheduler o servizi applicativi. Il progetto della beta `meteo-friul` non è stato modificato.

`publish_remote_icon.py` collega preparazione e publisher esistenti a store iniettati, senza cambiare il runner SQLite locale. `remote_publication_intent.py` conserva in storage condizionale l'identità e l'ora della prima pubblicazione: restart riutilizzano l'intento, input diversi falliscono, timeout ambiguo non causa scrittura ripetuta alla cieca. Stato e dati sono parametri separati; IAM e bucket separati restano da attuare.

Dieci test unitari passati (6 adapter GCS, 4 intenti remoti). Prova d'integrazione sugli artefatti ICON reali del 6 settembre, con due database SQLite temporanei come implementazione delle porte: prima esecuzione `published`, 215 payload; seconda `no_op/run_already_published`, 215 riutilizzati. Questa prova verifica l'orchestrazione, non l'API Google reale.

Da completare: adattamento stato/acquisizione CAMS, runtime Linux, integrazione SDK Google, preventivo complessivo, IAM e risorse con fatturazione, test remoti, servizio HTTPS e scheduler. Nessun cambiamento APK o dati del telefono in questo passaggio.

### Stato per-run su object store

Aggiunto `ObjectStateStore`: ogni run ha uno snapshot SQLite privato separato, scaricato in una directory temporanea e aggiornato sullo storage tramite CAS. Riutilizza la macchina a stati verificata, senza montare SQLite su filesystem di rete. Snapshot massimo 1 MiB, massimo tre conflitti CAS; un timeout ambiguo interrompe il tentativo. Nessun permesso acquisito localmente viene restituito prima del commit remoto. I token di esclusione del vecchio owner restano quelli della macchina a stati originale.

15 test combinati superati: 5 per snapshot di stato (inclusi due worker simultanei con un unico proprietario), 4 per intento di pubblicazione e 6 per adapter GCS. Test con storage locale/simulato: non provano ancora Google Cloud. L'adapter di stato non è ancora collegato al downloader ADS né attivato in un job. Va verificata anche la validazione della lease rispetto al tempo trascorso durante una CAS e lo scarto dell'orologio prima dell'uso remoto.

Nel primo test è stata corretta la chiusura esplicita della connessione SQLite di serializzazione, necessaria anche per rimuovere la directory temporanea su Windows. Nessuna risorsa cloud o app installata modificata durante questo passaggio.

### Downloader ADS: checkpoint persistenti

`retrieve_cams.retrieve` ora accetta un checkpoint_saver opzionale, chiamato prima del POST e dopo il salvataggio del request_id. Il comportamento locale resta predefinito. `retrieve_remote_cams.py` conserva solo quattro file JSON consentiti tramite storage iniettato; ripristina il job per `resume` e rifiuta una nuova submission quando esiste un intent senza job. Chiave stabile su data e hash della richiesta, non sul timestamp della raccolta metadati. Stato ambiguo richiede riconciliazione. Download e pubblicazione automatica end-to-end restano da integrare.

67 test combinati superati: downloader 49, wrapper remoto 3, object state 5, publication intent 4, GCS 6. Nessuna nuova richiesta ADS reale o attivazione cloud durante questi test.

### Blocco prima della fatturazione

La documentazione Google aggiornata contempla spend cap in preview per Cloud Run, ma non per tutti i servizi: ritardo nell'applicazione, richieste in corso e storage possono comunque generare costi oltre la soglia. Non equivale al tetto assoluto di 5 EUR precedentemente promesso. Serve chiarire se l'utente accetta un budget operativo stimato e controllato (non garantito al centesimo) prima di collegare la fatturazione e attivare il cloud. Non interpretare l'istruzione di completare la procedura come autorizzazione a superare il limite.

Fonte verificata: https://docs.cloud.google.com/billing/docs/how-to/budgets-spend-caps (limiti e costi oltre soglia).

### Attivazione infrastruttura autorizzata

Utente ha accettato il budget operativo (non hard cap) e confermato l'account di fatturazione. Collegato esclusivamente `meteofriul-pilot-20260906` all'account esistente. Abilitate API Storage, Cloud Build, Artifact Registry, Cloud Run, Scheduler, Secret Manager e Budget nel pilot. Nessuna API abilitata nella beta; la prima lettura dei budget ha segnalato API assente nel progetto predefinito e non è stata confermata l'attivazione lì.

Budget avvisi ID `cab20d26-b6b7-4a6c-8b4a-35f311bc13db`, 4 EUR mensili prudenziali, filtro solo progetto pilot e soglie 50/80/100%. È alerts-only, non arresto automatico.

Bucket privati `meteofriul-pilot-20260906-state` e `meteofriul-pilot-20260906-data`, europe-west1, uniform bucket-level access e public access prevention. Smoke GCS reale passato: create-only, hash in lettura, CAS e rifiuto generazione vecchia. Conservato oggetto diagnostico di pochi byte `pilot/smoke/f76d00810088484590b2798851a43fcb.json` nel bucket state.

Client google-cloud-storage 3.13.1 installato soltanto nell'ambiente Python pilot. Creata identità `pilot-build-check` nel pilot, con ruolo logging.logWriter; nessun ruolo Firebase/beta. Avviata una sola build Linux senza upload sorgenti o credenziali, timeout 600 s, ID `2acc3e48-686b-47b7-953d-f55ec0ac77cb`, regione europe-west1. Verificare esito prima di dichiarare runtime pronto. La build verifica import e libreria ecCodes nativa, non l'intera acquisizione.

Esito verificato della build: **SUCCESS**. Passata verifica Linux Python 3.13, import NumPy/ADS/GCS e creazione/rilascio handle GRIB2 ecCodes. Non è stata eseguita una nuova acquisizione né pubblicato un feed remoto. Scheduler e job automatici non ancora creati; budget presente solo come avvisi. Il pilot telefonico rimane dipendente dal reader locale. Il margine operativo di 5 EUR è accettato dall'utente, non è una garanzia di spesa assoluta.

### Integrazione CAMS e worker

`publish_remote_cams.py` connette la preparazione/commit CAMS a ObjectStateStore e all'intento remoto. Prova completa sui file reali del 6 settembre riuscita con store SQLite temporanei: family latest creato per `20260906T000000Z`, revisione 1. Copiati payload e report decodificati dentro la directory acquisizione per rispettare il contratto, senza cambiare gli originali.

### Immagine Linux verificata e blocco credenziale ADS

Build completa `96900114-2810-4781-ab2d-2dab14a6a6c9` riuscita. Successiva build `86142fa6-5905-493b-be6f-ae0df7e04f70` riuscita con 22 test mirati senza rete nel container e pubblicazione dell'immagine privata:
`europe-west1-docker.pkg.dev/meteofriul-pilot-20260906/pilot/weather-worker@sha256:394b2b9e4256f4db5332622631bdcfd5bbcb66571ecaef190d41fc4d773a384d`.

Upload limitato da allowlist a Python sperimentale e due cataloghi pubblici; nessun file di credenziali/configurazione beta. Bucket build privato dedicato, scadenza archivi a 7 giorni e soft delete disabilitato solo su questo bucket. La rimozione futura degli archivi scaduti non sarà recuperabile dal bucket. Nessun dato meteo rimosso.

ObjectStateStore considera il tempo monotono trascorso durante lettura/CAS e rifiuta di restituire una lease già scaduta. Test reale GCS con due worker concorrenti superato: un proprietario, record persistente e rilascio pulito. Non equivale ancora a verifica della pubblicazione completa remota.

Create le identità pilot-icon e pilot-cams nel solo progetto pilot, ancora senza ruoli runtime sui bucket. Registro pilot privato con ruolo writer alla sola identità di build (oltre ai permessi amministrativi ereditati).

Il controllo di sicurezza ha rifiutato PRIMA dell'esecuzione il comando di creazione del secret pilot-ads dal file locale .cdsapirc.TXT. Credenziale NON caricata; binding secretAccessor successivo NON eseguito. Serve consenso esplicito dell'utente al trasferimento del file verso Google Secret Manager nel progetto meteofriul-pilot-20260906, con accesso runtime limitato a pilot-cams. Non aggirare il rifiuto.

Restano IAM runtime, secret, job con limiti, prova completa remota, conto operativo, servizio HTTPS e scheduler. Nessun nuovo job o scheduler attivo; nessun cambiamento APK o beta.

### Consenso esplicito e credenziale ADS protetta

Dopo consenso esplicito dell'utente, creato `pilot-ads` versione 1 in Secret Manager nel progetto `meteofriul-pilot-20260906`, replica user-managed europe-west1. Verificata versione ENABLED tramite soli metadati. Assegnato secretAccessor sulla singola risorsa a `pilot-cams@meteofriul-pilot-20260906.iam.gserviceaccount.com`; nessun accesso assegnato a ICON o alla build. Restano gli accessi amministrativi ereditati del progetto. Contenuto non mostrato nei log né incluso nell'immagine o nell'APK. Nessun job o scheduler avviato in questo passaggio; beta invariata.

`cloud_worker.py` assembla le chiamate di acquisizione e pubblicazione, con guardia sul progetto pilot, credenziali ADS previste come secret montato e massimo due slot UTC per provider/giorno (include tentativi falliti). CAMS già pubblicato nello stesso giorno non viene riscaricato. Slot consumati non vengono ritentati alla cieca. Questo limite va valutato rispetto ai ritardi ADS: non garantisce due aggiornamenti riusciti al giorno. Il worker non è distribuito e non è ancora verificato end-to-end su Linux. Undici test mirati passati su worker/adapter GCS/wrapper ADS, inclusi rifiuto progetto beta e dispatch duplicato. Mancano build immagine completa, IAM runtime, secret ADS, test di acquisizione remota, scheduling e servizio HTTPS. Non presentare questi file come automazione attiva.
