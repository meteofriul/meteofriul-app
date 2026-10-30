import { API_BASE } from "./apiConfig";
import bootstrap from "../data/markets/catalogue2026.json";

export const MARKETS_CATALOGUE_CACHE_PREFIX = "meteofriul:markets-catalogue:v2:";
const emptyCatalogue = { schemaVersion: 2, revision: -1, markets: [], dates: [], identities: [], tombstones: [], validThrough: "1970-01-01" };
const blockedStatuses = new Set(["archived", "withdrawn", "suspended", "cancelled"]);

export function resolveMarketsApiBase(env = import.meta.env, fallback = API_BASE) {
  const configured = String(env?.VITE_MARKETS_API_BASE || "").trim();
  if (!configured) return fallback;
  const url = new URL(configured);
  if (url.protocol !== "https:" || url.username || url.password || url.search || url.hash
    || url.pathname.replace(/\/$/, "") !== "/api") throw new Error("markets_api_base_must_be_https_api");
  return url.href.replace(/\/$/, "");
}
export const MARKETS_API_BASE = resolveMarketsApiBase();

function defaultStorage() {
  try { return globalThis.localStorage || null; } catch { return null; }
}
function civilDay(timestamp) {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/Rome", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date(timestamp));
}
export function marketsCatalogueUrl(apiBase = MARKETS_API_BASE) {
  return `${String(apiBase).replace(/\/$/, "")}/markets/catalogue`;
}
export function validateMarketsCatalogue(value) {
  if (value?.schemaVersion !== 2 || !Number.isSafeInteger(value.revision) || value.revision < 0
    || !String(value.snapshotId || "").trim() || !Number.isFinite(Date.parse(value.expiresAt))
    || !/^\d{4}-\d{2}-\d{2}$/.test(value.validThrough || "")
    || ![value.markets, value.dates, value.identities, value.tombstones].every(Array.isArray)) {
    throw new Error("Catalogo mercati non valido");
  }
  const marketIds = new Set(), editionIds = new Set();
  for (const market of value.markets) {
    if (!market?.id || marketIds.has(market.id) || !market.name || !market.comune
      || !Array.isArray(market.weekdays)) throw new Error("Identità mercato non valida");
    marketIds.add(market.id);
  }
  for (const edition of value.dates) {
    if (!edition?.id || editionIds.has(edition.id) || !marketIds.has(edition.marketId)
      || !/^\d{4}-\d{2}-\d{2}$/.test(edition.date || "")) throw new Error("Edizione mercato non valida");
    editionIds.add(edition.id);
  }
  for (const identity of value.identities) {
    if (!identity?.marketId || !identity.name || !identity.comune) throw new Error("Indice mercati non valido");
  }
  for (const tombstone of value.tombstones) {
    if (!tombstone?.marketId || ![...blockedStatuses, "rescheduled"].includes(tombstone.status)) {
      throw new Error("Ritiro mercato non valido");
    }
  }
  return value;
}

