import { getLocationCacheKey } from "../../domain/geo/locationCacheKey";
import { isCommunityGroupHiddenFromMap } from "./communityMapVisibility";

// This key is intentionally pilot-only, including when a QA caller supplies an
// in-memory storage adapter. It never migrates or reads the beta's state.
export const COMMUNITY_SEEN_STORAGE_KEY = "localCommunityPilot:v1:communitySeen:v1";
export const COMMUNITY_SEEN_TTL_MS = 7 * 24 * 60 * 60 * 1000;
export const COMMUNITY_SEEN_MAX_LOCATIONS = 64;
export const COMMUNITY_SEEN_MAX_ENTRIES = 4096;
export const COMMUNITY_UNREAD_RADIUS_KM = 30;

function text(value) {
  return typeof value === "string" ? value.trim().slice(0, 200) : "";
}

function point(value) {
  const lat = value?.lat;
  const lon = value?.lon;
  return typeof lat === "number" && Number.isFinite(lat) && Math.abs(lat) <= 90
    && typeof lon === "number" && Number.isFinite(lon) && Math.abs(lon) <= 180
    ? { lat, lon } : null;
}

// An opaque local bucket identifier, not encryption or an anonymous identity.
// Avoid serializing a place name or coordinates into the seen-state journal.
function opaqueKey(value) {
  let first = 2166136261;
  let second = 2246822507;
  for (const char of value) {
    const code = char.charCodeAt(0);
    first = Math.imul(first ^ code, 16777619);
    second = Math.imul(second ^ code, 3266489909);
  }
  return `scope:${(first >>> 0).toString(16)}:${(second >>> 0).toString(16)}`;
}

export function getCommunityUnreadLocationKey(location) {
  const coordinates = point(location);
  return coordinates ? opaqueKey(getLocationCacheKey(coordinates)) : "";
}

function distanceKm(first, second) {
  const radians = (value) => value * Math.PI / 180;
  const a = Math.sin(radians(second.lat - first.lat) / 2) ** 2
    + Math.cos(radians(first.lat)) * Math.cos(radians(second.lat))
      * Math.sin(radians(second.lon - first.lon) / 2) ** 2;
  return 6371 * 2 * Math.asin(Math.sqrt(Math.min(1, Math.max(0, a))));
}

function sourceKeys(entry) {
  return [...(Array.isArray(entry?.sourceKeys) ? entry.sourceKeys : []), entry?.sourceKey]
    .map(text).filter(Boolean);
}

function activeIds(entries, property, now) {
  return new Set((Array.isArray(entries) ? entries : [])
    .filter((entry) => Number(entry?.expiresAt) > now)
    .map((entry) => text(entry?.[property])).filter(Boolean));
}

// The input is the moderation-filtered display model, not a raw backend feed.
// Markers take precedence: a report retained only in Recenti is not map news.
export function createCommunityUnreadSnapshot(location, communityModel, {
  personalState,
  now = Date.now(),
} = {}) {
  const locationPoint = point(location);
  const locationKey = getCommunityUnreadLocationKey(location);
  if (!locationPoint || !locationKey) return null;
  const ready = communityModel?.enabled === true && communityModel?.status?.id === "fresh";
  if (!ready) return { locationKey, ready: false, entries: [] };

  const ownReports = Array.isArray(personalState?.reports) ? personalState.reports : [];
  const ownIds = new Set(ownReports.map((entry) => text(entry?.reportId)).filter(Boolean));
  const ownSources = new Set(ownReports.flatMap(sourceKeys));
  const removed = new Set([
    ...activeIds(personalState?.reportWithdrawals, "reportId", now),
    ...activeIds(personalState?.reportExpirations, "reportId", now),
  ]);
  const markers = Array.isArray(communityModel?.markers) ? communityModel.markers : null;
  const groups = markers
    ? markers.flatMap((marker) => (Array.isArray(marker?.phenomena) && marker.phenomena.length
      ? marker.phenomena.map((entry) => ({ ...entry, lat: entry.lat ?? marker.lat, lon: entry.lon ?? marker.lon }))
      : [marker]))
    : (Array.isArray(communityModel?.items) ? communityModel.items : []);
  const byId = new Map();

  for (const group of groups) {
    if (!group || group.hidden || isCommunityGroupHiddenFromMap(group, personalState, { now })) continue;
    const groupPoint = point(group);
    const distance = groupPoint ? distanceKm(locationPoint, groupPoint) : group.distanceKm;
    if (typeof distance !== "number" || !Number.isFinite(distance)
      || distance < 0 || distance > COMMUNITY_UNREAD_RADIUS_KM) continue;
    const contributions = Array.isArray(group.contributions) ? group.contributions : [];
    const known = new Set(contributions.map((entry) => text(entry?.id)).filter(Boolean));
    const reportIds = Array.isArray(group.reportIds) ? group.reportIds : [];
    const candidates = [
      ...contributions,
      ...reportIds.map(text).filter((id) => id && !known.has(id)).map((id) => ({
        id,
        expiresAt: group.expiresAt,
        // A shared group containing the owner is not wholly owned by them.
        ...(reportIds.length === 1 ? { sourceKeys: sourceKeys(group) } : {}),
      })),
    ];
    for (const candidate of candidates) {
      const id = text(candidate?.id);
      const expiresAt = Number(candidate?.expiresAt);
      if (!id || !Number.isFinite(expiresAt) || expiresAt <= now
        || candidate.hidden || candidate.isOwn || ownIds.has(id) || removed.has(id)
        || sourceKeys(candidate).some((key) => ownSources.has(key))) continue;
      const previous = byId.get(id);
      if (!previous || previous.expiresAt < expiresAt) byId.set(id, { id, expiresAt });
    }
  }
  return { locationKey, ready: true, entries: [...byId.values()].sort((a, b) => a.id.localeCompare(b.id)) };
}

