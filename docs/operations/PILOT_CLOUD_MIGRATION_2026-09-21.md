# Pilot cloud cutover — 21 September 2026

Scope authorized by the owner: **pilot only**. Project
`meteofriul-pilot-20260906`, number `335641913741`, region `europe-west1`.
The published/beta project `meteo-friul`, its deployments, APK and schedules
were not changed. No Git push or Play publication forms part of this cutover.

## New runtime resources

- `pilot-national-weather`: public read-only national ICON v2 reader; dedicated
  `pilot-national-reader` identity; 1 CPU / 1 GiB, min 0, max 1, concurrency 2.
- `pilot-national-icon`: real national acquisition/publisher; dedicated identity,
  1 CPU / 2 GiB, one task, no retry, initial 1,800-second limit.
- `pilot-national-icon-refresh`: 06:00 and 18:00 UTC, existing pilot scheduler
  identity granted invocation on **this new job only**, no retry.
- `pilot-community`: enrolled-device Community API; 1 CPU / 512 MiB, min 0,
  max 1, concurrency 4. Internet ingress does not authorize report access:
  bearer and installation binding are checked before application operations.
- Firestore `(default)`: newly created **in the pilot project**, Standard Native,
  regional `europe-west1`, deletion protection enabled. No default Firebase app.
- Private bucket `meteofriul-pilot-20260906-community`: uniform access and public
  access prevention. Immutable complete transaction snapshots are private GCS
  objects; Firestore atomically selects the current snapshot. This is not a
  one-document-per-observation Firestore model.

National data/state use only `pilot/weather/v2/` and
`pilot/state/national-icon/` in the existing pilot data/state buckets. The job
has replacement permission **only** for
`pilot/weather/v2/icon2i/pilot.json`; immutable runs cannot be deleted by it.
Community has read/create snapshot permissions, no object deletion permission.

The owner separately confirmed runtime IAM and public Cloud Run invocation
(`allUsers`, `roles/run.invoker`) for these two endpoints. Firestore and all
buckets remain non-public. Regional ICON/CAMS/events jobs and schedules remain
unchanged.

## Deployed images and evidence

National image digest:
`sha256:fb33b77b0972cd5aa049b7adca9a0898a349cc6b66c78f7278cf46cba16f35fa`.
Build `11194611-4916-461f-9181-38f07eac8795` succeeded including offline tests.

Community image digest (CORS refinement included):
`sha256:c4fa27a357b7f58ffadf0676b9a3068e711e48240bab53e511c22287f799abd5`.
Build `a2ece767-6d5a-4aa5-bb3a-2558945189fa` succeeded; revision
`pilot-community-00002-6wq`. Unauthenticated report access was verified as 401.

The complete reviewed 20 September national bundle was imported first. Job
execution `pilot-national-icon-wwt9x` then succeeded in 3m50.25s and published
real run `20260921T000000Z`, generated at `2026-09-21T15:34:31Z`.
The reader verifies metadata/index and only the requested geographic block,
not all national blocks per cold start.

Observed PC HTTPS timings, **not a full phone UI benchmark**: first Roma resolve
3,091 ms, cached block 142 ms; after fresh publication Pordenone 386 ms and Urbino
206 ms. Actual authenticated phone report reads returned 200 in about 141–171 ms
server latency. Do not infer end-to-end app fluidity from those server timings.

## Existing state and Android preservation

The local SQLite state was read consistently and imported create-only. All 21
ledgers were empty; canonical payload 946 bytes, SHA-256
`f11c5a37b7dbee691aad3e397c9b76113746c9365e13bcd73e49285f4521c77b`.
Cloud readback and a second SQLite read after stopping the local writer matched.
The original SQLite file was retained, not deleted or used as a cloud fallback.

First cloud APK SHA-256:
`5ff84e044e9a328a22df5966e838249de3b3210610698cebef816c1478a414ab`.
Package `com.meteofriul.app.localpilot`, code `300012`, name
`1.0.1-local-pilot`, installed with `adb install -r` at 17:37:07 local time.
Before/after hashes of private preferences, WebView, databases and no-backup
data were identical. First installation date was preserved. Beta
`com.meteofriul.app` remained last updated at `2026-08-30 00:41:28`.
There were no `adb reverse` mappings.

