# Eventi: struttura dei job, pubblicazione e allarmi

Data dell'audit: 13 ottobre 2026. Ramo locale: `codex/events-card-quarantine`.
Questo documento descrive il **codice del ramo** e separa ciò che è stato
osservato online da ciò che deve ancora essere distribuito. È pensato come base
per una revisione fonte per fonte e per i futuri interventi operativi.

**Aggiornamento Fase 0, sera del 13 ottobre:** correzioni, controlli locali e
prova browser sono documentati nel [resoconto Fase 0](EVENTI_FASE_0_CORREZIONI_AUDIT_2026-10-13.md)
e nel [collaudo locale](EVENTI_FASE_0_COLLAUDO_LOCALE_2026-10-13.md).
Il successivo [deploy e collaudo TEST](EVENTI_FASE_0_DEPLOY_E_TEST_2026-10-13.md)
registra worker/API aggiornati al commit `9718e2bc`, un ciclo cloud fallito su
TurismoFVG e il recupero mirato riuscito. Il catalogo finale ha 15 fonti
pubblicabili, 6 quarantene e nessun lotto `stale`; l'app TEST ha letto lo
snapshot nuovo. Resta da verificare un ciclo completo senza recuperi e da
chiarire i 7 risultati TurismoFVG pendenti del primo tentativo. Le sezioni
11–13 rimangono la cronologia degli interventi precedenti; questa Fase 0
non è stata ancora promossa a `main` locale.


**Audit successivo dei pendenti:** il [controllo TurismoFVG](EVENTI_TURISMOFVG_PENDING_AUDIT_2026-10-13.md)
ha riprodotto il blocco dell'intera fonte per un errore isolato di lettura,
la perdita di diagnostici, il rinnovo anticipato che rimuove prove ancora
valide e il caso opposto di manutenzione HTTP 200 accettata come lotto vuoto.
Dopo l'approvazione sono state implementate e testate localmente le
[correzioni di isolamento dei dettagli](EVENTI_TURISMOFVG_ISOLAMENTO_DETTAGLI_2026-10-13.md).
Sono nel ramo, non nel runtime distribuito: quarantene per errori isolati con
prova corrente di funzionamento, protezione dal lotto vuoto da manutenzione,
rinnovi senza falsa freschezza e diagnostici separati del tentativo fallito.

## 1. Obiettivo e confine

Il percorso principale raccoglie eventi da 15 siti approvati, verifica gli
inventari e le singole schede, salva un catalogo JSON e lo rende consultabile
all'app. La richiesta HTTP dell'utente legge il catalogo: non visita i siti
degli eventi. L'app mostra solo eventi con date o programma provati, filtra per
località e unisce i doppioni conservando la provenienza.

I siti osservati come possibili fonti aggiuntive non sono automaticamente
fonti pubblicate. Palazzo Attems e GiroFVG sono **monitor diagnostici**: la
loro lettura non crea schede pubbliche. Pro Loco FVG ed EventiFVG sono stati
valutati come indici; Anteprima Sagre è stata rimossa dal percorso operativo
per accesso cloud non affidabile. Queste distinzioni evitano di confondere
"sito letto" con "fonte completa e pubblicata".

## 2. Percorsi esistenti: non sono lo stesso job

| Percorso | Scopo | Pubblica le schede dell'app? | Comando nel codice |
| --- | --- | --- | --- |
| `meteofriul-events-refresh` | Catalogo Eventi delle 15 fonti | Sì, se i lotti superano i gate | `python -m app.events.pilot_cloud` |
| `meteofriul-events` | Servizio HTTP di consultazione | Legge soltanto il catalogo | `app.events.pilot_http` |
| `meteofriul-event-source-shadow` | Controllo storico in ombra delle fonti legacy | No con `EVENT_SOURCE_FEED_MODE=off` | `python -m app.jobs.sync_event_sources` |
| `meteofriul-event-source-publication-control` | Controllo manuale del gate del percorso legacy | Non è il refresh delle 15 fonti | `python -m app.jobs.control_event_source_publication` |

La configurazione storica documenta lo shadow alle 06:20 e 18:20
`Europe/Rome`, senza pubblicazione, e il publication-control senza scheduler.
Questi due job **non vanno scambiati** con il refresh corrente. Nell'inventario
cloud letto il 13 ottobre il publication-control esiste, ma lo shadow non
compare più nella regione `europe-west1`: la riga shadow descrive quindi il
percorso del codice e la configurazione storica, non un job online confermato.

## 3. Catena del catalogo principale

```text
Cloud Scheduler → Cloud Run Job meteofriul-events-refresh
  → pilot_cloud.publish
  → pilot_sources.source_adapters: 15 adattatori
  → pilot_collection.collect: un processo per fonte, in sequenza
  → pilot_source_policy.gate_batch: inventario e qualità della scheda
  → pilot_catalog.merge_collection: fresh / partial / stale
  → Storage: gs://meteo-friul-weather-data/pilot/events/v1/catalog.json
    (scrittura con generation match)
  → servizio meteofriul-events: lettura JSON, filtro e deduplica
  → app: pagine coerenti, anteprima e cache locale
```

