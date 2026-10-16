# Audit repertorio proverbi giornalieri

Data audit: 2026-07-04

## Obiettivo

Capire come reperire i proverbi mancanti per un Almanacco giornaliero, senza usare testi casuali, senza violare fonti moderne e senza pubblicare materiale non revisionato.

## Aggiornamento corrente 2026-07-23

| Blocco | Quantita | Stato |
| --- | ---: | --- |
| Proverbi pubblicati | 173 | 139 `lab_ready`, 34 `draft` |
| Proverbi idonei all'Almanacco | 168 | Esclusi i record senza regola temporale o contesto sufficiente |
| Proverbi con revisione umana dichiarata | 139 | IT/FUR approvati |
| Date fisse in calendario | 33 | Tutti i riferimenti puntano a record idonei |
| Candidati estratti | 122 | 83 gia pubblicati, 39 chiusi fuori dal repertorio |
| Repertorio di lavoro distinto | 212 | Pubblicati + candidati non duplicati |

Decisioni dell'ultima tranche:

- quattro dei nove record pubblicati ma non idonei sono stati verificati sul facsimile e ammessi alla rotazione generica;
- il proverbio sulla luna seduta resta fuori dall'Almanacco finche l'app non possiede il dato sull'orientamento apparente della falce;
- tre associazioni a date fisse prive di fonte esatta sono state rimosse dal calendario;
- le nove varianti duplicate della vecchia coda sono state risolte: sette escluse e due promosse dopo revisione IT/FUR;
- `No je mai stade ploie che il bon timp nol sedi tornât` entra nella rotazione generica;
- `Nadal in cjase e Pasche in place, o viceversa` resta vincolato alla Pasqua mobile e non puo comparire fuori ricorrenza.
- la coda residua di 54 candidati e' chiusa: 15 promossi, 29 destinati all'archivio e 10 varianti non selezionate;
- nessun candidato resta in `needs_context` o `hold`;
- Venerdi Santo, Pasqua e Ascensione usano offset dalla Pasqua; Canicola e mesais usano intervalli espliciti;
- San Ruperto e Sant'Egidio aggiungono due date fisse verificate;
- il detto su marzo, aprile e maggio entra nella rotazione dei tre mesi, senza occupare da solo l'intera primavera.
- il quinto lotto del volume 1876 aggiunge 15 proverbi verificati e revisionati IT/FUR;
- `Un flôr nol fâs primevere` e' limitato alla primavera; gli altri 14 nuovi testi sono generali;
- il divario verso 366 proverbi distinti idonei e' ora di 198.

Gli audit puntuali sono conservati in:

- `scripts/data/ostermann-proverbs-1876/published-noneligible-review.json`;
- `scripts/data/ostermann-proverbs-1876/legacy-candidate-variant-resolution-batch-01.json`;
- `scripts/data/ostermann-proverbs-1876/legacy-candidate-finalization-batch-02.json`.

## Aggiornamento corrente 2026-07-22 - volume completo 1876

E' stato acquisito ed estratto il facsimile completo di *Proverbi friulani raccolti dalla viva voce del popolo* di Valentino Ostermann, Udine 1876, dalla Biblioteca Digitale Friulana delle Teche di Udine.

| Blocco | Quantita | Stato |
| --- | ---: | --- |
| Pagine PDF | 315 | Facsimile completo verificato |
| Pagine di contenuto estratte | 289 | PDF 19-307 |
| Righe sorgente OCR | 7.541 | Ricerca e confronto, non pubblicazione |
| Blocchi sorgente | 3.093 | Raggruppamento preliminare |
| Blocchi candidati | 2.875 | Grezzi, possono contenere varianti o piu detti |
| Priorita P1 | 282 | Candidati meteo, calendario, stagioni e altri segnali forti; l'estrazione grezza conteneva anche un'intestazione |
| Priorita P2 | 646 | Seconda coda editoriale |
| Proverbi gia pubblicati | 105 | Invariati |
| Proverbi gia idonei all'Almanacco | 96 | Invariati |

File di lavoro:

- `scripts/data/ostermann-proverbs-1876/source.json` conserva fonte, hash e regola editoriale;
- `master-pages.jsonl` conserva OCR e testo PDF pagina per pagina;
- `source-lines.csv` conserva tutte le righe con pagina e sezione;
- `source-blocks.csv` prepara la scrematura per priorita senza dichiarare automaticamente che ogni blocco sia un proverbio.

Decisione: l'estrazione completa e' conclusa, ma non equivale alla promozione dei 261 nuovi proverbi richiesti. La review parte dai 282 candidati P1; varianti, spiegazioni, testi offensivi o OCR incerto vengono separati o esclusi. Solo i testi scelti passano a normalizzazione FUR, resa IT e assegnazione editoriale al calendario.

La coda P1/P2 risultante contiene 914 blocchi:

| Esito preliminare | Quantita | Significato |
| --- | ---: | --- |
| Nuovo candidato da recensire | 812 | Nessuna somiglianza forte rilevata |
| Da dividere o contestualizzare | 40 | Blocco con piu varianti o spiegazione |
| Possibile record gia presente | 37 | Confronto manuale necessario |
| Probabile record gia presente | 17 | Evitare una seconda traduzione/promozione |
| Revisione delicata | 8 | Tono o contenuto storico non adatto automaticamente alla app |

