# Audit della rotazione editoriale di Scopri

Data dell'audit: 21 agosto 2026.

## Contratto applicato

La selezione conserva questo ordine: data esatta, festivita mobile, intervallo preciso,
mese o stagione, patrimonio generale. Le date esatte e le festivita mobili non vengono
mai sostituite da contenuti generici. In caso di piu contenuti certi per la stessa data,
la scelta ruota in modo deterministico tra gli anni.

Gli intervalli restano prevalenti per due giorni su tre, ma lasciano spazio al materiale
stagionale o generale per evitare che una sola card occupi la rubrica per settimane.
Mese e stagione si alternano invece con il patrimonio generale. La rubrica Riti e
credenze non usa questo riempimento: compare soltanto con data, festivita o intervallo
documentato e puo quindi restare assente.

## Simulazione di 366 giorni

La simulazione programmatica usa il 2028, anno bisestile, e il profilo territoriale di
Pordenone. Il calendario completo e generato da
`frontend/src/features/discover/discoverEditorialCalendarAudit.js` e verificato dai test.

| Rubrica | Copertura | Materiale usato | Ripetizione consecutiva massima |
| --- | ---: | ---: | ---: |
| Memoria del giorno | 366/366 giorni | 366 memorie principali | 1 giorno |
| Riti e credenze | 35/366 giorni | 11 schede nel 2028 | 6 giorni, per le *mesais* |
| Si diceva che... | 366/366 giorni | 30 detti su 30 | 1 giorno |
| Archivio e tradizioni | 366/366 giorni | 25 schede | 2 giorni |

Nel catalogo esistono inoltre 196 memorie secondarie approvate distribuite su 145 date;
la loro presenza effettiva dipende dalla localita attiva.

Non risultano collisioni tra le card visibili e nessuna ricorrenza esatta viene persa.
San Barnaba (11 giugno) e Sant'Ermacora (12 luglio) non vengono ripetuti in Archivio,
perche lo stesso contenuto e gia mostrato quel giorno come Memoria del giorno.

## Materiale locale verificato

- Ostermann culturale: 63 schede totali.
- Riti e credenze da Ostermann: 14 schede, di cui 10 calendarizzabili e 4 ancora
  legate al meteo.
- Riti istituzionali approvati: 5 schede su 5, tutte calendarizzabili e con copy
  IT/FUR controllata. Il catalogo completo di Scopri sale quindi a 68 schede e la
  rubrica rituale a 19 schede, di cui 15 calendarizzabili.
- Archivio e tradizioni: 49 schede, di cui 27 calendarizzabili e 22 legate al meteo.
- Proverbi: 379 record grezzi, 369 idonei per l'Almanacco e 279 con revisione IT/FUR
  approvata.
- Si diceva che...: 11 schede dedicate piu 19 riusi controllati dell'Almanacco, per un
  totale di 30. Il testo rimane in `proverbs.json`, evitando copie divergenti.

Il riuso tra Almanacco e Scopri e intenzionale: l'Almanacco anticipa il proverbio nella
scheda quotidiana; Scopri lo ripropone come patrimonio linguistico. Non e considerato
un doppione tra card della stessa vista.

## Registro delle lacune editoriali

Il registro verificabile si trova in
`frontend/src/data/discover/editorialExpansionBacklog.json`. Non viene letto dalla UI:
serve a non dimenticare il materiale mancante e viene confrontato con i cataloghi dai
test automatici.

| Rubrica | Stato attuale | Lacuna o lavoro futuro |
| --- | --- | --- |
| Conosci la localita | 215 profili e 407 tappe | Copertura completa: 0 Comuni senza tappe; 100 con una, 38 con due e 77 con tre. In futuro ampliare con priorita i profili che hanno ancora una sola tappa. |
| Memoria del giorno | 366 date coperte, 196 memorie secondarie | Nessuna lacuna di copertura. Integrare soltanto nuove memorie documentate e pertinenti. |
| Riti e credenze | 19 schede, 15 calendarizzabili | Ampliare con fonti su Rogazioni, cicli agricoli, vendemmia, Avvento e riti patronali; 4 schede restano separate perche dipendono dal meteo. |
| Si diceva che... | 30 detti, tutti usati ogni anno | Nessun giorno vuoto. Nuovi detti servono in futuro solo ad aumentare la varieta pluriennale. |
| Archivio e tradizioni | 49 schede, 27 calendarizzabili | Materiale sufficiente; 22 schede attendono un contesto meteo affidabile e non sono una lacuna di copy. |

