import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const harness = vi.hoisted(() => ({
  effects: [],
  state: vi.fn(),
  ref: vi.fn(),
  register: vi.fn(),
  pilot: vi.fn(),
}));

vi.mock("react", async (importOriginal) => ({
  ...await importOriginal(),
  useEffect: (effect, deps) => harness.effects.push({ effect, deps }),
  useState: harness.state,
  useRef: harness.ref,
}));
vi.mock("../../services/pilotBackNavigation", () => ({ registerPilotBackHandler: harness.register }));
vi.mock("../../services/localWeatherPilot", () => ({
  isDefinitiveAppExperience: harness.pilot,
  isLocalWeatherPilot: harness.pilot,
}));

import { PilotHourlyForecast, WeatherHourlyForecast } from "./WeatherHourlyForecast";

const item = { timestamp: "2026-09-07T19:00:00Z", dateKey: "2026-09-07", time: "21:00", temperature: "26°" };
const model = { title: "Prossime 48 ore", items: [item], groups: [{ dateKey: item.dateKey, label: "Oggi" }] };

beforeEach(() => {
  vi.clearAllMocks();
  harness.effects.length = 0;
  vi.stubGlobal("document", { body: { style: { overflow: "auto" } } });
});
afterEach(() => vi.unstubAllGlobals());

function prepare({ open = false } = {}) {
  const select = vi.fn();
  const dialog = { open: false, showModal: vi.fn(() => { dialog.open = true; }) };
  const opener = { focus: vi.fn() };
  const unregister = vi.fn();
  harness.state.mockReturnValueOnce([null, vi.fn()])
    .mockReturnValueOnce([open ? item.timestamp : null, select])
    .mockReturnValueOnce([null, vi.fn()]);
  harness.ref.mockReturnValueOnce({ current: dialog })
    .mockReturnValueOnce({ current: opener })
    .mockReturnValueOnce({ current: null });
  harness.register.mockReturnValue(unregister);
  return { select, dialog, opener, unregister };
}

describe("pilot hourly dialog native Back integration", () => {
  it("owns Back only while open and cleans up focus, scrolling and registration", () => {
    const { select, dialog, opener, unregister } = prepare({ open: true });
    PilotHourlyForecast({ model });
    const cleanup = harness.effects[0].effect();
    expect(harness.effects[0].deps).toEqual([true]);
    expect(dialog.showModal).toHaveBeenCalledOnce();
    expect(document.body.style.overflow).toBe("hidden");
    const [onBack, options] = harness.register.mock.calls[0];
    expect(options.isActive()).toBe(true);
    onBack();
    expect(select).toHaveBeenCalledWith(null);
    dialog.open = false;
    expect(options.isActive()).toBe(false);
    cleanup();
    expect(unregister).toHaveBeenCalledOnce();
    expect(document.body.style.overflow).toBe("auto");
    expect(opener.focus).toHaveBeenCalledOnce();
  });

  it("registers nothing when no hour is selected", () => {
    const { dialog } = prepare();
    PilotHourlyForecast({ model });
    expect(harness.effects[0].effect()).toBeUndefined();
    expect(harness.register).not.toHaveBeenCalled();
    expect(dialog.showModal).not.toHaveBeenCalled();
  });

  it("keeps beta on its unchanged legacy component", () => {
    harness.pilot.mockReturnValue(false);
    const rendered = WeatherHourlyForecast({ model });
    expect(rendered.type.name).toBe("LegacyHourlyForecast");
    expect(harness.register).not.toHaveBeenCalled();
    expect(harness.effects).toHaveLength(0);
  });
});
