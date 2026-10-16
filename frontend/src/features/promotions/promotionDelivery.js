import {
  PROMOTION_MAX_ROTATION_CAMPAIGNS,
  PROMOTION_ROTATION_INTERVAL_SECONDS,
} from "../../services/promotionCatalog";

export const PROMOTION_STATE_KEY = "meteofriul.home-promotions.v1";
export const PROMOTION_SESSION_KEY = "meteofriul.home-promotion-session.v1";
export const PROMOTION_DAILY_CAP = 2;
export const PROMOTION_ROTATION_INTERVAL_MS = PROMOTION_ROTATION_INTERVAL_SECONDS * 1000;

// Promotions are intentionally remote-controlled. An empty embedded catalog
// guarantees that a missing, stale or unreachable API never enables an ad.
export const PROMOTION_CAMPAIGNS = Object.freeze([]);

function toTimestamp(value) {
  if (value instanceof Date) return value.getTime();
  const numeric = Number(value);
  if (Number.isFinite(numeric) && String(value ?? "").trim()) return numeric;
  const parsed = Date.parse(String(value || ""));
  return Number.isFinite(parsed) ? parsed : Date.now();
}

export function getPromotionDayKey(now = Date.now()) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    day: "2-digit",
    month: "2-digit",
    timeZone: "Europe/Rome",
    year: "numeric",
  }).formatToParts(new Date(toTimestamp(now)));
  const values = Object.fromEntries(parts.map(part => [part.type, part.value]));
  return `${values.year}-${values.month}-${values.day}`;
}

export function getPromotionRotationSlot(
  now = Date.now(),
  rotationIntervalMs = PROMOTION_ROTATION_INTERVAL_MS,
) {
  const interval = Math.max(30_000, Number(rotationIntervalMs) || PROMOTION_ROTATION_INTERVAL_MS);
  return Math.floor(toTimestamp(now) / interval);
}

function getRomeClockMinutes(nowTimestamp) {
  const parts = new Intl.DateTimeFormat("en-GB", {
    hour: "2-digit",
    hourCycle: "h23",
    minute: "2-digit",
    timeZone: "Europe/Rome",
  }).formatToParts(new Date(nowTimestamp));
  const values = Object.fromEntries(parts.map(part => [part.type, part.value]));
  return (Number(values.hour) * 60) + Number(values.minute);
}

function timeToMinutes(value, fallback) {
  const selected = String(value || "").trim();
  if (selected === "24:00") return 24 * 60;
  const match = /^(\d{2}):(\d{2})$/u.exec(selected);
  return match ? (Number(match[1]) * 60) + Number(match[2]) : fallback;
}

function isCampaignActive(campaign, nowTimestamp) {
  if (!campaign?.enabled) return false;
  const day = getPromotionDayKey(nowTimestamp);
  const scheduleMode = campaign.scheduleMode || (campaign.activeDates?.length ? "days" : "period");
  const startsAt = String(campaign.startsAt || "").trim();
  const endsAt = String(campaign.endsAt || "").trim();
  if (scheduleMode === "days" && !campaign.activeDates?.includes(day)) {
    return false;
  }
  if (scheduleMode === "month" && campaign.activeMonth && !day.startsWith(`${campaign.activeMonth}-`)) return false;
  if (scheduleMode === "period") {
    if (/^\d{4}-\d{2}-\d{2}$/.test(startsAt) && day < startsAt) return false;
    if (/^\d{4}-\d{2}-\d{2}$/.test(endsAt) && day > endsAt) return false;
    if (startsAt && !/^\d{4}-\d{2}-\d{2}$/.test(startsAt) && nowTimestamp < Date.parse(startsAt)) return false;
    if (endsAt && !/^\d{4}-\d{2}-\d{2}$/.test(endsAt) && nowTimestamp > Date.parse(endsAt)) return false;
  }
  const minute = getRomeClockMinutes(nowTimestamp);
  if (minute < timeToMinutes(campaign.startTime, 0)) return false;
  if (minute >= timeToMinutes(campaign.endTime, 24 * 60)) return false;
  return true;
}

function getCampaignPlacementMode(campaign, placement) {
  if (!Array.isArray(campaign?.placements) || !campaign.placements.includes(placement)) return "";
  const assignment = campaign?.placementAssignments?.[placement];
  if (Number(assignment?.cardNumber) !== 1) return "";
  return ["exclusive", "rotation"].includes(assignment?.mode) ? assignment.mode : "";
}

function hasImpressionCapacity(campaign, dayState, dailyCap) {
  return Number(dayState.total || 0) < dailyCap
    && Number(dayState.campaigns?.[campaign.id] || 0) < Number(campaign.campaignDailyCap || 1)
    && Number(dayState.advertisers?.[campaign.advertiserId] || 0) < Number(campaign.advertiserDailyCap || 1);
}

