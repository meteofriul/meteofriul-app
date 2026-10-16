# Pilota aggiornata sul Samsung — 10 settembre 2026

Aggiornamento richiesto dall'utente per la prova nell'uso quotidiano. Sorgenti
compilati: **`c54cdb9`**, worktree `fb42`, senza modifiche di codice aggiuntive.
Installazione alle **16:55:57 Europe/Rome / 14:55:57 UTC** sul Samsung A52
`SM-A525F`, seriale `OWNER_DEVICE_SERIAL`.

## Identità e prova dell'aggiornamento

- Package esclusivo: `com.meteofriul.app.localpilot`.
- Versione dichiarata invariata: `1.0.1-local-pilot`, versionCode `300012`.
  Non usare questi soli numeri per distinguere questa build da quella del 9.
- Nuovo SHA256, identico per APK prodotta e `base.apk` sul dispositivo:
  `9a1dfb212343e412ff7b6df5477c51913d91fb7877d4d1c8be9aa487b5b13b57`.
- APK precedente sul dispositivo:
  `e17ea2483f0cb7762f385c5fc70b873c8bf629ceed410c8a2d7df7b5a57054bf`,
  aggiornamento del 9 settembre alle 18:44:34.
- Installazione `adb -s OWNER_DEVICE_SERIAL install -r`: `Success`. Nessuna
  disinstallazione, cancellazione dati/cache/preferenze o reset dei permessi.
- `firstInstallTime=2026-09-04 11:11:31` conservato.

APK archiviata localmente, non pubblicata:
`.dev-logs/local-weather-pilot/meteofriul-pilot-20260910-c54cdb9.apk`.
Screenshot reale dell'avvio, acquisito soltanto con la pilota in primo piano:
`.dev-logs/local-weather-pilot/installed-20260910-c54cdb9.png`.

## Build e controlli

Script protetto eseguito fuori sandbox dalla root, senza normale `android:sync`:

```powershell
.\scripts\build-android-local-weather-pilot.ps1 -ApiBase 'https://cfweb-bcee09e---meteofriul-api-bx24xqvcda-ew.a.run.app/api' -WeatherCloud
```

Meteo pilota su `https://pilot-weather-335641913741.europe-west1.run.app`.
Nessun orologio simulato, loopback o `adb reverse`. Guard endpoint, identità APK,
isolamento Capacitor e launcher approvato superati: **82.944 pixel coincidenti**,
11 asset launcher verificati, nessuna rigenerazione del marchio.

Test Node eseguiti in un'unica sessione:

```powershell
node --test frontend/scripts/android-local-pilot-guard.node-tests.mjs frontend/scripts/local-weather-pilot-config.node-tests.mjs frontend/scripts/android-pilot-prefetch.node-tests.mjs frontend/scripts/runtime-api-binding.node-tests.mjs
```

**21 superati, 0 falliti, 0 saltati.** Sono controlli locali dei guard, non prove
Doze o recupero CAMS sul telefono. Le verifiche precedenti dei sorgenti sono
registrate nel commit UI `c54cdb9` (81 test, lint e build) e nel rapporto
`CAMS_RECOVERY_SOURCE_FIXES_2026-09-10.md`; non sono conteggiate come rieseguite qui.

Gradle: **BUILD SUCCESSFUL**, 151 task (21 eseguiti, 130 up-to-date).
Gli indicatori NO-SOURCE/SKIPPED della build non sono test eseguiti; nessuna suite
strumentale Android è stata avviata. Avvisi preesistenti non corretti: import
dinamico AlmanacView inefficace; chunk oltre 500 kB; uso flatDir; deprecazioni
incompatibili con Gradle 9. Nessuna soglia o configurazione alterata.

## Avvio reale e beta intatta

```powershell
adb -s OWNER_DEVICE_SERIAL shell am start -W -n com.meteofriul.app.localpilot/com.meteofriul.app.MainActivity
```

Esito `Status: ok`, `LaunchState: COLD`, `TotalTime: 5694 ms`. È il tempo di avvio
dell'Activity, non del completamento dei dati. Processo e finestra in primo piano
verificati. Screenshot: Home renderizzata con meteo, allerta ufficiale ed eventi;
nessun risultato CAMS/UV o di recovery mattutina dedotto da questa sola schermata.

Beta `com.meteofriul.app` invariata prima/dopo: versione `1.0.1` / `300012`,
ultimo aggiornamento `2026-08-30 00:41:28`, stessi percorsi e SHA256 di base e
tre split. Base: `88b7068652a35cfb6c9190881fd06c9ccd7eeace5ef12767a55761eab0d526cb`.

## Cosa arriva sul telefono e cosa resta aperto

Questa APK contiene le modifiche frontend fino a `c54cdb9`: timeout CAMS finito,
recupero al gate esistente, protezione del bundle nuovo dalle risposte vecchie,
rubrica e rifiniture UI già committate, inclusa la card UV compatta.

**Nessun deploy cloud.** La correzione Python del worker `7da153e` non può essere
distribuita tramite un'APK e resta soltanto nei sorgenti. Nessuna acquisizione
ADS, modifica a scheduler/frequenze/Firebase/notifiche/backend/sito.
La soglia CAMS resta **30 ore**; la proposta di 35 ore non è applicata. Il dettaglio
storico del 400 UV resta mancante, come nel rapporto specifico.

Installazione e smoke test conclusi; **il problema sul Samsung non è ancora
dichiarato risolto**. Va osservato nell'uso reale, specialmente dopo inattività,
ritorno rete e disponibilità della nuova corsa, senza confondere l'intento delle
12:01:11 del 10 settembre con il cambio puntatore delle 12:10:02.461 e la verifica
conclusiva delle 12:10:37.202 CEST.
