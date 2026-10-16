# Pilota Android aggiornata e launcher senza doppia cornice

## Perimetro e provenienza

Frontend con Home/Scopri fino al commit `21eab7e`, più la variante launcher
`android/launcher-assets/pilot-092026-launcher-r2` di questo intervento.
La nuova variante conserva i pixel del master originale; l'estrazione tecnica
è stata esplicitamente autorizzata. I due risultati imagegen privi di vera
trasparenza sono stati scartati e non sono incorporati né inventariati.

- Solo foreground RGBA in cinque densità e cinque XML di localPilot.
- Sfondo continuo separato; nessuna cornice o scala aggiuntiva negli XML.
- Originali inventariati, risorse main/beta, splash, monochrome, notifiche,
  header, PWA e Play invariati. Nessun deploy o modifica cloud/Firebase.

## Verifiche prima dell'installazione

- 21/21 test Node: guard Android, configurazione pilota, prefetch e binding.
- Pacchetto r2: 11 asset, hash, allowlist, dimensioni, margini alpha e
  corrispondenza runtime; `CheckOnly` senza scritture.
- Pacchetto approvato 082026: 41 asset e supplemento web r2 integri; gate
  runtime beta passato. Nessun diff nei pacchetti approvati o in main/res.
- Build protetta `build-android-local-weather-pilot.ps1 -WeatherCloud`,
  eseguita fuori sandbox, senza `WeatherTestNow` e senza adb reverse.
- API ordinaria: `https://cfweb-bcee09e---meteofriul-api-bx24xqvcda-ew.a.run.app/api`.
- Dati ICON/CAMS: `https://pilot-weather-335641913741.europe-west1.run.app`.
- APK verificata: package `com.meteofriul.app.localpilot`, debug,
  `1.0.1-local-pilot` / code `300012`; cinque foreground impacchettati con
  alpha 0 negli angoli e 255 al centro. Nessuna falsa scacchiera opaca.

## Installazione e readback reale

Aggiornamento conservativo `adb install -r` sul Samsung A52 / Android 14,
completato alle **21:58:12 CEST dell'8 settembre 2026**. Nessuna disinstallazione,
cancellazione cache/preferenze, modifica dell'orologio o della rete del telefono.

SHA-256 APK locale e APK installata, identici:
`9ddfc56eeb6ce29ad8a9f986591037450a1261d8f8439e5a886f7b001092face`.

Copia locale conservata in
`.dev-logs/local-weather-pilot/meteofriul-pilot-20260908-2158-launcher-r2.apk`.

- Home Samsung prima/dopo: doppio quadrato eliminato, marchio leggibile,
  solo sagoma esterna Samsung. Il launcher ha aggiornato la scorciatoia
  esistente senza cancellarne dati o configurazione.
- Avvio Activity OK (WARM, 2099 ms: non è una misura del caricamento dati).
  Screenshot successivo conferma Home completa con dati, card Memoria e
  I perché nuove. Nessun crash Android del processo rilevato nel campione.
- Tap reale sulla domanda apre la risposta Palmanova in Scopri, con apertura
  “Per difendersi.”, linea oro e fonte compatta. Nessun nuovo collaudo di Doze
  o promessa sui tempi del prefetch viene dedotto da questa installazione.
- Beta `com.meteofriul.app` invariata: versione `1.0.1` / `300012`, ultimo
  aggiornamento `2026-08-30 00:41:28`. SHA di base.apk e dei tre split identici
  prima/dopo; base SHA-256
  `88b7068652a35cfb6c9190881fd06c9ccd7eeace5ef12767a55761eab0d526cb`.

Screenshot locali, non pubblicati, in `.dev-logs/local-weather-pilot/`:
`launcher-before-20260908.png`, `launcher-after-20260908.png`,
`home-loaded-20260908.png`, `home-cards-20260908.png`,
`discover-ready-20260908.png`.
