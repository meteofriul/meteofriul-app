// @vitest-environment jsdom

import { act } from "react";
import { createRoot } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const radarLayerMock = vi.hoisted(() => ({
  create: vi.fn(),
}));

vi.mock("../bulletin/dpcRadarLeafletLayer", () => ({
  createDpcRadarGridLayer: (...args) => radarLayerMock.create(...args),
}));

import { TerritoryRadarOverlay } from "./TerritoryRadarOverlay";

function buildModel(overrides = {}) {
  return {
    animationLabel: "Ultimi 90 minuti",
    available: true,
    copy: {
      frameUnavailable: "Fotogramma radar non disponibile",
      live: "LIVE",
      noPrecipitation: "Nessuna precipitazione rilevata",
      pause: "Metti in pausa",
      pauseButton: "Pausa",
      play: "Anima gli ultimi 90 minuti",
      hideLegend: "Nascondi la legenda radar",
      showLegend: "Mostra la legenda radar",
      timelineLabel: "Sequenza radar degli ultimi 90 minuti",
      unavailable: "Radar temporaneamente non disponibile",
      waiting: "Radar in attesa del prossimo fotogramma",
    },
    isStale: false,
    legend: {
      ariaLabel: "Scala dell'intensità della pioggia",
      labels: ["Debole", "Moderata", "Intensa", "Forte", "Molto forte"],
    },
    playLabel: "Anima gli ultimi 90 minuti",
    product: {
      periodMinutes: 5,
      productType: "SRI",
      time: "2026-08-03T07:10:00Z",
    },
    tiles: {
      baseUrl: "https://tiles.example.test",
      tileSize: 256,
    },
    title: "Radar precipitazioni",
    ...overrides,
  };
}

function createLayerHarness() {
  const listeners = new Map();
  const layer = {
    addTo: vi.fn(() => layer),
    off: vi.fn((event, listener) => {
      if (listeners.get(event) === listener) listeners.delete(event);
      return layer;
    }),
    on: vi.fn((event, listener) => {
      listeners.set(event, listener);
      return layer;
    }),
    prefetchFrame: vi.fn(() => Promise.resolve()),
    setFrame: vi.fn((product, time) => {
      layer.frameTime = time;
      listeners.get("loading")?.();
    }),
  };

  return { layer, listeners };
}

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((onResolve, onReject) => {
    resolve = onResolve;
    reject = onReject;
  });
  return { promise, resolve, reject };
}

