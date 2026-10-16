# Retention dei dispositivi push inattivi

Questa procedura riguarda esclusivamente `push_devices`. Non sostituisce il gate
degli outbox 30/14 giorni descritto in `FIRESTORE_PUSH_TTL_GATE.md`.

## Contratto applicativo

- `POST /api/push/devices/unregister` continua a cancellare subito e
  atomicamente il record dispositivo, l'eventuale indice
  `push_target_owners` e la voce nella capacita attiva.
- Un errore FCM terminale `fcm_token_invalid` disattiva il dispositivo, elimina
  subito il target in chiaro e lo rimuove da indice/capacita.
- Il solo record inattivo risultante riceve `expires_at = updated_at + 30 giorni`.
- Un nuovo `register` della stessa installazione riattiva il record e imposta
  `expires_at` a `null`; Firestore non applica TTL a campi assenti o null.
- Nessun dispositivo attivo puo contenere un timestamp `expires_at` valido.
- Motivi di disabilitazione diversi da `fcm_token_invalid` non ricevono
  automaticamente una scadenza: richiedono una decisione esplicita.

Il record inattivo non conserva piu `target_value` o il campo legacy `token`, ma
mantiene fino alla scadenza i relativi hash, l'identificativo installazione
hashato, piattaforma/versione/App Check, lingua, preferenze, Comune/localita
canonici, modalita e prova temporale/accuratezza della posizione, timestamp e
motivo della disabilitazione. Non contiene coordinate GPS.

I 30 giorni coincidono con la finestra tecnica massima gia adottata per
l'outbox delle allerte ufficiali. La cancellazione TTL Firestore e asincrona e
puo avvenire dopo il raggiungimento del timestamp, normalmente entro 24 ore.

## Audit e backfill

Lo script seguente e dry-run per impostazione predefinita e non stampa ID,
token, hash target, Comune o dati di posizione:

```powershell
.\scripts\audit-backfill-firestore-push-device-retention.ps1
```

Le letture e le mutazioni Firestore live richiedono PowerShell 7: il parser
mantiene `updateTime` come stringa ISO originale, senza la conversione automatica
in `DateTime` che puo perdere la precisione necessaria alla precondizione di
scrittura. I test puri restano compatibili anche con Windows PowerShell 5.1.

Controlla:

- policy univoca `push_devices.expires_at`, stato `ACTIVE`, offset zero;
- nessun timestamp TTL sui dispositivi attivi;
- solo record schema 2.x, `active=false`, motivo `fcm_token_invalid` nel
  backfill;
- target in chiaro gia vuoto;
- assenza del dispositivo da `push_target_owners` e dalle capacita attive;
- orizzonte esatto `updated_at + 30 giorni`;
- eventuali record legacy non classificabili, senza modificarli.

Per applicare un backfill serve una seconda esecuzione esplicita con il digest
del set mostrato dal dry-run. Il digest rende evidente qualsiasi variazione tra
controllo e scrittura; ogni documento usa inoltre la precondizione Firestore
`updateTime`, quindi una modifica concorrente annulla atomicamente l'operazione.

```powershell
.\scripts\audit-backfill-firestore-push-device-retention.ps1 `
  -ApplyBackfill `
  -ExpectedTargetSetSha256 <digest-del-dry-run>
```

La seconda esecuzione e idempotente: se non restano record senza scadenza non
scrive nulla. Non abilita o disabilita policy TTL.

## Bonifica separata del record legacy

Il record della vecchia applicazione non entra nel backfill TTL. Il dry-run
pubblica esclusivamente:

- numero dei candidati legacy;
- SHA-256 del set dei candidati;
- SHA-256 dell'insieme degli `updateTime`.

Non stampa percorso/ID documento, installation ID, token, hash target, campi
personali o lo stesso `updateTime` in chiaro. Un record entra nel set soltanto
se contemporaneamente:

- non contiene `schema_version`;
- non contiene `active`;
- non e' referenziato da `push_target_owners`;
- non compare in alcun `active_device_ids` della capacita push;
- possiede un `updateTime` Firestore valido per la precondizione.

La cancellazione e un hard-delete distinto, non implicito nel backfill. Richiede
lo switch e il digest esatto appena osservato:

```powershell
.\scripts\audit-backfill-firestore-push-device-retention.ps1 `
  -ApplyLegacyCleanup `
  -ExpectedLegacyTargetSetSha256 <legacyTargetSetSha256-del-dry-run>
```

La procedura corrente ammette esattamente un record legacy. Firestore esegue il
delete con `currentDocument.updateTime`: una registrazione, rotazione o altra
modifica concorrente fa fallire l'intera scrittura invece di cancellare uno
stato cambiato. Dopo il commit viene ripetuto il read-back e il comando fallisce
se resta anche un solo record legacy. Il percorso non modifica owner, capacita,
record schema 2.x o dispositivi attivi.

## Attivazione cloud futura

Solo dopo approvazione separata, deploy dello stesso nuovo digest backend su
API, job allerte ufficiali e job avvisi locali, e backfill verificato, la policy
si configura con:

```powershell
gcloud firestore fields ttls update expires_at `
  --collection-group=push_devices `
  --project=meteo-friul `
  --database='(default)' `
  --enable-ttl
```

Poi il dry-run deve restituire `ready=true`. La revisione runtime deve essere
attestata come per gli altri writer TTL, perche l'API cancella la scadenza in
riattivazione mentre entrambi i job possono impostarla dopo un token invalido.

## Stato verificato il 23 agosto 2026

- 8 record schema corrente attivi, nessuno con `expires_at`;
- 1 record inattivo `fcm_token_invalid`, target in chiaro gia rimosso e
  scadenza di 30 giorni applicata con digest e precondizione `updateTime`;
- il solo record legacy non classificato e non referenziato e' stato eliminato
  con l'hard-delete fail-closed separato;
- read-back successivo: zero record legacy e zero record da backfillare;
- policy TTL `push_devices.expires_at` ancora assente, da attivare soltanto dopo
  il deploy del nuovo writer su API e sui due job push.

La normale esecuzione di audit resta sempre read-only. Le due mutazioni sopra
sono state richieste esplicitamente tramite gli switch dedicati e validate da
un secondo read-back.

## Test locali

```powershell
C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile `
  -ExecutionPolicy Bypass `
  -File .\scripts\push-device-retention-audit.contract.tests.ps1

pwsh -NoProfile -File .\scripts\push-device-retention-audit.contract.tests.ps1
```

I test backend mirati devono includere repository, dispatcher ufficiale e
dispatcher locale. Prima di pubblicare la privacy servono infine: deploy,
backfill approvato, attivazione TTL, read-back verde e decisione sul record
legacy. Play Console e generazione AAB restano fuori da questa procedura.
