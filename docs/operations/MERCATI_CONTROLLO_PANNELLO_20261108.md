# Mercati — controllo del pannello e delle schede, 8 novembre 2026

## Stato osservato

Il pannello online `https://meteofriul-inserzioni.web.app/` apre l'archivio
Mercati con il login Firebase del progetto. L'assenza della base API nella
precedente build Hosting impediva l'apertura delle schede: nel ramo esterno
`codex/panel-events-editor-20261107`, il commit `6e1c68d` imposta la base
Mercati di produzione in assenza di override e aggiorna la CSP report-only.
Sono passati cinque test mirati, lint e build del pannello; il solo target
`hosting:inserzioni` è stato ridistribuito. Il login, la lettura e il salvataggio
nel pannello online sono stati poi verificati con la sessione del proprietario.
La build del pannello è stata eseguita con Node 24/npm 11 disponibili su questo
PC, anziché Node 22.17.1/npm 10.9.2 prescritti dal progetto.

L'archivio Firestore privato è alla **revisione 30**: 100 schede, 222 edizioni,
59 pratiche di ricerca, **21 selezionate**, 34 sospese e 45 bozze. I cinque
blocchi della revisione 30 sono stati riletti e verificati contro lo SHA-256
del puntatore. `publication_errors` restituisce una lista vuota; la proiezione
a secco produce 21 mercati, 128 date e 37 rimozioni rispetto al catalogo
pubblico precedente, senza scrivere la revisione pubblica. Nella precedente
revisione 23 erano selezionate 14 schede; le altre sette sono rientrate dopo
il controllo delle informazioni ordinarie e la scelta editoriale sulle festività.
Il primo gruppo di 14 comprendeva i mercati abituali di Sacile, Palmanova e Cordenons,
più Mercanti in Giardino, Antiquariato e Usato di Trieste, CREATTIVAMENTE, META,
Mercatino al tram, Cavana, Porto Vecchio, Un pozzo di occasioni, I sabati di
Arti in Piazza, Lo Scrigno del Doge e Barbacan Produce. Si aggiungono Codroipo,
San Daniele, Grado, Campagna Amica in piazza Vittorio Veneto, il Mercato coperto
di Trieste, l'accesso pubblico al Mercato ortofrutticolo e Budoia.
La **revisione pubblica è 0**. Il servizio rifiuta ancora la pubblicazione e
non serve un catalogo pubblico; l'app Web e Android distribuite sono invariate.
Nessun job è stato creato o riattivato. La prossima revisione generale rimane
manuale, il 7 febbraio 2027.

## Correzioni salvate nel catalogo privato

