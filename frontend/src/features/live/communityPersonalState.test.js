import { describe, expect, it } from "vitest";

import {
  COMMUNITY_PERSONAL_STATE_KEY,
  expireCommunityReport,
  forgetCommunityReport,
  getCommunityContributionCount,
  getCommunityVote,
  getOwnCommunityReport,
  getOwnCommunityReports,
  hasRememberedCommunityMapWithdrawal,
  readCommunityPersonalState,
  releaseCommunityReportReceipt,
  refreshCommunityReportReceipt,
  rememberCommunityMapWithdrawal,
  rememberCommunityReport,
  rememberCommunityVote,
  withdrawCommunityReport,
} from "./communityPersonalState";

function createStorage() {
  const values = new Map();
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
  };
}

describe("communityPersonalState", () => {
  it("remembers an own report only until its public expiry", () => {
    const storage = createStorage();
    const now = 1_000;
    const state = rememberCommunityReport(
      { reports: [], votes: [] },
      {
        expiresAt: 61_000,
        groupId: "rain:pordenone",
        id: "report-1",
        place: "Pordenone",
        sourceKey: "opaque-daily-key",
        typeId: "rain",
      },
      { now, storage },
    );

    expect(getOwnCommunityReport(state, "rain:pordenone")).toMatchObject({
      reportId: "report-1",
      sourceKey: "opaque-daily-key",
    });
    expect(readCommunityPersonalState({ now: 61_001, storage }).reports).toEqual([]);
  });

  it("forgets an undone report", () => {
    const storage = createStorage();
    const state = rememberCommunityReport(
      { reports: [], votes: [] },
      { expiresAt: 61_000, groupId: "wind:udine", id: "report-2" },
      { now: 1_000, storage },
    );

    expect(forgetCommunityReport(state, "report-2", { now: 2_000, storage }).reports).toEqual([]);
  });

  it("retains separate receipts for two own reports in the same group", () => {
    const storage = createStorage();
    const first = rememberCommunityReport({}, {
      id: "first", groupId: "rain:udine", expiresAt: 100_000,
    }, { now: 1_000, storage });
    const second = rememberCommunityReport(first, {
      id: "second", groupId: "rain:udine", expiresAt: 110_000,
    }, { now: 2_000, storage });
    const restored = readCommunityPersonalState({ now: 3_000, storage });

    expect(getOwnCommunityReports(restored, "rain:udine").map((report) => report.reportId))
      .toEqual(["first", "second"]);
    expect(getOwnCommunityReport(restored, "rain:udine").reportId).toBe("second");
    expect(getCommunityContributionCount(second)).toBe(2);
    const undone = forgetCommunityReport(restored, "second", { now: 4_000, storage });
    expect(getOwnCommunityReport(undone, "rain:udine").reportId).toBe("first");
    expect(getCommunityContributionCount(undone)).toBe(1);
    expect(undone).not.toHaveProperty("reportWithdrawals");
  });

  it("withdraws only the chosen receipt and preserves daily activity", () => {
    const storage = createStorage();
    const first = rememberCommunityReport({}, {
      id: "first", groupId: "rain:udine", expiresAt: 100_000,
    }, { now: 1_000, storage });
    const second = rememberCommunityReport(first, {
      id: "second", groupId: "rain:udine", expiresAt: 110_000,
    }, { now: 2_000, storage });
    const retired = withdrawCommunityReport(second, "second", { now: 3_000, storage });

    expect(getOwnCommunityReport(retired, "rain:udine").reportId).toBe("first");
    expect(getCommunityContributionCount(retired)).toBe(2);
    expect(retired.reportWithdrawals).toEqual([{ reportId: "second", expiresAt: 110_000 }]);
    expect(retired.mapWithdrawals).toEqual([]);
    const restored = readCommunityPersonalState({ now: 4_000, storage });
    expect(restored).toEqual(retired);
    const repeated = withdrawCommunityReport(restored, "second", { now: 5_000, storage, expiresAt: 90_000 });
    expect(repeated).toEqual(retired);

    const lateResponse = rememberCommunityReport(repeated, {
      id: "second", groupId: "rain:udine", expiresAt: 110_000,
    }, { now: 6_000, storage });
    expect(lateResponse).toEqual(retired);
    expect(getCommunityContributionCount(lateResponse)).toBe(2);
  });

  it("expires report-specific withdrawal evidence exactly at public expiry", () => {
    const storage = createStorage();
    const state = rememberCommunityReport({}, {
      id: "first", groupId: "rain:udine", expiresAt: 61_000,
    }, { now: 1_000, storage });
    withdrawCommunityReport(state, "first", { now: 2_000, storage });
    expect(readCommunityPersonalState({ now: 60_999, storage }).reportWithdrawals).toHaveLength(1);
    const expired = readCommunityPersonalState({ now: 61_000, storage });
    expect(expired).not.toHaveProperty("reportWithdrawals");
    expect(getCommunityContributionCount(expired)).toBe(1);
    expect(expired.reports).toEqual([]);
  });

  it("accepts a captured acknowledged report expiry but never invents one", () => {
    const storage = createStorage();
    const empty = readCommunityPersonalState({ now: 1_000, storage });
    expect(withdrawCommunityReport(empty, "unknown", { now: 1_000, storage }))
      .not.toHaveProperty("reportWithdrawals");
    const acknowledged = withdrawCommunityReport(empty, "acknowledged", {
      now: 1_000, storage, expiresAt: 61_000,
    });
    expect(acknowledged.reportWithdrawals).toEqual([{ reportId: "acknowledged", expiresAt: 61_000 }]);
    expect(getCommunityContributionCount(acknowledged)).toBe(0);
  });

  it("normalizes legacy state without adding withdrawal fields or losing receipts", () => {
    const storage = createStorage();
    storage.setItem(COMMUNITY_PERSONAL_STATE_KEY, JSON.stringify({
      reports: [
        { reportId: "first", groupId: "rain:udine", expiresAt: 61_000 },
        { reportId: "second", groupId: "rain:udine", expiresAt: 62_000 },
      ],
      votes: [],
    }));
    const normalized = readCommunityPersonalState({ now: 1_000, storage });
    expect(normalized.reports.map((report) => report.reportId)).toEqual(["first", "second"]);
    expect(Object.keys(normalized)).toEqual(["dailyContributions", "mapWithdrawals", "reports", "votes"]);
  });

  it("remembers only the latest local vote for an active group", () => {
    const storage = createStorage();
    const first = rememberCommunityVote(
      { reports: [], votes: [] },
      { expiresAt: 61_000, groupId: "rain:pordenone", vote: "yes" },
      { now: 1_000, storage },
    );
    const second = rememberCommunityVote(
      first,
      { expiresAt: 61_000, groupId: "rain:pordenone", vote: "no" },
      { now: 2_000, storage },
    );

    expect(getCommunityVote(second, "rain:pordenone")).toBe("no");
    expect(second.votes).toHaveLength(1);
    expect(getCommunityContributionCount(second)).toBe(1);
  });

  it("persists a map-withdrawal tombstone until the public group expires", () => {
    const storage = createStorage();
    rememberCommunityMapWithdrawal(
      { reports: [], votes: [] },
      { expiresAt: 61_000, groupId: "rain:pordenone" },
      { now: 1_000, storage },
    );

    const restored = readCommunityPersonalState({ now: 2_000, storage });
    expect(hasRememberedCommunityMapWithdrawal(restored, "rain:pordenone")).toBe(true);
    expect(restored.mapWithdrawals).toEqual([{
      expiresAt: 61_000,
      groupId: "rain:pordenone",
    }]);

    const expired = readCommunityPersonalState({ now: 61_001, storage });
    expect(hasRememberedCommunityMapWithdrawal(expired, "rain:pordenone")).toBe(false);
    expect(expired.mapWithdrawals).toEqual([]);
  });

  it("keeps the furthest withdrawal expiry across repeated stale responses", () => {
    const storage = createStorage();
    const first = rememberCommunityMapWithdrawal(
      { reports: [], votes: [] },
      { expiresAt: 61_000, groupId: "wind:cordenons" },
      { now: 1_000, storage },
    );
    const repeated = rememberCommunityMapWithdrawal(
      first,
      { expiresAt: 41_000, groupId: "wind:cordenons" },
      { now: 2_000, storage },
    );

    expect(repeated.mapWithdrawals).toEqual([{
      expiresAt: 61_000,
      groupId: "wind:cordenons",
    }]);
  });

  it("counts each active local contribution only once", () => {
    const storage = createStorage();
    const firstReport = rememberCommunityReport(
      { reports: [], votes: [] },
      { expiresAt: 61_000, groupId: "rain:pordenone", id: "report-1" },
      { now: 1_000, storage },
    );
    const repeatedReport = rememberCommunityReport(
      firstReport,
      { expiresAt: 62_000, groupId: "rain:pordenone", id: "report-1" },
      { now: 2_000, storage },
    );
    const confirmed = rememberCommunityVote(
      repeatedReport,
      { expiresAt: 63_000, groupId: "snow:udine", vote: "yes" },
      { now: 3_000, storage },
    );
    const changedVote = rememberCommunityVote(
      confirmed,
      { expiresAt: 64_000, groupId: "snow:udine", vote: "no" },
      { now: 4_000, storage },
    );

    expect(getCommunityContributionCount(changedVote)).toBe(2);
  });

  it("removes an undone report from today's contribution count", () => {
    const storage = createStorage();
    const state = rememberCommunityReport(
      { reports: [], votes: [] },
      { expiresAt: 61_000, groupId: "wind:udine", id: "report-2" },
      { now: 1_000, storage },
    );

    expect(getCommunityContributionCount(
      forgetCommunityReport(state, "report-2", { now: 2_000, storage }),
    )).toBe(0);
  });

  it("keeps today's count after the public report or vote expires", () => {
    const storage = createStorage();
    const reported = rememberCommunityReport(
      { reports: [], votes: [] },
      { expiresAt: 61_000, groupId: "rain:pordenone", id: "report-1" },
      { now: 1_000, storage },
    );
    rememberCommunityVote(
      reported,
      { expiresAt: 61_000, groupId: "snow:udine", vote: "yes" },
      { now: 2_000, storage },
    );

    const expired = readCommunityPersonalState({ now: 62_000, storage });
    expect(expired.reports).toEqual([]);
    expect(expired.votes).toEqual([]);
    expect(getCommunityContributionCount(expired)).toBe(2);
  });

  it("undoes only the matching contribution when other activity exists", () => {
    const storage = createStorage();
    const reported = rememberCommunityReport(
      { reports: [], votes: [] },
      { expiresAt: 61_000, groupId: "rain:pordenone", id: "report-1" },
      { now: 1_000, storage },
    );
    const confirmed = rememberCommunityVote(
      reported,
      { expiresAt: 61_000, groupId: "snow:udine", vote: "yes" },
      { now: 2_000, storage },
    );

    expect(getCommunityContributionCount(
      forgetCommunityReport(confirmed, "report-1", { now: 3_000, storage }),
    )).toBe(1);
  });

  it("keeps report counting idempotent across a storage round trip", () => {
    const storage = createStorage();
    rememberCommunityReport(
      { reports: [], votes: [] },
      { expiresAt: 61_000, groupId: "rain:pordenone", id: "report-1" },
      { now: 1_000, storage },
    );
    const restored = readCommunityPersonalState({ now: 2_000, storage });
    const repeated = rememberCommunityReport(
      restored,
      { expiresAt: 62_000, groupId: "rain:pordenone", id: "report-1" },
      { now: 3_000, storage },
    );

    expect(getCommunityContributionCount(repeated)).toBe(1);
    expect(repeated.dailyContributions).not.toHaveProperty("keys");
  });

  it("treats a new observation after public expiry as another contribution", () => {
    const storage = createStorage();
    rememberCommunityReport(
      { reports: [], votes: [] },
      { expiresAt: 61_000, groupId: "rain:pordenone", id: "report-1" },
      { now: 1_000, storage },
    );
    const expired = readCommunityPersonalState({ now: 62_000, storage });
    const observedAgain = rememberCommunityReport(
      expired,
      { expiresAt: 122_000, groupId: "rain:pordenone", id: "report-2" },
      { now: 62_000, storage },
    );

    expect(getCommunityContributionCount(observedAgain)).toBe(2);
  });

  it("refreshes the same receipt after a clock race without adding a contribution", () => {
    const storage = createStorage();
    rememberCommunityReport({}, {
      id: "report-update", groupId: "rain:pordenone", expiresAt: 3_601_000, revision: 1,
    }, { now: 1_000, storage });
    const locallyExpired = readCommunityPersonalState({ now: 3_601_001, storage });
    expect(locallyExpired.reports).toEqual([]);
    expect(getCommunityContributionCount(locallyExpired)).toBe(1);

    const refreshed = refreshCommunityReportReceipt(locallyExpired, {
      id: "report-update",
      groupId: "rain:pordenone",
      expiresAt: 7_201_001,
      revision: 2,
      typeId: "rain",
    }, { now: 3_601_001, storage });
    expect(getCommunityContributionCount(refreshed)).toBe(1);
    expect(getOwnCommunityReport(refreshed, "rain:pordenone")).toMatchObject({
      expiresAt: 7_201_001,
      reportId: "report-update",
      revision: 2,
    });
  });

  it("records a server expiry without undoing activity or retaining ownership", () => {
    const storage = createStorage();
    const state = rememberCommunityReport({}, {
      id: "report-expired", groupId: "fog:udine", expiresAt: 61_000, revision: 1,
    }, { now: 1_000, storage });
    const expired = expireCommunityReport(state, "report-expired", { now: 2_000, storage });

    expect(expired.reports).toEqual([]);
    expect(getCommunityContributionCount(expired)).toBe(1);
    expect(expired.reportExpirations).toEqual([{
      expiresAt: 3_902_000,
      reportId: "report-expired",
    }]);
    expect(readCommunityPersonalState({ now: 3_902_000, storage }))
      .not.toHaveProperty("reportExpirations");
  });

  it("releases a mismatched ownership receipt without hiding public data or changing quota", () => {
    const storage = createStorage();
    const state = rememberCommunityReport({}, {
      id: "report-owner-mismatch",
      groupId: "rain:pordenone",
      expiresAt: 61_000,
      revision: 1,
    }, { now: 1_000, storage });

    const released = releaseCommunityReportReceipt(
      state,
      "report-owner-mismatch",
      { now: 2_000, storage },
    );
    expect(released.reports).toEqual([]);
    expect(getCommunityContributionCount(released)).toBe(1);
    expect(released).not.toHaveProperty("reportExpirations");
    expect(released).not.toHaveProperty("reportWithdrawals");
    expect(released.mapWithdrawals).toEqual([]);
  });

  it("does not subtract today's activity when undoing yesterday's report", () => {
    const storage = createStorage();
    const firstDay = new Date(2026, 7, 29, 23, 58).getTime();
    const secondDay = new Date(2026, 7, 30, 0, 1).getTime();
    const reported = rememberCommunityReport(
      { reports: [], votes: [] },
      {
        expiresAt: firstDay + 60 * 60_000,
        groupId: "rain:pordenone",
        id: "report-1",
      },
      { now: firstDay, storage },
    );
    const confirmed = rememberCommunityVote(
      reported,
      {
        expiresAt: secondDay + 60 * 60_000,
        groupId: "snow:udine",
        vote: "yes",
      },
      { now: secondDay, storage },
    );

    const undone = forgetCommunityReport(
      confirmed,
      "report-1",
      { now: secondDay + 60_000, storage },
    );
    expect(getCommunityContributionCount(undone)).toBe(1);
    expect(undone.votes).toHaveLength(1);
  });

  it("migrates legacy daily keys to a count without retaining identifiers", () => {
    const storage = createStorage();
    const now = new Date(2026, 7, 29, 12).getTime();
    const dayKey = readCommunityPersonalState({ now, storage }).dailyContributions.dayKey;
    storage.setItem(COMMUNITY_PERSONAL_STATE_KEY, JSON.stringify({
      dailyContributions: {
        dayKey,
        expiresAt: now + 60_000,
        keys: ["report:one", "report:one", "vote:two"],
      },
      reports: [],
      votes: [],
    }));

    const migrated = readCommunityPersonalState({ now, storage });
    expect(getCommunityContributionCount(migrated)).toBe(2);
    expect(JSON.parse(storage.getItem(COMMUNITY_PERSONAL_STATE_KEY)).dailyContributions)
      .not.toHaveProperty("keys");
  });

  it("resets the local contribution count at the next local day", () => {
    const storage = createStorage();
    const firstDay = new Date(2026, 7, 29, 23, 58).getTime();
    const secondDay = new Date(2026, 7, 30, 0, 1).getTime();
    rememberCommunityReport(
      { reports: [], votes: [] },
      { expiresAt: firstDay + 60 * 60_000, groupId: "rain:pordenone", id: "report-1" },
      { now: firstDay, storage },
    );

    expect(getCommunityContributionCount(
      readCommunityPersonalState({ now: secondDay, storage }),
    )).toBe(0);
  });
});


