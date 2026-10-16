# Registro cutover notifiche Play

Questa directory contiene evidenze operative append-only. Un'evidenza non è
una configurazione e non autorizza alcuna modifica cloud. Sono previsti tre
tipi distinti di record:

- revoca completa dei token Firebase App Check Debug;
- retarget controllato del tag Cloud Run su una nuova revisione di sola
  configurazione, mantenendo l'immagine backend immutabile dell'AAB;
- bonifica controllata dello stato push legacy, eseguita soltanto dopo la
  prima registrazione valida dal track Play e seguita da un read-back.

Ogni verifica crea un **nuovo** file sotto `evidence/`, con nome UTC ordinabile:

`YYYYMMDDTHHMMSSZ-debug-tokens-revoked.json`

oppure:

`YYYYMMDDTHHMMSSZ-legacy-push-cleanup-verified.json`

oppure:

`YYYYMMDDTHHMMSSZ-runtime-revision-retarget-verified.json`

Non modificare, rinominare o cancellare un'evidenza già committata. Se viene
creato in seguito un altro token Debug, revocarlo e aggiungere un nuovo record;
la sua TTL riparte dalla nuova `revokedAtUtc`.

Schema:

```json
{
  "schemaVersion": 1,
  "event": "firebase-app-check-debug-tokens-revoked",
  "recordedAtUtc": "2026-08-23T12:05:00Z",
  "revokedAtUtc": "2026-08-23T12:00:00Z",
  "projectId": "meteo-friul",
  "projectNumber": "49007668366",
  "firebaseAppId": "1:49007668366:android:725bf6f8b339177a852ddf",
  "androidPackage": "com.meteofriul.app",
  "playSigningCertificateSha256": "<64 CARATTERI ESADECIMALI>",
  "maximumTokenTtlSeconds": 3600,
  "verifiedDebugTokenCount": 0,
  "verificationMethod": "firebase-app-check-rest-v1-paginated",
  "playConsoleEvidenceReference": "<riferimento verificabile alla firma app>",
  "firebaseConsoleEvidenceReference": "<riferimento verificabile a policy e revoca>"
}
```

Regole:

- `revokedAtUtc` è l'istante dell'ultima revoca/controllo completo;
- `maximumTokenTtlSeconds` è la massima TTL che potevano avere i token già
  emessi, compresa fra 1800 e 604800 secondi;
- la SHA è quella della firma app gestita da Play, non della upload key;
- i riferimenti non devono contenere token, credenziali o segreti;
- il file deve essere aggiunto in un singolo commit e non modificato dopo.

L'audit live verifica che il file sia tracciato, pulito, aggiunto una volta e
mai modificato; ricontrolla inoltre via API che i token Debug siano ancora
zero e che sia trascorsa la TTL più conservativa.

## Retarget della revisione runtime dopo l'AAB

Il manifesto AAB registra revisione, digest e host API esatti al momento della
build. Un successivo aggiornamento delle sole variabili Cloud Run crea una
nuova revisione anche quando l'immagine non cambia. In quel caso non si
modifica il manifesto: dopo il read-back amministrativo del tag si aggiunge un
nuovo anello append-only con questo schema:

```json
{
  "schemaVersion": 1,
  "event": "android-play-runtime-revision-retarget-verified",
  "recordedAtUtc": "2026-08-23T12:05:00Z",
  "retargetedAtUtc": "2026-08-23T12:00:00Z",
  "projectId": "meteo-friul",
  "projectNumber": "49007668366",
  "region": "europe-west1",
  "serviceName": "meteofriul-api",
  "androidPackage": "com.meteofriul.app",
  "versionName": "1.0.0",
  "versionCode": 300011,
  "aabSha256": "<SHA-256 DELL'AAB REGISTRATO NEL MANIFESTO>",
  "aabReleaseManifestPath": "release-history/android-play/<MANIFESTO>.release.json",
  "aabReleaseManifestSha256": "<SHA-256 DEL FILE MANIFESTO>",
  "previousEvidencePath": "",
  "apiTag": "play-beta",
  "apiBase": "https://play-beta---<HOST-CLOUD-RUN>/api",
  "fromRevision": "<REVISIONE PRECEDENTE>",
  "fromImageDigest": "<IMMAGINE@sha256:DIGEST-AAB>",
  "fromTag": "play-beta",
  "fromTagUrl": "https://play-beta---<HOST-CLOUD-RUN>",
  "toRevision": "<NUOVA REVISIONE SERVITA DAL TAG>",
  "toImageDigest": "<STESSA IMMAGINE@sha256:DIGEST-AAB>",
  "toTag": "play-beta",
  "toTagUrl": "https://play-beta---<STESSO-HOST-CLOUD-RUN>",
  "sameImageDigest": true,
  "configurationPurpose": "play-notification-cutover-staged",
  "verificationMethod": "cloud-run-admin-read-back"
}
```

