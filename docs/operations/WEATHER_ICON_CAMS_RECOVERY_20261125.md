# ICON nazionale e CAMS: diagnosi e correzioni candidate — 25 novembre 2026

## Stato e perimetro

Base del codice `origin/main` `61ca8e5e`; workstream
`codex/weather-icon-cams-recovery-20261125`. Questo rapporto distingue
**sorgente**, **codice candidato**, **immagine distribuita**, **esecuzione del
job** e **dato pubblicato**. Al controllo live delle **15:34 UTC / 16:34 CET**
le immagini cloud non erano state aggiornate da questo workstream. Le letture
cloud e le tre richieste GET ai metadati pubblici CAMS erano in sola lettura:
nessun ADS POST, esecuzione manuale, modifica di fence, Scheduler o policy.

## CAMS: causa verificata e correzione

La [comunicazione ufficiale ECMWF del 23 novembre](https://forum.ecmwf.int/t/upgrade-u11-to-the-cams-european-air-quality-products/15596)
annuncia l'upgrade U11 dei prodotti europei e sette parametri aggiuntivi,
con prima produzione operativa prevista il 24 novembre. Il form pubblico
ADS letto via GET il 25 novembre espone **35 variabili**: le 28 richieste
dall'app più quelle sette. Il codice precedente richiedeva un'uguaglianza
esatta fra form e lista di 28, perciò gli slot 09/10/11 UTC terminavano in
`PublicMetadataError` nella validazione. Alle 15 UTC il catalogo esponeva
anche `cads:sanity_check.status="warning"`, fuori dall'insieme
`available/down` accettato; il job ha registrato
`catalogue_sanity_unavailable`. Il puntatore famiglia aria/pollini su
Storage e HTTP era ancora al run del **23 novembre, 09:01:18 UTC**.
Nello stesso slot delle 15 UTC UV è stato pubblicato separatamente con
`run_at=2026-11-25T00:00:00Z`.

La modifica a [cams_request_plan.py](../../experiments/weather_autonomy/cams_request_plan.py)
accetta **solo** le sette opzioni U11 aggiuntive nel form, senza richiederle.
Il piano resta di **28 variabili × 97 lead = 2.716 campi**; nomi mancanti o
ulteriori non approvati falliscono. `warning`, come il già tollerato `down`,
passa soltanto dopo identità, licenza, DOI, data, URL/hash e vincoli completi
con un'unica riga compatibile; un dataset esplicitamente disabilitato resta
bloccato. Il controllo pubblico GET del 25 novembre alle 15:34 UTC ha creato
in memoria un piano valido senza inviare una richiesta ADS.

La diagnostica aggiunta emette campi sicuri come `metadata_field`,
`expected_count` e `actual_count`; per il caso U11 registra 28/35 e lo stato
`warning` dopo validazione, senza URL, body o dettagli arbitrari di eccezione.
Il catalogo pubblico letto aveva DOI `10.24381/a4005cee`, licenza CC-BY-4.0
e timestamp del sanity check `2026-11-25T14:18:02.925059+00:00`.

**Limite di qualità:** U11 cambia anche la conversione upstream dei gas da
mixing ratio a concentrazione a temperatura/pressione standard. Il decoder
locale tratta i valori GRIB di massa e non ripete quella conversione;
il piano validato non dimostra comparabilità o plausibilità dei nuovi valori.
Dopo una corsa autorizzata servono controllo delle unità GRIB, dei range,
della famiglia aria/pollini e della lettura Storage+HTTP. Nessun dato CAMS
è dichiarato recuperato sulla base dei soli test o GET.

## ICON nazionale: log e stato durevole

Il controllo live delle 15:34 UTC trova ancora
`state/icon-recovery/v1/national/active.json` in `manual_review`, slot
`20261121-pm`, ciclo `20261121T120000Z`, con fence presente. L'ultimo slot
osservato, 10 UTC, è fallito; il prossimo è previsto alle 18 UTC. Il puntatore
Storage pubblico resta al run 00Z del 21 novembre e il reader HTTP restituisce
503. La prima acquisizione del 21 novembre risulta completata alle 18:02:58
UTC, seguita da `acquisition_requires_review` alle 18:03:20. Esiste
`intent.json`, ma non mapping, prepared o manifest pubblico. Il bundle GRIB
in memoria non è conservato: non è possibile riprodurre esattamente
l'eccezione originale da quel ciclo. I dodici slot falliti successivi possono
solo rileggere la stessa fence.

Il codice precedente catturava l'eccezione prima di registrare il tipo/la
fase sicuri. La modifica a
[national_cloud_worker.py](../../experiments/weather_autonomy/national_cloud_worker.py)
delimita validazione del bundle, preparazione, upload e verifica del
checkpoint; [icon_recovery.py](../../experiments/weather_autonomy/local_pipeline/icon_recovery.py)
emette un evento strutturato prima di trasformare l'errore in
`manual_review`. Il filtro in
[operational_diagnostics.py](../../experiments/weather_autonomy/local_pipeline/operational_diagnostics.py)
ammette solo nomi di file e campi controllati, non messaggi, URL o payload
arbitrari. I test simulano errori contenenti dati sensibili e verificano che
non siano stampati.

**La fence esistente non viene rimossa da questa patch.** Il contratto di
recupero permette di sostituire un owner soltanto dopo una pubblicazione
verificata o un checkpoint durevole; qui quest'ultimo manca. Per riprendere
ICON nazionale serve una procedura operativa separata, revisionata, con prova
che non vi siano esecuzioni attive, registrazione immutabile dell'incidente,
CAS esatto sullo stato, scelta di un ciclo sorgente successivo e verifica
completa di manifest, puntatore e HTTP. Una semplice cancellazione della
fence o un timeout violerebbero l'invariante di concorrenza.

Il disegno di ripresa richiede di congelare le esecuzioni e leggere stato e
generazione esatti, intent, checkpoint assenti e puntatore pubblico. Una nuova
implementazione deve creare e rileggere un record immutabile dell'incidente,
reclamare una sola volta un ciclo successivo con precondizione sulla generazione
e riconciliare anche una risposta CAS persa. Qualsiasi cambiamento concorrente,
prova mancante o doppio claim blocca la ripresa. Il nuovo ciclo segue poi
acquisizione, checkpoint, manifest, readback Storage, CAS del puntatore e
lettura HTTP ordinari. Questo protocollo necessita test per concorrenza, crash,
fonte non valida e lettura finale prima di operare sullo stato reale.

## Log e monitor esistenti

I job scrivono eventi JSON strutturati in Cloud Logging: fasi, esiti,
componenti, tipi di errore, file/riga e reason code consentiti. Il monitor
ICON confronta anche puntatore Storage, HTTP, copertura e freschezza: al
controllo del 25 novembre rilevava il nazionale critico, pur con il proprio
container riuscito. CAMS ha policy sui fallimenti del job, ma quella policy
non attesta che aria e pollini siano correnti e non vede uno Scheduler che
non invoca il job.

Il bucket Cloud Logging `_Default` del progetto conserva i log per **30
giorni**. Il suo sink include i log Cloud Run Job; l'unica esclusione
configurata riguarda le richieste HTTP grezze del servizio Community per
privacy. `_Required` conserva per 400 giorni i log di audit obbligatori,
non è l'archivio applicativo dei job. L'assenza dell'eccezione iniziale ICON
nel novembre corrente deriva quindi dalla cattura nel codice, non da una
retention già scaduta.

I limiti di osservabilità qui erano **specifici**:

- `Recovery.run` trasformava l'eccezione iniziale ICON in
  `acquisition_requires_review` senza emettere prima la fase e il tipo
  dell'errore; gli slot seguenti leggevano solo la fence persistente.
- La diagnostica CAMS occultava correttamente i testi non fidati, ma non
  conservava un'etichetta controllata del campo rifiutato. Gli eventi
  precedenti permettevano di distinguere `metadata_validation` e
  `catalogue_sanity_unavailable`, non la nuova lista U11.

Le correzioni aggiungono **categorie e conteggi predefiniti**, senza
registrare credenziali, URL con parametri, corpi HTTP, GRIB o messaggi
arbitrari. Occorre ancora verificare che gli eventi arrivino nel log di
una futura esecuzione cloud e che un allarme sia effettivamente ricevuto;
la presenza di una policy non è prova di recapito.

## Verifiche e prossimi gate

- **Codice candidato:** 120 test combinati ICON/CAMS/diagnostica passati in
  locale; i test CAMS includono variabili U11, `warning`, rifiuto di opzioni
  sconosciute o vincoli incompleti e indipendenza UV. Due test ICON simulano
  il primo guasto senza manifest, mantengono `manual_review` e verificano
  l'assenza di segreti nei log. La suite meteo completa è stata interrotta
  dopo circa 20 minuti senza un esito finale: non è conteggiata come prova.
  I test non sono una corsa cloud.
- **CI PR #61:** i job `backend`, `frontend` e `hosting-preview-tool` della
  corsa `45649847742` sul commit `76c601bf` sono tutti riusciti il 25
  novembre. Nessuna promozione a `main` è implicata dal successo della CI.
- **Immagine CAMS candidata:** le Cloud Build
  `56ee9426-997d-442d-b651-c1da43dfe2f3` e
  `aca7ba50-ac5d-4eb9-b88c-033904dd276c` si sono arrestate ai gate:
  rispettivamente modo file diverso (`0644` nel tar contro `0666` nella
  base) e confronto di `Config.Image`, metadato del builder. Nessuna delle
  due ha pubblicato un'immagine o aggiornato il job. Il terzo archivio
  immutabile, SHA-256 `a46d74e0cfd6121d2fca5591b0e7a73268381fe7940c90e730f57a67b53eec5c`,
  ha completato Cloud Build `4cf58cf9-588c-41d6-86e0-2c700c361fd5`
  alle 16:19 UTC: tutti e quattro gli step sono `SUCCESS`, inclusi 438 test
  offline senza rete, zero errori/fallimenti/skipped. Il verificatore ha
  riscontrato solo i due file previsti cambiati sui 212 file `/app`;
  hash/modi degli altri file, pacchetti, Python, UID, configurazione runtime
  e layer base sono conservati. Il solo `Config.Image` builder è escluso dal
  confronto; `Env`, `Cmd`, `User`, etichette e gli altri campi restano uguali.
  Digest candidato `sha256:b377e7d029f8e0d861ca3eba7fe640c1b1f0fb13b0578d775c09e7de32689012`.
  Alle 16:19 UTC era un artefatto costruito, non ancora distribuito.
- **CAMS prima di dichiarare recupero:** provenienza immagine, deploy
  controllato, una corsa reale, checkpoint/reader Storage+HTTP, freschezza
  delle tre componenti e plausibilità U11. Nessuna di queste prove è
  implicata dal GET di metadati.
- **ICON prima di dichiarare recupero:** definire e verificare la procedura
  sulla fence, acquisire un nuovo ciclo, completare i checkpoint e il
  manifest, verificare Storage/HTTP e il monitor di freschezza. La sola
  diagnostica migliora il prossimo errore, non ripara il ciclo 21 novembre.

In questa fase di diagnosi non erano state modificate le app Web/Android,
i job distribuiti, Mercati o le notifiche. La successiva modifica del solo
job CAMS è registrata sotto.

## Promozione e verifica CAMS del 25 novembre

La [PR 61](https://github.com/meteofriul/meteofriul-app/pull/61) è stata
integrata in `main` con `488f7d3c`; CI PR sul commit finale
`45652718958` e unica CI di `main` `45653497810` sono verdi nei tre job
backend, frontend e hosting. Il 25 novembre alle 16:28 UTC il preflight
cloud ha confermato account e progetto attesi, template CAMS generazione 11
uguale al baseline, Scheduler `ENABLED` con `0 9,10,11,15,20 * * *`
`Etc/UTC`, provider `cams`, continuità attiva e zero esecuzioni aperte
nelle 200 più recenti.

Il solo job `meteofriul-cams` è passato al digest immutabile candidato
`sha256:b377e7d029f8e0d861ca3eba7fe640c1b1f0fb13b0578d775c09e7de32689012`,
generazione 11 → 12. Il confronto readback del template ha trovato soltanto
l'immagine e la label `client.knative.dev/nonce` generata dal comando Cloud
Run; gli altri campi coincidono. Scheduler CAMS e digest del job ICON
nazionale sono invariati. I verbali di intento e i template completi
restano nello staging locale ignorato `.tmp/weather-icon-cams-deploy-20261125/`;
nessun dato sensibile è riportato qui.

Il primo controllo preliminare degli oggetti ha omesso per errore il prefisso
Storage `pilot/` e quindi **non prova** l'assenza di un intent precedente.
La successiva lettura del percorso corretto trova piano, `intent.json` e
`submitted.json`; le loro generazioni indicano creazione dalle 16:32:04 UTC,
dopo l'avvio manuale. Il worker applica inoltre la sua identità durevole
di richiesta per evitare una seconda POST sullo stesso ciclo. Alle 16:31:47
UTC è stata avviata una sola esecuzione manuale, `meteofriul-cams-96f4b`.
I log delle 16:32 UTC
registrano `form_u11_extra_variables_validated` e
`catalogue_sanity_warning_constraints_validated`, poi l'acquisizione ADS.
Alle 16:34 UTC il componente aria era ancora `pending` con reason
`acquisition_not_completed`; il worker ha proseguito i propri tentativi sullo
stesso stato durevole. L'esecuzione è terminata `Completed=False` alle
**16:39:43 UTC**: ADS restava `accepted`, i componenti aria/pollini erano
`remote_pending`/`remote_processing` e il worker ha registrato
`execution_budget_exhausted`. È un limite d'attesa della fonte, non un nuovo
rifiuto dei metadati. Piano, intent e `submitted.json` sono presenti; il
codice di ripresa legge il checkpoint `submitted` e non invia una seconda POST
per lo stesso piano. Nessuna seconda corsa manuale è stata avviata.
La pubblicazione corrente e la plausibilità U11 richiedono ancora un
risultato ADS disponibile e un readback completo.

La verifica indipendente dopo il fallimento trova Storage e HTTP concordi
su revisione 72, ciclo aria/pollini `20261123T000000Z`, pubblicato il 23
novembre alle 09:01:18 UTC; il release HTTP corrisponde al proprio hash.
UV risponde HTTP 200 sul ciclo del 25 novembre 00Z e copre 72 ore. Il
checkpoint `submitted.json` supera i controlli di piano, hash, intento,
identità del job e zero retry POST. Nel codice la ripresa da `submitted`
usa `client.get_remote` sul medesimo job ADS; `client.submit` compare solo
nel ramo di nuova submission. Due test mirati di ripresa/no seconda POST
passano. Il prossimo slot ordinario CAMS è alle 20:00 UTC; un suo successo
richiederà comunque verifica della famiglia, HTTP e valori U11. Un controllo
diretto dello stato ADS richiederebbe credenziale e client del job: non è
stato effettuato né sono state lette credenziali.

## Ramo separato ICON: protocollo candidato, fence intatta

Alle **16:53 UTC** la fence nazionale è ancora `manual_review` sul ciclo
`20261121T120000Z`, slot `20261121-pm`. Il job nazionale distribuito usa
ancora il digest `sha256:d062db94…`; il suo Scheduler resta attivo. La
[PR 63 bozza](https://github.com/meteofriul/meteofriul-app/pull/63), nata
dal `main` `488f7d3c`, contiene un protocollo esplicito con incidente
immutabile, CAS, riconciliazione e un solo claim, più `inspect` in sola
lettura. Sono passati 95 test mirati ICON, `compileall`, diff check e 41
test del nuovo comando CI eseguiti localmente. La CI remota della PR e la
build cloud non sono attestate qui.

**Non è stato usato `--execute` nel cloud.** Servono un job operatore
isolato, immagine/commit/marker distribuiti, IAM e inventario degli altri
writer verificato durante una finestra con Scheduler sospeso. L'inventario
statico della bozza vale 60 secondi e può scadere durante il provisioning:
il comando rifiuta l'operazione in quel caso. Il solo codice o deploy non
supera la fence. Il progetto e i gate sono nella PR bozza e non sono ancora
presenti su `main`.

## Seguito delle 17:12 UTC / 18:12 CET: diagnostica ICON distribuita

La correzione diagnostica della PR 61, integrata in `main` `488f7d3c`, è
stata preparata per il job nazionale partendo dal digest distribuito
`sha256:d062db94eedf2337ef1886f8f2a80c9babc0901c8c78bc7385c6930fa730eb26`.
L'archivio immutabile ha SHA-256
`1e40983836f73738be4aefd76ac8b4bbbdb2e674f2d058665db020e0038e83e3`.
La Cloud Build `cc48932f-46bb-4f23-b2b4-fd10a8fd0773` ha superato tutti
e quattro gli step, inclusi **125 test offline** e il confronto di 175 file
runtime: cambiano solo `national_cloud_worker.py`,
`local_pipeline/icon_recovery.py` e
`local_pipeline/operational_diagnostics.py`; dipendenze, permessi,
configurazione runtime e base dell'immagine sono conservati. Un primo replay
locale si era fermato per `PYTHONPATH` mancante; ripetuto con l'ambiente
corretto, i 125 test sono passati. Il digest risultante è
`sha256:6fe9e4980222ff57ccb12d6fe0a2045d9a5d585135efcc17dcf664aabe98c361`.

Il preflight ha confermato account/progetto, template nazionale originale,
Scheduler `ENABLED` con `0 6,7,8,10,18,19,20,22 * * *` `Etc/UTC`, nessuna
esecuzione aperta fra le 200 più recenti e distanza dallo slot delle 18 UTC.
Il solo job `meteofriul-national-icon` è passato alla nuova immagine,
generazione 2 → 3. Il readback del template trova soltanto immagine e nonce
Cloud Run generato; Scheduler e job CAMS sono invariati. Subito dopo, la
fence nazionale risultava ancora `manual_review` sul ciclo
`20261121T120000Z`, slot `20261121-pm`. Non è stata avviata una corsa
manuale, modificato lo stato durevole o distribuito il codice operatore.
La prima esecuzione ordinaria con questa diagnostica è prevista alle
**18:00 UTC / 19:00 CET**: finché la fence resta attiva, il nuovo log del
primo errore non può ricostruire il guasto del 21 novembre.

La [PR 63 bozza](https://github.com/meteofriul/meteofriul-app/pull/63)
per il protocollo operatore ha superato la CI remota `45659615514` nei tre
job; resta non integrata e non distribuita. Una corsa manuale CI equivalente
`45660003853` è stata annullata dopo la riuscita della CI PR, per evitare
un duplicato. Il comando `--execute` non è ancora utilizzabile in modo
operativo: mancano il job isolato, la prova IAM/writer e un inventario
aggiornabile durante l'avvio. Il prossimo passo è una revisione del
protocollo e delle sue condizioni, poi un recupero esplicito della fence;
questa distribuzione serve solo a diagnosticare eventuali nuovi guasti.
