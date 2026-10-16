# Audit fonti eventi: risultati, correzioni e blocchi di rilascio

Data: 7 settembre 2026. Attività locale, nessuna pubblicazione cloud e nessuna
attivazione di nuove fonti nella beta. Nessun nuovo job o servizio AI acquistato.

## Perimetro e significato dei risultati

Eseguiti 15 percorsi reali su 14 fonti: TurismoFVG è letto sia dalla legacy sia
dalla pilota. Le raccolte non sono simultanee e non hanno la stessa copertura.
Le fonti legacy sono interrogate per Pordenone, limite 100; la pilota legge
programmi regionali. I numeri seguenti NON sono manifestazioni uniche né tutti
eventi vicini a Pordenone. Una raccolta riuscita non prova completezza del sito.

| Fonte | Percorso/esito reale | Azione o limite accertato |
| --- | --- | --- |
| TurismoFVG | Pilota: 526 record, 67 pagine, 168,5 s in una raccolta riuscita precedente al controllo rigoroso dell'anno. Legacy: 62 record, 21,4 s | Altre esecuzioni: reset di connessione e timeout diagnostico. Cinque URL legacy assenti dall'output regionale. Riquadro in evidenza non coperto dal parser; molte tessere piccole prive di anno. Non certificata la versione finale su tutta la fonte. |
| Pordenonelegge | 445 record, 442 nel filtro Pordenone 20 km | Programma, non dettagli individuali. Conservati incontri distinti; chiave locale include ora, luogo e titolo. |
| Azalea | 3 record e 3 revisioni | Entrambi i concerti Baglioni segnalati riportano rinvio al 2027. Sfera Ebbasta rimane in revisione: non dedurre annullamento definitivo dal solo segnale testuale. |
| CSS Udine | Dopo correzioni: 41 record, 1 revisione | Recuperate liste di giorni, orari con punto, fasce orarie e programma su tre comuni. Cieli sonori resta senza anno verificato nel blocco calendario. |
| Pordenone Pensa | 2 record | Limitato a In Giallo 2026: non è un lettore generico delle future edizioni. |
| Verdi Pordenone | Dopo correzioni: 56 record, 2 revisioni | Spazio Due verificato su https://teatroverdipordenone.it/le-sale/. Restano Sdeng senza calendario e Teatro genera cultura con sede esterna e data 22 luglio 2026, ormai passata. |
| Verdi Trieste | Dopo correzioni: 56 appuntamenti, 0 revisioni sintattiche | Date discrete anche su più mesi; gli orari mancanti restano assenti. Nessuna verifica garantita dei dettagli protetti o di avvisi fuori dal calendario. |
| SagreFVG | Legacy: 18 record | API strutturata; non attivata nella pilota. Frazioni come Tamai e Tesis non sono comuni canonici; la pagina API letta non dimostra esaustività della paginazione. |
| Pro Loco FVG | Legacy: 2 record | Entrambi fuori dal raggio Pordenone 20 km nella prova. L'estrazione legacy cerca date anche nel testo ampio: non promuoverla senza delimitare il blocco evento. |
| Paesi in Festa | Legacy: 16 record | 11 nel filtro diagnostico. Titoli generici e frazioni richiedono riconciliazione: due «Sagra di Pordenone» hanno URL distinti, non si possono unire dal solo titolo. |
| Anteprima Sagre | Legacy: 5 record | 2 nel filtro diagnostico. Alcune date senza anno nell'output legacy: non sono prove sufficienti per il nuovo controllo. |
| EventiFVG | Legacy: 6 record | 5 senza coordinate, 1 fuori raggio. Nessuna posizione sostituita con quella del telefono. |
| Villa Manin | 359 ricevuti, 1 accettato, 110 rifiutati, 248 inattivi | Percorso sperimentale; non è una fonte pilota attiva. Le esclusioni richiedono analisi dei formati prima di rivendicare copertura. |
| ERPAC | 14 ricevuti, 7 accettati, 6 rifiutati, 1 inattivo | 5 eleggibili per revisione e 2 da revisione manuale; nessuna pubblicazione automatica. |

