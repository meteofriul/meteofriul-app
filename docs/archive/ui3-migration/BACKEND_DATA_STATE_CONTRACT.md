# Meteo Friul UI 3.0.0 - Contratto backend stato dati

Data: 2026-06-24

## Scopo

Questo documento e' il punto di partenza architetturale per collegare, in futuro, Bollettino OSMER, allerte ufficiali e notifiche alla UI 3.0.0.

Non e' implementazione.

Non collega Firebase, Cloud Run, GitHub Actions o notifiche.

Definisce:

- quali stati il backend deve produrre;
- quali dati devono essere obbligatori;
- dove deve vivere lo stato precedente;
- quali stati possono essere mostrati in app;
- quali stati possono spegnere una vecchia allerta;
- quali stati possono generare una notifica.

## Principio architetturale

La pipeline deve essere divisa in quattro livelli.

```text
fonte esterna -> osservazione grezza -> transizione -> stato finale app -> azione/notifica
```

Il backend non deve esporre alla UI una decisione implicita nascosta dentro `active`, `alerts.length` o `cache.status`.

La UI deve leggere uno stato finale gia interpretato.

## Regola piu importante

`active=false` non significa automaticamente "nessuna allerta".

Puo significare:

- fonte regionale letta e nessuna allerta;
- fonte non disponibile;
- fallback diagnostico DPC;
- cache vecchia;
- vecchia allerta scaduta;
- errore parser;
- override inattivo.

Solo `state=inactive_confirmed` puo spegnere una vecchia allerta.

## Oggetti principali

### `official_alert_observation`

Osservazione grezza di una lettura allerta.

E' il risultato del fetcher, prima della decisione finale.

Deve conservare anche errori e fallback, non solo successi.

```json
{
  "schema_version": "1.0",
  "observation_id": "official-alerts-20260624T100000Z-github-page",
  "observed_at": "2026-06-24T10:00:00Z",
  "source_mode": "github_actions_official_page",
  "source_authority": "regional_fvg",
  "source_url": "https://www.protezionecivile.fvg.it/it/allerte",
  "fetch_status": "success",
  "parser_status": "success",
  "active": true,
  "count": 1,
  "alerts": [],
  "expires_at": "2026-06-25T00:00:00+02:00",
  "error": "",
  "warning": "",
  "raw_ref": ""
}
```

Stati ammessi per `fetch_status`:

- `success`;
- `timeout`;
- `http_error`;
- `parse_error`;
- `skipped`;
- `unavailable`.

Stati ammessi per `parser_status`:

- `success`;
- `empty_confirmed`;
- `diagnostic`;
- `failed`;
- `not_run`.

### `official_alert_state`

Stato finale corrente da esporre alla UI.

Questo e' il documento che la UI dovrebbe leggere.

```json
{
  "schema_version": "1.0",
  "state_id": "official-alert-state-current",
  "state": "active",
  "active": true,
  "count": 1,
  "alerts": [],
  "alert_signature": "pc-fvg-yellow-storm-20260624|gialla|2026-06-25T00:00:00+02:00",
  "source_mode": "github_actions_official_page",
  "source_authority": "regional_fvg",
  "freshness": "fresh",
  "confidence": "high",
  "fetched_at": "2026-06-24T10:00:00Z",
  "expires_at": "2026-06-25T00:00:00+02:00",
  "previous_state": "inactive_confirmed",
  "transition_actions": ["NOTIFY_NEW_OFFICIAL_ALERT"],
  "can_show_home_banner": true,
  "can_show_bulletin_notice": true,
  "can_clear_previous_alert": false,
  "can_notify": true,
  "error": "",
  "warning": ""
}
```

Stati ammessi:

| Stato | Significato | Home | Bollettino | Spegne vecchia allerta | Notifica |
| --- | --- | --- | --- | --- | --- |
| `active` | Allerta valida non verde. | Si | Si | No | Solo con `NOTIFY_NEW_OFFICIAL_ALERT` |
| `inactive_confirmed` | Fonte regionale/override verificato dice nessuna allerta. | No | No | Si | No |
| `stale_held_active` | Allerta precedente trattenuta per prudenza. | Si, con tono non fresco | Si | No | No |
| `expired` | Validita superata senza conferma regionale fresca. | No | Nota cauta | No | No |
| `diagnostic` | Fallback DPC no-active o stato informativo non regionale. | No | Nota tecnica/discreta | No | No |
| `unavailable` | Fonte non letta o backend fallback. | No | Nota se utile | No | No |
| `stale` | Dato vecchio non piu affidabile. | No | Nota se utile | No | No |

### `official_alert_transition`

Audit di una decisione.

Serve a capire perche' il backend ha acceso, trattenuto, spento o ignorato uno stato.

```json
{
  "schema_version": "1.0",
  "transition_id": "official-alert-transition-20260624T100000Z",
  "computed_at": "2026-06-24T10:00:05Z",
  "previous_state_id": "official-alert-state-current",
  "observation_id": "official-alerts-20260624T100000Z-github-page",
  "from_state": "inactive_confirmed",
  "to_state": "active",
  "actions": ["NOTIFY_NEW_OFFICIAL_ALERT"],
  "reason": "regional_fvg_active_alert",
  "alert_signature_before": "",
  "alert_signature_after": "pc-fvg-yellow-storm-20260624|gialla|2026-06-25T00:00:00+02:00",
  "dry_run": true
}
```

