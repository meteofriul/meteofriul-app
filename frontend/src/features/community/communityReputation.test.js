import { describe, expect, it } from "vitest";

import { normalizeCommunityReputation } from "./communityReputation";

describe("community reputation", () => {
  it("normalizes the server-side pseudonymous summary", () => {
    expect(normalizeCommunityReputation({
      max_daily_awards: 3,
      pending_reports: 2,
      points: 7,
      rank: {
        id: "lookout",
        label: "Vedetta",
        min_points: 5,
        next_rank_at: 20,
      },
      source: {
        id: "community-report",
        storage: "firestore",
        type: "pseudonymous",
        verified: true,
      },
      total_reports: 12,
      validated_reports: 8,
    })).toEqual({
      maxDailyAwards: 3,
      pendingReports: 2,
      points: 7,
      rank: {
        id: "lookout",
        minPoints: 5,
        nextRankAt: 20,
      },
      source: {
        id: "community-report",
        storage: "firestore",
        type: "pseudonymous",
        verified: true,
      },
      totalReports: 12,
      validatedReports: 8,
    });
  });

  it("accepts camelCase while keeping rank thresholds server-authoritative", () => {
    expect(normalizeCommunityReputation({
      maxDailyAwards: 3,
      pendingReports: 1,
      points: 22,
      rank: { id: "sentinel", minPoints: 20, nextRankAt: null },
      totalReports: 31,
      validatedReports: 24,
    })).toMatchObject({
      maxDailyAwards: 3,
      pendingReports: 1,
      points: 22,
      rank: { id: "sentinel" },
      totalReports: 31,
      validatedReports: 24,
    });
    expect(normalizeCommunityReputation({
      points: 22,
      total_reports: 31,
      validated_reports: 24,
    })).toBeNull();
  });

  it("does not invent zero points when the authoritative count is absent", () => {
    expect(normalizeCommunityReputation({
      pending_reports: 3,
      rank: { id: "novice" },
      validated_reports: 0,
    })).toBeNull();
    expect(normalizeCommunityReputation(null)).toBeNull();
  });

  it("contains malformed optional counts without losing valid points", () => {
    expect(normalizeCommunityReputation({
      max_daily_awards: -2,
      pending_reports: "not-a-number",
      points: 4.9,
      rank: { id: "novizio", next_rank_at: -1 },
      total_reports: -4,
      validated_reports: null,
    })).toMatchObject({
      maxDailyAwards: null,
      pendingReports: null,
      points: 4,
      rank: { id: "novice", nextRankAt: null },
      totalReports: null,
      validatedReports: null,
    });
  });

  it("treats null points as unavailable rather than as an authoritative zero", () => {
    expect(normalizeCommunityReputation({
      points: null,
      rank: { id: "novice" },
      validated_reports: 0,
    })).toBeNull();
  });
});