## Differenza da interpretare Villa Manin / ERPAC

«Lo scrigno del Doge in Villa Manin»: Villa Manin restituisce inizio 25 aprile
2026, ERPAC 20 settembre 2026; termine comune 6 gennaio 2027. La provenienza
ERPAC è già segnalata come duplicato della fonte Villa Manin e priva di comune.
Non si scelgono le date per maggioranza né si combinano i campi senza evidenze.

Rettifica dopo lettura della pagina primaria: il calendario di Lo scrigno del
Doge elenca sei occorrenze, 25 aprile, 2 giugno, 20 settembre, 1 novembre,
8 dicembre 2026 e 6 gennaio 2027. Il 20 settembre può quindi rappresentare la
prossima occorrenza, mentre il 25 aprile è l'inizio dell'intera serie: i soli
estremi diversi NON dimostrano un conflitto. Occorre confrontare insiemi di
date equivalenti e stesso istante di osservazione prima di segnalarlo.
Fonte letta: https://www.villamanin.it/evento/lo-scrigno-del-doge-in-villa-manin/
Esiste invece una divergenza da tenere distinta: il calendario PDF ERPAC
2026 pubblicato in aprile riporta 6 dicembre, la pagina evento 8 dicembre.
Non sostituire la data della pagina corrente con quella del PDF precedente.

La priorità richiesta esiste già nelle funzioni di consolidamento in audit.py:
Villa Manin primaria per URL canonico condiviso, ERPAC come riscontro senza
scheda separata. ERPAC non è subordinata indistintamente per eventi di altri
poli: la fonte diretta del relativo evento va identificata separatamente.
80 test Villa Manin/ERPAC/audit superati; entrambe restano in ombra, non attivate.

## Confronto locale a filtro uguale

Pordenone (45.9569, 12.6605), 20 km in linea d'aria, 7 settembre–6 dicembre 2026.
84 record legacy e 547 pilota dopo il filtro; 68 coppie candidate, 27 record
legacy senza candidato e 479 pilota senza candidato. Gran parte della diversa
quantità deriva da Pordenonelegge, assente dal registro legacy esaminato.
Non sono conteggi di eventi persi: fonti, acquisizioni e identità differiscono.

Nei candidati: 12 differenze di inizio, 10 di fine, 12 di sede, 1 di ora, 1 di
place. Una differenza può essere una replica o un campo mancante, non per forza
un errore. Il confronto non esegue fusioni automatiche.

Cinque riferimenti TurismoFVG legacy assenti anche dall'output regionale grezzo:

- `/eventi/pordenonelegge-2026` (pagina controllata: HTTP 200; link nel riquadro in evidenza).
- `/eventi/jazz-river-lucio-c-e-la-vita-e-la-musica-di-lucio-dalla`
- `/eventi/matilda-mi-racconti-una-storia-502205`
- `/eventi/40-giostra-dei-castelli`
- `/eventi/pedalare-verso-il-cambiamento-mobilita-sostenibile-salute-e-liberta`

## Correzioni locali implementate

- Controllo di pubblicazione comune realmente collegato alle sette fonti pilota:
  fonte, date, occorrenze, ore, coordinate finite e accoppiate; conteggi esclusioni.
- TurismoFVG: niente anno corrente aggiunto in modalità pilota; URL senza data
  esplicita conservati in revisione. Default legacy mantenuto.
- Un solo retry transitorio per pagina TurismoFVG tramite helper già esistente;
  limite del processo/cloud invariato. Non validato con un'ulteriore scansione
  completa dopo l'ultimo cambiamento, per evitare una sequenza illimitata di richieste.
- Dettaglio vuoto non certificato, avviso precedente non cancellato da una lettura
  fallita; download dettagli limitato. Nessun riuso descrizioni abilitato.
- Formati CSS e Trieste corretti con test derivati dai casi reali; Spazio Due
  ammesso come sala verificata del Verdi Pordenone.
