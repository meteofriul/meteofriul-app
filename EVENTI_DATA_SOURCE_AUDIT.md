# Audit sorgenti Eventi

Data: 2026-07-01

## Aggiunta richiesta per la sola pilota — 2026-09-06

### Ulteriori fonti approvate dall'utente

Azalea, CSS Udine, Teatro Verdi Pordenone, Teatro Verdi Trieste e Pordenone
Pensa sono registrate in `pilot_source_policy.APPROVED_SOURCES`. Lettori
specifici e collegamento alla pubblicazione ancora da completare: non sono
fonti runtime attive. Nessuna modifica al backend beta.

Prima verifica pubblica: metadati generici WebPage/CollectionPage per quattro
fonti, nessun JSON-LD nella homepage CSS. Non sono feed Event utilizzabili
direttamente. Esempio Azalea Sebastian Di Bin: datePublished 19 agosto 2026
non coincide con la data concerto 6 settembre 2026. Vietato usare tale campo
come data evento. Il validatore locale richiede provenienza esplicita della
data, anno completo e comune; scarta eventi passati e richiede revisione per
annullamenti, rinvii e conflitti. Va chiamato dagli adattatori prima di publicarli.

### Pordenonelegge

Azalea implementation follow-up: `pilot_azalea.py` reads explicit schedule,
city and venue fields. Initial real probe returned 7 FVG events; the stricter
schedule-change check then stopped publication on wording requiring review.
Adapter remains outside the active registry until that case is inspected.
No event publication or cloud mutation was performed. Other four new adapters
remain pending. Article dates are never fallback event dates.

- **Pordenonelegge**, fonte ufficiale: https://www.pordenonelegge.it/
- Programma verificato: https://www.pordenonelegge.it/programma?giorno=mer
- Stato: adattatore pilota implementato e registrato in `pilot_sources.py`;
  scheduler/pubblicazione cloud non ancora collegati.
- Prova reale 2026-09-06: programma completo letto in una richiesta,
  445 incontri dal 16 al 20 settembre 2026, 14 comuni, nessun comune irrisolto.
  Coordinate comunali, non sedi precise. 49 test pilota superati, inclusi
  7 test specifici per date, sedi, accesso, duplicati e sessioni a orari diversi.
- URL di raccolta: https://www.pordenonelegge.it/programma?giorno=tutto
- Acquisire i singoli incontri con data, ora, luogo e link ufficiale, non le
  notizie della homepage come se fossero eventi.
- Includere le sedi Fuoricittà usando il comune effettivo; non assegnare tutti
  gli incontri a Pordenone. Applicare il raggio dopo la raccolta.
- Conservare le indicazioni di accesso (per esempio incontri riservati alle
  scuole); non indicare disponibilità o ingresso libero senza evidenza.
- Verificare anno dell'edizione, duplicati con TurismoFVG e condizioni di
  riutilizzo prima di attivare il collector. Non copiare descrizioni integrali
  o immagini senza verifica dei diritti.
- Nessuna modifica alla lista delle fonti attive del backend condiviso/beta.

Obiettivo: verificare che UI3 erediti Eventi puliti dal backend esistente, senza riscrivere la pagina frontend e senza introdurre consigli o fallback inventati.

## Flusso dati

```text
UI3 -> /api/local/events -> backend vecchio
  -> TurismoFVG
  -> SagreFVG
  -> Pro Loco FVG
  -> Paesi in Festa
  -> Anteprima Sagre
  -> EventiFVG
  -> filter_events_for_requested_place
  -> filter_relevant_nearby_events
  -> filter_past_events
  -> filter_default_event_window
  -> merge_events
  -> select_events_by_scope
  -> diversify_events
  -> cache risposta canonical limit
```

Regola cardinale: la UI non deve correggere semanticamente gli eventi. Se un evento e' fuori zona, deve essere filtrato prima nel backend.

## Matrice sorgenti

