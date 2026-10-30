import { describe, expect, it } from "vitest";
import { buildEventsViewModel } from "../events/eventsViewModel";
import { findRequestedMarketEvent, getMarket, marketDirectionsUrl, mergeMarketEvents, selectMarkets } from "./marketsCatalog";

const now = new Date("2026-10-30T12:00:00Z");
const location = { city: "Pordenone", regionCode: "IT-36" };
const market = getMarket("M035");
const source = { market_id: market.id, event_city: market.comune, title: market.name,
  start_date: "2026-11-01", end_date: "2026-11-01", venue: "Sede precedente", lat: 0, lon: 0,
  url: "https://source.example/edition", source: "Comune", category: "mercato", id: "old-feed-id" };
function catalogue(fields = {}) {
  return { schemaVersion: 2, validThrough: "2026-12-31", markets: [market],
    identities: [{ marketId: market.id, name: market.name, comune: market.comune, sourceUrls: [market.url], status: "published" }],
    tombstones: [], dates: [{ id: "edition-stable-1", marketId: market.id, date: "2026-11-02", status: "published",
      legacyDates: ["2026-11-01"], venue: { id: "venue-2", place: "Piazza nuova", directionsQuery: "Piazza nuova, Pordenone" }, source: market.url }], ...fields };
}

