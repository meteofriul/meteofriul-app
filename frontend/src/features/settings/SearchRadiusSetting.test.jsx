// @vitest-environment jsdom
import { StrictMode, act, useState } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const backHandlers = vi.hoisted(() => ({ browser: null, pilot: null }));
vi.mock("../../app/useBrowserDialogBack", () => ({
  useBrowserDialogBack: (callback, enabled = true) => { backHandlers.browser = enabled ? callback : null; },
}));
vi.mock("../../app/usePilotBackHandler", () => ({
  usePilotBackHandler: (callback, enabled = true) => { backHandlers.pilot = enabled ? callback : null; },
}));

import { SearchRadiusSetting } from "./SearchRadiusSetting";

let container;
let root;
let originalShowModal;
let originalClose;
let originalOverflow;

function ControlledRadius({ initialRadius = 20, onChange }) {
  const [radius, setRadius] = useState(initialRadius);
  return <SearchRadiusSetting radius={radius} onChange={value => {
    onChange(value);
    setRadius(value);
  }} />;
}

const trigger = () => container.querySelector(".mf-settings-search-radius__trigger");
const dialog = () => container.querySelector("dialog");
const action = label => [...dialog().querySelectorAll("button")].find(button => button.textContent.trim() === label);

async function render(props = {}, controlled = false, strict = false) {
  const element = controlled
    ? <ControlledRadius {...props} />
    : <SearchRadiusSetting {...props} />;
  await act(async () => root.render(strict ? <StrictMode>{element}</StrictMode> : element));
  return trigger();
}

async function dispatch(target, type, options = {}) {
  const event = type === "keydown"
    ? new KeyboardEvent(type, { bubbles: true, cancelable: true, ...options })
    : type === "click"
      ? new MouseEvent(type, { bubbles: true, cancelable: true, ...options })
      : new Event(type, { bubbles: true, cancelable: true, ...options });
  await act(async () => target.dispatchEvent(event));
  return event;
}

async function open() {
  trigger().focus();
  await dispatch(trigger(), "click");
  expect(dialog()?.open).toBe(true);
  return container.querySelector('[role="spinbutton"]');
}

async function confirm(label = "Conferma") {
  await dispatch(action(label), "click");
}

async function scroll(wheel, top) {
  wheel.scrollTop = top;
  await dispatch(wheel, "scroll");
}

async function advance(milliseconds) {
  await act(async () => vi.advanceTimersByTime(milliseconds));
}