- Fine orario discordante impedisce deduplicazione; valore disponibile conservato.
- Etichette coordinate `exact` e `venue` riconosciute; posizioni comunali approssimative.
- Contatore UI riferito alle schede filtrate e raggruppate, non al totale grezzo.
- Strumenti offline di confronto e probe locale, senza dipendenze da client cloud.

## Rilascio: NON approvato come sistema completo

L'audit ha prodotto risultati su tutte le fonti, ma non dimostra né realizza
un catalogo completo e privo di errori. Prima di pubblicare le modifiche:

1. Completata la scoperta dei riquadri in evidenza TurismoFVG come candidati; trovare
   la prova dell'anno per le tessere piccole senza ripristinare inferenze silenziose.
2. Misurare quante verifiche dettaglio servono con il budget esistente. Non basta
   un limite di 20 URL per promettere tutti i dettagli verificati a ogni giro.
3. Verificare le anomalie editoriali residue e le 110 esclusioni Villa Manin
   prima di aggiungere fonti oggi sperimentali.
4. Ripetere il confronto sulla versione finale con ambito e acquisizione registrati.
5. Abilitare testi/immagini soltanto con provenienza e condizioni compatibili.

Non sono stati aumentati timeout cloud, creati job o attivate nuove fonti.
Per il momento la decisione sicura è mantenere queste modifiche locali.

## Riproducibilità

- `python tools/probe_pilot_sources.py --all`: probe limitato, output in directory temporanea.
- `python tools/probe_pilot_sources.py --source pilot:TurismoFVG --timeout 360`: controllo sorgente isolata.
- `python tools/compare_event_snapshots.py legacy.json pilot.json`: rifiuta ambiti diversi.
- `python tools/summarize_event_evidence.py <cartelle> --as-of 2026-09-07`: stesso filtro, senza attribuire identità certa.
- `python -m unittest discover -s tests -p 'test_pilot_*.py'` da backend.
- Test legacy mirati: test_events_engine, test_event_source_audit, test_event_source_http.
- Test frontend: EventsView, eventsViewModel, eventOccurrences con configurazione nativa.

Evidenze temporanee: `meteofriul-source-audit-cfabg3bv`,
`meteofriul-source-audit-cqx4qi8w`, `meteofriul-source-audit-zp34sx75`
in `%LOCALAPPDATA%/Temp`. Questo documento conserva le conclusioni anche se
Windows elimina gli output temporanei; non contiene copie delle descrizioni.

## Verifica completa TurismoFVG con dettagli — aggiornamento finale della sessione

Probe locale `--source pilot:TurismoFVG --details --timeout 360`, evidenza
`meteofriul-source-audit-_kju3d9z`: concluso in 259,1 secondi, stato ok,
20 URL di dettaglio richiesti, 16 record ammessi, 470 candidati pendenti,
zero gruppi di duplicati esatti. Non significa assenza di duplicati semantici.
La scansione supera il precedente limite di rete e verifica il percorso con anno
esplicito. Il conteggio di 526 della scansione precedente non è quindi il
conteggio pubblicabile del nuovo controllo. Non sono conteggi confrontabili
con un filtro locale Pordenone/20 km applicato.

Il probe riportava una segnalazione dettaglio; successivamente è stato corretto
il wrapper che sovrascriveva le segnalazioni dell'elenco. Ora conserva entrambe
le raccolte. Il totale delle segnalazioni non è stato rimisurato via rete dopo
questa correzione; non va interpretato come numero di problemi unici.

I dettagli sono richiesti entro il limite esistente di 20 URL e il tempo della
fonte. I candidati senza data certa non entrano nel catalogo. Titolo e comune
devono concordare; la promozione automatica copre solo date singole esplicite.
Gli intervalli richiedono un controllo delle effettive giornate di apertura.
La cache contiene fatti e verdetti, non biografie o descrizioni copiate.

