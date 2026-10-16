import { describe, expect, it } from "vitest";

import editorialBacklog from "../../data/discover/editorialExpansionBacklog.json";
import archiveResearchWave01 from "../../data/discover/archiveResearchWave01.json";
import archiveResearchWave02 from "../../data/discover/archiveResearchWave02.json";
import archiveResearchWave05 from "../../data/discover/archiveResearchWave05.json";
import secondaryMemoryResearchWave01 from "../../data/discover/secondaryMemoryResearchWave01.json";
import weatherContextReview from "../../data/discover/weatherContextReview.json";
import ritualResearchWave07 from "../../data/discover/ritualResearchWave07.json";
import localMemory from "../../data/discover/localMemory.json";
import municipalityProfiles from "../../data/discover/municipalityProfiles.json";
import traditionalSayingsArchive from "../../data/discover/traditionalSayings.json";
import { buildDiscoverEditorialCalendarAudit } from "../../features/discover/discoverEditorialCalendarAudit";
import culturalRecords from "./discoverCulturalRecords";
import { isCuratedDiscoverPublished } from "./discoverCulturalReadiness";
import {
  getTraditionalSayingRecords,
  getTraditionalSayingsSummary,
} from "./traditionalSayings";

const READY_MEMORY_SOURCE_TYPES = new Set(["verified_source", "editorial_note"]);

function getBacklogRecord(id) {
  return editorialBacklog.records.find((record) => record.id === id);
}

function isReadyCulturalRecord(record) {
  return isCuratedDiscoverPublished(record);
}

function isReadyMemory(record) {
  return record?.readyForUi === true
    && record?.primaryUse === "discover"
    && record?.editorialStatus === "ready_for_discover"
    && READY_MEMORY_SOURCE_TYPES.has(record?.source?.type);
}

function isSourceVerifiedArchiveCandidate(record) {
  return ["source_verified_for_copy", "it_copy_approved", "promoted"].includes(record?.reviewStatus);
}

