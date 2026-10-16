# Webcam San Daniele del Friuli — verifica 1 ottobre 2026

## Decisione

`san-daniele-centro` usa l'**anteprima aggiornata** Panomax nel catalogo attivo,
con attribuzione, collegamento diretto alla pagina originale, fallback
territoriale e nessun player. Il player Panomax resta censito come opzione
tecnica inattiva e non viene caricato automaticamente. E' una scelta editoriale
revocabile: la disponibilita' pubblica del fotogramma non viene presentata come
licenza o autorizzazione al riuso.

## Verifica puntuale

Controllo eseguito il `2026-10-01T18:46:02Z` su fonti primarie.

| Campo | Esito |
| --- | --- |
| Localita' e identita' | San Daniele del Friuli, ripresa panoramica del centro. La pagina specifica dichiara `camId = 9495` e il catalogo ufficiale PromoTurismoFVG elenca `San Daniele del Friuli` come voce autonoma. |
| Sorgente e URL ufficiale | [Catalogo webcam PromoTurismoFVG](https://www.turismofvg.it/it/webcam) e [pagina Panomax San Daniele del Friuli](https://sandanieledelfriuli.panomax.com/). Fotogrammi tecnicamente esposti da `https://live-image.panomax.com/cams/9495/recent_reduced.jpg` e `https://panodata.panomax.com/cams/9495/preview_og.jpg`. |
| Stato corrente | La voce PromoTurismoFVG, la pagina Panomax e i due JPEG sono raggiungibili. La pagina dichiara `preview_og.jpg` come immagine sociale e usa lo stesso ID camera per il fotogramma recente. |
| Freschezza osservata | Entrambi i JPEG riportavano `Last-Modified: Thu, 01 Oct 2026 17:42:33 GMT`, circa 63 minuti prima del controllo serale. Il singolo controllo conferma disponibilita' ma non una cadenza continua. E' un panorama periodico, non un flusso video. |
| Modalita' tecnica disponibile | Panorama web Panomax e JPEG HTTPS. Il catalogo v26 usa `preview_og.jpg` come snapshot e non configura `playerUrl`; la card conserva fallback locale, attribuzione e apertura della pagina Panomax dopo gesto dell'utente. Il player resta verificabile soltanto come opzione separata. |
| HTTPS, CORS e cache | `preview_og.jpg`: HTTPS, MIME `image/jpeg`, 44.950 byte, `ETag` e `Cache-Control: public, max-age=60`; `recent_reduced.jpg`: 202.288 byte con la stessa freschezza e cache. Nessun `Access-Control-Allow-Origin` osservato. |
| Attribuzione | `Panomax / PromoTurismoFVG`, con collegamento alla pagina Panomax della webcam. |
| Licenza o permesso noto | Nessun accordo privato noto. L'imprint Panomax vieta gli usi non autorizzati, inclusi download, riproduzione, uso commerciale e distribuzione; la pagina di distribuzione descrive app e partner come usi approvati tramite API. La presenza nel catalogo PromoTurismoFVG prova identita' e provenienza, non trasferisce automaticamente diritti a Meteo Friul. |
| Stato | **Attiva come anteprima aggiornata per scelta editoriale revocabile; player non attivo; autorizzazione e continuita' da consolidare.** |
| Motivo e azione proposta | Fattibilita' tecnica alta e identita' ufficiale. Mantenere attribuzione, link, refresh moderato e revoca; chiedere conferma PromoTurismoFVG/Panomax e ricontrollare la freschezza in orario diurno. |

## Privacy, banda e continuita'

Il JPEG diretto evita il codice del player ma comunica comunque IP e metadati
di rete al CDN Panomax. Il fotogramma scelto pesa circa 45 kB, contro circa
202 kB del `recent_reduced.jpg`; riduce quindi la banda senza introdurre proxy
o archiviazione. Il player, se mai attivato, richiedera' una decisione separata
per privacy, cookie e autorizzazione.

## Collaudo Android reale

Collaudo eseguito la sera del 1 ottobre 2026 su Samsung SM-A525F con Brave,
aprendo il pilot locale tramite `adb reverse tcp:5174 tcp:5174`. E' una prova
del frontend Web su Android reale, non una build Capacitor e non una
distribuzione.

- la card San Daniele ha caricato il JPEG Panomax completo a `1200x630`, con
  badge `Ultima immagine disponibile`, attribuzione e link alla fonte;
- il documento non conteneva `iframe`: il player non e' stato caricato;
- dopo il passaggio al launcher e 15 secondi in background, Brave ha ripreso la
  stessa attivita' in stato `HOT`, mantenendo card, immagine, attribuzione e
  collegamento;
- il refresh manuale ha cambiato il parametro `mf_snapshot`, lasciando
  l'immagine completa a `1200x630`; il pulsante era disabilitato durante il
  cooldown e nuovamente disponibile dopo 12 secondi;
- la sospensione del timer automatico quando il documento non e' visibile resta
  coperta dai test automatici; il collaudo fisico conferma la ripresa della UI e
  del contenuto dopo un reale cambio foreground/background.

## Condizioni operative

- solo snapshot pubblico ridotto, senza proxy, archivio o player;
- attribuzione e collegamento alla pagina Panomax sempre disponibili;
- refresh ogni 10 minuti soltanto quando la preview e' visibile e l'app e' in
  primo piano; refresh manuale con cooldown di 12 secondi;
- fallback locale su errore e futura revoca indipendente per fonte;
- conferma PromoTurismoFVG/Panomax ancora consigliata per consolidare il riuso;
- ricontrollo della freschezza in orario diurno;
- collaudo Web e Android-browser del caricamento e della ripresa completato;
  un'eventuale verifica nella WebView Capacitor richiedera' un artefatto Android
  successivo e non e' necessaria per questa modifica solo-catalogo.
