# Icona piccola notifiche Android r3

Pacchetto approvato il 27 settembre 2026 per rendere il simbolo Meteo Friûl
più leggibile nel badge circolare delle notifiche Android.

Il simbolo monocromatico `nuvola + torre` deriva dal master bianco del launcher
pilota r4, ma viene riequilibrato verticalmente e ispessito per la resa a 24 dp.
Alla densità `mdpi` l'area visibile è `22 x 18` pixel sul canvas Android standard
di `24 x 24`, contro il precedente profilo basso `22 x 13`. Il dettaglio resta
monocromatico bianco con trasparenza, come richiesto dalle small icon Android.

Le cinque densità sono inventariate con dimensione e SHA-256 in
`inventario.csv`. Lo script `scripts/package-android-notification-icon.ps1`
verifica sorgente, geometria, monocromia, inventario e copie runtime delle build
pilota e ufficiale; senza `-CheckOnly` riallinea soltanto queste cinque risorse
nei due source set.

Il nome Android rimane `@drawable/ic_stat_meteofriul`, quindi Allerte e Avvisi
continuano a usare la stessa small icon e mantengono canali distinti. Launcher,
splash, PWA, favicon e scheda Google Play non vengono modificati.
