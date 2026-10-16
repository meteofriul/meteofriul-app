function replaceToken(template, token, value) {
  return String(template || "").replace(`{${token}}`, String(value));
}

function replaceTokens(template, replacements) {
  return Object.entries(replacements).reduce(
    (value, [token, replacement]) => replaceToken(value, token, replacement),
    String(template || ""),
  );
}

export function getCommunityActiveCount(items) {
  return (Array.isArray(items) ? items : []).reduce(
    (total, item) => total + Math.max(1, Number(item?.count) || 1),
    0,
  );
}

export function getCommunityActiveSummary(copy, count) {
  const normalizedCount = Math.max(0, Number(count) || 0);
  const template = normalizedCount === 1
    ? copy?.communityActiveSummaryOne || copy?.communityActiveSummary
    : copy?.communityActiveSummaryMany || copy?.communityActiveSummary;
  return replaceToken(template, "count", normalizedCount);
}

export function getCommunityRecentSummary(copy, count) {
  const normalizedCount = Math.max(0, Number(count) || 0);
  const template = normalizedCount === 1
    ? copy?.communityRecentSummaryOne || copy?.communityRecentSummary
    : copy?.communityRecentSummaryMany || copy?.communityRecentSummary;
  return replaceToken(template, "count", normalizedCount);
}

export function getCommunityContributionLabel(copy, count) {
  return replaceToken(copy?.communityContributionToday, "count", Math.max(0, Number(count) || 0));
}

export function getCommunityNearbyMatchSummary(copy, match) {
  const count = Math.max(1, Number(match?.count) || 1)
    + Math.max(0, Number(match?.confirmations?.yes) || 0);
  const template = count === 1 ? copy?.communityMatchOne : copy?.communityMatchMany;
  const phenomenon = String(match?.typeLabel || "").toLocaleLowerCase("it");

  return replaceTokens(template, { count, phenomenon });
}

export function getCommunityConfirmationSummary(copy, confirmations) {
  const yes = Math.max(0, Number(confirmations?.yes) || 0);
  if (yes === 1) return copy?.confirmationRecentOne || "";
  if (yes > 1) return replaceToken(copy?.confirmationRecentMany, "count", yes);
  return copy?.communityStateNew || "";
}

export function getCommunityDenialLabel(copy, confirmations) {
  const count = Math.max(0, Number(confirmations?.no) || 0);
  if (!count) return "";

  return replaceToken(
    count === 1 ? copy?.denialCountOne : copy?.denialCountMany,
    "count",
    count,
  );
}

export function getCommunityMapWithdrawalLabel(copy, report) {
  return Math.max(0, Number(report?.confirmations?.no) || 0) >= 3
    ? copy?.denialMapRemoved || ""
    : "";
}

export function getCommunityUpdatedLabel(
  copy,
  {
    ageMs,
    now = Date.now(),
    sourceUpdatedAt,
  } = {},
) {
  const parsedUpdatedAt = typeof sourceUpdatedAt === "number"
    ? sourceUpdatedAt
    : Date.parse(String(sourceUpdatedAt || ""));
  const numericAge = Number(ageMs);
  const resolvedAgeMs = Number.isFinite(parsedUpdatedAt)
    ? Math.max(0, Number(now) - parsedUpdatedAt)
    : Number.isFinite(numericAge)
      ? Math.max(0, numericAge)
      : Number.NaN;

  if (!Number.isFinite(resolvedAgeMs)) return copy?.communityUpdatedUnknown || "";

  const minutes = Math.floor(resolvedAgeMs / 60_000);
  if (minutes < 1) return copy?.communityUpdatedNow || "";

  return replaceToken(copy?.communityUpdatedMinutesAgo, "minutes", minutes);
}

export function getOwnReportExpiryLabel(
  copy,
  expiresAt,
  now = Date.now(),
  { maxMinutes } = {},
) {
  const remainingMs = Number(expiresAt) - Number(now);
  if (!Number.isFinite(remainingMs) || remainingMs <= 0) return "";

  const roundedMinutes = Math.max(1, Math.ceil(remainingMs / 60_000));
  const numericMaximum = Number(maxMinutes);
  const minutes = Number.isFinite(numericMaximum) && numericMaximum > 0
    ? Math.min(roundedMinutes, Math.max(1, Math.floor(numericMaximum)))
    : roundedMinutes;
  return replaceToken(copy?.ownReportExpiresIn, "minutes", minutes);
}

export function getCommunityAvailability(model) {
  const status = String(model?.status?.id || "unknown").toLowerCase();
  const hasContent = Boolean(model?.items?.length || model?.markers?.length);

  if (hasContent) {
    return {
      hasContent,
      kind: status === "stale" ? "stale" : "ready",
    };
  }
  if (status === "loading" || status === "unknown") {
    return { hasContent, kind: "loading" };
  }
  if (["error", "offline", "unavailable"].includes(status)) {
    return { hasContent, kind: "error" };
  }
  if (["stale", "degraded", "fallback"].includes(status)) {
    return { hasContent, kind: "stale" };
  }
  return { hasContent, kind: "empty" };
}
