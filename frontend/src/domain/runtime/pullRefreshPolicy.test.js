import { describe, expect, it } from "vitest";

import {
  canStartPullRefresh,
  getPullRefreshEndState,
  getPullRefreshMoveState,
  getPullRefreshResultState,
  PULL_REFRESH_EXCLUDED_SELECTOR,
  PULL_REFRESH_STATE,
  shouldIgnorePullRefreshTarget,
} from "./pullRefreshPolicy";

function targetMatching(value) {
  return {
    closest: () => value,
  };
}

describe("pullRefreshPolicy", () => {
  it("starts only at the top of the main scroll area", () => {
    expect(canStartPullRefresh({ scrollTop: 0 })).toBe(true);
    expect(canStartPullRefresh({ scrollTop: 1 })).toBe(false);
    expect(canStartPullRefresh({ disabled: true, scrollTop: 0 })).toBe(false);
  });

  it("ignores interactive and protected targets", () => {
    expect(PULL_REFRESH_EXCLUDED_SELECTOR).toContain(".mf-live-webcam-carousel");
    expect(PULL_REFRESH_EXCLUDED_SELECTOR).toContain(".mf-weather-environment-sheet");
    expect(PULL_REFRESH_EXCLUDED_SELECTOR).toContain(".leaflet-container");
    expect(shouldIgnorePullRefreshTarget(targetMatching({ tagName: "BUTTON" }))).toBe(true);
    expect(canStartPullRefresh({
      scrollTop: 0,
      target: targetMatching({ className: "mf-bulletin-map-frame" }),
    })).toBe(false);
  });

  it("waits for a vertical direction lock before tracking", () => {
    expect(getPullRefreshMoveState({
      currentX: 0,
      currentY: 20,
      startX: 0,
      startY: 0,
    })).toMatchObject({
      distance: 0,
      state: PULL_REFRESH_STATE.idle,
    });
  });

  it("cancels horizontal gestures", () => {
    expect(getPullRefreshMoveState({
      currentX: 90,
      currentY: 36,
      startX: 0,
      startY: 0,
    })).toMatchObject({
      state: PULL_REFRESH_STATE.cancelled,
      shouldPreventDefault: false,
    });
  });

  it("tracks vertical pulls and becomes ready after the trigger threshold", () => {
    expect(getPullRefreshMoveState({
      currentX: 2,
      currentY: 120,
      startX: 0,
      startY: 0,
    })).toMatchObject({
      distance: 70,
      shouldTrigger: false,
      state: PULL_REFRESH_STATE.tracking,
    });

    expect(getPullRefreshMoveState({
      currentX: 2,
      currentY: 310,
      startX: 0,
      startY: 0,
    })).toMatchObject({
      distance: 180,
      shouldTrigger: true,
      state: PULL_REFRESH_STATE.ready,
    });
  });

  it("refreshes only when released after the trigger threshold", () => {
    expect(getPullRefreshEndState({ distance: 120 })).toMatchObject({
      shouldRefresh: false,
      state: PULL_REFRESH_STATE.idle,
    });

    expect(getPullRefreshEndState({ distance: 180 })).toMatchObject({
      distance: 76,
      shouldRefresh: true,
      state: PULL_REFRESH_STATE.refreshing,
    });
  });

  it("maps refresh results to persistent feedback states", () => {
    expect(getPullRefreshResultState({ result: { status: "settled" } })).toMatchObject({
      distance: 76,
      state: PULL_REFRESH_STATE.success,
    });

    expect(getPullRefreshResultState({ result: {
      components: { icon: "settled", officialAlerts: "unavailable" },
      status: "partial",
    } })).toMatchObject({
      components: { icon: "settled", officialAlerts: "unavailable" },
      distance: 76,
      state: PULL_REFRESH_STATE.partial,
    });

    expect(getPullRefreshResultState({ result: { status: "timeout" } })).toMatchObject({
      distance: 76,
      state: PULL_REFRESH_STATE.failed,
    });

    expect(getPullRefreshResultState({
      offline: true,
      result: { status: "partial" },
    })).toMatchObject({
      distance: 76,
      state: PULL_REFRESH_STATE.failed,
    });
  });
});
