# Allerte FVG: deploy e verifica ordinaria completata

20 ottobre 2026: deploy verificato. **Controllo completato il 21 ottobre:
acquisizione ripristinata, primo invio parziale e otto esecuzioni successive riuscite.** Ramo `codex/fvg-alerts-deploy`, partito da
main `5cbcd35ca88088220ff167b299cb4353ebdaf6d4` con CI verde.

## Autorizzazione e perimetro

Il proprietario ha autorizzato deploy e verifica della prossima corsa, senza
esecuzioni manuali, AAB o installazioni. Successivamente ha chiarito
«se serve inviamo» e richiesto una verifica del funzionamento reale.
Pertanto si conserva **send/true**, con destinatari e regole preesistenti.
Questa indicazione sostituisce il precedente vincolo senza invii e il piano
preparatorio off/false; non autorizza notifiche di prova o esecuzioni manuali.

## Distribuzione verificata

- Job `meteofriul-official-alert-sync`, progetto `meteo-friul`, regione
  `europe-west8`; account `meteofriul@gmail.com` verificato.
- Aggiornamento completato: `2026-10-20T19:44:31.901961+00:00`.
- Candidata: `europe-west1-docker.pkg.dev/meteo-friul/meteofriul/backend@sha256:7364eca349bda9afb5cdbb9c88a9e3f01c7fc14f0bea8f0595ad926fc8f43368`.
- Rollback compatibile: `europe-west1-docker.pkg.dev/meteo-friul/meteofriul/backend@sha256:af2390e06de733509ac69304d2972cec48363e53a59e2049d75f75a5e76daca4`.
- Cloud Build `d4ebd2e8-3298-414c-966d-33cc945d2695`, SUCCESS: prima rollback e verifica, poi candidata
  e verifica. Immagine base fissata, nessun aggiornamento di dipendenze.
- Tre soli moduli runtime della correzione approvata, byte per byte uguali a
  main: parser, riconciliazione/persistenza e firma della mappa livelli.
  L'API esistente legge i record nuovi: nessun deploy API necessario.
- Cambiata solo l'immagine del job. Tutte le variabili, destinatari, identità,
  memoria 512 MiB, retry, timeout e scheduler sono invariati. Restano invariati
  gli altri 13 job, 11 scheduler e API.
- Nessuna esecuzione creata dal deploy. Il prossimo avvio ordinario è
  **20 ottobre, 22:00 Europe/Rome / 20:00 UTC**.

## Allerta ufficiale e lettura dell'app prima della corsa del 20 ottobre

