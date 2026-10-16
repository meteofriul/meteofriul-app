# TEST Android: barre e pannello orizzontale — 13 ottobre 2026

Corretto il pannello tagliato nelle finestre basse e allineato lo stile delle
barre della TEST a quello già configurato nell'app principale. Restano scuri i
tre tasti dell'immagine Android 15 con sistema chiaro: il difetto è riprodotto
anche da una piccola app nativa indipendente, senza Capacitor o WebView.
Il caso resta **FAIL visivo su questa immagine**, non viene trasformato in PASS.

## Candidata e perimetro

- Integrazione solo locale su `codex/community-reports-simplification`.
- Barre: ramo `codex/android-test-bar-contrast`, modifica mantenuta `4202dcd9`.
- Layout: ramo `codex/android-territory-short-height`, modifica `a1427da0`.
- APK costruita su `6209e8990588c7f7ed97cdabc63d819d777c850d`.
  HEAD successivo `c845fcd147105090d5a37b8c14b143519de84e45` ha lo stesso albero
  versionato, verificato con `git diff --exit-code`: il tentativo aggiuntivo sul
  contrasto automatico non ha risolto il caso API 35 ed è stato ritirato.
- APK locale `.tmp/android-ui-fixes/meteofriul-community-ui-test.apk`.
- SHA-256 `542b36e5a142012502a55a41e589706455813fbec4c41ad72f56c4684deb537f`.
- Package `com.meteofriul.app.localpilot`, `0.1.14-local-pilot`, versionCode
  `300031`, target SDK 36, debug non minificata.
- Main resta `5a68de5dc1607105f921d4d2b731170f1a8a0446`.
  Nessun push, AAB, Play, modifica alla produzione o installazione sul telefono.
- Community esclusivamente SQLite locale su `127.0.0.1:8783`, meteo con la
  precedente fixture. Le prove funzionali di invio, voto e premi restano nel
  [resoconto precedente](COMMUNITY_REPORTS_ANDROID_TEST_2026-10-13.md).

## Correzioni mantenute

La configurazione Capacitor di `localPilot` sostituisce quella sincronizzata.
Mancava `SystemBars.style: DARK`: Capacitor 8.5.0 poteva ripristinare icone scure
al cambio di configurazione, mentre il plugin dell'app chiedeva icone chiare.
La TEST ora usa la stessa impostazione dell'app principale. Il test del
contratto controlla entrambe le configurazioni. Nessuna modifica alle API Java
delle barre, alle dipendenze o all'edge-to-edge.

Nelle finestre Android alte al massimo 600 CSS px la pagina Territorio può
crescere e scorrere, mantenendo un'altezza minima utile alla mappa e al pannello.
Prima il pannello assoluto superava il contenitore e la sua parte superiore
veniva esclusa dallo scorrimento. Ora selettori, storico e pulsante Segnala meteo
sono raggiungibili. Su schermi bassi non sono tutti visibili contemporaneamente:
si scorre la pagina e, nello storico espanso, l'elenco. Nessuna nuova navigazione.

## Prove runtime della candidata mantenuta

Stessi AVD e impronte del resoconto precedente: API 35
`MeteoFriul_R8_Opt_API35` (immagine Google APIs revisione 9,
`AE3A.240806.043/12960925`) e API 36 `MeteoFriul_Community_API36`
(`BE2A.250530.026.D1/13818094`), 1080 × 2400, densità 420.
ADB porta 5038, seriali espliciti `emulator-5590` e `emulator-5588`.
Emulatori usati in sequenza; nessun controllo di mouse o tastiera del PC.

| Caso | Esito | Evidenza |
| --- | --- | --- |
| 15: cambio sistema scuro → chiaro, app scura | PASS per le icone di stato; FAIL residuo dei tre tasti con sistema chiaro | [Scuro](evidence/android-ui-fixes-2026-10-13/api35-final-system-dark.png), [chiaro](evidence/android-ui-fixes-2026-10-13/api35-final-system-light.png) |
| 16: app/sistema chiari | PASS, icone di stato e tre tasti chiari | [Mappa](evidence/android-ui-fixes-2026-10-13/api36-final-system-light.png) |
| 16: app scura/sistema chiaro e app chiara/sistema scuro | PASS dopo cambio nell'app, senza background/ripresa per correggere le icone | [Scura/chiaro](evidence/android-ui-fixes-2026-10-13/api36-final-app-dark-system-light.png), [chiara/scuro](evidence/android-ui-fixes-2026-10-13/api36-final-app-light-system-dark.png) |
| Gesti 15/16, sistema chiaro | PASS, indicatore chiaro e navigazione dell'app separata dall'inset | [15](evidence/android-ui-fixes-2026-10-13/api35-final-gestures.png), [16](evidence/android-ui-fixes-2026-10-13/api36-final-gestures.png) |
| Pannello in orizzontale, 15/16 | PASS accessibilità tramite scorrimento; aperti Recenti e compositore su entrambi, Storico su 16 | [15](evidence/android-ui-fixes-2026-10-13/api35-final-landscape.png), [16](evidence/android-ui-fixes-2026-10-13/api36-final-landscape.png) |
| Storico e rotazione inversa 16 | PASS consultazione e scorrimento, conserva il proprio invio | [Storico](evidence/android-ui-fixes-2026-10-13/api36-final-history-landscape.png), [inverso](evidence/android-ui-fixes-2026-10-13/api36-final-history-reverse.png) |
| Compositore con barre laterali, entrambi i versi | PASS chiusura e footer raggiungibili, contenuto scorrevole | [15](evidence/android-ui-fixes-2026-10-13/api35-final-composer-landscape.png), [15 inverso](evidence/android-ui-fixes-2026-10-13/api35-final-composer-reverse.png), [16 inverso](evidence/android-ui-fixes-2026-10-13/api36-final-composer-reverse.png) |
| GPS e riepilogo 16 in orizzontale | PASS GPS Android a Pordenone, selezione Pioggia e Continua fino al riepilogo; nessun nuovo invio finale | [GPS](evidence/android-ui-fixes-2026-10-13/api36-final-gps-landscape.png), [riepilogo](evidence/android-ui-fixes-2026-10-13/api36-final-review-landscape.png) |
| Aggiornamento con `install -r` | PASS conservazione dati: B mantiene alias, 1 inviata, 1 confermata, 1 punto | [Profilo](evidence/android-ui-fixes-2026-10-13/api36-final-profile.png) |

