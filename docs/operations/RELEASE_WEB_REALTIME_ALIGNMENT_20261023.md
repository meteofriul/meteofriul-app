# Release 0.1.15 e Web: integrazione di Tempo reale — 23 ottobre 2026

## Esito locale

La release incorpora main `2d8b0c327204c5812bb67dbf203ed948812a445e` tramite il merge locale
`16890b8c640d4ad45e33e2bea3da4d8562a3d754`, senza conflitti. Il delta rispetto a `d8ee20ef`
contiene soltanto layout di Tempo reale, regressioni e relativo verbale.
Conservate Posizione, aria e pollini (compreso il rientro), configurazione nativa
e le altre modifiche già presenti nella 300035. Main e GitHub non modificati.

Web e asset Web per Android sono compilati da questa stessa sorgente,
albero frontend `20779cfcc19dedebb81061333ff370a67e062c43`. La candidata Web corrente
sostituisce quella da `5e9bc7dc`, conservata come artefatto storico.
Nessuna nuova AAB: nome 0.1.15 e codice configurato 300035 invariati.
Il codice 300035 è già consumato; una futura AAB richiederà un codice superiore,
verificato contro Play e ledger prima della riserva. Nessuna riserva eseguita.

Sponsor confermati in sola lettura prima e dopo la compilazione:
`enabled=false`, zero campagne, revisione 117.
Pannello e allineamento dei dati sponsor non avviati.

## Controlli completati

| Controllo | Esito |
| --- | --- |
| Suite frontend completa, massimo due worker | 5047 PASS, 0 FAIL, 13 saltati; 552 file passati e 5 saltati |
| Lint completo | PASS |
| Guardie endpoint, mappe, versione, dipendenze e QA | 16 PASS |
| Contratti builder | PASS con `-SkipGradleExecution` |
| Configurazione nativa | 43 asserzioni PASS, nessuna nuova build o analisi di AAB |
| Contratti R8 e preflight API | PASS |
| Dipendenze | 361 pacchetti obbligatori conformi al lock; node_modules fisico, Vite 8.1.6; nessuna installazione |
| Pulizia workspace canonico | PASS |
| Ledger | 54 record immutabili, nessun nuovo codice |
| File protetti | 259 hash invariati: artefatti, configurazioni private e registri |
| Build Web `-BuildOnly` | PASS; API prima/dopo, mappe e service worker verificati |
| Build soli asset Web Android | PASS; endpoint e mappe verificati |
| Correzione Tempo reale nei due bundle | PASS: griglia a due righe e navigazione nel flusso, compresa la variante per finestra bassa |
| Integrità archivio e sorgenti | Tutti i file verificati con dimensione e SHA256 |

Archivio canonico ignorato: `release-artifacts/web-candidates/20261023-0.1.15-16890b8c/`.
Web: 506 file; asset Web Android:
505 file.
Manifest SHA256: `6dc45aa682c277f9ae3cace1a8add59a527ab78c99773a183693416daf2fb82e`.
[Ricevuta strutturata](evidence/release-web-realtime-alignment-20261023/verification.json).
Log privati: `.tmp/release-realtime-alignment-20261023/`.
Il primo controllo temporaneo delle dipendenze si è fermato per la codifica
Windows dei JSON; lettura corretta a UTF-8, poi verifica superata senza cambiare
pacchetti o sorgenti dell'app.

## API e limiti delle prove

Binding Play `play-b6fbe4d`, revisione `meteofriul-api-00251-jow`, immagine
`5522b4cf…`: preflight protetto superato prima e dopo. Provenienza originale
`e180b87a` e attestazione già registrata. Questa integrazione è frontend e non
richiede un aggiornamento backend. Non è un controllo complessivo dei job.

Le prove visive IT/FUR su Brave/Galaxy e chiaro/scuro nell'anteprima del
[fix Tempo reale](REALTIME_LAYOUT_FIX_20261023.md) sono riutilizzate dopo
confronto degli hash dei tre sorgenti verificati. Non sono nuove prove della
candidata integrata né del runtime Android minificato. Nessun nuovo test browser
o sul telefono in questa preparazione. Il distacco di 8 px rimane attestato
dalla precedente misura DOM; il controllo dei bundle prova la presenza del CSS,
non la sua resa su un nuovo dispositivo.

La **300035 installata rimane difettosa in Tempo reale** e non è stata modificata.
REALTIME-LAYOUT-01 è corretto nei sorgenti e negli asset preparati, ma resta aperto
per la futura AAB. Per chiuderlo occorrono artefatto autorizzato, verifica su
telefono del pacchetto minificato e ricontrollo delle sezioni adiacenti.
I risultati positivi di Posizione/CAMS/configurazione nativa della 300035 restano
storici e delimitati dal [verbale](ANDROID_0.1.15_300035_DEVICE_CHECK_20261023.md).

## Quattro aree Android e passi successivi

| Area | Stato della nuova candidata |
| --- | --- |
| Edge-to-edge/inset | Contratti CSS e barre PASS; nuova geometria in release minificata da provare. Android 15/16, gesti/cutout e tastiera non verificati |
| API deprecate | Toolchain e codice nativo invariati; avvisi delle dipendenze non dichiarati risolti |
| Orientamento/adattabilità | Policy portrait smartphone conservata; tablet e multi-window non verificati |
| R8/risorse | Contratti PASS; nessun nuovo pacchetto minificato. Packaging corretto e avvio provati solo nella precedente 300035 |

Prima della prossima AAB: salvataggio/push autorizzato del ramo release, CI sul
commit destinato alla build, ricontrollo Play/ledger, codice superiore e builder
protetto. Poi collaudo del pacchetto reale, includendo separatamente Home,
Previsioni, Bollettino, Tempo reale, Eventi, Scopri e Impostazioni.
Non basta una verifica mirata per qualificare l'intera release.

La Web pubblica non è aggiornata da questa attività; ultima lettura registrata
22 ottobre: 0.1.14. Prima di pubblicare la candidata restano controllo del bundle
statico e aggiornamento cache; Safari/iPhone/PWA non verificati.
Nessuna AAB/APK, installazione, emulatore, sync Capacitor, Gradle, push, deploy
o invio. La release non è promossa su main.
