# Incastro ICON–sintesi e margine degli allarmi — 25 ottobre 2026

Stato: verifica in sola lettura e proposta locale; **nessuna integrazione distribuita**.
Nessuna modifica a codice applicativo, policy, orari, scheduler o destinatari;
nessun job, acquisizione o notifica manuale in questo controllo.
Il refresh Eventi manuale precedente resta documentato separatamente, e il
controllo ordinario del 26 ottobre alle 05:00 Europe/Rome rimane attivo.

## Risultato verificato

| Percorso | Pubblicazione ICON del 25/10, ora italiana | Sintesi mattutina | Margine |
| --- | --- | --- | --- |
| FVG | 07:03:15, corsa `20261025T000000Z`, published/verified | avvio 07:30:04 | circa 27 minuti |
| Nazionale | 07:03:14, stessa corsa, published | stessa finestra della sintesi | circa 27 minuti |

I job produttori sono conclusi rispettivamente alle 07:03:19 e 07:03:17.
Nove esecuzioni per produttore dal 21 al 25 ottobre risultano riuscite, senza
retry: durata massima FVG circa 4m17s, nazionale circa 4m37s. È un campione
operativo limitato, non una garanzia sui tempi futuri. La sintesi del 25 ottobre
ha chiuso alle 07:32:09 con 50 tentativi, 50 accettazioni FCM, zero errori e
17 gruppi; non è stata verificata la visualizzazione su ciascun telefono.

Durante la sua finestra temporale i log HTTP registrano 19 GET con user agent
del worker: latest, manifest e 17 documenti comunali della corsa
`20261025T000000Z`, tutti HTTP 200. Non compaiono richieste nazionali in questo
campione: dimostra la disponibilità nazionale, non un consumo nazionale effettivo.
Tempi, user agent e numero di gruppi sono concordi con la sintesi. Manca però
un identificativo che colleghi direttamente ogni richiesta all’esecuzione:
l’attribuzione al job è una ricostruzione coerente, non un audit per destinatario.
Il riepilogo applicativo non conserva `source_run_id`.

## Cosa cambia tra estate e inverno

| Regime | Acquisizione ICON mattutina | Sintesi | Relazione |
| --- | --- | --- | --- |
| Ora legale | 08:00 italiane (06:00 UTC) | 07:30 italiane (05:30 UTC) | la sintesi precede la nuova acquisizione di 30 minuti |
| Ora solare | 07:00 italiane (06:00 UTC) | 07:30 italiane (06:30 UTC) | 30 minuti tra gli avvii, oggi circa 27 dopo la pubblicazione |

Il 24 ottobre i 19 accessi del worker nella finestra mattutina leggono la corsa
`20261023T120000Z`, tutti HTTP 200: è la corsa precedente, disponibile prima
che parta l’acquisizione delle 08:00. Gli altri accessi nella stessa finestra,
provenienti da client diversi, sono esclusi dall’attribuzione.
Per la serale del 24 ottobre i 19 accessi del worker leggono
`20261024T120000Z`, tutti HTTP 200, dopo la pubblicazione intorno alle 20:03–20:04.

La serale mantiene le 20:45 locali: ha 45 minuti dall’avvio del produttore in
estate e 105 minuti in inverno. La corsa serale del 25 ottobre non è ancora
avvenuta durante il controllo. Nessun orario va corretto automaticamente in base
alla sola differenza UTC. Pretendere sempre il nuovo ciclo mattutino alle 07:30
non sarebbe compatibile con gli orari estivi attuali.

Il modello offline con ZoneInfo Europe/Rome verifica intervalli giornalieri
23 ore (29 marzo 2026 e 28 marzo 2027), 24 ore (giorni normali), 25 ore
(25 ottobre 2026). È un calcolo di calendario, non una prova di quelle corse.

## Allarme attuale: margine e limite

Le due policy «senza successi» usano ALIGN_SUM su 90.000 secondi (25 ore),
soglia < 1 per 300 secondi e dati mancanti trattati come condizione attiva.
Il passaggio all’ora solare ha distanziato i completamenti mattutini di
**90.004,211771 secondi**, cioè 25 ore e circa 4 secondi. Il margine rispetto
alla sola finestra di aggregazione è quindi esaurito; resta il periodo di
persistenza di cinque minuti. Questo non prova che sia scattato un falso allarme.

La metrica `run.googleapis.com/job/completed_execution_count` è campionata ogni
60 secondi e dichiara fino a 120 secondi d’ingestione, verificati anche nel
descrittore del progetto. La lettura retrospettiva alle 07:36 del 25 ottobre
contiene già il successo odierno. Non sono stati letti lo storico incidenti o
le email, né ricostruita la disponibilità della metrica a ogni istante passato.
Non si dichiara quindi un falso allarme osservato.