Il job completo è distinto da `--retry-failed`: il retry legge soltanto i nomi
registrati in stato fallito nel catalogo precedente, non rilancia i monitor e
non dichiara di aver ricontrollato le altre fonti. Un adapter passato
esplicitamente a `publish` è un percorso di prova, non il ciclo giornaliero.

### Avvio, tempi e isolamento

`pilot_cloud.publish` richiede il progetto Eventi configurato e controlla il
progetto del client Storage. La lettura online del 13 ottobre conferma
Scheduler giornaliero alle **04:00 UTC**, un task, zero retry, timeout Cloud
Run di **900 secondi**, 1 CPU e 1 GiB di memoria. Questi valori vanno riletti
prima di una distribuzione per rilevare modifiche intervenute dopo l'audit.
Job e servizio API online usano entrambi `EVENTS_CLOUD_PROJECT=meteo-friul`,
`EVENTS_DATA_BUCKET=meteo-friul-weather-data` e
`EVENTS_CATALOG_KEY=pilot/events/v1/catalog.json`, ma hanno immagini distinte.
Il writer usa l'account `meteofriul-events-writer`, il lettore l'account
`meteofriul-events-reader`.

Gli adapter girano **in sequenza**, ciascuno in un sottoprocesso `spawn`. Il
budget complessivo dichiarato è 860 secondi, con limite massimo ammesso di
875. TurismoFVG ha 360 secondi, Paesi in Festa 90, Villa Manin 65, SagreFVG
e Teatro Verdi Pordenone 60; gli altri hanno budget da 10 a 35 secondi.
Timeout, eccezione, uscita inattesa o risultato di formato invalido diventano
un errore della singola fonte con un codice diagnostico. La sequenza limita
carico sui siti e memoria del worker; una fonte lenta può comunque consumare
quasi tutto il tempo totale. Il controllo annuale TurismoFVG non parte se il
tempo già usato dal job supera 600 secondi.

### Le 15 fonti pubblicate

Il registro eseguibile è `pilot_sources.source_adapters`; la lista di
ammissione è `pilot_source_policy.APPROVED_SOURCES`. Il test del registro e
quello del job confrontano i nomi per evitare che una fonte venga dimenticata.

| Fonte | Strategia di lettura e controllo principale |
| --- | --- |
| TurismoFVG | Calendario, sitemap, dettaglio strutturato e checkpoint; finestra mobile verificata di 45 giorni, controllo annuale separato il lunedì. |
| Pordenonelegge | Programma ufficiale e copertura degli appuntamenti; una scheda per edizione con programma ordinato. Edizione conclusa ammessa solo con prova. |
| Le Giornate del Cinema Muto | Giorni di calendario e widget del programma ufficiale; una scheda per edizione con sessioni ordinate. |
| Azalea | Archivio, sitemap e dettagli ufficiali. |
| CSS Udine | Indici delle stagioni e dettagli degli spettacoli. |
| Pordenone Pensa | API degli articoli riconciliata con sitemap e dettagli. |
| Teatro Verdi Pordenone | Stagione, API e dettagli delle repliche. |
| Teatro Verdi Trieste | Calendario, API della stagione, sitemap e dettagli. |
| Paesi in Festa | Liste, indici, sitemap e schede complete; accesso diretto a ogni scheda. |
| SagreFVG | API paginata e finestre annuali complete. |
| Villa Manin | API, calendario e archivio annuale, con dettaglio delle schede attive. |
| Magazzino delle Idee | API, sitemap e liste Mostre/Eventi con dettagli. |
| MESS | Programma dei 36 slot 2026, 18 musei e inventario notizie; laboratori e mostre verificati. |
| Galleria Spazzapan | API Eventi, categorie, mostre, notizie e dettagli incrociati. |
| Barcolana | Calendario e sitemap ufficiali; una scheda dell'edizione con programma scorrevole. |

La tabella indica il contratto implementato, **non** la prova che ogni sito
resterà completo dopo modifiche future. Gli adapter hanno controlli propri
per URL, date, luoghi, conteggi, edizione e anteprime. Le descrizioni sono
prese dalle pagine dove disponibili, attribuite alla fonte e mostrate nella
preview; immagini e descrizioni possono essere integrate da una fonte
corroborante solo quando l'identità dell'evento è stata verificata.

## 4. Decisione su una scheda e su una fonte

L'adapter prima dimostra di aver letto l'**inventario**: tutte le pagine,
finestre, API o sitemap previste per quel sito. Poi valuta le schede. Il gate
comune controlla campi, provenienza, date e altri requisiti. Il criterio
concordato è:

| Caso | Schede pubbliche | Stato della fonte | Esito del job |
| --- | --- | --- | --- |
| Tutto verificato | Tutte le schede eleggibili | `fresh` | Successo, salvo altri errori |
| Inventario completo, alcune schede dubbie identificate per URL e motivo, altre valide | Solo le valide | `partial` | Successo, con tag `quarantined_cards` |
| Inventario incompleto, fonte non verificabile, guasto strutturale generale o timeout del processo | Nessuna scheda della fonte | `stale` o `unavailable` | Fallimento |
| Inventario completo e prova specifica che l'edizione è terminata | Zero schede | `fresh` | Successo |
| Sito con eventi attivi ma tutte le schede escluse | Nessuna | In genere errore | Fallimento e revisione |

La quarantena non copia date incerte e non legge programmi PDF nel job
periodico. Le quarantene conservano il motivo in `review_required`, con
URL o identità quando disponibili. Non tutti gli scarti sono quarantene:
`past_event` viene filtrato senza aggiungere una revisione; gli elenchi
`excluded` degli adapter non sono persistiti in modo generale dal merge.

Per le 12 fonti in `strict_source`, se il controllo generico trova **una sola**
scheda che l'adapter non aveva classificato, la mette in quarantena soltanto
quando l'inventario è verificato, resta almeno una scheda valida e URL e
identità della scheda errata sono riconoscibili. Più esclusioni inattese,
URL non affidabili o zero schede valide fermano queste fonti: potrebbero
indicare una modifica del parser. Pordenone Pensa, Teatro Verdi Pordenone e
Teatro Verdi Trieste non appartengono a `strict_source`: conservano i propri
gate di inventario, ma non questa soglia generica sulle esclusioni inattese.

Il caso di **zero schede valide mentre il sito presenta eventi attivi** resta
bloccante per Villa Manin e Magazzino delle Idee. Allentarlo in modo generale
renderebbe indistinguibile una stagione conclusa da un parser che ha perso
tutte le schede. Occorre una prova specifica di chiusura dell'edizione o un
contratto per quel sito prima di trattare lo zero come normale. Barcolana è
una sola scheda aggregata: se il programma non è verificabile, l'intera
scheda diventa dubbia.

Pordenone Pensa può invece risultare `partial` con zero schede future: il suo
inventario API e sitemap è verificato, ma l'unico articolo potenzialmente
futuro ha date aggiuntive non ancora suddivise in appuntamenti. La scheda
resta in revisione e non viene mostrata; non è una prova che il parser abbia
perso schede già verificate.

`merge_collection` sostituisce solo i lotti `ok`/`partial` con nuovi eventi.
In caso di errore mantiene la vecchia copia internamente, la marca `stale` e
aggiunge `last_attempt_*`; la query HTTP **non** espone eventi di un lotto
`stale`/`unavailable`. Nel report del job, questi due stati usano conteggi,
verifica e problemi dell'ultimo tentativo (`last_attempt_*`), mentre i dati
dell'ultimo lotto valido restano nel catalogo per diagnosi. `pending_count`
distingue i dettagli ancora da verificare; `review_issues` mostra al massimo
30 voci e, per un tentativo fallito, include revisioni e dettagli pendenti.
Non espone il testo completo delle eccezioni. Questa scelta evita di spacciare dati vecchi per
attuali, ma può far sparire temporaneamente una fonte dall'app mentre il job
segnala il problema. `--retry-failed` può recuperarla dopo gli stessi gate.

### Correzione locale successiva: dettagli TurismoFVG

Nel collector mobile un timeout del singolo dettaglio non equivale più a un
timeout dell'intero processo. Con inventario completo, almeno una prova
strutturata letta nello stesso ciclo e schede pubblicabili, gli URL falliti
vengono esclusi con diagnostici e la fonte può risultare `partial`.
Pagine mai tentate per budget esaurito, inventari difettosi e assenza di prova
corrente di funzionamento restano bloccanti. I controlli di salute aggiuntivi
sono limitati a tre dettagli entro il budget esistente.

`detail_diagnostics` conserva i problemi per URL; in caso di lotto fallito
si usano `last_attempt_detail_diagnostics` e, separatamente dal checkpoint
verificato, `last_attempt_control_checkpoint`. Il report mostra al massimo
30 diagnostici. Il checkpoint fallito serve alla diagnosi e non sostituisce
quello verificato usato per il recupero. Regole, test e limiti sono nel
[resoconto della correzione](EVENTI_TURISMOFVG_ISOLAMENTO_DETTAGLI_2026-10-13.md).
Questa parte non è ancora distribuita e non cambia le policy email.

## 5. Pubblicazione del JSON e lettura nell'app

Il catalogo ha schema `pilot-events-v1`, sezioni `sources`, `monitors` e
`attempted_at`; il limite è 8 MiB. La scrittura Storage usa
`if_generation_match`, così due cicli sovrapposti non sovrascrivono
silenziosamente una versione più recente. Il job salva anche un catalogo
parzialmente riuscito prima di segnalare il fallimento delle fonti: il
fallimento del job e la presenza di un JSON nuovo **non sono contraddittori**.

