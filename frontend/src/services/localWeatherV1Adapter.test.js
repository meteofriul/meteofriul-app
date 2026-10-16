import { describe, expect, it, vi } from "vitest";

import {
  LOCAL_WEATHER_V1_CATALOG,
  LOCAL_WEATHER_V1_CAMS_TIMEOUT_MS,
  LOCAL_WEATHER_V1_ISTAT_CODES,
  fetchLocalWeatherV1Bootstrap,
  fetchLocalWeatherV1CamsSupplement,
  fetchLocalWeatherV1Conditions,
  resolveLocalWeatherV1Istat,
} from "./localWeatherV1Adapter";
import { CAMS_AIR_FIELDS, decodeVerifiedCamsHourlyCache } from "./camsHourlyCache";

const RUN_AT = "2026-09-03T00:00:00Z";
const NOW = "2026-09-03T10:30:00Z";
const HOUR_MS = 60 * 60 * 1000;
const ISTAT = "093033";
const POLLEN_VARIABLES = [
  ["alder_pollen", "ontano"],
  ["birch_pollen", "betulla"],
  ["grass_pollen", "graminacee"],
  ["mugwort_pollen", "artemisia"],
  ["olive_pollen", "olivo"],
  ["ragweed_pollen", "ambrosia"],
];

function isoAt(hours) {
  return new Date(Date.parse(RUN_AT) + hours * HOUR_MS).toISOString().replace(".000Z", "Z");
}

function localDate(value) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    day: "2-digit",
    month: "2-digit",
    timeZone: "Europe/Rome",
    year: "numeric",
  }).formatToParts(new Date(value));
  const byType = Object.fromEntries(parts.map(({ type, value: part }) => [type, part]));
  return `${byType.year}-${byType.month}-${byType.day}`;
}

function condition() {
  return {
    native_code: 0,
    native_status: "valid",
    native_label_it: "Sereno",
    semantic_key: "clear",
    text_key: "conditionSun",
    icon_key: "Sun",
    scene_key: "clear",
  };
}

function municipality() {
  return {
    istat_code: ISTAT,
    name: "Pordenone",
    slug: "pordenone",
    province: "PN",
    representative_point: { lat: 45.9567, lon: 12.6605 },
    model_point: { lat: 45.95, lon: 12.65, distance_km: 1.1, grid_index: 4 },
  };
}

function iconDocument() {
  return {
    provider: "icon2i",
    model: { id: "icon-2i", product: "surface_pressure_levels" },
    source: { attribution: "ItaliaMeteo", license: "CC BY 4.0" },
    run_at: RUN_AT,
    generated_at: isoAt(1),
    catalog: LOCAL_WEATHER_V1_CATALOG,
    municipality: municipality(),
    hourly: Array.from({ length: 73 }, (_, hour) => ({
      valid_at: isoAt(hour),
      interval_start: hour ? isoAt(hour - 1) : null,
      interval_end: hour ? isoAt(hour) : null,
      temperature_c: 12 + hour / 10,
      apparent_temperature_c: 11 + hour / 10,
      relative_humidity_pct: 70,
      pressure_msl_hpa: 1013,
      wind_speed_m_s: 2,
      wind_from_degrees: 180,
      wind_gust_max_m_s: hour ? 3 : null,
      cloud_cover_pct: 10,
      precipitation_mm: hour ? 0.2 : null,
      liquid_rain_mm: hour ? 0.2 : null,
      snow_water_equivalent_mm: hour ? 0 : null,
      condition: condition(),
      quality_flags: [],
    })),
  };
}

function camsPollenDocument() {
  const pollen = POLLEN_VARIABLES.map(([id, ui_key]) => ({
    id,
    ui_key,
    category: "pollen",
    unit: "grains/m3",
    validation_status: "experimental_unvalidated_by_provider",
  }));
  const variables = pollen;
  const values = Object.fromEntries(variables.map(({ id }, index) => [id, index + 0.5]));
  const qualityFlags = Object.fromEntries(variables.map(({ id }) => [id, []]));
  return {
    provider: "cams_europe_pollen",
    model: { id: "cams-european-regional-ensemble" },
    source: { attribution: "CAMS", license: "CC BY 4.0" },
    run_at: RUN_AT,
    generated_at: isoAt(1),
    freshness: { fresh_until: isoAt(24), usable_until: isoAt(96) },
    catalog: LOCAL_WEATHER_V1_CATALOG,
    municipality: municipality(),
    variables,
    health_classification: null,
    projection: {
      id: "cams_pollen_hourly_v1",
      source_provider: "cams_europe",
      source_kind: "meteofriul.weather.cams.municipality",
      retained_variable_ids: POLLEN_VARIABLES.map(([id]) => id),
    },
    hourly: Array.from({ length: 97 }, (_, hour) => ({
      valid_at: isoAt(hour),
      values: { ...values },
      quality_flags: Object.fromEntries(
        Object.entries(qualityFlags).map(([id, flags]) => [id, [...flags]]),
      ),
    })),
  };
}

function camsAirDocument() {
  const variables = CAMS_AIR_FIELDS.map(id => ({
    id,
    ui_key: id,
    category: "air_quality",
    unit: "ug/m3",
    validation_status: "valid",
  }));
  return {
    provider: "cams_europe",
    model: { id: "cams-european-regional-ensemble" },
    source: { attribution: "CAMS", license: "CC BY 4.0" },
    run_at: RUN_AT,
    generated_at: isoAt(1),
    freshness: { fresh_until: isoAt(24), usable_until: isoAt(96) },
    catalog: LOCAL_WEATHER_V1_CATALOG,
    municipality: municipality(),
    variables,
    hourly: Array.from({ length: 97 }, (_, hour) => ({
      valid_at: isoAt(hour),
      values: Object.fromEntries(CAMS_AIR_FIELDS.map((id, index) => [id, hour + index / 10])),
      quality_flags: Object.fromEntries(CAMS_AIR_FIELDS.map(id => [id, []])),
    })),
  };
}

