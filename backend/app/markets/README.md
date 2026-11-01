# Archivio Mercati

## Servizio cloud dedicato

`app.markets_cloud:create_app` parte per impostazione predefinita in modalità
solo pannello: catalogo pubblico assente (404), pubblicazione bloccata (423
anche per un amministratore autenticato) e CORS limitato al pannello.
L'amministrazione e il salvataggio delle bozze restano disponibili con Firebase.
`MARKETS_PUBLIC_CATALOGUE_ENABLED=true` abilita esplicitamente catalogo e
pubblicazione; non impostarlo senza un'autorizzazione specifica del proprietario
dopo la revisione di interfaccia e dati. Il valore predefinito è `false`.
La liveness indica `publicCatalogueEnabled` senza leggere l'archivio.
Il servizio rifiuta storage SQLite, credenziali locali e progetti Firebase
discordanti all'avvio. Il progetto non inizializza dati durante una richiesta.
`backend/Dockerfile.markets` esegue i test del contratto nel container e usa
un utente non privilegiato. `scripts/prepare-markets-cloud.py --output <nuova-cartella>`
prepara dal commit pulito un contesto esplicito con hash, senza dati locali o
credenziali. Il servizio usa un'identita cloud dedicata, distinta dai servizi
Meteo, Eventi, Sponsor e Community.

L'app puo selezionare questo servizio con `VITE_MARKETS_API_BASE`, URL HTTPS
terminante in `/api`; senza override mantiene la base API esistente. La
distribuzione del servizio non aggiorna automaticamente Web o Android.
Il pannello usa la medesima variabile per il suo collegamento amministrativo.
La preparazione di codice o build non autorizza la distribuzione del pannello,
del servizio o dell'app. Il punto di arresto e le risorse già predisposte sono
registrati nel [verbale del 30 ottobre](../../../docs/operations/MERCATI_ATTIVAZIONE_ONLINE_20261030.md).

L'API generale `app.main` espone un solo catalogo per Mercati ed Eventi.
I raccoglitori Eventi e i servizi Community separati non scrivono questo archivio.

## Configurazione

In locale il provider predefinito e SQLite persistente nel file ignorato
`.dev-logs/markets/archive.sqlite3`. `MARKETS_STORAGE=sqlite` e
`MARKETS_SQLITE_PATH` permettono di selezionare esplicitamente un altro file.
Il file viene creato una sola volta dal seed; riavviarlo non reimporta o sovrascrive
modifiche. Un archivio corrotto o di schema diverso genera errore, senza reset.
Le prove automatizzate usano esclusivamente directory temporanee.

L'autenticazione predefinita e Firebase con claim **`marketsAdmin: true`** e
controllo revoca. I claim Sponsor e Webcam non concedono questo permesso.
Per la sola anteprima locale sono disponibili `MARKETS_ADMIN_AUTH_MODE=local`
e `MARKETS_ADMIN_LOCAL_TOKEN`, distinto da ogni altro token. Non inserire il token
nel repository, nel bundle dell'app o nei log. La modalita locale e SQLite vengono
rifiutati quando `K_SERVICE` identifica Cloud Run.

L'anteprima del 30 ottobre usa app `http://127.0.0.1:5174` e pannello
`http://127.0.0.1:5182`. La credenziale locale e conservata soltanto nel file
ignorato `.dev-logs/markets/admin-local-token.txt`: inserirla nel campo
"Credenziale del servizio locale" del pannello; non copiarla in un file
versionato o in una variabile Vite. Il campo non esiste nella build di produzione.
Per riprendere dopo lo spegnimento del PC, dalla radice canonica:

```powershell
$env:MARKETS_STORAGE = 'sqlite'
$env:MARKETS_ADMIN_AUTH_MODE = 'local'
$env:MARKETS_ADMIN_LOCAL_TOKEN = Get-Content .dev-logs/markets/admin-local-token.txt -Raw
& scripts/start-local-weather-pilot.ps1 -WeatherCloud
```

Se il backend era gia avviato con un'altra configurazione, riavviarlo tramite
lo stesso launcher prima di verificarne l'accesso; non modificare processi
estranei. Il pannello e un progetto separato: avviarlo dal suo checkout con
Node 22.17.1, `npm run dev -- --host 127.0.0.1` (porta 5182).

