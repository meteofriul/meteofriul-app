# Separate national weather pilot

This package adds the experimental national ICON v2 transport and acquisition
only in `meteofriul-pilot-20260906`, `europe-west1`. It does not modify the beta
project `meteo-friul`, regional service `pilot-weather`, regional job `pilot-icon`,
CAMS, UV, or their schedules. No cloud operation is performed by the build tests.

## Input and build gates

The checked-in national catalog is pinned by its canonical self-hash
`ee856c27ec135be45c4c7eaaf946158fdfc61bc83135cf9b6fbbce892ce3cf0d` and the exact count
7,894. The public, approved ISTAT capoluogo artifact is packaged at
`national-assets/forecast-points.json` (4,975,625 bytes):

- file-byte SHA-256: `c0977fafef85276e1d29cc79891f95f9a1bf4d8388ecf63d73798b7880c94342`;
- canonical self-hash, excluding its own hash field:
  `f9d36d88a7724822b7eac2b6810b6a8e6dc9890ed6dad16a674dec68ee5aa038`;
- approved point-set SHA-256:
  `7993c58d891592e04df845c7fc7f9ef77471cd358db414e160ab5b73e27852ac`.

`python national_cloud_assets.py` verifies bytes, complete point provenance,
approved status and catalog agreement. The Docker build runs this same gate.
To stage the existing approved local artifact create-only:

```powershell
py -3.13 -B experiments/weather_autonomy/national_cloud_assets.py --stage-points "$env:TEMP/meteofriul-national-full-20260920-b/forecast-points.json"
```

Build from the canonical repository root with the dedicated allowlist. Supply an
explicit project, region and unique tag; never rely on the default gcloud project:

```powershell
gcloud builds submit . --project=meteofriul-pilot-20260906 --region=europe-west1 --config=experiments/weather_autonomy/national-cloud-build.yaml --ignore-file=experiments/weather_autonomy/national-cloud-package.gcloudignore --substitutions=_TAG=national-pilot-20260921
```

The allowlist includes only pipeline Python, the national Dockerfile and the two
public national assets. It excludes credentials, local databases and source GRIB.
The build performs offline national integrity, resolver, publication, worker and
GCS tests with Docker `--network=none`. Deploy only the successful immutable image
digest, independently to the reader and job.

## Resource and IAM contract

Suggested first measured shadow configuration:

| Resource | Identity and limits |
| --- | --- |
| Cloud Run service `pilot-national-weather` | Dedicated `pilot-national-reader` service account, 1 CPU, 2 GiB, min 0 / max 1 instance, concurrency 2, request timeout 300 s, CPU boost off |
| Cloud Run job `pilot-national-icon` | Dedicated `pilot-national-icon` service account, 1 CPU, 2 GiB, 1 task, parallelism 1, retry 0, timeout 1,800 s for the first measured run |
| Future scheduler `pilot-national-icon-refresh` | Dedicated scheduler identity, invoker only on this job, retry 0; two UTC slots at 06:00 and 18:00 after manual success |

The previous local benchmark was about 222 seconds for 1.109 GB of input and
655 MB peak working set. That excludes cloud publication of 644 immutable objects
and full readback. The initial 1,800-second bound is explicit measurement headroom,
not an expected duration or cost guarantee. Reduce it from observed successful
acquisition/publication timing. Reader startup loads only pointer, manifest and
index; the first municipality resolution adds its one block. Each requested block
is checked against the committed hashes and the full v2 cell/time/metadata rules.
Its LRU is bounded to 16 blocks / 16 MiB per retained run. On the real local artifact,
catalog + manifest + index took 1.395 s; adding first Roma resolution and block took
1.445 s total. These are local CPU/file measurements, not cloud latency. Measure the
four-object GCS path and cold start before setting client expectations.

`GCSObjectStore` adds `pilot/` automatically. All prefixes below are actual GCS
object names in the existing private pilot buckets:

- reader: only `storage.objects.get` under data bucket
  `pilot/weather/v2/icon2i/`; no list, state, writes, ADS or v1 access;
- job: GET/CREATE under data `pilot/weather/v2/icon2i/` and state
  `pilot/state/national-icon/`; replacement (`storage.objects.delete`, required
  by GCS to replace existing objects) only for the exact data object
  `pilot/weather/v2/icon2i/pilot.json`; no delete on run objects;
- scheduler: job invoker only, no storage permissions;
- no Secret Manager permission is needed: ICON is an anonymous public source.

Merge the additional prefix from `national-cloud-data-retention.json` into the
existing bucket lifecycle policy. Do not replace existing v1 lifecycle rules with
that fragment. Keep the pointer excluded; retain immutable runs for 30 days.
Private national state also needs bounded operational retention before extending
the trial (dispatch claims and completed run mapping/intent artifacts).