La somiglianza serve soltanto a ordinare la review: non elimina record e non decide la pubblicazione.

### Review volume completo - lotto 1

Il primo lotto verificato direttamente sul facsimile e registrato in `scripts/data/ostermann-proverbs-1876/review-decisions-batch-01.json`.

| Decisione | Quantita | Stato |
| --- | ---: | --- |
| Passano alla revisione linguistica | 10 | Testo fonte verificato; ancora fuori da UI e calendario |
| Richiedono contesto o chiarimento linguistico | 4 | Nessuna traduzione o promozione automatica |
| Variante secondaria | 1 | Conservata senza duplicare il proverbio principale |
| Pubblicati dal lotto | 0 | `publish: false` per tutti i record |

Il lotto separa inoltre singoli proverbi da blocchi OCR che contenevano piu detti. La resa FUR normalizzata viene affrontata solo dopo la conferma editoriale della selezione.

Il secondo lotto, registrato in `review-decisions-batch-02.json`, aggiunge 15 decisioni verificate sul facsimile: 12 passano alla revisione linguistica e 3 richiedono contesto o chiarimento. Include anche proverbi generali su lavoro, agricoltura e natura, ammessi nel repertorio quotidiano senza fingere un legame locale o una data che la fonte non contiene.

Questa sezione sostituisce, per lo stato attuale, le valutazioni storiche del 4 luglio che limitavano il lavoro alle sole pagine mirate gia individuate.

## Aggiornamento corrente 2026-07-20

| Blocco | Quantita | Stato |
| --- | ---: | --- |
| Proverbi pubblicati | 105 | 66 `lab_ready`, 39 `draft` |
| Proverbi selezionabili nell'Almanacco | 96 | `almanacEligible` |
| Date fisse | 32 | Calendario puntuale + fallback |
| Candidati estratti | 122 | Archivio di lavoro, non pubblicazione automatica |
| Date note con candidati | 43 | Il repertorio resta una rotazione, non 366 testi datati |
| Pagine del piano fonte Ostermann | 42/42 | Piano chiuso |

La Home non mostra il proverbio completo. Il vecchio campo `homeEligible`, citato nelle sezioni storiche qui sotto, e stato rinominato `almanacEligible`.

## Stato rilevato il 2026-07-04

| Blocco | Quantita | Stato |
| --- | ---: | --- |
| Proverbi pubblicati in `proverbs.json` | 91 | Archivio app esistente con 52 record `lab_ready` e 39 `draft` |
| Proverbi usabili in home/almanacco | 82 | `homeEligible` |
| Date fisse in `schedule.json` | 21 | Calendario puntuale minimo ampliato |
| Candidati in `proverbCandidates.json` | 111 | Non pubblicati automaticamente |
| Candidati gia recensiti | 111 | Review editoriale preliminare completa |
| Candidati ancora da recensire | 0 | Nessun candidato della coda P1/P2 resta senza decisione |
| Candidati consigliati/promuovibili dopo review | 57 | 52 gia promossi tecnicamente come `lab_ready`, 5 pendenti |
| Pagine fonte Ostermann candidate | 40 | 40 chiuse: 37 candidati proverbio + 3 Scopri/contesto |
| Pagine gia estratte come candidati | 37 | `candidate_extracted` |
| Pagine chiuse come Scopri/contesto | 3 | `discover_backlog_extracted`, gia recuperate dalla vecchia app |
| Pagine fonte ancora da estrarre | 0 | Nessuna pagina P1/P2 della coda resta `to_extract` |
| Pagine ancora solo backlog Discover | 0 | Backlog P1/P2 individuato completato |

## Quanto resta da estrarre da Ostermann

Risposta operativa:

- per il piano Almanacco gia individuato: **0 pagine** restano da estrarre;
- per i candidati gia creati: restano **0 candidati** da recensire nella coda attuale;
- per il corpus Ostermann completo: esistono **751 pagine OCR**, di cui **737** non vuote/minime, ma questo e archivio grezzo, non una coda da importare tutta.

Quindi il lavoro immediato non e estrarre ancora a tappeto. Il lavoro corretto e:

1. trattare solo i 5 pendenti rimasti, senza forzare in UI record lunari, meteo o datati incerti;
2. usare i testi piu lunghi come materiale Scopri/archivio, con spiegazione editoriale;
3. aprire una seconda campagna Ostermann solo se dopo la review resta un gap reale, partendo da temi e date, non da scraping sequenziale.

## Matrice repertorio 2026-07-04

La matrice e calcolata da `getProverbRepertoireMatrix`, non scritta a mano.
Serve a distinguere repertorio pubblicato, candidati grezzi, date effettive e gap reale.

