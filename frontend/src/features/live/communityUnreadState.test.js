import { describe, expect, it, vi } from "vitest";
import {
  COMMUNITY_SEEN_MAX_ENTRIES,
  COMMUNITY_SEEN_MAX_LOCATIONS,
  COMMUNITY_SEEN_STORAGE_KEY,
  COMMUNITY_SEEN_TTL_MS,
  createCommunityUnreadSnapshot,
  getCommunityUnreadCount,
  getCommunityUnreadLocationKey,
  markCommunitySnapshotSeen,
  readCommunitySeenState,
  writeCommunitySeenState,
} from "./communityUnreadState";

const NOW = 1_800_000_000_000;
const HOUR = 60 * 60 * 1000;
const torino = { city: "Torino", lat: 45.0703, lon: 7.6869 };
const pordenone = { city: "Pordenone", lat: 45.9564, lon: 12.6606 };
const empty = () => readCommunitySeenState({ storage: null, now: NOW });
const contribution = (id, extra = {}) => ({ id, expiresAt: NOW + HOUR, sourceKey: `source-${id}`, ...extra });
const group = (ids = ["report-a"], extra = {}) => ({
  id: "group-a", groupId: "group-a", ...torino, count: ids.length,
  expiresAt: NOW + HOUR, contributions: ids.map((id) => contribution(id)), reportIds: ids, ...extra,
});
const model = (groups = [group()], extra = {}) => ({ enabled: true, status: { id: "fresh" }, markers: groups, ...extra });
const snapshot = (groups, options = {}) => createCommunityUnreadSnapshot(torino, model(groups), { now: NOW, ...options });

describe("pilot unread snapshot", () => {
  it("counts stable report IDs, not aggregate count or municipality markers", () => {
    const result = snapshot([{ ...torino, phenomena: [group(["a", "b"], { count: 100 }), group(["b", "c"])] }]);
    expect(result.entries.map((entry) => entry.id)).toEqual(["a", "b", "c"]);
    expect(getCommunityUnreadCount(result, empty(), { now: NOW })).toBe(3);
  });

  it("does not make a fabricated unread report from an unidentified group", () => {
    expect(snapshot([group([], { count: 8 })]).entries).toEqual([]);
  });

  it("does not count FVG preview markers when Torino is selected", () => {
    const result = snapshot([group(["fvg"], pordenone), group(["torino"])]);
    expect(result.entries.map((entry) => entry.id)).toEqual(["torino"]);
  });

  it("includes nearby municipalities but excludes reports beyond 30 km", () => {
    const result = snapshot([group(["near"], { lat: torino.lat + 0.2 }), group(["far"], { lat: torino.lat + 0.4 })]);
    expect(result.entries.map((entry) => entry.id)).toEqual(["near"]);
  });

  it("prefers actual marker coordinates over distance computed for an old location", () => {
    expect(snapshot([group(["fvg"], { ...pordenone, distanceKm: 0 })]).entries).toEqual([]);
  });

  it("allows normalized item distance when no marker geometry exists, but not missing distance", () => {
    const result = createCommunityUnreadSnapshot(torino, {
      enabled: true, status: { id: "fresh" }, items: [
        group(["near"], { lat: null, lon: null, distanceKm: 29 }),
        group(["unknown"], { lat: null, lon: null }),
      ],
    }, { now: NOW });
    expect(result.entries.map((entry) => entry.id)).toEqual(["near"]);
  });

  it.each([null, {}, { city: "Torino" }, { lat: null, lon: 0 }, { lat: 91, lon: 0 }, { lat: 0, lon: Infinity }])(
    "rejects unresolved scope %j", (location) => {
      expect(createCommunityUnreadSnapshot(location, model(), { now: NOW })).toBeNull();
    },
  );

  it.each(["loading", "cache", "stale", "error", "unsupported", "offline"])(
    "never clears or counts a %s result", (status) => {
      const result = createCommunityUnreadSnapshot(torino, model(undefined, { status: { id: status } }), { now: NOW });
      const state = empty();
      expect(result.ready).toBe(false);
      expect(getCommunityUnreadCount(result, state, { now: NOW })).toBe(0);
      expect(markCommunitySnapshotSeen(state, result, { now: NOW })).toBe(state);
    },
  );

  it("does not treat a disabled model as loaded", () => {
    expect(createCommunityUnreadSnapshot(torino, model(undefined, { enabled: false }), { now: NOW }).ready).toBe(false);
  });

  it("uses filtered map markers rather than reports retained only in Recenti", () => {
    expect(createCommunityUnreadSnapshot(torino, model([], { items: [group()] }), { now: NOW }).entries).toEqual([]);
  });

  it("excludes own contributions without excluding somebody else in the same group", () => {
    const result = snapshot([group(["mine", "other", "my-other-report"], {
      contributions: [contribution("mine"), contribution("other"), contribution("my-other-report", { sourceKey: "source-mine" })],
    })], { personalState: { reports: [{ reportId: "mine", sourceKey: "source-mine" }] } });
    expect(result.entries.map((entry) => entry.id)).toEqual(["other"]);
  });

  it("excludes expired, locally retired, server-expired and hidden contributions", () => {
    const result = snapshot([group(["expired", "retired", "server-expired", "hidden", "visible"], {
      contributions: [contribution("expired", { expiresAt: NOW }), contribution("retired"),
        contribution("server-expired"), contribution("hidden", { hidden: true }), contribution("visible")],
    })], { personalState: {
      reportWithdrawals: [{ reportId: "retired", expiresAt: NOW + HOUR }],
      reportExpirations: [{ reportId: "server-expired", expiresAt: NOW + HOUR }],
    } });
    expect(result.entries.map((entry) => entry.id)).toEqual(["visible"]);
  });

  it("excludes a denied group and a group removed after three denials", () => {
    const result = snapshot([
      group(["denied"]), group(["moderated"], { groupId: "moderated", confirmations: { no: 3 } }),
      group(["kept"], { groupId: "kept" }),
    ], { personalState: { votes: [{ groupId: "group-a", vote: "no", expiresAt: NOW + HOUR }] } });
    expect(result.entries.map((entry) => entry.id)).toEqual(["kept"]);
  });

  it("uses partial-feed report IDs without recounting known contributions or own receipts", () => {
    const result = snapshot([group(["known", "mine", "other"], { contributions: [contribution("known")] })], {
      personalState: { reports: [{ reportId: "mine" }] },
    });
    expect(result.entries.map((entry) => entry.id)).toEqual(["known", "other"]);
  });
});

