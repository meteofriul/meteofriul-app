import { describe, expect, it } from "vitest";

import furReview from "../../data/discover/discoverDailyFurReviewWave60.json";
import italianReview from "../../data/discover/discoverDailyItalianReviewWave60.json";
import localMemory from "../../data/discover/localMemory.json";

describe("Discover daily FUR review wave 60", () => {
  it("approves all fifteen Italian selections without pending entries", () => {
    expect(furReview.summary).toEqual({
      totalRecords: 15,
      approved: 15,
      pendingHumanReview: 0,
    });
    expect(furReview.records.every((record) => record.status === "approved")).toBe(true);
  });

  it("covers exactly the canonical records selected in Italian", () => {
    const expectedIds = italianReview.keepDaily.map((selected) => (
      localMemory.records.find((record) => record.candidateId === selected.id)?.id
    ));

    expect(furReview.records.map((record) => record.id)).toEqual(expectedIds);
    expect(expectedIds.every(Boolean)).toBe(true);
  });

  it("publishes the approved bilingual copy without changing the Italian decisions", () => {
    for (const item of furReview.records) {
      const canonical = localMemory.records.find((record) => record.id === item.id);
      const selected = italianReview.keepDaily.find((record) => record.id === canonical?.candidateId);

      expect(canonical).toMatchObject({
        candidateId: selected?.id,
        dailyRole: "primary",
        priority: selected?.priority,
        editorialStatus: "ready_for_discover",
        languageStatus: { it: "approved", fur: "approved" },
        readyForUi: true,
        title: { it: selected?.titleIt, fur: item.titleFur },
        summary: { it: selected?.copyIt, fur: item.summaryFur },
      });
    }
  });

  it("uses established FUR territory and chronology", () => {
    const corpus = furReview.records.map((record) => `${record.titleFur} ${record.summaryFur}`).join(" ");

    expect(corpus).toContain("Pordenon");
    expect(corpus).toContain("Udin");
    expect(corpus).toContain("Gurize");
    expect(corpus).toContain("Triest");
    expect(corpus).toContain("Friûl Vignesie Julie");
    expect(corpus).toContain("Ai 24 di Fevrâr dal 1945");
    expect(corpus).toContain("Ai 14 di Març dal 1902");
  });
});
