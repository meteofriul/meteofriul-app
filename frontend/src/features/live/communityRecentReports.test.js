import { describe, expect, it } from "vitest";
import { buildCommunityRecentItems, COMMUNITY_RECENT_WINDOW_MS, getCommunityHistoryTimeLabel } from "./communityRecentReports";
import { getLiveViewCopy } from "../../copy/liveViewCopy";

const now = 1_800_000_000_000;
const history = (id, age, status = "expired") => ({ id, createdAt: now - age,
  expiresAt: now - age + 3_600_000, status, typeId: "rain" });

describe("real recent reports", () => {
  it.each([[0, "Adesso"], [59, "59 min fa"], [60, "1 ora fa"], [120, "2 ore fa"],
    [24 * 60, "24 ore fa"], [48 * 60 - 1, "47 ore fa"]])("formats the elapsed time at %i minutes", (minutes, label) => {
    expect(getCommunityHistoryTimeLabel(now - minutes * 60_000, now, getLiveViewCopy("it"))).toBe(label);
  });
  it("keeps grouped archive counts and frozen votes when live reports expire", () => {
    const row = { ...history("group-last", 4_000_000), count: 3, confirmations: { yes: 4, no: 1 } };
    expect(buildCommunityRecentItems([row], [], now)[0]).toMatchObject({ count: 3, confirmations: { yes: 4, no: 1 } });
    expect(getCommunityHistoryTimeLabel(now - 7_200_000, now, getLiveViewCopy("fur"))).toBe("2 oris fa");
  });
  it("keeps live groups once, merges archives chronologically and excludes the 48-hour boundary", () => {
    const rows = [history("a", 5000, "active"), history("b", 6000, "active"),
      history("older", 4_000_000), history("boundary", COMMUNITY_RECENT_WINDOW_MS)];
    const group = { id: "group", reportIds: ["a", "b"], createdAt: now - 5000, expiresAt: now + 1000 };
    const items = buildCommunityRecentItems(rows, [group], now);
    expect(items.map((row) => [row.id, row.recentKind])).toEqual([["group", "live"], ["older", "history"]]);
  });
  it("never lets an expired or replaced observation open the live detail", () => {
    const rows = [history("a", 5000, "replaced"), history("b", 3_600_000, "active")];
    const staleGroups = [{ id: "group-a", reportIds: ["a"], expiresAt: now + 1000 },
      { id: "group-b", reportIds: ["b"], expiresAt: now }];
    expect(buildCommunityRecentItems(rows, staleGroups, now).map((row) => [row.id, row.status, row.recentKind]))
      .toEqual([["a", "replaced", "history"], ["b", "expired", "history"]]);
  });
  it("keeps a new live group visible while history refreshes and does not mutate either feed", () => {
    const row = Object.freeze(history("previous", 2000, "replaced"));
    const group = Object.freeze({ id: "new", reportIds: ["new-id"], createdAt: now, expiresAt: now + 1000 });
    expect(buildCommunityRecentItems([row], [group], now).map((item) => item.id)).toEqual(["new", "previous"]);
  });
});
