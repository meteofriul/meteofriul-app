# Mercati — controllo editoriale del 7 novembre 2026

## Decisione operativa

Mercati è un archivio di attività relativamente stabili. La ricerca iniziale e
l'inserimento sono una tantum; le correzioni si fanno dal pannello. Il prossimo
controllo manuale delle fonti compare il **7 febbraio 2027**, poi circa ogni tre
mesi. Il task Windows `MeteoFriul-MarketsRefresh-Local` risulta disabilitato;
quello per l'email non è registrato. La preferenza email è disattivata. Nessun
nuovo job è stato creato.

Il pannello usa il login Firebase esistente e il claim `marketsAdmin`. Il claim
è stato assegnato all'account del progetto, preservando gli altri permessi.
Il campo per la chiave locale è stato rimosso. Il servizio locale rifiuta
richieste amministrative anonime e continua a bloccare la pubblicazione.

## Archivio e selezione

Prima del controllo: 100 schede, 219 edizioni e 59 pratiche di ricerca
(13 più complete, 46 con verifiche residue); 34 schede erano selezionate per la
prossima pubblicazione. Il controllo tecnico precedente segnalava un solo
errore, pur lasciando nella selezione schede con fonti storiche o prive di date
future. Pertanto quel solo indicatore non rappresentava un'approvazione
editoriale aggiornata.

Dopo il controllo: **revisione amministrativa locale 15**, **16 schede
selezionate**, **37 sospese** e 47 bozze, tutte conservate nel pannello. Le
59 pratiche e le edizioni rimangono conservate. Le 37 erano già comprese nello
snapshot locale precedente: `status=draft` ne avrebbe mantenuto la vecchia
versione visibile; `status=suspended` ne prepara il ritiro alla prossima
pubblicazione. Non è
stata eseguita alcuna pubblicazione: **revisione pubblica 0**, 53 schede nello
snapshot preesistente. La selezione locale non equivale a una pubblicazione
online né aggiorna automaticamente app Web o Android.

### Schede selezionate

