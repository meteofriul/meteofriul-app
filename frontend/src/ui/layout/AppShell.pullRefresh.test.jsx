// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getUiShellCopy } from "../../app/uiShellCopy";

vi.mock("./AppHeader", () => ({
  AppHeader: ({ hidePilotProfileAction }) => (
    <div data-hide-pilot-profile-action={hidePilotProfileAction ? "true" : "false"} />
  ),
}));
vi.mock("./BottomNavigation", () => ({ BottomNavigation: () => null }));

import { AppShell } from "./AppShell";

function dispatchTouch(target, type, touches = []) {
  const event = new Event(type, { bubbles: true, cancelable: true });
  Object.defineProperty(event, "touches", { value: touches });
  target.dispatchEvent(event);
}

describe("AppShell plain-language pull refresh feedback", () => {
  let container;
  let root;

  beforeEach(() => {
    vi.useFakeTimers();
    vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    container.remove();
    vi.clearAllTimers();
    vi.useRealTimers();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("fits only the requested main viewport without affecting other routes", async () => {
    await act(async () => {
      root.render(
        <AppShell
          activeRoute="live"
          activeTab="weather"
          copy={getUiShellCopy("it")}
          fitMainViewport
          language="it"
          tabs={[]}
        >
          <div>Territorio</div>
        </AppShell>,
      );
    });

    expect(container.querySelector(".mf-app-main")?.classList)
      .toContain("mf-app-main--territory-fit");

    await act(async () => {
      root.render(
        <AppShell
          activeRoute="weather"
          activeTab="weather"
          copy={getUiShellCopy("it")}
          language="it"
          tabs={[]}
        >
          <div>Previsioni</div>
        </AppShell>,
      );
    });

    expect(container.querySelector(".mf-app-main")?.classList)
      .not.toContain("mf-app-main--territory-fit");
  });

  it("activates the approved definitive-app chrome only when requested", async () => {
    await act(async () => {
      root.render(
        <AppShell
          activeRoute="weather"
          activeTab="weather"
          copy={getUiShellCopy("it")}
          definitiveExperience
          language="it"
          tabs={[]}
        >
          <div>Previsioni</div>
        </AppShell>,
      );
    });

    expect(container.querySelector(".mf-app-shell")?.classList)
      .toContain("is-definitive-app");

    await act(async () => {
      root.render(
        <AppShell
          activeRoute="weather"
          activeTab="weather"
          copy={getUiShellCopy("it")}
          language="it"
          tabs={[]}
        >
          <div>Previsioni</div>
        </AppShell>,
      );
    });

    expect(container.querySelector(".mf-app-shell")?.classList)
      .not.toContain("is-definitive-app");
  });

  it("hides the pilot profile action only while settings is the active route", async () => {
    const renderShell = async (activeRoute) => {
      await act(async () => {
        root.render(
          <AppShell
            activeRoute={activeRoute}
            activeTab="home"
            copy={getUiShellCopy("it")}
            language="it"
            tabs={[]}
          >
            <div>{activeRoute}</div>
          </AppShell>,
        );
      });
    };

    await renderShell("settings");
    expect(container.querySelector("[data-hide-pilot-profile-action]")?.dataset.hidePilotProfileAction)
      .toBe("true");

    await renderShell("weather");
    expect(container.querySelector("[data-hide-pilot-profile-action]")?.dataset.hidePilotProfileAction)
      .toBe("false");
  });

  it("keeps partial component diagnostics out of the user-facing message", async () => {
    const onRuntimeRefresh = vi.fn(async () => ({
      components: {
        cams: "settled",
        icon: "settled",
        internalWeatherAdapter: "backend_timeout",
        officialAlerts: "unavailable",
      },
      status: "partial",
    }));

    await act(async () => {
      root.render(
        <AppShell
          activeRoute="weather"
          activeTab="weather"
          copy={getUiShellCopy("it")}
          language="it"
          onRuntimeRefresh={onRuntimeRefresh}
          tabs={[]}
        >
          <div>Previsioni ICON disponibili</div>
        </AppShell>,
      );
    });

    const main = container.querySelector(".mf-app-main");
    await act(async () => {
      dispatchTouch(main, "touchstart", [{ clientX: 40, clientY: 0 }]);
      dispatchTouch(main, "touchmove", [{ clientX: 40, clientY: 400 }]);
      dispatchTouch(main, "touchend");
      await vi.advanceTimersByTimeAsync(1400);
    });

    const status = container.querySelector('[role="status"]');
    expect(onRuntimeRefresh).toHaveBeenCalledWith({ force: true, source: "pull" });
    expect(status.textContent).toBe("Aggiornato");
    expect(status.textContent).not.toMatch(/allerte|officialAlerts|internalWeatherAdapter|backend_timeout/i);
    expect(container.textContent).toContain("Previsioni ICON disponibili");
  });

  it("turns a failed refresh into an actionable connection message", async () => {
    const onRuntimeRefresh = vi.fn(async () => ({
      components: {
        icon: "failed",
        officialAlerts: "settled",
      },
      status: "failed",
    }));

    await act(async () => {
      root.render(
        <AppShell
          activeRoute="weather"
          activeTab="weather"
          copy={getUiShellCopy("it")}
          language="it"
          onRuntimeRefresh={onRuntimeRefresh}
          tabs={[]}
        >
          <div>Ultimi dati disponibili</div>
        </AppShell>,
      );
    });

    const main = container.querySelector(".mf-app-main");
    await act(async () => {
      dispatchTouch(main, "touchstart", [{ clientX: 40, clientY: 0 }]);
      dispatchTouch(main, "touchmove", [{ clientX: 40, clientY: 400 }]);
      dispatchTouch(main, "touchend");
      await vi.advanceTimersByTimeAsync(1400);
    });

    const status = container.querySelector('[role="status"]');
    expect(status.textContent).toBe("Controlla la rete");
    expect(status.textContent).not.toMatch(/fallito|icon|officialAlerts|failed|settled/i);
    expect(container.textContent).toContain("Ultimi dati disponibili");
  });

  it("asks to check the network when the device is offline even if cached data settles", async () => {
    vi.spyOn(window.navigator, "onLine", "get").mockReturnValue(false);
    const onRuntimeRefresh = vi.fn(async () => ({ status: "partial" }));

    await act(async () => root.render(
      <AppShell activeRoute="weather" activeTab="weather" copy={getUiShellCopy("it")}
        language="it" onRuntimeRefresh={onRuntimeRefresh} tabs={[]}>
        <div>Ultimi dati disponibili</div>
      </AppShell>,
    ));

    const main = container.querySelector(".mf-app-main");
    await act(async () => {
      dispatchTouch(main, "touchstart", [{ clientX: 40, clientY: 0 }]);
      dispatchTouch(main, "touchmove", [{ clientX: 40, clientY: 400 }]);
      dispatchTouch(main, "touchend");
      await vi.advanceTimersByTimeAsync(1400);
    });

    expect(container.querySelector('[role="status"]')?.textContent).toBe("Controlla la rete");
    expect(container.textContent).toContain("Ultimi dati disponibili");
  });

  it("dismisses a superseded route refresh without reporting a failure or blocking the next gesture", async () => {
    let finishRefresh;
    const onRuntimeRefresh = vi.fn(() => new Promise(resolve => { finishRefresh = resolve; }));
    await act(async () => root.render(
      <AppShell activeRoute="weather" activeTab="weather" copy={getUiShellCopy("it")}
        language="it" onRuntimeRefresh={onRuntimeRefresh} tabs={[]}>
        <div>Previsioni</div>
      </AppShell>,
    ));
    const main = container.querySelector(".mf-app-main");
    const pull = () => {
      dispatchTouch(main, "touchstart", [{ clientX: 40, clientY: 0 }]);
      dispatchTouch(main, "touchmove", [{ clientX: 40, clientY: 400 }]);
      dispatchTouch(main, "touchend");
    };
    await act(async () => pull());
    expect(container.querySelector(".mf-pull-refresh").classList).toContain("is-refreshing");
    await act(async () => {
      finishRefresh({ status: "superseded" });
      await vi.advanceTimersByTimeAsync(1);
    });
    expect(container.querySelector(".mf-pull-refresh").classList).toContain("is-idle");
    expect(container.querySelector('[role="status"]')).toBeNull();
    await act(async () => pull());
    expect(onRuntimeRefresh).toHaveBeenCalledTimes(2);
  });

  it("dismisses a skipped overlapping refresh without showing a false error", async () => {
    const onRuntimeRefresh = vi.fn(async () => ({ status: "skipped" }));
    await act(async () => root.render(
      <AppShell activeRoute="weather" activeTab="weather" copy={getUiShellCopy("it")}
        language="it" onRuntimeRefresh={onRuntimeRefresh} tabs={[]}>
        <div>Previsioni</div>
      </AppShell>,
    ));

    const main = container.querySelector(".mf-app-main");
    await act(async () => {
      dispatchTouch(main, "touchstart", [{ clientX: 40, clientY: 0 }]);
      dispatchTouch(main, "touchmove", [{ clientX: 40, clientY: 400 }]);
      dispatchTouch(main, "touchend");
      await vi.advanceTimersByTimeAsync(1);
    });

    expect(onRuntimeRefresh).toHaveBeenCalledOnce();
    expect(container.querySelector(".mf-pull-refresh")?.classList).toContain("is-idle");
    expect(container.querySelector('[role="status"]')).toBeNull();
  });

  it("leaves downward Leaflet gestures to the map instead of refreshing the page", async () => {
    const onRuntimeRefresh = vi.fn(async () => ({ status: "settled" }));

    await act(async () => {
      root.render(
        <AppShell
          activeRoute="weather"
          activeTab="weather"
          copy={getUiShellCopy("it")}
          language="it"
          onRuntimeRefresh={onRuntimeRefresh}
          tabs={[]}
        >
          <div className="leaflet-container">
            <div className="leaflet-tile">Mappa interattiva</div>
          </div>
        </AppShell>,
      );
    });

    const mapTile = container.querySelector(".leaflet-tile");
    await act(async () => {
      dispatchTouch(mapTile, "touchstart", [{ clientX: 120, clientY: 120 }]);
      dispatchTouch(mapTile, "touchmove", [{ clientX: 120, clientY: 440 }]);
      dispatchTouch(mapTile, "touchend");
      await vi.advanceTimersByTimeAsync(3000);
    });

    expect(onRuntimeRefresh).not.toHaveBeenCalled();
    expect(container.querySelector(".mf-pull-refresh")?.classList.contains("is-idle")).toBe(true);
  });
});
