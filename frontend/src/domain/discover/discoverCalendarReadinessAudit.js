import dailyHistoryBacklogAudit from "../../data/discover/dailyHistoryBacklogAudit.json";
import { getDailyHistoryBacklogAudit } from "./dailyHistoryBacklogAudit";
import { getDiscoverCoverageSummary } from "./discoverCoverage";
import { getDiscoverDailyCalendarPlanSummary } from "./discoverDailyCalendarPlan";

export function getDiscoverCalendarReadinessAudit({
  coverageSummary = getDiscoverCoverageSummary(),
  calendarSummary = getDiscoverDailyCalendarPlanSummary(),
  historyBacklog = dailyHistoryBacklogAudit,
} = {}) {
  const historySummary = historyBacklog?.summary || {};
  const historyAudit = getDailyHistoryBacklogAudit(historyBacklog);
  const memoryMissingDaySet = new Set(calendarSummary.memoryMissingDayKeys || []);
  const missingMemoryDaysWithCandidates = historyAudit.unqueuedCandidateDateAnchors
    .filter((dayKey) => memoryMissingDaySet.has(dayKey));
  const missingMemoryDaysWithLightReview = historyAudit.lightReviewCandidateDateAnchors
    .filter((dayKey) => memoryMissingDaySet.has(dayKey));
  const missingMemoryDaysWithoutUnqueuedCandidates = (calendarSummary.memoryMissingDayKeys || [])
    .filter((dayKey) => !historyAudit.unqueuedCandidateDateAnchors.includes(dayKey));

  return {
    dailyTarget: calendarSummary.dailyTarget,
    readyNow: {
      memoryReadyDays: calendarSummary.memoryReadyDays,
      sayingReadyDays: coverageSummary.discover.traditionalSayingsDailySelectionDays,
      sayingExactDateDays: calendarSummary.sayingReadyDays,
    },
    reviewBacklog: {
      historyEligibleCandidates: historySummary.eligibleCandidates || 0,
      historyUnqueuedEligibleCandidates: historySummary.unqueuedEligibleCandidates || 0,
      historyCoveredDays: historySummary.coveredDays || 0,
      historyCoveredUnqueuedDays: historySummary.coveredUnqueuedDays || 0,
      historyEmptyDays: historySummary.emptyDays || [],
      historyNextLightReviewCandidates: historySummary.nextLightReviewCandidates || 0,
      historyNextLightReviewOnePerDay: historySummary.nextLightReviewOnePerDay === true,
      historyBySuggestedReviewLane: historySummary.bySuggestedReviewLane || {},
      historyFirstLightReviewDaysForMissingMemory: missingMemoryDaysWithLightReview.slice(0, 20),
      ostermannBacklogRecords: coverageSummary.discover.backlogRecords,
      ostermannBacklogReadyForUi: coverageSummary.discover.backlogReadyForUi,
    },
    gaps: {
      memoryMissingDays: calendarSummary.memoryMissingDays,
      sayingMissingDays: coverageSummary.discover.traditionalSayingsMissingDays.length,
      sayingExactDateMissingDays: calendarSummary.sayingMissingDays,
      historySourceEmptyDays: historySummary.emptyDays?.length || 0,
      memoryMissingDaysWithLightReviewCandidates: missingMemoryDaysWithLightReview.length,
      memoryMissingDaysWithUnqueuedHistoryCandidates: missingMemoryDaysWithCandidates.length,
      memoryMissingDaysWithoutUnqueuedHistoryCandidates: missingMemoryDaysWithoutUnqueuedCandidates.length,
      firstMemoryMissingDaysWithoutUnqueuedHistoryCandidates:
        missingMemoryDaysWithoutUnqueuedCandidates.slice(0, 20),
    },
    nextWork: {
      memory:
        "review_primary_gap_candidates_then_research_new_sources",
      discoverArchive:
        "use_ostermann_context_records_as_human_explanations_not_daily_fillers",
    },
  };
}
