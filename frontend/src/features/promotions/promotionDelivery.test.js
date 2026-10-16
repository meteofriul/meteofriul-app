import { describe, expect, it } from "vitest";

import {
  PROMOTION_STATE_KEY,
  getPromotionDayKey,
  readPromotionState,
  recordPromotionImpression,
  selectPromotion,
} from "./promotionDelivery";

function memoryStorage(initial = {}) {
  const values = new Map(Object.entries(initial));
  return {
    getItem: key => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
  };
}

const campaigns = ["a", "b", "c", "d", "e", "f"].map(id => ({
  advertiserDailyCap: 10,
  advertiserId: `advertiser-${id}`,
  campaignDailyCap: 10,
  enabled: true,
  id,
  placements: ["home", "events", "discover"],
  placementAssignments: {
    home: { cardNumber: 1, mode: "rotation" },
    events: { cardNumber: 1, mode: "rotation" },
    discover: { cardNumber: 1, mode: "rotation" },
  },
}));

describe("promotion delivery", () => {
  it("rotates one visible card every 120 seconds and caps the pool at five", () => {
    expect(selectPromotion({ campaigns, now: 0 })?.id).toBe("a");
    expect(selectPromotion({ campaigns, now: 119_999 })?.id).toBe("a");
    expect(selectPromotion({ campaigns, now: 120_000 })?.id).toBe("b");
    expect(selectPromotion({ campaigns, now: 240_000 })?.id).toBe("c");
    expect(selectPromotion({ campaigns, now: 480_000 })?.id).toBe("e");
    expect(selectPromotion({ campaigns, now: 600_000 })?.id).toBe("a");
  });

  it("filters campaigns independently for Home, Events and Discover", () => {
    const placementCampaigns = [
      { ...campaigns[0], id: "home", placements: ["home"] },
      { ...campaigns[1], id: "events", placements: ["events"] },
      { ...campaigns[2], id: "discover", placements: ["discover"] },
    ];

    expect(selectPromotion({ campaigns: placementCampaigns, now: 0, placement: "home" })?.id).toBe("home");
    expect(selectPromotion({ campaigns: placementCampaigns, now: 0, placement: "events" })?.id).toBe("events");
    expect(selectPromotion({ campaigns: placementCampaigns, now: 0, placement: "discover" })?.id).toBe("discover");
  });

  it("uses independent intervals and indices for Home, Events and Discover", () => {
    const expectedTurns = [
      [0, "a", "a", "a"],
      [30_000, "b", "a", "a"],
      [60_000, "c", "b", "a"],
    ];

    expectedTurns.forEach(([now, home, events, discover]) => {
      expect(selectPromotion({ campaigns, now, placement: "home", rotationIntervalMs: 30_000 })?.id).toBe(home);
      expect(selectPromotion({ campaigns, now, placement: "events", rotationIntervalMs: 60_000 })?.id).toBe(events);
      expect(selectPromotion({ campaigns, now, placement: "discover", rotationIntervalMs: 300_000 })?.id).toBe(discover);
    });
  });

  it("keeps a single sponsor visible across every timer boundary", () => {
    const placementCampaigns = [
      { ...campaigns[0], id: "home", placements: ["home"] },
      { ...campaigns[1], id: "events", placements: ["events"] },
      { ...campaigns[2], id: "discover", placements: ["discover"] },
    ];

    expect(selectPromotion({ campaigns: placementCampaigns, now: 30_000, placement: "home", rotationIntervalMs: 30_000 })?.id).toBe("home");
    expect(selectPromotion({ campaigns: placementCampaigns, now: 600_000, placement: "events", rotationIntervalMs: 60_000 })?.id).toBe("events");
    expect(selectPromotion({ campaigns: placementCampaigns, now: 3_000_000, placement: "discover", rotationIntervalMs: 300_000 })?.id).toBe("discover");
  });

  it("gives an exclusive assignment precedence only on its placement", () => {
    const exclusive = {
      ...campaigns[5],
      id: "z-exclusive",
      placementAssignments: {
        ...campaigns[5].placementAssignments,
        home: { cardNumber: 1, mode: "exclusive" },
      },
    };

    expect(selectPromotion({ campaigns: [...campaigns, exclusive], now: 240_000, placement: "home" })?.id)
      .toBe("z-exclusive");
    expect(selectPromotion({ campaigns: [...campaigns, exclusive], now: 240_000, placement: "events" })?.id)
      .toBe("c");
  });

  it("fails closed when a campaign lacks the assignment for the requested page", () => {
    const legacy = { ...campaigns[0] };
    delete legacy.placementAssignments;

    expect(selectPromotion({ campaigns: [legacy], now: 0, placement: "home" })).toBeNull();
  });

  it("uses Europe/Rome for daily boundaries", () => {
    expect(getPromotionDayKey("2026-03-29T21:59:59Z")).toBe("2026-03-29");
    expect(getPromotionDayKey("2026-03-29T22:00:00Z")).toBe("2026-03-30");
  });

  it("honors optional Rome hours and date scheduling while a catalog is cached", () => {
    const scheduled = [{
      ...campaigns[0],
      activeDates: ["2026-09-27"],
      endTime: "18:00",
      scheduleMode: "days",
      startTime: "10:00",
    }];

    expect(selectPromotion({ campaigns: scheduled, now: "2026-09-27T07:59:00Z" })).toBeNull();
    expect(selectPromotion({ campaigns: scheduled, now: "2026-09-27T08:00:00Z" })?.id).toBe("a");
    expect(selectPromotion({ campaigns: scheduled, now: "2026-09-27T16:00:00Z" })).toBeNull();
    expect(selectPromotion({ campaigns: scheduled, now: "2026-09-28T08:00:00Z" })).toBeNull();
  });

  it("deduplicates one slot per placement without mixing the three sections", () => {
    const storage = memoryStorage();
    const campaign = campaigns[0];
    const common = { campaign, dailyCap: 10, now: 0, sessionId: "session-a", storage };

    expect(recordPromotionImpression({ ...common, placement: "home" })).toBe(true);
    expect(recordPromotionImpression({ ...common, placement: "home" })).toBe(false);
    expect(recordPromotionImpression({ ...common, placement: "events" })).toBe(true);
    expect(recordPromotionImpression({ ...common, now: 120_000, placement: "home" })).toBe(true);
    expect(readPromotionState(storage).days[getPromotionDayKey(0)].total).toBe(3);
    expect(JSON.stringify(readPromotionState(storage))).not.toMatch(/gps|lat|lon|email|account/iu);
  });

  it("fails closed on unreadable persisted state", () => {
    const storage = memoryStorage({ [PROMOTION_STATE_KEY]: "invalid" });
    expect(readPromotionState(storage)).toEqual({ days: {}, lastShownAt: {}, sessions: {} });
  });
});
