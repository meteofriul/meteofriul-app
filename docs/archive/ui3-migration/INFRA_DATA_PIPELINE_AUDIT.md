# Meteo Friul UI 3.0.0 - Audit infrastruttura dati Bollettino e allerte

Data: 2026-06-24

Ultima passata read-only: 2026-06-26

Ultima passata Bollettino/previsioni: 2026-06-27

## Scopo

Questo documento e' un audit locale e read-only della filiera dati della vecchia app.

Non collega servizi, non modifica backend, non modifica UI e non abilita notifiche.

Serve a decidere come portare in UI 3.0.0 il recupero dati di Bollettino, allerte e notifiche senza importare rumore o scorciatoie fragili.

Fonti lette localmente:

- `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\firebase.json`
- `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\backend\Dockerfile`
- `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\backend\main.py`
- `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\backend\osmer_audit_storage.py`
- `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\.github\workflows\sync-official-alerts.yml`
- `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\.github\workflows\send-local-weather-notices.yml`
- `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\.github\workflows\send-manual-app-notice.yml`
- `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\scripts\sync-protezione-civile-alert-override.py`
- documenti operativi vecchi su Firebase, Cloud Run, GitHub Actions, push e fetcher ufficiale.

## Aggiornamento audit read-only 2026-06-26

Questa passata ha verificato solo file locali. Non sono stati chiamati endpoint live, non sono stati modificati scheduler, Firestore, FCM, GitHub Actions o Cloud Run.

File e punti letti in modo mirato:

- `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\.github\workflows\sync-official-alerts.yml`
- `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\.github\workflows\send-local-weather-notices.yml`
- `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\.github\workflows\send-manual-app-notice.yml`
- `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\.github\workflows\update-webcams-json.yml`
- `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\firebase.json`
- `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\backend\Dockerfile`
- `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\backend\main.py`
- `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\backend\data_state_contract.py`
- `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\scripts\sync-protezione-civile-alert-override.py`
- `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\docs\github-official-alert-fetcher.md`
- `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\docs\push-notifications-readiness.md`

Esito netto:

- la nuova logica `observation -> state -> transition -> notification_decision` esiste gia come laboratorio e contratto;
- il vecchio invio push ufficiale ora usa una decisione derivata dal contratto `state/transition`, non piu direttamente `alerts[]` come decisore;
- Tranche B completata il 2026-06-26: il workflow `sync-official-alerts.yml` sincronizza l'override e poi chiama `/api/push/alerts/check` solo con `dry_run:true`;
- Tranche C completata il 2026-06-26: DPC nazionale nello script sorgente produce solo diagnostica `skip_backend_update`;
- Tranche D completata il 2026-06-26: l'endpoint dry-run ufficiale espone un `storage_plan` per `official_alert_state/current`, osservazioni, transizioni e audit push, con `write_enabled=false`;
- Tranche E completata il 2026-06-27: `dispatch_official_alert_pushes()` notifica solo se `transition_actions` contiene `NOTIFY_NEW_OFFICIAL_ALERT`;
- il backend sorgente importa `data_state_contract.py`;
- Tranche A completata il 2026-06-26: il `backend/Dockerfile` copia ora `data_state_contract.py` nell'immagine futura;
- non va comunque fatto nessun deploy Cloud Run in automatico: il gate locale e' `ready`, ma il live richiede una tranche di collegamento e rollback separata;
- `firebase.json` usa `pinTag:true` su `/api/**`, quindi un futuro deploy Cloud Run richiedera anche Firebase Hosting deploy per ripinnare la nuova revisione;
- le notifiche locali meteo sono un flusso separato e non vanno toccate in questa fase.
- nel lab frontend UI 3.0.0 e' stata trovata e chiusa una contraddizione: `github_actions_dpc_national_criticity_fallback` non produce piu stato `active`, banner o notifica; resta `diagnostic`.

Decisione architetturale aggiornata:

- Protezione Civile FVG pagina/widget resta l'unica fonte decisionale primaria per accendere o spegnere allerte ufficiali;
- Telegram FVG e DPC nazionale sono supporto diagnostico, non fonti decisionali;
- Telegram/DPC non possono dichiarare "nessuna allerta", non possono spegnere una vecchia allerta e non possono generare notifiche;
- se FVG e' irraggiungibile e una vecchia allerta e' ancora valida, l'app mantiene la vecchia allerta con la sua scadenza normale;
- l'utente non deve vedere copy tecnico tipo "da verificare" in Home/Bollettino;
- una notifica e' ammessa solo quando la transizione finale produce una nuova allerta FVG primaria o un cambio livello rilevante.

Gap bloccanti prima del collegamento live:

Nessun blocco locale del gate read-only.

Passaggi ancora necessari prima di qualunque live:

1. Tenere `PUSH_DRY_RUN` o flag equivalente come interruttore globale durante i primi test protetti.
2. Definire rollback e osservabilita per Firestore/GitHub Actions/Cloud Run.
3. Decidere esplicitamente quando collegare storage reale e quando esporre endpoint state alla UI.
4. Aggiornare i test backend reali prima di qualunque invio FCM reale.

Verifica locale dopo la correzione lab frontend:

- `python -B -m unittest discover backend_dryrun_staging`: 39 test OK;
- `npm test -- src/domain/alerts/officialAlertContract.test.js src/domain/alerts/officialAlerts.test.js src/domain/alerts/officialAlertTransition.test.js src/domain/pipeline/backendDataStateContract.test.js src/domain/pipeline/bulletinPipelineScenario.test.js`: 36 test OK.

Report unico locale letto dopo i test:

- allerta ufficiale: `inactive_confirmed`, fonte `github_actions_official_page`, 0 allerte;
- Home: nessuna allerta;
- Bollettino: nessun avviso allerta;
- notifica: non ammessa, motivo `inactive_confirmed_does_not_notify`;
- prossimo controllo FVG proposto: 30 minuti;
- OSMER: `ready`, `source_status=merged_xml_window`;
- mappa A1-A9: renderizzabile;
- stato complessivo: `ready_for_review`;
- `scheduler_connected=false`, `live_connected=false`.

Gate ponte backend live aggiunto dopo l'audit:

- nuovo comando locale: `python -B backend_dryrun_staging/backend_live_bridge_readiness.py`;
- nuovo test: `python -B backend_dryrun_staging/test_backend_live_bridge_readiness.py`;
- il comando legge il vecchio sorgente e non chiama rete, Firestore, FCM, scheduler o deploy;
- al 2026-06-27 il vecchio sorgente risulta `ready` nel gate locale read-only.

Blocchi rilevati dal gate:

Tranche A packaging risolta:

- `backend/Dockerfile` copia `data_state_contract.py`.

Tranche B workflow risolta:

- `sync-official-alerts.yml` chiama `/push/alerts/check` solo con `dry_run:true`.

Tranche C DPC risolta:

- `scripts/sync-protezione-civile-alert-override.py` tratta DPC nazionale come `skip_backend_update` diagnostico.

Tranche D storage plan risolta:

- il dry-run ufficiale produce un piano storage per `official_alert_state/current`;
- osservazione, stato, transizione e decisione push sono descritti in documenti separati;
- il piano resta non operativo: `dry_run=true`, `write_enabled=false`.

Blocchi residui del gate:

Nessuno.

Verifica Tranche A:

- `python -B backend_dryrun_staging\backend_live_bridge_readiness.py --format json`: `overall=blocked`, `blockers=4`, `dockerfile_copies_data_state_contract=pass`;
- `python -B -m unittest discover backend_dryrun_staging`: 39 test OK;
- controllo sintattico read-only su `main.py`, `data_state_contract.py` e `test_data_state_contract.py`: OK.

Verifica Tranche B:

- `python -B backend_dryrun_staging\backend_live_bridge_readiness.py --format json`: `overall=blocked`, `blockers=3`, `official_alert_workflow_no_real_push_after_sync=pass`;
- `python -B -m unittest discover backend_dryrun_staging`: 39 test OK.

Verifica Tranche C:

- `python -B backend_dryrun_staging\backend_live_bridge_readiness.py --format json`: `overall=blocked`, `blockers=2`, `sync_script_dpc_is_not_decision_source=pass`;
- dry-run DPC diagnostico: `action=skip_backend_update`, `reason=regional_source_unreachable_dpc_diagnostic_only`;
- dry-run widget FVG no-alert: `state=inactive_confirmed`, `clears_previous_alert=true`;
- `python -B -m unittest discover backend_dryrun_staging`: 39 test OK.