Regole:

- `fromRevision` del primo record coincide con `CloudRunRevision` del
  manifesto AAB; ogni record successivo parte dal `toRevision` precedente;
- il primo `previousEvidencePath` e vuoto; nei record successivi coincide
  esattamente con il percorso Git del record precedente;
- path e SHA-256 del file manifesto, SHA-256 dell'AAB, package e versione
  legano ogni anello agli stessi artefatti immutabili;
- entrambi i digest coincidono byte per byte con `CloudRunImageDigest`
  dell'AAB: questo registro non autorizza mai una nuova immagine;
- `apiBase`, `fromTag`, `toTag` e le autorita HTTPS restano quelli
  incorporati nell'AAB;
- `configurationPurpose` vale `play-notification-cutover-staged` per la fase
  staged e `play-notification-cutover-active` per il retarget che abilita la
  fase active; una catena active puo contenere prima gli anelli staged, mai il
  contrario, e deve terminare con un anello active;
- i percorsi dei record sono passati all'audit nell'ordine della catena;
- il record deve essere creato soltanto dopo il read-back della revisione
  realmente servita dal tag, aggiunto in un singolo commit e mai modificato;
- l'audit fallisce se manca un anello, se la catena torna su una revisione gia
  vista o se l'ultimo `toRevision` non coincide con il tag Cloud Run live.

Se il tag serve ancora la revisione del manifesto AAB, non si crea alcun
record runtime. Ogni futuro retarget richiede un nuovo file: non si aggiorna
quello precedente.

## Bonifica dello stato push legacy

Questa operazione viene eseguita **dopo** che la prima installazione dal track
Play è registrata e verificata in `dry_run`. Non è svolta dallo script di audit.
L'operatore deve eliminare esclusivamente:

- record `push_devices` con `enrollment_generation` assente oppure diversa
  dalla nuova generazione Play;
- documenti `push_target_owners` che puntano a record eliminati, mancanti o
  appartenenti a una generazione precedente;
- documenti `push_pilot_state/device_capacity` e
  `device_capacity__<generazione-precedente>`, conservando soltanto il
  documento della generazione Play corrente.

La query e il read-back devono essere paginati e devono preservare la nuova
registrazione Play, il relativo owner FCM e il documento capacity corrente.
Non copiare nel registro ID installazione, token FCM, hash target, Comune,
preferenze o dati di posizione. Schema dell'evidenza:

```json
{
  "schemaVersion": 1,
  "event": "legacy-push-state-cleanup-verified",
  "recordedAtUtc": "2026-08-23T12:20:00Z",
  "firstPlayRegistrationVerifiedAtUtc": "2026-08-23T12:00:00Z",
  "cleanupCompletedAtUtc": "2026-08-23T12:15:00Z",
  "readBackAtUtc": "2026-08-23T12:19:00Z",
  "projectId": "meteo-friul",
  "projectNumber": "49007668366",
  "firebaseAppId": "1:49007668366:android:725bf6f8b339177a852ddf",
  "androidPackage": "com.meteofriul.app",
  "currentEnrollmentGeneration": "play-beta-v1",
  "currentAppVersion": "1.0.0+300011",
  "cleanupScope": "missing-or-different-enrollment-generation-only",
  "legacyPushDeviceCountAfterReadBack": 0,
  "orphanOrLegacyTargetOwnerCountAfterReadBack": 0,
  "legacyCapacityDocumentCountAfterReadBack": 0,
  "currentGenerationPushDeviceCountAfterReadBack": 1,
  "currentGenerationTargetOwnerCountAfterReadBack": 1,
  "currentGenerationCapacityDocumentCountAfterReadBack": 1,
  "currentGenerationCapacityActiveCountAfterReadBack": 1,
  "currentPlayRecordPreserved": true,
  "verificationMethod": "firestore-admin-paginated-read-back",
  "evidenceReference": "<riferimento al log controllato senza identificatori>"
}
```

La fase `active` resta bloccata se uno dei tre conteggi legacy non è zero, se
owner/device/capacity correnti non sono coerenti, se la registrazione Play non
risulta preservata o se il file non è Git append-only.
