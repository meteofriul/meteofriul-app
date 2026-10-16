# CAMS: capacità e limiti del pilota FVG

Verifica: 3 settembre 2026. Scopo: tutte le 28 variabili **ensemble, superficie, previsione** del dataset `cams-europe-air-quality-forecasts`, per i 215 Comuni del catalogo. Non comprende tutti i modelli individuali, livelli atmosferici o prodotti Copernicus. Questa matrice non certifica accuratezza locale, completamento dell'acquisizione regionale o costi cloud.

## Evidenza già disponibile

- Il report locale non versionato CAMS di Pordenone verifica 28 variabili × 97 istanti = 2.716 campi, senza duplicati, dalla corsa 03/09 ore 00 UTC al 07/09 ore 00 UTC. È una verifica tecnica di una località, non una validazione meteorologica regionale.
- Il report locale non versionato ICON integrato copre 215 Comuni × 73 istanti nativi. Il suo stato rimane `partial_pilot_not_production`.
- L'estensione CAMS è ora riuscita: 215 × 28 × 97 = **583.940 valori associati ai Comuni**, su 90 celle native, senza valori mancanti o invalidi nei punti estratti. Il [rapporto regionale](CAMS_FVG_PILOT_2026-09-03.md) separa acquisizione, decodifica e trasporto proposto. Più Comuni condividono la stessa cella: non sono 215 osservazioni indipendenti.

## Contratto del prodotto

Griglia 0,1° × 0,1°, frequenza oraria, aggiornamento giornaliero. `ensemble` è una mediana dei risultati dei modelli, non il pacchetto dei singoli membri. Scaricare la sola mediana non fornisce lo spread necessario per stimare l'incertezza tra modelli. [Scheda ADS](https://ads.atmosphere.copernicus.eu/datasets/cams-europe-air-quality-forecasts?tab=overview).

