import { afterEach, describe, expect, it, vi } from "vitest";
import proverbs from "../../data/almanac/proverbs.json";
import reuse from "../../data/discover/traditionalSayingAlmanacReuse.json";
import { getTraditionalSayingRecords } from "./traditionalSayings";

afterEach(() => {
  vi.doUnmock("../../data/almanac/proverbs.json");
  vi.doUnmock("../../data/discover/traditionalSayingAlmanacReuse.json");
  vi.resetModules();
});

describe("reused saying bibliography", () => {
  it("preserves the primary edition, verified pages, approved copy and source identity for every real reuse", () => {
    const before = JSON.stringify(proverbs);
    const records = getTraditionalSayingRecords().filter((record) => record.reusedFromAlmanac);
    expect(records).toHaveLength(reuse.records.length);
    for (const record of records) {
      const proverb = proverbs.find((item) => item.id === record.candidateId);
      const edition = proverb.source.match(/Ostermann (\d{4})/)[1];
      expect(record.source.label).toBe(`Ostermann ${edition}`);
      expect(record.source.verifiedAgainst).toBe(proverb.source);
      expect(record.source.sourcePath).toBe("frontend/src/data/almanac/proverbs.json");
      if (proverb.sourceDetail?.pdfPage) expect(record.source.pdfPage).toBe(proverb.sourceDetail.pdfPage);
      if (proverb.sourceDetail?.textPage) expect(record.source.textPage).toBe(proverb.sourceDetail.textPage);
      expect(record.title).toEqual({ it: proverb.it, fur: proverb.fur });
      expect(proverb.editorialReview).toMatchObject({ it: "approved", fur: "approved" });
      expect(record.editorialReview.reviewedAt).toBe(proverb.editorialReview.reviewedAt);
    }
    expect(JSON.stringify(proverbs)).toBe(before);
  });

  it("does not label the 1894 primary source as its secondary 1876 corroboration", () => {
    const record = getTraditionalSayingRecords().find((item) => item.candidateId === "ostermann-103-no-mai-ploe");
    expect(record.source).toMatchObject({ label: "Ostermann 1894", pdfPage: 103 });
  });

  it("uses only positive integer structured pages or explicit primary PDF pages without guessing from IDs", async () => {
    const fixtures = [
      { id: "ost1876-misleading", source: "Ostermann 1894, p. PDF 12; riscontro Ostermann 1876, p. PDF 99", sourceDetail: { pdfPage: 15, textPage: 3 } },
      { id: "invalid-pages", source: "Ostermann 1894, p. PDF 12", sourceDetail: { pdfPage: "17", textPage: -1 } },
      { id: "secondary-page", source: "Ostermann 1894, p. 7; riscontro Ostermann 1876, p. PDF 99", sourceDetail: { pdfPage: 0, textPage: 1.5 } },
      { id: "ost1876-unknown", source: "Raccolta locale; confronto Ostermann 1876, p. PDF 99" },
      { id: "empty-source", source: "" },
    ].map((item) => ({ ...item, it: "Testo", fur: "Test", editorialReview: { it: "approved", fur: "approved", reviewedAt: "2026-08-31" } }));
    vi.doMock("../../data/almanac/proverbs.json", () => ({ default: fixtures }));
    vi.doMock("../../data/discover/traditionalSayingAlmanacReuse.json", () => ({ default: { records: fixtures.map((item) => ({ proverbId: item.id })) } }));
    vi.resetModules();
    const module = await import("./traditionalSayings");
    const records = module.getTraditionalSayingRecords().filter((item) => item.reusedFromAlmanac);
    expect(records.map((item) => ({ label: item.source.label, pdfPage: item.source.pdfPage, textPage: item.source.textPage }))).toEqual([
      { label: "Ostermann 1894", pdfPage: 15, textPage: 3 },
      { label: "Ostermann 1894", pdfPage: 12, textPage: undefined },
      { label: "Ostermann 1894", pdfPage: undefined, textPage: undefined },
      { label: "Raccolta locale", pdfPage: undefined, textPage: undefined },
      { label: "Ostermann", pdfPage: undefined, textPage: undefined },
    ]);
  });
});
