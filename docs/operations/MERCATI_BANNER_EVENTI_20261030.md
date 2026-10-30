# Mercati: banner di accesso da Eventi — 30 ottobre 2026

Modifica locale nel ramo `codex/mercati-integration-20261028`, base
`5ee56469`. Il riquadro che apre il catalogo Mercati da Eventi diventa un
banner riconoscibile, secondo la proposta del proprietario: gradiente blu
scuro, testo bianco, icona dedicata con badge e freccia evidente.

## Comportamento e aspetto

- Il banner sopra l’elenco Eventi mostra «Mercati e mercatini» e
  «Esplora nella tua zona», riusando anche le traduzioni friulane esistenti.
- Icona di bancarella `Store` da Lucide nel badge di 48 px; freccia da 22 px
  in un cerchio di 32 px. L’intero riquadro è un unico pulsante.
- Gradiente `#142344` → `#1b365a` → `#244e7a`, titolo bianco e testo
  secondario `#d5e7fa`. Gli stessi colori valgono nei due temi.
- Titolo da 1 rem, senza ridimensionamento basato sulla lunghezza del testo;
  testo a capo e colonna centrale comprimibile. Sotto 380 px diminuiscono
  spaziature e padding, mantenendo badge e freccia.
- Focus da tastiera con contorno e bordo interno bianco; nessuna animazione.
  Lo stato hover conserva il focus visibile.
- Il pulsante mantiene la stessa apertura del catalogo localizzato e resta
  disponibile anche senza appuntamenti nell’elenco Eventi.

Il modificatore CSS riguarda soltanto questo accesso. Le schede dei singoli
appuntamenti, il collegamento dal dettaglio e l’ingresso da Scopri conservano
il comportamento e lo stile precedenti. Nessun cambiamento a fonti, date,
filtri territoriali o registro dei 192 casi.

File applicativi: `frontend/src/features/events/EventsView.jsx` e
`frontend/src/features/markets/markets.css`. In `MarketsExplorer.test.jsx`
è aggiornato soltanto il selettore del testo del pulsante; il controllo della
callback rimane invariato. Nessun nuovo test che replichi le regole CSS.

## Verifiche locali

La [ricevuta dei controlli](evidence/MERCATI_BANNER_EVENTI_VERIFICA_20261030.json)
conserva comandi, provenienza delle prove, hash dei sorgenti e limiti.

- Node **22.17.1**, npm **10.9.2**, configurazione Vite/Vitest nativa.
- **6 file, 32 test esistenti PASS:** `EventsView.markets.test.jsx`,
  `MarketsExplorer.test.jsx`, `EventsView.test.jsx`,
  `EventsView.preview.test.jsx`, `eventsCss.test.js` e
  `MarketsExplorer.browserBack.test.jsx`.
- `npm run lint`: PASS, nessun errore o avviso.
- Contrasto calcolato sui colori dichiarati del gradiente: minimo **8,59:1**
  per il titolo e **6,80:1** per il sottotitolo. È un controllo numerico dei
  colori, non una verifica visiva o completa di accessibilità.
- Compilazione Vite **8.1.6** con `--configLoader native`: PASS,
  **2127 moduli**, output univoco nel TEMP di Windows. È una compilazione
  di verifica, non un artefatto Web o Android di release.
- Avvisi di compilazione non bloccanti: directory esterna non svuotata,
  import Almanac statico/dinamico, chunk oltre 500 kB e `PLUGIN_TIMINGS`.
- Anteprima canonica già attiva su `http://127.0.0.1:5174/`: modulo Eventi
  e CSS aggiornati restituiti con HTTP 200; `/api/healthz` restituisce `ok`.
  Questo prova la disponibilità dei sorgenti, non la loro resa visiva.

La verifica visiva automatica non è disponibile: il browser restituisce
`The browser access host is unavailable`; il collegamento Windows restituisce
`Computer Use native pipe is unavailable`, errore 2. Nessuna schermata o prova
su telefono è attestata. Restano da osservare IT/FUR, chiaro/scuro e larghezze
ridotte nell’anteprima locale prima di promuovere la modifica.

## Stato di consegna

Solo modifica locale del banner e documentazione. Pannello esterno, catalogo,
servizi, AAB 300038 e Web distribuita invariati. Nessun push, promozione a main,
build Android o pubblicazione in questo passaggio.
