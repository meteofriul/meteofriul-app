# Retiring the parallel pilot cloud project — 26 September 2026

The historical project `meteofriul-pilot-20260906` was a side-by-side validation
environment for the private local-pilot APK. It is not the production project
and must no longer be used by the official app or the canonical browser preview.

## Cutover evidence

- Official Cloud Run services for Weather, National Weather, Events and
  Community are active in project `meteo-friul`.
- The official Events endpoint returned the current complete catalogue for
  Pordenone; the official Community endpoint returned the current Pordenone
  scope by ISTAT code.
- No Cloud Run service, Cloud Run job or Cloud Scheduler job in `meteo-friul`
  references project `meteofriul-pilot-20260906`, project number `335641913741`
  or a `pilot-*.run.app` endpoint.
- The browser preview on port 5174 now proxies Events to
  `meteofriul-events-49007668366.europe-west1.run.app`. The old Events service
  last received a browser request at 19:48 UTC; the official service received
  the post-cutover browser request at 20:05 UTC.
- The private Community credential bridge and its Android local-pilot plugin
  were removed. The `-CommunityCloudStore` launcher option now fails closed.
- Weather and national Weather cloud bindings already used the official
  services and remain unchanged.

No Play AAB was produced as part of this cutover. Firebase/App Check policy was
not changed.

## Pre-deletion inventory

At audit time the project was still active and contained:

- Cloud Run services: `pilot-weather`, `pilot-national-weather`,
  `pilot-events`, `pilot-community`;
- no Cloud Run jobs and no Cloud Scheduler jobs;
- buckets: build, Cloud Build, state, data and Community;
- Firestore `(default)` in `europe-west1`, with deletion protection enabled;
- Artifact Registry repository `pilot` (about 1.08 GB);
- Secret Manager secret `pilot-ads`;
- pilot reader, writer, worker, scheduler, build and Community service accounts.

These resources were historical data and deployment infrastructure, not
dependencies of the canonical app.

## Final decommission completed

On 26 September 2026 the owner confirmed that the parallel pilot path and its
historical data were no longer required. Before deletion, the active gcloud
identity was verified as `meteofriul@gmail.com` and a guard confirmed the exact
target:

- project ID: `meteofriul-pilot-20260906`;
- project number: `335641913741`;
- lifecycle state before the operation: `ACTIVE`;
- target different from the official project `meteo-friul`.

Google Cloud accepted the project deletion request. The resource-manager
read-back reports lifecycle state `DELETE_REQUESTED`. This single project-level
operation schedules the four pilot services, five buckets, Firestore database,
Artifact Registry images, secret and pilot-only service accounts for deletion.
Recovery remains possible only during Google Cloud's limited project recovery
window; no recovery is planned.

After the deletion request, the following official endpoints were checked and
all returned HTTP 200:

- tagged official API: `/api/weather/official-alerts`;
- official Events: `/api/local/events` for Pordenone;
- official Community: `/api/community/reports` for ISTAT scope `093033`;
- official FVG Weather: `/weather/v1/icon2i/latest.json`;
- official National Weather: `/weather/v2/icon2i/resolve.json` for Roma.

No Play AAB was produced. Firebase, App Check and the official `meteo-friul`
project were not modified by this decommission.

Do not modify the official `meteo-friul` project while performing this cleanup.
