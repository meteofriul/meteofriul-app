import { describe, expect, it, vi } from "vitest";

import {
  COMMUNITY_MODERATION_SOURCE_TTL_MS,
  COMMUNITY_MODERATION_STORAGE_KEY,
  filterCommunityModerationModel,
  hideCommunityContentLocally,
  hideCommunitySourcesLocally,
  readCommunityModerationState,
} from "./communityModerationState";

function createStorage(initialValue = null) {
  const values = new Map();
  if (initialValue) {
    values.set(COMMUNITY_MODERATION_STORAGE_KEY, JSON.stringify(initialValue));
  }

  return {
    getItem: vi.fn((key) => values.get(key) || null),
    setItem: vi.fn((key, value) => values.set(key, value)),
    values,
  };
}

function buildContribution(id, sourceKey, createdAt) {
  return {
    createdAt,
    expiresAt: 3_600_000,
    id,
    sourceKey,
    sourceKeys: [sourceKey],
    timeLabel: createdAt === 200 ? "Adesso" : "2 min fa",
  };
}

function buildModel() {
  const rain = {
    confirmations: { no: 1, yes: 2 },
    count: 2,
    countLabel: "2 segnalazioni",
    contributions: [
      buildContribution("rain-a-2", "source-a", 100),
      buildContribution("rain-a-1", "source-a", 90),
    ],
    createdAt: 100,
    expiresAt: 3_600_000,
    groupId: "group-rain",
    id: "group-rain",
    reportIds: ["rain-a-2", "rain-a-1"],
    sourceKey: "source-a",
    sourceKeys: ["source-a"],
    timeLabel: "2 min fa",
    typeId: "rain",
    typeLabel: "Pioggia",
  };
  const wind = {
    confirmations: { no: 0, yes: 1 },
    count: 2,
    countLabel: "2 segnalazioni",
    contributions: [
      buildContribution("wind-b", "source-b", 200),
      buildContribution("wind-c", "source-c", 150),
    ],
    createdAt: 200,
    expiresAt: 3_600_000,
    groupId: "group-wind",
    id: "group-wind",
    reportIds: ["wind-b", "wind-c"],
    sourceKey: "",
    sourceKeys: ["source-b", "source-c"],
    timeLabel: "Adesso",
    typeId: "wind",
    typeLabel: "Vento forte",
  };

  return {
    copy: {
      reportCountMany: "{count} segnalazioni",
      reportCountOne: "1 segnalazione",
      reportMultiplePhenomena: "Più fenomeni",
    },
    items: [
      { ...rain, id: "report-rain" },
      { ...wind, id: "report-wind" },
    ],
    markers: [{
      ...wind,
      confirmations: { no: 1, yes: 3 },
      count: 4,
      countLabel: "4 segnalazioni",
      id: "place:pordenone",
      phenomena: [wind, rain],
      typeId: "multiple",
      typeLabel: "Più fenomeni",
    }],
  };
}

