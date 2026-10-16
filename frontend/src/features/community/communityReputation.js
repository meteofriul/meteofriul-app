export const COMMUNITY_REPUTATION_RANK_IDS = Object.freeze([
  "novice",
  "lookout",
  "sentinel",
]);

const RANK_ID_ALIASES = Object.freeze({
  lookout: "lookout",
  novice: "novice",
  novizio: "novice",
  sentinella: "sentinel",
  sentinel: "sentinel",
  vedetta: "lookout",
});

function normalizeOptionalCount(value) {
  if (value === null || value === undefined || String(value).trim() === "") return null;
  const count = Number(value);
  return Number.isFinite(count) && count >= 0
    ? Math.floor(count)
    : null;
}

function normalizeRankId(value) {
  const normalized = String(value || "").trim().toLowerCase();
  return RANK_ID_ALIASES[normalized] || "";
}

function normalizeSource(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;

  return Object.freeze({
    id: String(value.id || "").trim(),
    storage: String(value.storage || "").trim(),
    type: String(value.type || "").trim(),
    verified: value.verified === true,
  });
}

export function normalizeCommunityReputation(value) {
  const payload = value?.reputation && typeof value.reputation === "object"
    ? value.reputation
    : value;
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) return null;

  const points = normalizeOptionalCount(
    payload.points ?? payload.validated_points ?? payload.validatedPoints,
  );
  if (points === null) return null;

  const rawRank = payload.rank;
  const rankId = normalizeRankId(
    typeof rawRank === "object" ? rawRank?.id : rawRank,
  );
  if (!COMMUNITY_REPUTATION_RANK_IDS.includes(rankId)) return null;

  return Object.freeze({
    maxDailyAwards: normalizeOptionalCount(
      payload.max_daily_awards ?? payload.maxDailyAwards,
    ),
    pendingReports: normalizeOptionalCount(
      payload.pending_reports ?? payload.pendingReports,
    ),
    points,
    rank: Object.freeze({
      id: rankId,
      minPoints: normalizeOptionalCount(
        rawRank?.min_points ?? rawRank?.minPoints,
      ),
      nextRankAt: normalizeOptionalCount(
        rawRank?.next_rank_at ?? rawRank?.nextRankAt,
      ),
    }),
    source: normalizeSource(payload.source),
    totalReports: normalizeOptionalCount(
      payload.total_reports ?? payload.totalReports,
    ),
    validatedReports: normalizeOptionalCount(
      payload.validated_reports ?? payload.validatedReports,
    ),
  });
}
