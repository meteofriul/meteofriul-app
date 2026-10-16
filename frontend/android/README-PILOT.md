# Meteo Friûl Android wrapper

This is the Capacitor 8 wrapper used by the owner preflight and Google Play
candidate. The former private pilot is retained only as frozen history. The
wrapper does not contain a tracked signing key or private
Firebase credentials. Native push runtime and channels are integrated, while the machine-local
`google-services.json` remains intentionally ignored by Git. The shared React
application also contains a separate Web owner runtime; it is not part of this
native wrapper and is not considered deployed until its HTTPS preview passes
the pilot checks.

> **Current distribution path:** Google Play Console with the guarded AAB.
> Firebase App Distribution and `private_test` are frozen legacy/rollback
> paths; do not create new tester releases there. Their executable instructions
> remain only in Git history. The authoritative read-only notification
> cutover gate is
> [PLAY_NOTIFICATION_CUTOVER_AUDIT.md](../../PLAY_NOTIFICATION_CUTOVER_AUDIT.md).

## Identity and runtime

- Application ID: `com.meteofriul.app`
- Owner/Google Play release version: `0.1.8`
- Version code: `300025` (accepted in the Google Play internal test and
  verified on the owner device)
- Web origin inside the WebView: `https://localhost`
- API base: nuovo endpoint Cloud Run tagged, fornito esplicitamente alla build
  tramite `VITE_ANDROID_API_BASE`; non usare il fallback web pubblico
- Location: staged foreground one-shot fixes at startup/resume and at most
  every 3 minutes while visible; after the separate `Allow all the time`
  consent, an exit geofence plus WorkManager checks scheduled with Android's
  15-minute minimum keep the local notice target fresh while closed, without
  a permanent foreground service; Android may defer periodic work
- Orientation: portrait only; sensor rotation never switches the app to landscape
- Launch screen: Friuli blue background with the launcher icon centered; no dark WebView flash
- Ko-fi: opened outside the app via an Android intent
- App Check: custom plugin `MeteoFirebaseAppCheck`; debug provider in debug
  builds and Play Integrity provider in release/private-test builds
- Permission order: foreground GPS request, then notification request
- Push defaults: `Allerte` ON and `Avvisi` ON
- Official push: regional alerts for Android installations admitted by the
  guarded Play notification cutover; the old cap of ten belongs only to the
  frozen `private_test` path
- Local notices: preference retained; background targeting is App Check
  protected and stores canonical place plus time/accuracy, never raw GPS
  coordinates; delivery stays controlled until the E2E pilot passes

## Sync the wrapper

Use Node.js 22.17.1 and run from `frontend`:

On this Windows workstation, Codex must run the owner-preflight `android:sync`
outside its sandbox from the first attempt. A sandboxed run can report a false
`EPERM` while writing `frontend/dist`; do not respond by repeatedly deleting the
directory or manually copying assets. The authoritative recovery and Play/owner
distinction are documented in `ANDROID_PILOT_RUNBOOK.md` under **Preflight
Android owner corrente su Windows/Codex**.

```powershell
npm run android:sync
```

Before syncing an owner preflight, set `VITE_ANDROID_API_BASE` to the approved
tagged candidate endpoint.
Set the same origin for native background updates with the Gradle property
`METEO_API_BASE=https://<tagged-host>/api`; the build rejects non-HTTPS or
non-`/api` values. The worker never accepts an API URL from JavaScript.
The debug owner preflight does not prove Play Integrity, `PLAY_RECOGNIZED` or
`LICENSED`. Do not register a new App Check Debug token while preparing the Play
cutover unless a separate approved test explicitly requires it.

For a Play candidate, do not run `android:sync` first. Run the guarded
`scripts/build-play-aab.ps1` directly outside the sandbox; it builds in `%TEMP%`,
checks WebView and native endpoint parity, synchronizes Android and applies the
release ledger/signing gates.

