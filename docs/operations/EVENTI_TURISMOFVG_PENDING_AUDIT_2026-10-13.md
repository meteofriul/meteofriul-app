# TurismoFVG — audit dei risultati pendenti e del blocco della fonte

Data: 13 ottobre 2026, dopo il recupero serale.
Ramo: `codex/events-card-quarantine`.
Commit esaminato: `b60b3d48`; runtime distribuito: `9718e2bc`.

## 1. Mandato, metodo e limiti

Richiesta: «procedi al controllo», riferita alle sette pagine rimaste pendenti
nel ciclo completo. Questo intervento esamina il comportamento, senza
correzioni applicative, nuovi job cloud, nuove letture dei siti o modifiche
alle regole di pubblicazione. Usa codice del ramo, cataloghi/log già salvati e
prove locali con HTML ed errori simulati. Nessuna operazione GitHub.

**Esito: il comportamento attuale non realizza completamente la regola
“problema di singola scheda → escludere la scheda; problema generale della
fonte → bloccare la fonte”.** Le quarantene dei contenuti già letti funzionano,
ma alcuni errori di lettura restano bloccanti per tutta TurismoFVG. Esiste
anche un caso opposto di guasto generale che può essere classificato come
semplice insieme di quarantene.

La riuscita delle prove sotto significa che i difetti sono riprodotti sul
codice invariato, non che siano corretti. Non è stato avviato un nuovo ciclo
per tentare di ricreare l'incidente su TurismoFVG.

## 2. Cosa si sa del vero incidente

Riferimento: [deploy, recupero e prova TEST](EVENTI_FASE_0_DEPLOY_E_TEST_2026-10-13.md).

- Ciclo `hbz5f`: `pending=7`, `source_complete=false`, `within_budget=true`.
  Due revisioni note nel controllo; il problema bloccante è l'inventario
  non concluso, non il solo numero delle revisioni.
- Il catalogo dopo il fallimento mantiene **esattamente lo stesso checkpoint
  verificato** di prima: 1.189 URL, zero pendenti. Il tentativo nuovo,
  descritto solo dai contatori, aveva un inventario di 1.216 URL.
- Il fingerprint dell'inventario del recupero `vc7lk` coincide con quello
  dichiarato dal tentativo fallito. Il recupero ha zero pendenti e pubblica
  1.209 schede, con tre quarantene.
- Gli URL dei sette pendenti e il loro ultimo errore non sono recuperabili
  dagli artefatti persistiti esaminati. Non sono sette schede di cui sia
  provata la non conformità; potevano essere richieste fallite o letture
  ancora da completare. Non è dimostrato un blocco antiautomazione del sito.
- Durante l'esclusione TurismoFVG, la query API Pordenone/20 km è passata
  dalle 281 schede precedenti a 104; dopo il recupero a 299. Le altre fonti
  hanno continuato a contribuire. Non si è svuotato l'intero catalogo.

### Ricostruzione limitata delle letture possibili

Confrontando l'inventario del recupero con il checkpoint precedente e
l'età all'inizio del ciclo fallito, risultano:

| Classe | URL |
| --- | ---: |
| Risultato riutilizzabile senza rinnovo anticipato | 1.158 |
| Nessun risultato precedente | 41 |
| Firma dell'indice cambiata | 11 |
| Stato precedente da ricontrollare | 3 |
| Ancora validi, ma candidati al rinnovo anticipato | 3 |
| Scaduti per età fra quelli con firma e stato riutilizzabili | 0 |

Sono quindi 58 candidati a una lettura o rilettura, **non l'elenco dei sette
fallimenti**. È una ricostruzione basata sull'inventario del recupero con
fingerprint coincidente, non il registro mancante del primo tentativo.
I tre rinnovi anticipati, da soli, non spiegano sette pendenti.

## 3. Risultati del controllo

### P1 — un singolo errore di lettura esclude tutte le schede della fonte

[inspect_batch](../../backend/app/events/pilot_regional_year_control.py),
righe 521, 556 e 570: 404/410 su pagine elencate diventano revisioni; invece
403, 429, 503, timeout ed eccezioni restano nel dizionario `attempts`, senza
un risultato della pagina. Il contatore massimo è tre tentativi dell'adapter.

[summary](../../backend/app/events/pilot_regional_year_control.py), riga 596,
e [collector](../../backend/app/events/pilot_regional_verified.py), righe 390
e 408: per la completezza servono un risultato per ogni URL e zero tentativi
irrisolti. Una sola pagina mancante restituisce `incomplete_source`, con
`events=[]`, anche se tutte le altre pagine sono state verificate.

Il [merge](../../backend/app/events/pilot_catalog.py), riga 63, marca il lotto
precedente `stale`. L'API lo esclude. Il [job](../../backend/app/events/pilot_cloud.py),
riga 139, salva il catalogo con gli aggiornamenti delle altre fonti e poi
termina con errore. Questo può generare l'email di fallimento Eventi.

