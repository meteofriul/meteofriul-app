# Segnalazioni TEST: collaudo sul telefono — 13 ottobre 2026

Installazione autorizzata nel seguito della richiesta di provare la TEST sul
telefono, dopo il collaudo sugli emulatori. Superate le prove mirate di invio
con GPS reale, ricezione della conferma, punto assegnato e storico. Non equivale
al completamento della matrice di rilascio. Durante una chiamata i tocchi sono
stati sospesi e ripresi soltanto dopo il «pronto» del proprietario.

## Candidata e ambiente

- Ramo locale `codex/community-reports-simplification`, HEAD prima del resoconto
  `1938f421ea8913a40c637082f95b2cb83a98fd30`.
- Stessa APK del [collaudo emulatori](ANDROID_TEST_UI_FIXES_2026-10-13.md),
  costruita sul commit `6209e8990588c7f7ed97cdabc63d819d777c850d`.
  Nessuna differenza in `frontend` e `backend` rispetto alla candidata.
- SHA-256 `542b36e5a142012502a55a41e589706455813fbec4c41ad72f56c4684deb537f`.
  Verificata anche la copia dell'APK riletta dal telefono dopo l'installazione.
- Package `com.meteofriul.app.localpilot`, versione `0.1.14-local-pilot`,
  versionCode `300031`, target SDK 36, debug non minificata.
- Samsung Galaxy A52, modello `SM-A525F`, Android 14/API 34,
  `samsung/a52qnseea/a52q:14/UP1A.231005.007/A525FXXSCFYF1:user/release-keys`.
  Schermo 1080 × 2400, densità 420, navigazione a tre tasti, sistema scuro.
- Prima installazione del pacchetto `localpilot`, eseguita con `adb install -r`.
  Il pacchetto non era presente: nessuna migrazione del profilo dalla precedente
  TEST `com.meteofriul.app.tester`.
- Community su SQLite locale, `127.0.0.1:8783/api`; salute verificata con
  `storage: sqlite`, `published: false`. Connessione USB con ADB reverse 8783
  e 8781. Questa candidata richiede PC, servizi locali e collegamento USB.
- Servizi verificati tramite `scripts/start-local-weather-pilot.ps1
  -CommunityPilot -WeatherTestNow 2026-09-04T05:00:00Z`; riusati i processi
  canonici già attivi. L'APK usa la fixture meteo del 4 settembre alle 12:00Z:
  i dati meteo di questa build non rappresentano le condizioni correnti.

## Esiti disponibili

| Caso | Esito |
| --- | --- |
| Firma e identità APK | PASS: firma verificata; hash installato uguale alla candidata |
| App preesistenti | PASS: versione e data di aggiornamento di `com.meteofriul.app` e `com.meteofriul.app.tester` identiche prima/dopo |
| Avvio | PASS: primo avvio, selezione Italiano e sezione Meteo aperti |
| Barre, verticale, sistema chiaro/scuro | PASS: stato e tre tasti leggibili con app su Sistema; verificata anche app chiara con sistema scuro |
| Selettore Comune con tastiera | PASS visivo iniziale: dialogo e chiusura visibili, tastiera aperta e richiusa |
| Orizzontale e rotazione inversa | PASS accessibilità: comandi e compositore raggiunti con scorrimento; navigazione laterale leggibile |
| GPS reale e invio | PASS: permesso preciso durante l'uso, Comune Pordenone rilevato dal telefono; Pioggia inviata dalla UI alle 22:01 locali |
| Conteggi prima della conferma | PASS: 1 inviata, 0 confermate, 0 punti |
| Conferma da altra installazione | PASS: emulatore Android 16 conferma dalla UI con posizione Android Pordenone; dopo riavvio della TEST sul telefono 1 inviata, 1 confermata, 1 punto |
| Nessun premio al confermante | PASS: emulatore B conserva i precedenti 1 inviata, 1 confermata, 1 punto |
| Storico 48 ore | PASS consultazione e scorrimento: propria Pioggia attiva con 1 punto; Neve scaduta precedente senza azioni di voto. Non attese 48 ore reali |
| R8 | NON VERIFICATO: APK debug, prova minificata separata |

Schermate e riscontri dell'installazione sono conservati in
[evidence/community-phone-2026-10-13](evidence/community-phone-2026-10-13/SHA256SUMS.txt).
Nessuna nuova esecuzione dei test di codice:
la candidata è invariata rispetto alle prove documentate sugli emulatori.

I due profili hanno casualmente lo stesso alias visibile, ma sono installazioni
distinte: il voto è accettato e non è un'autoconferma. Non alterati il tempo o i
premi. La Community del telefono resta esclusivamente locale. Per vedere le
osservazioni è stata selezionata Pordenone: con Udine attiva lo storico della
zona era vuoto. Tema app ripristinato su Sistema, sistema scuro, orientamento
di sistema verticale con rotazione automatica disattivata, come all'inizio.

Il GPS dell'emulatore era già disponibile su Pordenone: il tentativo di
aggiornarlo con `emu geo fix` ha restituito «unknown command» e non è conteggiato
come eseguito. Il voto successivo è riuscito con il provider Android esistente.
Non provati in questa sessione il voto dal telefono, la sostituzione del proprio
invio, tutti i limiti antispam, gesti Samsung, tablet o multi-window.

## Scelta di prodotto successiva alle prove

Il proprietario ha precisato: **smartphone solo in verticale, nessuna opzione
di rotazione**. I controlli di orientamento su schermi grandi restano necessari:
Android 16 ignora le restrizioni sugli schermi con larghezza minima >= 600 dp;
i telefoni sotto tale soglia sono esclusi da questa modifica della piattaforma.
[Riferimento Android](https://developer.android.com/about/versions/16/behavior-changes-16#large-screens).
La candidata sopra precede l'implementazione di questa scelta.

Main resta `5a68de5dc1607105f921d4d2b731170f1a8a0446`. Nessun push GitHub,
AAB, Play o pubblicazione. L'installazione sul telefono non autorizza la
promozione su main. Il caso dei tre tasti dell'immagine Android 15 rimane
registrato nel resoconto precedente.
