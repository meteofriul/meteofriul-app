import { describe, expect, it, vi } from "vitest";
import {
  getCommunityUnreadCount,
  markCommunitySnapshotSeen,
  readCommunitySeenState,
} from "../features/live/communityUnreadState";

import {
  createCommunityNavigationSnapshot,
  createEventsNavigationSnapshot,
  getAppRouteViewKey,
  getCommunityNavigationTotal,
  getEventsNavigationPeriod,
  getEventsNavigationTotal,
  getPilotWhyRequestId,
  loadAndCommitEventsRouteData,
  readEventsNavigationSnapshot,
  readEventsRouteInitialState,
  reconcileCommunityNavigationSnapshot,
  reconcileEventsNavigationSnapshot,
} from "./appRouteRuntime";

function deferred() {
  let resolve;
  const promise = new Promise(next => { resolve = next; });
  return { promise, resolve };
}

const UNREAD_NOW = 1_800_000_000_000;
const UNREAD_HOUR = 60 * 60 * 1000;
const unreadTorino = { city: "Torino", lat: 45.0703, lon: 7.6869 };
const unreadPordenone = { city: "Pordenone", lat: 45.9567, lon: 12.6605 };

function unreadModel(ids, { location = unreadTorino, status = "fresh", expiresAt = UNREAD_NOW + UNREAD_HOUR } = {}) {
  const group = {
    ...location,
    id: "rain-group",
    groupId: "rain-group",
    count: ids.length,
    expiresAt,
    contributions: ids.map((id) => ({ id, expiresAt, sourceKey: `source-${id}` })),
    reportIds: ids,
  };
  return { enabled: true, status: { id: status }, items: [group], markers: [group] };
}

