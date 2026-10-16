# Pilota integrato locale — 3 settembre 2026

## Misura di ripetibilità ICON — 4 settembre 2026

Una seconda acquisizione completa e indipendente ha selezionato il run
`2026090400` e ha confermato lo stesso perimetro: 14 campi × 73 ore × 215 Comuni,
1.022 messaggi GRIB unici e nessun duplicato. Sono stati trasferiti
1.093.589.616 byte in 116,590 s; decodifica 9,857 s, elaborazione 2,431 s,
totale 136,894 s e picco working set 220.016.640 byte (circa 210 MiB).

Il payload verificato misura 26.640.155 byte, copre 48 ore future utili ed è stato
servito nel contratto locale a tutti i 215 Comuni. Quattro lievi casi `Td > T`
(Enemonzo, Preone e due ore di Forni Avoltri) sono rimasti esplicitamente null con
flag, senza correzioni o valori inventati. Lo smoke test end-to-end di tutti i
Comuni ha superato hash, manifest, 73 campioni e 36 aggregati bi-orari.

Questa seconda misura conferma che il costo dominante è il download nazionale;
decodifica e formule locali sono una quota secondaria. Non è ancora una misura di
costo Cloud Run né una validazione dell'accuratezza meteorologica.

Aggiornamento successivo: dopo registrazione e accettazione personale della
licenza, anche il test CAMS diretto per Pordenone è riuscito. Esito e misure in
[CAMS_PORDENONE_PILOT_2026-09-03.md](CAMS_PORDENONE_PILOT_2026-09-03.md).
Le indicazioni CAMS "bloccato" qui sotto descrivono lo stato della prima prova
ICON, non lo stato attuale. Gli artefatti di quella prova restano immutati.

L'estensione successiva CAMS copre ora tutti i 215 Comuni: 28 variabili,
97 istanti e 90 celle native, con dati e misure nel
[rapporto FVG](CAMS_FVG_PILOT_2026-09-03.md). Il pilota ICON originale non è
stato riscaricato o riscritto; la preview affianca i due snapshot separati.

## Esito e perimetro

Acquisizione ICON-2I → estrazione per 215 Comuni → elaborazioni → JSON →
preview diagnostica locale eseguita realmente in un unico processo. Non è una
migrazione dell'app, una validazione dell'accuratezza meteorologica o una misura
della bolletta cloud. CAMS non è stato scaricato: l'utente ha confermato di non
avere ancora account ADS e licenza del dataset accettata.

Nessuna modifica in questo turno a provider/cache dell'app, bollettino ufficiale
OSMER, allerte, job, Scheduler, Firebase o Cloudflare. Nessun commit, push o deploy.
Le modifiche locali preesistenti, comprese Scopri e hero, sono state preservate.

Il 3 settembre l'utente ha inoltre chiesto di acquisire tutti i parametri CAMS
possibili prima di decidere cosa visualizzare. Perimetro concordato: tutte le
variabili a superficie del dataset europeo, ensemble, solo FVG, fino a 96 ore;
non tutti i prodotti globali CAMS, livelli verticali e singoli modelli.

## Misura live riproducibile

Il report completo è `experiments/weather_autonomy/icon2i_integrated_report_20260903.json`.
La corsa pubblica più recente all'avvio era **2026090300**. Fine acquisizione e
generazione dati il 3 settembre, circa **14:00 UTC / 16:00 Europe/Rome**.

| Voce | Misura |
| --- | ---: |
| Comuni | 215 |
| Campi scaricati | 14 |
| Istanti nativi per campo | 73, lead 0…72 |
| Ore-punto Comune | 15.695 |
| Messaggi GRIB decodificati | 1.022 |
| Decodifiche duplicate | 0 |
| Costruzioni della mappa cella/Comune | 1 |
| Download, inclusi indici del processo integrato | 1.093.589.616 byte |
| GET del processo integrato | 29 |
| Tempo rete | 127,699 s |
| Decodifica, validazione metadati ed estrazione | 8,935 s |
| Elaborazioni e controlli snapshot | 1,973 s |
| Totale incluso JSON, compressione di misura e scrittura artefatti | 144,628 s |
| Picco working set prima della serializzazione | 145.752.064 byte |
| Picco working set finale del processo | 221.990.912 byte, circa 212 MiB |
| Snapshot sorgente estratto | 3.385.337 byte |
| JSON diagnostico, 215 Comuni / 73 istanti / dettagli qualità | 24.794.614 byte |
| Lo stesso JSON con gzip livello 6 | 1.474.524 byte |
| Un Comune, stesso formato diagnostico completo | 118.487–135.206 byte |
| Un Comune diagnostico compresso | 9.736–11.586 byte |

