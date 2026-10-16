# Webcam Moruzzo - Panorama verso ovest — verifica 2 ottobre 2026

## Decisione

`moruzzo-panorama` passa dal catalogo candidato al catalogo attivo v29 come
**anteprima aggiornata**. L'app usa il mirror JPEG HTTPS del pannello ARPA FVG
- OSMER e GRN, conserva la pagina specifica WeatherCam come azione “Apri la
fonte” e non incorpora video, timelapse o player.

La scelta e' editoriale, revocabile per singola fonte e compatibile con il
fallback locale. Non costituisce una dichiarazione di licenza o di permesso da
parte del Comune di Moruzzo, di MeteoProject/WeatherCam o di OSMER.

## Verifica puntuale

Controllo eseguito il `2026-10-02T06:43:41Z` sulle pagine e risorse correnti.

| Campo | Esito |
| --- | --- |
| Localita' e identita' | Moruzzo, panorama verso ovest, quota dichiarata 267 m. Il fotogramma mostra la chiesa di San Tomaso Apostolo, Piazza del Tiglio e il panorama collinare; l'overlay riporta `Webcam Comune di Moruzzo (UD) - 267m s.l.m.` e il logo WeatherCam. |
| Pagina proprietaria | [WeatherCam - Webcam di Moruzzo](https://www.weathercam.it/webcam/moruzzo): cliente `Comune di Moruzzo`, attivazione maggio 2025, quota 267 m e origine MeteoProject. La pagina dichiara inoltre che le camere del portale sono pubblicate dal cliente, che ne e' proprietario. |
| Pagina tecnica | [Stazione MeteoProject di Moruzzo](https://stazioni.meteoproject.it/dati/moruzzo/webcam.php). Le coordinate `46.121, 13.139` e la quota 221 m pubblicate nella pagina generale appartengono alla stazione meteo del Polo Scolastico e non vengono usate per la camera. |
| Riferimento OSMER | [Pannello webcam ARPA FVG - OSMER e GRN](https://www.meteo.fvg.it/webcam_img.php?ln=it) e [feed mappa](https://www.meteo.fvg.it/ajax/webcamList.php). La voce `Moruzzo` riporta quota 267 m, vista ovest, fonte WeatherCam/MeteoProject, upstream e mirror locale. |
| Coordinate | Marker dichiarato dal feed OSMER: `46.1196936077918, 13.1235643188482`. E' la posizione editoriale pubblicata da OSMER, non una misura fisica certificata della telecamera; resta distinta dalle coordinate della stazione meteo. |
| Mirror usato dall'app | `https://www.meteo.fvg.it/ext/webcams/webcams/Moruzzo-moruzzo.jpg.jpg`, senza il nonce volatile aggiunto dal pannello. |
| Upstream | `https://stazioni.meteoproject.it/webcam/moruzzo/moruzzo.jpg`. E' tecnicamente utilizzabile e piu' fresco, ma non viene caricato dal record v29; resta una possibile sostituzione puntuale futura. |
| Stato corrente | Mirror e upstream: stato `200`, `image/jpeg`, JPEG JFIF valido 1920×1080. Il fotogramma osservato riportava data 02/10/2026 e timestamp coerente con gli header. |
| Freschezza osservata | Alle 08:40 CEST l'upstream era aggiornato da circa 4 secondi e il mirror da circa 10 minuti. Alle 08:46 il mirror ha recepito il fotogramma delle 08:45. L'osservazione e' coerente con una copia OSMER ogni circa 15 minuti, ma la cadenza non e' dichiarata ne' garantita. |
| HTTPS, CORS e cache | Entrambi HTTPS con `ETag`, `Last-Modified` e `Accept-Ranges`; nessun `Access-Control-Allow-Origin`, `Cache-Control`, `Expires` o `Set-Cookie` osservato sull'immagine. Funzionano in `<img>`; il frontend non legge gli header cross-origin. |
| Banda | Circa 730–758 KiB per fotogramma al controllo. Nessun preload dell'elenco. L'app aggiorna ogni 10 minuti soltanto quando l'anteprima e' visibile e l'app e' in primo piano; il refresh manuale conserva il cooldown di 12 secondi e puo' ricevere lo stesso fotogramma OSMER. |
| Privacy | La ripresa inquadra uno spazio pubblico, veicoli e possibili passanti. L'app non aggiunge riconoscimento, registrazione o archivio e non carica script/cookie WeatherCam: richiede soltanto il JPEG. L'ingrandimento mantiene tuttavia la risoluzione 1920×1080 della fonte e va incluso nella verifica periodica. |
| Attribuzione | Fonte visibile: `Comune di Moruzzo / Meteo-Project`. Raccolta tecnica separata: `WeatherCam / Meteo-Project · ARPA FVG - OSMER e GRN`, collegata al pannello OSMER. |
| Licenza o permesso noto | Nessun accordo privato noto e nessuna licenza di riuso individuata. WeatherCam attribuisce la proprieta' al cliente; la disponibilita' pubblica, il mirror e l'integrazione concessa al proprietario non autorizzano automaticamente Meteo Friûl. |
| Stato | **Attiva localmente come anteprima aggiornata per scelta editoriale revocabile; autorizzazione da consolidare con il Comune/proprietario.** |

## Integrazione

Il catalogo v29:

- conserva l'ID `moruzzo-panorama` e lo rimuove dal manifest candidato;
- usa il mirror HTTPS OSMER come snapshot, senza proxy Meteo Friûl;
- usa la pagina WeatherCam specifica, non la precedente `index-vuoto.php`;
- mostra separatamente proprietario/gestore e raccolta OSMER;
- usa le coordinate del marker OSMER, senza sostituirle con quelle della
  stazione meteo;
- mantiene `/municipalities/photos/030063-photo.webp` come fallback;
- non configura `playerUrl`, iframe, timelapse, cookie o download server-side.

## Condizioni operative

- immagine completa, senza ritaglio del timestamp o del logo originario;
- refresh moderato e solo foreground/visibile;
- fallback territoriale su errore o spegnimento dal controllo per fonte;
- nessuna promessa di nuova immagine a ogni pressione del refresh;
- controllo periodico di freschezza, privacy e permanenza del path OSMER;
- rimozione del solo `imageUrl`/`mediaType` se il proprietario chiede di
  interrompere l'anteprima, mantenendo card, fallback e pagina fonte.

## Collaudo

Collaudo locale completato il 2 ottobre 2026:

- API del pilot: catalogo v29, 30 webcam attive e contratto Moruzzo completo;
- pilot avviato esclusivamente con
  `scripts/start-local-weather-pilot.ps1 -WeatherTestNow 2026-09-04T12:00:00Z`
  sulla porta 5174. Il profilo temporale supportato evita che lo snapshot ICON
  offline scaduto blocchi l'avvio e non altera il contratto webcam;
- filtro `Pianura`: 9 sorgenti; il filtro non apre il pannello e l'elenco viene
  mostrato soltanto con `Vedi tutte`;
- scheda Moruzzo: JPEG caricato a 1920×1080, nome/localita' corretti, fonte e
  attribuzione leggibili, pagina WeatherCam aperta con `target="_blank"` e
  `rel="noopener noreferrer"`, nessun iframe o player;
- refresh manuale: il parametro `mf_snapshot` cambia, l'immagine resta valida a
  1920×1080 e il comando entra nel cooldown previsto di 12 secondi;
- console: nessun errore o avviso riferito alle webcam. Il pilot ha registrato
  soltanto l'indisponibilita' del resolver meteo nazionale, estranea a questo
  workstream e coerente con il profilo offline usato;
- backend: `65 passed, 152 subtests passed` nella suite webcam completa;
- frontend: `50` file e `774` test della feature live superati;
- lint frontend e `git diff --check`: superati.

La prova Android reale di background/ripresa resta separata e non e' stata
eseguita in questo blocco; non e' richiesta per il commit locale del catalogo.
