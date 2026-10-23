# Tempo reale: mappa collassata e distanza dalla navigazione — 23 ottobre 2026

## Stato e perimetro

Correzione locale nel ramo `codex/realtime-layout`, dalla base main
`f9e178b25afd5154008539dbd15d9c1b5957abd1`. Sorgenti identificate dagli hash
nel [risultato verificabile](evidence/realtime-layout-20261023/verification.json).
Il proprietario ha autorizzato il 23 ottobre commit e promozione locale su main
delle modifiche verificate. L’integrazione in una nuova AAB rimane da eseguire.
La 0.1.15 / 300035 installata rimane difettosa: questo verbale non chiude
la sua verifica runtime e non autorizza una pubblicazione.

## Causa e correzione

Il raggruppamento di località e menù in AppRoutes ha ridotto da tre a due
i figli diretti di WeatherSwipeShell. Il layout di Tempo reale manteneva
tre righe: la mappa era nella seconda, automatica, mentre la terza flessibile
rimaneva vuota. Nell'anteprima 661 × 902 la mappa era alta 2 pixel;
la riga vuota occupava circa 586,61 pixel. Lo stesso schema CSS è presente
nel sorgente `5e9bc7d` della 300035 segnalata dal proprietario.

- Corrette le due righe della griglia, anche nella regola Android per altezze
  inferiori a 600 pixel.
- Su richiesta del proprietario, il contenitore della mappa termina a 8 pixel
  dalla navigazione inferiore. Solo in Tempo reale la barra occupa una riga
  propria: il suo ingombro effettivo sostituisce la riserva stimata di 84 pixel.
  Restano lo spazio sicuro inferiore e la protezione per gli schermi bassi.
- Non modificati la barra fissa di Bollettino/Eventi, lo scorrimento delle
  Previsioni, i servizi, i dati e gli invii.

## Verifiche eseguite

La nuova regressione incrocia i figli effettivi di AppRoutes con entrambe
le definizioni della griglia. Prima del fix fallisce in italiano e friulano
(14 passati, 2 falliti); dopo il fix passa.

Vitest con `--configLoader native`: **170 test passati in 8 file**,
relativi ad AppRoutes.weatherSwipe, liveCss, LiveView.pilotCompactLayout,
LiveView, LiveView.webcamCarousel, layoutCss, AppShell.nativeChrome,
WeatherSwipeShell. Lint dei due file di test modificati e `git diff --check`
superati. Nessuna build Android eseguita.

Anteprima avviata esclusivamente con `scripts/start-local-weather-pilot.ps1`
sulla porta 5174, profilo NationalCloud, riusando il backend locale esistente.
La configurazione Carto mancante nel nuovo checkout è stata riutilizzata
dalla release nel solo file ignorato `.env.local-pilot.local`, senza cambiarla
o pubblicarla. Screenshot e geometria confermano la mappa visibile in italiano
e friulano, chiaro e scuro: contenitore alto 626,66 pixel, distacco 8 pixel.
Lista segnalazioni vuota, catalogo Webcam e controlli Radar raggiungibili.
Previsioni visibili con scorrimento normale; Bollettino visibile con intestazione
sticky; ritorno a Tempo reale senza collasso.

Galaxy A52 / Android 14, Brave già installato, collegamento USB verso 5174:
mappa e barra visibili in italiano e friulano, con piccolo distacco, confermati
da screenshot. Ripristinato italiano chiaro. Nessuna installazione né modifica
alle preferenze dell'app ufficiale. Le gerarchie Brave catturate espongono
principalmente il browser, quindi la prova del contenuto è visiva; la misura
esatta degli 8 pixel è quella DOM dell'anteprima desktop.

## Limiti e prossimo passaggio

La prova riguarda il layout locale. Non equivale a una prova della nuova release
minificata sul Galaxy, né a un collaudo completo di Tempo reale. Non sono stati
provati invii, conferme o ritiri, tutte le singole webcam, Android 15/16 o il
runtime nativo con finestra bassa. L'anteprima ha Community non configurata:
mostra un pulsante disabilitato e una nota che occupa spazio nel pannello
inferiore; questa configurazione non rappresenta l'invio dell'app ufficiale.

Prima di chiudere REALTIME-LAYOUT-01 nella release serve integrare questo fix,
produrre un nuovo artefatto solo quando autorizzato e verificare sul telefono
la mappa visibile, il distacco e i controlli sul pacchetto minificato effettivo.
Sponsor invariati e disattivati. Nessun push, deploy, AAB, installazione,
emulatore o invio manuale eseguiti. La promozione del codice su main è separata
dalla verifica della prossima release installata.

Le prove private sono conservate nella radice canonica sotto
`.tmp/realtime-layout-20261023`; gli hash dei soli screenshot pertinenti sono
nel JSON. Nessuna credenziale, alias o identificativo dispositivo nel verbale.
