# Meteo autonomo - decisioni approvate e punto di ripartenza

Data: 4 settembre 2026

## Scopo

Questo documento fissa le decisioni approvate per portare il pilot locale
ICON-2I/CAMS verso un ambiente operativo reale. Non autorizza deploy, scheduler,
creazione di risorse cloud o modifiche dell'app ufficiale. OSMER e allerte
ufficiali restano fuori dal perimetro tecnico della nuova pipeline.

Le fasi sono checkpoint di sviluppo locale, non rilasci intermedi. Il passaggio
pubblico, se autorizzato in seguito, avverra con un solo aggiornamento completo.

## Responsabilita dei provider

| Dominio | Fonte primaria | Regola |
| --- | --- | --- |
| Condizioni e previsioni | ICON-2I | Hero, dati numerici e orizzonte dichiarato di 48 ore. Sono previsioni di modello, non osservazioni di stazione. |
| Pollini e qualita dell'aria | CAMS Europe | Circuito, run, manifest, cache e stato indipendenti da ICON. |
| Bollettino ufficiale | OSMER | Circuito esistente invariato. |
| Allerte ufficiali | Fonti ufficiali gia in uso | Circuito, cache, scheduler e presentazione invariati. |
| Fallback previsionale | Open-Meteo | Attivabile soltanto con decisione e configurazione esplicita dello sviluppatore. Mai automatico per errore, rete, dato stale o indisponibilita ICON. |

Il passaggio manuale a Open-Meteo sostituisce atomicamente l'intero dominio
previsionale. Non e ammesso comporre silenziosamente temperatura ICON con
condizione, icona o altri campi Open-Meteo. La provenienza resta sempre inclusa
nel contratto e disponibile nella UI informativa.

La policy frontend gia presente soddisfa il vincolo di assenza di fallback
automatico. Prima della nuova release andra aggiunto un gate di build che renda
obbligatoria la configurazione del provider; il default di compatibilita
dell'app attuale non deve diventare il default della nuova versione. Un eventuale
kill switch remoto firmato e versionato e una decisione successiva, non un
prerequisito del primo ambiente locale.

## Contratto temporale

Ogni prodotto versionato conserva almeno:

- `schema_version`;
- `provider` e versione del modello;
- `source_run_id` e `run_at`, cioe la corsa sorgente;
- `generated_at`, cioe quando il prodotto e stato elaborato;
- `valid_from`, `valid_to` e `valid_at` per gli istanti previsti;
- `fresh_until` e `usable_until` distinti;
- stato esplicito `fresh`, `stale`, `unavailable` o equivalente;
- identita ISTAT, catalogo, unita, hash e provenienza.

Questi metadati non devono affollare la Home. Servono al client per scegliere
l'ora corretta, non ringiovanire un vecchio run dopo averlo risalvato, mantenere
l'ultimo prodotto valido e mostrare uno stato discreto quando il dato e stale.

## Cache e composizione client

La cache e condivisa come infrastruttura applicativa, ma separata per dominio:

- slice `forecast` per ICON oppure, solo dopo override manuale, Open-Meteo;
- slice `environment` per CAMS;
- cache editoriali di Scopri indipendenti dai dati meteo;
- cache OSMER e allerte invariate.

Home e la futura sezione Meteo leggono lo stesso store per Comune. Un cambio di
tab non deve produrre un nuovo download durante la finestra di verifica. ICON e
CAMS conservano run, TTL, ultimo dato valido ed errori indipendenti: un problema
CAMS non oscura ICON e un problema ICON non cancella CAMS ancora utilizzabile.

Gli oggetti immutabili per run hanno cache lunga; i puntatori `latest` hanno
validazione breve. ICON conserva il proprio puntatore di provider. Per CAMS,
invece, aria e pollini vengono preparati come due collezioni immutabili e sono
resi visibili soltanto da un'unica release di famiglia e dal solo puntatore
`weather/v1/families/cams/latest.json`. Il reader verifica release, entrambi i
manifest e i relativi payload prima di sostituire insieme le due slice nella
cache. La composizione tra domini avviene soltanto in lettura, dopo la
validazione dei singoli prodotti.

## CAMS e Home

L'archivio di elaborazione conserva tutte le variabili CAMS acquisite. Il
prodotto inviato al dispositivo deve invece restare compatto ed evitare di
duplicare payload completo e proiezione pollini nella cache locale.

