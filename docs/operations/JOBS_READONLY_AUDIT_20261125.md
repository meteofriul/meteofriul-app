# Audit operativo dei job e dei dati — 25 novembre 2026

## Base, perimetro e metodo

Rapporto in **sola lettura** sul progetto cloud atteso `meteo-friul`, con
identità CLI verificata prima delle query. Codice di riferimento:
`origin/main` `61ca8e5e` (controllato anche sul remoto il 25 novembre).
Il profilo nativo `controllo_job` è stato effettivamente attivato per la
raccolta; non è un agente generico che simula il profilo. L'inventario
permanente è [JOBS_INVENTORY.md](JOBS_INVENTORY.md); la relazione con le pagine
è nella [mappa app](APP_SYSTEM_MAP_20261125.md).

Le query CLI hanno elencato Cloud Run Job in `europe-west1` e `europe-west8`,
Scheduler in entrambe le regioni pertinenti, esecuzioni recenti e log
aggregati; sono stati confrontati prodotti Storage e risposte HTTP pubbliche.
La lettura dei riepiloghi delle corse copre il 24–25 novembre fino a circa
**14:40 UTC / 15:40 CET del 25 novembre**; non anticipa gli slot ancora da
eseguire nel pomeriggio o nella sera. Le ultime letture API pubbliche sono
state eseguite alle **14:55 UTC / 15:55 CET**.
La lettura dell'installazione Windows ha controllato i task Mercati. Questo
rapporto conserva solo nomi di risorse, esiti e contatori aggregati: non
riporta identificativi di persone, dispositivi, token o materiale di firma.
Nessun job avviato o ritentato, nessuna policy o pianificazione cambiata,
nessuna notifica inviata, nessun deploy, nessuna modifica a Mercati.

**Legenda:** `VERIFICATO` significa provato solo per l'aspetto e la finestra
indicati; `ANOMALIA` indica una discrepanza osservata; `NON VERIFICABILE`
segnala un confine di accesso o di campione. `Completed=True`, HTTP 200,
catalogo scritto, FCM accettato e visualizzazione sul telefono restano
passaggi diversi.

### Riproducibilità e ampiezza del campione

La raccolta ha usato `gcloud run jobs list/describe` nelle due regioni,
`gcloud scheduler jobs list/describe` in west1, liste delle esecuzioni per
job e `gcloud logging read` sui job/esecuzioni recenti del 24–25 novembre.
Le query hanno selezionato stato, istanti, target, cron/fuso e riepiloghi
applicativi; i log riportati qui sono categorie e contatori, non dump grezzi.
Le policy sono state lette con GET di Cloud Monitoring, perché lo script di
confronto repository si è interrotto come descritto sotto. Per i prodotti
sono stati confrontati puntatori Storage e letture HTTP dei reader meteo,
catalogo/API Eventi e due risposte di allerte ufficiali.

L'inventario di job è completo **per le regioni `europe-west1` e
`europe-west8` interrogate**, e quello degli Scheduler per le regioni
interrogate nel progetto; non è una scansione di ogni possibile regione o
di altri progetti. Le esecuzioni sono un campione limitato al 24–25 novembre o
all'ultima corsa nota dei job senza Scheduler; i log non sono una ricerca
storica completa. Il confronto dei prodotti HTTP usa un campione pubblico,
non ogni Comune, documento meteo, evento o dispositivo. Questo rapporto
non attesta parità fra tutte le immagini distribuite e il commit `main`:
il readback configurativo sotto confronta cinque digest con ricevute datate,
ma non ricostruisce il contenuto delle immagini o tutti i grant IAM.

## Inventario cloud e divergenze dal vecchio registro

Alla lettura del 25 novembre risultano **15 istanze Cloud Run Job**:
14 in `europe-west1` e una seconda istanza di `official-alert-sync` in
`europe-west8`. I **12 Scheduler sono `ENABLED`** e si trovano in
`europe-west1`; 11 invocano l'API Cloud Run `jobs:run`, mentre il monitor
ICON passa per il dispatcher HTTP `/dispatch`. Il target del sync FVG è in
west8. Non risultano Scheduler ordinari per il job storico FVG in west1,
`event-source-publication-control` e `local-notice-tolerance-qa`.

