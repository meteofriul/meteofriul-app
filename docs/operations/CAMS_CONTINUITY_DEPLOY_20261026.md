# CAMS: deploy della continuità e policy — 26 ottobre 2026

**Distribuito e riletto; recupero sulla nuova corsa ancora da verificare.**
Questo intervento riguarda soltanto il job `meteofriul-cams` e la policy
`cams-failures`. Nessuna nuova AAB, installazione, pubblicazione Web,
esecuzione o notifica manuale. Sponsor disattivati. Il follow-up Eventi
eliminato dal proprietario non è stato ricreato; nessuna nuova automazione.

## Sorgenti e controlli

- [PR 32](https://github.com/meteofriul/meteofriul-app/pull/32), merge
  `026d5ca064fdbeebb30403b458929cd6ea1e79c0`; CI PR `40309156216` e main `40309821859` superate
  in tutti e tre i job, senza esecuzioni CI duplicate.
- 191 casi Python locali distinti e contratti PowerShell della policy:
  PASS. Controllo workspace canonico e diff: PASS.
- Cloud Build `5e8d4abe-12cf-4871-8f6a-3e205595454f`: SUCCESS. Archivio dell'esatto commit main,
  immagine con etichetta di provenienza e suite del file di build versionato
  eseguita nel container Linux con `--network=none`: **433 test PASS**,
  209,468 secondi, nessun errore o fallimento.
- Immagine candidata: `europe-west1-docker.pkg.dev/meteo-friul/meteofriul/weather-worker@sha256:572ea2889b37009b746e746402816a2fd1e6966db15c8d642e5105ccd5b0ce8e`.
- Riepilogo pubblico ed hash delle evidenze:
  [ricevuta](evidence/CAMS_CONTINUITY_DEPLOY_20261026.json).

## Cambiamento effettivo

Aggiornati soltanto immagine del job e `WEATHER_CAMS_CONTINUITY_ENABLED=1`.
Restano invariati timeout, risorse, identità, segreti, destinazioni e scheduler
`0 9,10,11,15,20 * * *` in UTC; UV resta alle 15 e 20 UTC.
Confronto prima/dopo: 12 altri job e
6 servizi invariati.

La policy mantiene due fallimenti in 8 ore e gli stessi destinatari. Cambiano
solo titolo della condizione, istruzioni e `notificationPrompts=[OPENED]`:
la chiusura della finestra non annuncia un recupero dei dati.
Le altre 22 policy sono rimaste invariate.
Non è stato attivato un nuovo monitor permanente delle 11:30 UTC: quello
resta un controllo di recupero proposto, distinto dalla policy sui fallimenti.

## Compatibilità e letture pubbliche

Il reader HTTP già attivo è quello attestato dal deploy del 25 ottobre,
compatibile con `continuity.json`: non è stato aggiornato. Identità dell'immagine,
traffico al 100% e file del lettore verificati rispetto ai sorgenti attestati.

Prima e dopo il deploy: famiglia `20261026T000000Z`, entrambi i manifest
con 215 comuni, binding e hash validi. Controllati quattro payload reali
(aria e pollini di Udine e Pordenone), campione orario corrente e CORS per
Android (`https://localhost`) e Web (`https://meteofriul.app`).
Questo campione non equivale alla rilettura HTTP di tutti i 430 documenti,
né a una prova visiva su telefono o iPhone.

La famiglia odierna conserva il contratto originale: **nessun documento
di continuità aggiunto retroattivamente**. Scade il 27 ottobre alle 06 UTC
(07 italiane); per essa può ancora esserci un vuoto prima dell'acquisizione
successiva. La prima nuova famiglia, attesa dal ciclo del 27 ottobre, potrà
pubblicare il grant a 36 ore. Da quel momento solo i client compatibili e
con campione orario valido useranno tale estensione. I client precedenti
mantengono 30 ore, senza modifiche ai byte v1.

## Rollback compatibile, pronto ma non eseguito

Digest precedente: `europe-west1-docker.pkg.dev/meteo-friul/meteofriul/weather-worker@sha256:40f64c406144128b3f2768b8eaaaf82c43a0c2cb03855ee45276ee76d4d0d795`. Salvati configurazione del job,
policy completa, patch inversa e comando di ripristino che rimuove il flag.
Il codice estratto dai layer dell'immagine precedente, verificati per digest,
ha letto offline una famiglia sintetica nuova con sidecar: verifica riuscita
e nessun oggetto modificato. Il reader HTTP compatibile resta attivo.
Il rollback torna a nuove pubblicazioni senza grant; non cancella i documenti
già pubblicati e non esegue il job. Non è automatico.

## Verifica ordinaria preparata, ancora aperta

1. Prima corsa dopo deploy: **26 ottobre, 12:00 Europe/Rome**
   (11:00 UTC), da leggere almeno 20 minuti dopo.
   Può verificare il worker nuovo sulla famiglia odierna e la diagnostica;
   `legacy_no_grant` è atteso, non prova della continuità nuova.
2. Prima famiglia nuova: **27 ottobre, 10:00 Europe/Rome** (09 UTC).
   Se il fornitore non è pronto, distinguere `source_pending` dai guasti e
   leggere le successive corse ordinarie delle 10/11 UTC separatamente,
   senza presentarle come la corsa delle 09. Controllo di recupero dei dati
   proposto alle 11:30 UTC; nessuna esecuzione manuale.
3. Verificare origine Scheduler, digest, esiti separati aria/pollini/UV,
   `cams_family_verified`, Storage e tutti i 215+215 payload HTTP, grant
   legato a corsa/release/hash, scadenze e ora nativa corrente.
4. Dichiarare se il recupero TLS non viene esercitato: un successo al primo
   tentativo prova la lettura, non il retry in produzione. Un job verde da
   solo non dimostra disponibilità dei dati.

Script locali nella radice canonica `.tmp/cams-continuity-deploy-20261026/`:
`verify_ordinary.py first` e `verify_ordinary.py new-family`, sola lettura;
`verify_http.py --name <nome> --all --require-new` completa il confronto HTTP.
Gli script non sono stati usati per anticipare corse future.

## Stato applicativo

Questa modifica backend non cambia il frontend della candidata 0.1.15 /
300038, già compatibile, né gli artefatti salvati sul ramo release. Play interno
e produzione restano separati. Aggiornamento AAB e pubblicazione Web non fanno
parte di questo deploy.
