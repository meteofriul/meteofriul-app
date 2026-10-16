# Osservazioni test chiuso Google Play

Stato di riferimento: release `300011 (1.0.0)`, test chiuso Alpha.

Questo registro raccoglie problemi e miglioramenti emersi durante la beta. Una
nota non autorizza automaticamente modifiche, build o deploy: gli interventi
vanno verificati e raggruppati nella successiva release pianificata, salvo
blocchi critici.

## Da verificare

### Permesso notifiche su Samsung A40

- **Osservazione:** durante l'installazione della beta da Google Play non e'
  comparsa la richiesta del permesso notifiche.
- **Ipotesi da non assumere come causa:** il dispositivo potrebbe avere
  conservato un'autorizzazione o uno stato della precedente installazione.
- **Controlli richiesti:** verificare versione Android/API, stato del permesso
  nelle impostazioni di sistema, tipo di installazione effettuata
  (aggiornamento o installazione pulita), chiamata effettiva alla richiesta
  `POST_NOTIFICATIONS` e comportamento dopo reinstallazione pulita.
- **Esito atteso:** sui dispositivi che richiedono il permesso, la domanda deve
  comparire una sola volta nel momento previsto; se il permesso e' gia'
  concesso, l'app non deve mostrare richieste o messaggi incoerenti.

### Pulsanti e destinazioni della sezione Webcam

- **Osservazione:** alcuni pulsanti non funzionano in modo affidabile o aprono
  una destinazione non corretta.
- **Controlli richiesti:** censire ogni pulsante, URL e comportamento tra web e
  Android; verificare link diretti, redirect, apertura esterna/interna,
  fallback e webcam non piu' disponibili.
- **Esito atteso:** ciascun comando apre la webcam o la pagina ufficiale
  corretta e gestisce in modo leggibile i collegamenti non disponibili.

### Salto dello scorrimento nella sezione Segnala

- **Osservazione:** durante lo scorrimento la sezione `Segnala` a volte cambia
  improvvisamente posizione o produce uno scatto visibile.
- **Ipotesi da verificare:** caricamento asincrono delle webcam, immagini senza
  spazio riservato, aggiornamento dei dati Territorio o altro layout shift
  nella stessa pagina.
- **Controlli richiesti:** riprodurre su Android e Web, misurare quale elemento
  cambia altezza, verificare placeholder e dimensioni riservate delle webcam e
  controllare gli aggiornamenti che avvengono mentre l'utente scorre.
- **Esito atteso:** la posizione visiva della sezione resta stabile durante il
  caricamento e lo scorrimento.

### Suggerimenti nella modifica posizione di Segnala

- **Osservazione:** la modifica della posizione propone soltanto due localita'
  suggerite.
- **Valutazione richiesta:** verificare se il limite e' intenzionale e se due
  risultati bastano nei casi reali, soprattutto per localita', frazioni e
  Comuni vicini con nomi simili.
- **Esito atteso:** l'utente deve poter individuare senza ambiguita' la
  posizione corretta; il numero dei suggerimenti andra' aumentato soltanto se
  i test dimostrano che due non sono sufficienti.
- **Audit 2026-08-29:** confermate due opzioni totali: localita' rilevata piu'
  il Comune realmente piu' vicino entro 5 km. Corretto il QA locale, che prima
  affiancava per errore il Comune alfabeticamente successivo (`Aiello del
  Friuli` / `Amaro`); il caso corretto e' `Aiello del Friuli` / `Visco`.
  Anteprima e flusso reale condividono ora lo stesso ordinamento geografico.
- **Follow-up geografico:** il catalogo dei 215 Comuni e le coordinate risultano
  coerenti, ma la scelta usa ancora la distanza dal punto rappresentativo del
  Comune. Prima del rilascio generale va valutata la risoluzione tramite i
  confini ISTAT gia' disponibili nel backend, soprattutto per aree montane e
  punti prossimi al confine regionale.

### Grassetto Eventi e contrasto del Bollettino scuro

- **Correzione locale 2026-08-30:** il CSS del player webcam dichiarava il layer
  `features` prima dell'ordine centrale. I reset prevalevano sul grassetto dei
  filtri Eventi e lo sfondo chiaro dei tab condivisi prevaleva sul Bollettino.