Azioni ammesse:

- `NOTIFY_NEW_OFFICIAL_ALERT`;
- `SUPPRESS_DUPLICATE_NOTIFICATION`;
- `DISABLE_NEW_NOTIFICATIONS`;
- `KEEP_BULLETIN_NOTICE`;
- `LOG_DIAGNOSTIC_ALERT`;
- `HIDE_BANNER_FROM_HOME`;
- `RETAIN_DB_CRITICALITY`;
- `CLEAR_ALL_ALERTS_AND_BANNERS`;
- `RESET_STATE_ENGINE`.

## Contratto OSMER

### `osmer_bulletin_observation`

Osservazione grezza del bollettino OSMER.

```json
{
  "schema_version": "1.0",
  "observation_id": "osmer-structured-20260624T100000Z-it",
  "observed_at": "2026-06-24T10:00:00Z",
  "language": "it",
  "source_kind": "structured_xml",
  "source_status": "reachable_xml",
  "source_url": "https://dev.meteo.fvg.it/xml/previsioni/PW20260624.xml",
  "source_date": "2026-06-24",
  "requested_date": "2026-06-24",
  "id_emissione": "PW20260624",
  "days": [],
  "quality": {
    "days_count": 5,
    "all_days_complete": true,
    "confidence": "alta"
  },
  "error": "",
  "raw_ref": ""
}
```

Stati ammessi per `source_kind`:

- `structured_xml`;
- `official_projected`;
- `mixed`;
- `unavailable`.

Stati ammessi per `source_status`:

- `reachable_xml`;
- `merged_xml_window`;
- `merged_xml_lookback`;
- `source_404`;
- `source_unavailable`;
- `parse_error`;
- `empty`.

### `osmer_bulletin_state`

Stato finale corrente del bollettino.

```json
{
  "schema_version": "1.0",
  "state_id": "osmer-bulletin-state-current",
  "state": "ready",
  "source_kind": "structured_xml",
  "source_status": "reachable_xml",
  "confidence": "high",
  "fetched_at": "2026-06-24T10:00:00Z",
  "source_date": "2026-06-24",
  "requested_date": "2026-06-24",
  "valid_dates": ["2026-06-24", "2026-06-25"],
  "days": [],
  "can_render_native_map": true,
  "can_use_as_current": true,
  "source_mix": false,
  "healed_manifest": {},
  "warnings": []
}
```

Stati ammessi:

| Stato | Significato | Mappa nativa | Uso come corrente |
| --- | --- | --- | --- |
| `ready` | XML strutturato completo per il giorno richiesto. | Si | Si |
| `partial` | Dato leggibile ma incompleto. | Solo se A1-A9 complete | Con warning |
| `partial_healed` | Buco sanato da snapshot precedente. | Si, con warning | Si, con `source_mix=true` |
| `stale_from_cache` | XML nuovo non disponibile, lookback valido. | Si, con etichetta | Si, entro finestra |
| `projected` | Proiezione da testo ufficiale, non XML nativo. | No come mappa nativa | Solo fallback |
| `unavailable` | Nessun dato utile. | No | No |

### Regola UI 3.0.0: nessuna alternativa mascherata

Gli stati tecnici `partial_healed`, `stale_from_cache`, `mixed` e `projected` possono essere utili per audit, confronto e robustezza interna.

Non sono pero' automaticamente contenuto utente equivalente al bollettino OSMER corrente.

Per la UI 3.0.0:

- la mappa nativa si abilita solo con `source_kind=structured_xml`, A1-A9 complete e dato non stale;
- `official_projected` non abilita marker ufficiali e non deve essere mostrato come previsione strutturata;
- `stale_from_cache` e `partial_healed` richiedono una decisione esplicita di prodotto prima di essere mostrati;
- fixture, dati di laboratorio e proiezioni non devono mai sostituire silenziosamente un dato OSMER mancante;
- se il dato ufficiale manca, la UI mostra indisponibilita' o consultazione fonte, non una previsione alternativa.

### `bulletin_display_field_audit`

Audit read-only per verificare cosa la schermata Bollettino puo' mostrare da un payload.

Modulo laboratorio:

```text
backend_dryrun_staging/bulletin_display_payload_audit.py
```

Input:

```text
payload bootstrap salvato, URL read-only o --city su bootstrap locale
```

Output:

```json
{
  "dry_run": true,
  "side_effects": {
    "firestore": false,
    "fcm": false,
    "workflow": false,
    "writes": false
  },
  "payloads": [
    {
      "city": "Pordenone",
      "summary": {
        "rows": 24,
        "safe_to_show": 23,
        "not_safe_to_show": 1,
        "official_text_days": 5,
        "native_map_days": 5
      },
      "rows": []
    }
  ]
}
```

Campi controllati:

