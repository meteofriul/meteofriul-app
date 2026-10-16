import { readCachedIconLatest, sha256Hex } from "./weatherV1Client";
import {
  LOCAL_WEATHER_V1_CATALOG,
  LOCAL_WEATHER_V1_ISTAT_CODES,
  resolveLocalWeatherV1Istat,
  resolveLocalWeatherV1PresentationPoint,
} from "./localWeatherV1Adapter";
import { getPilotWeatherPrefetchReader } from "./pilotWeatherPrefetch";
import { getHomeSolarState } from "../features/home/homeDayPhase";
import { ICON_FORECAST_WINDOW_POLICY, selectIconFutureRows } from "./iconForecastWindow";
import {
  CAMS_POLLEN_FIELDS,
  decodeVerifiedCamsHourlyCache,
} from "./camsHourlyCache";

const HOUR_MS = 60 * 60 * 1000;
const CURRENT_SAMPLE_MAX_LAG_MS = ICON_FORECAST_WINDOW_POLICY.currentSampleMaxLagMs;
const MAX_RETAINED_BUNDLES = 8;
const PERSISTED_BUNDLE_VERSION = 4;
const PERSISTED_CAMS_DELTA_VERSION = 1;
const PERSISTED_CAMS_DELTA_KIND = "cams-delta";
const PERSISTED_CAMS_FAMILY_DECISION_VERSION = 1;
const PERSISTED_CAMS_FAMILY_DECISION_KIND =
  "meteofriul.weather.cams_family_decision";
const CAMS_QUALITY_FIELDS = Object.freeze([
  "cams_status",
  "cams_run_utc",
  "cams_valid_at_utc",
  "cams_sample_status",
  "cams_diagnostic",
]);
const LEGACY_BUNDLE_CACHE_SPECS = Object.freeze([
  Object.freeze({
    prefix: "meteofriul:weather-v1:bundle:v2",
    indexKey: "meteofriul:weather-v1:bundle:v2:lru",
  }),
  Object.freeze({
    prefix: "meteofriul:weather-v1:bundle:v3",
    indexKey: "meteofriul:weather-v1:bundle:v3:lru",
  }),
]);
const AUTONOMOUS_PRIMARY_SOURCE = "icon2i_local_pilot";
const AUTONOMOUS_MODE = "local_contract_v1";
const CAMS_USABLE_AGE_MS = 30 * HOUR_MS;
const MAX_VERIFY_WINDOW_MS = 10 * 60 * 1000;
const EXPECTED_CATALOG_VERSION = LOCAL_WEATHER_V1_CATALOG.version;
const EXPECTED_CATALOG_SHA256 = LOCAL_WEATHER_V1_CATALOG.sha256;
const EXPECTED_MUNICIPALITY_COUNT = LOCAL_WEATHER_V1_CATALOG.municipality_count;

export const LOCAL_WEATHER_V1_BUNDLE_CACHE_PREFIX = "meteofriul:weather-v1:bundle:v4";
export const LOCAL_WEATHER_V1_BUNDLE_CACHE_INDEX_KEY =
  `${LOCAL_WEATHER_V1_BUNDLE_CACHE_PREFIX}:lru`;
export const LOCAL_WEATHER_V1_CAMS_FAMILY_DECISION_CACHE_PREFIX =
  "meteofriul:weather-v1:cams-family-decision:v1";
export const LOCAL_WEATHER_V1_VERIFY_WINDOW_MS = 10 * 60 * 1000;

const identities = new WeakMap();
const cleanedLegacyBundleStores = new WeakSet();
const inFlight = new Map();
const retainedBundles = new Map();
const recentlyVerifiedBundles = new Map();
const candidateCommitFailures = new Map();
const camsFamilyStates = new Map();
const iconFamilyStates = new Map();
let nextIdentity = 1;

export function clearLocalWeatherV1MemoryCache() {
  retainedBundles.clear();
  recentlyVerifiedBundles.clear();
  candidateCommitFailures.clear();
  camsFamilyStates.clear();
  iconFamilyStates.clear();
  return true;
}

function identity(value) {
  if ((typeof value !== "object" || value === null) && typeof value !== "function") {
    return `${typeof value}:${String(value)}`;
  }
  let result = identities.get(value);
  if (!result) {
    result = `ref:${nextIdentity}`;
    nextIdentity += 1;
    identities.set(value, result);
  }
  return result;
}

function locationIdentity(location) {
  if (typeof location === "string") return `city:${location.trim().toLocaleLowerCase("it")}`;
  const istat = String(location?.municipality?.istatCode || location?.istatCode || "").trim();
  const city = String(location?.municipality?.name || location?.city || "").trim().toLocaleLowerCase("it");
  const latitude = Number(location?.lat);
  const longitude = Number(location?.lon);
  return JSON.stringify({
    istat,
    city,
    lat: Number.isFinite(latitude) ? latitude : null,
    lon: Number.isFinite(longitude) ? longitude : null,
  });
}

function normalizedName(value) {
  return String(value || "")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("it")
    .replace(/[^a-z0-9]+/g, " ")
    .trim()
    .replace(/\s+/g, " ");
}

function municipalityIdentity(location) {
  const istatCode = String(
    location?.municipality?.istatCode || location?.istatCode || "",
  ).trim();
  if (/^\d{6}$/.test(istatCode)) return `istat:${istatCode}`;
  const city = normalizedName(
    typeof location === "string"
      ? location
      : location?.municipality?.name || location?.city,
  );
  return city ? `city:${city}` : null;
}

export function getLocalWeatherV1BundleCacheKey(location, { baseUrl } = {}) {
  const municipality = municipalityIdentity(location);
  if (!municipality || typeof baseUrl !== "string" || !baseUrl.trim()) return null;
  const scope = sha256Hex(baseUrl.replace(/\/+$/, "")).slice(0, 16);
  const catalogScope = EXPECTED_CATALOG_SHA256.slice(0, 16);
  return `${LOCAL_WEATHER_V1_BUNDLE_CACHE_PREFIX}:${scope}:${catalogScope}:${municipality}`;
}

export function getLocalWeatherV1CamsFamilyDecisionCacheKey({ baseUrl } = {}) {
  if (typeof baseUrl !== "string" || !baseUrl.trim()) return null;
  const scope = sha256Hex(baseUrl.replace(/\/+$/, "")).slice(0, 16);
  const catalogScope = EXPECTED_CATALOG_SHA256.slice(0, 16);
  return `${LOCAL_WEATHER_V1_CAMS_FAMILY_DECISION_CACHE_PREFIX}:${scope}:${catalogScope}`;
}

function clockMilliseconds(now) {
  try {
    const value = typeof now === "function" ? now() : now;
    if (value instanceof Date) return value.getTime();
    if (typeof value === "string") return Date.parse(value);
    return Number(value);
  } catch {
    return NaN;
  }
}

function iconEvidenceIdentity(value) {
  const evidence = value?.source?.icon?.evidence;
  const path = evidence?.path;
  const etag = evidence?.etag;
  if (
    typeof path !== "string"
    || !/^runs\/\d{8}T\d{6}Z\/municipalities\/\d{6}\.json$/.test(path)
    || typeof etag !== "string"
    || !etag
  ) return null;
  return `${path}\n${etag}`;
}

function iconObjectIdentity(bundle) {
  const current = iconEvidenceIdentity(bundle?.current);
  const forecast = iconEvidenceIdentity(bundle?.forecast);
  return current && current === forecast ? current : null;
}

function camsFamilyDecisionFromEvidence(evidence) {
  const family = evidence?.family;
  if (
    !family
    || Object.keys(family).sort().join(",")
      !== "active_run_id,disabled_run_ids,published_at,revision"
    || !Number.isSafeInteger(family.revision)
    || family.revision < 1
    || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/.test(family.published_at)
    || !Number.isFinite(Date.parse(family.published_at))
    || !/^\d{8}T\d{6}Z$/.test(family.active_run_id)
    || !Array.isArray(family.disabled_run_ids)
  ) return null;
  const canonicalDisabled = [...new Set(family.disabled_run_ids)].sort();
  if (
    canonicalDisabled.length !== family.disabled_run_ids.length
    || canonicalDisabled.some((runId, index) => runId !== family.disabled_run_ids[index])
    || canonicalDisabled.some((runId) => !/^\d{8}T\d{6}Z$/.test(runId))
    || canonicalDisabled.includes(family.active_run_id)
  ) return null;
  return {
    activeRunId: family.active_run_id,
    disabledRunIds: canonicalDisabled,
    publishedAt: Date.parse(family.published_at),
    revision: family.revision,
  };
}

function camsFamilyEvidenceFromDecision(decision) {
  return {
    revision: decision.revision,
    published_at: new Date(decision.publishedAt).toISOString().replace(".000Z", "Z"),
    active_run_id: decision.activeRunId,
    disabled_run_ids: [...decision.disabledRunIds],
  };
}

function camsFamilyDecisionFromLatestSnapshot(latest) {
  if (!exactObjectKeys(latest, [
    "revision", "published_at", "latest", "disabled_run_ids",
  ]) || !exactObjectKeys(latest.latest, ["source_run_id"])) return null;
  return camsFamilyDecisionFromEvidence({
    family: {
      revision: latest.revision,
      published_at: latest.published_at,
      active_run_id: latest.latest.source_run_id,
      disabled_run_ids: latest.disabled_run_ids,
    },
  });
}

function camsFamilyDecisionPayload(decision, baseUrl) {
  const family = camsFamilyEvidenceFromDecision(decision);
  return {
    kind: PERSISTED_CAMS_FAMILY_DECISION_KIND,
    version: PERSISTED_CAMS_FAMILY_DECISION_VERSION,
    scope_sha256: sha256Hex(String(baseUrl || "").replace(/\/+$/, "")),
    catalog_sha256: EXPECTED_CATALOG_SHA256,
    ...family,
  };
}

function serializeCamsFamilyDecision(decision, baseUrl) {
  const payload = camsFamilyDecisionPayload(decision, baseUrl);
  return JSON.stringify({
    ...payload,
    sha256: sha256Hex(canonicalJson(payload)),
  });
}

function parseCamsFamilyDecisionRecord(serialized, baseUrl) {
  let record;
  try {
    record = JSON.parse(serialized);
  } catch {
    throw runtimeError("CAMS_REVOCATION_JOURNAL_INVALID", "registro revoche CAMS non valido");
  }
  if (!exactObjectKeys(record, [
    "kind", "version", "scope_sha256", "catalog_sha256", "revision",
    "published_at", "active_run_id", "disabled_run_ids", "sha256",
  ])) {
    throw runtimeError("CAMS_REVOCATION_JOURNAL_INVALID", "schema registro revoche CAMS non valido");
  }
  const { sha256, ...payload } = record;
  const decision = camsFamilyDecisionFromEvidence({
    family: {
      revision: payload.revision,
      published_at: payload.published_at,
      active_run_id: payload.active_run_id,
      disabled_run_ids: payload.disabled_run_ids,
    },
  });
  if (
    record.kind !== PERSISTED_CAMS_FAMILY_DECISION_KIND
    || record.version !== PERSISTED_CAMS_FAMILY_DECISION_VERSION
    || record.scope_sha256 !== sha256Hex(String(baseUrl || "").replace(/\/+$/, ""))
    || record.catalog_sha256 !== EXPECTED_CATALOG_SHA256
    || !decision
    || !/^[0-9a-f]{64}$/.test(sha256)
    || sha256Hex(canonicalJson(payload)) !== sha256
  ) {
    throw runtimeError("CAMS_REVOCATION_JOURNAL_INVALID", "integrita registro revoche CAMS non valida");
  }
  return decision;
}

function camsFamilyValueProvenance(value) {
  const quality = value?.data_quality;
  const evidence = value?.source?.cams?.evidence;
  const decision = camsFamilyDecisionFromEvidence(evidence);
  const stages = evidence?.stages;
  const latest = stages?.latest;
  const manifest = stages?.manifest;
  const municipality = stages?.municipality;
  const match = typeof latest?.path === "string"
    ? /^families\/cams\/runs\/(\d{8}T\d{6}Z)\/release\.json#pollen$/.exec(latest.path)
    : null;
  if (
    !match
    || typeof latest.etag !== "string"
    || !latest.etag
    || manifest?.path !== `runs/${match[1]}/manifest.json`
    || typeof municipality?.path !== "string"
    || !municipality.path.startsWith(`runs/${match[1]}/municipalities/`)
    || !decision
    || decision.activeRunId !== match[1]
  ) return null;
  const runAt = Date.parse(quality?.cams_run_utc);
  if (!Number.isFinite(runAt)) return null;
  const expectedRunId = new Date(runAt).toISOString().replace(/[-:]/g, "").replace(".000", "");
  if (match[1] !== expectedRunId) return null;
  return {
    ...decision,
    identity: `${latest.path}\n${latest.etag}`,
  };
}

function camsFamilyDecision(bundle) {
  const current = camsFamilyDecisionFromEvidence(bundle?.current?.source?.cams?.evidence);
  const forecast = camsFamilyDecisionFromEvidence(bundle?.forecast?.source?.cams?.evidence);
  if (
    !current
    || !forecast
    || current.activeRunId !== forecast.activeRunId
    || current.revision !== forecast.revision
    || current.publishedAt !== forecast.publishedAt
    || current.disabledRunIds.join("\n") !== forecast.disabledRunIds.join("\n")
  ) return null;
  return current;
}

function camsFamilyProvenance(bundle) {
  const current = camsFamilyValueProvenance(bundle?.current);
  const forecast = camsFamilyValueProvenance(bundle?.forecast);
  if (
    !current
    || !forecast
    || current.activeRunId !== forecast.activeRunId
    || current.revision !== forecast.revision
    || current.publishedAt !== forecast.publishedAt
    || current.identity !== forecast.identity
    || current.disabledRunIds.join("\n") !== forecast.disabledRunIds.join("\n")
  ) return null;
  return current;
}

function camsFamilyEvidenceIdentity(bundle) {
  return camsFamilyProvenance(bundle)?.identity ?? null;
}

function hasAutonomousSource(value) {
  return value?.primary_source === AUTONOMOUS_PRIMARY_SOURCE
    && value?.source?.active === AUTONOMOUS_PRIMARY_SOURCE
    && value?.source?.primary_source === AUTONOMOUS_PRIMARY_SOURCE
    && value?.source?.icon?.status === "available"
    && value?.data_quality?.mode === AUTONOMOUS_MODE
    && value?.data_quality?.catalog_version === EXPECTED_CATALOG_VERSION
    && value?.data_quality?.catalog_sha256 === EXPECTED_CATALOG_SHA256
    && value?.source?.catalog?.version === EXPECTED_CATALOG_VERSION
    && value?.source?.catalog?.sha256 === EXPECTED_CATALOG_SHA256
    && value?.source?.catalog?.municipality_count === EXPECTED_MUNICIPALITY_COUNT
    && iconEvidenceIdentity(value) !== null;
}

