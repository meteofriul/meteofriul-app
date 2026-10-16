# Cloud Run runtime IAM: audit e migrazione least-privilege

Data audit live in sola lettura: 23 agosto 2026.
Decisione Community: 25 agosto 2026.

Stato di questo documento: procedura preparatoria. Nessun service account, ruolo,
binding IAM, servizio, job, revisione, traffico o scheduler e' stato modificato.
Per la prima beta il digest Community e' una contingenza dormiente: non va creato
e non fa parte della topologia runtime richiesta.

## Esito sintetico

Il rischio e' confermato ma il presupposto iniziale va corretto: non tutti i job
usano il Compute Engine default service account.

| Workload | Identita' osservata o contrattuale | Accesso richiesto dal codice |
| --- | --- | --- |
| servizio `meteofriul-api` | `49007668366-compute@developer.gserviceaccount.com` | Firestore RW/transazioni; FCM nei percorsi push abilitati |
| job `meteofriul-alert-sync-pilot` | Compute default | Firestore RW/transazioni; FCM quando il modo e' `send` |
| job `meteofriul-local-notice-owner-pilot` | Compute default | Firestore RW/transazioni; FCM quando il modo e' `send` |
| job `meteofriul-event-source-shadow` | `event-source-monitor@meteo-friul.iam.gserviceaccount.com` | Firestore RW |
| job `meteofriul-event-source-publication-control` | `event-source-monitor@meteo-friul.iam.gserviceaccount.com` | Firestore RW |

Il Compute default ha ancora `roles/editor`. `event-source-monitor` ha gia'
`roles/datastore.user` e non risulta abilitato a FCM. Non sono richiesti service
account, ruoli, job o scheduler per il digest Community nella prima beta. Tutte
le risorse runtime attive restano in `europe-west1`.

Un secondo consumer e' stato confermato: `gcloud builds get-default-service-account`
e le ultime sei build del 20 agosto indicano ancora il Compute default SA. I tre
Cloud Scheduler attivi usano invece `official-alert-scheduler` o
`event-source-scheduler`. Compute Engine, Cloud Functions e Cloud Asset Inventory
sono disabilitati; App Engine API e' abilitata ma il progetto non contiene
un'applicazione App Engine. Nessuna API e' stata abilitata durante l'audit.

Le configurazioni runtime non contengono `FIREBASE_SERVICE_ACCOUNT_JSON`,
`FIREBASE_SERVICE_ACCOUNT_B64`, `FIREBASE_CREDENTIALS_PATH` o
`GOOGLE_APPLICATION_CREDENTIALS`, quindi ADC usera' davvero la service identity.
Quattro immagini sono fissate per digest; `meteofriul-alert-sync-pilot` conserva
invece il tag `e8ce2b1-alerts` e deve essere pin-nato al digest risolto prima di
superare `TargetReady`.

La topologia approvata e obbligatoria e':

- mantenere i due job Eventi su `event-source-monitor`, con solo
  `roles/datastore.user`;
- spostare API, sync allerte e delivery locale su
  `meteofriul-runtime@meteo-friul.iam.gserviceaccount.com`;
- assegnare a quest'ultimo `roles/datastore.user` e un ruolo custom contenente
  esclusivamente `cloudmessaging.messages.create`.

Il gate rifiuta un target uguale al Compute default o a `event-source-monitor`.
Non e' supportata una variante a SA unico, perche' darebbe ai job Eventi il permesso
FCM e cancellerebbe il confine least-privilege scelto.

## Evidenza dal codice e ruoli minimi

`backend/app/infrastructure/firebase.py` usa Application Default Credentials in
Cloud Run. I repository `community.py`, `official_alerts.py`, `push.py`,
`local_notice_shadow.py`, `local_notice_delivery.py` ed `event_sources.py`
eseguono letture, scritture, batch e transazioni Firestore. Il ruolo predefinito
minimo pratico e' quindi `roles/datastore.user`; `roles/datastore.viewer` non basta.

