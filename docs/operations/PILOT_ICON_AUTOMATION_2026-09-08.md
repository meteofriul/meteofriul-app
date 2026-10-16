# ICON: recupero e automazione della pubblicazione

## Perimetro

Solo progetto `meteofriul-pilot-20260906`, regione `europe-west1`, job
`pilot-icon`, account runtime `pilot-icon@meteofriul-pilot-20260906.iam.gserviceaccount.com`.
Scheduler `pilot-icon-refresh` invariato: `0 6,18 * * *`, `Etc/UTC`.
Nessuna modifica a Firebase, beta, frontend, CAMS o reader.

Richiesta: recuperare `20260908T000000Z` dai file gia validati, poi rendere
automatici checkpoint, retry della sola pubblicazione e verifica del risultato.
Non promuovere dati incompleti o revocati; mantenere il precedente latest fino
alla pubblicazione atomica verificata. Il collaudo della prossima finestra
programmata e distinto dalle esecuzioni manuali di recupero/test.

## Stato iniziale verificato

- Esecuzione schedulata `pilot-icon-56rgk`, 08/09 06:00:32 UTC: fallita alle
  06:03:17; log legacy `manual_review` privo di motivo. Nessuna causa storica
  specifica viene dedotta dal solo messaggio generico.
- Latest ICON revision 3: `20260907T120000Z`, previous `20260907T000000Z`.
- Intent `state/publication/icon/20260908T000000Z.json`: pubblicazione congelata
  `2026-09-08T06:01:17Z`, fingerprint
  `8974eea961ab3a7b5882076005aa894217d7e67d6827f80c002734b1f90b2123`.
- Lacuna riprodotta nel codice: claim di finestra creato prima dell'acquisizione,
  poi salto incondizionato della finestra gia occupata. Un restart non riprendeva
  la pubblicazione. Il job aveva maxRetries 0.
- Digest ICON originale:
  `d33da939bb659d395a6da5da9dbfa6287013db6c1dfc0c070e61b47e06055bc4`.
- Stato IAM letto: ICON puo leggere/creare solo oggetti del proprio provider
  e stato sotto `pilot/state/dispatch/icon/` e `pilot/state/publication/icon/`.
  Replace limitato al puntatore `pilot/weather/v1/icon2i/latest.json`.

## Step 1: diagnostica distribuita e verificata

Distribuito sul solo `pilot-icon` il digest
`3f71762c531d2d339cb22a568f1fc062ae1d12467f6a421f62eaee685ad9b36a`, prodotto dal
build regionale `f195cfe4-71a4-4b76-9256-a9424d36a73a` (SUCCESS).
Readback della configurazione: stesso account, CPU1/RAM1GiB, timeout900s,
task1/parallelismo1, retry0, env e scheduler invariati.

Test locali diagnostica/GCS/intent: 21 passati. Test degli stessi moduli nel
job distribuito: esecuzione `pilot-icon-ffq7q`, completata con successo il
08/09 alle 16:34:21 UTC; log `Ran 21 tests`, `OK`, exit0. Override degli argomenti
limitato a questa esecuzione (`python -m unittest ...`): non ha eseguito
`cloud_worker`, non ha acquisito dati ne consumato una finestra ICON.

Lo step diagnostico da solo non sblocca la pubblicazione. Recovery e collaudo
end-to-end restano da registrare dopo il loro completamento.

## Step 2: recovery implementata e distribuita

Commit separato `cfe1c90`, sulla stessa linea della pilota (nessun nuovo ramo).

- Checkpoint create-only compresso con manifest e 215 payload completi, verificato
  prima di congelare l'intent remoto; ripresa dopo interruzione senza DWD.
- Slot originale legato all'esecuzione, conservato anche oltre il cambio d'ora.
  Solo il proprietario puo ritentare un'acquisizione priva di checkpoint.
