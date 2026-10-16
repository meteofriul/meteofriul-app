import { describe, expect, it } from "vitest";

import candidatesArchive from "../../data/discover/dailyHistoryCandidates.json";
import {
  getDiscoverEditorialPolicyAudit,
  getDiscoverEditorialReadiness,
  isValidItalianDayMonth,
  isSensitiveDailyHistoryCandidate,
} from "./discoverEditorialPolicy";

describe("discover editorial policy", () => {
  it("validates editorial dates in explicit Italian DD-MM format", () => {
    expect(isValidItalianDayMonth("12-10")).toBe(true);
    expect(isValidItalianDayMonth("29-02")).toBe(true);
    expect(isValidItalianDayMonth("31-11")).toBe(false);
    expect(isValidItalianDayMonth("10-31")).toBe(false);
  });

  it("allows light publication only for low-risk records with source leads", () => {
    const readiness = getDiscoverEditorialReadiness({
      id: "daily-history-light",
      title: { it: "Una fiera di primavera" },
      category: "tradizione",
      reviewStatus: "source_lead_found",
      readyForUi: false,
    });

    expect(readiness).toMatchObject({
      status: "light_candidate",
      canPublishLight: true,
      needsStrongSource: false,
    });
  });

  it("requires strong sources for battles, disasters and sensitive history", () => {
    expect(isSensitiveDailyHistoryCandidate({
      title: { it: "Battaglia di esempio" },
      category: "storia",
      year: 1809,
    })).toBe(true);

    expect(getDiscoverEditorialReadiness({
      id: "daily-history-sensitive",
      title: { it: "Rivolta di esempio" },
      category: "storia",
      year: 1953,
      reviewStatus: "source_lead_found",
      readyForUi: false,
    })).toMatchObject({
      status: "needs_strong_source",
      canPublishLight: false,
      needsStrongSource: true,
    });
  });

  it("keeps verified records ready for copy, not automatically published", () => {
    expect(getDiscoverEditorialReadiness({
      id: "daily-history-verified",
      title: { it: "L'assedio di esempio" },
      reviewStatus: "source_verified_for_copy",
      editorialStatus: "candidate_for_review",
      readyForUi: false,
    })).toMatchObject({
      status: "strong_ready_for_copy",
      canPublishLight: false,
      needsStrongSource: false,
    });
  });

  it("classifies the current pilot queue with published and blocked records separated", () => {
    const audit = getDiscoverEditorialPolicyAudit(candidatesArchive.records);

    expect(audit).toMatchObject({
      totalRecords: 10,
      byReadiness: {
        needs_strong_source: 8,
        published: 2,
      },
      lightCandidateRecordIds: [],
    });
    expect(audit.strongReadyForCopyRecordIds).toEqual([]);
  });
});