function matchesMunicipality(bundle, location) {
  const expected = municipalityIdentity(location);
  if (!expected) return false;
  const current = bundle?.current;
  const forecast = bundle?.forecast;
  if (expected.startsWith("istat:")) {
    const expectedCode = expected.slice(6);
    return current?.data_quality?.municipality_istat === expectedCode
      && forecast?.data_quality?.municipality_istat === expectedCode;
  }
  const expectedName = expected.slice(5);
  return normalizedName(bundle?.city || current?.city) === expectedName
    && normalizedName(forecast?.city || bundle?.city) === expectedName;
}

function hasOfficialPayloadFields(bundle) {
  return ["officialAlerts", "osmerAudit", "official_alerts", "osmer_audit"]
    .some((key) => Object.prototype.hasOwnProperty.call(bundle || {}, key));
}

function readVerifiedCamsHourlyCache(bundle) {
  return decodeVerifiedCamsHourlyCache(bundle?.current?.cams_hourly_cache, {
    municipalityIstat: bundle?.current?.data_quality?.municipality_istat,
    catalogSha256: EXPECTED_CATALOG_SHA256,
    runUtc: bundle?.current?.data_quality?.cams_run_utc,
  });
}

function camsRunFreshness(cache, current) {
  return current <= Date.parse(cache.fresh_until_utc) ? "fresh" : "stale";
}

function decorateCamsState(value, { currentSample, freshness }) {
  const flags = (value.data_quality.flags || [])
    .filter(flag => !["cams_pending", "cams_unavailable", "cams_last_known"].includes(flag));
  if (!currentSample) flags.push("cams_last_known");
  return {
    ...value,
    model_support: { ...value.model_support, cams: true },
    source: {
      ...value.source,
      status: "available",
      cams: { ...value.source.cams, status: "available", diagnostic: null },
    },
    data_quality: {
      ...value.data_quality,
      cams_status: freshness,
      cams_diagnostic: null,
      cams_sample_status: currentSample ? "current" : "last_known",
      capability_gaps: (value.data_quality.capability_gaps || [])
        .filter(gap => !["cams_pollen", "cams_pollen_pending"].includes(gap)),
      flags: [...new Set(flags)].sort(),
    },
  };
}

function withCachedCamsSample(bundle, cache, sample, current) {
  const timestamp = Date.parse(sample.valid_at_utc);
  const usableUntil = Date.parse(cache.usable_until_utc);
  const runAt = Date.parse(cache.run_utc);
  const currentSample = current >= timestamp
    && current - timestamp < CURRENT_SAMPLE_MAX_LAG_MS
    && current <= usableUntil
    && current - runAt <= CAMS_USABLE_AGE_MS;
  const freshness = camsRunFreshness(cache, current);
  const pollenVariables = new Map(cache.pollen_variables.map(variable => [variable.id, variable]));
  const currentValue = decorateCamsState(bundle.current, { currentSample, freshness });
  const pollenData = {
    ...currentValue.pollen_data,
    status: "experimental_model_snapshot",
    freshness,
    valid_at_utc: sample.valid_at_utc,
    values: { ...sample.pollen_values },
    all_variables: CAMS_POLLEN_FIELDS.map(([id, uiKey]) => ({
      ...pollenVariables.get(id),
      value: sample.pollen_values[uiKey],
      units: pollenVariables.get(id).unit,
      quality_flags: [...sample.pollen_quality_flags[id]],
    })),
    sample_status: currentSample ? "current" : "last_known",
  };
  const airData = {
    ...(currentValue.air_quality_data || {}),
    run_at: cache.run_utc,
    valid_at: sample.valid_at_utc,
    values: { ...sample.air_values },
    sample_status: currentSample ? "current" : "last_known",
  };
  currentValue.pollen_data = pollenData;
  currentValue.air_quality_data = airData;
  currentValue.data_quality.cams_run_utc = cache.run_utc;
  currentValue.data_quality.cams_valid_at_utc = sample.valid_at_utc;
  const forecastValue = decorateCamsState(bundle.forecast, { currentSample, freshness });
  forecastValue.data_quality.cams_run_utc = cache.run_utc;
  forecastValue.data_quality.cams_valid_at_utc = sample.valid_at_utc;
  return {
    ...bundle,
    current: currentValue,
    forecast: forecastValue,
  };
}

function retainLastKnownCams(bundle, current) {
  const validAt = Date.parse(bundle?.current?.data_quality?.cams_valid_at_utc);
  const runAt = Date.parse(bundle?.current?.data_quality?.cams_run_utc);
  if (!Number.isFinite(validAt) || current < validAt) return bundle;
  const currentSample = current - validAt < CURRENT_SAMPLE_MAX_LAG_MS
    && Number.isFinite(runAt)
    && current - runAt <= CAMS_USABLE_AGE_MS;
  if (currentSample) return bundle;
  const freshness = currentSample && bundle.current.data_quality.cams_status === "fresh" ? "fresh" : "stale";
  const currentValue = decorateCamsState(bundle.current, { currentSample, freshness });
  currentValue.pollen_data = {
    ...currentValue.pollen_data,
    freshness,
    sample_status: currentSample ? "current" : "last_known",
  };
  if (currentValue.air_quality_data) {
    currentValue.air_quality_data = {
      ...currentValue.air_quality_data,
      sample_status: currentSample ? "current" : "last_known",
    };
  }
  return {
    ...bundle,
    current: currentValue,
    forecast: decorateCamsState(bundle.forecast, { currentSample, freshness }),
  };
}

function reselectRetainedCams(bundle, current) {
  if (!camsFamilyProvenance(bundle)
    || bundle?.current?.source?.cams?.status !== "available"
    || bundle?.current?.pollen_data?.status !== "experimental_model_snapshot") return bundle;
  const cache = readVerifiedCamsHourlyCache(bundle);
  if (!cache) return retainLastKnownCams(bundle, current);
  const sample = cache.samples.findLast(row => Date.parse(row.valid_at_utc) <= current);
  return sample ? withCachedCamsSample(bundle, cache, sample, current) : retainLastKnownCams(bundle, current);
}

function withoutCams(bundle, diagnostic, familyEvidence) {
  const retainedFamily = familyEvidence === undefined
    ? bundle?.current?.source?.cams?.evidence?.family || null
    : familyEvidence;
  const cleanFamily = retainedFamily ? {
    ...retainedFamily,
    disabled_run_ids: [...retainedFamily.disabled_run_ids],
  } : null;
  const decorate = value => ({
    ...value,
    model_support: { ...value.model_support, cams: false },
    source: {
      ...value.source,
      status: "degraded",
      label: "ItaliaMeteo ICON-2I · CAMS non disponibile",
      cams: {
        ...value.source.cams,
        status: "unavailable",
        model: null,
        attribution: null,
        run_utc: null,
        evidence: cleanFamily ? { family: cleanFamily, stages: {} } : null,
        diagnostic,
      },
    },
    data_quality: {
      ...value.data_quality,
      cams_status: "unavailable",
      cams_run_utc: null,
      cams_valid_at_utc: null,
      cams_sample_status: null,
      cams_diagnostic: diagnostic,
      capability_gaps: [...new Set([
        ...(value.data_quality.capability_gaps || []).filter(gap => gap !== "cams_pollen_pending"),
        "cams_pollen",
      ])],
      flags: [...new Set([
        ...(value.data_quality.flags || []).filter(flag => !flag.startsWith("cams_")),
        "cams_unavailable",
      ])].sort(),
    },
  });
  const current = decorate(bundle.current);
  current.air_quality_data = null;
  current.cams_hourly_cache = null;
  current.pollen = "Pollini CAMS non disponibili";
  current.pollen_data = {
    status: "unavailable",
    freshness: null,
    summary: current.pollen,
    level: null,
    main: null,
    values: {},
    units: "grains/m3",
    run_utc: null,
    generated_at_utc: null,
    valid_at_utc: null,
    source: "cams_european_ensemble",
    all_variables: [],
    grid_point: null,
    attribution: null,
    health_classification: null,
    note: "CAMS non disponibile; nessun fallback o classificazione sanitaria applicata",
    diagnostic,
  };
  return { ...bundle, current, forecast: decorate(bundle.forecast) };
}

function withoutExpiredCandidateCams(bundle) {
  return withoutCams(bundle, {
    provider: "cams_europe_pollen",
    status: "unavailable",
    stage: "adapt",
    code: "EXPIRED",
    message: "Dati CAMS non disponibili per questo aggiornamento; meteo ICON conservato",
  });
}

function withoutRevokedCams(bundle, familyEvidence) {
  return withoutCams(bundle, {
    provider: "cams_europe_pollen",
    status: "unavailable",
    stage: "family",
    code: "RUN_DISABLED",
    message: "Run CAMS revocato; meteo ICON verificato conservato",
  }, familyEvidence);
}

function withoutUnverifiableCamsAuthority(bundle, error) {
  return withoutCams(bundle, {
    provider: "cams_europe_pollen",
    status: "unavailable",
    stage: "family",
    code: error?.code || "CAMS_REVOCATION_RESTORE_FAILED",
    message: "Stato delle revoche CAMS non verificabile; meteo ICON conservato",
  }, null);
}

function retainedSolar(bundle, currentTime, location) {
  let point;
  try {
    point = resolveLocalWeatherV1PresentationPoint(
      location,
      bundle.current.data_quality.catalog_point,
    );
  } catch {
    return null;
  }
  const solar = getHomeSolarState({ now: currentTime, latitude: point.lat, longitude: point.lon, timeZone: "Europe/Rome" });
  if (solar.source === "fallback" || !Number.isFinite(solar.sunriseMinutes) || !Number.isFinite(solar.sunsetMinutes)) return null;
  const formatClock = minutes => `${String(Math.floor(minutes / 60)).padStart(2, "0")}:${String(Math.round(minutes % 60)).padStart(2, "0")}`;
  return { solar, point, sunrise: formatClock(solar.sunriseMinutes), sunset: formatClock(solar.sunsetMinutes) };
}

function normalizeRetainedSolar(bundle, currentTime, location) {
  if (!["is_day", "sunrise", "sunset"].every(field => Object.hasOwn(bundle?.current || {}, field))) {
    return bundle;
  }
  const resolved = retainedSolar(bundle, currentTime, location);
  if (!resolved) return null;
  const dataQuality = {
    ...bundle.current.data_quality,
    day_phase_source: resolved.solar.source,
    location_scope: resolved.point.source,
  };
  return {
    ...bundle,
    current: {
      ...bundle.current,
      is_day: resolved.solar.isNight ? 0 : 1,
      sunrise: resolved.sunrise,
      sunset: resolved.sunset,
      data_quality: dataQuality,
    },
    forecast: {
      ...bundle.forecast,
      data_quality: { ...bundle.forecast.data_quality, day_phase_source: resolved.solar.source,
        location_scope: resolved.point.source },
    },
  };
}

function rebaseRetainedCurrent(bundle, sample, currentTime, location) {
  const normalized = normalizeRetainedSolar(bundle, currentTime, location);
  if (!normalized) return null;
  const fields = ["temperature", "condition", "wind_speed", "wind_direction", "wind_gusts", "cloud_cover",
    "precipitation", "rain", "humidity", "pressure", "feels_like"];
  if (!fields.every(key => Object.hasOwn(sample, key)) || !Number.isFinite(sample.temperature)) return null;
  const current = {
    ...normalized.current,
    ...Object.fromEntries(fields.map(key => [key, sample[key]])),
    data_quality: {
      ...normalized.current.data_quality,
      valid_at_utc: sample.time,
      native_weather_code: sample.data_quality?.native_weather_code ?? null,
      native_condition_label: sample.data_quality?.native_condition_label ?? null,
      native_condition_status: sample.data_quality?.native_condition_status ?? null,
      snowfall_water_equivalent_mm: sample.snowfall_water_equivalent_mm ?? null,
      flags: [...new Set([...(sample.quality_flags || []),
        ...(normalized.current.data_quality.flags || []).filter(flag => flag.startsWith("cams_"))])].sort(),
    },
  };
  return { ...normalized, current, forecast: { ...normalized.forecast, data_quality: { ...current.data_quality } } };
}

function prepareRetainedBundle(bundle, now, location) {
  const current = clockMilliseconds(now);
  const quality = bundle?.current?.data_quality;
  const forecastQuality = bundle?.forecast?.data_quality;
  const runAt = Date.parse(quality?.run_utc);
  const forecastRunAt = Date.parse(forecastQuality?.run_utc);
  const validAt = Date.parse(quality?.valid_at_utc);
  if (hasOfficialPayloadFields(bundle)) return null;
  if (!hasAutonomousSource(bundle?.current) || !hasAutonomousSource(bundle?.forecast)) return null;
  if (!iconObjectIdentity(bundle)) return null;
  if (!matchesMunicipality(bundle, location)) return null;
  if (![current, runAt, forecastRunAt, validAt].every(Number.isFinite)) return null;
  if (runAt !== forecastRunAt || current < runAt || current < validAt || validAt < runAt) return null;
  const rows = bundle.current.hourly_forecast;
  const future = selectIconFutureRows(rows, current, "time");
  if (future.length < ICON_FORECAST_WINDOW_POLICY.minimumFutureHours
    || rows.some(row => Date.parse(row.time) < runAt || Date.parse(row.time) > runAt + 72 * HOUR_MS)) return null;
  let prepared = normalizeRetainedSolar(bundle, current, location);
  if (!prepared) return null;
  if (current - validAt >= CURRENT_SAMPLE_MAX_LAG_MS) {
    const sample = rows.findLast(row => Date.parse(row.time) <= current);
    if (!sample || current - Date.parse(sample.time) >= CURRENT_SAMPLE_MAX_LAG_MS) return null;
    prepared = rebaseRetainedCurrent(prepared, sample, current, location);
    if (!prepared) return null;
  }
  if (!["pending", "unavailable"].includes(quality?.cams_status)) {
    const camsRunAt = Date.parse(quality?.cams_run_utc);
    const camsValidAt = Date.parse(quality?.cams_valid_at_utc);
    if (!camsFamilyProvenance(bundle) || bundle.current.source.cams.status !== "available"
      || bundle.current.pollen_data?.status !== "experimental_model_snapshot"
      || ![camsRunAt, camsValidAt].every(Number.isFinite) || current < camsRunAt || current < camsValidAt) return null;
    prepared = reselectRetainedCams(prepared, current);
  }
  const freshUntil = Date.parse(quality.fresh_until_utc);
  if (Number.isFinite(freshUntil)) {
    const status = current <= freshUntil ? "fresh" : "stale";
    if (prepared.current.data_quality.status !== status || prepared.current.cache?.status !== status) {
      const decorate = value => ({ ...value, cache: { ...value.cache, status },
        data_quality: { ...value.data_quality, status } });
      prepared = { ...prepared, current: decorate(prepared.current), forecast: decorate(prepared.forecast) };
    }
  }
  if (prepared !== bundle || future.length !== rows.length || future.some((row, index) => row !== rows[index])) {
    const dataQuality = {
      ...prepared.current.data_quality,
      run_age_hours: (current - runAt) / HOUR_MS,
      coverage_hours: (Date.parse(future.at(-1).time) - current) / HOUR_MS,
    };
    prepared = {
      ...prepared,
      current: { ...prepared.current, hourly_forecast: future, hourly_next_12h: future.slice(0, 12), data_quality: dataQuality },
      forecast: { ...prepared.forecast, data_quality: { ...dataQuality } },
    };
  }
  return prepared;
}

