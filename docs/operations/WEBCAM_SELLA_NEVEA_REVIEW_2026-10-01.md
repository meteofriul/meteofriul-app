# Webcam Sella Nevea — verifica 1 ottobre 2026

## Decisione

`sella-nevea-canin` usa l'**anteprima aggiornata** Panomax nel catalogo attivo,
con attribuzione, collegamento diretto alla pagina originale, fallback
territoriale e nessun player. E' una scelta editoriale revocabile: la
disponibilita' pubblica del fotogramma non viene presentata come licenza o
autorizzazione al riuso, mentre la continuita' va ricontrollata di giorno.

## Verifica puntuale

Controllo eseguito il `2026-10-01T18:32:21Z` su fonti primarie.

| Campo | Esito |
| --- | --- |
| Localita' e identita' | Sella Nevea, Comune di Chiusaforte, nel contesto del gruppo del Monte Canin. La pagina Panomax dichiara `camId = 1984`; il catalogo ufficiale PromoTurismoFVG elenca separatamente `Sella Nevea` e `Sella Nevea - Campi scuola`. Il record Meteo Friul si riferisce alla prima. |
| Sorgente e URL ufficiale | [Catalogo webcam PromoTurismoFVG](https://www.turismofvg.it/it/webcam) e [pagina Panomax Sella Nevea](https://sellanevea.panomax.com/). Fotogrammi tecnicamente esposti da `https://live-image.panomax.com/cams/1984/recent_reduced.jpg` e `https://panodata.panomax.com/cams/1984/preview_og.jpg`. |
| Stato corrente | Il catalogo PromoTurismoFVG continua a elencare Sella Nevea. La pagina Panomax e i due JPEG hanno risposto HTTP `200`; il markup pubblica `preview_og.jpg` come immagine sociale. |
| Freschezza osservata | Entrambi i JPEG riportavano `Last-Modified: Thu, 01 Oct 2026 17:06:39 GMT`, circa 86 minuti prima del controllo serale. Il singolo controllo conferma disponibilita' ma non una cadenza continua; verificare nuovamente in orario diurno. E' un panorama periodico, non un flusso video. |
| Modalita' tecnica disponibile | Panorama web Panomax e JPEG HTTPS. Il catalogo v25 usa `preview_og.jpg` come snapshot e non configura `playerUrl`; la card conserva fallback locale, attribuzione e apertura della pagina Panomax dopo gesto dell'utente. |
| HTTPS, CORS e cache | `preview_og.jpg`: HTTPS, MIME `image/jpeg`, 73.772 byte, `ETag` e `Cache-Control: public, max-age=60`; `recent_reduced.jpg`: 161.187 byte con la stessa freschezza e cache. Nessun `Access-Control-Allow-Origin` osservato. |
| Attribuzione | `Panomax / PromoTurismoFVG`, con collegamento alla pagina Panomax della webcam. |
| Licenza o permesso noto | Nessun accordo privato noto. L'imprint Panomax vieta gli usi non autorizzati, inclusi download, riproduzione, uso commerciale e distribuzione; la pagina di distribuzione descrive app e partner come usi approvati tramite API. La presenza nel catalogo PromoTurismoFVG prova identita' e provenienza, non trasferisce automaticamente diritti a Meteo Friul. |
| Stato | **Attiva come anteprima aggiornata per scelta editoriale revocabile; player non attivo; autorizzazione e continuita' da consolidare.** |
| Motivo e azione proposta | Fattibilita' tecnica alta e identita' ufficiale. Mantenere attribuzione, link, refresh moderato e revoca; chiedere conferma PromoTurismoFVG/Panomax e ricontrollare la freschezza in orario diurno. |

## Privacy, banda e continuita'

Il JPEG diretto evita il codice del player ma comunica comunque IP e metadati
di rete al CDN Panomax. Il fotogramma scelto pesa circa 74 kB, contro circa
161 kB del `recent_reduced.jpg`; riduce quindi la banda senza introdurre proxy
o archiviazione.

## Condizioni operative

- solo snapshot pubblico ridotto, senza proxy, archivio o player;
- attribuzione e collegamento alla pagina Panomax sempre disponibili;
- refresh ogni 10 minuti soltanto quando la preview e' visibile e l'app e' in
  primo piano; refresh manuale con cooldown di 12 secondi;
- fallback locale su errore e futura revoca indipendente per fonte;
- conferma PromoTurismoFVG/Panomax ancora consigliata per consolidare il riuso;
- ricontrollo della freschezza in orario diurno;
- collaudo del caricamento e della ripresa dopo background su telefono reale.
