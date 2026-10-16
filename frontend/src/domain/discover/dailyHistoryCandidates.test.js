import { describe, expect, it } from "vitest";

import candidatesArchive from "../../data/discover/dailyHistoryCandidates.json";
import {
  convertSourceDayKeyToDateAnchor,
  getDailyHistoryCandidatesAudit,
  getLocalizedSecondaryDailyHistoryEntries,
} from "./dailyHistoryCandidates";

describe("daily history candidates", () => {
  it("keeps source day keys separate from app date anchors", () => {
    expect(convertSourceDayKeyToDateAnchor("03-11")).toBe("11-03");
    expect(convertSourceDayKeyToDateAnchor("09-10")).toBe("10-09");
    expect(convertSourceDayKeyToDateAnchor("bad-date")).toBeNull();
  });

  it("tracks the pilot queue after the first source-verified promotions", () => {
    const audit = getDailyHistoryCandidatesAudit(candidatesArchive);

    expect(audit).toMatchObject({
      schemaVersion: 1,
      sourceDateFormat: "DD-MM",
      appDateFormat: "MM-DD",
      totalRecords: 10,
      uniqueDateAnchors: 10,
      duplicateDateAnchors: [],
      dateFormatErrors: [],
      publishableRecords: 2,
      recordsNeedingItCopy: 8,
      recordsNeedingFurCopy: 8,
      byReviewStatus: {
        source_lead_found: 8,
        source_verified_for_copy: 2,
      },
      byEditorialStatus: {
        candidate_for_review: 8,
        ready_for_discover: 2,
      },
      byEditorialReadiness: {
        needs_strong_source: 8,
        published: 2,
      },
      lightCandidateRecordIds: [],
      strongSourceRequiredRecordIds: [
        "daily-history-candidate-0401-assedio-aquileia-238",
        "daily-history-candidate-1103-rivolta-trieste-1953",
        "daily-history-candidate-0806-sesta-battaglia-isonzo-1916",
        "daily-history-candidate-1012-assedio-trieste-1813",
        "daily-history-candidate-0415-battaglia-sacile-1809",
        "daily-history-candidate-1029-battaglia-pozzuolo-1917",
        "daily-history-candidate-0515-battaglia-tarvisio-1809",
        "daily-history-candidate-0316-battaglia-valvasone-1797",
      ],
      strongReadyForCopyRecordIds: [],
      bySourceType: {
        wikidata_candidate: 10,
      },
      sourceReviewedRecords: 10,
      bySourceReviewStatus: {
        source_lead_found: 8,
        source_verified_for_copy: 2,
      },
      sourceVerificationAttemptedRecords: 6,
      bySourceVerificationOutcome: {
        bibliography_only_for_now: 3,
        official_link_temporarily_unreachable: 1,
        primary_sources_not_yet_checked: 1,
        sensitive_topic_needs_better_source: 1,
      },
      sourceVerificationRetriedRecords: 6,
      bySourceVerificationRetryOutcome: {
        local_historical_source_found_date_confirmed: 1,
        official_link_still_unreachable: 1,
        still_bibliography_only: 2,
        still_primary_sources_not_directly_checked: 1,
        still_sensitive_needs_better_source: 1,
      },
      recordsWithDayComposition: 1,
      secondarySameDayCandidates: 2,
      discardedSameDayCandidates: 2,
    });
  });

  it("tracks the selected ten pilot days explicitly", () => {
    const audit = getDailyHistoryCandidatesAudit(candidatesArchive);

    expect(audit.recordIds).toEqual([
      "daily-history-candidate-0401-assedio-aquileia-238",
      "daily-history-candidate-1103-rivolta-trieste-1953",
      "daily-history-candidate-0806-sesta-battaglia-isonzo-1916",
      "daily-history-candidate-1009-vajont-1963",
      "daily-history-candidate-1012-assedio-trieste-1813",
      "daily-history-candidate-0415-battaglia-sacile-1809",
      "daily-history-candidate-1029-battaglia-pozzuolo-1917",
      "daily-history-candidate-0515-battaglia-tarvisio-1809",
      "daily-history-candidate-0316-battaglia-valvasone-1797",
      "daily-history-candidate-0426-assedio-osoppo-1848",
    ]);
  });

  it("localizes secondary entries without replacing the main daily memory", () => {
    const vajont = candidatesArchive.records.find((record) => (
      record.id === "daily-history-candidate-1009-vajont-1963"
    ));

    expect(getLocalizedSecondaryDailyHistoryEntries(vajont, {
      city: "Pordenone",
      province: "PN",
    }).map((entry) => entry.title)).toEqual([
      "Nasce Francesco Bearzatti",
      "Muore Giancarlo Rittmeyer",
    ]);

    expect(getLocalizedSecondaryDailyHistoryEntries(vajont, {
      city: "Gorizia",
      province: "GO",
    })).toEqual([]);
  });
});
