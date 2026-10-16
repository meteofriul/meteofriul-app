# Android edge-to-edge — verifica e promozione del 12 ottobre 2026

Ramo di integrazione: `codex/android-edge-to-edge`, basato su
`origin/main` a `42cc815e82bb9e741b7cc0ecf7eaca9a4eb1f705`.
Il 12 ottobre il proprietario ha accettato il collaudo sugli emulatori
("se passano sull'emulatore per me va bene") e poi autorizzato la promozione
("portiamo su main?"). Per questo intervento il controllo sul telefono reale
non e richiesto. La decisione non modifica il criterio generale di AGENTS.md.

## Comportamento risultante

- `WindowCompat.enableEdgeToEdge` abilita la gestione compatibile delle barre.
- Il plugin non chiama direttamente i setter deprecati dei colori delle barre
  o del contrasto della status bar. `ProtectionLayout` e `ColorProtection`
  disegnano gli sfondi blu, con icone chiare in entrambi i temi.
- Il contenitore esterno copre i bordi della finestra. Il contenitore interno
  applica solo il margine della tastiera; CSS gestisce barre e ritagli dello
  schermo, evitando di sommare due volte gli spazi.
- Gli inset CSS conservano tre decimali alle densita frazionarie e vengono
  ripristinati dopo caricamento, ricaricamento, ripresa e cambio configurazione.
  L'iniezione verifica che `document.documentElement` esista durante l'avvio.
- `adjustResize` rende esplicita la gestione della tastiera; il margine CSS
  inferiore diventa zero mentre questa e visibile.
- Capacitor mantiene icone chiare con `SystemBars.style = DARK`; la sua
  gestione automatica degli inset rimane disabilitata.
- I temi non impostano piu i colori deprecati delle barre. Gli attributi delle
  icone di navigazione sono limitati a `values-v27`, compatibile con minSdk 24.

Il plugin e il layout nativo provengono dalla TEST verificata. I margini CSS
sono gli stessi, con lo sfondo Web scuro allineato al colore nativo gia
presente. La configurazione `adjustResize` e lo stile delle icone vengono
applicati al pacchetto principale, senza importare suffisso, permessi rimossi,
branding o funzioni riservate al pacchetto TEST.

Orientamento, R8, notifiche, dipendenze, versione, firma e risorse di branding
non cambiano. Questa promozione riguarda i sorgenti: non produce un AAB,
non pubblica su Play e non installa sul telefono.

## Verifiche

- Pulizia workspace canonico: superata.
- TEST: build protetta del pacchetto `com.meteofriul.app.tester`, versione
  `300031 / 0.1.14-tester`, completata; 5 file Vitest e 23 test superati.
- Emulatore Android 15/API 35 e Android 16/API 36: avvio, Home, impostazioni,
  temi chiaro/scuro, inset, tastiera, ricaricamento e ripresa verificati.
  Nessun crash dell'app osservato. Insets con densita 2.625: superiore
  51.810 px, inferiore 24 px con gesti oppure 48 px con tre tasti;
  con tastiera la viewport passa da 915 a 578 px e l'inset inferiore a zero.
- Controllo JavaScript dell'iniezione nativa: documento non ancora disponibile
  senza eccezioni; quattro valori frazionari applicati al documento pronto.
- Ramo finale di integrazione: 4 file Vitest, 19 test superati su barre,
  safe area e layout; compilazione debug del codice nativo e dei test
  strumentali e `testDebugUnitTest` superati. Nessun nuovo APK prodotto.
- I test strumentali includono geometria, cutout sintetico, tastiera,
  ricaricamento e temi; le aspettative ora conservano i decimali degli inset.
  La precedente implementazione del ramo aveva superato 5 test su API 36
  sia con gesti sia con tre tasti. Questo dato storico non equivale a una
  nuova esecuzione strumentale sull'integrazione finale.
- Il lint Android completo non e verde: la precedente build del pacchetto
  principale riportava 3 errori `MissingPermission` nei file invariati di
  localizzazione; la TEST riportava 9 errori, inclusi quelli del manifest
  isolato e dei suoi temi. Nessuna soppressione aggiunta per nasconderli.

## Eccezione dell'emulatore Android 15

Con tema di sistema chiaro i tre tasti sono scuri sullo sfondo blu. Il
problema e stato riprodotto in una Activity Android indipendente, priva di
WebView, Capacitor e AndroidX: anche richiedendo icone bianche (`appearance=0`)
il launcher dell'emulatore applica il proprio colore. La navigazione a gesti
e corretta; su Android 16 anche i tre tasti sono leggibili.

Immagine: `google/sdk_gphone64_x86_64/emu64xa:15/AE3A.240806.043/12960925:userdebug/dev-keys`,
patch di sicurezza `2024-09-05`. Nessuna modifica grafica dell'app introdotta
per compensare questo difetto; comportamento su un telefono Android 15 non
verificato. Durante un cambio rapido della configurazione e stato osservato
anche un warning Capacitor non fatale relativo al thread del vecchio bridge.

## Evidenze locali e limite Play

La TEST conserva `.tmp/android-edge-to-edge/verification.json`, le schermate
e la prova nativa `native-probe/api35-white-request.png` e relativo log.
L'APK TEST verificato ha SHA-256
`1F1B269A9511637B1D73B018B8999A96E477FD5D9B59115AC0969C3FC79370C8`.
Il log della compilazione finale di integrazione e nel workspace canonico:
`.tmp/edge-to-edge/promotion-native-check.log`.
Gli artefatti locali sono ignorati da Git e non vengono pubblicati.

AndroidX usa ancora chiamate alle API deprecate per compatibilita con le
versioni precedenti. La rimozione di tutte le segnalazioni di Play non puo
essere certificata senza l'analisi di un futuro bundle; nessun bundle e stato
prodotto o caricato per questa promozione.

Riferimenti ufficiali:

- [Guida edge-to-edge Views](https://developer.android.com/develop/ui/views/layout/edge-to-edge)
- [WindowCompat.enableEdgeToEdge](https://developer.android.com/reference/androidx/core/view/WindowCompat#enableEdgeToEdge(android.view.Window))
- [Comportamenti Android 15](https://developer.android.com/about/versions/15/behavior-changes-15)
