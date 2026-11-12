# Notifiche e allarmi: audit dell'11-12 novembre 2026

## Perimetro e prova

Audit in sola lettura del codice, dei log Cloud Run e delle metriche Cloud Monitoring
del progetto `meteo-friul`, confrontati con lo screenshot dell'operatore. Le
letture cloud sono state eseguite l'11 novembre con l'account operativo gia
attivo; non sono stati avviati job, inviati push o modificate risorse. I log
dimostrano l'accettazione da parte di FCM, non l'ora di visualizzazione sul
telefono. Le ore italiane qui sotto sono CET (UTC+1).

| Evidenza del telefono | Riscontro server | Conclusione e limite |
| --- | --- | --- |
| App Android, sintesi alle 07:31 | Job `meteofriul-morning-forecast`: 11 novembre 06:31:58 UTC, `sent=53`, `attempted=53`, `source_failed=0`; ciclo ICON `20261111T000000Z` | Orario coerente. Il log non certifica la consegna al singolo dispositivo. |
| Brave, stessa sintesi alle 08:49 | Unica corsa mattutina ordinaria trovata nella finestra, conclusa alle 07:31:58 | Android e Web sono target distinti. 08:49 e dentro il TTL di tre ore; il punto del ritardo tra FCM e Brave non e attestato. |
| Brave, «Domani a Pordenone» alle 05:53 | Job serale del 10 novembre: 19:46:30 UTC (20:46:30 CET), `sent=53`, `attempted=53`, `source_failed=0`; nessuna corsa serale dell'11 novembre nei log letti | La visualizzazione indicata e circa nove ore dopo l'invio, oltre il TTL configurato di tre ore. Richiede prove lato browser/FCM; non dedurre un nuovo invio. |
| App Android, allerta gialla alle 14:01 | Job ufficiale FVG: 11 novembre 13:01:48 UTC, `push.status=sent`, `push.sent=55`; alle 15:01 UTC `deduplicated`, zero invii | Corrisponde al flusso di allerta ufficiale, indipendente dalle sintesi ICON. |
| Email `ICON2I freshness - telemetry`, 10 novembre 20:19 UTC | Monitor dei cicli 19:10, 19:40 e 20:10 UTC: FVG e nazionale `check_state=0`, `critical_active=0`, `check_completed=1`, scritture metriche `confirmed` | Email operativa, non push dell'app. Il motivo della valutazione `__missing__` al momento dell'allarme non e ancora provato. |

### Origine della frase sulle precipitazioni

Il job mattutino usa `RoutedIconLocalNoticeSource`, che valida puntatore,
manifest e documento ICON e conserva i `null` della sorgente. Nel documento
pubblico di Pordenone del ciclo `20261111T000000Z`, la temperatura delle 08:00
e presente (9,236 °C), mentre `precipitation_mm` e `liquid_rain_mm` sono `null`.
I flag includono `TOT_PREC:positive_within_encoding_resolution` e
`RAIN_GSP:positive_within_encoding_resolution`: un valore non quantificabile
non equivale a zero. Nelle 16 ore 08:00-23:00 del giorno, almeno uno dei due
campi manca in 12 ore; nessuna temperatura oraria manca nel campione.

La modifica del 7 novembre, documentata in
[MORNING_SUMMARY_SOURCE_QUALITY_DEPLOY_20261107.md](MORNING_SUMMARY_SOURCE_QUALITY_DEPLOY_20261107.md),
permetteva di inviare la temperatura ma aggiungeva il testo tecnico «dati sulle
precipitazioni incompleti». Questa e la causa diretta della frase mostrata.
Il ramo `codex/notification-quality-20261111` la elimina: se mancano le
precipitazioni, invia solo temperatura, massima e condizione corrente quando
quest'ultima e verificata. Non formula affermazioni su pioggia o assenza di
pioggia. Blocca la sintesi se la serie della giornata ha meno di dieci ore,
buchi orari, inizia troppo tardi o termina prima delle 18:00, per non chiamare
«massima» il massimo di poche ore. Valori malformati restano bloccanti.
Il job registra ora `quality_limited_groups` nel proprio riepilogo tecnico:
conta i gruppi per cui e stata preparata una sintesi ridotta senza esporre
localita o identificativi personali. Prima del deploy tale contatore non e
presente nei log ordinari.

## Mappa dei percorsi

