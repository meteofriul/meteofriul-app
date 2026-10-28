# Meteo Friûl workspace instructions

## Mandatory release preparation

- Before preparing dependencies, changing a release version or starting the Play builder, read [the mandatory build prevention rules](docs/operations/ANDROID_BUILD_PREVENTION_RULES.md). They apply to every resumed release attempt too. Never copy dependencies with recursive exclusions for build/dist/lib, use cross-worktree node_modules junctions for release builds, or consume a version before the dependency and provenance preflight.

## Canonical workspace

- The canonical project root is `F:\proggetto Meteo Friul App\meteo FRIUL`.
- Directories with similar legacy names are historical archives, never runtime
  dependencies or valid launch targets.
- Validate the pilot UI only through `scripts/start-local-weather-pilot.ps1` on
  port `5174`. The generic `start-dev.ps1` flow is ordinary engineering mode,
  not the pilot app.
- Run `scripts/test-canonical-workspace-cleanliness.ps1` before establishing a
  new canonical clone or delivery baseline.

## App map and coordinated agents

- The four primary tabs are defined in `frontend/src/app/appConfig.js` and
  routed in `frontend/src/app/AppRoutes.jsx`: HOME (`home`), METEO (`weather`,
  with `weather` / `bulletin` / `live` routes), EVENTI (`events`), and SCOPRI
  (`discover`). `almanac` and `settings` are additional routes, not primary tabs.
- HOME: `frontend/src/features/home/` renders current local weather, the scene,
  hourly and local summaries, official alerts/bulletin, and previews of events,
  almanac and territorial content. Its data controller consumes other sections'
  services. Coordinate changes to their sources with the relevant specialist.
- METEO: `frontend/src/features/weather/` is Previsioni;
  `frontend/src/features/bulletin/` is the official ARPA FVG/OSMER bulletin and
  alerts; `frontend/src/features/live/` is Tempo Reale (reports, radar, webcams).
  Radar code also exists in the bulletin feature. Keep the three information
  types distinct while assigning one functional owner to the tab.
- EVENTI: `frontend/src/features/events/`, `frontend/src/services/eventsApi.js`,
  `backend/app/api/events.py`, `backend/app/events/` and related event services
  cover catalog, sources, schedules, filters, cards and detail flows.
- SCOPRI: `frontend/src/features/discover/` and `features/almanac/`,
  `frontend/src/domain/discover/` and `domain/almanac/`,
  `frontend/src/data/discover/` and `data/almanac/`, and the related curation
  scripts provide territorial, seasonal and small editorial cards. New copy
  needs its own assignment; the current organization task adds no content.
- `Community` is wider than reports: `features/live/` handles reports and their
  interactions, while `features/community/`, `features/settings/`, and backend
  community modules also handle identity, reputation, moderation, persistence
  and privacy. Do not equate the name with one screen or rename code from this
  map alone.
- The main chat scopes work, selects only useful specialists from
  `.codex/agents/`, assigns each changed file to exactly one editor, reviews
  cross-tab effects, gathers evidence and returns one result. A section may
  span frontend, backend, data and scripts; do not move sources for ownership.
  For broad METEO work, keep `meteo` accountable and delegate bounded file
  groups only with explicit assignments.
- The main chat assigns an explicit owner before changes to shared files:
  `frontend/src/app/` (routing), `frontend/src/ui/` (shell/theme),
  `frontend/src/features/settings/`, `features/community/`,
  `features/promotions/`, shared `frontend/src/services/`, `domain/` and
  `copy/`, location/notification code, backend common APIs/services, project
  configurations, dependencies, Android wrapper, contracts, and `scripts/`.
  Other specialists may analyze or review the same file, but only its assigned
  editor changes it. `build_verifica` owns verification evidence; it changes
  build rules or scripts only when separately assigned.
- `controllo_job` audits scheduled jobs, bounded execution logs, published data
  freshness and existing monitoring in read-only mode. Use the
  [job inventory](docs/operations/JOBS_INVENTORY.md); distinguish repository
  configuration, deployed configuration, execution results and data results.
  The profile does not grant cloud permissions or create a periodic monitor.
  Verify actual agent availability; if invoked through a generic agent that
  reads the profile, report that fallback explicitly. Never execute/retry jobs,
  change schedules or policies, deploy or send notifications during an audit.
  The coordinator assigns any later corrections to `meteo`, `eventi` or the
  relevant shared-service owner; `build_verifica` verifies their evidence.
