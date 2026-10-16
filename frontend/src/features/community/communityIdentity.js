export const COMMUNITY_IDENTITY_STORAGE_VERSION = 2;
export const COMMUNITY_IDENTITY_SNAPSHOT_VERSION = 1;
export const COMMUNITY_IDENTITY_STORAGE_KEY = "meteoFriul:communityIdentity:v2";
export const COMMUNITY_IDENTITY_LEGACY_ALIAS_INDEX_KEY = "meteoFriul:communityProfileAlias:v1";

const DEFAULT_SUBJECT_ID = "claf";
const MAX_ALIAS_LENGTH = 80;

// The first 26 entries preserve the exact order used by the v1 alias-index
// preference. Keep additions after that compatibility block.
const SUBJECT_DEFINITIONS = [
  ["crot", "Crot", "animal", "frog"],
  ["ruie", "Ruie", "animal", "bird"],
  ["ors", "Ors", "animal", "bear"],
  ["acuile", "Acuile", "animal", "eagle"],
  ["pufe", "Pufe", "animal", "owl"],
  ["bolp", "Bolp", "animal", "fox"],
  ["suris", "Surîs", "animal", "mouse"],
  ["sghirate", "Sghirate", "animal", "squirrel"],
  ["cocal", "Cocâl", "animal", "bird"],
  ["sarpint", "Sarpint", "animal", "snake"],
  ["stele", "Stele", "object", "star"],
  ["cjan", "Cjan", "animal", "dog"],
  ["gjat", "Gjat", "animal", "cat"],
  ["cisile", "Cisile", "animal", "bird"],
  ["cjaval", "Cjaval", "animal", "horse"],
  ["cjavre", "Cjavre", "animal", "goat"],
  ["flor", "Flôr", "nature", "flower"],
  ["plante", "Plante", "nature", "leaf"],
  ["rol", "Rôl", "nature", "tree"],
  ["cjariese", "Cjariese", "nature", "cherry"],
  ["claf", "Clâf", "object", "key"],
  ["cjampane", "Cjampane", "object", "bell"],
  ["clap", "Clap", "object", "stone"],
  ["cjistiel", "Cjistiel", "object", "castle"],
  ["cjapiel", "Cjapiel", "object", "hat"],
  ["cjicare", "Cjicare", "object", "cup"],
  ["cevron", "Cevron", "animal", "goat"],
  ["civo", "Civo", "animal", "deer"],
  ["lof", "Lôf", "animal", "wolf"],
  ["tasso", "Tasso", "animal", "badger"],
  ["gial", "Gial", "animal", "rooster"],
  ["scarpete", "Scarpete", "object", "shoe"],
  ["cjar", "Cjar", "object", "cart"],
  ["sfuei", "Sfuei", "object", "leaf"],
  ["sedon", "Sedon", "object", "spoon"],
  ["cjalcjut", "Cjalcjut", "object", "pan"],
  ["tapon", "Tapòn", "object", "cork"],
  ["cenc", "Cenc", "object", "bell"],
];

export const COMMUNITY_IDENTITY_SUBJECTS = Object.freeze(
  SUBJECT_DEFINITIONS.map(([id, label, kind, glyph]) => Object.freeze({
    glyph,
    id,
    kind,
    label,
  })),
);

export const COMMUNITY_IDENTITY_PALETTES = Object.freeze([
  Object.freeze({ accent: "#f2c94c", end: "#0284c7", id: "sky", start: "#38bdf8" }),
  Object.freeze({ accent: "#fde68a", end: "#1d4ed8", id: "cobalt", start: "#2563eb" }),
  Object.freeze({ accent: "#f2c94c", end: "#0f766e", id: "lagoon", start: "#2dd4bf" }),
  Object.freeze({ accent: "#ffffff", end: "#b45309", id: "gold", start: "#fbbf24" }),
  Object.freeze({ accent: "#f2c94c", end: "#334155", id: "slate", start: "#64748b" }),
  Object.freeze({ accent: "#38bdf8", end: "#0f172a", id: "night", start: "#1e3a8a" }),
]);

export const COMMUNITY_IDENTITY_PATTERN_IDS = Object.freeze([
  "diagonal",
  "halo",
  "split",
  "orbit",
]);

