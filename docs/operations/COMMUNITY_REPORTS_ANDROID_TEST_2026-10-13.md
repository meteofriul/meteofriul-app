# Segnalazioni: collaudo Android della TEST — 13 ottobre 2026

Aggiornamento successivo: [correzioni e nuovo collaudo delle barre e del pannello](ANDROID_TEST_UI_FIXES_2026-10-13.md).
Le righe sotto descrivono la candidata precedente; il seguito risolve il taglio
del pannello e documenta separatamente l'anomalia dei tre tasti dell'AVD 15.

Le prove principali Community sono passate su emulatori Android 15 e 16 con GPS.
Il collaudo Android complessivo **non è interamente verde**: restano il contrasto
dei tre tasti su Android 15 con sistema chiaro e il pannello tagliato in orizzontale.

Ramo: `codex/community-reports-simplification`. Community esclusivamente locale:
`127.0.0.1:8783`, SQLite, contratto `community-reports-v3`. Main è rimasto
`5a68de5dc1607105f921d4d2b731170f1a8a0446`. Nessun push GitHub, modifica a
produzione/Play, AAB o installazione sul telefono.

## Candidati e correzioni

| Candidato | Commit del codice | APK SHA-256 | Prove |
| --- | --- | --- | --- |
| Prima prova | `1923c2e79e86bc2477b727f1ff0bcda1679b17f5` | `3fc435b7558c8b97ad83842d3398024b8b6d28bad33ca7c9267f939b3eb37077` | Invio Android 15, primo conteggio, intervallo minimo, tastiera e primo storico |
| Pannello corretto | `b842b925` | `5065a4f29b71c0a074a91196885bf2dd2b4360e5070f9f41a9686e1350e18563` | Conferma e invio Android 16, GPS, punti e selettore storico |
| Finale | `650e55d495c9a11f48a721a9d4bc6ecdbae1e047` | `51a84441020c86aa84f9ecc086148b38d7207e03b18871240551897f82e0ecb6` | Installata con aggiornamento su entrambi; dati conservati, storico, invio/sostituzione e voti Android 15, barre e rotazione |

Package `com.meteofriul.app.localpilot`, versione `0.1.14-local-pilot`,
versionCode `300031`, target SDK 36. Variante debug non minificata.
APK finale locale: `.tmp/community-rules-evidence/meteofriul-community-rules-test-final.apk`.
[Identità della candidata](evidence/community-reports-2026-10-13/candidate.json).

Build protetta `scripts/build-android-local-weather-pilot.ps1 -CommunityPilot`,
con fixture meteo del 4 settembre. Community usa l'ora corrente.
I servizi meteo locali non disponibili non sono stati inclusi nell'esito Community.
La build finale è riuscita; log integrale locale in
`.tmp/community-rules-evidence/android-build-final.log`.

Correzioni limitate effettuate durante il collaudo:

- Spazio dedicato al selettore Recenti / Storico nel pannello compatto, prima
  schiacciato dalla prima scheda. Mappa, icone, navigazione e flusso preservati.
- Linee guida IT/FUR allineate a «fenomeno terminato» al posto di «smentire».
  Aggiornate anche aspettative dei test sui pulsanti che usavano ancora le vecchie diciture.

## Ambiente e metodo

- Android 15/API 35, AVD `MeteoFriul_R8_Opt_API35`, Pixel 7, 1080 × 2400,
  densità 420: `google/sdk_gphone64_x86_64/emu64xa:15/AE3A.240806.043/12960925:userdebug/dev-keys`.
- Android 16/API 36, AVD `MeteoFriul_Community_API36`, 1080 × 2400, densità 420:
  `google/sdk_gphone64_x86_64/emu64xa:16/BE2A.250530.026.D1/13818094:user/release-keys`.
- GPS simulato tramite provider Android: Pordenone 45.957 / 12.661; negativo
  Trieste 45.65 / 13.77. Nessun mock del GPS JavaScript nei flussi verificati.
