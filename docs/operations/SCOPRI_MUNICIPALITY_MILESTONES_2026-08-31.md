# Scopri — arricchimento delle tappe comunali

Registro avviato il 31 agosto 2026 con il lotto `pn-enrichment-milestones-01` e aggiornato con i successivi lotti multiprovinciali.

## Stato

Quattro nuove tappe per tre profili già esistenti: Andreis, Cimolais e Sacile. Dopo la richiesta di completamento Scopri sono **integrate nel catalogo locale**, con fonti storiche controllate e revisione editoriale IT/FUR assistita. Nessuna modifica a backend, webcam o release Android; nessuna pubblicazione remota.

La revisione FUR è assistita e basata su riferimenti ufficiali ARLeF; non costituisce una traduzione ufficiale dei testi, una certificazione ARLeF o una revisione professionale indipendente. Non viene riusata l'approvazione delle precedenti 17 schede: la nuova base è `user_delegated_assisted_editorial_review`, decisione redazionale assistita nell'ambito del mandato di completamento, senza attribuire all'utente una lettura frase per frase. `independentHumanReview` resta `false`.

## Testi proposti

| Comune / anno | Italiano | Friulano — revisione assistita |
| --- | --- | --- |
| Andreis · 1981 | Apre al pubblico il Museo dell'Arte e Civiltà Contadina di Andreis | Al vierç al public il Museo dell'Arte e Civiltà Contadina di Andreis |
| Cimolais · 1930 | Viene inaugurato il Rifugio Pordenone in Val Cimoliana | Al ven inaugurât il Rifugio Pordenone in Val Cimoliana |
| Cimolais · 1985 | In Val Cimoliana viene reintrodotto lo stambecco | In Val Cimoliana il stambec al ven introdusût di gnûf |
| Sacile · 1190 | Sacile ottiene il privilegio di borghesia e le libertà comunali | Sacîl al oten il privileç di borghesie e lis libertât comunâls |

I nomi propri del museo, del rifugio e della valle restano quelli delle fonti, senza inventare denominazioni ufficiali friulane. Sacîl è già il toponimo FUR usato nel profilo comunale.

## Fonti e limiti delle affermazioni