Verifica Tranche D:

- `python -B backend_dryrun_staging\backend_live_bridge_readiness.py --format json`: `overall=blocked`, `blockers=1`, `final_state_storage_not_implemented=pass`;
- `python -B -m unittest test_data_state_contract`: 13 test OK nel backend sorgente;
- `python -B -m unittest discover backend_dryrun_staging`: 39 test OK;
- controllo sintattico read-only su `main.py`, `data_state_contract.py` e `test_data_state_contract.py`: OK.

Verifica Tranche E:

- `python -B backend_dryrun_staging\backend_live_bridge_readiness.py --format json`: `overall=ready`, `blockers=0`, `official_push_uses_transition_decision=pass`;
- `python -B -m unittest test_weather_engine.OfficialAlertPushHardeningTest.test_official_push_response_exposes_alert_source_metadata test_weather_engine.OfficialAlertPushHardeningTest.test_official_push_suppresses_diagnostic_dpc_source test_weather_engine.OfficialAlertPushHardeningTest.test_official_push_uses_transition_decision_for_regional_alert`: 3 test OK;
- `python -B -m unittest test_data_state_contract`: 13 test OK;
- `python -B -m unittest discover backend_dryrun_staging`: 39 test OK;
- controllo sintattico read-only su `main.py`, `data_state_contract.py`, `test_data_state_contract.py` e `test_weather_engine.py`: OK.

Verifica Tranche 85:

- `python -B -m unittest test_weather_engine`: 65 test OK;
- `python -B -m unittest test_data_state_contract`: 13 test OK;
- `python -B -m unittest discover backend_dryrun_staging`: 39 test OK;
- gate read-only: `overall=ready`, `blockers=0`;
- i test legacy DPC sono stati aggiornati per verificare diagnostica `skip_backend_update`, non fallback decisionale.

Questo gate diventa il controllo minimo prima di qualunque collegamento live.

## Tranche 86 - Audit visualizzazione Bollettino e previsioni

Data: 2026-06-27

Scopo:

- controllare non solo allerte/notifiche, ma anche previsioni e contenuto visibile nel Bollettino;
- verificare che la UI 3.0.0 non mostri dati alternativi come se fossero OSMER ufficiale;
- rendere esplicito il confine tra dati ufficiali, stati tecnici, fixture e diagnostica.

Controlli locali eseguiti:

- frontend locale UI 3.0.0: `http://127.0.0.1:5173/?tab=bulletin`;
- backend locale sorgente vecchio: `http://127.0.0.1:8001`;
- `GET /api/health/data-sources`;
- `GET /api/weather/bootstrap?city=Udine`.

Esito bootstrap Udine:

- `forecast.osmer_structured` presente;
- `source_status=merged_xml_window`;
- `days=5`;
- tutti i giorni osservati hanno `source_kind=structured_xml`;
- ogni giorno ha A1-A9 complete e F1-F4 complete;
- il testo previsionale arriva da `forecast.official.it.forecasts`;
- `official_alerts.source_mode=github_actions_dpc_national_criticity_no_active_fvg_unverified`;
- l'allerta DPC/no-active resta diagnostica e non genera avviso UI.

Correzione UI applicata:

- `buildBulletinViewModel()` non usa piu' fixture come contenuto reale di default;
- fixture attivabili solo con `allowFixtureFallback:true`;
- se mancano testo ufficiale e XML OSMER strutturato, lo stato e' `unavailable`;
- senza dati reali non vengono mostrati marker, focus grid o dati utili di laboratorio;
- la vista nasconde attendibilita', focus e dati utili quando non hanno valore reale.

Regola di prodotto:

- niente Open-Meteo, fixture, proiezioni o dati cache mostrati come bollettino ufficiale;
- `official_projected` resta diagnostica/audit, non mappa nativa;
- `stale_from_cache` e `partial_healed` richiedono una decisione esplicita prima di comparire all'utente;
- se il dato manca, si mostra indisponibilita' e link fonte, non una previsione alternativa.

