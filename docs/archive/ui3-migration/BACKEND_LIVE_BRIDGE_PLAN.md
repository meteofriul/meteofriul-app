# Meteo Friul UI 3.0.0 - Piano ponte backend live

Data: 2026-06-26

## Scopo

Questo piano serve a trasformare il lavoro di audit in un percorso ordinato verso il backend reale.

Non collega nulla.

Non modifica Cloud Run, GitHub Actions, Firestore, FCM o UI.

Il principio resta:

```text
fonte reale -> osservazione -> transizione -> stato app -> eventuale notifica
```

La nuova app deve leggere uno stato pulito, non interpretare pezzi sparsi del vecchio backend.

## Stato attuale

Il gate read-only:

```text
python -B backend_dryrun_staging/backend_live_bridge_readiness.py
```

oggi restituisce:

```text
overall=ready
blockers=0
```

Questo significa che i blocchi architetturali locali sono risolti. Non significa che il live sia collegato o che si possa deployare senza una tranche dedicata.

Tranche A completata il 2026-06-26: il `backend/Dockerfile` del sorgente vecchio copia ora `data_state_contract.py`, e il gate passa `dockerfile_copies_data_state_contract`.

Tranche B completata il 2026-06-26: il workflow `sync-official-alerts.yml` mantiene il controllo push solo in `dry_run:true`, e il gate passa `official_alert_workflow_no_real_push_after_sync`.

Tranche C completata il 2026-06-26: lo script sorgente tratta DPC nazionale come diagnostica `skip_backend_update`, e il gate passa `sync_script_dpc_is_not_decision_source`.

Tranche D completata il 2026-06-26: l'endpoint dry-run ufficiale espone un `storage_plan` per `official_alert_state/current`, osservazioni, transizioni e audit push. Il piano resta dichiarativo: `write_enabled=false`, nessuna scrittura Firestore.

Tranche E completata il 2026-06-27: `dispatch_official_alert_pushes()` passa dal contratto `state/transition` e invia solo se `transition_actions` contiene `NOTIFY_NEW_OFFICIAL_ALERT`. DPC nazionale resta diagnostica e non notifica.

## Blocchi da risolvere

Nessun blocco del gate read-only.

Restano fuori da questo piano:

- deploy Cloud Run/Firebase;
- scrittura reale Firestore;
- collegamento UI agli endpoint live;
- invio FCM reale.

## Ordine di lavoro consigliato

### Tranche A - Packaging sicuro

Obiettivo: rendere il vecchio backend capace di importare i moduli dry-run senza rischio di immagine incompleta.

Stato: completata il 2026-06-26.

Intervento eseguito:

- aggiungere `COPY data_state_contract.py .` al `backend/Dockerfile` sorgente.

Accettazione verificata:

- controllo sintattico read-only su `main.py`, `data_state_contract.py` e `test_data_state_contract.py`;
- `python -B -m unittest discover backend_dryrun_staging`: 39 test OK;
- gate passa il controllo `dockerfile_copies_data_state_contract`;
- gate complessivo resta correttamente `blocked` con 4 blocker residui;
- nessun deploy.

### Tranche B - Workflow senza push reale automatico

Obiettivo: separare lettura fonte e invio notifiche.

Stato: completata il 2026-06-26.

Intervento eseguito:

- `sync-official-alerts.yml` non e' piu nominato come workflow di invio;
- il controllo `/push/alerts/check` resta solo come simulazione;
- payload cambiato da `{"force":false,"dry_run":false}` a `{"force":false,"dry_run":true}`.

Accettazione verificata:

- gate passa `official_alert_workflow_no_real_push_after_sync`;
- `python -B -m unittest discover backend_dryrun_staging`: 39 test OK;
- gate complessivo resta correttamente `blocked` con 3 blocker residui;
- nessun FCM;
- nessun deploy.

### Tranche C - DPC solo diagnostico

Obiettivo: impedire che DPC nazionale accenda UI/notifiche nella nuova pipeline.

Stato: completata il 2026-06-26.

Intervento eseguito:

- lo script sorgente usa `github_actions_dpc_national_criticity_diagnostic`;
- se pagina/widget FVG falliscono, DPC puo essere letto ma produce `skip_backend_update`;
- il DPC non produce piu override `active`, no-alert, spegnimenti o notifiche;
- il tool `official_alert_source_audit.py` esporta i campioni DPC come payload diagnostici/skipped.

Accettazione verificata:

- gate passa `sync_script_dpc_is_not_decision_source`;
- dry-run campione DPC: `action=skip_backend_update`, `source_mode=github_actions_dpc_national_criticity_diagnostic`;
- dry-run campione widget FVG no-alert: resta `inactive_confirmed` e puo spegnere allerta precedente;
- `python -B -m unittest discover backend_dryrun_staging`: 39 test OK;
- gate complessivo resta correttamente `blocked` con 2 blocker residui;
- nessuna notifica.