- Invii e voti eseguiti nell'interfaccia dell'APK. HTTP GET e SQLite in sola
  lettura usati per riscontro dei contatori; nessuna alterazione del tempo o dei premi.
- Installazioni distinte: A = Cjavre dal Troi (Android 15), B = Cjampane dal Cîl
  (Android 16). Orologi emulatori UTC: negli screenshot le ore sono due ore
  indietro rispetto a Europe/Rome; le durate e le scadenze sono coerenti.
- ADB reverse 8781/8783, sempre con seriale emulatore esplicito. Per la parte
  finale server ADB 5038, seriali `emulator-5588` (16) e `emulator-5590` (15).
- Esecuzione in sequenza per la RAM disponibile. Per Android 16 creato AVD pulito
  dopo problemi di autenticazione del precedente, che è stato conservato.
  Nessun crash report inviato. Il telefono collegato è rimasto escluso.

## Risultati funzionali

| Caso | Esito e riscontro |
| --- | --- |
| Invio con GPS | PASS: A invia Grandine a Pordenone; ricevuta e durata 60 minuti. Prima della conferma: 1 inviata / 0 confermate / 0 punti. |
| Antispam 3 minuti | PASS sul primo APK: tentativo Neve prima della scadenza bloccato con 45 secondi residui; Grandine mantenuta. [Schermata](evidence/community-reports-2026-10-13/api35-cooldown.png). |
| Conferma da altra installazione | PASS: B conferma A con GPS Pordenone; A ottiene 1 punto e 1 confermata. B resta 0 invii / 0 confermate / 0 punti. [Profilo di B](evidence/community-reports-2026-10-13/api36-profile.png). |
| Invio indipendente nello stesso gruppo | PASS: B invia Grandine a Pordenone e ottiene 1 inviata / 1 confermata / 1 punto; A rimane a 1 punto. [B dopo aggiornamento APK](evidence/community-reports-2026-10-13/api36-final-data.png). |
| GPS fuori Comune per «Non c’è più» | PASS: B con GPS Trieste non può votare il fenomeno a Pordenone; conteggio no resta 0. [Schermata](evidence/community-reports-2026-10-13/api36-gps-wrong-comune.png). |
| GPS cambiato durante l'invio | PASS: riepilogo iniziale Trieste, GPS nuovo Pordenone alla conferma; invio interrotto e richiesto nuovo riepilogo. Dopo nuova approvazione viene inviata Pordenone. [Schermata](evidence/community-reports-2026-10-13/api36-review-gps-changed.png). |
| Sostituzione senza ereditare conferme | PASS su APK finale: A invia Neve; la propria Grandine esce dalle attive e resta nello storico. Neve ha sì 0 / no 0. Profilo A: 2 inviate / 1 confermata / 1 punto. [Profilo](evidence/community-reports-2026-10-13/api35-final-profile-replaced.png), [dati visibili](evidence/community-reports-2026-10-13/final-visible-reports.json). |
| Storico 48 ore | PASS in verticale su entrambi: voci attive/scadute/sostituite, scorrimento e consultazione senza voto. Il punto compare sulla propria Grandine sostituita. [Android 15](evidence/community-reports-2026-10-13/api35-final-history-replaced.png), [Android 16](evidence/community-reports-2026-10-13/api36-final-history.png). Non attese 48 ore reali: il taglio temporale resta coperto dai test server. |
| Voti sulla candidata finale | PASS Android 15: «Confermo» fuori Comune respinto; riportato GPS a Pordenone, conferma accettata (sì 2). Successivo «Non c’è più» accettato (sì 1 / no 1). Nessun punto duplicato o sottratto. [GPS respinto](evidence/community-reports-2026-10-13/api35-confirm-wrong-comune.png), [conferma](evidence/community-reports-2026-10-13/api35-final-confirm.png), [termine fenomeno](evidence/community-reports-2026-10-13/api35-final-ended.png). |
| Aggiornamento APK e ripresa | PASS: installazione `-r` su entrambi conserva alias, preferenze, invii e punti; provata ripresa dal background. |

