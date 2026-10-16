import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyItalianReviewWave20.json";

function toRuntimeDateKey(dateIt) {
  const [day, month] = dateIt.split("-");
  return `${month}-${day}`;
}

describe("Discover daily Italian review wave 20", () => {
  it("keeps the Italian selection blocked until FUR approval", () => {
    expect(reviewWave.policy).toMatchObject({
      readyForUi: false,
      furDeferred: true,
      dateFormat: "DD-MM",
      excludeDeaths: true,
      excludeGenericPoliticalProfiles: true,
      excludeGenericProfessionalProfiles: true,
      rejectSemanticDuplicates: true,
      rejectUncertainCalendarDates: true,
      sourceFirst: true,
      publishAfterFurOnly: true,
      allowMultipleMemoriesPerDate: true,
      allowVerifiedNonWikidataEntity: true,
    });
    expect(reviewWave.keepDaily.every((record) => record.readyForUi === false)).toBe(true);
    expect(JSON.stringify(reviewWave)).not.toContain('"fur"');
  });

  it("selects ten substantial profiles and opens six uncovered primary dates", () => {
    expect(reviewWave.keepDaily).toHaveLength(10);
    expect(reviewWave.keepDaily.filter((record) => record.dailyRole === "primary")).toHaveLength(6);
    expect(reviewWave.keepDaily.filter((record) => record.dailyRole === "secondary")).toHaveLength(4);
    expect(reviewWave.hold).toEqual([]);
    expect(reviewWave.excluded).toEqual([]);
    expect(reviewWave.summary).toMatchObject({
      keepDaily: 10,
      primary: 6,
      secondary: 4,
      canonicalPrimaryDatesBefore: 182,
      canonicalPrimaryDatesAfter: 188,
      currentVisiblePrimaryCoverage: 174,
    });
    expect(JSON.stringify(reviewWave.keepDaily).toLowerCase()).not.toContain("muore");
    expect(reviewWave.keepDaily.every((record) => record.sourceStatus === "pass")).toBe(true);
  });

  it("uses unique source entities and authoritative URLs", () => {
    const ids = reviewWave.keepDaily.map((record) => record.id);
    const entityIds = reviewWave.keepDaily.map((record) => record.sourceEntityId || record.wikidataId);
    const sourceUrls = reviewWave.keepDaily.map((record) => record.sourceUrl);

    expect(new Set(ids).size).toBe(ids.length);
    expect(new Set(entityIds).size).toBe(entityIds.length);
    expect(new Set(sourceUrls).size).toBe(sourceUrls.length);
    expect(reviewWave.keepDaily.find((record) => record.titleIt.startsWith("Giuseppe Marchetti"))).toMatchObject({
      sourceEntityId: "dbf-marchetti-giuseppe",
      sourceLabel: "Dizionario Biografico dei Friulani",
    });
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
      expect(record.dailyRole).toBe(candidate.dailyRole);
      expect(record.languageStatus).toMatchObject({
        it: "approved",
        fur: "approved",
      });
      expect(record.source).toMatchObject({
        type: "verified_source",
        entityId: candidate.sourceEntityId || candidate.wikidataId,
      });
      expect(record.readyForUi).toBe(true);
    }
  });
});
