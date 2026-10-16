import { afterEach, describe, expect, it, vi } from "vitest";

import { createPilotBackNavigation } from "./pilotBackNavigation";

const ANDROID = { isNativePlatform: () => true, getPlatform: () => "android" };

function setup(overrides = {}) {
  let back;
  const remove = vi.fn(async () => {});
  const app = { addListener: vi.fn(async (event, callback) => {
    expect(event).toBe("backButton");
    back = callback;
    return { remove };
  }) };
  const history = { back: vi.fn() };
  const controller = createPilotBackNavigation({
    app, capacitor: ANDROID, enabled: true, history: () => history, ...overrides,
  });
  return { app, controller, history, press: (event) => back(event), remove };
}

describe("Android Back ownership", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it.each([
    ["non-definitive build", { enabled: false }],
    ["browser", { capacitor: { isNativePlatform: () => false, getPlatform: () => "web" } }],
    ["iOS", { capacitor: { isNativePlatform: () => true, getPlatform: () => "ios" } }],
  ])("never registers or changes Back in %s", async (_name, options) => {
    const { controller, app } = setup(options);
    controller.registerOverlay(vi.fn());
    controller.setPageHandler(vi.fn());
    await controller.whenSettled();
    expect(app.addListener).not.toHaveBeenCalled();
  });

  it("registers the native listener by default in the official definitive Android app", async () => {
    vi.stubEnv("VITE_DEFINITIVE_APP_EXPERIENCE", "1");
    vi.stubEnv("VITE_OFFICIAL_APP_RELEASE", "1");
    vi.stubEnv("VITE_LOCAL_WEATHER_PILOT", "0");
    vi.stubEnv("VITE_ANDROID_LOCAL_WEATHER_PILOT", "0");

    let back;
    const page = vi.fn();
    const app = { addListener: vi.fn(async (event, callback) => {
      expect(event).toBe("backButton");
      back = callback;
      return { remove: vi.fn(async () => {}) };
    }) };
    const controller = createPilotBackNavigation({
      app,
      capacitor: ANDROID,
      history: () => ({ back: vi.fn() }),
    });

    controller.setPageHandler(page);
    await controller.whenSettled();
    back({ canGoBack: false });

    expect(app.addListener).toHaveBeenCalledOnce();
    expect(page).toHaveBeenCalledOnce();
  });

  it("leaves Home without overlays to the native default", async () => {
    const { controller, app } = setup();
    controller.setPageHandler(null);
    await controller.whenSettled();
    expect(app.addListener).not.toHaveBeenCalled();
  });

  it("closes the top overlay, then its parent, then the page, one press at a time", async () => {
    const { controller, app, press, remove } = setup();
    const page = vi.fn();
    const clearPage = controller.setPageHandler(page);
    const parent = vi.fn(() => clearParent());
    const clearParent = controller.registerOverlay(parent);
    const child = vi.fn(() => clearChild());
    const clearChild = controller.registerOverlay(child);
    await controller.whenSettled();
    expect(app.addListener).toHaveBeenCalledTimes(1);

    press();
    expect(child).toHaveBeenCalledTimes(1);
    expect(parent).not.toHaveBeenCalled();
    expect(page).not.toHaveBeenCalled();
    press();
    expect(parent).toHaveBeenCalledTimes(1);
    expect(page).not.toHaveBeenCalled();
    press();
    expect(page).toHaveBeenCalledTimes(1);
    clearPage();
    await controller.whenSettled();
    expect(remove).toHaveBeenCalledTimes(1);
  });

  it("consumes a busy overlay press even when closing returns false", async () => {
    const { controller, press, history } = setup();
    const page = vi.fn();
    controller.setPageHandler(page);
    const busy = vi.fn(() => false);
    controller.registerOverlay(busy);
    await controller.whenSettled();
    press({ canGoBack: true });
    expect(busy).toHaveBeenCalledTimes(1);
    expect(page).not.toHaveBeenCalled();
    expect(history.back).not.toHaveBeenCalled();
  });

  it("ignores a no-longer-open overlay and retains the current page handler", async () => {
    const { controller, press } = setup();
    const obsolete = vi.fn();
    const page = vi.fn();
    controller.registerOverlay(obsolete, { isActive: () => false });
    controller.setPageHandler(page);
    await controller.whenSettled();
    press();
    expect(obsolete).not.toHaveBeenCalled();
    expect(page).toHaveBeenCalledTimes(1);
  });

  it("does not clear a newer page handler with a previous effect cleanup", async () => {
    const { controller, press, app } = setup();
    const oldPage = vi.fn();
    const newPage = vi.fn();
    const oldCleanup = controller.setPageHandler(oldPage);
    controller.setPageHandler(newPage);
    oldCleanup();
    oldCleanup();
    await controller.whenSettled();
    press();
    expect(oldPage).not.toHaveBeenCalled();
    expect(newPage).toHaveBeenCalledTimes(1);
    expect(app.addListener).toHaveBeenCalledTimes(1);
  });

  it("removes an asynchronously registered listener when the overlay has already closed", async () => {
    let resolveRegistration;
    const remove = vi.fn(async () => {});
    const app = { addListener: vi.fn(() => new Promise(resolve => { resolveRegistration = resolve; })) };
    const { controller } = setup({ app });
    const stop = controller.registerOverlay(vi.fn());
    await vi.waitFor(() => expect(app.addListener).toHaveBeenCalledOnce());
    stop();
    stop();
    resolveRegistration({ remove });
    await controller.whenSettled();
    expect(remove).toHaveBeenCalledOnce();
  });

  it("serializes removal and reopening without accumulating listeners", async () => {
    let finishRemoval;
    const slowRemove = vi.fn(() => new Promise(resolve => { finishRemoval = resolve; }));
    const newRemove = vi.fn(async () => {});
    const app = { addListener: vi.fn()
      .mockResolvedValueOnce({ remove: slowRemove })
      .mockResolvedValueOnce({ remove: newRemove }) };
    const { controller } = setup({ app });
    const stop = controller.registerOverlay(vi.fn());
    await controller.whenSettled();
    stop();
    await vi.waitFor(() => expect(slowRemove).toHaveBeenCalledOnce());
    const stopNew = controller.registerOverlay(vi.fn());
    expect(app.addListener).toHaveBeenCalledTimes(1);
    finishRemoval();
    await controller.whenSettled();
    expect(app.addListener).toHaveBeenCalledTimes(2);
    stopNew();
    await controller.whenSettled();
    expect(newRemove).toHaveBeenCalledOnce();
  });

  it("preserves AppPlugin's history-only fallback for an event already queued during cleanup", async () => {
    const { controller, press, history } = setup();
    const stop = controller.registerOverlay(vi.fn());
    await controller.whenSettled();
    stop();
    press({ canGoBack: false });
    expect(history.back).not.toHaveBeenCalled();
    press({ canGoBack: true });
    expect(history.back).toHaveBeenCalledOnce();
    await controller.whenSettled();
  });

  it("handles registration rejection without a retry loop and retries after a new action", async () => {
    const remove = vi.fn(async () => {});
    const app = { addListener: vi.fn()
      .mockRejectedValueOnce(new Error("bridge unavailable"))
      .mockResolvedValueOnce({ remove }) };
    const { controller } = setup({ app });
    const stop = controller.registerOverlay(vi.fn());
    await controller.whenSettled();
    expect(app.addListener).toHaveBeenCalledOnce();
    stop();
    const nextStop = controller.registerOverlay(vi.fn());
    await controller.whenSettled();
    expect(app.addListener).toHaveBeenCalledTimes(2);
    nextStop();
    await controller.whenSettled();
    expect(remove).toHaveBeenCalledOnce();
  });
});
