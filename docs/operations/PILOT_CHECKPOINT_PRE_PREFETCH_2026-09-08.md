# Pilota: checkpoint verificato prima del prefetch Android

Data: 8 settembre 2026. Riferimento locale previsto:
`pilota-stabile-pre-prefetch-20260908`.

## Linea di sviluppo e perimetro

Il checkpoint conserva lo stato corrente nello stesso worktree e nella stessa
sequenza di commit. Il checkout era gia detached su `e5f0ace`: nessun nuovo
branch, copia del progetto, cambio di checkout o riscrittura della storia.
Il tag locale identifica il punto di ripristino senza creare una linea parallela.

Sono inclusi gli interventi gia presenti su navigazione Indietro della pilota,
swipe Meteo, localita rapide, resilienza UV, finestra ICON reale 12–48 ore e
diagnostica cloud. Le quattro aspettative test obsolete (Timp, Territorio,
scorrimento orizzontale della striscia oraria) sono riallineate al comportamento
gia approvato; nessuna modifica UI aggiunta durante questa verifica.

La diagnostica cloud e salvata come codice preparato, NON come deploy eseguito.
Recovery ICON/CAMS e monitoraggio restano distinti e non sono attestati completi.
Il prefetch Android non e ancora incluso in questo checkpoint.

## Verifiche del checkpoint

- Build protetta `scripts/build-android-local-weather-pilot.ps1 -WeatherCloud`
  completata: Web + `assembleLocalPilot`, package `com.meteofriul.app.localpilot`.
- Endpoint ICON/CAMS: `https://pilot-weather-335641913741.europe-west1.run.app`.
- API ufficiale: `https://cfweb-bcee09e---meteofriul-api-bx24xqvcda-ew.a.run.app/api`.
- Nessun orologio simulato nel bundle.
- APK SHA-256:
  `329585997b850db6eade1bb904ffcf97f12bfb1cbd3568bf34974cc770e867a4`.
  Il percorso generato e riutilizzato dalle build successive: questo hash
  identifica esclusivamente il controllo pre-prefetch, non ogni APK futuro.
- 380 test frontend mirati passati; 5 test live saltati come gia previsto.
- 13 test Node di configurazione pilota, identita Android e binding API passati.
- 62 test Python diagnostica/store/planner/worker/entrypoint passati:
  `python -m unittest test_operational_diagnostics test_gcs_object_store
  test_cams_request_plan test_cloud_worker test_job_entrypoints`.
- `git diff --check` pulito.

## Limiti dichiarati: non e una certificazione di release

La suite frontend estesa ha prodotto 3255 successi, 3 fallimenti e 11 skip.
Resta il test preesistente `EventsView > shows available descriptions in the
list without fetching a detail`: richiede un excerpt che il componente attuale
non renderizza. Il test NON e stato cancellato, saltato o indebolito; introdurre
quel contenuto cambierebbe la UI e richiede una decisione separata.

Gli altri due fallimenti sono timeout delle simulazioni annuali Scopri
(`discoverInstitutionalArchive`, `discoverEditorialCalendar`) al limite di
5 secondi sotto carico. Non e stato aumentato il timeout per nasconderli.
Le due suite, rieseguite isolate insieme alle prove anteprima/cache Eventi,
passano: 26/26 test.

Il lint dei file modificati rileva ancora due errori preesistenti in
`AppRoutes.jsx` (variabile `setRadius` inutilizzata e setState in effect) e
warning Fast Refresh. Le righe responsabili non appartengono alle modifiche
del checkpoint; non si dichiara il lint globale pulito.

Il gate Python esteso con publisher e UV e distinto dai 62 test mirati;
l'ambiente Windows non dispone di ecCodes nativo per due prove UV.
Per il futuro monitoraggio cloud, usare l'esito autorevole `publication_result`:
una fase puo loggare ERROR per `StaleContractRun` prima che il job lo classifichi
correttamente come no-op per presenza di una corsa piu recente.

Nessuna installazione sul telefono, deploy cloud/Play/web/sito, modifica Firebase,
beta o scheduler. Il collaudo fisico del nuovo prefetch andra eseguito dopo
l'implementazione e la sua compilazione, senza confonderlo con questa verifica.

## Regola per i prossimi interventi

Ogni intervento importante successivo ha un commit distinto. Il nuovo prefetch
deve mantenere un solo validatore ICON/CAMS, usare gli spazi Android gia riservati
a `localPilot` e non duplicare il progetto o modificare l'interfaccia.
