# Tolleranze ICON-2I: produttore aggiornato, nuova corsa attesa

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
