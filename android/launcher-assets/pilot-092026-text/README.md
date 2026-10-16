# Logo con scritta — pilota 7 settembre 2026

Master: `frontend/public/brand/meteo-eventi-friul-text-master.png`.
Originale utente: `ChatGPT Image 7 set 2026, 14_26_18.png`.
Preparato con imagegen integrato. Prompt: estendere soltanto lo sfondo blu
negli angoli neri; preservare sagoma, tipografia, colori e testo esatto
«Meteo Eventi Friûl», senza margini o altri elementi.

Derivati residui inventariati con SHA-256. Misure ereditate da approved-082026:
adaptive/maskable 54%, splash 66%, shortcut 78,1%. La notifica e il launcher
monocromatico conservano la sagoma del master edge, senza testo minuscolo.
Pacchetti precedenti e risorse Android main/beta non modificati.

Il launcher adattivo attivo è gestito esclusivamente da
`scripts/package-pilot-launcher-layers.ps1`, vincolato al riferimento corrente
descritto nel README della cartella padre. I 10 vecchi foreground/background
adattivi sono rimossi; il generatore generale precedente è ritirato per non
reintrodurli. Restano attivi da questo pacchetto i raster legacy usati da
Android 24/25, le notifiche e le risorse favicon/PWA: non eliminarli come se
fossero inutilizzati. Lo splash e il marchio WebView della pilota sono ora
derivati dal pacchetto r3. I vecchi splash e monochrome restano inventariati
per provenienza; il runtime usa gli output del pacchetto launcher corrente.

Web: derivati copiati in `frontend/public/brand/pilot-text`, manifest dedicato;
il collegamento favicon/PWA è applicato da Vite esclusivamente alla pilota.
Asset Play preparato, non pubblicato. Richiesto collaudo su dispositivo prima
di dichiarare verificate le maschere launcher e la schermata di avvio.
