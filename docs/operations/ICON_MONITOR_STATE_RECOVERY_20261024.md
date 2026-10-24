# Recupero del salvataggio di stato del monitor ICON — 24 ottobre 2026

Stato: correzione locale sul ramo `codex/icon-monitor-state-recovery`, da main `eb109518`. Separata dalla correzione Eventi. Revisione e suite locale ripetuta completate per il commit e la promozione autorizzati il 24 ottobre. Deploy e corsa ordinaria da attestare separatamente.

## Problema

La corsa monitor delle 10:10 aveva verificato previsioni FVG e nazionali aggiornate, poi ha terminato con `monitor state commit uncertain` sul prodotto nazionale. L'adattatore non distingueva il codice HTTP e non recuperava i fallimenti temporanei di salvataggio; il recupero della valutazione iniziale non copriva tutte le transizioni della coda delle metriche.

Il vecchio log non conserva lo status HTTP. La lettura dei log di audit Storage nell'intervallo del guasto non ha restituito errori: non prova assenza di errori, perché copertura e abilitazione di quei log non sono attestate. Non attribuire quindi il caso osservato a un 429, timeout o problema IAM specifico.

## Correzione

Il solo adattatore di stato ora:

1. Mantiene sempre la stessa precondizione `ifGenerationMatch` e gli stessi byte del valore richiesto.
2. Dopo timeout, errore di trasporto temporaneo, HTTP 408/429/5xx rilegge lo stato. Se trova esattamente il valore scritto con una nuova generation, conferma il salvataggio senza ripeterlo.
3. Se lo stato è diverso e più recente, restituisce il conflitto al controllo già esistente, senza sovrascriverlo.
4. Se la generation non è cambiata, ritenta entro un massimo di tre tentativi, con attese di 1 e 2 secondi e rispettando il budget originario.
5. Conserva gli errori permanenti e quelli non verificabili come errori; il log espone lo status HTTP, senza corpo di risposta, URL privati o credenziali.

La coda delle metriche mantiene proprietà, deduplicazione e regole di conferma esistenti. Schema dello stato, metriche, scheduler, soglie e dati meteo non cambiano. Nessun aumento del timeout complessivo. La rilettura non verificabile non viene presentata come successo.

Riferimenti tecnici: Google documenta i retry condizionati alle precondizioni e gli errori temporanei in [Retry strategy](https://docs.cloud.google.com/storage/docs/retry-strategy); il limite di scritture sullo stesso oggetto è descritto in [Cloud Storage quotas](https://docs.cloud.google.com/storage/quotas#objects). Questi riferimenti giustificano l'attesa e le precondizioni; non dimostrano la causa HTTP del caso osservato.

## Verifiche locali

`python -m unittest discover -s . -p 'test_freshness_monitor*.py'`, dalla cartella `experiments/weather_autonomy`: **90 test eseguiti, 89 superati e 1 saltato**. Il controllo saltato richiede `PROMTOOL`, non configurato; le policy di monitoraggio non sono state modificate. Nessuna installazione eseguita.

Le nuove regressioni simulano errori transitori e permanenti, risposta persa dopo scrittura riuscita, concorrenza, lettura di conferma indisponibile, limite di tentativi e budget. Esercitano tutti e sette i salvataggi della valutazione e delle tre metriche: dopo il recupero ogni metrica è scritta una sola volta e una riesecuzione non la duplica.

Lo stesso test delle sette transizioni, contro il codice precedente su main, fallisce in **12 sottocasi**; il candidato li supera. Test completamente offline, nessuna scrittura su Storage o Monitoring.

## Evidenze e passo successivo

Evidenza sintetica: `evidence/icon-monitor-state-recovery-20261024/checks.json`. Log privati nella cartella locale ignorata `.tmp/icon-monitor-state-recovery-20261024` della radice canonica.

Dopo revisione: commit separato, integrazione su main e CI, quindi eventuale deploy autorizzato del solo monitor. Controllare una corsa ordinaria, le metriche confermate per entrambi i prodotti e l'assenza di errori di persistenza; un job verde da solo non basta. Il precedente monitor resta compatibile come rollback, con la lacuna di recupero originaria. Non serve ridistribuire il produttore ICON.

Nessuna modifica alla sintesi mattutina, alle notifiche, all'app o agli sponsor. Nella fase locale descritta non sono stati eseguiti job cloud manuali, invii, push, deploy, AAB o installazioni. Il successivo push/CI e deploy dei soli Eventi e monitor ICON sono autorizzati dal proprietario; l’esito operativo resta da registrare.
