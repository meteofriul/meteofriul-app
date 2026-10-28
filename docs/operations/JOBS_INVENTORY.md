# Inventario dei job e responsabilità

Inventario predisposto il **28 ottobre 2026**, da main
`9f81253e6b1832816e4032930b7b5eb64ebff6ad`, sul ramo
`codex/job-control-inventory`. È un indice delle configurazioni esistenti,
non una seconda configurazione da distribuire. La prima osservazione cloud
è separata nel [verbale del 28 ottobre](JOBS_READONLY_AUDIT_20261028.md).

## Come leggere l'inventario

- **Configurato nel repository**: intenzione espressa da script, manifest o
  template. Non dimostra che il deploy sia avvenuto.
- **Configurato nel cloud**: lettura di job, scheduler e policy, con data nel
  verbale. Non dimostra che una corsa sia riuscita.
- **Esecuzione osservata**: esito e log di una specifica corsa. Un exit code
  positivo non dimostra da solo dati aggiornati o notifiche viste sul telefono.
- **Risultato osservato**: metadati e contenuto pubblicato confrontati con
  ciò che la corsa doveva produrre, nei limiti del campione dichiarato.

`controllo_job` raccoglie queste prove e segnala al coordinatore. `meteo`
interviene su meteo, allerte, notifiche meteorologiche, ICON e CAMS; `eventi`
su acquisizione e catalogo Eventi. Il coordinatore assegna esplicitamente i
file comuni e le modifiche cloud; `build_verifica` verifica le correzioni.
`home` e `scopri` partecipano solo se il problema riguarda un loro consumo o
contenuto. Questo documento non assegna una reperibilità automatica.

## Fonti di configurazione

| Riferimento | Che cosa definisce | Limite |
| --- | --- | --- |
| [Policy dei job](../../scripts/cloud-run-job-monitoring-policies.json) | 18 policy per 9 nomi di job: errori, assenza successi, errori Scheduler e osservazione Eventi | Non contiene tutte le pianificazioni né tutti i job live; soglie e testi si mantengono in quel JSON |
| [Script delle policy](../../scripts/sync-cloud-run-job-monitoring.ps1) | Confronto e applicazione delle policy | Solo la modalità di lettura è pertinente a un audit; nessun `Apply` autorizzato da questo inventario |
| [Mattino](../../scripts/deploy-morning-forecast-job.ps1), [sera](../../scripts/deploy-evening-forecast-job.ps1), [avvisi](../../scripts/deploy-local-notice-job.ps1), [sync nazionale](../../scripts/deploy-national-official-alert-job.ps1) | Nomi, entrypoint, cron, fuso, timeout e retry | Sono script di deploy: si leggono, non si eseguono durante un controllo |
| [Runtime CAMS](../../experiments/weather_autonomy/production-runtime.json) | Pianificazione, slot UV, timeout e budget | Configurazione del checkout, da confrontare con cloud e sorgente del deploy |
| [Piano monitor ICON](../../experiments/weather_autonomy/freshness_monitor/resources/deployment-plan.json) | Job, pianificazione e risorse del monitor | Template con stato `LOCAL_REVIEW_ONLY_NOT_APPLIED`; le vecchie policy disabilitate non dimostrano lo stato live |
| [Ricevuta FVG del 20 ottobre](../../release-history/cloud-operations/20261020-fvg-alert-deploy/configuration-summary.json) | Job/scheduler FVG in `europe-west8`, cron e fuso del deploy | Ricevuta datata, non manifesto aggiornato automaticamente |
| [Architettura Eventi del 13 ottobre](EVENTI_ARCHITETTURA_JOB_E_ALLARMI_2026-10-13.md), [audit fusi del 25 ottobre](SUMMARY_JOBS_DST_AUDIT_20261025.md) | Flussi Eventi e orari effettivamente letti allora, inclusi ICON e dispatcher nazionale | Evidenza storica da riconfermare; non trasferire automaticamente a oggi lo stato dei job legacy |

## Pianificazioni e risultati attesi

Orari italiani indicati per CET (inverno, UTC+1) e CEST (estate, UTC+2).
`Europe/Rome` segue l'ora italiana; `UTC`/`Etc/UTC` mantiene l'ora UTC.
Le corse orarie/notturne con ora italiana richiedono attenzione al cambio d'ora:
non si presume che ogni giornata abbia esattamente 24 ore.

