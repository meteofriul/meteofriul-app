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

Il set verificato il 20 ottobre 2026 è
`runtime-writer-sets/play-services-20261020.json`. Aggiorna le attestazioni del
tag API Play e del job serale già distribuiti; non dichiara distribuita la nuova
correzione delle allerte FVG. Le prove sono in
`../cloud-operations/20261020-services-attestation/`. La copia originale locale
dell'archivio serale coincide con lo SHA-256 di Cloud Build, anche se l'oggetto
temporaneo cloud è stato rimosso.

## Set corrente per la release 0.1.15 / 300034

Il gate usa `runtime-writer-sets/play-services-notices-20261023.json`.
Include le allerte FVG del 20 ottobre e il job avvisi locali aggiornato il
21 ottobre (sorgente `18b88049`, Cloud Build `d7be8c19-3a33-4aef-ab98-6bf76c9794ca`).
Il job mattutino conserva la precedente immagine. I set storici restano immutati.
L'archivio locale del build del 21 ottobre coincide con lo SHA-256 di Cloud
Build; sorgenti backend e writer push coincidono con il commit attestato.

Dopo ogni deploy che cambia un writer, prima di preparare una AAB verificare
il nuovo digest, la provenienza Cloud Build e il codice TTL nell'archivio
sorgente. Aggiungere un nuovo set immutabile e aggiornare il percorso predefinito
del gate. Un digest diverso non autorizza a ignorare il controllo: occorrono
prima le prove del deploy, poi un nuovo audit in lettura. Non serve ridistribuire
un job soltanto per aggiornare questa attestazione.
