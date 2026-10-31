# ICON: distribuzione del recupero automatico — 31 ottobre 2026

Il proprietario ha autorizzato la distribuzione del recupero automatico ICON. Sono aggiornati soltanto i produttori FVG/nazionale e i loro due Scheduler esistenti. La verifica finale è del 2026-10-31T21:37:50.901803+00:00.

## Provenienza e preparazione

- Sorgente distribuita: `04ea00b2498d9cf37b7352bc7dfcc61da61d19ba`, merge della [PR 38](https://github.com/meteofriul/meteofriul-app/pull/38).
- [CI di main 41227684967](https://github.com/meteofriul/meteofriul-app/actions/runs/41227684967): tutti i tre job riusciti. Regressione locale finale: 282 test PASS, registrati nella [ricevuta precedente](ICON_VERIFICATION_REUSE_20261031.md).
- Tutti i layer delle immagini precedenti sono stati letti e autenticati. Confrontati sorgenti e asset con il commit approvato; il limite FVG di 64 MiB è conservato e gli asset nazionali canonici sono identici.
- Le immagini derivano dai digest effettivamente in uso: nessuna installazione di dipendenze. Verificati dentro ogni immagine Python, versioni dei pacchetti, utente non privilegiato e hash di tutti i file inclusi (177 FVG, 175 nazionali). I due alberi applicativi sono sostituiti integralmente, evitando residui di vecchi moduli.
- Il confronto giustifica l’esclusione di vecchi verifier/provenance, fixture e package del monitor: queste immagini aggiornano esclusivamente i job ICON; non sostituiscono monitor o servizi HTTP.

## Immagini e collaudi

### FVG

- Immagine precedente: `europe-west1-docker.pkg.dev/meteo-friul/meteofriul/weather-worker@sha256:53c8709e74e75b350b1f502149bda489eb99b6e2c30eb6b47c46c4f689e78d48`.
- Immagine distribuita: `europe-west1-docker.pkg.dev/meteo-friul/meteofriul/weather-worker@sha256:c0503d339272a0f2ba9d11843990d8d4e4cfa0c20d2b2160494cb22bddbf0fd8`.
- Cloud Build: `4c05d75d-f95a-42a6-b313-5b0482b387c0`, tutti gli step PASS, test senza rete: Ran 482 tests in 280.645s; Ran 2 tests in 16.700s.
- Ambiente conservato: Python `3.13.16`, SDK Storage `3.13.1`; inventario completo dei pacchetti confrontato.
- SHA-256 archivio sorgente: `8b4a258cff744c3943c17a120853708a1d4200f91fcbc4b1892ad1eb6b20ee4d`; configurazione build: `38fbe6016ef99215fcf60d8aa9e7ce8f73e07e83813855ca60de1902c1470586`.
- SHA-256 manifesto dei file: `41f5fe2d231b908a75ad257ebbe56396f7301d9c14b42038188c8797bcff4c44`.
- Esecuzione controllata: `meteofriul-icon-gpfkd`, riuscita in 118.226 s, retry 0.
- Esiti strutturati: `no_op/run_already_published`.
- Stato del recupero `completed`, ciclo `20261031T120000Z`; puntatore pubblico e generazione `1793461260434648` invariati. Nessuna fase di acquisizione GRIB nei log completi dell’esecuzione.
- Lettura pubblica indipendente PASS: 5 richieste, 239043 byte JSON. Manifest e payload Udine/Pordenone/Trieste. La verifica completa del prodotto è svolta dal worker; questo controllo HTTP è campionato.

### Nazionale

- Immagine precedente: `europe-west1-docker.pkg.dev/meteo-friul/meteofriul/national-weather@sha256:580b3841913331d267d50f511c90e56693e257dad97662f6e622bd292da67104`.
- Immagine distribuita: `europe-west1-docker.pkg.dev/meteo-friul/meteofriul/national-weather@sha256:d062db94eedf2337ef1886f8f2a80c9babc0901c8c78bc7385c6930fa730eb26`.
- Cloud Build: `8c69937b-5527-4fee-a431-3239394c758c`, tutti gli step PASS, test senza rete: Ran 112 tests in 8.457s.
- Ambiente conservato: Python `3.13.15`, SDK Storage `3.13.1`; inventario completo dei pacchetti confrontato.
- SHA-256 archivio sorgente: `a5b26a4c66c1b5de922452620af3bb75afa1c3ade5a7ed3e3075e3339cfd515f`; configurazione build: `0c0ba267d01055a837a88905b2e279ab5d92880d71fb22e828e2b0e51d2b7f2f`.
- SHA-256 manifesto dei file: `ae698d084e47549b3ded8a3e76553e16e27077d99c80256570ec23c9ffe07032`.
- Esecuzione controllata: `meteofriul-national-icon-cdrqk`, riuscita in 173.948 s, retry 0.
- Esiti strutturati: `published/publication_committed`.
- Stato del recupero `completed`, ciclo `20261031T120000Z`; puntatore pubblico e generazione `1793461298011191` invariati. Nessuna fase di acquisizione GRIB nei log completi dell’esecuzione.
- Lettura pubblica indipendente PASS: 6 richieste, 1491443 byte JSON. Manifest, indice e blocchi Roma/Milano/Napoli. La verifica completa del prodotto è svolta dal worker; questo controllo HTTP è campionato.

## Configurazione effettiva

- Progetto `meteo-friul`, regione `europe-west1`. Flag `WEATHER_ICON_AUTOMATIC_RECOVERY_ENABLED=true` sui soli due job ICON. Nel codice rimane disattivato per default.
- Cron dei due Scheduler: `0 6,7,8,10,18,19,20,22 * * *`, fuso `Etc/UTC`: base alle 06/18 UTC, recuperi dopo 1, 2 e 4 ore. In ora italiana invernale: 07/08/09/11 e 19/20/21/23; il fuso operativo resta UTC anche in estate.
- Otto avvii programmati per prodotto al giorno, invece di due: dodici avvii giornalieri aggiuntivi complessivi, nessun nuovo job o Scheduler. L’inventario osservato passa da 120 a 132 avvii programmati/giorno. La spesa effettiva successiva al deploy resta da misurare; i tempi dei collaudi non sono una previsione dei cicli con acquisizione.
- Risorse, timeout, retry Cloud Run, comandi/argomenti, identità, bucket e namespace preservati. Conservato in particolare l’override `python national_cloud_worker.py` del job nazionale.
- Target, autenticazione, retry e deadline degli Scheduler preservati; modificato soltanto il campo `schedule`.
- IAM del bucket di stato e policy di allarme invariati. I permessi già presenti erano sufficienti. Conservata anche l’identità di compilazione esistente.
- Confronto finale PASS: 6 servizi HTTP invariati, 11 altri template di job nella regione invariati, insieme dei job e degli Scheduler invariato. Gli altri Scheduler mantengono la loro configurazione.

## Passaggio di stato, limiti e ripristino

Prima di ogni aggiornamento è stata accertata l’assenza di esecuzioni legacy attive. Il FVG ha superato il collaudo prima dell’aggiornamento nazionale; gli orari aggiuntivi di ciascun prodotto sono stati attivati soltanto dopo verifica del worker e lettura pubblica.

I collaudi hanno adottato i checkpoint completi già esistenti del ciclo 31 ottobre, ore 12 UTC, autenticato i contenuti e completato la rilettura senza cambiare i puntatori pubblici. Per FVG il manifest del checkpoint arricchito e quello pubblico hanno hash diversi per la proiezione dei sidecar: il controllo della proiezione e del fingerprint originale è riuscito. Nessuna migrazione manuale.

**Non è ancora osservato online un nuovo ciclo con fonte inizialmente assente e successivo recupero**, né il percorso reale di concorrenza del record di polling. Questi casi sono coperti dai test, ma il collaudo distribuito di oggi dimostra adozione legacy, scritture dello stato e verifica dei dati. Il monitor di freschezza esistente rimane il riferimento; non viene creato un monitor duplicato. Gli esiti pending/error restano soggetti alle policy esistenti, che questo lavoro non modifica.

Letti anche i due rapporti persistenti del monitor: ultimo slot disponibile `2026-10-31T21:10:00Z`, `check_state=0`, nessuna causa critica per entrambi. Questo slot precede il deploy: non viene presentato come una verifica automatica successiva al passaggio. Nessun monitor avviato manualmente; il primo rapporto post-deploy resta da osservare.

Preparato un ripristino circoscritto: accertare quiescenza, riportare i due cron a `0 6,18 * * *`, ripristinare i precedenti digest immutabili e rimuovere il solo flag. Claim, checkpoint, stato di recupero e dati validi si conservano. Nessun rollback eseguito.

Nessuna build di distribuzione o pubblicazione Web/Android, nessuna installazione su telefono e nessuna attivazione Mercati/pannello. Le prove backend non estendono le qualificazioni Safari/iPhone o dispositivo.

## Tracce locali

Le risposte cloud complete sono conservate localmente in `.tmp/icon-deploy-20261031/` e non versionate, per evitare di pubblicare configurazioni e identificativi non necessari. Identità degli artefatti, build ed esecuzioni sono riportate sopra. SHA-256 delle ricevute:

- `base-code-review.json`: `0592fbc51c9c393321ee344ad8f435f0393b6c4aba044ee8f9b04974fadbab44`.
- `rollout-preflight.json`: `af7729e5ee96ac354b3852dd1f8fc373318df223b7ceed5e1a2ec43e5b0dd1d0`.
- `candidate-fvg.json`: `19f28ca8592cf2a2225b997968914f5db20029d3843bf966b95e6d6d2c9dc2dd`.
- `candidate-national.json`: `a93e9a4972d6643d63a97a99ce3ea43d2fe2a237d6e878b5f764d1686a28b498`.
- `canary-verified-fvg.json`: `f6366def3a136a3b14724452d9cced2f46694c98651dbc7e9e084ac13cdff68d`.
- `canary-verified-national.json`: `e91203209b6131e72284f6531f86638747b7ed8b0c9964e505088c92262772dd`.
- `public-readback-fvg.json`: `3876944fb425feb9f1d9f7c370154f99113e1f552fcfd83b29eae4dfad8ce1b1`.
- `public-readback-national.json`: `ccb032030ff7b078c2065512af09fa4e9e25d41068bc7fadf461f73a64d30657`.
- `final-audit.json`: `607d4b08b770ad08a3209f668015d36beb6c4d295ffd2415eac6bae6d7a80e26`.
