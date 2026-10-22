# Correzione sovrapposizione mappa bollettino — 22 ottobre 2026

## Perimetro

Ramo `codex/bulletin-map-label-spacing`, avviato da main
`3da1db2d4d2f1de4bd14745ef7fd078ec8d399dd`.
Unica modifica funzionale: spostamento orizzontale dell'etichetta 1000 m
(dal 28% al 15% della mappa), mantenendo la quota verticale al 28%.
Nessuna modifica a dati, simboli meteo, traduzioni o navigazione.

## Problema e riscontro

Le gocce e il fulmine del simbolo della Carnia occupavano la stessa area
dell'etichetta 1000 m. Riprodotto nel browser con pioggia e testo
`1000m -12°C`; dopo lo spostamento etichetta e simbolo sono separati.
Controllata anche la resa nella pagina completa del bollettino.

## Verifica locale

- Anteprima avviata con `scripts/start-local-weather-pilot.ps1`, porta 5174.
- ICON/CAMS dell'anteprima: snapshot locale del 4 settembre 2026;
  il bollettino della pagina completa legge i documenti OSMER pubblicati.
- Componente reale e CSS reali, con dati sintetici esplicitamente indicati
  nella pagina di verifica per esercitare i simboli anche quando non presenti
  nel bollettino corrente.
- 24 combinazioni: larghezze 320, 390 e 480 px; temi chiaro/scuro;
  italiano/friulano; pioggia, temporale, neve, nebbia, sole e variabile;
  temperature 9°C e -12°C. Le combinazioni sono un campione, non il prodotto
  cartesiano di tutti i parametri.
- In tutti i casi: nessuna intersezione del badge con le forme dei simboli,
  testo contenuto nel badge, badge interno alla mappa, nessun overflow
  orizzontale. Ispezione visiva di pioggia chiara e temporale scuro.
- `BulletinView.test.jsx` e `bulletinViewModel.test.js`: 36 test superati,
  con Vitest `--configLoader native`.
- ESLint sul componente e `git diff --check`: superati.

## Limiti

Telefono non collegato: nessuna verifica Android su dispositivo.
Correzione conservata sul ramo dedicato, senza promozione su main.
Nessuna AAB, installazione, emulatore, push, deploy o invio.
I file della verifica sintetica restano locali e ignorati da Git.