La corsa parte alle 00 UTC, con lead 0–96 inclusi: **97 istanti**, non 96 ore sempre future dall'apertura dell'app. La superficie rappresenta uno strato modellistico, non una stazione a 2 metri; il prodotto descrive lo sfondo regionale, non la singola strada. La guida indica disponibilità garantita entro le 08 UTC per 0–48 e le 10 UTC per 49–96. [Guida ECMWF, aggiornata 16/03/2026](https://confluence.ecmwf.int/spaces/CKB/pages/202173092/CAMS+Regional+European+air+quality+analysis+and+forecast+data+documentation).

La scheda ADS riporta invece 06:45/08:30 UTC: non equiparare questi orari nominali a garanzie. Proposta operativa: verificare corsa e completezza effettive, con tentativi limitati e ultima previsione valida esplicitamente datata; mai sostituire un ritardo con valori zero. [Orari nella scheda ADS](https://ads.atmosphere.copernicus.eu/datasets/cams-europe-air-quality-forecasts?tab=overview).

## Matrice delle 28 variabili

Gli identificatori sono quelli del [modulo ufficiale ADS verificato](https://object-store.os-api.cci2.ecmwf.int:443/cci2-prod-catalogue/resources/cams-europe-air-quality-forecasts/form_bb2d051a4d63bb141e88ce87298ccfa559411aa5107e8d846ff49af0546f6a89.json), non nomi API dedotti dalle traduzioni. I [vincoli del catalogo](https://object-store.os-api.cci2.ecmwf.int:443/cci2-prod-catalogue/resources/cams-europe-air-quality-forecasts/constraints_2ecf5587cbe8537f7a0179d9461bb95522b124e977c10fbab72518d40a2fd183.json) consentono questa selezione insieme per la corsa verificata.

Unità normalizzate: **P = granuli/m³**, **M = µg/m³**. Le 22 concentrazioni non polliniche sono documentate in kg/m³ nel GRIB e µg/m³ nel NetCDF; i sei pollini rimangono granuli/m³. Conversione soltanto dopo verifica dell'identità del parametro. [Unità ADS](https://ads.atmosphere.copernicus.eu/datasets/cams-europe-air-quality-forecasts?tab=overview).

**V/E è la classificazione dichiarata nella scheda ADS**, non un giudizio nostro: V = regolarmente validata contro osservazioni; E = sperimentale. La scheda elenca **7 V e 21 E**. L'asterisco segnala una discordanza documentale discussa sotto. La divisione in cinque inquinanti principali, pollini e componenti aggiuntivi segue la [presentazione CAMS](https://atmosphere.copernicus.eu/european-air-quality-forecast-plots).

| Gruppo | Identificatore ADS | Contenuto | Unità | Scheda ADS |
|---|---|---|---|---|
| Pollini (6) | `alder_pollen` | Ontano | P | E |
| Pollini | `birch_pollen` | Betulla | P | E |
| Pollini | `grass_pollen` | Graminacee | P | E |
| Pollini | `mugwort_pollen` | Artemisia | P | E |
| Pollini | `olive_pollen` | Olivo | P | E |
| Pollini | `ragweed_pollen` | Ambrosia | P | E |
| Principali (5) | `nitrogen_dioxide` | NO₂ | M | V |
| Principali | `ozone` | O₃ | M | V |
| Principali | `particulate_matter_10um` | PM10 | M | V |
| Principali | `particulate_matter_2.5um` | PM2.5 | M | V |
| Principali | `sulphur_dioxide` | SO₂ | M | V |
| Altri gas (7) | `ammonia` | Ammoniaca | M | E |
| Altri gas | `carbon_monoxide` | CO | M | E* |
| Altri gas | `formaldehyde` | Formaldeide | M | E |
| Altri gas | `glyoxal` | Gliossale | M | E |
| Altri gas | `nitrogen_monoxide` | NO | M | V* |
| Altri gas | `non_methane_vocs` | COV non metanici | M | E |
| Altri gas | `peroxyacyl_nitrates` | Nitrati di perossiacile | M | E |
| Aerosol/componenti (10) | `dust` | Polvere minerale nel PM10 | M | V* |
| Aerosol/componenti | `pm10_sea_salt_dry` | Sale marino secco nel PM10 | M | E |
| Aerosol/componenti | `pm10_wildfires` | Tracciante PM10 da incendi | M | E |
| Aerosol/componenti | `pm2.5_ammonium` | Ammonio nel PM2.5 | M | E |
| Aerosol/componenti | `pm2.5_nitrate` | Nitrato nel PM2.5 | M | E |
| Aerosol/componenti | `pm2.5_sulphate` | Solfato nel PM2.5 | M | E |
| Aerosol/componenti | `residential_elementary_carbon` | Carbonio elementare residenziale, PM2.5 | M | E |
| Aerosol/componenti | `total_elementary_carbon` | Carbonio elementare totale, PM2.5 | M | E |
| Aerosol/componenti | `secondary_inorganic_aerosol` | Aerosol inorganico secondario, PM2.5 | M | E |
| Aerosol/componenti | `pm2.5_total_organic_matter` | Materia organica totale, PM2.5 | M | E |

La guida ECMWF include **NO e dust fra gli sperimentali**, diversamente dalla scheda, e descrive la valutazione del CO. Riportare quindi 7/21 solo come classificazione della scheda: non promuovere NO/dust/CO a badge di affidabilità senza chiarimento. La stessa guida precisa: NMVOC espresso come massa di carbonio; alcuni modelli forniscono metilgliossale nel campo gliossale; `pm10_wildfires` è un tracciante aerosol primario non reattivo. [Dettagli e limitazioni ECMWF](https://confluence.ecmwf.int/spaces/CKB/pages/202173092/CAMS+Regional+European+air+quality+analysis+and+forecast+data+documentation).

## Analisi possibili: proposte, non funzionalità già certificate

| Analisi | Calcolo sensato | Condizione di accettazione |
|---|---|---|
| Controllo completo | Presenza di 28 × 97 campi, identità, unità, tempi, duplicati e finitezza; copertura dei 215 Comuni | Report per corsa, hash sorgente, valori mancanti separati dagli zeri |
| Situazione modellistica | Valore dell'ora scelta, età della corsa, ultimo istante futuro | Etichetta “previsto”, orario esplicito; nessuna finta osservazione in tempo reale |
| Andamento | Minimo, massimo, ora del picco e media per singola variabile in finestre di 6/12/24 ore | Campioni orari validi e finestra completa; distinguere giorno UTC e giorno locale |
| Vista bioraria | Media dei due campioni e massimo della finestra, entrambi etichettati | Conservare l'orario nativo; non eliminare il picco con un campione sì e uno no |
| Variazione | Differenza della stessa variabile fra ore o finestre confrontabili | Stessa unità e copertura; percentuali non definite con denominatore zero |
| Distribuzione regionale | Mappa per cella, intervallo e punti estremi | Deduplicare celle; media dei Comuni ≠ media territoriale o di esposizione della popolazione |
| Confronto tra corse | Cambiamento della previsione per identico luogo e ora valida | Archiviare almeno due corse; non confonderlo con spread dell'ensemble |
| Confronto con misure | Errori rispetto a stazioni rappresentative, per variabile e anticipo | Dati osservati indipendenti e confronto ripetuto: una corsa non misura l'affidabilità |

Regole interpretative proposte per evitare risultati apparentemente precisi ma impropri:

- Niente AQI inventato o somma degli inquinanti. Un eventuale indice richiede metodologia ufficiale identificata, unità, medie temporali, completezza e implementazione verificata separatamente. Questa matrice non assegna categorie sanitarie né soglie cliniche ai pollini.
- Le concentrazioni non sono accumuli: sommare 24 valori in µg/m³ non produce una “quantità giornaliera di inquinamento”. Le medie descritte sopra riassumono campioni modellistici, non dosi personali.
- Non sommare PM10, PM2.5 e loro componenti: esistono inclusioni e sovrapposizioni. Inoltre la somma delle mediane non coincide generalmente con la mediana della somma. Nessuna torta obbligata al 100% o percentuale corretta artificialmente per chiuderla.
- `pm10_wildfires` non identifica incendi attivi o la loro posizione: da una concentrazione prevista non si deduce “incendio nel Comune”. `dust` non certifica origine sahariana; serve evidenza ulteriore sulla provenienza.
- I sei pollini non rappresentano tutti gli allergeni. Un dato assente non è zero; un numero molto piccolo non certifica assenza di rischio. Conservare valore e qualità originali anche quando l'interfaccia arrotonda.
- Allineare orari e celle prima di affiancare ICON e CAMS. Una correlazione con vento/pioggia non dimostra causalità né rende CAMS più dettagliato della sua griglia.

## Cosa resta fuori dalla copertura meteo

Il pilota ICON dispone di temperatura, percepita derivata, umidità derivata, vento/raffiche, nuvolosità, codice del tempo, quantità/fasi delle precipitazioni e pressione al livello del mare; la [matrice locale ICON](../../experiments/weather_autonomy/icon_semantics.py) mantiene espliciti i parametri non disponibili.

**Probabilità di precipitazione, visibilità e previsione meteo a cinque giorni rimangono mancanti nel contratto corrente.** Le 28 variabili CAMS non colmano questi vuoti; 96 ore di composizione atmosferica non estendono a 96 ore il meteo ICON, né producono 120 ore. Bollettino ufficiale OSMER e allerte della Protezione civile restano separati e invariati.

Il report regionale di una corsa è completo. Prima della scelta operativa restano da campionare più corse e confrontare osservazioni rappresentative, misurando distribuzione e memoria sul servizio effettivo. I tempi locali non dimostrano gratuità o permanenza nelle quote cloud; nessuna stima economica è dedotta qui.
