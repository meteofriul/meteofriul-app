import { API_BASE, isAndroidCapacitorRuntime } from "./apiConfig";
import { getDateTimeFormatter } from "../domain/dateTimeFormatters.js";
import { isLocalWeatherPilot } from "./localWeatherPilot";
import { getLocationMunicipalityName } from "../domain/geo/locationIdentity";
import { projectPilotProgrammeCards } from "./pilotProgrammeProjection";
import { readEventsCatalogHealth } from "./eventsCatalogHealth";
import { FIXED_FVG_PLACES } from "../data/fvgPlaces";

const LOCAL_EVENTS_API = import.meta.env.VITE_LOCAL_EVENTS_API_BASE || "";
export const PRODUCTION_EVENTS_API = LOCAL_EVENTS_API ? "" : "https://meteofriul-events-49007668366.europe-west1.run.app/api";
// Compatibility export for the local-pilot UI. It now resolves to the same
// official catalogue as production; the retired pilot project is never read.
export const PILOT_EVENTS_API = LOCAL_EVENTS_API || PRODUCTION_EVENTS_API;
export const LOCAL_PILOT_EVENTS_API = "/__pilot-events/api";
export const HOME_EVENTS_LIMIT = 8;
export const FULL_EVENTS_LIMIT = 100;
export const EVENTS_REFRESH_MAX_RETRIES = 20;
const inFlightEventLoads = new WeakMap();

export function resolveEventsApiBase({
  apiBase = API_BASE,
  localPilot = isLocalWeatherPilot(),
  nativeAndroid = isAndroidCapacitorRuntime(),
} = {}) {
  if (!localPilot) {
    return import.meta.env.PROD === true ? PRODUCTION_EVENTS_API : apiBase;
  }
  return nativeAndroid ? PILOT_EVENTS_API : LOCAL_PILOT_EVENTS_API;
}

function isPilotEventsApiBase(apiBase) {
  const normalized = String(apiBase || "").replace(/\/+$/, "");
  return normalized === PILOT_EVENTS_API || normalized === PRODUCTION_EVENTS_API || normalized === LOCAL_PILOT_EVENTS_API;
}