**Riproduzione:** due eventi, uno valido e uno che va sempre in timeout:
un solo URL pendente, zero eventi TurismoFVG pubblicabili, tre tentativi
sull'URL problematico. Lo stesso accade per 403/429/503 isolati.

### P1 — una manutenzione generale HTTP 200 può svuotare la fonte senza bloccarla

[Collector](../../backend/app/events/pilot_regional_verified.py), riga 416,
[proiezione](../../backend/app/events/pilot_regional_display_audit.py), riga 342,
e [gate TurismoFVG](../../backend/app/events/pilot_source_policy.py), riga 402:
le pagine lette e classificate `review_required` possono rendere completo
l'inventario anche se non resta nessuna scheda valida.

**Riproduzione:** indice completo con due eventi; entrambe le letture
restituiscono `<h1>Servizio momentaneamente non disponibile</h1>` come HTML.
Il risultato supera il gate come `partial`, zero eventi e due quarantene.
Nel merge un lotto precedente con schede valide viene sostituito dal lotto
vuoto. TurismoFVG non è aggiunta alle fonti bloccanti del job in questo caso;
gli altri controlli del job restano indipendenti.

È un caso simulato, **non osservato sul sito reale durante l'incidente**.
Dimostra però che allargare le quarantene senza riconoscere i guasti generali
può peggiorare la situazione. Un indice vuoto legittimo o una stagione
conclusa provata devono restare distinti da un sito in manutenzione.

### P2 — il rinnovo anticipato può rimuovere una prova ancora valida

[Collector](../../backend/app/events/pilot_regional_verified.py), righe 345–362:
quando tutte le pagine sono già coperte, rinnova i risultati che hanno
raggiunto metà del limite di età. Prima della richiesta, li toglie da
`results`. Se la nuova lettura fallisce, il risultato originale non viene
rimesso, anche se ha ancora età e firma ammissibili.

**Riproduzione:** una scheda controllata un'ora prima e una 25 ore prima,
con limite di validità 48 ore e firme invariate. Il controllo precedente è
ancora fresco. Fallisce solo il rinnovo della seconda: la fonte diventa
`stale`, la query restituisce zero schede, il checkpoint precedente resta
conservato ma non è visibile.

Correzione da valutare: mantenere separata la prova ancora valida durante
un rinnovo facoltativo, sostituendola solo a lettura riuscita. Non va cambiato
il suo `checked_at`, né esteso il limite 48/96/168 ore. Una firma cambiata,
un avviso di annullamento o una lettura valida con dati diversi richiedono
invece il normale nuovo controllo, senza recuperare silenziosamente i dati vecchi.

### P2 — si perdono diagnosi e progressi del tentativo fallito

Il controllo interno conserva l'URL, il numero dei tentativi e il nome
dell'eccezione. Non conserva il codice HTTP per gli errori diversi da 404/410,
né separa chiaramente la fase di download da quella di analisi HTML.
Un `HTTPError` può rappresentare 403, 429 o 503; un'eccezione del parser viene
riprovata riscaricando la pagina.

Il collector restituisce l'intero controllo in memoria, ma non espone gli
URL pendenti come `detail_candidates`. [failure_diagnostics](../../backend/app/events/pilot_catalog.py),
riga 15, conta soltanto quella lista e le revisioni. Quando esiste già un
checkpoint verificato, il merge mantiene quello e non salva il nuovo
controllo incompleto. Nel caso reale restano così `pending=7` nel riepilogo,
`last_attempt_pending_count=0` e nessuna identità dei sette URL.

Il checkpoint verificato va protetto; serve un registro separato del
tentativo, non la sua sostituzione indiscriminata. Il recupero attuale riparte
dalla verifica precedente e ripete calendario, sitemap e dettagli dovuti;
non è un download delle sole sette pagine e non riusa i progressi del
fallimento che non sono stati conservati.

### Osservazioni sui tempi e sui tentativi

- Ogni chiamata a [fetch_detail](../../backend/app/events/pilot_regional_sitemap_audit.py)
  può già riprovare una volta gli errori transitori tramite
  [http_client](../../backend/app/events/http_client.py). Tre tentativi del
  controllo possono quindi produrre **sei GET** sullo stesso URL. Riprodotto
  con HTTP 503 usando i veri helper e una risposta simulata.
- `within_budget=true` non prova che tutte le pagine siano state tentate.
  Il loop non inizia un altro lotto negli ultimi 20 secondi dei 335 concessi.
  Nella simulazione con indice completato a 316 secondi, entrambe le pagine
  restano pendenti senza alcun tentativo, ma `within_budget` è ancora vero.
- Il timeout esterno della fonte resta 360 secondi. Nessun tempo, retry o
  parallelismo è stato aumentato per questo audit.

## 4. Matrice riprodotta, codice invariato

Eseguiti 11 test di caratterizzazione con 16 scenari; tutti riproducono
l'esito atteso del codice corrente. Non sono test che attestano una correzione.

