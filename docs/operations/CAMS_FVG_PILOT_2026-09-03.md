# CAMS FVG — acquisizione completa e analisi locale

Esito del 3 settembre 2026: **215 Comuni × 28 variabili × 97 istanti**, acquisiti direttamente da ADS e decodificati. Nessun valore mancante o invalido nei punti estratti. È un test completo del perimetro regionale di una corsa, non una migrazione dell'app né una validazione dell'accuratezza delle previsioni.

OSMER, allerte ufficiali, Open-Meteo nell'app, Firebase, Scheduler e pubblicazione restano invariati. Nessun commit, push o deploy. Le modifiche preesistenti a Scopri e meteo sono preservate. Nessuna credenziale è inclusa negli artefatti; l'accettazione della licenza è stata effettuata personalmente dall'utente prima del test.

## Perimetro verificato

- Dataset `cams-europe-air-quality-forecasts`, modello `ensemble`, livello `0`, tipo `forecast`, formato GRIB.
- Corsa **2026-09-03 00:00 UTC**, lead orari **0–96 inclusi**: dal 3 settembre 00 UTC al 7 settembre 00 UTC. Sono 97 istanti, non 96 ore sempre future dall'apertura della pagina.
- Una sola estrazione rettangolare: **N 46.7, W 12.2, S 45.5, E 14.0**. Non 215 richieste, né tutti i modelli o i livelli verticali Copernicus.
- Tutte le 28 variabili di superficie ammesse per questa selezione: 6 pollini, 5 inquinanti principali, 7 ulteriori gas e 10 componenti aerosol. Identità, unità, significato e limiti sono nella [matrice completa](CAMS_DATA_CAPABILITIES_2026-09-03.md).
- Catalogo locale: 134 Comuni UD, 50 PN, 25 GO, 6 TS. Un punto catalogato per Comune, non una media dell'intero territorio comunale. Nessuna nuova geocodifica esterna.

La griglia estratta contiene **18 × 12 = 216 punti**, passo 0,1°, centri da 45.55 a 46.65 N e da 12.25 a 13.95 E. L'area rettangolare comprende anche punti oltre confine e mare; non è un ritaglio lungo i confini amministrativi. I 215 punti comunali selezionano **90 celle native distinte**; le altre restano nel GRIB archiviato.

## Completezza e correttezza tecnica

| Controllo | Risultato |
|---|---:|
| Comuni associati a una cella | 215 / 215 |
| Variabili × istanti per cella | 28 × 97 |
| Messaggi GRIB distinti decodificati | 2.716 |
| Messaggi duplicati | 0 |
| Costruzioni della mappa Comuni-celle | 1 |
| Celle utilizzate / condivise da più Comuni | 90 / 57 |
| Valori distinti delle celle utilizzate | 244.440 |
| Valori associati ai Comuni, contando le condivisioni | 583.940 |
| Valori mancanti, negativi o non finiti nei punti estratti | 0 |
| Casi PM2.5 maggiore di PM10 | 0 |
| Distanza punto comunale–centro cella | 0,215–6,460 km |

Ogni campo viene decodificato una sola volta e gli indici delle 90 celle sono riutilizzati solo con griglia invariata. I valori condivisi non sono ricopiati per ogni Comune: 215 associazioni non equivalgono a 215 previsioni spazialmente indipendenti. Per esempio Trieste e Muggia condividono la cella 195; Pordenone usa la 130, Tarvisio la 31. Staranzano presenta la distanza maggiore, 6,460 km.

Controlli applicati: corsa e validità, livello, identità chimica, unità, griglia/scansione, coordinate e indici, matrice completa, duplicati, valori non finiti, negativi e mancanti. Il campo generico `units` di ecCodes è `unknown` in questi messaggi: le unità sono risolte mediante identità numerica verificata e documentazione del prodotto, con provenienza esplicita. Sei pollini restano granuli/m³; le altre 22 variabili passano da kg/m³ a µg/m³ con fattore 10⁹. Si conservano anche i valori grezzi e gli eventuali flag, senza trasformare null o tracce positive in zero.

La classificazione **7 regolarmente validate / 21 sperimentali** è attribuita esclusivamente alla scheda ADS. La guida ECMWF più recente differisce per NO, dust e CO: la discrepanza è visibile nella preview e spiegata nella matrice. “Decodificato correttamente” non significa “validato contro osservazioni locali”.

## Tempi e memoria misurati

