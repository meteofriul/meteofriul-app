import { describe, expect, it, vi } from "vitest";

import { FULL_EVENTS_LIMIT, HOME_EVENTS_LIMIT } from "../../services/eventsApi";
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
