import { describe, expect, it, vi } from "vitest";
import {
  WeatherV1ClientError,
  writeWeatherV1CacheValue,
  canonicalJsonStringify,
  createWeatherV1Client,
  readCachedIconLatest,
  sha256Hex,
} from "./weatherV1Client";
import { ICON_FORECAST_WINDOW_POLICY } from "./iconForecastWindow";

const HOUR_MS = 60 * 60 * 1000;
const RUN_AT = "2026-09-03T00:00:00Z";
const RUN_ID = "20260903T000000Z";
const CODES = Object.freeze(
  Array.from({ length: 215 }, (_, index) => String(index + 1).padStart(6, "0")),
);
const TARGET = CODES[0];
const CATALOG = Object.freeze({
  version: "istat-2026-irdat-2006-representative-points-v1",
  sha256: "a".repeat(64),
  municipality_count: 215,
});

const CONTRACT = Object.freeze({
  icon2i: Object.freeze({
    horizon: 72,
    kind: "meteofriul.weather.icon.municipality",
    model: { id: "icon-2i", product: "surface_pressure_levels" },
    source: {
      attribution: "Agenzia ItaliaMeteo / Arpae Emilia-Romagna Idro-Meteo-Clima",
      license: "CC BY 4.0",
      license_url: "https://creativecommons.org/licenses/by/4.0/",
    },
    policyId: "icon2i_48h_v1",
    freshHours: 18,
    usableHours: 30,
    requiredHours: 48,
  }),
  cams_europe: Object.freeze({
    horizon: 96,
    kind: "meteofriul.weather.cams.municipality",
    model: {
      id: "cams-european-regional-ensemble",
      dataset: "cams-europe-air-quality-forecasts",
      forecast_type: "ensemble",
      statistic: "median",
      level: "surface",
    },
    source: {
      attribution:
        "Copernicus Atmosphere Monitoring Service (CAMS), European regional ensemble providers, Atmosphere Data Store (ADS)",
      license: "CC BY 4.0",
      license_url: "https://creativecommons.org/licenses/by/4.0/",
      doi: "10.24381/a4005cee",
    },
    policyId: "cams_current_v1",
    freshHours: 24,
    usableHours: 30,
    requiredHours: 0,
  }),
  cams_europe_pollen: Object.freeze({
    horizon: 96,
    kind: "meteofriul.weather.cams.pollen_municipality",
    model: {
      id: "cams-european-regional-ensemble",
      dataset: "cams-europe-air-quality-forecasts",
      forecast_type: "ensemble",
      statistic: "median",
      level: "surface",
    },
    source: {
      attribution:
        "Copernicus Atmosphere Monitoring Service (CAMS), European regional ensemble providers, Atmosphere Data Store (ADS)",
      license: "CC BY 4.0",
      license_url: "https://creativecommons.org/licenses/by/4.0/",
      doi: "10.24381/a4005cee",
    },
    policyId: "cams_pollen_current_v1",
    freshHours: 24,
    usableHours: 30,
    requiredHours: 0,
  }),
});

const ICON_UNITS = {
  temperature_c: "degC",
  apparent_temperature_c: "degC",
  relative_humidity_pct: "percent",
  pressure_msl_hpa: "hPa",
  wind_speed_m_s: "m/s",
  wind_from_degrees: "degree",
  wind_gust_max_m_s: "m/s",
  cloud_cover_pct: "percent",
  precipitation_mm: "mm",
  liquid_rain_mm: "mm",
  snow_water_equivalent_mm: "mm",
};

const CAMS_VARIABLE_SPECS = [
  ["alder_pollen", "ontano", "pollen", "grains/m3", "experimental_unvalidated_by_provider"],
  ["ammonia", "ammoniaca", "air_quality", "ug/m3", "experimental_unvalidated_by_provider"],
  ["birch_pollen", "betulla", "pollen", "grains/m3", "experimental_unvalidated_by_provider"],
  ["carbon_monoxide", "monossido_carbonio", "air_quality", "ug/m3", "experimental_unvalidated_by_provider"],
  ["formaldehyde", "formaldeide", "air_quality", "ug/m3", "experimental_unvalidated_by_provider"],
  ["glyoxal", "gliossale", "air_quality", "ug/m3", "experimental_unvalidated_by_provider"],
  ["grass_pollen", "graminacee", "pollen", "grains/m3", "experimental_unvalidated_by_provider"],
  ["mugwort_pollen", "artemisia", "pollen", "grains/m3", "experimental_unvalidated_by_provider"],
  ["nitrogen_dioxide", "biossido_azoto", "air_quality", "ug/m3", "regularly_validated_in_situ_by_provider"],
  ["nitrogen_monoxide", "monossido_azoto", "air_quality", "ug/m3", "regularly_validated_in_situ_by_provider"],
  ["non_methane_vocs", "cov_non_metanici", "air_quality", "ug/m3", "experimental_unvalidated_by_provider"],
  ["olive_pollen", "olivo", "pollen", "grains/m3", "experimental_unvalidated_by_provider"],
  ["ozone", "ozono", "air_quality", "ug/m3", "regularly_validated_in_situ_by_provider"],
  ["particulate_matter_2.5um", "pm2_5", "air_quality", "ug/m3", "regularly_validated_in_situ_by_provider"],
  ["pm2.5_ammonium", "pm2_5_ammonio", "air_quality", "ug/m3", "experimental_unvalidated_by_provider"],
  ["pm2.5_nitrate", "pm2_5_nitrato", "air_quality", "ug/m3", "experimental_unvalidated_by_provider"],
  ["residential_elementary_carbon", "carbonio_elementare_residenziale", "air_quality", "ug/m3", "experimental_unvalidated_by_provider"],
  ["secondary_inorganic_aerosol", "aerosol_inorganico_secondario", "air_quality", "ug/m3", "experimental_unvalidated_by_provider"],
  ["pm2.5_sulphate", "pm2_5_solfato", "air_quality", "ug/m3", "experimental_unvalidated_by_provider"],
  ["total_elementary_carbon", "carbonio_elementare_totale", "air_quality", "ug/m3", "experimental_unvalidated_by_provider"],
  ["pm2.5_total_organic_matter", "pm2_5_materia_organica", "air_quality", "ug/m3", "experimental_unvalidated_by_provider"],
  ["particulate_matter_10um", "pm10", "air_quality", "ug/m3", "regularly_validated_in_situ_by_provider"],
  ["dust", "polvere_minerale_pm10", "air_quality", "ug/m3", "regularly_validated_in_situ_by_provider"],
  ["pm10_sea_salt_dry", "pm10_sale_marino_secco", "air_quality", "ug/m3", "experimental_unvalidated_by_provider"],
  ["pm10_wildfires", "pm10_incendi", "air_quality", "ug/m3", "experimental_unvalidated_by_provider"],
  ["peroxyacyl_nitrates", "nitrati_perossiacile", "air_quality", "ug/m3", "experimental_unvalidated_by_provider"],
  ["ragweed_pollen", "ambrosia", "pollen", "grains/m3", "experimental_unvalidated_by_provider"],
  ["sulphur_dioxide", "biossido_zolfo", "air_quality", "ug/m3", "regularly_validated_in_situ_by_provider"],
];
const CAMS_VARIABLES = CAMS_VARIABLE_SPECS.map(
  ([id, ui_key, category, unit, validation_status]) => ({
    id,
    ui_key,
    category,
    unit,
    validation_status,
  }),
);
const CAMS_IDS = CAMS_VARIABLES.map(({ id }) => id);
const CAMS_POLLEN_VARIABLES = CAMS_VARIABLES.filter(({ category }) => category === "pollen");
const CAMS_POLLEN_IDS = CAMS_POLLEN_VARIABLES.map(({ id }) => id);
const CAMS_POLLEN_PROJECTION = {
  id: "cams_pollen_hourly_v1",
  source_provider: "cams_europe",
  source_kind: "meteofriul.weather.cams.municipality",
  retained_variable_ids: CAMS_POLLEN_IDS,
};

function isoAt(hours) {
  return new Date(Date.parse(RUN_AT) + hours * HOUR_MS).toISOString().replace(".000Z", "Z");
}

function freshness(provider) {
  const contract = CONTRACT[provider];
  const coverageLimit = contract.horizon - contract.requiredHours;
  return {
    policy_id: contract.policyId,
    fresh_until: isoAt(Math.min(contract.freshHours, coverageLimit)),
    usable_until: isoAt(Math.min(contract.usableHours, coverageLimit)),
    required_future_hours: contract.requiredHours,
    current_sample_max_lag_minutes: 60,
  };
}

function commonPayload(provider, istatCode = TARGET) {
  const contract = CONTRACT[provider];
  return {
    schema_version: 1,
    kind: contract.kind,
    provider,
    model: contract.model,
    source: contract.source,
    source_run_id: RUN_ID,
    run_at: RUN_AT,
    generated_at: isoAt(1),
    valid_from: RUN_AT,
    valid_to: isoAt(contract.horizon),
    timezone: "Europe/Rome",
    freshness: freshness(provider),
    catalog: CATALOG,
    municipality: {
      istat_code: istatCode,
      name: "Comune test",
      slug: "comune-test",
      province: "UD",
      representative_point: { lat: 46, lon: 13 },
      model_point: { lat: 46, lon: 13, distance_km: 0, grid_index: 1 },
    },
  };
}

function iconPayload(istatCode = TARGET) {
  const hourly = Array.from({ length: 73 }, (_, lead) => ({
    valid_at: isoAt(lead),
    interval_start: lead === 0 ? null : isoAt(lead - 1),
    interval_end: lead === 0 ? null : isoAt(lead),
    temperature_c: 10,
    apparent_temperature_c: 9,
    relative_humidity_pct: 70,
    pressure_msl_hpa: 1013,
    wind_speed_m_s: 2,
    wind_from_degrees: 180,
    wind_gust_max_m_s: lead === 0 ? null : 3,
    cloud_cover_pct: 20,
    precipitation_mm: lead === 0 ? null : 0,
    liquid_rain_mm: lead === 0 ? null : 0,
    snow_water_equivalent_mm: lead === 0 ? null : 0,
    condition: {
      native_code: 0,
      native_status: "valid",
      native_label_it: "Sereno",
      semantic_key: "clear",
      text_key: "conditionSun",
      icon_key: "Sun",
      scene_key: "clear",
    },
    quality_flags: [],
  }));
  const twoHourly = Array.from({ length: 36 }, (_, index) => ({
    start_at: isoAt(index * 2),
    end_at: isoAt((index + 1) * 2),
    source_hours: 2,
    precipitation_mm: 0,
    wind_gust_max_m_s: 3,
    temperature_min_c: 10,
    temperature_max_c: 10,
    temperature_end_c: 10,
    status: "valid",
    quality_flags: [],
  }));
  return {
    ...commonPayload("icon2i", istatCode),
    units: ICON_UNITS,
    apparent_temperature_method: "steadman_bom_shade_t2m_rh_magnus_wind10m_v1",
    hourly,
    two_hourly: twoHourly,
  };
}

function camsPayload(istatCode = TARGET) {
  const values = Object.fromEntries(CAMS_IDS.map((id) => [id, 1]));
  const flags = Object.fromEntries(CAMS_IDS.map((id) => [id, []]));
  return {
    ...commonPayload("cams_europe", istatCode),
    variables: CAMS_VARIABLES,
    hourly: Array.from({ length: 97 }, (_, lead) => ({
      valid_at: isoAt(lead),
      values: { ...values },
      quality_flags: Object.fromEntries(CAMS_IDS.map((id) => [id, [...flags[id]]])),
    })),
    health_classification: null,
  };
}

function camsPollenPayload(istatCode = TARGET) {
  const values = Object.fromEntries(CAMS_POLLEN_IDS.map((id) => [id, 1]));
  const flags = Object.fromEntries(CAMS_POLLEN_IDS.map((id) => [id, []]));
  return {
    ...commonPayload("cams_europe_pollen", istatCode),
    variables: CAMS_POLLEN_VARIABLES,
    hourly: Array.from({ length: 97 }, (_, lead) => ({
      valid_at: isoAt(lead),
      values: { ...values },
      quality_flags: Object.fromEntries(
        CAMS_POLLEN_IDS.map((id) => [id, [...flags[id]]]),
      ),
    })),
    health_classification: null,
    projection: CAMS_POLLEN_PROJECTION,
  };
}

function buildArtifacts(
  provider,
  {
    payloadIstat = TARGET,
    descriptorIstat = TARGET,
    mutatePayload,
    mutateManifest,
    mutateLatest,
  } = {},
) {
  const payload = provider === "icon2i"
    ? iconPayload(payloadIstat)
    : provider === "cams_europe_pollen"
      ? camsPollenPayload(payloadIstat)
      : camsPayload(payloadIstat);
  mutatePayload?.(payload);
  const payloadBody = canonicalJsonStringify(payload);
  const objects = Object.fromEntries(
    CODES.map((code) => [
      code,
      {
        path: `runs/${RUN_ID}/municipalities/${code}.json`,
        json_bytes: code === descriptorIstat ? new TextEncoder().encode(payloadBody).length : 1,
        sha256: code === descriptorIstat ? sha256Hex(payloadBody) : "0".repeat(64),
      },
    ]),
  );
  const contract = CONTRACT[provider];
  const manifest = {
    schema_version: 1,
    kind: "meteofriul.weather.run_manifest",
    provider,
    model: contract.model,
    source: contract.source,
    source_run_id: RUN_ID,
    run_at: RUN_AT,
    generated_at: isoAt(1),
    valid_from: RUN_AT,
    valid_to: isoAt(contract.horizon),
    freshness: freshness(provider),
    catalog: CATALOG,
    objects,
  };
  mutateManifest?.(manifest);
  const manifestBody = canonicalJsonStringify(manifest);
  const latest = {
    schema_version: 1,
    kind: "meteofriul.weather.latest",
    provider,
    revision: 1,
    published_at: isoAt(2),
    catalog: CATALOG,
    latest: {
      source_run_id: RUN_ID,
      run_at: RUN_AT,
      manifest_path: `runs/${RUN_ID}/manifest.json`,
      manifest_json_bytes: new TextEncoder().encode(manifestBody).length,
      manifest_sha256: sha256Hex(manifestBody),
    },
    previous: null,
    disabled_run_ids: [],
  };
  mutateLatest?.(latest);
  return {
    payload,
    payloadBody,
    manifest,
    manifestBody,
    latest,
    latestBody: canonicalJsonStringify(latest),
  };
}

