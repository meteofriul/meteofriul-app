# Prova indipendenza da Open-Meteo — 2 settembre 2026

## Esito e perimetro

Esito positivo per un **benchmark tecnico ICON-2I di 48 ore su 215 Comuni**,
non per una migrazione: accesso anonimo, decodifica GRIB, estrazione puntuale
e calcolo locale della temperatura apparente funzionano senza chiamare
Open-Meteo. Dopo il campione iniziale di tre località, la prova completa
ha elaborato 10.535 righe in 61,55 secondi e prodotto 881.738 byte di JSON.
Sono segnalati 25 incrementi pioggia negativi, non trasformati in zero.
Non sono dimostrate accuratezza, continuità operativa o gratuità permanente
dell'infrastruttura. CAMS è verificato a livello documentale/catalogo, non
ancora con un download numerico autenticato.

Tutto il codice nuovo è confinato in `experiments/weather_autonomy/`.
Nessun collegamento al backend/frontend, nessuna modifica della hero, del
bollettino OSMER o delle allerte. Lavoro Scopri e modifiche precedenti
preservati. Nessun account creato, licenza accettata per conto dell'utente,
job pianificato, commit, push o deploy.

## Evidenza ICON reale — campione iniziale

- Acquisizione finale: **2026-09-02 20:17:23 UTC**.
- Corsa: **2026-09-02 12:00 UTC**, scadenze **+9, +33, +57 ore**.
- Validità: 2, 3 e 4 settembre alle 21:00 UTC, ossia **23:00 CEST**.
- 8 campi × 3 scadenze = 24 messaggi GRIB; tre punti per messaggio.
- Trasferimento dell'esecuzione riuscita: **27.806.817 byte**, 42 GET,
  **8,13 secondi** sulla connessione di prova. Non è un benchmark/SLA;
  non include installazione dipendenze e tentativi preliminari.
- GRIB `regular_ll`: **761 × 761**, 579.121 punti;
  incremento longitudine 0,025°, latitudine 0,02°.
- Distanza cella più vicina: Pordenone **0,883 km**, Trieste **1,066 km**,
  Tarvisio **0,725 km**. Nessuna interpolazione, maschera terra/mare o
  correzione altimetrica: soprattutto costa e valli richiedono validazione.

Campione del **2 settembre, ore 23:00 CEST** — previsioni, non osservazioni:

| Località | T aria °C | RH derivata % | Vento m/s | MSLP hPa | AT ombra °C |
| --- | ---: | ---: | ---: | ---: | ---: |
| Pordenone | 23,17 | 57,58 | 6,51 | 1018,06 | 20,00 |
| Trieste | 24,77 | 51,94 | 1,56 | 1017,22 | 25,02 |
| Tarvisio | 14,85 | 83,72 | 1,12 | 1022,60 | 14,73 |

L'evidenza completa, con URL originali, metadati e valori anche delle altre
scadenze, è in `experiments/weather_autonomy/icon2i_sample_20260902.json`.
Gli URL del fornitore hanno conservazione limitata: il risultato salvato
documenta questa prova, non garantisce che la corsa resti scaricabile.
SHA-256 del JSON conservato:
`4ad2a0dc189e053f0eeb213bf6c6c6a3a8aaa1d5154d946cbecf9eebd6d3887b`.

| Campo pubblico | Identità ecCodes verificata | Utilizzo / cautela |
| --- | --- | --- |
| T_2M | 2t, 167, 2 m, K | T aria; conversione K → °C |
| TD_2M | 2d, 168, 2 m, K | Punto di rugiada per derivare RH |
| U_10M / V_10M | 10u / 10v, 165 / 166, m/s | Modulo e direzione; componenti earth-relative verificate |
| CLCT | clct, 500046, % | Copertura nuvolosa totale |
| PMSL | pmsl, 500002, Pa | Pressione al livello del mare; Pa → hPa |
| TOT_PREC | tp, 228228, kg/m² | Accumulo dal run, non precipitazione oraria |
| WW | ww, 500292 | Codice meteo grezzo; mappatura icone ancora da verificare |

