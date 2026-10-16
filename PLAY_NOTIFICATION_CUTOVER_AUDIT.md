# Audit notifiche beta Google Play

Questa procedura verifica il cutover delle notifiche senza modificare Google
Cloud, Firebase, App Check o Play Console e senza creare un AAB. Lo script
termina al primo dato mancante o discordante; un esito diverso da `PASS` vieta
il passaggio alla fase successiva.

## Dati che deve fornire il titolare

Prima dell'audit servono cinque valori deliberati, non dedotti dallo script:

1. SHA-256 del **certificato di firma dell'app** mostrato in Play Console. Non
   usare la SHA-256 della upload key.
2. `versionName` e `versionCode` esatti del candidato che verrà caricato sul
   track Play. La release corrente è `0.1.3` e `300020`: verificarli nuovamente
   nel manifest AAB prima dell'uso.
3. nuova generazione server, per esempio `play-beta-v1`.
4. cap atteso. In `staged` deve essere esattamente `1`; in `active` può essere
   aumentato esplicitamente, ma non oltre `100`.
5. allowlist completa delle identità `versionName+versionCode` ammesse durante
   l'aggiornamento. Per la `300020` deve contenere `0.1.0+300017`,
   `0.1.2+300019` e `0.1.3+300020`, senza cambiare generazione.

Il titolare deve inoltre inserire in un nuovo file JSON append-only sotto
`release-history/play-notification-cutover/evidence/` i riferimenti alle
schermate Play Console e Firebase Console usate per confermare firma e revoca
dei token Debug. Il formato è documentato nel README di quel registro.

Serve infine il manifesto `*.release.json` dell'esatto AAB candidato, già
committato sotto `release-history/android-play/`. L'audit ricava da quel record
API base, tag, revisione e digest; non accetta valori scelti a mano né usa la
revisione `latestReady` come sostituto. Se, dopo la build, una modifica di sola
configurazione crea una nuova revisione sullo stesso digest, ogni retarget deve
essere attestato da un nuovo record append-only. I record ordinati collegano
la revisione AAB alla revisione realmente servita dal tag; non autorizzano mai
un cambio immagine, host o AAB.

## Gate manuali prima dell'audit

In Firebase App Check, per l'App Android
`1:49007668366:android:725bf6f8b339177a852ddf`:

- impostare `allowUnrecognizedVersion=false`;
- impostare `requireLicensed=true`;
- richiedere `MEETS_DEVICE_INTEGRITY`;
- revocare **tutti** i token Debug, non soltanto quello dell'ultimo telefono;
- annotare la TTL massima dei token che potevano essere già stati emessi.

Poiché il manifest Android dichiara `ACCESS_BACKGROUND_LOCATION`, prima del
caricamento Play devono essere pronti anche il Permissions Declaration Form,
un breve video Android accessibile al reviewer che mostri funzione, disclosure
prominente e passaggio al prompt/impostazione di sistema, e una descrizione
coerente della funzione nella scheda Store. Questo è un gate manuale: lo script
non può compilare né attestare al posto del titolare i campi della Console.

La revoca non invalida immediatamente token App Check già emessi. Dopo aver
committato una nuova evidenza append-only bisogna attendere almeno il massimo
tra la TTL annotata e la TTL configurata attualmente. Lo script ricontrolla
questo intervallo; non accetta evidenze non tracciate, modificate dopo il primo
commit o ancora sporche nel worktree.

## Audit fase staged

Prima della prima registrazione Play, servizio e due job devono usare lo stesso
digest backend e la stessa configurazione beta. Entrambi i dispatcher restano
in `dry_run`, le allowlist owner sono vuote e il cap è `1`.

```powershell
.\scripts\audit-play-notification-cutover.ps1 `
  -Phase staged `
  -ExpectedPlaySigningSha256 "<SHA256 FIRMA APP PLAY>" `
  -ExpectedEnrollmentGeneration "play-beta-v1" `
  -ExpectedVersionName "0.1.3" `
  -ExpectedVersionCode 300020 `
  -ExpectedAllowedAppVersions @(
    "0.1.0+300017",
    "0.1.2+300019",
    "0.1.3+300020"
  ) `
  -ExpectedMaxDevices 1 `
  -AabReleaseManifestPath ".\release-history\android-play\meteofriul-300020-0.1.3.release.json" `
  -DebugTokenRevocationEvidence ".\release-history\play-notification-cutover\evidence\<UTC>-debug-tokens-revoked.json" `
  -RuntimeRevisionEvidencePaths @(
    ".\release-history\play-notification-cutover\evidence\<UTC>-runtime-revision-retarget-verified.json"
  )
```

Omettere `-RuntimeRevisionEvidencePaths` se il tag serve ancora esattamente la
revisione del manifesto. Se esistono più retarget, elencare tutti i file in
ordine, dal primo spostamento successivo all'AAB fino a quello corrente.

Solo dopo `Status: PASS` si installa dal track Play e si controlla la prima
registrazione in dry-run. A quel punto si esegue una bonifica controllata dei
record push precedenti e il relativo read-back, senza mai eliminare il record
della nuova generazione Play. La procedura e lo schema dell'evidenza sono nel
[registro cutover](release-history/play-notification-cutover/README.md).

