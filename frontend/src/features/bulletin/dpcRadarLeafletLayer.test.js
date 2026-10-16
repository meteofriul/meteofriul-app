import { afterEach, describe, expect, it, vi } from "vitest";

import {
  DPC_RADAR_COVERAGE_BOUNDS,
  DPC_RADAR_NATIVE_ZOOM,
  DPC_RADAR_PREPARED_CACHE_LIMIT,
  DPC_RADAR_SHARED_MAX_ZOOM,
  DPC_RADAR_SHARED_MIN_ZOOM,
  DPC_RADAR_SHARED_TILE_OPTIONS,
  createDpcRadarGridLayer,
  isDpcRadarTileAvailable,
} from "./dpcRadarLeafletLayer";

function createLeafletStub() {
  class GridLayer {
    constructor(options) {
      this.initialize(options);
    }

    redraw() {}

    fire(event, payload) {
      this.listeners?.get(event)?.(payload);
      return this;
    }

    on(event, listener) {
      this.listeners ||= new Map();
      this.listeners.set(event, listener);
    }
  }

  GridLayer.extend = (definition) => {
    class ExtendedGridLayer extends GridLayer {}
    Object.assign(ExtendedGridLayer.prototype, definition);
    return ExtendedGridLayer;
  };

  return {
    GridLayer,
    setOptions(layer, options) {
      layer.options = options;
    },
  };
}

function installCanvasHarness() {
  const images = [];
  const contexts = [];
  vi.stubGlobal("document", {
    createElement: () => {
      const context = {
        clearRect: vi.fn(),
        drawImage: vi.fn(),
        getImageData: vi.fn(() => ({ data: new Uint8ClampedArray([128, 0, 0, 255]) })),
        putImageData: vi.fn(),
      };
      contexts.push(context);
      return { getContext: () => context };
    },
  });
  vi.stubGlobal("Image", class {
    set src(value) {
      this.url = value;
      images.push(this);
    }
    removeAttribute() {}
  });
  return { images, contexts };
}

function createVisibleLayer() {
  const layer = createDpcRadarGridLayer(createLeafletStub(), {
    product: { productType: "SRI" },
    tileBaseUrl: "https://tiles.example.test",
    time: "2026-09-15T08:00:00Z",
  });
  layer._tiles = { first: { coords: { x: 68, y: 45, z: 7 }, current: true } };
  return layer;
}