| Percorso | Origine e pianificazione da repository | Gate prima dell'invio | Destinazione e diagnostica |
| --- | --- | --- | --- |
| Sintesi mattutina | ICON FVG/nazionale -> `RoutedIconLocalNoticeSource` -> `build_morning_forecast_body` -> `send_morning_forecast`; Scheduler 07:30 `Europe/Rome` | Consenso `weather_notices`, dispositivo/versione/localita idonei, dati orari, claim giornaliero nell'outbox | FCM Android o Web; TTL 3 ore, `collapse_key` e tag `mf-morning-forecast`; riepilogo `sent`, errori e `source_trace` nel log del job |
| Anticipazione serale | Stessa fonte, `build_evening_forecast_contents` -> `send_evening_forecast`; 20:45 `Europe/Rome` | Ciclo sorgente fresco, almeno 20 ore del giorno successivo, campi meteo completi, consenso e claim giornaliero | FCM Android/Web; TTL 3 ore, tag `mf-evening-forecast`; log del job |
| Avvisi meteo locali | ICON -> valutazione fenomeni -> job locale ogni ora | Qualita per fenomeno, finestra temporale, localita, consenso, deduplica | FCM su canale `mf_weather_notices_v1`; esito `data_degraded` e audit tecnico quando la qualita non basta |
| Allerta ufficiale FVG | Fonte ufficiale -> snapshot persistente -> `sync_official_alerts`; ore pari :00 `Europe/Rome` | Snapshot utile, allerta azionabile, consenso `official_alerts`, outbox dedicato | FCM su canale `mf_official_alerts_v1`; log separa refresh e push |
| Allerta nazionale DPC | Sync ore pari :35, invio separato :50 `Europe/Rome` | Snapshot verificato, comune manuale Android Play idoneo, opt-in e gate di invio | Outbox e canale nazionali separati; non attribuire a questo flusso l'allerta FVG dello screenshot |
| Monitor tecnico ICON2I | Scheduler :10/:40 UTC -> dispatcher -> job -> sei metriche (tre per FVG/nazionale) | Policy PromQL su stato critico o assenza telemetria per 90 minuti | Email Cloud Monitoring; non e una notifica meteorologica dell'app |

L'app Android registra un token FCM; la Web app registra un Firebase
installation ID mediante service worker. Il backend salva target distinti e
deduplica per target e data, non fra due installazioni sullo stesso telefono.
Per questo la presenza di due notifiche con lo stesso testo nei due canali non
dimostra un doppio invio allo stesso target. `FirebaseCloudMessagingSender`
costruisce payload e TTL separati per Android e Web; il service worker Web usa
Firebase Messaging. Gli stati `sent` significano accettazione FCM, non lettura
o visualizzazione.

## Email ICON2I: cosa prova e cosa resta aperto

