# CAMS: piano verificato e snapshot locale fresco

Questo percorso resta isolato dall'app, da Cloud Run e da ogni deploy. Il controllo
pubblico non usa credenziali e non invia `POST`. La richiesta autenticata va eseguita
solo in un secondo momento e solo se il piano immutabile è stato creato con successo.

## Gate pubblico obbligatorio

Il catalogo è l'unico punto di ingresso fissato nel codice:

- catalogo: <https://ads.atmosphere.copernicus.eu/api/catalogue/v1/collections/cams-europe-air-quality-forecasts>
- licenza: <https://spdx.org/licenses/CC-BY-4.0>
- documentazione ADS: <https://confluence.ecmwf.int/spaces/CKB/pages/202163324/Atmosphere+Data+Store+ADS+documentation>

Gli URL di `form` e `constraints` non sono fissati: vengono scoperti ogni volta dal
catalogo. Devono usare HTTPS, host
`object-store.os-api.cci2.ecmwf.int`, percorso esatto del dataset e nome
content-addressed. L'hash nel nome deve coincidere con SHA-256 dei byte ricevuti.

Il gate accetta soltanto:

- dataset `cams-europe-air-quality-forecasts`, sanity `available` o `down`,
  nessun `cads:disabled_reason`, DOI atteso e licenza esatta `CC-BY-4.0`;
- le 28 variabili approvate, senza elementi mancanti, aggiunti o duplicati;
- `model=ensemble`, `level=0`, `type=forecast`, `time=00:00`;
- tutti e soli i 97 lead orari da `0` a `96`;
- data richiesta coperta da catalogo, form e da una sola riga di constraints;
- area FVG limitata `[46.7, 12.2, 45.5, 14.0]` e formato `grib` per la pipeline.

La modifica proposta il 10 ottobre 2026 evita che il solo stato `down` del
sanity check del catalogo blocchi il piano: lo ammette solo dopo form,
constraints, data e selezione 28 × 97, e produce il warning
`catalogue_sanity_down_constraints_validated`. Un test ADS della richiesta
FVG esatta del 10 ottobre (job ADS `ca7bc15b-b479-4847-9efb-a37d89a21b8d`)
è riuscito: 2.214.628 byte GRIB e 2.716 messaggi GRIB2 strutturalmente validi.
Questa prova non sostituisce la decodifica, la verifica dei valori e i gate di
pubblicazione del worker; se l'acquisizione reale fallisce, non pubblicare.

Alle 08:21 circa del 4 settembre 2026 il primo controllo del catalogo indicava il
dataset disponibile, ma la riga ensemble del giorno esponeva solo 73 lead
(`0..72`). Il gate ha correttamente fallito senza leggere credenziali e senza
inviare `POST`. Un nuovo controllo alle 10:11 circa ha invece trovato una sola
riga compatibile con la matrice completa: 28 variabili e tutti i 97 lead `0..96`.
Il piano immutabile è stato quindi scritto con esito
`verified_plan_written_no_retrieval` e questi digest:

- piano: `51009a1a32d12afd1888641be26bfb9ef2203095bd959d629ae839ef082cb0fa`;
- richiesta: `3512829bf323f8518477394cf25706b1da32cd2dbe801c1e4207f2cac08f0143`.

Il fallimento delle 08:21 resta un test utile del comportamento fail-closed, non
lo stato finale del run. Il comando seguente registra il piano effettivamente usato
per questa acquisizione; quel percorso ora esiste e non va riutilizzato. Per creare
un piano futuro, da `experiments\weather_autonomy`, cambiare data e scegliere sempre
un nome di output nuovo:

```powershell
$PilotPython = 'PERCORSO_AMBIENTE_PYTHON\Scripts\python.exe'
$Plan = Join-Path ([System.IO.Path]::GetTempPath()) 'cams-request-plan-2026-09-04-check-1000.json'
& $PilotPython .\cams_request_plan.py --date 2026-09-04 --output $Plan --area 46.7 12.2 45.5 14.0 --data-format grib
if ($LASTEXITCODE -ne 0) { throw 'CAMS non espone ancora la matrice completa 28 x 97: non inviare POST ADS.' }
```

Il successo stampa `verified_plan_written_no_retrieval`, `plan_sha256` e
`request_sha256`. Un file già esistente non viene mai sovrascritto. Se serve un
secondo controllo, scegliere un altro nome: non cancellare o rigenerare il piano che
ha già accompagnato una richiesta.

## Acquisizione esplicita, non automatica

Questo comando è documentato per una sessione autorizzata successiva; non fa parte
del gate pubblico. Presuppone che la persona abbia già accettato i termini del
dataset. La directory deve essere nuova e contenere la data nel nome:

```powershell
$Artifacts = Join-Path ([System.IO.Path]::GetTempPath()) 'meteofriul-cams-fvg-20260904'
& $PilotPython .\retrieve_cams.py --credentials-file 'PERCORSO_PRIVATO\.cdsapirc' --request-plan $Plan --artifacts-directory $Artifacts --scope fvg --max-wait 900
```

Prima di leggere le credenziali, il programma valida il piano, l'area, la versione
del client e la destinazione. Copia gli stessi byte in `request-plan.json` e porta i
due hash in `request.json`, `submission-intent.json`, `job.json` e nei report. Il
client è fissato a un solo tentativo: un errore ambiguo dopo l'intent non causa mai
un secondo `POST`.

