import { describe, expect, it } from "vitest";

import proverbs from "../../data/almanac/proverbs.json";

const BATCH_IDS = [
  "ost1876-ocasion-fas-om-mestri",
  "ost1876-ocasion-fas-om-lari",
  "ost1876-no-riscje-no-rosee",
  "ost1876-mior-uf-vue-gjaline-doman",
  "ost1876-prat-seat-no-scuindisi",
  "ost1876-cjapa-ucei-cuant-passin",
  "ost1876-mulin-cuant-je-aghe",
  "ost1876-pense-prime-no-pintiti",
  "ost1876-pense-vue-par-doman",
  "ost1876-cjale-bas-denant-muda-pas",
  "ost1876-no-comede-picule-buse",
  "ost1876-dopo-fat-ognidun-sa-fa",
  "ost1876-tet-no-par-une-ploe",
  "ost1876-jet-no-par-une-sere",
  "ost1876-plea-arbul-zovin",
];

describe("Ostermann 1876 review batch 07", () => {
  const records = BATCH_IDS.map((id) => proverbs.find((record) => record.id === id));

  it("publishes every reviewed record with complete bilingual copy and source", () => {
    expect(records).toHaveLength(15);
    records.forEach((record) => {
      expect(record).toMatchObject({
        almanacEligible: true,
        humanReviewRequired: true,
        normalizationStatus: "lab_ready",
        editorialReview: {
          it: "approved",
          fur: "approved",
          reviewedAt: "2026-07-23",
        },
      });
      expect(record.it).toBeTruthy();
      expect(record.fur).toBeTruthy();
      expect(record.source).toMatch(/^Facsimile Ostermann 1876, p\. PDF 1(?:49|50|51|52)$/);
    });
  });

  it("keeps the general sayings free from invented calendar constraints", () => {
    records.forEach((record) => {
      expect(record.almanacTargetUse).toBeUndefined();
      expect(record.dateAnchors).toBeUndefined();
      expect(record.dateRanges).toBeUndefined();
      expect(record.months).toBeUndefined();
      expect(record.seasons).toBeUndefined();
      expect(record.movableFeasts).toBeUndefined();
    });
  });

  it("preserves the reviewed forms most exposed to normalization errors", () => {
    const byId = Object.fromEntries(records.map((record) => [record.id, record]));

    expect(byId["ost1876-no-riscje-no-rosee"].fur).toBe(
      "Se no si riscje, no si rosee.",
    );
    expect(byId["ost1876-mior-uf-vue-gjaline-doman"].fur).toBe(
      "Miôr un ûf vuê che une gjaline doman.",
    );
    expect(byId["ost1876-prat-seat-no-scuindisi"].fur).toBe(
      "Tal prât seât no si pues scuindisi.",
    );
    expect(byId["ost1876-mulin-cuant-je-aghe"].fur).toBe(
      "Bisugne lâ a mulin cuant che e je aghe.",
    );
    expect(byId["ost1876-pense-prime-no-pintiti"].fur).toBe(
      "Pense prime par no pintîti dopo.",
    );
  });
});
