import { communityStorageKey } from "../../services/localCommunityPilot";

export const COMMUNITY_MODERATION_STORAGE_KEY = communityStorageKey("meteoFriul:communityModeration:v1");
export const COMMUNITY_MODERATION_DEFAULT_TTL_MS = 60 * 60 * 1000;
export const COMMUNITY_MODERATION_SOURCE_TTL_MS = 24 * 60 * 60 * 1000;
export const COMMUNITY_MODERATION_MAX_TTL_MS = COMMUNITY_MODERATION_SOURCE_TTL_MS;

function getStorage(storage) {
  if (storage !== undefined) return storage;

  try {
    return globalThis.localStorage;
  } catch {
    return null;
  }
}

function normalizeKey(value) {
  return String(value || "").trim();
}

function normalizeExpiry(expiresAt, now) {
  const requested = Number(expiresAt);
  const defaultExpiry = now + COMMUNITY_MODERATION_DEFAULT_TTL_MS;

  if (!Number.isFinite(requested) || requested <= now) return defaultExpiry;
  return Math.min(requested, now + COMMUNITY_MODERATION_MAX_TTL_MS);
}

function normalizeEntries(entries, now) {
  const byKey = new Map();

  (Array.isArray(entries) ? entries : []).forEach((entry) => {
    const key = normalizeKey(entry?.key);
    const expiresAt = Number(entry?.expiresAt);
    if (!key || !Number.isFinite(expiresAt) || expiresAt <= now) return;

    const current = byKey.get(key);
    if (!current || current.expiresAt < expiresAt) {
      byKey.set(key, { expiresAt, key });
    }
  });

  return [...byKey.values()];
}

function normalizeState(value, now) {
  return {
    content: normalizeEntries(value?.content, now),
    sources: normalizeEntries(value?.sources, now),
  };
}

function writeState(state, storage) {
  try {
    storage?.setItem?.(COMMUNITY_MODERATION_STORAGE_KEY, JSON.stringify(state));
  } catch {
    // The current React state still hides the content when storage is unavailable.
  }
}

export function readCommunityModerationState({
  now = Date.now(),
  storage,
} = {}) {
  const resolvedStorage = getStorage(storage);
  let parsed;

  try {
    parsed = JSON.parse(resolvedStorage?.getItem?.(COMMUNITY_MODERATION_STORAGE_KEY) || "null");
  } catch {
    parsed = null;
  }

  const state = normalizeState(parsed, Number(now));
  writeState(state, resolvedStorage);
  return state;
}

function addHiddenKey(state, collection, key, { expiresAt, now }) {
  const normalizedKey = normalizeKey(key);
  if (!normalizedKey) return normalizeState(state, now);

  return normalizeState({
    ...state,
    [collection]: [
      ...(state?.[collection] || []),
      { expiresAt: normalizeExpiry(expiresAt, now), key: normalizedKey },
    ],
  }, now);
}

export function hideCommunityContentLocally(
  state,
  contentId,
  {
    expiresAt,
    now = Date.now(),
    storage,
  } = {},
) {
  const resolvedStorage = getStorage(storage);
  const nextState = addHiddenKey(state, "content", contentId, {
    expiresAt,
    now: Number(now),
  });
  writeState(nextState, resolvedStorage);
  return nextState;
}

export function hideCommunitySourceLocally(
  state,
  sourceKey,
  {
    expiresAt,
    now = Date.now(),
    storage,
  } = {},
) {
  const resolvedStorage = getStorage(storage);
  const nextState = addHiddenKey(state, "sources", sourceKey, {
    expiresAt,
    now: Number(now),
  });
  writeState(nextState, resolvedStorage);
  return nextState;
}

export function hideCommunitySourcesLocally(
  state,
  sourceKeys,
  {
    expiresAt,
    now = Date.now(),
    storage,
  } = {},
) {
  const resolvedStorage = getStorage(storage);
  const numericNow = Number(now);
  const nextState = (Array.isArray(sourceKeys) ? sourceKeys : [sourceKeys]).reduce(
    (current, sourceKey) => addHiddenKey(current, "sources", sourceKey, {
      expiresAt,
      now: numericNow,
    }),
    state,
  );
  writeState(nextState, resolvedStorage);
  return nextState;
}

function getEntrySourceKeys(entry) {
  const sourceKeys = Array.isArray(entry?.sourceKeys)
    ? entry.sourceKeys.map(normalizeKey).filter(Boolean)
    : [normalizeKey(entry?.sourceKey)].filter(Boolean);

  return [...new Set(sourceKeys)];
}

function countLabel(count, copy) {
  return count === 1
    ? copy.reportCountOne
    : copy.reportCountMany.replace("{count}", String(count));
}

function isContentHidden(entry, hiddenContent) {
  return hiddenContent.has(normalizeKey(entry?.id))
    || hiddenContent.has(normalizeKey(entry?.groupId));
}

