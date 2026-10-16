import { sha256Hex } from "./weatherV1Client";

const HOUR_MS = 60 * 60 * 1000;
const MAX_V1_SAMPLES = 193;
const V2_SAMPLE_COUNT = 97;

export const CAMS_HOURLY_CACHE_VERSION = 2;
export const CAMS_POLLEN_FIELDS = Object.freeze([
  ["alder_pollen", "ontano"],
  ["birch_pollen", "betulla"],
  ["grass_pollen", "graminacee"],
  ["mugwort_pollen", "artemisia"],
  ["olive_pollen", "olivo"],
  ["ragweed_pollen", "ambrosia"],
]);
export const CAMS_AIR_FIELDS = Object.freeze([
  "particulate_matter_2.5um",
  "particulate_matter_10um",
  "ozone",
  "nitrogen_dioxide",
]);

function exactKeys(value, expected) {
  return value && typeof value === "object" && !Array.isArray(value)
    && Object.keys(value).sort().join("\n") === [...expected].sort().join("\n");
}

function validNumber(value) {
  return value === null || (Number.isFinite(value) && value >= 0);
}

function validPollenVariables(pollenVariables) {
  if (!Array.isArray(pollenVariables)
    || pollenVariables.length !== CAMS_POLLEN_FIELDS.length) return false;
  const variables = new Map(pollenVariables.map(variable => [variable?.id, variable]));
  return variables.size === CAMS_POLLEN_FIELDS.length
    && CAMS_POLLEN_FIELDS.every(([id, uiKey]) => {
      const variable = variables.get(id);
      return exactKeys(variable, ["id", "ui_key", "category", "unit", "validation_status"])
        && variable.ui_key === uiKey
        && variable.category === "pollen"
        && typeof variable.unit === "string"
        && typeof variable.validation_status === "string";
    });
}

function validV2PollenVariables(pollenVariables) {
  return pollenVariables?.length === CAMS_POLLEN_FIELDS.length
    && validPollenVariables(pollenVariables)
    && pollenVariables.map(variable => variable.id).join("\n")
      === CAMS_POLLEN_FIELDS.map(([id]) => id).join("\n");
}

function validCanonicalFlags(flags) {
  if (!Array.isArray(flags)) return false;
  const sorted = [...new Set(flags)].sort();
  return flags.every(flag => typeof flag === "string" && flag && flag === flag.trim())
    && sorted.length === flags.length
    && sorted.every((flag, index) => flag === flags[index]);
}

function bytesToBase64(bytes) {
  let binary = "";
  for (let offset = 0; offset < bytes.length; offset += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + 0x8000));
  }
  return globalThis.btoa(binary);
}

function base64ToBytes(value, expectedBytes) {
  if (typeof value !== "string" || value.length !== Math.ceil(expectedBytes / 3) * 4
    || !/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(value)) return null;
  try {
    const binary = globalThis.atob(value);
    if (binary.length !== expectedBytes) return null;
    const bytes = Uint8Array.from(binary, character => character.charCodeAt(0));
    return bytesToBase64(bytes) === value ? bytes : null;
  } catch {
    return null;
  }
}

function cacheView(cache, samples) {
  return {
    stored: cache,
    municipality_istat: cache.municipality_istat,
    catalog_sha256: cache.catalog_sha256,
    run_utc: cache.run_utc,
    generated_at_utc: cache.generated_at_utc,
    fresh_until_utc: cache.fresh_until_utc,
    usable_until_utc: cache.usable_until_utc,
    pollen_variables: cache.pollen_variables,
    samples,
  };
}

