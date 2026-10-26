# CAMS: continuità e rilettura — 26 ottobre 2026

Stato: **preparazione locale, non distribuita** sul ramo
`codex/cams-continuity-readback`, da main `c2b2cfe1`.
Correzione e test salvati nel commit locale `ae41628b`; policy e documentazione
sono salvate separatamente nello stesso ramo.
Riguarda soltanto CAMS e la policy `cams-failures`. Non modifica ICON, Eventi,
sintesi, orari, destinatari, sponsor o interfaccia. La verifica Eventi del
27 ottobre resta separata e attiva. Nessuna acquisizione, esecuzione di job,
notifica manuale, installazione, AAB, push o deploy in questa attività.

## Evidenza osservata, non ipotesi

Rilettura del 26 ottobre alle **09:58:39 UTC**:

- Scheduler CAMS `0 9,10,11,15,20 * * *`, `Etc/UTC`.
- Esecuzione ordinaria `meteofriul-cams-dhh72`, partita alle 09:00 UTC,
  terminata con errore alle 09:08:54 UTC.
- Famiglia pubblica **20261026T000000Z**, release e due manifest con hash
  corrispondenti, ciascuno con 215 descrittori comunali.
- Entrambi i componenti hanno `fresh_until=2026-10-27T00:00:00Z` e
  `usable_until=2026-10-27T06:00:00Z`. `continuity.json` restituisce 404.
- Esito persistito di aria/pollini: `manual_review`,
  `stage=stored_payload_verification`, `operation=download`, causa `SSLError`,
  `retryable=false`. UV escluso correttamente da questo slot.

La pubblicazione e il suo controllo sono quindi esiti diversi. Questa lettura
prova la presenza della famiglia e dei manifest, **non** la verifica di tutti
i 430 payload attraverso HTTP né una prova sul telefono.
I vecchi log non conservano la causa TLS interna: non consentono di distinguere
un'interruzione della connessione da un errore del certificato. Non attribuiamo
retroattivamente una causa più precisa.

Evidenze private conservate nella radice canonica:
`.tmp/cams-continuity-readback-20261026/read-only-20261026T095737Z/`.
Contengono configurazione, esecuzione, log, release, manifest e `summary.json`.
La policy live è stata confrontata in modalità **Audit**: `drifted` rispetto
alla candidata locale, exit 2 atteso; nessuna applicazione.

## Correzione preparata

1. **Continuità a 36 ore:** `WEATHER_CAMS_CONTINUITY_ENABLED=1` nella
   configurazione candidata. Riusa il contratto già presente, senza alterare
   manifest o payload v1. Il documento aggiuntivo è legato alla release
   immutabile e scritto prima di esporre una nuova famiglia. Una famiglia già
   attiva senza documento non viene prolungata retroattivamente.
   `continuity_status` distingue `verified` da `legacy_no_grant`.
2. **Rilettura locale al guasto:** il solo worker CAMS usa `CamsObjectStore`.
   Due tentativi supplementari totali, condivisi fra i suoi store, con pause
   di 1 e 2 secondi e rispetto del budget CAMS esistente. Solo letture
   idempotenti; download sulla stessa generazione, SDK ancora senza retry.
   Upload e CAS non vengono ripetuti da questo adattatore. Non vengono ripetute
   automaticamente le acquisizioni del fornitore.
3. **TLS verificato:** un EOF TLS tipizzato può essere ritentato; certificato
   invalido o TLS non classificabile restano bloccanti. La classificazione
   usa tipi e codici controllati, senza registrare testo delle eccezioni,
   URL o credenziali. Non disattiva la verifica TLS.
   Il motivo e la possibilità di riprovare sopravvivono anche al passaggio
   dal report di acquisizione al worker, senza ripetere un POST ambiguo.
4. **Esiti leggibili:** `cams_family_verified` compare soltanto dopo la
   verifica Storage e HTTP. `cams_component_unverified` identifica invece
   aria, pollini o UV non verificati, con fase e motivo, dopo il recupero
   limitato. L'exit code di errore resta invariato.
5. **Policy:** resta la soglia di due fallimenti in otto ore, con gli stessi
   destinatari. Testo adeguato ai cinque slot effettivi; proposta
   `notificationPrompts=OPENED`, perché l'uscita dei fallimenti dalla finestra
   non dimostra il recupero dei dati. Nessuna nuova policy duplicata.

Le app compatibili con `cams_continuity_36h_v1` possono usare il campione
orario valido fino a 36 ore. La freschezza resta 24 ore, il campione corrente
deve rispettare il limite di 60 minuti e le revoche restano vincolanti.
Le app precedenti continuano con il contratto a 30 ore: compatibili, ma senza
il beneficio della continuità. Non basta cambiare il timestamp della cache.
Il frontend della candidata 0.1.15 / 300038 supporta già questo contratto;
questa correzione backend non richiede di rigenerare quel pacchetto.

