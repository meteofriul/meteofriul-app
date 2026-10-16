# Pilot ICON fallback — 8 September 2026

## Authorized scope

Client-side pilot only. The owner's latest minimum is **12 real future hourly
samples**, superseding the earlier 24-hour proposal. Maximum 48. No CSS, JSX,
visible labels, scheduler, Firebase, beta, CAMS acquisition or cloud deployments.
Existing unrelated worktree changes were preserved.

## Invariants

- A normal valid run supplies up to 48 genuinely future timestamps.
- If current cannot be used, only a previous run named by a verified pointer
  may be tried. Network failure can reuse previously verified raw objects.
- The window contains only existing timestamps at or after the evaluation time,
  in UTC order. Below 12 it is rejected. No interpolation, duplicated samples,
  repeated last values, artificial fill, or past samples to reach a quota.
- The current-condition sample remains separate (at most one hour old).
- ICON's immutable 73-sample / 72-hour contract, manifest hashes, municipality,
  catalogue, source identity and revocation validation are unchanged.
- A separate pilot usage policy (`iconForecastWindow.js`) governs 12–48. The
  legacy client retains its original freshness policy unless explicitly opted in.
- Daily extrema still use the full validated timeline, including morning hours.
- CAMS expiry does not invalidate usable ICON. CAMS's own usability threshold is
  unchanged; its existing unavailable representation is reused, without new copy.

## Audit and changes

| Layer | Previous assumption | Change |
| --- | --- | --- |
| Raw client | Requires 48 residual hours before fetching objects | Separate opt-in pilot use policy; signed metadata validation unchanged |
| Adapter | Requires exactly 48 mapped rows | Real future rows, minimum 12 / maximum 48; independent current sample; verified previous selection |
| Runtime cache | 24-hour age cap, at least 48 rows, expires whole bundle with CAMS | Re-project real cached samples at current time; separate ICON and CAMS eligibility |
| Bulletin view model | Upper bound removes the 48th strictly future sample | Pilot-only maximum count after future filter; legacy selection unchanged |
| Home, forecast, ribbon, charts | Already accept shorter nonempty arrays | Regression tests only; no component changes |

The existing chart label “Finestra di 24 ore” remains unchanged, even for a
shorter chart window, per the prohibition on JSX/copy changes. No data are
generated to fill that nominal maximum. The existing Options diagnostic age
label is not an eligibility gate and was deliberately left unchanged.

## Cache safety

- Forced refresh still tries the network. Only network/408/429/5xx failures may
  reuse validated ICON raw bytes; abort/auth/404/schema/hash failures do not.
- Known hard errors quarantine the affected derived cache. Revocations are
  observed before replacement objects load and restored from the validated raw
  pointer on reopening; a failed replacement cannot resurrect a revoked run.
- A successful same-object refresh may extend a shorter cached window only if
  actual overlapping samples agree. A new run can replace the fallback.
- Reopening and advancing the clock never freeze the old temperature: the
  current sample must be present in the verified cached timeline.

## Verification

Automated coverage includes 48, 37, 36, 24, 12 and 11 future samples; exact and
mid-hour boundaries; DST; offline reopening; return of the newer run; ICON with
CAMS missing/expired; corruption, auth, revocation and cache isolation.

The opt-in `iconFallback.live.test.js` retrieves the real pilot ICON dataset
through the local proxy and then tests isolated in-memory/persisted cache copies
with simulated clocks and network failure. It does not modify the browser's
cache, cloud objects or the operational clock. Five integration cases passed.

Production compilation was checked in a unique operating-system temporary
directory; no app/site publish or APK regeneration was performed. Pilot/Android
isolation guards passed.

Final regression gate:

- 350 tests passed across the 11 focused policy/client/adapter/runtime/consumer
  suites; 32 API-routing tests passed separately; 10 pilot isolation guards passed.
- Five real-dataset/offline integration cases passed after the cache changes.
- Full frontend suite: **3252 passed, 5 failed, 11 skipped** (434 files).
  Remaining failures are unrelated existing UI expectations: `appShellCopy`
  and `uiShellCopy` still expect “Meteo” instead of “Timp”; `AppRoutes` expects
  “Live” instead of “Territorio”; `EventsView` expects a list excerpt; and
  `weatherForecastCss` prohibits the already existing horizontal ribbon.
  Those components, copy and CSS were not changed for this fallback request.
- Scoped ESLint and `git diff --check` passed.
- No commit, APK installation, beta update, cloud job update or scheduler change.