| Blocco | Quantita | Nota |
| --- | ---: | --- |
| Proverbi pubblicati | 91 | 82 `homeEligible`; 52 `lab_ready` con review umana ancora richiesta |
| Candidati grezzi | 111 | 97 `source_checked`, 14 ancora `candidate` |
| Repertorio di lavoro complessivo | 202 | Pubblicati + candidati, non tutti pubblicabili |
| Target archivio editoriale | 500 | Mancano 298 record anche contando i candidati |
| Date fisse in schedule | 21 | Mancano 345 slot per calendario 366 |
| Date note includendo candidati | 34 | Mancano 332 date distinte anche contando i candidati |
| Pagine Ostermann del piano fonte | 40/40 | 37 `candidate_extracted`, 3 `discover_backlog_extracted` |

Distribuzione dei candidati grezzi:

| Coda stimata | Quantita |
| --- | ---: |
| Databili | 37 |
| Date mobili | 4 |
| Segni meteo | 53 |
| Stagionali | 17 |

Conclusione: il problema non e solo promuovere i candidati esistenti. Anche se li usassimo tutti, restiamo lontani sia dai 366 giorni sia dal target prudente di 500 record verificati.

## Review candidati 2026-07-04, batch 1

Il primo batch dei candidati rimasti ha chiuso 20 record:

- 9 candidati promuovibili ma ancora pendenti, non pubblicati;
- 3 candidati legati a date fisse: Sant'Antonio, San Mattia, San Gregorio;
- 3 candidati segni meteo: nebbia bassa, nubi a scalini, rana/pioggia;
- 1 candidato mensile per agosto;
- 1 candidato stagionale sul cuculo;
- 1 candidato ciclo lunare;
- feste mobili e varianti lasciate fuori dalla promozione;
- parafrasi senza forma FUR pronta spostate verso Scopri/archivio.

Decisione importante: i proverbi di Venerdi Santo e Ascensione restano `needs_context` finche' non esiste un calendario mobile. La variante San Vincenzo/San Lorenzo resta `variant_choose_one` per evitare duplicazioni con San Lorenzo gia promosso.

## Review candidati 2026-07-04, batch finale

Il batch finale ha chiuso i 37 record residui:

- 12 nuovi candidati promuovibili ma ancora pendenti;
- 3 candidati legati a date fisse: San Paolo, San Marco e Santa Lucia;
- 4 candidati mensili/stagionali;
- 4 candidati segni meteo;
- 1 candidato ciclo lunare;
- 25 record lasciati fuori dalla promozione per contesto, variante, tono narrativo, prosa lunga o uso piu adatto a Scopri.

Decisione importante: la coda di review Almanacco e chiusa. Nessun record nuovo entra automaticamente in `proverbs.json`, `schedule.json` o UI: i pendenti richiedono ancora review FUR finale e promozione controllata.

## Candidati promossi dopo review preliminare

Questi sono il primo bacino concreto gia promosso in `proverbs.json` come `lab_ready`.
Restano marcati `humanReviewRequired`, quindi non equivalgono a certificazione linguistica finale:

| ID | Tipo intervento |
| --- | --- |
| `ostermann-103-umiditat-glazze` | Sostituisce record esistente sporco/meno fondato |
| `ostermann-103-parsore-nul-seren` | Nuovo proverbio |
| `ostermann-103-bon-timp-buine-int` | Nuovo proverbio |
| `ostermann-103-zornade-matine` | Nuovo proverbio |
| `ostermann-103-nul-lizer-sere` | Nuovo proverbio |
| `ostermann-105-lune-cercli` | Nuovo proverbio |
| `ostermann-105-lune-pelose` | Nuovo proverbio |
| `ostermann-190-san-josef-biel` | Nuovo proverbio/databile |
| `ostermann-190-plois-marz-brosiz-avril` | Nuovo proverbio stagionale |
| `ostermann-190-avril-plojos` | Nuovo proverbio stagionale |
| `ostermann-190-avril-bagnat` | Nuovo proverbio stagionale |
| `ostermann-190-mai-jugn-pan-vin` | Nuovo proverbio stagionale |
| `ostermann-190-pluv-avost` | Nuovo proverbio stagionale |

## Nuovo giro fonte Ostermann 2026-07-04

Le pagine normalizzate disponibili sono 751. Il primo piano da 28 pagine e' stato esaurito, ma non basta per coprire un Almanacco giornaliero robusto.
La nuova coda non pubblica nulla in app: prepara solo le prossime pagine da leggere, estrarre, verificare e classificare.

| Pagina PDF | Priorita | Tema | Uso previsto |
| ---: | --- | --- | --- |
| 29 | P1 | Canicola e andamento stagionale | Detti su canicola, pioggia, asciutto e segni estivi; evitare duplicati astronomici. |
| 31 | P1 | Orione, gennaio e Canicola | Proverbio carnico sulle stelle di gennaio e segni stagionali. |
| 43 | P1 | Luna di settembre | Pronostici lunari stagionali, da verificare per varianti e resa FUR. |
| 44 | P2 | Luna e lavori agricoli | Materiale agricolo-lunare, forse piu' Scopri che proverbio quotidiano. |
| 46 | P2 | Luna e consuetudini domestiche | Credenze lunari quotidiane, da usare solo se il testo resta leggibile e non superstizioso. |
| 58 | P1 | Stagioni e santi d'inverno | Avvio sezione proverbi stagionali con San Paolo e San Sebastiano. |
| 68 | P1 | Fumo, presagi e Midili | Due proverbi sul fumo e presagi d'annata, con forte identita locale. |
| 83 | P2 | Natale e fuoco rituale | Materiale natalizio da distinguere fra proverbio, tradizione e pillola Scopri. |
| 87 | P2 | Calendario liturgico e detti | Detti su feste mobili e calendario rituale. |
| 100 | P1 | Nubi e pronostici | Pagina ponte sui segni delle nubi; scartare credenze lunghe. |
| 111 | P2 | Pioggia, nozze e grandine | Materiale delicato, da valutare soprattutto per Scopri. |
| 146 | P1 | Aloni lunari e tempo | Proverbi brevi su cerchi lunari, pioggia vicina/lontana e vento. |

