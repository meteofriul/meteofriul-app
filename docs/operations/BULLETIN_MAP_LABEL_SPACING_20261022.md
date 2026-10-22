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

Prima verifica svolta senza telefono; il successivo controllo sul Galaxy è riportato sotto. Nessuna verifica della modifica nel pacchetto Android installato.
Alla chiusura della prima verifica la correzione era conservata sul ramo dedicato, senza promozione su main.
Nessuna AAB, installazione, emulatore, push, deploy o invio.
I file della verifica sintetica restano locali e ignorati da Git.

## Verifica Galaxy collegato

Completata il 22 ottobre sul candidato `babbc67f`, senza ulteriori modifiche
funzionali. Galaxy A52 SM-A525F, Android 14, schermo 1080 × 2400, densità 420;
Brave 1.97.59 già installato. Anteprima locale sulla porta 5174 via USB reverse.

- Pioggia, italiano/chiaro, `1000m -12°C`: badge interamente visibile e
  separato dalle gocce della Carnia.
- Temporale, friulano/scuro, `1000m -12°C`: badge separato dal fulmine.
- Pagina completa del bollettino, italiano/chiaro: mappa e badge corretti,
  con dati OSMER del 22 ottobre. Non è una nuova verifica dei servizi meteo.
- Screenshot fisici e gerarchia Android acquisiti dopo apertura delle pagine.
  Il primo scatto della pagina completa era ancora in caricamento; non è usato
  come prova di successo. Lo scatto successivo mostra la mappa caricata.

[Evidenze selezionate e hash](evidence/bulletin-map-2026-10-22/manifest.json).
I due casi pioggia/temporale usano il componente e i CSS reali con dati
sintetici dichiarati, per esercitare le icone indipendentemente dal meteo.

Esito positivo per questa correzione nel browser reale del telefono.
Non equivale a una prova di una nuova AAB/WebView Android. Nessuna installazione,
AAB, push, deploy, modifica alle app installate o invio manuale.
Durante le verifiche main e gli altri rami sono rimasti invariati; la verifica non include GPS,
configurazione nativa o navigazione fissa delle sezioni.
## Promozione locale su main

Il 22 ottobre il proprietario ha autorizzato il passaggio su main della sola
correzione della mappa e del verbale, dopo la verifica sul Galaxy in Brave.
Il perimetro comprende `babbc67f` (correzione) e `a9af8f98` (verifica sul
telefono), le relative evidenze e questo aggiornamento documentale.

Controlli finali: ramo e worktree main puliti; diff limitato al componente
mappa e alla sua documentazione; `git diff --check`, controllo di pulizia del
workspace canonico e hash dei file salvati nel commit tutti superati.
Il componente è invariato rispetto ai 36 test e alle verifiche browser/Galaxy.

La navigazione fissa di Bollettino ed Eventi resta nel ramo separato
`codex/section-sticky-navigation` (`aa505cd6`), esclusa da questa promozione.
L'anteprima della mappa non include quella modifica. Restano separati anche
GPS e preparazione della release. Nessuna AAB, installazione, push, deploy o
invio: promozione del codice solo locale, senza aggiornare l'app installata.