describe("pilot community unread navigation", () => {
  it("adopts a new observation ID even when the aggregate count has not changed", () => {
    const options = { now: UNREAD_NOW };
    const current = createCommunityNavigationSnapshot(unreadTorino, unreadModel(["old"]), options);
    const seen = markCommunitySnapshotSeen(readCommunitySeenState({ storage: null, ...options }), current.unread, options);
    const next = reconcileCommunityNavigationSnapshot(current, unreadTorino, unreadTorino, unreadModel(["new"]), options);

    expect(next).not.toBe(current);
    expect(next.total).toBe(current.total);
    expect(getCommunityUnreadCount(next.unread, seen, options)).toBe(1);
    expect(reconcileCommunityNavigationSnapshot(next, unreadTorino, unreadTorino, unreadModel(["new"]), options)).toBe(next);
  });

  it("keeps a renewed ID read beyond its original expiry without confusing it with a new contribution", () => {
    const options = { now: UNREAD_NOW };
    const current = createCommunityNavigationSnapshot(unreadTorino, unreadModel(["same"]), options);
    const seen = markCommunitySnapshotSeen(readCommunitySeenState({ storage: null, ...options }), current.unread, options);
    const renewed = reconcileCommunityNavigationSnapshot(current, unreadTorino, unreadTorino, unreadModel(["same"], {
      expiresAt: UNREAD_NOW + 2 * UNREAD_HOUR,
    }), { now: UNREAD_NOW + UNREAD_HOUR });

    expect(renewed).not.toBe(current);
    expect(renewed.unread.entries[0].expiresAt).toBe(UNREAD_NOW + 2 * UNREAD_HOUR);
    expect(getCommunityUnreadCount(renewed.unread, seen, { now: UNREAD_NOW + UNREAD_HOUR })).toBe(0);
  });

  it("does not turn a FVG QA total into Torino news", () => {
    const result = createCommunityNavigationSnapshot(unreadTorino, unreadModel(["fvg-a", "fvg-b"], {
      location: unreadPordenone,
    }), { now: UNREAD_NOW });
    expect(result.total).toBe(2);
    expect(result.unread).toMatchObject({ ready: true, entries: [] });
  });

  it("rejects a late response and an acknowledgement scoped to the prior municipality", () => {
    const options = { now: UNREAD_NOW };
    const current = createCommunityNavigationSnapshot(unreadTorino, unreadModel(["torino"]), options);
    const late = reconcileCommunityNavigationSnapshot(current, unreadTorino, unreadPordenone,
      unreadModel(["fvg"], { location: unreadPordenone }), options);
    const elsewhere = createCommunityNavigationSnapshot(unreadPordenone,
      unreadModel(["fvg"], { location: unreadPordenone }), options);
    const seen = markCommunitySnapshotSeen(readCommunitySeenState({ storage: null, ...options }), elsewhere.unread, options);

    expect(late).toBe(current);
    expect(getCommunityNavigationTotal(elsewhere, unreadTorino)).toBeNull();
    expect(getCommunityUnreadCount(current.unread, seen, options)).toBe(1);
  });

  it.each(["loading", "cache", "stale", "error", "offline"])(
    "does not acknowledge observations from a %s snapshot", (status) => {
      const options = { now: UNREAD_NOW };
      const state = readCommunitySeenState({ storage: null, ...options });
      const result = createCommunityNavigationSnapshot(unreadTorino, unreadModel(["a"], { status }), options);
      expect(result.unread.ready).toBe(false);
      expect(markCommunitySnapshotSeen(state, result.unread, options)).toBe(state);
      const fresh = createCommunityNavigationSnapshot(unreadTorino, unreadModel(["a"]), options);
      expect(fresh.unread.ready).toBe(true);
      expect(getCommunityUnreadCount(fresh.unread, state, options)).toBe(1);
    },
  );

  it.each(["loading", "cache", "stale", "error", "offline"])(
    "retains verified unread IDs when a same-scope %s render arrives", (status) => {
      const options = { now: UNREAD_NOW };
      const current = createCommunityNavigationSnapshot(unreadTorino, unreadModel(["a"]), options);
      const next = reconcileCommunityNavigationSnapshot(current, unreadTorino, unreadTorino,
        unreadModel(["a", "cached-new"], { status }), options);
      expect(next).toBe(current);
      expect(getCommunityUnreadCount(next.unread, null, options)).toBe(1);
      expect(getCommunityUnreadCount(next.unread, null, { now: UNREAD_NOW + UNREAD_HOUR })).toBe(0);
      const fresh = reconcileCommunityNavigationSnapshot(next, unreadTorino, unreadTorino,
        unreadModel(["a", "fresh-new"]), options);
      expect(getCommunityUnreadCount(fresh.unread, null, options)).toBe(2);
    },
  );

  it("does not retain a previously verified total across location changes", () => {
    const options = { now: UNREAD_NOW };
    const current = createCommunityNavigationSnapshot(unreadTorino, unreadModel(["a"]), options);
    const next = reconcileCommunityNavigationSnapshot(current, unreadPordenone, unreadPordenone,
      unreadModel(["fvg-cached"], { location: unreadPordenone, status: "cache" }), options);
    expect(next).not.toBe(current);
    expect(next.unread.ready).toBe(false);
    expect(getCommunityUnreadCount(next.unread, null, options)).toBe(0);
  });

  it("passes personal receipts and visibility guards into navigation snapshots", () => {
    const result = createCommunityNavigationSnapshot(unreadTorino, unreadModel(["mine", "retired", "other"]), {
      now: UNREAD_NOW,
      personalState: {
        reports: [{ reportId: "mine", sourceKey: "source-mine" }],
        reportWithdrawals: [{ reportId: "retired", expiresAt: UNREAD_NOW + UNREAD_HOUR }],
      },
    });
    expect(result.unread.entries.map((entry) => entry.id)).toEqual(["other"]);
  });

  it("a fresh but expired contribution is not unread despite the aggregate count", () => {
    const result = createCommunityNavigationSnapshot(unreadTorino, unreadModel(["expired"], {
      expiresAt: UNREAD_NOW,
    }), { now: UNREAD_NOW });
    expect(result.total).toBe(1);
    expect(result.unread.entries).toEqual([]);
  });
});

