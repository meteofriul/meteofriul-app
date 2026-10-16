# Meteo Friul UI 3.0.0 - Audit sorgenti reali verso contratto allerte

Data: 2026-06-25

## Scopo

Questo audit mette in fila il percorso reale delle allerte ufficiali nel backend sorgente e lo confronta con il contratto dati UI 3.0.0.

Non collega nulla.

Non cambia parser, Firestore, Cloud Run, GitHub Actions, notifiche o UI.

La domanda a cui risponde e':

```text
Quando OSMER/Protezione Civile/GitHub/DPC producono un payload, il contratto sa capire se puo:
- mostrare una allerta;
- inviare una notifica;
- trattenere una vecchia allerta;
- spegnere una vecchia allerta;
- oppure segnare solo diagnostica/non disponibilita?
```

## Regola base

La lista vuota `alerts=[]` non basta per dire "nessuna allerta".

Per spegnere una vecchia allerta serve una lettura regionale fresca e autorevole:

```text
state=inactive_confirmed
source_authority=regional_fvg
can_clear_previous_alert=true
```

Tutti gli altri casi senza alert sono prudenziali:

- `diagnostic`;
- `unavailable`;
- `stale`;
- `expired`;
- `stale_held_active`.

## Percorso reale letto

Nel backend sorgente il percorso principale e' in:

```text
F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\backend\main.py
```

Funzioni rilevanti:

| Funzione | Ruolo |
| --- | --- |
| `parse_civil_protection_alerts()` | Parser HTML pagina Protezione Civile FVG. |
| `parse_civil_protection_widget_alerts()` | Parser JSONP widget Protezione Civile FVG. |
| `official_alert_override_is_current()` | Decide se un override Firestore/memoria e' ancora valido. |
| `build_official_alert_override()` | Costruisce payload override da route protetta. |
| `build_stale_inactive_official_alert_response()` | Trasforma un vecchio inactive override in risposta stale prudenziale. |
| `build_official_alerts_unavailable_response()` | Fallback veloce quando la fonte non viene letta. |
| `fetch_civil_protection_alerts()` | Lettura corrente usata da bootstrap/push. |
| `sync_official_alerts_external_fetcher()` | Chiama sync esterno, se configurato. |
| `dispatch_official_alert_pushes()` | Push ufficiali correnti; oggi non legge ancora il nuovo contratto `transition_actions`. |

Script esterno GitHub:

```text
F:\proggetto Meteo Friul App\meteo friul 13 - Nuova UI con Figma\scripts\sync-protezione-civile-alert-override.py
```

Funzioni rilevanti:

| Funzione | Ruolo |
| --- | --- |
| `fetch_official_source()` | Prova pagina FVG, poi widget FVG, poi fallback nazionale DPC. |
| `parse_national_dpc_criticity_alerts()` | Estrae criticita FVG dal bollettino nazionale DPC. |
| `current_is_active_regional_override()` | Riconosce se il backend ha gia una allerta regionale piu precisa. |
| `current_override_is_more_precise_than_dpc_fallback()` | Evita che DPC sovrascriva una fonte regionale migliore. |
| `build_dpc_no_active_diagnostic_payload()` | Crea payload diagnostico quando DPC non indica criticita FVG ma FVG non e' raggiungibile. |
| `build_override_payload()` | Produce payload attivo, inactive confermato, skip o clear. |
| `summarize_payload()` | Riassume l'azione prima del post al backend. |

## Priorita reale di lettura

`fetch_civil_protection_alerts()` oggi segue questa logica:

1. cache in memoria `protezione_civile_alerts_cache`;
2. override corrente da memoria/Firestore;
3. se `allow_direct_fetch` non e' esplicito, usa `PROTEZIONE_CIVILE_DIRECT_FETCH_ON_READ`;
4. se il fetch diretto e' disabilitato:
   - prova stale inactive override;
   - altrimenti ritorna `official_alerts_unavailable_fast_fallback`;
5. se il fetch diretto e' abilitato:
   - prova pagina FVG;
   - se fallisce prova widget FVG;
   - se pagina non produce alert prova comunque widget;
   - filtra solo alert non verdi;
   - mette in cache la risposta;
6. se il fetch diretto fallisce:
   - riprova override;
   - poi stale inactive override;
   - poi stale cache;
   - poi unavailable fallback.

