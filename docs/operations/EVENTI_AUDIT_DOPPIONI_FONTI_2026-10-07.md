# Eventi: controllo delle fonti e dei doppioni — 7 ottobre 2026

Ramo: `codex/events-discovery-audit`. Prova locale di sola lettura sulle dodici
fonti del job pilot; nessun catalogo è stato pubblicato. Le prove sul telefono
restano rinviate come richiesto.

## Copertura della raccolta

Le undici fonti diverse da TurismoFVG hanno prodotto 433 record, tutti con
`status=ok` e zero revisioni. Il controllo CSS Udine ha restituito 161 repliche:
nessuna anteprima vuota o contenente il testo della newsletter. Il controllo
SagreFVG ha restituito 28 eventi e zero revisioni. Pordenonelegge non ha date
future al 7 ottobre: un risultato vuoto verificato, non una fonte saltata.

La scansione annuale TurismoFVG ha letto 304 pagine di calendario, sitemap e
2.395 URL di dettaglio. Il checkpoint completo registra zero URL pendenti,
ambigui o in revisione. Il gate indipendente proietta 1.418 schede, di cui
1.308 con anteprima e 1.393 con immagine; `source_complete=true`. La nuova
lettura dell'indice pubblico, senza riusare la copia locale, ha trovato tre
URL aggiuntivi e li ha verificati prima di produrre questi conteggi. Il
checkpoint locale resta in `.dev-logs/events-duplicate-audit-2026-10-07`.

Sono stati corretti i casi incontrati nella scansione:

- Entità HTML e caratteri invisibili nell'URL e nel titolo di una scheda;
  l'URL reale rimane intatto, mentre il titolo viene normalizzato.
- La Mostra Mercato Regionale della Patata usa sei date discrete pubblicate
  nel dettaglio, non un intervallo quotidiano. L'ordine usa la prossima data.
- Tre dettagli in tedesco vengono riconciliati con data e comune del calendario.
  Per Barcolana 58 il periodo 2–11 ottobre è confermato anche
  dall'[organizzatore](https://www.barcolana.it/it/news/2026/barcolana58-presented-by-generali-tutto-pronto-per-la-grande-regata).
- Dieci pagine storiche senza anno nel dettaglio vengono escluse soltanto dopo
  la corrispondenza esatta con il calendario storico; la seconda pagina di
  «Radici nella pietra» viene unita al dettaglio corrente.

## Doppioni tra fonti

L'insieme dei dodici snapshot contiene 1.851 record. La riconciliazione locale
ne lascia 1.776 prima dei filtri per posizione e della proiezione dei programmi.
Conserva nella scheda scelta gli URL delle fonti accorpate e copia immagine o
anteprima soltanto con la provenienza verificata. I programmi completi di CSS
e dei due Teatro Verdi prevalgono sui brevi intervalli regionali quando titolo,
comune, teatro e copertura delle date concordano. Le sagre con stesso nome,
comune e periodo vengono unite alla scheda regionale. Titoli generici, sedi
diverse, orari distinti e periodi non corroborati rimangono separati.

La scheda [Le Radici del Vino 2026](https://www.leradicidelvino.com/s-projects-basic)
è una sola vicino a Rauscedo. Mostra l'anteprima della nona Fiera da Paesi in
Festa: il testo SagreFVG dell'ottava edizione era obsoleto. La preferenza
specifica vale solo per il periodo 9–11 ottobre 2026. Anche «Festa d'Autunno»
a Gonars appare una volta: il testo SagreFVG prova il 10 e l'11 ottobre, mentre
la data finale nell'API si fermava al 10. Per «Un giorno con Napoleone» la
[pagina Paesi in Festa](https://paesiinfesta.com/friuli-venezia-giulia/udine/campoformido/)
prova l'inaugurazione del 9 ottobre e conserva un'unica scheda 9–11 ottobre;
le due pagine TurismoFVG 10–11 sono riferimenti della stessa manifestazione.
Per la Festa delle Zucche di Cordenons la scheda TurismoFVG 18–25 ottobre
copre anche l'appuntamento preliminare del 18, presente nel
[programma Paesi in Festa](https://paesiinfesta.com/friuli-venezia-giulia/pordenone/sagra-di-cordenons-inverno/).

Il confronto per titolo, comune e date lascia 14 relazioni da non fondere:
tredici collegano le rassegne annuali «Dialoghi Open Lab» e «La scuola dello
sguardo #7» ai loro singoli incontri CSS; l'ultima collega il concerto
«Tisanota Fogherfest Biris & Blavars» del 9 ottobre alla festa Tisanota del
9–10 ottobre. Sono schede a granularità diversa, non due copie della medesima
sessione. Il confronto euristico è diagnostico; il job applica solo le regole
di identità provate e conserva gli altri casi per evitare fusioni scorrette.

## Verifica della consultazione

Una simulazione di `merge_collection` e `query_catalog` con gli snapshot delle
dodici fonti ha prodotto una sola scheda per Le Radici del Vino, Festa
d'Autunno a Gonars e Festa delle Zucche a Cordenons nelle ricerche attorno a
Rauscedo, Pordenone, Udine e Campoformido. Le quattro date di «Mrs Dalloway
#1» restano quattro repliche CSS distinte; l'intervallo TurismoFVG dello stesso
spettacolo non appare come quinta scheda.

Questa prova non verifica il primo ciclo del job distribuito né l'APK sul
telefono. Il gate della fonte continua a fermare una raccolta incompleta; il
confronto fra fonti si ripete automaticamente durante ogni consultazione.
