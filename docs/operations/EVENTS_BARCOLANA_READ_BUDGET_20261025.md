# Barcolana: budget delle letture — 25 ottobre 2026

Stato: correzione locale, non distribuita. Ramo `codex/events-pnpensa-barcolana`,
base main `0841020a42d836e44de306e9639b07b98fceaefc`; segue il commit Pordenone
Pensa `84cb94c0` ([verbale](EVENTS_PNPENSA_SESSIONS_20261025.md)).

## Riscontro e limite della diagnosi

La corsa ordinaria Eventi `meteofriul-events-refresh-bbmkg` del 25 ottobre alle
04:00 UTC / 05:00 Europe/Rome ha conservato Barcolana come fonte obsoleta dopo
il timeout esterno di 35 secondi. Evidenze già disponibili nella radice canonica:
`.tmp/jobs-targeted-deploy-20261024/ordinary-verification.json`.

Il codice eseguiva in serie calendario, sitemap e notizia di edizione. Ogni
lettura poteva consumare 25 secondi e un retry, mentre l'intera fonte aveva
35 secondi. Questo percorso poteva esaurire il budget anche senza scaricare
le pagine di dettaglio. I vecchi log non identificano la richiesta lenta:
non attribuiamo il timeout a uno specifico endpoint né dichiariamo già risolto
il problema in produzione.

## Correzione

- Calendario, sitemap, notizia e soli riscontri regionali ancora pertinenti
  sono letti in parallelo, con massimo quattro richieste contemporanee.
  Al 25 ottobre le letture obbligatorie sono tre; le pagine regionali concluse
  non sono richieste. L'eventuale orfano noto è controllato solo se in sitemap.
- Tutte le letture condividono 28 secondi. Timeout connessione 3 secondi e
  inattività lettura 8 secondi, ridotti quando il tempo residuo è inferiore.
  Un solo retry transitorio, entro la stessa scadenza. I timeout HTTP non sono
  una garanzia di durata totale: la scadenza del gruppo e il processo esterno
  proteggono anche da letture che continuano lentamente o non cooperano.
- Restano il limite esterno di 35 secondi e il totale delle fonti di 860 secondi.
  Non sono stati cambiati timeout o scheduler cloud.
- Una lettura necessaria fallita rifiuta la fonte, senza restituire un sottoinsieme
  o un falso elenco vuoto. L'errore riporta la fase o le letture ancora pendenti.
  Le connessioni, compresa quella dell'orfano, sono chiuse.
- Conservati controlli di edizione, calendario/sitemap, immagini, descrizione,
  deduplica, riscontri regionali e appuntamenti futuri. La fine della regata
  principale non elimina le premiazioni del 29 novembre.

## Verifiche locali

- 13 test Barcolana PASS: letture effettivamente concorrenti e limitate,
  scadenza con pagina bloccata, retry senza rinnovo del budget, nessuna richiesta
  dopo scadenza, 404 non ritentato, chiusura risposte, rifiuto di pagine mancanti,
  controlli di completezza e mantenimento del programma di novembre.
- Suite `python -m unittest discover -s tests -p "test_pilot*.py"`: **777 test,
  PASS con 1 skip** per l'artefatto ISTAT locale facoltativo assente. Il numero
  comprende anche i 14 test Pordenone Pensa del commit precedente.
- `python -m unittest discover -s tests -p test_event_source_http.py -v`:
  **5 test PASS**, inclusi retry transitori e rifiuti HTTP permanenti.
- Replay finale offline Pordenone Pensa: ancora 5 eventi dal post 6892 e
  revisione per anni discordanti del post 6945.
- `git diff --check`: PASS. Nessuna modifica frontend, schema API, sponsor,
  versione Android o artefatto Web.

[Identità del codice e riepilogo](evidence/events-barcolana-20261025/verification.json).
Log completo locale: `events-pilot-final-20261025.log` nella cartella temporanea
Windows. Si tratta di verifiche offline: non provano i tempi del sito reale
né il recupero della prossima corsa. Nessun job o invio manuale, push o deploy.

## Passo successivo proposto

Revisionare i due commit e integrarli secondo il flusso main/PR/CI; solo dopo
l'autorizzazione aggiornare il job Eventi, mantenendo il digest precedente per
rollback. Non occorrono nuova AAB o pubblicazione Web per questo schema dati.

La verifica della successiva corsa ordinaria dovrà richiedere Barcolana fresca
con sessioni future nelle API e i cinque appuntamenti Pordenone Pensa con sedi,
orari e descrizioni. Il post Scienza contraddittorio deve restare in revisione.
Controllare tutte le fonti e distinguere catalogo parziale da fonte obsoleta:
un job verde da solo non dimostra la completezza. La gestione generale fuori
stagione e altre sorgenti non sono modificate da questi commit.
