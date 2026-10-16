import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../services/localCommunityPilot", async (importOriginal) => ({
  ...await importOriginal(), isLocalCommunityPilot: vi.fn(() => true),
}));

import { isLocalCommunityPilot } from "../../services/localCommunityPilot";
import { createCommunityReportPreviewMemoryStorage } from "./communityReportPreview";
import { readCommunityPersonalState, rememberCommunityReport } from "./communityPersonalState";
import { submitLiveCommunityReport } from "./liveReportController";
import { COMMUNITY_GUIDELINES_POLICY_VERSION } from "./liveReportPolicy";
import { getPilotMutationFeedback, performPilotReportOperation, readPilotPendingOperations, readPilotReplacement } from "./pilotReportOperations";

const NOW = Date.parse("2026-09-21T12:00:00Z");
const oldReport = { id: "old-rain", reportId: "old-rain", groupId: "rain-pordenone", typeId: "rain", place: "Pordenone", istatCode: "093033", revision: 2, expiresAt: NOW + 3_000_000, correctionUntil: NOW - 1, replacementAvailable: true };
const newReport = { ...oldReport, id: "new-wind", reportId: "new-wind", groupId: "wind-pordenone", typeId: "wind", revision: 1, replacementAvailable: false };
const location = () => ({ coords: { lat: 45.9567, lon: 12.6605, accuracyM: 40 }, locatedAt: Date.now() - 1000, istatCode: "093033", selectedPlace: "Pordenone", nearbyPlaces: [{ place: "Pordenone" }] });
const retired = { ok: true, action: "replacement_ready", report_id: oldReport.id, replacement_token: "qa-grant", replacement_expires_at: oldReport.expiresAt };

let storage;
let withdrawer;
let creator;
let corrector;
let resolver;
let pilotOperation;
let options;

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(NOW);
  vi.mocked(isLocalCommunityPilot).mockReturnValue(true);
  storage = createCommunityReportPreviewMemoryStorage();
  rememberCommunityReport(readCommunityPersonalState({ storage }), oldReport, { storage });
  withdrawer = vi.fn().mockResolvedValue(retired);
  creator = vi.fn().mockResolvedValue({ ok: true, report: newReport });
  corrector = vi.fn();
  resolver = vi.fn().mockResolvedValue({ status: "not_found" });
  let sequence = 0;
  pilotOperation = vi.fn((kind, payload, operationOptions) => performPilotReportOperation(kind, payload, {
    ...operationOptions,
    sender: kind === "replace" ? withdrawer : kind === "correct" ? corrector : creator,
    resolver,
    clientIdResolver: () => "pilot-test-installation",
    operationIdFactory: () => `replacement-test-operation-${++sequence}`,
  }));
  options = { acceptedTerms: true, replacementReport: oldReport, operationStorage: storage, pilotOperation };
});

afterEach(() => vi.useRealTimers());

