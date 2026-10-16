# Registro di integrazione delle fonti eventi — 6 ottobre 2026

Ramo di lavoro: `codex/events-discovery-audit`. Questo registro distingue una
fonte presente nel job da una fonte la cui copertura sia stata verificata.
Un commit di checkpoint conserva il lavoro, ma non promuove la fonte a
"terminata". Nessuna modifica di questo ramo e' distribuita da questo registro.

## Job comune e controllo contro le omissioni

Il job predefinito `pilot_cloud.publish` legge `source_adapters`, passa tutti
gli adattatori a `pilot_collection.collect`, applica i gate per fonte e salva
il catalogo. La lista autorizzata e' `pilot_source_policy.APPROVED_SOURCES`.
`test_pilot_source_registry.py` fissa esplicitamente i nomi integrati e li
confronta con entrambe le liste. `test_pilot_cloud.py` verifica che il job
predefinito passi **tutte** le fonti registrate alla raccolta. Quando una
fonte sara' pronta, occorrera' aggiornare deliberatamente registro, lista
autorizzata, adattatore e test; ometterne uno fara' fallire il controllo.

## Una sola scheda per lo stesso evento

La consultazione del catalogo deduplica automaticamente i record verificati
delle diverse fonti. L'identita' richiede stessa data o periodo, comune,
titolo, orario e sede dichiarata; le coppie particolari gia' verificate
(sagre, Villa Manin e Magazzino delle Idee) mantengono le loro regole
specifiche. Un titolo generico senza prova sufficiente, una sede diversa o
due orari diversi non autorizzano una fusione: potrebbero essere incontri
distinti. I programmi di Pordenonelegge e Cinema Muto conservano la scheda
unica con le sessioni ordinate.

Tra due record dello stesso evento vince la scheda della fonte diretta;
fra record con autorita' equivalente contano la precisione del luogo e i
dati verificati. Se la scheda scelta manca di immagine o anteprima, puo'
ricevere il campo disponibile dall'altra fonte, mantenendo nome, URL e data
del controllo della descrizione. Entrambi gli URL restano nella provenienza,
ma il risultato pubblico e' **una sola scheda**. La deduplicazione avviene
dopo il filtro per data e raggio, prima della proiezione dei programmi.
L'integrazione MESS riconcilia esplicitamente il laboratorio del 28 novembre
gia' coperto da TurismoFVG, anche se le due pagine hanno titoli diversi; una
somiglianza generica non basta.

Il [controllo reale del 7 ottobre](EVENTI_AUDIT_DOPPIONI_FONTI_2026-10-07.md)
ha aggiunto il confronto fra programmi teatrali ufficiali e intervalli
regionali, le sagre regionali e i periodi discordanti verificati. Sul catalogo
locale di dodici fonti, 1.851 record diventano 1.776 prima del filtro per
posizione; le sovrapposizioni tra rassegna e singolo incontro restano distinte.

La successiva prova locale completa del 7 ottobre, dopo l'integrazione di
MESS e Galleria Spazzapan e la correzione del filtro sitemap di Teatro Verdi
Trieste, ha restituito **14 fonti `fresh` su 14** in **386,92 secondi**, senza
revisioni. Usa il checkpoint annuale TurismoFVG gia' verificato e non
pubblica dati cloud. Il primo ciclo distribuito da catalogo vuoto resta una
verifica separata prima della promozione del ramo.

L'integrazione successiva di Barcolana ha portato il job a **15 fonti**.
Nel ciclo locale del 7 ottobre, prima delle correzioni successive, Barcolana
e' `fresh`, ma il totale e' **12 fonti `fresh` su 15**: TurismoFVG e' andato
in timeout, Teatro Verdi Pordenone ha rifiutato un URL di paginazione con
`gclid`, e SagreFVG ha fermato una nuova scheda senza provincia nel titolo.
Le tre fonti sono state poi corrette e verificate isolatamente. Una prima
ripetizione del ciclo ha trovato il limite di tempo di CSS Udine, anch'esso
corretto. La [seconda ripetizione locale](EVENTI_CICLO_15_FONTI_2026-10-07.md)
ha restituito **15/15 fonti `fresh` in 435,89 secondi**, zero revisioni e
nessun timeout. Dettagli nel
[seguito Barcolana](EVENTI_BARCOLANA_INTEGRAZIONE_2026-10-07.md).

## Stato delle fonti

