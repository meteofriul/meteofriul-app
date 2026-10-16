// Forme friulane verificate su fonti ufficiali ARLeF. Le aggiunte future vanno
// controllate lessicalmente prima dell'uso: https://arlef.it/it/al-e-on-line-ghiti/
// e https://superdizionari.arlef.it/.
export const COMMUNITY_SOURCE_ALIASES = Object.freeze([
  "Crot",
  "Ruie",
  "Ors",
  "Acuile",
  "Pufe",
  "Bolp",
  "Surîs",
  "Sghirate",
  "Cocâl",
  "Sarpint",
  "Stele",
  "Cjan",
  "Gjat",
  "Cisile",
  "Cjaval",
  "Cjavre",
  "Flôr",
  "Plante",
  "Rôl",
  "Cjariese",
  "Clâf",
  "Cjampane",
  "Clap",
  "Cjistiel",
  "Cjapiel",
  "Cjicare",
]);

function normalizeSourceKeys(sourceKeys) {
  const values = Array.isArray(sourceKeys) ? sourceKeys : [sourceKeys];

  return [...new Set(values
    .map((value) => String(value || "").trim())
    .filter(Boolean))];
}

function hashSourceKey(sourceKey) {
  let hash = 0x811c9dc5;

  for (let index = 0; index < sourceKey.length; index += 1) {
    hash ^= sourceKey.charCodeAt(index);
    hash = Math.imul(hash, 0x01000193);
  }

  return hash >>> 0;
}

export function getCommunitySourceAlias(sourceKey) {
  const normalizedKey = String(sourceKey || "").trim();
  if (!normalizedKey || COMMUNITY_SOURCE_ALIASES.length < 2) return "";

  const aliasCount = COMMUNITY_SOURCE_ALIASES.length;
  const pairIndex = hashSourceKey(normalizedKey) % (aliasCount * (aliasCount - 1));
  const firstIndex = Math.floor(pairIndex / (aliasCount - 1));
  const secondOffset = pairIndex % (aliasCount - 1);
  const secondIndex = secondOffset >= firstIndex ? secondOffset + 1 : secondOffset;

  return `${COMMUNITY_SOURCE_ALIASES[firstIndex]} · ${COMMUNITY_SOURCE_ALIASES[secondIndex]}`;
}

export function getCommunitySourceAliasPreview(sourceKeys, { limit = 3 } = {}) {
  const normalizedKeys = normalizeSourceKeys(sourceKeys);
  const numericLimit = Number(limit);
  const safeLimit = Number.isFinite(numericLimit)
    ? Math.max(0, Math.floor(numericLimit))
    : 3;
  const distinctAliases = [...new Set(
    normalizedKeys.map(getCommunitySourceAlias).filter(Boolean),
  )];
  const aliases = distinctAliases.slice(0, safeLimit);

  return {
    aliases,
    hiddenCount: Math.max(0, distinctAliases.length - aliases.length),
    totalCount: distinctAliases.length,
  };
}

export function formatCommunitySourceLabel(sourceKeys, copy) {
  const normalizedKeys = normalizeSourceKeys(sourceKeys);
  if (!normalizedKeys.length) return "";

  if (normalizedKeys.length > 1) {
    return String(copy?.reportAnonymousSources || "")
      .replace("{count}", String(normalizedKeys.length));
  }

  const alias = getCommunitySourceAlias(normalizedKeys[0]);
  if (!alias) return "";

  return String(copy?.reportAnonymousSource || "").replace("{alias}", alias);
}
