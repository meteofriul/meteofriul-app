# Prova editoriale del pannello · 8 novembre 2026

Il backend editoriale del commit `7a1f188a` è stato costruito con Cloud Build `2477efb3-fad6-4696-bc8a-97b510120fe0` dall'archivio Git dei soli `backend/app`, `backend/requirements.txt` e `backend/Dockerfile`. Immagine: `europe-west1-docker.pkg.dev/meteo-friul/cloud-run-source-deploy/meteofriul-api@sha256:f4b1a2ee4de459a496656c08048b498b94119b6980d3cfd8305e764b23513e69`.

La revisione Cloud Run `meteofriul-api-00255-yuz` ha il tag `editorial-7a1f188a` e **0% del traffico ordinario**. Il 100% resta sulla revisione `meteofriul-api-play-b6fbe4d-001`. Il pannello usa direttamente l'URL del tag. La variabile della revisione `EDITORIAL_PUBLICATION_ENABLED=false` blocca la pubblicazione anche sul server; il lettore pubblico restituisce `item: null`.

Verifiche online: `/api/healthz` 200; `/api/editorial/home-advice` 200 con `item: null`; `/api/admin/editorial/home-advice/state` senza login 401; preflight CORS dal pannello 200 con origine consentita. Il claim Firebase `editorialAdmin` è stato assegnato al login proprietario già indicato, conservando gli altri claim. Nove test mirati backend e `compileall` sono passati; il ramo app precedente aveva superato 2.064 test backend, 5.074 test frontend, lint e build.

Salva bozza e Conferma messaggio possono ora essere provati dal pannello online autenticato. La prova manuale autenticata di scrittura, rilettura e conferma resta da eseguire con l'operatore. Questo deploy non sposta il traffico dell'app, non distribuisce il lettore frontend e non produce una nuova Web App o AAB Android. `VITE_EDITORIAL_ADVICE_ENABLED` resta disattivato nella sorgente app. Prima di qualsiasi futura pubblicazione serviranno verifica del flusso autenticato, integrazione del ramo e qualifica della Home su Web e dispositivo.

Per interrompere la prova del pannello, ripristinare il precedente Hosting del pannello o rimuovere l'URL del tag dalla sua configurazione. Il traffico ordinario dell'API è rimasto invariato; non serve una modifica al servizio usato dall'app.