- Recovery degli immutabili esistenti: intent originale, fingerprint, manifest,
  catalogo, 215 payload, hash e generazioni. Nessuna riscrittura dei file gia validi.
- Pubblicazione condizionale di latest, verifica dopo scrittura, protezioni contro
  revoche, conflitti e regressioni mantenute. Anche un successo registrato viene
  riverificato: non basta leggere un vecchio marcatore.
- Tre tentativi in-processo della sola pubblicazione (attese 1 e 3 secondi), solo
  per errori transitori. HTTP 408/429/5xx e trasporto conservano il tipo di errore.
  Esiti terminali leggibili e persistenti; nessuna ripetizione del download per
  errori permanenti gia classificati.

Gate locali: 57 test worker/checkpoint/intent/entrypoint, 24 test recovery e
regressioni publisher, 172 test probe/benchmark/acquisizione, 8 diagnostici:
tutti passati. I test checkpoint usano dati reali di fixture per tutti i 215 comuni,
inclusi gzip corrotto, hash/catalogo errati e risposta persa alla scrittura.

Build cloud con upload allowlist (115 file, solo codice pipeline e cataloghi):
`c0fc0323-5966-420c-8d6e-5042539effc0`, tag `icon-recovery-20260908-1850`.
Il digest non va distribuito finche il gate Linux offline non e superato.

Il gate completo ha eseguito 327 test in 996,577s: 326 passati e un errore
nel simulatore `PauseFamilyLatestCasStore` (`resume.wait(20)`), non nel runtime.
Caso: `test_cams_family_release_observes_its_concurrent_rollback_as_superseded`.
Il thread principale valida tre release complete; il timeout di sincronizzazione
scadeva dopo il CAS mentre il rollback era ancora in corso. Problema preesistente
gia annotato nel rapporto Android. Nessuna immagine di quel gate distribuita.

Corretto soltanto il budget del simulatore a 120s, mantenendo identici
interleaving e assert su superseded/revisione/ETag/corsa attiva/revoca.
Retest locale dello stesso caso: 1 passato in 93,926s. Timeout del solo build
completo portato a 1800s (non e il timeout del job ICON, che rimane 900s).

La ripetizione completa `15638fc5-f387-47a1-a5fe-b92aac0ecba2` e stata fermata
all'inizio; sostituita dal retest mirato cloud `551786e5-afc7-4b09-9b8e-97c2bcef3dcb`
(tag `icon-recovery-20260908-retest`): tutti gli altri moduli e, nominativamente,
il test concorrente corretto. Il gate completo standard resta disponibile.
Non presentare l'esito cumulativo come un unico gate completo verde.

Confrontati in memoria i due archivi effettivamente caricati su Cloud Build:
115 file, unica differenza `test_contract_publisher.py`; 68 file runtime,
cataloghi e Dockerfile byte-identici, digest aggregato
`676406e6b3e19635f27b52770a9f00897e3862bef9c36a8eb43a175dafc06605`.

Retest cloud: **302/302 passati in 215,335s**, incluso il caso concorrente;
build SUCCESS 08/09 17:15:31 UTC. Distribuito sul solo `pilot-icon` il digest
`3f29490510584488b26f507149f3a1a965717ce1accb38226aaa14a1131bbd88`.
Correzione del simulatore documentata nel commit separato `6107867`.

Readback job: stesso service account, CPU1/RAM1GiB, timeout900s; env solo
progetto pilota e provider ICON. `maxRetries` ora 2 per riprendere il checkpoint
dopo un'interruzione. Nessun override recovery persistente. Scheduler letto
nuovamente: ENABLED, `0 6,18 * * *`, Etc/UTC, prossima 18:00:02 UTC; invariato.

