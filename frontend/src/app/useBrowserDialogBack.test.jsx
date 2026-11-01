// @vitest-environment jsdom
import { StrictMode, act, useState } from "react";
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
function NestedDialogs({ onParentClose, onChildClose }) {
  const [childOpen, setChildOpen] = useState(false);
  useBrowserDialogBack(onParentClose);
  return <section data-parent-dialog>
    <button data-open-child onClick={() => setChildOpen(true)}>Open child</button>
    {childOpen ? <Dialog onClose={() => {
      onChildClose();
      setChildOpen(false);
    }} /> : null}
  </section>;
}
const childCloseButton = () => [...host.querySelectorAll("button")].find(button => button.textContent === "Close");
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

  it.each(["manual", "back"])("closes only the child on %s, then Back closes its parent", async closeMethod => {
    const parentClose = vi.fn(() => root.render(null));
    const childClose = vi.fn();
    const push = vi.spyOn(window.history, "pushState");
    await act(async () => root.render(<StrictMode><NestedDialogs onParentClose={parentClose} onChildClose={childClose} /></StrictMode>));
    const parentEntry = window.history.state[ENTRY];
    expect(parentEntry).toBeTruthy();
    expect(push).toHaveBeenCalledTimes(1);
    await act(async () => host.querySelector("[data-open-child]").click());
    expect(window.history.state[ENTRY]).not.toBe(parentEntry);
    expect(push).toHaveBeenCalledTimes(2);
    if (closeMethod === "manual") await act(async () => childCloseButton().click());
    else await back();
    await act(async () => vi.waitFor(() => expect(window.history.state[ENTRY]).toBe(parentEntry)));
    expect(childClose).toHaveBeenCalledTimes(1);
    expect(parentClose).not.toHaveBeenCalled();
    expect(host.querySelector("[data-parent-dialog]")).not.toBeNull();
    expect(childCloseButton()).toBeUndefined();
    expect(window.location.search).toBe("?tab=events");
    await back();
    expect(parentClose).toHaveBeenCalledTimes(1);
    expect(window.history.state).toEqual({ route: "events", unrelated: 42 });
  });

  it("reopens a nested child during the close traversal without losing its parent's entry", async () => {
    const parentClose = vi.fn(() => root.render(null));
    const childClose = vi.fn();
    await act(async () => root.render(<StrictMode><NestedDialogs onParentClose={parentClose} onChildClose={childClose} /></StrictMode>));
    const parentEntry = window.history.state[ENTRY];
    await act(async () => host.querySelector("[data-open-child]").click());
    const firstChildEntry = window.history.state[ENTRY];
    await act(async () => childCloseButton().click());
    await act(async () => host.querySelector("[data-open-child]").click());
    await act(async () => vi.waitFor(() => {
      expect(window.history.state[ENTRY]).toBeTruthy();
      expect(window.history.state[ENTRY]).not.toBe(parentEntry);
      expect(window.history.state[ENTRY]).not.toBe(firstChildEntry);
    }));
    expect(parentClose).not.toHaveBeenCalled();
    expect(childClose).toHaveBeenCalledTimes(1);
    await back();
    expect(childClose).toHaveBeenCalledTimes(2);
    expect(parentClose).not.toHaveBeenCalled();
    expect(window.history.state[ENTRY]).toBe(parentEntry);
    await back();
    expect(parentClose).toHaveBeenCalledTimes(1);
  });
});
