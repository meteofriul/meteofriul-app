import placeNames from "../data/fvgPlaceNamesFur.json";
import { getDateTimeFormatter } from "../domain/dateTimeFormatters.js";
import { getLocationMunicipality, getLocationMunicipalityName } from "../domain/geo/locationIdentity";
import { getHomeSolarState } from "../features/home/homeDayPhase";
import { createWeatherV1Client } from "./weatherV1Client";
import {
  CAMS_AIR_FIELDS,
  encodeCamsHourlyCacheV2,
} from "./camsHourlyCache";
import { ICON_FORECAST_WINDOW_POLICY, selectIconFutureRows } from "./iconForecastWindow";
import { getPilotWeatherPrefetchReader } from "./pilotWeatherPrefetch";

const HOUR_MS = 60 * 60 * 1000;
const TIME_ZONE = "Europe/Rome";
const PRIMARY_SOURCE = "icon2i_local_pilot";
const MODE = "local_contract_v1";
const EXPECTED_MUNICIPALITIES = 215;
const ISTAT_PATTERN = /^\d{6}$/;
const DIAGNOSTIC_CODE_PATTERN = /^[A-Z][A-Z0-9_]{0,63}$/;
const CAMS_POLLEN_PROVIDER = "cams_europe_pollen";
const camsFamilyObserverFailures = new WeakSet();

export const LOCAL_WEATHER_V1_CATALOG = Object.freeze({
  version: "istat-2026-irdat-2006-representative-points-v1",
  sha256: "d5cb6f9efdf10151caa0508b07ed910488db01dc29de45b293ac9eb05652eca4",
  municipality_count: EXPECTED_MUNICIPALITIES,
});

// One end-to-end budget (preflight, family/release, manifests and both payloads),
// not a fresh budget for each hop. A52 logs: OPTIONS <=2.1 s + first GET <=6 s;
// 20 s leaves ~12 s for remaining validated reads and mobile transport variance.
// Deferred callers deliver ICON immediately; this is not a first-render wait.
export const LOCAL_WEATHER_V1_CAMS_TIMEOUT_MS = 20_000;

const POLLEN_IDS = Object.freeze([
  ["alder_pollen", "ontano"],
  ["birch_pollen", "betulla"],
  ["grass_pollen", "graminacee"],
  ["mugwort_pollen", "artemisia"],
  ["olive_pollen", "olivo"],
  ["ragweed_pollen", "ambrosia"],
]);

const CONDITION_LABELS = Object.freeze({
  clear: "Sereno",
  mostly_sunny: "Poco nuvoloso",
  partly_cloudy: "Parzialmente nuvoloso",
  overcast: "Coperto",
  fog: "Nebbia",
  drizzle: "Pioviggine",
  freezing_drizzle: "Pioviggine gelata",
  rain: "Pioggia",
  heavy_rain: "Pioggia intensa",
  freezing_rain: "Pioggia gelata",
  snow: "Neve",
  snow_grains: "Neve",
  showers: "Rovesci",
  snow_showers: "Rovesci di neve",
  storm: "Temporale",
  strong_storm: "Temporale forte",
});

export class LocalWeatherV1AdapterError extends Error {
  constructor(code, message, options) {
    super(message, options);
    this.name = "LocalWeatherV1AdapterError";
    this.code = code;
  }
}

function fail(code, message, cause) {
  throw new LocalWeatherV1AdapterError(code, message, cause ? { cause } : undefined);
}

function normalizeName(value) {
  return String(value || "")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("it")
    .replace(/[^a-z0-9]+/g, " ")
    .trim()
    .replace(/\s+/g, " ");
}

function buildMunicipalityIndex() {
  if (
    !placeNames ||
    !Array.isArray(placeNames.names) ||
    placeNames.names.length !== EXPECTED_MUNICIPALITIES
  ) {
    fail("INVALID_LOCAL_CATALOG", "dataset locale dei 215 comuni non disponibile");
  }
  const codes = new Set();
  const names = new Map();
  for (const record of placeNames.names) {
    const code = record?.istatCode;
    if (!ISTAT_PATTERN.test(code) || codes.has(code)) {
      fail("INVALID_LOCAL_CATALOG", "dataset locale con ISTAT invalido o duplicato");
    }
    codes.add(code);
    for (const name of [record.it, record.fur]) {
      const normalized = normalizeName(name);
      if (!normalized) continue;
      const existing = names.get(normalized);
      if (existing && existing !== code) {
        fail("INVALID_LOCAL_CATALOG", "nome comunale locale ambiguo");
      }
      names.set(normalized, code);
    }
  }
  return {
    codes: Object.freeze([...codes].sort()),
    names,
  };
}

const MUNICIPALITY_INDEX = buildMunicipalityIndex();
export const LOCAL_WEATHER_V1_ISTAT_CODES = MUNICIPALITY_INDEX.codes;

export function resolveLocalWeatherV1Istat(location) {
  const municipality = getLocationMunicipality(location);
  const explicit = String(municipality?.istatCode || "").trim();
  if (explicit) {
    if (!MUNICIPALITY_INDEX.codes.includes(explicit)) {
      fail("UNKNOWN_MUNICIPALITY", "codice ISTAT non presente nel catalogo locale");
    }
    return explicit;
  }
  const normalized = normalizeName(getLocationMunicipalityName(location));
  const resolved = MUNICIPALITY_INDEX.names.get(normalized);
  if (!resolved) fail("UNKNOWN_MUNICIPALITY", "comune non presente nel catalogo locale");
  return resolved;
}

function clockFunction(now) {
  return typeof now === "function" ? now : () => now;
}

function clockMilliseconds(now) {
  const value = clockFunction(now)();
  const milliseconds = value instanceof Date ? value.getTime() : new Date(value).getTime();
  if (!Number.isFinite(milliseconds)) fail("INVALID_CLOCK", "orologio locale non valido");
  return milliseconds;
}

function finiteCoordinate(value, minimum, maximum) {
  if (value === null || value === undefined || value === "") return null;
  const number = Number(value);
  return Number.isFinite(number) && number >= minimum && number <= maximum ? number : null;
}