beforeEach(() => {
  vi.useFakeTimers();
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  backHandlers.browser = null;
  backHandlers.pilot = null;
  originalShowModal = Object.getOwnPropertyDescriptor(HTMLDialogElement.prototype, "showModal");
  originalClose = Object.getOwnPropertyDescriptor(HTMLDialogElement.prototype, "close");
  Object.defineProperty(HTMLDialogElement.prototype, "showModal", {
    configurable: true, value: vi.fn(function () { this.open = true; }),
  });
  Object.defineProperty(HTMLDialogElement.prototype, "close", {
    configurable: true, value: vi.fn(function () { this.open = false; }),
  });
  originalOverflow = document.body.style.overflow;
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(async () => {
  if (root) await act(async () => root.unmount());
  container.remove();
  if (originalShowModal) Object.defineProperty(HTMLDialogElement.prototype, "showModal", originalShowModal);
  else delete HTMLDialogElement.prototype.showModal;
  if (originalClose) Object.defineProperty(HTMLDialogElement.prototype, "close", originalClose);
  else delete HTMLDialogElement.prototype.close;
  document.body.style.overflow = originalOverflow;
  vi.restoreAllMocks();
  vi.useRealTimers();
  delete globalThis.IS_REACT_ACT_ENVIRONMENT;
});

describe("confirmed search radius editor", () => {
  it.each([
    ["it", "Raggio di ricerca", "Raggio di ricerca eventi", "Annulla", "Conferma"],
    ["fur", "Rai di ricercje", "Rai di ricercje dai events", "Anule", "Conferme"],
  ])("exposes a localized trigger and accessible dialog/wheel in %s", async (language, title, dialogTitle, cancelLabel, confirmLabel) => {
    await render({ language, radius: 25 });
    expect(trigger().tagName).toBe("BUTTON");
    expect(trigger().getAttribute("aria-label")).toBe(`${title}: 25 km`);
    expect(trigger().getAttribute("aria-haspopup")).toBe("dialog");
    expect(container.querySelector('[role="spinbutton"]')).toBeNull();
    const wheel = await open();
    expect(wheel.tabIndex).toBe(0);
    expect(wheel.getAttribute("aria-valuemin")).toBe("5");
    expect(wheel.getAttribute("aria-valuemax")).toBe("50");
    expect(wheel.getAttribute("aria-valuenow")).toBe("25");
    expect(document.getElementById(dialog().getAttribute("aria-labelledby"))?.textContent).toBe(dialogTitle);
    const label = document.getElementById(wheel.getAttribute("aria-labelledby"));
    expect(label?.textContent).toBe(dialogTitle);
    expect(action(cancelLabel)).toBeDefined();
    expect(action(confirmLabel)).toBeDefined();
    expect(wheel.scrollTop).toBe(96);
  });

  it("cannot change the saved radius by scrolling or pressing arrows while closed", async () => {
    const onChange = vi.fn();
    await render({ onChange }, true);
    await dispatch(trigger(), "wheel");
    await dispatch(trigger(), "scroll");
    await dispatch(trigger(), "touchstart");
    await dispatch(trigger(), "touchend");
    await dispatch(trigger(), "keydown", { key: "ArrowUp" });
    await advance(500);
    expect(onChange).not.toHaveBeenCalled();
    expect(trigger().getAttribute("aria-label")).toBe("Raggio di ricerca: 20 km");
    expect(container.querySelector('[role="spinbutton"]')).toBeNull();
  });

  it("normalizes invalid input before exposing or positioning the draft", async () => {
    await render({ radius: 7 });
    expect(trigger().getAttribute("aria-label")).toBe("Raggio di ricerca: 20 km");
    const wheel = await open();
    expect(wheel.getAttribute("aria-valuenow")).toBe("20");
    expect(wheel.scrollTop).toBe(72);
  });

  it("keeps keyboard edits bounded and saves only the confirmed draft once", async () => {
    const onChange = vi.fn();
    await render({ onChange }, true);
    const wheel = await open();
    expect((await dispatch(wheel, "keydown", { key: "ArrowUp" })).defaultPrevented).toBe(true);
    expect(wheel.getAttribute("aria-valuenow")).toBe("25");
    await dispatch(wheel, "keydown", { key: "ArrowDown" });
    expect(wheel.getAttribute("aria-valuenow")).toBe("20");
    await dispatch(wheel, "keydown", { key: "Home" });
    await dispatch(wheel, "keydown", { key: "ArrowDown" });
    expect(wheel.getAttribute("aria-valuenow")).toBe("5");
    await dispatch(wheel, "keydown", { key: "End" });
    await dispatch(wheel, "keydown", { key: "ArrowUp" });
    expect(wheel.getAttribute("aria-valuenow")).toBe("50");
    const ignoredKey = await dispatch(wheel, "keydown", { key: "Tab" });
    expect(ignoredKey.defaultPrevented).toBe(false);
    expect(onChange).not.toHaveBeenCalled();
    expect(trigger().getAttribute("aria-label")).toBe("Raggio di ricerca: 20 km");
    await confirm();
    await advance(500);
    expect(onChange).toHaveBeenCalledExactlyOnceWith(50);
    expect(dialog()).toBeNull();
    expect(trigger().getAttribute("aria-label")).toBe("Raggio di ricerca: 50 km");
  });

  it("does not emit a change when confirming the already saved value", async () => {
    const onChange = vi.fn();
    await render({ onChange }, true);
    await open();
    await confirm();
    expect(onChange).not.toHaveBeenCalled();
    expect(dialog()).toBeNull();
  });

  it("clicks a number into the draft without persisting it until confirmation", async () => {
    const onChange = vi.fn();
    await render({ onChange }, true);
    const wheel = await open();
    const number = [...wheel.querySelectorAll("[data-radius-index]")].find(element => element.textContent.trim() === "35");
    await dispatch(number, "click");
    await dispatch(number, "click");
    await advance(500);
    expect(onChange).not.toHaveBeenCalled();
    expect(wheel.getAttribute("aria-valuenow")).toBe("35");
    await confirm();
    expect(onChange).toHaveBeenCalledExactlyOnceWith(35);
  });

  it("debounces the draft after scrolling and leaves the saved radius unchanged", async () => {
    const onChange = vi.fn();
    await render({ onChange }, true);
    const wheel = await open();
    await scroll(wheel, 120);
    await advance(100);
    await scroll(wheel, 178);
    await advance(159);
    expect(wheel.getAttribute("aria-valuenow")).toBe("20");
    await advance(1);
    expect(wheel.getAttribute("aria-valuenow")).toBe("40");
    expect(wheel.scrollTop).toBe(168);
    await dispatch(wheel, "scroll");
    await advance(160);
    expect(onChange).not.toHaveBeenCalled();
    await confirm();
    expect(onChange).toHaveBeenCalledExactlyOnceWith(40);
  });

  it("uses measured item height when rounding the draft scroll position", async () => {
    vi.spyOn(HTMLElement.prototype, "offsetHeight", "get").mockReturnValue(30);
    const onChange = vi.fn();
    await render({ onChange }, true);
    const wheel = await open();
    expect(wheel.scrollTop).toBe(90);
    await scroll(wheel, 130);
    await advance(160);
    expect(wheel.getAttribute("aria-valuenow")).toBe("25");
    expect(wheel.scrollTop).toBe(120);
    expect(onChange).not.toHaveBeenCalled();
    await confirm();
    expect(onChange).toHaveBeenCalledExactlyOnceWith(25);
  });

  it("keeps scroll overshoot within bounds before confirmation", async () => {
    const onChange = vi.fn();
    await render({ onChange }, true);
    const wheel = await open();
    await scroll(wheel, -40);
    await advance(160);
    expect(wheel.getAttribute("aria-valuenow")).toBe("5");
    await scroll(wheel, 1000);
    await advance(160);
    expect(wheel.getAttribute("aria-valuenow")).toBe("50");
    expect(onChange).not.toHaveBeenCalled();
  });

  it.each(["touchend", "touchcancel"])("settles touch into a draft after %s without saving", async endEvent => {
    const onChange = vi.fn();
    await render({ onChange }, true);
    const wheel = await open();
    await dispatch(wheel, "touchstart");
    await scroll(wheel, 168);
    await advance(1000);
    expect(wheel.getAttribute("aria-valuenow")).toBe("20");
    await dispatch(wheel, endEvent);
    await advance(160);
    expect(wheel.getAttribute("aria-valuenow")).toBe("40");
    expect(onChange).not.toHaveBeenCalled();
    await confirm();
    expect(onChange).toHaveBeenCalledExactlyOnceWith(40);
  });

  it("does not save on blur and confirms the pending scroll directly", async () => {
    const onChange = vi.fn();
    await render({ onChange }, true);
    const wheel = await open();
    await scroll(wheel, 96);
    await dispatch(wheel, "focusout");
    expect(onChange).not.toHaveBeenCalled();
    await confirm();
    await advance(500);
    expect(onChange).toHaveBeenCalledExactlyOnceWith(25);
  });

  it("opens at the saved value through StrictMode modal setup and focus cleanup", async () => {
    HTMLDialogElement.prototype.showModal.mockImplementation(function () {
      this.open = true;
      this.querySelector('[role="spinbutton"]')?.focus();
    });
    const onChange = vi.fn();
    await render({ onChange }, true, true);
    const wheel = await open();
    await advance(500);
    expect(wheel.getAttribute("aria-valuenow")).toBe("20");
    expect(wheel.scrollTop).toBe(72);
    expect(onChange).not.toHaveBeenCalled();
    await dispatch(wheel, "keydown", { key: "ArrowUp" });
    expect(wheel.getAttribute("aria-valuenow")).toBe("25");
    expect(onChange).not.toHaveBeenCalled();
  });

  it("confirms the current scroll position before the debounce settles", async () => {
    const onChange = vi.fn();
    await render({ onChange }, true);
    const wheel = await open();
    await scroll(wheel, 178);
    expect(wheel.getAttribute("aria-valuenow")).toBe("20");
    await confirm();
    await advance(500);
    expect(onChange).toHaveBeenCalledExactlyOnceWith(40);
    expect(trigger().getAttribute("aria-label")).toBe("Raggio di ricerca: 40 km");
  });

  it.each(["cancel", "escape", "browser back", "pilot back", "backdrop"])("discards edits on %s and restores focus and body scrolling", async closeMethod => {
    const onChange = vi.fn();
    document.body.style.overflow = "clip";
    await render({ onChange }, true);
    const opener = trigger();
    const wheel = await open();
    expect(document.body.style.overflow).toBe("hidden");
    await scroll(wheel, 168);
    await advance(160);
    expect(wheel.getAttribute("aria-valuenow")).toBe("40");
    if (closeMethod === "cancel") await dispatch(action("Annulla"), "click");
    if (closeMethod === "escape") await dispatch(dialog(), "cancel");
    if (closeMethod === "browser back") await act(async () => backHandlers.browser());
    if (closeMethod === "pilot back") await act(async () => backHandlers.pilot());
    if (closeMethod === "backdrop") await dispatch(dialog(), "click", { clientX: -1, clientY: -1 });
    await advance(500);
    expect(dialog()).toBeNull();
    expect(onChange).not.toHaveBeenCalled();
    expect(document.body.style.overflow).toBe("clip");
    expect(document.activeElement).toBe(opener);
    const reopened = await open();
    expect(reopened.getAttribute("aria-valuenow")).toBe("20");
    expect(reopened.scrollTop).toBe(72);
  });

  it("does not dismiss the dialog when its content or inner whitespace is clicked", async () => {
    const onChange = vi.fn();
    await render({ onChange });
    await open();
    const modal = dialog();
    vi.spyOn(modal, "getBoundingClientRect").mockReturnValue({ left: 10, right: 210, top: 10, bottom: 230 });
    await dispatch(modal, "click", { clientX: 50, clientY: 50 });
    expect(dialog()).toBe(modal);
    await dispatch(modal.querySelector("h2"), "click", { clientX: 50, clientY: 50 });
    expect(dialog()).toBe(modal);
    expect(onChange).not.toHaveBeenCalled();
  });

  it("reopens at the newly confirmed value and restores focus on confirmation", async () => {
    const onChange = vi.fn();
    await render({ onChange }, true);
    const opener = trigger();
    const wheel = await open();
    await dispatch(wheel, "keydown", { key: "Home" });
    await confirm();
    await advance(20);
    expect(document.activeElement).toBe(opener);
    const reopened = await open();
    expect(reopened.getAttribute("aria-valuenow")).toBe("5");
    expect(reopened.scrollTop).toBe(0);
    expect(onChange).toHaveBeenCalledExactlyOnceWith(5);
  });

  it("replaces obsolete pending edits when the saved radius changes externally", async () => {
    const onChange = vi.fn();
    await render({ radius: 20, onChange });
    const oldWheel = await open();
    await scroll(oldWheel, 216);
    await advance(100);
    await render({ radius: 10, onChange });
    const currentWheel = container.querySelector('[role="spinbutton"]');
    expect(currentWheel.getAttribute("aria-valuenow")).toBe("10");
    expect(currentWheel.scrollTop).toBe(24);
    await advance(500);
    expect(onChange).not.toHaveBeenCalled();
    await confirm();
    expect(onChange).not.toHaveBeenCalled();
  });

  it("does not recover stale touch edits after an external radius update", async () => {
    const onChange = vi.fn();
    await render({ radius: 20, onChange });
    const oldWheel = await open();
    await dispatch(oldWheel, "touchstart");
    await scroll(oldWheel, 216);
    await render({ radius: 10, onChange });
    const currentWheel = container.querySelector('[role="spinbutton"]');
    await dispatch(currentWheel, "touchend");
    await advance(500);
    expect(currentWheel.getAttribute("aria-valuenow")).toBe("10");
    expect(currentWheel.scrollTop).toBe(24);
    await confirm();
    expect(onChange).not.toHaveBeenCalled();
  });

  it("cleans up pending work, the modal and body lock on unmount without saving", async () => {
    const onChange = vi.fn();
    document.body.style.overflow = "clip";
    await render({ onChange });
    const wheel = await open();
    const modal = dialog();
    const schedule = vi.spyOn(window, "setTimeout");
    const cancel = vi.spyOn(window, "clearTimeout");
    await scroll(wheel, 144);
    const pendingCall = schedule.mock.calls.findIndex(([, delay]) => delay === 160);
    expect(pendingCall).toBeGreaterThanOrEqual(0);
    const pendingSelection = schedule.mock.results[pendingCall].value;
    await act(async () => root.unmount());
    root = null;
    expect(cancel).toHaveBeenCalledWith(pendingSelection);
    await advance(500);
    expect(onChange).not.toHaveBeenCalled();
    expect(modal.open).toBe(false);
    expect(document.body.style.overflow).toBe("clip");
  });
});