// Keep the last authoritative identity/revocation ledger even when its visible
// calendar expires. This key deliberately is not an ordinary disposable cache.
export function createMarketsCatalogueStore({
  apiBase = MARKETS_API_BASE, storage = defaultStorage(), fetchImpl = (...args) => globalThis.fetch(...args),
  now = Date.now, bootstrapCatalogue = bootstrap,
} = {}) {
  const url = marketsCatalogueUrl(apiBase);
  const key = MARKETS_CATALOGUE_CACHE_PREFIX + url;
  const markerKey = key + ":seen";
  let envelope = null, hasSeenRemote = false, highWater = null, inFlight = null;
  const listeners = new Set();
  try {
    const marker = storage?.getItem(markerKey);
    hasSeenRemote = marker != null;
    if (marker) {
      const parsed = JSON.parse(marker);
      if (Number.isSafeInteger(parsed?.revision)) highWater = parsed;
    }
    const saved = JSON.parse(storage?.getItem(key) || "null");
    if (saved) {
      hasSeenRemote = true;
      validateMarketsCatalogue(saved.catalogue);
      if (highWater && (saved.catalogue.revision < highWater.revision
        || (saved.catalogue.revision === highWater.revision && saved.catalogue.snapshotId !== highWater.snapshotId))) {
        throw new Error("Cache mercati precedente all’ultima revisione");
      }
      envelope = saved;
      highWater = { revision: saved.catalogue.revision, snapshotId: saved.catalogue.snapshotId };
    }
  } catch { /* A malformed remote cache must never reopen the packaged seed. */ }

  function initialState() {
    if (envelope) {
      const expired = now() >= Date.parse(envelope.catalogue.expiresAt);
      return { catalogue: { ...envelope.catalogue, unavailable: expired }, status: expired ? "expired" : "cached", error: null };
    }
    const bootstrapValid = !hasSeenRemote && civilDay(now()) <= bootstrapCatalogue.validThrough;
    return { catalogue: bootstrapValid ? bootstrapCatalogue : { ...emptyCatalogue, unavailable: true, blockUnknownMarkets: hasSeenRemote },
      status: bootstrapValid ? "bootstrap" : "unavailable", error: null };
  }
  let state = initialState();
  const emit = next => { state = next; listeners.forEach(listener => listener()); };
  function syncStorage() {
    try {
      const marker = JSON.parse(storage?.getItem(markerKey) || "null");
      if (!Number.isSafeInteger(marker?.revision) || (highWater && marker.revision < highWater.revision)
        || (envelope?.catalogue.revision === marker.revision && envelope.catalogue.snapshotId === marker.snapshotId)) return;
      hasSeenRemote = true;
      highWater = marker;
      try {
        const saved = JSON.parse(storage?.getItem(key) || "null");
        validateMarketsCatalogue(saved?.catalogue);
        if (saved.catalogue.revision !== marker.revision || saved.catalogue.snapshotId !== marker.snapshotId) throw new Error("Snapshot incompleto");
        envelope = saved;
        emit(initialState());
      } catch {
        // Another reader has already seen a newer revision. Until its complete
        // payload is available, neither this old copy nor a late response wins.
        emit({ catalogue: { ...(envelope?.catalogue || emptyCatalogue), unavailable: true, blockUnknownMarkets: true }, status: "unavailable", error: null });
      }
    } catch { /* Keep the in-memory high-water mark if storage is unavailable. */ }
  }
  function checkExpiry() {
    if (envelope && now() >= Date.parse(envelope.catalogue.expiresAt) && !state.catalogue.unavailable) {
      emit({ ...state, catalogue: { ...envelope.catalogue, unavailable: true }, status: "expired" });
    } else if (!envelope && state.status === "bootstrap"
      && civilDay(now()) > bootstrapCatalogue.validThrough) {
      emit({ ...state, catalogue: { ...emptyCatalogue, unavailable: true }, status: "unavailable" });
    }
  }
  async function refresh() {
    syncStorage();
    checkExpiry();
    if (inFlight) return inFlight;
    inFlight = Promise.resolve().then(async () => {
      try {
        const response = await fetchImpl(url, { cache: "no-store" });
        if (!response?.ok) throw new Error("Catalogo mercati non disponibile");
        const catalogue = validateMarketsCatalogue(await response.json());
        syncStorage();
        const previous = highWater;
        if (previous && (catalogue.revision < previous.revision
          || (catalogue.revision === previous.revision && catalogue.snapshotId !== previous.snapshotId))) {
          throw new Error("Revisione mercati superata o incoerente");
        }
        // A snapshot is immutable. A successful fetch cannot renew its expiry.
        envelope = { catalogue };
        hasSeenRemote = true;
        highWater = { revision: catalogue.revision, snapshotId: catalogue.snapshotId };
        try {
          storage?.setItem(markerKey, JSON.stringify(highWater));
          storage?.setItem(key, JSON.stringify(envelope));
        } catch { /* Keep current-session safety even when device storage is full. */ }
        const expired = now() >= Date.parse(catalogue.expiresAt);
        emit({ catalogue: { ...catalogue, unavailable: expired }, status: expired ? "expired" : "fresh", error: null });
        return state;
      } catch (error) {
        checkExpiry();
        emit({ ...state, error: String(error?.message || error) });
        return state;
      } finally { inFlight = null; }
    });
    return inFlight;
  }
  return { getSnapshot: () => state, subscribe: listener => { listeners.add(listener); return () => listeners.delete(listener); }, refresh, checkExpiry, syncStorage };
}
