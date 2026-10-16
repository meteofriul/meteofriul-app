# Branding pilota r4 — profilo scuro

Questa variante aggiorna come un'unica operazione il launcher adattivo, lo
splash nativo e il marchio Home/Opzioni della build
`com.meteofriul.app.localpilot`. I due file forniti dall'utente il 18 settembre
2026 sono conservati byte per byte:

- `reference/logo1-transparent-20260918.png`: foreground RGBA 1254 × 1254,
  SHA-256 `441CA1BA9390FE0BEAFDC84A9395E6DFFE5012C04B5130E0DDE9448A1382E959`;
- `reference/logo2-composite-20260918.png`: riferimento composito RGB
  1254 × 1254, SHA-256
  `DD8EB0A97FF8EC28CED3B579F9EF84010B45D3BDE329A344828F5ED3AE6AE270`.

`logo1` fornisce la sagoma trasparente del foreground. La parte scura viene
portata deterministicamente alla palette più profonda misurata in `logo2`,
mentre il bianco resta intatto. `logo2` è inoltre la sorgente cromatica del
nuovo background pieno. Non viene copiato come quadrato opaco perché incorpora
già marchio, angoli arrotondati e canvas nero: la maschera esterna deve restare
responsabilità di Android. Il layer monocromatico Android 13+ conserva l'alpha
dei soli pixel chiari del simbolo.

## Geometria

La tela originale viene ridotta in un box da circa 69 dp sul canvas adattivo
da 108 dp, con un lieve spostamento ottico verso il basso. Il simbolo bianco
rimane dentro la safe-circle Android da 66 dp; la sagoma del Friuli è un
elemento decorativo e può estendersi nella zona dinamica prevista dalle icone
adattive. Lo stesso rapporto è applicato alle cinque densità:

| densità | canvas | box | offset x/y |
|---|---:|---:|---:|
| mdpi | 108 | 69 | 19 / 20 |
| hdpi | 162 | 104 | 29 / 30 |
| xhdpi | 216 | 138 | 39 / 40 |
| xxhdpi | 324 | 207 | 58 / 60 |
| xxxhdpi | 432 | 276 | 78 / 80 |

Il test ricostruisce ogni raster, confronta i pixel e verifica la safe-circle,
non soltanto il rettangolo di contenimento.

## Superfici statiche

Il composito `logo2` viene anche ripulito soltanto dal matte nero collegato ai
bordi, senza ridisegnare il marchio. Da questo master statico derivano sempre:

- marchio Home/Opzioni 192 × 192 nel percorso versionato `pilot-r4`;
- splash 512 × 512 con marchio 338 × 338 centrato a `(87,87)`.

Il percorso Web versionato evita che la WebView riusi dalla cache un marchio
precedente. Il test ricostruisce entrambi gli output pixel per pixel.

## Perimetro preservato

Restano byte per byte uguali alla r3:

- XML `anydpi`;
- launcher legacy API 24/25;
- PWA, favicon, Play e risorse della beta;
- icone monocromatiche delle notifiche.

Il background adattivo cambia intenzionalmente: usa un gradiente pieno campionato
da `logo2`, senza angoli neri né una seconda squircle incorporata. Il pacchetto
contiene 16 output inventariati: tre master, background, splash, marchio WebView
e dieci raster foreground/monochrome. `inventario.csv` e gli hash nello script
bloccano ogni variazione non intenzionale.

## Riproduzione

```powershell
.\scripts\package-pilot-launcher-layers.ps1
.\scripts\package-pilot-launcher-layers.ps1 -CheckOnly
.\scripts\test-pilot-launcher-reference.ps1
.\scripts\generate-android-launcher-assets.ps1 -CheckOnly
```

La build protetta localPilot esegue automaticamente il controllo read-only.
La resa finale va verificata sul launcher, nello splash e nella Home Samsung
dopo ogni nuova installazione.
