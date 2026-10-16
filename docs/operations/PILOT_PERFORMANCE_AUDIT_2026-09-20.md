# Audit prestazionale pilota — 20 settembre 2026

Stato: **APK pilota aggiornata sul telefono; confronto prestazionale e stabilità
del player radar verificati sul Samsung. Riscontro soggettivo ancora da raccogliere**.

Perimetro: pilota `com.meteofriul.app.localpilot`, Samsung A52 con Android 14;
sorgenti dalla baseline Git `07513ed`, con modifiche locali successive.
Nessun push, commit, pubblicazione o modifica cloud effettuati per questo audit.
Il package beta/main e la distribuzione Play sono esterni al perimetro.

## Baseline sul telefono

Misure della pilota installata prima dell'aggiornamento. Sono singoli campioni
con diagnostica attiva; non costituiscono una distribuzione statistica di avvii
né una promessa di 60 fps. Activity startup, primo contenuto WebView, long task
e intervalli `requestAnimationFrame` misurano fenomeni diversi.

| Misura | Baseline | Significato |
| --- | ---: | --- |
| Avvio Android COLD, `am start -W` | 4.096 ms | Avvio Activity; non FCP né completamento dati |
| FCP dell'avvio COLD baseline | 2.368 ms | Primo contenuto WebView di quell'avvio, distinto dal reload sotto |
| FCP, ricaricamento WebView profilato per 10 s | 1.476 ms | Primo contenuto dipinto nel campione di reload |
| Long task nello stesso intervallo | 13; somma 3.507 ms; massimo 709 ms | Occupazione prolungata del thread principale |
| Intervalli rAF nello stesso campione | p99 315,7 ms; massimo 747,6 ms | Ritardi tra callback; non una misura autonoma degli fps di tutte le schermate |
| Posizione superiore slider radar, campione 16 s | 626,5536–643,7262 px | Escursione 17,17 px |
| Larghezza slider radar, stesso campione | 220,0893–252,5833 px | Escursione 32,49 px |

Il profilo CPU attribuisce una parte rilevante del costo ripetuto alla creazione
di `Intl.DateTimeFormat` nelle date degli eventi e nelle etichette orarie meteo.
La geometria radar variabile è un problema di stabilità dei controlli distinto
dalla latenza di caricamento delle tessere.

## Modifiche locali

- Formatter riutilizzabili con limite di 32 configurazioni e chiave completa di
  locale/opzioni. Si conservano soltanto formatter con fuso esplicito; quelli
  con fuso implicito mantengono il comportamento nativo al cambio di timezone.
  Le date civili degli eventi copiano i campi locali in UTC prima della resa,
  mantenendo il giorno calendario. Applicazione a eventi, orari meteo,
  conversioni solari, adapter ICON e selezione UV; la chiave del giorno UV è
  calcolata una volta per selezione.
- Almanacco e Scopri della Home hanno memo separati dalle risposte degli altri
  servizi, così l'arrivo di eventi/bollettino non ricostruisce indiscriminatamente
  i modelli editoriali.
- Le richieste eventi identiche già in corso condividono lo stesso caricamento,
  incluse tutte le pagine. Dopo esito o errore la deduplica è rimossa: un refresh
  successivo può interrogare nuovamente il servizio.
- Webcam e community possono aggiornare la UI appena il rispettivo risultato è
  disponibile. Il completamento complessivo attende entrambi; la generazione
  corrente protegge da risposte tardive di una vista precedente.
- Il refresh manuale appartiene alla vista che lo ha ricevuto: non viene
  riprodotto automaticamente sulle viste aperte dopo e il feedback di una
  richiesta superata viene chiuso.
- La proiezione dei marker mappa raggruppa gli eventi Leaflet nello stesso frame.
  La correzione radar mantiene spazio stabile per i controlli e prepara il frame
  successivo preservando l'immagine precedente. Ogni frame caricato ha almeno
  700 ms di permanenza prima dell'avanzamento; la palette LUT mantiene identiche
  tutte le 65.536 combinazioni intensità/trasparenza verificate nel test.
- Il percorso protetto di build ora inizializza la directory ignorata
  `android/app/src/main/assets/public` come scaffold vuoto dei plugin. Capacitor 8
  altrimenti tenta `copy android` su un clone nuovo senza `dist`. Non vengono
  importati archivi, costruiti asset Web ordinari o trasferiti asset pilota nel
  ramo main; restano il confronto hash dei Gradle e il guard prima del mirror
  da build temporanea a `localPilot`.
- Su richiesta dell'utente il nome pilota Android, browser e manifest PWA è
  **Meteo Friûl**, senza “Eventi”. Le icone sono invariate.

