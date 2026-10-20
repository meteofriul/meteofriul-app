# Tolleranze ICON-2I: produttore aggiornato, verifica nuova corsa bloccata

**Aggiornamento 20 ottobre:** la prima esecuzione ordinaria con il produttore nuovo
e fallita durante l'acquisizione. Nessuna nuova corsa FVG pubblicata; verifica
delle tolleranze incompleta e follow-up in pausa. Dettagli nell'esito in fondo.
Le sezioni datate 19 ottobre descrivono il deploy e il piano originario.

19 ottobre 2026. Il solo job `meteofriul-icon` è stato aggiornato con il
produttore della fase 03. **La verifica reale delle tolleranze è ancora
incompleta:** la corsa `20261019T120000Z` era già pubblicata prima del deploy.
Non è stata riscritta e non è stata avviata un'acquisizione manuale.

## Distribuzione verificata

- Immagine: `europe-west1-docker.pkg.dev/meteo-friul/meteofriul/weather-worker@sha256:b8719b7f26c355115ded47e282e19f8011ff270e0d0107a831526879155ac2f2`.
- Cloud Build: `7d127b81-6075-43f0-a938-2ba48aee623f`, SUCCESS. Suite locale: 198 test in
  1275.205 secondi, **197 passati e uno fallito** nell'attesa di 20 secondi
  del test di concorrenza CAMS. Lo stesso caso, invariato, è stato ripetuto
  con successo nel container Linux insieme a 65 verifiche mirate di tolleranze,
  checkpoint, sidecar, worker, lettore e campione Ciampac, senza rete.
  Nessuna soglia del test o del prodotto è stata allentata. Il limite di
  temporizzazione osservato nella suite completa Windows resta documentato.
- Sorgenti: BASE `8497e773b1613312bb952236d72c074e22a7b1c6` + patch congelate
  01, 02, 03; tutti i 180 file del contesto corrispondono a main
  `5e04343a27716c9c42a65d2a45aea0f628bbb9d8`. Nessun nuovo push Git.
- Modificata solo l'immagine del produttore: configurazione, identità,
  risorse e retry invariati; altri 12 job e
  11 scheduler invariati.
- Il job QA conserva `dry_run`, lettura sidecar abilitata e identità priva
  di permessi FCM. Nessun invio avviato e nessun job di invio aggiornato.

## App già installate

I due client storici (`2f02c8ba`, app ufficiale 0.1.14, e `8497e773`)
accettano tutti i 215 documenti FVG della corsa attuale. Verificati hash,
dimensioni e CORS Android. Dopo il deploy latest e manifest conservano gli
stessi byte; rilette anche tre località, senza modifiche.
Il servizio HTTP della fase 01 mantiene il 100% del traffico.

Verificati in sola lettura anche Milano, Canazei, Roma, Napoli, Palermo e
Cagliari, 73 ore ciascuna: entrambi i vecchi client accettano i dati nazionali;
manifest, indice e hash sono validi. È un campione, non una verifica dei 7.894
comuni. Il servizio e il produttore nazionale non sono stati aggiornati.

Il Galaxy A52 era collegato, ma non si ripete una prova visiva sui dati vecchi:
la precedente verifica sul dispositivo è documentata nella fase 01. Nessuna
build/installazione Android, nessun emulatore, nessuna AAB. **La lettura dalle
app della corsa prodotta dal codice nuovo resta da verificare.**

## Prossimo controllo autorizzato

Lo scheduler esistente partirà il **20 ottobre alle 06:00 UTC / 08:00 Europe/Rome**.
È attesa la corsa `20261020T000000Z`, se disponibile presso il fornitore.
Conservare gli oggetti immutabili precedenti e non forzare slot o identificativi.
Follow-up di questa chat `verifica-tolleranze-icon-sulla-nuova-corsa` attivo
alle 08:20 e alle 09:20 italiane del 20 ottobre, massimo due controlli:
si ferma al successo o a un problema che richiede decisione. La seconda
occasione serve se la pubblicazione è ancora in attesa. Nessun nuovo
scheduler cloud è stato creato; il follow-up è gestito dall'app Codex.

1. Confermare digest effettivo, esito del produttore, checkpoint schema 2,
   log `source_quality` e pubblicazione di una corsa maggiore di `20261019T120000Z`.
2. Eseguire `.tmp/verify_icon_phase3_http.py --name new-run-http --require-new`:
   215 documenti accettati dai lettori storici e sidecar validi, legati a
   hash, comune, corsa e ore. Non dichiarare riuscita la verifica se manca la nuova corsa.
