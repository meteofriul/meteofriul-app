# Meteo Friûl

**Mercati, 30 ottobre: banner in Eventi.** L’accesso al catalogo usa un gradiente blu scuro, testo bianco, icona di bancarella e freccia. 32 test, lint completo e compilazione di verifica PASS; sorgenti disponibili nell’anteprima locale 5174. [Modifica e limiti della verifica visiva](docs/operations/MERCATI_BANNER_EVENTI_20261030.md). Singoli appuntamenti e dati invariati; nessuna promozione o pubblicazione.

**Mercati, 30 ottobre: revisione completa dei 192 casi.** Esaminati tutti i quattro lotti (25 + 96 + 6 + 65), senza residui: 59 casi utilizzabili per la preparazione editoriale corrente, di cui 46 con limiti espliciti; gli altri 133 restano storici, non confermati, in conflitto, progettati o fuori categoria. [Esiti e fonti per ogni caso](docs/operations/MERCATI_REVISIONE_192_20261030.md). I 192 casi non equivalgono a 192 nuovi mercati attivi. Registrata l’azione futura nel pannello per ciascuno; gestione amministrativa ancora da realizzare. Catalogo applicativo, pannello esterno, AAB 300038 e Web distribuita invariati. Nessuna promozione a main o pubblicazione in questo passaggio.

**Mercati, 30 ottobre: ricognizione territoriale e gestione futura.** Primo esame dei 215 comuni FVG, con fonti, limiti e approfondimenti distinti nel [registro per comune](docs/operations/MERCATI_RICOGNIZIONE_COMUNI_20261030.md). Nessuna assenza dedotta da ricerche senza risultati. Verificato in sola lettura il pannello esterno: Eventi/Scopri sono predisposti ma non collegati a Mercati; definita la [proposta di gestione di schede, edizioni, sedi e sospensioni](docs/operations/MERCATI_GESTIONE_PANNELLO_CONTRATTO_20261030.md). Solo ricerca e documentazione nel ramo Mercati; catalogo applicativo, pannello, AAB 300038 e Web distribuita invariati.

**Mercati, 30 ottobre: catalogazione delle fonti.** Proseguita la ricerca nel ramo `codex/mercati-integration-20261028`, allineato al main verificato: 51 fonti, 44 schede approfondite e 11 nuove candidature. Dieci schede pronte alla revisione editoriale, con limiti espliciti; date puntuali, conflitti e prove storiche conservati nel [dossier e registro](docs/operations/MERCATI_FONTI_CATALOGAZIONE_20261030.md). Nessuna nuova voce attivata nell'app; catalogo, AAB 300038 e Web distribuita invariati. Prova visiva Mercati e revisione FUR aperte.