export function resolveLocalWeatherV1PresentationPoint(location, representativePoint) {
  const requestedLatitude = finiteCoordinate(location?.lat ?? location?.latitude, 45, 47.2);
  const requestedLongitude = finiteCoordinate(location?.lon ?? location?.longitude, 11.8, 14.5);
  const requestedAccuracy = Number(location?.positionAccuracyM);
  const requestedCapturedAt = Date.parse(location?.positionCapturedAt);
  const hasVerifiedDevicePoint = requestedLatitude !== null
    && requestedLongitude !== null
    && Number.isFinite(requestedAccuracy)
    && requestedAccuracy >= 0
    && Number.isFinite(requestedCapturedAt);
  if (hasVerifiedDevicePoint) {
    return { lat: requestedLatitude, lon: requestedLongitude, source: "device_location" };
  }
  const latitude = finiteCoordinate(representativePoint?.lat, 45, 47.2);
  const longitude = finiteCoordinate(representativePoint?.lon, 11.8, 14.5);
  if (latitude === null || longitude === null) {
    fail("INVALID_MUNICIPALITY_POINT", "punto comunale autorevole non valido");
  }
  return { lat: latitude, lon: longitude, source: "authoritative_municipality_point" };
}

function locationCoordinates(location, municipality) {
  const point = resolveLocalWeatherV1PresentationPoint(location, municipality?.representative_point);
  return { latitude: point.lat, longitude: point.lon, source: point.source };
}

function solarState(timestamp, coordinates) {
  const state = getHomeSolarState({
    now: timestamp,
    latitude: coordinates.latitude,
    longitude: coordinates.longitude,
    timeZone: TIME_ZONE,
  });
  if (
    state.source === "fallback" ||
    !Number.isFinite(state.sunriseMinutes) ||
    !Number.isFinite(state.sunsetMinutes)
  ) {
    fail("SOLAR_STATE_UNAVAILABLE", "calcolo locale giorno/notte non disponibile");
  }
  return state;
}

function clockLabel(minutes) {
  const hour = Math.floor(minutes / 60);
  const minute = Math.round(minutes % 60);
  return `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
}

function conditionLabel(condition) {
  if (condition?.native_status !== "valid") return "Condizione meteo non disponibile";
  return CONDITION_LABELS[condition.semantic_key] || "Condizione meteo non disponibile";
}

function toKmh(value) {
  return value === null ? null : value * 3.6;
}

function rowTimestamp(row, label) {
  const timestamp = Date.parse(row?.valid_at);
  if (!Number.isFinite(timestamp)) fail("INVALID_TIMELINE", `${label} senza timestamp valido`);
  return timestamp;
}

function currentRow(payload, nowMilliseconds, label) {
  if (!Array.isArray(payload?.hourly) || !payload.hourly.length) {
    fail("INVALID_TIMELINE", `${label} senza timeline oraria`);
  }
  let selected = null;
  let selectedTime = null;
  for (const row of payload.hourly) {
    const timestamp = rowTimestamp(row, label);
    if (timestamp <= nowMilliseconds && (selectedTime === null || timestamp > selectedTime)) {
      selected = row;
      selectedTime = timestamp;
    }
  }
  if (!selected || nowMilliseconds - selectedTime >= HOUR_MS) {
    fail("CURRENT_SAMPLE_UNAVAILABLE", `${label} senza campione dell'ora corrente`);
  }
  return { row: selected, index: payload.hourly.indexOf(selected), timestamp: selectedTime };
}

function hourlySlot(row, coordinates) {
  const solar = solarState(row.valid_at, coordinates);
  return {
    time: row.valid_at,
    interval_start: row.interval_start,
    interval_end: row.interval_end,
    temperature: row.temperature_c,
    condition: conditionLabel(row.condition),
    weathercode: null,
    primary_source: PRIMARY_SOURCE,
    feels_like: row.apparent_temperature_c,
    humidity: row.relative_humidity_pct,
    pressure: row.pressure_msl_hpa,
    cloud_cover: row.cloud_cover_pct,
    wind_speed: toKmh(row.wind_speed_m_s),
    wind_direction: row.wind_from_degrees,
    wind_gusts: toKmh(row.wind_gust_max_m_s),
    precipitation: row.precipitation_mm,
    rain: row.liquid_rain_mm,
    showers: null,
    snowfall: null,
    precipitation_probability: null,
    visibility: null,
    is_day: solar.isNight ? 0 : 1,
    snowfall_water_equivalent_mm: row.snow_water_equivalent_mm,
    quality_flags: [...row.quality_flags],
    data_quality: {
      mode: MODE,
      native_weather_code: row.condition.native_code,
      native_condition_label: row.condition.native_label_it,
      native_condition_status: row.condition.native_status,
      native_semantic_key: row.condition.semantic_key,
      valid_at_utc: row.valid_at,
      day_phase_source: solar.source,
    },
  };
}

function zonedParts(timestamp) {
  const parts = getDateTimeFormatter("en-CA", {
    day: "2-digit",
    hour: "2-digit",
    hourCycle: "h23",
    month: "2-digit",
    timeZone: TIME_ZONE,
    year: "numeric",
  }).formatToParts(new Date(timestamp));
  const values = Object.fromEntries(parts.map(({ type, value }) => [type, value]));
  return {
    date: `${values.year}-${values.month}-${values.day}`,
    hour: Number(values.hour),
  };
}

