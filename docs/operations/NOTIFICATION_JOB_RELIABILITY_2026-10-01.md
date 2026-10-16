# Affidabilita job notifiche - audit e correzione del 2026-10-01

## Ambito

Audit dei Cloud Run Job e dei Cloud Scheduler che gestiscono:

- avvisi meteo locali orari;
- sintesi meteo mattutina delle 07:30 `Europe/Rome`;
- anticipazione meteo serale delle 20:45 `Europe/Rome`.

Il lavoro non comprende webcam, frontend, Android, AAB, servizi ICON produttori o
modifiche al minimo numero di istanze.

## Evidenze e cause

### Avvisi locali

Nelle 72 esecuzioni esaminate, 12 erano fallite e 60 riuscite. Le esecuzioni
fallite terminavano con `source_timeout`, di norma durante il primo gruppo di
localita. Nello stesso intervallo il servizio sorgente `meteofriul-weather`
mostrava richieste concluse con HTTP 200 ma latenze fino a circa 59 secondi,
coerenti con avvii a freddo. Il job usava ancora:

- immagine `sha256:4cc5bbe6...`;
- timeout sorgente di 15 secondi;
- Compute Engine default service account.

Il comportamento applicativo restava fail-safe: durante i fallimenti osservati
non risultavano tentativi FCM, errori di sicurezza, errori dispositivo o scritture
parziali di consegna.

### Sintesi mattutina

Cloud Scheduler aveva tentato l'invocazione del 2026-10-01 alle 05:30 UTC
(07:30 `Europe/Rome`), ricevendo `HTTP 403 PERMISSION_DENIED`. La policy IAM del
job era vuota: mancava `roles/run.invoker` per
`official-alert-scheduler@meteo-friul.iam.gserviceaccount.com`.

Il job usava inoltre la stessa immagine precedente, timeout sorgente di 15
secondi e Compute Engine default service account. Lo script di deploy verificava
soltanto immagine, entrypoint e calendario, quindi poteva dichiarare `ready` anche
con IAM o runtime errati.

### Anticipazione serale

Al momento dell'audit il job serale era gia allineato all'immagine corretta, al
runtime IAM dedicato, al timeout sorgente di 30 secondi e al binding invoker. Il
fallimento manuale precedente era relativo al gate di collaudo singolo; i test
mirati successivi erano riusciti. Non e stato eseguito un invio generale manuale.

### Monitoring

La policy degli avvisi locali sommava i fallimenti in una finestra di tre ore.
L'allineamento della finestra e il ritardo di ingestione avevano prodotto
chiusure e riaperture ripetute dello stesso incidente. Le policy giornaliere
guardavano solo il contatore dei fallimenti Cloud Run: non potevano vedere il
`403` dello Scheduler, perche in quel caso l'esecuzione Cloud Run non nasce.

## Correzioni applicate

Il 2026-10-01 tra le 16:31 e le 16:40 `Europe/Rome` sono state applicate queste
correzioni, usando l'immagine gia collaudata:

`europe-west1-docker.pkg.dev/meteo-friul/meteofriul/backend@sha256:4f2f6da0db893cc65fe7c53921a4a7154dc8c089b6eac285da20e4677c950568`

Per `meteofriul-morning-forecast` e `meteofriul-local-notice`:

- runtime `meteofriul-runtime@meteo-friul.iam.gserviceaccount.com`;
- timeout sorgente 30 secondi, con il retry applicativo gia incluso
  nell'immagine;
- task timeout 300 secondi e zero retry dell'intero job;
- binding `roles/run.invoker` limitato al service account dello Scheduler;
- scheduler, fuso orario, target HTTP OAuth ed entrypoint verificati tramite
  readback.

La configurazione persistente e rimasta `send`; i collaudi manuali hanno usato
esclusivamente override per-esecuzione `dry_run`.

Il catalogo Cloud Monitoring contiene ora 17 policy e il readback finale le
classifica tutte `unchanged`:

- errore Cloud Scheduler per ognuno dei tre job di notifica;
- nessuna esecuzione riuscita nelle ultime 25 ore per mattino e sera;
- nessun successo nelle ultime tre ore per il job orario, gia esistente;
- fallimento mattino/sera limitato alla finestra di due ore;
- almeno due fallimenti del job orario nella finestra di quattro ore, per
  ridurre il rumore di chiusura e riapertura.

Le policy basate sui log hanno rate limit di un'ora. Le policy di ultimo successo
notificano anche il recupero.

## Collaudo senza push

| Job | Esecuzione | Override | Esito | Durata |
| --- | --- | --- | --- | --- |
| `meteofriul-local-notice` | `meteofriul-local-notice-d97gl` | `LOCAL_NOTICE_DELIVERY_MODE=dry_run` | riuscita | 32,84 s |
| `meteofriul-morning-forecast` | `meteofriul-morning-forecast-47vll` | `LOCAL_NOTICE_DELIVERY_MODE=dry_run`, `MORNING_FORECAST_DELIVERY_MODE=dry_run` | riuscita | 47,11 s |

Il readback delle due esecuzioni conferma immagine `sha256:4f2f6da0...`, runtime
dedicato, timeout sorgente 30 secondi e override `dry_run`. Non e stato richiesto
alcun invio FCM di collaudo.

## Verifiche locali

- 43 test backend mirati superati;
- contratto operativo PowerShell superato;
- parsing PowerShell e JSON superato;
- `git diff --check` superato;
- audit Cloud finale di job, scheduler, IAM e monitoring superato.

## Osservazione residua

Restano da osservare le prime esecuzioni ordinarie successive alla modifica:

- avvisi locali: primo passaggio utile allo scoccare dell'ora;
- anticipazione serale: 20:45 `Europe/Rome`;
- sintesi mattutina: 07:30 `Europe/Rome` del giorno successivo.

Il singolo errore recente del produttore ICON FVG era `source_not_advanced`, non
un timeout, ed e stato seguito da esecuzioni riuscite. Eventuali modifiche al
produttore ICON o al suo scaling appartengono a un workstream distinto.