| Caso | Esito corrente |
| --- | --- |
| Due schede valide | `ok`, due eventi |
| Una scheda leggibile senza date | `partial`, un evento e una quarantena |
| Una pagina elencata 404 o 410 | `partial`, un evento e una quarantena |
| Una pagina 403, 429 o 503 persistente | Errore fonte, un pendente, zero eventi |
| Un timeout persistente | Errore fonte, un pendente, zero eventi |
| Un errore di validazione della risposta | Errore fonte, tre letture |
| Un'eccezione del parser | Errore fonte, tre download e tre analisi |
| HTTP 503 tramite helper reale | Sei GET simulati, poi errore fonte |
| Rinnovo fallito a 25 ore, validità 48 ore | Fonte `stale`, dati precedenti nascosti |
| Indice consuma il tempo utile | Pendenti non tentati, `within_budget=true` |
| Indice incompleto | Eccezione prima dei dettagli |
| Tutti i dettagli in timeout | Errore fonte |
| Tutti i dettagli con HTML di manutenzione | `partial` vuoto; sostituisce il lotto valido |

La prima esecuzione dell'helper di audit conteneva un argomento non previsto
in una chiamata di verifica (`today` invece di `now`): corretto solo l'helper
e ripetuta la prova. Nessuna modifica necessaria al runtime per riprodurre
il problema. Le prove definitive terminano in meno di un secondo, senza rete.

## 5. Soluzione proposta da approvare

Ordine consigliato per una correzione locale sullo stesso ramo:

1. **Diagnostica persistente per URL:** fase (`fetch`, `parse`, budget),
   categoria dell'errore, eventuale codice HTTP, tentativi, timestamp e motivo
   di arresto. Distinguere “mai tentata” da “tentativi esauriti”. Mantenere
   separati checkpoint verificato e tentativo incompleto. Contatori nei log
   e nel catalogo devono riferirsi agli stessi URL.
2. **Separare esito dell'indice, della fonte e della scheda:** un inventario
   incompleto o un guasto generale provato devono restare bloccanti. Una
   pagina isolata che fallisce deve poter restare in quarantena lasciando
   pubblicabili le altre, con prove che il resto della fonte funzioni.
   Le pagine mai tentate per tempo esaurito non vanno falsamente classificate
   come schede non conformi o sito guasto.
3. **Riconoscere manutenzione/blocco anche con HTTP 200**, ed evitare il lotto
   vuoto “riuscito” quando tutte le pagine correnti perdono la struttura
   dell'evento. Zero eventi legittimi ed edizioni concluse restano casi distinti.
   L'eventuale soglia numerica o percentuale di guasto va dichiarata e motivata,
   non introdotta implicitamente o sostituita da “zero pendenti obbligatori”.
4. **Conservare i risultati ancora validi nei soli rinnovi facoltativi**, con
   firma ed età controllate, mantenendo data originale della verifica e
   fallimento del rinnovo visibile nei diagnostici.
5. Trasformare i casi sopra in test della nuova regola: scheda isolata
   esclusa, schede sane presenti, guasto generale bloccante, nessuna perdita
   dei diagnostici, nessuna freschezza artificiale. Separare download e parser
   per evitare i retry di rete che non possono correggere un errore di analisi.

La correzione deve includere sia il collector sia il gate indipendente, poi
merge/API/log: modificare soltanto il ritorno del collector non basta, perché
il gate ricontrolla gli stessi vincoli. I guasti interni del programma vanno
segnalati come tali e non dichiarati guasti del sito senza prove.

**Stato alla chiusura dell'audit:** nessuna di queste modifiche applicative
è stata eseguita. Il backend distribuito rimane quello del recupero già
verificato. Prossimo passo: autorizzare e preparare la correzione locale con
test; merge, distribuzione e ulteriori cicli cloud restano azioni separate.

## 6. Evidenze e continuità

Directory locale: `.dev-logs/events-turismofvg-pending-audit-2026-10-13/`.

- `offline-characterization.py`: riproduzione locale senza rete.
- `offline-characterization.json`: 16 scenari, contatori e risultati.
- `incident-checkpoint-analysis.json`: confronto dell'incidente, con l'elenco
  dei 58 candidati esplicitamente marcato come inferenza, non come errori.
- `manifest.json`: dimensioni e SHA-256 delle prove.

Le evidenze grezze sono ignorate da Git; questo resoconto e la matrice
riproducibile sono salvati nel ramo. La struttura completa del sistema resta
in [architettura job e allarmi](EVENTI_ARCHITETTURA_JOB_E_ALLARMI_2026-10-13.md).

## 7. Seguito autorizzato

Dopo l'approvazione dell'utente è stata preparata e verificata localmente la
[correzione di isolamento dei dettagli](EVENTI_TURISMOFVG_ISOLAMENTO_DETTAGLI_2026-10-13.md)
sullo stesso ramo. Le sezioni precedenti descrivono lo stato e le prove al
momento dell'audit; non implicano che la nuova correzione sia già distribuita.