Questo aumenta il limite prudenziale di calcolo ICON: fino a tre tentativi per
esecuzione, due finestre al giorno, quindi `2 x 3 x 900 = 5400` secondi-task/giorno
contro i precedenti 1800. E un massimo per guasti persistenti, non il consumo
ordinario e non un tetto di spesa globale. CAMS e i suoi limiti restano invariati.
La vecchia stima monetaria del rapporto iniziale non includeva questi restart.

Controllo telefono prima del recupero, 08/09 16:53 UTC: Samsung collegato,
pacchetto `com.meteofriul.app.localpilot`, localita Pordenone `093033`.
Bundle corrente verificato alle 16:52:53 UTC: ICON `2026-09-07T12:00:00Z`,
44 ore future reali, cache esistente preservata. CAMS `2026-09-08T00:00:00Z`.
Non e una prova del recupero: registra esplicitamente la baseline da confrontare.

## Step 3: recupero reale e readback completati

Test post-deploy sull'immagine distribuita: `pilot-icon-z9wrk`, 24/24 passati,
exit0, completata 17:18:09 UTC. Solo override degli argomenti del singolo test;
nessuna acquisizione ne claim di finestra.

Recovery autorizzata: `pilot-icon-hdspt`, override della sola esecuzione
`PILOT_ICON_RECOVER_RUN_ID=20260908T000000Z`. Completata con successo
08/09 17:20:31 UTC (19:20 locali). Validazione in 21,393s, commit e readback
in 0,46s, lavoro worker complessivo 23,386s oltre alla partenza Cloud Run.

Log strutturato reale `publication_result`:

- status `published`, reason `publication_committed`;
- `validation_status=passed`, `publication_status=verified`;
- `payload_count=215`, `reused_payload_count=215`, `manifest_reused=true`;
- `latest_updated=true`.

Nessuna fase di acquisizione: tutti i file gia esistenti sono stati riusati,
nessun nuovo download DWD. Il recupero reale non ha richiesto un retry;
l'esecuzione manuale prova il recupero dei file, non la partenza da scheduler.

Readback diretto GCS: revision 4, latest `20260908T000000Z`, previous
`20260907T120000Z`, nessuna revoca. Manifest 36.111 byte, SHA-256 uguale al
fingerprint dell'intent originale. `published_at=2026-09-08T06:01:17Z` resta
quello congelato nell'intent; non e l'orario effettivo del recupero.

Audit indipendente via reader HTTPS pubblico: 215/215 payload verificati per
schema, hash e catalogo; manifest, previous, CORS dell'origine `https://localhost`,
ETag e puntatore stabile prima/dopo le letture. Esito passed: 219 GET,
12.926.497 byte, 25,174s; zero scritture cloud e zero richieste alla sorgente.
Al controllo tutti i comuni avevano ancora 55 ore future reali nel dataset.

Telefono Samsung, stessa APK `com.meteofriul.app.localpilot`, cache preservata:
al normale controllo di versione, dopo il periodo di cache esistente di 10 minuti,
ricevuti latest, manifest e payload Pordenone della nuova corsa. Bundle verificato
alle 17:23:05 UTC: corrente E previsioni indicano `2026-09-08T00:00:00Z`, entrambi
con evidence `runs/20260908T000000Z/municipalities/093033.json`, stato fresh.
Mostrate 48 ore reali, da 08/09 18:00 UTC a 10/09 17:00 UTC. Home aggiornata
senza cancellazione cache, reinstallazione, nuovi testi o modifiche di interfaccia.
CAMS rimane sulla sua corsa valida dell'8. La beta sul telefono conserva
versione 1.0.1/code300012 e lastUpdateTime 30/08 00:41:28.

Readback finale job: override recovery ASSENTE dalla configurazione permanente,
digest e retry corretti. Claim `state/dispatch/icon/20260908-pm.json` assente
(404 verificato): il recupero non ha consumato lo slot serale. Scheduler ancora
ENABLED, ultima chiamata prevista del mattino, prossima 18:00:02 UTC.