| Sorgente | Ruolo | Dato localita | Regola audit |
| --- | --- | --- | --- |
| TurismoFVG | Fonte principale eventi territoriali e culturali | `event_city`, `place`, coordinate quando disponibili | Ammessa se match testuale con localita richiesta o distanza entro raggio quando ci sono coordinate. |
| SagreFVG | Sagre/eventi tradizionali, anche via API | `venue.city`, `venue.venue`, coordinate API | Anche se l'API restituisce eventi non locali, il filtro finale deve eliminarli prima della risposta. |
| Pro Loco FVG | Eventi locali e di associazioni | dettaglio evento, `event_city`, `place`, `location_confidence` | Vietato fare fallback alla localita richiesta se non c'e localita verificata o match esplicito nel titolo. |
| Paesi in Festa | Supporto sagre/localita minori | testo estratto + geocode | Ammessa solo se il luogo estratto passa i controlli locali/nearby finali. |
| Anteprima Sagre | Supporto sagre/localita minori | testo estratto + geocode | Ammessa solo se il luogo estratto passa i controlli locali/nearby finali. |
| EventiFVG | Fonte supplementare | luogo estratto + geocode | Ammessa solo se il luogo estratto passa i controlli locali/nearby finali. |

## Correzioni chiuse

### Pro Loco FVG

Problema: il parser poteva usare la citta richiesta come `place` anche quando l'evento non aveva una localita verificata. Questo poteva far comparire eventi fuori zona nella pagina Eventi.

Decisione: se `location_confidence` e' assente o `none`, l'evento passa solo se:

- la localita verificata contiene la localita richiesta; oppure
- il titolo contiene esplicitamente la localita richiesta.

Commit backend: `79de21a Guard Pro Loco events without verified location`.

### Cache UI3

Problema: anche dopo fix backend, una vecchia cache browser poteva mostrare record sporchi fino al refresh.

Decisione: invalidare la cache Eventi UI3.

Commit UI3: `76c12cd Invalidate events cache after backend location guard`.

## Test di regressione

Backend:

- `test_proloco_event_without_verified_location_does_not_fallback_to_requested_city`
- `test_proloco_event_with_requested_city_in_text_can_use_display_fallback`
- `test_final_events_response_filters_out_of_place_source_payloads`

Il terzo test e' il contratto piu importante: se una sorgente restituisce un evento fuori localita, la risposta finale `/api/local/events` lo elimina prima che arrivi alla UI.

UI3:

- cache Eventi aggiornata a `eventsCache:v11`;
- test cache/controller Eventi/Home passati.

## Verifiche live locali

Endpoint locale verificato:

```text
http://127.0.0.1:8001/api/local/events
```

Campione controllato:

| Localita | Totale | Scope | Cache | Note |
| --- | ---: | --- | --- | --- |
| Pordenone | 47 | local | fresh | Nessun caso sospetto TRIESTE/Muggia/Latisana. |
| Gorizia | 21 | local | stale | Contenuto pulito; cache valida ma non fresh. |
| Udine | 48 | local | fresh | Nessun caso sospetto. |
| Trieste | 23 | local | fresh | Solo coerente con Trieste nel campione. |
| Lignano Sabbiadoro | 23 | local | fresh | Nessun caso sospetto. |

Browser UI3:

- pagina Eventi su Gorizia verificata;
- nessun record visibile `TRIESTE`, `Muggia`, `Latisana`;
- lista coerente con localita `Gorizia`.

## Debiti aperti

- Verificare con snapshot periodici che le nuove fonti supplementari non introducano rumore simile a Pro Loco.
- Decidere se mostrare in UI un micro-stato quando Eventi arriva da cache `stale`, senza trasformarlo in errore.
- Auditare ranking Home Eventi: evitare che mostre lunghe o eventi troppo generici dominino sempre la card.
- Auditare immagini Eventi per fallback, proporzioni e casi senza immagine, ma solo dopo la qualita dati.

## Estensione 2026-08-19: Villa Manin ed ERPAC in modalità ombra