function pairedCamsFixtureClientFactory() {
  const fixture = fixtureClientFactory();
  const runId = RUN_AT.replaceAll("-", "").replaceAll(":", "");
  const familyDocument = {
    provider: "cams",
    revision: 7,
    published_at: "2026-09-03T02:00:00Z",
    latest: { source_run_id: runId },
    disabled_run_ids: [],
  };
  const pollenLatest = {
    document: familyDocument,
    path: `families/cams/runs/${runId}/release.json#pollen`,
    etag: '"cams-family-pollen"',
  };
  const airLatest = {
    document: familyDocument,
    path: `families/cams/runs/${runId}/release.json#air`,
    etag: '"cams-family-air"',
  };
  const result = (document, member) => ({
    document,
    path: `runs/${runId}/municipalities/${ISTAT}.json`,
    etag: `"cams-${member}-payload"`,
    freshness: { status: "fresh", freshUntil: isoAt(24), usableUntil: isoAt(96) },
  });
  const clients = {
    camsFamily: {
      fetchMembersLatest: vi.fn(async () => ({ camsPollen: pollenLatest, camsEurope: airLatest })),
    },
    camsPollen: {
      fetchManifest: vi.fn(async () => ({ document: {}, path: `runs/${runId}/manifest.json` })),
      fetchMunicipality: vi.fn(async () => result(camsPollenDocument(), "pollen")),
    },
    camsEurope: {
      fetchManifest: vi.fn(async () => ({ document: {}, path: `runs/${runId}/manifest.json` })),
      fetchMunicipality: vi.fn(async () => result(camsAirDocument(), "air")),
    },
  };
  return {
    ...fixture,
    ...clients,
    factory: vi.fn(() => ({ icon2i: fixture.icon2i, ...clients })),
  };
}

function providerClient(document, name, trace) {
  const runId = RUN_AT.replaceAll("-", "").replaceAll(":", "");
  const latest = {
    document: name === "cams_europe_pollen"
      ? {
        provider: name,
        revision: 7,
        published_at: "2026-09-03T02:00:00Z",
        latest: { source_run_id: runId },
        disabled_run_ids: ["20260902T120000Z"],
      }
      : { provider: name },
    path: name === "cams_europe_pollen"
      ? `families/cams/runs/${runId}/release.json#pollen`
      : "latest.json",
    etag: `"${name}-latest"`,
    fromCache: true,
    notModified: true,
    networkFallback: false,
  };
  const manifest = {
    document: { provider: name },
    path: `runs/${runId}/manifest.json`,
    etag: `"${name}-manifest"`,
    fromCache: false,
    notModified: false,
    cachePersisted: true,
  };
  const payload = {
    document,
    path: `runs/${runId}/municipalities/${ISTAT}.json`,
    etag: `"${name}-payload"`,
    freshness: {
      status: "fresh",
      remainingCoverageHours: name === "icon2i" ? 61.5 : 85.5,
      requiredFutureHours: name === "icon2i" ? 48 : 0,
    },
    fromCache: false,
    notModified: false,
    cachePersisted: true,
  };
  return {
    fetchLatest: vi.fn(async () => {
      trace.push(`${name}:latest`);
      return latest;
    }),
    fetchManifest: vi.fn(async (value) => {
      expect(value).toBe(latest);
      trace.push(`${name}:manifest`);
      return manifest;
    }),
    fetchMunicipality: vi.fn(async (value, istat) => {
      expect(value).toBe(manifest);
      expect(istat).toBe(ISTAT);
      trace.push(`${name}:payload`);
      return payload;
    }),
  };
}

function fixtureClientFactory() {
  const trace = [];
  let options;
  const icon2i = providerClient(iconDocument(), "icon2i", trace);
  const camsPollen = providerClient(camsPollenDocument(), "cams_europe_pollen", trace);
  const camsEurope = { fetchLatest: vi.fn(() => {
    throw new Error("il bundle UI non deve scaricare il payload CAMS completo");
  }) };
  const factory = vi.fn((received) => {
    options = received;
    return { icon2i, camsEurope, camsPollen };
  });
  return {
    factory,
    get options() { return options; },
    icon2i,
    camsEurope,
    camsPollen,
    trace,
  };
}

function storage() {
  return { getItem: vi.fn(), setItem: vi.fn(), removeItem: vi.fn() };
}

