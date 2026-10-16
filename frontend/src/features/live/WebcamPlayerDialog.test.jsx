import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { getLiveViewCopy } from "../../copy/liveViewCopy";
import { WebcamPlayerDialog } from "./WebcamPlayerDialog";
import { subscribeToWebcamPlayerBackgroundClose } from "./webcamPlayerLifecycle";

function createEventTarget(properties = {}) {
  const listeners = new Map();
  return {
    ...properties,
    addEventListener: vi.fn((type, listener) => {
      listeners.set(type, listener);
    }),
    emit(type) {
      listeners.get(type)?.();
    },
    removeEventListener: vi.fn((type, listener) => {
      if (listeners.get(type) === listener) listeners.delete(type);
    }),
  };
}

describe("WebcamPlayerDialog", () => {
  it("renders a labelled tap-loaded iframe with a constrained sandbox", () => {
    const copy = getLiveViewCopy("it");
    const markup = renderToStaticMarkup(
      <WebcamPlayerDialog
        camera={{
          name: "Gemona del Friuli - Duomo",
          playerUrl: "https://stream-meteoproject.eu/weathercam-player.php?code=18",
          sourceUrl: "https://www.weathercam.it/webcam/gemona",
        }}
        copy={copy}
        onClose={() => {}}
      />,
    );

    expect(markup).toContain('role="dialog"');
    expect(markup).toContain('aria-modal="true"');
    expect(markup).toContain('title="Webcam live: Gemona del Friuli - Duomo"');
    expect(markup).toContain(
      'src="https://stream-meteoproject.eu/weathercam-player.php?code=18"',
    );
    expect(markup).toContain('sandbox="allow-same-origin allow-scripts"');
    expect(markup).toContain('allow="fullscreen"');
    expect(markup).toContain('referrerPolicy="no-referrer"');
    expect(markup).not.toContain("autoplay");
    expect(markup).not.toContain("allow-forms");
    expect(markup).not.toContain("allow-popups");
    expect(markup).toContain(copy.webcamLiveExternal);
  });

  it("closes the player once when the app enters the background", () => {
    const documentRef = createEventTarget({ visibilityState: "visible" });
    const windowRef = createEventTarget();
    const onClose = vi.fn();
    const cleanup = subscribeToWebcamPlayerBackgroundClose({
      documentRef,
      onClose,
      windowRef,
    });

    documentRef.emit("visibilitychange");
    expect(onClose).not.toHaveBeenCalled();

    documentRef.visibilityState = "hidden";
    documentRef.emit("visibilitychange");
    windowRef.emit("pagehide");
    expect(onClose).toHaveBeenCalledOnce();

    cleanup();
    expect(documentRef.removeEventListener).toHaveBeenCalledWith(
      "visibilitychange",
      expect.any(Function),
    );
    expect(windowRef.removeEventListener).toHaveBeenCalledWith(
      "pagehide",
      expect.any(Function),
    );
  });

  it("also closes a visible player when its page is hidden", () => {
    const documentRef = createEventTarget({ visibilityState: "visible" });
    const windowRef = createEventTarget();
    const onClose = vi.fn();
    const cleanup = subscribeToWebcamPlayerBackgroundClose({
      documentRef,
      onClose,
      windowRef,
    });

    windowRef.emit("pagehide");
    expect(onClose).toHaveBeenCalledOnce();
    cleanup();
  });
});