[Contatori e archivio finali letti da SQLite](evidence/community-reports-2026-10-13/final-counters.json).
La Grandine ancora attiva sulla mappa dopo la sostituzione è quella di B,
non quella ritirata automaticamente di A.

Le soglie 4/ora e 12/giorno, 3 ore dall'ultimo premio per autore/fenomeno/Comune,
tranquillo senza punti, ranghi 5/15, concorrenza e scadenza sono coperti dai test
server precedenti; non riprodotti tutti con attese reali sugli emulatori.

## Standard Android: esiti e limiti

| Area | Esito |
| --- | --- |
| Edge-to-edge e inset | In verticale: intestazione, navigazione e dialoghi accessibili su 15/16; tastiera del selettore Comune verificata su 15 nel primo APK. 19 test Web/CSS passati. Non equivale a copertura completa di tutte le schermate e dispositivi. |
| Contrasto delle barre | **APERTO** su 15 con sistema chiaro e tre tasti, riprodotto anche sull'APK finale dopo ripresa: tasti grigio scuro su blu. [Evidenza](evidence/community-reports-2026-10-13/api35-final-system-light.png). Con sistema scuro i tasti tornano chiari. Su 16, sistema chiaro e tre tasti: icone chiare leggibili. Gesti leggibili nelle prove. |
| Cambio configurazione | **APERTO**: icone della barra di stato temporaneamente scure dopo cambio tema su 15 e rotazione su 16; tornano chiare dopo background/ripresa. Non classificato come risolto. |
| API deprecate | Nessuna modifica nativa. Nei sorgenti applicativi assenti `setStatusBarColor`, `setNavigationBarColor`, `setNavigationBarDividerColor` e opt-out edge-to-edge. Non certificata la rimozione di avvisi Play o chiamate interne delle dipendenze. Il precedente warning PushNotificationsPlugin non è classificato come API delle barre. |
| Rotazione, ridimensionamento e schermi grandi | Manifest ridimensionabile, nessun blocco di orientamento. Rotazione eseguita su 15/16: **APERTO**, il pannello supera l'altezza disponibile e taglia selettori/prime schede. [Android 15](evidence/community-reports-2026-10-13/api35-final-landscape.png), [Android 16](evidence/community-reports-2026-10-13/api36-final-landscape.png). Ritorno verticale funzionante. Tablet e multi-window non verificati. |
| R8 e risorse | Contratto configurazione R8 PASS; 9 test release guard PASS. Questa APK è debug: runtime minificato, mapping e confronto release **non verificati**. |

Restano da verificare anche una versione Android precedente alla 15 e il telefono
reale. I rilievi di barre e orientamento richiedono correzione e nuovo collaudo;
nessuna deroga è stata approvata. Il presente esito non autorizza main, AAB,
Play o produzione.

## Controlli automatici ed evidenze

- [159 test mirati frontend](evidence/community-reports-2026-10-13/final-targeted-tests.log)
  su candidata finale: copy, storico, voti, invio/GPS, CSS e pannello mappa.
- [19 test Android/CSS](evidence/community-reports-2026-10-13/android-css-tests.log),
  [9 release guard](evidence/community-reports-2026-10-13/release-guard.log),
  [contratto R8](evidence/community-reports-2026-10-13/r8-contract.log).
- [Pulizia workspace canonico](evidence/community-reports-2026-10-13/cleanliness.log)
  e `git diff --check` superati.
- Precedenti 991 test frontend e 156 backend: vedi
  [documento delle regole](COMMUNITY_REPORTS_RULES_PROPOSAL_2026-10-13.md).
  Non presentati come nuova esecuzione completa di questa sessione.

Schermate, log selezionati e manifest sono conservati in
`docs/operations/evidence/community-reports-2026-10-13/`, con
[hash SHA-256](evidence/community-reports-2026-10-13/SHA256SUMS.txt).
Le altre schermate e i log integrali restano in `.tmp/community-rules-evidence/`.
