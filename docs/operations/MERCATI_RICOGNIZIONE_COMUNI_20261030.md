# Mercati: ricognizione dei comuni e manutenzione dal pannello

**Seguito del 30 ottobre:** completata la [revisione approfondita dei 192 casi](MERCATI_REVISIONE_192_20261030.md), con decisione, riconciliazione e azione amministrativa per ciascuno. Il presente documento e il suo JSON conservano lo stato della prima ricognizione; i conteggi delle priorità qui sotto sono quelli iniziali.

Aggiornamento del **30 ottobre 2026**, ramo `codex/mercati-integration-20261028`,
base di ricerca `425369ea`. Segue il [primo dossier di fonti del 30 ottobre](MERCATI_FONTI_CATALOGAZIONE_20261030.md)
e la [ricerca dei 74 candidati del 29 ottobre](MERCATI_COPERTURA_RICERCA_20261029.md).

**Tutti i 215 comuni hanno ora una prima ricognizione registrata. Non significa
che siano stati accertati tutti i mercati né che ogni comune ne abbia uno.**
In 115 comuni è stata approfondita almeno una pista; gli altri 100 restano al
primo esame. Nessun comune viene dichiarato privo di mercati sulla base di
ricerche senza risultati.

Il [registro strutturato](evidence/MERCATI_RICOGNIZIONE_COMUNI_20261030.json)
conserva per ogni comune codice ISTAT, ricerche, fonti, candidature, limiti,
collegamenti pregressi e prossima azione. È documentazione di ricerca, non un
file da importare nell'app. La [proposta per il pannello](MERCATI_GESTIONE_PANNELLO_CONTRATTO_20261030.md)
traduce i casi trovati in operazioni di gestione da realizzare.

## Copertura e significato dei numeri

| Territorio | Comuni | Almeno una pista approfondita | Primo esame |
|---|---:|---:|---:|
| Udine | 134 | 66 | 68 |
| Pordenone | 50 | 36 | 14 |
| Gorizia | 25 | 10 | 15 |
| Trieste | 6 | 3 | 3 |
| **Totale** | **215** | **115** | **100** |

