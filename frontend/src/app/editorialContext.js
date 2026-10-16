import { PRODUCT_SCOPE, isFvgLocation } from "../domain/scope/productScope";
import { DEFAULT_APP_LOCATION, normalizeAppLocation } from "./appLocation";

export const EDITORIAL_CONTEXT_STORAGE_KEY = "editorialContext:v1";

function getStorage(storage = globalThis.window?.localStorage) {
  return storage || null;
}

function toFvgFocusLocation(location) {
  const normalized = normalizeAppLocation(location);
  if (!normalized || !isFvgLocation(normalized)) return null;
  if (Number.isFinite(normalized.lat) && Number.isFinite(normalized.lon)) return normalized;

  // Older/default editorial contexts can carry only the municipality identity.
  // Resolve its public catalog point so the pilot events API receives a valid
  // FVG center even when the weather location itself is outside the region.
  const municipalityCenter = normalizeAppLocation({
    ...normalized,
    displayName: normalized.city,
    locality: { kind: "municipality", name: normalized.city },
    source: "manual_recent",
  });

  return municipalityCenter && isFvgLocation(municipalityCenter)
    ? municipalityCenter
    : normalized;
}

export function createEditorialContext(focusLocation = DEFAULT_APP_LOCATION) {
  return {
    followsWeatherLocation: false,
    focusLocation: toFvgFocusLocation(focusLocation) || DEFAULT_APP_LOCATION,
    regionCode: PRODUCT_SCOPE.fvgRegionCode,
    scopeId: PRODUCT_SCOPE.editorial,
    version: 1,
  };
}

export function readStoredEditorialContext({ storage } = {}) {
  const localStorage = getStorage(storage);
  if (!localStorage) return null;

  try {
    const value = JSON.parse(localStorage.getItem(EDITORIAL_CONTEXT_STORAGE_KEY));
    if (value?.version !== 1 || value?.scopeId !== PRODUCT_SCOPE.editorial) return null;

    const focusLocation = toFvgFocusLocation(value.focusLocation);
    return focusLocation ? createEditorialContext(focusLocation) : null;
  } catch {
    return null;
  }
}

export function readInitialEditorialContext({ storage, weatherLocation } = {}) {
  return readStoredEditorialContext({ storage })
    || createEditorialContext(toFvgFocusLocation(weatherLocation) || DEFAULT_APP_LOCATION);
}

export function writeStoredEditorialContext(context, { storage } = {}) {
  const localStorage = getStorage(storage);
  const normalized = createEditorialContext(context?.focusLocation);
  if (!localStorage) return normalized;

  try {
    localStorage.setItem(EDITORIAL_CONTEXT_STORAGE_KEY, JSON.stringify(normalized));
  } catch {
    return null;
  }

  return normalized;
}