Use an in-place install for upgrades so the WebView storage and random
installation ID are preserved. Reinstalling or clearing app data creates a new
installation ID; the old record remains distinct until it is explicitly
unregistered or removed. A debug preflight installation must never be treated
as proof that the Play installation is recognized or licensed.

The Android build must use Android Studio's JBR 21, not the machine-wide Java
8 runtime.

## Autonomous weather local-pilot APK

The autonomous ICON-2I/CAMS test has a separate, side-by-side debug build type.
Run `scripts/build-android-local-weather-pilot.ps1` from the repository root;
do not run `android:sync` first. Its application ID is
`com.meteofriul.app.localpilot`, its generated Web assets live only under the
ignored `app/src/localPilot/assets/public`, and its WebView keeps the production
`https://localhost` origin so OSMER, official alerts and the remaining API use
the explicit tagged HTTPS endpoint passed to the script. Mixed content is
enabled only in this debug flavor; Android's dedicated network-security policy
still permits cleartext solely to `localhost` and `127.0.0.1` for the loopback
weather data plane.

The variant cannot be requested directly from Gradle without the script's
one-run marker. It removes background-location permission, disables the legacy
native weather-prefetch worker and never enrolls predictive local notices.
Foreground official-alert data is unchanged. Native FCM delivery is outside
this harness because the side-by-side package deliberately has no Firebase
Android identity; the production `google-services.json` is neither copied nor
rewritten.

Connect a phone only after the APK exists, then use `adb reverse tcp:8781
tcp:8781` before installing `app-localPilot.apk`. This builds and installs
locally only; it does not upload, deploy, publish or modify a cloud service.

## Google Play AAB candidate

The Play artifact has a separate, fail-closed procedure. It never reuses the
private-test signing configuration implicitly and it never uploads to Play
Console. Before the first build, decide and back up the Play upload key, then
create the ignored `frontend/android/play-keystore.properties` file:

Before creating the candidate, manually verify that
`https://meteofriul.it/privacy/` is publicly reachable over HTTPS and contains
`Titolare del trattamento: Riccardo Rosset — progetto Meteo Friûl` with contact
`info@meteofriul.it`. The developer profile, privacy URL and owner-entered Play
Console data must match. Credits wording is already present in the app and only
needs verification; this gate does not change the splash screen. The guarded
build does not infer or write any of these Console fields.

Because the manifest requests `ACCESS_BACKGROUND_LOCATION`, Play upload is
also blocked until the owner completes the Permissions Declaration Form,
prepares a short reviewer-accessible Android video showing the local-notice
feature, prominent in-app disclosure, user action and Android background
permission prompt/settings, and describes the same feature consistently in
the Store listing. These are manual Console gates; the build cannot attest
them automatically.

The Firestore push-outbox TTL gate must also return exit code `0` before the
candidate build:

```powershell
.\scripts\audit-firestore-push-ttl.ps1
```

It requires `ACTIVE` TTL policies for the official-alert and local-notice
outboxes, validates the 30/14-day timestamps written by the backend, and
requires evidence that historic documents missing `expires_at` were explicitly
checked and backfilled or cleaned. See
`docs/operations/FIRESTORE_PUSH_TTL_GATE.md`.

Territorio is constrained anonymous UGC, not a read-only weather layer. Before
building the Play candidate, the distinct
`docs/operations/COMMUNITY_MODERATION_GATE.md` must also be green: guidelines
v2, in-app content reporting and anonymous-source blocking, private moderation,
runtime contracts, privacy/Data Safety alignment, and verified Firestore TTL
for every community collection. The push-outbox TTL gate does not cover these
collections. The exact landing and Play disclosure handoff is tracked in
`docs/operations/COMMUNITY_PRIVACY_DATA_SAFETY_HANDOFF.md`; the candidate stays
blocked while the public IT/FUR pages use the former IP-based description or
the FUR copy lacks explicit linguistic review.

