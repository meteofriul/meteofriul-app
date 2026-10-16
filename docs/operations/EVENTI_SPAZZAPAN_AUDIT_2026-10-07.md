# Galleria Spazzapan: audit e integrazione del 7 ottobre 2026

## Inventari ufficiali

Il sito espone superfici diverse, che il job legge e confronta a ogni ciclo:
[API Eventi](https://galleriaspazzapan.regione.fvg.it/core/events/erpac_spazzapan/it/)
(3 record), [categoria Eventi](https://galleriaspazzapan.regione.fvg.it/core/categories/erpac_spazzapan/it/14038/)
(2), [Mostra in corso](https://galleriaspazzapan.regione.fvg.it/core/categories/erpac_spazzapan/it/16101/)
(4), [Mostra](https://galleriaspazzapan.regione.fvg.it/core/categories/erpac_spazzapan/it/13346/)
(7) e [Notizia](https://galleriaspazzapan.regione.fvg.it/core/categories/erpac_spazzapan/it/15922/)
(77). La [categoria plurale](https://galleriaspazzapan.regione.fvg.it/core/categories/erpac_spazzapan/it/16102/)
ha un solo record del 2024, da trattare come storico. Il primo audit la
descriveva come vuota: era un errore.

Le notizie pubblicate nel 2026 sono 43; 44 articoli risultano modificati
nel 2026, incluso uno pubblicato nel 2025. Le notizie correnti sono state
esaminate per eventi, repliche, avvisi e progetti. Il controllo automatico
confronta ID e data di modifica delle 43 notizie correnti. Una nuova notizia
o una modifica ferma la fonte per riesame: il job non ignora nuovi candidati
senza prova di data e sede.

## Schede risultanti

Al 7 ottobre le quattro schede distinte ancora attive sono:

| Scheda | Periodo | Prova e scelta |
| --- | --- | --- |
| [FVG70.02 – Nuovi modelli di ricerca](https://galleriaspazzapan.regione.fvg.it/it/fvg7002-eventi-collaterali-di-ottobre-172985) | 23 luglio–29 novembre 2026 | Il modulo mostra nel dettaglio specifica date, Galleria a Gradisca d'Isonzo, descrizione e immagine. La pagina di mostra espone solo un rinvio breve. |
| [FVG70.03 – Sergio Pausig](https://galleriaspazzapan.regione.fvg.it/it/fvg7003-sergio-pausig-173388) | 11 settembre–11 ottobre 2026 | Testo del dettaglio e modulo Eventi concordano su data e sede. Una sola scheda per la mostra, senza replicare la voce dell'API Eventi. |
| [Mario Palli / Studio Visit](https://galleriaspazzapan.regione.fvg.it/it/giornata-del-contemporaneo-2026-75485) | 10 ottobre 2026 | La visita e' nello studio dell'artista a Gradisca d'Isonzo; la Galleria e' il punto di ritrovo. Indirizzo dello studio non pubblicato: precisione `municipality`. |
| [Nuovo paesaggio: una mostra da salvare](https://galleriaspazzapan.regione.fvg.it/it/eventi-collaterali-ottobre-174329) | 14 ottobre 2026 | Data, ora e sede sono pubblicate; la pagina contiene solo "a breve ulteriori dettagli". Immagine si', anteprima testuale no. |

Per FVG70.02 e FVG70.03, i campi strutturati di *Mostra in corso*
riportano il periodo del progetto generale (27 giugno 2026–15 gennaio 2027),
che non e' il periodo delle due mostre. Il job accetta quel valore solo come
anomalia nota e richiede l'intervallo proprio nei dettagli. Se il sito
corregge il campo strutturato, viene accettato solo quando coincide con il
periodo del dettaglio. Il [progetto FVG Settanta](https://galleriaspazzapan.regione.fvg.it/it/fvg-settanta-170166)
e' un riepilogo: non genera una quinta scheda. *Together/Insieme* non ha
periodo o programma definito e resta fuori da Eventi.

La scheda TurismoFVG di FVG70.02 era gia' nello snapshot annuale: il
confronto reale produce una sola card e conserva entrambi gli URL di
provenienza. Le altre tre schede non avevano un corrispondente nello stesso
snapshot. Le anteprime delle tre pagine con prose utilizzabili vengono
attribuite alla Galleria, senza copiare testi di servizio o promesse di
contenuti futuri.

## Gate e prova locale

Il gate verifica le identita' dei cinque inventari correnti, la categoria
storica, la presenza delle 43 notizie revisionate, i dettagli delle quattro
schede, i due progetti esclusi, date, comune, sede, immagini e attribuzione
delle anteprime. Una discordanza rende la fonte non pubblicabile e richiede
revisione; nuove edizioni o formati non vengono indovinati. Non si leggono
PDF o immagini di programma.

La prova isolata dell'adattatore ha prodotto 4 schede e zero revisioni in
3,2 secondi. La quota assegnata e' 15 secondi; con 14 fonti il budget
complessivo e' 875 secondi su 900 disponibili. Nessun dato e' stato
pubblicato sul catalogo cloud; le verifiche visive sul telefono restano
rinviate su richiesta dell'utente.

La suite automatica del blocco Eventi passa (602 test), inclusi i casi di
date strutturate discordanti, nuova notizia, anteprima non attribuibile,
doppione con TurismoFVG e mancato riuso di una fonte divenuta obsoleta.

Nel primo ciclo locale completo delle 14 fonti, durato 426,2 secondi,
**Galleria Spazzapan era `fresh`** con quattro record in 2,51 secondi e zero
revisioni. Teatro Verdi Trieste aveva invece segnalato `modified Teatro
Verdi Trieste show outside inventory`: la sitemap aveva aggiornato due
indici e una pagina inglese, fuori dall'inventario italiano. Dopo la
correzione separata del filtro, il **secondo ciclo e' durato 386,92 secondi**:
14 fonti su 14 `fresh`, nessun errore o URL in revisione. Spazzapan ha
prodotto quattro record in 2,47 secondi. Anche questa e' una prova locale con
checkpoint TurismoFVG gia' verificato; non sostituisce il primo ciclo
distribuito da catalogo vuoto.