## Audit fase active

Dopo il controllo della prima installazione Play, impostare deliberatamente il
cap desiderato e `send` su entrambi i dispatcher. L'audit active richiede anche
`PUSH_OFFICIAL_ALERTS_REQUIRED=true`.

```powershell
.\scripts\audit-play-notification-cutover.ps1 `
  -Phase active `
  -ExpectedPlaySigningSha256 "<SHA256 FIRMA APP PLAY>" `
  -ExpectedEnrollmentGeneration "play-beta-v1" `
  -ExpectedVersionName "0.1.3" `
  -ExpectedVersionCode 300020 `
  -ExpectedAllowedAppVersions @(
    "0.1.0+300017",
    "0.1.2+300019",
    "0.1.3+300020"
  ) `
  -ExpectedMaxDevices 100 `
  -AabReleaseManifestPath ".\release-history\android-play\meteofriul-300020-0.1.3.release.json" `
  -DebugTokenRevocationEvidence ".\release-history\play-notification-cutover\evidence\<UTC>-debug-tokens-revoked.json" `
  -LegacyPushCleanupEvidence ".\release-history\play-notification-cutover\evidence\<UTC>-legacy-push-cleanup-verified.json" `
  -RuntimeRevisionEvidencePaths @(
    ".\release-history\play-notification-cutover\evidence\<UTC>-runtime-revision-retarget-verified.json"
  )
```

Il valore `30` è il cap operativo deliberato per questa coorte. La variabile
`PUSH_PLAY_BETA_ALLOWED_APP_VERSIONS` viene confrontata come insieme: ordine e
spazi non contano, ma versioni mancanti, duplicate o inattese bloccano l'audit.
La versione del candidato deve sempre appartenere all'insieme. L'evidenza di
bonifica può riferirsi alla `300017`, purché appartenga alla stessa generazione
e resti compresa nell'allowlist durante la coesistenza. Se la fase active ha
creato una seconda revisione,
l'array deve contenere prima l'evidenza staged e poi quella active; ogni nuovo
retarget si aggiunge in coda senza sostituire i percorsi precedenti.

## Cosa legge e cosa confronta

Lo script usa esclusivamente comandi e richieste di lettura:

- account attivo, progetto e project number da `gcloud`;
- Android App e certificati SHA tramite Firebase Management REST;
- configurazione Play Integrity e lista completa paginata dei token Debug
  tramite Firebase App Check REST;
- revisione realmente servita dal tag del servizio `meteofriul-api`;
- job `meteofriul-official-alert-sync` e `meteofriul-local-notice`.

Il controllo richiede:

- account `meteofriul@gmail.com`, progetto `meteo-friul` e project number
  `49007668366`;
- package `com.meteofriul.app` e App ID esatti;
- SHA-256 Play registrata una sola volta fra i certificati Firebase SHA-256;
- manifesto AAB Git immutabile e sua identità esatta di versione/package;
- policy App Check restrittiva e zero token Debug dopo aver seguito tutta la
  paginazione;
- TTL trascorsa da evidenza Git append-only;
- tag/host API dell'AAB collegato alla revisione del manifesto oppure a una
  catena append-only completa di retarget; ogni anello e la revisione live
  devono conservare esattamente il digest AAB, anche quando `latestReady`
  indica un'altra revisione;
- stesso digest immutabile `@sha256:` sulla revisione tagged e sui due job;
- entrambi gli enrollment `play_beta`, stessa generazione, App ID, singola
  identità `versionName+versionCode` e stesso cap;
- allowlist owner vuote;
- in `active`, evidenza Git append-only che il read-back non trovi più record
  `push_devices`, owner FCM o capacity delle generazioni precedenti e che la
  registrazione Play corrente sia rimasta integra;
- `dry_run` coerente in `staged`, `send` coerente in `active`.

Il controllo non dimostra che un tester abbia installato davvero dal track:
quella prova resta il controllo manuale successivo allo staged. L'identità
versione nel backend è difesa in profondità; la separazione crittografica resta
affidata ai verdict `PLAY_RECOGNIZED` e `LICENSED` di App Check.

## Test locali

```powershell
.\scripts\audit-play-notification-cutover.tests.ps1
```

I test usano fixture JSON e non accedono al cloud. Verificano sia i percorsi
validi staged/active sia i principali errori fail-closed, inclusi residui
legacy, generazione errata, cancellazione accidentale del nuovo record Play e
catene runtime mancanti, alterate, riferite a un altro manifesto/AAB/host o
con cambio del digest backend.

## Riferimenti API ufficiali

- [Configurazione Play Integrity per App Check](https://firebase.google.com/docs/reference/appcheck/rest/v1/projects.apps.playIntegrityConfig)
- [Lista paginata dei token Debug](https://firebase.google.com/docs/reference/appcheck/rest/v1/projects.apps.debugTokens/list)
- [Certificati SHA dell'Android App](https://firebase.google.com/docs/reference/firebase-management/rest/v1beta1/projects.androidApps.sha/list)
