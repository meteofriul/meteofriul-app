import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyItalianReviewWave.json";

function toRuntimeDateKey(dateIt) {
  const [day, month] = dateIt.split("-");
  return `${month}-${day}`;
}

function allRecords() {
  return [
    ...reviewWave.keepDaily,
    ...reviewWave.demoteArchive,
    ...reviewWave.reuseExisting,
    ...reviewWave.hold,
  ];
}

describe("Discover daily Italian review wave", () => {
  it("remains outside runtime and defers FUR", () => {
    expect(reviewWave.policy).toMatchObject({
      readyForUi: false,
      furDeferred: true,
      dateFormat: "DD-MM",
    });
    expect(allRecords().every((record) => record.readyForUi === false)).toBe(true);
    expect(JSON.stringify(reviewWave)).not.toContain('"fur"');
  });

  it("contains the reconciled decisions", () => {
    expect(reviewWave.keepDaily).toHaveLength(12);
    expect(reviewWave.demoteArchive).toHaveLength(3);
    expect(reviewWave.reuseExisting).toHaveLength(3);
    expect(reviewWave.hold).toHaveLength(1);

    const ids = allRecords().map((record) => record.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("maps its unique Italian dates to the canonical runtime dates", () => {
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

  it("keeps Italian copy canonical while FUR controls publication", () => {
    const recordsByCandidateId = new Map(
      localMemory.records
        .filter((record) => record.candidateId)
        .map((record) => [record.candidateId, record]),
    );
    const promotedRecords = reviewWave.keepDaily.map((candidate) => recordsByCandidateId.get(candidate.id));

    expect(promotedRecords.every(Boolean)).toBe(true);
    expect(promotedRecords.every((record) => (
      record.languageStatus?.it === "approved" && record.source?.type === "verified_source"
    ))).toBe(true);
    expect(promotedRecords.filter((record) => (
      record.editorialStatus === "ready_for_discover"
      && record.languageStatus?.fur === "approved"
      && record.readyForUi === true
    ))).toHaveLength(12);
    expect(promotedRecords.filter((record) => (
      record.editorialStatus === "source_verified"
      && record.languageStatus?.fur === "human_review_needed"
      && record.readyForUi === false
    ))).toHaveLength(0);
  });
});
