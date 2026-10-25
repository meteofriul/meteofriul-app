# Servizio HTTP FVG: avvio lento — correzione locale del 25 ottobre 2026

Stato: **correzione locale verificata, non distribuita** sul ramo
`codex/weather-http-startup`, da main `0ed41767ff4b21668947ece4575fe9f389a54f1d`.
Commit e promozione tramite PR/CI autorizzati dal proprietario il 25 ottobre;
esito remoto ancora da registrare. Nessun deploy, nuova AAB o installazione.
Sponsor disattivati. Controllo Eventi del 26 ottobre alle 05:00 italiane mantenuto.
Il lavoro non committato sul monitor sintesi resta nel suo worktree separato.

## Problema accertato

Il 25 ottobre, gli avvisi locali delle **12:00 e 15:00 Europe/Rome** hanno
rifiutato tutti i 12 gruppi: 24 record `source_timeout`, zero valutazioni e zero
tentativi di invio nelle due esecuzioni. Non è un problema delle tolleranze;
non possiamo concludere che in quelle finestre non vi fossero rischi.

`latest.json` FVG ha risposto in 90,00 s (504) e 61,61 s (200) a mezzogiorno;
85,86 s e 55,93 s (200) alle 15. Il consumatore attende 30 s per ciascuno dei
due tentativi. Entrambe le sequenze coincidono con l’avvio di una nuova istanza
HTTP. Le risposte 200 successive arrivano quindi quando il job ha già rinunciato.
[Evidenza sanitizzata](evidence/weather-http-startup-20261025/incident-summary.json).

Il percorso iniziale di `cloud_reader.py`, identico fra main e la sorgente della
fase 01 distribuita, costruisce un lettore per tutti i prodotti. Prima della
prima risposta ICON verifica anche CAMS core/pollini, inclusi i run precedenti:
sei manifest da 215 comuni e 1.290 letture separate di metadati. Il lock globale
può inoltre trattenere le altre richieste durante tale inizializzazione.
Questo lavoro superfluo è riprodotto localmente; non abbiamo un profilo temporale
cloud di ciascuna fase per attribuirle separatamente gli 85–90 secondi osservati.

## Correzione

- Inizializzazione su richiesta per due gruppi indipendenti: ICON e famiglia
  CAMS. Core e pollini continuano a condividere una vista atomica verificata.
- Cache e lock separati: la richiesta ICON non attende il lock o l’inizializzazione
  CAMS nei casi locali verificati. Il lock globale protegge solo la creazione del
  contenitore dei lettori. Questo non equivale all’isolamento dei processi cloud.
- Per ciascun manifest si legge in blocco l’elenco dei metadati nella sola
  directory immutabile dei comuni. Il risultato resta limitato a 216 elementi,
  con elenco dei 215 attesi, dimensioni, hash, generazioni e formato verificati.
  Nessun payload comunale viene scaricato anticipatamente.
- Un elenco incompleto, un errore di pagina o metadati invalidi vengono rifiutati
  senza inserire risultati parziali nella cache. La lettura del payload conserva
  verifica del suo hash e vincolo alla generazione Storage.
- Nessuna modifica al validatore dei run pubblicati, alle revoche, ai sidecar,
  al contratto JSON, alle soglie, ai timeout degli avvisi o agli orari.

## Verifiche locali

**91 test distinti superati**, inclusi 18 nuovi casi di regressione. Coperti:
lettura a freddo/calda, concorrenza ICON/CAMS, famiglia CAMS indivisibile, dati
mancanti/corrotti, errori durante l’elenco, revoche, oggetti non pubblicati,
sidecar delle tolleranze, CORS, gzip, ETag/304 e HEAD.

La prima esecuzione bloccava anche il loopback, impedendo 15 test HTTP esistenti
(39 asserzioni/subtest falliti). Ripetuti con sole connessioni locali consentite:
35/35 test HTTP/avvio superati, rete esterna e DNS esterno bloccati. Le altre
regressioni già superate non sono state ripetute senza motivo.
[Elenco, hash dei sorgenti e limiti](evidence/weather-http-startup-20261025/verification.json).

Confronto su fixture completa, stessi dati, corsa attiva e precedente:

| Prima risposta ICON | Main | Candidato |
| --- | ---: | ---: |
| Operazioni Storage | 1.310 | 8 |
| Operazioni relative a CAMS | 874 | 0 |
| Payload comunali scaricati | 0 | 0 |
| Risposta | HTTP 200 | HTTP 200, stessi byte/hash |

Le 8 operazioni comprendono 2 elenchi paginabili: non sono una garanzia del
numero esatto di richieste HTTP sul servizio reale, né una misura della sua
latenza. La durata sul PC non viene usata come promessa sui tempi cloud.
[Confronto riproducibile e hash](evidence/weather-http-startup-20261025/cold-read-comparison.json).

Python locale 3.13; SDK google-cloud-storage locale 3.15.0, immagine esistente
vincolata a 3.13.1. Non è stata costruita o provata una nuova immagine: il controllo
con le dipendenze esatte del container e la misura a freddo cloud restano aperti.

### Revisione mirata dopo il chiarimento del proprietario