La policy live `602951789070907305` e abilitata e usa la query del repository:
`absent_over_time(...[90m])` su sei serie, con valutazione ogni 60 secondi.
L'API Monitoring, riletta per la finestra 18:45-20:20 UTC del 10 novembre,
restituisce tre punti per ciascuna delle sei serie (`fvg` e `national`):
`check_state=0`, `critical_active=0`, `check_completed=1`. Le etichette delle
serie sono `monitored_resource=global`, `project_id=meteo-friul` e il prodotto
atteso. La query PromQL live rivalutata **oggi** all'istante storico delle
20:19 UTC restituisce un vettore vuoto, cioe nessuna assenza. Questa prova
retrospettiva non ricostruisce la visibilita delle metriche nel motore di
alerting alle 20:19; una latenza d'ingestione o valutazione resta un'ipotesi,
non una causa accertata. L'email non dimostra un guasto delle precipitazioni.
L'incidente `0.oev096ptbeqb` della policy indicata nell'email si e aperto il
10 novembre alle 20:19:54 UTC e si e chiuso alle 20:24:05 UTC. La condizione
ha `duration=0s`: Google [documenta](https://docs.cloud.google.com/monitoring/alerts/troubleshooting-alerts)
che una singola valutazione e dati arrivati in ritardo possono produrre
incidenti apparentemente anomali. Questa e una possibilita tecnica, non la
diagnosi definitiva: prima di cambiare la policy servono evidenze sui tempi
di visibilita delle serie e sulle valutazioni.

## Controlli aperti prima di modificare servizi o pubblicare

1. Verificare l'evento di consegna/visualizzazione Web delle 05:53. La sola
   accettazione FCM delle 20:46 non spiega un orario oltre il TTL; valutare una
   protezione di freschezza lato Web solo dopo una riproduzione o telemetria.
2. Correlare l'incidente Cloud Monitoring con i tempi di ingestione delle sei
   serie e con le valutazioni della policy. Non abbassare la soglia o disattivare
   l'allarme sulla base della sola email.
3. Dopo il deploy, leggere `quality_limited_groups` insieme a `source_trace` e
   `source_failed`; il contatore e preparato nel ramo ma non esiste nei log
   storici dell'11 novembre.
4. La CI della [PR 46](https://github.com/meteofriul/meteofriul-app/pull/46)
   e quella del merge su `main` sono PASS; prova owner e deploy sono
   documentati sotto. Resta da osservare la prima corsa ordinaria con il
   nuovo digest. Nessuna modifica all'app installata e necessaria per la frase.

Verifica locale del ramo: 79 test mirati di sintesi, dati mancanti, FCM e
telemetria PASS (53 subtest); suite backend completa con `lxml 6.1.0`
prescritta: 2.083 test PASS e 2 saltati (1.062 subtest PASS). `compileall`
dei moduli modificati PASS. CI della PR 46 sul commit `24edc3df`:
backend, frontend e hosting PASS.

## Preparazione del collaudo owner, sera dell'11 novembre

L'archivio Git del backend del commit `24edc3df`, composto solo da
`Dockerfile`, `requirements.txt` e `app`, ha SHA-256
`0270aa0a7de24a8437f8563f71c1bf5f1138487a8d7a87b76eef8d0ce1a425cc`.
Cloud Build `95598f3e-f157-4b0b-9ffe-ed640f9b54c3` e terminata con
`SUCCESS`; digest immutabile:
`europe-west1-docker.pkg.dev/meteo-friul/meteofriul/backend@sha256:6c2b64c8c52e3f613aea406214b54da955e38330862abcb95c30845ea1aa20c5`.

Il job temporaneo `meteofriul-morning-forecast-qa-20261111` usa quel digest,
ma ha entrambi i modi di invio `off`, gate singolo `true`, zero retry,
nessun identificativo di installazione permanente, nessuno scheduler e zero
esecuzioni al readback. L'installazione owner Android gia usata nel collaudo
del 7 novembre risulta attiva, iscritta alla generazione `play-beta-v1` e
con consenso agli avvisi meteo. L'identificativo non e registrato qui.

## Esito del collaudo owner, 12 novembre

Il proprietario aveva scelto dati correnti, ma ha ripreso il collaudo alle
15:38 CET, quando le ore residue non bastavano per la massima giornaliera.
Ha quindi scelto un replay chiaramente marcato `TEST` dei dati verificati
delle 07:31 del 12 novembre. Il job ordinario delle 07:30 aveva usato il ciclo
`20261112T000000Z`; il replay e stato vincolato allo stesso ciclo.

L'esecuzione QA `meteofriul-morning-forecast-qa-20261111-6hlvh` ha prodotto
`dry_run`, `eligible_devices=1`, `attempted=1`, `sent=0`, `failed=0`
e `source_failed=0`. Il testo anteprima e stato verificato prima dell'invio.
L'esecuzione `meteofriul-morning-forecast-qa-20261111-9l9t8`, con un ID di
collaudo distinto, ha registrato `sent=1`, `attempted=1`, `eligible_devices=1`
e `failed=0` alle 14:48:10 UTC. Il proprietario ha confermato sul proprio
Android la ricezione del titolo `TEST` e l'apertura del Bollettino al tocco.
L'identificativo del dispositivo e il token non sono riportati.

Il ciclo usato aveva precipitazioni complete: questa prova conferma il
percorso di invio, la presentazione e il tap, mentre il ramo di testo per
precipitazioni incomplete resta verificato dai test automatici. Il job QA,
rimasto senza scheduler e con configurazione permanente `off` dopo gli
override delle esecuzioni, e stato eliminato dopo il readback. Il job
ordinario conservava ancora il digest precedente alla fine del collaudo;
merge, CI di `main` e deploy sono stati eseguiti successivamente.

## Merge e deploy del solo job mattutino, 12 novembre

La [PR 46](https://github.com/meteofriul/meteofriul-app/pull/46) e stata
integrata in `main` con merge `b939a1771d90da9a84bd1ff84f968da2c06236a4`.
La CI della PR (`43241690768`) e quella di `main` (`43242575701`)
hanno superato backend, frontend e hosting. L'albero `backend` del merge
coincide con quello del commit sorgente `24edc3df` usato per Cloud Build
(`ddbec623084cec21786e2db4e3d41865d4aacfce`).

Dopo autorizzazione esplicita del proprietario, e stata aggiornata **solo
l'immagine** del job ordinario `meteofriul-morning-forecast`, dal digest
`sha256:50f6eaebc18ba27890cffb540653adcef618c4df97a55118df81dd8a0f7db61b`
al digest candidato
`sha256:6c2b64c8c52e3f613aea406214b54da955e38330862abcb95c30845ea1aa20c5`.
Il readback con `scripts/deploy-morning-forecast-job.ps1 -Mode Audit` restituisce
`ready=true`: ambiente di invio, account runtime, invoker e scheduler
`ENABLED` con `30 7 * * *` in `Europe/Rome` sono invariati. Non e stata
forzata una corsa ordinaria. La prima corsa programmata con il nuovo digest
e attesa il **13 novembre alle 07:30 CET**: verificarne log, `sent`,
`source_failed`, `quality_limited_groups` e testo ricevuto quando
disponibile. Non sono stati modificati AAB, Web, policy o altri job.
