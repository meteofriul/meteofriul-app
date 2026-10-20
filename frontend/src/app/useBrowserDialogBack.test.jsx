// @vitest-environment jsdom
import { StrictMode, act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useBrowserDialogBack } from "./useBrowserDialogBack";

const native = vi.hoisted(() => ({ enabled: false }));
vi.mock("@capacitor/core", () => ({
  Capacitor: { isNativePlatform: () => native.enabled },
}));

const ENTRY = "__mfBrowserDialog";
let root;
let host;
function Dialog({ onClose }) {
  useBrowserDialogBack(onClose);
  return <button onClick={onClose}>Close</button>;
}
async function show(onClose) {
  await act(async () => root.render(<StrictMode><Dialog onClose={onClose} /></StrictMode>));
}
async function hide() {
  await act(async () => root.render(null));
  await act(async () => vi.waitFor(() => expect(window.history.state?.[ENTRY]).toBeUndefined()));
}
async function traverse(direction) {
  await act(async () => {
    const done = new Promise(resolve => window.addEventListener("popstate", resolve, { once: true }));
    window.history[direction]();
    await done;
  });
}
async function back() { await traverse("back"); }

describe("browser dialog history", () => {
  beforeEach(() => {
    globalThis.IS_REACT_ACT_ENVIRONMENT = true;
    native.enabled = false;
    window.history.replaceState({ route: "events", unrelated: 42 }, "", "/?tab=events");
    host = document.createElement("div");
    document.body.append(host);
    root = createRoot(host);
  });
  afterEach(async () => {
    await hide();
    await act(async () => root.unmount());
    host.remove();
    vi.restoreAllMocks();
  });

  it("adds exactly one entry in StrictMode and Back closes without leaving the page", async () => {
    const push = vi.spyOn(window.history, "pushState");
    const close = vi.fn();
    await show(close);
    expect(push).toHaveBeenCalledTimes(1);
    expect(window.history.state).toMatchObject({ route: "events", unrelated: 42 });
    await back();
    expect(close).toHaveBeenCalledTimes(1);
    expect(window.history.state).toEqual({ route: "events", unrelated: 42 });
    expect(window.location.search).toBe("?tab=events");
    const historyBack = vi.spyOn(window.history, "back");
    await hide();
    expect(historyBack).not.toHaveBeenCalled();
  });

  it("removes the extra entry on manual close and permits repeated open/close cycles", async () => {
    const close = vi.fn(() => root.render(null));
    for (let i = 0; i < 3; i += 1) {
      await show(close);
      expect(window.history.state[ENTRY]).toBeTruthy();
      await act(async () => host.querySelector("button").click());
      await act(async () => vi.waitFor(() => expect(window.history.state).toEqual({ route: "events", unrelated: 42 })));
    }
    expect(close).toHaveBeenCalledTimes(3);
  });

  it("uses the latest close action without adding entries on rerender", async () => {
    const first = vi.fn();
    const latest = vi.fn();
    const push = vi.spyOn(window.history, "pushState");
    await show(first);
    await show(latest);
    expect(push).toHaveBeenCalledTimes(1);
    await back();
    expect(first).not.toHaveBeenCalled();
    expect(latest).toHaveBeenCalledTimes(1);
  });

  it("waits for a manual-close traversal before reopening", async () => {
    const close = vi.fn();
    await show(close);
    const previousEntry = window.history.state[ENTRY];
    await act(async () => root.render(null));
    await show(close);
    await act(async () => vi.waitFor(() => {
      expect(window.history.state[ENTRY]).toBeTruthy();
      expect(window.history.state[ENTRY]).not.toBe(previousEntry);
    }));
    expect(close).not.toHaveBeenCalled();
    await back();
    expect(close).toHaveBeenCalledTimes(1);
  });

  it("does not reopen on Forward and reuses a stale entry left by reload", async () => {
    const close = vi.fn();
    await show(close);
    await back();
    await hide();
    await traverse("forward");
    const push = vi.spyOn(window.history, "pushState");
    await show(close);
    expect(push).not.toHaveBeenCalled();
    await back();
    expect(close).toHaveBeenCalledTimes(2);
  });

  it("leaves native Capacitor navigation untouched", async () => {
    native.enabled = true;
    const push = vi.spyOn(window.history, "pushState");
    const historyBack = vi.spyOn(window.history, "back");
    await show(vi.fn());
    await hide();
    expect(push).not.toHaveBeenCalled();
    expect(historyBack).not.toHaveBeenCalled();
  });
});