I tempi rete escludono le pause locali di decodifica ma includono connessione e
attesa dei body HTTP. Non misurano una coda di estrazione geografica. Il totale
esclude il salvataggio finale del report, le verifiche/browser e i controlli
pubblici preliminari svolti in processi separati. Il picco RAM è il working set
Windows dell'intero processo, librerie native incluse: non è una misura Linux o
Cloud Run né una garanzia che un container da 512 MiB basti in produzione.

Non confrontare direttamente questi 1,09 GB / 145 secondi con i 455 MB / 62
secondi di ieri: ieri erano 8 campi e 49 istanti, oggi 14 campi e l'intera corsa.

## Download e controlli

Il nuovo `run_pilot.py` legge esplicitamente i file delle variabili selezionate
con HTTP 200 e streaming limitato a blocchi di 64 KiB. Non è un fallback da Range
fallito, e non è un ritaglio FVG lato server: ogni messaggio contiene il dominio
nazionale. Limite totale 1.250 MiB, per file 100 MiB, per messaggio 4 MiB.
Redirect, lunghezze mancanti/incoerenti, messaggi extra o troncati sono rifiutati.
Nessun file GRIB nazionale viene conservato su disco o accumulato interamente in
RAM. Lo snapshot salva solo valori estratti e metadati.

Campi: T_2M, TD_2M, U_10M, V_10M, CLCT, PMSL, TOT_PREC, WW, VMAX_10M,
RAIN_CON, RAIN_GSP, SNOW_CON, SNOW_GSP, GRAU_GSP.

Griglia verificata: regular_ll 761 × 761, hash
`79cbd14686b4b38355cc0d1cc29e4580`. Ogni campo/ora viene validato per identità,
livello, unità, corsa e istante/periodo; la mappa degli indici viene riusata solo
con lo stesso hash di griglia. Nessuna interpolazione, correzione di quota o
costa. Coordinate dal catalogo locale, originariamente geocodificato tramite
Open-Meteo: nessuna nuova chiamata Open-Meteo e provenienza non cancellata.

Il campo SNOW_CON è costante zero per questa corsa: 15.330 byte per tutte le 73
scadenze, non 84 MB. Il parser non assume una dimensione fissa dei messaggi.

## Semantica e qualità, senza riempimenti fittizi

- Pressione: solo PMSL / 100, mai pressione di stazione.
- Umidità: approssimazione Magnus da T2m/Td2m, non RH a 1000 hPa; input incoerenti
  danno null, senza clipping nascosto.
- Percepita principale: Steadman/BOM all'ombra, vento a 10 m; Heat Index e Wind
  Chill sono confronti distinti, non uno switch o blending non validato.
- WW: interpretazione della tabella DWD ICON del tempo significativo dell'ora
  precedente. Codici ignoti restano ignoti. Il 96 include grandine **oppure**
  temporale forte; il 99 non viene assunto valido per ICON-2I.
- VMAX_10M: massimo della precedente ora, verificato su tutte le scadenze. Lead
  zero non viene presentato come raffica di un'ora precedente osservata.
- Accumuli: differenze della stessa corsa. In `grid_simple`, il quantum è la
  spaziatura della griglia codificata, non una barra d'errore certificata dal
  formato. Accumuli decodificati identici producono quindi `0 mm`; un cambio
  positivo o negativo nonzero entro `q_precedente + q_attuale` resta invece
  null e viene qualificato, senza trasformarlo in pioggia o asciutto.
- I minuscoli `referenceValue` positivi del run 2026090400 sono stati verificati
  come code-0: al massimo `1,184e-21 mm`, meno dello 0,006 dell'ULP di un quantum
  da `0,0009765625 mm`. Solo quando `reference + quantum == quantum` in binary64
  quel fondo viene normalizzato esplicitamente a zero. Il raw signed resta
  conservato e la normalizzazione è marcata
  `valid_reference_floor_normalized`.
- Costanti GRIB `bitsPerValue=0`: il reference porta il valore costante e il
  quantum effettivo è zero; il valore deve coincidere con quel reference.
- RAIN_CON/GSP: il descrittore ecCodes conserva unità da flusso, ma stepType=accum
  e manuale DWD indicano valori già accumulati. **Nessuna moltiplicazione per 3600**.
