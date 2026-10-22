// @vitest-environment jsdom
import { StrictMode, act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const testState = vi.hoisted(() => ({ previewMode: "", routes: null, shell: null, definitive: true }));

// Keep App navigation and browser history real; isolate unrelated service IO.
vi.mock("../ui/layout/AppShell", () => ({
  AppShell: (props) => {
    testState.shell = props;
    return <main data-unread={props.communityReportsTotal ?? "none"}>{props.children}</main>;
  },
}));
vi.mock("./AppRoutes", () => ({
  AppRoutes: (props) => { testState.routes = props; return null; },
}));
vi.mock("../services/localWeatherPilot", async importOriginal => ({
  ...await importOriginal(),
  isDefinitiveAppExperience: () => testState.definitive,
  isLocalWeatherPilot: () => testState.definitive,
  isLocalWeatherNationalPilot: () => testState.definitive,
}));
vi.mock("../services/localCommunityPilot", async importOriginal => ({
  ...await importOriginal(), isLocalCommunityPilot: () => true,
}));
vi.mock("../features/live/communityReportPreview", async importOriginal => ({
  ...await importOriginal(), getLocalCommunityReportPreviewMode: () => testState.previewMode,
}));
vi.mock("./appLocation", async importOriginal => ({
  ...await importOriginal(),
  readInitialAppLocation: () => ({
    city: "Pordenone", lat: 45.9567, lon: 12.6605,
    municipality: { name: "Pordenone", istatCode: "093033" }, source: "manual",
  }),
  readStoredAutoLocationEnabled: () => false,
}));
vi.mock("../features/live/liveDataController", async importOriginal => ({
  ...await importOriginal(),
  readInitialLiveData: () => null,
  loadLiveData: () => new Promise(() => {}),
}));
vi.mock("../services/officialAlertsRuntime", async importOriginal => ({
  ...await importOriginal(),
  readInitialOfficialAlertsRuntime: () => ({ payload: null }),
  loadOfficialAlertsRuntime: async () => ({ payload: null, status: "fresh", alertState: "inactive_confirmed" }),
}));
vi.mock("../services/firebaseWebMessaging", async importOriginal => ({
  ...await importOriginal(),
  createWebPushRuntime: async () => ({ ok: false, reason: "not_configured" }),
  readWebPushPermission: () => "unsupported",
}));
vi.mock("../features/startup/webStartupOnboardingState", async importOriginal => ({
  ...await importOriginal(), readWebStartupOnboardingState: () => "completed",
}));
vi.mock("../features/startup/pilotLanguageOnboardingState", async importOriginal => ({
  ...await importOriginal(), readPilotLanguageOnboardingState: () => "completed",
}));
vi.mock("../services/weatherApi", async importOriginal => ({
  ...await importOriginal(), readWeatherBootstrapCache: () => null,
}));
vi.mock("../features/home/homeDataController", async importOriginal => ({
  ...await importOriginal(), loadHomeWeather: () => new Promise(() => {}),
}));
vi.mock("./labFlags", () => ({ readUiV3LabFlag: () => false }));

import App from "./App";

const ENTRY = "__mfBrowserDialog";
let root;
let container;

async function mount(route = "home") {
  window.history.replaceState({ unrelated: "retained" }, "", `/?tab=${route}`);
  root = createRoot(container);
  await act(async () => root.render(<StrictMode><App /></StrictMode>));
}

async function openSettings() {
  await act(async () => testState.shell.onSettingsOpen());
  await act(async () => vi.waitFor(() => expect(window.history.state?.[ENTRY]).toBeTruthy()));
  expect(testState.routes.activeTab).toBe("settings");
}

async function browserBack() {
  await act(async () => {
    const returned = new Promise(resolve => window.addEventListener("popstate", resolve, { once: true }));
    window.history.back();
    await returned;
  });
}

async function expectReturned(route) {
  await act(async () => vi.waitFor(() => expect(window.history.state).toEqual({ unrelated: "retained" })));
  expect(testState.routes.activeTab).toBe(route);
}

beforeEach(() => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  vi.stubGlobal("fetch", vi.fn(() => { throw new Error("Unexpected live network request"); }));
  window.localStorage.clear();
  testState.definitive = true;
  testState.routes = null;
  testState.shell = null;
  container = document.createElement("div");
  document.body.append(container);
});

afterEach(async () => {
  if (root) await act(async () => root.unmount());
  await act(async () => vi.waitFor(() => expect(window.history.state?.[ENTRY]).toBeUndefined()));
  root = null;
  container.remove();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe.each([true, false])("Settings browser Back (definitive experience: %s)", definitive => {
  it.each(["home", "weather", "bulletin", "events", "discover"])("returns to %s without leaving the browser page", async route => {
    testState.definitive = definitive;
    await mount(route);
    const url = window.location.href;
    const push = vi.spyOn(window.history, "pushState");
    await openSettings();
    expect(push).toHaveBeenCalledTimes(1);
    await browserBack();
    await expectReturned(route);
    expect(window.location.href).toBe(url);
  });
});

it("uses the section actually visited, including repeated Back and in-app arrow cycles", async () => {
  await mount("weather");
  for (const route of ["events", "bulletin", "weather"]) {
    await act(async () => testState.routes.onNavigate(route));
    await openSettings();
    await browserBack();
    await expectReturned(route);
    await openSettings();
    await act(async () => testState.routes.onSettingsBack());
    await expectReturned(route);
  }
});

it("cleans the Settings entry when leaving through another tab", async () => {
  await mount("events");
  await openSettings();
  await act(async () => testState.routes.onNavigate("weather"));
  await expectReturned("weather");
  await openSettings();
  await browserBack();
  await expectReturned("weather");
});
