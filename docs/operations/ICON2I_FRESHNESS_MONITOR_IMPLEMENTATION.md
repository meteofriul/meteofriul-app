# Monitor ICON-2I: implementazione e consegna locale

> Aggiornamento operativo del 16 ottobre 2026: monitor attivo e primo avvio
> automatico verificato. Stato corrente ed esiti nel
> [rapporto di attivazione](ICON2I_FRESHNESS_MONITOR_ACTIVATION_20261016.md).
> Le sezioni seguenti descrivono la consegna locale precedente.

Base locale: `1d598572194b173675d6dbd35d121a2399f615a5`, branch
`codex/icon2i-freshness-monitor`. I quattro file del riferimento `696cf0f5`
sono invariati. Il controllo di pulizia del workspace passa.

Specifica di riferimento: revisione del 15 ottobre 2026, SHA-256
`8ab2def8d7011fc8823993e02584f9847852b1f9ee9354d7ea4b8f0d996b3bb4`.
Perimetro: Ã‚Â§0, parte A e Ã‚Â§6.1. Parti B/C/D escluse.
Il documento originale in Downloads non ÃƒÂ¨ stato modificato.

## Piano seguito

1. Lettura e verifica di puntatori, resolver, manifesti e indice nazionale.
2. Stato condizionale per prodotto/slot, metriche idempotenti e log strutturati.
3. Adattatori cloud protetti e definizioni locali di policy/query.
4. Collaudi offline con orologio e servizi simulati, piÃƒÂ¹ il motore PromQL reale.
5. Consegna locale; nessuna attivazione, operazione cloud, GitHub o CI.

## Contenuto

Il nuovo package ÃƒÂ¨ [freshness_monitor](../../experiments/weather_autonomy/freshness_monitor/).
Non cambia reader, worker, frontend, valori meteo, scheduler esistenti o l'adattatore
Storage nazionale. Non modifica OSMER o allerte ufficiali.

| File | ResponsabilitÃƒÂ  |
|---|---|
| `core.py` | Soglie, UTC, sei slot, stato indeterminato, critico conservato e avanzamento |
| `contracts.py` | Riutilizzo dei validatori esistenti, confronto semantico, resolver Roma/RM |
| `collect.py` | Fotografie coerenti Storage/HTTP, budget, retry limitati e diagnosi separata |
| `runner.py` | CAS dello stato, deduplica, registrazione degli invii e riconciliazione |
| `google.py` | REST per letture meteo, soli due oggetti di stato e sei serie Monitoring |
| `__main__.py` | Entrypoint Cloud Run protetto, identitÃƒÂ  dell'esecuzione e slot |
| `definitions.py` | Definizioni locali di metriche, policy, query e piano di configurazione |
| `resources/*.json` | Copie per revisione, non applicate ai servizi |

Sono inclusi un [Dockerfile separato](../../experiments/weather_autonomy/Dockerfile.freshness-monitor)
e quattro file di test. Il comando predefinito dell'immagine stampa soltanto `--help`;
`ICON2I_MONITOR_ALLOW_CLOUD=0` ÃƒÂ¨ il valore predefinito. Non sono state costruite
o pubblicate immagini. ÃƒË† stata verificata localmente la chiusura dei file COPY,
importando il pacchetto isolato e caricando i cataloghi vincolati da 215/7.894 comuni.

## Comportamento implementato

- Soglie concordate: etÃƒÂ  Ã¢â€°Â¥19/Ã¢â€°Â¥20 ore; pubblicazione nuova >13/>14 ore;
  copertura dichiarata <24/<12 campioni futuri. Campione esattamente all'ora
  corrente incluso; cambio ora legale senza modifica di slot o soglie.
- FVG: GET di `latest.json` con `Cache-Control: max-age=0`, equivalente alla
  lettura senza corpo in cache del client Fetch `no-cache`.
