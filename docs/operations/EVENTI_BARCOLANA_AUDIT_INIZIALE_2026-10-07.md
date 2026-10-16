# Barcolana — audit iniziale del 7 ottobre 2026

Aggiornamento: l'adattatore e il gate sono stati aggiunti sul ramo di audit.
La verifica di integrazione e i limiti aggiornati sono descritti nel
[seguito dell'audit](EVENTI_BARCOLANA_INTEGRAZIONE_2026-10-07.md).
I paragrafi seguenti conservano lo stato rilevato prima dell'integrazione.

## Decisione e forma della scheda

[Barcolana](https://www.barcolana.it/it/calendario-eventi) entra nel registro
delle fonti da integrare. L'utente ha scelto **una sola scheda dell'edizione**
con programma scorrevole, come per Pordenonelegge. Il sito ufficiale pubblica
un calendario strutturato sufficiente per costruirla, ma l'adattatore e il
controllo automatico non sono ancora nel job. Non creare centinaia di tessere
individuali nella lista Eventi.

## Inventario pubblico verificato

- La pagina iniziale del calendario carica le righe con la fonte dati pubblica
  `Eventi`. La risposta completa, ottenuta con il filtro che usa il sito
  (`search=1&_ds=0:Eventi&_cids=0:i1g43`), contiene **680 righe** con ID
  distinti. Le date coprono **15 giorni** dal 25 settembre al 29 novembre
  2026; 675 righe sono fra il 1° e l'11 ottobre, tre a settembre, una il
  12 ottobre e una premiazione il 29 novembre. Il filtro del giorno 8 ottobre restituisce
  **85 righe**, esattamente quante ne compaiono nella risposta completa.
- La [sitemap ufficiale](https://www.barcolana.it/sitemap-index.xml) espone
  2.645 URL, di cui **681** nel percorso delle schede `it/eventi/.../2026/`:
  514 Terra, 107 senza categoria nel percorso, 58 Mare, due Sea Summit.
  L'URL eccedente della
  [pagina «Concerto dei ragazzi del Collegio del Mondo Unito»](https://www.barcolana.it/it/eventi/terra/2026/concerto-dei-ragazzi-del-collegio-del-mondo-unito-dell-adriatico)
  restituisce HTTP 404 e non ha una riga nel calendario. La differenza
  numerica non autorizza a ignorare altri futuri scostamenti: il job dovra'
  confrontare inventario, pagine valide e calendario a ogni edizione.
- Le 680 righe contengono 326 titoli distinti; alcuni eventi, mostre e
  iscrizioni compaiono in piu' giornate. **43 righe non dichiarano un luogo**.
  Otto coppie hanno gli stessi titolo, data, luogo e orario; vanno
  riconciliate prima di produrre la lista scorrevole. L'ID del calendario
  resta la prova che le righe pubbliche sono 680.
- Il sito annuncia la manifestazione principale
  [dal 2 all'11 ottobre 2026](https://www.barcolana.it/it/news/2026/barcolana58-presented-by-generali-tutto-pronto-per-la-grande-regata).
  Il calendario include tre righe di anticipazione a settembre e la premiazione del
  29 novembre. Queste date vanno distinte dal periodo principale nella
  scheda, senza trasformare l'intero intervallo in giorni di apertura.

## Dati e doppioni

La [notizia ufficiale sulla Nave Vespucci](https://www.barcolana.it/it/news/2026/nave-amerigo-vespucci-e-il-villaggio-in-italia-in-arrivo-a-trieste-per-la-conclusione-del-tour-mondiale-vespucci-campagna-in-nord-america-2026)
conferma sosta e visite a Trieste **dall'8 al 12 ottobre**. Il calendario
Barcolana ha la cerimonia di chiusura del tour e l'inaugurazione del
Villaggio IN Italia l'8 ottobre, ma non rappresenta in quelle righe tutte
le giornate di visita: l'anteprima del programma dovra' riportare anche il
rinvio alla notizia ufficiale, senza inventare orari.
La riga della cerimonia nel calendario codifica le **16:00** locali, mentre
la notizia indica l'avvio del programma cittadino alle **16:30**. Prima di
mostrare un orario per quella voce occorre riconciliare i due testi; la
scheda unica puo' comunque indicare l'intervallo provato 8-12 ottobre.

TurismoFVG ha gia' la scheda generale
[«58a Ed. Barcolana.»](https://www.turismofvg.it/eventi/58a-ed-barcolana)
dal 2 all'11 ottobre a Trieste e altre schede di singoli appuntamenti.
L'integrazione deve fondere la scheda generale con quella dell'organizzatore
e confrontare le altre pagine regionali una per una: nessun doppione in
lista e nessun appuntamento scartato solo perche' cita «Barcolana» nel titolo.

La [notizia dell'edizione 2026](https://www.barcolana.it/it/news/2026/barcolana58-presented-by-generali-tutto-pronto-per-la-grande-regata)
e la notizia Vespucci offrono un testo descrittivo e un'immagine `og:image`
ufficiali. Le schede evento possono avere testo ma non immagine. Titolo
HTML e descrizioni social generiche del calendario riportano ancora
«Barcolana 57»; l'edizione va provata dal programma e dalla notizia
2026, non da quei metadati.

## Lavoro aperto prima della pubblicazione

1. Parsing del calendario completo con riconciliazione contro la sitemap,
   controllo di ID, date e modifiche, senza PDF o immagini scaricate.
2. Verifica delle otto coppie omonime, delle 43 righe prive di luogo e
   dell'orario discordante della cerimonia Vespucci;
   calendario e dettaglio devono fornire sedi corrette, senza assegnare
   automaticamente Trieste alle sedi di altri comuni.
3. Una sola scheda Barcolana 2026 con programma ordinato, periodo principale
   distinto dalle anticipazioni e dalla premiazione; descrizione e immagine
   della notizia ufficiale corrente.
4. Riconciliazione con TurismoFVG, compresa la scheda generale e la Nave
   Vespucci. Test del gate della fonte, della deduplica e della proiezione
   della scheda prima di registrare l'adattatore nel job.

L'audit e' sul ramo `codex/events-discovery-audit`; Barcolana non e' ancora
nel catalogo del job online e non e' dichiarata fonte completa.