- Centralizzato il CSS del player in `ui/index.css`, nello stesso layer delle
  altre sezioni; l'entry CSS viene caricata prima di `App`. Non sono stati
  cambiati palette, pesi tipografici o logica dei filtri per compensare il bug.
- Aggiunti quattro test di regressione sull'ordine dei CSS. Verificati 329 test
  mirati, lint, build frontend e ordine dei layer nel CSS compilato.
- Controllo browser dopo ricarica completa: filtri Eventi e giorni Bollettino
  corretti in chiaro/scuro; popup Segnala centrato e invio QA disabilitato.
  Nessun commit, push, deploy o aggiornamento Android per questa correzione.

## Miglioramenti pianificati

### Identita' mostrata nelle segnalazioni

- usare come identificativo mostrato il nome friulano di un oggetto: non una
  generica etichetta utente tradotta in IT/FUR e non un nome personale;
- mantenere il nome friulano anche nell'interfaccia italiana, senza aggiungere
  `fonte anonima` o altre etichette equivalenti accanto all'identificativo;
- rivedere il dizionario e la forma degli alias attuali, che combinano due
  parole anche di animali/natura; non attribuire un alias singolo ai gruppi
  composti da piu' autori;
- mantenere internamente l'anonimato, la moderazione e il blocco della fonte
  tecnica senza esporre chiavi tecniche, profili o dati personali;
- verificare la coerenza dell'identificativo nella card, nel dettaglio della
  mappa e nella conferma dell'invio. La modifica resta da implementare.

### Leggibilita' e dimensioni tipografiche

- iniziare soltanto dai testi piccolissimi del popup `Segnala`, poi valutare
  il risultato con l'utente prima di estendere l'intervento;
- prima prova: portare i testi secondari da circa 10-12 px a 14 px usando il
  token tipografico esistente, con interlinea proporzionata;
- lasciare invariati titoli, scala tipografica globale, Webcam e barra di
  navigazione: non e' richiesto un audit generale ne' un intervento specifico
  per A40 in questa fase;
- conservare intestazione e invio fissi, controllare i ritorni a capo e non
  aumentare padding o spaziature per compensare la dimensione dei caratteri;
- sottoporre la prova locale alla valutazione visiva dell'utente prima di
  decidere ulteriori cambiamenti o una distribuzione.
- **Prima prova locale:** testi piccoli del popup portati al token da 14 px;
  62 test mirati e build frontend superati. Verifica visiva automatizzata
  bloccata dalla policy del browser della sessione, quindi da completare con
  l'utente. Nessun commit, push o deploy di questa prova.
- **Controllo successivo 2026-08-30:** completata la verifica visiva nel browser
  locale, nei due temi, insieme alla correzione dell'ordine CSS. Il popup
  mantiene intestazione/invio e resta centrato; nessuna segnalazione inviata.

### Gate di compatibilita' per il prossimo deploy

- **Stato:** il contratto in sviluppo richiede l'accettazione delle linee guida
  anche per confermare o smentire una segnalazione.
- **Vincolo release 300011:** il client Android gia' distribuito non invia
  `accepted_terms` e `policy_version`; il nuovo backend lo rifiuterebbe. Nella
  direzione opposta, il nuovo client non e' compatibile con il vecchio backend
  che rifiuta campi aggiuntivi.
- **Gate:** nessun deploy separato di frontend o backend prima di aver definito
  e verificato una transizione retrocompatibile oppure un rilascio coordinato.

### Evoluzione oraria a 48 ore

- richiesta aggiornata il 2026-08-30: estendere in Home l'evoluzione Open-Meteo
  dalle 12 ore alle successive 48 ore, superando l'ipotesi iniziale di 24 ore;
- rendere il pannello orario scorrevole orizzontalmente, mantenendo subito
  visibili le prime fasce utili;
- conservare il filtro delle ore gia' trascorse, il fuso della localita', il
  controllo con l'ora del dispositivo e la gestione del cambio ora;
- mantenere il caricamento immediato dalla cache e l'aggiornamento in
  sottofondo, senza rallentare la card meteo principale;
- verificare leggibilita', indicazione dello scorrimento e accessibilita' su
  telefoni stretti prima della pubblicazione.
