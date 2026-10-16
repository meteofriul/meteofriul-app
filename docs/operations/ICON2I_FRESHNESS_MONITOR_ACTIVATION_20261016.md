# Monitor ICON-2I: attivazione del 16 ottobre 2026

**Attivo ogni 30 minuti, ai minuti :10 e :40 UTC.** Primo avvio automatico
riuscito e verificato: **07:40 UTC (09:40 Europe/Rome)**. Le acquisizioni
preesistenti non sono state modificate.

**Aggiornamento del 16 ottobre 2026:** email di apertura e chiusura abilitate
esplicitamente sulle tre regole; prova di risoluzione riuscita, con entrambe
le email ricevute in Gmail e confermate dal titolare.

Progetto `meteo-friul`, regione `europe-west1`; branch locale
`codex/icon2i-freshness-monitor`. Questo rapporto aggiorna lo stato operativo
della [consegna locale](ICON2I_FRESHNESS_MONITOR_IMPLEMENTATION.md) e del
[collaudo ridotto](ICON2I_FRESHNESS_MONITOR_CLOUD_COLLAUDO_20261016.md), che
restano registrazioni storiche delle rispettive fasi.

## Risorse operative

- Scheduler `meteofriul-icon2i-freshness`: `10,40 * * * *`, `timeZone=UTC`,
  deadline 30 secondi, retry disattivati. Prossimo orario letto nella verifica
  iniziale di attivazione (dato storico):
  `2026-10-16T08:10:00.711959Z`.
- Servizio privato `meteofriul-icon2i-freshness-dispatch`: 1 CPU, 256 MiB,
  da zero a una istanza, timeout 20 secondi. Riceve l'orario di Scheduler e
  lo passa esplicitamente al job; non usa l'ora di partenza del container.
- Account `icon2i-freshness-scheduler@meteo-friul.iam.gserviceaccount.com`:
  può invocare soltanto il nuovo servizio. Autenticazione OIDC; nessun accesso anonimo.
- Account `icon2i-freshness-dispatch@meteo-friul.iam.gserviceaccount.com`:
  ruolo `icon2iFreshnessJobLaunch`, con `run.jobs.run` e `run.jobs.runWithOverrides`,
  associato soltanto al job del monitor.
- Job del monitor già collaudato: configurazione invariata, 1 CPU, 512 MiB,
  un task, timeout 120 secondi, nessun retry. Le letture meteo e le scritture
  dei due stati restano assegnate al suo account dedicato.

## Primo tentativo e correzione verificata

Il tentativo automatico delle **07:10 UTC** ha raggiunto il servizio ma ha
ricevuto HTTP 400 prima di avviare un job. Scheduler invia nell'header
`X-CloudScheduler-JobName` il nome breve `meteofriul-icon2i-freshness`;
la versione iniziale accettava soltanto il percorso completo della risorsa.

Una chiamata manuale diagnostica alle 07:14 UTC ha reso visibili questi soli
metadati, senza credenziali e senza avviare il monitor. Non viene conteggiata
come avvio automatico riuscito. La correzione accetta solo il nome breve esatto
o il percorso completo atteso; autenticazione IAM, vincoli temporali e rifiuto
di altri job restano invariati. Il timestamp originale, anche con offset di fuso,
viene conservato e normalizzato in UTC per individuare lo slot.

**64 test locali superati** in 14,716 secondi, inclusa regressione con gli header
osservati, nomi di job non ammessi e diagnostica priva di credenziali.
Commit locale: `2b194f6277f9b4ca0d8f83ca2f62af5cde94bf5b`.
In quella fase, nessuna scrittura GitHub, esecuzione di GitHub Actions o
promozione a `main`.

La nuova immagine è applicata solo al servizio di avvio. Il job conserva
l'immagine già collaudata del commit `35b31aef93281880f3b5e8729d5a1061d7304389`:
nei 53 file del pacchetto è cambiato soltanto `freshness_monitor/dispatcher.py`.
Build corretta: `5c061b60-7dd9-441c-8b57-c3b77697b840`. Digest del servizio:
`sha256:d5ac59bfd989b535915bc14eb9cea69188fbee811de7b5d2a24382b14ca8a017`. Digest del job invariato:
`sha256:db0160d88a9397ca7789fe62750158dfb424212feb7e9f8abba6bfc1cbd5db80`.

## Avvio automatico delle 07:40 UTC

Esecuzione: `meteofriul-icon2i-freshness-zcwrn`.

| Passaggio | Valore osservato |
|---|---|
| Orario del tentativo nel log di Scheduler | `2026-10-16T07:40:01.553246Z` |
| Orario programmato letto da Scheduler prima dell'avvio | `2026-10-16T07:40:00.711959Z` |
| Header originale ricevuto e inoltrato | `2026-10-16T00:40:00.711959-07:00` |
| Slot UTC nel servizio, negli argomenti del job e nei due stati | `2026-10-16T07:40:00.000000Z` |
| Ricezione nel servizio | `2026-10-16T07:40:03.340998Z` |
| Creazione esecuzione | `2026-10-16T07:40:04.704412Z` |
| Avvio Cloud Run | `2026-10-16T07:40:07.228537Z` |
| Completamento | `2026-10-16T07:40:49.464012Z` |

