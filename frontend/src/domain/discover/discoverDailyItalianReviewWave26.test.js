import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyItalianReviewWave26.json";

function toRuntimeDateKey(dateIt) {
  const [day, month] = dateIt.split("-");
  return `${month}-${day}`;
}

describe("Discover daily Italian review wave 26", () => {
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
      secondaryOrderedByPriority: true,
    });
    expect(reviewWave.keepDaily.every((record) => record.readyForUi === false)).toBe(true);
    expect(JSON.stringify(reviewWave.keepDaily)).not.toContain('"fur"');
  });

  it("reviews fifteen candidates without forcing new calendar coverage", () => {
    const primary = reviewWave.keepDaily.filter((record) => record.dailyRole === "primary");
    const secondary = reviewWave.keepDaily.filter((record) => record.dailyRole === "secondary");

    expect(reviewWave.keepDaily).toHaveLength(5);
    expect(primary).toHaveLength(0);
    expect(secondary).toHaveLength(5);
    expect(reviewWave.hold).toHaveLength(4);
    expect(reviewWave.excluded).toHaveLength(6);
    expect(reviewWave.summary).toMatchObject({
      keepDaily: 5,
      primary: 0,
      secondary: 5,
      canonicalPrimaryDatesBefore: 214,
      canonicalPrimaryDatesAfter: 214,
      currentVisiblePrimaryCoverage: 206,
    });
    expect(JSON.stringify(reviewWave.keepDaily).toLowerCase()).not.toContain("muore");
  });

  it("keeps every selected record secondary on an already covered date", () => {
    const candidateIds = new Set(reviewWave.keepDaily.map((record) => record.id));
    const previousPrimaryDates = new Set(
      localMemory.records
        .filter((record) => (
          record.primaryUse === "discover"
          && record.dailyRole !== "secondary"
          && !candidateIds.has(record.candidateId)
        ))
        .flatMap((record) => record.dateAnchors || []),
    );

    for (const candidate of reviewWave.keepDaily) {
      expect(candidate.dailyRole).toBe("secondary");
      expect(previousPrimaryDates.has(toRuntimeDateKey(candidate.dateIt))).toBe(true);
    }
  });

  it("uses unique entities, verified sources and explicit territories", () => {
    const ids = reviewWave.keepDaily.map((record) => record.id);
    const entityIds = reviewWave.keepDaily.map((record) => record.wikidataId);
    const sourceUrls = reviewWave.keepDaily.map((record) => record.sourceUrl);

    expect(new Set(ids).size).toBe(ids.length);
    expect(new Set(entityIds).size).toBe(entityIds.length);
    expect(new Set(sourceUrls).size).toBe(sourceUrls.length);
    expect(reviewWave.keepDaily.every((record) => record.sourceStatus === "pass")).toBe(true);
    expect(reviewWave.keepDaily.every((record) => record.municipality && record.province)).toBe(true);
    expect(sourceUrls.every((url) => !url.includes("wikipedia.org") && !url.includes("wikidata.org"))).toBe(true);
  });

  it("maps each candidate to one canonical record promoted after FUR review", () => {
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
      expect(record.title.fur).not.toBe("pending_review");
      expect(record.summary.fur).not.toBe("pending_review");
      expect(record.source).toMatchObject({
        type: "verified_source",
        entityId: candidate.wikidataId,
        url: candidate.sourceUrl,
      });
      expect(record.editorialStatus).toBe("ready_for_discover");
      expect(record.readyForUi).toBe(true);
    }
  });
});
