import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { UV_CACHE_KEY, UV_CANDIDATE_CACHE_KEY } from "../features/weather/uvForecastRuntime";
import {
  CAMS_AIR_FIELDS,
  CAMS_POLLEN_FIELDS,
  encodeCamsHourlyCacheV2,
} from "./camsHourlyCache";
import { harness, RUN_A, RUN_B, START } from "./camsRecoveryTestFixtures";
import {
  fetchLocalWeatherV1Bootstrap,
  LOCAL_WEATHER_V1_CATALOG,
} from "./localWeatherV1Adapter";
import {
  getLocalWeatherV1BundleCacheKey,
  getLocalWeatherV1CamsFamilyDecisionCacheKey,
  readLocalWeatherV1PersistedBundle,
} from "./localWeatherV1Runtime";
import {
  canonicalJsonStringify,
  createWeatherV1Client,
  sha256Hex,
} from "./weatherV1Client";

const LOCATION = "Pordenone";
const CAMS_TIMEOUT_MS = 25;

function runId(runAt) {
  return runAt.replaceAll("-", "").replaceAll(":", "");
}

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((settle, fail) => {
    resolve = settle;
    reject = fail;
  });
  return { promise, reject, resolve };
}

function jsonResponse(body, etag = '"runtime-revocation"') {
  const bytes = new TextEncoder().encode(body);
  return {
    status: 200,
    headers: {
      get(name) {
        const normalized = String(name).toLowerCase();
        if (normalized === "content-type") return "application/json";
        if (normalized === "etag") return etag;
        return null;
      },
    },
    async arrayBuffer() {
      return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
    },
  };
}

function familySnapshot({
  activeRun = RUN_B,
  disabledRuns = [RUN_A],
  publishedAt = "2026-09-10T02:00:00Z",
  revision = 2,
} = {}) {
  return {
    revision,
    published_at: publishedAt,
    latest: { source_run_id: runId(activeRun) },
    disabled_run_ids: disabledRuns.map(runId).sort(),
  };
}

function familyPointer(snapshot = familySnapshot()) {
  const releaseBody = canonicalJsonStringify({ deliberately: "unavailable" });
  const activeRunId = snapshot.latest.source_run_id;
  return canonicalJsonStringify({
    schema_version: 1,
    kind: "meteofriul.weather.cams_family_latest",
    family: "cams",
    revision: snapshot.revision,
    published_at: snapshot.published_at,
    catalog: LOCAL_WEATHER_V1_CATALOG,
    latest: {
      source_run_id: activeRunId,
      release_path: `runs/${activeRunId}/release.json`,
      release_json_bytes: new TextEncoder().encode(releaseBody).length,
      release_sha256: sha256Hex(releaseBody),
    },
    previous: null,
    disabled_run_ids: [...snapshot.disabled_run_ids],
  });
}

function withFamilySnapshot(bundle, snapshot = familySnapshot()) {
  const result = JSON.parse(JSON.stringify(bundle));
  const family = {
    revision: snapshot.revision,
    published_at: snapshot.published_at,
    active_run_id: snapshot.latest.source_run_id,
    disabled_run_ids: [...snapshot.disabled_run_ids],
  };
  result.current.source.cams.evidence.family = { ...family };
  result.forecast.source.cams.evidence.family = { ...family };
  return result;
}

