# Private Community pilot storage and packaging

This implementation is restricted to `meteofriul-pilot-20260906` and does not
use the published `meteo-friul` project or the default Firebase application.

## Local browser after the cloud cutover

Use the canonical launcher explicitly:

```powershell
./scripts/start-local-weather-pilot.ps1 -CommunityPilot -CommunityCloudStore -NationalCloud -RestartFrontend
```

This keeps the browser on `127.0.0.1:5174` in `local-pilot` mode and starts
Community only on `127.0.0.1:8783`, against the **same** existing cloud pointer
and private snapshots used by the enrolled phone. It does not restart or import
the old SQLite store. Do not run the old SQLite Community mode after cutover.
The browser keeps its independent existing installation identity; no phone token
or phone identity is copied. National data and ICON/CAMS proxy destinations are
the fixed pilot cloud readers; the old local weather writer is not started.

The existing `.dev-logs/cloud-admin-venv` is required. The local-only backend
uses the active `meteofriul@gmail.com` gcloud owner and explicit pilot project,
refreshing short-lived access tokens in memory with bounded subprocess calls.
No ADC, secret argument, token log, environment token, or host credential file
is created. Missing auth or cloud state fails closed; health identifies
`meteofriul.community.loopback-cloud-pilot.v1` and revalidates the cloud snapshot.
The module/credential helper are excluded from the allowlisted Cloud Run image.

This is a trusted-owner local preview, not another remotely enrolled client:
local processes and the existing allowed localhost origins can call its API.
Host, Origin, mutation header and request-size checks remain in force. Stop it
with the canonical launcher's mode-independent `-Stop` when it is not needed.
Use `-CheckOnly` without restart flags for prerequisite checks; it does not
start services or acquire the owner token. Actual auth is checked at startup.

The private bucket is `meteofriul-pilot-20260906-community`. Complete versioned
state snapshots use `pilot/community/v1/snapshots/<uuid>.json`; the Firestore
document `pilot_community_state/current` is their atomic commit pointer. Every
pointer update requires the exact previously read Firestore update timestamp.
Missing/corrupt state or an uncertain commit produces an unavailable response.
Runtime cannot create a fresh store or reset protections. Existing operation
receipts reconcile retries after a committed write loses its acknowledgement.

Import is explicit and create-only. `backend/tools/seed_pilot_community_cloud.py`
defaults to validating the existing SQLite file read-only. `--execute` permits
the create-only cloud seed and verifies its readback. The owner administration
tool additionally supports the existing signed-in gcloud account without a
credential file. Freeze local Community writes at the cutover if preserving
changes made after the import snapshot is required.

## Image packaging

Run `scripts/package-community-cloud-context.ps1` from the canonical workspace.
It creates a unique operating-system temporary directory using the exact file
allowlist in `backend/community-pilot-context.files.json`, copies the geography
artifact only after verifying its pinned SHA-256, then verifies copied hashes.
No Cloud Build submission or deployment is performed by the script. `-VerifyOnly`
validates source files and the geography artifact without creating a context.

Submit only that generated directory with its `cloudbuild.yaml`; never submit
the workspace as the Community build context. The image starts only
`app.pilot_community_cloud:create_cloud_app`, with one Uvicorn worker on port
8080 and Uvicorn access logging disabled. It includes no credentials, mutable
SQLite state, Firebase setup, published application entrypoint, or unrelated
weather data. The only `.sqlite3` input is the immutable reviewed geography.

Dependencies use the existing backend pins plus `google-cloud-firestore==2.31.0`
and `google-cloud-storage==3.14.1`, checked against their official PyPI releases
on 2026-09-21. The image checks the private API contract and loads all 7,894
municipalities before its runtime command is installed.

## Retired snapshots: maintenance pending

Immutable historical snapshots still contain earlier private state. Their
cleanup is pending and is not invoked by runtime, packaging, import, or device
enrollment. The runtime service account requires object read/create permissions,
not object deletion. No snapshot cleanup execution or delete permission is part
of this cutover.

Do not apply an unconditional age-based lifecycle to this prefix: the current
snapshot must survive indefinitely while the service is idle. Future explicit
maintenance must preserve the latest valid Firestore pointer target, consider
only recognized immutable snapshot keys older than 48 hours, and delete only
the generation that was inspected. It must fail closed if authoritative state
cannot be verified. Administrative rollback to an old pointer must be coordinated
with that maintenance. A bounded payload-cap failure must never be resolved by
dropping quotas, denial history, replacement lineage, or permanent accepted
operation receipts.
