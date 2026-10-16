# Scopri — piano di completamento di tutte le rubriche

Data: 31 agosto 2026. Stato: **in corso, non completato**.

## Mandato e metodo

L'utente chiede di completare Scopri e ampliare anche le rubriche diverse dalle tappe comunali, lasciando l'ordine di lavoro alla redazione assistita. Si procede per lotti bilanciati: chiudere il piccolo lotto comunale già documentato, poi lavorare su riti, detti e altri contenuti senza aspettare di esaurire tutti i Comuni.

Le integrazioni restano locali: nessun commit, push, deploy o pacchetto Android è implicito in questo piano. L'ultimo commit precedente è `6ce1473`.

Il registro operativo è `frontend/src/data/discover/editorialExpansionBacklog.json`. Le cinque rubriche corrispondono al contratto `ALMANAC_DISCOVER_CONTENT_CONTRACT.md`; non si introducono sezioni ulteriori solo per riempire la pagina.

## Perimetro e criterio di chiusura

| Rubrica | Lavoro da completare | Verifica richiesta |
| --- | --- | --- |
| Conosci la località | Esaminare i Comuni con una o due tappe e puntare a tre fatti distinti quando documentabili. Registrare le eccezioni invece di inventare date. | 215 identità comunali corrette, fonti per tappa, IT/FUR, ordine cronologico e assenza di duplicati; nessun Comune lasciato senza valutazione. |
| Riti e credenze popolari | Ampliare periodi e territori ancora poco rappresentati: Rogazioni, cicli agricoli, raccolti, vendemmia, Avvento e patronali. | Calendario di dodici mesi esaminato; ogni presenza legata a una data o intervallo verificato, varianti locali separate, nessun obbligo di apparire tutti i giorni. |
| Si diceva che… | Ampliare il repertorio riusando prima i testi già revisionati, poi cercando nuovi detti contestualizzabili. | Testo autorevole unico, approvazioni IT/FUR conservate, audit pluriennale di utilizzo e ripetizioni; eventuali nuove spiegazioni hanno una propria revisione. |
| Archivio e tradizioni | Proseguire oltre le venti schede istituzionali già integrate, ampliando argomenti e aree geografiche. | Una scheda al giorno, fonte dichiarata, nessun doppione con Memoria o altre rubriche, tutte le schede ammissibili utilizzate o escluse con motivazione. |
| Memoria del giorno | Conservare il calendario primario completo e ampliare le memorie secondarie quando aggiungono un fatto rilevante e distinto. | Tutte le 366 date coperte, precedenza alle ricorrenze esatte, secondarie ordinate e controlli sulle collisioni. La copertura completa non chiude automaticamente ogni ampliamento editoriale. |

Non esiste un numero magico di schede che renda definitivo un archivio culturale. Il completamento della passata richiede una verifica esplicita di ogni ambito sopra, con lacune e scelte documentate; non basta portare a verde il test di copertura giornaliera.

## Lavoro tecnico trasversale: contenuti legati al meteo

All'inizio della passata erano esclusi 26 contenuti: quattro nei riti e ventidue nell'archivio. La quarta passata, descritta sotto, li ha valutati tutti: otto sono recuperati come racconti storici soltanto in Scopri, diciotto restano esclusi. Un eventuale collegamento ai dati attuali richiede ancora, uno per uno:

1. distinguere una credenza su un fenomeno da una condizione osservabile;
2. verificare se l'app dispone del dato locale necessario, sufficientemente recente e non ambiguo;
3. mantenere il comportamento chiuso in caso di dato mancante, vecchio o incoerente;
4. conservare il carattere culturale del testo: non è una previsione scientifica né un avviso;
5. scegliere e documentare integrazione contestuale, riclassificazione archivistica motivata oppure esclusione.

Questo passaggio non viene ottenuto eliminando il controllo che oggi esclude `recurrence: weather`.

La prima ricognizione del codice distingueva i 26 record nei gruppi seguenti. È la classificazione iniziale, non il conteggio attuale degli esclusi; le decisioni correnti sono in `weatherContextReview.json`:

| Gruppo | Record | Passo successivo |
| --- | ---: | --- |
| Pertinenza tematica con il meteo già disponibile | 5 | Nubi, venti, temporali e neve: usare località, provenienza e freschezza; non dedurre grandine o innevamento dalla sola condizione meteo. |
| Calendario lunare | 2 | Riutilizzare fase ed età lunare già calcolate, dopo revisione della regola editoriale. Non serve una nuova API. |
| Ottica, paesaggio, prima neve, animali e piante | 15 | I tag pioggia/vento non provano aloni, arcobaleni o comportamenti animali. Valutare racconti storici o stagionali, non una falsa rilevazione automatica. |
| Riti senza data precisa | 4 | Scongiuri, campane, streghe e credenze: valutare un approfondimento d'archivio; non farli apparire come pratiche in corso grazie a un tag meteo. |

I cinque casi iniziali sono `ost-0001-nubi-pioggia`, `ost-0005-lessico-venti`, `ost-0007-grandine-temporale`, `ost-0041-neve-abbondanza`, `ost-0048-palle-neve-slitte`. I due lunari sono `ost-0009-luna-lavori-agricoli` e `ost-0014-proverbi-lunari-pioggia`.

Il contesto meteo runtime non viene implementato in questa passata: `DiscoverView` non riceve meteo; `discoverTemporalSelection` continua a escludere le ricorrenze meteorologiche e `discoverViewModel` ammette nei riti solo i ranghi di calendario 0–2. Le otto riclassificazioni sono invece applicate esplicitamente nel solo catalogo Scopri. L'eventuale adattatore futuro dovrà distinguere osservazioni ARPA e supporto Open-Meteo, senza copiare alla cieca i tag dell'Almanacco; i limiti di provenienza e freschezza sono documentati in `SCOPRI_WEATHER_CONTEXT_AUDIT_2026-08-31.md`.

## Prima passata avviata

- **Comuni:** integrate quattro tappe per Andreis, Cimolais e Sacile; totale 411. Restano 136 profili con una o due tappe. Le fonti specifiche sono conservate anche nel modello della scheda, senza aggiungere righe all'interfaccia.
- **Detti:** tre riusi di testi già approvati — l'asino e la carretta, le chiacchiere che accorciano la notte, nessuno nasce maestro. Totale 63 detti, di cui 52 riusi; Almanacco non modificato.
- **Riti:** integrate Rogazioni del Matajur e Missus; totale 21 schede, di cui 17 calendarizzabili. Nella simulazione 2028 la rubrica compare in 39 giorni con 12 testi diversi; gli altri giorni resta correttamente assente. Fonti, calendario e limiti descritti sotto. La valutazione non esaurisce le lacune della rubrica.
- **Archivio e memorie:** mantenuti nel perimetro della passata; i precedenti venti contenuti istituzionali e il calendario primario restano validi, ma non si usano per dichiarare chiuso l'intero lavoro.

## Due riti e loro calendario editoriale

**Matajur:** la fonte del 19 aprile 2023 descrive la rogazione maggiore di San Marco con partenza da Tercimonte, attraversamento delle comunità e soste. La scheda è un racconto documentato, non una conferma di svolgimento o un itinerario utilizzabile per l'anno corrente. Finestra di lettura: 25 aprile. Non coincide con il Bacio delle Croci di Zuglio. [Arcidiocesi di Udine — Rogazioni](https://www.diocesiudine.it/in-prossimita-della-festa-di-san-marco-tornano-gli-antichi-riti-delle-rogazioni/).

**Missus:** la fonte documenta le nove sere del 15–23 dicembre. L'app propone l'approfondimento nelle **prime tre sere, 15–17 dicembre**: è una scelta editoriale per non ripetere la stessa scheda nove giorni, non una modifica della durata della Novena. La tradizione non viene estesa alla Devetica Božična delle Valli del Natisone, esplicitamente distinta dalla fonte. Non si afferma come certa l'origine aquileiese. [Arcidiocesi di Udine — Missus e Novena](https://www.diocesiudine.it/missus-est-il-canto-dellannunciazione-illumina-le-sere-della-novena-del-natale-in-friuli/).

Non vengono riutilizzate fotografie, registrazioni o riproduzioni delle fonti.

## Revisione e tracciabilità

Per il nuovo lotto comunale e i nuovi riti la base è `user_delegated_assisted_editorial_review`: **decisione redazionale assistita nel mandato di prosecuzione**, non attestazione che l'utente abbia letto e approvato ciascuna frase. I confronti con riferimenti standard sono documentati; `independentHumanReview` resta `false`. Non si dichiara certificazione ARLeF o revisione professionale indipendente.

Il riuso dei tre detti mantiene invece le approvazioni originali del catalogo Almanacco e non genera nuove traduzioni. Le copie di ricerca restano escluse dalla UI e collegate ai record promossi.

## Prossima passata

Archivio e memorie secondarie sono stati ampliati nella terza passata; i 26 contenuti meteorologici sono stati valutati nella quarta. La prossima priorità torna alla **ricerca rituale per luglio, ottobre e novembre, oltre a maggio**, senza riempire ogni giorno. Le tappe comunali continuano per lotti senza assorbire tutto il lavoro sulle altre rubriche. I diciotto contenuti ancora esclusi hanno un percorso individuale nel manifest: non richiedono un'attivazione meteo indiscriminata e non impediscono di lavorare sulle altre rubriche.

## Verifiche della prima passata

- Suite frontend completa: **359 file, 2.307 test superati**, compresi i 14 test del nuovo lotto rituale.
- Lint frontend completo e controllo mirato degli ultimi test: superati. `git diff --check` senza errori.
- Build Web di produzione e service worker standalone: superati in una directory temporanea del sistema operativo. L'avviso già noto sulla dimensione dei chunk resta non bloccante; nessun deploy.
- Audit 2026–2031 IT/FUR dei detti: tutti i 63 usati, massimo due giorni consecutivi, nessuna collisione né violazione delle precedenze.
- Audit 2028 dei riti: 39 giorni, 12 schede usate su 17 calendarizzabili, massimo sei giorni consecutivi invariato. Nessuna collisione con le altre rubriche.
- Confronto con HEAD: i 215 profili preesistenti sono invariati al netto delle sole quattro aggiunte; i cinque riti istituzionali precedenti sono integralmente identici. Nessuna modifica ai testi originali dell'Almanacco.

Queste verifiche chiudono **la prima passata**, non l'intero piano. Le modifiche restano locali e non committate.

## Seconda passata — ricorrenze locali e Comuni UD/GO

Il successivo «procediamo» porta due riti nuovi e quattro tappe comunali. I numeri della prima passata sopra restano una fotografia storica; quelli correnti sono nel backlog.

- **Riti:** 23 schede totali, 19 calendarizzabili e quattro meteorologiche ancora escluse. Aggiunte Titiano e Castelmonte, con IT/FUR e revisione assistita tracciata in `ritualResearchWave03.json`. Il dossier non viene letto dalla UI e rimanda ai testi del catalogo senza duplicarli.
- **Comuni:** 415 tappe per 215 profili. Bagnaria Arsa passa da una a tre tappe; Talmassons e Monfalcone da due a tre. Restano 133 profili con una o due tappe: 97 con una, 36 con due; 82 ne hanno tre.
- **Altre rubriche:** invariati i 63 detti, le 69 schede d'archivio e le 565 memorie visibili. Restano nel piano di ampliamento, non vengono dichiarate editorialmente definitive.

### Le due ricorrenze

**Titiano, 5 agosto:** l'Atlante della Comunità Riviera Friulana documenta la processione in barca da Precenicco a Titiano, seguita dall'accompagnamento della statua alla chiesetta. STAI conferma la data. La sintesi non riporta la leggenda delle apparizioni come fatto storico e non contiene orari, istruzioni di navigazione o conferme per l'edizione corrente. [Atlante dei Luoghi, sezione Chiesetta della Madonna della Neve](https://www.atlantedeiluoghirivierafriulana.it/), [STAI — Precenicco](https://www.stellaboschilaguna.it/it/town/precenicco/).

