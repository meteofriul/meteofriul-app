import {
  fetchLocalWeatherV1CamsSupplement,
  LOCAL_WEATHER_V1_CATALOG,
  LOCAL_WEATHER_V1_ISTAT_CODES,
} from "./localWeatherV1Adapter";

const HOUR_MS = 3_600_000;
const VERIFY_WINDOW_MS = 60_000;
const entries = new Map();

function milliseconds(now) {
  const value = typeof now === "function" ? now() : now;
  const result = value instanceof Date ? value.getTime() : Number(value);
  if (!Number.isFinite(result)) throw new Error("Orologio CAMS nazionale non valido");
  return result;
}

function municipalityCode(bundle) {
  // Use the national reader's verified municipality, not a locality/GPS index
  // or a similarly named municipality. Only the existing 215 CAMS codes qualify.
  const code = bundle?.current?.source?.municipality_istat;
  return LOCAL_WEATHER_V1_ISTAT_CODES.includes(code) ? code : null;
}

function keyFor(bundle, baseUrl) {
  const code = municipalityCode(bundle);
  return code ? `${String(baseUrl).replace(/\/+$/, "")}|${code}` : null;
}

function unavailable(code = "CAMS_UNAVAILABLE") {
  return {
    available: false,
    status: "unavailable",
    diagnostic: { code, provider: "cams_europe_pollen", status: "unavailable" },
  };
}

function withCams(bundle, supplement, status = supplement?.status || "unavailable") {
  const available = supplement?.available === true
    && supplement.municipality_istat === municipalityCode(bundle)
    && supplement.catalog?.sha256 === LOCAL_WEATHER_V1_CATALOG.sha256;
  if (supplement?.available && !available) {
    supplement = unavailable("PROVIDER_IDENTITY_MISMATCH");
    status = "unavailable";
  }
  const pending = status === "pending";
  const source = supplement?.source || {
    provider: "cams_europe_pollen", source_provider: "cams_europe",
    status: pending ? "pending" : "unavailable", diagnostic: supplement?.diagnostic || null,
  };
  const decorate = value => ({
    ...value,
    source: { ...value.source, cams: source },
    model_support: { ...value.model_support, cams: available },
    data_quality: {
      ...value.data_quality,
      cams_status: available ? status : pending ? "pending" : "unavailable",
      cams_coverage: "fvg_only",
      cams_catalog_sha256: available ? supplement.catalog.sha256 : null,
      cams_run_utc: available ? supplement.pollen_data.run_utc : null,
      cams_valid_at_utc: available ? supplement.pollen_data.valid_at_utc : null,
      cams_sample_status: available ? "current" : null,
      cams_diagnostic: supplement?.diagnostic || null,
      capability_gaps: [...new Set([
        ...(value.data_quality?.capability_gaps || []).filter(gap => !["cams_pollen", "cams_pollen_pending"].includes(gap)),
        ...(available ? [] : [pending ? "cams_pollen_pending" : "cams_pollen"]),
      ])],
      flags: [...new Set([
        ...(value.data_quality?.flags || []).filter(flag => !["cams_unavailable", "cams_pending"].includes(flag)),
        ...(available ? [] : [pending ? "cams_pending" : "cams_unavailable"]),
      ])],
    },
  });
  return {
    ...bundle,
    current: {
      ...decorate(bundle.current),
      pollen: available ? supplement.pollen : pending ? "Pollini CAMS in arrivo" : null,
      pollen_data: available ? supplement.pollen_data : {
        status: pending ? "pending" : "unavailable",
        note: pending ? "Dati CAMS in arrivo" : "CAMS pilota disponibile solo per i comuni FVG coperti; nessun fallback",
        diagnostic: supplement?.diagnostic || null,
      },
      air_quality_data: available ? supplement.air_quality_data : null,
      cams_hourly_cache: available ? supplement.cams_hourly_cache : null,
    },
    forecast: decorate(bundle.forecast),
  };
}

function recentSupplement(entry, { now, verificationNow, verifyWindowMs }) {
  if (!entry?.supplement || entry.supplement.available !== true) return null;
  const elapsed = milliseconds(verificationNow) - entry.verifiedAt;
  if (elapsed < 0 || elapsed >= verifyWindowMs) return null;
  const time = milliseconds(now);
  const validAt = Date.parse(entry.supplement.pollen_data?.valid_at_utc);
  const usableUntil = Date.parse(entry.supplement.usable_until_utc);
  // Crossing an hour or the freshness boundary requires a new verified read;
  // never relabel a previously selected value as the current sample.
  const freshUntil = Date.parse(entry.supplement.fresh_until_utc);
  if (!Number.isFinite(validAt) || !Number.isFinite(usableUntil)
    || time < validAt || time - validAt >= HOUR_MS || time > usableUntil
    || (entry.supplement.status === "fresh" && time > freshUntil)) return null;
  return entry.supplement;
}

