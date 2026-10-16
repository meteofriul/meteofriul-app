# Ripristino pilot locale — 6 settembre 2026

## Risultato verificato

Gli artefatti del 4 settembre erano nel worktree `f419`, non in `fb42`. Recuperati i quattro payload/report previsti dal launcher in `.dev-logs/weather-v1`, senza sovrascrivere file esistenti. Il database è stato trasferito tramite backup SQLite da connessione alla sorgente in sola lettura, non copiando un database WAL potenzialmente incoerente. `PRAGMA quick_check`: `ok`.

`start-local-weather-pilot.ps1 -CheckOnly -WeatherTestNow 2026-09-04T21:00:00Z` supera i controlli dei prerequisiti, binding dei report, catalogo e finestre temporali. Reader locale avviato sulla porta 8781 usando `serve_published_contract_v1.py` e il database recuperato, senza riavviare il backend esistente o modificare la produzione.

Verifiche HTTP: ICON latest, manifest ICON e family latest CAMS rispondono 200. Manifest ICON e family latest CAMS rispondono 304 alla richiesta condizionale ETag. I 112 test di `weatherV1Client`, `localWeatherV1Runtime` e `localWeatherV1Adapter` passano. Non è una misura della fluidità visiva sul dispositivo.

## Limiti e prossimo passaggio

- Sono snapshot storici del 4 settembre, non nuove acquisizioni: non presentarli come meteo aggiornato al 6 settembre. Il pilot usa esplicitamente il proprio orologio storico.
- Nessun telefono rilevato da ADB durante la verifica. Collegamento USB/reverse e prova fisica restano da ripetere.
- Il reader è un processo locale della sessione di lavoro, non un servizio persistente di produzione né un avvio automatico garantito al riavvio del PC.
- Acquisizione di nuove corse ICON/CAMS, pubblicazione controllata e schedulazione continuativa restano da completare/verificare. I runner di pubblicazione esistenti consumano artefatti già acquisiti e non vanno scambiati per downloader automatici.
- Nessuna modifica a codice applicativo, APK pubblico, credenziali, cloud o scheduling remoto.

Per proseguire: verificare il pilot ricollegato, quindi preparare una nuova acquisizione in directory distinta; non sovrascrivere questi artefatti di ripristino e non rimuovere l'orologio storico prima che entrambi i provider siano verificati secondo le rispettive finestre temporali.