**Castelmonte, 8 settembre:** il 1976 riguarda il pellegrinaggio **diocesano annuale**, non la fondazione del santuario né l'inizio di ogni pellegrinaggio. Il limite compare anche nei testi visibili: «pellegrinaggio diocesano» in IT e «pelegrinaç de Glesie di Udin» in FUR. La fonte del 2025 documenta data, origine e cammino; il programma di quell'anno non viene importato. [Arcidiocesi di Udine — pellegrinaggio a Castelmonte](https://www.diocesiudine.it/la-chiesa-udinese-si-affida-a-maria-in-pellegrinaggio-a-castelmonte-chiesa-giubilare/).

Sono ricorrenze locali estiva e di settembre, **non nuovi riti agricoli**. La ricerca agricola non ha prodotto in questo lotto una data nuova sufficientemente documentata: vendemmia e pratiche lunari duplicavano temi Ostermann; il Ringraziamento richiedeva una regola di data variabile non verificata. Barbana è già presente come bozza in `localMemory`: non ne è stata creata una seconda copia.

### Le quattro tappe

| Comune | Anno | Fatto e fonte |
| --- | ---: | --- |
| Bagnaria Arsa | 1375 | Censimento con nomi, età e mestieri degli abitanti dei villaggi; non nascita del Comune moderno o primato censuario. [Storia comunale](https://www.comune.bagnariaarsa.ud.it/vivere-il-comune/territorio/storia-del-comune/). |
| Bagnaria Arsa | 1990 | Rinvenimento di undici tombe altomedievali; non data di origine della necropoli e non undici tombe tutte attribuite ai Longobardi. [Storia comunale](https://www.comune.bagnariaarsa.ud.it/vivere-il-comune/territorio/storia-del-comune/). |
| Talmassons | 1339 | Concessione in feudo a Corardo Bojani, mantenendo il nome personale della fonte. [Storia comunale](https://www.comune.talmassons.ud.it/informazioni-sul-comune/storia/). |
| Monfalcone | 1908 | Fondazione del Cantiere Navale Triestino su iniziativa dei Cosulich; il museo precisa il 3 aprile. [MuCa — Storia del cantiere](https://www.mucamonfalcone.it/storia-del-cantiere/). |

Ricerca, revisione e promozione sono nei tre file `municipalityMilestone{Research,FurReview,Promotion}.ud-go-enrichment-01.json`. Le copie di ricerca restano escluse dalla UI; l'eccezione alla revisione FUR indipendente è circoscritta ai quattro ID, non all'intero catalogo. I nomi ufficiali degli enti restano invariati. Controllati, fra gli altri, `censiment`, `regjistrâ`, `mistîr`, `alt medievâl`, `feut` e `fondâ` nei lemmi SuperDizionari. Nessuna certificazione linguistica implicita.

Nota per una successiva revisione del corpus precedente: ricontrollare `cjantiers` nella vecchia sintesi FUR di Monfalcone rispetto al lessico standard `cantîrs`. Non è parte delle quattro nuove frasi e non è stato cambiato in questo lotto.

### Audit del calendario rituale

Simulazione reale 2026–2031 in IT e FUR: **41 giorni con rito per anno**, massimo sei ripetizioni consecutive, nessuna collisione o violazione di precedenza. Tutte le **19 schede calendarizzabili** sono utilizzate almeno una volta nel sessennio. Nel 2028 ne compaiono 14; le cinque rimanenti entrano nella rotazione di altri anni, non sono contenuti permanentemente irraggiungibili.

| Mese 2028 | Giorni con rito | Schede distinte |
| --- | ---: | ---: |
| Gennaio | 6 | 2 |
| Febbraio | 6 | 2 |
| Marzo | 1 | 1 |
| Aprile | 6 | 4 |
| Maggio | 0 | 0 |
| Giugno | 7 | 2 |
| Luglio | 0 | 0 |
| Agosto | 1 | 1 |
| Settembre | 1 | 1 |
| Ottobre | 0 | 0 |
| Novembre | 0 | 0 |
| Dicembre | 13 | 3 |

La tabella misura l'uso reale del selettore, non promette una tradizione per ogni mese. I giorni senza rito rimangono intenzionalmente senza questa sezione. Nessuna nuova API, modifica al selettore meteo o all'interfaccia.

### Verifiche della seconda passata

- Controlli mirati: 32 test sui lotti rituali 02/03 e 31 su profili e lotti comunali PN/UD-GO, tutti superati; lint mirato e controllo diff superati.
- Tutti i sette riti precedenti sono identici tramite digest. Tutti i 215 profili sono identici alla prima passata rimuovendo soltanto le quattro nuove tappe; nessun profilo supera tre tappe.
- Suite frontend completa: **361 file, 2.333 test superati**. Lint completo e controllo mirato finale superati; `git diff --check` senza errori.
- Il nuovo controllo del sessennio inizialmente superava il limite di cinque secondi perché ripeteva sei simulazioni già svolte. I test ora riusano gli audit annuali non mutati; il solo test complessivo dispone di 30 secondi anche quando eseguito isolatamente. Nessuna modifica alle regole runtime o alle soglie di ripetizione, collisione e precedenza.
- Build Web di produzione e service worker standalone superati in una nuova directory temporanea del sistema operativo. Avviso sulle dimensioni dei chunk già noto e non bloccante; nessuna pubblicazione.
- Nessun commit, push, deploy, modifica al backend o nuova release Android.

## Terza passata — mestieri, abitazioni e memorie secondarie

Il successivo «procedi» amplia le rubriche diverse dai Comuni. Sono integrati **tre racconti d'archivio e due memorie secondarie**, tutti IT/FUR; nessuna modifica al selettore, all'interfaccia, ad Almanacco o ai servizi esterni.

### Nuovi racconti d'archivio

- **Stolvizza / Val Resia:** il passaggio dalla mola portata sulle spalle alla bicicletta usata anche per azionarla con i pedali. La sintesi distingue mezzo di trasporto e postazione ferma sui cavalletti; non parla di motore. [MiC — Museo dell'arrotino](https://cultura.gov.it/luogo/museo-dell-arrotino).
- **Gorizia:** il torcitoio circolare da seta settecentesco, mosso da una persona che cammina all'indietro al suo interno. Nessun primato di antichità, orario o programma di visita. La fonte principale è la scheda ERPAC leggibile su GO!2025, non il vecchio annuncio MiC in timeout. [ERPAC / GO!2025 — Museo della Moda](https://www.go2025.eu/it/imports/poi/erpac/museo-della-moda-e-delle-arti-applicate).
- **Grado:** materiali locali, unica stanza con focolare e orientamento a Ovest della porta dei casoni. Il riferimento ai venti descrive l'architettura e non attiva la scheda sulla base del meteo. Il Consorzio Grado Turismo è indicato correttamente come consorzio, non come Comune. [Grado Turismo — I casoni](https://grado.it/it/cosa-fare/natura/la-laguna-di-grado/i-casoni).

Le tre schede entrano nella normale rotazione annuale, senza date commemorative inventate. `archiveResearchWave03.json` conserva il manifest di fonti e duplicati; i testi sono presenti una sola volta nel catalogo `institutionalArchive.json`. Nessuna immagine o riproduzione delle fonti riutilizzata.

### Due secondarie triestine

- **1 gennaio 1810 — Società di Minerva:** fondazione su iniziativa di Domenico Rossetti, con il contesto dell'Archeografo Triestino avviato nel 1829. Il 1829 non viene attribuito alla ricorrenza del 1 gennaio. [Società di Minerva — storia](https://www.societadiminerva.it/demo/un-po-di-storia/).
- **5 ottobre 1964 — ICTP:** inaugurazione del centro all'Hotel Jolly, con Abdus Salam e studiosi di paesi diversi. Il fatto resta distinto dalla sede completata nel 1968. [ICTP — Training Scientists in Fusion Energy](https://2022.ictp.it/news/2024/5/training-scientists-fusion-energy), [CERN Courier — ICTP at 40](https://cern-courier.web.cern.ch/a/ictp-at-40-the-centres-legacy-for-the-future/).

Entrambe rispettano il filtro locale Trieste/TS e il limite esistente di tre secondarie. Nessuna sostituzione della primaria: restano Paolo Diacono il 1 gennaio e Francesco Arnaldi il 5 ottobre. La secondaria Pressburger del 5 ottobre rimane disponibile. Il manifest è `secondaryMemoryResearchWave01.json`.

### Revisione e stato corrente

Per tutte e cinque le aggiunte è registrata la revisione `user_delegated_assisted_editorial_review`, con `independentHumanReview: false`. I lemmi standard ARLeF sono riferimenti lessicali, non certificazione delle traduzioni. In FUR i termini tecnici italiani «torcitoio» e «casoni» sono citati senza inventare equivalenti; le denominazioni dell'associazione e della rivista restano proprie.

La regola di revisione umana di `localMemory` mantiene una **eccezione esplicita limitata ai due nuovi ID**. Le 14 bozze sospese precedenti non sono state promosse o modificate. Tutti i 579 record precedenti e le 20 schede istituzionali precedenti sono identici tramite digest.

| Rubrica | Situazione dopo il lotto |
| --- | --- |
| Comuni | 215 profili, 415 tappe; 133 profili con una o due tappe, invariati. |
| Riti | 23 schede, 19 calendarizzabili; invariati. |
| Detti | 63 schede, invariati. |
| Archivio | 72 schede complessive: 23 nel catalogo integrativo, 50 calendarizzabili, 22 meteorologiche ancora escluse. |
| Memorie | 581 record: 567 pronti, di cui 369 primari e 198 secondari su 146 date; 14 sospesi invariati. Le 366 date principali restano coperte. |

Nel 2028 Archivio compare in 366 giorni, usa 48 schede e non ripete la stessa per più di due giorni consecutivi. Le due ricorrenze d'archivio non selezionate restano correttamente coperte dalla Memoria del giorno. Tutte e tre le aggiunte entrano nella rotazione di ciascun anno 2026–2031 in entrambe le lingue, senza collisioni o violazioni di precedenza.

### Verifiche della terza passata

- Suite frontend completa: **363 file, 2.359 test superati**. Include 8 test del lotto Archivio, 17 delle memorie secondarie e la tracciabilità dei manifest nel backlog.
- Controlli mirati prima della suite: 81 test superati su dieci file; audit annuali 2026–2031 in IT/FUR e rendering delle nuove schede compresi.
- Lint frontend completo e `git diff --check`: superati. Rilettura indipendente assistita delle copie, delle fonti e dei diff: nessun problema concreto residuo.
- Build Web di produzione e service worker standalone: superati in `C:\Users\LOCALU~1\AppData\Local\Temp\meteofriul-scopri-a020f22417644f15a612fd008a9b55ed`. Avviso già noto sulle dimensioni dei chunk non bloccante.
- Nessun commit, push, deploy, modifica al backend o nuova release Android. Nessuna nuova verifica fisica su telefono: il lotto modifica contenuti e test, non l'interfaccia.

Il terzo lotto è concluso; **il piano complessivo Scopri resta in corso**. La revisione dei contenuti meteorologici prevista come seguito è documentata nella quarta passata.

## Quarta passata — recupero storico dei contenuti meteorologici

Valutati individualmente tutti i **26 record `weather`** del catalogo Ostermann. La decisione è in `frontend/src/data/discover/weatherContextReview.json`, che contiene metadati e motivazioni, non copie dei testi. Sono recuperati otto approfondimenti storici; diciotto rimangono esclusi con un prossimo controllo specifico.

### Gli otto recuperi

| ID | Racconto | Collocazione in Scopri |
| --- | --- | --- |
| `ost-0005-lessico-venti` | Nomi del vento raccolti da Ostermann | Archivio, tutto l'anno; nessuna deduzione del vento attuale. |
| `ost-0009-luna-lavori-agricoli` | Ruolo storico della luna nel calendario agricolo | Archivio, tutto l'anno; nessuna fase specifica inventata o consiglio agronomico attuale. |
| `ost-0021-segni-animali-vento` | Osservazione popolare degli animali | Archivio, tutto l'anno; il testo esclude già il valore previsionale. |
| `ost-0024-monti-col-cappello` | Nubi sulle cime come linguaggio del paesaggio | Archivio, primavera/estate/autunno; stagioni originali conservate. |
| `ost-0026-pioggia-grandine-streghe` | Paure storiche della grandine | Spostato da Riti ad Archivio, primavera/estate; nessun rito in corso. |
| `ost-0042-vespe-neve-inverno` | Corrispondenze popolari fra stagioni | Archivio, estate/inverno; conservata la frase che dichiara il legame non scientifico. |
| `ost-0048-palle-neve-slitte` | Giochi invernali e divieto udinese raccontato da Ostermann | Archivio, inverno; nessuna neve al suolo o condizione adatta alle slitte affermata. |
| `ost-0058-demoni-aria-tempeste` | Immaginario delle paure meteorologiche | Spostato da Riti ad Archivio, tutto l'anno; non spiegazione del tempo. |

La funzione `applyDiscoverWeatherEditorialPolicy` ammette soltanto gli otto ID autorizzati e soltanto i campi `section` e `recurrence`. Verifica collocazione e stagioni originali, assenza di vincoli di data aggiunti e idoneità editoriale già esistente. Non può riscrivere copy, fonte, identità o stato linguistico tramite l'override.

Gli otto ID sono anche esclusi dal focus generico quando manca un Comune riconosciuto. Il caso `2028-01-20`, località sconosciuta, inizialmente poteva mostrare il lessico dei venti nel riquadro principale oltre a un'altra scheda d'archivio: corretto con un'esclusione circoscritta e test su tutto gennaio in IT/FUR. Il comportamento dei vecchi candidati al focus non viene modificato.

Il file condiviso `ostermannCulturalDiscover.json` resta integralmente immutato: digest SHA-256 dei 63 record `f4a8864f7d16765c3e4091573e4fe66e48b24bd0669d05a63db8ba7c9c0bfc05`. Almanacco continua a importare quel file originale. Il selettore comune conserva `weather → null` e i Riti conservano il requisito di una data o finestra precisa.

### I diciotto esclusi e la provenienza meteo

Le esclusioni non sono tutte uguali: alcune richiedono fonti o copy da ricontrollare (nubi, segni di grandine, carlina, uccelli marini); altre una decisione di riuso storico o una regola lunare esplicita. I comportamenti animali, i colori del cielo e gli aloni non sono dimostrati dai tag pioggia, vento o luna. Campane e `lin di strie` restano i due Riti senza calendario esclusi.

L'audit tecnico del codice ha rilevato che i dati correnti possono mescolare stazione e modello, che `condition` può derivare dal bollettino e che il momento di salvataggio della cache non equivale all'istante dell'osservazione. È una constatazione sul contratto dati per un eventuale nuovo uso in Scopri, **non una modifica né una diagnosi completa delle altre viste**. Dettagli e limiti in `SCOPRI_WEATHER_CONTEXT_AUDIT_2026-08-31.md`.

Nessuna nuova richiesta meteo, API, prop di `DiscoverView` o regola lunare è stata introdotta. I racconti sono stabili per data e non cambiano con un aggiornamento del tempo durante la giornata.

### Stato dopo la riclassificazione

- **Archivio:** 74 record complessivi, di cui 58 calendarizzabili e 16 ancora esclusi come `weather`. Il conteggio totale aumenta di due per il trasferimento delle credenze, non per nuove copie.
- **Riti:** 21 record complessivi, di cui 19 calendarizzabili e due esclusi. La presenza reale resta di 41 giorni nel 2028 con 14 testi diversi; nessun nuovo riempitivo.
- **Catalogo culturale:** sempre 95 record. Comuni, 63 detti e 581 memorie invariati rispetto alla terza passata.
- **Archivio 2028:** 366 giorni coperti, 56 testi usati, massimo due ripetizioni consecutive. Le due ricorrenze restanti sono coperte dalla Memoria del giorno.
- **Audit 2026–2031 IT/FUR:** tutti gli otto recuperi compaiono ogni anno, senza collisioni o violazioni delle precedenze.

È una decisione editoriale assistita sul riuso dei testi esistenti (`user_delegated_assisted_editorial_review`), non una nuova verifica della fonte storica o certificazione linguistica. Restano invariati anche i metadati originali `it: ready_draft`, `fur: approved`, `editorialStatus: ready_it`; nessuna promozione linguistica silenziosa.

### Verifiche della quarta passata

- Suite frontend finale: **365 file, 2.376 test superati**. Lint completo superato; `git diff --check` senza errori.
- Controlli iniziali: 66 test su sette file (policy, integrazione, calendario, backlog, composizione giornaliera e Almanacco), tutti verdi. Dopo la correzione del focus generico, ulteriori 37 test mirati verdi prima di ripetere l'intera suite.
- Dodici test della policy verificano le 26 decisioni, gli otto soli override, il digest della fonte originale, input congelati, esclusioni, stati non pronti, limiti stagionali e precedenza delle date esatte. Quattro test di integrazione controllano testo/fonti renderizzati e comportamento con Comune sconosciuto in entrambe le lingue.
- L'audit pluriennale mantiene tutte le soglie precedenti: nessuna collisione, date certe rispettate e massimo due ripetizioni consecutive nell'Archivio. La matrice esistente verifica anche il modello completo (focus e secondarie inclusi) su 366 giorni, quattro province e due lingue.
- Build Web di produzione e service worker standalone superati nella directory temporanea `C:\Users\LOCALU~1\AppData\Local\Temp\meteofriul-scopri-9842ba1dadb34621a9525b875e7e10ff`. Avviso già noto sulle dimensioni dei chunk non bloccante.
- Nessun commit, push, deploy, modifica al backend o release Android. Nessuna nuova prova fisica sul telefono; verificati i modelli e il rendering delle schede, senza modificare il layout.

La valutazione iniziale dei 26 record è conclusa; le 18 esclusioni restano lavoro editoriale tracciato. Il piano generale non è completo: prossimo lotto su ricorrenze rituali poco rappresentate, continuando l'ampliamento delle altre rubriche.

## Quinta passata — riti di luglio e ottobre

Due nuove schede IT/FUR, con decisione editoriale assistita limitata agli ID del manifest `ritualResearchWave04.json`. Non è una certificazione ARLeF né una revisione linguistica professionale indipendente. Il dossier non è importato dalla UI e rimanda alla copia unica dei testi nel catalogo.

- **Sappada/Plodn, 20 luglio:** Santa Margherita e il ruolo dei ragazzi coscritti. La fonte distingue la festa dalla descrizione generale delle processioni estive: anche la copy mantiene questa distinzione. Plodn è il nome sappadino, non una traduzione friulana. [Associazione Plodar — Tradizioni](https://www.plodn.info/tradizioni/).
- **Piano d’Arta, prima domenica di ottobre:** rosari e fiori preparati dalla comunità. Il racconto dei preparativi resta esplicitamente attribuito al 2014, senza annunciare il programma corrente. [Arcidiocesi di Udine — Rosario a Piano d’Arta](https://www.diocesiudine.it/wd-appuntamenti/piano-darta-celebra-la-madonna-del-rosario/).

### Calendario ordinale

`nthWeekdayDates` aggiunge ricorrenze del tipo prima domenica del mese, con lo stesso rango delle feste mobili. Il criterio è il giorno civile esatto, non un intervallo di sette giorni: Piano d’Arta è selezionabile il 4 ottobre 2026, 3 ottobre 2027, 1 ottobre 2028, 7 ottobre 2029, 6 ottobre 2030 e 5 ottobre 2031.

Mese, giorno della settimana e ordinale sono interi validati; una quinta occorrenza assente non slitta al mese successivo. Regole esplicite vuote, malformate o non corrispondenti non attivano la rotazione generica. Date fisse, Pasqua e intervalli esistenti conservano le precedenze. Il guard del riuso meteorologico rifiuta anche questo nuovo vincolo, per non cancellarlo durante una riclassificazione futura. Il contratto dei contenuti documenta il campo; nessuna modifica al calendario dell'Almanacco.

### Candidati non forzati nel calendario

- **Illegio:** la fonte culturale collega la salita a San Floriano al 4 maggio, ma il programma 2025 la colloca il 3 maggio. Non è stato aggiunto un rito invariabile al 4 maggio. [Comitato San Floriano](https://illegio.it/luoghi-di-interesse/), [programma UNPLI 2025](https://prolocoregionefvg.it/eventi-delle-associate/sagra-di-san-floriano-illegio-2/).
- **Barbana:** esiste già `memory-draft-grado-perdon-barbana`, non promossa e non duplicata. La futura valutazione può ora usare una regola ordinale, ma richiede ancora il recupero editoriale della traccia esistente.
- **Maj di Lucinico:** già presente nell'Archivio, senza crearne una seconda copia come rito.
- **Maggio e novembre:** ricerca ancora aperta; nessun candidato dubbio o semplice tag stagionale aggiunto per occupare i mesi vuoti.

Le altre quattro rubriche sono invariate in questa passata. Il prossimo lotto torna ai Comuni con una o due tappe, mantenendo aperta la ricerca rituale: completamento generale ancora in corso.

### Stato e controlli del lotto

- Catalogo culturale: **97 record**; Riti: **23**, di cui **21 calendarizzabili** e due meteorologici esclusi. I nove riti istituzionali precedenti sono integralmente identici (digest dei primi nove record: `0dfd677b84a070d3f477a968de38fd82485d20734272c310a9a83dad3d5b132b`).
- Simulazione 2026–2031 IT/FUR: **43 giorni con rito per anno**, entrambi i nuovi ID presenti esattamente una volta per anno. Nel 2028 sono usati 16 testi; tutti i 21 calendarizzabili sono utilizzati nel sessennio. Nessuna collisione o alterazione delle precedenze; massimo sei ripetizioni consecutive invariato.
- Test mirati: **68 test su sette file**, più **26 test del lotto Wave04**, superati. Verificati anche il rendering di testo e fonte, l'assenza nei giorni adiacenti, i dati congelati e il blocco di regole ordinali invalide.
- Nessun contenuto, layout, backend o pacchetto Android esterno al perimetro Scopri modificato in questa passata. Nessun commit, push o deploy.

### Verifica finale della quinta passata

- Suite frontend completa: **366 file, 2.412 test superati** con `node node_modules/vitest/vitest.mjs run --configLoader native --maxWorkers 2` (138 secondi). Nessuna soglia o asserzione indebolita.
- L'esecuzione a parallelismo automatico aveva superato 2.410 test e fallito soltanto per timeout sull'audit Almanacco 2024–2100 e su una simulazione annuale Scopri. Un primo tentativo di limitare i worker tramite lo script npm non aveva inoltrato l'opzione e fu interrotto; la ripetizione completa diretta con due worker, senza lint concorrente, è tutta verde.
- Lint completo e `git diff --check`: superati.
- Build Web di produzione e service worker standalone: superati in `C:\Users\LOCALU~1\AppData\Local\Temp\meteofriul-scopri-002e80c7c3524e968c00c6e768cd2015`. Rimane soltanto l'avviso già noto sulle dimensioni dei chunk.
- Verifica basata su modelli e rendering delle schede: nessuna nuova prova fisica Android, nessuna pubblicazione.

## Sesta passata — tappe comunali TS/UD/PN

Il nuovo lotto aggiunge **sei tappe IT/FUR** a tre profili con una sola tappa: **Muggia, Artegna e San Vito al Tagliamento**. Nessuna modifica al layout, al selettore delle rubriche, ad Almanacco, alle webcam, al backend o ad Android.

| Comune | Nuove tappe | Fonti verificate |
| --- | --- | --- |
| Muggia | 1420: passaggio alla sovranità veneziana. 2006: inaugurazione del Museo d'arte moderna Ugo Carà. | [SIUSA](https://siusa-archivi.cultura.gov.it/cgi-bin/siusa/pagina.pl?Chiave=9188&TipoPag=prodente), [ERPAC](https://patrimonioculturale.regione.fvg.it/museo/?s_id=440670). |
| Artegna | 1384: il castello inferiore passa ai Savorgnan. 1878: nasce la banda musicale guidata da Luigi Mattiussi. | [SABAP FVG](https://sabapfvg.cultura.gov.it/artegna/), [ANBIMA FVG](https://www.anbimafvg.it/index.php/2018/03/31/artegna/). |
| San Vito al Tagliamento | 1369: attestazione dell'Ospedale dei Battuti. 21 marzo 1973: primo spettacolo ERT al Teatro Cinema Italia. | [Guidarte](https://guidartefvg.it/elenco/la-chiesa-dei-battuti-san-vito-al-tagliamento/), [ERT FVG](https://ertfvg.it/teatri/san-vito-al-tagliamento/). |

### Distinzioni conservate

- **Muggia:** il patto del 1202 non equivale alla sovranità del 1420; donazione del 1999 ed edificio del 2004–2005 non sostituiscono l'apertura del museo nel 2006. La memoria di Ugo Carà riguarda invece la nascita dell'artista. La tappa comunale precedente resta un secolo (13° / Secul 13), senza inventare un anno.
- **Artegna:** il 1005 rimane il riferimento a un'iscrizione; il 1384 è un passaggio di proprietà, non la costruzione. La banda nasce nel 1878, ma l'intitolazione a Mattiussi risale al 1953. ANBIMA è indicata come fonte culturale associativa, non comunale. Il passaggio del castello è corroborato anche dall'[Ecomuseo delle Acque](https://www.ecomuseodelleacque.it/collezione-ecomuseale/siti-storico-archeologici/artegna-castello-savorgnan/).
- **San Vito:** il 1369 è una notizia documentaria; la fonte riferisce un'attività già nel 1360. Il primato del 1973 riguarda soltanto ERT in quella sala, non l'origine del teatro cittadino. Guidarte è un progetto della Deputazione di Storia Patria per il Friuli, con testo di Paolo Pastres; i [crediti](https://guidartefvg.it/progetto/) non sono attribuiti al Comune. Nessun programma attuale, prezzo o orario teatrale è stato importato.

### Tracciabilità e stato corrente

La ricerca, la revisione FUR e la promozione sono conservate nei tre manifest `municipalityMilestoneResearch.ts-ud-pn-enrichment-01.json`, `municipalityMilestoneFurReview.ts-ud-pn-enrichment-01.json` e `municipalityMilestonePromotion.ts-ud-pn-enrichment-01.json`. Le copie di ricerca non sono lette dal runtime. Ogni tappa nel catalogo conserva la propria fonte.

I lemmi ARLeF sono stati letti in HTML, compresi i risultati di ricerca che mostrano la voce completa. Le denominazioni proprie vengono mantenute; la traduzione descrittiva non viene presentata come denominazione ufficiale friulana. L'approvazione è `user_delegated_assisted_editorial_review`, con `independentHumanReview: false`; la deroga alla policy di revisione umana è limitata ai sei nuovi ID. Nessuna certificazione ARLeF o revisione professionale indipendente implicita.

Il catalogo raggiunge **421 tappe per 215 Comuni**: 94 profili con una tappa, 36 con due, 85 con tre. Restano **130 profili** sotto l'obiettivo editoriale di tre tappe; non vengono riempiti senza fonti. Rimuovendo soltanto le sei aggiunte, tutti i 215 profili conservano esattamente il digest precedente `37abbddf45bcf823d52f8c4728f44e7b87583682ae5b8f3950f2bd324b9c39f6`.

Le altre rubriche sono invariate: 23 riti (21 calendarizzabili), 63 detti, 74 schede d'Archivio (58 calendarizzabili), 581 memorie di cui 567 pronte. Il piano generale resta aperto: **prossimo focus sui detti**, privilegiando il patrimonio già revisionato e la varietà, senza duplicare il testo dell'Almanacco.

### Verifiche della sesta passata

- Test mirati: **55 test su cinque file**, inclusi 13 nuovi controlli di fonti, date, revisione assistita, integrità dei profili e rendering IT/FUR. L'ISTAT prevale anche quando l'etichetta della città è discordante.
- Suite frontend completa: **367 file, 2.425 test superati** con configurazione nativa e due worker (134 secondi). I conteggi storici delle promozioni precedenti non sono riscritti; il backlog verifica la situazione corrente.
- Lint completo e `git diff --check`: superati. Rilettura assistita separata dei sei testi e dei tre manifest: nessun problema concreto rilevato.
- Build Web di produzione e service worker standalone: superati in `C:\Users\LOCALU~1\AppData\Local\Temp\meteofriul-scopri-031667f0e3744b0a9da7598d3644a8f2`. Avviso sulle dimensioni dei chunk già noto e non bloccante.
- Nessuna nuova prova fisica su Android. Nessun commit, push o deploy; tutte le modifiche dei lotti precedenti sono conservate.

## Settima passata — varietà dei detti e crediti bibliografici

La rubrica **Si diceva che…** passa da **63 a 75 detti**: undici schede dedicate e 64 riusi dell'Almanacco. Il lotto aggiunge soltanto dodici riferimenti a testi IT/FUR già approvati, senza nuove traduzioni o trascrizioni. Non cambia né amplia il repertorio dell'Almanacco, che mantiene tutti i suoi 379 record.

### Dodici immagini proverbiali

| Tema | Detti selezionati | Edizione e pagine PDF già documentate |
| --- | --- | --- |
| Campi | Conservare il frumento; il prato falciato in cui non ci si nasconde. | Ostermann 1876, 45 e 149. |
| Mestieri e casa | Battere il ferro caldo; la sola farina non basta per il pane. | Ostermann 1876, 147 e 234. |
| Rapporti quotidiani | Voler bene non costa; il sangue comune; lo staio di sale per conoscersi; mantenere le promesse. | Ostermann 1876, 302, 304, 175 e 190. |
| Collaborazione e pazienza | Le gocce che forano la pietra; quattro occhi; piegarsi senza spezzarsi; dare tempo al tempo. | Ostermann 1876, 201, 176, 180 e 230. |

I dodici testi non hanno vincoli di calendario nel catalogo autorevole: entrano nella rotazione generale. Il ferro caldo e le gocce sono immagini proverbiali, non osservazioni meteo; il sale non è una quantità alimentare consigliata. Nessun mese di fienagione, ricorrenza affettiva, fase lunare o dato meteorologico è stato inventato.

La seconda lettura assistita non ha rilevato doppioni equivalenti fra i dodici o rispetto ai 63 detti precedenti. Le affinità di tema restano distinte: osservazione condivisa, forza dell'unione, attesa e azione ripetuta non sono la stessa formulazione. Rimangono escluse dal lotto le varianti già rappresentate e i proverbi che richiedono un contesto temporale più specifico.

Il manifest `traditionalSayingReuseWave03.json` traccia ID, motivazione, citazione e data dell'approvazione preesistente. Non contiene una seconda copia IT/FUR, non viene letto dalla UI e non attribuisce una nuova revisione umana, certificazione ARLeF o lettura del facsimile a questa passata. La scelta di riuso è assistita; le approvazioni linguistiche restano quelle dei record originali.

### Correzione dei crediti

L'adattatore del riuso assegnava **Ostermann 1876 a tutte le fonti**. Undici dei 52 riusi precedenti hanno invece come fonte primaria il volume 1894; dieci perdevano anche la pagina PDF perché la stringa bibliografica non conteneva la sigla «PDF».

Ora anno e pagina provengono dalla citazione primaria e dai metadati strutturati. Il riscontro secondario 1876 del detto sulla pioggia non sostituisce più la fonte primaria 1894. Le pagine PDF e del testo restano distinte; non si ricavano pagine o anni dall'ID, non si promuove un riscontro secondario e non si inventa l'anno di una fonte sconosciuta. Il testo della citazione completa e il riferimento al catalogo autorevole restano disponibili. La correzione è verificata anche nel rendering del credito visibile.

### Integrità e seguito

- Digest JSON dell'intero catalogo Almanacco invariato: `fc6d44d1636cc9c3eaa6aeb7e8fefcdba88cf35f4ba51173ef52dd15176169d6`.
- Undici schede dedicate invariate: `2815007a540341eb22de796fa0d2ecc156da9c764c0a5bf9d41c5a9e169c7f1a`.
- Primi 52 descrittori di riuso invariati: `894c51de12d2051dd7e172604b803debc312419469935aaf4007a8a41074b449`.
- Nessuna modifica alle regole del selettore. La nota editoriale del riuso ora descrive correttamente l'alternanza già esistente fra detti generali e periodi, mantenendo la precedenza delle date esatte e mobili.
- Comuni, memorie, riti e Archivio invariati in questa passata. Nessuna modifica al layout, alle webcam, al backend o ad Android.

Il piano complessivo rimane aperto. Il prossimo lotto torna ai **Comuni con una o due tappe**, senza considerare esaurito il lavoro sulle altre rubriche. Il repertorio dei detti resta ampliabile per varietà, non per riempire giorni vuoti.

### Verifiche della settima passata

- Controlli mirati: **85 test su dieci file**, tutti superati. Il nuovo lotto aggiunge 24 controlli di integrità, riuso, calendario e rendering; tre ulteriori test coprono le fonti bibliografiche, inclusi riscontri secondari, ID fuorvianti e pagine invalide.
- Simulazione 2026–2031 IT/FUR: tutti i **75 detti** sono utilizzati in ciascun anno, senza giornate vuote, senza collisioni visibili fra rubriche e con al massimo due ripetizioni consecutive. Le otto date esatte e le precedenze mobili restano rispettate; ogni nuovo testo è verificato anche nel modello UI e nel rendering di entrambe le lingue.
- Suite frontend completa: **369 file, 2.452 test superati**, con configurazione nativa e due worker (139 secondi).
- Lint completo e `git diff --check` superati. Build Web di produzione e service worker standalone superati in `C:\Users\LOCALU~1\AppData\Local\Temp\meteofriul-scopri-a9f1fa37a8b24d3b90fd48b4ee407b47`; avviso sui chunk già noto e non bloccante.
- Nessuna nuova prova fisica Android. Nessun commit, push o deploy; preservato tutto il lavoro precedente.

## Ottava passata — Gemona, Grado e Aviano

Sei tappe IT/FUR arricchiscono tre profili che ne avevano una sola. L'ordine cronologico e le tappe precedenti restano invariati; non vengono aggiunte nuove schede alle altre rubriche.

| Comune | Nuove tappe | Fonte specifica |
| --- | --- | --- |
| Gemona del Friuli / Glemone | 1502, avvio del rifacimento del Palazzo Comunale; 2008, apertura dell'Archivio Cinema del Friuli Venezia Giulia. | Comune: [Palazzo Comunale](https://www.visitgemona.com/feel/percorsi/passeggiata-in-centro/) e [Cineteca](https://www.visitgemona.com/feel/arte-e-cultura/la-cineteca-del-friuli/). |
| Grado / Grau | 1892, titolo di Azienda di cura; 1936, inaugurazione del ponte girevole verso la terraferma. | Consorzio Grado Turismo: [storia dal 1892](https://grado.it/it/cosa-fare/arte-storia-e-cultura/la-storia-di-grado/grado-dal-1892) e [origini](https://grado.it/it/cosa-fare/arte-storia-e-cultura/curiosita/le-origini); [Archivio Luce](https://patrimonio.archivioluce.com/luce-web/detail/IL5000023897/2/l-inaugurazione-del-nuovo-ponte-girevole-che-unisce-grado-alla-terraferma.html). |
| Aviano / Davian | 1615, consacrazione del Santuario della Madonna del Monte; 1971, apertura internazionale del Festival del Folklore. | [Diocesi di Concordia-Pordenone](https://diocesi.concordia-pordenone.it/santuario-diocesano-madonna-del-monte-in-costa-di-aviano/) e [Pro Loco Aviano](https://www.prolocoaviano.it/festival-del-folklore/). |

### Cautele applicate

- Il 1502 non diventa l'inaugurazione del Palazzo Comunale. L'Archivio aperto nel 2008 non è confuso con la Cineteca fondata nel 1977.
- Per il riconoscimento gradese è registrato il **25 giugno 1892**, distinto dalla spedizione della legge a luglio. Nessuna affermazione sull'efficacia medica delle cure viene importata.
- Per il ponte si conserva **soltanto il 1936**: il Consorzio indica il 14 luglio, ma il cinegiornale Luce B0902 che documenta l'inaugurazione è datato 17 giugno. Neppure quest'ultima data diventa quella della cerimonia. Non si afferma che fosse il primo collegamento mai esistito.
- L'apparizione religiosa del 1510 non viene presentata come fatto storico accertato. La consacrazione del santuario è distinta dalla fondazione.
- La pagina del festival riporta sia 1968 sia 1969 per la nascita: la tappa usa solo il passaggio internazionale del 1971. Nessun programma attuale, orario, numero cumulativo di partecipanti o fotografia è riprodotto.

### Revisione, integrità e seguito

Ricerca, revisione FUR e promozione sono separate nei tre manifest `municipalityMilestone{Research,FurReview,Promotion}.ud-go-pn-enrichment-02.json`. La verifica lessicale usa pagine HTML ARLeF, senza attribuire all'ente la certificazione delle frasi. L'approvazione editoriale assistita è limitata ai sei ID; `independentHumanReview` resta `false` e la policy generale di revisione umana non cambia. I nomi propri storici e istituzionali non ricevono traduzioni ufficiali inventate.

Il catalogo raggiunge **427 tappe per 215 Comuni**: 91 profili con una tappa, 36 con due e 88 con tre. Restano **127 profili** sotto l'obiettivo editoriale, da esaminare senza riempimenti automatici. Eliminando soltanto le sei aggiunte, il digest JSON dei profili rimane `ae22259e3c03c4cad00c26da19e957ed37437e4354b708d43d74816496cc99cf`: tutte le 421 tappe e i metadati precedenti sono conservati.

Il piano non è concluso. Il prossimo focus torna a **Riti e credenze popolari**, approfondendo soprattutto maggio e novembre e riutilizzando eventuali bozze esistenti, senza duplicarle. Almanacco, 75 detti, 23 riti, 74 schede d'Archivio e 581 memorie non cambiano in questa passata. Nessuna modifica a layout, webcam, backend o Android.

### Verifiche dell'ottava passata

- Test mirati: **69 test su sei file**, superati. Quattordici nuovi controlli coprono fonti, date controverse, revisione assistita, integrità e rendering IT/FUR dei tre profili.
- Suite frontend completa: **370 file, 2.466 test superati**, configurazione nativa e due worker (150 secondi).
- Lint completo e `git diff --check` superati. Build Web di produzione e service worker standalone superati in `C:\Users\LOCALU~1\AppData\Local\Temp\meteofriul-scopri-9fb3763fb7734c8c90d49e01170bfc1a`; avviso sui chunk già noto e non bloccante.
- Seconda lettura assistita delle sei tappe e dei manifest: nessun problema concreto rilevato. Oltre al digest pre-passata, confermata la conservazione delle 407 tappe già in HEAD; le venti aggiunte complessive appartengono ai quattro lotti comunali locali.
- Nessuna nuova prova fisica Android. Nessun commit, push o deploy.

## Nona passata — riti di maggio e novembre

Due schede IT/FUR introducono ricorrenze documentate nei due mesi che non avevano ancora riti selezionabili. I testi restano brevi: raccontano le pratiche locali, non annunciano eventi in programma.

### Pasian di Prato, 31 maggio

La processione mariana riunisce le parrocchie del territorio e collega a piedi San Giacomo e l'istituto «La Nostra Famiglia». Il [testo diocesano del 2024](https://www.diocesiudine.it/wd-appuntamenti/pasian-di-prato-con-maria-in-cammino-fino-a-la-nostra-famiglia/) dichiara esplicitamente la ricorrenza annuale del 31 maggio. Il [programma della parrocchia per il 2025](https://www.parrocchiapasiandiprato.it/maggio-mese-mariano-ecco-gli-appuntamenti/) conferma la data ma descrive il percorso in senso inverso: perciò la scheda non fissa partenza e arrivo.

Il contenitore calendario della pagina del 2024 indica invece 1 giugno. La regola deriva dalla descrizione esplicita della tradizione, non da quel metadato discordante. Gli anniversari dell'istituto e del fondatore citati per il 2024 non diventano ricorrenze annuali; nessun orario viene importato.

### Moggio Udinese, 21 novembre

La Madonna della Salute è accompagnata in processione dai pompieri volontari, che portano la statua a spalla; partecipano anche fedeli dei paesi vicini. Le testimonianze dell'Arcidiocesi del [2024](https://www.diocesiudine.it/wd-appuntamenti/moggio-udinese-messa-e-processione-per-la-madonna-della-salute/) e del [2022](https://www.diocesiudine.it/wd-appuntamenti/a-moggio-udinese-si-rinnova-la-processione-della-madonna-della-salute/) concordano sul 21 novembre e sui portatori.

Anche qui il contenitore calendario riporta il giorno successivo, 22 novembre: non viene adottato. La fonte del 2022 dichiara incerte le origini e ricorda una sospensione durante la pandemia; non si inventano una fondazione, una continuità senza interruzioni o un'origine legata agli emigranti. Nessuna efficacia sanitaria viene attribuita alla pratica religiosa.

### Tracciabilità e integrità

- `ritualResearchWave05.json` conserva fonti, calendario, ambito, cautele e decisione editoriale; resta non visibile e non contiene una seconda copia dei testi. Le due schede approvate sono aggiunte a `institutionalRituals.json`.
- Lessico FUR controllato tramite HTML ARLeF, compresi `parochiis`, `pompîrs`, `spalis` e `Mueç`; i nomi propri delle istituzioni sono conservati. Si tratta di revisione assistita, non certificazione ARLeF, revisione professionale indipendente o approvazione dell'utente frase per frase.
- I precedenti undici riti istituzionali restano identici: digest JSON `69c3ff377ad63fa00dcef3d7445a204603f315edc7e826e738f0ff2ed69777b6`. Verificata anche l'integrità dei cataloghi Archivio, Memorie, Comuni e Ostermann rispetto all'inizio della passata.
- Le memorie del 31 maggio e del 21 novembre raccontano fatti differenti; non sono soppresse né duplicate. Barbana resta bozza non visibile. Il Maj di Lucinico è già nell'Archivio; Illegio richiede ancora una regola distinta dalla semplice memoria del santo.

Il catalogo culturale passa da **97 a 99 schede**. La rubrica conta **25 riti**, di cui **23 calendarizzabili** e due ancora esclusi perché dipendenti dal meteo. Nel 2028 mostra **18 riti diversi su 45 giorni**; negli altri giorni non appare per riempire la pagina. Le due aggiunte compaiono esclusivamente il 31 maggio e il 21 novembre, anche in friulano.

Il lavoro non è concluso: una ricorrenza per mese non esaurisce varietà territoriale e cicli agricoli. Il prossimo lotto torna ad **Archivio e tradizioni**, ampliando temi e territori oltre alle feste religiose. Restano invariati le 427 tappe comunali, i 75 detti, le 74 schede d'Archivio, le 581 memorie e l'Almanacco. Nessuna modifica a selettori runtime, layout, backend, webcam o Android.

### Verifiche della nona passata

- **85 test mirati su sette file superati**, inclusi 24 nuovi controlli delle schede e la simulazione pluriennale 2026–2031 IT/FUR. Sono verificati anche assenza nei giorni adiacenti, credito visibile e indipendenza dell'ambito culturale dalla posizione dell'utente.
- Suite frontend completa: **371 file, 2.490 test superati**, configurazione nativa e due worker (154 secondi).
- Lint e `git diff --check` superati. Build Web e service worker standalone superati in `C:\Users\LOCALU~1\AppData\Local\Temp\meteofriul-scopri-38a4a71df5624bfea247a4e12ab9a724`; avviso sui chunk già noto e non bloccante.
- Seconda lettura assistita e confronto sul runtime reale, ricostruendo il catalogo precedente senza i due ID: nel 2028 IT/FUR cambiano esclusivamente 31 maggio e 21 novembre. Memoria, secondarie, detti e Archivio sono identici; nessuna collisione o violazione di precedenza. Confermato il digest degli undici riti precedenti.
- Nessun commit, push, deploy o nuova prova fisica Android.

## Decima passata — oggetti, mestieri e trasporti

Tre nuove schede brevi IT/FUR ampliano Archivio e tradizioni oltre alle feste religiose:

- **Maniago, il rumore del maglio.** La [scheda ERPAC PST_219](https://patrimonioculturale.regione.fvg.it/patrimonio-scientifico-tecnologico/?s_id=597151), letta integralmente in HTML, documenta la molla a lamine e l'operatore che riconosceva dal rumore una lamina rotta. Il racconto resta riferito al macchinario descritto e alla testimonianza raccolta, senza istruzioni di manutenzione o generalizzazioni a tutte le officine. Non duplica la mola dell'arrotino né le tappe del museo di Maniago.
- **Pesariis, gli orologi sotto i portici.** La [scheda MiC del Museo dell'orologeria Pesarina](https://cultura.gov.it/luogo/museo-dell-orologeria-pesarina) documenta la produzione familiare seicentesca, la collocazione sotto i portici e il rapporto con i lavori agricoli. Il Seicento è contesto storico, non una ricorrenza; nessun primato, orario museale o nuova fondazione. Il tema è distinto dalle tappe su Solari e sul museo nel profilo di Prato Carnico.
- **Opicina, il tram aiutato dalla fune.** La [pagina del servizio TPL FVG](https://tplfvg.it/it/servizi/tramopicina/) descrive le vetture spinte o trattenute dai carri-scudo nel tratto ripido di circa 800 metri. Non è la lunghezza dell'intera linea. Non vengono importati inaugurazione, riapertura, unicità, tariffe o programmi di servizio; la scheda racconta il meccanismo di trasporto, non promette corse attuali. Le memorie già presenti su Opicina riguardano invece la Seconda guerra mondiale.

### Revisione e integrazione

- `archiveResearchWave04.json` conserva fonti, cautele, confronto con i cataloghi precedenti e decisione editoriale. Il manifest resta nascosto alla UI; i testi sono presenti una sola volta nei tre record aggiunti a `institutionalArchive.json`.
- Sono schede in rotazione annuale: nessuna data forzata, stagione esclusiva o attivazione meteorologica. Gli ambiti restano Maniago, Pesariis/Prato Carnico/Carnia e Trieste/Opicina/Carso, senza attribuirli al Comune selezionato dall'utente.
- ERPAC è un catalogo regionale, MiC una fonte museale e TPL FVG un operatore del trasporto pubblico: le tipologie delle fonti non sono uniformate artificialmente. Nessuna immagine o riproduzione riutilizzata.
- Lessico controllato nelle pagine HTML ARLeF: fra gli altri `mai`, `balestre`, `suste`, `orloi`, `puarti`, `Sîscent`, `agricul`, `cuarde`, `funicolâr`, `stratignî` e `Cjars`. Il composto tecnico italiano «carri-scudo» resta citato. Revisione assistita con seconda lettura, non certificazione ARLeF, revisione umana indipendente o approvazione dell'utente frase per frase.
- Confermata l'integrità dei 23 record d'Archivio precedenti con digest JSON `a33c0a3cfd40008ebe12ca8763c22ecfc23ef5ddb485ebd2e602e73d4ff08bfe`. Invariati anche i digest di Riti, Memorie, Comuni e catalogo Ostermann condiviso.

Le schede d'Archivio da queste fonti passano da **23 a 26**; il catalogo culturale complessivo da **99 a 102**. La rubrica Archivio conta **77 record**, di cui **61 calendarizzabili** e sedici meteorologici ancora esclusi. Nel 2028 utilizza **59 schede diverse su 366 giorni**; due ricorrenze restano correttamente assorbite da Memoria del giorno. Ripetizione consecutiva massima: due giorni.

Le altre rubriche non vengono ampliate in questa passata: 427 tappe comunali, 25 riti, 75 detti e 581 memorie. Il piano complessivo resta aperto: prossimo focus sui **127 Comuni con una o due tappe**, senza perdere l'alternanza con le altre rubriche. Nessuna modifica al layout, al backend, ad Android o alle webcam.

### Verifiche della decima passata

- Sette nuovi test coprono integrità, manifest, fonti, revisione assistita, ambito, regole temporali e rendering delle tre schede in IT/FUR. Il confronto con il catalogo precedente sui 366 giorni del 2028 conferma selezioni identiche per Memoria, secondarie, riti e detti.
- La simulazione pluriennale 2026–2031 in entrambe le lingue utilizza tutte e tre le aggiunte senza collisioni o violazioni delle ricorrenze; ripetizione consecutiva massima dell'Archivio ancora di due giorni.
- Suite frontend completa finale: **372 file, 2.497 test superati**, configurazione nativa e due worker (203 secondi). Il nuovo controllo con due simulazioni annuali aveva superato il timeout predefinito di cinque secondi sotto carico: timeout circoscritto a quel test portato a quindici secondi e intera suite rieseguita, senza indebolire le asserzioni.
- Lint completo e `git diff --check` superati. Build Web di produzione e service worker standalone superati in `C:\Users\LOCALU~1\AppData\Local\Temp\meteofriul-scopri-759e7d85961e4d8b8199349eaa961386`; avvisi sui chunk e sui tempi dei plugin non bloccanti.
- Seconda lettura assistita di testi e collegamenti manifest/runtime: nessun problema concreto rilevato. Nessun commit, push, deploy o nuova prova fisica Android.

## Undicesima passata — tre nuove tappe comunali

Tre profili che avevano due sole tappe raggiungono il massimo editoriale di tre fatti documentati. Il lotto alterna nuovamente il lavoro sui Comuni dopo l'ampliamento di Archivio e tradizioni.

- **Aquileia, 1998.** L'[area archeologica e la Basilica patriarcale](https://unesco.cultura.gov.it/projects/archaeological-area-and-the-patriarchal-basilica-of-aquileia/) entrano nella Lista del Patrimonio Mondiale UNESCO; la [scheda internazionale UNESCO](https://whc.unesco.org/en/list/825/) conferma bene e anno. La tappa nomina entrambe le componenti, non estende il riconoscimento indistintamente all'intera città e non trasforma l'iscrizione in fondazione o inizio della tutela.
- **Gradisca d'Isonzo, 1788.** Gradisca diventa sede vescovile fino al 1791, come documentano la [cronologia del Comune](https://www.comune.gradiscadisonzo.go.it/it/novita-232939/avvisi-232942/la-citta-48177) e il [SIUSA del Ministero della Cultura](https://siusa-archivi.cultura.gov.it/cgi-bin/siusa/pagina.pl?Chiave=9097&RicDimF=2&RicProgetto=reg-fvg&TipoPag=prodente). Sono escluse le transizioni politiche del 1647 e del 1754, troppo vicine alla tappa asburgica del 1511 già presente.
- **Cordenons, 1902.** Viene creato il giardino di Villa Raetz. La [scheda ERPAC PG_49](https://patrimonioculturale.regione.fvg.it/parchi-e-giardini/?s_id=749704) lo data al 1902, contemporaneamente alla villa padronale e al cotonificio, e attribuisce a Guglielmo Raetz il disegno del giardino. La tappa non gli attribuisce anche il progetto degli edifici e non aggiunge giorno, apertura o programma di visita.

### Tracciabilità e integrità

- Ricerca, revisione FUR e promozione sono separate nei tre manifest `municipalityMilestone*ud-go-pn-enrichment-03.json`, non importati dalla UI. Soltanto le tre tappe approvate sono integrate in `municipalityProfiles.json`.
- Ogni tappa conserva una fonte propria; Aquileia e Gradisca hanno anche la seconda fonte istituzionale. Gli anni restano 1998, 1788 e 1902, senza giorno o mese dedotti.
- I testi FUR sono stati controllati su HTML ARLeF e con seconda lettura assistita. La decisione è limitata ai tre ID del lotto e non equivale a certificazione ARLeF, revisione professionale indipendente o approvazione dell'utente frase per frase.
- Rimuovendo le sole tre aggiunte, i 215 profili e le 427 tappe precedenti restituiscono il digest JSON `bbbe2ca3e24e7e52701090bd2cfa53b12ac219c93e02dca0af833327657e799a`.

Il catalogo raggiunge **430 tappe per 215 Comuni**: 91 profili con una tappa, 33 con due e 91 con almeno tre. Restano **124 profili** sotto l'obiettivo editoriale. Le altre rubriche sono invariate: 25 riti, 75 detti, 77 schede d'Archivio e 581 memorie.

Il piano complessivo resta aperto. Per mantenere l'alternanza fra rubriche, il prossimo focus torna a **Riti e credenze popolari**, senza usare contenuti generici come riempitivo e senza considerare chiusa la successiva ricerca comunale. Nessuna modifica a layout, backend, Android o webcam.

### Verifiche dell'undicesima passata

- Test mirati: **82 test su sette file superati**, compresi i tredici nuovi controlli del lotto. Verificati baseline, 430 ID unici, fonti e supporti individuali, decisione IT/FUR, rendering dei tre profili e assenza di contaminazioni fra Comuni.
- Suite frontend completa: **373 file, 2.510 test superati**, configurazione nativa e due worker (128 secondi).
- Lint completo e `git diff --check` superati. Build Web di produzione e service worker standalone superati in `C:\Users\LOCALU~1\AppData\Local\Temp\meteofriul-scopri-d9144ab6f47b4893ad444fda44fb678f`; avvisi sui chunk e sui tempi dei plugin già noti e non bloccanti.
- Seconda lettura assistita di manifest, runtime, fonti, testi e test: nessun problema concreto rilevato. Nessun commit, push, deploy o nuova prova fisica Android.

## Dodicesima passata — laguna e ciclo agricolo di luglio

Due nuove schede IT/FUR ampliano **Riti e credenze popolari** con pratiche diverse e una regola di calendario esatta. Entrambe compaiono soltanto nella domenica documentata; non diventano riempitivi quotidiani né annunci di eventi futuri.

### Perdòn di Barbana, prima domenica di luglio

Il [Consorzio Grado Turismo](https://grado.it/it/eventi-ed-escursioni/grandi-eventi/sabo-grando-e-perdon-di-barbana) indica esplicitamente la ricorrenza annuale, il corteo di barche da Grado a Barbana e la «Stella del Mare» che porta la statua della Madonna degli Angeli. [PromoTurismoFVG](https://www.turismofvg.it/it/mare/escursioni-in-barca-nella-costa-del-friuli-venezia-giulia/i-10-itinerari-in-barca-da-non-perdere/in-visita-al-santuario-di-barbana-nella-laguna-di-grado) conferma percorso, calendario e memoria del 1237; l'[Arcidiocesi di Gorizia](https://www.diocesigorizia.it/wd-interventi-vesc/ciascuno-di-noi-partecipa-a-disegnare-una-responsabilita-collettiva/) documenta il voto rinnovato dalla comunità.

La copy attribuisce l'origine del 1237 alla **tradizione**, senza presentarla come cronaca dimostrata. Non include il Sabo Grando, gli orari di una singola edizione o la distinta processione dei pescatori del primo maggio. La precedente `memory-draft-grado-perdon-barbana`, nascosta e priva di fonte istituzionale, resta intatta e non selezionabile; il manifest registra il recupero editoriale e il tema ha una sola scheda attiva.

### Trebbiatura a Cjase Cocèl, seconda domenica di luglio

La [Pro Loco Fagagna](https://www.prolocofagagna.it/festa-della-rebbiatura/) descrive la seconda domenica di luglio, il frumento portato sull'aia, la trebbia azionata dal trattore e la segale battuta a mano. Il [Museo Cjase Cocèl](https://www.museocjasecocel.it/) definisce la propria missione di conservazione e racconto del lavoro contadino; l'[elenco eventi del Comune di Fagagna](https://www.comune.fagagna.ud.it/it/vivere-il-comune-29554/eventi-29556) conferma il 12 luglio per l'edizione 2026, coerente con la regola ordinale.

La scheda parla sempre di **rievocazione museale**. Non afferma che la pratica agricola sia continuata senza interruzioni e non importa programma, orari o promesse di svolgimento. È distinta dai racconti sulla vendemmia, dalle Rogazioni e dalla tappa storica del museo.

### Tracciabilità e stato corrente

- `ritualResearchWave06.json` conserva fonti, supporti, calendari ordinali, deduplicazione e decisione editoriale. Resta fuori dalla UI e non duplica i testi IT/FUR del catalogo.
- Le regole sono `prima domenica di luglio` e `seconda domenica di luglio`; la simulazione 2026–2031 verifica ogni data concreta in entrambe le lingue.
- Il lessico FUR è stato letto direttamente in HTML ARLeF: fra gli altri `procession`, `corteu`, `barcje`, `vôt`, `batidure`, `forment` e `siale`. La revisione è assistita e limitata ai due ID; non equivale a certificazione ARLeF, revisione professionale indipendente o approvazione frase per frase dell'utente.
- I primi tredici record istituzionali restano identici: digest JSON `7aa488140d0b7bbf25a6432640a355646adec0facd2935ab05028d5759ae1e79`.

Il catalogo culturale passa da **102 a 104 schede**. La rubrica raggiunge **27 riti**, di cui **25 calendarizzabili** e due ancora esclusi perché dipendenti dal meteo. Nel 2028 mostra **20 riti diversi su 47 giorni**, due in più del lotto precedente; negli altri giorni resta assente. Comuni, 75 detti, 77 schede d'Archivio e 581 memorie non vengono ampliati in questa passata.

Il piano resta aperto. Il prossimo lotto torna a **Si diceva che…** per ampliare la varietà senza creare una seconda copia dei testi dell'Almanacco. Pignano di Ragogna e il pellegrinaggio da Forni Avoltri a Maria Luggau restano piste verificate per futuri riti; una regola di «ultimo fine settimana» non verrà approssimata con due date possibili.

### Verifiche della dodicesima passata

- Test mirati iniziali: **108 test su dodici file**, tutti superati. Ventitré nuovi controlli coprono integrità, fonti, bozza superata, calendario 2026–2031, rendering IT/FUR e limiti della copy.
- La prima suite completa ha individuato una modifica non necessaria alla bozza storica nascosta di Barbana. La bozza è stata ripristinata byte per byte e il test di integrità è rimasto attivo: il recupero editoriale è ora documentato soltanto nel manifest, mentre il vecchio record resta intatto e non selezionabile.
- Suite frontend completa finale: **374 file, 2.533 test superati**, configurazione nativa e due worker (138 secondi). Lint completo e `git diff --check` superati.
- Build Web di produzione, service worker standalone e controllo push superati in `C:\Users\LOCALU~1\AppData\Local\Temp\meteofriul-scopri-da38abbc44bc4cc08f7999a8d9971604`. Restano soltanto gli avvisi già noti su directory temporanea esterna, tempi dei plugin e dimensione del chunk principale, non bloccanti per questa passata.
- Nessun commit, push, deploy o prova fisica Android.

## Tredicesima passata — campi, usanze e saper fare

La rubrica **Si diceva che…** cresce riusando cinque testi che avevano già copy italiana e friulana approvata nell'Almanacco. Il catalogo autorevole non viene copiato o riscritto: `traditionalSayingAlmanacReuse.json` aggiunge soltanto i riferimenti necessari alla rotazione Scopri.

- **«Annata di nuvole, annata di pannocchie».** L'immagine agricola viene conservata come osservazione popolare storica, non come previsione o verità agronomica; non le viene inventato un mese.
- **«Altri tempi, altre usanze».** Il cambiamento nel tempo resta distinto dal detto già presente sulle usanze di ogni paese: non attribuisce superiorità al passato o al presente.
- **«Spazza davanti alla tua porta».** La responsabilità personale entra con un'immagine domestica, senza trasformarsi in un rimprovero rivolto all'utente.
- **«Meglio il pane guadagnato col sudore che una manciata di quello rubato».** È registrato come valore tradizionale del lavoro onesto, non come prescrizione sociale dell'app.
- **«Chi ha fatto la pentola sa fare anche il manico».** Pentola e manico introducono un'immagine concreta dell'abilità di mestiere, senza attribuirla a un artigiano o territorio non indicato dalla fonte.

La fonte bibliografica comune resta **Valentino Ostermann, _Proverbi friulani raccolti dalla viva voce del popolo_, 1876**, conservato dalle [Biblioteche Digjitâl Furlane / Teche Udine](https://www.techeudine.it/biblioteche-digital-furlane/proverbi-friulani-raccolti-dalla-viva-voce-del-popolo). Pagine, testi normalizzati e date delle approvazioni precedenti sono ereditati dai singoli record di `proverbs.json`.

### Selezione e integrità

- `traditionalSayingReuseWave04.json` documenta motivazione, pagina e decisione di riuso, ma non contiene una seconda copia IT/FUR e non è importato dalla UI.
- Nessuna nuova data, stagione, provenienza comunale, regola meteo o traduzione. Il lotto usa solo record `lab_ready` con revisione IT/FUR già approvata; la scelta di riuso resta assistita e non equivale a certificazione ARLeF, revisione professionale indipendente o approvazione frase per frase dell'utente.
- Invariati i 379 proverbi Almanacco, digest JSON `fc6d44d1636cc9c3eaa6aeb7e8fefcdba88cf35f4ba51173ef52dd15176169d6`, e le undici schede dedicate Scopri, digest `2815007a540341eb22de796fa0d2ecc156da9c764c0a5bf9d41c5a9e169c7f1a`. Conservati anche i 64 descrittori precedenti, digest `2b689e2d09b86dd8f383a99507069d74c541a836f5f2c7b760943a7ea2d10684`.
- Una preselezione di sei testi era valida sul piano editoriale, ma nel 2030 avrebbe lasciato inutilizzato un detto precedente. Il lotto finale resta quindi di cinque: nella simulazione 2026–2031 tutti i record compaiono almeno una volta ogni anno e nessuno si ripete per più di due giorni consecutivi.

La rubrica passa da **75 a 80 detti**: undici schede dedicate e 69 riusi dell'Almanacco. Restano otto ancoraggi esatti e la presenza copre tutti i 366 giorni del 2028 utilizzando l'intero repertorio. Almanacco, 430 tappe comunali, 27 riti, 77 schede d'Archivio e 581 memorie non cambiano in questa passata.

Il piano complessivo resta aperto. Il prossimo lotto torna ai **124 Comuni con una o due tappe**; restano inoltre da esplorare, con una scheda contestualizzata e senza attivazione automatica, i temi del mare e dell'orientamento popolare della Luna.

### Verifiche della tredicesima passata

- Test mirati iniziali: **94 test su otto file**, tutti superati. Coprono integrità, assenza di doppioni, fonte e pagina, riuso verbatim, rendering IT/FUR, calendario 2026–2031, precedenza delle regole precise e conteggi del backlog.
- Suite frontend completa finale: **375 file, 2.550 test superati**, configurazione nativa e due worker (197 secondi). Una prima invocazione npm aveva interpretato il valore dei worker come filtro e aveva eseguito soltanto 39 file: non è stata considerata verifica completa e la suite è stata rilanciata direttamente con il runner nativo.
- Lint completo, validazione JSON e `git diff --check` superati. Build Web di produzione, service worker standalone e controllo push superati in `C:\Users\LOCAL_USER\AppData\Local\Temp\meteofriul-scopri-wave04-20260901-1729a4c2`; restano soltanto gli avvisi già noti sulla directory temporanea esterna, sui tempi dei plugin e sul chunk principale, non bloccanti.
- Nessun commit, push, deploy o prova fisica Android.

## Quattordicesima passata — fortezza, Grande Guerra, botanica e mosaico

Quattro tappe documentate ampliano altrettanti profili senza forzarli tutti alla stessa quota. Palmanova, Medea e Spilimbergo passano da due a tre fatti; Sgonico, unico profilo triestino ancora fermo a una sola tappa, passa correttamente a due.

- **Palmanova, 1806.** Inizia la costruzione della terza cinta fortificata napoleonica. La [storia della fortezza del Comune](https://www.comune.palmanova.ud.it/it/territorio-2802/storia-della-fortezza-3654) documenta l'incarico dato a partire dal 1806 e le lunette aggiunte in asse ai baluardi veneziani. La tappa indica l'avvio dei lavori, non il completamento nello stesso anno, e resta distinta sia dalla fondazione del 1593 sia dal riconoscimento UNESCO del 2017.
- **Medea, 1915.** Le truppe italiane entrano nel territorio comunale il 24 maggio. La [cronologia del Comune](https://www.comune.medea.go.it/it/turismo-e-informazioni-7829/la-storia-17930) permette una formula neutra: ingresso militare, non annessione politica o «liberazione». L'episodio non duplica la distruzione medievale né l'Ara Pacis.
- **Sgonico, 1978.** Il Giardino botanico Carsiana apre al pubblico. La [storia ufficiale di Carsiana](https://giardinobotanicocarsiana.it/it/giardino/storia.html) separa chiaramente la fondazione del 1964, già presente, dal sostegno provinciale iniziato nel 1972 e dall'apertura del 1978. Non viene inventata una terza tappa solo per raggiungere una quota.
- **Spilimbergo, 1922.** Nasce la Scuola di mosaico. La [Scuola Mosaicisti del Friuli](https://scuolamosaicistifriuli.it/storia-e-attualita/) documenta la nascita a Spilimbergo nel 1922; la [storia comunale](https://www.comune.spilimbergo.pn.it/it/novita-202743/notizie-202745/la-citta-e-la-sua-storia-249660) conferma anno e iniziativa del Comune con la Società Umanitaria. La copy non aggiunge primati né presume una forma giuridica rimasta immutata.

### Tracciabilità e integrità

- I tre manifest `municipalityMilestone*ud-go-pn-ts-enrichment-04.json` separano ricerca, controllo FUR e promozione; non sono importati dalla UI. Le quattro tappe visibili sono integrate una sola volta in `municipalityProfiles.json` e conservano una fonte individuale.
- Il lessico FUR riusa modelli già approvati nei profili e viene confrontato con le voci HTML ARLeF per costruzione, truppe, apertura al pubblico, scuola e mosaico. È una revisione editoriale assistita, non una certificazione ARLeF, una revisione professionale indipendente o un'approvazione frase per frase attribuita all'utente.
- Rimuovendo soltanto i quattro nuovi ID, i 215 profili e le 430 tappe precedenti restituiscono il digest JSON `b80f4bdb80c97b5e7a8ea5ef260e7f7ab5c45e7c14e991968fbd1ca4f9775523`.

Il catalogo raggiunge **434 tappe per 215 Comuni**: 90 profili con una tappa, 31 con due e 94 con almeno tre. Restano **121 profili** sotto l'obiettivo editoriale. Le altre rubriche non cambiano: 27 riti, 80 detti, 77 schede d'Archivio e 581 memorie.

Il piano resta aperto e torna ora a **Riti e credenze popolari**, la seconda lacuna ad alta priorità, conservando l'alternanza fra rubriche. Nessuna modifica a layout, Almanacco, backend, Android o webcam.

### Verifiche della quattordicesima passata

- Tutti i **139 test comunali su sedici file** sono superati con configurazione Vite/Vitest nativa. Coprono baseline, ID unici, fonti, cautele, promozione, rendering IT/FUR e compatibilità con tutti i lotti precedenti.
- Suite frontend completa: **376 file, 2.565 test superati** con due worker (157 secondi). Lint completo e `git diff --check` superati.
- Build Web di produzione, service worker standalone e controllo push superati in `C:\Users\LOCAL_USER\AppData\Local\Temp\meteofriul-scopri-municipalities-20260901-1754`. Restano soltanto gli avvisi già noti sui tempi dei plugin e sulla dimensione del chunk principale, non bloccanti.
- Nessun commit, push, deploy o prova fisica Android.

## Quindicesima passata — Immacolata a Pignan e Femenàte di Paulâr

Due schede IT/FUR ampliano **Riti e credenze popolari** con pratiche invernali diverse e due date fisse documentate. Entrambe restano racconti culturali: non importano programmi correnti e non usano l'area del rito come posizione dell'utente.

### Processione dell'Immacolata a Pignan, 8 dicembre

L'[Arcidiocesi di Udine](https://www.diocesiudine.it/wd-appuntamenti/a-pignano-di-ragogna-da-111-anni-si-celebra-limmacolata/) documenta l'8 dicembre, la processione per le vie del borgo e la statua arrivata in chiesa nel 1904. Una [pubblicazione del 2024](https://www.diocesiudine.it/wd-appuntamenti/pignano-di-ragogna-in-festa-per-limmacolata-2/) registra la centoventesima edizione e conferma Vespri e processione; la [pagina del 2025](https://www.diocesiudine.it/wd-appuntamenti/pignano-celebra-limmacolata-con-la-processione/) conferma nuovamente data e gesto.

La regola viene dal corpo degli articoli, non dal widget del CMS, che nel 2024 mostra il 9 dicembre pur descrivendo «domenica 8». Non vengono conservati orari, nomi dei gruppi o un percorso invariabile: le fonti annuali alternano infatti `Borc di Sot` e `Borc di Sore`. **Pignan** e **Ruvigne** seguono la toponomastica friulana ufficiale. La scheda resta distinta dalla Memoria di Gemona dell'8 dicembre: quella racconta un incendio quattrocentesco, questa la tradizione locale legata alla statua del 1904.

### Femenàte di Paulâr, 5 gennaio

L'[Ecomuseo I Mistîrs](https://www.ecomuseomistirs.it/la-femenate/) descrive le strutture romboidali rivestite di materiali vegetali, l'accensione nelle borgate di Paularo il 5 gennaio e l'osservazione rituale di fumo e faville. Il [Museo Carnico delle arti popolari](https://patrimonio.museodolom.it/items/show/5755) conferma forma, calendario e lettura degli auspici per l'anno successivo; la [pagina degli eventi annuali dell'Ecomuseo](https://www.ecomuseomistirs.it/gli-eventi/) indica il 5 gennaio e una Femenàte per ogni borgata.

La copy non estende la pratica a tutti i fuochi epifanici, non presenta l'origine celtica come certezza e non trasforma i presagi in una previsione attendibile. Le cidulis di Cercivento hanno data, forma e gesto differenti; la scheda sui portatori di doni invernali non racconta i fuochi. `Femenàte` resta il nome tradizionale locale, mentre il corpo usa friulano standard assistito.

### Tracciabilità e stato corrente

- `ritualResearchWave07.json` conserva fonti, supporti, regole, deduplicazione e decisione editoriale. Resta fuori dalla UI e non contiene una seconda copia dei testi IT/FUR.
- I due record promossi compaiono soltanto il **5 gennaio** e l'**8 dicembre**. La simulazione 2026–2031 verifica data esatta, giorni adiacenti, rendering IT/FUR e indipendenza dalla località dell'utente.
- Il lessico FUR è stato letto direttamente in HTML ARLeF; `Pignan` viene dalla toponomastica ufficiale. La revisione è assistita e limitata ai due ID: non equivale a certificazione ARLeF, revisione professionale indipendente o approvazione dell'utente frase per frase.
- I primi quindici record istituzionali restano identici: digest JSON `09b7449604db932977e1c31436e238d58ce8476b0e87d024d66754141cb43ad6`.

Il catalogo culturale passa da **104 a 106 schede**. La rubrica raggiunge **29 riti**, di cui **27 calendarizzabili** e due dipendenti dal meteo. Nel 2028 vengono usati **22 riti diversi su 48 giorni**: Pignano aggiunge una giornata, mentre la Femenàte condivide il 5 gennaio con materiale già calendarizzato e prevale correttamente come data esatta. Restano invariati 434 tappe comunali, 80 detti, 77 schede d'Archivio e 581 memorie.

Il piano resta aperto. Il prossimo focus passa ad **Archivio e contesto meteorologico**, conservando la separazione tra racconti storici e dati meteo attuali. Per i riti restano piste future Porzûs, con l'esplicita cautela diocesana sulle apparizioni, e Forni Avoltri–Maria Luggau, senza approssimare la regola dell'ultimo fine settimana; Majenca resta sospesa per fonti calendariali discordanti.

### Verifiche della quindicesima passata

- Test mirati: **80 test su otto file superati**. Coprono baseline, unicità, fonti, manifest nascosto, deduplicazione, date 2026–2031, rendering IT/FUR, precedenza delle date esatte e conteggi del backlog.
- Suite frontend completa: **377 file, 2.582 test superati** con configurazione nativa e due worker (148 secondi).
- Lint completo, validazione di tutti i JSON Scopri e `git diff --check` superati.
- Build Web di produzione, service worker standalone e controllo push superati in `C:\Users\LOCAL_USER\AppData\Local\Temp\meteofriul-scopri-ritual-wave07-20260901-1836`. Restano soltanto gli avvisi già noti sui tempi dei plugin e sulla dimensione del chunk principale, non bloccanti.
- Nessun commit, push, deploy o prova fisica Android.

## Sedicesima passata — fax, alpeggio e ghiacciaie

Tre nuove schede IT/FUR ampliano **Archivio e tradizioni** senza collegare racconti storici al meteo corrente. Tutte entrano nella normale rotazione annuale: non introducono ricorrenze, trigger meteorologici, coordinate di visita o materiali multimediali di terzi.

### Le prime previsioni regionali diffuse via fax

[ARPA FVG](https://www.arpa.fvg.it/temi/temi/meteo-e-clima/ultimi-approfondimenti-pubblicati/losservatorio-meteorologico-regionale-di-arpa-fvg-evoluzione-dei-servizi-e-della-comunicazione-in-ambito-meteo-climatico/) documenta che il **25 giugno 1991** il Centro Meteorologico ERSA, predecessore dell'OSMER, produsse le prime previsioni regionali a due giorni. Le mappe ECMWF arrivavano via fax da Klagenfurt, venivano interpretate e disegnate a mano e il bollettino era inviato via fax agli utenti e al Gazzettino il lunedì, mercoledì e venerdì.

La copy mantiene la distinzione storica tra Centro Meteorologico ERSA e OSMER: non retrodata il nome dell'osservatorio attuale. Il 25 giugno resta nel racconto e non diventa un anniversario automatico. Non vengono riutilizzate mappe, bollettini o immagini della fonte.

### Alpeggio e scorta di fieno in Carnia

Il [Museo Carnico delle Arti Popolari](https://museocarnico.it/it/esplora/la-malga/alpeggio/) spiega che la distanza dai paesi e il breve periodo vegetativo favorivano l'uso comunitario della malga. Portare gli animali in alpeggio permetteva alle famiglie di accumulare più fieno per il lungo periodo dall'autunno alla primavera e lasciava tempo per la fienagione.

La scheda racconta un'organizzazione storica del lavoro e delle scorte in **Carnia**: non la attribuisce a un singolo paese, non descrive l'alpeggio contemporaneo e resta distinta dalle schede già dedicate ai campanacci e alla trasformazione del latte. Il testo è una sintesi originale, non una citazione estesa della pagina museale.

### Le ghiacciaie di pietra del Carso

La pagina 53 del [manuale del paesaggio culturale del Carso pubblicato dal Comune di Duino Aurisina](https://comune.duino-aurisina.ts.it/media/files/032001/attachment/Living_Landscape_Manuale_per_la_gestione_ed_il_recupero_del_paesaggio_cult..._Carso.pdf) descrive le ghiacciaie come strutture in pietra usate per produrre e conservare il ghiaccio fino all'arrivo dell'elettricità nelle abitazioni. I pochi esempi superstiti si trovano fuori dai centri, spesso su terreni privati, e non svolgono più la funzione originaria.

La copy non inventa coordinate, accessibilità o indicazioni di visita e non riusa fotografie o tavole del manuale. La tipologia carsica resta distinta dalla specifica galleria naturale usata anche come ghiacciaia già citata nella tappa comunale di Resiutta.

### Tracciabilità e stato corrente

- `archiveResearchWave05.json` conserva fonti, prove, cautele, deduplicazione e decisione editoriale; non è importato dalla UI e non contiene una seconda copia dei testi IT/FUR.
- I tre testi visibili sono promossi una sola volta in `institutionalArchive.json`. Il lessico FUR è stato controllato nelle pagine HTML ARLeF; la revisione resta editoriale assistita e non equivale a certificazione ARLeF, revisione professionale indipendente o approvazione dell'utente frase per frase.
- Rimuovendo i tre nuovi ID, i primi 26 record istituzionali restituiscono il digest JSON `3ed64fd1dc30322cd96d8805bceb75485760ecf1ed384d65de541b3179e64914`.
- Il manifest `weatherContextReview.json` non cambia: otto testi Ostermann restano reinterpretati soltanto in Scopri e diciotto contenuti restano esclusi. Nessun dato meteo attuale viene letto o dedotto per queste tre nuove schede.

Il catalogo culturale passa da **106 a 109 schede**. **Archivio e tradizioni** passa da **77 a 80 schede**: 64 calendarizzabili e 16 dipendenti dal meteo. Nel 2028 usa **62 schede diverse su 366 giorni**, con al massimo due giorni consecutivi per lo stesso contenuto e due ricorrenze esatte coperte dalla Memoria del giorno. Restano invariati 434 tappe comunali, 29 riti, 80 detti e 581 memorie.

Il piano resta aperto. Il prossimo focus torna alle **tappe storiche comunali**, mantenendo l'alternanza fra rubriche e senza forzare i 121 profili ancora fermi a una o due tappe.

### Verifiche della sedicesima passata

- Test mirati: **63 test su otto file superati**. Coprono baseline, unicità, fonti, manifest nascosto, deduplicazione, cautele della copy, rendering IT/FUR, rotazione 2028 e conteggi del backlog.
- Suite frontend completa: **378 file, 2.589 test superati** con configurazione Vite/Vitest nativa e due worker (150 secondi).
- Lint completo, validazione dei **237 JSON Scopri** e `git diff --check` superati.
- Build Web di produzione, service worker standalone e controllo push superati in `C:\Users\LOCALU~1\AppData\Local\Temp\meteofriul-scopri-archive-wave05-79846b4a83ef4ed7a29fc3e7e7845b74`. Restano soltanto gli avvisi già noti sulla directory temporanea esterna, sui tempi dei plugin e sulla dimensione del chunk principale, non bloccanti.
- Nessun commit, push, deploy o prova fisica Android.

## Diciassettesima passata — acque, scuola, nome e abbazia

Quattro tappe documentate portano a tre fatti i profili di Budoia, Fiume Veneto e Sesto al Reghena.

- **Budoia, 1670.** Le [autorità veneziane autorizzano le opere idrauliche a Dardago](https://turismo.comune.budoia.pn.it/contenuti/430923/storia). La tappa conserva il provvedimento e le opere documentate, ma non il primato regionale attribuito dalla stessa sintesi locale a un mulino.
- **Budoia, 1870.** [Apre la scuola femminile](https://turismo.comune.budoia.pn.it/contenuti/430923/storia). La fonte documenta apertura e numerose iscrizioni; la copy non deduce la piena parità del sistema scolastico.
- **Fiume Veneto, 1911.** Un [decreto reale aggiunge «Veneto» al nome Fiume](https://www.comune.fiumeveneto.pn.it/it/cultura-23021/la-storia-26125), su richiesta comunale per evitare soprattutto confusioni postali. È un cambio di nome, non la fondazione del Comune.
- **Sesto al Reghena, 899.** L'[invasione degli Ungheri distrugge quasi completamente l'abbazia](https://www.comune.sesto-al-reghena.pn.it/labbazia/). La distruzione resta limitata all'abbazia; la ricostruzione comincia soltanto fra il 960 e il 965.

### Tracciabilità e integrità

- `municipalityMilestoneResearch.pn-enrichment-02.json`, `municipalityMilestoneFurReview.pn-enrichment-02.json` e `municipalityMilestonePromotion.pn-enrichment-02.json` separano ricerca, revisione FUR e promozione e non sono importati dalla UI.
- Il lessico FUR è stato controllato nelle pagine HTML ARLeF. La revisione resta editoriale assistita, non una certificazione ARLeF o una revisione professionale indipendente.
- Rimuovendo soltanto i quattro nuovi ID, i 215 profili e le 434 tappe precedenti restituiscono il digest JSON `84cce150c8c1083b705777be59f684b3bf4730f9e47253751fd33360bb142033`.

Il catalogo raggiunge **438 tappe per 215 Comuni**: 89 profili con una tappa, 29 con due e 97 con almeno tre. Restano **118 profili** sotto l'obiettivo editoriale. Le altre rubriche restano invariate: 29 riti, 80 detti, 80 schede d'Archivio e 581 memorie.

Il prossimo focus torna a **Riti e credenze popolari**, conservando l'alternanza fra rubriche. Nessuna modifica a layout, backend, Android o webcam.

### Verifiche della diciassettesima passata

- Test mirati: **99 test su otto file superati**. Coprono baseline storiche, unicità, fonti, manifest nascosti, deduplicazione, cautele della copy, rendering IT/FUR e conteggi del backlog.
- Suite frontend completa: **379 file, 2.602 test superati** con configurazione Vite/Vitest nativa e due worker (133 secondi).
- Lint completo, validazione dei **240 JSON Scopri** e `git diff --check` superati.
- Build Web di produzione, service worker standalone e controllo push superati in `C:\Users\LOCAL_USER\AppData\Local\Temp\meteofriul-scopri-municipality-pn02-20260901-1935`. Restano soltanto gli avvisi già noti sulla directory temporanea esterna, sui tempi dei plugin e sulla dimensione del chunk principale, non bloccanti.
- Nessun commit, push, deploy o prova fisica Android.

## Diciottesima passata — Dobradan, župa e Grotta Gigante

Tre tappe documentate portano a tre fatti i profili di Doberdò del Lago e Sgonico, continuando il lavoro comunale senza alternarlo con le altre rubriche.

- **Doberdò del Lago, 1179.** La [storia pubblicata dal Comune](https://www.comune.doberdo.go.it/it/vivere-il-comune-96560/luoghi-96561/storia-156637) documenta la prima menzione della località con il nome `Dobradan`. La tappa non trasforma la menzione nella nascita del Comune e non deduce un'etimologia.
- **Doberdò del Lago, 1524.** La stessa fonte registra la prima testimonianza scritta di una comunità istituzionalizzata, indicata come `župa`. Il termine storico resta invariato e non viene tradotto come Comune, municipalità o amministrazione moderna.
- **Sgonico, 1908.** Il [Catasto Speleologico Regionale FVG](https://catastogrotte.regione.fvg.it/scheda/2-Grotta_Gigante) localizza la Grotta Gigante nel Comune di Sgonico e ne data l'apertura turistica al **5 luglio 1908**. Il [gestore diretto](https://www.grottagigante.it/la-scoperta/) documenta i lavori iniziati nel 1905 e il percorso realizzato in circa tre anni. La copy non attribuisce l'iniziativa al Comune.

### Tracciabilità e integrità

- `municipalityMilestoneResearch.go-ts-enrichment-01.json`, `municipalityMilestoneFurReview.go-ts-enrichment-01.json` e `municipalityMilestonePromotion.go-ts-enrichment-01.json` separano ricerca, revisione FUR e promozione e non sono importati dalla UI.
- `Dobradan`, `župa` e `Grotta Gigante` restano nomi propri o termini storici invariati. Il lessico FUR è stato controllato nelle pagine HTML ARLeF; la revisione resta editoriale assistita e non equivale a certificazione ARLeF o revisione professionale indipendente.
- Rimuovendo soltanto i tre nuovi ID, i 215 profili e le 438 tappe precedenti restituiscono il digest JSON `818e4fe36717dc597781aa2806ba3a8457b5022bce0aafaa6c2654e7f493e8be`.

Il catalogo raggiunge **441 tappe per 215 Comuni**: 88 profili con una tappa, 28 con due e 99 con almeno tre. Restano **116 profili** sotto l'obiettivo editoriale. Le altre rubriche restano invariate: 29 riti, 80 detti, 80 schede d'Archivio e 581 memorie.

Il prossimo focus resta sulle **tappe storiche comunali**. Il registro abbandona temporaneamente l'alternanza fra rubriche, come deciso dopo la diciassettesima passata; le altre lacune restano documentate ma non interrompono i lotti comunali.

### Verifiche della diciottesima passata

- Test mirati: **110 test su nove file superati**. Coprono baseline storiche, unicità, fonti, data completa della Grotta Gigante, manifest nascosti, deduplicazione, cautele della copy, rendering IT/FUR e conteggi del backlog.
- Suite frontend completa: **380 file, 2.613 test superati** con configurazione Vite/Vitest nativa e due worker (149 secondi).
- Lint completo, validazione dei **243 JSON Scopri** e `git diff --check` superati.
- Build Web di produzione, service worker standalone e controllo push superati in `C:\Users\LOCAL_USER\AppData\Local\Temp\meteofriul-scopri-municipality-gots01-20260901-2020`. Restano soltanto gli avvisi già noti sulla directory temporanea esterna, sui tempi dei plugin e sulla dimensione del chunk principale, non bloccanti.
- Nessun commit, push, deploy o prova fisica Android.

## Diciannovesima passata — Consorzio, DOP e autonomia comunale

Quattro tappe documentate portano da uno a tre fatti i profili di San Daniele del Friuli e Staranzano. Il lavoro resta concentrato sui Comuni e non modifica le altre rubriche.

- **San Daniele del Friuli, 1961.** Viene istituito il Consorzio del Prosciutto di San Daniele. La [storia pubblicata dal Consorzio](https://prosciuttosandaniele.it/il-consorzio/il-consorzio/) data al 1961 l'istituzione dell'ente; la tappa non presenta quell'anno come nascita del prosciutto e non riprende il primato promozionale di «primo consorzio di salumi in Italia» senza un riscontro indipendente.
- **San Daniele del Friuli, 1996.** L'Unione europea riconosce il Prosciutto di San Daniele come DOP. La stessa fonte documenta il passaggio europeo. Il riconoscimento italiano come Denominazione di Origine del 1970 è verificato e conservato nel manifest, ma non promosso per evitare due riconoscimenti consecutivi nella stessa timeline.
- **Staranzano, 1848.** Staranzano diventa Comune anche sul piano amministrativo. La [storia pubblicata dal Comune](https://www.comune.staranzano.go.it/it/novita-76815/notizie-76816/staranzano-storia-e-territorio-del-paese-82839), sostenuta dal [PAESC comunale](https://www.comune.staranzano.go.it/media/files/md/031023/03594_PAESC_STARANZANO_DEFINITIVO-SIGNED.PDF), distingue questo riconoscimento dalla nascita del Comune collocata nell'intervallo 1817–1820; non viene quindi inventata una data puntuale nel 1817.
- **Staranzano, 1907.** Staranzano si separa definitivamente da Monfalcone e riacquista l'autonomia comunale mediante decreto dell'imperatore Francesco Giuseppe. La tappa non data al 1867 l'aggregazione: la fonte attribuisce a quell'anno soltanto la richiesta, senza esplicitare nella stessa frase la data dell'atto che la accolse.

### Tracciabilità e integrità

- `municipalityMilestoneResearch.ud-go-enrichment-02.json`, `municipalityMilestoneFurReview.ud-go-enrichment-02.json` e `municipalityMilestonePromotion.ud-go-enrichment-02.json` separano ricerca, revisione FUR e promozione e non sono importati dalla UI.
- Il nome legale `Consorzio del Prosciutto di San Daniele`, la denominazione protetta `Prosciutto di San Daniele` e la sigla `DOP` restano invariati. Il lessico FUR è stato confrontato con le pagine HTML ARLeF; la revisione resta editoriale assistita e non equivale a certificazione ARLeF, revisione professionale indipendente o approvazione frase per frase attribuita all'utente.
- Rimuovendo soltanto i quattro nuovi ID, i 215 profili e le 441 tappe precedenti restituiscono il digest JSON `1820d7ffa63714130f5c573ba162a9a7c8b33e55683412c596e2412a810b1909`.

Il catalogo raggiunge **445 tappe per 215 Comuni**: 86 profili con una tappa, 28 con due e 101 con almeno tre. Restano **114 profili** sotto l'obiettivo editoriale. Le altre rubriche restano invariate: 29 riti, 80 detti, 80 schede d'Archivio e 581 memorie.

Il prossimo focus resta sulle **tappe storiche comunali**. Nessuna modifica a layout, Almanacco, backend, Android o webcam.

### Verifiche della diciannovesima passata

- Test mirati: **118 test su nove file superati**. Coprono baseline storiche, unicità, fonti, manifest nascosti, cautele della copy, revisione FUR assistita, rendering IT/FUR e conteggi del backlog.
- Suite frontend completa: **381 file, 2.624 test superati** con configurazione Vite/Vitest nativa e quattro worker (66 secondi).
- Lint completo, validazione dei **246 JSON Scopri** e `git diff --check` superati.
- Build Web di produzione, service worker standalone e controllo push superati in `C:\Users\LOCAL_USER\AppData\Local\Temp\meteofriul-scopri-udgo02-20260901-2054`. Restano soltanto gli avvisi già noti sulla directory temporanea esterna, sui tempi dei plugin e sulla dimensione del chunk principale, non bloccanti.
- Nessun commit, push, deploy o prova fisica Android.

## Ventesima passata — Fiera, sede patriarcale e assetto napoleonico

Sei tappe documentate portano da uno a tre fatti i profili di Aiello del Friuli, Cividale del Friuli e San Quirino. Il lavoro resta concentrato sui Comuni e non modifica le altre rubriche.

- **Aiello del Friuli, 1816.** Viene istituita la Fiera di San Carlo. La [scheda pubblicata dal Comune](https://www.comune.aiellodelfriuli.ud.it/media/files/030001/attachment/Fiera_San_Carlo.pdf) attribuisce l'istituzione a Francesco I d'Austria. La tappa non chiama San Carlo patrono del paese e non afferma una continuità annuale ininterrotta.
- **Aiello del Friuli, 1931.** Il Comune di Joannis viene soppresso e aggregato ad Aiello. Il [censimento ISTAT](https://lipari.istat.it/digibib/Censimenti%20popolazione/censpop1931/VolumeIIIFascicoliProvinciali/IST0005870Fasc26_UDINE%2BOCRottimizz.pdf) collega l'atto al regio decreto 18 maggio 1931 n. 648; la copy conserva il corretto status amministrativo di Joannis.
- **Cividale del Friuli, 737.** Il patriarca Callisto trasferisce la propria sede a Cividale. La [relazione illustrativa comunale](https://comune.cividale-del-friuli.ud.it/media/files/md/030026/Elab.07_Relazione_illustrativa.pdf), sostenuta da materiale didattico dello stesso Comune, documenta il passaggio senza farlo partire arbitrariamente da Aquileia.
- **Cividale del Friuli, 1817.** Viene fondato il Museo archeologico di Cividale. Il [Ministero della Cultura](https://cultura.gov.it/luogo/museo-archeologico-nazionale-di-cividale-del-friuli) data la fondazione al 1817; l'attuale qualifica di Museo nazionale non viene retrodatata nella tappa.
- **San Quirino, 1499.** L'incursione turca incendia San Quirino e la sua chiesa. [SIUSA](https://siusa-archivi.cultura.gov.it/cgi-bin/siusa/pagina.pl?Chiave=6979&RicDimF=2&TipoPag=prodente) documenta il fatto il 30 settembre; la copy non aggiunge vittime né distruzione totale.
- **San Quirino, 1807.** San Quirino entra nel Distretto di Pordenone del Regno d'Italia napoleonico. La [scheda archivistica del Comune](https://siusa-archivi.cultura.gov.it/cgi-bin/siusa/pagina.pl?Chiave=9327&TipoPag=prodente) documenta l'inquadramento; la tappa non lo trasforma nella fondazione della comunità.

### Tracciabilità e integrità

- `municipalityMilestoneResearch.ud-pn-enrichment-05.json`, `municipalityMilestoneFurReview.ud-pn-enrichment-05.json` e `municipalityMilestonePromotion.ud-pn-enrichment-05.json` separano ricerca, revisione FUR e promozione e non sono importati dalla UI.
- Le fonti comunali, ISTAT, Ministero della Cultura e SIUSA restano associate alla singola tappa. Il lessico e i toponimi FUR sono stati controllati nelle risorse ufficiali ARLeF; la revisione resta editoriale assistita e non equivale a certificazione ARLeF o revisione professionale indipendente.
- Rimuovendo soltanto i sei nuovi ID, i 215 profili e le 445 tappe precedenti restituiscono il digest JSON `1350f4d09311ba0a5ae70a917a24658903030c124a1dbb980f61871838c61673`.

Il catalogo raggiunge **451 tappe per 215 Comuni**: 83 profili con una tappa, 28 con due e 104 con almeno tre. Restano **111 profili** sotto l'obiettivo editoriale. Le altre rubriche restano invariate: 29 riti, 80 detti, 80 schede d'Archivio e 581 memorie.

Il prossimo focus resta sulle **tappe storiche comunali**. Nessuna modifica a layout, Almanacco, backend, Android o webcam.

### Verifiche della ventesima passata

- Test mirati: **132 test su dieci file superati**. Coprono il nuovo lotto, tutte le baseline comunali storiche, ID unici, fonti, date complete, cautele della copy, revisione FUR assistita, rendering IT/FUR e conteggi del backlog.
- Suite frontend completa: **382 file, 2.638 test superati** con configurazione Vite/Vitest nativa e quattro worker (81 secondi).
- Lint completo, validazione dei **249 JSON Scopri** e `git diff --check` superati.
- Build Web di produzione, service worker standalone e controllo push superati in `C:\Users\LOCAL_USER\AppData\Local\Temp\meteofriul-scopri-udpn05-20260901-2128`. Restano soltanto gli avvisi già noti sulla directory temporanea esterna, sui tempi dei plugin e sulla dimensione del chunk principale, non bloccanti.
- Nessun commit, push, deploy o prova fisica Android.

## Ventunesima passata — Bagni di Lignano, Torre Picotta e scavi del Foro

Tre tappe documentate portano da due a tre fatti i profili di Lignano Sabbiadoro, Tolmezzo e Zuglio. Il lavoro resta concentrato sui Comuni e non modifica le altre rubriche.

- **Lignano Sabbiadoro, 1903.** Viene costruito il primo stabilimento balneare di Lignano. La [relazione del PRGC comunale](https://comune.lignano-sabbiadoro.ud.it/amministrazione/documenti-e-dati/amministrazione-trasparente/pianificazione-e-governo-del-territorio/varianti-al-prgc-1/variante-n-66-trasposizione-dello-strumento-urbanistico-su-nuovo-supporto-cartografico/relazione.pdf/@@download/file_principale) documenta la costruzione nel 1903 e la [pagina comunale per i 120 anni](https://comune.lignano-sabbiadoro.ud.it/argomenti/turismo/120-anni) collega al 15 aprile il momento fondativo dei Bagni di Lignano. La copy non afferma che lo stabilimento apra nello stesso anno, perché un'altra cronologia comunale colloca l'apertura nel 1904, e non confonde l'avvio della località balneare con l'autonomia comunale del 1959.
- **Tolmezzo, 1477–1479.** Viene costruita la Torre Picotta a difesa del borgo e del castello. La [storia pubblicata dal Comune](https://www.comune.tolmezzo.ud.it/localita-di-tolmezzo/) conserva l'intero intervallo e documenta la funzione difensiva di fronte alla minaccia turca; la tappa non sceglie arbitrariamente il 1477 come anno di completamento e non inventa una battaglia respinta dalla torre.
- **Zuglio, inizio XIX secolo.** Iniziano i primi scavi sistematici nel Foro di Iulium Carnicum. La [scheda ERPAC FVG](https://patrimonioculturale.regione.fvg.it/museo/?s_id=440628), sostenuta dalla [cronologia comunale](https://www.comune.zuglio.ud.it/it/home-2611/cultura-2614/la-storia-6506), colloca all'inizio dell'Ottocento le prime indagini regolari nel Foro. La tappa non inventa l'anno 1800 e non estende il primato a ogni rinvenimento archeologico precedente nell'intero territorio.

### Tracciabilità e integrità

- `municipalityMilestoneResearch.ud-enrichment-06.json`, `municipalityMilestoneFurReview.ud-enrichment-06.json` e `municipalityMilestonePromotion.ud-enrichment-06.json` separano ricerca, revisione FUR e promozione e non sono importati dalla UI.
- Il lessico e la grafia FUR sono stati confrontati con le pagine HTML ARLeF. La revisione resta editoriale assistita e non equivale a certificazione ARLeF, revisione professionale indipendente o approvazione frase per frase attribuita all'utente.
- Rimuovendo soltanto i tre nuovi ID, i 215 profili e le 451 tappe precedenti restituiscono il digest JSON `11a48c4a9b678c363647d2fd191eca113d5f6d255aa2b5f26ef34beaacb6fd27`.

Il catalogo raggiunge **454 tappe per 215 Comuni**: 83 profili con una tappa, 25 con due e 107 con almeno tre. Restano **108 profili** sotto l'obiettivo editoriale. Le altre rubriche restano invariate: 29 riti, 80 detti, 80 schede d'Archivio e 581 memorie.

Il prossimo focus resta sulle **tappe storiche comunali**. Nessuna modifica a layout, Almanacco, backend, Android o webcam.

### Verifiche della ventunesima passata

- Test mirati: **135 test su dieci file superati**. Coprono il nuovo lotto, le baseline comunali interessate, ID unici, fonti, periodi non puntuali, cautele della copy, revisione FUR assistita, rendering IT/FUR e conteggi del backlog.
- Lint completo, validazione dei **252 JSON Scopri** e `git diff --check` superati.
- La suite frontend completa, la build Web e il service worker già verificati nella ventesima passata non sono stati ripetuti, come richiesto.
- Nessun commit, push, deploy o prova fisica Android.

## Ventiduesima passata — Mura di Venzone, incursione di Polcenigo e vino a Canale Anfora

Tre tappe documentate portano da due a tre fatti i profili di Venzone, Polcenigo e Terzo d'Aquileia. Il lavoro resta concentrato sui Comuni e non modifica le altre rubriche.

- **Venzone, 1258.** Inizia la costruzione della doppia cinta muraria. La [scheda ERPAC FVG del circuito difensivo](https://patrimonioculturale.regione.fvg.it/architettura/?s_id=446567), sostenuta dal [percorso tematico regionale](https://patrimonioculturale.regione.fvg.it/percorso-tematico/?s_id=875161), documenta l'avvio del cantiere da parte di Glizoio di Mels. La tappa non trasforma il 1258 nella data di completamento e non presenta le strutture odierne come integralmente originali.
- **Polcenigo, 1499.** L'incursione turca devasta Polcenigo. La [pagina comunale del castello](https://www.comune.polcenigo.pn.it/it/vivere-il-comune-273915/luoghi-273916/castello-di-polcenigo-289700) e la [guida storico-naturalistica comunale](https://www.comune.polcenigo.pn.it/media/files/md/093031/COMUNE_DI_POLCENIGO_Op_Scrignoverde.pdf) documentano il borgo ridotto in macerie. La copy non aggiunge la distruzione definitiva del castello o l'abbandono permanente del paese.
- **Terzo d'Aquileia, XIV–XIII secolo a.C.** Nell'abitato di Canale Anfora è documentato il consumo di vino. Il [piano comunale dell'illuminazione](https://comune.terzodiaquileia.ud.it/media/files/md/030120/Piano_Comunale_di_illuminazione_web_1.pdf), con il riscontro dell'[Università di Udine](https://qui.uniud.it/ricerca-e-innovazione/3000-anni-fa-in-friuli-venezia-giulia-si-consumava-vino/), associa residui di vino a una coppa presso un focolare. La tappa non deduce produzione locale, coltivazione della vite o un primato nazionale.

### Tracciabilità e integrità

- `municipalityMilestoneResearch.ud-pn-enrichment-07.json`, `municipalityMilestoneFurReview.ud-pn-enrichment-07.json` e `municipalityMilestonePromotion.ud-pn-enrichment-07.json` separano ricerca, revisione FUR e promozione e non sono importati dalla UI.
- Il lessico, la grafia e i toponimi FUR sono stati confrontati con le pagine HTML ARLeF. La revisione resta editoriale assistita e non equivale a certificazione ARLeF, revisione professionale indipendente o approvazione frase per frase attribuita all'utente.
- Rimuovendo soltanto i tre nuovi ID, i 215 profili e le 454 tappe precedenti restituiscono il digest JSON `be46c7f278861894c09dc2aed123eb1650cdc1527e402a300475742e03ae9ce2`.

Il catalogo raggiunge **457 tappe per 215 Comuni**: 83 profili con una tappa, 22 con due e 110 con almeno tre. Restano **105 profili** sotto l'obiettivo editoriale. Le altre rubriche restano invariate: 29 riti, 80 detti, 80 schede d'Archivio e 581 memorie.

Il prossimo focus resta sulle **tappe storiche comunali**. Nessuna modifica a layout, Almanacco, backend, Android o webcam.

### Verifiche della ventiduesima passata

- Test mirati: **160 test su dodici file superati**. Coprono il nuovo lotto, tutte le baseline comunali storiche interessate, ID unici, fonti, intervallo protostorico, cautele della copy, revisione FUR assistita, rendering IT/FUR e conteggi del backlog.
- Lint completo, validazione dei **255 JSON Scopri** e `git diff --check` superati.
- La suite frontend completa, la build Web e il service worker già verificati nella ventesima passata non sono stati ripetuti, come richiesto.
- Nessun commit, push, deploy o prova fisica Android.

## Ventitreesima passata — Academiuta, museo archeologico e Pordenone

Il lotto `pn-enrichment-milestones-08` aggiunge una tappa a Casarsa della Delizia, Montereale Valcellina e Pinzano al Tagliamento: ciascun profilo raggiunge tre fatti. Il focus resta sui Comuni, senza alternare le altre rubriche.

- Casarsa: fondazione dell'Academiuta a Versuta, 1945; [fonte SFF / Centro Studi Pasolini](https://www.pasolinibibliografiafriulana.it/opere/academiuta-di-lenga-furlana_2728).
- Montereale: inaugurazione del Museo archeologico, 2011; [Forum Iulii XXXV, p. 234](https://museoarcheologicocividale.beniculturali.it/wp-content/uploads/2021/03/Forum-Iulii-XXXV-Notiziari.compressed.pdf), con riscontro della sede in [ERPAC](https://patrimonioculturale.regione.fvg.it/museo/?s_id=440633).
- Pinzano: Madonna col Bambino del Pordenone in San Martino, 1525; [PromoTurismoFVG](https://www.turismofvg.it/it/71917/chiesa-di-san-martino-vescovo).

### Tracciabilità e integrità

I manifesti `municipalityMilestoneResearch.pn-enrichment-08.json`, `municipalityMilestoneFurReview.pn-enrichment-08.json` e `municipalityMilestonePromotion.pn-enrichment-08.json` separano ricerca, revisione e promozione. Le cautele sulle date, sulle istituzioni omonime e sulle attribuzioni restano documentate nella ricerca.

Il confronto con ARLeF è una revisione editoriale assistita: non certificazione linguistica, revisione professionale indipendente o approvazione frase per frase dell'utente. I dati preesistenti restano intatti: escludendo soltanto i tre nuovi ID, il digest dei 215 profili con 457 tappe è `cebb815e05b109e2963580bd214549c737e805b087d514ed2ec3cab7ee0ad0cf`.

Il catalogo raggiunge **460 tappe per 215 Comuni**: 83 profili con una tappa, 19 con due e 113 con almeno tre; **102** ancora sotto soglia. Restano invariati 29 riti, 80 detti, 80 schede d'Archivio e 581 memorie. Nessuna modifica a layout, Almanacco, backend, Android o webcam.

### Verifiche della ventitreesima passata

- Test mirati: **174 test su tredici file superati**, inclusi baseline storiche, unicità, fonti, date, cautele della copy, revisione FUR, rendering IT/FUR e backlog.
- Lint completo, validazione dei **258 JSON Scopri** e `git diff --check` superati. I tre nuovi manifesti di ricerca, revisione e promozione non sono importati dal codice runtime.
- Suite frontend completa, build Web e service worker già verificati non ripetuti, come richiesto.
- Nessun commit, push, deploy o prova fisica Android.

## Ventiquattresima passata — Prampero, Taipana e Cavalicco

Il lotto `ud-enrichment-milestones-09` aggiunge una tappa a Magnano in Riviera, Taipana e Tavagnacco: ciascun profilo raggiunge tre fatti. Il focus editoriale resta sui Comuni.

- Magnano: menzione documentaria del Castello di Prampero, 1107; [Consorzio Castelli FVG, Castelli n. 107, p. 2](https://consorziocastelli.it/biblioteca/pubblicazioni/notiziario/anno-2006/107.pdf). Non è una data di fondazione e non riabilita le cronologie discordanti escluse nel lotto UD zero 03.
- Taipana: autorizzazione al cambio di nome del Comune di Platischis, 1931; [Regio decreto n. 1382/1931](https://www.gazzettaufficiale.it/eli/id/1931/11/21/031U1382/sg). Si distinguono decreto, pubblicazione ed entrata in vigore; la tappa conserva solo l'anno.
- Tavagnacco: Madonna in trono di Pietro Fuluto a Cavalicco, 1512; [Comune](https://agenda.comune.tavagnacco.ud.it/Luoghi/Chiesa-antica-di-Cavalicco) e [Istituto Pio Paschini](https://www.dizionariobiograficodeifriulani.it/fuluto-pietro/). L'attribuzione resta limitata all'opera, senza estenderla agli altri affreschi.

### Tracciabilità e integrità

I tre manifesti `municipalityMilestone*ud-enrichment-09.json` separano ricerca, revisione FUR e promozione. La revisione assistita usa i lemmi ARLeF e non equivale a certificazione o revisione professionale indipendente.

Rimuovendo soltanto i tre nuovi ID, i 215 profili e le 460 tappe della baseline restituiscono il digest JSON `a41337b65f04e44330f441b842fd7ba4600f893f3d833941b40ac32ab9ef8223`. Il lotto PN 08 non committato resta intatto.

Il catalogo raggiunge **463 tappe per 215 Comuni**: 83 profili con una tappa, 16 con due e 116 con almeno tre; **99** ancora sotto soglia. Restano invariati 29 riti, 80 detti, 80 schede d'Archivio e 581 memorie.

### Verifiche della ventiquattresima passata

- **194 test mirati su quindici file superati**, incluse baseline storiche, fonti, cautele cronologiche, revisione FUR, rendering IT/FUR e backlog.
- Lint completo, validazione dei **261 JSON Scopri** e `git diff --check` superati. I tre nuovi manifesti non sono importati dal codice runtime.
- Suite frontend completa, build Web e service worker già verificati non ripetuti, come richiesto.
- Nessun commit, push o deploy. La successiva modifica alle fonti della hero, richiesta separatamente dall'utente, non fa parte del lotto editoriale.

## Ripresa del 6 settembre 2026 — qualità delle fonti, lotto UD 10

Primo passaggio di ricerca, **non promozione nel runtime**. Il catalogo resta a 215 profili, 463 tappe e 99 profili sotto tre tappe. Nessuna nuova rubrica, modifica grafica o traduzione pubblicata.

Il manifesto `municipalitySourceReview.ud-quality-10.json` registra due fonti istituzionali lette nell'HTML completo: Regione FVG per l'eccidio di Avasinis del 1945 e Vigili del Fuoco per le distruzioni del 1976 a Trasaghis. Confermano le due tappe esistenti, oggi ancora prive di fonte propria e appoggiate alla fonte generale Wikipedia. Non si estende questa verifica all'intero riassunto del profilo; i testi IT/FUR restano invariati e non ricevono una nuova certificazione linguistica.

Per Moimacco è conservata una candidata relativa all'attestazione del 1192: l'estratto SIUSA è stato trovato, ma la pagina completa non è stata letta. La candidata resta esclusa dalla UI, con FUR nullo e revisione pendente. Non interpretare l'attestazione come fondazione.

Prossimo passo: integrare le due fonti puntuali preservando la tracciabilità dei test di baseline; poi completare la verifica SIUSA e la revisione assistita FUR prima di promuovere Moimacco. Le impronte storiche del catalogo non sono state riscritte. Il test Node dedicato controlla separazione ricerca/runtime, corrispondenza delle tappe, conteggi e mancata promozione della candidata. Nessun download privato, contatto esterno, commit o deploy.

### Integrazione e pausa editoriale del 6 settembre

Le due citazioni di Trasaghis sono ora esposte dal modello IT/FUR tramite `municipalityMilestoneSources.json`: la fonte puntuale già presente in una tappa conserva precedenza, poi si consulta il registro verificato e infine la fonte generale del profilo. Il manifesto di ricerca resta storico e non viene importato nel runtime. Testi, catalogo e impronte delle baseline restano invariati.

La lettura diretta SIUSA di Moimacco è stata ritentata e termina in timeout: nessuna promozione, nessuna traduzione FUR inventata. L'editoriale viene lasciato a questo checkpoint per riprendere il lato progettuale, come richiesto. Nessuna modifica a meteo, monetizzazione, eventi, webcam o Android.