### Tranche D - Stato finale allerta

Obiettivo: introdurre il documento finale che la nuova UI potra leggere.

Stato: completata il 2026-06-26 in sola modalita dry-run.

Storage previsto:

```text
official_alert_state/current
official_alert_observations/{id}
official_alert_transitions/{id}
push_decision_audit/{id}
```

Intervento eseguito:

- aggiunta funzione pura `build_official_alert_storage_plan()` nel contratto backend sorgente;
- l'endpoint `POST /api/weather/data-pipeline/dry-run/official-alerts` restituisce `storage_plan`;
- il piano include `official_alert_state/current`, `official_alert_observations/{id}`, `official_alert_transitions/{id}` e `push_decision_audit/{id}`;
- `write_enabled=false`, quindi non scrive Firestore e non collega storage reale.

Accettazione verificata:

- `official_alert_state/current` e' l'unico punto di lettura futuro per UI/push;
- il gate passa `final_state_storage_not_implemented`;
- `python -B -m unittest test_data_state_contract`: 13 test OK nel backend sorgente;
- `python -B -m unittest discover backend_dryrun_staging`: 39 test OK;
- gate complessivo resta correttamente `blocked` con 1 blocker residuo;
- nessuna UI collegata.

### Tranche E - Push guidato da transizione

Obiettivo: permettere notifiche solo se la transizione lo autorizza.

Stato: completata il 2026-06-27.

Regola:

```text
invia FCM solo se transition_actions contiene NOTIFY_NEW_OFFICIAL_ALERT
```

Intervento eseguito:

- `dispatch_official_alert_pushes()` costruisce una decisione da `data_state_contract`;
- la lista notificabile viene prodotta solo se `transition_actions` contiene `NOTIFY_NEW_OFFICIAL_ALERT`;
- DPC nazionale attivo/no-active viene classificato come diagnostica non notificabile;
- deduplica esistente resta;
- `PUSH_DRY_RUN` resta interruttore globale.

Accettazione verificata:

- gate passa `official_push_uses_transition_decision`;
- test mirati su fonte regionale attiva e DPC diagnostico;
- `python -B -m unittest test_data_state_contract`: 13 test OK nel backend sorgente;
- `python -B -m unittest discover backend_dryrun_staging`: 39 test OK;
- gate complessivo `ready`, 0 blocker;
- FCM reale ancora spento.

## Vietato in questa fase

- collegare la UI agli endpoint live;
- attivare Cloud Scheduler;
- inviare FCM reali;
- usare DPC o Telegram come fonte decisionale;
- cancellare una vecchia allerta senza `inactive_confirmed` da fonte FVG;
- trattare `active=false` come "nessuna allerta";
- fare deploy Cloud Run/Firebase solo per "provare".

## Sequenza di verifica

Dopo ogni tranche:

```text
python -B -m unittest discover backend_dryrun_staging
python -B backend_dryrun_staging/backend_live_bridge_readiness.py
```

Quando si tocchera il backend sorgente, aggiungere anche i test del vecchio backend interessati.

## Tranche F - Collegamento protetto futuro

Questa tranche non e' stata eseguita.

Obiettivo: passare dal laboratorio `ready` a una prova protetta senza aprire subito notifiche reali o UI live.

Ordine obbligatorio:

1. fotografare configurazione attuale di Cloud Run, Firebase Hosting, GitHub Actions, Firestore e variabili push;
2. confermare `PUSH_DRY_RUN=true` o interruttore equivalente prima di qualunque chiamata a `/api/push/alerts/check`;
3. verificare che `sync-official-alerts.yml` resti in `dry_run:true`;
4. preparare rollback Cloud Run/Firebase Hosting prima del deploy, ricordando che `/api/**` usa `pinTag:true`;
5. deployare solo dopo approvazione esplicita;
6. fare smoke test read-only sugli endpoint dry-run, non su FCM reale;
7. solo dopo valutare scrittura controllata dello stato `official_alert_state/current`;
8. solo dopo valutare endpoint `state` per UI;
9. solo dopo valutare notifiche reali.

Test minimi prima di qualsiasi collegamento:

```text
python -B -m unittest test_data_state_contract
python -B -m unittest test_weather_engine
python -B -m unittest discover backend_dryrun_staging
python -B backend_dryrun_staging/backend_live_bridge_readiness.py --format json
```

Condizione di uscita: gate `ready`, suite legacy verde, piano rollback scritto, nessun FCM reale senza consenso.

## Criterio per passare al live

Il live si considera avvicinabile solo quando:

- il gate e' `ready`;
- i test dry-run sono verdi;
- il push e' ancora in dry-run;
- il piano di rollback e' scritto;
- l'utente approva esplicitamente il collegamento.