L'API Eventi accetta solo GET, carica il JSON senza fare scraping e usa una
cache di processo di 60 secondi. `/api/local/events` richiede coordinate e
raggio tra 5 e 50 km a passi di 5, applica data corrente nel fuso di Roma,
posizione, deduplica e proiezione dei programmi, poi ordina per distanza.
Ogni lotto deve essere `fresh` o `partial` e aggiornato da non oltre 48 ore.
Paginazione, `snapshot` e HTTP 409 impediscono di combinare pagine di due
cataloghi diversi. La risposta contiene gli stati per fonte, i tag dei
fallimenti, lo stato globale e lo stato dei monitor. Anche con un job
terminato correttamente, un lotto `partial` produce il tag
`quarantined_cards` e `catalog_status=degraded` nell'API: significa che alcune
schede sono in revisione, non che il JSON sia mancato o che tutte le fonti
siano bloccate.

**Distribuzione verificata in precedenza:** la limitazione che ammetteva
`partial` soltanto per Paesi in Festa è stata superata dalla distribuzione
API della sezione 11 e dalla promozione locale della sezione 13. La revisione
API `meteofriul-events-00012-pfn` verificata il 13 ottobre leggeva già i lotti
`partial` di tutte le fonti. Le immagini di API e worker sono distinte; è
necessario verificarne la compatibilità, non imporre digest identici.

**Nuova correzione locale dell'età (Fase 0):** `catalog_status` usa ora anche
lo stesso controllo temporale della query, con un unico istante per richiesta.
Oltre 48 ore il tag è `source_expired`; un timestamp mancante, invalido o
senza fuso produce `source_timestamp_invalid`; un timestamp futuro produce
`source_timestamp_future`. Il limite esatto di 48 ore resta incluso. I tag
rendono il catalogo `degraded`, senza modificare la visibilità delle schede.
`source_status` resta lo stato persistito dell'ultima raccolta, quindi può
essere `fresh` mentre il tag segnala che il lotto è scaduto. Per un lotto
`partial` scaduto, il tag temporale precede `quarantined_cards`; la quarantena
rimane riconoscibile dallo stato `partial`. Questi diagnostici API richiedono
una futura distribuzione del servizio per essere disponibili online.

Il frontend (`eventsApi.js`) carica tutte le pagine di uno stesso snapshot,
proietta le schede programma e riusa richieste già in corso. La cache locale
per località ha durata massima di 48 ore; le schermate possono mostrarla
mentre arriva la risposta nuova o se la richiesta fallisce. Il caricamento
dati dell'app non equivale a una nuova raccolta dai siti: il refresh utente
interroga l'API, che legge il JSON già pubblicato. Per verificare una
correzione al job occorre quindi distinguere **versione dell'immagine del
job**, **generazione del catalogo**, **versione del servizio API** e **cache
dell'app**.

L'età della cache locale decorre da `savedAt`, non dall'ultimo successo della
fonte. Una risposta HTTP riuscita con `events=[]` sostituisce la cache con un
elenco vuoto. Il test di regressione conferma il caso valido; un test di
caratterizzazione documenta che accade anche se l'API segnala fonti scadute.
La Fase 0 non modifica tale secondo comportamento. L'adattatore frontend
continua a trattare la risposta del catalogo come `cacheStatus=ready` e
conserva i diagnostici in `raw`; non esiste un campo `empty_reason` che
attribuisca in modo univoco lo zero ai filtri, alle quarantene o alla scadenza.

## 6. Controlli successivi alla raccolta

Nel ciclo completo, dopo le 15 fonti:

1. **Palazzo Attems** legge inventari come candidato. Se una voce cambia o
   la lettura fallisce, salva `review_required` o `unverified` in `monitors`.
2. **GiroFVG** osserva sitemap e categorie. È un indice editoriale con una
   pagina storica HTTP 500 già nota; non crea schede. Cambiamenti o mancata
   lettura seguono la stessa diagnostica separata.
3. **TurismoFVG annual inventory** gira il lunedì, una volta per giorno
   riuscito, per confrontare l'anno con la finestra corrente. Una discrepanza
   o l'impossibilità di verificarlo resta bloccante perché riguarda una fonte
   effettivamente pubblicata. Negli altri giorni il risultato precedente
   rimane nel catalogo.

