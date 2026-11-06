# Sintesi mattutina: ritiri FCM e avvisi Cloud, 6 novembre 2026

## Stato

La [PR 42](https://github.com/meteofriul/meteofriul-app/pull/42) è integrata in `main` con commit `d072a6d4a2e2eb0ff2a84990956e944a918b7a46`. La [CI della PR](https://github.com/meteofriul/meteofriul-app/actions/runs/42202179543) e la [CI di main](https://github.com/meteofriul/meteofriul-app/actions/runs/42204956923) sono verdi nei tre job. Localmente erano passati 53 test backend mirati, il contratto operativo PowerShell e `compileall`.

Il job `meteofriul-morning-forecast` usa l'immagine `europe-west1-docker.pkg.dev/meteo-friul/meteofriul/backend@sha256:ab5ad97c5120d80fa1bdc4954ab9faca2d010d21aac842e1c3aba51ce327ea13`. Cloud Build `c2f5eea7-b486-4140-8503-48434f41bfe1` ha completato con `SUCCESS`; l'immagine è stata costruita da un archivio Git del commit di `main` contenente solo `Dockerfile`, `requirements.txt` e `app` del backend. SHA-256 dell'archivio locale: `c4b454b6c8ff7f75297d82d349739ca47f03ee7afa6d7edaa796f49309303a8e`. Il digest è stato confermato nel registry e nel readback del job.

È stata aggiornata solo l'immagine del job. Il readback del deploy conferma entrypoint, account runtime, timeout, zero retry, ambiente `send`, binding Scheduler, calendario `30 7 * * *` in `Europe/Rome` e stato `ENABLED`. I 17 valori d'ambiente del file di produzione coincidevano con quelli live prima dell'aggiornamento. Il digest precedente, disponibile come riferimento per il rollback, era `sha256:7af9d579cdc135b1823e226ae99aec7fb3ec93276d5aa0af80910923b363fe04`.

Le sole policy `morning-forecast-failures` e `evening-forecast-failures` sono state applicate una alla volta. L'audit della configurazione precedente dava `unchanged` per entrambe: la sola differenza richiesta era `notificationPrompts = ["OPENED"]`. Dopo ciascuna applicazione, l'audit della nuova configurazione dà `unchanged`. Le policy `morning-forecast-last-success` e `evening-forecast-last-success` restano `unchanged` e continuano a notificare anche il recupero. Soglie, finestre, canale e pianificazioni non sono stati modificati.

## Portata e verifica successiva

Un token FCM confermato invalido e disattivato conta ora come destinatario ritirato anche al mattino, senza far fallire il job. Errori temporanei FCM, problemi della fonte e disattivazioni non confermate restano fallimenti. Non è stato avviato alcun job o invio manuale: al controllo finale l'ultima esecuzione mattutina era ancora quella ordinaria del 6 novembre alle 07:30 CET. La prima corsa ordinaria con la nuova immagine è attesa il 7 novembre alle 07:30 CET e il suo esito non è ancora verificato.

Le previsioni ICON mancanti nella sintesi serale richiedono un'indagine distinta. Questo intervento non cambia il codice della serale, il frontend, gli artefatti Android o Web, né le pubblicazioni applicative.
