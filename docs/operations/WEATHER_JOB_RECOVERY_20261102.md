# CAMS e avvisi ICON — correzione del 2 novembre 2026

Distribuzione completata il 2 novembre, riscontro finale alle 21:53 CET.
Workstream `codex/weather-job-recovery-20261102`, base main `92230e1d`.
Il proprietario ha autorizzato la correzione dopo la diagnosi odierna.
Eventi escluso. Nuova immagine CAMS e due policy ICON verificate nel cloud;
la prima corsa ordinaria della nuova immagine resta da osservare.

## Problema e cambiamento

Al primo avvio CAMS, l'assenza prevista dei checkpoint `submitted` e `intent`
veniva gestita chiamando l'acquisizione dentro `except ObjectNotFound`.
Una successiva attesa ADS scaduta ereditava il contesto del precedente 404 e
`retryable=false`: il worker la classificava come `manual_review` invece di
`remote_pending`, interrompendo il recupero interno.

La correzione esce dai gestori di assenza prima di chiamare acquisizione o
riconciliazione. Conserva la richiesta già registrata e la riprende senza
un secondo POST. Non cambia budget, pianificazioni, verifiche TLS, controlli
d'integrità, pubblicazione o limiti di validità. Nessuna dipendenza runtime
aggiornata. Una sentinella privata distingue l'assenza prevista da un valore
inatteso dello store.

Per i soli due allarmi `icon-fvg-failures` e `icon-national-failures`, il conteggio
passa a una query PromQL sulla stessa metrica DELTA: somma mobile in due ore,
con zero quando non vi sono punti e soglia di almeno un fallimento. La query
filtra il progetto, la regione e il job esatti. Nessun `bool` nel confronto:
una serie di valore zero non deve attivare l'allarme.

Le policy hanno severità WARNING e sola notifica OPENED. La fine della finestra
di errori non viene annunciata come recupero dei dati. I monitor esistenti di
freschezza ICON e assenza di successi restano invariati e distinti. Nessun nuovo
monitor CAMS, scheduler, destinatario o job è introdotto.

## Prove della diagnosi

Il 2 novembre i produttori ICON hanno recuperato con gli slot ordinari delle
11 e 19: il recupero distribuito il 31 ottobre è quindi esercitato su una
sorgente inizialmente non avanzata. Le vecchie policy errori restavano aperte
perché la serie `failed` non emetteva più punti dopo le 09, mentre le riuscite
apparivano in una serie separata.

CAMS: errori di metadati catalogo alle 10/11, attesa ADS scaduta alle 12 con
`retryable=false`; nuova famiglia atomica alle 16:05:26 CET e verifica completa
alle 16:06. Il grant precedente terminava alle 13:00: intervallo di 3h05m26s
fra scadenza e nuova pubblicazione. Il campo dichiarato `published_at` precedeva
il commit effettivo e non è stato usato per calcolare l'intervallo.

Il difetto è riprodotto offline con gli helper reali. La catena completa della
specifica eccezione di produzione non è conservata: l'attribuzione alla corsa
odierna è coerente con i campi osservati, non una trace integrale.

## Verifiche del candidato

- 76 test Python PASS: acquisizione remota, retriever e recupero worker.
  Python 3.13.5, client ADS 0.5.3, confini esterni simulati. Due regressioni
  falliscono sul sorgente precedente caricato in memoria e passano col fix.
  Provati attesa/ripresa dello stesso ID senza reinvio, riconciliazione,
  certificato TLS invalido e checkpoint con integrità errata.
- Contratti PowerShell delle operazioni job PASS: query con scope, finestra e
  soglia esatti; rilevamento di `bool`, fallback fuori confronto, metrica,
  regione, finestra, severità o notifiche divergenti.
- Quattro query storiche reali, HTTP 200. 642 campioni PromQL confrontati con
  i DELTA REST: zero discrepanze. Conteggio torna a zero alle 11:05 FVG e
  11:04 nazionale; la condizione non restituisce più serie dopo quegli istanti.
  Questa prova non è un test di ricezione delle email.
- Le tre suite CAMS sono aggiunte al job backend CI esistente, con installazione
  del client di test fissato a 0.5.3. Nessun nuovo job o trigger GitHub.

