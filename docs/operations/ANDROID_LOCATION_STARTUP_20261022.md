# Posizione automatica: conservazione della preferenza all'avvio

**22 ottobre 2026 — correzione locale verificata, non distribuita e non promossa
su main.** Ramo codex/android-location-startup-preservation, base
3da1db2d4d2f1de4bd14745ef7fd078ec8d399dd. La 0.1.15 / 300033 del test interno
rimane l'artefatto già installato; nessuna build, versione o configurazione cloud
è stata cambiata. Sponsor disattivati.

## Difetto riprodotto

All'avvio Android, App esegue nuovamente la richiesta della posizione.
Il callback di startup non specificava keepAutomaticModeOnTemporaryFailure,
che nel risolutore vale false per impostazione predefinita. Un timeout GPS,
un servizio Posizione temporaneamente spento, un fix troppo vecchio/impreciso
oppure un errore della risoluzione della località potevano quindi scrivere
autoLocationEnabled=false, anche se la preferenza salvata era attiva.

Il normale percorso di ripresa Android e il controllo Web già conservano
la preferenza in queste condizioni. La correzione applica la stessa opzione
anche all'avvio Android. L'errore resta esposto e l'ultima località non viene
sostituita con una posizione non verificata. Un successivo controllo ordinario
può recuperare senza chiedere all'utente di riattivare l'interruttore.

Restano invariati lo spegnimento volontario, il permesso negato, il runtime
non supportato e la prima attivazione fallita. Non vengono riattivate preferenze
già memorizzate come disattivate: non è possibile distinguere retroattivamente
una scelta dell'utente da una disattivazione causata dal difetto.

## Rapporto con LOCATION-UPDATE-01

Il codice di startup, storage, bootstrap e policy esaminato sulla base main è
identico al corrispondente codice sorgente della AAB
f82503e4daabc283a5caf77b49e7cf58439abf61. Il difetto è dunque presente anche
nella sorgente installata, ma **non prova la causa dell'episodio riferito dal
proprietario dopo l'aggiornamento Play**. Non è dimostrato che quel primo avvio
abbia ricevuto uno degli errori riprodotti.

Mancano lo stato della preferenza prima dell'aggiornamento e la lettura immediata
successiva, prima di qualsiasi interazione. Il rilievo LOCATION-UPDATE-01 resta
aperto per la verifica su dispositivo. Non si attribuisce la causa al file
Capacitor mancante; NATIVE-CONFIG-01 e BULLETIN-MAP-01 restano lavori separati.

## Verifica locale

Test di integrazione frontend/src/app/App.locationStartup.test.jsx:
App, storage locale, controllo della qualità GPS, avvio Android e policy di
ripresa sono reali; GPS, risoluzione della località, servizi esterni e componenti
visivi sono sostituiti con confini controllati. Nessuna richiesta HTTP reale
consentita dal test. Non è un emulatore né una prova di aggiornamento Play.

| Controllo | Risultato |
| --- | --- |
| Prima della correzione | 6 regressioni falliscono: la preferenza attiva diventa false; 4 controlli negativi passano |
| Dopo la correzione | Tutti i 10 casi della regressione passano |
| Suite pertinente | 10 file, 114 test superati, un solo worker |
| Analisi statica | ESLint sui due file modificati: superato |
| Prova sul Galaxy / aggiornamento Play | Non eseguita; nessuna installazione autorizzata in questa attività |

I casi coprono timeout, servizio Posizione spento, fix impreciso, errore reverse,
recupero con una nuova posizione alla ripresa, permesso negato, runtime non
supportato, preferenza esplicitamente spenta, prima richiesta fallita e
spegnimento volontario mantenuto al successivo avvio.

Comando della suite, dalla radice del checkout:

    node frontend/node_modules/vitest/vitest.mjs run --configLoader native --root frontend src/app/App.locationStartup.test.jsx src/app/autoLocationRuntime.test.js src/app/appLocation.test.js src/app/androidStartupRuntime.test.js src/app/locationActions.test.js src/domain/startup/androidStartupPromptFlow.test.js src/domain/startup/androidPermissionGate.test.js src/domain/geo/autoLocationPolicy.test.js src/services/capacitorAppResume.test.js src/features/settings/SettingsView.notificationLocationIndependence.test.jsx --maxWorkers 1

Le dipendenze sono una copia fisica integrale già disponibile localmente,
con lockfile identico alla base main; nessun aggiornamento o download di pacchetti.
Gli hash dei log e i conteggi sono nel
[riepilogo della verifica](evidence/location-startup-20261022/verification.json).
I log completi restano in .tmp/location-startup-check/.

## Passaggio successivo

Prima della promozione del codice, verificare su dispositivo la conservazione
della preferenza e il recupero dopo un errore temporaneo, mantenendo le scelte
esplicitamente disattivate. Alla prossima installazione autorizzata acquisire
separatamente, prima e subito dopo: interruttore dell'app, permessi Android
e servizio Posizione del sistema. Questa attività non autorizza build,
caricamenti Play, installazioni, push, deploy o notifiche manuali.

Lo [stato della 0.1.15](RELEASE_0.1.15_STATUS_20261021.md) conserva gli altri
rilievi e i gate di rilascio.

## Integrazione nella release, 22 ottobre

Il commit `2e5fc0b6` è incorporato in `codex/release-0.1.15` tramite `a3290715`,
dopo l'allineamento a main `d62683b9`. La suite frontend completa della base
integrata supera 5.030 test, con 13 saltati; include i dieci casi di regressione
qui descritti. Web e asset Web Android sono compilati dallo stesso frontend.

Questo non promuove la correzione su main, non modifica la AAB 300033 e non prova
la conservazione della preferenza durante un aggiornamento Play. Il rilievo
runtime resta aperto. [Verbale dell'integrazione](RELEASE_WEB_ALIGNMENT_20261022.md).