function hasUsableCams(bundle, now) {
  const current = clockMilliseconds(now);
  const quality = bundle?.current?.data_quality;
  const runAt = Date.parse(quality?.cams_run_utc);
  const validAt = Date.parse(quality?.cams_valid_at_utc);
  return !["pending", "unavailable"].includes(quality?.cams_status)
    && bundle?.current?.source?.cams?.status === "available"
    && bundle?.current?.pollen_data?.status === "experimental_model_snapshot"
    && camsFamilyEvidenceIdentity(bundle) !== null
    && [current, runAt, validAt].every(Number.isFinite)
    && current >= runAt
    && current >= validAt
    && current - runAt <= CAMS_USABLE_AGE_MS
    && current - validAt < CURRENT_SAMPLE_MAX_LAG_MS;
}

function hasRetainableCams(bundle, now) {
  const current = clockMilliseconds(now);
  const quality = bundle?.current?.data_quality;
  const runAt = Date.parse(quality?.cams_run_utc);
  const validAt = Date.parse(quality?.cams_valid_at_utc);
  return !["pending", "unavailable"].includes(quality?.cams_status)
    && bundle?.current?.source?.cams?.status === "available"
    && bundle?.current?.pollen_data?.status === "experimental_model_snapshot"
    && camsFamilyEvidenceIdentity(bundle) !== null
    && [current, runAt, validAt].every(Number.isFinite)
    && current >= runAt
    && current >= validAt;
}

function prepareIncomingBundle(incoming, now, location) {
  const prepared = prepareRetainedBundle(incoming, now, location);
  if (!prepared || !hasRetainableCams(prepared, now) || hasUsableCams(prepared, now)) return prepared;
  const current = clockMilliseconds(now);
  const runAt = Date.parse(prepared.current.data_quality.cams_run_utc);
  return current - runAt > CAMS_USABLE_AGE_MS
    ? withoutExpiredCandidateCams(prepared)
    : prepared;
}

function bundleOrder(bundle, now) {
  const quality = bundle.current.data_quality;
  const camsAvailable = hasUsableCams(bundle, now);
  const camsRetained = hasRetainableCams(bundle, now);
  const camsStatus = quality.cams_status;
  const family = camsRetained ? camsFamilyProvenance(bundle) : null;
  return {
    iconRun: Date.parse(quality.run_utc),
    iconValid: Date.parse(quality.valid_at_utc),
    camsRank: camsAvailable ? 3 : camsRetained ? 2 : camsStatus === "unavailable" ? 1 : 0,
    camsAvailable,
    camsRetained,
    camsRun: Date.parse(quality.cams_run_utc),
    camsValid: Date.parse(quality.cams_valid_at_utc),
    camsRevision: family?.revision ?? 0,
    camsRunId: family?.activeRunId ?? null,
    camsDisabledRunIds: new Set(family?.disabledRunIds ?? []),
  };
}

function iconDisplayFingerprint(bundle) {
  const stripProviderMetadata = (value) => {
    const {
      pollen: _pollen,
      pollen_data: _pollenData,
      air_quality_data: _airQualityData,
      cams_hourly_cache: _camsHourlyCache,
      source: _source,
      model_support: _modelSupport,
      cache: _cache,
      data_quality: _dataQuality,
      ...displayData
    } = value || {};
    return displayData;
  };
  return sha256Hex(JSON.stringify({
    city: bundle?.city,
    current: stripProviderMetadata(bundle?.current),
    forecast: stripProviderMetadata(bundle?.forecast),
  }));
}

function withDailyForecast(bundle, forecast) {
  return {
    ...bundle,
    forecast: {
      ...bundle.forecast,
      forecast: forecast?.forecast,
      daily: forecast?.daily,
      daily_extrema_version: forecast?.daily_extrema_version,
    },
  };
}

function hasConsistentDailyTable(forecast) {
  const days = forecast?.forecast;
  if (!Array.isArray(days) || !days.length) return false;
  const dates = days.map(day => day.date);
  return new Set(dates).size === dates.length
    && [
      ["time", dates],
      ["temperature_2m_min", days.map(day => day.min_temp)],
      ["temperature_2m_max", days.map(day => day.max_temp)],
      ["weathercode", days.map(day => day.weathercode ?? null)],
      ["weather_code", days.map(day => day.weathercode ?? null)],
    ].every(([field, values]) => JSON.stringify(forecast.daily?.[field]) === JSON.stringify(values));
}

// Both inputs came from the verified adapter for the same ICON object. The
// only permitted daily change is additional historical hours, not a revision
// of existing extrema or the loss of any already retained day/hour.
function enrichesDailyForecast(current, candidate, iconRun) {
  if (current?.daily_extrema_version !== 2 || candidate?.daily_extrema_version !== 2
    || !hasConsistentDailyTable(current) || !hasConsistentDailyTable(candidate)
    || current.forecast.length !== candidate.forecast.length) return false;
  let extended = false;
  const valid = current.forecast.every((day, index) => {
    const next = candidate.forecast[index];
    if (day.date !== next.date) return false;
    if (JSON.stringify(day) === JSON.stringify(next)) return true;
    const previousRun = Date.parse(next.previous_run_at);
    if (!Number.isFinite(previousRun) || previousRun >= iconRun) return false;
    const { previous_run_at: _previousRun, ...oldFields } = day;
    const { previous_run_at: _nextPreviousRun, ...newFields } = next;
    // The adapter records historical provenance on every day, even if only
    // today's morning was added. Unchanged future days remain acceptable.
    if (JSON.stringify(oldFields) === JSON.stringify(newFields)) return true;
    if (day.partial_day !== true || typeof next.partial_day !== "boolean"
      || !Number.isInteger(day.source_hours) || day.source_hours < 1
      || !Number.isInteger(next.source_hours) || next.source_hours <= day.source_hours
      || next.source_hours > 25
      || ![day.sampled_min_temp, day.sampled_max_temp, next.sampled_min_temp, next.sampled_max_temp]
        .every(Number.isFinite)
      || next.sampled_min_temp > day.sampled_min_temp
      || next.sampled_max_temp < day.sampled_max_temp
      || next.sampled_min_temp > next.sampled_max_temp) return false;
    if (next.partial_day
      ? next.min_temp !== null || next.max_temp !== null
      : ![23, 24, 25].includes(next.source_hours)
        || next.min_temp !== next.sampled_min_temp || next.max_temp !== next.sampled_max_temp) return false;
    extended = true;
    return true;
  });
  return valid && extended;
}

function alignVerifiedHourlyWindows(current, candidate, now) {
  const leftRows = current.current.hourly_forecast;
  const rightRows = candidate.current.hourly_forecast;
  if (JSON.stringify(leftRows) === JSON.stringify(rightRows)) return [current, candidate];
  const rowsByTime = new Map(leftRows.map(row => [Date.parse(row.time), row]));
  let overlaps = false;
  for (const row of rightRows) {
    const time = Date.parse(row.time);
    const previous = rowsByTime.get(time);
    if (previous) {
      if (JSON.stringify(previous) !== JSON.stringify(row)) return null;
      overlaps = true;
    } else rowsByTime.set(time, row);
  }
  if (!overlaps) return null;
  const rows = selectIconFutureRows([...rowsByTime.entries()]
    .sort(([left], [right]) => left - right).map(([, row]) => row), clockMilliseconds(now), "time");
  if (rows.length < ICON_FORECAST_WINDOW_POLICY.minimumFutureHours) return null;
  const decorate = bundle => {
    const coverageHours = (Date.parse(rows.at(-1).time) - clockMilliseconds(now)) / HOUR_MS;
    return { ...bundle, current: {
      ...bundle.current, hourly_forecast: rows, hourly_next_12h: rows.slice(0, 12),
      data_quality: { ...bundle.current.data_quality, coverage_hours: coverageHours },
    }, forecast: { ...bundle.forecast,
      data_quality: { ...bundle.forecast.data_quality, coverage_hours: coverageHours } } };
  };
  return [decorate(current), decorate(candidate)];
}

function preferredCamsBundle(current, candidate, now) {
  const left = bundleOrder(current, now);
  const right = bundleOrder(candidate, now);
  if (right.camsRank !== left.camsRank) return right.camsRank > left.camsRank ? candidate : current;
  if (!right.camsRetained) {
    // Once a revocation has sanitized the previous active, retain the terminal
    // outcome delivered with that same/newer family decision. This preserves a
    // useful acquisition diagnostic without ever restoring revoked values.
    if (right.camsRank === 1) {
      const previousDecision = camsFamilyDecision(current);
      const candidateDecision = camsFamilyDecision(candidate);
      if (candidateDecision && (!previousDecision
        || candidateDecision.revision >= previousDecision.revision)) return candidate;
    }
    return current;
  }
  if (
    right.camsRevision > left.camsRevision
    && right.camsDisabledRunIds.has(left.camsRunId)
  ) return candidate;
  if (
    left.camsRevision > right.camsRevision
    && left.camsDisabledRunIds.has(right.camsRunId)
  ) return current;
  if (right.camsRun !== left.camsRun) return right.camsRun > left.camsRun ? candidate : current;
  if (right.camsValid !== left.camsValid) return right.camsValid > left.camsValid ? candidate : current;
  const candidateHourlyCache = readVerifiedCamsHourlyCache(candidate);
  if (!readVerifiedCamsHourlyCache(current) && candidateHourlyCache
    && right.camsRunId === left.camsRunId
    && right.camsRevision === left.camsRevision
    && camsFamilyEvidenceIdentity(current) === camsFamilyEvidenceIdentity(candidate)) {
    // A bundle persisted by an earlier app version can already contain the
    // same verified CAMS snapshot without its compact hourly series. Enrich
    // only that active bundle: the currently rendered values stay untouched,
    // while later offline hour selection can use the verified samples.
    return {
      ...current,
      current: { ...current.current, cams_hourly_cache: candidateHourlyCache.stored },
    };
  }
  const air = candidate?.current?.air_quality_data;
  if (!current?.current?.air_quality_data && air
    && right.camsRunId === left.camsRunId
    && right.camsRevision === left.camsRevision
    && camsFamilyEvidenceIdentity(current) === camsFamilyEvidenceIdentity(candidate)
    && Date.parse(air.run_at) === right.camsRun
    && Date.parse(air.valid_at) === right.camsValid) return candidate;
  return current;
}

function withCamsFrom(iconBundle, camsBundle) {
  if (iconBundle === camsBundle) return iconBundle;
  const camsQualityFields = [
    "cams_status", "cams_run_utc", "cams_valid_at_utc", "cams_diagnostic", "cams_sample_status",
  ];
  const mergeQuality = (target, source) => {
    const quality = { ...target };
    for (const field of camsQualityFields) {
      if (Object.hasOwn(source || {}, field)) quality[field] = source[field];
      else delete quality[field];
    }
    quality.flags = [...new Set([
      ...(target?.flags || []).filter(flag => !flag.startsWith("cams_")),
      ...(source?.flags || []).filter(flag => flag.startsWith("cams_")),
    ])].sort();
    quality.capability_gaps = [...new Set([
      ...(target?.capability_gaps || []).filter(gap => !gap.startsWith("cams_")),
      ...(source?.capability_gaps || []).filter(gap => gap.startsWith("cams_")),
    ])];
    return quality;
  };
  const mergeValue = (target, source) => ({
    ...target,
    source: {
      ...target.source,
      status: source.source.status,
      label: source.source.label,
      cams: source.source.cams,
    },
    model_support: {
      ...(target.model_support || {}),
      cams: source.model_support?.cams ?? source.source?.cams?.status === "available",
    },
    data_quality: mergeQuality(target.data_quality, source.data_quality),
  });
  const current = mergeValue(iconBundle.current, camsBundle.current);
  current.pollen = camsBundle.current.pollen;
  current.pollen_data = camsBundle.current.pollen_data;
  current.air_quality_data = camsBundle.current.air_quality_data;
  current.cams_hourly_cache = camsBundle.current.cams_hourly_cache ?? null;
  return {
    ...iconBundle,
    current,
    forecast: mergeValue(iconBundle.forecast, camsBundle.forecast),
  };
}

function preferBundle(current, candidate, now) {
  if (!current) return candidate;
  if (!candidate) return current;
  const originalCurrent = current;
  const left = bundleOrder(current, now);
  const right = bundleOrder(candidate, now);
  if (right.iconRun !== left.iconRun || right.iconValid !== left.iconValid) {
    const iconBundle = right.iconRun !== left.iconRun
      ? right.iconRun > left.iconRun ? candidate : current
      : right.iconValid > left.iconValid ? candidate : current;
    return withCamsFrom(iconBundle, preferredCamsBundle(current, candidate, now));
  }
  const leftIconObject = iconObjectIdentity(current);
  const rightIconObject = iconObjectIdentity(candidate);
  if (!leftIconObject || leftIconObject !== rightIconObject) return current;
  // Window changes are allowed only for the same immutable ICON object, with
  // identical overlapping real samples. Preserve newly available future hours.
  const aligned = alignVerifiedHourlyWindows(current, candidate, now);
  if (!aligned) return current;
  [current, candidate] = aligned;
  // Check identity AND all non-daily display fields before allowing enrichment.
  // A daily upgrade must not smuggle a changed current/hourly ICON payload.
  if (
    iconDisplayFingerprint(current) !== iconDisplayFingerprint(withDailyForecast(candidate, current.forecast))
  ) {
    return originalCurrent;
  }
  if (iconDisplayFingerprint(current) !== iconDisplayFingerprint(candidate)) {
    if ((candidate.forecast?.daily_extrema_version === 2 && current.forecast?.daily_extrema_version !== 2)
      || enrichesDailyForecast(current.forecast, candidate.forecast, left.iconRun)) {
      current = withDailyForecast(current, candidate.forecast);
    } else if (enrichesDailyForecast(candidate.forecast, current.forecast, left.iconRun)) {
      // A failed historical retry must not erase morning data or prevent a
      // newer CAMS supplement from being selected by the existing rules below.
      candidate = withDailyForecast(candidate, current.forecast);
    } else {
      return originalCurrent;
    }
  }
  return preferredCamsBundle(current, candidate, now);
}