Prima tranche estratta:

| Pagina PDF | Candidati aggiunti | Nota |
| ---: | ---: | --- |
| 29 | 1 | Canicola e andamento stagionale; variante contraddittoria lasciata fuori. |
| 31 | 1 | Orione/Macis di gennaio; utile come ponte fra Almanacco e Scopri. |
| 58 | 1 | San Paolo del 10 gennaio; candidato databile. |
| 146 | 1 | Aloni lunari e pioggia vicina/lontana; collegabile alla spiegazione Scopri sugli aloni. |

Seconda tranche estratta:

| Pagina PDF | Candidati aggiunti | Nota |
| ---: | ---: | --- |
| 43 | 1 | Luna di settembre; il testo lungo resta materiale Scopri. |
| 68 | 2 | Proverbi del fumo del Midili; locali/rituali, da tenere con contesto. |
| 83 | 1 | Detto del giovedi; pagina non presente nel catalogo estratti precedente. |
| 87 | 2 | Formule calendario Santa Lucia/Natale. |
| 100 | 1 | Proverbio breve sulle nubi; il resto resta spiegazione Scopri/meteo popolare. |

Chiusura coda Scopri/contesto:

| Pagina PDF | Candidati aggiunti | Esito |
| ---: | ---: | --- |
| 44 | 0 | Gia recuperata come `ost-extract-044-luna-lavori-campi`; resta Scopri/consigli terra, FUR non pronto. |
| 46 | 0 | Gia recuperata come `ost-extract-046-luna-uccelli-bucato`; ha FUR breve nel record curato, ma resta archivio/Scopri. |
| 111 | 0 | Gia recuperata come `ost-extract-111-uccelli-marini-pioggia`; FUR approvato nel record curato, ponte Scopri/meteo popolare. |

Regola:

- le pagine non ancora lavorate restano `to_extract`;
- le pagine gia recuperate come materiale Scopri ma non proverbiali passano a `discover_backlog_extracted`;
- i record estratti passano in `proverbCandidates.json`, non in UI;
- non entrano in `proverbs.json`;
- non diventano `homeEligible`;
- ogni proverbio estratto dovra' poi passare da fonte, normalizzazione FUR, resa IT, tag, data/rotazione e review.

## Pagine Ostermann da lavorare dopo i candidati gia estratti

Le pagine seguenti sono gia nel piano fonte e hanno priorita alta. Non sono ancora proverbi pubblicabili: vanno estratte, normalizzate, tradotte, datate/taggate e revisionate.

| Pagina PDF | Tema | Uso previsto |
| ---: | --- | --- |
| 59 | Candelora e inverno | Batch candidato estratto il 2026-07-03 |
| 60 | Santi estivi e vendemmie | Batch candidato estratto il 2026-07-03 |
| 61 | Calende, santi e inverno | Batch candidato estratto il 2026-07-03 |
| 63 | San Giovanni e Sant'Egidio | Batch candidato estratto il 2026-07-03 |
| 94 | Lessico dei venti | Batch candidato estratto il 2026-07-03 |
| 96 | Vento delle Palme | Batch candidato estratto il 2026-07-03 |
| 97 | Vento, aloni, neve e pioggia | Batch candidato estratto il 2026-07-03 |
| 99 | Nebbia e pronostici | Batch candidato estratto il 2026-07-03 |
| 101 | Sole rosso e nebbia | Batch candidato estratto il 2026-07-03 |
| 102 | Colore della luna | Batch candidato estratto il 2026-07-03 |
| 104 | Monti col cappello, rane, vacche | Batch candidato estratto il 2026-07-03 |
| 126 | Temporali e grandine | Batch candidato estratto il 2026-07-03 |
| 130 | Neve e abbondanza | Batch candidato estratto il 2026-07-03 |
| 131 | Vespe e neve | Batch candidato estratto il 2026-07-03 |
| 132 | Neve, brina e valanghe | Batch candidato estratto il 2026-07-03 |
| 140 | Arcobaleno e annata | Batch candidato estratto il 2026-07-03 |
| 141 | Arcobaleno e tempo | Batch candidato estratto il 2026-07-03 |
| 189 | Annata, pioggia e gennaio | Batch candidato estratto il 2026-07-03 |
| 192 | Vigna, santi e vendemmia | Batch candidato estratto il 2026-07-03 |
| 608 | San Giorgio e San Barnaba | Batch candidato estratto il 2026-07-03 |
| 609 | Sant'Ermacora e bufere | Batch candidato estratto il 2026-07-03 |
| 674 | Giochi di neve e slitte | Batch candidato estratto il 2026-07-03 |

