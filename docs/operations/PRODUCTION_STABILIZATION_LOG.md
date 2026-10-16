# Registro storico di stabilizzazione UI3

> **Documento storico append-only.** Registra gli esiti osservati nel momento
> indicato e non rappresenta lo stato operativo corrente. Prima di qualsiasi
> intervento su produzione, verificare direttamente Cloudflare, Cloud Run,
> Firebase e gli scheduler attivi.

Gli orari sono espressi in `Europe/Rome`. Una riga può essere marcata `CLEAN`
soltanto quando tutti i controlli previsti sono stati eseguiti; un controllo
non eseguibile deve produrre almeno `WARN`, mai un falso esito pulito. Non
inserire token, segreti, identificativi dei dispositivi, coordinate o altri
dati personali.

| Data e ora | Esito | Smoke live | Automazioni | Anomalie / note |
| --- | --- | --- | --- | --- |
| 2026-08-11 22:51 CEST | WARN | Homepage, healthz, bootstrap Pordenone, radar e frame WMS, Eventi, webcam e segnalazioni operativi senza `5xx` o timeout; allerte HTTP `200` ma stato `unavailable` | GitHub `queued=0`, `in_progress=0`; 4 workflow legacy `disabled_manually`; 2 job Scheduler su 2 `PAUSED`; Hosting e Cloud Run coerenti | Snapshot allerte assente (`firestore_empty`): non equivale a nessuna allerta confermata. Le route diagnostiche legacy non esposte sono `N/A`. Preview `alert-status-check` separato dal live, scadenza 12/08 18:59 UTC. |
| 2026-08-11 23:26 CEST | WARN | Radar UI pubblicato: homepage e asset `200`, health `ok`, bootstrap Pordenone, 2 prodotti radar e frame WMS reale, 12 eventi, 20 webcam e 1 segnalazione; preview e prova browser verdi | PR #2 fusa dopo CI verde; monitor locale ogni 4 ore messo `PAUSED` perché il PC verrà spento; nessuna automazione di produzione riattivata | Allerte ufficiali ancora `official_alerts_unavailable`. Hosting live `e6aaa89ad49ee5b5` conserva `ui3-clean-1530ad0`; mapping hotfix e traffico Cloud Run invariati; `pre-ui3` intatto. |
| 2026-08-17 17:40 CEST | WARN | `meteofriul.app` e API meteo rispondono `200`; smoke Web pulito con meteo, fascia oraria, bollettino ed eventi; reverse Web osservato `200` | Invii ufficiali ancora in `dry_run`; invii meteo locali `off`; backend di test isolato dal traffico Cloud Run principale | `www.meteofriul.app` restituisce `522` invece di reindirizzare al dominio principale; Search Console segnala l'URL `http://www`; favicon piccole non uniformi alla nuova identità; registrazione notifiche Web rifiutata dalla modalità privata Android-only (`403`). Questi punti richiedono verifiche nuove dopo ogni correzione. |
