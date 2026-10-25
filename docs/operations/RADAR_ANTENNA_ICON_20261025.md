# Icona antenna radar sulla mappa — 25 ottobre 2026

## Identità e perimetro

Ramo `codex/radar-antenna-icon`, da main
`35843b19cee6ba66b4f47331d08713bc9a9c815e`.
Modifica approvata dal proprietario: antenna con onde (`SatelliteDish` della
libreria Lucide già presente) al posto dei cerchi radar nel pulsante di Tempo reale.
Cambiano soltanto import e componente SVG in `TerritoryImmersiveMap.jsx`.
Restano invariati dimensioni, colori, logica, stato attivo/disattivo, etichette
accessibili, sorgenti meteo e controlli del bollettino. Nessuna nuova dipendenza.

Modifica applicativa salvata nel commit `738c6538`, verificata sul Galaxy e
promossa in **main locale** insieme al presente verbale. Il ramo dedicato è
conservato. Nessun push: GitHub e ramo release non aggiornati da questa promozione.
La modifica non compare negli artefatti Android/Web già generati né nella Web pubblica.
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

## Verifica reale Brave / Galaxy e promozione locale

Il 25 ottobre verificata la stessa sorgente `738c6538` su **Galaxy A52
(SM-A525F), Android 14 / API 34, Brave 1.97.59**, motore Chrome 155.0.8059.85.
Anteprima del ramo sulla porta 5174 raggiunta tramite USB; nessuna installazione,
nessuna emulazione e nessuna modifica dell'app Android installata.

- Chiaro e scuro: antenna leggibile e interamente contenuta nel pulsante,
  sia spenta sia attiva. Nessuna ulteriore correzione CSS necessaria.
- Tocco sul telefono: apertura e chiusura del pannello radar, con
  `aria-pressed` rispettivamente `true` e `false`, in entrambi i temi.
- Misure reali: pulsante 44 × 44 px CSS, SVG 21 × 21 px CSS;
  viewport 411 × 728 px, DPR 2,625; nessun overflow orizzontale.
- Riscontro effettuato sugli stati effettivi e sulle schermate dopo i tocchi,
  non dedotto dal solo successo del comando di interazione.
- Ripristinati tema chiaro e radar spento, come all'inizio della prova su Brave.

Le misure e gli hash delle sei schermate del Galaxy (quattro stati e due ritorni
allo stato spento) sono nella ricevuta, sezione `device_check`. I file sono solo
locali in `.tmp/radar-antenna-galaxy-20261025`, ignorata da Git. I precedenti
controlli automatici restano riferiti alla stessa identica sorgente: l'hash è
stato ricontrollato e in questo passaggio cambia soltanto la documentazione.
Promozione locale senza conflitti, con avanzamento di main dal precedente
`35843b19`; nessuna CI remota avviata in assenza di push. README, stato release e
parità Web aggiornati distinguendo sorgenti approvate e pacchetti non rigenerati.

## Evidenze e limiti

[Ricevuta con misure e hash](evidence/radar-antenna-20261025/verification.json).
Quattro screenshot sono conservati localmente nella cartella
`radar-antenna-20261025` dell'area visualizzazioni della chat, fuori dal repository;
nomi e hash sono nella ricevuta. Nessuna immagine o credenziale privata in Git.

- Prova reale Brave/Galaxy superata per questo intervento. Safari/iPhone e
  nuova AAB con questa icona non provati: non sono attestati da questa verifica.
- Nessuna nuova verifica linguistica in friulano: testi italiani e friulani non
  modificati; lo stesso componente rende entrambe le lingue.
- Il controllo è limitato all'icona e al comando della mappa, non attesta qualità
  meteorologica, recapito di notifiche o funzionamento di tutti i servizi.
- Nessuna AAB, installazione, push, deploy o invio. Nessuna modifica agli orari.
- Follow-up Eventi del **26 ottobre, corsa delle 05:00 Europe/Rome**, mantenuto
  attivo; prima verifica dalle 05:15, anche più tardi se il PC viene acceso dopo.