Le ottimizzazioni non allungano le scadenze dei dati né eliminano i controlli di
integrità, provenienza e località del meteo.

## Verifiche automatiche

- Suite frontend estesa: **492 file passati, 4 saltati; 4.119 test passati,
  11 saltati**.
- Successiva verifica mirata delle ultime correzioni radar: **66 test passati
  in 4 file**.
- Guard Node: **24/24 passati**, inclusi nome pilota e regressione clone nuovo
  eseguita contro il CLI Capacitor realmente installato in una fixture
  temporanea. Il test passa dalla root e da `frontend`.
- ESLint mirato e `git diff --check` puliti.
- Formatter/consumatori verificati anche nella tranche dedicata da 142 test;
  tre casi su date civili/cambio d'ora passano inoltre con `Pacific/Honolulu` e
  `Asia/Tokyo`.

## Microbenchmark PC

Microbenchmark Node sul PC: 25 coppie intercalate di vecchio sorgente da HEAD e
nuovo sorgente, con output JSON identico per ogni coppia.

| Funzione isolata | Mediana prima | Mediana dopo |
| --- | ---: | ---: |
| Selezione UV su 72 ore | 21,35 ms | 0,85 ms |
| Calcolo/presentazione di 48 campioni solari | 32,87 ms | 2,56 ms |

Sono misure di funzioni sul PC, **non tempi del telefono** né del caricamento
completo. Le osservazioni dell'APK aggiornata sono riportate separatamente sotto.

## Build e aggiornamento conservativo

Build protetta `localPilot`: **PASS, 151 task**. APK e `base.apk` realmente
installata hanno SHA-256 identico:

```text
8307f0144183158fa4465046452e650519bede39d9c3145786e3676cfcffbeaf
```

`adb install -r` riuscito alle **10:41:41 CEST del 20 settembre**. Identità:
`com.meteofriul.app.localpilot`, versione `1.0.1-local-pilot`, codice `300012`
invariati. App ID Android `10742` e prima installazione del 4 settembre alle
11:11:31 invariati.

Conservazione verificata senza cancellare dati:

- tre file di preferenze native byte-per-byte identici;
- 66 chiavi localStorage presenti, nessuna eliminata; 59 hash identici e sette
  valori di cache aggiornati;
- beta/main invariata: hash di APK base e tre split e `lastUpdateTime` identici.

Il bundle iniziale resta ampio: **3.856,97 kB**, **885,63 kB gzip**. Non è stato
eseguito un refactor dei chunk/cataloghi; il warning di dimensione rimane un
limite distinto dai miglioramenti di elaborazione misurati.

## Misure sul telefono dopo l'aggiornamento

Confronto fra due campioni di reload WebView profilati per 10 secondi:

| Misura | Prima | Dopo |
| --- | ---: | ---: |
| FCP | 1.476 ms | 1.200 ms |
| Long task | 13 | 11 |
| Somma durate long task | 3.507 ms | 1.466 ms |
| Long task massimo | 709 ms | 446 ms |
| Intervallo rAF p99 | 315,7 ms | 116,4 ms |
| Intervallo rAF massimo | 747,6 ms | 481,9 ms |
| Richieste HTTP eventi | 6 | 3 |

Le tre richieste eventi corrispondono a una paginazione completa invece di due
caricamenti duplicati. Nessun errore runtime rilevato nel campione successivo.
I long task residui e gli intervalli rAF elevati impediscono di dichiarare
fluidità costante a 60 fps.

Avvii Android COLD, da non mescolare con i reload della tabella precedente:

| Campione | Activity `am start -W` | FCP WebView |
| --- | ---: | ---: |
| Baseline precedente | 4.096 ms | 2.368 ms |
| Prima apertura immediatamente dopo installazione | **6.556 ms** | **4.028 ms** |
| Avvio COLD ripetuto dopo aggiornamento | 2.993 ms | 1.332 ms |

La prima apertura dopo installazione è risultata **più lenta della baseline**.
Il successivo avvio è più rapido, ma questi campioni non stabiliscono una causa
certa della differenza né un miglioramento statistico degli avvii. Cache,
inizializzazione, diagnostica e condizioni dei servizi non sono stati isolati
con una campagna ripetuta.

## Disponibilità dati cloud, separata dalla velocità UI

Verifiche pubbliche in sola lettura del 20 settembre, ultime letture alle
**08:26 UTC / 10:26 CEST**:

| Flusso | Ultima corsa pubblicata | Pubblicazione | Stato rispetto alle policy |
| --- | --- | --- | --- |
| ICON, revisione 26 | 19 settembre 12:00 UTC | 19 settembre 18:00:20 UTC | Freschezza terminata il 20 alle 06:00 UTC; utilizzabile fino alle 12:00 UTC |
| CAMS aria/pollini, revisione 11 | 19 settembre 00:00 UTC | 19 settembre 10:01:24 UTC | Limite di 30 ore superato il 20 alle 06:00 UTC |
| UV | 19 settembre 00:00 UTC | Non attestata da questa lettura | Entro 48 ore; 72 campioni fino al 21 settembre 23:00 UTC |

I tre endpoint dati rispondono HTTP 200. Alle 08:12 UTC sono stati verificati
anche hash/dimensioni della release CAMS e dei manifest ICON, aria e pollini,
schema, catalogo e copertura dei 215 Comuni: coerenti con i riferimenti pubblicati.

`start-local-weather-pilot.ps1 -CheckOnly -WeatherCloud` fallisce perché
`Test-CamsFamilyArtifacts -RequireCurrent` richiede CAMS entro `run + 30 ore`.
Il fallimento attestato riguarda la freschezza, non la raggiungibilità del
reader o una corruzione dei manifest. Un'app più veloce non produce nuove corse.

Il reader sorgente non espone avanzamento pubblico dei job. Il percorso
`/healthz`, presente nel sorgente, restituisce 404 Google sul servizio osservato;
gli endpoint dati restano disponibili. Gli esiti operativi sono nei file privati
`state/dispatch/...` e nei log `publication_result`. Non è quindi attestato se
l'acquisizione del 20 settembre sia pending, running o failed; non sono stati
avviati job o eseguiti interventi cloud durante queste verifiche.

## Radar verificato sul Samsung

L'utente ha aperto Tempo reale → Radar e avviato Play. Campione aggiornato di
18 secondi, con un giro completo della sequenza, incluso il badge LIVE:

| Misura | Prima (16 s) | Dopo (18 s) |
| --- | ---: | ---: |
| Escursione verticale slider | 17,17 px | **0 px** |
| Variazione larghezza slider | 32,49 px | **0 px** |
| Long task | 1 da 50 ms | **0** |
| Intervallo rAF massimo | 83 ms | 49,9 ms |
| Intervallo rAF p99 | 49,9 ms | 49,8 ms |
| Intervalli completi tra frame pronti | 731–814,3 ms (20) | 714,1–747,8 ms (24) |

La prima frazione di frame già in corso all'avvio di ciascuna misurazione è
esclusa dal confronto di cadenza. Il pannello aggiornato mantiene top
626,3572 px e larghezza slider 203,3810 px; sinistra e altezza sono costanti.
Nessun errore runtime rilevato nel campione. Screenshot finale ispezionato.
La prova è avvenuta con messaggio «Nessuna precipitazione rilevata»: non attesta
le prestazioni con precipitazioni intense, zoom/trascinamento simultaneo o
connessione degradata. Pausa, scrub, ritorno A→B→A, lentezza del prefetch,
errori e smontaggio hanno inoltre copertura automatica; pausa e scrub verificati
anche sul browser pilota ufficiale a porta 5174.

Il saltello geometrico osservato è risolto nel campione reale. Non si dichiara
un miglioramento significativo del p99 radar, sostanzialmente invariato,
né fluidità universale a 60 fps. Il giudizio soggettivo dell'utente rimane
da raccogliere.

## Limiti residui e prossimo intervento suggerito

Il profilo aggiornato mostra ancora elaborazioni sincrone: ranking eventi
(circa 218 ms inclusivi), costruzione record eventi (circa 167 ms su altri
stack), calendario annuale dei proverbi (circa 147 ms) e SHA/fingerprint
(circa 128 ms, principalmente confronti ripetuti di display). Sono stime da
campionamento CPU, non tempi di rete o somme da equiparare ai long task.

I prossimi interventi circoscritti sono condividere la proiezione degli eventi
fra Home e badge, evitare di costruire subito l'intero calendario annuale e
memorizzare soltanto fingerprint di oggetti immutabili. Non sono implementati
in questa tranche e non devono rimuovere verifiche di integrità. Il profilo
non dimostra che il parsing JSON sia il costo dominante del bundle.

La UI web locale usa una fixture meteo del 4 settembre: è valida per collaudo
UI, non per valutare la freschezza del cloud. L'APK compilata usa il cloud HTTPS
senza orologio di test. Nessun dato è stato importato da cartelle storiche.

La disponibilità cloud descritta è quella verificata alle 10:26 CEST, non una
certificazione permanente né una recovery della pipeline. Nessun push o
pubblicazione è necessario per questi test locali.
