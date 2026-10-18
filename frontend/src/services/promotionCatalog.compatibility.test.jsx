import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import fixture from "../../../backend/tests/fixtures/promotions_card_contract.json";
import { PromotionPlacementCard } from "../features/promotions/PromotionPlacementCard";
import { normalizePromotionCatalog as normalize014 } from "./__fixtures__/promotionCatalog014";
import { fetchPromotionCatalog, normalizePromotionCatalog, readPromotionCatalogCache } from "./promotionCatalog";

const fields = { businessName: "title", category: "category", address: "businessAddress", city: "location", title: "headline", description: "text" };
const privateValues = ["SYNTHETIC-PRIVATE-NOTE", "SYNTHETIC-PRIVATE-INVOICE", "private-contact@example.test"];
const full = fixture.cases.find(item => item.name === "all-selected").catalog.campaigns[0];

describe("sponsor API and Android 0.1.14 compatibility", () => {
  it.each(fixture.cases)("documents actual legacy acceptance for $name", ({ catalog, legacy014Visible }) => {
    const legacy = normalize014(catalog);
    expect(legacy.enabled).toBe(legacy014Visible);
    expect(legacy.campaigns).toHaveLength(legacy014Visible ? 1 : 0);
    const current = normalizePromotionCatalog(catalog);
    expect(current.enabled).toBe(true);
    expect(current.campaigns).toHaveLength(1);
    if (legacy014Visible) {
      expect(legacy.campaigns[0].id).toBe(current.campaigns[0].id);
      expect(legacy.campaigns[0].advertiserId).toBe(current.campaigns[0].advertiserId);
      expect(legacy.campaigns[0].placementAssignments).toEqual(current.campaigns[0].placementAssignments);
    }
  });

  it.each(fixture.cases)("renders only selected text in all placements for $name", ({ catalog }) => {
    const current = normalizePromotionCatalog(catalog);
    for (const placement of ["home", "events", "discover"]) {
      const html = renderToStaticMarkup(<PromotionPlacementCard campaigns={current.campaigns} now={Date.parse(fixture.now)} placement={placement} />);
      expect(html).toContain('data-promotion-id="synthetic-sponsor"');
      expect(html).toContain("Pubblicità");
      expect(html).toContain('rel="sponsored noopener noreferrer"');
      for (const [selected, field] of Object.entries(fields)) {
        if (current.campaigns[0].visibleFields.includes(selected)) expect(html).toContain(full[field]);
        else expect(html).not.toContain(full[field]);
      }
      for (const value of privateValues) expect(html).not.toContain(value);
    }
  });

  it.each(fixture.cases)("keeps selection on refresh, offline fallback and cache expiry for $name", async ({ catalog }) => {
    const values = new Map();
    const storage = { getItem: key => values.get(key), setItem: (key, value) => values.set(key, value) };
    const fetchedAt = Date.parse(fixture.now);
    const current = await fetchPromotionCatalog({ apiBase: "/api", now: () => fetchedAt, storage,
      fetchImpl: vi.fn().mockResolvedValue({ ok: true, json: async () => catalog }) });
    const cached = await fetchPromotionCatalog({ apiBase: "/api", now: () => fetchedAt + 1000, storage,
      fetchImpl: vi.fn().mockRejectedValue(new Error("offline")) });
    expect(cached).toEqual(current);
    expect(readPromotionCatalogCache({ now: fetchedAt + 301000, storage }).enabled).toBe(false);
  });

  it("continues to read a catalog predating visibleFields", () => {
    const catalog = structuredClone(fixture.cases[0].catalog);
    delete catalog.campaigns[0].visibleFields;
    expect(normalizePromotionCatalog(catalog).campaigns[0].visibleFields).toEqual(["businessName", "city", "title", "description"]);
    expect(normalize014(catalog).enabled).toBe(true);
  });
});
