# Webcam Marina Monfalcone — verifica 30 settembre 2026

## Decisione

`monfalcone-marina` resta **solo collegamento** alla pagina proprietaria di
Marina Monfalcone. Non vengono aggiunti `imageUrl` o `playerUrl` al catalogo
attivo.

La sorgente e' tecnicamente integrabile e corrente, ma l'autorizzazione al
riuso non e' dimostrata. I termini pubblicati da Marina Monfalcone vietano la
riproduzione, distribuzione e visualizzazione pubblica dei contenuti senza
consenso scritto. Panomax descrive inoltre la distribuzione verso app e partner
come un accesso approvato. L'embed presente sul sito proprietario non trasferisce
questa autorizzazione a Meteo Friûl.

## Verifica puntuale

Controllo eseguito il `2026-09-30T19:08:18Z` su fonti primarie.

| Campo | Esito |
| --- | --- |
| Localita' e identita' | Spiaggia di Marina Monfalcone, Marina Monfalcone S.r.l., Via Bagni Nuova 41, Monfalcone. Non vengono assegnate coordinate precise alla camera: le coordinate pubblicate sul sito identificano la struttura, non il punto di ripresa. |
| Sorgente e URL ufficiale | [Pagina webcam Marina Monfalcone](https://marinamonfalcone.com/it/webcam/), che incorpora `https://marinamonfalcone.panomax.com`. Istanza Panomax osservata come `cam10949`. |
| Stato corrente | Pagina proprietaria HTTP `200`; istanza Panomax HTTP `200`; JPEG di anteprima HTTP `200`. |
| Freschezza osservata | JPEG `Last-Modified: Wed, 30 Sep 2026 19:05:21 GMT`, verificato meno di tre minuti dopo. E' un panorama aggiornato, non un flusso video continuo. |
| Modalita' tecnica candidata | Snapshot HTTPS diretto `https://live-image.panomax.com/cams/10949/recent_reduced.jpg`, oppure iframe Panomax caricato solo dopo gesto e consenso. Entrambe restano inattive. |
| HTTPS, CORS e cache | JPEG HTTPS con HSTS, MIME `image/jpeg`, `1800x450`, 32.386 byte, `ETag` e `Cache-Control: public, max-age=60`; nessun `Access-Control-Allow-Origin` osservato. E' visualizzabile come `<img>`, ma non leggibile da canvas cross-origin. |
| Attribuzione richiesta | `Marina Monfalcone · Panomax`, con collegamento prioritario alla pagina proprietaria. |
| Licenza o permesso noto | Nessun accordo privato noto. I [termini Marina Monfalcone](https://marinamonfalcone.com/it/terms-of-use/) richiedono consenso scritto per riproduzione o visualizzazione pubblica; i [termini Panomax](https://www.panomax.com/en/terms-of-use) riservano i diritti a Panomax o ai licenzianti e non consentono al cliente di trasferirli a terzi fuori dall'ambito concordato. La [distribuzione Panomax](https://www.panomax.com/en/content-distribution) verso app e partner e' descritta come approvata. |
| Stato | **Bloccata per snapshot/player; attiva come collegamento.** |
| Motivo e azione proposta | Fattibilita' tecnica alta e continuita' corrente buona, ma autorizzazione assente. Conservare fallback e link. Abilitare una preview solo dopo consenso scritto di Marina Monfalcone e conferma dell'ambito Panomax per app terza. |

## Privacy e terze parti

La pagina proprietaria blocca l'iframe Panomax con Borlabs Cookie finche'
l'utente non accetta il servizio e avverte che l'indirizzo IP puo' essere
condiviso con fornitori terzi. La relativa [privacy policy](https://marinamonfalcone.com/it/privacy-policy/)
spiega l'uso del gestore del consenso. Questo rende il player inadatto a un
caricamento automatico nell'app.

Lo snapshot diretto evita script, iframe e storage del player, ma comunica
comunque IP e metadati di rete a `live-image.panomax.com`. Un eventuale uso
futuro dovra' mantenere `referrerPolicy="no-referrer"`, caricamento solo quando
la preview e' visibile, refresh controllato e revoca per singola webcam. Queste
cautele riducono l'impatto privacy e di banda, ma non sostituiscono il permesso.

## Risorse tecniche conservate

Le risorse snapshot e player restano documentate per evitare una nuova ricerca
se arrivera' l'autorizzazione. Non vengono inviate al frontend finche' la voce
rimane link-only. In caso di futura attivazione, l'etichetta corretta e'
**Panorama aggiornato**, non **Video in diretta**.