Solo dopo un errore ambiguo senza `job.json`, riconciliare con richieste `GET`:

```powershell
& $PilotPython .\reconcile_cams_job.py --credentials-file 'PERCORSO_PRIVATO\.cdsapirc' --directory $Artifacts --request-plan $Plan --scope fvg
if ($LASTEXITCODE -ne 0) { throw 'Riconciliazione non univoca: non risottomettere e non eseguire resume.' }
```

Solo `unique_existing_job_restored` termina con codice zero. `no_matching_job_found`,
più corrispondenze o una pagina inconcludente impongono uno stop manuale: non creare
una nuova directory per risottomettere la stessa richiesta.

Se invece `job.json` esiste, riprendere lo stesso job senza risottometterlo:

```powershell
& $PilotPython .\retrieve_cams.py --credentials-file 'PERCORSO_PRIVATO\.cdsapirc' --request-plan $Plan --resume $Artifacts --scope fvg --max-wait 900
```

Il download usa `source.grib.part` e un marcatore legato a job, piano e richiesta.
Se il trasferimento si interrompe, una ripresa dello stesso job può eliminare e
riscaricare soltanto quel parziale verificato; un file senza marcatore o appartenente
a un altro job non viene mai cancellato. Il file finale appare soltanto dopo `fsync`
e pubblicazione atomica senza sovrascrittura.

## Decodifica locale vincolata allo stesso piano

```powershell
& $PilotPython .\decode_cams_region.py --input "$Artifacts\source.grib" --request-plan $Plan --output "$Artifacts\cams-fvg-2026-09-04.json" --report "$Artifacts\cams-fvg-2026-09-04-report.json"
```

La data non è più un default del decoder: arriva dal piano. Un GRIB del 3 settembre
con un piano del 4 settembre, una matrice incompleta, un'area diversa o un hash non
coerente viene rifiutato.

## Esito verificato del run 4 settembre

La singola acquisizione autenticata autorizzata e la successiva decodifica offline
sono terminate con successo, senza risottomissioni e senza pubblicazione cloud. Il run
`20260904T000000Z` contiene tutti i 215 Comuni, 90 celle native condivise, tutte le
28 variabili e 97 istanti orari. Il contratto locale lo considera fresco fino al
`2026-09-05T00:00:00Z` e ancora utilizzabile, in stato degradabile esplicito, fino
al `2026-09-05T06:00:00Z`.

Misure reali della richiesta:

- acquisizione complessiva: **`214.560 s`**;
- coda del servizio: **`14.923 s`**;
- elaborazione remota: **`191.015 s`**;
- download: **2.251.564 byte** in **`1.027 s`**;
- SHA-256 del GRIB: `294ac1b5eecbbafb7b77c975d4b4a336aacc79235abd4129cec5df2313153b51`.

Misure reali della decodifica:

- tempo complessivo: **`42.152 s`**;
- payload JSON: **10.229.423 byte**;
- proiezione gzip: **4.478.578 byte**;
- picco del working set del processo: **210.653.184 byte**;
- SHA-256 del payload: `77c9b9181e95797ea7f380a7bd91bc6fdc7133412708a253268de36ab82825f0`.

Il lifecycle ha poi pubblicato le viste complete e pollini soltanto nei database
SQLite locali, raggiungendo lo stato durevole `PUBLISHED`. La ripetizione con gli
stessi artefatti, hash e timestamp ha restituito
`core_stage_idempotent=true`, `pollen_stage_idempotent=true` e
`family_idempotent=true`, senza aggiornare di nuovo il family latest: nessun
duplicato e nessuna seconda richiesta ADS.

Questi numeri misurano una sola corsa locale e non costituiscono una stima di
affidabilità plurimensile, accuratezza meteorologica o costo cloud.

## Dipendenze e ordine di grandezza

Ambiente isolato verificato: Python 3.13.5, `requests 2.34.2`,
`ecmwf-datastores-client 0.5.3`, `eccodes 2.48.0`, `numpy 2.5.2`.

La misura fresca riportata sopra ha prodotto 2.716 campi GRIB e 583.940 valori
associati ai Comuni. È coerente come ordine di grandezza con la corsa precedente,
ma non garantisce tempi uguali per il run successivo: coda, elaborazione e download
possono variare indipendentemente.

Rischi da trattare come stop, non come motivo per ritentare automaticamente:
metadati pubblici parziali, cambio di schema/licenza/host, timeout ambiguo del POST,
job duplicati, file o hash discordanti, output esistenti, download incompleto e GRIB
non conforme. Nessun passaggio di questo runbook pubblica dati o cambia l'app.


### Vincoli ADS divisi per variabile

Il catalogo ADS puo separare le 22 variabili aria dalle 6 variabili pollini in
righe distinte. Il gate ammette questa partizione solo se le variabili richieste
sono complete e disgiunte: ogni riga deve selezionare la stessa data, ensemble,
livello 0, forecast e 00:00, e deve contenere autonomamente tutti i lead 0..96.
Non si combinano modelli, livelli, orari o orizzonti incompleti per inventare
una copertura. Sovrapposizioni, variabili mancanti e selezioni malformate restano
bloccanti. Il piano risultante mantiene una sola richiesta di 28 x 97 campi,
la stessa area FVG e gli hash dei documenti pubblici originali.