Villa Manin ed ERPAC sono sorgenti candidate, non sorgenti attive. I relativi parser
non sono registrati in `build_local_events_response` e i loro record non possono
raggiungere l'app. L'acquisizione serve esclusivamente a produrre un report locale di
verifica.

Il contratto applicato è `event-source-audit-v1`:

- ogni fonte conserva il proprio record originale e la propria provenienza;
- le card scartate per data, anno o altri campi mancanti restano nel report come
  evidenza non pubblicabile e vengono confrontate per URL canonico o titolo esatto;
- TurismoFVG rimane la base regionale strutturata più matura, ma non è un requisito
  perché un evento ufficiale possa essere proposto alla revisione;
- Villa Manin può originare eventi ufficiali di Villa Manin assenti da TurismoFVG;
- ERPAC può originare eventi ufficiali ERPAC assenti da TurismoFVG;
- se ERPAC rimanda allo stesso URL canonico di una scheda Villa Manin, la scheda
  primaria resta Villa Manin e ERPAC viene conservato come conferma, senza generare
  un secondo evento; l'eventuale incompletezza della copia ERPAC viene conservata
  come nota della fonte secondaria, non come blocco della scheda primaria;
- nessun candidato viene pubblicato o unito automaticamente;
- un errore strutturale del parser blocca la relativa fonte;
- un errore HTTP su una singola pagina di dettaglio blocca quella scheda e viene
  registrato, ma non invalida le altre schede già acquisite e complete;
- una raccolta incompleta delle fonti già attive blocca l'approvazione dei candidati,
  perché non consente di escludere i doppioni con sufficiente sicurezza.
- TurismoFVG viene acquisito seguendo esclusivamente i collegamenti ufficiali
  `carica altri eventi`; leggere soltanto il primo blocco non costituisce un catalogo
  completo;
- per ogni candidato viene eseguita anche una ricerca TurismoFVG mirata per titolo:
  serve a intercettare record presenti nel catalogo ma non restituiti dalla prima
  pagina o dal normale ordinamento territoriale;
- un errore di raccolta delle fonti attive blocca i candidati del Comune interessato
  e mantiene bloccato lo stato generale del report, senza invalidare le verifiche
  complete ottenute per altri Comuni.

### Classificazione dei doppioni

| Esito | Condizione | Azione |
| --- | --- | --- |
| Doppione certo | URL canonico condiviso; oppure titolo, località e intervallo date pienamente concordi | Non creare una seconda card; controllare comunque eventuali conflitti. |
| Possibile doppione | Titolo correlato, località coerente e date sovrapposte, contenute una nell'altra o distanti al massimo un giorno | Quarantena e controllo manuale. |
| Conflitto | Discordanza su data, orario, località o stato tra record che sembrano riferirsi allo stesso evento | Pubblicazione bloccata. |
| Evento nuovo | Nessuna corrispondenza e campi critici completi | Candidato alla sola approvazione manuale. |

Il margine di un giorno serve soltanto a trovare record sospetti. Non autorizza mai
un'unione automatica. Anche una corrispondenza tramite URL non nasconde una data o una
località discordante: l'identità può essere certa mentre i dati restano in conflitto.
Una singola occorrenza contenuta nel calendario più ampio della pagina ufficiale viene
invece segnalata come calendario parziale: richiede controllo, ma non è etichettata
erroneamente come data incompatibile.

Le identità confermate manualmente tra due URL ufficiali vengono registrate in una
lista puntuale e tracciata con data e motivi della verifica. Questa lista evita di
riaprire a ogni audit lo stesso doppione già esaminato, ma non modifica le soglie
generali e non nasconde variazioni successive: una nuova discordanza su data, orario,
Comune, sede o stato resta un conflitto bloccante.

### Autorità contestuale per campo

Non esiste una fonte vincente in assoluto. Il report indica la fonte preferita per
ciascun campo, senza usare la preferenza per risolvere silenziosamente un conflitto:

