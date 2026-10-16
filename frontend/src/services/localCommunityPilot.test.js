import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as apiConfig from "./apiConfig";
import { getLocalCommunityReadScope, isLocalCommunityPilot } from "./localCommunityPilot";
import {
  deleteCommunityReport,
  fetchCommunityReports,
  postCommunityReport,
  updateLocalCommunityReport,
  withdrawLocalCommunityReport,
} from "./liveApi";
import { loadLiveData, readInitialLiveData } from "../features/live/liveDataController";
import {
  locateLiveCommunityReport,
  LIVE_REPORT_UPDATE_OPERATIONS_KEY,
  readPendingLiveCommunityReportUpdates,
  reconcilePendingLiveCommunityReportUpdate,
  updateLiveCommunityReport,
  withdrawLiveCommunityReport,
} from "../features/live/liveReportController";
import { resolveProductScope } from "../domain/scope/productScope";

const pordenone = { istatCode: "093033", city: "Pordenone", regionCode: "IT-36" };
const urbino = { istatCode: "041067", city: "Urbino", regionCode: "IT-57" };
function activate() {
  vi.stubEnv("DEV", true);
  vi.stubEnv("MODE", "local-pilot");
  vi.stubEnv("VITE_ANDROID_LOCAL_WEATHER_PILOT", "0");
  vi.stubEnv("VITE_LOCAL_WEATHER_PILOT", "1");
  vi.stubEnv("VITE_LOCAL_COMMUNITY_PILOT_ENABLED", "1");
  vi.stubEnv("VITE_LOCAL_COMMUNITY_PILOT_API_BASE", "/__local-community/api");
  vi.stubGlobal("location", { hostname: "127.0.0.1" });
  vi.spyOn(apiConfig, "isAndroidCapacitorRuntime").mockReturnValue(false);
}
function storage() {
  const values = new Map();
  return {
    get length() { return values.size; },
    key: (index) => [...values.keys()][index],
    getItem: (key) => values.get(key) || null,
    setItem: (key, value) => values.set(key, value),
    removeItem: (key) => values.delete(key),
    values,
  };
}
const payload = (place) => ({ reports: [{ place }], map_groups: [], source: { storage: "memory" } });
beforeEach(activate);
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllEnvs(); vi.unstubAllGlobals(); });