function buildCamsFamilyArtifacts({
  core = buildArtifacts("cams_europe"),
  disabledRunIds = [],
  pollen = buildArtifacts("cams_europe_pollen"),
  pointerPublishedAt = isoAt(2),
  previous = null,
  releasePublishedAt = isoAt(2),
  revision = 1,
  sourceRunId = RUN_ID,
  mutateRelease,
  mutateFamilyLatest,
} = {}) {
  const descriptor = (provider, artifacts) => ({
    provider,
    source_run_id: sourceRunId,
    manifest_key: `weather/v1/${provider}/runs/${sourceRunId}/manifest.json`,
    manifest_json_bytes: new TextEncoder().encode(artifacts.manifestBody).length,
    manifest_sha256: sha256Hex(artifacts.manifestBody),
  });
  const release = {
    schema_version: 1,
    kind: "meteofriul.weather.cams_family_release",
    family: "cams",
    source_run_id: sourceRunId,
    published_at: releasePublishedAt,
    validation_sha256: "b".repeat(64),
    catalog: CATALOG,
    components: {
      core: descriptor("cams_europe", core),
      pollen: descriptor("cams_europe_pollen", pollen),
    },
  };
  mutateRelease?.(release);
  const releaseBody = canonicalJsonStringify(release);
  const latest = {
    schema_version: 1,
    kind: "meteofriul.weather.cams_family_latest",
    family: "cams",
    revision,
    published_at: pointerPublishedAt,
    catalog: CATALOG,
    latest: {
      source_run_id: sourceRunId,
      release_path: `runs/${sourceRunId}/release.json`,
      release_json_bytes: new TextEncoder().encode(releaseBody).length,
      release_sha256: sha256Hex(releaseBody),
    },
    previous,
    disabled_run_ids: [...disabledRunIds],
  };
  mutateFamilyLatest?.(latest);
  return {
    core,
    pollen,
    release,
    releaseBody,
    latest,
    latestBody: canonicalJsonStringify(latest),
  };
}

function memoryStorage(values = new Map()) {
  return {
    values,
    getItem: vi.fn((key) => values.get(key) ?? null),
    setItem: vi.fn((key, value) => values.set(key, value)),
    removeItem: vi.fn((key) => values.delete(key)),
  };
}

function enumerableMemoryStorage(values = new Map()) {
  const storage = memoryStorage(values);
  storage.key = vi.fn(index => [...storage.values.keys()][index] ?? null);
  Object.defineProperty(storage, "length", {
    configurable: true,
    get: () => storage.values.size,
  });
  return storage;
}

function jsonResponse(body, { status = 200, etag = '"etag"', contentType = "application/json" } = {}) {
  const bytes = new TextEncoder().encode(body || "");
  const headers = new Map([
    ["etag", etag],
    ["content-type", contentType],
  ]);
  return {
    status,
    headers: { get: (name) => headers.get(String(name).toLowerCase()) ?? null },
    arrayBuffer: async () => bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength),
  };
}

function abortErrorForTest() {
  const error = new Error("aborted");
  error.name = "AbortError";
  return error;
}

function harness({ nowHours = 10, storage = memoryStorage(), force = false, iconWindowPolicy = null, readPrefetchedObject = null } = {}) {
  const responses = [];
  const requests = [];
  const fetchImpl = vi.fn(async (url, options) => {
    requests.push({ url, options });
    if (!responses.length) throw new Error("missing mocked response");
    return responses.shift();
  });
  const client = createWeatherV1Client({
    baseUrl: "http://127.0.0.1:8787/",
    fetchImpl,
    storage,
    now: () => Date.parse(RUN_AT) + nowHours * HOUR_MS,
    catalog: CATALOG,
    istatCodes: CODES,
    force,
    iconWindowPolicy,
    readPrefetchedObject,
  });
  return { client, responses, requests, fetchImpl, storage };
}

async function fetchChain(provider, testHarness, artifacts, signal, istatCode = TARGET) {
  const providerClient = {
    icon2i: testHarness.client.icon2i,
    cams_europe: testHarness.client.camsEurope,
    cams_europe_pollen: testHarness.client.camsPollen,
  }[provider];
  if (provider === "icon2i") {
    testHarness.responses.push(
      jsonResponse(artifacts.latestBody, { etag: '"latest-1"' }),
      jsonResponse(artifacts.manifestBody, { etag: '"manifest-1"' }),
      jsonResponse(artifacts.payloadBody, { etag: '"payload-1"' }),
    );
  } else {
    const family = buildCamsFamilyArtifacts({
      ...(provider === "cams_europe" ? { core: artifacts } : { pollen: artifacts }),
    });
    testHarness.responses.push(
      jsonResponse(family.latestBody, { etag: '"family-latest-1"' }),
      jsonResponse(family.releaseBody, { etag: '"family-release-1"' }),
      jsonResponse(artifacts.manifestBody, { etag: '"manifest-1"' }),
      jsonResponse(artifacts.payloadBody, { etag: '"payload-1"' }),
    );
  }
  const latest = await providerClient.fetchLatest(signal);
  const manifest = await providerClient.fetchManifest(latest, signal);
  const payload = await providerClient.fetchMunicipality(manifest, istatCode, signal);
  return { providerClient, latest, manifest, payload };
}

function cachedBodyRecords(storage, provider, kind) {
  return [...storage.values.entries()]
    .filter(([key]) => key.includes(`:${provider}:${kind}:`) && !key.endsWith(":lru"))
    .map(([key, raw]) => ({ key, record: JSON.parse(raw) }));
}

describe("optional native weather-v1 staging read port", () => {
  function readerFor(artifacts, provider = "icon2i", family = null) {
    const objects = new Map([
      [`${provider}/${artifacts.latest.latest.manifest_path}`, artifacts.manifestBody],
      [`${provider}/${artifacts.manifest.objects[TARGET].path}`, artifacts.payloadBody],
      ...(family ? [[`families/cams/${family.latest.latest.release_path}`, family.releaseBody]] : []),
    ]);
    return vi.fn(({ provider: requestedProvider, path }) => {
      const body = objects.get(`${requestedProvider}/${path}`);
      return body ? { body, etag: '"native-staged"' } : null;
    });
  }

  async function iconChain(testHarness) {
    const latest = await testHarness.client.icon2i.fetchLatest();
    const manifest = await testHarness.client.icon2i.fetchManifest(latest);
    const payload = await testHarness.client.icon2i.fetchMunicipality(manifest, TARGET);
    return { latest, manifest, payload };
  }

  it("reads current metadata from network and validates staged immutable ICON bytes before committing", async () => {
    const artifacts = buildArtifacts("icon2i");
    const readPrefetchedObject = readerFor(artifacts);
    const testHarness = harness({ readPrefetchedObject });
    testHarness.responses.push(jsonResponse(artifacts.latestBody));
    const { latest, manifest, payload } = await iconChain(testHarness);
    expect(testHarness.requests).toHaveLength(1);
    expect(testHarness.requests[0].url).toMatch(/\/icon2i\/latest\.json$/);
    expect(readPrefetchedObject).toHaveBeenNthCalledWith(1, {
      provider: "icon2i", path: artifacts.latest.latest.manifest_path,
      sha256: artifacts.latest.latest.manifest_sha256, signal: undefined,
    });
    expect(readPrefetchedObject).toHaveBeenNthCalledWith(2, {
      provider: "icon2i", path: artifacts.manifest.objects[TARGET].path,
      sha256: artifacts.manifest.objects[TARGET].sha256, signal: undefined,
    });
    expect(payload.document).toEqual(artifacts.payload);
    expect(payload.cachePersisted).toBe(true);
    expect(manifest.cachePersisted).toBe(true);
    expect(payload).not.toHaveProperty("networkFallback");
    expect(payload).not.toHaveProperty("prefetched");
    expect(cachedBodyRecords(testHarness.storage, "icon2i", "municipality")).toHaveLength(1);
    await testHarness.client.icon2i.fetchManifest(latest);
    await testHarness.client.icon2i.fetchMunicipality(manifest, TARGET);
    expect(readPrefetchedObject).toHaveBeenCalledTimes(2);
    expect(testHarness.requests).toHaveLength(1);
  });

  it.each([
    ["missing", () => null],
    ["plugin failure", () => { throw new Error("native unavailable"); }],
    ["plugin timeout", () => Promise.reject(new Error("native timed out"))],
    ["plugin-internal abort without caller cancellation", () => Promise.reject(abortErrorForTest())],
    ["wrong hash", () => ({ body: "{}", etag: '"native"' })],
    ["non-string body", () => ({ body: {}, etag: '"native"' })],
    ["oversized body", () => ({ body: "x".repeat(2 * 1024 * 1024 + 1), etag: '"native"' })],
    ["oversized UTF-8", () => ({ body: "é".repeat(1024 * 1024 + 1), etag: '"native"' })],
    ["empty ETag", body => ({ body, etag: "" })],
    ["invalid ETag", body => ({ body, etag: "native\r\nheader" })],
  ])("treats %s staging as a miss and keeps normal network validation", async (_label, response) => {
    const artifacts = buildArtifacts("icon2i");
    const readPrefetchedObject = vi.fn(() => response(artifacts.manifestBody));
    const testHarness = harness({ readPrefetchedObject });
    const { payload } = await fetchChain("icon2i", testHarness, artifacts);
    expect(payload.document).toEqual(artifacts.payload);
    expect(testHarness.requests).toHaveLength(3);
    expect(readPrefetchedObject).toHaveBeenCalledTimes(2);
  });

  it.each([
    ["manifest", { mutateManifest: value => { value.catalog = { ...CATALOG, sha256: "b".repeat(64) }; } }],
    ["payload", { mutatePayload: value => { value.hourly.splice(15, 1); } }],
  ])("fails closed on staged %s with matching SHA but invalid full schema", async (kind, options) => {
    const artifacts = buildArtifacts("icon2i", options);
    const testHarness = harness({ readPrefetchedObject: readerFor(artifacts) });
    testHarness.responses.push(jsonResponse(artifacts.latestBody));
    await expect(iconChain(testHarness)).rejects.toBeInstanceOf(WeatherV1ClientError);
    expect(testHarness.requests).toHaveLength(1);
    expect(cachedBodyRecords(testHarness.storage, "icon2i", kind === "payload" ? "municipality" : "manifest"))
      .toHaveLength(0);
  });

  it("aborts a pending native read promptly without falling through to network or committing", async () => {
    const artifacts = buildArtifacts("icon2i");
    const readPrefetchedObject = vi.fn(() => new Promise(() => {}));
    const testHarness = harness({ readPrefetchedObject });
    testHarness.responses.push(jsonResponse(artifacts.latestBody));
    const latest = await testHarness.client.icon2i.fetchLatest();
    const controller = new AbortController();
    const pending = testHarness.client.icon2i.fetchManifest(latest, controller.signal);
    const rejection = expect(pending).rejects.toMatchObject({ code: "TRANSPORT_FAILURE", aborted: true });
    await vi.waitFor(() => expect(readPrefetchedObject).toHaveBeenCalledOnce());
    expect(readPrefetchedObject.mock.calls[0][0].signal).toBe(controller.signal);
    controller.abort();
    await rejection;
    expect(testHarness.requests).toHaveLength(1);
    expect(cachedBodyRecords(testHarness.storage, "icon2i", "manifest")).toHaveLength(0);
  });

  it("does not bypass an already aborted signal through a verified raw-cache hit", async () => {
    const artifacts = buildArtifacts("icon2i");
    const readPrefetchedObject = readerFor(artifacts);
    const testHarness = harness({ readPrefetchedObject });
    testHarness.responses.push(jsonResponse(artifacts.latestBody));
    const { latest } = await iconChain(testHarness);
    const controller = new AbortController();
    controller.abort();
    await expect(testHarness.client.icon2i.fetchManifest(latest, controller.signal))
      .rejects.toMatchObject({ code: "TRANSPORT_FAILURE", aborted: true });
    expect(readPrefetchedObject).toHaveBeenCalledTimes(2);
    expect(testHarness.requests).toHaveLength(1);
  });

  it("force bypasses native staging for the complete ICON chain", async () => {
    const artifacts = buildArtifacts("icon2i");
    const readPrefetchedObject = readerFor(artifacts);
    const testHarness = harness({ readPrefetchedObject, force: true });
    await fetchChain("icon2i", testHarness, artifacts);
    expect(readPrefetchedObject).not.toHaveBeenCalled();
    expect(testHarness.requests).toHaveLength(3);
    expect(testHarness.requests.every(({ options }) => options.cache === "no-store")).toBe(true);
  });

  it("keeps default municipality conditional network reads without the optional port", async () => {
    const artifacts = buildArtifacts("icon2i");
    const testHarness = harness();
    const { manifest } = await fetchChain("icon2i", testHarness, artifacts);
    testHarness.responses.push(jsonResponse("", { status: 304, etag: '"payload-1"' }));
    expect((await testHarness.client.icon2i.fetchMunicipality(manifest, TARGET)).notModified).toBe(true);
    expect(testHarness.requests).toHaveLength(4);
  });

  it("does not use staging below a pointer recovered offline, even if the manifest network read succeeds", async () => {
    const artifacts = buildArtifacts("icon2i");
    const storage = memoryStorage();
    await fetchChain("icon2i", harness({ storage }), artifacts);
    const readPrefetchedObject = readerFor(artifacts);
    const testHarness = harness({ storage, readPrefetchedObject });
    testHarness.responses.push(jsonResponse("", { status: 503 }),
      jsonResponse(artifacts.manifestBody), jsonResponse("", { status: 503 }));
    const { latest, manifest, payload } = await iconChain(testHarness);
    expect(latest.networkFallback).toBe(true);
    expect(manifest).not.toHaveProperty("networkFallback");
    expect(payload.networkFallback).toBe(true);
    expect(readPrefetchedObject).not.toHaveBeenCalled();
    expect(testHarness.requests).toHaveLength(3);
  });

  it("never uses staged bytes from an ICON run revoked by current metadata", async () => {
    const artifacts = buildArtifacts("icon2i");
    const readPrefetchedObject = readerFor(artifacts);
    const testHarness = harness({ readPrefetchedObject, iconWindowPolicy: ICON_FORECAST_WINDOW_POLICY });
    const replacement = "20260903T120000Z";
    testHarness.responses.push(jsonResponse(canonicalJsonStringify({ ...artifacts.latest,
      revision: 2, disabled_run_ids: [RUN_ID], latest: { ...artifacts.latest.latest,
        source_run_id: replacement, run_at: isoAt(12), manifest_path: `runs/${replacement}/manifest.json` },
    })));
    await testHarness.client.icon2i.fetchLatest();
    await expect(testHarness.client.icon2i.fetchManifest({ document: artifacts.latest }))
      .rejects.toMatchObject({ code: "RUN_DISABLED" });
    expect(readPrefetchedObject).not.toHaveBeenCalled();
  });

  it("does not substitute staged objects for a failed mutable metadata request", async () => {
    const artifacts = buildArtifacts("icon2i");
    const readPrefetchedObject = readerFor(artifacts);
    const testHarness = harness({ readPrefetchedObject });
    testHarness.responses.push(jsonResponse("", { status: 401 }));
    await expect(iconChain(testHarness)).rejects.toMatchObject({ code: "HTTP_ERROR", httpStatus: 401 });
    expect(readPrefetchedObject).not.toHaveBeenCalled();
    expect(testHarness.requests).toHaveLength(1);
  });

  it.each(["cams_europe", "cams_europe_pollen"])("uses staged %s only below verified family metadata and preserves CAMS freshness", async provider => {
    const artifacts = buildArtifacts(provider);
    const family = buildCamsFamilyArtifacts({ [provider === "cams_europe" ? "core" : "pollen"]: artifacts });
    const readPrefetchedObject = readerFor(artifacts, provider, family);
    const testHarness = harness({ readPrefetchedObject });
    testHarness.responses.push(jsonResponse(family.latestBody));
    const member = provider === "cams_europe" ? testHarness.client.camsEurope : testHarness.client.camsPollen;
    const latest = await member.fetchLatest();
    const manifest = await member.fetchManifest(latest);
    const payload = await member.fetchMunicipality(manifest, TARGET);
    expect(payload.document).toEqual(artifacts.payload);
    expect(payload.freshness.requiredFutureHours).toBe(0);
    expect(testHarness.requests).toHaveLength(1);
    expect(testHarness.requests[0].url).toMatch(/\/families\/cams\/latest\.json$/);
    expect(readPrefetchedObject).toHaveBeenCalledTimes(3);
    const expired = harness({ readPrefetchedObject, nowHours: 31, iconWindowPolicy: ICON_FORECAST_WINDOW_POLICY });
    expired.responses.push(jsonResponse(family.latestBody));
    await expect(expired.client.camsPollen.fetchLatest()).rejects.toMatchObject({ code: "EXPIRED" });
  });

  it("rejects invalid port configuration instead of silently enabling it", () => {
    for (const readPrefetchedObject of [true, {}, "native"]) {
      expect(() => harness({ readPrefetchedObject })).toThrowError(expect.objectContaining({ code: "INVALID_CONFIG" }));
    }
  });
});

