# Eventi — collaudo locale della Fase 0

Data: 13 ottobre 2026. Ramo: `codex/events-card-quarantine`.
Candidato applicativo: `27045887fb837491e6052233cd5d64c6493d282d`.
Base `main` locale: `5a68de5dc1607105f921d4d2b731170f1a8a0446`.

**Seguito operativo:** le affermazioni su mancato deploy/prova nativa in
questo documento descrivono questa fase locale. La successiva distribuzione,
il fallimento del ciclo cloud, il recupero TurismoFVG e il collaudo TEST
sono documentati nel [resoconto deploy](EVENTI_FASE_0_DEPLOY_E_TEST_2026-10-13.md).

## Esito e limiti

La compatibilità dell'API e il recupero della fonte fallita sono verificati in
locale. Il ciclo completo iniziale **ha fallito per timeout Azalea**; il
successivo recupero della sola Azalea è riuscito entro il limite esistente.
Il catalogo risultante ha 15 fonti pubblicabili, 11 `fresh` e 4 `partial`,
1.586 schede grezze e 6 schede in revisione. Non è la prova di un singolo
ciclo integrale interamente riuscito, né una certificazione della raccolta
futura dal cloud.

Nessuna modifica applicativa aggiuntiva rispetto al candidato. GitHub fermo,
nessun deploy, nessuna scrittura Storage, nessun job Cloud Run avviato. Sono
stati letti i soli metadati del job e del servizio online. Nessuna APK/AAB
costruita o installata. Il collaudo del candidato nel browser del telefono è
riuscito; il pilot precedente è stato ripristinato. La TEST nativa contro
il backend distribuito resta una verifica successiva al deploy.

## 1. Raccolta reale, salvataggio solo locale

Eseguito `scripts/audit-events-full-readonly.py` con `MemoryClient`, che
sostituisce Storage con memoria del processo e salva un JSON locale. Il
collector legge i siti pubblici con gli stessi adapter, gate e limiti del job.

- Input: catalogo ufficiale già salvato alle 11:49 locali; snapshot
  `2026-10-13T09:40:04.618654+00:00`.
- SHA-256 input: `a4c88dfdfe1941444e4692985e39931bd5db5ba31de198421dc36415b79cfb26`.
- Avvio raccolta: `2026-10-13T16:37:58.090605+00:00`.
- Durata fino al salvataggio locale: circa 453.8 secondi.
- Esito del processo: codice 2, `event source verification failed: Azalea`.
- 14 fonti `fresh`/`partial`; Azalea `stale`, errore `timeout`, 7 vecchie
  schede conservate internamente e zero pubblicate per quella fonte.
- Le altre fonti hanno aggiornato le proprie schede. Le quarantene non hanno
  causato il fallimento del ciclo.

Il report del fallimento legge i dati dell'ultimo tentativo: per Azalea il
motivo è `timeout`, con zero revisioni e zero pendenti. Non recupera vecchi
problemi dal lotto precedente. Le quarantene attuali delle altre fonti sono
riportate separatamente con conteggio e URL.

### Recupero mirato

Un solo recupero locale mediante `publish(..., retry_failed=True)`, senza
allargare il budget Azalea di 20 secondi: **10,54 secondi**, stato `fresh`,
7 schede verificate. Tutti i lotti delle altre fonti e i monitor sono stati
confrontati con il precedente JSON e risultano identici. Nessuna nuova
scansione completa eseguita.

Questo dimostra che il timeout non si è ripetuto nel recupero. Non identifica
il singolo URL lento e non prova che il problema sia eliminato definitivamente.
L'adapter Azalea non cambia nel commit Fase 0.

### Catalogo dopo il recupero

| Fonte | Stato | Schede grezze | Revisioni |
| --- | --- | ---: | ---: |
| TurismoFVG | `partial` | 1209 | 3 |
| Pordenonelegge | `fresh` | 0 | 0 |
| Azalea | `fresh` | 7 | 0 |
| CSS Udine | `partial` | 157 | 1 |
| Pordenone Pensa | `partial` | 0 | 1 |
| Teatro Verdi Pordenone | `fresh` | 88 | 0 |
| Teatro Verdi Trieste | `fresh` | 70 | 0 |
| Le Giornate del Cinema Muto | `fresh` | 0 | 0 |
| Paesi in Festa | `fresh` | 17 | 0 |
| SagreFVG | `partial` | 14 | 1 |
| Villa Manin | `fresh` | 4 | 0 |
| Magazzino delle Idee | `fresh` | 0 | 0 |
| MESS | `fresh` | 17 | 0 |
| Galleria Spazzapan | `fresh` | 2 | 0 |
| Barcolana | `fresh` | 1 | 0 |

Snapshot dopo recupero: `2026-10-13T16:47:33.182692+00:00`.
SHA-256: `abb5e330b98aaafb2f53b42c87a71df4bcf397173fd94fd2e335b09f5179d660`.