- fonte mostrata;
- aggiornamento;
- snapshot OSMER strutturato;
- banner allerta;
- tab giorno;
- testo ufficiale;
- mappa nativa;
- attendibilita.

Regola:

ogni riga deve spiegare `payload_path`, `source`, `state`, `safe_to_show` e `reason`.

Questo audit non decide notifiche e non collega la UI: serve solo a impedire che il Bollettino mostri dati incompleti, proiettati o diagnostici come se fossero ufficiali.

### `osmer_bulletin_transition`

Audit del cambio stato OSMER.

## Contratto notifiche meteo locali

Le notifiche meteo locali sono distinte dalle allerte ufficiali.

Non usano livelli giallo/arancione/rosso e non possono sostituire o reinterpretare una fonte Protezione Civile FVG.

### Principio

```text
localita utente -> osservazione meteo locale -> fenomeno rilevante -> decisione notifica -> invio opzionale
```

La notifica deve essere localizzata.

Frasi macro-area come `temporali sui monti`, `caldo in pianura` o `vento sulla costa` sono adatte al Bollettino, non a una push personale.

### `local_weather_notice_detection`

Il detector e' il primo pezzo della catena locale.

Modulo laboratorio:

```text
backend_dryrun_staging/local_weather_notice_detector.py
```

Input:

```text
city + weather snapshot
```

Output:

```json
{
  "kind": "rain",
  "category": "rain",
  "severity": 2,
  "city": "Pordenone",
  "starts_at": "2026-06-27T17:00",
  "event_at": "2026-06-27T17:00",
  "body": "Pioggia prevista verso le 17:00.",
  "source": "open_meteo_model_support",
  "threshold": "rain/precipitation >= 0.3 mm or precipitation_probability >= 60%",
  "evidence": "17:00: rain 1.2 mm, probability 75%",
  "trigger_source": "",
  "trigger_value": null,
  "trigger_unit": ""
}
```

Regole:

- il detector non decide la notifica finale;
- il detector non deve importare backend, rete, Firestore, FCM o fixture esterne;
- ogni candidato deve portare `threshold` ed `evidence`;
- se una soglia precisa genera il candidato, deve portare anche `trigger_source`, `trigger_value`, `trigger_unit`;
- il testo puo essere ancora grezzo, ma deve essere una formula nota al normalizzatore;
- la localita finale viene validata dal normalizzatore.

Per il caldo:

- `current_feels_like`: soglia da percepita corrente;
- `current_temperature`: soglia da temperatura corrente;
- `hourly_temperature`: soglia da picco orario futuro.

Soglie di laboratorio:

| Fenomeno | Soglia |
| --- | --- |
| `rain` | precipitazione/pioggia/rovesci >= 0.3 mm o probabilita >= 60% |
| `storm` | `weathercode` 95, 96, 99 |
| `hail` | `weathercode` 96, 99 |
| `snow` | codice neve o `snowfall >= 0.2 mm` |
| `ice` | precipitazione gelata o temperatura <= 0 con slot bagnato/probabilita |
| `wind` | raffiche >= 55 km/h |
| `bora` | raffiche >= 55 km/h + area esposta/direzione Bora o flag Bora |
| `heat` | temperatura >= 33 C o percepita >= 34 C |

### `local_weather_payload_audit`

Audit di un payload reale o salvato prima di decidere qualsiasi invio.

Modulo laboratorio:

```text
backend_dryrun_staging/local_weather_payload_adapter.py
backend_dryrun_staging/local_weather_real_payload_dryrun.py
```

Input ammesso:

- JSON salvato da endpoint meteo;
- payload `bootstrap` con `current`, `forecast`, `official_alerts`;
- snapshot diretto con `city` + `weather`;
- URL read-only, solo per audit manuale.

Output minimo:

```json
{
  "summary": {
    "payloads": 5,
    "ready_payloads": 0,
    "no_notice_payloads": 5,
    "candidate_notices": 0,
    "dry_run_notifiable": 0
  },
  "payloads": [
    {
      "city": "Pordenone",
      "status": "no_notice",
      "source_shape": "weather_bootstrap",
      "numeric_snapshot": {
        "temperature": 28.0,
        "feels_like": 33.0,
        "observed_at": "2026-06-27T21:00",
        "hourly_count": 12,
        "peak_temperature": 28.7,
        "peak_temperature_time": "2026-06-27T22:00"
      },
      "data_gaps": [],
      "text_signals": [
        {
          "kind": "heat",
          "count": 12,
          "used_for_local_push": false,
          "reason": "segnale testuale regionale: non basta per una push locale"
        }
      ],
      "notices": []
    }
  ]
}
```

Regole:

- `text_signals` e' diagnostico;
- `text_signals` non crea push locale;
- `numeric_snapshot` serve a spiegare perche' una soglia locale e' o non e' scattata;
- i gap dati (`missing_hourly_next_12h`, `missing_feels_like`, ecc.) vanno mostrati nel report;
- l'eventuale notifica nasce solo dal detector numerico/localizzato;
- eventuali allerte ufficiali nel payload possono sopprimere il candidato locale coerente.

### `local_weather_notice_candidate`

Il candidato notificabile e' il risultato del normalizzatore, non l'output grezzo del backend.

