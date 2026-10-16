// @vitest-environment jsdom

import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const backHarness = vi.hoisted(() => ({ register: vi.fn() }));
vi.mock("../../services/pilotBackNavigation", () => ({
  registerPilotBackHandler: backHarness.register,
}));

import { getLiveViewCopy } from "../../copy/liveViewCopy";
import { WebcamImageViewerDialog } from "./WebcamImageViewerDialog";

const camera = {
  mediaType: "snapshot",
  name: "Lignano Sabbiadoro - Punta Faro",
};

function dispatchPointer(target, type, properties) {
  const event = new Event(type, { bubbles: true, cancelable: true });
  Object.entries(properties).forEach(([key, value]) => {
    Object.defineProperty(event, key, { configurable: true, value });
  });
  target.dispatchEvent(event);
}

describe("WebcamImageViewerDialog", () => {
  let appRoot;
  let container;
  let copy;
  let originalCancelAnimationFrame;
  let originalRequestAnimationFrame;
  let root;
  let trigger;
  let unregister;

  beforeEach(() => {
    globalThis.IS_REACT_ACT_ENVIRONMENT = true;
    copy = getLiveViewCopy("it");
    appRoot = document.createElement("div");
    appRoot.id = "root";
    trigger = document.createElement("button");
    trigger.textContent = "Apri immagine";
    container = document.createElement("div");
    appRoot.append(trigger, container);
    document.body.append(appRoot);
    root = createRoot(container);
    unregister = vi.fn();
    backHarness.register.mockReset();
    backHarness.register.mockReturnValue(unregister);
    originalRequestAnimationFrame = globalThis.requestAnimationFrame;
    originalCancelAnimationFrame = globalThis.cancelAnimationFrame;
    globalThis.requestAnimationFrame = (callback) => {
      callback();
      return 1;
    };
    globalThis.cancelAnimationFrame = vi.fn();
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    appRoot.remove();
    document.querySelectorAll(".mf-live-webcam-image-viewer-layer").forEach((node) => node.remove());
    document.documentElement.classList.remove("mf-webcam-player-open");
    if (originalRequestAnimationFrame) globalThis.requestAnimationFrame = originalRequestAnimationFrame;
    else delete globalThis.requestAnimationFrame;
    if (originalCancelAnimationFrame) globalThis.cancelAnimationFrame = originalCancelAnimationFrame;
    else delete globalThis.cancelAnimationFrame;
    delete globalThis.IS_REACT_ACT_ENVIRONMENT;
  });

  async function renderViewer(onClose = vi.fn()) {
    await act(async () => {
      root.render(
        <WebcamImageViewerDialog
          camera={camera}
          copy={copy}
          imageUrl="https://example.test/punta-faro.jpg"
          onClose={onClose}
        />,
      );
    });
    return onClose;
  }

  it("portals a labelled modal, isolates the app, traps focus, and restores it", async () => {
    trigger.focus();
    await renderViewer();

    const dialog = document.body.querySelector(".mf-live-webcam-image-viewer");
    const closeButton = document.body.querySelector(`[aria-label="${copy.webcamImageViewerClose}"]`);
    const zoomInButton = document.body.querySelector(`[aria-label="${copy.webcamImageZoomIn}"]`);

    expect(dialog).not.toBeNull();
    expect(container.querySelector("[role='dialog']")).toBeNull();
    expect(dialog.getAttribute("aria-modal")).toBe("true");
    expect(dialog.getAttribute("aria-labelledby")).toBeTruthy();
    expect(document.getElementById(dialog.getAttribute("aria-labelledby")).textContent).toBe(camera.name);
    expect(document.activeElement).toBe(dialog);
    expect(appRoot.inert).toBe(true);
    expect(appRoot.getAttribute("aria-hidden")).toBe("true");
    expect(document.documentElement.classList.contains("mf-webcam-player-open")).toBe(true);

    await act(async () => {
      document.dispatchEvent(new KeyboardEvent("keydown", { bubbles: true, key: "Tab" }));
    });
    expect(document.activeElement).toBe(closeButton);

    zoomInButton.focus();
    await act(async () => {
      document.dispatchEvent(new KeyboardEvent("keydown", { bubbles: true, key: "Tab" }));
    });
    expect(document.activeElement).toBe(closeButton);

    await act(async () => root.render(null));
    expect(appRoot.inert).toBe(false);
    expect(appRoot.hasAttribute("aria-hidden")).toBe(false);
    expect(document.documentElement.classList.contains("mf-webcam-player-open")).toBe(false);
    expect(document.activeElement).toBe(trigger);
    expect(unregister).toHaveBeenCalledOnce();
  });

  it("closes from Escape, the backdrop, and the registered app Back handler", async () => {
    const onClose = await renderViewer();
    const [onBack] = backHarness.register.mock.calls[0];

    await act(async () => {
      document.dispatchEvent(new KeyboardEvent("keydown", { bubbles: true, key: "Escape" }));
    });
    expect(onClose).toHaveBeenCalledTimes(1);

    await act(async () => {
      document.body.querySelector(".mf-live-webcam-image-viewer-layer__backdrop").click();
    });
    expect(onClose).toHaveBeenCalledTimes(2);

    await act(async () => onBack());
    expect(onClose).toHaveBeenCalledTimes(3);
  });

  it("offers bounded zoom, reset, wheel zoom, and pointer panning", async () => {
    await renderViewer();
    const viewport = document.body.querySelector(".mf-live-webcam-image-viewer__viewport");
    const image = document.body.querySelector(".mf-live-webcam-image-viewer__image");
    const zoomValue = document.body.querySelector(".mf-live-webcam-image-viewer__zoom-value");
    const zoomInButton = document.body.querySelector(`[aria-label="${copy.webcamImageZoomIn}"]`);
    const resetButton = document.body.querySelector(`[aria-label="${copy.webcamImageZoomReset}"]`);

    expect(viewport.style.touchAction).toBe("none");
    expect(image.getAttribute("draggable")).toBe("false");
    expect(zoomValue.textContent.trim()).toBe("100%");
    expect(resetButton.disabled).toBe(true);

    await act(async () => zoomInButton.click());
    expect(zoomValue.textContent.trim()).toBe("150%");
    expect(image.style.transform).toContain("scale(1.5)");
    expect(resetButton.disabled).toBe(false);

    await act(async () => {
      dispatchPointer(viewport, "pointerdown", {
        button: 0,
        clientX: 100,
        clientY: 100,
        pointerId: 7,
        pointerType: "touch",
      });
      dispatchPointer(viewport, "pointermove", {
        clientX: 120,
        clientY: 115,
        pointerId: 7,
        pointerType: "touch",
      });
      dispatchPointer(viewport, "pointerup", {
        clientX: 120,
        clientY: 115,
        pointerId: 7,
        pointerType: "touch",
      });
    });
    expect(image.style.transform).toContain("translate3d(20px, 15px, 0)");

    await act(async () => {
      viewport.dispatchEvent(new WheelEvent("wheel", {
        bubbles: true,
        cancelable: true,
        clientX: 100,
        clientY: 100,
        deltaY: -1,
      }));
    });
    expect(zoomValue.textContent.trim()).toBe("175%");

    await act(async () => resetButton.click());
    expect(zoomValue.textContent.trim()).toBe("100%");
    expect(image.style.transform).toContain("translate3d(0px, 0px, 0) scale(1)");
    expect(resetButton.disabled).toBe(true);

    await act(async () => {
      dispatchPointer(viewport, "pointerdown", {
        button: 0,
        clientX: 100,
        clientY: 100,
        pointerId: 8,
        pointerType: "touch",
      });
      dispatchPointer(viewport, "pointerdown", {
        button: 0,
        clientX: 200,
        clientY: 100,
        pointerId: 9,
        pointerType: "touch",
      });
      dispatchPointer(viewport, "pointermove", {
        clientX: 250,
        clientY: 100,
        pointerId: 9,
        pointerType: "touch",
      });
      dispatchPointer(viewport, "pointercancel", {
        clientX: 100,
        clientY: 100,
        pointerId: 8,
        pointerType: "touch",
      });
      dispatchPointer(viewport, "pointercancel", {
        clientX: 250,
        clientY: 100,
        pointerId: 9,
        pointerType: "touch",
      });
    });
    expect(zoomValue.textContent.trim()).toBe("150%");
  });

  it("clamps pan to the rendered object-contain image instead of the viewport box", async () => {
    await renderViewer();
    const viewport = document.body.querySelector(".mf-live-webcam-image-viewer__viewport");
    const image = document.body.querySelector(".mf-live-webcam-image-viewer__image");
    const zoomInButton = document.body.querySelector(`[aria-label="${copy.webcamImageZoomIn}"]`);

    Object.defineProperties(viewport, {
      clientHeight: { configurable: true, value: 800 },
      clientWidth: { configurable: true, value: 400 },
    });
    Object.defineProperties(image, {
      naturalHeight: { configurable: true, value: 900 },
      naturalWidth: { configurable: true, value: 1600 },
    });

    await act(async () => {
      for (let step = 0; step < 6; step += 1) zoomInButton.click();
    });
    expect(image.style.transform).toContain("scale(4)");

    await act(async () => {
      dispatchPointer(viewport, "pointerdown", {
        button: 0,
        clientX: 100,
        clientY: 100,
        pointerId: 10,
        pointerType: "touch",
      });
      dispatchPointer(viewport, "pointermove", {
        clientX: 1000,
        clientY: 1000,
        pointerId: 10,
        pointerType: "touch",
      });
      dispatchPointer(viewport, "pointerup", {
        clientX: 1000,
        clientY: 1000,
        pointerId: 10,
        pointerType: "touch",
      });
    });

    // A 16:9 image contained in 400x800 renders at 400x225. At 4x zoom
    // its real pan limits are therefore 600px horizontally and 50px vertically.
    expect(image.style.transform).toContain("translate3d(600px, 50px, 0) scale(4)");
  });
});