function normalizeStorage(storage) {
  try {
    if (
      storage
      && (typeof storage === "object" || typeof storage === "function")
      && typeof storage.getItem === "function"
      && typeof storage.setItem === "function"
      && typeof storage.removeItem === "function"
    ) return storage;
  } catch {
    return null;
  }
  return null;
}

function isBundleKeyForPrefix(key, prefix, indexKey) {
  if (typeof key !== "string") return false;
  const keyPrefix = `${prefix}:`;
  if (!key.startsWith(keyPrefix) || key === indexKey) return false;
  const [scope, catalog, identityKind, identityValue, ...extra] = key.slice(keyPrefix.length).split(":");
  if (extra.length || !/^[0-9a-f]{16}$/.test(scope) || !/^[0-9a-f]{16}$/.test(catalog)) {
    return false;
  }
  if (identityKind === "istat") return /^\d{6}$/.test(identityValue);
  return identityKind === "city" && /^[a-z0-9]+(?: [a-z0-9]+)*$/.test(identityValue);
}

function isPersistedBundleKey(key) {
  return isBundleKeyForPrefix(
    key,
    LOCAL_WEATHER_V1_BUNDLE_CACHE_PREFIX,
    LOCAL_WEATHER_V1_BUNDLE_CACHE_INDEX_KEY,
  );
}

function persistedCandidateBaseKey(key) {
  const suffix = ":candidate";
  if (typeof key !== "string" || !key.endsWith(suffix)) return null;
  const baseKey = key.slice(0, -suffix.length);
  return isPersistedBundleKey(baseKey) ? baseKey : null;
}

function legacyBundleSpecForKey(key) {
  return LEGACY_BUNDLE_CACHE_SPECS.find(({ prefix, indexKey }) =>
    isBundleKeyForPrefix(key, prefix, indexKey),
  ) ?? null;
}

function cleanupLegacyPersistedBundles(storage) {
  if (!storage || cleanedLegacyBundleStores.has(storage)) return;
  const candidates = new Set();
  let complete = true;
  for (const { indexKey } of LEGACY_BUNDLE_CACHE_SPECS) {
    try {
      const raw = storage.getItem(indexKey);
      if (raw !== null) {
        const record = JSON.parse(raw);
        if (Array.isArray(record?.keys)) {
          for (const key of record.keys) {
            if (legacyBundleSpecForKey(key)) candidates.add(key);
          }
        }
      }
    } catch {
      // A corrupt legacy index is complemented by enumerable storage below.
    }
  }
  try {
    if (typeof storage.key === "function" && Number.isSafeInteger(storage.length)) {
      for (let index = 0; index < storage.length; index += 1) {
        const key = storage.key(index);
        if (legacyBundleSpecForKey(key)) candidates.add(key);
      }
    }
  } catch {
    complete = false;
  }
  for (const key of candidates) {
    try {
      storage.removeItem(key);
    } catch {
      complete = false;
    }
  }
  for (const { indexKey } of LEGACY_BUNDLE_CACHE_SPECS) {
    try {
      storage.removeItem(indexKey);
    } catch {
      complete = false;
    }
  }
  if (complete) cleanedLegacyBundleStores.add(storage);
}

function uniquePersistedBundleKeys(keys) {
  const unique = new Set();
  for (const key of keys || []) {
    if (!isPersistedBundleKey(key)) continue;
    unique.delete(key);
    unique.add(key);
  }
  return [...unique];
}

function enumeratePersistedBundleKeys(storage) {
  try {
    if (typeof storage?.key !== "function" || !Number.isSafeInteger(storage.length)) return [];
    const keys = [];
    for (let index = 0; index < storage.length; index += 1) {
      const key = storage.key(index);
      if (isPersistedBundleKey(key)) keys.push(key);
    }
    return uniquePersistedBundleKeys(keys);
  } catch {
    return [];
  }
}

function enumeratePersistedCandidateBaseKeys(storage) {
  try {
    if (typeof storage?.key !== "function" || !Number.isSafeInteger(storage.length)) return [];
    const keys = new Set();
    for (let index = 0; index < storage.length; index += 1) {
      const baseKey = persistedCandidateBaseKey(storage.key(index));
      if (baseKey) keys.add(baseKey);
    }
    return [...keys];
  } catch {
    return [];
  }
}

function persistedBundleKeyExists(storage, key) {
  try {
    return storage.getItem(key) !== null;
  } catch {
    // If reads are temporarily blocked, retaining the index entry is safer than
    // deleting a bundle which may still be present.
    return true;
  }
}

function readPersistedBundleIndex(storage) {
  const enumerated = enumeratePersistedBundleKeys(storage);
  try {
    const raw = storage.getItem(LOCAL_WEATHER_V1_BUNDLE_CACHE_INDEX_KEY);
    if (raw === null) return enumerated;
    const record = JSON.parse(raw);
    if (
      !record
      || record.version !== PERSISTED_BUNDLE_VERSION
      || !Array.isArray(record.keys)
      || record.keys.length > 10_000
    ) {
      return enumerated;
    }
    return uniquePersistedBundleKeys([
      ...record.keys.filter(key => persistedBundleKeyExists(storage, key)),
      ...enumerated,
    ]);
  } catch {
    return enumerated;
  }
}

function persistedBundleStorageKeys(storage) {
  return uniquePersistedBundleKeys([
    ...readPersistedBundleIndex(storage),
    ...enumeratePersistedCandidateBaseKeys(storage),
  ]);
}

function persistedRecordExists(storage, key) {
  try {
    return storage.getItem(key) !== null;
  } catch {
    return true;
  }
}

function runtimeError(code, message, cause) {
  const error = new Error(message, cause ? { cause } : undefined);
  error.code = code;
  return error;
}

function iconRunIdFromBundle(bundle) {
  const runAt = Date.parse(bundle?.current?.data_quality?.run_utc);
  return Number.isFinite(runAt)
    ? new Date(runAt).toISOString().replace(/[-:]/g, "").replace(".000", "") : null;
}

function iconFamilyStateFor(baseUrl) {
  const scope = String(baseUrl || "").replace(/\/+$/, "");
  let state = iconFamilyStates.get(scope);
  if (!state) {
    state = { disabledRunIds: new Set() };
    iconFamilyStates.set(scope, state);
  }
  return state;
}

function purgeScopedBundles(baseUrl, storage, shouldRemove) {
  const scope = String(baseUrl || "").replace(/\/+$/, "");
  for (const [key, bundle] of retainedBundles) {
    if (key.split("\n")[0] === scope && shouldRemove(bundle)) {
      retainedBundles.delete(key);
      candidateCommitFailures.delete(key);
    }
  }
  for (const [key, record] of recentlyVerifiedBundles) {
    if (record.baseUrl === scope && shouldRemove(record.bundle)) recentlyVerifiedBundles.delete(key);
  }
  const target = normalizeStorage(storage);
  if (!target) return true;
  const prefix = `${LOCAL_WEATHER_V1_BUNDLE_CACHE_PREFIX}:${sha256Hex(scope).slice(0, 16)}:`;
  const retained = [];
  let removed = true;
  for (const key of persistedBundleStorageKeys(target)) {
    const activeExists = persistedRecordExists(target, key);
    let remove = false;
    let removeCandidate = false;
    if (key.startsWith(prefix)) {
      let activeRecord = null;
      try {
        activeRecord = JSON.parse(target.getItem(key));
        remove = shouldRemove(activeRecord?.bundle);
      }
      catch { /* Corrupt bundles are discarded by the normal validated read. */ }
      try {
        const candidate = JSON.parse(target.getItem(`${key}:candidate`));
        removeCandidate = candidate?.kind === PERSISTED_CAMS_DELTA_KIND
          ? remove || !activeRecord?.bundle
          : candidate ? shouldRemove(candidate.bundle) : false;
      } catch {
        removeCandidate = true;
      }
    }
    if (removeCandidate) removed = discardPersistedCandidate(target, key) && removed;
    if (remove) removed = discardPersistedBundle(target, key) && removed;
    else if (activeExists) retained.push(key);
  }
  savePersistedBundleIndex(target, retained);
  return removed;
}

function observeIconLatest(latest, { baseUrl, storage }) {
  const state = iconFamilyStateFor(baseUrl);
  const disabled = latest?.disabled_run_ids;
  if (!Array.isArray(disabled) || disabled.some(runId => !/^\d{8}T\d{6}Z$/.test(runId))) {
    throw runtimeError("INVALID_DOCUMENT", "disabled_run_ids non e canonico");
  }
  // Observe revocations before fetching the replacement. A transport failure
  // for B must never turn A, already revoked by the verified pointer, into a fallback.
  for (const runId of disabled) state.disabledRunIds.add(runId);
  const scope = String(baseUrl || "").replace(/\/+$/, "");
  for (const [key, failure] of candidateCommitFailures) {
    if (key.split("\n")[0] === scope && state.disabledRunIds.has(failure.iconRun)) {
      candidateCommitFailures.delete(key);
    }
  }
  if (!purgeScopedBundles(baseUrl, storage, bundle => state.disabledRunIds.has(iconRunIdFromBundle(bundle)))) {
    throw runtimeError("CACHE_INVALIDATION_FAILED", "impossibile eliminare tutti i bundle ICON revocati");
  }
}

function assertBundleIconEnabled(bundle, baseUrl) {
  if (iconFamilyStateFor(baseUrl).disabledRunIds.has(iconRunIdFromBundle(bundle))) {
    throw runtimeError("RUN_DISABLED", "run ICON revocato");
  }
}

function restoreIconRevocations({ baseUrl, storage }) {
  const latest = readCachedIconLatest({ baseUrl, storage,
    catalog: LOCAL_WEATHER_V1_CATALOG, istatCodes: LOCAL_WEATHER_V1_ISTAT_CODES });
  if (latest) observeIconLatest(latest, { baseUrl, storage });
}

function camsRunIdFromBundle(bundle) {
  const runAt = Date.parse(bundle?.current?.data_quality?.cams_run_utc);
  if (!Number.isFinite(runAt)) return null;
  return new Date(runAt).toISOString().replace(/[-:]/g, "").replace(".000", "");
}

function camsFamilyStateFor(baseUrl) {
  const scope = String(baseUrl || "").replace(/\/+$/, "");
  let state = camsFamilyStates.get(scope);
  if (!state) {
    state = {
      activeRunId: null,
      disabledRunIds: new Set(),
      publishedAt: 0,
      revision: 0,
      familyEvidence: null,
      durableRevision: 0,
      authorityError: null,
    };
    camsFamilyStates.set(scope, state);
  }
  return state;
}

function sameCamsFamilyDecision(state, family) {
  return family.revision === state.revision
    && family.activeRunId === state.activeRunId
    && family.publishedAt === state.publishedAt
    && family.disabledRunIds.join("\n") === [...state.disabledRunIds].sort().join("\n");
}

function assertCamsFamilyTransition(state, family) {
  if (state.disabledRunIds.has(family.activeRunId)) {
    throw runtimeError("RUN_DISABLED", `il run CAMS ${family.activeRunId} e stato revocato`);
  }
  for (const runId of state.disabledRunIds) {
    if (!family.disabledRunIds.includes(runId)) {
      throw runtimeError("CAMS_FAMILY_REGRESSION", "la decisione CAMS perde una revoca osservata");
    }
  }
  if (!state.revision || sameCamsFamilyDecision(state, family)) return;
  if (family.revision <= state.revision || family.publishedAt < state.publishedAt) {
    throw runtimeError("CAMS_FAMILY_REGRESSION", "decisione family CAMS non monotona");
  }
  if (
    family.activeRunId < state.activeRunId
    && !family.disabledRunIds.includes(state.activeRunId)
  ) {
    throw runtimeError(
      "CAMS_FAMILY_REGRESSION",
      "rollback CAMS senza revoca del run sostituito",
    );
  }
}

function commitCamsFamilyDecisionToSession(state, family) {
  state.activeRunId = family.activeRunId;
  state.publishedAt = family.publishedAt;
  state.revision = family.revision;
  for (const runId of family.disabledRunIds) state.disabledRunIds.add(runId);
  state.familyEvidence = camsFamilyEvidenceFromDecision({
    ...family,
    disabledRunIds: [...state.disabledRunIds].sort(),
  });
  state.authorityError = null;
  return state;
}

function readPersistedCamsFamilyDecision({ baseUrl, storage }) {
  const target = normalizeStorage(storage);
  const key = getLocalWeatherV1CamsFamilyDecisionCacheKey({ baseUrl });
  if (!target || !key) return null;
  let serialized;
  try {
    serialized = target.getItem(key);
  } catch (cause) {
    throw runtimeError(
      "CAMS_REVOCATION_RESTORE_FAILED",
      "lettura del registro revoche CAMS non riuscita",
      cause,
    );
  }
  return serialized == null ? null : parseCamsFamilyDecisionRecord(serialized, baseUrl);
}

export function readLocalWeatherV1PersistedCamsFamilyDecision({ baseUrl, storage = null } = {}) {
  const decision = readPersistedCamsFamilyDecision({ baseUrl, storage });
  return decision ? camsFamilyEvidenceFromDecision(decision) : null;
}

function persistCamsFamilyDecision(family, { baseUrl, storage }) {
  const target = normalizeStorage(storage);
  const key = getLocalWeatherV1CamsFamilyDecisionCacheKey({ baseUrl });
  if (!target || !key) return false;
  let previousSerialized;
  try {
    previousSerialized = target.getItem(key);
  } catch (cause) {
    throw runtimeError(
      "CAMS_REVOCATION_PERSIST_FAILED",
      "lettura preliminare del registro revoche CAMS non riuscita",
      cause,
    );
  }
  if (previousSerialized != null) {
    try {
      const previous = parseCamsFamilyDecisionRecord(previousSerialized, baseUrl);
      const previousState = {
        activeRunId: previous.activeRunId,
        disabledRunIds: new Set(previous.disabledRunIds),
        publishedAt: previous.publishedAt,
        revision: previous.revision,
      };
      assertCamsFamilyTransition(previousState, family);
      if (sameCamsFamilyDecision(previousState, family)) return true;
    } catch (error) {
      // A newly verified server decision may repair a corrupt local journal.
      // Monotonic conflicts from a valid older record must still fail closed.
      if (error?.code !== "CAMS_REVOCATION_JOURNAL_INVALID") throw error;
    }
  }
  const serialized = serializeCamsFamilyDecision(family, baseUrl);
  try {
    target.setItem(key, serialized);
  } catch (cause) {
    try {
      if (target.getItem(key) === serialized) return true;
    } catch { /* The exact durable bytes could not be proven. */ }
    throw runtimeError(
      "CAMS_REVOCATION_PERSIST_FAILED",
      "scrittura del registro revoche CAMS non riuscita",
      cause,
    );
  }
  try {
    if (target.getItem(key) === serialized) return true;
  } catch (cause) {
    throw runtimeError(
      "CAMS_REVOCATION_PERSIST_FAILED",
      "rilettura del registro revoche CAMS non riuscita",
      cause,
    );
  }
  throw runtimeError(
    "CAMS_REVOCATION_PERSIST_FAILED",
    "il registro revoche CAMS non coincide dopo la scrittura",
  );
}

