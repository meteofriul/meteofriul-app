import { describe, expect, it } from "vitest";
import { createPreviewState, creationWait, currentRecords, historyRecords, HOUR, MINUTE, previewReducer, rankFor } from "./communityPreviewState";

const NOW = Date.UTC(2026, 9, 13, 10, 20);
const initial = () => createPreviewState(NOW);
const submit = (state, phenomenon = "storm", options = {}) => previewReducer(state, { type: "submit", phenomenon, gps: true, ...options });
const advance = (state, minutes) => previewReducer(state, { type: "advance", minutes });
const witness = (state, id = state.records[0].id) => previewReducer(state, { type: "witness", id });

describe("Community UI preview scenarios (not backend integration)", () => {
  it("replaces only the author's active observation, without inheriting votes or points", () => {
    const state = initial();
    const next = submit(state);
    expect(currentRecords(next).filter((r) => r.mine && r.status === "active")).toHaveLength(1);
    expect(next.records[0]).toMatchObject({ type: "storm", yes: 0, no: 0, validated: false, point: false });
    expect(next.records.find((r) => r.id === "own-wind")).toMatchObject({ status: "replaced", point: true });
    expect(next.records.find((r) => r.id === "other-rain").status).toBe("active");
    expect(next.total).toBe(9);
    expect(next.points).toBe(4);
    expect(state.records[0].status).toBe("active");
  });

  it.each([{ fail: true }, { gps: false }])("failed submission preserves the previous report and quotas: %j", (options) => {
    const state = initial();
    const failed = submit(state, "storm", options);
    expect(failed.error).toBeTruthy();
    expect(failed.records).toEqual(state.records);
    expect(failed.creations).toEqual(state.creations);
    expect(failed.total).toBe(state.total);
    const retry = submit(failed);
    expect(retry.error).toBe("");
    expect(retry.total).toBe(state.total + 1);
  });

  it("counts validation independently of the 3-hour reward restriction, without moving its deadline", () => {
    const state = submit(initial(), "wind");
    const next = witness(state);
    expect(next.validated).toBe(6);
    expect(next.points).toBe(4);
    expect(next.awards["wind:Pordenone"]).toBe(NOW - 6 * MINUTE);
    expect(witness(next).validated).toBe(6);
    expect(witness(next).points).toBe(4);
  });

  it("allows the next award exactly 3 hours after the last award, while the new report is still active", () => {
    const fresh = submit(advance(initial(), 173), "wind");
    const early = witness(fresh);
    expect(early.points).toBe(4);
    expect(early.validated).toBe(6);
    const atDeadline = witness(advance(early, 1));
    expect(atDeadline.points).toBe(5);
    expect(atDeadline.validated).toBe(6);
    expect(atDeadline.awards["wind:Pordenone"]).toBe(NOW + 174 * MINUTE);
    expect(witness(atDeadline).points).toBe(5);
  });

  it("has no daily point cap and a different phenomenon is not blocked by the wind award", () => {
    const state = { ...initial(), points: 25 };
    const next = witness(submit(state, "storm"));
    expect(next.points).toBe(26);
    expect(next.awards["wind:Pordenone"]).toBe(state.awards["wind:Pordenone"]);
  });

  it("an independent active matching report validates the new report, but archived evidence does not", () => {
    const matching = submit(initial(), "rain");
    expect(matching.records[0]).toMatchObject({ point: true, validated: true, yes: 0 });
    const expiredEvidence = submit(advance(initial(), 60), "rain");
    expect(expiredEvidence.records[0]).toMatchObject({ point: false, validated: false, yes: 0 });
  });

  it("a delayed confirmation cannot validate a replacement or award an expired report", () => {
    const replaced = submit(initial());
    const late = witness(replaced, "own-wind");
    expect(late.error).toBeTruthy();
    expect(late.records[0].validated).toBe(false);
    const expired = witness(advance(replaced, 60));
    expect(expired.error).toBeTruthy();
    expect(expired.points).toBe(4);
  });

  it("preserves the existing hourly group boundary for independent matching observations", () => {
    const state = createPreviewState(Date.UTC(2026, 9, 13, 11));
    const next = submit(state, "rain");
    expect(next.records.find((r) => r.id === "other-rain").status).toBe("active");
    expect(next.records[0].validated).toBe(false);
  });

  it("quiet counts as an accepted and confirmed observation but awards no point", () => {
    const state = witness(submit(initial(), "quiet"));
    expect(state.total).toBe(9);
    expect(state.validated).toBe(6);
    expect(state.points).toBe(4);
  });

  it("enforces the 3-minute boundary and retains rolling hourly quota after replacement", () => {
    const state = submit(initial());
    expect(creationWait(advance(state, 2)).seconds).toBe(60);
    expect(submit(advance(state, 2)).error).toBeTruthy();
    const second = submit(advance(state, 3), "snow");
    const third = submit(advance(second, 3), "hail");
    expect(creationWait(third)).toEqual({ reason: "hour", seconds: 46 * 60 });
    expect(creationWait(advance(third, 46)).seconds).toBe(0);
  });

  it("enforces 12 submissions in rolling 24 hours and releases the oldest slot at the boundary", () => {
    const state = { ...initial(), creations: Array.from({ length: 12 }, (_, i) => NOW - (23 - i) * HOUR) };
    expect(creationWait(state)).toEqual({ reason: "day", seconds: 3600 });
    expect(submit(state).error).toBeTruthy();
    expect(creationWait(advance(state, 60)).seconds).toBe(0);
  });

  it.each(["yes", "no"])("requires GPS for %s votes and never awards the voter", (vote) => {
    const state = initial();
    const action = { type: "vote", id: "other-fog", vote, gps: false };
    const rejected = previewReducer(state, action);
    expect(rejected.error).toBeTruthy();
    expect(rejected.records).toEqual(state.records);
    const accepted = previewReducer(state, { ...action, gps: true });
    expect(accepted.points).toBe(4);
    expect(accepted.validated).toBe(5);
    expect(accepted.records.find((r) => r.id === action.id).voted).toBe(vote);
    expect(previewReducer(accepted, { ...action, gps: true }).records).toEqual(accepted.records);
    expect(previewReducer(state, { ...action, id: "own-wind", gps: true }).error).toBeTruthy();
  });

  it("the third independent cessation removes the report, without revoking earned points", () => {
    const state = initial();
    state.records = state.records.map((r) => r.id === "other-fog" ? { ...r, no: 2 } : r);
    const next = previewReducer(state, { type: "vote", id: "other-fog", vote: "no", gps: true });
    expect(next.records.find((r) => r.id === "other-fog").status).toBe("ceased");
    expect(next.points).toBe(state.points);
  });

  it("keeps history for 48 hours from creation, without removing cumulative counters", () => {
    const state = submit(initial());
    expect(historyRecords(advance(state, 48 * 60 - 1)).map((r) => r.id)).toEqual(["preview-1"]);
    const later = advance(state, 48 * 60);
    expect(historyRecords(later)).toEqual([]);
    expect(later.total).toBe(9);
    expect(later.points).toBe(4);
  });

  it("changes cosmetic rank at 5 and 15 points", () => {
    expect(rankFor(4)).toBe("Osservadôr dal Cîl");
    expect(rankFor(5)).toBe("Vuaite dal Timp");
    expect(rankFor(14)).toBe("Vuaite dal Timp");
    expect(rankFor(15)).toBe("Sentinele dal Teritori");
  });
});
