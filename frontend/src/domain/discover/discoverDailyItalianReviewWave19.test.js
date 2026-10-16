import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyItalianReviewWave19.json";

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

describe("Discover daily Italian review wave 19", () => {
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

  it("keeps six sourced secondary memories without deaths or generic filler", () => {
    expect(reviewWave.keepDaily).toHaveLength(6);
    expect(reviewWave.keepDaily.every((record) => record.dailyRole === "secondary")).toBe(true);
    expect(reviewWave.hold).toHaveLength(4);
    expect(reviewWave.excluded).toHaveLength(0);
    expect(reviewWave.summary).toMatchObject({
      keepDaily: 6,
      primary: 0,
      secondary: 6,
      hold: 4,
      excluded: 0,
      canonicalPrimaryDatesBefore: 182,
      canonicalPrimaryDatesAfter: 182,
      currentVisiblePrimaryCoverage: 168,
    });
    expect(JSON.stringify(reviewWave.keepDaily).toLowerCase()).not.toContain("muore");
    expect(reviewWave.keepDaily.every((record) => record.sourceStatus === "pass")).toBe(true);
  });

  it("uses unique candidate, Wikidata and source identifiers", () => {
    const ids = allReviewedRecords().map((record) => record.id);
    const wikidataIds = reviewWave.keepDaily.map((record) => record.wikidataId);
    const sourceUrls = reviewWave.keepDaily.map((record) => record.sourceUrl);

    expect(new Set(ids).size).toBe(ids.length);
    expect(new Set(wikidataIds).size).toBe(wikidataIds.length);
    expect(new Set(sourceUrls).size).toBe(sourceUrls.length);
  });

  it("holds every disputed or unsupported calendar date", () => {
    const reasons = reviewWave.hold.map((record) => record.reason).join(" ");

    expect(reasons).toContain("primo gennaio");
    expect(reasons).toContain("16");
    expect(reasons.match(/manca ancora una fonte forte/g)).toHaveLength(2);
  });

  it("maps each selected candidate to one canonical bilingual record", () => {
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
