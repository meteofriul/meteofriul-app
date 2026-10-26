# Barcolana: lettura lenta e significato degli allarmi — 26 ottobre 2026

**Aggiornamento successivo:** i due commit sono in main tramite PR 30; deploy del job e aggiornamento della sola policy completati. [Distribuzione, rollback e controllo ordinario](EVENTS_BARCOLANA_RECOVERY_DEPLOY_20261026.md). Le sezioni seguenti conservano l'evidenza della fase locale precedente.

## Stato e perimetro

Correzioni **locali, non distribuite**, sul ramo `codex/events-barcolana-recovery`,
base main `a41353921bd10c94b7763f8f1b5588da72e810d7`.
La prima riguarda solo il lettore Barcolana; la seconda riguarda la diagnostica
di recupero dei lotti Eventi e la sola policy `events-failures`.
Nessun nuovo job o controllo di altri servizi aggiunto al job Eventi.

Il pannello per correggere gli errori degli eventi è sviluppato dal proprietario
in un'altra chat: non modificato qui. Nessuna variazione a schema del catalogo,
API, gate editoriali, schede in revisione, orari o account. Sponsor disattivati.
Non servono nuove AAB per queste correzioni backend. Nessun push, deploy,
esecuzione manuale, acquisizione reale o notifica manuale eseguita.

## Evidenza da cui parte la correzione

Riusata la verifica della corsa ordinaria `2026-10-26T04:00:00Z` (05:00 locali),
esecuzione `meteofriul-events-refresh-mnx6g`, terminata alle 04:07:51 UTC.
Scheduler e digest atteso verificati; esito fallito. L'immagine distribuita
resta `sha256:074d93066cc35fa77bf193f95b8dba1163f5bb11e487dd12c12224b29ef26a26`.

- Barcolana: errore `ReadTimeout` nella pagina calendario, timeout lettura 8 s;
  lotto `stale`, ultimo aggiornamento 25 ottobre 07:59:50 UTC, escluso dalle API.
- Altre 14 fonti aggiornate dalla corsa: 9 fresche e 5 parziali esplicite.
- Cinque incontri ABC Pordenone Pensa presenti con dettagli; Scienza in revisione.
- Premiazioni Barcolana del 29 novembre assenti dalle API; catalogo `degraded`.
- Le email fornite mostrano lo stesso incidente aperto alle 04:12 UTC e chiuso
  circa due ore dopo. La policy conta fallimenti negli ultimi 7200 secondi:
  la chiusura non prova una nuova acquisizione riuscita.

Evidenza privata originale: `.tmp/events-pnpensa-barcolana-deploy-20261025/ordinary-verification.json`
nella radice canonica; SHA-256
`4ec65d8000659d295d84cbbed85875987a70adc2b3a1197919e573a1afd4c37d`.
L'esito ordinario richiede intervento; il follow-up del 26 ottobre è stato
eliminato su richiesta del proprietario. Non è in attesa di altri controlli.

## 1. Lettura Barcolana

Prima entrambi i tentativi avevano timeout di lettura di 8 secondi. Ora il primo
resta a 8 s e il secondo può usare fino a 16 s, ridotti al tempo residuo dopo
la quota di connessione. Rimangono due tentativi massimi, pausa 0,5 s per soli
errori transitori, connessione fino a 3 s e deadline condivisa di 28 s. Nessun
reset del tempo al retry. Pool di quattro letture e guardia del processo a 35 s
invariati; somma dei budget delle 15 fonti ancora 860 s.

Un HTTP 404, documento sovradimensionato, troncato, identità errata o dati
discordanti non diventano un successo e non ricevono nuovi tentativi di parsing.
Il fallimento di una pagina obbligatoria rifiuta la fonte, senza pubblicarne un
sottoinsieme arbitrario. Le altre fonti continuano la raccolta.

