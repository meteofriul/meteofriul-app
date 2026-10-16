import { describe, expect, it } from "vitest";

import backlogAudit from "../../data/discover/dailyHistoryBacklogAudit.json";
import { getDailyHistoryBacklogAudit } from "./dailyHistoryBacklogAudit";

describe("daily history backlog audit", () => {
  it("keeps Italian source dates separate from runtime calendar anchors", () => {
    const audit = getDailyHistoryBacklogAudit({
      summary: {},
      days: [{
        dayKey: "07-01",
        dateAnchor: "01-07",
        unqueuedEligibleCandidates: 1,
        topUnqueued: [],
      }],
    });

    expect(audit.unqueuedCandidateDays).toEqual(["07-01"]);
    expect(audit.unqueuedCandidateDateAnchors).toEqual(["01-07"]);
  });

  it("tracks the full extraction backlog without publishing records", () => {
    const audit = getDailyHistoryBacklogAudit(backlogAudit);

    expect(backlogAudit.purpose).toContain("Non letto dalla UI");
    expect(backlogAudit.policy).toMatchObject({
      noAutomaticPublication: true,
      tracksCalendarCoverage: true,
      keepsQueuedAndUnqueuedSeparate: true,
      excludesDeaths: true,
    });
    expect(audit).toMatchObject({
      schemaVersion: 1,
      sourceDays: 366,
      sourceCandidates: 2482,
      eligibleCandidates: 1048,
      unqueuedEligibleCandidates: 155,
      coveredDays: 332,
      coveredUnqueuedDays: 111,
      nextReviewCandidates: 120,
      nextLightReviewCandidates: 0,
      readyPrimaryDays: 366,
      missingPrimaryDays: 0,
      missingPrimaryDaysWithUnqueuedCandidates: 0,
      missingPrimaryDaysWithoutUnqueuedCandidates: 0,
      nextPrimaryGapCandidates: 0,
      duplicateNextReviewWikidataIds: [],
      duplicateNextLightReviewWikidataIds: [],
      duplicateNextLightReviewSourceDays: [],
      duplicateNextPrimaryGapDateAnchors: [],
    });
    expect(audit.unqueuedCandidateDays).toHaveLength(111);
    expect(audit.unqueuedCandidateDateAnchors).toHaveLength(111);
    expect(audit.lightReviewCandidateDays).toHaveLength(0);
    expect(backlogAudit.summary.byEligibleType).toEqual({
      Evento: 28,
      Nascita: 1020,
    });
  });

  it("keeps the calendar gaps visible for source-first work", () => {
    const audit = getDailyHistoryBacklogAudit(backlogAudit);

    expect(audit.emptyDays).toEqual([
      "06-02",
      "07-04",
      "03-06",
      "08-07",
      "05-08",
      "02-10",
      "05-10",
      "08-10",
      "10-11",
      "11-11",
      "05-12",
      "03-13",
      "11-14",
      "10-17",
      "10-18",
      "11-18",
      "12-18",
      "05-20",
      "04-22",
      "05-22",
      "06-22",
      "07-22",
      "02-23",
      "12-24",
      "06-25",
      "09-25",
      "10-25",
      "12-25",
      "04-28",
      "05-28",
      "04-30",
      "05-30",
      "07-30",
      "08-30",
    ]);
    expect(audit.emptyUnqueuedDays).toContain("04-10");
    expect(audit.emptyUnqueuedDays).toContain("10-17");
    expect(audit.firstUnqueuedCandidateDays.slice(0, 3)).toEqual(["01-02", "01-03", "02-05"]);
    expect(audit.firstLightReviewCandidateDays).toEqual([]);
    expect(backlogAudit.sourceInput.excludedItalianReviewWaves.at(-1)).toBe(
      "discoverDailyItalianReviewWave78.json",
    );
  });

  it("shows that most eligible records are archive material, not daily copy", () => {
    const audit = getDailyHistoryBacklogAudit(backlogAudit);

    expect(audit.byEligibleEditorialClass).toMatchObject({
      A: 16,
      B: 237,
      C: 795,
    });
    expect(audit.bySuggestedReviewLane).toMatchObject({
      archive_low_priority: 199,
      archive_review: 551,
      hold_strong_source: 116,
      light_review: 182,
    });
    expect(audit.byEligibleCategory.arte_cultura).toBeGreaterThan(200);
    expect(audit.byEligibleCategory.altro).toBeGreaterThan(600);
  });

  it("keeps a separate light-review queue for faster editorial work", () => {
    const candidates = backlogAudit.nextLightReviewCandidates || [];

    expect(candidates).toHaveLength(0);
    expect(candidates.every((candidate) => candidate.suggestedReviewLane === "light_review")).toBe(true);
    expect(candidates.every((candidate) => candidate.alreadyQueuedOrKnown === false)).toBe(true);
    expect(new Set(candidates.map((candidate) => candidate.sourceDayKey))).toHaveLength(candidates.length);
  });
});
