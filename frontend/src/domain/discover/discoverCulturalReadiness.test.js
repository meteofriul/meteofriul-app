import { describe, expect, it } from "vitest";

import {
  isCuratedDiscoverPublished,
  isCuratedDiscoverUiReady,
} from "./discoverCulturalReadiness";

const readyRecord = {
  editorialStatus: "ready_it",
  languageStatus: { fur: "approved" },
};

describe("discover cultural readiness", () => {
  it("keeps legacy curated records compatible while honoring an explicit UI block", () => {
    expect(isCuratedDiscoverUiReady(readyRecord)).toBe(true);
    expect(isCuratedDiscoverUiReady({ ...readyRecord, readyForUi: true })).toBe(true);
    expect(isCuratedDiscoverUiReady({ ...readyRecord, readyForUi: false })).toBe(false);
    expect(isCuratedDiscoverUiReady({ ...readyRecord, editorialStatus: "candidate_for_review" })).toBe(false);
  });

  it("treats a curated record as published only after FUR approval", () => {
    expect(isCuratedDiscoverPublished(readyRecord)).toBe(true);
    expect(isCuratedDiscoverPublished({
      ...readyRecord,
      languageStatus: { fur: "pending_human_review" },
    })).toBe(false);
    expect(isCuratedDiscoverPublished({ ...readyRecord, readyForUi: false })).toBe(false);
  });
});
