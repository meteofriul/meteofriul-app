# Launcher adattivo pilota — livelli separati, 8 settembre 2026

Correzione della doppia cornice autorizzata dall'utente, con successiva
approvazione esplicita dell'estrazione tecnica dal master originale senza IA.

## Provenienza e invarianti

- Sorgente: `frontend/public/brand/meteo-eventi-friul-text-master.png`, SHA-256
  `97FFC85EE43F0FC51893BBB82C6AA947852A7AD5B4E29DCEE397F7210ED1BC5E`.
- Estrazione deterministica dello sfondo blu collegato al bordo della tela;
  i pixel conservati mantengono esattamente gli RGB originali. La soglia e il
  flood fill sono documentati in `scripts/package-pilot-launcher-layers.ps1`.
  I riflessi interni della sagoma, tipografia, testo e colori non sono ridisegnati.
- Due tentativi imagegen sono stati scartati: producevano RGB con scacchiera,
  non vera trasparenza. Nessuno dei loro pixel entra nel progetto o nell'APK.
- Foreground RGBA in cinque densità 108/162/216/324/432 px, tela al 68%:
  centratura intera della tela originale, senza centratura del bounding box né
  traslazioni ottiche. È la composizione dell'immagine allegata dall'utente
  `Immagine Codex 9 set 2026, 18_28_04.png`, conservata byte per byte in
  `reference/approved-preview-20260909.png`, SHA-256
  `F3276D62AAA20421CF5DA2FD0DBAA97CB57AD51E5867104A7DAA0D869FB3F989`.
  La variante al 74% installata alle 18:27 non era quella voluta: è sostituita
  da questo riferimento esplicito, senza modificare master o disegno.
  Margini trasparenti verificati. La maschera esterna resta quella del launcher.
  Nessun inset XML o quadrato opaco nel foreground.
- Sfondo XML opaco a piena superficie, blu intenso con alone luminoso centrale,
  rivisto il 9 settembre dopo il confronto con la home Samsung. Il gradiente
  usa coordinate del viewport, non un raggio fisso in dp: rimane proporzionato
  anche alle piccole dimensioni del launcher. Non è una copia pixel-per-pixel
  dello sfondo raster; riprende i suoi colori senza ripristinare il quadrato interno. La sola
  maschera esterna è applicata dal launcher Android, non disegnata due volte.
- Override adattivi standard/round per API 26 e 33 esclusivamente localPilot.
  Layer monochrome preesistente invariato; anche legacy raster, splash, header,
  notifica, web/PWA e Play restano invariati.

Gli 11 file del pacchetto sono registrati in `inventario.csv`. Gli originali
`approved-082026`, i supplementi e `pilot-092026-text` non sono sovrascritti.

## Riproduzione e controlli

PowerShell 7 con System.Drawing disponibile, dalla radice del repository:

```powershell
.\scripts\package-pilot-launcher-layers.ps1
.\scripts\package-pilot-launcher-layers.ps1 -CheckOnly
.\scripts\test-pilot-launcher-reference.ps1
.\scripts\generate-android-launcher-assets.ps1 -CheckOnly
```

Il primo comando rigenera questa sola variante e ne sincronizza i 10 file
runtime. Prima delle copie controlla tutti gli hash, allowlist esatta,
duplicati, percorsi contenuti nelle radici autorizzate e margini del foreground.
Il confronto della composizione con il riferimento allegato è obbligatorio:
nessuna differenza sui 82.944 pixel dell'anteprima. La maschera dell'anteprima
è indicativa e non viene incorporata nel foreground Android.
Il secondo non scrive; il terzo attesta che gli asset approvati beta sono intatti.

Riferimento tecnico: [Android adaptive icons](https://developer.android.com/develop/ui/compose/system/icon_design_adaptive).
La resa finale va verificata sulla home del telefono, non solo nei file PNG.