The phone was enrolled without rotating its existing Community client identity.
Its bearer exists only in app-private no-backup storage, not the APK, Web storage
or logs. Bridge logging is disabled and the plugin refuses credentials otherwise.
The initial private trial authorization expires on **21 October 2026**; renewal
is a deliberate administrator action, not a reason to reinstall the app. This
owner enrollment is not the final public distribution authentication design.

## Validation and follow-up discovered during acceptance

- 124 targeted backend tests and 47 subtests passed (local/SQLite/cloud rules,
  expiration/idempotency, snapshot persistence, API isolation and enrollment).
- 76 national offline tests passed; complete 644-document seed verified.
- Frontend full run: 4,359 passed, 13 skipped; lint clean. Additional national
  coordinate privacy and native build guard checks passed subsequently.
- User confirmed without cable: forecasts load and report composer recognizes
  Pordenone. No fabricated field observation was submitted for this check.
- User found UV present but pollen/air quality missing. CAMS cloud data is fresh;
  the national frontend branch had skipped its CAMS enrichment. The client now
  fetches the independently verified CAMS supplement without requesting regional
  ICON or delaying the national forecast. Coverage remains the existing FVG
  CAMS catalogue, not nationwide CAMS coverage.

## CAMS correction and browser alignment

- Browser verification against current cloud data: Pordenone, national ICON run
  21 September 2026 00:00 UTC; air card PM2.5 5.3 and PM10 9.1 micrograms/m3;
  pollen card Artemisia 14.28 grains/m3. Both detail panels were opened and showed
  the CAMS sample for 18:00 local time, including six pollen species and the four
  air constituents. These are observed model values, not ground measurements.
- 375 targeted frontend tests passed for enrichment, national identity,
  asynchronous delivery, timeout/retry, concurrent requests, obsolete responses,
  cache/revocations, UV and Home/route lifecycle. Final complete frontend run:
  **4,372 passed, 13 skipped**, 507 passing test files.
- Corrected APK SHA-256:
  `cec2b8e3fa8f909446b58e2a870b3642aa80a19581547d0f282d469bbd400132`.
  Installed with `adb install -r` at **18:03:40 local time**. Private-data hashes,
  first installation date and beta package/version timestamps remained identical.
  Cloud enrollment was preserved; no token rotation or app-data reset occurred.
- Final on-device acceptance: the user reopened the corrected pilot without
  cable and explicitly confirmed that **both air quality and pollen appear**.
  Together with the earlier disconnected forecast/GPS check, this closes the
  reported missing-CAMS issue. It is not a general claim that every pilot feature
  or network-failure scenario has been retested on the phone.

The canonical browser preview was restarted using:

```powershell
./scripts/start-local-weather-pilot.ps1 -CommunityPilot -CommunityCloudStore -NationalCloud -RestartFrontend
```

It remains a development page on `127.0.0.1:5174`: fixed server-side proxies read
current national/CAMS cloud data, while the owner-only Community bridge on
`127.0.0.1:8783` uses the same pilot cloud repository as the phone. That bridge
keeps short-lived, refreshing owner credentials solely in server memory, checks
the exact account/project, and retains the existing Host/Origin/request guards.
It does not reuse the phone token, restart SQLite, initialize missing cloud state,
or run weather acquisition jobs. This local development bridge is not needed by
the installed autonomous APK. Backend port 8002 was reused, and all active local
listeners were verified loopback-only and healthy after startup.

Bridge verification: 115 backend tests, nine Node configuration tests and 35
launcher checks passed. Owner-only modules are excluded from Cloud Run build
contexts. Canonical workspace cleanliness and whitespace checks passed.
Final frontend lint also passed.

Old immutable Community snapshots require a separate retention maintenance
procedure before a broader/public trial. Never apply an unconditional age
lifecycle to all snapshots: an idle current snapshot must remain intact. Do not
claim that the private pilot authentication or whole-state snapshot architecture
is already the final scalable public release architecture.
