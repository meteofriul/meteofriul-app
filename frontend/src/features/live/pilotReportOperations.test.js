import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../services/localCommunityPilot", async (importOriginal) => ({
  ...await importOriginal(), isLocalCommunityPilot: vi.fn(() => true),
}));
import { isLocalCommunityPilot } from "../../services/localCommunityPilot";
import { createCommunityReportPreviewMemoryStorage } from "./communityReportPreview";
import { readCommunityPersonalState } from "./communityPersonalState";
import { LIVE_REPORT_UPDATE_OPERATIONS_KEY, updateLiveCommunityReport } from "./liveReportController";
import { isCommunityGroupHiddenFromMap } from "./communityMapVisibility";
import {
  getPilotMutationFeedback, performPilotReportOperation, readPilotPendingOperations,
  readPilotReplacement, reconcilePilotReportOperation,
} from "./pilotReportOperations";

const NOW = Date.parse("2026-09-21T12:00:00Z");
const intent = { acceptedTerms: true, typeId: "rain", istatCode: "093033", selectedPlace: "Pordenone", coords: { lat: 45.9567, lon: 12.6605, accuracyM: 40 }, ageMs: 1000 };
const report = { id: "owned-rain", groupId: "rain-pordenone", typeId: "rain", place: "Pordenone", istatCode: "093033", revision: 1, expiresAt: NOW + 3_600_000, correctionUntil: NOW + 300_000, replacementAvailable: true };
const accepted = { ok: true, report, correction_until: NOW + 300_000, replacement_available: true };
const options = (storage, sender, resolver = vi.fn().mockResolvedValue({ status: "not_found" })) => ({
  storage, sender, resolver, clientIdResolver: () => "persistent-pilot-user",
  operationIdFactory: () => "pilot-operation-123456789",
});

beforeEach(() => { vi.useFakeTimers(); vi.setSystemTime(NOW); vi.mocked(isLocalCommunityPilot).mockReturnValue(true); });
afterEach(() => { vi.useRealTimers(); });