**Modifica preparata in questo ramo:** Palazzo Attems e GiroFVG emettono il
log strutturato `event_candidate_watch_alert` quando richiedono revisione o
non sono leggibili; non trasformano più in fallimento la raccolta riuscita
delle 15 fonti. La policy separata `events-candidate-watch` usa quel log e lo
stesso canale email operativo, con limite di una notifica per ora. La policy
è stata **creata online il 13 ottobre** e riletta con stato `unchanged`.
L'esecuzione cloud isolata `meteofriul-events-refresh-gzkth` ha emesso un log
reale con `jsonPayload.event=event_candidate_watch_alert` e il nome del job
previsto dal filtro della policy. Palazzo Attems e GiroFVG risultavano
`review_required`; il job è terminato con successo. La schermata dell'email
ricevuta dall'utente il 13 ottobre alle 11:16 circa mostra la stessa policy,
con avvio alle 08:53 UTC: anche la consegna email è confermata. Questo
avviso riguarda i candidati e non prova un fallimento del job Eventi.
Il monitor annuale TurismoFVG e gli errori delle fonti pubblicate
continuano a far fallire il job.

## 7. Allarmi e interpretazione

| Segnale | Attivazione | Significato | Azione corretta |
| --- | --- | --- | --- |
| `events-failures` | Una esecuzione Cloud Run fallita nella finestra di 2 ore | Almeno una fonte pubblicata o un controllo bloccante non è riuscito; possibile anche errore Storage/runtime | Leggere esecuzione, `source_status`, `last_attempt_*`, catalogo e log; identificare la fonte |
| `events-candidate-watch` (log cloud ed email verificati) | Log `event_candidate_watch_alert` del job | Palazzo Attems/GiroFVG hanno cambiamenti o sono illeggibili | Esaminare l'inventario candidato; non trattarlo come fallimento delle 15 fonti |
| Errore annuale TurismoFVG | Eccezione del job, quindi `events-failures` | Riconciliazione annuale mancante o discordante | Esaminare checkpoint e differenza con calendario/sitemap |
| `quarantined_cards` | Tag del lotto `partial` nel catalogo/API | Schede specifiche escluse, altre pubblicate | Revisionare URL e motivi, correggere l'adapter o attendere fonte ufficiale |
| `stale`/`unavailable` | Lotto fallito nel catalogo/API | Nessuna scheda di quella fonte è live | Recuperare la causa, poi retry mirato controllato |

La policy `events-failures` guarda il **risultato del job Cloud Run**, non il
numero di schede. Un'email di errore non dimostra da sola che il JSON non sia
stato scritto; una email di recupero non dimostra che tutti i contenuti
siano completi. Gli stati del catalogo, la generazione Storage e la risposta
API sono verifiche distinte. La configurazione delle policy vive in
`scripts/cloud-run-job-monitoring-policies.json`; lo script
`scripts/sync-cloud-run-job-monitoring.ps1` parte in `Audit` e richiede
`Apply` per scrivere le policy. L'opzione `-PolicyKey events-candidate-watch`
limita audit e applicazione alla nuova policy, evitando di correggere per
errore drift di altri servizi. L'email non viene inviata direttamente dal
backend.

### Procedura quando arriva un avviso

1. Identificare **job, esecuzione e ora** nell'email: un test manuale del job
   ufficiale può attivare le stesse policy del ciclo programmato. Non dedurre
   dalla sola email quale catalogo sia stato usato.
2. Per `events-failures`, leggere lo stato finale dell'esecuzione e il log
   `event_source_verification`. Confrontare `status`, `failure_tag`,
   `review_issues` e `last_attempt_*` dei lotti nel JSON della chiave usata
   da quell'esecuzione. Verificare separatamente se la generazione Storage è
   cambiata: il job può salvare i lotti riusciti e poi uscire con errore.
3. Se un lotto è `partial`, le schede con `review_required` sono escluse e le
   altre sono pubblicabili. Revisionare gli URL e i motivi; non rilanciare
   automaticamente tutte le fonti solo per eliminare il tag.
4. Se un lotto è `stale`/`unavailable`, controllare inventario, risposta del
   sito e timeout. Un `--retry-failed` riguarda solo i lotti falliti e non
   sostituisce il successivo ciclo integrale; verificarne di nuovo stati e
   generazione prima di considerare risolto l'incidente.
5. Per `events-candidate-watch`, leggere `event_candidate_watch_alert` e
   `monitors`. Palazzo Attems e GiroFVG richiedono analisi editoriale o
   tecnica, ma non dimostrano un fallimento delle 15 fonti pubblicate.
6. Controllare la risposta dell'API e, se serve, l'app dopo il refresh. La
   cache dell'API dura 60 secondi e quella locale dell'app può durare fino a
   48 ore: il dato visto sul telefono può quindi appartenere a una
   generazione precedente anche quando Storage è già aggiornato.

## 8. Evidenza e problemi ancora aperti

- Suite locale del ramo: `756 passed, 2 skipped, 189 subtests passed` per
  `backend/tests -k pilot`; altri 46 test mirati, inclusi Palazzo Attems,
  passano. Passa anche il contratto PowerShell dei job di produzione.
  L'audit cloud mirato ha prima trovato `events-candidate-watch=missing`;
  dopo l'applicazione della sola policy l'ha riletta come `unchanged`.