Le transizioni di sistema dell'AVD 16 richiedono alcuni secondi: i tentativi di
tocco durante lo snapshot di transizione sono stati ripetuti dopo la sua chiusura.
I fotogrammi finali sono stati ispezionati; non viene certificata l'assenza di
ogni possibile transitorio a livello di singolo frame.

Lo storico in orizzontale su 15 è stato aperto sulla candidata intermedia
`8bf2fb1e`, SHA-256 `525e9d6aa506b4a25443b6df78427648abba93ec410dde9da0febfddc381f9a8`:
stesso layout Web, con il tentativo nativo sul contrasto poi ritirato.
Il dump delle barre citato sotto è stato acquisito sulla candidata `6209e899`;
la riproduzione indipendente usa invece l'APK diagnostica identificata sotto.

## Diagnosi indipendente dei tre tasti API 35

La [piccola Activity diagnostica](evidence/android-ui-fixes-2026-10-13/BarProbe.java)
ha solo uno sfondo blu e la chiamata Android nativa `setSystemBarsAppearance`.
Target SDK 35, nessun framework UI o dipendenza dell'app. Compilata localmente,
installata esclusivamente sugli emulatori e rimossa al termine.
APK SHA-256 `a417964f29dbd01ec9e7c03aa88aef499ccb179122edea024bced762684b6e8c`.

Su API 35 la richiesta LIGHT restituisce flag `0`, DARK restituisce `16`, ma
i tre tasti rimangono scuri in entrambi i casi:
[LIGHT](evidence/android-ui-fixes-2026-10-13/api35-native-probe-light-icons.png),
[DARK](evidence/android-ui-fixes-2026-10-13/api35-native-probe-dark-icons.png).
La stessa APK diagnostica su API 36, con sistema chiaro e richiesta LIGHT,
produce correttamente [tasti bianchi](evidence/android-ui-fixes-2026-10-13/api36-native-probe-light-icons.png).
Il dump riporta `mHasLightNavigationBar=false` e intensità scura `0`, mentre il
launcher applica un override dello sfondo a `1`:
[estratto diagnostico](evidence/android-ui-fixes-2026-10-13/api35-bar-diagnostics.txt).
Questa evidenza attribuisce il comportamento osservato all'immagine di sistema,
non alla logica Meteo Friûl. Non dimostra che tutti i dispositivi Android 15 siano
esenti dal difetto: resta la verifica su un'altra immagine o su dispositivo reale.

Riferimenti primari consultati: [stili SystemBars Capacitor](https://capacitorjs.com/docs/apis/system-bars),
[barre e protezioni Android](https://developer.android.com/develop/ui/views/layout/edge-to-edge),
[gestione colori nel launcher AOSP](https://android.googlesource.com/platform/packages/apps/Launcher3/+/5a28d10fa04f45f52091101babd858e30ecff5d2/quickstep/src/com/android/launcher3/taskbar/NavbarButtonsViewController.java).
Il sorgente AOSP è un riscontro del meccanismo di override, non una certificazione
della versione Google del launcher installata nell'AVD.

## Controlli e limiti di rilascio

- [133 test frontend mirati](evidence/android-ui-fixes-2026-10-13/targeted-tests.log): PASS.
- [9 release guard](evidence/android-ui-fixes-2026-10-13/release-guard.log): PASS.
- [Contratto R8](evidence/android-ui-fixes-2026-10-13/r8-contract.log): PASS.
- [Build TEST protetta](evidence/android-ui-fixes-2026-10-13/build.log): PASS.
- [Pulizia workspace](evidence/android-ui-fixes-2026-10-13/cleanliness.log): PASS.
- [Manifest della candidata](evidence/android-ui-fixes-2026-10-13/candidate.json)
  e [hash delle evidenze](evidence/android-ui-fixes-2026-10-13/SHA256SUMS.txt).
- API deprecate: nessun nuovo setter colore o opt-out; nessun aggiornamento di
  toolchain. Gli avvisi delle dipendenze e l'esito Play non sono ricertificati.
- Orientamento: verifiche mirate sopra; tablet, multi-window e matrice completa
  delle altre sezioni NON VERIFICATI in questo intervento.
- Android precedente alla 15 NON VERIFICATO: non presente tra le immagini locali.
- Telefono reale e runtime R8 minificato NON VERIFICATI. Nessuna deroga approvata.

Il rilievo visivo API 35 resta registrato. Questa sessione non costituisce un
via libera al rilascio o alla promozione su main.