describe("pilot seen journal", () => {
  it("marks only the supplied snapshot and preserves identity on repeat acknowledgement", () => {
    const result = snapshot();
    const seen = markCommunitySnapshotSeen(empty(), result, { now: NOW });
    expect(getCommunityUnreadCount(result, seen, { now: NOW })).toBe(0);
    expect(markCommunitySnapshotSeen(seen, result, { now: NOW + 1000 })).toBe(seen);
    expect(getCommunityUnreadCount(snapshot([group(["report-a", "report-b"])]), seen, { now: NOW })).toBe(1);
  });

  it("a renewal of the same observation is not new, even beyond its original expiry", () => {
    const seen = markCommunitySnapshotSeen(empty(), snapshot(), { now: NOW });
    const renewal = snapshot([group(["report-a"], {
      expiresAt: NOW + 2 * HOUR, contributions: [contribution("report-a", { expiresAt: NOW + 2 * HOUR, revision: 2 })],
    })]);
    expect(getCommunityUnreadCount(renewal, seen, { now: NOW + HOUR })).toBe(0);
    const refreshed = markCommunitySnapshotSeen(seen, renewal, { now: NOW + HOUR });
    expect(refreshed.locations[0].entries[0].expiresAt).toBe(NOW + 2 * HOUR + COMMUNITY_SEEN_TTL_MS);
  });

  it("keeps selected-location buckets independent and stable across labels", () => {
    expect(getCommunityUnreadLocationKey({ ...torino, city: "Turin", source: "gps" })).toBe(getCommunityUnreadLocationKey(torino));
    const seen = markCommunitySnapshotSeen(empty(), snapshot(), { now: NOW });
    const elsewhere = createCommunityUnreadSnapshot(pordenone, model([group(["report-a"], pordenone)]), { now: NOW });
    expect(getCommunityUnreadCount(elsewhere, seen, { now: NOW })).toBe(1);
  });

  it("drops expired seen tombstones after the bounded retention period", () => {
    const seen = markCommunitySnapshotSeen(empty(), snapshot(), { now: NOW });
    const storage = { getItem: () => JSON.stringify(seen) };
    expect(readCommunitySeenState({ storage, now: NOW + HOUR + COMMUNITY_SEEN_TTL_MS }).locations).toEqual([]);
  });

  it("bounds persisted scopes and IDs", () => {
    const locations = Array.from({ length: 80 }, (_, index) => ({
      key: `scope:${index.toString(16)}:aa`,
      entries: Array.from({ length: 100 }, (_, number) => ({ id: `id-${number}`, expiresAt: NOW + HOUR })),
    }));
    const result = readCommunitySeenState({ storage: { getItem: () => JSON.stringify({ locations }) }, now: NOW });
    expect(result.locations.length).toBeLessThanOrEqual(COMMUNITY_SEEN_MAX_LOCATIONS);
    expect(result.locations.reduce((sum, scope) => sum + scope.entries.length, 0)).toBe(COMMUNITY_SEEN_MAX_ENTRIES);
  });

  it("persists only opaque scopes, IDs and expiry, not GPS, names or report content", () => {
    const storage = { setItem: vi.fn() };
    const seen = markCommunitySnapshotSeen(empty(), snapshot(), { now: NOW });
    writeCommunitySeenState(seen, { storage, now: NOW });
    const [key, payload] = storage.setItem.mock.calls[0];
    expect(key).toBe(COMMUNITY_SEEN_STORAGE_KEY);
    expect(payload).not.toMatch(/Torino|45\.0703|7\.6869|source-report|sourceKey|city|lat|lon/);
    expect(JSON.parse(payload)).toEqual(seen);
  });

  it.each(["invalid json", "null", '{"locations":[null]}', '{"locations":[{"key":"Torino|45|7","entries":[]}]}'])(
    "recovers safely from invalid storage %s", (stored) => {
      expect(readCommunitySeenState({ storage: { getItem: () => stored }, now: NOW })).toEqual(empty());
    },
  );

  it("keeps QA memory separate and tolerates unavailable browser storage", () => {
    const real = new Map();
    const qa = new Map();
    const adapter = (map) => ({ getItem: (key) => map.get(key), setItem: (key, value) => map.set(key, value) });
    writeCommunitySeenState(markCommunitySnapshotSeen(empty(), snapshot(), { now: NOW }), { storage: adapter(qa), now: NOW });
    expect(readCommunitySeenState({ storage: adapter(real), now: NOW })).toEqual(empty());
    expect(readCommunitySeenState({ storage: adapter(qa), now: NOW }).locations).toHaveLength(1);
    expect(readCommunitySeenState({ storage: { getItem() { throw new Error("blocked"); } }, now: NOW })).toEqual(empty());
    expect(() => writeCommunitySeenState(empty(), { storage: { setItem() { throw new Error("full"); } }, now: NOW })).not.toThrow();
  });
});
