# Deploy Eventi: Pordenone Pensa e Barcolana — 25 ottobre 2026

## Revisione, sorgenti e CI

[PR 22](https://github.com/meteofriul/meteofriul-app/pull/22), integrata in main
`e355128111aa4cf81d978ad49f599928004d4382`. Due correzioni runtime separate, `84cb94c0` e `a949b98e`,
più `070cfd1e` per allineare tre test storici al parametro deadline.
La prima CI ha rilevato quei tre test incompleti; la CI successiva della PR
è superata. [CI main](https://github.com/meteofriul/meteofriul-app/actions/runs/40173449781): completata con successo.

Le regressioni locali delle fonti passano: 777 test pilot con uno skip ISTAT
facoltativo e 70 test `test_event_source*.py`. Suite completa Windows: 2005 test,
uno skip e due sottocasi XML falliti per lxml locale 5.4.0, diverso dal 6.1.0
prescritto. La CI completa con dipendenze dichiarate è la prova di quel percorso;
nessuna installazione o modifica delle dipendenze locali è stata effettuata.

## Immagine e distribuzione

Build Cloud Build `705cf507-c4f1-4e07-ab61-55502c81342a`: SUCCESS. Archivio da `git archive` del commit
main sopra; SHA-256 `7441d898a209c4a3e90abbd8dfcd73e4180491118b417a37750e55ff39951d40`. Dockerfile Eventi esistente, comprese le
regressioni durante la build: 517 test pilot, 15 test delle fonti e 7 Attems
superati. Nessuna immagine per altri servizi.

Deploy verificato UTC: `2026-10-25T07:50:00.885551+00:00`.
Job: `meteofriul-events-refresh`, progetto `meteo-friul`, regione `europe-west1`.
Identità operativa verificata prima di ogni mutazione: account Meteo Friûl.

- Candidato: `europe-west1-docker.pkg.dev/meteo-friul/meteofriul/events-worker@sha256:074d93066cc35fa77bf193f95b8dba1163f5bb11e487dd12c12224b29ef26a26`.
- Rollback compatibile: `europe-west1-docker.pkg.dev/meteo-friul/meteofriul/events-worker@sha256:53f821f6e90b6732532ae7dc276efbed233c83eea1e271b1e72ffcd12e06c45c`.
- Modificata solo l'immagine. Template degli altri job, scheduler, risorse,
  account di servizio e configurazioni API Eventi/Community invariati.
- Sponsor disattivati; risposta dell'endpoint effettivo Play: enabled=false,
  zero campagne prima e dopo. Nessun pannello o allineamento sponsor attivato.
- Nessun job o invio manuale, AAB, installazione, modifica Web o produzione Play.

Il rollback legge lo stesso schema di catalogo e gli eventi con URL condiviso
ma date distinte. Ripristina però il rischio timeout Barcolana e lo scarto dei
programmi Pordenone Pensa con più appuntamenti; non è eseguito automaticamente.
Comando pronto in `rollback.ps1` nelle evidenze private.

## Compatibilità e controllo ordinario

Confronto dell'immagine precedente con main: soltanto `pilot_pnpensa.py` e
`pilot_barcolana.py` differiscono nel runtime backend. Schema, serializzazione,
HTTP, entrypoint e formato dei dati dei client sono invariati. Letture API
Pordenone/Trieste riuscite prima e dopo il deploy, CORS Android e Web verificato.
Le risposte dopo il deploy servono ancora il catalogo precedente; non sono la
verifica della nuova acquisizione.
Nessuna nuova prova su dispositivo: questo deploy non modifica il client.
Il deploy non ripubblica il catalogo; non equivale al recupero degli eventi.

Target fissato: **26 ottobre 2026 alle 05:00 Europe/Rome**, `2026-10-26T04:00:00Z`.
Scheduler confermato `0 4 * * *`, Etc/UTC; primo controllo dalle 05:15 italiane.
Controllare esattamente questa corsa anche se il PC viene acceso più tardi.
Follow-up attivo: `verifica-eventi-pordenone-pensa-e-barcolana`; primo passaggio
previsto dalle 05:20. Non interroga il cloud prima della finestra autorizzata,
si elimina dopo un esito conclusivo e non avvia esecuzioni.

Richiesti digest e identità Scheduler, completamento, tutte le 15 fonti fresche
oppure parziali con motivi espliciti e dati aggiornati dalla stessa corsa;
cinque incontri ABC Pordenone Pensa con sede/ora/descrizione nelle API;
programma Scienza contraddittorio in revisione; premiazioni Barcolana del
29 novembre visibili su Trieste. Distinguere fonti parziali da obsolete:
nessuna dichiarazione di completezza dal solo job verde.

Evidenze private e script: `.tmp/events-pnpensa-barcolana-deploy-20261025` nella
radice canonica. `verify_ordinary.py` è di sola lettura e riusa gli esiti conclusi;
`update_report.py` aggiorna solo questo verbale e i riferimenti di stato locali.
I comandi di distribuzione restano separati; non usarli nel follow-up.

## Esito ordinario

**In attesa.** Non presentare il vecchio catalogo come recuperato.
