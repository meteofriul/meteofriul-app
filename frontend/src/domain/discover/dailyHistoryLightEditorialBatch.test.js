import { describe, expect, it } from "vitest";

import batch from "../../data/discover/dailyHistoryLightEditorialBatch.json";
import { getDailyHistoryLightEditorialBatchAudit } from "./dailyHistoryLightEditorialBatch";

describe("daily history light editorial batch", () => {
  it("keeps the first light review batch unpublished and deduplicated", () => {
    const audit = getDailyHistoryLightEditorialBatchAudit(batch);

    expect(batch.purpose).toContain("Non letto dalla UI");
    expect(batch.policy).toMatchObject({
      doNotPublishFromThisFile: true,
      requiresHumanReview: true,
      requiresFurReview: true,
      oneMainMemoryPerDay: true,
    });
    expect(audit).toMatchObject({
      schemaVersion: 1,
      totalRecords: 52,
      readyForUiRecords: 0,
      duplicateDates: [],
      duplicateWikidataIds: [],
    });
  });

  it("separates copy candidates from archive and hold records", () => {
    const audit = getDailyHistoryLightEditorialBatchAudit(batch);

    expect(audit.byDecision).toEqual({
      archive_context: 17,
      copy_candidate: 33,
      hold_strong_source: 2,
    });
    expect(audit.bySurface).toEqual({
      discover_archive: 17,
      hold: 2,
      memory_of_the_day: 33,
    });
    expect(audit.copyCandidates).toBe(33);
    expect(audit.copyCandidatesWithItDraft).toBe(33);
    expect(audit.copyCandidatesNeedingFur).toBe(33);
  });
});
