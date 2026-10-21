# ICON: deploy del limite payload e rollback compatibile

20 ottobre 2026: deploy completato. **21 ottobre: verifica della corsa ordinaria completata con esito positivo.**
Autorizzazione: aggiornare il produttore ICON e verificare la prossima corsa
ordinaria, senza esecuzioni manuali (QA compreso), AAB, installazioni o invii.

## Distribuzione

- Sorgente: main `5cbcd35ca88088220ff167b299cb4353ebdaf6d4`, CI [39481286330](https://github.com/meteofriul/meteofriul-app/actions/runs/39481286330) verde.
- Job: `meteofriul-icon`, progetto `meteo-friul`, regione `europe-west1`, account verificato `meteofriul@gmail.com`.
- Immagine distribuita: `europe-west1-docker.pkg.dev/meteo-friul/meteofriul/weather-worker@sha256:53c8709e74e75b350b1f502149bda489eb99b6e2c30eb6b47c46c4f689e78d48`.
- Cloud Build: `00bffaee-b3fa-49e3-90ee-6db2647825b5`, SUCCESS; sorgenti verificati con SHA-256.
- Cambiata soltanto l'immagine del produttore alle 2026-10-20T19:28:55.056618+00:00.
  Configurazione, identità, CPU, memoria 1 GiB, timeout e retry invariati.
  Altri 12 job, 11 scheduler e servizio HTTP invariati.
- Nessuna nuova esecuzione prodotta dal deploy, nessun QA manuale o invio.
  Gli slot terminali del 20 ottobre e gli oggetti immutabili non sono stati modificati.

La correzione porta il limite JSON/ZIP decompresso da 32 a 64 MiB e migliora
la diagnostica del superamento. Non cambia soglie meteo, tolleranze o formato
pubblico. Mantiene la correzione `packingError` e il lettore checkpoint 1/2.
Riferimento: [correzione locale](ICON2I_PAYLOAD_LIMIT_FIX_20261020.md).

## Verifiche dell'immagine

183 test della candidata e 108 del rollback superati, zero fallimenti,
errori o casi saltati. Container con rete disabilitata e memoria limitata a
1 GiB, senza aggiornare dipendenze. Il caso sintetico completo copre
215 comuni x 73 ore, checkpoint schema 2 e 215 sidecar legati ai documenti.
Picco RSS dell'intera suite candidata: 341.217.280 byte (circa 325,4 MiB).
Questa misura non sostituisce quella della prossima acquisizione reale.

## Rollback preparato, non eseguito

Immagine precedente: `europe-west1-docker.pkg.dev/meteo-friul/meteofriul/weather-worker@sha256:e72f606ffe1feec5f1c108f945ec5dbce43cfebef3d69913fc72c11b04cbcae2`.
Verificata nell'immagine effettiva la lettura dei checkpoint 1 e 2; i sorgenti
di lettura del checkpoint, qualità e packing coincidono con la candidata.
Il [comando pronto](evidence/icon-payload-limit-deploy-2026-10-20/rollback-command.txt)
cambia solo l'immagine, con progetto, account e regione espliciti.

**Limite del rollback:** riporta il tetto a 32 MiB. Una nuova acquisizione
grande può quindi bloccarsi nuovamente; la compatibilità dei dati non equivale
alla soluzione del problema. Non usarlo per riaprire esiti terminali o
riscrivere checkpoint. Prima di eseguirlo controllare che non ci sia un job
attivo e che l'immagine corrente sia quella attesa. Nessun rollback automatico.

## Letture delle app al momento del deploy (20 ottobre)

FVG: latest, manifest e tre documenti riletti sono invariati. Si riusano le
prove dei due lettori storici (`2f02c8ba`, `8497e773`) sui medesimi 215 documenti
immutabili. La corsa è ancora `20261019T120000Z`: prova di compatibilità,
**non** di aggiornamento riuscito con il nuovo produttore.

Nazionale: Milano, Canazei, Roma, Napoli, Palermo e Cagliari passano con
entrambi i lettori, 73 ore per località, corsa `20261020T120000Z`.
Hash, manifest, indice e CORS Android validi. È un campione, non tutto il Paese.
Nessuna modifica al servizio nazionale o verifica visiva sul telefono.

## Piano del controllo ordinario, completato il 21 ottobre

Scheduler invariato: corsa **21 ottobre, 06:00 UTC / 08:00 italiane**.
Il piano prevedeva un controllo alle 08:20 e, se necessario, alle 09:20.
La chiusura documentata sotto avviene nel follow-up pomeridiano; nessun avvio manuale.
I seguenti script della cartella `.tmp` canonica effettuano solo letture:

1. `inspect_icon_limit_ordinary.py`: esecuzione creata dallo scheduler, digest
   atteso, successo, checkpoint schema 2, nuova corsa e log source_quality.
2. `verify_icon_limit_http.py --name new-run-http --require-new`: tutti i
   215 documenti nei vecchi client, sidecar autenticati per corsa/comune/ora/hash,
   conteggi delle tolleranze e integrità del vecchio manifest.
3. `verify_icon_limit_national.py --name national-http-next`: campione nazionale.

Se non vi sono tolleranze esercitate, dichiararlo; eventuale valutazione
integrativa solo locale sui dati già pubblicati. Il QA cloud non va eseguito:
questa verifica esclude ogni esecuzione manuale e non modifica la
configurazione degli invii ordinari autorizzati dal proprietario.
Il ripristino delle allerte ufficiali FVG è un intervento separato.

Il follow-up «Verifica tolleranze ICON sulla nuova corsa» è stato eliminato
il 21 ottobre, dopo il completamento verificato.

Le evidenze grezze private restano in `.tmp/icon-payload-limit-deploy-20261020`,
già esclusa da Git. Il [manifesto delle evidenze](evidence/icon-payload-limit-deploy-2026-10-20/SHA256SUMS.txt)
identifica copie ripulite, sorgenti delle verifiche e risultati. Le copie dei
tool vanno riportate nella `.tmp` canonica prima dell'uso; non avviarle dalla
cartella di archivio. Non è stato effettuato alcun push Git.

## Esito della corsa ordinaria del 21 ottobre

**Esito positivo sulla nuova corsa `20261021T000000Z`.** L'esecuzione
`meteofriul-icon-6nwgl`, creata dallo scheduler alle 06:00:00 UTC, ha concluso
con successo alle 06:04:18 UTC. Il digest effettivo coincide con quello del
deploy sopra attestato. Il checkpoint è schema 2, 1.626.396 byte; hash e
identità sono conservati nel [risultato ordinario](evidence/icon-payload-limit-deploy-2026-10-20/ordinary-2026-10-21/ordinary-run-result.json).
Il limite corretto non ha bloccato questa acquisizione ordinaria.

I tre script previsti hanno terminato con esito positivo. Il controllo HTTP
successivo completa l'indicazione intermedia `http_validation` presente nel
risultato del primo script; l'esito finale è nella
[chiusura verificata](evidence/icon-payload-limit-deploy-2026-10-20/ordinary-2026-10-21/closure.json).

### Previsioni e compatibilità

- FVG: **215 documenti e 215 sidecar** verificati sulla nuova corsa; integrità
  del documento e legami corsa/comune/ora/hash dei sidecar validi. Entrambi i
  lettori storici (`2f02c8ba`, `8497e773`) accettano tutti i 215 documenti.
  Il corpo pubblico mantiene il formato compatibile; il vecchio manifest
  immutabile è invariato. CORS Android valido.
- Nazionale: Milano, Canazei, Roma, Napoli, Palermo e Cagliari passano con
  entrambi i lettori, sulla corsa `20261021T000000Z`, 73 ore per località.
  Manifest, indice, hash, associazione comune/cella e CORS Android validi.
  I lettori ricavano 12 ore e 4 giorni per ogni località.

Risultati: [FVG](evidence/icon-payload-limit-deploy-2026-10-20/ordinary-2026-10-21/fvg-http-result.json)
e [campione nazionale](evidence/icon-payload-limit-deploy-2026-10-20/ordinary-2026-10-21/national-http-result.json).
Si verifica la lettura dei dati con il codice dei vecchi client, non la
visualizzazione su un telefono. Il nazionale resta un campione di sei comuni.

### Qualità e tolleranze realmente esercitate

Il singolo evento `source_quality` coincide, campo per campo, con il riepilogo
ricavato dal checkpoint. I conteggi dei sidecar sono stati ricalcolati
localmente sugli stessi dati scaricati e coincidono con il risultato HTTP.
Ogni campo ha **15.695 ore-comune previste (215 x 73)**.

| Campo finale | Quantificato | Zero noto | Tolleranza verificata | Indisponibile |
| --- | ---: | ---: | ---: | ---: |
| Precipitazione, mm | 5.727 | 7.400 | 2.353 | 215 |
| Pioggia liquida, mm | 5.589 | 7.687 | 2.204 | 215 |
| Neve, mm SWE | 16 | 15.462 | 2 | 215 |

Le tolleranze sono quindi presenti nei dati reali, anche per la neve. Tutti
questi record hanno budget entro la tolleranza dichiarata. Nessun blocco per
metadati di risoluzione assenti o budget oltre tolleranza, su 15.695 casi per
campo. Le 215 indisponibilità per campo sono tutte nell'ora iniziale
`2026-10-21T00:00:00Z`, con motivo `missing_or_invalid_accumulation`; restano
indisponibili. I tre conteggi non rappresentano comuni distinti e non vanno
sommati come numero di episodi meteo.

Restano **40 anomalie di umidità su 15.695 righe**, con 40 campioni diagnostici
conservati e nessun troncamento. I dati mancanti non sono stati normalizzati.
Questa verifica dimostra pubblicazione, metadati e compatibilità; non misura
le decisioni del job avvisi, candidati recuperati o notifiche ricevute. Non è
stato eseguito alcun QA cloud o confronto di invii.

### Provenienza e limiti operativi

La chiusura è stata effettuata nel follow-up pomeridiano del 21 ottobre,
leggendo l'esecuzione ordinaria mattutina e riusando i risultati completi.
Il precedente percorso locale del monitor non esisteva più: è stato
riaperto il ramo esistente `codex/icon2i-payload-limit-deploy` in un checkout
gestito. Per lo script nazionale è stato sostituito solo in memoria il
percorso del repository; i riferimenti immutabili dei due lettori sono
invariati. Nessuna modifica allo script operativo o ai dati cloud.

Zero esecuzioni manuali, acquisizioni manuali, QA cloud, invii manuali,
deploy, rollback, AAB, installazioni, emulatori o push Git durante il controllo.
Configurazioni degli invii e scheduler non modificati. I risultati grezzi
restano nella `.tmp` canonica; le copie ripulite e i loro hash sono nel
[manifesto della verifica](evidence/icon-payload-limit-deploy-2026-10-20/ordinary-2026-10-21/SHA256SUMS.txt).
