# Mercati e mercatini — copertura e ricerca del 29 ottobre 2026

**Seguito del 30 ottobre:** [dossier e registro delle fonti](MERCATI_FONTI_CATALOGAZIONE_20261030.md), con 44 schede approfondite e 11 nuove candidature. Il presente rapporto resta evidenza datata; nuove conferme e conflitti sono nel seguito, senza modificare il catalogo applicativo.

Ricerca sul ramo dedicato `codex/mercati-integration-20261028`, base
`742b409a`. Orto sospeso e conservato nel proprio ramo. Il coordinatore è
l'unico autore di questo rapporto; `scopri` ha ricercato gli abituali UD/PN,
`eventi` i periodici/stagionali e i sette esclusi, `build_verifica` ha svolto
l'audit statico dei limiti del modello. Il coordinatore ha ricercato GO/TS.

Questo è un inventario di ricerca per ampliare la copertura regionale, non
un aggiornamento già applicato al catalogo né un censimento completo dei
mercati attivi in FVG. Fonti consultate il 29 ottobre 2026; date e orari locali
Europe/Rome. La data di consultazione non rende attuale un documento storico.
Il [verbale della versione locale](MERCATI_SCOPRI_V1_LOCALE_2026-10-15.md)
rimane il riferimento per comportamento, avvio e prove precedenti.

## Punto di partenza misurato

Fonte: [catalogue2026.json](../../frontend/src/data/markets/catalogue2026.json),
verifica interna dichiarata 14 ottobre e limite di proiezione 31 dicembre 2026.

| Area | Schede pubbliche | Abituali | Periodici/fiere | Comuni rappresentati | Comuni con abituali |
|---|---:|---:|---:|---:|---:|
| UD | 16 | 6 | 10 | 8 | 5 |
| PN | 16 | 9 | 7 | 7 | 5 |
| GO | 6 | 4 | 2 | 6 | 4 |
| TS | 15 | 4 | 11 | 3 | 2 |
| Totale | **53** | **23** | **30** | **24** | **16** |

- Conservati anche 7 record esclusi: 5 `Parziale`, 2 `Conflitto`.
- 176 date, tutte 2026: 161 su schede documentate, 15 su tre escluse
  (M029: 1; M050: 12; M056: 2). Nessuna data 2027.
- Dal 29 ottobre al 31 dicembre: **30 date pubblicate su 14 schede pubbliche**.
  Le altre 16 schede occasionali non hanno date future; alcune sono stagionali
  già concluse, altre hanno un calendario da completare. Non sono tutte errori.
- Fra le 53 schede: 6 senza sede, 35 senza orario, 22 senza query per Maps.
  Un dato assente va ricercato; non si riempie con una stima o un punto inventato.
- Dieci occasionali documentati non hanno alcuna data inserita, neppure passata:
  restano consultabili in «Tutti», ma non alimentano i filtri per giorno e non
  generano edizioni dal catalogo in Eventi. Eventuali appuntamenti forniti dal
  backend restano disponibili attraverso il flusso Eventi esistente.

L'assenza di una scheda non dimostra l'assenza di un mercato nel comune.
Nessuna percentuale di copertura regionale viene dichiarata: manca un
denominatore completo e aggiornato dei mercati effettivamente attivi.

## Primo elenco di 74 candidati

**30 UD/PN + 12 GO + 12 TS + 20 periodici/stagionali**. Sono candidature di
identità/sede, non 74 nuove schede approvate o 74 appuntamenti futuri.
Una sede con più giornate è talvolta raggruppata; prima dell'importazione
occorre fissare identità e relazioni, evitando doppioni fra mercato ordinario,
agricolo, rionale e manifestazioni ospitate nello stesso luogo.

Accesso alle prove: **L** = pagina/documento aperto e passaggio pertinente letto;
**I** = estratto indicizzato della fonte primaria, apertura incompleta/JS/timeout;
**H** = informazione storica da aggiornare; **C** = conflitto da riconciliare.
Le sigle descrivono la prova, non l'approvazione per l'app. Un regolamento
documenta un'istituzione o una regola, non lo svolgimento effettivo di oggi.

### Abituali: Udine e Pordenone

Il lotto riguarda 19 comuni: 13 non compaiono nelle attuali 24 località
pubbliche, mentre altri sei hanno già mercati di tipo diverso. Comprende
anche Carnia, Canal del Ferro, Val Canale e pedemontana.