| Fonte | Nel job predefinito | Stato di questo audit | Prossimo controllo |
| --- | --- | --- | --- |
| TurismoFVG | Si' | Prima scansione annuale del 7 ottobre: 2.395 URL, 1.418 schede, 1.308 anteprime. La successiva prova live, usando direttamente le finestre annuali verificate, ha letto 2.445 URL, 1.468 schede e 1.356 anteprime, zero revisioni; 217,13 secondi entro il limite della fonte. Il ciclo completo ripetuto passa in 167,13 secondi. Da catalogo vuoto, l'8 ottobre controlla 960/2.433 dettagli in 319,28 secondi, conserva il checkpoint e non pubblica schede parziali | Preparare un checkpoint completo per il primo ciclo distribuito e provarlo nell'app prima della promozione. [Tempo del job](EVENTI_TURISMOFVG_JOB_TEMPO_2026-10-07.md), [avvio locale](EVENTI_COLD_START_LOCALE_2026-10-08.md). |
| Pordenonelegge | Si' | Scheda unica con programma scorrevole; riconoscimento automatico dell'edizione e controllo della copertura del calendario nel job | Verifica visiva su dispositivo con un'edizione futura disponibile; sorvegliare il primo cambio d'anno del programma. |
| Le Giornate del Cinema Muto | Si' | Calendario HTML ufficiale integrato: dieci pagine e 87 blocchi di programma nel 2026; una scheda con lista scorrevole e gate di copertura; vista nel browser pilot su telefono | Verifica nell'APK con catalogo pubblicato e controllo del primo cambio di edizione; le proiezioni senza sede esplicita restano associate al solo comune. |
| Azalea | Si' | Archivio ufficiale, dettagli e sitemap verificati il 7 ottobre: 13 schede, 7 eventi FVG futuri, 7 anteprime e 7 immagini; gate automatico sui conteggi e sulle modifiche fuori archivio | Verificare il primo ciclo distribuito; sorvegliare eventuali pagine future non presenti ne' nell'archivio ne' nella sitemap. |
| CSS Udine | Si' | Homepage e cinque stagioni verificate il 7 ottobre: 122 schede distinte e altrettanti dettagli; 95 con date future e comune preciso, 161 repliche, tutte con anteprima e immagine; esclusi i testi di servizio nelle anteprime. Dopo un timeout a 45 secondi nel ciclo condiviso, il riuso delle connessioni ha portato la prova attraverso il job a 10,04 secondi e il ciclo completo a 6,36 secondi, entrambi `fresh` | Verificare il primo ciclo distribuito; prove sul telefono rinviate su richiesta dell'utente. [Tempo del job](EVENTI_CSS_TEMPO_JOB_2026-10-07.md). |
| Pordenone Pensa | Si' | API e sitemap ufficiali riconciliati il 7 ottobre: 235 post, 9 pagine, un annuncio futuro con prima data provata; gate automatico | Verificare il primo ciclo distribuito; acquisire le altre date dell'ABC solo quando saranno pubblicate. |
| Teatro Verdi Pordenone | Si' | Elenco di stagione e API pubblica riconciliati il 7 ottobre: 64 spettacoli; 94 dettagli recenti verificati, 88 repliche future con anteprima e immagine. Un parametro pubblicitario `gclid` nei link di paginazione e' rimosso solo dopo averlo riconosciuto; la raccolta live successiva passa il gate in 34,61 secondi e il ciclo completo ripetuto in 36,54 secondi | Verificare il primo ciclo distribuito; prove sul telefono rinviate. |
| Teatro Verdi Trieste | Si' | Calendario, API della stagione, sitemap e 22 dettagli riconciliati il 7 ottobre: 73 repliche future, 30 con anteprima testuale e 73 con immagine. Il filtro sitemap controlla nuove schede italiane, escludendo gli indici e le traduzioni | Verificare il primo ciclo distribuito; prove sul telefono rinviate. |
| Villa Manin | Si' | API completa, archivio annuale, tessere Eventi e tre dettagli futuri riconciliati il 7 ottobre: cinque date future, cinque anteprime e quattro immagini; gate automatico | Verificare il primo ciclo distribuito e sorvegliare il passaggio all'archivio 2027; prove sul telefono rinviate. |
| Magazzino delle Idee | Si' | API completa, sitemap, archivio 2026, elenchi Mostre/Eventi e dettaglio riconciliati il 7 ottobre: una mostra attiva con anteprima e immagine; gate automatico anche sulla data della tessera Mostre | Verificare il primo ciclo distribuito e il prossimo cambio dell'archivio annuale; prove sul telefono rinviate. |
| ERPAC (portale generale) | No | Homepage esaminata il 7 ottobre: indice editoriale di otto tessere, con rinvii a siti di musei diversi; non e' un inventario completo autonomo | Usare le tessere per confrontare gli audit separati dei poli e individuare nuove schede. |
| DAG - Digital Art Gallery Gorizia | No | Scheda ERPAC e pagina di accesso lette il 7 ottobre: installazione visitabile con orari e prenotazione fino al 31 dicembre 2026, senza programma di eventi distinto | Escludere dalle schede Eventi secondo il criterio "solo eventi con programma"; rivalutare eventuali mostre o appuntamenti con scheda e data proprie. |
| Palazzo Attems Petzenstein | No | Controllo diagnostico aggiunto al codice del job su questo ramo, non ancora distribuito, senza nuove schede: 27 Eventi, 25 nella categoria, una mostra corrente, 41 notizie 2026; due schede attive irrisolte e un avviso di annullamento futuro. La scheda regionale di ottobre contiene gia' parte del programma, quindi va evitata una copia | Riconciliare sede e programma per appuntamento, annullamento e doppioni prima di integrare. [Audit Palazzo Attems](EVENTI_PALAZZO_ATTEMS_AUDIT_2026-10-07.md). |
| Galleria Spazzapan | Si' | API Eventi (3), categoria Eventi (2), Mostra in corso (4), Mostra (7) e Notizia (77) riconciliate; quattro schede distinte, con date dei dettagli prioritarie rispetto ai due campi strutturati errati. Gate su inventari, notizie e prove di sede; una duplicazione TurismoFVG risolta | Sorvegliare nuovi articoli e cambio programma; test sul telefono rinviati. [Audit Spazzapan](EVENTI_SPAZZAPAN_AUDIT_2026-10-07.md). |
| Musei Provinciali di Gorizia (portale) | No | Homepage e quattro categorie confrontate il 7 ottobre: API Eventi con un appuntamento del 2023 e una scheda di prova senza data; categorie Eventi/Mostra senza schede correnti; mostra Italia Settanta rinviata a Palazzo Attems | Conservare come indice diagnostico dei poli, senza adattatore autonomo; verificare i singoli musei/siti quando pubblicano programmi propri. |
| MESS | Si' | API ufficiale: 36 date, compreso il 28 novembre scritto `novenbre`; 18 sedi, due incontri ciascuna. Gate su programma, sedi e 51 notizie; 3 mostre attive corroborate con TurismoFVG. Sedici laboratori futuri, raggruppati in 9 schede per museo | Sorvegliare nuovi articoli e cambio edizione; test sul telefono rinviati. [Audit MESS](EVENTI_MESS_AUDIT_2026-10-07.md). |
| Paesi in Festa | Si' | Due liste, cinque indici e delta del sitemap con acquisizione delle schede complete; audit iniziale dei post pubblici senza eventi FVG attivi omessi | Sorvegliare cambiamenti di struttura e la pagina Carnevale provvisoria. |
| EventiFVG | No | Decisione: chiuso come fonte autonoma; resta indice diagnostico di scoperta | Incrociare i candidati con fonti che provano data e comune; rivalutare solo se emergono molti eventi FVG unici e verificabili. |
| SagreFVG | Si' | Primo ricontrollo: 944 record 2026, 28 attivi. Dopo la nuova Festa del Borgo di San Leonardo, la raccolta live legge 945 record in 19 pagine e 29 schede attive con zero revisioni; il comune senza sigla nel titolo e' provato dai campi della sede e il gate passa in 42,43 secondi. Il ciclo completo ripetuto passa in 38,23 secondi. Camporosso assegnato a Tarvisio; Gonars 10-11 ottobre provato dal programma | Verificare il primo ciclo distribuito; sorvegliare cambiamenti del formato e date discordanti. [Ricontrollo SagreFVG](EVENTI_SAGREFVG_RECHECK_2026-10-07.md). |
| [Pro Loco FVG](https://prolocoregionefvg.it/eventi-delle-associate/) | Monitor diagnostico nel job del ramo; nessuna scheda aggiunta | Audit del 7 ottobre: 6 pagine, 54 tessere, 32 dettagli; tutti coperti da TurismoFVG (30 titoli uguali, 2 alias verificati). Il monitor leggero confronta ogni tessera dell'indice con data, comune e titolo regionali; zero anomalie nella prova live | Verificare il primo ciclo distribuito. [Audit Pro Loco](EVENTI_PROLOCO_FVG_AUDIT_2026-10-07.md). |
| [Anteprima Sagre](https://www.anteprimasagre.it/) | Monitor diagnostico nel job del ramo; nessuna scheda aggiunta | API e sitemap: 1.397 post; 347 aggiornati nel 2026. Al 7 ottobre nessun post pubblico recente prova una data futura; Pan-Zal dichiara esplicitamente che le date 2026 non sono comunicate. Monitor completo dell'orizzonte 2025-2026: 419 post pubblici, zero date future provate, una quarantena nota | Rivedere automaticamente ogni nuova data futura o modifica di Pan-Zal prima di pubblicare; primo ciclo distribuito ancora da verificare. [Audit Anteprima](EVENTI_ANTEPRIMA_SAGRE_AUDIT_2026-10-07.md). |
| [GiroFVG](https://www.girofvg.com/) | Monitor diagnostico nel job del ramo; nessuna scheda aggiunta | La prova live dell'8 ottobre legge 12.297 URL della sitemap, 89/90 pagine e 1.793 tessere delle sette categorie in 19,36 secondi, compreso il ricontrollo finale; zero cambiamenti da revisionare. La pagina storica in HTTP 500 resta esclusione esplicita, quindi `source_complete=false`. Date, anteprime e immagini GiroFVG non vengono pubblicate; Nave Vespucci e' gia' nel programma ufficiale Barcolana | Verificare il primo ciclo distribuito e sorvegliare i candidati nuovi o mutati, confermandoli dalla fonte diretta. [Monitor](EVENTI_GIROFVG_MONITOR_2026-10-08.md). |
| [Barcolana](https://www.barcolana.it/it/calendario-eventi) | Si', sul ramo di audit; non distribuita | Fonte ufficiale preferita: 671 appuntamenti dopo nove doppioni, piu' tre voci regionali mancanti, in una scheda con programma, immagine e anteprima 2026; 680 righe di calendario contro 681 URL sitemap e una pagina 404 verificata. Cinque programmi giornalieri, il Museo del Mare e due talk sono riconciliati automaticamente con l'HTML regionale; prova live e gate verdi in 8,45 secondi; ciclo locale a 15 fonti `fresh` in 435,89 secondi | Restano sei iniziative regionali distinte e non duplicate. Primo ciclo distribuito e prova reale nell'app prima della promozione. [Integrazione](EVENTI_BARCOLANA_INTEGRAZIONE_2026-10-07.md). |

L'ordine concordato per le prossime verifiche e' Pro Loco FVG, Anteprima Sagre,
SagreFVG e GiroFVG, una fonte alla volta. SagreFVG e' gia' nel ramo ma non nel
catalogo online: verra' ricontrollata prima del rilascio. I portali locali di
Gorizia, Trieste e Udine restano una successiva ricerca di siti candidati,
senza considerare l'elenco attuale esaustivo.

Nell'audit Pro Loco FVG, la scheda della Sagra della Castagna di
Mezzomonte mostra cinque giorni nel campo "Quando", mentre il testo annuncia
anche il 25 ottobre. La scheda Festa d'Autunno di Gonars mostra 10 ottobre
nel campo "Quando" e 11 ottobre nel testo. Le rispettive pagine TurismoFVG
confermano [sei giorni per la Sagra](https://www.turismofvg.it/eventi/40%C2%AA-sagra-della-castagna)
e [10-11 ottobre per Gonars](https://www.turismofvg.it/eventi/festa-d-autunno-504304),
ma la discordanza interna a Pro Loco vieta di copiare automaticamente il
campo `Quando`. Alcune immagini restituiscono `/media/not-found`. Il nuovo
monitor segnala eventi dell'indice non coperti dalla scheda regionale e
lascia Pro Loco fuori dalle schede pubbliche per evitare doppioni.

Per TurismoFVG, il [controllo annuale](EVENTI_TURISMOFVG_ANNUAL_CONTROL_2026-10-06.md)
ha chiuso le quarantene della [revisione iniziale](EVENTI_TURISMOFVG_REVIEW_55_2026-10-05.md).
L'adattatore del job usa lo stesso inventario annuale e salva un checkpoint
compresso nel catalogo pilot. La sorgente diventa visibile solo quando
`source_complete=true`, il gate indipendente riproietta tutte le schede e non
restano URL in revisione. Una scansione parziale conserva il progresso ma non
pubblica schede TurismoFVG. Il ramo non e' stato distribuito.

Il [test del primo avvio del 7 ottobre](EVENTI_TURISMOFVG_COLD_START_2026-10-07.md)
ha trovato un totale del calendario mutato durante la paginazione. Il ramo
usa ora direttamente finestre datate con unione controllata. Una prova delle
finestre ha riconciliato 2.478 tessere; il primo ciclo ha salvato 384
dettagli e 2.055 pendenti. Il checkpoint e' stato poi completato e il ciclo
locale di 15 fonti e' passato. Nessun dato di questi test e' stato
pubblicato; il primo avvio distribuito resta da verificare.

La [homepage delle Giornate del Cinema Muto](https://www.giornatedelcinemamuto.it/)
indica per l'edizione 2026 il festival a Pordenone dal 3 al 10 ottobre.
L'[annuncio ufficiale](https://www.giornatedelcinemamuto.it/le-giornate-del-cinema-muto-45a-edizione/)
aggiunge la preapertura del 2 ottobre a Sacile e la replica dell'11 ottobre.
Il `page-sitemap.xml` pubblico espone dieci pagine `calendario-DDMMYY/`, una
per ciascun giorno dal 2 all'11 ottobre. L'adattatore legge quelle pagine HTML
e verifica che l'intestazione e l'anno di ogni pagina coincidano con l'URL e
con le date dell'edizione. I 97 widget di contenuto contengono dieci titoli
giornalieri e **87 blocchi di programma con orario**. Alcuni blocchi elencano
piu' film: il conteggio indica sessioni di calendario, non singoli film.
Le pagine `eventi-serali-DDMMYY/` descrivono appuntamenti gia' presenti nel
calendario e non aggiungono schede. Non si scaricano PDF.

Il job registra la fonte ufficiale come decima fonte e pubblica una sola scheda
per l'edizione, con le sessioni ancora attive ordinate per giorno e ora e
collegate alla pagina ufficiale del rispettivo giorno. La scheda mostra
separatamente le date principali 3–10 ottobre; il periodo complessivo 2–11
include preapertura e replica. La localita' della preapertura e' Sacile;
per i blocchi senza sede esplicita si usa Pordenone senza inventare un teatro.
L'esatta [scheda TurismoFVG](https://www.turismofvg.it/eventi/45-le-giornate-del-cinema-muto)
del 2026 puo' fornire immagine e descrizione con attribuzione, solo quando
comune e date 3–10 coincidono: viene fusa nella stessa scheda, non duplicata.
Se la scheda regionale non passa il suo gate, il programma ufficiale resta
visibile senza una descrizione inventata. Il gate della fonte confronta sitemap,
giorni, URL, widget e sessioni; rifiuta un giorno mancante, una struttura
sconosciuta o un calo oltre il 10% dei blocchi nella stessa edizione.
La prova reale del 6 ottobre ha acquisito 87 blocchi in 11,24 secondi; il gate
ne conserva 60 dal giorno corrente in avanti. La copertura dimostrata riguarda
le pagine di calendario esposte nel sitemap: eventuali contenuti non pubblicati
li' o annunciati solo fuori calendario richiedono un controllo editoriale.
Nel browser pilot avviato dallo script canonico sulla porta 5174 e aperto su
un telefono Android via USB, il catalogo locale di sola lettura ha mostrato
una scheda prioritaria a Pordenone, 60 appuntamenti, le date principali
separate e la lista scorrevole fino all'11 ottobre. Il test ha fatto emergere
un contrasto insufficiente per conteggio e orari nel tema scuro, corretto e
ricontrollato sul telefono. Il pilot meteo usava l'orologio deterministico del
4 settembre per gli snapshot offline; Eventi usava la data reale del 6 ottobre.
Questa e' una prova della UI browser, non dell'APK nativo o della pubblicazione
del catalogo.

Per Paesi in Festa, il controllo del 6 ottobre ha trovato 17 URL unici nella
[lista Sagre](https://paesiinfesta.com/sagre-in-friuli-venezia-giulia-e-veneto-orientale/)
e 7 nella [lista Rievocazioni](https://paesiinfesta.com/rievocazioni-storiche/).
Sono 24 **pagine**, non 24 singoli eventi. Le 17 sagre espongono date visibili
e `Event` JSON-LD concordanti; le 7 rievocazioni hanno date e introduzione
visibili ma non `Event` JSON-LD. La [pagina Presepi](https://paesiinfesta.com/appuntamenti-con-i-presepi/)
ha intestazione e metadati 2025–2026, mentre il programma contiene 11 voci
2026–2027. La [pagina Carnevale](https://paesiinfesta.com/carnevale-in-piazza/)
raggruppa sfilate in luoghi diversi e dichiara l'uso del calendario precedente.
La raccolta ora legge le due liste e 21 schede FVG collegate in 44,7 secondi.
Il gate ha accettato 22 eventi futuri o in corso, senza schede in revisione:
13 schede individuali e 9 appuntamenti con Presepi aventi ciascuno date e
localita' proprie. Delle 6 esclusioni motivate, 3 sono schede venete,
1 e' il Presepe di Annone Veneto, 1 e' il Presepe di Spilimbergo con soli mesi
senza giorni esatti, 1 e' il calendario Carnevale dichiarato provvisorio.
Le anteprime provengono dal testo della scheda o da un sottotitolo distinto
quando presente, con URL e nome della fonte; nessuna descrizione viene creata
per riempire un campo vuoto. Sagre e rievocazioni hanno regole distinte per
titolo, date e anteprima. Le date della lista sono confrontate con quelle della
scheda e, per le sagre, con `Event` JSON-LD; una discordanza ferma l'intera
fonte. I due riepiloghi non sono pubblicati come un unico evento con un unico
luogo. Il job comune ammette un budget massimo di 875 secondi. Dopo
l'aggiunta del monitor GiroFVG le quote configurate sommano 835 secondi:
360 TurismoFVG, 90 Paesi in Festa, 60 SagreFVG, 20 Pordenonelegge,
25 Pordenone Pensa, 30 Cinema Muto, 20 Azalea, 20 CSS Udine,
50 Teatro Verdi Pordenone,
25 Teatro Verdi Trieste, 65 Villa Manin, 30 Magazzino delle Idee, 10 MESS,
10 Galleria Spazzapan e 20 Barcolana.
Sono limiti per fonte, non durate previste; il primo ciclo
distribuito deve ancora confermare il margine del job cloud da 900 secondi.

Il 6 ottobre e' stato esaminato anche il [sitemap pubblico](https://paesiinfesta.com/sitemap_index.xml):
tre file contengono 594 post, di cui 561 con percorso FVG o alla radice. Dei
post non presenti nelle liste, 529 avevano una data di fine gia' passata e
11 erano pagine video/editoriali senza un calendario evento. Le due schede
del 2027 viste nell'[archivio regionale](https://paesiinfesta.com/friuli-venezia-giulia/)
erano gia' nella lista Sagre. Il confronto delle schede FVG ancora attive
su home, archivio regionale, pagine provinciali di Udine e Pordenone e prima
pagina dell'[Archivio](https://paesiinfesta.com/archivio/) non ha trovato
URL mancanti. Il programma Miss pubblica ancora date del 2024; la pagina
"Sagre oggi" contiene testo informativo e un riquadro di appuntamenti gia'
presenti nella home.

L'adattatore ora legge automaticamente queste cinque superfici insieme alle
due liste: una scheda FVG attiva presente solo in un indice entra nella stessa
verifica di titolo, date e dettaglio; date, titolo, localita' o categoria
discordanti fermano la fonte. L'Archivio viene controllato solo nella prima
pagina, per non leggere quotidianamente 24 pagine di eventi passati. Il job
legge anche i tre file XML del sitemap e apre **solo i post modificati dopo
la base verificata del 6 ottobre** che non sono gia' nelle liste o negli
indici. Se uno di questi contiene date ancora attive o non interpretabili,
la sua scheda viene letta: entra nel catalogo quando prova titolo, programma,
date e comune FVG. Per le sagre, le date visibili devono coincidere con
`Event` JSON-LD; per le rievocazioni si usano le due date esplicite e la
localita' della scheda. L'anteprima usa il testo introduttivo o la descrizione
specifica della pagina, se disponibile. Un conflitto o una possibile doppia
scheda per lo stesso luogo e periodo resta in revisione e ferma la fonte.
I test coprono entrambi i formati; due schede reali gia' note, Le Radici del
Vino e Un giorno con Napoleone, sono passate anche nel nuovo lettore di
dettaglio isolato dal sitemap con titolo, comune, date e anteprima corretti.
Nella prova live: 13 URL FVG attivi distinti negli indici, zero URL extra,
zero modifiche del sitemap da esaminare, 22 eventi accettati, zero revisioni,
52,4 secondi entro i 90 previsti. La copertura verificata riguarda i post
pubblici del sitemap e le superfici qui elencate; un contenuto non esposto ne'
nel sitemap ne' in queste pagine non puo' essere provato da questo controllo.

## EventiFVG: indice di scoperta, non fonte autonoma

Il vecchio lettore `engine.fetch_eventifvg_events` prende la home, filtra i
primi risultati e completa date prive d'anno con l'anno corrente: non e' una
prova di copertura. Il sito espone invece
[`/wp-json/tribe/events/v1/events`](https://www.eventifvg.it/wp-json/tribe/events/v1/events)
con dati strutturati, totale e paginazione. Il limite effettivo e' 50 record
per pagina. Al 6 ottobre 2026 l'audit diagnostico ha letto 287 ID distinti,
ordinati in 6 pagine, dal 6 ottobre 2026 al 30 agosto 2027. Verifica
automaticamente totale, numero e dimensione delle pagine, ID/URL unici,
ordinamento, date e risposta JSON. Non pubblica nessun evento.

La [documentazione del plugin](https://docs.theeventscalendar.com/reference/classes/tribe__events__rest__v1__endpoints__archive_event/read_args/)
specifica che `start_date` seleziona gli eventi **iniziati dopo** la data
indicata. Quindi l'API futura non copre da sola eventi gia' iniziati ma ancora
aperti. Una scansione dal 1 gennaio 2026 conterebbe 4.876 record, circa 98
pagine, troppo ampia per aggiungerla senza un bootstrap e una cache verificata
al job quotidiano. Le viste giornaliere provate non hanno aggiunto una prova
affidabile degli eventi plurigiorno gia' avviati.

La localita' e' l'altro blocco. Dei 287 record futuri, solo 62 hanno un comune
FVG verificabile nei campi strutturati del luogo o nell'indirizzo; 8 indicano
esplicitamente un Paese estero; 217 restano senza comune dimostrabile con
questi campi. Non si puo' usare la categoria provinciale come sostituto:
la [scheda Le Radici del Vino](https://www.eventifvg.it/evento/le-radici-del-vino-2026/)
ha luogo a Rauscedo ma l'API la classifica in "Udine e Provincia". Le schede
HTML campionate espongono gli stessi dati di luogo dell'API, senza un comune
aggiuntivo. L'audit risolve Rauscedo tramite la corrispondenza gia' verificata
con Paesi in Festa; non deduce il comune da "Via Udine".

Infine il [sito EventiFVG](https://www.eventifvg.it/) vieta la riproduzione
anche parziale dei testi senza autorizzazione. Il lettore diagnostico non
salva o ripubblica descrizioni. Per un'anteprima in app occorre usare testo
autorizzato dalla fonte primaria oppure un contenuto originale basato su fatti
strutturati, dopo una decisione editoriale esplicita.

Decisione del 6 ottobre: EventiFVG **non entra come fonte autonoma nel job**.
L'audit API rimane eseguibile come indice di scoperta e segnala URL con luogo
incerto; non genera schede pubblicabili. Un candidato puo' essere usato solo
quando una fonte primaria o un'altra scheda verificata prova data e comune.
I candidati senza prova restano nel rapporto diagnostico e non ricevono una
posizione inventata. Le anteprime vanno prese da testo autorizzato della fonte
primaria. La decisione si puo' riaprire se il rapporto mostra molti eventi
FVG unici e verificabili. Un'eventuale integrazione autonoma richiederebbe
anche la scansione iniziale degli eventi gia' in corso, la rivalidazione dei
luoghi e una nuova revisione del budget del job, ora fissato a quattordici fonti e 875
secondi. Questo e' un esito conclusivo dell'audit del sito, non una
certificazione di completezza del suo calendario.

## SagreFVG: API annuale e anteprime

La [lista Sagris](https://sagrefvg.it/sagris/) usa il calendario The Events
Calendar. Il vecchio lettore dell'app pescava poche schede in base alla citta'
richiesta. Il nuovo adattatore legge invece **tutte le pagine dell'anno in
corso**, filtra soltanto dopo aver verificato la data di fine e prosegue per
anni futuri finche' trova due anni consecutivi vuoti e un overflow vuoto.
Questo include le sagre gia' iniziate, che un filtro API dalla data odierna
perderebbe. Controlla conteggi, dimensione delle pagine, ID e URL unici,
ordinamento e date. Il gate rifiuta la fonte se una scheda attiva resta in
revisione o se la prova di copertura non quadra.

Nella prova reale del 6 ottobre 2026, l'API ha esposto 940 schede del 2026
in 19 pagine; 916 erano terminate e 24 ancora in corso o future. Il 2027 e il
2028, oltre all'intervallo successivo, erano vuoti. Tutte le 24 schede attive
hanno superato titolo, comune, provincia e coordinate; quelle senza coordinate
del luogo usano il centro del comune verificato e sono marcate come posizioni
approssimative. Tutte e 24 hanno un'anteprima breve attribuita a SagreFVG,
ricavata dal testo della rispettiva scheda. La raccolta con gate ha impiegato
37,7 secondi, entro il budget di 60. Il nome della festa e' separato dal
prefisso di localita' del titolo sorgente, che resta tracciato in `source_title`.

Questa prova certifica la scansione dell'API nell'orizzonte dichiarato. Un
confronto con eventuali nuove sezioni del sito e con gli eventi sovrapposti
ad altre fonti rimane parte del monitoraggio. Il confronto reale con Paesi in
Festa ha trovato cinque coppie con stesso comune e stesse date. Il catalogo
puo' unire queste coppie solo quando coincidono anche la frazione e una parola
distintiva del nome della festa; eventi con date o luoghi diversi restano
separati. Questo evita che la mancanza dell'orario produca cinque doppioni
evidenti senza unire in modo generico manifestazioni diverse.

## Azalea: archivio e dettagli ufficiali

L'[archivio Azalea](https://www.azalea.it/eventi/) espone schede con titolo,
data e comune. Ogni scheda ha una pagina con data, luogo, descrizione e
immagine. L'adattatore legge tutte le schede visibili e ogni dettaglio,
confronta data, comune e titolo, e pubblica soltanto gli eventi FVG non
terminati. La descrizione breve e' attribuita alla pagina ufficiale; l'immagine
proviene dal suo `og:image`. Il caso di [Claudio Baglioni a
Codroipo](https://www.azalea.it/eventi/claudio-baglioni-48/) usa il 1 luglio
2027 perche' il testo ufficiale collega esplicitamente questa data al
posticipo del concerto previsto nel 2026. Altri avvisi di rinvio o
annullamento restano in revisione.

Il link tecnico `rel=next` dell'archivio porta a pagine 2 e 3 con le stesse
13 schede della prima pagina; anche le pagine 4 e 5 sono state confrontate
nell'audit. Il lettore interrompe la paginazione dopo due pagine identiche
consecutive; se compaiono nuove schede nelle pagine successive, le acquisisce.
Il gate rifiuta schede senza dettaglio, differenze fra elenco e dettaglio,
conteggi incoerenti e la scomparsa di un evento FVG ancora futuro rispetto al
catalogo precedente.

Il 7 ottobre 2026 la [sitemap ufficiale](https://www.azalea.it/sitemap_index.xml)
conteneva 249 URL di eventi: 13 nell'archivio e 236 fuori. Una lettura unica
dei 236 dettagli non ha trovato eventi FVG futuri omessi. Il job conserva
questo inventario come base e a ogni esecuzione legge solo la sitemap e gli
eventuali dettagli fuori archivio nuovi o modificati, fino a 50 per ciclo.
Oltre quel limite, o se trova un evento FVG futuro fuori archivio, la fonte
fallisce invece di pubblicare un catalogo dichiarato completo. La prova live
ha letto 13 dettagli, prodotto 7 eventi FVG con 7 descrizioni e 7 immagini,
senza revisioni, in 9,0 secondi entro il budget di 55. Una fonte stale non e'
mostrata nelle ricerche e il job segnala l'esecuzione come incompleta.

Il controllo copre archivio e sitemap pubblici al momento dell'esecuzione.
Un evento non esposto in nessuna delle due superfici non e' osservabile da
questo job; il primo ciclo distribuito resta da verificare prima della
promozione del ramo.

## Pordenone Pensa: post, pagine e programmi

Il vecchio adattatore leggeva soltanto [In Giallo 2026](https://www.pnpensa.it/pnpensa-giallo-settembre-2026-pordenone/),
concluso il 7 settembre. La homepage e le pagine delle tre rassegne non sono
un inventario sufficiente: un annuncio futuro puo' trovarsi anche in un post
non categorizzato. L'adattatore ora legge tutte le pagine dell'API WordPress e
riconcilia gli URL con [sitemap dei post](https://www.pnpensa.it/post-sitemap.xml)
e [sitemap delle pagine](https://www.pnpensa.it/page-sitemap.xml). Le date
del post sono usate per interpretare un giorno/mese senza anno soltanto quando
l'edizione e' esplicita nel testo o l'annuncio segue la pubblicazione nello
stesso anno. La data di pubblicazione da sola non e' una data di evento.

Il 7 ottobre 2026 l'API e i sitemap concordavano su **235 post e 9 pagine**:
191 post riportavano una data gia' passata, 43 non contenevano una data evento
definita e uno conteneva un annuncio futuro con data provata:
[l'ABC dell'educazione finanziaria](https://www.pnpensa.it/torna-labc-delleducazione-finanziaria-cinque-appuntamenti-sulle-assicurazioni-dal-27-ottobre/).
Il titolo indica l'avvio dal **27 ottobre**, il corpo indica l'edizione 2026,
il martedi' alle **19** e **Pordenone**. Il testo promette cinque incontri ma
non pubblica ancora le date delle altre quattro sessioni ne' le sedi. La
scheda mostra solo la prima data e il link ufficiale, con anteprima e immagine
della pagina; non calcola i quattro martedi' successivi e non inventa una sede.
La locandina presente nella pagina e' una copertina, non un calendario.

Il gate controlla numero totale, paginazione, identita' e URL di ogni post e
pagina, esito di ciascun post, data/comune delle schede future e
regressioni rispetto al catalogo precedente. Un nuovo programma con piu'
sessioni o una seconda data aggiunta all'ABC ferma la fonte finche' le singole
sessioni non sono acquisibili senza ambiguita'. La prova reale ha prodotto
**una scheda futura e zero revisioni** in 10,4 secondi, nel budget di 40.
`source_complete=true` riguarda soltanto le date pubblicate e verificate al
momento della scansione. Il primo ciclo del job distribuito resta da controllare;
le prove sul telefono sono rinviate.

## CSS Udine: stagioni e spettacoli

La sola [homepage CSS](https://www.cssudine.it/) non copre l'intero programma.
L'adattatore legge anche le cinque sezioni di stagione correnti: [Contatto](https://www.cssudine.it/stagione-contatto),
[Festil](https://www.cssudine.it/stagione-festil),
[Pasolini](https://www.cssudine.it/stagione-pasolini),
[TIG](https://www.cssudine.it/stagione-tig) e
[TIG in famiglia](https://www.cssudine.it/stagione-tig-in-famiglia).
  I link di menu, le produzioni e gli articoli non sono contati come schede.
  Gli ID dei link agli spettacoli presenti in ciascuna pagina devono comparire
  anche nelle sue schede: un ID nuovo fuori dall'inventario blocca la fonte.
  Ogni dettaglio e' confrontato con data e luogo della scheda di stagione.

Il 7 ottobre 2026 le sei superfici esponevano 122 URL distinti. Tutti i 122
dettagli hanno risposto. Le pagine con date future e comune preciso erano 95 e
producevano 161 repliche; ogni replica ha una breve descrizione attribuita
alla propria pagina ufficiale e l'immagine dello spettacolo. Il lettore
riconosce "Cervignano" come Cervignano del Friuli solo nel contesto CSS e
acquisisce anche il programma TIG per le scuole quando sede e giornate sono
esplicite. Se manca l'ora, conserva la data senza inventare un orario.
Le repliche con lo stesso URL, titolo e luogo sono raggruppate dalla vista
Eventi in una scheda con le occorrenze.

Le altre 27 pagine sono classificate nel risultato: 20 passate, due riepiloghi
di stagione gia' rappresentati da appuntamenti specifici, due senza date
definite e tre programmi itineranti in scuole o spazi non identificati con un
comune preciso. Questi ultimi non possono essere posizionati correttamente
in una ricerca per raggio e restano registrati come esclusioni motivate.
Il gate richiede che tutte le schede abbiano un dettaglio e una disposizione,
controlla conteggi e anteprime, blocca anomalie e la scomparsa di date future
rispetto al catalogo precedente. In caso di errore CSS diventa stale e le sue
vecchie schede non compaiono nelle ricerche.

La prova live del 7 ottobre ha impiegato 33,2 secondi, entro il budget di 55;
il passaggio nel job comune e la query locale hanno restituito 161 repliche
con stato `fresh`. `incontri` espone solo una scheda del 2018 e
`stagione-iosonomecenate` schede del 2020; sono state controllate una volta
per escludere programmi correnti fuori dalle cinque stagioni. Il primo ciclo
distribuito resta da verificare. Le prove sul telefono sono rinviate su
richiesta dell'utente.

## Teatro Verdi Pordenone: stagione e repliche

Il lettore segue tutte le pagine dell'[elenco di stagione](https://teatroverdipordenone.it/la-stagione/),
poi confronta gli URL con gli spettacoli pubblicati dall'[API della stagione](https://teatroverdipordenone.it/wp-json/wp/v2/spettacolo?spettacolo_stagione=215&per_page=100&_fields=id,link,modified,spettacolo_stagione)
e con le [sitemap ufficiali](https://teatroverdipordenone.it/sitemap_index.xml).
Il 7 ottobre 2026 elenco e API della stagione 2026/2027 contenevano gli stessi
64 spettacoli. La sitemap recente ne conteneva 94: tutti i dettagli sono stati
letti; i 30 spettacoli fuori dall'elenco avevano date passate. La sitemap
storica conteneva altri 1000 URL: il job ne controlla gli URL e le date di
ultima modifica, fermandosi se compare una modifica fuori dall'inventario
corrente. Non rilegge ogni volta tutti i mille dettagli storici.

Le schede future producono 88 repliche, ordinate per data e ora. Ogni replica
porta la data della propria scheda ufficiale, una breve descrizione narrativa
attribuita e l'immagine della stessa pagina. Una sala sconosciuta su una
replica futura richiede revisione; un vecchio spettacolo estivo in sede esterna
non blocca il calendario corrente. Il gate verifica la corrispondenza fra API,
elenco, sitemap recente, dettagli e repliche, e blocca la scomparsa di una
data futura rispetto al catalogo precedente. Se il controllo fallisce, la
fonte diventa stale e le sue schede non compaiono nella ricerca.

La prova live del 7 ottobre ha impiegato 30,8 secondi, entro il budget di 55.
Nel job comune la fonte risultava `fresh`; la ricerca locale a Pordenone
restituiva tutte le 88 repliche, ognuna con anteprima e immagine. Il primo
ciclo distribuito e le prove sul telefono restano da verificare.

## Teatro Verdi Trieste: API della stagione e dettagli delle repliche

Il [calendario pubblico](https://www.teatroverdi-trieste.com/it/calendario-spettacoli/)
non e' sufficiente da solo: il 7 ottobre 2026 elencava 18 spettacoli e il
vecchio lettore ne ricavava 62 date future senza gli orari individuali.
L'[API ufficiale della stagione 2026/27](https://www.teatroverdi-trieste.com/wp-json/wp/v2/spettacoli?stagione=295&per_page=100&lang=it&_fields=id,link,stagione,lang)
conteneva 21 schede italiane. Due concerti erano passati; due spettacoli
futuri mancavano nel calendario: [11° Concerto](https://www.teatroverdi-trieste.com/it/spettacoli/11-concerto/)
il 19 maggio 2027 e [Norma](https://www.teatroverdi-trieste.com/it/spettacoli/norma/)
con sei repliche dall'11 al 20 giugno 2027. Il concerto del 31 dicembre
2026 e' nel calendario ma appartiene alla stagione 2025/26. L'unione di
calendario e API produce 22 URL da verificare; tutti risultavano presenti
nella sitemap degli spettacoli, che aveva 446 URL.

Il lettore apre ogni dettaglio: le date future del calendario devono
coincidere con quelle dei biglietti nella scheda, mentre una scheda della
stagione ancora assente dal calendario puo' entrare solo con data e ora
esplicite nel dettaglio. Per "La fiaba di Aida" e "Lo Schiaccianoci" il
dettaglio distingue due repliche nello stesso giorno che l'elenco sintetico
non rappresenta. Il risultato e' 73 repliche future, ordinate per data e ora,
con immagine ufficiale in tutte le schede. Trenta repliche hanno anche una
breve informazione testuale attribuita al dettaglio; per le altre la pagina
non offre un testo utile come anteprima e il campo resta vuoto.

Sono state verificate una volta anche le 25 schede italiane della stagione
2025/26: l'unico appuntamento ancora futuro e' quello del 31 dicembre, gia'
nel calendario. Il job sorveglia la sitemap e si ferma se viene modificata
una scheda **italiana di spettacolo** esterna all'inventario corrente.
Indici e traduzioni non sono schede italiane. Il gate verifica conteggi, URL,
date, orari, immagini, descrizioni presenti e regressioni rispetto al
catalogo precedente; in caso di errore la fonte diventa stale e non compare
nella ricerca. La prova live del 7 ottobre ha impiegato circa 10 secondi.
Il job comune ha restituito stato `fresh` e la ricerca locale a Trieste
mostrava tutte le 73 repliche. Il primo ciclo distribuito e le prove sul
telefono restano da verificare.

Nel ciclo locale a 14 fonti del 7 ottobre, il sito ha aggiornato nella sitemap
l'[indice Spettacoli](https://www.teatroverdi-trieste.com/it/spettacoli/),
l'indice inglese e una vecchia pagina inglese di *The tale of Aida*, tutti
fuori dall'API italiana. Il filtro precedente li trattava erroneamente come
nuovi spettacoli e fermava la fonte. La correzione limita il controllo ai
dettagli `/it/spettacoli/<slug>/`; un dettaglio italiano nuovo continua a
bloccare il job. La raccolta reale ripetuta dopo la correzione ha restituito
73 repliche e zero revisioni in 12,1 secondi.
Nel ciclo locale completo ripetuto, il Teatro e' tornato `fresh` con 73
repliche e zero revisioni in 10,59 secondi.

## Villa Manin: API, archivio annuale e calendario visibile

Il [calendario Eventi](https://www.villamanin.it/eventi/) mostra tessere con
date iniziale e finale. L'[API pubblica dei dettagli](https://www.villamanin.it/wp-json/wp/v2/evento?_embed=1&per_page=100&page=1)
espone l'intero testo delle schede, le immagini in evidenza e la tassonomia
`anno`. L'[archivio 2026](https://www.villamanin.it/anno/2026/) fornisce
un secondo inventario paginato. Il lettore percorre tutte le pagine API,
confronta totale, numero di pagine, ID e URL unici, poi richiede che gli URL
con `anno=2026` coincidano con quelli delle cinque pagine dell'archivio.
Le tessere di Eventi devono appartenere all'API; ogni evento ancora attivo
deve comparire li' e avere titolo, date e descrizione coerenti con la sua
pagina HTML. Le date del post WordPress non sostituiscono date dell'evento.

Il 7 ottobre 2026 la prova live ha letto **361 record API in quattro pagine**,
**47 URL nell'archivio 2026** e **34 tessere Eventi**. I 47 URL e le rispettive
tassonomie coincidono. Dei 361 record, 248 hanno date concluse, 106 esclusioni
non sono nelle superfici correnti e non sono state modificate dopo l'inizio
dell'audit, quattro schede 2026 respinte dal parser mostrano sulla tessera
una fine gia' passata, e tre schede hanno date ancora utili. Ogni nuova
esclusione corrente o modificata dopo il 7 ottobre deve essere revisionata;
un'esclusione futura ferma la fonte. Una tessera storica di “Appuntamento in
giardino” mostra 6 giugno 2026 come inizio e 7 giugno 2025 come fine:
l'anomalia resta contata ma non altera eventi futuri.

Le schede attive sono [Famiglie al Museo](https://www.villamanin.it/evento/famiglie-al-museo/)
per l'11 ottobre, [Giornata delle Ville Venete](https://www.villamanin.it/evento/giornata-delle-ville-venete/)
per il 18 ottobre e [Lo scrigno del Doge](https://www.villamanin.it/evento/lo-scrigno-del-doge-in-villa-manin/).
L'ultima pagina indica sei **appuntamenti distinti**, dei quali restano
1 novembre e 8 dicembre 2026 e 6 gennaio 2027. Non viene creata una scheda
per ogni giorno compreso fra aprile e gennaio. La tassonomia della pagina
Scrigno contiene 2025 e 2026, ma l'intestazione del dettaglio e la tessera
Eventi indicano esplicitamente il 6 gennaio 2027; il lettore richiede la
concordanza di queste due date visibili senza pretendere che ogni occorrenza
abbia una tassonomia propria.

Il risultato sono **cinque date future**, tutte con anteprima breve attribuita
alla pagina ufficiale. Quattro hanno immagine in evidenza; la pagina delle
Ville Venete non ne fornisce una e il campo resta vuoto. Quando la scheda
TurismoFVG dello Scrigno presenta lo stesso evento come intervallo generico
aprile–dicembre, il catalogo conserva le date puntuali di Villa Manin e
aggiunge l'URL regionale alla provenienza, evitando una scheda doppia.

La raccolta live con gate ha impiegato **38,7 secondi**, entro il budget di
65. Il gate controlla i conteggi, la riconciliazione annuale, i dettagli,
le esclusioni e l'eventuale scomparsa di date future rispetto al catalogo
precedente. Se una di queste prove fallisce la fonte diventa stale e le sue
schede non sono mostrate. La copertura dimostrata riguarda API, archivio e
calendario pubblici; una pagina non esposta in alcuna delle tre superfici
non e' osservabile automaticamente. Il primo ciclo distribuito e le prove
su telefono restano da verificare prima della promozione del ramo.

## Magazzino delle Idee: API, due elenchi e date della mostra

L'[API pubblica degli eventi](https://magazzinodelleidee.it/wp-json/wp/v2/evento?_embed=1&per_page=100&page=1)
espone i dettagli, l'immagine in evidenza e le tassonomie `anno` e
`tipologia`. Il lettore percorre tutte le pagine API e riconcilia ID e URL
unici con l'[event sitemap](https://magazzinodelleidee.it/evento-sitemap.xml),
l'[archivio 2026](https://magazzinodelleidee.it/anno/2026/), le pagine
[Eventi](https://magazzinodelleidee.it/eventi/) e
[Mostre](https://magazzinodelleidee.it/mostre/). Per ogni scheda corrente
richiede una presenza nell'elenco pubblico e confronta titolo, periodo e
descrizione con la pagina di dettaglio. Per le mostre confronta anche la data
scritta nella tessera Mostre. Una differenza ferma l'intera fonte.

La prova live del 7 ottobre 2026 ha letto **104 record API in due pagine**.
La sitemap contiene 133 voci ma **104 URL unici**, uguali agli URL API;
l'archivio annuale elenca tre URL, uguali alle tre schede con `anno=2026`.
Le quattro pagine Eventi espongono 62 URL distinti; Mostre ne espone sette,
tutti presenti nell'API. Delle tre schede annuali, due sono concluse e una
e' ancora attiva: [Ila Bêka - Fotoni](https://magazzinodelleidee.it/evento/ila-beka-fotoni/),
dal 27 giugno all'11 ottobre 2026 a Trieste. La mostra ha descrizione breve
attribuita e immagine ufficiale. La data della tessera Mostre coincide con
API e dettaglio. Il titolo cliccabile della tessera Mostre punta per errore
a una mostra del 2025, mentre il pulsante e l'immagine conducono a Fotoni:
il catalogo usa l'URL canonico dell'API, verificato dal dettaglio.

Il gate controlla paginazione, inventari, schede correnti, date e testo del
dettaglio, data della tessera Mostre e scomparsa di eventi ancora futuri.
Una modifica successiva al 7 ottobre di un record legacy fuori dall'archivio
richiede revisione. La raccolta live finale ha impiegato **20,1 secondi** entro il
budget di 35. La scheda TurismoFVG della stessa mostra viene unita a quella
ufficiale quando coincidono titolo, periodo, comune e sede. La copertura
provata riguarda le superfici pubbliche esaminate; il primo ciclo distribuito
e le prove sul telefono sono ancora da verificare.

## ERPAC: portale editoriale e siti dei musei

La [homepage ERPAC](https://erpac.regione.fvg.it/) non e' un archivio completo
di eventi. Il 7 ottobre 2026 la sua versione HTML prerenderizzata mostrava
**otto tessere** nelle sezioni Eventi e Mostre; la stessa homepage rinviava
anche ai siti separati di Villa Manin, Magazzino delle Idee, Palazzo Attems,
Galleria Spazzapan, MESS e Musei Provinciali di Gorizia, oltre ad altri poli.
Il lettore diagnostico esistente ha riconosciuto cinque tessere con date e
respinto tre tessere senza una data completa. Dei cinque record, [Lo scrigno
del Doge](https://www.villamanin.it/evento/lo-scrigno-del-doge-in-villa-manin/)
e' gia' coperto dalla fonte diretta Villa Manin; [DAG](https://erpac.regione.fvg.it/it/dag-digital-art-gallery-gorizia-165754),
[Ila Beka. Fotoni](https://magazzinodelleidee.it/evento/ila-beka-fotoni/) e
[FVG Settanta](https://galleriaspazzapan.regione.fvg.it/it/fvg-settanta-170166)
hanno dettagli autonomi; [Italia Settanta](https://palazzoattems.regione.fvg.it/it/italia-settanta-165450)
richiede una nuova prova di sede e date perche' il dettaglio non espone piu'
il sottotitolo sul quale si basava una risoluzione manuale di agosto.

Le tre tessere escluse sono gli [eventi collaterali di ottobre](https://palazzoattems.regione.fvg.it/it/eventi-collaterali-di-ottobre-174290)
di Palazzo Attems, [i laboratori MESS](https://mess.regione.fvg.it/it/didattica-museale-171043)
e [la mostra sulle antiche vetrerie](https://museiprovincialigorizia.regione.fvg.it/it/mostra-sulle-tracce-delle-antiche-vetrerie-del-goriziano-167353).
Il primo dettaglio rimanda a una locandina immagine per il calendario; il
secondo contiene nel testo decine di appuntamenti con giorno e mese e dichiara
piu' avanti «da agosto a dicembre 2026». L'adattatore MESS collega ogni
appuntamento alla sede e all'anno del programma. Il terzo
descrive un'apertura primaverile e la stagione estiva senza fine esatta.
Questi casi non diventano eventi con date o luoghi dedotti. Il job periodico
non legge locandine PDF o immagini.

Decisione: **non aggiungere il portale ERPAC come fonte del job**. La homepage
resta un indice diagnostico di scoperta e di confronto; ogni polo va verificato
con la propria lista, il proprio dettaglio e il proprio controllo automatico.
Gli audit separati di Palazzo Attems, Galleria Spazzapan, MESS e Musei
Provinciali sono registrati sotto. Le schede gia' coperte da Villa Manin restano
una sola volta nel catalogo. Questo chiude la decisione sul portale generale,
non certifica ancora la copertura dei siti dei musei.

La [scheda DAG - Digital Art Gallery Gorizia](https://erpac.regione.fvg.it/it/dag-digital-art-gallery-gorizia-165754)
e' un'altra tessera da distinguere da un evento. Descrive la galleria e
l'installazione *Data Tunnel* di Refik Anadol, fornisce orari di apertura
fino al 31 dicembre 2026 e link per prenotare ingressi singoli, gruppi e
abbonamenti. La [pagina dell'ingresso singolo](https://erpac.regione.fvg.it/it/dag-digital-art-gallery-singolo-ingresso-fruibile-dal-17122025-al-31122026-161410)
indica un intervallo di fruizione, non un programma di appuntamenti. In base
al criterio concordato "solo eventi con programma", DAG non diventa una
scheda Eventi solo perche' e' visitabile per un lungo periodo. Se il polo
pubblichera' una mostra temporanea o un incontro con date proprie, quello
sara' valutato come evento distinto. Il footer ERPAC indica Palazzo Alvarez:
la scheda DAG identifica invece la Galleria Giorgio Bombi, e l'indirizzo del
footer non va usato come sede dell'installazione.

## Palazzo Attems Petzenstein: inventario disponibile, localita' incomplete

Aggiornamento del 7 ottobre: il [controllo diagnostico](EVENTI_PALAZZO_ATTEMS_AUDIT_2026-10-07.md)
confronta automaticamente sei superfici ufficiali, dettagli attivi e 41 notizie
2026 versionate. Conferma una mostra e le visite guidate, ma blocca due
schede attive con sede o programma non riconciliati e l'annullamento
dell'11 ottobre. La categoria Mostra contiene soltanto 11 voci storiche;
la mostra corrente e' sulla homepage. Palazzo resta fuori dalle fonti che
pubblicano schede; il codice del job su questo ramo sorveglia le novita' nel
suo inventario quando verra' distribuito.

La [pagina Eventi](https://palazzoattems.regione.fvg.it/it/events) e' una
applicazione JavaScript. L'HTML ordinario non contiene le schede; il sito
espone comunque una versione HTML pubblica con il parametro
`?_escaped_fragment_=`. La stessa applicazione legge l'[API ufficiale degli
eventi](https://palazzoattems.regione.fvg.it/core/events/erpac_palazzoattems/it/):
il 7 ottobre 2026 essa ha restituito **27 schede**, coincidenti con il totale
visibile nelle tre pagine Eventi da nove schede ciascuna. La categoria
`Evento` nella ricerca del sito mostrava solo cinque vecchi risultati, quindi
non rappresenta l'inventario corrente. I dettagli hanno un endpoint JSON per
ID, per esempio la [scheda dell'8 ottobre](https://palazzoattems.regione.fvg.it/core/page/erpac_palazzoattems/174333/it/).

Dei 27 record, il 7 ottobre restavano attivi un incontro dell'8 ottobre,
un riepilogo 1–15 ottobre e un programma di visite 12 settembre–29 novembre.
Tutti i 27 record hanno `event_location` vuoto. La [pagina delle visite
guidate](https://palazzoattems.regione.fvg.it/it/visite-guidate-gratuite-173302)
nomina Palazzo Attems Petzenstein nel corpo e pubblica in testo le singole
giornate di ottobre e novembre: e' una fonte utilizzabile per un programma
raggruppato. Il [riepilogo degli eventi di ottobre](https://palazzoattems.regione.fvg.it/it/eventi-collaterali-di-ottobre-174290)
cita invece due sedi, Palazzo Attems a Gorizia e Galleria Spazzapan a Gradisca,
e affida il calendario dettagliato a una locandina immagine. Non va mostrato
come un singolo evento in un solo comune. La [scheda individuale dell'8
ottobre](https://palazzoattems.regione.fvg.it/it/eventi-collaterali-di-ottobre-174333)
fornisce data, titolo e ora, ma non una sede testuale; anche il suo dettaglio
JSON lascia vuoto `event_location`. Il footer del sito indica l'indirizzo del
museo, non quello specifico dell'incontro, e non risolve questa lacuna.

La [mostra Italia Settanta](https://palazzoattems.regione.fvg.it/it/italia-settanta-165450)
e' provata dalla homepage e dalla scheda dettagliata dal 27 giugno al
29 novembre 2026 a Palazzo Attems Petzenstein, Gorizia; dispone di testo per
l'anteprima e immagine. Le mostre non sono comprese nell'API `core/events/`:
servira' un secondo inventario, riconciliato con la homepage e l'elenco delle
mostre in corso. Il futuro adattatore dovra' confrontare il totale API con gli
elenchi, leggere i dettagli correnti, separare le mostre, accettare solo eventi
con sede e giorni provati in testo, e fermare la fonte quando un evento attivo
resta irrisolto. **Palazzo Attems non pubblica ancora schede proprie**; nessuna scheda
parziale viene pubblicata. Il controllo diagnostico e' configurato nel job su
questo ramo e non richiede PDF ne' riconoscimento
del testo delle locandine.

## Galleria Spazzapan: elenco eventi e mostre hanno coperture diverse

Il 7 ottobre 2026 l'[API ufficiale Eventi](https://galleriaspazzapan.regione.fvg.it/core/events/erpac_spazzapan/it/)
conteneva **tre** record ancora attivi: [Mario Palli / Studio
Visit](https://galleriaspazzapan.regione.fvg.it/it/giornata-del-contemporaneo-2026-75485)
il 10 ottobre, [Nuovo paesaggio: una mostra da salvare](https://galleriaspazzapan.regione.fvg.it/it/eventi-collaterali-ottobre-174329)
il 14 ottobre e [FVG70.03 - Sergio Pausig](https://galleriaspazzapan.regione.fvg.it/it/donazione-sergio-pausig-172996)
fino all'11 ottobre. La [categoria
Eventi](https://galleriaspazzapan.regione.fvg.it/core/categories/erpac_spazzapan/it/14038/)
ha solo i primi due; non puo' sostituire l'API. La scheda di Mario Palli
spiega che la visita avviene nello **studio dell'artista** a Gradisca d'Isonzo,
con ritrovo alla Galleria in via Marziano Ciotti 51: la Galleria non e' la
sede della visita. Le tre schede hanno `event_location` vuoto, percio' sede e
comune vanno provati nel testo. Il dettaglio del 14 ottobre fornisce solo
"a breve ulteriori dettagli sull'evento": data, ora e indirizzo sono
pubblicati, ma non esiste ancora una descrizione significativa da usare come
anteprima.

L'[elenco Mostra in
corso](https://galleriaspazzapan.regione.fvg.it/core/categories/erpac_spazzapan/it/16101/)
contiene **quattro** schede e la categoria
[Mostra](https://galleriaspazzapan.regione.fvg.it/core/categories/erpac_spazzapan/it/13346/)
ne contiene sette, tre storiche. Tra le correnti,
[FVG70.02 - Nuovi modelli di ricerca](https://galleriaspazzapan.regione.fvg.it/it/fvg7002-nuovi-modelli-di-ricerca-173006)
non compare nell'API Eventi, mentre FVG70.03 vi compare ed e' quindi un
duplicato da unire. Il dettaglio FVG70.02 reindirizza alla [notizia sugli
eventi collaterali di ottobre](https://galleriaspazzapan.regione.fvg.it/it/fvg7002-eventi-collaterali-di-ottobre-172985),
che incorpora un modulo con le date **23 luglio–29 novembre 2026**, la sede
via Marziano Ciotti 51 a Gradisca d'Isonzo, una descrizione estesa e una
copertina. FVG70.03 ha nel suo dettaglio autonomo le date
**11 settembre–11 ottobre 2026**, Sala Patuna della Galleria, descrizione e
immagine. Per entrambe, invece, i campi strutturati
`start_event_date_formatted` / `end_event_date_formatted` dell'elenco
"Mostra in corso" riportano **27 giugno 2026–15 gennaio 2027**, cioe' le
date del [progetto ombrello FVG
Settanta](https://galleriaspazzapan.regione.fvg.it/it/fvg-settanta-170166).
Pubblicare quelle date senza controllo del dettaglio prolungherebbe
erroneamente le due mostre. Il progetto ombrello non va duplicato come
mostra continuativa; [Together/Insieme](https://galleriaspazzapan.regione.fvg.it/it/progetto-togetherinsieme-170074)
non pubblica un periodo o programma definito e resta escluso.

La categoria [Notizia](https://galleriaspazzapan.regione.fvg.it/core/categories/erpac_spazzapan/it/15922/)
contiene **77** record, di cui 44 modificati nel 2026. Include un secondo
annuncio di Mario Palli, due notizie riepilogative FVG70.02 con lo stesso
modulo di mostra e avvisi storici. E' un inventario da controllare per
appuntamenti sfuggiti agli altri elenchi, non una lista da pubblicare
automaticamente: servono prova testuale dell'anno, data, comune, sede e
deduplicazione con Eventi e Mostre. Le [due categorie omonime di mostre in
corso](https://galleriaspazzapan.regione.fvg.it/it/categories/mostre-in-corso-16102)
non sono equivalenti: la variante plurale `16102` contiene una sola scheda
storica del 2024. Il primo controllo che la indicava vuota era errato.

Il gate verifica a ogni ciclo conteggi e ID delle categorie e dell'API Eventi,
le 43 notizie pubblicate nel 2026, i dettagli delle schede attive e le due
esclusioni di progetto. Una nuova notizia o una data/sede discordante ferma
la fonte. L'adattatore produce **quattro schede distinte**, ne unisce una
alla corrispondente scheda TurismoFVG e salva una descrizione attribuita per
le tre pagine che ne pubblicano una utilizzabile. La prova isolata e i limiti
sono nell'[audit Spazzapan](EVENTI_SPAZZAPAN_AUDIT_2026-10-07.md). I
quattordici adattatori hanno un budget complessivo di 875 secondi su 900;
aggiungerne uno richiede una nuova revisione misurata.

## Musei Provinciali di Gorizia: indice dei poli, non inventario corrente

La [homepage dei Musei Provinciali](https://museiprovincialigorizia.regione.fvg.it/)
mostra sei sedi e due tessere di mostre. Quella di
[Italia Settanta](https://palazzoattems.regione.fvg.it/it/italia-settanta-165450)
rimanda al sito autonomo di Palazzo Attems e prova l'intervallo 27 giugno–29
novembre 2026; l'altra annuncia una mostra terminata nell'estate 2026. Il
"Calendario Eventi 2026" della homepage e' un PDF, che non entra nel job
periodico in base al perimetro concordato.

L'[API Eventi](https://museiprovincialigorizia.regione.fvg.it/core/events/erpac_musei_gorizia/it/)
ha due schede: "Anche le statue parlano" del 19 febbraio **2023** e un
"Evento di prova" senza data. La [categoria
Evento](https://museiprovincialigorizia.regione.fvg.it/core/categories/erpac_musei_gorizia/it/15312/)
ha due notizie del 2025. La categoria
[Mostra](https://museiprovincialigorizia.regione.fvg.it/core/categories/erpac_musei_gorizia/it/13708/)
ha sei record, l'ultimo pubblicato nel novembre 2025; la categoria [Mostre
concluse](https://museiprovincialigorizia.regione.fvg.it/core/categories/erpac_musei_gorizia/it/15310/)
ne ha nove. La categoria [Notizia](https://museiprovincialigorizia.regione.fvg.it/core/categories/erpac_musei_gorizia/it/15311/)
ha 159 record, ma l'ultimo pubblicato e aggiornato risale al **30 giugno
2026**. Nessuna delle quattro categorie presenta una data strutturata ancora
attiva al 7 ottobre. La notizia [Via per le strade. Paolo
Gasparini](https://museiprovincialigorizia.regione.fvg.it/it/via-per-le-strade-paolo-gasparini-167022),
per esempio, terminava il 27 settembre.

Decisione: **non aggiungere il portale Musei Provinciali come fonte autonoma**.
Le sue tessere e le notizie restano utili per scoprire e confrontare i siti
delle singole sedi, ma l'API Eventi e le categorie non dimostrano un
inventario completo corrente. In particolare Italia Settanta va verificata
una sola volta nella futura fonte Palazzo Attems. La decisione non copre
eventuali programmi futuri pubblicati sui siti dei singoli musei.

## MESS: programma per museo e notizie verificate

Il [programma ufficiale](https://mess.regione.fvg.it/it/didattica-museale-171043)
dichiara 36 laboratori da agosto a dicembre 2026. La sua API pubblica
effettivamente **36 righe datate**: la riga del 28 novembre era sfuggita al
primo audit perche' scrive `novenbre`. L'adattatore accetta quel refuso solo
per la data e l'edizione gia' verificate, senza inventare altre date. Le
[18 sedi](https://mess.regione.fvg.it/it/i-musei-del-mess-171271) espongono
indirizzi testuali; due laboratori corrispondono a ogni museo. Alcune coordinate
della mappa puntano al comune sbagliato: la posizione delle schede deriva dal
comune dell'indirizzo verificato, con precisione dichiarata `municipality`.

Al 7 ottobre restano **16 laboratori futuri in 9 musei**. La lista pubblica
mostra una scheda per museo, con gli appuntamenti ordinati nell'anteprima, la
descrizione tratta dal programma e un collegamento alla pagina ufficiale.
Le schede regionali degli stessi laboratori sono riconciliate per URL
revisionati, data e comune. Nessuna lista PDF viene letta dal job.

La categoria [Notizie dai Musei](https://mess.regione.fvg.it/core/categories/erpac_mess/it/18221/)
contiene 51 record, 24 pubblicati nel 2026. Tre mostre ancora attive hanno
date e comune corroborati anche dalle rispettive pagine TurismoFVG:
[Sulla soglia](https://mess.regione.fvg.it/it/not-173804),
[Spiriti, amuleti e memorie ancestrali](https://mess.regione.fvg.it/it/not-173318/no-173328)
e [Storie di erbe](https://mess.regione.fvg.it/it/not-169209).
Ognuna conserva immagine e anteprima attribuite alla notizia MESS e diventa
una sola scheda insieme al doppione regionale. Un'altra notizia, *La bottega
Giampaoli*, pubblica soltanto la data di inizio: resta fuori da Eventi finche'
non e' provato un periodo o un programma definito.

Il gate controlla a ogni ciclo il numero delle righe, le 18 sedi, il legame
due incontri per museo, i metadati delle 24 notizie revisionate e la prova
regionale delle tre mostre. Se una nuova notizia o una nuova edizione cambia
l'inventario, la fonte viene fermata per revisione, senza pubblicare dati
parziali. I risultati della prova locale e i limiti sono nell'[audit MESS
del 7 ottobre](EVENTI_MESS_AUDIT_2026-10-07.md).

## Criterio per un commit "fonte terminata"

1. Inventario delle pagine di elenco e prova che tutti i link pertinenti
   siano stati percorsi, senza contare caroselli e duplicati.
2. Regole della fonte per titolo, localita', date e anteprima; confronto fra
   elenco, dettaglio e metadati, con anomalie bloccate o risolte.
3. Gate automatico di completezza e test dell'adattatore; nessuna data o
   descrizione inventata per riempire campi mancanti.
4. Registrazione nel job comune e nelle liste autorizzate; test del job
   predefinito e prova locale di raccolta entro il suo budget.
5. Commit sullo stesso ramo con il nome della fonte e i risultati delle
   verifiche. Solo dopo i controlli complessivi si valutera' la promozione
   a `main`.

I checkpoint intermedi riportano esplicitamente "in corso" e non soddisfano
da soli i cinque criteri.