function sanitizeDisabledMemoryBundles(baseUrl, disabledRunIds, familyEvidence) {
  const scope = String(baseUrl || "").replace(/\/+$/, "");
  for (const [key, bundle] of retainedBundles) {
    const separator = key.indexOf("\n");
    const keyScope = key.slice(0, separator < 0 ? key.length : separator).replace(/\/+$/, "");
    if (keyScope === scope && disabledRunIds.has(camsRunIdFromBundle(bundle))) {
      retainedBundles.set(key, withoutRevokedCams(bundle, familyEvidence));
    }
  }
  for (const [key, record] of recentlyVerifiedBundles) {
    if (
      record.baseUrl === scope
      && disabledRunIds.has(camsRunIdFromBundle(record.bundle))
    ) {
      recentlyVerifiedBundles.set(key, {
        ...record,
        bundle: withoutRevokedCams(record.bundle, familyEvidence),
        camsVerifiedAt: null,
      });
    }
  }
}

function quarantineCamsMemoryBundles(baseUrl, error) {
  const scope = String(baseUrl || "").replace(/\/+$/, "");
  for (const [key, bundle] of retainedBundles) {
    const separator = key.indexOf("\n");
    const keyScope = key.slice(0, separator < 0 ? key.length : separator).replace(/\/+$/, "");
    if (keyScope === scope) {
      retainedBundles.set(key, withoutUnverifiableCamsAuthority(bundle, error));
    }
  }
  for (const [key, record] of recentlyVerifiedBundles) {
    if (record.baseUrl === scope) {
      recentlyVerifiedBundles.set(key, {
        ...record,
        bundle: withoutUnverifiableCamsAuthority(record.bundle, error),
        camsVerifiedAt: null,
      });
    }
  }
}

function sanitizePersistedCamsRecord(target, key, record, familyEvidence, candidate = false) {
  const sanitized = JSON.stringify({
    ...record,
    camsVerifiedAt: null,
    bundle: withoutRevokedCams(record.bundle, familyEvidence),
  });
  try {
    target.setItem(candidate ? `${key}:candidate` : key, sanitized);
    if (target.getItem(candidate ? `${key}:candidate` : key) === sanitized) return true;
  } catch {
    // A Web Storage replacement is atomic. If an implementation reports an
    // exception after committing, the exact readback still proves success.
    try {
      if (target.getItem(candidate ? `${key}:candidate` : key) === sanitized) return true;
    } catch { /* Fall through to fail-closed removal. */ }
  }
  return candidate
    ? discardPersistedCandidate(target, key)
    : false;
}

function sanitizeDisabledPersistedBundles(baseUrl, storage, disabledRunIds, familyEvidence) {
  const target = normalizeStorage(storage);
  if (!target) return true;
  cleanupLegacyPersistedBundles(target);
  const scope = sha256Hex(String(baseUrl || "").replace(/\/+$/, "")).slice(0, 16);
  const keyPrefix = `${LOCAL_WEATHER_V1_BUNDLE_CACHE_PREFIX}:${scope}:`;
  const keys = persistedBundleStorageKeys(target);
  const retained = [];
  let secured = true;
  for (const key of keys) {
    const activeExists = persistedRecordExists(target, key);
    if (!key.startsWith(keyPrefix)) {
      if (activeExists) retained.push(key);
      continue;
    }
    let record = null;
    let runId = null;
    try {
      record = JSON.parse(target.getItem(key));
      runId = camsRunIdFromBundle(record?.bundle);
    } catch {
      // Unknown/corrupt records are handled by the normal validated read path.
    }
    const candidateRecord = (() => {
      try {
        return JSON.parse(target.getItem(`${key}:candidate`));
      } catch {
        return null;
      }
    })();
    const deltaCandidate = candidateRecord?.kind === PERSISTED_CAMS_DELTA_KIND;
    const candidateRunId = deltaCandidate
      ? candidateRecord.cams_run_id
      : camsRunIdFromBundle(candidateRecord?.bundle);
    const recoverableDeltaCandidate = deltaCandidate
      && /^\d{8}T\d{6}Z$/.test(candidateRunId || "")
      && !disabledRunIds.has(candidateRunId)
      && candidateRunId === familyEvidence?.active_run_id;
    if (deltaCandidate && (!/^\d{8}T\d{6}Z$/.test(candidateRunId || "")
      || disabledRunIds.has(candidateRunId))) {
      secured = discardPersistedCandidate(target, key) && secured;
    } else if (candidateRunId && disabledRunIds.has(candidateRunId)) {
      secured = sanitizePersistedCamsRecord(target, key, candidateRecord, familyEvidence, true)
        && secured;
    }
    if (runId !== null && disabledRunIds.has(runId)) {
      if (!recoverableDeltaCandidate) {
        secured = sanitizePersistedCamsRecord(target, key, record, familyEvidence) && secured;
        if (deltaCandidate) secured = discardPersistedCandidate(target, key) && secured;
      }
    }
    if (activeExists && persistedRecordExists(target, key)) retained.push(key);
  }
  savePersistedBundleIndex(target, retained);
  return secured;
}

function restoreCamsFamilyDecision({ baseUrl, storage }) {
  const state = camsFamilyStateFor(baseUrl);
  let family;
  try {
    family = readPersistedCamsFamilyDecision({ baseUrl, storage });
  } catch (error) {
    if (![
      "CAMS_REVOCATION_JOURNAL_INVALID",
      "CAMS_REVOCATION_RESTORE_FAILED",
    ].includes(error?.code)) throw error;
    state.authorityError = error;
    state.durableRevision = 0;
    quarantineCamsMemoryBundles(baseUrl, error);
    return state;
  }
  if (!family) return state;
  if (state.revision > family.revision) {
    // A failed write can leave this session ahead of its last durable floor.
    // Re-reading that older journal must not roll the session back or make its
    // stricter in-memory quarantine unusable.
    if (family.disabledRunIds.some(runId => !state.disabledRunIds.has(runId))) {
      throw runtimeError(
        "CAMS_FAMILY_REGRESSION",
        "lo stato CAMS di sessione perde una revoca gia durevole",
      );
    }
    state.durableRevision = Math.max(state.durableRevision, family.revision);
    return state;
  }
  assertCamsFamilyTransition(state, family);
  commitCamsFamilyDecisionToSession(state, family);
  state.durableRevision = Math.max(state.durableRevision, family.revision);
  sanitizeDisabledMemoryBundles(baseUrl, state.disabledRunIds, state.familyEvidence);
  // The journal is the durable authority. Rewriting old bundle bytes is an
  // optimisation; every read applies the journal again if this best-effort
  // cleanup cannot be completed by the device store.
  sanitizeDisabledPersistedBundles(
    baseUrl,
    storage,
    state.disabledRunIds,
    state.familyEvidence,
  );
  return state;
}

function applyCamsFamilyDecision(family, { baseUrl, storage }) {
  restoreCamsFamilyDecision({ baseUrl, storage });
  const state = camsFamilyStateFor(baseUrl);
  const repairsAuthority = Boolean(state.authorityError);
  assertCamsFamilyTransition(state, family);
  commitCamsFamilyDecisionToSession(state, family);
  sanitizeDisabledMemoryBundles(baseUrl, state.disabledRunIds, state.familyEvidence);

  let persistenceError = null;
  if (family.disabledRunIds.length || repairsAuthority) {
    try {
      if (!persistCamsFamilyDecision(family, { baseUrl, storage })) {
        throw runtimeError(
          "CAMS_REVOCATION_PERSIST_FAILED",
          "storage durevole per le revoche CAMS non disponibile",
        );
      }
      state.durableRevision = Math.max(state.durableRevision, family.revision);
    } catch (error) {
      persistenceError = error;
    }
  }
  const persistedBundlesSecured = sanitizeDisabledPersistedBundles(
    baseUrl,
    storage,
    state.disabledRunIds,
    state.familyEvidence,
  );
  if (persistenceError) throw persistenceError;
  if (!persistedBundlesSecured && state.durableRevision < family.revision) {
    throw runtimeError(
      "CACHE_INVALIDATION_FAILED",
      "impossibile mettere in sicurezza tutti i bundle CAMS revocati",
    );
  }
  return state;
}

function observeVerifiedCamsFamilyDecision(latest, options) {
  const family = camsFamilyDecisionFromLatestSnapshot(latest);
  if (!family) {
    throw runtimeError("INVALID_DOCUMENT", "decisione family CAMS verificata non valida");
  }
  return applyCamsFamilyDecision(family, options);
}

function observeCamsFamily(bundle, options) {
  const family = camsFamilyDecision(bundle);
  if (!family) return camsFamilyStateFor(options.baseUrl);
  return applyCamsFamilyDecision(family, options);
}

function assertBundleCamsEnabled(bundle, state) {
  const runId = camsRunIdFromBundle(bundle);
  if (runId && state.authorityError) {
    throw runtimeError(
      state.authorityError.code || "CAMS_REVOCATION_RESTORE_FAILED",
      "stato delle revoche CAMS non verificabile",
      state.authorityError,
    );
  }
  if (runId && state.disabledRunIds.has(runId)) {
    throw runtimeError("RUN_DISABLED", `il run CAMS ${runId} e stato revocato`);
  }
}

function isQuotaExceeded(error) {
  const name = String(error?.name || "").toLocaleLowerCase("en");
  const message = String(error?.message || "").toLocaleLowerCase("en");
  return name.includes("quota")
    || message.includes("quota")
    || error?.code === 22
    || error?.code === 1014;
}

function discardPersistedBundle(storage, key) {
  if (!isPersistedBundleKey(key)) return false;
  try {
    storage?.removeItem(key);
    return true;
  } catch {
    try {
      // A logical tombstone prevents a revoked bundle from being rehydrated
      // after a remount when removeItem alone is blocked by the device store.
      storage?.setItem(key, "null");
      return true;
    } catch {
      return false;
    }
  }
}

function discardPersistedCandidate(storage, key) {
  const candidateKey = `${key}:candidate`;
  try {
    storage?.removeItem(candidateKey);
    return true;
  } catch {
    try {
      storage?.setItem(candidateKey, "null");
      return true;
    } catch {
      return false;
    }
  }
}

function evictOldestPersistedBundle(storage, keys, protectedKey = null) {
  const candidateIndex = keys.findIndex((key) => key !== protectedKey);
  if (candidateIndex < 0) return null;
  const [key] = keys.splice(candidateIndex, 1);
  discardPersistedBundle(storage, key);
  discardPersistedCandidate(storage, key);
  return key;
}

function savePersistedBundleIndex(storage, keys, protectedKey = null) {
  const save = () => storage.setItem(
    LOCAL_WEATHER_V1_BUNDLE_CACHE_INDEX_KEY,
    JSON.stringify({
      version: PERSISTED_BUNDLE_VERSION,
      keys,
    }),
  );
  try {
    save();
    return true;
  } catch (error) {
    if (!isQuotaExceeded(error)) return false;
    evictOldestPersistedBundle(storage, keys, protectedKey);
    try {
      save();
      return true;
    } catch {
      return false;
    }
  }
}

function touchPersistedBundle(storage, key) {
  if (!isPersistedBundleKey(key)) return false;
  const keys = readPersistedBundleIndex(storage).filter((candidate) => candidate !== key);
  keys.push(key);
  while (keys.length > MAX_RETAINED_BUNDLES) {
    evictOldestPersistedBundle(storage, keys, key);
  }
  return savePersistedBundleIndex(storage, keys, key);
}

function touchPersistedBundleWithoutEviction(storage, key) {
  if (!isPersistedBundleKey(key)) return false;
  const keys = readPersistedBundleIndex(storage).filter(candidate => candidate !== key);
  keys.push(key);
  if (keys.length > MAX_RETAINED_BUNDLES) return false;
  try {
    storage.setItem(LOCAL_WEATHER_V1_BUNDLE_CACHE_INDEX_KEY, JSON.stringify({
      version: PERSISTED_BUNDLE_VERSION,
      keys,
    }));
    return true;
  } catch {
    // The active record remains discoverable by storage enumeration and was
    // already indexed before a CAMS-only replacement. Never evict another
    // municipality merely to reorder the LRU after a successful promotion.
    return false;
  }
}

function exactObjectKeys(value, expected) {
  return value && typeof value === "object" && !Array.isArray(value)
    && Object.keys(value).sort().join("\n") === [...expected].sort().join("\n");
}

function canonicalValue(value) {
  if (Array.isArray(value)) return value.map(canonicalValue);
  if (!value || typeof value !== "object") return value;
  return Object.fromEntries(Object.keys(value).sort().map(key => [key, canonicalValue(value[key])]));
}

function canonicalJson(value) {
  return JSON.stringify(canonicalValue(value));
}

function camsDataQuality(value) {
  const quality = {};
  for (const field of CAMS_QUALITY_FIELDS) {
    if (!Object.hasOwn(value?.data_quality || {}, field)) return null;
    quality[field] = value.data_quality[field];
  }
  if (!Array.isArray(value?.data_quality?.flags)
    || !Array.isArray(value?.data_quality?.capability_gaps)) return null;
  quality.flags = value.data_quality.flags.filter(flag => String(flag).startsWith("cams_"));
  quality.capability_gaps = value.data_quality.capability_gaps
    .filter(gap => String(gap).startsWith("cams_"));
  return quality;
}

function camsValueDomain(value, current = false) {
  const quality = camsDataQuality(value);
  if (!quality || typeof value?.source?.status !== "string"
    || typeof value?.source?.label !== "string"
    || !value.source.cams || typeof value.source.cams !== "object"
    || typeof value?.model_support?.cams !== "boolean") return null;
  const common = {
    source: {
      status: value.source.status,
      label: value.source.label,
      cams: value.source.cams,
    },
    model_support_cams: value.model_support.cams,
    data_quality: quality,
  };
  if (!current) return common;
  if (!Object.hasOwn(value, "pollen")
    || !Object.hasOwn(value, "pollen_data")
    || !Object.hasOwn(value, "air_quality_data")
    || !Object.hasOwn(value, "cams_hourly_cache")) return null;
  return {
    ...common,
    pollen: value.pollen,
    pollen_data: value.pollen_data,
    air_quality_data: value.air_quality_data,
    cams_hourly_cache: value.cams_hourly_cache,
  };
}

