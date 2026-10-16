import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyItalianReviewWave13.json";

function toRuntimeDateKey(dateIt) {
  const [day, month] = dateIt.split("-");
  return `${month}-${day}`;
}

function allRecords() {
  return [
    ...reviewWave.keepDaily,
    ...reviewWave.hold,
  ];
}

describe("Discover daily Italian review wave 13", () => {
  it("keeps the selected Italian records blocked until FUR approval", () => {
    expect(reviewWave.policy).toMatchObject({
      readyForUi: false,
      furDeferred: true,
      dateFormat: "DD-MM",
      excludeDeaths: true,
      excludeGenericPoliticalProfiles: true,
      excludeAlreadyReviewedProfiles: true,
      sourceFirst: true,
      publishAfterFurOnly: true,
      allowMultipleMemoriesPerDate: true,
      secondaryOrderedByPriority: true,
    });
    expect(allRecords().every((record) => record.readyForUi === false || !("readyForUi" in record))).toBe(true);
    expect(JSON.stringify(reviewWave)).not.toContain('"fur"');
  });

  it("contains fifteen new records and explicit editorial exclusions", () => {
    expect(reviewWave.keepDaily).toHaveLength(15);
    expect(reviewWave.keepDaily.filter((record) => record.dailyRole === "primary")).toHaveLength(14);
    expect(reviewWave.keepDaily.filter((record) => record.dailyRole === "secondary")).toHaveLength(1);
    expect(reviewWave.hold).toHaveLength(4);
    expect(reviewWave.summary).toMatchObject({
      keepDaily: 15,
      primary: 14,
      secondary: 1,
      hold: 4,
      potentialPrimaryCoverageBefore: 149,
      potentialPrimaryCoverageAfter: 163,
      currentVisiblePrimaryCoverage: 149,
    });

    const ids = allRecords().map((record) => record.id);
    expect(new Set(ids).size).toBe(ids.length);
    expect(JSON.stringify(reviewWave.keepDaily).toLowerCase()).not.toContain("muore");
    expect(reviewWave.keepDaily.every((record) => record.sourceStatus === "pass")).toBe(true);
  });

  it("orders two 8 October memories with Picco primary and Ellero secondary", () => {
    expect(reviewWave.keepDaily).toEqual(expect.arrayContaining([
      expect.objectContaining({
        id: "master-fvg-08-10-Q55946337",
        dailyRole: "primary",
        priority: 48,
      }),
      expect.objectContaining({
        id: "master-fvg-08-10-Q3903853",
        dailyRole: "secondary",
        priority: 64,
      }),
    ]));
  });

  it("maps every reviewed date to exactly one canonical record", () => {
    const recordsByCandidateId = new Map(
      localMemory.records
        .filter((record) => record.candidateId)
        .map((record) => [record.candidateId, record]),
    );
    const primaryDates = reviewWave.keepDaily
      .filter((record) => record.dailyRole === "primary")
      .map((record) => toRuntimeDateKey(record.dateIt));

    expect(new Set(primaryDates).size).toBe(primaryDates.length);
    expect(reviewWave.keepDaily.every((candidate) => (
      recordsByCandidateId.get(candidate.id)?.dateAnchors?.[0] === toRuntimeDateKey(candidate.dateIt)
    ))).toBe(true);
    expect(reviewWave.keepDaily.every((record) => /^\d{2}-\d{2}$/.test(record.dateIt))).toBe(true);
  });

  it("documents only records published after complete IT and FUR review", () => {
    const recordsByCandidateId = new Map(
      localMemory.records
        .filter((record) => record.candidateId)
        .map((record) => [record.candidateId, record]),
    );
    const promotedRecords = reviewWave.keepDaily.map((candidate) => recordsByCandidateId.get(candidate.id));

    expect(promotedRecords.every(Boolean)).toBe(true);
    expect(promotedRecords.every((record) => (
      record.editorialStatus === "ready_for_discover"
      && record.languageStatus?.it === "approved"
      && record.languageStatus?.fur === "approved"
      && record.readyForUi === true
      && record.source?.type === "verified_source"
    ))).toBe(true);
  });
});
