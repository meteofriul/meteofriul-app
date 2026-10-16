import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyItalianReviewWave31.json";

function toRuntimeDateKey(dateIt) {
  const [day, month] = dateIt.split("-");
  return `${month}-${day}`;
}

const MONTHS_IT = [
  "gennaio",
  "febbraio",
  "marzo",
  "aprile",
  "maggio",
  "giugno",
  "luglio",
  "agosto",
  "settembre",
  "ottobre",
  "novembre",
  "dicembre",
];

describe("Discover daily Italian review wave 31", () => {
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

  it("records fifteen audited decisions without overlap", () => {
    const primary = reviewWave.keepDaily.filter((record) => record.dailyRole === "primary");
    const secondary = reviewWave.keepDaily.filter((record) => record.dailyRole === "secondary");
    const decisionIds = [
      ...reviewWave.keepDaily.map((record) => record.id),
      ...reviewWave.hold.map((record) => record.id),
      ...reviewWave.excluded.map((record) => record.id),
    ];

    expect(reviewWave.keepDaily).toHaveLength(11);
    expect(primary).toHaveLength(6);
    expect(secondary).toHaveLength(5);
    expect(reviewWave.hold).toHaveLength(4);
    expect(reviewWave.excluded).toHaveLength(0);
    expect(decisionIds).toHaveLength(15);
    expect(new Set(decisionIds).size).toBe(decisionIds.length);
    expect(reviewWave.summary).toMatchObject({
      reviewed: 15,
      keepDaily: 11,
      primary: 6,
      secondary: 5,
      hold: 4,
      excluded: 0,
      canonicalPrimaryDatesBefore: 229,
      canonicalPrimaryDatesAfter: 235,
      currentVisiblePrimaryCoverage: 221,
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

  it("keeps every structured Italian date aligned with the published copy", () => {
    for (const candidate of reviewWave.keepDaily) {
      const [day, month] = candidate.dateIt.split("-").map(Number);
      expect(candidate.copyIt.toLocaleLowerCase("it")).toContain(`${day} ${MONTHS_IT[month - 1]}`);
    }

    const robortello = reviewWave.keepDaily.find((record) => record.wikidataId === "Q1751281");
    expect(robortello).toMatchObject({
      id: "master-fvg-19-09-Q1751281",
      dateIt: "09-09",
    });
    expect(robortello.dateAuditNote).toContain("ID del candidato sorgente");
  });

  it("keeps known date conflicts out of canonical staging", () => {
    const heldIds = new Set(reviewWave.hold.map((record) => record.id));
    const selectedIds = new Set(reviewWave.keepDaily.map((record) => record.id));

    expect(heldIds).toContain("master-fvg-09-11-Q543158");
    expect(heldIds).toContain("master-fvg-17-06-Q3703633");
    expect(selectedIds.has("master-fvg-09-11-Q543158")).toBe(false);
    expect(selectedIds.has("master-fvg-17-06-Q3703633")).toBe(false);
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