Il registro datato 28 ottobre elencava 14 istanze e 11 Scheduler: da allora
è presente anche `meteofriul-markets-weekly-audit`. I due Scheduler ICON
hanno ora **otto slot UTC al giorno**, non due: le 06/18 sono le basi, con
recuperi a +1, +2 e +4 ore. La ragione e il deploy documentato sono in
[ICON_AUTOMATIC_RECOVERY_DEPLOY_20261031.md](ICON_AUTOMATIC_RECOVERY_DEPLOY_20261031.md).
Queste differenze sono state incorporate nel nuovo [inventario](JOBS_INVENTORY.md).

### Readback configurativo delle 15 istanze

Tutte hanno `taskCount=1`. `Digest` è il prefisso di dodici caratteri del
digest SHA-256 effettivo, utile per confrontare il job senza riportare
indirizzi di registro o valori d'ambiente. «Immagine» significa che il job
non sovrascrive l'entrypoint: l'entrypoint interno dell'immagine non è stato
ispezionato in questo audit. `Retry` è il massimo Cloud Run, non quello dello
Scheduler.

| Cloud Run Job (`meteofriul-` omesso) | Generazione | Digest | Comando nel job | Timeout / retry | Target Scheduler |
| --- | ---: | --- | --- | --- | --- |
| `cams` | 11 | `83a67540e413` | immagine | 1200 s / 0 | `cams-refresh` west1 |
| `evening-forecast` | 8 | `7d4596aef2b7` | `python -m app.jobs.send_evening_forecast` | 300 s / 0 | omonimo west1 |
| `event-source-publication-control` | 5 | `cffe49982e47` | `python -m app.jobs.control_event_source_publication` | 120 s / 0 | nessuno |
| `events-refresh` | 49 | `d6ff27f255a0` | immagine | 900 s / 0 | omonimo west1 |
| `icon` | 8 | `c0503d339272` | immagine | 900 s / 2 | `icon-refresh` west1 |
| `icon2i-freshness` | 3 | `5be377e2a3a8` | immagine | 120 s / 0 | dispatcher `/dispatch` |
| `local-notice` | 21 | `3b0cac97d0bb` | `python -m app.jobs.send_local_weather_notices` | 300 s / 0 | omonimo west1 |
| `local-notice-tolerance-qa` | 1 | `48d293f2d2ea` | `python -m app.jobs.send_local_weather_notices` | 300 s / 0 | nessuno |
| `markets-weekly-audit` | 7 | `3e53f4370324` | `python -m app.markets.weekly_audit_job` | 3600 s / 0 | omonimo west1 |
| `morning-forecast` | 10 | `3811ae86d202` | `python -m app.jobs.send_morning_forecast` | 300 s / 0 | omonimo west1 |
| `national-icon` | 2 | `d062db94eedf` | `python national_cloud_worker.py` | 1800 s / 0 | `national-icon-refresh` west1 |
| `national-official-alert-send` | 2 | `0ca66c4c7839` | `python -m app.jobs.send_national_official_alerts` | 300 s / 0 | omonimo west1 |
| `national-official-alert-sync` | 2 | `0ca66c4c7839` | `python -m app.jobs.sync_national_official_alerts` | 300 s / 0 | omonimo west1 |
| `official-alert-sync` west1, storico | 17 | `7af9d579cdc1` | `python -m app.jobs.sync_official_alerts` | 180 s / 0 | nessuno |
| `official-alert-sync` west8 | 4 | `7364eca349bd` | `python -m app.jobs.sync_official_alerts` | 180 s / 0 | omonimo west8 |

I digest interi di **Eventi, serale, CAMS e dei due ICON** coincidono con le
ricevute di deploy già presenti
([23 novembre](OPS_JOBS_PROMOTION_20261123.md),
[CAMS 2 novembre](WEATHER_JOB_RECOVERY_20261102.md),
[ICON 31 ottobre](ICON_AUTOMATIC_RECOVERY_DEPLOY_20261031.md)).
Questo esclude una divergenza d'immagine rispetto a **quelle cinque ricevute**,
non attribuisce automaticamente la causa dei guasti. La provenienza delle
altre dieci immagini non è stata confrontata con ricevute in questa passata.
I nomi delle variabili d'ambiente sono stati letti senza valori; account di
servizio distinti sono stati osservati in gruppi, senza riportarne le email.