describe("explicit pilot replace-and-submit pipeline", () => {
  it("retires exactly the selected receipt then creates with its persisted grant", async () => {
    expect(withdrawer).not.toHaveBeenCalled();
    const result = await submitLiveCommunityReport("wind", location(), options);
    expect(result).toMatchObject({ ok: true, report: newReport, replacedReportId: oldReport.id, replacementPhase: "creation", replacementWithdrawn: true });
    expect(pilotOperation.mock.calls.map(([kind]) => kind)).toEqual(["replace", "create"]);
    expect(withdrawer).toHaveBeenCalledExactlyOnceWith(expect.objectContaining({ reportId: oldReport.id, expectedRevision: 2, action: "replace" }));
    expect(creator).toHaveBeenCalledExactlyOnceWith(expect.objectContaining({ typeId: "wind", replacementToken: "qa-grant", istatCode: "093033" }));
    expect(readPilotReplacement({ storage })).toBeNull();
    expect(readCommunityPersonalState({ storage }).reports.map((entry) => entry.reportId)).toEqual([newReport.id]);
  });

  it("does not create after a lost retirement response and recovers the same operation first", async () => {
    withdrawer.mockRejectedValueOnce(new Error("response lost"));
    const result = await submitLiveCommunityReport("wind", location(), options);
    expect(result).toMatchObject({ ok: false, uncertain: true, replacementPhase: "withdrawal", replacementWithdrawn: false });
    expect(creator).not.toHaveBeenCalled();
    const pending = readPilotPendingOperations({ storage })[0];
    expect(pending.kind).toBe("replace");
    expect(getPilotMutationFeedback(result)).toContain("nessun nuovo invio è stato avviato");

    resolver.mockResolvedValueOnce({ status: "accepted", result: retired });
    expect(await submitLiveCommunityReport("wind", location(), options)).toMatchObject({ ok: true });
    expect(resolver).toHaveBeenCalledWith(expect.objectContaining({ operationId: pending.operationId }));
    expect(withdrawer).toHaveBeenCalledOnce();
    expect(creator).toHaveBeenCalledOnce();
  });

  it("retries a not-arrived retirement using its original operation ID", async () => {
    withdrawer.mockRejectedValueOnce(new Error("offline"));
    await submitLiveCommunityReport("wind", location(), options);
    await submitLiveCommunityReport("wind", location(), options);
    expect(withdrawer).toHaveBeenCalledTimes(2);
    expect(withdrawer.mock.calls[1][0].operationId).toBe(withdrawer.mock.calls[0][0].operationId);
    expect(creator).toHaveBeenCalledOnce();
  });

  it("recovers a lost create response without another retirement or duplicate create", async () => {
    creator.mockRejectedValueOnce(new Error("create response lost"));
    const result = await submitLiveCommunityReport("wind", location(), options);
    expect(result).toMatchObject({ ok: false, uncertain: true, replacementPhase: "creation", replacementWithdrawn: true, replacementToken: "qa-grant" });
    expect(getPilotMutationFeedback(result)).toContain("L’esito del nuovo invio è da verificare");
    const pending = readPilotPendingOperations({ storage })[0];
    expect(pending.kind).toBe("create");
    expect(readPilotReplacement({ storage }).reportId).toBe(oldReport.id);
    resolver.mockResolvedValueOnce({ status: "accepted", result: { ok: true, report: newReport } });

    expect(await submitLiveCommunityReport("wind", location(), options)).toMatchObject({ ok: true, report: newReport });
    expect(resolver).toHaveBeenCalledWith(expect.objectContaining({ operationId: pending.operationId }));
    expect(withdrawer).toHaveBeenCalledOnce();
    expect(creator).toHaveBeenCalledOnce();
    expect(readPilotReplacement({ storage })).toBeNull();
  });

  it("retains an acknowledged grant after a quota rejection and reuses it on retry", async () => {
    creator.mockRejectedValueOnce({ status: 429, detail: { code: "community_hourly_limit" } });
    const result = await submitLiveCommunityReport("wind", location(), options);
    expect(result).toMatchObject({ ok: false, replacementWithdrawn: true, replacementToken: "qa-grant" });
    expect(getPilotMutationFeedback(result)).toContain("La precedente segnalazione è stata ritirata");
    expect(getPilotMutationFeedback(result)).toContain("ultimi 60 minuti");
    expect(readPilotReplacement({ storage }).token).toBe("qa-grant");
    expect(readPilotPendingOperations({ storage })).toHaveLength(0);
    expect(await submitLiveCommunityReport("wind", location(), options)).toMatchObject({ ok: true });
    expect(withdrawer).toHaveBeenCalledOnce();
    expect(creator).toHaveBeenCalledTimes(2);
    expect(creator.mock.calls[1][0].replacementToken).toBe("qa-grant");
  });

  it.each([
    ["stale GPS", { locatedAt: NOW - 120_001 }],
    ["future GPS", { locatedAt: NOW + 1 }],
    ["missing GPS timestamp", { locatedAt: undefined }],
    ["inaccurate GPS", { coords: { lat: 45.95, lon: 12.66, accuracyM: 501 } }],
    ["zero accuracy", { coords: { lat: 45.95, lon: 12.66, accuracyM: 0 } }],
    ["missing coordinate", { coords: { lon: 12.66, accuracyM: 20 } }],
    ["invalid ISTAT", { istatCode: "" }],
    ["unverified selected Comune", { selectedPlace: "Roma" }],
  ])("rejects %s before retiring anything", async (_label, override) => {
    expect(await submitLiveCommunityReport("wind", { ...location(), ...override }, options)).toMatchObject({ ok: false });
    expect(pilotOperation).not.toHaveBeenCalled();
    expect(withdrawer).not.toHaveBeenCalled();
    expect(creator).not.toHaveBeenCalled();
  });

  it("requires current terms and a valid source revision before retirement", async () => {
    expect(await submitLiveCommunityReport("wind", location(), { ...options, acceptedTerms: false })).toMatchObject({ reason: "terms_required" });
    expect(await submitLiveCommunityReport("wind", location(), { ...options, policyVersion: `${COMMUNITY_GUIDELINES_POLICY_VERSION}-old` })).toMatchObject({ reason: "terms_required" });
    expect(await submitLiveCommunityReport("wind", location(), { ...options, replacementReport: { reportId: oldReport.id } })).toMatchObject({ reason: "invalid_report" });
    expect(pilotOperation).not.toHaveBeenCalled();
  });

  it("keeps the grant if GPS becomes stale during retirement and resumes only with fresh GPS", async () => {
    withdrawer.mockImplementationOnce(async () => { vi.setSystemTime(NOW + 120_001); return retired; });
    const result = await submitLiveCommunityReport("wind", location(), options);
    expect(result).toMatchObject({ ok: false, replacementWithdrawn: true, replacementPhase: "creation", reason: "stale_or_imprecise" });
    expect(creator).not.toHaveBeenCalled();
    expect(readPilotReplacement({ storage }).token).toBe("qa-grant");
    expect(await submitLiveCommunityReport("wind", location(), options)).toMatchObject({ ok: true });
    expect(withdrawer).toHaveBeenCalledOnce();
    expect(creator).toHaveBeenCalledOnce();
  });

  it("does not consume a grant belonging to another source report", async () => {
    await pilotOperation("replace", { reportId: oldReport.id, expectedRevision: 2 }, { storage });
    pilotOperation.mockClear();
    expect(await submitLiveCommunityReport("wind", location(), { ...options, replacementReport: { ...oldReport, reportId: "other-source" } })).toMatchObject({ reason: "pending_operation" });
    expect(pilotOperation).not.toHaveBeenCalled();
    expect(creator).not.toHaveBeenCalled();
  });

  it("never converts an expired correction into replacement", async () => {
    corrector.mockRejectedValueOnce({ status: 409, detail: { code: "community_correction_window_closed" } });
    expect(await submitLiveCommunityReport("wind", location(), { ...options, replacementReport: null, correctionReport: oldReport })).toMatchObject({ ok: false, code: "community_correction_window_closed" });
    expect(pilotOperation.mock.calls.map(([kind]) => kind)).toEqual(["correct"]);
    expect(withdrawer).not.toHaveBeenCalled();
    expect(creator).not.toHaveBeenCalled();
  });

  it("rejects mixed correction/replacement intentions and ordinary non-pilot execution", async () => {
    expect(await submitLiveCommunityReport("wind", location(), { ...options, correctionReport: oldReport })).toMatchObject({ reason: "invalid_intent" });
    vi.mocked(isLocalCommunityPilot).mockReturnValue(false);
    expect(await submitLiveCommunityReport("wind", location(), options)).toMatchObject({ reason: "local_pilot_required" });
    expect(pilotOperation).not.toHaveBeenCalled();
  });

  it("deduplicates two overlapping confirmed submissions for the same source", async () => {
    let finishRetirement;
    withdrawer.mockImplementationOnce(() => new Promise((resolve) => { finishRetirement = resolve; }));
    const first = submitLiveCommunityReport("wind", location(), options);
    const second = submitLiveCommunityReport("wind", location(), options);
    finishRetirement(retired);
    const results = await Promise.all([first, second]);
    expect(results[0]).toEqual(results[1]);
    expect(withdrawer).toHaveBeenCalledOnce();
    expect(creator).toHaveBeenCalledOnce();
  });
});