| ID ricerca | Comune / mercato o sede | Giorno o periodo esplicito | Prova e verifica residua |
|---|---|---|---|
| UP01 | Udine, piazza XX Settembre, ordinari | Mar, gio, ven, sab | L/H: [regolamento 2023][udine]; giornate raggruppate per sede, esercizio attuale da riscontrare |
| UP02 | Udine, piazza XX Settembre, ortofrutta/fiori | Mer | L/H: [scheda 2-bis][udine]; identità distinta dagli ordinari |
| UP03 | Udine, Vât, via Redipuglia | Sab | L/H: [scheda 7][udine]; controllare avvisi recenti |
| UP04 | Udine, via Riccardo di Giusto | Gio | L/H: [scheda 8][udine]; controllare avvisi recenti |
| UP05 | Tolmezzo, centro | Lun mattina | L/H: [regolamento 2009](https://www.comune.tolmezzo.ud.it/wp-content/uploads/2024/05/Regolamento-per-la-disciplina-del-commercio-su-aree-pubbliche.pdf), art. 19; sedi corroborate da [ordinanza 2025, I](https://www.comune.tolmezzo.ud.it/wp-content/uploads/2025/10/Ordinanza-364-Filo-Sapori-2025.pdf); eccezioni festive da acquisire |
| UP06 | Cervignano del Friuli, piazza Indipendenza e vie adiacenti | Gio | L/H: [regolamento 2005](https://www.comune.cervignanodelfriuli.ud.it/media/files/md/030023/regolamento_per_la_disciplina_del_mercato_settimanale.pdf), artt. 2–3; aggiornamento attuale necessario |
| UP07 | Latisana, centro | Mer | L: [disciplina sosta 30/12/2025][latisana-sosta]; piazze Garibaldi, Indipendenza, Matteotti e vie adiacenti; orario della sosta diverso da vendita |
| UP08 | Latisana, Pertegada | Ven | L: [regolamento art. 17](https://www.comune.latisana.ud.it/media/files/030046/attachment/COMMERCIO_AREE_PUBBLICHE_REGOLAMENTO_TESTO_COORDINATO_01.pdf); sede puntuale e attualità da completare |
| UP09 | Tarcento, settimanale | Ven | L: [pagina del regolamento](https://www.comune.tarcento.ud.it/it/documenti_pubblici/regolamento-del-mercato-32297); PDF non estraibile, sede da verificare |
| UP10 | Lignano Sabbiadoro, mercato estivo | Lun, 1 maggio–30 settembre | L: [regolamento 19/12/2024](https://comune.lignano-sabbiadoro.ud.it/amministrazione/documenti-e-dati/atti-normativi/regolamenti/regolamento-per-la-disciplina-dell-attivita-commerciale-sulle-aree-pubbliche/regolamento-per-la-disciplina-dellattivita-commerciale-sulle-aree-pubbliche.pdf/%40%40download/file_principale); indirizzo della planimetria A da completare; stagione conclusa |
| UP11 | Lignano Sabbiadoro, invernale, via Lilla–Cinecity | Mar, 06/10/2026–27/04/2027, 07:30–13:30 | L: [avviso 02/10/2026](https://comune.lignano-sabbiadoro.ud.it/novita/avvisi/avviso-spostamento-temporaneo-mercato-invernale); sede temporanea, non viale Porpetto; relazione con UP10 da modellare |
| UP12 | Tarvisio, via Vittorio Veneto | Mar e sab | L/H: [regolamento 2019, art. 8][tarvisio]; [app comunale, I](https://tarvisio.comune.digital/eventi) mostra anche 31/10, 3 e 7/11/2026; distinto dal coperto |
| UP13 | Tarvisio, Camporosso, via Valcanale | Gio | L/H: [regolamento art. 8][tarvisio]; attività effettiva da accertare |
| UP14 | Pontebba, piazza del Mercato | Mer e ven | L/H: [regolamento 19/05/2022](https://www.comune.pontebba.ud.it/media/files/030076/attachment/Regolamento_per_l_esercizio_del_commercio_sulle_aree_pubbliche.pdf), art. 8; non ridurre al solo mercoledì |
| UP15 | Moggio Udinese, mercato comunale | Sab | L/H: [regolamento 29/06/2015](https://comune.moggioudinese.ud.it/media/files/030059/attachment/Regolamento_disciplina_Attivita_commerciale_sulle_aree_pubbliche.pdf), art. 8; sede e attualità non accertate |
| UP16 | Aviano, settimanale ordinario del centro | Mar | L: [bando comunale 2025](https://backoffice-comuni.regione.fvg.it/media/files/093004/attachment/Bando-signed.pdf); distinto dal contadino M020; non adottare il sabato degli aggregatori |
| UP17 | Spilimbergo, centro | Sab | L/H: [regolamento 2016](https://comune.spilimbergo.pn.it/media/files/093044/attachment/Regolamento_Aree_Pubbliche_modificato_con_delibera_CC_del_2016_c3JXv8M.pdf), scheda A; vie Mazzini, I Maggio, Borgolucido; riscontro recente da acquisire |
| UP18 | Maniago, via Roma / area via Regina Elena | Lun | [Avviso dicembre 2024, I](https://www.comune.maniago.pn.it/it/novita-221530/notizie-221531/avviso-mercato-settimanale-290832), sedi nel [bando 09/01/2026, L](https://www.comune.maniago.pn.it/media/files/093025/attachment/AVVISO_PUBBLICO_SITO_RIAPERTURA_BANDO.pdf) |
| UP19 | San Vito al Tagliamento, piazza del Popolo | Ven | L: [ordinanza 52/2026](https://backoffice-comuni.regione.fvg.it/media/files/md/093041/ORDINANZA_N._52_2026.pdf); gli orari ZTL non sono quelli di vendita |
| UP20 | Fontanafredda, piazzale San Luca | Gio | I: [Comune](https://www.comune.fontanafredda.pn.it/vivere-il-comune/) e [assegnazione 17/01/2025](https://servizionline.comune.fontanafredda.pn.it/zf/index.php/atti-amministrativi/determine/dettaglio/table-determine-public-page/54/atto/GTVRreEU1TT0-H); completare lettura |
| UP21 | Cordenons, piazza della Vittoria | Ven | L: [scheda delibera 62, 21/05/2026](https://sac4.halleysac.it/c093017/zf/index.php/atti-amministrativi/delibere/dettaglio/atto/G9mpBd0TUWT0-A); allegato integrale/posteggi/orari non qualificati |
| UP22 | Fiume Veneto, piazzale del Des | Gio | L: [ordinanza 53, 18/10/2024](https://comune.fiumeveneto.pn.it/media/files/093021/attachment/COPIACONFORMEORD0.1_iKCThGi.pdf); non mantenere lo spostamento valido solo il 24/10/2024 |
| UP23 | Azzano Decimo, piazza Libertà, ordinario | Lun | L/H: [rendiconto 2023, p. 58][azzano]; attività attuale da riscontrare |
| UP24 | Azzano Decimo, piazza Libertà, agricolo | Mer | L/H: [rendiconto][azzano]; distinto dal lunedì; attualità da aggiornare |
| UP25 | Azzano Decimo, Tiezzo | Gio | L/H: [rendiconto][azzano]; [PIAO 2025, I](https://comune.azzanodecimo.pn.it/media/files/093005/attachment/PIAO_2025_-_COMUNE_DI_AZZANO_DECIMOsigned.pdf) prevede ricollocazione: sede attuale da verificare |
| UP26 | Azzano Decimo, Corva | Mer pomeriggio | L/H: [rendiconto][azzano]; sede puntuale e prosecuzione da accertare |
| UP27 | Casarsa della Delizia, capoluogo | Mar | L: [regolamento 10/03/2025, art. 31][casarsa]; completare sede, indicata solo da [servizio TARI, I](https://www.trasparenzatari.it/trasparenzatari/?comune=b940) |
| UP28 | Casarsa della Delizia, San Giovanni | Mer | L: [regolamento art. 31][casarsa]; sede e attività attuale da verificare |
| UP29 | Pordenone, Torre, piazza Don Lozer, agricolo | Gio mattina | I: [nota/bando 28/05/2024](https://www.comune.pordenone.it/it/comune/comunicazione/comune-informa/stampa/area-stampa/aperto-il-bando-per-la-gestione-del-mercato-di-torre); affidamento successivo da verificare |
| UP30 | Pordenone, Sacro Cuore, agricolo | Ven | I/H: [nota 07/07/2025](https://www.comune.pordenone.it/it/novita/affidamento-temporaneo-e-rilancio-del-mercato-agricolo-del-sacro-cuore); affidamento documentato fino al 31/12/2025, gestione 2026 e sede da verificare |

[udine]: https://www.comune.udine.it/content/download/2424/43368/file/regolamento_AP_approvato_da_DC51_2023_-con_numero_determina.pdf
[latisana-sosta]: https://www.comune.latisana.ud.it/media/files/md/030046/TARIFFE_E_DISCIPLINARE.pdf
[tarvisio]: https://comune.tarvisio.ud.it/media/files/md/030117/Nuovo_Regolamento_modifiche_2019.pdf
[azzano]: https://www.comune.azzanodecimo.pn.it/media/files/093005/attachment/allegato_B_Relazione_Rendiconto_2023_pJlQsdm.pdf
[casarsa]: https://www.comune.casarsadelladelizia.pn.it/media/files/093010/attachment/POLIZIA_URBANA_TESTO_PER_SITO.pdf

### Abituali e sedi ricorrenti: Trieste

Per TS01–TS09 la [guida comunale][trieste-aree] è leggibile nell'indice di
ricerca, mentre l'apertura diretta restituisce soltanto la richiesta JavaScript.
La pagina nasce nel 2021 e collega anche graduatorie 2026–2027; ciò non
certifica l'aggiornamento di ogni riga. TS09 richiede inoltre verifica del
trasferimento annunciato nel giugno 2026.

| ID ricerca | Comune / mercato o sede | Indicazione della fonte | Prova e verifica residua |
|---|---|---|---|
| TS01 | Trieste, piazza Hortis, rionale | Lun–sab 08–14 | I: [Comune][trieste-aree]; distinto dalle manifestazioni creative |
| TS02 | Trieste, piazza Foraggi, rionale | Lun–sab 08–14 | I: [Comune][trieste-aree] |
| TS03 | Trieste, piazza Garibaldi, rionale | Lun–sab 08–14 | I: [Comune][trieste-aree] |
| TS04 | Trieste, Campo San Giacomo, rionale | Mar 08–14 | I: [Comune][trieste-aree]; distinto dall'agricolo del sabato |
| TS05 | Trieste, piazza Tra i Rivi, rionale | Lun–sab 08–14 | I: [Comune][trieste-aree] |
| TS06 | Trieste, Opicina, via Doberdò | Lun 08–14 | I: [Comune][trieste-aree] |
| TS07 | Trieste, via dei Mille | Lun 08–14 | I: [Comune][trieste-aree] |
| TS08 | Trieste, Borgo San Sergio, rionale | Mer 08–13 | I: [Comune][trieste-aree]; distinto dal Mercatino di Borgo E04 |
| TS09 | Trieste, mercato storico Ponterosso | Guida: mar–sab 07–15 | I/C: [guida][trieste-aree] e [avviso di trasferimento dal 03/06/2026, indice](https://www.comune.trieste.it/it/categories/content/commercio-1915); sede corrente da accertare. Non è automaticamente M050 usato/antiquariato |
| TS10 | Trieste, Campagna Amica Campo San Giacomo | Sabato / alternanza con Goldoni | L/C: [organizzatore][ca-sangiacomo], testo 08–13 e riquadro 08–14; acquisire calendario e orari coerenti |
| TS11 | Trieste, Campagna Amica piazza Goldoni | Sabati alterni | L/C: [stessa fonte][ca-sangiacomo]; non generare tutti i sabati né dedurre l'alternanza |
| TS12 | Duino-Aurisina, mercato di Aurisina, piazza San Rocco | 1° e 3° mar, 07:30–13:30 | I/H: [regolamento storico, art. 20](https://www.comune.duino-aurisina.ts.it/media/files/032001/attachment/sad_MMK5E_REGOLAMENTO_COMMERCIO_AREE_PUBBLICHE_01_1bIoQU1.pdf); riscontro attuale necessario; distinto da M046 antiquariato |

[trieste-aree]: https://www.comune.trieste.it/it/guide-223180/guida-alle-attivita-economiche-230935/attivita-di-mercato-13598/mercato-su-aree-pubbliche-13599
[ca-sangiacomo]: https://www.campagnamica.it/la-nostra-rete/mercato/il-mercato-di-campagna-amica-di-campo-san-giacomo-di-trieste/

### Abituali e sedi ricorrenti: Gorizia

| ID ricerca | Comune / mercato o sede | Indicazione della fonte | Prova e verifica residua |
|---|---|---|---|
| GO01 | Gradisca d'Isonzo, ordinario della Spianata | Mar e sab mattina | I/H: [regolamento comunale TOSAP, art. 29](https://www.comune.gradiscadisonzo.go.it/media/files/md/031008/REGOLAMENTO_T.O.S.A.P._mpBM9ht.pdf); [riscontro locale letto](https://www.conteadigradisca.it/info/). Acquisire calendario attuale, distinto da M032 antiquariato |
| GO02 | Staranzano, piazza Dante Alighieri | Sab mattina | L: [delibera 106 del 29/08/2025](https://www.comune.staranzano.go.it/media/files/031023/attachment/delibera_106_29_8.pdf), pp. 3–4; orari e successive variazioni da completare |
| GO03 | Monfalcone, Campagna Amica, piazza Falcone e Borsellino | Mer 08–13, tutto l'anno | L: [organizzatore](https://www.campagnamica.it/la-nostra-rete/mercato/il-mercato-di-campagna-amica-di-monfalcone/); distinto dal settimanale ordinario M008; eccezioni da acquisire |
| GO04 | Doberdò del Lago, agricolo, piazza San Martino | Settimanale, orari scolastici/estivi diversi | L: [PromoTurismo](https://www.turismofvg.it/eventi/cose-buone-persone-buone-doberdo-del-lago); il testo non esplicita il giorno. L'intervallo 2026–2027 non è un calendario giornaliero; confrontare con organizzatore |
| GO05 | Gorizia, mercato coperto comunale, corso Verdi | Identità e luogo | L: [portale del Comune](https://letsgo.gorizia.it/punto-di-interesse/mercato-coperto/); orari/attività effettive da completare, distinto da via IX Agosto |
| GO06 | Gorizia, coperto Campagna Amica, via IX Agosto 4/b | Giorni attuali da riconciliare | L/H: [apertura 2019](https://www.campagnamica.it/attualita/gorizia-nasce-primo-mercato-coperto-km-zero/); [produttore partecipante, I](https://www.agricolablasizza.it/) indica mar pomeriggio, gio/sab mattina. Non riciclare gli orari originari o la vecchia sede Garibaldi |
| GO07 | Gradisca d'Isonzo, Campagna Amica, piazzale Unità | Testo mar/gio, riquadro ven 08:30–13 | L/C: [organizzatore](https://www.campagnamica.it/la-nostra-rete/mercato/il-mercato-isontino-di-campagna-amica-di-gradisca-disonzo/); conflitto interno da risolvere, distinto dall'ordinario GO01 |
| GO08 | Grado, mercato coperto, piazza Duca d'Aosta | Identità e luogo | L: [portale turistico](https://grado.it/it/audioguide/itinerario-sport-natura-ed-enogastronomia?tappa=fossalon-and-white-asparagus-); orari da acquisire, distinto dal settimanale M006 |
| GO09 | Fogliano Redipuglia, area feste via San Michele | Gio 07:30–13, sperimentazione 12 mesi | L/H: [regolamento 2020](https://municipium-images-production.s3-eu-west-1.amazonaws.com/s3/2823/allegati/regolamenti/regolamento-per-listituzione-e-la-disciplina-del-mercato-settimanale.pdf), artt. 2–5, collegato dalla [pagina comunale](https://www.comune.foglianoredipuglia.go.it/it/page/regolamenti). Proroga/prosecuzione attuale non verificata |
| GO10 | Gorizia, mercato del centro | Piano storico: giovedì quindicinale | L/H: [piano aree pubbliche][gorizia-piano], p. 3; copertina con estremi di approvazione incompleti, calendario attuale non acquisito |
| GO11 | Gorizia, piazzale Casa Rossa | Piano storico: giovedì quindicinale | L/H: [piano][gorizia-piano], p. 4; stessa cautela, non generare ogni giovedì |
| GO12 | Gorizia, via dei Catterini | Piano storico: venerdì | L/H: [piano][gorizia-piano], p. 5; attività attuale non verificata |

[gorizia-piano]: https://www.comune.gorizia.it/media/files/md/031007/all_C_delibera_Regolamento_-_Piano_AA_PP.pdf

**Deduplicazione ancora necessaria:** Campagna Amica Cormons è segnalato da un
[produttore partecipante](https://www.agricolablasizza.it/) il venerdì in piazza
Libertà. Potrebbe essere parte del mercato ordinario M007: non è contato come
nuova scheda autonoma. Il vecchio agricolo di via Garibaldi a Gorizia non viene
aggiunto: l'organizzatore ne documenta il trasferimento in via IX Agosto.

### Periodici, artigianato e manifestazioni stagionali

E01–E15 hanno una prossima edizione o un periodo 2026 pubblicato, con i limiti
indicati; E16 ha una cadenza primaria da aggiornare; E17–E20 hanno prove
storiche 2026. Il calendario di una festa può essere più ampio di quello delle
bancarelle. Le date oltre oggi+15 giorni non sono ancora appuntamenti Eventi.

| ID ricerca | Comune / manifestazione | Evidenza temporale | Fonte e limite |
|---|---|---|---|
| E01 | Trieste, Gente creativa, largo Panfili | 14/11 e 12/12/2026 | L: [Discover Trieste](https://www.discover-trieste.it/vivi/trieste-now/gente-creativa); calendario annuale esplicito, solo orario diurno |
| E02 | Trieste, CreAttivaMente | Hortis 8/11 e 13/12; Cavana/via del Pesce 15/11 e 20/12/2026 | L: [Discover Trieste](https://www.discover-trieste.it/vivi/trieste-now/creattivamente); sedi per data, distinto da M044 Muggia e M048 antiquariato Cavana |
| E03 | Trieste, Mostra dell'ingegno artistico creativo | Piazza Borsa: 15 e 29/11, 13 e 20/12/2026 | L: [Discover Trieste](https://www.discover-trieste.it/vivi/trieste-now/mostra-mercato-ingegno-artistico-creativo); anche sede diversa in un'edizione passata, non inferire ricorrenza |
| E04 | Trieste, Mercatino di Borgo, piazza XXV Aprile | 14/11 e 19/12/2026, 08–tramonto | L: [Discover Trieste](https://www.discover-trieste.it/vivi/trieste-now/mercatino-di-borgo); novembre non è il terzo sabato; verificare alias «L'occasione del Borgo» |
| E05 | Trieste, Mostra mercato Disco/CD/DVD, Chiarbola | 29/11/2026, 10–19 | L: [Discover Trieste](https://www.discover-trieste.it/vivi/trieste-now/mostra-mercato-disco-cd-dvd-usato-e-da-collezione); ingresso a pagamento, singola edizione |
| E06 | Monfalcone, libri usati, biblioteca via Ceriani 10 | 7/11 e 5/12/2026, 09:30–12:30 | L: [Biblioteca](https://bibliotecamonfalcone.it/attivita/mercatino-usati/); anno nei link datati, dettagli non aperti; verificare eccezioni al primo sabato |
| E07 | San Vito al Tagliamento, Voglia di Natale, Antico Ospedale dei Battuti | 5, 6, 8, 12, 13, 19, 20/12/2026, 10–19:30 | L: [Pro San Vito](https://www.prosanvito.it/2026/07/16/mercatino-voglia-di-natale-2026/); distinto da M058 nelle vie cittadine |
| E08 | Martignacco, Idea Natale, Fiera di Udine | 13–16/11/2026 | L/C: [organizzatore](https://www.udinesposizioni.it/idea-natale/), [PromoTurismo IT](https://www.turismofvg.it/eventi/idea-natale-2026-un-esperienza-da-vivere-in-fiera); comune Martignacco, orario lunedì discordante IT/EN |
| E09 | Pordenone, Fotomercato, Fiera | 21–22/11/2026 | L/C: [Fiera](https://www.fierapordenone.it/eventi/fotomercato-11-2026/), [organizzatore](https://fotomercato.com/eventi/); padiglione 7 contro 8, non importare il 20/11 degli aggregatori |
| E10 | Pordenone, IO CREO, Fiera | 20–22/11/2026, 09:30–18:30 | L: [Fiera](https://www.fierapordenone.it/eventi/io-creo-dai-vita-alle-tue-idee-2026/); padiglione 1; pertinente come mostra commerciale di creatività, non estendere a fiere B2B |
| E11 | Latisana, Fiera di San Martino | Festa 6–11/11/2026 | L: [PromoTurismo](https://www.turismofvg.it/eventi/fiera-di-san-martino-504039?LangSetCMS=it); programma completo successivo, giorni effettivi delle bancarelle da acquisire |
| E12 | Trieste, Fiera di San Nicolò, viale XX Settembre | 28/11–06/12/2026, 09–21 | L: [PromoTurismo](https://www.turismofvg.it/eventi/la-magia-del-natale-fiera-di-san-nicolo?LangSetCMS=it); riscontro nell'indice comunale; distinto da E13 |
| E13 | Trieste, Mercatino di Natale | Produzione: 05/12/2026–06/01/2027 | L/C: [PromoTurismo pubblico](https://www.turismofvg.it/eventi/la-magia-del-natale-mercatino-di-natale-2026); verificare inaugurazione con Comune, preproduzione/aggregatori discordano; non usare preproduzione per pubblicare |
| E14 | Sauris, A Sauris è Natale, Sauris di Sopra | 5, 6 e 8/12/2026 | L: [Italia.it](https://www.italia.it/it/friuli-venezia-giulia/udine/cosa-fare/evento-natale-a-sauris); riscontro calendario montagna PromoTurismo, dettaglio organizzatore da completare; non aggiungere 7/12 |
| E15 | Lignano Sabbiadoro, Natale d'A...Mare / Villaggio del Gusto | Programma 05/12/2026–10/01/2027 | L/C: [organizzazione](https://www.lignanonataledamare.it/); alcuni riquadri conservano intervalli vecchi; distinguere casette, presepe e festa, acquisire aperture effettive |
| E16 | Latisana, Dentro il Baule, piazza Matteotti | Primo sabato; calendario attuale incompleto | L/H/C: [disciplinare comunale][latisana-sosta], [UNPLI 2025](https://prolocoregionefvg.it/eventi-delle-associate/dentro-il-baule-mercatino-dellusato-e-dellantiquariato-8/); altra sede/terzo sabato da riconciliare, non usare fasce della sosta come orari |
| E17 | Cividale del Friuli, Mercato dei Patriarchi | 15/02–11/10/2026, periodo concluso | L/H: [PromoTurismo](https://www.turismofvg.it/eventi/mercato-dei-patriarchi-476488); singola edizione 8/3 anche in agenda comunale; non generare future date |
| E18 | Codroipo, Grande Mercato di San Simone | 25/10/2026, trascorso | L/H: [atto comunale 230/2026](https://servizionline.comune.codroipo.ud.it/zf/index.php/atti-amministrativi/delibere/dettaglio/atto/GT0RrM5UUUT0-F); non usare tutto il periodo della festa |
| E19 | Palmanova, Fiera di Santa Giustina | 2–4/10/2026, trascorsa | L/H: [Comune](https://www.comune.palmanova.ud.it/it/novita-179021/notizie-179022/eventi-per-santa-giustina-e-ottobre-palmarino-2026-327858); utile alla raccolta della prossima edizione |
| E20 | Codroipo, Mercanti in Erba, via Candotti | 19/04/2026, 10–18, trascorso | L/H: [regolamento comunale](https://www.comune.codroipo.ud.it/media/files/030027/attachment/Regolamento_2026_4.pdf); libero scambio per bambini/ragazzi, non Mercanti in Giardino |

## Sette esclusi: prove nuove e impedimenti

| ID app | Riscontro del 29 ottobre | Azione necessaria |
|---|---|---|
| M024 Riuso Udine | [UNPLI](https://prolocoregionefvg.it/eventi-delle-associate/mercatino-del-riuso-4/) conserva 4/4 contro testo senza aprile; [PromoTurismo aggiornato](https://www.turismofvg.it/veranstaltung/mercatino-del-riuso-474446) anticipa 5/12 al 28/11, altre versioni conservano 5/12 | Riconciliare date con organizzatore; conflitto ancora aperto |
| M026 Antiquariato San Vito | Nessun nuovo calendario annuale primario accertato; resta prova precedente del 4/10 | Completare fonte/cadenza; non promuovere per somiglianza con altri mercati |
| M029 Venzone | [PromoTurismo](https://www.turismofvg.it/eventi/mercanti-nel-borgo-antigae-e-a-vencon-478654): **8/11/2026, 08–17, centro storico**, anche con maltempo | Prima candidata alla rivalutazione editoriale: identità e singola data documentate, calendario annuale non accertato |
| M036 Antiquariato in Contrada PN | Nessuna nuova primaria sufficiente; sito ProPordenone non accessibile al lettore | Chiarire calendario/sospensioni, soprattutto dicembre |
| M039 Baule del Diavolo | [PromoTurismo](https://www.turismofvg.it/eventi/il-baule-del-diavolo-475626?LangSetCMS=it): quarta domenica, periodo 25/1–22/11/2026, 09–tramonto | Le sospensioni non sono tutte chiarite; acquisire singole edizioni/avvisi |
| M050 Ponterosso | [Discover Trieste](https://www.discover-trieste.it/vivi/trieste-now/mercatino-di-ponterosso) mantiene «solitamente ultima domenica» ma data 22/11/2026 | Chiarire con organizzatore; non confondere col mercato storico TS09 |
| M056 Usato Montedoro | [Organizzatore](https://www.montedoroshoppingcenter.it/2026/02/05/mercatino-dellusato/) conferma solo 14–15/02/2026 | Nessuna nuova cadenza fissa; conservare come edizione storica |

La qualità della scheda e l'affidabilità della singola data richiedono giudizi
distinti. Il modello attuale consente già un sottoinsieme di date puntuali su
una scheda `Documentato`: non occorre inventare un calendario annuale completo.
Ogni eventuale riclassificazione deve però essere motivata e verificata, senza
rendere pubbliche indiscriminatamente le schede `Parziale` o `Conflitto`.

## Date mancanti in schede già pubbliche

La ricerca mirata ha trovato **sette date future esplicite su quattro schede**
che oggi non hanno date future nel JSON. Sono da integrare con verifica degli
avvisi, non da conteggiare come nuovi mercati:

| Scheda | Data 2026 pubblicata | Prova e limite |
|---|---|---|
| M025 AnticaMente, Aviano | 1 novembre | [Edizione UNPLI](https://prolocoregionefvg.it/eventi-delle-associate/anticamente-mercatino-dellantiquariato-ad-aviano-8/?return=%2Feventi-delle-associate%2F); dicembre non confermato |
| M034 Gemona, pulci/libro usato | 1 novembre, 6 dicembre | [Campo Quando UNPLI](https://prolocoregionefvg.it/eventi-delle-associate/mercatino-delle-pulci-e-del-libro-usato/), date elencate separatamente |
| M037 Sacellum, Sacile | 22 novembre, 27 dicembre | [Calendario Pro Sacile](https://www.prosacile.it/antiquariato); disposizione variabile e 27 dicembre espressamente modificabile per esigenze comunali |
| M040 Udine Antiqua | 15 novembre, 20 dicembre | [UNPLI](https://prolocoregionefvg.it/eventi-delle-associate/udine-antiqua-3/); incoerenza storica su aprile, queste due date future non contraddette nel testo consultato |

Per M027 Cervignano la [Pro Loco](https://www.prolococervignanofvg.it/comunicazione-importante-mercatino-dellusato-della-prima-domenica-del-mese/)
conferma l'appuntamento di novembre alla prima domenica, ma non è stata trovata
una data numerica completa con anno nelle fonti primarie consultate. Resta
una conferma parziale. Nessuna delle sette date sopra è stata calcolata dalla
cadenza; nessuna è stata inserita nel runtime in questo passo.

## Ulteriori piste e confini della ricerca

- **Pordenone Villanova:** [fonte comunale indicizzata](https://www.comune.pordenone.it/it/argomenti/mercato/mercato-di-quartiere-villanova)
  indica «temporaneamente sospeso». Non contato come nuovo mercato attivo.
- **Ronchi, Di tutto un po':** [organizzatore](https://www.prolocoronchifvg.it/events/di-tutto-un-po-mercatino-dellantiquariato-del-modernariato-e-del-vintage)
  restituisce errore 500; il solo riscontro secondario non basta.
- **Ovaro, Marcjât di San Martin:** 11 novembre nell'indice montagna
  PromoTurismo; dettaglio/sede da acquisire. **Palmanova, Oggetti e cose d'altri
  tempi / Chi Cerca Trova:** dettaglio primario non accessibile.
- **Monfalcone Mercatino della Rocca, Udine Terminal Nord Antiqua, Trieste
  Il Giulia e Musicart:** acquisire primaria e calendario. Per Musicart
  esistono atti 2026, non ancora un calendario qualificato per sede.
- **Natale a Paluzza, Prata di Pordenone, Vito d'Asio, Aquileia, Monfalcone:**
  piste da approfondire, non edizioni già confermate. Presepi e Advent Pur
  non sono automaticamente mercatini: verificare effettiva vendita/esposizione.
- L'[inventario territoriale Magredi e Risorgive](https://magredierisorgivefvg.eu/wp-content/uploads/2022/11/04_Piasentier-min.pdf)
  è una pista indicizzata per San Quirino, Vivaro, Zoppola e Roveredo; non un
  calendario attuale. Restano da coprire sistematicamente i piccoli comuni e
  le frazioni della Bassa, delle valli e della pedemontana.

Ricercati Comuni e loro atti, organizzatori, PromoTurismoFVG, Discover Trieste,
Pro Loco, biblioteche ed enti fieristici. Gli aggregatori sono stati usati
come piste: mostrano anche giorni sbagliati, date festive generate, comuni
imprecisi e intervalli eccessivi. Nel perimetro consultato non è emersa una
singola fonte ufficiale completa e aggiornata per tutti i mercati regionali.

## Cosa manca nel modello attuale

Audit statico di `build_verifica`, non nuovo test runtime:

1. **Eccezioni degli abituali.** Il [calendario ufficiale Pordenone](https://www.comune.pordenone.it/it/argomenti/mercato/cittadino/determina-calendario-2026-2027.pdf/%40%40download/file)
   sopprime il 26/12/2026. Il predicato di
   [selectMarkets](../../frontend/src/features/markets/marketsCatalog.js)
   selezionerebbe M001 in «Oggi/Weekend» perché sabato. Inserire una
   cancellazione in `dates` non basta: il ramo `regular` usa solo giorno della
   settimana e validità. È un limite concreto del filtro Scopri; non genera
   un evento settimanale in Eventi, e l'avviso di apertura non garantita esiste.
2. **Stagionalità/alternanza.** `cadence` è testo. Lignano estivo/invernale,
   Aurisina primo/terzo martedì e mercati a sabati alterni richiedono periodi e
   regole verificabili. Per gli occasionali le date puntuali sono già supportate.
3. **Sede e orario per edizione.** `dates` contiene mercato/giorno/fonte/stato;
   luogo e orari mostrati da [MarketsExplorer](../../frontend/src/features/markets/MarketsExplorer.jsx)
   sono quelli globali della scheda. M011 descrive già sedi diverse nel testo;
   E02 mostra perché vanno associati chiaramente data e luogo, anche per Maps.
4. **Spostamenti e annullamenti.** Stato non pubblicato toglie una data
   occasionale, ma non rappresenta il collegamento vecchia/nuova data né
   un'avvertenza strutturata. Il riconoscimento delle cancellazioni provenienti
   da Eventi esiste e va conservato.
5. **2027.** Il limite 31/12/2026 è intenzionale. Alcune nuove fonti lo
   superano; occorre aggiornare dati e verifica, non spostare soltanto la soglia.
   «Tutti» conserva le anagrafiche con avviso, i filtri/data Eventi non proiettano 2027.
6. **Manutenzione editoriale.** Il catalogo è incluso nel frontend e non
   richiede rete per essere consultato. Non è emerso un aggiornamento automatico
   di questo JSON: fonte, data di verifica e modifiche vanno mantenute insieme.

Restano invariati deduplica Eventi, annullamenti riconosciuti, finestra da oggi
a oggi+15 giorni inclusi, separazione fra giorno abituale e data pubblicata,
lingue e requisiti del [contratto Scopri](../../ALMANAC_DISCOVER_CONTENT_CONTRACT.md).

## Ordine operativo consigliato

1. **Calendario affidabile prima dell'ampliamento in app:** eccezioni,
   stagionalità, sede per data e prova UI mobile. Coordinatore assegna i file
   condivisi; `scopri` cura catalogo/UI, `eventi` il collegamento alle edizioni,
   `build_verifica` verifica casi limite e regressioni.
2. **Primo inserimento dai riferimenti più solidi:** rivalutare M029 e
   completare le date dei mercatini già presenti; aggiungere progressivamente
   le sedi oggi assenti con giorno/luogo verificati. Aggiornare le fonti
   storiche prima di usarle come prova di attività corrente.
3. **Copertura continua per territorio e stagione:** completare piccoli comuni,
   frazioni, agricoli e Natale; acquisire i calendari 2027. Conservare una coda
   di ricerca distinta dall'elenco pubblicato, con responsabile e ultima verifica.

## Verifiche e limiti della consegna

Questo passo riguarda documentazione e ricerca. Nessun catalogo applicativo,
codice, dipendenza, servizio, job o configurazione è modificato. Nessun contatto
inviato agli organizzatori e nessuna nuova automazione. I PDF sono stati letti
tramite gli strumenti disponibili; non sono stati importati integralmente
né sono state recuperate immagini per l'app.

Le prove automatiche del 28 ottobre restano storiche; non sono rieseguite
suite, lint o build per questa ricerca. Verifica visiva e revisione friulana
della sezione Mercati restano aperte. AAB 300038, Web pubblicata e relative
qualificazioni non cambiano.

Controlli documentali superati: 74 ID unici e conteggi per gruppo, metriche del
JSON, sette date su quattro schede, cinque link locali e otto reference
Markdown, diff staged. Review di `scopri`, `eventi` e `build_verifica` senza
rilievi sostanziali. Guard canonico superato dopo lo staging dei cinque
Markdown: 4021 file tracciati. Catalogo identico al blob di HEAD; SHA-256
`dce63d9d521ccfd9f593de9143f0ff0649220a0a15c09135ecf902290fecbafb`.
Hook `pre-push` con privacy guard esterno presente e invariato; nessun push.