// Non-geographic Friulian epithets deliberately keep the anonymous profile
// independent from both the user's weather location and the report location.
// Keep existing entries stable and append new ones: the deterministic fallback
// for profiles created before `epithetId` was persisted depends on this order.
export const COMMUNITY_IDENTITY_EPITHETS = Object.freeze([
  Object.freeze({ id: "di-aur", label: "di Aur" }),
  Object.freeze({ id: "dal-bosc", label: "dal Bosc" }),
  Object.freeze({ id: "dal-fogolar", label: "dal Fogolâr" }),
  Object.freeze({ id: "dal-cil", label: "dal Cîl" }),
  Object.freeze({ id: "de-tiare", label: "de Tiare" }),
  Object.freeze({ id: "dal-troi", label: "dal Troi" }),
  Object.freeze({ id: "de-mont", label: "de Mont" }),
  Object.freeze({ id: "dal-riu", label: "dal Riu" }),
  Object.freeze({ id: "dal-vint", label: "dal Vint" }),
  Object.freeze({ id: "de-lune", label: "de Lune" }),
  Object.freeze({ id: "dal-plan", label: "dal Plan" }),
  Object.freeze({ id: "de-ploe", label: "de Ploe" }),
]);

export const COMMUNITY_IDENTITY_ANGLES = Object.freeze([45, 90, 135]);
export const COMMUNITY_IDENTITY_VARIANT_COUNT = 4;

const SUBJECTS_BY_ID = new Map(COMMUNITY_IDENTITY_SUBJECTS.map((subject) => [subject.id, subject]));
const PALETTES_BY_ID = new Map(COMMUNITY_IDENTITY_PALETTES.map((palette) => [palette.id, palette]));
const EPITHETS_BY_ID = new Map(COMMUNITY_IDENTITY_EPITHETS.map((epithet) => [epithet.id, epithet]));
const LEGACY_SUBJECT_IDS = Object.freeze(COMMUNITY_IDENTITY_SUBJECTS.slice(0, 26).map(({ id }) => id));

function resolveStorage(storage) {
  if (storage !== undefined) return storage;

  try {
    return globalThis.localStorage ?? null;
  } catch {
    return null;
  }
}

function compactText(value, maxLength) {
  return [...String(value ?? "")]
    .map((character) => {
      const codePoint = character.codePointAt(0);
      return codePoint <= 31 || codePoint === 127 ? " " : character;
    })
    .join("")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, maxLength)
    .trim();
}

function normalizeRevision(value) {
  const revision = Number(value);
  return Number.isSafeInteger(revision) && revision >= 0 ? revision : 0;
}

function normalizeRandomValue(random) {
  let value;

  try {
    value = Number(random?.());
  } catch {
    value = 0;
  }

  return Number.isFinite(value) ? Math.min(Math.max(value, 0), 0.999999999) : 0;
}

function hashText(value) {
  let hash = 0x811c9dc5;

  for (const character of String(value || "")) {
    hash ^= character.codePointAt(0);
    hash = Math.imul(hash, 0x01000193);
  }

  return hash >>> 0;
}

function readHashLane(hash, shift, length) {
  return (hash >>> shift) % length;
}

function normalizeSubjectId(subjectId) {
  const normalized = String(subjectId || "").trim().toLowerCase();
  return SUBJECTS_BY_ID.has(normalized) ? normalized : "";
}

function normalizeEpithetId(epithetId) {
  const normalized = String(epithetId || "").trim().toLowerCase();
  return EPITHETS_BY_ID.has(normalized) ? normalized : "";
}

function deriveCommunityEpithet(subjectId, revision = 0) {
  const normalizedSubjectId = normalizeSubjectId(subjectId) || DEFAULT_SUBJECT_ID;
  const normalizedRevision = normalizeRevision(revision);
  const hash = hashText(`community-epithet|${normalizedSubjectId}|${normalizedRevision}`);

  return COMMUNITY_IDENTITY_EPITHETS[hash % COMMUNITY_IDENTITY_EPITHETS.length];
}

function normalizeStoredIdentity(value) {
  let record = value;

  if (typeof record === "string") {
    try {
      record = JSON.parse(record);
    } catch {
      return null;
    }
  }

  if (!record || typeof record !== "object") return null;
  if (Number(record.version) !== COMMUNITY_IDENTITY_STORAGE_VERSION) return null;

  const subjectId = normalizeSubjectId(record.subjectId ?? record.subject_id);
  if (!subjectId) return null;

  return buildCommunityIdentity({
    epithetId: record.epithetId ?? record.epithet_id,
    revision: record.revision,
    subjectId,
  });
}

