# Evidenze Firestore TTL

Questa directory conserva l'evidenza verificabile e revisionata della bonifica
una tantum dei documenti push storici privi di `expires_at`.

Il file operativo atteso dal gate e'
`push-outbox-history.json`. Non creare un placeholder e non dichiarare
`missingOrInvalidExpiresAt: 0` per deduzione: va scritto soltanto dopo il
read-back Firestore e l'eventuale backfill/cleanup approvato. Il gate esegue
anche un nuovo read-back ad ogni controllo pre-AAB.

L'evidenza deve entrare in Git con una singola aggiunta e non puo' essere
modificata in seguito. Se serve una verifica nuova, creare un nuovo file e
aggiornare intenzionalmente il percorso usato dal gate; non riscrivere la
storia per farlo passare.

Le attestazioni storiche per singola immagine restano in
`runtime-writer-images/` e non vanno modificate. Il gate Play attuale usa
invece `runtime-writer-sets/`: un file append-only per il set effettivo
comprende API standard, tag API Play e quattro job raggiunti dagli Scheduler.
Ogni digest distinto ha prova Cloud Build, archivio sorgente e SHA-256 di
`backend/app/repositories/push.py`; non e' richiesta una sola immagine per
tutti i writer. Il file del set va aggiunto una volta a Git e mai riscritto.
