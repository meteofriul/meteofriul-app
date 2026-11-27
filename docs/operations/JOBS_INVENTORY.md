# Inventario dei job di Meteo Friûl — aggiornato il 27 novembre 2026

Questo è l'indice corrente di **funzioni, dipendenze e pianificazioni**.
Il [verbale del 25 novembre](JOBS_READONLY_AUDIT_20261125.md) contiene
esecuzioni e dati effettivamente osservati; la [mappa dell'app](APP_SYSTEM_MAP_20261125.md)
collega i risultati alle pagine. La mappa originaria usa `main` `61ca8e5e`;
il recupero ICON successivo usa `main` `e4b80906`.
Il cloud può avere risorse o immagini diverse dal codice: qui il cron è quello
letto nel cloud il 25 novembre, con l'aggiunta Eventi riletta il 27 novembre;
non è una promessa ricavata da un template.

## Come funziona la catena

Cloud Scheduler invoca un Cloud Run Job con identità autorizzata; il job legge
una fonte o un catalogo, valida il risultato e può scrivere Storage/Firestore
o inviare tramite FCM. Reader e API servono poi il dato all'app. Logging e
Monitoring osservano esecuzione e metriche. Sono cinque prove diverse:
**configurazione**, **invocazione**, **esito del processo**, **qualità del dato**
e **visualizzazione nell'app/telefono**. Nessuna prova implica automaticamente
la successiva.

I 12 Scheduler osservati il 25 novembre erano `ENABLED` in `europe-west1`.
Il readback del 27 novembre ne conta **13, tutti `ENABLED`**: si è aggiunta
la ripresa condizionale Eventi. L'allerta FVG
invoca il job in `europe-west8`, gli altri target ordinari sono in
`europe-west1`. Il monitor ICON invoca un dispatcher HTTP `/dispatch`; gli
altri 12 invocano `jobs/<nome>:run`. I nomi Scheduler `-refresh` per CAMS e
ICON puntano ai job senza quel suffisso. Gli orari italiani cambiano fra CET e
CEST quando il cron usa UTC; quelli in `Europe/Rome` mantengono l'ora civile.

## Pianificazioni ordinarie

| Scheduler → job | Cron e fuso live | Funzione, risultato e motivo della scelta |
| --- | --- | --- |
| `meteofriul-morning-forecast` → omonimo | `30 7 * * *`, `Europe/Rome` | Sintesi del giorno per dispositivi idonei, con deduplica e FCM. L'ora civile 07:30 serve il mattino locale anche al cambio d'ora. Consuma meteo ICON; un invio accettato non prova la ricezione sul telefono. [entrypoint](../../backend/app/jobs/send_morning_forecast.py), [deploy](../../scripts/deploy-morning-forecast-job.ps1). |
| `meteofriul-evening-forecast` → omonimo | `45 20 * * *`, `Europe/Rome` | Anticipazione del giorno seguente alle 20:45. La copy completa richiede copertura oraria; quella ridotta usa solo temperatura verificata quando altri campi sono incerti. Separata dal mattino per giorno bersaglio, qualità dei dati e orario. [entrypoint](../../backend/app/jobs/send_evening_forecast.py), [decisione 23/11](EVENING_VERIFIED_TEMPERATURE_20261123.md). |
| `meteofriul-local-notice` → omonimo | `0 * * * *`, `Europe/Rome` | Valuta fenomeni locali ogni ora; `no_candidate` può essere corretto, `data_degraded` non è pieno successo. Frequenza oraria per tempestività, con gate di qualità e deduplica. [entrypoint](../../backend/app/jobs/send_local_weather_notices.py), [deploy](../../scripts/deploy-local-notice-job.ps1). |
| `meteofriul-official-alert-sync` → omonimo in west8 | `0 */2 * * *`, `Europe/Rome` | Acquisisce e conserva allerte FVG ufficiali, con possibile push e stato valido limitato. Il job storico omonimo in west1 **non** è il target di questo Scheduler. Due ore più 30 minuti di margine spiegano il TTL di 150 minuti per lo stato senza allerta. [entrypoint](../../backend/app/jobs/sync_official_alerts.py), [regola](../../backend/app/services/official_alerts.py). |
| `meteofriul-national-official-alert-sync` → omonimo | `35 */2 * * *`, `Europe/Rome` | Legge e persiste allerte DPC nazionali; **non invia push**. Lo scarto di 35 minuti dal ciclo FVG e la separazione dall'invio mantengono distinti fonti e controlli. [entrypoint](../../backend/app/jobs/sync_national_official_alerts.py), [deploy](../../scripts/deploy-national-official-alert-job.ps1). |
| `meteofriul-national-official-alert-send` → omonimo | `50 */2 * * *`, `Europe/Rome` | Quindici minuti dopo il sync nazionale seleziona candidati, deduplica e invia FCM. L'invio non è prova che il sync precedente abbia acquisito un'allerta nuova. [entrypoint](../../backend/app/jobs/send_national_official_alerts.py). |
| `meteofriul-icon-refresh` → `meteofriul-icon` | `0 6,7,8,10,18,19,20,22 * * *`, `Etc/UTC` | Produce il bundle ICON FVG su Storage e reader HTTP. Le 06/18 sono slot base; +1, +2 e +4 ore sono recuperi automatici se il ciclo sorgente arriva tardi. Sono otto avvii previsti, non otto nuove pubblicazioni garantite. [piano](../../experiments/weather_autonomy/icon-recovery-plan.json), [deploy del cron](ICON_AUTOMATIC_RECOVERY_DEPLOY_20261031.md). |
| `meteofriul-national-icon-refresh` → `meteofriul-national-icon` | Stessi otto slot UTC | Produce il bundle ICON nazionale separato dal FVG, per letture e funzioni nazionali abilitate. Il suo esito non determina quello FVG. [worker](../../experiments/weather_autonomy/national_cloud_worker.py), [piano](../../experiments/weather_autonomy/icon-recovery-plan.json). |
| `meteofriul-cams-refresh` → `meteofriul-cams` | `0 9,10,11,15,20 * * *`, `Etc/UTC` | Aria, pollini e UV. Tre slot mattutini permettono attesa/recupero della fonte; UV è previsto solo alle 15/20 UTC. Il container può fallire o riuscire con componenti differenti: occorre leggere esiti, continuità e HTTP. [runtime](../../experiments/weather_autonomy/production-runtime.json). |
| `meteofriul-events-refresh` → omonimo | `0 4 * * *`, `Etc/UTC` | Legge fonti Eventi approvate, verifica inventari e schede, scrive `pilot/events/v1/catalog.json`. L'API mostra solo lotti `fresh`/`partial`, non quelli `stale`; il job può scrivere diagnostici pur terminando con errore. UTC colloca la corsa alle 05:00 CET/06:00 CEST. [publisher](../../backend/app/events/pilot_cloud.py), [reader](../../backend/app/events/pilot_http.py). |
| `meteofriul-events-conditional-recovery` → omonimo | `0 6 * * *`, `Etc/UTC` | Due ore dopo il refresh ordinario controlla il catalogo: se TurismoFVG è sana esce senza leggerla o scrivere; se è incompleta per errore temporaneo o scaduta, riprende **solo** quella fonte con checkpoint e gate invariati. Un claim Storage limita la lettura automatica a una per data italiana; un tentativo ancora incompleto salva diagnostica ed esce con errore. Primo slot atteso il 28 novembre alle 06:00 UTC. [rapporto di attivazione](EVENTS_CONDITIONAL_RECOVERY_ACTIVATION_20261127.md). |
| `meteofriul-icon2i-freshness` → dispatcher `/dispatch` → job omonimo | `10,40 * * * *`, `UTC` | Controlla ogni mezz'ora età/identità dei prodotti ICON FVG e nazionale fra Storage e HTTP. È un osservatore distinto dai produttori: un suo successo esecutivo può accompagnare uno stato dati critico. [piano](../../experiments/weather_autonomy/freshness_monitor/resources/deployment-plan.json). |
| `meteofriul-markets-weekly-audit` → omonimo | `0 9 * * 2`, `Europe/Rome` | Audit settimanale Mercati, **presente nel cloud ma assente dal codice di `main`**. La sorgente nel ramo separato `codex/markets-weekly-audit-20261113` confronta fonti e salva un rapporto Firestore quando completo; non scrive l'archivio delle schede né pubblica l'app. La pianificazione del martedì non riattiva il task Windows locale disabilitato. Questo flusso è mappato solo in lettura, perché Mercati è in pausa. |

### Perché produttori e controlli sono separati

- **Meteo previsto, ambiente, bollettino e allerte** hanno fonti, tempi e
  validità differenti. Un unico «job meteo» nasconderebbe quale componente è
  vecchia o non verificata.
- **FVG e nazionale** hanno geografie e contratti diversi. ICON nazionale e
  allerte DPC non sostituiscono automaticamente ICON FVG e OSMER.
- **Sync nazionale e invio** sono separati: una lettura senza candidati non
  diventa un push; l'outbox e la deduplica hanno un loro momento operativo.
- **Eventi** raccoglie siti esterni una volta al giorno, poi l'API serve un
  catalogo verificato senza visitare le fonti per ogni utente. Timeout e
  cambi dei siti possono lasciare lotti `stale` pur conservando diagnostici.
  Il secondo job prova solo TurismoFVG quando necessario e mantiene distinti
  successo del processo e qualità del catalogo.
- **Freschezza ICON** è monitorata fuori dal produttore, per scoprire anche
  processi che terminano bene senza avanzare il ciclo pubblicato.

## Job cloud non ordinari e percorsi assenti

Nel controllo iniziale del 25 novembre erano presenti **15 istanze Cloud Run
Job nelle regioni `europe-west1` e `europe-west8`**: le 12 raggiunte dagli
Scheduler più tre senza target. Alle 19:42 UTC, dopo il recupero nazionale,
è presente anche il job operatore sotto: **16 istanze**, 12 schedulate e
quattro senza Scheduler. Al readback del 27 novembre dopo la nuova ripresa
Eventi risultano **17 istanze**, 13 schedulate e quattro senza Scheduler,
nelle due regioni già inventariate.

| Istanza | Ruolo e limite |
| --- | --- |
| `meteofriul-official-alert-sync` in `europe-west1` | Copia storica distinta dal job FVG schedulato in west8. Presenza non significa attivazione; non va riavviata durante un audit. |
| `meteofriul-event-source-publication-control` | Controllo storico/manuale di un percorso Eventi legacy, non il refresh del catalogo corrente. [codice](../../backend/app/jobs/control_event_source_publication.py). |
| `meteofriul-local-notice-tolerance-qa` | Job di prova, senza Scheduler ordinario. Non è il job pubblico degli avvisi locali. |
| `meteofriul-national-icon-operator` | Job isolato senza Scheduler, creato il 25 novembre per supersedere una fence nazionale `manual_review` priva di checkpoint. Usa la stessa immagine immutabile del job nazionale, un solo task, retry zero, comando `icon_operator_cli.py` e service account dedicata con permessi Storage limitati a tre prefissi ICON tramite cartelle gestite. Il comando predefinito è `--help`; l'unica esecuzione `--execute` ha pubblicato il ciclo `20261125T120000Z`. [Protocollo ed evidenza](WEATHER_ICON_CAMS_RECOVERY_20261125.md). |

`meteofriul-event-source-shadow`, il digest Community e il monitor delle
sintesi per data locale compaiono in codice o piani storici, ma non tra le
15 istanze lette; non si deduce da ciò che esistano in altri progetti.
Le route amministrative che possono avviare una verifica Eventi non sono
Scheduler. ([sync_event_sources.py](../../backend/app/jobs/sync_event_sources.py),
[emit_community_moderation_digest.py](../../backend/app/jobs/emit_community_moderation_digest.py),
[inspect_summary_slots.py](../../backend/app/jobs/inspect_summary_slots.py)).

## Task locali, CI e fallback

Il precedente inventario del checkout Mercati registra
`MeteoFriul-MarketsRefresh-Local` **disabilitato** e
`MeteoFriul-MarketsReminder-Local` non registrato. La lettura Windows del
25 novembre è nel verbale operativo. Il job cloud settimanale sopra è un
percorso distinto, e questo indice non modifica Mercati.

La [CI](../../.github/workflows/ci.yml) è attivata da PR verso `main`, push
su `main` o richiesta manuale: verifica codice, non aggiorna periodicamente
i dati. Il [fallback allerte](../../.github/workflows/sync-official-alerts.yml)
è solo `workflow_dispatch`, senza cron GitHub; non è stato avviato in questo
audit. L'eventuale scheduler locale in `experiments/` è codice di prova, non
prova di un servizio distribuito.

## Monitoraggio e limiti di copertura

Il [catalogo delle policy](../../scripts/cloud-run-job-monitoring-policies.json)
contiene 22 definizioni per 10 nomi di job: fallimenti, assenza di successi,
errori Scheduler e osservazione delle fonti Eventi. Le policy del monitor
ICON e le vecchie prove si controllano separatamente nel cloud; numeri e
canali live sono nel [verbale](JOBS_READONLY_AUDIT_20261125.md). Una policy
di fallimento non rileva necessariamente Scheduler fermo, dati stantii o
utente senza notifica. L'endpoint del pannello owner
[/api/admin/operations](../../backend/app/api/operations_admin.py) legge
riepiloghi mattino/sera e catalogo Eventi, non tutti i 13 Scheduler.

| Famiglia | Policy del catalogo e lacuna residua |
| --- | --- |
| Mattino, sera, avvisi locali | Per ciascuno: corsa fallita, assenza di successi, errore Scheduler. La policy metrica non certifica il contenuto o la ricezione FCM. |
| Allerte FVG | Fallimenti del sync; risultato e validità delle allerte richiedono lettura distinta. |
| DPC nazionale | Fallimenti del **sync**; nessuna policy dedicata al job `national-official-alert-send` individuata. |
| ICON FVG e nazionale | Per ciascuno: fallimenti e assenza di successi; tre policy ulteriori seguono il monitor di freschezza Storage/HTTP. |
| CAMS | Fallimenti del job; la policy non prova tutte le componenti né uno Scheduler mancante. |
| Eventi | Alle due policy precedenti si aggiungono assenza di successo del refresh ordinario per 25 ore, errore dei due Scheduler e fallimento della ripresa condizionale: quattro nuove policy sul canale operativo esistente. L'ultimo successo del job non certifica da solo la freschezza del lotto TurismoFVG servito dall'API. [readback](EVENTS_CONDITIONAL_RECOVERY_ACTIVATION_20261127.md). |
| Mercati cloud | Nessuna policy dedicata letta nel progetto al 25 novembre. Il job è su workstream separato in pausa. |

Il controllo operativo deve leggere per ogni funzione cron/target, esecuzioni
e log in una finestra dichiarata, prodotto Storage/HTTP o contatori FCM,
policy e limiti. Il profilo di audit non avvia job, non riprova fonti, non cambia
cron/policy e non invia notifiche. Le anomalie osservate il 25 novembre sono descritte nel verbale,
non inferite dalla sola presenza di questo inventario.