Confronto eseguito fra log di Scheduler, log del servizio, argomenti e log del
job, stato FVG e nazionale. L'header originale coincide esattamente con il
`ScheduleTime` letto da Scheduler prima dell'avvio. Il campo del log
`AttemptStarted.scheduledTime` differisce di circa 0,841 secondi: è registrato
separatamente e non sostituisce l'header nella definizione dello slot.
Anche i tempi di ricezione e di esecuzione restano separati. Un solo task riuscito.
Sei punti riletti da Cloud Monitoring, tutti coerenti con i valori e l'istante
`observed_at` salvati nei due stati. Lo slot previsto non viene usato al posto
del momento effettivo di osservazione della metrica.

| Prodotto | Run verificato | Età | Campioni futuri | Stato | Cause |
|---|---|---|---|---|---|
| fvg | 20261016T000000Z | 7.68 h | 65 | regolare | nessuna |
| national | 20261016T000000Z | 7.68 h | 65 | regolare | nessuna |

I campioni sono quelli dichiarati dal manifesto. Il monitor confronta i percorsi
HTTP dell'app con Storage, incluso il resolver nazionale, e verifica i metadati
degli oggetti referenziati; non scarica direttamente tutti i payload previsionali.

## Allarmi e consultazione

Le tre policy sono state abilitate dopo la conferma delle sei metriche:

| Policy | ID | Stato | Email abilitate |
|---|---|---|---|
| ICON2I freshness - fvg | `8522206169610857782` | attiva | apertura e chiusura |
| ICON2I freshness - national | `17358382305278768094` | attiva | apertura e chiusura |
| ICON2I freshness - telemetry | `602951789070907305` | attiva | apertura e chiusura |

Destinazione: `info@meteofriul.it`; il titolare legge queste email in Gmail. Email
all'apertura di un incidente critico e alla sua chiusura; promemoria ogni sei ore
finché l'incidente resta aperto. Attenzione solo nei log. Finestra dati
120 minuti, assenza telemetria 90 minuti; valutazione
ogni 60 secondi. Una chiusura tecnica senza nuova verifica completa non prova
il rientro del problema. Query operative rilette sul motore PromQL Google.

Tre query salvate in Cloud Logging, visibilità privata dell'account operativo:
`icon2i-freshness-attention`, `icon2i-freshness-indeterminate`,
`icon2i-freshness-http`. Retention `_Default` verificata: **30 giorni**, invariata.
L'incidente della precedente prova email si è chiuso alle 05:53:49 UTC;
la policy sintetica resta disabilitata.

## Email di risoluzione: abilitazione e prova riuscita

Il 16 ottobre 2026 è stato impostato esplicitamente
`alertStrategy.notificationPrompts = ["OPENED", "CLOSED"]` sulle tre policy:
FVG alle **07:57:11 UTC**, nazionale alle **07:57:12 UTC**, telemetria alle
**07:57:13 UTC**. Le modifiche hanno riguardato soltanto questo campo, tramite
`updateMask=alertStrategy.notificationPrompts`.

La rilettura delle tre risorse ha confermato il valore salvato, il canale email
`projects/meteo-friul/notificationChannels/11334808831344967323` attivo e i
promemoria invariati a `21600s`. Il confronto prima/dopo, escluso il campo
modificato e il relativo record di modifica, ha confermato invariati gli altri
parametri delle policy.

La prova successiva ha usato la regola separata
**PROVA RISOLUZIONE - monitor ICON2I - 16 ottobre 2026**,
ID `12415396176098492726`, con lo stesso canale email e la stessa configurazione
di notifica. La condizione PromQL leggeva esclusivamente la metrica di collaudo
`custom.googleapis.com/meteofriul/icon2i_collaudo/email_probe`, con
`product="resolution_20261016"`: nessun campione scritto nelle metriche operative.

| Evento del 16 ottobre 2026 | UTC | Europe/Rome |
|---|---|---|
| Timestamp del campione sintetico di errore, valore `1` | 08:01:53 | 10:01:53 |
| Apertura automatica dell'incidente (`OPEN`) | 08:05:19 | 10:05:19 |
| Timestamp del campione sintetico di rientro, valore `0` | 08:05:25 | 10:05:25 |
| Chiusura automatica dell'incidente (`CLOSED`) | 08:11:24 | 10:11:24 |

Incidente verificato: `projects/meteo-friul/alerts/0.odvwaq3dnki6`.
La chiusura è avvenuta dopo il campione regolare, senza chiusura manuale né
modifica della condizione. Fra il timestamp del campione di rientro e la chiusura
sono trascorsi **5 minuti e 59 secondi**. È un tempo osservato in questa prova,
non una garanzia sui tempi futuri o sul momento di consegna dell'email.

