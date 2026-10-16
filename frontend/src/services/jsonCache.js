function getDefaultStorage() {
  return globalThis?.localStorage || null;
}

function getNowValue(now) {
  return typeof now === "function" ? now() : now;
}

export function readJsonCacheEntry(
  key,
  maxAgeMs,
  { removeExpired = false, storage = getDefaultStorage(), now = Date.now } = {},
) {
  if (!storage || typeof storage.getItem !== "function") return null;

  try {
    const raw = storage.getItem(key);
    if (raw === null) return null;
    const cached = JSON.parse(raw);
    const savedAt = Number(cached?.savedAt || 0);
    const age = getNowValue(now) - savedAt;

    if (cached?.data && age >= 0) {
      if (age <= maxAgeMs) {
        return {
          data: cached.data,
          age,
          savedAt,
        };
      }
      if (removeExpired && typeof storage.removeItem === "function") {
        storage.removeItem(key);
      }
      return null;
    }

    if (typeof storage.removeItem === "function") {
      storage.removeItem(key);
    }
  } catch {
    if (typeof storage.removeItem === "function") {
      storage.removeItem(key);
    }
  }

  return null;
}

export function readJsonCache(key, maxAgeMs, options = {}) {
  return readJsonCacheEntry(key, maxAgeMs, options)?.data || null;
}

export function writeJsonCache(key, data, { storage = getDefaultStorage(), now = Date.now } = {}) {
  if (!storage || typeof storage.setItem !== "function") return false;

  try {
    storage.setItem(key, JSON.stringify({ savedAt: getNowValue(now), data }));
    return true;
  } catch {
    return false;
  }
}

export function removeJsonCache(key, { storage = getDefaultStorage() } = {}) {
  if (!storage || typeof storage.removeItem !== "function") return false;

  try {
    storage.removeItem(key);
    return true;
  } catch {
    return false;
  }
}