- Il job programmato del **13 ottobre** ha fallito sulle fonti TurismoFVG
  (tre URL da revisionare), Pordenone Pensa (una data futura aggiuntiva),
  Pordenonelegge (redirect inatteso del programma) e Teatro Verdi Pordenone
  (timeout). Questa evidenza è del codice allora online, non di questo ramo.
  Dettagli: [audit della quarantena](EVENTI_QUARANTENA_SCHEDE_2026-10-13.md).
- Nel ramo locale sono state predisposte quarantene per le singole schede di
  numerose fonti, compresi MESS e Galleria Spazzapan. I test dimostrano il
  comportamento con casi costruiti. Un ciclo integrale in sola lettura del 13
  ottobre, eseguito con il catalogo ufficiale come input e Storage sostituito
  da memoria locale, ha completato **15 fonti su 15**: 1.532 schede, TurismoFVG
  `partial` con 1.159 schede e tre URL in revisione, Pordenone Pensa `partial`
  con zero schede future verificabili e un URL in revisione; le altre 13 fonti
  sono `fresh`. Il JSON è stato salvato solo in un file temporaneo locale.
  Nella query locale per Caneva, la Sagra del Rosario delle due fonti è una
  scheda sola; per Trieste, Barcolana è una scheda sola con 672 sessioni.
  Palazzo Attems e GiroFVG hanno prodotto un unico log
  `event_candidate_watch_alert` senza far fallire il ciclo. Questo log locale
  non dimostra ancora l'invio della notifica cloud.
- L'API WSGI del ramo, alimentata in memoria con il JSON del preflight cloud,
  risponde `200 OK` per Caneva, riporta TurismoFVG e Pordenone Pensa come
  `partial` e mostra una sola Sagra del Rosario. Lo stato globale è
  `degraded` perché esistono schede in quarantena, anche se l'esecuzione cloud
  è riuscita; le pagine successive restano disponibili tramite `next_offset`.
- Per le 12 fonti `strict_source`, il gate generico mette in quarantena una
  sola scheda inattesa con identità verificabile e almeno un'altra scheda
  valida. Più esclusioni inattese o l'assenza di altre schede valide bloccano
  queste fonti. Per le tre eccezioni si veda la sezione 4. La regola
  assoluta "qualsiasi numero di schede errate non blocca mai il job" potrebbe
  mascherare un parser rotto; il limite va verificato fonte per fonte nei
  primi cicli reali.
- Il Dockerfile Eventi include ora anche `test_pilot_mess.py` e i suoi due
  fixture: il controllo MESS passa così sia nella suite locale sia nella
  build dell'immagine. La Cloud Build `1b5a76e9-b702-47a3-a9b2-cc3daa5d0423`
  è riuscita e ha prodotto il digest di prova
  `sha256:3d6afce26fd089161047fc32b9d088365644a50328ccfeb4499b0066fddf3c6e`
  dal commit locale `ae8f5af5`. Gli altri test locali non copiati nel
  container restano una copertura distinta da eseguire prima della distribuzione.
- La lettura cloud del 13 ottobre ha confermato Scheduler Eventi `0 4 * * *`
  nel fuso `Etc/UTC`, job `meteofriul-events-refresh` con timeout 900 s,
  account `meteofriul-events-writer` e immagine con digest
  `sha256:e17ad7a8e168820d4d2bcd61b9427a729f0898297d8b73dd2075336826fe39da`.
  Il servizio API usa il digest distinto
  `sha256:aed9e7f26cd0072523048f8daf258b3fcb53c252dfdb88cb7e4fabcd322b36b7`.
  Il job legacy `meteofriul-event-source-publication-control` esiste, mentre
  `meteofriul-event-source-shadow` non compare nell'inventario dei job della
  regione. L'audit delle policy trova `events-failures` invariata e
  `events-candidate-watch` inizialmente mancante, poi creata e riletta come
  `unchanged`. Trova inoltre drift nella policy `icon-fvg-last-success`,
  estranea agli Eventi: l'applicazione è stata limitata a
  `events-candidate-watch`.
- L'esecuzione cloud di prova `meteofriul-events-refresh-gzkth` ha usato il
  digest nuovo e la chiave
  `pilot/events/v1/preflight/quarantine-ae8f5af5-20261013.json`, inizializzata
  come copia del catalogo ufficiale. È **riuscita in 6 minuti e 40 secondi**.
  Il JSON di prova è passato dalla generazione `1791881124862142` a
  `1791881568294580`: 15 fonti `fresh`/`partial`, 1.533 schede, TurismoFVG
  `partial` con quattro URL in revisione, Pordenone Pensa `partial` con uno.
  I monitor Palazzo Attems e GiroFVG sono `review_required` senza fallimento
  del job; Cloud Logging contiene il log strutturato corrispondente alle
  condizioni della policy separata. La scansione cloud ha isolato anche
  Triestespresso Expo 2026, che la scansione locale precedente non aveva
  isolato. Una nuova lettura in sola lettura con la stessa funzione del job
  allinea identità e periodo 21–23 ottobre: non forziamo quindi la
  pubblicazione dalla prova successiva, ma monitoriamo la risposta del sito
  al prossimo ciclo.