Le 1.586 schede sono il conteggio interno, prima dei filtri per distanza,
date e aggregazione/deduplica. Il numero effettivo nell'app varia per località
ed intervallo. Pordenone Pensa ha zero schede verificate e una revisione,
secondo il contratto già esistente; non è una nuova eccezione della Fase 0.
Villa Manin ha passato il gate reale con quattro schede: il caso misto con
scheda malformata resta coperto dal test riprodotto nella fase precedente.

### Monitor

Il primo ciclo si è fermato prima dei monitor, perché Azalea era fallita;
il recupero delle sole fonti non li riesegue. I monitor nel JSON sono quelli
conservati dall'input: candidati controllati alle 09:40 UTC del 13 ottobre,
inventario annuale TurismoFVG del 12 ottobre. Non si dichiara un nuovo esito
Palazzo Attems, GiroFVG o inventario annuale. Nessuna email può essere stata
prodotta da questo salvataggio locale.

## 2. API del candidato su cataloghi reali

Eseguita l'applicazione WSGI del commit con `load_catalog` sostituito dal file
locale: stessa query, stesso gate temporale e stessa paginazione, senza client
Storage. Verificati sia l'input precedente sia il nuovo catalogo del ciclo.
Per ogni località, la concatenazione delle pagine coincide con la query
completa; nessuna pagina troncata o mescolata fra snapshot.

| Località, raggio 50 km | Vecchio catalogo | Nuovo catalogo prima del recupero |
| --- | ---: | ---: |
| Caneva | 381 | 398 |
| Pordenone | 794 | 808 |
| Udine | 1.160 | 1.178 |
| Trieste | 570 | 579 |
| Gorizia | 1.021 | 1.025 |

Questi numeri descrivono due inventari a orari diversi, non un incremento
causato automaticamente dal fix.

Ulteriori verifiche positive:

- Una sola Sagra del Rosario a Caneva, categoria `sagra`, date 2–18 ottobre.
- Una sola scheda aggregata Barcolana nella query di Trieste; tre schede MESS.
- Snapshot volutamente errato: HTTP 409.
- Copia isolata con lotti vecchi di 49 ore: HTTP 200, zero eventi e
  `catalog_status=degraded` con tag `source_expired`. I file originali non
  vengono alterati.
- API realmente in ascolto su `127.0.0.1:5176`, alimentata dal catalogo dopo
  recupero: `/health` e `/api/local/events` HTTP 200. Pordenone a 20 km:
  299 schede, prima pagina da 100. Azalea `fresh` e senza tag di errore;
  soltanto i quattro tag `quarantined_cards` attesi.

L'API locale è un servizio di collaudo: non è la revisione online e non è una
build Docker/Linux. Docker non risulta disponibile su questa macchina.

## 3. Collaudo sul telefono e ripristino del pilot

Eseguito il 13 ottobre, circa 19:08–19:10 CEST, dopo l'autorizzazione esplicita
«Sì, prova e ripristina». Dispositivo Samsung SM-A525F, Android 14, schermo
1080×2400; browser Brave 1.97.56, mediante un collegamento ADB reverse locale
alla porta 5174. Il telefono usa il 13 ottobre reale per Eventi.

La TEST già installata è `com.meteofriul.app.tester`, versione
`0.1.14-tester`, codice `300031`. Non è stata reinstallata né ne sono stati
cancellati i dati. Questa prova riguarda **il browser sul telefono reale**,
non una nuova APK o la TEST nativa collegata al candidato.

### Configurazione verificata

- Frontend canonico: `F:/proggetto Meteo Friul App/meteo FRIUL`, ramo
  `codex/community-reports-simplification`, commit
  `308757d2b8c42779e9bec5ca5ba97f7f8a321bf4`. Nessun file applicativo modificato.
- Confrontati mediante SHA-256 i dieci file runtime di
  `frontend/src/features/events/` e dei servizi `eventsApi.js`/`eventsCache.js`:
  coincidono con il ramo Eventi. I file di test sono esclusi dal confronto.
- API candidata: WSGI del commit `27045887`, su `127.0.0.1:5176`, catalogo
  locale dopo il recupero Azalea; nessuna lettura o scrittura Storage.
- Riavvio del solo frontend attraverso il launcher canonico
  `scripts/start-local-weather-pilot.ps1 -CommunityPilot -RestartFrontend
  -WeatherTestNow '2026-09-04T12:00:00Z'`, con la variabile **di processo**
  `VITE_LOCAL_EVENTS_PROXY_TARGET=http://127.0.0.1:5176`.
- Profilo conservato: `weather-offline-v1-community-local-v1`. Il parametro
  storico è quello già in uso per lo snapshot meteo, recuperato dal modulo
  servito dal frontend. Non modifica la data Eventi, che usa `new Date()`.
  Il primo tentativo senza tale parametro è stato fermato prima di modificare
  i processi perché lo snapshot meteo era scaduto rispetto all'orologio reale.
- Il launcher esegue anche il proprio writer dello snapshot meteo locale;
  i processi esistenti backend, data plane e segnalazioni sono stati riusati.

### Risultati osservati

