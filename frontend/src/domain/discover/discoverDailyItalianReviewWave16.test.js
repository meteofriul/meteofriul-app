import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyItalianReviewWave16.json";

function toRuntimeDateKey(dateIt) {
  const [day, month] = dateIt.split("-");
  return `${month}-${day}`;
}

function allReviewedRecords() {
  return [
    ...reviewWave.keepDaily,
    ...reviewWave.hold,
    ...reviewWave.excluded,
  ];
}

describe("Discover daily Italian review wave 16", () => {
  it("keeps the Italian selection blocked until FUR approval", () => {
    expect(reviewWave.policy).toMatchObject({
      readyForUi: false,
      furDeferred: true,
      dateFormat: "DD-MM",
      excludeDeaths: true,
      excludeGenericPoliticalProfiles: true,
      excludeGenericProfessionalProfiles: true,
      excludeAlreadyReviewedProfiles: true,
      rejectSemanticDuplicates: true,
      rejectUncertainCalendarDates: true,
      sourceFirst: true,
      publishAfterFurOnly: true,
      allowMultipleMemoriesPerDate: true,
      secondaryOrderedByPriority: true,
    });
    expect(reviewWave.keepDaily.every((record) => record.readyForUi === false)).toBe(true);
    expect(JSON.stringify(reviewWave)).not.toContain('"fur"');
  });

  it("keeps five sourced secondary memories without adding filler", () => {
    expect(reviewWave.keepDaily).toHaveLength(5);
    expect(reviewWave.keepDaily.every((record) => record.dailyRole === "secondary")).toBe(true);
    expect(reviewWave.hold).toHaveLength(2);
    expect(reviewWave.excluded).toHaveLength(5);
    expect(reviewWave.summary).toMatchObject({
      keepDaily: 5,
      primary: 0,
      secondary: 5,
      hold: 2,
      excluded: 5,
      canonicalPrimaryDatesBefore: 182,
      canonicalPrimaryDatesAfter: 182,
      currentVisiblePrimaryCoverage: 168,
    });
    expect(JSON.stringify(reviewWave.keepDaily).toLowerCase()).not.toContain("muore");
    expect(reviewWave.keepDaily.every((record) => record.sourceStatus === "pass")).toBe(true);
  });

  it("uses unique candidates and records the semantic duplicate explicitly", () => {
    const ids = allReviewedRecords().map((record) => record.id);
    const wikidataIds = reviewWave.keepDaily.map((record) => record.wikidataId);
    expect(new Set(ids).size).toBe(ids.length);
    expect(new Set(wikidataIds).size).toBe(wikidataIds.length);

    const lella = reviewWave.excluded.find((record) => record.id === "master-fvg-13-08-Q6520921");
    expect(lella?.reason).toContain("Duplicato semantico");
    expect(localMemory.records.filter((record) => record.id === "memory-copy-0813-lella-vignelli")).toHaveLength(1);
  });

  it("allows the two distinct 16 June memories and preserves their importance order", () => {
    const june16 = reviewWave.keepDaily
      .filter((record) => record.dateIt === "16-06")
      .sort((a, b) => b.priority - a.priority);

    expect(june16.map((record) => record.id)).toEqual([
      "master-fvg-16-06-Q88782529",
      "master-fvg-16-06-Q12794563",
    ]);
  });

  it("maps each selected candidate to one canonical promoted record", () => {
    const recordsByCandidateId = new Map(
      localMemory.records
        .filter((record) => record.candidateId)
        .map((record) => [record.candidateId, record]),
    );

    for (const candidate of reviewWave.keepDaily) {
      const record = recordsByCandidateId.get(candidate.id);
      expect(record).toBeTruthy();
      expect(record.dateAnchors).toEqual([toRuntimeDateKey(candidate.dateIt)]);
      expect(record.dailyRole).toBe("secondary");
      expect(record.languageStatus).toMatchObject({
        it: "approved",
        fur: "approved",
      });
      expect(record.source).toMatchObject({
        type: "verified_source",
        wikidataId: candidate.wikidataId,
      });
      expect(record.readyForUi).toBe(true);
    }
  });
});
