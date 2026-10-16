import { describe, expect, it, vi } from "vitest";

import {
  PUSH_INSTALLATION_ID_STORAGE_KEY,
  PUSH_LOCATION_EVIDENCE_FUTURE_SKEW_MS,
  PUSH_LOCATION_EVIDENCE_MAX_AGE_MS,
  readOrCreatePushInstallationId,
  readPushInstallationId,
  registerPushDevice,
  resolvePushRegistrationPreferences,
  toPushRegistrationLocationEvidence,
  toPushRegistrationLocationMode,
  toPushRegistrationLocality,
  toPushRegistrationMunicipality,
  unregisterPushDevice,
} from "./pushDeviceRegistration";

describe("pushDeviceRegistration", () => {
  it("disables only predictive local notices in the autonomous local pilot", () => {
    expect(resolvePushRegistrationPreferences({
      officialAlerts: true,
      weatherNotices: true,
    }, { localPilot: true })).toEqual({
      official_alerts: true,
      weather_notices: false,
    });
    expect(resolvePushRegistrationPreferences({
      officialAlerts: false,
      weatherNotices: true,
    }, { localPilot: false })).toEqual({
      official_alerts: false,
      weather_notices: true,
    });
    expect(resolvePushRegistrationPreferences({
      officialAlerts: true,
      weatherNotices: true,
    }, {
      localPilot: false,
      officialAlertsEligible: false,
    })).toEqual({
      official_alerts: false,
      weather_notices: true,
    });
  });

  it("creates one persistent random 128-bit installation id", () => {
    const values = new Map();
    const storage = {
      getItem: vi.fn((key) => values.get(key) || null),
      setItem: vi.fn((key, value) => values.set(key, value)),
    };
    const cryptoLike = {
      getRandomValues: vi.fn((bytes) => {
        bytes.forEach((_, index) => { bytes[index] = index; });
        return bytes;
      }),
    };

    const first = readOrCreatePushInstallationId({ cryptoLike, storage });
    const second = readOrCreatePushInstallationId({ cryptoLike, storage });

    expect(first).toBe("000102030405060708090a0b0c0d0e0f");
    expect(second).toBe(first);
    expect(storage.setItem).toHaveBeenCalledWith(PUSH_INSTALLATION_ID_STORAGE_KEY, first);
    expect(cryptoLike.getRandomValues).toHaveBeenCalledTimes(1);
  });

  it("reads an existing installation id without creating one", () => {
    const storage = {
      getItem: vi.fn(() => null),
      setItem: vi.fn(),
    };

    expect(readPushInstallationId({ storage })).toBe("");
    expect(storage.setItem).not.toHaveBeenCalled();

    storage.getItem.mockReturnValue("00112233445566778899AABBCCDDEEFF");
    expect(readPushInstallationId({ storage })).toBe("00112233445566778899aabbccddeeff");
    expect(storage.setItem).not.toHaveBeenCalled();
  });

  it("only sends a complete municipality and never coordinates", () => {
    expect(toPushRegistrationMunicipality({
      city: "Pordenone",
      istatCode: "093033",
      lat: 45.95,
      lon: 12.66,
    })).toEqual({ istat: "093033", name: "Pordenone" });
    expect(toPushRegistrationMunicipality({ city: "Pordenone" })).toBeNull();
    expect(toPushRegistrationMunicipality({
      city: "Udine",
      istatCode: "030129",
      source: "placeholder",
    })).toBeNull();
  });

  it("sends only a corroborated canonical locality id and name", () => {
    const location = {
      city: "Fontanafredda",
      displayName: "Vigonovo",
      lat: 45.9892,
      lon: 12.5473,
      locality: { id: "irdat:vigonovo", name: "Vigonovo", kind: "settlement" },
      municipality: { istatCode: "093022", name: "Fontanafredda" },
      resolution: { localityCorroborated: true },
    };

    expect(toPushRegistrationMunicipality(location)).toEqual({
      istat: "093022",
      name: "Fontanafredda",
    });
    expect(toPushRegistrationLocality(location)).toEqual({
      id: "irdat:vigonovo",
      name: "Vigonovo",
    });
    expect(toPushRegistrationLocality({
      ...location,
      resolution: { localityCorroborated: false },
    })).toBeNull();
    expect(toPushRegistrationLocality({
      ...location,
      resolution: undefined,
    })).toBeNull();
    expect(toPushRegistrationLocality({ city: "Fontanafredda" })).toBeNull();
  });

  it("sends location evidence only for a complete verified GPS fix", () => {
    const now = () => Date.parse("2026-08-16T10:05:00.000Z");
    const gpsLocation = {
      lat: 45.9892,
      lon: 12.5473,
      positionAccuracyM: 12.5,
      positionCapturedAt: "2026-08-16T10:00:00+00:00",
      source: "android_current_location",
    };

    expect(toPushRegistrationLocationEvidence(gpsLocation, { now })).toEqual({
      captured_at: "2026-08-16T10:00:00.000Z",
      accuracy_m: 12.5,
    });
    expect(toPushRegistrationLocationEvidence({
      ...gpsLocation,
      source: "manual",
    }, { now })).toBeNull();
    expect(toPushRegistrationLocationEvidence({
      ...gpsLocation,
      positionAccuracyM: null,
    }, { now })).toBeNull();
    expect(toPushRegistrationLocationEvidence({
      ...gpsLocation,
      positionCapturedAt: "invalid",
    }, { now })).toBeNull();
    expect(toPushRegistrationLocationEvidence({
      ...gpsLocation,
      positionAccuracyM: 251,
    }, { now })).toBeNull();
    expect(toPushRegistrationLocationMode({
      ...gpsLocation,
      city: "Fontanafredda",
      istatCode: "093022",
      locality: { id: "irdat:vigonovo", name: "Vigonovo" },
      municipality: { istatCode: "093022", name: "Fontanafredda" },
      resolution: { localityCorroborated: true },
    }, { now })).toBe("automatic_gps");
    expect(toPushRegistrationLocationMode({
      ...gpsLocation,
      city: "Fontanafredda",
      istatCode: "093022",
      locality: null,
      municipality: { istatCode: "093022", name: "Fontanafredda" },
      resolution: { localityCorroborated: false },
    }, { now })).toBe("automatic_gps");
  });

  it("drops stale or future GPS evidence without dropping the canonical target", async () => {
    const nowMs = Date.parse("2026-08-16T12:00:00.000Z");
    const canonicalLocation = {
      city: "Fontanafredda",
      displayName: "Vigonovo",
      istatCode: "093022",
      lat: 45.9892,
      lon: 12.5473,
      locality: { id: "irdat:vigonovo", name: "Vigonovo" },
      municipality: { istatCode: "093022", name: "Fontanafredda" },
      resolution: { localityCorroborated: true },
      positionAccuracyM: 12,
      source: "android_current_location",
    };
    const staleLocation = {
      ...canonicalLocation,
      positionCapturedAt: new Date(
        nowMs - PUSH_LOCATION_EVIDENCE_MAX_AGE_MS - 1,
      ).toISOString(),
    };
    const futureLocation = {
      ...canonicalLocation,
      positionCapturedAt: new Date(
        nowMs + PUSH_LOCATION_EVIDENCE_FUTURE_SKEW_MS + 1,
      ).toISOString(),
    };

    expect(toPushRegistrationLocationEvidence(staleLocation, { now: nowMs })).toBeNull();
    expect(toPushRegistrationLocationMode(staleLocation, { now: nowMs })).toBeNull();
    expect(toPushRegistrationLocationEvidence(futureLocation, { now: nowMs })).toBeNull();
    expect(toPushRegistrationLocationMode(futureLocation, { now: nowMs })).toBeNull();

    const fetchImpl = vi.fn(async () => ({
      json: async () => ({ registered: true }),
      ok: true,
      status: 200,
    }));
    await registerPushDevice({
      activeLocation: staleLocation,
      apiBase: "/api",
      appVersion: "pilot",
      fetchImpl,
      installationId: "00112233445566778899aabbccddeeff",
      now: nowMs,
      token: "fcm-secret",
      tokenProvider: async () => "app-check-token",
    });

    expect(JSON.parse(fetchImpl.mock.calls[0][1].body)).toMatchObject({
      municipality: { istat: "093022", name: "Fontanafredda" },
      locality: { id: "irdat:vigonovo", name: "Vigonovo" },
      location_evidence: null,
      location_mode: null,
    });
  });

  it("keeps a recent locality as an explicit manual target without stale GPS evidence", () => {
    const recentLocation = {
      city: "Fontanafredda",
      displayName: "Vigonovo",
      lat: 45.9892,
      lon: 12.5473,
      locality: { id: "irdat:vigonovo", name: "Vigonovo" },
      municipality: { istatCode: "093022", name: "Fontanafredda" },
      resolution: { localityCorroborated: true },
      source: "manual_recent",
    };

    expect(toPushRegistrationMunicipality(recentLocation)).toEqual({
      istat: "093022",
      name: "Fontanafredda",
    });
    expect(toPushRegistrationLocality(recentLocation)).toEqual({
      id: "irdat:vigonovo",
      name: "Vigonovo",
    });
    expect(toPushRegistrationLocationEvidence(recentLocation)).toBeNull();
    expect(toPushRegistrationLocationMode(recentLocation)).toBe("manual_selection");
    expect(toPushRegistrationLocationMode({
      city: "Udine",
      istatCode: "030129",
      source: "placeholder",
    })).toBeNull();
    expect(toPushRegistrationLocationMode({
      city: "Pordenone",
      istatCode: "093033",
      source: "manual",
    })).toBe("manual_selection");
  });

  it("registers a municipality-only GPS target without inventing a locality", async () => {
    const fetchImpl = vi.fn(async () => ({
      json: async () => ({ registered: true }),
      ok: true,
      status: 200,
    }));

    await registerPushDevice({
      activeLocation: {
        city: "Fontanafredda",
        istatCode: "093022",
        lat: 45.972,
        lon: 12.575,
        locality: null,
        municipality: { istatCode: "093022", name: "Fontanafredda" },
        resolution: { localityCorroborated: false, status: "municipality_only" },
        positionAccuracyM: 18,
        positionCapturedAt: "2026-08-16T10:00:00.000Z",
        source: "android_current_location",
      },
      apiBase: "/api",
      appVersion: "pilot",
      fetchImpl,
      installationId: "00112233445566778899aabbccddeeff",
      now: () => Date.parse("2026-08-16T10:05:00.000Z"),
      token: "fcm-secret",
      tokenProvider: async () => "app-check-token",
    });

    expect(JSON.parse(fetchImpl.mock.calls[0][1].body)).toMatchObject({
      municipality: { istat: "093022", name: "Fontanafredda" },
      locality: null,
      location_evidence: {
        captured_at: "2026-08-16T10:00:00.000Z",
        accuracy_m: 18,
      },
      location_mode: "automatic_gps",
    });
  });

  it("registers the Android device with the fixed App Check contract", async () => {
    const fetchImpl = vi.fn(async () => ({
      json: async () => ({ registered: true }),
      ok: true,
      status: 200,
    }));
    const tokenProvider = vi.fn(async () => "app-check-token");

    await expect(registerPushDevice({
      activeLocation: {
        city: "Fontanafredda",
        displayName: "Vigonovo",
        istatCode: "093022",
        lat: 45.9892,
        lon: 12.5473,
        locality: { id: "irdat:vigonovo", name: "Vigonovo" },
        municipality: { istatCode: "093022", name: "Fontanafredda" },
        resolution: { localityCorroborated: true },
        positionAccuracyM: 12,
        positionCapturedAt: "2026-08-16T10:00:00.000Z",
        source: "android_current_location",
      },
      apiBase: "https://example.test/api",
      appVersion: "3.0.0-pilot.3",
      fetchImpl,
      installationId: "00112233445566778899aabbccddeeff",
      language: "fur",
      notificationPreferences: { officialAlerts: true, weatherNotices: false },
      now: () => Date.parse("2026-08-16T10:05:00.000Z"),
      token: "fcm-secret",
      tokenProvider,
    })).resolves.toEqual({ registered: true });

    expect(fetchImpl).toHaveBeenCalledWith(
      "https://example.test/api/push/devices/register",
      expect.objectContaining({
        headers: {
          "Content-Type": "application/json",
          "X-Firebase-AppCheck": "app-check-token",
        },
        method: "POST",
      }),
    );
    expect(JSON.parse(fetchImpl.mock.calls[0][1].body)).toEqual({
      installation_id: "00112233445566778899aabbccddeeff",
      token: "fcm-secret",
      platform: "android",
      app_version: "3.0.0-pilot.3",
      language: "fur",
      municipality: { istat: "093022", name: "Fontanafredda" },
      locality: { id: "irdat:vigonovo", name: "Vigonovo" },
      location_evidence: {
        captured_at: "2026-08-16T10:00:00.000Z",
        accuracy_m: 12,
      },
      location_mode: "automatic_gps",
      preferences: { official_alerts: true, weather_notices: false },
    });
  });

  it("registers a manual municipality target without inventing a locality", async () => {
    const fetchImpl = vi.fn(async () => ({
      json: async () => ({ registered: true }),
      ok: true,
      status: 200,
    }));

    await registerPushDevice({
      activeLocation: {
        city: "Pordenone",
        istatCode: "093033",
        source: "manual",
      },
      apiBase: "/api",
      appVersion: "pilot",
      fetchImpl,
      installationId: "00112233445566778899aabbccddeeff",
      token: "fcm-secret",
      tokenProvider: async () => "app-check-token",
    });

    expect(JSON.parse(fetchImpl.mock.calls[0][1].body)).toMatchObject({
      municipality: { istat: "093033", name: "Pordenone" },
      locality: null,
      location_evidence: null,
      location_mode: "manual_selection",
    });
  });

  it("keeps national alerts off by default for a manually selected Italian municipality", async () => {
    const fetchImpl = vi.fn(async () => ({
      json: async () => ({ registered: true }),
      ok: true,
      status: 200,
    }));

    await registerPushDevice({
      activeLocation: {
        city: "Roma",
        country: "Italia",
        countryCode: "IT",
        istatCode: "058091",
        municipality: { istatCode: "058091", name: "Roma", province: "RM" },
        province: "RM",
        region: "Lazio",
        regionCode: "IT-62",
        source: "manual",
      },
      apiBase: "/api",
      appVersion: "pilot",
      fetchImpl,
      installationId: "00112233445566778899aabbccddeeff",
      notificationPreferences: { officialAlerts: true, weatherNotices: true },
      token: "fcm-secret",
      tokenProvider: async () => "app-check-token",
    });

    expect(JSON.parse(fetchImpl.mock.calls[0][1].body)).toMatchObject({
      municipality: { istat: "058091", name: "Roma" },
      locality: null,
      location_evidence: null,
      location_mode: "manual_selection",
      preferences: {
        official_alerts: false,
        weather_notices: true,
      },
    });
  });

  it("enrolls an exact manually selected national municipality only after explicit opt-in", async () => {
    const fetchImpl = vi.fn(async () => ({
      json: async () => ({ registered: true }),
      ok: true,
      status: 200,
    }));
    const roma = {
      city: "Roma",
      countryCode: "IT",
      municipality: { istatCode: "058091", name: "Roma" },
      regionCode: "IT-62",
      source: "manual",
    };

    await registerPushDevice({
      activeLocation: roma,
      apiBase: "/api",
      appVersion: "0.1.13",
      fetchImpl,
      installationId: "00112233445566778899aabbccddeeff",
      notificationPreferences: { nationalOfficialAlerts: true, officialAlerts: false },
      token: "fcm-secret",
      tokenProvider: async () => "app-check-token",
    });

    expect(JSON.parse(fetchImpl.mock.calls[0][1].body)).toMatchObject({
      municipality: { istat: "058091", name: "Roma" },
      location_evidence: null,
      location_mode: "manual_selection",
      preferences: { official_alerts: true },
    });
  });

  it.each(["android", "web"])("rejects national GPS enrollment on %s", async (platform) => {
    const fetchImpl = vi.fn(async () => ({
      json: async () => ({ registered: true }),
      ok: true,
      status: 200,
    }));
    await registerPushDevice({
      activeLocation: {
        city: "Roma",
        countryCode: "IT",
        municipality: { istatCode: "058091", name: "Roma" },
        regionCode: "IT-62",
        source: "capacitor_geolocation",
      },
      apiBase: "/api",
      fetchImpl,
      installationId: "00112233445566778899aabbccddeeff",
      notificationPreferences: { nationalOfficialAlerts: true },
      platform,
      registration: platform === "web"
        ? { kind: "firebase_installation_id", value: "cABCDEFGHIJKLMNOPQRSTU" }
        : undefined,
      token: "fcm-secret",
      tokenProvider: async () => "app-check-token",
    });

    expect(JSON.parse(fetchImpl.mock.calls[0][1].body)).toMatchObject({
      municipality: null,
      location_mode: null,
      preferences: { official_alerts: false },
    });
  });

  it("keeps web national registration disabled even with manual municipality and opt-in", async () => {
    const fetchImpl = vi.fn(async () => ({
      json: async () => ({ registered: true }),
      ok: true,
      status: 200,
    }));
    await registerPushDevice({
      activeLocation: {
        city: "Roma",
        countryCode: "IT",
        municipality: { istatCode: "058091", name: "Roma" },
        regionCode: "IT-62",
        source: "manual",
      },
      apiBase: "/api",
      fetchImpl,
      installationId: "00112233445566778899aabbccddeeff",
      notificationPreferences: { nationalOfficialAlerts: true },
      platform: "web",
      registration: { kind: "firebase_installation_id", value: "cABCDEFGHIJKLMNOPQRSTU" },
      tokenProvider: async () => "app-check-token",
    });

    expect(JSON.parse(fetchImpl.mock.calls[0][1].body)).toMatchObject({
      municipality: null,
      preferences: { official_alerts: false },
    });
  });

  it("registers web messaging by FID without exposing an Android token field", async () => {
    const fetchImpl = vi.fn(async () => ({
      json: async () => ({ registered: true }),
      ok: true,
      status: 200,
    }));

    await registerPushDevice({
      activeLocation: {
        city: "Pordenone",
        istatCode: "093033",
        lat: 45.9567,
        lon: 12.6605,
        positionAccuracyM: 8,
        positionCapturedAt: "2026-08-16T10:00:00.000Z",
        source: "browser_geolocation",
      },
      apiBase: "/api",
      appVersion: "3.0.0-pilot.6",
      fetchImpl,
      installationId: "00112233445566778899aabbccddeeff",
      language: "it",
      notificationPreferences: { officialAlerts: true, weatherNotices: true },
      platform: "web",
      registration: {
        kind: "firebase_installation_id",
        value: "cABCDEFGHIJKLMNOPQRSTU",
      },
      tokenProvider: async () => "web-app-check-token",
    });

    expect(JSON.parse(fetchImpl.mock.calls[0][1].body)).toEqual({
      installation_id: "00112233445566778899aabbccddeeff",
      platform: "web",
      app_version: "3.0.0-pilot.6",
      language: "it",
      municipality: { istat: "093033", name: "Pordenone" },
      locality: null,
      location_evidence: null,
      location_mode: "manual_selection",
      preferences: { official_alerts: true, weather_notices: true },
      registration: {
        kind: "firebase_installation_id",
        value: "cABCDEFGHIJKLMNOPQRSTU",
      },
    });
    expect(fetchImpl.mock.calls[0][1].body).not.toContain('"token"');
  });

  it("force-refreshes App Check once after an authentication rejection", async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValueOnce({ json: async () => ({}), ok: false, status: 401 })
      .mockResolvedValueOnce({ json: async () => ({ registered: true }), ok: true, status: 200 });
    const tokenProvider = vi
      .fn()
      .mockResolvedValueOnce("stale")
      .mockResolvedValueOnce("fresh");

    await registerPushDevice({
      apiBase: "/api",
      appVersion: "pilot",
      fetchImpl,
      installationId: "00112233445566778899aabbccddeeff",
      token: "fcm-secret",
      tokenProvider,
    });

    expect(tokenProvider).toHaveBeenNthCalledWith(1, { forceRefresh: false });
    expect(tokenProvider).toHaveBeenNthCalledWith(2, { forceRefresh: true });
    expect(fetchImpl).toHaveBeenCalledTimes(2);
  });

  it("does not refresh or retry a terminal 403 enrollment rejection", async () => {
    const fetchImpl = vi.fn(async () => ({
      json: async () => ({
        detail: { code: "push_platform_not_allowed" },
      }),
      ok: false,
      status: 403,
    }));
    const tokenProvider = vi.fn(async () => "valid-app-check-token");

    await expect(registerPushDevice({
      apiBase: "/api",
      appVersion: "web",
      fetchImpl,
      installationId: "00112233445566778899aabbccddeeff",
      language: "it",
      notificationPreferences: { officialAlerts: true, weatherNotices: true },
      platform: "web",
      registration: {
        kind: "firebase_installation_id",
        value: "cABCDEFGHIJKLMNOPQRSTU",
      },
      tokenProvider,
    })).rejects.toMatchObject({
      code: "push_device_http_403",
      serverCode: "push_platform_not_allowed",
      status: 403,
    });

    expect(tokenProvider).toHaveBeenCalledTimes(1);
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });

  it("unregisters using only the private installation id", async () => {
    const fetchImpl = vi.fn(async () => ({
      json: async () => ({ unregistered: true }),
      ok: true,
      status: 200,
    }));

    await unregisterPushDevice({
      apiBase: "/api",
      fetchImpl,
      installationId: "00112233445566778899aabbccddeeff",
      tokenProvider: async () => "app-check-token",
    });

    expect(JSON.parse(fetchImpl.mock.calls[0][1].body)).toEqual({
      installation_id: "00112233445566778899aabbccddeeff",
    });
  });
});