- Nazionale: GET di `pilot.json` e `resolve.json?city=Roma&province=RM` con
  `Cache-Control: no-cache` e `Pragma: no-cache`. Confronto del comune `058091`,
  del run, dei descrittori e dell'associazione al blocco nell'indice.
- La generazione Storage viene riletta dopo gli endpoint HTTP e dopo una
  diagnosi. Al massimo due fotografie; un cambiamento persistente produce
  indeterminato, senza confondere due run.
- Richieste ordinarie e diagnostiche restano distinte nei log. Una diagnosi
  aggiornata non cancella un risultato ordinario vecchio. Un errore giÃƒÂ 
  dimostrato rimane critico anche se una lettura successiva esaurisce il budget.
- Nessun download diretto dei blocchi previsionali o dei payload comunali.
  Il resolver puÃƒÂ² effettuare una lettura interna di blocco: questo costo resta.
- Grazia iniziale configurabile **60 s per prodotto**: 30 s del reader verificati
  piÃƒÂ¹ 30 s di margine iniziale. Testati i confini 59/60/61 s. ÃƒË† un parametro
  iniziale, non una latenza massima misurata; confermarlo nella fase cloud.
- Budget applicativo 110 s, dentro il timeout previsto di 120 s. Raccolta entro
  75 s complessivi, massimo 35 s per prodotto; entrambi vengono osservati prima
  degli invii delle metriche. Chiamate limitate a 5 s e un solo retry transitorio.
  Nessun aumento dei timeout per mascherare errori.

## Stato e metriche

Stato in due soli oggetti, nel bucket esistente di stato:

- `monitoring/icon2i-freshness/v1/fvg.json`;
- `monitoring/icon2i-freshness/v1/national.json`.

Ogni scrittura richiede la generazione precedente (creazione: `ifGenerationMatch=0`).
Un risultato duplicato recupera la valutazione giÃƒÂ  salvata; uno slot piÃƒÂ¹ vecchio
non puÃƒÂ² sostituire quello piÃƒÂ¹ recente. Il timestamp dei tre punti ÃƒÂ¨ quello della
valutazione originale, mai l'ora di un reinvio.

Sono previste tre metriche GAUGE/INT64, risorsa `global`, unica label `product`:
`check_state`, `critical_active`, `check_completed`. Totale: sei serie.
Le cause, i run e le esecuzioni non diventano label.

Ogni punto passa da `ready` a `prepared` con CAS prima dell'invio. Dopo una
risposta certa si registra `confirmed`; un rifiuto esplicito ÃƒÂ¨ `rejected`.
Un esito incerto rimane `prepared` e viene confrontato con Monitoring prima
di decidere: punto identico Ã¢â€ â€™ confermato, timestamp piÃƒÂ¹ recente Ã¢â€ â€™ superato,
stesso timestamp con valore diverso Ã¢â€ â€™ conflitto. Non si reinviano punti confermati.

**Limite esplicito della riconciliazione:** l'assenza di un punto non prova che una
richiesta preparata non sia ancora in volo o in ritardo di visibilitÃƒÂ . In quel caso
non si reinvia alla cieca. Gli altri punti ancora non tentati possono procedere;
lo slot successivo produce una nuova valutazione. Un rifiuto esplicito puÃƒÂ² essere
ritentato al massimo una volta nello stesso slot, dopo riconciliazione. Restano
il limite di assenza a 90 minuti e il caso di un critico breve rimasto solo nei log.

Il riepilogo strutturato viene emesso **prima** degli invii e di nuovo al termine:
`phase=evaluation_committed` / `telemetry_result`. Entrambe le righe mantengono lo
stesso slot; non vanno contate come due controlli. Un guasto alle metriche non
cancella dai log l'evidenza critica. Un errore dello stato non produce uno zero
o un heartbeat sostitutivo.

