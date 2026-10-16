import {
  NATIONAL_OFFICIAL_ALERTS_RECHECK_INTERVAL_MS,
  NATIONAL_OFFICIAL_ALERTS_STORAGE_MAX_AGE_MS,
  readNationalOfficialAlertsCache,
  writeNationalOfficialAlertsCache,
} from "../../services/nationalOfficialAlertsCache";
import {
  fetchNationalOfficialAlertsPayload,
  getNationalOfficialAlertsIstat,
} from "../../services/nationalOfficialAlertsApi";

const CONTRACT = "meteofriul.official_alerts.location.v1";

function nowValue(now) {
  return typeof now === "function" ? now() : now;
}

function errorMessage(error) {
  return error instanceof Error ? error.message : String(error || "Errore sconosciuto");
}

export function isUsableNationalOfficialAlerts(payload, location, { now = Date.now } = {}) {
  const expectedIstat = getNationalOfficialAlertsIstat(location);
  const expiresAt = Date.parse(String(payload?.expires_at || ""));
  return Boolean(
    expectedIstat
      && payload?.contract === CONTRACT
      && Number(payload?.schema_version) === 1
      && payload?.municipality?.istat === expectedIstat
      && payload?.standalone_display_allowed === true
      && Array.isArray(payload?.zones)
      && payload.zones.length
      && Array.isArray(payload?.records)
      && payload.records.length
      && Number.isFinite(expiresAt)
      && expiresAt > nowValue(now),
  );
}

export function createNationalOfficialAlertsState(
  payload = null,
  { error = null, fromCache = false, isStale = false } = {},
) {
  return {
    data: payload,
    error: error ? errorMessage(error) : null,
    fromCache,
    isStale,
    status: payload ? (error ? "stale" : fromCache ? "cache" : "fresh") : error ? "error" : "empty",
  };
}

export function readInitialNationalOfficialAlerts(
  location,
  {
    now = Date.now,
    storage,
    cacheReader = readNationalOfficialAlertsCache,
  } = {},
) {
  const recent = cacheReader(location, {
    maxAgeMs: NATIONAL_OFFICIAL_ALERTS_RECHECK_INTERVAL_MS,
    now,
    storage,
  });
  if (isUsableNationalOfficialAlerts(recent, location, { now })) {
    return createNationalOfficialAlertsState(recent, { fromCache: true });
  }
  const fallback = cacheReader(location, {
    maxAgeMs: NATIONAL_OFFICIAL_ALERTS_STORAGE_MAX_AGE_MS,
    now,
    storage,
  });
  return isUsableNationalOfficialAlerts(fallback, location, { now })
    ? createNationalOfficialAlertsState(fallback, { fromCache: true, isStale: true })
    : createNationalOfficialAlertsState();
}

export async function loadNationalOfficialAlerts(
  location,
  {
    cacheReader = readNationalOfficialAlertsCache,
    cacheWriter = writeNationalOfficialAlertsCache,
    fetcher = fetchNationalOfficialAlertsPayload,
    force = false,
    now = Date.now,
    storage,
  } = {},
) {
  if (!getNationalOfficialAlertsIstat(location)) {
    return createNationalOfficialAlertsState(null, {
      error: new Error("Codice ISTAT del Comune mancante"),
    });
  }

  const recent = cacheReader(location, {
    maxAgeMs: NATIONAL_OFFICIAL_ALERTS_RECHECK_INTERVAL_MS,
    now,
    storage,
  });
  const fallback = recent || cacheReader(location, {
    maxAgeMs: NATIONAL_OFFICIAL_ALERTS_STORAGE_MAX_AGE_MS,
    now,
    storage,
  });
  if (!force && isUsableNationalOfficialAlerts(recent, location, { now })) {
    return createNationalOfficialAlertsState(recent, { fromCache: true });
  }

  try {
    const payload = await fetcher(location, { force, now });
    if (!isUsableNationalOfficialAlerts(payload, location, { now })) {
      throw new Error("Contratto allerte nazionali non verificato");
    }
    cacheWriter(location, payload, { now, storage });
    return createNationalOfficialAlertsState(payload);
  } catch (error) {
    if (isUsableNationalOfficialAlerts(fallback, location, { now })) {
      return createNationalOfficialAlertsState(fallback, {
        error,
        fromCache: true,
        isStale: !recent,
      });
    }
    return createNationalOfficialAlertsState(null, { error });
  }
}