3. Eseguire una sola volta `.tmp/execute_icon_phase3_qa.py`; è vincolato a
   nuova corsa verificata e `dry_run`. Leggere i risultati con
   `.tmp/read_icon_phase3_results.py`, senza attivare gli invii.
4. Confrontare baseline e candidato sugli stessi dati, punti e istante;
   registrare tolleranze usate, non valutabili per causa, candidati e zero
   invii/prenotazioni. Se i punti reali non usano tolleranze, dichiararlo e
   integrare solo una valutazione locale dei dati salvati.
5. Verificare nuovamente letture nazionali e, se ancora collegato, app sul
   telefono senza installazioni né cambio delle preferenze di avviso.

## Rollback compatibile

Immagine già verificata nel registro:
`europe-west1-docker.pkg.dev/meteo-friul/meteofriul/weather-worker@sha256:3be1d207321e8ea0cee07466c9ac29fcec230ba4e10b3267647fa8f0cb2315a6`.
Per un ripristino necessario aggiornare solo l'immagine di `meteofriul-icon`
a questo digest, mantenendo ambiente e scheduler. Non tornare al vecchio
lettore rigido, non cancellare checkpoint e non riscrivere corse pubblicate.
Il rollback non è stato eseguito: è pronto e la compatibilità è coperta dai test.

Evidenze: [manifest degli hash](evidence/icon-tolerance-phase3-2026-10-19/SHA256SUMS.txt).
Log e risposte complete: `.tmp/icon-tolerance-phase3-20261019` del workspace canonico.
Il confronto sulla nuova corsa e la decisione sugli invii restano aperti.


## Esito del controllo del 20 ottobre 2026

**Verifica incompleta per errore del produttore; non e un esito positivo delle
nuove tolleranze.** Controlli successivi alle 06:00 UTC, in sola lettura su
`meteo-friul`, regione `europe-west1`, account `meteofriul@gmail.com`.

### Esecuzione ordinaria e punto di arresto

- Esecuzione `meteofriul-icon-x26c6`, creata alle `06:00:45.240739Z`
  (08:00 italiane), conclusa alle `06:03:42.916705Z` con exit 1.
- Digest effettivo uguale a quello previsto dal deploy del 19 ottobre:
  `sha256:b8719b7f26c355115ded47e282e19f8011ff270e0d0107a831526879155ac2f2`.
- Il log seleziona `2026102000`, 14 campi, 73 ore e 215 comuni. Alle
  `06:02:28Z` l'acquisizione fallisce con `ValueError`.
- Esito persistito: `manual_review`, motivo `unexpected_internal_failure`,
  `retryable: false`. I retry del container rileggono l'esito terminale;
  non risulta una seconda acquisizione nei log di questa esecuzione.
- Il log espone `cloud_worker.py`, `_run_icon_result`, riga 524, ma omette
  deliberatamente il messaggio dell'eccezione. Nel sorgente congelato questa
  riga chiama `run_outputs`: **la causa interna non e ancora identificata**.
- Nel prefisso `pilot/state/dispatch/icon/20261020-am` sono presenti lease,
  marcatore di acquisizione ed esito; manca `checkpoint.json.gz`. Nessun
  evento `source_quality` nei log letti per l'esecuzione. Schema 2 e nuovi
  metadati delle tolleranze quindi non verificabili. Lo `schema_version: 1`
  dell'esito terminale identifica la busta dell'esito, non un checkpoint.

### Verifica HTTP, QA e confronto

`latest` FVG e ancora `20261019T120000Z`, revisione 83. E stato eseguito
`.tmp/verify_icon_phase3_http.py --name new-run-http --require-new`:
si e fermato correttamente con
`New source run is not published yet: do not execute QA`.
La directory `new-run-http` non contiene `result.json` e non e un'evidenza
completa. Non sono stati convalidati 215 documenti e sidecar di una nuova corsa.

`execution-submission.json` assente: il QA non e stato avviato e gli script di
esecuzione/lettura dei risultati QA non sono stati eseguiti. Il confronto
baseline/candidato, i candidati cambiati, le tolleranze usate, i non valutabili
per causa e i denominatori restano **non misurati**, non valori zero.
Una valutazione supplementare sui dati vecchi privi di metadati non colmerebbe
questa lacuna. Zero invii e zero prenotazioni attribuibili al QA perche il QA
non e stato sottoposto; non e un'affermazione sugli altri job operativi.

### Continuita delle letture delle app

- FVG: riutilizzata la verifica completa dei due lettori storici `2f02c8ba`
  e `8497e773` sui 215 documenti del 19 ottobre, dopo avere confermato che
  l'hash del manifest immutabile e identico. Riletti via HTTP Pordenone,
  Udine e Fontanafredda: hash, dimensioni e CORS Android validi. La lettura
  della corsa precedente resta funzionante; **manca l'aggiornamento FVG**.
