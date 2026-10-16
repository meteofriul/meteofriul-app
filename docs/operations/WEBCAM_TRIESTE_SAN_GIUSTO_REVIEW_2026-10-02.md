# Webcam Trieste - Colle di San Giusto — verifica 2 ottobre 2026

## Decisione

`trieste-san-giusto` passa dal catalogo candidato al catalogo attivo e usa
l'**anteprima aggiornata** Panomax, con attribuzione, collegamento diretto alla
pagina originale, fallback territoriale e nessun player in produzione. Il
panorama interattivo resta disponibile soltanto nel pilot locale attraverso il
gate QA Panomax: non viene inviato o caricato nel record pubblico.

La promozione e' una scelta editoriale revocabile coerente con le altre fonti
Panomax gia' approvate per l'app. La disponibilita' pubblica del fotogramma non
viene presentata come licenza o autorizzazione al riuso.

## Verifica puntuale

Controllo eseguito il `2026-10-02T05:11:02Z` su fonti primarie.

| Campo | Esito |
| --- | --- |
| Localita' e identita' | Trieste, Colle di San Giusto. La pagina specifica si intitola `Webcam Trieste - San Giusto` e dichiara `camId = 6949`; il catalogo ufficiale PromoTurismoFVG elenca `Trieste San Giusto` come voce autonoma. Le coordinate del record sono `45.646699, 13.772191`. |
| Sorgente e URL ufficiale | [Catalogo webcam PromoTurismoFVG](https://www.turismofvg.it/it/webcam) e [pagina Panomax Trieste - San Giusto](https://trieste.panomax.com/). Fotogrammi tecnicamente esposti da `https://live-image.panomax.com/cams/6949/recent_reduced.jpg` e `https://panodata.panomax.com/cams/6949/preview_og.jpg`. |
| Stato corrente | La voce PromoTurismoFVG, la pagina Panomax e i due JPEG sono raggiungibili. La pagina dichiara `preview_og.jpg` come immagine sociale e usa lo stesso ID camera per il fotogramma recente. |
| Freschezza osservata | Entrambi i JPEG riportavano `Last-Modified: Fri, 02 Oct 2026 05:10:14 GMT`, circa 48 secondi prima del controllo. Il singolo controllo conferma disponibilita' e ottima freschezza puntuale, non una garanzia di continuita'. E' un panorama aggiornato, non un flusso video. |
| Modalita' tecnica disponibile | Panorama web Panomax e JPEG HTTPS. Il catalogo v27 usa `preview_og.jpg` come snapshot e non configura `playerUrl`; la card conserva fallback locale, attribuzione e apertura della pagina Panomax dopo gesto dell'utente. Il player e' provabile soltanto nel pilot di sviluppo tramite il gate QA esplicito. |
| HTTPS, CORS e cache | `preview_og.jpg`: HTTPS, MIME `image/jpeg`, 130.568 byte, `ETag` e `Cache-Control: public, max-age=60`; `recent_reduced.jpg`: 203.435 byte, stessa freschezza e cache, HSTS. Nessun `Access-Control-Allow-Origin` osservato. Il caricamento in `<img>` non richiede lettura cross-origin dei pixel. |
| Attribuzione richiesta | `Panomax / PromoTurismoFVG`, con collegamento alla pagina Panomax della webcam. |
| Licenza o permesso noto | Nessun accordo privato noto. L'[imprint Panomax](https://www.panomax.com/en/imprint) riserva i contenuti e vieta utilizzi non autorizzati; la pagina di [content distribution](https://www.panomax.com/en/content-distribution) descrive app e partner come integrazioni approvate con API. La presenza nel catalogo PromoTurismoFVG prova identita' e provenienza, non trasferisce automaticamente diritti a Meteo Friul. |
| Stato | **Attiva come anteprima aggiornata per scelta editoriale revocabile; player non attivo in produzione; autorizzazione e continuita' da consolidare.** |
| Motivo e azione proposta | Fattibilita' tecnica alta, identita' ufficiale e fotogramma molto fresco al controllo. Mantenere attribuzione, link, refresh moderato, fallback e revoca indipendente; chiedere conferma PromoTurismoFVG/Panomax per consolidare il riuso. |

## Privacy, banda e continuita'

Il JPEG diretto evita script, cookie e risorse del player, ma comunica comunque
IP e metadati di rete al CDN Panomax. Il fotogramma scelto pesa circa 128 kB,
contro circa 199 kB del `recent_reduced.jpg`; riduce quindi la banda senza
introdurre proxy o archiviazione. Il player, se mai attivato fuori dal pilot,
richiedera' una decisione separata per privacy, cookie e autorizzazione.

## Collaudo Web nel pilot

Collaudo eseguito il 2 ottobre 2026 con il pilot canonico avviato tramite
`scripts/start-local-weather-pilot.ps1` sulla porta `5174`.

- l'endpoint locale espone il catalogo v27 con 29 webcam e il record
  `trieste-san-giusto` come `snapshot`;
- il JPEG Panomax e' stato caricato completo a `1200x630`, con badge `Ultima
  immagine disponibile`, attribuzione e collegamento alla fonte corretti;
- il dettaglio non contiene `iframe`: il player non viene caricato;
- il refresh manuale ha cambiato il parametro `mf_snapshot`, mantenendo
  l'immagine completa a `1200x630`; durante il cooldown il pulsante era
  disabilitato ed e' tornato disponibile dopo 12 secondi;
- non sono stati osservati errori o warning nella console del tab.

## Condizioni operative

- solo snapshot pubblico ridotto, senza proxy, archivio o player in produzione;
- attribuzione e collegamento alla pagina Panomax sempre disponibili;
- refresh ogni 10 minuti soltanto quando la preview e' visibile e l'app e' in
  primo piano; refresh manuale con cooldown di 12 secondi;
- fallback locale su errore e futura revoca indipendente per fonte;
- conferma PromoTurismoFVG/Panomax ancora consigliata per consolidare il riuso;
- collaudo Web di caricamento e refresh completato nel pilot; il fallback resta
  coperto dai test automatici;
- collaudo Android-browser o WebView da eseguire quando sara' disponibile un
  dispositivo o un emulatore configurato.
