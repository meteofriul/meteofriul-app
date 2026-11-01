import { EVENT_RADII } from "../features/events/eventsRadius";

export const EVENTS_RADIUS_STORAGE_KEY = "mfEventsMarketsRadiusKm";
export const DEFAULT_EVENTS_RADIUS_KM = 20;

export function normalizeEventsRadius(value) {
  if (typeof value !== "string" && typeof value !== "number") return null;
  const radius = Number(value);
  return EVENT_RADII.includes(radius) ? radius : null;
}

export function readEventsRadiusPreference(storage) {
  try {
    const target = storage ?? globalThis.window?.localStorage;
    return normalizeEventsRadius(target?.getItem(EVENTS_RADIUS_STORAGE_KEY)) ?? DEFAULT_EVENTS_RADIUS_KM;
  } catch {
    return DEFAULT_EVENTS_RADIUS_KM;
  }
}

export function writeEventsRadiusPreference(value, storage) {
  const radius = normalizeEventsRadius(value) ?? DEFAULT_EVENTS_RADIUS_KM;
  try {
    const target = storage ?? globalThis.window?.localStorage;
    target?.setItem(EVENTS_RADIUS_STORAGE_KEY, String(radius));
  } catch {
    // The preference remains usable for this session when storage is unavailable.
  }
  return radius;
}
