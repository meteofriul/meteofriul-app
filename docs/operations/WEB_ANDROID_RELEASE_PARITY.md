# Allineamento della Web App con Android

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
