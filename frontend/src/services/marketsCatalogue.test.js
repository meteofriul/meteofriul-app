import { describe, expect, it, vi } from "vitest";
import { createMarketsCatalogueStore, MARKETS_CATALOGUE_CACHE_PREFIX, marketsCatalogueUrl } from "./marketsCatalogue";
import { getMarket, mergeMarketEvents } from "../features/markets/marketsCatalog";

const time = Date.parse("2026-10-30T12:00:00Z");
const location = { city: "Pordenone", regionCode: "IT-36" };
const market = getMarket("M035");
const feed = { market_id: "M035", title: market.name, event_city: "Pordenone", start_date: "2026-11-01", category: "mercato" };
function memoryStorage() {
  const values = new Map();
  return { getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value), removeItem: key => values.delete(key) };
}
function snapshot(revision = 1, fields = {}) {
  return { schemaVersion: 2, revision, snapshotId: `markets-${revision}-hash`, publishedAt: "2026-10-30T12:00:00Z",
    expiresAt: "2026-10-31T12:00:00Z", validThrough: "2026-12-31", markets: [market],
    dates: [{ id: "edition-35-a", marketId: market.id, date: "2026-11-01", status: "published", source: market.url }],
    identities: [{ marketId: market.id, name: market.name, comune: market.comune, sourceUrls: [market.url], status: "published" }],
    tombstones: [], ...fields };
}
const response = data => ({ ok: true, json: async () => data });

describe("persistent managed market catalogue", () => {
  it("loads one snapshot for concurrent readers and retries after a synchronous network error", async () => {
    const fetchImpl = vi.fn().mockImplementationOnce(() => { throw new Error("offline"); }).mockResolvedValue(response(snapshot()));
    const store = createMarketsCatalogueStore({ storage: memoryStorage(), fetchImpl, now: () => time });
    await Promise.all([store.refresh(), store.refresh()]);
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    expect(store.getSnapshot().status).toBe("bootstrap");
    await store.refresh();
    expect(store.getSnapshot().catalogue.revision).toBe(1);
    expect(fetchImpl.mock.lastCall[0]).toBe(marketsCatalogueUrl());
  });

  it("never restores a withdrawn market from a stale feed, offline restart, or expiry", async () => {
    const storage = memoryStorage();
    const withdrawn = snapshot(2, { markets: [], dates: [],
      identities: [{ marketId: market.id, name: market.name, comune: market.comune, status: "archived" }],
      tombstones: [{ marketId: market.id, status: "archived" }] });
    const store = createMarketsCatalogueStore({ storage, fetchImpl: async () => response(withdrawn), now: () => time });
    await store.refresh();
    const restarted = createMarketsCatalogueStore({ storage, fetchImpl: () => Promise.reject(new Error("offline")), now: () => time + 86400001 });
    await restarted.refresh();
    const state = restarted.getSnapshot();
    expect(state.status).toBe("expired");
    expect(state.catalogue.tombstones).toEqual(withdrawn.tombstones);
    expect(mergeMarketEvents([feed], { location, now: new Date(time), catalogue: state.catalogue })).toEqual([]);
  });

  it("rejects a downgrade after losing the payload but retaining the revision ledger", async () => {
    const storage = memoryStorage(), key = MARKETS_CATALOGUE_CACHE_PREFIX + marketsCatalogueUrl();
    const first = createMarketsCatalogueStore({ storage, fetchImpl: async () => response(snapshot(9)), now: () => time });
    await first.refresh();
    storage.setItem(key, "invalid");
    const restarted = createMarketsCatalogueStore({ storage, fetchImpl: async () => response(snapshot(8)), now: () => time });
    expect(restarted.getSnapshot().catalogue.unavailable).toBe(true);
    await restarted.refresh();
    expect(restarted.getSnapshot().status).toBe("unavailable");
    expect(restarted.getSnapshot().error).toMatch(/superata/);
    expect(mergeMarketEvents([feed], { location, catalogue: restarted.getSnapshot().catalogue })).toEqual([]);
  });

  it("accepts restoration only in a newer public revision", async () => {
    const fetchImpl = vi.fn().mockResolvedValueOnce(response(snapshot(5, { markets: [], dates: [], tombstones: [{ marketId: market.id, status: "suspended" }] })))
      .mockResolvedValueOnce(response(snapshot(4))).mockResolvedValueOnce(response(snapshot(6)));
    const store = createMarketsCatalogueStore({ storage: memoryStorage(), fetchImpl, now: () => time });
    await store.refresh(); await store.refresh();
    expect(store.getSnapshot().catalogue.revision).toBe(5);
    expect(store.getSnapshot().catalogue.markets).toEqual([]);
    await store.refresh();
    expect(store.getSnapshot().catalogue.revision).toBe(6);
    expect(store.getSnapshot().catalogue.markets).toHaveLength(1);
  });

  it("does not let a slow response in another tab overwrite a newer withdrawal", async () => {
    const storage = memoryStorage();
    let resolve;
    const slow = createMarketsCatalogueStore({ storage, now: () => time,
      fetchImpl: () => new Promise(done => { resolve = done; }) });
    const pending = slow.refresh();
    await Promise.resolve();
    const fast = createMarketsCatalogueStore({ storage, now: () => time, fetchImpl: async () => response(snapshot(7, {
      markets: [], dates: [], tombstones: [{ marketId: market.id, status: "archived" }],
    })) });
    await fast.refresh();
    resolve(response(snapshot(6)));
    await pending;
    expect(slow.getSnapshot().catalogue.revision).toBe(7);
    expect(slow.getSnapshot().catalogue.markets).toEqual([]);
    const restarted = createMarketsCatalogueStore({ storage, now: () => time });
    expect(restarted.getSnapshot().catalogue.revision).toBe(7);
  });

  it("rejects conflicting snapshot identities and invalid editions without replacing the last usable snapshot", async () => {
    const fetchImpl = vi.fn().mockResolvedValueOnce(response(snapshot(5)))
      .mockResolvedValueOnce(response(snapshot(5, { snapshotId: "conflict" })))
      .mockResolvedValueOnce(response(snapshot(6, { dates: [{ id: "unknown", marketId: "missing", date: "2026-11-01" }] })));
    const store = createMarketsCatalogueStore({ storage: memoryStorage(), fetchImpl, now: () => time });
    await store.refresh(); await store.refresh(); await store.refresh();
    expect(store.getSnapshot().catalogue.revision).toBe(5);
    expect(store.getSnapshot().error).toMatch(/Edizione/);
  });

  it("expires the packaged bootstrap and does not renew a remote snapshot through a fresh fetch", async () => {
    const expired = createMarketsCatalogueStore({ storage: memoryStorage(), now: () => Date.parse("2027-01-01T12:00:00Z") });
    expect(expired.getSnapshot().status).toBe("unavailable");
    const store = createMarketsCatalogueStore({ storage: memoryStorage(), fetchImpl: async () => response(snapshot()), now: () => time + 86400001 });
    await store.refresh();
    expect(store.getSnapshot().status).toBe("expired");
    expect(store.getSnapshot().catalogue.unavailable).toBe(true);
  });
});
