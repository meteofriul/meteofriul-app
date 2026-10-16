import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyItalianReviewWave2.json";

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

describe("Discover daily Italian review wave 2", () => {
  it("keeps the new IT wave hidden until FUR review", () => {
    expect(reviewWave.policy).toMatchObject({
      readyForUi: false,
      furDeferred: true,
      dateFormat: "DD-MM",
      sourceFirst: true,
    });
    expect(allRecords().every((record) => record.readyForUi === false)).toBe(true);
    expect(JSON.stringify(reviewWave)).not.toContain('"fur"');
  });

  it("documents a small selected batch and explicit holds", () => {
    expect(reviewWave.keepDaily).toHaveLength(6);
    expect(reviewWave.hold).toHaveLength(2);
    expect(reviewWave.summary).toMatchObject({
      keepDaily: 6,
      hold: 2,
      potentialPrimaryCoverageBefore: 45,
      potentialPrimaryCoverageAfter: 51,
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
    const candidateDates = reviewWave.keepDaily.map((record) => toRuntimeDateKey(record.dateIt));

    expect(new Set(candidateDates).size).toBe(candidateDates.length);
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
  });
});
