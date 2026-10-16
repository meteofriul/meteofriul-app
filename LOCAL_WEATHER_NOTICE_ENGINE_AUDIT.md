# Meteo Friul UI 3.0.0 - Audit motore notifiche meteo locali

Data: 2026-06-27

## Scopo

Questo documento separa tre concetti che non devono confondersi:

- allerte ufficiali Protezione Civile FVG;
- Bollettino OSMER regionale;
- notifiche meteo locali Meteo Friul.

Le notifiche meteo locali sono una feature utile, ma non sono allerte e non devono usare lessico, colori o logica da allerta.

## Stato attuale nel backend sorgente

Nel backend vecchio esiste gia' un flusso locale:

- endpoint protetto: `POST /api/push/local-weather/check`;
- workflow manuale: `.github/workflows/send-local-weather-notices.yml`;
- dispatcher: `dispatch_local_weather_pushes()`;
- generatore per localita': `build_local_weather_notices_for_city(city)`;
- storico deduplica: `push_local_weather_sends`;
- ultimo check diagnostico: `push_local_weather_checks`;
- preferenze: `rain`, `storms`, `wind`, `snow`, `heat`.

Il flusso e' gia' localizzato per citta':

```text
push_devices -> raggruppamento per city -> build_local_weather_notices_for_city(city)
```

Quindi non invia "temporali sui monti" a tutti. Lavora per la localita registrata dal dispositivo.

## Limite attuale

La localizzazione e' reale, ma il motore non e' ancora il contratto definitivo UI 3.0.0.

Il generatore usa:

- `get_real_current_weather(city)`;
- prossime ore `hourly_next_12h`;
- dati stazione/OSMER quando disponibili;
- supporto Open-Meteo per orari, probabilita, codici WMO e alcune soglie.

Questo significa che oggi alcune notifiche nascono da supporto modello/orario, non dal Bollettino OSMER strutturato.

Per UI 3.0.0 va bene come base da auditare, ma non va promosso senza contratto fonte/stato.

## Fenomeni attuali

Il motore riconosce:

- caldo;
- pioggia;
- temporali;
- grandine;
- neve;
- ghiaccio;
- vento forte;
- Bora.

Le notifiche sono deduplicate con firma:

```text
city + kind + category + starts_at hour + reminder_window
```

Questo evita ripetizioni nella stessa finestra, ma consente un promemoria diverso mattina/pomeriggio/sera se serve.

## Soppressione quando c'e' allerta ufficiale

Se una allerta ufficiale copre lo stesso rischio, la notifica locale viene soppressa.

Esempi:

- allerta temporali/idrogeologico sopprime pioggia e temporali;
- allerta vento/Bora sopprime vento;
- allerta neve/ghiaccio sopprime neve e ghiaccio;
- allerta caldo sopprime caldo.

Questa regola e' corretta e va mantenuta.

## Politica anti-rumore

Non basta dire "massimo una push": sarebbe una regola troppo cieca.

La regola corretta e':

1. generare tutti i candidati locali;
2. sopprimere quelli coperti da allerta ufficiale;
3. ordinare per priorita e distanza temporale;
4. notificare solo cio' che e' utile nel momento giusto.

Ordine di priorita candidato:

```text
grandine > temporali > ghiaccio > neve > Bora > vento forte > pioggia > caldo
```

Regole temporali candidate:

- fenomeni entro 4 ore: vince quello con priorita piu alta;
- la finestra entro 4 ore va confrontata come gruppo di candidati, non come scansione solo in avanti;
- se pioggia arriva alle 15:00 e grandine alle 17:00, vince grandine anche se cronologicamente viene dopo;
- a parita di priorita entro la stessa finestra, vince l'evento piu vicino, cioe' quello che arriva prima;
- caldo: viene trattenuto se c'e' un fenomeno piu importante entro 8 ore;
- fenomeni distanti mattina/sera possono produrre notifiche separate;
- caldo resta prudente: non deve coprire o duplicare fenomeni piu utili.

Esempi:

- caldo alle 15:00 e pioggia alle 17:00 -> si notifica pioggia, caldo resta candidato;
- pioggia alle 15:00 e grandine alle 17:00 -> si notifica grandine, pioggia resta candidata;
- grandine alle 18:00 e neve alle 21:00 -> si notifica grandine, neve resta candidata;
- caldo al mattino e temporale la sera -> entrambi possono essere candidati notificabili, se restano in finestre separate;
- allerta ufficiale temporali -> nessuna push locale per temporali/pioggia coerenti.

## Regola di prodotto

Le notifiche meteo locali devono dire:

- cosa succede;
- dove;
- quando, se disponibile;
- da quale fonte/stato arriva.

Esempi ammessi:

- `Pioggia prevista a Pordenone verso le 17:00.`
- `Temporali previsti a Tarvisio verso le 18:00.`
- `Temporali con possibile grandine previsti a Palmanova verso le 18:00.`
- `Neve prevista a Tarvisio verso le 21:00.`
- `Bora prevista a Trieste verso le 21:00.`
- `Caldo previsto oggi a Pordenone.`

Esempi da evitare come push personale:

- `Temporali sui monti`;
- `Caldo in pianura`;
- `Vento sulla costa`;
- `Pioggia probabile domani in regione`.

Queste frasi possono stare nel Bollettino regionale, non in una push locale.

## Lessico vietato

Le notifiche meteo locali non devono usare:

- `Allerta`;
- `gialla`, `arancione`, `rossa`;
- `criticita`;
- `emergenza`;
- `pericolo`;
- toni istituzionali da Protezione Civile.

Se serve una frase prudente:

- usare `prevista`, `possibile`, `da tenere d'occhio`;
- indicare sempre la localita.

## Contratto candidato

```json
{
  "schema_version": "1.0",
  "notice_id": "local-weather:Pordenone:heat:2026-06-27:afternoon",
  "type": "local_weather_notice",
  "kind": "heat",
  "category": "heat",
  "city": "Pordenone",
  "lat": 45.9567,
  "lon": 12.6605,
  "starts_at": "2026-06-27T15:00:00+02:00",
  "reminder_window": "afternoon",
  "severity": 1,
  "body": "Caldo previsto oggi a Pordenone.",
  "source_kind": "local_weather_model",
  "source_authority": "meteo_friul",
  "source_inputs": ["osmer_station", "open_meteo_hourly_support"],
  "official_alert_overlap": false,
  "candidate_can_notify": true,
  "can_notify": true,
  "notification_policy": "selected_by_priority_and_time",
  "dedupe_signature": ""
}
```

## Stati ammessi

| Stato | Significato | Notifica |
| --- | --- | --- |
| `ready` | Fenomeno locale rilevante e localizzato. | Si, se opt-in e non duplicato |
| `suppressed_by_official_alert` | C'e' allerta ufficiale coerente. | No |
| `duplicate` | Gia' notificato nella finestra. | No |
| `no_opt_in_devices` | Nessun device interessato. | No |
| `no_notice` | Nessun fenomeno sopra soglia. | No |
| `source_unavailable` | Dato locale non leggibile. | No |
| `low_confidence` | Fonte incompleta o non localizzabile. | No |

## Differenza da Bollettino

Il Bollettino mostra una lettura regionale/OSMER.

La push locale deve essere localizzata sulla citta dell'utente.

Se non sappiamo localizzare il fenomeno:

- non inviare push;
- al massimo mostrare il fenomeno nel Bollettino come informazione regionale.

## Correzione applicata

La notifica caldo e' stata riallineata al principio di localizzazione e asciugata nel tono:

```text
Caldo previsto oggi a {city}.
```

Prima era diventata generica:

```text
Caldo intenso nelle ore piu' calde.
```

La frase generica e' meno utile per una push personale; la frase con consigli comportamentali e' stata evitata per non rendere la push automatica eccessiva.

## Detector candidati

Prima del normalizzatore c'e' ora un detector puro:

```text
backend_dryrun_staging/local_weather_notice_detector.py
```

Ruolo:

- riceve `city + weather snapshot`;
- legge solo le prossime ore dichiarate nello snapshot;
- applica soglie esplicite per pioggia, temporali, grandine, neve, ghiaccio, vento/Bora e caldo;
- produce notifiche grezze con `kind`, `category`, `severity`, `starts_at`, `event_at`, `threshold`, `evidence`, `source`;
- non importa il backend sorgente;
- non legge rete;
- non scrive Firestore;
- non invia FCM.

Soglie attuali di laboratorio:

| Fenomeno | Soglia |
| --- | --- |
| pioggia | precipitazione/pioggia/rovesci >= 0.3 mm o probabilita >= 60% |
| temporali | `weathercode` 95, 96, 99 |
| grandine | `weathercode` 96, 99 |
| neve | codice neve o `snowfall >= 0.2 mm` |
| ghiaccio | precipitazione gelata o temperatura <= 0 con slot bagnato/probabilita |
| vento | raffiche >= 55 km/h |
| Bora | raffiche >= 55 km/h + area esposta/direzione Bora o flag Bora |
| caldo | temperatura >= 33 C o percepita >= 34 C |

