export const PULL_REFRESH_STATE = Object.freeze({
  idle: "idle",
  tracking: "tracking",
  ready: "ready",
  refreshing: "refreshing",
  success: "success",
  partial: "partial",
  failed: "failed",
  cancelled: "cancelled",
});

export const PULL_REFRESH_CONFIG = Object.freeze({
  directionLockPx: 28,
  triggerPx: 172,
  maxPx: 224,
  trackingRatio: 0.58,
  minFeedbackMs: 1400,
  resultFeedbackMs: 1100,
  releasedDistancePx: 76,
});

export const PULL_REFRESH_EXCLUDED_SELECTOR = [
  "a",
  "button",
  "input",
  "select",
  "textarea",
  "[role='button']",
  ".mf-app-header",
  ".mf-bottom-nav",
  ".mf-location-sheet",
  ".mf-weather-environment-sheet",
  ".mf-bulletin-map-frame",
  ".leaflet-container",
  ".mf-bulletin-tabs",
  ".mf-live-webcam-carousel",
  ".mf-tabs",
  ".mf-tab",
  ".mf-weather-variant-preview",
].join(",");

function toFiniteNumber(value, fallback = 0) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : fallback;
}

export function shouldIgnorePullRefreshTarget(target, selector = PULL_REFRESH_EXCLUDED_SELECTOR) {
  if (!target?.closest) return false;

  try {
    return Boolean(target.closest(selector));
  } catch {
    return true;
  }
}

export function canStartPullRefresh({
  disabled = false,
  scrollTop = 0,
  target = null,
} = {}) {
  if (disabled) return false;
  if (toFiniteNumber(scrollTop) > 0) return false;

  return !shouldIgnorePullRefreshTarget(target);
}

export function getPullRefreshMoveState({
  config = PULL_REFRESH_CONFIG,
  currentX,
  currentY,
  startX,
  startY,
} = {}) {
  const deltaX = toFiniteNumber(currentX) - toFiniteNumber(startX);
  const deltaY = toFiniteNumber(currentY) - toFiniteNumber(startY);
  const absX = Math.abs(deltaX);
  const absY = Math.abs(deltaY);

  if (deltaY <= 0) {
    return {
      distance: 0,
      shouldPreventDefault: false,
      shouldTrigger: false,
      state: PULL_REFRESH_STATE.cancelled,
    };
  }

  if (absY < config.directionLockPx) {
    return {
      distance: 0,
      shouldPreventDefault: false,
      shouldTrigger: false,
      state: PULL_REFRESH_STATE.idle,
    };
  }

  if (absX > absY) {
    return {
      distance: 0,
      shouldPreventDefault: false,
      shouldTrigger: false,
      state: PULL_REFRESH_STATE.cancelled,
    };
  }

  const distance = Math.min(config.maxPx, Math.round(deltaY * config.trackingRatio));
  const shouldTrigger = distance >= config.triggerPx;

  return {
    distance,
    shouldPreventDefault: true,
    shouldTrigger,
    state: shouldTrigger ? PULL_REFRESH_STATE.ready : PULL_REFRESH_STATE.tracking,
  };
}

export function getPullRefreshEndState({
  config = PULL_REFRESH_CONFIG,
  distance = 0,
} = {}) {
  const shouldRefresh = toFiniteNumber(distance) >= config.triggerPx;

  return {
    distance: shouldRefresh ? config.releasedDistancePx : 0,
    shouldRefresh,
    state: shouldRefresh ? PULL_REFRESH_STATE.refreshing : PULL_REFRESH_STATE.idle,
  };
}

export function getPullRefreshResultState({
  config = PULL_REFRESH_CONFIG,
  offline = false,
  result = null,
} = {}) {
  const componentDetails = result?.components && typeof result.components === "object"
    ? { components: { ...result.components } }
    : {};

  if (offline) {
    return {
      ...componentDetails,
      distance: config.releasedDistancePx,
      state: PULL_REFRESH_STATE.failed,
    };
  }

  if (result?.status === "partial") {
    return {
      ...componentDetails,
      distance: config.releasedDistancePx,
      state: PULL_REFRESH_STATE.partial,
    };
  }

  const isSuccess = result?.ok === true ||
    result?.status === "settled" ||
    result?.status === "success";

  return {
    ...componentDetails,
    distance: config.releasedDistancePx,
    state: isSuccess ? PULL_REFRESH_STATE.success : PULL_REFRESH_STATE.failed,
  };
}
