import { beforeEach, describe, expect, it, vi } from "vitest";

const hooks = vi.hoisted(() => ({ index: 0, slots: [], pending: [], register: vi.fn() }));
vi.mock("react", () => ({
  useRef(value) {
    const index = hooks.index++;
    return hooks.slots[index] ||= { current: value };
  },
  useEffect(effect, dependencies) {
    const index = hooks.index++;
    const previous = hooks.slots[index];
    if (!previous || dependencies.some((value, i) => value !== previous.dependencies[i])) {
      hooks.pending.push(() => {
        previous?.cleanup?.();
        hooks.slots[index] = { dependencies, cleanup: effect() };
      });
    }
  },
}));
vi.mock("../services/pilotBackNavigation", () => ({ registerPilotBackHandler: hooks.register }));

import { usePilotBackHandler } from "./usePilotBackHandler";

function HookHarness(onBack, enabled) {
  hooks.index = 0;
  usePilotBackHandler(onBack, enabled);
  hooks.pending.splice(0).forEach(effect => effect());
}

describe("pilot back hook lifecycle", () => {
  beforeEach(() => {
    hooks.slots = [];
    hooks.pending = [];
    hooks.register.mockReset();
  });
  it("keeps stack position on rerender and invokes the current close action", () => {
    const first = vi.fn();
    const latest = vi.fn();
    const unregister = vi.fn();
    hooks.register.mockReturnValue(unregister);
    HookHarness(first, true);
    const dispatch = hooks.register.mock.calls[0][0];
    HookHarness(latest, true);
    expect(hooks.register).toHaveBeenCalledTimes(1);
    dispatch();
    expect(first).not.toHaveBeenCalled();
    expect(latest).toHaveBeenCalledTimes(1);
    HookHarness(latest, false);
    expect(unregister).toHaveBeenCalledTimes(1);
  });
  it("registers only while open and releases its handle on unmount", () => {
    const close = vi.fn();
    const unregister = vi.fn();
    hooks.register.mockReturnValue(unregister);
    HookHarness(close, false);
    expect(hooks.register).not.toHaveBeenCalled();
    HookHarness(close, true);
    hooks.slots.forEach(slot => slot?.cleanup?.());
    expect(unregister).toHaveBeenCalledTimes(1);
  });
});