## Metodo di reperimento

### Batch estrazione 2026-07-03

Pagine lavorate:

| Pagina PDF | Candidati aggiunti | Nota |
| ---: | ---: | --- |
| 97 | 2 | Proverbi su vento e rugiade; righe OCR rovinate escluse. |
| 102 | 4 | Due proverbi FUR sul cuculo e due pronostici lunari italiani tenuti come `candidate`, non promuovibili. |
| 99 | 3 | Proverbi brevi su nebbia e pioggia; nota diaristica di Del Negro esclusa dal batch. |
| 104 | 5 | Proverbi su monti, nubi e rane; righe OCR rovinate escluse. |
| 59 | 3 | Venerdi Santo e Ascensione; varianti contraddittorie tenute con note. |
| 60 | 4 | Santi estivi, vendemmia e segni dei monti in agosto. |
| 61 | 4 | Santi autunnali, ingresso dell'inverno e foglie tardive. |
| 63 | 3 | San Zuan, Sant'Egidio e relazione ottobre/febbraio; parti OCR rotte escluse. |
| 94 | 1 | Lessico dei venti quasi tutto archiviabile; un solo detto su pioggia lunga estratto. |
| 96 | 3 | Garbino, bora e arie rosse; materiale folklorico su vento escluso. |
| 101 | 1 | Solo il proverbio del gallo fuori orario; rosso/nebbia gia coperti altrove. |
| 126 | 5 | Grandine e temporali; credenze narrative su lampi/demoni escluse dal batch. |
| 130 | 1 | Proverbio neve/pioggia/raccolto; desideri e formule lunghe esclusi. |
| 131 | 3 | Neve e calendario; varianti incerte tenute con note di cautela. |
| 132 | 3 | Proverbi neve/pianura/Natale; materiale su valanghe e frasi oscure escluso. |
| 140 | 1 | Pronostico in prosa sui colori del primo arcobaleno di primavera, non proverbio FUR pubblicabile. |
| 141 | 2 | San Marco, arcobaleno e pioggia; canti e testi rituali esclusi. |
| 189 | 3 | Gennaio, febbraio, pioggia e granaio; varianti da decidere in revisione. |
| 192 | 3 | San Barnaba, Assunta, pioggia, sole e vendemmia. |
| 608 | 0 | Pagina lavorata ma non duplicata: nucleo San Barnaba gia estratto dalla pagina 192. |
| 609 | 1 | Sant'Ermacora come memoria meteo estiva; prosa culturale, non allerta. |
| 674 | 1 | Giochi di neve: candidato culturale per Scopri/pillola invernale. |

Regola applicata:

- i candidati FUR leggibili sono `source_checked`;
- i pronostici in italiano sono tenuti senza `fur` e restano `candidate`;
- nessun record nuovo e entrato in `proverbs.json`;
- nessun record nuovo e `homeEligible`;
- le pagine 97 e 102 passano a `candidate_extracted`.

### Fase 1 - Promozione controllata dei candidati esistenti

1. Prendere i 13 candidati consigliati per promozione.
2. Verificare testo contro pagina pulita/PDF.
3. Normalizzare grafia FUR.
4. Scrivere/validare resa IT.
5. Aggiungere fonte pagina.
6. Assegnare tag, mese/stagione o data.
7. Promuovere in `proverbs.json`.
8. Aggiornare `schedule.json` solo se il proverbio e realmente databile.

Stato 2026-07-03:

- prima tranche completata: 13 candidati promossi come `lab_ready`;
- `proverbs.json` passa da 48 a 52 record dopo la promozione dei 5 candidati residui gia recensiti;
- `homeEligible` passa da 39 a 43;
- nessuna modifica a `schedule.json`, perche i 5 record residui sono generici, mensili o stagionali e non slot giornalieri puntuali.

### Fase 1b - Routing dei candidati rimanenti

Dopo la promozione dei 13 candidati gia recensiti e la review dei batch pagina 54/60/61/192/126/130/104/49/96-97-99-102, restavano 46 candidati senza review editoriale completa.
La classificazione non pubblica nulla e non equivale a review linguistica:

| Coda | Quantita | Uso |
| --- | ---: | --- |
| Review Almanacco | 0 | Candidati `source_checked` con segnale positivo gia controllati in review preliminare. |
| Contesto o sospensione | 32 | Candidati interessanti ma con varianti, tono delicato, doppie date, contesto locale o nota necessaria. |
| Scopri/archivio | 14 | Record `candidate`, senza FUR pronto o in prosa: non sono proverbi quotidiani pubblicabili. |

Aggiornamento 2026-07-04:

- il primo batch dei candidati rimanenti ha chiuso 20 record;
- i candidati senza review editoriale completa passano da 57 a 37;
- la coda residua diventa: 2 in Review Almanacco, 23 in Contesto o sospensione, 12 in Scopri/archivio.
- il batch finale ha chiuso i 37 record residui;
- la coda residua diventa: 0 in Review Almanacco, 0 in Contesto o sospensione non decisionato, 0 in Scopri/archivio non decisionato.

Regola:

- nessun record rimanente entra in `proverbs.json`;
- nessun record rimanente diventa `homeEligible`;
- `Scopri` resta il contenitore naturale per prosa, curiosita e materiale contestuale;
- Almanacco puo pescare solo dalla coda Review dopo controllo umano.

Batch pagina 54 revisionato:

| ID | Esito |
| --- | --- |
| `ostermann-054-epifanie-fred` | Promuovibile dopo review finale FUR; data 06/01. |
| `ostermann-054-febrar-soreli` | Promuovibile come proverbio mensile/solare; resa di `agâr` da validare. |
| `ostermann-054-san-blas-fred` | Promuovibile dopo review finale FUR; data 03/02. |
| `ostermann-054-san-valantin-fin-inviar` | Promuovibile dopo review finale FUR; data 14/02. |

Batch pagina 60 revisionato:

| ID | Esito |
| --- | --- |
| `ostermann-060-sant-ane-furmiar` | Promuovibile dopo review finale FUR; data 26/07. |
| `ostermann-060-san-lurinz-seren` | Promuovibile dopo review finale FUR; data 10/08. |
| `ostermann-060-san-bortolomio-bon-timp` | Promuovibile dopo review finale FUR; data 24/08. |

Nota: `ostermann-060-avost-monz-fumin` resta fuori da questo batch perche richiede contesto e verifica lessicale sul tema dei monti fumanti.

Batch pagina 61 revisionato:

| ID | Esito |
| --- | --- |
| `ostermann-061-san-maurizi-seren` | Promuovibile dopo review finale FUR; data 22/09. |
| `ostermann-061-san-simon-unviar` | Promuovibile dopo review finale FUR; data 28/10. |
| `ostermann-061-fueis-tardis` | Promuovibile come proverbio autunnale, non come slot calendario. |

Nota: i record pagina 61 restano fuori da `proverbs.json` finche non viene fatta la promozione controllata.

Batch pagina 192 revisionato:

| ID | Esito |
| --- | --- |
| `ostermann-192-san-barnaba-vin` | Promuovibile dopo review finale FUR; data 11/06. |
| `ostermann-192-assunte-vin` | Promuovibile dopo review finale FUR; data 15/08. |

Nota: il record San Barnaba mantiene una cautela esplicita per l'OCR della data nella pagina fonte; l'aggancio calendario resta da confermare durante la promozione.

Batch pagina 126 revisionato:

| ID | Esito |
| --- | --- |
| `ostermann-126-tone-ploe-tempieste` | Promuovibile come proverbio stagionale temporalesco, non come slot calendario. |
| `ostermann-126-mai-tempieste` | Promuovibile come proverbio mensile di maggio, non come giorno fisso. |

Nota: gli altri record temporaleschi pagina 126 restano fuori per contesto, tono o cautela editoriale gia tracciata.

Batch pagina 130 revisionato:

| ID | Esito |
| --- | --- |
| `ostermann-130-sot-nev-pan` | Promuovibile come proverbio invernale, non come slot calendario. |

Nota: la pagina 130 ha layout OCR disturbato, ma il nucleo proverbiale e confermato dalla pagina clean e dal record candidate.

Batch pagina 104 revisionato:

| ID | Esito |
| --- | --- |
| `ostermann-104-monts-chapiel` | Promuovibile come segno meteo visuale, non come slot calendario. |
| `ostermann-104-cil-lane` | Promuovibile come segno meteo quotidiano, non come slot calendario. |

Nota: i record pagina 104 con riferimento locale specifico o traduzione meno stabile restano fuori da questa review.

Batch pagina 49 revisionato:

| ID | Esito |
| --- | --- |
| `ostermann-049-prin-martars-lune-pluv` | Promuovibile come proverbio lunare/ciclo lunare, non come slot calendario. |
| `ostermann-049-lune-brume` | Promuovibile come proverbio mensile di novembre, non come giorno fisso. |

Nota: gli altri record lunari pagina 49 restano fuori per tono, spiegazione o oscurita editoriale gia tracciata.

Batch finale coda Review Almanacco revisionato:

| ID | Esito |
| --- | --- |
| `ostermann-096-garbin-timp` | Promuovibile come segno meteo/vento, non come slot calendario. |
| `ostermann-097-rosadis-marz-bueris-avril` | Promuovibile come proverbio mensile marzo-aprile, non come giorno fisso. |
| `ostermann-099-tre-fumatis-ploe` | Promuovibile come segno meteo autunnale/invernale, non come slot calendario. |
| `ostermann-102-cuch-ploe-sut` | Promuovibile come proverbio primaverile, non come slot calendario. |

Nota: la coda `Review Almanacco` e chiusa. Restano da trattare separatamente i record `Contesto o sospensione` e `Scopri/archivio`.

### Fase 1c - Piano di promozione controllata

La coda `Review Almanacco` primaria e chiusa, ma non tutti i 57 candidati promuovibili vanno trattati allo stesso modo.
Il piano di promozione separa cio che e gia stato pubblicato in laboratorio da cio che deve ancora entrare in `proverbs.json` e, solo se datato, in `schedule.json`.