La Home mantiene la presentazione approvata: specie con la concentrazione CAMS
prevista piu alta e relativa misura, per esempio `Artemisia - 5,06 grani/m3`.
Non vengono inventati livelli sanitari `basso`, `medio` o `alto`. La posizione
della qualita dell'aria e l'eventuale dettaglio con tutte le specie saranno
decisi durante la nuova UI senza cambiare l'acquisizione.

La specie prevalente e la misura restano nella fascia bianca dei dati locali,
insieme a vento, umidita, pressione e precipitazioni: i pollini non occupano una
card autonoma. La quarta card rapida riusa invece la rubrica quotidiana
`Memoria del giorno` (`Memorie dal dì` in FUR), gia curata in Scopri, senza rete
o seconda cache. Non mostra piu il profilo del Comune: titolo, testo, categoria
e data cambiano una volta al giorno e il tap apre direttamente la stessa scheda
di Scopri tramite il suo riferimento stabile.

Nella Home implementata, subito dopo la fascia delle metriche locali resta uno
slot stabile con una card bianca. In condizioni ordinarie contiene soltanto la
sintesi ufficiale OSMER. Quando e valida un'allerta ufficiale, nello stesso slot
compare invece una card distinta della Protezione Civile, con livello, fenomeno
e validita espressi anche da icona e testo. Contenuti OSMER e Protezione Civile
non vengono mai mescolati nella stessa card e non sono mostrati insieme nello
stesso slot.

Una futura funzione premium potra dare priorita alle specie selezionate
dall'utente e offrire notifiche personalizzate. Le preferenze allergiche dovranno
restare sul dispositivo per impostazione predefinita e non trasformare una
concentrazione prevista in consiglio medico. Allerte ufficiali e informazioni
ambientali di base non saranno subordinate alla funzione premium.

## Navigazione e direzione grafica successive

La navigazione target e:

```text
Home | Meteo | Eventi | Scopri
```

`Meteo` conterra tre viste interne:

- `Previsioni`: riepilogo attuale compatto e orientato ai dati, evoluzione fino
  a 48 ore, quindi precipitazioni, vento e altri dettagli. La scena illustrata
  con l'aquila resta esclusiva della Home e non viene duplicata qui;
- `Bollettino`: contenuto ufficiale OSMER;
- `Live`: radar, webcam, azione Segnala e consultazione delle segnalazioni della comunita.

Le segnalazioni della comunita restano distinte dalle allerte ufficiali. Le
allerte attive non avranno una fascia globale sotto l'intestazione. `Eventi` e
`Scopri` non mostrano pannelli di allerta. La gestione oggi implementata riguarda
la sola Home: la card Protezione Civile sostituisce la sintesi OSMER nello slot
bianco stabile descritto sopra, mantenendo i due contenuti distinti.

Nella vista `Bollettino` il dettaglio completo e separato della Protezione Civile
resta gia disponibile prima del contenuto OSMER. Per la futura tab principale
`Meteo` resta da valutare soltanto un badge o richiamo discreto che conduca a
quel dettaglio. Il badge non e ancora implementato e, in assenza di un'allerta
valida, non dovra occupare spazio; uno stato sorgente non disponibile non verra
trasformato in un falso stato verde.

La direzione grafica conserva hero illustrata e identita blu/gialla, con sfondo
azzurro chiaro e card bianche o quasi bianche. Prima del restyling completo
saranno confrontate localmente una variante bianco puro e una leggermente
azzurrata. Il PDF di riorganizzazione e una direzione, non un rendering da
replicare alla lettera.

## Stato verificato al checkpoint

Gia completato e da riusare:

- contratto `weather/v1`, catalogo ISTAT dei 215 Comuni e orizzonte ICON;
- acquisizioni reali ICON e CAMS e artefatti verificati;
- lifecycle CAMS, idempotenza e recovery su stato SQLite locale;
- pubblicazione locale ICON con oggetti immutabili, manifest, CAS, rollback e
  revoca; pubblicazione CAMS con staging immutabile e visibilita atomica di aria
  e pollini tramite una release di famiglia, inclusi revoca e rollback atomici;
- data plane locale con ETag, `304`, gzip e CORS;
- client e APK pilota con cache persistente e nessun fallback automatico;
- test accelerati di crash, richiamo e continuita sul telefono.

Ancora necessario per l'ambiente operativo reale:

- stato e checkpoint durevoli adatti ai job, senza dipendere dal filesystem del container;
- adapter R2/S3 e prove locali di `412`, `5xx`, timeout e upload parziale;
- container Linux riproducibili e dipendenze fissate;
- definizioni scheduler ICON due volte al giorno e CAMS una volta al giorno;
- richiamo state-aware, senza ripetere alla cieca il `POST` CAMS;
- single-flight prima della preparazione CAMS e rinnovo della lease durante gli
  staging lunghi, con fencing verificato prima della CAS;
- vincoli temporali tra `generated_at`, `published_at` e ora del runner, incluso
  un limite allo scarto dell'orologio per evitare che un timestamp futuro
  blocchi i run successivi;
- osservabilita di durata, memoria, byte, no-op, retry, errori e costo;
- prove agli orari naturali dei provider;
- store frontend condiviso con cache ICON/CAMS realmente indipendenti;
- adapter UI provider-neutral e prodotto CAMS aria compatto.

## Primo blocco di implementazione (completato localmente)

Questo blocco ha separato definitivamente l'esecuzione dei job dal servizio di
lettura:

1. definire due entrypoint indipendenti, uno ICON e uno CAMS;
2. introdurre un risultato comune e strutturato per `published`, `no_op`,
   `retryable_failure`, `manual_review` e `permanent_failure`;
3. collegare le primitive locali esistenti tramite porte per stato, checkpoint e
   object store, inizialmente sostituite da fake nei test;
4. garantire che il data plane resti esclusivamente read-only;
5. provare concorrenza, run precedente, crash e ripresa senza rete o cloud.

Solo dopo questo blocco verranno aggiunti gli adapter reali e preparate, ma non
attivate, le definizioni cloud. Il telefono non serve fino alla verifica client
finale.

## Checkpoint runner locali del 5 settembre 2026

Il primo blocco e ora eseguibile senza rete e senza scheduler:

- `run_icon_job.py` accetta esclusivamente payload/report ICON, object DB e
  directory degli intenti;
- `run_cams_job.py` accetta esclusivamente la directory completa delle prove
  CAMS, payload/report decodificati, state DB, object DB, directory degli
  intenti; l'identita del tentativo e un UUID interno nuovo a ogni invocazione;
- i due runner non espongono credenziali, acquisizione, `published_at` manuale,
  server o configurazioni dell'altro provider;
- entrambi applicano la sequenza `prepare -> intent -> apertura DB -> commit`:
  il materiale verificato diventa immutabile e nessun file sorgente viene
  riaperto dopo la creazione dell'intento;
- un intento JSON canonico create-only congela `published_at` prima di aprire i
  database e lega il tentativo a job, run e hash dei manifest completi;
- un richiamo identico riusa lo stesso intento; input cambiati, intenti corrotti
  o conflitti richiedono un arresto sicuro;
- ogni invocazione che raggiunge il confine CLI emette una sola riga `JobResult`
  priva di messaggi sensibili e usa gli exit code comuni `0`, `75`, `2` e `1`;
  un arresto forzato del processo o un errore di avvio dell'interprete restano,
  inevitabilmente, fuori da questa garanzia;
- i path rifiutano alias Win32, ADS, device name, UNC, symlink, junction e
  collisioni con database SQLite, WAL, SHM, journal e sentinel CAMS;
- il lease CAMS dura 15 minuti come limite per un arresto duro; ogni uscita
  gestita lo rilascia subito e un concorrente riceve il tempo residuo reale;
- stato CAMS e object store vengono aperti separatamente e chiusi in ordine
  inverso; il reader pubblico continua a possedere soltanto `head/get`.

Prove locali concluse nel checkpoint dei runner:

- ICON autorevole: prima esecuzione `published`, richiamo `no_op`, 215 Comuni,
  ETag, revisione e `published_at` invariati;
- CAMS su fixture lifecycle completa `215 x 28 x 97`: prima esecuzione
  `published` per core e pollini, richiamo `no_op`, intento condiviso;
- il prototipo iniziale ha verificato nello stesso object DB il puntatore ICON e
  i due puntatori CAMS allora indipendenti; questi ultimi non sono piu il
  percorso pubblico ammesso dopo il gate atomico descritto sotto;
- crash, lease, fencing, fingerprint, input mutati dopo la preparazione,
  collisioni dei path, confini CLI e regressioni publisher/reader sono coperti
  da test offline;
- gli artefatti temporanei della prova sono stati rimossi; gli input autorevoli
  originali sono rimasti intatti.