Modulo laboratorio:

```text
backend_dryrun_staging/local_weather_notice_normalizer.py
```

Campi minimi:

```json
{
  "schema_version": "1.0",
  "type": "local_weather_notice",
  "state": "ready",
  "kind": "rain",
  "category": "rain",
  "city": "Pordenone",
  "starts_at": "2026-06-27T17:00",
  "event_at": "2026-06-27T17:00",
  "event_precision": "hour",
  "body": "Pioggia prevista a Pordenone verso le 17:00.",
  "source_authority": "meteo_friul",
  "source_inputs": ["open_meteo_hourly_support"],
  "confidence": "medium",
  "candidate_can_notify": true,
  "can_notify": false,
  "validation_errors": [],
  "copy_normalizations": ["inserted_city"]
}
```

Regole:

- `candidate_can_notify` dice solo se il candidato puo entrare nella policy;
- `can_notify` resta `false` finche' la policy non decide;
- formule note senza localita possono essere normalizzate con `inserted_city`;
- formule sconosciute senza localita vengono respinte;
- macro-zone e lessico da allerta vengono respinti.

### `local_weather_notice_observation`

Osservazione tecnica per una localita.

Campi minimi:

```json
{
  "schema_version": "1.0",
  "observation_id": "local-weather-observation-Pordenone-20260627T120000",
  "city": "Pordenone",
  "lat": 45.9567,
  "lon": 12.6605,
  "observed_at": "2026-06-27T12:00:00+02:00",
  "source_inputs": ["osmer_station", "open_meteo_hourly_support"],
  "hourly_window_hours": 12,
  "source_status": "ready",
  "confidence": "medium",
  "phenomena": []
}
```

### `local_weather_notice_state`

Stato finale notificabile.

```json
{
  "schema_version": "1.0",
  "type": "local_weather_notice",
  "state": "ready",
  "kind": "heat",
  "category": "heat",
  "city": "Pordenone",
  "starts_at": "2026-06-27T15:00:00+02:00",
  "reminder_window": "afternoon",
  "severity": 1,
  "body": "Caldo previsto oggi a Pordenone.",
  "source_authority": "meteo_friul",
  "source_inputs": ["osmer_station", "open_meteo_hourly_support"],
  "official_alert_overlap": false,
  "candidate_can_notify": true,
  "can_notify": true,
  "notification_policy": "selected_by_priority_and_time"
}
```

Stati ammessi:

| Stato | Significato | Notifica |
| --- | --- | --- |
| `ready` | Fenomeno locale rilevante e localizzato. | Si, se opt-in e non duplicato |
| `suppressed_by_official_alert` | Esiste allerta ufficiale coerente. | No |
| `duplicate` | Gia notificato nella finestra. | No |
| `no_opt_in_devices` | Nessun device interessato. | No |
| `no_notice` | Nessun fenomeno sopra soglia. | No |
| `source_unavailable` | Dato locale non disponibile. | No |
| `low_confidence` | Fonte incompleta o non localizzabile. | No |

### Lessico

Le notifiche meteo locali devono evitare:

- `Allerta`;
- `gialla`, `arancione`, `rossa`;
- `criticita`;
- `emergenza`;
- toni istituzionali da Protezione Civile.

Sono ammessi:

- `prevista`;
- `possibile`;
- `da tenere d'occhio`;
- indicazione della localita.

Politica anti-rumore candidata:

- tutti i fenomeni vengono prima generati come candidati;
- l'allerta ufficiale coerente sopprime il candidato locale;
- la priorita e': grandine, temporali, ghiaccio, neve, Bora, vento forte, pioggia, caldo;
- fenomeni entro 4 ore non devono produrre doppia push;
- il confronto entro 4 ore deve essere globale sulla finestra dei candidati, non dipendere dall'ordine cronologico di lettura;
- se un fenomeno piu importante arriva dopo uno meno importante ma dentro la stessa finestra, vince quello piu importante;
- a parita di priorita dentro la stessa finestra, vince l'evento piu vicino nel tempo;
- il caldo viene trattenuto se entro 8 ore c'e' un fenomeno piu importante;
- fenomeni separati mattina/sera possono restare entrambi notificabili.

La policy pura di laboratorio e':

```text
backend_dryrun_staging/local_weather_notification_policy.py
```

Il modulo non conosce fonti, backend, Firestore, FCM o fixture. Riceve candidati gia normalizzati e restituisce decisioni annotate.

```json
{
  "schema_version": "1.0",
  "transition_id": "osmer-bulletin-transition-20260624T100000Z",
  "computed_at": "2026-06-24T10:00:05Z",
  "previous_state_id": "osmer-bulletin-state-current",
  "observation_id": "osmer-structured-20260624T100000Z-it",
  "from_state": "stale_from_cache",
  "to_state": "ready",
  "actions": [],
  "reason": "structured_xml_complete",
  "healed_manifest": {},
  "source_mix": false
}
```

Azioni ammesse:

- `USE_LOOKBACK_SNAPSHOT`;
- `LOG_OSMER_SOURCE_GAP`;
- `HEAL_MISSING_AREAS_FROM_PREVIOUS`;
- `LOG_OSMER_HEALED_MERGE`.

