import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyItalianReviewWave15.json";

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

describe("Discover daily Italian review wave 15", () => {
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
      rejectUncertainCalendarDates: true,
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
    expect(reviewWave.keepDaily.filter((record) => record.dailyRole === "primary")).toHaveLength(5);
    expect(reviewWave.keepDaily.filter((record) => record.dailyRole === "secondary")).toHaveLength(5);
    expect(reviewWave.hold).toHaveLength(3);
    expect(reviewWave.summary).toMatchObject({
      keepDaily: 10,
      primary: 5,
      secondary: 5,
      hold: 3,
      potentialPrimaryCoverageBefore: 169,
      potentialPrimaryCoverageAfter: 174,
      currentVisiblePrimaryCoverage: 163,
    });

    const ids = allRecords().map((record) => record.id);
    const wikidataIds = reviewWave.keepDaily.map((record) => record.wikidataId);
    expect(new Set(ids).size).toBe(ids.length);
    expect(new Set(wikidataIds).size).toBe(wikidataIds.length);
    expect(JSON.stringify(reviewWave.keepDaily).toLowerCase()).not.toContain("muore");
    expect(reviewWave.keepDaily.every((record) => record.sourceStatus === "pass")).toBe(true);
  });

  it("adds five uncovered dates and keeps five explicit secondary memories", () => {
    const primaryDates = reviewWave.keepDaily
      .filter((record) => record.dailyRole === "primary")
      .map((record) => toRuntimeDateKey(record.dateIt));

    expect(new Set(primaryDates).size).toBe(primaryDates.length);
    expect(primaryDates).toEqual(expect.arrayContaining([
      "09-27",
      "06-12",
      "11-19",
      "02-17",
      "09-18",
    ]));
    expect(reviewWave.keepDaily.filter((record) => record.dailyRole === "secondary").map((record) => record.id)).toEqual([
      "master-fvg-04-08-Q114492",
      "master-fvg-18-04-Q16559795",
      "master-fvg-20-09-Q743984",
      "master-fvg-20-12-Q1236933",
      "master-fvg-10-09-Q246373",
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

    const regionalRecord = recordsByCandidateId.get("master-fvg-10-09-Q246373");
    expect(regionalRecord.areas).toEqual(expect.arrayContaining(["friuli_venezia_giulia", "fvg"]));
    expect(regionalRecord.areas).not.toContain("udine");
  });
});