| Scheda | Decisione | Controllo e correzione |
| --- | --- | --- |
| M001 Pordenone | Sospesa | [Pagina comunale](https://www.comune.pordenone.it/it/argomenti/mercato/cittadino): area del centro, mercoledì/sabato 08:00–14:00 e indicazioni verso piazza XX Settembre. [Calendario comunale](https://www.comune.pordenone.it/it/argomenti/mercato/cittadino/determina-calendario-2026-2027.pdf/@@download/file): 26 dicembre 2026 annullato, 6 gennaio 2027 confermato. Verificare l'assetto dopo lo [spostamento temporaneo di alcuni banchi](https://www.comune.pordenone.it/it/novita/mercato-cittadino-spostamento-dei-banchi-in-piazza-xx-settembre) prima della selezione. |
| M002 Sacile | Selezionata | [Regolamento comunale](https://comune.sacile.pn.it/media/files/093037/attachment/Regolamento_CQcs8ay.pdf): giovedì, centro storico, vendita 08:15–13:00; destinazione piazza del Popolo. |
| M003 Codroipo | Selezionata | [Piano comunale](https://www.comune.codroipo.ud.it/media/files/md/030027/PIANO_SICUREZZA_MERCATO_CODROIPO.PDF): martedì mattina e vie del mercato; destinazione piazza Garibaldi. Nessun orario numerico inventato. Apertura dell'8 dicembre non attestata. |
| M004 San Daniele del Friuli | Selezionata | La [Pro San Daniele](https://www.infosandaniele.com/it/agenda/in-programma/mercato-settimanale-1) indica via Trento e Trieste e 08:00–13:00. Orario e fonte salvati nella revisione 16; apertura del 6 gennaio 2027 non attestata. |
| M005 Palmanova | Selezionata | [Comunicazione comunale 2026](https://www.comune.palmanova.ud.it/it/novita-179021/notizie-179022/lunedi-di-pasquetta-sui-bastioni-di-palmanova-6-aprile-2026-320575) e [atto posteggi](https://comune.palmanova.ud.it/media/files/030070/attachment/Allegato_B1.0.pdf): lunedì mattina, Piazza Grande e Contrada Donato; orario numerico vuoto. |
| R-PN-M004 Cordenons | Selezionata | [Delibera 2026](https://sac4.halleysac.it/c093017/zf/index.php/atti-amministrativi/delibere/dettaglio/atto/G9mpBd0TUWT0-A) e [delibera 2025](https://www.comune.cordenons.pn.it/media/files/093017/attachment/delibera_di_giunta_n._144-2025.pdf): venerdì, Piazza della Vittoria, vendita 08:00–13:00. Il 25 dicembre 2026 e il 1° gennaio 2027 sono marcati annullati per la normale ricorrenza del venerdì; l'eventuale anticipo resta da confermare. |
| R-PN-M012 Budoia | Selezionata | [Bando comunale per concessioni 2024–2033](https://comune.budoia.pn.it/media/files/093008/attachment/BANDO_COMUNE_DI_BUDOIA.pdf): mercoledì, Piazza Umberto I, 08:00–13:00; la [guida del Distretto 2026](https://www.distrettocommercioaltolivenza.it/alla-scoperta-delle-tradizioni-del-distretto-feste-sagre-e-mercati-storici-da-non-perdere/) conferma il mercato. Apertura del 6 gennaio non attestata. |
| R-PN-M013 Maron di Brugnera | Bozza, non convalidata | La [guida del Distretto 2026](https://www.distrettocommercioaltolivenza.it/alla-scoperta-delle-tradizioni-del-distretto-feste-sagre-e-mercati-storici-da-non-perdere/) conferma mercoledì mattina e Piazza Mercato 12. Una [segnalazione secondaria](https://fvg.piazzainfesta.it/brugnera/dal-campat-alla-piazza-tradizioni-e-sapori-a-maron-87615), che dichiara di usare l'IA, parla di spostamento in via IV Novembre il 18 e 25 novembre. Cercare l'ordinanza originale prima di selezionarla. |
| R-PN-M014 Caneva | Bozza | La guida del Distretto conferma venerdì mattina; l'abbreviazione «Piazza M. Garibaldini» è stata sciolta in Piazza Martiri Garibaldini e sono state aggiunte indicazioni. Verificare le festività del 25 dicembre e 1° gennaio. |
| R-PN-M016 Coltura di Polcenigo | Bozza | La guida del Distretto conferma mercoledì mattina in via dell'Ovre presso la chiesa; la [fermata TPL FVG](https://s3.eu-central-1.amazonaws.com/it.tplfvg.media/media/documents/P33_dal_27-10-2025.pdf) corrobora il punto per le indicazioni. Verificare l'Epifania del 6 gennaio; nessun orario numerico dichiarato. |
| M055 Barbacan Produce | Selezionata | [Discover Trieste](https://www.discover-trieste.it/vivi/trieste-now/barbacan-produce) e [organizzatore](https://www.barbacanproduce.com/) confermano Piazza Barbacan e dintorni; aggiunta la destinazione delle indicazioni. L'edizione del 13 dicembre resta 10:30–18:30. |
| M053 Lo Scrigno del Doge | Selezionata | [UNPLI FVG](https://prolocoregionefvg.it/eventi-delle-associate/lo-scrigno-del-doge-in-villa-manin-mercatino-dellantiquariato-e-modernariato/) conferma Villa Manin/Passariano e le date; luogo e destinazione delle indicazioni sono stati resi leggibili. |

I campi interni di ricerca non sono stati trasformati in promesse pubbliche.
Le schede deboli rimangono nel pannello per correzioni future. I dati stabili
sono stati inseriti una volta; le modifiche future si faranno dallo stesso
editor autenticato e produrranno una nuova revisione privata. Salvare una
scheda non aggiorna automaticamente l'app. Quando il catalogo pubblico sarà
abilitato, la pubblicazione rimarrà un'azione editoriale separata. Per ritirare
una scheda pubblicata occorre sospenderla o archiviarla: una bozza conserva la
precedente versione pubblica fino a una nuova decisione.

Per la prima release dell'app occorre configurare `VITE_MARKETS_API_BASE` verso
il servizio Mercati pubblico. Dopo questa integrazione iniziale, il lettore
dell'app ricarica il catalogo quando la vista si apre o torna in primo piano e
ricontrolla periodicamente mentre è attiva. Una correzione dei soli dati,
salvata e poi pubblicata nel pannello, potrà quindi raggiungere Web e Android
senza ricompilare l'app; una modifica a interfaccia o logica richiederà invece
una normale release. La [verifica precedente delle 34 schede fisse](MERCATI_FISSI_CONTROLLO_FONTI_20261107.md)
resta la coda editoriale: le altre 13 con dettaglio decisivo aperto vanno
analizzate dopo questo gruppo, le sette con fonte debole per ultime. Le 66
schede occasionali richiedono la verifica delle singole edizioni future.

## Festività dei mercati abituali

La convalida tecnica non conosce le chiusure festive. Le seguenti ricorrenze
della revisione 16 cadevano su date festive senza eccezione documentata.
Nella revisione 23 le sette schede erano state sospese per prudenza. Il
proprietario ha poi deciso di mantenerle consultabili come mercati abituali,
con un avviso breve in lista e una spiegazione nel dettaglio: la ricorrenza
non garantisce l'apertura del singolo giorno festivo. Le sette schede sono
state riselezionate nella revisione 30 dopo aver ricontrollato identità,
fonte, sede, cadenza e testi; le note del pannello registrano il limite.

| Data | Schede da chiarire |
| --- | --- |
| 8 dicembre 2026 | M003, M021, M022, M023 |
| 25 dicembre 2026 | M022, M023 |
| 26 dicembre 2026 | M006, M022, M023 |
| 1° gennaio 2027 | M022, M023 |
| 6 gennaio 2027 | M004, M022, M023, R-PN-M012 |

Per M001 e R-PN-M004 le eccezioni già documentate sono state salvate come
edizioni annullate; ciò non conferma gli eventuali anticipi. Le sette schede
rimangono in **Tutti** e, nel loro giorno abituale, possono comparire in
**Oggi/Weekend** con «Festivi: verifica la fonte». Non viene generato un evento
datato in Eventi dalla sola ricorrenza; gli annullamenti documentati continuano
a prevalere. Il test sull'8 dicembre verifica questa distinzione. M021 usa ora la pagina diretta dell'organizzatore
[Campagna Amica](https://www.campagnamica.it/la-nostra-rete/mercato/il-mercato-di-campagna-amica-a-trieste/).
M001 e la segnalazione di Maron restano da chiarire per altre ragioni.

Le date occasionali del gruppo selezionato sono state ricontrollate anche oltre
le prossime settimane: [Discover Trieste](https://www.discover-trieste.it/vivi/trieste-now/un-pozzo-di-occasioni)
elenca il 26 dicembre per *Un pozzo di occasioni* e [UNPLI FVG](https://prolocoregionefvg.it/eventi-delle-associate/lo-scrigno-del-doge-in-villa-manin-mercatino-dellantiquariato-e-modernariato/)
elenca l'8 dicembre e il 6 gennaio per *Lo Scrigno del Doge*. Non sono stati
creati job o date festive per supposizione.

La proiezione privata delle 14 schede è stata caricata **solo temporaneamente**
nel pilota locale 5174 per una prova browser a larghezza telefono. A Pordenone
sono apparse Cordenons e Sacile; a Trieste nove mercatini nel raggio di 20 km.
Il dettaglio di *Un pozzo di occasioni* mostrava 28 novembre, 26 dicembre,
fonte e collegamento Maps. Una categoria interna (`regular`) compariva come
testo grezzo: il ramo app la rende ora «Settimanale» nelle schede, nel dettaglio
e nelle descrizioni Eventi. Il catalogo temporaneo è stato ripristinato al
file originale dopo la prova; questa non è una verifica su telefono reale.
Sul ramo app sono passati 25 test mirati, lint e build Web con service worker;
la verifica frontend ha usato Node 24/npm 11 disponibili sul PC.

L'avviso compatto è stato osservato a larghezza telefono nella scheda Mercati
di Pordenone nel browser locale. Questa seconda prova ha usato il vecchio
catalogo pubblico locale, non la proiezione privata di 21 schede: verifica la
presentazione dell'avviso, non le 21 schede una per una. La prova ha mostrato
la scheda, ma il launcher del pilota ha terminato il controllo finale perché
la connessione alle fonti meteo era negata nell'ambiente sandbox. La successiva
verifica del codice ha superato 18 test mirati, lint e build Web. Restano la
prove su dispositivo; il riscontro puntuale delle fonti collegate al primo
gruppo è riportato sotto.

Per la prima uscita restano la configurazione del servizio pubblico, build Web
e Android dallo stesso commit approvato, prove reali su telefono e Safari/iPhone,
PR e pubblicazioni distinte secondo i runbook.

### Riscontro delle 14 schede già selezionate, 8 novembre

Ho confrontato in sola lettura le 14 schede della precedente revisione 23 con
le rispettive fonti collegate alla revisione privata 30. Per i tre mercati
settimanali ho verificato cadenza, sede e orari dichiarati; per gli undici
mercatini occasionali ho verificato le edizioni future presenti in archivio.
Le date in questa tabella sono quelle pubblicate dalle fonti e già registrate
nel pannello, a novembre/dicembre 2026 e gennaio 2027; non sono ricorrenze
future create per supposizione.

| Scheda | Riscontro sulla fonte | Esito |
| --- | --- | --- |
| M002 Sacile | [Regolamento comunale](https://www.comune.sacile.pn.it/media/files/093037/attachment/Regolamento_CQcs8ay.pdf): giovedì, centro storico, vendita 08:15–13:00. | Coerente. |
| M005 Palmanova | [Bando comunale](https://comune.palmanova.ud.it/media/files/030070/attachment/Allegato_B1.0.pdf) e [notizia comunale](https://www.comune.palmanova.ud.it/it/novita-179021/notizie-179022/lunedi-di-pasquetta-sui-bastioni-di-palmanova-6-aprile-2026-320575): lunedì, Piazza Grande e Contrada Donato; nessun orario numerico nella scheda. | Coerente. |
| R-PN-M004 Cordenons | [Delibera comunale 2025](https://www.comune.cordenons.pn.it/media/files/093017/attachment/delibera_di_giunta_n._144-2025.pdf) e [modifica 2026](https://sac4.halleysac.it/c093017/zf/index.php/atti-amministrativi/delibere/dettaglio/atto/G9mpBd0TUWT0-A): venerdì, Piazza della Vittoria, vendita 08:00–13:00. Il venerdì festivo è anticipato al precedente non festivo solo se aderiscono almeno cinque operatori; un'edizione festiva richiede accordo con il Comune. | Coerente la cancellazione della ricorrenza ordinaria il 25 dicembre e il 1° gennaio; nessun anticipo datato confermato. |
| M028 Mercanti in Giardino | [UNPLI FVG](https://prolocoregionefvg.it/eventi-delle-associate/mercatino-dellusato-codroipo/): Piazza Giardini, dalle 08:00, 8 novembre e 13 dicembre. | Date e sede coerenti. |
| M033 Antiquariato e Usato di Trieste | [Discover Trieste](https://www.discover-trieste.it/vivi/trieste-now/mercatino-antiquariato): Largo Granatieri e Ghetto, 08:00–20:00, 15 novembre e 20 dicembre. | Date e sede coerenti. |
| M044 CREATTIVAMENTE | [PromoTurismo FVG](https://www.turismofvg.it/events/market-in-muggia-creattivamente): Piazza Galilei, 09:00–17:00, 21 novembre e 19 dicembre. | Date e sede coerenti. |
| M045 META | [PromoTurismo FVG](https://www.turismofvg.it/events/market-in-muggia-meta): Piazzetta Galilei, 15 novembre e 6, 13, **20 dicembre**. | Tutte e quattro le date sono già nella revisione 30; nessuna correzione. |
| M047 Mercatino al tram | [Discover Trieste](https://www.discover-trieste.it/vivi/trieste-now/mercatino-al-tram): piazzale Monte Re, 14 novembre e 12 dicembre; recupero domenicale solo se annunciato. | Date e sede coerenti. |
| M048 Cavana | [Discover Trieste](https://www.discover-trieste.it/vivi/trieste-now/mercatino-cavana): piazza Cavana e via del Pesce, 08:00–tramonto, 6 dicembre. | Data e sede coerenti. |
| M049 Porto Vecchio | [Discover Trieste](https://www.discover-trieste.it/vivi/trieste-now/mercatino-di-porto-vecchio): Largo Città di Santos, 08:00–tramonto, 8 novembre e 13 dicembre. | Date e sede coerenti. |
| M051 Un pozzo di occasioni | [Discover Trieste](https://www.discover-trieste.it/vivi/trieste-now/un-pozzo-di-occasioni): Opicina, 08:00–tramonto, 28 novembre e **26 dicembre**. | Date e sede coerenti. |
| M052 I sabati di Arti in Piazza | [Discover Trieste](https://www.discover-trieste.it/vivi/trieste-now/artinpiazza): 14 novembre e 5 dicembre; il testo descrive Piazza Piccola e il sottoportico del Comune, mentre l'intestazione dell'indirizzo dice piazza Unità d'Italia. | Date coerenti; la sede descritta nella scheda segue il testo della fonte. |
| M053 Lo Scrigno del Doge | [UNPLI FVG](https://prolocoregionefvg.it/eventi-delle-associate/lo-scrigno-del-doge-in-villa-manin-mercatino-dellantiquariato-e-modernariato/): Villa Manin, 8 dicembre e **6 gennaio**; sedi delle edizioni già specificate. | Date e sede coerenti. |
| M055 Barbacan Produce | [Organizzatore](https://www.barbacanproduce.com/barbacan-produce-regolamento-2/) e [Discover Trieste](https://www.discover-trieste.it/vivi/trieste-now/barbacan-produce): Piazza Barbacan e dintorni, 13 dicembre, 10:30–18:30. | Data, sede e orario coerenti. |

Non sono emerse discrepanze da correggere nelle 14 schede. Questo è un
riscontro delle fonti collegate, non una garanzia contro comunicazioni comunali
successive o avvisi pubblicati altrove. La revisione privata resta **30** e
quella pubblica **0**. Nessuna scheda è stata modificata, nessun job è stato
creato e nessuna nuova edizione oltre le date esplicite è stata generata.

### Verifica mirata delle fonti, 8 novembre

Il [portale turistico di Grado](https://grado.it/it/eventi/mercato-settimanale)
scrive «tutti i sabati dell'anno», ma non nomina il 26 dicembre 2026: la
ricorrenza generale è confermata, l'eventuale eccezione natalizia resta aperta.
La [pagina del mercato coperto di Trieste](https://www.discover-trieste.it/vivi/shopping/il-mercato-coperto)
e la [guida ai mercati cittadini](https://www.discover-trieste.it/vivi/shopping/andar-per-mercatini)
riportano gli orari ordinari di M022 e M023 senza calendario festivo. Anche
l'[organizzatore di Campagna Amica](https://www.campagnamica.it/la-nostra-rete/mercato/il-mercato-di-campagna-amica-a-trieste/)
conferma il martedì di M021 senza indicare l'8 dicembre 2026. Il
[regolamento di Codroipo](https://www.comune.codroipo.ud.it/media/files/030027/attachment/regolamento_comunale_commercio_aree_pubbliche_DpeySPT.pdf)
conferma il martedì, senza una regola per le festività. Nessuna chiusura o
apertura puntuale è stata inserita per supposizione.

Il [Comune di Pordenone](https://www.comune.pordenone.it/it/novita/mercati-del-mercoledi-e-del-sabato-spostamento-banchi-di-piazza-xx-settembre)
documenta inoltre lo spostamento di parte dei banchi in piazzetta Pescheria e
via Roma dal 14 ottobre; la scheda M001 resta sospesa finché l'assetto
temporaneo e quello successivo saranno descritti con chiarezza. Per Maron,
la ricerca non ha trovato un atto comunale che confermi lo spostamento del
18 e 25 novembre riportato dalla fonte secondaria: R-PN-M013 resta bozza.
