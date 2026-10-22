# Release 0.1.15 e Web dalla stessa base — 22 ottobre 2026

## Esito e perimetro

Preparazione locale completata sul ramo esistente `codex/release-0.1.15`.
La candidata integra tutte le correzioni approvate in main e la conservazione
della posizione automatica. Sono compilati Web e asset Web per Android dalla
stessa sorgente; non è stato prodotto alcun pacchetto Android.

Nessuna AAB/APK, esecuzione Gradle, sincronizzazione Capacitor, installazione,
emulatore, push, deploy, invio manuale o promozione su main. Sponsor, pannello
e allineamento dati sponsor restano disattivati. Lettura API finale: catalogo
`enabled=false`, zero campagne, revisione 117.

## Identità e integrazione

| Elemento | Identità |
| --- | --- |
| Main integrato | `d62683b9666ad38de42033fd2fe6db022ead8943` |
| Allineamento main nella release | `2dbdf7be` |
| Correzione posizione incorporata | `2e5fc0b69f80fe862142e294a612c78c6aef2f57` |
| Sorgente compilata, merge posizione | `a32907150ea96d906a8f1f1130b5e35269df0368` |
| Albero frontend | `9b7accf283f9a29c122b5bbcd12a7e8949d7d38f` |
| Nome versione | `0.1.15` |
| Codice configurato, invariato | `300033`, relativo all'artefatto precedente; nessuna nuova riserva |

Incorporati mappa del bollettino, località/menù fissi solo in Bollettino ed
Eventi, Vite 8.1.6 e Indietro dalle Impostazioni nel browser. Restano le precedenti
correzioni approvate di testi, temi, Community, FVG ed Eventi. Nessuna impostazione
speciale della TEST è stata importata. La correzione nativa e l'adeguamento della
guardia sul nome versione, già nel ramo release, sono conservati.

La posizione attiva non viene più spenta dal controllo di avvio Android dopo
un errore temporaneo. Restano rispettati permesso negato e scelta esplicita di
disattivarla. Non si riaccendono preferenze già spente e non si attribuisce una
causa certa all'episodio segnalato dopo l'aggiornamento Play.

I commit documentali successivi possono cambiare HEAD senza cambiare i sorgenti
compilati: manifest e albero frontend identificano questa candidata. La PR 11
remota resta in bozza e non riceve l'integrazione locale senza un push autorizzato.

## Controlli locali eseguiti

| Controllo | Esito |
| --- | --- |
| Suite frontend completa, config loader nativo | 5.030 PASS, 0 FAIL, 13 saltati; 551 file passati e 5 saltati |
| ESLint completo | PASS |
| Guardie Node frontend | 19 PASS: endpoint, CARTO, parità versione, dipendenze, QA Community, anteprima social |
| Contratti builder | PASS con `-SkipGradleExecution` |
| Contratti preflight API e hardening R8 | PASS; nessuna nuova prova R8 su artefatto |
| Contratti configurazione nativa | 42 asserzioni PASS; la AAB 300033 senza configurazione viene rifiutata come atteso |
| Audit ledger | 49 record storici / 49 correnti invariati, nessuna riserva |
| Protezione asset privati e storici | 56 file con hash invariati, inclusi ledger, configurazioni locali e artefatti censiti |
| Build Web protetta | PASS con `deploy-cloudflare-app.ps1 -BuildOnly`; API verificata prima e dopo |
| Build asset Web in modalità Android | PASS, solo Vite; controlli endpoint e CARTO superati |
| Integrità archivio e sorgenti | 1.011 asset e 1.891 file sorgente confrontati tramite SHA256 |

Le dipendenze sono fisiche, senza junction. Riutilizzata una copia locale
integrale di Vite 8.1.6 dopo confronto dei lockfile, diversi soltanto nel numero
di versione del prodotto. Verificati 23.116 file, 313.749.903 byte e 363 versioni
di pacchetti installati; nessun download o aggiornamento di pacchetti. La copia
precedente è conservata nell'archivio temporaneo locale, senza cancellazioni.
L'avviso noto sulla dimensione dei chunk resta non bloccante.

## API e backend

- API ufficiale: `https://play-b6fbe4d---meteofriul-api-bx24xqvcda-ew.a.run.app/api`.
- Revisione `meteofriul-api-00251-jow`, backend `599aea2f8a3b1e7e65af2b43e77bb54e4637c96e`.
- Immagine attestata: `sha256:5522b4cfc15076a9f93e838e3643b35e1aa5ad4ce0bf5bca4851997ea94c2ae8`.
- Preflight live PASS, health OK e legame commit/immagine verificato con
  `release-history/cloud-operations/20261020-services-attestation/api-backend.json`.

Queste correzioni dell'interfaccia, della posizione e del confezionamento non
introducono un requisito di aggiornamento backend. I job non sono stati avviati
né distribuiti in questa attività; restano validi gli esiti dei rispettivi
verbali, senza dedurre dal preflight che ogni sorgente dati sia fresca.

