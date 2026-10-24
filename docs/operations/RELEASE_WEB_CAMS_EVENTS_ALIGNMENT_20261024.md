# Release 0.1.15 e candidata Web allineate a main — 24 ottobre 2026

## Esito e identità

Il ramo locale `codex/release-0.1.15` è stato allineato in fast-forward da
`8fb11af8` a main **`0841020a42d836e44de306e9639b07b98fceaefc`**, senza conflitti e senza modifiche al prodotto.
Il frontend comune è l'albero `7eeb8368dee24aa60bea567d02af6883c589c0d1`.
Incluse le correzioni approvate delle PR 19 e 20: recupero e transitorio iniziale
aria/pollini, contatore Eventi in scuro, testo GPS e traduzioni friulane.
Conservate le correzioni precedenti, compresa Tempo reale.

Nuova candidata Web compilata con il percorso protetto `-BuildOnly`, insieme
ai soli asset Web in modalità Android dalla stessa sorgente. Nessuna AAB,
APK, sincronizzazione Capacitor, Gradle, installazione, push, deploy o invio.
Durante la preparazione main e GitHub non sono stati modificati. La documentazione
è stata salvata sul ramo release, successiva alla base prodotto `0841020a`.
Il successivo push autorizzato è registrato nella sezione seguente; nessun merge su main.

Nome 0.1.15 e codice configurato 300036 invariati: nessun nuovo numero riservato.
La AAB 300036 resta l'ultimo artefatto firmato, dalla sorgente `9d5ff2f4`.
Questa candidata contiene correzioni successive e non aggiorna l'app installata.

## Archivio nuovo e conservazione

Archivio canonico ignorato:
`release-artifacts/web-candidates/20261024-0.1.15-0841020a/`.

| Contenuto | File | Byte |
| --- | --- | --- |
| Web, incluso service worker | 506 | 76031510 |
| Soli asset Web Android | 505 | 75978842 |

Manifest SHA256: `bd0a6ee2a9ad767efb0e6b85a8466bf61cb426677ae14a13b69bc1183a4d50b2`.
Verificati dimensioni e hash di tutti i 1.011 file prodotti e di 1.892 sorgenti.
I **6.916 file preesistenti protetti sono invariati**, inclusi artefatti,
configurazioni locali e registri. Ledger: 57 record validi e 58 file invariati.
Nessun archivio storico sovrascritto.

[Ricevuta strutturata](evidence/release-web-cams-events-alignment-20261024/verification.json).
Log privati ed evidenze locali: `.tmp/release-cams-events-alignment-20261024/`.

## Controlli e limiti delle prove riutilizzate

| Controllo | Esito |
| --- | --- |
| Sorgenti release rispetto a main | Identici, compresi i file provati sul Galaxy |
| Dipendenze | Directory fisica; 361 versioni conformi al lockfile; Vite 8.1.6; nessuna installazione |
| Pulizia canonica, ledger, parità versioni e diff | PASS |
| Guardie endpoint, CARTO, versione, dipendenze e QA | 16 test PASS |
| Web `-BuildOnly` | PASS; preflight API prima/dopo, endpoint, CARTO e service worker |
| Asset Web Android | PASS; endpoint e CARTO verificati, senza build nativa |
| Bundle entrambi | Contatore scuro, testi IT/FUR, ciclo CAMS e CSS Tempo reale presenti; harness locale assente |
| Hash archivio/sorgenti/protetti | PASS |
| Sponsor prima/dopo | `enabled=false`, zero campagne, revisione 117 |

La [CI di main 40107051151](https://github.com/meteofriul/meteofriul-app/actions/runs/40107051151)
è verde nei tre job (frontend, backend, strumenti Windows). Il commit corrente
aggiunge solo documenti alla sorgente di quella CI: identità del codice
confermata. Non ripetuta la suite completa già passata sugli stessi sorgenti.

Riutilizzati anche i 76 test mirati e le prove
[Brave/Galaxy IT/FUR delle ultime due correzioni](CAMS_INITIAL_LOADING_EVENTS_CONTRAST_20261024.md):
hash dei file esattamente coincidenti. Le
[quattro correzioni precedenti](WEB_POST_300036_GALAXY_20261024.md) restano
incluse; le prove hanno i rispettivi limiti dichiarati. Nessuna nuova sessione
browser o telefono in questa attività. Compilazione e uguaglianza del codice
non vengono presentate come nuova verifica runtime di un pacchetto.

Restano gli avvisi di compilazione già noti sul chunk principale e sull'import
statico/dinamico Almanac. Nessuna modifica a dipendenze o toolchain.

## API e sponsor

API tagged `play-b6fbe4d`, revisione `meteofriul-api-00251-jow`, digest `5522b4cf…`,
sorgente backend originale `e180b87a`: binding e health verificati dal preflight
protetto prima e dopo la build. La verifica lega sorgenti, immagine e revisione,
non si limita a una risposta HTTP 200. Solo letture nel progetto `meteo-friul`,
regione `europe-west1`, account previsto `meteofriul@gmail.com`.
Nessun aggiornamento backend richiesto da questi controlli, nessun audit
aggiuntivo dei job. Sponsor disattivati; pannello e allineamento dati non avviati.

## Qualifica Android e Web ancora distinta

Configurazione nativa, dipendenze e toolchain sono identiche alla sorgente
della 300036. Le quattro aree Android obbligatorie mantengono questi limiti:

| Area | Stato |
| --- | --- |
| Edge-to-edge e inset | Codice nativo invariato; nessuna nuova AAB o prova nativa. Android 15/16, gesti e casi non esercitati restano aperti |
| API delle barre di sistema | Nessuna modifica; gli avvisi delle dipendenze restano quelli già documentati |
| Orientamento e schermi grandi | Policy precedente conservata; tablet e multi-window non verificati qui |
| R8 e risorse | Configurazione invariata; compilati soltanto asset Web. Mapping, shrinking e runtime della futura AAB da verificare con la build autorizzata |

La nuova Web resta **non pubblicata**. Prima della pubblicazione restano la
verifica dei servizi del bundle da un'origine autorizzata e il passaggio dalla
cache della Web pubblica. Safari/iPhone e PWA non verificati. Nessuna nuova
lettura del sito pubblico o di Play: restano le ultime osservazioni datate.

Per la futura AAB servirà un codice superiore a quelli consumati, verificato
nuovamente contro Play e ledger prima della riserva. La preparazione non
autorizza generazione, caricamento o distribuzione.

## Push e verifica GitHub — 24 ottobre 2026

Push autorizzato del solo ramo `codex/release-0.1.15`, confermato su GitHub
con il commit documentale `61318213`. Il precedente `9dd12d6d` non è stato
pubblicato: due hash SHA-256 delle evidenze erano falsi positivi della regola
generica per chiavi API. Tutti i 26 hash sono stati verificati contro i file
locali e rappresentati in record separati file/SHA-256. Nessun segreto rilevato;
controllo privacy completo superato, senza esclusioni o modifiche alla guardia.

Confronto remoto: zero commit di main mancanti, sole differenze documentali.
Main resta `0841020a`. CI `40107051151` riconfermata verde nei tre job; codice
frontend, backend, script e workflow identico al commit verificato `7813d5c4`.
Il push ordinario a `codex/**` non avvia la CI: nessuna nuova CI dichiarata,
nessuna esecuzione manuale richiesta, nessun workflow in corso o in coda.
Il presente aggiornamento documentale segue sullo stesso ramo.

Sponsor disattivati come nelle letture già registrate, configurazione non
modificata. Nessuna AAB, installazione, pubblicazione Web/Play, deploy o invio.
