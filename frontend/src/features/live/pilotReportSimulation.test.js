import { describe, expect, it } from "vitest";
import { applyPilotReportSimulation, applyPilotReportSimulationSubmission, createCommunityReportSimulationOverlay } from "./communityReportPreview";

const now = Date.parse("2026-09-21T12:00:00Z");
const location = { selectedPlace: "Pordenone", coords: { lat: 45.9567, lon: 12.6605 } };

describe("isolated pilot browser QA", () => {
  it("replaces and creates on the retirement overlay only after explicit submission", () => {
    const initial = createCommunityReportSimulationOverlay({}, { now });
    const first = applyPilotReportSimulation(initial, "create", { typeId: "quiet", location }, { now });
    const result = applyPilotReportSimulationSubmission(first.overlay, "wind", location, {
      replacementReport: first.result.report,
    }, { now: now + 301_000 });
    expect(first.overlay.ownedReportIds).toEqual([first.result.report.id]);
    expect(result.result).toMatchObject({ ok: true, replacementPhase: "creation", replacementWithdrawn: true, replacedReportId: first.result.report.id });
    expect(result.overlay.ownedReportIds).toEqual([result.result.report.id]);
    expect(result.result.report).toMatchObject({ typeId: "wind", replacementAvailable: false });
    expect(result.overlay.reports.some((entry) => entry.id === first.result.report.id)).toBe(false);
    expect(result.overlay.pilotCreates).toHaveLength(2);
  });

  it("preserves the retired state and token when creation fails, then resumes without retiring again", () => {
    const initial = createCommunityReportSimulationOverlay({}, { now });
    const first = applyPilotReportSimulation(initial, "create", { typeId: "quiet", location }, { now });
    const limited = { ...first.overlay, pilotCreates: [now - 20 * 60_000, now - 10 * 60_000, now - 5 * 60_000, now] };
    const failed = applyPilotReportSimulationSubmission(limited, "wind", location, {
      replacementReport: first.result.report,
    }, { now: now + 301_000 });
    expect(failed.result).toMatchObject({ ok: false, code: "community_hourly_limit", replacementWithdrawn: true });
    expect(failed.overlay.ownedReportIds).toHaveLength(0);
    expect(failed.overlay.pilotReplacement.token).toBe(failed.result.replacementToken);
    expect(failed.overlay.pilotCreates).toEqual(limited.pilotCreates);
    const retried = applyPilotReportSimulationSubmission(failed.overlay, "wind", location, {
      replacementReport: first.result.report,
    }, { now: now + 40 * 60_000 });
    expect(retried.result.ok).toBe(true);
    expect(retried.overlay.ownedReportIds).toEqual([retried.result.report.id]);
    expect(retried.result.report.replacementAvailable).toBe(false);
    expect(retried.overlay.pilotReplacement).toBeNull();
  });

  it("does not auto-replace a correction whose window has closed", () => {
    const first = applyPilotReportSimulation(createCommunityReportSimulationOverlay({}, { now }), "create", { typeId: "quiet", location }, { now });
    const failed = applyPilotReportSimulationSubmission(first.overlay, "wind", location, {
      correctionReport: { ...first.result.report, reportId: first.result.report.id },
    }, { now: now + 301_000 });
    expect(failed.result).toMatchObject({ ok: false, code: "community_correction_window_closed" });
    expect(failed.overlay).toBe(first.overlay);
    expect(failed.overlay.pilotReplacement).toBeFalsy();
    expect(failed.overlay.ownedReportIds).toEqual([first.result.report.id]);
  });

  it("corrects the same contribution then permits exactly one explicit replacement", () => {
    const initial = createCommunityReportSimulationOverlay({}, { now });
    const first = applyPilotReportSimulation(initial, "create", { typeId: "quiet", location }, { now });
    const corrected = applyPilotReportSimulation(first.overlay, "correct", { reportId: first.result.report.id, typeId: "wind", location }, { now: now + 5000 });
    expect(corrected.result.report).toMatchObject({ id: first.result.report.id, expiresAt: first.result.report.expiresAt, typeId: "wind", revision: 2 });
    expect(corrected.overlay.ownedReportIds).toHaveLength(1);
    expect(corrected.overlay.pilotCreates).toHaveLength(1);
    const withdrawn = applyPilotReportSimulation(corrected.overlay, "replace", { reportId: corrected.result.report.id }, { now: now + 6000 });
    expect(withdrawn.overlay.ownedReportIds).toHaveLength(0);
    expect(withdrawn.result.replacementToken).toBeTruthy();
    const replacement = applyPilotReportSimulation(withdrawn.overlay, "create", { typeId: "quiet", location, replacementToken: withdrawn.result.replacementToken }, { now: now + 7000 });
    expect(replacement.result.report.replacementAvailable).toBe(false);
    expect(replacement.overlay.pilotCreates).toHaveLength(2);
    expect(applyPilotReportSimulation(replacement.overlay, "replace", { reportId: replacement.result.report.id }, { now: now + 8000 }).result.code).toBe("community_replacement_unavailable");
  });

  it("retains rolling quota history through withdrawal and supports different phenomena after two minutes", () => {
    const initial = createCommunityReportSimulationOverlay({}, { now });
    const first = applyPilotReportSimulation(initial, "create", { typeId: "quiet", location }, { now });
    expect(applyPilotReportSimulation(first.overlay, "create", { typeId: "wind", location }, { now: now + 1000 }).result.code).toBe("community_minimum_interval");
    const second = applyPilotReportSimulation(first.overlay, "create", { typeId: "wind", location }, { now: now + 120_000 });
    expect(second.result.ok).toBe(true);
    expect(second.overlay.ownedReportIds).toHaveLength(2);
    const withdrawn = applyPilotReportSimulation(second.overlay, "withdraw", { reportId: second.result.report.id }, { now: now + 125_000 });
    expect(withdrawn.overlay.pilotCreates).toHaveLength(2);
    expect(applyPilotReportSimulation(withdrawn.overlay, "create", { typeId: "snow", location }, { now: now + 130_000 }).result.code).toBe("community_minimum_interval");
  });
});