La Bora non e' letta come parola generica: richiede raffica sopra soglia e contesto compatibile.

## Modulo policy puro estratto

La politica `candidati -> notifica finale` e' stata separata nel laboratorio:

```text
backend_dryrun_staging/local_weather_notification_policy.py
```

Caratteristiche:

- non importa il backend sorgente;
- non legge rete;
- non scrive Firestore;
- non invia FCM;
- riceve candidati gia normalizzati;
- restituisce copie annotate con `can_notify` e `notification_policy`.

Il report:

```text
backend_dryrun_staging/local_weather_notice_dryrun.py
```

resta responsabile solo di fixture, osservazione e stampa leggibile.

Catena attuale di laboratorio:

```text
fixture weather -> detector -> normalizzatore -> policy -> report
```

## Payload reali/read-only

Per verificare payload reali o salvati senza collegare live il motore e' stato aggiunto:

```text
backend_dryrun_staging/local_weather_payload_adapter.py
backend_dryrun_staging/local_weather_real_payload_dryrun.py
```

Catena:

```text
saved/read-only payload -> adapter -> detector -> normalizzatore -> policy -> report
```

Regole:

- il payload puo arrivare da file JSON o da URL letta in sola lettura;
- il payload puo essere richiesto anche per lista di citta con `--city`;
- il tool non scrive storage, non chiama Firestore, non invia FCM e non attiva workflow;
- il testo regionale OSMER viene letto come segnale diagnostico;
- i segnali testuali regionali non bastano da soli per una push locale;
- la push locale nasce solo se il detector trova una soglia numerica/localizzata compatibile.

Regola di tracciamento caldo:

- il candidato caldo deve portare `trigger_source`, `trigger_value`, `trigger_unit`;
- se nasce da percepita attuale: `trigger_source=current_feels_like`;
- se nasce da temperatura attuale: `trigger_source=current_temperature`;
- se nasce da picco orario futuro: `trigger_source=hourly_temperature`;
- l'orario evento non deve essere preso dal picco orario se la soglia e' superata dal dato corrente.

Audit multi-citta read-only:

```text
python -B backend_dryrun_staging\local_weather_real_payload_dryrun.py --city Pordenone --city Udine --city Trieste --city Tarvisio --city "Lignano Sabbiadoro"
```

Osservazione:

- payload analizzati: 5;
- candidati locali numerici: 0;
- notificabili in dry-run: 0;
- nessuna delle cinque localita supera le soglie locali numeriche nel payload letto;
- Pordenone mostra temperatura 28 C, percepita 33 C, picco orario 28.7 C: sotto soglia caldo;
- i segnali testuali regionali sono uguali o simili tra le localita e restano diagnostici.

## Normalizzatore candidati

Prima della policy pura c'e' un normalizzatore:

```text
backend_dryrun_staging/local_weather_notice_normalizer.py
```

Ruolo:

- riceve una notifica grezza generata dal backend sorgente;
- verifica `city`, `kind`, `category`, `event_at`, `body`, `source`, `confidence`;
- rifiuta macro-zone come `monti`, `pianura`, `costa`, `FVG`;
- rifiuta parole da allerta: `allerta`, `gialla`, `arancione`, `rossa`, `criticita`, `emergenza`, `pericolo`;
- dichiara `source_inputs` e `confidence`;
- produce `candidate_can_notify`, ma non decide la notifica finale.

Regola copy:

- se la frase contiene gia' la localita, viene preservata;
- se la frase e' una formula nota del backend vecchio ma manca la localita, il normalizzatore inserisce la citta e registra `copy_normalizations=["inserted_city"]`;
- se la frase e' sconosciuta e manca la localita, il candidato viene bloccato con `body_missing_city`.

Esempio:

```text
Pioggia prevista verso le 17:00.
```

diventa:

```text
Pioggia prevista a Pordenone verso le 17:00.
```

con normalizzazione tracciata.

## Prossimo passo tecnico

Prima di collegare questo motore alla UI 3.0.0:

1. trasformare il detector in contratto dati definitivo;
2. decidere quali categorie possono usare supporto Open-Meteo e con quale confidenza;
3. separare definitivamente osservazione, normalizzazione, decisione e invio nel backend reale;
4. impedire invii se la localita e' solo macro-zona;
5. mantenere il workflow manuale/dry-run finche' non c'e' approvazione esplicita.

Completato in laboratorio:

- detector puro `weather snapshot -> raw notice`;
- normalizzatore candidati grezzi -> candidati puliti;
- politica `priorita + distanza temporale` in modulo puro;
- test su grandine dopo pioggia, parita di priorita, caldo bloccato e finestre separate.