function decodeV1(cache) {
  if (!exactKeys(cache, [
    "version", "municipality_istat", "catalog_sha256", "run_utc", "generated_at_utc",
    "fresh_until_utc", "usable_until_utc", "pollen_variables", "samples", "sha256",
  ]) || cache.version !== 1
    || !Number.isFinite(Date.parse(cache.generated_at_utc))
    || !Number.isFinite(Date.parse(cache.fresh_until_utc))
    || !Number.isFinite(Date.parse(cache.usable_until_utc))
    || !/^[0-9a-f]{64}$/.test(cache.sha256)
    || !validPollenVariables(cache.pollen_variables)
    || !Array.isArray(cache.samples)
    || !cache.samples.length
    || cache.samples.length > MAX_V1_SAMPLES) return null;
  const { sha256, ...payload } = cache;
  if (sha256Hex(JSON.stringify(payload)) !== sha256) return null;
  let previous = null;
  for (const sample of cache.samples) {
    if (!exactKeys(sample, ["valid_at_utc", "pollen_values", "pollen_quality_flags", "air_values"])) return null;
    const timestamp = Date.parse(sample.valid_at_utc);
    if (!Number.isFinite(timestamp) || (previous !== null && timestamp - previous !== HOUR_MS)) return null;
    previous = timestamp;
    if (!exactKeys(sample.pollen_values, CAMS_POLLEN_FIELDS.map(([, uiKey]) => uiKey))
      || !exactKeys(sample.pollen_quality_flags, CAMS_POLLEN_FIELDS.map(([id]) => id))
      || CAMS_POLLEN_FIELDS.some(([id, uiKey]) => !validNumber(sample.pollen_values[uiKey])
        || !Array.isArray(sample.pollen_quality_flags[id])
        || sample.pollen_quality_flags[id].some(flag => typeof flag !== "string"))
      || !sample.air_values || typeof sample.air_values !== "object" || Array.isArray(sample.air_values)
      || Object.keys(sample.air_values).some(id => !id || !validNumber(sample.air_values[id]))) return null;
  }
  return cacheView(cache, cache.samples);
}

function timestampLike(firstTimestamp, milliseconds) {
  const canonical = new Date(milliseconds).toISOString();
  return firstTimestamp.endsWith(".000Z") ? canonical : canonical.replace(".000Z", "Z");
}

function canonicalUtc(value) {
  if (typeof value !== "string"
    || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.000)?Z$/.test(value)) return false;
  const milliseconds = Date.parse(value);
  if (!Number.isFinite(milliseconds)) return false;
  return timestampLike(value, milliseconds) === value;
}

