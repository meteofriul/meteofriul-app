# CAMS diretto — prova locale Pordenone, 3 settembre 2026

## Esito

Acquisizione ADS autenticata e decodifica riuscite: **28 variabili × 97 istanti
= 2.716 campi**, senza campi mancanti o duplicati. Comprende 6 pollini e 22
componenti della qualità dell'aria. Nessuna chiamata Open-Meteo in questa prova.
Non è una migrazione dell'app, una validazione dell'accuratezza o una prova
dell'affidabilità di aggiornamento su più giorni.

L'utente ha creato l'account e accettato personalmente la licenza. Il token è
stato letto dal file da lui indicato, soltanto in memoria per l'API ufficiale
ADS. Non è copiato nel progetto o negli artefatti. Il download dal risultato
ECMWF usa una sessione distinta, senza token, cookie o autenticazione implicita.

Nessun intervento su Firebase, Cloud Run, job periodici, app pubblicata, OSMER,
allerte o Scopri. Nessun commit, push o deploy.

## Richiesta e misure reali

Dataset `cams-europe-air-quality-forecasts`, ensemble median, superficie,
corsa **2026-09-03 00 UTC**, lead orari 0…96. Ultimo istante **7 settembre
00 UTC**: non sono 96 ore future dal momento della consultazione.
Area N/W/S/E: **46.1 / 12.5 / 45.8 / 12.8**.

| Voce | Misura |
| --- | ---: |
| Coda server, timestamp ADS | 14,389 s |
| Elaborazione server, timestamp ADS | 190,238 s |
| Totale server | 204,627 s |
| Download GRIB | 564.685 byte |
| Tempo trasferimento | 0,706 s |
| Decodifica locale separata | 31,020 s |
| JSON diagnostico, con valori grezzi e provenienza | 906.764 byte |
| Lo stesso JSON con gzip | 56.461 byte |
| Griglia effettivamente ricevuta | 3 × 3 punti, passo 0,1° |
| Matrici cella/punto costruite | 1 |
| Campi decodificati unici | 2.716 |

È confermato un vero ritaglio geografico lato server **per questo dataset
CAMS**. Non dimostra che ItaliaMeteo/ICON esponga lo stesso servizio.
La preview diagnostica serve il JSON non compresso: i 56 kB sono una misura
di compressione, non il traffico attuale dell'app. Nessuna misura della RAM
del processo CAMS o della bolletta cloud è stata effettuata.

Una sola richiesta è stata inviata. Dopo l'accettazione un controllo locale
troppo restrittivo ha rifiutato i timestamp ADS senza suffisso di fuso. Il
client ufficiale li interpreta come UTC; il parser è stato allineato e il
medesimo job è stato ripreso, senza un secondo POST. Il report della ripresa
misura 138,264 s dal riaggancio: **non** va confuso con la durata completa del
job. I tempi server sopra riportati comprendono l'intera esecuzione originale.

## Dati e controlli

Punto richiesto: 45.95689 N, 12.66051 E. Cella selezionata: **45.95 N,
12.65 E**, a circa **1,116 km** dal punto; la risoluzione resta circa 10 km,
non diventa 1 km. Nessuna interpolazione o correzione locale.

Il decoder verifica GRIB2, ensemble centre 85/subCentre 2, identità chimica,
superficie, corsa, scadenza, unità, griglia e completezza. Non usa gli alias
`unknown`/`paramId=0` di ecCodes per indovinare le variabili. Le identità
provengono dalla documentazione ECMWF; per ammonio, nitrati e solfati anche
dalla tabella WMO inclusa in ecCodes 2.48.0. Le unità generiche sono risolte
tramite identità verificata e documentazione del prodotto, conservando un flag.

Inquinanti: GRIB kg/m³ → µg/m³, fattore 10⁹. Pollini: grani/m³, invariati.
Null, valori non finiti e concentrazioni negative hanno stati espliciti; non
sono convertiti in zero. Tracce numeriche positive molto piccole restano tali
e nella preview non vengono arrotondate a uno zero esatto.

