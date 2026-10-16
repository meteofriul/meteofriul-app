import { describe, expect, it } from "vitest";

import {
  HOME_PROMOTION_STATE_KEY,
  getPromotionDayKey,
  readHomePromotionState,
  recordHomePromotionImpression,
  selectHomePromotion,
} from "./homePromotions";

function memoryStorage(initial = {}) {
  const values = new Map(Object.entries(initial));
  return {
    getItem: key => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
  };
}

const campaigns = [
  { advertiserDailyCap: 3, advertiserId: "ale", campaignDailyCap: 3, enabled: true, id: "ale-a", placements: ["home"], placementAssignments: { home: { cardNumber: 1, mode: "rotation" } } },
  { advertiserDailyCap: 3, advertiserId: "other", campaignDailyCap: 3, enabled: true, id: "other-a", placements: ["home"], placementAssignments: { home: { cardNumber: 1, mode: "rotation" } } },
];

describe("Home promotion compatibility exports", () => {
  it("rotates the Home placement every two minutes", () => {
    const first = selectHomePromotion({ campaigns, now: 0, placement: "home" });
    const beforeBoundary = selectHomePromotion({ campaigns, now: 119_999, placement: "home" });
    const afterBoundary = selectHomePromotion({ campaigns, now: 120_000, placement: "home" });

    expect(first.id).toBe("ale-a");
    expect(beforeBoundary.id).toBe("ale-a");
    expect(afterBoundary.id).toBe("other-a");
  });

  it("keeps legacy storage and daily caps compatible", () => {
    const storage = memoryStorage();
    const now = "2026-09-24T08:00:00+02:00";
    const campaign = campaigns[0];

    expect(recordHomePromotionImpression({ campaign, dailyCap: 1, now, sessionId: "session-a", storage })).toBe(true);
    expect(recordHomePromotionImpression({ campaign, dailyCap: 1, now: "2026-09-24T08:02:00+02:00", sessionId: "session-a", storage })).toBe(false);
    expect(readHomePromotionState(storage).days[getPromotionDayKey(now)].total).toBe(1);
  });

  it("fails closed on unreadable local state", () => {
    const storage = memoryStorage({ [HOME_PROMOTION_STATE_KEY]: "not-json" });
    expect(readHomePromotionState(storage)).toEqual({ days: {}, lastShownAt: {}, sessions: {} });
  });
});