Questa scelta e' corretta per non bloccare la lettura app, ma significa che `active=false` sul read path puo essere:

- quiete regionale confermata;
- fallback tecnico;
- stale prudenziale;
- fonte non letta.

Per questo serve il contratto.

## Matrice sorgente -> contratto

| Sorgente reale | `source_mode` reale | Stato contratto atteso | Autorita | Notifica | Spegne vecchia allerta | Note |
| --- | --- | --- | --- | --- | --- | --- |
| Pagina Protezione Civile FVG via GitHub | `github_actions_official_page` | `active` se non verde, `inactive_confirmed` se verde/no-active | `regional_fvg` | Si solo se `active` nuovo | Si solo se `inactive_confirmed` | Fonte prioritaria per accendere e spegnere. |
| Widget Protezione Civile FVG via GitHub | `github_actions_official_widget` | `active` se non verde, `inactive_confirmed` se verde/no-active | `regional_fvg` | Si solo se `active` nuovo | Si solo se `inactive_confirmed` | Seconda fonte regionale autorevole. |
| Pagina FVG letta direttamente dal backend | `official_page` | `active` o `inactive_confirmed` | `regional_fvg` | Si solo se `active` nuovo | Si solo se `inactive_confirmed` | Oggi non e' il percorso normale se direct fetch su read e' disabilitato. |
| Widget FVG letto direttamente dal backend | `official_widget` | `active` o `inactive_confirmed` | `regional_fvg` | Si solo se `active` nuovo | Si solo se `inactive_confirmed` | Deve restare fallback regionale, non fonte secondaria generica. |
| Override manuale protetto | `manual_official_override` | `active` se contiene alert, `inactive_confirmed` se conferma no-active | `manual_verified` | Si solo se `active` nuovo | Si solo se `inactive_confirmed` | Allineato in dry-run: il `source_mode` reale resta `manual_official_override`, l'autorita semantica e' `manual_verified`. |
| Worker/widget terzo ma regionale | `cloudflare_worker_official_widget` | `active`/`inactive_confirmed` se normalizzato come widget ufficiale | `regional_fvg` per substring `official_widget` | Si solo se `active` nuovo | Si solo se `inactive_confirmed` | Gia riconosciuto dallo script come regionale, da tenere solo se auditato. |
| Fallback DPC nazionale con criticita FVG | `github_actions_dpc_national_criticity_fallback` | `diagnostic` | `national_dpc` | No | No | Decisione aggiornata: supporto diagnostico soltanto; non accende UI 3.0.0 e non notifica. |
| Fallback DPC nazionale senza criticita FVG | `github_actions_dpc_national_criticity_no_active_fvg_unverified` | `diagnostic` | `national_dpc` | No | No | Non e' verde regionale. Se esiste allerta recente, il contratto puo produrre `stale_held_active`. |
| Stale inactive override | `stale_no_alert_override` oppure source regionale stale | `stale` | `unknown` o `regional_fvg` se source originale resta presente | No | No | Prudenziale: non deve pulire banner/stato precedente. |
| Cache stale dopo refresh fallito | source originale + `cache.status=stale` | `stale` | dipende da source originale | No | No | Conserva informazione, ma non e' fresca. |
| Allerta scaduta senza conferma fresca | source originale + `expires_at` passato | `expired` | dipende da source originale | No | No | Non equivale a nessuna allerta. |
| Fallback backend non disponibile | `official_alerts_unavailable_fast_fallback` | `unavailable` | `backend_fallback` | No | No | Non significa verde. |

## Punti solidi gia verificati

- Il widget verde/non attivo non e' azionabile.
- Il read path normale non deve fare fetch diretto bloccante.
- Il fallback unavailable non puo spegnere una vecchia allerta.
- Il DPC no-active e' diagnostico, non quiete regionale.
- Il DPC active storico non deve diventare stato finale UI 3.0.0: resta diagnostica interna.
- Lo script esterno preserva una allerta regionale corrente se il fallback DPC e' meno preciso.
- Il nuovo endpoint dry-run restituisce `observation -> state -> transition` senza HTTP esterno, Firestore o FCM.

## Punti prima del collegamento

### 1. Override manuale normalizzato in dry-run

