import { describe, expect, it, vi } from "vitest";
import { DEFAULT_APP_LOCATION } from "../app/appLocation";
import { getLocalFvgLocationResults } from "./locationSearch";

import {
  buildLocalEventDetailUrl,
  buildLocalEventsUrl,
  coerceFiniteNumber,
  fetchLocalEventDetail,
  fetchLocalEvents,
  FULL_EVENTS_LIMIT,
  getEventsRequestLimit,
  HOME_EVENTS_LIMIT,
  LOCAL_PILOT_EVENTS_API,
  normalizeLocalEventsPayload,
  PILOT_EVENTS_API,
  resolveEventsApiBase,
} from "./eventsApi";

describe("events api service", () => {
  it("uses the verified municipality point for a fresh-install placeholder without changing it", () => {
    const before = structuredClone(DEFAULT_APP_LOCATION);
    const params = new URL(buildLocalEventsUrl(DEFAULT_APP_LOCATION, { apiBase: PILOT_EVENTS_API })).searchParams;
    const udine = getLocalFvgLocationResults("Udine").find((place) => place.istatCode === "030129");
    expect(Number(params.get("lat"))).toBe(udine.latitude);
    expect(Number(params.get("lon"))).toBe(udine.longitude);
    expect(DEFAULT_APP_LOCATION).toEqual(before);
  });
  it("shares a complete in-flight pilot snapshot and allows a fresh load afterward", async () => {
    let resolveFirstPage;
    const fetchImpl = vi.fn()
      .mockImplementationOnce(() => new Promise(resolve => { resolveFirstPage = resolve; }))
      .mockResolvedValueOnce({ ok: true, json: async () => ({ events: [{ title: "b" }], snapshot: "s1", next_offset: null }) })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ events: [{ title: "new" }], total: 1, snapshot: "s2" }) });
    const options = { apiBase: PILOT_EVENTS_API, fetchImpl };
    const first = fetchLocalEvents("Udine", options);
    const second = fetchLocalEvents("Udine", { ...options, limit: FULL_EVENTS_LIMIT });
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    resolveFirstPage({ ok: true, json: async () => ({ events: [{ title: "a" }], total: 2, snapshot: "s1", next_offset: 100 }) });
    const results = await Promise.all([first, second]);
    expect(results[0].events).toHaveLength(2);
    expect(results[1].events).toEqual(results[0].events);
    expect(fetchImpl).toHaveBeenCalledTimes(2);
    const refreshed = await fetchLocalEvents("Udine", options);
    expect(refreshed.events[0].title).toBe("new");
    expect(fetchImpl).toHaveBeenCalledTimes(3);
  });

  it("keeps retry budgets independent and does not retain failed requests", async () => {
    let resolveRequest;
    const fetchImpl = vi.fn()
      .mockImplementationOnce(() => new Promise(resolve => { resolveRequest = resolve; }))
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce({ ok: true, json: async () => ({ events: [] }) });
    const options = { apiBase: "/api", fetchImpl };
    const first = fetchLocalEvents("Udine", options);
    const second = fetchLocalEvents("Udine", { ...options, retry: 20 });
    resolveRequest({ ok: true, json: async () => ({ events: [], cache: { status: "refreshing" } }) });
    expect((await first).shouldRetry).toBe(true);
    expect((await second).shouldRetry).toBe(false);
    await expect(fetchLocalEvents("Udine", options)).rejects.toThrow("offline");
    await expect(fetchLocalEvents("Udine", options)).resolves.toMatchObject({ events: [] });
    expect(fetchImpl).toHaveBeenCalledTimes(3);
  });

  it("does not share different locations, radii or fetch transports", async () => {
    const response = () => ({ ok: true, json: async () => ({ events: [] }) });
    const fetchImpl = vi.fn(async () => response());
    const otherFetch = vi.fn(async () => response());
    await Promise.all([
      fetchLocalEvents({ city: "Udine", eventsRadius: 5 }, { apiBase: PILOT_EVENTS_API, fetchImpl }),
      fetchLocalEvents({ city: "Udine", eventsRadius: 20 }, { apiBase: PILOT_EVENTS_API, fetchImpl }),
      fetchLocalEvents({ city: "Trieste", eventsRadius: 5 }, { apiBase: PILOT_EVENTS_API, fetchImpl }),
      fetchLocalEvents({ city: "Udine", eventsRadius: 5 }, { apiBase: PILOT_EVENTS_API, fetchImpl: otherFetch }),
    ]);
    expect(fetchImpl).toHaveBeenCalledTimes(3);
    expect(otherFetch).toHaveBeenCalledTimes(1);
  });

  it("routes only the local pilot to its dedicated Events catalog", () => {
    expect(resolveEventsApiBase({
      apiBase: "/api",
      localPilot: false,
      nativeAndroid: false,
    })).toBe("/api");
    expect(resolveEventsApiBase({
      apiBase: "/api",
      localPilot: true,
      nativeAndroid: false,
    })).toBe(LOCAL_PILOT_EVENTS_API);
    expect(resolveEventsApiBase({
      apiBase: "/api",
      localPilot: true,
      nativeAndroid: true,
    })).toBe(PILOT_EVENTS_API);
  });

  it("collects all pilot pages and sends the selected radius", async () => {
    const apiBase = "https://meteofriul-events-49007668366.europe-west1.run.app/api";
    const fetchImpl = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => ({ events: [{title:"a"}], total:2, snapshot:"s1", next_offset:100 }) })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ events: [{title:"b"}], total:2, snapshot:"s1", next_offset:null }) });
    const result = await fetchLocalEvents({ city:"Udine", lat:46, lon:13, eventsRadius:50 }, { apiBase, fetchImpl });
    expect(result.events).toHaveLength(2);
    expect(fetchImpl.mock.calls[0][0]).toContain("radius=50");
    expect(fetchImpl.mock.calls[1][0]).toContain("offset=100&snapshot=s1");
  });

  it("paginates the browser pilot through its relative same-origin proxy", async () => {
    const fetchImpl = vi.fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          events: [{ title: "a" }],
          total: 2,
          snapshot: "s1",
          next_offset: 100,
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          events: [{ title: "b" }],
          total: 2,
          snapshot: "s1",
          next_offset: null,
        }),
      });

    const result = await fetchLocalEvents(
      { city: "Pordenone", lat: 45.9567, lon: 12.6605 },
      { apiBase: LOCAL_PILOT_EVENTS_API, fetchImpl },
    );

    expect(result.events).toHaveLength(2);
    expect(fetchImpl.mock.calls[0][0]).toContain("/__pilot-events/api/local/events?");
    expect(fetchImpl.mock.calls[1][0]).toContain("/__pilot-events/api/local/events?");
    expect(fetchImpl.mock.calls[1][0]).toContain("offset=100&snapshot=s1");
  });

  it("rejects a truncated pilot catalog instead of caching it as complete", async () => {
    const apiBase = "https://meteofriul-events-49007668366.europe-west1.run.app/api";
    const fetchImpl = vi.fn().mockResolvedValue({ok:true,json:async()=>({events:[],total:101})});
    await expect(fetchLocalEvents({city:"Udine",lat:46,lon:13},{apiBase,fetchImpl})).rejects.toThrow("incompleto");
  });
  it("does not turn missing coordinates into zero", () => {
    for (const value of [null, undefined, "", true, false]) {
      expect(coerceFiniteNumber(value)).toBe(null);
    }
  });

  it("adapts pilot dates and preserves separate performance identities", async () => {
    const apiBase = "https://meteofriul-events-49007668366.europe-west1.run.app/api";
    const fetchImpl = vi.fn().mockResolvedValue({ ok: true, json: async () => ({
      events: ["2026-09-07", "2026-09-08"].map(start_date => ({
        title: "Spettacolo", url: "https://example.org/event", start_date, time: "20:00",
      })),
    }) });
    const result = await fetchLocalEvents({ city: "Udine", lat: 46.06, lon: 13.23 }, { apiBase, fetchImpl });
    expect(result.events[0].date).toBe("7 settembre 2026");
    expect(result.events[0].id).not.toBe(result.events[1].id);
    expect(result.contractVersion).toBe("pilot-events-v2-programmes");
    expect(result.shouldRetry).toBe(false);
    expect(fetchImpl.mock.calls[0][0]).toContain(apiBase);
  });

  it("preserves the official deadline label when no start date is published", async () => {
    const event = {
      source: "TurismoFVG", url: "https://www.turismofvg.it/eventi/mostra",
      title: "Memorie riflesse", start_date: null, end_date: "2027-01-07",
      schedule_kind: "end_only", date_label: "Fino al 7 gennaio 2027",
    };
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true, json: async () => ({ events: [event], total: 1 }),
    });
    const result = await fetchLocalEvents(
      { city: "Udine", lat: 46.06, lon: 13.23 },
      { apiBase: PILOT_EVENTS_API, fetchImpl },
    );
    expect(result.events[0].date).toBe("Fino al 7 gennaio 2027");
    expect(result.events[0].start_date).toBeNull();
  });

  it("shows an exhibition's month precision without invented opening days", async () => {
    const event = {
      source: "TurismoFVG", url: "https://www.turismofvg.it/eventi/radici-nella-pietra",
      title: "Radici nella pietra", start_date: "2026-05-01", end_date: "2026-12-31",
      schedule_kind: "month_range", date_precision: "month",
      date_label: "maggio–dicembre 2026",
    };
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true, json: async () => ({ events: [event], total: 1 }),
    });
    const result = await fetchLocalEvents(
      { city: "Udine", lat: 46.06, lon: 13.23 },
      { apiBase: PILOT_EVENTS_API, fetchImpl },
    );
    expect(result.events[0].date).toBe("maggio–dicembre 2026");
    expect(result.events[0].date_precision).toBe("month");
  });

  it("projects an old pilot programme only after validating the complete raw catalog", async () => {
    const apiBase = PILOT_EVENTS_API;
    const events = ["17", "18"].map((day) => ({
      distance_km: 1,
      event_city: "Pordenone",
      source: "Pordenonelegge",
      start_date: `2026-09-${day}`,
      title: `Incontro ${day}`,
      url: `https://www.pordenonelegge.it/eventi/${day}`,
      venue: `Sala ${day}`,
    }));
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ events, next_offset: null, snapshot: "edition", total: 2 }),
    });

    const result = await fetchLocalEvents(
      { city: "Pordenone", lat: 45.9567, lon: 12.6605 },
      { apiBase, fetchImpl },
    );

    expect(result.events).toHaveLength(1);
    expect(result.events[0]).toMatchObject({
      active_session_count: 2,
      programme_id: "pordenonelegge-2026",
      title: "Pordenonelegge 2026",
    });
    expect(result.events[0]).not.toHaveProperty("session_count");
    expect(result.raw).toMatchObject({ raw_total: 2, total: 1 });
  });

  it("builds an encoded request for one official event detail", () => {
    expect(buildLocalEventDetailUrl(
      {
        source: "TurismoFVG",
        url: "https://www.turismofvg.it/eventi/armonie-in-citta?ignored=no",
      },
      { apiBase: "/api/" },
    )).toBe(
      "/api/local/events/detail?source=TurismoFVG&url=https%3A%2F%2Fwww.turismofvg.it%2Feventi%2Farmonie-in-citta%3Fignored%3Dno",
    );
  });

  it("promotes the home request limit to the full canonical collection", () => {
    expect(getEventsRequestLimit(HOME_EVENTS_LIMIT)).toBe(FULL_EVENTS_LIMIT);
    expect(buildLocalEventsUrl("Pordenone", { apiBase: "/api", limit: HOME_EVENTS_LIMIT })).toBe(
      "/api/local/events?city=Pordenone&limit=100",
    );
  });

  it("adds finite coordinates to the local events request", () => {
    const url = buildLocalEventsUrl(
      {
        city: "Fontanafredda",
        displayName: "Vigonovo",
        lat: "45.9892",
        lon: "12.5473",
        locality: { id: "irdat:vigonovo", name: "Vigonovo" },
        municipality: { istatCode: "093022", name: "Fontanafredda" },
      },
      { apiBase: "/api", limit: FULL_EVENTS_LIMIT },
    );

    expect(url).toBe(
      "/api/local/events?city=Fontanafredda&limit=100&lat=45.9892&lon=12.5473",
    );
  });

  it("omits coordinates unless both values are finite", () => {
    expect(coerceFiniteNumber("46.1")).toBe(46.1);
    expect(coerceFiniteNumber("abc")).toBe(null);
    expect(buildLocalEventsUrl({ city: "Udine", lat: 46.06, lon: "no" }, { apiBase: "/api" })).toBe(
      "/api/local/events?city=Udine&limit=100",
    );
  });

  it("normalizes backend refresh states", () => {
    expect(normalizeLocalEventsPayload({
      events: [],
      cache: { status: "refreshing", event_contract_version: "canonical-events-v2" },
    })).toMatchObject({
      events: [],
      total: 0,
      cacheStatus: "refreshing",
      contractVersion: "canonical-events-v2",
      isRefreshing: true,
      shouldRetry: true,
    });

    expect(
      normalizeLocalEventsPayload({ events: [{ id: "e1" }], cache: { status: "partial" } }, { retry: 20 }),
    ).toMatchObject({
      events: [{ id: "e1" }],
      total: 1,
      isPartial: true,
      shouldRetry: false,
    });
  });

  it("fetches and normalizes events through an injected fetch", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ events: [{ id: "event-1" }], cache: { status: "fresh" } }),
    });

    const payload = await fetchLocalEvents("Udine", { apiBase: "/api", fetchImpl });

    expect(fetchImpl).toHaveBeenCalledWith("/api/local/events?city=Udine&limit=100");
    expect(payload.events).toEqual([{ id: "event-1" }]);
    expect(payload.cacheStatus).toBe("fresh");
  });

  it("fetches a verified event description through an injected fetch", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        source: "TurismoFVG",
        url: "https://www.turismofvg.it/eventi/armonie-in-citta",
        description: "  Descrizione ufficiale.  ",
        event_city: "Udine",
        venue: "Teatro Palamostre",
        address: "Piazzale Paolo Diacono, 21",
      }),
    });

    const payload = await fetchLocalEventDetail(
      {
        source: "TurismoFVG",
        url: "https://www.turismofvg.it/eventi/armonie-in-citta",
      },
      { apiBase: "/api", fetchImpl },
    );

    expect(fetchImpl).toHaveBeenCalledWith(
      "/api/local/events/detail?source=TurismoFVG&url=https%3A%2F%2Fwww.turismofvg.it%2Feventi%2Farmonie-in-citta",
    );
    expect(payload.description).toBe("Descrizione ufficiale.");
    expect(payload.eventCity).toBe("Udine");
    expect(payload.venue).toBe("Teatro Palamostre");
    expect(payload.address).toBe("Piazzale Paolo Diacono, 21");
  });

  it("uses the verified pilot record for preview details without a second request", async () => {
    const fetchImpl = vi.fn();
    const payload = await fetchLocalEventDetail({
      raw: {
        address: "Piazza XX Settembre",
        description: "  Dettaglio già incluso nel catalogo pilota.  ",
        event_city: "Pordenone",
        venue: "Centro città",
      },
      source: "TurismoFVG",
      url: "https://www.turismofvg.it/eventi/esempio",
    }, {
      apiBase: LOCAL_PILOT_EVENTS_API,
      fetchImpl,
    });

    expect(fetchImpl).not.toHaveBeenCalled();
    expect(payload).toMatchObject({
      address: "Piazza XX Settembre",
      description: "Dettaglio già incluso nel catalogo pilota.",
      eventCity: "Pordenone",
      venue: "Centro città",
    });
  });
});
