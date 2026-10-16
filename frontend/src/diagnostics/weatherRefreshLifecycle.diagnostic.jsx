// @vitest-environment jsdom
import { act, useEffect } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const auditState = vi.hoisted(() => ({
  completed: [],
  routeRefreshes: [],
}));

vi.mock("../services/localWeatherPilot", async importOriginal => ({
  ...await importOriginal(),
  isDefinitiveAppExperience: () => false,
  isLocalWeatherPilot: () => false,
}));

vi.mock("../app/appLocation", async importOriginal => ({
  ...await importOriginal(),
  readInitialAppLocation: () => ({
    city: "Pordenone",
    source: "manual",
    municipality: { name: "Pordenone", istatCode: "093033" },
    lat: 45.9567,
    lon: 12.6605,
  }),
  readStoredAutoLocationEnabled: () => false,
}));

vi.mock("../services/officialAlertsRuntime", async importOriginal => ({
  ...await importOriginal(),
  readInitialOfficialAlertsRuntime: () => ({ payload: null }),
  loadOfficialAlertsRuntime: async () => ({
    payload: null,
    status: "fresh",
    alertState: "inactive_confirmed",
  }),
}));

vi.mock("../services/firebaseWebMessaging", async importOriginal => ({
  ...await importOriginal(),
  createWebPushRuntime: async () => ({ ok: false, reason: "not_configured" }),
  readWebPushPermission: () => "unsupported",
}));

vi.mock("../features/startup/webStartupOnboardingState", async importOriginal => ({
  ...await importOriginal(),
  readWebStartupOnboardingState: () => "completed",
}));

vi.mock("../ui/layout/AppShell", () => ({
  AppShell: ({ children, onRuntimeRefresh, onTabChange }) => (
    <main>
      <button
        data-testid="manual-refresh"
        onClick={() => {
          void onRuntimeRefresh({ force: true }).then(result => auditState.completed.push(result));
        }}
      >
        Refresh
      </button>
      <button data-testid="open-bulletin" onClick={() => onTabChange("bulletin")}>Bollettino</button>
      <button data-testid="open-home" onClick={() => onTabChange("home")}>Home</button>
      {children}
    </main>
  ),
}));

vi.mock("../app/labFlags", () => ({ readUiV3LabFlag: () => false }));

vi.mock("../app/AppRoutes", () => {
  function RouteRefreshProbe({ onSettled, tab, token }) {
    useEffect(() => {
      if (!token) return;
      auditState.routeRefreshes.push({ tab, token });
      onSettled(token, { status: "success" });
    }, [onSettled, tab, token]);

    return <output data-testid="route-token">{`${tab}:${token}`}</output>;
  }

  return {
    AppRoutes: ({ activeTab, onRuntimeRefreshSettled, runtimeRefreshToken }) => (
      // AppRoutes gives the real route view an equivalent tab/location key.
      <RouteRefreshProbe
        key={activeTab}
        onSettled={onRuntimeRefreshSettled}
        tab={activeTab}
        token={runtimeRefreshToken}
      />
    ),
  };
});

import App from "../app/App";

let container;
let root;

beforeEach(() => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  Object.defineProperty(document, "visibilityState", { configurable: true, value: "visible" });
  window.localStorage.clear();
  auditState.completed = [];
  auditState.routeRefreshes = [];
  container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
});

afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

async function click(testId) {
  await act(async () => {
    container.querySelector(`[data-testid="${testId}"]`).click();
    await Promise.resolve();
    await Promise.resolve();
  });
}

describe("open weather refresh lifecycle contract at revision 3f517a8", () => {
  it("consumes a completed refresh token once instead of replaying it on later route mounts", async () => {
    await act(async () => root.render(<App />));
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    await click("manual-refresh");
    expect(auditState.completed).toEqual([{ status: "settled", token: 1 }]);
    expect(auditState.routeRefreshes).toEqual([{ tab: "home", token: 1 }]);

    await click("open-bulletin");
    await click("open-home");

    expect(auditState.routeRefreshes.filter(({ token }) => token === 1)).toHaveLength(1);
  });
});
