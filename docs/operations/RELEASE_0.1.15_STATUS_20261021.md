# Stato release 0.1.15 e lavoro salvato — aggiornamento sorgenti del 24 ottobre 2026

**Mercati, 30 ottobre: collegamento online in preparazione.** Il servizio dedicato espone soltanto catalogo e amministrazione Mercati. Verifiche locali: 38 test backend, 8 test client, lint e compilazione Python. [Perimetro](MERCATI_ATTIVAZIONE_ONLINE_20261030.md). Non cambia la release Android/Web; distribuzione del servizio e dati remoti ancora da attestare.

**Mercati, 30 ottobre: preparazione operativa locale.** Salvate 59 bozze (13/46), con 19 aggiornamenti e 40 nuove identità, nella revisione amministrativa 1. Snapshot pubblico 0 invariato, nessuna approvazione editoriale automatica. [Evidenza](MERCATI_BOZZE_PREPARATE_20261030.md). Main, servizi online, Web e AAB invariati.

**Mercati, 30 ottobre: archivio amministrativo locale.** Collegati pannello, API e lettore condiviso Mercati/Eventi; SQLite locale persistente e provider Firestore esplicito, pubblicazione distinta dalle bozze, revisioni, sospensioni e sedi per edizione. 59 pratiche private preparate (13/46), senza attivare nuove schede. [Verifica e limiti](MERCATI_PANNELLO_VERIFICA_20261030.md). Raggio nelle Impostazioni completato separatamente nel ramo `codex/events-markets-radius-settings-20261030`, commit `f8c9ff5b`, non integrato nel checkout Mercati. Nessuna configurazione cloud, attribuzione del permesso, promozione a main, AAB o pubblicazione Web; AAB 300038 invariata.

**Mercati, 30 ottobre: banner in Eventi.** L’accesso al catalogo usa un gradiente blu scuro, testo bianco, icona di bancarella e freccia. 32 test, lint completo e compilazione di verifica PASS; sorgenti disponibili nell’anteprima locale 5174. [Modifica e limiti della verifica visiva](MERCATI_BANNER_EVENTI_20261030.md). AAB 300038, Web distribuita e catalogo invariati; nessuna promozione o pubblicazione.

**Mercati, 30 ottobre: revisione completa dei 192 casi.** Esaminati tutti i quattro lotti (25 + 96 + 6 + 65), senza residui: 59 casi utilizzabili per la preparazione editoriale corrente, di cui 46 con limiti espliciti; gli altri 133 restano storici, non confermati, in conflitto, progettati o fuori categoria. [Esiti e fonti per ogni caso](MERCATI_REVISIONE_192_20261030.md). I 192 casi non equivalgono a 192 nuovi mercati attivi. Registrata l’azione futura nel pannello per ciascuno; gestione amministrativa ancora da realizzare. Catalogo applicativo, pannello esterno, AAB 300038 e Web distribuita invariati. Nessuna promozione a main o pubblicazione in questo passaggio.

**Mercati, 30 ottobre: ricognizione territoriale e gestione futura.** Primo esame dei 215 comuni FVG, con fonti, limiti e approfondimenti distinti nel [registro per comune](MERCATI_RICOGNIZIONE_COMUNI_20261030.md). Nessuna assenza dedotta da ricerche senza risultati. Verificato in sola lettura il pannello esterno: Eventi/Scopri sono predisposti ma non collegati a Mercati; definita la [proposta di gestione di schede, edizioni, sedi e sospensioni](MERCATI_GESTIONE_PANNELLO_CONTRATTO_20261030.md). Solo ricerca e documentazione nel ramo Mercati; catalogo applicativo, pannello, AAB 300038 e Web distribuita invariati.

**Mercati, 30 ottobre: catalogazione delle fonti.** Proseguita la ricerca nel ramo `codex/mercati-integration-20261028`, allineato al main verificato: 51 fonti, 44 schede approfondite e 11 nuove candidature. Dieci schede pronte alla revisione editoriale, con limiti espliciti; date puntuali, conflitti e prove storiche conservati nel [dossier e registro](MERCATI_FONTI_CATALOGAZIONE_20261030.md). Nessuna nuova voce attivata nell'app; catalogo, AAB 300038 e Web distribuita invariati. Prova visiva Mercati e revisione FUR aperte.

