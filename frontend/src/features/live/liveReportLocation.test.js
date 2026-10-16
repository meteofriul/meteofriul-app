import { describe, expect, it } from "vitest";

import {
  LIVE_REPORT_LOCATIONS,
  findNearbyMatchingCommunityGroups,
  getLiveReportLocationDecision,
  isWithinLiveReportBounds,
  selectCommunityNearbyMatch,
} from "./liveReportLocation";

describe("live report location policy", () => {
  it("uses the complete audited FVG municipality catalog", () => {
    expect(LIVE_REPORT_LOCATIONS).toHaveLength(215);
    expect(LIVE_REPORT_LOCATIONS.some((item) => item.place === "Cordenons")).toBe(true);
  });

  it("accepts coordinates in FVG and selects the nearest supported zone", () => {
    const result = getLiveReportLocationDecision(
      { lat: 45.9567, lon: 12.6605 },
      { locations: [
        { place: "Pordenone", lat: 45.9569, lon: 12.6605 },
        { place: "Cordenons", lat: 45.9836, lon: 12.7004 },
      ] },
    );

    expect(result).toMatchObject({
      detectedPlace: "Pordenone",
      maxDistanceKm: 5,
      ok: true,
    });
    expect(result.nearbyPlaces.map((item) => item.place)).toEqual([
      "Pordenone",
      "Cordenons",
    ]);
  });

  it("limits the correction menu to the two nearest supported zones", () => {
    const result = getLiveReportLocationDecision(
      { lat: 45.9567, lon: 12.6605 },
      { locations: [
        { place: "Far away", lat: 46.2, lon: 13.3 },
        { place: "Third", lat: 45.97, lon: 12.68 },
        { place: "Nearest", lat: 45.9569, lon: 12.6605 },
        { place: "Second", lat: 45.96, lon: 12.665 },
      ] },
    );

    expect(result.nearbyPlaces.map((item) => item.place)).toEqual([
      "Nearest",
      "Second",
    ]);
  });

  it("keeps only the detected zone when every alternative is outside five kilometres", () => {
    const result = getLiveReportLocationDecision(
      { lat: 45.9567, lon: 12.6605 },
      { locations: [
        { place: "Pordenone", lat: 45.9569, lon: 12.6605 },
        { place: "Udine", lat: 46.063, lon: 13.235 },
      ] },
    );

    expect(result.nearbyPlaces.map((item) => item.place)).toEqual(["Pordenone"]);
  });

  it("rejects coordinates outside FVG", () => {
    expect(isWithinLiveReportBounds({ lat: 44.5, lon: 12.7 })).toBe(false);
    expect(getLiveReportLocationDecision({ lat: 44.5, lon: 12.7 }))
      .toEqual({ ok: false, reason: "out_of_area" });
  });

  it("rejects an FVG coordinate with no supported reporting zone within five kilometres", () => {
    const result = getLiveReportLocationDecision(
      { lat: 46.25, lon: 13.1 },
      { locations: [{ place: "Udine", lat: 46.0711, lon: 13.2346 }] },
    );

    expect(result).toEqual({ ok: false, reason: "out_of_area" });
  });
});

describe("nearby community report matching", () => {
  const coords = { lat: 45.9567, lon: 12.6605 };

  it("keeps only active groups of the same type within five kilometres", () => {
    const now = Date.parse("2026-08-29T18:00:00Z");
    const matches = findNearbyMatchingCommunityGroups([
      {
        createdAt: now - 60_000,
        expiresAt: now + 60_000,
        groupId: "rain:pordenone",
        lat: 45.9567,
        lon: 12.6605,
        typeId: "rain",
      },
      {
        createdAt: now,
        expiresAt: now + 60_000,
        groupId: "snow:pordenone",
        lat: 45.9567,
        lon: 12.6605,
        typeId: "snow",
      },
      {
        createdAt: now,
        expiresAt: now + 60_000,
        groupId: "rain:trieste",
        lat: 45.6495,
        lon: 13.7768,
        typeId: "rain",
      },
      {
        createdAt: now,
        expiresAt: now + 10_000,
        groupId: "rain:expiring",
        lat: 45.9567,
        lon: 12.6605,
        typeId: "rain",
      },
    ], { coords, now, typeId: "rain" });

    expect(matches.map((item) => item.groupId)).toEqual(["rain:pordenone"]);
  });

  it("orders candidates by distance, recency and stable group id", () => {
    const now = Date.parse("2026-08-29T18:00:00Z");
    const matches = findNearbyMatchingCommunityGroups([
      {
        createdAt: now - 120_000,
        expiresAt: now + 60_000,
        groupId: "rain:farther",
        lat: 45.975,
        lon: 12.68,
        typeId: "rain",
      },
      {
        createdAt: now - 120_000,
        expiresAt: now + 60_000,
        groupId: "rain:older",
        lat: 45.9567,
        lon: 12.6605,
        typeId: "rain",
      },
      {
        createdAt: now - 60_000,
        expiresAt: now + 60_000,
        groupId: "rain:newer",
        lat: 45.9567,
        lon: 12.6605,
        typeId: "rain",
      },
    ], { coords, now, typeId: "rain" });

    expect(matches.map((item) => item.groupId)).toEqual([
      "rain:newer",
      "rain:older",
      "rain:farther",
    ]);
  });

  it("fails closed for invalid coordinates", () => {
    expect(findNearbyMatchingCommunityGroups([
      {
        expiresAt: Date.now() + 60_000,
        groupId: "rain:test",
        lat: 46,
        lon: 13,
        typeId: "rain",
      },
    ], { coords: null, typeId: "rain" })).toEqual([]);
  });

  it("prevents duplicate nearby contributions but lets a negative vote change to yes", () => {
    const matches = [{ groupId: "nearest" }, { groupId: "own" }];
    expect(selectCommunityNearbyMatch(matches, {
      reports: [{ groupId: "own" }],
      votes: [],
    })).toMatchObject({ match: { groupId: "own" }, state: "own" });

    expect(selectCommunityNearbyMatch(matches, {
      reports: [],
      votes: [{ groupId: "nearest", vote: "no" }],
    })).toMatchObject({ match: { groupId: "nearest" }, state: "confirmable" });

    expect(selectCommunityNearbyMatch(matches, {
      reports: [],
      votes: [{ groupId: "own", vote: "yes" }],
    })).toMatchObject({ match: { groupId: "own" }, state: "voted" });
  });
});