The protected build always performs a fresh read-only LIVE check of the exact
cloud identity, all eight `ACTIVE` policies, and every document currently
present. Empty collections are valid in that fresh snapshot. Separately, it
requires the newest append-only aggregate record in
`release-history/firestore-community-ttl`: all eight collections need a
non-zero valid LIVE sample, the record must be at most 30 days old, and its
deterministic writer-source SHA-256 must match. Fixture, wrong-identity,
untracked, dirty, edited, stale, or hash-mismatched records fail closed. Create
that record explicitly while controlled samples exist; the AAB build remains
separate. Do not assume real data exists: run the private moderation smoke and
the marker-owned `seed_community_ttl_evidence_live.py` in two terminals with a
maximum 120-second hold, record only after both evidence-ready events, and
accept the record only after both transactional cleanups succeed. The seed's
report is already expired and moderation-hidden; the tagged public API and a
fresh public-service read must remain free of it before, during, and after the
hold. Recording names the full backend source commit. The build independently
hashes the writer/evidence-producer blobs from the tagged revision's
authoritative `BackendCommit` without checking it out; a matching JSON field by
itself is never trusted. The evidence source must be an ancestor; a descendant
backend commit passes only while those blobs remain unchanged. See
the ledger README for the recording command.

```properties
storeFile=C:/secure/meteofriul-play-upload.jks
storePassword=<local-secret>
keyAlias=<upload-alias>
keyPassword=<local-secret>
```

Do not commit this file, the keystore or their passwords. Download an official
`bundletool-all-*.jar` locally and pass its exact path to the guarded build.
The jar is not downloaded or updated automatically. Calculate its SHA-256 from
the trusted download and pass that expected value explicitly: the script checks
the digest before it executes bundletool and records both version and digest.

From the repository root, after confirming the latest version code visible in
Play Console, run:

```powershell
pwsh -NoProfile -File .\scripts\build-play-aab.ps1 `
  -ApiBase "https://<tagged-host>/api" `
  -CommunityApiBase "https://meteofriul-community-49007668366.europe-west1.run.app/api" `
  -ExpectedRevision "meteofriul-api-<scope>-<commit7>" `
  -ExpectedBackendCommit "<backend-commit-40>" `
  -ExpectedLatestPlayVersionCode 0 `
  -BundletoolPath "C:\secure\bundletool-all.jar" `
  -ExpectedBundletoolSha256 "<bundletool-sha256>" `
  -ExpectedUploadCertificateSha256 "<first-upload-key-sha256>"
```

The guarded build requires PowerShell 7 with
`ConvertFrom-Json -DateKind`; Windows PowerShell 5.1 is rejected before any
release preflight.

Use `0` only when Play Console confirms that the package has no uploaded
version. The first build also requires the upload-key fingerprint as an
explicit trust anchor. Later builds derive trust only from the latest
append-only `play-accepted` evidence; a `built-not-uploaded` manifest is never a
trust anchor. A key change requires explicit `upload-key-rotation` evidence.

The script requires a clean pushed commit and verifies the tagged Cloud Run
URL, resolved revision, backend commit, readiness, image digest and health
before and after the build. It validates the exact Firebase identity in the
local `google-services.json`: project `meteo-friul`, project number
`49007668366`, app ID `1:49007668366:android:725bf6f8b339177a852ddf` and package
`com.meteofriul.app`. The Gradle guard blocks every release-producing task,
including signing, packaging and finalization tasks, unless the protected
script supplies its one-run marker and all API, signing and Firebase
properties.

Before compilation the script writes an immutable version reservation. It
then validates the AAB with the trusted bundletool, reads package/version from
the packaged manifest and uses the Java verifier to read every non-`META-INF`
entry, require exactly one signer and enforce one certificate fingerprint.
WebView and native background worker must contain the same API endpoint.