describe("local weather v1 adapter", () => {
  it("reads verified paired Pordenone CAMS without fetching regional ICON", async () => {
    const fixture = pairedCamsFixtureClientFactory();
    const supplement = await fetchLocalWeatherV1CamsSupplement({
      city: "Pordenone", municipality: { istatCode: ISTAT, name: "Pordenone" },
    }, { now: () => Date.parse(NOW), storage: storage(), clientFactory: fixture.factory });
    expect(supplement).toMatchObject({
      municipality_istat: ISTAT, catalog: LOCAL_WEATHER_V1_CATALOG,
      available: true, status: "fresh",
      pollen_data: { status: "experimental_model_snapshot", valid_at_utc: isoAt(10) },
      air_quality_data: { valid_at: isoAt(10), values: { "particulate_matter_2.5um": 10 } },
      source: { evidence: { family: { revision: 7 } } },
    });
    expect(Object.keys(supplement.pollen_data.values)).toHaveLength(6);
    expect(supplement.cams_hourly_cache).toBeTruthy();
    expect(fixture.icon2i.fetchLatest).not.toHaveBeenCalled();
    expect(fixture.camsFamily.fetchMembersLatest).toHaveBeenCalledTimes(1);
    expect(fixture.camsPollen.fetchMunicipality).toHaveBeenCalledWith(expect.anything(), ISTAT, expect.anything());
    expect(fixture.camsEurope.fetchMunicipality).toHaveBeenCalledWith(expect.anything(), ISTAT, expect.anything());
  });

  it.each(["0", "1"])("honours the reader continuity capability flag (%s)", async (flag) => {
    vi.stubEnv("VITE_CAMS_CONTINUITY_ENABLED", flag);
    try {
      const fixture = pairedCamsFixtureClientFactory();
      await fetchLocalWeatherV1CamsSupplement({ city: "Pordenone", municipality: { istatCode: ISTAT } },
        { now: () => Date.parse(NOW), storage: storage(), clientFactory: fixture.factory });
      expect(fixture.factory).toHaveBeenCalledWith(expect.objectContaining({ camsContinuity: flag === "1" }));
    } finally {
      vi.unstubAllEnvs();
    }
  });

  it("fails the separate CAMS channel closed for unsupported or mismatched municipalities", async () => {
    const fixture = pairedCamsFixtureClientFactory();
    await expect(fetchLocalWeatherV1CamsSupplement({ municipality: { istatCode: "058091" } }, {
      clientFactory: fixture.factory,
    })).rejects.toMatchObject({ code: "UNKNOWN_MUNICIPALITY" });
    expect(fixture.factory).not.toHaveBeenCalled();
    const document = camsPollenDocument();
    document.municipality.istat_code = "030129";
    fixture.camsPollen.fetchMunicipality.mockResolvedValue({ document, freshness: { status: "fresh" } });
    const supplement = await fetchLocalWeatherV1CamsSupplement("Pordenone", {
      now: () => Date.parse(NOW), storage: storage(), clientFactory: fixture.factory,
    });
    expect(supplement).toMatchObject({ available: false, status: "unavailable",
      diagnostic: { code: "PROVIDER_IDENTITY_MISMATCH" } });
    expect(supplement.air_quality_data).toBeNull();
    expect(fixture.icon2i.fetchLatest).not.toHaveBeenCalled();
  });

  it("emette 97 campioni CAMS nello schema binario v2 sotto 18 KB", async () => {
    const fixture = pairedCamsFixtureClientFactory();
    const result = await fetchLocalWeatherV1Bootstrap("Pordenone", {
      clientFactory: fixture.factory,
      storage: storage(),
      now: () => Date.parse(NOW),
    });

    const cache = result.current.cams_hourly_cache;
    expect(cache).toMatchObject({ version: 2, sample_count: 97, step_seconds: 3600 });
    expect(cache).not.toHaveProperty("samples");
    expect(JSON.stringify(cache).length).toBeLessThan(18_000);
    const decoded = decodeVerifiedCamsHourlyCache(cache, {
      municipalityIstat: ISTAT,
      catalogSha256: LOCAL_WEATHER_V1_CATALOG.sha256,
      runUtc: RUN_AT,
    });
    expect(decoded.samples).toHaveLength(97);
    expect(decoded.samples[10]).toEqual({
      valid_at_utc: isoAt(10),
      pollen_values: {
        ontano: 0.5, betulla: 1.5, graminacee: 2.5,
        artemisia: 3.5, olivo: 4.5, ambrosia: 5.5,
      },
      pollen_quality_flags: Object.fromEntries(POLLEN_VARIABLES.map(([id]) => [id, []])),
      air_values: {
        "particulate_matter_2.5um": 10,
        "particulate_matter_10um": 10.1,
        ozone: 10.2,
        nitrogen_dioxide: 10.3,
      },
    });
  });

  it.each([48, 37, 36, 24, 12])("delivers %i real future ICON hours without requiring CAMS", async (count) => {
    const fixture = fixtureClientFactory();
    const now = Date.parse(isoAt(73 - count));
    const bundle = await fetchLocalWeatherV1Bootstrap("Pordenone", {
      clientFactory: () => ({ icon2i: fixture.icon2i }), storage: storage(), now: () => now,
    });
    const expected = iconDocument().hourly.filter(row => Date.parse(row.valid_at) >= now).slice(0, 48);
    expect(bundle.current.hourly_forecast.map(row => row.time)).toEqual(expected.map(row => row.valid_at));
    expect(bundle.current.hourly_forecast.map(row => row.temperature)).toEqual(expected.map(row => row.temperature_c));
    expect(bundle.current.hourly_next_12h).toHaveLength(12);
    expect(bundle.current.model_support.hourly).toBe(true);
    expect(bundle.current.model_support.cams).toBe(false);
    expect(bundle.forecast.forecast.length).toBeGreaterThan(0);
  });

  it("does not count the current-condition sample as a future hour", async () => {
    const fixture = fixtureClientFactory();
    const now = Date.parse(isoAt(60)) + 30 * 60_000;
    const bundle = await fetchLocalWeatherV1Bootstrap("Pordenone", {
      clientFactory: fixture.factory, storage: storage(), now: () => now,
    });
    expect(bundle.current.data_quality.valid_at_utc).toBe(isoAt(60));
    expect(bundle.current.temperature).toBe(iconDocument().hourly[60].temperature_c);
    expect(bundle.current.hourly_forecast[0].time).toBe(isoAt(61));
    expect(bundle.current.hourly_forecast).toHaveLength(12);
    expect(bundle.current.hourly_forecast.every(row => Date.parse(row.time) >= now)).toBe(true);
  });

  it("rejects 11 future samples instead of padding with the current or last value", async () => {
    const fixture = fixtureClientFactory();
    await expect(fetchLocalWeatherV1Bootstrap("Pordenone", {
      clientFactory: fixture.factory, storage: storage(), now: () => Date.parse(isoAt(61)) + 1,
    })).rejects.toMatchObject({ code: "HOURLY_COVERAGE_INCOMPLETE" });
  });

  it.each(["missing", "invalid", "not-yet-valid"])("uses only the verified previous descriptor when current is %s", async (failure) => {
    const fixture = fixtureClientFactory();
    const previous = iconDocument();
    const now = Date.parse(isoAt(49));
    const pointer = { document: { previous: { source_run_id: "20260903T000000Z" } } };
    const original = fixture.icon2i.fetchMunicipality;
    const originalResult = await original(await fixture.icon2i.fetchManifest(await fixture.icon2i.fetchLatest()), ISTAT);
    fixture.icon2i.fetchLatest.mockResolvedValue(pointer);
    fixture.icon2i.fetchManifest.mockImplementation(async (_pointer, _signal, options) => {
      if (!options?.previous) throw Object.assign(new Error(failure), {
        code: failure === "invalid" ? "INTEGRITY_MISMATCH" : failure === "not-yet-valid" ? "NOT_YET_VALID" : "HTTP_ERROR",
      });
      return { document: {}, previous: true };
    });
    fixture.icon2i.fetchMunicipality.mockResolvedValue({ ...originalResult, document: previous });
    const bundle = await fetchLocalWeatherV1Bootstrap("Pordenone", {
      clientFactory: fixture.factory, storage: storage(), now: () => now,
    });
    expect(bundle.current.hourly_forecast).toHaveLength(24);
    expect(bundle.current.data_quality.run_utc).toBe(RUN_AT);
    expect(fixture.icon2i.fetchManifest).toHaveBeenCalledWith(pointer, undefined, { previous: true });
  });

  it("never uses an unchecked previous candidate if verification fails", async () => {
    const fixture = fixtureClientFactory();
    const failure = Object.assign(new Error("invalid current"), { code: "INTEGRITY_MISMATCH" });
    fixture.icon2i.fetchLatest.mockResolvedValue({ document: { previous: { source_run_id: "previous" } } });
    fixture.icon2i.fetchManifest.mockRejectedValue(failure);
    await expect(fetchLocalWeatherV1Bootstrap("Pordenone", {
      clientFactory: fixture.factory, storage: storage(), now: () => Date.parse(NOW),
    })).rejects.toBe(failure);
    expect(fixture.icon2i.fetchMunicipality).not.toHaveBeenCalled();
  });

  it("reports verified ICON revocations before a later object request fails", async () => {
    const fixture = fixtureClientFactory();
    const onIconLatest = vi.fn();
    const decision = { revision: 2, latest: { source_run_id: "20260903T120000Z" }, disabled_run_ids: ["20260903T000000Z"] };
    fixture.icon2i.fetchLatest.mockResolvedValue({ document: decision });
    fixture.icon2i.fetchManifest.mockImplementation(async () => {
      expect(onIconLatest).toHaveBeenCalledWith(decision);
      throw Object.assign(new Error("offline"), { code: "TRANSPORT_FAILURE" });
    });
    await expect(fetchLocalWeatherV1Bootstrap("Pordenone", {
      clientFactory: fixture.factory, storage: storage(), now: () => Date.parse(NOW), onIconLatest,
    })).rejects.toMatchObject({ code: "TRANSPORT_FAILURE" });
  });

  it("does not try another run after a cancelled ICON request", async () => {
    const fixture = fixtureClientFactory();
    fixture.icon2i.fetchLatest.mockResolvedValue({ document: { previous: { source_run_id: "previous" } } });
    fixture.icon2i.fetchManifest.mockRejectedValue(Object.assign(new Error("cancelled"), {
      code: "TRANSPORT_FAILURE", aborted: true,
    }));
    await expect(fetchLocalWeatherV1Bootstrap("Pordenone", {
      clientFactory: fixture.factory, storage: storage(), now: () => Date.parse(NOW),
    })).rejects.toMatchObject({ aborted: true });
    expect(fixture.icon2i.fetchManifest).toHaveBeenCalledTimes(1);
  });

  it("does not suppress a failed revocation-cache quarantine", async () => {
    const fixture = fixtureClientFactory();
    fixture.icon2i.fetchLatest.mockResolvedValue({ document: {
      revision: 2, latest: { source_run_id: "20260903T120000Z" },
      previous: { source_run_id: "20260902T120000Z" }, disabled_run_ids: ["20260903T000000Z"],
    } });
    const failure = Object.assign(new Error("quarantine failed"), { code: "CACHE_INVALIDATION_FAILED" });
    await expect(fetchLocalWeatherV1Bootstrap("Pordenone", {
      clientFactory: fixture.factory, storage: storage(), now: () => Date.parse(NOW),
      onIconLatest: () => { throw failure; },
    })).rejects.toBe(failure);
    expect(fixture.icon2i.fetchManifest).not.toHaveBeenCalled();
  });

  it("recovers morning extrema from the previous run without replacing current hours", async () => {
    const fixture = fixtureClientFactory();
    const old = iconDocument();
    old.hourly.forEach(row => { row.temperature_c = 22; });
    old.hourly[5].temperature_c = 18.94;
    const latestDocument = iconDocument();
    latestDocument.hourly = latestDocument.hourly.slice(12);
    latestDocument.hourly.forEach(row => { row.temperature_c = 26; });
    latestDocument.hourly[1].temperature_c = 32.29;
    const pointer = { document: { previous: { source_run_id: "previous" } } };
    fixture.icon2i.fetchLatest.mockResolvedValue(pointer);
    fixture.icon2i.fetchManifest.mockImplementation(async (_value, _signal, options) => ({ previous: options?.previous }));
    fixture.icon2i.fetchMunicipality.mockImplementation(async manifest => ({ document: manifest.previous ? old : latestDocument, freshness: { status: "fresh" } }));
    const result = await fetchLocalWeatherV1Bootstrap("Pordenone", {
      clientFactory: fixture.factory, storage: storage(), now: () => Date.parse(isoAt(19)),
    });
    expect(result.forecast.forecast[0].sampled_min_temp).toBe(18.94);
    expect(result.forecast.forecast[0].sampled_max_temp).toBe(32.29);
    expect(result.current.hourly_forecast[0].temperature).toBe(26);
    expect(fixture.icon2i.fetchManifest).toHaveBeenCalledWith(pointer, undefined, { previous: true });
  });
  it("deriva tutti e soli i 215 ISTAT dal dataset locale", () => {
    expect(LOCAL_WEATHER_V1_ISTAT_CODES).toHaveLength(215);
    expect(new Set(LOCAL_WEATHER_V1_ISTAT_CODES).size).toBe(215);
    expect(resolveLocalWeatherV1Istat("Pordenone")).toBe(ISTAT);
    expect(resolveLocalWeatherV1Istat("Pordenon")).toBe(ISTAT);
    expect(resolveLocalWeatherV1Istat({
      city: "localita visualizzata",
      municipality: { istatCode: ISTAT, name: "Pordenone" },
    })).toBe(ISTAT);
    expect(() => resolveLocalWeatherV1Istat("Comune inesistente")).toThrowError(
      expect.objectContaining({ code: "UNKNOWN_MUNICIPALITY" }),
    );
  });

  it("esegue due catene provider separate e costruisce current, 48h, daily e pollini", async () => {
    const fixture = fixtureClientFactory();
    const fetchImpl = vi.fn();
    const injectedStorage = storage();
    const result = await fetchLocalWeatherV1Bootstrap(
      {
        city: "Pordenone",
        lat: 45.96,
        lon: 12.66,
        positionAccuracyM: 12,
        positionCapturedAt: NOW,
        source: "browser_geolocation",
        municipality: { istatCode: ISTAT, name: "Pordenone" },
      },
      {
        baseUrl: "/__local-weather-pilot",
        clientFactory: fixture.factory,
        fetchImpl,
        storage: injectedStorage,
        now: () => Date.parse(NOW),
        force: true,
      },
    );

    expect(fixture.options).toMatchObject({
      baseUrl: "/__local-weather-pilot",
      fetchImpl,
      storage: injectedStorage,
      catalog: LOCAL_WEATHER_V1_CATALOG,
      istatCodes: LOCAL_WEATHER_V1_ISTAT_CODES,
      force: true,
    });
    for (const provider of ["icon2i", "cams_europe_pollen"]) {
      expect(fixture.trace.indexOf(`${provider}:latest`)).toBeLessThan(
        fixture.trace.indexOf(`${provider}:manifest`),
      );
      expect(fixture.trace.indexOf(`${provider}:manifest`)).toBeLessThan(
        fixture.trace.indexOf(`${provider}:payload`),
      );
    }
    const camsSignal = fixture.camsPollen.fetchLatest.mock.calls[0][0];
    expect(camsSignal).toBeInstanceOf(AbortSignal);
    expect(fixture.camsPollen.fetchManifest.mock.calls[0][1]).toBe(camsSignal);
    expect(fixture.camsPollen.fetchMunicipality.mock.calls[0][2]).toBe(camsSignal);
    expect(fixture.camsEurope.fetchLatest).not.toHaveBeenCalled();
    expect(fixture.icon2i.fetchLatest.mock.calls[0][0]).toBeUndefined();
    expect(result.current).toMatchObject({
      city: "Pordenone",
      primary_source: "icon2i_local_pilot",
      weathercode: null,
      is_day: 1,
    });
    expect(result.current.data_quality).toMatchObject({
      native_weather_code: 0,
      catalog_version: LOCAL_WEATHER_V1_CATALOG.version,
      catalog_sha256: LOCAL_WEATHER_V1_CATALOG.sha256,
      location_scope: "device_location",
    });
    expect(result.current.sunrise).toMatch(/^\d{2}:\d{2}$/);
    expect(result.current.sunset).toMatch(/^\d{2}:\d{2}$/);
    expect(result.current.hourly_forecast).toHaveLength(48);
    const intervalSlot = result.current.hourly_forecast.find((slot) => slot.interval_start);
    expect(intervalSlot.interval_end).toBe(intervalSlot.time);
    expect(Date.parse(intervalSlot.interval_end) - Date.parse(intervalSlot.interval_start)).toBe(HOUR_MS);
    expect(new Set(result.current.hourly_forecast.map(({ is_day }) => is_day))).toEqual(
      new Set([0, 1]),
    );
    expect(result.forecast.forecast.length).toBeGreaterThan(1);
    expect(result.forecast.daily.time).toHaveLength(result.forecast.forecast.length);
    expect(result.forecast.forecast.reduce((total, day) => total + day.source_hours, 0)).toBe(73);
    expect(result.forecast.daily.time.at(-1)).toBe(localDate(isoAt(72)));
    // Morning minimum is retained, although the visible hourly ribbon starts at noon.
    expect(result.forecast.forecast[0]).toMatchObject({
      sampled_min_temp: 12,
      sampled_max_temp: 14.1,
      source_hours: 22,
    });
    expect(result.current.pollen_data).toMatchObject({
      level: null,
      main: null,
      health_classification: null,
    });
    expect(result.current.pollen_data.all_variables).toHaveLength(6);
    expect(Object.keys(result.current.pollen_data.values).sort()).toEqual(
      ["ambrosia", "artemisia", "betulla", "graminacee", "olivo", "ontano"],
    );
    expect(JSON.stringify(result)).not.toMatch(/"primary_source":"open_meteo"|fallback[^,}]*open.?meteo/i);
    expect(result).not.toHaveProperty("official_alerts");
    expect(result).not.toHaveProperty("osmer_audit");
    expect(result.current.model_support.open_meteo).toBe(false);
    expect(result.forecast.model_support.open_meteo).toBe(false);
    expect(result.current.source.icon.evidence).toMatchObject({
      from_cache: true,
      not_modified: true,
      network_fallback: false,
      cache_persisted: true,
      stages: {
        latest: { from_cache: true, not_modified: true },
        manifest: { from_cache: false, cache_persisted: true },
        municipality: { from_cache: false, cache_persisted: true },
      },
    });
    expect(result.current.source.cams).toMatchObject({
      provider: "cams_europe_pollen",
      source_provider: "cams_europe",
      evidence: {
        family: {
          revision: 7,
          published_at: "2026-09-03T02:00:00Z",
          active_run_id: "20260903T000000Z",
          disabled_run_ids: ["20260902T120000Z"],
        },
        stages: {
          latest: {
            path: "families/cams/runs/20260903T000000Z/release.json#pollen",
          },
        },
      },
    });
  });

  it("consegna ICON mentre CAMS e ancora bloccato e pubblica poi l'arricchimento", async () => {
    const fixture = fixtureClientFactory();
    const originalCamsLatest = fixture.camsPollen.fetchLatest.getMockImplementation();
    let releaseCams;
    fixture.camsPollen.fetchLatest.mockImplementationOnce((signal) => new Promise((resolve, reject) => {
      releaseCams = () => Promise.resolve(originalCamsLatest(signal)).then(resolve, reject);
    }));
    const onCamsUpdate = vi.fn();

    const initial = await fetchLocalWeatherV1Bootstrap("Pordenone", {
      clientFactory: fixture.factory,
      deferCams: true,
      fetchImpl: vi.fn(),
      onCamsUpdate,
      storage: storage(),
      now: () => Date.parse(NOW),
    });

    expect(fixture.icon2i.fetchMunicipality).toHaveBeenCalledOnce();
    expect(fixture.camsPollen.fetchLatest).toHaveBeenCalledOnce();
    expect(fixture.camsPollen.fetchManifest).not.toHaveBeenCalled();
    expect(onCamsUpdate).not.toHaveBeenCalled();
    expect(initial.current).toMatchObject({
      temperature: 13,
      pollen: "Pollini CAMS in arrivo",
      source: {
        status: "pending",
        icon: { status: "available" },
        cams: { status: "pending", diagnostic: null },
      },
      pollen_data: { status: "pending", diagnostic: null },
      data_quality: { cams_status: "pending", cams_diagnostic: null },
    });
    expect(initial.current.data_quality.flags).toContain("cams_pending");
    expect(initial.current.data_quality.flags).not.toContain("cams_unavailable");

    releaseCams();
    await vi.waitFor(() => expect(onCamsUpdate).toHaveBeenCalledOnce());
    const enriched = onCamsUpdate.mock.calls[0][0];
    expect(enriched.current.temperature).toBe(initial.current.temperature);
    expect(enriched.current).toMatchObject({
      source: { status: "available", cams: { status: "available" } },
      pollen_data: { status: "experimental_model_snapshot" },
    });
    expect(enriched.current.pollen_data.all_variables).toHaveLength(6);
  });

  it("in modalita predefinita continua ad attendere CAMS", async () => {
    const fixture = fixtureClientFactory();
    const originalCamsLatest = fixture.camsPollen.fetchLatest.getMockImplementation();
    let releaseCams;
    fixture.camsPollen.fetchLatest.mockImplementationOnce((signal) => new Promise((resolve, reject) => {
      releaseCams = () => Promise.resolve(originalCamsLatest(signal)).then(resolve, reject);
    }));
    let settled = false;
    const request = fetchLocalWeatherV1Bootstrap("Pordenone", {
      clientFactory: fixture.factory,
      fetchImpl: vi.fn(),
      storage: storage(),
      now: () => Date.parse(NOW),
    }).then((result) => {
      settled = true;
      return result;
    });

    await vi.waitFor(() => expect(fixture.icon2i.fetchMunicipality).toHaveBeenCalledOnce());
    expect(settled).toBe(false);
    releaseCams();
    await expect(request).resolves.toMatchObject({
      current: { source: { cams: { status: "available" } } },
    });
  });

  it("consegna come supplemento unavailable un errore CAMS senza rimuovere ICON", async () => {
    const fixture = fixtureClientFactory();
    fixture.camsPollen.fetchManifest.mockRejectedValueOnce(
      Object.assign(new Error("CAMS unavailable"), { code: "HTTP_ERROR" }),
    );
    const onCamsUpdate = vi.fn();

    const initial = await fetchLocalWeatherV1Bootstrap("Pordenone", {
      clientFactory: fixture.factory,
      deferCams: true,
      fetchImpl: vi.fn(),
      onCamsUpdate,
      storage: storage(),
      now: () => Date.parse(NOW),
    });
    expect(initial.current.data_quality.cams_status).toBe("pending");

    await vi.waitFor(() => expect(onCamsUpdate).toHaveBeenCalledOnce());
    const unavailable = onCamsUpdate.mock.calls[0][0];
    expect(unavailable.current.temperature).toBe(initial.current.temperature);
    expect(unavailable.current).toMatchObject({
      source: {
        icon: { status: "available" },
        cams: {
          status: "unavailable",
          evidence: {
            family: {
              revision: 7,
              active_run_id: "20260903T000000Z",
              disabled_run_ids: ["20260902T120000Z"],
            },
          },
          diagnostic: { stage: "manifest", code: "HTTP_ERROR" },
        },
      },
      pollen_data: { status: "unavailable" },
      data_quality: { cams_status: "unavailable" },
    });
  });

  it("consegna come supplemento unavailable anche il timeout CAMS", async () => {
    vi.useFakeTimers();
    try {
      const fixture = fixtureClientFactory();
      fixture.camsPollen.fetchLatest.mockImplementationOnce((signal) => new Promise(
        (_resolve, reject) => {
          signal.addEventListener("abort", () => reject(
            Object.assign(new Error("CAMS aborted"), { name: "AbortError" }),
          ), { once: true });
        },
      ));
      const onCamsUpdate = vi.fn();
      const initial = await fetchLocalWeatherV1Bootstrap("Pordenone", {
        camsTimeoutMs: 25,
        clientFactory: fixture.factory,
        deferCams: true,
        fetchImpl: vi.fn(),
        onCamsUpdate,
        storage: storage(),
        now: () => Date.parse(NOW),
      });

      expect(initial.current.data_quality.cams_status).toBe("pending");
      await vi.advanceTimersByTimeAsync(25);
      await vi.runOnlyPendingTimersAsync();

      expect(onCamsUpdate).toHaveBeenCalledOnce();
      expect(onCamsUpdate.mock.calls[0][0].current).toMatchObject({
        temperature: initial.current.temperature,
        source: {
          icon: { status: "available" },
          cams: {
            status: "unavailable",
            diagnostic: { stage: "timeout", code: "CAMS_TIMEOUT" },
          },
        },
        data_quality: { cams_status: "unavailable" },
      });
      expect(vi.getTimerCount()).toBe(0);
    } finally {
      vi.useRealTimers();
    }
  });

  it("conserva la revoca osservata se il timeout scatta mentre la release resta pendente", async () => {
    vi.useFakeTimers();
    try {
      const fixture = fixtureClientFactory();
      const observed = {
        revision: 8,
        published_at: "2026-09-03T03:00:00Z",
        latest: { source_run_id: "20260902T180000Z" },
        disabled_run_ids: ["20260903T000000Z"],
      };
      fixture.camsPollen.fetchLatest.mockImplementationOnce((_signal, onFamilyLatest) => {
        onFamilyLatest(observed);
        // Deliberately ignore AbortSignal: the adapter timeout must still settle.
        return new Promise(() => {});
      });

      const request = fetchLocalWeatherV1Bootstrap("Pordenone", {
        camsTimeoutMs: 25,
        clientFactory: fixture.factory,
        fetchImpl: vi.fn(),
        storage: storage(),
        now: () => Date.parse(NOW),
      });
      expect(fixture.camsPollen.fetchLatest).toHaveBeenCalledOnce();
      await vi.advanceTimersByTimeAsync(25);

      await expect(request).resolves.toMatchObject({
        current: {
          source: {
            cams: {
              status: "unavailable",
              evidence: {
                family: {
                  revision: 8,
                  active_run_id: "20260902T180000Z",
                  disabled_run_ids: ["20260903T000000Z"],
                },
                stages: {},
              },
              diagnostic: { stage: "timeout", code: "CAMS_TIMEOUT" },
            },
          },
          data_quality: { cams_status: "unavailable" },
        },
      });
      expect(fixture.camsPollen.fetchManifest).not.toHaveBeenCalled();
      expect(vi.getTimerCount()).toBe(0);
    } finally {
      vi.useRealTimers();
    }
  });

  it("propaga l'errore del gate durevole della decisione CAMS", async () => {
    const fixture = fixtureClientFactory();
    const observed = {
      revision: 8,
      published_at: "2026-09-03T03:00:00Z",
      latest: { source_run_id: "20260902T180000Z" },
      disabled_run_ids: ["20260903T000000Z"],
    };
    const safetyFailure = Object.assign(new Error("journal CAMS non persistito"), {
      code: "CAMS_REVOCATION_PERSIST_FAILED",
    });
    fixture.camsPollen.fetchLatest.mockImplementationOnce((_signal, onFamilyLatest) => {
      onFamilyLatest(observed);
      return new Promise(() => {});
    });

    await expect(fetchLocalWeatherV1Bootstrap("Pordenone", {
      clientFactory: fixture.factory,
      fetchImpl: vi.fn(),
      storage: storage(),
      now: () => Date.parse(NOW),
      onCamsFamilyLatest: () => { throw safetyFailure; },
    })).rejects.toBe(safetyFailure);
    expect(fixture.camsPollen.fetchManifest).not.toHaveBeenCalled();
  });

  it("segnala lo stesso errore senza bloccare il primo rendering ICON differito", async () => {
    const fixture = fixtureClientFactory();
    const observed = {
      revision: 8,
      published_at: "2026-09-03T03:00:00Z",
      latest: { source_run_id: "20260902T180000Z" },
      disabled_run_ids: ["20260903T000000Z"],
    };
    const safetyFailure = Object.assign(new Error("journal CAMS non persistito"), {
      code: "CAMS_REVOCATION_PERSIST_FAILED",
    });
    const onCamsFailure = vi.fn();
    fixture.camsPollen.fetchLatest.mockImplementationOnce((_signal, onFamilyLatest) => {
      onFamilyLatest(observed);
      return new Promise(() => {});
    });

    const initial = await fetchLocalWeatherV1Bootstrap("Pordenone", {
      clientFactory: fixture.factory,
      fetchImpl: vi.fn(),
      storage: storage(),
      now: () => Date.parse(NOW),
      deferCams: true,
      onCamsFamilyLatest: () => { throw safetyFailure; },
      onCamsFailure,
    });

    expect(initial.current.source.icon.status).toBe("available");
    expect(initial.current.source.cams.status).toBe("pending");
    await vi.waitFor(() => expect(onCamsFailure).toHaveBeenCalledWith(safetyFailure));
  });

  it("ignora le coordinate statiche manuali e usa il punto comunale autorevole", async () => {
    const fixture = fixtureClientFactory();
    const result = await fetchLocalWeatherV1Bootstrap({
      city: "Pordenone",
      lat: 45.96,
      lon: 12.66,
      source: "manual",
      municipality: { istatCode: ISTAT, name: "Pordenone" },
    }, {
      clientFactory: fixture.factory,
      fetchImpl: vi.fn(),
      storage: storage(),
      now: () => Date.parse(NOW),
    });

    expect(result.current.data_quality.location_scope).toBe("authoritative_municipality_point");
  });

  it("espone alle condizioni locali lo stesso current senza mescolare il forecast", async () => {
    const fixture = fixtureClientFactory();
    const result = await fetchLocalWeatherV1Conditions("Pordenone", {
      clientFactory: fixture.factory,
      fetchImpl: vi.fn(),
      storage: storage(),
      now: () => Date.parse(NOW),
    });
    expect(result.city).toBe("Pordenone");
    expect(result.current.hourly_forecast).toHaveLength(48);
    expect(result).not.toHaveProperty("forecast");
  });

  it("mantiene ICON e marca CAMS non disponibile quando la catena CAMS fallisce", async () => {
    const fixture = fixtureClientFactory();
    const camsError = Object.assign(new Error("CAMS unavailable"), { code: "HTTP_ERROR" });
    fixture.camsPollen.fetchManifest.mockRejectedValueOnce(camsError);
    const result = await fetchLocalWeatherV1Bootstrap("Pordenone", {
      clientFactory: fixture.factory,
      fetchImpl: vi.fn(),
      storage: storage(),
      now: () => Date.parse(NOW),
    });

    expect(result.current).toMatchObject({
      temperature: 13,
      primary_source: "icon2i_local_pilot",
      pollen: "Pollini CAMS non disponibili",
      model_support: { icon2i: true, cams: false, open_meteo: false },
      pollen_data: {
        status: "unavailable",
        values: {},
        all_variables: [],
        diagnostic: {
          provider: "cams_europe_pollen",
          status: "unavailable",
          stage: "manifest",
          code: "HTTP_ERROR",
        },
      },
      source: {
        status: "degraded",
        icon: { status: "available" },
        cams: {
          status: "unavailable",
          diagnostic: { stage: "manifest", code: "HTTP_ERROR" },
        },
      },
      data_quality: {
        cams_status: "unavailable",
        cams_run_utc: null,
        cams_valid_at_utc: null,
      },
    });
    expect(result.current.data_quality.flags).toContain("cams_unavailable");
    expect(result.current.data_quality.capability_gaps).toContain("cams_pollen");
    expect(result.forecast.model_support.cams).toBe(false);
    expect(fixture.icon2i.fetchMunicipality).toHaveBeenCalledOnce();
    expect(fixture.camsPollen.fetchMunicipality).not.toHaveBeenCalled();
    expect(fixture.camsEurope.fetchLatest).not.toHaveBeenCalled();
    expect(Object.keys(fixture.factory.mock.results[0].value).sort()).toEqual([
      "camsEurope",
      "camsPollen",
      "icon2i",
    ]);
  });

  it("propaga la revoca family anche se il target del nuovo latest non e valido", async () => {
    const fixture = fixtureClientFactory();
    const failure = Object.assign(new Error("release CAMS non valida"), {
      code: "INTEGRITY_MISMATCH",
      camsFamilyLatest: {
        revision: 8,
        published_at: "2026-09-03T03:00:00Z",
        latest: { source_run_id: "20260902T180000Z" },
        disabled_run_ids: ["20260903T000000Z"],
      },
    });
    fixture.camsPollen.fetchLatest.mockRejectedValueOnce(failure);

    const result = await fetchLocalWeatherV1Bootstrap("Pordenone", {
      clientFactory: fixture.factory,
      fetchImpl: vi.fn(),
      storage: storage(),
      now: () => Date.parse(NOW),
    });

    expect(result.current.source.cams).toMatchObject({
      status: "unavailable",
      evidence: {
        family: {
          revision: 8,
          active_run_id: "20260902T180000Z",
          disabled_run_ids: ["20260903T000000Z"],
        },
        stages: {},
      },
      diagnostic: { stage: "latest", code: "INTEGRITY_MISMATCH" },
    });
  });

  it("conserva la decisione family se l'adattamento del payload target fallisce", async () => {
    const fixture = fixtureClientFactory();
    const originalFetchMunicipality = fixture.camsPollen.fetchMunicipality.getMockImplementation();
    fixture.camsPollen.fetchMunicipality.mockImplementationOnce(async (...args) => {
      const result = await originalFetchMunicipality(...args);
      return {
        ...result,
        document: { ...result.document, hourly: [] },
      };
    });

    const result = await fetchLocalWeatherV1Bootstrap("Pordenone", {
      clientFactory: fixture.factory,
      fetchImpl: vi.fn(),
      storage: storage(),
      now: () => Date.parse(NOW),
    });

    expect(result.current.source.cams).toMatchObject({
      status: "unavailable",
      evidence: {
        family: {
          revision: 7,
          published_at: "2026-09-03T02:00:00Z",
          active_run_id: "20260903T000000Z",
          disabled_run_ids: ["20260902T120000Z"],
        },
        stages: {
          latest: {
            path: "families/cams/runs/20260903T000000Z/release.json#pollen",
          },
        },
      },
      diagnostic: { stage: "adapt", code: "INVALID_TIMELINE" },
    });
    expect(result.current.data_quality).toMatchObject({
      cams_status: "unavailable",
      cams_run_utc: null,
    });
  });

  it("fallisce chiuso quando manca ICON anche se CAMS e disponibile", async () => {
    const fixture = fixtureClientFactory();
    fixture.icon2i.fetchLatest.mockRejectedValueOnce(new Error("ICON unavailable"));
    await expect(fetchLocalWeatherV1Bootstrap("Pordenone", {
      clientFactory: fixture.factory,
      fetchImpl: vi.fn(),
      storage: storage(),
      now: () => Date.parse(NOW),
    })).rejects.toThrow("ICON unavailable");
    expect(fixture.camsPollen.fetchMunicipality).toHaveBeenCalledOnce();
  });

  it("limita CAMS nel tempo, abortisce solo CAMS e cancella il timer", async () => {
    vi.useFakeTimers();
    try {
      const fixture = fixtureClientFactory();
      let observedSignal;
      fixture.camsPollen.fetchLatest.mockImplementationOnce((signal) => {
        observedSignal = signal;
        return new Promise((_resolve, reject) => {
          signal.addEventListener("abort", () => {
            const error = new Error("CAMS aborted");
            error.name = "AbortError";
            reject(error);
          }, { once: true });
        });
      });

      const pending = fetchLocalWeatherV1Bootstrap("Pordenone", {
        clientFactory: fixture.factory,
        fetchImpl: vi.fn(),
        storage: storage(),
        now: () => Date.parse(NOW),
        camsTimeoutMs: 25,
      });
      await vi.advanceTimersByTimeAsync(25);
      const result = await pending;

      expect(LOCAL_WEATHER_V1_CAMS_TIMEOUT_MS).toBe(20_000);
      expect(observedSignal.aborted).toBe(true);
      expect(fixture.icon2i.fetchLatest.mock.calls[0][0]).toBeUndefined();
      expect(result.current.temperature).toBe(13);
      expect(result.current.source.cams).toMatchObject({
        status: "unavailable",
        diagnostic: { stage: "timeout", code: "CAMS_TIMEOUT" },
      });
      expect(result.current.model_support).toMatchObject({
        icon2i: true,
        cams: false,
        open_meteo: false,
      });
      expect(vi.getTimerCount()).toBe(0);
    } finally {
      vi.useRealTimers();
    }
  });

  it("cancella il timeout CAMS anche quando la catena termina subito", async () => {
    vi.useFakeTimers();
    try {
      const fixture = fixtureClientFactory();
      await fetchLocalWeatherV1Bootstrap("Pordenone", {
        clientFactory: fixture.factory,
        fetchImpl: vi.fn(),
        storage: storage(),
        now: () => Date.parse(NOW),
        camsTimeoutMs: 25,
      });
      expect(vi.getTimerCount()).toBe(0);
    } finally {
      vi.useRealTimers();
    }
  });

  it("consegna ICON subito e completa CAMS dopo preflight e letture lente entro il budget unico", async () => {
    vi.useFakeTimers();
    try {
      const fixture = fixtureClientFactory();
      const latest = fixture.camsPollen.fetchLatest.getMockImplementation();
      const manifest = fixture.camsPollen.fetchManifest.getMockImplementation();
      fixture.camsPollen.fetchLatest.mockImplementation(async (...args) => {
        await new Promise(resolve => setTimeout(resolve, 2100 + 6000));
        return latest(...args);
      });
      fixture.camsPollen.fetchManifest.mockImplementation(async (...args) => {
        await new Promise(resolve => setTimeout(resolve, 2000));
        return manifest(...args);
      });
      const updates = vi.fn();
      const initial = await fetchLocalWeatherV1Bootstrap("Pordenone", {
        clientFactory: fixture.factory, now: () => Date.parse(NOW),
        deferCams: true, onCamsUpdate: updates,
      });
      expect(initial.current.temperature).toBe(13);
      expect(initial.current.source.cams.status).toBe("pending");
      await vi.advanceTimersByTimeAsync(4000);
      expect(updates).not.toHaveBeenCalled();
      await vi.advanceTimersByTimeAsync(6101);
      expect(updates).toHaveBeenCalledTimes(1);
      expect(updates.mock.lastCall[0].current.source.cams.status).toBe("available");
      expect(fixture.icon2i.fetchLatest).toHaveBeenCalledTimes(1);
      expect(vi.getTimerCount()).toBe(0);
    } finally { vi.useRealTimers(); }
  });
});
