# Revisione webcam Udine — 29 settembre 2026

## Decisione

La voce `udine-piazza-matteotti` viene ritirata dal catalogo attivo. Non viene
rinominata: la ripresa di Corte San Giacomo e il panorama dalla Specola del
Castello sono due webcam diverse.

La nuova voce è `udine-panorama-castello`, con nome **Udine — Panorama dal
Castello** e area **Specola del Castello**. Il riferimento ufficiale del Comune
di Udine identifica la ripresa e dichiara la collaborazione con PromoTurismoFVG;
il collegamento comunale apre l'istanza Panomax che eroga effettivamente il
panorama.

## Verifica puntuale

Controllo eseguito il **29 settembre 2026 alle 20:12 CEST**.

| Elemento | Esito osservato |
| --- | --- |
| Pagina Corte San Giacomo | Timeout dopo 15 secondi sia sull'host principale sia su `www` |
| Ultimo JPEG noto Corte San Giacomo | Timeout dopo 15 secondi |
| API locale Meteo Friûl | Voce Udine `degraded`, senza `imageUrl`, con fallback territoriale |
| Pagina Comune di Udine | Raggiungibile; identifica la webcam dalla Specola e collega `udine.panomax.com` |
| Pagina Panomax Udine | HTTP 200; istanza `cam2859` |
| JPEG anteprima Panomax | HTTP 200, JPEG HTTPS 1200×630, 43.579 byte |
| Freschezza JPEG | `Last-Modified: 29/09/2026 19:20:05 CEST` |
| Cache | `Cache-Control: max-age=60, public`, `ETag` e `Accept-Ranges` presenti |
| CORS | Nessun `Access-Control-Allow-Origin` osservato; non serve per un elemento `img` |

Il Comune specifica che la webcam riprende il panorama **dall'alba al
tramonto**. L'ultimo fotogramma serale può quindi restare invariato durante la
notte senza indicare automaticamente un guasto.

## Integrazione

- anteprima diretta 1200×630, preferita al panorama completo perché leggibile
  nella card 16:9: `https://panodata.panomax.com/cams/2859/preview_og.jpg`;
- pagina aperta dall'app: `https://udine.panomax.com/`;
- riferimento unico visibile:
  **Comune di Udine · PromoTurismoFVG · Panomax**;
- tipo: snapshot/panorama aggiornato, non video in diretta;
- nessun iframe, player, script Panomax o cookie di terze parti caricato dentro
  Meteo Friûl;
- fallback territoriale di Udine conservato;
- refresh controllato dal supporto snapshot già esistente.

La pagina informativa del Comune resta l'evidenza documentale primaria:
<https://www.comune.udine.it/Novita/Notizie/Webcam-panoramica>.

## Riuso e attribuzione

Non viene dichiarato alcun accordo privato con Comune, PromoTurismoFVG o
Panomax. La scelta editoriale del progetto è mostrare l'anteprima pubblica con
attribuzione esplicita e apertura della pagina che offre la webcam. La
raggiungibilità tecnica dell'immagine non viene descritta come trasferimento di
licenza.

## Modifiche tecniche collegate

Il resolver `corte-san-giacomo`, il relativo campo interno, il modulo dedicato e
i test esclusivi vengono rimossi: non erano condivisi con altre webcam. Il
catalogo mantiene 28 voci e passa alla versione 14.

Prima del commit sono stati completati controllo del manifest, collaudo visivo
nel pilot canonico sulla porta 5174, 58 test backend webcam, 1.312 test backend
complessivi e 144 test frontend mirati. Il comportamento dopo
background/ripresa resta da verificare successivamente sul telefono reale.

Il successivo controllo amministrativo delle anteprime è descritto in
[WEBCAM_CONTROL_PLANE.md](./WEBCAM_CONTROL_PLANE.md). È un livello backend
separato: non modifica la decisione editoriale o la fonte della webcam di Udine
e non richiede un nuovo contratto pubblico per gli APK esistenti.