describe("weather v1 local client", () => {
  function accumulationQuality(row) {
    return {
      schema_version: "icon-accumulation-tolerance.v1",
      fields: Object.fromEntries([
        ["precipitation_mm", 0.1, "mm"], ["liquid_rain_mm", 0.1, "mm"],
        ["snow_water_equivalent_mm", 0.02, "mm_swe"],
      ].map(([field, tolerance, unit]) => [field, {
        state: row[field] === null ? "resolution_tolerance_verified" : row[field] === 0 ? "known_zero" : "quantified",
        unit, known_component_sum_mm: row[field] ?? 0,
        unquantified_components: row[field] === null ? 1 : 0,
        resolution_budget_mm: row[field] === null ? 0.001 : 0,
        tolerance_mm: tolerance, reason: null,
      }])),
    };
  }

  it("legge vecchi documenti e il contratto additivo senza riempire i null dell'app", async () => {
    for (const extension of [false, true]) {
      const artifacts = buildArtifacts("icon2i", { mutatePayload: (document) => {
        const row = document.hourly[1];
        row.snow_water_equivalent_mm = null;
        if (extension) row.accumulation_quality = accumulationQuality(row);
      } });
      const { payload } = await fetchChain("icon2i", harness(), artifacts);
      expect(payload.document.hourly[1].snow_water_equivalent_mm).toBeNull();
      expect(payload.document.hourly[1].precipitation_mm).toBe(0);
      expect(payload.document.hourly[1].accumulation_quality).toEqual(artifacts.payload.hourly[1].accumulation_quality);
    }
  });

  it.each([
    ["unit", "cm"], ["tolerance_mm", 2], ["resolution_budget_mm", 1],
    ["known_component_sum_mm", false], ["unquantified_components", true],
    ["state", {}], ["reason", "guessed"],
  ])("rifiuta la prova di tolleranza invalida: %s", async (key, value) => {
    const artifacts = buildArtifacts("icon2i", { mutatePayload: (document) => {
      const row = document.hourly[1];
      row.snow_water_equivalent_mm = null;
      row.accumulation_quality = accumulationQuality(row);
      row.accumulation_quality.fields.snow_water_equivalent_mm[key] = value;
    } });
    await expect(fetchChain("icon2i", harness(), artifacts)).rejects.toMatchObject({ code: "INVALID_DOCUMENT" });
  });

  it("il bootstrap legge il latest raw verificato e le revoche senza rete ne vincolo di freshness", async () => {
    const warm = harness({ iconWindowPolicy: ICON_FORECAST_WINDOW_POLICY });
    const artifacts = buildArtifacts("icon2i", {
      mutateLatest: (latest) => { latest.disabled_run_ids = ["20260902T120000Z"]; },
    });
    await fetchChain("icon2i", warm, artifacts);
    const storage = memoryStorage(new Map(warm.storage.values));
    const options = { baseUrl: "http://127.0.0.1:8787", storage, catalog: CATALOG, istatCodes: CODES };
    const latest = readCachedIconLatest(options);
    expect(latest).toEqual(artifacts.latest);
    expect(latest.disabled_run_ids).toEqual(["20260902T120000Z"]);
    expect(Object.isFrozen(latest.disabled_run_ids)).toBe(true);
    expect(readCachedIconLatest({ ...options, baseUrl: "http://127.0.0.1:8788" })).toBeNull();
    expect(warm.fetchImpl).toHaveBeenCalledTimes(3);
  });

  it.each(["hash", "catalog"])("il bootstrap rifiuta latest cold-cache con %s invalido", async (failure) => {
    const warm = harness();
    await fetchChain("icon2i", warm, buildArtifacts("icon2i"));
    const storage = memoryStorage(new Map(warm.storage.values));
    const { key, record } = cachedBodyRecords(storage, "icon2i", "latest")[0];
    if (failure === "hash") {
      record.body_sha256 = "0".repeat(64);
      storage.removeItem.mockImplementation(() => { throw new Error("storage is read-only"); });
    } else {
      const latest = JSON.parse(record.body);
      latest.catalog.sha256 = "0".repeat(64);
      record.body = canonicalJsonStringify(latest);
      record.body_sha256 = sha256Hex(record.body);
      record.body_bytes = new TextEncoder().encode(record.body).length;
    }
    storage.values.set(key, JSON.stringify(record));
    const options = { baseUrl: "http://127.0.0.1:8787", storage, catalog: CATALOG, istatCodes: CODES };
    expect(readCachedIconLatest(options)).toBeNull();
    expect(readCachedIconLatest(options)).toBeNull();
  });

  it("la policy pilota usa solo ore future reali senza alterare la freshness del contratto", async () => {
    for (const nowHours of [25.5, 48, 60.5, 61]) {
      const artifacts = buildArtifacts("icon2i");
      const testHarness = harness({ nowHours, iconWindowPolicy: ICON_FORECAST_WINDOW_POLICY });
      const { latest, manifest, payload } = await fetchChain("icon2i", testHarness, artifacts);
      expect(latest).not.toHaveProperty("freshness");
      expect(manifest.freshness).toMatchObject({ status: "stale", requiredFutureHours: 12, localWindowPolicy: true });
      expect(payload.freshness.availableFutureHours).toBe(73 - Math.ceil(nowHours));
      expect(payload.document.freshness).toEqual(freshness("icon2i"));
      expect(payload.document.hourly).toHaveLength(73);
    }
  });

  it("12 timestamp futuri sono utilizzabili ma un millisecondo dopo restano 11 e sono rifiutati", async () => {
    const artifacts = buildArtifacts("icon2i");
    const exact = harness({ nowHours: 61, iconWindowPolicy: ICON_FORECAST_WINDOW_POLICY });
    const { payload } = await fetchChain("icon2i", exact, artifacts);
    expect(payload.freshness.availableFutureHours).toBe(12);
    const short = harness({ nowHours: 61 + 1 / HOUR_MS, iconWindowPolicy: ICON_FORECAST_WINDOW_POLICY });
    short.responses.push(jsonResponse(artifacts.latestBody), jsonResponse(artifacts.manifestBody));
    const latest = await short.client.icon2i.fetchLatest();
    await expect(short.client.icon2i.fetchManifest(latest)).rejects.toMatchObject({ code: "EXPIRED" });
  });

  it("il puntatore pilota con current non ancora valido permette il previous verificato", async () => {
    const artifacts = buildArtifacts("icon2i");
    const oldDescriptor = artifacts.latest.latest;
    const currentRunId = "20260903T120000Z";
    const pointer = {
      ...artifacts.latest,
      previous: oldDescriptor,
      latest: { ...oldDescriptor, source_run_id: currentRunId, run_at: isoAt(12), manifest_path: `runs/${currentRunId}/manifest.json` },
    };
    const testHarness = harness({ nowHours: 10, iconWindowPolicy: ICON_FORECAST_WINDOW_POLICY });
    testHarness.responses.push(jsonResponse(canonicalJsonStringify(pointer)), jsonResponse(artifacts.manifestBody), jsonResponse(artifacts.payloadBody));
    const latest = await testHarness.client.icon2i.fetchLatest();
    const manifest = await testHarness.client.icon2i.fetchManifest(latest, undefined, { previous: true });
    const payload = await testHarness.client.icon2i.fetchMunicipality(manifest, TARGET);
    expect(payload.document.source_run_id).toBe(RUN_ID);
  });

  it("force pilota interroga la rete ma recupera raw ICON verificati solo su guasto transitorio", async () => {
    const storage = memoryStorage();
    const artifacts = buildArtifacts("icon2i");
    await fetchChain("icon2i", harness({ storage }), artifacts);
    const fallback = harness({ storage, nowHours: 48, force: true, iconWindowPolicy: ICON_FORECAST_WINDOW_POLICY });
    fallback.responses.push(jsonResponse("", { status: 503 }), jsonResponse("", { status: 429 }));
    const latest = await fallback.client.icon2i.fetchLatest();
    const manifest = await fallback.client.icon2i.fetchManifest(latest);
    const payload = await fallback.client.icon2i.fetchMunicipality(manifest, TARGET);
    expect([latest, manifest, payload].every((item) => item.networkFallback)).toBe(true);
    expect(fallback.requests).toHaveLength(3);
    for (const request of fallback.requests) {
      expect(request.options.cache).toBe("no-store");
      expect(request.options.headers).not.toHaveProperty("If-None-Match");
    }
  });

  it.each([401, 403, 404])("force pilota non maschera HTTP %s con la cache", async (httpStatus) => {
    const storage = memoryStorage();
    await fetchChain("icon2i", harness({ storage }), buildArtifacts("icon2i"));
    const testHarness = harness({ storage, force: true, iconWindowPolicy: ICON_FORECAST_WINDOW_POLICY });
    testHarness.responses.push(jsonResponse("", { status: httpStatus }));
    await expect(testHarness.client.icon2i.fetchLatest()).rejects.toMatchObject({ code: "HTTP_ERROR", httpStatus });
    const offline = harness({ storage, force: true, iconWindowPolicy: ICON_FORECAST_WINDOW_POLICY });
    await expect(offline.client.icon2i.fetchLatest()).rejects.toMatchObject({ code: "TRANSPORT_FAILURE" });
  });

  it("force pilota non maschera un abort come fallback e mantiene la cache per il prossimo tentativo", async () => {
    const storage = memoryStorage();
    await fetchChain("icon2i", harness({ storage }), buildArtifacts("icon2i"));
    const testHarness = harness({ storage, force: true, iconWindowPolicy: ICON_FORECAST_WINDOW_POLICY });
    testHarness.fetchImpl.mockRejectedValueOnce(abortErrorForTest());
    await expect(testHarness.client.icon2i.fetchLatest()).rejects.toMatchObject({ code: "TRANSPORT_FAILURE", aborted: true });
    const recovered = await testHarness.client.icon2i.fetchLatest();
    expect(recovered.networkFallback).toBe(true);
  });

  it("un latest invalido invalida i raw precedenti e non riemerge dopo un errore di rete", async () => {
    const storage = memoryStorage();
    const artifacts = buildArtifacts("icon2i");
    await fetchChain("icon2i", harness({ storage }), artifacts);
    const testHarness = harness({ storage, force: true, iconWindowPolicy: ICON_FORECAST_WINDOW_POLICY });
    testHarness.responses.push(jsonResponse("{}"));
    await expect(testHarness.client.icon2i.fetchLatest()).rejects.toMatchObject({ code: "INVALID_DOCUMENT" });
    await expect(testHarness.client.icon2i.fetchLatest()).rejects.toMatchObject({ code: "TRANSPORT_FAILURE" });
    testHarness.responses.push(jsonResponse(artifacts.latestBody));
    expect((await testHarness.client.icon2i.fetchLatest()).document.latest.source_run_id).toBe(RUN_ID);
    const updated = { ...artifacts.latest, revision: 2, published_at: isoAt(3) };
    testHarness.responses.push(jsonResponse(canonicalJsonStringify(updated), { etag: '"recovered-latest"' }));
    expect((await testHarness.client.icon2i.fetchLatest()).document.revision).toBe(2);
  });

  it("la policy pilota non allenta hash, copertura nativa o policy documentale", async () => {
    const malformed = [
      buildArtifacts("icon2i", { mutatePayload: (payload) => payload.hourly.splice(30, 1) }),
      buildArtifacts("icon2i", { mutatePayload: (payload) => { payload.freshness.required_future_hours = 12; } }),
    ];
    for (const artifacts of malformed) {
      const testHarness = harness({ nowHours: 48, iconWindowPolicy: ICON_FORECAST_WINDOW_POLICY });
      await expect(fetchChain("icon2i", testHarness, artifacts)).rejects.toBeInstanceOf(WeatherV1ClientError);
    }
    const artifacts = buildArtifacts("icon2i");
    const testHarness = harness({ nowHours: 48, iconWindowPolicy: ICON_FORECAST_WINDOW_POLICY });
    testHarness.responses.push(jsonResponse(artifacts.latestBody), jsonResponse(artifacts.manifestBody), jsonResponse(`${artifacts.payloadBody} `));
    const latest = await testHarness.client.icon2i.fetchLatest();
    const manifest = await testHarness.client.icon2i.fetchManifest(latest);
    await expect(testHarness.client.icon2i.fetchMunicipality(manifest, TARGET)).rejects.toMatchObject({ code: "INTEGRITY_MISMATCH" });
  });

  it("un payload di rete con hash errato impedisce che il prossimo guasto recuperi i vecchi raw", async () => {
    const storage = memoryStorage();
    const artifacts = buildArtifacts("icon2i");
    await fetchChain("icon2i", harness({ storage }), artifacts);
    const testHarness = harness({ storage, nowHours: 48, force: true, iconWindowPolicy: ICON_FORECAST_WINDOW_POLICY });
    testHarness.responses.push(jsonResponse(artifacts.latestBody), jsonResponse(artifacts.manifestBody), jsonResponse(`${artifacts.payloadBody} `));
    const latest = await testHarness.client.icon2i.fetchLatest();
    const manifest = await testHarness.client.icon2i.fetchManifest(latest);
    await expect(testHarness.client.icon2i.fetchMunicipality(manifest, TARGET)).rejects.toMatchObject({ code: "INTEGRITY_MISMATCH" });
    await expect(testHarness.client.icon2i.fetchMunicipality(manifest, TARGET)).rejects.toMatchObject({ code: "TRANSPORT_FAILURE" });
  });

  it("una revoca pilota osservata impedisce riuso del vecchio token anche da un altro client", async () => {
    const storage = memoryStorage();
    const artifacts = buildArtifacts("icon2i");
    const first = harness({ storage, iconWindowPolicy: ICON_FORECAST_WINDOW_POLICY });
    const old = await fetchChain("icon2i", first, artifacts);
    const nextRunId = "20260903T120000Z";
    const revokedPointer = {
      ...artifacts.latest,
      revision: artifacts.latest.revision + 1,
      previous: null,
      disabled_run_ids: [RUN_ID],
      latest: { ...artifacts.latest.latest, source_run_id: nextRunId, run_at: isoAt(12), manifest_path: `runs/${nextRunId}/manifest.json` },
    };
    const updated = harness({ storage, iconWindowPolicy: ICON_FORECAST_WINDOW_POLICY });
    updated.responses.push(jsonResponse(canonicalJsonStringify(revokedPointer), { etag: '"new-pointer"' }));
    await updated.client.icon2i.fetchLatest();
    await expect(first.client.icon2i.fetchMunicipality(old.manifest, TARGET)).rejects.toMatchObject({ code: "RUN_DISABLED" });
    await expect(first.client.icon2i.fetchManifest(old.latest)).rejects.toMatchObject({ code: "RUN_DISABLED" });
  });

  it("policy pilota invalida non puo disabilitare il minimo e CAMS mantiene la policy originale", async () => {
    expect(() => harness({ iconWindowPolicy: { ...ICON_FORECAST_WINDOW_POLICY, minimumFutureHours: 0 } }))
      .toThrowError(expect.objectContaining({ code: "INVALID_CONFIG" }));
    const testHarness = harness({ nowHours: 31, iconWindowPolicy: ICON_FORECAST_WINDOW_POLICY });
    await expect(fetchChain("cams_europe", testHarness, buildArtifacts("cams_europe")))
      .rejects.toMatchObject({ code: "EXPIRED" });
  });

  it("usa SHA-256 deterministico e richiede tutte le dipendenze iniettate", () => {
    expect(sha256Hex("abc")).toBe("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
    expect(() => createWeatherV1Client()).toThrowError(
      expect.objectContaining({ code: "INVALID_CONFIG" }),
    );
  });

  it("rimuove le cache raw v2/v3 ritirate senza toccare chiavi estranee", () => {
    const scope = sha256Hex("http://127.0.0.1:8787").slice(0, 16);
    const legacyLatest = `meteofriul:weather-v1:v2:${scope}:cams_europe:latest:0`;
    const legacyPayload = `meteofriul:weather-v1:v2:${scope}:cams_europe_pollen:municipality:3`;
    const legacyFamily = `meteofriul:weather-v1:v3:${scope}:families/cams:release:1`;
    const unrelated = "meteofriul:other-feature:keep";
    const storage = memoryStorage(new Map([
      [legacyLatest, "legacy-latest"],
      [legacyPayload, "legacy-payload"],
      [legacyFamily, "legacy-family"],
      [unrelated, "preserved"],
    ]));

    harness({ storage });

    expect(storage.values.has(legacyLatest)).toBe(false);
    expect(storage.values.has(legacyPayload)).toBe(false);
    expect(storage.values.has(legacyFamily)).toBe(false);
    expect(storage.values.get(unrelated)).toBe("preserved");
  });

  it("recupera quota rimuovendo soltanto gli scope raw v4 di endpoint obsoleti", () => {
    const currentBaseUrl = "http://127.0.0.1:8787";
    const obsoleteScope = sha256Hex("http://127.0.0.1:8781").slice(0, 16);
    const currentScope = sha256Hex(currentBaseUrl).slice(0, 16);
    const obsoleteLatest = `meteofriul:weather-v1:v4:${obsoleteScope}:icon2i:latest:0`;
    const obsoletePayload = `meteofriul:weather-v1:v4:${obsoleteScope}:cams_europe:municipality:3`;
    const obsoleteIndex = `meteofriul:weather-v1:v4:${obsoleteScope}:families/cams:lru`;
    const currentPayload = `meteofriul:weather-v1:v4:${currentScope}:icon2i:municipality:0`;
    const bundleFromOtherScope = `meteofriul:weather-v1:bundle:v4:${obsoleteScope}:${"a".repeat(16)}:istat:093033`;
    const malformedLookalike = `meteofriul:weather-v1:v4:${obsoleteScope}:icon2i:municipality:99`;
    const unrelated = "meteofriul:events:v1:keep";
    const storage = enumerableMemoryStorage(new Map([
      [obsoleteLatest, "obsolete-latest"],
      [obsoletePayload, "obsolete-payload"],
      [obsoleteIndex, "obsolete-index"],
      [currentPayload, "current-payload"],
      [bundleFromOtherScope, "bundle"],
      [malformedLookalike, "malformed"],
      [unrelated, "preserved"],
    ]));

    harness({ storage });

    expect(storage.values.has(obsoleteLatest)).toBe(false);
    expect(storage.values.has(obsoletePayload)).toBe(false);
    expect(storage.values.has(obsoleteIndex)).toBe(false);
    expect(storage.values.get(currentPayload)).toBe("current-payload");
    expect(storage.values.get(bundleFromOtherScope)).toBe("bundle");
    expect(storage.values.get(malformedLookalike)).toBe("malformed");
    expect(storage.values.get(unrelated)).toBe("preserved");
  });

  it("invoca fetch con il contesto globale richiesto dai browser", async () => {
    const artifacts = buildArtifacts("icon2i");
    let observedThis = null;
    const fetchImpl = vi.fn(function fetchWithBrowserBrand() {
      observedThis = this;
      if (this !== globalThis) throw new TypeError("Illegal invocation");
      return Promise.resolve(jsonResponse(artifacts.latestBody, { etag: '"browser-latest"' }));
    });
    const client = createWeatherV1Client({
      baseUrl: "http://127.0.0.1:8787",
      fetchImpl,
      storage: memoryStorage(),
      now: () => Date.parse(RUN_AT) + 10 * HOUR_MS,
      catalog: CATALOG,
      istatCodes: CODES,
    });

    await expect(client.icon2i.fetchLatest()).resolves.toMatchObject({
      document: { provider: "icon2i" },
    });
    expect(observedThis).toBe(globalThis);
  });

  it("rifiuta il catalogo legacy anche se hash e copertura hanno forma valida", () => {
    expect(() =>
      createWeatherV1Client({
        baseUrl: "http://127.0.0.1:8787",
        fetchImpl: vi.fn(),
        storage: memoryStorage(),
        now: () => Date.parse(RUN_AT),
        catalog: { ...CATALOG, version: ["istat", "codici", "2026", "02", "21"].join("-") },
        istatCodes: CODES,
      }),
    ).toThrowError(expect.objectContaining({ code: "INVALID_CONFIG" }));
  });

  it("scarica latest, manifest e payload ICON separatamente e valida la catena", async () => {
    const testHarness = harness();
    const artifacts = buildArtifacts("icon2i");
    const chain = await fetchChain("icon2i", testHarness, artifacts);

    expect(chain.payload.document.municipality.istat_code).toBe(TARGET);
    expect(chain.manifest.freshness).toMatchObject({
      status: "fresh",
      requiredFutureHours: 48,
      remainingCoverageHours: 62,
    });
    expect(testHarness.requests.map(({ url }) => url)).toEqual([
      "http://127.0.0.1:8787/weather/v1/icon2i/latest.json",
      `http://127.0.0.1:8787/weather/v1/icon2i/runs/${RUN_ID}/manifest.json`,
      `http://127.0.0.1:8787/weather/v1/icon2i/runs/${RUN_ID}/municipalities/${TARGET}.json`,
    ]);
    expect(testHarness.storage.values.size).toBe(4);
  });

  it("valida anche la catena CAMS senza condividere cache o URL con ICON", async () => {
    const testHarness = harness();
    const artifacts = buildArtifacts("cams_europe");
    const chain = await fetchChain("cams_europe", testHarness, artifacts);

    expect(chain.payload.document.provider).toBe("cams_europe");
    expect(chain.payload.document.hourly).toHaveLength(97);
    expect(testHarness.requests.map(({ url }) => url)).toEqual([
      "http://127.0.0.1:8787/weather/v1/families/cams/latest.json",
      `http://127.0.0.1:8787/weather/v1/families/cams/runs/${RUN_ID}/release.json`,
      `http://127.0.0.1:8787/weather/v1/cams_europe/runs/${RUN_ID}/manifest.json`,
      `http://127.0.0.1:8787/weather/v1/cams_europe/runs/${RUN_ID}/municipalities/${TARGET}.json`,
    ]);
    expect(Object.keys(testHarness.client).sort()).toEqual(["camsEurope", "camsFamily", "camsPollen", "icon2i"]);
    expect(Object.keys(testHarness.client)).not.toContain("openMeteo");

    const iconArtifacts = buildArtifacts("icon2i");
    testHarness.responses.push(jsonResponse(iconArtifacts.latestBody, { etag: '"icon-latest"' }));
    await testHarness.client.icon2i.fetchLatest();
    const cacheKeys = [...testHarness.storage.values.keys()];
    expect(cacheKeys.some((key) => key.includes(":cams_europe:"))).toBe(true);
    expect(cacheKeys.some((key) => key.includes(":icon2i:"))).toBe(true);
    expect(new Set(cacheKeys).size).toBe(cacheKeys.length);
  });

  it("valida il provider pollini derivato senza ridurre il provider CAMS completo", async () => {
    const testHarness = harness();
    const artifacts = buildArtifacts("cams_europe_pollen");
    const chain = await fetchChain("cams_europe_pollen", testHarness, artifacts);

    expect(chain.payload.document).toMatchObject({
      kind: "meteofriul.weather.cams.pollen_municipality",
      provider: "cams_europe_pollen",
      model: CONTRACT.cams_europe.model,
      source: CONTRACT.cams_europe.source,
      health_classification: null,
      projection: CAMS_POLLEN_PROJECTION,
    });
    expect(chain.payload.document.variables.map(({ id }) => id)).toEqual(CAMS_POLLEN_IDS);
    expect(chain.payload.document.hourly).toHaveLength(97);
    expect(Object.keys(chain.payload.document.hourly[0].values)).toEqual(CAMS_POLLEN_IDS);
    expect(chain.payload.document.freshness.policy_id).toBe("cams_pollen_current_v1");
    expect(testHarness.requests.map(({ url }) => url)).toEqual([
      "http://127.0.0.1:8787/weather/v1/families/cams/latest.json",
      `http://127.0.0.1:8787/weather/v1/families/cams/runs/${RUN_ID}/release.json`,
      `http://127.0.0.1:8787/weather/v1/cams_europe_pollen/runs/${RUN_ID}/manifest.json`,
      `http://127.0.0.1:8787/weather/v1/cams_europe_pollen/runs/${RUN_ID}/municipalities/${TARGET}.json`,
    ]);
    expect(testHarness.client.camsEurope.provider).toBe("cams_europe");
    expect(testHarness.client.camsPollen.provider).toBe("cams_europe_pollen");
  });

  it("lega entrambi i provider allo stesso snapshot family senza richiedere latest legacy", async () => {
    const testHarness = harness();
    const family = buildCamsFamilyArtifacts();
    testHarness.responses.push(
      jsonResponse(family.latestBody, { etag: '"family-shared"' }),
      jsonResponse(family.releaseBody, { etag: '"release-shared"' }),
    );

    const [coreLatest, pollenLatest] = await Promise.all([
      testHarness.client.camsEurope.fetchLatest(),
      testHarness.client.camsPollen.fetchLatest(),
    ]);

    expect(coreLatest.document.latest.source_run_id).toBe(RUN_ID);
    expect(pollenLatest.document.latest.source_run_id).toBe(RUN_ID);
    expect(testHarness.fetchImpl).toHaveBeenCalledTimes(2);
    const urls = testHarness.requests.map(({ url }) => url);
    expect(urls).toEqual([
      "http://127.0.0.1:8787/weather/v1/families/cams/latest.json",
      `http://127.0.0.1:8787/weather/v1/families/cams/runs/${RUN_ID}/release.json`,
    ]);
    expect(urls.some((url) => /\/cams_europe(?:_pollen)?\/latest\.json$/.test(url))).toBe(false);
  });

  it("espone core e pollini da un solo snapshot family anche se vengono consumati in sequenza", async () => {
    const testHarness = harness();
    const family = buildCamsFamilyArtifacts();
    testHarness.responses.push(
      jsonResponse(family.latestBody, { etag: '"family-pair"' }),
      jsonResponse(family.releaseBody, { etag: '"release-pair"' }),
      jsonResponse(family.core.manifestBody, { etag: '"core-manifest"' }),
      jsonResponse(family.pollen.manifestBody, { etag: '"pollen-manifest"' }),
    );

    const members = await testHarness.client.camsFamily.fetchMembersLatest();
    const coreManifest = await testHarness.client.camsEurope.fetchManifest(members.camsEurope);
    const pollenManifest = await testHarness.client.camsPollen.fetchManifest(members.camsPollen);

    expect(members.camsEurope.document.latest.source_run_id).toBe(RUN_ID);
    expect(members.camsPollen.document.latest.source_run_id).toBe(RUN_ID);
    expect(coreManifest.document.source_run_id).toBe(RUN_ID);
    expect(pollenManifest.document.source_run_id).toBe(RUN_ID);
    expect(testHarness.requests.map(({ url }) => url)).toEqual([
      "http://127.0.0.1:8787/weather/v1/families/cams/latest.json",
      `http://127.0.0.1:8787/weather/v1/families/cams/runs/${RUN_ID}/release.json`,
      `http://127.0.0.1:8787/weather/v1/cams_europe/runs/${RUN_ID}/manifest.json`,
      `http://127.0.0.1:8787/weather/v1/cams_europe_pollen/runs/${RUN_ID}/manifest.json`,
    ]);
  });

  it("fallisce chiuso su una release CAMS mixed-run prima di leggere i manifest", async () => {
    const family = buildCamsFamilyArtifacts({
      mutateRelease(release) {
        release.components.pollen.source_run_id = "20260902T000000Z";
      },
    });
    const testHarness = harness();
    testHarness.responses.push(jsonResponse(family.latestBody), jsonResponse(family.releaseBody));

    await expect(testHarness.client.camsPollen.fetchLatest()).rejects.toMatchObject({
      code: "RUN_MISMATCH",
    });
    expect(testHarness.requests).toHaveLength(2);
    expect(
      testHarness.requests.some(({ url }) => /\/cams_europe(?:_pollen)?\/latest\.json$/.test(url)),
    ).toBe(false);
  });

  it("rifiuta un manifest che non coincide col descriptor firmato dalla release family", async () => {
    const pollen = buildArtifacts("cams_europe_pollen");
    const family = buildCamsFamilyArtifacts({ pollen });
    family.release.components.pollen.manifest_sha256 = "c".repeat(64);
    family.releaseBody = canonicalJsonStringify(family.release);
    family.latest.latest.release_json_bytes = new TextEncoder().encode(family.releaseBody).length;
    family.latest.latest.release_sha256 = sha256Hex(family.releaseBody);
    family.latestBody = canonicalJsonStringify(family.latest);
    const testHarness = harness();
    testHarness.responses.push(
      jsonResponse(family.latestBody),
      jsonResponse(family.releaseBody),
      jsonResponse(pollen.manifestBody),
    );

    const latest = await testHarness.client.camsPollen.fetchLatest();
    await expect(testHarness.client.camsPollen.fetchManifest(latest)).rejects.toMatchObject({
      code: "INTEGRITY_MISMATCH",
    });
    expect(testHarness.requests.map(({ url }) => url)).toEqual([
      "http://127.0.0.1:8787/weather/v1/families/cams/latest.json",
      `http://127.0.0.1:8787/weather/v1/families/cams/runs/${RUN_ID}/release.json`,
      `http://127.0.0.1:8787/weather/v1/cams_europe_pollen/runs/${RUN_ID}/manifest.json`,
    ]);
  });

  it("rifiuta previous CAMS uguale o successiva alla release current", async () => {
    const family = buildCamsFamilyArtifacts({
      mutateFamilyLatest(latest) {
        latest.previous = { ...latest.latest };
      },
    });
    const testHarness = harness();
    testHarness.responses.push(jsonResponse(family.latestBody));

    await expect(testHarness.client.camsFamily.fetchLatest()).rejects.toMatchObject({
      code: "RUN_MISMATCH",
    });
    expect(testHarness.requests).toHaveLength(1);
  });

  it.each([
    ["lista mancante", (latest) => { delete latest.disabled_run_ids; }, "INVALID_DOCUMENT"],
    [
      "duplicato",
      (latest) => { latest.disabled_run_ids = ["20260901T000000Z", "20260901T000000Z"]; },
      "INVALID_DOCUMENT",
    ],
    [
      "ordine non canonico",
      (latest) => {
        latest.disabled_run_ids = ["20260902T000000Z", "20260901T000000Z"];
      },
      "INVALID_DOCUMENT",
    ],
    ["run non canonico", (latest) => { latest.disabled_run_ids = ["bad-run"]; }, "INVALID_DOCUMENT"],
    ["active revocato", (latest) => { latest.disabled_run_ids = [RUN_ID]; }, "RUN_DISABLED"],
    [
      "previous revocato",
      (latest) => {
        latest.previous = {
          ...latest.latest,
          source_run_id: "20260902T000000Z",
          release_path: "runs/20260902T000000Z/release.json",
        };
        latest.disabled_run_ids = ["20260902T000000Z"];
      },
      "RUN_DISABLED",
    ],
  ])("rifiuta disabled_run_ids CAMS non esatto: %s", async (_label, mutate, code) => {
    const family = buildCamsFamilyArtifacts({ mutateFamilyLatest: mutate });
    const testHarness = harness();
    testHarness.responses.push(jsonResponse(family.latestBody));

    await expect(testHarness.client.camsFamily.fetchLatest()).rejects.toMatchObject({ code });
    expect(testHarness.requests).toHaveLength(1);
  });

  it("accetta una release CAMS anteriore al puntatore family", async () => {
    const family = buildCamsFamilyArtifacts({
      releasePublishedAt: isoAt(1),
      pointerPublishedAt: isoAt(2),
    });
    const testHarness = harness();
    testHarness.responses.push(jsonResponse(family.latestBody), jsonResponse(family.releaseBody));

    await expect(testHarness.client.camsFamily.fetchLatest()).resolves.toMatchObject({
      document: { published_at: isoAt(2) },
      release: { published_at: isoAt(1) },
    });
  });

  it("accetta B->A solo come rollback revocante e invalida cache raw e token B", async () => {
    const rollbackRunId = "20260902T180000Z";
    const rollback = buildCamsFamilyArtifacts({
      sourceRunId: rollbackRunId,
      revision: 4,
      releasePublishedAt: "2026-09-02T20:00:00Z",
      pointerPublishedAt: isoAt(3),
      disabledRunIds: [RUN_ID],
    });
    const current = buildCamsFamilyArtifacts({
      previous: rollback.latest.latest,
    });
    const storage = memoryStorage();
    const testHarness = harness({ storage });
    testHarness.responses.push(
      jsonResponse(current.latestBody, { etag: '"family-b"' }),
      jsonResponse(current.releaseBody, { etag: '"release-b"' }),
      jsonResponse(current.core.manifestBody, { etag: '"core-b"' }),
      jsonResponse(current.pollen.manifestBody, { etag: '"pollen-b"' }),
      jsonResponse(current.pollen.payloadBody, { etag: '"payload-b"' }),
    );
    const currentMembers = await testHarness.client.camsFamily.fetchMembersLatest();
    await testHarness.client.camsEurope.fetchManifest(currentMembers.camsEurope);
    const currentPollenManifest = await testHarness.client.camsPollen.fetchManifest(
      currentMembers.camsPollen,
    );
    await testHarness.client.camsPollen.fetchMunicipality(currentPollenManifest, TARGET);

    testHarness.responses.push(
      jsonResponse(rollback.latestBody, { etag: '"family-a"' }),
      jsonResponse(rollback.releaseBody, { etag: '"release-a"' }),
    );
    const rolledBack = await testHarness.client.camsFamily.fetchMembersLatest();

    expect(rolledBack.camsEurope.document).toMatchObject({
      revision: 4,
      latest: { source_run_id: rollbackRunId },
      disabled_run_ids: [RUN_ID],
    });
    expect(rolledBack.camsPollen.document.disabled_run_ids).toEqual([RUN_ID]);
    const requestCount = testHarness.requests.length;
    await expect(
      testHarness.client.camsPollen.fetchManifest(currentMembers.camsPollen),
    ).rejects.toMatchObject({ code: "RUN_DISABLED" });
    await expect(
      testHarness.client.camsPollen.fetchMunicipality(currentPollenManifest, TARGET),
    ).rejects.toMatchObject({ code: "RUN_DISABLED" });
    expect(testHarness.requests).toHaveLength(requestCount);
    for (const provider of ["families/cams", "cams_europe", "cams_europe_pollen"]) {
      const records = ["release", "manifest", "municipality"]
        .flatMap((kind) => cachedBodyRecords(storage, provider, kind));
      expect(records.some(({ record }) => record.path.includes(RUN_ID))).toBe(false);
    }
  });

  it.each([
    ["revision invariata", { revision: 1, disabledRunIds: [RUN_ID] }],
    ["run B non revocato", { revision: 2, disabledRunIds: [] }],
  ])("rifiuta rollback CAMS %s", async (_label, rollbackOptions) => {
    const rollbackRunId = "20260902T180000Z";
    const target = buildCamsFamilyArtifacts({
      sourceRunId: rollbackRunId,
      pointerPublishedAt: isoAt(3),
      releasePublishedAt: "2026-09-02T20:00:00Z",
      ...rollbackOptions,
    });
    const current = buildCamsFamilyArtifacts({ previous: target.latest.latest });
    const testHarness = harness();
    testHarness.responses.push(
      jsonResponse(current.latestBody),
      jsonResponse(current.releaseBody),
      jsonResponse(target.latestBody),
      jsonResponse(target.releaseBody),
    );
    await testHarness.client.camsFamily.fetchLatest();

    await expect(testHarness.client.camsFamily.fetchLatest()).rejects.toMatchObject({
      code: "RUN_MISMATCH",
    });
  });

  it.each([2, 3])(
    "accetta un rollback revision %i solo verso il previous del puntatore B cached",
    async (revision) => {
    const previous = buildCamsFamilyArtifacts({ sourceRunId: "20260902T180000Z" });
    const current = buildCamsFamilyArtifacts({ previous: previous.latest.latest });
    const storage = memoryStorage();
    const warm = harness({ storage });
    warm.responses.push(jsonResponse(current.latestBody), jsonResponse(current.releaseBody));
    await warm.client.camsFamily.fetchLatest();

    const wrongTarget = buildCamsFamilyArtifacts({
      sourceRunId: "20260902T120000Z",
      revision,
      releasePublishedAt: "2026-09-02T14:00:00Z",
      pointerPublishedAt: isoAt(3),
      disabledRunIds: [RUN_ID],
    });
    const reloaded = harness({ storage: memoryStorage(storage.values) });
    reloaded.responses.push(jsonResponse(wrongTarget.latestBody));

    await expect(reloaded.client.camsFamily.fetchLatest()).rejects.toMatchObject({
      code: "RUN_MISMATCH",
    });
    expect(reloaded.requests).toHaveLength(1);
    },
  );

  it("vincola il previous di un forward consecutivo C alla release B completa", async () => {
    const current = buildCamsFamilyArtifacts();
    const arbitrary = buildCamsFamilyArtifacts({ sourceRunId: "20260902T180000Z" });
    const nextRunId = "20260903T060000Z";
    const invalidNext = buildCamsFamilyArtifacts({
      sourceRunId: nextRunId,
      revision: 2,
      previous: arbitrary.latest.latest,
      releasePublishedAt: isoAt(8),
      pointerPublishedAt: isoAt(8),
    });
    const testHarness = harness();
    testHarness.responses.push(
      jsonResponse(current.latestBody),
      jsonResponse(current.releaseBody),
      jsonResponse(invalidNext.latestBody),
    );
    await testHarness.client.camsFamily.fetchLatest();

    await expect(testHarness.client.camsFamily.fetchLatest()).rejects.toMatchObject({
      code: "RUN_MISMATCH",
    });
    expect(testHarness.requests).toHaveLength(3);
  });

  it("accetta un forward consecutivo C con previous B esatto", async () => {
    const current = buildCamsFamilyArtifacts();
    const next = buildCamsFamilyArtifacts({
      sourceRunId: "20260903T060000Z",
      revision: 2,
      previous: current.latest.latest,
      releasePublishedAt: isoAt(8),
      pointerPublishedAt: isoAt(8),
    });
    const testHarness = harness();
    testHarness.responses.push(
      jsonResponse(current.latestBody),
      jsonResponse(current.releaseBody),
      jsonResponse(next.latestBody),
      jsonResponse(next.releaseBody),
    );
    await testHarness.client.camsFamily.fetchLatest();

    await expect(testHarness.client.camsFamily.fetchLatest()).resolves.toMatchObject({
      document: {
        revision: 2,
        latest: { source_run_id: "20260903T060000Z" },
        previous: { source_run_id: RUN_ID },
      },
    });
  });

  it.each([
    [
      "forward con previous arbitrario piu vecchio",
      (current, arbitrary) => buildCamsFamilyArtifacts({
        sourceRunId: "20260903T060000Z",
        revision: 3,
        previous: arbitrary.latest.latest,
        releasePublishedAt: isoAt(8),
        pointerPublishedAt: isoAt(8),
        disabledRunIds: [RUN_ID],
      }),
    ],
    [
      "forward senza previous ne revoca di B",
      () => buildCamsFamilyArtifacts({
        sourceRunId: "20260903T060000Z",
        revision: 3,
        releasePublishedAt: isoAt(8),
        pointerPublishedAt: isoAt(8),
      }),
    ],
    [
      "same-active che conserva un previous",
      (current) => buildCamsFamilyArtifacts({
        revision: 3,
        previous: current.latest.previous,
        pointerPublishedAt: isoAt(3),
      }),
    ],
  ])("rifiuta una transizione CAMS con gap: %s", async (_label, candidateFactory) => {
    const previous = buildCamsFamilyArtifacts({ sourceRunId: "20260902T180000Z" });
    const current = buildCamsFamilyArtifacts({ previous: previous.latest.latest });
    const arbitrary = buildCamsFamilyArtifacts({ sourceRunId: "20260902T120000Z" });
    const candidate = candidateFactory(current, arbitrary);
    const testHarness = harness();
    testHarness.responses.push(
      jsonResponse(current.latestBody),
      jsonResponse(current.releaseBody),
      jsonResponse(candidate.latestBody),
    );
    await testHarness.client.camsFamily.fetchLatest();

    await expect(testHarness.client.camsFamily.fetchLatest()).rejects.toMatchObject({
      code: "RUN_MISMATCH",
    });
    expect(testHarness.requests).toHaveLength(3);
  });

  it("purga B prima di una quota sul rollback e non lo fa riapparire offline", async () => {
    const rollbackRunId = "20260902T180000Z";
    const rollback = buildCamsFamilyArtifacts({
      sourceRunId: rollbackRunId,
      revision: 2,
      releasePublishedAt: "2026-09-02T20:00:00Z",
      pointerPublishedAt: isoAt(3),
      disabledRunIds: [RUN_ID],
    });
    const current = buildCamsFamilyArtifacts({ previous: rollback.latest.latest });
    const storage = memoryStorage();
    const testHarness = harness({ storage });
    testHarness.responses.push(jsonResponse(current.latestBody), jsonResponse(current.releaseBody));
    await testHarness.client.camsFamily.fetchLatest();

    storage.setItem.mockImplementation(() => {
      throw new DOMException("quota", "QuotaExceededError");
    });
    testHarness.responses.push(jsonResponse(rollback.latestBody), jsonResponse(rollback.releaseBody));
    await expect(testHarness.client.camsFamily.fetchLatest()).resolves.toMatchObject({
      document: { latest: { source_run_id: rollbackRunId }, disabled_run_ids: [RUN_ID] },
      cachePersisted: false,
    });
    expect(cachedBodyRecords(storage, "families/cams", "latest")).toHaveLength(0);
    for (const provider of ["families/cams", "cams_europe", "cams_europe_pollen"]) {
      const records = ["release", "manifest", "municipality"]
        .flatMap((kind) => cachedBodyRecords(storage, provider, kind));
      expect(records.some(({ record }) => record.path.includes(RUN_ID))).toBe(false);
    }

    const offline = harness({ storage: memoryStorage(storage.values) });
    await expect(offline.client.camsFamily.fetchLatest()).rejects.toMatchObject({
      code: "TRANSPORT_FAILURE",
    });
  });

  it("invalida logicamente B se localStorage blocca removeItem", async () => {
    const rollbackRunId = "20260902T180000Z";
    const rollback = buildCamsFamilyArtifacts({
      sourceRunId: rollbackRunId,
      revision: 2,
      releasePublishedAt: "2026-09-02T20:00:00Z",
      pointerPublishedAt: isoAt(3),
      disabledRunIds: [RUN_ID],
    });
    const current = buildCamsFamilyArtifacts({ previous: rollback.latest.latest });
    const storage = memoryStorage();
    const testHarness = harness({ storage });
    testHarness.responses.push(jsonResponse(current.latestBody), jsonResponse(current.releaseBody));
    const tokenB = await testHarness.client.camsPollen.fetchLatest();
    storage.removeItem.mockImplementation(() => {
      throw new Error("storage locked");
    });
    testHarness.responses.push(jsonResponse(rollback.latestBody), jsonResponse(rollback.releaseBody));

    await expect(testHarness.client.camsFamily.fetchLatest()).resolves.toMatchObject({
      document: { latest: { source_run_id: rollbackRunId }, disabled_run_ids: [RUN_ID] },
    });
    await expect(testHarness.client.camsPollen.fetchManifest(tokenB)).rejects.toMatchObject({
      code: "RUN_DISABLED",
    });
    const offline = harness({ storage: memoryStorage(storage.values) });
    await expect(offline.client.camsFamily.fetchLatest()).resolves.toMatchObject({
      document: { latest: { source_run_id: rollbackRunId }, disabled_run_ids: [RUN_ID] },
      networkFallback: true,
    });
  });

  it("applica la revoca del puntatore prima del fallback se la release A e offline", async () => {
    const rollbackRunId = "20260902T180000Z";
    const rollback = buildCamsFamilyArtifacts({
      sourceRunId: rollbackRunId,
      revision: 2,
      pointerPublishedAt: isoAt(3),
      releasePublishedAt: "2026-09-02T20:00:00Z",
      disabledRunIds: [RUN_ID],
    });
    const current = buildCamsFamilyArtifacts({ previous: rollback.latest.latest });
    const storage = memoryStorage();
    const testHarness = harness({ storage });
    testHarness.responses.push(jsonResponse(current.latestBody), jsonResponse(current.releaseBody));
    const tokenB = await testHarness.client.camsPollen.fetchLatest();
    testHarness.responses.push(jsonResponse(rollback.latestBody));

    const failure = await testHarness.client.camsFamily.fetchLatest().catch((error) => error);
    expect(failure).toMatchObject({
      code: "TRANSPORT_FAILURE",
      camsFamilyLatest: {
        revision: 2,
        latest: { source_run_id: rollbackRunId },
        disabled_run_ids: [RUN_ID],
      },
    });
    expect(cachedBodyRecords(storage, "families/cams", "latest")).toHaveLength(0);
    expect(cachedBodyRecords(storage, "families/cams", "release")).toHaveLength(0);
    const requestCount = testHarness.requests.length;
    await expect(testHarness.client.camsPollen.fetchManifest(tokenB)).rejects.toMatchObject({
      code: "RUN_DISABLED",
    });
    expect(testHarness.requests).toHaveLength(requestCount);
  });

  it("segnala la revoca prima che una release che ignora AbortSignal termini", async () => {
    const rollbackRunId = "20260902T180000Z";
    const rollback = buildCamsFamilyArtifacts({
      sourceRunId: rollbackRunId,
      revision: 2,
      pointerPublishedAt: isoAt(3),
      releasePublishedAt: "2026-09-02T20:00:00Z",
      disabledRunIds: [RUN_ID],
    });
    const current = buildCamsFamilyArtifacts({ previous: rollback.latest.latest });
    const storage = memoryStorage();
    const testHarness = harness({ storage });
    testHarness.responses.push(jsonResponse(current.latestBody), jsonResponse(current.releaseBody));
    await testHarness.client.camsPollen.fetchLatest();

    const controller = new AbortController();
    const onFamilyLatest = vi.fn();
    testHarness.responses.push(jsonResponse(rollback.latestBody), new Promise(() => {}));
    const pending = testHarness.client.camsPollen.fetchLatest(controller.signal, onFamilyLatest);
    await vi.waitFor(() => expect(onFamilyLatest).toHaveBeenCalledOnce());
    expect(onFamilyLatest).toHaveBeenCalledWith({
      revision: 2,
      published_at: isoAt(3),
      latest: { source_run_id: rollbackRunId },
      disabled_run_ids: [RUN_ID],
    });
    expect(cachedBodyRecords(storage, "families/cams", "latest")).toHaveLength(0);
    expect(cachedBodyRecords(storage, "families/cams", "release")).toHaveLength(0);

    controller.abort();
    await expect(pending).rejects.toMatchObject({
      code: "TRANSPORT_FAILURE",
      camsFamilyLatest: { disabled_run_ids: [RUN_ID] },
    });
  });

  it("non assorbe un errore del destinatario della decisione CAMS verificata", async () => {
    const rollbackRunId = "20260902T180000Z";
    const rollback = buildCamsFamilyArtifacts({
      sourceRunId: rollbackRunId,
      revision: 2,
      pointerPublishedAt: isoAt(3),
      releasePublishedAt: "2026-09-02T20:00:00Z",
      disabledRunIds: [RUN_ID],
    });
    const current = buildCamsFamilyArtifacts({ previous: rollback.latest.latest });
    const testHarness = harness({ storage: memoryStorage() });
    testHarness.responses.push(jsonResponse(current.latestBody), jsonResponse(current.releaseBody));
    await testHarness.client.camsFamily.fetchLatest();

    const safetyFailure = Object.assign(new Error("journal write failed"), {
      code: "CAMS_REVOCATION_PERSIST_FAILED",
    });
    const observer = vi.fn(() => { throw safetyFailure; });
    testHarness.responses.push(jsonResponse(rollback.latestBody));

    await expect(testHarness.client.camsFamily.fetchLatest(undefined, observer)).rejects.toBe(
      safetyFailure,
    );
    expect(observer).toHaveBeenCalledOnce();
    expect(testHarness.requests).toHaveLength(3);
  });

  it("consegna la decisione verificata anche se la bonifica della cache raw fallisce", async () => {
    const rollbackRunId = "20260902T180000Z";
    const rollback = buildCamsFamilyArtifacts({
      sourceRunId: rollbackRunId,
      revision: 2,
      pointerPublishedAt: isoAt(3),
      releasePublishedAt: "2026-09-02T20:00:00Z",
      disabledRunIds: [RUN_ID],
    });
    const current = buildCamsFamilyArtifacts({ previous: rollback.latest.latest });
    const storage = memoryStorage();
    const testHarness = harness({ storage });
    testHarness.responses.push(jsonResponse(current.latestBody), jsonResponse(current.releaseBody));
    await testHarness.client.camsFamily.fetchLatest();
    storage.removeItem.mockImplementation(() => { throw new Error("remove blocked"); });
    storage.setItem.mockImplementation(() => { throw new Error("write blocked"); });
    const observer = vi.fn();
    testHarness.responses.push(jsonResponse(rollback.latestBody));

    await expect(testHarness.client.camsFamily.fetchLatest(undefined, observer)).rejects.toMatchObject({
      code: "CACHE_INVALIDATION_FAILED",
      camsFamilyLatest: { disabled_run_ids: [RUN_ID] },
    });
    expect(observer).toHaveBeenCalledWith(expect.objectContaining({
      revision: 2,
      latest: { source_run_id: rollbackRunId },
      disabled_run_ids: [RUN_ID],
    }));
  });

  it("non autorizza un manifest CAMS ricostruito da un documento provider privo del token family", async () => {
    const artifacts = buildArtifacts("cams_europe_pollen");
    const testHarness = harness();

    await expect(
      testHarness.client.camsPollen.fetchManifest({ document: artifacts.latest }),
    ).rejects.toMatchObject({ code: "FAMILY_CONTEXT_REQUIRED" });
    expect(testHarness.requests).toHaveLength(0);
  });

  it("non persiste una family CAMS live gia scaduta", async () => {
    const storage = memoryStorage();
    const family = buildCamsFamilyArtifacts();
    const testHarness = harness({ storage, nowHours: 31 });
    testHarness.responses.push(
      jsonResponse(family.latestBody, { etag: '"family-expired"' }),
      jsonResponse(family.releaseBody, { etag: '"release-expired"' }),
    );

    await expect(testHarness.client.camsPollen.fetchLatest()).rejects.toMatchObject({
      code: "EXPIRED",
    });
    expect(cachedBodyRecords(storage, "families/cams", "latest")).toHaveLength(0);
    expect(cachedBodyRecords(storage, "families/cams", "release")).toHaveLength(0);
  });

  it("scarta una family CAMS cached quando non e piu utilizzabile", async () => {
    const storage = memoryStorage();
    const family = buildCamsFamilyArtifacts();
    const warm = harness({ storage });
    warm.responses.push(
      jsonResponse(family.latestBody, { etag: '"family-cached"' }),
      jsonResponse(family.releaseBody, { etag: '"release-cached"' }),
    );
    await warm.client.camsPollen.fetchLatest();
    expect(cachedBodyRecords(storage, "families/cams", "latest")).toHaveLength(1);
    expect(cachedBodyRecords(storage, "families/cams", "release")).toHaveLength(1);

    const expired = harness({ storage, nowHours: 31 });
    await expect(expired.client.camsPollen.fetchLatest()).rejects.toMatchObject({
      code: "EXPIRED",
    });
    expect(cachedBodyRecords(storage, "families/cams", "latest")).toHaveLength(0);
    expect(cachedBodyRecords(storage, "families/cams", "release")).toHaveLength(0);
  });

  it("non persiste il family latest se la release non entra nella cache durevole", async () => {
    const storage = memoryStorage();
    storage.setItem.mockImplementation((key, value) => {
      if (key.includes(":families/cams:release:")) {
        throw new DOMException("quota", "QuotaExceededError");
      }
      storage.values.set(key, value);
    });
    const family = buildCamsFamilyArtifacts();
    const testHarness = harness({ storage });
    testHarness.responses.push(jsonResponse(family.latestBody), jsonResponse(family.releaseBody));

    await expect(testHarness.client.camsFamily.fetchLatest()).resolves.toMatchObject({
      fromCache: false,
      cachePersisted: false,
    });
    expect(cachedBodyRecords(storage, "families/cams", "latest")).toHaveLength(0);
    expect(cachedBodyRecords(storage, "families/cams", "release")).toHaveLength(0);
  });

  it.each([
    [
      "una settima variabile",
      (payload) => {
        payload.variables = [...payload.variables, CAMS_VARIABLES.find(({ id }) => id === "ammonia")];
      },
      "INVALID_DOCUMENT",
    ],
    [
      "la proiezione con ordine diverso",
      (payload) => {
        payload.projection = {
          ...payload.projection,
          retained_variable_ids: [...payload.projection.retained_variable_ids].reverse(),
        };
      },
      "INVALID_DOCUMENT",
    ],
    [
      "un valore pollinico mancante",
      (payload) => {
        delete payload.hourly[0].values.alder_pollen;
      },
      "INVALID_DOCUMENT",
    ],
    [
      "una classificazione sanitaria",
      (payload) => {
        payload.health_classification = { level: "low" };
      },
      "INVALID_DOCUMENT",
    ],
    [
      "una timeline di sole 96 ore",
      (payload) => {
        payload.hourly.pop();
      },
      "COVERAGE_MISMATCH",
    ],
  ])("rifiuta nel payload pollini %s", async (_label, mutatePayload, code) => {
    const artifacts = buildArtifacts("cams_europe_pollen", { mutatePayload });
    const family = buildCamsFamilyArtifacts({ pollen: artifacts });
    const testHarness = harness();
    testHarness.responses.push(
      jsonResponse(family.latestBody),
      jsonResponse(family.releaseBody),
      jsonResponse(artifacts.manifestBody),
      jsonResponse(artifacts.payloadBody),
    );
    const latest = await testHarness.client.camsPollen.fetchLatest();
    const manifest = await testHarness.client.camsPollen.fetchManifest(latest);

    await expect(
      testHarness.client.camsPollen.fetchMunicipality(manifest, TARGET),
    ).rejects.toMatchObject({ code });
    expect(cachedBodyRecords(testHarness.storage, "cams_europe_pollen", "municipality")).toHaveLength(0);
  });

  it("verifica l'integrita del payload pollini contro il manifest", async () => {
    const artifacts = buildArtifacts("cams_europe_pollen");
    const family = buildCamsFamilyArtifacts({ pollen: artifacts });
    const testHarness = harness();
    testHarness.responses.push(
      jsonResponse(family.latestBody),
      jsonResponse(family.releaseBody),
      jsonResponse(artifacts.manifestBody),
      jsonResponse(artifacts.payloadBody.replace('"alder_pollen":1', '"alder_pollen":2')),
    );
    const latest = await testHarness.client.camsPollen.fetchLatest();
    const manifest = await testHarness.client.camsPollen.fetchManifest(latest);

    await expect(
      testHarness.client.camsPollen.fetchMunicipality(manifest, TARGET),
    ).rejects.toMatchObject({ code: "INTEGRITY_MISMATCH" });
  });

  it("mantiene una cache family condivisa e cache payload separate per CAMS completo e pollini", async () => {
    const storage = memoryStorage();
    await fetchChain("cams_europe", harness({ storage }), buildArtifacts("cams_europe"));
    await fetchChain(
      "cams_europe_pollen",
      harness({ storage, force: true }),
      buildArtifacts("cams_europe_pollen"),
    );
    const fullCamsBefore = new Map(
      [...storage.values].filter(([key]) => key.includes(":cams_europe:")),
    );
    expect(cachedBodyRecords(storage, "families/cams", "latest")).toHaveLength(1);
    expect(cachedBodyRecords(storage, "families/cams", "release")).toHaveLength(1);
    expect(cachedBodyRecords(storage, "cams_europe", "municipality")).toHaveLength(1);
    expect(cachedBodyRecords(storage, "cams_europe_pollen", "municipality")).toHaveLength(1);

    const revalidated = harness({ storage: memoryStorage(storage.values) });
    revalidated.responses.push(
      jsonResponse("", { status: 304, etag: '"family-latest-1"' }),
      jsonResponse("", { status: 304, etag: '"payload-1"' }),
    );
    const latest = await revalidated.client.camsPollen.fetchLatest();
    const manifest = await revalidated.client.camsPollen.fetchManifest(latest);
    const payload = await revalidated.client.camsPollen.fetchMunicipality(manifest, TARGET);

    expect([latest, manifest, payload].every(({ fromCache, notModified }) => (
      fromCache && notModified
    ))).toBe(true);
    expect(
      revalidated.requests[0].url.includes("/families/cams/latest.json"),
    ).toBe(true);
    expect(revalidated.requests).toHaveLength(2);
    expect(
      [...fullCamsBefore].every(([key, value]) => storage.values.get(key) === value),
    ).toBe(true);
  });

  it("invia If-None-Match e usa la cache verificata soltanto su 304 coerente", async () => {
    const testHarness = harness();
    const artifacts = buildArtifacts("icon2i");
    testHarness.responses.push(jsonResponse(artifacts.latestBody, { etag: '"latest-1"' }));
    await testHarness.client.icon2i.fetchLatest();

    testHarness.responses.push(jsonResponse("", { status: 304, etag: '"latest-1"' }));
    const cached = await testHarness.client.icon2i.fetchLatest();

    expect(cached).toMatchObject({ fromCache: true, notModified: true, etag: '"latest-1"' });
    expect(testHarness.requests[1].options.headers["If-None-Match"]).toBe('"latest-1"');
  });

  it("force bypassa ETag e cache del browser per tutta la catena provider", async () => {
    const sharedStorage = memoryStorage();
    const artifacts = buildArtifacts("icon2i");
    const warmHarness = harness({ storage: sharedStorage });
    await fetchChain("icon2i", warmHarness, artifacts);
    sharedStorage.getItem.mockClear();

    const forcedHarness = harness({ storage: sharedStorage, force: true });
    const forced = await fetchChain("icon2i", forcedHarness, artifacts);

    expect(forced.latest.fromCache).toBe(false);
    expect(forced.manifest.fromCache).toBe(false);
    expect(forced.payload.fromCache).toBe(false);
    expect(forced.payload.cachePersisted).toBe(true);
    expect(forcedHarness.requests).toHaveLength(3);
    for (const { options } of forcedHarness.requests) {
      expect(options.cache).toBe("no-store");
      expect(options.headers).not.toHaveProperty("If-None-Match");
    }
  });

  it("deduplica il cold start concorrente senza consumare due volte gli stessi body", async () => {
    const storage = memoryStorage();
    const artifacts = buildArtifacts("icon2i");
    const responses = [
      jsonResponse(artifacts.latestBody, { etag: '"latest-shared"' }),
      jsonResponse(artifacts.manifestBody, { etag: '"manifest-shared"' }),
      jsonResponse(artifacts.payloadBody, { etag: '"payload-shared"' }),
    ];
    const fetchImpl = vi.fn(async () => responses.shift());
    const options = {
      baseUrl: "http://127.0.0.1:8787",
      fetchImpl,
      storage,
      now: () => Date.parse(RUN_AT) + 10 * HOUR_MS,
      catalog: CATALOG,
      istatCodes: CODES,
    };
    const left = createWeatherV1Client(options).icon2i;
    const right = createWeatherV1Client(options).icon2i;

    const [leftLatest, rightLatest] = await Promise.all([left.fetchLatest(), right.fetchLatest()]);
    const [leftManifest, rightManifest] = await Promise.all([
      left.fetchManifest(leftLatest),
      right.fetchManifest(rightLatest),
    ]);
    const [leftPayload, rightPayload] = await Promise.all([
      left.fetchMunicipality(leftManifest, TARGET),
      right.fetchMunicipality(rightManifest, TARGET),
    ]);

    expect(fetchImpl).toHaveBeenCalledTimes(3);
    expect(leftPayload.document).toEqual(rightPayload.document);
    expect(responses).toHaveLength(0);
  });

  it("l'abort di un consumer non annulla la richiesta condivisa dell'altro", async () => {
    const artifacts = buildArtifacts("icon2i");
    let release;
    let transportSignal;
    const fetchImpl = vi.fn((_url, options) => new Promise((resolve, reject) => {
      transportSignal = options.signal;
      release = () => resolve(jsonResponse(artifacts.latestBody, { etag: '"latest-shared"' }));
      options.signal?.addEventListener("abort", () => reject(abortErrorForTest()), { once: true });
    }));
    const options = {
      baseUrl: "http://127.0.0.1:8787",
      fetchImpl,
      storage: memoryStorage(),
      now: () => Date.parse(RUN_AT) + 10 * HOUR_MS,
      catalog: CATALOG,
      istatCodes: CODES,
    };
    const left = createWeatherV1Client(options).icon2i;
    const right = createWeatherV1Client(options).icon2i;
    const leftController = new AbortController();
    const rightController = new AbortController();
    const leftPromise = left.fetchLatest(leftController.signal);
    const rightPromise = right.fetchLatest(rightController.signal);
    await vi.waitFor(() => expect(fetchImpl).toHaveBeenCalledTimes(1));

    leftController.abort();
    await expect(leftPromise).rejects.toMatchObject({ code: "TRANSPORT_FAILURE" });
    expect(transportSignal.aborted).toBe(false);
    release();
    await expect(rightPromise).resolves.toMatchObject({ fromCache: false });
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });

  it("non deduplica due richieste network-only force", async () => {
    const artifacts = buildArtifacts("icon2i");
    const fetchImpl = vi.fn(async () => jsonResponse(artifacts.latestBody, { etag: '"forced"' }));
    const options = {
      baseUrl: "http://127.0.0.1:8787",
      fetchImpl,
      storage: memoryStorage(),
      now: () => Date.parse(RUN_AT) + 10 * HOUR_MS,
      catalog: CATALOG,
      istatCodes: CODES,
      force: true,
    };
    await Promise.all([
      createWeatherV1Client(options).icon2i.fetchLatest(),
      createWeatherV1Client(options).icon2i.fetchLatest(),
    ]);
    expect(fetchImpl).toHaveBeenCalledTimes(2);
  });

  it("funziona senza localStorage e riusa in memoria solo il documento verificato", async () => {
    const artifacts = buildArtifacts("icon2i");
    const responses = [jsonResponse(artifacts.latestBody, { etag: '"volatile"' })];
    const fetchImpl = vi.fn(async () => {
      if (!responses.length) throw new Error("offline");
      return responses.shift();
    });
    const options = {
      baseUrl: "http://127.0.0.1:8799",
      fetchImpl,
      storage: null,
      now: () => Date.parse(RUN_AT) + 10 * HOUR_MS,
      catalog: CATALOG,
      istatCodes: CODES,
    };
    const live = await createWeatherV1Client(options).icon2i.fetchLatest();
    const offline = await createWeatherV1Client(options).icon2i.fetchLatest();

    expect(live).toMatchObject({ fromCache: false, cachePersisted: false });
    expect(offline).toMatchObject({
      fromCache: true,
      networkFallback: true,
      fallbackReason: "transport_failure",
    });
    expect(fetchImpl).toHaveBeenCalledTimes(2);
  });

  it("isola l'AbortSignal del chiamante tramite segnali di trasporto interni", async () => {
    const testHarness = harness();
    const controller = new AbortController();
    await fetchChain("cams_europe", testHarness, buildArtifacts("cams_europe"), controller.signal);

    expect(testHarness.requests).toHaveLength(4);
    expect(testHarness.requests.every(({ options }) => options.signal instanceof AbortSignal)).toBe(true);
    expect(testHarness.requests.every(({ options }) => options.signal !== controller.signal)).toBe(true);
  });

  it("su 500 usa solo la cache verificata e segnala esplicitamente il fallback di rete", async () => {
    const testHarness = harness();
    const artifacts = buildArtifacts("icon2i");
    testHarness.responses.push(jsonResponse(artifacts.latestBody, { etag: '"latest-1"' }));
    await testHarness.client.icon2i.fetchLatest();
    testHarness.responses.push(jsonResponse("", { status: 500 }));

    await expect(testHarness.client.icon2i.fetchLatest()).resolves.toMatchObject({
      fromCache: true,
      notModified: false,
      networkFallback: true,
      fallbackReason: "http_500",
      freshness: { status: "fresh" },
    });
    expect(testHarness.fetchImpl).toHaveBeenCalledTimes(2);
    expect(testHarness.requests.some(({ url }) => /open.?meteo/i.test(url))).toBe(false);
  });

  it("ricostruisce offline l'intera catena solo da corpi in cache nuovamente validati", async () => {
    const storage = memoryStorage();
    const artifacts = buildArtifacts("cams_europe");
    await fetchChain("cams_europe", harness({ storage }), artifacts);

    const offline = harness({ storage: memoryStorage(storage.values) });
    const latest = await offline.client.camsEurope.fetchLatest();
    const manifest = await offline.client.camsEurope.fetchManifest(latest);
    const payload = await offline.client.camsEurope.fetchMunicipality(manifest, TARGET);

    for (const item of [latest, manifest, payload]) {
      expect(item).toMatchObject({
        fromCache: true,
        notModified: false,
        networkFallback: true,
        fallbackReason: "transport_failure",
      });
    }
    expect(payload.freshness).toMatchObject({ status: "fresh", remainingCoverageHours: 86 });
    expect(offline.requests).toHaveLength(4);
    expect(offline.requests.some(({ url }) => /open.?meteo/i.test(url))).toBe(false);
  });

  it("accetta offline lo stale utilizzabile ma rifiuta e scarta il latest cached scaduto", async () => {
    const storage = memoryStorage();
    const artifacts = buildArtifacts("icon2i");
    await fetchChain("icon2i", harness({ storage }), artifacts);

    const stale = harness({ storage, nowHours: 20 });
    const staleLatest = await stale.client.icon2i.fetchLatest();
    const staleManifest = await stale.client.icon2i.fetchManifest(staleLatest);
    const stalePayload = await stale.client.icon2i.fetchMunicipality(staleManifest, TARGET);
    expect([staleLatest, staleManifest, stalePayload].every((item) => item.networkFallback)).toBe(true);
    expect(stalePayload.freshness).toMatchObject({ status: "stale", remainingCoverageHours: 52 });

    const expired = harness({ storage, nowHours: 25 });
    await expect(expired.client.icon2i.fetchLatest()).rejects.toMatchObject({ code: "EXPIRED" });
    expect(cachedBodyRecords(storage, "icon2i", "latest")).toHaveLength(0);
  });

  it("non usa la cache su errori HTTP definitivi, abort o force", async () => {
    const storage = memoryStorage();
    const artifacts = buildArtifacts("icon2i");
    const warm = harness({ storage });
    warm.responses.push(jsonResponse(artifacts.latestBody, { etag: '"latest-1"' }));
    await warm.client.icon2i.fetchLatest();

    const notFound = harness({ storage });
    notFound.responses.push(jsonResponse("", { status: 404 }));
    await expect(notFound.client.icon2i.fetchLatest()).rejects.toMatchObject({ code: "HTTP_ERROR" });

    const aborted = harness({ storage });
    const controller = new AbortController();
    controller.abort();
    await expect(aborted.client.icon2i.fetchLatest(controller.signal)).rejects.toMatchObject({
      code: "TRANSPORT_FAILURE",
    });

    const forced = harness({ storage, force: true });
    await expect(forced.client.icon2i.fetchLatest()).rejects.toMatchObject({
      code: "TRANSPORT_FAILURE",
    });
    expect(forced.requests[0].options).toMatchObject({ cache: "no-store" });
    expect(forced.requests[0].options.headers).not.toHaveProperty("If-None-Match");
  });

  it("rifiuta e rimuove un corpo cached manomesso anche se i metadati locali sono ricalcolati", async () => {
    const storage = memoryStorage();
    const artifacts = buildArtifacts("icon2i");
    const warm = harness({ storage });
    warm.responses.push(jsonResponse(artifacts.latestBody, { etag: '"latest-1"' }));
    await warm.client.icon2i.fetchLatest();

    const [{ key, record }] = cachedBodyRecords(storage, "icon2i", "latest");
    record.body = record.body.replace('"provider":"icon2i"', '"provider":"open_meteo"');
    record.body_bytes = new TextEncoder().encode(record.body).length;
    record.body_sha256 = sha256Hex(record.body);
    storage.values.set(key, JSON.stringify(record));

    const offline = harness({ storage: memoryStorage(storage.values) });
    await expect(offline.client.icon2i.fetchLatest()).rejects.toMatchObject({
      code: "PROVIDER_MISMATCH",
    });
    expect(storage.values.has(key)).toBe(false);
  });

  it("una quota esaurita non trasforma una risposta live verificata in errore", async () => {
    const storage = memoryStorage();
    storage.setItem.mockImplementation(() => {
      throw new DOMException("quota", "QuotaExceededError");
    });
    const testHarness = harness({ storage });
    const artifacts = buildArtifacts("icon2i");
    testHarness.responses.push(jsonResponse(artifacts.latestBody, { etag: '"latest-live"' }));

    await expect(testHarness.client.icon2i.fetchLatest()).resolves.toMatchObject({
      fromCache: false,
      cachePersisted: false,
      etag: '"latest-live"',
    });
    expect(storage.values.size).toBe(0);
  });

  it("un errore di scrittura conserva il record verificato precedente e restituisce il nuovo live", async () => {
    const storage = memoryStorage();
    const artifacts = buildArtifacts("icon2i");
    const warm = harness({ storage });
    warm.responses.push(jsonResponse(artifacts.latestBody, { etag: '"latest-old"' }));
    await warm.client.icon2i.fetchLatest();
    const [{ key }] = cachedBodyRecords(storage, "icon2i", "latest");
    const oldRaw = storage.values.get(key);
    storage.setItem.mockImplementation((storageKey, value) => {
      if (storageKey === key) throw new DOMException("quota", "QuotaExceededError");
      storage.values.set(storageKey, value);
    });

    const live = harness({ storage });
    live.responses.push(jsonResponse(artifacts.latestBody, { etag: '"latest-new"' }));
    await expect(live.client.icon2i.fetchLatest()).resolves.toMatchObject({
      fromCache: false,
      cachePersisted: false,
      etag: '"latest-new"',
    });
    expect(storage.values.get(key)).toBe(oldRaw);

    storage.setItem.mockImplementation((storageKey, value) => storage.values.set(storageKey, value));
    const revalidated = harness({ storage });
    revalidated.responses.push(jsonResponse("", { status: 304, etag: '"latest-new"' }));
    await expect(revalidated.client.icon2i.fetchLatest()).resolves.toMatchObject({
      fromCache: true,
      notModified: true,
      etag: '"latest-new"',
    });
  });

  it("una cache corrotta e non eliminabile non blocca una risposta live valida", async () => {
    const storage = memoryStorage();
    const artifacts = buildArtifacts("icon2i");
    const warm = harness({ storage });
    warm.responses.push(jsonResponse(artifacts.latestBody, { etag: '"latest-old"' }));
    await warm.client.icon2i.fetchLatest();
    const [{ key, record }] = cachedBodyRecords(storage, "icon2i", "latest");
    record.body += " ";
    storage.values.set(key, JSON.stringify(record));
    storage.removeItem.mockImplementation(() => {
      throw new Error("storage locked");
    });

    const live = harness({ storage });
    live.responses.push(jsonResponse(artifacts.latestBody, { etag: '"latest-new"' }));
    await expect(live.client.icon2i.fetchLatest()).resolves.toMatchObject({
      fromCache: false,
      cachePersisted: true,
      etag: '"latest-new"',
    });
    expect(JSON.parse(storage.values.get(key)).etag).toBe('"latest-new"');
  });

  it("mantiene al massimo quattro Comuni per provider con sostituzione LRU indipendente", async () => {
    const storage = memoryStorage();
    const testHarness = harness({ storage });
    const iconArtifacts = buildArtifacts("icon2i");
    await fetchChain("icon2i", testHarness, iconArtifacts);
    const iconKeysBefore = [...storage.values.keys()].filter((key) => key.includes(":icon2i:"));

    for (const index of [0, 1, 2, 3, 0, 4, 5]) {
      const code = CODES[index];
      const artifacts = buildArtifacts("cams_europe", {
        payloadIstat: code,
        descriptorIstat: code,
      });
      await fetchChain("cams_europe", testHarness, artifacts, undefined, code);
    }

    const municipalityRecords = cachedBodyRecords(storage, "cams_europe", "municipality");
    expect(municipalityRecords).toHaveLength(4);
    expect(
      municipalityRecords.map(({ record }) => record.path.match(/(\d{6})\.json$/)[1]).sort(),
    ).toEqual([CODES[0], CODES[3], CODES[4], CODES[5]].sort());
    expect(
      cachedBodyRecords(storage, "cams_europe", "latest")
        .concat(cachedBodyRecords(storage, "cams_europe", "manifest"))
        .concat(municipalityRecords)
        .reduce((sum, { record }) => sum + record.body_bytes, 0),
    ).toBeLessThanOrEqual(1792 * 1024);
    expect(iconKeysBefore.every((key) => storage.values.has(key))).toBe(true);
  });

  it("riduce ulteriormente l'LRU dei Comuni quando raggiunge il budget byte", async () => {
    const storage = memoryStorage();
    const testHarness = harness({ storage });
    for (const index of [0, 1, 2, 3]) {
      const code = CODES[index];
      const artifacts = buildArtifacts("cams_europe", {
        payloadIstat: code,
        descriptorIstat: code,
        mutatePayload(payload) {
          payload.hourly[0].quality_flags.alder_pollen = [`padding-${"x".repeat(390_000)}`];
        },
      });
      expect(new TextEncoder().encode(artifacts.payloadBody).length).toBeLessThan(512 * 1024);
      await fetchChain("cams_europe", testHarness, artifacts, undefined, code);
    }

    const allRecords = [
      ...cachedBodyRecords(storage, "cams_europe", "latest"),
      ...cachedBodyRecords(storage, "cams_europe", "manifest"),
      ...cachedBodyRecords(storage, "cams_europe", "municipality"),
    ];
    expect(cachedBodyRecords(storage, "cams_europe", "municipality").length).toBeLessThan(4);
    expect(allRecords.reduce((sum, { record }) => sum + record.body_bytes, 0)).toBeLessThanOrEqual(
      1792 * 1024,
    );
  });

  it("rifiuta un 304 senza una cache associata al provider", async () => {
    const testHarness = harness();
    testHarness.responses.push(jsonResponse("", { status: 304, etag: '"unknown"' }));
    await expect(testHarness.client.camsEurope.fetchLatest()).rejects.toMatchObject({
      code: "CACHE_MISS_304",
    });
  });

  it.each([
    ["provider", (latest) => { latest.provider = "open_meteo"; }, "PROVIDER_MISMATCH"],
    ["catalogo", (latest) => { latest.catalog = { ...CATALOG, sha256: "b".repeat(64) }; }, "CATALOG_MISMATCH"],
    [
      "versione catalogo",
      (latest) => { latest.catalog = { ...CATALOG, version: ["istat", "codici", "2026", "02", "21"].join("-") }; },
      "CATALOG_MISMATCH",
    ],
    ["path", (latest) => { latest.latest.manifest_path = "../manifest.json"; }, "PATH_MISMATCH"],
  ])("fallisce chiuso se latest altera %s", async (_label, mutateLatest, code) => {
    const artifacts = buildArtifacts("icon2i", { mutateLatest });
    const testHarness = harness();
    testHarness.responses.push(jsonResponse(artifacts.latestBody));
    await expect(testHarness.client.icon2i.fetchLatest()).rejects.toMatchObject({ code });
    expect(testHarness.storage.values.size).toBe(0);
  });

  it("rifiuta JSON non canonico, campi extra e chiavi duplicate", async () => {
    const artifacts = buildArtifacts("icon2i");
    const bodies = [
      ` ${artifacts.latestBody}`,
      canonicalJsonStringify({ ...artifacts.latest, extra: true }),
      artifacts.latestBody.replace('"catalog":', '"catalog":null,"catalog":'),
    ];
    for (const body of bodies) {
      const testHarness = harness();
      testHarness.responses.push(jsonResponse(body));
      await expect(testHarness.client.icon2i.fetchLatest()).rejects.toBeInstanceOf(WeatherV1ClientError);
    }
  });

  it("rifiuta manifest con run errato, copertura ISTAT incompleta o path payload alterato", async () => {
    const mutations = [
      (manifest) => { manifest.source_run_id = "20260902T000000Z"; },
      (manifest) => { delete manifest.objects[CODES.at(-1)]; },
      (manifest) => { manifest.objects[TARGET].path = "runs/escape.json"; },
    ];
    for (const mutateManifest of mutations) {
      const artifacts = buildArtifacts("icon2i", { mutateManifest });
      const testHarness = harness();
      testHarness.responses.push(jsonResponse(artifacts.latestBody), jsonResponse(artifacts.manifestBody));
      const latest = await testHarness.client.icon2i.fetchLatest();
      await expect(testHarness.client.icon2i.fetchManifest(latest)).rejects.toBeInstanceOf(
        WeatherV1ClientError,
      );
    }
  });

  it("rifiuta un payload alterato anche se il JSON resta valido", async () => {
    const artifacts = buildArtifacts("icon2i");
    const testHarness = harness();
    testHarness.responses.push(
      jsonResponse(artifacts.latestBody),
      jsonResponse(artifacts.manifestBody),
      jsonResponse(artifacts.payloadBody.replace('"temperature_c":10', '"temperature_c":11')),
    );
    const latest = await testHarness.client.icon2i.fetchLatest();
    const manifest = await testHarness.client.icon2i.fetchManifest(latest);
    await expect(testHarness.client.icon2i.fetchMunicipality(manifest, TARGET)).rejects.toMatchObject({
      code: "INTEGRITY_MISMATCH",
    });
  });

  it("rifiuta ISTAT nel body diverso dal path anche con hash coerente", async () => {
    const artifacts = buildArtifacts("icon2i", { payloadIstat: CODES[1] });
    const testHarness = harness();
    testHarness.responses.push(
      jsonResponse(artifacts.latestBody),
      jsonResponse(artifacts.manifestBody),
      jsonResponse(artifacts.payloadBody),
    );
    const latest = await testHarness.client.icon2i.fetchLatest();
    const manifest = await testHarness.client.icon2i.fetchManifest(latest);
    await expect(testHarness.client.icon2i.fetchMunicipality(manifest, TARGET)).rejects.toMatchObject({
      code: "ISTAT_MISMATCH",
    });
  });

  it("espone stale solo entro la finestra utilizzabile e poi rifiuta copertura insufficiente", async () => {
    const artifacts = buildArtifacts("icon2i");
    const staleHarness = harness({ nowHours: 20 });
    staleHarness.responses.push(jsonResponse(artifacts.latestBody), jsonResponse(artifacts.manifestBody));
    const staleLatest = await staleHarness.client.icon2i.fetchLatest();
    const staleManifest = await staleHarness.client.icon2i.fetchManifest(staleLatest);
    expect(staleManifest.freshness).toMatchObject({ status: "stale", remainingCoverageHours: 52 });

    const expiredHarness = harness({ nowHours: 25 });
    expiredHarness.responses.push(jsonResponse(artifacts.latestBody), jsonResponse(artifacts.manifestBody));
    await expect(expiredHarness.client.icon2i.fetchLatest()).rejects.toMatchObject({
      code: "EXPIRED",
    });
  });
});


describe("additive CAMS 36-hour continuity", () => {
  function setup({ nowHours = 33, enabled = true, missing = null, mutate, storage = memoryStorage() } = {}) {
    const family = buildCamsFamilyArtifacts();
    const grant = { schema_version: 1, kind: "meteofriul.weather.cams_continuity",
      policy_id: "cams_continuity_36h_v1", source_run_id: RUN_ID, catalog: CATALOG,
      release_sha256: family.latest.latest.release_sha256,
      release_json_bytes: family.latest.latest.release_json_bytes,
      issued_at: family.release.published_at, run_at: RUN_AT,
      fresh_until: isoAt(24), usable_until: isoAt(36), current_sample_max_lag_minutes: 60 };
    mutate?.(grant);
    const objects = new Map([
      ["families/cams/latest.json", family.latestBody],
      [`families/cams/runs/${RUN_ID}/release.json`, family.releaseBody],
      [`families/cams/runs/${RUN_ID}/continuity.json`, canonicalJsonStringify(grant)],
      ...["core", "pollen"].flatMap(role => {
        const provider = role === "core" ? "cams_europe" : "cams_europe_pollen";
        return [[`${provider}/runs/${RUN_ID}/manifest.json`, family[role].manifestBody],
          [`${provider}/runs/${RUN_ID}/municipalities/${TARGET}.json`, family[role].payloadBody]];
      }),
    ]);
    const state = { offline: false, nowHours, missing };
    const fetchImpl = vi.fn(async url => {
      if (state.offline) throw new TypeError("offline");
      const path = url.split("/weather/v1/")[1];
      if (path.endsWith("continuity.json") && state.missing) return jsonResponse("", { status: state.missing });
      return objects.has(path) ? jsonResponse(objects.get(path)) : jsonResponse("", { status: 404 });
    });
    const client = createWeatherV1Client({ baseUrl: "http://127.0.0.1:8787", fetchImpl,
      catalog: CATALOG, istatCodes: CODES, storage, camsContinuity: enabled,
      now: () => Date.parse(RUN_AT) + state.nowHours * HOUR_MS });
    async function read() {
      const latest = await client.camsPollen.fetchLatest();
      const manifest = await client.camsPollen.fetchManifest(latest);
      return client.camsPollen.fetchMunicipality(manifest, TARGET);
    }
    return { read, client, state, fetchImpl, storage, grant };
  }
  it.each([[24,"fresh"], [24+1/HOUR_MS,"stale"], [30,"stale"], [33,"stale"], [36,"stale"]])(
    "keeps native sample and 24h freshness at %s hours", async (nowHours, status) => {
      const h = setup({ nowHours }); const result = await h.read();
      expect(result.freshness).toMatchObject({ status, freshUntil: isoAt(24), usableUntil: isoAt(36), continuity: h.grant });
      expect(result.document.freshness.usable_until).toBe(isoAt(30));
      expect(result.document.run_at).toBe(RUN_AT);
    });
  it("fails closed immediately after 36h", async () => {
    await expect(setup({ nowHours: 36+1/HOUR_MS }).read()).rejects.toMatchObject({ code: "EXPIRED" });
  });
  it("leaves legacy clients at 30h without requesting the additive document", async () => {
    const h = setup({ enabled: false, nowHours: 30 });
    expect((await h.read()).freshness.usableUntil).toBe(isoAt(30));
    expect(h.fetchImpl.mock.calls.some(([url]) => url.endsWith("continuity.json"))).toBe(false);
    h.state.nowHours = 30+1/HOUR_MS;
    await expect(h.read()).rejects.toMatchObject({ code: "EXPIRED" });
  });
  it.each([400,404,503])("falls back only to the v1 limit on HTTP %s", async missing => {
    const h = setup({ missing, nowHours: 30 });
    expect((await h.read()).freshness.usableUntil).toBe(isoAt(30));
    h.state.nowHours = 33;
    await expect(h.read()).rejects.toMatchObject({ code: "EXPIRED" });
  });
  it.each(["release_sha256","source_run_id","issued_at","fresh_until","usable_until","catalog"])(
    "rejects a modified %s grant", async field => {
      const h = setup({ mutate: doc => { doc[field] = "invalid"; } });
      await expect(h.read()).rejects.toMatchObject({ code: "CONTINUITY_MISMATCH" });
    });
  it("revalidates a cached grant offline and expires it without rejuvenating the run", async () => {
    const h = setup({ nowHours: 24 }); await h.read();
    h.state.offline = true; h.state.nowHours = 33;
    expect((await h.read()).freshness.status).toBe("stale");
    h.state.nowHours = 36+1/HOUR_MS;
    await expect(h.read()).rejects.toMatchObject({ code: "EXPIRED" });
  });
  it("discards a previously cached grant when the reader returns 404", async () => {
    const h = setup({ nowHours: 24 }); await h.read();
    h.state.missing = 404; h.state.nowHours = 33;
    await expect(h.read()).rejects.toMatchObject({ code: "EXPIRED" });
    h.state.offline = true;
    await expect(h.read()).rejects.toMatchObject({ code: "TRANSPORT_FAILURE" });
  });
});


describe("origin quota recovery", () => {
  it.each(["", "isolated-scope:"])("only releases same-endpoint raw municipality slots in storage scope %j", namespace => {
    const values = new Map();
    let capacity = Infinity;
    const original = {
      get length() { return values.size; },
      key: index => [...values.keys()][index] ?? null,
      getItem: key => values.get(key) ?? null,
      setItem(key, value) {
        const size = [...values].reduce((sum, [k, v]) => sum + (k === key ? 0 : k.length + v.length), 0);
        if (size + key.length + value.length > capacity) throw new DOMException("full", "QuotaExceededError");
        values.set(key, value);
      },
      removeItem: key => values.delete(key),
    };
    const baseUrl = "https://weather.example.test";
    const prefix = `meteofriul:weather-v1:v4:${sha256Hex(baseUrl).slice(0, 16)}:`;
    const storage = {
      getItem: key => original.getItem(`${namespace}${key}`),
      setItem: (key, value) => original.setItem(`${namespace}${key}`, value),
      removeItem: key => original.removeItem(`${namespace}${key}`),
    };
    const keep = {
      [`${prefix}icon2i:latest:0`]: "authoritative-pointer",
      [`${prefix}cams_europe:manifest:0`]: "manifest",
      [`${prefix}families/cams:latest:0`]: "revocations",
      "meteofriul:weather-v1:bundle:v4:active": "active-bundle",
      "mfTheme": "dark",
      "meteofriul:weather-v1:v4:otherendpoint:icon2i:municipality:0": "other-endpoint",
    };
    for (const [key, value] of Object.entries(keep)) storage.setItem(key, value);
    const outsideScopeKey = `${namespace ? "" : "another-scope:"}${prefix}cams_europe:municipality:0`;
    original.setItem(outsideScopeKey, "other-scope-must-stay");
    storage.setItem(`${prefix}cams_europe:municipality:0`, "x".repeat(4000));
    storage.setItem(`${prefix}icon2i:municipality:0`, "small-snapshot");
    capacity = [...values].reduce((sum, [key, value]) => sum + key.length + value.length, 0);
    writeWeatherV1CacheValue(storage, "new-candidate", "n".repeat(1000), baseUrl);
    expect(storage.getItem("new-candidate")).toHaveLength(1000);
    expect(storage.getItem(`${prefix}cams_europe:municipality:0`)).toBeNull();
    expect(storage.getItem(`${prefix}icon2i:municipality:0`)).toBe("small-snapshot");
    expect(original.getItem(outsideScopeKey)).toBe("other-scope-must-stay");
    for (const [key, value] of Object.entries(keep)) expect(storage.getItem(key)).toBe(value);
  });

  it.each(["SecurityError", "QuotaExceededError"])("keeps active data when recovery is unavailable: %s", name => {
    const baseUrl = "/quota-failure";
    const rawKey = `meteofriul:weather-v1:v4:${sha256Hex(baseUrl).slice(0, 16)}:icon2i:municipality:0`;
    const error = new DOMException("blocked", name);
    const storage = {
      setItem: vi.fn(() => { throw error; }),
      getItem: vi.fn(key => key === rawKey ? "keep" : null),
      removeItem: vi.fn(() => { throw new Error("removal blocked"); }),
    };
    expect(() => writeWeatherV1CacheValue(storage, "candidate", "new", baseUrl)).toThrow(error);
    expect(storage.getItem(rawKey)).toBe("keep");
    expect(storage.removeItem).toHaveBeenCalledTimes(name === "QuotaExceededError" ? 1 : 0);
  });

  it("never removes the raw slot currently being replaced", () => {
    const baseUrl = "/quota-protected-slot";
    const key = `meteofriul:weather-v1:v4:${sha256Hex(baseUrl).slice(0, 16)}:icon2i:municipality:0`;
    const storage = {
      setItem: vi.fn(() => { throw new DOMException("full", "QuotaExceededError"); }),
      getItem: vi.fn(candidate => candidate === key ? "previous-verified-bytes" : null),
      removeItem: vi.fn(),
    };
    expect(() => writeWeatherV1CacheValue(storage, key, "replacement", baseUrl)).toThrow("full");
    expect(storage.removeItem).not.toHaveBeenCalled();
  });
});