export function coerceFiniteNumber(value) {
  if (value == null || value === "" || typeof value === "boolean") return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

export function getEventsRequestLimit(limit = HOME_EVENTS_LIMIT) {
  return limit === HOME_EVENTS_LIMIT ? FULL_EVENTS_LIMIT : limit;
}

export function buildLocalEventsUrl(
  location,
  { apiBase = resolveEventsApiBase(), limit = HOME_EVENTS_LIMIT } = {},
) {
  const eventLocation = location && typeof location === "object" ? location : { city: location };
  const city = getLocationMunicipalityName(eventLocation);

  if (!city) {
    throw new Error("Localita eventi mancante");
  }

  const requestLimit = getEventsRequestLimit(limit);
  const params = new URLSearchParams({
    city,
    limit: String(requestLimit),
  });
  if (isPilotEventsApiBase(apiBase)) {
    const radius = Number(eventLocation.eventsRadius ?? 20);
    if (!Number.isInteger(radius) || radius < 5 || radius > 50 || radius % 5 !== 0) throw new Error("Raggio eventi non valido");
    params.set("radius", String(radius));
  }
  let lat = coerceFiniteNumber(eventLocation.lat);
  let lon = coerceFiniteNumber(eventLocation.lon);
  if ((lat === null || lon === null) && isPilotEventsApiBase(apiBase)) {
    // A fresh installation has a named placeholder municipality, not GPS.
    // Use its checked catalogue point only for the event-radius query.
    const istat = String(eventLocation.municipality?.istatCode || eventLocation.istatCode || "");
    const municipality = /^\d{6}$/u.test(istat)
      ? Object.values(FIXED_FVG_PLACES).find((place) => place.istatCode === istat)
      : null;
    if (municipality) {
      lat = coerceFiniteNumber(municipality.latitude);
      lon = coerceFiniteNumber(municipality.longitude);
    }
  }

  if (lat !== null && lon !== null) {
    params.set("lat", String(lat));
    params.set("lon", String(lon));
  }

  const base = String(apiBase || "").replace(/\/$/, "");
  return `${base}/local/events?${params.toString()}`;
}

export function buildLocalEventDetailUrl(event, { apiBase = resolveEventsApiBase() } = {}) {
  const source = String(event?.source || "").trim();
  const url = String(event?.url || "").trim();

  if (!source || !url) {
    throw new Error("Dettaglio evento incompleto");
  }

  const params = new URLSearchParams({ source, url });
  const base = String(apiBase || "").replace(/\/$/, "");
  return `${base}/local/events/detail?${params.toString()}`;
}

export function normalizeLocalEventsPayload(payload, { retry = 0 } = {}) {
  const events = Array.isArray(payload?.events) ? payload.events : [];
  const catalogHealth = readEventsCatalogHealth(payload);
  const isDegraded = catalogHealth?.status === "degraded";
  const cacheStatus = isDegraded ? "degraded" : payload?.cache?.status || null;
  const contractVersion = String(payload?.cache?.event_contract_version || "").trim() || null;
  const isRefreshing = cacheStatus === "refreshing" && events.length === 0;
  const isPartial = cacheStatus === "partial";

  return {
    events,
    total: events.length,
    cacheStatus,
    contractVersion,
    catalogHealth,
    isDegraded,
    isRefreshing,
    isPartial,
    shouldRetry: (isRefreshing || isPartial) && retry < EVENTS_REFRESH_MAX_RETRIES,
    raw: payload,
  };
}

export async function fetchLocalEvents(
  location,
  {
    apiBase = resolveEventsApiBase(),
    fetchImpl = globalThis.fetch,
    limit = HOME_EVENTS_LIMIT,
    retry = 0,
  } = {},
) {
  if (typeof fetchImpl !== "function") {
    throw new Error("Fetch non disponibile");
  }

  const url = buildLocalEventsUrl(location, { apiBase, limit });
  let requests = inFlightEventLoads.get(fetchImpl);
  if (!requests) {
    requests = new Map();
    inFlightEventLoads.set(fetchImpl, requests);
  }
  let request = requests.get(url);
  if (!request) {
    request = loadLocalEventsSnapshot(url, { apiBase, fetchImpl });
    requests.set(url, request);
    const clear = () => {
      if (requests.get(url) === request) requests.delete(url);
    };
    request.then(clear, clear);
  }
  // Share only work already in flight, including its complete page snapshot.
  // Completed/error responses never prevent a later explicit refresh.
  const payload = await request;
  return normalizeLocalEventsPayload(payload, { retry });
}

async function loadLocalEventsSnapshot(url, { apiBase, fetchImpl }) {
  const response = await fetchImpl(url);

  if (!response?.ok) {
    throw new Error("Risposta eventi non valida");
  }

  const payload = await response.json();
  if (isPilotEventsApiBase(apiBase) && Array.isArray(payload.events)) {
    // Collect one consistent snapshot in bounded pages. UI already reveals
    // filtered results progressively, without truncating the source list.
    let next = payload.next_offset;
    let previousOffset = 0;
    while (next != null) {
      if (!Number.isInteger(next) || next <= previousOffset || next > 10000) throw new Error("Paginazione eventi non valida");
      const queryIndex = url.indexOf("?");
      const pageBase = queryIndex >= 0 ? url.slice(0, queryIndex) : url;
      const pageParams = new URLSearchParams(queryIndex >= 0 ? url.slice(queryIndex + 1) : "");
      pageParams.set("offset", String(next));
      pageParams.set("snapshot", payload.snapshot);
      const pageResponse = await fetchImpl(`${pageBase}?${pageParams.toString()}`);
      if (!pageResponse.ok) throw new Error("Catalogo cambiato o pagina non disponibile: riprova");
      const page = await pageResponse.json();
      if (page.snapshot !== payload.snapshot || !Array.isArray(page.events)) throw new Error("Catalogo eventi incoerente");
      payload.events.push(...page.events);
      previousOffset = next;
      next = page.next_offset;
    }
    if (Number.isFinite(payload.total) && payload.events.length !== payload.total) throw new Error("Catalogo eventi incompleto");
    const dateLabel = (iso) => /^\d{4}-\d{2}-\d{2}$/.test(iso || "")
      ? getDateTimeFormatter("it-IT", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" }).format(new Date(`${iso}T12:00:00Z`)) : "";
    payload.raw_total = payload.total;
    payload.events = projectPilotProgrammeCards(payload.events).map((event) => ({ ...event,
      id: [event.url, event.start_date, event.time, event.title].join("|"),
      date: event.date || (["end_only", "month_range"].includes(event.schedule_kind) ? event.date_label :
        event.end_date && event.end_date !== event.start_date
        ? `dal ${dateLabel(event.start_date)} al ${dateLabel(event.end_date)}` : dateLabel(event.start_date)),
    }));
    payload.total = payload.events.length;
    payload.cache = {
      status: readEventsCatalogHealth(payload)?.status === "degraded" ? "degraded" : "ready",
      event_contract_version: "pilot-events-v2-programmes",
    };
  }
  return payload;
}

export async function fetchLocalEventDetail(
  event,
  { apiBase = resolveEventsApiBase(), fetchImpl = globalThis.fetch } = {},
) {
  const pilot = isPilotEventsApiBase(apiBase);
  if (!pilot && typeof fetchImpl !== "function") {
    throw new Error("Fetch non disponibile");
  }

  const response = pilot
    ? null
    : await fetchImpl(buildLocalEventDetailUrl(event, { apiBase }));

  if (!pilot && !response?.ok) {
    throw new Error("Risposta dettaglio evento non valida");
  }

  const payload = pilot ? (event?.raw || event || {}) : await response.json();
  return {
    description: String(payload?.description || "").trim(),
    eventCity: String(payload?.event_city || "").trim(),
    place: String(payload?.place || "").trim(),
    venue: String(payload?.venue || "").trim(),
    address: String(payload?.address || "").trim(),
    mapsUrl: String(payload?.maps_url || "").trim(),
    lat: coerceFiniteNumber(payload?.lat),
    lon: coerceFiniteNumber(payload?.lon),
    locationConfidence: String(payload?.location_confidence || "").trim(),
    raw: payload,
  };
}