La [documentazione Google sulle policy PromQL](https://docs.cloud.google.com/monitoring/alerts/using-promql)
resta il riferimento per i tempi di valutazione/chiusura. La chiusura del
conteggio errori non certifica sorgente, freschezza o salute della telemetria.

## Distribuzione e verifica ordinaria

Sorgente integrato tramite [PR 40](https://github.com/meteofriul/meteofriul-app/pull/40),
commit della correzione `d3ca483f4b5711277558ebadc742074e0d2ce05c`, merge main
`f20cc976227161bbaea1e3c64af8607008dd5b07`.
[CI PR](https://github.com/meteofriul/meteofriul-app/actions/runs/41519399611) e
[CI main](https://github.com/meteofriul/meteofriul-app/actions/runs/41520225858)
PASS nei tre job, senza dispatch duplicati.

Immagine composita: base immutabile CAMS dal sorgente
`026d5ca064fdbeebb30403b458929cd6ea1e79c0`, più il solo
`retrieve_remote_cams.py` estratto dal merge main verificato. Non è una
ricostruzione di tutto main: etichetta della base preservata, revisione della
patch registrata separatamente. Nessuna installazione di dipendenze.

| Prova | Risultato |
| --- | --- |
| Cloud Build | `7aa0fd58-0f5f-429d-92d7-e0190a9e1622`, quattro step SUCCESS |
| Digest CAMS attivo | `sha256:83a67540e4131a0f3a90e1a9cc5674d5a0621dae6a225686613c0ff03762dbd7` |
| Digest precedente e rollback | `sha256:572ea2889b37009b746e746402816a2fd1e6966db15c8d642e5105ccd5b0ce8e` |
| File runtime corretto | SHA-256 `61d37d633e04c3c157cf6b571cd8ac054f241836d24bb2e10d5df842754e063e` |
| Integrità Linux | Un solo file diverso su 212; permessi, pacchetti e configurazione preservati; Python 3.13.17, UID 65532 |
| Suite Linux | 437 test PASS, zero errori, fallimenti o esclusioni; rete disabilitata; nuovi test di regressione montati esternamente, senza aggiunte all'immagine runtime |
| Deploy CAMS | Aggiornamento cloud alle 21:51:09 CET; solo immagine modificata, zero corse attive prima dell'aggiornamento |
| Confronto cloud | Scheduler invariato; altri 12 job e 6 servizi invariati |

Le due policy ICON sono state applicate con PATCH sui rispettivi ID esistenti,
sostituendo le condition ID del vecchio tipo threshold. Readback delle 21:45:21
CET PASS tramite le stesse funzioni di confronto del repository: query uguali
al probe, WARNING, OPENED, valutazione ogni 60 secondi, soglia e canali
preservati. Totale 23 policy; le altre 21 invariate. Backup e rollback salvati.
Il campo `autoClose` è conservato ma ignorato per le condizioni PromQL; non
viene usato come prova della loro tempistica di chiusura. L'API non offre un
CAS atomico: eseguito confronto immediato prima di ciascuna PATCH e dopo.

Al readback delle 21:53 CET tutti i cinque incidenti meteo odierni già noti
risultano CLOSED: CAMS dalle 19:10:06, freschezza nazionale dalle 11:16:40,
freschezza FVG dalle 11:17:09; i due errori ICON dalle 21:46:02. Questi ultimi
si sono chiusi dopo la migrazione delle condizioni, senza chiusura manuale e
senza nuova pubblicazione: non sono una prova di recupero prodotto dal deploy.
Nessun nuovo incidente rilevante nella pagina letta; la paginazione storica
è troncata, ma tutti i cinque incidenti già osservati sono presenti.

Le corse delle 21:00, anteriori al deploy, erano riuscite verificando dati già
pubblicati: ICON FVG/nazionale `publication_already_verified` sul ciclo 12Z;
CAMS aria/pollini `existing_family_verified`, UV `uv_already_published`.
Il puntatore CAMS rimane aggiornato alle 16:05:26.810 CET, ciclo 00Z/revisione
51. Il controllo freschezza ICON delle 21:40 è regolare per entrambi.
La lettura HTTP dopo il deploy conferma i puntatori invariati.

Nessuna esecuzione manuale, modifica a dati/checkpoint, destinatari o
pianificazioni. Il confronto dopo il deploy conferma la nuova immagine nel
job CAMS; l'ultima esecuzione resta quella precedente delle 21:00.

Il recupero della nuova immagine dovrà essere osservato in una corsa ordinaria
successiva, la prima prevista il 3 novembre alle 10:00 CET, distinguendo
successo tecnico, pubblicazione e lettura HTTP.
Un successo senza attesa ADS non prova il ramo di ripresa in produzione.
Nessun controllo periodico aggiuntivo è registrato da questo lavoro.

Frontend, API pubbliche, build e artefatti Web/Android restano invariati;
nessuna installazione o nuova qualificazione su dispositivo o Safari/iPhone.
Evidenze locali sanificate in `.tmp/weather-job-diagnosis-20261102/` e
`.tmp/weather-job-recovery-deploy-20261102/`; configurazioni complete private
restano escluse dai commit.
