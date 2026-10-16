# Palazzo Attems Petzenstein — audit del 7 ottobre 2026

Stato: **non integrato come fonte di schede**, `source_complete=false`. Su
questo ramo il job e' configurato per eseguire un controllo diagnostico in sola
lettura dopo la raccolta delle 14 fonti attive; non e' ancora distribuito. Non
pubblica schede Palazzo Attems, non apre PDF o locandine e non usa OCR.

## Inventari confrontati

Il comando `python backend/tools/audit_palazzo_attems.py --as-of 2026-10-07`
legge gli elenchi pubblici, le API e i dettagli correnti. Esce con codice non
zero se una scheda resta irrisolta. Ha trovato:

| Superficie | Risultato |
| --- | ---: |
| [Pagina Eventi](https://palazzoattems.regione.fvg.it/it/events?_escaped_fragment_=) / [API Eventi](https://palazzoattems.regione.fvg.it/core/events/erpac_palazzoattems/it/) | 27 / 27; tre con periodo ancora attivo |
| [Categoria Evento](https://palazzoattems.regione.fvg.it/core/categories/erpac_palazzoattems/it/15308/) | 25; cinque esclusive sono del 2024–2025, mentre sette voci API non hanno quella categoria |
| [Categoria Mostra](https://palazzoattems.regione.fvg.it/core/categories/erpac_palazzoattems/it/13463/) | 11 schede storiche, nessuna aggiornata nel 2026 |
| [Mostre concluse](https://palazzoattems.regione.fvg.it/core/categories/erpac_palazzoattems/it/14035/) | 15 |
| Homepage corrente | Una mostra in evidenza, Italia Settanta |
| [Categoria Notizia](https://palazzoattems.regione.fvg.it/core/categories/erpac_palazzoattems/it/15309/) | 154 articoli, 41 pubblicati nel 2026 |

Le 41 notizie 2026 sono state confrontate con ID e versione `modified`. Una
notizia nuova o cambiata rende l'audit incompleto fino a nuova revisione. La
scheda API senza data strutturata, [Domenica al museo](https://palazzoattems.regione.fvg.it/it/prima-domenica-del-mese-174327),
indica nel dettaglio il 4 ottobre 2026: era gia' passata alla data dell'audit.

## Schede utilizzabili e blocchi

- [Italia Settanta](https://palazzoattems.regione.fvg.it/it/italia-settanta-165450): la homepage rimanda alla scheda, che prova Palazzo Attems Petzenstein a Gorizia e il periodo 27 giugno–29 novembre 2026. L'API dettaglio non ha `preview_image`; l'evento e' gia' presente nella fonte TurismoFVG con immagine e anteprima.
- [Visite guidate](https://palazzoattems.regione.fvg.it/it/visite-guidate-gratuite-173302): la scheda nomina Palazzo Attems e pubblica in testo i giorni di ottobre e novembre, fino al 29 novembre. Sarebbe un programma raggruppato distinto dalla mostra, con anteprima ricavabile dal testo.
- [Sguardi social sui '70](https://palazzoattems.regione.fvg.it/it/eventi-collaterali-di-ottobre-174333): l'8 ottobre alle 19 e' provato, ma nel dettaglio ufficiale non compare una sede testuale e il campo descrizione contiene un testo riciclato sul DJ set del 25 settembre. La [scheda TurismoFVG di ottobre](https://www.turismofvg.it/eventi/italia-settanta-la-creativita-come-antidoto-arte-moda-design-eventi-collaterali-505824) include l'incontro e indica Gorizia/Palazzo per il riepilogo, ma nello stesso testo include esplicitamente anche due appuntamenti a Gradisca. Serve una riconciliazione per appuntamento prima di assegnare la sede.
- [Eventi collaterali di ottobre](https://palazzoattems.regione.fvg.it/it/eventi-collaterali-di-ottobre-174290): periodo 1–15 ottobre; nomina sia Palazzo Attems sia Galleria Spazzapan e pubblica il calendario dettagliato solo come immagine. TurismoFVG lo trascrive in testo: 1, 8 e 15 ottobre nel contesto di Gorizia; il 10 e il 14 identifica esplicitamente la Galleria Spazzapan a Gradisca. Le schede ufficiali Spazzapan del 10 e 14 sono gia' nel job. La scheda regionale di riepilogo e' gia' nel catalogo: aggiungerne una copia da Palazzo creerebbe ridondanza.
- [Comunicazione di annullamento](https://palazzoattems.regione.fvg.it/it/evento-annullato-174454): pubblicata il 7 ottobre nella categoria Notizia, annulla l'evento dedicato a Michelangelo Pistoletto previsto per l'11 ottobre. Non e' una riga separata nell'API Eventi; il controllo la segnala per evitare che un programma ricavato dalla locandina la ripubblichi.

## Decisione

Palazzo Attems non entra ancora tra le fonti `fresh`: i due record attivi
irrisolti e l'annullamento richiedono un calendario testuale riconciliato per
data e comune. Il codice del job controlla l'inventario e le versioni
delle schede esaminate; una novita', un cambio o l'impossibilita' di leggerli
rende il job non riuscito e richiede revisione. Le lacune note restano tracciate
senza bloccare ogni esecuzione. La prossima
integrazione dovra' rappresentare una sola volta il programma regionale e le
schede dirette, mantenendo preferenza per la scheda migliore; le prove sul
telefono restano rinviate come richiesto.

Il catalogo regionale distingue ora le due schede omonime con titoli di
anteprima diversi: **visite guidate e iniziative** (settembre–novembre) ed
**eventi di ottobre** (1–15 ottobre). Sono due programmi con contenuti e
periodi diversi, non due copie della stessa scheda; la mostra rimane una terza
scheda distinta. L'assegnazione automatica del titolo richiede URL, periodo e
sede gia' verificati, e decade se quei dati cambiano. Non crea nuove schede
Palazzo né considera l'11 ottobre annullato come incontro.
