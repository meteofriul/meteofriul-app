# Cloud pilot: preflight 6 settembre 2026

## Stato: non attivato

Budget autorizzato: massimo 5 EUR/mese per il solo pilot. Nessuna modifica a beta, backend, DNS, scheduler o risorse esistenti; nessuna nuova risorsa fatturabile creata.

Inventario Google Cloud letto: `meteo-friul` è il progetto app esistente; gli altri tre progetti elencati non sono identificati come pilot. Non usarli implicitamente. È disponibile un account di fatturazione aperto, ma non è stato collegato alcun nuovo progetto.

Cloudflare `whoami`: account atteso `b74cf20dd75712b35313b69c191c97d5`, email Meteo Friûl confermata. Il CLI risolto da npx è Wrangler 4.129.0; segnala credenziali default cifrate, non il profilo nominato atteso nelle istruzioni workspace. Non sono state modificate credenziali/profili. Prima delle mutazioni va risolto esplicitamente questo disallineamento.

`wrangler r2 bucket list` fallisce con codice **10042**, "Please enable R2 through the Cloudflare Dashboard". Serve attivazione R2 dell'account prima di creare il bucket isolato previsto. Non richiedere chiavi o dati di pagamento in chat.

## Codice preparato, non ancora integrato nei job

`local_pipeline/s3_object_store.py`: adapter con client SDK iniettato, bucket dedicato con prefisso nome `meteofriul-pilot-`, namespace `pilot/`, limite 16 MiB per oggetto, creazione condizionale, CAS con ETag opaco, hash SHA-256 indipendente, lettura verificata e chiusura stream. Nessuna cancellazione né overwrite incondizionato. Errori remoti sanitizzati.

Sette test unitari superati su client simulato: non costituiscono prova di compatibilità reale R2 o pubblicazione cloud. Il vincolo nome è una difesa applicativa, non sostituisce credenziali ristrette al bucket.

## Gate ancora necessari

1. Attivazione R2, risoluzione profilo Wrangler, bucket e credenziali pilot limitate.
2. Test reali di scritture condizionali, timeout, conflitti e pubblicazione completa; integrazione adapter nei runner.
3. Stato e claim remoti durevoli, senza duplicare submission ADS in caso ambiguo.
4. Progetto Google dedicato, identità senza permessi beta, runtime Linux verificato. Docker non è disponibile nel PATH; WSL non risulta pronto all'esecuzione Linux.
5. Stima completa entro 5 EUR inclusi calcolo, attese CAMS, scheduler, build, storage, log, trasferimenti e imposte applicabili. Quote gratuite non assunte disponibili: Cloud Run le aggrega per billing account.
6. Limiti di esecuzione/retry, retention, accesso dati pilot e arresto operativo. Un avviso budget non garantisce un tetto assoluto.
7. Solo dopo questi gate, schedulazione e prova senza PC/USB. Il telefono continua con il reader locale del 6 settembre.

Fonti consultate: https://cloud.google.com/run/pricing ; https://developers.cloudflare.com/r2/pricing/ ; https://developers.cloudflare.com/r2/api/s3/api/ ; https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/put_object.html .
