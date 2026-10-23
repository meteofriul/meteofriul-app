# Release 0.1.15 e Web allineate a main — 23 ottobre 2026

> Seguito: [candidata 0.1.15 / 300034](RELEASE_0.1.15_300034_PREPARATION_20261023.md), con correzione del transitorio CAMS e nuovi asset. Il resoconto seguente descrive la precedente base `cda576e7`.

## Esito

Il ramo `codex/release-0.1.15` incorpora main `f9e178b2`, comprese aria e
pollini: “Caricamento…” / “In cjariament…” sono distinti dall'indisponibilità
nelle card e nei dettagli. Conservate le correzioni locali della posizione
e della configurazione nativa. Il merge `cda576e7` non ha conflitti.

Web e asset Web per Android sono compilati dalla stessa sorgente
`cda576e7d59025171aa0c2fbb65cd58db7aa4052`, albero frontend
`89ee1ced2c7ef2c63c303966c55c023538a551d9`. Non è un nuovo pacchetto Android.
Nome 0.1.15 e codice configurato 300033 invariati; nessuna riserva nuova.

Sponsor: lettura API `enabled=false`, zero campagne, revisione 117. Pannello
e allineamento dati sponsor non avviati. Nessuna AAB/APK, Gradle, sync Capacitor,
installazione, emulatore, push, deploy o invio. Nessuna promozione della release
su main: i rilievi nativi restano aperti.

## Controlli e archivio

| Controllo | Esito |
| --- | --- |
| Suite frontend completa | 5.039 PASS, 0 FAIL, 13 saltati; 551 file passati, 5 saltati |
| Lint | PASS |
| Dipendenze locali | 363 versioni conformi al lock, Vite 8.1.6 fisico; nessuna installazione o download |
| Pulizia workspace canonico | PASS |
| Ledger | 49 record invariati, nessuna nuova riserva |
| Asset privati e storici | 56 file con hash invariati |
| Build Web protetta, `-BuildOnly` | PASS; preflight API prima e dopo, service worker, endpoint e CARTO verificati |
| Asset Web modalità Android | PASS; endpoint e CARTO verificati, nessun pacchetto nativo |
| Integrità archivio | 1.011 asset con dimensioni e SHA256 verificati; sorgenti verificati contro il manifest |

Riutilizzate le prove del 22 ottobre per guardie Node (19 PASS), builder senza
Gradle, contratti API/R8 e configurazione nativa (42 asserzioni). Prima del riuso
sono confrontati gli hash dei log e l'assenza di differenze in `scripts/`,
`frontend/scripts/`, `frontend/android/`, package e lock rispetto ad `a3290715`.
Non vengono presentate come nuove prove del runtime nativo.

Archivio locale ignorato:
`release-artifacts/web-candidates/20261023-0.1.15-cda576e7/`.

- Web: 506 file, 76.030.030 byte.
- Asset Web Android: 505 file, 75.977.362 byte.
- Manifest SHA256: `7c15ac5859b2a0009d2ba8a99015e2555a2914247a33ed09f295a68b2f609aa9`.

Il precedente archivio del 22 ottobre e la AAB 300033 restano conservati.
I successivi commit documentali non cambiano il sorgente compilato.
[Ricevuta condivisibile e hash](evidence/release-web-alignment-2026-10-23/verification.json).
Log e screenshot completi restano in `.tmp/release-web-alignment-20261023/`.

La prima invocazione BuildOnly è stata rifiutata prima della compilazione per
un parametro incompleto: era passato il solo hash invece del riferimento
immagine completo. Ripetuta con il riferimento attestato, senza cambiare il
backend né indebolire la guardia. L'avviso noto sui chunk resta non bloccante.

## API e anteprima

API Play `play-b6fbe4d`, revisione `meteofriul-api-00251-jow`, backend
`599aea2f8a3b1e7e65af2b43e77bb54e4637c96e`, digest
`sha256:5522b4cfc15076a9f93e838e3643b35e1aa5ad4ce0bf5bca4851997ea94c2ae8`:
preflight PASS e health OK. L'attestazione esistente del 20 ottobre è verificata
dal builder. L'integrazione CAMS è frontend e non richiede aggiornamenti ai job.
Questo controllo non è una verifica complessiva delle corse di oggi.