- per un evento ospitato a Villa Manin, la pagina dedicata Villa Manin è il riferimento
  principale per titolo, data, luogo, descrizione e immagine;
- il Comune `Codroipo` può essere risolto dalla sede canonica approvata soltanto quando
  il contenuto della singola pagina nomina esplicitamente `Villa Manin`; il semplice
  fatto che la pagina appartenga al dominio `villamanin.it` non basta;
- per Magazzino delle Idee o un evento ERPAC diretto, la pagina ufficiale collegata da
  ERPAC è il riferimento principale;
- TurismoFVG conserva priorità per la classificazione regionale normalizzata e resta
  un confronto essenziale per completezza, località e deduplicazione;
- se due fonti autorevoli discordano su un campo critico, la gerarchia viene mostrata
  nel report ma la scheda resta bloccata.

### Campi e aggiornamenti bloccanti

Un candidato non può essere approvato senza titolo, URL ufficiale valido, data precisa
e Comune verificabile. Il Comune deve essere esplicito nella scheda oppure provenire
da una corrispondenza canonica di sede già approvata e tracciata, come `Villa Manin` →
`Passariano di Codroipo` → `Codroipo`. Descrizione, immagine e sede sono lacune
qualitative visibili nel report, non valori da inventare.

Per un evento già approvato:

- una modifica a data, orario, Comune, sede o stato riapre la verifica;
- una sede descritta in modo diverso tra card e pagina di dettaglio resta bloccata
  finché non viene confermato che si tratta, per esempio, di nome e indirizzo dello
  stesso luogo;
- una pagina scomparsa non equivale automaticamente a un annullamento;
- un annullamento o rinvio deve provenire da una fonte ufficiale e resta tracciato;
- una nuova descrizione o immagine della stessa fonte autorevole può essere proposta
  come aggiornamento, conservando la provenienza.

Le eccezioni già controllate a mano sono registrate per URL, data della revisione,
campi originari, valore risolto e collegamenti ufficiali usati come prova. La
risoluzione viene applicata solo se i campi critici osservati coincidono ancora con
quelli verificati; una variazione produce `reviewed_resolution_evidence_changed` e
riporta automaticamente la scheda in verifica.

### Esecuzione locale

Lo strumento `backend/tools/audit_event_sources.py`:

1. acquisisce l'intero catalogo Villa Manin tramite API ufficiale;
2. acquisisce la home ERPAC e, quando previsto, le pagine ufficiali di dettaglio;
3. interroga separatamente le sei fonti già attive per ogni Comune candidato;
4. per TurismoFVG segue la paginazione ufficiale e aggiunge le ricerche mirate dei
   titoli candidati;
5. confronta anche Villa Manin ed ERPAC tra loro;
6. genera JSON integrale e Markdown leggibile sotto `tmp/event-source-audit/`.

La directory `tmp/` è ignorata da Git. Il report è quindi locale, ripetibile e non
costituisce una pubblicazione. Una cartella che contiene già un report non viene
sovrascritta: ogni acquisizione deve conservare il proprio campione e il proprio esito.

### Automazione protetta e pubblicazione separata

L'audit può essere eseguito periodicamente dal job
`app.jobs.sync_event_sources`. Il job non pubblica direttamente i record: salva uno
stato versionato separato nella collezione Firestore
`event_source_automation/current`, oppure in un file JSON esplicito durante le prove
locali.

Il contratto operativo è fail-closed:

- un evento nuovo deve comparire con lo stesso fingerprint critico in due scansioni
  complete consecutive prima di passare da `pending` ad `approved`;
- il fingerprint comprende URL, titolo, data iniziale e finale, occorrenze, Comune,
  sede, orario e stato;
- una variazione critica rimette la nuova versione in attesa; fino alla seconda
  conferma resta disponibile la precedente versione approvata;
- descrizione e immagine possono aggiornarsi dalla stessa fonte senza riaprire la
  verifica critica;