- **Prova locale implementata:** un intervallo per ogni ora, scorrimento
  orizzontale nativo, etichette `Oggi`/`Vuê` o data e confine
  del giorno; frecce tastiera e Home/End non spostano verticalmente la pagina.
- **Ulteriore alleggerimento richiesto:** nascosti intestazione e barra di
  scorrimento; la casella successiva parzialmente visibile suggerisce lo swipe.
  Nessuna riduzione dei caratteri o delle ore disponibili. Titolo e fonte
  restano nella descrizione accessibile del pannello. Open-Meteo e' citato
  nell'informativa pubblica raggiungibile dalle Impostazioni; il componente
  locale `ImageCreditsView` completo di licenze non ha attualmente una route.
  Verifica locale IT/FUR: altezza da circa 125 a 91 px, tutte le 48 ore
  raggiungibili con Home/End, nessun overflow della pagina a 533 px;
  138 test mirati verdi dopo l'alleggerimento.
- Il backend fornisce gia' 48 slot: nessun cambio server, endpoint o polling.
  Sono mostrati soltanto gli intervalli disponibili entro la finestra futura;
  cache incompleta/legacy usa il titolo neutro `Evoluzione oraria`. Rimangono
  distinti gli istanti con offset diversi nel cambio ora autunnale.
- Il nuovo orizzonte e' attivato soltanto per Home; il modello locale del
  Bollettino conserva il comportamento preesistente quando non richiesto.
- Test: suite frontend completa 2.078 verdi, poi 127 mirati verdi comprendenti
  l'ultima aggiunta tastiera; lint e build frontend finali verdi. Verificati
  nel browser locale IT/FUR, temi chiaro/scuro, date e accesso all'ultima ora
  senza overflow della pagina (viewport 533 px). Prova su telefono reale
  ancora da eseguire. Nessun commit, push o deploy.

### Versione app nelle Informazioni

- Aggiunta locale del 2026-08-30: riga Versione/Version sotto Meteo Friul,
  nelle Impostazioni, senza nuove schermate o pulsanti.
- Android mostra versione e build realmente installate, ricavate dalla
  lettura `CapacitorApp.getInfo()` gia' esistente; esempio `1.0.1 (300012)`.
  Identita' non disponibile: testo neutro, nessun numero inventato.
- Il Web mostra il proprio numero di pacchetto, distinto da Android con
  `Anteprima Web` in sviluppo o `Web` in produzione. Nessun cambio a Gradle,
  release identity, permessi, notifiche o backend.
- Verifica: 114 test mirati verdi, lint e build verdi; controllo visivo IT/FUR
  nel browser locale a 533 px, valore a 14 px e wrapping per versioni lunghe.
  Formato e inoltro del dato nativo coperti dai test; lettura su dispositivo
  non riprovata in questo giro.
  Nessun commit, push o deploy.

### Coerenza date e icona della sintesi Bollettino in Home

- Date Bollettino/Almanacco Home allineate con iniziale maiuscola, in IT/FUR.
- **Successiva modifica richiesta:** l'icona generica della sintesi Bollettino
  e' sostituita dalla stessa icona colorata della card sopra l'aquila. Le due
  icone condividono meteo attuale, fase solare e aggiornamento giorno/notte:
  rappresentano il momento nella localita', non il testo del bollettino.
- L'allerta mantiene la priorita': triangolo, livello e azione preesistenti
  non cambiano. Testo del bollettino e icone delle previsioni orarie invariati.
- Verificato nel browser che le due immagini usino esattamente lo stesso
  asset. Modifica soltanto locale, senza commit, push o deploy.

### Titoli dentro le card Home

- Prova locale successiva al commit `e5124be`: spostati i titoli nelle card,
  con prima riga `Sintesi` + data, `Almanacco` + data e
  `Eventi vicino a te` + conteggio numerico. Niente pill e niente titoli
  esterni duplicati; tolta anche la frase `L'almanacco del giorno`.
- Freccetta di apertura uniformata accanto al titolo delle tre card,
  rimossa dal contenuto: compare solo se la card ha un'azione disponibile.
- Su successiva richiesta dell'utente mantenuta la dimensione precedente
  dei titoli: token da 22 px. Date e conteggio a 14 px, ritorno a capo
  consentito senza ridurre i caratteri. Controllo visivo a 360 px senza
  overflow delle intestazioni.