Per le policy PromQL, Google documenta una chiusura dopo il maggiore fra
270 secondi e il doppio dell'intervallo di valutazione, calcolato dall'ultima
valutazione che soddisfaceva la condizione. Con valutazione ogni 60 secondi,
il periodo è quindi di 270 secondi, a cui si aggiungono i tempi di acquisizione
delle metriche, valutazione e consegna. Riferimento:
[comportamento delle policy PromQL](https://docs.cloud.google.com/monitoring/alerts/using-promql).

**Esito positivo completo:** il titolare ha confermato in chat la ricezione in
Gmail sia dell'email di apertura sia della successiva email di risoluzione.
Gli orari esatti di arrivo in casella non sono stati misurati.

A conclusione della prova, la regola temporanea è stata **disattivata** e riletta
con `enabled=false`; resta conservata come evidenza del collaudo, insieme
all'incidente chiuso. Il confronto con la copia precedente alla prova ha
confermato identiche le tre policy operative, tutte attive con `OPENED` e
`CLOSED`. Nessuna modifica alle acquisizioni, allo scheduler o ai servizi
esistenti durante questa prova.

La prova verifica il canale email e la notifica di chiusura di una condizione
sintetica; non riproduce tutti i guasti reali dei tre monitor. Resta valida la
regola operativa: una chiusura tecnica, da sola, non certifica il recupero dei
dati senza una nuova verifica completa. Non è stata aggiunta una notifica
nell'app Meteo Friul; l'eventuale notifica sul telefono dipende da Gmail.

## Perimetro e limiti della verifica

Per l'attivazione iniziale, confronto prima/dopo superato: configurazioni e
generazioni dei job e servizi preesistenti invariate, come i dieci scheduler
preesistenti, le policy precedenti
e la policy IAM del progetto. Nessuna modifica alle acquisizioni ICON-2I,
al radar, ai reader, a OSMER o alle allerte ufficiali. Il nuovo servizio resta
privato e i permessi aggiunti sono limitati alle risorse del monitor.

Questo collaudo dimostra un avvio automatico completo e il passaggio dell'orario
reale. Ritardi, duplicati e altri guasti restano coperti dai test locali;
non vengono dichiarati tutti riprodotti nel cloud. Le due settimane di
osservazione delle soglie e dei costi non sono ancora trascorse.

[Evidenze strutturate dell'attivazione iniziale](ICON2I_FRESHNESS_MONITOR_ACTIVATION_20261016.json).
Il JSON collegato precede l'abilitazione esplicita delle email di chiusura e la
nuova prova di risoluzione; questi esiti sono documentati nella sezione aggiunta
al presente rapporto. La prima integrazione di questi esiti ha modificato solo
il Markdown. Il successivo allineamento locale è descritto di seguito.

## Allineamento delle definizioni locali e verifica prima del salvataggio

Il 16 ottobre 2026 anche
[definitions.py](../../experiments/weather_autonomy/freshness_monitor/definitions.py)
e la copia generata
[policies.json](../../experiments/weather_autonomy/freshness_monitor/resources/policies.json)
sono stati allineati a `notificationPrompts = ["OPENED", "CLOSED"]` per tutte e tre
le regole. I modelli restano disabilitati per impostazione predefinita, con canali
da fornire esplicitamente; nessuna attivazione o modifica cloud viene eseguita
dalla generazione. I promemoria configurati restano di sei ore.

I [test di contratto delle policy](../../experiments/weather_autonomy/test_freshness_monitor_policies.py)
verificano apertura e chiusura sia nei modelli senza canali sia nelle tre regole
con canale esplicito, mantenendo il controllo di corrispondenza con il JSON.

Suite locale eseguita dalla directory `experiments/weather_autonomy`:

```text
python -B -m unittest test_freshness_monitor test_freshness_monitor_policies test_freshness_monitor_package test_freshness_monitor_dispatcher -v
```

**Esito: 65 test individuati, 64 superati e 1 saltato, nessun errore, in 17,339
secondi.** Il solo test saltato richiede `PROMTOOL`, non disponibile nell'ambiente
locale individuato; il motore PromQL non è quindi stato nuovamente collaudato in
questa fase. Le query PromQL sono invariate. Sono passati i test locali di
raccolta, stato, notifiche, pacchetto, ritardi, duplicati e inoltro dell'orario
previsto. Diff e collegamenti locali del rapporto verificati.

Branch di consegna: `codex/icon2i-freshness-monitor`. Il salvataggio comprende
questo rapporto, le definizioni, il relativo JSON e i test di contratto, senza
merge su `main`, deploy o modifiche alle acquisizioni. Prima del push sono stati
verificati l'assenza di PR aperte e di esecuzioni CI per il branch, e i trigger dei
workflow: push limitato a `main`, PR con base `main` e avvio manuale. Il semplice
push del branch del monitor non richiede l'avvio di CI.