La lettura delle fonti pubbliche alle `2026-10-20T19:38:13.016707+00:00` trova l'allerta
**30/2026**, corroborata fra widget PCR e ARPA: A/B arancione, C gialla,
D verde; validità dalle 00:00 del 21 ottobre alle 06:00 del 22 ottobre.
[Bollettino ufficiale](https://pianiemergenza.protezionecivile.fvg.it/alerts/30_2026.pdf).
La verifica riconcilia le fonti solo in memoria: nessuna scrittura o notifica.

Prima della corsa ordinaria l'API Play restituisce ancora zero allerte con
`official_alerts_unavailable` / `persistent_snapshot_unavailable`: non è una
conferma di assenza di rischio. Il readback dopo il deploy è conservato.
La comparsa dell'allerta dipende dall'acquisizione e dalla persistenza riuscite
alle 22:00, poi dal normale aggiornamento dell'app. Il formato pubblico mantiene
il livello più alto e il link al bollettino; zone e livelli distinti restano
nei dati. Nessun frontend o pacchetto Android è stato distribuito qui.

## Controlli completati

172 verifiche offline locali, poi le stesse 172 in ciascuna immagine Linux,
zero errori/fallimenti/skip. Non sono 516 casi distinti. Rete disabilitata,
memoria container limitata a 512 MiB; verificati 127 moduli runtime effettivi
per immagine. Coperti schema v2/v3, alterazione dei dati, fonti discordanti,
scadenza, vecchio lettore API, destinatari, deduplicazione e gestione errori
degli invii; i sender dei test sono fittizi.

Il modulo `repositories/push.py` è identico alla base attestata. Nuovo set
[writer](../../release-history/firestore-ttl/runtime-writer-sets/play-services-fvg-20261020.json)
e [attestazione](../../release-history/cloud-operations/20261020-fvg-alert-deploy/backend.json)
aggiunti senza riscrivere le prove precedenti. Audit LIVE TTL, immagini,
scheduler e archivio notifiche: **ready=true, zero rilievi bloccanti**.

Il verificatore locale del ramo di deploy ammette che una stessa Cloud Build produca candidata
e rollback: richiede comunque il digest esatto fra i risultati e lo stesso hash
dell'archivio sorgente. Restano rifiutati digest assente e archivio diverso;
nuovi casi positivi/negativi e suite di contratto superati. Non è una deroga
alla verifica delle immagini. Nessuna AAB o altra modifica cloud deriva
da questo aggiornamento degli strumenti locali. La promozione dei verbali
non modifica gli script operativi di main; le prove descrivono gli strumenti
usati sul ramo di deploy.

## Perché serve il rollback

Il nuovo writer salva prove `runtime-v3`, che includono la mappa dei livelli.
Il vecchio lettore rigido potrebbe rifiutarle. Il rollback costruito legge v2/v3
e mantiene il vecchio writer v2; non cancella o riscrive lo storico.
Non ripara però l'acquisizione di nuove allerte a livelli misti.

Il [comando preparato](../../release-history/cloud-operations/20261020-fvg-alert-deploy/rollback-command.txt)
è solo una procedura di emergenza, **non eseguita né automatica**. Imposta
off/false durante il ripristino per evitare invii con la vecchia firma di
deduplicazione, mantenendo obbligatoria la persistenza. Prima di usarlo servono
una valutazione del problema e il controllo delle esecuzioni attive.
Questa cautela sul rollback non cambia il normale candidato, che resta send/true.

## Criteri del controllo dopo il deploy

Il piano iniziale prevedeva il follow-up alle **22:05** e un secondo passaggio
alle **22:15** del 20 ottobre se necessario. Chiusura effettuata il 21 ottobre
su richiesta esplicita del proprietario, conservando il primo esito parziale.
Lo script canonico `.tmp/verify_fvg_ordinary.py` legge esecuzione, log, snapshot
Firestore, API Play/predefinita e fonti pubbliche. Non avvia job né sender.
La verifica deve confermare:

1. Avvio dallo scheduler con il digest previsto; refresh riuscito e persistenza.
2. Fonti fresche e concordi; allerta, zone, massimo, orari, PDF e schema v3
   coerenti fra fonte, Firestore e risposta letta dall'app.
3. Esito reale delle notifiche: invio, nessun destinatario idoneo, deduplicazione,
   parziale, errore o invio non confermato, con i relativi contatori.

`sent` dimostra l'accettazione da FCM, non la visualizzazione sul telefono.
Non sono state eseguite prove visive o installazioni su dispositivi.
Un job verde da solo non chiude la verifica. Non inventare invii in assenza
di destinatari e non reinviare manualmente per provare il canale.

Evidenze selezionate nel [manifesto](../../release-history/cloud-operations/20261020-fvg-alert-deploy/SHA256SUMS.txt).
Gli originali completi restano nella `.tmp/fvg-alerts-deploy-20261020` canonica,
esclusa da Git; copie ripulite e strumenti sono versionati localmente.
Le copie dei tool si eseguono dalla `.tmp` canonica, non dalla cartella archivio.
Nessun push Git, deploy Web/API, AAB, installazione o emulatore effettuato.

## Verifica del 21 ottobre e chiusura del promemoria

**Acquisizione, persistenza e lettura dell'allerta sono funzionanti.** La prima
corsa ordinaria del 20 ottobre alle 22:00 italiane aveva acquisito l'allerta
30/2026, ma aveva concluso con invio parziale: **45 tentativi, 44 accettazioni
FCM, un errore, zero invii non confermati**. Questo esito rimane parziale;
non viene riclassificato come successo. Il precedente audit della release
0.1.15 classifica il caso come `failed_invalid_token / fcm_token_invalid`;
il runtime non permette di distinguere Unregistered da SenderIdMismatch.
Nessun destinatario ripristinato o invio ritentato manualmente.

Le **otto esecuzioni ordinarie successive**, dalle 00:00 alle 14:00 italiane
incluse del 21 ottobre, sono tutte riuscite. Verificati per ciascuna creatore
scheduler, digest distribuito e configurazione `send/true`: refresh riuscito,
cache dichiarata fresca, persistenza Firestore e nessun errore della sorgente.
Ogni esecuzione registra 44 deduplicazioni, zero nuove notifiche, zero errori
e zero invii non confermati. Sono gli stessi destinatari già gestiti: non
sono 352 notifiche o destinatari distinti. Il job non ha ripetuto l'allerta.

Il confronto attuale conferma massimo regionale arancione, zone A/B arancione,
C gialla e D verde; validità dalle 00:00 del 21 alle 06:00 del 22 ottobre,
bollettino 30/2026. API Play, API predefinita, snapshot Firestore e fonti
ufficiali concordano su livello, zone, validità e PDF. Il record persistente
e' `runtime-v3`, aggiornato dalla corsa delle 14:00 italiane.

**Limite osservato nella prima lettura HTTP:** l'API Play ha inizialmente
restituito `official_alerts_unavailable`, con archivio `refreshing` e nessuna
allerta nel corpo. Lo script ha correttamente interrotto il controllo per
incoerenza; la risposta non è stata interpretata come assenza di rischio.
Una sola rilettura alle 15:37 italiane ha restituito l'allerta e `fresh/firestore`,
coerenti con le altre tre fonti. Questo documenta il recupero, non dimostra
assenza di risposte temporanee indisponibili o corretto comportamento visivo
di ogni client. Non sono stati modificati cache, dati o servizi.

Il proprietario aveva già confermato in chat l'arrivo della notifica sul
proprio telefono. Non è una prova di ricezione su tutti i dispositivi e non
certifica la futura AAB. Nessuna nuova verifica visiva o installazione.

Il verificatore originale è stato rieseguito dalla radice canonica; sono stati
spostati soltanto l'output in una sottocartella separata e il riferimento locale
al contesto della candidata, preservando le evidenze del 20 ottobre. Le letture
aggiuntive dei log riguardano le otto corse già concluse. Nessuna esecuzione,
notifica manuale, modifica di destinatari o configurazioni, deploy, AAB o push.

Il promemoria **«Verifica allerte FVG dopo deploy» è stato eliminato**, come
richiesto dal proprietario: il controllo una tantum è concluso. L'esito
parziale iniziale e la distinzione degli errori FCM restano documentati come
questione separata; non si tengono attivi controlli limitati al 20 ottobre.

Evidenze ripulite: [esito e limiti](../../release-history/cloud-operations/20261020-fvg-alert-deploy/recheck-20261021/result.json),
[otto corse successive](../../release-history/cloud-operations/20261020-fvg-alert-deploy/recheck-20261021/subsequent-results.json),
[manifesto SHA-256](../../release-history/cloud-operations/20261020-fvg-alert-deploy/recheck-20261021/SHA256SUMS.txt).
Le prove grezze rimangono nella `.tmp` canonica, escluse da Git.

### Forma delle copie promosse su main

Nelle copie archiviate `source-provenance.json` e `recheck-20261021/result.json`,
19 valori SHA-256 associati a nomi contenenti API o auth sono espressi come
oggetti con campo `sha256`, per distinguerli dalle credenziali nei controlli
automatici. I valori sono invariati; la riconversione alla forma originaria
è stata confrontata strutturalmente con gli originali. I manifesti SHA-256
identificano le copie in questa forma; i file grezzi e le evidenze conservate
sul ramo di deploy restano invariati. Nessuna regola del controllo privacy è
stata modificata o disabilitata.
