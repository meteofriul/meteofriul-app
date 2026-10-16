import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyItalianReviewWave59.json";

const excludedId = "master-fvg-26-02-Q24052040";

describe("Discover daily Italian review wave 59", () => {
  it("closes the final low-merit primary-gap candidate", () => {
    expect(reviewWave.policy).toMatchObject({
      excludeSportsOnlyProfiles: true,
      allowExceptionalSportsProfiles: true,
      sourceFirst: true,
      doNotPromoteToPrimaryForCoverageOnly: true,
    });
    expect(reviewWave.summary).toEqual({
      reviewed: 1,
      keepDaily: 0,
      primary: 0,
      secondary: 0,
      hold: 0,
      excluded: 1,
      canonicalPrimaryDatesBefore: 277,
      canonicalPrimaryDatesAfter: 277,
      currentVisiblePrimaryCoverage: 272,
    });
    expect(reviewWave.keepDaily).toEqual([]);
    expect(reviewWave.hold).toEqual([]);
    expect(reviewWave.excluded).toEqual([
      expect.objectContaining({ id: excludedId }),
    ]);
  });

  it("does not create a canonical memory or FUR work for the excluded athlete", () => {
    const canonical = localMemory.records.find((record) => record.candidateId === excludedId);

    expect(canonical).toBeUndefined();
    expect(reviewWave.excluded[0].reason.length).toBeGreaterThan(120);
  });
});
