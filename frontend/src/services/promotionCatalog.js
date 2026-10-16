import { API_BASE } from "./apiConfig";
import {
  FIREBASE_APP_CHECK_HEADER,
  getFirebaseAppCheckToken,
} from "./firebaseAppCheckAdapter";

export const PROMOTION_CATALOG_CACHE_KEY = "meteofriul.promotion-catalog.v1";
export const PROMOTION_CATALOG_REFRESH_MS = 5 * 60 * 1000;
export const PROMOTION_CATALOG_SCHEMA_VERSION = 2;
export const PROMOTION_ROTATION_INTERVAL_SECONDS = 120;
export const PROMOTION_MAX_ROTATION_CAMPAIGNS = 5;
export const PROMOTION_PLACEMENTS = Object.freeze(["home", "events", "discover"]);
export const PROMOTION_ROTATION_INTERVAL_OPTIONS = Object.freeze([30, 60, 120, 300]);
export const PROMOTION_PLACEMENT_ROTATION_INTERVALS = Object.freeze({
  discover: PROMOTION_ROTATION_INTERVAL_SECONDS,
  events: PROMOTION_ROTATION_INTERVAL_SECONDS,
  home: PROMOTION_ROTATION_INTERVAL_SECONDS,
});
const MAX_ACCEPTED_CACHE_AGE_SECONDS = 10 * 60;

export const EMPTY_PROMOTION_CATALOG = Object.freeze({
  campaigns: Object.freeze([]),
  dailyCap: 0,
  enabled: false,
  fetchedAt: 0,
  maxRotationCampaigns: PROMOTION_MAX_ROTATION_CAMPAIGNS,
  maxAgeSeconds: 300,
  placementRotationIntervals: PROMOTION_PLACEMENT_ROTATION_INTERVALS,
  placements: PROMOTION_PLACEMENTS,
  revision: 0,
  rotationIntervalSeconds: PROMOTION_ROTATION_INTERVAL_SECONDS,
  schemaVersion: PROMOTION_CATALOG_SCHEMA_VERSION,
  timezone: "Europe/Rome",
});

function finiteInteger(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? Math.trunc(parsed) : fallback;
}

function safeHttpsUrl(value) {
  try {
    const url = new URL(String(value || "").trim());
    if (url.protocol !== "https:" || url.username || url.password) return "";
    return url.href;
  } catch {
    return "";
  }
}

function safeClockTime(value, { allowEndOfDay = false } = {}) {
  const selected = String(value || "").trim();
  if (!selected) return "";
  if (allowEndOfDay && selected === "24:00") return selected;
  return /^(?:[01]\d|2[0-3]):[0-5]\d$/u.test(selected) ? selected : "";
}

export function normalizePlacementRotationIntervals(value) {
  const source = value && typeof value === "object" ? value : {};
  return Object.fromEntries(PROMOTION_PLACEMENTS.map((placement) => {
    const interval = finiteInteger(
      source[placement],
      PROMOTION_PLACEMENT_ROTATION_INTERVALS[placement],
    );
    return [
      placement,
      PROMOTION_ROTATION_INTERVAL_OPTIONS.includes(interval)
        ? interval
        : PROMOTION_PLACEMENT_ROTATION_INTERVALS[placement],
    ];
  }));
}

function normalizeCampaign(value) {
  if (!value || typeof value !== "object" || value.enabled !== true) return null;
  const declaredPlacements = Array.isArray(value.placements) ? [...new Set(
    value.placements
      .map(item => String(item || "").trim().toLowerCase())
      .filter(item => PROMOTION_PLACEMENTS.includes(item)),
  )] : [];
  const rawAssignments = value.placementAssignments && typeof value.placementAssignments === "object"
    ? value.placementAssignments
    : {};
  const placementAssignments = Object.fromEntries(declaredPlacements.flatMap((placement) => {
    const assignment = rawAssignments[placement];
    const mode = String(assignment?.mode || "").trim().toLowerCase();
    if (
      !assignment
      || finiteInteger(assignment.cardNumber, 0) !== 1
      || !["exclusive", "rotation"].includes(mode)
    ) return [];
    return [[placement, { cardNumber: 1, mode }]];
  }));
  const placements = declaredPlacements.filter(placement => placementAssignments[placement]);
  const assignmentModes = [...new Set(
    Object.values(placementAssignments).map(assignment => assignment.mode),
  )];
  const id = String(value.id || "").trim().slice(0, 120);
  const url = safeHttpsUrl(value.url);
  const image = safeHttpsUrl(value.image);
  const advertiserId = String(value.advertiserId || "").trim().slice(0, 120);
  const title = String(value.title || "").trim().slice(0, 80);
  const text = String(value.text || "").trim().slice(0, 180);
  if (!id || !url || !image || !advertiserId || !title || !text || !placements.length) {
    return null;
  }
  return {
    advertiserDailyCap: Math.max(1, finiteInteger(value.advertiserDailyCap, 1)),
    advertiserId,
    bookingMode: assignmentModes.length === 1 ? assignmentModes[0] : "mixed",
    campaignDailyCap: Math.max(1, finiteInteger(value.campaignDailyCap, 1)),
    category: String(value.category || "").trim().slice(0, 120),
    businessAddress: String(value.businessAddress || "").trim().slice(0, 240),
    ctaLabel: String(value.ctaLabel || "").trim().slice(0, 50),
    activeDates: Array.isArray(value.activeDates)
      ? value.activeDates.map(item => String(item || "").trim()).filter(Boolean).slice(0, 366)
      : [],
    activeMonth: /^\d{4}-\d{2}$/u.test(String(value.activeMonth || "").trim())
      ? String(value.activeMonth).trim()
      : "",
    deliveryMode: "all_selected",
    enabled: true,
    endTime: safeClockTime(value.endTime, { allowEndOfDay: true }),
    endsAt: String(value.endsAt || "").trim().slice(0, 40),
    id,
    image,
    headline: String(value.headline || "").trim().slice(0, 80),
    location: String(value.location || "").trim().slice(0, 120),
    placementAssignments,
    placements,
    scheduleMode: ["days", "month"].includes(value.scheduleMode) ? value.scheduleMode : "period",
    startTime: safeClockTime(value.startTime),
    startsAt: String(value.startsAt || "").trim().slice(0, 40),
    text,
    title,
    url,
  };
}

