# Candidata Web sul Galaxy — 20 ottobre 2026

## Esito

Verifica reale completata su **Brave Android**, con esito positivo per
previsioni FVG, temi chiaro/scuro, italiano/friulano, aggiornamento manuale
della vista e catalogo Eventi. La prova non costituisce approvazione alla
pubblicazione: ricerca nazionale e Community sono limitate dall'origine
locale; restano la verifica Safari/iPhone e il binding API già aperto.

Chrome risultava disattivato (`enabled=3`) e non apriva l'intent. Il proprietario
ha autorizzato espressamente «Usa Brave». Chrome non è stato riattivato.

## Identità e metodo

- Galaxy A52 SM-A525F, Android 14/API 34, navigazione a tre pulsanti.
- Brave `1.97.59`, motore dichiarato nello user agent Chrome `155.0.0.0`.
  Lo user agent riduce Android a `10/K`; la versione reale Android è letta da ADB.
- Schermo 1080 × 2400; viewport osservato 411 × 728 CSS px, DPR 2,625.
- Frontend invariato: `bf304281aa9851369687c2dd646b8bd473c0b23d`.
  Ramo di preparazione `codex/web-android-parity`, HEAD iniziale `a8bb5f1f`.
- Archivio: `release-artifacts/web-candidates/20261020-bf304281/web-preview.zip`,
  SHA-256 `e81b04aaaeefdf3c7ab8356cfc31557be77ba00f7bcfb4a56d818b59a5ff32fa`.
  HTML e asset principali serviti coincidono byte per byte con l'archivio.
- Anteprima statica `http://127.0.0.1:5176/`, raggiunta tramite USB reverse.
  Browser reale, senza emulazione di viewport. Screenshot ottenuti dal telefono.
- Intercettazione nella sola scheda di verifica: ammessi GET/HEAD/OPTIONS,
  rifiutati gli altri metodi. Nel riepilogo delle 15:50:39 Europe/Rome:
  91 GET, 18 OPTIONS, nessuna richiesta di scrittura intercettata.
  Nessun click di invio o consenso alle notifiche; `Notification.permission=default`.
  I contatori descrivono il traffico osservato della scheda, non un audit cloud.

## Risultati

| Area | Esito osservato |
| --- | --- |
| Primo avvio | Scelta Italiano, posizione e notifiche saltate con «Non ora» |
| FVG | Udine e Pordenone caricano previsioni reali; il cambio comune modifica i dati |
| Chiaro/scuro e IT/FUR | Quattro combinazioni osservate, nessuno sforamento laterale: pagina e viewport entrambi 411 px |
| Giorni | Tre card larghe circa 113,97 px, alte 97 px; etichette senza data ridondante, data completa accessibile |
| Selezioni | Bordo, ombra interna e fondo di giorno e ora selezionati identici nelle misure dei due temi |
| Precipitazioni | Gocce leggibili e importi positivi evidenziati; dettagli orari con quantità e intervallo |
| Dettaglio orario | Apertura e visualizzazione di dati/grafici in friulano verificate |
| Eventi | Quattro eventi reali a Udine, filtri e dettaglio «Monet. Una vita a colori» leggibili; link esterni non aperti |
| Refresh FVG | Trascinamento fisico sul telefono: «Aggiornamento…», poi ritorno alla vista; HTTP 200 per latest, manifest e documento Pordenone |
| Scorrimento | Schede ambientali e navigazione inferiore raggiungibili, senza sovrapposizione con le barre di Brave nel caso osservato |
| Persistenza | Friulano/tema chiaro conservati al ricaricamento; successivamente Italiano, Pordenone e tema chiaro conservati dopo Home/ritorno a Brave e ricaricamento |
| App installate | Versioni e date installazione/aggiornamento di ufficiale `300031`, TEST `300037` e Chrome identiche prima/dopo |
| Errori JavaScript dell'app | Nessun `Runtime.exceptionThrown` osservato; le interrogazioni del probe ripetute dopo caricamento non sono errori del prodotto |

La corsa FVG letta è ancora **20261019T120000Z**, mostrata come
«19/10 · 14:00». Il refresh riuscito non significa pubblicazione di una corsa
nuova e non chiude il controllo ICON previsto separatamente.
Aria e pollini sono non disponibili su entrambi i comuni. UV non disponibile
a Udine, disponibile a Pordenone (1,1, picco 1,6 nel momento osservato).
Non attribuire tutti questi esiti allo stesso difetto o considerarli risolti.

## Riscontri della prima verifica

Aggiornamento successivo del 20 ottobre: i punti 1 e 3 sono stati corretti
e riverificati su Brave del Galaxy; dettagli nel
[verbale delle correzioni](WEB_APP_BROWSER_FIXES_20261020.md).
Le osservazioni sotto descrivono la candidata iniziale, conservata separatamente.

1. **Indietro del browser e finestre.** Due prove del tasto Android Indietro
   con il dettaglio Eventi aperto hanno lasciato la candidata per la pagina
   precedente della scheda. In questa prova era il 404 locale iniziale,
   intenzionalmente innocuo. Non è un crash né un 404 del sito pubblico.
   Il codice `services/pilotBackNavigation.js` abilita la gestione delle
   finestre soltanto nel runtime Capacitor Android; la Web segue la cronologia
   del browser. Valutare una gestione Web delle finestre prima di promettere
   parità di navigazione con l'app. Non modificata in questa verifica.
2. **Ricerca nazionale.** Inserendo «Roma» dalla tastiera reale appare il
   risultato FVG locale «Romans d'Isonzo», non Roma. Osservati errori CORS
   per i servizi remoti dall'origine 127.0.0.1:5176, coerenti con il limite
   già documentato sul PC. La prova nazionale resta incompleta, non un
   successo; nessuna modifica CORS o sostituzione dell'origine.
3. **Ricerca con tastiera.** Brave mostra il proprio comando di cancellazione
   insieme a quello dell'app; durante la ricerca con tastiera il comando
   dell'app è apparso su una seconda riga. A tastiera chiusa i due comandi
   sono affiancati. Rifinitura Web da valutare, documentata nelle immagini.
4. **Community.** La lettura `/api/community/reports` risponde 403
   nell'anteprima locale. Non verificati invio/ricevuta reali e nessuna
   simulazione sostituita alla prova dei servizi.
5. **Altri ambienti.** Chrome non verificato; Safari/iPhone, Aggiungi a Home,
   aggiornamento della Web pubblica, uso offline e riavvio completo del
   browser non verificati. Non estrapolare il risultato Brave a questi casi.

Nessuna AAB, installazione, push Git, deploy, esecuzione cloud manuale,
notifica o segnalazione. Nessuna modifica al frontend, a main, alle preferenze
cloud o ai controlli programmati CAMS/ICON. Preferenze cambiate solo nella
nuova origine locale del browser per svolgere il collaudo.

## Evidenze e prossima decisione

Evidenze selezionate con hash:
[`evidence/web-candidate-galaxy-2026-10-20/manifest.json`](evidence/web-candidate-galaxy-2026-10-20/manifest.json).
Comprendono schermate, misure DOM, rete senza query/token, controllo pacchetti
e confronto asset. Il materiale completo è archiviato localmente accanto
all'artefatto Web e conservato anche nella directory di lavoro `.tmp`.

Prima della pubblicazione: decidere la correzione della navigazione Web e
della ricerca, completare il binding API e provare i servizi dall'origine
pubblica autorizzata, oltre alla verifica Safari prevista dal runbook.
Questo verbale registra la prova; non autorizza pubblicazione o nuova AAB.