describe("community moderation local state", () => {
  it("persists hidden content and all opaque sources with a short expiry", () => {
    const storage = createStorage();
    let state = readCommunityModerationState({ now: 1_000, storage });
    state = hideCommunityContentLocally(state, "group-rain", {
      expiresAt: 50_000,
      now: 1_000,
      storage,
    });
    state = hideCommunitySourcesLocally(state, ["source-b", "source-c"], {
      expiresAt: 50_000,
      now: 1_000,
      storage,
    });

    expect(state.content).toEqual([{ expiresAt: 50_000, key: "group-rain" }]);
    expect(state.sources.map((entry) => entry.key)).toEqual(["source-b", "source-c"]);
    expect(JSON.parse(storage.values.get(COMMUNITY_MODERATION_STORAGE_KEY))).toEqual(state);
  });

  it("automatically removes expired local moderation keys", () => {
    const storage = createStorage({
      content: [{ expiresAt: 999, key: "old-group" }],
      sources: [
        { expiresAt: 999, key: "old-source" },
        { expiresAt: 2_000, key: "active-source" },
      ],
    });

    expect(readCommunityModerationState({ now: 1_000, storage })).toEqual({
      content: [],
      sources: [{ expiresAt: 2_000, key: "active-source" }],
    });
  });

  it("removes only the blocked contribution from a mixed-source group", () => {
    const filtered = filterCommunityModerationModel(buildModel(), {
      content: [],
      sources: [{ expiresAt: 9_999, key: "source-c" }],
    });

    expect(filtered.items.map((item) => item.id)).toEqual(["report-rain", "report-wind"]);
    expect(filtered.items[1]).toMatchObject({
      count: 1,
      countLabel: "1 segnalazione",
      reportIds: ["wind-b"],
      sourceKey: "source-b",
      sourceKeys: ["source-b"],
    });
    expect(filtered.items[1].contributions.map((item) => item.id)).toEqual(["wind-b"]);
    expect(filtered.markers).toHaveLength(1);
    expect(filtered.markers[0]).toMatchObject({
      confirmations: { no: 1, yes: 3 },
      count: 3,
      countLabel: "3 segnalazioni",
      typeId: "multiple",
      typeLabel: "Più fenomeni",
    });
    expect(filtered.markers[0].phenomena.map((item) => item.groupId)).toEqual([
      "group-wind",
      "group-rain",
    ]);
  });

  it("filters every single-source group from a locally blocked source", () => {
    const filtered = filterCommunityModerationModel(buildModel(), {
      content: [],
      sources: [{ expiresAt: 9_999, key: "source-a" }],
    });

    expect(filtered.items.map((item) => item.id)).toEqual(["report-wind"]);
    expect(filtered.markers[0].phenomena.map((item) => item.groupId)).toEqual(["group-wind"]);
  });

  it("does not hide the group id when blocking a source, so a later second source can appear", () => {
    const storage = createStorage();
    const state = hideCommunitySourcesLocally(
      { content: [], sources: [] },
      ["source-a"],
      { now: 1_000, storage },
    );
    const model = buildModel();
    model.items[0] = {
      ...model.items[0],
      contributions: [
        buildContribution("rain-a", "source-a", 100),
        buildContribution("rain-b", "source-b", 90),
      ],
      reportIds: ["rain-a", "rain-b"],
      sourceKey: "",
      sourceKeys: ["source-a", "source-b"],
    };
    model.markers[0] = {
      ...model.markers[0],
      phenomena: [model.items[0]],
    };

    const filtered = filterCommunityModerationModel(model, state);

    expect(state.content).toEqual([]);
    expect(filtered.items.map((item) => item.id)).toContain("report-rain");
    expect(filtered.items[0]).toMatchObject({
      count: 1,
      reportIds: ["rain-b"],
      sourceKey: "source-b",
      sourceKeys: ["source-b"],
    });
    expect(filtered.markers[0].phenomena[0].sourceKeys).toEqual(["source-b"]);
  });

  it("removes a mixed-source group after every known source is blocked", () => {
    const filtered = filterCommunityModerationModel(buildModel(), {
      content: [],
      sources: [
        { expiresAt: 9_999, key: "source-b" },
        { expiresAt: 9_999, key: "source-c" },
      ],
    });

    expect(filtered.items.map((item) => item.id)).toEqual(["report-rain"]);
    expect(filtered.markers[0]).toMatchObject({
      count: 2,
      countLabel: "2 segnalazioni",
      sourceKey: "source-a",
      sourceKeys: ["source-a"],
      typeId: "rain",
      typeLabel: "Pioggia",
    });
    expect(filtered.markers[0].phenomena.map((item) => item.groupId)).toEqual([
      "group-rain",
    ]);
  });

  it("keeps a new report from the same hidden source filtered during the 24-hour window", () => {
    const storage = createStorage({
      content: [],
      sources: [{ expiresAt: 86_401_000, key: "source-a" }],
    });
    const state = readCommunityModerationState({ now: 82_801_000, storage });
    const model = buildModel();
    model.items[0] = {
      ...model.items[0],
      groupId: "new-group-rain",
      id: "new-report-rain",
    };
    model.markers[0] = {
      ...model.markers[0],
      phenomena: [{
        ...model.markers[0].phenomena[1],
        groupId: "new-group-rain",
        id: "new-group-rain",
      }],
    };

    const filtered = filterCommunityModerationModel(model, state);

    expect(filtered.items.map((item) => item.id)).not.toContain("new-report-rain");
    expect(filtered.markers).toEqual([]);
  });

  it("automatically restores a blocked source after 24 hours", () => {
    const storage = createStorage({
      content: [],
      sources: [{ expiresAt: 86_401_000, key: "source-a" }],
    });

    const state = readCommunityModerationState({ now: 86_401_001, storage });
    const filtered = filterCommunityModerationModel(buildModel(), state);

    expect(state.sources).toEqual([]);
    expect(filtered.items.map((item) => item.id)).toContain("report-rain");
  });

  it("caps a local source block at exactly 24 hours", () => {
    const storage = createStorage();
    const now = 10_000;
    const state = hideCommunitySourcesLocally(
      { content: [], sources: [] },
      ["source-a"],
      {
        expiresAt: now + (72 * 60 * 60 * 1000),
        now,
        storage,
      },
    );

    expect(state.sources).toEqual([{
      expiresAt: now + COMMUNITY_MODERATION_SOURCE_TTL_MS,
      key: "source-a",
    }]);
  });
});