- L'immagine e la chiave del job schedulato sono state subito rimesse ai
  valori ufficiali e rilette. La generazione del catalogo ufficiale è rimasta
  `1791864564401503` prima e dopo la prova; il servizio API non è stato
  modificato in quella fase. Nessuna verifica sul telefono è stata eseguita.
  GitHub era fermo su richiesta dell'utente. Lo stato successivo è nella
  sezione 11.

## 9. Sequenza di verifica prima di promuovere

1. Revisionare insieme la matrice di decisione delle schede e il caso zero
   valide di Villa Manin/Magazzino, mantenendo il blocco finché non esiste
   prova specifica di chiusura.
2. Completare i test locali del job, della policy log e dell'API; controllare
   il diff del ramo e la copertura Docker.
3. Account, progetto, scheduler, job, API e policy sono stati letti. La policy
   separata dei candidati è stata applicata e il filtro ha trovato un log
   reale della nuova immagine. L'utente ha ricevuto l'email corrispondente.
4. Il ciclo cloud isolato è riuscito e ha salvato 15 lotti verificati sulla
   chiave di prova; le quarantene non l'hanno fatto fallire. I test locali
   coprono il blocco di una fonte strutturalmente rotta, senza alterare un
   sito reale. Seguire il nuovo caso Triestespresso nel prossimo ciclo.
5. Verificare nell'API date, anteprime, programmi, filtro Sagre, doppioni e
   refresh dopo una nuova generazione. Ripetere sull'app e sul telefono reale
   quando il dispositivo è disponibile.
6. La distribuzione backend autorizzata è registrata nella sezione 11.
   Promuovere il ramo a `main` solo dopo i controlli automatizzati e quelli
   sul dispositivo reale richiesti da `AGENTS.md`.

## 10. Mappa dei file principali

- `backend/app/events/pilot_cloud.py`: orchestrazione, Storage, monitor e retry.
- `backend/app/events/pilot_sources.py`: registro dei 15 adapter.
- `backend/app/events/pilot_collection.py`: worker isolati e limiti di tempo.
- `backend/app/events/pilot_source_policy.py`: gate per fonte e validazione.
- `backend/app/events/pilot_catalog.py`: merge, stati, filtro e deduplica.
- `backend/app/events/pilot_http.py`: API di sola lettura.
- `backend/Dockerfile.events-pilot`: immagine del job e test di build.
- `frontend/src/services/eventsApi.js`: fetch paginato e proiezione.
- `frontend/src/services/eventsCache.js`: cache locale.
- `frontend/src/features/events/eventsDataController.js`: stato e refresh UI.
- `scripts/cloud-run-job-monitoring-policies.json`: definizioni degli allarmi.
- `scripts/sync-cloud-run-job-monitoring.ps1`: audit/applicazione delle policy.
- `scripts/audit-events-full-readonly.py`: ciclo integrale con input JSON locale
  e sostituto Storage in memoria; legge i siti ma non scrive sul cloud.

## 11. Distribuzione e verifica del 13 ottobre

- Il ramo dedicato è `codex/events-card-quarantine`, salvato su GitHub nella
  PR #46 in bozza. Il commit applicativo `efadff20` aggiunge il recupero
  della paginazione TurismoFVG; `d949f095` documenta il preflight isolato.
  La suite locale `unittest` ha superato 678 test pilot con un test saltato;
  gli 8 test del calendario filtrato e i 13 del worker TurismoFVG sono verdi.
  I tre check CI della PR (`backend`, `frontend`, `hosting-preview-tool`)
  sono verdi al commit applicativo `efadff20`. Sul successivo commit solo
  Markdown `bdf61821`, GitHub ha marcato tutti e tre come falliti prima di
  iniziare i passi: l'annotazione dice che recenti pagamenti dell'account
  non sono riusciti oppure che va aumentato il limite di spesa. Non è un
  fallimento dei test, ma lo stato CI dell'ultimo commit è rosso. Dopo la
  risoluzione del problema dell'account bisogna rieseguire i check prima
  di valutare il merge.
- L'API Eventi `meteofriul-events` è stata aggiornata per prima al digest
  `sha256:3d6afce26fd089161047fc32b9d088365644a50328ccfeb4499b0066fddf3c6e`.
  Revisione `meteofriul-events-00012-pfn`, traffico 100%, `/health` HTTP 200.
  Comando `gunicorn`, account reader, variabili, chiave Storage e limiti sono
  rimasti invariati. Questo codice legge i lotti `partial` di tutte le fonti.
