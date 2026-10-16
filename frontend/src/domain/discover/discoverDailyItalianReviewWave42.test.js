import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyItalianReviewWave42.json";

function toRuntimeDateKey(dateIt) {
  const [day, month] = dateIt.split("-");
  return `${month}-${day}`;
}

describe("Discover daily Italian review wave 42", () => {
  it("records all fifteen decisions with explicit daily roles", () => {
    const decisionIds = [
      ...reviewWave.keepDaily.map((record) => record.id),
      ...reviewWave.hold.map((record) => record.id),
      ...reviewWave.excluded.map((record) => record.id),
    ];

    expect(reviewWave.summary).toEqual({
      reviewed: 15,
      keepDaily: 12,
      primary: 9,
      secondary: 3,
      hold: 3,
      excluded: 0,
      canonicalPrimaryDatesBefore: 254,
      canonicalPrimaryDatesAfter: 263,
      currentVisiblePrimaryCoverage: 249,
    });
    expect(reviewWave.keepDaily.filter((record) => record.dailyRole === "primary")).toHaveLength(9);
    expect(reviewWave.keepDaily.filter((record) => record.dailyRole === "secondary")).toHaveLength(3);
    expect(decisionIds).toHaveLength(15);
    expect(new Set(decisionIds).size).toBe(15);
  });

  it("publishes one primary and three ordered secondary records on 6 July", () => {
    const selected = reviewWave.keepDaily.filter((record) => record.dateIt === "06-07");
    const primary = selected.filter((record) => record.dailyRole === "primary");
    const secondaryPriorities = selected
      .filter((record) => record.dailyRole === "secondary")
      .map((record) => record.priority);

    expect(primary).toHaveLength(1);
    expect(primary[0]).toMatchObject({ id: "master-fvg-06-07-Q19477276", priority: 99 });
    expect(secondaryPriorities).toEqual([96, 94, 89]);
  });

  it("maps every selection to one canonical published record", () => {
    for (const selected of reviewWave.keepDaily) {
      const canonicalRecords = localMemory.records.filter((record) => record.candidateId === selected.id);

      expect(canonicalRecords).toHaveLength(1);
      expect(canonicalRecords[0]).toMatchObject({
        dailyRole: selected.dailyRole,
        dateAnchors: [toRuntimeDateKey(selected.dateIt)],
        priority: selected.priority,
        editorialStatus: "ready_for_discover",
        languageStatus: { it: "approved", fur: "approved" },
        readyForUi: true,
      });
    }
  });

  it("keeps earlier archive records secondary to avoid date collisions", () => {
    const spaini = localMemory.records.find((record) => record.id === "memory-copy-0706-alberto-spaini");
    const camagni = localMemory.records.find((record) => record.id === "memory-copy-0325-giulio-camagni");

    expect(spaini?.dailyRole).toBe("secondary");
    expect(camagni?.dailyRole).toBe("secondary");
  });

  it("uses explicit territories and reviewed non-Wikimedia sources", () => {
    for (const selected of reviewWave.keepDaily) {
      expect(selected.sourceStatus).toBe("pass");
      expect(selected.municipality).toBeTruthy();
      expect(selected.province).toMatch(/^(GO|PN|TS|UD)$/);
      expect(selected.sourceUrl).not.toContain("wikipedia.org");
      expect(selected.sourceUrl).not.toContain("wikidata.org");
      expect(selected.copyIt).toContain(String(selected.year));
    }
  });

  it("does not create canonical records for the three held candidates", () => {
    const canonicalCandidateIds = new Set(localMemory.records.map((record) => record.candidateId));

    expect(reviewWave.hold).toHaveLength(3);
    for (const held of reviewWave.hold) {
      expect(canonicalCandidateIds.has(held.id)).toBe(false);
      expect(held.reason.length).toBeGreaterThan(40);
    }
  });
});
