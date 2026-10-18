import { describe, expect, it, vi } from "vitest";

import {
  EMPTY_PROMOTION_CATALOG,
  PROMOTION_CATALOG_CACHE_KEY,
  fetchPromotionCatalog,
  normalizePromotionCatalog,
  readPromotionCatalogCache,
  recordPromotionEvent,
} from "./promotionCatalog";

function memoryStorage(initial = {}) {
  const values = new Map(Object.entries(initial));
  return {
    getItem: key => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
  };
}

const remoteCatalog = {
  campaigns: [{
    advertiserDailyCap: 1,
    advertiserId: "advertiser-1",
    campaignDailyCap: 1,
    enabled: true,
    id: "campaign-1",
    image: "https://storage.example.test/image.webp",
    location: "Pordenone",
    businessAddress: "Via Roma 12",
    category: "Marketing, comunicazione e media",
    activeDates: ["2026-09-27"],
    activeMonth: "",
    bookingMode: "rotation",
    deliveryMode: "rotation",
    endTime: "18:00",
    endsAt: "2026-09-30",
    placements: ["home", "events", "discover"],
    placementAssignments: {
      home: { cardNumber: 1, mode: "exclusive" },
      events: { cardNumber: 1, mode: "rotation" },
      discover: { cardNumber: 1, mode: "rotation" },
    },
    scheduleMode: "days",
    startTime: "08:00",
    startsAt: "2026-09-20",
    text: "Descrizione promozionale.",
    title: "Attività locale",
    url: "https://example.test/campaign",
  }],
  dailyCap: 2,
  enabled: true,
  maxAgeSeconds: 300,
  maxRotationCampaigns: 5,
  placementRotationIntervals: {
    home: 30,
    events: 60,
    discover: 300,
  },
  revision: 4,
  rotationIntervalSeconds: 120,
  schemaVersion: 2,
  timezone: "Europe/Rome",
};

describe("promotion catalog", () => {
  it("fails closed when disabled or malformed", () => {
    expect(normalizePromotionCatalog({ enabled: false })).toMatchObject({ enabled: false, campaigns: [] });
    expect(normalizePromotionCatalog({
      ...remoteCatalog,
      campaigns: [{ ...remoteCatalog.campaigns[0], image: "data:image/png;base64,AA==" }],
    })).toMatchObject({ enabled: false, campaigns: [] });
    expect(normalizePromotionCatalog({ ...remoteCatalog, schemaVersion: 3 }))
      .toMatchObject({ enabled: false, campaigns: [] });
  });

  it("preserves the per-placement rotation contract", () => {
    const catalog = normalizePromotionCatalog(remoteCatalog, { fetchedAt: 1_000 });

    expect(catalog).toMatchObject({
      enabled: true,
      maxRotationCampaigns: 5,
      placementRotationIntervals: {
        home: 30,
        events: 60,
        discover: 300,
      },
      placements: ["home", "events", "discover"],
      rotationIntervalSeconds: 30,
      schemaVersion: 2,
      timezone: "Europe/Rome",
    });
    expect(catalog.campaigns[0]).toMatchObject({
      businessAddress: "Via Roma 12",
      category: "Marketing, comunicazione e media",
      activeDates: ["2026-09-27"],
      activeMonth: "",
      bookingMode: "mixed",
      deliveryMode: "all_selected",
      endTime: "18:00",
      endsAt: "2026-09-30",
      placements: ["home", "events", "discover"],
      placementAssignments: {
        home: { cardNumber: 1, mode: "exclusive" },
        events: { cardNumber: 1, mode: "rotation" },
        discover: { cardNumber: 1, mode: "rotation" },
      },
      scheduleMode: "days",
      startTime: "08:00",
      startsAt: "2026-09-20",
    });
    expect(catalog.campaigns[0].visibleFields).toEqual([
      "businessName", "category", "address", "city", "description",
    ]);
  });

  it("keeps an explicitly selected text layout even without name or description", () => {
    const campaign = {
      ...remoteCatalog.campaigns[0],
      title: "",
      text: "",
      headline: "Tagli su misura",
      visibleFields: ["title", "title", "unsupported"],
    };
    const normalized = normalizePromotionCatalog({ ...remoteCatalog, campaigns: [campaign] });
    expect(normalized.enabled).toBe(true);
    expect(normalized.campaigns[0].visibleFields).toEqual(["title"]);

    const invalid = normalizePromotionCatalog({
      ...remoteCatalog,
      campaigns: [{ ...campaign, visibleFields: ["businessName"] }],
    });
    expect(invalid).toMatchObject({ enabled: false, campaigns: [] });
  });

  it("defaults every missing or invalid placement interval to 120 seconds", () => {
    const catalog = normalizePromotionCatalog({
      ...remoteCatalog,
      placementRotationIntervals: { home: 999 },
      rotationIntervalSeconds: 30,
    });

    expect(catalog.placementRotationIntervals).toEqual({
      home: 120,
      events: 120,
      discover: 120,
    });
    expect(catalog.rotationIntervalSeconds).toBe(120);
  });

  it("fails closed for a campaign without an explicit assignment for its page", () => {
    const catalog = normalizePromotionCatalog({
      ...remoteCatalog,
      campaigns: [{ ...remoteCatalog.campaigns[0], placementAssignments: {} }],
    });

    expect(catalog).toMatchObject({ enabled: false, campaigns: [] });
  });

  it("uses a verified cache only within its declared age", () => {
    const storage = memoryStorage();
    storage.setItem(PROMOTION_CATALOG_CACHE_KEY, JSON.stringify({
      ...normalizePromotionCatalog(remoteCatalog, { fetchedAt: 1_000 }),
    }));

    expect(readPromotionCatalogCache({ now: 300_000, storage }).revision).toBe(4);
    expect(readPromotionCatalogCache({ now: 302_000, storage })).toEqual(EMPTY_PROMOTION_CATALOG);
  });

  it("stores a valid response and hides the placement when refresh fails with stale cache", async () => {
    const storage = memoryStorage();
    const fetchImpl = vi.fn().mockResolvedValue({
      json: async () => remoteCatalog,
      ok: true,
    });
    const current = await fetchPromotionCatalog({ apiBase: "/api", fetchImpl, now: () => 1_000, storage });
    expect(current.enabled).toBe(true);
    expect(fetchImpl).toHaveBeenCalledWith("/api/promotions/catalog", expect.objectContaining({ cache: "no-store" }));

    const hidden = await fetchPromotionCatalog({
      apiBase: "/api",
      fetchImpl: vi.fn().mockRejectedValue(new Error("offline")),
      now: () => 302_000,
      storage,
    });
    expect(hidden).toEqual(EMPTY_PROMOTION_CATALOG);
  });

  it("sends only aggregate event fields", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({ ok: true });
    await recordPromotionEvent({
      apiBase: "/api",
      campaignId: "campaign-1",
      fetchImpl,
      tokenProvider: async () => "app-check-token",
      type: "open",
    });

    const [, request] = fetchImpl.mock.calls[0];
    expect(JSON.parse(request.body)).toEqual({
      campaignId: "campaign-1",
      placement: "home",
      type: "open",
    });
    expect(request.headers["X-Firebase-AppCheck"]).toBe("app-check-token");
    expect(request.body).not.toMatch(/gps|lat|lon|user|email/iu);
  });
});