export function readPromotionState(storage = globalThis.localStorage) {
  try {
    const parsed = JSON.parse(storage?.getItem?.(PROMOTION_STATE_KEY) || "null");
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      return { days: {}, lastShownAt: {}, sessions: {} };
    }
    return {
      days: parsed.days && typeof parsed.days === "object" ? parsed.days : {},
      lastShownAt: parsed.lastShownAt && typeof parsed.lastShownAt === "object" ? parsed.lastShownAt : {},
      sessions: parsed.sessions && typeof parsed.sessions === "object" ? parsed.sessions : {},
    };
  } catch {
    return { days: {}, lastShownAt: {}, sessions: {} };
  }
}

export function getPromotionSessionId(storage = globalThis.sessionStorage) {
  try {
    const existing = String(storage?.getItem?.(PROMOTION_SESSION_KEY) || "").trim();
    if (existing) return existing;
    const generated = globalThis.crypto?.randomUUID?.()
      || `session-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    storage?.setItem?.(PROMOTION_SESSION_KEY, generated);
    return generated;
  } catch {
    return `session-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  }
}

export function selectPromotion({
  campaigns = PROMOTION_CAMPAIGNS,
  maxRotationCampaigns = PROMOTION_MAX_ROTATION_CAMPAIGNS,
  now = Date.now(),
  placement = "home",
  rotationIntervalMs = PROMOTION_ROTATION_INTERVAL_MS,
} = {}) {
  const nowTimestamp = toTimestamp(now);
  const active = campaigns
    .filter(campaign => (
      isCampaignActive(campaign, nowTimestamp)
      && getCampaignPlacementMode(campaign, placement)
    ))
    .sort((left, right) => String(left.id).localeCompare(String(right.id), "it"));
  const exclusive = active.filter(
    campaign => getCampaignPlacementMode(campaign, placement) === "exclusive",
  );
  if (exclusive.length) return exclusive[0];
  const rotation = active
    .filter(campaign => getCampaignPlacementMode(campaign, placement) === "rotation")
    .slice(0, Math.max(
      1,
      Math.min(PROMOTION_MAX_ROTATION_CAMPAIGNS, Number(maxRotationCampaigns) || 1),
    ));
  if (!rotation.length) return null;
  return rotation[getPromotionRotationSlot(nowTimestamp, rotationIntervalMs) % rotation.length];
}

export function recordPromotionImpression({
  campaign,
  dailyCap = PROMOTION_DAILY_CAP,
  now = Date.now(),
  placement = "home",
  rotationIntervalMs = PROMOTION_ROTATION_INTERVAL_MS,
  sessionId,
  storage = globalThis.localStorage,
} = {}) {
  if (!campaign?.id || !campaign?.advertiserId || !sessionId) return false;
  const timestamp = toTimestamp(now);
  const day = getPromotionDayKey(timestamp);
  const slot = getPromotionRotationSlot(timestamp, rotationIntervalMs);
  const state = readPromotionState(storage);
  const sessionState = state.sessions?.[sessionId] || {};
  const previousPlacement = sessionState.placements?.[placement];
  if (previousPlacement?.campaignId === campaign.id && previousPlacement?.slot === slot) return false;
  // Preserve compatibility with the original Home-only session record.
  if (placement === "home" && sessionState.campaignId === campaign.id && sessionState.day === day) return false;

  const dayState = state.days?.[day] || { advertisers: {}, campaigns: {}, total: 0 };
  if (!hasImpressionCapacity(campaign, dayState, dailyCap)) return false;
  const nextDays = Object.fromEntries(
    Object.entries(state.days || {}).filter(([key]) => key >= getPromotionDayKey(timestamp - (14 * 86400000))),
  );
  nextDays[day] = {
    advertisers: {
      ...(dayState.advertisers || {}),
      [campaign.advertiserId]: Number(dayState.advertisers?.[campaign.advertiserId] || 0) + 1,
    },
    campaigns: {
      ...(dayState.campaigns || {}),
      [campaign.id]: Number(dayState.campaigns?.[campaign.id] || 0) + 1,
    },
    total: Number(dayState.total || 0) + 1,
  };

  try {
    storage?.setItem?.(PROMOTION_STATE_KEY, JSON.stringify({
      days: nextDays,
      lastShownAt: { ...(state.lastShownAt || {}), [campaign.id]: timestamp },
      sessions: {
        ...(state.sessions || {}),
        [sessionId]: {
          ...sessionState,
          placements: {
            ...(sessionState.placements || {}),
            [placement]: { campaignId: campaign.id, day, slot },
          },
        },
      },
    }));
    return true;
  } catch {
    return false;
  }
}
