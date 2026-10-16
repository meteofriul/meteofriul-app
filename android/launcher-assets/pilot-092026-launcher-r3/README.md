# Launcher adattivo pilota r3 — riferimento cloud e campanile

Questa variante sostituisce il launcher adattivo colorato, il layer
monocromatico Android 13+, lo splash nativo e il piccolo marchio mostrato
nell'header e nelle impostazioni di `com.meteofriul.app.localpilot`. Il file
fornito dall'utente è conservato byte per byte in
`reference/approved-reference-20260911.png`: 1254 × 1254 pixel RGB, SHA-256
`83AA2C3389B3DF4E297221B3D9292ECE38EBE9B57284440232E37A619D99B4D6`.

## Derivazione deterministica

- Il crop centrale 1014 × 1014 con origine `(120,120)` serve soltanto come
  confine e seme del flood fill. I pixel conservati vengono rimessi alle loro
  coordinate originali su una tela trasparente 1254 × 1254; il crop non viene
  ingrandito.
- Il flood fill elimina soltanto lo sfondo blu/ciano collegato al bordo del
  crop, con il predicato documentato nello script. Conserva esattamente i pixel
  originali della sagoma del Friuli, della nuvola e del campanile.
- La tela originale viene collocata al 68% nei foreground adattivi 108, 162,
  216, 324 e 432 px, con centratura intera. Lo sfondo radiale a piena superficie
  della variante r2 resta invariato; Android applica la sola maschera esterna.
- I layer `monochrome` usano soltanto i pixel del soggetto per cui tutti i
  canali RGB sono almeno 200. Ne risultano la nuvola/campanile e il piccolo
  segno interno, senza testo e senza il bianco esterno del riferimento.
- Per le superfici statiche, un secondo flood fill parte dal bordo bianco del
  riferimento completo. Rimuove soltanto il canvas esterno connesso, conserva
  il vero sfondo blu/ciano con gli angoli arrotondati e mantiene l'intera tela
  originale 1254 x 1254 in `source/static-original-tile.png`, senza ritagli o
  zoom. Non viene creato alcun nuovo gradiente e non viene riutilizzato il solo
  foreground adattivo.
- Il marchio WebView 192 × 192 deriva con un unico ridimensionamento dal master
  statico trasparente. Home e Opzioni mostrano quindi la composizione originale
  intera, senza una seconda safe-zone e senza una mattonella quadrata opaca.
- Lo splash conserva la tela trasparente 512 × 512 prevista dalle regole
  ufficiali: il master statico viene ridotto direttamente a 338 × 338 e
  centrato a `(87,87)`, senza passare dal raster WebView.

`inventario.csv` registra i tre master tecnici, cinque XML, dieci raster
launcher, lo splash e il marchio WebView. Lo script vincola anche gli hash
degli output, la geometria dei componenti, la conservazione dello sfondo
originale e le copie runtime.

## Perimetro preservato

Restano byte per byte invariati i dieci raster launcher legacy API 24/25
(`ic_launcher.png` e `ic_launcher_round.png`) e le cinque icone di notifica
della pilota. `frontend/android/app/src/main/res`, beta, favicon/PWA, gli altri
asset web, Play e servizi cloud non vengono sincronizzati da questo pacchetto.
Il solo output WebView viene copiato nel percorso dedicato
`frontend/public/brand/pilot-r3/` e viene selezionato a runtime esclusivamente
dalla variante `localPilot`.

## Riproduzione e controlli

Dalla radice del repository, in PowerShell:

```powershell
.\scripts\package-pilot-launcher-layers.ps1
.\scripts\package-pilot-launcher-layers.ps1 -CheckOnly
.\scripts\test-pilot-launcher-reference.ps1
.\scripts\generate-android-launcher-assets.ps1 -CheckOnly
```

Il primo comando è l'unico autorizzato a rigenerare e sincronizzare i layer r3.
Gli altri comandi sono in sola lettura. La resa finale deve comunque essere
verificata sul launcher reale del telefono.
