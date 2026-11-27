# Allineamento della Web App con Android

**Eventi, dati pubblici del 27 novembre 2026.** La sola immagine del job
backend è stata aggiornata dopo PR 69, CI e collaudo QA; la ripresa mirata
ha reso TurismoFVG `partial` e visibile tramite l'API usata da Web e Android.
Udine e Trieste rispondono HTTP 200. Contratto API, frontend, versione,
artefatti e deployment Web/Android invariati. Questa lettura HTTP non è un
nuovo collaudo di parità su browser o dispositivo; la prima corsa ordinaria
del nuovo worker resta da osservare. [Prove e limiti](EVENTS_TURISMOFVG_TIMEOUT_REVIEW_20261127.md).

**Eventi, continuità candidata il 27 novembre 2026.** Il nuovo comando di
ripresa condizionale è soltanto sorgente backend: non cambia contratto API,
frontend o artefatti Web/Android. Non è stato attivato alcun nuovo job o
Scheduler e non è stato eseguito un nuovo collaudo su dispositivo.
[Disegno e limiti](EVENTS_CONDITIONAL_RECOVERY_DESIGN_20261127.md).

**Dati meteo, 25 novembre 2026, 20:04 UTC.** ICON nazionale pubblica il
ciclo 25 novembre 12Z e CAMS aria/pollini il ciclo 25 novembre 00Z;
Storage e HTTP pubblico sono coerenti. Le app Web e Android consumano
i dati aggiornati attraverso i contratti esistenti: nessun frontend,
versione, AAB o deployment applicativo è cambiato. Questa verifica dei
dati non equivale a un nuovo collaudo Web/Android o Safari su dispositivo.
[Evidenza](WEATHER_ICON_CAMS_RECOVERY_20261125.md).

**Dato ICON nazionale, 25 novembre 2026, 19:41 UTC.** Il job backend ha
pubblicato il ciclo `20261125T120000Z`; puntatore e manifest sono leggibili
su Storage e HTTP. CAMS aria/pollini attende lo slot delle 20:00 UTC.
Questa è una variazione dei dati serviti dalle API: versione, frontend,
artefatti e deployment delle app Web e Android non sono cambiati. Non è
un nuovo collaudo di parità su browser o dispositivo.
[Verifica del dato](WEATHER_ICON_CAMS_RECOVERY_20261125.md).

**Dati meteo, 25 novembre 2026, slot 18 UTC.** Il reader ICON FVG serve
il ciclo 25 novembre 12Z dopo il job riuscito; ICON nazionale resta
bloccato sul ciclo del 21 novembre. CAMS aria/pollini era ancora al ciclo
del 23 novembre alle 17:57 UTC. Nessun codice, artefatto o deploy delle
app Web/Android è cambiato; non è un collaudo di parità su dispositivo.
[Esiti](WEATHER_ICON_CAMS_RECOVERY_20261125.md).

**Verifica del 25 novembre 2026.** La Web pubblica serve ancora l'HTML e
l'asset principale della 0.1.14 del 21 ottobre, verificati per hash. La
AAB 0.1.15/300038 è nel test interno Play dal 26 ottobre, mentre la Web
candidata dalla sua stessa sorgente non è pubblicata. Non esiste dunque
parità fra Web pubblica e Android interno, né fra questi artefatti e il
frontend attuale di `main`. Il runtime 300038 su telefono e Safari/iPhone
restano non attestati. [Matrice e prove](APP_ALIGNMENT_STATUS_20261125.md).

**Dati CAMS e ICON, 25 novembre 2026, ore 17:31 UTC.** La ripresa della
stessa richiesta ADS non ha ancora prodotto una nuova famiglia aria/pollini;
il puntatore Storage e l'API HTTP restano alla revisione 72 del 23 novembre.
ICON nazionale resta in `manual_review`, senza nuovo dato pubblicato.
Nessuna modifica a codice/frontend, API, artefatti o deploy Web/Android e
nessun nuovo collaudo browser/dispositivo.
[Evidenza](WEATHER_ICON_CAMS_RECOVERY_20261125.md).

