# Eventi — verifica su telefono TEST del 13 ottobre 2026

## Identità

- Ramo: `codex/events-card-quarantine`; candidato verificato: `921ce1fc`.
- Telefono: Samsung SM-A525F, Android 14 (API 34), collegato via ADB.
- App già installata: `com.meteofriul.app.tester`, versione `0.1.14-tester` (`300031`), ultimo aggiornamento 12 ottobre 2026 alle 16:46. Nessuna APK è stata generata o installata per questa verifica; i dati dell'app sono stati conservati.
- Backend in esercizio: job Eventi al digest `sha256:926f97d9a45df8f8845d89aaa4ab9c23c51893fc39f095a01e23f7ec102c89c4`; API al digest `sha256:3d6afce26fd089161047fc32b9d088365644a50328ccfeb4499b0066fddf3c6e`. Catalogo ufficiale verificato nella sezione 11 dell'architettura: generazione `1791884923752339`.

## Controlli nell'app TEST

1. Aperta la sezione Eventi a Pordenone: le schede hanno immagini, date, località e categoria visibili.
2. Selezionato `Oggi` e `Feste e sagre`: quattro schede, tra cui una sola `Sagra del Rosario` a Caneva. Nessun doppione di questa festa nel filtro osservato.
3. Aperta l'anteprima `Sagra del Rosario`: immagine 2026, categoria sagra, date 2–18 ottobre 2026, Via Roma 1 a Caneva, descrizione, fonte TurismoFVG e pulsanti `Pagina dell'evento` e `Indicazioni` presenti. Non sono stati aperti i link esterni.
4. Cambiata temporaneamente la località in Trieste e aperto `Prossimi`: `Laboratori MESS · Museo della Bora` mostra una sola scheda con `2 appuntamenti`. L'anteprima espone descrizione, fonte MESS, giornate 18 ottobre e 15 novembre, e due voci distinte nel programma scorrevole.
5. Ripristinate la località predefinita Pordenone e la Posizione attiva. Il controllo finale delle impostazioni mostra entrambi i valori originali; tornando a Eventi appare nuovamente Pordenone.

Esito: **positivo** per visualizzazione del catalogo, categoria Sagre, scheda senza doppione osservabile, anteprima con descrizione e programma a più appuntamenti. Le prove backend, del job e dell'API sono registrate nel resoconto architetturale e nei test locali del ramo. La scheda Barcolana non è stata verificata sul telefono in questa sessione.

Le schermate locali, ignorate da Git, sono in `.dev-logs/events-preview/device-20261013/` (`sagre-pordenone.png`, `rosario-preview.png`, `mess-programme.png`, `settings-restored.png`).

## Ambito della verifica

Il ramo Eventi modifica il backend, gli script e i documenti, senza modificare il frontend o Android rispetto al punto di diramazione. Dopo l'integrazione di `main` nel ramo, il diff Eventi rispetto a `main` non contiene file frontend. La prova sul telefono valida quindi il nuovo catalogo e l'API attraverso la TEST già installata. Non equivale a una nuova verifica di rilascio Android.

Le modifiche Android e CSS entrate in `main` il 12–13 ottobre sono state valutate separatamente nel loro workstream; per quel lavoro il proprietario aveva accettato la prova su emulatori in sostituzione del telefono, come documentato in [ANDROID_EDGE_TO_EDGE_2026-10-12.md](ANDROID_EDGE_TO_EDGE_2026-10-12.md). Nessuna nuova APK TEST è necessaria per promuovere questo solo intervento backend.