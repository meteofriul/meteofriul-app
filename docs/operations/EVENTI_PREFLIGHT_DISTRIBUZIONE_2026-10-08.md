# Eventi: controllo prima del job distribuito, 8 ottobre 2026

> Stato successivo: [distribuzione diretta del catalogo a 15 fonti](EVENTI_DISTRIBUZIONE_15_FONTI_2026-10-08.md).
> Questo documento conserva il controllo preliminare e il piano proposto in quel momento.

## Esito

**Il ramo non va collegato direttamente al job ufficiale.** Il codice a 15
fonti ha superato il [ciclo locale completo](EVENTI_CICLO_UNICO_15_FONTI_2026-10-08.md),
ma il catalogo online usa ancora sette fonti e non possiede il checkpoint
annuale TurismoFVG necessario al primo ciclo del nuovo lettore.

Questo controllo e' stato in sola lettura per Google Cloud. Non sono stati
creati job, immagini, oggetti Storage, APK o release.

## Evidenza letta dal progetto ufficiale

- Progetto gcloud attivo: `meteo-friul`; account attivo:
  `meteofriul@gmail.com`.
- Endpoint HTTPS Events: `/health` risponde con `pilot-events`.
  `/api/local/events` per Trieste entro 20 km risponde `ready`, 82 record,
  sette fonti e nessuna scheda Barcolana. Le fonti sono Azalea, CSS Udine,
  Pordenone Pensa, Pordenonelegge, Teatro Verdi Pordenone,
  Teatro Verdi Trieste e TurismoFVG.
- Oggetto `gs://meteo-friul-weather-data/pilot/events/v1/catalog.json`:
  sette lotti `fresh`, 1.095.345 byte, nessun `control_checkpoint` nel lotto
  TurismoFVG. Il lotto regionale contiene 136 schede.
- Job `meteofriul-events-refresh`: un task, una CPU, 512 MiB, timeout 900 s,
  zero retry, service account `meteofriul-events-writer`; Scheduler abilitato
  ogni giorno alle 04:00 UTC. Le esecuzioni del 6, 7 e 8 ottobre risultano
  riuscite con l'immagine precedente.

## Controlli del candidato

- Catalogo locale del ramo: 15/15 lotti `fresh`, zero revisioni,
  3.072.048 byte, inferiore al limite di 8 MiB. TurismoFVG ha 1.441 schede
  e un checkpoint annuale completo.
- 53 test mirati di pubblicazione, catalogo, raccolta e HTTP passano.
- Il contesto Cloud Build in allowlist ometteva `test_attems_audit.py`, che
  il Dockerfile copia e lancia. L'allowlist del ramo ora lo include; i 33 file
  di test richiesti dal Dockerfile esistono e sono ammessi nel contesto.
- Il [primo avvio locale senza checkpoint](EVENTI_COLD_START_LOCALE_2026-10-08.md)
  ha controllato 960 di 2.433 dettagli nei 360 secondi concessi alla fonte.
  Ha salvato il progresso, ma non poteva dichiarare TurismoFVG `fresh`.
- `pilot_cloud.publish` carica il catalogo prima di sollevare l'errore di
  fonte incompleta. `query_catalog` non restituisce schede TurismoFVG quando
  il lotto e' `stale` per `incomplete_source`. Aggiornare direttamente il job
  ufficiale farebbe quindi sparire temporaneamente le 136 schede regionali
  online durante il primo ciclo.

## Collaudo distribuito necessario

1. Costruire l'immagine del ramo con il contesto Events in allowlist.
2. Eseguire un job separato, senza Scheduler e con una chiave Storage di
   collaudo diversa da `pilot/events/v1/catalog.json`; inizializzarla con il
   checkpoint locale completo verificato. Il servizio Events ufficiale deve
   continuare a leggere solo il catalogo attuale.
3. Verificare nel risultato remoto 15 fonti `fresh`, zero revisioni,
   `source_complete=true` per TurismoFVG, dimensione entro 8 MiB e risposte
   complete per Trieste e Pordenone. Se il job fallisce, conservare l'esito
   nella sola chiave di collaudo.
4. Solo dopo un collaudo riuscito, preparare la promozione coordinata del
   catalogo e del job ufficiale, con lettura di ritorno dell'API e prova
   dell'app. Questa fase non e' stata eseguita.