function buildDaily(iconRows) {
  const groups = new Map();
  for (const row of iconRows) {
    const timestamp = rowTimestamp(row, "ICON");
    const local = zonedParts(timestamp);
    if (!groups.has(local.date)) groups.set(local.date, []);
    groups.get(local.date).push({ row, localHour: local.hour, timestamp });
  }
  const forecast = [...groups.entries()].sort(([left], [right]) => left.localeCompare(right)).map(
    ([date, entries]) => {
      entries.sort((left, right) => left.timestamp - right.timestamp);
      const temperatures = entries.map(({ row }) => row.temperature_c);
      const numeric = temperatures.filter((value) => Number.isFinite(value));
      const complete =
        entries[0]?.localHour === 0 &&
        entries.at(-1)?.localHour === 23 &&
        [23, 24, 25].includes(entries.length) &&
        numeric.length === entries.length;
      const representative = entries.reduce((selected, entry) =>
        Math.abs(entry.localHour - 12) < Math.abs(selected.localHour - 12) ? entry : selected,
      );
      return {
        date,
        condition: conditionLabel(representative.row.condition),
        weathercode: null,
        min_temp: complete ? Math.min(...numeric) : null,
        max_temp: complete ? Math.max(...numeric) : null,
        sampled_min_temp: numeric.length ? Math.min(...numeric) : null,
        sampled_max_temp: numeric.length ? Math.max(...numeric) : null,
        source_hours: entries.length,
        partial_day: !complete,
        condition_policy: "Condizione ICON nativa disponibile piu vicina al mezzogiorno locale",
        extrema_policy: "Estremi campionati orari; i giorni parziali non espongono min/max completi",
        primary_source: PRIMARY_SOURCE,
        official_text: "",
        emission: "",
        data_quality: {
          mode: MODE,
          native_weather_code: representative.row.condition.native_code,
          native_condition_label: representative.row.condition.native_label_it,
          native_condition_status: representative.row.condition.native_status,
        },
      };
    },
  );
  if (!forecast.length) fail("DAILY_UNAVAILABLE", "previsione giornaliera ICON non disponibile");
  return {
    forecast,
    daily: {
      time: forecast.map(({ date }) => date),
      temperature_2m_min: forecast.map(({ min_temp }) => min_temp),
      temperature_2m_max: forecast.map(({ max_temp }) => max_temp),
      weathercode: forecast.map(() => null),
      weather_code: forecast.map(() => null),
    },
  };
}

function deliveryEvidence(result) {
  return {
    path: result.path,
    etag: result.etag,
    freshness: result.freshness,
    ...(result.familyRelease ? { family_release: result.familyRelease, family_release_published_at: result.familyReleasePublishedAt } : {}),
    from_cache: result.fromCache === true,
    network_fallback: result.networkFallback === true,
    fallback_reason: result.fallbackReason || null,
    not_modified: result.notModified === true,
    cache_persisted:
      typeof result.cachePersisted === "boolean" ? result.cachePersisted : null,
  };
}

function familyDecisionEvidence(latestDocument) {
  return Number.isSafeInteger(latestDocument?.revision)
    && typeof latestDocument?.published_at === "string"
    && typeof latestDocument?.latest?.source_run_id === "string"
    && Array.isArray(latestDocument?.disabled_run_ids)
    ? {
      revision: latestDocument.revision,
      published_at: latestDocument.published_at,
      active_run_id: latestDocument.latest.source_run_id,
      disabled_run_ids: [...latestDocument.disabled_run_ids],
    }
    : null;
}

function providerEvidence(outcome) {
  const results = outcome?.stages || { municipality: outcome?.result };
  const stages = Object.fromEntries(
    Object.entries(results)
      .filter(([, result]) => result)
      .map(([stage, result]) => [stage, deliveryEvidence(result)]),
  );
  const values = Object.values(stages);
  const municipality = stages.municipality || deliveryEvidence(outcome.result);
  const persisted = values
    .map(({ cache_persisted: value }) => value)
    .filter((value) => typeof value === "boolean");
  const family = familyDecisionEvidence(results.latest?.document);
  return {
    ...municipality,
    from_cache: values.some(({ from_cache: value }) => value),
    network_fallback: values.some(({ network_fallback: value }) => value),
    fallback_reason:
      values.find(({ fallback_reason: value }) => value)?.fallback_reason || null,
    not_modified: values.some(({ not_modified: value }) => value),
    cache_persisted: persisted.length ? persisted.every(Boolean) : null,
    stages,
    ...(family ? { family } : {}),
  };
}

function partialFamilyEvidence(outcome) {
  const latest = outcome?.stages?.latest;
  const family = familyDecisionEvidence(latest?.document ?? outcome?.familyLatest);
  return family
    ? {
      family,
      stages: latest ? { latest: deliveryEvidence(latest) } : {},
    }
    : null;
}

function buildCamsSource(camsState) {
  let cams;
  if (camsState.available) {
    cams = {
      provider: CAMS_POLLEN_PROVIDER,
      source_provider: camsState.result.document.projection?.source_provider || "cams_europe",
      status: "available",
      model: camsState.result.document.model,
      attribution: camsState.result.document.source,
      run_utc: camsState.result.document.run_at,
      evidence: providerEvidence(camsState.outcome),
      diagnostic: null,
    };
  } else if (camsState.pending) {
    cams = {
      provider: CAMS_POLLEN_PROVIDER,
      source_provider: "cams_europe",
      status: "pending",
      model: null,
      attribution: null,
      run_utc: null,
      evidence: null,
      diagnostic: null,
    };
  } else {
    cams = {
      provider: CAMS_POLLEN_PROVIDER,
      source_provider: "cams_europe",
      status: "unavailable",
      model: null,
      attribution: null,
      run_utc: null,
      evidence: partialFamilyEvidence(camsState.outcome),
      diagnostic: camsState.diagnostic,
    };
  }
  return cams;
}

function buildSource(iconOutcome, camsState, municipality, retainedSource = null) {
  const iconResult = iconOutcome?.result;
  return {
    status: camsState.available ? "available" : camsState.pending ? "pending" : "degraded",
    active: PRIMARY_SOURCE,
    primary_source: PRIMARY_SOURCE,
    mode: MODE,
    label: camsState.available
      ? "ItaliaMeteo ICON-2I e CAMS · contratto locale v1"
      : camsState.pending
        ? "ItaliaMeteo ICON-2I · CAMS in arrivo"
        : "ItaliaMeteo ICON-2I · CAMS non disponibile",
    fallback_used: null,
    current_policy: "local-icon-cams-v1-no-provider-fallback",
    municipality_istat: municipality.istat_code,
    catalog: LOCAL_WEATHER_V1_CATALOG,
    icon: retainedSource?.icon || {
      provider: "icon2i",
      status: "available",
      model: iconResult.document.model,
      attribution: iconResult.document.source,
      run_utc: iconResult.document.run_at,
      evidence: providerEvidence(iconOutcome),
    },
    cams: buildCamsSource(camsState),
  };
}