function decodeV2(cache) {
  if (!exactKeys(cache, [
    "version", "municipality_istat", "catalog_sha256", "run_utc", "generated_at_utc",
    "fresh_until_utc", "usable_until_utc", "first_valid_at_utc", "step_seconds",
    "sample_count", "pollen_variables", "air_variable_ids", "values_f64_b64",
    "quality_flag_sets", "pollen_quality_refs_u16_b64", "sha256",
  ]) || cache.version !== CAMS_HOURLY_CACHE_VERSION
    || !Number.isSafeInteger(cache.sample_count)
    || cache.sample_count !== V2_SAMPLE_COUNT
    || cache.step_seconds !== HOUR_MS / 1000
    || !validV2PollenVariables(cache.pollen_variables)
    || !Array.isArray(cache.air_variable_ids)
    || cache.air_variable_ids.join("\n") !== CAMS_AIR_FIELDS.join("\n")
    || !Array.isArray(cache.quality_flag_sets)
    || cache.quality_flag_sets.length < 1 || cache.quality_flag_sets.length > 0x10000
    || !/^[0-9a-f]{64}$/.test(cache.sha256)) return null;
  const timestampFields = [
    cache.run_utc, cache.generated_at_utc, cache.fresh_until_utc,
    cache.usable_until_utc, cache.first_valid_at_utc,
  ];
  const timestamps = timestampFields.map(Date.parse);
  if (timestampFields.some(value => !canonicalUtc(value))
    || timestamps.some(timestamp => !Number.isFinite(timestamp))
    || cache.first_valid_at_utc !== cache.run_utc
    || timestamps[2] > timestamps[3]) return null;
  const { sha256, ...payload } = cache;
  if (sha256Hex(JSON.stringify(payload)) !== sha256) return null;
  const uniqueFlagSets = new Set();
  for (const flags of cache.quality_flag_sets) {
    if (!validCanonicalFlags(flags)) return null;
    const identity = JSON.stringify(flags);
    if (uniqueFlagSets.has(identity)) return null;
    uniqueFlagSets.add(identity);
  }
  const valueCount = cache.sample_count * (CAMS_POLLEN_FIELDS.length + CAMS_AIR_FIELDS.length);
  const valuesBytes = base64ToBytes(cache.values_f64_b64, valueCount * Float64Array.BYTES_PER_ELEMENT);
  const refCount = cache.sample_count * CAMS_POLLEN_FIELDS.length;
  const refsBytes = base64ToBytes(cache.pollen_quality_refs_u16_b64, refCount * Uint16Array.BYTES_PER_ELEMENT);
  if (!valuesBytes || !refsBytes) return null;
  const values = new DataView(valuesBytes.buffer, valuesBytes.byteOffset, valuesBytes.byteLength);
  const refs = new DataView(refsBytes.buffer, refsBytes.byteOffset, refsBytes.byteLength);
  const samples = [];
  let valueOffset = 0;
  let refOffset = 0;
  for (let sampleIndex = 0; sampleIndex < cache.sample_count; sampleIndex += 1) {
    const rowValues = [];
    for (let fieldIndex = 0; fieldIndex < CAMS_POLLEN_FIELDS.length + CAMS_AIR_FIELDS.length; fieldIndex += 1) {
      const value = values.getFloat64(valueOffset, true);
      valueOffset += Float64Array.BYTES_PER_ELEMENT;
      const decoded = Number.isNaN(value) ? null : value;
      if (!validNumber(decoded)) return null;
      rowValues.push(decoded);
    }
    const pollenQualityFlags = {};
    for (const [id] of CAMS_POLLEN_FIELDS) {
      const reference = refs.getUint16(refOffset, true);
      refOffset += Uint16Array.BYTES_PER_ELEMENT;
      if (reference >= cache.quality_flag_sets.length) return null;
      pollenQualityFlags[id] = [...cache.quality_flag_sets[reference]];
    }
    samples.push({
      valid_at_utc: timestampLike(
        cache.first_valid_at_utc,
        timestamps[4] + sampleIndex * cache.step_seconds * 1000,
      ),
      pollen_values: Object.fromEntries(CAMS_POLLEN_FIELDS
        .map(([, uiKey], index) => [uiKey, rowValues[index]])),
      pollen_quality_flags: pollenQualityFlags,
      air_values: Object.fromEntries(CAMS_AIR_FIELDS.map((id, index) => [
        id,
        rowValues[CAMS_POLLEN_FIELDS.length + index],
      ])),
    });
  }
  return cacheView(cache, samples);
}

export function decodeVerifiedCamsHourlyCache(cache, {
  municipalityIstat,
  catalogSha256,
  runUtc,
} = {}) {
  if (!cache || cache.municipality_istat !== municipalityIstat
    || cache.catalog_sha256 !== catalogSha256
    || cache.run_utc !== runUtc) return null;
  if (cache.version === 1) return decodeV1(cache);
  if (cache.version === CAMS_HOURLY_CACHE_VERSION) return decodeV2(cache);
  return null;
}

