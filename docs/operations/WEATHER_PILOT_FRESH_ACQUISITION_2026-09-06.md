# Pilot: nuove acquisizioni e limite cloud — 6 settembre 2026

## Vincoli

- Autorizzato dall'utente un tetto di **5 EUR/mese**, esclusivamente per il pilot.
- La beta chiusa, il relativo APK e i servizi condivisi non devono essere modificati.
- Nessuna risorsa cloud a pagamento è stata creata. Il budget non costituisce prova di un limite tecnico di spesa.
- Non usare il progetto Google Cloud `meteo-friul` per attivare questa pipeline: non è stato individuato un progetto pilot dedicato.

## Nuovi dati verificati

Artefatti separati in `.dev-logs/weather-v1/fresh-20260906/`; gli snapshot storici non sono stati sovrascritti.

- ICON: corsa `2026-09-06T00:00:00Z`, 215 Comuni, 73 istanti, 14 campi, 1022 messaggi senza duplicati; download 1.143.400.499 byte. Payload validato.
- CAMS Europe: richiesta del 6 settembre accettata, ripresa con lo stesso job e completata; GRIB decodificato con il piano verificato. Nessuna credenziale riportata nei documenti.
- Pubblicazione nel nuovo `objects.sqlite3` conclusa: `icon2i`, `cams_europe`, `cams_europe_pollen` risultano `published` per `20260906T000000Z`.
- Reader read-only separato sulla porta 8782. Il reader storico 8781 non è stato sostituito.
- Due test live frontend superati contro 8782 con orologio reale: lettura aria/pollini e aggiornamento CAMS differito attraverso il runtime.
- 49 test scheduler/reader/pubblicazione superati. Nove test sulla misura di memoria superati dopo l'aggiunta del supporto `/proc/self/status` Linux; non equivalgono a una prova reale del container Linux.

## Ancora da chiudere

### Aggiornamento telefono, ore 15:54

Samsung OWNER_DEVICE_SERIAL rilevato. Compilato e installato con `install -r` esclusivamente `com.meteofriul.app.localpilot`, senza orologio simulato. SHA256 APK: `fa37f9d25d0fe5914b0fed8b7d4a2c419eb81d0891c9c272a49fa80a1ce5e2c7`. Due test live ripetuti e superati.

Il reverse telefono 8781 → host 8782 non funziona con la verifica Host del reader: la porta deve corrispondere. Sostituito quindi il solo reader storico sulla porta 8781 con il database nuovo, mantenendo intatto il database storico. Reverse definitivo 8781 → 8781. Verifica visiva: Pordenone 32 °C, ICON e CAMS corsa 06/09/26 00:00 UTC, dato 13:00 UTC, origine rete. Screenshot `.dev-logs/local-weather-pilot/phone-fresh-20260906.png`. La dipendenza PC/USB rimane; nessuna modifica alla beta.

- Il telefono era assente al controllo delle 15:44; aggiornamento e verifica successivi descritti sopra.
- Il reader rimane locale e dipende dal PC. Non è un servizio cloud persistente.
- Acquisizione, pubblicazione e test sono stati eseguiti manualmente: non dimostrano una schedulazione autonoma.
- Servono ambiente isolato, verifica dei costi e limiti operativi, runtime Linux verificato, storage remoto e schedulazione con gestione errori/ultimo dato valido prima di dichiarare concluso il punto 1.
- Non presentare il limite mensile come garantito da semplici avvisi di budget.
