# Anticipazione meteo serale — 30 settembre 2026

## Stato

Implementazione promossa su `main` e attivazione di produzione completata il
30 settembre 2026.

- Cloud Run Job `meteofriul-evening-forecast` creato e aggiornato;
- scheduler omonimo abilitato alle `20:45` `Europe/Rome`;
- delivery generale `send`, gate singolo disattivato;
- nessun selettore di test persistito nel job;
- policy Cloud Monitoring applicata e audit finale `ready=true`;
- nessun invio generale manuale eseguito dopo l'attivazione;
- nessun APK/AAB generato;
- prossima esecuzione pianificata: 1 ottobre 2026 alle `20:45`
  `Europe/Rome`.

Il preflight iniziale in sola lettura del 30 settembre 2026 aveva confermato
l'account `meteofriul@gmail.com`, il progetto `meteo-friul` e l'assenza sia del
job sia dello scheduler. La successiva applicazione autorizzata ha creato
entrambe le risorse lasciando la delivery spenta.

Il ramo parte da `main` al commit
`8b87b965fbc5fa5b686af413a8b6d9eb7a4db7c1` e al commit di merge
`02b1e29f` incorpora il lavoro separato sulla resilienza ICON. Il lavoro webcam
resta escluso e continua sul ramo dedicato `codex/webcam-sources-review`.

## Gate IAM prima del deploy

Il workstream separato `codex/notification-runtime-iam`, al commit `85fa2cdc`,
ha creato e verificato
`meteofriul-runtime@meteo-friul.iam.gserviceaccount.com`. Il readback live del
30 settembre 2026 conferma esclusivamente `roles/datastore.user` e il ruolo
custom con la sola permission `cloudmessaging.messages.create`.

Lo script di deploy serale usa questa identita' e contiene un contratto che
rifiuta il Compute default. Assegna inoltre allo scheduler esistente
`official-alert-scheduler@meteo-friul.iam.gserviceaccount.com` soltanto
`roles/run.invoker` sulla risorsa del nuovo job e ne verifica il readback. La
preparazione IAM non ha creato o modificato job, scheduler o servizi e non ha
attivato notifiche.

## Evidenze di build e preattivazione

- commit applicativo verificato: `1b58908e`;
- test backend: `1349` superati;
- contratto operativo e controllo pulizia workspace: superati;
- Cloud Build: `41eee53a-b702-449e-bf9e-749308f95f93`, stato `SUCCESS`;
- immagine live immutabile:
  `europe-west1-docker.pkg.dev/meteo-friul/meteofriul/backend@sha256:4f2f6da0db893cc65fe7c53921a4a7154dc8c089b6eac285da20e4677c950568`;
- account runtime del job:
  `meteofriul-runtime@meteo-friul.iam.gserviceaccount.com`;
- invoker scheduler limitato alla risorsa del job: verificato;
- esecuzione in configurazione permanente `off`:
  `meteofriul-evening-forecast-z8pvw`, `status=disabled`, zero tentativi e zero
  invii;
- esecuzione con override effimero `dry_run` e selettore owner:
  `meteofriul-evening-forecast-rm6c4`, una installazione eleggibile, una
  localita' valutata, sorgente valida, zero errori e `sent=0`;
- readback successivo: modalita' permanente ancora `off`; hash, run-id e filtro
  piattaforma di test assenti dalla configurazione persistita.

La build usa ancora l'identita' Cloud Build preesistente. Questa non e'
l'identita' runtime del job e resta un eventuale hardening IAM separato.

## Collaudo sul telefono reale

Collaudo completato il 30 settembre 2026 su Samsung `SM-A525F`, pacchetto Play
`com.meteofriul.app`, versione `0.1.8` (`300025`). Non e' stato installato o
generato alcun APK/AAB. Il permesso notifiche era gia' concesso.

- apertura normale dell'app: registrazione backend rinnovata e associata in
  modo univoco al `device_id` SHA-256, senza leggere o mostrare il token FCM;
- dry-run sul telefono: esecuzione `meteofriul-evening-forecast-c95p6`, un
  dispositivo eleggibile, una previsione valutata, zero errori e zero invii;
- invio italiano con app in primo piano:
  `meteofriul-evening-forecast-sr2jf`, `status=sent`, una consegna;
- notifica italiana verificata nel pannello Android: titolo
  `Domani a Pordenone`, corpo `Giornata soleggiata. Apri e guarda.`;
- tap verificato: rimozione automatica della notifica e apertura del Bollettino
  OSMER di Pordenone;
- ripetizione con lo stesso run-id:
  `meteofriul-evening-forecast-5824w`, `status=deduplicated`, zero nuovi invii
  e nessuna seconda notifica;
- lingua cambiata dall'interfaccia dell'app a Furlan e normale registrazione
  backend verificata, senza modifica diretta dei documenti Firestore;
- invio friulano con app in background:
  `meteofriul-evening-forecast-mnbhk`, `status=sent`, una consegna;
- notifica friulana verificata nel pannello Android: titolo
  `Doman a Pordenone`, corpo `Zornade di soreli. Vierç e cjale.`;
- tap verificato dal background: ripresa della stessa app e apertura del
  `Boletin` OSMER; nessuna notifica residua;
- lingua infine ripristinata a italiano nell'app e nel backend.

Il readback conclusivo conferma nuovamente la configurazione permanente
`off`, gate singolo attivo e assenza di hash, run-id o piattaforma di test
persistiti.

## Promozione e attivazione di produzione

Il lavoro notifiche e IAM e' stato promosso su `main` al commit di merge
`af0d9860`. La prima CI ha rilevato un test Scopri dipendente dalla data e non
correlato alle notifiche: il test e' stato reso deterministico nel ramo
separato `codex/discover-date-stable-test`, senza modificare il comportamento
dell'app, e integrato in `main` al commit `9944a4a3`.

