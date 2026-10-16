import { describe, expect, it, vi } from "vitest";

import communityConfirmedFixture from "../../../contracts/runtime-api/v1/live/community-confirmed.json";
import communityCreatedFixture from "../../../contracts/runtime-api/v1/live/community-created.json";
import communityDeletedFixture from "../../../contracts/runtime-api/v1/live/community-deleted.json";
import communityEmptyFixture from "../../../contracts/runtime-api/v1/live/community-empty.json";
import webcamsSuccessFixture from "../../../contracts/runtime-api/v1/live/webcams-success.json";
import { COMMUNITY_GUIDELINES_POLICY_VERSION } from "../features/live/liveReportPolicy";
import { FIREBASE_APP_CHECK_HEADER } from "./firebaseAppCheckAdapter";

import {
  LIVE_REPORT_CLIENT_ID_KEY,
  LIVE_REPORT_SESSION_CLIENT_ID_KEY,
  deleteCommunityReport,
  fetchCommunityReputation,
  fetchCommunityReports,
  fetchLiveWebcams,
  getOrCreateLiveReportClientId,
  getPersistentLiveReportClientId,
  postCommunityReport,
  postCommunityReportConfirmation,
  postCommunityReportFlag,
  readExistingLiveReportClientId,
} from "./liveApi";

function response(payload, { headers = {}, ok = true, status = 200 } = {}) {
  return {
    headers: { get: vi.fn((name) => headers[name] ?? headers[name.toLowerCase()] ?? null) },
    json: vi.fn().mockResolvedValue(payload),
    ok,
    status,
  };
}

