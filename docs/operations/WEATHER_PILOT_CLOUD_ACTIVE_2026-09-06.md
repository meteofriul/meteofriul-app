# Pilot meteo cloud — stato operativo 6 settembre 2026

Questo documento aggiorna lo stato corrente; GOOGLE_ONLY conserva la cronologia dei passaggi precedenti.

## Operativo e verificato

- Progetto esclusivo `meteofriul-pilot-20260906`, europe-west1. Progetto beta `meteo-friul` non modificato.
- HTTPS `https://pilot-weather-335641913741.europe-west1.run.app` (API dati, non sito UI).
- ICON: acquisizione cloud e pubblicazione completa riuscite, run `20260906T120000Z`, 215 comuni. Esecuzione `pilot-icon-kbzgg`, circa 166 secondi inclusa partenza.
- CAMS: prima esecuzione `pilot-cams-98qmc` ha salvato richiesta ADS e terminato pending; ripresa `pilot-cams-ngsjv` ha pubblicato core e pollini insieme, run `20260906T000000Z`, circa 372 secondi. Nessuna seconda submission necessaria.
- HTTPS ha restituito puntatori ICON e CAMS verificati. Reader conserva le verifiche dei manifest e controlla i metadati dei comuni in parallelo; prima richiesta CAMS misurata circa 3,86 secondi (misura singola, non SLA).
- Scheduler ICON: 06:00 e 18:00 UTC, 2 finestre/giorno; CAMS: 05:00, 10:00, 15:00 e 20:00 UTC, 4 finestre/giorno. CAMS già pubblicato non si riscarica. Attesa ADS limita il tempo in esecuzione; le finestre consumate non vengono cancellate.
- Prova reale scheduler→job riuscita: `pilot-icon-sc2qj` e `pilot-cams-cs9dx` completati con successo; entrambe le pianificazioni ENABLED e ultimo invio senza errore. Le future esecuzioni a orario non sono ancora state osservate.
- APK localpilot cloud installato sul Samsung OWNER_DEVICE_SERIAL; SHA256 `1ca16411d80e72e0785fb30f00ac001d398af5ec730f90edc2cc90637d48d52c`. Orologio reale, nessun ponte adb reverse 8781 presente. Verificati Home, aria e pollini sul telefono; screenshot in `.dev-logs/local-weather-pilot/phone-cloud-20260906.png` e `phone-cloud-forecast-20260906.png`.
- 100 test client/cache e 10 test guardie di build passati. Build Android protetta riuscita. Test cloud documentati nelle build Linux.
- Build finale `12404cdc-9291-42a6-bd2b-30a1cce6b42d` SUCCESS con 28 test cloud. ICON aggiornato al digest `d33da939bb659d395a6da5da9dbfa6287013db6c1dfc0c070e61b47e06055bc4`: gli esiti negativi di pubblicazione producono exit nonzero. CAMS resta al digest verificato `ba47163b1d59e3afcb21ac6953a784031843d766a213847fbfba10ca98096372`; reader al digest `200978b1e3735b0fdac7310613a3fac2292099b0228217ed1073a001f710b483`. Tutte le immagini nel registro `europe-west1-docker.pkg.dev/meteofriul-pilot-20260906/pilot/weather-worker`.

## Isolamento e sicurezza

Identità distinte pilot-icon, pilot-cams, pilot-reader e pilot-scheduler. La proposta iniziale objectUser su entrambi i bucket è stata rifiutata e NON applicata. In alternativa: ruoli custom GET/CREATE, condizioni sui soli percorsi del rispettivo provider; DELETE necessario per sostituzione solo su latest e snapshot di stato CAMS. Payload immutabili senza DELETE. Reader solo GET su `pilot/weather/v1/`, senza elenco, scritture, stato interno o ADS. Scheduler invoker sui due job, non a livello di progetto.

Secret `pilot-ads:1`, replica europe-west1, autorizzato esplicitamente dall'utente; secretAccessor runtime solo a pilot-cams. Restano i normali privilegi amministrativi ereditati del progetto. Nessun segreto incluso nel codice, APK o immagine.

La pubblicazione HTTPS è accessibile senza autenticazione perché contiene dati meteo pubblici. CORS limita gli origin browser previsti ma NON è autenticazione né limite di spesa. Il bucket resta privato. Solo corse referenziate da puntatori verificati vengono esposte; endpoint di stato/ADS assenti.

## Limiti e costi

Job: 1 CPU, 1 GiB, 1 task, parallelismo 1, retry 0. ICON massimo 900 s, CAMS 600 s. Scheduler retry 0. Reader richiesta-fatturata, min 0/max 1 istanza, 512 MiB, concorrenza 4, timeout 90 s, niente CPU boost.

Stima prudenziale del solo calcolo job senza quote gratuite: `31 × (2×900 + 4×600) × (0,000018 + 0,000002) = 2,604 USD/mese`. È uno scenario massimo delle finestre configurate, non un hard cap globale (partenze, prove manuali e invocazioni aggiuntive costano a parte). Due scheduler circa 0,20 USD/mese senza free tier. Aggiungere storage, operazioni, registry, secret, build, log, letture/traffico HTTPS, conversione valuta e imposte. Per un piccolo pilot, margine operativo orientativo 1–1,5 EUR oltre al calcolo job; da confrontare con la fattura reale, non promessa di prezzo.

Budget notifiche prudenziale già impostato a 4 EUR; obiettivo utente 5 EUR/mese, accettato come budget operativo non garantito. Reader max1 non è un limite monetario: traffico anomalo può superare la stima. Non estendere a una platea pubblica senza riesame.

Archivi build: scadenza 7 giorni, soft delete disabilitato solo sul bucket build. Dati: corse immutabili oltre 30 giorni soggette a lifecycle; latest esclusi, soft delete dati lasciato invariato. Non è stato cancellato alcun dato attuale. Nessuna pulizia dei digest delle immagini in uso: mantenerli disponibili per rollback.

Fonti tariffe: [Cloud Run](https://cloud.google.com/run/pricing), [Scheduler](https://cloud.google.com/scheduler/pricing), [Storage](https://cloud.google.com/storage/pricing), [Artifact Registry](https://cloud.google.com/artifact-registry/pricing).

## Limiti residui e gestione

Questo chiude il collegamento/acquisizione automatica ICON e CAMS europeo del pilot; NON certifica tutta l'app al 100%. Push pilot restano disabilitate, UV globale e altri interventi funzionali sono separati. Anche gli errori/ritardi dei provider possono impedire una nuova pubblicazione; si conserva l'ultima corsa entro i limiti di validità client, poi si mostra indisponibilità, mai dati inventati.

Un intent ADS senza job richiede riconciliazione, non una nuova submission automatica. Ritardi oltre tutte le finestre giornaliere e manutenzioni prolungate richiedono controllo; nessuna garanzia di freschezza assoluta. Controllare prime esecuzioni a orario e costi reali prima di ampliare i tester. Non abilitato un nuovo sistema di notifiche operative.

Per sospendere i costi dei job: mettere in pausa solo `pilot-icon-refresh` e `pilot-cams-refresh` nel progetto pilot; non usare comandi sul progetto predefinito. Per il reader usare revisione precedente verificata, senza cambiare beta o Firebase. La modalità locale APK resta disponibile omettendo `-WeatherCloud` nello script protetto.
