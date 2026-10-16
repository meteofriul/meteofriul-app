import { describe, expect, it } from "vitest";
import institutionalRituals from "../../data/discover/institutionalRituals.json";
import backlog from "../../data/discover/ritualResearchBacklog.json";

describe("ritual research backlog", () => {
  it("keeps the approval trail linked to the promoted institutional records", () => {
    expect(backlog.records).toHaveLength(5);
    const promotedById = new Map(institutionalRituals.map((record) => [record.id, record]));
    const originalBatch = institutionalRituals.filter((record) => (
      backlog.records.some((lead) => lead.promotedRecordId === record.id)
    ));
    expect(originalBatch).toHaveLength(5);

    backlog.records.forEach((record) => {
      expect(record.readyForUi).toBe(false);
      expect(record.status).toMatch(/^approved_promoted_/);
      expect(record.approvalNote).toBeTruthy();
      expect(record.geographicScope.length).toBeGreaterThan(0);
      expect(record.temporalRule.type).toBeTruthy();
      expect(record.source.url).toMatch(/^https:\/\//);
      expect(record.source.type).toMatch(/archive|catalogue/);

      expect(promotedById.get(record.promotedRecordId)).toMatchObject({
        sourceId: record.id,
        section: "riti_credenze_popolari",
        editorialStatus: "ready_it",
        languageStatus: { it: "approved", fur: "approved" },
        sourceStatus: "controllato",
      });
    });
  });

  it("does not flatten local practices into a region-wide claim", () => {
    const cidulis = backlog.records.find((record) => record.id === "ritual-lead-cidulis-cercivento");
    const resianCarnival = backlog.records.find((record) => record.id === "ritual-lead-carnevale-resiano");

    expect(cidulis.geographicScope).toEqual(["Cercivento", "Carnia"]);
    expect(resianCarnival.geographicScope).toEqual(["Resia"]);
  });

  it("keeps all promoted copy complete and all movable periods explicit", () => {
    institutionalRituals.forEach((record) => {
      expect(record.title.it).toBeTruthy();
      expect(record.title.fur).toBeTruthy();
      expect(record.text.it).toBeTruthy();
      expect(record.text.fur).toBeTruthy();
      expect(record.source.url).toMatch(/^https:\/\//);
      expect(record.areas.length).toBeGreaterThan(0);
    });

    const movableRecords = institutionalRituals.filter((record) => (
      record.recurrence === "movable_range"
    ));
    expect(movableRecords).toHaveLength(3);
    expect(movableRecords.every((record) => record.movableDateRanges.length === 1)).toBe(true);
  });
});
