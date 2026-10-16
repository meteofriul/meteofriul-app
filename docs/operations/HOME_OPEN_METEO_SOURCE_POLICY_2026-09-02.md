# Hero Open-Meteo e fonti ufficiali separate — 2 settembre 2026

## Decisione e perimetro

Su richiesta dell'utente, temperatura, percepita, descrizione e icona della hero usano le condizioni attuali Open-Meteo. Non si combinano più temperatura di stazione OSMER e percepita modellistica.

Open-Meteo fornisce condizioni attuali **modellistiche**, non misure dirette di una stazione: [documentazione ufficiale](https://open-meteo.com/en/docs#current). L'app traduce il codice meteo in testo e icona e conserva l'adattamento solare giorno/notte.

- Anche i campi numerici del medesimo payload corrente (vento, umidità, pressione e precipitazioni) restano Open-Meteo, evitando che influenzino la semantica della hero con osservazioni di un'altra fonte.
- La stazione OSMER resta nel campo separato `station`, senza sovrascrivere i dati attuali. Il campo `official` conserva il bollettino.
- Il percorso previsionale e il bollettino ufficiale OSMER non cambiano. Nessuna modifica a testi, mappa strutturata o risoluzione territoriale del bollettino.
- Fonti, livelli, cache regionale, notifiche e scheduler delle allerte ufficiali restano invariati.
- Pollini CAMS, radar, evoluzione oraria a 48 ore e impaginazione della hero restano fuori dal cambiamento.

## Implementazione e indisponibilità

`backend/app/weather/current_engine.py` dichiara `primary_source: open_meteo`, `certainty: model` e la policy `open-meteo-current-v1`. La richiesta al modello usa il timeout della fonte primaria, non quello del supporto secondario.

Se il modello non risponde, il motore può riusare una precedente risposta Open-Meteo entro il limite stale già configurato; `cache.status` e `data_quality.status` sono marcati `stale`. La Home propaga lo stato e mostra «Dati non aggiornati» / «Dats no inzornats». Non si ripiega su stazione o testo OSMER per riempire la hero. Senza una risposta modellistica valida il dato corrente resta indisponibile.

Una percepita assente resta assente: non si copia la temperatura normale e non si converte un valore mancante in 0 °C. La stessa cautela vale per la temperatura principale.

## Cache e compatibilità

- La chiave backend include la nuova policy, così le risposte miste precedenti non sono riutilizzate come Open-Meteo.
- La cache Home passa da `weatherBootstrapCache:v2` a `weatherBootstrapCache:v3`. Nessuna cancellazione delle cache precedenti o delle preferenze.
- I prefetch Android che dichiarano la vecchia fonte corrente OSMER vengono ignorati dalla Home.
- La cache dedicata del bollettino mantiene la precedenza; la migrazione può ancora recuperare il testo ufficiale dalla vecchia v2, senza esporre quella cache alla hero.
- Il contratto API non aggiunge campi top-level obbligatori; il metadato di policy è interno a `source`.

## Verifica locale

- **92 test backend**: motore corrente, servizio, contratti API, previsioni e fonti/stato delle allerte.
- **260 test frontend su 14 file**: normalizzazione, hero IT/FUR, dati mancanti, stato stale, ciclo solare, cache, prefetch Android, bollettino e allerte.
- Scopri verificato separatamente: **194 test su 15 file**, 261 JSON validi e baseline del lotto 08 preservata.
- Lint completo e `git diff --check` superati. La suite frontend completa e le build già concluse non sono state ripetute.
- Nessuna chiamata live usata per dichiarare aggiornata la produzione; nessun commit, push, deploy o prova fisica Android.

## Distribuzione successiva

Questa modifica è locale. Al rilascio, aggiornare prima il backend e poi i client Web/Android, per evitare che un client con cache v3 continui a ricevere dati misti dal vecchio backend. Verificare il payload canonico: `current.primary_source` Open-Meteo, `forecast.primary_source` OSMER quando disponibile e fonte delle allerte invariata.
