# Consolidamento del progetto — 27 ottobre 2026

## Perimetro e sorgenti

Il proprietario ha autorizzato il consolidamento del lavoro concluso in
`main` mediante pull request. Base remota verificata:
`4219581f17b35aa42bd346ff652058004d9cf5f0`; candidato locale iniziale:
`acb8a77d541dceae126ad10e5d48cd33b49409ee`.

Il ramo `codex/scopri-source-archive` comprende otto commit ancora assenti
dalla base remota, senza divergenze:

| Commit | Contenuto |
| --- | --- |
| `759b354d` | Associazione Pordenone Pensa al solo programma verificato |
| `616b1a7c` | Evidenze e precedente promozione Eventi sul main locale |
| `8e6d9c0b` | Colori di stato del radar in tema scuro |
| `4fcba4a1` | Cinque agenti, responsabilita' e regole di coordinamento |
| `c4ec900c` | Selezione esplicita della toolchain nel launcher pilot |
| `08af2032` | Inventario locale delle fonti Scopri/Ostermann recuperate |
| `eb2986df` | Mappa del codice condiviso, Android e possibile futuro iPhone |
| `acb8a77d` | Inventario delle ulteriori fonti documentali FVG |

I due commit Eventi erano gia' in `main` locale. Il loro contenuto e'
conservato; questa operazione completa il percorso verso GitHub.

## Revisioni ed evidenze funzionali

- `meteo`: review dei due selettori CSS superata. L'effetto riguarda i testi
  di stato del radar disponibile, nel workspace inline in tema scuro.
- Il proprietario ha dichiarato conclusa positivamente la verifica manuale
  del radar in questa conversazione. Non sono stati forniti nuovi screenshot
  o dettagli sufficienti per attribuire dispositivo, stati dei dati o una
  qualifica Android a questa dichiarazione.
- `eventi`: review superata e hash dei quattro file sorgente/test/fixture
  conformi alla ricevuta del
  [collaudo del 26 ottobre](EVENTS_PNPENSA_PROGRAMME_MEMBERSHIP_20261026.md).
  Quel verbale attesta Brave/Galaxy A52, italiano/chiaro e friulano/scuro,
  per i tre incontri visibili nei 15 giorni; gli altri due sono coperti dai
  test. Le prove storiche non vengono presentate come nuove osservazioni.
- `build_verifica` raccoglie i controlli di questa integrazione; il
  coordinatore e' l'unico autore dell'aggiornamento documentale.

## Controlli del consolidamento

Toolchain effettiva: Node `22.17.1`, npm `10.9.2`, PowerShell Windows;
dipendenze esistenti, nessuna installazione. PATH modificato soltanto nel
processo dei controlli.

| Controllo locale | Risultato |
| --- | --- |
| Contratti launcher, inclusa toolchain esplicita | PASS, 60 asserzioni |
| Guard local-pilot | PASS, 11 test |
| Test mirati radar ed Eventi | PASS, 202 test in 6 file |
| Build Web, service worker e relativo assert | PASS, output nuovo nel temporaneo del sistema |
| Definizioni TOML dei cinque agenti | PASS |
| Workspace canonico e diff | PASS prima del commit |
| `npm run lint` completo locale | BLOCCATO: `EPERM` su `frontend/.pytest_cache` |
| ESLint su tutti i 941 file JS/JSX/MJS/CJS versionati | PASS, quattro batch, nessun warning |

Il lint completo e' stato ripetuto fuori sandbox con lo stesso esito. La
cache e' una directory fisica ignorata da Git, con accesso negato anche
alle ACL; il tentativo di spostarla conservandola nel temporaneo e' stato
negato. Non sono stati cambiati permessi, esclusioni ESLint o soglie.
Il controllo complementare sui sorgenti versionati non sostituisce il
PASS del comando completo in CI, richiesto prima della promozione.
Sono stati passati i percorsi Git direttamente a ESLint, con la stessa
configurazione; non risultano nuovi sorgenti frontend non versionati.

Comandi principali, dalla radice per il launcher e da `frontend/` per gli
altri controlli. `$pilotNode` indica la distribuzione portabile prescritta;
`$buildDirectory` una directory nuova sotto il temporaneo del sistema:

```powershell
.\scripts\start-local-weather-pilot.contract.tests.ps1 -NodeDirectory $pilotNode
npm run test:local-pilot-guard
node node_modules/vitest/vitest.mjs run --configLoader native src/features/live/TerritoryRadarOverlay.test.jsx src/features/live/liveCss.test.js src/features/live/TerritoryImmersiveMap.integration.test.jsx src/services/pilotProgrammeProjection.test.js src/services/eventsApi.test.js src/features/events/eventsViewModel.test.js
npm run lint
node node_modules/vite/bin/vite.js build --configLoader native --outDir $buildDirectory --emptyOutDir
node node_modules/vite/bin/vite.js build --config vite.sw.config.js --configLoader native --outDir $buildDirectory
node scripts/assert-web-push-service-worker.mjs $buildDirectory
```

La build segnala dimensioni dei chunk e import dinamici che non separano
moduli gia' importati staticamente; warning conservati, non bloccanti per
questo intervento. L'output serve al controllo e non e' un candidato Web
autorizzato alla pubblicazione.

Non sono cambiate sorgenti backend: non occorre ripetere i test Python
locali per questo diff; la CI mantiene la propria copertura prevista.

## Conservazione e confini

Gli agenti `home`, `meteo`, `eventi`, `scopri` e `build_verifica` e le regole
di assegnazione dei file sono versionati. I confini sono istruzioni
operative nel checkout condiviso, non un isolamento fisico delle cartelle.
Le protezioni Git e i controlli di pubblicazione restano invariati.

L'[archivio Scopri](../archive/scopri/README.md) conserva localmente 2756
file, 249711363 byte, verificati contro i manifest. Git contiene indici e
checksum; originali e ricevute con percorsi macchina restano ignorati.
Un clone Git non sostituisce il backup della cartella completa.

La distribuzione Node dedicata resta fuori dal repository e viene scelta
con `-NodeDirectory`; installazione globale e PATH permanente non cambiano.
La mappa iPhone e' documentale: Android e Web restano le priorita'.

Il consolidamento riguarda i sorgenti. Non genera o carica APK/AAB, non
consuma versioni, non aggiorna il ramo release, non pubblica la Web e non
modifica backend, job, dati remoti o sponsor. La qualificazione dell'AAB
300038 resta invariata. Safari/iPhone e le verifiche Android non attestate
restano aperte nei rispettivi verbali.

## Promozione

Preparazione locale in corso. Push del ramo, PR, CI della PR e successiva
CI di `main` devono essere verificati; nessun push diretto su `main`.
