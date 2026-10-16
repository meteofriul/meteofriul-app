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

const NOW = Date.parse("2026-09-21T12:00:00Z");

describe("pilot direct observation editor", () => {
  let container;
  let root;
  let clock;
  let copy;
  let report;
  let location;
  let storage;
  let actions;

  beforeEach(() => {
    globalThis.IS_REACT_ACT_ENVIRONMENT = true;
    clock = NOW;
    vi.spyOn(Date, "now").mockImplementation(() => clock);
    vi.stubGlobal("requestAnimationFrame", (callback) => setTimeout(callback, 0));
    vi.stubGlobal("cancelAnimationFrame", (id) => clearTimeout(id));
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    copy = getLiveViewCopy("it");
    report = Object.freeze({
      reportId: "owned-rain", groupId: "rain:pordenone", typeId: "rain",
      place: "Pordenone", istatCode: "093033", revision: 1,
      createdAt: NOW, expiresAt: NOW + 3_600_000,
      correctionUntil: NOW + 300_000, replacementAvailable: true,
    });
    location = {
      ok: true, coords: { lat: 45.9567, lon: 12.6605, accuracyM: 30 },
      locatedAt: NOW, istatCode: "093033", detectedPlace: "Pordenone",
      selectedPlace: "Pordenone", nearbyPlaces: [{ place: "Pordenone", distanceKm: 0 }],
    };
    storage = createCommunityReportPreviewMemoryStorage();
    rememberCommunityGuidelinesConsent(COMMUNITY_GUIDELINES_POLICY_VERSION, { storage });
    rememberReportLocationNoticeConsent({ storage });
    actions = {
      onClose: vi.fn(),
      onLocate: vi.fn().mockResolvedValue(location),
      onManagedUpdate: vi.fn().mockResolvedValue({
        ok: true, action: "updated", report: { ...report, id: report.reportId, revision: 2 },
      }),
      onSubmit: vi.fn().mockResolvedValue({
        ok: true, report: { ...report, id: report.reportId, typeId: "wind", revision: 2 },
      }),
      onConfirmNearby: vi.fn().mockResolvedValue({ ok: true }),
      onPersonalStateChange: vi.fn(),
      onViewMap: vi.fn(),
    };
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    container.remove();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    delete globalThis.IS_REACT_ACT_ENVIRONMENT;
  });

  async function render(overrides = {}) {
    await act(async () => {
      root.render(
        <CommunityReportForm
          {...actions}
          copy={copy}
          dialogId="direct-edit-test"
          locations={[]}
          managedReport={report}
          maxDistanceKm={5}
          options={Object.entries(copy.reportTypes)
            .filter(([id]) => id !== "unknown")
            .map(([id, label]) => ({ id, label }))}
          personalState={{ reports: [report], votes: [], mapWithdrawals: [] }}
          personalStorage={storage}
          pilotStyle
          sheet
          {...overrides}
        />,
      );
    });
  }

  const dialog = () => document.querySelector("#direct-edit-test");
  const options = () => Array.from(dialog().querySelectorAll(".mf-live-report-option"));
  const submit = () => dialog().querySelector(".mf-live-report-submit");
  const select = async (typeId) => {
    await act(async () => dialog().querySelector(`.mf-live-report-option--${typeId}`).click());
  };
  const confirm = async () => { await act(async () => submit().click()); };

  it("opens all eight icons with the current phenomenon selected and does not mutate on opening", async () => {
    await render();
    expect(options()).toHaveLength(8);
    expect(options().filter((button) => button.getAttribute("aria-pressed") === "true"))
      .toEqual([dialog().querySelector(".mf-live-report-option--rain")]);
    expect(submit().textContent).toBe("Conferma che continua");
    expect(submit().disabled).toBe(false);
    expect(actions.onLocate).toHaveBeenCalledOnce();
    expect(actions.onSubmit).not.toHaveBeenCalled();
    expect(actions.onManagedUpdate).not.toHaveBeenCalled();
  });

  it("renews the same phenomenon using the existing update action and an accurate success title", async () => {
    await render();
    await confirm();
    expect(actions.onLocate).toHaveBeenCalledOnce();
    expect(actions.onManagedUpdate).toHaveBeenCalledExactlyOnceWith(report);
    expect(actions.onSubmit).not.toHaveBeenCalled();
    expect(dialog().querySelector(".mf-live-report-success__title")?.textContent)
      .toBe("Situazione aggiornata!");
    expect(dialog().querySelector(".mf-live-report-success__description")?.textContent)
      .toContain("stesso fenomeno");
    expect(dialog().textContent).not.toContain("Segnalazione inviata!");
  });

  it("corrects a different phenomenon within five minutes without selecting replacement", async () => {
    await render();
    await select("wind");
    expect(submit().textContent).toBe("Conferma modifica");
    expect(dialog().querySelector(".mf-live-report-duration")?.textContent).toContain(copy.reportCorrectionHint);
    await confirm();
    expect(actions.onSubmit).toHaveBeenCalledExactlyOnceWith("wind", location, expect.objectContaining({
      acceptedTerms: true, correctionReport: report, replacementReport: null,
    }));
    expect(actions.onManagedUpdate).not.toHaveBeenCalled();
    expect(dialog().querySelector(".mf-live-report-success__title")?.textContent)
      .toBe("Osservazione corretta");
  });

  it("explains and submits replacement only on explicit confirmation after five minutes", async () => {
    clock = NOW + 300_000;
    await render();
    await select("wind");
    expect(dialog().querySelector(".mf-live-report-duration")?.textContent).toContain(copy.reportEditReplacementHint);
    expect(actions.onSubmit).not.toHaveBeenCalled();
    await confirm();
    expect(actions.onSubmit).toHaveBeenCalledExactlyOnceWith("wind", location, expect.objectContaining({
      correctionReport: null, replacementReport: report,
    }));
    expect(actions.onManagedUpdate).not.toHaveBeenCalled();
  });

  it.each(["close", "Escape"])("leaves the original untouched when closing with %s after changing selection", async (method) => {
    await render();
    await select("wind");
    await act(async () => {
      if (method === "close") dialog().querySelector(".mf-live-report-form__header button").click();
      else document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    });
    expect(actions.onClose).toHaveBeenCalledOnce();
    expect(actions.onSubmit).not.toHaveBeenCalled();
    expect(actions.onManagedUpdate).not.toHaveBeenCalled();
  });

  it("does not mistake the selected own phenomenon for a nearby vote or self-match", async () => {
    await render({
      activeGroups: [{
        ...report, id: report.groupId, count: 1,
        lat: location.coords.lat, lon: location.coords.lon,
        reportIds: [report.reportId],
      }],
      selfMatchGroupIds: [report.groupId],
    });
    expect(dialog().querySelector(".mf-live-report-match")).toBeNull();
    expect(submit().textContent).toBe("Conferma che continua");
    await confirm();
    expect(actions.onManagedUpdate).toHaveBeenCalledOnce();
    expect(actions.onConfirmNearby).not.toHaveBeenCalled();
  });

  it("asks for a second explicit confirmation if correction expires between explanation and tap", async () => {
    await render();
    await select("wind");
    expect(dialog().querySelector(".mf-live-report-duration")?.textContent).toContain(copy.reportCorrectionHint);
    clock = NOW + 300_000;
    await confirm();
    expect(actions.onSubmit).not.toHaveBeenCalled();
    expect(dialog().textContent).toContain(copy.reportEditChanged);
    expect(dialog().querySelector(".mf-live-report-duration")?.textContent).toContain(copy.reportEditReplacementHint);
    await confirm();
    expect(actions.onSubmit).toHaveBeenCalledExactlyOnceWith("wind", location, expect.objectContaining({
      correctionReport: null, replacementReport: report,
    }));
  });

  it("locks all choices after an uncertain correction and retries the same intention", async () => {
    actions.onSubmit.mockResolvedValue({ ok: false, uncertain: true, reason: "request_failed" });
    await render();
    await select("wind");
    await confirm();
    expect(options().every((button) => button.disabled)).toBe(true);
    expect(submit().textContent).toBe("Verifica l’esito");
    await select("rain");
    clock = NOW + 300_000;
    await confirm();
    expect(actions.onSubmit).toHaveBeenCalledTimes(2);
    expect(actions.onSubmit.mock.calls[1]).toEqual(actions.onSubmit.mock.calls[0]);
    expect(actions.onManagedUpdate).not.toHaveBeenCalled();
  });

  it("locks all choices after an uncertain renewal and never routes its retry to creation", async () => {
    actions.onManagedUpdate.mockResolvedValue({ ok: false, reason: "request_failed" });
    await render();
    await confirm();
    expect(options().every((button) => button.disabled)).toBe(true);
    expect(submit().textContent).toBe("Verifica l’esito");
    await select("wind");
    await confirm();
    expect(actions.onManagedUpdate).toHaveBeenCalledTimes(2);
    expect(actions.onSubmit).not.toHaveBeenCalled();
  });

  it("treats a thrown submission error as uncertain and locks the correction intention", async () => {
    actions.onSubmit.mockRejectedValue(new Error("connection interrupted"));
    await render();
    await select("wind");
    await confirm();
    expect(options().every((button) => button.disabled)).toBe(true);
    expect(submit().textContent).toBe("Verifica l’esito");
    expect(dialog().textContent).toContain(copy.reportEditPending);
    await select("rain");
    await confirm();
    expect(actions.onSubmit).toHaveBeenCalledTimes(2);
    expect(actions.onSubmit.mock.calls[1]).toEqual(actions.onSubmit.mock.calls[0]);
    expect(actions.onManagedUpdate).not.toHaveBeenCalled();
  });

  it("keeps a failed replacement creation locked to completion after the old report was withdrawn", async () => {
    clock = NOW + 300_000;
    actions.onSubmit.mockResolvedValue({
      ok: false, replacementWithdrawn: true, reason: "rejected", code: "community_hourly_limit",
    });
    await render();
    await select("wind");
    await confirm();
    expect(options().every((button) => button.disabled)).toBe(true);
    expect(submit().textContent).toBe("Completa sostituzione");
    await select("rain");
    await confirm();
    expect(actions.onSubmit).toHaveBeenCalledTimes(2);
    expect(actions.onSubmit.mock.calls[1][0]).toBe("wind");
    expect(actions.onManagedUpdate).not.toHaveBeenCalled();
    expect(actions.onPersonalStateChange).toHaveBeenCalled();
  });

  it("refreshes stale GPS after retirement without losing the chosen replacement or promising the original remains", async () => {
    clock = NOW + 300_000;
    actions.onSubmit.mockResolvedValueOnce({
      ok: false, replacementWithdrawn: true, reason: "stale_or_imprecise",
      code: "community_location_stale",
    });
    await render();
    await select("wind");
    await confirm();
    expect(options().every((button) => button.disabled)).toBe(true);
    expect(submit().disabled).toBe(true);
    expect(submit().textContent).toBe("Completa sostituzione");
    expect(dialog().querySelector(".mf-live-report-form__header")?.textContent)
      .not.toContain("Finché non confermi, la segnalazione non cambia");
    const retryGps = dialog().querySelector(`button[aria-label="${copy.reportGpsRetry}"]`);
    expect(retryGps).not.toBeNull();
    expect(retryGps.disabled).toBe(false);
    const freshLocation = { ...location, locatedAt: clock, coords: { ...location.coords, accuracyM: 15 } };
    actions.onLocate.mockResolvedValue(freshLocation);
    await act(async () => retryGps.click());
    expect(actions.onLocate).toHaveBeenCalledTimes(3);
    expect(options().every((button) => button.disabled)).toBe(true);
    expect(submit().disabled).toBe(false);
    expect(submit().textContent).toBe("Completa sostituzione");
    await confirm();
    expect(actions.onLocate).toHaveBeenCalledTimes(4);
    expect(actions.onSubmit).toHaveBeenCalledTimes(2);
    expect(actions.onSubmit.mock.calls[1]).toEqual(["wind", freshLocation, expect.objectContaining({
      correctionReport: null, replacementReport: report,
    })]);
    expect(actions.onManagedUpdate).not.toHaveBeenCalled();
  });

  it("opens an unresolved renewal already locked to verifying that operation", async () => {
    const pendingReport = { ...report, pendingUpdate: true };
    await render({ managedReport: pendingReport });
    expect(options().every((button) => button.disabled)).toBe(true);
    expect(submit().textContent).toBe("Verifica l’esito");
    await confirm();
    expect(actions.onManagedUpdate).toHaveBeenCalledExactlyOnceWith(pendingReport);
    expect(actions.onSubmit).not.toHaveBeenCalled();
  });

  it("does not offer replacement after its one-time permission was already consumed", async () => {
    clock = NOW + 300_000;
    await render({ managedReport: { ...report, replacementAvailable: false } });
    await select("wind");
    expect(submit().disabled).toBe(true);
    expect(dialog().textContent).toContain(copy.reportChangeUnavailable);
    expect(actions.onSubmit).not.toHaveBeenCalled();
    await select("rain");
    expect(submit().disabled).toBe(false);
    expect(submit().textContent).toBe("Conferma che continua");
  });
});