function withVerifiedHourlyCache(bundle) {
  const result = JSON.parse(JSON.stringify(bundle));
  const run = Date.parse(result.current.data_quality.cams_run_utc);
  const samples = Array.from({ length: 97 }, (_, hour) => ({
    valid_at_utc: new Date(run + hour * 60 * 60 * 1000).toISOString().replace(".000Z", "Z"),
    pollen_values: Object.fromEntries(CAMS_POLLEN_FIELDS.map(([, uiKey]) => [uiKey, hour])),
    pollen_quality_flags: Object.fromEntries(CAMS_POLLEN_FIELDS.map(([id]) => [id, []])),
    air_values: Object.fromEntries(CAMS_AIR_FIELDS.map((id) => [id, 100 + hour])),
  }));
  result.current.cams_hourly_cache = encodeCamsHourlyCacheV2({
    municipality_istat: result.current.data_quality.municipality_istat,
    catalog_sha256: LOCAL_WEATHER_V1_CATALOG.sha256,
    run_utc: result.current.data_quality.cams_run_utc,
    generated_at_utc: new Date(run + 60 * 60 * 1000).toISOString().replace(".000Z", "Z"),
    fresh_until_utc: new Date(run + 24 * 60 * 60 * 1000).toISOString().replace(".000Z", "Z"),
    usable_until_utc: new Date(run + 96 * 60 * 60 * 1000).toISOString().replace(".000Z", "Z"),
    pollen_variables: CAMS_POLLEN_FIELDS.map(([id, uiKey]) => ({
      id,
      ui_key: uiKey,
      category: "pollen",
      unit: "grains/m3",
      validation_status: "experimental_unvalidated_by_provider",
    })),
    samples,
  });
  return result;
}

function rawRevocationBundleFetcher(state, {
  iconGate = null,
  pointerGate = null,
  pointerBody = familyPointer(),
  releaseMode = "pending",
} = {}) {
  const releaseStarted = deferred();
  const rawFetch = vi.fn((url, options = {}) => {
    if (url.endsWith("/weather/v1/families/cams/latest.json")) {
      return pointerGate?.promise ?? Promise.resolve(jsonResponse(pointerBody));
    }
    if (url.includes("/weather/v1/families/cams/runs/") && url.endsWith("/release.json")) {
      releaseStarted.resolve();
      if (releaseMode === "failure") {
        return Promise.reject(Object.assign(new Error("controlled release failure"), {
          code: "TRANSPORT_FAILURE",
        }));
      }
      return new Promise((_, reject) => {
        options.signal?.addEventListener("abort", () => {
          const error = new Error("controlled release abort");
          error.name = "AbortError";
          reject(error);
        }, { once: true });
      });
    }
    throw new Error(`unexpected raw request ${url}`);
  });
  const bundleFetcher = (location, options) => fetchLocalWeatherV1Bootstrap(location, {
    ...options,
    camsTimeoutMs: CAMS_TIMEOUT_MS,
    clientFactory: (clientOptions) => {
      const raw = createWeatherV1Client({ ...clientOptions, fetchImpl: rawFetch });
      const fixtureIcon = state.clientFactory(clientOptions).icon2i;
      if (iconGate) fixtureIcon.fetchLatest.mockImplementationOnce(() => iconGate.promise);
      return { ...raw, icon2i: fixtureIcon };
    },
  });
  return { bundleFetcher, rawFetch, releaseStarted };
}

function journalBytes(state) {
  const key = getLocalWeatherV1CamsFamilyDecisionCacheKey({
    baseUrl: state.options.baseUrl,
  });
  return { key, value: state.storage.getItem(key) };
}

function expectCamsRevoked(bundle, diagnostic = { stage: "family", code: "RUN_DISABLED" }) {
  expect(bundle.current).toMatchObject({
    source: {
      icon: { status: "available" },
      cams: {
        status: "unavailable",
        diagnostic,
      },
    },
    data_quality: {
      cams_status: "unavailable",
      cams_run_utc: null,
      cams_valid_at_utc: null,
    },
    air_quality_data: null,
    pollen_data: { status: "unavailable" },
  });
}

function expectIconUnchanged(before, after) {
  expect(after.current.temperature).toBe(before.current.temperature);
  expect(after.current.source.icon).toEqual(before.current.source.icon);
  expect(after.current.data_quality.run_utc).toBe(before.current.data_quality.run_utc);
  expect(after.current.hourly_forecast).toEqual(before.current.hourly_forecast);
  expect(after.forecast.daily).toEqual(before.forecast.daily);
}

async function coldRuntime() {
  vi.resetModules();
  return import("./localWeatherV1Runtime.js");
}

async function settlePendingCams() {
  await vi.advanceTimersByTimeAsync(CAMS_TIMEOUT_MS + 1);
  await vi.runOnlyPendingTimersAsync();
}

