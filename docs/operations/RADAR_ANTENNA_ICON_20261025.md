# Icona antenna radar sulla mappa — 25 ottobre 2026

## Identità e perimetro

Ramo `codex/radar-antenna-icon`, da main
`35843b19cee6ba66b4f47331d08713bc9a9c815e`.
Modifica approvata dal proprietario: antenna con onde (`SatelliteDish` della
libreria Lucide già presente) al posto dei cerchi radar nel pulsante di Tempo reale.
Cambiano soltanto import e componente SVG in `TerritoryImmersiveMap.jsx`.
Restano invariati dimensioni, colori, logica, stato attivo/disattivo, etichette
accessibili, sorgenti meteo e controlli del bollettino. Nessuna nuova dipendenza.

La modifica è salvata sul ramo dedicato e non è promossa in main o nel ramo
release. Non compare negli artefatti Android/Web già generati né nella Web pubblica.
Sponsor disattivati: nessuna modifica a configurazione, pannello o dati sponsor.

## Verifica browser locale

Anteprima avviata con `scripts/start-local-weather-pilot.ps1 -WeatherCloud`,
porta 5174. Browser integrato Codex, lingua italiana, viewport CSS 589 × 902.
Configurazione CARTO locale già esistente riutilizzata solo nell'ambiente del
processo; nessuna chiave salvata nel verbale o nel codice.

| Caso | Riscontro |
| --- | --- |
| Chiaro, radar spento | Antenna blu sul pulsante bianco, senza tagli. |
| Chiaro, radar attivo | Antenna bianca sul gradiente blu; pannello radar visibile. |
| Scuro, radar spento | Antenna chiara sul pulsante scuro, senza tagli. |
| Scuro, radar attivo | Antenna bianca sul gradiente azzurro; pannello radar visibile. |

Misurati 44 × 44 px per il pulsante e 21 × 21 px per l'icona in tutti i casi.
L'SVG eredita il colore dal pulsante (`currentColor`). Verificati il cambio
`aria-pressed` e l'apertura del pannello; l'anteprima è stata riportata al tema
chiaro con radar attivo, come all'inizio. Nessuna modifica CSS risultata necessaria
per questa sostituzione. Le osservazioni sono visive, non una certificazione
completa del contrasto o dell'accessibilità dell'intera mappa.

## Controlli automatici

Due regressioni esistenti superate: accensione/spegnimento radar indipendenti
senza rimuovere i marker Community; radar indisponibile disabilitato senza
alterare gli altri marker. Esecuzione mirata: **2 PASS, 41 esclusi dal filtro**,
non un'esecuzione dell'intera suite.

```powershell
node node_modules/vitest/vitest.mjs --configLoader native run src/features/live/TerritoryImmersiveMap.integration.test.jsx -t 'toggles radar independently|keeps an unavailable radar visibly disabled'
```

ESLint del componente superato nella precedente verifica della stessa identica
modifica. `git diff --check` superato. Nessun test aggiunto per duplicare la semplice
sostituzione del simbolo.

## Evidenze e limiti

[Ricevuta con misure e hash](evidence/radar-antenna-20261025/verification.json).
Quattro screenshot sono conservati localmente nella cartella
`radar-antenna-20261025` dell'area visualizzazioni della chat, fuori dal repository;
nomi e hash sono nella ricevuta. Nessuna immagine o credenziale privata in Git.

- Nessuna nuova prova sul Galaxy o Safari/iPhone; prima di un'eventuale promozione
  resta la verifica su dispositivo prevista da AGENTS.md.
- Nessuna nuova verifica linguistica in friulano: testi italiani e friulani non
  modificati; lo stesso componente rende entrambe le lingue.
- Il controllo è limitato all'icona e al comando della mappa, non attesta qualità
  meteorologica, recapito di notifiche o funzionamento di tutti i servizi.
- Nessuna AAB, installazione, push, deploy o invio. Nessuna modifica agli orari.
- Follow-up Eventi del **26 ottobre, corsa delle 05:00 Europe/Rome**, mantenuto
  attivo; prima verifica dalle 05:15, anche più tardi se il PC viene acceso dopo.