function readStoredValue(storage, key) {
  try {
    return storage?.getItem?.(key) ?? null;
  } catch {
    return null;
  }
}

function writeStoredIdentity(identity, storage) {
  if (!storage || !identity) return false;

  const record = {
    alias: identity.alias,
    epithetId: identity.epithetId,
    revision: identity.revision,
    subjectId: identity.subjectId,
    version: COMMUNITY_IDENTITY_STORAGE_VERSION,
  };

  try {
    storage.setItem?.(COMMUNITY_IDENTITY_STORAGE_KEY, JSON.stringify(record));
    return true;
  } catch {
    return false;
  }
}

function migrateLegacyIdentity(storage) {
  const storedIndex = readStoredValue(storage, COMMUNITY_IDENTITY_LEGACY_ALIAS_INDEX_KEY);
  if (storedIndex === null || String(storedIndex).trim() === "") return null;

  const legacyIndex = Number(storedIndex);
  if (!Number.isInteger(legacyIndex) || legacyIndex < 0 || legacyIndex >= LEGACY_SUBJECT_IDS.length) {
    return null;
  }

  return buildCommunityIdentity({
    revision: 0,
    subjectId: LEGACY_SUBJECT_IDS[legacyIndex],
  });
}

export function getCommunityIdentitySubject(subjectId) {
  return SUBJECTS_BY_ID.get(normalizeSubjectId(subjectId)) ?? null;
}

export function getCommunityIdentityPalette(paletteId) {
  return PALETTES_BY_ID.get(String(paletteId || "").trim()) ?? null;
}

export function formatCommunityIdentityAlias(subjectId, options = {}) {
  const subject = getCommunityIdentitySubject(subjectId)
    ?? getCommunityIdentitySubject(DEFAULT_SUBJECT_ID);
  const normalizedOptions = options && typeof options === "object" ? options : {};
  const epithet = EPITHETS_BY_ID.get(normalizeEpithetId(normalizedOptions.epithetId))
    ?? deriveCommunityEpithet(subject.id, normalizedOptions.revision);

  return `${subject.label} ${epithet.label}`;
}

export function deriveCommunityAvatar({ alias, revision = 0, subjectId } = {}) {
  const subject = getCommunityIdentitySubject(subjectId)
    ?? getCommunityIdentitySubject(DEFAULT_SUBJECT_ID);
  const normalizedRevision = normalizeRevision(revision);
  // The place is deliberately excluded: an identity keeps the same visual
  // when it reports from another municipality. `alias` remains accepted for
  // backwards-compatible callers but is not identity material.
  void alias;
  const hash = hashText(`${subject.id}|${normalizedRevision}`);
  const palette = COMMUNITY_IDENTITY_PALETTES[
    readHashLane(hash, 0, COMMUNITY_IDENTITY_PALETTES.length)
  ];

  return Object.freeze({
    angle: COMMUNITY_IDENTITY_ANGLES[
      readHashLane(hash, 12, COMMUNITY_IDENTITY_ANGLES.length)
    ],
    glyph: subject.glyph,
    kind: subject.kind,
    paletteId: palette.id,
    patternId: COMMUNITY_IDENTITY_PATTERN_IDS[
      readHashLane(hash, 7, COMMUNITY_IDENTITY_PATTERN_IDS.length)
    ],
    variant: readHashLane(hash, 17, COMMUNITY_IDENTITY_VARIANT_COUNT),
  });
}

export function buildCommunityIdentity({
  epithetId,
  revision = 0,
  subjectId = DEFAULT_SUBJECT_ID,
} = {}) {
  const normalizedSubjectId = normalizeSubjectId(subjectId) || DEFAULT_SUBJECT_ID;
  const normalizedRevision = normalizeRevision(revision);
  const subject = getCommunityIdentitySubject(normalizedSubjectId);
  const epithet = EPITHETS_BY_ID.get(normalizeEpithetId(epithetId))
    ?? deriveCommunityEpithet(normalizedSubjectId, normalizedRevision);
  const alias = formatCommunityIdentityAlias(normalizedSubjectId, { epithetId: epithet.id });

  return Object.freeze({
    alias,
    avatar: deriveCommunityAvatar({
      alias,
      revision: normalizedRevision,
      subjectId: normalizedSubjectId,
    }),
    epithetId: epithet.id,
    epithetLabel: epithet.label,
    kind: subject.kind,
    revision: normalizedRevision,
    subjectId: normalizedSubjectId,
    subjectLabel: subject.label,
    version: COMMUNITY_IDENTITY_STORAGE_VERSION,
  });
}