## Reader and worker commands

Reader URL:
`https://pilot-national-weather-335641913741.europe-west1.run.app`.
The image CMD starts Gunicorn on port 8080, one worker, two threads, timeout 300,
and disables application access logs. Set
`GOOGLE_CLOUD_PROJECT=meteofriul-pilot-20260906`. The HTTP Host and browser origins
are exact allowlists. Public model data does not require a bearer token; CORS is
not authentication. Cloud Run platform request logs are separate from application
logs; assess their retention because resolver URLs contain municipality names.

Job overrides: command `python`, argument `national_cloud_worker.py`, environment:

```text
GOOGLE_CLOUD_PROJECT=meteofriul-pilot-20260906
PILOT_NATIONAL_ACQUISITION=experimental-approved
```

Cloud Run must supply `CLOUD_RUN_JOB=pilot-national-icon` and an execution name
beginning `pilot-national-icon-`; the module fails before opening storage otherwise.
The explicit profile flag acknowledges the already authorized experimental pilot
profile. It does not authorize public production or official-alert use.

Each UTC AM/PM slot has a create-only claim. A separate execution in a claimed slot
does not repeat acquisition. The job first verifies any existing published run,
then discovers a newer complete source run before downloading any GRIB fields.
The real decoder checks all 14 variables, 73 times and 7,894 approved points. It
retains source/mapping hashes privately; no synthetic builder is on this path.
All input bytes are streamed with the existing bounded source limits.

A per-run intent freezes generation time before acquisition. Partial immutable
uploads can only be reconciled with identical bytes. A fully written manifest
is a durable checkpoint and is reused without downloading the source again.
An interrupted source acquisition before that checkpoint may need a fresh source
download in a later slot; this first implementation does not persist GRIB files
or field matrices. Failed runs preserve the last verified pointer. Investigate a
failure before attempting another execution in the same slot: a different
execution is deliberately a no-op, not an automatic claim takeover.

## Optional seed from the already verified local run

The existing local bundle remains only a seed, not ongoing freshness. The seed
command accepts exactly the reviewed `20260920T000000Z` manifest and mapping,
checks every document again, and rejects it after 2026-09-22 13:00 UTC when fewer
than 12 future hourly samples remain. Skip seeding and run the fresh job if expired.
Use scoped ADC credentials, or privately pipe a short-lived current gcloud token:

```powershell
$env:GOOGLE_CLOUD_PROJECT = 'meteofriul-pilot-20260906'
gcloud auth print-access-token --project=meteofriul-pilot-20260906 | py -3.13 -B experiments/weather_autonomy/national_cloud_seed.py --bundle-dir "$env:TEMP/meteofriul-national-full-20260920-b/bundle" --mapping "$env:TEMP/meteofriul-national-full-20260920-b/mapping.json" --confirm-pilot-shadow-seed --access-token-stdin
```

The token is consumed from stdin and never printed or written to a file. This
command neither logs in nor changes the global gcloud project. It publishes only
the v2 pointer and immutable namespace through the same full-readback publisher.

## Publication and validation

`pilot.json` is promoted only after block/index writes, manifest-last commit and
complete readback. GCS generation CAS prevents concurrent pointer replacement;
lost responses are reconciled by exact bytes. Run regression and conflicting
immutable bytes are rejected. A previous verified run descriptor remains in the
pointer, so a client resolving before a promotion can still fetch its block.
The reader swaps newly verified manifest/index metadata atomically, checks the
pointer at most every 30 seconds and keeps one prior run on demand. It verifies
only the requested blocks; global completeness remains a mandatory publisher gate.

The pointer/resolve/search wire shapes intentionally retain the existing
`experimental_local_pilot_only` labels and `local_pilot_*` kinds for compatibility
with the pilot client contract. They describe the experimental pilot contract,
not the network transport. They must not be relabeled as a production contract.

`/healthz` is process liveness only. Data readiness requires HTTP 200 from
`/weather/v2/icon2i/pilot.json`, a successful exact resolver and a verified referenced
block. Dynamic endpoints reject expired coverage with 503. Immutable objects keep
their stable hashes and long cache lifetime. Failed refresh or corrupt/missing data
must not return invented values or advance the pointer.

Before APK cutover, exercise real-clock resolution for several regions, ambiguous
names, search, block gzip/hash/ETag, current hourly data and >=12 future hours; also
check old block fetch across a pointer promotion. Confirm regional v1 endpoints
are unchanged. The client build and APK cutover are a separate owner workflow.
No recurring schedule should be enabled until the fresh manual job succeeds and
readback is verified. The existing FVG multi-run comparison and profile-review
requirements remain gates for any broader production rollout.