- Il primo ciclo ufficiale con quel digest, esecuzione
  `meteofriul-events-refresh-blhzp`, è fallito il 13 ottobre alle 09:27:52 UTC.
  Il catalogo è stato comunque scritto alla generazione `1791883668323469`:
  13 fonti `fresh`, Pordenone Pensa `partial`, TurismoFVG `stale`. Il campo
  `last_attempt_error_detail` di TurismoFVG indica un conteggio cambiato
  durante la lettura delle pagine: pagina 58, `477/476` risultati dichiarati,
  `8/8` schede sulla pagina. Non si trattava di una scheda non conforme.
- `fetch_year_resilient` era già implementata ma non era il percorso della
  raccolta a 45 giorni. Il commit `efadff20` la usa come percorso principale
  e, quando il totale cambia, riprova con finestre datate da al massimo 128
  risultati prima di riconciliare il loro insieme con la finestra completa.
  Se manca una scheda, cambiano le identità o non esiste un inventario finale
  stabile, il controllo continua a fallire. Cloud Build
  `2020ccd4-6d87-464f-91fe-e430e94d0093` è riuscita, inclusi 394 test
  pilot e 7 test Palazzo Attems nel Dockerfile, e ha prodotto il digest
  `sha256:926f97d9a45df8f8845d89aaa4ab9c23c51893fc39f095a01e23f7ec102c89c4`.
- Il job `meteofriul-events-refresh` usa ora quest'ultimo digest. Chiave
  `pilot/events/v1/catalog.json`, account writer, 1 task, 0 retry, timeout
  900 secondi e Scheduler `0 4 * * *` UTC sono invariati. Il secondo ciclo
  ufficiale `meteofriul-events-refresh-nh5p9` è riuscito in 9 minuti e
  10 secondi, terminando alle 09:48:46 UTC. La generazione Storage è
  `1791884923752339`, con 15 fonti `fresh`/`partial` e 1.540 schede grezze.
  TurismoFVG è `partial` con 1.167 schede e 5 URL in revisione; Pordenone
  Pensa è `partial` con zero schede e 1 URL in revisione. La revisione delle
  5 URL TurismoFVG resta un lavoro distinto: le altre schede sono pubblicate.
- L'API live legge lo snapshot del secondo ciclo e risponde `ready`.
  Riporta TurismoFVG e Pordenone Pensa come `partial`, e lo stato generale
  `degraded` per la quarantena delle singole voci. Nella query per Caneva
  appare una sola `Sagra del Rosario`, categoria `sagra`; a Trieste appare
  una sola scheda `Barcolana 2026`. I monitor Palazzo Attems e GiroFVG sono
  `review_required`, con allarme email separato; il monitor annuale
  TurismoFVG è `checked` e completo. L'utente ha ricevuto l'email dei
  candidati prodotta dal preflight riuscito: non era un errore del job.
- L'utente non può collegare ora il dispositivo. La verifica dell'app reale
  resta aperta; per questo la PR #46 rimane in bozza e il ramo non viene
  promosso a `main`. La distribuzione backend è già operativa, autorizzata
  separatamente dalla promozione del codice e da un'eventuale AAB Play.

## 12. Verifica locale e telefono, 13 ottobre

Dopo la distribuzione descritta nella sezione 11, `main` è stato integrato nel ramo Eventi al commit `49c4b4ce`, senza conflitti. Sul codice combinato sono passati 1.782 test backend (uno saltato) e la compilazione Python, 4.790 test frontend (13 saltati), nove test release guard, lint, build, sincronizzazione Capacitor e i 20 controlli del job Windows `hosting-preview-tool`. La CI GitHub dell'ultimo commit resta non avviata per il limite dell'account; questo esito locale non ne cambia lo stato.

La prova con l'app TEST già installata è documentata in [EVENTI_VERIFICA_TELEFONO_2026-10-13.md](EVENTI_VERIFICA_TELEFONO_2026-10-13.md). Il controllo sul telefono del backend Eventi è positivo. Il ramo Eventi non cambia frontend o Android rispetto all'attuale `main`; le modifiche Android entrate su `main` appartengono a un lavoro separato, validato con la deroga agli emulatori accettata dal proprietario. Non è stata generata o installata una nuova APK.
## 13. Promozione solo locale

Dopo i controlli integrati della sezione 12 e la verifica sull'app TEST, il
worktree di `main` è stato avanzato in fast-forward al commit `efc22d4d`.
Questa promozione riguarda esclusivamente il repository locale: al momento
`origin/main` è ancora a `d8a54e17`. Non è stato eseguito alcun push, merge
GitHub, workflow Actions o nuovo deployment cloud. Il ramo
`codex/events-card-quarantine` resta conservato. Quando i runner GitHub
torneranno disponibili, rileggere il delta fra `origin/main` e `main` locale
prima di sincronizzarlo, perché altri workstream potrebbero aver avanzato il
remote nel frattempo.
