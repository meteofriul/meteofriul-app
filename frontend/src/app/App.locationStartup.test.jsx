// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const boundaries = vi.hoisted(() => ({
  requestCoordinates: vi.fn(),
  reverseLocation: vi.fn(),
  resume: null,
}));

// App startup, preference storage, location quality checks and the Android
// startup/resume policies remain real. Only device/network and visual boundaries
// are replaced; this does not simulate a Play upgrade or prove device behavior.
vi.mock("../services/localWeatherPilot", async importOriginal => ({
  ...await importOriginal(),
  isDefinitiveAppExperience: () => true,
  isLocalWeatherPilot: () => false,
}));
vi.mock("../services/deviceLocation", async importOriginal => ({
  ...await importOriginal(),
  requestDeviceCoordinates: (...args) => boundaries.requestCoordinates(...args),
}));
vi.mock("../services/reverseLocation", async importOriginal => ({
  ...await importOriginal(),
  resolveReverseLocation: (...args) => boundaries.reverseLocation(...args),
}));
vi.mock("../services/capacitorAppResume", async importOriginal => ({
  ...await importOriginal(),
  startCapacitorAppResumeRuntime: callbacks => {
    boundaries.resume = callbacks;
    return { stop() {} };
  },
}));
vi.mock("../services/nativePushAdapter", async importOriginal => ({
  ...await importOriginal(),
  getNativePushNotificationsPlugin: () => null,
}));
vi.mock("../services/backgroundLocationAdapter", async importOriginal => {
  const actual = await importOriginal();
  return {
    ...actual,
    configureBackgroundLocation: async () => actual.DEFAULT_BACKGROUND_LOCATION_STATUS,
    readBackgroundLocationStatus: async () => actual.DEFAULT_BACKGROUND_LOCATION_STATUS,
  };
});
vi.mock("../services/officialAlertsRuntime", async importOriginal => ({
  ...await importOriginal(),
  readInitialOfficialAlertsRuntime: () => ({ payload: null }),
  loadOfficialAlertsRuntime: async () => ({ payload: null, status: "unavailable" }),
}));
vi.mock("../features/live/liveDataController", async importOriginal => {
  const actual = await importOriginal();
  return { ...actual, loadLiveData: async () => actual.createEmptyLiveDataState() };
});
vi.mock("../features/home/homeDataController", async importOriginal => ({
  ...await importOriginal(),
  loadHomeWeather: async () => ({ status: "unavailable" }),
}));
vi.mock("./labFlags", () => ({ readUiV3LabFlag: () => false }));
vi.mock("../ui/layout/AppShell", () => ({
  AppShell: ({ children }) => <main>{children}</main>,
}));
vi.mock("./AppRoutes", () => ({
  AppRoutes: ({ autoLocationEnabled, deviceLocationStatus, activeLocation, onAutomaticLocationChange }) => (
    <>
      <output data-testid="location" data-enabled={String(autoLocationEnabled)}
        data-status={deviceLocationStatus.status} data-reason={deviceLocationStatus.reason || ""}
        data-city={activeLocation.city} />
      <button onClick={() => onAutomaticLocationChange(false)}>Disable location</button>
    </>
  ),
}));

import App from "./App";
import {
  APP_AUTO_LOCATION_STORAGE_KEY,
  APP_LOCATION_STORAGE_KEY,
  writeStoredAppLocation,
  writeStoredAutoLocationEnabled,
} from "./appLocation";
import { markBackgroundLocationDisclosureAccepted } from "../features/settings/backgroundLocationDisclosureState";
import { writePilotLanguageOnboardingState } from "../features/startup/pilotLanguageOnboardingState";

const storedPlace = {
  city: "Pordenone", source: "android_current_location",
  municipality: { name: "Pordenone", istatCode: "093033", province: "PN" },
  dataPoint: { lat: 45.957, lon: 12.661, source: "municipality_catalog" },
};
const freshFix = {
  ok: true, source: "android_current_location", ageMs: 500,
  coords: { lat: 45.957, lon: 12.661, accuracyM: 20 },
};
let root;
let container;

