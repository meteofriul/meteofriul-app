# Audit fonti Webcam — 27 agosto 2026

> Aggiornamento: la [revisione del 30 agosto](./WEBCAM_CATALOG_REVIEW_2026-08-30.md) porta il catalogo locale a 19 attive, 6 candidate e 1 sospesa e corregge le fonti indicate sotto. Questo documento conserva la fotografia dell'audit originario, non il catalogo corrente.

## Esito

- Catalogo attivo locale: 18 webcam.
- Modalità di presentazione: foto territoriale locale già approvata e collegamento alla pagina esterna specifica.
- Immagini o flussi di terzi incorporati: nessuno.
- Candidati non pubblicati: 8, nel manifest `backend/app/data/webcams_candidates.json` con `mode: shadow` e `publish: false`.
- Pubblicazioni o scheduler cloud creati durante l'audit: nessuno.

Le foto territoriali provengono dal catalogo locale già revisionato. Autore, licenza e fonte restano nel registro `frontend/src/data/discover/municipalityPhotoCredits.json` e nell'informativa “Privacy, fonti e crediti”.

Il registro interno è completo per tutte le foto impiegate. Prima di una pubblicazione, autore, fonte e licenza dovranno essere consultabili anche dall'utente tramite un unico collegamento globale ai crediti: non verranno ripetuti dentro ogni card Webcam.

## Regola editoriale

Ogni scheda visibile contiene soltanto:

1. nome specifico della webcam;
2. Comune e località, piazza o punto di osservazione;
3. fonte e collegamento alla pagina webcam esterna.

Coordinate, stato del controllo e altri dati tecnici non sono mostrati nella card. Un fotogramma di terzi non può essere usato come foto statica: il fallback deve essere un'immagine prodotta dal progetto o già disponibile con licenza compatibile.

Dieci webcam attive dispongono della coordinata pubblicata dalla pagina specifica o dall'API ufficiale; per le altre la distanza usa temporaneamente il centro del Comune ed è marcata con `~` per dichiararne il carattere indicativo. Le coordinate restano metadati invisibili e non allungano la scheda.

## Catalogo attivo corretto

Le 18 voci attive hanno una pagina dedicata alla webcam oppure un catalogo webcam ufficiale pertinente e verificato:

- Grado — Ingresso spiaggia;
- Lignano Sabbiadoro — Punta Faro;
- Duino Aurisina — Sistiana;
- Monfalcone — Marina Julia;
- Trieste — Parco di Miramare;
- Trieste — Piazza della Borsa;
- Monte Zoncolan — Baita Goles;
- Tarvisio — Piazza della Chiesa;
- Forni di Sopra — località Chianeit;
- Piancavallo — Nevelandia;
- Val Saisera;
- Udine — Piazza Matteotti;
- Cividale del Friuli — Ponte del Diavolo;
- Gemona del Friuli — Centro;
- Gorizia — Piazza della Vittoria;
- Aquileia — Basilica;
- Sacile;
- San Daniele del Friuli — Centro.

Barcis e Spilimbergo sono state rimosse dal catalogo attivo: le vecchie webcam non risultano più disponibili e i collegamenti rimasti conducevano soltanto a pagine generiche. Potranno rientrare esclusivamente con una pagina webcam reale e verificabile.

## Candidati in ombra

Gli otto candidati sono Sappada, Sella Nevea/Canin, Val Settimana/Rifugio La Pussa, Monte Matajur, Moruzzo, Cervignano del Friuli, Piazza della Transalpina e Trieste/San Giusto.

Il backend pubblico non legge il manifest candidati. Per renderne attiva una voce occorrono, nell'ordine:

1. pagina specifica ancora raggiungibile;
2. nome e località confermati;
3. foto locale approvata e relativi crediti;
4. controllo di assenza di duplicati;
5. passaggio esplicito nel manifest attivo e revisione dell'interfaccia.

## Controllo tecnico locale

Il comando seguente valida il catalogo, controlla gli asset locali e verifica le pagine esterne senza salvare immagini:

```powershell
cd backend
venv\Scripts\python.exe tools\check_webcams.py
```

Per i candidati:

```powershell
cd backend
venv\Scripts\python.exe tools\check_webcams.py --candidates app\data\webcams_candidates.json
```

Il report dichiara sempre `publish: false`. Il controllo è uno strumento locale/pre-release, non un nuovo workflow o job cloud.