export function encodeCamsHourlyCacheV2({
  municipality_istat,
  catalog_sha256,
  run_utc,
  generated_at_utc,
  fresh_until_utc,
  usable_until_utc,
  pollen_variables,
  samples,
}) {
  if (!validV2PollenVariables(pollen_variables)
    || !Array.isArray(samples) || samples.length !== V2_SAMPLE_COUNT) {
    throw new TypeError("invalid CAMS hourly cache input");
  }
  const firstTimestamp = samples[0]?.valid_at_utc;
  const firstMilliseconds = Date.parse(firstTimestamp);
  if (![run_utc, generated_at_utc, fresh_until_utc, usable_until_utc, firstTimestamp]
    .every(canonicalUtc)
    || !Number.isFinite(firstMilliseconds)
    || firstTimestamp !== run_utc
    || Date.parse(fresh_until_utc) > Date.parse(usable_until_utc)) {
    throw new TypeError("invalid CAMS hourly cache timestamps");
  }
  const fieldCount = CAMS_POLLEN_FIELDS.length + CAMS_AIR_FIELDS.length;
  const valuesBytes = new Uint8Array(samples.length * fieldCount * Float64Array.BYTES_PER_ELEMENT);
  const values = new DataView(valuesBytes.buffer);
  const refsBytes = new Uint8Array(samples.length * CAMS_POLLEN_FIELDS.length * Uint16Array.BYTES_PER_ELEMENT);
  const refs = new DataView(refsBytes.buffer);
  const qualityFlagSets = [];
  const qualityFlagIndexes = new Map();
  let valueOffset = 0;
  let refOffset = 0;
  const writeValue = (value) => {
    if (!validNumber(value)) throw new TypeError("invalid CAMS hourly cache value");
    values.setFloat64(valueOffset, value === null ? Number.NaN : value, true);
    valueOffset += Float64Array.BYTES_PER_ELEMENT;
  };
  for (const [sampleIndex, sample] of samples.entries()) {
    if (Date.parse(sample?.valid_at_utc) !== firstMilliseconds + sampleIndex * HOUR_MS
      || !exactKeys(sample?.pollen_values, CAMS_POLLEN_FIELDS.map(([, uiKey]) => uiKey))
      || !exactKeys(sample?.pollen_quality_flags, CAMS_POLLEN_FIELDS.map(([id]) => id))
      || !exactKeys(sample?.air_values, CAMS_AIR_FIELDS)) {
      throw new TypeError("invalid CAMS hourly cache sample");
    }
    for (const [, uiKey] of CAMS_POLLEN_FIELDS) writeValue(sample.pollen_values[uiKey]);
    for (const id of CAMS_AIR_FIELDS) writeValue(sample.air_values[id]);
    for (const [id] of CAMS_POLLEN_FIELDS) {
      const flags = sample.pollen_quality_flags[id];
      if (!validCanonicalFlags(flags)) {
        throw new TypeError("invalid CAMS hourly cache quality flags");
      }
      const identity = JSON.stringify(flags);
      let reference = qualityFlagIndexes.get(identity);
      if (reference === undefined) {
        reference = qualityFlagSets.length;
        if (reference > 0xffff) throw new TypeError("too many CAMS quality flag sets");
        qualityFlagIndexes.set(identity, reference);
        qualityFlagSets.push([...flags]);
      }
      refs.setUint16(refOffset, reference, true);
      refOffset += Uint16Array.BYTES_PER_ELEMENT;
    }
  }
  const payload = {
    version: CAMS_HOURLY_CACHE_VERSION,
    municipality_istat,
    catalog_sha256,
    run_utc,
    generated_at_utc,
    fresh_until_utc,
    usable_until_utc,
    first_valid_at_utc: firstTimestamp,
    step_seconds: HOUR_MS / 1000,
    sample_count: samples.length,
    pollen_variables: CAMS_POLLEN_FIELDS.map(([id]) => ({
      ...pollen_variables.find(variable => variable.id === id),
    })),
    air_variable_ids: [...CAMS_AIR_FIELDS],
    values_f64_b64: bytesToBase64(valuesBytes),
    quality_flag_sets: qualityFlagSets,
    pollen_quality_refs_u16_b64: bytesToBase64(refsBytes),
  };
  return { ...payload, sha256: sha256Hex(JSON.stringify(payload)) };
}
