# Teatro Verdi Trieste: lettura XML, 15 novembre 2026

## Problema osservato

La corsa ordinaria di `meteofriul-events-refresh` del 15 novembre si è
interrotta con `XML or text declaration not at start of entity: line 2,
column 0` per Teatro Verdi Trieste. I log riportano lo stesso errore dal
10 al 15 novembre. Una lettura HTTP in sola lettura del 15 novembre ha
confermato che sia `sitemap_index.xml` sia
`spettacoli-sitemap.xml` rispondono 200 e iniziano con una riga vuota
prima della dichiarazione XML.

## Correzione nel ramo

Il lettore elimina soltanto BOM e spazi iniziali prima di analizzare le due
sitemap. Rimangono attivi i limiti di dimensione, la verifica degli URL,
della struttura e del calendario. Un prefisso non composto da spazi continua
a fallire.

## Verifica

- 77 test mirati Eventi superati e `compileall` del lettore superato.
- Lettura completa della fonte ufficiale in locale, senza scritture: 59
  eventi raccolti, zero schede in revisione, gate di fonte `ok`.
- Confronto con il lotto online precedente di 61 eventi: gate `ok`.

Il job cloud e il catalogo online non sono stati modificati. La prova locale
non certifica una futura corsa pianificata né la pubblicazione dei 59 eventi.