describe("TerritoryRadarOverlay", () => {
  let container;
  let layerHarness;
  let map;
  let mapListeners;
  let root;

  beforeEach(() => {
    globalThis.IS_REACT_ACT_ENVIRONMENT = true;
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
    layerHarness = createLayerHarness();
    radarLayerMock.create.mockReset();
    radarLayerMock.create.mockImplementation((leaflet, options) => {
      layerHarness.layer.frameTime = options.time;
      return layerHarness.layer;
    });
    mapListeners = new Map();
    map = {
      createPane: vi.fn(() => ({ style: {} })),
      getPane: vi.fn(() => null),
      off: vi.fn((event, listener) => {
        if (mapListeners.get(event) === listener) mapListeners.delete(event);
      }),
      on: vi.fn((event, listener) => {
        mapListeners.set(event, listener);
      }),
      removeLayer: vi.fn(),
    };
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    container.remove();
    vi.useRealTimers();
    delete globalThis.IS_REACT_ACT_ENVIRONMENT;
  });

  async function renderRadar(overrides = {}) {
    await act(async () => root.render(
      <TerritoryRadarOverlay enabled leaflet={{}} map={map} radarModel={buildModel(overrides)} />,
    ));
  }

  async function finishFrame({ error = false, echo = true } = {}) {
    await act(async () => {
      layerHarness.listeners.get(error ? "tileerror" : "tileload")?.({
        tile: { radarFrameTime: layerHarness.layer.frameTime, radarHasEcho: echo },
      });
      layerHarness.listeners.get("load")?.();
    });
  }

  async function selectFrame(index) {
    await act(async () => {
      const range = container.querySelector('input[type="range"]');
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(range, String(index));
      range.dispatchEvent(new Event("input", { bubbles: true }));
    });
  }

  it("reserves the status and live slots throughout loading, empty, ready and error frames", async () => {
    await renderRadar();
    const statusSlot = container.querySelector(".mf-territory-radar-status--frame");
    const liveSlot = container.querySelector(".mf-territory-radar-live");
    expect(statusSlot?.getAttribute("aria-hidden")).toBe("true");
    expect(liveSlot?.textContent).toBe("");

    await finishFrame({ echo: false });
    expect(statusSlot.textContent).toContain("Nessuna precipitazione");
    expect(statusSlot.hasAttribute("aria-hidden")).toBe(false);
    expect(liveSlot.textContent).toContain("LIVE");

    await act(async () => layerHarness.listeners.get("loading")());
    expect(statusSlot.textContent).toBe("");
    expect(liveSlot.textContent).toBe("");
    await finishFrame({ error: true });
    expect(statusSlot.textContent).toContain("Fotogramma radar non disponibile");
    expect(container.querySelector(".mf-territory-radar-status--frame")).toBe(statusSlot);
    expect(container.querySelector(".mf-territory-radar-live")).toBe(liveSlot);
  });

  it("keeps the previous image timestamp while preparing a frame and on preparation failure", async () => {
    await renderRadar();
    await finishFrame();
    const pending = deferred();
    layerHarness.layer.prefetchFrame.mockReturnValue(pending.promise);
    await selectFrame(0);

    await finishFrame(); // The previous layer completes again while the next is pending.
    expect(container.querySelector(".mf-territory-radar-overlay").getAttribute("aria-busy")).toBe("true");
    expect(container.querySelector(".mf-territory-radar-timestamp strong").textContent).toBe("09:10");
    expect(container.querySelector(".mf-territory-radar-live").textContent).toBe("");
    expect(layerHarness.layer.setFrame).not.toHaveBeenCalled();

    await act(async () => pending.reject(new Error("network")));
    expect(container.querySelector('[role="status"]').textContent).toContain("Fotogramma radar non disponibile");
    expect(container.querySelector(".mf-territory-radar-timestamp strong").textContent).toBe("09:10");
    expect(layerHarness.layer.setFrame).not.toHaveBeenCalled();
  });

  it("restores the loaded frame when scrubbing back before a pending frame is ready", async () => {
    vi.useFakeTimers();
    await renderRadar();
    await finishFrame();
    const pending = deferred();
    layerHarness.layer.prefetchFrame.mockReturnValue(pending.promise);
    await selectFrame(0);
    await selectFrame(18);

    expect(container.querySelector(".mf-territory-radar-overlay").getAttribute("aria-busy")).toBe("false");
    expect(container.querySelector(".mf-territory-radar-live").textContent).toContain("LIVE");
    await act(async () => {
      pending.resolve();
      await vi.advanceTimersByTimeAsync(13_000);
    });
    expect(layerHarness.layer.setFrame).not.toHaveBeenCalled();
    expect(container.querySelector('[role="status"]').textContent).toBe("");
  });

  it("gives a slowly prepared visible frame its full dwell instead of skipping it", async () => {
    vi.useFakeTimers();
    await renderRadar();
    await finishFrame();
    const pending = deferred();
    const firstTime = "2026-08-03T05:40:00.000Z";
    layerHarness.layer.prefetchFrame.mockImplementation((product, time) => (
      time === firstTime ? pending.promise : Promise.resolve()
    ));
    await act(async () => container.querySelector(".mf-territory-radar-play").click());
    await act(async () => vi.advanceTimersByTimeAsync(1_700));
    expect(layerHarness.layer.setFrame).not.toHaveBeenCalled();
    expect(container.querySelector('input[type="range"]').value).toBe("18");
    expect(layerHarness.layer.prefetchFrame.mock.calls.every(([, time]) => time === firstTime))
      .toBe(true);

    await act(async () => pending.resolve());
    expect(layerHarness.layer.setFrame).toHaveBeenCalledTimes(1);
    expect(layerHarness.layer.setFrame.mock.calls[0][1]).toBe(firstTime);
    await finishFrame();
    expect(container.querySelector(".mf-territory-radar-timestamp strong").textContent).toBe("07:40");
    await act(async () => vi.advanceTimersByTimeAsync(699));
    expect(layerHarness.layer.setFrame).toHaveBeenCalledTimes(1);
    await act(async () => vi.advanceTimersByTimeAsync(1));
    expect(layerHarness.layer.setFrame).toHaveBeenCalledTimes(2);
    expect(layerHarness.layer.setFrame.mock.calls[1][1]).toBe("2026-08-03T05:45:00.000Z");
  });

  it("waits after a failed national frame, retries it, and gives the recovered frame its full dwell", async () => {
    vi.useFakeTimers();
    await renderRadar();
    await finishFrame();
    await act(async () => container.querySelector(".mf-territory-radar-play").click());

    const firstTime = "2026-08-03T05:40:00.000Z";
    await act(async () => vi.advanceTimersByTimeAsync(700));
    expect(layerHarness.layer.setFrame).toHaveBeenCalledTimes(1);
    expect(layerHarness.layer.setFrame.mock.calls[0][1]).toBe(firstTime);
    await finishFrame({ error: true });

    expect(container.querySelector('input[type="range"]').value).toBe("18");
    expect(container.querySelector(".mf-territory-radar-timestamp strong").textContent).toBe("09:10");
    expect(container.querySelector(".mf-territory-radar-play").getAttribute("aria-label"))
      .toBe("Metti in pausa");
    expect(container.querySelector('[role="status"]').textContent).toContain("Radar in attesa");
    await act(async () => vi.advanceTimersByTimeAsync(1_499));
    expect(layerHarness.layer.setFrame).toHaveBeenCalledTimes(1);
    await act(async () => vi.advanceTimersByTimeAsync(1));
    expect(layerHarness.layer.setFrame).toHaveBeenCalledTimes(2);
    expect(layerHarness.layer.setFrame.mock.calls[1][1]).toBe(firstTime);

    await finishFrame();
    expect(container.querySelector('input[type="range"]').value).toBe("0");
    await act(async () => vi.advanceTimersByTimeAsync(699));
    expect(layerHarness.layer.setFrame).toHaveBeenCalledTimes(2);
    await act(async () => vi.advanceTimersByTimeAsync(1));
    expect(layerHarness.layer.setFrame).toHaveBeenCalledTimes(3);
    expect(layerHarness.layer.setFrame.mock.calls[2][1]).toBe("2026-08-03T05:45:00.000Z");
  });

  it("skips one twice-failed frame without fast-forwarding the displayed timeline", async () => {
    vi.useFakeTimers();
    await renderRadar();
    await finishFrame();
    await act(async () => container.querySelector(".mf-territory-radar-play").click());

    const firstTime = "2026-08-03T05:40:00.000Z";
    const nextTime = "2026-08-03T05:45:00.000Z";
    const nextFrame = deferred();
    layerHarness.layer.prefetchFrame.mockImplementation((product, time) => {
      if (time === firstTime) return Promise.reject(new Error("tile unavailable"));
      if (time === nextTime) return nextFrame.promise;
      return Promise.resolve();
    });

    await act(async () => vi.advanceTimersByTimeAsync(700));
    await act(async () => vi.advanceTimersByTimeAsync(1_500));
    await act(async () => vi.advanceTimersByTimeAsync(1_500));
    expect(layerHarness.layer.setFrame).not.toHaveBeenCalled();
    expect(container.querySelector('input[type="range"]').value).toBe("18");
    expect(container.querySelector(".mf-territory-radar-timestamp strong").textContent).toBe("09:10");
    await act(async () => vi.advanceTimersByTimeAsync(5_000));
    expect(layerHarness.layer.setFrame).not.toHaveBeenCalled();

    await act(async () => nextFrame.resolve());
    expect(layerHarness.layer.setFrame.mock.calls[0][1]).toBe(nextTime);
    await finishFrame();
    expect(container.querySelector('input[type="range"]').value).toBe("1");
    await act(async () => vi.advanceTimersByTimeAsync(699));
    expect(layerHarness.layer.setFrame).toHaveBeenCalledTimes(1);
  });

  it("backs off during a sustained outage and cancels automatic retries on pause", async () => {
    vi.useFakeTimers();
    await renderRadar();
    await finishFrame();
    const play = container.querySelector(".mf-territory-radar-play");
    await act(async () => play.click());
    layerHarness.layer.prefetchFrame.mockClear();
    layerHarness.layer.prefetchFrame.mockRejectedValue(new Error("source unavailable"));

    await act(async () => vi.advanceTimersByTimeAsync(700));
    await act(async () => vi.advanceTimersByTimeAsync(1_500));
    await act(async () => vi.advanceTimersByTimeAsync(1_500));
    expect(layerHarness.layer.prefetchFrame).toHaveBeenCalledTimes(3);
    expect(layerHarness.layer.setFrame).not.toHaveBeenCalled();
    expect(play.getAttribute("aria-label")).toBe("Metti in pausa");
    expect(container.querySelector('[role="status"]').textContent).toContain("Radar in attesa");
    await act(async () => vi.advanceTimersByTimeAsync(9_999));
    expect(layerHarness.layer.prefetchFrame).toHaveBeenCalledTimes(3);
    await act(async () => vi.advanceTimersByTimeAsync(1));
    expect(layerHarness.layer.prefetchFrame).toHaveBeenCalledTimes(4);

    await act(async () => play.click());
    await act(async () => vi.advanceTimersByTimeAsync(30_000));
    expect(layerHarness.layer.prefetchFrame).toHaveBeenCalledTimes(4);
    expect(play.getAttribute("aria-label")).toBe("Anima gli ultimi 90 minuti");
  });

  it("does not mistake the last displayed frame for a new frame after a failed full cycle", async () => {
    vi.useFakeTimers();
    await renderRadar({ product: { periodMinutes: 45, productType: "SRI", time: "2026-08-03T07:10:00Z" } });
    await finishFrame();
    await act(async () => container.querySelector(".mf-territory-radar-play").click());
    layerHarness.layer.prefetchFrame.mockClear();
    layerHarness.layer.prefetchFrame.mockRejectedValue(new Error("all frames unavailable"));

    await act(async () => vi.advanceTimersByTimeAsync(700));
    await act(async () => vi.advanceTimersByTimeAsync(1_500));
    await act(async () => vi.advanceTimersByTimeAsync(1_500));
    await act(async () => vi.advanceTimersByTimeAsync(10_000));
    await act(async () => vi.advanceTimersByTimeAsync(10_000));

    const requestedTimes = layerHarness.layer.prefetchFrame.mock.calls.map(([, time]) => time);
    expect(requestedTimes).toEqual([
      "2026-08-03T05:40:00.000Z",
      "2026-08-03T05:40:00.000Z",
      "2026-08-03T06:25:00.000Z",
      "2026-08-03T06:25:00.000Z",
      "2026-08-03T05:40:00.000Z",
    ]);
    expect(container.querySelector('input[type="range"]').value).toBe("2");
    expect(container.querySelector(".mf-territory-radar-timestamp strong").textContent).toBe("09:10");
    expect(container.querySelector('[role="status"]').textContent).toContain("Radar in attesa");
    expect(layerHarness.layer.setFrame).not.toHaveBeenCalled();
  });

  it("keeps retrying the only unseen frame when the sequence has two frames", async () => {
    vi.useFakeTimers();
    await renderRadar({ product: { periodMinutes: 90, productType: "SRI", time: "2026-08-03T07:10:00Z" } });
    await finishFrame();
    await act(async () => container.querySelector(".mf-territory-radar-play").click());
    layerHarness.layer.prefetchFrame.mockClear();
    layerHarness.layer.prefetchFrame.mockRejectedValue(new Error("frame unavailable"));

    await act(async () => vi.advanceTimersByTimeAsync(700));
    await act(async () => vi.advanceTimersByTimeAsync(1_500));
    await act(async () => vi.advanceTimersByTimeAsync(1_500));
    expect(layerHarness.layer.prefetchFrame).toHaveBeenCalledTimes(3);
    expect(container.querySelector('input[type="range"]').value).toBe("1");
    await act(async () => vi.advanceTimersByTimeAsync(10_000));
    expect(layerHarness.layer.prefetchFrame).toHaveBeenCalledTimes(4);
    expect(container.querySelector('[role="status"]').textContent).toContain("Radar in attesa");
  });

  it("ignores a timed-out preparation that finishes after its retry", async () => {
    vi.useFakeTimers();
    await renderRadar();
    await finishFrame();
    await act(async () => container.querySelector(".mf-territory-radar-play").click());
    const firstTime = "2026-08-03T05:40:00.000Z";
    const pending = deferred();
    let requests = 0;
    layerHarness.layer.prefetchFrame.mockImplementation((product, time) => {
      if (time === firstTime && requests++ === 0) return pending.promise;
      return Promise.resolve();
    });

    await act(async () => vi.advanceTimersByTimeAsync(700));
    await act(async () => vi.advanceTimersByTimeAsync(12_000));
    expect(container.querySelector('[role="status"]').textContent).toContain("Radar in attesa");
    expect(container.querySelector('input[type="range"]').value).toBe("18");
    expect(layerHarness.layer.setFrame).not.toHaveBeenCalled();
    await act(async () => vi.advanceTimersByTimeAsync(1_500));
    expect(layerHarness.layer.setFrame).toHaveBeenCalledTimes(1);
    await act(async () => pending.resolve());
    expect(layerHarness.layer.setFrame).toHaveBeenCalledTimes(1);
  });

  it("warms the following frame only after the displayed frame finishes loading", async () => {
    await renderRadar();
    await act(async () => container.querySelector(".mf-territory-radar-play").click());
    expect(layerHarness.layer.prefetchFrame).not.toHaveBeenCalled();
    await finishFrame();
    expect(layerHarness.layer.prefetchFrame).toHaveBeenCalledWith(
      expect.objectContaining({ productType: "SRI" }),
      "2026-08-03T05:40:00.000Z",
    );
  });

  it("does not advance after pausing or commit a prepared frame after unmount", async () => {
    vi.useFakeTimers();
    await renderRadar();
    await finishFrame();
    const warming = deferred();
    layerHarness.layer.prefetchFrame.mockReturnValue(warming.promise);
    const play = container.querySelector(".mf-territory-radar-play");
    await act(async () => play.click());
    await act(async () => play.click());
    await act(async () => {
      warming.resolve();
      await vi.advanceTimersByTimeAsync(1_500);
    });
    expect(layerHarness.layer.setFrame).not.toHaveBeenCalled();

    const pending = deferred();
    layerHarness.layer.prefetchFrame.mockReturnValue(pending.promise);
    await selectFrame(0);
    await act(async () => root.render(null));
    await act(async () => pending.resolve());
    expect(layerHarness.layer.setFrame).not.toHaveBeenCalled();
    expect(map.removeLayer).toHaveBeenCalledWith(layerHarness.layer);
  });

  it("pauses playback atomically while the shared map is zooming", async () => {
    vi.useFakeTimers();
    await renderRadar();
    await finishFrame();
    const play = container.querySelector(".mf-territory-radar-play");
    await act(async () => play.click());

    expect(play.getAttribute("aria-label")).toBe("Metti in pausa");
    expect(mapListeners.has("zoomstart")).toBe(true);
    expect(mapListeners.has("zoom")).toBe(true);
    expect(mapListeners.has("zoomend")).toBe(true);

    await act(async () => {
      mapListeners.get("zoomstart")?.();
      mapListeners.get("zoom")?.();
      mapListeners.get("zoomend")?.();
      await vi.advanceTimersByTimeAsync(1_400);
    });

    expect(play.getAttribute("aria-label")).toBe("Anima gli ultimi 90 minuti");
    expect(layerHarness.layer.setFrame).not.toHaveBeenCalled();

    await act(async () => root.render(null));
    expect(mapListeners.size).toBe(0);
    expect(map.off).toHaveBeenCalledTimes(3);
  });

  it("mounts one independent DPC layer and labels only its loaded latest frame as live", async () => {
    const model = buildModel();

    await act(async () => {
      root.render(
        <TerritoryRadarOverlay
          enabled
          leaflet={{}}
          map={map}
          radarModel={model}
        />,
      );
    });

    expect(radarLayerMock.create).toHaveBeenCalledTimes(1);
    expect(layerHarness.layer.addTo).toHaveBeenCalledWith(map);
    const player = container.querySelector(".mf-territory-radar-player");
    const legendButton = container.querySelector(".mf-territory-radar-info");
    expect([...player.children].map((element) => element.className)).toEqual([
      "mf-territory-radar-play",
      "mf-territory-radar-timeline",
      "mf-territory-radar-timestamp",
      "mf-territory-radar-info",
    ]);
    expect(container.querySelector(".mf-territory-radar-timeline-start")).toBeNull();
    expect(legendButton?.getAttribute("aria-expanded")).toBe("false");
    expect(legendButton?.getAttribute("aria-label")).toBe("Mostra la legenda radar");
    expect(container.querySelector(".mf-territory-radar-scale")).toBeNull();
    expect(container.textContent).not.toContain("● LIVE");

    await act(async () => legendButton.click());

    const legend = container.querySelector(".mf-territory-radar-scale");
    expect(legendButton.getAttribute("aria-expanded")).toBe("true");
    expect(legendButton.getAttribute("aria-label")).toBe("Nascondi la legenda radar");
    expect(legend?.getAttribute("role")).toBe("img");
    expect(legend?.getAttribute("aria-label"))
      .toBe("Scala dell'intensità della pioggia");
    expect(legendButton.getAttribute("aria-controls")).toBe(legend?.id);
    expect(legend?.textContent).toContain("Debole");
    expect(legend?.textContent).toContain("Molto forte");

    await act(async () => legendButton.click());

    expect(legendButton.getAttribute("aria-expanded")).toBe("false");
    expect(legendButton.getAttribute("aria-label")).toBe("Mostra la legenda radar");
    expect(container.querySelector(".mf-territory-radar-scale")).toBeNull();

    await act(async () => {
      layerHarness.listeners.get("tileload")?.({
        tile: {
          radarFrameTime: "2026-08-03T07:10:00.000Z",
          radarHasEcho: true,
        },
      });
      layerHarness.listeners.get("load")?.();
    });

    expect(container.textContent).toContain("● LIVE");
    expect(container.querySelector('input[type="range"]')?.getAttribute("aria-valuetext"))
      .toBe("09:10 · LIVE");
  });

  it("keeps a frame failure local and exposes only the user-facing radar message", async () => {
    const model = buildModel();

    await act(async () => {
      root.render(
        <TerritoryRadarOverlay enabled leaflet={{}} map={map} radarModel={model} />,
      );
    });
    await act(async () => {
      layerHarness.listeners.get("tileerror")?.({
        tile: { radarFrameTime: "2026-08-03T07:10:00.000Z" },
      });
      layerHarness.listeners.get("load")?.();
    });

    expect(container.querySelector('[role="status"]')?.textContent)
      .toBe("Fotogramma radar non disponibile");
    expect(container.textContent).not.toMatch(/tile|exception|error/i);
  });

  it.each([
    ["empty", "Nessuna precipitazione rilevata"],
    ["error", "Fotogramma radar non disponibile"],
  ])("keeps radar freshness visible for a stale %s frame", async (frameKind, frameMessage) => {
    const model = buildModel({
      isStale: true,
      staleNotice: "Radar non aggiornato",
    });

    await act(async () => {
      root.render(
        <TerritoryRadarOverlay enabled leaflet={{}} map={map} radarModel={model} />,
      );
    });
    await act(async () => {
      if (frameKind === "error") {
        layerHarness.listeners.get("tileerror")?.({
          tile: { radarFrameTime: "2026-08-03T07:10:00.000Z" },
        });
      }
      layerHarness.listeners.get("load")?.();
    });

    const status = container.querySelector('[role="status"]');
    expect(status?.textContent).toContain(frameMessage);
    expect(status?.textContent).toContain("Radar non aggiornato");
  });

  it("pauses and returns to the latest frame after the layer is unmounted", async () => {
    const model = buildModel();

    await act(async () => {
      root.render(
        <TerritoryRadarOverlay enabled leaflet={{}} map={map} radarModel={model} />,
      );
    });

    const range = container.querySelector('input[type="range"]');
    const latestFrame = range?.max;
    await act(async () => {
      range.value = "0";
      range.dispatchEvent(new Event("change", { bubbles: true }));
    });
    await act(async () => {
      container.querySelector(".mf-territory-radar-play")?.click();
    });
    expect(container.querySelector(".mf-territory-radar-play")?.getAttribute("aria-label"))
      .toBe("Metti in pausa");

    await act(async () => {
      root.render(null);
    });
    await act(async () => {
      root.render(
        <TerritoryRadarOverlay enabled leaflet={{}} map={map} radarModel={model} />,
      );
    });

    expect(container.querySelector('input[type="range"]')?.value).toBe(latestFrame);
    expect(container.querySelector(".mf-territory-radar-play")?.getAttribute("aria-label"))
      .toBe("Anima gli ultimi 90 minuti");
  });

  it("removes only its own radar layer when the independent toggle is disabled", async () => {
    const model = buildModel();

    await act(async () => {
      root.render(
        <TerritoryRadarOverlay enabled leaflet={{}} map={map} radarModel={model} />,
      );
    });
    await act(async () => {
      root.render(
        <TerritoryRadarOverlay enabled={false} leaflet={{}} map={map} radarModel={model} />,
      );
    });

    expect(map.removeLayer).toHaveBeenCalledWith(layerHarness.layer);
    expect(container.innerHTML).toBe("");
  });

  it("renders a friendly status instead of attempting a layer when radar is unavailable", () => {
    const markup = renderToStaticMarkup(
      <TerritoryRadarOverlay
        enabled
        leaflet={{}}
        map={map}
        radarModel={{
          available: false,
          title: "Radar precipitazioni",
          unavailableLabel: "Radar temporaneamente non disponibile",
        }}
      />,
    );

    expect(markup).toContain("Radar temporaneamente non disponibile");
    expect(markup).toContain('role="status"');
    expect(radarLayerMock.create).not.toHaveBeenCalled();
  });
});
