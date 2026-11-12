import { describe, expect, it } from "vitest";
import { buildEventsViewModel } from "../events/eventsViewModel";
import historicalCatalogue from "../../data/markets/catalogue2026.json";
import {
  MARKET_CATALOGUE as candidateCatalogue, eventMarketDays, findRequestedMarketEvent as findRequestedMarketEventIn,
  getMarket as getMarketIn, marketDay, marketDirectionsUrl, matchMarket as matchMarketIn,
  mergeMarketEvents as mergeMarketEventsIn, publicMarkets as publicMarketsIn,
  publishedMarketDates as publishedMarketDatesIn, selectMarkets as selectMarketsIn, weekendMarketDays,
} from "./marketsCatalog";

// These migration cases deliberately exercise the original 60-card seed.
const MARKET_CATALOGUE = historicalCatalogue;
const getMarket = (id, catalogue = historicalCatalogue) => getMarketIn(id, catalogue);
const publicMarkets = (catalogue = historicalCatalogue) => publicMarketsIn(catalogue);
const publishedMarketDates = (market, now, catalogue = historicalCatalogue) => publishedMarketDatesIn(market, now, catalogue);
const selectMarkets = ({ catalogue = historicalCatalogue, ...options }) => selectMarketsIn({ ...options, catalogue });
const mergeMarketEvents = (events, { catalogue = historicalCatalogue, ...options }) => mergeMarketEventsIn(events, { ...options, catalogue });
const matchMarket = (event, catalogue = historicalCatalogue) => matchMarketIn(event, catalogue);
const findRequestedMarketEvent = (events, request, now, catalogue = historicalCatalogue) => findRequestedMarketEventIn(events, request, now, catalogue);

