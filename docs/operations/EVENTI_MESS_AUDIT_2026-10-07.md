# MESS: audit e integrazione del 7 ottobre 2026

## Perimetro e fonti

L'adattatore legge il [programma di didattica museale](https://mess.regione.fvg.it/it/didattica-museale-171043),
l'[elenco dei musei](https://mess.regione.fvg.it/it/i-musei-del-mess-171271)
e la [categoria Notizie dai Musei](https://mess.regione.fvg.it/core/categories/erpac_mess/it/18221/)
tramite le rispettive API JSON pubbliche. Per le tre mostre attive controlla
anche i dettagli ufficiali TurismoFVG. Il job non apre PDF o locandine.

## Risultato della lettura

- Il programma dichiara 36 appuntamenti e contiene **36 righe datate**,
  distribuite in 18 musei con due laboratori ciascuno. Il 28 novembre era
  stato erroneamente contato come assente nel primo audit: il sito scrive
  `novenbre`. La correzione e' ammessa solo per il 28 novembre 2026.
- Al 7 ottobre restano 16 laboratori futuri. Sono associati ai rispettivi
  indirizzi e comuni e proiettati in 9 schede museo con sessioni ordinate e
  descrizione attribuita al programma MESS. Alcune coordinate della mappa
  portano a comuni diversi dagli indirizzi: si usano i comuni testuali e il
  punto rappresentativo del comune, dichiarando la precisione
  `municipality`.
- La categoria notizie contiene 51 articoli, 24 pubblicati nel 2026. Dopo
  lettura degli articoli correnti, le tre mostre con periodo attivo e sede
  verificati sono [Sulla soglia](https://mess.regione.fvg.it/it/not-173804),
  [Spiriti, amuleti e memorie ancestrali](https://mess.regione.fvg.it/it/not-173318/no-173328)
  e [Storie di erbe](https://mess.regione.fvg.it/it/not-169209). Le rispettive
  pagine TurismoFVG confermano anno, intervallo e comune. Le tre schede hanno
  immagine ufficiale e anteprima tratta dal testo MESS.
- *La bottega Giampaoli* riporta soltanto l'inizio e non un periodo o
  programma definito: viene esclusa secondo la regola editoriale concordata.
  Gli avvisi amministrativi e gli eventi passati non generano schede.

L'adattatore ha prodotto **19 record futuri o attivi** (16 laboratori e tre
mostre), zero revisioni. Le tre mostre si uniscono ciascuna alla rispettiva
scheda TurismoFVG. Il programma dei laboratori si unisce alle schede
regionali revisionate per sede, data e identita' esatta; il riepilogo
regionale multisede e' soppresso quando il programma diretto MESS e' presente.

## Controllo automatico e limiti

A ogni ciclo il gate richiede programma e anno leggibili, 36 righe, 18 musei,
due appuntamenti per museo, data/indirizzo/comune e descrizione di ogni
laboratorio. Per le notizie confronta i 24 articoli 2026 gia' revisionati
con gli ID e le modifiche correnti; per le tre mostre verifica anche le
schede TurismoFVG. Un nuovo articolo, un articolo modificato o un cambio di
edizione senza regola verificata fermano la fonte intera: serve allora
riesaminare il contenuto e aggiornare l'adattatore. Il gate evita omissioni
silenziose, ma non interpreta automaticamente un nuovo formato editoriale.

Il budget massimo del job per MESS e' 20 secondi, su 860 secondi complessivi
per 13 fonti e 900 secondi disponibili al job. La prova isolata di MESS e'
durata 3,2 secondi. Il **ciclo locale completo delle 13 fonti** e' durato
**383,32 secondi**: tutte le fonti sono `fresh`, senza errori; MESS ha
impiegato 3,53 secondi e ha prodotto 19 record, senza revisioni. La prova
usa un checkpoint TurismoFVG annuale gia' verificato e indici pubblici
aggiornati; non equivale ancora a una prova del job distribuito da catalogo
vuoto. I test automatici del blocco Eventi passano (594 test).

Non e' stata fatta alcuna pubblicazione sul catalogo cloud. Le prove
visive sul telefono restano rinviate su richiesta dell'utente.