export function generateCommunityIdentity({
  random = Math.random,
  revision = 0,
} = {}) {
  const subjectIndex = Math.floor(
    normalizeRandomValue(random) * COMMUNITY_IDENTITY_SUBJECTS.length,
  );

  return buildCommunityIdentity({
    revision,
    subjectId: COMMUNITY_IDENTITY_SUBJECTS[subjectIndex].id,
  });
}

export function persistCommunityIdentity(identity, { storage } = {}) {
  const normalized = normalizeStoredIdentity(identity);
  if (!normalized) return false;

  return writeStoredIdentity(normalized, resolveStorage(storage));
}

export function readCommunityIdentity({
  random = Math.random,
  storage,
} = {}) {
  const resolvedStorage = resolveStorage(storage);
  const stored = normalizeStoredIdentity(
    readStoredValue(resolvedStorage, COMMUNITY_IDENTITY_STORAGE_KEY),
  );
  if (stored) {
    // Rewrite legacy v2 records once so obsolete geographic `placeName` and
    // alias values are removed without changing the storage/wire version.
    writeStoredIdentity(stored, resolvedStorage);
    return stored;
  }

  const identity = migrateLegacyIdentity(resolvedStorage)
    ?? generateCommunityIdentity({ random });
  writeStoredIdentity(identity, resolvedStorage);
  return identity;
}

export function regenerateCommunityIdentity(
  currentIdentity,
  { random = Math.random, storage } = {},
) {
  const resolvedStorage = resolveStorage(storage);
  const current = normalizeStoredIdentity(currentIdentity)
    ?? readCommunityIdentity({ random, storage: resolvedStorage });
  const currentIndex = COMMUNITY_IDENTITY_SUBJECTS.findIndex(({ id }) => id === current.subjectId);
  const offset = 1 + Math.floor(
    normalizeRandomValue(random) * (COMMUNITY_IDENTITY_SUBJECTS.length - 1),
  );
  const nextSubject = COMMUNITY_IDENTITY_SUBJECTS[
    (currentIndex + offset) % COMMUNITY_IDENTITY_SUBJECTS.length
  ];
  const nextIdentity = buildCommunityIdentity({
    revision: current.revision + 1,
    subjectId: nextSubject.id,
  });

  writeStoredIdentity(nextIdentity, resolvedStorage);
  return nextIdentity;
}

export function formatCommunityIdentityForPlace(identity, placeName) {
  // Compatibility shim for callers shipped before aliases were decoupled from
  // locations. The place is intentionally ignored.
  void placeName;
  return normalizeStoredIdentity(identity);
}

export function buildPublicCommunityIdentitySnapshot(identity, { placeName } = {}) {
  const storedIdentity = normalizeStoredIdentity(identity);
  if (!storedIdentity) return null;
  // `placeName` remains accepted for source compatibility, but a public
  // identity snapshot must never inherit the report location.
  void placeName;
  const normalized = storedIdentity;

  return Object.freeze({
    alias: normalized.alias,
    avatar: Object.freeze({
      angle: normalized.avatar.angle,
      paletteId: normalized.avatar.paletteId,
      patternId: normalized.avatar.patternId,
      variant: normalized.avatar.variant,
    }),
    subjectId: normalized.subjectId,
    version: COMMUNITY_IDENTITY_SNAPSHOT_VERSION,
  });
}