- Neve/graupel: equivalente d'acqua in mm, non centimetri di neve al suolo.
- Vista 2h: somma delle due precipitazioni, massimo delle due raffiche massime
  orarie, min/max dei due campioni termici e valore finale; non una riga sì/no.

Risultato qualità live: 211 intervalli TOT_PREC e 211 RAIN_GSP sotto risoluzione;
7.791 SNOW_GSP e 9.015 GRAU_GSP sotto risoluzione. Questi ultimi includono tracce
numeriche estremamente piccole e NON dimostrano neve o grandine reale. Nessuna
anomalia WW o T/Td segnalata in questa corsa. Le assenze di intervallo precedente
al lead zero sono intenzionali (215 per campo), non buchi delle ore future.

La policy quantitativa va ancora validata per l'uso operativo; `0 mm` significa
nessun incremento risolto nel prodotto decodificato, non una promessa di assenza
fisica assoluta di precipitazione.

### Replay precipitazione del run 2026090400 (4 settembre)

Il replay offline usa lo snapshot immutato con SHA-256
`ab839b5b7ff35712d8436b9f25c8f8c2962ec99d6a207ff5cd58a01c5bfe4199`;
non ha riscaricato GRIB e non ha sovrascritto gli artefatti originari.

- `precipitation_previous_hour_mm`: da 461/15.695 valori noti a 15.471/15.695;
  restano null i 215 lead zero e 9 incrementi positivi nonzero entro la
  risoluzione combinata. I 31 incrementi positivi già quantificabili restano 31.
- Zeri numerici: da 430 a 15.440. Di questi, 5.397 derivano esclusivamente dalla
  normalizzazione tracciata del reference floor code-0; 9.613 erano coppie
  identiche nonzero erroneamente annullate dalla vecchia policy.
- Vista a due ore: da 219/7.740 a 7.731/7.740 intervalli noti; 9 restano nulli.
- Pordenone: da 2/73 a 72/73 valori orari noti; il solo null restante è il lead
  zero, che non possiede un'ora precedente.

Nuovi artefatti, distinti dagli originali:

- `.dev-logs/weather-v1/icon_payload_precipitation_semantics_v3_20260904.json`
  (SHA-256 `9b9e18bc3613eed505180ce99af8fca723047d1956d817db79985ded4fe1a74e`);
- `.dev-logs/weather-v1/icon_report_precipitation_semantics_v3_20260904.json`
  (SHA-256 `6abcbf6fda33621f50dd1f114c6d92de362b119754bdd83954cca9dce6df8186`).

## Copertura e scadenza

Al momento della generazione: età corsa 14,006 ore, copertura futura 57,994 ore,
finestra 48h utilizzabile. Policy del laboratorio: recente fino a 18h, datato ma
utilizzabile dopo 18h solo se la finestra è completa, massimo assoluto 30h.
Queste soglie sono scelte del pilota, non uno SLA di ItaliaMeteo.

Simulazioni offline sulla stessa corsa:

| Età corsa | Copertura restante | Stato |
| --- | --- | --- |
| 18h | 54h | fresh |
| 24h | 48h | stale, utilizzabile con etichetta |
| 25h | 47h | expired, insufficiente per 48h |
| 31h | 41h | expired |

La preview rivaluta età/copertura col proprio orologio ogni minuto. Non continua
a mostrare un badge verde congelato. Non esiste ancora un job periodico che
scarichi nuove corse o una cache distribuita di produzione: gli artefatti sono
immutabili e un errore non sovrascrive un precedente risultato valido.

## Artefatti, ripresa e preview

- `icon2i_integrated_report_20260903.json`: misure live, hash, metadati estremi,
  lacune e simulazioni.
- `icon2i_integrated_source_20260903.zip`: archivio dei soli punti/metadati
  estratti, 661.413 byte; contiene `source.json`, nessun GRIB nazionale.
- `icon2i_integrated_payload_20260903.zip`: conserva `pilot.json` diagnostico
  originale per consultazione e profiling offline anche dopo la scadenza.
- SHA256 source.json:
  `d23fc8165f330f8a05db2e556337144b58d8f44f01618639ceb4ad94f32b9187`.
- SHA256 payload diagnostico originale:
  `f14d7c1e19f887dcb2adca6fbfd852afac4031d48616aad192824d6bdf2fc8de`.
- SHA256 archivio:
  `0f654807cf00f451cd776b390cd0935d01530e201ece11e35f2a1db45309e135`.

