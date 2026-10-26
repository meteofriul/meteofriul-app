# Allineamento della Web App con Android

**Stato corrente — 26 ottobre, ore 13:28:** AAB ufficiale **0.1.15 / 300038 disponibile nel test interno**, sorgente immutabile `7130c28a`, main incorporato `c2b2cfe1`. Stessi due account abilitati; produzione invariata a **0.1.14 / 300031**. Sponsor spenti. Nessuna installazione dell'agente: runtime della 300038 da provare sul Galaxy. Web dalla stessa sorgente preparata, non pubblicata. CAMS e Barcolana restano verifiche backend distinte; follow-up Eventi eliminato su richiesta, nessuna nuova automazione. [Accettazione, controlli e limiti](ANDROID_0.1.15_300038_UPLOAD_20261026.md).

**CAMS — deploy distinto del 26 ottobre:** solo job e policy aggiornati, rollback pronto; letture dei dati correnti attestate, recupero della nuova famiglia con continuità ancora da verificare. [Verbale backend](https://github.com/meteofriul/meteofriul-app/blob/4219581f17b35aa42bd346ff652058004d9cf5f0/docs/operations/CAMS_CONTINUITY_DEPLOY_20261026.md). Questo upload non modifica i servizi.

**Eventi — aggiornamento del 26 ottobre:** PR 30 integrata, CI PR/main superate; solo job Eventi e policy `events-failures` aggiornati con rollback pronto. Il secondo tentativo Barcolana usa più tempo entro lo stesso budget; la chiusura della finestra degli errori non notifica più un falso recupero. [Deploy e verifica](EVENTS_BARCOLANA_RECOVERY_DEPLOY_20261026.md). Corsa ordinaria del 27 ottobre alle 05:00 ancora da verificare; follow-up eliminato su richiesta del proprietario. Nessuna esecuzione manuale. Sponsor spenti, contratti Web/Android e pacchetti invariati.

**Antenna radar — pubblicata in main il 25 ottobre:** commit `738c6538` verificato su Brave/Galaxy in chiaro e scuro, con radar attivo e disattivo, integrato tramite [PR 28](https://github.com/meteofriul/meteofriul-app/pull/28), merge `d159ec59`. CI della PR e di main superate in tutti e tre i job. [Verbale ed evidenze](RADAR_ANTENNA_ICON_20261025.md). La AAB 300038 incorpora queste sorgenti ed è nel test interno dal 26 ottobre; Web candidata dalla stessa base, non pubblicata. Sponsor disattivati; follow-up Eventi eliminato su richiesta.

**Avvio HTTP FVG — sorgenti del 25 ottobre:** [PR 26](https://github.com/meteofriul/meteofriul-app/pull/26) integrata in main (`613fe78a`), commit della correzione `a431bd14`. 91 test locali e CI di PR/main superati. [Verbale, evidenze e limiti](WEATHER_HTTP_STARTUP_20261025.md). Il successivo deploy HTTP del 25 ottobre e la corsa avvisi delle 18:00 sono attestati nelle evidenze operative locali: source_failed=0 e tolleranze esercitate in 11/11 punti. Contratti Web/Android invariati; nessuna nuova AAB necessaria per il solo servizio HTTP.

**Sintesi per data locale — sorgenti del 25 ottobre:** [PR 24](https://github.com/meteofriul/meteofriul-app/pull/24) integrata in main (`8a47c752`); 84 test locali e CI di PR/main superati. [Verbale e limiti](SUMMARY_LOCAL_DATE_MONITOR_20261025.md). Nuovo allarme non attivato: collegamento operativo ancora da completare. Orari, Web/Android e sponsor invariati. Il controllo Eventi del 26 ottobre è concluso; il successivo follow-up del 27 ottobre è stato eliminato su richiesta.

**Aggiornamento backend del 25 ottobre:** PR 22 integrata, CI superata e solo job Eventi aggiornato. [Verbale e rollback](EVENTS_PNPENSA_BARCOLANA_DEPLOY_20261025.md). Corsa ordinaria del 26 ottobre alle 05:00 italiane fallita con Barcolana stale per ReadTimeout. Correzione del timeout e distinzione degli allarmi distribuite il 26 ottobre; recupero da verificare nella corsa del 27 ottobre. Web/Android mantengono il contratto; il recupero Barcolana non è attestato.

Regola del proprietario, 20 ottobre 2026: la Web App deve seguire la AAB,
perché chi usa iPhone accede al prodotto dal browser.

## Candidata Web storica associata alla AAB 300037 — 24 ottobre 2026

AAB 0.1.15 / 300037 e Web compilate dalla stessa sorgente
`d15edb10067b972c10e4989ebebfe6410a194f2c`, base main `0841020a` più incremento
versionCode. Incluse le correzioni delle PR 19/20. Archivio Web storico:
`release-artifacts/web-candidates/20261024-0.1.15-d15edb10/`.
Manifest `1bc0ab3316aab8ec6d879e754a23ca38ee956a9498c3aa9602f4f9a2236dff2b`.

CI del commit esatto, compilazioni Web/Android, API, CARTO, service worker,
configurazione nativa, firma e hash PASS. Sponsor disattivati. AAB disponibile
nel test interno dalle 18:52 del 24 ottobre, stessi due account; Web non pubblicata.
Nessuna installazione o deploy. Codice, registri e documenti nel ramo release;
main invariato. Ultimo pacchetto osservato sul telefono: **300037**, verificato
il 24 ottobre su Galaxy Android 14 in IT/FUR nei percorsi documentati.
Posizione e preferenze conservate, CAMS e contatore Eventi leggibili. Catalogo
Eventi aggiornato dalla corsa manuale autorizzata delle 22:24: TurismoFVG recuperata; a quella data restavano 20 schede in revisione e la prova ordinaria del 25 ottobre pendente. Per lo stato corrente vedere il verbale del 26 ottobre, che distingue la corsa effettivamente letta. [Esito e limiti](EVENTS_MANUAL_RECOVERY_20261024.md).
Contrasto del testo secondario radar scuro aperto nella 300037; correzione ora nella candidata del 26 ottobre, senza nuova prova su dispositivo.
[Prova Android e limiti](ANDROID_0.1.15_300037_DEVICE_CHECK_20261024.md). Questo non certifica il bundle Web da origine pubblica.
[Caricamento della 300037 e limiti](ANDROID_0.1.15_300037_UPLOAD_20261024.md).

Servizi/cache della candidata da origine autorizzata, Safari/iPhone e PWA
restano non verificati. Le precedenti prove Brave/Galaxy IT/FUR dei sorgenti
non sostituiscono una prova runtime della nuova AAB o della nuova Web pubblicata.
[Build e limiti](ANDROID_0.1.15_300037_BUILD_20261024.md). Il
[precedente allineamento](RELEASE_WEB_CAMS_EVENTS_ALIGNMENT_20261024.md)
e i suoi archivi restano conservati.

## Rifiniture pubblicate in main dopo la PR 19

Il 24 ottobre il commit `53bedfe4` è arrivato anche in main su GitHub tramite
la [PR 20](https://github.com/meteofriul/meteofriul-app/pull/20), merge `7813d5c4`:
transitorio iniziale aria/pollini e contatore Eventi in scuro corretti.
Verifica Brave/Galaxy in italiano e friulano, 76 test, lint e compilazione PASS;
sorgenti pubblicati identici a quelli verificati. CI della PR e
[di main](https://github.com/meteofriul/meteofriul-app/actions/runs/40107051151) verdi in tutti e tre i job.
Il ramo release è stato successivamente allineato in locale a `0841020a` e
la Web ricompilata come indicato sopra. La AAB 300036, il suo archivio Web
storico e il sito pubblico restano invariati; il solo ramo release è aggiornato su GitHub.
[Prova e limiti](CAMS_INITIAL_LOADING_EVENTS_CONTRAST_20261024.md).

## Pacchetti del 23 ottobre 2026 — AAB 300036 e Web storica

AAB **0.1.15 / 300036** e candidata Web dalla stessa sorgente `9d5ff2f415ab8b10be510eff2a0b058a8c2408ac`,
allineata a main `2d8b0c32`. Inclusa la correzione di Tempo reale; conservate
Posizione, CAMS e configurazione nativa. AAB firmata, verificata e disponibile nel test interno dalle 13:37 del 23 ottobre;
Web compilata con `-BuildOnly` e non pubblicata. Sponsor spenti, zero campagne.
Archivio canonico `release-artifacts/web-candidates/20261023-0.1.15-9d5ff2f4/`.
[Controlli, hash e limiti](ANDROID_0.1.15_300036_BUILD_20261023.md).

La candidata `16890b8c` e quella precedente da `5e9bc7dc` restano conservate.
La AAB 300035, precedente candidata interna, non contiene il fix Tempo reale.
La 300036 è stata osservata sul Galaxy il 23 ottobre: mappa e dock visibili
anche dopo avvio a freddo, Posizione conservata, aria/pollini IT/FUR e percorsi
di navigazione osservati PASS. [Prova e limiti](ANDROID_0.1.15_300036_DEVICE_CHECK_20261023.md).
Il caricamento resta attestato nel [verbale Play](ANDROID_0.1.15_300036_UPLOAD_20261023.md).
La verifica Android non sostituisce un collaudo del bundle statico Web.
Eseguita la [verifica locale IT/FUR del bundle statico](WEB_0.1.15_300036_FINAL_CHECK_20261023.md):
avvio e integrità confermati, servizi bloccati dalle regole CORS per localhost.
Il pilot della stessa sorgente ha verifiche complementari con dati reali.
I rilievi GPS, traduzioni e recupero CAMS hanno ora [correzioni locali verificate](WEB_0.1.15_300036_CORRECTIONS_20261023.md)
nel commit `cd471769`, con prova Brave/Galaxy completata e promozione
tracciata nella PR 19. Non sono contenute nella AAB 300036 o nella Web storica da `9d5ff2f4`; la nuova candidata da `0841020a` le include.
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