- **Andreis:** l'Ente Parco colloca l'apertura del museo nel luglio 1981. Non riprendiamo il termine ambiguo relativo alla lavorazione dell'osso presente nella stessa pagina. Il nuovo fatto riguarda l'apertura, non le collezioni già raccontate nella scheda dei pettini. [Parco Naturale Dolomiti Friulane — Andreis](https://www.parcodolomitifriulane.it/i-paesi-del-parco/andreis/).
- **Rifugio Pordenone:** la storia CAI indica l'inaugurazione il **25 maggio 1930**. Il 1928 riguarda la decisione di costruirlo, il 1929 i lavori. Il rifugio si trova in Comune di **Cimolais**, non a Pordenone. Non sono introdotte informazioni attuali su apertura, posti letto o percorsi. [Storia CAI Pordenone](https://caipordenone.it/chi-siamo/storia/), [scheda del rifugio](https://caipordenone.it/strutture/rifugio-pordenone/), [cronologia PrenotaRifugi CAI](https://www.prenotarifugi.cai.it/en/detail/Rifugio%20Pordenone/?id=6000).
- **Stambecco:** la sezione Val Cimoliana della pagina del Parco documenta la reintroduzione nel 1985. La frase non attribuisce il progetto al Parco attuale né descrive la popolazione odierna. [Parco Naturale Dolomiti Friulane — Cimolais](https://www.parcodolomitifriulane.it/i-paesi-del-parco/cimolais/).
- **Sacile:** il portale turistico cittadino documenta il privilegio di borghesia e le libertà comunali nel 1190. Esclusi primati regionali non necessari e interpretazioni come nascita di uno Stato indipendente. Non tocchiamo le tappe esistenti del 796 e del 1420. [Visit Sacile — Storia della città](https://www.visitsacile.it/arte-storia-fede/storia/).

## Controllo FUR

I riferimenti puntuali e le motivazioni sono conservati nel file di revisione, uno per ogni tappa. Controllati il lessico di apertura e inaugurazione, `stambec`, `introdusût di gnûf`, `privileç`, `borghesie`, `libertât` e l'accordo `comunâls`. Per la specie animale è stata preferita una parafrasi: la traduzione di «reintrodurre» riferita a usanze non era pertinente.

Metodo: le voci SuperDizionari sono state lette nell'HTML restituito dal form pubblico di ricerca, comprese definizioni, traduzioni ed esempi; non sono state dedotte dai soli estratti del motore di ricerca. Il lettore Web non apriva direttamente alcuni permalink dei lemmi, mentre la richiesta HTTP al form pubblico riusciva. I permalink sono conservati come riferimenti alle voci.

Riferimenti principali: [SuperDizionari — stambecco](https://superdizionari.arlef.it/lemma/stambecco/57419?language=it&oneshot=1&gui=fur), [SuperDizionari — borghesia](https://superdizionari.arlef.it/lemma/borghesia/4461?language=it&oneshot=1&gui=fur), [ARLeF — Tiere](https://arlef.it/libris/tiere/).

## Ricerca conservata e conteggi dopo l'integrazione

La copia iniziale di ricerca conserva `label.fur: null`, `runtimeIntegration: false` e `readyForUi: false`. La revisione separata registra quattro approvazioni redazionali assistite; il manifesto collega i quattro nuovi ID al catalogo runtime. Fonti e fonti di supporto di ciascuna tappa arrivano anche al modello della scheda. La fonte generale del profilo viene usata soltanto per tappe preesistenti prive di una fonte propria.

| Indicatore | Prima del lotto | Dopo l'integrazione locale |
| --- | ---: | ---: |
| Profili comunali | 215 | 215 |
| Tappe totali | 407 | 411 |
| Profili con una tappa | 100 | 98 |
| Profili con due tappe | 38 | 38 |
| Profili con almeno tre tappe | 77 | 79 |

Andreis passa da una a due tappe, Cimolais da una a tre, Sacile da due a tre. Nessun profilo supera il limite attuale di tre tappe. I conteggi del backlog sono aggiornati a 411; `researchProgress` distingue le quattro candidate documentate dalle quattro promosse. I 136 profili ancora con una o due tappe restano nel piano, insieme alle altre rubriche.

## Verifiche della preparazione iniziale

- 46 test mirati superati in otto file: nuovo lotto (7), profili comunali, ricerca precedente, backlog, copertura e controlli di prontezza IT/FUR.
- Lint frontend completo superato; `git diff --check` senza errori.
- Catalogo dei 215 profili e 407 tappe invariato; nessun nuovo ID esposto nei modelli UI IT/FUR.
- Nessuna nuova build Android o Web: questo passaggio modifica soltanto ricerca, documentazione, backlog e test, non codice o dati runtime.

Questo elenco descrive la preparazione precedente all'integrazione. Le verifiche successive sono riportate nel [piano complessivo](SCOPRI_COMPLETION_PLAN_2026-08-31.md); i test del lotto ora verificano la promozione e non l'assenza dei quattro ID dal runtime.

## File e prossimo passo

- `frontend/src/data/discover/municipalityMilestoneResearch.pn-enrichment-01.json`: fatti, fonti, date escluse, duplicati e stato iniziale dei tre profili.
- `frontend/src/data/discover/municipalityMilestoneFurReview.pn-enrichment-01.json`: testi FUR, riferimenti linguistici e base della decisione editoriale assistita.
- `frontend/src/data/discover/municipalityMilestonePromotion.pn-enrichment-01.json`: quattro ID promossi e conteggi iniziali/finali distinti.
- `frontend/src/domain/discover/municipalityMilestoneResearch.pn-enrichment-01.test.js`: corrispondenza dei record promossi, fonti, geografia, conteggi e resa IT/FUR.

Proseguire con lotti bilanciati: altri Comuni, riti, detti, archivio e memorie secondarie. Non dichiarare completata Scopri per il solo inserimento di queste quattro tappe.

## Aggiornamento del 1 settembre 2026 — secondo lotto PN

Lotto `pn-enrichment-milestones-02`. Budoia passa da una a tre tappe; Fiume Veneto e Sesto al Reghena da due a tre.

| Comune / anno | Italiano | Friulano — revisione assistita |
| --- | --- | --- |
| Budoia · 1670 | Le autorità veneziane autorizzano le opere idrauliche a Dardago | Lis autoritâts venezianis a autorizin lis oparis idraulichis a Dardago |
| Budoia · 1870 | Apre la scuola femminile | E vierç la scuele feminîl |
| Fiume Veneto · 1911 | Un decreto reale aggiunge «Veneto» al nome Fiume | Un decret regâl al zonte «Veneto» al non Fiume |
| Sesto al Reghena · 899 | L'invasione degli Ungheri distrugge quasi completamente l'abbazia | La invasion ongjarese e distrûç cuasi dal dut la badie |

Le fonti ufficiali sono il [portale turistico comunale di Budoia](https://turismo.comune.budoia.pn.it/contenuti/430923/storia), la [storia del Comune di Fiume Veneto](https://www.comune.fiumeveneto.pn.it/it/cultura-23021/la-storia-26125) e la [pagina dell'Abbazia del Comune di Sesto al Reghena](https://www.comune.sesto-al-reghena.pn.it/labbazia/). Sono esclusi il primato del mulino, la presunta piena parità scolastica, la fondazione di Fiume Veneto nel 1911 e la ricostruzione dell'abbazia nello stesso anno della distruzione.

| Indicatore | Prima del lotto | Dopo l'integrazione locale |
| --- | ---: | ---: |
| Profili comunali | 215 | 215 |
| Tappe totali | 434 | 438 |
| Profili con una tappa | 90 | 89 |
| Profili con due tappe | 31 | 29 |
| Profili con almeno tre tappe | 94 | 97 |

Restano 118 profili con una o due tappe. Ricerca, revisione FUR e promozione sono conservate nei tre manifest del lotto; la base editoriale resta `user_delegated_assisted_editorial_review`, con `independentHumanReview: false`.

## Aggiornamento del 1 settembre 2026 — lotto GO/TS

Lotto `go-ts-enrichment-milestones-01`. Doberdò del Lago passa da una a tre tappe; Sgonico da due a tre.

| Comune / anno | Italiano | Friulano — revisione assistita |
| --- | --- | --- |
| Doberdò del Lago · 1179 | La località di Doberdò compare per la prima volta in un documento con il nome «Dobradan» | La localitât di Doberdò e comparìs pe prime volte intun document cul non «Dobradan» |
| Doberdò del Lago · 1524 | È documentata per la prima volta una comunità istituzionalizzata di Doberdò, indicata dalla fonte come župa | Pe prime volte e je documentade une comunitât istituzionalizade di Doberdò, che la font e indiche come župa |
| Sgonico · 1908 | La Grotta Gigante apre al pubblico con il percorso turistico | La Grotta Gigante e vierç al public cul percors turistic |

Le fonti sono la [storia del Comune di Doberdò del Lago](https://www.comune.doberdo.go.it/it/vivere-il-comune-96560/luoghi-96561/storia-156637), il [Catasto Speleologico Regionale FVG](https://catastogrotte.regione.fvg.it/scheda/2-Grotta_Gigante) e la [storia pubblicata dal gestore della Grotta Gigante](https://www.grottagigante.it/la-scoperta/). Sono escluse la nascita del Comune nel 1179, un'etimologia dedotta da `Dobradan`, l'equivalenza tra `župa` e Comune moderno e l'attribuzione dell'apertura della grotta all'amministrazione di Sgonico.

| Indicatore | Prima del lotto | Dopo l'integrazione locale |
| --- | ---: | ---: |
| Profili comunali | 215 | 215 |
| Tappe totali | 438 | 441 |
| Profili con una tappa | 89 | 88 |
| Profili con due tappe | 29 | 28 |
| Profili con almeno tre tappe | 97 | 99 |

Restano 116 profili con una o due tappe. Ricerca, revisione FUR e promozione sono conservate nei tre manifest del lotto; la base editoriale resta `user_delegated_assisted_editorial_review`, con `independentHumanReview: false`. Il prossimo lotto resta comunale.

## Aggiornamento del 1 settembre 2026 — secondo lotto UD/GO

Lotto `ud-go-enrichment-milestones-02`. San Daniele del Friuli e Staranzano passano entrambi da una a tre tappe.

| Comune / anno | Italiano | Friulano — revisione assistita |
| --- | --- | --- |
| San Daniele del Friuli · 1961 | Viene istituito il Consorzio del Prosciutto di San Daniele | Al ven istituît il Consorzio del Prosciutto di San Daniele |
| San Daniele del Friuli · 1996 | L’Unione europea riconosce il Prosciutto di San Daniele come DOP | La Union europeane e ricognòs il Prosciutto di San Daniele tant che DOP |
| Staranzano · 1848 | Staranzano diventa Comune anche sul piano amministrativo | Staranzan al devente Comun ancje sul plan aministratîf |
| Staranzano · 1907 | Staranzano si separa definitivamente da Monfalcone e riacquista l'autonomia comunale | Staranzan al si separe in maniere definitive di Monfalcon e al torne a jessi comun autonom |

La fonte di San Daniele è la [storia ufficiale del Consorzio del Prosciutto di San Daniele](https://prosciuttosandaniele.it/il-consorzio/il-consorzio/). Il 1961 riguarda l'istituzione del Consorzio, non la nascita del prodotto; il primato promozionale del Consorzio non viene ripreso. Il riconoscimento italiano del 1970 è verificato ma non promosso, perché la tappa DOP del 1996 rappresenta il passaggio europeo senza aggiungere due riconoscimenti consecutivi.

Per Staranzano si usano la [storia pubblicata dal Comune](https://www.comune.staranzano.go.it/it/novita-76815/notizie-76816/staranzano-storia-e-territorio-del-paese-82839) e il [PAESC comunale](https://www.comune.staranzano.go.it/media/files/md/031023/03594_PAESC_STARANZANO_DEFINITIVO-SIGNED.PDF). Non viene fissata al 1817 la nascita del Comune, che la fonte colloca nell'intervallo 1817–1820. Il 1867 resta escluso perché documenta la richiesta di aggregazione a Monfalcone, non esplicitamente l'atto concluso; il 1907 è invece la data documentata della separazione definitiva e del recupero dell'autonomia.

| Indicatore | Prima del lotto | Dopo l'integrazione locale |
| --- | ---: | ---: |
| Profili comunali | 215 | 215 |
| Tappe totali | 441 | 445 |
| Profili con una tappa | 88 | 86 |
| Profili con due tappe | 28 | 28 |
| Profili con almeno tre tappe | 99 | 101 |

Restano 114 profili con una o due tappe. Le altre rubriche non cambiano: 29 riti, 80 detti, 80 schede d'Archivio e 581 memorie.

Ricerca, revisione FUR e promozione sono conservate in `municipalityMilestoneResearch.ud-go-enrichment-02.json`, `municipalityMilestoneFurReview.ud-go-enrichment-02.json` e `municipalityMilestonePromotion.ud-go-enrichment-02.json`. La base editoriale resta `user_delegated_assisted_editorial_review`, con `independentHumanReview: false`. Rimuovendo i quattro nuovi ID, la baseline di 215 profili e 441 tappe restituisce il digest JSON `1820d7ffa63714130f5c573ba162a9a7c8b33e55683412c596e2412a810b1909`.

## Aggiornamento del 1 settembre 2026 — lotto UD/PN 05

Lotto `ud-pn-enrichment-milestones-05`. Aiello del Friuli, Cividale del Friuli e San Quirino passano tutti da una a tre tappe.

| Comune / anno | Italiano | Friulano — revisione assistita |
| --- | --- | --- |
| Aiello del Friuli · 1816 | Viene istituita la Fiera di San Carlo | E ven istituide la Fiere di San Carli |
| Aiello del Friuli · 1931 | Il Comune di Joannis viene soppresso e aggregato ad Aiello | Il Comun di Vuanis al ven sopress e agregât a Dael |
| Cividale del Friuli · 737 | Il patriarca Callisto trasferisce la propria sede a Cividale | Il patriarcje Calist al trasferìs la sô sede a Cividât |
| Cividale del Friuli · 1817 | Viene fondato il Museo archeologico di Cividale | Al ven fondât il Museu archeologjic di Cividât |
| San Quirino · 1499 | L'incursione turca incendia San Quirino e la sua chiesa | La incursion turche e met San Quarin e la sô glesie a fûc e sanc |
| San Quirino · 1807 | San Quirino entra nel Distretto di Pordenone del Regno d'Italia napoleonico | San Quarin al jentre tal Distret di Pordenon dal Ream d'Italie napoleonic |

Per Aiello si usano la [scheda comunale sulla Fiera di San Carlo](https://www.comune.aiellodelfriuli.ud.it/media/files/030001/attachment/Fiera_San_Carlo.pdf), il [censimento ISTAT del 1931](https://lipari.istat.it/digibib/Censimenti%20popolazione/censpop1931/VolumeIIIFascicoliProvinciali/IST0005870Fasc26_UDINE%2BOCRottimizz.pdf), una [pubblicazione storica comunale](https://www.comune.aiellodelfriuli.ud.it/media/files/030001/attachment/Progetto_Co-housing-BROCHURE_APPARTAMENTO_A.pdf) e [SIUSA](https://siusa-archivi.cultura.gov.it/cgi-bin/siusa/pagina.pl?Chiave=8939&TipoPag=prodente). La Fiera non viene chiamata patronale e non le viene attribuita una continuità annuale ininterrotta; Joannis resta correttamente il Comune soppresso e aggregato, non una frazione retrodatata.

Per Cividale la [relazione urbanistica comunale](https://comune.cividale-del-friuli.ud.it/media/files/md/030026/Elab.07_Relazione_illustrativa.pdf) documenta il trasferimento della sede di Callisto nel 737 e il [Ministero della Cultura](https://cultura.gov.it/luogo/museo-archeologico-nazionale-di-cividale-del-friuli) la fondazione del Museo archeologico nel 1817. La copy non fa partire il trasferimento da Aquileia e non retrodata l'attuale qualifica nazionale del museo. Il riconoscimento UNESCO del 2011 resta fuori dalle nuove tappe perché già presente nel riassunto del profilo; il 1420 non viene promosso per non comprimere fasi e uffici amministrativi documentati in modo diverso dalle fonti.

Per San Quirino le schede SIUSA della [Parrocchia](https://siusa-archivi.cultura.gov.it/cgi-bin/siusa/pagina.pl?Chiave=6979&RicDimF=2&TipoPag=prodente) e del [Comune](https://siusa-archivi.cultura.gov.it/cgi-bin/siusa/pagina.pl?Chiave=9327&TipoPag=prodente) documentano il 30 settembre 1499 e l'inquadramento amministrativo del 1807. La prima tappa non aggiunge vittime o distruzione totale; la seconda non presenta l'assetto napoleonico come nascita assoluta del Comune.

| Indicatore | Prima del lotto | Dopo l'integrazione locale |
| --- | ---: | ---: |
| Profili comunali | 215 | 215 |
| Tappe totali | 445 | 451 |
| Profili con una tappa | 86 | 83 |
| Profili con due tappe | 28 | 28 |
| Profili con almeno tre tappe | 101 | 104 |

Restano 111 profili con una o due tappe. Le altre rubriche non cambiano: 29 riti, 80 detti, 80 schede d'Archivio e 581 memorie.

Ricerca, revisione FUR e promozione sono conservate nei tre manifesti `municipalityMilestone*ud-pn-enrichment-05.json`. La base editoriale resta `user_delegated_assisted_editorial_review`, con `independentHumanReview: false`; `Vuanis`, `Dael`, `Cividât` e `San Quarin` sono verificati sui repertori ARLeF. Rimuovendo i sei nuovi ID, la baseline di 215 profili e 445 tappe restituisce il digest JSON `1350f4d09311ba0a5ae70a917a24658903030c124a1dbb980f61871838c61673`.

## Aggiornamento del 1 settembre 2026 — lotto UD 06

Lotto `ud-enrichment-milestones-06`. Lignano Sabbiadoro, Tolmezzo e Zuglio passano tutti da due a tre tappe.

| Comune / periodo | Italiano | Friulano — revisione assistita |
| --- | --- | --- |
| Lignano Sabbiadoro · 1903 | Viene costruito il primo stabilimento balneare di Lignano | Al ven costruît il prin stabiliment balneâr di Lignan |
| Tolmezzo · 1477–1479 | Viene costruita la Torre Picotta a difesa del borgo e del castello | E ven costruide la Torre Picotta par difindi il borc e il cjistiel |
| Zuglio · inizio XIX secolo | Iniziano i primi scavi sistematici nel Foro di Iulium Carnicum | A tachin i prins sgjâfs sistematics tal forum di Iulium Carnicum |

Per Lignano il [PRGC comunale](https://comune.lignano-sabbiadoro.ud.it/amministrazione/documenti-e-dati/amministrazione-trasparente/pianificazione-e-governo-del-territorio/varianti-al-prgc-1/variante-n-66-trasposizione-dello-strumento-urbanistico-su-nuovo-supporto-cartografico/relazione.pdf/@@download/file_principale) documenta nel 1903 la costruzione del primo stabilimento balneare; la [pagina comunale dei 120 anni](https://comune.lignano-sabbiadoro.ud.it/argomenti/turismo/120-anni) colloca al 15 aprile dello stesso anno il momento fondativo dei Bagni di Lignano. Non viene indicata l'apertura: un'altra cronologia comunale la data al 1904. Il 1903 non viene inoltre confuso con l'autonomia del Comune, già raccontata nel 1959.

La [cronologia del Comune di Tolmezzo](https://www.comune.tolmezzo.ud.it/localita-di-tolmezzo/) colloca tra il 1477 e il 1479 la costruzione della Torre Picotta, a difesa del borgo e del castello di fronte alla minaccia turca. La tappa conserva l'intervallo completo e non deduce né un completamento nel primo anno né una battaglia respinta dalla torre.

Il catalogo [ERPAC FVG del Museo archeologico Iulium Carnicum](https://patrimonioculturale.regione.fvg.it/museo/?s_id=440628) documenta all'inizio dell'Ottocento i primi scavi sistematici nel Foro, condotti dal Commissario di Guerra del Regno d'Italia e da studiosi carnici; la [storia del Comune di Zuglio](https://www.comune.zuglio.ud.it/it/home-2611/cultura-2614/la-storia-6506) conferma i primi scavi regolari nello stesso periodo. Non viene inventato un anno puntuale e il primato resta limitato agli scavi sistematici del Foro.

| Indicatore | Prima del lotto | Dopo l'integrazione locale |
| --- | ---: | ---: |
| Profili comunali | 215 | 215 |
| Tappe totali | 451 | 454 |
| Profili con una tappa | 83 | 83 |
| Profili con due tappe | 28 | 25 |
| Profili con almeno tre tappe | 104 | 107 |

Restano 108 profili con una o due tappe. Le altre rubriche non cambiano: 29 riti, 80 detti, 80 schede d'Archivio e 581 memorie.

Ricerca, revisione FUR e promozione sono conservate nei tre manifesti `municipalityMilestone*ud-enrichment-06.json`. La base editoriale resta `user_delegated_assisted_editorial_review`, con `independentHumanReview: false`; lessico e grafia FUR sono tracciati sui lemmi ARLeF e riusano modelli già approvati nel catalogo. Rimuovendo i tre nuovi ID, la baseline di 215 profili e 451 tappe restituisce il digest JSON `11a48c4a9b678c363647d2fd191eca113d5f6d255aa2b5f26ef34beaacb6fd27`.

## Aggiornamento del 2 settembre 2026 — lotto UD/PN 07

Lotto `ud-pn-enrichment-milestones-07`. Venzone, Polcenigo e Terzo d'Aquileia passano tutti da due a tre tappe.

| Comune / periodo | Italiano | Friulano — revisione assistita |
| --- | --- | --- |
| Venzone · 1258 | Inizia la costruzione della doppia cinta muraria di Venzone | E scomence la costruzion de dople cinte murarie di Vençon |
| Polcenigo · 1499 | L'incursione turca devasta Polcenigo | La incursion turche e vuaste Polcenic |
| Terzo d'Aquileia · XIV–XIII secolo a.C. | Nell'abitato di Canale Anfora è documentato il consumo di vino | Tal abitât di Canale Anfora al è documentât il consum di vin |

Per Venzone la scheda [ERPAC FVG sul circuito difensivo](https://patrimonioculturale.regione.fvg.it/architettura/?s_id=446567), sostenuta dal [percorso tematico regionale](https://patrimonioculturale.regione.fvg.it/percorso-tematico/?s_id=875161), attribuisce al 1258 l'inizio della costruzione della doppia cinta muraria. La tappa non trasforma l'avvio nel completamento e non presenta come integralmente originali le strutture oggi visibili, interessate da distruzioni e ricostruzioni.

Per Polcenigo la [pagina comunale del castello](https://www.comune.polcenigo.pn.it/it/vivere-il-comune-273915/luoghi-273916/castello-di-polcenigo-289700) e la [guida storico-naturalistica del Comune](https://www.comune.polcenigo.pn.it/media/files/md/093031/COMUNE_DI_POLCENIGO_Op_Scrignoverde.pdf) documentano l'incursione turca del 1499 e il borgo ridotto in macerie. La copy non attribuisce all'episodio la distruzione definitiva del castello o l'abbandono permanente dell'abitato.

Per Terzo d'Aquileia il [piano comunale dell'illuminazione](https://comune.terzodiaquileia.ud.it/media/files/md/030120/Piano_Comunale_di_illuminazione_web_1.pdf), con il riscontro dell'[Università di Udine](https://qui.uniud.it/ricerca-e-innovazione/3000-anni-fa-in-friuli-venezia-giulia-si-consumava-vino/), documenta residui di vino in una coppa presso un focolare dell'abitato di Canale Anfora, databile al XIV–XIII secolo a.C. La tappa attesta il consumo, non la produzione locale o la coltivazione della vite, e non estende il primato regionale indicato dalla fonte a un primato nazionale.

| Indicatore | Prima del lotto | Dopo l'integrazione locale |
| --- | ---: | ---: |
| Profili comunali | 215 | 215 |
| Tappe totali | 454 | 457 |
| Profili con una tappa | 83 | 83 |
| Profili con due tappe | 25 | 22 |
| Profili con almeno tre tappe | 107 | 110 |

Restano 105 profili con una o due tappe. Le altre rubriche non cambiano: 29 riti, 80 detti, 80 schede d'Archivio e 581 memorie.

Ricerca, revisione FUR e promozione sono conservate nei tre manifesti `municipalityMilestone*ud-pn-enrichment-07.json`. La base editoriale resta `user_delegated_assisted_editorial_review`, con `independentHumanReview: false`; lessico, grafia e toponimi FUR sono tracciati sui lemmi ARLeF. Rimuovendo i tre nuovi ID, la baseline di 215 profili e 454 tappe restituisce il digest JSON `be46c7f278861894c09dc2aed123eb1650cdc1527e402a300475742e03ae9ce2`.

## Aggiornamento del 2 settembre 2026 — lotto PN 08

Lotto `pn-enrichment-milestones-08`. Casarsa della Delizia, Montereale Valcellina e Pinzano al Tagliamento passano tutti da due a tre tappe.

| Comune / anno | Italiano | Friulano — revisione assistita |
| --- | --- | --- |
| Casarsa della Delizia · 1945 | A Versuta nasce l'Academiuta di lenga furlana | A Versute e nas la Academiuta di lenga furlana |
| Montereale Valcellina · 2011 | Viene inaugurato il Museo archeologico di Montereale Valcellina | Al ven inaugurât il Museu archeologjic di Montreâl |
| Pinzano al Tagliamento · 1525 | Il Pordenone dipinge la Madonna col Bambino nella chiesa di San Martino | Il Pordenone al piture la Madone cul Frutin te glesie di sant Martin |

Per Casarsa la [bibliografia della Società Filologica Friulana e del Centro Studi Pasolini](https://www.pasolinibibliografiafriulana.it/opere/academiuta-di-lenga-furlana_2728) documenta il 18 febbraio 1945 e una fondazione collettiva. La denominazione storica dell'Academiuta resta invariata.

Per Montereale il [notiziario di Forum Iulii XXXV, p. 234](https://museoarcheologicocividale.beniculturali.it/wp-content/uploads/2021/03/Forum-Iulii-XXXV-Notiziari.compressed.pdf) indica marzo 2011: non viene inventato il giorno. Il passo è stato consultato nell'estrazione indicizzata e il PDF verificato disponibile direttamente via HTTP 200. [ERPAC](https://patrimonioculturale.regione.fvg.it/museo/?s_id=440633) conferma Palazzo Toffoli come sede, distinta dal Museo dell'energia.

Per Pinzano la [scheda PromoTurismoFVG](https://www.turismofvg.it/it/71917/chiesa-di-san-martino-vescovo) data la singola Madonna col Bambino. Non si estende il 1525 agli altri affreschi e non si confonde San Martino con le chiese di Valeriano.

Il catalogo raggiunge **460 tappe uniche per 215 profili**: 83 con una tappa, 19 con due e 113 con almeno tre. Restano **102 Comuni** sotto soglia; le altre rubriche non cambiano.

Ricerca, revisione FUR e promozione sono conservate nei tre manifesti `municipalityMilestone*pn-enrichment-08.json`. La revisione è assistita, non certificata da ARLeF né professionale indipendente: `user_delegated_assisted_editorial_review`, `independentHumanReview: false`. Toponimi e lessico sono tracciati sui lemmi ARLeF, compresi Versute, Montreâl, Madone cul Frutin e sant Martin.

Rimuovendo i soli tre nuovi ID, la baseline di 215 profili e 457 tappe restituisce il digest JSON `cebb815e05b109e2963580bd214549c737e805b087d514ed2ec3cab7ee0ad0cf`.

## Aggiornamento del 2 settembre 2026 — lotto UD 09

Lotto `ud-enrichment-milestones-09`. Magnano in Riviera, Taipana e Tavagnacco passano tutti da due a tre tappe.

| Comune / anno | Italiano | Friulano — revisione assistita |
| --- | --- | --- |
| Magnano in Riviera · 1107 | Il castello di Prampero è documentato per iscritto | Il cjistiel di Prampar al è documentât par scrit |
| Taipana · 1931 | Il Comune di Platischis viene autorizzato a chiamarsi Taipana | Il Comun di Platiscjis al ven autorizât a clamâsi Taipane |
| Tavagnacco · 1512 | Pietro Fuluto dipinge la Madonna in trono a Cavalicco | Pietro Fuluto al piture la Madone in tron a Cjavalì |

Per Magnano il [notiziario del Consorzio Castelli FVG, marzo 2006, p. 2](https://consorziocastelli.it/biblioteca/pubblicazioni/notiziario/anno-2006/107.pdf) distingue la menzione del 1107 dalle ipotesi di fondazione. Lo snapshot UD zero 03 sulle date discordanti non viene riscritto.

Per Taipana la [Gazzetta Ufficiale](https://www.gazzettaufficiale.it/eli/id/1931/11/21/031U1382/sg) documenta l'autorizzazione al cambio di denominazione: decreto del 15 ottobre, pubblicazione del 21 novembre ed entrata in vigore del 6 dicembre 1931. Non è la nascita del Comune; nessuna delle tre date viene usata come equivalente delle altre.

Per Tavagnacco il [Comune](https://agenda.comune.tavagnacco.ud.it/Luoghi/Chiesa-antica-di-Cavalicco), con riscontro dell'[Istituto Pio Paschini](https://www.dizionariobiograficodeifriulani.it/fuluto-pietro/), data al 1512 la Madonna in trono. Non si attribuisce a Fuluto l'intero ciclo e non si confonde Cavalicco con Osais.

Il catalogo raggiunge **463 tappe uniche per 215 profili**: 83 con una tappa, 16 con due e 116 con almeno tre. Restano **99 Comuni** sotto soglia; le altre rubriche non cambiano.

Ricerca, revisione FUR e promozione sono conservate nei tre manifesti `municipalityMilestone*ud-enrichment-09.json`. La revisione è assistita, non certificata da ARLeF né professionale indipendente: `user_delegated_assisted_editorial_review`, `independentHumanReview: false`. Toponimi e lessico sono tracciati sui lemmi ARLeF, compresi Prampar, Platiscjis, Taipane, Cjavalì, documentât e autorizât.

Rimuovendo i soli tre nuovi ID, la baseline di 215 profili e 460 tappe restituisce il digest JSON `a41337b65f04e44330f441b842fd7ba4600f893f3d833941b40ac32ab9ef8223`.