function camsBundleDomain(bundle) {
  const current = camsValueDomain(bundle?.current, true);
  const forecast = camsValueDomain(bundle?.forecast);
  return current && forecast ? { current, forecast } : null;
}

function applyCamsValueDomain(value, domain, current = false) {
  const mergeCamsSet = (existing, incoming, { sorted = true } = {}) => {
    const merged = [...new Set([
      ...(existing || []).filter(item => !String(item).startsWith("cams_")),
      ...incoming,
    ])];
    return sorted ? merged.sort() : merged;
  };
  const result = {
    ...value,
    source: {
      ...value.source,
      status: domain.source.status,
      label: domain.source.label,
      cams: domain.source.cams,
    },
    model_support: { ...value.model_support, cams: domain.model_support_cams },
    data_quality: {
      ...value.data_quality,
      ...domain.data_quality,
      flags: mergeCamsSet(value.data_quality?.flags, domain.data_quality.flags),
      capability_gaps: mergeCamsSet(
        value.data_quality?.capability_gaps,
        domain.data_quality.capability_gaps,
        { sorted: false },
      ),
    },
  };
  if (!current) return result;
  result.pollen = domain.pollen;
  result.pollen_data = domain.pollen_data;
  result.air_quality_data = domain.air_quality_data;
  result.cams_hourly_cache = domain.cams_hourly_cache;
  return result;
}

function applyCamsBundleDomain(bundle, domain) {
  return {
    ...bundle,
    current: applyCamsValueDomain(bundle.current, domain.current, true),
    forecast: applyCamsValueDomain(bundle.forecast, domain.forecast),
  };
}

function validCamsDeltaValueDomain(value, current = false) {
  const expected = ["source", "model_support_cams", "data_quality"];
  if (current) expected.push("pollen", "pollen_data", "air_quality_data", "cams_hourly_cache");
  return exactObjectKeys(value, expected)
    && exactObjectKeys(value.source, ["status", "label", "cams"])
    && typeof value.source.status === "string"
    && typeof value.source.label === "string"
    && value.source.cams && typeof value.source.cams === "object" && !Array.isArray(value.source.cams)
    && typeof value.model_support_cams === "boolean"
    && exactObjectKeys(value.data_quality, [...CAMS_QUALITY_FIELDS, "flags", "capability_gaps"])
    && [value.data_quality.flags, value.data_quality.capability_gaps].every(items => (
      Array.isArray(items)
      && items.every(item => typeof item === "string" && item.startsWith("cams_")
        && item.trim() === item && item.length > 5)
      && items.every((item, index) => index === 0 || items[index - 1] < item)
    ));
}

function validCamsDeltaDomain(domain) {
  return exactObjectKeys(domain, ["current", "forecast"])
    && validCamsDeltaValueDomain(domain.current, true)
    && validCamsDeltaValueDomain(domain.forecast);
}

function buildCamsDeltaCandidate(base, targetRecord, location, options) {
  const baseRecord = base?.record;
  const baseBundle = baseRecord?.bundle;
  const targetBundle = targetRecord?.bundle;
  const domain = camsBundleDomain(targetBundle);
  const baseIconIdentity = iconObjectIdentity(baseBundle);
  const targetIconIdentity = iconObjectIdentity(targetBundle);
  const familyIdentity = camsFamilyEvidenceIdentity(targetBundle);
  const runId = camsRunIdFromBundle(targetBundle);
  const targetCache = readVerifiedCamsHourlyCache(targetBundle);
  const targetPrepared = prepareRetainedBundle(targetBundle, options.now, location);
  if (!domain || !validCamsDeltaDomain(domain)
    || targetCache?.stored?.version !== 2
    || !baseIconIdentity || baseIconIdentity !== targetIconIdentity
    || !familyIdentity || !runId
    || baseRecord.municipality !== targetRecord.municipality
    || baseRecord.municipality !== municipalityIdentity(location)
    || !Number.isFinite(baseRecord.verifiedAt)
    || !Number.isFinite(targetRecord.verifiedAt)
    || targetRecord.verifiedAt < baseRecord.verifiedAt
    || !Number.isFinite(targetRecord.camsVerifiedAt)
    || (Number.isFinite(baseRecord.camsVerifiedAt)
      && targetRecord.camsVerifiedAt < baseRecord.camsVerifiedAt)
    || !targetPrepared) return null;
  const reconstructed = {
    version: PERSISTED_BUNDLE_VERSION,
    municipality: targetRecord.municipality,
    verifiedAt: targetRecord.verifiedAt,
    camsVerifiedAt: targetRecord.camsVerifiedAt,
    bundle: applyCamsBundleDomain(baseBundle, domain),
  };
  const reconstructedPrepared = prepareRetainedBundle(reconstructed.bundle, options.now, location);
  const preferred = reconstructedPrepared
    ? preferredCamsBundle(base.prepared, reconstructedPrepared, options.now)
    : null;
  const preferredCache = readVerifiedCamsHourlyCache(preferred);
  if (!reconstructedPrepared
    || !hasRetainableCams(reconstructedPrepared, options.now)
    || canonicalJson(reconstructedPrepared) !== canonicalJson(targetPrepared)
    || camsRunIdFromBundle(preferred) !== runId
    || canonicalJson(preferredCache?.stored) !== canonicalJson(targetCache.stored)) return null;
  const reconstructedSerialized = JSON.stringify(reconstructed);
  const payload = {
    kind: PERSISTED_CAMS_DELTA_KIND,
    version: PERSISTED_CAMS_DELTA_VERSION,
    municipality: targetRecord.municipality,
    catalog_sha256: EXPECTED_CATALOG_SHA256,
    base_record_sha256: sha256Hex(base.serialized),
    target_record_sha256: sha256Hex(reconstructedSerialized),
    icon_identity_sha256: sha256Hex(baseIconIdentity),
    cams_family_identity_sha256: sha256Hex(familyIdentity),
    cams_run_id: runId,
    verifiedAt: targetRecord.verifiedAt,
    camsVerifiedAt: targetRecord.camsVerifiedAt,
    domain,
  };
  return {
    record: { ...payload, sha256: sha256Hex(JSON.stringify(payload)) },
    reconstructed,
    serialized: reconstructedSerialized,
  };
}

function readPreparedPersistedRecord(target, key, location, options, familyState) {
  let serialized;
  let record;
  try {
    serialized = target.getItem(key);
    record = JSON.parse(serialized);
  } catch {
    return null;
  }
  if (!record
    || typeof record !== "object"
    || record.version !== PERSISTED_BUNDLE_VERSION
    || record.municipality !== municipalityIdentity(location)
    || !Object.hasOwn(record.bundle?.current || {}, "air_quality_data")) return null;
  const authorityError = familyState?.authorityError;
  const revokedRun = familyState?.disabledRunIds.has(camsRunIdFromBundle(record?.bundle));
  if (authorityError) {
    record = {
      ...record,
      camsVerifiedAt: null,
      bundle: withoutUnverifiableCamsAuthority(record.bundle, authorityError),
    };
    serialized = JSON.stringify(record);
  } else if (revokedRun && familyState?.familyEvidence) {
    record = {
      ...record,
      camsVerifiedAt: null,
      bundle: withoutRevokedCams(record.bundle, familyState.familyEvidence),
    };
    serialized = JSON.stringify(record);
  }
  const prepared = prepareRetainedBundle(record?.bundle, options.now, location);
  if (iconFamilyStateFor(options.baseUrl).disabledRunIds.has(iconRunIdFromBundle(record.bundle))
    || !prepared) return null;
  return { prepared, record, serialized };
}

function readPreparedCamsDeltaRecord(serialized, base, location, options) {
  let record;
  try {
    record = JSON.parse(serialized);
  } catch {
    return null;
  }
  if (!exactObjectKeys(record, [
    "kind", "version", "municipality", "catalog_sha256", "base_record_sha256",
    "target_record_sha256", "icon_identity_sha256", "cams_family_identity_sha256",
    "cams_run_id", "verifiedAt", "camsVerifiedAt", "domain", "sha256",
  ]) || record.kind !== PERSISTED_CAMS_DELTA_KIND
    || record.version !== PERSISTED_CAMS_DELTA_VERSION
    || record.municipality !== municipalityIdentity(location)
    || record.catalog_sha256 !== EXPECTED_CATALOG_SHA256
    || !/^[0-9a-f]{64}$/.test(record.base_record_sha256)
    || !/^[0-9a-f]{64}$/.test(record.target_record_sha256)
    || !/^[0-9a-f]{64}$/.test(record.icon_identity_sha256)
    || !/^[0-9a-f]{64}$/.test(record.cams_family_identity_sha256)
    || !/^\d{8}T\d{6}Z$/.test(record.cams_run_id)
    || !Number.isFinite(record.verifiedAt) || record.verifiedAt < 0
    || !Number.isFinite(record.camsVerifiedAt) || record.camsVerifiedAt < 0
    || !Number.isFinite(base.record.verifiedAt) || base.record.verifiedAt < 0
    || record.verifiedAt < base.record.verifiedAt
    || (Number.isFinite(base.record.camsVerifiedAt)
      && record.camsVerifiedAt < base.record.camsVerifiedAt)
    || !validCamsDeltaDomain(record.domain)
    || !/^[0-9a-f]{64}$/.test(record.sha256)) return null;
  const { sha256, ...payload } = record;
  if (sha256Hex(JSON.stringify(payload)) !== sha256
    || record.base_record_sha256 !== sha256Hex(base.serialized)) return null;
  const baseBundle = base.record.bundle;
  const iconIdentity = iconObjectIdentity(baseBundle);
  if (!iconIdentity || record.icon_identity_sha256 !== sha256Hex(iconIdentity)) return null;
  const reconstructed = {
    version: PERSISTED_BUNDLE_VERSION,
    municipality: record.municipality,
    verifiedAt: record.verifiedAt,
    camsVerifiedAt: record.camsVerifiedAt,
    bundle: applyCamsBundleDomain(baseBundle, record.domain),
  };
  const familyIdentity = camsFamilyEvidenceIdentity(reconstructed.bundle);
  const cache = readVerifiedCamsHourlyCache(reconstructed.bundle);
  const reconstructedPrepared = prepareRetainedBundle(reconstructed.bundle, options.now, location);
  const preferred = reconstructedPrepared
    ? preferredCamsBundle(base.prepared, reconstructedPrepared, options.now)
    : null;
  const preferredCache = readVerifiedCamsHourlyCache(preferred);
  if (!familyIdentity
    || record.cams_family_identity_sha256 !== sha256Hex(familyIdentity)
    || record.cams_run_id !== camsRunIdFromBundle(reconstructed.bundle)
    || record.target_record_sha256 !== sha256Hex(JSON.stringify(reconstructed))
    || canonicalJson(camsBundleDomain(reconstructed.bundle)) !== canonicalJson(record.domain)
    || cache?.stored?.version !== 2
    || !reconstructedPrepared
    || !hasRetainableCams(reconstructedPrepared, options.now)
    || camsRunIdFromBundle(preferred) !== record.cams_run_id
    || canonicalJson(preferredCache?.stored) !== canonicalJson(cache.stored)) return null;
  try {
    assertBundleIconEnabled(reconstructed.bundle, options.baseUrl);
    assertBundleCamsEnabled(reconstructed.bundle, camsFamilyStateFor(options.baseUrl));
  } catch {
    return null;
  }
  return {
    reconstructed,
    prepared: reconstructedPrepared,
    serialized: JSON.stringify(reconstructed),
  };
}

function writePersistedCamsDelta(target, key, candidateKey, targetRecord, location, options) {
  // A delta is one atomic validation decision. Freeze the wall clock so the
  // independently prepared target and reconstruction cannot diverge merely
  // because Date.now advanced between integrity checks.
  const evaluatedAt = clockMilliseconds(options.now);
  if (!Number.isFinite(evaluatedAt)) return null;
  const stableOptions = { ...options, now: evaluatedAt };
  const familyState = camsFamilyStateFor(options.baseUrl);
  const base = readPreparedPersistedRecord(target, key, location, stableOptions, familyState);
  const delta = base ? buildCamsDeltaCandidate(base, targetRecord, location, stableOptions) : null;
  if (!delta) return null;
  const deltaSerialized = JSON.stringify(delta.record);
  try {
    target.setItem(candidateKey, deltaSerialized);
  } catch {
    return false;
  }
  try {
    if (target.getItem(candidateKey) !== deltaSerialized) {
      discardPersistedCandidate(target, key);
      return false;
    }
  } catch {
    discardPersistedCandidate(target, key);
    return false;
  }

  const readVerifiedDelta = () => {
    const latestBase = readPreparedPersistedRecord(target, key, location, stableOptions, familyState);
    if (!latestBase || sha256Hex(latestBase.serialized) !== delta.record.base_record_sha256) {
      return null;
    }
    let staged;
    try { staged = target.getItem(candidateKey); } catch { return null; }
    if (staged !== deltaSerialized) return null;
    return readPreparedCamsDeltaRecord(staged, latestBase, location, stableOptions);
  };
  let verified = readVerifiedDelta();
  if (!verified) {
    discardPersistedCandidate(target, key);
    return false;
  }
  const activeMatches = () => {
    try { return target.getItem(key) === verified.serialized; } catch { return false; }
  };
  try {
    target.setItem(key, verified.serialized);
  } catch (error) {
    if (!activeMatches()) {
      if (!isQuotaExceeded(error)) {
        discardPersistedCandidate(target, key);
        return false;
      }
      // Keeping both the full replacement and the delta may itself exceed the
      // device quota. Remove only the fully verified delta, prove that the
      // byte-identical base is still active, then retry the atomic replacement.
      if (!discardPersistedCandidate(target, key)) return false;
      const latestBase = readPreparedPersistedRecord(target, key, location, stableOptions, familyState);
      if (!latestBase || sha256Hex(latestBase.serialized) !== delta.record.base_record_sha256) {
        return false;
      }
      verified = readPreparedCamsDeltaRecord(deltaSerialized, latestBase, location, stableOptions);
      if (!verified) return false;
      try {
        target.setItem(key, verified.serialized);
      } catch {
        if (!activeMatches()) return false;
      }
    }
  }
  if (!activeMatches()) {
    discardPersistedCandidate(target, key);
    return false;
  }
  try { target.removeItem(candidateKey); } catch { /* The inactive delta remains harmless. */ }
  touchPersistedBundleWithoutEviction(target, key);
  return true;
}

