# Recupero Eventi — esecuzione manuale autorizzata del 24 ottobre 2026

**Esito: pubblicazione riuscita e TurismoFVG nuovamente disponibile nelle API.**
Il proprietario ha autorizzato una sola corsa manuale dopo il controllo della
300037. Questa autorizzazione supera il precedente divieto soltanto per il job
Eventi; non modifica i controlli ordinari già pianificati.

## Identità ed esecuzione

- Progetto `meteo-friul`, regione `europe-west1`, identità proprietario verificata.
- Job `meteofriul-events-refresh`, esecuzione `meteofriul-events-refresh-9jskq`.
- Creata `2026-10-24T20:24:05.144411Z`, completata `2026-10-24T20:31:53.750930Z` UTC
  (22:24–22:31 Europe/Rome). Un task riuscito, zero fallimenti, zero retry.
- Digest `sha256:53f821f6e90b6732532ae7dc276efbed233c83eea1e271b1e72ffcd12e06c45c`,
  già distribuito dal codice main `23153e54`. Nessun nuovo deploy.
- Snapshot `2026-10-24T20:24:55.699907+00:00`, generazione Storage `1792873909746075`;
  catalogo e aggiornamento di tutte le 15 fonti ricadono nella stessa esecuzione.
- Template del job e scheduler identici prima/dopo. Un solo POST di avvio,
  registrato prima dell'attesa; tutti i controlli successivi sono letture.

## Recupero e confronto sulle stesse API

Prima: 9 fonti fresche, 5 parziali, TurismoFVG obsoleta ed esclusa dalle API;
357 righe pubblicabili e 1.375 righe TurismoFVG conservate ma non servite.
Dopo: 9 fonti fresche e 6 parziali, nessuna obsoleta; **1.791 righe pubblicabili**,
di cui **1.434 TurismoFVG**. Le 1.375 righe precedenti non erano un conteggio
di eventi correnti e non sono la misura del recupero.

Campioni sugli stessi centri pubblici, raggio 20 km, snapshot fissato e tutte
le pagine lette (Udine richiede due pagine). CORS `https://localhost` verificato.

| Comune | Righe API prima | Righe API dopo | Di cui TurismoFVG dopo |
| --- | ---: | ---: | ---: |
| Pordenone | 100 | 367 | 267 |
| Udine | 120 | 532 | 413 |
| Gradisca | 48 | 302 | 254 |

Questi sono conteggi API, comprendono date future e non equivalgono alle schede
«Oggi/Prossimi» dopo i filtri temporali e la deduplicazione dell'app.
I campioni territoriali possono sovrapporsi e non vanno sommati come eventi unici.
Nessuna nuova verifica visiva sul Galaxy dopo la pubblicazione di questo catalogo.

## Completezza e limiti rimasti

Il controllo TurismoFVG dichiara `verified-rolling-45-day-window`,
`source_complete=true`, `within_budget=true`, `pending=0` e `ambiguous=0`:
1.367 letture strutturate, nessun dettaglio ancora pendente. Si tratta della
finestra verificata della fonte, non di tutti gli eventi esistenti in regione.

Restano **20 schede in revisione**. TurismoFVG ne ha 14: 5 dettagli con HTTP 404,
4 possibili variazioni del programma, 4 identità/calendario da chiarire e
1 dettaglio non risolto. Gli altri 6 casi sono Azalea (1), CSS Udine (1),
Pordenone Pensa (2), SagreFVG (1) e Villa Manin (1).
I cinque 404 isolati non fermano più l'intera fonte; le schede dubbie rimangono
escluse e il catalogo/API espongono correttamente `degraded`/`quarantined_cards`.
Non è quindi dichiarata completezza al 100%.

Titolo, fonte, URL, date valide, comune e sede/luogo presenti nei tre campioni;
nessuna riga esattamente duplicata. Restano campi opzionali assenti:

| Comune | Denominatore | Orario assente | Immagine assente | Descrizione/estratto assente |
| --- | ---: | ---: | ---: | ---: |
| Pordenone | 367 | 101 | 12 | 31 |
| Udine | 532 | 179 | 11 | 43 |
| Gradisca | 302 | 131 | 5 | 16 |

Non verificata la correttezza fattuale di ogni evento sul sito originario.
I monitor candidati Palazzo Attems e GiroFVG mantengono `review_required`
(rispettivamente 5 e 18 variazioni): sono segnali separati dalle 15 fonti e
dal successo del catalogo. Il controllo annuale TurismoFVG conserva la prova
del 19 ottobre e non è stato rieseguito oggi. Nessuna correzione ulteriore.

## Controllo successivo e conservazione

Resta da verificare la corsa ordinaria esatta del **25 ottobre alle 04:00 UTC,
05:00 Europe/Rome** dopo il cambio d'ora, con controllo dalle 05:15.
Il follow-up `verifica-eventi-e-monitor-icon-dopo-correzioni-24-ottobre`
rimane attivo; il suo risultato Eventi non è stato sostituito con questa corsa.
Il lettore locale riconosce ora anche il rapporto di successo senza wrapper
e segue la paginazione API completa; sintassi Python verificata, nessuna
esecuzione del controllo ordinario anticipata e nessuna modifica cloud.

Sponsor, destinatari, invii, applicazioni e preferenze invariati. Nessuna AAB,
installazione, pubblicazione Web/Play o notifica app inviata manualmente.
I log di avviso dei monitor possono alimentare le policy esistenti: non si
dichiara assenza di email automatiche. Nessun commit o push in questa fase.

Evidenze grezze private nella radice canonica: `.tmp/events-manual-20261024/`.
[Ricevuta sintetica e hash](evidence/events-manual-20261024/verification.json).
Il catalogo precedente e la verifica sul telefono restano conservati come
fotografia precedente all'avvio manuale, senza riscrivere i risultati storici.
