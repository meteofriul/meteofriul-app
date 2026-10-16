import { describe, expect, it } from "vitest";
import catalogData from "../../data/discover/pilotWhyCatalog.json";
import record from "../../data/discover/pilotWhyPalmanova.json";
import {
  getPilotWhyContent,
  getPilotWhyContentById,
  getPilotWhyContentForDate,
} from "./pilotWhyContent";

describe("daily pilot why content", () => {
  it.each(["it", "fur"])("preserves the sourced and reviewed Palmanova %s record", language => {
    const content = getPilotWhyContent(language, record);
    expect(content.question).toBe(record.question[language]);
    expect(content.lead).toBe(record.lead[language]);
    expect(content.answer).toEqual(record.answer[language]);
    expect(content.anchor).toBe("discover-card-why-palmanova-star");
    expect(content.sources).toEqual(record.sources);
    expect(content.rubric).toBe(language === "fur" ? "I parcè dal Friûl" : "I perché del Friûl");
    expect(content.actionLabel).toContain(content.question);
  });

  it("selects the documented local-calendar record, including leap day", () => {
    expect(getPilotWhyContentForDate("it", "2026-09-08").id).toBe("why-222");
    expect(getPilotWhyContentForDate("it", "2026-09-09").id).toBe("why-257");
    expect(getPilotWhyContentForDate("fur", "2028-02-29").id).toBe("why-366");
    expect(getPilotWhyContentForDate("it", "2026-02-21").id).toBe("why-palmanova-star");
    expect(getPilotWhyContentForDate("it", "2026-02-21").sources).toEqual(record.sources);
  });

  it("keeps the selected identity available across midnight and language changes", () => {
    const clicked = getPilotWhyContentForDate("it", "2026-09-08");
    expect(getPilotWhyContentForDate("it", "2026-09-09").id).not.toBe(clicked.id);
    expect(getPilotWhyContentById("fur", clicked.id).id).toBe(clicked.id);
    expect(getPilotWhyContentById("it", clicked.id).anchor).toBe(clicked.anchor);
  });

  it("covers every calendar date with complete bilingual local content", () => {
    expect(catalogData.records).toHaveLength(366);
    expect(Object.keys(catalogData.schedule)).toHaveLength(366);
    for (const dateKey of Object.keys(catalogData.schedule)) {
      for (const language of ["it", "fur"]) {
        const content = getPilotWhyContentForDate(language, `2000-${dateKey}`);
        expect(content?.question).toBeTruthy();
        expect(content?.answer.length).toBeGreaterThan(0);
        expect(content?.sources[0].label).toBeTruthy();
        expect(JSON.stringify(content)).not.toMatch(/[\u3400-\u9fff]/u);
      }
    }
  });

  it("records, without guessing, the six duplicated and six unassigned source IDs", () => {
    expect(catalogData.metadata.scheduleWarnings).toEqual({
      duplicateScheduleIds: ["#80", "#110", "#186", "#290", "#303", "#340"],
      unassignedArchiveIds: ["#167", "#250", "#266", "#272", "#286", "#298"],
    });
  });

  it.each([
    null,
    { ...record, id: "" },
    { ...record, question: { it: " " } },
    { ...record, answer: { it: [] } },
    { ...record, answer: { it: [""] } },
    { ...record, sources: [] },
    { ...record, sources: [{ label: "unsafe", url: "javascript:alert(1)" }] },
  ])("does not offer incomplete or unsafe content (%#)", invalid => {
    expect(getPilotWhyContent("it", invalid)).toBeNull();
  });

  it("accepts a declared text source and does not share mutable values", () => {
    const imported = catalogData.records[1];
    expect(getPilotWhyContent("it", imported).sources[0]).toEqual({ label: imported.sources[0].label });
    expect(getPilotWhyContent("fur", { ...record, answer: { it: record.answer.it } })).toBeNull();
    const first = getPilotWhyContent("it", record);
    first.answer[0] = "Modified";
    first.sources[0].label = "Modified";
    expect(getPilotWhyContent("it", record).answer[0]).toBe(record.answer.it[0]);
    expect(getPilotWhyContent("it", record).sources[0].label).toBe(record.sources[0].label);
  });
});
