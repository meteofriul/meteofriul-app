# Icona piccola notifiche Android r2

Pacchetto approvato il 26 settembre 2026 per sostituire le precedenti icone
troppo piccole nel badge circolare delle notifiche Android.

Il simbolo monocromatico `nuvola + torre` deriva dal master bianco del launcher
pilota r4, senza modificare launcher, splash, PWA o scheda Google Play. La sua
area visibile passa, alla densita `xxxhdpi`, a `88 x 52` pixel su un canvas
Android standard di `96 x 96` pixel.

Le cinque densita sono inventariate con dimensione e SHA-256 in
`inventario.csv`. Lo script `scripts/package-android-notification-icon.ps1`
verifica geometria, monocromia, inventario e copie runtime di build pilota e
ufficiale; senza `-CheckOnly` riallinea soltanto queste cinque risorse in
entrambi i source set.

Il nome Android rimane `@drawable/ic_stat_meteofriul`, quindi Allerte e Avvisi
continuano a usare lo stesso small icon e mantengono canali distinti.
