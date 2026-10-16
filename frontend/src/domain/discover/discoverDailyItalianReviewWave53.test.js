import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyItalianReviewWave53.json";

function toRuntimeDateKey(dateIt) {
  const [day, month] = dateIt.split("-");
  return `${month}-${day}`;
}

describe("Discover daily Italian review wave 53", () => {
  it("assigns one controlled decision to every residual candidate", () => {
    const decisionIds = [
      ...reviewWave.keepDaily.map((record) => record.id),
      ...reviewWave.hold.map((record) => record.id),
      ...reviewWave.excluded.map((record) => record.id),
    ];

    expect(reviewWave.policy).toMatchObject({
      allowExceptionalSportsProfiles: true,
      rejectBirthplaceOnlyProfiles: true,
      rejectInternallyInconsistentRecords: true,
      sourceFirst: true,
      publishAfterFurOnly: true,
    });
    expect(reviewWave.summary).toEqual({
      reviewed: 3,
      keepDaily: 1,
      primary: 0,
      secondary: 1,
      hold: 1,
      excluded: 1,
      canonicalPrimaryDatesBefore: 274,
      canonicalPrimaryDatesAfter: 274,
      currentVisiblePrimaryCoverage: 269,
    });
    expect(decisionIds).toHaveLength(3);
    expect(new Set(decisionIds).size).toBe(3);
  });

  it("publishes Reno Bertoia as an exceptional secondary sports memory", () => {
    const selected = reviewWave.keepDaily[0];
    const dateKey = toRuntimeDateKey(selected.dateIt);
    const primaryAnchor = localMemory.records.find((record) => (
      record.dailyRole !== "secondary"
      && record.primaryUse === "discover"
      && record.readyForUi === true
      && record.dateAnchors?.includes(dateKey)
    ));
    const canonical = localMemory.records.filter((record) => record.candidateId === selected.id);

    expect(selected).toMatchObject({
      wikidataId: "Q7313382",
      dateIt: "08-01",
      municipality: "San Vito al Tagliamento",
      province: "PN",
      canonicalCategory: "sport",
      dailyRole: "secondary",
      sourceStatus: "pass",
      readyForUi: false,
    });
    expect(selected.sourceUrl).toBe("https://baseballhalloffame.ca/hall-of-famer/reno-bertoia/");
    expect(selected.copyIt).toContain("dieci stagioni nella Major League Baseball");
    expect(selected.copyIt).toContain("Canadian Baseball Hall of Fame");
    expect(primaryAnchor).toBeTruthy();
    expect(canonical).toHaveLength(1);
    expect(canonical[0]).toMatchObject({
      dailyRole: "secondary",
      dateAnchors: [dateKey],
      editorialStatus: "ready_for_discover",
      languageStatus: { it: "approved", fur: "approved" },
      readyForUi: true,
    });
  });

  it("holds Sara Casasola without discarding either official source", () => {
    const held = reviewWave.hold[0];

    expect(held.id).toBe("master-fvg-29-11-Q43303860");
    expect(held.reason).toContain("resta sospesa");
    expect(held.evidence).toHaveLength(2);
    expect(held.evidence.every((source) => source.url.startsWith("https://"))).toBe(true);
  });

  it("rejects the conflated Reggie Jackson record", () => {
    expect(reviewWave.excluded).toEqual([
      expect.objectContaining({
        id: "master-fvg-16-04-Q2640578",
        reason: expect.stringContaining("internamente incoerente"),
      }),
    ]);
  });
});
