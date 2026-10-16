# Barcolana 2026 — integrazione sul ramo di audit

L'organizzatore [Barcolana](https://www.barcolana.it/it/calendario-eventi)
e' la fonte primaria della scheda «Barcolana 2026». Una sola scheda in lista
mostra gli appuntamenti dalla data corrente in avanti in un programma scorrevole,
ordinato per data e ora. La sua immagine e
l'anteprima testuale vengono dalla
[notizia ufficiale dell'edizione 58](https://www.barcolana.it/it/news/2026/barcolana58-presented-by-generali-tutto-pronto-per-la-grande-regata).
La scheda mette in primo piano **2–11 ottobre**, il periodo principale;
il catalogo conserva separatamente le anticipazioni, il 12 ottobre e la
premiazione del 29 novembre. Dopo l'11 ottobre, se resta solo la premiazione,
la data visibile segue il prossimo appuntamento, prima il 12 ottobre e poi
il 29 novembre. A Trieste la scheda di programma ha
la priorita' locale gia' prevista dall'interfaccia.

## Acquisizione e gate

Il job legge l'HTML completo pubblicato dalla fonte dati del calendario,
la sitemap XML e la notizia ufficiale. Non legge PDF e non scarica immagini.
La prova live del 7 ottobre ha impiegato **5,88 secondi** e ha riconciliato:

- **680 righe** con ID distinti nel calendario, su 15 date del 2026;
- **671 appuntamenti ufficiali** dopo la rimozione di otto copie identiche
  e di una nona copia dello stesso spettacolo alle 16:00 del 10 ottobre,
  pubblicata come «Palco Cavana» e «Palco Piazza Cavana»;
- **681 URL** di eventi 2026 nella sitemap, con una pagina eccedente
  [in HTTP 404](https://www.barcolana.it/it/eventi/terra/2026/concerto-dei-ragazzi-del-collegio-del-mondo-unito-dell-adriatico);
- **231 link diretti** a dettagli, assegnati soltanto quando titolo e slug
  sono univoci su entrambe le superfici. Le altre righe puntano al calendario
  ufficiale, per evitare abbinamenti ipotetici.

Il 7 ottobre la risposta dell'app per Trieste mostra **453 appuntamenti dal
giorno corrente in avanti** nella scheda. I record dei giorni trascorsi rimangono nel catalogo della
fonte per il controllo di completezza, senza appesantire l'anteprima.

Il gate richiede l'edizione 2026, la presenza delle date principali, conteggi
coerenti fra righe, appuntamenti e duplicati, sitemap pari alle righe piu'
l'unica pagina 404 nota, immagine e testo della notizia 2026, e nessuna
regressione maggiore del 10% rispetto al ciclo precedente. Un cambio della
pagina orfana o un nuovo scarto tra calendario e sitemap blocca la fonte.
Questo e' un controllo di inventario per conteggi e corrispondenze univoche:
le restanti pagine dettaglio non vengono lette singolarmente nel job.

Le **43 righe senza luogo** restano senza luogo nella lista scorrevole;
Trieste e' il comune della scheda del festival, non la sede inventata di
ogni appuntamento. La cerimonia della Nave Vespucci non mostra un orario:
il calendario codifica 16:00, mentre la
[notizia ufficiale](https://www.barcolana.it/it/news/2026/nave-amerigo-vespucci-e-il-villaggio-in-italia-in-arrivo-a-trieste-per-la-conclusione-del-tour-mondiale-vespucci-campagna-in-nord-america-2026)
indica 16:30 per l'avvio del programma cittadino.

Il job legge anche sette pagine HTML strutturate di TurismoFVG legate al
festival: cinque programmi giornalieri in piazza, il calendario del Museo del
Mare e il programma di due talk. La prova live legge rispettivamente **41**,
**8** e **2** righe. Gli appuntamenti con data, titolo e ora gia' nel calendario
ufficiale non vengono ripetuti. Tre voci mancanti vengono aggiunte alla
scheda Barcolana, con link diretto alla pagina regionale: il
[concerto del Collegio del Mondo Unito](https://www.turismofvg.it/eventi/barcolana-58-eventi-in-piazza-505759)
dell'8 ottobre e i due talk del 9 e 10 ottobre. Il concerto corrisponde alla
pagina presente nella sitemap ufficiale ma attualmente in HTTP 404.
Per il concerto serbo ortodosso del 7 ottobre le fonti danno 19:30 e 19:00:
la scheda usa l'ora del calendario ufficiale e il gate riconosce solo questo
scarto revisionato; ulteriori scarti bloccano la fonte. Se una delle sette
pagine cambia identita' o non presenta piu' tutte le righe leggibili, la
fonte non passa il controllo. La raccolta live completa impiega **8,45
secondi**, entro il budget di 20 secondi. Non vengono letti PDF.

## Preferenza e doppioni

La scheda generale [TurismoFVG](https://www.turismofvg.it/eventi/58a-ed-barcolana)
viene sostituita dalla scheda ufficiale solo se coincidono edizione,
periodo e comune. Sei ulteriori URL regionali revisionati vengono assorbiti
solo quando il programma ufficiale contiene la corrispondente voce o un
appuntamento nel periodo verificato. Gli URL regionali restano nella
provenienza della scheda.

Nel confronto locale con lo snapshot TurismoFVG del 7 ottobre, le cinque
schede dei programmi giornalieri, il Museo del Mare, il programma talk e le
due schede dei singoli talk vengono assorbiti. Anche la scheda regionale
«Barcolana Ski» viene assorbita quando la scheda generale e' nel raggio; se
questa non e' visibile, resta la scheda locale per Aurisina. La distanza
della scheda generale segue quella locale quando assorbe un evento fuori
Trieste, cosi' la sua priorita' non peggiora.

Restano **sei schede regionali distinte**: lo stand di Monfalcone a Molo
Audace, Dense Floor, l'incontro con Marley e tre concerti a Muggia. I loro
appuntamenti non sono nel calendario ufficiale e non rappresentano copie
di una sua voce. Mantenerle come eventi autonomi conserva sede e priorita'
geografica senza inventare orari o ripetizioni nel programma ufficiale.

## Stato di rilascio

L'adattatore e' nel job comune a **15 fonti** sul ramo
`codex/events-discovery-audit`. Il tetto complessivo resta **875 secondi**:
Magazzino delle Idee passa da 35 a 30 secondi, MESS da 20 a 10 e
Galleria Spazzapan da 15 a 10, lasciando 20 secondi a Barcolana.
Le prove isolate precedenti delle tre fonti erano rispettivamente di
20,1, 3,2 e 2,5 secondi. Nel ciclo locale del 7 ottobre, durato
**618,29 secondi**, Barcolana e' `fresh` in **5,5 secondi** con una scheda
e zero revisioni; le tre fonti con budget ridotto sono `fresh` in 19,06,
3,55 e 2,72 secondi. **Dodici fonti su quindici** sono `fresh`. Il ciclo
non e' verde per tre motivi indipendenti da Barcolana:

- TurismoFVG e' andato in timeout nel limite di 360 secondi, usando il
  checkpoint annuale verificato precedente;
- Teatro Verdi Pordenone ha inserito nella paginazione un link con parametro
  pubblicitario `gclid`, che il suo lettore rifiuta come URL non affidabile;
- SagreFVG ha un nuovo record futuro della Festa del Borgo di San Leonardo
  senza provincia nel titolo; il gate lo ha fermato per revisione.

La prova locale non pubblica il catalogo. Alla data di quel primo test il
rilascio su `main` richiedeva la risoluzione di questi tre casi, il controllo
dell'intero job e la prova reale nell'app concordata con l'utente.

I tre casi sono stati risolti in seguito. Nel
[ciclo locale ripetuto delle 15 fonti](EVENTI_CICLO_15_FONTI_2026-10-07.md)
tutte le fonti sono `fresh`, senza revisioni, in 435,89 secondi;
Barcolana passa in 10,08 secondi con una scheda. Restano il primo ciclo
distribuito e la prova reale nell'app prima della promozione.

## Cambio delle pagine regionali l'8 ottobre

La pagina TurismoFVG del programma in piazza del **7 ottobre** ora risponde
404; le quattro pagine dei giorni **8–11 ottobre**, il Museo del Mare e i talk
rispondono 200. Il calendario ufficiale Barcolana resta leggibile con 680
righe, 671 appuntamenti distinti e nove doppioni esatti. La sitemap ufficiale
ha rimosso l'URL orfano gia' noto, mentre il programma regionale dell'8
ottobre pubblica ancora il relativo concerto.

L'adattatore legge i programmi regionali con giorno o fine periodo non ancora
trascorsi, verifica integralmente ognuno di essi e deriva dal giorno corrente
le attese del gate. Il concerto dell'8 ottobre resta l'unica aggiunta del
programma in piazza finche' quella pagina e' corrente; dal 9 ottobre non
viene piu' riproposto. Dopo l'11 ottobre l'adattatore non richiede piu' le
pagine regionali scadute, ma continua a verificare il calendario ufficiale,
che include anche un appuntamento del 29 novembre. Un test simula una pagina
passata in 404, il successivo cambio di giorno e una pagina futura mancante:
quest'ultima continua a fermare la fonte.

La lettura isolata live dell'8 ottobre passa il gate con quattro pagine in
piazza attive, 33 appuntamenti regionali, otto al museo e due talk. E' stata
combinata solo in un artefatto locale con le altre 14 fonti verificate: non e'
ancora una pubblicazione ne' un singolo ciclo completo dopo questa correzione.
Il job condiviso aveva prodotto 14/15 fonti `fresh` prima di questa correzione;
il catalogo locale combinato ne contiene 15/15. Il percorso di pubblicazione
alimentato con il catalogo locale, senza ripetere la scansione delle fonti, ha
superato i monitor Palazzo Attems, Pro Loco FVG, Anteprima Sagre e GiroFVG con
zero candidati nuovi. Nessun dato cloud o APK e' stato aggiornato.

L'[audit del ciclo unico dell'8 ottobre](EVENTI_CICLO_UNICO_15_FONTI_2026-10-08.md)
supera questa limitazione: il job reale ha prodotto 15/15 fonti `fresh` in una
sola esecuzione locale, dopo aver rimosso una voce duplicata di Barcolana Ski
con titolo tecnico errato pubblicato dal sito ufficiale.