export function normalizePublicCommunityIdentitySnapshot(value) {
  let source = value;

  if (typeof source === "string") {
    try {
      source = JSON.parse(source);
    } catch {
      return null;
    }
  }

  if (source?.identity && typeof source.identity === "object") source = source.identity;
  if (!source || typeof source !== "object") return null;
  if (Number(source.version) !== COMMUNITY_IDENTITY_SNAPSHOT_VERSION) return null;

  const subjectId = normalizeSubjectId(source.subjectId ?? source.subject_id);
  const subject = getCommunityIdentitySubject(subjectId);
  const alias = compactText(source.alias, MAX_ALIAS_LENGTH);
  const avatar = source.avatar;
  const isCurrentAlias = COMMUNITY_IDENTITY_EPITHETS.some(
    ({ label }) => alias === `${subject?.label} ${label}`,
  );
  // Existing reports and older clients used "<subject> di <place>". Keep
  // accepting that shape so historical immutable snapshots remain readable.
  const isLegacyAlias = Boolean(subject)
    && alias.startsWith(`${subject.label} di `)
    && alias.length > `${subject.label} di `.length;
  if (!subject || (!isCurrentAlias && !isLegacyAlias) || !avatar || typeof avatar !== "object") {
    return null;
  }

  const paletteId = String(avatar.paletteId ?? avatar.palette_id ?? "").trim();
  const patternId = String(avatar.patternId ?? avatar.pattern_id ?? "").trim();
  const variant = Number(avatar.variant);
  const angle = Number(avatar.angle);
  if (
    !PALETTES_BY_ID.has(paletteId)
    || !COMMUNITY_IDENTITY_PATTERN_IDS.includes(patternId)
    || !Number.isInteger(variant)
    || variant < 0
    || variant >= COMMUNITY_IDENTITY_VARIANT_COUNT
    || !COMMUNITY_IDENTITY_ANGLES.includes(angle)
  ) {
    return null;
  }

  return Object.freeze({
    alias,
    avatar: Object.freeze({ angle, paletteId, patternId, variant }),
    subjectId,
    version: COMMUNITY_IDENTITY_SNAPSHOT_VERSION,
  });
}

export function serializePublicCommunityIdentitySnapshot(identityOrSnapshot) {
  const snapshot = normalizePublicCommunityIdentitySnapshot(identityOrSnapshot)
    ?? buildPublicCommunityIdentitySnapshot(identityOrSnapshot);

  return snapshot ? JSON.stringify(snapshot) : "";
}

export function parsePublicCommunityIdentitySnapshot(serialized) {
  return normalizePublicCommunityIdentitySnapshot(serialized);
}

export function toPublicCommunityIdentityWire(identityOrSnapshot, options) {
  const snapshot = normalizePublicCommunityIdentitySnapshot(identityOrSnapshot)
    ?? buildPublicCommunityIdentitySnapshot(identityOrSnapshot, options);
  if (!snapshot) return null;

  return {
    alias: snapshot.alias,
    avatar: {
      angle: snapshot.avatar.angle,
      palette_id: snapshot.avatar.paletteId,
      pattern_id: snapshot.avatar.patternId,
      variant: snapshot.avatar.variant,
    },
    subject_id: snapshot.subjectId,
    version: snapshot.version,
  };
}

export function createFallbackCommunityIdentitySnapshot(
  sourceKey,
  placeName,
) {
  void placeName;
  const normalizedKey = compactText(sourceKey, 256);
  if (!normalizedKey) return null;

  const hash = hashText(`legacy-community-source|${normalizedKey}`);
  const identity = buildCommunityIdentity({
    revision: readHashLane(hash, 11, 1024),
    subjectId: COMMUNITY_IDENTITY_SUBJECTS[
      hash % COMMUNITY_IDENTITY_SUBJECTS.length
    ].id,
  });

  return buildPublicCommunityIdentitySnapshot(identity);
}

export function getCommunityIdentityPreview({
  identities = [],
  limit = 3,
  placeName,
  sourceKeys = [],
} = {}) {
  const normalizedLimit = Number.isFinite(Number(limit))
    ? Math.max(0, Math.floor(Number(limit)))
    : 3;
  const sourceEntries = [];
  const seenSourceKeys = new Set();

  (Array.isArray(identities) ? identities : []).forEach((entry) => {
    const sourceKey = compactText(entry?.sourceKey ?? entry?.source_key, 256);
    if (sourceKey && seenSourceKeys.has(sourceKey)) return;
    if (sourceKey) seenSourceKeys.add(sourceKey);
    sourceEntries.push({
      identity: normalizePublicCommunityIdentitySnapshot(entry?.identity ?? entry),
      sourceKey,
    });
  });

  (Array.isArray(sourceKeys) ? sourceKeys : [sourceKeys]).forEach((value) => {
    const sourceKey = compactText(value, 256);
    if (!sourceKey || seenSourceKeys.has(sourceKey)) return;
    seenSourceKeys.add(sourceKey);
    sourceEntries.push({ identity: null, sourceKey });
  });

  const snapshots = sourceEntries
    .map(({ identity, sourceKey }) => (
      identity || createFallbackCommunityIdentitySnapshot(sourceKey, placeName)
    ))
    .filter(Boolean);

  return Object.freeze({
    hiddenCount: Math.max(0, snapshots.length - normalizedLimit),
    identities: Object.freeze(snapshots.slice(0, normalizedLimit)),
    totalCount: snapshots.length,
  });
}
