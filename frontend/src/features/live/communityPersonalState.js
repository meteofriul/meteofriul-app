import { normalizePublicCommunityIdentitySnapshot } from "../community/communityIdentity";
import { communityStorageKey } from "../../services/localCommunityPilot";

export const COMMUNITY_PERSONAL_STATE_KEY = communityStorageKey("meteoFriul:communityPersonal:v1");
export const COMMUNITY_PERSONAL_DEFAULT_TTL_MS = 60 * 60 * 1000;
export const COMMUNITY_SERVER_EXPIRY_GUARD_MS = 65 * 60 * 1000;

function resolveStorage(storage) {
  if (storage !== undefined) return storage;

  try {
    return globalThis.localStorage;
  } catch {
    return null;
  }
}

function normalizeText(value) {
  return String(value || "").trim();
}

function normalizeExpiry(value, now) {
  const expiresAt = Number(value);
  return Number.isFinite(expiresAt) && expiresAt > now
    ? expiresAt
    : now + COMMUNITY_PERSONAL_DEFAULT_TTL_MS;
}

function getLocalDayKey(now) {
  const date = new Date(Number(now));
  const year = String(date.getFullYear()).padStart(4, "0");
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function getNextLocalMidnight(now) {
  const date = new Date(Number(now));
  return new Date(
    date.getFullYear(),
    date.getMonth(),
    date.getDate() + 1,
  ).getTime();
}

function normalizeDailyContributions(value, now) {
  const dayKey = getLocalDayKey(now);
  const storedCount = Number(value?.count);
  const legacyCount = Array.isArray(value?.keys)
    ? new Set(value.keys.map(normalizeText).filter(Boolean)).size
    : 0;
  const count = value?.dayKey === dayKey
    ? Math.max(
      0,
      Math.floor(Number.isFinite(storedCount) ? storedCount : legacyCount),
    )
    : 0;

  return {
    count,
    dayKey,
    expiresAt: getNextLocalMidnight(now),
  };
}

function normalizeReports(reports, now) {
  const byReport = new Map();

  (Array.isArray(reports) ? reports : []).forEach((report) => {
    const groupId = normalizeText(report?.groupId);
    const reportId = normalizeText(report?.reportId);
    const expiresAt = Number(report?.expiresAt);
    if (!groupId || !reportId || !Number.isFinite(expiresAt) || expiresAt <= now) return;

    byReport.set(reportId, {
      ...pilotReportMetadata(report),
      contributionDayKey: normalizeText(report?.contributionDayKey),
      expiresAt,
      groupId,
      identity: normalizePublicCommunityIdentitySnapshot(report?.identity),
      place: normalizeText(report?.place),
      reportId,
      revision: Math.max(1, Math.floor(Number(report?.revision) || 1)),
      sourceKey: normalizeText(report?.sourceKey),
      typeId: normalizeText(report?.typeId),
    });
  });

  return [...byReport.values()];
}

function pilotReportMetadata(report, previous = {}) {
  const correctionUntil = Number(report?.correctionUntil ?? report?.correction_until ?? previous.correctionUntil);
  const replacementAvailable = report?.replacementAvailable ?? report?.replacement_available ?? previous.replacementAvailable;
  const istatCode = report?.istatCode || report?.istat_code || previous.istatCode;
  return {
    ...(Number.isFinite(correctionUntil) && correctionUntil > 0 ? { correctionUntil } : {}),
    ...(typeof replacementAvailable === "boolean" ? { replacementAvailable } : {}),
    ...(istatCode ? { istatCode: String(istatCode) } : {}),
  };
}

function normalizeReportExpirations(expirations, now) {
  const byReport = new Map();

  (Array.isArray(expirations) ? expirations : []).forEach((expiration) => {
    const reportId = normalizeText(expiration?.reportId);
    const expiresAt = Number(expiration?.expiresAt);
    if (!reportId || !Number.isFinite(expiresAt) || expiresAt <= now) return;
    const current = byReport.get(reportId);
    if (!current || current.expiresAt < expiresAt) byReport.set(reportId, { reportId, expiresAt });
  });

  return [...byReport.values()];
}

function normalizeVotes(votes, now) {
  const byGroup = new Map();

  (Array.isArray(votes) ? votes : []).forEach((vote) => {
    const groupId = normalizeText(vote?.groupId);
    const value = normalizeText(vote?.vote).toLowerCase();
    const expiresAt = Number(vote?.expiresAt);
    if (
      !groupId
      || !["yes", "no"].includes(value)
      || !Number.isFinite(expiresAt)
      || expiresAt <= now
    ) return;

    byGroup.set(groupId, {
      contributionDayKey: normalizeText(vote?.contributionDayKey),
      expiresAt,
      groupId,
      vote: value,
    });
  });

  return [...byGroup.values()];
}

function normalizeMapWithdrawals(withdrawals, now) {
  const byGroup = new Map();

  (Array.isArray(withdrawals) ? withdrawals : []).forEach((withdrawal) => {
    const groupId = normalizeText(withdrawal?.groupId);
    const expiresAt = Number(withdrawal?.expiresAt);
    if (!groupId || !Number.isFinite(expiresAt) || expiresAt <= now) return;

    const current = byGroup.get(groupId);
    if (!current || current.expiresAt < expiresAt) {
      byGroup.set(groupId, { expiresAt, groupId });
    }
  });

  return [...byGroup.values()];
}

function normalizeState(value, now) {
  const reportExpirations = normalizeReportExpirations(value?.reportExpirations, now);
  const byReport = new Map();
  (Array.isArray(value?.reportWithdrawals) ? value.reportWithdrawals : []).forEach((withdrawal) => {
    const reportId = normalizeText(withdrawal?.reportId);
    const expiresAt = Number(withdrawal?.expiresAt);
    if (!reportId || !Number.isFinite(expiresAt) || expiresAt <= now) return;
    const previous = byReport.get(reportId);
    if (!previous || previous.expiresAt < expiresAt) byReport.set(reportId, { reportId, expiresAt });
  });
  const reportWithdrawals = [...byReport.values()];
  return {
    dailyContributions: normalizeDailyContributions(value?.dailyContributions, now),
    mapWithdrawals: normalizeMapWithdrawals(value?.mapWithdrawals, now),
    reports: normalizeReports(value?.reports, now).filter((report) => (
      !byReport.has(report.reportId)
      && !reportExpirations.some((expiration) => expiration.reportId === report.reportId)
    )),
    ...(reportExpirations.length ? { reportExpirations } : {}),
    ...(reportWithdrawals.length ? { reportWithdrawals } : {}),
    votes: normalizeVotes(value?.votes, now),
  };
}

function changeDailyContribution(state, delta, now) {
  const dailyContributions = normalizeDailyContributions(state?.dailyContributions, now);

  return {
    ...dailyContributions,
    count: Math.max(0, dailyContributions.count + Number(delta || 0)),
  };
}

function writeState(state, storage) {
  try {
    storage?.setItem?.(COMMUNITY_PERSONAL_STATE_KEY, JSON.stringify(state));
  } catch {
    // The UI can continue without remembering personal contribution labels.
  }
}

export function readCommunityPersonalState({ now = Date.now(), storage } = {}) {
  const resolvedStorage = resolveStorage(storage);
  let parsed = null;

  try {
    parsed = JSON.parse(resolvedStorage?.getItem?.(COMMUNITY_PERSONAL_STATE_KEY) || "null");
  } catch {
    // Invalid local state is treated as empty and rewritten below.
  }

  const state = normalizeState(parsed, Number(now));
  writeState(state, resolvedStorage);
  return state;
}

export function rememberCommunityReport(
  state,
  report,
  { now = Date.now(), storage } = {},
) {
  const resolvedStorage = resolveStorage(storage);
  const numericNow = Number(now);
  const groupId = normalizeText(report?.groupId || report?.group_id);
  const reportId = normalizeText(report?.id || report?.reportId);
  if (!groupId || !reportId) return normalizeState(state, numericNow);
  const currentState = normalizeState(state, numericNow);
  // A delayed successful-submit response must not restore an already retired
  // receipt or count the same contribution a second time.
  if (currentState.reportWithdrawals?.some((entry) => entry.reportId === reportId)) return currentState;
  const existingReport = currentState.reports.find(
    (entry) => entry.reportId === reportId,
  );
  const isNewContribution = !existingReport;

  const nextState = normalizeState({
    ...currentState,
    dailyContributions: isNewContribution
      ? changeDailyContribution(currentState, 1, numericNow)
      : currentState.dailyContributions,
    reports: [
      ...currentState.reports.filter((entry) => entry.reportId !== reportId),
      {
        contributionDayKey: existingReport
          ? existingReport.contributionDayKey
          : getLocalDayKey(numericNow),
        ...pilotReportMetadata(report, existingReport),
        expiresAt: normalizeExpiry(report?.expiresAt || report?.expires_at, numericNow),
        groupId,
        identity: normalizePublicCommunityIdentitySnapshot(report?.identity),
        place: normalizeText(report?.place),
        reportId,
        revision: Math.max(
          1,
          Math.floor(Number(report?.revision) || Number(existingReport?.revision) || 1),
        ),
        sourceKey: normalizeText(report?.sourceKey || report?.source_key),
        typeId: normalizeText(report?.typeId || report?.type_id),
      },
    ],
    reportExpirations: (currentState.reportExpirations || []).filter(
      (entry) => entry.reportId !== reportId,
    ),
  }, numericNow);
  writeState(nextState, resolvedStorage);
  return nextState;
}

// Refreshing an existing observation never represents another contribution.
// Recreate the ownership receipt after an in-flight expiry race, but preserve
// the daily count exactly as it was before the server acknowledgement.
export function refreshCommunityReportReceipt(
  state,
  report,
  { now = Date.now(), storage } = {},
) {
  const resolvedStorage = resolveStorage(storage);
  const numericNow = Number(now);
  const currentState = normalizeState(state, numericNow);
  const groupId = normalizeText(report?.groupId || report?.group_id);
  const reportId = normalizeText(report?.id || report?.reportId);
  if (!groupId || !reportId) return currentState;
  const existingReport = currentState.reports.find((entry) => entry.reportId === reportId);
  const nextState = normalizeState({
    ...currentState,
    reportExpirations: (currentState.reportExpirations || []).filter(
      (entry) => entry.reportId !== reportId,
    ),
    reports: [
      ...currentState.reports.filter((entry) => entry.reportId !== reportId),
      {
        contributionDayKey: existingReport?.contributionDayKey || "",
        ...pilotReportMetadata(report, existingReport),
        expiresAt: normalizeExpiry(report?.expiresAt || report?.expires_at, numericNow),
        groupId,
        identity: normalizePublicCommunityIdentitySnapshot(report?.identity),
        place: normalizeText(report?.place),
        reportId,
        revision: Math.max(
          1,
          Math.floor(Number(report?.revision) || Number(existingReport?.revision) || 1),
        ),
        sourceKey: normalizeText(report?.sourceKey || report?.source_key),
        typeId: normalizeText(report?.typeId || report?.type_id),
      },
    ],
  }, numericNow);
  writeState(nextState, resolvedStorage);
  return nextState;
}

// A server-confirmed expiry is not an undo or a withdrawal. It removes only
// the local ownership receipt and temporarily shields the map from an older
// cache response; daily activity, votes and anti-abuse state remain intact.
export function expireCommunityReport(
  state,
  reportId,
  { now = Date.now(), storage } = {},
) {
  const numericNow = Number(now);
  const normalizedReportId = normalizeText(reportId);
  const currentState = normalizeState(state, numericNow);
  if (!normalizedReportId) return currentState;
  const nextState = normalizeState({
    ...currentState,
    reportExpirations: [
      ...(currentState.reportExpirations || []).filter(
        (entry) => entry.reportId !== normalizedReportId,
      ),
      {
        expiresAt: numericNow + COMMUNITY_SERVER_EXPIRY_GUARD_MS,
        reportId: normalizedReportId,
      },
    ],
    reports: currentState.reports.filter((entry) => entry.reportId !== normalizedReportId),
  }, numericNow);
  writeState(nextState, resolveStorage(storage));
  return nextState;
}

// A deterministic owner/updateability rejection invalidates only the local
// ownership proof. The public observation may belong to someone else and must
// therefore remain visible; activity quotas and map visibility are untouched.
export function releaseCommunityReportReceipt(
  state,
  reportId,
  { now = Date.now(), storage } = {},
) {
  const numericNow = Number(now);
  const normalizedReportId = normalizeText(reportId);
  const currentState = normalizeState(state, numericNow);
  if (!normalizedReportId) return currentState;
  const nextState = normalizeState({
    ...currentState,
    reports: currentState.reports.filter((entry) => entry.reportId !== normalizedReportId),
  }, numericNow);
  writeState(nextState, resolveStorage(storage));
  return nextState;
}

export function forgetCommunityReport(
  state,
  reportId,
  { now = Date.now(), storage } = {},
) {
  const resolvedStorage = resolveStorage(storage);
  const normalizedReportId = normalizeText(reportId);
  const numericNow = Number(now);
  const currentState = normalizeState(state, numericNow);
  const removedReport = currentState.reports.find(
    (entry) => entry.reportId === normalizedReportId,
  );
  const removedContribution = removedReport?.contributionDayKey === getLocalDayKey(numericNow);
  const nextState = normalizeState({
    ...currentState,
    dailyContributions: removedContribution
      ? changeDailyContribution(currentState, -1, numericNow)
      : currentState.dailyContributions,
    reports: currentState.reports.filter((entry) => entry.reportId !== normalizedReportId),
  }, numericNow);
  writeState(nextState, resolvedStorage);
  return nextState;
}

// Call only after the server has acknowledged retirement (or confirmed that
// this receipt is no longer active). Unlike quick undo, retirement preserves
// today's contribution count and creates no group-wide visibility tombstone.
export function withdrawCommunityReport(
  state,
  reportId,
  { now = Date.now(), storage, expiresAt } = {},
) {
  const numericNow = Number(now);
  const normalizedReportId = normalizeText(reportId);
  const currentState = normalizeState(state, numericNow);
  if (!normalizedReportId) return currentState;
  const receipt = currentState.reports.find((entry) => entry.reportId === normalizedReportId);
  const knownWithdrawal = currentState.reportWithdrawals?.find((entry) => entry.reportId === normalizedReportId);
  const validExpiries = [receipt?.expiresAt, knownWithdrawal?.expiresAt, expiresAt]
    .map(Number)
    .filter((value) => Number.isFinite(value) && value > numericNow);
  const nextState = normalizeState({
    ...currentState,
    reports: currentState.reports.filter((entry) => entry.reportId !== normalizedReportId),
    reportWithdrawals: [
      ...(currentState.reportWithdrawals || []),
      ...(validExpiries.length ? [{
        reportId: normalizedReportId,
        expiresAt: Math.max(...validExpiries),
      }] : []),
    ],
  }, numericNow);
  writeState(nextState, resolveStorage(storage));
  return nextState;
}

export function rememberCommunityVote(
  state,
  { expiresAt, groupId, vote },
  { now = Date.now(), storage } = {},
) {
  const resolvedStorage = resolveStorage(storage);
  const numericNow = Number(now);
  const normalizedGroupId = normalizeText(groupId);
  const normalizedVote = normalizeText(vote).toLowerCase();
  if (!normalizedGroupId || !["yes", "no"].includes(normalizedVote)) {
    return normalizeState(state, numericNow);
  }
  const currentState = normalizeState(state, numericNow);
  const existingVote = currentState.votes.find(
    (entry) => entry.groupId === normalizedGroupId,
  );
  const isNewContribution = !existingVote;

  const nextState = normalizeState({
    ...currentState,
    dailyContributions: isNewContribution
      ? changeDailyContribution(currentState, 1, numericNow)
      : currentState.dailyContributions,
    votes: [
      ...currentState.votes.filter((entry) => entry.groupId !== normalizedGroupId),
      {
        contributionDayKey: existingVote
          ? existingVote.contributionDayKey
          : getLocalDayKey(numericNow),
        expiresAt: normalizeExpiry(expiresAt, numericNow),
        groupId: normalizedGroupId,
        vote: normalizedVote,
      },
    ],
  }, numericNow);
  writeState(nextState, resolvedStorage);
  return nextState;
}

export function rememberCommunityMapWithdrawal(
  state,
  { expiresAt, groupId },
  { now = Date.now(), storage } = {},
) {
  const resolvedStorage = resolveStorage(storage);
  const numericNow = Number(now);
  const normalizedGroupId = normalizeText(groupId);
  if (!normalizedGroupId) return normalizeState(state, numericNow);

  const currentState = normalizeState(state, numericNow);
  const nextState = normalizeState({
    ...currentState,
    mapWithdrawals: [
      ...currentState.mapWithdrawals,
      {
        expiresAt: normalizeExpiry(expiresAt, numericNow),
        groupId: normalizedGroupId,
      },
    ],
  }, numericNow);
  writeState(nextState, resolvedStorage);
  return nextState;
}

export function getOwnCommunityReport(state, groupId) {
  return getOwnCommunityReports(state, groupId).at(-1) || null;
}

export function getOwnCommunityReports(state, groupId) {
  const normalizedGroupId = normalizeText(groupId);
  return (state?.reports || []).filter((report) => report.groupId === normalizedGroupId);
}

export function getCommunityVote(state, groupId) {
  const normalizedGroupId = normalizeText(groupId);
  return (state?.votes || []).find((vote) => vote.groupId === normalizedGroupId)?.vote || "";
}

export function hasRememberedCommunityMapWithdrawal(state, groupId) {
  const normalizedGroupId = normalizeText(groupId);
  return (state?.mapWithdrawals || []).some(
    (withdrawal) => withdrawal.groupId === normalizedGroupId,
  );
}

export function getCommunityContributionCount(state) {
  const count = Number(state?.dailyContributions?.count);
  return Number.isFinite(count) ? Math.max(0, Math.floor(count)) : 0;
}