**ICON nazionale, 25 novembre 2026, ore 17:12 UTC.** Aggiornata soltanto
l'immagine diagnostica del job nazionale a `sha256:6fe9e498…`; Scheduler,
fence `manual_review`, API e codice frontend invariati. Il dato nazionale
resta da recuperare; la PR 63 operatore è solo una bozza con CI verde.
Nessun nuovo artefatto o deploy Web/Android e nessun nuovo collaudo su
browser o dispositivo. [Prove](WEATHER_ICON_CAMS_RECOVERY_20261125.md).

**CAMS U11, 25 novembre 2026, stato operativo.** Il backend del solo job
CAMS è passato al digest `sha256:b377e7d0…` dopo PR 61 e CI `main` verde;
Scheduler invariato. Una prova reale ha superato i nuovi metadati, ma il
prodotto aria/pollini resta in attesa ADS e non è attestato come corrente.
Il contratto API e il codice frontend delle app Web/Android non cambiano;
nessun artefatto applicativo è stato preparato o pubblicato e la parità su
dispositivo non è stata riesaminata. ICON nazionale resta bloccato dalla
fence esistente. [Prove](WEATHER_ICON_CAMS_RECOVERY_20261125.md).

**Job meteo, 25 novembre 2026.** La [PR 61](https://github.com/meteofriul/meteofriul-app/pull/61)
modifica soltanto i worker CAMS e ICON: il piano U11 mantiene le 28 variabili
e 97 ore del contratto esistente e aggiunge diagnostica sicura. Non cambia
frontend, API dell'app, artefatti Web/Android o versione; non costituisce un
collaudo di parità su Safari o dispositivo. Al controllo delle 15:34 UTC i
dati pubblici CAMS aria/pollini e ICON nazionale non erano recuperati.
[Evidenza](WEATHER_ICON_CAMS_RECOVERY_20261125.md).

**Anticipazione serale, integrata in `main` il 23 novembre 2026.** La modifica backend
di testo limitato alle temperature non cambia frontend o artefatti Web/Android.
Il solo job serale pubblico usa ora il digest `sha256:7d4596ae…`, con
scheduler invariato e prima corsa ordinaria ancora da verificare. Un job QA
isolato ha registrato una sola
notifica TEST inviata all'Android owner ed è stato eliminato; il proprietario
ha confermato ricezione e apertura del Bollettino sul dispositivo. La CI
di `main` è verde.
[Evidenza e stato dei job](OPS_JOBS_PROMOTION_20261123.md).

**Fonti Eventi, integrate in `main` il 23 novembre 2026.** I nuovi limiti di
lettura sono nel solo backend. Il collaudo Cloud completo su catalogo QA con i
checkpoint pubblici è riuscito; il solo job Eventi pubblico usa ora il digest
`sha256:d6ff27f2…`. Il catalogo pubblico resta al precedente snapshot fino
alla prossima corsa; frontend e artefatti Web/Android non sono stati
aggiornati. [Evidenza](OPS_JOBS_PROMOTION_20261123.md).

**API amministrativa operativa, 22 novembre 2026.** La
[PR 56](https://github.com/meteofriul/meteofriul-app/pull/56), integrata in
`main` con `4cab51b2` e CI `main` verde, legge log e
catalogo Eventi per il solo pannello; la revisione con tag `ops-panel-v1` ha
zero traffico app. Il pannello online è stato provato con login e viewport
360 px. Il frontend dell'app e i suoi endpoint pubblici non cambiano: nessun
nuovo artefatto Web/Android o collaudo Safari/telefono per l'app. Quattro
policy email duplicate sono state alleggerite, mentre gli avvisi importanti
restano. [Evidenza e limiti](OPERATIONAL_ALERT_ROUTING_20261122.md).

**Verifica backend del 20–22 novembre 2026.** Le sintesi mattutine sono state
inviate; le tre anticipazioni serali non sono state inviate perché la fonte
ICON non superava il controllo dei dati. L'API Eventi pubblica risponde
HTTP 200 ma segnala `degraded`: Azalea e Barcolana `stale` sono escluse
dagli eventi visibili. [Evidenza e limiti](OPERATIONAL_JOBS_CHECK_20261122.md).
Nessun contratto client, artefatto Web/Android o pubblicazione applicativa
e cambiato durante l'audit; la parita visiva e su dispositivo non e stata
riesaminata in questa verifica dei job.

**Notifiche, 19 novembre 2026 — aggiornati solo i job backend mattutino e
serale.** Il cambio di comune durante il claim ora risulta invio saltato,
senza errore del job. [PR 53](https://github.com/meteofriul/meteofriul-app/pull/53)
e CI PR/main verdi; digest Cloud Run `sha256:3811ae86...`, Scheduler e
configurazione invariati. Il payload e i contratti di Android e Web non sono
stati modificati; nessun nuovo artefatto o pubblicazione applicativa, nessuna
nuova qualifica Safari/Android. La prima corsa ordinaria resta da osservare.
[Provenienza e limiti](FORECAST_LOCATION_CHANGE_NONFAILURE_20261119.md).

**Eventi, backend pubblico del 19 novembre 2026.** Le PR 48–51 sono integrate e la CI è verde. Job e lettore Eventi usano il digest `sha256:fcf3a81c...`; una corsa completa pubblica è riuscita e il lettore `00024-vaz` ha il 100% del traffico. L'endpoint usato dalle app Web e Android risponde HTTP 200 da Udine e Trieste con 14 fonti attive `fresh`/`partial` e Spazzapan in pausa. Non sono stati creati nuovi artefatti Web/Android né eseguite pubblicazioni applicative; il contratto API resta lo stesso. Il browser del telefono ha verificato *SDENG!* nel collaudo locale, non un APK né Safari. Prima corsa ordinaria del 20 novembre ancora da osservare. [Evidenza e limiti](EVENTS_JOB_DEPLOYMENT_20261119.md).

**Eventi, job QA del 19 novembre 2026.** La
[PR 48](https://github.com/meteofriul/meteofriul-app/pull/48) ha CI verde;
il worker da commit `eb9fbfcb` ha completato un ciclo cloud su catalogo
separato. Il lettore QA con lo stesso digest ha 0% del traffico e mostra
Verdi Trieste e CSS Udine recuperati, con Spazzapan in pausa. Il catalogo
pubblico e gli artefatti Web/Android non sono cambiati. Il browser del
telefono Android ha confermato la scheda *SDENG!* con entrambe le repliche,
sede e Indicazioni; la prova non qualifica un APK o Safari.
[Evidenza](EVENTS_JOB_RECOVERY_20261119.md).

**Eventi, 19 novembre 2026.** Il controllo online ha Spazzapan in pausa
alla revisione 1, ma il lettore pubblico non lo consuma ancora. Il recupero
XML di Teatro Verdi Trieste è verificato in lettura locale; CSS Udine resta
esclusa dal catalogo pubblico per il gate di confronto. Nessun artefatto Web
o Android, endpoint pubblico o traffico Cloud Run è cambiato.
[Prove e limiti](EVENTS_SOURCE_DECISION_20261119.md). Il controllo sul client
reale resta aperto prima di promuovere il nuovo lettore.

**Eventi, collaudo isolato del 15 novembre 2026.** La
[PR 48](https://github.com/meteofriul/meteofriul-app/pull/48) aggiunge controlli
per fonte al backend e il ramo XML. Un job QA senza pianificazione ha verificato
il recupero di Teatro Verdi Trieste; il job è stato eliminato. Il lettore con
tag QA usa una copia del catalogo e ha 0% del traffico; CSS Udine e Galleria
Spazzapan restano escluse perché non verificate. Il lettore pubblico, il job
ordinario, gli artefatti Web e Android e i loro endpoint non sono cambiati.
[Prova e limiti](EVENTS_SOURCE_CONTROLS_20261115.md). La prova su Web/Android
reali resta necessaria prima di promuovere il nuovo lettore.

**Eventi, sorgenti del 15 novembre 2026.** Il ramo `codex/events-xml-recovery-20261115` modifica solo il lettore backend Teatro Verdi Trieste; 77 test mirati e lettura reale senza scritture PASS. [Prova](EVENTS_VERDI_TRIESTE_XML_RECOVERY_20261115.md). Nessun nuovo artefatto, deploy o controllo su dispositivo Web/Android: la parità delle versioni distribuite resta invariata.

**Notifiche, 12 novembre — aggiornato solo il job backend mattutino.** La correzione del testo e in `main` `b939a177` tramite [PR 46](https://github.com/meteofriul/meteofriul-app/pull/46), con CI PR/main PASS e [collaudo Android owner](NOTIFICATIONS_ALERTS_AUDIT_20261111.md) ricevuto e aperto sul Bollettino. Il job ordinario usa il digest candidato con readback `ready=true`; i canali Android e Web ricevono entrambi il testo costruito dal backend. Nessun artefatto o pubblicazione Web/Android nuova, nessuna qualifica Safari aggiunta. La parita degli artefatti pubblici non cambia.

**Sintesi mattutina, 7 novembre — job backend aggiornato.** Il testo della notifica gestisce dati di precipitazione incompleti senza dedurre assenza di pioggia. [PR 44](https://github.com/meteofriul/meteofriul-app/pull/44), CI PR/main, prova su un telefono e [readback del job](MORNING_SUMMARY_SOURCE_QUALITY_DEPLOY_20261107.md) verificati; la prima corsa ordinaria resta aperta. Frontend, contratti dati, artefatti e pubblicazioni Web/Android invariati; nessuna nuova qualifica Safari o Android.

**Sintesi mattutina e avvisi, 6 novembre — backend distribuito.** Il job mattutino ritira i token FCM invalidi confermati; le sole policy di errore mattino/sera notificano l'apertura. [Digest, CI, audit e limiti](MORNING_SUMMARY_ALERT_NOISE_DEPLOY_20261106.md). Nessun cambio al frontend o ai contratti dati Web/Android; nessun artefatto di release rigenerato o pubblicato e nessuna nuova qualifica browser/dispositivo.

**CAMS e avvisi ICON, 2 novembre — backend distribuito.** Correzione della ripresa ADS attiva nel job CAMS e due policy errori ICON aggiornate; [digest, CI, 437 test Linux e limiti](WEATHER_JOB_RECOVERY_20261102.md). Prima corsa ordinaria della nuova immagine ancora da osservare. Nessun cambio al frontend o ai contratti dati Web/Android; nessun artefatto di release rigenerato o pubblicato, nessuna nuova qualifica browser/dispositivo.

**Audit costi e servizi, 31 ottobre:** [letture e modello dei job](JOBS_COST_AUDIT_20261031.md) e [indice della copertura dei servizi](APP_SERVICE_REPORT_COVERAGE_20261031.md) salvati nel candidato ICON. Le prove mancanti su hosting e Safari/iPhone sono esplicite; questo audit non estende le qualificazioni browser/dispositivo.

**ICON, 31 ottobre — recupero automatico distribuito e attivo.** Sorgente `04ea00b2`, [PR 38](https://github.com/meteofriul/meteofriul-app/pull/38) e CI di main superate. Aggiornati i soli produttori FVG/nazionale, entrambi collaudati; attivati i tentativi dopo una, due e quattro ore tramite i due Scheduler esistenti. [Immagini, test, configurazione e limiti](ICON_AUTOMATIC_RECOVERY_DEPLOY_20261031.md). Verificata l’adozione dei checkpoint senza nuovi download GRIB; il primo caso reale di fonte in ritardo resta da osservare. Nessuna nuova build di distribuzione o pubblicazione Web/Android, nessuna attivazione Mercati/pannello.

**Home, 30 ottobre:** dimensioni e spaziature delle due schede editoriali uniformate in main tramite [PR 36](https://github.com/meteofriul/meteofriul-app/pull/36), merge `05ec9aa9`, con risultato osservato approvato dal proprietario. [Modifica e verifiche](HOME_EDITORIAL_TYPOGRAPHY_20261030.md). 50 test, lint, compilazione frontend e CI PR/main PASS nei tre job. Nessun artefatto Web/Android di release rigenerato, nessuna pubblicazione o nuova qualifica completa browser/dispositivo.

**Avvio locale, 30 ottobre:** corretto e verificato il controllo CAMS del launcher, nel ramo `codex/local-pilot-cams-startup-20261030`: 93 asserzioni e avvio reale PASS; [diagnosi e prove](LOCAL_PILOT_CAMS_STARTUP_20261030.md). Il frontend distribuito, gli artefatti Web/Android e le qualificazioni dei browser non cambiano; nessuna pubblicazione richiesta per il solo launcher locale.

**Consolidamento del 27 ottobre: completato in main.** [PR 34](https://github.com/meteofriul/meteofriul-app/pull/34) integrata nel merge `cab2b6ee`; [CI della PR](https://github.com/meteofriul/meteofriul-app/actions/runs/40585354043) e [CI di main](https://github.com/meteofriul/meteofriul-app/actions/runs/40586282824) superate nei tre job, incluso il lint completo. Consolidati agenti e confini, launcher, inventari documentali, mappa architetturale e correzioni radar/Eventi. [Evidenze e limiti](PROJECT_CONSOLIDATION_20261027.md). Originali Scopri conservati localmente; cache Python locale ancora inaccessibile al lint. AAB 300038, Web, servizi e qualificazioni esistenti invariati.

**Pordenone Pensa — correzione su main locale, 26 ottobre:** sul ramo `codex/events-programme-membership` i cinque incontri autunnali restano autonomi, con le proprie date, senza essere attribuiti al programma di settembre. 81 test IT/FUR, lint, build e replay dei quattro campioni API superati. [Verbale, ricevuta e limiti](EVENTS_PNPENSA_PROGRAMME_MEMBERSHIP_20261026.md). Verifica Brave sul Galaxy A52 superata in italiano/chiaro e friulano/scuro: tre incontri entro i 15 giorni, con dettagli corretti; gli altri due restano coperti dai test locali. Commit `759b354d` salvato e promosso su main locale dopo revisione; nessun push, PR o CI remota eseguiti in questo passaggio. Per aggiornare GitHub resta la PR obbligatoria con CI. La AAB interna 300038 e la Web candidata già archiviate restano immutate. Nessun aggiornamento dei job richiesto; sponsor invariati e spenti.

**CAMS — deploy del 26 ottobre:** [PR 32](https://github.com/meteofriul/meteofriul-app/pull/32) e CI PR/main superate; aggiornati solo job CAMS e policy, con rollback compatibile pronto. [Verbale, letture e limiti](CAMS_CONTINUITY_DEPLOY_20261026.md). Letture attuali di aria/pollini verificate su Udine e Pordenone. La famiglia già pubblicata mantiene 30 ore; il grant a 36 ore deve ancora essere verificato sulla nuova famiglia attesa dal 27 ottobre. Orari e destinatari invariati. Nessun nuovo monitor permanente o follow-up, nessuna AAB o Web rigenerata. Sponsor spenti; follow-up Eventi eliminato su richiesta del proprietario.

**Eventi — aggiornamento del 26 ottobre:** PR 30 integrata, CI PR/main superate; solo job Eventi e policy `events-failures` aggiornati con rollback pronto. Il secondo tentativo Barcolana usa più tempo entro lo stesso budget; la chiusura della finestra degli errori non notifica più un falso recupero. [Deploy e verifica](EVENTS_BARCOLANA_RECOVERY_DEPLOY_20261026.md). Corsa ordinaria del 27 ottobre alle 05:00: non ancora verificata; follow-up automatico eliminato il 26 ottobre su richiesta del proprietario. Nessuna esecuzione manuale. Sponsor spenti, contratti Web/Android e pacchetti invariati.

**Antenna radar — pubblicata in main il 25 ottobre:** commit `738c6538` verificato su Brave/Galaxy in chiaro e scuro, con radar attivo e disattivo, integrato tramite [PR 28](https://github.com/meteofriul/meteofriul-app/pull/28), merge `d159ec59`. CI della PR e di main superate in tutti e tre i job. [Verbale ed evidenze](RADAR_ANTENNA_ICON_20261025.md). Sorgenti su GitHub; ramo release, AAB, pacchetti Web e pubblicazioni applicative non aggiornati da questo intervento. Sponsor disattivati. Il controllo del 26 ottobre è concluso; il follow-up del 27 ottobre è stato successivamente eliminato su richiesta del proprietario.

**Avvio HTTP FVG — sorgenti del 25 ottobre:** [PR 26](https://github.com/meteofriul/meteofriul-app/pull/26) integrata in main (`613fe78a`), commit della correzione `a431bd14`. 91 test locali e CI di PR/main superati. [Verbale, evidenze e limiti](WEATHER_HTTP_STARTUP_20261025.md). Il successivo deploy HTTP del 25 ottobre e la corsa avvisi delle 18:00 sono attestati nelle evidenze operative locali: source_failed=0 e tolleranze esercitate in 11/11 punti. Contratti Web/Android invariati; nessuna nuova AAB necessaria per il solo servizio HTTP. Sponsor disattivati. Il controllo del 26 ottobre è concluso; il follow-up del 27 ottobre è stato successivamente eliminato su richiesta del proprietario.

**Sintesi per data locale — sorgenti del 25 ottobre:** [PR 24](https://github.com/meteofriul/meteofriul-app/pull/24) integrata in main (`8a47c752`); 84 test locali e CI di PR/main superati. [Verbale e limiti](SUMMARY_LOCAL_DATE_MONITOR_20261025.md). Nuovo allarme non attivato: collegamento operativo ancora da completare. Orari, Web/Android e sponsor invariati. Il follow-up Eventi del 27 ottobre è stato successivamente eliminato su richiesta del proprietario.

**Aggiornamento backend del 25 ottobre:** PR 22 integrata, CI superata e solo job Eventi aggiornato. [Verbale e rollback](EVENTS_PNPENSA_BARCOLANA_DEPLOY_20261025.md). Corsa ordinaria del 26 ottobre alle 05:00 italiane: `needs_review`, timeout Barcolana; Pordenone Pensa verificato. Follow-up concluso ed eliminato. Contratti Web/Android e pacchetti invariati; correzione successiva soltanto locale.

Regola del proprietario, 20 ottobre 2026: la Web App deve seguire la AAB,
perché chi usa iPhone accede al prodotto dal browser.

## Sorgenti allineate il 24 ottobre 2026

Il ramo release incorpora main `23153e54` e il fix `cd471769`, mediante
`ffa61949`, senza differenze frontend rispetto alle correzioni già verificate.
Nuova esecuzione dei 116 test mirati: PASS. Il 24 ottobre completata anche
la [prova reale Brave/Galaxy IT/FUR](WEB_POST_300036_GALAXY_20261024.md).
Promozione e CI sono tracciate nella [PR 19](https://github.com/meteofriul/meteofriul-app/pull/19).
Web e Android dovranno usare questa stessa base approvata alla prossima build.
[Verbale corrente](RELEASE_WEB_SOURCE_ALIGNMENT_20261024.md).

## Rifiniture pubblicate in main dopo la PR 19

Il 24 ottobre il commit `53bedfe4` è arrivato anche in main su GitHub tramite
la [PR 20](https://github.com/meteofriul/meteofriul-app/pull/20), merge `7813d5c4`:
transitorio iniziale aria/pollini e contatore Eventi in scuro corretti.
Verifica Brave/Galaxy in italiano e friulano, 76 test, lint e compilazione PASS;
sorgenti pubblicati identici a quelli verificati. CI della PR e
[di main](https://github.com/meteofriul/meteofriul-app/actions/runs/40107051151) verdi in tutti e tre i job.
Il ramo release rimane a `8fb11af8`: il suo riallineamento servirà prima dei
prossimi pacchetti Web e Android, dalla stessa base frontend approvata.
AAB 300036, archivio Web e sito pubblico non sono aggiornati da questo push.
[Prova e limiti](CAMS_INITIAL_LOADING_EVENTS_CONTRAST_20261024.md).

## Ultimi pacchetti prodotti il 23 ottobre 2026 — Tempo reale

AAB **0.1.15 / 300036** e candidata Web dalla stessa sorgente `9d5ff2f415ab8b10be510eff2a0b058a8c2408ac`,
allineata a main `2d8b0c32`. Inclusa la correzione di Tempo reale; conservate
Posizione, CAMS e configurazione nativa. AAB firmata, verificata e disponibile nel test interno dalle 13:37 del 23 ottobre;
Web compilata con `-BuildOnly` e non pubblicata. Sponsor spenti, zero campagne.
Archivio canonico `release-artifacts/web-candidates/20261023-0.1.15-9d5ff2f4/`.
[Controlli, hash e limiti](ANDROID_0.1.15_300036_BUILD_20261023.md).

La candidata `16890b8c` e quella precedente da `5e9bc7dc` restano conservate.
La AAB 300035, precedente candidata interna, non contiene il fix Tempo reale.
La 300036 è ora l'ultimo pacchetto osservato sul Galaxy: mappa e dock visibili
anche dopo avvio a freddo, Posizione conservata, aria/pollini IT/FUR e percorsi
di navigazione osservati PASS. [Prova e limiti](ANDROID_0.1.15_300036_DEVICE_CHECK_20261023.md).
Il caricamento resta attestato nel [verbale Play](ANDROID_0.1.15_300036_UPLOAD_20261023.md).
La verifica Android non sostituisce un collaudo del bundle statico Web.
Eseguita la [verifica locale IT/FUR del bundle statico](WEB_0.1.15_300036_FINAL_CHECK_20261023.md):
avvio e integrità confermati, servizi bloccati dalle regole CORS per localhost.
Il pilot della stessa sorgente ha verifiche complementari con dati reali.
I rilievi GPS, traduzioni e recupero CAMS hanno ora [correzioni locali verificate](WEB_0.1.15_300036_CORRECTIONS_20261023.md)
nel commit `cd471769`, con prova Brave/Galaxy completata e promozione
tracciata nella PR 19. Non sono contenute nella AAB 300036 o nella Web archiviata.
L'episodio iniziale CAMS non aveva una traccia temporale; è stato riprodotto e
corretto il meccanismo di recupero da errore di trasporto, senza dichiarare
retroattivamente provata ogni causa di quell'osservazione.
Prima della pubblicazione restano collaudo dei servizi del bundle da origine
autorizzata e aggiornamento cache; Safari/iPhone e PWA non verificati. Il sito pubblico nell'ultima lettura
del 23 ottobre rimane 0.1.14: HTML con `main-D-Nry2Xb.js` e asset SHA256
`c5ab69f0a4b63df56ea2254b60fcf829e91b30274632653f000962ac1aa010ca`,
identico alla ricevuta del 22 ottobre. La parità pubblicata non è ancora raggiunta.

## Base comune e confini

Usare lo stesso frontend approvato in main per Web e Android ufficiale. La TEST
serve al collaudo: marchio, package, simulazioni Community, endpoint locali e
servizi esclusi dalla TEST non vanno importati nella Web App pubblica.
Il numero di versione uguale è necessario ma non dimostra la parità del codice.
Una modifica solo nativa può differire: annotarne il motivo. Meteo, Eventi,
testi, temi, Community e contratti dati devono invece avere un comportamento
coerente nei due canali.

## Preparazione, prima di chiedere la pubblicazione

1. Identificare commit frontend approvato, versione, controlli Android già fatti
   e differenze rispetto al Web pubblico. Conservare manifest con hash degli
   asset e dei sorgenti; non usare una vecchia cartella dist come candidata.
2. Controllare versione frontend/lock/Android e configurazione Cloudflare:
   esperienza ufficiale, CARTO, endpoint assoluti, meteo FVG/nazionale, Eventi,
   Community e service worker. Nessuna impostazione speciale della TEST.
3. Per un candidato distribuibile usare `scripts/deploy-cloudflare-app.ps1`
   con `-BuildOnly`, passando API, revisione e commit backend verificati e,
   quando necessario, digest ed evidenza Cloud Build. L'health 200 non prova
   il legame fra immagine e sorgenti. Se tale legame manca, una compilazione
   frontend resta un'anteprima, non un pacchetto autorizzato alla pubblicazione.
4. Verificare nel browser IT/FUR, temi chiaro/scuro, selezione giorno/ora,
   aggiornamento FVG, località nazionale, catalogo Eventi, navigazione e
   Community senza invii reali. I controlli simulati vanno distinti dalle
   letture dei servizi veri. La UI pilot va avviata soltanto con il launcher
   canonico su 5174; un'anteprima statica del bundle Web va identificata come
   tale e non sostituisce la prova pilot o Android.
5. Su Safari di un iPhone reale verificare browser e Aggiungi a Home: avvio,
   safe area, barre del browser, tastiera, scorrimento, ripresa, ricaricamento,
   tema/lingua/località conservati, refresh dei dati e passaggio dalla versione
   precedente. Annotare modello e iOS. Fino ad allora: NON VERIFICATO.
6. Verificare cache HTTP, nomi asset con hash, manifest e service worker.
   Il worker Firebase attuale gestisce notifiche: non è una prova di uso
   offline. Nessuna attivazione di notifiche o iscrizione durante il collaudo
   senza autorizzazione. Non promettere servizi nativi nel browser.

## Pubblicazione coordinata, solo se autorizzata

Prima chiudere gli eventuali prerequisiti dei servizi; poi ricontrollare il
binding API subito prima della build/pubblicazione. Registrare esplicitamente
l'ordine e l'eventuale intervallo fra Web e Play. L'assenza di una nuova AAB
non impedisce di preparare il Web, ma non autorizza nessuna pubblicazione.

Per Cloudflare verificare da root `npx wrangler whoami`: profilo `meteofriul`,
account `b74cf20dd75712b35313b69c191c97d5`, email `meteofriul@gmail.com`, progetto
`meteofriul-app-bcee09e`. Non usare l'account globale o il sito `meteofriul.it`.
Usare lo script di deploy protetto, senza rimuoverne i controlli.

Conservare prima l'identità del deployment Web precedente. Dopo pubblicazione
confrontare HTML/asset realmente serviti con gli hash della candidata,
verificare una sessione esistente e una nuova, poi annotare esiti e limiti.
Un rollback Web deve ripristinare il deployment noto mantenendo la compatibilità
con i contratti dati attivi. Non è autorizzato implicitamente dalla preparazione.

## Aggiornamento dello stato

Quando cambia lo stato di sorgenti, verifiche o canali, aggiornare insieme
README, stato della release e questo piano. Ogni dichiarazione deve indicare
la data della verifica e distinguere codice salvato/promosso, pacchetto
generato, test interno e pubblicazione effettiva. Conservare i verbali storici
e gli hash degli artefatti; non attribuire una correzione a una build precedente.
I limiti del collaudo rimangono aperti finché non esiste una nuova evidenza.

## Evidenza minima per ogni aggiornamento

- Commit e versione frontend comune; AAB/versionCode solo se realmente prodotti.
- Manifest e hash del pacchetto Web, API/revisione/digest/backend verificati.
- Funzioni allineate, differenze native motivate, esiti dei controlli locali.
- Safari/iPhone e PWA: PASS, FAIL o NON VERIFICATO con evidenza.
- Deployment pubblico effettivo e precedente per rollback, dopo autorizzazione.
- Nessun riferimento a chiavi private, token o credenziali negli allegati.

Preparazioni precedenti: [300034](RELEASE_0.1.15_300034_PREPARATION_20261023.md) e [300035](ANDROID_0.1.15_300035_BUILD_20261023.md). Sono verbali storici; la candidata corrente è identificata sopra.

La Web pubblica è già stata aggiornata il 21 ottobre da `1b0287c1`, versione
0.1.14: non contiene le correzioni successive del 22 ottobre. Il precedente
[candidato del 20 ottobre](WEB_APP_CANDIDATE_20261020.md) resta un verbale storico,
non l'identità della nuova candidata o dello stato pubblico corrente.

# Eventi, preparazione dei controlli per fonte (15 novembre 2026)

Il ramo `codex/events-source-controls-20261115` e la
[PR 48](https://github.com/meteofriul/meteofriul-app/pull/48) in bozza
intervengono su job, API Eventi e API amministrativa. CI PR PASS nei tre job.
Non cambiano il bundle frontend, la Web app pubblicata o
l'APK/AAB Android. Nessun artefatto o endpoint è stato distribuito da questo
ramo. Prima dell'attivazione va verificato il client Eventi Web e Android
contro il catalogo con una fonte in pausa e dopo una verifica riuscita;
vedere [il passaggio operativo](EVENTS_SOURCE_CONTROLS_20261115.md).
