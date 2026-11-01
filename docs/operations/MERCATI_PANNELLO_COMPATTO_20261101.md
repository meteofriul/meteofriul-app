# Pannello Mercati: selezione e schede compatte — 1 novembre 2026

Intervento locale richiesto dal proprietario durante la revisione degli screenshot.
Il coordinatore è l'unico editor dei sette file coinvolti nel pannello esterno
`PANNELLO INSERZIONI`, ramo `codex/markets-management-20261030`.
Le modifiche precedenti sono conservate; nessun commit, push o pubblicazione.

## Comportamento

- Le 100 schede non sono più mostrate tutte in una lista di card. Due sezioni,
  **Bozze** e **Selezionate per la prossima pubblicazione**, offrono ciascuna
  una tendina con comune e nome e un pulsante **Apri scheda**.
- Ricerca sull'intero archivio, ordinamento per comune/nome e conteggi dei
  risultati. Un filtro che esclude la scelta corrente disabilita l'apertura.
  Sospese e archiviate rimangono raggiungibili se presenti.
- `published` rimane il valore del contratto amministrativo. L'etichetta
  descrive la selezione per la prossima pubblicazione, non attesta la presenza
  attuale nell'app. L'API amministrativa non restituisce la composizione
  del catalogo di riferimento: nessuna nuova qualifica online è dedotta.
- La scheda mantiene Nome e Comune visibili e separa Dati, Calendario,
  Edizioni, Fonti e verifica. Nelle Edizioni si sceglie un appuntamento alla
  volta; identità e altre date vengono conservate. Il salvataggio e i controlli
  backend rimangono quelli esistenti.
- Anche le pratiche si scelgono da una tendina: viene aperta una sola pratica.
  Il campo della credenziale si richiude dopo il collegamento e può essere
  riaperto. Credenziale solo in memoria; nessuna persistenza aggiunta.
- Riepiloghi e controlli finali compattati; mantenuta la spaziatura di 14 px
  fra campo credenziale e pulsante richiesta nello stesso controllo visivo.

## Verifiche

Copia di lavoro dentro il workspace, senza installare dipendenze: sorgenti e
asset non modificati confrontati con il pannello effettivo, nessuna differenza.
Node 22.17.1, Vite/Vitest con configurazione nativa.

- **180 test in 30 file PASS**, inclusi raggiungibilità delle 100 identità,
  filtri su tutto l'archivio, sezioni per stato, scelta obbligatoria, scheda
  iniziale compatta e 73 edizioni selezionabili con un solo modulo visibile.
- Prima corsa con due worker e build concorrente: 179 PASS, timeout di 5 secondi
  nel test PDF preesistente `receiptFile.test.js`. Ripetizione completa isolata
  con un worker: 180 PASS, senza cambiare test o timeout.
- Lint completo PASS. Build in directory unica OS TEMP PASS, 1952 moduli;
  avviso sulla dimensione dei chunk non bloccante.
- Copia dei sette file verificata con SHA-256 e controllo delle modifiche
  concorrenti. Originali dei quattro file preesistenti conservati in `.tmp/`.
  Il primo tentativo di copia si è fermato prima di qualsiasi scrittura esterna
  per un array annidato nel manifest PowerShell; corretto il manifest
  conservando gli hash originali, copia successiva completata.
- Pannello 5182 e quattro moduli aggiornati: HTTP 200. Servizio bozze 8003: `ok`,
  `publicationEnabled=false`. Archivio al controllo tecnico precedente al
  salvataggio confermato sotto: revisione **2**, revisione pubblica **0**,
  **100 schede**, **213 date**, **59 pratiche**, **66 bozze**, **34 selezionate**.

Manifest delle copie e percorso della build sono nei file ignorati
`.tmp/markets-compact-delivery-20261101.json` e
`.tmp/markets-compact-build-20261101.txt`.

## Verifica guidata tramite screenshot del proprietario

