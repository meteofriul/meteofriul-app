# Webcam Trieste - Piazza della Borsa — verifica 1 ottobre 2026

## Decisione

`trieste-piazza-borsa` resta nel catalogo attivo come **collegamento alla fonte
e fallback territoriale**, senza caricare automaticamente fotografia o player.
La fonte e' tecnicamente corrente, ma i termini WhatsUpCams non autorizzano la
ripubblicazione nell'app: disponibilita' pubblica, HTTPS e incorporabilita' non
sono una licenza.

## Verifica puntuale

Controllo eseguito il `2026-10-01T15:05:19Z` su fonti primarie.

| Campo | Esito |
| --- | --- |
| Localita' e identita' | Piazza della Borsa, Comune di Trieste. La pagina WhatsUpCams identifica la ripresa come `Trieste - Borsa square webcam live`; le coordinate del catalogo puntano alla piazza e non vengono presentate come posizione esatta della camera. |
| Sorgente e URL ufficiale | [Pagina specifica WhatsUpCams](https://www.whatsupcams.com/it/webcams/italia/friuli-venezia-giulia-it/trieste-it/piazza-della-borsa/); widget pubblico `https://services.whatsupcams.com/wgt/it_tsborsa`; fotografia esposta dal widget `https://cdn.whatsupcams.com/snapshot/it_tsborsa.jpg`. |
| Stato corrente | Pagina, widget e JPEG hanno risposto HTTP `200`. Il widget usa lo stesso JPEG come sfondo e rimanda alla pagina WhatsUpCams. |
| Freschezza osservata | Il JPEG riportava `Last-Modified: Thu, 01 Oct 2026 14:58:14 GMT`, circa sette minuti prima del controllo. E' un fotogramma aggiornato, non prova di continuita' futura e non va chiamato video live nell'anteprima. |
| Modalita' tecnica disponibile | JPEG HTTPS diretto, widget iframe e player sulla pagina sorgente sono raggiungibili. Nel catalogo non sono configurati `imageUrl`, `playerUrl` o proxy: la card usa la fotografia territoriale locale e apre la fonte esterna su gesto dell'utente. |
| HTTPS, CORS e cache | JPEG HTTPS, MIME `image/jpeg`, 66.840 byte, `ETag`, `Last-Modified`, HSTS e cache CDN osservata come `HIT`; non sono stati osservati `Access-Control-Allow-Origin`, `Cache-Control` o `Expires`. Il widget e' HTML HTTPS. |
| Attribuzione richiesta | In caso di futura autorizzazione: `WhatsUpCams`, con collegamento alla pagina specifica e senza rimuovere marchi o crediti del player. Oggi il provider e la pagina sorgente restano nel catalogo link-only. |
| Licenza o permesso noto | Nessun accordo privato noto. I [termini WhatsUpCams](https://www.whatsupcams.com/fr/terms-of-use/) concedono al visitatore una licenza personale, limitata, revocabile e non commerciale per la visione; vietano senza autorizzazione scritta riproduzione, pubblicazione, visualizzazione pubblica e framing in un altro sito o servizio. |
| Stato | **Bloccata per snapshot/player; attiva come solo link.** |
| Motivo e azione proposta | Fattibilita' tecnica alta e fonte fresca; autorizzazione al riuso assente e condizioni esplicitamente restrittive; continuita' non garantita. Conservare link e fallback, non interrogare automaticamente CDN/widget, chiedere autorizzazione scritta a S3MEA/WhatsUpCams prima di qualunque anteprima o player. |

## Privacy, banda e revoca

Il solo link non contatta WhatsUpCams finche' l'utente non decide di aprire la
pagina esterna. Un iframe o player, invece, comunicherebbe almeno indirizzo IP,
dispositivo e pagina richiesta al fornitore; la [privacy policy
WhatsUpCams](https://www.whatsupcams.com/fr/privacy-policy/) descrive inoltre
cookie, pixel e pubblicita' di terze parti. Per questo il player non deve essere
precaricato come anteprima.

Lo snapshot isolato ridurrebbe cookie e JavaScript, ma resterebbe una richiesta
automatica al CDN del fornitore e, soprattutto, una ripubblicazione non
autorizzata. HTTPS, dimensione ridotta e cache CDN non cambiano il risultato sui
diritti.

## Criteri per un'eventuale attivazione

- autorizzazione scritta che copra espressamente app Web/Android e anteprima o
  player scelto;
- formula di attribuzione e collegamento concordati;
- caricamento solo quando la card e' visibile, senza archivio o copia
  persistente;
- informativa privacy aggiornata prima di incorporare un player;
- fallback e revoca indipendente per questa webcam;
- ricontrollo della freschezza e collaudo Web/telefono reale.