| Job/funzione | Pianificazione di riferimento e fonte | Risultato atteso da confrontare con i log/dati | Monitoraggio previsto nel repository | Responsabile intervento |
| --- | --- | --- | --- | --- |
| `meteofriul-morning-forecast` | `30 7 * * *`, `Europe/Rome`: 07:30 italiane, script mattino | Sintesi del giorno; riepilogo con idonei, tentativi, accettazioni FCM, errori e deduplica | `morning-forecast-failures`, `-last-success`, `-scheduler-failures` | `meteo` |
| `meteofriul-evening-forecast` | `45 20 * * *`, `Europe/Rome`: 20:45 italiane, script sera | Anticipazione del giorno successivo; freschezza/copertura ICON e contatori di invio | Tre policy `evening-forecast-*` analoghe al mattino | `meteo` |
| `meteofriul-local-notice` | `0 * * * *`, `Europe/Rome`: ogni ora, script avvisi | Valutazione tempestiva per fenomeno e risultato invio; `no_candidate` può essere corretto, `data_degraded` resta esplicito | Tre policy `local-notice-*`; il risultato applicativo resta distinto dall'exit code | `meteo` |
| `meteofriul-official-alert-sync` | `0 */2 * * *`, `Europe/Rome`: ore pari :00, ricevuta FVG del 20 ottobre | Acquisizione/persistenza allerte FVG e risultato push. Assenza di allerta attiva è un risultato legittimo | `official-alert-failures` | `meteo` |
| `meteofriul-national-official-alert-sync` | `35 */2 * * *`, `Europe/Rome`: ore pari :35, script nazionale | Acquisizione e persistenza DPC, `stored`/`already_current` o rinvio motivato. Il sync non invia push | `national-official-alert-failures` | `meteo` |
| `meteofriul-national-official-alert-send` (`app.jobs.send_national_official_alerts`) | `50 */2 * * *`, `Europe/Rome`: ore pari :50, audit del 25 ottobre e lettura cloud del 28 ottobre | Candidati, deduplica e contatori invio; separato dall'acquisizione nazionale | Non elencato fra i 9 job del catalogo policy: copertura effettiva nel verbale corrente | `meteo` |
| `meteofriul-icon` | `0 6,18 * * *`, `Etc/UTC`, audit del 25 ottobre: 07/19 CET, 08/20 CEST | Pubblicazione atomica FVG: manifest, documenti e sidecar coerenti, nuova corsa leggibile via HTTP | `icon-fvg-failures`, `icon-fvg-last-success`; monitor freschezza separato | `meteo` |
| `meteofriul-national-icon` | `0 6,18 * * *`, `Etc/UTC`, audit del 25 ottobre: 07/19 CET, 08/20 CEST | Bundle nazionale, puntatore `weather/v2/icon2i/pilot.json` e lettura HTTP coerenti | `icon-national-failures`, `icon-national-last-success`; monitor freschezza separato | `meteo` |
| `meteofriul-cams` | `0 9,10,11,15,20 * * *`, `Etc/UTC`, runtime CAMS: 10/11/12/16/21 CET, 11/12/13/17/22 CEST; UV negli slot 15/20 UTC | Aria, pollini e UV con esiti separati; famiglia/corsa, validità e continuità Storage/HTTP. Non confondere successo del container con disponibilità di tutte le componenti | `cams-failures`; controlli di continuità nei dati e nel servizio | `meteo` |
| `meteofriul-events-refresh` | `0 4 * * *`, `Etc/UTC`, audit Eventi/fusi: 05 CET, 06 CEST | `pilot/events/v1/catalog.json` pubblicato solo dopo i gate; data catalogo, fonti, schede e candidati in revisione | `events-failures` e `events-candidate-watch`: errore esecutivo e revisione editoriale sono segnali diversi | `eventi` |
| `meteofriul-icon2i-freshness` | `10,40 * * * *`, `UTC`, template monitor: ogni mezz'ora ai minuti :10/:40 | Confronto FVG/nazionale Storage/HTTP, età della corsa, stato e metriche del monitor | Template distinti FVG, nazionale e telemetria; leggere policy live e risultati, non il solo template | `meteo` |

Le soglie numeriche restano nella configurazione collegata: non devono essere
modificate per far risultare positivo un controllo. La prima verifica elenca
anche job aggiuntivi, duplicati regionali, QA e schedulazioni inattive rilevati
nel cloud; non sono nuovi servizi da attivare.

## Percorsi da non confondere con i job ordinari