Il controllo non considera sufficiente una risposta HTTP `2xx`: segnala anche il reindirizzamento a una pagina generica e l'assenza di elementi riconducibili a webcam, player o contenuti incorporati. In questo modo un cambio di struttura del sito non produce un falso esito positivo silenzioso.

Esito del 27 agosto 2026: 18/18 fonti attive e 8/8 candidate in ombra verificate; nessun contenuto candidato è stato pubblicato.

## Addendum — player incorporati, 29 agosto 2026

Il controllo successivo ha distinto tre aspetti che il primo audit teneva volutamente separati: raggiungibilità della pagina esterna, disponibilità tecnica di un fotogramma/player e autorizzazione all'incorporamento nell'app.

### Esito sulle 18 webcam attive

- Le webcam WhatsUpCams espongono widget tecnicamente funzionanti, ma le condizioni generali non autorizzano chiaramente Meteo Friûl a incorporarli: restano foto locale e collegamento esterno fino a consenso scritto.
- Lignano dispone di un flusso HLS funzionante; non è stata trovata una licenza pubblica di incorporamento, quindi non viene attivato.
- Meteo System Miramare e Corte San Giacomo pubblicano fotogrammi aggiornati, mentre WeatherCam espone un player; per tutte e tre manca un'autorizzazione pubblica sufficientemente chiara.
- Piancavallo, Cividale e Val Saisera non sono candidati live: le prime due fonti risultano ferme e la pagina indicata per Val Saisera mostra una webcam riferita a un'altra località.
- Protezione Civile FVG non offre video. L'API pubblica usa JPEG sostituiti tramite polling; Monfalcone e Sacile non hanno immagini recuperabili e i 38 fotogrammi ancora esposti dal portale sono fermi tra aprile e maggio 2026. Non possono essere presentati come live.
- Le vecchie immagini OSMER non vengono incorporate: le note legali vietano la ripubblicazione in tempo reale prima di 24 ore senza autorizzazione preventiva.

### Candidati Panomax

Forni di Sopra e San Daniele del Friuli espongono nelle rispettive pagine Panomax la funzione `Link/Embed` e generano questi iframe canonici:

- `https://fornidisopra.panomax.com/`;
- `https://sandanieledelfriuli.panomax.com/`.

Non sono stream MP4, HLS o MJPEG: sono panorami interattivi aggiornati. Le due pagine rispondono senza reindirizzamenti e non inviano intestazioni che ne impediscano tecnicamente il framing.

L'uso in produzione resta però sospeso. L'imprint Panomax vieta genericamente i frame esterni e la documentazione per app/partner parla di distribuzione approvata; inoltre il player carica Matomo e servizi Google. Prima della beta servono:

1. autorizzazione scritta di Panomax e, preferibilmente, del proprietario/PromoTurismo FVG;
2. verifica e aggiornamento dell'informativa privacy;
3. conferma su Android reale dopo l'autorizzazione.

### Prova locale protetta

È disponibile soltanto in sviluppo con il parametro esplicito:

```text
?tab=live&webcamPlayerQa=panomax
```

La prova non modifica `backend/app/data/webcams_active.json`. Aggiunge localmente il player alle sole due webcam Panomax, mantiene la foto come anteprima e crea l'iframe esclusivamente dopo un gesto dell'utente. Il frontend accetta soltanto le due URL canoniche; il validatore backend applica lo stesso criterio e respinge tipo, host, porta, percorso o query diversi. Non esistono autoplay o pulsante `Riprova`.

Verifica del 29 agosto 2026: 1.996 test frontend, 29 test backend mirati, lint e build superati. Nessun commit, push o deploy eseguito.

## Addendum — pannello video ARPA/OSMER, 29 agosto 2026

Il pannello video è stato auditato separatamente dalle immagini statiche. Contiene 49 fonti: 21 player/stream turistici e 28 clip MP4 dell'A23. Quarantasette risultano tecnicamente raggiungibili, ma nessuna supera il filtro completo per l'incorporamento pubblico senza autorizzazioni o rapporti contrattuali.

Il catalogo attivo, l'allowlist dei player e la beta restano invariati. Esito, criteri e inventario completo sono documentati in [WEBCAM_OSMER_VIDEO_AUDIT_2026-08-29.md](./WEBCAM_OSMER_VIDEO_AUDIT_2026-08-29.md).