La produzione richiede esplicitamente:

- `MARKETS_STORAGE=firestore`;
- `MARKETS_FIREBASE_PROJECT_ID` uguale al progetto del client Firebase condiviso;
- eventuale `MARKETS_FIRESTORE_COLLECTION`, altrimenti `markets_archive`;
- autenticazione Firebase e permesso Mercati assegnato all'operatore.

Non dipende da `COMMUNITY_STORAGE` e non degrada su memoria. Un errore del provider
restituisce 503. Il runtime non inizializza un archivio Firestore mancante.

Dopo l'autorizzazione alla configurazione remota, l'operatore puo eseguire una sola
volta `python -m app.markets.bootstrap --confirm-project <progetto-configurato>`
da `backend/`. Il comando confronta il progetto dichiarato con la configurazione,
usa una transazione create-only e rifiuta un archivio gia esistente. Pubblica soltanto
la migrazione delle 53 schede gia visibili; le 59 pratiche restano bozze. Nessuna
esecuzione remota o assegnazione di claim fa parte dei test locali di questo modulo.

## API e revisioni

- `GET /api/markets/catalogue`: snapshot pubblico schema 2, revision, snapshotId
  contenente hash, ETag e 304; nessuna nota interna o pratica di ricerca.
- `GET /api/admin/markets/state`: stato amministrativo completo, revision,
  publishedRevision, publicationErrors, audit e indicazione del provider.
- `PUT /api/admin/markets/state`: `{expectedRevision, operationId, reason, state}`.
  `state` contiene markets, dates, drafts e validita. I metadati di sola lettura
  eventualmente ricevuti dalla GET non diventano valori autorevoli.
- `POST /api/admin/markets/publish`: `{expectedRevision, operationId, reason}`.
- `GET /api/admin/markets/history`: audit con revisioni, autore interno, motivo e
  campi modificati. Il provider conserva anche lo snapshot completo di ogni revisione.

Ogni scrittura richiede revisione intera attesa, operationId da 8 a 120 caratteri e
motivo da 3 a 1000 caratteri. L'ID deve restare uguale nei ritentativi della stessa
richiesta. Un replay restituisce la risposta originale con `idempotentReplay: true`;
richiesta diversa con lo stesso ID o revisione superata produce 409.

SQLite salva stato, revisione immutabile e ricevuta in una transazione
`BEGIN IMMEDIATE`. Firestore usa revisioni immutabili suddivise in blocchi,
puntatore e ricevuta nella stessa transazione; i test del provider usano un fake,
non attestano permessi, IAM o funzionamento di un deployment reale.

Il salvataggio non pubblica. `status=draft` conserva la precedente proiezione
pubblica durante la pubblicazione di altri contenuti; solo suspended/archived
ritirano il mercato. Lo stesso vale per la bozza di un'edizione gia pubblica.
La pubblicazione richiede revisione editoriale, fonte, verifica, validita e,
per i nuovi occasionali, date documentate. Le ricorrenze non generano edizioni.
Il ripristino di un mercato archiviato e una nuova revisione pubblicata.

Date ed edizioni mantengono un ID stabile durante spostamenti. `legacyDates`,
`editionAliases`, `identities` e `tombstones` permettono ai lettori di sopprimere
ritiri e vecchi appuntamenti riproposti dai feed. La sede specifica dell'edizione
prevale su quella abituale. La cancellazione fisica di identita, date e pratiche
gia conservate viene rifiutata; usare gli stati amministrativi.

Ogni mercato ha la propria `validThrough`: la migrazione dei 60 conserva il
31 dicembre 2026. Le nuove bozze richiedono una validita esplicita. L'orizzonte
globale e l'`expiresAt` immutabile seguono la massima validita pubblicata senza
estendere le prove degli altri mercati. Un aggiornamento al 2027 non richiede
modifiche al codice; i lettori devono rispettare anche la validita individuale.

## Ricontrollo automatico delle fonti

