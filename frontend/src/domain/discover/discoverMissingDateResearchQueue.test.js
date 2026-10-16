import { describe, expect, it } from "vitest";
import localMemory from "../../data/discover/localMemory.json";
import researchQueue from "../../data/discover/discoverMissingDateResearchQueue.json";
import secondPassReview from "../../data/discover/discoverMissingDateSecondPassReview.json";
import italianReviewWave25 from "../../data/discover/discoverDailyItalianReviewWave25.json";

const READY_SOURCE_TYPES = new Set(["verified_source", "editorial_note"]);

function readyPrimaryDateAnchors() {
  return new Set((localMemory.records || [])
    .filter((record) => (
      record.readyForUi === true
      && record.primaryUse === "discover"
      && record.editorialStatus === "ready_for_discover"
      && READY_SOURCE_TYPES.has(record.source?.type)
      && record.dailyRole !== "secondary"
    ))
    .flatMap((record) => record.dateAnchors || []));
}

describe("discover missing-date research queue", () => {
  it("tracks every uncovered primary day without publishing it", () => {
    const readyDates = readyPrimaryDateAnchors();
    const queueDates = researchQueue.records.map((record) => record.dateAnchor);

    expect(readyDates.size).toBe(366);
    expect(queueDates).toHaveLength(0);
    expect(new Set(queueDates).size).toBe(0);
    expect(queueDates.some((dateAnchor) => readyDates.has(dateAnchor))).toBe(false);
    expect(researchQueue.records.every((record) => record.readyForUi === false)).toBe(true);
    expect(researchQueue.records.every((record) => record.editorialDecision === "pending")).toBe(true);
  });

  it("keeps Italian review dates separate from application date anchors", () => {
    for (const record of researchQueue.records) {
      expect(record.dateIt).toMatch(/^\d{2}-\d{2}$/);
      expect(record.dateAnchor).toMatch(/^\d{2}-\d{2}$/);

      const [month, day] = record.dateAnchor.split("-");
      expect(record.dateIt).toBe(`${day}-${month}`);
    }
  });

  it("sends every unresolved date to new-source research after the second pass", () => {
    const targetedSourceChecks = researchQueue.records
      .filter((record) => record.researchLane === "targeted_source_check");
    const newSource = researchQueue.records
      .filter((record) => record.researchLane === "research_new_source");
    const reviewedCandidates = researchQueue.records
      .flatMap((record) => record.reviewedCandidates);

    expect(targetedSourceChecks).toHaveLength(0);
    expect(newSource).toHaveLength(0);
    expect(reviewedCandidates).toHaveLength(0);
    expect(reviewedCandidates.every((candidate) => candidate.existingDecisions.length > 0)).toBe(true);
    expect(reviewedCandidates.every((candidate) => candidate.secondPassReview !== null)).toBe(true);
  });

  it("preserves the previous decisions and keeps Ida Vallerugo out without an exact date", () => {
    const idaVallerugo = secondPassReview.records
      .find((candidate) => candidate.wikidataId === "Q3791751");
    const idaOriginalHold = italianReviewWave25.hold
      .find((candidate) => candidate.id === "master-fvg-13-05-Q3791751");
    const scipioneDiManzano = secondPassReview.records
      .find((candidate) => candidate.wikidataId === "Q36834676");

    expect(idaVallerugo.decision).toBe("keep_for_archive");
    expect(idaVallerugo.reason).toContain("non il 13 maggio");
    expect(idaOriginalHold.reason).toContain("manca ancora una fonte autorevole");
    expect(scipioneDiManzano.reason).toContain("14 novembre");
  });

  it("keeps approved secondary memories secondary after their date gains a primary memory", () => {
    const secondaryMemories = researchQueue.records
      .flatMap((record) => record.readySecondaryMemories);
    const secondaryIds = secondaryMemories.map((record) => record.id);

    expect(secondaryMemories).toHaveLength(0);
    expect(secondaryMemories.every((record) => (
      record.secondPassReview?.decision === "keep_secondary"
    ))).toBe(true);
    expect(secondaryIds).toEqual([]);
    expect(localMemory.records.filter((record) => secondaryIds.includes(record.id)).every((record) => (
      record.dailyRole === "secondary"
    ))).toBe(true);
    expect(researchQueue.summary.completedPromotions).toBe(0);
    expect(researchQueue.summary.secondaryMemoriesKeptSecondary).toBe(0);
    expect(localMemory.records.find((record) => (
      record.id === "memory-it-ready-1223-olga-brunner-e-un-salotto-per-la-musica-europea"
    ))).toMatchObject({
      dailyRole: "secondary",
      readyForUi: true,
    });
    expect(localMemory.records.find((record) => (
      record.id === "memory-it-ready-0526-roberto-damiani-e-la-cultura-civile-di-trieste"
    ))).toMatchObject({
      dailyRole: "secondary",
      readyForUi: true,
    });
  });

  it("keeps one explicit and unambiguous decision for every second-pass candidate", () => {
    const candidateIds = secondPassReview.records.map((record) => record.sourceCandidateId);

    expect(secondPassReview.records).toHaveLength(14);
    expect(new Set(candidateIds).size).toBe(14);
    expect(secondPassReview.records.every((record) => record.decision)).toBe(true);
    expect(secondPassReview.records.every((record) => record.reason)).toBe(true);

    for (const record of secondPassReview.records) {
      const [month, day] = record.dateAnchor.split("-");
      expect(record.dateIt).toBe(`${day}-${month}`);
    }
  });
});