function deliver(callback, value, stillCurrent = () => true) {
  if (typeof callback !== "function") return;
  globalThis.setTimeout(() => {
    if (!stillCurrent()) return;
    try { Promise.resolve(callback(value)).catch(() => {}); } catch { /* Optional observer. */ }
  }, 0);
}

export function readNationalWeatherV2CamsBundle(bundle, {
  baseUrl, now = Date.now, verificationNow = Date.now, verifyWindowMs = VERIFY_WINDOW_MS,
} = {}) {
  const key = keyFor(bundle, baseUrl);
  if (!key) return withCams(bundle, unavailable("CAMS_COVERAGE_UNAVAILABLE"));
  const entry = entries.get(key);
  const supplement = recentSupplement(entry, { now, verificationNow, verifyWindowMs });
  return withCams(bundle, supplement, supplement?.status || (entry?.promise ? "pending" : "unavailable"));
}

export async function enrichNationalWeatherV2WithCams(bundle, {
  baseUrl, fetchImpl = globalThis.fetch, storage = null,
  now = Date.now, verificationNow = Date.now, verifyWindowMs = VERIFY_WINDOW_MS,
  force = false, deferCams = false, retryUnavailableCams = false, onCamsUpdate, onCamsFailure,
  camsFetcher = fetchLocalWeatherV1CamsSupplement,
} = {}) {
  if (typeof deferCams !== "boolean" || typeof force !== "boolean" || typeof retryUnavailableCams !== "boolean"
    || !Number.isInteger(verifyWindowMs) || verifyWindowMs < 0 || verifyWindowMs > 600_000
    || (onCamsUpdate !== undefined && typeof onCamsUpdate !== "function")
    || (onCamsFailure !== undefined && typeof onCamsFailure !== "function")) {
    throw new Error("Configurazione CAMS nazionale non valida");
  }
  const key = keyFor(bundle, baseUrl);
  if (!key) return withCams(bundle, unavailable("CAMS_COVERAGE_UNAVAILABLE"));
  let entry = entries.get(key);
  const recent = !force && recentSupplement(entry, { now, verificationNow, verifyWindowMs });
  if (recent) return withCams(bundle, recent);
  if (force || !entry?.promise) {
    entry = { supplement: null, verifiedAt: null, promise: null };
    entries.set(key, entry);
    while (entries.size > 32) entries.delete(entries.keys().next().value);
    const code = municipalityCode(bundle);
    entry.promise = Promise.resolve().then(() => camsFetcher({
      city: bundle.city, municipality: { istatCode: code, name: bundle.city },
    }, {
      baseUrl, fetchImpl, storage, now, force,
      // A new verified decision invalidates the older in-memory sample even
      // if a following payload read fails. The v1 client enforces revocations.
      onCamsFamilyLatest: () => {
        entry.supplement = null;
        const scope = key.slice(0, key.lastIndexOf("|") + 1);
        for (const [otherKey, other] of entries) {
          if (otherKey.startsWith(scope) && other !== entry) other.supplement = null;
        }
      },
    })).then(supplement => {
      if (supplement?.municipality_istat !== code
        || supplement?.catalog?.sha256 !== LOCAL_WEATHER_V1_CATALOG.sha256) {
        return unavailable("PROVIDER_IDENTITY_MISMATCH");
      }
      return supplement;
    }).catch(error => {
      deliver(onCamsFailure, error, () => entries.get(key) === entry);
      return unavailable();
    }).then(supplement => {
      if (entries.get(key) === entry) {
        entry.supplement = supplement;
        entry.verifiedAt = milliseconds(verificationNow);
        entry.promise = null;
      }
      return supplement;
    });
  }
  const pending = entry.promise;
  const currentEntry = () => entries.get(key) === entry;
  if (!deferCams) {
    const supplement = await pending;
    return withCams(bundle, currentEntry() ? supplement : unavailable("CAMS_REQUEST_SUPERSEDED"));
  }
  void pending.then(supplement => {
    deliver(onCamsUpdate, withCams(bundle, supplement), currentEntry);
  }).catch(error => deliver(onCamsFailure, error, currentEntry));
  return withCams(bundle, null, "pending");
}

// No enriched national bundle is written to persistent storage: after a cold
// start CAMS must pass the existing family/release/revocation verifier again.
export function clearNationalWeatherV2CamsRuntime() {
  entries.clear();
}