| Fase | Misura osservata |
|---|---:|
| Coda ADS, timestamp del servizio | 11,758 s |
| Elaborazione ADS, timestamp del servizio | 183,660 s |
| Download GRIB | 1,092 s |
| Acquisizione totale lato client, incluso polling | 214,869 s |
| Decodifica, estrazione, conversioni | 36,615 s |
| Analisi e confronto Pordenone | 1,346 s |
| Serializzazione JSON | 0,848 s |
| Compressione gzip dell'audit completo | 1,657 s |
| Processo offline complessivo | 40,999 s |
| Picco memoria processo Windows | 203.059.200 byte, circa 194 MiB |

Le righe di dettaglio locale sono incluse nei 40,999 s, non vanno sommate due volte. Acquisizione riuscita e processo offline separato sommano circa **4 minuti e 16 secondi**, esclusi il tentativo fallito e il tempo umano tra i due processi. Non è una misura end-to-end di un job cloud. I test della preview possono essersi sovrapposti al benchmark locale: il computer non era un ambiente di misura dedicato.

La validazione/lettura dei metadati occupa 32,209 s dei 36,615 s di decodifica; l'estrazione numerica 0,203 s e le conversioni/organizzazione 3,862 s. La mappa geografica richiede circa 0,014 s. Questi numeri descrivono questo codice e questo computer, non costi garantiti in produzione.

Il primo tentativo regionale ha ricevuto HTTP 502 senza un handle locale. Prima del secondo invio è stata controllata in sola lettura la lista dei job ADS: nessun job corrispondente all'intento, un solo job precedente. Il secondo invio è riuscito; nessun retry POST automatico e nessuna richiesta per Comune. Il nuovo helper di riconciliazione limita metodi a GET, host, finestra temporale e dimensione della pagina; con risultati incompleti o ambigui si ferma.

## Byte: archivio completo e consegna all'app sono distinti

Misure UTF-8 compatto e gzip livello 9. MB e KB qui sono decimali. Il GRIB è la sorgente completa; il JSON di audit conserva valori grezzi, convertiti e metadati. Il formato di visualizzazione proposto elimina dal trasporto soltanto la duplicazione dei valori grezzi e alcuni metadati binari: **stessi valori convertiti, senza arrotondamento**, stesse 28 variabili, 97 istanti, unità, flag, corsa, cella e hash della sorgente.

| Artefatto / proposta | JSON o sorgente | gzip |
|---|---:|---:|
| GRIB regionale scaricato | 2.251.564 byte | Non ricompresso |
| Audit regionale, 90 celle e 215 associazioni | 10.217.878 byte | 4.479.262 byte |
| Visualizzazione regionale proposta | 4.816.843 byte | 2.197.780 byte |
| Audit di un Comune, minimo–massimo | 155.865–156.725 byte | 53.070–54.956 byte |
| Visualizzazione di un Comune, minimo–massimo | 71.695–72.392 byte | **27.712–28.575 byte** |
| Visualizzazione di un Comune, mediana | 71.934 byte | **28.164 byte** |

Il profilo di trasporto è un'elaborazione separata del JSON esistente: 0,269 s per leggerlo e 7,785 s per misurare entrambe le proposte su tutti i Comuni. Nessun secondo download o decoding GRIB. Non si propone di comprimere 215 volte a ogni apertura dell'app: in un'eventuale pipeline i risultati per corsa sarebbero preparati una volta e riutilizzati.

**La preview diagnostica attuale serve ancora il JSON di audit regionale non compresso**, insieme allo snapshot ICON separato. I circa 28 KB non sono il traffico già ottenuto in questa pagina, né includono il meteo ICON, intestazioni HTTP o cache. Il dato concreto dimostra che CAMS può avere una consegna piccola per Comune; non dimostra gratuità di Firebase né permanenza nelle quote di un servizio. Il download nazionale ICON già misurato resta separato e non è stato ripetuto.

## Cosa mostra già l'analisi

Il report contiene intervalli per tutte le 28 variabili e **560 riepiloghi provincia/variabile/giorno UTC** (4 province × 28 × 5 date), con cella, Comuni associati e orario del primo estremo incontrato. Il 7 settembre contiene solo l'istante 00 UTC ed è marcato come giorno parziale. Non sono medie territoriali, misure di esposizione o soglie sanitarie.

Alcuni massimi modellistici nell'intera corsa, compresi gli istanti eventualmente già passati:

| Variabile | Massimo | Cella associata a | Istante UTC |
|---|---:|---|---|
| Ambrosia | 114,793 granuli/m³ | Cassacco, Colloredo di Monte Albano, Moruzzo, Pagnacco, Treppo Grande | 04/09 07:00 |
| Graminacee | 9,066 granuli/m³ | Basiliano, Coseano, Mereto di Tomba, San Vito di Fagagna | 03/09 17:00 |
| PM10 | 24,716 µg/m³ | Brugnera, Prata di Pordenone | 04/09 23:00 |
| PM2.5 | 18,497 µg/m³ | Chions | 05/09 00:00 |
| Ozono | 144,303 µg/m³ | Caneva | 04/09 15:00 |
| NO₂ | 20,629 µg/m³ | Muggia, Trieste | 04/09 21:00 |

Non sono avvisi o misure osservate, né affermazioni di rischio. Le concentrazioni minuscole di ontano restano numeri positivi in notazione scientifica, non zeri inventati. I pollini disponibili non coprono tutti gli allergeni; PM10 da incendi non identifica un incendio nel Comune e dust non dimostra origine sahariana. Non si sommano PM10, PM2.5 e componenti sovrapposte e non si costruiscono AQI o percentuali cliniche arbitrarie.

## Confronto con Pordenone e tracciabilità

Il piccolo ritaglio Pordenone e quello regionale hanno stessa corsa, cella fisica 45.95 N / 12.65 E e 2.716 campi confrontabili. Gli indici interni differiscono perché cambia il ritaglio. **896 valori convertiti non coincidono bit per bit**: scarto massimo 0,00000355 µg/m³ per ozono; per i pollini circa 6,1 × 10⁻¹⁸ granuli/m³. La differenza è compatibile con precisione della codifica del ritaglio, ma questa spiegazione non è stata dimostrata analizzando il packing originale. Nessuna correzione applicata e nessuna pretesa di validazione indipendente del modello.

Nota sull'evidenza immutabile: il report di decodifica originale contiene una frase troppo generale sulle mediane nel controllo PM2.5/PM10. Non ci sono violazioni osservate. In generale, con gli stessi membri ordinati PM2.5 ≤ PM10, anche le mediane preservano l'ordine; un'inversione richiederebbe indagini su disponibilità dei membri, definizioni e codifica, non sarebbe spiegata automaticamente dalle mediane. La dicitura del codice per le analisi future è stata corretta senza rigenerare la misura originale.

Artefatti in `experiments/weather_autonomy/`:

- `cams_fvg_request_20260903.json`: richiesta pubblica, perimetro e catalogo.
- `cams_fvg_acquisition_20260903.json`: tempi del servizio, polling, byte e hash; stato storico di fine download, completato poi dal decoder separato.
- `cams_fvg_source_20260903.grib`: sorgente pubblica, SHA-256 `7dfb8b942ebfee7ab1b75914fb5a0b3918c22bdc119b2e37b1e7af74231272d1`.
- `cams_fvg_payload_20260903.json`: audit con celle condivise, SHA-256 `f44158a526858a05642565b74d7e1aab3594ef9b948793852b588fea403175ad`.
- `cams_fvg_decode_report_20260903.json`: completezza, estremi, province, anomalie, tempi, memoria e confronto Pordenone.
- `cams_fvg_transport_projection_20260903.json`: byte proposti per tutti i 215 Comuni, distinti dal traffico reale.

Hash del catalogo locale usato: `06ced5bedc823365b38d83d2be93bd1bf5102ec97b2e5ba4f91c9f5ae5975a57`. Gli artefatti Pordenone e ICON precedenti sono preservati; nessun handle del job o file di credenziali è copiato nel repository.

## Preview, verifica e prossimo limite

[Preview locale](http://127.0.0.1:8767/#cams-section): il selettore dei 215 Comuni coordina ICON e CAMS, ma conserva corse, griglie e coperture distinte. Verificati nel browser Udine, Pordenone, Tarvisio, Trieste e Muggia: 28 righe riepilogative, 97 righe per serie, coordinate corrette, cella condivisa esplicita e tracce positive non azzerate. Nessun errore o avviso nella console durante il controllo.

**454 test isolati superati** (12,687 s), più `git diff --check` senza errori. Coprono formato, decodifica, conversioni, celle, trasporto, riconciliazione sicura dei job e preview, senza nuove richieste ADS. Il prossimo passo significativo è una verifica su **più corse e osservazioni indipendenti**, seguita dalla misura nel servizio scelto. Nessun monitor o job ricorrente è stato creato. CAMS non colma le lacune già identificate nel contratto ICON: probabilità di precipitazione, visibilità e previsioni meteo a cinque giorni.