Dopo l'aggiornamento sono stati ricevuti quattro screenshot della nuova
interfaccia, distinti dalle immagini iniziali che motivavano la correzione:

- Catalogo: entrambe le tendine (66 bozze e 34 selezionate), ricerca,
  riepiloghi e controlli richiudibili rientrano nella schermata ricevuta.
- Apertura di **Lo Scrigno del Doge**, Codroipo: sezione Dati e pulsanti
  di salvataggio visibili, senza sovrapposizioni o tagli osservabili.
- Edizioni: selettore con conteggio 6 e un solo modulo visibile.
  Il proprietario conferma testualmente che scegliendo un'altra edizione
  la data cambia. Non è stata confermata separatamente la variazione
  degli altri campi, né il salvataggio delle date.
- Fonti e verifica: fonte, ente, data del controllo, destinazione per la
  prossima pubblicazione, conferma editoriale e pulsanti rientrano nella
  schermata ricevuta. La spunta visibile descrive lo stato del modulo;
  non è una nuova approvazione editoriale attribuita al proprietario.

Le immagini sono nella conversazione; non sono state esportate come file
di evidenza né utilizzate per dedurre dispositivo, browser, zoom o viewport
che il proprietario non ha specificato. Questa è una verifica guidata
delle schermate mostrate, non una sessione automatizzata di browser.

## Conferma del proprietario su modifica e salvataggio

Il 1 novembre il proprietario conferma testualmente: «funziona la modifica ed
il salvataggio». Registrata come prova manuale riuscita del percorso di modifica
e salvataggio nell'anteprima, senza eseguire ulteriori scritture di prova.
Non sono specificati il campo modificato, la nuova revisione, una riapertura
dopo riavvio o il controllo dello storico; questi dettagli non sono dedotti
dalla conferma. Le revisioni e i conteggi sopra restano quelli del controllo
tecnico precedente, non una rilettura dopo il salvataggio del proprietario.

## Limiti residui

Il browser e il controllo nativo di questa sessione IDE restano indisponibili.
Restano da osservare il percorso Pratiche e la ricerca in uso. Il salvataggio
è confermato dal proprietario; riapertura dopo riavvio, controllo dello storico,
casi mobile e verifica diretta nel browser da parte dell'agente non sono
attestati da questa conferma.

## Correzione successiva del Calendario

Un ulteriore screenshot del proprietario mostra il Calendario con i pulsanti
di salvataggio troppo vicini al bordo inferiore e alla barra delle applicazioni.
Durante la modifica della scheda sono ora nascoste la riga della credenziale,
la revisione con Ricarica e la navigazione Catalogo/Pratiche: erano comandi
disabilitati. Tornando all'archivio ricompaiono. L'avviso sulla pubblicazione
disattivata resta visibile.

Orari e due date di validità condividono una riga sugli schermi ampi; sotto
680 px tornano in colonna. Tutti i campi e le dimensioni dei controlli sono
conservati. Nessuna modifica ai dati o ai contratti di salvataggio.

Verifica della correzione: **25 test mirati in quattro file PASS**, lint completo
e build PASS (1952 moduli, consueto avviso sulla dimensione dei chunk).
I tre file sono stati copiati nel pannello dopo il confronto degli hash
originali e verificati con SHA-256; i moduli aggiornati sono serviti su 5182
con HTTP 200. Manifest `.tmp/markets-calendar-fit-delivery-20261101.json` e
percorso build `.tmp/markets-calendar-fit-build-20261101.txt`.
Nel successivo screenshot allegato alla domanda sulle note pubbliche, Calendario,
motivo della modifica e pulsanti rientrano nella schermata, con spazio sotto
le azioni. Questa osservazione riguarda soltanto lo screenshot fornito.

Nessuna scrittura ai dati da parte dell'agente: il salvataggio manuale è quello
confermato dal proprietario. Nessuna nuova build Android, artefatto Web di
release, promozione a main o pubblicazione. La revisione editoriale resta aperta.