afterEach(() => {
  vi.clearAllTimers();
  vi.useRealTimers();
});

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(START);
});

describe("durable CAMS family revocations", () => {
  it("journals a verified revocation before a pending release and restores it offline", async () => {
    const state = harness({ available: true });
    const active = await state.fetch();
    const firstJournal = journalBytes(state).value;
    const uvActive = '{"marker":"uv-active"}';
    const uvCandidate = '{"marker":"uv-candidate"}';
    state.storage.setItem(UV_CACHE_KEY, uvActive);
    state.storage.setItem(UV_CANDIDATE_CACHE_KEY, uvCandidate);
    const pending = rawRevocationBundleFetcher(state);

    const returned = await state.fetch({
      bundleFetcher: pending.bundleFetcher,
      deferCams: true,
      force: true,
    });
    await pending.releaseStarted.promise;

    const secondJournal = journalBytes(state).value;
    expect(firstJournal).toBeNull();
    expect(secondJournal).not.toBe(firstJournal);
    expectCamsRevoked(returned);
    expectIconUnchanged(active, returned);
    expectCamsRevoked(state.saved().bundle);
    expect(state.storage.getItem(UV_CACHE_KEY)).toBe(uvActive);
    expect(state.storage.getItem(UV_CANDIDATE_CACHE_KEY)).toBe(uvCandidate);

    const cold = await coldRuntime();
    const reopened = cold.readLocalWeatherV1PersistedBundle(LOCATION, {
      baseUrl: state.options.baseUrl,
      storage: { ...state.storage },
      now: () => START,
    });
    expectCamsRevoked(reopened);
    expectIconUnchanged(active, reopened);

    const offline = await cold.fetchLocalWeatherV1RuntimeBundle(LOCATION, {
      ...state.options,
      storage: { ...state.storage },
      bundleFetcher: vi.fn().mockRejectedValue(new Error("offline after reopen")),
      force: true,
    });
    expectCamsRevoked(offline);
    expect(offline.current.cache.runtime_fallback).toBe(true);
    await settlePendingCams();
  });

  it("notifies the revocation before ICON settles and keeps it through ICON failure", async () => {
    const state = harness({ available: true });
    const active = await state.fetch();
    const iconGate = deferred();
    const pending = rawRevocationBundleFetcher(state, { iconGate });
    const update = vi.fn();

    let requestSettled = false;
    const request = state.fetch({
      bundleFetcher: pending.bundleFetcher,
      deferCams: true,
      force: true,
      onCamsUpdate: update,
    });
    void request.finally(() => { requestSettled = true; });
    await pending.releaseStarted.promise;
    await vi.waitFor(() => expect(update).toHaveBeenCalled());

    expect(requestSettled).toBe(false);
    expect(update.mock.calls.some(([, lifecycle]) => (
      lifecycle?.lifecycle === "intermediate" && lifecycle?.reason === "revocation"
    ))).toBe(true);
    const quarantined = update.mock.calls.find(([bundle]) => (
      bundle?.current?.data_quality?.cams_diagnostic?.code === "RUN_DISABLED"
    ))?.[0];
    expectCamsRevoked(quarantined);
    expectIconUnchanged(active, quarantined);

    iconGate.reject(Object.assign(new Error("controlled ICON failure"), {
      code: "TRANSPORT_FAILURE",
    }));
    const fallback = await request;
    expectCamsRevoked(fallback);
    expectIconUnchanged(active, fallback);
    await settlePendingCams();
    expect(update).toHaveBeenCalledTimes(1);
  });

  it("uses the durable journal after interruption even if the old bundle bytes remain", async () => {
    const state = harness({ available: true });
    const active = await state.fetch();
    const bundleKey = getLocalWeatherV1BundleCacheKey(LOCATION, {
      baseUrl: state.options.baseUrl,
    });
    const oldActiveBytes = state.storage.getItem(bundleKey);
    const replacementFailure = Object.assign(new Error("stop after durable decision"), {
      code: "INTEGRITY_MISMATCH",
    });
    const bundleFetcher = vi.fn(async (_location, options) => {
      options.onCamsFamilyLatest(familySnapshot());
      throw replacementFailure;
    });

    await expect(state.fetch({ bundleFetcher, force: true })).rejects.toBe(replacementFailure);
    expect(journalBytes(state).value).not.toBeNull();
    // Re-create the exact crash boundary: the journal is committed, while the
    // old active and staging records still contain A.
    state.storage.setItem(bundleKey, oldActiveBytes);
    state.storage.setItem(`${bundleKey}:candidate`, oldActiveBytes);

    const cold = await coldRuntime();
    const reopened = cold.readLocalWeatherV1PersistedBundle(LOCATION, {
      baseUrl: state.options.baseUrl,
      storage: { ...state.storage },
      now: () => START,
    });
    expectCamsRevoked(reopened);
    expectIconUnchanged(active, reopened);
  });

  it("recovers a fully saved replacement delta before sanitizing its revoked base", async () => {
    const state = harness({ available: true });
    const active = await state.fetch();
    const bundleKey = getLocalWeatherV1BundleCacheKey(LOCATION, {
      baseUrl: state.options.baseUrl,
    });
    const candidateKey = `${bundleKey}:candidate`;
    const oldActiveBytes = state.storage.getItem(bundleKey);
    state.publish();
    const durableSnapshot = familySnapshot();
    const replacement = withVerifiedHourlyCache(withFamilySnapshot(
      await fetchLocalWeatherV1Bootstrap(LOCATION, {
        baseUrl: state.options.baseUrl,
        clientFactory: state.clientFactory,
        fetchImpl: state.options.fetchImpl,
        now: state.options.now,
        storage: state.storage,
      }),
      durableSnapshot,
    ));
    expect(replacement.current.data_quality.cams_run_utc).toBe(RUN_B);
    expect(replacement.current.cams_hourly_cache).toMatchObject({ version: 2 });
    const originalSetItem = state.storage.setItem;
    const originalRemoveItem = state.storage.removeItem;
    let deltaBaseBytes = null;
    let deltaBytes = null;
    let forcedFullCandidateQuota = false;
    state.storage.setItem = (key, value) => {
      let record = null;
      try { record = JSON.parse(value); } catch { /* Non-JSON writes are unrelated. */ }
      if (key === candidateKey
        && record?.kind !== "cams-delta"
        && !forcedFullCandidateQuota) {
        forcedFullCandidateQuota = true;
        const error = new Error("controlled quota for full candidate");
        error.name = "QuotaExceededError";
        throw error;
      }
      if (key === candidateKey && record?.kind === "cams-delta") {
        deltaBaseBytes = state.storage.getItem(bundleKey);
        deltaBytes = value;
      }
      if (key === candidateKey && value === "null" && deltaBytes) {
        throw new Error("controlled interruption before candidate tombstone");
      }
      if (key === bundleKey
        && record?.bundle?.current?.data_quality?.cams_run_utc === RUN_B
        && deltaBytes) {
        throw new Error("controlled interruption before candidate promotion");
      }
      return originalSetItem(key, value);
    };
    state.storage.removeItem = (key) => {
      if (key === candidateKey && deltaBytes) {
        throw new Error("controlled interruption before candidate removal");
      }
      return originalRemoveItem(key);
    };
    const replacementFetcher = vi.fn(async () => replacement);

    const retained = await state.fetch({ bundleFetcher: replacementFetcher, force: true });
    expect(deltaBaseBytes).not.toBeNull();
    expect(deltaBytes).not.toBeNull();
    expect(retained.current.data_quality.cams_run_utc).toBeNull();
    expect(JSON.parse(deltaBaseBytes).bundle.current.data_quality.cams_run_utc).toBeNull();
    expect(journalBytes(state).value).not.toBeNull();

    // Recreate an interruption immediately after the complete, byte-verified
    // delta B was saved but before its atomic promotion. Also restore the raw
    // pre-sanitation A bytes: the durable journal must still prevent A from
    // becoming presentable and preserve the exact base needed by the delta.
    state.storage.setItem = originalSetItem;
    state.storage.removeItem = originalRemoveItem;
    state.storage.setItem(bundleKey, oldActiveBytes);
    state.storage.setItem(candidateKey, deltaBytes);
    expect(JSON.parse(state.storage.getItem(bundleKey)).bundle.current.data_quality.cams_run_utc)
      .toBe(RUN_A);
    expect(state.storage.getItem(candidateKey)).toBe(deltaBytes);

    const cold = await coldRuntime();
    const reopened = cold.readLocalWeatherV1PersistedBundle(LOCATION, {
      baseUrl: state.options.baseUrl,
      storage: state.storage,
      now: () => START,
    });
    expect(reopened.current.source.cams.status).toBe("available");
    expect(reopened.current.data_quality.cams_run_utc).toBe(RUN_B);
    expectIconUnchanged(active, reopened);
    expect(JSON.parse(state.storage.getItem(bundleKey)).bundle.current.data_quality.cams_run_utc)
      .toBe(RUN_B);
    expect(state.storage.getItem(candidateKey)).toBeNull();
  });

  it("keeps the verified revocation when the replacement release download fails", async () => {
    const state = harness({ available: true });
    const active = await state.fetch();
    const failed = rawRevocationBundleFetcher(state, { releaseMode: "failure" });

    const result = await state.fetch({ bundleFetcher: failed.bundleFetcher, force: true });
    await failed.releaseStarted.promise;

    expectCamsRevoked(result, { stage: "latest", code: "TRANSPORT_FAILURE" });
    expectIconUnchanged(active, result);
    expectCamsRevoked(state.saved().bundle, { stage: "latest", code: "TRANSPORT_FAILURE" });
    expect(journalBytes(state).value).not.toBeNull();
  });

  it("keeps CAMS revoked when ICON fails after the family decision", async () => {
    const state = harness({ available: true });
    const active = await state.fetch();
    const iconGate = deferred();
    const pending = rawRevocationBundleFetcher(state, { iconGate });
    const request = state.fetch({ bundleFetcher: pending.bundleFetcher, force: true });
    await pending.releaseStarted.promise;
    iconGate.reject(new Error("controlled ICON failure"));

    const fallback = await request;
    expectCamsRevoked(fallback);
    expectIconUnchanged(active, fallback);
    expectCamsRevoked(state.saved().bundle);
    await settlePendingCams();
  });

  it("does not let an older family response overwrite a newer durable decision", async () => {
    const state = harness({ available: true });
    await state.fetch();
    const newer = familySnapshot({ revision: 3, publishedAt: "2026-09-10T03:00:00Z" });
    const newFailure = Object.assign(new Error("replacement not yet usable"), {
      code: "INTEGRITY_MISMATCH",
    });
    const decisionOnlyFetcher = snapshot => vi.fn(async (_location, options) => {
      expect(typeof options.onCamsFamilyLatest).toBe("function");
      options.onCamsFamilyLatest(snapshot);
      throw newFailure;
    });

    await expect(state.fetch({
      bundleFetcher: decisionOnlyFetcher(newer),
      force: true,
    })).rejects.toBe(newFailure);
    const durableNewer = journalBytes(state).value;
    expect(durableNewer).not.toBeNull();

    const cold = await coldRuntime();
    const older = familySnapshot({
      disabledRuns: [],
      publishedAt: "2026-09-10T02:00:00Z",
      revision: 2,
    });
    await expect(cold.fetchLocalWeatherV1RuntimeBundle(LOCATION, {
      ...state.options,
      storage: { ...state.storage },
      bundleFetcher: decisionOnlyFetcher(older),
      force: true,
    })).rejects.toMatchObject({ code: "CAMS_FAMILY_REGRESSION" });
    expect(journalBytes(state).value).toBe(durableNewer);
    expectCamsRevoked(cold.readLocalWeatherV1PersistedBundle(LOCATION, {
      baseUrl: state.options.baseUrl,
      storage: { ...state.storage },
      now: () => START,
    }));
  });

  it("does not journal or apply a revocation from an invalid family pointer", async () => {
    const state = harness({ available: true });
    const active = await state.fetch();
    const before = journalBytes(state).value;
    const invalid = JSON.parse(familyPointer());
    invalid.disabled_run_ids = [runId(RUN_A), runId(RUN_A)];
    const attempt = rawRevocationBundleFetcher(state, {
      pointerBody: canonicalJsonStringify(invalid),
      releaseMode: "failure",
    });

    const retained = await state.fetch({ bundleFetcher: attempt.bundleFetcher, force: true });

    expect(retained.current.data_quality.cams_run_utc).toBe(RUN_A);
    expect(retained.current.source.cams.status).toBe("available");
    expectIconUnchanged(active, retained);
    expect(journalBytes(state).value).toBe(before);
    expect(attempt.rawFetch).toHaveBeenCalledTimes(1);
  });

  it("quarantines only CAMS when the journal is corrupt without mutating stored candidates", async () => {
    const state = harness({ available: true });
    const active = await state.fetch();
    const bundleKey = getLocalWeatherV1BundleCacheKey(LOCATION, {
      baseUrl: state.options.baseUrl,
    });
    const activeBytes = state.storage.getItem(bundleKey);
    const candidateKey = `${bundleKey}:candidate`;
    const candidateBytes = activeBytes;
    const journal = journalBytes(state);
    const corruptJournal = '{"invalid":"journal"}';
    const uvActive = '{"marker":"uv-active-corrupt-journal"}';
    const uvCandidate = '{"marker":"uv-candidate-corrupt-journal"}';
    state.storage.setItem(candidateKey, candidateBytes);
    state.storage.setItem(journal.key, corruptJournal);
    state.storage.setItem(UV_CACHE_KEY, uvActive);
    state.storage.setItem(UV_CANDIDATE_CACHE_KEY, uvCandidate);

    const warm = readLocalWeatherV1PersistedBundle(LOCATION, {
      baseUrl: state.options.baseUrl,
      storage: state.storage,
      now: () => START,
    });
    expectCamsRevoked(warm, {
      stage: "family",
      code: "CAMS_REVOCATION_JOURNAL_INVALID",
    });
    expectIconUnchanged(active, warm);

    const cold = await coldRuntime();
    const reopened = cold.readLocalWeatherV1PersistedBundle(LOCATION, {
      baseUrl: state.options.baseUrl,
      storage: state.storage,
      now: () => START,
    });
    expectCamsRevoked(reopened, {
      stage: "family",
      code: "CAMS_REVOCATION_JOURNAL_INVALID",
    });
    expectIconUnchanged(active, reopened);
    const offline = await cold.fetchLocalWeatherV1RuntimeBundle(LOCATION, {
      ...state.options,
      storage: state.storage,
      bundleFetcher: vi.fn().mockRejectedValue(new Error("offline with corrupt journal")),
      force: true,
    });
    expectCamsRevoked(offline, {
      stage: "family",
      code: "CAMS_REVOCATION_JOURNAL_INVALID",
    });
    expectIconUnchanged(active, offline);
    expect(state.storage.getItem(journal.key)).toBe(corruptJournal);
    expect(state.storage.getItem(bundleKey)).toBe(activeBytes);
    expect(state.storage.getItem(candidateKey)).toBe(candidateBytes);
    expect(state.storage.getItem(UV_CACHE_KEY)).toBe(uvActive);
    expect(state.storage.getItem(UV_CANDIDATE_CACHE_KEY)).toBe(uvCandidate);
  });

  it("keeps ICON readable when only the revocation journal read fails", async () => {
    const state = harness({ available: true });
    const active = await state.fetch();
    const journal = journalBytes(state);
    const storageWithJournalReadFailure = {
      getItem(key) {
        if (key === journal.key) throw new Error("controlled journal read failure");
        return state.storage.getItem(key);
      },
      setItem: (key, value) => state.storage.setItem(key, value),
      removeItem: key => state.storage.removeItem(key),
    };
    const cold = await coldRuntime();

    const reopened = cold.readLocalWeatherV1PersistedBundle(LOCATION, {
      baseUrl: state.options.baseUrl,
      storage: storageWithJournalReadFailure,
      now: () => START,
    });
    expectCamsRevoked(reopened, {
      stage: "family",
      code: "CAMS_REVOCATION_RESTORE_FAILED",
    });
    expectIconUnchanged(active, reopened);
  });

  it("repairs a corrupt journal only after a new verified family decision", async () => {
    const state = harness({ available: true });
    const active = await state.fetch();
    const journal = journalBytes(state);
    const corruptJournal = "not-json";
    state.storage.setItem(journal.key, corruptJournal);
    const cold = await coldRuntime();
    expectCamsRevoked(cold.readLocalWeatherV1PersistedBundle(LOCATION, {
      baseUrl: state.options.baseUrl,
      storage: state.storage,
      now: () => START,
    }), { stage: "family", code: "CAMS_REVOCATION_JOURNAL_INVALID" });
    const replacementFailure = Object.assign(new Error("replacement still unavailable"), {
      code: "INTEGRITY_MISMATCH",
    });
    const verifiedDecisionOnly = vi.fn(async (_location, options) => {
      options.onCamsFamilyLatest(familySnapshot());
      throw replacementFailure;
    });

    await expect(cold.fetchLocalWeatherV1RuntimeBundle(LOCATION, {
      ...state.options,
      storage: state.storage,
      bundleFetcher: verifiedDecisionOnly,
      force: true,
    })).rejects.toBe(replacementFailure);
    expect(state.storage.getItem(journal.key)).not.toBe(corruptJournal);
    expect(cold.readLocalWeatherV1PersistedCamsFamilyDecision({
      baseUrl: state.options.baseUrl,
      storage: state.storage,
    })).toMatchObject({
      revision: 2,
      active_run_id: runId(RUN_B),
      disabled_run_ids: [runId(RUN_A)],
    });

    const restarted = await coldRuntime();
    const reopened = restarted.readLocalWeatherV1PersistedBundle(LOCATION, {
      baseUrl: state.options.baseUrl,
      storage: state.storage,
      now: () => START,
    });
    expectCamsRevoked(reopened);
    expectIconUnchanged(active, reopened);
  });

  it("rejects a verified revocation when durable storage is unavailable", async () => {
    const state = harness({ available: true });
    await state.fetch();
    const decisionOnly = vi.fn(async (_location, options) => {
      options.onCamsFamilyLatest(familySnapshot());
    });

    await expect(state.fetch({
      bundleFetcher: decisionOnly,
      force: true,
      storage: null,
    })).rejects.toMatchObject({ code: "CAMS_REVOCATION_PERSIST_FAILED" });
  });

  it("surfaces deferred journal persistence failure through the runtime channel", async () => {
    const state = harness({ available: true });
    const active = await state.fetch();
    const journal = journalBytes(state);
    const bundleKey = getLocalWeatherV1BundleCacheKey(LOCATION, {
      baseUrl: state.options.baseUrl,
    });
    const originalSetItem = state.storage.setItem;
    state.storage.setItem = (key, value) => {
      if (key === journal.key || key === bundleKey || key === `${bundleKey}:candidate`) {
        throw new Error("controlled deferred persistence failure");
      }
      return originalSetItem(key, value);
    };
    const attempt = rawRevocationBundleFetcher(state);
    const failure = vi.fn();
    const update = vi.fn();

    await state.fetch({
      bundleFetcher: attempt.bundleFetcher,
      deferCams: true,
      force: true,
      onCamsFailure: failure,
      onCamsUpdate: update,
    });
    await vi.waitFor(() => expect(failure).toHaveBeenCalledOnce());
    expect(failure.mock.calls[0][0]).toMatchObject({
      code: "CAMS_REVOCATION_PERSIST_FAILED",
    });
    const quarantined = update.mock.calls.find(([bundle]) => (
      bundle?.current?.data_quality?.cams_diagnostic?.code === "RUN_DISABLED"
    ))?.[0];
    expectCamsRevoked(quarantined);
    expectIconUnchanged(active, quarantined);
    const sessionRead = readLocalWeatherV1PersistedBundle(LOCATION, {
      baseUrl: state.options.baseUrl,
      storage: state.storage,
      now: () => START,
    });
    expectCamsRevoked(sessionRead);
    expectIconUnchanged(active, sessionRead);
    expect(state.storage.getItem(journal.key)).toBeNull();
  });

  it("surfaces journal persistence failure and remains fail-closed for the session", async () => {
    const state = harness({ available: true });
    const active = await state.fetch();
    const before = journalBytes(state);
    const bundleKey = getLocalWeatherV1BundleCacheKey(LOCATION, {
      baseUrl: state.options.baseUrl,
    });
    expect(before.value).toBeNull();
    const originalSetItem = state.storage.setItem;
    state.storage.setItem = (key, value) => {
      if (key === before.key || key === bundleKey || key === `${bundleKey}:candidate`) {
        throw new Error("controlled revocation persistence failure");
      }
      return originalSetItem(key, value);
    };
    const replacementFailure = Object.assign(new Error("replacement not usable"), {
      code: "INTEGRITY_MISMATCH",
    });
    const bundleFetcher = vi.fn(async (_location, options) => {
      expect(typeof options.onCamsFamilyLatest).toBe("function");
      options.onCamsFamilyLatest(familySnapshot());
      throw replacementFailure;
    });

    await expect(state.fetch({ bundleFetcher, force: true })).rejects.toMatchObject({
      code: "CAMS_REVOCATION_PERSIST_FAILED",
    });
    expect(state.storage.getItem(before.key)).toBe(before.value);
    const sessionRead = readLocalWeatherV1PersistedBundle(LOCATION, {
      baseUrl: state.options.baseUrl,
      storage: state.storage,
      now: () => START,
    });
    expectCamsRevoked(sessionRead);
    expectIconUnchanged(active, sessionRead);

    // Without a byte-verified journal (and with the bundle rewrite blocked), a
    // new process cannot truthfully claim that the decision survived. The
    // surfaced error is therefore part of the safety contract, not a success.
    const cold = await coldRuntime();
    const reopenedWithoutDurability = cold.readLocalWeatherV1PersistedBundle(LOCATION, {
      baseUrl: state.options.baseUrl,
      storage: { ...state.storage },
      now: () => START,
    });
    expect(reopenedWithoutDurability.current.source.cams.status).toBe("available");
    expect(reopenedWithoutDurability.current.data_quality.cams_run_utc).toBe(RUN_A);
  });

  it("does not claim durability when exact journal readback fails", async () => {
    const state = harness({ available: true });
    const active = await state.fetch();
    const journal = journalBytes(state);
    const originalGetItem = state.storage.getItem;
    const originalSetItem = state.storage.setItem;
    let journalWasWritten = false;
    state.storage.getItem = (key) => {
      if (key === journal.key && journalWasWritten) {
        throw new Error("controlled journal readback failure");
      }
      return originalGetItem(key);
    };
    state.storage.setItem = (key, value) => {
      const result = originalSetItem(key, value);
      if (key === journal.key) journalWasWritten = true;
      return result;
    };
    const decisionOnly = vi.fn(async (_location, options) => {
      options.onCamsFamilyLatest(familySnapshot());
    });

    await expect(state.fetch({ bundleFetcher: decisionOnly, force: true })).rejects.toMatchObject({
      code: "CAMS_REVOCATION_PERSIST_FAILED",
    });
    const sessionRead = readLocalWeatherV1PersistedBundle(LOCATION, {
      baseUrl: state.options.baseUrl,
      storage: state.storage,
      now: () => START,
    });
    expectCamsRevoked(sessionRead, {
      stage: "family",
      code: "CAMS_REVOCATION_RESTORE_FAILED",
    });
    expectIconUnchanged(active, sessionRead);

    state.storage.getItem = originalGetItem;
    state.storage.setItem = originalSetItem;
    expect(state.storage.getItem(journal.key)).not.toBeNull();
    const cold = await coldRuntime();
    const reopened = cold.readLocalWeatherV1PersistedBundle(LOCATION, {
      baseUrl: state.options.baseUrl,
      storage: state.storage,
      now: () => START,
    });
    expectCamsRevoked(reopened);
    expectIconUnchanged(active, reopened);
  });
});
