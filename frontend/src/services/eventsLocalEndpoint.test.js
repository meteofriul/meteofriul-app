import { afterEach, expect, it, vi } from "vitest";

afterEach(() => { vi.unstubAllEnvs(); vi.resetModules(); });

it.each([0, 2])("keeps local TEST endpoint isolation and catalog health across online/offline refresh (%s events)", async (count) => {
  vi.stubEnv("VITE_LOCAL_EVENTS_API_BASE", "http://127.0.0.1:8784/api");
  vi.resetModules();
  const api = await import("./eventsApi");
  const { loadEventsData, readInitialEventsData } = await import("../features/events/eventsDataController");
  const apiBase = api.resolveEventsApiBase({ localPilot: true, nativeAndroid: true });
  expect(apiBase).toBe("http://127.0.0.1:8784/api");
  expect(api.PRODUCTION_EVENTS_API).toBe("");
  const location = { city: "Udine", lat: 46.07, lon: 13.23 };
  const values = new Map();
  const storage = { getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value), removeItem: (key) => values.delete(key) };
  const now = () => Date.parse("2026-10-15T12:00:00Z");
  const health = { catalog_status: "degraded", snapshot: "local-snapshot",
    source_status: { TurismoFVG: "partial" }, source_failure_tags: { TurismoFVG: "quarantined_cards" } };
  const card = (id) => ({ title: `Evento ${id}`, url: `https://example.test/${id}`,
    source: "TurismoFVG", event_city: "Udine", start_date: "2026-10-15", end_date: "2026-10-15", time: "17:00" });
  const fetchImpl = vi.fn().mockResolvedValueOnce({ ok: true, json: async () => ({
    ...health, events: count ? [card(1)] : [], total: count, next_offset: count ? 1 : null,
  }) });
  if (count) fetchImpl.mockResolvedValueOnce({ ok: true, json: async () => ({
    ...health, events: [card(2)], total: count, next_offset: null,
  }) });
  const options = { storage, now, pilot: true,
    eventsFetcher: (place, opts) => api.fetchLocalEvents(place, { ...opts, apiBase, fetchImpl }) };
  const online = await loadEventsData(location, options);
  expect(online).toMatchObject({ status: "degraded", isDegraded: true, total: count, shouldRetry: false });
  expect(online.items).toHaveLength(count);
  expect(readInitialEventsData(location, { storage, now })).toMatchObject({
    fromCache: true, status: "degraded", catalogHealth: online.catalogHealth,
  });
  if (count) expect(fetchImpl.mock.calls[1][0]).toContain("snapshot=local-snapshot");
  fetchImpl.mockRejectedValueOnce(new Error("local API offline"));
  const offline = await loadEventsData(location, options);
  expect(offline).toMatchObject({ status: "stale", fromCache: true,
    catalogHealth: online.catalogHealth, items: online.items });
  fetchImpl.mockResolvedValueOnce({ ok: true, json: async () => ({
    events: [], total: 0, next_offset: null, snapshot: "reconnected",
    catalog_status: "complete", source_status: { TurismoFVG: "fresh" }, source_failure_tags: {},
  }) });
  const reconnected = await loadEventsData(location, options);
  expect(reconnected).toMatchObject({ status: "fresh", isDegraded: false, fromCache: false,
    items: [], catalogHealth: { status: "complete", sourceFailureTags: {} } });
  expect(fetchImpl).toHaveBeenCalledTimes((count ? 2 : 1) + 2);
  for (const [url] of fetchImpl.mock.calls) expect(new URL(url).origin).toBe("http://127.0.0.1:8784");
});