L'anagrafica deriva da [fvg_municipalities.json](../../backend/app/data/fvg_municipalities.json),
la cui provenienza dichiara codici ISTAT al 21/02/2026. La [pagina generale
regionale](https://autonomielocali.regione.fvg.it/aall/opencms/AALL/Informazioni_generali/)
corrobora il totale di 215 comuni; non è un censimento dei mercati e le sue
informazioni demografiche hanno una propria data. Non sono state copiate
coordinate personali o recapiti privati nel registro.

| Misura del lotto territoriale | Quantità |
|---|---:|
| Stringhe di ricerca distinte registrate | 522 |
| Fonti catalogate, URL distinti | 182 |
| Fonti con passaggio pertinente letto | 139 |
| Fonti accessibili soltanto tramite estratto indicizzato | 38 |
| Fonti non acquisite, tentativo documentato | 5 |
| Schede di candidatura o riconciliazione | 192 |
| Pronte alla revisione | 25 |
| Da confermare | 96 |
| Con conflitti | 6 |
| Soltanto storiche | 65 |
| Assenze comunali confermate | **0** |

Le 522 stringhe documentano le ricerche assegnate ai comuni, almeno due per
comune; non sono un contatore delle chiamate al motore né una prova che siano
state esaurite tutte le frazioni, categorie e pagine social. «Approfondito»
riguarda almeno una pista letta, anche se storica o poi rivelatasi insufficiente.

Le **192 candidature non sono 192 nuovi mercati attivi**: comprendono identità
note, riconciliazioni, mercati di frazione, testimonianze passate e progetti.
«Pronto alla revisione» non equivale a pubblicato; può mancare un orario o può
trattarsi di un'edizione già trascorsa. Anche gli URL già incontrati nei lotti
precedenti sono conservati: non sommare 182 alle 51 fonti del primo dossier
come se fossero tutte nuove.

Gli esiti per comune sono 43 con riscontri da esaminare, anche pregressi,
96 con elementi storici/incerti e 76 senza riscontro primario pertinente
acquisito in questa ricerca. L'ultimo gruppo è una coda di verifica, **non un
elenco di comuni senza mercato**. Sono collegati tutti i 74 candidati iniziali,
le 44 schede del primo approfondimento e le 60 schede applicative, comprese
le 7 escluse. La nuova ricerca non cancella automaticamente prove pregresse
più specifiche: per esempio Sauris conserva anche il riferimento E14 del 29 ottobre.

## Riscontri utili e problemi emersi

| Caso | Evidenza | Conseguenza per catalogazione e gestione |
|---|---|---|
| Mercati nelle frazioni | Il [Distretto Alto Livenza](https://www.distrettocommercioaltolivenza.it/alla-scoperta-delle-tradizioni-del-distretto-feste-sagre-e-mercati-storici-da-non-perdere/) distingue Budoia, Maron, Caneva, Polcenigo e Coltura; ulteriori piste ad Aprilia Marittima, Campagnola e Vendoglio | Il solo nome del capoluogo non identifica mercato o sede; comune e frazione vanno separati |
| Pordenone, festivi | La [determina 924/2026](https://www.comune.pordenone.it/it/argomenti/mercato/cittadino/determina-calendario-2026-2027.pdf/@@download/file) annulla il 26/12/2026; straordinari 13 e 20/12 subordinati alle adesioni | Una ricorrenza del sabato non basta; eccezioni e condizioni devono prevalere. Verificare atti successivi prima della pubblicazione |
| San Pietro al Natisone | [Organizzatore](https://www.nediskedoline.it/wpnediske/event/gesti-antichi-per-un-nuovo-natale-2026/): 5, 6 e 8 dicembre 2026, 10–18; chiuso il 7 | Conservare giornate effettive e chiusura, senza espandere indiscriminatamente il periodo 5–8 dicembre |
| Muggia, settimanale | [Indice comunale](https://www.comune.muggia.ts.it/it/categories/mercato-9905): sede temporanea dal 07/05/2026 e sospensione del 02/07/2026 | Decorrenza della sede e annullamento di un'edizione sono operazioni diverse; rientro da verificare |
| Gemona, sedi | [Visit Gemona](https://visitgemona.com/servizi/contatti/) distingue primo/ultimo venerdì dagli altri per il settimanale; sul mercatino delle pulci diverge da [UNPLI](https://prolocoregionefvg.it/eventi-delle-associate/mercatino-delle-pulci-e-del-libro-usato/) | Distinguere settimanale e periodico, versionare le sedi; resta aperto il conflitto Ferro/via Bini del mercatino delle pulci |
| San Floriano del Collio | [MIMIT](https://www.mimit.gov.it/en/eventi-2026/mercato-all-aperto): iniziativa per istituire un mercato, datata 15/04/2026 | Registrare un progetto da confermare, non un mercato attivo né un'edizione in quella data |
| Trieste, Foraggi/via dei Mille | La [presentazione comunale](https://www.comune.trieste.it/media/files/032006/attachment/241204_-_CTS_-_presentazione_regolamento_lr-1.pdf), p.9, menziona esplicitamente l'eliminazione dei due mercati inutilizzati | È un riscontro più preciso della semplice omissione da un elenco; riconciliare atti efficaci, decorrenza e vecchia guida prima di decidere sulle schede |
| Romans d'Isonzo | L'[opuscolo 2025](https://www.comune.romans.go.it/media/files/031015/attachment/Fiera_di_Santa_Elisabetta_opuscolo_2025_low_7Dj8UBt.pdf), p.9, annuncia la Fiera 12–16/11/2026 | Il periodo della festa non prova tutti i giorni/orari delle bancarelle; serve il programma operativo 2026 |

Ulteriori candidature future documentate nel registro comprendono Turriaco
06/12, Ronchis 22/11, Raveo 13/12 e la mostra mercato di San Pietro. Sono
conservate con fonti e limiti per la revisione, senza modificare il runtime.
I mercati di Campagna Amica di Cividale e Codroipo sono tenuti distinti dai
settimanali ordinari; una riduzione di posteggi, come a Majano, non viene
interpretata come chiusura del mercato.

Sono rimasti aperti, fra gli altri, il conflitto linguistico/temporale della
Fiera San Carlo di Aiello, le date incoerenti di Natale a Spilimbergo, la
continuità del mercato contadino di Fontanafredda e di numerosi mercati
descritti soltanto da vecchi regolamenti. Le notizie di mercatini «nei dintorni»,
i negozi che contengono la parola mercato, le gite verso altre città e la sede
legale di un organizzatore non sono state trasformate in mercati del comune.

## Come usare questo lavoro nel pannello

L'audit della copia locale del pannello ha verificato che **Eventi e Scopri
sono ancora predisposizioni**, mentre le bozze editoriali del consiglio sono
locali al browser. Il catalogo Mercati dell'app è un import statico. Quindi
oggi il pannello non può ancora aggiornare queste schede nell'app.

Il [contratto proposto](MERCATI_GESTIONE_PANNELLO_CONTRATTO_20261030.md) prevede
un archivio comune e un editor nel pannello esistente, con:

- identità stabile del mercato e delle singole edizioni;
- modifica di data/sede limitata a una giornata oppure con decorrenza;
- aggiunta, sospensione, ritiro e archiviazione con storico;
- fonti, stato di verifica, revisione, anteprima e pubblicazione separati;
- stessa revisione consumata da Scopri ed Eventi su Web e Android;
- cache e feed che rispettano ritiri e spostamenti, senza far riapparire dati vecchi.

Gli ID di ricerca UDA/UDB/PN/GTS non sostituiscono gli ID applicativi M001…M060.
Prima dell'importazione occorre riconciliare identità, alias e fonti per campo.
I giorni nel registro sono ISO 1–7: il selettore attuale usa invece 0 per la
domenica. Le date esplicite, anche quando presenti, possono essere storiche,
condizionate o in conflitto e non costituiscono un lotto automaticamente pubblicabile.

## Verifica e prossime attività

Il lotto interessa solo documentazione e dati di ricerca. **Verifica
indipendente superata** su anagrafica, identificatori, riferimenti alle fonti,
formati data, conteggi e immutabilità del catalogo applicativo. Verificati
215 codici unici, i collegamenti a tutte le 74/44/60 schede pregresse e la
separazione di **105 coppie candidatura/data esplicita** da **9 periodi di
manifestazione**. Trenta date sono dal 30 ottobre in poi: non sono per questo
automaticamente pubblicabili.

Il controllo del contratto contro app e pannello locale non ha rilevato
impedimenti tecnici nella proposta. Controllati indice comunale e link locali.
`scripts/test-canonical-workspace-cleanliness.ps1` superato su **4029 file
tracciati**, inclusi i tre nuovi documenti/dati; `git diff --cached --check`
superato. Il verificatore ha controllato coerenza e limiti delle attribuzioni,
senza rileggere sul Web tutte le fonti: non è una seconda conferma indipendente
di ogni fatto remoto. Nessun test applicativo, lint o build necessario per
questo lotto documentale; il funzionamento del futuro collegamento al pannello
non è stato implementato né provato.

Il catalogo runtime resta di **53 schede pubbliche e 7 escluse**, con **176
date** e verifica applicativa ferma al 14/10/2026. SHA-256:
`dce63d9d521ccfd9f593de9143f0ff0649220a0a15c09135ecf902290fecbafb`.
Nessuna nuova voce attivata, nessuna promozione remota, modifica al pannello,
build o pubblicazione Web/Android. AAB 300038 e Web distribuita invariati.
Prova visiva Mercati e revisione FUR restano aperte.

La coda successiva è esplicita: approfondire i 100 comuni al primo esame e le
piste storiche/incerte degli altri, risolvere i conflitti, completare orari e
sedi, riconciliare le identità e revisionare le candidature selezionate. La
realizzazione del collegamento col pannello segue il contratto separato.
Nessun contatto agli enti o agli organizzatori è stato inviato.

## Indice dei comuni

«Approfondita» significa almeno una pista, non censimento completo.
«Riscontri» può includere prove pregresse; «Da chiarire» comprende storia e
conflitti; «Non acquisiti» non significa assenza di mercati. I dettagli e la
prossima azione sono nel JSON, identificati dal codice ISTAT.

<!-- MUNICIPALITY_TABLE -->

| ISTAT | Comune | Provincia | Esame | Esito | Candidature del lotto | ID applicativi collegati |
|---|---|---|---|---|---:|---|
| 031001 | Capriva del Friuli | GO | Primo esame | Non acquisiti | 0 | — |
| 031002 | Cormons | GO | Primo esame | Riscontri | 0 | M007 |
| 031003 | Doberdò del Lago | GO | Approfondita | Da chiarire | 1 | — |
| 031004 | Dolegna del Collio | GO | Primo esame | Non acquisiti | 0 | — |
| 031005 | Farra d'Isonzo | GO | Primo esame | Non acquisiti | 0 | — |
| 031006 | Fogliano Redipuglia | GO | Primo esame | Da chiarire | 0 | — |
| 031007 | Gorizia | GO | Approfondita | Da chiarire | 1 | M030 |
| 031008 | Gradisca d'Isonzo | GO | Approfondita | Riscontri | 1 | M032 |
| 031009 | Grado | GO | Primo esame | Da chiarire | 1 | M006 |
| 031010 | Mariano del Friuli | GO | Primo esame | Non acquisiti | 0 | — |
| 031011 | Medea | GO | Approfondita | Da chiarire | 1 | — |
| 031012 | Monfalcone | GO | Primo esame | Riscontri | 0 | M008 |
| 031013 | Moraro | GO | Primo esame | Non acquisiti | 0 | — |
| 031014 | Mossa | GO | Approfondita | Da chiarire | 2 | — |
| 031015 | Romans d'Isonzo | GO | Approfondita | Da chiarire | 1 | — |
| 031016 | Ronchi dei Legionari | GO | Primo esame | Da chiarire | 1 | M009 |
| 031017 | Sagrado | GO | Primo esame | Non acquisiti | 0 | — |
| 031018 | San Canzian d'Isonzo | GO | Approfondita | Non acquisiti | 0 | — |
| 031019 | San Floriano del Collio | GO | Approfondita | Da chiarire | 1 | — |
| 031020 | San Lorenzo Isontino | GO | Primo esame | Non acquisiti | 0 | — |
| 031021 | San Pier d'Isonzo | GO | Primo esame | Non acquisiti | 0 | — |
| 031022 | Savogna d'Isonzo | GO | Primo esame | Non acquisiti | 0 | — |
| 031023 | Staranzano | GO | Approfondita | Da chiarire | 1 | — |
| 031024 | Turriaco | GO | Approfondita | Riscontri | 1 | — |
| 031025 | Villesse | GO | Primo esame | Da chiarire | 1 | — |
| 093001 | Andreis | PN | Approfondita | Da chiarire | 1 | — |
| 093002 | Arba | PN | Primo esame | Non acquisiti | 0 | — |
| 093004 | Aviano | PN | Approfondita | Riscontri | 3 | M020, M025 |
| 093005 | Azzano Decimo | PN | Approfondita | Da chiarire | 4 | — |
| 093006 | Barcis | PN | Approfondita | Da chiarire | 1 | — |
| 093007 | Brugnera | PN | Approfondita | Riscontri | 2 | — |
| 093008 | Budoia | PN | Approfondita | Da chiarire | 1 | — |
| 093009 | Caneva | PN | Approfondita | Da chiarire | 1 | — |
| 093010 | Casarsa della Delizia | PN | Approfondita | Da chiarire | 3 | — |
| 093011 | Castelnovo del Friuli | PN | Primo esame | Non acquisiti | 0 | — |
| 093012 | Cavasso Nuovo | PN | Primo esame | Non acquisiti | 0 | — |
| 093013 | Chions | PN | Primo esame | Non acquisiti | 0 | — |
| 093014 | Cimolais | PN | Approfondita | Riscontri | 1 | — |
| 093015 | Claut | PN | Approfondita | Da chiarire | 1 | — |
| 093016 | Clauzetto | PN | Approfondita | Da chiarire | 1 | — |
| 093017 | Cordenons | PN | Approfondita | Da chiarire | 1 | — |
| 093018 | Cordovado | PN | Primo esame | Non acquisiti | 0 | — |
| 093019 | Erto e Casso | PN | Approfondita | Da chiarire | 1 | — |
| 093020 | Fanna | PN | Approfondita | Riscontri | 1 | — |
| 093021 | Fiume Veneto | PN | Approfondita | Da chiarire | 1 | — |
| 093022 | Fontanafredda | PN | Approfondita | Da chiarire | 3 | — |
| 093024 | Frisanco | PN | Primo esame | Non acquisiti | 0 | — |
| 093025 | Maniago | PN | Approfondita | Da chiarire | 1 | — |
| 093026 | Meduno | PN | Primo esame | Da chiarire | 1 | — |
| 093027 | Montereale Valcellina | PN | Approfondita | Da chiarire | 1 | — |
| 093028 | Morsano al Tagliamento | PN | Approfondita | Da chiarire | 1 | — |
| 093029 | Pasiano di Pordenone | PN | Primo esame | Da chiarire | 2 | M012, M019 |
| 093030 | Pinzano al Tagliamento | PN | Approfondita | Riscontri | 1 | — |
| 093031 | Polcenigo | PN | Approfondita | Da chiarire | 3 | — |
| 093032 | Porcia | PN | Approfondita | Da chiarire | 1 | — |
| 093033 | Pordenone | PN | Approfondita | Riscontri | 5 | M001, M035, M036 |
| 093034 | Prata di Pordenone | PN | Approfondita | Riscontri | 2 | — |
| 093035 | Pravisdomini | PN | Primo esame | Non acquisiti | 0 | — |
| 093036 | Roveredo in Piano | PN | Approfondita | Da chiarire | 1 | — |
| 093037 | Sacile | PN | Approfondita | Riscontri | 4 | M002, M018, M037 |
| 093038 | San Giorgio della Richinvelda | PN | Primo esame | Non acquisiti | 0 | — |
| 093039 | San Martino al Tagliamento | PN | Primo esame | Non acquisiti | 0 | — |
| 093040 | San Quirino | PN | Approfondita | Da chiarire | 2 | — |
| 093041 | San Vito al Tagliamento | PN | Approfondita | Riscontri | 4 | M026, M058, M059 |
| 093042 | Sequals | PN | Approfondita | Da chiarire | 1 | — |
| 093043 | Sesto al Reghena | PN | Primo esame | Da chiarire | 3 | M013, M014, M015 |
| 093044 | Spilimbergo | PN | Approfondita | Riscontri | 4 | M031, M060 |
| 093045 | Tramonti di Sopra | PN | Approfondita | Riscontri | 1 | — |
| 093046 | Tramonti di Sotto | PN | Approfondita | Da chiarire | 1 | — |
| 093047 | Travesio | PN | Primo esame | Non acquisiti | 0 | — |
| 093052 | Vajont | PN | Approfondita | Da chiarire | 1 | — |
| 093053 | Valvasone Arzene | PN | Primo esame | Da chiarire | 3 | — |
| 093049 | Vito d'Asio | PN | Approfondita | Da chiarire | 1 | — |
| 093050 | Vivaro | PN | Approfondita | Da chiarire | 1 | — |
| 093051 | Zoppola | PN | Approfondita | Da chiarire | 1 | — |
| 032001 | Duino Aurisina | TS | Primo esame | Da chiarire | 0 | M046 |
| 032002 | Monrupino | TS | Approfondita | Da chiarire | 1 | — |
| 032003 | Muggia | TS | Primo esame | Da chiarire | 1 | M016, M044, M045, M056, M057 |
| 032004 | San Dorligo della Valle | TS | Approfondita | Riscontri | 1 | — |
| 032005 | Sgonico | TS | Primo esame | Non acquisiti | 0 | — |
| 032006 | Trieste | TS | Approfondita | Riscontri | 0 | M021, M022, M023, M033, M047, M048, M049, M050, M051, M052, M055 |
| 030001 | Aiello del Friuli | UD | Approfondita | Riscontri | 2 | — |
| 030002 | Amaro | UD | Primo esame | Non acquisiti | 0 | — |
| 030003 | Ampezzo | UD | Primo esame | Non acquisiti | 0 | — |
| 030004 | Aquileia | UD | Approfondita | Da chiarire | 2 | — |
| 030005 | Arta Terme | UD | Approfondita | Riscontri | 1 | — |
| 030006 | Artegna | UD | Approfondita | Da chiarire | 1 | — |
| 030007 | Attimis | UD | Primo esame | Non acquisiti | 0 | — |
| 030008 | Bagnaria Arsa | UD | Approfondita | Riscontri | 1 | — |
| 030009 | Basiliano | UD | Approfondita | Riscontri | 1 | — |
| 030010 | Bertiolo | UD | Approfondita | Da chiarire | 1 | — |
| 030011 | Bicinicco | UD | Primo esame | Non acquisiti | 0 | — |
| 030012 | Bordano | UD | Approfondita | Da chiarire | 1 | — |
| 030013 | Buja | UD | Primo esame | Non acquisiti | 0 | — |
| 030014 | Buttrio | UD | Approfondita | Da chiarire | 1 | — |
| 030015 | Camino al Tagliamento | UD | Approfondita | Da chiarire | 1 | — |
| 030016 | Campoformido | UD | Approfondita | Da chiarire | 1 | — |
| 030138 | Campolongo Tapogliano | UD | Primo esame | Non acquisiti | 0 | — |
| 030018 | Carlino | UD | Approfondita | Da chiarire | 1 | — |
| 030019 | Cassacco | UD | Approfondita | Da chiarire | 1 | — |
| 030020 | Castions di Strada | UD | Primo esame | Non acquisiti | 0 | — |
| 030021 | Cavazzo Carnico | UD | Approfondita | Da chiarire | 1 | — |
| 030022 | Cercivento | UD | Approfondita | Riscontri | 1 | — |
| 030023 | Cervignano del Friuli | UD | Approfondita | Riscontri | 3 | M027 |
| 030024 | Chiopris-Viscone | UD | Primo esame | Non acquisiti | 0 | — |
| 030025 | Chiusaforte | UD | Primo esame | Non acquisiti | 0 | — |
| 030026 | Cividale del Friuli | UD | Approfondita | Riscontri | 3 | M010, M039 |
| 030027 | Codroipo | UD | Approfondita | Riscontri | 2 | M003, M028, M053 |
| 030028 | Colloredo di Monte Albano | UD | Primo esame | Non acquisiti | 0 | — |
| 030029 | Comeglians | UD | Approfondita | Da chiarire | 1 | — |
| 030030 | Corno di Rosazzo | UD | Approfondita | Da chiarire | 1 | — |
| 030031 | Coseano | UD | Primo esame | Non acquisiti | 0 | — |
| 030032 | Dignano | UD | Approfondita | Da chiarire | 1 | — |
| 030033 | Dogna | UD | Primo esame | Non acquisiti | 0 | — |
| 030034 | Drenchia | UD | Primo esame | Non acquisiti | 0 | — |
| 030035 | Enemonzo | UD | Approfondita | Riscontri | 1 | — |
| 030036 | Faedis | UD | Primo esame | Non acquisiti | 0 | — |
| 030037 | Fagagna | UD | Primo esame | Non acquisiti | 0 | — |
| 030190 | Fiumicello Villa Vicentina | UD | Approfondita | Riscontri | 4 | — |
| 030039 | Flaibano | UD | Primo esame | Non acquisiti | 0 | — |
| 030137 | Forgaria nel Friuli | UD | Primo esame | Non acquisiti | 0 | — |
| 030040 | Forni Avoltri | UD | Approfondita | Da chiarire | 1 | — |
| 030041 | Forni di Sopra | UD | Approfondita | Riscontri | 2 | — |
| 030042 | Forni di Sotto | UD | Primo esame | Non acquisiti | 0 | — |
| 030043 | Gemona del Friuli | UD | Approfondita | Riscontri | 3 | M011, M034, M043 |
| 030044 | Gonars | UD | Approfondita | Da chiarire | 1 | — |
| 030045 | Grimacco | UD | Primo esame | Non acquisiti | 0 | — |
| 030046 | Latisana | UD | Approfondita | Riscontri | 3 | — |
| 030047 | Lauco | UD | Primo esame | Non acquisiti | 0 | — |
| 030048 | Lestizza | UD | Primo esame | Non acquisiti | 0 | — |
| 030049 | Lignano Sabbiadoro | UD | Approfondita | Riscontri | 2 | — |
| 030051 | Lusevera | UD | Primo esame | Non acquisiti | 0 | — |
| 030052 | Magnano in Riviera | UD | Primo esame | Non acquisiti | 0 | — |
| 030053 | Majano | UD | Approfondita | Riscontri | 1 | — |
| 030054 | Malborghetto Valbruna | UD | Approfondita | Da chiarire | 1 | — |
| 030055 | Manzano | UD | Approfondita | Da chiarire | 1 | — |
| 030056 | Marano Lagunare | UD | Approfondita | Da chiarire | 1 | — |
| 030057 | Martignacco | UD | Approfondita | Da chiarire | 1 | — |
| 030058 | Mereto di Tomba | UD | Primo esame | Non acquisiti | 0 | — |
| 030059 | Moggio Udinese | UD | Approfondita | Riscontri | 1 | — |
| 030060 | Moimacco | UD | Approfondita | Da chiarire | 1 | — |
| 030061 | Montenars | UD | Approfondita | Da chiarire | 1 | — |
| 030062 | Mortegliano | UD | Approfondita | Da chiarire | 3 | — |
| 030063 | Moruzzo | UD | Primo esame | Non acquisiti | 0 | — |
| 030064 | Muzzana del Turgnano | UD | Primo esame | Non acquisiti | 0 | — |
| 030065 | Nimis | UD | Approfondita | Da chiarire | 1 | — |
| 030066 | Osoppo | UD | Approfondita | Da chiarire | 1 | — |
| 030067 | Ovaro | UD | Approfondita | Riscontri | 2 | — |
| 030068 | Pagnacco | UD | Primo esame | Non acquisiti | 0 | — |
| 030069 | Palazzolo dello Stella | UD | Approfondita | Da chiarire | 1 | — |
| 030070 | Palmanova | UD | Approfondita | Riscontri | 3 | M005 |
| 030071 | Paluzza | UD | Primo esame | Da chiarire | 1 | — |
| 030072 | Pasian di Prato | UD | Approfondita | Da chiarire | 1 | — |
| 030073 | Paularo | UD | Approfondita | Da chiarire | 3 | — |
| 030074 | Pavia di Udine | UD | Primo esame | Non acquisiti | 0 | — |
| 030075 | Pocenia | UD | Primo esame | Non acquisiti | 0 | — |
| 030076 | Pontebba | UD | Approfondita | Riscontri | 1 | — |
| 030077 | Porpetto | UD | Primo esame | Non acquisiti | 0 | — |
| 030078 | Povoletto | UD | Primo esame | Non acquisiti | 0 | — |
| 030079 | Pozzuolo del Friuli | UD | Primo esame | Da chiarire | 1 | — |
| 030080 | Pradamano | UD | Primo esame | Da chiarire | 1 | — |
| 030081 | Prato Carnico | UD | Approfondita | Da chiarire | 1 | — |
| 030082 | Precenicco | UD | Primo esame | Non acquisiti | 0 | — |
| 030083 | Premariacco | UD | Approfondita | Da chiarire | 1 | — |
| 030084 | Preone | UD | Primo esame | Non acquisiti | 0 | — |
| 030085 | Prepotto | UD | Primo esame | Non acquisiti | 0 | — |
| 030086 | Pulfero | UD | Primo esame | Non acquisiti | 0 | — |
| 030087 | Ragogna | UD | Approfondita | Da chiarire | 1 | — |
| 030088 | Ravascletto | UD | Primo esame | Non acquisiti | 0 | — |
| 030089 | Raveo | UD | Approfondita | Riscontri | 1 | — |
| 030090 | Reana del Rojale | UD | Approfondita | Da chiarire | 1 | — |
| 030091 | Remanzacco | UD | Primo esame | Non acquisiti | 0 | — |
| 030092 | Resia | UD | Primo esame | Da chiarire | 1 | — |
| 030093 | Resiutta | UD | Approfondita | Da chiarire | 1 | — |
| 030094 | Rigolato | UD | Primo esame | Non acquisiti | 0 | — |
| 030095 | Rive d'Arcano | UD | Approfondita | Da chiarire | 1 | — |
| 030188 | Rivignano Teor | UD | Primo esame | Riscontri | 0 | — |
| 030097 | Ronchis | UD | Approfondita | Riscontri | 1 | — |
| 030098 | Ruda | UD | Primo esame | Da chiarire | 1 | — |
| 030099 | San Daniele del Friuli | UD | Approfondita | Da chiarire | 1 | M004, M017, M038 |
| 030100 | San Giorgio di Nogaro | UD | Primo esame | Da chiarire | 0 | — |
| 030101 | San Giovanni al Natisone | UD | Approfondita | Da chiarire | 1 | — |
| 030102 | San Leonardo | UD | Primo esame | Non acquisiti | 0 | — |
| 030103 | San Pietro al Natisone | UD | Approfondita | Riscontri | 1 | — |
| 030105 | San Vito al Torre | UD | Primo esame | Non acquisiti | 0 | — |
| 030106 | San Vito di Fagagna | UD | Primo esame | Non acquisiti | 0 | — |
| 030104 | Santa Maria la Longa | UD | Primo esame | Non acquisiti | 0 | — |
| 030189 | Sappada | UD | Approfondita | Da chiarire | 1 | M054 |
| 030107 | Sauris | UD | Approfondita | Da chiarire | 2 | — |
| 030108 | Savogna | UD | Primo esame | Non acquisiti | 0 | — |
| 030109 | Sedegliano | UD | Primo esame | Non acquisiti | 0 | — |
| 030110 | Socchieve | UD | Primo esame | Non acquisiti | 0 | — |
| 030111 | Stregna | UD | Primo esame | Non acquisiti | 0 | — |
| 030112 | Sutrio | UD | Primo esame | Non acquisiti | 0 | — |
| 030113 | Taipana | UD | Primo esame | Non acquisiti | 0 | — |
| 030114 | Talmassons | UD | Primo esame | Non acquisiti | 0 | — |
| 030116 | Tarcento | UD | Approfondita | Da chiarire | 1 | — |
| 030117 | Tarvisio | UD | Primo esame | Da chiarire | 0 | — |
| 030118 | Tavagnacco | UD | Primo esame | Da chiarire | 1 | — |
| 030120 | Terzo d'Aquileia | UD | Approfondita | Da chiarire | 1 | — |
| 030121 | Tolmezzo | UD | Primo esame | Riscontri | 0 | — |
| 030122 | Torreano | UD | Primo esame | Non acquisiti | 0 | — |
| 030123 | Torviscosa | UD | Primo esame | Non acquisiti | 0 | — |
| 030124 | Trasaghis | UD | Approfondita | Da chiarire | 2 | — |
| 030126 | Treppo Grande | UD | Approfondita | Da chiarire | 3 | — |
| 030191 | Treppo Ligosullo | UD | Primo esame | Da chiarire | 1 | — |
| 030127 | Tricesimo | UD | Approfondita | Da chiarire | 2 | — |
| 030128 | Trivignano Udinese | UD | Primo esame | Non acquisiti | 0 | — |
| 030129 | Udine | UD | Approfondita | Riscontri | 3 | M024, M040, M041, M042 |
| 030130 | Varmo | UD | Primo esame | Non acquisiti | 0 | — |
| 030131 | Venzone | UD | Primo esame | Riscontri | 0 | M029 |
| 030132 | Verzegnis | UD | Primo esame | Non acquisiti | 0 | — |
| 030133 | Villa Santina | UD | Approfondita | Da chiarire | 1 | — |
| 030135 | Visco | UD | Primo esame | Da chiarire | 1 | — |
| 030136 | Zuglio | UD | Primo esame | Non acquisiti | 0 | — |
