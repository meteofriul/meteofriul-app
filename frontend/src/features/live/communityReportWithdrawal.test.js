import { describe, expect, it } from "vitest";
import {
  filterCommunityExpiredReportsFromMap,
  filterCommunityWithdrawnReportsModel,
} from "./communityReportWithdrawal";

const NOW = 1_000;
const copy = {
  reportCountOne: "1 segnalazione",
  reportCountMany: "{count} segnalazioni",
  reportMultiplePhenomena: "Più fenomeni",
};

function contribution(id, sourceKey, createdAt = 500) {
  const identity = { alias: sourceKey };
  return {
    id, sourceKey, sourceKeys: [sourceKey], identity,
    identities: [{ sourceKey, identity }], createdAt, expiresAt: createdAt + 60_000,
    timeLabel: `${createdAt} fa`,
  };
}

function group(id, typeId, contributions) {
  const latest = contributions.reduce((previous, item) => item.createdAt > previous.createdAt ? item : previous);
  const sourceKeys = [...new Set(contributions.flatMap((item) => item.sourceKeys))];
  return {
    id, groupId: id, typeId, typeLabel: typeId, contributions,
    reportIds: contributions.map((item) => item.id),
    count: contributions.length,
    countLabel: contributions.length === 1 ? copy.reportCountOne : `${contributions.length} segnalazioni`,
    confirmations: { yes: 2, no: 0 },
    sourceKeys, sourceKey: sourceKeys.length === 1 ? sourceKeys[0] : "",
    identities: sourceKeys.map((sourceKey) => ({ sourceKey, identity: { alias: sourceKey } })),
    identity: latest.identity,
    createdAt: latest.createdAt, expiresAt: latest.expiresAt, timeLabel: latest.timeLabel,
  };
}

function model(groups) {
  return {
    copy,
    items: groups,
    markers: [{
      ...groups[0], id: "place:093033", phenomena: groups,
      count: groups.reduce((count, item) => count + item.count, 0),
      typeId: groups.length > 1 ? "multiple" : groups[0].typeId,
    }],
  };
}

function withdrawn(...reportIds) {
  return { reportWithdrawals: reportIds.map((reportId) => ({ reportId, expiresAt: 61_000 })) };
}