Questo non attiva job automatici. I due puntatori CAMS indipendenti erano validi
solo come prova del prototipo: un crash tra le due CAS avrebbe potuto rendere
visibile aria nuova con pollini precedenti.

## Checkpoint visibilita atomica CAMS del 5 settembre 2026

Il gate locale successivo elimina quella finestra di incoerenza:

- core CAMS e proiezione pollini vengono scritti come payload e manifest
  immutabili di staging, senza aggiornare i rispettivi `latest` di provider;
- una release immutabile
  `weather/v1/families/cams/runs/{source_run_id}/release.json` lega i due
  manifest, la stessa identita del run e l'hash della validazione;
- una sola CAS su `weather/v1/families/cams/latest.json` rende visibili insieme
  aria e pollini; il lifecycle CAMS non aggiorna i due `latest` legacy e
  reader/data plane ne bloccano la lettura pubblica;
- il reader autorizza soltanto release `current` e `previous`, verifica
  puntatore, release, manifest e payload e installa entrambe le fotografie CAMS
  sotto lo stesso lock; un refresh corrotto conserva la coppia valida gia in
  cache;
- un crash prima della CAS lascia soltanto oggetti immutabili invisibili e
  riutilizzabili dal richiamo; un crash dopo la CAS ma prima del checkpoint
  durevole trova la release gia visibile, la verifica e completa il lifecycle
  in modo idempotente;
- la finestra supportata e intenzionalmente limitata a `current` e `previous`.
  Revoca e rollback della famiglia CAMS usano esclusivamente il puntatore
  familiare e non possono essere simulati tramite le vecchie API dei singoli
  provider;
- quando il client deve usare insieme aria e pollini, acquisisce entrambi i
  token da una sola lettura della release familiare; due chiamate sequenziali ai
  singoli membri non costituiscono una fotografia comune;
- le cache client raw e bundle passano alla versione `v3`, rimuovono i dati
  `v2` e rifiutano un bundle CAMS privo della prova della release familiare;
- i database sperimentali pre-family non vengono migrati in-place: il pilot usa
  un nuovo object DB e un futuro job durevole dovra usare un nuovo namespace di
  stato con checkpoint `family_*`. Gli artefatti sorgente gia verificati restano
  riutilizzabili senza un nuovo download.

Verifiche concluse per questo checkpoint:

- 27 casi lifecycle CAMS e stato SQLite verificati: 24 nella suite completa
  iniziale e le 3 regressioni di concorrenza aggiunte dagli audit rieseguite
  singolarmente;
- 16 test del publisher atomico; il caso modificato nell'audit finale e stato
  inoltre rieseguito singolarmente;
- 81 test integrati per data plane HTTP, reader, pilot, schedule ed entrypoint;
- suite frontend completa: 395 file superati e 1 ignorato, 2.897 test superati
  e 3 ignorati;
- lint, build Web, controllo service worker, sintassi del launcher PowerShell e
  `git diff --check` verdi;
- pilot reale locale verificato su tutti i payload in due avvii consecutivi,
  con la seconda esecuzione idempotente.

Il lavoro resta interamente locale: nessuno scheduler o job cloud e stato
attivato, nessuna risorsa remota e stata creata e non sono stati eseguiti push,
deploy o aggiornamenti dell'app pubblica. ICON, bollettino OSMER, allerte
ufficiali e la regola Open-Meteo attivabile solo dall'operatore restano
invariati.

## Checkpoint revoca e rollback CAMS del 5 settembre 2026

La revoca non elimina ne modifica gli oggetti immutabili. L'autorita pubblica e
il campo canonico `disabled_run_ids` nel solo
`weather/v1/families/cams/latest.json`:

- revocare il run corrente `B` esegue una sola CAS, disabilita `B` e riporta
  insieme core e pollini al precedente verificato `A`;
- revocare il solo precedente lo rimuove dalla lista pubblica senza disturbare
  il corrente;
- un run disabilitato non puo essere ripubblicato, riattivato da una cache o
  recuperato tramite i vecchi `latest` dei singoli provider;
- l'elenco delle revoche e cumulativo, ordinato e privo di duplicati; revisione
  e `published_at` del puntatore non possono regredire;
- publisher, reader e client accettano un rollback soltanto con revisione
  familiare maggiore e con il run sostituito esplicitamente disabilitato;
