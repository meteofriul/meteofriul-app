# Meteo Friul UI 3.0.0 - Audit dati Bollettino, OSMER e allerte

Data: 2026-06-24

## Scopo

Questo documento non collega servizi e non modifica la UI.

Serve solo a fissare una lettura accurata del vecchio sistema dati prima di decidere come riscriverlo in modo pulito nella UI 3.0.0.

Fonti lette:

- `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\backend\main.py`
- `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\backend\parser_osmer.py`
- `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\backend\test_parser_osmer.py`
- `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\backend\test_weather_engine.py`
- `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\scripts\sync-protezione-civile-alert-override.py`
- `F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\.github\workflows\sync-official-alerts.yml`
- documenti operativi del vecchio progetto su notifiche e fetcher ufficiale.

## Sintesi netta

Il problema non e' unico.

Il Bollettino OSMER ha due strati diversi:

1. previsioni/A1-A9: relativamente solide, perche' arrivano da XML strutturato OSMER;
2. allerte ufficiali: piu fragili, perche' passano da Protezione Civile FVG, pagina HTML/widget JSONP, override Firestore e fallback nazionale DPC.

La nuova app non deve leggere solo `active=false` per decidere che non ci sono allerte.

Deve leggere almeno:

- `active`;
- `count`;
- `alerts`;
- `source_mode`;
- `cache.status`;
- `cache.reason`;
- `error`;
- `fetched_at`;
- eventuale `warning`.

## Bollettino OSMER strutturato

### Fonte

Il vecchio backend non costruisce A1-A9 dalla pagina HTML pubblica `home.php`.

La parte A1-A9 viene da XML OSMER:

```text
https://dev.meteo.fvg.it/xml/previsioni/PWYYYYMMDD.xml
https://dev.meteo.fvg.it/xml/previsioni/NWYYYYMMDD.xml
```

Il backend scopre i file dalla pagina `https://dev.meteo.fvg.it/` e aggiunge anche candidati calcolati per lookback/lookahead.

### Parser

`parser_osmer.py` produce uno snapshot con:

- `id_emissione`;
- `source_date`;
- `requested_date`;
- `published_at`;
- `updated_at`;
- `raw_hash`;
- `parser_version`;
- `schema_version`;
- `testo_ufficiale`;
- `days`;
- `quality`.

Ogni giorno contiene:

- `valid_date`;
- `regional`;
- `areas9`;
- `fasce4`;
- `quality`.

Le aree obbligatorie sono:

```text
A1, A2, A3, A4, A5, A6, A7, A8, A9
```

Le fasce obbligatorie sono:

```text
F1, F2, F3, F4
```

Ogni area A1-A9 contiene:

- attendibilita;
- testo;
- probabilita precipitazioni;
- probabilita temporali;
- quota neve;
- dati montagna quando presenti;
- simboli cielo/pioggia/neve/temporale/nebbia/vento;
- condizione dominante.

### Qualita gia disponibile

Il parser dichiara:

- `quality.xml_valid`;
- `quality.days_count`;
- `quality.all_days_complete`;
- `quality.incomplete_days`;
- `quality.confidence`.

Per ogni giorno:

- `quality.all_nodes_present`;
- `quality.missing_nodes`;
- `quality.all_fasce_present`;
- `quality.missing_fasce`;
- `quality.confidence`.

Questa e' una buona base. La nuova pipeline deve conservarla e non appiattirla.

### Cosa deve capire il parser

Nel progetto nuovo il parser non deve essere un semplice lettore di campi.

Deve produrre una lettura semantica controllata:

- riconoscere se la fonte e' stata letta davvero;
- distinguere XML OSMER nativo da testo proiettato;
- riconoscere giorni validi, giorni scaduti e giorni mancanti;
- verificare se A1-A9 e F1-F4 sono completi;
- classificare la condizione meteo dominante senza inventare dati;
- conservare il testo ufficiale separato dai dati derivati;
- assegnare una qualita al risultato;
- dichiarare esplicitamente quando non puo capire abbastanza.

