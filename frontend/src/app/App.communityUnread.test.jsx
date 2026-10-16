// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const testState = vi.hoisted(() => ({ previewMode: "", routes: null, shell: null }));

// Keep App's state, snapshot reconciliation and durable seen journal real.
// Only expose the route/shell contract and neutralize unrelated IO boundaries.
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
  isDefinitiveAppExperience: () => true,
  isLocalWeatherPilot: () => true,
  isLocalWeatherNationalPilot: () => true,
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
import {
  COMMUNITY_SEEN_STORAGE_KEY,
  createCommunityUnreadSnapshot,
  markCommunitySnapshotSeen,
  readCommunitySeenState,
  writeCommunitySeenState,
} from "../features/live/communityUnreadState";

const NOW = Date.parse("2026-09-21T18:00:00Z");
const HOUR = 60 * 60 * 1000;
const LOCATION = { city: "Pordenone", lat: 45.9567, lon: 12.6605 };
const TORINO = { city: "Torino", lat: 45.0703, lon: 7.6869 };
let root;
let container;

function community(ids = ["report-a"], overrides = {}) {
  const group = {
    ...LOCATION, id: "group-rain", groupId: "group-rain", typeId: "rain",
    count: ids.length, reportIds: ids, expiresAt: Date.now() + HOUR,
    contributions: ids.map(id => ({ id, sourceKey: `source-${id}`, expiresAt: Date.now() + HOUR })),
  };
  return { enabled: true, status: { id: "fresh" }, items: [group], markers: [group], ...overrides };
}

async function mount() {
  root = createRoot(container);
  await act(async () => { root.render(<App />); });
}

async function navigate(route) {
  await act(async () => { testState.routes.onNavigate(route); });
}

async function publish(model = community(), location = LOCATION, options) {
  await act(async () => { testState.routes.onCommunityNavigationState(location, model, options); });
}

async function viewed(model = community(), location = LOCATION, options) {
  await act(async () => { testState.routes.onCommunityReportsViewed(location, model, options); });
}

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(NOW);
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  vi.stubGlobal("fetch", vi.fn(() => { throw new Error("Unexpected live network request"); }));
  Object.defineProperty(document, "visibilityState", { configurable: true, value: "visible" });
  window.history.replaceState({}, "", "/?tab=home");
  window.localStorage.clear();
  testState.previewMode = "";
  testState.routes = null;
  testState.shell = null;
  container = document.createElement("div");
  document.body.append(container);
});

afterEach(async () => {
  if (root) await act(async () => root.unmount());
  root = null;
  container.remove();
  vi.clearAllTimers();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("App pilot community unread wiring", () => {
  it("counts fresh route snapshots and clears only after the current live map reports viewing", async () => {
    await mount();
    expect(testState.shell.communityReportsUnread).toBe(true);
    await publish(community(["a", "b"]));
    expect(testState.shell.communityReportsTotal).toBe(2);

    // A callback on Home and merely switching tabs are not evidence of viewing.
    await viewed(community(["a", "b"]));
    expect(testState.shell.communityReportsTotal).toBe(2);
    await navigate("live");
    expect(testState.routes.activeTab).toBe("live");
    expect(testState.shell.communityReportsTotal).toBe(2);
    await viewed(community(["a", "b"]));
    expect(testState.shell.communityReportsTotal).toBe(0);
    await navigate("home");
    expect(testState.shell.communityReportsTotal).toBe(0);
  });

  it("counts a new ID even when aggregate count is unchanged, but does not recount a renewal", async () => {
    await mount();
    await publish(community(["original"]));
    await navigate("live");
    await viewed(community(["original"]));
    await navigate("home");
    vi.setSystemTime(NOW + 10 * 60_000);
    await publish(community(["original"]));
    expect(testState.shell.communityReportsTotal).toBe(0);
    await publish(community(["new-report"]));
    expect(testState.shell.communityReportsTotal).toBe(1);
  });

  it.each(["stale", "cache", "loading", "error"])("does not mark a %s model viewed", async status => {
    await mount();
    await publish();
    await navigate("live");
    await viewed(community(undefined, { status: { id: status } }));
    expect(testState.shell.communityReportsTotal).toBe(1);
    expect(readCommunitySeenState().locations).toEqual([]);
  });

  it("ignores view callbacks while the document is hidden", async () => {
    await mount();
    await publish();
    await navigate("live");
    Object.defineProperty(document, "visibilityState", { configurable: true, value: "hidden" });
    await viewed();
    expect(testState.shell.communityReportsTotal).toBe(1);
    expect(readCommunitySeenState().locations).toEqual([]);
    Object.defineProperty(document, "visibilityState", { configurable: true, value: "visible" });
    await viewed();
    expect(testState.shell.communityReportsTotal).toBe(0);
  });

  it("ignores both snapshot and view callbacks for a different selected location", async () => {
    await mount();
    await publish();
    await navigate("live");
    await publish(community(["other-location-report"]), TORINO);
    await viewed(community(), TORINO);
    expect(testState.shell.communityReportsTotal).toBe(1);
    expect(readCommunitySeenState().locations).toEqual([]);
    await viewed();
    expect(testState.shell.communityReportsTotal).toBe(0);
  });

  it("persists actual seen state across App remounts without marking a later ID seen", async () => {
    await mount();
    await publish();
    await navigate("live");
    await viewed();
    expect(readCommunitySeenState().locations[0].entries[0].id).toBe("report-a");
    await act(async () => root.unmount());
    root = null;
    await mount();
    await publish();
    expect(testState.shell.communityReportsTotal).toBe(0);
    await publish(community(["report-a", "report-b"]));
    expect(testState.shell.communityReportsTotal).toBe(1);
  });

  it("isolates interactive QA seen state from the persistent actual pilot journal", async () => {
    const realState = markCommunitySnapshotSeen(
      readCommunitySeenState(), createCommunityUnreadSnapshot(LOCATION, community()),
    );
    writeCommunitySeenState(realState);
    const persisted = window.localStorage.getItem(COMMUNITY_SEEN_STORAGE_KEY);
    const setItem = vi.spyOn(Storage.prototype, "setItem");
    testState.previewMode = "interactive";
    await mount();
    await publish();
    // Actual seen IDs must not suppress independent preview data with the same ID.
    expect(testState.shell.communityReportsTotal).toBe(1);
    await navigate("live");
    await viewed();
    expect(testState.shell.communityReportsTotal).toBe(0);
    expect(window.localStorage.getItem(COMMUNITY_SEEN_STORAGE_KEY)).toBe(persisted);
    expect(setItem.mock.calls.filter(([key]) => key === COMMUNITY_SEEN_STORAGE_KEY)).toEqual([]);
    await act(async () => root.unmount());
    root = null;
    await mount();
    await publish();
    expect(testState.shell.communityReportsTotal).toBe(1);
    expect(window.localStorage.getItem(COMMUNITY_SEEN_STORAGE_KEY)).toBe(persisted);
  });
});