La coda dà precedenza agli URL mai controllati e fa ruotare anche i tentativi
falliti. Test: 25 candidati comportano al massimo 20 richieste e cinque pendenti.
Questo NON risolve ancora la copertura: 470 candidati richiederebbero almeno
24 ulteriori giri da 20, anche senza errori o nuovi ingressi. La scadenza della
cache a 24 ore deve essere valutata insieme alla frequenza del job esistente;
non è dimostrato che il sistema raggiunga una copertura stabile. Nessun nuovo
job o aumento di budget è stato introdotto.

Ulteriore regressione corretta: il prefiltro del catalogo conserva titolo,
fine orario e insieme delle occorrenze nell'identità; la deduplicazione comune
non fonde insiemi di repliche discordanti. Verifica finale locale: 136 test
`test_pilot_*.py` superati. Rilascio ancora non approvato: serve chiudere la
copertura dei dettagli e il confronto finale, non semplicemente distribuire
un catalogo impoverito dal filtro prudenziale.

## Correzione di metodo: partire dalla pagina e dal legacy

Su richiesta dell'utente, il controllo torna a partire dai dati pubblicati e
dall'estrattore legacy, non dall'aggiunta di restrizioni. Letti i dettagli reali
di Matilda, Pordenonelegge e Festeggiamenti di S. Angelo: il JSON-LD osservato
descrive il sito (WebSite/SearchAction), non gli eventi. I campi utili sono già
nel riquadro HTML letto dal legacy: data completa, comune e sede. Non occorre
inventare un nuovo accesso API né dedurre l'anno dalla data corrente.

Matilda è ora verificato dal percorso di acquisizione reale: una manifestazione,
otto occorrenze (3/17 settembre, 1/15/29 ottobre, 12/26 novembre, 10 dicembre
2026), sede Centro per le Famiglie, Pordenone. L'intervallo settembre–dicembre
non viene trasformato in presenza quotidiana. Il parser legge il blocco
esplicito Calendario e usa l'anno del campo data completo, controllando che
tutte le occorrenze ricadano nell'intervallo. Test negativi per calendari
incompleti, date impossibili, anni discordanti e date incidentali nel racconto.
Sede e occorrenze sono conservate anche nella cache dei fatti (versione 4);
le coordinate restano dichiarate comunali, non della sede.

139 test pilota superati. Questa verifica risolve un formato reale, non tutti
i 470 candidati: intervalli, calendari diversi e copertura delle richieste
restano da misurare. Nessun deploy o nuovo job.

Regola per i prossimi interventi: prima campioni reali rappresentativi e
confronto legacy, poi test riproducibili e correzione dell'estrattore. Un crollo
dei record ammessi è una regressione da spiegare, non una prova di qualità
dei filtri. Ogni limite operativo deve avere una misura a sostegno.

## Rimozione del limite arbitrario sui dettagli