**Condizione 1 soddisfatta. Condizione 2 ancora da verificare:** non dichiarare
ICON definitivamente risolto prima del ciclo programmato successivo.

## Seconda verifica indipendente

Follow-up `verifica-prossima-corsa-icon-pilota`, sola lettura cloud. Finestra
programmata 08/09 18:00 UTC (20:00 Europe/Rome), controllo dalle 20:15 locali.
Attesa corsa `20260908T120000Z`, se disponibile. Il follow-up non avvia job,
non pubblica e non modifica risorse per ottenere un risultato positivo.
Il completamento richiede sia il recupero reale della corsa del mattino sia
il ciclo programmato successivo. In assenza di un guasto reale, il secondo
controllo dimostra il ciclo automatico regolare, non un retry reale in produzione.
In Cloud Logging leggere anche `jsonPayload`: i nuovi eventi strutturati non
compaiono necessariamente in `textPayload`. Atteso checkpoint dello slot
`state/dispatch/icon/20260908-pm/checkpoint.json.gz` e relativo outcome;
le verifiche successive devono restare in sola lettura cloud.

## Seconda verifica completata dopo il blackout del PC

Controlli del 08/09 dalle 20:27 alle 20:34 Europe/Rome, esclusivamente in
lettura cloud. Nessun avvio manuale, deploy, ripubblicazione o cambio scheduler.

- Scheduler `pilot-icon-refresh` ENABLED, frequenza 06/18 UTC invariata;
  chiamata delle 18:00:40 UTC (20:00:40 locali) senza errore.
- Execution `pilot-icon-v62s5`: avvio 18:00:45 UTC, successo 18:03:01 UTC.
  Creator e lastModifier sono
  `pilot-scheduler@meteofriul-pilot-20260906.iam.gserviceaccount.com`.
  Immagine recovery attesa: digest
  `3f29490510584488b26f507149f3a1a965717ce1accb38226aaa14a1131bbd88`.
- Evento strutturato `publication_result` alle 18:02:57.872 UTC:
  `published`, `validation_status=passed`, `publication_status=verified`,
  `payload_count=215`, `latest_updated=true`, `task_attempt=0`.
  Outcome PM persistito con lo stesso risultato.
- Checkpoint `pilot/state/dispatch/icon/20260908-pm/checkpoint.json.gz`
  presente: generation `1788890530773943`, 1.348.335 byte.
- Reader HTTPS: latest `20260908T120000Z`, revision 5; previous
  `20260908T000000Z`, manifest precedente valido e nessuna revoca.
  SHA-256 manifest corrente:
  `8bcfdeec8f03726a6f36e0d02f9c58710d754dd397d2633758a7da169d6cad39`.
- Audit pubblico indipendente PASS alle 20:33:07 locali: 215/215 payload
  verificati per schema, catalogo, hash e JSON canonico; 219 GET, circa 13 MB,
  23,492 secondi. Latest stabile nel readback finale, CORS nativo verificato;
  tutti i comuni conservavano 66 ore future reali nel dataset.
- Ripristinati solo backend locale 127.0.0.1:8002 e preview 127.0.0.1:5176.
  Il proxy della preview serve la stessa revision 5. Nel browser la pilota
  mostra `ICON-2I · aggiornamento modello 08/09/2026, 14:00`, cioe la corsa
  delle 12 UTC, e 48 ore reali dalle 21:00 dell'8 alle 20:00 del 10 settembre.
  Cache non cancellata, nessuna modifica al codice runtime, nessuna nuova APK.

**Anche la Condizione 2 e soddisfatta:** corsa successiva avviata
automaticamente, validata, pubblicata e servita alla preview della pilota.
Il blackout locale non ha impedito l'esecuzione cloud. In questo controllo
non e stata verificata nuovamente l'APK sul telefono: il readback client e
quello della preview. Questo successo al primo tentativo dimostra il ciclo
programmato regolare, non un retry reale in produzione.