Quindi "capire" significa trasformare la fonte in un contratto dati leggibile dalla app:

```text
fonte letta -> struttura valida -> significato normalizzato -> qualita dichiarata
```

Se manca un pezzo, il parser non deve andare avanti in silenzio: deve restituire stato parziale, mancante o non affidabile.

### Merge giorni

Il vecchio backend unisce piu snapshot XML per data valida, non per indice.

Regola osservata:

- lo snapshot piu recente vince per una data;
- giorni con `valid_date` passata rispetto alla richiesta vengono scartati;
- se un giorno manca nello XML piu recente, puo essere recuperato da snapshot precedente;
- `PW` copre lookback;
- `NW` copre lookahead.

Questa regola va mantenuta.

### Fallback testuale/proiezioni

Il backend puo completare date mancanti usando testo ufficiale OSMER trasformato in `official_projected`.

Questo e' utile ma piu rischioso dello XML:

- non e' A1-A9 nativo;
- deriva da testo;
- deve restare marcato come proiezione;
- non deve sovrascrivere giorni XML reali;
- non deve essere confuso con `structured_xml`.

## Allerte ufficiali

### Fonti

Il vecchio sistema usa:

1. pagina Protezione Civile FVG:

```text
https://www.protezionecivile.fvg.it/it/allerte
```

2. widget JSONP Protezione Civile FVG:

```text
https://pianiemergenza.protezionecivile.fvg.it/api/alerts.jsonp
```

3. override backend/Firestore:

```text
official_alert_overrides/current
```

4. fallback nazionale DPC:

```text
pcm-dpc/DPC-Bollettini-Criticita-Idrogeologica-Idraulica
```

### Perche esiste il fetcher esterno

Il vecchio progetto documenta che Cloud Run non raggiunge in modo affidabile le fonti Protezione Civile FVG.

Per questo esiste GitHub Actions:

```text
.github/workflows/sync-official-alerts.yml
scripts/sync-protezione-civile-alert-override.py
```

Il workflow gira su cron circa ogni 10 minuti, legge le fonti esterne e aggiorna l'override backend.

Questo e' un punto progettuale importante: il path di lettura dell'app non dovrebbe dipendere da scraping live fragile.

### Stati osservati

Possibili stati reali o quasi reali:

| Caso | Significato | Come va trattato |
| --- | --- | --- |
| `active=true`, alert non verde | Allerta ufficiale attiva | mostra banner, dettaglio, possibile notifica |
| `active=false`, `source_mode=github_actions_official_page` | pagina FVG letta e nessuna allerta attiva | spegnimento credibile |
| `active=false`, `source_mode=github_actions_official_widget` | widget FVG letto e nessuna allerta attiva | spegnimento credibile |
| `active=false`, `source_mode=official_widget` | widget letto direttamente e solo verde/nessuna allerta | spegnimento credibile se fetch diretto abilitato e recente |
| `active=false`, `source_mode=official_alerts_unavailable_fast_fallback` | il backend non ha letto la fonte | non e' prova di nessuna allerta |
| `active=false`, `cache.status=stale` | stato vecchio o override inattivo scaduto | non e' prova fresca |
| `source_mode=github_actions_dpc_national_criticity_fallback` | fallback nazionale segnala criticita FVG | vecchio comportamento operativo da non importare come decisione UI 3.0.0; nella nuova pipeline resta diagnostica |
| `source_mode=github_actions_dpc_national_criticity_no_active_fvg_unverified` | DPC non segnala criticita FVG, ma FVG non era raggiungibile | diagnostico, non verde FVG verificato |

## Punto fragile principale

Nel vecchio backend `build_official_alerts_unavailable_response()` restituisce:

```json
{
  "active": false,
  "count": 0,
  "alerts": [],
  "source_mode": "official_alerts_unavailable_fast_fallback",
  "cache": {
    "status": "unavailable"
  },
  "error": "official_alerts_unavailable"
}
```