describe("App route runtime", () => {
  it("keeps the active community report total tied to its weather location", () => {
    const pordenone = { city: "Pordenone", lat: 45.9567, lon: 12.6605 };
    const udine = { city: "Udine", lat: 46.0635, lon: 13.2358 };
    const community = {
      enabled: true,
      items: [{ count: 3, id: "rain" }, { count: 1, id: "wind" }],
    };
    const snapshot = createCommunityNavigationSnapshot(pordenone, community);

    expect(snapshot).toEqual(expect.objectContaining({ total: 4 }));
    expect(getCommunityNavigationTotal(snapshot, pordenone)).toBe(4);
    expect(getCommunityNavigationTotal(snapshot, udine)).toBeNull();
    expect(createCommunityNavigationSnapshot(pordenone, { enabled: false, items: community.items }))
      .toBeNull();
  });

  it("ignores a late community snapshot from the previous weather location", () => {
    const pordenone = { city: "Pordenone" };
    const udine = { city: "Udine" };
    const current = createCommunityNavigationSnapshot(pordenone, {
      enabled: true,
      items: [{ count: 2 }],
    });
    const late = reconcileCommunityNavigationSnapshot(
      current,
      udine,
      pordenone,
      { enabled: true, items: [{ count: 7 }] },
    );
    const next = reconcileCommunityNavigationSnapshot(
      late,
      udine,
      udine,
      { enabled: true, items: [{ count: 1 }, { count: 4 }] },
    );

    expect(late).toBe(current);
    expect(getCommunityNavigationTotal(late, udine)).toBeNull();
    expect(getCommunityNavigationTotal(next, udine)).toBe(5);
  });

  it("keeps a complete events total tied to its location", () => {
    const pordenone = { city: "Pordenone", lat: 45.9567, lon: 12.6605 };
    const snapshot = createEventsNavigationSnapshot(pordenone, {
      fromCache: false,
      items: [{ id: "event-1", date_label: "Oggi" }, { id: "event-2", date_label: "Oggi" }],
      loadedLimit: 100,
      status: "fresh",
      total: 2,
    });

    expect(snapshot).toEqual(expect.objectContaining({ catalogTotal: 2, period: "today", total: 2 }));
    expect(getEventsNavigationTotal(snapshot, pordenone)).toBe(2);
    expect(getEventsNavigationPeriod(snapshot, pordenone)).toBe("today");
    expect(getEventsNavigationTotal(snapshot, { city: "Udine" })).toBeNull();
    expect(getEventsNavigationTotal(snapshot, { ...pordenone, eventsRadius: 50 })).toBeNull();
    expect(getEventsNavigationPeriod(snapshot, { ...pordenone, eventsRadius: 5 })).toBeNull();
    expect(reconcileEventsNavigationSnapshot(null, { ...pordenone, eventsRadius: 5 }, pordenone, {
      items: [{ id: "old-wide-result", date_label: "Oggi" }], loadedLimit: 100, status: "fresh", total: 1,
    })).toBeNull();
  });

  it("accepts a verified cached total while rejecting incomplete candidates", () => {
    const location = { city: "Pordenone" };
    const cached = {
      fromCache: true,
      isRefreshing: true,
      items: [{ id: "cached-event", date_label: "Oggi" }],
      loadedLimit: 100,
      status: "refreshing",
      total: 1,
    };
    const partial = {
      fromCache: false,
      isPartial: true,
      items: [{ id: "partial-event", date_label: "Oggi" }],
      loadedLimit: 100,
      status: "partial",
      total: 1,
    };
    const emptyLoading = {
      fromCache: false,
      isRefreshing: true,
      items: [],
      loadedLimit: 0,
      status: "refreshing",
      total: 0,
    };
    const oldHomeSubset = {
      fromCache: true,
      items: Array.from({ length: 8 }, (_, index) => ({ id: `old-${index}`, date_label: "Oggi" })),
      loadedLimit: 8,
      status: "cache",
      total: 8,
    };
    const mismatchedTotal = {
      fromCache: true,
      items: [{ id: "only-loaded-event", date_label: "Oggi" }],
      loadedLimit: 100,
      status: "cache",
      total: 2,
    };
    const unavailable = {
      cacheStatus: "source_unavailable",
      fromCache: false,
      items: [],
      loadedLimit: 100,
      status: "fresh",
      total: 0,
    };

    expect(createEventsNavigationSnapshot(location, cached)?.total).toBe(1);
    expect(createEventsNavigationSnapshot(location, partial)).toBeNull();
    expect(createEventsNavigationSnapshot(location, emptyLoading)).toBeNull();
    expect(createEventsNavigationSnapshot(location, oldHomeSubset)).toBeNull();
    expect(createEventsNavigationSnapshot(location, mismatchedTotal)).toBeNull();
    expect(createEventsNavigationSnapshot(location, unavailable)).toBeNull();
  });

  it("hides the old locality and rejects its late response before adopting the new one", () => {
    const pordenone = { city: "Pordenone" };
    const udine = { city: "Udine" };
    const pordenoneState = {
      items: Array.from({ length: 2 }, (_, index) => ({ id: `pordenone-${index}`, date_label: "Oggi" })),
      loadedLimit: 100,
      status: "fresh",
      total: 2,
    };
    const udineState = {
      items: Array.from({ length: 7 }, (_, index) => ({ id: `udine-${index}`, date_label: "Oggi" })),
      loadedLimit: 100,
      status: "fresh",
      total: 7,
    };
    const pordenoneSnapshot = reconcileEventsNavigationSnapshot(
      null,
      pordenone,
      pordenone,
      pordenoneState,
    );
    const afterLatePordenone = reconcileEventsNavigationSnapshot(
      pordenoneSnapshot,
      udine,
      pordenone,
      pordenoneState,
    );
    const udineSnapshot = reconcileEventsNavigationSnapshot(
      afterLatePordenone,
      udine,
      udine,
      udineState,
    );

    expect(getEventsNavigationTotal(pordenoneSnapshot, udine)).toBeNull();
    expect(afterLatePordenone).toBe(pordenoneSnapshot);
    expect(getEventsNavigationTotal(udineSnapshot, udine)).toBe(7);
  });

  it("keeps the previous total when Home reports that its event source is unavailable", () => {
    const location = { city: "Pordenone" };
    const current = createEventsNavigationSnapshot(location, {
      items: [{ id: "cached-event", date_label: "Oggi" }],
      loadedLimit: 100,
      status: "cache",
      total: 1,
    });
    const next = reconcileEventsNavigationSnapshot(current, location, location, {
      cacheStatus: "source_unavailable",
      items: [],
      loadedLimit: 100,
      status: "fresh",
      total: 0,
    });

    expect(next).toBe(current);
  });

  it("reads an existing events cache through the injected synchronous reader once", () => {
    const location = { city: "Pordenone" };
    const readInitialState = vi.fn(() => ({
      fromCache: true,
      items: [],
      loadedLimit: 100,
      status: "cache",
      total: 0,
    }));

    expect(readEventsNavigationSnapshot(location, { readInitialState }))
      .toEqual(expect.objectContaining({ total: 0 }));
    expect(readInitialState).toHaveBeenCalledExactlyOnceWith(location);
  });

  it("forwards a selected Why only for the current Discover visit", () => {
    expect(getPilotWhyRequestId("discover", { whyId: "  why-2026-09-08  " }))
      .toBe("why-2026-09-08");
    expect(getPilotWhyRequestId("home", { whyId: "why-2026-09-08" })).toBe("");
    expect(getPilotWhyRequestId("discover")).toBe("");
  });

  it("remounts Events for a new location and initializes without the previous location items", () => {
    const pordenone = { city: "Pordenone", lat: 45.9567, lon: 12.6605 };
    const udine = { city: "Udine", lat: 46.0635, lon: 13.2358 };
    const pordenoneState = { items: [{ id: "pordenone-event" }], status: "fresh" };
    const loadingState = { items: [], status: "refreshing" };
    const readInitialState = vi.fn(location => (
      location.city === "Pordenone" ? pordenoneState : null
    ));

    expect(getAppRouteViewKey("events", udine))
      .not.toBe(getAppRouteViewKey("events", pordenone));
    expect(readEventsRouteInitialState(udine, {
      createLoadingState: () => loadingState,
      readInitialState,
    })).toBe(loadingState);
    expect(loadingState.items).not.toContainEqual({ id: "pordenone-event" });
    expect(readInitialState).toHaveBeenCalledExactlyOnceWith(udine);
  });

  it("remounts Events, but not editorial routes, when the weather location changes", () => {
    const pordenone = { city: "Pordenone", region: "Friuli Venezia Giulia" };
    const roma = { city: "Roma", region: "Lazio", countryCode: "IT" };
    const editorial = { city: "Udine", region: "Friuli Venezia Giulia" };

    expect(getAppRouteViewKey("events", pordenone, editorial))
      .not.toBe(getAppRouteViewKey("events", roma, editorial));
    expect(getAppRouteViewKey("discover", pordenone, editorial))
      .toBe(getAppRouteViewKey("discover", roma, editorial));
    expect(getAppRouteViewKey("weather", pordenone, editorial))
      .not.toBe(getAppRouteViewKey("weather", roma, editorial));
  });

  it("does not let a late response for the old location replace the new location", async () => {
    const oldRequest = deferred();
    const commits = [];
    let oldRequestIsCurrent = true;
    const onCommit = state => commits.push(state);
    const pordenoneState = { items: [{ id: "pordenone-event" }] };
    const udineState = { items: [{ id: "udine-event" }] };

    const pendingOldRequest = loadAndCommitEventsRouteData({ city: "Pordenone" }, {
      isCurrent: () => oldRequestIsCurrent,
      loadData: () => oldRequest.promise,
      onCommit,
    });
    oldRequestIsCurrent = false;
    await loadAndCommitEventsRouteData({ city: "Udine" }, {
      loadData: async () => udineState,
      onCommit,
    });
    oldRequest.resolve(pordenoneState);
    await pendingOldRequest;

    expect(commits).toEqual([udineState]);
  });
});
