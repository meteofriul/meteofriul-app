# Attivazione nazionale Avvisi locali — 25 settembre 2026

## Esito

Gli Avvisi previsionali Meteo Friûl sono abilitati direttamente per i Comuni
italiani selezionati manualmente, senza fase shadow o coorte. La posizione GPS
automatica resta limitata al FVG finché non è disponibile un resolver nazionale
dei confini comunali: fuori regione il backend non approssima il Comune dal punto
più vicino. Le Allerte ufficiali restano distinte e limitate al FVG.

La precisione massima accettata resta 250 m. La prova GPS salvata è valida per
60 minuti. Il job Avvisi viene eseguito ogni ora in `Europe/Rome`; la
deduplicazione esistente resta attiva.

## Codice e verifiche

- Commit funzionale: `c9fab10 feat: enable nationwide local weather notices`.
- Suite backend completa: 1.241 test superati, 633 subtest superati, 7 warning.
- Suite mirata finale: 102 test superati, 66 subtest superati.
- Smoke test reale del contratto nazionale ICON su Roma (`ISTAT 058091`):
  risposta valida, run `20260925T000000Z`, otto ore validate, esito
  `no_candidate`, nessun errore di validazione.
- Il routing conserva la sorgente ICON v1 per il FVG e usa il contratto ICON v2
  nazionale per gli altri Comuni.
- Il convertitore conserva esplicitamente i codici WMO per temporali, pioggia
  congelantesi e neve intensa prima delle derivazioni generiche.

## Rilascio Cloud Run

- Account verificato: `meteofriul@gmail.com`.
- Progetto verificato: `meteo-friul`.
- Build Cloud Build: `ab6fc99e-d17c-4ec1-8ac5-d49a48ec4ef6`, stato
  `SUCCESS`.
- Immagine distribuita esclusivamente al job `meteofriul-local-notice`:
  `europe-west1-docker.pkg.dev/meteo-friul/meteofriul/backend@sha256:e3508cd26e840e7f9be97cef2a0fdd64d4e55315907dc7580a91b1dbb1f2736d`.
- Variabile aggiunta:
  `LOCAL_NOTICE_NATIONAL_ICON_BASE_URL=https://meteofriul-national-weather-49007668366.europe-west1.run.app/weather/v2/icon2i/`.
- Comando, argomenti, service account, timeout, CPU, memoria, retry ed elenco
  versioni Play sono rimasti invariati.

Il collaudo reale `meteofriul-local-notice-6hlxz` è terminato con successo in
46,09 secondi. Il riepilogo applicativo è `no_eligible_device`, con zero errori
di sorgente, storage, sicurezza e invio. Questo esito è normale quando non ci
sono dispositivi idonei registrati nel ciclo.

## Scheduler dopo il rilascio

| Job | Schedule | Fuso | Stato |
| --- | --- | --- | --- |
| `meteofriul-local-notice` | `0 * * * *` | `Europe/Rome` | `ENABLED` |
| `meteofriul-official-alert-sync` | `0 */2 * * *` | `Europe/Rome` | `ENABLED` |

Lo scheduler delle Allerte ufficiali, la relativa destinazione e il job Cloud
Run delle Allerte non sono stati modificati. Anche l'API non è stata aggiornata
da questo rilascio.

## Confini operativi

- Fuori FVG: Avvisi locali disponibili tramite Comune selezionato manualmente.
- In FVG: disponibili Comune manuale o prova GPS recente e precisa.
- Segnalazioni Community v2: continuano a essere nazionali e indipendenti dagli
  Avvisi locali.
- Allerte ufficiali: continuano a essere FVG e non vanno presentate come Avvisi
  previsionali.
- Non è richiesto un nuovo AAB per questa attivazione backend/scheduler.