`backend/app/push/fcm.py` chiama `firebase_admin.messaging.send`. L'unica
permission Cloud Messaging necessaria al percorso osservato e'
`cloudmessaging.messages.create`. Il ruolo predefinito documentato da Google,
`roles/firebasecloudmessaging.admin`, include anche gestione delle topic
subscription e lettura delivery data: e' utilizzabile come fallback, ma non e'
il minimo stretto. Il gate finale richiede percio' un ruolo custom di progetto
con una sola permission.

Non assegnare al runtime `roles/iam.serviceAccountUser`, Artifact Registry Reader,
Cloud Run Admin o Logs Writer: il primo serve al soggetto che allega l'identita'
alla revisione/job, l'immagine viene gestita dal service agent Cloud Run e stdout /
stderr sono raccolti dalla piattaforma. Aggiungere ruoli solo se una chiamata
applicativa nuova viene dimostrata da codice e smoke test.

Riferimenti ufficiali:

- Firestore server client e `roles/datastore.user`: https://cloud.google.com/firestore/docs/security/iam
- ruolo e permission FCM: https://cloud.google.com/iam/docs/roles-permissions/firebasecloudmessaging
- Firebase Admin SDK e ruolo sender: https://firebase.google.com/docs/cloud-messaging/send/admin-sdk
- identita' Cloud Run e `iam.serviceAccounts.actAs`: https://cloud.google.com/run/docs/configuring/services/service-identity
- revisioni senza traffico e rollback: https://cloud.google.com/run/docs/rollouts-rollbacks-traffic-migration

## Gate audit-only

`audit-cloud-run-runtime-iam.ps1` inventaria i quattro job realmente attivi e
non richiede job, scheduler o service account del digest Community. Il gate
effimero autorevole resta quello eseguito da `build-play-aab.ps1`; questa
procedura IAM verifica separatamente le identita' dei workload attivi e non
attiva la collection TTL dormiente.

Lo script non contiene comandi di creazione, update, execute, deploy o modifica IAM.
Legge solo account, progetto, descrizioni Cloud Run, policy IAM e definizione del
ruolo custom. Per il servizio legge `status.traffic`, include anche i target taggati
allo 0%, risolve con `run revisions describe` ogni revisione referenziata e la
`latestReadyRevision`, quindi confronta service account, stato e digest. Un errore
di rete, un account diverso, una risorsa in piu' o in meno, una revisione non
risolta, un entrypoint cambiato o un ruolo troppo ampio arrestano il gate.

```powershell
# Stato attuale verificato: deve passare l'inventario e mostrare Editor come debito.
powershell -NoProfile -File scripts/audit-cloud-run-runtime-iam.ps1 -Stage Baseline

# Dopo la preparazione IAM, prima di cambiare i workload.
powershell -NoProfile -File scripts/audit-cloud-run-runtime-iam.ps1 -Stage TargetReady

# Dopo lo spostamento delle identita', durante la finestra rollback.
powershell -NoProfile -File scripts/audit-cloud-run-runtime-iam.ps1 `
  -Stage Cutover -RollbackRevision meteofriul-api-<REVISIONE-LEGACY>

# Solo dopo osservazione e rimozione del ruolo legacy.
powershell -NoProfile -File scripts/audit-cloud-run-runtime-iam.ps1 `
  -Stage Final -RollbackRevision meteofriul-api-<REVISIONE-LEGACY>
```

Exit code `0` significa gate coerente; `2` significa stato letto correttamente ma
con blocker; `1` significa audit non affidabile. Gli exit `1` e `2` vietano di
procedere con questa migrazione IAM, non con l'AAB disciplinato dal gate
effimero. Le fixture non contengono valori d'ambiente o identificativi device:

```powershell
powershell -NoProfile -File scripts/audit-cloud-run-runtime-iam.ps1 `
  -FixturePath scripts/fixtures/cloud-run-runtime-iam-baseline.json -Stage Baseline
