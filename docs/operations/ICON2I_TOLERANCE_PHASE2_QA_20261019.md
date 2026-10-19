# Tolleranze ICON-2I: fase 02, job di verifica senza invii

Data: 19 ottobre 2026. Job separato creato e verificato con un'esecuzione manuale
terminata alle **20:11 Europe/Rome** (18:11 UTC). Il produttore e i job operativi
non sono stati aggiornati. Questa fase segue il
[lettore HTTP già pubblicato](ICON2I_TOLERANCE_PHASE1_DEPLOY_20261019.md)
e il [piano coordinato](ICON2I_COORDINATED_ROLLOUT_20261019.md).

## Immagine e configurazione effettive

- Job: `meteofriul-local-notice-tolerance-qa`, progetto `meteo-friul`,
  regione `europe-west1`, account operatore `meteofriul@gmail.com`.
- Immagine: `europe-west1-docker.pkg.dev/meteo-friul/meteofriul/backend@sha256:48d293f2d2ea2a0b5f1416e82be4b59ee95a86857a79b79822b6ee8ae5d71ca1`.
- Build: `8b1cc80d-b281-40e4-9ada-3b8de41db66e`, SUCCESS.
- Provenienza: BASE `8497e773b1613312bb952236d72c074e22a7b1c6` + patch 01 e 02
  del kit congelato, verificate byte per byte contro main
  `5e04343a27716c9c42a65d2a45aea0f628bbb9d8`. Patch 03 esclusa.
- `cloud_worker.py`, `run_pilot.py` e materializzatore ancora identici alla BASE.
- Entrypoint `python -m app.jobs.send_local_weather_notices`.
- `LOCAL_NOTICE_DELIVERY_MODE=dry_run` e
  `LOCAL_NOTICE_ICON_ACCUMULATION_SIDECAR_ENABLED=true`.
- Coorte: gli stessi dispositivi Play beta idonei del job operativo, con i
  filtri esistenti di iscrizione, versione, preferenze e validità della posizione.
  Nessun dispositivo aggiunto e nessuna preferenza modificata.
- 1 task, parallelismo 1, 1 CPU, 512 MiB, timeout 300 secondi, retry 0.
- Identità nuova `meteofriul-notice-qa@meteo-friul.iam.gserviceaccount.com`:
  solo `roles/datastore.user`. Verificati i permessi del ruolo: nessun permesso
  FCM/messaging. Nessuna chiave privata generata, nessun segreto copiato.
- Nessuno scheduler creato e nessun binding invoker diretto aggiunto al job.

## Verifiche

201 test passati localmente con rete bloccata in 24,825 secondi; gli stessi
201 passati nell'immagine effettiva, rete container disabilitata, in 20,243
secondi. Non sono 402 test distinti. Suite su sorgenti regionali/nazionali,
sidecar, mancanti, rilevatori, tolleranze, invio/outbox, audit, ombra e riepiloghi.

Esecuzione reale: `meteofriul-local-notice-tolerance-qa-vcgqj`, completata
con successo / exit 0. Dati pubblicati della corsa `20261019T120000Z`,
prodotta dal circuito ordinario, non da un'acquisizione avviata per questa prova.

| Riscontro | Esito |
| --- | --- |
| Dispositivi idonei / valutati | 16 / 16 |
| Punti canonici / comuni distinti | 6 / 6 |
| Denominatore per ciascuno dei sei rilevatori | 6, senza moltiplicare per i dispositivi |
| Comuni | Chions, Cordenons, Fontanafredda, Pordenone, San Giorgio della Richinvelda, Valvasone Arzene |
| Esito | `no_candidate`, tutti i rilevatori valutabili sui dati di questa finestra |
| Candidati / tentativi / invii / batch di consegna | 0 / 0 / 0 / 0 |
| Errori di sorgente, audit o altro | 0 |
| Audit persistiti | 6, modalità `dry_run`, `can_send=false` |
| Metadati aggiuntivi | 6 `unavailable`, 0 `verified`, 0 tolleranze usate |
| Prenotazioni di invio | 0 documenti outbox aggiornati durante la finestra QA |

La prova chiude il funzionamento del nuovo consumatore sui dati reali e la
gestione dell'assenza del sidecar. **Non dimostra ancora l'uso operativo delle
tolleranze**: il produttore precedente non pubblica le prove, e questi sei punti
avevano già i dati necessari. I casi mancanti, le guardie e i candidati in
dry-run sono coperti dai test software; in questa esecuzione reale non c'erano
candidati. La coorte effettiva era tutta FVG: nessuna nuova valutazione cloud
extra-FVG viene dichiarata; i controlli nazionali della fase 01 restano separati.

## Audit, monitoraggio e invarianti

L'audit usa la collezione esistente `local_notice_pilot_runs`. Non è una nuova
collezione isolata: i record sono distinti da modalità `dry_run` e identificativo
univoco di tentativo, incluso nella chiave documento, con scadenza a 14 giorni.
Il riferimento del tentativo è nel [manifest](evidence/icon-tolerance-phase2-2026-10-19/deployment.json).
Sono state lette solo le righe audit nel periodo dell'esecuzione; nessun token
dispositivo è copiato nelle evidenze. Il controllo outbox usa il campo
`updated_at`, scritto da ogni acquisizione/rinnovo/finalizzazione della consegna.

Confronto prima/dopo: i 12 job già presenti conservano esattamente le loro
specifiche; gli 11 scheduler sono invariati. Il solo job aggiunto è il QA.
Le altre assegnazioni IAM di progetto sono identiche; il solo nuovo ruolo è
quello dell'identità QA. Il servizio HTTP della fase 01 conserva il 100% del
traffico. Mattutino e serale sono verificati nel codice candidato ma mantengono
le immagini operative precedenti.

Lettura delle 23 policy di monitoraggio presenti: gli allarmi di fallimento e
assenza successi degli avvisi locali filtrano il nome esatto del job operativo;
non includono il QA. Le altre policy sono dedicate ad altri job, scheduler o
metriche ICON2I. Due policy di prova email risultano disabilitate. Nessuna policy
modificata e nessun exit code cambiato. Un futuro `data_degraded` resta exit 1:
prima di cambiare questa semantica occorre ancora coordinare il monitoraggio.

## Punti aperti alla chiusura della fase 02

L'aggiornamento successivo del produttore e la verifica ancora pendente sulla
nuova corsa sono nel [verbale della fase 03](ICON2I_TOLERANCE_PHASE3_DEPLOY_20261019.md).

Il job QA rimane disponibile per un successivo avvio manuale, senza esecuzioni
programmate. Per attivare realmente le tolleranze serve la fase 03: distribuire
il produttore su una nuova corsa, preservando gli oggetti storici e usando il
rollback compatibile già preparato. Poi verificare le prove pubblicate,
ripetere questo QA e confrontare i risultati sugli stessi dati e punti.
Gli invii del nuovo consumatore restano subordinati a quel controllo e alla
successiva autorizzazione; i job di invio operativi non sono stati sostituiti.

Nessuna AAB, build/installazione Android, emulatore o nuovo push Git.
Verbale e piano conservati nel ramo del lavoro.
Evidenze compatte e hash in
[evidence/icon-tolerance-phase2-2026-10-19](evidence/icon-tolerance-phase2-2026-10-19/SHA256SUMS.txt);
risposte complete e log nella directory canonica `.tmp/icon-tolerance-phase2-20261019`.
