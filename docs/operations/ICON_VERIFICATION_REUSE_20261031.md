# Riuso della verifica FVG — 31 ottobre 2026

L'ottimizzazione del ramo `codex/icon-automatic-recovery-20261031` elimina due
letture complete ripetute durante un'esecuzione di recupero FVG che trova
già pubblicato il ciclo atteso. Il test usa tutti i 215 documenti comunali
contrattuali: **645 → 215 letture dei corpi JSON, circa il 67% in meno**.
Le letture leggere di puntatore e manifest restano presenti. Questa misura
non equivale a una riduzione del 67% del costo complessivo del job.

## Regole preservate

- La prova completa vale solo nella stessa invocazione e per la generazione
  esatta del puntatore verificato. Non viene salvata una nuova cache persistente.
- `read_verified_latest_snapshot` restituisce documento, manifest ed ETag
  della fotografia originale, evitando di associare un vecchio controllo a
  una generazione letta dopo la verifica.
- Ogni riuso conferma la generazione con `read_latest_if_etag`. Se cambia,
  serve una verifica completa; una seconda mutazione durante quella verifica
  interrompe l'esito positivo, senza un ciclo illimitato di tentativi.
- Rollback, revoca di un ciclo, manifest o documenti corrotti restano errori
  verificabili. La scadenza viene valutata rispetto all'ora corrente, non al
  momento in cui è stata memorizzata la prova.
- Ogni tentativo di pubblicazione elimina la prova prima e dopo l'operazione,
  anche se fallisce o non aggiorna il puntatore. La verifica finale rilegge
  integralmente i documenti pubblicati.
- Una nuova invocazione riparte dalla verifica completa. Il percorso legacy
  e l'attivazione disabilitata per default rimangono invariati.

Il riuso si appoggia al contratto esistente di oggetti immutabili e letture
legate alla generazione. Una modifica amministrativa diretta a un payload,
senza cambiare il puntatore e dopo la verifica iniziale, non è riletta durante
lo stesso caso senza aggiornamento: viene controllata alla nuova invocazione
o alla rilettura completa dopo pubblicazione. Non è una sorveglianza continua
di ogni oggetto e non sostituisce il monitor indipendente della freschezza.

## Verifica e consegna

La [ricevuta indipendente](evidence/ICON_VERIFICATION_REUSE_20261031.json)
riporta comandi, conteggi e hash finali. Copre l'intera regressione dei worker,
stato di recupero, checkpoint, pubblicazione e Storage, oltre al publisher.
La suite completa supera **282 test in 972,416 secondi**: 254 nei dodici
moduli principali e 28 del publisher. I 38 test eseguiti anche con `python -S`
sono già compresi nel totale e non si sommano. Dopo la prova è stato rimosso
soltanto un LF finale superfluo da un file di test, senza modifiche semantiche.
I test dell'identità della fotografia e del recupero puro sono verificati
anche senza dipendenze cloud e inclusi nella CI esistente. Non vengono
aggiunti trigger, dipendenze o job GitHub pianificati.

Le prove sono locali con store di test e documenti contrattuali, non un
benchmark GCS o un ciclo operativo Cloud Run. La CI remota va consultata
sul commit della PR; non è attestata dalla ricevuta delle prove locali.

Il proprietario ha autorizzato salvataggio, push e PR di questo lavoro.
Il [ramo del candidato](https://github.com/meteofriul/meteofriul-app/tree/codex/icon-automatic-recovery-20261031)
comprende anche il [recupero automatico](ICON_AUTOMATIC_RECOVERY_20261031.md),
l'[audit dei costi](JOBS_COST_AUDIT_20261031.md) e la
[ricognizione degli altri servizi](APP_SERVICE_REPORT_COVERAGE_20261031.md).
La promozione in main e l'attivazione cloud restano separate. Nessuna immagine,
pianificazione o app distribuita viene aggiornata da questa consegna.
