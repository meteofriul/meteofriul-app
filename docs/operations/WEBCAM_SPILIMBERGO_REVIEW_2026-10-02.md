# Webcam Spilimbergo — verifica 2 ottobre 2026

## Decisione

Il catalogo v30 attiva soltanto `spilimbergo-duomo` come **anteprima
aggiornata**. La vista `spilimbergo-municipio` resta fuori dal catalogo attivo:
al controllo la scena era capovolta di 180 gradi, mentre overlay e loghi erano
gia' orientati correttamente, e l'orologio impresso risultava quasi un'ora nel
futuro. Non viene applicata una rotazione CSS che renderebbe errati testo e
crediti della fonte.

La scelta sul Duomo e' editoriale, revocabile per singola fonte e coerente con
la politica approvata per le anteprime pubbliche. Non costituisce una
dichiarazione di licenza o autorizzazione da parte di PromoTurismoFVG, del
Comune di Spilimbergo o di OSMER.

## Verifica puntuale

Controllo eseguito il `2026-10-02T07:04:47Z`.

| Campo | Duomo | Palazzo di Sopra / Municipio |
| --- | --- | --- |
| Identita' OSMER | `Spilimbergo - Duomo (132 m)`, fonte `www.turismofvg.it`. | `Spilimbergo - Palazzo di Sopra e Municipio (132 m)`, fonte `www.turismofvg.it`. |
| Coordinate dichiarate | `46.110679, 12.904467`. | `46.112464, 12.904751`; circa 200 m dalla vista Duomo, quindi identita' distinta. |
| Mirror HTTPS OSMER | `https://www.meteo.fvg.it/ext/webcams/webcams/Spilimbergo-Duomo-spilimbergo_piazzaduomo.jpg.jpg` | `https://www.meteo.fvg.it/ext/webcams/webcams/Spilimbergo-Municipio-spilimbergo_municipio.jpg.jpg` |
| Upstream | Vecchio endpoint PromoTurismoFVG solo HTTP: `.../spilimbergo_piazzaduomo.jpg`. | Vecchio endpoint PromoTurismoFVG solo HTTP: `.../spilimbergo_municipio.jpg`. |
| Formato | JPEG 704×576, circa 46 KiB. | JPEG 768×576, circa 274 KiB. |
| Stato visivo | Immagine orientata correttamente: fianco del Duomo, campanile e prato; fascia inferiore con loghi istituzionali. | **Non utilizzabile:** scena capovolta di 180 gradi, ma testo e loghi dritti. |
| Timestamp e freschezza | Mirror circa 10–11 minuti dietro l'upstream nel campione. L'overlay appariva in UTC/non locale e non viene usato come metadato autorevole. | Mirror fresco nel campione, ma overlay quasi 56 minuti nel futuro. Clock non affidabile. |
| HTTPS, CORS e cache | Mirror `200 image/jpeg`, `ETag`, `Last-Modified`, `Accept-Ranges`; nessun CORS, `Cache-Control`, `Expires` o cookie osservato. `<img>` valido, `fetch`/canvas cross-origin no. | Stesso contratto HTTP del Duomo. |
| Privacy | Spazio pubblico; nessun volto o targa leggibile nel campione. Nessun player, cookie, archivio o timelapse aggiunto dall'app. | Spazio pubblico; nessun volto o targa leggibile nel campione. |
| Diritti | Nessuna licenza specifica o autorizzazione Meteo Friûl individuata. La pagina webcam PromoTurismoFVG corrente non elenca piu' Spilimbergo; accessibilita' del JPEG e mirror OSMER non equivalgono a permesso. | Stessa situazione autorizzativa, oltre al difetto tecnico. |
| Stato | **Attiva localmente come scelta editoriale revocabile; autorizzazione e continuita' da consolidare.** | **Bloccata.** Ricontrollare soltanto dopo correzione alla fonte di rotazione e orologio. |

Fonti di verifica:

- [pannello webcam ARPA FVG - OSMER e GRN](https://www.meteo.fvg.it/webcam_img.php?ln=it);
- [feed mappa OSMER](https://www.meteo.fvg.it/ajax/webcamList.php);
- [catalogo webcam PromoTurismoFVG corrente](https://www.turismofvg.it/it/webcam);
- [Duomo di Santa Maria Maggiore](https://www.vivispilimbergo.it/chiese/duomo-di-santa-maria-maggiore/);
- [Palazzo di Sopra](https://www.vivispilimbergo.it/palazzi-storici/palazzo-di-sopra/).

## Integrazione Duomo

Il record v30:

- usa un nuovo ID `spilimbergo-duomo`, senza riutilizzare lo storico
  `spilimbergo-municipio`;
- usa soltanto il mirror JPEG HTTPS OSMER, senza proxy Meteo Friûl;
- conserva nome, quota e coordinate dichiarati dal feed OSMER;
- mostra `PromoTurismoFVG` come fonte e il ruolo tecnico di ARPA FVG - OSMER e
  GRN;
- collega il pannello OSMER, unica pagina ufficiale corrente trovata che
  esponga ancora questa camera;
- usa `/municipalities/photos/093044-photo.webp` come fallback;
- non configura player, iframe, timelapse o download server-side.

## Condizioni operative

- mantenere immagine completa e fascia dei loghi originari;
- non usare l'ora sovraimpressa come indicatore di freschezza;
- refresh automatico solo foreground/visibile ogni 10 minuti e cooldown
  manuale di 12 secondi;
- fallback territoriale su errore o spegnimento dal controllo per fonte;
- monitorare `Last-Modified`, hash, permanenza del mirror e ritorno della
  camera nel catalogo PromoTurismoFVG;
- rivalutare Municipio soltanto dopo un periodo di immagini orientate e clock
  coerente; in quel caso andra' aggiunta come seconda vista, non come alias.

## Collaudo

Collaudo locale completato il 2 ottobre 2026:

- API del pilot: catalogo v30, 31 webcam attive e un solo record Spilimbergo;
- pilot avviato esclusivamente con
  `scripts/start-local-weather-pilot.ps1 -WeatherTestNow 2026-09-04T12:00:00Z`
  sulla porta 5174. Il profilo temporale supportato evita che lo snapshot ICON
  offline scaduto blocchi l'avvio e non altera il contratto webcam;
- filtro `Pianura`: 10 sorgenti; l'elenco mostra `Spilimbergo - Duomo` e non
  contiene `Spilimbergo - Municipio`;
- scheda Duomo: JPEG caricato a 704×576, nome, localita', fonte e attribuzione
  corretti, pannello OSMER aperto con `target="_blank"` e
  `rel="noopener noreferrer"`, nessun iframe o player;
- refresh manuale: il parametro `mf_snapshot` cambia, l'immagine resta valida
  a 704×576 e il comando entra nel cooldown previsto di 12 secondi;
- console: nessun errore o avviso riferito alle webcam.

La prova Android reale di background/ripresa resta separata e non e' stata
eseguita in questo blocco; non e' richiesta per il commit locale del catalogo.