Il contratto architetturale cita:

```text
manual_verified
```

Il backend sorgente usa:

```text
manual_official_override
```

Decisione presa nel dry-run:

- `manual_official_override` resta il `source_mode` reale del backend sorgente;
- `source_authority` diventa `manual_verified`;
- un override manuale attivo puo notificare;
- un override manuale inattivo puo spegnere una vecchia allerta;
- questo resta ammesso solo per route protette e auditabili.

### 2. Stale inactive override non deve diventare verde

`build_stale_inactive_official_alert_response()` e' utile per non mostrare errore se abbiamo una vecchia quiete, ma non deve diventare:

```text
inactive_confirmed
```

Nel contratto deve restare:

```text
stale
can_clear_previous_alert=false
```

### 3. Push corrente non usa ancora `transition_actions`

`dispatch_official_alert_pushes()` oggi:

1. fa sync esterno;
2. legge `fetch_civil_protection_alerts()`;
3. filtra `actionable_official_alerts()`;
4. invia se non duplicato.

Quindi il nuovo contratto dry-run e' pronto, ma non e' ancora il decisore reale delle notifiche.

Regola futura:

```text
invia push solo se transition_actions contiene NOTIFY_NEW_OFFICIAL_ALERT
```

### 4. Empty parser non significa fonte confermata

Un parser che torna `[]` puo significare:

- nessuna allerta;
- HTML cambiato;
- widget vuoto;
- fonte non raggiunta;
- fallback non regionale.

Il contratto deve ricevere sempre `source_mode`, `cache.status`, `error`, `fetched_at` e possibilmente `parser_status`.

### 5. Serve raw/audit trail prima del live

Prima del collegamento reale servono:

- raw ref o snapshot hash;
- observation_id stabile;
- transition_id;
- storage consultabile;
- dry-run confrontabile su payload reali.

## Decisione operativa

Il sistema corretto non deve essere:

```text
parser -> active -> UI/push
```

Deve essere:

```text
fonte reale -> observation -> state -> transition -> UI/push
```

Per le allerte ufficiali, la transizione e' piu importante del parser.

Il parser deve estrarre bene, ma la decisione deve stare nel contratto.

## Prossimo passo consigliato

Senza collegare ancora nulla:

1. usare `backend_dryrun_staging/official_alert_source_audit.py` per salvare raw snapshot, hash, payload e risultato contratto;
2. usare `backend_dryrun_staging/official_alert_live_report.py` per una lettura rapida fonte -> effetto utente;
3. usare `backend_dryrun_staging/official_alert_case_table.py` per leggere tutti i casi come effetto utente;
4. confrontare le transizioni delicate con `official_alert_transition_film.py`;
5. solo dopo progettare il passaggio da push corrente a `transition_actions`.

Film dry-run disponibile:

- `backend_dryrun_staging/official_alert_transition_film.py` verifica il passaggio da una gialla attiva a:
  - stessa allerta;
  - no-alert confermato;
  - stale;
  - DPC no-active diagnostico;
  - unavailable.

Primo esito live con comando unico, 2026-06-26:

```text
parser=page
alerts_found=0
state=inactive_confirmed
home=nessuna allerta in Home
bollettino=nessun avviso allerta nel Bollettino
notifiche=non inviata: fonte verificata senza allerta
stato_precedente=spegne una vecchia allerta
```

Tabella casi dry-run disponibile:

- `backend_dryrun_staging/official_alert_case_table.py --format markdown` verifica 12 casi su 12 contro gli attesi base;
- `backend_dryrun_staging/official_alert_case_table.py --assume-previous-yellow --format markdown` mostra cosa cambia quando prima c'era una vecchia gialla.

Audit fonte disponibile:

- `backend_dryrun_staging/official_alert_source_audit.py` salva riga JSONL, raw snapshot, hash e payload contratto;
- primo audit reale 2026-06-26: pagina FVG letta, `raw_sha256=9896e9c639d325d0fe913fdbc2566bc01f1f737760ccf986b16ad23b329b689c`, `alerts_found=0`, `state=inactive_confirmed`;
- il raw snapshot e' in `backend_dryrun_staging/audit_log/raw/`;
- il payload contratto e' in `backend_dryrun_staging/audit_log/payloads/`.
