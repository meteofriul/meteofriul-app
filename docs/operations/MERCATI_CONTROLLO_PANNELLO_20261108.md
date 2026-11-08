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

L'archivio Firestore privato è alla **revisione 16**: 100 schede, 222 edizioni,
59 pratiche di ricerca, **21 selezionate**, 34 sospese e 45 bozze. I cinque
blocchi della revisione 15 sono stati letti e verificati contro lo SHA-256 del
puntatore. La revisione 16 è stata riletta con lo stesso controllo di integrità;
contiene l'orario aggiornato di M004 e `publicationReady: false` per quella
scheda. Prima della modifica, il validatore `publication_errors` non segnalava
campi obbligatori mancanti nelle 21 schede selezionate; tutte hanno
`directionsQuery`. Ora il pannello segnala **una convalida editoriale da rifare**
per M004, dopo aver chiarito la festività del 6 gennaio.
La **revisione pubblica è 0**. Il servizio rifiuta ancora la pubblicazione e
non serve un catalogo pubblico; l'app Web e Android distribuite sono invariate.
Nessun job è stato creato o riattivato. La prossima revisione generale rimane
manuale, il 7 febbraio 2027.

## Correzioni salvate nel catalogo privato

| Scheda | Decisione | Controllo e correzione |
| --- | --- | --- |
| M001 Pordenone | Sospesa | [Pagina comunale](https://www.comune.pordenone.it/it/argomenti/mercato/cittadino): area del centro, mercoledì/sabato 08:00–14:00 e indicazioni verso piazza XX Settembre. [Calendario comunale](https://www.comune.pordenone.it/it/argomenti/mercato/cittadino/determina-calendario-2026-2027.pdf/@@download/file): 26 dicembre 2026 annullato, 6 gennaio 2027 confermato. Verificare l'assetto dopo lo [spostamento temporaneo di alcuni banchi](https://www.comune.pordenone.it/it/novita/mercato-cittadino-spostamento-dei-banchi-in-piazza-xx-settembre) prima della selezione. |
| M002 Sacile | Selezionata | [Regolamento comunale](https://comune.sacile.pn.it/media/files/093037/attachment/Regolamento_CQcs8ay.pdf): giovedì, centro storico, vendita 08:15–13:00; destinazione piazza del Popolo. |
| M003 Codroipo | Selezionata | [Piano comunale](https://www.comune.codroipo.ud.it/media/files/md/030027/PIANO_SICUREZZA_MERCATO_CODROIPO.PDF): martedì mattina e vie del mercato; destinazione piazza Garibaldi. Nessun orario numerico inventato. |
| M004 San Daniele del Friuli | Selezionata, da riconvalidare | La [Pro San Daniele](https://www.infosandaniele.com/it/agenda/in-programma/mercato-settimanale-1) indica via Trento e Trieste e 08:00–13:00. Orario e fonte salvati nella revisione 16; la modifica ha tolto la precedente convalida editoriale. Resta da verificare il 6 gennaio 2027. |
| M005 Palmanova | Selezionata | [Comunicazione comunale 2026](https://www.comune.palmanova.ud.it/it/novita-179021/notizie-179022/lunedi-di-pasquetta-sui-bastioni-di-palmanova-6-aprile-2026-320575) e [atto posteggi](https://comune.palmanova.ud.it/media/files/030070/attachment/Allegato_B1.0.pdf): lunedì mattina, Piazza Grande e Contrada Donato; orario numerico vuoto. |
| R-PN-M004 Cordenons | Selezionata | [Delibera 2026](https://sac4.halleysac.it/c093017/zf/index.php/atti-amministrativi/delibere/dettaglio/atto/G9mpBd0TUWT0-A) e [delibera 2025](https://www.comune.cordenons.pn.it/media/files/093017/attachment/delibera_di_giunta_n._144-2025.pdf): venerdì, Piazza della Vittoria, vendita 08:00–13:00. Il 25 dicembre 2026 e il 1° gennaio 2027 sono marcati annullati per la normale ricorrenza del venerdì; l'eventuale anticipo resta da confermare. |
| R-PN-M012 Budoia | Selezionata | [Bando comunale per concessioni 2024–2033](https://comune.budoia.pn.it/media/files/093008/attachment/BANDO_COMUNE_DI_BUDOIA.pdf): mercoledì, Piazza Umberto I, 08:00–13:00; la [guida del Distretto 2026](https://www.distrettocommercioaltolivenza.it/alla-scoperta-delle-tradizioni-del-distretto-feste-sagre-e-mercati-storici-da-non-perdere/) conferma il mercato. |
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

## Blocco editoriale prima della prima pubblicazione

La convalida tecnica non conosce le chiusure festive. Nella revisione 16 le
seguenti ricorrenze selezionate cadono su date festive senza eccezione
documentata; il filtro **Oggi/Weekend** potrebbe quindi presentarle come
abituali se la pubblicazione avvenisse ora:

| Data | Schede da chiarire |
| --- | --- |
| 8 dicembre 2026 | M003, M021, M022, M023 |
| 25 dicembre 2026 | M022, M023 |
| 26 dicembre 2026 | M006, M022, M023 |
| 1° gennaio 2027 | M022, M023 |
| 6 gennaio 2027 | M004, M022, M023, R-PN-M012 |

Per M001 e R-PN-M004 le eccezioni già documentate sono state salvate come
edizioni annullate; ciò non conferma gli eventuali anticipi. Prima di aprire
il catalogo pubblico, controllare gli atti o gli avvisi dei gestori per le
date sopra, aggiungere solo eccezioni documentate, ricontrollare M001 e la
segnalazione di Maron, poi verificare la proiezione delle schede con anteprima
mobile e pulsante Indicazioni. Solo dopo seguono configurazione del servizio
pubblico, build Web/Android dallo stesso commit approvato, prove reali su
telefono e Safari/iPhone, PR e pubblicazioni distinte secondo i runbook.

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
