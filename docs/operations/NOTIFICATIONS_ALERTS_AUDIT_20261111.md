# Notifiche e allarmi: audit dell'11 novembre 2026

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
4. Verificare la CI della [PR 46 in bozza](https://github.com/meteofriul/meteofriul-app/pull/46) e osservare
   una corsa ordinaria dopo il deploy del **solo job backend**. Nessuna modifica
   all'app installata e necessaria per la frase; deploy e invio di prova sono
   azioni distinte e non sono stati eseguiti in questo audit.

Verifica locale del ramo: 79 test mirati di sintesi, dati mancanti, FCM e
telemetria PASS (53 subtest); suite backend completa con `lxml 6.1.0`
prescritta: 2.083 test PASS e 2 saltati (1.062 subtest PASS). `compileall`
dei moduli modificati PASS. La CI della PR 46 resta da verificare.