I target Scheduler coincidono con i job e le regioni attesi. Il dispatcher
del monitor usa OIDC e deadline 30 s; dieci Scheduler ordinari usano OAuth
e deadline 180 s; Markets usa OAuth e deadline 30 s. I grant IAM puntuali
non sono stati letti: una corsa riuscita prova invocazione e lavoro svolto
nel campione, non completezza generale dei permessi su tutti i dati.

## Esiti osservati e impatto sui dati

| Funzione | Esecuzione/campione | Dato o effetto verificato | Giudizio |
| --- | --- | --- | --- |
| **Eventi** | 24/11 `Completed=True`; 25/11 `Completed=False`. | Il catalogo pubblico del 25/11 è `degraded`: Azalea e TurismoFVG `stale`, Barcolana `fresh`, Spazzapan in pausa. L'API per un punto comunale pubblico di Udine risponde 200/`ready` con 88 eventi nella ricerca; non significa che tutte le fonti siano sane. | **ANOMALIA** su due fonti; resto del catalogo disponibile nel campione. |
| **CAMS** | Slot 25/11 09, 10 e 11 UTC: tre `Completed=False`. | Puntatore Storage e HTTP ancora al ciclo del 23/11; aria e pollini bloccati alla validazione dei metadati pubblici, UV fuori finestra in questi slot. | **ANOMALIA**: il prodotto aria/pollini non è corrente; il vincolo preciso rifiutato non è nei log. |
| **ICON nazionale** | Dodici slot consecutivi 24–25/11 `Completed=False`. | Storage fermo al ciclo del 21/11; reader HTTP restituisce 503. | **ANOMALIA**: prodotto nazionale non disponibile nel controllo pubblico. |
| **ICON FVG** | Ultime tre corse osservate `Completed=True`. | Storage e HTTP mostrano ciclo del 25/11. | **VERIFICATO** avanzamento del prodotto FVG nel campione; non prova ogni Comune/ora. |
| **Sintesi mattutina** | 25/11 06:30 UTC, `Completed=True`. | Riepilogo `sent`, 68/68 FCM accettati, zero errori; 23 gruppi con testo limitato. La visualizzazione sul telefono non fa parte di questo audit. | **VERIFICATO** esito applicativo aggregato; consegna finale **NON VERIFICABILE**. |
| **Anticipazione serale** | 24/11 19:45 UTC, `Completed=True`, immagine aggiornata il 23/11. | Riepilogo `sent`, 68/68 FCM accettati, zero errori; 21 gruppi con testo limitato. Prima prova ordinaria successiva al deploy, distinta dal TEST QA. | **VERIFICATO** esito applicativo aggregato; consegna finale **NON VERIFICABILE**. |
| **Avvisi locali** | 25/11 14:00 UTC, `Completed=True`. | `no_candidate`, zero invii e zero gruppi degradati: risultato legittimo nel campione. | **VERIFICATO** esito della corsa, non una prova di avviso reale. |
| **Allerte FVG ufficiali** | Job schedulato in west8, 25/11 13:00 UTC, `Completed=True`. | Riepilogo `cache_status=fresh`, `active=true`, `refreshed=true`. API pubblica HTTP 200: una allerta attiva, cache fresca, lettura 13:00:10Z, validità fino al 26/11 11:00Z. | **VERIFICATO** job e dato pubblico nella lettura; push non verificato. |
| **Sync allerte DPC nazionali** | 25/11 13:35 UTC, `Completed=True`. | `status=ok`, `already_current`, revisione sorgente `20261124_1515`; per contratto nessun push in questo job. API pubblica su un Comune campione: HTTP 200, `active`, completo, 15 record, cache fresca, validità fino al 25/11 22:59:59Z. | **VERIFICATO** riepilogo e campione pubblico, non ogni Comune. |
| **Invio allerte DPC nazionali** | 25/11 13:50 UTC, `Completed=True`. | `no_candidate`, zero invii e zero errori: risultato legittimo nel campione. | **VERIFICATO** riepilogo, non prova di invio con candidato. |
| **Monitor freschezza ICON** | 25/11 14:40 UTC, container `Completed=True`. | FVG `check_state=0`, completo e senza criticità; nazionale `check_state=2`, incompleto e critico, con età run circa 110,7 ore, puntatore HTTP non leggibile e copertura critica. | **ANOMALIA** nazionale confermata dal monitor; successo del container non è salute del prodotto. |
| **Audit Mercati cloud** | 24/11 08:00 UTC, `Completed=True`. | Rapporto `completed`: 100/100 mercati controllati, uno con cambi, 91 con issue. Il job salva un rapporto separato e non aggiorna schede o app. | **VERIFICATO** esecuzione e contatori; qualità delle 91 issue da esaminare nel workstream Mercati in pausa. |
| **Sync FVG storico west1** | Senza Scheduler; ultima corsa letta 8/10, `Completed=True`. | Istanza distinta dal target attivo west8. | **VERIFICATO** presenza; funzionamento attuale non applicabile al flusso schedulato. |
| **Controllo pubblicazione Eventi legacy** | Senza Scheduler; ultima corsa letta 29/8, `Completed=True`. | Non è il refresh pubblico Eventi. | **VERIFICATO** presenza storica; nessuna corsa provocata. |
| **QA tolleranza avvisi locali** | Senza Scheduler; ultima corsa letta 19/10, `Completed=True`. | Job di prova, non circuito ordinario. | **VERIFICATO** presenza storica; nessuna corsa provocata. |

