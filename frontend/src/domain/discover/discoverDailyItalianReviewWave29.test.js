import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyItalianReviewWave29.json";

function toRuntimeDateKey(dateIt) {
  const [day, month] = dateIt.split("-");
  return `${month}-${day}`;
}

describe("Discover daily Italian review wave 29", () => {
  it("keeps the Italian selection blocked until FUR approval", () => {
    expect(reviewWave.policy).toMatchObject({
      readyForUi: false,
      furDeferred: true,
      dateFormat: "DD-MM",
      excludeDeaths: true,
      excludeGenericPoliticalProfiles: true,
      excludeGenericProfessionalProfiles: true,
      excludeSportsOnlyProfiles: true,
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

  it("records all one hundred twenty audited decisions without overlap", () => {
    const primary = reviewWave.keepDaily.filter((record) => record.dailyRole === "primary");
    const secondary = reviewWave.keepDaily.filter((record) => record.dailyRole === "secondary");
    const decisionIds = [
      ...reviewWave.keepDaily.map((record) => record.id),
      ...reviewWave.hold.map((record) => record.id),
      ...reviewWave.excluded.map((record) => record.id),
    ];

    expect(reviewWave.keepDaily).toHaveLength(15);
    expect(primary).toHaveLength(6);
    expect(secondary).toHaveLength(9);
    expect(reviewWave.hold).toHaveLength(31);
    expect(reviewWave.excluded).toHaveLength(74);
    expect(decisionIds).toHaveLength(120);
    expect(new Set(decisionIds).size).toBe(decisionIds.length);
    expect(reviewWave.summary).toMatchObject({
      reviewed: 120,
      keepDaily: 15,
      primary: 6,
      secondary: 9,
      hold: 31,
      excluded: 74,
      canonicalPrimaryDatesBefore: 220,
      canonicalPrimaryDatesAfter: 226,
      currentVisiblePrimaryCoverage: 218,
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
    expect(reviewWave.keepDaily.every((record) => (
      !record.titleIt.includes("?")
      && !record.copyIt.includes("?")
      && !record.sourceLabel.includes("?")
    ))).toBe(true);
  });

  it("maps each selected candidate to one canonical record after Italian staging", () => {
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
      expect(record.title.it).toBe(candidate.titleIt);
      expect(record.summary.it).toBe(candidate.copyIt);
      expect(record.languageStatus).toMatchObject({
        it: "approved",
        fur: expect.stringMatching(/^(human_review_needed|approved)$/),
      });
      expect(record.source).toMatchObject({
        type: "verified_source",
        entityId: candidate.wikidataId,
        url: candidate.sourceUrl,
      });
    }
  });
});