describe("pilot durable operations", () => {
  it.each(["create", "correct"])("retires only unapplied legacy intents, preserving uncertain %s", async (kind) => {
    const storage = createCommunityReportPreviewMemoryStorage();
    const sender = vi.fn().mockRejectedValue(new Error("offline"));
    await performPilotReportOperation(kind, intent, options(storage, sender));
    const pending = readPilotPendingOperations({ storage })[0];
    const resolver = vi.fn().mockResolvedValue({ status: "not_found", rules_version: "community-reports-v3" });
    const result = await reconcilePilotReportOperation(pending, options(storage, sender, resolver));
    expect(Boolean(result.retired)).toBe(kind !== "create");
    expect(readPilotPendingOperations({ storage })).toHaveLength(kind === "create" ? 1 : 0);
  });
  it("recovers a lost accepted create response without posting another contribution", async () => {
    const storage = createCommunityReportPreviewMemoryStorage();
    const sender = vi.fn().mockRejectedValue(new Error("network timeout"));
    const first = await performPilotReportOperation("create", intent, options(storage, sender));
    expect(first.uncertain).toBe(true);
    const pending = readPilotPendingOperations({ storage });
    expect(pending).toHaveLength(1);
    expect(JSON.stringify(pending)).not.toContain("45.9567");
    const resolver = vi.fn().mockResolvedValue({ status: "accepted", result: accepted });
    const recovered = await reconcilePilotReportOperation(pending[0], options(storage, sender, resolver));
    expect(recovered.ok).toBe(true);
    expect(sender).toHaveBeenCalledOnce();
    expect(readPilotPendingOperations({ storage })).toEqual([]);
    expect(readCommunityPersonalState({ storage }).reports[0]).toMatchObject({ reportId: "owned-rain", correctionUntil: report.correctionUntil, replacementAvailable: true });
  });

  it("retries a not-arrived create across a reload with the same intent ID and fresh GPS", async () => {
    const storage = createCommunityReportPreviewMemoryStorage();
    const firstSender = vi.fn().mockRejectedValue(new Error("offline"));
    await performPilotReportOperation("create", intent, options(storage, firstSender));
    const serialized = Object.fromEntries(Array.from({ length: storage.length }, (_, i) => [storage.key(i), storage.getItem(storage.key(i))]));
    const reopenedStorage = createCommunityReportPreviewMemoryStorage(serialized);
    const sender = vi.fn().mockResolvedValue(accepted);
    const recovered = await performPilotReportOperation("create", { ...intent, coords: { ...intent.coords, accuracyM: 12 }, ageMs: 10 }, options(reopenedStorage, sender));
    expect(recovered.ok).toBe(true);
    expect(sender.mock.calls[0][0]).toMatchObject({ operationId: firstSender.mock.calls[0][0].operationId, ageMs: 10, coords: { accuracyM: 12 } });
    expect(readPilotPendingOperations({ storage: reopenedStorage })).toEqual([]);
  });

  it("does not replace uncertain intent or treat lack of network as not_found", async () => {
    const storage = createCommunityReportPreviewMemoryStorage();
    await performPilotReportOperation("create", intent, options(storage, vi.fn().mockRejectedValue(new Error("timeout"))));
    const sender = vi.fn();
    const failed = await performPilotReportOperation("create", { ...intent, typeId: "wind" }, options(storage, sender));
    expect(failed.uncertain).toBe(true);
    expect(sender).not.toHaveBeenCalled();
    const network = await performPilotReportOperation("create", intent, options(storage, sender, vi.fn().mockRejectedValue(new Error("offline"))));
    expect(network.notFound).not.toBe(true);
    expect(sender).not.toHaveBeenCalled();
    expect(readPilotPendingOperations({ storage })[0].typeId).toBe("rain");
  });

  it("keeps the original Comune on retry even after the fresh GPS has moved", async () => {
    const storage = createCommunityReportPreviewMemoryStorage();
    const sender = vi.fn().mockRejectedValueOnce(new Error("timeout")).mockRejectedValueOnce({ status: 409, detail: { code: "community_observation_location_changed" } });
    await performPilotReportOperation("create", intent, options(storage, sender));
    const result = await performPilotReportOperation("create", { ...intent, istatCode: "030129", selectedPlace: "Udine", coords: { lat: 46.07, lon: 13.23, accuracyM: 20 } }, options(storage, sender));
    expect(sender.mock.calls[1][0]).toMatchObject({ operationId: sender.mock.calls[0][0].operationId, istatCode: "093033", selectedPlace: "Pordenone", coords: { lat: 46.07, lon: 13.23 } });
    expect(result.code).toBe("community_observation_location_changed");
    expect(readPilotPendingOperations({ storage })).toEqual([]);
  });

  it("keeps replacement grant across reopening and consumes it only on acknowledged new send", async () => {
    const storage = createCommunityReportPreviewMemoryStorage();
    await performPilotReportOperation("create", intent, options(storage, vi.fn().mockResolvedValue(accepted)));
    const withdrawn = await performPilotReportOperation("replace", { reportId: report.id, expectedRevision: 1 }, options(storage, vi.fn().mockResolvedValue({ ok: true, action: "replacement_ready", report_id: report.id, replacement_token: "replacement-secret" })));
    expect(withdrawn.replacementToken).toBe("replacement-secret");
    expect(readCommunityPersonalState({ storage }).reports).toEqual([]);
    expect(readPilotReplacement({ storage }).token).toBe("replacement-secret");
    const sender = vi.fn().mockRejectedValue(new Error("timeout"));
    await performPilotReportOperation("create", { ...intent, typeId: "wind", replacementToken: "replacement-secret" }, options(storage, sender));
    expect(readPilotReplacement({ storage }).token).toBe("replacement-secret");
    await reconcilePilotReportOperation(readPilotPendingOperations({ storage })[0], options(storage, sender, vi.fn().mockResolvedValue({ status: "accepted", result: { ok: true, report: { ...report, id: "owned-wind", typeId: "wind", replacementAvailable: false }, replacement_available: false } })));
    expect(readPilotReplacement({ storage })).toBeNull();
    expect(readCommunityPersonalState({ storage }).reports[0].replacementAvailable).toBe(false);
  });

  it("clears a pending expired withdrawal only after an authoritative rejection on same-ID retry", async () => {
    const storage = createCommunityReportPreviewMemoryStorage();
    const payload = { reportId: report.id, expectedRevision: 1 };
    const sender = vi.fn().mockRejectedValueOnce(new Error("timeout")).mockRejectedValueOnce({ status: 404, detail: { code: "community_observation_not_active" } });
    await performPilotReportOperation("withdraw", payload, options(storage, sender));
    await performPilotReportOperation("withdraw", payload, options(storage, sender));
    expect(sender.mock.calls[1][0].operationId).toBe(sender.mock.calls[0][0].operationId);
    expect(readPilotPendingOperations({ storage })).toEqual([]);
  });

  it("does not restore a past-expiry receipt after delayed accepted response", async () => {
    const storage = createCommunityReportPreviewMemoryStorage();
    await performPilotReportOperation("create", intent, options(storage, vi.fn().mockRejectedValue(new Error("timeout"))));
    vi.setSystemTime(NOW + 3_700_000);
    const result = await reconcilePilotReportOperation(readPilotPendingOperations({ storage })[0], options(storage, vi.fn(), vi.fn().mockResolvedValue({ status: "accepted", result: accepted })));
    expect(result).toMatchObject({ ok: true, expired: true });
    expect(readCommunityPersonalState({ storage }).reports).toEqual([]);
  });

  it("accepts a compact aged receipt without sending again or recreating a report", async () => {
    const storage = createCommunityReportPreviewMemoryStorage();
    await performPilotReportOperation("create", intent, options(storage, vi.fn().mockRejectedValue(new Error("timeout"))));
    const pending = readPilotPendingOperations({ storage })[0];
    const result = await reconcilePilotReportOperation(pending, options(storage, vi.fn(), vi.fn().mockResolvedValue({ status: "accepted", result: { ok: true, reconciled_only: true, operation_id: pending.operationId, report_id: report.id } })));
    expect(result).toMatchObject({ ok: true, reconciledOnly: true });
    expect(readPilotPendingOperations({ storage })).toEqual([]);
    expect(readCommunityPersonalState({ storage }).reports).toEqual([]);
  });

  it("preserves contribution count and expiry when acknowledging a correction", async () => {
    const storage = createCommunityReportPreviewMemoryStorage();
    await performPilotReportOperation("create", intent, options(storage, vi.fn().mockResolvedValue(accepted)));
    const corrected = { ...report, typeId: "wind", groupId: "wind-pordenone", revision: 2 };
    await performPilotReportOperation("correct", { ...intent, typeId: "wind", reportId: report.id, expectedRevision: 1 }, options(storage, vi.fn().mockResolvedValue({ ok: true, action: "corrected", report: corrected, revision: 2 })));
    const personal = readCommunityPersonalState({ storage });
    expect(personal.dailyContributions.count).toBe(1);
    expect(personal.reports).toHaveLength(1);
    expect(personal.reports[0]).toMatchObject({ reportId: report.id, typeId: "wind", expiresAt: report.expiresAt });
  });

  it("keeps ordinary app execution gated off", async () => {
    vi.mocked(isLocalCommunityPilot).mockReturnValue(false);
    const sender = vi.fn();
    expect(await performPilotReportOperation("create", intent, options(createCommunityReportPreviewMemoryStorage(), sender))).toMatchObject({ ok: false, reason: "local_pilot_required" });
    expect(sender).not.toHaveBeenCalled();
  });

  it("blocks a different mutation while an update result is unresolved and vice versa", async () => {
    const storage = createCommunityReportPreviewMemoryStorage();
    storage.setItem(LIVE_REPORT_UPDATE_OPERATIONS_KEY, JSON.stringify({ [report.id]: { operationId: "pending-update-12345678", createdAt: NOW, expectedRevision: 1 } }));
    const sender = vi.fn();
    const blocked = await performPilotReportOperation("create", intent, options(storage, sender));
    expect(blocked.reason).toBe("pending_operation");
    expect(sender).not.toHaveBeenCalled();
    storage.removeItem(LIVE_REPORT_UPDATE_OPERATIONS_KEY);
    await performPilotReportOperation("create", intent, options(storage, vi.fn().mockRejectedValue(new Error("offline"))));
    const updater = vi.fn();
    const update = await updateLiveCommunityReport(report, { coords: intent.coords, locatedAt: NOW }, { acceptedTerms: true, operationStorage: storage, reportUpdater: updater });
    expect(update.reason).toBe("pending_operation");
    expect(updater).not.toHaveBeenCalled();
  });

  it("does not transfer a previous phenomenon denial to a new observation", () => {
    const entry = { groupId: "wind-pordenone", lineageGroupIds: ["rain-pordenone"], expiresAt: NOW + 3_600_000, confirmations: { no: 1 } };
    expect(isCommunityGroupHiddenFromMap(entry, { votes: [{ groupId: "rain-pordenone", vote: "no" }] })).toBe(false);
    expect(isCommunityGroupHiddenFromMap(entry, { votes: [] })).toBe(false);
    vi.mocked(isLocalCommunityPilot).mockReturnValue(false);
    expect(isCommunityGroupHiddenFromMap(entry, { votes: [{ groupId: "rain-pordenone", vote: "no" }] })).toBe(false);
  });

  it("explains rolling quotas, duplicate and correction deadline concretely", () => {
    expect(getPilotMutationFeedback({ code: "community_hourly_limit", retryAfterSeconds: 90 })).toContain("ultimi 60 minuti");
    expect(getPilotMutationFeedback({ code: "community_daily_limit" })).toContain("ultime 24 ore");
    expect(getPilotMutationFeedback({ code: "community_observation_already_recent" })).toContain("questo Comune");
    expect(getPilotMutationFeedback({ code: "community_correction_window_closed" })).toContain("5 minuti");
  });
});
