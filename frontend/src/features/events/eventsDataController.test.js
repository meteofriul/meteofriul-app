import { describe, expect, it, vi } from "vitest";

import {
  fetchLocalEvents, FULL_EVENTS_LIMIT, HOME_EVENTS_LIMIT,
  LOCAL_PILOT_EVENTS_API, PILOT_EVENTS_API,
} from "../../services/eventsApi";
import {
  createEventsCachePayload,
  EVENTS_DEVICE_CACHE_MAX_AGE_MS,
  getEventsCacheKey,
} from "../../services/eventsCache";
import {
  loadEventsData,
  readInitialEventsData,
} from "./eventsDataController";

const location = { city: "Pordenone", lat: 45.9569, lon: 12.6605 };
const NOW = 2_000_000_000;

function createStorage(initial = {}) {
  const values = new Map(Object.entries(initial));

  return {
    getItem: vi.fn((key) => values.get(key) || null),
    removeItem: vi.fn((key) => values.delete(key)),
    setItem: vi.fn((key, value) => values.set(key, value)),
  };
}

describe("events data controller", () => {
  it("pilot keeps visible cached events when sources are unavailable", async () => {
    const writer = vi.fn();
    const state = await loadEventsData(location, {
      pilot: true,
      eventsCacheReader: () => ({ data: createEventsCachePayload([{ id: 'saved' }]) }),
      eventsCacheWriter: writer,
      eventsFetcher: async () => ({ events: [], cacheStatus: 'source_unavailable' }),
    });
    expect(state.items).toEqual([{ id: 'saved' }]);
    expect(state.status).toBe('stale');
    expect(writer).not.toHaveBeenCalled();
  });

  it("pilot replaces a small partial cache with a larger partial response", async () => {
    const writer = vi.fn();
    const state = await loadEventsData(location, {
      pilot: true,
      eventsCacheReader: () => ({ data: createEventsCachePayload([{ id: 'one' }], 'v2') }),
      eventsCacheWriter: writer,
      eventsFetcher: async () => ({ events: [{ id: 'one' }, { id: 'two' }], contractVersion: 'v2', isPartial: true, shouldRetry: true }),
    });
    expect(state.items).toHaveLength(2);
    expect(writer).toHaveBeenCalledOnce();
    expect(state.shouldRetry).toBe(true);
  });
  it("hydrates the Events page from cache before calling the network", () => {
    const state = readInitialEventsData(location, {
      eventsCacheReader: vi.fn().mockReturnValue({
        data: createEventsCachePayload([{ id: "cached-event" }]),
        limit: FULL_EVENTS_LIMIT,
      }),
    });

    expect(state).toMatchObject({
      fromCache: true,
      items: [{ id: "cached-event" }],
      loadedLimit: FULL_EVENTS_LIMIT,
      status: "cache",
    });
  });

  it("fetches the full events collection and writes the canonical cache", async () => {
    const eventsCacheWriter = vi.fn();
    const state = await loadEventsData(location, {
      eventsCacheReader: vi.fn().mockReturnValue(null),
      eventsCacheWriter,
      eventsFetcher: vi.fn().mockResolvedValue({
        events: [{ id: "fresh-event" }],
        total: 1,
      }),
    });

    expect(eventsCacheWriter).toHaveBeenCalledWith(location, [{ id: "fresh-event" }], expect.objectContaining({
      limit: FULL_EVENTS_LIMIT,
    }));
    expect(state).toMatchObject({
      items: [{ id: "fresh-event" }],
      loadedLimit: FULL_EVENTS_LIMIT,
      status: "fresh",
    });
  });

  it.each([false, true])("clears populated cache after a valid empty catalog (pilot=%s)", async (pilot) => {
    const storage = createStorage({
      [getEventsCacheKey(location, FULL_EVENTS_LIMIT)]: JSON.stringify({
        data: createEventsCachePayload([{ id: "removed-event" }], "pilot-events-v2-programmes"),
        savedAt: NOW - 1_000,
      }),
      [getEventsCacheKey(location, HOME_EVENTS_LIMIT)]: JSON.stringify({
        data: createEventsCachePayload([{ id: "old-home-event" }]),
        savedAt: NOW - 1_000,
      }),
    });
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        events: [], total: 0, next_offset: null, snapshot: "empty-valid",
        status: "ready", catalog_status: "complete",
        source_status: { Azalea: "fresh" }, source_failure_tags: {},
      }),
    });
    const state = await loadEventsData(location, {
      pilot, storage, now: () => NOW,
      eventsFetcher: (place, options) => fetchLocalEvents(place, {
        ...options, apiBase: pilot ? LOCAL_PILOT_EVENTS_API : PILOT_EVENTS_API, fetchImpl,
      }),
    });
    expect(state).toMatchObject({ items: [], total: 0, fromCache: false, status: "fresh" });
    const saved = JSON.parse(storage.getItem(getEventsCacheKey(location, FULL_EVENTS_LIMIT)));
    expect(saved).toMatchObject({ savedAt: NOW, data: { events: [], total: 0 } });
    expect(readInitialEventsData(location, { storage, now: () => NOW }).items).toEqual([]);
    const offline = await loadEventsData(location, {
      pilot, storage, now: () => NOW + 1,
      eventsFetcher: async () => { throw new Error("offline"); },
    });
    expect(offline).toMatchObject({ items: [], fromCache: true, status: "stale" });
    expect(fetchImpl).toHaveBeenCalledOnce();
  });

  it.each([false, true])("preserves degraded health for empty expired-source responses and cached reopen (pilot=%s)", async (pilot) => {
    // Expired source data is removed, while EV-04 keeps degradation explicit.
    const storage = createStorage({
      [getEventsCacheKey(location, FULL_EVENTS_LIMIT)]: JSON.stringify({
        data: createEventsCachePayload([{ id: "last-visible-event" }], "pilot-events-v2-programmes"),
        savedAt: NOW - 1_000,
      }),
    });
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        events: [], total: 0, next_offset: null, snapshot: "sources-expired",
        status: "ready", catalog_status: "degraded",
        source_status: { Azalea: "fresh" }, source_failure_tags: { Azalea: "source_expired" },
      }),
    });
    let received;
    const state = await loadEventsData(location, {
      pilot, storage, now: () => NOW,
      eventsFetcher: async (place, options) => {
        received = await fetchLocalEvents(place, {
          ...options, apiBase: pilot ? LOCAL_PILOT_EVENTS_API : PILOT_EVENTS_API, fetchImpl,
        });
        return received;
      },
    });
    expect(received).toMatchObject({ cacheStatus: "degraded", isPartial: false,
      raw: { catalog_status: "degraded", source_failure_tags: { Azalea: "source_expired" } } });
    expect(state).toMatchObject({ items: [], total: 0, status: "degraded", isDegraded: true, fromCache: false });
    expect(JSON.parse(storage.getItem(getEventsCacheKey(location, FULL_EVENTS_LIMIT))))
      .toMatchObject({ savedAt: NOW, data: { events: [], total: 0,
        catalogHealth: { status: "degraded", sourceFailureTags: { Azalea: "source_expired" } } } });
    expect(readInitialEventsData(location, { storage, now: () => NOW }))
      .toMatchObject({ items: [], status: "degraded", isDegraded: true, fromCache: true });
  });

  it("refreshes even when a fresh cache entry exists", async () => {
    const eventsCacheWriter = vi.fn();
    const state = await loadEventsData(location, {
      eventsCacheReader: vi.fn().mockReturnValue({
        data: createEventsCachePayload([]),
        limit: FULL_EVENTS_LIMIT,
      }),
      eventsCacheWriter,
      eventsFetcher: vi.fn().mockResolvedValue({
        events: [{ id: "fresh-event" }],
        total: 1,
      }),
    });

    expect(eventsCacheWriter).toHaveBeenCalledWith(location, [{ id: "fresh-event" }], expect.objectContaining({
      limit: FULL_EVENTS_LIMIT,
    }));
    expect(state).toMatchObject({
      fromCache: false,
      items: [{ id: "fresh-event" }],
      status: "fresh",
    });
  });

  it("keeps cached events visible when the backend is still refreshing", async () => {
    const eventsCacheWriter = vi.fn();
    const state = await loadEventsData(location, {
      eventsCacheReader: vi.fn().mockReturnValue({
        data: createEventsCachePayload([{ id: "cached-event" }]),
        limit: HOME_EVENTS_LIMIT,
      }),
      eventsCacheWriter,
      eventsFetcher: vi.fn().mockResolvedValue({
        cacheStatus: "refreshing",
        events: [],
        isRefreshing: true,
        shouldRetry: true,
      }),
      force: true,
      retry: 2,
    });

    expect(eventsCacheWriter).not.toHaveBeenCalled();
    expect(state).toMatchObject({
      fromCache: true,
      isRefreshing: true,
      items: [{ id: "cached-event" }],
      loadedLimit: HOME_EVENTS_LIMIT,
      retry: 2,
      shouldRetry: true,
      status: "refreshing",
    });
  });

  it("replaces a stale contract cache with a non-empty canonical partial response", async () => {
    const eventsCacheWriter = vi.fn();
    const state = await loadEventsData(location, {
      eventsCacheReader: vi.fn().mockReturnValue({
        data: createEventsCachePayload([{ id: "old-duplicate" }], "canonical-events-v1"),
        limit: FULL_EVENTS_LIMIT,
      }),
      eventsCacheWriter,
      eventsFetcher: vi.fn().mockResolvedValue({
        cacheStatus: "partial",
        contractVersion: "canonical-events-v2",
        events: [{ id: "canonical-event" }],
        isPartial: true,
        isRefreshing: false,
        shouldRetry: true,
      }),
    });

    expect(eventsCacheWriter).toHaveBeenCalledWith(
      location,
      [{ id: "canonical-event" }],
      expect.objectContaining({
        contractVersion: "canonical-events-v2",
        limit: FULL_EVENTS_LIMIT,
      }),
    );
    expect(state).toMatchObject({
      contractVersion: "canonical-events-v2",
      fromCache: false,
      items: [{ id: "canonical-event" }],
      isPartial: true,
    });
  });

  it("keeps cached events visible when a forced refresh fails", async () => {
    const state = await loadEventsData(location, {
      eventsCacheReader: vi.fn().mockReturnValue({
        data: createEventsCachePayload([{ id: "cached-event" }]),
        limit: FULL_EVENTS_LIMIT,
      }),
      eventsFetcher: vi.fn().mockRejectedValue(new Error("Risposta eventi non valida")),
      force: true,
    });

    expect(state).toMatchObject({
      error: "Risposta eventi non valida",
      fromCache: true,
      items: [{ id: "cached-event" }],
      status: "stale",
    });
  });

  it("does not revive expired events when the endpoint is offline", async () => {
    const storage = createStorage({
      [getEventsCacheKey(location, FULL_EVENTS_LIMIT)]: JSON.stringify({
        data: createEventsCachePayload([{ id: "expired-event" }]),
        savedAt: NOW - EVENTS_DEVICE_CACHE_MAX_AGE_MS - 1,
      }),
    });

    const state = await loadEventsData(location, {
      eventsFetcher: vi.fn().mockRejectedValue(new Error("offline")),
      now: () => NOW,
      storage,
    });

    expect(state).toMatchObject({
      error: "offline",
      fromCache: false,
      items: [],
      status: "error",
    });
  });
});