Documento dedicato:

- `BULLETIN_DATA_DISPLAY_AUDIT.md`.

Verifica:

- `npx vitest run --configLoader native src/features/bulletin/bulletinViewModel.test.js src/features/bulletin/bulletinDataController.test.js src/domain/weather/osmerStructuredContract.test.js`: 17 test OK;
- `npx vitest run --configLoader native src/domain/alerts/officialAlerts.test.js src/features/bulletin/bulletinViewModel.test.js`: 19 test OK.

## Tranche 87 - Audit notifiche meteo locali

Data: 2026-06-27

Scopo:

- chiarire come trattare caldo, pioggia, temporali, grandine, neve, ghiaccio, vento e Bora quando non sono allerte ufficiali;
- verificare se il backend vecchio localizza davvero per citta;
- separare feature push locale da Allerte e Bollettino.

Esito audit:

- il backend sorgente ha gia un flusso `local weather push`;
- endpoint protetto: `POST /api/push/local-weather/check`;
- workflow esistente: `.github/workflows/send-local-weather-notices.yml`;
- il workflow e' manuale (`workflow_dispatch`), non schedulato;
- il dispatcher raggruppa i device per `city`;
- il generatore e' `build_local_weather_notices_for_city(city)`;
- le preferenze sono `rain`, `storms`, `wind`, `snow`, `heat`;
- la deduplica usa citta, tipo fenomeno, categoria, ora e finestra della giornata;
- se un'allerta ufficiale copre la stessa categoria, la notifica locale viene soppressa.

Limite:

- oggi molte decisioni locali dipendono da `hourly_next_12h` e supporto modello/orario;
- alcune fonti sono `open_meteo_model_support` o `osmer_station_and_open_meteo_support`;
- quindi il motore e' localizzato per citta, ma non e' ancora il contratto pulito UI 3.0.0;
- non va promosso a scheduler automatico senza `source_inputs`, `confidence`, stato finale e dry-run controllato.

Correzione minima:

- la notifica caldo e' stata riallineata alla localita:
  - prima: `Caldo intenso nelle ore piu' calde.`
  - ora: `Caldo previsto oggi a {city}.`

Regola:

- le push locali devono sempre citare la localita;
- niente frasi macro-area come push personale;
- niente lessico allerta;
- se non e' localizzabile, niente push.

Documento dedicato:

- `LOCAL_WEATHER_NOTICE_ENGINE_AUDIT.md`.

Verdetto 2026-06-27:

La pipeline locale e' pronta per una revisione di collegamento protetto. Non e' stato collegato live nulla: scheduler, Firestore finale, UI e FCM restano fuori.

## Sintesi netta

La vecchia app ha gia molti pezzi utili, ma non vanno copiati cosi come sono.

La parte piu fragile non e' OSMER A1-A9. La parte piu fragile e' la filiera delle allerte ufficiali:

1. Protezione Civile FVG non e' raggiungibile in modo affidabile da Cloud Run;
2. GitHub Actions prova pagina FVG, widget FVG e fallback nazionale DPC;
3. il risultato viene scritto come override Firestore;
4. Cloud Run legge l'override e decide banner/push;
5. quando la fonte manca, l'API puo restituire `active=false` anche se non ha verificato davvero il verde FVG.

Per UI 3.0.0 la regola deve essere piu severa:

- osservazione grezza: cosa ho letto e da dove;
- stato transizionale: come interpreto l'osservazione rispetto allo stato precedente;
- stato app: cosa posso mostrare;
- stato notifica: cosa posso inviare.

Questi quattro livelli non devono essere fusi nello stesso payload.

## Architettura vecchia osservata

### Firebase Hosting

`firebase.json` pubblica `frontend/dist` e riscrive:

```text
/api/** -> Cloud Run service meteofriul-api, region europe-west1
```

Il rewrite usa `pinTag: true`.

Conseguenza operativa: dopo un deploy Cloud Run, Firebase Hosting deve essere ridistribuito per ripinnare `/api/**` alla nuova revisione. Un push Git o un deploy Cloud Run da soli non garantiscono che `https://meteo-friul.web.app/api/**` stia servendo la revisione nuova.

### Cloud Run