La completezza tecnica non è validazione scientifica: il fornitore verifica
regolarmente 7 variabili; le altre 21, inclusi tutti i pollini, sono indicate
come sperimentali/non validate. Nessun AQI, giudizio sanitario o categoria
di rischio è stato inventato.

## Artefatti e ripresa senza rete

In `experiments/weather_autonomy/`:

- `cams_pordenone_source_20260903.grib`: originale ritagliato.
- `cams_pordenone_request_20260903.json`: parametri e provenienza, senza token.
- `cams_pordenone_acquisition_20260903.json`: tempi e hash del download.
- `cams_pordenone_inventory_20260903.json`: inventario preliminare.
- `cams_pordenone_payload_20260903.json`: estrazione completa verificata.
- `cams_pordenone_decode_report_20260903.json`: controlli, dimensioni e intervalli.
- `retrieve_cams.py`: acquisizione limitata, ripresa esplicita, nessun retry POST.
- `decode_cams.py`: decodifica offline e output nuovi, senza sovrascrittura.

SHA256 GRIB: `2b1a5e0e9fa2b5c51d37a4a4bed84d4679b4233f611fa2eff6669a17dbb8d4fa`.
SHA256 JSON: `a9ae299a3ae0afa14f4f3fdfd26a935e62895b891ab356e9c988fbd97150f75d`.

`serve_pilot.py --payload <ICON-pilot.json> --cams-payload <CAMS-payload.json>`
espone la preview su `http://127.0.0.1:8767/`: endpoint fissi separati,
solo lettura, nessun accesso esterno. La sezione CAMS mostra 28 variabili e
97 righe per la variabile selezionata; il riepilogo usa l'ultimo orario già
valido. CAMS resta limitato a Pordenone anche cambiando Comune nella parte ICON.
Gli archivi ICON originali non sono modificati. Il PC serve soltanto per
vedere la preview; file e risultati rimangono salvati quando viene spento.

## Limiti e prossimo passo

Verifiche finali: **401 test offline del laboratorio superati** e
`git diff --check` pulito. QA nel browser: 28 righe nel riepilogo, 97 righe
nella serie selezionata, cambio ad Ambrosia, timestamp corrente della corsa,
7 variabili marcate come regolarmente validate dal fornitore e 21 sperimentali;
nessun errore o warning console. I numeri originali e i rispettivi hash sono
conservati; le etichette della preview non cambiano i dati.

Il test dimostra che l'accesso diretto e il ritaglio funzionano e sono leggeri
per questo campione. Prima di adottarli: misurare l'intero FVG, diverse corse,
ritardi/errori, memoria e costi effettivi del job ospitato. Non scaricare un
file separato per ciascuno dei 215 Comuni: valutare un ritaglio regionale unico
e l'estrazione locale dei punti. Nessun nuovo job è stato creato.

La licenza dati CC BY 4.0 permette il riuso commerciale rispettandone i termini,
l'attribuzione e l'indicazione delle modifiche. Questa prova non certifica le
altre fonti dell'app o la conformità pubblicitaria/privacy complessiva; l'app
attuale non è stata migrata dal servizio Open-Meteo.

## Fonti primarie

- [Dataset, risoluzione, unità e validazione](https://ads.atmosphere.copernicus.eu/datasets/cams-europe-air-quality-forecasts?tab=overview).
- [Identità dei campi GRIB CAMS](https://forum.ecmwf.int/t/how-to-identify-fields-in-european-air-quality-forecast-grib-files/1563).
- [Documentazione regionale CAMS](https://confluence.ecmwf.int/spaces/CKB/pages/202173092/CAMS+Regional+European+air+quality+analysis+and+forecast+data+documentation).
- [Client ufficiale ADS](https://ecmwf.github.io/ecmwf-datastores-client/README.html).
- [Licenza CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