describe("discover editorial expansion backlog", () => {
  it("keeps all five rubrics in the completion plan instead of only municipality timelines", () => {
    expect(editorialBacklog.executionPlan).toMatchObject({
      status: "in_progress",
      strategy: "municipality_first_editorial_batches",
      nextFocus: "municipality-historical-milestones",
    });
    expect(editorialBacklog.executionPlan.scope).toEqual([
      "municipality-historical-milestones",
      "ritual-calendar-breadth",
      "traditional-sayings-variety",
      "archive-weather-context",
      "daily-memory-coverage",
    ]);
    const backlogIds = new Set(editorialBacklog.records.map(({ id }) => id));
    for (const id of editorialBacklog.executionPlan.scope) {
      expect(backlogIds.has(id)).toBe(true);
    }
  });

  it("keeps every backlog item explicit and actionable", () => {
    expect(editorialBacklog.records.map((record) => record.id)).toEqual([
      "municipality-historical-milestones",
      "ritual-calendar-breadth",
      "traditional-sayings-variety",
      "archive-weather-context",
      "archive-daily-variety-research-wave-01",
      "archive-daily-variety-research-wave-02",
      "daily-memory-coverage",
    ]);
    editorialBacklog.records.forEach((record) => {
      expect(record.status).toBeTruthy();
      expect(record.priority).toBeTruthy();
      expect(record.futureWork.length).toBeGreaterThan(0);
    });
  });

  it("tracks the real municipality milestone gap", () => {
    const profiles = municipalityProfiles.profiles;
    const milestoneCounts = profiles.map((profile) => profile.milestones?.length || 0);
    const pordenone = profiles.find((profile) => profile.municipality === "Pordenone");

    expect(getBacklogRecord("municipality-historical-milestones").currentSnapshot).toEqual({
      municipalityProfiles: profiles.length,
      totalMilestones: milestoneCounts.reduce((total, count) => total + count, 0),
      profilesWithoutMilestones: milestoneCounts.filter((count) => count === 0).length,
      profilesWithOneMilestone: milestoneCounts.filter((count) => count === 1).length,
      profilesWithTwoMilestones: milestoneCounts.filter((count) => count === 2).length,
      profilesWithAtLeastThreeMilestones: milestoneCounts.filter((count) => count >= 3).length,
      pordenoneMilestones: pordenone?.milestones?.length || 0,
    });
  });

  it("separates ritual material gaps from weather-dependent records", () => {
    const audit = buildDiscoverEditorialCalendarAudit({ year: 2028 });
    const rituals = culturalRecords
      .filter(isReadyCulturalRecord)
      .filter((record) => record.section === "riti_credenze_popolari");

    expect(getBacklogRecord("ritual-calendar-breadth").currentSnapshot).toEqual({
      catalogRecords: rituals.length,
      calendarizableRecords: rituals.filter((record) => record.recurrence !== "weather").length,
      weatherDependentRecords: rituals.filter((record) => record.recurrence === "weather").length,
      recordsUsedInPordenone2028: audit.summary.ritual.uniqueUsed,
      daysShownInPordenone2028: audit.summary.ritual.daysShown,
    });
  });

  it("records that sayings are complete today but remain expandable", () => {
    const audit = buildDiscoverEditorialCalendarAudit({ year: 2028 });
    const summary = getTraditionalSayingsSummary();
    const records = getTraditionalSayingRecords();

    expect(getBacklogRecord("traditional-sayings-variety").currentSnapshot).toEqual({
      catalogRecords: records.length,
      dedicatedDiscoverRecords: traditionalSayingsArchive.records.length,
      reusedAlmanacRecords: records.filter((record) => record.reusedFromAlmanac).length,
      exactDateRecords: summary.exactDateRecords,
      daysShownIn2028: audit.summary.saying.daysShown,
      recordsUsedIn2028: audit.summary.saying.uniqueUsed,
      unusedEligibleRecords: audit.summary.saying.unusedEligibleIds.length,
      longestConsecutiveRepeatDays: audit.summary.saying.longestConsecutiveRepeat.days,
    });
  });

  it("tracks archive runtime blockers without treating them as missing copy", () => {
    const audit = buildDiscoverEditorialCalendarAudit({ year: 2028 });
    const archive = culturalRecords
      .filter(isReadyCulturalRecord)
      .filter((record) => record.section !== "riti_credenze_popolari");

    expect(getBacklogRecord("archive-weather-context").currentSnapshot).toEqual({
      catalogRecords: archive.length,
      calendarizableRecords: archive.filter((record) => record.recurrence !== "weather").length,
      weatherDependentRecords: archive.filter((record) => record.recurrence === "weather").length,
      recordsUsedIn2028: audit.summary.archive.uniqueUsed,
      daysShownIn2028: audit.summary.archive.daysShown,
      longestConsecutiveRepeatDays: audit.summary.archive.longestConsecutiveRepeat.days,
      exactRecordsCoveredByMemoryOfTheDay: audit.summary.exactDateCoveredByHigherRubric.length,
    });
  });

  it("tracks the first research wave and its separate approved catalog entries", () => {
    const candidates = archiveResearchWave01.records;

    expect(getBacklogRecord("archive-daily-variety-research-wave-01").currentSnapshot).toEqual({
      candidateRecords: candidates.length,
      sourceVerifiedRecords: candidates.filter(isSourceVerifiedArchiveCandidate).length,
      itDraftRecords: candidates.filter((record) => record.languageStatus?.it === "draft").length,
      itApprovedRecords: candidates.filter((record) => record.languageStatus?.it === "approved").length,
      itReadyForFurDraftRecords: candidates.filter((record) => (
        record.editorialStatus === "it_ready_for_fur_draft"
      )).length,
      furDraftPendingReviewRecords: candidates.filter((record) => (
        record.editorialStatus === "bilingual_draft_pending_review"
      )).length,
      furPendingRecords: candidates.filter((record) => record.languageStatus?.fur === "pending_human_review").length,
      promotionReadyExceptFurRecords: candidates.filter((record) => (
        record.editorialStatus === "promotion_ready_except_fur"
      )).length,
      promotedRecords: candidates.filter((record) => record.reviewStatus === "promoted").length,
      readyForUiRecords: candidates.filter((record) => record.readyForUi === true).length,
    });
  });

  it("tracks the second research wave and its separate approved catalog entries", () => {
    const candidates = archiveResearchWave02.records;

    expect(getBacklogRecord("archive-daily-variety-research-wave-02").currentSnapshot).toEqual({
      candidateRecords: candidates.length,
      sourceVerifiedRecords: candidates.filter(isSourceVerifiedArchiveCandidate).length,
      itDraftRecords: candidates.filter((record) => record.languageStatus?.it === "draft").length,
      itApprovedRecords: candidates.filter((record) => record.languageStatus?.it === "approved").length,
      itReadyForFurDraftRecords: candidates.filter((record) => (
        record.editorialStatus === "it_ready_for_fur_draft"
      )).length,
      furDraftPendingReviewRecords: candidates.filter((record) => (
        record.editorialStatus === "bilingual_draft_pending_review"
      )).length,
      furPendingRecords: candidates.filter((record) => record.languageStatus?.fur === "pending_human_review").length,
      promotionReadyExceptFurRecords: candidates.filter((record) => (
        record.editorialStatus === "promotion_ready_except_fur"
      )).length,
      promotedRecords: candidates.filter((record) => record.reviewStatus === "promoted").length,
      readyForUiRecords: candidates.filter((record) => record.readyForUi === true).length,
    });
  });

  it("keeps the complete daily-memory inventory under observation", () => {
    const readyRecords = localMemory.records.filter(isReadyMemory);
    const primaryRecords = readyRecords.filter((record) => record.dailyRole !== "secondary");
    const secondaryRecords = readyRecords.filter((record) => record.dailyRole === "secondary");
    const primaryDates = new Set(primaryRecords.flatMap((record) => record.dateAnchors || []));
    const secondaryDates = new Set(secondaryRecords.flatMap((record) => record.dateAnchors || []));

    expect(getBacklogRecord("daily-memory-coverage").currentSnapshot).toEqual({
      readyPrimaryRecords: primaryRecords.length,
      coveredCalendarDates: primaryDates.size,
      readySecondaryRecords: secondaryRecords.length,
      datesWithSecondaryRecords: secondaryDates.size,
    });
  });

  it("traces the new editorial batches without publishing their research copies", () => {
    [
      ["ritual-calendar-breadth", "ritual-research-wave-07", "ritualResearchWave07.json", ritualResearchWave07, culturalRecords],
      ["archive-weather-context", "archive-research-wave-05", "archiveResearchWave05.json", archiveResearchWave05, culturalRecords],
      ["daily-memory-coverage", "secondary-memory-research-wave-01", "secondaryMemoryResearchWave01.json", secondaryMemoryResearchWave01, localMemory.records],
    ].forEach(([backlogId, batchId, fileName, research, runtime]) => {
      expect(getBacklogRecord(backlogId).latestEditorialBatch).toEqual({
        batchId,
        manifest: `frontend/src/data/discover/${fileName}`,
        promotedRecords: research.records.length,
        approvalBasis: "user_delegated_assisted_editorial_review",
        independentHumanReview: false,
      });
      expect(research.readyForUi).toBe(false);
      research.records.forEach((candidate) => {
        expect(candidate.readyForUi).toBe(false);
        expect(runtime.find((record) => record.id === candidate.promotedRecordId)?.readyForUi).toBe(true);
      });
    });
  });

  it("accounts for every weather-bound record without claiming live weather integration", () => {
    expect(getBacklogRecord("archive-weather-context").weatherReview).toEqual({
      manifest: "frontend/src/data/discover/weatherContextReview.json",
      originalWeatherRecords: 26,
      reviewedRecords: weatherContextReview.records.length,
      reclassifiedForDiscover: weatherContextReview.records.filter((record) => record.disposition === "archive_rotation").length,
      stillExcluded: culturalRecords.filter((record) => record.recurrence === "weather").length,
      runtimeWeatherIntegration: false,
      sharedOstermannCatalogChanged: false,
    });
  });
});
