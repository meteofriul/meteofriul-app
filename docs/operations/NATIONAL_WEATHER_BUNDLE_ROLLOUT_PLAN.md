# Piano di rollout dei pacchetti meteo nazionali

Data: 25 settembre 2026
Stato: bundle nazionale pubblicato; attivazione diretta per Avvisi locali approvata
Perimetro: previsioni ICON-2I precalcolate per tutti i Comuni italiani

## Decisione

La destinazione approvata è una copertura nazionale precalcolata. Ogni corsa ICON
completa produrrà blocchi geografici immutabili e un indice Comune ISTAT → blocco.
L'app scaricherà soltanto il blocco della località attiva. La pipeline non eseguirà
calcoli meteorologici su richiesta dell'utente.

Il contratto nazionale è `weather/v2/icon2i` e resta separato dal contratto FVG
v1. Per gli Avvisi locali la decisione del 25 settembre è l'apertura nazionale
diretta, senza coorte e senza periodo shadow: FVG continua a usare il contratto
v1 già collaudato, gli altri Comuni usano v2. L'apertura extra-FVG parte dal
Comune selezionato manualmente; il GPS nazionale resta fail-closed fino alla
disponibilità di un resolver di confini comunali di produzione. Allerte
ufficiali Protezione Civile restano esclusivamente FVG.

Ogni lettura v2 verifica identità ISTAT, run, percorso, dimensione e SHA-256 del
blocco, catalogo nazionale fissato e serie orarie richieste. Il servizio non
degrada su un Comune vicino e non invia se una verifica fallisce. Nessun
puntatore viene considerato valido prima che tutti i blocchi, l'indice e il
manifest siano completi e verificati.

## Fondazione offline completata

- catalogo identitario dei 7.894 Comuni al 21 febbraio 2026;
- codici ISTAT, UTS, provincia storica, regione e sigla provinciale distinti;
- fonti, licenza CC BY 4.0, hash e proiezione ISTAT fissati;
- riconciliazione esplicita delle variazioni amministrative successive ai confini del
  1° gennaio 2026;
- lookup esatto per ISTAT o nome + provincia, con omonimi fail-closed;
- artefatto approvato di 7.894 punti capoluogo ISTAT, con provenienza e policy
  verificabili;
- contratto v2 con JSON canonico, hash, limiti di dimensione, deduplicazione delle
  celle, indice e manifest pubblicabile per ultimo;
- benchmark strutturale e benchmark GRIB reale riproducibili, validati contro lo
  stesso contratto.

I punti oggi presenti nel catalogo sono punti interni derivati dai confini
generalizzati ISTAT. Servono alla verifica geometrica e al dimensionamento, ma **non
sono automaticamente sedi comunali né punti meteo approvati**. Il benchmark reale
non li usa: carica il distinto artefatto ufficiale dei capoluoghi descritto sotto.

## Risultato del benchmark strutturale

Assunzioni: tessere da 0,5°, 73 ore, 14 variabili, griglia ICON approssimata e valori
sintetici deterministici.

| Misura | Risultato |
| --- | ---: |
| Comuni | 7.894 |
| Blocchi | 209 |
| Celle approssimate uniche | 7.775 |
| Blocco massimo | 261 Comuni / 236 celle |
| Blocco massimo JSON | 1.409.939 byte |
| Blocco massimo gzip-6 | 114.094 byte |
| Bundle completo JSON | 47.366.826 byte |
| Bundle completo gzip-6 | 4.232.400 byte |

Il sintetico ha confermato il contratto, ma ha sottostimato il peso reale. Nella
prima prova GRIB una tessera da 0,5° ha superato il limite invariato di 2 MiB JSON.
Per questo il profilo nazionale reale usa tessere da 0,25°, senza aumentare alcun
limite di sicurezza.

## Risultato del benchmark GRIB reale

Corsa pubblica ICON-2I `2026092000`, 14 variabili × 73 scadenze. I GRIB sono stati
trasferiti in streaming e non conservati. Mapping, layout, input e output sono legati
da hash; il bundle prodotto è stato riletto e validato integralmente.

