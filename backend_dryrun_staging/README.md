# Laboratorio dati portabile

Questa cartella contiene strumenti **read-only** e policy pure usati per
verificare i payload meteo prima di collegarli all'interfaccia. Non e' parte del
runtime dell'app e non dipende da repository fratelli, cartelle storiche o
percorsi assoluti del computer.

Gli strumenti non scrivono su Firestore, non inviano notifiche e non attivano
workflow. I comandi che accettano un URL eseguono soltanto richieste `GET`; per
un controllo completamente offline si puo' sempre passare un file JSON.

Eseguire i comandi dalla radice del progetto canonico.

## Verifica del Bollettino

`bulletin_display_payload_audit.py` mostra quali campi del Bollettino sono
presenti, da quale fonte arrivano e se sono sicuri da visualizzare.

```text
python -B backend_dryrun_staging/bulletin_display_payload_audit.py --input payload.json
python -B backend_dryrun_staging/bulletin_display_payload_audit.py --city Pordenone
```

## Policy pure per le allerte

Questi moduli non leggono fonti esterne e non hanno effetti collaterali:

- `official_alert_transition_policy.py`: stato finale e mantenimento di una
  precedente allerta;
- `official_alert_notification_policy.py`: ammissibilita', severita' e chiave
  di deduplicazione di una possibile notifica;
- `official_alert_polling_policy.py`: cadenza consigliata del controllo fonte.

```text
python -B backend_dryrun_staging/official_alert_transition_policy.py --format markdown
python -B backend_dryrun_staging/official_alert_notification_policy.py --format markdown
python -B backend_dryrun_staging/official_alert_polling_policy.py --format markdown
```

La matrice dichiarativa condivisa e' `data_pipeline_case_matrix.json`.
`data_pipeline_status_report.py` puo' riassumere eventuali audit JSONL gia'
presenti in `backend_dryrun_staging/audit_log/`; non acquisisce direttamente
le fonti.

```text
python -B backend_dryrun_staging/data_pipeline_status_report.py --format json
```

## Avvisi meteo locali

La catena locale e' composta da:

1. `local_weather_payload_adapter.py`;
2. `local_weather_notice_detector.py`;
3. `local_weather_notice_normalizer.py`;
4. `local_weather_notification_policy.py`.

Per una prova dichiarativa:

```text
python -B backend_dryrun_staging/local_weather_notice_dryrun.py
```

Per un payload salvato o una lettura `GET` del bootstrap:

```text
python -B backend_dryrun_staging/local_weather_real_payload_dryrun.py --input payload.json
python -B backend_dryrun_staging/local_weather_real_payload_dryrun.py --city Pordenone
```

## Contratto `exports/` per Scopri

`backend_dryrun_staging/exports/` resta il percorso temporaneo condiviso dagli
script di ricerca e revisione della sezione Scopri. La cartella e' ignorata da
Git: i contenuti sono rigenerabili e non vanno copiati nella base pulita.

Tra i producer e consumer attuali ci sono:

- `scripts/import-fvg-daily-history-source.mjs`;
- `scripts/score-fvg-daily-history-candidates.mjs`;
- `scripts/triage-fvg-daily-history-master.mjs`;
- `scripts/build-fvg-daily-history-review-pack.mjs`;
- `scripts/build-fvg-daily-history-expanded-review.mjs`;
- `scripts/build-fvg-daily-history-backlog-audit.mjs`;
- `scripts/build-discover-missing-date-research-queue.mjs`;
- `scripts/export-discover-review-sheet.mjs`.

Il nome e la posizione di `exports/` sono quindi un contratto di lavoro ancora
attivo, mentre i file generati al suo interno sono solo materiale temporaneo.

## Test

La suite della cartella copre le policy e gli adattatori rimasti:

```text
python -m unittest discover -s backend_dryrun_staging -p "test_*.py"
```

Oppure, con le dipendenze di sviluppo installate:

```text
python -m pytest backend_dryrun_staging -q
```

La cartella deve restare portabile: nuovi strumenti devono usare percorsi
relativi alla radice del repository o argomenti espliciti, mai percorsi verso
vecchie copie del progetto.
