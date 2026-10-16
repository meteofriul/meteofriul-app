import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { fetchLocalEvents, LOCAL_PILOT_EVENTS_API, PRODUCTION_EVENTS_API, FULL_EVENTS_LIMIT } from "../../services/eventsApi";
import { createEventsCachePayload, getEventsCacheKey, readEventsCacheEntry } from "../../services/eventsCache";
import { loadEventsData, readInitialEventsData } from "./eventsDataController";
import { loadHomeEvents, readInitialHomeData } from "../home/homeDataController";
import { buildEventsViewModel } from "./eventsViewModel";
import { buildHomeEventsViewModel } from "../home/homeViewModel";
import { EventsView, EventPreviewPanel } from "./EventsView";
import { HomeEventsTeaser } from "../home/HomeEventsTeaser";

const location = { city: "Udine", lat: 46.07, lon: 13.23 };
const now = new Date("2026-10-15T10:00:00Z");
const event = { title: "Concerto verificato", source: "Azalea", start_date: "2026-10-15",
  url: "https://example.test/event", event_city: "Udine" };
const health = {
  catalog_status: "degraded", snapshot: "daily-snapshot",
  source_status: { Azalea: "fresh", TurismoFVG: "partial", Spazzapan: "stale" },
  source_failure_tags: { TurismoFVG: "quarantined_cards", Spazzapan: "adapter_exception" },
  source_updated_at: { Azalea: "2026-10-15T04:00:00Z", Spazzapan: "2026-10-13T04:00:00Z" },
};

function storageWithSavedEvent() {
  const values = new Map([[getEventsCacheKey(location, FULL_EVENTS_LIMIT), JSON.stringify({
    savedAt: now.getTime() - 1000,
    data: createEventsCachePayload([{ ...event, title: "Old failed-source event", source: "Spazzapan" }]),
  })]]);
  return { getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value), removeItem: (key) => values.delete(key) };
}

const loaders = [
  { name: "Events", load: loadEventsData, hydrate: readInitialEventsData },
  { name: "Home", load: loadHomeEvents,
    hydrate: (place, options) => readInitialHomeData(place, {
      ...options, weatherCacheReader: () => null, bootstrapCacheReader: () => null,
    })?.events },
];

