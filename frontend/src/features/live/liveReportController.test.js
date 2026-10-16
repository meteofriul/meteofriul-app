import { describe, expect, it, vi } from "vitest";

import {
  confirmLiveCommunityReport,
  flagLiveCommunityReport,
  LIVE_REPORT_SUBMIT_MAX_AGE_MS,
  locateLiveCommunityReport,
  submitLiveCommunityReport,
  undoLiveCommunityReport,
} from "./liveReportController";
import { DEVICE_GEOLOCATION_OPTIONS } from "../../services/deviceLocation";
import { COMMUNITY_GUIDELINES_POLICY_VERSION } from "./liveReportPolicy";

describe("live report controller", () => {
  it("resolves a fresh GPS position independently from the selected app city", async () => {
    const coordinateResolver = vi.fn().mockResolvedValue({
      coords: { accuracyM: 80, lat: 45.9567, lon: 12.6605 },
      ageMs: 1_000,
      ok: true,
      source: "android_current_location",
    });

    const result = await locateLiveCommunityReport({
      coordinateResolver,
      locations: [
        { place: "Pordenone", lat: 45.9569, lon: 12.6605 },
        { place: "Cordenons", lat: 45.9836, lon: 12.7004 },
      ],
    });

    expect(coordinateResolver).toHaveBeenCalledWith({
      maxAccuracyM: 1000,
      maxAgeMs: 120000,
    });
    expect(result).toMatchObject({
      coords: { accuracyM: 80, lat: 45.9567, lon: 12.6605 },
      detectedPlace: "Pordenone",
      ok: true,
      selectedPlace: "Pordenone",
      source: "android_current_location",
    });
    expect(result.nearbyPlaces.map((item) => item.place)).toEqual([
      "Pordenone",
      "Cordenons",
    ]);
  });

  it("requires a current non-cached fix when verifying at submit", async () => {
    const coordinateResolver = vi.fn().mockResolvedValue({
      coords: { accuracyM: 25, lat: 45.9567, lon: 12.6605 },
      ageMs: 500,
      ok: true,
      source: "android_current_location",
    });

    await expect(locateLiveCommunityReport({
      coordinateResolver,
      locations: [{ place: "Pordenone", lat: 45.9569, lon: 12.6605 }],
      requireCurrent: true,
    })).resolves.toMatchObject({ ok: true, selectedPlace: "Pordenone" });
    expect(coordinateResolver).toHaveBeenCalledExactlyOnceWith({
      maxAccuracyM: 1000,
      maxAgeMs: LIVE_REPORT_SUBMIT_MAX_AGE_MS,
      options: DEVICE_GEOLOCATION_OPTIONS,
      requireCurrent: true,
    });
  });

  it("posts original GPS coordinates and a manually corrected nearby zone", async () => {
    const reportPoster = vi.fn().mockResolvedValue({ report: { id: "report-1" } });
    const location = {
      coords: { lat: 45.9567, lon: 12.6605 },
      nearbyPlaces: [{ place: "Pordenone" }, { place: "Cordenons" }],
      selectedPlace: "Cordenons",
      source: "android_current_location",
    };

    const result = await submitLiveCommunityReport("rain", location, {
      acceptedTerms: true,
      clientIdResolver: () => "client-1",
      policyVersion: COMMUNITY_GUIDELINES_POLICY_VERSION,
      reportPoster,
    });

    expect(reportPoster).toHaveBeenCalledWith({
      acceptedTerms: true,
      clientId: "client-1",
      coords: { lat: 45.9567, lon: 12.6605 },
      policyVersion: COMMUNITY_GUIDELINES_POLICY_VERSION,
      selectedPlace: "Cordenons",
      typeId: "rain",
    });
    expect(result).toEqual({
      cooldownUntil: null,
      ok: true,
      report: { id: "report-1" },
      source: "android_current_location",
      undoUntil: null,
    });
  });

  it("forwards the current cosmetic identity without replacing technical ownership", async () => {
    const reportPoster = vi.fn().mockResolvedValue({ report: { id: "report-identity" } });
    const identity = {
      alias: "Acuile di Pordenon",
      avatar: { angle: 90, paletteId: "cobalt", patternId: "orbit", variant: 1 },
      subjectId: "acuile",
      version: 1,
    };

    await submitLiveCommunityReport("rain", {
      coords: { lat: 45.9567, lon: 12.6605 },
      nearbyPlaces: [{ place: "Pordenone" }],
      selectedPlace: "Pordenone",
    }, {
      acceptedTerms: true,
      clientIdResolver: () => "private-owner",
      identity,
      reportPoster,
    });

    expect(reportPoster).toHaveBeenCalledWith(expect.objectContaining({
      clientId: "private-owner",
      identity,
    }));
  });

  it("returns a controlled result when GPS permission is denied", async () => {
    await expect(locateLiveCommunityReport({
      coordinateResolver: vi.fn().mockResolvedValue({ ok: false, reason: "permission_denied" }),
    })).resolves.toMatchObject({ ok: false, reason: "permission_denied" });
  });

  it("distinguishes pilot location verification failures from update request failures", async () => {
    const coordinateResolver = vi.fn().mockResolvedValue({
      coords: { accuracyM: 50, lat: 45.9567, lon: 12.6605 },
      ageMs: 1_000,
      ok: true,
      source: "android_current_location",
    });

    await expect(locateLiveCommunityReport({
      coordinateResolver,
      nationalResolver: vi.fn().mockRejectedValue(new Error("resolver offline")),
      pilotEnabled: true,
    })).resolves.toEqual({
      error: "resolver offline",
      ok: false,
      reason: "location_verification_failed",
    });
    expect(coordinateResolver).toHaveBeenCalledWith({
      maxAccuracyM: 500,
      maxAgeMs: 120000,
    });
  });

  it.each([
    [null, "missing"],
    [-1, "negative"],
    [1001, "over the 1000 m limit"],
  ])("rejects report GPS accuracy %s when it is %s", async (accuracyM) => {
    await expect(locateLiveCommunityReport({
      coordinateResolver: vi.fn().mockResolvedValue({
        coords: { accuracyM, lat: 45.9567, lon: 12.6605 },
        ageMs: 1_000,
        ok: true,
        source: "browser_geolocation",
      }),
    })).resolves.toMatchObject({ ok: false, reason: "stale_or_imprecise" });
  });

  it.each([
    ["browser_geolocation", 120_001],
    ["android_last_location", 120_001],
  ])("rejects stale %s report coordinates", async (source, ageMs) => {
    await expect(locateLiveCommunityReport({
      coordinateResolver: vi.fn().mockResolvedValue({
        coords: { accuracyM: 50, lat: 45.9567, lon: 12.6605 },
        ageMs,
        ok: true,
        source,
      }),
    })).resolves.toMatchObject({ ok: false, reason: "stale_or_imprecise", source });
  });

  it("returns endpoint failures as a controlled result", async () => {
    await expect(submitLiveCommunityReport("wind", {
      coords: { lat: 45.9567, lon: 12.6605 },
      nearbyPlaces: [{ place: "Pordenone" }],
      selectedPlace: "Pordenone",
    }, {
      acceptedTerms: true,
      reportPoster: vi.fn().mockRejectedValue(new Error("cooldown")),
    })).resolves.toEqual({
      error: "cooldown",
      ok: false,
      reason: "request_failed",
    });
  });

  it("preserves structured cooldown failures for the UI", async () => {
    const error = Object.assign(new Error("Puoi inviare una nuova segnalazione più tardi."), {
      detail: {
        message: "Puoi inviare una nuova segnalazione più tardi.",
        retry_after_seconds: 119,
      },
      retryAfterSeconds: 119,
      status: 429,
    });

    await expect(submitLiveCommunityReport("wind", {
      coords: { lat: 45.9567, lon: 12.6605 },
      nearbyPlaces: [{ place: "Pordenone" }],
      selectedPlace: "Pordenone",
    }, {
      acceptedTerms: true,
      reportPoster: vi.fn().mockRejectedValue(error),
    })).resolves.toEqual({
      detail: error.detail,
      error: error.message,
      ok: false,
      reason: "cooldown",
      retryAfterSeconds: 119,
      status: 429,
    });
  });

  it("preserves the backend region rollout denial as a stable reason", async () => {
    const error = Object.assign(new Error("Scrittura non attiva"), {
      detail: {
        code: "community_region_not_enabled",
        message: "Le segnalazioni partecipative non sono ancora attive in questa regione.",
      },
      status: 403,
    });

    await expect(submitLiveCommunityReport("wind", {
      coords: { lat: 41.9028, lon: 12.4964 },
      nearbyPlaces: [{ place: "Roma" }],
      selectedPlace: "Roma",
    }, {
      acceptedTerms: true,
      reportPoster: vi.fn().mockRejectedValue(error),
    })).resolves.toMatchObject({
      detail: error.detail,
      ok: false,
      reason: "community_region_not_enabled",
      status: 403,
    });
  });

  it("rejects a manual place outside the GPS-compatible list before the endpoint", async () => {
    const reportPoster = vi.fn();

    await expect(submitLiveCommunityReport("storm", {
      coords: { lat: 45.9567, lon: 12.6605 },
      nearbyPlaces: [{ place: "Pordenone" }],
      selectedPlace: "Trieste",
    }, {
      acceptedTerms: true,
      reportPoster,
    })).resolves.toMatchObject({ ok: false, reason: "invalid_place" });
    expect(reportPoster).not.toHaveBeenCalled();
  });

  it("does not post when current community terms were not accepted", async () => {
    const reportPoster = vi.fn();

    await expect(submitLiveCommunityReport("rain", {
      coords: { lat: 45.9567, lon: 12.6605 },
      nearbyPlaces: [{ place: "Pordenone" }],
      selectedPlace: "Pordenone",
    }, { reportPoster })).resolves.toEqual({ ok: false, reason: "terms_required" });
    expect(reportPoster).not.toHaveBeenCalled();
  });

  it("confirms an active map group with the anonymous community client", async () => {
    const confirmationPoster = vi.fn().mockResolvedValue({
      confirmations: { no: 0, yes: 2 },
      group: { id: "group-rain:pordenone:1" },
      vote: "yes",
    });

    await expect(confirmLiveCommunityReport("group-rain:pordenone:1", "yes", {
      acceptedTerms: true,
      clientIdResolver: () => "client-1",
      confirmationPoster,
      policyVersion: COMMUNITY_GUIDELINES_POLICY_VERSION,
    })).resolves.toMatchObject({
      confirmations: { no: 0, yes: 2 },
      ok: true,
      vote: "yes",
    });
    expect(confirmationPoster).toHaveBeenCalledWith({
      acceptedTerms: true,
      clientId: "client-1",
      groupId: "group-rain:pordenone:1",
      policyVersion: COMMUNITY_GUIDELINES_POLICY_VERSION,
      vote: "yes",
    });
  });

  it("posts a denial only with the verified persistent installation identity", async () => {
    const clientIdResolver = vi.fn(() => "session-only-client");
    const persistentClientIdResolver = vi.fn(() => "durable-installation-1");
    const confirmationPoster = vi.fn().mockResolvedValue({
      confirmations: { no: 1, yes: 0 },
      group: { id: "group-rain:pordenone:1" },
      vote: "no",
    });

    await expect(confirmLiveCommunityReport("group-rain:pordenone:1", "no", {
      acceptedTerms: true,
      clientIdResolver,
      confirmationPoster,
      persistentClientIdResolver,
      policyVersion: COMMUNITY_GUIDELINES_POLICY_VERSION,
    })).resolves.toMatchObject({
      confirmations: { no: 1, yes: 0 },
      ok: true,
      vote: "no",
    });
    expect(clientIdResolver).not.toHaveBeenCalled();
    expect(persistentClientIdResolver).toHaveBeenCalledOnce();
    expect(confirmationPoster).toHaveBeenCalledWith({
      acceptedTerms: true,
      clientId: "durable-installation-1",
      groupId: "group-rain:pordenone:1",
      policyVersion: COMMUNITY_GUIDELINES_POLICY_VERSION,
      vote: "no",
    });
  });

  it("does not post a denial without a durable installation identity", async () => {
    const confirmationPoster = vi.fn();

    await expect(confirmLiveCommunityReport("group-1", "no", {
      acceptedTerms: true,
      confirmationPoster,
      persistentClientIdResolver: () => "",
      policyVersion: COMMUNITY_GUIDELINES_POLICY_VERSION,
    })).resolves.toEqual({
      ok: false,
      reason: "persistent_identity_required",
    });
    expect(confirmationPoster).not.toHaveBeenCalled();
  });

  it("contains persistent identity resolver failures without posting a denial", async () => {
    const confirmationPoster = vi.fn();

    await expect(confirmLiveCommunityReport("group-1", "no", {
      acceptedTerms: true,
      confirmationPoster,
      persistentClientIdResolver: () => { throw new Error("storage blocked"); },
      policyVersion: COMMUNITY_GUIDELINES_POLICY_VERSION,
    })).resolves.toEqual({
      error: "storage blocked",
      ok: false,
      reason: "request_failed",
    });
    expect(confirmationPoster).not.toHaveBeenCalled();
  });

  it("preserves confirmation cooldown status and retry time", async () => {
    const error = Object.assign(new Error("Troppe conferme."), {
      detail: { message: "Troppe conferme.", retry_after_seconds: 18 },
      retryAfterSeconds: 18,
      status: 429,
    });

    await expect(confirmLiveCommunityReport("group-1", "yes", {
      acceptedTerms: true,
      confirmationPoster: vi.fn().mockRejectedValue(error),
      policyVersion: COMMUNITY_GUIDELINES_POLICY_VERSION,
    })).resolves.toEqual({
      detail: error.detail,
      error: error.message,
      ok: false,
      reason: "cooldown",
      retryAfterSeconds: 18,
      status: 429,
    });
  });

  it("rejects incomplete confirmation commands before the endpoint", async () => {
    const confirmationPoster = vi.fn();

    await expect(confirmLiveCommunityReport("", "yes", { confirmationPoster }))
      .resolves.toMatchObject({ ok: false, reason: "invalid_confirmation" });
    expect(confirmationPoster).not.toHaveBeenCalled();
  });

  it("does not post a confirmation before current community terms are accepted", async () => {
    const confirmationPoster = vi.fn();

    await expect(confirmLiveCommunityReport("group-1", "yes", {
      confirmationPoster,
    })).resolves.toEqual({ ok: false, reason: "terms_required" });
    expect(confirmationPoster).not.toHaveBeenCalled();
  });

  it("flags a community group with one of the explicit moderation reasons", async () => {
    const flagPoster = vi.fn().mockResolvedValue({
      flag_count: 1,
      group_id: "group-rain:pordenone:1",
      hidden: false,
      reason: "duplicate",
    });

    await expect(flagLiveCommunityReport(
      "group-rain:pordenone:1",
      "duplicate",
      {
        clientIdResolver: () => "client-1",
        flagPoster,
      },
    )).resolves.toEqual({
      flagCount: 1,
      groupId: "group-rain:pordenone:1",
      hidden: false,
      ok: true,
      reason: "duplicate",
    });
    expect(flagPoster).toHaveBeenCalledWith({
      clientId: "client-1",
      groupId: "group-rain:pordenone:1",
      reason: "duplicate",
    });
  });

  it("rejects unknown moderation reasons before calling the endpoint", async () => {
    const flagPoster = vi.fn();

    await expect(flagLiveCommunityReport("group-1", "other", { flagPoster }))
      .resolves.toEqual({ ok: false, reason: "invalid_flag" });
    expect(flagPoster).not.toHaveBeenCalled();
  });

  it("undoes a recent report with the same anonymous client", async () => {
    const reportDeleter = vi.fn().mockResolvedValue({ ok: true, report_id: "report-1" });

    await expect(undoLiveCommunityReport("report-1", {
      clientIdResolver: () => "client-1",
      reportDeleter,
    })).resolves.toEqual({ ok: true, reportId: "report-1" });
    expect(reportDeleter).toHaveBeenCalledWith({
      clientId: "client-1",
      reportId: "report-1",
    });
  });
});
