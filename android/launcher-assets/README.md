# Meteo Eventi Friûl — riferimento del marchio e asset launcher

## Branding pilota: profilo scuro approvato il 18 settembre 2026

I riferimenti `logo1.png` e `logo2.png` forniti dall'utente definiscono la r4
del launcher, dello splash e del marchio interno della pilota. Gli originali sono conservati senza
modifiche in `pilot-092026-launcher-r4/reference/`; hash, geometria e perimetro
sono documentati nel README del pacchetto.

Per ogni cambio del marchio della pilota usare soltanto
`scripts/package-pilot-launcher-layers.ps1`.
I master sono derivati deterministicamente dal riferimento trasparente, con
palette e background ancorati al composito scuro `logo2`. Il test
`scripts/test-pilot-launcher-reference.ps1` vincola sorgenti, pixel, output,
copie runtime e safe-circle da 66 dp del simbolo bianco; anche la build pilota
lo esegue prima di compilare. La maschera esterna continua a essere applicata
da Android.

Le varianti r2/r3 e le prove precedenti restano cronologia. La r4 cambia i layer
adattivi colorato, monocromatico, background, splash e marchio WebView interno:
XML `anydpi`, legacy API 24/25, notifiche, favicon/PWA, Play, beta e risorse
Android `main` restano invariati.

### Contratto obbligatorio per le icone future

Una nuova icona della pilota non è mai una modifica del solo launcher. Lo stesso
passaggio deve aggiornare launcher adattivo/monocromatico/background, splash e
marchio Home/Opzioni con percorso versionato; deve rigenerare inventario e hash,
superare i test pixel/geometria e la build protetta, poi essere verificato sulle
tre superfici del telefono senza disinstallare o cancellare dati. Il guard della
build fallisce se una delle copie runtime non corrisponde al pacchetto canonico.

## Asset della beta approvati 082026 — da preservare

Questa cartella contiene l'unica sorgente tecnica autorizzata per icone,
launcher, splash e icone di notifica della beta Meteo Friûl ancora in test.
Questi asset restano separati dal nuovo riferimento della pilota.

## Sorgenti canoniche

- `source/launcher-082026-master.png`: disegno originale coniato dall'autore.
  SHA-256: `7D9D72D20D2661F614EC024BB0C3A1DCFE6E1A6AC8D38ABA00069FE84D768E7F`.
- `approved-082026/`: pacchetto immutabile di 41 asset già approvati.
- `approved-082026/inventario-approvati.csv`: dimensioni e SHA-256 di ciascun
  asset. SHA-256 dell'inventario:
  `7A8101C2B5C6862611B98A69197805BC4DCC071294A94A03839645E6750A3888`.
- `approved-web-shortcut-082026-r2/`: supplemento immutabile con le sole due
  icone PWA `purpose: any` a composizione sicura (78,1%), introdotto dopo la
  verifica reale della scorciatoia Brave. Le risorse Android e `maskable`
  restano nel pacchetto base e non cambiano.

Il pacchetto conserva separatamente:

- `android/res/`: 31 raster Android (launcher, layer adattivi, splash al 66%
  e icona piccola bianca per le notifiche);
- `web-pwa/public/`: nove asset PWA, favicon e Apple Touch versionati;
- `google-play/`: icona 512 × 512 destinata esclusivamente alla scheda Play.

Le scelte grafiche approvate sono: crop 1112, adaptive/maskable 54%, splash
66% e small notification icon monocromatica con margine 2 dp. Non rigenerare
questi file partendo da percentuali o trasformazioni ImageMagick: il risultato
autorizzato è definito dagli hash dell'inventario.

## Verifica dell’archivio storico

Da PowerShell, nella radice del repository:

```powershell
.\scripts\generate-android-launcher-assets.ps1
```

Lo script non genera immagini, non esegue build e non copia più asset nel
runtime. Verifica soltanto master, inventario, tutti i 41 asset e il supplemento
r2, che rimangono evidenza storica. In particolare, le vecchie icone Web con la
scritta `meteo friul` non possono essere ripubblicate accidentalmente.

Per una verifica senza scritture:

```powershell
.\scripts\generate-android-launcher-assets.ps1 -CheckOnly
```

L'icona Google Play non viene mai copiata nel runtime e non entra nell'APK o
nell'AAB. Il caricamento in Play Console resta un'operazione manuale separata.

Il launcher Android corrente è gestito da
`scripts/package-pilot-launcher-layers.ps1`. Le icone della scorciatoia PWA e
lo splash generato dal browser sono gestiti separatamente da
`scripts/package-web-pwa-icons.ps1`, usando lo splash launcher-r4 approvato e il
fondo `#061A2E`.

## Icona notifiche Android r3

Il pacchetto `notification-092026-r3/` sostituisce esclusivamente la small icon
Android con il simbolo monocromatico `nuvola + torre`, più alto, pieno e leggibile
nel badge circolare del sistema. `scripts/package-android-notification-icon.ps1`
verifica sorgente e inventario e mantiene identiche le copie runtime della build
pilota e ufficiale. Launcher, splash, PWA e scheda Play non vengono modificati.

## Materiale precedente

I nomi `icon_launcher_3.0-*`, il vecchio mirror `res/`, il vecchio
`play-store/` e i generatori percentuali non sono sorgenti valide. La loro
storia resta recuperabile da Git, ma non devono essere ripristinati nel ramo di
release.
