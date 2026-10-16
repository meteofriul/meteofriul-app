import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  buildWebcamSnapshotUrl,
  watchWebcamSnapshot,
  WEBCAM_SNAPSHOT_REFRESH_MS,
} from "./webcamSnapshotRefresh";

describe("webcam snapshot URL", () => {
  it("adds the request timestamp while retaining the image query and fragment", () => {
    expect(buildWebcamSnapshotUrl(
      "https://images.example.test/sacile.jpg?camera=2&quality=high#view",
      123456,
    )).toBe("https://images.example.test/sacile.jpg?camera=2&quality=high&mf_snapshot=123456#view");
  });

  it("replaces old snapshot parameters without changing other query values", () => {
    const url = new URL(buildWebcamSnapshotUrl(
      "https://images.example.test/sacile.jpg?token=a%2Bb%20c&mf_snapshot=1&mf_snapshot=2#latest",
      300001,
    ));

    expect(url.searchParams.getAll("mf_snapshot")).toEqual(["300001"]);
    expect(url.searchParams.get("token")).toBe("a+b c");
    expect(url.hash).toBe("#latest");
  });

  it.each([0, -1, NaN, Infinity, -Infinity, null, undefined, "123"])(
    "does not load an image for an invalid or unrequested timestamp: %s",
    (requestedAt) => {
      expect(buildWebcamSnapshotUrl("https://images.example.test/sacile.jpg", requestedAt)).toBe("");
    },
  );

  it.each([
    "",
    "not a URL",
    "/sacile.jpg",
    "//images.example.test/sacile.jpg",
    "http://images.example.test/sacile.jpg",
    "data:image/png;base64,example",
    "javascript:alert(1)",
    "https:images.example.test/sacile.jpg",
    "https://",
    "https://bad host/sacile.jpg",
    "https://user:password@images.example.test/sacile.jpg",
    null,
    undefined,
  ])("refuses a non-HTTPS or malformed image URL: %s", (imageUrl) => {
    expect(buildWebcamSnapshotUrl(imageUrl, 123456)).toBe("");
  });
});

