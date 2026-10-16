import { afterEach, describe, expect, it, vi } from "vitest";

import { harness, RUN_A, RUN_B, START } from "../services/camsRecoveryTestFixtures";
import {
  fetchLocalWeatherV1Bootstrap,
  LOCAL_WEATHER_V1_CATALOG,
} from "../services/localWeatherV1Adapter";
import {
  canonicalJsonStringify,
  createWeatherV1Client,
  sha256Hex,
} from "../services/weatherV1Client";

const LOCATION = "Pordenone";
const CAMS_TIMEOUT_MS = 25;

function runId(runAt) {
  return runAt.replaceAll("-", "").replaceAll(":", "");
}

function deferred() {
  let resolve;
  const promise = new Promise((settle) => {
    resolve = settle;
  });
  return { promise, resolve };
}

function jsonResponse(body, etag = '"diagnostic-family"') {
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

function revokedFamilyPointer() {
  // Only the pointer is expected to validate in these diagnostics. The release
  // body is deliberately never delivered, but its descriptor must still be a
  // canonical, integrity-bound family descriptor.
  const releaseBody = canonicalJsonStringify({ deliberately: "unavailable" });
  const activeRunId = runId(RUN_B);
  return canonicalJsonStringify({
    schema_version: 1,
    kind: "meteofriul.weather.cams_family_latest",
    family: "cams",
    revision: 2,
    published_at: "2026-09-10T02:00:00Z",
    catalog: LOCAL_WEATHER_V1_CATALOG,
    latest: {
      source_run_id: activeRunId,
      release_path: `runs/${activeRunId}/release.json`,
      release_json_bytes: new TextEncoder().encode(releaseBody).length,
      release_sha256: sha256Hex(releaseBody),
    },
    previous: null,
    disabled_run_ids: [runId(RUN_A)],
  });
}

function observeRawFamily(client, onObserved) {
  return {
    ...client,
    camsFamily: {
      ...client.camsFamily,
      fetchMembersLatest(signal, onFamilyLatest) {
        return client.camsFamily.fetchMembersLatest(signal, (latest) => {
          onObserved(latest);
          onFamilyLatest?.(latest);
        });
      },
    },
  };
}

function camsSnapshot(bundle) {
  return {
    run: bundle?.current?.data_quality?.cams_run_utc ?? null,
    status: bundle?.current?.source?.cams?.status ?? null,
    diagnostic: bundle?.current?.data_quality?.cams_diagnostic?.code ?? null,
  };
}

async function coldRead(storage, baseUrl) {
  // Resetting the module graph simulates a new WebView/runtime: the old
  // camsFamilyStates Map must not be the only place where a revocation lives.
  vi.resetModules();
  const { readLocalWeatherV1PersistedBundle } = await import(
    "../services/localWeatherV1Runtime.js"
  );
  return readLocalWeatherV1PersistedBundle(LOCATION, {
    baseUrl,
    storage,
    now: () => START,
  });
}

afterEach(() => {
  vi.clearAllTimers();
  vi.useRealTimers();
});

describe("open CAMS raw family-revocation contract", () => {
  it("quarantines A immediately while the replacement release is still pending, including a cold read", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(START);
    const state = harness({ available: true });
    const active = await state.fetch();
    expect(camsSnapshot(active).run).toBe(RUN_A);

    const releaseStarted = deferred();
    const observed = vi.fn();
    const familyBody = revokedFamilyPointer();
    const rawFetch = vi.fn((url, options = {}) => {
      if (url.endsWith("/weather/v1/families/cams/latest.json")) {
        return Promise.resolve(jsonResponse(familyBody));
      }
      if (url.includes(`/weather/v1/families/cams/runs/${runId(RUN_B)}/release.json`)) {
        releaseStarted.resolve();
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
        const raw = observeRawFamily(createWeatherV1Client({
          ...clientOptions,
          fetchImpl: rawFetch,
        }), observed);
        const fixtureIcon = state.clientFactory(clientOptions).icon2i;
        return { ...raw, icon2i: fixtureIcon };
      },
    });

    const returned = await state.fetch({
      bundleFetcher,
      deferCams: true,
      force: true,
    });
    await releaseStarted.promise;
    const persistedBeforeTimeout = JSON.parse(JSON.stringify(state.saved().bundle));
    const restartedBeforeTimeout = await coldRead(state.storage, state.options.baseUrl);

    // Let the deliberately pending request terminate so the diagnostic leaves
    // no asynchronous work behind. Assertions use the snapshots taken while
    // the authoritative replacement was still pending.
    await vi.advanceTimersByTimeAsync(CAMS_TIMEOUT_MS + 1);
    await vi.runOnlyPendingTimersAsync();

    expect(observed).toHaveBeenCalledWith(expect.objectContaining({
      revision: 2,
      disabled_run_ids: [runId(RUN_A)],
    }));
    expect.soft(camsSnapshot(returned)).toMatchObject({
      run: null,
      status: "unavailable",
      diagnostic: "RUN_DISABLED",
    });
    expect.soft(camsSnapshot(persistedBeforeTimeout)).toMatchObject({
      run: null,
      status: "unavailable",
      diagnostic: "RUN_DISABLED",
    });
    expect.soft(camsSnapshot(restartedBeforeTimeout)).toMatchObject({
      run: null,
      status: "unavailable",
      diagnostic: "RUN_DISABLED",
    });
  });

  it("keeps A revoked after release and ICON failures and a runtime restart", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(START);
    const state = harness({ available: true });
    const active = await state.fetch();
    expect(camsSnapshot(active).run).toBe(RUN_A);

    const releaseStarted = deferred();
    const observed = vi.fn();
    const familyBody = revokedFamilyPointer();
    const rawFetch = vi.fn((url) => {
      if (url.endsWith("/weather/v1/families/cams/latest.json")) {
        return Promise.resolve(jsonResponse(familyBody));
      }
      if (url.includes(`/weather/v1/families/cams/runs/${runId(RUN_B)}/release.json`)) {
        releaseStarted.resolve();
        return Promise.reject(new Error("controlled replacement release failure"));
      }
      if (url.endsWith("/weather/v1/icon2i/latest.json")) {
        return Promise.reject(new Error("controlled ICON failure"));
      }
      throw new Error(`unexpected raw request ${url}`);
    });
    const bundleFetcher = (location, options) => fetchLocalWeatherV1Bootstrap(location, {
      ...options,
      camsTimeoutMs: CAMS_TIMEOUT_MS,
      clientFactory: (clientOptions) => observeRawFamily(createWeatherV1Client({
        ...clientOptions,
        fetchImpl: rawFetch,
      }), observed),
    });

    const returned = await state.fetch({ bundleFetcher, force: true });
    await releaseStarted.promise;
    await vi.advanceTimersByTimeAsync(0);
    const persistedAfterFailures = JSON.parse(JSON.stringify(state.saved().bundle));
    const restartedAfterFailures = await coldRead(state.storage, state.options.baseUrl);

    expect(observed).toHaveBeenCalledWith(expect.objectContaining({
      revision: 2,
      disabled_run_ids: [runId(RUN_A)],
    }));
    expect.soft(camsSnapshot(returned)).toMatchObject({
      run: null,
      status: "unavailable",
      diagnostic: "RUN_DISABLED",
    });
    expect.soft(camsSnapshot(persistedAfterFailures)).toMatchObject({
      run: null,
      status: "unavailable",
      diagnostic: "RUN_DISABLED",
    });
    expect.soft(camsSnapshot(restartedAfterFailures)).toMatchObject({
      run: null,
      status: "unavailable",
      diagnostic: "RUN_DISABLED",
    });
  });
});
