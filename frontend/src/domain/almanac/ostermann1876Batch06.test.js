import { describe, expect, it } from "vitest";

import proverbs from "../../data/almanac/proverbs.json";

const BATCH_IDS = [
  "ost1876-ducj-sintin-orelis",
  "ost1876-ognidun-mangje-bocje",
  "ost1876-ognidun-viot-siei-voi",
  "ost1876-aghe-corinte-no-puarte-sporcjetat",
  "ost1876-fat-mont-po-disfalu",
  "ost1876-ogni-di-ven-gnot",
  "ost1876-pazience-maride-frari",
  "ost1876-vul-ledi-nol-vul-mandi",
  "ost1876-ogni-trop-masse",
  "ost1876-bez-po-spindi",
  "ost1876-len-sec-cjape-prin",
  "ost1876-acuile-no-pie-moscjis",
  "ost1876-farine-no-buine-ostiis",
  "ost1876-come-che-ven",
  "ost1876-dut-a-un-fin",
];

describe("Ostermann 1876 review batch 06", () => {
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
      expect(record.source).toMatch(/^Facsimile Ostermann 1876, p\. PDF 30[5-7]$/);
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

    expect(byId["ost1876-aghe-corinte-no-puarte-sporcjetat"].fur).toBe(
      "La aghe corinte no puarte sporcjetât.",
    );
    expect(byId["ost1876-vul-ledi-nol-vul-mandi"].fur).toBe(
      "Cui che al vûl che al ledi; cui che nol vûl che al mandi.",
    );
    expect(byId["ost1876-acuile-no-pie-moscjis"].fur).toBe(
      "La acuile no pie moscjis.",
    );
    expect(byId["ost1876-farine-no-buine-ostiis"].fur).toBe(
      "Ogni farine no je buine par fâ ostiis.",
    );
  });
});