## Cadenza del controllo CAMS

Il vuoto attuale è strutturale: la corsa precedente raggiunge 30 ore alle
06 UTC, mentre il primo tentativo del giorno parte alle 09 UTC. Con il
documento a 36 ore il limite diventa le 12 UTC, senza presentare i dati come
una nuova acquisizione.

| Passaggio | UTC | Italia inverno | Italia estate |
| --- | --- | --- | --- |
| Prima acquisizione ordinaria | 09:00 | 10:00 | 11:00 |
| Secondo tentativo | 10:00 | 11:00 | 12:00 |
| Recupero mattutino | 11:00 | 12:00 | 13:00 |
| Controllo dati proposto | **11:30** | **12:30** | **13:30** |
| Fine continuità della corsa precedente | 12:00 | 13:00 | 14:00 |

Il controllo delle 11:30 lascia i 20 minuti del timeout del job delle 11 e
altri 10 minuti di margine; resta mezz'ora prima della scadenza precedente.
Lo slot resta UTC anche al cambio d'ora. I passaggi delle 15 e 20 e la
finestra UV non cambiano.

**Questo è il piano del controllo di recupero, non un nuovo monitor cloud
già attivo.** L'attuale policy conta errori di esecuzione: non rileva da sola
un job mai avviato, né certifica la freschezza. Un eventuale controllo
permanente di pubblicazione va collegato separatamente al solo servizio CAMS;
non va inserito nel monitor ICON o nelle sintesi. Nessuna automazione esistente
è stata cambiata in questa preparazione.

## Ordine del passaggio, ancora da eseguire

1. Revisione, PR/CI e promozione della correzione. Costruire e provare offline
   la sola immagine candidata per il job CAMS; acquisire digest e configurazione
   live di rollback prima di qualsiasi modifica.
2. Attestare che il reader HTTP già distribuito supporti il documento
   `continuity.json` e i client v1. Il 404 su una corsa senza documento non
   prova da solo tale supporto. Il codice compatibile esiste già; non
   aggiornare il servizio HTTP per principio, ma confrontarne l'immagine.
3. Aggiornare solo `meteofriul-cams` e il flag della continuità. Conservare
   altri parametri, segreti, identità e scheduler. Non aggiungere un documento
   alle corse attive e non avviare una corsa manuale: il primo risultato utile
   deve appartenere a una **nuova corsa ordinaria**.
4. Applicare e rileggere solo `cams-failures`, con destinatari invariati.
   Conservare anche la policy precedente per il rollback.
5. Dopo la finestra mattutina verificare Scheduler, digest, esecuzione,
   `component_outcomes`, due manifest, tutti i comuni e nuovo documento
   legato a corsa/hash. Distinguere verifica dei vecchi client, dei client
   con continuità e del campione dell'ora corrente. Non basta un job verde.
6. Se un tentativo non viene esercitato, dichiararlo: successo al primo
   tentativo non prova il percorso di recupero TLS in produzione.

Rollback: ripristino del digest CAMS e dei parametri salvati, senza cancellare
famiglie o documenti immutabili. Il lettore deve restare compatibile con i
documenti già pubblicati. Tornare a nuove pubblicazioni senza continuità
reintroduce il limite a 30 ore, non autorizza a riscrivere gli orari.
Nessun rollback automatico.

## Verifiche locali

- 183 test mirati: PASS (store CAMS, TLS, worker, readback, disponibilità,
  metadati, configurazione di produzione, diagnostica, store generico e
  continuità del worker, acquisizione simulata e riconciliazione).
- 11 test della continuità: PASS, di cui 3 già compresi nei 183;
  byte v1 identici, pubblicazione atomica, binding, revoca, documento corrotto
  e divieto di estensione retroattiva. Totale: **191 casi Python distinti**.
- Prove iniziali: quattro aspettative di mock/log da aggiornare, poi corrette;
  l'estensione alla suite acquisizione ha trovato il client ECMWF assente nel
  Python generale. Prova finale eseguita con `ecmwf-datastores-client==0.5.3`
  in un venv temporaneo isolato (Python 3.13), senza installazioni sul telefono
  o modifiche alle dipendenze della release. La futura immagine Linux richiede
  comunque i propri test offline prima del deploy.
- Contratti PowerShell delle policy: PASS; soglia CAMS invariata, sola notifica
  OPENED e rilevamento di una riattivazione CLOSED indesiderata.
- Nessuna prova di recupero del codice candidato nel cloud: manca il deploy.

Log locali: `.tmp/cams-continuity-readback-20261026/local-tests-pinned-client.txt`,
`continuity-final.txt` e `policy-audit-private.txt` nella radice canonica. Gli artefatti Android/Web,
le chiavi private e i lavori delle altre chat non sono stati modificati.