I tre file completi originali source.json/pilot.json/report.json sono anche nella
directory temporanea locale non versionata usata per la misura.
Per riprendere senza rete, estrarre l'archivio in una nuova cartella temporanea e
usare `run_pilot.py --replay source.json --payload nuovo-pilot.json --report nuovo-report.json`.
Il replay è etichettato come tale, rivaluta la scadenza e non è una nuova misura
live. Gli output esistenti non vengono sovrascritti.

Runtime isolato già installato in un ambiente virtuale Python locale non versionato.
Dipendenze: requests, eccodes e numpy; nessuna modifica alle dipendenze app.

Preview: `serve_pilot.py --payload <pilot.json> --port 8767`, solo
`http://127.0.0.1:8767/`. Solo GET / e /pilot.json, nessun elenco directory, nessun
CORS o accesso esterno, nessun provider live. Il pulsante rilegge il file locale,
non scarica una nuova corsa. L'app sul 5173 è separata. Il server locale richiede
il PC acceso ma non è necessario lasciarlo acceso per conservare gli artefatti.

## CAMS, pubblicità e prossimi limiti da risolvere

Il dataset `cams-europe-air-quality-forecasts` include 6 pollini e 22 componenti
aria (28 variabili nel form verificato il 3 settembre), forecast ensemble a
superficie, passi orari 0…96. Il piano preparato usa area N/W/S/E
46.7 / 12.2 / 45.5 / 14.0. L'accesso numerico resta bloccato fino a registrazione
ADS, accettazione personale delle condizioni e token configurato localmente.
Nessuna licenza è stata accettata e nessun account è stato creato dall'agente.

Piano completo salvato in `experiments/weather_autonomy/cams_request_plan_20260903.json`,
con identificatori API ufficiali, link a form/constraints, 28 variabili × 97
istanti = 2.716 campi in un gruppo compatibile. `cams_request_plan.py` stampa
soltanto un piano offline: non legge credenziali e non invia richieste di
estrazione. La compatibilità è verificata per la data 2026-09-03; per un'altra
corsa occorre rileggere disponibilità e vincoli, non cambiare solo la data.
Le 96h sono l'orizzonte dalla corsa, non una promessa di 96h future al momento
in cui si apre l'app. Nessuna misura di byte o coda è stata inventata dal numero
dei campi.

Il dataset espone licenza CC BY: uso commerciale compatibile rispettando termini,
attribuzione e indicazione delle elaborazioni. Questo non certifica automaticamente
le altre fonti dell'app né adempimenti pubblicitari/privacy. Il dataset segnala
inoltre che variabili diverse dagli inquinanti regolarmente validati sono
sperimentali: i pollini non vanno presentati come misure locali validate.

L'app attuale mostra “Pollini CAMS” ma chiama l'API air-quality di Open-Meteo
(`backend/app/weather/current_engine.py`, get_pollen_data). CAMS è la fonte a
monte, Open-Meteo l'intermediario. La dicitura completa sarebbe “CAMS tramite
Open-Meteo”; non è stato modificato il testo in questa prova. Finché si usa
l'API gratuita Open-Meteo restano i suoi vincoli non commerciali, anche se la
pubblicità è solo nelle pagine non meteo. Accesso diretto CAMS e licenza dati
sono distinti dal servizio ospitato Open-Meteo.

Lacune ancora esplicite, nessun fallback nascosto:

1. Acquisizione/decodifica numerica CAMS e misura di coda, dimensioni e ritardi.
2. Probabilità di precipitazione: non ricavabile come percentuale arbitraria da
   una corsa deterministica. Serve un prodotto appropriato o una scelta UI.
3. Visibilità: nessun campo disponibile nell'indice pubblico ICON verificato.
4. Cinque giorni numerici dell'app: oltre l'orizzonte nativo ICON di 72h; il
   bollettino testuale ufficiale OSMER resta separato e invariato.
5. Confronti su più corse con vere stazioni/quote/istanti e test affidabilità.
6. Ritaglio geografico MeteoHub lato server: non misurato senza accesso e
   postprocessore supportato; il campo area da solo non dimostra questa capacità.
7. Migrazione di tutti i consumatori (compresi avvisi meteo locali e geocoding),
   cache persistente, distribuzione e misura Cloud Run: non realizzate qui.

Sono state individuate coordinate ufficiali OSMER per un confronto privato, ma
non è stata eseguita una validazione. Gli XML osservativi avvertono di limiti
sulla ripubblicazione prima di 24h senza deroga: nessuna osservazione real-time
è stata inserita nella preview o negli artefatti distribuibili.

