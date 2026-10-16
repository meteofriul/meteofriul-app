import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyItalianReviewWave14.json";

function toRuntimeDateKey(dateIt) {
  const [day, month] = dateIt.split("-");
  return `${month}-${day}`;
}

function allRecords() {
  return [
    ...reviewWave.keepDaily,
    ...reviewWave.hold,
  ];
}

describe("Discover daily Italian review wave 14", () => {
  it("keeps the selected Italian records blocked until FUR approval", () => {
    expect(reviewWave.policy).toMatchObject({
      readyForUi: false,
      furDeferred: true,
      dateFormat: "DD-MM",
      excludeDeaths: true,
      excludeGenericPoliticalProfiles: true,
      excludeGenericProfessionalProfiles: true,
      excludeAlreadyReviewedProfiles: true,
      rejectSemanticDuplicates: true,
      sourceFirst: true,
      publishAfterFurOnly: true,
      allowMultipleMemoriesPerDate: true,
      secondaryOrderedByPriority: true,
    });
    expect(allRecords().every((record) => record.readyForUi === false || !("readyForUi" in record))).toBe(true);
    expect(JSON.stringify(reviewWave)).not.toContain('"fur"');
  });

  it("contains ten selected records and documents the deferred candidates", () => {
    expect(reviewWave.keepDaily).toHaveLength(10);
    expect(reviewWave.keepDaily.filter((record) => record.dailyRole === "primary")).toHaveLength(6);
    expect(reviewWave.keepDaily.filter((record) => record.dailyRole === "secondary")).toHaveLength(4);
    expect(reviewWave.hold).toHaveLength(3);
    expect(reviewWave.summary).toMatchObject({
      keepDaily: 10,
      primary: 6,
      secondary: 4,
      hold: 3,
      potentialPrimaryCoverageBefore: 163,
      potentialPrimaryCoverageAfter: 169,
      currentVisiblePrimaryCoverage: 163,
    });

    const ids = allRecords().map((record) => record.id);
    const wikidataIds = reviewWave.keepDaily.map((record) => record.wikidataId);
    expect(new Set(ids).size).toBe(ids.length);
    expect(new Set(wikidataIds).size).toBe(wikidataIds.length);
    expect(JSON.stringify(reviewWave.keepDaily).toLowerCase()).not.toContain("muore");
    expect(reviewWave.keepDaily.every((record) => record.sourceStatus === "pass")).toBe(true);
  });

  it("adds six uncovered dates and keeps four explicit secondary memories", () => {
    const primaryDates = reviewWave.keepDaily
      .filter((record) => record.dailyRole === "primary")
      .map((record) => toRuntimeDateKey(record.dateIt));

    expect(new Set(primaryDates).size).toBe(primaryDates.length);
    expect(primaryDates).toEqual(expect.arrayContaining([
      "11-04",
      "12-16",
      "10-26",
      "06-28",
      "07-18",
      "06-19",
    ]));
    expect(reviewWave.keepDaily.filter((record) => record.dailyRole === "secondary").map((record) => record.id)).toEqual([
      "master-fvg-03-07-Q3886735",
      "master-fvg-08-07-Q5235256",
      "master-fvg-16-05-Q3770239",
      "master-fvg-30-11-Q3548105",
    ]);
  });

  it("maps each reviewed candidate to one canonical staged record", () => {
    const recordsByCandidateId = new Map(
      localMemory.records
        .filter((record) => record.candidateId)
        .map((record) => [record.candidateId, record]),
    );

    for (const candidate of reviewWave.keepDaily) {
      const record = recordsByCandidateId.get(candidate.id);
      expect(record).toBeTruthy();
      expect(record.dateAnchors).toEqual([toRuntimeDateKey(candidate.dateIt)]);
      expect(record.dailyRole).toBe(candidate.dailyRole);
      expect(record.languageStatus?.it).toBe("approved");
      expect(record.source?.type).toBe("verified_source");
      expect(record.source?.wikidataId).toBe(candidate.wikidataId);
      expect(record.readyForUi).toBe(record.languageStatus?.fur === "approved");
    }
  });
});
