# Webcam Forni di Sopra — verifica 1 ottobre 2026

## Decisione

`forni-varmost` usa l'**anteprima aggiornata** Panomax nel catalogo attivo, con
attribuzione, collegamento diretto alla pagina originale, fallback territoriale
e nessun player. La scelta editoriale applica lo stesso modello prudenziale gia'
adottato per Zoncolan: il fotogramma pubblico non viene presentato come licenza
o come video live e la fonte resta revocabile singolarmente.

## Verifica puntuale

Controllo eseguito il `2026-10-01T16:42:41Z` su fonti primarie.

| Campo | Esito |
| --- | --- |
| Localita' e identita' | Forni di Sopra, Malga Varmost. Il catalogo ufficiale PromoTurismoFVG elenca `Forni di Sopra`; la pagina Panomax corrisponde a `cam1987`. Non viene usato il nome Chianeit, che identifica una ripresa diversa. |
| Sorgente e URL ufficiale | [Catalogo webcam PromoTurismoFVG](https://www.turismofvg.it/it/webcam) e [pagina Panomax Forni di Sopra](https://fornidisopra.panomax.com/). Fotogrammi tecnicamente esposti da `https://live-image.panomax.com/cams/1987/recent_reduced.jpg` e `https://panodata.panomax.com/cams/1987/preview_og.jpg`. |
| Stato corrente | Pagina Panomax e i due JPEG hanno risposto HTTP `200`. |
| Freschezza osservata | Entrambi i JPEG riportavano `Last-Modified: Thu, 01 Oct 2026 16:39:34 GMT`, circa tre minuti prima del controllo. E' un panorama composto da scatti periodici, non un flusso video continuo. |
| Modalita' tecnica disponibile | Panorama web Panomax e JPEG HTTPS. Il catalogo v22 usa `preview_og.jpg` come snapshot e non configura `playerUrl`; la card conserva fallback locale, attribuzione e apertura della pagina Panomax dopo gesto dell'utente. |
| HTTPS, CORS e cache | `preview_og.jpg`: HTTPS, MIME `image/jpeg`, 63.463 byte, `ETag` e `Cache-Control: public, max-age=60`; `recent_reduced.jpg`: 216.851 byte con la stessa freschezza/cache. Nessun `Access-Control-Allow-Origin` osservato. |
| Attribuzione | `Panomax / PromoTurismoFVG`, con collegamento alla pagina Panomax della webcam. |
| Licenza o permesso noto | Nessun accordo privato noto. La presenza nel catalogo PromoTurismoFVG prova identita' e uso ufficiale da parte dell'ente, non trasferisce automaticamente diritti a Meteo Friul. I termini Panomax riservano i diritti a Panomax o ai licenzianti e la distribuzione ad app e partner resta un servizio approvato. |
| Stato | **Attiva come anteprima aggiornata; player non attivo; autorizzazione da consolidare.** |
| Motivo e azione proposta | Fattibilita' tecnica e qualita' alte, fonte fresca e identita' ufficiale. Mantenere attribuzione, link, refresh moderato e revoca; richiedere comunque conferma PromoTurismoFVG/Panomax per consolidare il riuso. |

## Privacy, banda e continuita'

Il JPEG diretto evita il codice del player ma comunica comunque IP e metadati di
rete al CDN Panomax. Il fotogramma scelto pesa circa 63 kB, contro circa 217 kB
del `recent_reduced.jpg`; riduce quindi la banda senza introdurre proxy o
archiviazione.

## Condizioni operative

- solo snapshot pubblico ridotto, senza proxy, archivio o player;
- attribuzione e collegamento alla pagina Panomax sempre disponibili;
- refresh ogni 10 minuti soltanto quando la preview e' visibile e l'app e' in
  primo piano; refresh manuale con cooldown di 12 secondi;
- fallback locale su errore e futura revoca indipendente per fonte;
- conferma PromoTurismoFVG/Panomax ancora consigliata per consolidare il riuso;
- collaudo del caricamento e della ripresa dopo background su telefono reale.
