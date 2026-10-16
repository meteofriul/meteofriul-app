# Eventi: revisione dei monitor Palazzo Attems e GiroFVG, 11 ottobre 2026

## Incidente osservato

L'esecuzione cloud `meteofriul-events-refresh-6cfjc` ha pubblicato il catalogo
`1791733990670117`: tutte le 15 fonti sono `fresh`, compresa Paesi in Festa
con 22 schede. Il job e' uscito con codice non zero **dopo** la pubblicazione,
perche' i monitor diagnostici Palazzo Attems e GiroFVG hanno individuato
inventario mutato. Il catalogo dell'API e' rimasto `complete`.

Questo comportamento e' il canale di allerta esistente per contenuti nuovi o
modificati dei monitor. La revisione seguente aggiorna soltanto le prove
puntuali; le modifiche future devono continuare a richiedere revisione.

## Palazzo Attems

L'[API Eventi](https://palazzoattems.regione.fvg.it/core/events/erpac_palazzoattems/it/)
ha aggiunto l'ID `619247`, 15 ottobre 2026 alle 18:00,
"I protagonisti della musica negli anni Settanta con Mister Fantasy". La
[scheda ufficiale](https://palazzoattems.regione.fvg.it/it/eventi-collaterali-di-ottobre-174560)
e la notizia `233853` rimandano allo stesso contenuto. Il testo diretto non
specifica la sede e il campo strutturato della sede e' vuoto. La
[scheda TurismoFVG degli eventi collaterali](https://www.turismofvg.it/eventi/italia-settanta-la-creativita-come-antidoto-arte-moda-design-eventi-collaterali-505824)
include gia' l'appuntamento del 15 ottobre, indica Palazzo Attems Petzenstein
a Gorizia ed e' presente nel catalogo pubblico come programma unico fino al
15 ottobre. Una seconda scheda Attems produrrebbe un doppione e avrebbe una
sede non provata dal suo dettaglio.

Sono state revisionate esattamente le versioni dell'evento `619247`, della
notizia `233853` modificata il `2026-10-09T12:03:31` e del dettaglio `174560`
modificato il `2026-10-09T12:04:24`. Gli altri tre blocchi noti restano tracciati:
assenza della sede nel testo di una scheda, programma multisede solo in
immagine e comunicazione di annullamento da riconciliare. Palazzo Attems
rimane un monitor, `source_complete=false`.

## GiroFVG

La sitemap ha cambiato soltanto due articoli di categoria:

- [Cinema Muto 2026](https://www.girofvg.com/le-giornate-del-cinema-muto-2026),
  `lastmod=2026-10-09T14:48:33Z`. Il testo menziona la replica dell'11 ottobre
  alle 16:30; il [sito ufficiale](https://www.giornatedelcinemamuto.it/calendario-111026/)
  e il catalogo della fonte dedicata riportano gia' la sessione dell'11
  ottobre alle 16:30.
- [Barcolana 2026](https://www.girofvg.com/barcolana-trieste-regata-2026),
  `lastmod=2026-10-11T09:32:02Z`. L'aggiornamento aggiunge un risultato della
  regata e riprende il programma. Il catalogo della fonte ufficiale Barcolana
  include gia' l'11 ottobre e 672 sessioni nel programma.

Sono stati aggiornati solo i due `lastmod` revisionati nella baseline. La
pagina storica `fiere-e-mostre?start=168` continua a restituire HTTP 500:
il monitor legge 89 pagine su 90 e rimane `source_complete=false`. GiroFVG
non pubblica schede proprie, per evitare date editoriali e duplicati.

## Verifiche

- 37 test mirati di audit, watch e pubblicazione cloud superati.
- 666 test pilot complessivi superati, uno ignorato; sette test Attems
  superati separatamente.
- Audit reale Palazzo Attems: 28 record API, `changes=[]`, tre blocchi noti.
- Monitor reale GiroFVG: 90 pagine attese, 89 lette,
  `source_complete=false`, `changes=[]`.