La pubblicazione ÃƒÂ¨ sconosciuta al bootstrap e dichiarata tale. Un cambio di run
verificato registra il `timeCreated` della generazione osservata; controlli dello
stesso run e riscritture successive non lo fanno avanzare. La freschezza del run
continua a essere misurabile anche quando l'istante di prima pubblicazione non ÃƒÂ¨
riconciliabile. Un run retrocesso produce un critico e conserva l'ultimo verificato.

## Orario previsto: passaggio esplicito completato in locale

Percorso previsto: **Cloud Scheduler â†’ servizio privato di inoltro â†’ Job del monitor**.
Il servizio `meteofriul-icon2i-freshness-dispatch` riceve solo `POST /dispatch`;
legge `X-CloudScheduler-JobName` e `X-CloudScheduler-ScheduleTime`, e avvia soltanto
`meteofriul-icon2i-freshness` tramite `jobs.run` con `containerOverrides.args`.
Il corpo della richiesta non puÃ² indicare un altro job, uno slot o parametri arbitrari.

Il Job riceve `--scheduled-slot` e `--scheduler-schedule-time`. Controlla che
corrispondano **prima di ottenere le credenziali o leggere/scrivere dati**.
La modalitÃ  `--use-execution-slot` e la deduzione dalla `createTime` sono eliminate.
Il recupero manuale autorizzato resta possibile con uno slot esplicito, registrato
come `manual_explicit`, distinto da `scheduler_header`.

Il timestamp originale di Scheduler Ã¨ conservato nei log di inoltro e del Job.
Google lo documenta come stabile fra i tentativi della stessa invocazione.
Il cron rimane `10,40 * * * *` in UTC. Gli orari di ricezione, creazione e avvio
non determinano mai l'identitÃ  del controllo.

**Normalizzazione della sorgente:** il timestamp RFC 3339 puÃ² avere offset e
frazioni di secondo. Si converte in UTC e si associa al precedente :10/:40 solo
se lo scarto della sorgente Ã¨ fra 0 e **120 secondi inclusi**. Questa Ã¨ una scelta
esplicita del contratto, per ammettere i secondi presenti nei timestamp Scheduler;
non Ã¨ una tolleranza applicata all'ora di arrivo. Nei log esaminati il 16 ottobre
il campo `scheduledTime` degli avvii presenta secondi, ma ciÃ² non certifica il
valore dell'header del futuro servizio: il collaudo cloud dovrÃ  registrarli e
confrontarli. Fuori dal limite, timestamp futuro, header assente/duplicato o
scheduler diverso: rifiuto, senza inventare lo slot corrente. Il timestamp
originale resta disponibile, anche dopo la normalizzazione.

| Caso | Comportamento |
|---|---|
| Controllo :10 ricevuto a :11 o :39 | Conserva lo slot :10 |
| Controllo :10 ricevuto a :40 o piÃ¹ tardi | HTTP 204, esito scaduto nei log, nessun avvio nÃ© heartbeat |
| Avvio accettato a :39:59, container partito a :40 | Job rifiuta lo slot prima delle credenziali |
| Scadenza durante raccolta o riconciliazione | Nessuna nuova valutazione/invio iniziato dopo la scadenza |
| Duplicato nello stesso intervallo | Stesso slot; CAS e outbox riutilizzano il risultato e i punti giÃ  confermati |
| Risposta di avvio perduta | Esito incerto, nessun retry interno; un duplicato mantiene lo stesso slot |
| Run/controllo piÃ¹ recente giÃ  registrato | Nessun arretramento dello stato |

Un invio giÃ  in volo puÃ² terminare dopo il confine: conserva il timestamp originale
e non viene reinterpretato come controllo dello slot successivo. Un HTTP 202
significa soltanto che Cloud Run ha accettato l'avvio, non che il monitor sia sano
o che le metriche siano arrivate. Il servizio di inoltro non scrive heartbeat.