| Tipo | ID | Riscontro principale |
| --- | --- | --- |
| Ricorrenti, con pagina senza anno | M004, M006 | [Pro San Daniele](https://www.infosandaniele.com/it/turismo/manifestazioni/mercato-settimanale) indica il mercoledì; [Grado Turismo](https://grado.it/it/eventi/mercato-settimanale) indica sabato, 08:00–13:00 e Viale Italia. |
| Ricorrenti, Trieste | M021, M022, M023 | [Discover Trieste, mercati](https://www.discover-trieste.it/vivi/shopping/andar-per-mercatini) conferma Campagna Amica in piazza Vittorio Veneto il martedì e l'accesso pubblico al mercato ortofrutticolo; [Mercato coperto](https://www.discover-trieste.it/vivi/shopping/il-mercato-coperto) conferma indirizzo e orari. |
| Date pubblicate, Codroipo | M028, M053 | [UNPLI, Mercanti in Giardino](https://prolocoregionefvg.it/eventi-delle-associate/mercatino-dellusato-codroipo/) e [UNPLI, Lo Scrigno del Doge](https://prolocoregionefvg.it/eventi-delle-associate/lo-scrigno-del-doge-in-villa-manin-mercatino-dellantiquariato-e-modernariato/) riportano le date future conservate. |
| Date pubblicate, Muggia | M044, M045 | [PromoTurismoFVG, CREATTIVAMENTE](https://www.turismofvg.it/events/market-in-muggia-creattivamente) indica 21 novembre e 19 dicembre, 09:00–17:00; [META](https://www.turismofvg.it/events/market-in-muggia-meta) indica 15 novembre e 6, 13, 20 dicembre. |
| Date pubblicate, Trieste | M033, M047, M048, M049, M051, M052, M055 | Pagine dedicate di [Discover Trieste](https://www.discover-trieste.it/vivi/shopping/andar-per-mercatini), con date e luoghi controllati sulle rispettive schede. La pagina [Antiquariato e Usato](https://www.discover-trieste.it/vivi/trieste-now/mercatino-antiquariato) precisa 08:00–20:00; [Barbacan Produce](https://www.discover-trieste.it/vivi/trieste-now/barbacan-produce) precisa 10:30–18:30 per il solo 13 dicembre. |

Per le cinque ricorrenze senza anno l'orizzonte individuale è il 7 febbraio
2027, data della prossima verifica manuale. Le date degli eventi 2026 non
sono state propagate al 2027. Orari non dichiarati dalle fonti restano vuoti.
Il controllo automatico precedente aveva segnalato alcuni formati non
interpretabili: le pagine corrispondenti sono state lette manualmente; quei
codici restano nello storico e non sono un nuovo job da correggere.

### Schede sospese, da correggere nel pannello

| Motivo prevalente | ID |
| --- | --- |
| Fonte storica, generica o luogo insufficiente | M007, M008, M009, M013, M014, M015, M031, M032, M038 |
| Manifestazione stagionale o edizione passata senza nuovo calendario | M046, M054, M057, M059, M060 |
| Ricorrenza plausibile ma programma futuro non inserito o sede della singola edizione da verificare | M030, M040, M041, M042 |

Altre 19 schede già visibili nello snapshot 0 erano state trasformate in bozze
durante la preparazione delle pratiche, con dati nuovi ancora da verificare.
Anche queste sono ora sospese per evitare che il vecchio contenuto sia
conservato implicitamente nella prossima proiezione: M001, M002, M003, M005,
M010, M011, M012, M016, M017, M018, M019, M020, M025, M027, M034, M035,
M037, M043 e M058. Restano riapribili e correggibili nel pannello.

Esempi verificabili: la pagina [Aurisina](https://www.turismofvg.it/events/market-in-aurisina-square)
si ferma al 17 ottobre 2026; la pagina [Gradisca](https://prolocoregionefvg.it/eventi-delle-associate/mercatino-dellantiquariato/)
elenca date del 2023; le pagine [Udine Antiqua](https://www.turismofvg.it/events/udine-antiqua-474448),
[Vecchi Ricordi](https://www.turismofvg.it/events/vecchi-ricordi-474442) e
[Robis di une volte](https://www.turismofvg.it/events/second-hand-market-robis-di-une-volte-474437)
descrivono ricorrenze 2026, ma nell'archivio non hanno edizioni future
esplicitamente inserite. La scheda [San Daniele](https://www.infosandaniele.com/it/turismo/manifestazioni/mercato-settimanale)
menziona anche l'antiquariato; M038 resta sospesa finché il programma non
viene confermato, senza dedurre le date delle domeniche.

## Interfaccia e verifiche ancora necessarie

Nel pannello la scheda mantiene Dati, Calendario, Edizioni e Fonti; le quattro
sezioni sono disposte in una griglia 2 × 2 su schermi stretti. La sezione
Verifiche ora presenta soltanto il controllo manuale trimestrale. Le edizioni
hanno un campo orario specifico. Nell'app il dettaglio mostra l'orario sotto
la data, e il collegamento a Eventi usa lo stesso dato. Per un intervallo
preciso, Eventi mostra anche l'ora di inizio e di fine. Le righe delle date
si adattano a più contenuto su schermi stretti. La coda del controllo manuale
include tutte le schede non archiviate, anche quelle sospese o senza problemi
tecnici rilevati, così restano raggiungibili per il prossimo controllo.

L'app è stata osservata in Chrome headless con viewport di 390 px, usando una
proiezione **locale e non pubblicata** della revisione 15 nella cache del solo
profilo di prova. Il catalogo di Trieste mostra tre mercati abituali e le
schede occasionali selezionate, senza le sospese; Barbacan mostra l'orario
10:30–18:30 sotto la data del 13 dicembre. La scheda Antiquariato e Usato
mostra titolo su due righe, orario, date e pulsante verso Eventi senza
fuoriuscite visibili. Aperto l'appuntamento del 15 novembre, Eventi mostra
08:00–20:00 insieme a data e luogo. La proiezione contiene 16 schede e 126 edizioni, incluse
quelle passate conservate per provenienza; scade dopo il 7 febbraio 2027.

L'editor del pannello è stato osservato a 390 px in una pagina temporanea con
dati di esempio e gli stessi componenti/CSS: Dati ed Edizioni sono leggibili,
la griglia delle sezioni non lascia un pulsante isolato e l'orario della singola
edizione entra nel modulo. I file della pagina temporanea sono stati rimossi.
Resta da osservare il login e il flusso di salvataggio nel pannello autenticato
del proprietario. La prova Chrome desktop con viewport mobile non sostituisce Safari/iPhone o un telefono
Android. Per un rilascio Web/Android valgono le prove e le autorizzazioni dei
runbook. L'archivio locale è stato salvato con copie SQLite coerenti prima dei
due interventi; il servizio cloud e l'archivio remoto non sono stati aggiornati.

Verifiche di codice: 121 test backend Mercati e `compileall` PASS; 194 test del
pannello, lint e build di verifica PASS; 5.190 test frontend, lint e build di
verifica PASS. Dopo la correzione dell'orario in Eventi, 16 test mirati PASS;
la compilazione frontend finale è stata ripetuta separatamente.