| Misura | Risultato |
| --- | ---: |
| Sorgente elaborata | 1.108.639.950 byte |
| Messaggi GRIB | 1.022 |
| Tempo totale locale | 221,90 s |
| Tempo CPU totale | 85,84 s |
| Tempo rete, inclusa discovery | 141,46 s |
| Decodifica ecCodes | 17,30 s |
| Costruzione bundle | 51,65 s |
| Picco working set | 655.314.944 byte |
| Comuni mappati | 7.894 |
| Celle ICON uniche | 7.502 |
| Celle condivise da più Comuni | 373 |
| Distanza media punto → cella | 0,817 km |
| Distanza massima punto → cella | 1,529 km |
| Tessere | 642 da 0,25° |
| Blocco massimo | 84 Comuni / 72 celle |
| Blocco massimo JSON | 788.685 byte |
| Blocco massimo gzip-6 | 234.326 byte |
| Blocco gzip mediano / p95 | 32.248 / 107.072 byte |
| Bundle completo JSON | 85.834.371 byte |
| Bundle completo gzip-6 | 26.642.401 byte |

Per il telefono conta il singolo blocco della località, non i 26,6 MB dell'intera
Italia. Nel benchmark i blocchi gzip vanno da 5.018 a 234.326 byte; indice e manifest
compressi pesano insieme circa 68 KB e possono essere memorizzati in cache.

### Indicazione economica Cloud Run Jobs

