# Release 0.1.15 e candidata Web — preparazione locale del 26 ottobre 2026

**Allineamento locale completato e build riuscite; verifica completa dei servizi dal vivo ancora aperta per CAMS scaduto.** Nessuna nuova AAB, riserva versione, installazione, push, deploy o invio. Sponsor disattivati (catalogo live: revisione 117, zero campagne).

## Sorgenti e lavoro salvato

- Ramo `codex/release-0.1.15`. Verbali e ricevute della prova Galaxy 300037 e del recupero Eventi del 24 ottobre salvati nel commit `15be063d`.
- Main `a41353921bd10c94b7763f8f1b5588da72e810d7`, uguale a `origin/main` letto il 26 ottobre, incorporato con merge `eb829a07`.
- Sorgente della candidata **`83c12c58535e56e0603c7136c7eb742f8ac2664f`**; include l'antenna radar approvata `738c6538` e la correzione circoscritta del testo secondario in scuro. Il riquadro bianco di indisponibilità mantiene testo scuro. Nessuna variazione di traduzioni, comportamenti radar o contratti meteo.
- Main non modificato da questa preparazione. La nuova correzione del contrasto è soltanto sul ramo release; non è stata promossa né provata sul Galaxy. Le correzioni Barcolana/allarmi e il pannello Eventi dell'altra chat restano separati.
- Ramo remoto release ancora `f53dfe20`; nuova sorgente non pubblicata, CI del commit esatto ancora da eseguire dopo push autorizzato. La CI delle vecchie sorgenti non certifica questa candidata.

## Build e verifiche

| Controllo | Esito |
| --- | --- |
| Frontend | 552 file superati, 5 esclusi; 5.055 test superati, 13 esclusi. Nessun fallimento. |
| Lint e guardie Node | PASS; 16 guardie su API, CARTO, versione, dipendenze e isolamento Community QA. |
| Dipendenze | 361 pacchetti non opzionali confrontati col lockfile; node_modules fisico, nessun aggiornamento della toolchain. |
| Android statico | Identità Firebase ufficiale, SDK 36, percorsi Capacitor e certificato upload uguale alla 300037. Contratti configurazione nativa/R8/builder PASS. Gradle di rilascio non eseguito. |
| Ledger e conservazione | 60 record verificati; **9.311 file preesistenti invariati**, inclusi archivi AAB/Web, registri e configurazioni protette. Nessun nuovo codice riservato. |
| API | Tag Play `play-b6fbe4d`, revisione `meteofriul-api-00251-jow`, digest e commit originale `e180b87a` verificati prima/dopo BuildOnly. Health OK. |
| Community / TTL | Contratto effimero, TTL Push, identità/policy/documenti TTL Community e attestazione storica PASS. Collezioni vuote: copertura dei nuovi campioni non completa, esplicitamente distinta dal PASS della policy. |
| Web + risorse Android | Build dalla stessa sorgente, binding API/Community e CARTO verificati, service worker Web verificato. Nessun loopback o harness locale nei bundle. |
| Contrasto radar | Fixture isolata con CSS reale: IT/FUR, chiaro/scuro, testo corrente, avvertenza e indisponibilità. Colori effettivi e assenza di troncamenti verificati nel browser. Non equivale a prova della mappa completa o della AAB. |

L'attestazione storica TTL Community attualmente valida raggiunge il limite dei 30 giorni il **26 ottobre alle 21:48:36 UTC (22:48:36 italiane)**. Il builder deve ripetere il gate; dopo quella scadenza serve una nuova attestazione valida, senza riscrivere la precedente o aggirare il controllo.

## Candidata Web archiviata

Archivio canonico: `release-artifacts/web-candidates/20261026-0.1.15-83c12c58/`.
Manifest SHA256 **`8609b3fca9fa2a3de2ac83562b34732a9bbb6f9b6f70d2c9b2591665e27cb135`**.
Web: 506 file; risorse Web Android: 505 file; 1892 sorgenti frontend con hash. Copie e hash verificati dopo archiviazione.
Frontend tree: `75d4941566eb02d5cf39b871a091f92256c679c4`.

