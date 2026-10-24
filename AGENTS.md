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