// The runtime supplies this only after validating a recently verified ICON
// bundle. Refreshing CAMS does not re-fetch or manufacture any ICON rows.
function assertRetainedIconIdentity(bundle, istatCode) {
  const source = bundle?.current?.source;
  if (source?.municipality_istat !== istatCode
    || source?.catalog?.sha256 !== LOCAL_WEATHER_V1_CATALOG.sha256
    || !source?.icon
    || bundle?.forecast?.data_quality?.municipality_istat !== istatCode) {
    fail("PROVIDER_IDENTITY_MISMATCH", "bundle ICON conservato non corrispondente");
  }
}

function buildRetainedIconCamsSupplement(bundle, camsOutcome, nowMilliseconds, istatCode) {
  assertRetainedIconIdentity(bundle, istatCode);
  const source = bundle.current.source;
  const municipality = { istat_code: istatCode };
  const camsState = resolveCamsState({ municipality, catalog: source.catalog }, camsOutcome, nowMilliseconds);
  const nextSource = buildSource(null, camsState, municipality, source);
  const decorate = value => ({
    ...value,
    source: { ...value.source, ...nextSource },
    model_support: { ...value.model_support, cams: camsState.available },
    data_quality: {
      ...value.data_quality,
      cams_status: camsState.available ? camsState.result.freshness.status : "unavailable",
      cams_run_utc: camsState.available ? camsState.result.document.run_at : null,
      cams_valid_at_utc: camsState.available ? camsState.current.row.valid_at : null,
      cams_sample_status: camsState.available ? "current" : null,
      cams_diagnostic: camsState.diagnostic,
      capability_gaps: [...new Set([
        ...(value.data_quality.capability_gaps || []).filter(gap => !["cams_pollen", "cams_pollen_pending"].includes(gap)),
        ...(camsState.available ? [] : ["cams_pollen"]),
      ])],
      flags: [...new Set([
        ...(value.data_quality.flags || []).filter(flag => !["cams_unavailable", "cams_pending"].includes(flag)),
        ...(camsState.available ? [] : ["cams_unavailable"]),
      ])].sort(),
    },
  });
  return {
    ...bundle,
    current: { ...decorate(bundle.current), pollen: camsState.pollen.summary,
      pollen_data: camsState.pollen, air_quality_data: camsState.air || null,
      cams_hourly_cache: buildCamsHourlyCache(camsState, istatCode) },
    forecast: decorate(bundle.forecast),
  };
}

function camsDiagnostic(error, stage) {
  const rawCode = typeof error?.code === "string" ? error.code : "";
  return {
    provider: CAMS_POLLEN_PROVIDER,
    status: "unavailable",
    stage,
    code: DIAGNOSTIC_CODE_PATTERN.test(rawCode) ? rawCode : "CAMS_UNAVAILABLE",
    message: "Dati CAMS non disponibili per questo aggiornamento; meteo ICON conservato",
  };
}

