# Private cloud Community enrollment — owner pilot only

The side-by-side Android package is `com.meteofriul.app.localpilot`. This is
restricted pilot enrollment, not the authentication design for public release.
The APK contains no bearer secret. Production Firebase/Play identity is unchanged.

Only the pilot Capacitor configuration sets `loggingBehavior: "none"`: Capacitor's
debug bridge otherwise logs successful native results, including credentials.
The plugin also refuses credential access if bridge logging is enabled. This
does not change the main/beta configuration or its logging behavior.

## Binding and files

The plugin `PilotCommunityAuth` exists only in the `localPilot` source set and
registry. On the first cloud Community request it hashes the existing persisted
Community client ID. It never rotates or replaces that identity. The raw ID is
not exported in the binding file. All pilot Web storage retains its existing
`localCommunityPilot:v1:` namespace, including pending-operation receipts.

Native app-private, backup-excluded paths relative to `run-as` package directory:

- `no_backup/pilot-community-installation.json`: version 1, `client_id_sha256`,
  and the exact `api_base`. Created atomically by the plugin even when enrollment
  has not yet been provisioned. An existing different binding fails closed.
- `no_backup/pilot-community-cloud-auth.json`: provisioned separately after
  authorization, with exactly `version`, `client_id_sha256`, `token`, `api_base`.
  The token is generated with `secrets.token_urlsafe(32)` (256 random bits).

The only allowed API base is
`https://pilot-community-335641913741.europe-west1.run.app/api`.
Both Java and JavaScript validate the endpoint, installation hash and token
shape before any cloud request. Native files are bounded to 4096 bytes.

## Provisioning without displaying identity or secrets

1. Install the guarded pilot APK with `adb install -r`, preserving app data.
2. Open the pilot. A Community request creates the SHA-only binding even though
   the missing credential causes a clear, closed failure. No request reaches the
   Community backend until enrollment is present.
3. A provisioning script captures `adb -s <serial> exec-out run-as
   com.meteofriul.app.localpilot cat no_backup/pilot-community-installation.json`
   into its process memory. Do not print that output. No raw client ID needs to
   be recovered from WebView storage or exposed to the operator.
4. The script generates the random bearer in memory and registers only
   SHA-256(token), bound to `client_id_sha256`, in the isolated pilot backend.
   Preserve accepted operation receipts, quotas and lineage when migrating
   existing local Community state; otherwise a pending local command could be
   misinterpreted as unaccepted by an empty cloud backend.
5. Write the private credential JSON over the subprocess stdin to a fixed
   app-private temporary filename using `adb shell run-as` and a restrictive
   umask, then atomically rename it to the fixed auth filename. No token in
   argv, shell history, repository, APK, Web storage, diagnostic output or logs.
   Avoid shared `/sdcard` staging. The script verifies only an installation hash
   and token fingerprint acknowledgement, never the bearer itself.
6. Reopen the app and verify cloud reads and explicit mutations. `install -r`
   preserves both private files; Android backup intentionally does not.

The plugin returns the bearer transiently to the enrolled app's WebView. The
adapter keeps it in request memory only and sends `Authorization: Bearer ...`
plus `X-Meteo-Pilot-Installation: <sha256>`. Redirects are refused. Every
Community endpoint is authenticated, including reads, resolve, reputation and
operation reconciliation; ordinary endpoints are unaffected. The backend must
verify that a submitted `client_id` hashes to the enrolled installation.

Coordinate-based Community reads use POST `/api/community/reports/query`, keeping
GPS values out of Cloud Run URL/access logs. ISTAT reads continue to use GET.
Browser-local development keeps its loopback adapter and receives no bearer.

Revocation is server-side by disabling/removing the enrolled token fingerprint.
Tokens must never be copied between installations or accepted for another host.