## Storage logico consigliato

Quando si passera a Firestore o storage equivalente:

| Documento/collezione | Tipo | Scopo |
| --- | --- | --- |
| `official_alert_state/current` | documento | Stato finale allerta letto dalla UI. |
| `official_alert_observations/{observation_id}` | collezione | Letture grezze e fallimenti. |
| `official_alert_transitions/{transition_id}` | collezione | Decisioni e azioni prodotte. |
| `osmer_bulletin_state/current` | documento | Stato finale Bollettino letto dalla UI. |
| `osmer_bulletin_observations/{observation_id}` | collezione | Snapshot OSMER letti o falliti. |
| `osmer_bulletin_transitions/{transition_id}` | collezione | Merge, lookback, healing e warning. |
| `push_decision_audit/{id}` | collezione | Esito sanificato prima di eventuale push reale. |

`official_alert_overrides/current` puo restare durante la migrazione, ma non deve essere il contratto finale UI 3.0.0.

## Endpoint futuri

Endpoint read-only da esporre alla UI:

```text
GET /api/weather/official-alerts/state
GET /api/weather/osmer/state
GET /api/weather/bulletin/state
```

Endpoint protetti per audit/diagnostica:

```text
GET /api/weather/official-alerts/transitions
GET /api/weather/osmer/transitions
GET /api/weather/data-pipeline/audit
POST /api/weather/data-pipeline/dry-run/official-alerts
POST /api/weather/data-pipeline/dry-run/osmer
```

Endpoint dry-run attualmente presenti nel backend sorgente:

```text
POST /api/weather/data-pipeline/dry-run/official-alerts
POST /api/weather/data-pipeline/dry-run/osmer
```

Caratteristiche:

- protetti con `require_push_secret(request)`;
- accettano payload diretto oppure fixture/scenario dichiarati;
- restituiscono `observation`, `state`, `transition`;
- il dry-run `official-alerts` restituisce anche `storage_plan`;
- impostano sempre `dry_run=true`;
- non chiamano fetcher esterni;
- non scrivono Firestore;
- non inviano FCM;
- non sono collegati alla UI.

Il piano storage ufficiale e' dichiarativo:

```text
official_alert_state/current
official_alert_observations/{observation_id}
official_alert_transitions/{transition_id}
push_decision_audit/{transition_id}
```

Non e' storage reale: `dry_run=true` e `write_enabled=false`.

Endpoint push:

```text
POST /api/push/alerts/check
```

Regola: l'endpoint push deve leggere `official_alert_state/current` e inviare solo se `transition_actions` contiene `NOTIFY_NEW_OFFICIAL_ALERT`.

## Banco prova locale

Primo artefatto verificabile creato in UI 3.0.0:

- `frontend/src/domain/pipeline/backendDataStateContract.js`;
- `frontend/src/domain/pipeline/backendDataStateContract.test.js`.

Il banco prova non e' un backend e non chiama servizi.

Usa i motori puri gia presenti per produrre documenti con forma simile al contratto backend:

- `buildOfficialAlertObservationDocument()`;
- `buildOfficialAlertStateDocument()`;
- `buildOfficialAlertTransitionDocument()`;
- `buildOsmerBulletinObservationDocument()`;
- `buildOsmerBulletinStateDocument()`;
- `buildOsmerBulletinTransitionDocument()`.

Regole gia verificate:

- una nuova allerta attiva produce `NOTIFY_NEW_OFFICIAL_ALERT`;
- la stessa allerta ancora attiva produce `SUPPRESS_DUPLICATE_NOTIFICATION`;
- DPC no-active diagnostico trattiene una recente allerta regionale senza spegnerla;
- allerta scaduta senza rete diventa `expired`, non verde;
- verde/nessuna allerta regionale porta a `inactive_confirmed`;
- OSMER lookback produce `stale_from_cache` con warning;
- OSMER merge sanato produce `partial_healed`, `source_mix=true` e manifest aree recuperate.

Questo banco prova e' il ponte tra documento e backend reale.

## Prima trasposizione backend dry-run

Prima trasposizione nel backend sorgente, senza live integration:

- `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\backend\data_state_contract.py`;
- `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\backend\test_data_state_contract.py`.

Caratteristiche:

- modulo Python puro;
- nessun import da FastAPI;
- nessuna chiamata HTTP;
- nessuna scrittura Firestore;
- nessun invio FCM;
- endpoint dry-run in `main.py` protetti e senza effetti collaterali;
- nessuna modifica a endpoint pubblici per UI o push live.

Funzioni dry-run disponibili nel backend sorgente:

- `build_official_alert_observation_document()`;
- `build_official_alert_state_document()`;
- `build_official_alert_transition_document()`;
- `build_official_alert_storage_plan()`;
- `build_osmer_bulletin_observation_document()`;
- `build_osmer_bulletin_state_document()`;
- `build_osmer_bulletin_transition_document()`.

Queste funzioni producono i tre livelli del contratto senza effetti collaterali:

```text
observation -> state -> transition
```

Test backend verificati:

