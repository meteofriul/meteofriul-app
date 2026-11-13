# Controllo settimanale Mercati — attivazione del 13 novembre 2026

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
URL ed estratto. Una pagina non interpretabile rimane fra le fonti da verificare;
la sua sola impronta non è presentata come cambiamento certo. Nessuna proposta convalida una scheda, modifica
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
Il metodo dell'impronta è versionato: il cambio dell'algoritmo non genera un
avviso di contenuto cambiato. Intervalli di date, elenchi con luoghi diversi e
calendari senza anno non generano date. Ogni fonte tentata indica se è stata
letta, se resta da interpretare o se non è raggiungibile; oltre quattro fonti
per scheda, quelle non tentate sono elencate. I codici tecnici vengono
tradotti in messaggi leggibili nel pannello. La copertura resta parziale.

## Collaudo online

I test con archivio locale **copiato** hanno elaborato 100/100 schede senza
modificare il file: 16 selezionate, 47 bozze, 37 sospese nello snapshot locale.
Il test automatico copre anche lo stato archiviato. Le esecuzioni online hanno
letto lo stato corrente: 80 schede `published`, 11 `draft`, 9 `suspended`,
nessuna `archived`. Le revisioni prima/dopo sono rimaste 57; la revisione
pubblica è 0 e `MARKETS_PUBLIC_CATALOGUE_ENABLED=false`.

La prima esecuzione online `meteofriul-markets-weekly-audit-nkccx` ha letto
100/100 schede ma mostrato i limiti iniziali. Il secondo giro `m97dz` ha
provato i nuovi parser e individuato tre differenze puramente tipografiche
negli orari. Il terzo `z5x76` ha ridotto le differenze a due schede, ma ha
mostrato 11 falsi avvisi di pagina cambiata su HTML non interpretato. Dopo la
correzione, l'esecuzione `746vt` è terminata con successo il 13 novembre alle
10:40 UTC in 3m44s: **100/100 schede**, revisione 57 invariata, **2 schede
con differenze** e **0 falsi avvisi di fonte cambiata** rispetto al giro
precedente. Restano la sede e le indicazioni di Lo Scrigno del Doge e l'inizio
alle 07:30 anziché 08:00 per Campagna Amica in piazza Vittorio Veneto a
Trieste. Nessuna differenza è stata applicata.

Nel rapporto finale 42 fonti sono documenti con impronta, 16 sono lette con
parser, 104 pagine rimangono da interpretare, 15 fonti non sono raggiungibili
e 2 sono oltre il limite di quattro fonti per scheda. 92 schede hanno almeno
un limite di fonte, fra cui 7 URL HTTP 404 e 5 pagine ancora oltre 8 MiB.
Il pannello online mostra il rapporto autenticato, filtri e confronto con
fonte ed estratto; la prova interattiva ha aperto il dettaglio di Lo Scrigno
del Doge. In quel collaudo la versione del pannello era Hosting
`904698932f3c3e55`.
127 test backend mirati, i test della build Cloud, 215 test del pannello, lint
e build del pannello sono passati. Node locale del pannello era v24/npm11,
diverso dalla versione prescritta v22/npm10.

## Verifica manuale delle fonti — aggiornamento del 13 novembre

Nel pannello online, il login amministrativo consente di annotare per ogni
coppia scheda/fonte uno di tre esiti: **verificata**, **correzione da fare** o
**fonte da sostituire**. Una nota di almeno cinque caratteri è obbligatoria;
la data è registrata dal server. Il pannello mostra l'esito e la nota accanto
alla fonte, con filtri per fonti da esaminare e verificate. L'operatore apre
la scheda nell'editor per correggere i dati, se necessario.

Le annotazioni stanno in `markets_weekly_audit/manual_reviews/items`, fuori
dall'archivio Mercati. Non cambiano schede, revisione privata o pubblica,
stato editoriale, job o pubblicazione. Un esito «verificata» nasconde il
relativo limite di lettura dall'elenco da esaminare per non più di 90 giorni;
una nuova impronta di una fonte leggibile, un cambio di stato della fonte o
una differenza di contenuto la rimette in evidenza. I problemi a livello di
scheda restano visibili. Il server accetta solo fonti nel rapporto più recente
e rifiuta una verifica se nel frattempo è arrivato un altro rapporto.

L'API amministrativa autenticata espone `GET
/api/admin/markets/weekly-audit/reviews` e `PUT
/api/admin/markets/weekly-audit/{market_id}/review`. La lettura usa riferimenti
puntuali alle fonti presenti nel rapporto, perché il ruolo di runtime dispone
di `datastore.entities.get` ma non di `datastore.entities.list`; non sono
stati ampliati i permessi IAM. Il primo tentativo di lettura online ha
restituito 503; la correzione è stata ridistribuita e il pannello ha caricato
il rapporto con 100 schede, 2 con differenze e 92 da esaminare. Il modulo è
stato aperto e annullato nel browser autenticato senza registrare un esito
editoriale reale. 128 test backend mirati, 219 test del pannello, lint e build
del pannello e Cloud Build sono passati. Il salvataggio di una verifica reale
in produzione resta da esercitare quando l'operatore ne avrà verificata una.
Il pannello aggiornato è online su `https://meteofriul-inserzioni.web.app/`:
dopo il nuovo caricamento, il rapporto autenticato mostra ancora 100 schede,
2 con differenze e 92 da esaminare.

## Configurazione attiva

- API Cloud Run `meteofriul-markets`, revisione `meteofriul-markets-00007-ljn`,
  al digest `sha256:15a73c0b27b508f0fa03b93d9c8dc6fdb96ee213d401a2b227981fbc9e87989b`
  del commit `2ed17514`.