Anteprima avviata soltanto con `scripts/start-local-weather-pilot.ps1
-NationalCloud`, porta 5174, profilo reader, browser integrato 661×902.
Controllati italiano/chiaro, friulano/scuro, dettaglio pollini friulano, ritorno
dalle Impostazioni, previsioni, bollettino e catalogo Eventi (18 eventi oggi).
Aria e pollini mostrano dati reali: PM2.5 6,4 µg/m³, PM10 8 µg/m³,
Artemisia 0,02 grani/m³, riferimento 23/10 07:00, corsa 22/10 02:00.
Ripristinati italiano e tema chiaro; località, posizione e notifiche non cambiate.

**Rilievo residuo CAMS:** al rientro nelle previsioni e dopo un reload è stata
osservata transitoriamente la dicitura di indisponibilità prima del recupero
dei valori. È stato osservato anche il corretto “Caricamento…” all'avvio.
Non è dimostrata la causa del transitorio, né un guasto dei job; non si certifica
l'assenza di ogni intermittenza dell'etichetta. Nessun cambiamento aggiuntivo
al codice o alla cache per nasconderlo. Da chiarire prima di considerare chiuso
anche questo percorso di caricamento.

Le prove simulate di attesa/indisponibilità/zero e la verifica Brave/Galaxy
IT/FUR del 22 ottobre sono in [CAMS](CAMS_LOADING_STATE_20261022.md).
Questa sessione non le sostituisce con una nuova prova sul telefono. Gli errori
Vite/fetch letti nella console precedono l'avvio riuscito del server; nessun
errore successivo è restituito nel campione consultato. Il pilot non dimostra
da solo il comportamento del bundle Web statico o del runtime Android minificato.

## Apertura del pacchetto Web compilato

Servito l'archivio Web identificato sopra su `127.0.0.1:5178`, in una tab
temporanea separata dal pilot. Applicazione e asset si avviano, senza errori
JavaScript restituiti dalla console consultata. I dati meteo sono indisponibili
in questa origine: una lettura di `/api/healthz` con le due origini conferma
HTTP 200 in entrambi i casi, ma `Access-Control-Allow-Origin` soltanto per
`https://meteofriul.app`, non per `http://127.0.0.1:5178`. Il codice backend
conferma l'elenco di origini autorizzate.

Non vengono cambiati CORS, endpoint o controlli del browser per aggirare il
limite. Il server statico e la tab temporanea sono chiusi dopo la prova; il
pilot su 5174 rimane aperto. Questo smoke test attesta l'avvio degli asset,
non tutte le letture dal dominio pubblico, le intestazioni Cloudflare o il
passaggio dalla precedente versione. I dati reali sono verificati nel pilot,
come distinto sopra.

## Aree Android e passaggi ancora distinti

| Area obbligatoria | Valutazione corrente |
| --- | --- |
| Edge-to-edge e inset | Sorgenti invariati rispetto al 22 ottobre; nuova release minificata e Android 15/16 ancora da provare |
| API deprecate delle barre | Nessun aggiornamento toolchain o nuovo intervento; rilievi dipendenze non dichiarati risolti |
| Orientamento e adattabilità | Policy smartphone portrait conservata; tablet e multi-window non verificati |
| R8 e risorse | Contratti invariati già verificati; packaging Capacitor/Cordova corretto localmente, ma contenuto minificato reale da verificare. Ottimizzazione risorse resta raccomandazione aperta |

Restano il nuovo codice libero scelto dopo lettura Play/ledger, la generazione
autorizzata con builder protetto, il controllo della configurazione nel bundle
e la prova sul telefono della posizione prima/subito dopo l'aggiornamento.
Il nome può restare 0.1.15. Non sovrascrivere 300033 e non prenotare un codice
in base alla sola numerazione ipotizzata.

Web pubblica: ultima verifica del 22 ottobre, versione 0.1.14 da `1b0287c1`.
Non è stata aggiornata in questa attività. Per pubblicare la candidata restano
il collaudo del bundle statico/profilo nuovo e il controllo aggiornamento cache;
Safari/iPhone/PWA è NON VERIFICATO. Per il remoto servono autorizzazione a push
e CI della sorgente candidata; main locale resta `f9e178b2`, origin/main
`d62683b9` nell'ultima lettura del 23 ottobre (due commit locali in più).

Riferimenti: [stato release](RELEASE_0.1.15_STATUS_20261021.md),
[preparazione precedente](RELEASE_WEB_ALIGNMENT_20261022.md),
[parità Web](WEB_ANDROID_RELEASE_PARITY.md), [runbook Play](PLAY_AAB_RUNBOOK.md).
