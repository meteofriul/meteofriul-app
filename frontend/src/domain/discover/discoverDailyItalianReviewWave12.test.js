import { describe, expect, it } from "vitest";

import localMemory from "../../data/discover/localMemory.json";
import reviewWave from "../../data/discover/discoverDailyItalianReviewWave12.json";

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

describe("Discover daily Italian review wave 12", () => {
  it("keeps the selected IT batch hidden until FUR review", () => {
    expect(reviewWave.policy).toMatchObject({
      readyForUi: false,
      furDeferred: true,
      dateFormat: "DD-MM",
      excludeDeaths: true,
      excludeGenericPoliticalProfiles: true,
      excludeWeakMediaProfiles: true,
      excludeWeakSportsProfiles: true,
      sourceFirst: true,
      publishAfterFurOnly: true,
      allowArchiveCandidateWhenHistoricallyStrong: true,
      allowMultipleMemoriesPerDate: true,
      secondaryOrderedByPriority: true,
    });
    expect(allRecords().every((record) => record.readyForUi === false || !("readyForUi" in record))).toBe(true);
    expect(JSON.stringify(reviewWave)).not.toContain('"fur"');
  });

  it("documents the selected scientific and cultural records with explicit holds", () => {
    expect(reviewWave.keepDaily).toHaveLength(15);
    expect(reviewWave.keepDaily.filter((record) => record.dailyRole === "primary")).toHaveLength(14);
    expect(reviewWave.keepDaily.filter((record) => record.dailyRole === "secondary")).toHaveLength(1);
    expect(reviewWave.hold).toHaveLength(6);
    expect(reviewWave.summary).toMatchObject({
      keepDaily: 15,
      primary: 14,
      secondary: 1,
      hold: 6,
      potentialPrimaryCoverageBefore: 135,
      potentialPrimaryCoverageAfter: 149,
      currentVisiblePrimaryCoverage: 135,
    });

    const ids = allRecords().map((record) => record.id);
    expect(new Set(ids).size).toBe(ids.length);
    expect(JSON.stringify(reviewWave.keepDaily).toLowerCase()).not.toContain("muore");
    expect(JSON.stringify(reviewWave.keepDaily).toLowerCase()).not.toContain("politico");
    expect(reviewWave.keepDaily.every((record) => record.sourceStatus === "pass")).toBe(true);
  });

  it("keeps same-date memories with an explicit editorial hierarchy", () => {
    expect(reviewWave.keepDaily).toEqual(expect.arrayContaining([
      expect.objectContaining({
        id: "master-fvg-10-04-Q10990586",
        dailyRole: "secondary",
        priority: 64,
      }),
      expect.objectContaining({
        id: "master-fvg-13-10-Q11909385",
        dailyRole: "primary",
        priority: 54,
      }),
    ]));
    expect(reviewWave.hold.map((record) => record.id)).not.toContain("master-fvg-10-04-Q10990586");
    expect(reviewWave.hold.map((record) => record.id)).not.toContain("master-fvg-13-10-Q11909385");
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
  });

  it("documents the records that were later published after FUR review", () => {
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