describe("webcam snapshot refresh visibility", () => {
  const cleanups = [];

  function createWatcher({ visibilityState = "visible", withObserver = true } = {}) {
    const listeners = new Set();
    const documentRef = {
      visibilityState,
      addEventListener: vi.fn((type, listener) => {
        if (type === "visibilitychange") listeners.add(listener);
      }),
      removeEventListener: vi.fn((type, listener) => {
        if (type === "visibilitychange") listeners.delete(listener);
      }),
    };
    const windowRef = {
      setTimeout: vi.fn((callback, delay) => setTimeout(callback, delay)),
      clearTimeout: vi.fn((timerId) => clearTimeout(timerId)),
    };
    const element = {};
    const onRefresh = vi.fn();
    let observer;

    class FakeIntersectionObserver {
      constructor(callback) {
        this.callback = callback;
        this.observe = vi.fn();
        this.disconnect = vi.fn();
        observer = this;
      }
    }

    const cleanup = watchWebcamSnapshot({
      element,
      onRefresh,
      documentRef,
      windowRef,
      IntersectionObserverClass: withObserver ? FakeIntersectionObserver : null,
    });
    cleanups.push(cleanup);

    return {
      cleanup,
      documentRef,
      element,
      observer,
      onRefresh,
      windowRef,
      intersect(isIntersecting) {
        observer.callback([{ target: element, isIntersecting }]);
      },
      setVisibility(nextVisibility) {
        documentRef.visibilityState = nextVisibility;
        for (const listener of listeners) listener();
      },
    };
  }

  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(0);
  });

  afterEach(() => {
    for (const cleanup of cleanups.splice(0)) cleanup();
    vi.useRealTimers();
  });

  it("waits for the observed element before the first refresh, including at time zero", () => {
    const watcher = createWatcher();

    expect(WEBCAM_SNAPSHOT_REFRESH_MS).toBe(600000);
    expect(watcher.observer.observe).toHaveBeenCalledWith(watcher.element);
    expect(watcher.onRefresh).not.toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(0);

    watcher.observer.callback([{ target: {}, isIntersecting: true }]);
    watcher.intersect(false);
    expect(watcher.onRefresh).not.toHaveBeenCalled();

    watcher.intersect(true);
    watcher.intersect(true);
    watcher.setVisibility("visible");
    expect(watcher.onRefresh.mock.calls).toEqual([[0]]);
    expect(vi.getTimerCount()).toBe(1);

    vi.advanceTimersByTime(WEBCAM_SNAPSHOT_REFRESH_MS - 1);
    expect(watcher.onRefresh).toHaveBeenCalledTimes(1);
    vi.advanceTimersByTime(1);
    expect(watcher.onRefresh.mock.calls).toEqual([[0], [600000]]);
    vi.advanceTimersByTime(WEBCAM_SNAPSHOT_REFRESH_MS);
    expect(watcher.onRefresh.mock.calls).toEqual([[0], [600000], [1200000]]);
  });

  it("makes no initial offscreen requests, even after several refresh intervals", () => {
    const watcher = createWatcher();
    watcher.intersect(false);
    vi.advanceTimersByTime(WEBCAM_SNAPSHOT_REFRESH_MS * 3);

    expect(watcher.onRefresh).not.toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(0);
    watcher.intersect(true);
    expect(watcher.onRefresh.mock.calls).toEqual([[1800000]]);
  });

  it("waits for a visible document even when the element is intersecting", () => {
    const watcher = createWatcher({ visibilityState: "hidden" });
    watcher.intersect(true);
    vi.advanceTimersByTime(WEBCAM_SNAPSHOT_REFRESH_MS * 2);

    expect(watcher.onRefresh).not.toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(0);
    watcher.setVisibility("visible");
    expect(watcher.onRefresh.mock.calls).toEqual([[1200000]]);
  });

  it.each(["offscreen", "background"])(
    "cancels timers while %s and waits only the residual time on a fresh return",
    (mode) => {
      const watcher = createWatcher();
      const setActive = (active) => mode === "offscreen"
        ? watcher.intersect(active)
        : watcher.setVisibility(active ? "visible" : "hidden");

      watcher.intersect(true);
      vi.advanceTimersByTime(60000);
      setActive(false);
      expect(vi.getTimerCount()).toBe(0);
      vi.advanceTimersByTime(60000);
      setActive(true);
      expect(watcher.onRefresh.mock.calls).toEqual([[0]]);
      expect(watcher.windowRef.setTimeout).toHaveBeenLastCalledWith(expect.any(Function), 480000);

      vi.advanceTimersByTime(479999);
      expect(watcher.onRefresh).toHaveBeenCalledTimes(1);
      vi.advanceTimersByTime(1);
      expect(watcher.onRefresh.mock.calls).toEqual([[0], [600000]]);
    },
  );

  it.each(["offscreen", "background"])(
    "makes no refreshes while %s and refreshes once immediately on a stale return",
    (mode) => {
      const watcher = createWatcher();
      const setActive = (active) => mode === "offscreen"
        ? watcher.intersect(active)
        : watcher.setVisibility(active ? "visible" : "hidden");

      watcher.intersect(true);
      vi.advanceTimersByTime(60000);
      setActive(false);
      vi.advanceTimersByTime(WEBCAM_SNAPSHOT_REFRESH_MS * 3);
      expect(watcher.onRefresh.mock.calls).toEqual([[0]]);
      expect(vi.getTimerCount()).toBe(0);

      setActive(true);
      setActive(true);
      expect(watcher.onRefresh.mock.calls).toEqual([[0], [1860000]]);
      expect(vi.getTimerCount()).toBe(1);
    },
  );

  it("requires both visibility conditions when the document returns before the element", () => {
    const watcher = createWatcher();
    watcher.intersect(true);
    watcher.setVisibility("hidden");
    watcher.intersect(false);
    vi.advanceTimersByTime(WEBCAM_SNAPSHOT_REFRESH_MS);
    watcher.setVisibility("visible");

    expect(watcher.onRefresh.mock.calls).toEqual([[0]]);
    expect(vi.getTimerCount()).toBe(0);
    watcher.intersect(true);
    expect(watcher.onRefresh.mock.calls).toEqual([[0], [600000]]);
  });

  it("rechecks document visibility when a timer fires without a visibility event", () => {
    const watcher = createWatcher();
    watcher.intersect(true);
    watcher.documentRef.visibilityState = "hidden";
    vi.advanceTimersByTime(WEBCAM_SNAPSHOT_REFRESH_MS);

    expect(watcher.onRefresh.mock.calls).toEqual([[0]]);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("falls back to document visibility when IntersectionObserver is unavailable", () => {
    const watcher = createWatcher({ visibilityState: "hidden", withObserver: false });
    expect(watcher.onRefresh).not.toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(0);

    watcher.setVisibility("visible");
    expect(watcher.onRefresh.mock.calls).toEqual([[0]]);
    vi.advanceTimersByTime(WEBCAM_SNAPSHOT_REFRESH_MS);
    expect(watcher.onRefresh.mock.calls).toEqual([[0], [600000]]);
    watcher.setVisibility("hidden");
    vi.advanceTimersByTime(WEBCAM_SNAPSHOT_REFRESH_MS * 2);
    expect(watcher.onRefresh).toHaveBeenCalledTimes(2);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("cleans up timers, listeners and observers and ignores queued observer callbacks", () => {
    const watcher = createWatcher();
    watcher.intersect(true);
    const visibilityListener = watcher.documentRef.addEventListener.mock.calls[0][1];

    watcher.cleanup();
    expect(vi.getTimerCount()).toBe(0);
    expect(watcher.observer.disconnect).toHaveBeenCalledOnce();
    expect(watcher.documentRef.removeEventListener).toHaveBeenCalledWith(
      "visibilitychange",
      visibilityListener,
    );

    vi.advanceTimersByTime(WEBCAM_SNAPSHOT_REFRESH_MS * 2);
    watcher.intersect(true);
    watcher.setVisibility("visible");
    visibilityListener();
    expect(watcher.onRefresh.mock.calls).toEqual([[0]]);
    expect(vi.getTimerCount()).toBe(0);
  });

  it.each(["documentRef", "windowRef", "element"])(
    "does not observe, listen, refresh or schedule without %s during SSR",
    (missingReference) => {
      const onRefresh = vi.fn();
      const IntersectionObserverClass = vi.fn();
      const documentRef = { visibilityState: "visible", addEventListener: vi.fn() };
      const windowRef = { setTimeout: vi.fn() };
      const cleanup = watchWebcamSnapshot({
        element: {},
        documentRef,
        windowRef,
        IntersectionObserverClass,
        onRefresh,
        [missingReference]: null,
      });

      expect(() => cleanup()).not.toThrow();
      expect(onRefresh).not.toHaveBeenCalled();
      expect(IntersectionObserverClass).not.toHaveBeenCalled();
      expect(documentRef.addEventListener).not.toHaveBeenCalled();
      expect(windowRef.setTimeout).not.toHaveBeenCalled();
      expect(vi.getTimerCount()).toBe(0);
    },
  );
});