L'indice pubblico `RELHUM` della corsa contiene solo livelli isobarici,
non RH a due metri: **RH a 1000 hPa non è intercambiabile con RH2m**.
Il prototipo usa il rapporto tra le pressioni di saturazione a Td2m e T2m,
con la stessa approssimazione Magnus sopra acqua della formula BOM.
Questa derivazione non pretende di invertire esattamente lo schema fisico
ICON, in particolare sottozero. Td > T viene rifiutata, senza clipping.

Il lettore richiede HTTP 206 e Content-Range coerente; rifiuta redirect e
fallback al file intero. Budget 40 MiB controllato per chunk (non un limite
al singolo byte sul traffico di rete). Il campionamento usa messaggi di
dimensione costante, salvo il primo accumulo pioggia nullo molto corto;
verifica identità, unità, livello, run, scadenza e coerenza delle celle.
Un diverso impacchettamento provoca arresto, non download indiscriminato.
**Tre scadenze non dimostrano la continuità di tutte le ore intermedie.**

## Correzioni alla proposta

### Dati aperti, non autonomia assoluta

Il catalogo ItaliaMeteo descrive ICON-2I deterministico a risoluzione nominale
2,2 km, due corse 00/12 UTC e orizzonte +72 ore. Il prodotto pubblico
campionato è una griglia lat/lon regolare. La risoluzione non dimostra da
sola maggiore accuratezza su una singola valle. L'app dipenderebbe ancora
dalla disponibilità dei produttori istituzionali. [Catalogo modello](https://dati.agenziaitaliameteo.it/dataset/previsioni-meteorologiche-modello-icon-2i),
[licenze ItaliaMeteo](https://meteohub.agenziaitaliameteo.it/app/license).

ICON-2I è indicato CC BY 4.0, attribuzione Agenzia ItaliaMeteo in cooperazione
con Arpae Emilia-Romagna Idro-Meteo-Clima. La licenza ammette uso commerciale
con attribuzione, link alla licenza e indicazione delle elaborazioni: non
equivale a disponibilità garantita o assenza di ogni altro adempimento.
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

MeteoHub offre attualmente accesso gratuito soggetto a fair use/risorse.
Download anonimo e richieste di estrazione autenticate sono percorsi distinti;
queste ultime sono asincrone. Il test non ha creato richieste o account.
[Guida ufficiale](https://meteohub.agenziaitaliameteo.it/ui/user-guide).

### Percepita e presentazione a due ore

La formula proposta è la temperatura apparente BOM/Steadman in ombra,
senza contributo della radiazione solare, con vento a 10 m in m/s.
È una stima modellistica, non una temperatura misurata o un'allerta sanitaria.
Il prototipo conserva **AT, Heat Index e Wind Chill separati**: niente switch
arbitrario della hero. HI usa screening NWS/Rothfusz e un inviluppo prudenziale
documentato; WC richiede T ≤10 °C e vento >3 mph.
[BOM](https://www.bom.gov.au/info/thermal_stress/),
[NWS Heat Index](https://www.wpc.ncep.noaa.gov/html/heatindex_equation.shtml),
[NWS Wind Chill](https://www.weather.gov/safety/cold-wind-chill-chart).

Mostrare un punto ogni due ore è sensato per la leggibilità, ma manterrei
l'orario a monte: accumuli pioggia vanno differenziati entro la stessa corsa,
poi aggregati per intervallo; raffiche, estremi e cambi di fenomeno non vanno
eliminati scegliendo semplicemente una riga sì e una no. La previsione
deterministica della pioggia non dà da sola una probabilità calibrata.
MSLP è adatta alla card comparabile costa/montagna, non sostituisce la
pressione locale nelle eventuali conversioni che richiedono quest'ultima.

### CAMS e pollini

Dataset candidato: `cams-europe-air-quality-forecasts`, ENSEMBLE al suolo.
Copertura oraria, **96 ore**, griglia **0,1° (~10 km)**, aggiornamento giornaliero,
formati GRIB/NetCDF. Sei pollini: ontano, betulla, graminacee, artemisia, olivo,
ambrosia. Non copre tutte le famiglie locali; i pollini non hanno la stessa
validazione regolare degli inquinanti principali.
[Catalogo CAMS](https://ads.atmosphere.copernicus.eu/datasets/cams-europe-air-quality-forecasts?tab=overview).

Il catalogo JSON pubblico è stato interrogato realmente senza credenziali:
`license: CC-BY-4.0`, non la generica etichetta «EU Open Data».
Prima della pubblicazione conservare DOI 10.24381/a4005cee, attribuzioni
Copernicus/produttori, indicazione di elaborazione e disclaimer richiesti
nella sezione Citation and attribution.
[Metadati ufficiali](https://ads.atmosphere.copernicus.eu/api/catalogue/v1/collections/cams-europe-air-quality-forecasts).

**Non è stata provata l'acquisizione numerica CAMS.** Occorrono account ADS,
token e accettazione della licenza da parte dell'utente. Il recupero prepara
file e può accodarsi, non è un'API puntuale JSON per ogni telefono.
[Accesso API](https://ads.atmosphere.copernicus.eu/how-to-api).
L'accesso alternativo HTTPS/SFTP operativo richiede abilitazione;
non costituisce una scorciatoia anonima.
[Procedura ECMWF](https://confluence.ecmwf.int/spaces/CKB/pages/599163953/SFTP%2Band%2BHTTPS%2Baccess%2Bto%2BCAMS%2BEuropean%2Bair%2Bquality%2Bforecast%2Bdata).

Per l'aggiunta dei pollini ARPA FVG serve chiarimento: le note legali indicano
CC BY 4.0 ma aggiungono condizioni non-commerciale/share-alike incompatibili
con quella denominazione. Inoltre la rete consultata segnala indisponibilità
delle rilevazioni. Non estendere automaticamente ai pollini le condizioni
di altri dataset meteo; attendere condizioni specifiche inequivoche.
[Note legali ARPA](https://www.arpa.fvg.it/link-footer/link-in-basso-cookie-privacy/note-legali/),
[rete pollini](https://www.arpa.fvg.it/temi/temi/pollini/sezioni-principali/rete-regionale-pollini/).
Questo rilievo non modifica i flussi OSMER/allerte già presenti nell'app.

## Costi e passo successivo proposto

La somma degli otto file completi osservati è **675.365.462 byte per corsa**.
Scenario volutamente non ottimizzato: due download completi al giorno,
30 giorni, **circa 40,5 GB/mese**, esclusi altri campi e CAMS. È un calcolo
di traffico, non un costo in euro o traffico imposto a ciascun utente.

Proposta da validare: acquisizione centralizzata una volta per nuova corsa,
estrazione FVG/comuni, pubblicazione di JSON compatti e cache condivisa.
Non scaricare GRIB sui telefoni né rilanciare l'acquisizione per ogni visita.
Ritagli a monte possono ridurre il trasferimento, ma accesso, limiti e tempi
di quel percorso non sono ancora misurati. Visualizzare metà delle ore non
dimezza automaticamente il lavoro del server o i costi di acquisizione.

Prima di sostituire Open-Meteo:

1. Produrre una serie oraria continua di 48 ore da adesso, con pioggia per
   intervallo, codici meteo verificati, altimetria e maschera costa.
2. Confrontare più corse con osservazioni OSMER appropriate per località,
   altezza e validità; misurare errori, ritardi e mancanze. Un confronto col
   solo Open-Meteo non è validazione contro la realtà.
3. Provare CAMS con account/consensi predisposti dall'utente, poi misurare
   download, conversione, memoria, traffico e cache sull'hosting scelto.
4. Prevedere fallback all'ultima corsa valida, età visibile e scadenza
   massima; non presentare come attuale una previsione scaduta.

Non è stato attivato alcun monitoraggio automatico. La formula corretta per
ora è **«indipendente da Open-Meteo, con dati aperti e costi da misurare»**,
non «interamente autonomo e sicuramente senza spese».

## Riproduzione della prova

Verifica del campione iniziale: **48/48 test offline superati** (18 probe, 30 termici),
JSON dell'evidenza valido e `git diff --check` verde. I test del lettore
usano stub per i casi di errore; la decodifica reale è documentata dal
campione live, non simulata dagli stub. Nessuna suite Scopri ripetuta.

Test offline, dalla radice del repository, senza dipendenze applicative:

```powershell
python -B -m unittest discover -s experiments/weather_autonomy -p 'test_*.py' -v
```

Probe live: Python 3.13 con `eccodes==2.48.0` e `requests==2.34.2`, installati
soltanto nell'ambiente temporaneo isolato
`%TEMP%/meteofriul-weather-autonomy-20260902/venv`.
La distribuzione Python ufficiale ECMWF include i binari Windows;
nessuna dipendenza del progetto è stata cambiata.
[Installazione ECMWF](https://github.com/ecmwf/eccodes-python).

```powershell
& (Join-Path $env:TEMP 'meteofriul-weather-autonomy-20260902/venv/Scripts/python.exe') experiments/weather_autonomy/probe_icon2i.py
```

Senza `--run` il programma sceglie l'ultima corsa pubblicata; `--output`
accetta solo un percorso nuovo e non sovrascrive file. I test offline non
eseguono download. L'evidenza JSON salvata resta un campione datato.

## Benchmark orario completo autorizzato — 2 settembre, ore 22:54 CEST

Script: `experiments/weather_autonomy/benchmark_icon2i.py`.
Acquisizione: `2026-09-02T20:54:20.755194+00:00`, corsa `2026090212`.
Gli otto campi sono gli stessi del campione iniziale: **49 istanti orari**
da +9 a +57, dal 2 settembre alle 21 UTC al 4 settembre alle 21 UTC.
La pioggia aggiunge l'accumulo +8 per ottenere anche il primo intervallo
orario: **393 messaggi unici**, non 393 file completi.

| Misura locale effettiva | Risultato |
| --- | ---: |
| Comuni × istanti | 215 × 49 = 10.535 |
| Corpi HTTP scaricati, inclusi indici/header GRIB | 455.267.877 byte (455,27 MB) |
| GET, nessun retry | 74 |
| Rete, comprese connessione/risposta/lettura | 56,568 s |
| Apertura GRIB, verifiche, decodifica/estrazione | 3,355 s |
| Di cui mappatura celle, effettuata una sola volta | 0,027 s |
| Conversioni, RH, vento, pioggia, indici termici | 0,437 s |
| Serializzazione JSON aggregato | 0,037 s |
| Compressione gzip aggregato, livello 6 | 0,075 s |
| Totale fino ai risultati in memoria | 61,555 s |
| Picco residente dell'intero processo Windows | 97.964.032 byte (97,96 MB; 93,43 MiB) |
| JSON aggregato, tutti i 215 Comuni | 881.738 byte |
| Stesso JSON compresso gzip | 290.309 byte |
| JSON autonomo di un Comune, metadati inclusi | 6.686–6.831 byte |
| Stesso JSON per Comune, gzip | 2.490–2.655 byte |

È una sola esecuzione su questo PC/connessione, non una misura Cloud Run,
un preventivo in euro o una distribuzione statistica. Il totale include
anche import, hashing, orchestrazione e misura dei JSON per Comune; esclude
la scrittura finale dei file. La voce gzip riguarda il solo JSON aggregato.
I byte sono corpi HTTP letti, non conteggio TCP/TLS/header o traffico fatturato.
Il picco è `PeakWorkingSetSize` Windows lungo la vita del processo, incluse
le librerie native residenti: non solo heap Python, non memoria impegnata
totale e non una promessa di identico fabbisogno su Linux/cloud.

### Metodo e tracciabilità

- Coordinate lette dal catalogo canonico `backend/app/data/fvg_municipalities.json`:
  215 record unici, corrispondenza con i 215 profili Scopri. Sono punti
  convenzionali dei Comuni, non stazioni né copertura di ogni punto GPS.
  La loro origine è geocoding Open-Meteo già storicizzato: nessuna chiamata
  al servizio durante questa prova, ma tale provenienza resta dichiarata.
- Richieste HTTP Range da massimo otto messaggi contigui; budget 550 MiB,
  risposta 206 obbligatoria, nessun fallback al file intero o retry.
  Nessun GRIB salvato su disco, nessun GRIB inviato a Firebase o ai telefoni.
- Stessa corsa, identità/altezza/unità, validità UTC, processing temporale
  e griglia controllati per ogni messaggio. Vento earth-relative verificato.
- Indici delle celle calcolati una volta e riusati solo con identico
  `md5GridSection`; zero decodifiche duplicate nella prova completa.
  Le celle non sono interpolate o corrette per quota/costa.
- Pioggia per `(timestamp−1h, timestamp]`, da differenza di accumuli della
  stessa corsa; AT in ombra, Heat Index e Wind Chill rimangono separati.
  I null degli indici non applicabili sono distinti dai `quality_flags`.
  Nessuna vista bioraria distruttiva né mappatura icone introdotta.

Evidenze conservate nel repository:

- `experiments/weather_autonomy/icon2i_hourly_report_20260902.json`:
  metadati, URL, SHA-256 dei range acquisiti per campo, tempi e pesi di
  ciascuno dei 215 JSON per Comune.
- `experiments/weather_autonomy/icon2i_hourly_evidence_20260902.json`:
  estratto delle 49 ore per Ampezzo, Tarvisio, Trieste e Pordenone,
  incluse le segnalazioni di qualità. Non è spacciato per l'intero payload.
- JSON completo generato, **non versionato**, nella directory temporanea
  `%TEMP%/meteofriul-weather-autonomy-20260902/icon2i_hourly_payload_20260902.json`.
  SHA-256: `dc771d8c800eb6326bbaeb6277986799112dd013a6656bd5c0ec3de25553e0e7`.

### Cosa questa prova non conclude

Audit mirato dei **25 incrementi pioggia segnalati**: tutti appartengono
all'intervallo +25→+26 della stessa corsa, cioè 3 settembre 13→14 UTC.
I due messaggi sono stati ricontrollati con un download separato di
**2.316.936 byte, 4 GET, 1,99 s**, escluso dai tempi/byte del benchmark sopra.
Tutti i decrementi sono esattamente **−0,001953125 mm**. Il packing è
`grid_simple`, 16 bit, riferimento zero e fattore decimale zero; il fattore
binario cambia −9→−8, raddoppiando il passo rappresentabile da
0,001953125 a 0,00390625 mm. Stessa griglia e tutti i 215 valori riproducono
la classificazione del payload originale, il cui SHA-256 è rimasto invariato.

È una forte **compatibilità con l'errore di quantizzazione GRIB**, non prova
causale assoluta senza i valori prima del packing. ECMWF documenta questo
meccanismo per gli accumuli e avverte che può produrre anche incrementi
positivi spuri molto piccoli: una futura politica deve considerare entrambi
i segni e la precisione del messaggio, non usare ciecamente `max(0, delta)`.
Le soglie illustrate per altri modelli/orizzonti non sono trasferite a ICON.
[FAQ ecCodes sugli accumuli negativi](https://confluence.ecmwf.int/display/UDOC/Why%2Bare%2Bthere%2Bsometimes%2Bsmall%2Bnegative%2Bprecipitation%2Baccumulations%2B-%2BecCodes%2BGRIB%2BFAQ).

Script e riscontro conservati in `experiments/weather_autonomy/`:
`audit_icon2i_rain.py` e `icon2i_rain_audit_20260902.json`. La prova mantiene
quei 25 valori come null con flag, senza correggere il payload a posteriori.

**48 ore fisse non bastano a garantire 48 ore scorrevoli tutto il giorno.**
Con acquisizione una volta per corsa, ogni circa 12 ore, servirebbe conservare
circa 60 ore future più un margine per ritardi, compatibilmente con le 72 ore
native del modello. Perciò 455 MB non è ancora il dimensionamento definitivo
di un servizio a due aggiornamenti giornalieri. Non abbiamo riscaricato dati
per estrapolare quel dimensionamento, né schedulato acquisizioni.

Il confronto con **ritaglio geografico lato server non è stato eseguito**:
la guida prevede estrazioni autenticate/asincrone e post-processing spaziale
dipendente dalla configurazione dell'account. Il filtro `area` e lo schema
generico `postprocessors` non provano un endpoint bbox ICON utilizzabile.
Attesa in coda, elaborazione e byte di questo percorso restano **non misurati**,
non zero. Ogni messaggio della prova diretta contiene ancora tutto il dominio.
[Guida MeteoHub](https://meteohub.agenziaitaliameteo.it/ui/user-guide),
[specifica API](https://meteohub.agenziaitaliameteo.it/api/specs).

Nessuna validazione contro osservazioni, confronto di più corse, gestione
operativa dei ritardi, raffiche o probabilità di pioggia. CAMS resta fuori da
questo benchmark. L'app continua a usare i suoi provider correnti.

### Pubblicità soltanto nelle pagine non meteo

Condizioni Open-Meteo verificate il 2 settembre 2026: il servizio API gratuito
è riservato all'uso non commerciale; gli esempi di uso commerciale includono
app e siti che mostrano pubblicità o vendono abbonamenti. Non è indicata
un'eccezione per annunci confinati a una sezione diversa dal meteo.
**Lettura prudenziale delle condizioni, non parere legale:** mettere annunci
soltanto in Scopri non è una base sufficiente per qualificare l'intera app
come non commerciale. Un'eventuale eccezione richiede conferma scritta del
fornitore. La licenza CC BY 4.0 dei dati, che ammette riuso commerciale con
attribuzione, è distinta dalle condizioni di accesso all'API ospitata.
[Termini Open-Meteo](https://open-meteo.com/en/terms),
[piani e licenza del servizio](https://open-meteo.com/en/pricing).

Nessuna pubblicità attivata, sottoscrizione acquistata o comunicazione inviata.

### Riproduzione del benchmark e verifica finale

**125 test offline superati**: 18 probe iniziale, 30 termici, 7 memoria,
70 benchmark (incluse risposte HTTP, indici/griglia, handle e campi mancanti).
JSON verificati e `git diff --check` verde. Nessuna suite Scopri o Web
già conclusa è stata ripetuta; nessuna dipendenza applicativa modificata.

Comando live, solo se si vuole una nuova acquisizione e usando due percorsi
di output nuovi in una directory già esistente (circa 455 MB nella corsa
misurata; nessuna sovrascrittura):

```powershell
& (Join-Path $env:TEMP 'meteofriul-weather-autonomy-20260902/venv/Scripts/python.exe') -B experiments/weather_autonomy/benchmark_icon2i.py --report "$env:TEMP/icon2i-new-report.json" --payload "$env:TEMP/icon2i-new-payload.json"
```

Senza `--run` viene scelta l'ultima corsa elencata; il test si ferma se non
copre la finestra richiesta. L'audit pioggia è deliberatamente specifico
della corsa `2026090212` e dei passi 25/26: non è un correttore generico.
Tutti gli script restano esterni all'app e non creano job o schedulazioni.