Questa candidata **non è la Web incorporata nella vecchia AAB 300037**: prepara il prossimo pacchetto dalla nuova sorgente. La 300037 e la sua Web storica da `d15edb10` restano immutabili. VersionName `0.1.15`, codice configurato ancora `300037`; `300038` è solo il prossimo codice compatibile con il registro locale, non riservato. Prima di generare: rileggere il massimo Play, aggiornare il codice, salvare/pushare il commit finale, ottenere CI e ricompilare i due target dalla medesima sorgente finale.

## Limite trovato nei servizi correnti

L'anteprima locale (dev e stabile) non supera il controllo di prontezza e il launcher arresta i processi che ha avviato. Non è dichiarata una verifica completa riuscita. L'apertura transitoria aveva anche la mappa CARTO senza chiave nel profilo locale; i bundle ufficiali hanno invece superato il controllo della chiave CARTO. Nessuna prova su tile reali della nuova candidata viene dedotta da questi controlli statici.

Letture dirette degli oggetti già pubblicati:

- ICON **`20261026T000000Z`**: indice e manifest coerenti per hash/dimensioni, 215 comuni, utilizzabile fino al 27 ottobre 00:00 UTC.
- Aria e pollini **`20261025T000000Z`**: release atomica e manifest integri, 215 oggetti ciascuno; `usable_until=2026-10-26T06:00:00Z`, cioè **07:00 italiane**. Alla lettura del 26 ottobre erano già scaduti. Non sono stati letti tutti i payload comunali né allungata la loro validità.
- Ultime tre esecuzioni CAMS ordinarie del 25 ottobre (11:00, 15:00 e 20:00 UTC) concluse con successo; ciò non prolunga la validità del modello pubblicato. Scheduler invariato `0 9,10,11,15,20 * * *`, `Etc/UTC`; prossima partenza prevista **26 ottobre 09:00 UTC / 10:00 italiane**. Esiste dunque un intervallo fra scadenza e prossima acquisizione; non viene qualificato come nuovo fallimento del job.

Il rifiuto dei dati scaduti è coerente con la guardia di prontezza. La nuova AAB non corregge questa finestra di indisponibilità: occorre verificare il recupero CAMS o affrontarne separatamente disponibilità/contratto, senza trasformare dati scaduti in dati correnti. Barcolana resta anch'essa una questione backend separata; la corsa Eventi del 26 ottobre aveva la fonte stale. Il follow-up Eventi è stato eliminato su richiesta, non è ancora pendente.

## Ordine per il prossimo test interno

1. Chiudere la lettura dal vivo di CAMS quando torna disponibile; verificare il limite di validità senza esecuzioni manuali implicite. Conservare aperto il recupero Barcolana finché non attestato.
2. Pubblicare il ramo release e verificare la CI sul commit finale; preparare il nuovo versionCode dopo lettura Play. Ripetere attestazioni che scadono, specialmente TTL Community.
3. Solo con autorizzazione esplicita generare la AAB tramite il builder protetto, verificare firma/configurazione/mapping e archiviare senza sovrascrivere. Caricamento interno separato, account già abilitati invariati.
4. Dopo aggiornamento Play del proprietario: prova della nuova AAB sul Galaxy, inclusi Posizione prima/dopo, aria/pollini al primo carico e rientro IT/FUR, tutte le sezioni, antenna/contrasto radar e completezza Eventi. Nessun invio di prova implicito.

Produzione e Web pubblica non aggiornate. Ultima osservazione pubblica disponibile: Web 0.1.14 del 23 ottobre e produzione Play 0.1.14/300031 del 24 ottobre; non sono letture ripetute oggi. Restano non verificati Android 15/16, gesti/cutout, tablet/multi-window, errori GPS reali e Safari/iPhone/PWA. Non è una qualifica completa né un'autorizzazione alla produzione.

[Ricevuta sanificata](evidence/release-web-alignment-20261026/verification.json) · [Stato release](RELEASE_0.1.15_STATUS_20261021.md) · [Parità Web](WEB_ANDROID_RELEASE_PARITY.md).
