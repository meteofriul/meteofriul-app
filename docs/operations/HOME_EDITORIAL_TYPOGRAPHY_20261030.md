# Home: tipografia delle schede editoriali — 30 ottobre 2026

Ramo dedicato `codex/home-editorial-typography-20261030`, creato da main
`9f81253e`, con il solo prerequisito locale di avvio CAMS `cfed5262`
(ripresa della correzione `86706ea8`). I filoni Mercati e Orto restano nei
rispettivi rami; non sono inclusi in questa correzione.

## Problema e comportamento corretto

La domanda di «I perché del Friûl» usava `clamp(1rem, 4vw, 1.25rem)`:
con dimensione base di 16 px variava da 16 a 20 px al cambiare della finestra.
Il titolo di «Memoria del giorno» rimaneva a `1.0625rem`, pari a 17 px.
La scheda dei Perché aggiungeva inoltre 5 px sopra il contenuto.

L'unico file applicativo modificato è
[`home.css`](../../frontend/src/features/home/home.css):

- Domanda e titolo condividono `1.0625rem`, peso 800 e interlinea 1.3.
  La dimensione resta relativa alle preferenze del lettore e non dipende
  dalla larghezza della finestra o dalla lunghezza del testo.
- Metadati condivisi: `0.6875rem`, peso 600, interlinea 1.4 e tracking
  `0.06em`. Margini e padding azzerati; distanza dal titolo di 7 px.
- Eliminato il margine aggiuntivo di 5 px dei Perché.
- Domanda e titolo restano integrali; l'estratto Memoria conserva
  `0.8125rem` e due righe. Colori, azioni, testi e navigazione invariati.

## Verifiche

- Revisione del diff e `git diff --check`: PASS.
- Anteprima canonica già attiva su `http://127.0.0.1:5174/`: CSS aggiornato
  restituito con HTTP 200, vecchia regola fluida assente, selettore condiviso
  presente; `/api/healthz` tramite frontend restituisce `status=ok`.
- Node 22.17.1 e npm 10.9.2, con PATH limitato al processo di verifica.
- Test esistenti `HomeQuickGrid.test.jsx`, `HomeView.test.jsx` e
  `homeCardHeadings.test.jsx`, tramite Vitest con `--configLoader native`:
  3 file, 50 test PASS.
- Compilazione frontend Vite con `--configLoader native` e output univoco
  nel TEMP di Windows: PASS, 2122 moduli. È una compilazione di verifica,
  non il pacchetto Web di release. Avvisi non bloccanti: directory esterna
  non svuotata, import Almanac statico/dinamico e chunk superiore a 500 kB.
- SHA-256 del CSS verificato:
  `7608a3aec59ed90fef806934bef680128e4af70aa411a2910b5e56cfc1a8705c`.
- Lint completo `npm run lint`: PASS, nessun errore o avviso.

La verifica visiva automatica è stata impedita dagli strumenti della sessione:
`The browser access host is unavailable`; il percorso Windows restituisce
`Computer Use native pipe is unavailable`, errore Windows 2.
Nessuna schermata acquisita dall'agente e nessuna prova automatica o su telefono
dichiarata. La matrice completa di domande brevi/lunghe, IT/FUR, chiaro/scuro
e larghezze 360, 390, 430 e 500 px non è attestata.

Il 30 ottobre il proprietario ha approvato il risultato osservato con
«Così va bene, puoi allineare il ramo», dopo la consegna della correzione
`02495d3f`. Questo è il riscontro visivo e l'autorizzazione alla promozione
per la discrepanza richiesta. Dispositivo e configurazione non sono stati
specificati: non si estende il riscontro a Safari/iPhone o a una matrice Android.

## Stato di consegna

Promozione dei sorgenti autorizzata, in preparazione tramite PR verso main;
CI della PR e di main da registrare. Il ramo include il prerequisito del
launcher CAMS già verificato con 93 asserzioni e avvio reale, documentato nel
[verbale dedicato](LOCAL_PILOT_CAMS_STARTUP_20261030.md).
Nessun pacchetto Android o artefatto Web di release generato e nessuna
pubblicazione applicativa autorizzata da questo allineamento.