| Gruppo | Quantita | Azione |
| --- | ---: | --- |
| Gia pubblicati in laboratorio | 52 | Presenti in `proverbs.json`; non duplicare. |
| Date fisse pendenti | 1 | San Grivor resta sospeso: la data nel testo OCR/fonte non e abbastanza pulita per lo schedule. |
| Mensili pendenti | 0 | Coda mensile promossa in `proverbs.json`; resta fuori dallo schedule fisso. |
| Stagionali pendenti | 0 | Coda stagionale promossa in `proverbs.json`; resta fuori dallo schedule fisso. |
| Segni meteo pendenti | 3 | Restano fuori dalla UI automatica: richiedono segnale non disponibile o contesto Scopri. |
| Ciclo lunare pendente | 1 | Resta fuori finche' non esiste un segnale dati sugli aloni lunari. |

Guardrail introdotti:

- nessuna pubblicazione automatica;
- i 5 candidati pendenti restano fuori dalla UI finche' non passano da review FUR finale e aggiornamento controllato;
- solo i record `almanac_dated` con `dateAnchors` possono diventare slot giornalieri;
- i record mensili, stagionali, lunari e segni meteo restano fuori dallo schedule fisso.

### Fase 1d - Promozione controllata dei record datati

I 10 record `almanac_dated` sono stati promossi in `proverbs.json` come contenuti `lab_ready`, con `humanReviewRequired: true`, e agganciati a `schedule.json`.
La promozione resta di laboratorio: i testi sono tracciati, fonte-controllati e usabili nel flusso Almanacco, ma non equivalgono a certificazione linguistica finale.

| Data | ID |
| --- | --- |
| 01-06 | `ostermann-054-epifanie-fred` |
| 02-03 | `ostermann-054-san-blas-fred` |
| 02-14 | `ostermann-054-san-valantin-fin-inviar` |
| 06-11 | `ostermann-192-san-barnaba-vin` |
| 07-26 | `ostermann-060-sant-ane-furmiar` |
| 08-10 | `ostermann-060-san-lurinz-seren` |
| 08-15 | `ostermann-192-assunte-vin` |
| 08-24 | `ostermann-060-san-bortolomio-bon-timp` |
| 09-22 | `ostermann-061-san-maurizi-seren` |
| 10-28 | `ostermann-061-san-simon-unviar` |

Risultato:

- `proverbs.json`: 52 -> 62 record;
- `homeEligible`: 43 -> 53 record;
- `lab_ready`: 13 -> 23 record;
- `humanReviewRequired`: 13 -> 23 record;
- date fisse in `schedule.json`: 6 -> 16.

Restano fuori:

- 4 candidati mensili;
- 4 candidati stagionali;
- 4 candidati segni meteo;
- 1 candidato ciclo lunare;
- code `Contesto o sospensione` e `Scopri/archivio`.

### Fase 1e - Promozione controllata dei nuovi record datati sicuri

Dopo la chiusura della review completa, 5 record datati sono stati promossi in `proverbs.json` come contenuti `lab_ready`, con `humanReviewRequired: true`, e agganciati a `schedule.json`.
Il candidato San Grivor/San Gregorio resta fuori: il proverbio e interessante, ma la data nel testo OCR/fonte non e abbastanza pulita per fissarlo nello schedule.

| Data | ID |
| --- | --- |
| 01-10 | `ostermann-058-san-pauli-scur` |
| 01-17 | `ostermann-054-sant-antoni-fred` |
| 02-24 | `ostermann-054-san-matie-glace` |
| 04-25 | `ostermann-141-arch-san-march-doman` |
| 12-13 | `ostermann-087-sante-luzie-nadal` |

Risultato:

- `proverbs.json`: 75 -> 80 record;
- `homeEligible`: 66 -> 71 record;
- `lab_ready`: 36 -> 41 record;
- `humanReviewRequired`: 36 -> 41 record;
- date fisse in `schedule.json`: 16 -> 21.

Restano fuori dalla UI:

- 1 candidato datato con fonte/data da ricontrollare;
- 5 candidati mensili;
- 1 candidato stagionale;
- 7 candidati segni meteo;
- 2 candidati ciclo lunare.

### Fase 1f - Promozione controllata dei record mensili/stagionali

Dopo la promozione dei record datati sicuri, i 6 record mensili/stagionali gia fonte-controllati sono stati promossi in `proverbs.json` come contenuti `lab_ready`, con `humanReviewRequired: true`.
Non sono stati agganciati a `schedule.json`: sono contenuti di rotazione mensile/stagionale, non proverbi di giorno fisso.

| Rotazione | ID |
| --- | --- |
| Gennaio | `ostermann-189-sut-zenar-granar` |
| Febbraio | `ostermann-189-ploe-febrar-ledamar` |
| Marzo/Maggio | `ostermann-131-tons-marz-nev-mai` |
| Agosto | `ostermann-060-avost-monz-fumin` |
| Settembre | `ostermann-043-lune-setembar-siet` |
| Primavera | `ostermann-102-cuch-montagne` |

Risultato:

- `proverbs.json`: 80 -> 86 record;
- `homeEligible`: 71 -> 77 record;
- `lab_ready`: 41 -> 47 record;
- `humanReviewRequired`: 41 -> 47 record;
- date fisse in `schedule.json`: ferme a 21.