`python -m app.markets.refresh_job --apply --report <rapporto.json>` controlla
le fonti dei mercati dovuti e aggiorna direttamente l'archivio amministrativo,
senza conferme interattive. Omettendo `--apply` produce soltanto un'anteprima.
Non inizializza un archivio SQLite mancante e non pubblica il catalogo.
In Cloud Run Job richiede Firestore e progetti Firebase coerenti, senza
credenziali locali; il job non è distribuito implicitamente da questo comando.

Un fatto documentato cambiato sostituisce il vecchio dato anche manuale;
lo stesso fatto già osservato non annulla una correzione manuale successiva.
Valori precedenti, prove e note rimangono nello storico delle revisioni.
Fonti discordanti o non interpretabili producono un'anomalia senza cancellare
dati; assenze nel calendario non cancellano edizioni. Un riscontro parziale
non aggiorna `checked` né l'approvazione editoriale della scheda intera.
`validThrough` può avanzare soltanto fino a una data esplicitamente documentata,
mai per il semplice successo della richiesta HTTP o fino a una fine anno dedotta.

Il comando usa un budget di 30 minuti e registra i mercati rimasti da controllare.
Ritorna 0 per un controllo con fatti verificati o nessun mercato dovuto, 1 per
un errore operativo, 2 quando non è stato possibile verificare alcun fatto.
I rapporti dettagliati restano nel percorso locale richiesto; stdout contiene
soltanto conteggi e codici. Le credenziali del pannello non servono al job locale.

Dalla radice canonica `scripts/refresh-markets-local.ps1` applica il controllo;
`-Preview` lo simula. `scripts/install-markets-local-refresh-task.ps1` mostra
la pianificazione; `-Install` registra il task Windows per le 08:20 e all'accesso,
con processo nascosto, senza password salvate e senza esecuzioni sovrapposte.
Richiede PC acceso e sessione Windows attiva. La frequenza effettiva è mensile,
settimanale per appuntamenti/scadenze entro 30 giorni e giornaliera per i
ritentativi transitori. I raccoglitori Eventi restano distinti.

## Seed e verifiche

`data/seed.json` contiene 60 identita esistenti, 176 date con ID stabile e 59
pratiche distinte: 13 complete e 46 con verifiche residue. Diciannove sono collegate
a ID runtime, 25 sono nuove candidature e 15 hanno precedenti nella ricerca.
Non sono 59 nuovi mercati pubblicati. Ogni pratica conserva fonti risolte,
limiti, suggerimenti e provenienza; il server protegge l'evidenza importata
mentre permette di modificarne stato, collegamenti e note editoriali.

`python -m app.markets.seed` rigenera deterministicamente il pacchetto dai tre
registri canonici e ne registra gli hash. Non modifica un archivio gia inizializzato.
Gli hash delle fonti usano i fine riga LF prescritti dal repository, per
conservare la stessa provenienza nelle build Windows e Linux.
Le giornate ISO 1-7 sono convertite esplicitamente nel campo JS 0-6 del lettore.
Periodicita mensili e stagionali non diventano ricorrenze settimanali.

Verifica locale: `python -m unittest tests.test_markets_archive tests.test_markets_api
tests.test_markets_firestore -v`, piu le regressioni Sponsor/Webcam/Firebase.
L'editor, i permessi remoti, Web/Android e il dispositivo reale richiedono evidenze
proprie: questi test non attestano una pubblicazione o una prova su telefono.
## Promemoria amministrativo locale — 1 novembre 2026

`review.py` calcola le scadenze mensili/trimestrali e la coda compatta persistente.
Le route amministrative `POST /review-complete` e `PUT /email-settings` usano
autenticazione, CAS e idempotenza. Le preferenze sono server-owned e separate
dalle schede. `email_reminder.py` gestisce invio SMTP con prenotazione durevole,
retry giornalieri solo per errori certi e nessun reinvio per esiti incerti.
Mittente/credenziali non sono esposti nelle API. Il collegamento della casella
e la registrazione del task email sono ancora da eseguire: non basta salvare
il destinatario nel pannello. [Stato operativo e istruzioni](../../../docs/operations/MERCATI_PROMEMORIA_20261101.md).