Il wrapper TurismoFVG usa ora il limite temporale esistente (335 secondi,
comprensivi dell'elenco, nel processo da 360 secondi) senza tetto di 20 URL.
Non sono stati introdotti nuovi job, concorrenti o un nuovo estrattore.
Restano la lettura legacy dei campi, le correzioni per le righe identificate
dalle icone e la cache dei fatti. Il parametro numerico resta disponibile
per test e diagnostica; senza parametro numerico è obbligatoria una scadenza.
Test: 25 URL vengono tutti controllati quando c'è tempo; a scadenza già
raggiunta non parte nessuna richiesta. 143 test pilota e 81 test legacy
mirati superati. La modifica non dimostra da sola copertura completa e non
è stata distribuita al job remoto.

Collaudo reale concluso: `meteofriul-source-audit-obyexn0r`, 335,7 secondi,
240 URL di dettaglio controllati, 160 record ammessi, 324 candidati pendenti.
Zero gruppi di duplicati esatti non certifica assenza di duplicati semantici.
Le 472 segnalazioni includono quelle dell'elenco conservate: non sono 472
eventi distinti errati. La rimozione del tetto migliora l'acquisizione ma non
chiude la copertura; non effettuato deploy né sostituito catalogo remoto.

## Riallineamento intervalli al legacy, rielaborazione offline

Rimosso il rifiuto generalizzato degli intervalli in `promote_candidate`.
Riutilizzate `parse_event_date_range` e `parse_turismofvg_discrete_occurrences`
del legacy: gli intervalli conservano inizio/fine senza creare repliche;
le date enumerate conservano le occorrenze. `schedule_kind` distingue i casi.
Restano escluse regole come "ogni lunedì fino a..." che il solo parser di
intervalli non risolve. Nessuna nuova richiesta alla fonte per questo confronto.

Sul campione salvato dei 324 candidati: 72 recuperati complessivamente
(comprendono i nove recuperati con i titoli abbreviati), 18 ancora da chiarire,
231 non scaricati e tre indisponibili. I 18 includono eventi multicomune,
toponimi non risolti, differenze di titolo, ricorrenze e una data in tedesco.
Non sono necessariamente eventi errati o duplicati. Questi sono risultati
di interpretazione offline, non conteggi di pubblicazione o aggiornamento cloud.

## Regola operativa per fonti aggiunte

Richiesta dell'utente: mantenere il percorso legacy; le nuove fonti devono
essere studiate prima della pubblicazione, altrimenti restano spente.
Verificato il registro effettivo: Villa Manin ed ERPAC sono già escluse dalla
raccolta pilota, così come i cinque adattatori legacy non trasferiti. Non è
necessario spegnere un servizio o cancellare dati per mantenerle escluse.
Test di regressione verifica che registro runtime e lista autorizzata coincidano
e che le sette fonti escluse non possano superare la validazione pubblica.

Prima di attivare Villa Manin/ERPAC occorrono almeno: risoluzione del conflitto
di data documentato per Lo scrigno del Doge, classificazione delle esclusioni,
distinzione date evento/pubblicazione, sedi e repliche, fixture HTML/API e test
positivi/negativi, prova con medesimo ambito del catalogo e verifica dei diritti
per eventuali testi e immagini. Non basta che il download termini senza errori.
Per le sette fonti pilota già studiate restano validi gli ambiti e i limiti
documentati nella tabella: non sono dichiarate esaustive di tutti i siti.

## Analisi delle esclusioni Villa Manin / ERPAC

Ripetuto il raccoglitore Villa Manin ESISTENTE, con `_embed=1` e data
7 settembre 2026: 359 record, 248 passati, 110 esclusi, un record accettato.
Le esclusioni sono 102 date mancanti, quattro intestazioni discordanti,
due calendari ambigui e due URL non ammessi. Non equivalgono a 110 eventi
futuri persi: il feed include archivio storico. Una lettura senza `_embed`
non è confrontabile: manca il contesto delle tassonomie anno e produce
ulteriori esclusioni artificiali. Mantenere il raccoglitore esistente.

Ispezione API diretta:
- Bike Tour, ID 26327: intestazione «Tutti i giovedì da giugno a metà settembre»,
  senza estremi precisi. Non convertire «metà settembre» in giorno inventato.
- Negramaro, ID 22030: intestazioni 25.07.2025 e 25 luglio 2026 nella stessa
  pagina; il corpo cita sabato 25 luglio 2026. Il conflitto è presente nella
  fonte, non generato dal parser. Entrambe le date sono passate al giorno
  dell'audit; non è un evento futuro mancante da recuperare automaticamente.

ERPAC, evidenza già salvata: sei esclusioni (cinque senza anno, una senza data).
Tre delle schede senza anno rimandano direttamente a Villa Manin (Giardino del
Doge, Cena in bianco, Sebastian Di Bin): vanno risolte con la fonte primaria,
non completate con l'anno corrente. Palazzo Altan ha repliche 6/20 settembre
senza anno nella tessera ERPAC: occorre leggere la pagina del museo collegata.
Questa analisi NON chiude ancora tutte le esclusioni e non autorizza l'attivazione.
