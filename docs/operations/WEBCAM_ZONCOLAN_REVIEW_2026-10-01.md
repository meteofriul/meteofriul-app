# Webcam Monte Zoncolan — verifica 1 ottobre 2026

## Decisione

`zoncolan-panorama` usa l'**anteprima aggiornata** Panomax nel catalogo attivo,
con attribuzione, collegamento diretto alla pagina originale, fallback
territoriale e nessun player. La scelta editoriale del 1 ottobre 2026 accetta il
rischio residuo del fotogramma pubblico senza presentarlo come licenza o come
video live; la fonte resta revocabile e sostituibile singolarmente.

## Verifica puntuale

Controllo eseguito il `2026-10-01T15:05:19Z` su fonti primarie.

| Campo | Esito |
| --- | --- |
| Localita' e identita' | Monte Zoncolan, area indicata nel catalogo come quota 1.750 m e Comune di Sutrio. Il catalogo webcam ufficiale PromoTurismoFVG elenca separatamente `Zoncolan`; la pagina Panomax corrisponde a `cam1988`. Non viene riutilizzata l'identita' della vecchia e diversa camera Baita Goles. |
| Sorgente e URL ufficiale | [Catalogo webcam PromoTurismoFVG](https://www.turismofvg.it/it/webcam) e [pagina Panomax Zoncolan](https://zoncolan.panomax.com/). Fotogrammi tecnicamente esposti da `https://live-image.panomax.com/cams/1988/recent_reduced.jpg` e `https://panodata.panomax.com/cams/1988/preview_og.jpg`. |
| Stato corrente | Pagina Panomax e i due JPEG hanno risposto HTTP `200`. Il markup della pagina identifica l'istanza e pubblica `preview_og.jpg` nei metadati sociali. |
| Freschezza osservata | Entrambi i JPEG riportavano `Last-Modified: Thu, 01 Oct 2026 15:02:48 GMT`, circa due minuti e mezzo prima del controllo. E' un panorama composto da scatti periodici, non un flusso video continuo. |
| Modalita' tecnica disponibile | Panorama web Panomax con funzioni embed e JPEG HTTPS. Il catalogo v21 usa `preview_og.jpg` come snapshot; non configura `playerUrl`. La card conserva fallback locale, attribuzione e apertura della pagina Panomax dopo gesto dell'utente. |
| HTTPS, CORS e cache | `recent_reduced.jpg`: HTTPS, MIME `image/jpeg`, 177.649 byte, `ETag`, HSTS e `Cache-Control: public, max-age=60`; `preview_og.jpg`: 66.081 byte e stessa freschezza/cache. Nessun `Access-Control-Allow-Origin` osservato. |
| Attribuzione richiesta | In caso di futura autorizzazione: `PromoTurismoFVG · Panomax`, con collegamento alla pagina ufficiale concordata e mantenimento dei crediti Panomax. |
| Licenza o permesso noto | Nessun accordo privato noto. La presenza nel sito PromoTurismoFVG prova identita' e uso ufficiale da parte dell'ente, non un trasferimento di diritti a terzi. I [termini Panomax](https://www.panomax.com/en/terms-of-use) riservano i diritti a Panomax o ai licenzianti e limitano l'uso del cliente allo scopo concordato; la pagina [Content Distribution](https://www.panomax.com/en/content-distribution) descrive API e distribuzione ad app tramite partner approvati, con accesso scelto e configurato. |
| Stato | **Attiva come anteprima aggiornata; player non attivo; autorizzazione da consolidare.** |
| Motivo e azione proposta | Fattibilita' tecnica e qualita' alte, fonte fresca e identita' ufficiale. L'autorizzazione per Meteo Friûl non e' dimostrata: mantenere attribuzione, link, refresh moderato e revoca; chiedere comunque a PromoTurismoFVG/Panomax di consolidare il riuso. |

## Privacy, banda e continuita'

Il solo link evita contatti con Panomax finche' l'utente non apre la fonte. Un
player incorporato caricherebbe codice e servizi Panomax e, tramite la mappa del
panorama, puo' coinvolgere ulteriori domini; richiede quindi anche una verifica
privacy/cookie prima dell'attivazione. Il JPEG diretto ridurrebbe tale impatto,
ma comunicherebbe comunque IP e metadati di rete al CDN e non risolve il tema
dei diritti.

Il fotogramma ridotto osservato pesa circa 178 kB e dichiara cache di un minuto.
Un'eventuale anteprima autorizzata dovra' caricarsi solo quando visibile, usare
refresh moderato, `referrerPolicy="no-referrer"`, fallback locale e revoca
indipendente.

## Condizioni operative dell'attivazione editoriale

- solo snapshot pubblico ridotto, senza proxy, archivio o player;
- attribuzione e collegamento alla pagina Panomax sempre disponibili;
- refresh ogni 10 minuti soltanto quando la preview e' visibile e l'app e' in
  primo piano; refresh manuale con cooldown di 12 secondi;
- fallback locale su errore e futura revoca indipendente per fonte;
- conferma PromoTurismoFVG/Panomax ancora consigliata per consolidare il riuso;
- collaudo del caricamento e della ripresa dopo background su telefono reale.
