import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyItalianReviewWave3.json";

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

describe("Discover daily Italian review wave 3", () => {
  it("keeps the wider IT batch hidden until FUR review", () => {
    expect(reviewWave.policy).toMatchObject({
      readyForUi: false,
      furDeferred: true,
      dateFormat: "DD-MM",
      sourceFirst: true,
      publishAfterFurOnly: true,
    });
    expect(allRecords().every((record) => record.readyForUi === false)).toBe(true);
    expect(JSON.stringify(reviewWave)).not.toContain('"fur"');
  });

  it("documents primary memories, secondary/archive items and explicit holds", () => {
    expect(reviewWave.keepDaily).toHaveLength(11);
    expect(reviewWave.keepDaily.filter((record) => record.dailyRole === "primary")).toHaveLength(7);
    expect(reviewWave.keepDaily.filter((record) => record.dailyRole === "secondary")).toHaveLength(4);
    expect(reviewWave.hold).toHaveLength(5);
    expect(reviewWave.summary).toMatchObject({
      keepDaily: 11,
      primary: 7,
      secondary: 4,
      hold: 5,
      potentialPrimaryCoverageBefore: 51,
      potentialPrimaryCoverageAfter: 58,
      currentVisiblePrimaryCoverage: 45,
    });

    const ids = allRecords().map((record) => record.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("maps selected Italian dates to canonical runtime records", () => {
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
    expect(reviewWave.keepDaily.every((record) => record.sourceStatus === "pass")).toBe(true);
  });

  it("keeps the promoted records visible only after approved FUR", () => {
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
    ))).toBe(true);
    expect(promotedRecords.filter((record) => record.dailyRole === "secondary")).toHaveLength(4);
  });
});