## Fonti primarie consultate

- [Indice pubblico ICON-2I della corsa](https://meteohub.agenziaitaliameteo.it/nwp/ICON-2I_SURFACE_PRESSURE_LEVELS/2026090300/).
- [Manuale DWD ICON, tabella 5.6 nota 5 e tabella 6.1](https://www.dwd.de/SharedDocs/downloads/DE/modelldokumentationen/nwv/icon/icon_dbbeschr_aktuell.pdf?nn=344870&view=nasPublication).
- [ecCodes: accumuli negativi e quantizzazione](https://confluence.ecmwf.int/display/UDOC/Why%2Bare%2Bthere%2Bsometimes%2Bsmall%2Bnegative%2Bprecipitation%2Baccumulations%2B-%2BecCodes%2BGRIB%2BFAQ).
- [Dataset CAMS europeo](https://ads.atmosphere.copernicus.eu/datasets/cams-europe-air-quality-forecasts?tab=overview).
- [Accesso ADS e accettazione personale dei termini](https://ads.atmosphere.copernicus.eu/how-to-api).
- [Licenza CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
- [Termini Open-Meteo](https://open-meteo.com/en/terms).
- [Anagrafe ufficiale stazioni OSMER](https://www.meteo.fvg.it/ajax/stationList.php?imgReq=1).

## Verifiche

Il controllo offline comprende test di framing HTTP/GRIB, metadati e periodi,
quantizzazione, finestra temporale, trasformazione sintetica 215×73, decoder
senza doppioni, output no-clobber e server locale. Test della preview eseguono
anche il JavaScript reale per scadenza, null e aggregati. Esito finale:
**327 test offline superati**, `git diff --check` pulito. Inclusi 61 test del
processo integrato, 34 del server/preview, 10 del profiling e 20 del piano CAMS.
Verificati anche lunghezza e SHA256 dei due JSON dentro gli archivi: identici
agli originali misurati. Il profilo di trasporto compattato è nell'appendice.

QA browser reale: Pordenone, Tarvisio e Trieste, passaggio 1h/2h (48 righe orarie
o 24 aggregati nella finestra visualizzata), valori reali, campi mancanti
espliciti; nessun errore console durante i controlli. Nessuna suite Scopri o build
Web già conclusa è stata rifatta per questa prova isolata.

## Appendice — proposta di trasporto, profilata offline

`profile_pilot_delivery.py` ha compattato il payload originale, senza rete né
nuova decodifica. La misura è separata dai 144,628 secondi del processo integrato.
Il candidato non è un endpoint di produzione o il contratto attuale dell'app.

Mantiene current delle 14 UTC e 49 istanti futuri: 3 settembre 15 UTC → 5
settembre 15 UTC, copertura 48,994 ore dalla generazione. Il punto oltre la fine
stretta delle 48h permette di coprire l'intero orizzonte. Null, condizioni WW,
componenti di precipitazione, incertezza di codifica e flag restano presenti.
Gli accumuli grezzi e gli incrementi firmati rimangono negli archivi diagnostici.

| Proposta di trasporto | JSON compatto | gzip livello 6 |
| --- | ---: | ---: |
| Tutti i 215 Comuni | 4.082.151 byte | 544.152 byte |
| Un singolo Comune, minimo | 23.081 byte | 5.294 byte |
| Un singolo Comune, massimo | 31.299 byte | 6.155 byte |

Questo non significa che oggi il telefono scarichi tale formato: la preview
legge il JSON diagnostico completo, mentre il candidato misura un possibile
formato di distribuzione per Comune. Nessun overhead HTTP o carico multiutente
è incluso. Le due ore vengono aggregate davvero; l'ultima ora spaiata è
esplicitamente incompleta. Non viene scartata per far sembrare completo il dato.

Report: `experiments/weather_autonomy/icon2i_delivery_report_20260903.json`.
Artefatto candidato temporaneo: `delivery-candidate-v2.json` nella cartella del
test. SHA256:
`e69defd20179c8fb6d01ed2b19d3df9ea823f7e5270b6b703bb1d3a6dc429907`.
La prima versione del solo profiling (senza suffisso v2) è superata: conservava
nel riepilogo la copertura nativa invece di quella ridotta. Nessun file live
integrato è stato riscritto e nessun nuovo download è stato eseguito per correggerla.