**Duplicati:** l'API `jobs.run` non fornisce qui un'identitÃ  di richiesta riutilizzata
per evitare un secondo avvio. Due consegne possono quindi creare due esecuzioni;
i controlli giÃ  presenti su stato e metriche impediscono che diventino due
osservazioni dello stesso slot. Non si introduce un terzo oggetto di stato o un
nuovo lease. Resta possibile lavoro duplicato prima del primo CAS; il costo va
misurato, senza dichiarare garantita un'esecuzione unica.

**Autenticazione prevista:** l'adattatore deve restare privato, con controllo IAM
Cloud Run attivo e il solo account Scheduler dedicato autorizzato a invocarlo.
Gli header Scheduler non sono credenziali e da soli sono falsificabili. Il suo
account runtime avrÃ  `run.jobs.run` e `run.jobs.runWithOverrides` soltanto sul Job
del monitor, senza accessi Storage o Monitoring. Il Job mantiene il proprio
account con letture meteo e scritture limitate allo stato/metriche; non gli serve
piÃ¹ `run.executions.get`. Il chiamante Scheduler usa OIDC con audience uguale
all'URL base del servizio, mentre l'inoltro verso l'API Google usa OAuth.
Queste identitÃ  e assegnazioni sono soltanto previste, non create o modificate.

Si riusa la stessa immagine, con `ENTRYPOINT ["python", "-m", "freshness_monitor"]`
e `CMD ["--help"]`. Per il servizio si cambia esplicitamente il comando in
`python -m freshness_monitor.dispatcher`, argomenti `--serve --cloud`.
Entrambi richiedono opt-in e identitÃ  progetto/Job/servizio corretta; import e
`--help` non attivano credenziali o server. Uvicorn 0.46.0 Ã¨ incluso nell'immagine;
nessuna immagine Ã¨ stata costruita in questa fase.

L'adattatore introduce **un piccolo servizio Cloud Run aggiuntivo**, a richieste,
con zero istanze minime, massimo una istanza, 1 CPU / 256 MiB, timeout 20 s.
Il suo costo e il tempo di avvio si aggiungono alla stima precedente del solo Job.
Scheduler mantiene deadline 30 s e retry zero. Il piano Ã¨ locale e disabilitato.