function preference() {
  return localStorage.getItem(APP_AUTO_LOCATION_STORAGE_KEY);
}
function view() {
  return container.querySelector('[data-testid="location"]');
}
async function mount() {
  root = createRoot(container);
  await act(async () => { root.render(<App />); });
}
async function unmount() {
  await act(async () => { root.unmount(); });
  root = null;
}
async function expectPreservedFailure(reason) {
  const previousPlace = localStorage.getItem(APP_LOCATION_STORAGE_KEY);
  await mount();
  expect(boundaries.requestCoordinates).toHaveBeenCalledTimes(1);
  expect(preference()).toBe("true");
  expect(view().dataset).toMatchObject({ enabled: "true", status: "error", reason, city: "Pordenone" });
  expect(localStorage.getItem(APP_LOCATION_STORAGE_KEY)).toBe(previousPlace);
}

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-10-22T08:00:00Z"));
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  // Select the existing Android branch without a real bridge or device.
  vi.stubGlobal("MeteoAndroid", {});
  vi.stubGlobal("fetch", vi.fn(() => { throw new Error("Unexpected live request"); }));
  localStorage.clear();
  window.history.replaceState({}, "", "/?tab=settings");
  writeStoredAppLocation(storedPlace);
  writeStoredAutoLocationEnabled(true);
  markBackgroundLocationDisclosureAccepted();
  writePilotLanguageOnboardingState();
  boundaries.requestCoordinates.mockReset().mockResolvedValue({ ok: false, reason: "native_location_timeout" });
  boundaries.reverseLocation.mockReset().mockResolvedValue({ ok: false, error: "reverse_unavailable" });
  boundaries.resume = null;
  container = document.createElement("div");
  document.body.append(container);
});

afterEach(async () => {
  if (root) await unmount();
  container.remove();
  expect(fetch).not.toHaveBeenCalled();
  vi.clearAllTimers();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("Android startup preserves an existing automatic location choice", () => {
  it.each(["native_location_timeout", "location_services_disabled", "stale_or_imprecise"])(
    "preserves the preference and last place after %s",
    async reason => {
      boundaries.requestCoordinates.mockResolvedValue({ ok: false, reason });
      await expectPreservedFailure(reason);
    },
  );

  it("preserves the preference if GPS succeeds but reverse lookup is temporarily unavailable", async () => {
    boundaries.requestCoordinates.mockResolvedValue(freshFix);
    await expectPreservedFailure("reverse_unavailable");
    expect(boundaries.reverseLocation).toHaveBeenCalledTimes(1);
  });

  it("can retry after startup failure and recover on the normal resume path", async () => {
    await expectPreservedFailure("native_location_timeout");
    boundaries.requestCoordinates.mockResolvedValue(freshFix);
    boundaries.reverseLocation.mockResolvedValue({
      ok: true, location: { ...storedPlace, resolution: { boundaryDistanceM: 1000 } },
    });
    await act(async () => { await boundaries.resume.onResume(); });
    expect(boundaries.requestCoordinates).toHaveBeenCalledTimes(2);
    expect(preference()).toBe("true");
    expect(view().dataset).toMatchObject({ enabled: "true", status: "success", city: "Pordenone" });
  });

  it.each(["permission_denied", "unsupported"])("still disables automatic location after %s", async reason => {
    boundaries.requestCoordinates.mockResolvedValue({ ok: false, reason });
    await mount();
    expect(preference()).toBe("false");
    expect(view().dataset.enabled).toBe("false");
  });

  it("does not reactivate a saved explicit opt-out", async () => {
    writeStoredAutoLocationEnabled(false);
    await mount();
    expect(boundaries.requestCoordinates).not.toHaveBeenCalled();
    expect(preference()).toBe("false");
    expect(view().dataset.enabled).toBe("false");
  });

  it("does not enable a new automatic preference when the first GPS request fails", async () => {
    localStorage.removeItem(APP_AUTO_LOCATION_STORAGE_KEY);
    localStorage.removeItem(APP_LOCATION_STORAGE_KEY);
    await mount();
    expect(boundaries.requestCoordinates).toHaveBeenCalledTimes(1);
    expect(preference()).toBe("false");
    expect(view().dataset.enabled).toBe("false");
  });

  it("keeps a deliberate disable after the temporary failure across the next startup", async () => {
    await expectPreservedFailure("native_location_timeout");
    await act(async () => { container.querySelector("button").click(); });
    expect(preference()).toBe("false");
    expect(view().dataset.enabled).toBe("false");
    await unmount();
    boundaries.requestCoordinates.mockClear();
    await mount();
    expect(boundaries.requestCoordinates).not.toHaveBeenCalled();
    expect(preference()).toBe("false");
    expect(view().dataset.enabled).toBe("false");
  });
});