Questo e' corretto come fallback tecnico, ma e' pericoloso se il frontend legge solo `active=false`.

Regola per UI 3.0.0:

```text
active=false non basta per dire nessuna allerta.
Serve una conferma fresca da fonte regionale o override verificato.
```

## Spegnimento allerta

La nuova pipeline deve spegnere un'allerta solo se una di queste condizioni e' vera:

1. fonte regionale FVG letta con successo e ritorna nessuna allerta/verde;
2. override verificato e recente con `active=false`;
3. stato attivo precedente e' scaduto, ma in UI va mostrato come scaduto/non aggiornato, non come verde verificato, finche' non arriva lettura fresca.

Non basta:

- fetch fallito;
- parser fallito;
- fallback nazionale senza criticita FVG;
- stato stale;
- `active=false` con `error`.

## Notifiche

La vecchia logica notifiche ufficiali:

- chiama `sync_official_alerts_external_fetcher()`;
- legge `fetch_civil_protection_alerts()`;
- filtra con `actionable_official_alerts`;
- invia solo alert non verdi;
- deduplica per firma allerta e installazione.

La nuova UI non deve importare questa logica.

Per ora va solo registrato che le notifiche dipendono dalla stessa qualita della fonte allerta. Se la fonte e' `unavailable` o `stale`, non deve partire una notifica ufficiale nuova.

## Rischi da risolvere prima dell'integrazione

1. Il contratto `official_alerts` mescola stato operativo e stato utente:
   - `active=false` puo voler dire nessuna allerta;
   - oppure fonte non letta.

2. La fonte regionale FVG non e' sempre raggiungibile da Cloud Run.

3. GitHub Actions non e' un timer realtime garantito.

4. Il fallback DPC nazionale puo essere utile come diagnostica quando FVG non risponde, ma nella nuova pipeline non e' equivalente alla pagina regionale e non decide stato o notifiche.

5. Il vecchio frontend e alcuni test gia difendono il caso verde, ma la nuova app deve difendere anche `unavailable`.

6. Il canale FUR delle previsioni esiste, ma non va trattato dentro questa fase: prima si fissa la certezza del dato ufficiale IT/source.

## Contratto dati consigliato

Per UI 3.0.0 il backend dovrebbe distinguere esplicitamente gli stati interpretati dal parser/fetcher, non lasciare questa logica alla UI:

```json
{
  "official_alerts": {
    "state": "active | inactive_confirmed | unavailable | stale | expired | diagnostic",
    "active": false,
    "count": 0,
    "alerts": [],
    "source_mode": "github_actions_official_page",
    "source_authority": "regional_fvg | national_dpc | backend_fallback",
    "freshness": "fresh | stale | unknown",
    "confidence": "high | medium | low",
    "fetched_at": "",
    "expires_at": "",
    "error": ""
  }
}
```

Stati minimi:

- `active`: allerta ufficiale non verde valida;
- `inactive_confirmed`: fonte regionale o override verificato dice verde/nessuna allerta;
- `unavailable`: fonte non letta;
- `stale`: dato vecchio;
- `expired`: vecchia allerta scaduta senza conferma fresca;
- `diagnostic`: fallback nazionale senza criticita FVG, ma regionale non raggiungibile.

## Regole UI conseguenti

Home:

- mostra `Allerta gialla/arancione/rossa` solo con `state=active`;
- non mostra "nessuna allerta";
- se `state=unavailable/stale/diagnostic`, non mostra allerta, ma il Bollettino puo avere una nota discreta.

Bollettino:

- mostra dettaglio allerta solo con `state=active`;
- mostra "Stato allerte non aggiornato" solo se serve e solo nel dettaglio;
- non deve trasformare `unavailable` in verde.

Notifiche future:

- invio solo con `state=active` e azione di transizione `NOTIFY_NEW_OFFICIAL_ALERT`;
- una conferma ripetuta della stessa allerta resta visibile come banner, ma produce `SUPPRESS_DUPLICATE_NOTIFICATION`;
- no invio con `inactive_confirmed`;
- no invio con `unavailable/stale/diagnostic`;
- deduplica basata su firma allerta e validita.