```text
python -m unittest test_data_state_contract
13 test passati

python -m unittest test_data_state_contract test_parser_osmer
18 test passati

python -m unittest test_data_state_contract test_parser_osmer test_weather_engine.DataPipelineDryRunEndpointTest
20 test passati

python -m py_compile main.py test_weather_engine.py data_state_contract.py test_data_state_contract.py
passato

Smoke HTTP locale verificato:

```text
POST /api/weather/data-pipeline/dry-run/official-alerts
fixture active-yellow-regional.json
state=active
source_authority=regional_fvg
transition_actions=NOTIFY_NEW_OFFICIAL_ALERT

POST /api/weather/data-pipeline/dry-run/osmer
scenario missing_area
state=partial
requested_date=2026-06-25
valid_dates=2026-06-25
warnings=osmer_partial_snapshot
```
```

Harness locale UI 3.0.0 per payload salvati:

- `backend_dryrun_staging/official_alert_payload_dryrun.py`;
- legge un JSON allerta completo gia salvato;
- importa solo `data_state_contract.py`;
- non importa `main.py`;
- non chiama rete;
- non scrive Firestore;
- non invia FCM;
- produce anche `user_effect`, cioe' la traduzione pratica per Home/Bollettino/notifiche.

Export dallo script sync sorgente:

- `scripts/sync-protezione-civile-alert-override.py --dry-run --export-payload <file>`;
- disponibile solo con `--dry-run`;
- espande il payload override in formato contratto con `alerts[]`;
- non cambia il workflow live se l'opzione non viene passata.

Film transizioni locale:

- `backend_dryrun_staging/official_alert_transition_film.py`;
- parte da una allerta gialla attiva precedente;
- verifica duplicato, no-alert confermato, stale, DPC diagnostico e unavailable;
- controlla `clears_previous_alert`, `can_notify` e visibilita Home.

Comando unico laboratorio:

- `backend_dryrun_staging/official_alert_live_report.py`;
- esegue `scripts/sync-protezione-civile-alert-override.py` solo con `--dry-run`;
- esporta un payload completo in `backend_dryrun_staging/exports/*.contract.json`;
- valuta subito `user_effect`;
- resta fuori da API runtime, Firestore, FCM e UI.

Fixture/matrici backend sorgente:

- `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\backend\fixtures\data_state\official_alert_cases.json`;
- `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\backend\fixtures\data_state\official_alerts\*.json`;
- `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\backend\fixtures\data_state\osmer_cases.json`;
- `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\backend\fixtures\data_state\README.md`.

Copertura fixture attuale:

- allerte regionali gialla, arancione e rossa;
- verde/nessuna allerta regionale confermata;
- fallback backend non disponibile;
- cache regionale stale;
- allerta regionale scaduta;
- fallback DPC diagnostico senza criticita FVG;
- fallback DPC attivo come diagnostica;
- override manuale verificato attivo;
- override manuale verificato inattivo;
- override no-active stale non confermativo;
- OSMER XML completo;
- OSMER A1-A9 incompleto;
- OSMER F1-F4 incompleto;
- OSMER XML non disponibile con lookback;
- OSMER merge sanato da snapshot precedente;
- OSMER proiezione ufficiale non XML nativo.

Stati OSMER dry-run espliciti:

- `ready`;
- `partial`;
- `partial_healed`;
- `stale_from_cache`;
- `projected`;
- `unavailable`.

Audit OSMER locale:

- `backend_dryrun_staging/osmer_source_audit.py`;
- legge XML OSMER reali o fixture;
- salva raw XML con hash;
- produce snapshot strutturato/merged;
- calcola `observation -> state -> transition`;
- non chiama backend runtime, Firestore, FCM o UI.

Esito reale 2026-06-26:

- XML letti: `NW20260627`, `PW20260625`, `PW20260624`;
- 404 attesi/non bloccanti: `NW20260628`, `PW20260626`;
- snapshot merged con giorni `2026-06-26`, `2026-06-27`, `2026-06-28`, `2026-06-29`;
- stato `ready`;
- `can_render_native_map=true`;
- nessun warning.

Report locale congiunto:

- `backend_dryrun_staging/data_pipeline_status_report.py`;
- legge solo audit salvati, senza rete e senza scritture;
- default `--scope live`: usa solo prove reali e non fixture;
- ignora audit OSMER invalidati;
- produce una decisione unica: Bollettino mostrabile, mappa renderizzabile, vecchie allerte spegnibili, notifiche ammesse solo in dry-run;
- include il blocco `polling` con prossimo controllo FVG, motivo, errori consecutivi e diagnostica Telegram/DPC ammessa o no.
- include il blocco `notification_decision`, calcolato da `official_alert_notification_policy.py`, con `can_notify`, `reason`, `severity`, `dedupe_key` e `live_connected=false`.

Matrice e test locali:

- `backend_dryrun_staging/data_pipeline_case_matrix.json`;
- `backend_dryrun_staging/test_data_pipeline_status_report.py`;
- `backend_dryrun_staging/official_alert_notification_policy.py`;
- `backend_dryrun_staging/test_official_alert_notification_policy.py`;
- `backend_dryrun_staging/official_alert_transition_policy.py`;
- `backend_dryrun_staging/test_official_alert_transition_policy.py`;
- coprono 8 casi allerta, 12 casi notifica e 5 casi OSMER minimi prima di qualunque collegamento live;
- verificano separazione `live` / `sample` e audit invalidati ignorati.

Caso `primary_unreachable_keep_previous_alert`:

- se il portale/widget FVG primario non e' raggiungibile e una allerta precedente e' ancora valida, l'app mantiene l'allerta precedente;
- la UI mostra l'allerta con la sua scadenza, senza testo "da verificare" o messaggi tecnici;
- Telegram FVG e DPC nazionale sono diagnostica interna;
- Telegram/DPC non possono spegnere allerta, dichiarare "nessuna allerta" o generare notifiche live.

Motore puro:

- `official_alert_transition_policy.py` riceve stato precedente, lettura primaria FVG e diagnostiche opzionali;
- non chiama rete, non scrive storage, non importa backend runtime e non invia notifiche;
- produce `final_alert_state`, `home_effect`, `bulletin_effect`, `notification_effect` e `audit_reason`;
- il test dedicato confronta il caso `primary_unreachable_keep_previous_alert` con la matrice dichiarativa.

## Matrice notifiche allerte

La decisione notifica vive in un motore puro separato:

- `backend_dryrun_staging/official_alert_notification_policy.py`;
- `backend_dryrun_staging/test_official_alert_notification_policy.py`.

Regole:

| Caso | Notifica |
| --- | --- |
| Nuova allerta gialla/arancione/rossa da fonte primaria FVG | Si |
| Stessa allerta gia nota | No |
| Cambio colore | Si |
| Cambio testo a parita di livello | No |
| Cambio testo a parita di livello marcato importante | Si |
| Fonte FVG irraggiungibile con vecchia allerta mantenuta | No |
| FVG conferma nessuna allerta | No |
| Allerta scaduta senza conferma FVG | No |
| Telegram FVG diagnostico | No |
| DPC nazionale diagnostico | No |

Output:

- `can_notify`;
- `reason`;
- `severity`;
- `dedupe_key`;
- `live_connected=false`.

La matrice e' presente anche in `data_pipeline_case_matrix.json` come `notification_cases`.

Regola `ready_for_review`:

- ammesso con allerta `active` o `inactive_confirmed`;
- richiede OSMER usabile e mappa A1-A9 renderizzabile;
- stati allerta `diagnostic`, `expired`, `stale`, `stale_held_active` e `unavailable` sono `needs_review`.

Esito report live 2026-06-26:

- allerta ufficiale: `inactive_confirmed`, 0 allerte trovate, Home e Bollettino senza avviso;
- prossimo controllo FVG: 30 minuti;
- diagnostica Telegram/DPC: non ammessa;
- decisione notifica: `inactive_confirmed_does_not_notify`, live non collegata;
- vecchia allerta: spegnibile;
- notifica: non ammessa;
- OSMER: `ready`, mappa A1-A9 renderizzabile;
- stato complessivo: `ready_for_review`.

Nota separata risolta:

```text
python -m unittest test_data_state_contract test_parser_osmer test_local_weather_pushes
```

aveva evidenziato un fallimento non collegato al nuovo modulo: `test_local_weather_pushes` si aspettava la vecchia copy "Oggi caldo a Pordenone", mentre il backend corrente produceva "Caldo intenso nelle ore più calde.". La copy caldo locale e' stata poi separata e fissata su frase breve, localizzata e non prescrittiva: `Caldo previsto oggi a {city}.`.

## Matrice sorgenti e autorita

| Fonte | `source_authority` | Puo accendere | Puo spegnere | Note |
| --- | --- | --- | --- | --- |
| Protezione Civile FVG pagina | `regional_fvg` | Si | Si | Fonte prioritaria. |
| Protezione Civile FVG widget | `regional_fvg` | Si | Si | Seconda fonte regionale. |
| Override manuale verificato | `manual_verified` / `manual_official_override` | Si | Si, solo per route protetta e auditata | Il backend sorgente usa `manual_official_override` come `source_mode`; il contratto dry-run lo classifica `manual_verified`. |
| DPC nazionale criticita FVG | `national_dpc` | No | No | Solo diagnostica: non sostituisce la fonte regionale FVG. |
| DPC nazionale no-active | `national_dpc` | No | No | Solo diagnostica: non dichiara "nessuna allerta" per FVG. |
| Backend fallback unavailable | `backend_fallback` | No | No | Non significa verde. |

Audit sorgenti reali:

- `REAL_SOURCE_TO_CONTRACT_AUDIT.md` mappa il percorso reale del backend sorgente verso questa matrice.
- Allineamento dry-run completato: `manual_official_override` resta `source_mode`, ma viene classificato con `source_authority=manual_verified`.
- Gap notifiche live risolto in laboratorio: `dispatch_official_alert_pushes()` usa una decisione derivata da `transition_actions`, non `alerts[]` come decisore diretto.

## Cadenza controllo fonte FVG

La fonte primaria FVG va controllata con una cadenza variabile in base allo stato corrente.