**Home, 30 ottobre: correzione integrata in main.** «I perché del Friûl» e «Memoria del giorno» condividono dimensione del titolo, metadati e spaziature. Risultato osservato approvato dal proprietario, 50 test locali e CI della [PR 36](https://github.com/meteofriul/meteofriul-app/pull/36) superati; merge `05ec9aa9`, incluso il prerequisito di avvio CAMS. [Modifica, prove e limiti](docs/operations/HOME_EDITORIAL_TYPOGRAPHY_20261030.md). CI di main superata in tutti e tre i job; pacchetti e pubblicazioni applicative invariati.

**Avvio locale, 30 ottobre:** corretto il blocco del launcher dopo le 30 ore CAMS, riconoscendo l'estensione esplicita a 36 ore. 93 asserzioni, preflight cloud e avvio locale superati; frontend 5174 e API 8002 sani. Correzione preparata nel ramo `codex/local-pilot-cams-startup-20261030`. [Diagnosi e prove](docs/operations/LOCAL_PILOT_CAMS_STARTUP_20261030.md). Pacchetti, pubblicazioni e servizi cloud invariati.

**Mercati, 29 ottobre: ricerca della copertura.** Sul ramo dedicato `codex/mercati-integration-20261028`, rilevati 74 candidati e sette date future mancanti su quattro schede esistenti. [Fonti, limiti e priorità](docs/operations/MERCATI_COPERTURA_RICERCA_20261029.md). Nessuna nuova voce attivata: catalogo, UI, AAB 300038, Web e servizi invariati. Orto sospeso nel proprio ramo; prova visiva Mercati e revisione FUR aperte.

**Mercati, 28 ottobre: integrazione locale verificata automaticamente.** Il lavoro salvato è ripreso nel ramo `codex/mercati-integration-20261028`: 53 schede documentate in Scopri, con collegamento alle date pubblicate in Eventi e adattamento alla navigazione corrente. 316 test distinti, lint completo e compilazione Web superati. [Prove e percorso di anteprima](docs/operations/MERCATI_SCOPRI_V1_LOCALE_2026-10-15.md#ripresa-sul-progetto-attuale--28-ottobre-2026). Fonti ferme al 14 ottobre; prova visiva e revisione friulana ancora aperte. Nessuna promozione a main o pubblicazione; AAB 300038 e Web distribuita invariati.

**Barcolana, 28 ottobre: diagnosi del timeout documentata.** Tre letture pubbliche complete e replay locale di collector/gate riusciti, con appuntamento futuro conservato. [Misure e limiti](docs/operations/EVENTS_BARCOLANA_TIMEOUT_DIAGNOSIS_20261028.md). Nessuna modifica al codice o ai timeout giustificata dalle prove attuali; causa dei fallimenti notturni e recupero del job remoto ancora da verificare. Nessun push, deploy o nuova automazione; AAB 300038 e Web invariati.

**Barcolana, 28 ottobre: controllo stagionale verificato in locale.** Sul ramo `codex/events-barcolana-seasonality`, ogni appuntamento futuro resta protetto; la fase del programma è ricavata solo dopo la verifica completa e l'archivio 2026 non qualifica automaticamente il 2027. 156 test distinti PASS. [Modifica, prove e limiti](docs/operations/EVENTS_BARCOLANA_SEASONALITY_20261028.md). Il timeout remoto resta aperto; nessun push, deploy o cambio di pianificazione. AAB 300038, Web e qualificazioni invariati.

**CSS Udine, 28 ottobre: correzione locale verificata.** Sul ramo `codex/events-css-stable-identity`, il controllo riconosce lo stesso spettacolo dopo un cambio di titolo e URL usando il codice ufficiale, stagione, data, comune e sede. 127 test distinti e compilazione mirata PASS; schede ambigue ancora in revisione e controlli contro perdite reali mantenuti. [Correzione, prove e limiti](docs/operations/EVENTS_CSS_STABLE_IDENTITY_20261028.md). Nessun push o deploy; il recupero della fonte nelle API resta da verificare. Barcolana, Magazzino, AAB 300038 e Web invariati.

**Organizzazione e controllo job, 28 ottobre, ramo locale:** indice dei documenti e [inventario dei job](docs/operations/JOBS_INVENTORY.md) aggiornati; nuovo profilo `controllo_job` avviato nativamente in una nuova sessione CLI. [Prima verifica in sola lettura](docs/operations/JOBS_READONLY_AUDIT_20261028.md): Eventi conserva tre fonti non aggiornate; CAMS ha recuperato dopo due fallimenti delle 09 UTC. Lint locale completo PASS dopo lo spostamento reversibile della cache in quarantena, con regole e toolchain prescritte invariate; nessuna correzione ai job o pianificazione di controlli periodici. Sorgenti applicativi, servizi, AAB 300038, artefatti Web e qualificazioni invariati.

**Consolidamento del 27 ottobre: completato in main.** [PR 34](https://github.com/meteofriul/meteofriul-app/pull/34) integrata nel merge `cab2b6ee`; [CI della PR](https://github.com/meteofriul/meteofriul-app/actions/runs/40585354043) e [CI di main](https://github.com/meteofriul/meteofriul-app/actions/runs/40586282824) superate nei tre job, incluso il lint completo. Consolidati agenti e confini, launcher, inventari documentali, mappa architetturale e correzioni radar/Eventi. [Evidenze e limiti](docs/operations/PROJECT_CONSOLIDATION_20261027.md). Originali Scopri conservati localmente; cache Python locale ancora inaccessibile al lint. AAB 300038, Web, servizi e qualificazioni esistenti invariati.

**Pordenone Pensa — correzione su main locale, 26 ottobre:** sul ramo `codex/events-programme-membership` i cinque incontri autunnali restano autonomi, con le proprie date, senza essere attribuiti al programma di settembre. 81 test IT/FUR, lint, build e replay dei quattro campioni API superati. [Verbale, ricevuta e limiti](docs/operations/EVENTS_PNPENSA_PROGRAMME_MEMBERSHIP_20261026.md). Verifica Brave sul Galaxy A52 superata in italiano/chiaro e friulano/scuro: tre incontri entro i 15 giorni, con dettagli corretti; gli altri due restano coperti dai test locali. Commit `759b354d` salvato e promosso su main locale dopo revisione; nessun push, PR o CI remota eseguiti in questo passaggio. Per aggiornare GitHub resta la PR obbligatoria con CI. La AAB interna 300038 e la Web candidata già archiviate restano immutate. Nessun aggiornamento dei job richiesto; sponsor invariati e spenti.

**CAMS — deploy del 26 ottobre:** [PR 32](https://github.com/meteofriul/meteofriul-app/pull/32) e CI PR/main superate; aggiornati solo job CAMS e policy, con rollback compatibile pronto. [Verbale, letture e limiti](docs/operations/CAMS_CONTINUITY_DEPLOY_20261026.md). Letture attuali di aria/pollini verificate su Udine e Pordenone. La famiglia già pubblicata mantiene 30 ore; il grant a 36 ore deve ancora essere verificato sulla nuova famiglia attesa dal 27 ottobre. Orari e destinatari invariati. Nessun nuovo monitor permanente o follow-up, nessuna AAB o Web rigenerata. Sponsor spenti; follow-up Eventi eliminato su richiesta del proprietario.

**Eventi — aggiornamento del 26 ottobre:** PR 30 integrata, CI PR/main superate; solo job Eventi e policy `events-failures` aggiornati con rollback pronto. Il secondo tentativo Barcolana usa più tempo entro lo stesso budget; la chiusura della finestra degli errori non notifica più un falso recupero. [Deploy e verifica](docs/operations/EVENTS_BARCOLANA_RECOVERY_DEPLOY_20261026.md). Corsa ordinaria del 27 ottobre alle 05:00: non ancora verificata; follow-up automatico eliminato il 26 ottobre su richiesta del proprietario. Nessuna esecuzione manuale. Sponsor spenti, contratti Web/Android e pacchetti invariati.

**Antenna radar — pubblicata in main il 25 ottobre:** commit `738c6538` verificato su Brave/Galaxy in chiaro e scuro, con radar attivo e disattivo, integrato tramite [PR 28](https://github.com/meteofriul/meteofriul-app/pull/28), merge `d159ec59`. CI della PR e di main superate in tutti e tre i job. [Verbale ed evidenze](docs/operations/RADAR_ANTENNA_ICON_20261025.md). Sorgenti su GitHub; ramo release, AAB, pacchetti Web e pubblicazioni applicative non aggiornati da questo intervento. Sponsor disattivati. Il controllo del 26 ottobre è concluso; il follow-up del 27 ottobre è stato successivamente eliminato su richiesta del proprietario.

**Avvio HTTP FVG — sorgenti del 25 ottobre:** [PR 26](https://github.com/meteofriul/meteofriul-app/pull/26) integrata in main (`613fe78a`), commit della correzione `a431bd14`. 91 test locali e CI di PR/main superati. [Verbale, evidenze e limiti](docs/operations/WEATHER_HTTP_STARTUP_20261025.md). Il successivo deploy HTTP del 25 ottobre e la corsa avvisi delle 18:00 sono attestati nelle evidenze operative locali: source_failed=0 e tolleranze esercitate in 11/11 punti. Contratti Web/Android invariati; nessuna nuova AAB necessaria per il solo servizio HTTP. Sponsor disattivati. Il controllo del 26 ottobre è concluso; il follow-up del 27 ottobre è stato successivamente eliminato su richiesta del proprietario.

**Sintesi per data locale — sorgenti del 25 ottobre:** [PR 24](https://github.com/meteofriul/meteofriul-app/pull/24) integrata in main (`8a47c752`); 84 test locali e CI di PR/main superati. [Verbale e limiti](docs/operations/SUMMARY_LOCAL_DATE_MONITOR_20261025.md). Nuovo allarme non attivato: collegamento operativo ancora da completare. Orari, Web/Android e sponsor invariati. Il follow-up Eventi del 27 ottobre è stato successivamente eliminato su richiesta del proprietario.

**Aggiornamento backend del 25 ottobre:** PR 22 integrata, CI superata e solo job Eventi aggiornato. [Verbale e rollback](docs/operations/EVENTS_PNPENSA_BARCOLANA_DEPLOY_20261025.md). Corsa ordinaria del 26 ottobre alle 05:00 italiane: `needs_review`, timeout Barcolana; Pordenone Pensa verificato. Web e Android mantengono lo stesso contratto; pacchetti e pubblicazioni invariati, sponsor disattivati. Correzione successiva distribuita il 26 ottobre, come indicato sopra; recupero da verificare nella corsa del 27 ottobre.

**Prima di preparare una release Android:** leggere le [regole obbligatorie di preparazione e recupero dagli errori](docs/operations/ANDROID_BUILD_PREVENTION_RULES.md), insieme al [runbook Play](docs/operations/PLAY_AAB_RUNBOOK.md).

Meteo Friûl è un'app indipendente dedicata al Friuli-Venezia Giulia. Riunisce
meteo locale, bollettino regionale, allerte ufficiali, radar, webcam, eventi e
contenuti culturali; l'interfaccia è disponibile in italiano e friulano.

> Ultima lettura Web del 23 ottobre 2026: `meteofriul.app` serve la
> pubblicazione del 21 ottobre, versione `0.1.14`, sorgente `1b0287c1`.
> La candidata **0.1.15** con le successive correzioni di main, inclusi aria e pollini e Tempo reale, è ora
> archiviata dalla stessa base della AAB 300036; non è pubblicata. Le quattro
> correzioni successive sono nel ramo release e richiedono nuovi pacchetti.
>
> La Web App deve seguire la release Android: è anche il canale per chi usa
> iPhone dal browser. Il [percorso di allineamento Web/Android](docs/operations/WEB_ANDROID_RELEASE_PARITY.md)
> richiede sorgenti e funzionalità coerenti, oltre alla verifica Safari/iPhone.

**Ultima AAB generata:** **0.1.15 / 300036**, sorgente `9d5ff2f4`, include main `2d8b0c32` e il fix Tempo reale. Firmata e verificata, CI verde; candidata Web dalla stessa sorgente. **Disponibile nel test interno dal 23 ottobre alle 13:37**, con la lista di due account confermata dal proprietario. Sponsor disattivati. La 300036 è stata verificata sul Galaxy A52 Android 14 dopo aggiornamento Play: Tempo reale visibile anche dopo avvio a freddo, Posizione conservata, aria/pollini IT/FUR e percorsi di navigazione osservati PASS. La matrice Android 15/16 e i casi non esercitati restano aperti. [Prova sul dispositivo](docs/operations/ANDROID_0.1.15_300036_DEVICE_CHECK_20261023.md). [Caricamento e limiti](docs/operations/ANDROID_0.1.15_300036_UPLOAD_20261023.md).

**Rilievo storico della 300035: Tempo reale mostrava una schermata vuota.
Difetto riprodotto dopo la segnalazione del proprietario; promozione allora
sospesa.** Il difetto è risolto e verificato nella 300036, come documentato sopra. La prima verifica era mirata e aveva omesso questa sezione.
I risultati positivi sotto non equivalgono a qualifica completa della release.
[Difetto ed evidenze](docs/operations/ANDROID_0.1.15_300035_DEVICE_CHECK_20261023.md#realtime-layout-01--difetto-riprodotto-dopo-la-segnalazione-del-proprietario).

**Precedente release interna del 23 ottobre 2026:** AAB **0.1.15 / 300035**,
caricata alle 09:59 con una sola lista e un account, sostituita alle 13:37 dalla 300036. Produzione invariata a 0.1.14 / 300031. Include main `f9e178b2`, transitorio aria/pollini,
conservazione della Posizione e configurazione nativa. CI e builder completo
PASS; la Web associata alla 300035 era preparata dalla stessa sorgente `5e9bc7dc`, non pubblicata. La candidata locale corrente è quella indicata sopra.
Sponsor disattivati. Il tentativo 300034 è conservato e abbandonato.
[Artefatto e controlli](docs/operations/ANDROID_0.1.15_300035_BUILD_20261023.md) ·
[Accettazione Play e limiti](docs/operations/ANDROID_0.1.15_300035_UPLOAD_20261023.md).

La **300035 è stata aggiornata dal proprietario via Play Store e verificata
sul Galaxy A52 Android 14**: posizione conservata nei percorsi osservati,
aria/pollini IT/FUR disponibili senza falsa indisponibilità nei campioni di
rientro, avvio nativo e navigazione verificati. Il proprietario conferma
Posizione attiva prima e subito dopo l'aggiornamento. Restano non esercitati
l'errore GPS temporaneo sul telefono e la matrice Android 15/16 e schermi grandi.
[Verifica e limiti](docs/operations/ANDROID_0.1.15_300035_DEVICE_CHECK_20261023.md).
La 300033 rimane una prova storica distinta. La [PR 11](https://github.com/meteofriul/meteofriul-app/pull/11)
è stata unita in main (`eb109518`); questo non ha pubblicato Web o produzione Play.
[Stato e prossimi passi](docs/operations/RELEASE_0.1.15_STATUS_20261021.md).

**Allineamento sorgenti del 24 ottobre:** il ramo `codex/release-0.1.15` incorpora
main `23153e54` e le quattro correzioni `cd471769`: recupero aria/pollini,
impaginazione del messaggio GPS e due traduzioni friulane. Le correzioni sono
verificate anche su Brave del Galaxy in italiano e friulano il 24 ottobre.
La prova reale richiesta da AGENTS.md è completata; promozione e CI sono
tracciate nella [PR 19](https://github.com/meteofriul/meteofriul-app/pull/19).
[Esiti e limiti sul Galaxy](docs/operations/WEB_POST_300036_GALAXY_20261024.md).
La AAB 300036 e il suo archivio Web non contengono queste quattro modifiche.
Nessun nuovo codice versione riservato. [Verbale di allineamento](docs/operations/RELEASE_WEB_SOURCE_ALIGNMENT_20261024.md).

**Aggiornamento GitHub del 24 ottobre, dopo PR 19:** correzioni `53bedfe4`
pubblicate in main tramite la [PR 20](https://github.com/meteofriul/meteofriul-app/pull/20),
merge `7813d5c4`: transitorio iniziale aria/pollini e contatore Eventi in
scuro corretti. Verifica Brave/Galaxy IT/FUR, 76 test, lint e compilazione
superati; [CI di main](https://github.com/meteofriul/meteofriul-app/actions/runs/40107051151) verde in tutti e tre i job.
Il ramo release rimane a `8fb11af8`, da riallineare prima dei prossimi pacchetti.
AAB 300036, archivio Web e canali pubblicati invariati; questi pacchetti non
includono le nuove correzioni. Sponsor disattivati.
[Evidenze e limiti](docs/operations/CAMS_INITIAL_LOADING_EVENTS_CONTRAST_20261024.md).

**Job meteo ICON-2I — verifica del 21 ottobre 2026:** nuova corsa pubblicata,
checkpoint schema 2, 215 documenti e sidecar e campione nazionale verificati.
Le tolleranze sono esercitate nei dati reali. Il 21 ottobre sono stati aggiornati
anche il job avvisi (valutazione per fenomeno e sidecar abilitato) e il job Eventi
(Spazzapan e recupero dei timeout). Riepilogo serale e avvisi locali verificati:
42 invii serali accettati da FCM; avvisi con 7/7 comuni valutabili e tolleranze
esercitate, senza candidati tempestivi da inviare. Anche la corsa Eventi del
22 ottobre alle 06:00 è verificata: Cinema Muto, Barcolana e Spazzapan recuperati;
restano 12 schede in revisione e i rilievi dei monitor Attems/GiroFVG.
[Esiti e limiti](docs/operations/JOBS_RECOVERY_DEPLOY_20261021.md).
[Verifica del produttore e limiti](docs/operations/ICON2I_PAYLOAD_LIMIT_DEPLOY_20261020.md).

**Allerte FVG e Community:** aggiornamenti già distribuiti e verificati nei
rispettivi [verbali allerte](docs/operations/FVG_ALERTS_DEPLOY_20261020.md) e
[Community](docs/operations/COMMUNITY_0.1.15_DEPLOY_20261021.md).
Sponsor, pannello e allineamento dati sponsor restano disattivati.

**Storico TEST — verifica locale del 19 ottobre 2026:** il candidato integrato con testi
IT/FUR, Indietro Android, conferma/ricevuta Community, aggiornamento FVG e nuovi
temi delle previsioni ha superato le verifiche sulla TEST `.6` (`300037`) del
Galaxy A52. Il lavoro approvato è integrato in main; le impostazioni speciali
della TEST restano escluse. Questa prova storica precede la AAB ufficiale 300033
e non sostituisce la sua verifica. Evidenze e limiti nel [verbale sul telefono](docs/operations/APP_INTEGRATED_TEST_DEVICE_20261019.md).

[Apri l'app web](https://meteofriul.app) ·
[Sostieni il progetto](https://ko-fi.com/meteofriul)

## Canali — sorgenti aggiornate il 24 ottobre; ultima lettura Web e Play il 23 ottobre 2026

| Canale | Stato |
| --- | --- |
| Web | `0.1.14` pubblicata il 21 ottobre; archivio `0.1.15` da `9d5ff2f4` non distribuito. Quattro correzioni successive verificate anche su Brave/Galaxy IT/FUR, tracciate nella PR 19; nuovi pacchetti ancora da confezionare. Safari/iPhone non verificato |
| API | FastAPI su Cloud Run, chiamata direttamente via HTTPS da Web e Android |
| Android | `0.1.15` (`300036`) disponibile nel test interno con fix Tempo reale; verifica sul Galaxy Android 14 dei percorsi osservati PASS, incluso Tempo reale dopo avvio a freddo. La qualifica completa resta distinta. Limiti GPS/Android 15–16/grandi schermi espliciti nel verbale. [Esito e limiti](docs/operations/RELEASE_0.1.15_STATUS_20261021.md) |
| Google Play | Produzione `0.1.14` (`300031`) nella lettura del 23 ottobre; `0.1.15` (`300036`) solo nel test interno, una lista con due account confermata dal proprietario. Sponsor disattivati |
| Landing `meteofriul.it` | Gestita e distribuita da un progetto separato |
| Push | Generazione `play-beta-v1`, App Check in enforce, Android/Web abilitati e lotti Firestore/FCM da 200 elementi |
| Sintesi mattutina | Una notifica quotidiana alle 07:30 `Europe/Rome`, con apertura diretta del Bollettino |
| Sostegno | Link Ko-fi esterno attivo, senza funzioni riservate |

L'app è gratuita e può includere contenuti pubblicitari, promozionali o
sponsorizzati. Il sostegno è volontario e non cambia le funzionalità
disponibili. Ko-fi si apre all'esterno: non sono presenti SDK di pagamento, IAP
o entitlement.

## Funzionalità

| Sezione | Contenuto |
| --- | --- |
| Home | Meteo locale, scena illustrata, sintesi del bollettino, almanacco ed eventi vicini |
| Bollettino | Testo ARPA FVG-OSMER, dati locali, allerte ufficiali e radar nazionale Radar-DPC |
| Territorio | Webcam regionali e segnalazioni community anonime, limitate e moderate |
| Eventi | Eventi locali raccolti da fonti territoriali con collegamento alla fonte |
| Scopri | Località selezionata, ricorrenze, storia, santi, proverbi e contenuti editoriali |
| Impostazioni | Lingua, tema, posizione, preferenze di notifica Web/Android, fonti, crediti e cache |

La ricerca manuale usa un catalogo canonico di 215 Comuni FVG. Con il GPS, il
Comune viene determinato dai confini ISTAT 2026 e la localita visibile viene
accettata solo se corroborata dal catalogo toponomastico IRDAT della Regione
FVG; per esempio Vigonovo resta visualizzato come localita del Comune di
Fontanafredda. La registrazione push conserva Comune, identita canonica della
localita, istante e fascia di precisione del fix; non conserva le coordinate
GPS. Gli Avvisi locali richiedono una posizione recente e precisa e falliscono
chiusi quando tale prova manca; un Comune o una localita canonica scelti
manualmente restano invece un target esplicito finche l'utente non li cambia.
Le fonti ufficiali e di terzi restano attribuite: Meteo Friûl non rappresenta
ARPA FVG, OSMER, Protezione Civile FVG, Regione o gli altri enti citati.

## Impostazioni predefinite

| Impostazione | Valore iniziale |
| --- | --- |
| Lingua | Italiano; friulano selezionabile e persistente |
| Tema | Sistema; chiaro e scuro selezionabili |
| Località web | Udine è il placeholder iniziale finché non viene scelta o rilevata una località |
| Primo avvio Web | Due azioni esplicite: richiesta GPS, poi richiesta notifiche; entrambe rinviabili |
| Posizione automatica | Proposta al primo avvio e attivata solo dopo il consenso del browser o di Android |
| Primo avvio Android | Richiesta GPS, poi richiesta notifiche |
| Allerte ufficiali Web/Android | Preferenza attiva; consegna soltanto alle registrazioni attestate ed eleggibili |
| Avvisi meteo locali Web/Android | Preferenza attiva; richiedono una località canonica e i gate di eleggibilità |
| Sintesi meteo mattutina | Invio quotidiano alle 07:30 per le registrazioni eleggibili; tap verso il Bollettino |

La posizione Android in primo piano usa un percorso rapido a tre stadi: fix
recente validato, fix bilanciato e, solo se necessario, alta precisione. Viene
controllata all'avvio, al ritorno in primo piano e, mentre l'app resta visibile,
al massimo ogni 3 minuti. Per mantenere aggiornato il target degli Avvisi anche
con app chiusa, l'utente puo concedere separatamente `Consenti sempre`:
Android usa allora un geofence di uscita e un controllo periodico WorkManager.
Non esiste un servizio GPS continuo ne' una notifica permanente di posizione.
La scelta manuale di un Comune disattiva la posizione automatica. Sul Web GPS
e notifiche richiedono due gesti separati perché il browser consente di aprire
ciascun prompt di permesso solo dopo un'azione dell'utente; Android mantiene
l'ordine GPS → notifiche.

Le preferenze `Allerte` e `Avvisi` sono entrambe attive per impostazione
predefinita su Web e Android. `Allerte` rende la registrazione eleggibile agli
invii ufficiali regionali e non è una sottoscrizione comunale. Gli `Avvisi`
meteo locali usano una pipeline separata, conservativa e comunale. Android è
ammesso soltanto con una release Play riconosciuta e licenziata; il Web usa il
proprio App ID attestato. Il valore operativo `200` è la dimensione dei lotti
Firestore/FCM, non un tetto al numero complessivo di registrazioni, e non
sostituisce i gate App Check, versione e preferenza. Le allerte mostrate dentro
l'app restano visibili indipendentemente dalle preferenze push.

Il fix preciso viene inviato soltanto nel body HTTPS della route App Check
dedicata e viene risolto subito contro confini ISTAT e localita IRDAT. Firestore
conserva Comune/localita canonici, orario e accuratezza, ma non latitudine o
longitudine GPS. Senza il permesso in background gli Avvisi automatici
falliscono chiusi quando l'evidenza scade; le Allerte ufficiali regionali non
dipendono da questo target.

## Web e Android Play

In produzione il browser usa una base API HTTPS assoluta e chiama direttamente
Cloud Run: Cloudflare Pages serve soltanto gli asset statici. In sviluppo Vite
mantiene il proxy relativo `/api`. La release Android incorpora a sua volta
una base HTTPS esplicita, verificata dal gate AAB insieme al worker nativo.

Nella release Android corrente:

- package: `com.meteofriul.app`;
- orientamento: solo verticale;
- localizzazione: one-shot in primo piano; geofence e WorkManager in background
  soltanto dopo il consenso separato `Consenti sempre`, senza servizio GPS
  permanente;
- splash screen: sfondo Blu Friuli e icona centrale;
- link Ko-fi: aperto esternamente;
- `Segnala`: App Check Debug soltanto nel preflight locale; Play Integrity nella
  release;
- registrazione push: token FCM nativo protetto da App Check/Play Integrity e
  ammesso soltanto per identità Play consentite;
- allerte ufficiali push: implementate con modalità fail-closed
  `off`/`dry_run`/`send`;
- avvisi locali: pipeline meteo separata e deduplicata in modalità `send`, con
  sorgenti ICON e comportamento fail-closed quando manca l'evidenza di
  località richiesta; log sanitizzati con TTL di 14 giorni;
- sintesi mattutina: notifica quotidiana deduplicata alle 07:30
  `Europe/Rome`, con deep link al Bollettino;
- release R8: `minifyEnabled` e `shrinkResources` attivi, profilo ottimizzato e
  `mapping.txt` verificato e archiviato dal gate Play;
- debug WebView: ammesso esclusivamente nel preflight owner e disattivato nella
  release;
- firma e distribuzione Play: configurate; la AAB `0.1.8` è stata accettata nel
  test interno e l'upload resta sempre un'azione esplicita.

Il runtime Web pubblicato usa:

- onboarding in due passaggi espliciti, prima GPS e poi notifiche;
- Firebase Cloud Messaging tramite Firebase Installation ID (FID) e service
  worker locale `/firebase-messaging-sw.js`;
- Firebase App Check con reCAPTCHA Enterprise;
- `Segnala` e mutazioni push abilitate soltanto quando App Check Web è
  configurato nella build e l'App ID Web è autorizzato dal backend;
- preferenze e semantica degli avvisi uguali all'APK.

La chiave pubblica VAPID è stata generata ed è versionata nella configurazione
di produzione; `VITE_FIREBASE_VAPID_KEY` consente un override locale esplicito.
Il codice Web non inizializza
Analytics. La lettura delle segnalazioni community resta pubblica; creazione,
conferma, annullamento, flag di moderazione e registrazione/revoca push sono
fail-closed senza un token App Check valido. La `0.1.8` pubblica è stata
verificata con service worker, registrazione push e API HTTPS correnti.

Le segnalazioni Territorio sono UGC strutturati ed effimeri: otto fenomeni
predefiniti, nessun testo, foto, profilo o nome, posizione pubblica sul Comune
canonico e scadenza di 60 minuti. Il client permette di segnalare il contenuto e
di nascondere localmente una fonte anonima fino al rinnovo della sua `sourceKey`
opaca giornaliera, comunque per non piu' di 24 ore. La chiave genera sul
dispositivo uno pseudonimo friulano amichevole e non espone identificatori
interni. Il `client_id` casuale nasce e resta memorizzato localmente, viene
trasmesso soltanto con le mutazioni e il backend ne conserva chiavi/hash
pseudonimi scoped: non e' un account o una registrazione pubblica del dispositivo,
ma non va descritto come assenza totale di identificatori. Report e fonte interna
scadono dopo 60 minuti, cooldown dopo 45 minuti, conferme entro la scadenza
dell'ultimo report attivo del gruppo, contatori antiabuso entro 2 ore e flag o
blocchi amministrativi eventuali entro 24 ore. La cancellazione fisica TTL
Firestore e' asincrona. Ogni flag nasconde subito il contenuto al segnalante e
crea un record privato temporaneo; non esiste un hide globale automatico basato
sul numero di flag. Un operatore conserva uno strumento privato per un'eventuale
rimozione o blocco temporaneo. Per la prima beta non sono richiesti ne' attivi
job, scheduler o email automatiche di moderazione. Il gate completo e' in
`docs/operations/COMMUNITY_MODERATION_GATE.md`; l'handoff privacy/Data Safety
e' in `docs/operations/COMMUNITY_PRIVACY_DATA_SAFETY_HANDOFF.md`.

Il rango personale e' separato dal feed pubblico effimero. Il backend conserva
un riepilogo pseudonimo per 365 giorni dall'ultima convalida o revoca e
assegnazioni idempotenti per episodio per 365 giorni dal relativo evento:
nessun `client_id` grezzo e nessun punto sono
pubblicati. Un punto va soltanto all'autore dopo corroborazione indipendente;
`Tutto tranquillo` e i votanti sono esclusi, con cap di tre punti al giorno
`Europe/Rome`. Questo nuovo trattamento riapre il gate privacy/Data Safety e
richiede due ulteriori policy TTL `ACTIVE` prima di un rilascio ufficiale.

Le registrazioni push supportano Android e Web/PWA. Il backend opera in modalità
`play_beta`, con App ID separati, generazione `play-beta-v1`, versioni Android
ammesse fino a `0.1.8+300025` e lotti Firestore/FCM da 200 elementi, senza un
tetto complessivo implicito. Il job degli Avvisi locali gira ogni ora, quello
delle Allerte ufficiali ogni due ore e la Sintesi mattutina ogni giorno alle
07:30, sempre nel fuso `Europe/Rome`.
La consegna FCM e il tap verso il Bollettino sono stati verificati con Android
in primo piano, in background e con processo normalmente chiuso, oltre che sul
Web. Un vero `Forza arresto` Android blocca invece FCM finché l'app non viene
riaperta, come previsto dal sistema operativo. Build HTTPS e test E2E restano
gate obbligatori per qualunque nuova release o modifica alla consegna.

Gli aggiornamenti sullo stesso telefono si installano con `adb install -r`,
così da preservare dati applicativi e ID installazione. Una disinstallazione o
la cancellazione dei dati genera un nuovo ID: prima di una nuova registrazione
va rimossa manualmente dal backend la precedente installazione owner.

Le allerte ufficiali della Protezione Civile FVG usano una cache regionale
separata da meteo e bollettino comunali: restano immediatamente visibili dopo un
avvio a freddo o un cambio località fino alla scadenza ufficiale, anche durante
un errore temporaneo delle fonti. Solo una scadenza o una conferma regionale di
assenza allerta può rimuoverle.

Il provider App Check Play Integrity è stato validato attraverso la build
firmata `0.1.8` distribuita nel test interno Google Play. I token Debug sono
individuali per dispositivo e non devono essere salvati nel repository,
nell'APK, nei documenti o negli screenshot.

## Architettura

```text
frontend/                React 19, Vite 8, UI web e wrapper Capacitor
frontend/src/            schermate, dominio, servizi, testi e dati condivisi
frontend/android/        wrapper Android: release e varianti pilota
android/launcher-assets/ sorgenti grafiche e inventari delle icone Android
backend/                 API modulare FastAPI, fonti e persistenza
contracts/               fixture e invarianti dei contratti runtime
scripts/                 avvio locale, export dati e guardrail di rilascio
firebase.json            Hosting, SPA e rewrite /api
```

Le fonti originali e le lavorazioni editoriali recuperate per Scopri sono
raccolte nell'[archivio Scopri](docs/archive/scopri/README.md), separato dal
runtime. L'indice e i checksum sono versionabili; i materiali originali sono
locali ed esclusi da Git, da includere esplicitamente nei backup del progetto.

Flusso web principale previsto:

```text
Browser -> Cloudflare Pages (asset statici)
Browser -> Cloud Run API -> fonti/cache/Firestore/Firebase
```

Il backend UI3 è autonomo dal monolite storico. La persistenza community in
produzione è fail-closed: non degrada silenziosamente su memoria locale. Le
allerte conservano l'ultimo stato confermato ancora valido e dichiarano sempre
fonte e modalità, senza trasformare un errore in una falsa assenza.

### Codice condiviso e possibilità futura iPhone

Ricognizione documentale del **27 ottobre 2026**, sui sorgenti `08af2032`.
**Android e Web restano le priorità.** Una futura app iPhone è una possibilità
da mantenere percorribile, senza avviarne ora lo sviluppo o fissare una
scadenza. Questa mappa identifica i punti da conservare e quelli da adattare
soltanto se il proprietario deciderà di iniziare quel lavoro.

Il frontend comune usa React/Vite e Capacitor `8.5.1`. La build produce i file
Web che Capacitor include nel wrapper Android; Gradle genera APK/AAB. Restano
validi i comandi e i guardrail esistenti: in particolare il builder Play
gestisce già preparazione degli asset e sincronizzazione prevista, senza
richiedere un `android:sync` manuale prima del suo avvio.

"Già condiviso" indica codice e regole riutilizzati dal prodotto attuale.
La compatibilità nativa iOS dovrà essere verificata separatamente: oggi
`frontend/ios/` e la dipendenza `@capacitor/ios` non sono presenti.

| Area | Già condiviso | Specifico Android oggi | Necessario per iPhone, se e quando si avvierà il lavoro |
| --- | --- | --- | --- |
| **API e dati** | Servizi HTTP, contratti dei dati, logica di dominio e cache; stesso backend per le informazioni del prodotto. | Selezione dell'indirizzo HTTPS nativo tramite `VITE_ANDROID_API_BASE`; origine del contenitore autorizzata dal backend come `https://localhost`. | Definire un profilo di indirizzi nativi iOS e l'origine esatta da autorizzare nel backend. Il percorso `/api` del browser e le estensioni CORS attuali, limitate a HTTPS, non attestano il supporto iOS. Conservare validazione degli indirizzi e controlli sulle origini. |
| **Posizione** | Scelta manuale della località, risoluzione geografica, controlli di qualità e distinzione tra posizione del telefono e Comune mostrato; acquisizione browser separata. | L'adapter del plugin standard Geolocation è abilitato solo per Android; sono presenti anche il bridge `MeteoAndroid` e codice nativo dedicato al background. | Collegare e verificare l'acquisizione in primo piano, i permessi Apple e i casi di rifiuto o revoca, conservando la scelta manuale. Valutare separatamente l'eventuale background: non è un requisito per la prima prova di compilazione. |
| **Notifiche** | Preferenze, contenuti degli avvisi e destinazioni nell'app; percorso Web con Firebase Messaging e service worker. | Adapter push nativo, canali Android, impostazioni di sistema e token FCM. Client di registrazione, contratto e invio backend distinguono oggi soltanto `android` e `web`. | Progettare registrazione e consegna iOS, permessi e apertura dell'app. Il plugin standard restituisce un token APNs su iOS: va scelta e verificata l'integrazione con FCM/APNs, estendendo esplicitamente il contratto backend senza trattare iOS come Android. |
| **Firebase e protezioni** | Servizi backend Firebase/Firestore e verifica server dei token App Check; sul Web sono presenti SDK Firebase e App Check con reCAPTCHA Enterprise. | Plugin nativo App Check e provider Play Integrity per la release; configurazione Firebase Android dedicata. | Registrare/configurare l'app Apple, scegliere e integrare il provider App Check nativo e autorizzare la sua identità nel backend. L'adapter nativo non Android e l'allowlist backend oggi non implementano iOS. Mantenere il rifiuto delle richieste non valide e le regole di privacy. |

Riferimenti verificati nei sorgenti:

- API: [selezione client](frontend/src/services/apiConfig.js) e
  [origini autorizzate dal backend](backend/app/main.py).
- Posizione: [orchestrazione](frontend/src/services/deviceLocation.js),
  [adapter Capacitor](frontend/src/services/capacitorLocationAdapter.js),
  [bridge Android](frontend/src/services/nativeLocationAdapter.js) e
  [background](frontend/src/services/backgroundLocationAdapter.js).
- Notifiche: [adapter nativo](frontend/src/services/nativePushAdapter.js),
  [registrazione client](frontend/src/services/pushDeviceRegistration.js),
  [percorso Web](frontend/src/services/firebaseWebMessaging.js),
  [contratto backend](backend/app/contracts/push.py) e
  [invio](backend/app/push/fcm.py).
- Firebase: [adapter App Check](frontend/src/services/firebaseAppCheckAdapter.js),
  [provider Web](frontend/src/services/firebaseWebAppCheck.js),
  [plugin Android](frontend/android/app/src/main/java/com/meteofriul/app/MeteoFirebaseAppCheckPlugin.java)
  e [verifica server](backend/app/infrastructure/app_check.py).

Per mantenere aperta questa strada, le nuove funzioni possono continuare a
condividere schermate e regole di prodotto, lasciando le differenze del
telefono negli adapter e nei progetti nativi. Si aggiorna questa mappa quando
un intervento modifica uno dei confini sopra; non occorre spostare cartelle,
duplicare le quattro sezioni, installare dipendenze Apple o introdurre
astrazioni preventive. Landing e pannello restano progetti esterni,
coordinati attraverso collegamenti pubblici e contratti API esistenti.

Un'eventuale prima prova iOS richiederà una decisione separata: ambiente Mac
con Xcode compatibile, pacchetto Capacitor iOS allineato, wrapper e profilo
di compilazione dedicati, poi verifica nel simulatore e su iPhone. Le versioni
richieste andranno ricontrollate allora. Compilazione, completezza delle
funzioni native e pubblicazione sono traguardi distinti. I riferimenti
ufficiali per quel futuro lavoro sono [Capacitor iOS](https://capacitorjs.com/docs/ios),
[Geolocation](https://capacitorjs.com/docs/apis/geolocation),
[notifiche native](https://capacitorjs.com/docs/apis/push-notifications),
[Firebase Messaging Apple](https://firebase.google.com/docs/cloud-messaging/ios/get-started)
e [App Check Apple](https://firebase.google.com/docs/app-check/ios/app-attest-provider).

L'accesso da Safari o da Aggiungi a Home resta il percorso Web/PWA, con la
propria verifica su iPhone reale secondo il
[runbook di parità Web/Android](docs/operations/WEB_ANDROID_RELEASE_PARITY.md).
Questo aggiornamento documentale non attesta prove iOS, non cambia la
qualificazione delle AAB esistenti e lascia invariati build, permessi,
protezioni e servizi remoti. I dossier architetturali datati restano evidenze
del rispettivo stato storico.

## Sviluppo locale

Prerequisiti:

- Node.js `22.17.1`;
- npm `10.9.2`;
- Python `3.13`;
- PowerShell su Windows;
- Android Studio con JBR 21 soltanto per il wrapper Android.

Preparazione iniziale:

```powershell
python -m venv backend\venv
backend\venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
npm --prefix frontend ci
```

Avvio tecnico ordinario dalla radice del repository:

```powershell
.\scripts\start-dev.ps1 -Restart
```

Servizi avviati:

- frontend Vite: `http://localhost:5173`;
- API UI3: `http://127.0.0.1:8002`;
- health API: `http://127.0.0.1:8002/healthz`.

Comandi utili:

```powershell
.\scripts\start-dev.ps1 -CheckOnly
.\scripts\start-dev.ps1 -Stop
```

Questo launcher è autonomo e non cerca più backend o repository storici in
cartelle adiacenti. Serve ai test tecnici ordinari; non rappresenta la variante
pilota.

Per vedere e validare la app pilota usare invece esclusivamente:

```powershell
.\scripts\start-local-weather-pilot.ps1 -WeatherCloud
```

Se la toolchain richiesta è estratta in una directory utente separata, indicarla
esplicitamente senza cambiare l'installazione globale o il PATH permanente:

```powershell
$pilotNode = Join-Path $env:LOCALAPPDATA "MeteoFriul\toolchains\node-v22.17.1-win-x64"
.\scripts\start-local-weather-pilot.ps1 -WeatherCloud -NodeDirectory $pilotNode -CheckOnly
.\scripts\start-local-weather-pilot.ps1 -WeatherCloud -NodeDirectory $pilotNode
```

`-NodeDirectory` richiede Node e npm nelle versioni di `frontend/package.json`;
un percorso esplicito non valido blocca l'avvio, senza fallback globale. Il PATH
selezionato vale soltanto per il frontend e i suoi figli. Per riavviare il
frontend posseduto aggiungere `-RestartFrontend`; per fermare la preview usare
`.\scripts\start-local-weather-pilot.ps1 -Stop`, anche senza la toolchain.

La pilota è esposta su `http://127.0.0.1:5174/`. Se il reader cloud non è
disponibile, il launcher può usare uno snapshot locale soltanto con un
`-WeatherTestNow` esplicito e compatibile con la finestra dichiarata dallo
snapshot. `STARTUP_PROMPT.md` contiene la procedura breve e il percorso
canonico del progetto.

Il runtime normale usa il flag assente oppure `?uiV3=0`. `?uiV3=1` sostituisce
soltanto la Home con il laboratorio dimostrativo e non va usato per validare i
dati reali.

## Test e qualità

Frontend:

```powershell
Push-Location frontend
npm test
npm run lint
Remove-Item Env:VITE_ANDROID_API_BASE -ErrorAction SilentlyContinue
$env:VITE_API_BASE = "/api"
npm run build
Pop-Location
```

Backend:

```powershell
Push-Location backend
.\venv\Scripts\python.exe -m unittest discover -s tests -v
.\venv\Scripts\python.exe -m compileall -q app
Pop-Location
```

Guardrail dello strumento di preview Hosting:

```powershell
.\scripts\deploy-hosting-preview-rest.contract.tests.ps1
.\scripts\deploy-hosting-preview-rest.tests.ps1
```

La CI esegue test, lint e build frontend; test e compilazione backend; test del
tool di preview Hosting. La compilazione Gradle Android resta un controllo
locale descritto nel runbook del pilot.

## Build e rilascio: web e Android restano separati

`npm run build` e `npm run build:android` scrivono entrambi in `frontend/dist`.
Non distribuire mai sul web un `dist` generato in modalità Android.

Per una build web locale, `VITE_API_BASE` resta `/api`. La build Cloudflare
deve invece ricevere come `VITE_API_BASE` l'URL HTTPS assoluto della revisione
Cloud Run approvata, comprensivo di `/api`; `VITE_ANDROID_API_BASE` non deve
essere presente nell'ambiente Web. Il valore incorporato va verificato nel
bundle prima di collegare il dominio pubblico.

Il deploy di produzione non va eseguito direttamente da `frontend/dist`. Usare
il comando fail-closed, che costruisce in una cartella temporanea, verifica il
binding nel bundle e controlla l'account Wrangler prima di pubblicare:

```powershell
.\scripts\deploy-cloudflare-app.ps1 `
  -ApiBase "https://<TAG>---<SERVIZIO>-<HASH>.a.run.app/api" `
  -ExpectedRevision "meteofriul-api-<SCOPO>-<COMMIT7>" `
  -ExpectedBackendCommit "<COMMIT_BACKEND_40>"
```

Il comando rifiuta `/api`, endpoint Cloud Run non tagged, variabili Android
presenti nella build Web, worktree non committati e account Cloudflare diversi
da quello Meteo Friûl. Prima della build risolve realmente il tag tramite
Google Cloud, verifica revisione attesa, commit backend identificato nel nome,
stato `Ready`, digest dell'immagine e `/api/healthz`; ripete il controllo prima
e dopo il deploy per intercettare spostamenti del tag durante la procedura. Un
deploy reale richiede inoltre che `HEAD` coincida con il branch remoto.
`-BuildOnly` esegue i controlli Cloud Run e del bundle senza pubblicare.

La parità Web richiede inoltre le variabili pubbliche `VITE_FIREBASE_*`
documentate in `frontend/.env.example`. App Check usa la site key reCAPTCHA
Enterprise; FCM Web richiede anche `VITE_FIREBASE_VAPID_KEY`. La chiave VAPID è
configurazione pubblica del bundle, non una credenziale server, ed è versionata
nella configurazione di produzione. Una build incompleta deve restare fail-closed e
mostrare la funzione come non configurata.

La mappa `Territorio` della sola pilota usa CARTO Positron quando la build
riceve `VITE_TERRITORY_CARTO_API_KEY`; senza chiave, o al primo errore di
caricamento delle tessere CARTO, conserva OpenStreetMap come fallback senza
rimontare Leaflet. La chiave CARTO è client-side e deve essere limitata e
monitorata. Le tessere sono richieste direttamente al provider: non introdurre
proxy/cache server, cache applicative o pacchetti offline. Le attribuzioni
CARTO e OpenStreetMap restano visibili sulla mappa.

Per la build Android locale della pilota, configurare la chiave in
`frontend/.env.android-local-pilot.local`. Vite compila quella variante con
la modalità `android-local-pilot`, quindi il file della pilota Web
`frontend/.env.local-pilot.local` non viene caricato automaticamente.

Nella pilota Web, il meteo FVG continua a usare il data-plane autonomo. Le
località italiane esplicitamente fuori FVG usano invece il prefisso Vite
dedicato `/__national-weather-api`, inoltrato all'API Cloud ordinaria senza
l'header della pilota. Il target predefinito è la revisione tagged pubblica
usata dall'app; per un collaudo controllato può essere sostituito con
`VITE_NATIONAL_WEATHER_PROXY_TARGET`, che deve essere una sola origine HTTPS
senza path, query o credenziali. La pilota Android usa direttamente
`VITE_ANDROID_API_BASE`. Questa selezione è preventiva e non introduce fallback
automatici tra provider.

`VITE_TERRITORY_BASEMAP_URL` permette un futuro provider alternativo e ha
precedenza sulla chiave CARTO. Prima di attivare CARTO in produzione vanno
verificati con la chiave reale gli header di cache, le restrizioni Web/Android
e l'assenza di watermark: una risposta grafica con chiave invalida potrebbe
non generare `tileerror` e quindi non attivare il fallback automatico.

Per il solo preflight debug owner, `VITE_ANDROID_API_BASE` deve essere l'URL
HTTPS tagged approvato. Su questa postazione Codex deve eseguire
`npm run android:sync` e Gradle direttamente fuori dal sandbox per evitare i
falsi `EPERM` Windows su `frontend/dist`. Il preflight non e' distribuibile e
non dimostra Play Integrity. La procedura completa e il fallback unico sono in
`ANDROID_PILOT_RUNBOOK.md`.

Per i tester usare esclusivamente il candidato AAB protetto di Google Play,
senza eseguire prima un `android:sync` manuale:

```powershell
pwsh -NoProfile -File .\scripts\build-play-aab.ps1 `
  -ApiBase "https://<TAG>---<SERVIZIO>-<HASH>.a.run.app/api" `
  -CommunityApiBase "https://meteofriul-community-49007668366.europe-west1.run.app/api" `
  -ExpectedRevision "meteofriul-api-<SCOPO>-<COMMIT7>" `
  -ExpectedBackendCommit "<COMMIT_BACKEND_40>" `
  -ExpectedLatestPlayVersionCode <ULTIMO_VERSION_CODE_PLAY_O_0> `
  -BundletoolPath "C:\secure\bundletool-all.jar" `
  -ExpectedBundletoolSha256 "<SHA256_BUNDLETOOL_ATTESO>" `
  -ExpectedUploadCertificateSha256 "<SHA256_UPLOAD_KEY>"
```

La build protetta richiede PowerShell 7 e il supporto
`ConvertFrom-Json -DateKind`; Windows PowerShell 5.1 viene rifiutato prima dei
preflight. Lo script Play costruisce gli asset in `%TEMP%`, incorpora e verifica
separatamente l'API meteo generale e l'API Community ufficiale, mantiene
allineati React e worker nativo dove previsto, verifica tag–revisione–commit,
firma e identita', riserva la versione nel ledger append-only e archivia AAB e
manifesto senza upload automatico. Firebase App Distribution e
`build-private-test-apk.ps1` sono congelati come storico e non sono un canale
tester corrente.

Il gate Community combina un read-back LIVE fresco, nel quale le collection
vuote sono ammesse, con evidenza storica LIVE aggregata e append-only che deve
coprire tutte le dieci collection. I due producer temporanei, il recorder
esplicito e la sequenza seed -> recorder -> cleanup sono documentati in
`release-history/firestore-community-ttl/README.md`; non si assumono report
reali e nessun producer viene eseguito durante la build AAB.
La policy della collection digest puo' restare attiva e vuota come contingenza
dormiente: non prova ne' richiede un job. La build verifica invece il contratto
effimero dell'API pubblica prima della compilazione e prima della copia
dell'artefatto: otto tipi chiusi, Comuni canonici, TTL di 60 minuti, posizione
zonale e nessun identificatore interno o contenuto libero nelle risposte. Dettagli e
diagnostica sono in
`ANDROID_PILOT_RUNBOOK.md` e
`docs/operations/COMMUNITY_MODERATION_GATE.md`.

I rilasci web seguono sempre questa sequenza:

1. commit pulito, inviato al remoto e CI verde;
2. revisione Cloud Run nominata con il commit backend, tagged a 0% traffico e
   collaudata direttamente;
3. risoluzione automatica del tag, revisione `Ready`, digest e health coerenti;
4. build web verificata con lo stesso endpoint assoluto;
5. nuova verifica del tag subito prima del deploy Cloudflare Pages;
6. smoke test di dati, GPS, App Check, `Segnala` e service worker;
7. collegamento di `meteofriul.app` soltanto dopo esito verde;
8. verifica finale del tag, smoke test sul dominio e rollback disponibile.

## Fonti, crediti e privacy

La schermata `Fonti e crediti` collega le principali fonti e licenze: ARPA
FVG-OSMER, Protezione Civile FVG, Open-Meteo, CAMS, Radar-DPC, OpenStreetMap,
NASA, Ostermann e le principali librerie open source.

Restano attività aperte prima di una distribuzione pubblica più ampia:

- pubblicare sulla futura landing il catalogo pubblico completo dei crediti
  delle 215 fotografie comunali già censite nel progetto;
- definire un contatto per rettifiche e richieste di rimozione;
- verificare autorizzazione e provenienza delle immagini Eventi e Webcam;
- verificare e documentare i termini d'uso delle osservazioni recenti e delle
  webcam OSMER, richiedendo un chiarimento scritto se i termini non coprono il
  riuso previsto;
- pubblicare privacy, crediti e disclaimer nella futura landing.

Un link o un'attribuzione non sostituiscono un'autorizzazione quando una fonte
o un'immagine è soggetta a condizioni ulteriori.

## Documentazione operativa

### Indice e responsabilità

Questo indice riusa i documenti esistenti. Per cambiare un comportamento si
confrontano contratto e codice; un verbale datato attesta soltanto le prove
descritte. Il coordinatore assegna un solo autore per ogni file condiviso.

| Argomento | Riferimento da usare | Responsabile | Documenti storici e limiti |
| --- | --- | --- | --- |
| Architettura e codice condiviso | [Architettura](#architettura), compresa la mappa Android/Web e il percorso eventuale iPhone; [backend](backend/README.md) per le API | Coordinatore; `build_verifica` per vincoli tecnici e compilazione | [Architettura completa del 12 settembre](docs/operations/PILOT_APP_COMPLETE_ARCHITECTURE_2026-09-12.md), [architettura dati meteo](docs/operations/PILOT_WEATHER_DATA_ARCHITECTURE_2026-09-12.md) e [inventario UI3](UI3_RUNTIME_DATA_INVENTORY.md) sono fotografie datate. Non provano la configurazione live attuale |
| Regole dell'app e dei dati | [Live](LIVE_VIEW_FUNCTIONAL_CONTRACT.md), [contratti API](contracts/runtime-api/v1/live/README.md), [località](contracts/runtime-api/v1/location/README.md), [Almanacco/Scopri](ALMANAC_DISCOVER_CONTENT_CONTRACT.md), [fonti Eventi](EVENTI_DATA_SOURCE_AUDIT.md) | `meteo`, `eventi`, `scopri` nei rispettivi ambiti; `home` per la composizione dei dati in Home. Il coordinatore assegna Community e servizi comuni | Gli audit Eventi/UI3 contengono osservazioni datate: distinguere le regole dalle vecchie liste di fonti e dai risultati dei test. I [verbali operativi](docs/operations/) conservano le successive verifiche |
| Vincoli e protezioni | [AGENTS](AGENTS.md), [prevenzione build](docs/operations/ANDROID_BUILD_PREVENTION_RULES.md), [runbook Play](docs/operations/PLAY_AAB_RUNBOOK.md), [parità Web/Android](docs/operations/WEB_ANDROID_RELEASE_PARITY.md), [privacy Community](docs/operations/COMMUNITY_PRIVACY_DATA_SAFETY_HANDOFF.md) | Coordinatore e `build_verifica`; autore esplicitamente assegnato per le modifiche. Le autorizzazioni del proprietario restano separate | [Cutover Web](PRODUCTION_CUTOVER_RUNBOOK.md) e audit precedenti non sostituiscono i gate correnti |
| Versioni e stato delle distribuzioni | [Manifest frontend](frontend/package.json), [configurazione Android](frontend/android/app/build.gradle), [registro Play](release-history/android-play/README.md), [stato release](docs/operations/RELEASE_0.1.15_STATUS_20261021.md) e [registro parità](docs/operations/WEB_ANDROID_RELEASE_PARITY.md) | `build_verifica` raccoglie commit, hash, strumenti e prove; il coordinatore distingue preparazione e pubblicazione | Le versioni del checkout, gli artefatti immutabili e i canali pubblicati sono stati diversi. Leggere la data di ogni attestazione; un vecchio verbale di build non certifica la release successiva |
| Struttura dell'interfaccia | [Mappa e confini](AGENTS.md#app-map-and-coordinated-agents), [tab](frontend/src/app/appConfig.js), [route](frontend/src/app/AppRoutes.jsx), [architettura CSS](CSS_ARCHITECTURE.md) | `home`, `meteo`, `eventi`, `scopri`; routing, shell e temi condivisi sono assegnati dal coordinatore | [Contratto iniziale UI](UI_COMPONENTS_CONTRACT.md): principi e nomenclatura iniziali; esempi e vecchia struttura vanno confrontati con le feature attuali |

Non occorrono copie parallele `architecture`, `business-logic`, `constraints`,
`version` o `ui-structure`: l'indice indica dove aggiornare ciascun argomento.

### Job e controllo dei servizi

- [Inventario dei job](docs/operations/JOBS_INVENTORY.md): configurazioni,
  pianificazioni con fuso, risultati attesi, monitoraggio e responsabilità.
- [Prima verifica del 28 ottobre](docs/operations/JOBS_READONLY_AUDIT_20261028.md):
  esiti osservati, anomalie, limiti e prova del nuovo profilo.
- [Profilo `controllo_job`](.codex/agents/controllo_job.toml): legge stati, log
  e dati; segnala al coordinatore, senza correggere o avviare job. Le eventuali
  correzioni spettano allo specialista competente e vengono verificate da
  `build_verifica`. Il profilo non crea un controllo periodico né nuovi permessi.

La disponibilità effettiva dell'agente va provata nella sessione: il file di
configurazione da solo non la dimostra. L'esito della prima prova è nel verbale.

### Runtime e operazioni

- [API UI3](backend/README.md): avvio, route, fonti, Firestore, App Check e test.
- [Osservazioni test chiuso Google Play](docs/operations/PLAY_CLOSED_BETA_OBSERVATIONS.md):
  problemi rilevati e miglioramenti da pianificare durante la beta Alpha.
- [Runbook pilot owner Android/Web](ANDROID_PILOT_RUNBOOK.md): target ammessi,
  matrici di prova, build e gestione delle attestazioni.
- [Wrapper Android](frontend/android/README-PILOT.md): identità, runtime e
  configurazione esclusa dal repository.
- [Hardening Android 0.1.8](docs/operations/ANDROID_0.1.8_TECHNICAL_HARDENING.md):
  obiettivi, gate e stato del lavoro R8.
- [Audit R8 Android 0.1.8](docs/operations/ANDROID_0.1.8_R8_AUDIT.md):
  mappatura nativa, refactoring, prove e artefatti di deoffuscazione.
- [Architettura CSS](CSS_ARCHITECTURE.md): layer, ownership e naming.
- [Contratto API Live](contracts/runtime-api/v1/live/README.md): fixture e
  invarianti delle risposte Territorio.
- [Contratto località](contracts/runtime-api/v1/location/README.md): ricerca e
  reverse geocoding.
- [Runbook del cutover web](PRODUCTION_CUTOVER_RUNBOOK.md): baseline storica,
  rollback e criteri di smoke test; non è lo stato live corrente.
- [Audit automazioni](PRODUCTION_AUTOMATION_AUDIT.md): fotografia operativa
  datata 11 agosto, da riverificare dopo la stabilizzazione.

### Contenuti e asset

- [Contratto Almanacco e Scopri](ALMANAC_DISCOVER_CONTENT_CONTRACT.md).
- [Asset launcher Android](android/launcher-assets/README.md).
- [Asset astronomici](frontend/public/astronomy/README.md).
- [Foto e stemmi comunali](frontend/public/municipalities/README.md).
- [Archivio Ostermann](scripts/data/ostermann-proverbs-1876/README.md).
- [Profili dei santi](scripts/data/saint-profiles/README.md).

Gli altri file `*_AUDIT.md`, i piani di migrazione e i documenti di importazione
sono evidenze datate del percorso di sviluppo. Non devono essere interpretati
come descrizione dello stato corrente senza una nuova verifica.

## Lavoro ancora aperto

- completare privacy/Data Safety e ottenere verdi i gate effimeri e TTL della
  Community, senza attivare il digest dormiente;
- custodire la upload key Play, mantenere aggiornate le dichiarazioni manuali e
  completare le evidenze richieste dalla Play Console;
- decidere e collaudare separatamente qualunque estensione del test Play oltre
  il telefono owner, senza confonderla con un rollout pubblico;
- mantenere l'osservazione delle soglie Open-Meteo e del comportamento
  geofence/WorkManager durante il closed test;
- consolidare coordinate, health e autorizzazioni del catalogo Webcam prima di
  ampliarlo o aggiungere una mappa;
- affrontare edge-to-edge e large-screen in cicli separati dalla pipeline R8;
- completare i gate di fonti, crediti, privacy e contatti.

## Regole di contribuzione

- Leggere e rispettare [AGENTS.md](AGENTS.md) prima di iniziare un intervento.
- Non committare `google-services.json`, keystore, password, token App Check
  Debug, token FCM o Firebase Installation ID. Le chiavi pubbliche di build
  Firebase/reCAPTCHA/VAPID non sostituiscono mai credenziali server.
- Non includere coordinate GPS precise nei log o nei documenti di test.
- Non mascherare un errore di fonte con dati vuoti o attribuzioni diverse.
- Conservare attribuzioni e collegamenti alle fonti nei cambi di UI.
- Tenere separati build web, build Android e deploy backend.
- Partire dal `main` verificato con un ramo dedicato al workstream; più build
  dello stesso lavoro restano sullo stesso ramo.
- Eseguire i controlli pertinenti e promuovere su `main` soltanto dopo la
  verifica, tramite pull request oppure avanzamento esplicitamente autorizzato.
- Prima di una promozione importante, verificare se le affermazioni di stato di
  questo README richiedono un aggiornamento.