const pn = { city: "Pordenone", regionCode: "IT-36" };
const ts = { city: "Trieste", regionCode: "IT-36" };
const now = new Date("2026-10-15T10:00:00Z");
describe("market catalogue and dated editions", () => {
  it("packages the selected 80 cards and withdrawals for the next app build", () => {
    expect(candidateCatalogue.markets).toHaveLength(80);
    expect(candidateCatalogue.dates).toHaveLength(206);
    expect(candidateCatalogue.tombstones).toHaveLength(13);
    expect(candidateCatalogue.markets.every(market => market.status === "published" && market.quality === "Documentato")).toBe(true);
    expect(["M013", "M014", "M015"].every(id => getMarketIn(id) === null)).toBe(true);
    expect(["M013", "M014", "M015"].every(id => candidateCatalogue.tombstones.some(item => item.marketId === id))).toBe(true);
  });
  it("shows documented weekly markets and keeps monthly markets without confirmed dates out of Events", () => {
    const reviewDay = new Date("2026-11-09T12:00:00Z");
    expect(getMarketIn("R-UDB-M040")?.group).toBe("regular");
    expect(getMarketIn("R-UDA-M054")?.validThrough).toBe("2027-04-27");
    expect(getMarketIn("M040")?.group).toBe("occasional");
    expect(getMarketIn("M032")?.group).toBe("occasional");
    expect(publishedMarketDatesIn(getMarketIn("M032"), reviewDay, candidateCatalogue)).toEqual([]);
    expect(publishedMarketDatesIn(getMarketIn("M040"), reviewDay, candidateCatalogue)).toEqual([]);
    expect(mergeMarketEventsIn([], { location: { city: "Udine", regionCode: "IT-36" }, radius: 5, now: reviewDay,
      catalogue: candidateCatalogue }).some(event => event.market_id === "M040")).toBe(false);
    expect(publishedMarketDatesIn(getMarketIn("M039"), reviewDay, candidateCatalogue).map(item => item.date)).toEqual(["2026-11-22"]);
  });
  it("uses the published December edition of AnticaMente with its habitual hours", () => {
    const reviewDay = new Date("2026-11-12T12:00:00Z");
    const market = getMarketIn("M025");
    expect(market.hours).toBe("Orario abituale: dall'alba al tramonto");
    expect(publishedMarketDatesIn(market, reviewDay, candidateCatalogue).map(item => item.date)).toEqual(["2026-12-06"]);
    const visible = selectMarketsIn({ location: pn, radius: 20, period: "all", now: reviewDay,
      catalogue: candidateCatalogue }).items.find(item => item.id === "M025");
    expect(visible?.dates.map(item => item.date)).toEqual(["2026-12-06"]);
  });
  it("shows only specifically published autumn editions and leaves unannounced ones undated", () => {
    const reviewDay = new Date("2026-11-12T12:00:00Z");
    expect(publishedMarketDatesIn(getMarketIn("M038"), reviewDay, candidateCatalogue).map(item => item.date))
      .toEqual(["2026-11-29"]);
    expect(publishedMarketDatesIn(getMarketIn("M042"), reviewDay, candidateCatalogue).map(item => item.date))
      .toEqual(["2026-11-29", "2026-12-13"]);
    for (const id of ["M027", "M032", "M040", "M041"]) {
      expect(publishedMarketDatesIn(getMarketIn(id), reviewDay, candidateCatalogue), id).toEqual([]);
    }
  });
  it("keeps all source records but publishes only documented cards", () => {
    expect(MARKET_CATALOGUE.markets).toHaveLength(60);
    expect(MARKET_CATALOGUE.dates).toHaveLength(176);
    expect(publicMarkets()).toHaveLength(53);
    expect(getMarket("M050")).toBeNull();
    expect(getMarket("M039")).toBeNull();
    expect(new Set(MARKET_CATALOGUE.markets.map(item => item.id)).size).toBe(60);
    expect(new Set(MARKET_CATALOGUE.dates.map(item => item.marketId + item.date)).size).toBe(176);
    expect(MARKET_CATALOGUE.dates.every(item => MARKET_CATALOGUE.markets.some(m => m.id === item.marketId))).toBe(true);
  });
  it("uses the selected FVG municipality and rejects outside-region or conflicting identities", () => {
    expect(selectMarkets({ location: { city: "Pordenone", regionCode: "IT-34" }, now }).supported).toBe(false);
    expect(selectMarkets({ location: null, now }).supported).toBe(false);
    expect(selectMarkets({ location: { city: "Roma", istatCode: "093033", regionCode: "IT-36" }, now }).supported).toBe(false);
    const local = selectMarkets({ location: pn, radius: 5, now });
    expect(local.items.every(item => item.comune === "Pordenone")).toBe(true);
    expect(local.items.map(item => item.id)).toContain("M001");
    expect(selectMarkets({ location: pn, radius: 50, now }).areaCount).toBeGreaterThan(local.areaCount);
  });
  it("filters habitual weekdays without generating weekly events", () => {
    const saturday = new Date("2026-10-17T10:00:00Z");
    expect(selectMarkets({ location: pn, radius: 5, period: "today", now: saturday }).items.map(item => item.id)).toContain("M001");
    expect(selectMarkets({ location: pn, radius: 5, period: "today", now }).items.map(item => item.id)).not.toContain("M001");
    expect(mergeMarketEvents([], { location: pn, radius: 5, now: saturday }).some(event => event.market_id === "M001")).toBe(false);
  });
  it("uses Rome civil days across midnight, DST and the current Sunday", () => {
    expect(marketDay(new Date("2026-10-14T22:30:00Z"))).toBe("2026-10-15");
    expect(weekendMarketDays(new Date("2026-10-18T10:00:00Z"))).toEqual(["2026-10-18"]);
    expect(weekendMarketDays(new Date("2026-10-23T22:30:00Z"))).toEqual(["2026-10-24", "2026-10-25"]);
  });
  it("does not invent monthly editions, holidays or dates in a new year", () => {
    expect(publishedMarketDates(getMarket("M037"), now)).toEqual([]);
    const afterYear = new Date("2027-01-02T12:00:00Z");
    expect(mergeMarketEvents([], { location: pn, radius: 50, now: afterYear })).toEqual([]);
    expect(selectMarkets({ location: pn, period: "today", now: afterYear }).items).toEqual([]);
    expect(selectMarkets({ location: pn, period: "all", now: afterYear }).items.length).toBeGreaterThan(0);
  });
  it("only injects published, local editions within the Events horizon", () => {
    const items = mergeMarketEvents([], { location: ts, radius: 20, now });
    expect(items.length).toBeGreaterThan(0);
    expect(items.every(event => event.start_date >= "2026-10-15" && event.start_date <= "2026-10-30")).toBe(true);
    expect(items.some(event => ["M024", "M050", "M056"].includes(event.market_id))).toBe(false);
    const model = buildEventsViewModel({ items }, { location: ts, now });
    expect(model.items.every(event => event.category === "mercato" && event.timeCategory !== "outside")).toBe(true);
  });
  it("reuses a source edition instead of adding a duplicate", () => {
    const source = {
      title: "La Soffitta in Piazza", event_city: "Pordenone", category: "mercato",
      date: "25 ottobre 2026", start_date: "2026-10-25", url: "https://example.org/edition", source: "Comune",
    };
    const merged = mergeMarketEvents([source], { location: pn, radius: 5, now });
    expect(merged.filter(event => event.market_id === "M035")).toHaveLength(1);
    expect(merged.find(event => event.market_id === "M035").url).toBe(source.url);
    const model = buildEventsViewModel({ items: merged }, { location: pn, now });
    expect(findRequestedMarketEvent(model.items, { marketId: "M035", date: "2026-10-25" }, now)?.title).toBe(source.title);
  });
  it("carries approximate municipality distances into injected market events without replacing a source distance", () => {
    const localMarket = getMarket("M035");
    const otherMarket = { ...localMarket, id: "test-udine", name: "Mercato di Udine", comune: "Udine" };
    const catalogue = { ...MARKET_CATALOGUE, markets: [localMarket, otherMarket], dates: [localMarket, otherMarket]
      .map(market => ({ marketId: market.id, date: "2026-10-25", status: "published", source: market.url })) };
    const local = mergeMarketEvents([], { location: pn, radius: 50, now, catalogue });
    expect(local.some(event => event.distance_km === 0)).toBe(true);
    expect(local.some(event => event.distance_km > 5)).toBe(true);
    expect(local.every(event => Number.isFinite(event.distance_km) && event.distance_km <= 50
      && event.distance_is_approximate === true)).toBe(true);
    const source = { title: "La Soffitta in Piazza", event_city: "Pordenone", start_date: "2026-10-25",
      distance_km: 0.7, distance_is_approximate: false, url: "https://example.org/edition" };
    const merged = mergeMarketEvents([source], { location: pn, radius: 5, now });
    expect(merged.find(event => event.market_id === "M035")).toMatchObject({ distance_km: 0.7, distance_is_approximate: false });
    const missing = mergeMarketEvents([{ ...source, distance_km: null }], { location: pn, radius: 5, now });
    expect(missing.find(event => event.market_id === "M035")).toMatchObject({ distance_km: 0, distance_is_approximate: true });
  });
  it("does not resurrect a cancelled date and does not turn a broad range into daily editions", () => {
    const source = { title: "La Soffitta in Piazza", event_city: "Pordenone", date: "25 ottobre 2026", status: "cancelled" };
    expect(mergeMarketEvents([source], { location: pn, radius: 5, now }).some(event => event.market_id === "M035")).toBe(false);
    const range = { ...source, status: "published", start_date: "2026-03-29", end_date: "2026-11-29" };
    expect(eventMarketDays(range, now)).toEqual([]);
    expect(mergeMarketEvents([range], { location: pn, radius: 5, now }).filter(event => event.market_id === "M035")).toHaveLength(1);
  });
  it("does not join different markets on a shared source URL or generic name", () => {
    const shared = getMarket("M004").url;
    expect(matchMarket({ title: "Mercatino", event_city: "San Daniele del Friuli", url: shared })).toBeNull();
    expect(matchMarket({ title: "Mercato settimanale" })).toBeNull();
    expect(matchMarket({ title: "La Soffitta in Piazza", event_city: "Trieste" })).toBeNull();
  });
  it("rejects a known market ID when the declared municipality contradicts it", () => {
    expect(matchMarket({ market_id: "M035", event_city: "Pordenone" })?.id).toBe("M035");
    expect(matchMarket({ market_id: "M035", event_city: "Trieste", title: "La Soffitta in Piazza" })).toBeNull();
    expect(matchMarket({ raw: { market_id: "M035", event_city: "Trieste" } })).toBeNull();
  });
  it("does not reopen an edition outside the current date window even if the record remains in the model", () => {
    const items = mergeMarketEvents([], { location: pn, radius: 5, now });
    const request = { marketId: "M035", date: "2026-10-25" };
    const expiredNow = new Date("2026-10-26T10:00:00Z");
    const expired = buildEventsViewModel({ items }, { location: pn, now: expiredNow });
    expect(expired.items.some(event => event.raw.market_id === "M035")).toBe(true);
    expect(findRequestedMarketEvent(expired.items, request, expiredNow)).toBeNull();
    expect(findRequestedMarketEvent(expired.items, request, new Date("2026-10-01T10:00:00Z"))).toBeNull();
  });
});


it("keeps source page query identities distinct and only maps a documented venue", () => {
  const market = { ...getMarket("M035"), url: "https://example.org/event?id=1" };
  const catalogue = { ...MARKET_CATALOGUE, markets: [market], dates: [] };
  expect(matchMarket({ url: "https://example.org/event?id=2" }, catalogue)).toBeNull();
  expect(matchMarket({ url: "https://example.org/event?utm_source=link&id=1" }, catalogue)?.id).toBe("M035");
  expect(marketDirectionsUrl(getMarket("M030"))).toBe("");
  const url = new URL(marketDirectionsUrl(market));
  expect(url.searchParams.get("query")).toContain("Pordenone");
  expect(url.pathname).toBe("/maps/search/");
});