La CI GitHub Actions `36761971249` e' quindi terminata con successo:

- backend: verde;
- frontend, inclusi test, guard API, lint e build: verde;
- contratti Hosting preview e Android release: verdi.

Dopo la CI verde, il deploy ha mantenuto l'immagine immutabile gia' collaudata
e ha applicato la configurazione versionata. Il readback live conferma:

- `EVENING_FORECAST_DELIVERY_MODE=send`;
- `EVENING_FORECAST_REQUIRE_SINGLE_TARGET=false`;
- `EVENING_FORECAST_TEST_INSTALLATION_HASH` assente;
- `EVENING_FORECAST_TEST_RUN_ID` assente;
- scheduler `ENABLED`, cron `45 20 * * *`, fuso `Europe/Rome`;
- runtime service account dedicato e invoker scheduler verificato;
- audit del job `ready=true`.

L'ultimo tentativo dello scheduler del 30 settembre era gia' avvenuto alle
`20:45`, prima dell'attivazione generale. Non e' stata forzata una corsa fuori
orario: il readback indica come prossima esecuzione il 1 ottobre 2026 alle
`20:45` `Europe/Rome`.

La sincronizzazione Cloud Monitoring ha creato la policy errori del job
serale; ha inoltre aggiornato le policy errori di avvisi locali e ICON FVG e
creato i controlli di ultima esecuzione riuscita per avvisi locali, ICON FVG e
ICON nazionale. Il secondo audit ha trovato tutte le dodici policy gestite
`unchanged` e ha restituito `ready=true`.

## Contratto funzionale

Il job `app.jobs.send_evening_forecast` prepara una sola anticipazione per
dispositivo e giornata prevista. L'orario di esercizio proposto e' `20:45`
`Europe/Rome`: dopo il ciclo ICON delle `18:00 UTC`, con 45 minuti di margine
durante l'ora legale e un margine maggiore durante l'ora solare.

La notifica usa il consenso esistente `weather_notices`, il canale Android
`mf_weather_notices_v1` e apre il Bollettino. La lingua deriva dal campo
registrato `language=it|fur`; non viene inferita dal Comune o dalla lingua del
server.

## Dati e criterio fail-safe

La sorgente ICON instradata fornisce fino a 48 ore. Il job ne richiede 36 e
seleziona esclusivamente la giornata civile successiva nel fuso
`Europe/Rome`. Servono serie coerenti per:

- orario;
- precipitazione totale, pioggia e rovesci;
- neve;
- codice meteo;
- raffiche a 10 metri.

La notifica non viene costruita se mancano almeno 20 righe della giornata, se
la copertura non arriva dalla notte alla sera o se una serie e' incoerente.
La corsa dichiarata da `source_run_id` non puo' inoltre avere piu' di 10 ore:
alle 20:45 questo ammette il ciclo serale atteso e rifiuta quello del mattino.
Un dato parziale o stale non viene trasformato in un testo rassicurante.

La priorita' editoriale e': temporali, precipitazioni gelate, neve, vento
forte, pioggia, poi condizione prevalente. La soglia del vento forte riusa la
soglia operativa delle raffiche locali (`70 km/h`).

## Copia compatta

Titolo:

- IT: `Domani a {localita}`;
- FUR: `Doman a {localita}`.

Corpi principali:

| Caso | Italiano | Friulano |
| --- | --- | --- |
| sole | `Giornata soleggiata. Apri e guarda.` | `Zornade di soreli. Vierç e cjale.` |
| nuvole con aperture | `Nuvoloso, possibili schiarite. Apri e guarda.` | `Nulât, pussibilis sclaridis. Vierç e cjale.` |
| pioggia pomeridiana | `Pioggia dal pomeriggio. Apri e guarda.` | `Ploie dal dopomisdì. Vierç e cjale.` |
| vento serale | `Vento forte in serata. Apri e guarda.` | `Aiar fuart in serade. Vierç e cjale.` |

Sono inoltre gestiti nebbia, temporali, neve, precipitazioni gelate, giornata
nuvolosa e tempo variabile, con la stessa struttura breve e le tre fasce
`mattinata`, `pomeriggio`, `serata`.

## Deduplica e consegna

- kind: `evening_forecast`;
- firma: namespace `meteofriul-evening-forecast-v1` e data prevista;
- collapse key e tag: `mf-evening-forecast`;
- TTL: 3 ore;
- massimo un invio per dispositivo e data prevista;
- italiano come fallback soltanto se un vecchio record non contiene una lingua
  valida.

## Ordine di attivazione

1. Integrare o riallineare prima il ramo separato della resilienza ICON.
2. Eseguire l'intera suite backend e i contratti operativi locali.
3. Creare il job in modalita' `off` e verificare il readback.
4. Passare a `dry_run` con gate singolo e controllare copertura/freschezza.
   Usare `EVENING_FORECAST_TEST_INSTALLATION_HASH` come override temporaneo
   per selezionare esattamente il `device_id` SHA-256 del telefono owner. Non
   salvare l'hash nel job e non usare mai il token FCM come selettore.
5. Eseguire due invii owner, uno IT e uno FUR, sul telefono reale; controllare
   testo non espanso, tap verso Bollettino e assenza di duplicati.
6. Solo dopo approvazione, rimuovere il gate singolo, impostare `send` e creare
   la policy di monitoraggio.

Tutti i punti 1-6 sono completati. L'attivazione generale e il monitoraggio
sono stati applicati soltanto dopo la promozione su `main`, la CI verde e il
collaudo reale gia' documentato.