function resolveStorage(storage) {
  if (storage !== undefined) return storage;
  try { return globalThis.localStorage; } catch { return null; }
}

function normalizeState(state, now) {
  const scopes = new Map();
  for (const scope of Array.isArray(state?.locations) ? state.locations : []) {
    const key = text(scope?.key);
    if (!/^scope:[a-f0-9]+:[a-f0-9]+$/.test(key)) continue;
    const byId = scopes.get(key) || new Map();
    for (const entry of Array.isArray(scope.entries) ? scope.entries : []) {
      const id = text(entry?.id);
      const expiresAt = Number(entry?.expiresAt);
      if (!id || !Number.isFinite(expiresAt) || expiresAt <= now) continue;
      const boundedExpiry = Math.min(expiresAt, now + COMMUNITY_SEEN_TTL_MS + 60 * 60 * 1000);
      const previous = byId.get(id);
      if (!previous || previous.expiresAt < boundedExpiry) byId.set(id, { id, expiresAt: boundedExpiry });
    }
    if (byId.size) scopes.set(key, byId);
  }
  let remaining = COMMUNITY_SEEN_MAX_ENTRIES;
  const locations = [...scopes].map(([key, entries]) => ({
    key, entries: [...entries.values()].sort((a, b) => b.expiresAt - a.expiresAt || a.id.localeCompare(b.id)),
  })).sort((a, b) => b.entries[0].expiresAt - a.entries[0].expiresAt || a.key.localeCompare(b.key))
    .slice(0, COMMUNITY_SEEN_MAX_LOCATIONS)
    .flatMap((scope) => {
      const entries = scope.entries.slice(0, remaining);
      remaining -= entries.length;
      return entries.length ? [{ key: scope.key, entries }] : [];
    });
  return { version: 1, locations };
}

export function readCommunitySeenState({ storage, now = Date.now() } = {}) {
  let value;
  try { value = JSON.parse(resolveStorage(storage)?.getItem?.(COMMUNITY_SEEN_STORAGE_KEY) || "null"); } catch { value = null; }
  return normalizeState(value, now);
}

export function writeCommunitySeenState(state, { storage, now = Date.now() } = {}) {
  try {
    resolveStorage(storage)?.setItem?.(COMMUNITY_SEEN_STORAGE_KEY, JSON.stringify(normalizeState(state, now)));
  } catch {
    // The current in-memory state remains usable when storage is unavailable.
  }
}

export function getCommunityUnreadCount(snapshot, state, { now = Date.now() } = {}) {
  if (!snapshot?.ready || !snapshot.locationKey) return 0;
  const scope = normalizeState(state, now).locations.find((entry) => entry.key === snapshot.locationKey);
  const seen = new Set((scope?.entries || []).map((entry) => entry.id));
  return new Set((snapshot.entries || [])
    .filter((entry) => Number(entry.expiresAt) > now && !seen.has(entry.id))
    .map((entry) => entry.id)).size;
}

export function markCommunitySnapshotSeen(state, snapshot, { now = Date.now() } = {}) {
  if (!snapshot?.ready || !snapshot.locationKey) return state;
  const normalized = normalizeState(state, now);
  const entries = (snapshot.entries || []).filter((entry) => Number(entry.expiresAt) > now)
    .map((entry) => ({ id: entry.id, expiresAt: Number(entry.expiresAt) + COMMUNITY_SEEN_TTL_MS }));
  const next = normalizeState({
    ...normalized,
    locations: [...normalized.locations, { key: snapshot.locationKey, entries }],
  }, now);
  return JSON.stringify(next) === JSON.stringify(state) ? state : next;
}
