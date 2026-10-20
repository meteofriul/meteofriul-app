import { countIconFutureHours } from "./iconForecastWindow";
import { validateCamsContinuity } from "./camsContinuityPolicy";
import { isValidIconAccumulationQuality } from "./iconAccumulationQuality";

const SCHEMA_VERSION = 1;
const CATALOG_VERSION = "istat-2026-irdat-2006-representative-points-v1";
const MUNICIPALITY_COUNT = 215;
const LATEST_KIND = "meteofriul.weather.latest";
const MANIFEST_KIND = "meteofriul.weather.run_manifest";
const CAMS_FAMILY = "cams";
const CAMS_FAMILY_SCOPE = "families/cams";
const CAMS_FAMILY_LATEST_KIND = "meteofriul.weather.cams_family_latest";
const CAMS_FAMILY_RELEASE_KIND = "meteofriul.weather.cams_family_release";
const CACHE_VERSION = 4;
const CACHE_PREFIX = "meteofriul:weather-v1:v4";
const LEGACY_CACHE_PREFIXES = Object.freeze([
  "meteofriul:weather-v1:v2",
  "meteofriul:weather-v1:v3",
]);
// Four real-world CAMS municipality payloads (~376 KiB each) plus metadata fit,
// while the per-provider cache remains comfortably bounded for localStorage.
const CACHE_BODY_BUDGET_BYTES = 1792 * 1024;
const CACHE_MANIFEST_SLOTS = 2;
const CACHE_RELEASE_SLOTS = 2;
const CACHE_MUNICIPALITY_SLOTS = 4;
const MAX_LATEST_BYTES = 128 * 1024;
const MAX_RELEASE_BYTES = 128 * 1024;
const MAX_MANIFEST_BYTES = 2 * 1024 * 1024;
const MAX_PAYLOAD_BYTES = 512 * 1024;
const HOUR_MS = 60 * 60 * 1000;

const RAW_CACHE_PROVIDERS = new Set([
  "icon2i",
  "cams_europe",
  "cams_europe_pollen",
  CAMS_FAMILY_SCOPE,
]);
const RAW_CACHE_SLOT_IDS = new Set([
  "latest:0",
  "release:0",
  "release:1",
  "continuity:0",
  "continuity:1",
  "manifest:0",
  "manifest:1",
  "municipality:0",
  "municipality:1",
  "municipality:2",
  "municipality:3",
  "lru",
]);

const FALLBACK_VOLATILE_CACHE = {
  values: new Map(),
  tombstones: new Set(),
  camsFamilies: new Map(),
};
const VOLATILE_CACHE_BY_STORAGE = new WeakMap();
const LEGACY_CACHE_CLEANUP_BY_STORAGE = new WeakMap();
const OBSOLETE_V4_CACHE_CLEANUP_BY_STORAGE = new WeakMap();
const IN_FLIGHT_BY_FETCH = new WeakMap();
const PREFETCH_BLOCKED_MANIFESTS = new WeakSet();

function rawCacheScopeForKey(key) {
  const prefix = `${CACHE_PREFIX}:`;
  if (typeof key !== "string" || !key.startsWith(prefix)) return null;
  const [scope, provider, ...slotParts] = key.slice(prefix.length).split(":");
  const slotId = slotParts.join(":");
  if (!/^[0-9a-f]{16}$/.test(scope)
    || !RAW_CACHE_PROVIDERS.has(provider)
    || !RAW_CACHE_SLOT_IDS.has(slotId)) return null;
  return scope;
}

export const WEATHER_V1_PROVIDERS = Object.freeze({
  ICON2I: "icon2i",
  CAMS_EUROPE: "cams_europe",
  CAMS_EUROPE_POLLEN: "cams_europe_pollen",
});

const PROVIDER_CONTRACTS = Object.freeze({
  icon2i: Object.freeze({
    property: "icon2i",
    horizonHours: 72,
    payloadKind: "meteofriul.weather.icon.municipality",
    model: Object.freeze({ id: "icon-2i", product: "surface_pressure_levels" }),
    source: Object.freeze({
      attribution: "Agenzia ItaliaMeteo / Arpae Emilia-Romagna Idro-Meteo-Clima",
      license: "CC BY 4.0",
      license_url: "https://creativecommons.org/licenses/by/4.0/",
    }),
    freshness: Object.freeze({
      policyId: "icon2i_48h_v1",
      freshHours: 18,
      usableHours: 30,
      requiredFutureHours: 48,
    }),
  }),
  cams_europe: Object.freeze({
    property: "camsEurope",
    horizonHours: 96,
    payloadKind: "meteofriul.weather.cams.municipality",
    model: Object.freeze({
      id: "cams-european-regional-ensemble",
      dataset: "cams-europe-air-quality-forecasts",
      forecast_type: "ensemble",
      statistic: "median",
      level: "surface",
    }),
    source: Object.freeze({
      attribution:
        "Copernicus Atmosphere Monitoring Service (CAMS), European regional ensemble providers, Atmosphere Data Store (ADS)",
      license: "CC BY 4.0",
      license_url: "https://creativecommons.org/licenses/by/4.0/",
      doi: "10.24381/a4005cee",
    }),
    freshness: Object.freeze({
      policyId: "cams_current_v1",
      freshHours: 24,
      usableHours: 30,
      requiredFutureHours: 0,
    }),
  }),
  cams_europe_pollen: Object.freeze({
    property: "camsPollen",
    horizonHours: 96,
    payloadKind: "meteofriul.weather.cams.pollen_municipality",
    model: Object.freeze({
      id: "cams-european-regional-ensemble",
      dataset: "cams-europe-air-quality-forecasts",
      forecast_type: "ensemble",
      statistic: "median",
      level: "surface",
    }),
    source: Object.freeze({
      attribution:
        "Copernicus Atmosphere Monitoring Service (CAMS), European regional ensemble providers, Atmosphere Data Store (ADS)",
      license: "CC BY 4.0",
      license_url: "https://creativecommons.org/licenses/by/4.0/",
      doi: "10.24381/a4005cee",
    }),
    freshness: Object.freeze({
      policyId: "cams_pollen_current_v1",
      freshHours: 24,
      usableHours: 30,
      requiredFutureHours: 0,
    }),
  }),
});

const ICON_UNITS = Object.freeze({
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
});

const ICON_CONDITIONS = Object.freeze({
  0: ["Sereno", "clear", "conditionSun", "Sun", "clear"],
  1: ["Poco nuvoloso", "mostly_sunny", "conditionMostlySunny", "MostlySunny", "partly"],
  2: ["Parzialmente nuvoloso", "partly_cloudy", "conditionPartlyCloudy", "PartlyCloudy", "partly"],
  3: ["Molto nuvoloso o coperto", "overcast", "conditionOvercast", "Overcast", "cloud"],
  45: ["Nebbia", "fog", "conditionFog", "Fog", "fog"],
  48: ["Nebbia con deposito di brina", "fog", "conditionFog", "Fog", "fog"],
  51: ["Pioviggine debole", "drizzle", "conditionLightRain", "LightRain", "rain"],
  53: ["Pioviggine moderata", "drizzle", "conditionLightRain", "LightRain", "rain"],
  55: ["Pioviggine intensa", "drizzle", "conditionLightRain", "LightRain", "rain"],
  56: ["Pioviggine gelata debole", "freezing_drizzle", "conditionFreezingDrizzle", "Sleet", "rain"],
  57: ["Pioviggine gelata moderata o intensa", "freezing_drizzle", "conditionFreezingDrizzle", "Sleet", "rain"],
  61: ["Pioggia debole", "rain", "conditionRain", "Rain", "rain"],
  63: ["Pioggia moderata", "rain", "conditionRain", "Rain", "rain"],
  65: ["Pioggia intensa", "heavy_rain", "conditionHeavyRain", "HeavyRain", "rain"],
  66: ["Pioggia gelata debole", "freezing_rain", "conditionFreezingRain", "Sleet", "rain"],
  67: ["Pioggia gelata moderata o intensa", "freezing_rain", "conditionFreezingRain", "Sleet", "rain"],
  71: ["Nevicata debole", "snow", "conditionSnow", "Snow", "snow"],
  73: ["Nevicata moderata", "snow", "conditionSnow", "Snow", "snow"],
  75: ["Nevicata intensa", "snow", "conditionSnow", "Snow", "snow"],
  77: ["Granuli di neve", "snow_grains", "conditionSnow", "Snow", "snow"],
  80: ["Rovesci di pioggia deboli", "showers", "conditionShowers", "Showers", "rain"],
  81: ["Rovesci di pioggia moderati o intensi", "showers", "conditionShowers", "Showers", "rain"],
  82: ["Rovesci di pioggia violenti", "showers", "conditionShowers", "Showers", "rain"],
  85: ["Rovesci di neve deboli", "snow_showers", "conditionSnow", "Snow", "snow"],
  86: ["Rovesci di neve moderati o intensi", "snow_showers", "conditionSnow", "Snow", "snow"],
  95: ["Temporale debole o moderato", "storm", "conditionStorm", "Storm", "storm"],
  96: [
    "Temporale con grandine o temporale forte",
    "strong_storm",
    "conditionStrongStorm",
    "StrongStorm",
    "storm",
  ],
});

const CAMS_VARIABLE_SPECS = Object.freeze([
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
]);

const CAMS_VARIABLES = Object.freeze(
  CAMS_VARIABLE_SPECS.map(([id, ui_key, category, unit, validation_status]) =>
    Object.freeze({ id, ui_key, category, unit, validation_status }),
  ),
);
const CAMS_VARIABLE_IDS = Object.freeze(CAMS_VARIABLES.map(({ id }) => id));
const CAMS_POLLEN_VARIABLES = Object.freeze(
  CAMS_VARIABLES.filter(({ category }) => category === "pollen"),
);
const CAMS_POLLEN_VARIABLE_IDS = Object.freeze(
  CAMS_POLLEN_VARIABLES.map(({ id }) => id),
);
const CAMS_POLLEN_PROJECTION = Object.freeze({
  id: "cams_pollen_hourly_v1",
  source_provider: WEATHER_V1_PROVIDERS.CAMS_EUROPE,
  source_kind: "meteofriul.weather.cams.municipality",
  retained_variable_ids: CAMS_POLLEN_VARIABLE_IDS,
});

const ISO_UTC_SECONDS = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/;
const RUN_ID = /^\d{8}T\d{6}Z$/;
const ISTAT_CODE = /^\d{6}$/;
const SHA256 = /^[0-9a-f]{64}$/;

export class WeatherV1ClientError extends Error {
  constructor(code, message, options) {
    super(message, options);
    this.name = "WeatherV1ClientError";
    this.code = code;
  }
}

function fail(code, message, cause) {
  throw new WeatherV1ClientError(code, message, cause ? { cause } : undefined);
}

function isRecord(value) {
  if (value === null || typeof value !== "object" || Array.isArray(value)) return false;
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

function exactKeys(value, expected, label) {
  if (!isRecord(value)) fail("INVALID_DOCUMENT", `${label} deve essere un oggetto`);
  const actual = Object.keys(value).sort();
  const wanted = [...expected].sort();
  if (actual.length !== wanted.length || actual.some((key, index) => key !== wanted[index])) {
    fail("INVALID_DOCUMENT", `${label} contiene campi mancanti o non previsti`);
  }
  return value;
}

function nonEmptyString(value, label) {
  if (typeof value !== "string" || !value || value !== value.trim()) {
    fail("INVALID_DOCUMENT", `${label} non e una stringa canonica`);
  }
  return value;
}

function finiteNumber(value, label, { minimum = -Infinity, maximum = Infinity } = {}) {
  if (typeof value !== "number" || !Number.isFinite(value) || value < minimum || value > maximum) {
    fail("INVALID_DOCUMENT", `${label} non e un numero valido`);
  }
  return value;
}

function integer(value, label, { minimum = Number.MIN_SAFE_INTEGER } = {}) {
  if (!Number.isSafeInteger(value) || value < minimum) {
    fail("INVALID_DOCUMENT", `${label} non e un intero valido`);
  }
  return value;
}

function parseUtc(value, label, { onHour = false } = {}) {
  if (typeof value !== "string" || !ISO_UTC_SECONDS.test(value)) {
    fail("INVALID_DOCUMENT", `${label} non usa UTC a secondi`);
  }
  const milliseconds = Date.parse(value);
  if (!Number.isFinite(milliseconds)) fail("INVALID_DOCUMENT", `${label} non e una data valida`);
  const canonical = new Date(milliseconds).toISOString().replace(".000Z", "Z");
  if (canonical !== value || (onHour && !value.endsWith(":00:00Z"))) {
    fail("INVALID_DOCUMENT", `${label} non e una data UTC canonica`);
  }
  return milliseconds;
}

function iso(milliseconds) {
  return new Date(milliseconds).toISOString().replace(".000Z", "Z");
}

function runIdFor(runAt) {
  return `${runAt.slice(0, 4)}${runAt.slice(5, 7)}${runAt.slice(8, 10)}T${runAt.slice(11, 13)}${runAt.slice(14, 16)}${runAt.slice(17, 19)}Z`;
}

function validateRunIdentity(sourceRunId, runAt, label) {
  parseUtc(runAt, `${label}.run_at`, { onHour: true });
  if (typeof sourceRunId !== "string" || !RUN_ID.test(sourceRunId) || sourceRunId !== runIdFor(runAt)) {
    fail("RUN_MISMATCH", `${label} identifica un run non canonico`);
  }
}

function compareJsonKeys(left, right) {
  const a = Array.from(left, (character) => character.codePointAt(0));
  const b = Array.from(right, (character) => character.codePointAt(0));
  for (let index = 0; index < Math.min(a.length, b.length); index += 1) {
    if (a[index] !== b[index]) return a[index] - b[index];
  }
  return a.length - b.length;
}

class CompactJsonParser {
  constructor(text, label) {
    this.text = text;
    this.label = label;
    this.position = 0;
  }

  error(message) {
    fail("INVALID_JSON", `${this.label}: ${message}`);
  }

  parse() {
    if (!this.text || this.text.charCodeAt(0) === 0xfeff) this.error("body vuoto o con BOM");
    const value = this.value();
    if (this.position !== this.text.length) this.error("dati dopo il documento JSON");
    return value;
  }

  value() {
    const token = this.text[this.position];
    if (token === "{") return this.object();
    if (token === "[") return this.array();
    if (token === '"') return this.string();
    if (token === "t" && this.consume("true")) return true;
    if (token === "f" && this.consume("false")) return false;
    if (token === "n" && this.consume("null")) return null;
    if (token === "-" || (token >= "0" && token <= "9")) return this.number();
    if (/\s/.test(token || "")) this.error("spazi fuori dalle stringhe non canonici");
    this.error("valore JSON non valido");
  }

  consume(expected) {
    if (this.text.slice(this.position, this.position + expected.length) !== expected) return false;
    this.position += expected.length;
    return true;
  }

  object() {
    this.position += 1;
    const result = Object.create(null);
    const keys = new Set();
    let previous = null;
    if (this.text[this.position] === "}") {
      this.position += 1;
      return result;
    }
    while (this.position < this.text.length) {
      if (this.text[this.position] !== '"') this.error("chiave oggetto non valida");
      const key = this.string();
      if (keys.has(key)) this.error(`chiave duplicata ${key}`);
      if (previous !== null && compareJsonKeys(previous, key) >= 0) {
        this.error("chiavi oggetto non ordinate canonicamente");
      }
      keys.add(key);
      previous = key;
      if (this.text[this.position] !== ":") this.error("separatore chiave/valore mancante");
      this.position += 1;
      Object.defineProperty(result, key, {
        value: this.value(),
        enumerable: true,
        configurable: true,
        writable: true,
      });
      const delimiter = this.text[this.position];
      if (delimiter === "}") {
        this.position += 1;
        return result;
      }
      if (delimiter !== ",") this.error("separatore oggetto mancante");
      this.position += 1;
    }
    this.error("oggetto JSON incompleto");
  }

  array() {
    this.position += 1;
    const result = [];
    if (this.text[this.position] === "]") {
      this.position += 1;
      return result;
    }
    while (this.position < this.text.length) {
      result.push(this.value());
      const delimiter = this.text[this.position];
      if (delimiter === "]") {
        this.position += 1;
        return result;
      }
      if (delimiter !== ",") this.error("separatore array mancante");
      this.position += 1;
    }
    this.error("array JSON incompleto");
  }

  string() {
    const start = this.position;
    this.position += 1;
    let escaped = false;
    while (this.position < this.text.length) {
      const code = this.text.charCodeAt(this.position);
      const character = this.text[this.position];
      if (!escaped && character === '"') {
        this.position += 1;
        const raw = this.text.slice(start, this.position);
        let value;
        try {
          value = JSON.parse(raw);
        } catch {
          this.error("stringa JSON non valida");
        }
        if (JSON.stringify(value) !== raw) this.error("stringa JSON non canonica");
        return value;
      }
      if (!escaped && code < 0x20) this.error("controllo non escapato in stringa");
      if (!escaped && character === "\\") {
        escaped = true;
      } else {
        escaped = false;
      }
      this.position += 1;
    }
    this.error("stringa JSON incompleta");
  }

  number() {
    const tail = this.text.slice(this.position);
    const match = /^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:e[+-]?\d+)?/.exec(tail);
    if (!match) this.error("numero JSON non valido");
    const token = match[0];
    this.position += token.length;
    const value = Number(token);
    if (!Number.isFinite(value)) this.error("numero JSON non finito");
    if (!/[.e]/.test(token) && (!Number.isSafeInteger(value) || String(value) !== token)) {
      this.error("intero JSON non canonico o non sicuro");
    }
    return value;
  }
}