Il timeout Requests misura l'inattività della connessione, non la durata totale
del download: rimangono quindi indispensabili deadline e guardia del processo.
[Documentazione Requests](https://requests.readthedocs.io/en/latest/user/quickstart/#timeouts).

Il log `event_source_read`, solo sui retry o errori, espone fase, tentativi,
tempo trascorso/residuo ed esito del trasporto, senza URL o corpo della pagina.
`status=read` non dichiara validazione o pubblicazione: i gate restano successivi.

## 2. Fine finestra dei fallimenti e recupero dei dati

La policy `events-failures` conserva soglia, finestra, canale e notifica di errore.
Nome della condizione e documentazione esplicitano «nelle ultime 2 ore».
`notifyOnRecovery=false` richiede soltanto `OPENED`: evita l'email `CLOSED` che
sembra certificare un recupero quando il fallimento è solo uscito dalla finestra.
La console potrà comunque mostrare l'incidente chiuso: è la condizione temporale,
non lo stato del catalogo. Non viene creato un nuovo allarme positivo.
[Contratto Google della strategia di notifica](https://docs.cloud.google.com/python/docs/reference/monitoring/latest/google.cloud.monitoring_v3.types.AlertPolicy.AlertStrategy).

Il generatore PowerShell ora conserva un array JSON anche con il solo `OPENED`;
il controllo locale ha rilevato e corretto la precedente serializzazione scalare.
Le altre policy restano invariate.

Il log separato `event_source_recovered` viene emesso **dopo** il salvataggio
condizionale riuscito e soltanto per una fonte selezionata, precedentemente
`stale`/`unavailable`, ora `fresh`/`partial`, con data nuova coerente con la corsa.
Un lotto vecchio, la sola scadenza del contatore, timestamp non validi o un errore
Storage non generano recupero. Sono espliciti schede pubblicate, revisioni,
parzialità e altre fonti ancora indisponibili o scadute. Un vuoto validato fuori
stagione può essere un recupero valido. Un refresh già sano non ripete il log.

Il segnale riguarda il lotto persistito, non il successo globale del job né la
visibilità su un telefono. `api_verified=false` richiede un riscontro separato
nelle API; nessun invio email/FCM viene effettuato da questo codice.

## Verifiche locali

**159 test Python distinti superati**, senza rete, con fake/mocks e processi locali:

- Barcolana, pubblicazione cloud simulata e client HTTP: 64 test (inclusa
  risposta da 10 s che falliva con il vecchio timeout di 8 s e ora riesce).
- Raccolta isolata, catalogo, health, gate, API e quarantena: 95 test.
- Coperti timeout persistente, budget esaurito, pagina in coda, risposta tardiva,
  mancata lettura obbligatoria, seconda fonte dopo timeout, errore Storage,
  recupero parziale, lotto vuoto validato e mancata ripetizione su fonte già sana.
- Contratti PowerShell produzione: PASS, inclusi builder reale estratto senza
  eseguirne l'entrypoint cloud, array `OPENED`, soglia invariata e rilevamento del
  ritorno accidentale di `CLOSED` nell'audit.

[Riepilogo verificabile](evidence/events-barcolana-recovery-20261026/verification.json).
Le verifiche non dimostrano quanto impiegherà il sito reale domani. Nessun recupero
cloud dichiarato in questo intervento; la nuova immagine non è stata costruita.

## Passaggio successivo e compatibilità

Revisione e salvataggio in commit separati per lettura e allarmi, poi PR/CI e,
solo nel passaggio autorizzato, aggiornamento del solo job Eventi e applicazione
mirata della policy `events-failures`. Prima distribuire la diagnostica che la
documentazione della policy cita. Mantenere il digest precedente come rollback:
legge lo stesso catalogo, ma riporta il limite di lettura a 8 s anche sul retry.

La verifica successiva deve associare esecuzione ordinaria, digest e catalogo;
controllare la nuova data di Barcolana, `event_source_recovered`, eventuali altre
fonti degradate e le premiazioni del 29 novembre nelle API Trieste. Un job verde
o una email chiusa non bastano. Non ripristinare copie vecchie a mano e non
confondere questo lavoro con le future operazioni editoriali del pannello.
