import { describe, expect, it, vi } from "vitest";
vi.mock("../../services/localCommunityPilot", async (original) => ({
  ...await original(), isLocalCommunityPilot: () => true,
}));
import { confirmLiveCommunityReport } from "./liveReportController";
import { COMMUNITY_GUIDELINES_POLICY_VERSION } from "./liveReportPolicy";

describe("national confirmation evidence", () => {
  it.each(["yes", "no"])("requires current GPS for %s and sends the observed report IDs", async (vote) => {
    const location = { ok: true, coords: { lat: 45.95, lon: 12.66, accuracyM: 20 }, locatedAt: Date.now() };
    const locationResolver = vi.fn().mockResolvedValue(location);
    const confirmationPoster = vi.fn().mockResolvedValue({ vote });
    const options = { acceptedTerms: true, policyVersion: COMMUNITY_GUIDELINES_POLICY_VERSION,
      persistentClientIdResolver: () => "installation-test", reportIds: ["observed-report"],
      locationResolver, confirmationPoster };
    expect((await confirmLiveCommunityReport("group", vote, options)).ok).toBe(true);
    expect(locationResolver).toHaveBeenCalledExactlyOnceWith({ requireCurrent: true });
    expect(confirmationPoster).toHaveBeenCalledExactlyOnceWith(expect.objectContaining({
      clientId: "installation-test", coords: location.coords, reportIds: ["observed-report"], vote,
    }));
    confirmationPoster.mockClear();
    locationResolver.mockResolvedValue({ ok: false, reason: "permission_denied" });
    expect((await confirmLiveCommunityReport("group", vote, options)).reason).toBe("vote_location_required");
    expect(confirmationPoster).not.toHaveBeenCalled();
  });

  it("cannot submit a group-only vote without the observed report IDs", async () => {
    const confirmationPoster = vi.fn();
    const result = await confirmLiveCommunityReport("group", "yes", {
      acceptedTerms: true, policyVersion: COMMUNITY_GUIDELINES_POLICY_VERSION,
      persistentClientIdResolver: () => "installation-test", confirmationPoster,
      locationResolver: async () => ({ ok: true, locatedAt: Date.now(), coords: { lat: 45.95, lon: 12.66 } }),
    });
    expect(result.reason).toBe("observation_changed");
    expect(confirmationPoster).not.toHaveBeenCalled();
  });
});