describe("EV-04 catalog health from API through cache and UI", () => {
  it.each([LOCAL_PILOT_EVENTS_API, PRODUCTION_EVENTS_API])("does not turn settled degradation into ready or retrying partial (%s)", async (apiBase) => {
    const fetchImpl = vi.fn(async () => ({ ok: true, json: async () => ({
      ...health, events: [event], total: 1, next_offset: null, status: "ready",
    }) }));
    const payload = await fetchLocalEvents(location, { apiBase, fetchImpl });
    expect(payload).toMatchObject({ cacheStatus: "degraded", isDegraded: true,
      isPartial: false, isRefreshing: false, shouldRetry: false,
      catalogHealth: { status: "degraded", snapshot: health.snapshot,
        sourceStatus: health.source_status, sourceFailureTags: health.source_failure_tags,
        sourceUpdatedAt: health.source_updated_at } });
    expect(fetchImpl).toHaveBeenCalledOnce();
  });

  for (const { name, load, hydrate } of loaders) {
    it.each([{ events: [] }, { events: [event] }])(`${name} preserves degraded health across an empty/mixed response, reopening and offline fallback ($events.length records)`, async ({ events }) => {
      const storage = storageWithSavedEvent();
      const options = { storage, now: () => now.getTime(),
        eventsFetcher: (place, opts) => fetchLocalEvents(place, { ...opts,
          apiBase: PRODUCTION_EVENTS_API,
          fetchImpl: async () => ({ ok: true, json: async () => ({
            ...health, events: [...events], total: events.length, next_offset: null,
          }) }),
        }),
      };
      const state = await load(location, options);
      expect(state).toMatchObject({ status: "degraded", isDegraded: true,
        shouldRetry: false, fromCache: false, total: events.length });
      expect(state.items.map((item) => item.title)).toEqual(events.map((item) => item.title));
      expect(readEventsCacheEntry(location, FULL_EVENTS_LIMIT, options).data.catalogHealth)
        .toEqual(state.catalogHealth);
      const reopened = hydrate(location, options);
      expect(reopened).toMatchObject({ status: "degraded", fromCache: true,
        isDegraded: true, catalogHealth: state.catalogHealth });
      const offline = await load(location, { ...options,
        eventsFetcher: async () => { throw new Error("offline"); } });
      expect(offline).toMatchObject({ status: "stale", fromCache: true,
        isDegraded: true, catalogHealth: state.catalogHealth });
      expect(offline.items).toEqual(state.items);
      expect(JSON.stringify(offline)).not.toContain("Old failed-source event");

      for (const language of ["it", "fur"]) {
        const viewOptions = { language, location, now };
        const model = buildEventsViewModel(state, viewOptions);
        const home = buildHomeEventsViewModel(state, viewOptions);
        const expected = language === "it" ? "Catalogo incompleto" : "Catalic incomplet";
        expect(model.message).toContain(expected);
        expect(home.message).toContain(expected);
        expect(model.message).not.toBe(model.copy.loadingBody);
        expect(renderToStaticMarkup(<EventsView model={model} language={language} />)).toContain(expected);
        expect(renderToStaticMarkup(<HomeEventsTeaser events={home} />)).toContain(expected);
        if (!events.length) {
          const html = renderToStaticMarkup(<EventsView model={model} language={language} />);
          expect(html).not.toContain(model.copy.emptyTitle);
        }
        const offlineModel = buildEventsViewModel(offline, viewOptions);
        expect(offlineModel.message).toContain(expected);
        expect(offlineModel.message).toContain(language === "it" ? "salvati" : "salvâts");
      }
    });

    it(`${name} accepts a complete empty result and clears previous health and events`, async () => {
      const storage = storageWithSavedEvent();
      storage.setItem(getEventsCacheKey(location, FULL_EVENTS_LIMIT), JSON.stringify({
        savedAt: now.getTime() - 1000,
        data: createEventsCachePayload([event], "pilot-events-v2-programmes", {
          status: "degraded", sourceStatus: health.source_status,
          sourceFailureTags: health.source_failure_tags,
        }),
      }));
      const state = await load(location, { storage, now: () => now.getTime(),
        eventsFetcher: (place, opts) => fetchLocalEvents(place, { ...opts,
          apiBase: PRODUCTION_EVENTS_API, fetchImpl: async () => ({ ok: true,
            json: async () => ({ events: [], total: 0, catalog_status: "complete",
              source_status: { Azalea: "fresh" }, source_failure_tags: {}, next_offset: null }),
          }),
        }),
      });
      expect(state).toMatchObject({ status: "fresh", isDegraded: false, items: [],
        catalogHealth: { status: "complete", sourceFailureTags: {} } });
      expect(hydrate(location, { storage, now: () => now.getTime() })).toMatchObject({
        items: [], isDegraded: false, fromCache: true,
      });
    });
  }

  it("treats expired fresh batches as degraded from failure tags even with no records", async () => {
    const payload = await fetchLocalEvents(location, { apiBase: PRODUCTION_EVENTS_API,
      fetchImpl: async () => ({ ok: true, json: async () => ({
        events: [], total: 0, source_status: { Azalea: "fresh" },
        source_failure_tags: { Azalea: "source_expired" }, next_offset: null,
      }) }),
    });
    expect(payload).toMatchObject({ cacheStatus: "degraded", isDegraded: true, shouldRetry: false });
  });

  it("does not hydrate pre-fix caches whose completeness is unknown", () => {
    const storage = storageWithSavedEvent();
    storage.setItem(getEventsCacheKey(location, FULL_EVENTS_LIMIT), JSON.stringify({
      savedAt: now.getTime(), data: { schemaVersion: "canonical-events-v2", events: [event] },
    }));
    expect(readInitialEventsData(location, { storage, now: () => now.getTime() })).toBeNull();
  });

  it("preserves settled degradation when collecting more than one page", async () => {
    const fetchImpl = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => ({
        ...health, events: [event], total: 2, next_offset: 1,
      }) })
      .mockResolvedValueOnce({ ok: true, json: async () => ({
        ...health, events: [{ ...event, title: "Secondo concerto", url: "https://example.test/second" }],
        total: 2, next_offset: null,
      }) });
    const payload = await fetchLocalEvents(location, { apiBase: PRODUCTION_EVENTS_API, fetchImpl });
    expect(payload).toMatchObject({ cacheStatus: "degraded", shouldRetry: false,
      catalogHealth: { sourceFailureTags: health.source_failure_tags } });
    expect(payload.events).toHaveLength(2);
    expect(fetchImpl).toHaveBeenCalledTimes(2);
  });

  it("keeps schedules, single times, end-only dates and recovered Spazzapan together in degraded cache", async () => {
    const regional = { source: "TurismoFVG", event_city: "Udine" };
    const events = [
      { ...regional, title: "Barbacan", url: "https://www.turismofvg.it/eventi/barbacan",
        start_date: "2026-04-12", end_date: "2026-12-13", schedule_kind: "period",
        opening_days_status: "unknown" },
      { ...regional, title: "Le Rose", url: "https://www.turismofvg.it/eventi/rose",
        start_date: "2026-10-15", end_date: "2026-10-15", time: "17:00" },
      { ...regional, title: "Memorie riflesse", url: "https://www.turismofvg.it/eventi/memorie",
        start_date: null, end_date: "2027-01-07", schedule_kind: "end_only",
        date_label: "Fino al 7 gennaio 2027" },
      { source: "Galleria Spazzapan", source_id: "234126", title: "Tra internazionalismo e Genius loci",
        url: "https://galleriaspazzapan.regione.fvg.it/it/eventi-collaterali-ottobre-174822",
        event_city: "Gradisca d'Isonzo", start_date: "2026-10-28", end_date: "2026-10-28", time: "18:00" },
    ];
    const storage = storageWithSavedEvent();
    const options = { storage, now: () => now.getTime(),
      eventsFetcher: (place, opts) => fetchLocalEvents(place, { ...opts,
        apiBase: PRODUCTION_EVENTS_API, fetchImpl: async () => ({ ok: true,
          json: async () => ({ events: structuredClone(events), total: events.length, next_offset: null,
            catalog_status: "degraded", snapshot: "integrated-snapshot",
            source_status: { TurismoFVG: "partial", "Galleria Spazzapan": "fresh" },
            source_failure_tags: { TurismoFVG: "quarantined_cards" } }),
        }),
      }),
    };
    const online = await loadEventsData(location, options);
    const reopened = readInitialEventsData(location, options);
    const offline = await loadEventsData(location, { ...options,
      eventsFetcher: async () => { throw new Error("offline"); } });
    for (const state of [online, reopened, offline]) {
      const model = buildEventsViewModel(state, { location, now });
      const byTitle = Object.fromEntries(model.items.map((item) => [item.title, item]));
      expect(state.catalogHealth.sourceStatus["Galleria Spazzapan"]).toBe("fresh");
      expect(state.shouldRetry).toBe(false);
      expect(model.message).toContain("Catalogo incompleto");
      expect(byTitle.Barbacan.timeCategory).toBe("next");
      expect(byTitle.Barbacan.scheduleLabel).toBe("Giornate di apertura da verificare");
      expect(byTitle["Memorie riflesse"].raw.start_date).toBeNull();
      expect(byTitle["Memorie riflesse"].timeCategory).toBe("next");
      for (const [title, expected] of [["Le Rose", "17:00"],
        ["Memorie riflesse", "Fino al 7 gennaio 2027"],
        ["Tra internazionalismo e Genius loci", "18:00"]]) {
        const html = renderToStaticMarkup(<EventPreviewPanel event={byTitle[title]}
          copy={model.copy} onClose={() => {}} />);
        expect(html).toContain(expected);
      }
      expect(renderToStaticMarkup(<EventsView model={model} />)).toContain("Catalogo incompleto");
    }
  });
});
