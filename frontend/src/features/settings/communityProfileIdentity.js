import { COMMUNITY_SOURCE_ALIASES } from "../live/communitySourceAlias";
import { COMMUNITY_IDENTITY_EPITHETS } from "../community/communityIdentity";

export const COMMUNITY_PROFILE_ALIAS_INDEX_KEY = "meteoFriul:communityProfileAlias:v1";

function resolveStorage(storage) {
  if (storage !== undefined) return storage;

  try {
    return globalThis.localStorage;
  } catch {
    return null;
  }
}

function normalizeIndex(value) {
  if (value === null || value === undefined || String(value).trim() === "") return null;
  const index = Number(value);
  return Number.isInteger(index) && index >= 0 && index < COMMUNITY_SOURCE_ALIASES.length
    ? index
    : null;
}

function getRandomIndex(random) {
  const numeric = Number(random?.());
  const bounded = Number.isFinite(numeric) ? Math.min(Math.max(numeric, 0), 0.999999999) : 0;
  return Math.floor(bounded * COMMUNITY_SOURCE_ALIASES.length);
}

function writeIndex(index, storage) {
  try {
    storage?.setItem?.(COMMUNITY_PROFILE_ALIAS_INDEX_KEY, String(index));
  } catch {
    // The in-memory React state still keeps the cosmetic alias for this session.
  }
}

export function readCommunityProfileAliasIndex({ random = Math.random, storage } = {}) {
  const resolvedStorage = resolveStorage(storage);

  try {
    const stored = normalizeIndex(
      resolvedStorage?.getItem?.(COMMUNITY_PROFILE_ALIAS_INDEX_KEY),
    );
    if (stored !== null) return stored;
  } catch {
    // Generate a session-only cosmetic alias when storage is unavailable.
  }

  const generated = getRandomIndex(random);
  writeIndex(generated, resolvedStorage);
  return generated;
}

export function regenerateCommunityProfileAliasIndex(
  currentIndex,
  { random = Math.random, storage } = {},
) {
  const resolvedStorage = resolveStorage(storage);
  const current = normalizeIndex(currentIndex)
    ?? readCommunityProfileAliasIndex({ random, storage: resolvedStorage });
  const offset = 1 + Math.floor(
    Math.min(Math.max(Number(random?.()) || 0, 0), 0.999999999)
      * (COMMUNITY_SOURCE_ALIASES.length - 1),
  );
  const next = (current + offset) % COMMUNITY_SOURCE_ALIASES.length;

  writeIndex(next, resolvedStorage);
  return next;
}

export function formatCommunityProfileAlias(index, placeName) {
  const normalizedIndex = normalizeIndex(index) ?? 0;
  // Compatibility argument retained for old callers. Anonymous aliases no
  // longer encode a weather or report location.
  void placeName;
  const epithet = COMMUNITY_IDENTITY_EPITHETS[
    normalizedIndex % COMMUNITY_IDENTITY_EPITHETS.length
  ];

  return `${COMMUNITY_SOURCE_ALIASES[normalizedIndex]} ${epithet.label}`;
}