- Nazionale: riletti Milano, Canazei, Roma, Napoli, Palermo e Cagliari sulla
  nuova corsa nazionale `20261020T000000Z`, 73 ore per localita. Entrambi i
  client storici accettano i sei casi; manifest, indice, hash e CORS validi.
  E un campione di sei comuni, non l'intero Paese. Il risultato nazionale
  non sostituisce la verifica della nuova corsa regionale mancante.
- `adb devices -l` non mostra dispositivi collegati. Nessuna verifica visiva
  sul Galaxy in questo controllo, nessuna installazione o cambio preferenze.

### Decisione e limiti

Il follow-up `verifica-tolleranze-icon-sulla-nuova-corsa` e stato messo in
**PAUSA** dopo il riscontro dell'errore, come autorizzato. Serve identificare
la causa del `ValueError` e concordare il recupero prima di ripetere il controllo
sulla nuova corsa. Il rollback compatibile resta disponibile ma non eseguito.
Nessun nuovo deploy, acquisizione manuale, modifica agli scheduler o agli
oggetti immutabili; nessuna AAB, emulatore, push Git o attivazione degli invii.

Evidenze del controllo: [riepilogo](evidence/icon-tolerance-phase3-2026-10-20/verification-summary.json)
e [manifest degli hash](evidence/icon-tolerance-phase3-2026-10-20/SHA256SUMS.txt).
Risposte e log completi rimangono in `.tmp/icon-tolerance-phase3-20261019`
nel workspace canonico. Verbale ed evidenze salvati localmente, senza commit
ne push in questo controllo.


## Diagnosi locale del 20 ottobre 2026

Dopo il controllo, il proprietario ha autorizzato di approfondire il blocco.
**Confermato un difetto deterministico nel codice distribuito**, senza rete,
nuovi dati del fornitore o modifiche al produttore:

1. `run_pilot.py:273-276`, `Decoder.decode`, aggiunge sempre `packingError`
   ai metadati di ogni messaggio, impostandolo a `None` se non disponibile.
2. `run_pilot.py:665-667`, `_validate_field_checkpoint`, accetta solo le
   chiavi precedenti (`META_KEYS`, piu il quantum per gli accumuli):
   `packingError` non e ammesso. Solleva `ValueError("Checkpoint metadata is invalid")`.
3. Il flusso ordinario attiva sempre il checkpoint locale dei campi.
   `_save_field_checkpoint` valida prima di scrivere; il salvataggio del
   primo campo completo, `T_2M`, quindi non puo riuscire. L'errore avviene
   prima del log di completamento del campo e prima della derivazione
   delle tolleranze o del checkpoint cloud schema 2.

Il file congelato del deploy corrisponde al commit verificato `5e04343a`
e al file attuale di `main` (SHA-256 normalizzato
`7900ee52879eb3777832419f76c712f27542eeb67950bf6aca5defc04be1c2ca`).
L'aggiunta di `packingError` risale a `d855e53d` e non ha aggiornato il
validatore del checkpoint dei campi. Questo checkpoint locale e distinto
dal checkpoint cloud schema 2 del piano di rollout.

### Riproduzione e copertura mancante

- Per tutti i 14 campi, il formato precedente viene accettato; aggiungendo
  `packingError` con valore finito oppure `None` si ottengono 28 rifiuti
  con lo stesso messaggio di errore.
- Eseguito anche `Decoder.decode` originale, senza modificarlo, collegato
  a un'interfaccia ecCodes sintetica: 73 messaggi per 215 punti, sia con
  `packingError` disponibile sia assente. In entrambi i casi il percorso
  reale decoder → salvataggio fallisce prima della scrittura.
- Connessioni socket disabilitate durante la riproduzione; nessuna libreria
  installata, nessun download GRIB, nessuna acquisizione reale.
- I test precedenti del checkpoint sostituiscono il decoder con
  `FakeCheckpointDecoder`, che usa una fixture di metadati senza
  `packingError`: non coprivano l'interfaccia tra il decoder aggiornato
  e il validatore. Non e un risultato dipendente dalle soglie meteo.

**Limite del riscontro cloud:** il dettaglio interno dell'eccezione delle
08:02 e nascosto dai log esistenti. La diagnostica conserva la riga esterna
`cloud_worker.py:524`, perche non include `run_pilot.py` tra i file di cui
espone la posizione e non ammette quel messaggio nel vocabolario sicuro.
Il difetto locale e certo ed e coerente con il punto e la tempistica del
fallimento; non si dichiara recuperato un traceback cloud che non esiste.
Non e necessario ipotizzare un ritardo del fornitore per riprodurre il blocco.