function unavailablePollen(diagnostic) {
  return {
    status: "unavailable",
    freshness: null,
    summary: "Pollini CAMS non disponibili",
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
}

function pendingPollen() {
  return {
    status: "pending",
    freshness: null,
    summary: "Pollini CAMS in arrivo",
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
    note: "Arricchimento CAMS in corso; il meteo ICON e gia disponibile",
    diagnostic: null,
  };
}

function buildPollen(camsResult, camsCurrent) {
  const payload = camsResult.document;
  if (!Array.isArray(payload.variables) || payload.variables.length !== POLLEN_IDS.length) {
    fail("CAMS_POLLEN_INCOMPLETE", "la vista CAMS non contiene le sei specie polliniche");
  }
  const variables = payload.variables.map((variable) => ({
    id: variable.id,
    ui_key: variable.ui_key,
    category: variable.category,
    value: camsCurrent.row.values[variable.id],
    units: variable.unit,
    validation_status: variable.validation_status,
    quality_flags: [...camsCurrent.row.quality_flags[variable.id]],
  }));
  const byId = new Map(variables.map((variable) => [variable.id, variable]));
  const pollenValues = Object.fromEntries(
    POLLEN_IDS.map(([sourceId, uiKey]) => {
      const variable = byId.get(sourceId);
      if (!variable || variable.category !== "pollen") {
        fail("CAMS_POLLEN_INCOMPLETE", "le sei specie polliniche CAMS non sono complete");
      }
      return [uiKey, variable.value];
    }),
  );
  return {
    status: "experimental_model_snapshot",
    sample_status: "current",
    freshness: camsResult.freshness.status,
    summary: "Previsione pollini CAMS · sperimentale",
    level: null,
    main: null,
    values: pollenValues,
    units: "grains/m3",
    run_utc: payload.run_at,
    generated_at_utc: payload.generated_at,
    valid_at_utc: camsCurrent.row.valid_at,
    source: "cams_european_ensemble",
    all_variables: variables,
    grid_point: { ...payload.municipality.model_point },
    attribution: { ...payload.source },
    health_classification: null,
    note: "Concentrazioni previste; nessuna soglia sanitaria o classe allergica",
  };
}

function resolveCamsState(icon, camsOutcome, nowMilliseconds) {
  if (camsOutcome?.pending) {
    return {
      available: false,
      pending: true,
      diagnostic: null,
      pollen: pendingPollen(),
    };
  }
  if (!camsOutcome.ok) {
    const diagnostic = camsDiagnostic(camsOutcome.error, camsOutcome.stage);
    return {
      available: false,
      pending: false,
      diagnostic,
      outcome: camsOutcome,
      pollen: unavailablePollen(diagnostic),
    };
  }
  try {
    const result = camsOutcome.result;
    const cams = result.document;
    if (
      cams.municipality?.istat_code !== icon.municipality?.istat_code ||
      cams.catalog?.sha256 !== icon.catalog?.sha256
    ) {
      fail("PROVIDER_IDENTITY_MISMATCH", "ICON e CAMS non identificano lo stesso comune/catalogo");
    }
    const current = currentRow(cams, nowMilliseconds, "CAMS");
    return {
      available: true,
      pending: false,
      outcome: camsOutcome,
      result,
      current,
      diagnostic: null,
      pollen: buildPollen(result, current),
      air: result.airResult ? buildAir(result.airResult, icon, nowMilliseconds) : null,
    };
  } catch (error) {
    const diagnostic = camsDiagnostic(error, "adapt");
    return {
      available: false,
      pending: false,
      diagnostic,
      outcome: camsOutcome,
      pollen: unavailablePollen(diagnostic),
    };
  }
}

function buildAir(result, icon, nowMilliseconds) {
  const payload = result.document;
  if (payload.municipality?.istat_code !== icon.municipality?.istat_code
    || payload.catalog?.sha256 !== icon.catalog?.sha256) {
    fail("PROVIDER_IDENTITY_MISMATCH", "ICON e CAMS aria non identificano lo stesso comune/catalogo");
  }
  const current = currentRow(payload, nowMilliseconds, "CAMS");
  return {
    valid_at: current.row.valid_at,
    run_at: payload.run_at,
    sample_status: "current",
    values: Object.fromEntries(payload.variables
      .filter((variable) => variable.category === "air_quality")
      .map((variable) => [variable.id, current.row.values[variable.id]])),
  };
}

function buildCamsHourlyCache(camsState, istatCode) {
  if (!camsState?.available) return null;
  const pollenDocument = camsState.result?.document;
  const airDocument = camsState.result?.airResult?.document;
  if (!pollenDocument || !airDocument) return null;
  const airRows = new Map(airDocument.hourly.map(row => [row.valid_at, row]));
  const pollenVariables = pollenDocument.variables.map(variable => ({
    id: variable.id,
    ui_key: variable.ui_key,
    category: variable.category,
    unit: variable.unit,
    validation_status: variable.validation_status,
  }));
  const airVariables = new Map(airDocument.variables
    .filter(variable => variable.category === "air_quality")
    .map(variable => [variable.id, variable]));
  if (CAMS_AIR_FIELDS.some(id => !airVariables.has(id))) {
    fail("CAMS_FAMILY_INCOMPLETE", "serie CAMS aria senza le quattro variabili UI");
  }
  const samples = pollenDocument.hourly.map(row => {
    const airRow = airRows.get(row.valid_at);
    if (!airRow) fail("CAMS_FAMILY_INCOMPLETE", "serie CAMS aria e pollini non allineate");
    return {
      valid_at_utc: row.valid_at,
      pollen_values: Object.fromEntries(POLLEN_IDS.map(([id, uiKey]) => [uiKey, row.values[id]])),
      pollen_quality_flags: Object.fromEntries(POLLEN_IDS.map(([id]) => [id, [...row.quality_flags[id]]])),
      air_values: Object.fromEntries(CAMS_AIR_FIELDS
        .map(id => [id, airRow.values[id]])),
    };
  });
  try {
    return encodeCamsHourlyCacheV2({
      municipality_istat: istatCode,
      catalog_sha256: pollenDocument.catalog.sha256,
      run_utc: pollenDocument.run_at,
      generated_at_utc: pollenDocument.generated_at,
      fresh_until_utc: camsState.result.freshness?.freshUntil || pollenDocument.freshness.fresh_until,
      usable_until_utc: camsState.result.freshness?.usableUntil || pollenDocument.freshness.usable_until,
      pollen_variables: pollenVariables,
      samples,
    });
  } catch (error) {
    fail("CAMS_FAMILY_INCOMPLETE", "serie CAMS non comprimibile in modo verificabile", error);
  }
}

// Both member tokens must originate from one family pointer read.
function pairedCamsClient(client) {
  if (!client.camsFamily || !client.camsEurope) return client.camsPollen;
  return {
    async fetchLatest(signal, onFamilyLatest) {
      const family = await client.camsFamily.fetchMembersLatest(signal, onFamilyLatest);
      // Use the same verified family token for both members.
      return { ...family.camsPollen, members: family };
    },
    async fetchManifest(family, signal) {
      const [pollen, air] = await Promise.all([
        client.camsPollen.fetchManifest(family.members.camsPollen, signal),
        client.camsEurope.fetchManifest(family.members.camsEurope, signal),
      ]);
      return { ...pollen, pollen, air };
    },
    async fetchMunicipality(manifests, istatCode, signal) {
      const [pollen, airResult] = await Promise.all([
        client.camsPollen.fetchMunicipality(manifests.pollen, istatCode, signal),
        client.camsEurope.fetchMunicipality(manifests.air, istatCode, signal),
      ]);
      return { ...pollen, airResult };
    },
  };
}

function throwIfAborted(signal) {
  if (!signal?.aborted) return;
  const error = new Error("catena provider interrotta");
  error.name = "AbortError";
  error.code = "PROVIDER_ABORTED";
  throw error;
}

async function fetchProviderOutcome(providerClient, istatCode, signal, onFamilyLatest, onLatest) {
  let stage = "latest";
  const stages = {};
  try {
    throwIfAborted(signal);
    const latest = await providerClient.fetchLatest(signal, onFamilyLatest);
    stages.latest = latest;
    if (onLatest) onLatest(latest);
    throwIfAborted(signal);
    stage = "manifest";
    const manifest = await providerClient.fetchManifest(latest, signal);
    stages.manifest = manifest;
    throwIfAborted(signal);
    stage = "municipality";
    const result = await providerClient.fetchMunicipality(manifest, istatCode, signal);
    stages.municipality = result;
    throwIfAborted(signal);
    return {
      ok: true,
      result,
      stages,
    };
  } catch (error) {
    return {
      ok: false,
      error,
      stage,
      stages,
      ...(error?.camsFamilyLatest ? { familyLatest: error.camsFamilyLatest } : {}),
    };
  }
}

function requireIconWindow(outcome, nowMilliseconds) {
  currentRow(outcome.result.document, nowMilliseconds, "ICON");
  if (selectIconFutureRows(outcome.result.document.hourly, nowMilliseconds).length
    < ICON_FORECAST_WINDOW_POLICY.minimumFutureHours) {
    fail("HOURLY_COVERAGE_INCOMPLETE", "ICON senza copertura futura sufficiente");
  }
  return outcome;
}

async function fetchIconOutcome(providerClient, istatCode, clock, onIconLatest) {
  const observeLatest = latest => {
    if (typeof onIconLatest !== "function") return;
    const document = latest.document;
    if (!document?.latest || !Array.isArray(document.disabled_run_ids)) return;
    try {
      onIconLatest({
        revision: document.revision,
        latest: { source_run_id: document.latest.source_run_id },
        disabled_run_ids: [...document.disabled_run_ids],
      });
    } catch (error) {
      // Cache quarantine is a safety gate, not an optional UI observer.
      if (error?.code === "CACHE_INVALIDATION_FAILED") throw error;
      // Other observer failures cannot change validated source bytes.
    }
  };
  const outcome = await fetchProviderOutcome(providerClient, istatCode, undefined, undefined, observeLatest);
  if (outcome.ok) {
    try {
      return requireIconWindow(outcome, clockMilliseconds(clock));
    } catch (error) {
      outcome.ok = false;
      outcome.error = error;
    }
  }
  // Only a previous run explicitly named by the verified pointer is eligible.
  // Each object still passes the same manifest/hash/catalog checks as current.
  const latest = outcome.stages.latest;
  if (!latest?.document?.previous || outcome.error?.name === "AbortError"
    || outcome.error?.aborted || outcome.error?.cause?.name === "AbortError"
    || outcome.error?.code === "CACHE_INVALIDATION_FAILED") return outcome;
  try {
    const manifest = await providerClient.fetchManifest(latest, undefined, { previous: true });
    const result = await providerClient.fetchMunicipality(manifest, istatCode);
    return requireIconWindow({
      ok: true, result, usedPreviousRun: true,
      stages: { latest, manifest, municipality: result },
    }, clockMilliseconds(clock));
  } catch {
    return outcome;
  }
}

async function fetchCamsOutcomeWithTimeout(
  providerClient,
  istatCode,
  timeoutMs,
  onCamsFamilyLatest,
) {
  if (typeof globalThis.AbortController !== "function") {
    return {
      ok: false,
      stage: "timeout",
      error: { code: "CAMS_ABORT_UNAVAILABLE" },
    };
  }
  const controller = new globalThis.AbortController();
  let familyLatest = null;
  let familyObserverError = null;
  const timeoutOutcome = () => ({
    ok: false,
    stage: "timeout",
    error: { code: "CAMS_TIMEOUT" },
    ...(familyLatest ? { familyLatest } : {}),
  });
  let timedOut = false;
  let timer;
  const providerOutcome = fetchProviderOutcome(
    providerClient,
    istatCode,
    controller.signal,
    (latest) => {
      familyLatest = latest;
      try {
        onCamsFamilyLatest?.(latest);
      } catch (error) {
        familyObserverError = error;
        if ((typeof error === "object" && error !== null) || typeof error === "function") {
          camsFamilyObserverFailures.add(error);
        }
        throw error;
      }
    },
  ).then((outcome) => {
    if (familyObserverError) throw familyObserverError;
    return timedOut ? timeoutOutcome() : outcome;
  });
  const timeoutOutcomePromise = new Promise((resolve) => {
    timer = globalThis.setTimeout(() => {
      timedOut = true;
      controller.abort();
      resolve(timeoutOutcome());
    }, timeoutMs);
  });
  try {
    return await Promise.race([providerOutcome, timeoutOutcomePromise]);
  } finally {
    globalThis.clearTimeout(timer);
  }
}

function deliverCamsUpdate(callback, bundle) {
  if (typeof callback !== "function") return;
  globalThis.setTimeout(() => {
    try {
      Promise.resolve(callback(bundle)).catch(() => {});
    } catch {
      // The optional observer must never invalidate a verified provider bundle.
    }
  }, 0);
}

function buildBundle(location, nowMilliseconds, iconOutcome, camsOutcome) {
  const iconResult = iconOutcome.result;
  const icon = iconResult.document;
  const municipality = icon.municipality;
  const coordinates = locationCoordinates(location, municipality);
  const iconCurrent = currentRow(icon, nowMilliseconds, "ICON");
  const camsState = resolveCamsState(icon, camsOutcome, nowMilliseconds);
  const solar = solarState(nowMilliseconds, coordinates);
  const iconWindow = selectIconFutureRows(icon.hourly, nowMilliseconds);
  const hourly = iconWindow.map((row) => hourlySlot(row, coordinates));
  if (hourly.length < ICON_FORECAST_WINDOW_POLICY.minimumFutureHours) {
    fail("HOURLY_COVERAGE_INCOMPLETE", "ICON senza copertura futura sufficiente");
  }
  const pollen = camsState.pollen;
  const source = buildSource(iconOutcome, camsState, municipality);
  const modelSupport = {
    icon2i: true,
    cams: camsState.available,
    open_meteo: false,
    hourly: true,
    daily: true,
  };
  // The current-condition sample is not padding for the future forecast ribbon.
  const sample = hourlySlot(iconCurrent.row, coordinates);
  const current = {
    temperature: sample.temperature,
    condition: sample.condition,
    weathercode: null,
    wind_speed: sample.wind_speed,
    wind_direction: sample.wind_direction,
    wind_gusts: sample.wind_gusts,
    cloud_cover: sample.cloud_cover,
    precipitation: sample.precipitation,
    rain: sample.rain,
    showers: null,
    snowfall: null,
    humidity: sample.humidity,
    pressure: sample.pressure,
    feels_like: sample.feels_like,
    visibility: null,
    is_day: solar.isNight ? 0 : 1,
    city: municipality.name,
    phrase: "",
    is_bora: false,
    pop: null,
    sunrise: clockLabel(solar.sunriseMinutes),
    sunset: clockLabel(solar.sunsetMinutes),
    hourly_next_12h: hourly.slice(0, 12),
    hourly_forecast: hourly,
    pollen: pollen.summary,
    pollen_data: pollen,
    air_quality_data: camsState.air || null,
    cams_hourly_cache: buildCamsHourlyCache(camsState, municipality.istat_code),
    source,
    station: null,
    official: null,
    fallback_used: null,
    primary_source: PRIMARY_SOURCE,
    model_support: modelSupport,
    cache: {
      status: iconResult.freshness.status,
      mode: MODE,
      generated_at: icon.generated_at,
      ttl_seconds: 0,
    },
    data_quality: {
      mode: MODE,
      status: iconResult.freshness.status,
      certainty: "experimental_model",
      source: PRIMARY_SOURCE,
      run_utc: icon.run_at,
      generated_at_utc: icon.generated_at,
      fresh_until_utc: iconResult.freshness.freshUntil,
      valid_at_utc: iconCurrent.row.valid_at,
      coverage_hours: iconResult.freshness.remainingCoverageHours,
      run_age_hours: (nowMilliseconds - Date.parse(icon.run_at)) / HOUR_MS,
      native_weather_code: iconCurrent.row.condition.native_code,
      native_condition_label: iconCurrent.row.condition.native_label_it,
      native_condition_status: iconCurrent.row.condition.native_status,
      native_condition_period: "previous_hour",
      cams_status: camsState.available
        ? camsState.result.freshness.status
        : camsState.pending ? "pending" : "unavailable",
      cams_run_utc: camsState.available ? camsState.result.document.run_at : null,
      cams_valid_at_utc: camsState.available ? camsState.current.row.valid_at : null,
      cams_sample_status: camsState.available ? "current" : null,
      cams_diagnostic: camsState.diagnostic,
      municipality_istat: municipality.istat_code,
      location_scope: coordinates.source,
      catalog_point: { ...municipality.representative_point },
      grid_point: { ...municipality.model_point },
      capability_gaps: [
        "visibility",
        "precipitation_probability",
        "station_observations",
        ...(camsState.available ? [] : [camsState.pending ? "cams_pollen_pending" : "cams_pollen"]),
      ],
      flags: [...new Set([
        ...iconCurrent.row.quality_flags,
        ...(camsState.available ? [] : [camsState.pending ? "cams_pending" : "cams_unavailable"]),
      ])].sort(),
      snowfall_water_equivalent_mm: iconCurrent.row.snow_water_equivalent_mm,
      day_phase_source: solar.source,
      catalog_version: LOCAL_WEATHER_V1_CATALOG.version,
      catalog_sha256: LOCAL_WEATHER_V1_CATALOG.sha256,
    },
  };
  // Daily extrema must include morning hours even when the ribbon starts tonight.
  const daily = buildDaily([...(iconOutcome.previousDailyRows || []), ...icon.hourly]);
  for (const day of daily.forecast) {
    day.previous_run_at = iconOutcome.previousDailyRunAt || null;
  }
  const forecast = {
    city: municipality.name,
    daily_extrema_version: 2,
    ...daily,
    source,
    fallback_used: null,
    primary_source: PRIMARY_SOURCE,
    model_support: { ...modelSupport },
    cache: { ...current.cache },
    data_quality: { ...current.data_quality },
  };
  return { city: municipality.name, current, forecast };
}

// A separate, verified CAMS channel for the national ICON reader. Its identity
// is the regional CAMS catalog, never a forged regional ICON document. Both
// members still originate from one verified family/release and one timeout.
export async function fetchLocalWeatherV1CamsSupplement(
  location,
  {
    baseUrl = "/__local-weather-pilot",
    fetchImpl = globalThis.fetch,
    storage = globalThis.localStorage,
    now = Date.now,
    force = false,
    onCamsFamilyLatest,
    camsTimeoutMs = LOCAL_WEATHER_V1_CAMS_TIMEOUT_MS,
    camsContinuity = import.meta.env.VITE_CAMS_CONTINUITY_ENABLED !== "0",
    clientFactory = createWeatherV1Client,
  } = {},
) {
  const istatCode = resolveLocalWeatherV1Istat(location);
  const clock = clockFunction(now);
  if (typeof force !== "boolean") fail("INVALID_CONFIG", "force deve essere booleano");
  if (!Number.isInteger(camsTimeoutMs) || camsTimeoutMs < 1 || camsTimeoutMs > 60_000) {
    fail("INVALID_CONFIG", "timeout CAMS deve essere un intero tra 1 e 60000 ms");
  }
  if (onCamsFamilyLatest !== undefined && typeof onCamsFamilyLatest !== "function") {
    fail("INVALID_CONFIG", "onCamsFamilyLatest deve essere una funzione");
  }
  const client = clientFactory({
    baseUrl, fetchImpl, storage, now: clock, force, camsContinuity,
    catalog: LOCAL_WEATHER_V1_CATALOG,
    istatCodes: LOCAL_WEATHER_V1_ISTAT_CODES,
  });
  const outcome = client?.camsFamily && client?.camsEurope && client?.camsPollen
    ? await fetchCamsOutcomeWithTimeout(
      pairedCamsClient(client), istatCode, camsTimeoutMs, onCamsFamilyLatest,
    )
    : { ok: false, stage: "client", error: { code: "CAMS_FAMILY_INCOMPLETE" } };
  const state = resolveCamsState({
    municipality: { istat_code: istatCode }, catalog: LOCAL_WEATHER_V1_CATALOG,
  }, outcome, clockMilliseconds(clock));
  return {
    municipality_istat: istatCode,
    catalog: LOCAL_WEATHER_V1_CATALOG,
    available: state.available,
    status: state.available ? state.result.freshness.status : "unavailable",
    source: buildCamsSource(state),
    pollen: state.pollen.summary || null,
    pollen_data: state.pollen,
    air_quality_data: state.air || null,
    cams_hourly_cache: buildCamsHourlyCache(state, istatCode),
    fresh_until_utc: state.result?.freshness?.freshUntil || state.result?.document?.freshness?.fresh_until || null,
    usable_until_utc: state.result?.freshness?.usableUntil || state.result?.document?.freshness?.usable_until || null,
    diagnostic: state.diagnostic,
  };
}

export async function fetchLocalWeatherV1Bundle(
  location,
  {
    baseUrl = "/__local-weather-pilot",
    fetchImpl = globalThis.fetch,
    storage = globalThis.localStorage,
    now = Date.now,
    force = false,
    deferCams = false,
    onCamsUpdate,
    onCamsFailure,
    onIconLatest,
    onCamsFamilyLatest,
    retainedIconBundle,
    camsTimeoutMs = LOCAL_WEATHER_V1_CAMS_TIMEOUT_MS,
    camsContinuity = import.meta.env.VITE_CAMS_CONTINUITY_ENABLED !== "0",
    clientFactory = createWeatherV1Client,
  } = {},
) {
  const istatCode = resolveLocalWeatherV1Istat(location);
  const clock = clockFunction(now);
  if (typeof force !== "boolean") fail("INVALID_CONFIG", "force deve essere booleano");
  if (typeof deferCams !== "boolean") fail("INVALID_CONFIG", "deferCams deve essere booleano");
  if (onCamsUpdate !== undefined && typeof onCamsUpdate !== "function") {
    fail("INVALID_CONFIG", "onCamsUpdate deve essere una funzione");
  }
  if (onCamsFailure !== undefined && typeof onCamsFailure !== "function") {
    fail("INVALID_CONFIG", "onCamsFailure deve essere una funzione");
  }
  if (onIconLatest !== undefined && typeof onIconLatest !== "function") {
    fail("INVALID_CONFIG", "onIconLatest deve essere una funzione");
  }
  if (onCamsFamilyLatest !== undefined && typeof onCamsFamilyLatest !== "function") {
    fail("INVALID_CONFIG", "onCamsFamilyLatest deve essere una funzione");
  }
  if (!Number.isInteger(camsTimeoutMs) || camsTimeoutMs < 1 || camsTimeoutMs > 60_000) {
    fail("INVALID_CONFIG", "timeout CAMS deve essere un intero tra 1 e 60000 ms");
  }
  if (retainedIconBundle) assertRetainedIconIdentity(retainedIconBundle, istatCode);
  const readPrefetchedObject = getPilotWeatherPrefetchReader({ baseUrl, istatCode });
  const client = clientFactory({
    baseUrl,
    fetchImpl,
    storage,
    now: clock,
    camsContinuity,
    catalog: LOCAL_WEATHER_V1_CATALOG,
    istatCodes: LOCAL_WEATHER_V1_ISTAT_CODES,
    force,
    iconWindowPolicy: ICON_FORECAST_WINDOW_POLICY,
    ...(readPrefetchedObject ? { readPrefetchedObject } : {}),
  });
  if (!client?.icon2i) fail("INVALID_CLIENT", "client ICON weather v1 locale mancante");
  const camsClientMissing = {
    ok: false,
    stage: "client",
    error: { code: "CAMS_CLIENT_UNAVAILABLE" },
  };
  const camsPromise = client.camsPollen
    ? fetchCamsOutcomeWithTimeout(
      pairedCamsClient(client),
      istatCode,
      camsTimeoutMs,
      onCamsFamilyLatest,
    )
    : Promise.resolve(camsClientMissing);
  if (retainedIconBundle) {
    const supplement = camsPromise.then(outcome => buildRetainedIconCamsSupplement(
      retainedIconBundle, outcome, clockMilliseconds(clock), istatCode,
    ));
    if (!deferCams) return supplement;
    void supplement.then(bundle => deliverCamsUpdate(onCamsUpdate, bundle)).catch(error => {
      const observerFailure = camsFamilyObserverFailures.has(error);
      if (observerFailure) {
        try { onCamsFailure?.(error); } catch { /* Safety failure was already applied by its observer. */ }
      }
      try {
        deliverCamsUpdate(onCamsUpdate, buildRetainedIconCamsSupplement(
          retainedIconBundle, { ok: false, stage: "adapt", error }, clockMilliseconds(clock), istatCode,
        ));
      } catch {
        // Even an internal adaptation/clock failure must release deduplication;
        // it is not a successful CAMS verification and publishes no payload.
        if (!observerFailure) {
          try { onCamsFailure?.(error); } catch { /* Optional observer only. */ }
        }
      }
    });
    return retainedIconBundle;
  }
  const iconPromise = fetchIconOutcome(client.icon2i, istatCode, clock, onIconLatest);
  const iconOutcome = await iconPromise;
  if (!iconOutcome.ok) {
    if (iconOutcome.error instanceof Error) throw iconOutcome.error;
    fail("ICON_UNAVAILABLE", "dati ICON obbligatori non disponibili");
  }
  const nowMilliseconds = clockMilliseconds(clock);
  // The current run may start in the afternoon. Recover only missing earlier
  // hours of today's forecast; never replace newer rows or alter the ribbon.
  const latest = iconOutcome.stages.latest;
  const previous = latest?.document?.previous;
  const firstTime = rowTimestamp(iconOutcome.result.document.hourly[0], "ICON");
  const today = zonedParts(nowMilliseconds).date;
  if (previous && !iconOutcome.usedPreviousRun
    && zonedParts(firstTime).date === today && zonedParts(firstTime).hour > 0) {
    try {
      const manifest = await client.icon2i.fetchManifest(latest, undefined, { previous: true });
      const result = await client.icon2i.fetchMunicipality(manifest, istatCode);
      iconOutcome.previousDailyRows = result.document.hourly.filter(row => {
        const time = rowTimestamp(row, "ICON");
        return time < firstTime && zonedParts(time).date === today;
      });
      iconOutcome.previousDailyRunAt = result.document.run_at;
    } catch {
      // Missing historical enrichment must not prevent current weather delivery.
      iconOutcome.previousDailyRows = [];
    }
  }
  if (deferCams) {
    const pendingBundle = buildBundle(
      location,
      nowMilliseconds,
      iconOutcome,
      { ok: false, pending: true, stage: "pending" },
    );
    void camsPromise
      .then((camsOutcome) => buildBundle(
        location,
        clockMilliseconds(clock),
        iconOutcome,
        camsOutcome,
      ))
      .then((bundle) => deliverCamsUpdate(onCamsUpdate, bundle))
      .catch((error) => {
        const observerFailure = camsFamilyObserverFailures.has(error);
        if (observerFailure) {
          try { onCamsFailure?.(error); } catch { /* Safety failure was already applied by its observer. */ }
        }
        try {
          const unavailable = buildBundle(location, nowMilliseconds, iconOutcome, {
            ok: false,
            stage: "adapt",
            error,
          });
          deliverCamsUpdate(onCamsUpdate, unavailable);
        } catch {
          // ICON was already delivered; a failed enrichment must remain non-fatal.
          if (!observerFailure) {
            try { onCamsFailure?.(error); } catch { /* Optional observer only. */ }
          }
        }
      });
    return pendingBundle;
  }
  const camsOutcome = await camsPromise;
  return buildBundle(location, clockMilliseconds(clock), iconOutcome, camsOutcome);
}

export async function fetchLocalWeatherV1Bootstrap(location, options) {
  return fetchLocalWeatherV1Bundle(location, options);
}

export async function fetchLocalWeatherV1Conditions(location, options) {
  const bundle = await fetchLocalWeatherV1Bundle(location, options);
  return { city: bundle.city, current: bundle.current };
}
