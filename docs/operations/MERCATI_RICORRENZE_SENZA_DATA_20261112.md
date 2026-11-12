# Mercati: ricorrenze senza prossima data — 12 novembre 2026

Controllate le 80 schede del catalogo candidato incorporato nell'app. Dopo la
correzione di AnticaMente, sei mercatini ricorrenti erano privi di una prossima
edizione datata. La cadenza abituale non è stata usata per inventare date.

| Scheda | Riscontro e trattamento nel candidato |
| --- | --- |
| M027, Cervignano | La [Pro Loco](https://www.prolococervignanofvg.it/comunicazione-importante-mercatino-dellusato-della-prima-domenica-del-mese/) conferma la ricorrenza e descrive l'orario, ma il suo avviso specifico riguarda novembre. Nessuna data futura aggiunta; orario dichiarato abituale. |
| M032, Gradisca | La [pagina UNPLI](https://prolocoregionefvg.it/eventi-delle-associate/mercatino-dellantiquariato/) trovata espone solo date storiche. Nessuna data futura aggiunta; orario indicativo dichiarato abituale. |
| M038, San Daniele | L'[agenda Pro San Daniele](https://www.infosandaniele.com/it/agenda/in-programma/mercatino-dell-antiquariato) pubblica **29 novembre 2026, 08:00–18:00** e Piazza Vittorio Emanuele II. Aggiunta l'edizione, corretti sede, indicazioni e link: il precedente link apriva il mercato settimanale. |
| M040, Udine Antiqua | La [scheda PromoTurismoFVG](https://www.turismofvg.it/events/udine-antiqua-494199) segnala possibili variazioni per altri eventi in piazza; non fornisce una prossima edizione esplicita. Nessuna data futura aggiunta. |
| M041, Vecchi Ricordi | La [scheda PromoTurismoFVG](https://www.turismofvg.it/eventi/vecchi-ricordi-474441) presenta la serie fino al 13 dicembre; compare anche [Vecchi Ricordi 2.0](https://www.turismofvg.it/eventi/vecchi-ricordi-2-0) con nome, organizzatore e cadenza parzialmente diversi. La singola edizione e l'identità corrente richiedono conferma dell'organizzatore prima di cambiare la scheda. |
| M042, Robis di une volte | [UNPLI FVG](https://prolocoregionefvg.it/eventi-delle-associate/robis-di-une-volte-4/) elenca espressamente **29 novembre e 13 dicembre 2026**. Aggiunte entrambe le edizioni e collegata la fonte che le riporta. |

Per ogni scheda senza futura edizione verificata l'app mostra «Prossima data non
annunciata» accanto alla cadenza, senza far apparire l'orario abituale come
programma confermato. Il candidato contiene 80 schede, 206 edizioni (anche
storiche) e 13 rimozioni. Il servizio pubblico Mercati resta alla revisione 0;
queste modifiche sono soltanto nei sorgenti dei rami app. Prima del rilascio
restano il confronto con il catalogo approvato e la prova su telefono.

Verifica: 58 test mirati Mercati, integrazione Eventi e catalogo, lint mirato e
build Web/service worker PASS. Un'asserzione di test sulla vecchia intestazione
del comune è stata aggiornata alla UI corrente.
Nel pilota locale su un'origine senza precedente cache sono stati osservati
Robis con le due date e Udine Antiqua con l'avviso senza data. Un'altra origine
di prova conservava una vecchia revisione del catalogo in cache: non è evidenza
del candidato aggiornato.

Il controllo dei mercati rimane editoriale e manuale. Il task Windows
`MeteoFriul-MarketsRefresh-Local` è disabilitato; `MeteoFriul-MarketsReminder-Local`
non è registrato. Il precedente task prevedeva una selezione settimanale di
appuntamenti e scadenze, ma aveva copertura parziale delle fonti e non
certificava tutte le schede. Prossimo controllo generale previsto nel pannello
il **7 febbraio 2027**, poi circa ogni tre mesi. Nessun job è stato creato o
riattivato in questo controllo.