Il backend e' FastAPI via `uvicorn main:app`.

`backend/Dockerfile` copia moduli meteo e audit:

- `main.py`;
- `data_state_contract.py`;
- `parser_osmer.py`;
- `osmer_audit_storage.py`;
- `osmer_interpreter.py`;
- `osmer_projection_audit.py`;
- `webcams_active.json`.

Questo e' importante: se in futuro si estrae altra logica dati in moduli nuovi, il Dockerfile deve essere aggiornato, altrimenti la produzione puo fallire anche se i test locali passano.

### GitHub Actions

Il workflow `sync-official-alerts.yml` e' oggi il lettore esterno principale delle allerte:

- gira sui minuti `7,17,27,37,47,57`;
- usa `PUSH_CRON_SECRET`;
- chiama `scripts/sync-protezione-civile-alert-override.py`;
- dopo la sync chiama `POST /api/push/alerts/check` solo con `dry_run:true`.

La schedule GitHub va considerata best-effort, non timer realtime garantito.

### Firestore

La vecchia app usa Firestore per:

- override corrente delle allerte ufficiali: `official_alert_overrides/current`;
- device push;
- storico invii push;
- audit OSMER quando `OSMER_BULLETIN_AUDIT_STORAGE=auto` gira su Cloud Run.

Per la nuova architettura Firestore non deve essere solo "posto dove salvo override"; deve diventare il punto in cui lo stato finale e auditabile viene separato dalle singole osservazioni.

## Allerte ufficiali

### Lettura vecchia

Nel vecchio backend `fetch_civil_protection_alerts()` segue questa priorita':

1. cache breve;
2. override Firestore corrente;
3. fetch diretto pagina/widget Protezione Civile FVG solo se abilitato;
4. vecchio override inattivo marcato stale;
5. fallback `official_alerts_unavailable_fast_fallback`.

Il fetch diretto da Cloud Run e' disattivato di default per evitare timeout bloccanti.

### Punto di rottura

`build_official_alerts_unavailable_response()` restituisce:

```text
active=false
count=0
alerts=[]
source_mode=official_alerts_unavailable_fast_fallback
cache.status=unavailable
error=official_alerts_unavailable
```

Se la UI guarda solo `active=false`, non distingue:

- nessuna allerta verificata;
- fonte non disponibile;
- fallback diagnostico;
- allerta precedente scaduta ma non ancora chiusa da fonte regionale.

Questa e' la falla logica principale da non importare.

### Regola UI 3.0.0

La nuova app deve usare lo stato classificato, non `active` da solo.

Stati minimi:

- `active`: allerta attiva, mostrabile e notificabile solo al primo passaggio utile;
- `inactive_confirmed`: fonte regionale letta e nessuna allerta, unico stato che spegne davvero;
- `unavailable`: fonte non letta, non mostrare nuovo banner e non spegnere vecchi stati da sola;
- `diagnostic`: fallback DPC senza criticita FVG, non equivalente a verde regionale;
- `expired`: validita superata, non e' verde certificato;
- `stale_held_active`: memoria prudente di allerta precedente, visibile solo come stato trattenuto, senza nuove notifiche.

### Fonte FVG e fallback DPC

Ordine sorgenti corretto:

1. pagina ufficiale Protezione Civile FVG;
2. widget Protezione Civile FVG;
3. DPC nazionale solo come diagnostica controllata.

Decisione aggiornata 2026-06-26: nella nuova pipeline UI 3.0.0 il DPC nazionale non accende una criticita e non spegne allerte. Resta solo diagnostica interna quando pagina/widget FVG sono irraggiungibili.

Il DPC nazionale senza criticita FVG non deve spegnere una allerta regionale corrente e non deve essere chiamato "verde FVG".

## Notifiche

Nel vecchio backend `dispatch_official_alert_pushes()`:

1. prova eventuale sync esterna;
2. legge `fetch_civil_protection_alerts()`;
3. filtra `actionable_official_alerts()`;
4. deduplica per alert/installazione;
5. invia via FCM se non e' dry-run.

La deduplica e il dry-run sono utili e da preservare.

Il punto da cambiare e' il trigger decisionale: la notifica non deve partire da "array alerts non vuoto" ma da una transizione finale:

```text
previous_final_state + current_observation -> final_state + actions
```

Solo l'azione `notify_new_official_alert` puo abilitare l'invio.

Stati che non devono notificare:

- `inactive_confirmed`;
- `unavailable`;
- `diagnostic`;
- `expired`;
- `stale_held_active`.

Le notifiche locali meteo devono restare separate e soppresse quando una allerta ufficiale copre lo stesso rischio. Questa regola esiste gia nella vecchia app e va mantenuta, ma non collegata ora.

## Bollettino OSMER

La parte A1-A9 e' piu solida delle allerte.

La vecchia app legge XML OSMER, usa lookback/lookahead e produce `forecast.osmer_structured`.

Punti buoni da preservare:

- merge per `valid_date`;
- tracciamento `source_date`, `requested_date`, `source_status`, `is_stale`, `stale_reason`;
- distinzione tra XML strutturato e `official_projected`;
- audit snapshot con storage file locale o Firestore in Cloud Run.

Punti da rendere piu espliciti in UI 3.0.0:

- A1-A9 complete sono requisito per mappa nativa;
- F1-F4 mancanti rendono il bollettino parziale;
- snapshot stale o source unavailable non devono diventare mappa corrente senza etichetta;
- la mappa non deve inventare marker quando mancano aree.

## Storage consigliato per UI 3.0.0

Quando si passera al backend reale, usare collezioni distinte:

| Area | Documento/collezione | Scopo |
| --- | --- | --- |
| Allerte | `official_alert_observations/{id}` | Osservazioni grezze: fonte, payload, errore, timestamp. |
| Allerte | `official_alert_state/current` | Stato finale dopo transizione. |
| Allerte | `official_alert_transitions/{id}` | Audit di cambio stato e azioni prodotte. |
| OSMER | `osmer_bulletin_observations/{id}` | Snapshot XML/proiettati letti. |
| OSMER | `osmer_bulletin_state/current` | Stato finale app per mappa/testo/qualita. |
| OSMER | `osmer_bulletin_transitions/{id}` | Merge, recuperi da lookback, warning. |
| Push | `push_decision_audit/{id}` | Decisione sanificata prima dell'invio reale. |

`official_alert_overrides/current` puo restare come compatibilita vecchia, ma non dovrebbe essere il contratto finale della nuova app.

## Rischi da non importare

1. Trattare `active=false` come "nessuna allerta".
2. Spegnere banner o notifiche per `unavailable`.
3. Confondere DPC no-active con verde regionale verificato.
4. Lasciare una vecchia allerta visibile all'infinito se FVG resta irraggiungibile.
5. Fare fetch diretto Protezione Civile da Cloud Run durante il bootstrap Home.
6. Far partire FCM prima di avere dry-run e audit della transizione.
7. Dimenticare `pinTag` dopo deploy Cloud Run.
8. Aggiungere moduli backend senza aggiornare Dockerfile.
9. Salvare solo stato corrente senza osservazioni storiche.
10. Unire logica OSMER, allerte e notifiche in un unico parser non testabile.

## Piano di collegamento futuro

Non collegare adesso.

Quando decideremo di farlo:

1. portare nel backend un motore puro di transizione per allerte, con fixture;
2. portare nel backend un motore puro di transizione OSMER, con fixture;
3. far scrivere a GitHub Actions solo osservazioni o override grezzi, non decisioni finali;
4. calcolare `official_alert_state/current` lato backend;
5. esporre endpoint read-only per UI:
   - `/api/weather/official-alerts/state`;
   - `/api/weather/osmer/state`;
6. collegare UI 3.0.0 solo agli endpoint `state`, non ai raw override;
7. abilitare push solo in dry-run;
8. passare a push reale solo dopo audit dei log e verifica manuale.

## Decisione per ora

Il prossimo passo non e' collegare Cloud Run/Firebase/GitHub.

Il prossimo passo corretto e':

1. formalizzare il contratto backend desiderato per `official_alert_state/current`;
2. formalizzare il contratto backend desiderato per `osmer_bulletin_state/current`;
3. preparare fixture equivalenti lato backend;
4. solo dopo decidere come adattare il vecchio backend.