## Test di comportamento aggiunti

La prima protezione concreta e' nel dominio frontend, senza collegare fonti live:

- `frontend/src/domain/alerts/officialAlerts.js`
- `frontend/src/domain/alerts/officialAlerts.test.js`
- `frontend/src/features/home/homeViewModel.test.js`
- `frontend/src/features/bulletin/bulletinViewModel.test.js`

Contratti ora coperti:

- allerta regionale attiva: `state=active`, banner/notifica permessi;
- verde o nessuna allerta da fonte regionale letta: `state=inactive_confirmed`, spegnimento permesso;
- fonte non letta: `state=unavailable`, nessuno spegnimento e nessun banner;
- cache vecchia: `state=stale`, nessun banner e nessuna notifica;
- allerta scaduta: `state=expired`, nessun banner;
- fallback DPC senza criticita FVG: `state=diagnostic`, non verde verificato.

Fixture create in `frontend/src/tests/fixtures/officialAlerts/`:

- `active-yellow-regional.json`;
- `inactive-confirmed-regional.json`;
- `unavailable-fast-fallback.json`;
- `stale-regional-cache.json`;
- `expired-regional-alert.json`;
- `diagnostic-dpc-no-active-fvg.json`;
- `active-orange-dpc-fallback.json`.

Il file `frontend/src/domain/alerts/officialAlertContract.test.js` usa queste fixture come matrice di contratto: ogni payload deve dichiarare se puo mostrare banner, spegnere una vecchia allerta o autorizzare una notifica futura.

Regola protetta:

```text
Home e Bollettino non devono perdere `source_mode/cache/error` filtrando prima l'array `alerts`.
La classificazione deve avvenire sul payload ufficiale intero.
```

## Test di comportamento OSMER strutturato

Aggiunto un contratto puro per distinguere dato OSMER nativo, parziale, stale, non disponibile e proiettato:

- `frontend/src/domain/weather/osmerStructuredContract.js`;
- `frontend/src/domain/weather/osmerStructuredContract.test.js`;
- `frontend/src/features/bulletin/bulletinViewModel.test.js`.

Contratti ora coperti:

- XML normalizzato reale con A1-A9 e F1-F4 complete: `state=ready`, mappa nativa ammessa;
- A1-A9 incomplete: `state=partial`, mappa non rappresentabile;
- F1-F4 incomplete: `state=partial`, geometria mappa possibile ma bollettino non pienamente completo;
- snapshot stale/source unavailable: `state=stale`, non usabile come mappa nativa corrente;
- fonte senza giorni: `state=unavailable`;
- giorno `official_projected`: rappresentazione proiettata distinta da XML nativo.

Regola protetta:

```text
La UI puo considerare una mappa "OSMER strutturata nativa" solo se il contratto dice `canRenderNativeMap=true`.
Un dato `official_projected`, stale o incompleto non deve essere presentato come XML OSMER nativo.
```

## Motori di transizione

Aggiunti due motori puri per testare i cambi di stato nel tempo:

- `frontend/src/domain/alerts/officialAlertTransition.js`;
- `frontend/src/domain/alerts/officialAlertTransition.test.js`;
- `frontend/src/domain/weather/osmerBulletinTransition.js`;
- `frontend/src/domain/weather/osmerBulletinTransition.test.js`.

### Transizione allerte

Contratti coperti:

- flapping: una recente allerta regionale `active` non viene spenta da un DPC nazionale `diagnostic`;
- `stale_held_active`: mantiene memoria dell'allerta precedente, disabilita nuove notifiche e non certifica il verde;
- allerta nuova o cambiata: produce `NOTIFY_NEW_OFFICIAL_ALERT`;
- stessa allerta ancora attiva: mantiene banner e dettaglio, ma produce `SUPPRESS_DUPLICATE_NOTIFICATION`;
- scadenza senza rete: una vecchia allerta diventa `expired`, non `inactive_confirmed`;
- spegnimento vero: solo fonte regionale `official_page/widget` con verde/nessuna allerta porta a `inactive_confirmed`.