- un doppione certo o una copia consolidata non entra nel catalogo approvato;
- una scheda ambigua, incompleta o in conflitto entra in quarantena;
- un errore di struttura o un confronto incompleto ripetuto apre un incidente; una
  singola osservazione transitoria non genera invece un falso allarme;
- ciascuna richiesta critica ammette un solo retry per timeout, connessione o HTTP
  transitorio; il secondo fallimento resta bloccante e non viene sostituito da cache
  vecchia;
- il 404 già verificato di `Flowers. Naturae, connessioni tra terra e arte` resta una
  quarantena attesa e non maschera altri errori;
- lo stato nasce con `publication_enabled=false`: l'automazione non può attivare da
  sola una fonte pubblica; dopo l'abilitazione manuale conserva il gate senza
  riaccenderlo autonomamente se un operatore lo disabilita.

Il feed applicativo ha tre modalità indipendenti:

- `off` (default): nessun record protetto raggiunge la pipeline Eventi;
- `preview`: ammessa soltanto in locale e utile per il controllo su browser/telefono;
- `active`: in produzione legge Firestore, ma restituisce eventi soltanto se anche il
  gate persistente `publication_enabled` è stato abilitato esplicitamente dopo i test.

In questo modo la disponibilità del parser, l'approvazione automatica prudente e la
pubblicazione sono tre decisioni distinte. Un guasto della persistenza o uno stato con
schema inatteso produce feed vuoto, mai dati non verificati.

### Monitoraggio tecnico

Il job emette un solo record JSON strutturato. Quando un incidente è attivo termina
con codice `1`, usa severità `ERROR` e include soltanto codici diagnostici sanificati.
In Cloud Run va associato a una policy Cloud Monitoring con canale email
`info@meteofriul.it`. Non viene usato SMTP nell'app e non vengono introdotte password
email nel backend. Il ritorno a esecuzioni sane risolve l'incidente nel monitoraggio.

In produzione ombra lo scheduler esegue il controllo alle `06:20` e alle `18:20`,
fuso `Europe/Rome`. Due scansioni consecutive significano quindi due osservazioni
distinte a circa dodici ore di distanza, non due richieste immediate allo stesso sito.
Le scansioni locali ripetute sono ammesse esclusivamente per collaudare il meccanismo
prima della prima attivazione.

L'immagine dei job deve essere aggiornata soltanto con un digest immutabile ricavato
da una build legata a un commit già testato. Prima e dopo l'update vanno confrontati
comando, argomenti, variabili, CPU, memoria, timeout, retry, task count e account di
servizio: l'unica differenza ammessa è `image`. Il recovery è valido soltanto quando
il job shadow termina con copertura completa, `incident_active=false` e `issues=[]`;
un candidato `pending` in attesa della seconda scansione non è un incidente e non
deve essere accelerato artificialmente. Il job di controllo pubblicazione va poi
eseguito esclusivamente in modalità `status`, lasciando invariato il gate.

### Anteprima locale del catalogo protetto

Dal backend:

```powershell
$env:EVENT_SOURCE_AUTOMATION_MODE='shadow'
$env:EVENT_SOURCE_LOCAL_STATE_PATH='..\tmp\event-source-automation\local-state.json'
$env:EVENT_SOURCE_ALERT_EMAIL_TO='info@meteofriul.it'
.\venv\Scripts\python.exe -m app.jobs.sync_event_sources
```

Dal root del progetto, dopo che lo stato contiene gli eventi approvati:

```powershell
.\scripts\start-dev.ps1 -Restart -EventSourcePreview
```

Lo switch passa al solo backend locale `EVENT_SOURCE_FEED_MODE=preview` e il percorso
assoluto del file. Per permettere il controllo visivo completo, la preview include
anche gli eventi protetti oltre la normale finestra dei prossimi giorni; le date non
vengono alterate. Non modifica Cloud Run, Cloudflare, Firebase o l'app pubblica.