function parseCanonicalJson(bytes, maximumBytes, label) {
  if (!(bytes instanceof Uint8Array) || bytes.length < 2 || bytes.length > maximumBytes) {
    fail("INVALID_JSON", `${label}: dimensione body non valida`);
  }
  if (bytes[0] === 0xef && bytes[1] === 0xbb && bytes[2] === 0xbf) {
    fail("INVALID_JSON", `${label}: BOM UTF-8 non ammesso`);
  }
  let text;
  try {
    text = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch (error) {
    fail("INVALID_JSON", `${label}: body non UTF-8`, error);
  }
  return { document: new CompactJsonParser(text, label).parse(), text };
}

export function canonicalJsonStringify(value) {
  if (value === null || typeof value === "string" || typeof value === "boolean") {
    return JSON.stringify(value);
  }
  if (typeof value === "number") {
    if (!Number.isFinite(value)) fail("INVALID_DOCUMENT", "numero JSON non finito");
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) return `[${value.map(canonicalJsonStringify).join(",")}]`;
  if (!isRecord(value)) fail("INVALID_DOCUMENT", "valore non rappresentabile come JSON canonico");
  return `{${Object.keys(value)
    .sort(compareJsonKeys)
    .map((key) => `${JSON.stringify(key)}:${canonicalJsonStringify(value[key])}`)
    .join(",")}}`;
}

const SHA256_K = Object.freeze([
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4,
  0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe,
  0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f,
  0x4a7484aa, 0x5cb0a9dc, 0x76f988da, 0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7,
  0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc,
  0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b,
  0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070, 0x19a4c116,
  0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
  0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7,
  0xc67178f2,
]);

function rotateRight(value, bits) {
  return (value >>> bits) | (value << (32 - bits));
}

export function sha256Hex(bytesOrText) {
  const bytes =
    typeof bytesOrText === "string" ? new TextEncoder().encode(bytesOrText) : bytesOrText;
  if (!(bytes instanceof Uint8Array)) fail("INVALID_DOCUMENT", "SHA-256 richiede byte UTF-8");
  const paddedLength = Math.ceil((bytes.length + 9) / 64) * 64;
  const padded = new Uint8Array(paddedLength);
  padded.set(bytes);
  padded[bytes.length] = 0x80;
  const view = new DataView(padded.buffer);
  view.setUint32(paddedLength - 8, Math.floor(bytes.length / 0x20000000));
  view.setUint32(paddedLength - 4, (bytes.length * 8) >>> 0);
  const state = new Int32Array([
    0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
    0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
  ]);
  const words = new Int32Array(64);
  for (let offset = 0; offset < paddedLength; offset += 64) {
    for (let index = 0; index < 16; index += 1) words[index] = view.getInt32(offset + index * 4);
    for (let index = 16; index < 64; index += 1) {
      const left = words[index - 15];
      const right = words[index - 2];
      const s0 = rotateRight(left, 7) ^ rotateRight(left, 18) ^ (left >>> 3);
      const s1 = rotateRight(right, 17) ^ rotateRight(right, 19) ^ (right >>> 10);
      words[index] = (words[index - 16] + s0 + words[index - 7] + s1) | 0;
    }
    let [a, b, c, d, e, f, g, h] = state;
    for (let index = 0; index < 64; index += 1) {
      const sum1 = rotateRight(e, 6) ^ rotateRight(e, 11) ^ rotateRight(e, 25);
      const choice = (e & f) ^ (~e & g);
      const temporary1 = (h + sum1 + choice + SHA256_K[index] + words[index]) | 0;
      const sum0 = rotateRight(a, 2) ^ rotateRight(a, 13) ^ rotateRight(a, 22);
      const majority = (a & b) ^ (a & c) ^ (b & c);
      const temporary2 = (sum0 + majority) | 0;
      h = g;
      g = f;
      f = e;
      e = (d + temporary1) | 0;
      d = c;
      c = b;
      b = a;
      a = (temporary1 + temporary2) | 0;
    }
    state[0] = (state[0] + a) | 0;
    state[1] = (state[1] + b) | 0;
    state[2] = (state[2] + c) | 0;
    state[3] = (state[3] + d) | 0;
    state[4] = (state[4] + e) | 0;
    state[5] = (state[5] + f) | 0;
    state[6] = (state[6] + g) | 0;
    state[7] = (state[7] + h) | 0;
  }
  return Array.from(state, (word) => (word >>> 0).toString(16).padStart(8, "0")).join("");
}

function sameJson(left, right) {
  return canonicalJsonStringify(left) === canonicalJsonStringify(right);
}

function validateCatalogReference(value, expected) {
  exactKeys(value, ["version", "sha256", "municipality_count"], "catalog");
  if (
    value.version !== expected.version ||
    value.sha256 !== expected.sha256 ||
    value.municipality_count !== expected.municipality_count
  ) {
    fail("CATALOG_MISMATCH", "riferimento al catalogo inatteso");
  }
}

function expectedFreshness(provider, runAt, validTo) {
  const contract = PROVIDER_CONTRACTS[provider];
  const run = parseUtc(runAt, "run_at", { onHour: true });
  const end = parseUtc(validTo, "valid_to", { onHour: true });
  const coverageLimit = end - contract.freshness.requiredFutureHours * HOUR_MS;
  return {
    policy_id: contract.freshness.policyId,
    fresh_until: iso(Math.min(run + contract.freshness.freshHours * HOUR_MS, coverageLimit)),
    usable_until: iso(Math.min(run + contract.freshness.usableHours * HOUR_MS, coverageLimit)),
    required_future_hours: contract.freshness.requiredFutureHours,
    current_sample_max_lag_minutes: 60,
  };
}

function validateFreshness(value, provider, runAt, validTo) {
  exactKeys(
    value,
    [
      "policy_id",
      "fresh_until",
      "usable_until",
      "required_future_hours",
      "current_sample_max_lag_minutes",
    ],
    "freshness",
  );
  const expected = expectedFreshness(provider, runAt, validTo);
  if (!sameJson(value, expected)) fail("FRESHNESS_MISMATCH", "freshness incoerente col provider");
}

function clockMilliseconds(now) {
  let value;
  try {
    value = now();
  } catch (error) {
    fail("INVALID_CLOCK", "clock iniettato non disponibile", error);
  }
  if (value instanceof Date) value = value.getTime();
  if (typeof value === "string") value = parseUtc(value, "clock");
  if (typeof value !== "number" || !Number.isFinite(value)) {
    fail("INVALID_CLOCK", "clock iniettato non restituisce un istante valido");
  }
  return value;
}

function normalizeIconWindowPolicy(value) {
  if (value === null) return null;
  if (
    !isRecord(value)
    || Object.keys(value).sort().join(",") !== "currentSampleMaxLagMs,maximumFutureHours,minimumFutureHours"
    || !Number.isInteger(value.minimumFutureHours)
    || value.minimumFutureHours < 12
    || !Number.isInteger(value.maximumFutureHours)
    || value.maximumFutureHours > 48
    || value.maximumFutureHours < value.minimumFutureHours
    || value.currentSampleMaxLagMs !== HOUR_MS
  ) fail("INVALID_CONFIG", "policy locale ICON non valida");
  return Object.freeze({ ...value });
}

function assessFreshness(document, provider, now, iconWindowPolicy = null, continuity = null) {
  const current = clockMilliseconds(now);
  const validFrom = parseUtc(document.valid_from, "valid_from", { onHour: true });
  const validTo = parseUtc(document.valid_to, "valid_to", { onHour: true });
  const freshUntil = parseUtc(document.freshness.fresh_until, "fresh_until");
  const usableUntil = continuity
    ? Math.min(parseUtc(continuity.usable_until, "continuity.usable_until"), validTo)
    : parseUtc(document.freshness.usable_until, "usable_until");
  const localPolicy = provider === WEATHER_V1_PROVIDERS.ICON2I ? iconWindowPolicy : null;
  const required = localPolicy?.minimumFutureHours ?? PROVIDER_CONTRACTS[provider].freshness.requiredFutureHours;
  const remaining = (validTo - current) / HOUR_MS;
  if (current < validFrom) fail("NOT_YET_VALID", "run meteo non ancora valido");
  const availableFutureHours = localPolicy ? countIconFutureHours(validTo, current) : null;
  if (localPolicy ? availableFutureHours < required : current > usableUntil || remaining + 1e-9 < required) {
    fail("EXPIRED", "run meteo scaduto o senza copertura residua sufficiente");
  }
  return Object.freeze({
    status: current <= freshUntil ? "fresh" : "stale",
    remainingCoverageHours: remaining,
    requiredFutureHours: required,
    freshUntil: document.freshness.fresh_until,
    usableUntil: localPolicy
      ? iso(validTo - (required - 1) * HOUR_MS)
      : continuity ? iso(usableUntil) : document.freshness.usable_until,
    ...(continuity ? { continuity } : {}),
    ...(localPolicy ? {
      availableFutureHours,
      maximumFutureHours: localPolicy.maximumFutureHours,
      localWindowPolicy: true,
    } : {}),
  });
}

function assessLatestFreshness(latest, provider, now, continuity = null) {
  const contract = PROVIDER_CONTRACTS[provider];
  const runAt = latest.latest.run_at;
  const run = parseUtc(runAt, "latest.latest.run_at", { onHour: true });
  const validTo = iso(run + contract.horizonHours * HOUR_MS);
  return assessFreshness(
    {
      valid_from: runAt,
      valid_to: validTo,
      freshness: expectedFreshness(provider, runAt, validTo),
    },
    provider,
    now,
    null,
    continuity,
  );
}

function validateProviderEnvelope(value, provider, kind, catalog, label) {
  const contract = PROVIDER_CONTRACTS[provider];
  if (value.schema_version !== SCHEMA_VERSION || value.kind !== kind || value.provider !== provider) {
    fail("PROVIDER_MISMATCH", `${label} non appartiene al provider/schema richiesto`);
  }
  if (!sameJson(value.model, contract.model) || !sameJson(value.source, contract.source)) {
    fail("PROVIDER_MISMATCH", `${label} ha modello o attribuzione inattesi`);
  }
  validateRunIdentity(value.source_run_id, value.run_at, label);
  const run = parseUtc(value.run_at, `${label}.run_at`, { onHour: true });
  if (parseUtc(value.generated_at, `${label}.generated_at`) < run) {
    fail("INVALID_DOCUMENT", `${label}.generated_at precede il run`);
  }
  if (value.valid_from !== value.run_at) fail("RUN_MISMATCH", `${label}.valid_from non coincide col run`);
  const validTo = parseUtc(value.valid_to, `${label}.valid_to`, { onHour: true });
  if (validTo !== run + contract.horizonHours * HOUR_MS) {
    fail("COVERAGE_MISMATCH", `${label} ha un orizzonte nativo inatteso`);
  }
  validateFreshness(value.freshness, provider, value.run_at, value.valid_to);
  validateCatalogReference(value.catalog, catalog);
}

function validateManifestDescriptor(value, label) {
  exactKeys(
    value,
    ["source_run_id", "run_at", "manifest_path", "manifest_json_bytes", "manifest_sha256"],
    label,
  );
  validateRunIdentity(value.source_run_id, value.run_at, label);
  const expectedPath = `runs/${value.source_run_id}/manifest.json`;
  if (value.manifest_path !== expectedPath) fail("PATH_MISMATCH", `${label} usa un path non canonico`);
  integer(value.manifest_json_bytes, `${label}.manifest_json_bytes`, { minimum: 1 });
  if (value.manifest_json_bytes > MAX_MANIFEST_BYTES || !SHA256.test(value.manifest_sha256)) {
    fail("INTEGRITY_MISMATCH", `${label} ha dimensione o SHA-256 non validi`);
  }
}

function validateLatest(value, provider, catalog) {
  exactKeys(
    value,
    [
      "schema_version",
      "kind",
      "provider",
      "revision",
      "published_at",
      "catalog",
      "latest",
      "previous",
      "disabled_run_ids",
    ],
    "latest",
  );
  if (value.schema_version !== SCHEMA_VERSION || value.kind !== LATEST_KIND || value.provider !== provider) {
    fail("PROVIDER_MISMATCH", "latest non appartiene al provider/schema richiesto");
  }
  integer(value.revision, "latest.revision", { minimum: 1 });
  parseUtc(value.published_at, "latest.published_at");
  validateCatalogReference(value.catalog, catalog);
  validateManifestDescriptor(value.latest, "latest.latest");
  if (value.previous !== null) {
    validateManifestDescriptor(value.previous, "latest.previous");
    if (value.previous.source_run_id === value.latest.source_run_id) {
      fail("RUN_MISMATCH", "latest e previous indicano lo stesso run");
    }
  }
  if (!Array.isArray(value.disabled_run_ids)) fail("INVALID_DOCUMENT", "disabled_run_ids non e un array");
  const sorted = [...new Set(value.disabled_run_ids)].sort();
  if (
    sorted.length !== value.disabled_run_ids.length ||
    sorted.some((runId, index) => runId !== value.disabled_run_ids[index]) ||
    sorted.some((runId) => !RUN_ID.test(runId))
  ) {
    fail("INVALID_DOCUMENT", "disabled_run_ids non e canonico");
  }
  if (sorted.includes(value.latest.source_run_id)) fail("RUN_DISABLED", "il run latest risulta revocato");
  if (value.previous && sorted.includes(value.previous.source_run_id)) {
    fail("RUN_DISABLED", "il run previous risulta revocato");
  }
  return value;
}

function runAtFor(sourceRunId, label) {
  if (typeof sourceRunId !== "string" || !RUN_ID.test(sourceRunId)) {
    fail("RUN_MISMATCH", `${label} non contiene un source_run_id canonico`);
  }
  const runAt = `${sourceRunId.slice(0, 4)}-${sourceRunId.slice(4, 6)}-${sourceRunId.slice(6, 8)}T${sourceRunId.slice(9, 11)}:${sourceRunId.slice(11, 13)}:${sourceRunId.slice(13, 15)}Z`;
  validateRunIdentity(sourceRunId, runAt, label);
  return runAt;
}

function validateCamsFamilyReleaseDescriptor(value, label) {
  exactKeys(
    value,
    ["source_run_id", "release_path", "release_json_bytes", "release_sha256"],
    label,
  );
  runAtFor(value.source_run_id, label);
  if (value.release_path !== `runs/${value.source_run_id}/release.json`) {
    fail("PATH_MISMATCH", `${label} usa un path release non canonico`);
  }
  integer(value.release_json_bytes, `${label}.release_json_bytes`, { minimum: 1 });
  if (value.release_json_bytes > MAX_RELEASE_BYTES || !SHA256.test(value.release_sha256)) {
    fail("INTEGRITY_MISMATCH", `${label} ha dimensione o SHA-256 non validi`);
  }
  return value;
}

function validateCamsFamilyLatest(value, catalog) {
  exactKeys(
    value,
    [
      "schema_version", "kind", "family", "revision", "published_at", "catalog", "latest",
      "previous", "disabled_run_ids",
    ],
    "CAMS family latest",
  );
  if (
    value.schema_version !== SCHEMA_VERSION ||
    value.kind !== CAMS_FAMILY_LATEST_KIND ||
    value.family !== CAMS_FAMILY
  ) {
    fail("PROVIDER_MISMATCH", "latest CAMS non appartiene alla famiglia/schema richiesta");
  }
  integer(value.revision, "CAMS family latest.revision", { minimum: 1 });
  parseUtc(value.published_at, "CAMS family latest.published_at");
  validateCatalogReference(value.catalog, catalog);
  if (!Array.isArray(value.disabled_run_ids)) {
    fail("INVALID_DOCUMENT", "CAMS family latest.disabled_run_ids non e un array");
  }
  const disabled = [...new Set(value.disabled_run_ids)].sort();
  if (
    disabled.length !== value.disabled_run_ids.length
    || disabled.some((runId, index) => runId !== value.disabled_run_ids[index])
    || disabled.some((runId) => !RUN_ID.test(runId))
  ) {
    fail("INVALID_DOCUMENT", "CAMS family latest.disabled_run_ids non e canonico");
  }
  const current = validateCamsFamilyReleaseDescriptor(value.latest, "CAMS family latest.latest");
  if (disabled.includes(current.source_run_id)) {
    fail("RUN_DISABLED", "la release CAMS attiva risulta revocata");
  }
  if (value.previous !== null) {
    const previous = validateCamsFamilyReleaseDescriptor(value.previous, "CAMS family latest.previous");
    if (previous.source_run_id >= current.source_run_id) {
      fail("RUN_MISMATCH", "la release CAMS previous non precede la current");
    }
    if (disabled.includes(previous.source_run_id)) {
      fail("RUN_DISABLED", "la release CAMS previous risulta revocata");
    }
  }
  return value;
}

const CAMS_COMPONENTS = Object.freeze({
  core: WEATHER_V1_PROVIDERS.CAMS_EUROPE,
  pollen: WEATHER_V1_PROVIDERS.CAMS_EUROPE_POLLEN,
});

function validateCamsComponentDescriptor(value, role, sourceRunId) {
  exactKeys(
    value,
    ["provider", "source_run_id", "manifest_key", "manifest_json_bytes", "manifest_sha256"],
    `CAMS family release.components.${role}`,
  );
  const provider = CAMS_COMPONENTS[role];
  const expectedKey = `weather/v1/${provider}/runs/${sourceRunId}/manifest.json`;
  if (
    value.provider !== provider ||
    value.source_run_id !== sourceRunId ||
    value.manifest_key !== expectedKey
  ) {
    fail("RUN_MISMATCH", `il componente CAMS ${role} non coincide con famiglia, ruolo o provider`);
  }
  integer(value.manifest_json_bytes, `${role}.manifest_json_bytes`, { minimum: 1 });
  if (value.manifest_json_bytes > MAX_MANIFEST_BYTES || !SHA256.test(value.manifest_sha256)) {
    fail("INTEGRITY_MISMATCH", `descriptor manifest CAMS ${role} non valido`);
  }
  return value;
}

function validateCamsFamilyRelease(value, latest, catalog) {
  exactKeys(
    value,
    [
      "schema_version", "kind", "family", "source_run_id", "published_at",
      "validation_sha256", "catalog", "components",
    ],
    "CAMS family release",
  );
  if (
    value.schema_version !== SCHEMA_VERSION ||
    value.kind !== CAMS_FAMILY_RELEASE_KIND ||
    value.family !== CAMS_FAMILY
  ) {
    fail("PROVIDER_MISMATCH", "release CAMS non appartiene alla famiglia/schema richiesta");
  }
  runAtFor(value.source_run_id, "CAMS family release");
  const releasePublishedAt = parseUtc(value.published_at, "CAMS family release.published_at");
  const pointerPublishedAt = parseUtc(latest.published_at, "CAMS family latest.published_at");
  if (releasePublishedAt > pointerPublishedAt) {
    fail("RUN_MISMATCH", "release CAMS pubblicata dopo il puntatore family latest");
  }
  if (!SHA256.test(value.validation_sha256)) {
    fail("INTEGRITY_MISMATCH", "fingerprint validazione CAMS non valido");
  }
  validateCatalogReference(value.catalog, catalog);
  exactKeys(value.components, ["core", "pollen"], "CAMS family release.components");
  for (const role of Object.keys(CAMS_COMPONENTS)) {
    validateCamsComponentDescriptor(value.components[role], role, value.source_run_id);
  }
  return value;
}

function componentRoleFor(provider) {
  if (provider === WEATHER_V1_PROVIDERS.CAMS_EUROPE) return "core";
  if (provider === WEATHER_V1_PROVIDERS.CAMS_EUROPE_POLLEN) return "pollen";
  fail("INVALID_CONFIG", `provider ${provider} non appartiene alla famiglia CAMS`);
}

function relativeManifestPath(provider, descriptor) {
  const prefix = `weather/v1/${provider}/`;
  if (!descriptor.manifest_key.startsWith(prefix)) {
    fail("PATH_MISMATCH", "manifest CAMS non appartiene allo spazio del provider");
  }
  return descriptor.manifest_key.slice(prefix.length);
}

function validateObjectDescriptor(value, sourceRunId, istatCode) {
  exactKeys(value, ["path", "json_bytes", "sha256"], `objects.${istatCode}`);
  const expectedPath = `runs/${sourceRunId}/municipalities/${istatCode}.json`;
  if (value.path !== expectedPath) fail("PATH_MISMATCH", `payload ${istatCode} usa un path non canonico`);
  integer(value.json_bytes, `objects.${istatCode}.json_bytes`, { minimum: 1 });
  if (value.json_bytes > MAX_PAYLOAD_BYTES || !SHA256.test(value.sha256)) {
    fail("INTEGRITY_MISMATCH", `descriptor payload ${istatCode} non valido`);
  }
}

function validateManifest(value, provider, catalog, istatCodes) {
  exactKeys(
    value,
    [
      "schema_version",
      "kind",
      "provider",
      "model",
      "source",
      "source_run_id",
      "run_at",
      "generated_at",
      "valid_from",
      "valid_to",
      "freshness",
      "catalog",
      "objects",
    ],
    "manifest",
  );
  validateProviderEnvelope(value, provider, MANIFEST_KIND, catalog, "manifest");
  if (!isRecord(value.objects)) fail("INVALID_DOCUMENT", "manifest.objects non e un oggetto");
  const codes = Object.keys(value.objects).sort();
  if (codes.length !== istatCodes.length || codes.some((code, index) => code !== istatCodes[index])) {
    fail("COVERAGE_MISMATCH", "manifest non copre esattamente i 215 codici ISTAT");
  }
  for (const code of codes) validateObjectDescriptor(value.objects[code], value.source_run_id, code);
  return value;
}

function validateFlags(value, label) {
  if (!Array.isArray(value)) fail("INVALID_DOCUMENT", `${label} non e un array`);
  const sorted = [...new Set(value)].sort();
  if (
    value.some((flag) => typeof flag !== "string" || !flag || flag !== flag.trim()) ||
    sorted.length !== value.length ||
    sorted.some((flag, index) => flag !== value[index])
  ) {
    fail("INVALID_DOCUMENT", `${label} non e un insieme ordinato di flag`);
  }
}

function expectedIconCondition(nativeCode) {
  if (nativeCode === null) {
    return {
      native_code: null,
      native_status: "invalid",
      native_label_it: "Condizione meteo non disponibile",
      semantic_key: null,
      text_key: null,
      icon_key: null,
      scene_key: null,
    };
  }
  if (!Number.isSafeInteger(nativeCode)) {
    fail("INVALID_DOCUMENT", "codice condizione ICON non intero");
  }
  const presentation = ICON_CONDITIONS[nativeCode];
  if (!presentation) {
    return {
      native_code: nativeCode,
      native_status: "unknown",
      native_label_it: "Codice meteo ICON-2I non riconosciuto",
      semantic_key: null,
      text_key: null,
      icon_key: null,
      scene_key: null,
    };
  }
  const [native_label_it, semantic_key, text_key, icon_key, scene_key] = presentation;
  return {
    native_code: nativeCode,
    native_status: "valid",
    native_label_it,
    semantic_key,
    text_key,
    icon_key,
    scene_key,
  };
}

function validateIconCondition(value) {
  exactKeys(
    value,
    [
      "native_code", "native_status", "native_label_it", "semantic_key", "text_key", "icon_key", "scene_key",
    ],
    "ICON.condition",
  );
  if (!sameJson(value, expectedIconCondition(value.native_code))) {
    fail("INVALID_DOCUMENT", "condizione ICON non coincide con la tassonomia v1");
  }
}

function numberOrNull(value, label, options) {
  if (value !== null) finiteNumber(value, label, options);
}

function validateMunicipality(value, expectedIstat) {
  exactKeys(
    value,
    ["istat_code", "name", "slug", "province", "representative_point", "model_point"],
    "payload.municipality",
  );
  if (value.istat_code !== expectedIstat || !ISTAT_CODE.test(value.istat_code)) {
    fail("ISTAT_MISMATCH", "payload e path indicano comuni diversi");
  }
  nonEmptyString(value.name, "municipality.name");
  nonEmptyString(value.slug, "municipality.slug");
  if (!["GO", "PN", "TS", "UD"].includes(value.province)) {
    fail("ISTAT_MISMATCH", "municipality.province non valida");
  }
  exactKeys(value.representative_point, ["lat", "lon"], "representative_point");
  finiteNumber(value.representative_point.lat, "representative_point.lat", { minimum: 45, maximum: 47 });
  finiteNumber(value.representative_point.lon, "representative_point.lon", { minimum: 12, maximum: 14.5 });
  exactKeys(value.model_point, ["lat", "lon", "distance_km", "grid_index"], "model_point");
  finiteNumber(value.model_point.lat, "model_point.lat", { minimum: 45, maximum: 47.2 });
  finiteNumber(value.model_point.lon, "model_point.lon", { minimum: 11.8, maximum: 14.5 });
  finiteNumber(value.model_point.distance_km, "model_point.distance_km", { minimum: 0 });
  integer(value.model_point.grid_index, "model_point.grid_index", { minimum: 0 });
}

const ICON_HOURLY_KEYS = [
  "valid_at", "interval_start", "interval_end", "temperature_c", "apparent_temperature_c",
  "relative_humidity_pct", "pressure_msl_hpa", "wind_speed_m_s", "wind_from_degrees",
  "wind_gust_max_m_s", "cloud_cover_pct", "precipitation_mm", "liquid_rain_mm",
  "snow_water_equivalent_mm", "condition", "quality_flags",
];

function validateIconPayload(value, run) {
  if (!sameJson(value.units, ICON_UNITS) || value.apparent_temperature_method !== "steadman_bom_shade_t2m_rh_magnus_wind10m_v1") {
    fail("INVALID_DOCUMENT", "unita o metodo temperatura percepita ICON inattesi");
  }
  if (!Array.isArray(value.hourly) || value.hourly.length !== 73) {
    fail("COVERAGE_MISMATCH", "payload ICON deve avere 73 campioni orari");
  }
  value.hourly.forEach((row, lead) => {
    const hasAccumulationQuality = isRecord(row) && Object.prototype.hasOwnProperty.call(row, "accumulation_quality");
    exactKeys(row, hasAccumulationQuality ? [...ICON_HOURLY_KEYS, "accumulation_quality"] : ICON_HOURLY_KEYS, `ICON.hourly.${lead}`);
    if (hasAccumulationQuality && !isValidIconAccumulationQuality(row.accumulation_quality, row)) {
      fail("INVALID_DOCUMENT", "ICON accumulation_quality non valido");
    }
    const expectedTime = iso(run + lead * HOUR_MS);
    if (row.valid_at !== expectedTime) fail("COVERAGE_MISMATCH", "timeline ICON non consecutiva");
    if (lead === 0) {
      if (row.interval_start !== null || row.interval_end !== null) {
        fail("COVERAGE_MISMATCH", "lead zero ICON ha un intervallo inatteso");
      }
      for (const key of [
        "wind_gust_max_m_s", "precipitation_mm", "liquid_rain_mm", "snow_water_equivalent_mm",
      ]) {
        if (row[key] !== null) fail("INVALID_DOCUMENT", `lead zero ICON ${key} non e null`);
      }
    } else if (row.interval_start !== iso(run + (lead - 1) * HOUR_MS) || row.interval_end !== expectedTime) {
      fail("COVERAGE_MISMATCH", "intervallo ICON non canonico");
    }
    numberOrNull(row.temperature_c, "temperature_c");
    numberOrNull(row.apparent_temperature_c, "apparent_temperature_c");
    numberOrNull(row.relative_humidity_pct, "relative_humidity_pct", { minimum: 0, maximum: 100 });
    numberOrNull(row.pressure_msl_hpa, "pressure_msl_hpa", { minimum: 0 });
    numberOrNull(row.wind_speed_m_s, "wind_speed_m_s", { minimum: 0 });
    numberOrNull(row.wind_from_degrees, "wind_from_degrees", { minimum: 0, maximum: 359.999999 });
    numberOrNull(row.wind_gust_max_m_s, "wind_gust_max_m_s", { minimum: 0 });
    numberOrNull(row.cloud_cover_pct, "cloud_cover_pct", { minimum: 0, maximum: 100 });
    numberOrNull(row.precipitation_mm, "precipitation_mm", { minimum: 0 });
    numberOrNull(row.liquid_rain_mm, "liquid_rain_mm", { minimum: 0 });
    numberOrNull(row.snow_water_equivalent_mm, "snow_water_equivalent_mm", { minimum: 0 });
    validateIconCondition(row.condition);
    validateFlags(row.quality_flags, "ICON quality_flags");
  });
  if (!Array.isArray(value.two_hourly) || value.two_hourly.length !== 36) {
    fail("COVERAGE_MISMATCH", "payload ICON deve avere 36 intervalli bi-orari");
  }
  value.two_hourly.forEach((row, index) => {
    exactKeys(
      row,
      [
        "start_at", "end_at", "source_hours", "precipitation_mm", "wind_gust_max_m_s",
        "temperature_min_c", "temperature_max_c", "temperature_end_c", "status", "quality_flags",
      ],
      `ICON.two_hourly.${index}`,
    );
    if (
      row.start_at !== iso(run + index * 2 * HOUR_MS) ||
      row.end_at !== iso(run + (index + 1) * 2 * HOUR_MS) ||
      row.source_hours !== 2 ||
      !["valid", "incomplete"].includes(row.status)
    ) {
      fail("COVERAGE_MISMATCH", "intervallo bi-orario ICON non canonico");
    }
    for (const key of [
      "precipitation_mm", "wind_gust_max_m_s", "temperature_min_c", "temperature_max_c", "temperature_end_c",
    ]) numberOrNull(row[key], `two_hourly.${key}`);
    validateFlags(row.quality_flags, "two_hourly.quality_flags");

    const pair = value.hourly.slice(index * 2 + 1, index * 2 + 3);
    const unionFlags = new Set([...pair[0].quality_flags, ...pair[1].quality_flags]);
    const missing = [];
    for (const key of ["precipitation_mm", "wind_gust_max_m_s", "temperature_c"]) {
      if (pair.some((hour) => hour[key] === null)) {
        missing.push(key);
        unionFlags.add(`missing_${key}`);
      }
    }
    const precipitation = pair.map((hour) => hour.precipitation_mm);
    const gusts = pair.map((hour) => hour.wind_gust_max_m_s);
    const temperatures = pair.map((hour) => hour.temperature_c);
    const expected = {
      start_at: pair[0].interval_start,
      end_at: pair[1].interval_end,
      source_hours: 2,
      precipitation_mm: precipitation.every((item) => item !== null)
        ? precipitation.reduce((total, item) => total + item, 0)
        : null,
      wind_gust_max_m_s: gusts.every((item) => item !== null) ? Math.max(...gusts) : null,
      temperature_min_c: temperatures.every((item) => item !== null)
        ? Math.min(...temperatures)
        : null,
      temperature_max_c: temperatures.every((item) => item !== null)
        ? Math.max(...temperatures)
        : null,
      temperature_end_c: temperatures.at(-1),
      status: missing.length ? "incomplete" : "valid",
      quality_flags: [...unionFlags].sort(),
    };
    if (!sameJson(row, expected)) {
      fail("COVERAGE_MISMATCH", "aggregato bi-orario ICON diverso dai campioni nativi");
    }
  });
}

function validateCamsPayload(
  value,
  run,
  variables = CAMS_VARIABLES,
  variableIds = CAMS_VARIABLE_IDS,
  projection = null,
) {
  if (
    !sameJson(value.variables, variables) ||
    value.health_classification !== null ||
    (projection !== null && !sameJson(value.projection, projection))
  ) {
    fail("INVALID_DOCUMENT", "variabili CAMS o classificazione salute non conformi al v1");
  }
  if (!Array.isArray(value.hourly) || value.hourly.length !== 97) {
    fail("COVERAGE_MISMATCH", "payload CAMS deve avere 97 campioni orari");
  }
  value.hourly.forEach((row, lead) => {
    exactKeys(row, ["valid_at", "values", "quality_flags"], `CAMS.hourly.${lead}`);
    if (row.valid_at !== iso(run + lead * HOUR_MS)) {
      fail("COVERAGE_MISMATCH", "timeline CAMS non consecutiva");
    }
    exactKeys(row.values, variableIds, `CAMS.values.${lead}`);
    exactKeys(row.quality_flags, variableIds, `CAMS.quality_flags.${lead}`);
    for (const variable of variableIds) {
      numberOrNull(row.values[variable], `CAMS.${variable}`, { minimum: 0 });
      validateFlags(row.quality_flags[variable], `CAMS.${variable}.quality_flags`);
    }
  });
}

function validatePayload(value, provider, catalog, expectedIstat, manifest) {
  const contract = PROVIDER_CONTRACTS[provider];
  const extras =
    provider === WEATHER_V1_PROVIDERS.ICON2I
      ? ["units", "apparent_temperature_method", "hourly", "two_hourly"]
      : [
        "variables",
        "hourly",
        "health_classification",
        ...(provider === WEATHER_V1_PROVIDERS.CAMS_EUROPE_POLLEN ? ["projection"] : []),
      ];
  exactKeys(
    value,
    [
      "schema_version", "kind", "provider", "model", "source", "source_run_id", "run_at",
      "generated_at", "valid_from", "valid_to", "timezone", "freshness", "catalog", "municipality",
      ...extras,
    ],
    "payload",
  );
  validateProviderEnvelope(value, provider, contract.payloadKind, catalog, "payload");
  if (value.timezone !== "Europe/Rome") fail("INVALID_DOCUMENT", "timezone payload inatteso");
  if (
    value.source_run_id !== manifest.source_run_id ||
    value.run_at !== manifest.run_at ||
    value.valid_from !== manifest.valid_from ||
    value.valid_to !== manifest.valid_to ||
    !sameJson(value.freshness, manifest.freshness) ||
    !sameJson(value.catalog, manifest.catalog)
  ) {
    fail("RUN_MISMATCH", "payload e manifest non descrivono lo stesso run");
  }
  validateMunicipality(value.municipality, expectedIstat);
  const run = parseUtc(value.run_at, "payload.run_at", { onHour: true });
  if (provider === WEATHER_V1_PROVIDERS.ICON2I) validateIconPayload(value, run);
  else if (provider === WEATHER_V1_PROVIDERS.CAMS_EUROPE_POLLEN) {
    validateCamsPayload(
      value,
      run,
      CAMS_POLLEN_VARIABLES,
      CAMS_POLLEN_VARIABLE_IDS,
      CAMS_POLLEN_PROJECTION,
    );
  } else validateCamsPayload(value, run);
  return value;
}

function deepFreeze(value) {
  if (value && typeof value === "object" && !Object.isFrozen(value)) {
    Object.freeze(value);
    for (const child of Object.values(value)) deepFreeze(child);
  }
  return value;
}

function normalizeConfigCatalog(catalog, istatCodes) {
  exactKeys(catalog, ["version", "sha256", "municipality_count"], "catalog atteso");
  if (
    catalog.version !== CATALOG_VERSION ||
    !SHA256.test(catalog.sha256) ||
    catalog.municipality_count !== MUNICIPALITY_COUNT
  ) {
    fail("INVALID_CONFIG", "catalog atteso non conforme al contratto v1");
  }
  if (!Array.isArray(istatCodes) || istatCodes.length !== MUNICIPALITY_COUNT) {
    fail("INVALID_CONFIG", "servono esattamente 215 codici ISTAT attesi");
  }
  const codes = [...istatCodes].sort();
  if (codes.some((code, index) => !ISTAT_CODE.test(code) || (index > 0 && code === codes[index - 1]))) {
    fail("INVALID_CONFIG", "codici ISTAT attesi non validi o duplicati");
  }
  return { catalog: deepFreeze({ ...catalog }), istatCodes: Object.freeze(codes) };
}

function normalizeBaseUrl(value) {
  if (typeof value !== "string") fail("INVALID_CONFIG", "baseUrl obbligatorio");
  const result = value.replace(/\/+$/, "");
  const hasControl = Array.from(result).some((character) => character.charCodeAt(0) < 0x20);
  if (!result || result.includes("?") || result.includes("#") || result.includes("\\") || hasControl) {
    fail("INVALID_CONFIG", "baseUrl non valido");
  }
  return result;
}

function validateDependencies(fetchImpl, now, force) {
  if (typeof fetchImpl !== "function") fail("INVALID_CONFIG", "fetchImpl iniettato obbligatorio");
  if (typeof now !== "function") fail("INVALID_CONFIG", "clock now iniettato obbligatorio");
  if (typeof force !== "boolean") fail("INVALID_CONFIG", "force deve essere booleano");
}

function normalizeOptionalStorage(storage) {
  try {
    if (
      storage &&
      (typeof storage === "object" || typeof storage === "function") &&
      typeof storage.getItem === "function" &&
      typeof storage.setItem === "function" &&
      typeof storage.removeItem === "function"
    ) {
      return storage;
    }
  } catch {
    return null;
  }
  return null;
}

function volatileCacheFor(storage) {
  if (!storage) return FALLBACK_VOLATILE_CACHE;
  let cache = VOLATILE_CACHE_BY_STORAGE.get(storage);
  if (!cache) {
    cache = { values: new Map(), tombstones: new Set(), camsFamilies: new Map() };
    VOLATILE_CACHE_BY_STORAGE.set(storage, cache);
  }
  return cache;
}

export function clearWeatherV1ClientMemoryCache({ storage = null } = {}) {
  const cache = volatileCacheFor(normalizeOptionalStorage(storage));
  cache.values.clear();
  cache.tombstones.clear();
  cache.camsFamilies.clear();
  return true;
}

// Raw municipality snapshots are downloadable duplicates of the validated
// display bundle. Under origin-wide localStorage pressure, release these before
// sacrificing the active forecast. Never touch pointers/revocations, display
// bundles, preferences, another endpoint or another TEST storage namespace.
export function writeWeatherV1CacheValue(storage, key, value, baseUrl) {
  const scope = sha256Hex(String(baseUrl || "").replace(/\/+$/, "")).slice(0, 16);
  const candidates = [];
  for (const provider of ["icon2i", "cams_europe", "cams_europe_pollen"]) {
    for (let slot = 0; slot < CACHE_MUNICIPALITY_SLOTS; slot += 1) {
      const candidate = `${CACHE_PREFIX}:${scope}:${provider}:municipality:${slot}`;
      if (candidate !== key) candidates.push(candidate);
    }
  }
  for (;;) {
    try {
      storage.setItem(key, value);
      return;
    } catch (error) {
      if (error?.name !== "QuotaExceededError" && error?.code !== 22 && error?.code !== 1014) throw error;
      // Largest first frees room with the fewest removals. Only persisted bytes
      // count; the bounded in-memory cache can still serve in-flight readers.
      let removable = null;
      let largest = 0;
      for (const candidate of candidates) {
        let bytes;
        try { bytes = storage.getItem(candidate); } catch { continue; }
        if (typeof bytes === "string" && bytes.length > largest) {
          removable = candidate;
          largest = bytes.length;
        }
      }
      if (!removable) throw error;
      candidates.splice(candidates.indexOf(removable), 1);
      try {
        storage.removeItem(removable);
        if (storage.getItem(removable) !== null) throw error;
      } catch { throw error; }
      // Raw indexes repair absent slots on the next read; writing an index
      // here would consume the space just recovered or recursively evict.
    }
  }
}

function header(response, name) {
  if (!response?.headers || typeof response.headers.get !== "function") {
    fail("INVALID_RESPONSE", "risposta fetch senza headers");
  }
  return response.headers.get(name);
}

function validEtag(value) {
  return typeof value === "string" && value === value.trim() && value.length > 0 && value.length <= 256 && !/[\r\n]/.test(value);
}

function validateAbortSignal(signal) {
  if (signal === undefined) return;
  if (
    !signal ||
    typeof signal.aborted !== "boolean" ||
    typeof signal.addEventListener !== "function" ||
    typeof signal.removeEventListener !== "function"
  ) {
    fail("INVALID_CONFIG", "AbortSignal weather v1 non valido");
  }
}

function abortError() {
  const error = new Error("richiesta weather v1 annullata");
  error.name = "AbortError";
  return error;
}

function subscribeToSharedRequest(entry, signal) {
  return new Promise((resolve, reject) => {
    let finished = false;
    entry.consumers += 1;
    const complete = (callback, value) => {
      if (finished) return;
      finished = true;
      signal?.removeEventListener("abort", onAbort);
      entry.consumers -= 1;
      callback(value);
    };
    const onAbort = () => {
      complete(reject, abortError());
      if (entry.consumers === 0 && !entry.settled) {
        entry.owner.delete(entry.key);
        entry.controller?.abort();
      }
    };
    if (signal?.aborted) {
      onAbort();
      return;
    }
    signal?.addEventListener("abort", onAbort, { once: true });
    entry.promise.then(
      (value) => complete(resolve, value),
      (error) => complete(reject, error),
    );
  });
}

function sharedRequest(fetchImpl, key, signal, start) {
  let requests = IN_FLIGHT_BY_FETCH.get(fetchImpl);
  if (!requests) {
    requests = new Map();
    IN_FLIGHT_BY_FETCH.set(fetchImpl, requests);
  }
  let entry = requests.get(key);
  if (!entry) {
    const controller = typeof globalThis.AbortController === "function"
      ? new globalThis.AbortController()
      : null;
    entry = {
      controller,
      consumers: 0,
      key,
      owner: requests,
      promise: null,
      settled: false,
    };
    entry.promise = Promise.resolve().then(() => start(controller?.signal));
    requests.set(key, entry);
    entry.promise.then(
      () => {
        entry.settled = true;
        if (requests.get(key) === entry) requests.delete(key);
      },
      () => {
        entry.settled = true;
        if (requests.get(key) === entry) requests.delete(key);
      },
    );
  }
  return subscribeToSharedRequest(entry, signal);
}

class ConditionalJsonTransport {
  constructor({ baseUrl, fetchImpl, storage, force, iconWindowPolicy = null, readPrefetchedObject = null }) {
    this.baseUrl = baseUrl;
    this.cacheScope = sha256Hex(baseUrl).slice(0, 16);
    this.fetchImpl = fetchImpl;
    this.storage = normalizeOptionalStorage(storage);
    this.volatileCache = volatileCacheFor(this.storage);
    this.force = force;
    this.iconWindowPolicy = iconWindowPolicy;
    this.readPrefetchedObject = readPrefetchedObject;
    this.cleanupPersistentCache();
  }

  cleanupPersistentCache() {
    if (!this.storage) return;
    let cleanedScopes = LEGACY_CACHE_CLEANUP_BY_STORAGE.get(this.storage);
    if (!cleanedScopes) {
      cleanedScopes = new Set();
      LEGACY_CACHE_CLEANUP_BY_STORAGE.set(this.storage, cleanedScopes);
    }
    let cleanedObsoleteScopes = OBSOLETE_V4_CACHE_CLEANUP_BY_STORAGE.get(this.storage);
    if (!cleanedObsoleteScopes) {
      cleanedObsoleteScopes = new Set();
      OBSOLETE_V4_CACHE_CLEANUP_BY_STORAGE.set(this.storage, cleanedObsoleteScopes);
    }
    if (cleanedScopes.has(this.cacheScope) && cleanedObsoleteScopes.has(this.cacheScope)) return;
    const slotIds = [
      "latest:0",
      "release:0",
      "release:1",
      "manifest:0",
      "manifest:1",
      "municipality:0",
      "municipality:1",
      "municipality:2",
      "municipality:3",
      "lru",
    ];
    if (!cleanedScopes.has(this.cacheScope)) {
      let legacyComplete = true;
      for (const prefix of LEGACY_CACHE_PREFIXES) {
        for (const provider of [...Object.values(WEATHER_V1_PROVIDERS), CAMS_FAMILY_SCOPE]) {
          for (const slotId of slotIds) {
            const key = `${prefix}:${this.cacheScope}:${provider}:${slotId}`;
            this.volatileCache.values.delete(key);
            this.volatileCache.tombstones.add(key);
            try {
              this.storage.removeItem(key);
            } catch {
              legacyComplete = false;
            }
          }
        }
      }
      if (legacyComplete) cleanedScopes.add(this.cacheScope);
    }
    if (cleanedObsoleteScopes.has(this.cacheScope)) return;
    let obsoleteComplete = true;
    const obsoleteV4Keys = new Set();
    // The pilot has one configured weather reader per installation. A raw v4
    // scope for a different base URL is therefore an obsolete endpoint cache,
    // not a second active provider. Bundle caches and feature caches are out of
    // scope and are deliberately left untouched.
    for (const key of this.volatileCache.values.keys()) {
      const scope = rawCacheScopeForKey(key);
      if (scope && scope !== this.cacheScope) obsoleteV4Keys.add(key);
    }
    try {
      if (typeof this.storage.key !== "function" || !Number.isSafeInteger(this.storage.length)) {
        obsoleteComplete = false;
      } else {
        // Snapshot before removal: localStorage indices shift after every delete.
        for (let index = 0; index < this.storage.length; index += 1) {
          const key = this.storage.key(index);
          const scope = rawCacheScopeForKey(key);
          if (scope && scope !== this.cacheScope) obsoleteV4Keys.add(key);
        }
      }
    } catch {
      obsoleteComplete = false;
    }
    for (const key of obsoleteV4Keys) {
      if (!this.safeRemove(key)) obsoleteComplete = false;
    }
    if (obsoleteComplete) cleanedObsoleteScopes.add(this.cacheScope);
  }

  hasPersistentStorage() {
    return this.storage !== null;
  }

  cacheKind(path) {
    if (path === "latest.json") return "latest";
    if (/^runs\/\d{8}T\d{6}Z\/continuity\.json$/.test(path)) return "continuity";
    if (/^runs\/\d{8}T\d{6}Z\/release\.json$/.test(path)) return "release";
    if (/^runs\/\d{8}T\d{6}Z\/manifest\.json$/.test(path)) return "manifest";
    if (/^runs\/\d{8}T\d{6}Z\/municipalities\/\d{6}\.json$/.test(path)) {
      return "municipality";
    }
    return null;
  }

  slotIds(kind) {
    if (kind === "latest") return ["latest:0"];
    const count = kind === "manifest"
      ? CACHE_MANIFEST_SLOTS
      : kind === "release" || kind === "continuity"
        ? CACHE_RELEASE_SLOTS
        : CACHE_MUNICIPALITY_SLOTS;
    return Array.from({ length: count }, (_, index) => `${kind}:${index}`);
  }

  allSlotIds() {
    return [
      ...this.slotIds("latest"),
      ...this.slotIds("release"),
      ...this.slotIds("continuity"),
      ...this.slotIds("manifest"),
      ...this.slotIds("municipality"),
    ];
  }

  slotKey(provider, slotId) {
    return `${CACHE_PREFIX}:${this.cacheScope}:${provider}:${slotId}`;
  }

  indexKey(provider) {
    return `${CACHE_PREFIX}:${this.cacheScope}:${provider}:lru`;
  }

  safeGet(key) {
    if (this.volatileCache.values.has(key)) return this.volatileCache.values.get(key);
    if (this.volatileCache.tombstones.has(key)) return null;
    if (!this.storage) return null;
    try {
      const value = this.storage.getItem(key);
      if (value != null) this.volatileCache.values.set(key, value);
      return value;
    } catch {
      return null;
    }
  }

  safeSet(key, value) {
    this.volatileCache.values.set(key, value);
    this.volatileCache.tombstones.delete(key);
    if (!this.storage) return false;
    try {
      writeWeatherV1CacheValue(this.storage, key, value, this.baseUrl);
      return true;
    } catch {
      return false;
    }
  }

  safeRemove(key) {
    this.volatileCache.values.delete(key);
    this.volatileCache.tombstones.add(key);
    if (!this.storage) return true;
    try {
      this.storage.removeItem(key);
      return true;
    } catch {
      try {
        // If deletion is blocked but writes still work, replace the cache body
        // with a deliberately invalid record so it cannot survive a remount.
        this.storage.setItem(key, "null");
        return true;
      } catch {
        return false;
      }
    }
  }

  camsFamilyState() {
    let state = this.volatileCache.camsFamilies.get(this.cacheScope);
    if (!state) {
      state = { latest: null, disabledRunIds: new Set() };
      this.volatileCache.camsFamilies.set(this.cacheScope, state);
    }
    return state;
  }

  emptyIndex(provider) {
    return { version: CACHE_VERSION, provider, counter: 0, slots: {} };
  }

  readIndex(provider) {
    const key = this.indexKey(provider);
    const raw = this.safeGet(key);
    if (raw == null) return this.emptyIndex(provider);
    try {
      const value = JSON.parse(raw);
      exactKeys(value, ["version", "provider", "counter", "slots"], "indice cache weather v1");
      if (
        value.version !== CACHE_VERSION ||
        value.provider !== provider ||
        !Number.isSafeInteger(value.counter) ||
        value.counter < 0 ||
        !isRecord(value.slots)
      ) {
        throw new Error("invalid cache index");
      }
      const allowedSlots = new Set(this.allSlotIds());
      const paths = new Set();
      for (const [slotId, descriptor] of Object.entries(value.slots)) {
        if (!allowedSlots.has(slotId)) throw new Error("invalid cache slot");
        exactKeys(descriptor, ["path", "access"], `indice cache weather v1 ${slotId}`);
        const kind = this.cacheKind(descriptor.path);
        if (
          !kind ||
          !slotId.startsWith(`${kind}:`) ||
          !Number.isSafeInteger(descriptor.access) ||
          descriptor.access < 0 ||
          descriptor.access > value.counter ||
          paths.has(descriptor.path)
        ) {
          throw new Error("invalid cache index descriptor");
        }
        paths.add(descriptor.path);
      }
      return value;
    } catch {
      this.safeRemove(key);
      return this.emptyIndex(provider);
    }
  }

  saveIndex(provider, index) {
    return this.safeSet(this.indexKey(provider), JSON.stringify(index));
  }

  markAccess(index, slotId, path) {
    if (index.counter >= Number.MAX_SAFE_INTEGER - 1) {
      const ordered = Object.entries(index.slots).sort(
        ([leftId, left], [rightId, right]) => left.access - right.access || leftId.localeCompare(rightId),
      );
      index.counter = 0;
      for (const [id, descriptor] of ordered) {
        index.counter += 1;
        descriptor.access = index.counter;
        index.slots[id] = descriptor;
      }
    }
    index.counter += 1;
    index.slots[slotId] = { path, access: index.counter };
  }

  maximumBytes(kind) {
    if (kind === "latest") return MAX_LATEST_BYTES;
    if (kind === "release" || kind === "continuity") return MAX_RELEASE_BYTES;
    if (kind === "manifest") return MAX_MANIFEST_BYTES;
    return MAX_PAYLOAD_BYTES;
  }

  readSlot(provider, slotId) {
    const key = this.slotKey(provider, slotId);
    const raw = this.safeGet(key);
    if (raw == null) return null;
    try {
      const value = JSON.parse(raw);
      exactKeys(
        value,
        ["version", "provider", "path", "etag", "body", "body_bytes", "body_sha256"],
        "cache weather v1",
      );
      const kind = this.cacheKind(value.path);
      if (
        value.version !== CACHE_VERSION ||
        value.provider !== provider ||
        !kind ||
        !slotId.startsWith(`${kind}:`) ||
        !validEtag(value.etag) ||
        typeof value.body !== "string" ||
        !Number.isSafeInteger(value.body_bytes) ||
        value.body_bytes < 2 ||
        value.body_bytes > this.maximumBytes(kind) ||
        !SHA256.test(value.body_sha256)
      ) {
        throw new Error("invalid cache record");
      }
      const bytes = new TextEncoder().encode(value.body);
      if (bytes.length !== value.body_bytes || sha256Hex(bytes) !== value.body_sha256) {
        throw new Error("corrupt cache body");
      }
      let persisted = false;
      if (this.storage) {
        try {
          persisted = this.storage.getItem(key) === raw;
        } catch {
          persisted = false;
        }
      }
      return { ...value, bytes, kind, slotId, persisted };
    } catch {
      this.safeRemove(key);
      return null;
    }
  }

  scanKind(provider, kind, index) {
    const records = [];
    for (const slotId of this.slotIds(kind)) {
      const record = this.readSlot(provider, slotId);
      if (!record) {
        delete index.slots[slotId];
        continue;
      }
      const descriptor = index.slots[slotId];
      if (!descriptor || descriptor.path !== record.path) {
        this.markAccess(index, slotId, record.path);
      }
      records.push(record);
    }
    return records;
  }

  read(provider, path) {
    const kind = this.cacheKind(path);
    if (!kind) return null;
    const index = this.readIndex(provider);
    let record = null;
    const indexed = Object.entries(index.slots).find(
      ([slotId, descriptor]) => slotId.startsWith(`${kind}:`) && descriptor.path === path,
    );
    if (indexed) {
      record = this.readSlot(provider, indexed[0]);
      if (!record || record.path !== path) delete index.slots[indexed[0]];
    }
    if (!record) record = this.scanKind(provider, kind, index).find((candidate) => candidate.path === path) ?? null;
    if (!record) return null;
    this.markAccess(index, record.slotId, record.path);
    this.saveIndex(provider, index);
    return record;
  }

  discard(provider, path) {
    const kind = this.cacheKind(path);
    if (!kind) return false;
    const index = this.readIndex(provider);
    let removed = true;
    for (const record of this.scanKind(provider, kind, index)) {
      if (record.path !== path) continue;
      removed = this.safeRemove(this.slotKey(provider, record.slotId)) && removed;
      delete index.slots[record.slotId];
    }
    this.saveIndex(provider, index);
    return removed;
  }

  purgeCamsRuns(runIds) {
    const disabled = new Set(runIds);
    let removed = true;
    for (const provider of [
      CAMS_FAMILY_SCOPE,
      WEATHER_V1_PROVIDERS.CAMS_EUROPE,
      WEATHER_V1_PROVIDERS.CAMS_EUROPE_POLLEN,
    ]) {
      const index = this.readIndex(provider);
      for (const kind of ["release", "continuity", "manifest", "municipality"]) {
        for (const record of this.scanKind(provider, kind, index)) {
          const match = /^runs\/(\d{8}T\d{6}Z)\//.exec(record.path);
          if (!match || !disabled.has(match[1])) continue;
          removed = this.safeRemove(this.slotKey(provider, record.slotId)) && removed;
          delete index.slots[record.slotId];
        }
      }
      this.saveIndex(provider, index);
    }
    return removed;
  }

  enforceBudget(provider, index, protectedSlotId) {
    const records = [
      ...this.scanKind(provider, "latest", index),
      ...this.scanKind(provider, "release", index),
      ...this.scanKind(provider, "continuity", index),
      ...this.scanKind(provider, "manifest", index),
      ...this.scanKind(provider, "municipality", index),
    ];
    let total = records.reduce((sum, record) => sum + record.body_bytes, 0);
    if (total <= CACHE_BODY_BUDGET_BYTES) return;
    const kindPriority = { municipality: 0, manifest: 1, release: 2, continuity: 2, latest: 3 };
    const candidates = records
      .filter(({ slotId }) => slotId !== protectedSlotId)
      .sort((left, right) => {
        const priority = kindPriority[left.kind] - kindPriority[right.kind];
        if (priority !== 0) return priority;
        const leftAccess = index.slots[left.slotId]?.access ?? 0;
        const rightAccess = index.slots[right.slotId]?.access ?? 0;
        return leftAccess - rightAccess || left.slotId.localeCompare(right.slotId);
      });
    for (const record of candidates) {
      if (total <= CACHE_BODY_BUDGET_BYTES) break;
      if (!this.safeRemove(this.slotKey(provider, record.slotId))) continue;
      delete index.slots[record.slotId];
      total -= record.body_bytes;
    }
  }

  write(provider, path, etag, body) {
    const kind = this.cacheKind(path);
    if (!kind || !validEtag(etag) || typeof body !== "string") return false;
    const bodyBytes = new TextEncoder().encode(body);
    if (bodyBytes.length < 2 || bodyBytes.length > this.maximumBytes(kind)) return false;
    const value = {
      version: CACHE_VERSION,
      provider,
      path,
      etag,
      body,
      body_bytes: bodyBytes.length,
      body_sha256: sha256Hex(bodyBytes),
    };
    const index = this.readIndex(provider);
    const records = this.scanKind(provider, kind, index);
    const existing = records.find((record) => record.path === path);
    const occupied = new Set(records.map(({ slotId }) => slotId));
    const empty = this.slotIds(kind).find((slotId) => !occupied.has(slotId));
    const leastRecentlyUsed = [...records].sort((left, right) => {
      const leftAccess = index.slots[left.slotId]?.access ?? 0;
      const rightAccess = index.slots[right.slotId]?.access ?? 0;
      return leftAccess - rightAccess || left.slotId.localeCompare(right.slotId);
    })[0];
    const slotId = existing?.slotId ?? empty ?? leastRecentlyUsed?.slotId;
    if (!slotId || !this.safeSet(this.slotKey(provider, slotId), JSON.stringify(value))) return false;
    this.markAccess(index, slotId, path);
    this.enforceBudget(provider, index, slotId);
    this.saveIndex(provider, index);
    return true;
  }

  async fetchSnapshot(url, options) {
    // Window.fetch is Web-IDL brand checked in browsers. Calling a stored
    // reference as this.fetchImpl(...) binds the transport instance as `this`
    // and Chromium rejects it with "Illegal invocation". Invoke it with the
    // actual global object while keeping injected test/native fetchers usable.
    const response = await Reflect.apply(this.fetchImpl, globalThis, [url, options]);
    if (!response || !Number.isInteger(response.status)) {
      fail("INVALID_RESPONSE", "fetch weather v1 non ha restituito una Response valida");
    }
    if (response.status === 304) {
      return { status: response.status, etag: header(response, "etag"), bytes: null };
    }
    if (response.status !== 200) {
      return { status: response.status, etag: null, bytes: null };
    }
    const contentType = header(response, "content-type");
    if (typeof contentType !== "string" || !/^application\/json(?:\s*;|$)/i.test(contentType)) {
      fail("INVALID_RESPONSE", "weather v1 non ha restituito application/json");
    }
    const etag = header(response, "etag");
    if (!validEtag(etag)) fail("INVALID_RESPONSE", "weather v1 non ha restituito un ETag valido");
    if (typeof response.arrayBuffer !== "function") {
      fail("INVALID_RESPONSE", "Response weather v1 non espone i byte del body");
    }
    try {
      return { status: response.status, etag, bytes: new Uint8Array(await response.arrayBuffer()) };
    } catch (error) {
      fail("INVALID_RESPONSE", "body weather v1 non leggibile", error);
    }
  }

  cachedResponse(cached, fallbackReason = null) {
    return {
      bytes: cached.bytes,
      etag: cached.etag,
      fromCache: true,
      notModified: fallbackReason === null,
      networkFallback: fallbackReason !== null,
      fallbackReason,
      cachePersisted: cached.persisted,
      commit() {
        return null;
      },
    };
  }

  uncommittedResponse(provider, path, { bytes, etag, body }, cached) {
    return {
      bytes,
      etag,
      cachedBefore: cached,
      fromCache: false,
      notModified: false,
      networkFallback: false,
      fallbackReason: null,
      commit: () => this.write(provider, path, etag, body),
    };
  }

  async prefetchedSnapshot(provider, path, signal, expectedHash) {
    const kind = this.cacheKind(path);
    if (!this.readPrefetchedObject || this.force || !expectedHash
      || !SHA256.test(expectedHash) || !kind || kind === "latest") return null;
    let onAbort;
    let wasAborted = false;
    try {
      if (signal?.aborted) throw abortError();
      const pending = Promise.resolve().then(() => {
        if (signal?.aborted) throw abortError();
        return this.readPrefetchedObject({ provider, path, sha256: expectedHash, signal });
      });
      const value = await (signal ? Promise.race([
        pending,
        new Promise((_, reject) => {
          onAbort = () => { wasAborted = true; reject(abortError()); };
          signal.addEventListener("abort", onAbort, { once: true });
        }),
      ]) : pending);
      if (signal?.aborted) throw abortError();
      const limit = this.maximumBytes(kind);
      if (!isRecord(value)) return null;
      const { body, etag } = value;
      if (typeof body !== "string" || !validEtag(etag)
        || body.length === 0 || body.length > limit) return null;
      const bytes = new TextEncoder().encode(body);
      if (bytes.length > limit || sha256Hex(bytes) !== expectedHash
        || new TextDecoder("utf-8", { fatal: true }).decode(bytes) !== body) return null;
      return { bytes, etag, body };
    } catch (error) {
      if (signal?.aborted || wasAborted) {
        const failure = new WeatherV1ClientError("TRANSPORT_FAILURE", `fetch weather v1 fallita per ${provider}`, { cause: error });
        failure.aborted = true;
        throw failure;
      }
      // Native staging is optional and untrusted. Plugin/missing/bad-byte
      // failures are cache misses; protocol validation remains outside here.
      return null;
    } finally {
      if (onAbort) signal.removeEventListener("abort", onAbort);
    }
  }

  async request(provider, path, signal, expectedHash = null) {
    try {
      return await this.requestSnapshot(provider, path, signal, expectedHash);
    } catch (error) {
      const transientHttp = error?.code === "HTTP_ERROR"
        && (error.httpStatus === 408 || error.httpStatus === 429
          || (error.httpStatus >= 500 && error.httpStatus <= 599));
      if (provider === WEATHER_V1_PROVIDERS.ICON2I && this.iconWindowPolicy
        && error?.code !== "TRANSPORT_FAILURE" && !transientHttp) {
        // A later offline retry must not resurrect bytes rejected by a known
        // authorization, missing-object, response-format or integrity failure.
        this.discard(provider, path);
      }
      throw error;
    }
  }

  async requestSnapshot(provider, path, signal, expectedHash = null) {
    validateAbortSignal(signal);
    if (this.readPrefetchedObject && signal?.aborted) {
      const failure = new WeatherV1ClientError("TRANSPORT_FAILURE", `fetch weather v1 fallita per ${provider}`, { cause: abortError() });
      failure.aborted = true;
      throw failure;
    }
    // A forced pilot refresh still goes to the network unconditionally. Only a
    // transient failure may reuse the old, fully revalidated ICON bytes.
    const canRetainForcedIcon = provider === WEATHER_V1_PROVIDERS.ICON2I && this.iconWindowPolicy !== null;
    const cached = this.force && !canRetainForcedIcon ? null : this.read(provider, path);
    // Immutable run objects are still checked against the parent hash by the
    // caller. Mutable latest pointers must always pass through the network.
    if (!this.force && cached && expectedHash && sha256Hex(cached.bytes) === expectedHash) return this.cachedResponse(cached);
    if (this.readPrefetchedObject && expectedHash && !this.force) {
    if (this.readPrefetchedObject && expectedHash && !this.force) {
      const prefetched = await this.prefetchedSnapshot(provider, path, signal, expectedHash);
      if (prefetched) return this.uncommittedResponse(provider, path, prefetched, cached);
    }
    }
    const headers = { Accept: "application/json" };
    if (cached && !this.force) headers["If-None-Match"] = cached.etag;
    const url = `${this.baseUrl}/weather/v1/${provider}/${path}`;
    const requestOptions = (requestSignal) => ({
      method: "GET",
      headers,
      cache: this.force ? "no-store" : "no-cache",
      ...(requestSignal === undefined ? {} : { signal: requestSignal }),
    });
    let response;
    try {
      response = this.force
        ? await this.fetchSnapshot(url, requestOptions(signal))
        : await sharedRequest(
          this.fetchImpl,
          `${url}\n${cached?.etag ?? ""}`,
          signal,
          (sharedSignal) => this.fetchSnapshot(url, requestOptions(sharedSignal)),
        );
    } catch (error) {
      if (error instanceof WeatherV1ClientError) throw error;
      if (cached && !signal?.aborted && error?.name !== "AbortError") return this.cachedResponse(cached, "transport_failure");
      const failure = new WeatherV1ClientError("TRANSPORT_FAILURE", `fetch weather v1 fallita per ${provider}`, { cause: error });
      failure.aborted = Boolean(signal?.aborted || error?.name === "AbortError");
      throw failure;
    }
    if (response.status === 304) {
      if (!cached || this.force) fail("CACHE_MISS_304", "304 ricevuto senza body verificabile in cache");
      const responseEtag = response.etag;
      if (responseEtag != null && (!validEtag(responseEtag) || responseEtag !== cached.etag)) {
        fail("INVALID_RESPONSE", "304 con ETag incoerente");
      }
      return this.cachedResponse(cached);
    }
    if (response.status !== 200) {
      if (
        cached &&
        (response.status === 408 ||
          response.status === 429 ||
          (response.status >= 500 && response.status <= 599))
      ) {
        return this.cachedResponse(cached, `http_${response.status}`);
      }
      const failure = new WeatherV1ClientError("HTTP_ERROR", `weather v1 ha risposto HTTP ${response.status}`);
      failure.httpStatus = response.status;
      throw failure;
    }
    const { bytes, etag } = response;
    let body;
    try {
      body = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
    } catch (error) {
      fail("INVALID_JSON", "body weather v1 non UTF-8", error);
    }
    return this.uncommittedResponse(provider, path, { bytes, etag, body }, cached);
  }
}

function documentFrom(value, label) {
  const document = isRecord(value) && "document" in value ? value.document : value;
  if (!isRecord(document)) fail("INVALID_DOCUMENT", `${label} mancante`);
  return document;
}

function result(document, loaded, path, freshness, cachePersisted) {
  return Object.freeze({
    document: deepFreeze(document),
    path,
    etag: loaded.etag,
    fromCache: loaded.fromCache,
    notModified: loaded.notModified,
    ...(loaded.networkFallback
      ? { networkFallback: true, fallbackReason: loaded.fallbackReason }
      : {}),
    ...(!loaded.fromCache ? { cachePersisted } : {}),
    ...(freshness ? { freshness } : {}),
  });
}

function createProviderClient({ provider, catalog, istatCodes, now, transport, iconWindowPolicy = null }) {
  const latestPath = "latest.json";
  let observedLatest = null;
  const observedDisabledRuns = new Set();

  function observeIconPointer(latest) {
    if (!iconWindowPolicy) return;
    if (observedLatest && (
      latest.revision < observedLatest.revision
      || (latest.revision === observedLatest.revision && !sameJson(latest, observedLatest))
    )) fail("RUN_MISMATCH", "latest ICON regredisce rispetto al puntatore verificato");
    if ([...observedDisabledRuns].some((runId) => !latest.disabled_run_ids.includes(runId))) {
      fail("RUN_DISABLED", "latest ICON perde una revoca gia verificata");
    }
    observedLatest = latest;
    for (const runId of latest.disabled_run_ids) observedDisabledRuns.add(runId);
  }

  function observeCachedIconPointer() {
    if (!iconWindowPolicy) return;
    const cached = transport.read(provider, latestPath);
    if (!cached) return;
    let latest;
    try {
      latest = validateLatest(parseCanonicalJson(cached.bytes, MAX_LATEST_BYTES, "ICON latest cached").document,
        provider, catalog);
    } catch {
      // Unverified local bytes cannot veto a valid network pointer or provide
      // evidence that a previously observed revocation has disappeared.
      return;
    }
    observeIconPointer(latest);
  }

  function assertIconRunEnabled(sourceRunId) {
    if (!iconWindowPolicy) return;
    observeCachedIconPointer();
    if (observedDisabledRuns.has(sourceRunId)) fail("RUN_DISABLED", "corsa ICON revocata");
  }

  return Object.freeze({
    provider,

    async fetchLatest(signal) {
      const loaded = await transport.request(provider, latestPath, signal);
      try {
        const parsed = parseCanonicalJson(loaded.bytes, MAX_LATEST_BYTES, `${provider} latest`);
        const latest = validateLatest(parsed.document, provider, catalog);
        observeCachedIconPointer();
        observeIconPointer(latest);
        // Pointer integrity/revocations remain mandatory. Its active run may be
        // unusable or not yet valid while the verified previous run is usable.
        const freshness = iconWindowPolicy ? null : assessLatestFreshness(latest, provider, now);
        const cachePersisted = loaded.commit();
        return result(latest, loaded, latestPath, freshness, cachePersisted);
      } catch (error) {
        if (loaded.fromCache || iconWindowPolicy) transport.discard(provider, latestPath);
        throw error;
      }
    },

    async fetchManifest(latestValue, signal, { previous = false } = {}) {
      const latest = validateLatest(documentFrom(latestValue, "latest"), provider, catalog);
      const descriptor = previous ? latest.previous : latest.latest;
      if (!descriptor || latest.disabled_run_ids.includes(descriptor.source_run_id)) {
        fail("RUN_DISABLED", "corsa precedente assente o revocata");
      }
      assertIconRunEnabled(descriptor.source_run_id);
      const path = descriptor.manifest_path;
      const loaded = await transport.request(provider, path, signal,
        latestValue?.networkFallback ? null : descriptor.manifest_sha256);
      try {
        if (
          loaded.bytes.length !== descriptor.manifest_json_bytes ||
          sha256Hex(loaded.bytes) !== descriptor.manifest_sha256
        ) {
          fail("INTEGRITY_MISMATCH", "SHA-256 o dimensione manifest non coincide con latest");
        }
        const parsed = parseCanonicalJson(loaded.bytes, MAX_MANIFEST_BYTES, `${provider} manifest`);
        const manifest = validateManifest(parsed.document, provider, catalog, istatCodes);
        if (
          manifest.source_run_id !== descriptor.source_run_id ||
          manifest.run_at !== descriptor.run_at
        ) {
          fail("RUN_MISMATCH", "manifest non coincide col run indicato da latest");
        }
        const freshness = assessFreshness(manifest, provider, now, iconWindowPolicy);
        assertIconRunEnabled(manifest.source_run_id);
        const cachePersisted = loaded.commit();
        const manifestResult = result(manifest, loaded, path, freshness, cachePersisted);
        if (latestValue?.networkFallback || loaded.networkFallback) {
          PREFETCH_BLOCKED_MANIFESTS.add(manifestResult);
          PREFETCH_BLOCKED_MANIFESTS.add(manifestResult.document);
        }
        return manifestResult;
      } catch (error) {
        if (loaded.fromCache || iconWindowPolicy) transport.discard(provider, path);
        throw error;
      }
    },

    async fetchMunicipality(manifestValue, istatCode, signal) {
      if (typeof istatCode !== "string" || !istatCodes.includes(istatCode)) {
        fail("ISTAT_MISMATCH", "codice ISTAT richiesto non presente nel catalogo v1");
      }
      const manifest = validateManifest(documentFrom(manifestValue, "manifest"), provider, catalog, istatCodes);
      assertIconRunEnabled(manifest.source_run_id);
      const descriptor = manifest.objects[istatCode];
      const path = descriptor.path;
      const loaded = await transport.request(provider, path, signal,
        transport.readPrefetchedObject && !manifestValue?.networkFallback
          && !PREFETCH_BLOCKED_MANIFESTS.has(manifestValue) ? descriptor.sha256 : null);
      try {
        if (loaded.bytes.length !== descriptor.json_bytes || sha256Hex(loaded.bytes) !== descriptor.sha256) {
          fail("INTEGRITY_MISMATCH", `SHA-256 o dimensione payload ${istatCode} non coincide col manifest`);
        }
        const parsed = parseCanonicalJson(loaded.bytes, MAX_PAYLOAD_BYTES, `${provider} payload ${istatCode}`);
        const payload = validatePayload(parsed.document, provider, catalog, istatCode, manifest);
        const freshness = assessFreshness(payload, provider, now, iconWindowPolicy);
        assertIconRunEnabled(payload.source_run_id);
        const cachePersisted = loaded.commit();
        return result(payload, loaded, path, freshness, cachePersisted);
      } catch (error) {
        if (loaded.fromCache || iconWindowPolicy) transport.discard(provider, path);
        throw error;
      }
    },

    clearLatestCache() {
      transport.discard(provider, latestPath);
    },
  });
}

const CAMS_MEMBER_CONTEXT = new WeakMap();
const CAMS_FAMILY_MEMBERS = new WeakMap();

function sameCamsFamilyPointer(left, right) {
  return left.revision === right.revision
    && left.published_at === right.published_at
    && left.latest.source_run_id === right.latest.source_run_id
    && left.previous?.source_run_id === right.previous?.source_run_id
    && canonicalJsonStringify(left.disabled_run_ids) === canonicalJsonStringify(right.disabled_run_ids);
}

function sameCamsReleaseDescriptor(left, right) {
  return left !== null
    && right !== null
    && canonicalJsonStringify(left) === canonicalJsonStringify(right);
}

function sameDisabledRuns(left, right) {
  return canonicalJsonStringify(left) === canonicalJsonStringify(right);
}

function disabledRunsWith(disabledRunIds, runId) {
  return [...new Set([...disabledRunIds, runId])].sort();
}

function validateConsecutiveCamsFamilyTransition(previous, candidate) {
  const previousRunId = previous.latest.source_run_id;
  const candidateRunId = candidate.latest.source_run_id;
  if (candidateRunId > previousRunId) {
    if (
      !sameCamsReleaseDescriptor(candidate.previous, previous.latest)
      || !sameDisabledRuns(candidate.disabled_run_ids, previous.disabled_run_ids)
    ) {
      fail(
        "RUN_MISMATCH",
        "la pubblicazione CAMS consecutiva deve legare previous alla release sostituita",
      );
    }
    return;
  }
  if (candidateRunId === previousRunId) {
    const revokedPrevious = previous.previous?.source_run_id;
    if (
      !sameCamsReleaseDescriptor(candidate.latest, previous.latest)
      || candidate.previous !== null
      || !revokedPrevious
      || !sameDisabledRuns(
        candidate.disabled_run_ids,
        disabledRunsWith(previous.disabled_run_ids, revokedPrevious),
      )
    ) {
      fail("RUN_MISMATCH", "transizione CAMS same-active non e una revoca coerente");
    }
    return;
  }
  if (
    !sameCamsReleaseDescriptor(candidate.latest, previous.previous)
    || candidate.previous !== null
    || !sameDisabledRuns(
      candidate.disabled_run_ids,
      disabledRunsWith(previous.disabled_run_ids, previousRunId),
    )
  ) {
    fail(
      "RUN_MISMATCH",
      "rollback CAMS consecutivo non coincide con previous/null e revoca del current",
    );
  }
}

function validateGappedCamsFamilyTransition(previous, candidate) {
  const previousRunId = previous.latest.source_run_id;
  const candidateRunId = candidate.latest.source_run_id;
  const disabled = new Set(candidate.disabled_run_ids);
  if (candidateRunId < previousRunId) {
    if (
      !sameCamsReleaseDescriptor(candidate.latest, previous.previous)
      || candidate.previous !== null
      || !disabled.has(previousRunId)
    ) {
      fail(
        "RUN_MISMATCH",
        "rollback CAMS con gap non coincide con previous/null e revoca del run osservato",
      );
    }
    return;
  }
  if (candidateRunId === previousRunId) {
    if (
      !sameCamsReleaseDescriptor(candidate.latest, previous.latest)
      || candidate.previous !== null
    ) {
      fail("RUN_MISMATCH", "transizione CAMS same-active con gap prepara un rollback arbitrario");
    }
    return;
  }
  if (candidate.previous === null) {
    if (!disabled.has(previousRunId)) {
      fail("RUN_MISMATCH", "pubblicazione CAMS con gap perde il run osservato senza revocarlo");
    }
    return;
  }
  const candidatePreviousRunId = candidate.previous.source_run_id;
  if (candidatePreviousRunId === previousRunId) {
    if (!sameCamsReleaseDescriptor(candidate.previous, previous.latest)) {
      fail("RUN_MISMATCH", "previous CAMS con gap altera la release osservata");
    }
    return;
  }
  if (
    candidatePreviousRunId < previousRunId
    && (
      !sameCamsReleaseDescriptor(candidate.previous, previous.previous)
      || !disabled.has(previousRunId)
    )
  ) {
    fail("RUN_MISMATCH", "previous CAMS con gap non appartiene alla catena osservata");
  }
}

function validateCamsFamilyTransition(previous, candidate, state) {
  const disabled = new Set(candidate.disabled_run_ids);
  for (const runId of state.disabledRunIds) {
    if (!disabled.has(runId)) {
      fail("RUN_MISMATCH", "il puntatore CAMS ha perso una revoca gia osservata");
    }
  }
  if (state.disabledRunIds.has(candidate.latest.source_run_id)) {
    fail("RUN_DISABLED", "il puntatore CAMS tenta di riattivare un run revocato");
  }
  if (!previous) return;
  if (sameCamsFamilyPointer(previous, candidate)) return;
  if (candidate.revision <= previous.revision) {
    fail("RUN_MISMATCH", "il puntatore CAMS modificato non incrementa la revision");
  }
  if (parseUtc(candidate.published_at, "CAMS family latest.published_at") < parseUtc(
    previous.published_at,
    "CAMS family previous.published_at",
  )) {
    fail("RUN_MISMATCH", "il puntatore CAMS ha un tempo di pubblicazione regressivo");
  }
  if (candidate.revision === previous.revision + 1) {
    validateConsecutiveCamsFamilyTransition(previous, candidate);
    return;
  }
  validateGappedCamsFamilyTransition(previous, candidate);
}

function cachedCamsFamilyLatest(loaded, catalog) {
  if (!loaded?.cachedBefore?.bytes) return null;
  try {
    const parsed = parseCanonicalJson(
      loaded.cachedBefore.bytes,
      MAX_LATEST_BYTES,
      "CAMS family latest cached precedente",
    );
    return validateCamsFamilyLatest(parsed.document, catalog);
  } catch {
    return null;
  }
}

function observeCamsFamilyLatest({ latest, loaded, state, transport, catalog }) {
  const previous = state.latest ?? cachedCamsFamilyLatest(loaded, catalog);
  validateCamsFamilyTransition(previous, latest, state);
  for (const runId of latest.disabled_run_ids) state.disabledRunIds.add(runId);
  state.latest = latest;
  if (latest.disabled_run_ids.length) {
    const oldPointerRemoved = loaded.fromCache
      || transport.discard(CAMS_FAMILY_SCOPE, "latest.json");
    if (!oldPointerRemoved || !transport.purgeCamsRuns(latest.disabled_run_ids)) {
      fail("CACHE_INVALIDATION_FAILED", "impossibile eliminare tutti i run CAMS revocati");
    }
  }
}

function camsFamilyDecisionSnapshot(latest) {
  return deepFreeze({
    revision: latest.revision,
    published_at: latest.published_at,
    latest: { source_run_id: latest.latest.source_run_id },
    disabled_run_ids: [...latest.disabled_run_ids],
  });
}

function assertCamsContextEnabled(context) {
  const runId = context?.component?.source_run_id;
  if (runId && context.state.disabledRunIds.has(runId)) {
    fail("RUN_DISABLED", `il run CAMS ${runId} e stato revocato`);
  }
}

function validateCamsMemberSnapshot({ latest, release, provider, role, catalog, now, continuity }) {
  const component = release.components[role];
  const runAt = runAtFor(component.source_run_id, `CAMS ${role}`);
  const synthetic = validateLatest(
    {
      schema_version: SCHEMA_VERSION,
      kind: LATEST_KIND,
      provider,
      revision: latest.revision,
      published_at: latest.published_at,
      catalog: latest.catalog,
      latest: {
        source_run_id: component.source_run_id,
        run_at: runAt,
        manifest_path: relativeManifestPath(provider, component),
        manifest_json_bytes: component.manifest_json_bytes,
        manifest_sha256: component.manifest_sha256,
      },
      previous: null,
      disabled_run_ids: [...latest.disabled_run_ids],
    },
    provider,
    catalog,
  );
  return Object.freeze({
    component,
    document: synthetic,
    freshness: assessLatestFreshness(synthetic, provider, now, continuity),
    provider,
    role,
  });
}

function validateCamsFamilyMembers(latest, release, catalog, now, continuity = null) {
  const current = clockMilliseconds(now);
  const snapshotClock = () => current;
  return Object.freeze(Object.fromEntries(
    Object.entries(CAMS_COMPONENTS).map(([role, provider]) => [
      role,
      validateCamsMemberSnapshot({
        latest,
        release,
        provider,
        role,
        catalog,
        now: snapshotClock,
        continuity,
      }),
    ]),
  ));
}

function camsMemberLatestFromFamily({ family, provider, role, catalog }) {
  const familyContext = CAMS_FAMILY_MEMBERS.get(family);
  const member = familyContext?.members?.[role];
  if (!member || member.provider !== provider || member.role !== role) {
    fail("FAMILY_CONTEXT_REQUIRED", "snapshot CAMS privo del contesto familiare verificato");
  }
  const synthetic = validateLatest(member.document, provider, catalog);
  const token = Object.freeze({ ...result(
    synthetic,
    family,
    `${CAMS_FAMILY_SCOPE}/${family.document.latest.release_path}#${role}`,
    member.freshness,
    family.cachePersisted,
  ), familyRelease: family.document.latest, familyReleasePublishedAt: family.release.published_at });
  const context = Object.freeze({
    family,
    component: member.component,
    role,
    provider,
    state: familyContext.state,
  });
  assertCamsContextEnabled(context);
  CAMS_MEMBER_CONTEXT.set(token, context);
  CAMS_MEMBER_CONTEXT.set(token.document, context);
  return token;
}

async function readCamsContinuity({ latest, release, transport, signal, catalog }) {
  const path = `runs/${release.source_run_id}/continuity.json`;
  let loaded;
  try {
    loaded = await transport.request(CAMS_FAMILY_SCOPE, path, signal);
  } catch (error) {
    // Old readers reject the unknown path (400); legacy/new readers without an
    // opt-in publication return 404. A temporary miss can use only the 30h v1
    // contract. A validated cached sidecar is handled by the transport itself.
    if (!error?.aborted && (error?.code === "TRANSPORT_FAILURE"
      || error?.code === "HTTP_ERROR" && ([400,404,408,429].includes(error.httpStatus) || error.httpStatus >= 500))) {
      if ([400,404].includes(error.httpStatus)) transport.discard(CAMS_FAMILY_SCOPE, path);
      return null;
    }
    transport.discard(CAMS_FAMILY_SCOPE, path);
    throw error;
  }
  try {
    const { document } = parseCanonicalJson(loaded.bytes, 4096, "CAMS continuity");
    validateCamsContinuity(document, {
      runId: release.source_run_id, releaseSha256: latest.latest.release_sha256,
      releaseJsonBytes: latest.latest.release_json_bytes, issuedAt: release.published_at, catalog,
    });
    loaded.commit();
    return deepFreeze(document);
  } catch (error) {
    transport.discard(CAMS_FAMILY_SCOPE, path);
    fail("CONTINUITY_MISMATCH", "policy di continuita CAMS non verificabile", error);
  }
}

function createCamsFamilyClient({ catalog, now, transport, camsContinuity }) {
  const latestPath = "latest.json";
  const state = transport.camsFamilyState();
  const fetchLatest = async (signal, onFamilyLatest) => {
    const latestLoaded = await transport.request(CAMS_FAMILY_SCOPE, latestPath, signal);
    let releaseLoaded = null;
    let releasePath = null;
    let latestCandidate = null;
    try {
      const latestParsed = parseCanonicalJson(
        latestLoaded.bytes,
        MAX_LATEST_BYTES,
        "CAMS family latest",
      );
      const latest = validateCamsFamilyLatest(latestParsed.document, catalog);
      latestCandidate = latest;
      let cacheInvalidationError = null;
      try {
        observeCamsFamilyLatest({
          latest,
          loaded: latestLoaded,
          state,
          transport,
          catalog,
        });
      } catch (error) {
        if (error?.code !== "CACHE_INVALIDATION_FAILED") throw error;
        cacheInvalidationError = error;
      }
      if (typeof onFamilyLatest === "function") {
        // This is a safety boundary, not an optional progress observer. The
        // snapshot has passed schema, catalog and transition validation, and
        // must reach the runtime even if purging the lower-level raw cache
        // failed. A runtime persistence error must remain observable.
        onFamilyLatest(camsFamilyDecisionSnapshot(latest));
      }
      if (cacheInvalidationError) throw cacheInvalidationError;
      const descriptor = latest.latest;
      releasePath = descriptor.release_path;
      releaseLoaded = await transport.request(CAMS_FAMILY_SCOPE, releasePath, signal,
        latestLoaded.networkFallback ? null : descriptor.release_sha256);
      if (
        releaseLoaded.bytes.length !== descriptor.release_json_bytes ||
        sha256Hex(releaseLoaded.bytes) !== descriptor.release_sha256
      ) {
        fail("INTEGRITY_MISMATCH", "SHA-256 o dimensione release CAMS non coincide con family latest");
      }
      const releaseParsed = parseCanonicalJson(
        releaseLoaded.bytes,
        MAX_RELEASE_BYTES,
        "CAMS family release",
      );
      const release = validateCamsFamilyRelease(releaseParsed.document, latest, catalog);
      if (release.source_run_id !== descriptor.source_run_id) {
        fail("RUN_MISMATCH", "release CAMS non coincide col run indicato da family latest");
      }
      const continuity = camsContinuity
        ? await readCamsContinuity({ latest, release, transport, signal, catalog }) : null;
      const members = validateCamsFamilyMembers(latest, release, catalog, now, continuity);

      // The immutable release is persisted first. A crash between these two
      // writes can leave an unreachable release, never a latest pointer whose
      // release is absent. The two CAMS provider caches are therefore never
      // used to reconstruct a family snapshot.
      const releaseCachePersisted = releaseLoaded.fromCache
        ? releaseLoaded.cachePersisted
        : releaseLoaded.commit();
      const releaseIsSafeForLatest = releaseCachePersisted || !transport.hasPersistentStorage();
      const latestCachePersisted = releaseIsSafeForLatest
        ? (latestLoaded.fromCache ? latestLoaded.cachePersisted : latestLoaded.commit())
        : false;
      const family = Object.freeze({
        document: deepFreeze(latest),
        release: deepFreeze(release),
        continuity,
        path: `${CAMS_FAMILY_SCOPE}/${latestPath}`,
        releasePath: `${CAMS_FAMILY_SCOPE}/${releasePath}`,
        etag: latestLoaded.etag,
        releaseEtag: releaseLoaded.etag,
        fromCache: latestLoaded.fromCache && releaseLoaded.fromCache,
        notModified: latestLoaded.notModified && releaseLoaded.notModified,
        ...(
          latestLoaded.networkFallback || releaseLoaded.networkFallback
            ? {
              networkFallback: true,
              fallbackReason: latestLoaded.fallbackReason ?? releaseLoaded.fallbackReason,
            }
            : {}
        ),
        ...(
          !latestLoaded.fromCache || !releaseLoaded.fromCache
            ? { cachePersisted: Boolean(releaseCachePersisted && latestCachePersisted) }
            : {}
        ),
      });
      CAMS_FAMILY_MEMBERS.set(family, Object.freeze({ members, state }));
      return family;
    } catch (error) {
      if (
        latestCandidate
        && state.latest === latestCandidate
        && error
        && (typeof error === "object" || typeof error === "function")
      ) {
        try {
          Object.defineProperty(error, "camsFamilyLatest", {
            configurable: true,
            value: camsFamilyDecisionSnapshot(latestCandidate),
          });
        } catch {
          // A non-extensible platform error still fails closed in the raw client.
        }
      }
      if (releaseLoaded?.fromCache && releasePath) {
        transport.discard(CAMS_FAMILY_SCOPE, releasePath);
      }
      if (latestLoaded.fromCache) transport.discard(CAMS_FAMILY_SCOPE, latestPath);
      throw error;
    }
  };

  return Object.freeze({
    family: CAMS_FAMILY,

    fetchLatest,

    async fetchMembersLatest(signal, onFamilyLatest) {
      const family = await fetchLatest(signal, onFamilyLatest);
      return Object.freeze({
        family,
        camsEurope: camsMemberLatestFromFamily({
          family,
          provider: WEATHER_V1_PROVIDERS.CAMS_EUROPE,
          role: "core",
          catalog,
        }),
        camsPollen: camsMemberLatestFromFamily({
          family,
          provider: WEATHER_V1_PROVIDERS.CAMS_EUROPE_POLLEN,
          role: "pollen",
          catalog,
        }),
      });
    },

    clearLatestCache() {
      transport.discard(CAMS_FAMILY_SCOPE, latestPath);
    },
  });
}

function createCamsMemberClient({ provider, catalog, istatCodes, now, transport, familyClient }) {
  const role = componentRoleFor(provider);
  return Object.freeze({
    provider,

    async fetchLatest(signal, onFamilyLatest) {
      const family = await familyClient.fetchLatest(signal, onFamilyLatest);
      return camsMemberLatestFromFamily({ family, provider, role, catalog });
    },

    async fetchManifest(latestValue, signal) {
      const latestDocument = documentFrom(latestValue, "latest");
      const latest = validateLatest(latestDocument, provider, catalog);
      const context = CAMS_MEMBER_CONTEXT.get(latestValue) ?? CAMS_MEMBER_CONTEXT.get(latestDocument);
      if (!context || context.provider !== provider || context.role !== role) {
        fail(
          "FAMILY_CONTEXT_REQUIRED",
          "manifest CAMS richiede il token verificato della release familiare corrente",
        );
      }
      assertCamsContextEnabled(context);
      const descriptor = context.component;
      if (
        descriptor.source_run_id !== latest.latest.source_run_id ||
        context.family.document.latest.source_run_id !== descriptor.source_run_id ||
        context.family.release.source_run_id !== descriptor.source_run_id
      ) {
        fail("RUN_MISMATCH", "token CAMS e release familiare non identificano lo stesso run");
      }
      const path = relativeManifestPath(provider, descriptor);
      const loaded = await transport.request(provider, path, signal,
        context.family.networkFallback ? null : descriptor.manifest_sha256);
      try {
        assertCamsContextEnabled(context);
        if (
          loaded.bytes.length !== descriptor.manifest_json_bytes ||
          sha256Hex(loaded.bytes) !== descriptor.manifest_sha256
        ) {
          fail("INTEGRITY_MISMATCH", "SHA-256 o dimensione manifest non coincide con release CAMS");
        }
        const parsed = parseCanonicalJson(loaded.bytes, MAX_MANIFEST_BYTES, `${provider} manifest`);
        const manifest = validateManifest(parsed.document, provider, catalog, istatCodes);
        if (manifest.source_run_id !== descriptor.source_run_id || manifest.run_at !== latest.latest.run_at) {
          fail("RUN_MISMATCH", "manifest non coincide col run CAMS rilasciato atomicamente");
        }
        const freshness = assessFreshness(manifest, provider, now, null, context.family.continuity);
        assertCamsContextEnabled(context);
        const cachePersisted = loaded.commit();
        const manifestResult = result(manifest, loaded, path, freshness, cachePersisted);
        if (context.family.networkFallback || loaded.networkFallback) {
          PREFETCH_BLOCKED_MANIFESTS.add(manifestResult);
          PREFETCH_BLOCKED_MANIFESTS.add(manifestResult.document);
        }
        CAMS_MEMBER_CONTEXT.set(manifestResult, context);
        CAMS_MEMBER_CONTEXT.set(manifestResult.document, context);
        return manifestResult;
      } catch (error) {
        if (loaded.fromCache) transport.discard(provider, path);
        throw error;
      }
    },

    async fetchMunicipality(manifestValue, istatCode, signal) {
      if (typeof istatCode !== "string" || !istatCodes.includes(istatCode)) {
        fail("ISTAT_MISMATCH", "codice ISTAT richiesto non presente nel catalogo v1");
      }
      const manifestDocument = documentFrom(manifestValue, "manifest");
      const context = CAMS_MEMBER_CONTEXT.get(manifestValue) ?? CAMS_MEMBER_CONTEXT.get(manifestDocument);
      if (!context || context.provider !== provider || context.role !== role) {
        fail(
          "FAMILY_CONTEXT_REQUIRED",
          "payload CAMS richiede il manifest legato alla release familiare corrente",
        );
      }
      assertCamsContextEnabled(context);
      const manifest = validateManifest(manifestDocument, provider, catalog, istatCodes);
      if (manifest.source_run_id !== context.family.release.source_run_id) {
        fail("RUN_MISMATCH", "manifest CAMS non appartiene alla release familiare verificata");
      }
      const descriptor = manifest.objects[istatCode];
      const path = descriptor.path;
      const loaded = await transport.request(provider, path, signal,
        transport.readPrefetchedObject && !manifestValue?.networkFallback && !context.family.networkFallback
          && !PREFETCH_BLOCKED_MANIFESTS.has(manifestValue) ? descriptor.sha256 : null);
      try {
        assertCamsContextEnabled(context);
        if (loaded.bytes.length !== descriptor.json_bytes || sha256Hex(loaded.bytes) !== descriptor.sha256) {
          fail("INTEGRITY_MISMATCH", `SHA-256 o dimensione payload ${istatCode} non coincide col manifest`);
        }
        const parsed = parseCanonicalJson(loaded.bytes, MAX_PAYLOAD_BYTES, `${provider} payload ${istatCode}`);
        const payload = validatePayload(parsed.document, provider, catalog, istatCode, manifest);
        const freshness = assessFreshness(payload, provider, now, null, context.family.continuity);
        assertCamsContextEnabled(context);
        const cachePersisted = loaded.commit();
        return result(payload, loaded, path, freshness, cachePersisted);
      } catch (error) {
        if (loaded.fromCache) transport.discard(provider, path);
        throw error;
      }
    },

    clearLatestCache() {
      familyClient.clearLatestCache();
    },
  });
}

// Bootstrap may consult revocations before attempting network I/O. This reads
// the same scoped raw pointer used by the client; it never accepts a derived
// bundle or bypasses cache hash, canonical JSON, provider or catalog checks.
export function readCachedIconLatest({ baseUrl, storage, catalog, istatCodes } = {}) {
  try {
    const normalized = normalizeConfigCatalog(catalog, istatCodes);
    const transport = new ConditionalJsonTransport({
      baseUrl: normalizeBaseUrl(baseUrl),
      storage,
      force: false,
    });
    const cached = transport.read(WEATHER_V1_PROVIDERS.ICON2I, "latest.json");
    if (!cached) return null;
    const parsed = parseCanonicalJson(cached.bytes, MAX_LATEST_BYTES, "ICON latest cached");
    return deepFreeze(validateLatest(parsed.document, WEATHER_V1_PROVIDERS.ICON2I, normalized.catalog));
  } catch {
    return null;
  }
}

export function createWeatherV1Client({
  baseUrl,
  fetchImpl,
  storage,
  now,
  catalog,
  istatCodes,
  force = false,
  iconWindowPolicy = null,
  readPrefetchedObject = null,
  camsContinuity = false,
} = {}) {
  validateDependencies(fetchImpl, now, force);
  if (typeof camsContinuity !== "boolean") fail("INVALID_CONFIG", "camsContinuity deve essere booleano");
  if (readPrefetchedObject !== null && typeof readPrefetchedObject !== "function") {
    fail("INVALID_CONFIG", "lettura prefetch weather v1 non valida");
  }
  const normalizedIconWindowPolicy = normalizeIconWindowPolicy(iconWindowPolicy);
  const normalized = normalizeConfigCatalog(catalog, istatCodes);
  const transport = new ConditionalJsonTransport({
    baseUrl: normalizeBaseUrl(baseUrl),
    fetchImpl,
    storage,
    force,
    iconWindowPolicy: normalizedIconWindowPolicy,
    readPrefetchedObject,
  });
  const camsFamily = createCamsFamilyClient({
    catalog: normalized.catalog,
    now,
    transport,
    camsContinuity,
  });
  return Object.freeze({
    icon2i: createProviderClient({
      provider: WEATHER_V1_PROVIDERS.ICON2I,
      catalog: normalized.catalog,
      istatCodes: normalized.istatCodes,
      now,
      transport,
      iconWindowPolicy: normalizedIconWindowPolicy,
    }),
    camsFamily,
    camsEurope: createCamsMemberClient({
      provider: WEATHER_V1_PROVIDERS.CAMS_EUROPE,
      catalog: normalized.catalog,
      istatCodes: normalized.istatCodes,
      now,
      transport,
      familyClient: camsFamily,
    }),
    camsPollen: createCamsMemberClient({
      provider: WEATHER_V1_PROVIDERS.CAMS_EUROPE_POLLEN,
      catalog: normalized.catalog,
      istatCodes: normalized.istatCodes,
      now,
      transport,
      familyClient: camsFamily,
    }),
  });
}
