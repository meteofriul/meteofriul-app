// @vitest-environment jsdom

import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../services/localCommunityPilot", async (importOriginal) => ({
  ...await importOriginal(),
  isLocalCommunityPilot: vi.fn(() => true),
}));

import { getLiveViewCopy } from "../../copy/liveViewCopy";
import { CommunityReportForm } from "./LiveView";
import { rememberCommunityGuidelinesConsent } from "./communityGuidelinesConsent";
import { createCommunityReportPreviewMemoryStorage } from "./communityReportPreview";
import { COMMUNITY_GUIDELINES_POLICY_VERSION } from "./liveReportPolicy";
import { rememberReportLocationNoticeConsent } from "./reportLocationNoticeConsent";

describe("community report submit location verification", () => {
  let container;
  let root;
  let copy;
  let storage;

  const initialLocation = {
    ok: true,
    coords: { accuracyM: 30, lat: 45.9567, lon: 12.6605 },
    locatedAt: Date.parse("2026-10-02T10:00:00Z"),
    istatCode: "093033",
    selectedPlace: "Pordenone",
    nearbyPlaces: [{ place: "Pordenone", distanceKm: 0 }],
    source: "capacitor_geolocation",
  };
  const currentLocation = {
    ...initialLocation,
    coords: { accuracyM: 12, lat: 45.957, lon: 12.661 },
    locatedAt: Date.parse("2026-10-02T10:00:10Z"),
  };

  beforeEach(() => {
    globalThis.IS_REACT_ACT_ENVIRONMENT = true;
    vi.stubGlobal("requestAnimationFrame", (callback) => setTimeout(callback, 0));
    vi.stubGlobal("cancelAnimationFrame", (id) => clearTimeout(id));
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    copy = getLiveViewCopy("it");
    storage = createCommunityReportPreviewMemoryStorage();
    rememberCommunityGuidelinesConsent(COMMUNITY_GUIDELINES_POLICY_VERSION, { storage });
    rememberReportLocationNoticeConsent({ storage });
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    container.remove();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    delete globalThis.IS_REACT_ACT_ENVIRONMENT;
  });

  async function renderForm({ onLocate, onSubmit }) {
    await act(async () => {
      root.render(
        <CommunityReportForm
          copy={copy}
          dialogId="submit-location-test"
          locations={[]}
          maxDistanceKm={5}
          onClose={() => {}}
          onLocate={onLocate}
          onSubmit={onSubmit}
          options={[{ id: "rain", label: copy.reportTypes.rain }]}
          personalStorage={storage}
          personalState={{ reports: [], votes: [], mapWithdrawals: [] }}
          pilotStyle
          sheet
        />,
      );
    });
  }

  async function chooseAndSubmit() {
    const dialog = document.querySelector("#submit-location-test");
    await act(async () => dialog.querySelector(".mf-live-report-option--rain").click());
    await act(async () => dialog.querySelector(".mf-live-report-submit").click());
    await act(async () => dialog.querySelector(".mf-live-report-submit").click());
    return dialog;
  }

  it("blocks the POST when location services are disabled after the initial fix", async () => {
    const onLocate = vi.fn()
      .mockResolvedValueOnce(initialLocation)
      .mockResolvedValueOnce({ ok: false, reason: "location_services_disabled" });
    const onSubmit = vi.fn();
    await renderForm({ onLocate, onSubmit });

    const dialog = await chooseAndSubmit();

    expect(onLocate).toHaveBeenCalledTimes(2);
    expect(onLocate).toHaveBeenLastCalledWith({
      locations: [],
      maxDistanceKm: 5,
      requireCurrent: true,
    });
    expect(onSubmit).not.toHaveBeenCalled();
    expect(dialog.querySelector(".mf-live-report-location__copy strong")?.textContent)
      .toBe(copy.reportGpsServicesDisabled);
    expect(dialog.querySelector(".mf-live-report-submit").disabled).toBe(true);
    expect(dialog.querySelector(".mf-live-report-option--rain").getAttribute("aria-pressed"))
      .toBe("true");
  });

  it("submits only the location reacquired at confirmation time", async () => {
    const onLocate = vi.fn()
      .mockResolvedValueOnce(initialLocation)
      .mockResolvedValueOnce(currentLocation);
    const onSubmit = vi.fn().mockResolvedValue({
      ok: true,
      report: { id: "report-current", typeId: "rain" },
    });
    await renderForm({ onLocate, onSubmit });

    await chooseAndSubmit();

    expect(onSubmit).toHaveBeenCalledExactlyOnceWith(
      "rain",
      currentLocation,
      expect.objectContaining({
        acceptedTerms: true,
        policyVersion: COMMUNITY_GUIDELINES_POLICY_VERSION,
      }),
    );
  });

  it("explains that approximate location is insufficient and does not post", async () => {
    const onLocate = vi.fn()
      .mockResolvedValueOnce(initialLocation)
      .mockResolvedValueOnce({ ok: false, reason: "approximate_location" });
    const onSubmit = vi.fn();
    await renderForm({ onLocate, onSubmit });

    const dialog = await chooseAndSubmit();

    expect(onSubmit).not.toHaveBeenCalled();
    expect(dialog.querySelector(".mf-live-report-location__copy strong")?.textContent)
      .toBe(copy.reportGpsApproximate);
  });
  it("keeps the existing form and requires a review before sending", async () => {
    const onLocate = vi.fn().mockResolvedValue(currentLocation);
    const onSubmit = vi.fn().mockResolvedValue({ ok: true });
    await renderForm({ onLocate, onSubmit });
    const dialog = document.querySelector("#submit-location-test");
    await act(async () => dialog.querySelector(".mf-live-report-option--rain").click());
    await act(async () => dialog.querySelector(".mf-live-report-submit").click());
    expect(onSubmit).not.toHaveBeenCalled();
    expect(dialog.querySelector(".mf-live-report-review").textContent).toContain("Pordenone");
    expect(dialog.textContent).toContain(copy.reportReviewReplacement);
    await act(async () => dialog.querySelector(".mf-live-report-review button").click());
    expect(dialog.querySelector(".mf-live-report-option--rain").getAttribute("aria-pressed")).toBe("true");
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("requires a new review if fresh GPS resolves a different municipality", async () => {
    const changed = { ...currentLocation, istatCode: "030129", selectedPlace: "Udine" };
    const onLocate = vi.fn().mockResolvedValueOnce(initialLocation).mockResolvedValue(changed);
    const onSubmit = vi.fn().mockResolvedValue({ ok: true });
    await renderForm({ onLocate, onSubmit });
    const dialog = await chooseAndSubmit();
    expect(onSubmit).not.toHaveBeenCalled();
    expect(dialog.textContent).toContain(copy.reportReviewLocationChanged);
    await act(async () => dialog.querySelector(".mf-live-report-submit").click());
    expect(dialog.querySelector(".mf-live-report-review").textContent).toContain("Udine");
    expect(onSubmit).not.toHaveBeenCalled();
    await act(async () => dialog.querySelector(".mf-live-report-submit").click());
    expect(onSubmit).toHaveBeenCalledExactlyOnceWith("rain", changed, expect.any(Object));
  });

});