Riferimenti: [header Scheduler](https://docs.cloud.google.com/scheduler/docs/reference/rest/v1/projects.locations.jobs#HttpTarget),
[override del Job](https://docs.cloud.google.com/run/docs/reference/rest/v2/projects.locations.jobs/run),
[autenticazione Cloud Run](https://docs.cloud.google.com/run/docs/authenticating/service-to-service).

## Policy e query pronte per revisione

[Policy](../../experiments/weather_autonomy/freshness_monitor/resources/policies.json):
due condizioni dati con `last_over_time[120m]`, una per prodotto; una condizione
di telemetria con `absent_over_time[90m]` su tutte le sei serie, ridotta a una
sola serie risultante. Valutazione 60 s, durata aggiuntiva zero.
Tutte le policy sono **disabilitate**, con canali non associati.

`policies(notification_channels=...)` prepara anche i promemoria a 21.600 s
per i canali forniti; non li salva. La chiusura tecnica resta distinta dal rientro:
servono una verifica completa successiva al critico, `critical_active=0` e
conferma di tutte le metriche. Nessun nuovo sistema di invio email ÃƒÂ¨ introdotto.

[Query di log](../../experiments/weather_autonomy/freshness_monitor/resources/logging-queries.json):
attenzione per etÃƒÂ /copertura, indeterminati negli ultimi sei slot e confronti
HTTP di puntatore/resolver. I record sono JSON su stdout per Cloud Logging,
con nomi interrogabili in `jsonPayload`. Nessuna dashboard aggiunta.

[Piano di configurazione](../../experiments/weather_autonomy/freshness_monitor/resources/deployment-plan.json):
regione `europe-west1`, cron `10,40 * * * *` / UTC, 1 vCPU / 512 MiB,
un task, retry zero. ÃƒË† un documento di revisione, non uno script di applicazione.

## Eseguire i test locali

Dalla radice del branch:

```powershell
Set-Location experiments/weather_autonomy
python -B -m unittest test_freshness_monitor test_freshness_monitor_policies test_freshness_monitor_package test_freshness_monitor_dispatcher -v
```

Per includere le prove del motore PromQL impostare `PROMTOOL` al percorso di
un eseguibile locale verificato. Senza questa variabile il relativo test segnala
esplicitamente lo skip; non equivale a una verifica delle policy.

Nella verifica di questa consegna ÃƒÂ¨ stato usato Prometheus/promtool **3.5.0**
scaricato dalla [release ufficiale](https://github.com/prometheus/prometheus/releases/tag/v3.5.0).
SHA-256 dell'archivio Windows amd64, verificato contro `sha256sums.txt`:
`b3c2607d1e80a277735fd3cde86432eb1b6843897cb82fb04fbf4c7ffb1d1c36`.

I test costruiscono dati sintetici usando i builder dei contratti esistenti,
senza scaricare dati meteo. I log di acquisizione/pubblicazione eventualmente
stampati dai test preesistenti riguardano le loro simulazioni.

## Criteri di accettazione e prove ancora distinte

| Gruppo della specifica | Verifica locale |
|---|---|
| Run invariato, vecchio ripubblicato, soglie 19/20 e 13/14 | Test con orologio controllato |
| Copertura 12/24, campione all'ora corrente, ora legale | Test deterministici UTC |
| Puntatore/manifesto/indice/resolver invalidi o mancanti | Dati sintetici e trasporti simulati |
| HTTP piÃƒÂ¹ vecchio/piÃƒÂ¹ nuovo, cambio di generazione, diagnosi | Reader simulati; prima evidenza conservata |
| Due consecutivi, tre su sei, slot mancanti | Transizioni di stato pure |
| Duplicati concorrenti, CAS perso, invii parziali/incerti | Stato e Monitoring simulati |
| Critico conservato dopo indeterminato; ripresa sana | Test di stato e telemetria |
| Sei serie, unica label, tre condizioni stabili | Definizioni e PromQL reale |
| Monitor fermo: telemetria prima della perdita del critico | Promtool: 89/90/119/120 minuti |
| Nuovo zero: rientro senza aspettare 120 minuti | Promtool: 29/30/31 minuti |
| Una serie assente nonostante heartbeat, bootstrap vuoto | Promtool |
| JSON interrogabile, query versionate e pacchetto importabile | Test locali; riscontro Cloud Logging ancora da fare |

**Non eseguiti e necessari nella futura fase autorizzata:**

- build dell'immagine e verifica della revisione effettivamente installata;
- IAM effettivo: dati meteo solo get/list, scritture ristrette ai due oggetti di
  stato, Monitoring create/list, piÃ¹ identitÃ  private di Scheduler e adattatore descritte sopra. Sovrascrivere
  un oggetto GCS richiede anche `storage.objects.delete`: limitarlo ai soli oggetti
  di stato; il codice non offre cancellazione meteo;
- riscontro cloud degli header Scheduler e del passaggio esplicito dello slot, rifiuto
  degli invocatori non autorizzati, verifica di grazia/tempo di esecuzione;
- creazione dei descrittori e policy, canali email/mobile, consegna reale,
  chiusura tecnica e rientro; il test PromQL non certifica il servizio Google;
- salvataggio delle tre query, ricezione in `jsonPayload`, retention effettiva
  per 14 giorni piÃƒÂ¹ il margine di revisione;
- costi e due settimane di osservazione. Il protocollo di conferma per punto
  aumenta le operazioni sullo stato rispetto a una semplice scrittura unica:
  la stima Storage iniziale non ÃƒÂ¨ un tetto giÃƒÂ  verificato;
- sostituzione delle vecchie policy solo dopo il collaudo autorizzato.

Fonti tecniche: [PromQL in Cloud Monitoring](https://docs.cloud.google.com/monitoring/promql),
[condizioni PromQL](https://docs.cloud.google.com/monitoring/api/ref_v3/rest/v3/projects.alertPolicies#PrometheusQueryLanguageCondition).

## Esito della prima consegna locale (prima di questo completamento)

Registrato il **2026-10-15 alle 22:25 UTC**:

- **42 test del monitor: tutti superati**, inclusi PromQL reale e pacchetto isolato
  (ultima esecuzione: 11,478 s; nessuno skip).
- **88 test dei contratti/reader preesistenti: tutti superati**, nella suite
  complessiva precedente da 129 test. L'ultimo controllo aggiunto riguarda
  esclusivamente la validazione Storage del nuovo monitor.
- Totale: **130 casi distinti verificati localmente**.
- `git diff --cached --check`, sintassi Python, link locali del documento e
  `test-canonical-workspace-cleanliness.ps1`: superati.
- Tutti i 17 percorsi della consegna sono nuovi; nessun file applicativo esistente
  ÃƒÂ¨ modificato. La specifica originale conserva lo SHA-256 riportato in apertura.
- Le prove non hanno eseguito deploy, creazione/modifica di risorse cloud,
  chiamate del monitor ai servizi reali, push, PR o CI.

La base locale comprende altri lavori giÃƒÂ  presenti in `main`. Per esaminare solo
questa consegna confrontare il branch con `1d598572194b173675d6dbd35d121a2399f615a5`;
un futuro confronto diretto con `origin/main` potrebbe includere anche quei lavori.

## Completamento del passaggio Scheduler: verifiche locali

Verificato il **2026-10-16 alle 05:18 UTC** sullo stesso branch, dopo `92720ae2`:

- **61 test superati**, nessuno skip, durata 13,823 s: 20 nuovi casi sul passaggio
  Scheduler/Job e 41 casi preesistenti del monitor, definizioni e pacchetto.
- Provati ritardi entro/fuori intervallo, scadenza fra avvio e partenza del container,
  duplicati, risposta di avvio perduta, confronto con uno slot più recente,
  scadenza durante raccolta e riconciliazione, cambio dell'ora legale, header
  invalidi/duplicati e tentativi di fornire parametri tramite il corpo HTTP.
- Prova HTTP reale **solo su loopback** con Uvicorn 0.46.0 e API Job simulata.
  Nei test del nuovo percorso le connessioni esterne sono bloccate.
- Prova completa simulata: due consegne dello stesso slot producono sei punti
  complessivi, non dodici; due slot diversi producono dodici punti. Nessun nuovo
  punto per la consegna scaduta, neppure quando lo stato contiene già uno slot nuovo.
- Import del pacchetto isolato, cataloghi, `--help` dei due entrypoint e contratto
  ENTRYPOINT/CMD verificati. Non è una build Docker né una prova IAM Google.
- Le espressioni PromQL, i descrittori e le policy sono invariati. Il test con
  promtool non è stato ripetuto in questo completamento; resta il risultato
  della prima consegna. Sono state rieseguite le verifiche delle definizioni locali.
- Pulizia canonica, controllo whitespace e link locali: verificati. Nessuna
  modifica alla specifica originale in Downloads, a reader o acquisizioni.

Comando della suite di questo completamento, da `experiments/weather_autonomy`:

```powershell
python -B -m unittest test_freshness_monitor_dispatcher test_freshness_monitor test_freshness_monitor_policies.DefinitionTests.test_disabled_policies_and_fixed_cardinality test_freshness_monitor_policies.DefinitionTests.test_review_files_match_the_definitions test_freshness_monitor_package -q
```

Il codice del passaggio è completato e verificato localmente. Restano separati
il deploy, l'IAM, il riscontro degli header reali, le notifiche e l'attivazione;
nessuna di queste operazioni è stata eseguita. Nessuna scrittura GitHub o CI.