describe("observation-bound votes", () => {
  it("does not transfer a cached vote or map withdrawal when a group ID is reused", () => {
    const storage = createStorage();
    const options = { now: 1000, storage };
    let state = rememberCommunityVote({}, {
      groupId: "rain:001:hour", reportIds: ["old-report"], vote: "no", expiresAt: 60000,
    }, options);
    rememberCommunityMapWithdrawal(state, {
      groupId: "rain:001:hour", reportIds: ["old-report"], expiresAt: 60000,
    }, options);
    state = readCommunityPersonalState(options);
    expect(getCommunityVote(state, "rain:001:hour", ["old-report"])).toBe("no");
    expect(getCommunityVote(state, "rain:001:hour", ["new-report"])).toBe("");
    expect(hasRememberedCommunityMapWithdrawal(state, "rain:001:hour", ["new-report"])).toBe(false);
    const legacy = { votes: [{ groupId: "rain:001:hour", vote: "no" }] };
    expect(getCommunityVote(legacy, "rain:001:hour", ["new-report"])).toBe("");
    state = rememberCommunityVote(state, {
      groupId: "rain:001:hour", reportIds: ["new-report"], vote: "yes", expiresAt: 70000,
    }, options);
    expect(getCommunityVote(state, "rain:001:hour", ["new-report"])).toBe("yes");
  });
});