- For structure and prescribed tools/commands, use [README](README.md#architettura)
  and [local development](README.md#sviluppo-locale). From the repository root,
  use `scripts/start-dev.ps1` for ordinary engineering and
  `scripts/start-local-weather-pilot.ps1` for the pilot. Run `npm test`,
  `npm run lint`, and `npm run build` from `frontend/`; run the Python tests
  and `compileall` from `backend/`, as shown in [Test e qualità](README.md#test-e-qualità).
  `frontend/package.json` prescribes Node `22.17.1` and npm `10.9.2`;
  README prescribes Python `3.13`, PowerShell on Windows and Android Studio
  JBR 21. The Android wrapper pins Gradle `8.14.3` and AGP `8.13.0`.
- Consult [runtime inventory](UI3_RUNTIME_DATA_INVENTORY.md),
  [Live contract](LIVE_VIEW_FUNCTIONAL_CONTRACT.md),
  [Eventi sources](EVENTI_DATA_SOURCE_AUDIT.md), and
  [Almanacco/Scopri contract](ALMANAC_DISCOVER_CONTENT_CONTRACT.md) for
  section-specific behavior. The [Android build prevention rules](docs/operations/ANDROID_BUILD_PREVENTION_RULES.md),
  [Play runbook](docs/operations/PLAY_AAB_RUNBOOK.md), and
  [Web/Android parity runbook](docs/operations/WEB_ANDROID_RELEASE_PARITY.md)
  remain authoritative for build and publication. Historical reports are
  evidence of their dated checks, not standing instructions or current status.
- Preserve the external Git privacy guard and active hook. Follow the existing
  [Community privacy contract](docs/operations/COMMUNITY_PRIVACY_DATA_SAFETY_HANDOFF.md)
  and publication gates in the runbooks; do not include
  private identifiers, precise location or signing material in reports or
  commits. The landing page and content-management panel are related external
  projects. Native iOS is a future goal, not a reason to add directories here.

## Branch and release workflow

- Treat `main` as the verified and promoted baseline.
- GitHub protects `main` and requires a pull request. For an authorized update
  of remote main, push the verified workstream branch, check the PR CI, merge
  through the PR, then check main CI. Do not attempt a direct push to main or
  bypass the protection. Markdown-only state updates use a documentation PR.
- Start each distinct feature, hardening activity, or release workstream from
  the current `main` in a dedicated `codex/` branch.
- Multiple changes and test builds that belong to the same workstream remain on
  the same branch; do not create a branch for every APK or build attempt.
- Merge or promote the work to `main` only after the relevant automated tests
  and real-device checks pass.
- Keep unrelated or independently risky workstreams, including R8,
  edge-to-edge, large-screen, notifications, and sponsor-contract changes, on
  separate branches.
- Returning to `main` must not delete, overwrite, or accidentally carry across
  ignored local assets such as private signing keys or build artifacts.
- Never generate or upload a Play AAB without the user's explicit
  authorization.
- When alignment, promotion, build, upload, publication or verification changes
  the recorded state, update README, the release status and the Web parity
  record in the same workstream. Distinguish source code, immutable artifacts,
  internal testing and public deployments; retain dated evidence and open checks.

## Web and Android release parity

- The Web app is the supported browser experience for iPhone users while no
  native Apple app exists. Keep its approved UI, languages, weather, events,
  Community and data contracts aligned with the official Android release.
- Prepare Web and Android from the same approved frontend commit, without TEST
  branding, fixtures, loopback endpoints or TEST-only service exclusions.
- Every Android release must include a Web parity review and publication plan;
  matching version numbers alone do not prove matching code or behavior.
- Record Web artifact hashes, source commit, endpoint bindings, deployed state,
  browser checks and remaining Safari/iPhone checks in the release evidence.
- Verify Safari on a real iPhone (browser and Add to Home Screen) before claiming
  iPhone compatibility. Desktop resizing does not replace that check.
- Follow [the Web parity runbook](docs/operations/WEB_ANDROID_RELEASE_PARITY.md).
  Web preparation, Web publication, AAB generation and Play publication remain
  separate actions requiring their respective authorization.

## Android release quality standard

- Product orientation policy: smartphones use portrait only, with no rotation
  setting in the app. Keep large displays (smallest width >= 600 dp) and
  multi-window adaptive; do not impose a global portrait manifest lock.
- For every Android release, follow the mandatory Android checks in
  [the Play runbook](docs/operations/PLAY_AAB_RUNBOOK.md#controlli-android-obbligatori-per-ogni-release).
- Always assess all four areas: edge-to-edge/insets, deprecated system-bar
  APIs, orientation/resizability/large screens, and R8/resource optimization.
  Reassess current Google guidance after target SDK or Android toolchain updates.
- Record the candidate commit and artifact identity, test environment, results,
  evidence and unresolved findings. Compilation alone is not a runtime test;
  a debug/TEST APK alone is not proof of minified release behavior.
- Distinguish Google's mandatory requirements from recommendations. Never mark
  untested cases or dependency warnings as resolved without evidence. Record
  any owner-approved deferral of a recommendation and its follow-up work.
- Use Android 15/16 emulator coverage plus a supported earlier Android version;
  keep the existing real-device rule unless the owner explicitly accepts an
  emulator substitute for the specific work. Never install on a phone implicitly.
- Code promotion, AAB generation, Play upload and production publication remain
  separate actions; completing this checklist does not authorize the next action.

## GitHub Actions usage

- The full CI runs automatically for pushes to `main` and pull requests whose
  base is `main`; ordinary pushes to `codex/**` branches do not start it.
- Use a pull request or the manual `workflow_dispatch` trigger when a remote CI
  result is required before promotion. Always run the relevant local checks
  first.
- Markdown-only changes intentionally skip the full CI. Validate their diff,
  links, and current-state claims locally instead.
- Do not broaden branch triggers or add scheduled GitHub-hosted jobs without
  the user's explicit authorization and a review of Actions-minute impact.
- After promoting a commit to `main`, verify that only the expected CI run is
  active and cancel any redundant or stuck duplicate after confirming an
  equivalent run is already green.

## Frontend commands on Windows

- Always load the Vite/Vitest configuration natively. Use the repository scripts, which already pass `--configLoader native`, or add that flag explicitly to targeted commands such as `npx vitest --configLoader native run ...`.
- Do not first run `npx vitest run` without `--configLoader native`: this workspace repeatedly hits `EPERM` while Vite writes `frontend/node_modules/.vite-temp`, and that failure is environmental rather than a test failure.
- For ad-hoc preview builds, do not use a new output directory inside `frontend`; Windows may reject its creation with `EPERM`. Use a unique directory under the operating-system temporary directory instead.
- When Codex builds the Android owner preflight, run `npm run android:sync` and the scoped Gradle task outside the sandbox from the first attempt. Sandboxed writes to `frontend/dist` and Android build outputs can fail with misleading Windows `EPERM` errors even when no process holds the files.
- On an Android `EPERM`, do not start a loop of deleting `frontend/dist`, copying individual assets, or inventing another in-workspace output directory. Retry the exact repository command once outside the sandbox. If that also fails, stop and inspect the exact process/path before removing only a resolved generated directory.
- The guarded Play AAB is different from the owner debug preflight: run `scripts/build-play-aab.ps1` outside the sandbox and do not precede it with a manual `android:sync`. The script already builds Web assets in a unique OS temporary directory, verifies the runtime endpoint, and mirrors them into Android.
- Treat the existing chunk-size warning as non-blocking unless the task specifically concerns bundle size.

## Cloudflare account safety

- This workspace is bound locally to the Wrangler auth profile `meteofriul`.
- Before any Cloudflare mutation or Pages deployment, run `npx wrangler whoami` from the workspace root and require account ID `b74cf20dd75712b35313b69c191c97d5` (`meteofriul@gmail.com`). Stop if it differs.
- The expected Pages projects are `meteofriul-app-bcee09e` for `meteofriul.app` and `meteofriul-site` for `meteofriul.it`.
- Do not log out, overwrite, or reuse the global/default Wrangler profile; other workspaces use separate named profiles.

## Pilot branding contract

- Treat every user-approved pilot icon as one atomic branding cutover, never as a launcher-only edit.
- The same version must update the adaptive color, monochrome and background launcher layers, the native splash, and the in-app Home/Settings mark through `scripts/package-pilot-launcher-layers.ps1`.
- Use a new versioned Web mark path to defeat WebView cache, regenerate and pin the inventory/hashes, and keep main/beta, Play, PWA/favicon, legacy launchers and notification icons unchanged unless the user explicitly expands scope.
- Do not call the update complete until the guarded build passes, the APK is installed with `adb install -r`, app data preservation is checked, and launcher, splash and Home are each verified on the real phone.
