# Webcam Tarvisio - Piazza Unita' — verifica 1 ottobre 2026

## Decisione

`tarvisio-piazza-chiesa` resta nel catalogo attivo come **collegamento alla
pagina webcam del Comune e fallback territoriale**, senza fotografia o player
caricati automaticamente. Il Comune di Tarvisio conferma la provenienza della
ripresa e rimanda a WhatsUpCams; i termini WUC richiedono comunque
autorizzazione scritta per ripubblicazione o framing.

## Verifica puntuale

Controllo eseguito il `2026-10-01T15:10:18Z` su fonti primarie.

| Campo | Esito |
| --- | --- |
| Localita' e identita' | Piazza Unita' d'Italia, centro di Tarvisio, con la Chiesa dei Santi Pietro e Paolo. Il nome catalogo `Piazza Chiesa` identifica la stessa veduta, ma la formula piu' precisa per una futura UI e' `Piazza Unita' · Chiesa SS. Pietro e Paolo`. Coordinate riferite alla piazza, non alla posizione esatta della camera. |
| Sorgente e URL ufficiale | [Pagina webcam del Comune di Tarvisio](https://tarvisio.comune.digital/webcam), che collega la [pagina specifica WhatsUpCams](https://www.whatsupcams.com/it/webcams/italia/friuli-venezia-giulia-it/tarvisio-it/tarvisio-piazza-unita-parrocchia-sspietro-e-paolo-apostoli/). Risorse tecniche: widget `https://services.whatsupcams.com/wgt/it_tarvisio01` e JPEG `https://cdn.whatsupcams.com/snapshot/it_tarvisio01.jpg`. |
| Stato corrente | Pagina comunale, pagina WUC, widget e JPEG hanno risposto HTTP `200`. La pagina comunale usa un pulsante grafico e apre WUC, senza incorporare il player. |
| Freschezza osservata | Il JPEG riportava `Last-Modified: Thu, 01 Oct 2026 15:06:56 GMT`, circa tre minuti prima del controllo. E' un fotogramma aggiornato; la pagina WUC offre anche la diretta, che resta una modalita' distinta. |
| Modalita' tecnica disponibile | JPEG HTTPS diretto, widget iframe e player WUC. Il catalogo Meteo Friûl non configura `imageUrl` o `playerUrl`; mostra il fallback comunale e apre la pagina ufficiale solo su gesto. |
| HTTPS, CORS e cache | JPEG HTTPS, MIME `image/jpeg`, 126.138 byte, `ETag`, `Last-Modified`, HSTS e cache CDN osservata come `EXPIRED`; nessun `Access-Control-Allow-Origin`, `Cache-Control` o `Expires` osservato. Widget HTML HTTPS. |
| Attribuzione richiesta | In caso di futura autorizzazione: `Comune di Tarvisio · WhatsUpCams`, con collegamento prioritario alla pagina comunale e riferimento specifico WUC. |
| Licenza o permesso noto | Nessun accordo privato noto. Il collegamento del Comune conferma la fonte, ma non trasferisce a Meteo Friûl i diritti di ripubblicazione. I [termini WhatsUpCams](https://www.whatsupcams.com/fr/terms-of-use/) limitano il visitatore alla visione personale non commerciale e vietano senza autorizzazione scritta riproduzione, visualizzazione pubblica e framing. |
| Stato | **Bloccata per snapshot/player; attiva come solo link.** |
| Motivo e azione proposta | Fattibilita' tecnica alta, identita' ufficiale e sorgente fresca; autorizzazione per l'app assente. Conservare link comunale e fallback. Per attivare un'anteprima o il player, chiedere permesso scritto a WhatsUpCams e conferma al Comune sulla formula di credito. |

## Privacy, banda e continuita'

Il solo collegamento non invia dati a WUC prima del gesto dell'utente. Widget o
player incorporati invierebbero IP e metadati al fornitore e potrebbero usare
cookie, pixel e servizi pubblicitari descritti nella [privacy policy
WhatsUpCams](https://www.whatsupcams.com/fr/privacy-policy/). Uno snapshot
eviterebbe script e cookie del player, ma resterebbe una richiesta automatica
al CDN e non risolverebbe i diritti.

## Criteri per un'eventuale attivazione

- permesso scritto per Web e Android, specifico per snapshot e/o player;
- attribuzione e collegamento concordati con Comune e WhatsUpCams;
- player caricato solo su gesto e previa verifica privacy;
- snapshot solo quando visibile, senza archivio, con refresh moderato;
- fallback e revoca indipendente;
- collaudo Web e sul telefono reale, inclusa ripresa dal background.