describe("authoritative market editions", () => {
  it("moves a stale source edition with the same stable ID and the edition's venue", () => {
    const snapshot = catalogue();
    const merged = mergeMarketEvents([source], { location, now, catalogue: snapshot });
    expect(merged).toHaveLength(1);
    expect(merged[0]).toMatchObject({ id: "edition-stable-1", start_date: "2026-11-02", venue: "Piazza nuova", lat: null, lon: null });
    expect(merged[0].maps_url).toContain("Piazza%20nuova");
    const model = buildEventsViewModel({ items: merged }, { location, now });
    expect(findRequestedMarketEvent(model.items, { marketId: market.id, date: "2026-11-01" }, now, snapshot)?.id).toBe("edition-stable-1");
    expect(findRequestedMarketEvent(model.items, { marketId: market.id, editionId: "edition-stable-1" }, now, snapshot)?.id).toBe("edition-stable-1");
  });

  it("keeps a dated venue distinct from another edition and does not guess directions", () => {
    const snapshot = catalogue();
    snapshot.dates.push({ ...snapshot.dates[0], id: "edition-stable-2", date: "2026-11-03", legacyDates: [], venue: { id: "venue-3", place: "Sede da precisare" } });
    const merged = mergeMarketEvents([], { location, now, catalogue: snapshot });
    expect(merged.map(item => item.venue)).toEqual(["Piazza nuova", "Sede da precisare"]);
    expect(marketDirectionsUrl(market, snapshot.dates[1])).toBe("");
    expect(merged[1].maps_url).toBe("");
  });

  it("recognizes archived identities and suppresses stale source events even without an explicit market ID", () => {
    const snapshot = catalogue({ markets: [], dates: [], tombstones: [{ marketId: market.id, status: "archived" }] });
    const old = { ...source, market_id: undefined };
    expect(mergeMarketEvents([old], { location, now, catalogue: snapshot })).toEqual([]);
  });

  it("recognizes an old municipality only through a documented alias and applies the current area", () => {
    const moved = { ...market, comune: "Udine", prov: "UD" };
    const snapshot = catalogue({ markets: [moved], identities: [{ marketId: market.id, name: market.name,
      comune: "Udine", municipalityAliases: ["Pordenone"], sourceUrls: [source.url] }] });
    expect(mergeMarketEvents([source], { location, radius: 5, now, catalogue: snapshot })).toEqual([]);
    const relocated = mergeMarketEvents([source], { location: { city: "Udine", regionCode: "IT-36" }, radius: 5, now, catalogue: snapshot });
    expect(relocated).toHaveLength(1);
    expect(relocated[0].event_city).toBe("Udine");
    const unrelated = { ...source, market_id: undefined, event_city: "Trieste" };
    expect(mergeMarketEvents([unrelated], { location, radius: 5, now, catalogue: snapshot })).toContain(unrelated);
  });

  it("does not recreate a cancelled edition or turn an unknown source range into an edition", () => {
    const snapshot = catalogue();
    snapshot.dates[0].status = "cancelled";
    expect(mergeMarketEvents([source], { location, now, catalogue: snapshot })).toEqual([]);
    const noDates = catalogue({ dates: [] });
    expect(mergeMarketEvents([{ ...source, end_date: "2026-11-20" }], { location, now, catalogue: noDates })).toEqual([]);
  });

  it("uses tombstones for dated regular cancellations and respects a bounded season", () => {
    const regular = { ...market, group: "regular", weekdays: [5], validFrom: "2026-11-01", validThrough: "2026-11-30" };
    const snapshot = catalogue({ markets: [regular], dates: [], tombstones: [{ marketId: market.id, date: "2026-11-01", status: "cancelled" }] });
    expect(mergeMarketEvents([source], { location, now, catalogue: snapshot })).toEqual([]);
    expect(selectMarkets({ location, now, period: "today", catalogue: snapshot }).items).toEqual([]);
  });

  it("removes a cancelled weekly day from today/weekend and shows only explicit extraordinary editions", () => {
    const friday = { ...market, group: "regular", weekdays: [5], validThrough: "2026-12-31" };
    const cancelled = catalogue({ markets: [friday], dates: [{ id: "cancelled-friday", marketId: market.id, date: "2026-10-30", status: "cancelled" }],
      tombstones: [{ marketId: market.id, editionId: "cancelled-friday", date: "2026-10-30", status: "cancelled" }] });
    expect(selectMarkets({ location, now, period: "today", catalogue: cancelled }).items).toEqual([]);
    expect(selectMarkets({ location, now, period: "all", catalogue: cancelled }).items).toHaveLength(1);
    const saturday = new Date("2026-10-31T12:00:00Z");
    const moved = catalogue({ markets: [friday], dates: [{ id: "special-saturday", marketId: market.id, date: "2026-10-31", status: "published" }] });
    expect(selectMarkets({ location, now: saturday, period: "today", catalogue: moved }).items).toHaveLength(1);
    expect(mergeMarketEvents([], { location, now, catalogue: moved }).map(item => item.id)).toEqual(["special-saturday"]);
    expect(mergeMarketEvents([], { location, now, catalogue: { ...moved, dates: [] } })).toEqual([]);
  });

  it("does not extend a market's evidence when another market expands the global horizon", () => {
    const snapshot = catalogue({ validThrough: "2027-04-27", markets: [{ ...market, validThrough: "2026-12-31" }],
      dates: [{ id: "old-evidence", marketId: market.id, date: "2027-01-02", status: "published" }] });
    const january = new Date("2027-01-01T12:00:00Z");
    expect(mergeMarketEvents([{ ...source, start_date: "2027-01-02", end_date: "2027-01-02" }], { location, now: january, catalogue: snapshot })).toEqual([]);
    expect(selectMarkets({ location, now: january, catalogue: snapshot }).items[0].dates).toEqual([]);
  });

  it("reconciles the weekday and opening hours of a regular market instead of trusting a stale feed", () => {
    const regular = { ...market, group: "regular", weekdays: [6], hours: "10:00–14:00", cadence: "Sabato" };
    const snapshot = catalogue({ markets: [regular], dates: [] });
    const oldFriday = { ...source, start_date: "2026-10-30", end_date: "2026-10-30", time: "08:00", description: "Aperto venerdì alle 8" };
    expect(mergeMarketEvents([oldFriday], { location, now, catalogue: snapshot })).toEqual([]);
    const saturday = { ...oldFriday, start_date: "2026-10-31", end_date: "2026-10-31" };
    const merged = mergeMarketEvents([saturday], { location, now, catalogue: snapshot });
    expect(merged).toHaveLength(1);
    expect(merged[0]).toMatchObject({ time: "10:00–14:00", lat: null, lon: null });
    expect(merged[0].description).toContain("Sabato");
    expect(merged[0].description).not.toContain("venerdì");
    expect(mergeMarketEvents([{ ...saturday, end_date: "2026-11-30" }], { location, now, catalogue: snapshot })).toEqual([]);
  });
});
