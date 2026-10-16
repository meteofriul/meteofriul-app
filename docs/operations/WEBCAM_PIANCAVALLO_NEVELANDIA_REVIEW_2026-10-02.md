# Webcam Piancavallo - Nevelandia — verifica 2 ottobre 2026

## Decisione

`piancavallo-nevelandia` mantiene identita', pagina proprietaria e fallback
gia' presenti nel catalogo e passa da solo collegamento a **anteprima
aggiornata** mediante il mirror JPEG HTTPS del pannello ARPA FVG - OSMER e
GRN. Non viene configurato alcun player.

La soluzione elimina il mixed-content dell'origine Axis HTTP senza introdurre
un proxy Meteo Friûl. La scelta resta revocabile per singola fonte e non viene
presentata come licenza o autorizzazione del proprietario.

## Verifica puntuale

Controllo eseguito il `2026-10-02T06:06:30Z` sulle pagine e risorse correnti.

| Campo | Esito |
| --- | --- |
| Localita' e identita' | Piancavallo, Comune di Aviano, area Nevelandia, quota pubblicata 1.265 m. Il feed OSMER indica `46.112847, 12.52325`. Il fotogramma mostra il parco, l'overlay `Piancavallo_Nevelandia1`, il timestamp e i loghi Piancavallo 1265, Nevelandia e PromoTurismoFVG. |
| Pagina proprietaria | [Nevelandia - Webcam Piancavallo](https://www.nevelandia.com/webcam-piancavallo/), che presenta la camera come “La nostra webcam a Piancavallo”, collega l'origine Axis e identifica `Piancavallo 1265 S.C.A.R.L.` come amministrazione del sito. |
| Riferimento OSMER | [Pannello webcam ARPA FVG - OSMER e GRN](https://www.meteo.fvg.it/webcam_img.php?ln=it). La voce `Piancavallo - Nevelandia` indica PromoTurismoFVG come fonte e pubblica il mirror stabile `https://www.meteo.fvg.it/ext/webcams/webcams/Piancavallo-Nevelandia-image.cgi.jpg`. |
| Stato corrente | Mirror HTTPS: stato `200`, `image/jpeg`, JPEG valido 1280×960. L'origine `http://46.19.234.136/axis-cgi/jpg/image.cgi` risponde, ma resta HTTP-only e quindi non viene caricata dall'app HTTPS. |
| Freschezza osservata | Mirror: `Last-Modified: Fri, 02 Oct 2026 06:01:21 GMT`, circa cinque minuti prima del controllo; ETag `1d68e-65cd542f07df4`. Il timestamp impresso nei pixel riportava `2026-10-02 07:01:20`, coerente con l'aggiornamento osservato. E' un fotogramma periodico, non video. |
| HTTPS, CORS e cache | Il mirror e' HTTPS e accetta richieste condizionali tramite ETag/Last-Modified; non espone `Access-Control-Allow-Origin`, `Cache-Control` o `Expires`. Funziona in `<img>`, ma il frontend non puo' leggere in modo affidabile i metadati HTTP cross-origin. |
| Banda | Circa 118 KiB al controllo. Il refresh resta ogni 10 minuti soltanto con anteprima visibile e app in primo piano; il tasto manuale conserva il cooldown di 12 secondi. Nessun preload dell'elenco. |
| Attribuzione | Fonte proprietaria visibile, in forma compatta per la card: `Nevelandia / Piancavallo 1265`; la pagina proprietaria identifica per esteso `Piancavallo 1265 S.C.A.R.L.`. Raccolta tecnica: `PromoTurismoFVG · ARPA FVG - OSMER e GRN`, collegata al pannello OSMER. |
| Licenza o permesso noto | Nessun accordo privato noto. La pagina Nevelandia riporta tutti i diritti riservati; l'accessibilita' pubblica, il mirror e i loghi nel fotogramma non costituiscono da soli un'autorizzazione al riuso. |
| Stato | **Attiva localmente come anteprima aggiornata per scelta editoriale revocabile; autorizzazione da consolidare.** |

## Integrazione

Il catalogo v28:

- usa il percorso mirror senza il query cache-buster volatile del pannello;
- conserva la pagina Nevelandia come azione principale “Apri la fonte”;
- mostra separatamente il credito PromoTurismoFVG/OSMER;
- usa le coordinate pubblicate dal feed OSMER invece del centro comunale
  approssimato;
- mantiene `/municipalities/photos/093004-photo.webp` come fallback;
- non configura `playerUrl`, iframe, cookie di player, archivio o download
  server-side.

## Condizioni operative

- immagine completa, senza ritaglio delle scritte e dei loghi originari;
- refresh moderato e solo foreground/visibile;
- fallback territoriale su errore o spegnimento dal controllo per fonte;
- nessuna promessa di nuova immagine a ogni pressione del refresh;
- verifica periodica di freschezza, identita' e permanenza del path OSMER;
- rimozione del solo `imageUrl`/`mediaType` se il proprietario chiede di
  interrompere l'anteprima, mantenendo card, fallback e pagina fonte.

## Collaudo

Collaudo locale eseguito il 2 ottobre 2026:

- endpoint del pilot `http://127.0.0.1:5174/api/live/webcams`: catalogo v28,
  29 record e contratto Nevelandia conforme;
- pilot canonico gia' attivo in porta 5174: anteprima caricata senza fallback,
  JPEG naturale 1280×960 e resa nella card 344×194;
- nessun `iframe` o elemento `video` nella scheda;
- credito PromoTurismoFVG/OSMER e azione “Apri la fonte” puntano ai due URL
  dichiarati e si aprono in una nuova scheda;
- refresh manuale verificato: il cache-buster cambia, l'immagine resta valida e
  il comando entra nel cooldown di 12 secondi;
- nessun errore console rilevato durante apertura e refresh;
- suite backend webcam: 64 test superati e 150 subtest superati;
- suite frontend `src/features/live`: 50 file e 773 test superati; lint pulito.

La prova Android reale resta separata e non e' richiesta per modificare
localmente il catalogo. Il pilot e' stato riavviato esclusivamente tramite
`scripts/start-local-weather-pilot.ps1` sulla porta 5174. Poiche' l'orologio
reale rende correttamente non utilizzabile lo snapshot ICON scaduto il 5
settembre 2026 e il profilo cloud sola-lettura non ha superato il proprio
health check, il collaudo finale usa il parametro supportato
`-WeatherTestNow 2026-09-04T12:00:00Z`; il launcher ha pubblicato gli snapshot
locali, chiuso le capacita' di scrittura e avviato backend, data plane e
frontend solo su loopback.