Per Eventi, i log del 25 novembre attribuiscono il fallimento ad Azalea
(`adapter_exception` su schede d'archivio non riconosciute) e TurismoFVG
(`CalendarPageUnavailable` su pagina 28, HTTP 404). Barcolana è invece
`fresh`: la correzione del 23 novembre ha superato almeno questa corsa,
non ogni futuro calendario. La regola del catalogo conserva i diagnostici
e nasconde le schede delle fonti `stale`; perciò job fallito e API HTTP 200
sono compatibili. La verifica dell'API è limitata alla ricerca campionata.
([publisher](../../backend/app/events/pilot_cloud.py),
[reader](../../backend/app/events/pilot_http.py)).

`unrecognized Azalea archive cards` significa che il parser ha trovato zero
oppure più di 100 elementi con la classe attesa: il log non distingue le due
condizioni né prova un cambio del sito. La lettura dell'archivio precede il
parallelismo dei dettagli aggiornato il 23 novembre; lo stesso sintomo era
già [documentato in ottobre](COMMUNITY_EVENTS_TEST_INTEGRATION_2026-10-14.md).
TurismoFVG distingue un 404 di pagina da un calendario vuoto e tenta la
ripartizione per date con controllo dei conteggi. Occorre stabilire dai log
se la pagina 28 era nella scansione diretta o nel recupero: per finestre con
totale non superiore a 512 il codice torna alla scansione diretta, possibile
lacuna da riprodurre. Anche un 404 di pagina 46 era già
[documentato in ottobre](TURISMOFVG_CALENDAR_404_FIX_20261024.md).
Servono le risposte sorgente e il totale dichiarato, acquisiti in sola
lettura e senza dati personali, prima di scegliere una correzione.

Le corse ICON nazionali riportano `manual_review` /
`acquisition_requires_review`; questa categoria descrive un blocco
dell'acquisizione, **non** una diagnosi conclusiva della causa upstream.
Nel [codice di recupero](../../experiments/weather_autonomy/local_pipeline/icon_recovery.py)
lo stesso stato può essere ripetuto dagli slot successivi quando una fence
`manual_review` è già attiva: dodici esecuzioni fallite non provano dodici
acquisizioni indipendenti. La lettura dello stato durevole
`pilot/state/icon-recovery/v1/national/active.json` mostra
`phase=manual_review`, slot `20261121-pm`, ciclo `20261121T120000Z` e fence
presente; l'identificativo della fence è omesso. La prima sequenza osservata
il 21 novembre registra `national_acquisition` avviata alle 18:01:12 UTC,
terminata alle 18:02:58, poi `manual_review` alle 18:03:20. Per quel ciclo
esiste `intent.json`, ma non `mapping.json`, `prepared.json` né il manifest
pubblico: il processo si è fermato prima di un checkpoint pubblicabile.
Il traceback disponibile è un `RuntimeError` generico di pubblicazione
incompleta; non rivela l'eccezione originaria né dimostra un errore della
fonte. La diagnosi va proseguita sul bundle e sulla validazione di quel ciclo,
preservando la fence fino a una ripresa con checkpoint verificato.
I log CAMS dei tre slot 09/10/11 UTC del 25 novembre coincidono: per aria e
pollini `phase_failed` a `metadata_validation`, `PublicMetadataError` in
`cams_request_plan.py:250`, poi errore generico del worker. Il reason code
di componente è `nonrecoverable_failure`, **non** l'evento distinto
`acquisition_nonrecoverable_failure` del retriever, assente nel campione
24–25 novembre. Il controllo dei metadati pubblici può fermare il piano
prima del recupero ADS; il log nasconde il dettaglio del campo rifiutato e
non contiene un riepilogo dei vincoli, quindi il mismatch preciso resta
**NON VERIFICABILE**. UV è `disabled/uv_outside_scheduled_window` in quegli
slot, non un fallimento UV. Il ciclo del 23 novembre supera il limite di
continuità di 36 ore per aria/pollini (o 30 ore senza grant): quei dati non
sono correnti il 25 novembre. La UI può mostrare stati `unavailable`,
`pending` o `last_known` e un dispositivo può avere una cache propria; il
comportamento effettivo non è stato verificato su un telefono.

L'impatto ICON nazionale dipende dalla località e dal gate di prodotto:
quando il percorso nazionale è abilitato, il bootstrap per località italiane
usa quel reader, incluso FVG nel pilota nazionale. La visibilità delle
Previsioni nazionali nella release ordinaria non è provata da questa lettura.
FVG ordinario usa invece `weather/v1`, che nel campione avanza. Il reader
nazionale richiede copertura corrente e futura: il ciclo del 21 novembre non
è un fallback affidabile per il 25. Bollettino e allerte ufficiali seguono
percorsi separati.

## Task locali e risorse fuori dal codice main

`MeteoFriul-MarketsRefresh-Local` è **Disabled**; ultima corsa Windows
registrata il 7 novembre alle 08:20. `MeteoFriul-MarketsReminder-Local` non
è registrato. Il job cloud `meteofriul-markets-weekly-audit` è un'altra
risorsa: Scheduler attivo martedì alle 09:00 italiane, job di generazione 7,
sette esecuzioni complessive lette. Il suo entrypoint
`python -m app.markets.weekly_audit_job` si trova nel ramo separato
`codex/markets-weekly-audit-20261113`, **non** nel `main` mappato qui.
Il codice del ramo precisa che salva il rapporto di audit, senza scrivere
l'archivio Mercati o pubblicare l'app. Non è stata effettuata alcuna
operazione su quel ramo o sui dati Mercati.

## Policy e visibilità operativa

La lettura diretta delle policy Monitoring via API GET ha restituito
**23 policy: 21 abilitate e due vecchie prove ICON disabilitate**. Le 21
abilitate comprendono le 18 del
[catalogo repository](../../scripts/cloud-run-job-monitoring-policies.json)
e tre del monitor freschezza ICON (FVG, nazionale e telemetria). Quattro
policy abilitate sono intenzionalmente senza canale di notifica: fallimento
singola corsa Eventi, revisione fonti candidate Eventi, fallimento singola
corsa mattutina e serale. È coerente con il
[riordino del 22 novembre](OPERATIONAL_ALERT_ROUTING_20261122.md): il pannello
raggruppa questi segnali, mentre altre policy mantengono un canale.

Non è stata individuata una policy dedicata al nuovo job Mercati cloud né
all'**invio** delle allerte DPC nazionali. Le policy sul sync DPC non
coprono automaticamente il sender. Inoltre l'endpoint owner
`/api/admin/operations` legge solo mattino, sera ed Eventi: la campanella
del pannello non va descritta come vista completa di tutti i job.
([operations_admin.py](../../backend/app/api/operations_admin.py)).

Lo script di confronto repository
[`sync-cloud-run-job-monitoring.ps1 -Mode Audit`](../../scripts/sync-cloud-run-job-monitoring.ps1)
si interrompe in `StrictMode`: assume la proprietà `notificationChannels`,
che le quattro policy senza canale omettono. Questo è uno scostamento dello
**strumento di audit** rispetto alla configurazione intenzionale, non la
prova che le policy manchino. La lettura diretta API GET non ha modificato
alcuna policy. Non sono stati verificati incidenti aperti, recapito delle
email o ricezione dei push sui telefoni.

## Priorità e confini della verifica

1. **ICON nazionale:** identificare l'errore fra acquisizione completata e
   checkpoint del 21 novembre; solo dopo, predisporre una ripresa verificata
   e confrontare Storage/HTTP. Non rimuovere la fence né allentare il monitor
   sulla base del solo successo di un container.
2. **CAMS:** confrontare in sola lettura catalogue/form/constraints pubblici
   con il contratto del piano, riprodurre il vincolo rifiutato e verificare
   poi aria, pollini, UV, continuità e validità. Il ciclo del 23 novembre
   non deve apparire come aggiornamento del 25.
3. **Eventi:** distinguere il numero di schede Azalea e la risposta ricevuta,
   poi localizzare la pagina 28 TurismoFVG nella scansione o nel recupero;
   riprodurre con fixture, preservare i gate e ricontrollare lotti e API.
4. **Copertura operativa:** pannello owner e policy esistenti non sono una
   prova unica di salute di tutti i 12 Scheduler e dei relativi dati. Riparare
   lo script di audit in una modifica separata e decidere la copertura di
   Markets/sender DPC senza creare notifiche duplicate.

Questa è una diagnosi, non un'autorizzazione a lanciare recuperi, mutare
Scheduler/policy, distribuire immagini o inviare notifiche. Eventuali
correzioni hanno responsabilità distinte: `meteo` per ICON/CAMS/notifiche,
`eventi` per gli adattatori Eventi, e una verifica separata dei risultati.

## Seguito del 25 novembre, ore 15:34 UTC / 16:34 CET

Su richiesta del proprietario è iniziato un **workstream distinto** per
correggere ICON e CAMS; questa sezione aggiorna il campione in sola lettura,
senza cambiare retroattivamente l'esito delle 14:55 UTC sopra. Il ramo codice
è `codex/weather-icon-cams-recovery-20261125`, creato dal `main` verificato.

Il job CAMS dello slot **15:00 UTC** è terminato `Completed=False` alle
15:05:53: aria/pollini hanno registrato `PublicMetadataUnavailable`, stage
`metadata_validation`/`public_metadata_plan`, reason
`catalogue_sanity_unavailable`. Il catalogo pubblico ora indica
`cads:sanity_check.status=warning`, fuori dai due stati accettati
dall'immagine distribuita. Storage e HTTP concordano sulla famiglia
aria/pollini ancora al run del **23 novembre, 09:01:18 UTC**. Nello stesso
slot il log indica `uv_publication_verified`; il puntatore UV Storage/HTTP
mostra `run_at` del **25 novembre 00:00 UTC**. La freschezza UV è quindi
distinta dal guasto della famiglia aria/pollini.

Una lettura GET dei metadati ufficiali ADS conferma anche che il form ora
espone **35 variabili**, includendo le 28 richieste e sette aggiunte U11.
L'[annuncio ECMWF](https://forum.ecmwf.int/t/upgrade-u11-to-the-cams-european-air-quality-products/15596)
data l'upgrade al 23 novembre e la prima produzione al 24. Il confronto
spiega il `PublicMetadataError` degli slot 09/10/11: il validatore
dell'immagine distribuita pretendeva un insieme identico di 28. Il candidato
locale accetta solo le sette opzioni aggiuntive, continua a richiedere
esattamente 28 variabili × 97 lead nel piano e valida i constraints prima
di tollerare `warning`. Un piano 28/97 è stato costruito con GET, senza
ADS POST; questa non è una prova di recupero del dato. U11 cambia anche
una conversione upstream dei gas: servono decodifica e controllo di
plausibilità dopo una vera acquisizione.

ICON nazionale è ancora `manual_review` sullo slot `20261121-pm`: ultimo
job osservato alle 10:00 UTC fallito, puntatore Storage al 21 novembre e
reader HTTP 503. La prima acquisizione del 21 novembre si concluse prima
del guasto, ma il bundle non fu salvato come checkpoint; l'eccezione iniziale
è assente dai log consultati. Un candidato di codice aggiunge fase e tipo
di errore sanitizzati **prima** della cattura; non cancella né supera la
fence. Lo sblocco richiede un procedimento operativo con audit immutabile,
controllo di concorrenza e verifica del nuovo ciclo, non un semplice retry.

Gli Scheduler erano ancora `ENABLED`: prossimi slot osservati ICON nazionale
18:00 UTC e CAMS 20:00 UTC. Il codice candidato non era distribuito alle
15:34 UTC. La verifica dei test, di eventuali immagini e dei prodotti dopo
una correzione viene registrata nel workstream meteo; non si inferisce da
questa lettura.

## Seguito delle 16:19 UTC / 17:19 CET: prova di build

La [PR 61](https://github.com/meteofriul/meteofriul-app/pull/61) contiene la
correzione CAMS e la diagnostica ICON, con 120 test mirati e CI PR verde sul
commit di codice. Due candidate Cloud Build sono state bloccate dai controlli
di conservazione dell'immagine prima della pubblicazione: una differenza nei
permessi dei due file sovrapposti, poi un metadato del builder confrontato
come configurazione runtime. Il terzo pacchetto, ancorato al commit
`76c601bf` e al digest base `sha256:83a67540…`, ha superato tutti e quattro
gli step della build `4cf58cf9-588c-41d6-86e0-2c700c361fd5`: cambiano
solo i due file runtime approvati e 438 test offline senza rete sono passati.
Il nuovo digest `sha256:b377e7d0…` è **soltanto un artefatto candidato** alle
16:19 UTC. Nessun risultato di un job reale o dato pubblicato è implicato.
[Dettaglio dei gate](WEATHER_ICON_CAMS_RECOVERY_20261125.md).

## Seguito delle 16:39 UTC / 17:39 CET: deploy e prova CAMS

La PR è stata integrata in `main` `488f7d3c`, con CI PR e `main` verdi. Il
solo job CAMS è passato dal digest `sha256:83a67540…` al candidato verificato
`sha256:b377e7d0…`, generazione 11 → 12; readback del template, al netto del
nonce generato da Cloud Run, e Scheduler invariati. Una sola corsa manuale
`meteofriul-cams-96f4b` ha superato i metadati U11 e inviato una richiesta
ADS con intent e ricevuta durevoli, ma è terminata `Completed=False` alle
16:39:43 UTC perché ADS era ancora `accepted` e il budget di attesa del
worker è scaduto. La prossima ripresa deve usare lo stesso job ADS; i dati
aria/pollini restano da verificare prima di dichiarare recupero. Il controllo
preliminare dei checkpoint aveva omesso il prefisso Storage `pilot/`; la
rettifica e le generazioni degli oggetti sono nel
[rapporto meteo](WEATHER_ICON_CAMS_RECOVERY_20261125.md).

ICON nazionale è rimasto in `manual_review` sul ciclo del 21 novembre
anche alle 16:53 UTC. La [PR 63 bozza](https://github.com/meteofriul/meteofriul-app/pull/63)
prepara una supersessione con incidente immutabile e CAS, ma non è integrata
né distribuita: job operatore, IAM, isolamento degli altri writer e prova di
quiescenza restano gate. Nessun reset della fence è stato eseguito.
