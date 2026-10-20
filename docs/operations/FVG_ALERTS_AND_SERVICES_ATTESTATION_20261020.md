# Allerte FVG e attestazioni API/job serale — 20 ottobre 2026

## Esito e perimetro

Correzione **locale** delle allerte FVG completata; attestazioni dei servizi
**già distribuiti** completate e verificate LIVE in sola lettura.
Il job delle allerte non è stato aggiornato: gli errori operativi possono
continuare fino a un deploy autorizzato. Nessuna generazione AAB, installazione,
push Git, modifica cloud, esecuzione manuale di job o invio effettuato.

Base `main`: `c45ba45d68eec19bec3103f8b832db9a31ab9b05`.
Ramo di preparazione: `codex/release-services-readiness`. In questa prima fase main non era stato promosso; vedere aggiornamento seguente.

- `c5c46675`: correzione allerte e regressioni.
- `56069cc1`: attestazioni append-only e collegamento al preflight protetto.

## Causa e correzione delle allerte

Il widget pubblico della Protezione Civile contiene l'allerta 30/2026:
A/B arancione, C gialla, D verde, dalle 00:00 del 21 ottobre alle 06:00 del
22 ottobre (Europe/Rome). Il parser precedente rifiutava più livelli positivi
con `mixed_widget_alert_levels`; la riconciliazione assumeva un livello unico.

Il candidato conserva **un solo evento**, la mappa `zone_levels` e i livelli
distinti. Il massimo regionale resta nel campo storico `level`, con
`mixed_levels=true`; non viene attribuito indistintamente alle altre zone.
Le zone verdi non entrano nell'elenco delle zone interessate.
Il testo ufficiale resta integro; la copia IT/FUR associa ciascun livello alle
sue zone, senza attribuire a tutte le zone ogni rischio trovato nel testo.
Non sono cambiate l'abilitazione o le regole territoriali degli invii.

La corroborazione richiede accordo esatto tra widget e ARPA su tutte e quattro
le zone, documento e finestra. Discordanza, zona mancante, documento o orario
diversi restano indisponibili. La firma di deduplicazione distingue anche una
redistribuzione dei livelli a massimo regionale invariato; un aggiornamento
identico non crea un nuovo episodio.

La prova persistita `runtime-v3` lega anche la mappa dei livelli. Il lettore
accetta le prove v2 precedenti senza mappe aggiunte e mantiene le regole
conservative per quelle più vecchie. **Rollback:** dopo la prima scrittura v3,
conservare un lettore compatibile v2/v3; non ripristinare alla cieca un worker
che riconosce solo v2. La procedura concreta di deploy/rollback va preparata
sull'immagine destinata alle allerte, prima di pubblicarla.

## Verifiche

- **195 test Python PASS**: parser, riconciliazione, persistenza, workflow/job,
  ARPA, preparazione/deduplicazione push. I test usano mock e non inviano.
- Fixture pubblica reale del widget conservata nei test; i pannelli PCR delle
  regressioni sono esplicitamente sintetici.
- Controllo separato il 20 ottobre alle 17:01:59 UTC: widget catturato e pagina
  pubblica ARPA letta in rete, riconciliazione **solo in memoria locale**.
  Esito attivo corroborato, A/B arancione, C gialla, D verde, nessun errore.
- Contratti PowerShell del preflight API, set writer LIVE e audit TTL: PASS.
  Lo script AAB è stato analizzato, non eseguito.
- Preflight API LIVE: PASS, health `ok`, collegamento
  `verified-image-evidence`.
- Audit push TTL LIVE: `ready=true`, zero rilievi bloccanti. Verificati
  scadenze, set delle immagini, Scheduler e prove Cloud Build. È una lettura
  dello stato attuale, non una prova di invio.

## API e job serale attestati

API Play `play-b6fbe4d`, revisione `meteofriul-api-00251-jow`,
digest `5522b4cfc15076a9f93e838e3643b35e1aa5ad4ce0bf5bca4851997ea94c2ae8`.
Cloud Build `4f68bd0e-6494-4caa-9be2-90d60d36a92b` (europe-west1), SUCCESS.
I 179 file runtime/Dockerfile/requirements dell'archivio immutabile coincidono
con `599aea2f8a3b1e7e65af2b43e77bb54e4637c96e`, normalizzando solo CRLF/LF.
Nessun file runtime aggiuntivo in Git. Si attesta l'equivalenza del contenuto,
non una label di commit assente nel build.

Job serale: digest
`68ce70252ae27a33a5bbd628984727fc993a9be09295777d945108441bf773c5`,
Cloud Build `d32ca0bf-a838-4297-862c-5b476e3aef23` (europe-west1), SUCCESS.
L'overlay approvato proviene da `b5f65e7b26097ad7d0141e80348c5323b77ccf1c`:
quattro file applicati al parent `7af9d579…`. La sola trasformazione di
`fcm.py` rimuove una costante nazionale inutilizzata, già dichiarata nel
manifesto originale. Non è una ricompilazione integrale di quel commit.
La copia locale originale `.tgz` coincide con lo SHA-256 di Cloud Build;
l'oggetto temporaneo remoto restituisce 404.

`repositories/push.py` nell'API e nel parent del job ha SHA-256
`989a05445be31c46fa8d23e9613d0fd54c83dd29aae999402a7cd3b41bbae71c`;
l'overlay non lo sostituisce. Le attestazioni storiche non sono state riscritte.

Lo script protetto AAB può ora ricevere `ExpectedImageDigest` e
`BackendEvidencePath` in entrambi i controlli API. I controlli continuano a
verificare commit, digest, revisione, tag, stato Ready e salute; nessuna deroga.
Non è stata riservata una versione Play.

## Prove e lavoro successivo

Prove versionate in
[`20261020-services-attestation`](../../release-history/cloud-operations/20261020-services-attestation/):
`api-backend.json`, `api-runtime-files.json`, `evening-backend.json`,
`public-alert-local-check.json`, `api-preflight-live.json`,
`push-ttl-live.json`, `checks.json`.

Nuovo set:
[`play-services-20261020.json`](../../release-history/firestore-ttl/runtime-writer-sets/play-services-20261020.json).
Descrive le immagini attive, **non** dichiara distribuito il fix FVG.
Ogni deploy successivo che cambia un digest richiede una nuova attestazione.

Prima di pubblicare la correzione: CI dopo
un push autorizzato, preparazione del rollback compatibile e deploy separatamente
autorizzato; verifica successiva delle corse ordinarie senza forzare invii.
Queste prove non sostituiscono la matrice Android della candidata minificata
né autorizzano AAB, caricamento Play o pubblicazione Web.

## Promozione locale su main autorizzata

Il 20 ottobre 2026 i tre commit `c5c46675`, `56069cc1` e `aa8a89c4` sono
stati portati su main con fast-forward dalla base `c45ba45d`, senza conflitti.
Prima della promozione sono stati rieseguiti: 195 test Python, contratti del
preflight API e del set/audit push TTL, verifica di pulizia del workspace e
`git diff --check`. Tutti superati. Nessun cambiamento a frontend o pacchetti:
le prove su telefono non sono applicabili a questa promozione solo backend,
attestazioni e strumenti di preparazione; la matrice Android resta da svolgere
sulla futura candidata di release.

Le attestazioni JSON restano immutate, con la loro singola aggiunta originale
in Git. Le prove LIVE sono quelle già registrate nella fase precedente: questa
promozione non esegue nuove verifiche cloud. CI remota rinviata al futuro push
autorizzato. Nessuna AAB, installazione, push, deploy o invio; la correzione
operativa del job FVG resta da distribuire separatamente.
