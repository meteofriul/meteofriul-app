import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyItalianReviewWave64.json";

function toRuntimeDateKey(dateIt) {
  const [day, month] = dateIt.split("-");
  return `${month}-${day}`;
}

describe("Discover daily Italian review wave 64", () => {
  it("selects one sourced primary memory for 19 May", () => {
    expect(reviewWave.policy).toMatchObject({
      dateFormat: "DD-MM",
      furDeferred: true,
      sourceFirst: true,
      publishAfterFurOnly: true,
      rejectUncertainCalendarDates: true,
    });
    expect(reviewWave.summary).toEqual({
      reviewed: 1,
      keepDaily: 1,
      primary: 1,
      secondary: 0,
      hold: 0,
      excluded: 0,
      canonicalPrimaryDatesBefore: 313,
      canonicalPrimaryDatesAfter: 314,
      currentVisiblePrimaryCoverage: 313,
    });
    expect(reviewWave.keepDaily[0]).toMatchObject({
      dateIt: "19-05",
      dailyRole: "primary",
      sourceStatus: "pass",
      readyForUi: false,
    });
  });

  it("publishes the canonical record only after bilingual approval", () => {
    const selected = reviewWave.keepDaily[0];
    const dateKey = toRuntimeDateKey(selected.dateIt);
    const canonical = localMemory.records.filter((record) => record.candidateId === selected.id);
    const competingReadyPrimary = localMemory.records.find((record) => (
      record.candidateId !== selected.id
      && record.dailyRole !== "secondary"
      && record.primaryUse === "discover"
      && record.readyForUi === true
      && record.dateAnchors?.includes(dateKey)
    ));

    expect(selected.sourceUrl).toMatch(/^https:\/\//);
    expect(selected.sourceUrl).not.toContain("wikipedia.org");
    expect(competingReadyPrimary).toBeUndefined();
    expect(canonical).toHaveLength(1);
    expect(canonical[0]).toMatchObject({
      dailyRole: "primary",
      dateAnchors: ["05-19"],
      editorialStatus: "ready_for_discover",
      languageStatus: { it: "approved", fur: "approved" },
      readyForUi: true,
    });
  });
});