function readPersistedBundle(location, { baseUrl, now, storage }, familyState = null) {
  const target = normalizeStorage(storage);
  const key = getLocalWeatherV1BundleCacheKey(location, { baseUrl });
  if (!target || !key) return null;
  cleanupLegacyPersistedBundles(target);
  const options = { baseUrl, now, storage };
  const candidateKey = `${key}:candidate`;
  restoreIconRevocations({ baseUrl, storage });
  const restoredFamilyState = restoreCamsFamilyDecision({ baseUrl, storage });
  const effectiveFamilyState = familyState || restoredFamilyState;
  try {
    if (!effectiveFamilyState.authorityError) {
      let deltaSerialized = null;
      try {
        const serialized = target.getItem(candidateKey);
        if (JSON.parse(serialized)?.kind === PERSISTED_CAMS_DELTA_KIND) {
          deltaSerialized = serialized;
        }
      } catch {
        // The normal candidate path below will discard an unreadable record.
      }
      if (deltaSerialized
        && effectiveFamilyState.durableRevision >= effectiveFamilyState.revision
        && effectiveFamilyState.revision > 0) {
        // The delta is integrity-bound to the exact pre-promotion active bytes.
        // Try both the raw base and its journal-filtered representation: the
        // revocation cleanup may have completed just before the process stopped.
        const rawDeltaBase = readPreparedPersistedRecord(
          target,
          key,
          location,
          options,
          null,
        );
        const filteredDeltaBase = readPreparedPersistedRecord(
          target,
          key,
          location,
          options,
          effectiveFamilyState,
        );
        const bases = [rawDeltaBase, filteredDeltaBase].filter((base, index, values) => (
          base && values.findIndex(candidate => candidate?.serialized === base.serialized) === index
        ));
        const recoveredDelta = bases
          .map(base => readPreparedCamsDeltaRecord(deltaSerialized, base, location, options))
          .find(Boolean) || null;
        const rawBaseRunId = camsRunIdFromBundle(rawDeltaBase?.record?.bundle);
        const rawBaseDecision = camsFamilyDecision(rawDeltaBase?.record?.bundle);
        const baseWasRevokedOrSanitized = effectiveFamilyState.disabledRunIds.has(rawBaseRunId)
          || (!rawBaseRunId && rawBaseDecision
            && sameCamsFamilyDecision(effectiveFamilyState, rawBaseDecision));
        const candidateFamily = camsFamilyDecision(recoveredDelta?.reconstructed?.bundle);
        const currentReplacement = recoveredDelta
          && baseWasRevokedOrSanitized
          && candidateFamily
          && candidateFamily.activeRunId === effectiveFamilyState.activeRunId
          && sameCamsFamilyDecision(effectiveFamilyState, candidateFamily);
        if (currentReplacement) {
          let promoted = false;
          try {
            target.setItem(key, recoveredDelta.serialized);
            promoted = target.getItem(key) === recoveredDelta.serialized;
          } catch {
            try { promoted = target.getItem(key) === recoveredDelta.serialized; } catch { /* Keep staging. */ }
          }
          if (promoted) {
            try { target.removeItem(candidateKey); } catch { /* Inactive delta remains harmless. */ }
            touchPersistedBundle(target, key);
          }
          return recoveredDelta.prepared;
        }
        discardPersistedCandidate(target, key);
        if (rawDeltaBase && effectiveFamilyState.disabledRunIds.has(rawBaseRunId)) {
          sanitizePersistedCamsRecord(
            target,
            key,
            rawDeltaBase.record,
            effectiveFamilyState.familyEvidence,
          );
        }
      }
    }
    const active = readPreparedPersistedRecord(
      target,
      key,
      location,
      options,
      effectiveFamilyState,
    );
    if (effectiveFamilyState.authorityError) {
      if (active) return active.prepared;
      return readPreparedPersistedRecord(
        target,
        candidateKey,
        location,
        options,
        effectiveFamilyState,
      )?.prepared || null;
    }
    if (active) {
      try { target.removeItem(candidateKey); } catch { /* Inactive complete staging data is harmless. */ }
      touchPersistedBundle(target, key);
      return active.prepared;
    }
    if (target.getItem(key) !== null) discardPersistedBundle(target, key);
    const candidate = readPreparedPersistedRecord(
      target,
      candidateKey,
      location,
      options,
      effectiveFamilyState,
    );
    if (!candidate) {
      try { target.removeItem(candidateKey); } catch { /* Invalid staging data is never read as active. */ }
      return null;
    }
    try {
      target.setItem(key, candidate.serialized);
      if (target.getItem(key) === candidate.serialized) {
        target.removeItem(candidateKey);
        touchPersistedBundle(target, key);
      }
    } catch {
      // The separately saved and fully validated candidate remains recoverable.
    }
    return candidate.prepared;
  } catch {
    return null;
  }
}

export function readLocalWeatherV1PersistedBundle(
  location,
  {
    baseUrl,
    now = Date.now,
    storage = null,
  } = {},
) {
  return readPersistedBundle(
    location,
    { baseUrl, now, storage },
    camsFamilyStateFor(baseUrl),
  );
}

function writePersistedBundle(
  bundle,
  location,
  { baseUrl, storage, now, verificationNow, iconVerifiedAt, camsVerifiedAt },
) {
  const target = normalizeStorage(storage);
  const key = getLocalWeatherV1BundleCacheKey(location, { baseUrl });
  if (!target || !key) return null;
  if (camsFamilyStateFor(baseUrl).disabledRunIds.has(camsRunIdFromBundle(bundle))) return false;
  if (iconFamilyStateFor(baseUrl).disabledRunIds.has(iconRunIdFromBundle(bundle))) return false;
  cleanupLegacyPersistedBundles(target);
  const targetRecord = {
    version: PERSISTED_BUNDLE_VERSION,
    municipality: municipalityIdentity(location),
    verifiedAt: iconVerifiedAt ?? clockMilliseconds(verificationNow),
    camsVerifiedAt: camsVerifiedAt ?? null,
    bundle,
  };
  const serialized = JSON.stringify(targetRecord);
  const candidateKey = `${key}:candidate`;
  const saveCandidate = () => target.setItem(candidateKey, serialized);
  try {
    saveCandidate();
  } catch (error) {
    if (!isQuotaExceeded(error)) return false;
    const deltaResult = writePersistedCamsDelta(
      target,
      key,
      candidateKey,
      targetRecord,
      location,
      { baseUrl, storage, now },
    );
    if (deltaResult !== null) return deltaResult;
    const keys = readPersistedBundleIndex(target);
    if (!evictOldestPersistedBundle(target, keys, key)) return false;
    savePersistedBundleIndex(target, keys, key);
    try {
      saveCandidate();
    } catch {
      return false;
    }
  }
  try {
    if (target.getItem(candidateKey) !== serialized
      || JSON.parse(target.getItem(candidateKey))?.municipality !== municipalityIdentity(location)) return false;
  } catch {
    return false;
  }
  const commit = () => target.setItem(key, serialized);
  try {
    commit();
  } catch (error) {
    if (!isQuotaExceeded(error)) return false;
    try { target.removeItem(candidateKey); } catch { return false; }
    try {
      commit();
    } catch (retryError) {
      if (!isQuotaExceeded(retryError)) return false;
      const keys = readPersistedBundleIndex(target);
      if (!evictOldestPersistedBundle(target, keys, key)) return false;
      savePersistedBundleIndex(target, keys, key);
      try { commit(); } catch { return false; }
    }
  }
  try {
    if (target.getItem(key) !== serialized) return false;
  } catch {
    return false;
  }
  try { target.removeItem(candidateKey); } catch { /* A complete inactive copy is harmless. */ }
  touchPersistedBundle(target, key);
  return true;
}

function withRuntimeFallback(bundle, source, { code = null, flag = null } = {}) {
  const fallbackFlag = "runtime_refresh_failed_bundle_retained";
  const decorate = (value) => ({
    ...value,
    cache: {
      ...value?.cache,
      runtime_fallback: true,
      runtime_fallback_source: source,
      ...(code ? { runtime_fallback_code: code } : {}),
    },
    data_quality: {
      ...value?.data_quality,
      flags: [...new Set([
        ...(value?.data_quality?.flags || []),
        fallbackFlag,
        ...(flag ? [flag] : []),
      ])].sort(),
    },
  });
  return {
    ...bundle,
    current: decorate(bundle.current),
    forecast: decorate(bundle.forecast),
  };
}

function candidateCommitFailure(bundle) {
  return {
    code: "CACHE_PERSIST_FAILED",
    iconObject: iconObjectIdentity(bundle),
    iconRun: iconRunIdFromBundle(bundle),
  };
}

function committedBundleCoversFailure(bundle, failure) {
  if (!failure) return true;
  const runId = iconRunIdFromBundle(bundle);
  if (!runId || !failure.iconRun) return false;
  if (runId > failure.iconRun) return true;
  return runId === failure.iconRun
    && iconObjectIdentity(bundle) === failure.iconObject;
}

function withCandidateCommitDiagnostic(key, bundle) {
  const failure = candidateCommitFailures.get(key);
  return failure
    ? withRuntimeFallback(bundle, "candidate_not_committed", {
      code: failure.code,
      flag: "runtime_candidate_not_committed",
    })
    : bundle;
}

function remember(key, bundle) {
  retainedBundles.delete(key);
  retainedBundles.set(key, bundle);
  while (retainedBundles.size > MAX_RETAINED_BUNDLES) {
    const oldest = retainedBundles.keys().next().value;
    retainedBundles.delete(oldest);
    candidateCommitFailures.delete(oldest);
  }
}

function rememberVerified(key, bundle, { baseUrl, verificationNow, iconVerifiedAt, camsVerifiedAt }) {
  const verifiedAt = iconVerifiedAt ?? clockMilliseconds(verificationNow);
  if (!Number.isFinite(verifiedAt)) return;
  recentlyVerifiedBundles.delete(key);
  recentlyVerifiedBundles.set(key, {
    baseUrl: String(baseUrl || "").replace(/\/+$/, ""),
    bundle,
    verifiedAt,
    camsVerifiedAt: camsVerifiedAt ?? null,
  });
  while (recentlyVerifiedBundles.size > MAX_RETAINED_BUNDLES) {
    recentlyVerifiedBundles.delete(recentlyVerifiedBundles.keys().next().value);
  }
}

function readRecentlyVerifiedBundle(key, location, options) {
  if (options.verifyWindowMs <= 0) return null;
  let record = recentlyVerifiedBundles.get(key);
  if (!record) {
    const bundle = readPersistedBundle(location, options, camsFamilyStateFor(options.baseUrl));
    try {
      const persisted = JSON.parse(normalizeStorage(options.storage)?.getItem(
        getLocalWeatherV1BundleCacheKey(location, options),
      ));
      if (bundle && Number.isFinite(persisted?.verifiedAt)) {
        record = { bundle, verifiedAt: persisted.verifiedAt, camsVerifiedAt: persisted.camsVerifiedAt ?? null,
          originalValidAt: persisted.bundle?.current?.data_quality?.valid_at_utc };
      }
    } catch { /* Missing or damaged verification metadata requires a check. */ }
  }
  if (!record) return null;
  if (record.bundle?.forecast?.daily_extrema_version !== 2) return null;
  const current = clockMilliseconds(options.verificationNow);
  const elapsed = current - record.verifiedAt;
  const familyState = camsFamilyStateFor(options.baseUrl);
  const prepared = prepareRetainedBundle(record.bundle, options.now, location);
  if (
    !Number.isFinite(current)
    || elapsed < 0
    || elapsed >= options.verifyWindowMs
    || !prepared
    || prepared.current.data_quality.valid_at_utc !== (record.originalValidAt ?? record.bundle.current.data_quality.valid_at_utc)
    || record.bundle?.current?.data_quality?.cams_status === "pending"
    || familyState.disabledRunIds.has(camsRunIdFromBundle(record.bundle))
    || iconFamilyStateFor(options.baseUrl).disabledRunIds.has(iconRunIdFromBundle(record.bundle))
  ) {
    recentlyVerifiedBundles.delete(key);
    return null;
  }
  recentlyVerifiedBundles.delete(key);
  recentlyVerifiedBundles.set(key, record);
  return { bundle: prepared, verifiedAt: record.verifiedAt, camsVerifiedAt: record.camsVerifiedAt ?? null };
}

function readPersistedVerificationMetadata(location, options) {
  const target = normalizeStorage(options.storage);
  const key = getLocalWeatherV1BundleCacheKey(location, options);
  if (!target || !key) return null;
  try {
    const record = JSON.parse(target.getItem(key));
    if (record?.version !== PERSISTED_BUNDLE_VERSION
      || record.municipality !== municipalityIdentity(location)) return null;
    return {
      verifiedAt: Number.isFinite(record.verifiedAt) ? record.verifiedAt : null,
      camsVerifiedAt: Number.isFinite(record.camsVerifiedAt) ? record.camsVerifiedAt : null,
    };
  } catch {
    return null;
  }
}

function selectedIncomingCams(selected, incoming, now) {
  return hasUsableCams(incoming, now)
    && hasRetainableCams(selected, now)
    && camsFamilyEvidenceIdentity(selected) === camsFamilyEvidenceIdentity(incoming)
    && selected.current.data_quality.cams_run_utc === incoming.current.data_quality.cams_run_utc
    && selected.current.data_quality.cams_valid_at_utc === incoming.current.data_quality.cams_valid_at_utc;
}

function selectedIncomingIcon(selected, incoming) {
  const selectedIdentity = iconObjectIdentity(selected);
  return selectedIdentity !== null
    && selectedIdentity === iconObjectIdentity(incoming)
    && selected.current.data_quality.run_utc === incoming.current.data_quality.run_utc
    && selected.current.data_quality.valid_at_utc === incoming.current.data_quality.valid_at_utc;
}