describe("live api", () => {
  it("uses the dedicated webcam and community endpoints", async () => {
    const fetchImpl = vi.fn()
      .mockResolvedValueOnce(response(webcamsSuccessFixture))
      .mockResolvedValueOnce(response(communityEmptyFixture));

    await expect(fetchLiveWebcams({ fetchImpl })).resolves.toEqual(webcamsSuccessFixture);
    await expect(fetchCommunityReports({ fetchImpl })).resolves.toEqual(communityEmptyFixture);

    expect(fetchImpl.mock.calls[0][0]).toBe("/api/live/webcams");
    expect(fetchImpl.mock.calls[1][0]).toBe("/api/community/reports");
    expect(fetchImpl.mock.calls[0][1]).toMatchObject({ method: "GET" });
  });

  it("posts the report type, fresh coordinates, validated zone and anonymous client id", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(response(communityCreatedFixture));

    await postCommunityReport({
      acceptedTerms: true,
      clientId: "client-1",
      coords: { lat: 45.9567, lon: 12.6605 },
      policyVersion: COMMUNITY_GUIDELINES_POLICY_VERSION,
      selectedPlace: "Pordenone",
      typeId: "rain",
    }, { fetchImpl });

    expect(fetchImpl).toHaveBeenCalledWith("/api/community/reports", expect.objectContaining({
      body: JSON.stringify({
        accepted_terms: true,
        client_id: "client-1",
        lat: 45.9567,
        lon: 12.6605,
        policy_version: COMMUNITY_GUIDELINES_POLICY_VERSION,
        selected_place: "Pordenone",
        type_id: "rain",
      }),
      method: "POST",
    }));
  });

  it("reads reputation without putting the pseudonymous client id in the URL", async () => {
    const payload = {
      max_daily_awards: 3,
      pending_reports: 1,
      points: 6,
      rank: { id: "lookout", min_points: 5, next_rank_at: 20 },
      validated_reports: 7,
    };
    const fetchImpl = vi.fn().mockResolvedValue(response(payload));
    const appCheckTokenProvider = vi.fn().mockResolvedValue("pilot-app-check-token");

    await expect(fetchCommunityReputation(
      { clientId: "private-client-1" },
      { appCheckTokenProvider, fetchImpl },
    )).resolves.toEqual(payload);

    expect(fetchImpl).toHaveBeenCalledWith(
      "/api/community/reputation",
      expect.objectContaining({
        body: JSON.stringify({ client_id: "private-client-1" }),
        headers: expect.objectContaining({
          "Content-Type": "application/json",
          [FIREBASE_APP_CHECK_HEADER]: "pilot-app-check-token",
        }),
        method: "POST",
      }),
    );
    expect(fetchImpl.mock.calls[0][0]).not.toContain("private-client-1");
  });

  it("posts only the allowlisted public identity snapshot", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(response(communityCreatedFixture));

    await postCommunityReport({
      acceptedTerms: true,
      clientId: "private-client-1",
      coords: { lat: 45.9567, lon: 12.6605 },
      identity: {
        alias: "Clâf di Pordenon",
        avatar: { angle: 135, paletteId: "sky", patternId: "halo", variant: 2 },
        subjectId: "claf",
        version: 1,
      },
      policyVersion: COMMUNITY_GUIDELINES_POLICY_VERSION,
      selectedPlace: "Pordenone",
      typeId: "rain",
    }, { fetchImpl });

    const body = JSON.parse(fetchImpl.mock.calls[0][1].body);
    expect(body.identity).toEqual({
      alias: "Clâf di Pordenon",
      avatar: {
        angle: 135,
        palette_id: "sky",
        pattern_id: "halo",
        variant: 2,
      },
      subject_id: "claf",
      version: 1,
    });
    expect(JSON.stringify(body.identity)).not.toContain("private-client-1");
  });

  it("surfaces backend validation details", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(response(
      { detail: { message: "Segnalazione consentita solo in FVG." } },
      { ok: false, status: 400 },
    ));

    const promise = postCommunityReport({
      acceptedTerms: true,
      clientId: "client-1",
      coords: { lat: 44, lon: 12 },
      policyVersion: COMMUNITY_GUIDELINES_POLICY_VERSION,
      typeId: "rain",
    }, { fetchImpl });

    await expect(promise).rejects.toMatchObject({
      detail: { message: "Segnalazione consentita solo in FVG." },
      message: "Segnalazione consentita solo in FVG.",
      status: 400,
    });
  });

  it("preserves cooldown status, detail and Retry-After", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(response(
      {
        detail: {
          message: "Puoi inviare una nuova segnalazione più tardi.",
          retry_after_seconds: 119,
        },
      },
      { headers: { "Retry-After": "119" }, ok: false, status: 429 },
    ));

    await expect(postCommunityReport({
      acceptedTerms: true,
      clientId: "client-1",
      coords: { lat: 45.9567, lon: 12.6605 },
      policyVersion: COMMUNITY_GUIDELINES_POLICY_VERSION,
      selectedPlace: "Pordenone",
      typeId: "rain",
    }, { fetchImpl })).rejects.toMatchObject({
      detail: {
        message: "Puoi inviare una nuova segnalazione più tardi.",
        retry_after_seconds: 119,
      },
      retryAfterSeconds: 119,
      status: 429,
    });
  });

  it("posts confirmation votes against the active map group", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(response(communityConfirmedFixture));

    await postCommunityReportConfirmation({
      acceptedTerms: true,
      clientId: "client-1",
      groupId: communityConfirmedFixture.group_id,
      policyVersion: COMMUNITY_GUIDELINES_POLICY_VERSION,
      vote: "yes",
    }, { fetchImpl });

    expect(fetchImpl).toHaveBeenCalledWith(
      `/api/community/reports/${encodeURIComponent(communityConfirmedFixture.group_id)}/confirmation`,
      expect.objectContaining({
        body: JSON.stringify({
          accepted_terms: true,
          client_id: "client-1",
          policy_version: COMMUNITY_GUIDELINES_POLICY_VERSION,
          vote: "yes",
        }),
        method: "POST",
      }),
    );
  });

  it("posts a distinct moderation flag against the active map group", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(response({
      flag_count: 1,
      group_id: "group-rain:pordenone:1",
      hidden: false,
      reason: "inaccurate",
    }));

    await postCommunityReportFlag({
      clientId: "client-1",
      groupId: "group-rain:pordenone:1",
      reason: "inaccurate",
    }, { fetchImpl });

    expect(fetchImpl).toHaveBeenCalledWith(
      "/api/community/reports/group-rain%3Apordenone%3A1/flags",
      expect.objectContaining({
        body: JSON.stringify({ client_id: "client-1", reason: "inaccurate" }),
        method: "POST",
      }),
    );
  });

  it("deletes only the report identified by the anonymous client", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(response(communityDeletedFixture));

    await deleteCommunityReport({
      clientId: "client-1",
      reportId: "report-1",
    }, { fetchImpl });

    expect(fetchImpl).toHaveBeenCalledWith(
      "/api/community/reports/report-1",
      expect.objectContaining({
        body: JSON.stringify({ client_id: "client-1" }),
        method: "DELETE",
      }),
    );
  });

  it("adds the native App Check token only to report mutations", async () => {
    const fetchImpl = vi.fn()
      .mockResolvedValueOnce(response(communityCreatedFixture))
      .mockResolvedValueOnce(response(communityConfirmedFixture))
      .mockResolvedValueOnce(response({
        flag_count: 1,
        group_id: communityConfirmedFixture.group_id,
        hidden: false,
        reason: "misuse",
      }))
      .mockResolvedValueOnce(response(communityDeletedFixture));
    const appCheckTokenProvider = vi.fn().mockResolvedValue("pilot-app-check-token");

    await postCommunityReport({
      acceptedTerms: true,
      clientId: "client-1",
      coords: { lat: 45.9567, lon: 12.6605 },
      policyVersion: COMMUNITY_GUIDELINES_POLICY_VERSION,
      selectedPlace: "Pordenone",
      typeId: "rain",
    }, { appCheckTokenProvider, fetchImpl });
    await postCommunityReportConfirmation({
      acceptedTerms: true,
      clientId: "client-1",
      groupId: communityConfirmedFixture.group_id,
      policyVersion: COMMUNITY_GUIDELINES_POLICY_VERSION,
      vote: "yes",
    }, { appCheckTokenProvider, fetchImpl });
    await postCommunityReportFlag({
      clientId: "client-1",
      groupId: communityConfirmedFixture.group_id,
      reason: "misuse",
    }, { appCheckTokenProvider, fetchImpl });
    await deleteCommunityReport({
      clientId: "client-1",
      reportId: "report-1",
    }, { appCheckTokenProvider, fetchImpl });

    expect(appCheckTokenProvider).toHaveBeenCalledTimes(4);
    fetchImpl.mock.calls.forEach(([, options]) => {
      expect(options.headers).toMatchObject({
        "Content-Type": "application/json",
        [FIREBASE_APP_CHECK_HEADER]: "pilot-app-check-token",
      });
    });
  });

  it("keeps webcam and report reads free from App Check headers", async () => {
    const fetchImpl = vi.fn()
      .mockResolvedValueOnce(response(webcamsSuccessFixture))
      .mockResolvedValueOnce(response(communityEmptyFixture));
    const appCheckTokenProvider = vi.fn().mockResolvedValue("must-not-be-used");

    await fetchLiveWebcams({ appCheckTokenProvider, fetchImpl });
    await fetchCommunityReports({ appCheckTokenProvider, fetchImpl });

    expect(appCheckTokenProvider).not.toHaveBeenCalled();
    expect(fetchImpl.mock.calls[0][1].headers).toBeUndefined();
    expect(fetchImpl.mock.calls[1][1].headers).toBeUndefined();
  });

  it("does not send an Android mutation when App Check cannot issue a token", async () => {
    const fetchImpl = vi.fn();
    const appCheckTokenProvider = vi.fn().mockRejectedValue(
      new Error("firebase_app_check_token_missing"),
    );

    await expect(postCommunityReport({
      acceptedTerms: true,
      clientId: "client-1",
      coords: { lat: 45.9567, lon: 12.6605 },
      policyVersion: COMMUNITY_GUIDELINES_POLICY_VERSION,
      selectedPlace: "Pordenone",
      typeId: "rain",
    }, { appCheckTokenProvider, fetchImpl })).rejects.toThrow(
      "firebase_app_check_token_missing",
    );
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  it("persists one anonymous report client id", () => {
    const values = new Map();
    const storage = {
      getItem: vi.fn((key) => values.get(key) || null),
      setItem: vi.fn((key, value) => values.set(key, value)),
    };
    const cryptoLike = { randomUUID: vi.fn(() => "uuid-1") };

    const sessionState = { clientId: "" };

    expect(getOrCreateLiveReportClientId({ cryptoLike, sessionState, storage })).toBe("uuid-1");
    expect(getOrCreateLiveReportClientId({ cryptoLike, sessionState, storage })).toBe("uuid-1");
    expect(storage.setItem).toHaveBeenCalledWith(LIVE_REPORT_CLIENT_ID_KEY, "uuid-1");
    expect(cryptoLike.randomUUID).toHaveBeenCalledTimes(1);
  });

  it("reads an existing anonymous client id without generating or persisting one", () => {
    const localStorage = {
      getItem: vi.fn((key) => (
        key === LIVE_REPORT_CLIENT_ID_KEY ? "existing-local-client" : null
      )),
      setItem: vi.fn(),
    };
    const sessionStorage = {
      getItem: vi.fn(() => null),
      setItem: vi.fn(),
    };
    const cryptoLike = { randomUUID: vi.fn(() => "must-not-be-generated") };

    expect(readExistingLiveReportClientId({
      cryptoLike,
      sessionState: { clientId: "" },
      sessionStorage,
      storage: localStorage,
    })).toBe("existing-local-client");
    expect(cryptoLike.randomUUID).not.toHaveBeenCalled();
    expect(sessionStorage.setItem).not.toHaveBeenCalled();
    expect(localStorage.setItem).not.toHaveBeenCalled();
  });

  it("returns an empty client id without writes or generation when none exists", () => {
    const localStorage = {
      getItem: vi.fn(() => null),
      setItem: vi.fn(),
    };
    const sessionStorage = {
      getItem: vi.fn(() => null),
      setItem: vi.fn(),
    };
    const cryptoLike = { randomUUID: vi.fn(() => "must-not-be-generated") };

    expect(readExistingLiveReportClientId({
      cryptoLike,
      sessionState: { clientId: "" },
      sessionStorage,
      storage: localStorage,
    })).toBe("");
    expect(cryptoLike.randomUUID).not.toHaveBeenCalled();
    expect(sessionStorage.getItem).toHaveBeenCalledWith(
      LIVE_REPORT_SESSION_CLIENT_ID_KEY,
    );
    expect(localStorage.getItem).toHaveBeenCalledWith(LIVE_REPORT_CLIENT_ID_KEY);
    expect(sessionStorage.setItem).not.toHaveBeenCalled();
    expect(localStorage.setItem).not.toHaveBeenCalled();
  });

  it("keeps one anonymous client id for the session when storage throws", () => {
    const storage = {
      getItem: vi.fn(() => { throw new Error("blocked"); }),
      setItem: vi.fn(() => { throw new Error("blocked"); }),
    };
    const cryptoLike = { randomUUID: vi.fn(() => "session-uuid-1") };
    const sessionState = { clientId: "" };
    const sessionStorage = {
      getItem: vi.fn(() => null),
      setItem: vi.fn(),
    };

    expect(getOrCreateLiveReportClientId({ cryptoLike, sessionState, sessionStorage, storage }))
      .toBe("session-uuid-1");
    expect(getOrCreateLiveReportClientId({ cryptoLike, sessionState, sessionStorage, storage }))
      .toBe("session-uuid-1");
    expect(cryptoLike.randomUUID).toHaveBeenCalledTimes(1);
    expect(sessionStorage.setItem).toHaveBeenCalledWith(
      LIVE_REPORT_SESSION_CLIENT_ID_KEY,
      "session-uuid-1",
    );
  });

  it("keeps the fallback session id if storage becomes available later", () => {
    const sessionState = { clientId: "" };
    const cryptoLike = { randomUUID: vi.fn(() => "session-uuid-2") };
    const blockedStorage = {
      getItem: vi.fn(() => { throw new Error("blocked"); }),
      setItem: vi.fn(() => { throw new Error("blocked"); }),
    };
    const availableStorage = {
      getItem: vi.fn(() => "different-stored-id"),
      setItem: vi.fn(),
    };

    expect(getOrCreateLiveReportClientId({ cryptoLike, sessionState, storage: blockedStorage }))
      .toBe("session-uuid-2");
    expect(getOrCreateLiveReportClientId({ cryptoLike, sessionState, storage: availableStorage }))
      .toBe("session-uuid-2");
    expect(availableStorage.getItem).not.toHaveBeenCalled();
  });

  it("restores the fallback id from sessionStorage after an app reload", () => {
    const blockedStorage = {
      getItem: vi.fn(() => { throw new Error("blocked"); }),
      setItem: vi.fn(() => { throw new Error("blocked"); }),
    };
    const sessionStorage = {
      getItem: vi.fn(() => "session-restored-id"),
      setItem: vi.fn(),
    };
    const cryptoLike = { randomUUID: vi.fn(() => "must-not-be-generated") };

    expect(getOrCreateLiveReportClientId({
      cryptoLike,
      sessionState: { clientId: "" },
      sessionStorage,
      storage: blockedStorage,
    })).toBe("session-restored-id");
    expect(cryptoLike.randomUUID).not.toHaveBeenCalled();
  });

  it("prefers the active session identity over an older persistent identity", () => {
    const storage = {
      getItem: vi.fn(() => "older-local-id"),
      setItem: vi.fn(),
    };
    const sessionStorage = {
      getItem: vi.fn(() => "report-owner-session-id"),
      setItem: vi.fn(),
    };

    expect(getOrCreateLiveReportClientId({
      sessionState: { clientId: "" },
      sessionStorage,
      storage,
    })).toBe("report-owner-session-id");
    expect(storage.getItem).not.toHaveBeenCalled();
    expect(storage.setItem).toHaveBeenCalledWith(
      LIVE_REPORT_CLIENT_ID_KEY,
      "report-owner-session-id",
    );
  });

  it("contains a throwing global localStorage getter", () => {
    const descriptor = Object.getOwnPropertyDescriptor(globalThis, "localStorage");
    const sessionState = { clientId: "" };
    const cryptoLike = { randomUUID: vi.fn(() => "session-uuid-3") };

    Object.defineProperty(globalThis, "localStorage", {
      configurable: true,
      get() { throw new Error("SecurityError"); },
    });

    try {
      expect(getOrCreateLiveReportClientId({ cryptoLike, sessionState }))
        .toBe("session-uuid-3");
      expect(getOrCreateLiveReportClientId({ cryptoLike, sessionState }))
        .toBe("session-uuid-3");
    } finally {
      if (descriptor) Object.defineProperty(globalThis, "localStorage", descriptor);
      else delete globalThis.localStorage;
    }
  });

  it("returns a denial identity only after verifying durable persistence", () => {
    const values = new Map();
    const storage = {
      getItem: vi.fn((key) => values.get(key) || null),
      setItem: vi.fn((key, value) => values.set(key, value)),
    };
    const sessionStorage = {
      getItem: vi.fn(() => null),
      setItem: vi.fn(),
    };

    expect(getPersistentLiveReportClientId({
      cryptoLike: { randomUUID: () => "durable-installation-1" },
      sessionState: { clientId: "" },
      sessionStorage,
      storage,
    })).toBe("durable-installation-1");
    expect(storage.setItem).toHaveBeenCalledWith(
      LIVE_REPORT_CLIENT_ID_KEY,
      "durable-installation-1",
    );
    expect(storage.getItem(LIVE_REPORT_CLIENT_ID_KEY)).toBe("durable-installation-1");
  });

  it.each([
    ["silently unavailable", {
      getItem: vi.fn(() => null),
      setItem: vi.fn(),
    }],
    ["blocked", {
      getItem: vi.fn(() => { throw new Error("SecurityError"); }),
      setItem: vi.fn(() => { throw new Error("SecurityError"); }),
    }],
  ])("fails closed when persistent identity storage is %s", (_label, storage) => {
    expect(getPersistentLiveReportClientId({
      cryptoLike: { randomUUID: () => "ephemeral-only" },
      sessionState: { clientId: "" },
      sessionStorage: null,
      storage,
    })).toBe("");
  });
});