Nei giorni normali la finestra concede circa un’ora oltre la cadenza quotidiana;
al ritorno all’ora legale concede circa due ore, al ritorno all’ora solare quasi
nessuna. Perciò anche il tempo di rilevazione di una corsa mancante varia con la
stagione. La misura attuale conta l’intera esecuzione riuscita, senza distinguere
un blocco generale da un esito parziale con notifiche già accettate.

**Non basta aumentare la finestra a 26 ore:** 25 ore è il massimo dell’aggregazione
per questo tipo di policy. Il limite 90.000 nel validatore locale riflette quello
del servizio e non va aggirato. La persistenza di 5 minuti è distinta dalla
finestra; aumentarla potrebbe mitigare ritardi ma rallenta gli allarmi e non
rende il controllo consapevole della corsa giornaliera attesa.

Riferimenti ufficiali consultati il 25 ottobre:
- [Limite dell’aggregation alignmentPeriod](https://docs.cloud.google.com/monitoring/api/ref_v3/rest/v3/projects.alertPolicies#Aggregation).
- [Campionamento e ritardo delle metriche Cloud Run](https://docs.cloud.google.com/monitoring/api/metrics_gcp_p_z#run).
- [Finestre, persistenza e ritardi degli allarmi](https://docs.cloud.google.com/monitoring/alerts/concepts-indepth).
- [Scheduler e orologio locale nei cambi d’ora](https://docs.cloud.google.com/scheduler/docs/configuring/cron-job-schedules#time_zone).

## Integrazione proposta, non implementata

1. Conservare 07:30 e 20:45 in Europe/Rome e le acquisizioni in UTC.
   Identificare la corsa attesa con tipo di sintesi + data locale, convertendo
   in UTC l’istante tramite il fuso, senza aggiungere ciecamente 24 ore.
2. Controllare quella corsa dopo un margine iniziale proposto di 15 minuti:
   07:45 per il mattino e 21:00 per la sera. Il margine va confermato con
   accodamento/avvio, timeout attuale di 300 secondi senza retry e ritardo delle
   evidenze. Un controllo periodico può rilevarla più tardi della scadenza:
   la frequenza e la latenza massima vanno dichiarate prima del rilascio.
3. Distinguere assente, ancora in corso oltre termine, errore, parziale e
   completata. Separare assenza di destinatari o deduplicazione lecita da invio
   accettato. Una prova manuale non deve mascherare una corsa ordinaria mancante:
   verificare origine Scheduler, target ed esecuzione esatta.
4. Aggiungere al log aggregato della sintesi ID esecuzione, slot/data locale,
   corsa ICON e conteggio dei gruppi per corsa, momento della lettura ed esito.
   Nessun token, ID dispositivo, testo personale o coordinata. Così il consumo
   della corsa nuova si verifica direttamente senza ricostruire log HTTP.
5. Riutilizzare, se compatibile, il monitor periodico esistente in sola lettura
   di esecuzioni/log. Con l’attuale cadenza ICON ai minuti 10/40, una soglia 07:45
   sarebbe vista al controllo delle 08:10 e quella delle 21:00 alle 21:10:
   questi sono i tempi effettivi, non 07:45/21:00. Valutare questo compromesso
   prima di scegliere l’integrazione; nessun nuovo scheduler è creato ora.
   Conservare gli allarmi su errori effettivi e mancata invocazione. Sostituire
   il vecchio allarme «25 ore» soltanto quando il nuovo segnale è verificato,
   evitando sia silenzi sia doppie email per lo stesso esito.

Verifiche locali previste quando si implementerà: giorno da 23/24/25 ore,
assenza della corsa di oggi non coperta da ieri, completamento entro/oltre il
margine, avvio ritardato, esito parziale, nessun destinatario, deduplicazione,
origine manuale e lettura meteo iniziata mentre cambia latest. Nessuna variazione
a soglie meteo, criteri di destinatari o politica di validità dei dati viene
implicata da questa proposta. Non serve una AAB per questa integrazione backend.
L’eventuale implementazione sarà un workstream dedicato, con autorizzazione
separata per distribuzione e modifiche al monitoraggio.

## Salvataggio, limiti e controllo Eventi

Evidenze private: `.tmp/icon-summary-dst-coupling-20261025` nella radice canonica;
riusate quelle già salvate in `.tmp/summary-dst-audit-20261025`.
Letture producer limitate a nove esecuzioni ciascuno dal 21 al 25 ottobre;
log di pubblicazione dettagliati per le ultime tre corse; tre finestre HTTP
mattino 24/25 e sera 24. Nessun censimento retrospettivo esteso.

Il follow-up `verifica-eventi-pordenone-pensa-e-barcolana` resta ACTIVE, con
corsa bersaglio `2026-10-26T04:00:00Z` (05:00 Europe/Rome), distinta dalla
prova manuale Eventi di oggi. Sponsor disattivati; nessuna AAB, installazione,
notifica, job manuale, push o nuovo deploy in questa verifica.