Applicando alle misure locali le [tariffe pubblicate per Cloud Run
Jobs](https://cloud.google.com/run/pricing) e ipotizzando 1 vCPU, 1 GiB e 221,90
secondi fatturabili, la sola generazione costa circa **$0,0031 per corsa** prima del
free tier. Sono circa **$0,37/mese** con quattro corse al giorno o **$0,75/mese**
con otto corse al giorno. Entrambi gli scenari restano sotto il free tier mensile
CPU/RAM pubblicato, se questo non è già consumato da altri workload dello stesso
account di fatturazione.

È una proiezione, non una fattura né un benchmark Cloud Run. Non include storage,
egress verso gli utenti, operazioni, log, retry, imposte o conversione valutaria.

## Punto meteo comunale

Per campionare una cella meteo non serve l'ingresso esatto del municipio. La base
approvata è il punto ufficiale del **capoluogo comunale** nella release ISTAT
`LocalitaPuntuali_21`, selezionato esclusivamente con `CENTRO_CL=1`. Non viene
presentato come posizione GPS, sede civica o centro geometrico.

La sorgente contiene 7.904 capoluoghi al 31 dicembre 2021. Il resolver offline la
riconcilia con il registro corrente del 2026:

- 7.510 Comuni tramite il codice ISTAT corrente;
- 377 tramite la colonna ufficiale dei codici 2017–2025;
- 7 fusioni recenti tramite override puntuali documentati;
- 7.894 `LOC_ID` distinti, senza riuso o fallback impliciti.

Tutti i punti sono stati trasformati da `EPSG:32632` a `EPSG:4326` con pyproj 3.8.0
e PROJ 9.8.1 e verificati, senza tolleranza, nei confini ISTAT 2026
**non generalizzati**. I confini generalizzati non sono adatti a questo gate: nove
capoluoghi risultavano artificialmente fuori di 11–179 metri per effetto della
semplificazione cartografica.

| Artefatto o fonte | SHA-256 |
| --- | --- |
| Località puntuali ISTAT 2021 | `67ba8a957b9c1ea21ed6144cc33ec1ac3c3a0b1370ba4443452e63ae37e2b9f9` |
| Registro Comuni ISTAT 2026 | `83842076860450f7e482daecea6b7a769f5f93d0bf5b0d48802b44896d7a26d5` |
| Confini dettagliati ISTAT 2026 | `a9075f8d839dcb2b409099703da7bdd37cc214f8967fa7372b32305875ad046f` |
| Policy di risoluzione | `a6ba986822a2c1fbc0657f6a577e057a528d021c34d60fd26d62ab7ead9c41df` |
| Punti canonici | `7993c58d891592e04df845c7fc7f9ef77471cd358db414e160ab5b73e27852ac` |
| Artefatto punti completo | `f9d36d88a7724822b7eac2b6810b6a8e6dc9890ed6dad16a674dec68ee5aa038` |

### Audit degli indirizzi civici del 20 settembre 2026

IndicePA e ANNCSU restano utili se un prodotto futuro richiederà l'accesso esatto
alla sede comunale, ma non sono più un gate per il punto meteo del capoluogo.

Lo snapshot ufficiale [Georeferenziazione accessi ANNCSU](https://www.anncsu.gov.it/it/consultazione-dellarchivio/georeferenziazione-numeri-civici/)
del 31 marzo 2026 contiene 7.894 righe comunali. Il file verificato misura
425.034 byte e ha SHA-256
`932d3e7682b98629ab468df5b7c070b260f46cc87fcb9f50f2d7106fb0b370c2`.
I suoi 7.894 `CODICE AMMINISTRATIVO` coincidono uno a uno con i codici
catastali del catalogo corrente. Il campo `CODICE ISTAT` dello stesso foglio
non è invece una chiave valida per il catalogo corrente: 377 valori sono
superati, soprattutto dopo il riordino territoriale della Sardegna.

Il join ammesso è quindi:

```text
catalogo.cadastral_code
  -> ANNCSU.CODICE AMMINISTRATIVO
  -> ANNCSU.CODICE IPA
  -> IndicePA Enti.Codice_IPA
```

Lo snapshot [IndicePA Enti](https://www.indicepa.gov.it/ipa-dati/dataset/enti)
del 20 settembre 2026 misura 4.271.588 byte e ha SHA-256
`549768f47403bc0f144e4eff38f252d683adc028f3061836eed5c2cc748701a3`.
Il join copre 7.894/7.894 enti e tutti hanno un indirizzo, ma 783 indirizzi
non contengono un civico numerico. Non si filtra per `Codice_natura=2430` e
non si usa la località della sede IndicePA come identità del Comune: entrambe
le scorciatoie perdono casi legittimi.

ANNCSU dichiara 27.487.263 accessi, di cui 18.417.502 georiferiti. La copertura
è completa per 4.304 Comuni, parziale per 742 e nulla per 2.848. Perciò
`exact_access` non può essere un requisito universale per il meteo nazionale.

Il riconciliatore locale `municipal_seat_reconciliation.py` applica questo join
senza rete e produce un audit canonico create-only. La CLI richiede gli SHA-256
attesi di ANNCSU e IndicePA e lega provenienza e parsing agli stessi byte
effettivamente analizzati. Sui due snapshot ufficiali l'audit contiene
7.894 record: 7.893 sono `pending` per la successiva risoluzione
indirizzo-accesso e uno è `unresolved`. Quest'ultimo è Caines/Kuens: IndicePA
colloca legittimamente la sede fisica a Rifiano, ma quel punto non può essere
riassegnato in silenzio all'identità comunale di Caines. Nessuna coordinata viene
inventata in questa fase. Questo audit resta separato dal punto meteo approvato.
L'audit riproducibile ottenuto il 20 settembre ha
SHA-256 `c9569166713005f996953c10184a024c0c61e1c53fd203f2ede9eda58f681418`.

## Artefatto di mapping ICON

Il benchmark ha prodotto il mapping ecCodes richiesto sulla griglia reale. Contiene:

```text
catalog_sha256
municipality_codes_sha256
forecast_points_sha256
grid_sha256
istat_code -> grid_index, cell_lat, cell_lon, distance_km
method = eccodes_nearest_v1
```

Il mapping è valido soltanto per quegli hash. Completezza, coordinate della cella e
distanza massima sono gate bloccanti. Il contratto del bundle verifica già la propria
coerenza interna; il publisher reale dovrà anche verificare questo artefatto e
l'impronta degli input GRIB, così valori di una corsa non possono essere etichettati
come un'altra.

Un probe live limitato sulla corsa pubblica `2026092000` ha verificato ecCodes
2.48.0 su otto campi, tre scadenze e tre località senza salvare GRIB: 27.806.817
byte, 42 GET e 13,5 secondi. La griglia reale è `regular_ll`, 761 × 761,
incrementi 0,02° × 0,025°; la Section 3 ha SHA-256
`308f0f76ba713a77d7e1dc7b55c094689077018f0126d18c229b9b10bfda7a18`.
Il benchmark nazionale completo è stato poi eseguito sulla stessa corsa. Il runner
ha limitato byte e messaggi, deduplicato le celle, registrato gli hash della Section
3, dei quattordici file e dei singoli messaggi, validato il bundle v2 e scritto solo
percorsi nuovi. Una rilettura indipendente ha validato tutti i 644 documenti.

Evidenze principali:

- input corsa: `12288d698b5f00d23a714124ebce70445a5988a998ab4ad99ce9f78816ce0f2d`;
- griglia / Section 3: `308f0f76ba713a77d7e1dc7b55c094689077018f0126d18c229b9b10bfda7a18`;
- layout 0,25°: `f5a89b964aa92a5f2f45d548bb24e77f8b29d1adb7ca154e243e6538cf72aa3b`;
- mapping: `f251c2a9e5f2f0acfb286cd8569c8c74f17cdff372ea33271aff221e5230f7eb`;
- manifest bundle: `77020ac7d1c17e4d33700f3b0854ebe47dcd7bf60716d9069690c4ae21bd4536`;
- report: `988ef83c342c01d6aee0d7a867135f12c3d6001621779965d5b9b324bf814f54`.

I punti sono approvati per il mapping; resta sperimentale soltanto il profilo delle
14 variabili. L'esito corretto è quindi
`experimental_product_profile_not_production`, non una deroga sui punti.

## Sequenza di rollout

### Fase A — catalogo dei punti meteo

- acquisire e fissare registro, capoluoghi e confini dettagliati ISTAT;
- riconciliare codici correnti, storici e fusioni successive al 2021;
- verificare unicità, provenienza e containment 7.894/7.894;
- mantenere separato l'audit civico IndicePA/ANNCSU.

Uscita raggiunta: 7.894 punti `official_istat_capoluogo`, senza fallback impliciti.

### Fase B — benchmark GRIB reale

- scegliere una corsa ICON completa e fissarne gli input;
- costruire il mapping ecCodes e l'artefatto di provenienza;
- produrre 73 × 14 dati reali nel contratto v2;
- misurare download, CPU, memoria, wall time, dimensioni raw/gzip e celle condivise.

Uscita raggiunta: misure locali reali e bundle completo validato. Queste misure non
sono ancora un benchmark Cloud Run né una garanzia di costo.

### Fase C — pubblicazione shadow

- caricare oggetti immutabili con create-only;
- verificare ogni hash e un campione nazionale;
- pubblicare il manifest per ultimo;
- avanzare un puntatore shadow soltanto dopo il readback completo;
- mantenere retention e rollback bounded.

Uscita: nessun client legge ancora v2.

### Fase D — confronto FVG e lettura pilota

- confrontare v1/v2 sui 215 Comuni FVG per più corse;
- verificare coste, montagna, pioggia, neve, vento e dati mancanti;
- abilitare il reader v2 soltanto nella pilota con fallback esplicito;
- misurare cambio località, cache per blocco e avvio a freddo.

### Fase E — rollout nazionale

- coorte controllata e osservabilità;
- nessun calcolo attivato dall'utente;
- `latest` aggiornato atomicamente solo per corse complete;
- rollback al precedente manifest senza riscrivere gli oggetti.

## Confini con gli altri prodotti

- Le segnalazioni nazionali usano celle privacy-safe proprie, non celle ICON.
- Le allerte ufficiali arrivano da DPC/centri regionali, non dal modello ICON.
- Gli avvisi previsionali Meteo Friûl basati su ICON sono un canale distinto e
  dichiaratamente non ufficiale.
- OSMER, webcam e contenuti friulani possono restare consultabili fuori regione come
  contenuti FVG esplicitamente etichettati.

## Vincoli attuali

- nessun deploy, push, job cloud, modifica beta o pubblicazione è stato eseguito;
- il catalogo dei confini generalizzati non autorizza segnalazioni GPS: per la
  Community servono geometrie adatte al point-in-polygon;
- il profilo meteo a 14 variabili deve essere revisionato prima della pubblicazione;
- il costo Cloud Run resta una stima finché non viene eseguito un benchmark shadow
  nell'ambiente target; il benchmark locale misura già carico e volume reali.
