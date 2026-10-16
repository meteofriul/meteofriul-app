import { describe, expect, it } from "vitest";

import reviewWave from "../../data/discover/discoverParallelReviewWave.json";

function allRecords() {
  return [
    ...reviewWave.dailyHistoryKeep,
    ...reviewWave.ostermannSayingKeep,
    ...reviewWave.ostermannArchiveKeep,
    ...reviewWave.ostermannRitualHold,
  ];
}

describe("Discover parallel editorial review wave", () => {
  it("remains staging-only and defers FUR", () => {
    expect(reviewWave.policy).toMatchObject({
      readyForUi: false,
      furDeferred: true,
      dateFormat: "DD-MM",
    });
    expect(allRecords().every((record) => record.readyForUi === false)).toBe(true);
    expect(JSON.stringify(reviewWave)).not.toContain('"fur"');
  });

  it("keeps reviewed groups explicit and internally consistent", () => {
    expect(reviewWave.dailyHistoryKeep).toHaveLength(7);
    expect(reviewWave.ostermannSayingKeep).toHaveLength(5);
    expect(reviewWave.ostermannArchiveKeep).toHaveLength(2);
    expect(reviewWave.ostermannRitualHold).toHaveLength(1);

    const ids = allRecords().map((record) => record.id);
    expect(new Set(ids).size).toBe(ids.length);
    expect(reviewWave.dailyHistoryKeep.every((record) => /^\d{2}-\d{2}$/.test(record.dateIt))).toBe(true);
    expect(reviewWave.dailyHistoryKeep.every((record) => record.province)).toBe(true);
  });
});
