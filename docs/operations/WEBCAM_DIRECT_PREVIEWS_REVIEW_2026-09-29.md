# Revisione anteprime webcam dirette — 29 settembre 2026

## Ambito ed esito

Verifica puntuale eseguita il **29 settembre 2026 tra le 21:21 e le 21:33
CEST** sulle dieci fonti che il catalogo attivo carica come snapshot. La prova
ha usato esclusivamente il pilot canonico avviato con
`scripts/start-local-weather-pilot.ps1` sulla porta `5174` e le pagine o gli
endpoint HTTPS dei gestori.

Tutte le anteprime erano raggiungibili e correnti. Non sono stati cambiati URL,
nomi, coordinate, attribuzioni o modalità di integrazione. Il manifest passa
alla versione **15** soltanto per registrare la nuova verifica.

La raggiungibilità tecnica non sostituisce il consenso del proprietario. Le
note di titolarità riportate sotto descrivono ciò che è pubblicato dalle fonti;
non trasformano automaticamente l'accesso pubblico in un'autorizzazione al
riuso.

## Verifica fonte per fonte

| Webcam | Fonte primaria e identità | Evidenza corrente | Integrazione nell'app | Titolarità osservata | Decisione |
| --- | --- | --- | --- | --- | --- |
| Sacile | [SacileMeteo](https://sacilemeteo.altervista.org/hik/webcam_hik.html), panorama da Sacile | JPEG 1920×1080 con orario impresso **21:21:12** | Snapshot HTTPS, refresh visibile/manuale, fallback comunale, unico riferimento `SacileMeteo · © Luigi Carbonera` | Il sito espone CC BY-SA 3.0 IT nel footer generale e identifica Carbonera; la pagina webcam non chiarisce separatamente la licenza del singolo fotogramma | **Mantenere attiva**, con credito e collegamento già presenti |
| Grado Pineta — Isolotto Sacca dei Moreri | [Consorzio Grado Turismo](https://grado.it/it/scoprire-grado/webcam), Residence Hotel Al Bosco e Kite Life FVG | Immagine 2688×1080 con orario impresso **21:29** | Snapshot HTTPS, nessun proxy o archivio; aggiornamento solo quando la preview è visibile | La pagina ufficiale mostra direttamente immagine e crediti, senza licenza pubblica specifica osservata | **Mantenere attiva**, evitando refresh più frequenti dei 5 minuti esistenti |
| Lignano — Punta Faro | [LignanoSabbiadoro.com](https://www.lignanosabbiadoro.com/webcam/webcam-spiaggia-punta-faro) | JPEG 1600×900, **21:28:31** | Prima vista del gruppo 1/5 | Il sito dichiara il contenuto protetto da diritti | **Mantenere attiva** con fonte visibile |
| Lignano — Spiaggia centrale | [LignanoSabbiadoro.com](https://www.lignanosabbiadoro.com/webcam/webcam-spiaggia-lignano-sabbiadoro) | JPEG 1600×900, **21:25:31** | Seconda vista 2/5 | Come sopra | **Mantenere attiva** con fonte visibile |
| Lignano — Piazza Fontana | [LignanoSabbiadoro.com](https://www.lignanosabbiadoro.com/webcam/webcam-piazza-fontana-centro) | JPEG 1600×900 corrente; `Last-Modified` mostrato nell'app alle **21:25** | Terza vista 3/5 | Come sopra; la pagina identifica anche la veduta dall'Hotel Monaco | **Mantenere attiva** con fonte visibile |
| Lignano — Pontile Pagoda | [LignanoSabbiadoro.com](https://www.lignanosabbiadoro.com/webcam/webcam-spiaggia-lignano-pineta) | JPEG 1600×900, **21:27:10** | Quarta vista 4/5 | Come sopra | **Mantenere attiva** con fonte visibile |
| Lignano — Spiaggia Riviera | [indice webcam Lignano](https://www.lignanosabbiadoro.com/webcam) | JPEG 1600×900, **21:25:01** | Quinta vista 5/5 | Come sopra | **Mantenere attiva** con fonte visibile |
| Monte Grisa — sud-est | [CISAR Trieste APS](https://www.cisartrieste.it/meteo-m-grisa/) | JPEG 2560×1440 con orario impresso **21:30:04 CEST** | Prima vista del gruppo 1/2 | La pagina espone `Copyright © CISAR Trieste APS — All rights reserved` | **Mantenere attiva** con fonte CISAR |
| Monte Grisa — sud-ovest | [CISAR Trieste APS](https://www.cisartrieste.it/meteo-m-grisa/) | JPEG 2560×1440 corrente alle **21:30** | Seconda vista 2/2 | Come sopra | **Mantenere attiva** con fonte CISAR |
| Trieste — Lanterna nord | [CISAR Trieste APS](https://www.cisartrieste.it/meteo-lanterna/) | JPEG 2560×1440 con orario impresso **21:30:01 CEST** | Snapshot singolo | Come sopra | **Mantenere attiva** con fonte CISAR |

## Collaudo UI

- Sacile e Grado mostrano immagine, refresh manuale, ingrandimento, fallback e
  collegamento alla pagina del gestore.
- Lignano mostra una sola immagine alla volta, frecce discrete sovrapposte a
  metà anteprima e contatore `1 di 5` … `5 di 5` in alto a destra. Nome,
  freschezza e link sorgente cambiano insieme alla vista.
- Monte Grisa usa lo stesso schema con contatore `1 di 2` … `2 di 2`; Lanterna
  resta una webcam singola.
- Il refresh automatico degli snapshot è sospeso quando la preview non è
  visibile o il documento passa in background; alla ripresa viene rivalutata la
  freschezza. L'intervallo attivo resta di 5 minuti.
- Nessun iframe, player, cookie di terze parti, proxy backend o copia persistente
  è introdotto da queste anteprime.

## Stato operativo

Le dieci anteprime dirette risultano tecnicamente sane. Il prossimo passaggio
del workstream è la revisione delle webcam oggi pubblicate come **solo
collegamento**, iniziando dalle fonti con player o panorama esterno. Qualunque
promozione da link a snapshot/player richiede una decisione distinta su
provenienza, continuità, privacy e autorizzazione.
