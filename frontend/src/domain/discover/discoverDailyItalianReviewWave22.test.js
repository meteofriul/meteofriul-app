import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyItalianReviewWave22.json";

function toRuntimeDateKey(dateIt) {
  const [day, month] = dateIt.split("-");
  return `${month}-${day}`;
}

describe("Discover daily Italian review wave 22", () => {
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
    });
    expect(reviewWave.keepDaily.every((record) => record.readyForUi === false)).toBe(true);
    expect(JSON.stringify(reviewWave.keepDaily)).not.toContain('"fur"');
  });

  it("selects nine substantial memories with an explicit daily hierarchy", () => {
    const primary = reviewWave.keepDaily.filter((record) => record.dailyRole === "primary");
    const secondary = reviewWave.keepDaily.filter((record) => record.dailyRole === "secondary");

    expect(reviewWave.keepDaily).toHaveLength(9);
    expect(primary).toHaveLength(4);
    expect(secondary).toHaveLength(5);
    expect(reviewWave.hold).toHaveLength(10);
    expect(reviewWave.excluded).toHaveLength(1);
    expect(reviewWave.summary).toMatchObject({
      keepDaily: 9,
      primary: 4,
      secondary: 5,
      canonicalPrimaryDatesBefore: 203,
      canonicalPrimaryDatesAfter: 207,
      currentVisiblePrimaryCoverage: 195,
    });
    expect(JSON.stringify(reviewWave.keepDaily).toLowerCase()).not.toContain("muore");
  });

  it("uses primaries only on uncovered dates and secondaries on covered dates", () => {
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
      const dateKey = toRuntimeDateKey(candidate.dateIt);
      if (candidate.dailyRole === "primary") {
        expect(previousPrimaryDates.has(dateKey)).toBe(false);
      } else {
        expect(previousPrimaryDates.has(dateKey)).toBe(true);
      }
    }
  });

  it("uses unique entities, authoritative sources and explicit territories", () => {
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
      expect(record.dailyRole).toBe(candidate.dailyRole);
      expect(record.languageStatus).toMatchObject({
        it: "approved",
        fur: "approved",
      });
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