powershell -NoProfile -File scripts/cloud-run-runtime-iam-audit.contract.tests.ps1
```

## Procedura futura (da non eseguire senza approvazione)

### 0. Snapshot e confine

1. Registrare digest immutabili, revisioni, traffico, configurazioni complete dei
   cinque workload Cloud Run attivi (un servizio e quattro job), IAM policy con `etag`,
   scheduler/invocatori e metriche baseline.
   Conservare gli snapshot in una directory di change protetta, senza secret.
   Risolvere e fissare il digest del job allerte in una modifica separata: il gate
   non consente di cambiare insieme immagine e service identity.
2. Enumerare ogni risorsa del progetto che usa il Compute default SA, non soltanto
   Cloud Run. Se Compute, Functions, App Engine, Scheduler OIDC o un workload non
   inventariato lo usa, il gate `Final` resta vietato. Cloud Build e' gia' un
   consumer confermato: prima del gate finale deve passare a un build SA dedicato
   con i soli permessi di build/push necessari, o ogni submit deve specificare e
   dimostrare un'identita' diversa; il runtime SA non va riutilizzato per le build.
3. Confermare account `meteofriul@gmail.com`, progetto `meteo-friul`, numero
   `49007668366` e regione `europe-west1`. Qualsiasi divergenza arresta il change.
4. Congelare deploy concorrenti e scheduler dei job durante la finestra. Non cambiare
   contemporaneamente immagine, variabili, segreti, scaling o logica applicativa.

### 1. Preparazione IAM, nessun cambio runtime

Con approvazione separata, creare il SA target e il ruolo custom sender.
Non creare identita', binding o invocatori per il digest Community dormiente.
Vincolare `roles/datastore.user` al database `(default)` quando la policy IAM
condizionale adottata dal progetto lo consente. Concedere al solo deployer autorizzato
`roles/iam.serviceAccountUser` sul target. Non toccare ancora `roles/editor` del
Compute default. Eseguire `TargetReady`: deve essere verde e il ruolo custom deve
contenere esattamente `cloudmessaging.messages.create`.

### 2. Prove credenziali prima del traffico

Con impersonazione autorizzata del SA target:

1. eseguire una query Firestore read-only su un documento noto;
2. creare e cancellare un documento deterministico sotto una collezione smoke
   dedicata, verificando alla fine che sia assente; non usare collezioni prodotto;
3. chiamare FCM HTTP v1 con `validate_only=true` e un token owner controllato, senza
   stampare token/access token. Il risultato deve dimostrare autorizzazione
   `cloudmessaging.messages.create` e nessun messaggio consegnato.

Un `403`, credenziale non impersonabile, cleanup Firestore non confermato o risposta
FCM ambigua blocca il change. Non sostituire il test FCM con il normale modo
applicativo `dry_run`: quel modo evita intenzionalmente di contattare FCM e quindi
non prova il permesso IAM.

### 3. Servizio API a traffico zero

Creare una nuova revisione della stessa immagine per digest, cambiando soltanto
l'identita' e usando `--no-traffic` con un tag IAM-canary univoco. Verificare:

- revisione `Ready`, digest e variabili identici allo snapshot;
- endpoint tagged health, bootstrap, allerte, Eventi e letture community;
- scrittura/cancellazione smoke autenticata e App Check sui percorsi protetti;
- log senza `PERMISSION_DENIED`, `DefaultCredentialsError` o fallback a memoria.

Il fatto che `latestReadyRevision` usi il nuovo SA non prova il cutover. Il gate
accetta `Cutover`/`Final` soltanto se ogni revisione con percentuale maggiore di
zero usa il runtime SA. La revisione legacy dichiarata con `-RollbackRevision`
deve restare risolta e taggata, ma con percentuale esattamente zero.

Spostare prima una quota minima di traffico sul canary; osservare error rate,
latenza, startup e Firestore. Solo dopo portare il tag applicativo e poi il traffico
previsto alla nuova revisione. Non usare `latest` e non cambiare il rewrite Hosting
nella stessa operazione.

Rollback servizio: riportare immediatamente il 100% alla revisione annotata nello
snapshot. La vecchia revisione conserva il Compute default SA e continua a
funzionare finche' il binding legacy necessario non viene rimosso; per questo la
rimozione e' deliberatamente posticipata.

### 4. Job, uno alla volta e senza esecuzione implicita

I job non ricevono traffico: l'update del template non li esegue. Per ciascun job,
nell'ordine shadow Eventi, publication `status`, sync allerte e delivery locale:

1. verificare che nessuna esecuzione sia attiva e che lo scheduler sia sospeso;
2. confrontare `serviceAccountName` con la mappa approvata; i due job Eventi
   usano l'identita' dedicata esistente, mentre per i due job sul Compute default
   si cambia soltanto `serviceAccountName`, conservando digest, comando,
   argomenti, retry, timeout, env e secret esatti;
3. dopo ogni singolo cambio usare `run jobs describe` in sola lettura e confrontare
   identita', digest e configurazione con lo snapshot firmato; lo stage `Cutover`
   e' intenzionalmente all-or-nothing e va eseguito soltanto dopo che API, sync
   allerte e delivery locale risultano tutti sulla nuova identita';
4. eseguire manualmente lo smoke controllato e leggere exit code/log strutturato;
5. riattivare lo scheduler di quel solo job dopo una finestra verde.

Per `publication-control` usare esclusivamente l'azione `status`. Per sync allerte e
delivery locale non eseguire uno smoke con configurazione `send`: usare una copia
canary/no-schedule con `dry_run`, oppure limitarsi ai probe impersonati della fase 2.
Mai alterare il job produttivo in `send` per fare una prova IAM.

Rollback job: aggiornare il template allo `serviceAccountName` salvato nello
snapshot e allo stesso digest/configurazione, quindi ripetere un solo smoke sicuro.
Se un job ha prodotto scritture parziali, applicare il runbook applicativo di
deduplica/outbox; non rilanciare alla cieca.

### 5. Osservazione e chiusura

Mantenere temporaneamente il binding legacy necessario sul Compute default per una
finestra rollback definita, ma senza assegnargli nuovi workload. Osservare almeno un
ciclo reale di ciascun job e traffico API rappresentativo. Il gate `Final` richiede:

- tutte e sole le identita' attese;
- target con Firestore + singola permission FCM;
- Eventi con Firestore e senza FCM;
- ogni revisione con traffico nonzero sul runtime SA e rollback legacy taggato allo 0%;
- nessuna dipendenza residua dal Compute default;
- Cloud Build con identita' dedicata diversa dal Compute default, dal runtime push
  e da `event-source-monitor`;
- assenza sia di `roles/editor` sia di `roles/owner` sul Compute default.

La rimozione di `roles/editor` o `roles/owner` e' una modifica IAM distruttiva
rispetto al rollback: va approvata a parte, eseguita con etag/policy aggiornata e
seguita subito dal gate `Final`. In caso di regressione, ripristinare il binding
dalla policy snapshot, riportare servizio/job alle identita' precedenti e aprire un
incidente; non ampliare il nuovo SA con ruoli primitivi per aggirare il problema.

## Criteri di arresto

Il change si ferma se compare anche uno solo di questi casi: account/progetto non
attesi; inventario diverso da 1 servizio + 4 job attivi; digest/config drift; SA target con
Owner/Editor; ruolo FCM con permission aggiuntive; job Eventi abilitati a FCM;
revisione servente non risolta o con identita' diversa dal target; rollback con
traffico nonzero; Cloud Build su uno dei SA runtime; risorsa non Ready; smoke che
scrive fuori dalla collezione dedicata; FCM non inequivocabilmente `validate_only`;
cleanup non confermato; scheduler o deploy concorrente; impossibilita' di dimostrare
che il Compute default non ha altri consumer.

I test contrattuali sono eseguiti in CI su `windows-latest` sia con Windows
PowerShell 5.1 sia con PowerShell 7. Includono la regressione critica nella quale
`latestReadyRevision` e il template usano il target, ma il 100% del traffico resta
sulla revisione legacy con Compute default SA.