Azioni operative dichiarate:

- `NOTIFY_NEW_OFFICIAL_ALERT`;
- `SUPPRESS_DUPLICATE_NOTIFICATION`;
- `DISABLE_NEW_NOTIFICATIONS`;
- `KEEP_BULLETIN_NOTICE`;
- `LOG_DIAGNOSTIC_ALERT`;
- `HIDE_BANNER_FROM_HOME`;
- `RETAIN_DB_CRITICALITY`;
- `CLEAR_ALL_ALERTS_AND_BANNERS`;
- `RESET_STATE_ENGINE`.

### Transizione OSMER

Contratti coperti:

- lookback a 36 ore: se l'XML corrente non e' disponibile a mezzanotte, uno snapshot precedente puo restare usabile se contiene `valid_date` richiesta;
- merge sanato: se lo XML nuovo e' quasi completo ma manca una zona, la zona puo essere recuperata dallo snapshot precedente;
- ogni merge sanato conserva `source_mix`, `healed_missing_areas`, `primary_source_date`, `fallback_source_date` e confidenza declassata.

Regola protetta:

```text
Il sistema puo sanare un buco OSMER, ma non puo far finta che il dato sia interamente fresco e omogeneo.
```

## Collaudo scenario completo

Aggiunto un collaudo test-only:

- `frontend/src/domain/pipeline/bulletinPipelineScenario.test.js`.

Il test simula il ciclo completo:

- allerta regionale attiva;
- fallback DPC diagnostico senza spegnimento della regionale;
- allerta scaduta senza rete, che diventa `expired` e non verde;
- ritorno della fonte regionale verde, che certifica lo spegnimento;
- buco XML OSMER a mezzanotte coperto da lookback;
- XML OSMER nuovo incompleto sanato con area da snapshot precedente.

Il collaudo proietta anche un contratto app minimo:

- Home: banner fresco, banner trattenuto, notifica si/no;
- Bollettino: notice allerta, mappa nativa, stato bollettino;
- audit: azioni operative da registrare.

## Audit infrastrutturale prima del collegamento

Prima di collegare questi contratti a dati reali serve una fase separata su:

- Cloud Run: raggiungibilita fonti, timeout, retry, cold start, variabili ambiente;
- Firebase Hosting: proxy `/api/**`, deploy order, cache e pinning backend;
- GitHub Actions: schedulazione, segreti, retry, scrittura override, ritardi cron;
- Firestore/storage: formato stato precedente, TTL, storico audit, lock concorrenti;
- notifiche push: deduplica, firma allerta, dry-run, invio reale disabilitabile.

Regola:

```text
Nessun collegamento live prima di sapere dove vive lo stato precedente e chi ha autorita per aggiornarlo.
```

## Prossimo audit consigliato

Prima di implementare:

1. raccogliere 3-5 payload reali o fixture per ciascun caso:
   - allerta gialla FVG;
   - allerta arancione FVG;
   - allerta rossa FVG;
   - nessuna allerta regionale verificata;
   - fonte regionale non raggiungibile;
   - fallback DPC attivo storico da declassare a diagnostica;
   - fallback DPC diagnostico senza criticita.
2. scrivere test sul parser semantico e sul contratto dati;
3. solo dopo collegare UI/cache/notifiche.

## Decisione provvisoria

Per ora la parte piu sicura da portare nella UI 3.0.0 e':

- XML OSMER strutturato per A1-A9;
- qualita parser;
- responsabilita semantica del parser;
- merge per `valid_date`;
- separazione `structured_xml` / `official_projected`;
- policy che non inventa marker se A1-A9 mancano.

La parte da ridisegnare prima di qualunque integrazione e':

- contratto `official_alerts`;
- stati di spegnimento allerta;
- distinzione fra "nessuna allerta confermata" e "fonte non disponibile".