describe("DPC radar Leaflet layer", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("prepares the next frame once and reuses decoded pixels without sharing tile DOM", async () => {
    const { images, contexts } = installCanvasHarness();
    const layer = createVisibleLayer();
    const nextTime = "2026-09-15T08:05:00Z";
    const preparation = layer.prefetchFrame({ productType: "SRI" }, nextTime);
    expect(images).toHaveLength(1);
    images[0].onload();
    const [preparedCanvas] = await preparation;
    layer.setFrame({ productType: "SRI" }, nextTime);
    const done = vi.fn();
    const tile = layer.createTile({ x: 68, y: 45, z: 7 }, done);
    await Promise.resolve();

    expect(images).toHaveLength(1);
    expect(tile).not.toBe(preparedCanvas);
    expect(contexts.filter((context) => context.getImageData.mock.calls.length)).toHaveLength(1);
    expect(tile.radarFrameTime).toBe(nextTime);
    expect(tile.radarHasEcho).toBe(true);
    expect(done).toHaveBeenCalledWith(null, tile);
    layer.onRemove();
  });

  it("swaps a prepared visible mosaic in place without removing Leaflet tiles", async () => {
    const { images, contexts } = installCanvasHarness();
    const visibleCanvas = globalThis.document.createElement("canvas");
    visibleCanvas.radarFrameTime = "2026-09-15T08:00:00Z";
    visibleCanvas.radarHasEcho = false;
    const layer = createVisibleLayer();
    layer._tiles.first.el = visibleCanvas;
    layer.redraw = vi.fn();
    const loading = vi.fn();
    const tileload = vi.fn();
    const load = vi.fn();
    layer.on("loading", loading);
    layer.on("tileload", tileload);
    layer.on("load", load);

    const nextTime = "2026-09-15T08:05:00Z";
    const swap = layer.setFrame({ productType: "SRI" }, nextTime);

    expect(loading).toHaveBeenCalledOnce();
    expect(layer.redraw).not.toHaveBeenCalled();
    expect(images).toHaveLength(1);
    expect(contexts[0].drawImage).not.toHaveBeenCalled();

    images[0].onload();
    await swap;

    expect(contexts[0].clearRect).not.toHaveBeenCalled();
    expect(contexts[0].drawImage).toHaveBeenCalledWith(
      expect.anything(), 0, 0, 256, 256,
    );
    expect(contexts[0].globalCompositeOperation).toBe("source-over");
    expect(visibleCanvas.radarFrameTime).toBe(nextTime);
    expect(visibleCanvas.radarHasEcho).toBe(true);
    expect(tileload).toHaveBeenCalledWith({
      coords: { x: 68, y: 45, z: 7 },
      tile: visibleCanvas,
    });
    expect(load).toHaveBeenCalledOnce();
    layer.onRemove();
  });

  it("turns an in-place canvas paint exception into a settled frame error", async () => {
    const { images, contexts } = installCanvasHarness();
    const visibleCanvas = globalThis.document.createElement("canvas");
    visibleCanvas.radarFrameTime = "2026-09-15T08:00:00Z";
    const layer = createVisibleLayer();
    layer._tiles.first.el = visibleCanvas;
    layer.redraw = vi.fn();
    const tileerror = vi.fn();
    const load = vi.fn();
    layer.on("tileerror", tileerror);
    layer.on("load", load);
    contexts[0].drawImage.mockImplementationOnce(() => {
      throw new Error("controlled canvas failure");
    });

    const nextTime = "2026-09-15T08:05:00Z";
    const swap = layer.setFrame({ productType: "SRI" }, nextTime);
    images[0].onload();

    await expect(swap).resolves.toBeUndefined();
    expect(visibleCanvas.radarFrameTime).toBe("2026-09-15T08:00:00Z");
    expect(contexts[0].clearRect).not.toHaveBeenCalled();
    expect(contexts[0].globalCompositeOperation).toBe("source-over");
    expect(tileerror).toHaveBeenCalledWith(expect.objectContaining({
      error: expect.objectContaining({ message: "controlled canvas failure" }),
      tile: { radarFrameTime: nextTime, radarHasEcho: false },
    }));
    expect(load).toHaveBeenCalledOnce();
    layer.onRemove();
  });

  it("keeps the previous complete mosaic visible when a replacement tile fails", async () => {
    const { images, contexts } = installCanvasHarness();
    const visibleCanvas = globalThis.document.createElement("canvas");
    visibleCanvas.radarFrameTime = "2026-09-15T08:00:00Z";
    visibleCanvas.radarHasEcho = true;
    const layer = createVisibleLayer();
    layer._tiles.first.el = visibleCanvas;
    layer.redraw = vi.fn();
    const tileerror = vi.fn();
    const load = vi.fn();
    layer.on("tileerror", tileerror);
    layer.on("load", load);

    const nextTime = "2026-09-15T08:05:00Z";
    const swap = layer.setFrame({ productType: "SRI" }, nextTime);
    images[0].onerror();
    await swap;

    expect(contexts[0].clearRect).not.toHaveBeenCalled();
    expect(contexts[0].drawImage).not.toHaveBeenCalled();
    expect(visibleCanvas.radarFrameTime).toBe("2026-09-15T08:00:00Z");
    expect(visibleCanvas.radarHasEcho).toBe(true);
    expect(tileerror).toHaveBeenCalledWith(expect.objectContaining({
      tile: { radarFrameTime: nextTime, radarHasEcho: false },
    }));
    expect(load).toHaveBeenCalledOnce();
    layer.onRemove();
  });

  it("refetches a failed prepared tile instead of caching a transient failure", async () => {
    const { images } = installCanvasHarness();
    const layer = createVisibleLayer();
    const product = { productType: "SRI" };
    const time = "2026-09-15T08:05:00Z";
    const failed = layer.prefetchFrame(product, time);
    images[0].onerror();
    await expect(failed).rejects.toThrow("non disponibile");

    const retried = layer.prefetchFrame(product, time);
    expect(images).toHaveLength(2);
    images[1].onload();
    await expect(retried).resolves.toHaveLength(1);
    layer.onRemove();
  });

  it("ignores old tile completions after frame changes, tile unload and layer removal", async () => {
    const { images } = installCanvasHarness();
    const layer = createVisibleLayer();
    const oldDone = vi.fn();
    layer.createTile({ x: 68, y: 45, z: 7 }, oldDone);
    layer.setFrame({ productType: "SRI" }, "2026-09-15T08:05:00Z");
    images[0].onload();
    await Promise.resolve();
    expect(oldDone).not.toHaveBeenCalled();

    const unloadedDone = vi.fn();
    const tile = layer.createTile({ x: 68, y: 45, z: 7 }, unloadedDone);
    layer.listeners.get("tileunload")({ tile });
    images[1].onload();
    await Promise.resolve();
    expect(unloadedDone).not.toHaveBeenCalled();

    layer.setFrame({ productType: "SRI" }, "2026-09-15T08:10:00Z");
    const removedDone = vi.fn();
    layer.createTile({ x: 68, y: 45, z: 7 }, removedDone);
    const lateOnLoad = images[2].onload;
    layer.onRemove();
    lateOnLoad();
    await Promise.resolve();
    expect(removedDone).not.toHaveBeenCalled();
    await expect(layer.prefetchFrame({ productType: "SRI" }, "2026-09-15T08:15:00Z"))
      .rejects.toThrow("non attivo");
  });

  it("bounds retained prepared tiles and excludes transparent tiles from prefetch", async () => {
    const { images } = installCanvasHarness();
    const layer = createVisibleLayer();
    layer._tiles.outside = { coords: { x: 15, y: 11, z: 5 }, current: true };
    layer._tiles.oldZoom = { coords: { x: 16, y: 11, z: 5 }, current: false };
    const times = Array.from({ length: DPC_RADAR_PREPARED_CACHE_LIMIT + 1 }, (_, i) => (
      new Date(Date.UTC(2026, 8, 15, 8, i * 5)).toISOString()
    ));
    for (const time of times) {
      const pending = layer.prefetchFrame({ productType: "SRI" }, time);
      images.at(-1).onload();
      await pending;
    }
    expect(images).toHaveLength(times.length);
    await layer.prefetchFrame({ productType: "SRI" }, times.at(-1));
    expect(images).toHaveLength(times.length);
    const evicted = layer.prefetchFrame({ productType: "SRI" }, times[0]);
    expect(images).toHaveLength(times.length + 1);
    images.at(-1).onload();
    await evicted;
    layer.onRemove();
  });

  it("can retain every supported native tile of one national radar frame", () => {
    for (const z of [5, 6, 7]) {
      let count = 0;
      for (let x = 0; x < 2 ** z; x += 1) {
        for (let y = 0; y < 2 ** z; y += 1) {
          if (isDpcRadarTileAvailable({ x, y, z })) count += 1;
        }
      }
      expect(count).toBeGreaterThan(0);
      expect(count).toBeLessThanOrEqual(DPC_RADAR_PREPARED_CACHE_LIMIT);
    }
  });
  it("uses native zoom 5 to 7 tiles and overzooms the shared Italy map", () => {
    expect(DPC_RADAR_NATIVE_ZOOM).toBe(7);
    expect(DPC_RADAR_SHARED_MIN_ZOOM).toBe(5);
    expect(DPC_RADAR_SHARED_MAX_ZOOM).toBe(13);
    expect(DPC_RADAR_COVERAGE_BOUNDS).toEqual([[35.06, 4.53], [47.57, 20.48]]);
    expect(DPC_RADAR_SHARED_TILE_OPTIONS).toEqual({
      bounds: [[35.06, 4.53], [47.57, 20.48]],
      maxNativeZoom: 7,
      maxZoom: 13,
      minZoom: 5,
      noWrap: true,
      opacity: 0.78,
      updateWhenZooming: false,
    });
  });

  it("creates an independently mountable layer and updates its frame in place", () => {
    const L = createLeafletStub();
    const firstProduct = { productType: "SRI" };
    const nextProduct = { productType: "VMI" };
    const layer = createDpcRadarGridLayer(L, {
      layerOptions: { pane: "radarPane", zIndex: 320 },
      product: firstProduct,
      tileBaseUrl: "https://tiles.example.test",
      tileSize: 512,
      time: "2026-09-15T08:00:00Z",
    });
    layer.redraw = vi.fn();

    expect(layer.options).toMatchObject({
      bounds: [[35.06, 4.53], [47.57, 20.48]],
      maxNativeZoom: 7,
      maxZoom: 13,
      minZoom: 5,
      pane: "radarPane",
      tileSize: 512,
      zIndex: 320,
    });
    expect(layer.frameProduct).toBe(firstProduct);
    expect(layer.frameTime).toBe("2026-09-15T08:00:00Z");

    layer.setFrame(nextProduct, "2026-09-15T08:05:00Z");

    expect(layer.frameProduct).toBe(nextProduct);
    expect(layer.frameTime).toBe("2026-09-15T08:05:00Z");
    expect(layer.redraw).toHaveBeenCalledOnce();
  });

  it("matches the official native SRI tile footprint from zoom 5 through 7", () => {
    expect(isDpcRadarTileAvailable({ x: 16, y: 11, z: 5 })).toBe(true);
    expect(isDpcRadarTileAvailable({ x: 17, y: 12, z: 5 })).toBe(true);
    expect(isDpcRadarTileAvailable({ x: 15, y: 11, z: 5 })).toBe(false);
    expect(isDpcRadarTileAvailable({ x: 33, y: 22, z: 6 })).toBe(true);
    expect(isDpcRadarTileAvailable({ x: 35, y: 22, z: 6 })).toBe(false);
    expect(isDpcRadarTileAvailable({ x: 66, y: 44, z: 7 })).toBe(true);
    expect(isDpcRadarTileAvailable({ x: 70, y: 44, z: 7 })).toBe(false);
    expect(isDpcRadarTileAvailable({ x: 68, y: 50, z: 7 })).toBe(true);
    expect(isDpcRadarTileAvailable({ x: 68, y: 50, z: 8 })).toBe(false);
  });

  it("resolves tiles outside the official footprint as transparent without a request", async () => {
    const canvas = { getContext: vi.fn(() => null) };
    const ImageStub = vi.fn();
    vi.stubGlobal("document", {
      createElement: vi.fn(() => canvas),
    });
    vi.stubGlobal("Image", ImageStub);

    try {
      const layer = createDpcRadarGridLayer(createLeafletStub(), {
        product: { productType: "SRI" },
        tileBaseUrl: "https://tiles.example.test/",
        time: "2026-09-15T08:05:00Z",
      });
      const done = vi.fn();

      expect(layer.createTile({ x: 15, y: 11, z: 5 }, done)).toBe(canvas);
      await Promise.resolve();

      expect(ImageStub).not.toHaveBeenCalled();
      expect(canvas).toMatchObject({
        height: 256,
        radarFrameTime: "2026-09-15T08:05:00Z",
        radarHasEcho: false,
        width: 256,
      });
      expect(done).toHaveBeenCalledWith(null, canvas);
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it("allows the existing locked card to narrow the layer zoom without changing shared defaults", () => {
    const layer = createDpcRadarGridLayer(createLeafletStub(), {
      layerOptions: { maxZoom: 7 },
      product: { productType: "SRI" },
      tileBaseUrl: "https://tiles.example.test",
      time: "2026-09-15T08:00:00Z",
    });

    expect(layer.options.maxNativeZoom).toBe(7);
    expect(layer.options.maxZoom).toBe(7);
    expect(DPC_RADAR_SHARED_TILE_OPTIONS.maxZoom).toBe(13);
  });

  it("keeps the DPC tile rendering contract inside the reusable layer", async () => {
    const pixels = new Uint8ClampedArray([128, 0, 0, 255]);
    const context = {
      clearRect: vi.fn(),
      drawImage: vi.fn(),
      getImageData: vi.fn(() => ({ data: pixels })),
      putImageData: vi.fn(),
    };
    const canvas = { getContext: vi.fn(() => context) };
    let requestedUrl = "";

    class ImageStub {
      set src(value) {
        requestedUrl = value;
        this.onload();
      }
    }

    vi.stubGlobal("document", {
      createElement: vi.fn(() => canvas),
    });
    vi.stubGlobal("Image", ImageStub);

    try {
      const layer = createDpcRadarGridLayer(createLeafletStub(), {
        product: { productType: "SRI" },
        tileBaseUrl: "https://tiles.example.test/",
        time: "2026-09-15T08:05:00Z",
      });
      const done = vi.fn();

      expect(layer.createTile({ x: 68, y: 45, z: 7 }, done)).toBe(canvas);
      expect(requestedUrl).toBe(
        "https://tiles.example.test/SRI/2026/09/15/0805/7/68/45/sri.webp",
      );
      await Promise.resolve();
      expect(canvas).toMatchObject({
        height: 256,
        radarFrameTime: "2026-09-15T08:05:00Z",
        radarHasEcho: true,
        width: 256,
      });
      expect(done).toHaveBeenCalledWith(null, canvas);
    } finally {
      vi.unstubAllGlobals();
    }
  });
});
