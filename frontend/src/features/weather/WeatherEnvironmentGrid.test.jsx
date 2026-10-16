// @vitest-environment jsdom

import { Sun, Wind } from "lucide-react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const backHarness = vi.hoisted(() => ({ register: vi.fn() }));
vi.mock("../../services/pilotBackNavigation", () => ({
  registerPilotBackHandler: backHarness.register,
}));

import { WeatherEnvironmentGrid } from "./WeatherEnvironmentGrid";

const items = () => [
  { id: "sky", title: "Sole e Luna", tone: "sky", icon: Sun, summary: <span>12h</span>, detail: <p>Dettaglio cielo</p> },
  { id: "air", title: "Qualità dell’aria", tone: "air", icon: Wind, summary: <span>PM2.5</span>, detail: <p>Quattro inquinanti</p> },
];

describe("WeatherEnvironmentGrid shared detail sheet", () => {
  let container;
  let root;
  let unregister;
  let showModal;
  let originalClose;
  let originalShowModal;

  beforeEach(() => {
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
    unregister = vi.fn();
    backHarness.register.mockReset();
    backHarness.register.mockReturnValue(unregister);
    globalThis.IS_REACT_ACT_ENVIRONMENT = true;
    originalShowModal = Object.getOwnPropertyDescriptor(HTMLDialogElement.prototype, "showModal");
    originalClose = Object.getOwnPropertyDescriptor(HTMLDialogElement.prototype, "close");
    showModal = vi.fn(function open() {
      this.setAttribute("open", "");
    });
    Object.defineProperty(HTMLDialogElement.prototype, "showModal", {
      configurable: true,
      value: showModal,
    });
    Object.defineProperty(HTMLDialogElement.prototype, "close", {
      configurable: true,
      value: vi.fn(function close() { this.removeAttribute("open"); }),
    });
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    container.remove();
    vi.restoreAllMocks();
    document.body.style.overflow = "";
    if (originalShowModal) Object.defineProperty(HTMLDialogElement.prototype, "showModal", originalShowModal);
    else delete HTMLDialogElement.prototype.showModal;
    if (originalClose) Object.defineProperty(HTMLDialogElement.prototype, "close", originalClose);
    else delete HTMLDialogElement.prototype.close;
    delete globalThis.IS_REACT_ACT_ENVIRONMENT;
  });

  it("uses one dialog, survives item recreation, owns Back, and restores focus and scrolling", async () => {
    await act(async () => root.render(<WeatherEnvironmentGrid items={items()} />));
    const trigger = container.querySelector(".mf-weather-environment-tile--air");
    expect(trigger.getAttribute("aria-label")).toBe("Apri i dettagli: Qualità dell’aria");
    expect(container.querySelector(".mf-weather-environment-tile__action")).toBeNull();
    trigger.focus();

    await act(async () => trigger.click());

    const dialog = container.querySelector("dialog");
    expect(dialog).not.toBeNull();
    expect(dialog.hasAttribute("open")).toBe(true);
    expect(showModal).toHaveBeenCalledOnce();
    expect(document.body.style.overflow).toBe("hidden");
    expect(container.querySelectorAll("dialog")).toHaveLength(1);
    expect(dialog.textContent).toContain("Quattro inquinanti");
    expect(dialog.textContent).toContain("Dettagli");

    const [onBack, options] = backHarness.register.mock.calls[0];
    expect(options.isActive()).toBe(true);

    await act(async () => root.render(<WeatherEnvironmentGrid items={items()} />));
    expect(showModal).toHaveBeenCalledOnce();
    expect(container.querySelector("dialog")?.hasAttribute("open")).toBe(true);

    await act(async () => onBack());
    expect(container.querySelector("dialog")).toBeNull();
    expect(document.body.style.overflow).toBe("");
    expect(unregister).toHaveBeenCalledOnce();
    expect(document.activeElement).toBe(trigger);
  });

  it("exposes the objective UV level as a visual-only data contract", async () => {
    await act(async () => root.render(<WeatherEnvironmentGrid items={[{
      detail: <p>Dettaglio UV</p>,
      icon: Sun,
      id: "uv",
      summary: <span>6</span>,
      title: "Indice UV",
      tone: "uv",
      visualTone: "high",
    }]} />));

    const uv = container.querySelector(".mf-weather-environment-tile--uv");
    expect(uv?.dataset.uvLevel).toBe("high");
    expect(uv?.getAttribute("aria-label")).toBe("Apri i dettagli: Indice UV");
  });
});