Per “Si diceva che...” la simulazione viene ora ripetuta anche dal 2026 al 2031: in
ogni anno usa tutti i 30 detti, non lascia giorni vuoti e non ripete lo stesso contenuto
per due giorni consecutivi.

## Ricerca rituale approvata

I cinque candidati documentati sono stati approvati e promossi nel catalogo separato
`frontend/src/data/discover/institutionalRituals.json`. Il file di ricerca
`frontend/src/data/discover/ritualResearchBacklog.json` resta come tracciato dell'audit,
ma non viene letto direttamente dalla UI.

- Le cidulis restano legate a Cercivento e al 24 giugno.
- Le maschere del Carnevale confrontano soltanto Carnia, Andreis e Grimacco.
- Il Pust resta una pratica esclusivamente resiana e conserva i termini della fonte.
- Le craceles restano legate ad Andreis e al Friuli occidentale negli ultimi tre giorni
  della Settimana Santa.
- I doni invernali sono una scheda comparativa proposta nelle principali date di
  dicembre: dichiara esplicitamente che le figure cambiano secondo l'area e non le
  presenta come un unico rito regionale.

La simulazione 2028 usa tutte e cinque le nuove schede. Nessuna resta approvata ma
oscurata dalla rotazione; il periodo dei doni non produce una ripetizione continua di
venti giorni.

## Audit conclusivo dei profili comunali

L'audit finale copre tutti i 215 profili del registro comunale FVG e le 407 tappe
pubblicate. I 201 nuovi record provengono da nove lotti di ricerca, revisione FUR e
promozione separati per provincia e area.

- 215 identificativi profilo e 215 codici ISTAT univoci.
- 407 identificativi tappa univoci; nessun duplicato testuale esatto rilevato.
- Nessun profilo privo di tappe: 100 ne hanno una, 38 ne hanno due e 77 ne hanno tre.
- Titolo, sintesi e testo di ogni tappa sono presenti sia in italiano sia in friulano;
  non risultano coppie IT/FUR accidentalmente identiche o revisioni FUR in attesa.
- Tutti gli anni e gli intervalli numerici sono coerenti e ordinati.
- I nove lotti conservano 133 esclusioni motivate, 35 conflitti tra fonti e 25
  candidati gia pubblicati esclusi come duplicati. I conflitti non sono stati risolti
  implicitamente nel runtime: la decisione resta tracciata nei file di ricerca.
- Le 201 promozioni coincidono esattamente tra ricerca, revisione FUR, manifesti di
  promozione e profili visibili.
- Sono stati controllati 167 indirizzi di fonte distinti. Quattro URL istituzionali
  obsoleti sono stati sostituiti con i rispettivi indirizzi canonici del Catasto
  speleologico regionale e di eBiblio ISTAT; tutte le fonti risultano raggiungibili o
  verificate direttamente.

La verifica automatica resta parte dei test: blocca profili mancanti, chiavi duplicate,
tappe incomplete, fonti non ammesse e divergenze tra ricerca, revisione e pubblicazione.

## Lavoro successivo

1. Ampliare progressivamente le tappe storiche dei Comuni che hanno ancora un solo
   record, senza superare il limite editoriale di tre tappe per profilo.
2. Cercare nuovi riti soltanto in fonti istituzionali, archivistiche o bibliografiche
   verificabili e senza generalizzare le varianti locali.
3. Valutare separatamente le 26 schede legate al meteo (4 riti e 22 d'archivio), quando
   Scopri ricevera un contesto meteorologico affidabile.
4. Ampliare in futuro detti e archivio, ma senza necessita immediata: la rotazione corrente e
   gia completa e non presenta intervalli editoriali lunghi.
5. Rieseguire l'audit di 366 giorni a ogni modifica di date, rubriche o cataloghi.