### Correzione da preparare

Allineare il contratto dei metadati del checkpoint a `packingError`,
convalidandone il valore e mantenendo compatibili i checkpoint precedenti
che non lo contengono. Aggiungere una regressione che attraversi il decoder
reale e il salvataggio, inclusi metadato assente, finito e invalido.
Rendere leggibile questa causa locale con diagnostica sicura senza esporre
risposte o credenziali del fornitore. Dopo la correzione serve un deploy
separatamente autorizzato e una nuova verifica: aspettare soltanto non elimina
il difetto. L'esito terminale dello slot fallito non e stato cancellato o alterato.

Questa diagnosi non ha applicato correzioni ai sorgenti, effettuato deploy,
riavviato il job o eseguito QA/invii. Il follow-up resta in pausa.
Evidenze: [risultato della riproduzione](evidence/icon-tolerance-phase3-2026-10-20/packing-error-diagnosis.json)
e [script locale](evidence/icon-tolerance-phase3-2026-10-20/diagnose_icon_phase3_checkpoint.py).


## Correzione locale preparata il 20 ottobre 2026

Ramo `codex/icon2i-checkpoint-metadata`, dalla base `main`
`bf304281aa9851369687c2dd646b8bd473c0b23d`. **Correzione verificata localmente,
non distribuita.** Il produttore cloud mantiene il difetto finche non viene
aggiornata la sua immagine; non e stata completata la prova sulla nuova corsa.

- Il checkpoint locale accetta `packingError` come unica chiave opzionale:
  ammette `None` e numeri finiti non negativi, incluso lo zero autentico.
  Chiavi sconosciute e valori invalidi nel checkpoint restano rifiutati.
- I checkpoint precedenti, senza la chiave, sono letti senza riscriverli
  o trasformare l'assenza del metadato in zero. Schema locale invariato.
- Il decoder conserva come indisponibile il metadato opzionale assente,
  negativo, booleano, testuale, non finito o non rappresentabile. I dati
  meteo restano invariati; una guardia che richiede quel metadato continua
  a rifiutare la tolleranza se il metadato non e disponibile.
- La diagnostica ammette due messaggi locali controllati e conserva la
  posizione interna in `run_pilot.py`, senza esporre URL, risposte o segreti.
- La fixture del decoder nei vecchi test ora include il nuovo metadato.
  Una regressione aggiuntiva usa il decoder originale e attraversa
  salvataggio/rilettura per tutti i 14 campi, 73 ore e tre stati del metadato.

### Esito delle verifiche

Prima della correzione: cinque nuovi metodi di test riproducono i difetti,
con 5 fallimenti e 44 errori nei sottocasi. Dopo la correzione:
**123 casi distinti hanno un esito finale positivo**, nessuno saltato,
con connessioni socket bloccate. Sono coperti acquisizione simulata,
checkpoint locali, ripresa senza download, dati invalidi, diagnostica,
tolleranze, qualita della sorgente e checkpoint cloud 1/2.

La prima suite da 123 casi ha superato 122 metodi e rilevato un problema
nel nuovo test diagnostico: `unittest.assertRaises` cancella il traceback
prima dell'ispezione. Il test e stato corretto per verificare il log realmente
emesso durante l'errore; la suite diagnostica di 10 casi e stata ripetuta
con successo. Nessuna modifica al codice produttivo tra le due esecuzioni;
non vengono presentate come un'unica suite da 133 casi distinti.

L'interfaccia ecCodes e simulata: il decoder Python e reale, ma questa prova
non e una decodifica di nuovi GRIB del fornitore. Non sono state installate
librerie o avviate acquisizioni. Restano necessarie la build dell'immagine,
il deploy autorizzato del solo produttore e la verifica sulla prima corsa
nuova, con 215 letture legacy, sidecar, checkpoint schema 2 e QA senza invii.
Non cancellare l'esito terminale dello slot fallito e non riscrivere corse
immutabili. Nessun cambiamento alle soglie, agli exit code, agli scheduler,
alle app o agli invii; follow-up ancora in pausa.

Risultati, provenienza e hash dei quattro sorgenti:
[correzione locale](evidence/icon-tolerance-phase3-2026-10-20/local-fix-summary.json).
Log della [suite iniziale](evidence/icon-tolerance-phase3-2026-10-20/local-fix-suite.log)
e della [verifica diagnostica finale](evidence/icon-tolerance-phase3-2026-10-20/local-fix-diagnostics-final.log).