| Verifica | Esito ed evidenza |
| --- | --- |
| Elenco Eventi, Pordenone | Visibile, immagini caricate e indicatore 40 eventi oggi (`03-events.png`) |
| Paginazione reale dal telefono | Tre risposte HTTP 200, offset 0/100/200, snapshot candidato unico; API: 299 schede entro 20 km |
| Filtro «Feste e sagre» | Sagra del Rosario di Caneva presente (`04-sagre.xml`) |
| Anteprima Rosario | Foto, descrizione, fonte TurismoFVG, Via Roma 1–Caneva e date 2–18 ottobre leggibili (`05-rosario-preview.png`) |
| Sezione «Prossimi», filtro sagre | Visibili Sagra delle Castagne e Sagra del Pan Zal con inizio 15 ottobre (`06-prossimi.xml`) |
| Coerenza del backend | Snapshot `2026-10-13T16:47:33.182692+00:00`, quattro tag `quarantined_cards` attesi; nessun tag Azalea |

Le richieste osservate sono conservate in `phone/api-phone-observed-requests.log`.
Il totale 299 è l'inventario API nel raggio, mentre il numero 40 riguarda il
filtro «Oggi»: non sono conteggi equivalenti. Le altre località e il caso
fonti scadute sono verificati tramite API/test, non dichiarati ricollaudati
visivamente sul telefono in questa sessione.

Il pilot aveva già il resolver meteo nazionale locale sulla porta 8782 non
raggiungibile; il relativo messaggio «Meteo non disponibile» non viene
considerato un esito positivo del meteo. La prova riguarda Eventi.

### Ripristino verificato

Al termine è stato rieseguito lo stesso launcher, con profilo e orologio
originali e senza l'override Eventi. Verificati:

- API Eventi nuovamente ufficiale, snapshot iniziale
  `2026-10-13T09:40:04.618654+00:00` ripristinato.
- Backend PID 12272, data plane PID 9376 e segnalazioni PID 18420 invariati,
  comprese le date di avvio. Il solo listener frontend è passato da 3168 a
  25296 per la prova, poi a 22376 per il ripristino; endpoint finale sano.
- Nessuna variabile Eventi persistente introdotta; orologio meteo invariato.
- Rimossa la sola mappatura ADB reverse aggiunta per 5174 e arrestata l'API
  temporanea 5176. Riportata in primo piano l'app ufficiale, che era aperta
  prima della prova; nessuna installazione o cancellazione dei dati app.
- Località browser Pordenone conservata, filtri riportati a Oggi/Tutti e Home.

Evidenze di confronto: `phone/pilot-before.json`, `phone/pilot-candidate.json`
e `phone/pilot-restored.json`. Il file `phone/checks.json` raccoglie ambiente,
prove, risultati e limiti; il confronto dei runtime è in
`phone/events-runtime-comparison.json`. Le prove sono locali e ignorate da Git.

## 4. Stato online letto, senza mutazioni

- Job `meteofriul-events-refresh`: un task, zero retry, timeout 900 secondi,
  account `meteofriul-events-writer`.
- Immagine worker:
  `europe-west1-docker.pkg.dev/meteo-friul/meteofriul/events-worker@sha256:926f97d9a45df8f8845d89aaa4ab9c23c51893fc39f095a01e23f7ec102c89c4`.
- Ultima esecuzione `meteofriul-events-refresh-nh5p9`: riuscita, conclusa il
  13 ottobre alle 09:48:46 UTC.
- API: revisione `meteofriul-events-00012-pfn`, traffico 100%, account reader.
- Immagine API:
  `europe-west1-docker.pkg.dev/meteo-friul/meteofriul/events-worker@sha256:3d6afce26fd089161047fc32b9d088365644a50328ccfeb4499b0066fddf3c6e`.

Sono riferimenti di confronto e ripristino da rileggere immediatamente prima
di un'eventuale distribuzione. Questo controllo non ha sincronizzato il nuovo
testo della policy e non ha alterato immagini, traffico, limiti o scheduler.

## 5. Evidenze e seguito

Evidenze locali conservate sotto `.dev-logs/events-phase0-27045887/`, ignorate
da Git: input, cataloghi, log, controlli API, metadati cloud, helper e
`manifest.json` con dimensioni e SHA-256. Le funzioni permanenti e le
correzioni sono descritte nel
[resoconto Fase 0](EVENTI_FASE_0_CORREZIONI_AUDIT_2026-10-13.md).

Il collaudo browser sul dispositivo del candidato è completato. Prossimo
passo consigliato, soggetto alla decisione del proprietario: distribuzione
controllata di worker e API, poi verifica dell'esecuzione cloud e consultazione
nella TEST nativa del nuovo backend. Il timeout Azalea del primo ciclo resta
registrato: il recupero riuscito non sostituisce la verifica di un ciclo cloud.

In questa fase non è stata effettuata una nuova promozione locale a `main`,
né alcun push GitHub. Il ramo e i commit restano locali; merge, deploy e
verifica dell'app distribuita sono operazioni distinte.
