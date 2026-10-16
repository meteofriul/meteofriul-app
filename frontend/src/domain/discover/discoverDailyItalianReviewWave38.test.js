import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyItalianReviewWave38.json";

function toRuntimeDateKey(dateIt) {
  const [day, month] = dateIt.split("-");
  return `${month}-${day}`;
}

describe("Discover daily Italian review wave 38", () => {
  it("keeps the Italian selection blocked until FUR approval", () => {
    expect(reviewWave.policy).toMatchObject({
      readyForUi: false,
      furDeferred: true,
      dateFormat: "DD-MM",
      excludeDeaths: true,
      excludeGenericPoliticalProfiles: true,
      excludeGenericProfessionalProfiles: true,
      excludeSportsOnlyProfiles: true,
      rejectBirthplaceOnlyProfiles: true,
      sourceFirst: true,
      publishAfterFurOnly: true,
      doNotPromoteToPrimaryForCoverageOnly: true,
    });
    expect(reviewWave.keepDaily).toHaveLength(1);
    expect(reviewWave.keepDaily[0].readyForUi).toBe(false);
    expect(JSON.stringify(reviewWave.keepDaily)).not.toContain('"fur"');
  });

  it("records fifteen audited decisions without overlap", () => {
    const decisionIds = [
      ...reviewWave.keepDaily.map((record) => record.id),
      ...reviewWave.hold.map((record) => record.id),
      ...reviewWave.excluded.map((record) => record.id),
    ];

    expect(reviewWave.keepDaily.filter((record) => record.dailyRole === "primary")).toHaveLength(0);
    expect(reviewWave.keepDaily.filter((record) => record.dailyRole === "secondary")).toHaveLength(1);
    expect(reviewWave.hold).toEqual([]);
    expect(reviewWave.excluded).toHaveLength(14);
    expect(decisionIds).toHaveLength(15);
    expect(new Set(decisionIds).size).toBe(decisionIds.length);
    expect(reviewWave.summary).toEqual({
      reviewed: 15,
      keepDaily: 1,
      primary: 0,
      secondary: 1,
      hold: 0,
      excluded: 14,
      canonicalPrimaryDatesBefore: 238,
      canonicalPrimaryDatesAfter: 238,
      currentVisiblePrimaryCoverage: 231,
    });
  });

  it("keeps Gasparotto secondary without replacing the Peteano primary memory", () => {
    const selected = reviewWave.keepDaily[0];
    const dateKey = toRuntimeDateKey(selected.dateIt);
    const sameDateRecords = localMemory.records.filter((record) => record.dateAnchors?.includes(dateKey));
    const existingPrimary = sameDateRecords.find((record) => record.dailyRole !== "secondary");
    const existingSecondary = sameDateRecords.find((record) => (
      record.candidateId === "master-fvg-31-05-Q3702403"
    ));

    expect(selected).toMatchObject({
      id: "master-fvg-31-05-Q3839683",
      dateIt: "31-05",
      municipality: "Sacile",
      province: "PN",
      dailyRole: "secondary",
      priority: 95,
    });
    expect(existingPrimary).toMatchObject({
      candidateId: "wave-history-0531-strage-peteano",
      dailyRole: "primary",
    });
    expect(selected.priority).toBeGreaterThan(existingSecondary.priority);
    expect(reviewWave.summary.canonicalPrimaryDatesAfter).toBe(
      reviewWave.summary.canonicalPrimaryDatesBefore,
    );
  });

  it("uses an explicit territory and an institutional non-Wikipedia source", () => {
    const selected = reviewWave.keepDaily[0];

    expect(selected.sourceStatus).toBe("pass");
    expect(selected.municipality).toBe("Sacile");
    expect(selected.province).toBe("PN");
    expect(selected.sourceUrl).toContain("consiglio.regione.fvg.it");
    expect(selected.sourceUrl).not.toContain("wikipedia.org");
    expect(selected.sourceUrl).not.toContain("wikidata.org");
    expect(selected.copyIt).toContain(String(selected.year));
  });

  it("rejects ordinary sport, generic profiles, birthplace-only ties and source mismatch", () => {
    const excludedIds = new Set(reviewWave.excluded.map((record) => record.id));

    expect(excludedIds).toContain("master-fvg-23-06-Q16039218");
    expect(excludedIds).toContain("master-fvg-23-10-Q933243");
    expect(excludedIds).toContain("master-fvg-24-05-Q3620333");
    expect(excludedIds).toContain("master-fvg-26-05-Q2114260");
    expect(excludedIds).toContain("master-fvg-19-07-Q7454409");
    expect(reviewWave.hold).toEqual([]);
  });

  it("maps the selected candidate to one canonical reviewed record", () => {
    const selected = reviewWave.keepDaily[0];
    const records = localMemory.records.filter((record) => record.candidateId === selected.id);

    expect(records).toHaveLength(1);
    expect(records[0]).toMatchObject({
      dateAnchors: [toRuntimeDateKey(selected.dateIt)],
      dailyRole: selected.dailyRole,
      priority: selected.priority,
      languageStatus: {
        it: "approved",
        fur: "approved",
      },
      title: {
        it: selected.titleIt,
      },
      summary: {
        it: selected.copyIt,
      },
    });
  });
});