Questa e' una policy architetturale, non uno scheduler gia collegato.

| Stato corrente | Cadenza controllo FVG | Motivo |
| --- | --- | --- |
| Nessuna allerta confermata | Ogni 30 minuti | Evita polling aggressivo quando la situazione e' stabile. |
| Allerta attiva | Ogni 10-15 minuti | Serve intercettare cambi di colore, testo, validita o rimozione. |
| Fonte FVG irraggiungibile | Retry a 5 minuti, poi 10, poi 20-30 | Recupera rapidamente errori temporanei senza insistere all'infinito. |
| Ultima ora prima della scadenza allerta | Ogni 5-10 minuti | Evita di tenere visibile una allerta oltre la validita senza nuova verifica. |
| Fonte FVG tornata raggiungibile | Riprende la cadenza coerente con lo stato letto | La decisione torna alla fonte primaria FVG. |

Regole:

- Telegram FVG e DPC nazionale non fanno parte della cadenza decisionale;
- Telegram/DPC possono essere consultati solo come diagnostica dopo errori ripetuti della fonte FVG;
- un controllo FVG fallito non spegne una allerta valida;
- un controllo FVG riuscito con `inactive_confirmed` puo spegnere una vecchia allerta;
- le notifiche restano separate: controllare la fonte non significa inviare una push.

Banco prova locale:

- `backend_dryrun_staging/official_alert_polling_policy.py`;
- `backend_dryrun_staging/test_official_alert_polling_policy.py`.

La funzione pura produce:

- `next_check_minutes`;
- `next_check_seconds`;
- `reason`;
- diagnostica ammessa/non ammessa;
- `scheduler_connected=false`;
- `live_connected=false`.

La policy e' quindi testata, ma non ancora collegata a GitHub Actions, Cloud Scheduler, Firestore, FCM o UI.

## Criteri di accettazione prima del collegamento

Prima di collegare davvero backend/live:

1. fixture per almeno 7 casi allerta:
   - gialla FVG;
   - arancione FVG;
   - rossa FVG;
   - verde/nessuna allerta FVG;
   - fonte FVG non disponibile;
   - DPC attivo come diagnostica non decisionale;
   - DPC no-active diagnostico.
2. fixture OSMER per almeno 5 casi:
   - XML completo;
   - A1-A9 incompleto;
   - F1-F4 incompleto;
   - XML non disponibile a mezzanotte;
   - merge sanato da snapshot precedente.
3. test motori transizione lato backend o condivisi.
4. endpoint dry-run che calcola lo stato senza scrivere e senza notificare.
5. log audit consultabile.
6. push reale disabilitabile con flag.
7. procedura di rollback scritta.

Stato attuale:

- punti 1, 2, 3 e 4 coperti in dry-run backend sorgente;
- punti 5-7 non ancora avviati per scelta progettuale.

## Gate read-only prima del live

Prima di toccare Cloud Run, GitHub Actions, Firestore finale o FCM va eseguito:

```text
python -B backend_dryrun_staging/backend_live_bridge_readiness.py
```

Il gate non collega nulla e non modifica file del vecchio progetto. Legge solo il sorgente e deve risultare `ready` prima di qualunque tranche live.

Al 2026-06-27 il risultato corretto e' `ready`.

Tranche A packaging completata: il Dockerfile sorgente copia ora `data_state_contract.py` e il controllo dedicato passa.

Tranche B workflow completata: `sync-official-alerts.yml` non contiene piu il push check reale `dry_run:false`; il controllo resta solo in `dry_run:true`.

Tranche C DPC completata: lo script sorgente non usa piu DPC nazionale come override decisionale; il payload DPC e' diagnostico e `skip_backend_update`.

Tranche D storage plan completata: il dry-run ufficiale produce `storage_plan` con `official_alert_state/current`, osservazioni, transizioni e audit push; il piano resta non operativo con `write_enabled=false`.

Tranche E push completata: il dispatcher push ufficiale passa dal contratto `state/transition`; DPC nazionale resta diagnostica e non puo produrre notifica.

Blocchi residui:

- nessun blocco del gate read-only;

## Sequenza di implementazione consigliata

1. Portare o condividere i motori puri lato backend senza Firestore.
2. Usare il banco prova locale come riferimento per fixture backend e test unitari.
3. Creare funzioni pure:
   - `buildOfficialAlertObservation()`;
   - `transitionOfficialAlertState()`;
   - `buildOsmerBulletinObservation()`;
   - `transitionOsmerBulletinState()`.
4. Creare endpoint dry-run locali.
5. Solo dopo collegare scrittura storage locale/file.
6. Solo dopo collegare Firestore.
7. Solo dopo esporre endpoint state alla UI.
8. Solo dopo valutare notifiche in dry-run.
9. Solo dopo valutare push reale.

## Decisione architettonica

Il backend della UI 3.0.0 deve essere progettato come motore di stato, non come semplice proxy di pagine HTML/XML.

La UI non deve indovinare.

GitHub Actions, Cloud Run, Firestore e notifiche devono restare strumenti intorno al motore, non il luogo in cui nasce la decisione.