La lettura cloud del **28 ottobre** ha trovato **14 istanze Cloud Run Job**
(13 nomi, perché il sync FVG esiste in due regioni) e **11 scheduler ENABLED**.
Tutti gli scheduler letti sono in `europe-west1`; quello FVG invoca il job in
`europe-west8`. Gli altri job ordinari sono in `europe-west1`.

Gli scheduler hanno lo stesso nome del job, salvo `meteofriul-cams-refresh`,
`meteofriul-icon-refresh` e `meteofriul-national-icon-refresh`, che puntano ai
rispettivi job senza suffisso `-refresh`. Lo scheduler
`meteofriul-icon2i-freshness` chiama il servizio dispatcher `/dispatch`,
non direttamente l'API RunJob. Gli 11 cron/fusi della tabella sono stati
riconfermati dalla lettura cloud; non sono stati modificati.

Le tre istanze aggiuntive senza target fra gli scheduler letti sono
`meteofriul-event-source-publication-control`,
`meteofriul-local-notice-tolerance-qa` e il vecchio
`meteofriul-official-alert-sync` in `europe-west1`. Il job shadow non compare
nell'inventario letto. Nessun nuovo job dedicato al monitor delle sintesi per
data locale è stato individuato; ciò non costituisce un'ispezione del contenuto
di ogni immagine distribuita. Dettagli e ultime corse nel verbale.

| Percorso | Ruolo e stato da verificare | Responsabile |
| --- | --- | --- |
| `meteofriul-events` e servizi HTTP meteo | Lettori/API dei risultati, non acquisizioni pianificate. Una risposta HTTP 200 non prova un catalogo o una previsione aggiornati | `eventi` / `meteo` |
| `meteofriul-event-source-shadow` | Percorso legacy `app.jobs.sync_event_sources`; cron storici non dimostrano un job oggi attivo | `eventi` |
| `meteofriul-event-source-publication-control` | Controllo di pubblicazione `app.jobs.control_event_source_publication`, storico/manuale; non sostituisce il refresh corrente | `eventi` |
| Varianti QA, duplicati regionali e scheduler sospesi | Conservare identità, regione, stato e ultima corsa nel verbale; non cancellare né riattivare come parte dell'audit | Coordinatore e specialista della funzione |
| [Monitor sintesi per data locale](SUMMARY_LOCAL_DATE_MONITOR_20261025.md) | Codice integrato, collegamento cloud documentato non attivo; eventuale attivazione è un intervento separato. Le policy esistenti non vengono disabilitate | `meteo`, con `build_verifica` |
| Digest Community | Codice dormiente; nessuna attivazione implicita. Identità/privacy/moderazione richiedono assegnazione specifica | Coordinatore |
| [Fallback GitHub allerte](../../.github/workflows/sync-official-alerts.yml) | Solo `workflow_dispatch`, vincoli su main e variabile di abilitazione; nessun cron GitHub. Non avviarlo come prova | `meteo`, con `build_verifica` |
| [CI](../../.github/workflows/ci.yml) | Test/build su push a main, PR verso main e richiesta manuale. Non aggiorna periodicamente i dati dell'app | `build_verifica` |

Landing e pannello di gestione sono progetti esterni. Questo inventario copre
la configurazione dell'app e le risorse del progetto cloud effettivamente lette;
non certifica loro job, schedulatori in altri account o installazioni esterne.

## Procedura di controllo

1. Identificare commit, account/progetto previsti e istante UTC/Europe/Rome.
   Leggere le configurazioni senza cambiare il progetto globale della CLI.
2. Elencare job e scheduler nelle regioni pertinenti. Distinguere nome, target,
   fuso e stato; confrontare il cloud con le fonti di questo indice.
3. Leggere una finestra limitata di esecuzioni/log e le policy esistenti;
   dichiarare limiti, campionamento e accessi mancanti. Usare riepiloghi
   strutturati senza dati di utenti o destinatari.
4. Verificare gli output disponibili: identità/data del catalogo o della corsa,
   validità, completezza nel campione, eventuali risultati degradati.
5. Riportare `VERIFICATO`, `ANOMALIA` e `NON VERIFICABILE` per il singolo
   aspetto, senza trasformare una verifica parziale in un giudizio generale.
   Collegare query, finestra, esecuzione ed evidenza sanificata.

Il controllo termina con una segnalazione al coordinatore. Nessun retry,
invocazione Scheduler, modifica delle policy, pubblicazione, notifica di prova
o controllo periodico è autorizzato da questa procedura. Un allarme configurato
non dimostra la ricezione di un'email; FCM accettato non dimostra la
visualizzazione della notifica sul telefono.
