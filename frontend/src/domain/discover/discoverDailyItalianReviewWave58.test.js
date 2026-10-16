import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyItalianReviewWave58.json";

const expectedExcludedIds = [
  "master-fvg-19-05-Q109933627",
  "master-fvg-26-02-Q3608777",
];

describe("Discover daily Italian review wave 58", () => {
  it("closes both remaining low-merit primary-gap candidates", () => {
    expect(reviewWave.policy).toMatchObject({
      excludeSportsOnlyProfiles: true,
      allowExceptionalSportsProfiles: true,
      sourceFirst: true,
      doNotPromoteToPrimaryForCoverageOnly: true,
    });
    expect(reviewWave.summary).toEqual({
      reviewed: 2,
      keepDaily: 0,
      primary: 0,
      secondary: 0,
      hold: 0,
      excluded: 2,
      canonicalPrimaryDatesBefore: 277,
      canonicalPrimaryDatesAfter: 277,
      currentVisiblePrimaryCoverage: 272,
    });
    expect(reviewWave.keepDaily).toEqual([]);
    expect(reviewWave.hold).toEqual([]);
    expect(reviewWave.excluded.map((record) => record.id)).toEqual(expectedExcludedIds);
  });

  it("does not create canonical memories or FUR work for the excluded athletes", () => {
    const canonicalCandidateIds = new Set(
      localMemory.records.map((record) => record.candidateId).filter(Boolean),
    );

    expect(expectedExcludedIds.every((id) => !canonicalCandidateIds.has(id))).toBe(true);
    expect(reviewWave.excluded.every((record) => record.reason.length > 120)).toBe(true);
  });
});
