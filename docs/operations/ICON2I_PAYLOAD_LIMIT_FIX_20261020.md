# ICON: correzione locale del limite payload, 20 ottobre 2026

**Correzione verificata localmente; non distribuita.**
Ramo `codex/icon2i-checkpoint-metadata`, base `c8aa724dfae311d004f072010f59a0eb30d26b15`.
Prosegue lo stesso intervento del checkpoint. Alla verifica iniziale il codice
era non committato e main invariato; successivamente il proprietario ha
autorizzato commit e promozione locale (vedere sotto). Nessun push, deploy,
AAB, installazione, emulatore, acquisizione o invio.

## Problema e intervento

La corsa ordinaria `meteofriul-icon-knbcb` ha registrato un payload di
34.601.901 byte contro il precedente limite di 33.554.432 byte (32 MiB).
Il fallimento in `_read_bounded` e il superamento sono documentati nel
[verbale serale](ICON2I_CHECKPOINT_METADATA_DEPLOY_20261020.md).
Il grezzo di quella corsa non è disponibile per un replay locale:
non si dichiara una ripetizione dei suoi valori meteo.

`MAX_ICON_JSON_BYTES` passa a **64 MiB**, per JSON e ZIP decompressi.
Il payload regionale comprende 215 comuni × 73 ore e la provenienza degli
accumuli. La regressione completa produce naturalmente 37.183.656 byte:
la soglia precedente è insufficiente anche per un caso valido di questo
formato; 64 MiB lascia margine mantenendo un tetto esplicito.

Anche la lettura effettiva del file ora è limitata, non soltanto lo `stat`:
un file che cresce durante la lettura non può causare un caricamento
illimitato. Restano i controlli su hash, catalogo, corsa, struttura, orari
e 215 comuni. I log conservano tipo di artefatto, byte osservati e limite,
senza pubblicare percorsi locali o dettagli sensibili.

**Nessuna modifica alle soglie meteo o al significato dei valori mancanti.**
Restano separati e invariati il report (4 MiB), i documenti comunali e sidecar
(512 KiB), il checkpoint pubblicazione (64 MiB espanso / 16 MiB gzip),
la diagnostica (2 MiB) e i checkpoint dei singoli campi acquisiti.

## Verifiche completate

**183 test passati**, zero errori, fallimenti o casi saltati:
7 nuove regressioni e 176 prove su acquisizione simulata,
diagnostica, tolleranze, checkpoint, sidecar, entrypoint e worker.
Socket bloccati: nessuna chiamata a fornitori, GCP o servizi dell'app.

1. Un JSON di esattamente 34.601.901 byte e uno ZIP con quel contenuto
   decompresso vengono rifiutati con il vecchio limite e accettati con quello nuovo.
2. Il limite esatto è ammesso; un byte oltre è rifiutato. Restano rifiutati
   file vuoti/cambiati, report fuori limite, hash errati e identità incoerenti.
3. Un caso **sintetico**, con catalogo reale e 215×73 righe, attraversa il
   vero `prepare_icon_publication`, checkpoint schema 2 con salvataggio e
   rilettura, pubblicazione e verifica di 215 sidecar nello storage in memoria.
   Il vecchio limite riproduce il blocco; quello nuovo completa il percorso.
4. I documenti pubblici conservano esattamente i campi/valori previsti per i
   vecchi client, separando i metadati nei sidecar. La ripetizione è idempotente:
   il puntatore `latest` non cambia.

Misure del caso completo:

| Oggetto | Dimensione verificata | Limite invariato, salvo input |
| --- | ---: | ---: |
| Payload sorgente | 37.183.656 byte, senza padding | 67.108.864 byte |
| Checkpoint espanso | 26,460,979 byte | 67.108.864 byte |
| Checkpoint gzip | 640,325 byte | 16.777.216 byte |
| Documento comunale arricchito più grande | 124,099 byte | 524.288 byte |

La prova esercita 15,552 valori con tolleranza verificata
fra i tre campi di accumulo; non sono altrettante ore o avvisi.
Picco residente del processo della regressione completa:
217,579,520 byte, circa
207.5 MiB.
È una misura Windows/Python 3.13.5, **non** una garanzia del consumo nel
container Linux da 1 GiB né una prova della prossima corsa reale.

## Ripetizione locale

Da `experiments/weather_autonomy`, con le dipendenze già presenti:

```text
python -B -m unittest test_icon_snapshot_limits test_run_pilot test_operational_diagnostics test_accumulation_tolerance test_icon_quality test_icon_checkpoint test_icon_accumulation_sidecar test_job_entrypoints test_cloud_worker
```

I log salvati sono stati ottenuti con un wrapper che blocca le connessioni
socket e misura la memoria. La suite usa dati sintetici e storage locale
in memoria; non esegue il job operativo.
Gli hash identificano esattamente i tre file verificati:
[manifesto](evidence/icon-payload-limit-2026-10-20/verification.json),
[prova completa](evidence/icon-payload-limit-2026-10-20/pipeline-probe.json),
[nuove regressioni](evidence/icon-payload-limit-2026-10-20/regression-final.txt),
[regressioni collegate](evidence/icon-payload-limit-2026-10-20/related-regressions.txt).

## Cosa resta prima della chiusura operativa

La modifica risolve **il blocco di dimensione nelle prove locali**.
La verifica della nuova corsa/tolleranze in produzione resta incompleta:
non sono cambiati produttore attivo, checkpoint remoti, esiti terminali o dati
pubblicati. Non riaprire gli slot terminali del 20 ottobre per forzare retry.

Dopo la promozione locale autorizzata resta da autorizzare la costruzione e
verifica dell'immagine Linux, conservando la correzione dei metadati
`9ef1410e` e il lettore checkpoint 1/2; poi distribuzione con rollback
compatibile, nuova corsa ordinaria e controlli HTTP, sidecar, qualità e QA
senza invii. La promozione Git non esegue né autorizza questi passaggi.


## Commit e promozione locale autorizzati

Il proprietario ha richiesto commit della correzione e del verbale, poi il
passaggio delle modifiche verificate su main locale. La base di integrazione
è `520caa9a42763e1e642bc3370c4d779e8bed1d4e`.
Si conserva anche `9ef1410e`, la compatibilità dei metadati già verificata
insieme al limite: non era ancora presente su main.

La promozione è subordinata al controllo di integrità delle evidenze, alla
pulizia del checkout main e all'assenza di modifiche ai sorgenti meteo già
provati. Se l'integrazione cambia quei sorgenti, le regressioni vanno ripetute.
Le evidenze originali restano immutate, incluso `uncommitted: true`, che
descrive il momento della prova e non lo stato Git successivo.
Attributi Git circoscritti a queste nuove evidenze ne preservano i byte
(CRLF/LF compresi) e quindi gli hash; la patch archiviata conserva gli
spazi di contesto richiesti dal formato unified diff.

Questo intervento riguarda il produttore e non modifica l'app: nessuna
installazione o prova sul telefono è necessaria per la promozione del codice.
La CI remota non viene avviata senza push. Il fallimento operativo del 20
ottobre e la verifica incompleta delle tolleranze restano aperti.