- Titoli semantici conservati fuori dal pulsante nativo che rende apribile
  l'intera card; priorita' allerta, contenuti, immagini e destinazioni
  invariati. Conteggio eventi derivato dallo stesso totale precedente,
  con etichetta IT/FUR completa per le tecnologie assistive.
- Verifica: 188 test mirati Home/AppRoutes e lint verdi; build Web verde.
  Controllo interattivo nel browser parzialmente limitato dalla modalita'
  commenti; nessun invio o modifica ai dati. Nessun push o deploy.

### Indicatori meteo locali in Home

- valutare lo spostamento dal Bollettino alla Home degli indicatori come
  umidita', pressione, vento, pollini e dati affini;
- distinguere esplicitamente dati locali e previsionali dai contenuti del
  bollettino regionale ufficiale, conservando fonte e significato di ciascun
  indicatore;
- verificare quali indicatori siano realmente utili a colpo d'occhio e quali
  debbano restare in un dettaglio secondario;
- studiare una presentazione compatta o espandibile che non appesantisca la
  Home e non rallenti la comparsa del meteo principale;
- controllare coerenza tra disponibilita' dei dati, localita', cache e stati di
  dato non disponibile prima di decidere lo spostamento definitivo.
- **Prova locale del 2026-08-30:** cinque mini-celle nello stesso blocco tra
  card meteo attuale e barra delle 48 ore: Vento, Umidita', Press., Pioggia,
  Pollini. Solo icona, etichetta e valore; nessun titolo, pulsante Cambia,
  scorrimento aggiuntivo o riga separata per i pollini. Dettagli invariati
  nel Bollettino.
- Riutilizzato il modello locale gia' calcolato dalla Home: nessuna nuova
  chiamata dati, priorita' OSMER e fallback esistenti conservati. Mancanti
  mostrati con `—`, zeri mantenuti e livello pollini non ricalcolato.
  Fonte e orario restano nella descrizione accessibile del blocco.
- Verifica: 259 test mirati Home/Bollettino/AppRoutes verdi, lint e build
  verdi. Browser IT/FUR e chiaro/scuro: blocco alto circa 75 px su Home
  larga 448 px, valori a 14 px, nessun overflow. Prova su telefono stretto
  ancora da eseguire. Nessun commit, push o deploy.
- **Successiva richiesta:** rimosso dal Bollettino il blocco esteso
  `A [localita']`, ora duplicato rispetto alla Home. Non e' piu' presente
  il dettaglio separato di raffiche, stazione e pollini in quella pagina.
  Rimossi anche caricamento e polling riservati alla scheda; la Home usa
  autonomamente bootstrap/cache meteo. Radar, previsioni e allerte invariati.
  Componenti e modello condiviso conservati nel codice, nessuna modifica
  a dati o backend. Verifica: 263 test mirati, lint e build verdi; browser
  con 5 celle Home, 48 ore e nessun blocco locale residuo nel Bollettino.
  Nessun commit, push o deploy.

### Richiamo Segnala nella Home

- Prova locale del 2026-08-30 rifiutata dopo la verifica visiva:
  l'utente non gradisce la riga `Segnala cosa vedi` tra le 48 ore e
  Sintesi bollettino. Rimossi richiamo, stili e collegamento di apertura
  dalla Home. Nessuna collocazione alternativa implementata.
- Il pulsante e il popup esistenti in Territorio restano invariati.
  Nessun commit, push o deploy.

### Ampliare la sezione Webcam

- individuare nuove webcam territoriali affidabili;
- verificare autorizzazione, stabilita', provenienza e attribuzione prima
  dell'integrazione;
- evitare duplicati e fonti che non consentono un collegamento o riuso sicuro;
- aggiungere le fonti in modo incrementale e coperto da controlli.

### Continuare l'ampliamento editoriale di Scopri

- proseguire il lavoro gia' avviato su localita', memorie, proverbi, riti e
  tradizioni;
- mantenere fonti, date certe e ricorrenze prioritarie;
- approvare separatamente testi italiani e friulani;
- registrare le lacune editoriali ancora da colmare ed evitare contenuti
  ripetitivi o non sufficientemente verificati.
