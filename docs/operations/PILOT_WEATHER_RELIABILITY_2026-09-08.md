# Pilot weather reliability — staged rollout, 8 September 2026

## Scope and approval

Owner approved implementation in separate tested/deployed stages:
diagnostics → ICON recovery → CAMS recovery → fallback → monitoring.
Only `meteofriul-pilot-20260906`, region `europe-west1`. Always pass the
project explicitly: the CLI default project belongs to the closed beta.
No Firebase, beta, public app/site deployment, UI components, graphics or copy.
Stop for owner confirmation if a change to visible application behaviour is needed.
Existing unrelated frontend changes are preserved and excluded from cloud packages.

## Baseline evidence

- ICON run `20260908T000000Z`: all 215 municipality objects plus manifest stored,
  hashes/metadata/schema independently verified read-only. `latest` still points
  to `20260907T120000Z`. The failed worker lost the underlying error; its exact
  historical cause cannot be recovered from existing logs.
- CAMS 05 UTC can legitimately lack the full 97 lead-hour selection. At 10 UTC,
  the plan passed and ADS accepted the request; the worker stopped after 45 s.
  Published time at the 15 UTC resume does not prove ADS needed five hours.
- Acquisition schedules stay ICON `0 6,18 * * *`, CAMS `0 5,10,15,20 * * *`, UTC.
- Baseline job limits: ICON 900 s / retry 0; CAMS 600 s / retry 0.
- Baseline ICON image digest:
  `d33da939bb659d395a6da5da9dbfa6287013db6c1dfc0c070e61b47e06055bc4`.

## Decisions

- Preserve the immutable-object/verified-manifest/conditional-latest publication
  design. No pointer is advanced before complete validation and read-back.
- Keep typed, secret-free errors with stage, object/municipality, HTTP status,
  reason and final outcome. Do not log SDK exception bodies or signed URLs.
- CAMS preferred recovery: short Cloud Run probes/completion coordinated by one
  pilot-only Workflows workflow. Keep the four scheduler times; only its target
  changes when stage 3 has passed tests. Workflows waits without an idle worker.
  No ADS credentials in the workflow; no Cloud Tasks or new HTTP worker service.
- ICON/CAMS usability limits must not alter immutable v1 metadata or bypass
  integrity/revocation rules. The owner's latest instruction supersedes the
  earlier ICON 48 h age / 24 remaining-hour proposal: ICON fallback uses only
  actual future samples, minimum 12 and maximum 48. An independent 48 h age
  cap would incorrectly reject the last 12–23 available samples of a validated
  72 h run. The pilot usage policy is separate from the signed v1 contract.
  CAMS recovery/usability changes remain pending, outside this fallback step.
- Monitoring deadlines are operational and configurable, not provider SLAs.
  CAMS incompleteness at 05 UTC is informational; proposed warning 11 UTC and
  critical 16 UTC, subject to observations with the repaired recovery path.
  ICON proposed warning +30 min / critical +60 min after each scheduled window.

## Rollout gates

1. Diagnostics: targeted offline tests and Linux build succeeded; not deployed.
2. ICON recovery: not started/deployed.
3. CAMS recovery: architecture reviewed; not started/deployed.
4. Fallback: owner reprioritized the client-only 12–48 future-sample change;
   implemented and tested locally (see `PILOT_ICON_FALLBACK_2026-09-08.md`).
   No CSS/JSX/copy changes or deployed APK. CAMS 72 h policy remains pending.
5. Monitoring: availability audit completed; not started/deployed.

Each release uses an explicit source allowlist, unique image tag and deployed
digest. Record the prior digest and verify actual job configuration after update.
Do not execute a normal worker merely to test diagnostics: that can consume a
scheduled acquisition slot prematurely. Use offline tests or explicit recovery.

Diagnostic build `f195cfe4-71a4-4b76-9256-a9424d36a73a` succeeded with image
digest `3f71762c531d2d339cb22a568f1fc062ae1d12467f6a421f62eaee685ad9b36a`.
No jobs were updated: cloud stages are on hold while implementing the owner's
more specific client fallback request. Schedulers and closed beta unchanged.

## Test environment

Isolated temporary Python environment:
`C:/Users/LOCAL_USER/AppData/Local/Temp/meteofriul-pipeline-tests-20260908`.
Cloud Linux image is authoritative for native ecCodes tests; that package is
absent in the Windows base environment. No global Python packages were changed.

## Sources for availability / orchestration

- [Regional CAMS documentation](https://confluence.ecmwf.int/spaces/CKB/pages/202173092/CAMS%2BRegional%2BEuropean%2Bair%2Bquality%2Banalysis%2Band%2Bforecast%2Bdata%2Bdocumentation)
- [ADS catalogue](https://ads.atmosphere.copernicus.eu/datasets/cams-europe-air-quality-forecasts?tab=overview)
- [ICON-2I catalogue](https://dati.agenziaitaliameteo.it/dataset/previsioni-meteorologiche-modello-icon-2i)
- [Cloud Run job connector](https://docs.cloud.google.com/workflows/docs/reference/googleapis/run/v1/namespaces.jobs/run)
- [Cloud Run pricing](https://cloud.google.com/run/pricing)
- [Workflows pricing](https://cloud.google.com/workflows/pricing)
