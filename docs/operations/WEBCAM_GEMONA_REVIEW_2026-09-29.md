# Revisione webcam Gemona — 29 settembre 2026

## Decisione

`gemona-centro` usa nel catalogo attivo v17 l'**immagine statica corrente**
pubblicata nella pagina ufficiale WeatherCam. Il player video verificato resta
una modalità alternativa tecnicamente approvata, ma non viene inviato nel
record attivo: l'app mostra o lo snapshot oppure il player, mai entrambi.

La scelta predefinita riduce banda, dipendenze di terze parti e superficie
privacy rispetto allo streaming. La decisione editoriale del proprietario di
Meteo Friûl è mantenere disponibile il passaggio futuro al video. Non esiste un
accordo privato con WeatherCam, Meteo-Project o Meteo System. Fattibilità
tecnica, pubblicazione pubblica e incorporabilità non vengono registrate come
licenza: fonte, attribuzione, fallback e revoca per singola webcam restano
obbligatori.

## Verifica corrente

Verifica eseguita il **29 settembre 2026 tra le 21:47 e le 22:24 CEST**.

| Campo | Esito verificato |
| --- | --- |
| Località e identità | Gemona del Friuli, centro storico, inquadratura verso il Duomo. La pagina WeatherCam descrive la camera come installata nel centro dell'abitato e puntata verso il Duomo. |
| Sorgente ufficiale | [WeatherCam — Gemona del Friuli](https://www.weathercam.it/webcam/gemona), cliente indicato `Meteo System srl`, attivazione marzo 2021. |
| Snapshot attivo | `https://www.meteoproject.it/ftp/webcam/gemonadelfriuli/gemona.jpg`. È il file usato dalla stessa pagina WeatherCam come immagine statica e metadato sociale. |
| Stato corrente | HTTP `200`, MIME `image/jpeg`, dimensione osservata 739.665 byte. La pagina sorgente dichiara un aggiornamento ogni 1 o 20 minuti; l'intervallo effettivo non è stato misurato indipendentemente durante questa verifica. |
| Modalità tecnica attiva | Immagine HTTPS diretta in `<img>`, senza proxy, copia o archiviazione nel backend Meteo Friûl. Caricamento all'apertura e ricarica manuale protetta dal limite già presente nel frontend. |
| HTTPS, CORS e cache | Il sorgente HTML pubblica ancora l'immagine con `http://`, ma lo stesso percorso risponde correttamente in HTTPS e il catalogo usa soltanto HTTPS. Non è stato osservato `Access-Control-Allow-Origin`: non serve per la visualizzazione diretta con `<img>`, ma l'immagine non va letta da canvas. Risposta con `Cache-Control: max-age=0, no-cache, no-store, must-revalidate`, `Pragma: no-cache` ed `Expires` scaduto; nessun `ETag` o `Last-Modified` osservato. |
| Banda e formati | JPEG di circa 740 kB al controllo. Nessun polling automatico dedicato: evitare ricariche frequenti e lasciare all'utente il comando di aggiornamento. |
| Terze parti e privacy | Il caricamento dell'immagine contatta `www.meteoproject.it`, ma non esegue script, player, font o HLS. Il frontend usa `referrerPolicy="no-referrer"` per gli snapshot. La [privacy UE di Meteo System](https://www.meteo-system.com/dichiarazione-sulla-privacy-ue/) riguarda i dati ottenuti attraverso `meteo-system.com`, dichiara cookie e trattamento basato sul consenso e non viene assunta come informativa per WeatherCam o per il dominio del player. Il link esterno porta l'utente nel contesto e nelle regole del sito di destinazione. |
| Attribuzione | `WeatherCam · Meteo System`, collegata alla pagina sorgente specifica. |
| Licenza o permesso noto | Nessuna licenza specifica e nessun accordo privato noto. WeatherCam dichiara che le telecamere del portale sono pubblicate spontaneamente dal cliente proprietario; Meteo-Project presenta l'integrazione su siti e social come funzionalità del servizio. La privacy di Meteo System non concede diritti di riutilizzo. Queste evidenze sostengono l'uso tecnico della risorsa, non trasferiscono i diritti sul contenuto. |
| Coordinate | Non viene introdotta una coordinata puntuale non pubblicata dalla fonte. La mappa continua a usare il riferimento comunale approssimativo di Gemona del Friuli. |
| Stato operativo | **Snapshot attivo nel ramo webcam**, reversibile a fallback/link per il solo ID `gemona-centro` tramite il controllo webcam. |

## Opzione video conservata

Il player ufficiale
`https://stream-meteoproject.eu/weathercam-player.php?code=18` è stato
verificato come HLS continuo a 1920×1080 ed è ancora ammesso dalle allowlist
backend e frontend. Il record attivo non contiene `playerUrl`, quindi il player
non viene caricato e non compare alcun comando video.

Una futura selezione del video deve modificare il record in modo atomico:

- rimuovere `imageUrl`;
- impostare `mediaType` a `iframe`;
- impostare `playerUrl` all'URL esatto già approvato;
- conservare foto territoriale, fonte e attribuzione;
- ripetere il collaudo Web e Android reale.

La modalità video resta soggetta a questi vincoli già verificati:

- iframe creato solo dopo un gesto esplicito, senza preload;
- `sandbox="allow-same-origin allow-scripts"`, fullscreen e
  `referrerPolicy="no-referrer"`;
- smontaggio alla chiusura, al passaggio in background e su `pagehide`;
- caricamento di HLS, `hls.js` da jsDelivr e CSS font da Google Fonts solo dopo
  il tap;
- consumo osservato di circa 0,87 Mbit/s sul segmento campione;
- nessuna licenza specifica o autorizzazione privata nota.

## Controlli di sicurezza e continuità

- Il catalogo attivo non invia contemporaneamente snapshot e player.
- L'allowlist video accetta esclusivamente l'URL HTTPS completo con `code=18`;
  camera diversa, parametri aggiunti e frammenti vengono rifiutati sia dal
  backend sia dal frontend.
- Non viene copiato o archiviato lo snapshot: il client lo richiede al gestore.
- Se lo snapshot fallisce, il frontend passa alla foto territoriale locale e
  mantiene il collegamento alla pagina sorgente.
- Se il controllo remoto disabilita la webcam, l'API elimina `imageUrl` e
  `mediaType`: restano foto territoriale e collegamento alla fonte.
- Una risposta valida non garantisce continuità futura. Prima della promozione
  occorre ripetere il test Web e verificare apertura, ricarica, errore e ripresa
  su un telefono Android reale.

## Limite di distribuzione

La versione frontend di questo ramo conosce già entrambe le modalità e
l'allowlist del player WeatherCam. Dopo che una versione compatibile sarà
distribuita, il backend potrà scegliere snapshot o video senza un nuovo AAB.
Le versioni Android precedenti non possono ricevere nuove regole di fiducia dal
solo catalogo remoto. In questa fase non viene generato né caricato alcun
APK/AAB e non viene modificato alcun servizio Cloud.
