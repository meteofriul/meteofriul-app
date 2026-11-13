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
della lista esplicita di date sulle pagine **Discover Trieste** con metadati
di titolo e URL coincidenti, calendario unico e anno scritto. Le pagine reali
di Cavana, Ponterosso, Mercatino al tram e Un pozzo di occasioni sono state
provate con il loro HTML: il parser ha ricavato solo le date future scritte.
Aggiunta la lettura degli orari espliciti nelle pagine Campagna Amica con
identità e comune verificati; provate le pagine reali di Codroipo, Passons e
Udine. Questi orari sono solo proposte, non mutazioni o nuove edizioni.

PDF e immagini fino a 8 MiB sono letti per calcolarne l'impronta e segnalare
modifiche successive, senza estrarne date o testi. Per l'HTML, il confronto
fra esecuzioni usa l'impronta del testo visibile, ignorando script e stile.
Il limite di 8 MiB permette anche di leggere alcune pagine comunali ufficiali
di Pordenone che misurano circa 5,5 MiB. L'avviso "fonte cambiata" è emesso
solo per fonti interpretate o documenti con impronta confrontabile: una pagina
HTML non interpretata può variare nella navigazione e non costituisce da sola
una modifica verificata del mercato. Rimane in "Fonti da verificare".
Il metodo dell'impronta è versionato: il secondo collaudo non segnalerà come
"pagina cambiata" tutte le fonti della prima esecuzione soltanto perché è
cambiato l'algoritmo. Intervalli di date, elenchi con luoghi diversi e
calendari senza anno non generano date. Ogni fonte tentata indica se è stata
letta, se resta da interpretare o se non è raggiungibile; oltre quattro fonti
per scheda, quelle non tentate sono elencate. I codici tecnici vengono
tradotti in messaggi leggibili nel pannello. La copertura resta parziale.

## Collaudo e attivazione

Il test con un archivio locale **copiato** ha elaborato 100/100 schede:
16 selezionate, 47 bozze, 37 sospese. Il file copiato è rimasto identico.
I test automatici coprono anche lo stato archiviato, un cambio di fonte senza
fatto certo, una scansione parziale e un errore del collector senza fuga del
testo dell'eccezione. Questo collaudo usa fonti simulate: non dimostra ancora
che tutte le fonti online siano raggiungibili o interpretabili.

La **prima esecuzione online**, con digest
`sha256:abca21a4a8dc3729561224a673d1115ad34732ab776980483166499d02bfde49`,
è terminata il 13 novembre in 3m21s: 100/100 schede, revisione privata 57
invariata e revisione pubblica 0. Il pannello ha mostrato due differenze di
sede/indicazioni per Lo Scrigno del Doge, con fonte e prima/dopo. 99 schede
avevano almeno un limite di lettura: 82 `source_format_not_supported`, 37
`unsupported_source_format`, 7 HTTP 404, oltre a pochi altri casi. Per questo
il parser Discover è stato corretto sui metadati reali, sono stati aggiunti
Campagna Amica e l'impronta dei documenti, ed è necessario un secondo giro
prima di pianificare. Nessuno Scheduler Mercati esiste a questa data.

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