export function normalizePromotionCatalog(value, { fetchedAt = Date.now() } = {}) {
  if (!value || typeof value !== "object" || value.enabled !== true) {
    return { ...EMPTY_PROMOTION_CATALOG, fetchedAt };
  }
  const schemaVersion = Math.max(1, finiteInteger(value.schemaVersion, 1));
  if (schemaVersion > PROMOTION_CATALOG_SCHEMA_VERSION) {
    return { ...EMPTY_PROMOTION_CATALOG, fetchedAt };
  }
  const campaigns = Array.isArray(value.campaigns)
    ? value.campaigns.map(normalizeCampaign).filter(Boolean)
    : [];
  if (!campaigns.length) return { ...EMPTY_PROMOTION_CATALOG, fetchedAt };
  const placementRotationIntervals = normalizePlacementRotationIntervals(
    value.placementRotationIntervals,
  );
  return {
    campaigns,
    dailyCap: Math.max(1, Math.min(20, finiteInteger(value.dailyCap, 1))),
    enabled: true,
    fetchedAt,
    maxRotationCampaigns: Math.max(1, Math.min(
      PROMOTION_MAX_ROTATION_CAMPAIGNS,
      finiteInteger(value.maxRotationCampaigns, PROMOTION_MAX_ROTATION_CAMPAIGNS),
    )),
    maxAgeSeconds: Math.max(60, Math.min(
      MAX_ACCEPTED_CACHE_AGE_SECONDS,
      finiteInteger(value.maxAgeSeconds, 300),
    )),
    placementRotationIntervals,
    placements: PROMOTION_PLACEMENTS.filter(placement => campaigns.some(
      campaign => campaign.placements.includes(placement),
    )),
    revision: Math.max(0, finiteInteger(value.revision, 0)),
    rotationIntervalSeconds: placementRotationIntervals.home,
    schemaVersion,
    timezone: value.timezone === "Europe/Rome" ? value.timezone : "Europe/Rome",
  };
}

export function readPromotionCatalogCache({
  now = Date.now(),
  storage = globalThis.localStorage,
} = {}) {
  try {
    const parsed = JSON.parse(storage?.getItem?.(PROMOTION_CATALOG_CACHE_KEY) || "null");
    const catalog = normalizePromotionCatalog(parsed, { fetchedAt: Number(parsed?.fetchedAt || 0) });
    const age = Number(now) - Number(catalog.fetchedAt || 0);
    if (!catalog.enabled || age < 0 || age > catalog.maxAgeSeconds * 1000) {
      return { ...EMPTY_PROMOTION_CATALOG };
    }
    return catalog;
  } catch {
    return { ...EMPTY_PROMOTION_CATALOG };
  }
}

export async function fetchPromotionCatalog({
  apiBase = API_BASE,
  fetchImpl = globalThis.fetch,
  now = Date.now,
  storage = globalThis.localStorage,
} = {}) {
  const fetchedAt = Number(now());
  try {
    const response = await fetchImpl(`${String(apiBase || "").replace(/\/$/, "")}/promotions/catalog`, {
      cache: "no-store",
      headers: { Accept: "application/json" },
      method: "GET",
    });
    if (!response?.ok) throw new Error(`promotion_catalog_http_${response?.status || 0}`);
    const catalog = normalizePromotionCatalog(await response.json(), { fetchedAt });
    storage?.setItem?.(PROMOTION_CATALOG_CACHE_KEY, JSON.stringify(catalog));
    return catalog;
  } catch {
    return readPromotionCatalogCache({ now: fetchedAt, storage });
  }
}

export async function recordPromotionEvent({
  apiBase = API_BASE,
  campaignId,
  fetchImpl = globalThis.fetch,
  placement = "home",
  tokenProvider = getFirebaseAppCheckToken,
  type,
} = {}) {
  if (!campaignId || !["impression", "open"].includes(type)) return false;
  let appCheckToken;
  try {
    appCheckToken = String(await tokenProvider() || "").trim();
  } catch {
    return false;
  }
  return Promise.resolve(fetchImpl(`${String(apiBase || "").replace(/\/$/, "")}/promotions/events`, {
    body: JSON.stringify({ campaignId, placement, type }),
    headers: {
      "Content-Type": "application/json",
      ...(appCheckToken ? { [FIREBASE_APP_CHECK_HEADER]: appCheckToken } : {}),
    },
    keepalive: true,
    method: "POST",
  })).then(response => Boolean(response?.ok)).catch(() => false);
}
