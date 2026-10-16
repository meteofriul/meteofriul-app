import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyItalianReviewWave32.json";

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

describe("Discover daily Italian review wave 32", () => {
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
      doNotPromoteToPrimaryForCoverageOnly: true,
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

    expect(reviewWave.keepDaily).toHaveLength(5);
    expect(primary).toHaveLength(2);
    expect(secondary).toHaveLength(3);
    expect(reviewWave.hold).toHaveLength(3);
    expect(reviewWave.excluded).toHaveLength(7);
    expect(decisionIds).toHaveLength(15);
    expect(new Set(decisionIds).size).toBe(decisionIds.length);
    expect(reviewWave.summary).toEqual({
      reviewed: 15,
      keepDaily: 5,
      primary: 2,
      secondary: 3,
      hold: 3,
      excluded: 7,
      canonicalPrimaryDatesBefore: 235,
      canonicalPrimaryDatesAfter: 237,
      currentVisiblePrimaryCoverage: 227,
    });
    expect(JSON.stringify(reviewWave.keepDaily).toLowerCase()).not.toContain("muore");
  });

  it("uses primaries only on uncovered dates without inflating coverage with secondary records", () => {
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

    const primaryDates = reviewWave.keepDaily
      .filter((record) => record.dailyRole === "primary")
      .map((record) => toRuntimeDateKey(record.dateIt));

    expect(primaryDates).toEqual(["10-24", "09-29"]);
    expect(primaryDates.every((dateKey) => !previousPrimaryDates.has(dateKey))).toBe(true);
    expect(reviewWave.keepDaily.filter((record) => record.dailyRole === "secondary")).toHaveLength(3);
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

  it("keeps every structured Italian date aligned with the approved copy", () => {
    for (const candidate of reviewWave.keepDaily) {
      const [day, month] = candidate.dateIt.split("-").map(Number);
      expect(candidate.copyIt.toLocaleLowerCase("it")).toContain(`${day} ${MONTHS_IT[month - 1]}`);
    }
  });

  it("keeps uncertain biographies out and applies the agreed exclusions", () => {
    const heldIds = new Set(reviewWave.hold.map((record) => record.id));
    const excludedIds = new Set(reviewWave.excluded.map((record) => record.id));
    const selectedIds = new Set(reviewWave.keepDaily.map((record) => record.id));

    expect(heldIds).toEqual(new Set([
      "master-fvg-24-01-Q110914766",
      "master-fvg-27-11-Q45027750",
      "master-fvg-29-04-Q61896397",
    ]));
    expect(excludedIds).toContain("master-fvg-28-10-Q21833023");
    expect(excludedIds).toContain("master-fvg-29-04-Q3972288");
    expect(excludedIds).toContain("master-fvg-28-01-Q3992736");
    expect([...heldIds, ...excludedIds].every((id) => !selectedIds.has(id))).toBe(true);
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