Il perimetro del codice resta in due file: `cloud_reader.py` e l’operazione di
sola lettura dei metadati in `local_pipeline/gcs_object_store.py`. Quest’ultima
è richiamata solo dal lettore HTTP. Nessun job, produttore, scheduler, monitor,
soglia di valutazione, selezione dei destinatari o codice dell’app è modificato.
Il lavoro sul monitor delle sintesi rimane in un altro worktree.

La revisione ha aggiunto due regressioni sulla funzione `build_reader` usata
dal servizio reale, con Storage simulato e rete/DNS bloccati:

- creare il lettore non deve accedere ai dati; la prima richiesta ICON legge
  solo ICON, la successiva CAMS legge solo la famiglia CAMS;
- con indice ICON assente, CAMS deve restare leggibile; l’errore è restituito
  soltanto quando viene richiesto ICON.

Gli stessi due test sul codice main `0ed41767` falliscono perché rilevano le
letture del prodotto non richiesto. Sulla patch passano, insieme agli altri 16
test della suite di avvio. Non è una nuova prova cloud o una simulazione di
notifiche. I 73 test distinti delle altre suite già verificati restano validi:
il codice applicativo non è cambiato durante questa revisione.
[Esito della revisione e riproduzione su main](evidence/weather-http-startup-20261025/review-verification.json).

La CI esistente include ora anche le suite `test_cloud_reader*.py` e
`test_gcs_object_store.py`. Nessun nuovo workflow o trigger: è un passo locale
al runner GitHub del job backend, senza accessi al cloud meteo né invii.

## Applicazione e rollback, ancora da autorizzare

### Precisazione sull’indipendenza richiesta dal proprietario

Ricontrollo del 25 ottobre su configurazioni cloud già acquisite alle 15:25 e
sulla configurazione HTTP letta alle 15:52 italiane; nessuna nuova esecuzione.

| Componente | Evidenza e limite |
| --- | --- |
| Acquisizione ICON FVG e CAMS | Job distinti, `WEATHER_PROVIDER=icon` e `cams`; il worker esegue il solo ramo selezionato. |
| Avvisi locali e sintesi | Job distinti, ma tutti leggono ICON dallo stesso endpoint HTTP regionale. La dipendenza dalla previsione è necessaria; quella dall’inizializzazione CAMS no. |
| Servizio HTTP regionale | Risorse condivise fra ICON e CAMS. La patch separa l’inizializzazione e i lock, non i processi o le risorse cloud. |
| Aria e pollini | Restano nello stesso job e nella stessa famiglia CAMS atomica. Non sono due servizi completamente indipendenti. |
| Nazionale | Produttore ed endpoint separati dal servizio HTTP FVG. |

I test con CAMS lento o mancante dimostrano l’assenza del blocco logico diretto
su ICON nei casi provati. Non dimostrano isolamento da saturazione dei thread,
esaurimento memoria o arresto dell’istanza comune. Questo è un limite dichiarato
della prova, non un’autorizzazione ad ampliare il lavoro: la correzione rimane
nel lettore HTTP esistente. Nessuna nuova pipeline, accorpamento di job o
separazione delle risorse cloud è inclusa in questo intervento.

La causa immediata delle due esecuzioni fallite è confermata come timeout.
Non è stato dimostrato che il job CAMS fosse guasto o quale quota esatta della
latenza dipendesse da CAMS: il lavoro superfluo nel percorso HTTP è confermato
dal codice e dal confronto locale, non da un profilo temporale cloud completo.

Per dichiarare il recupero servono ancora tempi della prima risposta misurati
sulla candidata con dipendenze effettive del container, compatibilità delle
risposte e una successiva corsa ordinaria che completi le valutazioni previste.
Il numero di test locali non sostituisce queste evidenze.

Serve aggiornare **solo il servizio HTTP regionale**.
Il produttore ICON, il job degli avvisi, CAMS e il servizio nazionale non
richiedono questa modifica. Web e Android leggono lo stesso contratto: questa
correzione non richiede nuove AAB o pacchetti Web.

La configurazione effettiva, l’identità della revisione di rollback e le evidenze
operative sono conservate soltanto nella cartella locale ignorata da Git
`.tmp/weather-http-startup/`. Non vengono pubblicati identificativi delle risorse,
endpoint interni, configurazioni runtime o assegnazioni IAM. Nessuna estensione
dei permessi è preparata o applicata. Prima del passaggio va verificata la lettura
in elenco con l’identità della candidata.

Ordine successivo: revisione/commit e PR con CI; costruzione immagine vincolata
alla sorgente approvata; candidata HTTP senza traffico pubblico, verifica a
freddo di ICON e CAMS, vecchi client e sidecar; poi cambio del solo traffico HTTP
e verifica della successiva corsa ordinaria degli avvisi. Non avviare job o
notifiche manuali per misurare il recupero.

Rollback compatibile: conservare e ripristinare il traffico sulla revisione
precedente registrata nelle evidenze operative locali, che già legge i sidecar delle tolleranze.
Ripristina il comportamento precedente, inclusa la lentezza; non corregge da
solo la causa e non va eseguito automaticamente. Nessun dato pubblicato, schema
o oggetto immutabile viene riscritto. Nessuna prova su telefono eseguita ora.