The signed output is copied without overwrite to the durable, Git-ignored
`release-artifacts/android-play/meteofriul-<versionCode>-<versionName>.aab`.
The reservation and immutable `built-not-uploaded` manifest are written to
`release-history/android-play`. Commit and push both records, require green CI,
then upload the exact archived AAB whose SHA-256 matches the manifest. Record
Play acceptance or abandonment afterward with
`scripts/record-play-release-evidence.ps1`; never rewrite an earlier record.
Both the protected build and CI run `scripts/audit-play-release-ledger.ps1`:
every JSON must have exactly one Git add commit and no later modification,
rename, copy, or deletion. Any historical ledger mutation blocks the release.
Play App Signing uses a separate app-signing certificate unless an explicit
migration decision says otherwise: obtain that certificate SHA-256 from Play
Console and register it in Firebase App Check; never infer it from the upload
certificate.

Before setting either backend enrollment mode to `play_beta`, and before the
first registration or dry run even with a cap of one, configure the Firebase
Play Integrity provider to require both `PLAY_RECOGNIZED` and `LICENSED` for the
Play build. If those verdicts cannot be isolated from the legacy sideload, use a
distinct Firebase Android App ID for the Play beta. The client-reported
`versionName+versionCode` allowlist is defense in depth, not proof of the Play
channel. Because Firebase App Check accepts registered Debug tokens separately
from Play Integrity verdicts, revoke every Android App Check Debug token,
record verifiable evidence that the Debug list is empty, close the sideload
policy, and wait at least the configured maximum App Check token TTL before
enabling `play_beta`. Restart the TTL wait after any accidental Debug-token
issuance. Do not enable `send` until these gates and the first track-installed
registration have been verified.

This personal Play developer account was created after 13 November 2023.
Production access therefore requires a closed test with at least 12 testers
continuously opted in for 14 days; internal testing does not replace that gate.
Invite a small margin above 12 to reduce operational risk, without presenting
that margin as an additional Play requirement. Keep the notification rollout
separate: validate the owner at cap `1` before increasing the cap for the
closed-test participants.

## Deliberately absent from this scaffold

- a tracked `google-services.json` (the machine-local file stays ignored)
- a tracked release/private-test keystore or its passwords
- a signed APK or public distribution package
- a tracked Play upload keystore, `play-keystore.properties` or bundletool jar

Web FCM lives in the shared frontend and uses a Firebase Installation ID plus
the local `/firebase-messaging-sw.js`; it does not use the native Android token
path. Web App Check uses reCAPTCHA Enterprise and `Segnala` stays fail-closed
when it is not configured. The public Web Push certificate key is versioned in
the production configuration; Web notification registration still needs the
controlled HTTPS preview test before it can be declared live. Web targets remain
outside the Android Play notification enrollment.

The native App Check bridge is already fail-closed: without a Firebase Android
app/config it returns `firebase_app_check_not_configured`, so `Segnala` cannot
send an unverified mutation. The native dependencies and providers are already
integrated: debug builds use the debug provider and release builds use Play
Integrity. Push register and unregister routes are App Check protected as well.
Keep every token, raw installation ID and signing secret out of Git.

## Background location for local notices

The manifest declares precise and background location because current-place
notices are a core pilot function. Foreground permission is requested first.
Android's separate `Allow all the time` choice is opened explicitly from
Settings; it is never disguised as the normal foreground prompt. Once granted:

- a recent accurate fused fix is reused for speed;
- balanced current location is attempted before high accuracy;
- an exit geofence requests a faster refresh after movement;
- WorkManager requests a bounded check at Android's 15-minute minimum (the OS
  may defer it) and restores the schedule after reboot or app update;
- no continuous watch, foreground service or permanent location notification
  is created.

The exact fix exists only in memory and in the HTTPS request body protected by
Firebase App Check. The backend persists canonical municipality/locality and
freshness evidence, not raw latitude/longitude. Denied permission, coarse or
stale fixes, mock locations and ambiguous municipal boundaries fail closed.
