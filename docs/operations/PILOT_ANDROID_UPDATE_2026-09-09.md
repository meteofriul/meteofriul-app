# Aggiornamento pilota e launcher approvato — 9 settembre 2026

## Rettifica del riferimento

L'installazione delle 18:27 descritta sotto usava una variante che l'utente
ha successivamente identificato come errata. Non è il marchio definitivo.
Il riferimento corretto è l'allegato `Immagine Codex 9 set 2026, 18_28_04.png`,
SHA-256 `F3276D62AAA20421CF5DA2FD0DBAA97CB57AD51E5867104A7DAA0D869FB3F989`:
tela originale al 68%, centratura intera, nessuno spostamento ottico.
Le evidenze dell'installazione precedente sono conservate come cronologia,
non come alternativa approvata. Vedere il riferimento unico in
`android/launcher-assets/README.md` e il controllo obbligatorio
`scripts/test-pilot-launcher-reference.ps1`.

## Perimetro

Aggiornamento conservativo della sola `com.meteofriul.app.localpilot` sul
Samsung A52 / Android 14. Nessuna modifica alla pipeline ICON/CAMS/UV, alle
frequenze, a Firebase o alla beta. I commit `c4354ac` e `5dfe8fa` sono conservati
senza riscritture; questo intervento launcher è separato.

L'utente ha approvato l'ultima anteprima dopo il confronto con l'icona reale:
blu intenso con alone luminoso, marchio ingrandito, nessun quadrato interno.
Le risorse finali usano la tela al 74% e uno spostamento ottico di −2 dp.
Il generatore è stato riallineato agli asset approvati: riproduzione temporanea
di tutte le cinque densità con SHA-256 identici, senza modificare i PNG approvati.
Master e cutout conservano i pixel originali; nessuna nuova generazione IA.

## Verifiche e build

- 21/21 test Node: guard Android, configurazione pilota, prefetch e binding.
- Pacchetto launcher: 11 asset verificati, inventario/hash, trasparenza e
  corrispondenza alle risorse runtime `localPilot`.
- Asset approvati beta: 41 originali e 2 supplementari integri; gate runtime
  Android/PWA e master passato. Nessun diff in `main/res`, header o web/PWA.
- Build protetta `build-android-local-weather-pilot.ps1 -WeatherCloud`, fuori
  sandbox, completata con successo. Nessun orologio di test o `adb reverse`.
- API ordinaria: `https://cfweb-bcee09e---meteofriul-api-bx24xqvcda-ew.a.run.app/api`.
- ICON/CAMS: `https://pilot-weather-335641913741.europe-west1.run.app`.
- APK verificata: `com.meteofriul.app.localpilot`, debug,
  `1.0.1-local-pilot`, versionCode `300012`.

## Installazione e riscontro sul telefono

`adb install -r` completato alle **18:27:50 CEST del 9 settembre 2026**, senza
disinstallazione o cancellazione di cache/preferenze. SHA-256 della build e
della `base.apk` installata, identici:

`d93e9c6c365ee739d612fbcde77be52680b1d9e596945f530c50d646055cd708`.

Copia locale conservata, non pubblicata:
`.dev-logs/local-weather-pilot/meteofriul-pilot-20260909-1827-launcher-approved.apk`.

La home Samsung mostra lo sfondo blu/alone e il marchio ingrandito, senza il
quadrato interno. Testo e sagoma risultano visibili. L'app si avvia correttamente
(Activity COLD, 2893 ms: non equivale al tempo completo di caricamento dati).
Lo screenshot successivo mostra Pordenone, dati meteo, allerta ufficiale e card
Home. Non sono dedotti da questo smoke test nuovi risultati su Doze o recovery cloud.

Beta `com.meteofriul.app` invariata prima/dopo: versione `1.0.1`, code `300012`,
ultimo aggiornamento `2026-08-30 00:41:28`; SHA-256 di base e tre split identici.
Base beta: `88b7068652a35cfb6c9190881fd06c9ccd7eeace5ef12767a55761eab0d526cb`.

Evidenze locali non pubblicate in `.dev-logs/local-weather-pilot/`:
`launcher-proposed-20260909.png`, `launcher-installed-20260909.png`,
`app-after-install-20260909.png`.

## Correzione effettiva e pulizia — 18:44 CEST

Il riferimento allegato dall'utente è ora conservato byte per byte e dichiarato
unico nuovo marchio nel README degli asset. Composizione riprodotta con
**0 differenze su 82.944 pixel**, compresa l'alpha della maschera indicativa
dell'immagine allegata. La maschera del launcher Android resta separata:
non è inserita nel foreground e non si ricrea una cornice interna.

Il nuovo controllo ha prima respinto la composizione errata (39.868 pixel
diversi), poi accettato quella esatta. La build pilota ora lo esegue in sola
lettura prima di compilare, insieme ai controlli inventario/runtime.

Pulizia strettamente launcher:

- Rimossi 45 PNG tracciati, 942.067 byte: 15 risorse `localPilot` inutilizzate,
  20 varianti launcher a colori del primo pacchetto pilota e 10 vecchi layer
  adattivi del pacchetto testuale. Inventari residui verificati: 23 e 33 asset.
- Rimossi l'XML `friulora` autoreferenziale e i tre generatori precedenti che
  potevano reintrodurre varianti obsolete. Tutto recuperabile da `bc64a18` in Git.
- Restano le risorse realmente usate: launcher legacy per Android 24/25,
  monochrome, splash, notifiche, header e web/PWA. Tutti gli asset beta/main intatti.
- La preview locale errata `launcher-proposed-20260909.png` e il relativo
  helper non sono più nel workspace: spostati, recuperabili, nella cartella
  temporanea `meteofriul-discarded-launcher-88e49ff46eab42738373dd813f55fe45`
  sotto il TEMP di Windows. Non costituiscono più riferimenti del marchio.

21/21 test Node e tutti i gate asset passati. Build protetta completata;
APK priva di risorse `friulora`, cinque foreground con hash identici al pacchetto
controllato contro il riferimento. Nessuna modifica a codice UI o pipeline.

Installazione conservativa riuscita alle **18:44:34 CEST** sul medesimo Samsung:
`com.meteofriul.app.localpilot`, versione `1.0.1-local-pilot` / `300012`.
Hash della build e della `base.apk` installata identici:

`e17ea2483f0cb7762f385c5fc70b873c8bf629ceed410c8a2d7df7b5a57054bf`.

Copia locale:
`.dev-logs/local-weather-pilot/meteofriul-pilot-20260909-1844-brand-reference.apk`.
Screenshot reale: `.dev-logs/local-weather-pilot/launcher-reference-installed-20260909.png`.
La home Samsung mostra la composizione corretta; avvio dell'app riuscito.
Beta ancora invariata, inclusi data di aggiornamento e hash di base e tre split.
I commit stabili `c4354ac` e `5dfe8fa` restano intatti.