- Cloud Run Job `meteofriul-markets-weekly-audit` al digest
  `sha256:3e53f437032472391928087ee7f5594d0284500b2ce3d1ef2b7319d4defb01f0`
  del commit `553a6fdb`.
- Il job gira in `europe-west1` come
  `meteofriul-markets@meteo-friul.iam.gserviceaccount.com` con comando
  `python -m app.markets.weekly_audit_job` e Firestore `meteo-friul`.
- Scheduler `meteofriul-markets-weekly-audit` **ENABLED**, cron `0 9 * * 2`,
  fuso `Europe/Rome`: martedì alle 09:00; primo avvio pianificato il
  **17 novembre 2026 alle 09:00**. Nessun retry automatico aggiuntivo.
  Usa OAuth dell'identità dedicata
  `meteofriul-markets-scheduler@meteo-friul.iam.gserviceaccount.com`, con
  `roles/run.invoker` limitato a questo job. La chiamata Scheduler di prova
  del 13 novembre alle 10:42 UTC ha creato l'esecuzione `jv5hj`, terminata
  con successo alle 10:46 UTC in 3m34s. Il rapporto `d1072da97085434bab0c3e7b61159475`
  ha ancora 100/100 schede, revisione 57/57, 2 schede con differenze e zero
  avvisi di fonte cambiata. Il primo avvio automatico del martedì resta da
  osservare.
- Il task Windows locale rimane disabilitato. Il controllo editoriale generale
  del 7 febbraio 2027 e poi circa trimestrale rimane una decisione separata.

Non riutilizzare `refresh_job --apply`: quello salva automaticamente modifiche
nell'archivio e contraddice la decisione editoriale di questo flusso.

## Verifica mirata di sede, date e orario — 13 novembre 2026

- **Lo Scrigno del Doge, M053.** La [fonte UNPLI FVG](https://prolocoregionefvg.it/eventi-delle-associate/lo-scrigno-del-doge-in-villa-manin-mercatino-dellantiquariato-e-modernariato/) indica Arcate dell'Esedra e Piazza Tonda di Villa Manin, Passariano, Codroipo. Il pannello online contiene lo stesso luogo, con punteggiatura diversa; le indicazioni puntano al complesso Villa Manin. Le edizioni future **8 dicembre 2026** e **6 gennaio 2027** sono confermate nel pannello con il luogo preciso, e le date coincidono con [UNPLI](https://prolocoregionefvg.it/eventi-delle-associate/lo-scrigno-del-doge-in-villa-manin-mercatino-dellantiquariato-e-modernariato/) e [PromoTurismoFVG](https://www.turismofvg.it/eventi/lo-scrigno-del-doge-in-villa-manin-mercatino-dell-antiquariato-e-modernariato). Non serve correggere la scheda.
- **Campagna Amica, M021.** La [guida Discover Trieste](https://www.discover-trieste.it/vivi/shopping/andar-per-mercatini) e l'[organizzatore](https://www.campagnamica.it/la-nostra-rete/mercato/il-mercato-di-campagna-amica-a-trieste/) confermano il **martedì** in **piazza Vittorio Veneto, Trieste**. Il pannello online ha ricorrenza settimanale martedì, destinazione nella stessa piazza e nota pubblica che dichiara apertura indicativa tra 07:30 e 08:00. La guida scrive 08:00; nella stessa pagina dell'organizzatore il testo scrive 08:00 e il riquadro orari 07:30. Questo scarto non cambia giorno né luogo e non richiede modifica della scheda.
- La [pagina calendario 2026 di Discover Trieste](https://www.discover-trieste.it/vivi/trieste-now/campagna-amica-trieste) menziona anche appuntamenti del **sabato** in piazza Vittorio Veneto, collegati allo spostamento da piazza Goldoni, e altri sabati in Campo San Giacomo. È un calendario distinto dalla ricorrenza del martedì di M021; l'eventuale scheda separata dei sabati richiede un controllo editoriale del calendario e della sede prima di aggiungerla.

Il confronto del job, commit `553a6fdb`, ora riconosce lo stesso luogo con CAP,
comune e punteggiatura aggiuntivi, una destinazione stradale al medesimo
complesso quando il luogo preciso concorda, e la variazione di apertura di
massimo 30 minuti **solo se già dichiarata come intervallo nella nota
pubblica**. Giorno diverso, nuovo luogo e date diverse restano differenze.
137 test Mercati e `compileall` sono passati. Cloud Build
`020c7e65-526b-486d-a647-d2a181ec9119` è **SUCCESS**; soltanto il Cloud Run
Job usa il nuovo digest
`sha256:3e53f437032472391928087ee7f5594d0284500b2ce3d1ef2b7319d4defb01f0`.
L'API resta alla revisione `meteofriul-markets-00007-ljn` e al digest
`sha256:15a73c0b27b508f0fa03b93d9c8dc6fdb96ee213d401a2b227981fbc9e87989b`,
con catalogo pubblico disattivato. Lo Scheduler è ancora **ENABLED** martedì
09:00 `Europe/Rome`.

La revisione automatica dell'azione ha respinto l'avvio manuale del job di
produzione durante questo audit, citando la regola del workspace che vieta
esecuzioni e retry di job durante un audit. Non è stato ritentato. Il rapporto
online resta quello precedente (100 schede, 2 con differenze); l'effetto del
nuovo confronto sui dati reali **non è ancora osservato** e sarà verificabile
dopo la prima esecuzione pianificata del 17 novembre.
