# Mercati e mercatini — prima versione locale

**Catalogazione del 30 ottobre 2026:** [dossier e registro delle fonti](MERCATI_FONTI_CATALOGAZIONE_20261030.md), 51 fonti e 44 schede approfondite sullo stesso ramo Mercati, ora allineato al main verificato. Nuovi riferimenti di ricerca, senza attivazioni nel catalogo né nuove prove runtime.

**Ricerca del 29 ottobre 2026:** [copertura, candidati e dati mancanti](MERCATI_COPERTURA_RICERCA_20261029.md). Individuati 74 candidati di ricerca e sette date future mancanti su quattro schede pubbliche; da qualificare prima dell'inserimento. Catalogo e UI invariati, prova visiva ancora aperta.

**Ripresa del 28 ottobre 2026:** implementazione recuperata nel ramo
`codex/mercati-integration-20261028` e adattata alla navigazione e alle regole
Eventi attuali. [Stato della ripresa e prove](#ripresa-sul-progetto-attuale--28-ottobre-2026).
Le verifiche del 15 ottobre riportate sotto restano evidenze storiche.

Data: 15 ottobre 2026. Ramo: `codex/mercati-mercatini`.
Base: `cab4871e8fe4f61014b0c9f8eb7d82b6b4b7ad0c`, il `main` locale all'apertura del lavoro.

## Comportamento

In **Scopri**, la voce «Mercati e mercatini» apre un catalogo con due gruppi:
mercati abituali e mercatini/fiere. Il catalogo segue il comune effettivamente
selezionato o rilevato dall'app, senza sostituirlo con il comune editoriale.
Sono disponibili un raggio da 5 a 50 km e i filtri Tutti, Oggi e Weekend.
Le distanze sono indicative tra centri comunali, non coordinate delle bancarelle.

La scheda presenta sede, cadenza, eventuali orari, note sulle eccezioni, date
pubblicate, fonte e ultima verifica. La ricerca della sede su Maps compare solo
quando il catalogo contiene un luogo documentato utilizzabile; non vengono
creati segnaposto geografici esatti. Il catalogo non richiede una chiamata di rete.
Etichette in italiano e friulano; nomi, luoghi e calendari conservano il contenuto
italiano delle fonti. La nuova traduzione friulana richiede revisione editoriale.

In **Eventi**, le edizioni esplicitamente pubblicate dei mercatini entrano nella
categoria già esistente «Mercati», entro la finestra corrente di 15 giorni.
Il giorno abituale di un mercato settimanale serve ai filtri di Scopri e non
genera appuntamenti nel calendario. Un appuntamento riconosciuto delle fonti
Eventi viene riutilizzato. Il riconoscimento usa ID, URL univoci o nome esatto
e comune; non usa somiglianze generiche. Gli annullamenti riconosciuti non
vengono riproposti dal catalogo. Un intervallo generico non diventa una serie
di edizioni giornaliere.

«Vedi appuntamento» apre la relativa anteprima in Eventi con il raggio scelto;
«Scheda del mercato» torna alla scheda. Eventi offre anche un accesso generale
al catalogo. Tornare alla lista conserva filtri e scorrimento durante la visita.
Una successiva visita normale a Eventi non riapre l'ultimo appuntamento.

## Dati e manutenzione

La sorgente fornita dall'utente è `Mercati_FVG_verifica_2026-10-14.json`.
Il JSON originale non è stato modificato. L'inventario applicativo ne registra
nome, data di verifica e SHA-256.

- 60 schede conservate come evidenza: 53 documentate consultabili, 5 parziali
  e 2 in conflitto escluse dalla consultazione e dalla proiezione in Eventi.
- Delle 53 visibili, 23 sono mercati abituali e 30 mercatini/fiere.
- 176 date pubblicate importate, comprese date passate e riferimenti a schede
  escluse. Solo le date future di schede documentate diventano utilizzabili.
- Nessuna conversione automatica di «quarta domenica» o «ultima domenica» in
  nuove date. Il calendario pubblicato conserva eventuali sospensioni.
- La proiezione è limitata al 31 dicembre 2026. È una scelta prudenziale
  dell'app, non una garanzia delle fonti. Nel 2027 le schede restano consultabili
  con avviso di aggiornamento, ma non alimentano Oggi/Weekend o nuove edizioni.

Per aggiornare il catalogo occorre verificare le fonti e modificare le schede
e le date in modo coordinato. Non basta aumentare la data di validità. Le note
di audit restano distinte dalle note mostrate al pubblico. Non sono stati
importati come mercati pubblici i semplici lead non verificati del documento.
La copertura regionale rimane parziale. Orari abituali e date pubblicate non
costituiscono una conferma in tempo reale: la scheda invita a verificare gli
avvisi della fonte. Per annullamenti non presenti nelle fonti Eventi o privi
di un'identità riconoscibile serve aggiornare manualmente l'inventario locale.

## File principali

- [Inventario](../../frontend/src/data/markets/catalogue2026.json)
- [Selezione, calendario e collegamento agli eventi](../../frontend/src/features/markets/marketsCatalog.js)
- [Interfaccia del catalogo](../../frontend/src/features/markets/MarketsExplorer.jsx)
- [Navigazione applicativa](../../frontend/src/app/AppRoutes.jsx)
- [Prova del percorso completo](../../frontend/src/app/AppRoutes.markets.test.jsx)

## Verifica locale

- **206 test superati, 19 suite**: catalogo, calendario, deduplicazione,
  annullamenti, cambio giorno a Roma, integrazione Scopri/Eventi, caricamento
  asincrono, cambio località, chiusura e regressioni di navigazione.
- ESLint sui file modificati e sul modulo Mercati: superato.
- Compilazione Web Vite con configurazione nativa in directory temporanea: superata.
- `scripts/test-canonical-workspace-cleanliness.ps1`: superato.
- SHA-256 della sorgente confrontato con l'inventario: coincidente.
- Diff e link locali del presente documento verificati.

Comando della suite mirata, da `frontend`:

```powershell
.\node_modules\.bin\vitest.cmd --configLoader native run src/features/events src/features/discover/DiscoverView.test.jsx src/features/markets src/app/AppRoutes.test.jsx src/app/AppRoutes.discoverLocation.test.jsx src/app/AppRoutes.refreshNavigation.test.jsx src/app/AppRoutes.markets.test.jsx src/app/usePilotBackHandler.test.js
```

La compilazione Web in directory temporanea è una verifica di compilazione,
non una prova dell'interfaccia pilot o di Android. Il warning sulle dimensioni
dei chunk e quello sul doppio import di AlmanacView restano non bloccanti.

Il controllo preliminare del launcher con `-WeatherCloud` non ha superato la
verifica di disponibilità/conformità del reader meteo. Il controllo con lo
snapshot locale e `-WeatherTestNow '2026-09-04T21:00:00Z'` è riuscito. L'orologio
del catalogo segue comunque il giorno effettivo di Europe/Rome.

**Verifica visiva non eseguita:** la porta 5174 è occupata dall'anteprima del
progetto principale e il proprietario ha chiesto di lasciarla attiva. Non sono
stati avviati server alternativi e non sono stati fermati i processi esistenti.
Quando la porta sarà disponibile, avviare questo checkout esclusivamente con
`scripts/start-local-weather-pilot.ps1` e verificare:

1. Layout a 360/390 px e desktop, tema chiaro/scuro, lingua italiana/friulana.
2. Scopri → catalogo → filtri/raggio → dettaglio → ritorno alla lista.
3. Pordenone → La Soffitta in Piazza → 25 ottobre 2026 → Eventi → scheda,
   usando una data reale entro la finestra; dopo il 25 ottobre scegliere
   un'edizione futura documentata entro 15 giorni.
4. Località fuori FVG, assenza di copertura, nessuna data futura e cambio comune.
5. Focus da tastiera, Escape, chiusura, scroll e contenimento del dialogo.

Nessuna build Android, installazione, push, PR, pubblicazione o promozione a
`main`. La verifica su dispositivo e le attività di release restano fuori
dall'ambito di questa prima versione locale.

## Ripresa sul progetto attuale — 28 ottobre 2026

Il ramo `codex/mercati-integration-20261028` nasce dal main verificato
`9f81253e6b1832816e4032930b7b5eb64ebff6ad`, allineato a `origin/main` tramite
lettura del remoto. Conserva con avanzamento fast-forward il lavoro locale
fino a `40431af7b8777671dd36b1c3096d7d714c14e640`, compresi organizzazione,
CSS Udine e Barcolana. Il solo cambiamento Mercati
`7693f3d5b625529cfdf4ae9d87e3072620b581b4` è stato riapplicato senza conflitti
testuali; il ramo originale è conservato. Nessun ritorno a vecchi servizi,
dipendenze o configurazioni del 15 ottobre.

`scopri` è responsabile di catalogo/interfaccia Mercati e accesso da Scopri;
`eventi` del collegamento agli appuntamenti; il coordinatore di routing, import
CSS condiviso e documentazione; `build_verifica` raccoglie le prove finali.

### Comportamento e adattamenti

- Mercati resta una sezione raggiungibile da Scopri, con accesso anche da Eventi:
  non aggiunge una quinta tab primaria.
- Il catalogo conserva i dati del 14 ottobre: 53 schede documentate consultabili,
  5 parziali e 2 in conflitto escluse. Fonti, date, testi e limite del 31 dicembre
  2026 non sono stati aggiornati o nuovamente certificati in questo intervento.
- Il dialogo Mercati ora usa la gestione Browser Indietro già presente nell'app
  e già adottata da Eventi. Il meccanismo comune non è modificato: viene collegato
  anche al prototipo Mercati recuperato. Escape e Indietro nativo conservano il
  percorso dettaglio → lista → chiusura; la cronologia è coordinata col passaggio
  al dettaglio Eventi.
- Una richiesta di appuntamento fuori dalla finestra corrente non riapre una
  vecchia scheda rimasta nel modello. Un ID di mercato noto con un comune
  dichiarato contraddittorio non viene associato al catalogo.
- Il dettaglio Eventi segue gli aggiornamenti dello stesso appuntamento;
  una risposta di arricchimento arrivata tardi non sovrascrive la nuova scheda.
  Coperti anche annullamento e scadenza della data richiesta.
- Conservati appartenenza ai programmi, orari verificati, aperture incerte,
  salute delle fonti e navigazione recente. La proiezione del catalogo Mercati
  avviene dopo il caricamento Eventi esistente; nessuna modifica al backend.

Le traduzioni friulane introdotte nel prototipo rimangono da revisione
editoriale. Non è stata conferita una nuova approvazione linguistica.

### Verifiche della ripresa

Toolchain prescritta Node `22.17.1` e npm `10.9.2`; dipendenze locali esistenti,
senza installazioni. Manifest, lockfile e processi di compilazione invariati.

- 316 test distinti in 27 file: 149 Eventi, 49 Scopri/Mercati e 118 routing,
  cronologia e servizi. Tutti superati con configurazione Vite/Vitest nativa.
- `npm run lint` completo: superato, senza esclusioni o riduzione delle regole.
- Compilazione Web in directory temporanea del sistema operativo: bundle Vite,
  service worker e controllo del service worker autonomo superati. Conservati
  warning non bloccanti sui chunk, import statico/dinamico di AlmanacView e
  tempi dei plugin. Nessuna modifica alle soglie.
- Il raccoglitore dei log ha incontrato un errore CP1252 stampando il segno
  di spunta dopo la compilazione principale già riuscita e salvata in UTF-8.
  Riprese soltanto le due fasi restanti nello stesso output temporaneo;
  l'errore riguardava la stampa del rapporto, non la compilazione.
- `CheckOnly` del launcher con `-WeatherCloud` e toolchain esplicita: superato.
  Reader cloud corrente conforme, senza scritture ai servizi remoti.
- Anteprima lasciata attiva su `http://127.0.0.1:5174/`, accessibile solo dal PC.
  Controllo finale `CheckOnly` sui medesimi processi: exit 0; frontend e backend
  riconosciuti, endpoint sani e listener limitati a loopback. GET della pagina:
  HTTP 200. Il processo Node usa la distribuzione prescritta.
- Guard di pulizia canonica superato dopo staging: 4020 file tracciati, senza
  output generati, segreti locali o dipendenze da cartelle storiche. Diff staged
  e dieci collegamenti locali verificati; i 17 hash dei sorgenti coincidono
  con quelli delle prove. Hook privacy esterno conservato, nessun push.

Il primo avvio del launcher è terminato, ma il raccoglitore Python dei log è
rimasto in attesa su una pipe ereditata dai server in background: il codice di
uscita iniziale del launcher non è recuperato. L'attesa non era una richiesta
meteo ancora in corso. È stato chiuso soltanto quel raccoglitore, dopo verifica
della sua identità e assenza di figli; i due server sono rimasti attivi e
immutati. L'esito di avvio è attestato dal successivo `CheckOnly`, dalla verifica
di proprietà dei processi e dalle risposte HTTP, senza un secondo avvio.

La [ricevuta della verifica](evidence/mercati-integration-20261028/verification.json)
registra comandi, esiti, hash dei file verificati e riscontro dell'anteprima.
Le prove automatiche non qualificano una nuova release Android o Web.

### Prova visiva e limiti

In questa sessione entrambi gli accessi automatici alla UI sono indisponibili:
il browser access host non è disponibile e il collegamento nativo restituisce
`Computer Use native pipe is unavailable`, errore Windows 2. Nessuna schermata
acquisita; nessuna verifica visiva o su telefono dichiarata riuscita.

La prova manuale deve usare l'anteprima canonica su `127.0.0.1:5174`, avviata con
`scripts/start-local-weather-pilot.ps1` e toolchain prescritta. Percorso utile
al 28 ottobre: selezionare Codroipo, aprire Scopri → Mercati e mercatini →
«Esplora nella tua zona», quindi cercare «Lo scrigno del Doge» (1 novembre) o
«Mercanti in Giardino» (8 novembre), secondo le date presenti nel catalogo.
Non usare il vecchio esempio del 25 ottobre come appuntamento futuro.

Verificare lista, raggio, filtri Oggi/Weekend, dettaglio, «Vedi appuntamento»,
«Scheda del mercato», chiusura e Indietro; ripetere in chiaro/scuro e IT/FUR,
su larghezza mobile e desktop. Controllare anche cambio comune, area senza
copertura e località fuori FVG. I controlli HTTP dell'anteprima non sostituiscono
questa prova.

Per avviare nuovamente l'anteprima dalla radice del progetto, usando la
distribuzione Node predisposta per questo workspace:

```powershell
$pilotNode = Join-Path $env:LOCALAPPDATA 'MeteoFriul\toolchains\node-v22.17.1-win-x64'
.\scripts\start-local-weather-pilot.ps1 -WeatherCloud -NodeDirectory $pilotNode -CheckOnly
.\scripts\start-local-weather-pilot.ps1 -WeatherCloud -NodeDirectory $pilotNode
```

Aprire `http://127.0.0.1:5174/` sullo stesso PC. Per arrestare i processi
riconosciuti dal launcher:

```powershell
.\scripts\start-local-weather-pilot.ps1 -Stop
```

Nessuna build Android, installazione, push, PR, promozione o deploy autorizzato
da questo passaggio. AAB 300038, pubblicazioni Web, servizi e qualificazioni
esistenti invariati. Nessun progetto, ramo, agente o dipendenza iOS creato:
il percorso Apple resta quello documentato nella mappa architetturale del README.
