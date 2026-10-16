# Webcam Sappada — verifica 1 ottobre 2026

## Decisione

`sappada-panorama` usa l'**anteprima aggiornata** Panomax nel catalogo attivo,
con attribuzione, collegamento diretto alla pagina originale, fallback
territoriale e nessun player. E' la stessa scelta editoriale revocabile gia'
adottata per Zoncolan, Forni di Sopra e Piancavallo: l'accessibilita' pubblica
del fotogramma non viene presentata come licenza o autorizzazione al riuso.

## Verifica puntuale

Controllo eseguito il `2026-10-01T18:21:12Z` su fonti primarie.

| Campo | Esito |
| --- | --- |
| Localita' e identita' | Sappada, panorama del paese. La pagina Panomax dichiara `camId = 1894`; il catalogo ufficiale PromoTurismoFVG elenca separatamente la webcam `Sappada`. |
| Sorgente e URL ufficiale | [Catalogo webcam PromoTurismoFVG](https://www.turismofvg.it/it/webcam) e [pagina Panomax Sappada](https://sappada.panomax.com/). Fotogrammi tecnicamente esposti da `https://live-image.panomax.com/cams/1894/recent_reduced.jpg` e `https://panodata.panomax.com/cams/1894/preview_og.jpg`. |
| Stato corrente | Il catalogo PromoTurismoFVG continua a elencare Sappada. La pagina Panomax e i due JPEG hanno risposto HTTP `200`; il markup pubblica `preview_og.jpg` come immagine sociale. |
| Freschezza osservata | Entrambi i JPEG riportavano `Last-Modified: Thu, 01 Oct 2026 17:29:14 GMT`, circa 52 minuti prima del controllo serale. E' un panorama composto da scatti periodici, non un flusso video continuo. |
| Modalita' tecnica disponibile | Panorama web Panomax e JPEG HTTPS. Il catalogo v24 usa `preview_og.jpg` come snapshot e non configura `playerUrl`; la card conserva fallback locale, attribuzione e apertura della pagina Panomax dopo gesto dell'utente. |
| HTTPS, CORS e cache | `preview_og.jpg`: HTTPS, MIME `image/jpeg`, 44.744 byte, `ETag` e `Cache-Control: public, max-age=60`; `recent_reduced.jpg`: 118.617 byte con la stessa freschezza e cache. Nessun `Access-Control-Allow-Origin` osservato. |
| Attribuzione | `Panomax / PromoTurismoFVG`, con collegamento alla pagina Panomax della webcam. |
| Licenza o permesso noto | Nessun accordo privato noto. L'imprint Panomax vieta gli usi non autorizzati, inclusi download, riproduzione, uso commerciale e distribuzione; la pagina di distribuzione descrive app e partner come usi approvati tramite API. La presenza nel catalogo PromoTurismoFVG prova identita' e provenienza, non trasferisce automaticamente diritti a Meteo Friul. |
| Stato | **Attiva come anteprima aggiornata per scelta editoriale revocabile; player non attivo; autorizzazione da consolidare.** |
| Motivo e azione proposta | Fattibilita' tecnica e qualita' alte, fonte corrente e identita' ufficiale. Mantenere attribuzione, link, refresh moderato e revoca; chiedere conferma PromoTurismoFVG/Panomax per consolidare il riuso. |

## Privacy, banda e continuita'

Il JPEG diretto evita il codice del player ma comunica comunque IP e metadati
di rete al CDN Panomax. Il fotogramma scelto pesa circa 45 kB, contro circa
119 kB del `recent_reduced.jpg`; riduce quindi la banda senza introdurre proxy
o archiviazione.

## Condizioni operative

- solo snapshot pubblico ridotto, senza proxy, archivio o player;
- attribuzione e collegamento alla pagina Panomax sempre disponibili;
- refresh ogni 10 minuti soltanto quando la preview e' visibile e l'app e' in
  primo piano; refresh manuale con cooldown di 12 secondi;
- fallback locale su errore e futura revoca indipendente per fonte;
- conferma PromoTurismoFVG/Panomax ancora consigliata per consolidare il riuso;
- collaudo del caricamento e della ripresa dopo background su telefono reale.
