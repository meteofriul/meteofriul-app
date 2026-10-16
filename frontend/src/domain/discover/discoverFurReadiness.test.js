import { describe, expect, it } from "vitest";

import { getDiscoverFurReadinessSummary } from "./discoverFurReadiness";

const approvedCurated = {
  id: "approved-curated",
  editorialStatus: "ready_it",
  languageStatus: { fur: "approved" },
};

const shortReadyCurated = {
  id: "short-ready-curated",
  editorialStatus: "archive_context",
  languageStatus: { fur: "short_ready" },
};

const readyLocalMemory = {
  id: "ready-local-memory",
  primaryUse: "discover",
  source: { type: "verified_source" },
  editorialStatus: "ready_for_discover",
  languageStatus: { fur: "approved" },
  readyForUi: true,
};

const pendingLocalMemory = {
  ...readyLocalMemory,
  id: "pending-local-memory",
  languageStatus: { fur: "human_review_needed" },
};

describe("getDiscoverFurReadinessSummary", () => {
  it("documents the current Scopri FUR coverage without publishing pending backlog", () => {
    const summary = getDiscoverFurReadinessSummary();

    expect(summary.visibleCuratedRecords).toBe(109);
    expect(summary.visibleCuratedFurApprovedRecords).toBe(109);
    expect(summary.visibleCuratedFurShortReadyRecords).toBe(0);
    expect(summary.hiddenInFurCuratedRecords).toBe(0);
    expect(summary.hiddenInFurCuratedRecordRefs).toEqual([]);
    expect(summary.localMemoryRecords).toBe(581);
    expect(summary.visibleLocalMemoryRecords).toBe(567);
    expect(summary.visibleLocalMemoryFurApprovedRecords).toBe(567);
    expect(summary.localMemoryFurHumanReviewNeededRecords).toBe(11);
    expect(summary.hiddenInFurLocalMemoryRecords).toBe(0);
    expect(summary.localMemoryBlockedUntilPromotionRecords).toBe(14);
    expect(summary.traditionalSayingsRecords).toBe(80);
    expect(summary.visibleTraditionalSayingsRecords).toBe(80);
    expect(summary.visibleTraditionalSayingsFurApprovedRecords).toBe(80);
    expect(summary.hiddenInFurTraditionalSayingsRecords).toBe(0);
    expect(summary.backlogRecords).toBe(29);
    expect(summary.backlogPendingFurRecords).toBe(29);
    expect(summary.backlogBlockedUntilPromotionRecords).toBe(29);
    expect(summary.backlogReadyForUiRecords).toBe(0);
    expect(summary.hiddenInFurRecords).toBe(0);
    expect(summary.discoverFurDisplayReady).toBe(true);
    expect(summary.discoverFurCoverageComplete).toBe(true);
  });

  it("marks coverage complete only when every visible Scopri record has approved FUR", () => {
    const summary = getDiscoverFurReadinessSummary({
      curatedRecords: [approvedCurated],
      localMemorySource: { records: [readyLocalMemory] },
      backlogSource: { records: [] },
      traditionalSayingsSource: { records: [] },
    });

    expect(summary.furVisibleRecords).toBe(2);
    expect(summary.hiddenInFurRecords).toBe(0);
    expect(summary.discoverFurCoverageComplete).toBe(true);
  });

  it("keeps publishable local memory out of FUR coverage when its FUR is not approved", () => {
    const summary = getDiscoverFurReadinessSummary({
      curatedRecords: [approvedCurated, shortReadyCurated],
      localMemorySource: { records: [readyLocalMemory, pendingLocalMemory] },
      backlogSource: { records: [] },
      traditionalSayingsSource: { records: [] },
    });

    expect(summary.hiddenInFurRecords).toBe(2);
    expect(summary.hiddenInFurCuratedRecordRefs).toEqual([
      { id: "short-ready-curated", source: "curated", status: "short_ready" },
    ]);
    expect(summary.hiddenInFurLocalMemoryRecordRefs).toEqual([
      { id: "pending-local-memory", source: "local_memory", status: "human_review_needed" },
    ]);
    expect(summary.discoverFurCoverageComplete).toBe(false);
  });

  it("does not report an explicitly blocked curated record as visible", () => {
    const summary = getDiscoverFurReadinessSummary({
      curatedRecords: [{ ...approvedCurated, readyForUi: false }],
      localMemorySource: { records: [] },
      backlogSource: { records: [] },
      traditionalSayingsSource: { records: [] },
    });

    expect(summary.visibleCuratedRecords).toBe(0);
    expect(summary.furVisibleRecords).toBe(0);
  });
});