- se il nuovo target non supera la verifica, il reader fallisce chiuso quando
  il run in cache e stato revocato. Se e stato revocato soltanto il precedente,
  puo invece mantenere il corrente gia verificato e potare il run vietato;
- le cache condivise rimuovono il run revocato per tutti i Comuni prima di
  installare o persistere il fallback verificato. La decisione di revoca viene
  propagata anche se la release di destinazione fallisce o supera il timeout,
  senza attendere una richiesta provider che ignori l'annullamento.
- le cache raw e bundle passano da `v3` a `v4` e rimuovono le versioni `v2` e
  `v3`; il ledger delle revoche impedisce il ripristino del run vietato anche
  dopo errori di quota o di accesso allo storage del dispositivo.

Il pilot usa un nuovo object DB `v5-cams-revocation`: il puntatore `v4` non
conteneva `disabled_run_ids` e viene quindi lasciato intatto, senza migrazione
ambigua e senza riscaricare gli snapshot sorgente.

Verifiche concluse per questo checkpoint:

- 57 test di publisher e reader, piu 11 subtest, tutti superati;
- 61 test integrati di data plane, server, schedule ed entrypoint, piu 40
  subtest, tutti superati;
- suite frontend completa: 395 file superati e 1 ignorato, 2.925 test superati
  e 3 ignorati;
- lint, build Web, service worker, compilazione Python, parser PowerShell,
  binding esatto del database e `git diff --check` verdi.

Solo dopo tale gate verranno sostituiti sidecar e store locali con porte
durevoli, aggiunto l'adapter R2/S3 e simulati timeout, `5xx`, `412`, upload
parziali, pubblicazioni lente e due runner simultanei. Le definizioni scheduler
resteranno non attive fino al completamento di queste verifiche.

## Checkpoint ambiente operativo locale del 5 settembre 2026

Il confine di scrittura e ora separato dal processo che distribuisce i JSON:

- `publish_snapshots_v1.py` e un writer monouso: verifica e pubblica ICON e la
  famiglia CAMS, non apre socket ed esce solo dopo avere chiuso lo store;
- `serve_published_contract_v1.py` riceve soltanto object DB e porta, apre
  SQLite in sola lettura e possiede esclusivamente le operazioni `head/get`;
- il launcher pretende prima il risultato canonico e completo del writer, poi
  avvia il reader e verifica l'intera catena HTTP. Il database predefinito
  diventa `weather-v1-objects-20260905-v6-readonly-split.sqlite3`;
- l'orologio storico del pilot e un parametro esplicito e canonico. Governa la
  validita meteorologica delle fixture ma non l'orologio reale usato dalla
  cache per decidere quando riverificare.

Il motore scheduler locale aggiunge un database SQLite dedicato, distinto da
stato CAMS e object store. Ogni `(job, slot_utc)` ha claim atomico, lease,
fencing monotono per provider, conteggio tentativi e risultato terminale
durevole. Esegue solo lo slot scaduto piu recente, non recupera una coda di run
ormai superati e pianifica un richiamo soltanto per `retryable_failure`, con
backoff e numero massimo di tentativi. Un crash lascia la lease da recuperare;
un vecchio worker non puo completare dopo che il fencing e avanzato. ICON e
CAMS hanno orari e runner indipendenti, quindi un errore di un provider non
impedisce il ciclo dell'altro.

Questa e un'implementazione locale configurabile e verificabile, non
l'attivazione dei tre orari reali: nessun processo ricorrente, Scheduler cloud,
download del provider o risorsa remota e stato avviato.

Nel client, Home e Meteo condividono per Comune e dipendenze la verifica del
bundle per una finestra breve di 60 secondi. Il cambio tab riusa subito i dati
gia verificati; la scadenza esegue una richiesta condizionale e un refresh
esplicito bypassa la finestra. Revoca CAMS, cambio Comune e cambio dipendenze
invalidano correttamente il riuso. Open-Meteo resta disponibile nel codice ma
spento nel pilot e attivabile solo con configurazione deliberata dello
sviluppatore.

Gate mirati conclusi prima della verifica end-to-end:

- 14/14 test scheduler locali, inclusi due worker, crash, fencing, retry,
  restart, abbassamento del limite tentativi e clock regressivo;
- 26/26 test per writer senza socket, publisher integrato e reader sola-lettura;
- 58/58 test frontend su runtime condiviso e adapter Home/Meteo;
- compilazione Python, parser PowerShell e `git diff --check` verdi.