Restano fuori dalla UI:

- 1 candidato datato con fonte/data da ricontrollare;
- 3 candidati segni meteo;
- 1 candidato ciclo lunare.

### Fase 1g - Promozione controllata dei segni meteo/lunari app-readable

Dopo la promozione mensile/stagionale, 5 record sono stati promossi in `proverbs.json` come contenuti `lab_ready`, con `humanReviewRequired: true`.
Non sono stati agganciati a `schedule.json`: entrano solo quando il modello Almanacco riceve un aggancio coerente da meteo o luna.

| Aggancio | ID |
| --- | --- |
| Primo martedi di lunazione | `ostermann-049-prin-martars-va-lune` |
| Nebbia | `ostermann-099-fumate-basse` |
| Nubi/pioggia | `ostermann-104-nul-schialins` |
| Bora/vento | `ostermann-096-buere-dispari` |
| Nubi/pioggia | `ostermann-100-nul-plovi` |

Risultato:

- `proverbs.json`: 86 -> 91 record;
- `homeEligible`: 77 -> 82 record;
- `lab_ready`: 47 -> 52 record;
- `humanReviewRequired`: 47 -> 52 record;
- date fisse in `schedule.json`: ferme a 21.

Correzione tecnica associata:

- la finestra di rotazione dei segni meteo passa da 4 a 6 record, cosi' i nuovi proverbi meteo non restano irraggiungibili quando piu' segnali condividono gli stessi tag.

Restano fuori dalla UI automatica:

- `ostermann-097-san-grivor-vint`: data/fonte da ricontrollare prima dello schedule;
- `ostermann-104-rane-ploe`: segnale animale non leggibile dai dati app;
- `ostermann-096-arie-rosse`: segnale cielo rosso non disponibile nei dati app;
- `ostermann-101-gial-dopo-miesdi`: segnale animale non leggibile dai dati app;
- `ostermann-146-cercli-lune-ploe`: alone lunare non disponibile nei dati app, adatto a Scopri/contesto.

### Fase 2 - Estrazione dalle pagine P1 gia individuate

1. Backlog `discover_backlog_extracted` completato per le pagine P1/P2 gia individuate.
2. Estrarre solo frasi adatte a proverbio giornaliero.
3. Scartare materiale troppo lungo, oscuro o solo archivistico.
4. Inserire i nuovi record in `proverbCandidates.json`, non direttamente in `proverbs.json`.
5. Aggiornare `proverbCandidateReview.json` con raccomandazione editoriale.

### Fase 3 - Fonti esterne solo dopo Ostermann

Se Ostermann non basta:

1. Cercare solo fonti con stato chiaro: pubblico dominio, licenza aperta o autorizzazione.
2. Registrare sempre fonte, pagina/link, licenza/stato d'uso.
3. Non copiare raccolte moderne protette.
4. Usare fonti moderne solo come bibliografia o traccia, non come testo copiabile.

## Regole anti-rumore

- Non usare proverbi senza fonte.
- Non usare proverbi lunghi come card principale: spostarli in Scopri o pillola spiegata.
- Non usare candidati `archive_only` o varianti non selezionate nell'Almanacco quotidiano.
- Non pubblicare FUR in stato incerto come se fosse approvato.
- Non forzare 365 giorni con duplicati mascherati.

## Obiettivo realistico

| Fase | Target |
| --- | ---: |
| Archivio minimo affidabile | 60-80 proverbi |
| Copertura stagionale buona | 120-150 proverbi |
| Calendario annuale editoriale | 366 slot assegnati |
| Archivio robusto per rotazione pluriennale | 500 proverbi verificati |

## Decisione

Il prossimo lavoro non e cercare genericamente sul web.

La fonte primaria iniziale e stata trasformata in candidati, ma il repertorio resta insufficiente. La nuova coda Ostermann 2026-07-04 riapre l'estrazione in modo tracciato: prima lettura pagina per pagina, poi candidati, poi review. Le prime due tranche hanno aggiunto 11 candidati grezzi; le 3 pagine residue sono state chiuse come materiale Scopri/contesto gia recuperato. Nessun testo nuovo entra in UI senza passare da promozione e revisione.

### Review del volume completo 1876 - lotti 1, 2, 3, 4 e 5

La revisione diretta del facsimile completo ha prodotto cinque lotti editoriali separati:

- 75 record verificati su 64 blocchi sorgente;
- 64 candidati sottoposti a revisione linguistica IT/FUR;
- 4 candidati che richiedono una spiegazione di contesto;
- 5 candidati che richiedono un chiarimento linguistico;
- 2 varianti secondarie da non usare come proverbio autonomo;
- 51 proverbi approvati e promossi nell'Almanacco;
- 5 contenuti approvati per Scopri;
- 4 contenuti sospesi per una condizione runtime non ancora disponibile;
- 1 accorpamento e 3 esclusioni editoriali.

I file da `review-decisions-batch-01.json` a `review-decisions-batch-05.json` conservano testo originale, pagina, proposta italiana e decisione editoriale. Il controllo automatico si esegue con `python scripts/validate-ostermann-1876-review-decisions.py`.