function filterCommunityEntry(entry, hiddenContent, hiddenSources, copy) {
  if (isContentHidden(entry, hiddenContent)) return null;
  if (!hiddenSources.size) return entry;

  const sourceKeys = getEntrySourceKeys(entry);
  const contributions = Array.isArray(entry?.contributions)
    ? entry.contributions
    : [];

  if (!contributions.length) {
    return sourceKeys.length > 0
      && sourceKeys.every((sourceKey) => hiddenSources.has(sourceKey))
      ? null
      : entry;
  }

  const visibleContributions = contributions.filter((contribution) => {
    const contributionSourceKeys = getEntrySourceKeys(contribution);
    return !contributionSourceKeys.some((sourceKey) => hiddenSources.has(sourceKey));
  });
  if (visibleContributions.length === contributions.length) return entry;

  const declaredCount = Math.max(
    contributions.length,
    Math.max(0, Number(entry?.count) || 0),
  );
  const unknownContributionCount = Math.max(0, declaredCount - contributions.length);
  const nextCount = visibleContributions.length + unknownContributionCount;
  if (nextCount <= 0) return null;

  const nextSourceKeys = [...new Set([
    ...sourceKeys.filter((sourceKey) => !hiddenSources.has(sourceKey)),
    ...visibleContributions.flatMap(getEntrySourceKeys),
  ])];
  const hiddenReportIds = new Set(
    contributions
      .filter((contribution) => !visibleContributions.includes(contribution))
      .map((contribution) => normalizeKey(contribution?.id))
      .filter(Boolean),
  );
  const reportIds = [...new Set([
    ...(Array.isArray(entry?.reportIds) ? entry.reportIds : [])
      .map(normalizeKey)
      .filter((reportId) => reportId && !hiddenReportIds.has(reportId)),
    ...visibleContributions
      .map((contribution) => normalizeKey(contribution?.id))
      .filter(Boolean),
  ])];
  const latest = unknownContributionCount === 0
    ? visibleContributions.reduce((current, contribution) => (
        !current || Number(contribution?.createdAt) > Number(current?.createdAt)
          ? contribution
          : current
      ), null)
    : null;

  return {
    ...entry,
    contributions: visibleContributions,
    count: nextCount,
    countLabel: countLabel(nextCount, copy),
    ...(latest ? {
      createdAt: latest.createdAt,
      expiresAt: latest.expiresAt,
      timeLabel: latest.timeLabel,
    } : {}),
    reportIds,
    sourceKey: nextSourceKeys.length === 1 ? nextSourceKeys[0] : "",
    sourceKeys: nextSourceKeys,
  };
}

export function filterCommunityModerationModel(model, state) {
  const hiddenContent = new Set((state?.content || []).map((entry) => entry.key));
  const hiddenSources = new Set((state?.sources || []).map((entry) => entry.key));
  const copy = model?.copy || {};

  const items = (model?.items || []).flatMap((item) => {
    const visibleItem = filterCommunityEntry(
      item,
      hiddenContent,
      hiddenSources,
      copy,
    );
    return visibleItem ? [visibleItem] : [];
  });
  const markers = (model?.markers || []).flatMap((marker) => {
    const phenomena = (marker.phenomena || [marker]).flatMap((phenomenon) => {
      const visiblePhenomenon = filterCommunityEntry(
        phenomenon,
        hiddenContent,
        hiddenSources,
        copy,
      );
      return visiblePhenomenon ? [visiblePhenomenon] : [];
    });
    if (!phenomena.length) return [];

    const latest = phenomena.reduce((current, phenomenon) => (
      Number(phenomenon.createdAt) > Number(current.createdAt) ? phenomenon : current
    ));
    const count = phenomena.reduce(
      (total, phenomenon) => total + Math.max(1, Number(phenomenon.count) || 1),
      0,
    );
    const sourceKeys = [...new Set(phenomena.flatMap(getEntrySourceKeys))];

    return [{
      ...marker,
      confirmations: phenomena.reduce((totals, phenomenon) => ({
        no: totals.no + Math.max(0, Number(phenomenon.confirmations?.no) || 0),
        yes: totals.yes + Math.max(0, Number(phenomenon.confirmations?.yes) || 0),
      }), { no: 0, yes: 0 }),
      count,
      countLabel: countLabel(count, copy),
      createdAt: latest.createdAt,
      expiresAt: latest.expiresAt,
      phenomena,
      reportIds: [...new Set(phenomena.flatMap((phenomenon) => (
        Array.isArray(phenomenon?.reportIds) ? phenomenon.reportIds : []
      )))],
      sourceKey: sourceKeys.length === 1 ? sourceKeys[0] : "",
      sourceKeys,
      timeLabel: latest.timeLabel,
      typeId: phenomena.length > 1 ? "multiple" : latest.typeId,
      typeLabel: phenomena.length > 1 ? copy.reportMultiplePhenomena : latest.typeLabel,
    }];
  });

  return { ...model, items, markers };
}