## Artefatti locali e Web pubblica

Archivio ignorato nella radice canonica:
`release-artifacts/web-candidates/20261022-0.1.15-a3290715/`.

- `web/`: 506 file, 76.029.284 byte, build Web ufficiale con service worker.
- `android-web/`: 505 file, 75.976.616 byte; solo asset, non una AAB/APK.
- `manifest.json`: SHA256 `31197b1336c4aa2aeb1c70e8b7df74d1252e1a70877e625ac097fdb8d6223957`.

Le differenze degli asset dipendono dalla modalità Web/Android; la base sorgente
è identica. Il manifesto completo e i pacchetti restano fuori Git; la
[ricevuta condivisibile](evidence/release-web-alignment-2026-10-22/verification.json)
conserva identità, conteggi, limiti e hash dei log.

La Web pubblica non è ancora questa candidata. Il 21 ottobre è stata pubblicata
la versione 0.1.14 da `1b0287c19dc78e81e84ad3fa4b54fb97c42ff250`, deployment
`a96afc59-b1c8-4c85-b146-377e57594690` del progetto `meteofriul-app-bcee09e`.
Lettura del 22 ottobre: HTML e asset principale corrispondono agli hash della
pubblicazione; la ricevuta riporta i digest. Il precedente deployment noto è
`015e1125-9ada-4d10-9f50-e0fbe10d17d2`. Nessuna nuova pubblicazione o rollback.

Questo rettifica le righe del README/stato release rimaste ferme alla
preparazione del 20 ottobre: non era corretto descrivere la Web come mai aggiornata
nel frattempo. Mancano sul pubblico le successive correzioni del 22 ottobre.

## Verifica nell'anteprima integrata

Avvio con il launcher canonico `scripts/start-local-weather-pilot.ps1
-NationalCloud`, porta 5174, profilo reader. La precedente anteprima è stata
fermata con il suo launcher e sostituita con quella del ramo release.

Nel browser integrato Codex, viewport 661 × 902:

- Bollettino e catalogo Eventi caricati; Indietro del browser dalle Impostazioni
  torna alla sezione di provenienza, sia da Bollettino sia da Eventi.
- Località e menù restano visibili nello scorrimento di Bollettino ed Eventi;
  la spaziatura della mappa lascia libere le etichette delle temperature.
- Controllati italiano/chiaro e friulano/scuro, incluso Indietro in friulano.
  Ripristinati lingua e tema iniziali; località, posizione e notifiche non cambiate.

È una verifica pilot sullo stesso sorgente, non la prova runtime del bundle
statico pubblico, di Brave/Galaxy o della nuova release nativa. Gli screenshot
e i log restano nell'archivio locale `.tmp/release-web-alignment-20261022/`.

Limiti osservati: nel reader locale aria e pollini risultavano non disponibili;
questa sessione non ne attesta il funzionamento. Il testo italiano del bollettino
riportava aggiornamento 22/10 09:16 e quello friulano 21/10 12:30: non si attesta
una freschezza identica delle due fonti linguistiche. Nessuna correzione dati o
nuova acquisizione è stata avviata.

## Cosa resta prima del rilascio

1. Quando autorizzato, sincronizzare il ramo release e verificare la CI su quella
   sorgente. Main non riceve ora i cambiamenti nativi non ancora provati.
2. Prima della nuova AAB rileggere Play e ledger e scegliere un codice libero
   crescente. Il nome può restare 0.1.15; 300034 è solo un possibile prossimo
   codice, non prenotato. Non sovrascrivere l'artefatto 300033.
3. Con autorizzazione distinta generare il bundle col builder protetto, verificare
   la configurazione nel risultato minificato, poi caricare nel test interno.
4. Sul successivo aggiornamento autorizzato registrare la posizione prima/subito
   dopo, verificare recupero GPS, plugin e log nativi. Restano le aree obbligatorie
   Android: edge-to-edge/inset, API delle barre, orientamento/adattabilità e R8.
   Android 15/16, gesti e tablet/multi-window restano non verificati.
5. Per la Web, prima della pubblicazione ricontrollare API/manifest e collaudo
   del pacchetto definitivo, anche con profilo nuovo. Safari/iPhone/PWA resta
   non verificato. Pubblicare solo dopo autorizzazione e confrontare gli asset
   realmente serviti con il manifesto.

Né la suite né la compilazione chiudono i rilievi runtime nativi o certificano
scritture Community e consegne reali. Riferimenti: [stato release](RELEASE_0.1.15_STATUS_20261021.md),
[posizione](ANDROID_LOCATION_STARTUP_20261022.md), [configurazione nativa](ANDROID_NATIVE_CONFIG_FIX_20261022.md),
[parità Web](WEB_ANDROID_RELEASE_PARITY.md), [runbook Play](PLAY_AAB_RUNBOOK.md).
