import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyItalianReviewWave55.json";

const expectedExcludedIds = [
  "master-fvg-03-10-Q64500522",
  "master-fvg-06-05-Q3611696",
  "master-fvg-06-10-Q3893790",
  "master-fvg-07-01-Q16573874",
  "master-fvg-07-11-Q3934580",
  "master-fvg-07-11-Q18811994",
  "master-fvg-08-04-Q3619595",
  "master-fvg-09-01-Q6911387",
  "master-fvg-09-03-Q6836868",
  "master-fvg-09-07-Q3707143",
  "master-fvg-09-08-Q3701828",
  "master-fvg-12-04-Q51879962",
  "master-fvg-13-01-Q50359737",
  "master-fvg-13-06-Q21076838",
  "master-fvg-13-11-Q3080872",
];

describe("Discover daily Italian review wave 55", () => {
  it("records one controlled exclusion for all 15 low-merit primary-gap candidates", () => {
    expect(reviewWave.policy).toMatchObject({
      excludeGenericPoliticalProfiles: true,
      excludeSportsOnlyProfiles: true,
      allowExceptionalSportsProfiles: true,
      sourceFirst: true,
      doNotPromoteToPrimaryForCoverageOnly: true,
    });
    expect(reviewWave.summary).toEqual({
      reviewed: 15,
      keepDaily: 0,
      primary: 0,
      secondary: 0,
      hold: 0,
      excluded: 15,
      canonicalPrimaryDatesBefore: 274,
      canonicalPrimaryDatesAfter: 274,
      currentVisiblePrimaryCoverage: 269,
    });
    expect(reviewWave.keepDaily).toEqual([]);
    expect(reviewWave.hold).toEqual([]);
    expect(reviewWave.excluded.map((record) => record.id)).toEqual(expectedExcludedIds);
    expect(new Set(expectedExcludedIds).size).toBe(expectedExcludedIds.length);
  });

  it("does not create canonical memories or translation work for excluded profiles", () => {
    const canonicalCandidateIds = new Set(
      localMemory.records.map((record) => record.candidateId).filter(Boolean),
    );

    expect(expectedExcludedIds.every((id) => !canonicalCandidateIds.has(id))).toBe(true);
    expect(reviewWave.excluded.every((record) => record.reason.length > 120)).toBe(true);
  });
});
