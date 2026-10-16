import { vi } from "vitest";
import { fetchLocalWeatherV1Bootstrap, LOCAL_WEATHER_V1_CATALOG } from "./localWeatherV1Adapter";
import { fetchLocalWeatherV1RuntimeBundle, getLocalWeatherV1BundleCacheKey } from "./localWeatherV1Runtime";

// Shared synthetic provider fixtures; no network or phone access.
const HOUR = 3_600_000;
const MINUTE = 60_000;
const START = Date.parse("2026-09-10T01:15:00Z");
const RUN_A = "2026-09-09T00:00:00Z";
const RUN_B = "2026-09-10T00:00:00Z";
const ICON_RUN = "2026-09-10T00:00:00Z";
const ISTAT = "093033";
const SPECIES = [
  ["alder_pollen", "ontano"], ["birch_pollen", "betulla"],
  ["grass_pollen", "graminacee"], ["mugwort_pollen", "artemisia"],
  ["olive_pollen", "olivo"], ["ragweed_pollen", "ambrosia"],
];
let sequence = 0;
const iso = time => new Date(time).toISOString().replace(".000Z", "Z");
const runId = time => time.replaceAll("-", "").replaceAll(":", "");
const at = hour => iso(Date.parse(ICON_RUN) + hour * HOUR);

function municipality() {
  return {
    istat_code: ISTAT, name: "Pordenone", slug: "pordenone", province: "PN",
    representative_point: { lat: 45.9567, lon: 12.6605 },
    model_point: { lat: 45.95, lon: 12.65, distance_km: 1.1, grid_index: 4 },
  };
}

function document(provider, { run = RUN_A, pollenValue = 0 } = {}) {
  const common = {
    provider, run_at: run, generated_at: iso(Date.parse(run) + HOUR),
    catalog: LOCAL_WEATHER_V1_CATALOG, municipality: municipality(),
    source: { attribution: provider === "icon2i" ? "ItaliaMeteo" : "CAMS", license: "CC BY 4.0" },
  };
  if (provider === "icon2i") return {
    ...common,
    model: { id: "icon-2i", product: "surface_pressure_levels" },
    hourly: Array.from({ length: 73 }, (_, hour) => ({
      valid_at: at(hour), interval_start: hour ? at(hour - 1) : null,
      interval_end: hour ? at(hour) : null, temperature_c: 12 + hour / 10,
      apparent_temperature_c: 11 + hour / 10, relative_humidity_pct: 70,
      pressure_msl_hpa: 1013, wind_speed_m_s: 2, wind_from_degrees: 180,
      wind_gust_max_m_s: hour ? 3 : null, cloud_cover_pct: 10,
      precipitation_mm: hour ? 0.2 : null, liquid_rain_mm: hour ? 0.2 : null,
      snow_water_equivalent_mm: hour ? 0 : null,
      condition: {
        native_code: 0, native_status: "valid", native_label_it: "Sereno",
        semantic_key: "clear", text_key: "conditionSun", icon_key: "Sun", scene_key: "clear",
      },
      quality_flags: [],
    })),
  };
  return {
    ...common,
    model: { id: "cams-european-regional-ensemble" },
    freshness: {
      fresh_until: iso(Date.parse(run) + 24 * HOUR),
      usable_until: iso(Date.parse(run) + 30 * HOUR),
    },
    variables: SPECIES.map(([id, ui_key]) => ({
      id, ui_key, category: "pollen", unit: "grains/m3",
      validation_status: "experimental_unvalidated_by_provider",
    })),
    health_classification: null,
    projection: {
      id: "cams_pollen_hourly_v1", source_provider: "cams_europe",
      source_kind: "meteofriul.weather.cams.municipality",
      retained_variable_ids: SPECIES.map(([id]) => id),
    },
    hourly: Array.from({ length: 97 }, (_, hour) => ({
      valid_at: iso(Date.parse(run) + hour * HOUR),
      values: Object.fromEntries(SPECIES.map(([id]) => [id, pollenValue])),
      quality_flags: Object.fromEntries(SPECIES.map(([id]) => [id, []])),
    })),
  };
}

function provider(document, revision = 1) {
  const name = document.provider;
  const id = runId(document.run_at);
  const pollen = name === "cams_europe_pollen";
  const latest = {
    document: pollen ? {
      provider: name, revision, published_at: iso(Date.parse(document.run_at) + HOUR),
      latest: { source_run_id: id }, disabled_run_ids: [],
    } : { provider: name },
    path: pollen ? `families/cams/runs/${id}/release.json#pollen` : "latest.json",
    etag: `"${name}-${id}-latest"`, fromCache: false, networkFallback: false,
  };
  const manifest = {
    document: { provider: name }, path: `runs/${id}/manifest.json`, etag: `"${id}-manifest"`,
  };
  const payload = {
    document, path: `runs/${id}/municipalities/${ISTAT}.json`, etag: `"${name}-${id}-payload"`,
    freshness: { status: "fresh", remainingCoverageHours: 60, requiredFutureHours: pollen ? 0 : 48 },
    cachePersisted: true,
  };
  return {
    fetchLatest: vi.fn(async () => latest),
    fetchManifest: vi.fn(async () => manifest),
    fetchMunicipality: vi.fn(async () => payload),
  };
}

function harness({ available = false, location = "Pordenone" } = {}) {
  const values = new Map();
  const storage = {
    getItem: key => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: key => values.delete(key),
  };
  const state = { available, run: RUN_A, revision: 1, offline: false };
  const observed = [];
  const clientFactory = vi.fn(() => {
    const icon2i = provider(document("icon2i", { run: ICON_RUN }));
    const camsPollen = provider(document("cams_europe_pollen", { run: state.run }), state.revision);
    const failure = Object.assign(new Error("controlled provider network failure"), { code: "TRANSPORT_FAILURE" });
    if (state.offline) icon2i.fetchLatest.mockRejectedValue(failure);
    if (!state.available || state.offline) camsPollen.fetchLatest.mockRejectedValue(failure);
    observed.push({ icon2i, camsPollen });
    return { icon2i, camsPollen };
  });
  const bundleFetcher = vi.fn((location, options) => fetchLocalWeatherV1Bootstrap(location, {
    ...options, clientFactory,
  }));
  const options = {
    baseUrl: `/diagnostic-cams-${++sequence}`, storage, now: () => Date.now(),
    verificationNow: () => Date.now(), fetchImpl: vi.fn(), bundleFetcher,
  };
  return {
    state, options, storage, clientFactory, bundleFetcher, observed,
    fetch: extra => fetchLocalWeatherV1RuntimeBundle(location, { ...options, ...extra }),
    saved: () => JSON.parse(storage.getItem(getLocalWeatherV1BundleCacheKey(location, options))),
    publish() { Object.assign(state, { available: true, run: RUN_B, revision: 2 }); },
  };
}

export { harness, MINUTE, START, RUN_A, RUN_B };
