# Revisione webcam Cividale — 29 settembre 2026

## Decisione

Meteo Friûl mantiene e presenta come **anteprime aggiornate** tre viste pubbliche
di Cividale del Friuli, caricate direttamente dal server OSMER e raccolte in una
sola località nell'interfaccia:

1. Veduta dal campanile ex Monastero Maggiore;
2. Piazza Duomo;
3. Piazza Paolo Diacono.

L'app mostra una vista alla volta. Nel pilot mobile si passa alla precedente o
alla successiva con gesto orizzontale oppure con i pulsanti discreti incorporati
a metà dell'anteprima; il contatore in alto a destra indica la posizione corrente.
Il catalogo usa un solo cluster editoriale
`cividale-del-friuli` e un solo riferimento visibile:

> ARPA FVG - OSMER e GRN

La pagina sorgente è il [pannello webcam OSMER](https://www.meteo.fvg.it/webcam_img.php?ln=it)
e l'attribuzione rimanda a [meteo.fvg.it](https://www.meteo.fvg.it/).

## Verifica puntuale

Controllo eseguito il **29 settembre 2026 alle 19:23 CEST**. Gli orari di modifica
sono quelli restituiti dal server e concordano, per le tre viste promosse, con il
timestamp impresso nel fotogramma.

| Vista | URL immagine | Ultimo aggiornamento osservato | Esito |
| --- | --- | --- | --- |
| Veduta dal campanile | `CividaleVedutadalcampanile-cividale_campanileexmonastero.jpg` | 29/09/2026 19:15 CEST | Attiva, promossa come vista iniziale |
| Piazza Duomo | `CividalePiazzaDuomo-cividale_piazzaduomo.jpg` | 29/09/2026 19:15 CEST | Attiva |
| Piazza Paolo Diacono | `CividalePiazzaDiacono-cividale_piazzadiacono.jpg` | 29/09/2026 19:15 CEST | Attiva |
| Ponte del Diavolo / Stretta San Martino | `CividalePontedelDiavolo-cividale_strettasanmartino.jpg` | 17/09/2026 17:29 CEST; fotogramma bianco | Esclusa |
| Natisone / Ponte del Diavolo | `CividaleNatisone-cividale_pontedeldiavolo.jpg` | 24/05/2026 19:38 CEST | Esclusa perché ferma |

Le tre immagini attive sono JPEG HTTPS. Il server espone `Last-Modified`, `ETag`
e `Accept-Ranges`, ma non `Cache-Control`, `Expires` o CORS. Il CORS non è
necessario per visualizzare un elemento `img`; l'assenza può invece impedire al
frontend Web di leggere via `fetch` i metadati HTTP. Il catalogo conserva quindi
il fallback territoriale già revisionato.

## Modalità di integrazione

Il backend distribuisce gli URL nel manifest ma non scarica né ripubblica i
fotogrammi. Browser e WebView richiedono il JPEG direttamente a `meteo.fvg.it`.
Il parametro di aggiornamento aggiunto dal frontend evita una copia obsoleta
nella cache del client; non viene creato un archivio Meteo Friûl.

Nel pilot le webcam che condividono il cluster editoriale sono rappresentate da
una sola voce. L'apertura carica soltanto la vista selezionata e il cambio vista
sostituisce il contenuto nel medesimo dettaglio, limitando banda e richieste.

## Note legali applicate

Le [note legali OSMER](https://www.osmer.fvg.it/note-legali.php) distinguono la
licenza generale dei contenuti dalla clausola dedicata ai “dati real-time”. La
clausola usa “ora di riferimento del dato” e non menziona le immagini; nelle
altre sezioni, quando l'ambito è generale, OSMER enumera invece dati, mappe,
previsioni e immagini. ARPA FVG descrive inoltre separatamente le misure
meteorologiche e l'acquisizione delle immagini webcam.

Non è stata trovata una disposizione ufficiale che estenda espressamente il
ritardo di 24 ore ai JPEG delle webcam. La precedente classificazione di
Cividale come bloccata in attesa di deroga è quindi ritirata. Meteo Friûl non
dichiara un'approvazione individuale ricevuta da OSMER: applica l'attribuzione
richiesta, mantiene il collegamento alla fonte e incorpora soltanto le anteprime
pubbliche erogate dal server sorgente.

## Verifica richiesta prima della consegna

- validazione del manifest backend versione 12 e conteggio delle fonti;
- test del modello frontend e del cluster Cividale;
- test del pulsante precedente/successiva e del gesto orizzontale;
- collaudo del pilot esclusivamente con `scripts/start-local-weather-pilot.ps1`
  sulla porta 5174;
- collaudo successivo su telefono reale di scorrimento, ripresa dal background,
  fallback e consumo di banda.
