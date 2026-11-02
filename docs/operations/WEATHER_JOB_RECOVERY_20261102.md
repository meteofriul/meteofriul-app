# CAMS e avvisi ICON — correzione del 2 novembre 2026

Preparazione su `codex/weather-job-recovery-20261102`, base main `92230e1d`.
Il proprietario ha autorizzato la correzione dopo la diagnosi odierna.
Eventi escluso. Questo stato precede promozione e distribuzione: non attesta
ancora una nuova immagine attiva o policy modificate nel cloud.

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

Piano: PR e CI, promozione protetta, CI main, immagine derivata dal digest CAMS
attuale con il solo file runtime corretto. Confrontare pacchetti, inventario
dei file e configurazione; eseguire la suite Linux senza rete. Conservare
digest precedente e rollback, verificare assenza di corse attive, aggiornare
solo l'immagine CAMS. Applicare e rileggere soltanto le due policy ICON,
confrontando le altre policy prima/dopo. Nessuna esecuzione manuale.

Il recupero della nuova immagine dovrà essere osservato in una corsa ordinaria
successiva, distinguendo successo tecnico, pubblicazione e lettura HTTP.
Un successo senza attesa ADS non prova il ramo di ripresa in produzione.
Nessun controllo periodico aggiuntivo è registrato da questo lavoro.

Frontend, API pubbliche, build e artefatti Web/Android restano invariati;
nessuna installazione o nuova qualificazione su dispositivo o Safari/iPhone.
Evidenze locali sanificate in `.tmp/weather-job-diagnosis-20261102/` e
`.tmp/weather-job-recovery-deploy-20261102/`; configurazioni complete private
restano escluse dai commit.