function selectVerifiedBundle(key, verificationKey, incoming, location, options) {
  assertBundleIconEnabled(incoming, options.baseUrl);
  const familyState = observeCamsFamily(incoming, options);
  assertBundleCamsEnabled(incoming, familyState);
  const memory = retainedBundles.get(key);
  const persisted = readPersistedBundle(location, options, familyState);
  let selected = !familyState.disabledRunIds.has(camsRunIdFromBundle(memory))
    && !iconFamilyStateFor(options.baseUrl).disabledRunIds.has(iconRunIdFromBundle(memory))
    ? prepareRetainedBundle(memory, options.now, location) : null;
  selected = preferBundle(selected, persisted, options.now);
  const previousActive = selected;
  const preparedIncoming = prepareIncomingBundle(incoming, options.now, location);
  // Applying an authoritative family decision (including revocations) is
  // independent from accepting this candidate as a complete ICON bundle. A
  // broken candidate must still make the refresh fail, while the sanitation
  // performed above leaves the previous active ICON available for a later read.
  if (!preparedIncoming) throw runtimeError("ICON_BUNDLE_UNUSABLE", "Dati meteo incompleti");
  selected = preferBundle(selected, preparedIncoming, options.now);
  if (!selected) throw runtimeError("ICON_BUNDLE_UNUSABLE", "Dati meteo incompleti");
  const iconFromIncoming = preparedIncoming && selectedIncomingIcon(selected, preparedIncoming);
  const camsFromIncoming = preparedIncoming
    && selectedIncomingCams(selected, preparedIncoming, options.now);
  const iconVerified = iconFromIncoming
    && options.iconVerifiedAt === undefined
    && !incoming.current?.source?.icon?.evidence?.network_fallback;
  const camsVerified = camsFromIncoming
    && !incoming.current?.source?.cams?.evidence?.network_fallback;
  const candidateChangesActive = Boolean(preparedIncoming && selected !== previousActive);
  if (candidateChangesActive || iconVerified || camsVerified) {
    const previous = recentlyVerifiedBundles.get(verificationKey)
      || readPersistedVerificationMetadata(location, options);
    const verifiedAt = clockMilliseconds(options.verificationNow);
    const metadata = {
      ...options,
      iconVerifiedAt: iconVerified
        ? verifiedAt
        : options.iconVerifiedAt ?? previous?.verifiedAt ?? 0,
      camsVerifiedAt: camsVerified
        ? verifiedAt
        : hasRetainableCams(selected, options.now) ? previous?.camsVerifiedAt ?? null : null,
    };
    const persistedCandidate = writePersistedBundle(selected, location, metadata);
    if (persistedCandidate === false || (persistedCandidate === null && previousActive)) {
      if (previousActive) {
        if (persistedCandidate === false) {
          candidateCommitFailures.set(key, candidateCommitFailure(selected));
        }
        remember(key, previousActive);
        return withCandidateCommitDiagnostic(key, previousActive);
      }
      throw runtimeError("CACHE_PERSIST_FAILED", "salvataggio atomico del bundle meteo non riuscito");
    }
    remember(key, selected);
    if (persistedCandidate === true
      && committedBundleCoversFailure(selected, candidateCommitFailures.get(key))) {
      candidateCommitFailures.delete(key);
    }
    if (iconVerified || camsVerified) rememberVerified(verificationKey, selected, metadata);
    // A hard failure belongs to the generation being fetched, not to a newer
    // independently verified commit. Revocations are still applied separately
    // by observeIconLatest/observeCamsFamily before this point.
    const cacheKey = getLocalWeatherV1BundleCacheKey(location, options);
    for (const pending of inFlight.values()) {
      if (persistedCandidate === true && (iconVerified || camsVerified)
        && pending.cacheKey === cacheKey && pending.storage === options.storage) {
        pending.supersededByVerifiedCommit = true;
      }
    }
  } else {
    remember(key, selected);
  }
  return withCandidateCommitDiagnostic(key, selected);
}

function rebaseDeferredCamsSupplement(incoming, location, options) {
  // A deferred supplement still carries the ICON snapshot used by its source
  // request. Validate that complete original bundle before taking only its
  // independently published CAMS family.
  assertBundleIconEnabled(incoming, options.baseUrl);
  const familyState = observeCamsFamily(incoming, options);
  assertBundleCamsEnabled(incoming, familyState);
  const preparedIncoming = prepareIncomingBundle(incoming, options.now, location);
  if (!preparedIncoming) {
    throw runtimeError("ICON_BUNDLE_UNUSABLE", "Dati meteo incompleti");
  }

  const target = normalizeStorage(options.storage);
  const activeKey = getLocalWeatherV1BundleCacheKey(location, options);
  const activeRecord = target && activeKey
    ? readPreparedPersistedRecord(target, activeKey, location, options, familyState)
    : null;
  const activePrepared = activeRecord
    && Number.isFinite(activeRecord.record.verifiedAt)
    && activeRecord.record.verifiedAt >= 0
    ? activeRecord.prepared
    : null;
  if (!activePrepared) {
    return { bundle: incoming, options };
  }

  const rebasedOptions = {
    ...options,
    // The supplement verifies CAMS, not the ICON object used as its durable
    // base. Preserve that object's existing verification timestamp.
    iconVerifiedAt: activeRecord.record.verifiedAt,
  };
  if (iconObjectIdentity(activePrepared) === iconObjectIdentity(preparedIncoming)
    && iconDisplayFingerprint(activePrepared) === iconDisplayFingerprint(preparedIncoming)) {
    return { bundle: incoming, options: rebasedOptions };
  }

  return {
    // The prepared view is intentionally lossy: it rebases the current hour
    // and removes elapsed ICON rows. Build the durable CAMS-only replacement
    // from the exact persisted payload so the delta can be reconstructed and
    // verified byte-for-byte against that active base.
    bundle: withCamsFrom(activeRecord.record.bundle, preparedIncoming),
    options: rebasedOptions,
  };
}

function readFallbackBundle(key, location, options) {
  const familyState = camsFamilyStateFor(options.baseUrl);
  const memory = retainedBundles.get(key);
  const persisted = readPersistedBundle(location, options, familyState);
  const usableMemory = !familyState.disabledRunIds.has(camsRunIdFromBundle(memory))
    && !iconFamilyStateFor(options.baseUrl).disabledRunIds.has(iconRunIdFromBundle(memory))
    ? prepareRetainedBundle(memory, options.now, location) : null;
  const selected = preferBundle(usableMemory, persisted, options.now);
  if (!selected) return null;
  remember(key, selected);
  return {
    bundle: selected,
    source: selected === persisted ? "verified_persistent_bundle" : "verified_memory_bundle",
  };
}

function dependencyKey(location, {
  baseUrl,
  fetchImpl,
  storage,
  now,
  verificationNow,
  bundleFetcher,
}) {
  return [
    String(baseUrl || "").replace(/\/+$/, ""),
    municipalityIdentity(location) || locationIdentity(location),
    identity(fetchImpl),
    identity(storage),
    identity(now),
    identity(verificationNow),
    identity(bundleFetcher),
  ].join("\n");
}

function retentionKey(dependencies, deferCams) {
  return [
    dependencies,
    deferCams ? "cams:deferred" : "cams:required",
  ].join("\n");
}

function requestKey(retainedKey, force) {
  return [
    retainedKey,
    force ? "refresh:forced" : "refresh:conditional",
  ].join("\n");
}

function safelyNotify(callback, bundle, lifecycle) {
  try {
    const notification = lifecycle === undefined
      ? callback(bundle)
      : callback(bundle, lifecycle);
    Promise.resolve(notification).catch(() => {});
  } catch {
    // Observer failures must not affect the shared weather request.
  }
}

function permitsRetainedFallback(error) {
  if (error?.name === "AbortError" || error?.aborted || error?.cause?.name === "AbortError") return false;
  if (error?.code === "HTTP_ERROR") {
    return error.httpStatus === 408 || error.httpStatus === 429
      || (Number.isInteger(error.httpStatus) && error.httpStatus >= 500 && error.httpStatus <= 599);
  }
  // Candidate validation/revocation errors are reported to the caller but no
  // longer purge the independently verified active bundle.
  return !error?.code || ["TRANSPORT_FAILURE", "TIMEOUT", "NETWORK_ERROR"].includes(error.code);
}

export async function fetchLocalWeatherV1RuntimeBundle(
  location,
  {
    baseUrl,
    fetchImpl,
    storage = null,
    now = Date.now,
    bundleFetcher,
    deferCams = false,
    force = false,
    retryUnavailableCams = false,
    onCamsUpdate,
    onCamsFailure,
    verificationNow = Date.now,
    verifyWindowMs = LOCAL_WEATHER_V1_VERIFY_WINDOW_MS,
  } = {},
) {
  if (typeof bundleFetcher !== "function") {
    throw new Error("Fetcher bundle weather v1 locale mancante");
  }
  if (typeof deferCams !== "boolean") {
    throw new Error("Modalita CAMS weather v1 locale non valida");
  }
  if (typeof force !== "boolean") {
    throw new Error("Modalita refresh weather v1 locale non valida");
  }
  if (typeof retryUnavailableCams !== "boolean") {
    throw new Error("Modalita recupero CAMS weather v1 locale non valida");
  }
  if (onCamsUpdate !== undefined && typeof onCamsUpdate !== "function") {
    throw new Error("Callback CAMS weather v1 locale non valida");
  }
  if (onCamsFailure !== undefined && typeof onCamsFailure !== "function") {
    throw new Error("Callback errore CAMS weather v1 locale non valida");
  }
  if (
    !Number.isInteger(verifyWindowMs)
    || verifyWindowMs < 0
    || verifyWindowMs > MAX_VERIFY_WINDOW_MS
  ) {
    throw new Error("Finestra di verifica weather v1 locale non valida");
  }
  // Keep the native selection in sync even when a recently verified bundle
  // satisfies this request without entering the adapter. This never awaits I/O.
  try {
    getPilotWeatherPrefetchReader({ baseUrl, istatCode: resolveLocalWeatherV1Istat(location) });
  } catch {
    // Optional Android staging must not alter the runtime's normal validation.
  }
  const verificationKey = dependencyKey(location, {
    baseUrl,
    fetchImpl,
    storage,
    now,
    verificationNow,
    bundleFetcher,
  });
  const retainedKey = retentionKey(verificationKey, deferCams);
  const key = requestKey(retainedKey, force);
  const bundleCacheOptions = {
    baseUrl,
    now,
    storage,
    verificationNow,
    verifyWindowMs,
  };
  restoreIconRevocations(bundleCacheOptions);
  restoreCamsFamilyDecision(bundleCacheOptions);
  const pending = inFlight.get(key);
  if (pending) {
    if (onCamsUpdate) pending.callbacks.add(onCamsUpdate);
    if (onCamsFailure) pending.failureCallbacks.add(onCamsFailure);
    return pending.promise;
  }
  let retainedIconBundle = null;
  if (!force) {
    const verified = readRecentlyVerifiedBundle(verificationKey, location, bundleCacheOptions);
    if (verified) {
      remember(retainedKey, verified.bundle);
      if (!retryUnavailableCams || hasUsableCams(verified.bundle, now)) {
        return withCandidateCommitDiagnostic(retainedKey, verified.bundle);
      }
      // An App-gated opportunity retries only the failed supplement. The
      // existing verification window still protects already verified ICON.
      retainedIconBundle = verified.bundle;
      bundleCacheOptions.iconVerifiedAt = verified.verifiedAt;
    }
  }

  const entry = {
    cacheKey: getLocalWeatherV1BundleCacheKey(location, bundleCacheOptions),
    storage,
    supersededByVerifiedCommit: false,
    callbacks: new Set(onCamsUpdate ? [onCamsUpdate] : []),
    failureCallbacks: new Set(onCamsFailure ? [onCamsFailure] : []),
    initialSettled: false,
    sourceSucceeded: false,
    supplement: null,
    supplementFailure: null,
    supplementSettled: !deferCams,
    promise: null,
  };
  const clearEntry = () => {
    if (inFlight.get(key) === entry) inFlight.delete(key);
  };
  const dispatchSupplement = () => {
    if (!entry.sourceSucceeded || !entry.supplement) {
      clearEntry();
      return;
    }
    const bundle = entry.supplement;
    entry.supplement = null;
    for (const callback of entry.callbacks) {
      safelyNotify(callback, bundle, { lifecycle: "final" });
    }
    entry.callbacks.clear();
    clearEntry();
  };
  const receiveSupplement = (bundle) => {
    try {
      if (entry.supplementFailure) return;
      const rebased = rebaseDeferredCamsSupplement(
        bundle,
        location,
        bundleCacheOptions,
      );
      entry.supplement = selectVerifiedBundle(
        retainedKey,
        verificationKey,
        rebased.bundle,
        location,
        rebased.options,
      );
    } finally {
      entry.supplementSettled = true;
      if (entry.initialSettled) dispatchSupplement();
    }
  };
  const publishRevocationState = () => {
    if (!entry.callbacks.size) return;
    const retained = readFallbackBundle(retainedKey, location, bundleCacheOptions);
    if (!retained) return;
    for (const callback of entry.callbacks) {
      safelyNotify(callback, retained.bundle, {
        lifecycle: "intermediate",
        reason: "revocation",
      });
    }
  };
  const fetchOptions = {
    baseUrl,
    fetchImpl,
    force,
    now,
    storage,
    ...(retainedIconBundle ? { retainedIconBundle } : {}),
    onIconLatest: latest => observeIconLatest(latest, bundleCacheOptions),
    onCamsFamilyLatest: latest => {
      const previousRunIds = new Set([
        camsRunIdFromBundle(retainedBundles.get(retainedKey)),
        camsRunIdFromBundle(recentlyVerifiedBundles.get(verificationKey)?.bundle),
      ].filter(Boolean));
      try {
        const target = normalizeStorage(storage);
        const cacheKey = getLocalWeatherV1BundleCacheKey(location, bundleCacheOptions);
        const persisted = JSON.parse(target?.getItem(cacheKey));
        const runId = camsRunIdFromBundle(persisted?.bundle);
        if (runId) previousRunIds.add(runId);
      } catch { /* A validated fallback read below remains authoritative. */ }
      try {
        observeVerifiedCamsFamilyDecision(latest, bundleCacheOptions);
      } finally {
        const disabled = camsFamilyStateFor(baseUrl).disabledRunIds;
        if ([...previousRunIds].some(runId => disabled.has(runId))) {
          publishRevocationState();
        }
      }
    },
    ...(deferCams ? {
      deferCams: true,
      onCamsUpdate: receiveSupplement,
      onCamsFailure: (error) => {
        entry.supplementFailure = error;
        entry.supplementSettled = true;
        for (const callback of entry.failureCallbacks) safelyNotify(callback, error);
        entry.failureCallbacks.clear();
        if (entry.initialSettled) clearEntry();
      },
    } : {}),
  };

  const request = Promise.resolve()
    .then(() => bundleFetcher(location, fetchOptions))
    .then((bundle) => {
      entry.sourceSucceeded = true;
      return selectVerifiedBundle(
        retainedKey,
        verificationKey,
        bundle,
        location,
        bundleCacheOptions,
      );
    })
    .catch((error) => {
      if (!permitsRetainedFallback(error)) {
        throw error;
      }
      const retained = readFallbackBundle(retainedKey, location, bundleCacheOptions);
      if (retained) {
        return withCandidateCommitDiagnostic(
          retainedKey,
          withRuntimeFallback(retained.bundle, retained.source),
        );
      }
      throw error;
    })
    .finally(() => {
      entry.initialSettled = true;
      if (!deferCams || !entry.sourceSucceeded) clearEntry();
      else if (entry.supplementSettled) globalThis.setTimeout(dispatchSupplement, 0);
    });
  entry.promise = request;
  inFlight.set(key, entry);
  return request;
}