describe("report-specific acknowledged withdrawals", () => {
  it("keeps the ordinary model reference intact without active matching tombstones", () => {
    const source = model([group("rain", "rain", [contribution("one", "source-a")])]);
    expect(filterCommunityWithdrawnReportsModel(source, {}, { now: NOW })).toBe(source);
    expect(filterCommunityWithdrawnReportsModel(source, { reportWithdrawals: [] }, { now: NOW })).toBe(source);
    expect(filterCommunityWithdrawnReportsModel(source, withdrawn("another"), { now: NOW })).toBe(source);
    expect(filterCommunityWithdrawnReportsModel(source, withdrawn("one"), { now: 61_000 })).toBe(source);
  });

  it("removes one report from a shared group while retaining other reports and votes", () => {
    const own = contribution("mine", "source-mine", 700);
    const other = contribution("other", "source-other", 600);
    const source = model([group("rain", "rain", [own, other])]);
    const snapshot = structuredClone(source);
    const result = filterCommunityWithdrawnReportsModel(source, withdrawn("mine"), { now: NOW });

    expect(source).toEqual(snapshot);
    expect(result.items[0]).toMatchObject({
      count: 1, countLabel: "1 segnalazione", contributions: [other], reportIds: ["other"],
      createdAt: 600, expiresAt: 60_600, timeLabel: "600 fa", identity: other.identity,
      sourceKey: "source-other", sourceKeys: ["source-other"],
      identities: [{ sourceKey: "source-other", identity: other.identity }],
      confirmations: { yes: 2, no: 0 },
    });
    expect(result.markers[0]).toMatchObject({ id: "place:093033", count: 1, reportIds: ["other"], typeId: "rain" });
    expect(result.markers[0].phenomena).toHaveLength(1);
    expect(filterCommunityWithdrawnReportsModel(result, withdrawn("mine"), { now: NOW })).toBe(result);
  });

  it("preserves a second report by the same author in the same group", () => {
    const old = contribution("mine-first", "same-source", 500);
    const newer = contribution("mine-second", "same-source", 700);
    const source = model([group("rain", "rain", [newer, old])]);
    const result = filterCommunityWithdrawnReportsModel(source, withdrawn("mine-second"), { now: NOW });
    expect(result.items[0].reportIds).toEqual(["mine-first"]);
    expect(result.items[0].sourceKeys).toEqual(["same-source"]);
    expect(result.items[0].count).toBe(1);
  });

  it("rebuilds a mixed municipality marker after its last report of one phenomenon is withdrawn", () => {
    const rain = group("rain", "rain", [contribution("mine", "mine", 800)]);
    const wind = group("wind", "wind", [contribution("other", "other", 600)]);
    const source = model([rain, wind]);
    const result = filterCommunityWithdrawnReportsModel(source, withdrawn("mine"), { now: NOW });
    expect(result.items).toEqual([wind]);
    expect(result.markers[0]).toMatchObject({
      id: "place:093033", groupId: "wind", typeId: "wind", typeLabel: "wind",
      count: 1, countLabel: "1 segnalazione", createdAt: 600, expiresAt: 60_600,
      reportIds: ["other"], phenomena: [wind], confirmations: wind.confirmations,
    });
  });

  it("drops an empty group and marker only after all their known reports are withdrawn", () => {
    const source = model([group("rain", "rain", [contribution("mine", "mine")])]);
    expect(filterCommunityWithdrawnReportsModel(source, withdrawn("mine"), { now: NOW }))
      .toMatchObject({ items: [], markers: [] });
  });

  it("uses reportIds when contribution details are absent and retains unknown contributors", () => {
    const source = model([{
      ...group("rain", "rain", [contribution("mine", "mine")]),
      contributions: [], reportIds: ["mine", "other"], count: 3,
    }]);
    const result = filterCommunityWithdrawnReportsModel(source, withdrawn("mine"), { now: NOW });
    expect(result.items[0]).toMatchObject({ count: 2, countLabel: "2 segnalazioni", reportIds: ["other"] });
    expect(result.markers[0].count).toBe(2);
  });

  it("never treats a group-wide map tombstone as ownership withdrawal", () => {
    const source = model([group("rain", "rain", [contribution("mine", "mine")])]);
    expect(filterCommunityWithdrawnReportsModel(source, {
      mapWithdrawals: [{ groupId: "rain", expiresAt: 61_000 }],
    }, { now: NOW })).toBe(source);
  });

  it("keeps unaffected entries referentially stable and restores item recency order", () => {
    const rain = group("rain", "rain", [contribution("mine", "mine", 900), contribution("other", "other", 100)]);
    const wind = group("wind", "wind", [contribution("wind-other", "wind-other", 600)]);
    const result = filterCommunityWithdrawnReportsModel(model([rain, wind]), withdrawn("mine"), { now: NOW });
    expect(result.items[0]).toBe(wind);
    expect(result.items[1].createdAt).toBe(100);
    expect(result.markers[0].typeId).toBe("multiple");
    expect(result.markers[0].count).toBe(2);
  });

  it("removes a server-expired receipt only from the map and preserves Recenti", () => {
    const mine = contribution("mine", "source-mine", 700);
    const other = contribution("other", "source-other", 600);
    const source = model([group("rain", "rain", [mine, other])]);
    const result = filterCommunityExpiredReportsFromMap(source, {
      reportExpirations: [{ reportId: "mine", expiresAt: 61_000 }],
    }, { now: NOW });

    expect(result.items).toBe(source.items);
    expect(result.items[0].reportIds).toEqual(["mine", "other"]);
    expect(result.markers[0]).toMatchObject({ count: 1, reportIds: ["other"] });
    expect(result.markers[0].phenomena[0].contributions).toEqual([other]);
  });
});