**Home, 30 ottobre:** correzione tipografica approvata dal proprietario e integrata tramite [PR 36](https://github.com/meteofriul/meteofriul-app/pull/36), merge `05ec9aa9`, con il prerequisito di avvio CAMS. 50 test Home, 93 asserzioni launcher, lint, compilazione e CI PR/main PASS nei tre job. [Prove e portata del riscontro visivo](HOME_EDITORIAL_TYPOGRAPHY_20261030.md). Versioni, pacchetti Android, canali Play e pubblicazioni Web invariati.

**Avvio locale, 30 ottobre:** corretto e verificato il controllo CAMS del launcher, nel ramo `codex/local-pilot-cams-startup-20261030`: 93 asserzioni e avvio reale PASS; [diagnosi e prove](LOCAL_PILOT_CAMS_STARTUP_20261030.md). Nessuna variazione di versione, pacchetto, canale Play, pubblicazione Web o servizio cloud.

**Mercati, 29 ottobre: ricerca della copertura.** Sul ramo dedicato `codex/mercati-integration-20261028`, rilevati 74 candidati e sette date future mancanti su quattro schede esistenti. [Fonti, limiti e priorità](MERCATI_COPERTURA_RICERCA_20261029.md). Nessuna nuova voce attivata: catalogo, UI, AAB 300038, Web e servizi invariati. Orto sospeso nel proprio ramo; prova visiva Mercati e revisione FUR aperte.

**Mercati, 28 ottobre: integrazione locale verificata automaticamente.** Il lavoro salvato è ripreso nel ramo `codex/mercati-integration-20261028`: 53 schede documentate in Scopri, con collegamento alle date pubblicate in Eventi e adattamento alla navigazione corrente. 316 test distinti, lint completo e compilazione Web superati. [Prove e percorso di anteprima](MERCATI_SCOPRI_V1_LOCALE_2026-10-15.md#ripresa-sul-progetto-attuale--28-ottobre-2026). Fonti ferme al 14 ottobre; prova visiva e revisione friulana ancora aperte. Nessuna promozione a main o pubblicazione; AAB 300038 e Web distribuita invariati.

**Barcolana, 28 ottobre: diagnosi del timeout documentata.** Tre letture pubbliche complete e replay locale di collector/gate riusciti, con appuntamento futuro conservato. [Misure e limiti](EVENTS_BARCOLANA_TIMEOUT_DIAGNOSIS_20261028.md). Nessuna modifica al codice o ai timeout giustificata dalle prove attuali; causa dei fallimenti notturni e recupero del job remoto ancora da verificare. Nessun push, deploy o nuova automazione; AAB 300038 e Web invariati.

**Barcolana, 28 ottobre: controllo stagionale verificato in locale.** Sul ramo `codex/events-barcolana-seasonality`, ogni appuntamento futuro resta protetto; la fase del programma è ricavata solo dopo la verifica completa e l'archivio 2026 non qualifica automaticamente il 2027. 156 test distinti PASS. [Modifica, prove e limiti](EVENTS_BARCOLANA_SEASONALITY_20261028.md). Il timeout remoto resta aperto; nessun push, deploy o cambio di pianificazione. AAB 300038, Web e qualificazioni invariati.

**CSS Udine, 28 ottobre: correzione locale verificata.** Sul ramo `codex/events-css-stable-identity`, il controllo riconosce lo stesso spettacolo dopo un cambio di titolo e URL usando il codice ufficiale, stagione, data, comune e sede. 127 test distinti e compilazione mirata PASS; schede ambigue ancora in revisione e controlli contro perdite reali mantenuti. [Correzione, prove e limiti](EVENTS_CSS_STABLE_IDENTITY_20261028.md). Nessun push o deploy; il recupero della fonte nelle API resta da verificare. Barcolana, Magazzino, AAB 300038 e Web invariati.

**Organizzazione e controllo job, 28 ottobre, ramo locale:** indice dei documenti e [inventario dei job](JOBS_INVENTORY.md) aggiornati; nuovo profilo `controllo_job` avviato nativamente in una nuova sessione CLI. [Prima verifica in sola lettura](JOBS_READONLY_AUDIT_20261028.md): Eventi conserva tre fonti non aggiornate; CAMS ha recuperato dopo due fallimenti delle 09 UTC. Lint locale completo PASS dopo lo spostamento reversibile della cache in quarantena, con regole e toolchain prescritte invariate; nessuna correzione ai job o pianificazione di controlli periodici. Sorgenti applicativi, servizi, AAB 300038, artefatti Web e qualificazioni invariati.

**Consolidamento del 27 ottobre: completato in main.** [PR 34](https://github.com/meteofriul/meteofriul-app/pull/34) integrata nel merge `cab2b6ee`; [CI della PR](https://github.com/meteofriul/meteofriul-app/actions/runs/40585354043) e [CI di main](https://github.com/meteofriul/meteofriul-app/actions/runs/40586282824) superate nei tre job, incluso il lint completo. Consolidati agenti e confini, launcher, inventari documentali, mappa architetturale e correzioni radar/Eventi. [Evidenze e limiti](PROJECT_CONSOLIDATION_20261027.md). Originali Scopri conservati localmente; cache Python locale ancora inaccessibile al lint. AAB 300038, Web, servizi e qualificazioni esistenti invariati.

**Pordenone Pensa — correzione su main locale, 26 ottobre:** sul ramo `codex/events-programme-membership` i cinque incontri autunnali restano autonomi, con le proprie date, senza essere attribuiti al programma di settembre. 81 test IT/FUR, lint, build e replay dei quattro campioni API superati. [Verbale, ricevuta e limiti](EVENTS_PNPENSA_PROGRAMME_MEMBERSHIP_20261026.md). Verifica Brave sul Galaxy A52 superata in italiano/chiaro e friulano/scuro: tre incontri entro i 15 giorni, con dettagli corretti; gli altri due restano coperti dai test locali. Commit `759b354d` salvato e promosso su main locale dopo revisione; nessun push, PR o CI remota eseguiti in questo passaggio. Per aggiornare GitHub resta la PR obbligatoria con CI. La AAB interna 300038 e la Web candidata già archiviate restano immutate. Nessun aggiornamento dei job richiesto; sponsor invariati e spenti.

**CAMS — deploy del 26 ottobre:** [PR 32](https://github.com/meteofriul/meteofriul-app/pull/32) e CI PR/main superate; aggiornati solo job CAMS e policy, con rollback compatibile pronto. [Verbale, letture e limiti](CAMS_CONTINUITY_DEPLOY_20261026.md). Letture attuali di aria/pollini verificate su Udine e Pordenone. La famiglia già pubblicata mantiene 30 ore; il grant a 36 ore deve ancora essere verificato sulla nuova famiglia attesa dal 27 ottobre. Orari e destinatari invariati. Nessun nuovo monitor permanente o follow-up, nessuna AAB o Web rigenerata. Sponsor spenti; follow-up Eventi eliminato su richiesta del proprietario.

**Eventi — aggiornamento del 26 ottobre:** PR 30 integrata, CI PR/main superate; solo job Eventi e policy `events-failures` aggiornati con rollback pronto. Il secondo tentativo Barcolana usa più tempo entro lo stesso budget; la chiusura della finestra degli errori non notifica più un falso recupero. [Deploy e verifica](EVENTS_BARCOLANA_RECOVERY_DEPLOY_20261026.md). Corsa ordinaria del 27 ottobre alle 05:00: non ancora verificata; follow-up automatico eliminato il 26 ottobre su richiesta del proprietario. Nessuna esecuzione manuale. Sponsor spenti, contratti Web/Android e pacchetti invariati.

**Antenna radar — pubblicata in main il 25 ottobre:** commit `738c6538` verificato su Brave/Galaxy in chiaro e scuro, con radar attivo e disattivo, integrato tramite [PR 28](https://github.com/meteofriul/meteofriul-app/pull/28), merge `d159ec59`. CI della PR e di main superate in tutti e tre i job. [Verbale ed evidenze](RADAR_ANTENNA_ICON_20261025.md). Sorgenti su GitHub; ramo release, AAB, pacchetti Web e pubblicazioni applicative non aggiornati da questo intervento. Sponsor disattivati. Il controllo del 26 ottobre è concluso; il follow-up del 27 ottobre è stato successivamente eliminato su richiesta del proprietario.

**Avvio HTTP FVG — sorgenti del 25 ottobre:** [PR 26](https://github.com/meteofriul/meteofriul-app/pull/26) integrata in main (`613fe78a`), commit della correzione `a431bd14`. 91 test locali e CI di PR/main superati. [Verbale, evidenze e limiti](WEATHER_HTTP_STARTUP_20261025.md). Il successivo deploy HTTP del 25 ottobre e la corsa avvisi delle 18:00 sono attestati nelle evidenze operative locali: source_failed=0 e tolleranze esercitate in 11/11 punti. Contratti Web/Android invariati; nessuna nuova AAB necessaria per il solo servizio HTTP. Sponsor disattivati. Il controllo del 26 ottobre è concluso; il follow-up del 27 ottobre è stato successivamente eliminato su richiesta del proprietario.

**Sintesi per data locale — sorgenti del 25 ottobre:** [PR 24](https://github.com/meteofriul/meteofriul-app/pull/24) integrata in main (`8a47c752`); 84 test locali e CI di PR/main superati. [Verbale e limiti](SUMMARY_LOCAL_DATE_MONITOR_20261025.md). Nuovo allarme non attivato: collegamento operativo ancora da completare. Orari, Web/Android e sponsor invariati. Il follow-up Eventi del 27 ottobre è stato successivamente eliminato su richiesta del proprietario.

**Aggiornamento backend del 25 ottobre:** PR 22 integrata, CI superata e solo job Eventi aggiornato. [Verbale e rollback](EVENTS_PNPENSA_BARCOLANA_DEPLOY_20261025.md). Corsa ordinaria del 26 ottobre alle 05:00 italiane: `needs_review`, timeout Barcolana; Pordenone Pensa verificato. Follow-up concluso ed eliminato. Contratti Web/Android e pacchetti invariati; correzione successiva soltanto locale.

**Ultimo pacchetto prodotto:** AAB **0.1.15 / 300036** generata e verificata da `9d5ff2f4`, con main `2d8b0c32` e Tempo reale corretto. Web dalla stessa sorgente; sponsor spenti. Disponibile nel test interno dalle 13:37 del 23 ottobre e aggiornata dal proprietario via Play. Verifica sul Galaxy Android 14: PASS dei percorsi osservati, compreso Tempo reale dopo avvio a freddo; qualifica completa ancora limitata dalla matrice non esercitata. Nessuna installazione dell’agente. [Verbale corrente](ANDROID_0.1.15_300036_DEVICE_CHECK_20261023.md).

**La precedente 0.1.15 / 300035 è stata sostituita nel test interno dalla 300036.
Nella prova storica della 300035 Tempo reale risultava vuoto:
difetto riprodotto sul Galaxy dopo la segnalazione del proprietario,
promozione allora sospesa. Il difetto è risolto nella 300036 verificata sopra.** La nuova AAB 300036 è quella indicata sopra; nessuna installazione dell'agente.

Già nella prova della 300035: Posizione conservata dopo ripresa e avvio a freddo; il proprietario la conferma
attiva prima e subito dopo l'aggiornamento. Aria/pollini IT/FUR e navigazione
superano i controlli osservati; configurazione nativa presente nell'APK e
precedente errore assente all'avvio. Restano da esercitare sul telefono gli
errori temporanei GPS; Android 15/16 e grandi schermi non provati.
[Verbale sul Galaxy](ANDROID_0.1.15_300035_DEVICE_CHECK_20261023.md).

AAB 300035 e sua candidata Web storica dalla sorgente `5e9bc7dc`; CI `39917176816` e builder PASS.
Web non pubblicata, sponsor disattivati. La sospensione della promozione per
Tempo reale appartiene alla 300035; la successiva prova della 300036 è descritta
sopra. Il tentativo 300034 resta abbandonato e conservato.
[Build](ANDROID_0.1.15_300035_BUILD_20261023.md) ·
[Accettazione Play](ANDROID_0.1.15_300035_UPLOAD_20261023.md).

## Allineamento sorgenti del 24 ottobre

Il ramo `codex/release-0.1.15` contiene `cd471769` (quattro correzioni successive
alla 300036) e main `23153e54`, uniti senza conflitti in `ffa61949`. I sorgenti
frontend sono identici a quelli delle prove del 23 ottobre; i 116 test mirati
sono nuovamente superati dopo l’allineamento. Il 24 ottobre anche la prova
Brave/Galaxy IT/FUR delle quattro correzioni è PASS, nei limiti del
[verbale dedicato](WEB_POST_300036_GALAXY_20261024.md). Promozione e CI sono
tracciate nella [PR 19](https://github.com/meteofriul/meteofriul-app/pull/19).

Questa è la base sorgente comune per il prossimo pacchetto Web e Android;
non una nuova AAB o Web distribuibile. Sponsor disattivati. Nessuna nuova
versione riservata, installazione, pubblicazione o invio manuale.
[Allineamento, controlli e passaggi ancora aperti](RELEASE_WEB_SOURCE_ALIGNMENT_20261024.md).

## Promozione e GitHub dopo la PR 19

Le correzioni `53bedfe4` e il registro `dd7ea109` sono stati pubblicati tramite
la [PR 20](https://github.com/meteofriul/meteofriul-app/pull/20), merge `7813d5c4`.
Corretti il transitorio prima della prima risposta aria/pollini e il contatore
Eventi poco contrastato in scuro. Prova Brave/Galaxy IT/FUR, 76 test, lint e
compilazione PASS; hash dei sorgenti confermati prima della promozione.
[CI della PR](https://github.com/meteofriul/meteofriul-app/actions/runs/40106722957) e [CI di main](https://github.com/meteofriul/meteofriul-app/actions/runs/40107051151) entrambe verdi nei tre job.
Il ramo `codex/release-0.1.15` resta a `8fb11af8`, da riallineare prima dei
prossimi pacchetti. Nessuna nuova AAB, installazione, pubblicazione Web/Play,
modifica dei job o invio. Sponsor disattivati.
[Verbale e limiti](CAMS_INITIAL_LOADING_EVENTS_CONTRAST_20261024.md).

## Canali e rami

| Ambito | Stato attestato |
| --- | --- |
| Produzione Play | Lettura Console del 23 ottobre: 0.1.14 / 300031; nessuna promozione della 0.1.15 in produzione |
| Test interno Play | 0.1.15 / 300036 disponibile dal 23 ottobre alle 13:37; una sola lista con due account, mantenuta su conferma del proprietario; sponsor disattivati |
| Web pubblica | Pubblicazione del 21 ottobre da `1b0287c1`, versione 0.1.14; HTML e asset riconfermati il 23 ottobre. Candidata 0.1.15 aggiornata da `9d5ff2f4` preparata, non distribuita; Safari/iPhone non verificato |
| Base main incorporata nella AAB | `2d8b0c32`, PR 17 e CI 39935808248 verde. La [PR 11](https://github.com/meteofriul/meteofriul-app/pull/11) è unita in main con `eb109518`. Main su GitHub include ora `53bedfe4` tramite PR 20 (`7813d5c4`); i commit aggiunti dopo la build non cambiano la AAB |
| `codex/release-0.1.15` | Sorgente AAB `9d5ff2f4`: main `2d8b0c32`, Posizione, transitorio CAMS e configurazione nativa conservati. I verbali di build/Play/dispositivo sono seguiti dal fix frontend `cd471769` e dall’unione di main `ffa61949`. Queste nuove correzioni non sono nell’artefatto 300036 né nella Web archiviata; prova Brave/Galaxy IT/FUR del 24 ottobre PASS; promozione tracciata nella PR 19 |
| Ultimo artefatto osservato sul telefono (300036) | Sorgente `9d5ff2f415ab8b10be510eff2a0b058a8c2408ac`, AAB SHA256 `024212752b3af72f163d75849aa53c2b191ba0352e42423b11efccd2d7f8b51f`; installer Play Store; [verifica sul Galaxy](ANDROID_0.1.15_300036_DEVICE_CHECK_20261023.md) |

I commit successivi, anche quando modificano il frontend, non cambiano il
commit sorgente dell’AAB già firmata. L’allineamento conserva la configurazione
0.1.15 / 300036: non riserva un nuovo codice, non ricostruisce la AAB e non
cambia i canali pubblicati. Una futura AAB richiederà un codice superiore a
300036 e la relativa autorizzazione.

**Preparazione locale del 22 ottobre:** la guardia del ramo release consente
un'altra AAB ufficiale con nome 0.1.15 e codice crescente, anche dopo 300033
accettata da Play. Riserve aperte e codici già consumati restano bloccati.
Suite locali e audit ledger superati; nessuna nuova versione riservata o
generata. [Dettagli e limiti](ANDROID_NATIVE_CONFIG_FIX_20261022.md#numerazione-e-prossimi-passi).

## Rilievi aperti e prossima azione

| Rilievo | Evidenza e stato |
| --- | --- |
| REALTIME-LAYOUT-01 | FAIL nella 300035 installata. Fix `40af8779` approvato e in main, integrato nella AAB 300036 da `9d5ff2f4`; regressioni e build PASS, sorgenti identici alla prova Brave/Galaxy. CHIUSO nella 300036 installata da Play sul Galaxy: mappa e dock visibili in IT chiaro/FUR scuro, webcam e lista utilizzabili, conferma dopo avvio a freddo. Matrice Android restante esplicita nel nuovo verbale |
| NATIVE-CONFIG-01 | Nell'AAB 300033 mancano il JSON Capacitor e la risorsa Cordova `xml/config`. [Correzione locale del 22 ottobre](ANDROID_NATIVE_CONFIG_FIX_20261022.md): copia esplicita, keep mirato e controllo del bundle; regressioni locali superate. CHIUSO nella 300035: JSON e risorsa presenti anche nell’APK installato; avvio a freddo sul Galaxy senza il precedente errore |
| LOCATION-UPDATE-01 | Causa dell'episodio Play ancora non provata. Il 22 ottobre è stato riprodotto e corretto localmente un percorso di avvio che disattiva la preferenza dopo errori temporanei: 114 test passano. Correzione inclusa nella sorgente 300036 oggetto della PR 11. Percorsi ordinari sul Galaxy PASS; proprietario conferma preferenza attiva prima/dopo Play. Recupero da errore temporaneo sul dispositivo ancora non esercitato. [Analisi e limiti](ANDROID_LOCATION_STARTUP_20261022.md) |
| BULLETIN-MAP-01 | [Spaziatura corretta e verificata su Brave/Galaxy](BULLETIN_MAP_LABEL_SPACING_20261022.md), già in main e incorporata nella candidata. Ricontrollata nei campioni delle AAB 300035 e 300036 installate sul Galaxy il 23 ottobre |
| CAMS-TRANSITION-01 | Causa riprodotta e corretta: cache incompleta durante una nuova richiesta. Fix `53aba4ff` incluso nella AAB 300035, regressioni automatiche IT/FUR superate; rientro IT/FUR sul Galaxy senza falsa indisponibilità osservata. Con cache disponibile i valori arrivano subito: testo di caricamento intermedio non esercitato sul telefono. [Verbale](CAMS_REENTRY_LOADING_20261023.md) |
| WEB-300036-01/04 | Quattro correzioni `cd471769`: layout GPS Community, Eventi «Mostre altris», errore fonte OSMER in FUR e recupero CAMS. Test locali, browser PC e Brave/Galaxy IT/FUR superati nei casi documentati. [Prova reale e limiti](WEB_POST_300036_GALAXY_20261024.md); nuovi pacchetti ancora da preparare. [Verbale](WEB_0.1.15_300036_CORRECTIONS_20261023.md) |
| Copertura restante | Android 15/16, gesti, tablet/multi-window e percorsi con scritture o consegne reali non verificati; nessun PASS implicito |

Superate sul precedente pacchetto ufficiale 300033 le prove di avvio/ripresa, Indietro, previsioni
FVG e nazionali, temi e campione IT/FUR, Eventi, ricerca, allerte, aria/pollini,
webcam e conferma Community **senza invio**. Nessun crash osservato nella sessione.
Lo stato delle preferenze è stato riportato alla prima osservazione dell'agente,
già successiva all'aggiornamento: non certifica la migrazione dal vecchio pacchetto.

La verifica corrente non ricostruisce né sovrascrive gli artefatti precedenti.
Promozione del codice e pubblicazione restano azioni separate secondo il
[runbook Play](PLAY_AAB_RUNBOOK.md), con i limiti runtime sopra dichiarati.
La 300036 è ora installata dal proprietario; nessuna installazione dell’agente, deploy o invio manuale. [Preparazione precedente](RELEASE_0.1.15_300034_PREPARATION_20261023.md) e [verbale di build](ANDROID_0.1.15_300034_BUILD_20261023.md).

## Servizi e Web

- **ICON:** nuova corsa `20261021T000000Z` verificata; checkpoint schema 2,
  215 documenti/sidecar compatibili con i due lettori storici e sei località
  nazionali. **Aggiornamento 22 ottobre:** consumatore distribuito e corsa
  ordinaria delle 21:00 del 21 ottobre verificata: tolleranze usate in 7/7
  comuni, 42/42 valutazioni possibili, nessun candidato tempestivo da inviare.
  Tolleranza SWE e consegna FCM degli avvisi locali non esercitate in quella corsa.
  [Esiti del consumatore e riepilogo serale](JOBS_RECOVERY_DEPLOY_20261021.md).
  [Verbale ICON](ICON2I_PAYLOAD_LIMIT_DEPLOY_20261020.md).
- **Allerte FVG:** correzione distribuita e corsa ordinaria verificata; primo
  invio parziale e successiva deduplicazione documentati. La notifica ricevuta
  dal proprietario non dimostra consegna a tutti i dispositivi.
  [Verbale allerte](FVG_ALERTS_DEPLOY_20261020.md).
- **Community:** aggiornamento compatibile v2/v3 già distribuito e attivato;
  il controllo sul Galaxy non ha eseguito nuove scritture.
  [Verbale Community](COMMUNITY_0.1.15_DEPLOY_20261021.md).
- **Sponsor:** schede, sviluppo del pannello e allineamento dati restano
  sospesi fino a nuovo ordine. Ultima lettura 23 ottobre: `enabled=false`,
  zero campagne, revisione 117.
- **Web:** pubblicazione del 21 ottobre confermata; il nuovo pacchetto locale
  0.1.15 deve ancora essere pubblicato separatamente. Manifest e sorgenti comuni
  nel [verbale corrente](RELEASE_WEB_REALTIME_ALIGNMENT_20261023.md); Safari/iPhone
  resta non verificato nel [piano Web](WEB_ANDROID_RELEASE_PARITY.md).
- **Eventi, aggiornamento 22 ottobre:** correzioni distribuite, corsa ordinaria
  delle 06:00 verificata; Cinema Muto, Barcolana e Spazzapan recuperati. Restano
  12 schede in revisione e i monitor Attems/GiroFVG. La classificazione degli
  errori FCM resta un'attività distinta.
  [Verbale Eventi e limiti](JOBS_RECOVERY_DEPLOY_20261021.md).

## Registri, prove e GitHub

- [PR 11 — promozione del codice verificato e verbali della release](https://github.com/meteofriul/meteofriul-app/pull/11).
- [Verbale build e accettazione Play](https://github.com/meteofriul/meteofriul-app/blob/codex/release-0.1.15/docs/operations/ANDROID_0.1.15_BUILD_20261021.md).
- [Verbale sul Galaxy e rettifica sulla posizione](https://github.com/meteofriul/meteofriul-app/blob/codex/release-0.1.15/docs/operations/ANDROID_0.1.15_DEVICE_CHECK_20261021.md).
- [Ricevuta strutturata del dispositivo](https://github.com/meteofriul/meteofriul-app/blob/codex/release-0.1.15/release-history/android-preparation/0.1.15-20261021/device-verification.json).
- [Registro immutabile del ramo release](https://github.com/meteofriul/meteofriul-app/blob/codex/release-0.1.15/release-history/android-play/README.md).
- [Regole obbligatorie di preparazione](ANDROID_BUILD_PREVENTION_RULES.md).

Le riserve 300032 (abbandonata senza bundle) e 300033 (bundle accettato da Play)
restano consumate e immutabili nel ramo release. Non duplicare o riscrivere quei
record per la sincronizzazione documentale di main: consultarli prima di una
nuova riserva. I log privati, gli screenshot e gli artefatti firmati restano
nell'archivio locale ignorato `release-artifacts/android-play/`; non vengono
pubblicati su GitHub. Sono conservati gli hash delle evidenze nei verbali.

La CI verde controlla il codice nei commit indicati dalle esecuzioni, non
risolve i rilievi del dispositivo. CI del sorgente `39944265214`, dei record di
build `39945799912` e dell'accettazione Play `39948472277` verdi per la 300036.
Il salvataggio dell'accettazione Play segue il registro append-only previsto dal runbook.

Il 23 ottobre il proprietario ha autorizzato commit/push dei verbali e
allineamento a main dopo la prova della 300036. La PR 11 è stata unita in `eb109518`;
il suo record GitHub conserva l’esito e la CI. Il successivo allineamento del
24 ottobre è documentato separatamente: prova delle quattro correzioni
sul dispositivo completata e PR 19 promossa. Le due rifiniture ulteriori
sono anch'esse verificate e pubblicate in main tramite PR 20, con CI verde. Nessuno SHA di merge sostituisce l’identità
sorgente della AAB già firmata.
Nessuna pubblicazione Web o produzione Play è inclusa. Restano espliciti i casi
non esercitati, i vecchi worktree indipendenti e i loro file non ancora salvati;
non vengono importati né eliminati per questo allineamento.
