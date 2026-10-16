import { JSDOM } from "jsdom";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { getEventsViewCopy } from "../../copy/eventsViewCopy";
import { createEventsCachePayload, EVENTS_DEVICE_CACHE_MAX_AGE_MS, getEventsCacheKey } from "../../services/eventsCache";
import { FULL_EVENTS_LIMIT } from "../../services/eventsApi";
import { loadEventsData } from "./eventsDataController";
import { buildEventsViewModel } from "./eventsViewModel";
import { EventsView } from "./EventsView";
import { loadHomeEvents } from "../home/homeDataController";
import { buildHomeEventsViewModel } from "../home/homeViewModel";
import { getHomeStaticViewModel } from "../home/homeFixture";
import { HomeView } from "../home/HomeView";

const now = new Date("2026-10-15T10:00:00Z");
const location = { city: "Udine", lat: 46.07, lon: 13.23 };
const event = { id: "concert", title: "Concerto verificato", source: "Azalea",
  start_date: "2026-10-15", date: "15 ottobre 2026", url: "https://example.test/concert", event_city: "Udine" };
const degraded = { status: "degraded", sourceFailureTags: { TurismoFVG: "source_expired" } };
const complete = { status: "complete", sourceFailureTags: {} };
const offline = async () => { throw new Error("Failed to fetch"); };

function storageWith(payload, age = 1000) {
  const values = new Map();
  if (payload) values.set(getEventsCacheKey(location, FULL_EVENTS_LIMIT), JSON.stringify({
    data: payload, savedAt: now.getTime() - age,
  }));
  return { getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value), removeItem: (key) => values.delete(key) };
}

function payload(events, health = complete) {
  return createEventsCachePayload(events, "pilot-events-v2-programmes", health);
}

function renderSurfaces(state, language) {
  const options = { language, location, now };
  const home = new JSDOM(renderToStaticMarkup(<HomeView language={language} weatherNow={now}
    model={{ ...getHomeStaticViewModel(language), events: buildHomeEventsViewModel(state, options) }} />));
  const events = new JSDOM(renderToStaticMarkup(<EventsView language={language}
    model={buildEventsViewModel(state, options)} />));
  return { home: home.window.document.querySelector(".mf-home-quick-card--events"),
    events: events.window.document.body };
}

describe.each(["it", "fur"])("EV-04 runtime Home and Events availability (%s)", (language) => {
  const copy = getEventsViewCopy(language);

  it.each([
    { label: "degraded online", health: degraded, saved: false },
    { label: "degraded offline", health: degraded, saved: true },
    { label: "complete offline", health: complete, saved: true },
  ])("keeps the featured event and its warning in the real Home: $label", async ({ health, saved }) => {
    const data = payload([event], health);
    const state = await loadHomeEvents(location, { storage: storageWith(data), now: () => now.getTime(),
      eventsFetcher: saved ? offline : async () => data });
    const { home } = renderSurfaces(state, language);
    expect(home.textContent).toContain(event.title);
    const warning = home.querySelector('[role="status"]');
    expect(warning).not.toBeNull();
    if (health === degraded) expect(warning.textContent).toContain(copy.degradedTitle);
    if (saved) expect(warning.textContent).toMatch(language === "it" ? /salvati/ : /salv[aâ]ts/);
    expect(home.querySelector(".mf-home-quick-events__count")).toBeNull();
  });

  for (const [name, load] of [["Home", loadHomeEvents], ["Events", loadEventsData]]) {
    it.each(["missing", "expired"])(`${name} reports unavailable with %s cache, without a false zero`, async (cache) => {
      const storage = cache === "missing" ? storageWith() : storageWith(payload([event]), EVENTS_DEVICE_CACHE_MAX_AGE_MS + 1);
      const state = await load(location, { storage, now: () => now.getTime(), eventsFetcher: offline });
      expect(state).toMatchObject({ status: "error", fromCache: false, items: [] });
      const surfaces = renderSurfaces(state, language);
      for (const surface of Object.values(surfaces)) {
        expect(surface.textContent).toContain(copy.unavailableTitle);
        expect(surface.textContent).toContain(copy.unavailableBody);
        expect(surface.textContent).not.toContain(copy.emptyBody);
        expect(surface.textContent).not.toContain(event.title);
      }
      expect(surfaces.home.querySelector(".mf-home-quick-events__count")).toBeNull();
      expect(surfaces.events.querySelector(".mf-events-empty").textContent).not.toContain(copy.emptyTitle);
    });
  }

  it("does not claim a successful empty result when an empty complete cache cannot be refreshed", async () => {
    const state = await loadEventsData(location, { storage: storageWith(payload([])),
      now: () => now.getTime(), eventsFetcher: offline });
    for (const surface of Object.values(renderSurfaces(state, language))) {
      expect(surface.textContent).toContain(copy.unavailableTitle);
      expect(surface.textContent).not.toContain(copy.emptyBody);
    }
  });

  it.each([false, true])("preserves degraded empty diagnostics (offline=%s)", async (saved) => {
    const data = payload([], degraded);
    const state = await loadEventsData(location, { storage: storageWith(data), now: () => now.getTime(),
      eventsFetcher: saved ? offline : async () => data });
    for (const surface of Object.values(renderSurfaces(state, language))) {
      expect(surface.textContent).toContain(copy.degradedTitle);
      expect(surface.textContent).toContain(copy.degradedEmptyBody);
      expect(surface.textContent).not.toContain(copy.emptyBody);
      if (saved) expect(surface.textContent).toContain(copy.savedCatalogBody);
    }
  });

  it("clears unavailable warnings after reconnecting to populated and genuinely empty complete results", async () => {
    const storage = storageWith();
    const options = { storage, now: () => now.getTime() };
    const failed = await loadEventsData(location, { ...options, eventsFetcher: offline });
    expect(failed.status).toBe("error");
    for (const items of [[event], []]) {
      const state = await loadEventsData(location, { ...options, eventsFetcher: async () => payload(items) });
      for (const surface of Object.values(renderSurfaces(state, language))) {
        expect(surface.textContent).not.toContain(copy.unavailableTitle);
        expect(surface.textContent).not.toContain(copy.degradedTitle);
        expect(surface.textContent).not.toContain(copy.savedCatalogBody);
        expect(surface.textContent).toContain(items.length ? event.title : copy.emptyBody);
      }
    }
  });
});
