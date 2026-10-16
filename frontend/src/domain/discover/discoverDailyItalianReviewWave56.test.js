import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyItalianReviewWave56.json";

const expectedExcludedIds = [
  "master-fvg-06-12-Q3860838",
  "master-fvg-09-01-Q16041299",
  "master-fvg-13-04-Q28058625",
  "master-fvg-13-06-Q3770672",
  "master-fvg-13-11-Q3740341",
  "master-fvg-15-07-Q17635276",
  "master-fvg-15-11-Q3645907",
  "master-fvg-16-09-Q21651781",
  "master-fvg-18-01-Q3051068",
  "master-fvg-19-04-Q3770103",
  "master-fvg-22-08-Q21030430",
  "master-fvg-23-10-Q3958507",
  "master-fvg-24-02-Q64225322",
  "master-fvg-24-03-Q56704255",
  "master-fvg-24-07-Q7406656",
];

describe("Discover daily Italian review wave 56", () => {
  it("records one controlled exclusion for all 15 low-merit primary-gap candidates", () => {
    expect(reviewWave.policy).toMatchObject({
      excludeGenericPoliticalProfiles: true,
      excludeGenericProfessionalProfiles: true,
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
