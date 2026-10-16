import { describe, expect, it } from "vitest";

import {
  COMMUNITY_MAP_WITHDRAWAL_DENIALS,
  filterCommunityMapMarkers,
  getAcquiredCommunityMapWithdrawals,
  isCommunityGroupHiddenFromMap,
} from "./communityMapVisibility";

const copy = {
  reportCountMany: "{count} segnalazioni",
  reportCountOne: "1 segnalazione",
  reportMultiplePhenomena: "Più fenomeni",
};
const NOW = 1_000;

function report(groupId, no = 0) {
  return {
    confirmations: { no, yes: 0 },
    count: 1,
    createdAt: 1_000,
    expiresAt: 61_000,
    groupId,
    reportIds: [`report:${groupId}`],
    sourceKeys: [`source:${groupId}`],
    typeId: "rain",
    typeLabel: "Pioggia",
  };
}

describe("community map visibility", () => {
  it("hides a group from this installation after its local no vote", () => {
    const entry = report("rain:pordenone", 1);
    const personalState = {
      mapWithdrawals: [],
      votes: [{ groupId: entry.groupId, vote: "no" }],
    };

    expect(isCommunityGroupHiddenFromMap(entry, personalState, { now: NOW })).toBe(true);
    expect(filterCommunityMapMarkers([entry], personalState, copy, { now: NOW })).toEqual([]);
  });

  it("withdraws a group from the map at three denials but keeps lower totals visible", () => {
    expect(COMMUNITY_MAP_WITHDRAWAL_DENIALS).toBe(3);
    expect(filterCommunityMapMarkers(
      [report("wind:cordenons", 2)],
      { mapWithdrawals: [], votes: [] },
      copy,
      { now: NOW },
    )).toHaveLength(1);
    expect(filterCommunityMapMarkers(
      [report("wind:cordenons", 3)],
      { mapWithdrawals: [], votes: [] },
      copy,
      { now: NOW },
    )).toEqual([]);
  });

  it("keeps a withdrawn group hidden when a stale response falls back below the threshold", () => {
    const staleEntry = report("snow:udine", 2);
    const personalState = {
      mapWithdrawals: [{
        expiresAt: staleEntry.expiresAt,
        groupId: staleEntry.groupId,
      }],
      votes: [],
    };

    expect(isCommunityGroupHiddenFromMap(staleEntry, personalState, { now: NOW })).toBe(true);
    expect(filterCommunityMapMarkers([staleEntry], personalState, copy, { now: NOW })).toEqual([]);
  });

  it("filters only map markers and never removes or mutates Recent items", () => {
    const localDenied = report("rain:pordenone", 1);
    const globallyWithdrawn = report("storm:udine", 4);
    const items = [localDenied, globallyWithdrawn];
    const snapshot = JSON.parse(JSON.stringify(items));
    const personalState = {
      mapWithdrawals: [],
      votes: [{ groupId: localDenied.groupId, vote: "no" }],
    };

    expect(filterCommunityMapMarkers(items, personalState, copy, { now: NOW })).toEqual([]);
    expect(items).toEqual(snapshot);
    expect(items).toHaveLength(2);
  });

  it("excludes an expired group only from map markers", () => {
    const expired = report("fog:gemona", 0);
    expired.expiresAt = NOW;
    const recentItems = [expired];
    const snapshot = JSON.parse(JSON.stringify(recentItems));
    const personalState = { mapWithdrawals: [], votes: [] };

    expect(isCommunityGroupHiddenFromMap(expired, personalState, { now: NOW - 1 }))
      .toBe(false);
    expect(isCommunityGroupHiddenFromMap(expired, personalState, { now: NOW }))
      .toBe(true);
    expect(filterCommunityMapMarkers(recentItems, personalState, copy, { now: NOW }))
      .toEqual([]);
    expect(recentItems).toEqual(snapshot);
  });

  it("does not treat a missing materialized expiry as an already expired group", () => {
    const withoutExpiry = report("rain:maniago", 0);
    withoutExpiry.expiresAt = 0;

    expect(filterCommunityMapMarkers(
      [withoutExpiry],
      { mapWithdrawals: [], votes: [] },
      copy,
      { now: NOW },
    )).toHaveLength(1);
  });

  it("acquires one monotonic tombstone from a threshold response", () => {
    const withdrawn = report("hail:trieste", 3);

    expect(getAcquiredCommunityMapWithdrawals({
      items: [withdrawn],
      markers: [withdrawn],
    }, {
      mapWithdrawals: [],
      votes: [],
    })).toEqual([{
      expiresAt: withdrawn.expiresAt,
      groupId: withdrawn.groupId,
    }]);
  });
});
