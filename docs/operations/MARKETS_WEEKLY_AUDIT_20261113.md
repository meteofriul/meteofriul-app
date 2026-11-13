# Controllo settimanale Mercati — preparazione del 13 novembre 2026

## Scopo e confini

Il nuovo comando `python -m app.markets.weekly_audit_job` legge l'archivio
Firestore online. Controlla **tutte** le schede, incluse bozze, sospese e
archiviate, e confronta i fatti espliciti nelle fonti con la revisione letta.
Non chiama `MarketsService.refresh`, `mutate` o `publish`. Scrive solo il
rapporto nella raccolta Firestore separata `markets_weekly_audit`, visibile
all'operatore autorizzato dal pannello in **Controllo fonti**. Il puntatore
`latest` viene aggiornato soltanto dopo aver salvato tutti i dettagli. Un
controllo parziale o con revisione dell'archivio cambiata durante la lettura
non sostituisce il rapporto precedente. La revisione dell'archivio è mostrata
per segnalare anche modifiche successive al controllo.

Le differenze sono **proposte** con valore in scheda, valore nella fonte,
URL ed estratto. Anche una pagina cambiata senza dato interpretabile viene
segnalata separatamente. Nessuna proposta convalida una scheda, modifica
una data o pubblica nell'app. Il controllo editoriale generale ogni tre mesi
rimane distinto e disponibile nel pannello.

## Fonti e limiti attuali

Restano i parser prudenti per JSON-LD Event con identità e data singola,
calendario Pro Sacile e dettagli etichettati Pro Loco FVG. Aggiunta la lettura
della lista esplicita di date su una pagina **Discover Trieste** con titolo
identico alla scheda, calendario unico e anno scritto. Intervalli di date,
elenchi con luoghi diversi, calendari senza anno e PDF non generano date.
Ogni fonte tentata indica se è stata letta, se il formato non è interpretabile
o se non è raggiungibile; oltre quattro fonti per scheda, quelle non tentate
sono elencate. I codici tecnici non sono mostrati come tali nel pannello.
Questa estensione non equivale a copertura completa dei siti censiti.

## Collaudo e attivazione

Il test con un archivio locale **copiato** ha elaborato 100/100 schede:
16 selezionate, 47 bozze, 37 sospese. Il file copiato è rimasto identico.
I test automatici coprono anche lo stato archiviato, un cambio di fonte senza
fatto certo, una scansione parziale e un errore del collector senza fuga del
testo dell'eccezione. Questo collaudo usa fonti simulate: non dimostra ancora
che tutte le fonti online siano raggiungibili o interpretabili.

Prima di creare la cadenza settimanale:

1. Distribuire API e pannello con le rotte del rapporto, senza abilitare la
   pubblicazione Mercati.
2. Creare il Cloud Run Job con lo stesso digest collaudato dell'API, account
   `meteofriul-markets@meteo-friul.iam.gserviceaccount.com`, progetto
   `meteo-friul`, regione `europe-west1`, comando
   `python -m app.markets.weekly_audit_job`, variabili
   `MARKETS_STORAGE=firestore`, `FIREBASE_PROJECT_ID=meteo-friul` e
   `MARKETS_FIREBASE_PROJECT_ID=meteo-friul`; **senza Scheduler**.
3. Avviare manualmente una sola esecuzione di collaudo, verificare 100/100
   schede e la revisione invariata, esaminare nel pannello differenze e
   problemi per stato e fonte, ampliare i parser necessari senza inferenze.
4. Solo dopo l'esito positivo creare lo Scheduler settimanale in
   `Europe/Rome`, con un'identità dedicata autorizzata a invocare **solo**
   questo job. Registrare nome, cron, identità, digest, prima esecuzione ed
   esito. Il task Windows locale rimane disabilitato.

Non riutilizzare `refresh_job --apply`: quello salva automaticamente modifiche
nell'archivio e contraddice la decisione editoriale di questo flusso.
