# Android 0.1.8 - hardening tecnico

Stato: audit e refactoring R8 implementati sul ramo isolato
`codex/android-0.1.8-r8-hardening`; collaudo dell'APK minificata completato su
emulatore Android 16/API 36. Installazione Play/telefono reale, edge-to-edge e
large-screen restano separati e non completati.

Audit ed evidenze R8 verificabili:
`docs/operations/ANDROID_0.1.8_R8_AUDIT.md`. La configurazione abilita ora
minificazione e resource shrinking per la release, ma non autorizza la
generazione di una nuova AAB.

Questa checklist riguarda la versione successiva alla `0.1.7 (300024)` gia'
inviata a Google Play. Non richiede il ritiro o la modifica dell'artefatto
`0.1.7` in revisione.

## Perimetro del refactoring

La `0.1.8` prevede un refactoring tecnico mirato, non una riscrittura generale
dell'app. Prima delle modifiche deve essere prodotta una mappa verificabile di:

- attivita', plugin nativi e API Android che governano barre di sistema,
  orientamento, ridimensionamento e inset;
- schermate Web che consumano safe area o dipendono da dimensioni/orientamento;
- componenti raggiunti tramite reflection o registrazione dinamica che R8 non
  deve eliminare;
- flussi critici da preservare: Firebase, App Check, notifiche, background
  worker, geolocalizzazione, fotocamera, mappe, deep link e sponsor.

Il refactoring deve rimuovere soltanto dipendenze deprecate o assunzioni non
piu' valide, mantenendo invariati i contratti funzionali e backend. Separatamente,
il `mapping.txt` generato da R8 deve essere conservato per rendere leggibili e
diagnosticabili gli stack trace della build offuscata.

## Segnalazioni Google Play da chiudere

### Ottimizzazione DEX con R8

- abilitare `minifyEnabled true` per la build release;
- abilitare `shrinkResources true`;
- usare il profilo ottimizzato `proguard-android-optimize.txt`;
- aggiungere soltanto le regole keep necessarie a Capacitor, plugin nativi,
  Firebase, WorkManager e componenti raggiunti tramite reflection;
- conservare e archiviare `mapping.txt` e i simboli nativi associati esattamente
  all'AAB pubblicato;
- verificare che shrinking, ottimizzazione e offuscamento superino la soglia
  comunicata da Google Play.

### Edge-to-edge Android 15/16

- sostituire nel plugin `MeteoSystemBarsPlugin` l'uso delle API deprecate
  `setStatusBarColor`, `setNavigationBarColor` e
  `setNavigationBarDividerColor`;
- adottare l'edge-to-edge tramite API AndroidX compatibili;
- mantenere il contrasto corretto delle icone di status bar e navigation bar
  nei temi chiaro, scuro e di sistema;
- completare la gestione degli inset e delle safe area a livello globale,
  evitando sovrapposizioni su header, barra inferiore, mappe, tastiera, sheet,
  dialoghi e schermate a tutto schermo;
- prevedere nell'interfaccia gli eventuali scrim necessari, senza dipendere dal
  colore imposto alle barre di sistema.

### Schermi grandi, pieghevoli e orientamento

- rimuovere da `MainActivity` il vincolo manifest
  `android:screenOrientation="portrait"`;
- verificare che nessuna logica dipenda dall'orientamento verticale forzato;
- rendere utilizzabili Home, Meteo, Tempo reale, Segnalazioni, Eventi, Scopri e
  Impostazioni in landscape e su finestre larghe;
- verificare mappe, webcam, fotocamera, sheet, dialoghi e tastiera su tablet e
  pieghevoli;
- controllare che il layout rimanga leggibile quando Android ridimensiona
  liberamente l'attivita'.

## Matrice minima di collaudo

- telefono reale con Android 15/16, se disponibile;
- navigazione a gesture e navigazione a tre pulsanti;
- tema chiaro, scuro e di sistema;
- portrait e landscape;
- emulatore tablet e pieghevole con larghezza almeno `600dp`;
- avvio, splash, launcher, Home e tutte le schede principali;
- login/registrazione Firebase anonima, App Check, Allerte e Avvisi;
- segnalazione meteo, fotocamera, mappe, deep link e notifiche;
- catalogo sponsor nelle sezioni Home, Eventi e Scopri;
- installazione come aggiornamento con dati locali conservati.

## Gate di rilascio

- non modificare la `0.1.7 (300024)` gia' sottoposta a revisione;
- assegnare alla nuova AAB un nuovo `versionCode` e il `versionName 0.1.8`;
- eseguire tutti i test frontend, backend e Android pertinenti;
- eseguire il guarded build esclusivamente con
  `scripts/build-play-aab.ps1`, senza un `android:sync` manuale preliminare;
- installare prima la build di verifica sul telefono reale e controllare che i
  dati dell'app siano preservati;
- completare il controllo visivo di launcher, splash, Home, barre di sistema e
  navigazione;
- caricare inizialmente la AAB nel test interno;
- rieseguire il read-back Firebase e una prova reale di Allerte e Avvisi prima
  di promuovere la release.