describe("isolated national community pilot", () => {
  it("requires the exact mode, loopback and owned endpoint", () => {
    expect(isLocalCommunityPilot()).toBe(true);
    for (const mode of ["production", "android", "cloudflare", "development", "local-pilot-cloud"]) {
      vi.stubEnv("MODE", mode);
      expect(isLocalCommunityPilot()).toBe(false);
    }
    vi.stubEnv("MODE", "local-pilot");
    vi.stubEnv("VITE_LOCAL_COMMUNITY_PILOT_API_BASE", "https://production.invalid/api");
    expect(isLocalCommunityPilot()).toBe(false);
    vi.stubEnv("VITE_LOCAL_COMMUNITY_PILOT_API_BASE", "/__local-community/api");
    vi.stubGlobal("location", { hostname: "meteofriul.app" });
    expect(isLocalCommunityPilot()).toBe(false);
  });

  it("reads only the requested municipality and never retries on the shared API", async () => {
    const fetchImpl = vi.fn().mockRejectedValue(new Error("local server offline"));
    await expect(fetchCommunityReports({ communityLocation: urbino, fetchImpl })).rejects.toThrow("offline");
    expect(fetchImpl).toHaveBeenCalledOnce();
    expect(fetchImpl.mock.calls[0][0]).toBe("/__local-community/api/community/reports?istat_code=041067&radius_km=30");
    expect(() => getLocalCommunityReadScope({ city: "Roma" })).toThrow();
  });

  it("keeps local writes off App Check and all ordinary writes protected", async () => {
    const fetchImpl = vi.fn(async () => ({ ok: true, json: async () => ({ ok: true }) }));
    const appCheckTokenProvider = vi.fn(async () => "real-token");
    const command = { selectedPlace: "Urbino", istatCode: "041067", ageMs: 10, coords: { lat: 43.726, lon: 12.636, accuracyM: 20 } };
    await postCommunityReport(command, { fetchImpl, appCheckTokenProvider });
    expect(appCheckTokenProvider).not.toHaveBeenCalled();
    expect(fetchImpl.mock.calls[0][0]).toBe("/__local-community/api/community/reports");
    expect(fetchImpl.mock.calls[0][1].headers["X-Meteo-Pilot-Community"]).toBe("local-only");
    expect(JSON.parse(fetchImpl.mock.calls[0][1].body).istat_code).toBe("041067");
    vi.stubEnv("VITE_LOCAL_COMMUNITY_PILOT_ENABLED", "0");
    await postCommunityReport(command, { fetchImpl, appCheckTokenProvider });
    expect(appCheckTokenProvider).toHaveBeenCalledOnce();
    expect(fetchImpl.mock.calls[1][0]).toBe(`${apiConfig.API_BASE}/community/reports`);
    expect(fetchImpl.mock.calls[1][1].headers["X-Firebase-AppCheck"]).toBe("real-token");
  });

  it("keeps quick undo and persistent withdrawal as explicit separate pilot commands", async () => {
    const fetchImpl = vi.fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ action: "undone", ok: true, report_id: "report-1" }),
        headers: { get: () => null },
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({
          action: "withdrawn",
          cooldown_until: 1234,
          ok: true,
          report_id: "report-1",
        }),
        headers: { get: () => null },
      });

    await deleteCommunityReport({ clientId: "client-1", reportId: "report-1" }, { fetchImpl });
    await withdrawLocalCommunityReport({ clientId: "client-1", reportId: "report-1" }, { fetchImpl });

    expect(JSON.parse(fetchImpl.mock.calls[0][1].body)).toEqual({
      action: "undo",
      client_id: "client-1",
    });
    expect(JSON.parse(fetchImpl.mock.calls[1][1].body)).toEqual({
      action: "withdraw",
      client_id: "client-1",
    });
    expect(fetchImpl.mock.calls[1][0]).toBe("/__local-community/api/community/reports/report-1");
  });

  it("coalesces duplicate withdrawals, validates the acknowledgement and clears failed requests", async () => {
    let finish;
    const reportWithdrawer = vi.fn(() => new Promise((resolve) => { finish = resolve; }));
    const options = { clientIdResolver: () => "client-1", reportWithdrawer };
    const first = withdrawLiveCommunityReport("report-1", options);
    const duplicate = withdrawLiveCommunityReport("report-1", options);

    expect(duplicate).toBe(first);
    await vi.waitFor(() => expect(reportWithdrawer).toHaveBeenCalledOnce());
    finish({ action: "withdrawn", cooldown_until: 1234, ok: true, report_id: "report-1" });
    await expect(first).resolves.toEqual({
      action: "withdrawn",
      cooldownUntil: 1234,
      ok: true,
      reportId: "report-1",
    });

    const invalid = vi.fn().mockResolvedValue({
      action: "undone",
      ok: true,
      report_id: "report-1",
    });
    await expect(withdrawLiveCommunityReport("report-1", {
      clientIdResolver: () => "client-1",
      reportWithdrawer: invalid,
    })).resolves.toMatchObject({ ok: false, reason: "invalid_response" });

    const retryable = vi.fn()
      .mockImplementationOnce(() => { throw new Error("temporary"); })
      .mockResolvedValueOnce({ action: "withdrawn", ok: true, report_id: "report-2" });
    const retryOptions = { clientIdResolver: () => "client-1", reportWithdrawer: retryable };
    await expect(withdrawLiveCommunityReport("report-2", retryOptions))
      .resolves.toMatchObject({ ok: false, reason: "request_failed" });
    await expect(withdrawLiveCommunityReport("report-2", retryOptions))
      .resolves.toMatchObject({ ok: true, reportId: "report-2" });
    expect(retryable).toHaveBeenCalledTimes(2);
  });

  it("sends the pilot update contract without changing type or municipality", async () => {
    const fetchImpl = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ({
        action: "updated",
        ok: true,
        report: { id: "report-1", revision: 2 },
        revision: 2,
      }),
      headers: { get: () => null },
    }));

    await updateLocalCommunityReport({
      acceptedTerms: true,
      ageMs: 25,
      clientId: "client-1",
      coords: { accuracyM: 18, lat: 45.9567, lon: 12.6605 },
      expectedRevision: 1,
      operationId: "operation-1",
      policyVersion: "community-guidelines-v2",
      reportId: "report-1",
    }, { fetchImpl });

    expect(fetchImpl).toHaveBeenCalledOnce();
    expect(fetchImpl.mock.calls[0][0]).toBe("/__local-community/api/community/reports/report-1");
    expect(fetchImpl.mock.calls[0][1].method).toBe("PATCH");
    expect(JSON.parse(fetchImpl.mock.calls[0][1].body)).toEqual({
      accepted_terms: true,
      accuracy_m: 18,
      age_ms: 25,
      client_id: "client-1",
      expected_revision: 1,
      lat: 45.9567,
      lon: 12.6605,
      operation_id: "operation-1",
      policy_version: "community-guidelines-v2",
    });
  });

  it("persists one update operation across a network failure and clears it after replay", async () => {
    const operationStorage = storage();
    const operationIdFactory = vi.fn(() => "stable-operation");
    const reportUpdater = vi.fn()
      .mockRejectedValueOnce(new Error("timeout"))
      .mockResolvedValueOnce({
        action: "updated",
        idempotent_replay: true,
        ok: true,
        report: { id: "report-retry", revision: 2 },
        revision: 2,
      });
    const options = {
      acceptedTerms: true,
      clientIdResolver: () => "client-1",
      now: () => 2_000,
      operationIdFactory,
      operationStorage,
      reportUpdater,
    };
    const firstLocation = {
      coords: { accuracyM: 20, lat: 45.95, lon: 12.66 },
      istatCode: "093033",
      locatedAt: 1_990,
    };
    await expect(updateLiveCommunityReport(
      { reportId: "report-retry", revision: 1 },
      firstLocation,
      options,
    )).resolves.toMatchObject({ ok: false, operationId: "stable-operation", reason: "request_failed" });
    expect(JSON.parse(operationStorage.getItem(LIVE_REPORT_UPDATE_OPERATIONS_KEY)))
      .toEqual({
        "report-retry": { createdAt: 2_000, expectedRevision: 1, operationId: "stable-operation" },
      });

    await expect(updateLiveCommunityReport(
      { reportId: "report-retry", revision: 1 },
      { ...firstLocation, coords: { ...firstLocation.coords, lat: 45.951 }, locatedAt: 1_995 },
      options,
    )).resolves.toMatchObject({
      idempotentReplay: true,
      ok: true,
      operationId: "stable-operation",
      revision: 2,
    });
    expect(operationIdFactory).toHaveBeenCalledOnce();
    expect(reportUpdater.mock.calls.map(([command]) => command.operationId))
      .toEqual(["stable-operation", "stable-operation"]);
    expect(JSON.parse(operationStorage.getItem(LIVE_REPORT_UPDATE_OPERATIONS_KEY))).toEqual({});
  });

  it("rejects zero GPS accuracy before attempting an observation update", async () => {
    const reportUpdater = vi.fn();

    await expect(updateLiveCommunityReport(
      { reportId: "report-zero-accuracy", revision: 1 },
      {
        coords: { accuracyM: 0, lat: 45.95, lon: 12.66 },
        locatedAt: 1_995,
      },
      {
        acceptedTerms: true,
        clientIdResolver: () => "client-1",
        now: () => 2_000,
        reportUpdater,
      },
    )).resolves.toEqual({ ok: false, reason: "stale_or_imprecise" });
    expect(reportUpdater).not.toHaveBeenCalled();
  });

  it("reconciles a response-lost update after reopening without submitting again", async () => {
    const operationStorage = storage();
    const reportUpdater = vi.fn().mockRejectedValue(new Error("response lost"));
    const firstNow = 1_000;

    await expect(updateLiveCommunityReport(
      { reportId: "report-reopen", revision: 1 },
      {
        coords: { accuracyM: 20, lat: 45.95, lon: 12.66 },
        locatedAt: firstNow - 5,
      },
      {
        acceptedTerms: true,
        clientIdResolver: () => "client-1",
        now: () => firstNow,
        operationIdFactory: () => "operation-reopen",
        operationStorage,
        reportUpdater,
      },
    )).resolves.toMatchObject({ ok: false, reason: "request_failed" });

    const reopenedAt = firstNow + 61 * 60 * 1_000;
    expect(readPendingLiveCommunityReportUpdates({ now: reopenedAt, operationStorage }))
      .toEqual([{
        createdAt: firstNow,
        expectedRevision: 1,
        operationId: "operation-reopen",
        reportId: "report-reopen",
      }]);
    expect(reconcilePendingLiveCommunityReportUpdate(
      {
        expiresAt: reopenedAt + 60 * 60 * 1_000,
        groupId: "group-rain",
        id: "report-reopen",
        revision: 1,
      },
      { now: reopenedAt, operationStorage },
    )).toMatchObject({ ok: false, reason: "revision_not_advanced" });
    expect(reconcilePendingLiveCommunityReportUpdate(
      {
        expiresAt: reopenedAt + 60 * 60 * 1_000,
        groupId: "group-rain",
        id: "report-other",
        revision: 2,
      },
      { now: reopenedAt, operationStorage },
    )).toMatchObject({ ok: false, reason: "no_pending_update" });
    expect(reconcilePendingLiveCommunityReportUpdate(
      {
        expiresAt: reopenedAt,
        groupId: "group-rain",
        id: "report-reopen",
        revision: 2,
      },
      { now: reopenedAt, operationStorage },
    )).toMatchObject({ ok: false, reason: "invalid_report" });
    expect(readPendingLiveCommunityReportUpdates({ now: reopenedAt, operationStorage }))
      .toHaveLength(1);

    const acceptedReport = {
      expiresAt: reopenedAt + 60 * 60 * 1_000,
      groupId: "group-rain",
      id: "report-reopen",
      revision: 2,
      typeId: "rain",
    };
    expect(reconcilePendingLiveCommunityReportUpdate(
      acceptedReport,
      { now: reopenedAt, operationStorage },
    )).toMatchObject({
      action: "reconciled",
      expectedRevision: 1,
      ok: true,
      operationId: "operation-reopen",
      report: acceptedReport,
      revision: 2,
    });
    expect(reportUpdater).toHaveBeenCalledOnce();
    expect(readPendingLiveCommunityReportUpdates({ now: reopenedAt, operationStorage })).toEqual([]);
  });

  it("prunes expired update operations and bounds persisted recovery state", () => {
    const operationStorage = storage();
    const now = 100_000_000;
    const operations = Object.fromEntries([
      ...Array.from({ length: 35 }, (_, index) => [
        `report-${index}`,
        {
          createdAt: now - index,
          expectedRevision: 1,
          operationId: `operation-${index}`,
        },
      ]),
      ["report-expired", {
        createdAt: now - (24 * 60 * 60 * 1_000),
        expectedRevision: 1,
        operationId: "operation-expired",
      }],
    ]);
    operationStorage.setItem(LIVE_REPORT_UPDATE_OPERATIONS_KEY, JSON.stringify(operations));

    const pending = readPendingLiveCommunityReportUpdates({ now, operationStorage });
    expect(pending).toHaveLength(32);
    expect(pending[0].reportId).toBe("report-0");
    expect(pending.some((entry) => entry.reportId === "report-expired")).toBe(false);
    expect(Object.keys(JSON.parse(
      operationStorage.getItem(LIVE_REPORT_UPDATE_OPERATIONS_KEY),
    ))).toHaveLength(32);
  });

  it("opens expiry recovery only for the exact server code and clears authoritative conflicts", async () => {
    const operationStorage = storage();
    const location = {
      coords: { accuracyM: 20, lat: 45.95, lon: 12.66 },
      istatCode: "093033",
      locatedAt: 1_990,
    };
    const run = (reportId, detail, status = 409) => updateLiveCommunityReport(
      { reportId, revision: 1 },
      location,
      {
        acceptedTerms: true,
        clientIdResolver: () => "client-1",
        now: () => 2_000,
        operationIdFactory: () => `operation-${reportId}`,
        operationStorage,
        reportUpdater: async () => {
          const error = new Error("rejected");
          error.detail = detail;
          error.status = status;
          throw error;
        },
      },
    );

    await expect(run("expired", {
      code: "community_observation_expired",
      state: {
        expires_at: 1_999,
        report_id: "expired",
        revision: 1,
        server_time: 2_000,
        status: "expired",
      },
    })).resolves.toMatchObject({ reason: "observation_expired", reportId: "expired" });
    await expect(run("mismatched-expiry", {
      code: "community_observation_expired",
      state: {
        expires_at: 1_999,
        report_id: "another-report",
        revision: 1,
        server_time: 2_000,
        status: "expired",
      },
    })).resolves.toMatchObject({ reason: "request_failed", reportId: "mismatched-expiry" });
    await expect(run("malformed-expiry", {
      code: "community_observation_expired",
      state: { report_id: "malformed-expiry", status: "expired" },
    })).resolves.toMatchObject({ reason: "request_failed", reportId: "malformed-expiry" });
    await expect(run("plain-409", { message: "generic" }))
      .resolves.toMatchObject({ reason: "request_failed", reportId: "plain-409" });
    await expect(run("conflict", {
      code: "community_observation_revision_conflict",
      state: {
        expires_at: 3_000,
        report_id: "conflict",
        revision: 2,
        server_time: 2_000,
        status: "recent",
      },
    })).resolves.toMatchObject({
      reason: "observation_conflict",
      reportId: "conflict",
      serverState: { report_id: "conflict", revision: 2, status: "recent" },
    });
    await expect(run("malformed-conflict", {
      code: "community_observation_revision_conflict",
      state: {
        expires_at: 3_000,
        report_id: "another-report",
        revision: 2,
        server_time: 2_000,
        status: "recent",
      },
    })).resolves.toMatchObject({ reason: "request_failed", reportId: "malformed-conflict" });
    await expect(run("idempotency-conflict", { code: "community_idempotency_conflict" }))
      .resolves.toMatchObject({
        reason: "observation_conflict",
        reportId: "idempotency-conflict",
        serverState: null,
      });
    for (const code of [
      "community_observation_not_active",
      "community_observation_not_updateable",
      "community_group_hidden",
      "community_observation_owner_mismatch",
    ]) {
      const reportId = `terminal-${code}`;
      await expect(run(reportId, { code, message: "Operazione non disponibile." }, 403))
        .resolves.toMatchObject({ code, reason: "observation_rejected", reportId });
    }

    const pending = JSON.parse(operationStorage.getItem(LIVE_REPORT_UPDATE_OPERATIONS_KEY));
    expect(pending).toEqual({
      "plain-409": {
        createdAt: 2_000,
        expectedRevision: 1,
        operationId: "operation-plain-409",
      },
      "mismatched-expiry": {
        createdAt: 2_000,
        expectedRevision: 1,
        operationId: "operation-mismatched-expiry",
      },
      "malformed-expiry": {
        createdAt: 2_000,
        expectedRevision: 1,
        operationId: "operation-malformed-expiry",
      },
      "malformed-conflict": {
        createdAt: 2_000,
        expectedRevision: 1,
        operationId: "operation-malformed-conflict",
      },
    });
  });

  it("separates pending requests and caches while switching cities", async () => {
    const cache = storage();
    let finishPordenone;
    let finishUrbino;
    const fetcher = vi.fn(({ communityLocation }) => new Promise((resolve) => {
      if (communityLocation.istatCode === "093033") finishPordenone = resolve;
      else finishUrbino = resolve;
    }));
    const first = loadLiveData({ communityLocation: pordenone, communityFetcher: fetcher, webcamsEnabled: false, storage: cache });
    const next = loadLiveData({ communityLocation: urbino, communityFetcher: fetcher, webcamsEnabled: false, storage: cache });
    await vi.waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));
    finishUrbino(payload("Urbino"));
    expect((await next).community.payload.reports[0].place).toBe("Urbino");
    finishPordenone(payload("Pordenone"));
    await first;
    expect(readInitialLiveData({ communityLocation: urbino, webcamsEnabled: false, storage: cache }).community.payload.reports[0].place).toBe("Urbino");
    expect(cache.values.has("liveCommunityReports:v1")).toBe(false);
    expect(cache.values.size).toBe(2);
  });

  it("uses fresh GPS for national submission regardless of the manually selected weather city", async () => {
    const coords = { lat: 43.726, lon: 12.636, accuracyM: 20 };
    const nationalResolver = vi.fn(async () => ({ ok: true, istatCode: "041067", selectedPlace: "Urbino", detectedPlace: "Urbino", nearbyPlaces: [{ place: "Urbino" }] }));
    const result = await locateLiveCommunityReport({ coordinateResolver: async () => ({ ok: true, coords, ageMs: 5 }), nationalResolver });
    expect(result).toMatchObject({ ok: true, istatCode: "041067", coords });
    expect(nationalResolver).toHaveBeenCalledWith({ coords, ageMs: 5 });
    const rejected = await locateLiveCommunityReport({ coordinateResolver: async () => ({ ok: true, coords: { ...coords, accuracyM: 1500 }, ageMs: 0 }), nationalResolver });
    expect(rejected.ok).toBe(false);
    const zeroAccuracy = await locateLiveCommunityReport({ coordinateResolver: async () => ({ ok: true, coords: { ...coords, accuracyM: 0 }, ageMs: 0 }), nationalResolver });
    expect(zeroAccuracy).toMatchObject({ ok: false, reason: "stale_or_imprecise" });
    expect(nationalResolver).toHaveBeenCalledOnce();
  });

  it("enables Italian writes only with pilot capability and keeps foreign locations closed", () => {
    expect(resolveProductScope(urbino).community.write).toBe(false);
    expect(resolveProductScope(urbino, { nationalCommunityEnabled: true }).community.write).toBe(true);
    expect(resolveProductScope({ countryCode: "SI" }, { nationalCommunityEnabled: true }).community.write).toBe(false);
  });
});
