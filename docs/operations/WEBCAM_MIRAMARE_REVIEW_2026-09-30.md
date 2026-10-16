# Webcam Trieste - Parco di Miramare — verifica 30 settembre 2026

## Decisione

`trieste-miramare` viene configurata nel ramo webcam come **anteprima
fotografica aggiornata e revocabile**. La card carica il JPEG pubblico esposto
dalla pagina Meteo System, mostra l'attribuzione `Meteo System` e conserva sia
il collegamento alla pagina ufficiale sia il fallback territoriale locale.

L'attivazione non viene descritta come prova di un'autorizzazione: non e' stata
individuata una licenza pubblica specifica per il riuso. E' la scelta editoriale
concordata per le anteprime pubbliche, mantenuta tecnicamente separabile e
disattivabile per singola fonte. Non vengono incorporati player, script, cookie
o archivio storico.

## Verifica puntuale

Controllo eseguito il `2026-09-30T19:11:41Z` su fonti primarie.

| Campo | Esito |
| --- | --- |
| Localita' e identita' | Parco del Castello di Miramare, localita' Grignano, Comune di Trieste. La pagina Meteo System identifica esplicitamente la ripresa come `Webcam Parco del Castello di Miramare`. Non vengono assegnate coordinate puntuali non pubblicate dal gestore. |
| Sorgente e URL ufficiale | [Pagina webcam Meteo System](https://www.meteosystem.com/stazione/trieste-miramare/webcam.php); JPEG pubblico `https://www.meteosystem.com/webcam/miramare/parco_miramare.jpg`. |
| Stato corrente | Pagina e JPEG HTTP `200`; la pagina ufficiale richiama direttamente lo stesso JPEG. |
| Freschezza osservata | `Last-Modified: Wed, 30 Sep 2026 19:11:41 GMT` al controllo. E' una fotografia periodicamente sostituita, non un flusso video. |
| Modalita' tecnica di integrazione | `<img>` HTTPS diretto, `mediaType: snapshot`, caricamento quando l'anteprima e' visibile, refresh gestito dal frontend, fallback locale e apertura della pagina ufficiale. Nessun proxy o salvataggio dell'immagine nel repository. |
| HTTPS, CORS e cache | JPEG HTTPS, MIME `image/jpeg`, `1919x1018`, 184.031 byte. Non sono stati osservati `Access-Control-Allow-Origin`, `Cache-Control`, `ETag` o `Expires`: e' visualizzabile come immagine cross-origin, ma non va trattato come risorsa leggibile da canvas. |
| Attribuzione richiesta | `Meteo System`, collegata alla pagina webcam ufficiale. |
| Licenza o permesso noto | Nessun accordo privato e nessuna licenza pubblica specifica individuata. Il copyright presente sul sito e la [privacy policy Meteo System](https://www.meteo-system.com/dichiarazione-sulla-privacy-ue/) non costituiscono un'autorizzazione di riuso. |
| Stato | **Attiva nel ramo come anteprima revocabile; autorizzazione da chiarire per un uso consolidato.** |
| Motivo e azione proposta | Fattibilita' tecnica alta, immagine corrente e identita' verificata. Mantenere fonte e attribuzione visibili, nessun player o archivio, monitorare freschezza e poter disattivare solo questa anteprima. Chiedere conferma al gestore per eliminare l'incertezza autorizzativa. |

## Privacy, banda e continuita'

Lo snapshot non esegue codice di terze parti e non introduce cookie o storage,
ma il browser contatta `www.meteosystem.com` e comunica i normali metadati di
rete. Il frontend deve mantenere `referrerPolicy="no-referrer"` e non ricaricare
la foto quando la finestra webcam non e' visibile.

La fotografia pesa circa 184 kB al controllo. In assenza di direttive cache
esplicite, il refresh deve restare moderato. Se la sorgente fallisce o viene
disabilitata dal controllo per webcam, l'app deve mostrare la foto territoriale
di Trieste e conservare il collegamento alla pagina ufficiale.

## Criteri di completamento

- manifest e test devono distinguere lo snapshot da un video live;
- fonte e attribuzione devono essere visibili in italiano e friulano;
- nessun `playerUrl`, proxy, archivio o download persistente;
- errore immagine e revoca devono degradare al fallback senza rompere il catalogo;
- prima di una promozione va ricontrollata la freschezza della sorgente e va
  eseguito il collaudo della card sul telefono reale.
