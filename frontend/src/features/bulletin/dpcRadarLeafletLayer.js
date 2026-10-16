import {
  buildDpcRadarTileUrl,
  colorizeSriRadarPixels,
} from "./radarDpcV2Tiles";

export const DPC_RADAR_NATIVE_ZOOM = 7;
export const DPC_RADAR_SHARED_MIN_ZOOM = 5;
export const DPC_RADAR_SHARED_MAX_ZOOM = 13;
export const DPC_RADAR_PREPARED_CACHE_LIMIT = 32;
const PREPARED_TILE_TIMEOUT_MS = 12_000;
export const DPC_RADAR_COVERAGE_BOUNDS = Object.freeze([
  Object.freeze([35.06, 4.53]),
  Object.freeze([47.57, 20.48]),
]);

// Mirrors the official SRI tile allowlist so edge tiles stay transparent
// instead of issuing expected 403 requests outside the national mosaic.
const DPC_RADAR_AVAILABLE_TILE_ROWS = Object.freeze({
  5: Object.freeze([[11, 16, 17], [12, 16, 17]]),
  6: Object.freeze([[22, 33, 34], [23, 33, 35], [24, 33, 35], [25, 34, 35]]),
  7: Object.freeze([
    [44, 66, 69],
    [45, 66, 69],
    [46, 66, 69],
    [47, 66, 70],
    [48, 66, 70],
    [49, 67, 70],
    [50, 68, 70],
  ]),
});

export function isDpcRadarTileAvailable(coords) {
  const x = Number(coords?.x);
  const y = Number(coords?.y);
  const z = Number(coords?.z);
  if (![x, y, z].every(Number.isInteger)) return false;

  return (DPC_RADAR_AVAILABLE_TILE_ROWS[z] || []).some(
    ([rowY, minX, maxX]) => y === rowY && x >= minX && x <= maxX,
  );
}

export const DPC_RADAR_SHARED_TILE_OPTIONS = Object.freeze({
  bounds: DPC_RADAR_COVERAGE_BOUNDS,
  maxNativeZoom: DPC_RADAR_NATIVE_ZOOM,
  maxZoom: DPC_RADAR_SHARED_MAX_ZOOM,
  minZoom: DPC_RADAR_SHARED_MIN_ZOOM,
  noWrap: true,
  opacity: 0.78,
  updateWhenZooming: false,
});

export function createDpcRadarGridLayer(L, {
  layerOptions = {},
  product,
  tileBaseUrl,
  tileSize = 256,
  time,
}) {
  const preparedTiles = new Map();
  let disposed = false;

  const prepareTile = (coords, frameProduct, frameTime) => {
    const key = `${frameProduct.productType}|${frameTime}|${coords.z}/${coords.x}/${coords.y}`;
    const cached = preparedTiles.get(key);
    if (cached) {
      preparedTiles.delete(key);
      preparedTiles.set(key, cached);
      return cached;
    }

    const entry = { canvas: null, cancel: null };
    entry.promise = new Promise((resolve, reject) => {
      const canvas = globalThis.document.createElement("canvas");
      canvas.height = tileSize;
      canvas.width = tileSize;
      canvas.radarHasEcho = false;
      let image = null;
      let timeoutId = null;
      let settled = false;
      const finish = (error) => {
        if (settled) return;
        settled = true;
        globalThis.clearTimeout(timeoutId);
        if (image) {
          image.onload = null;
          image.onerror = null;
        }
        if (error) {
          reject(error);
        } else {
          entry.canvas = canvas;
          resolve(canvas);
        }
      };
      entry.cancel = () => {
        finish(new Error("Caricamento radar annullato"));
        image?.removeAttribute?.("src");
      };
      if (!isDpcRadarTileAvailable(coords)) {
        finish();
        return;
      }
      const context = canvas.getContext("2d", { willReadFrequently: true });
      image = new globalThis.Image();
      image.crossOrigin = "anonymous";
      image.decoding = "async";
      image.onload = () => {
        if (disposed || settled) return;
        try {
          if (!context) throw new Error("Canvas radar non disponibile");
          context.drawImage(image, 0, 0, tileSize, tileSize);
          const imageData = context.getImageData(0, 0, tileSize, tileSize);
          canvas.radarHasEcho = colorizeSriRadarPixels(imageData.data).hasEcho;
          context.putImageData(imageData, 0, 0);
          finish();
        } catch (error) {
          finish(error);
        }
      };
      image.onerror = () => finish(new Error("Fotogramma radar DPC V2 non disponibile"));
      timeoutId = globalThis.setTimeout(() => {
        finish(new Error("Fotogramma radar DPC V2 non disponibile"));
      }, PREPARED_TILE_TIMEOUT_MS);
      image.src = buildDpcRadarTileUrl({
        baseUrl: tileBaseUrl,
        coords,
        productType: frameProduct.productType,
        time: frameTime,
      });
    });
    // A prefetched entry may be evicted before a visible tile subscribes to it.
    entry.promise.catch(() => {
      if (preparedTiles.get(key) === entry) preparedTiles.delete(key);
    });
    preparedTiles.set(key, entry);
    while (preparedTiles.size > DPC_RADAR_PREPARED_CACHE_LIMIT) {
      const oldestKey = preparedTiles.keys().next().value;
      preparedTiles.get(oldestKey)?.cancel?.();
      preparedTiles.delete(oldestKey);
    }
    return entry;
  };

  const RadarGridLayer = L.GridLayer.extend({
    initialize(options) {
      L.setOptions(this, options);
      this.frameProduct = product;
      this.frameTime = time;
      this.frameRevision = 0;
      this.on?.("tileunload", ({ tile }) => {
        if (tile) tile.radarCancelled = true;
      });
    },

    onAdd(map) {
      disposed = false;
      return L.GridLayer.prototype.onAdd?.call(this, map);
    },

    onRemove(map) {
      disposed = true;
      this.frameRevision += 1;
      for (const entry of preparedTiles.values()) entry.cancel?.();
      preparedTiles.clear();
      return L.GridLayer.prototype.onRemove?.call(this, map);
    },

    prefetchFrame(nextProduct, nextTime) {
      if (disposed) return Promise.reject(new Error("Radar non attivo"));
      const visibleTiles = Object.values(this._tiles || {})
        .filter((tile) => tile.current !== false && isDpcRadarTileAvailable(tile.coords));
      return Promise.all(visibleTiles.map(({ coords }) => (
        prepareTile(coords, nextProduct, nextTime).promise
      )));
    },

    setFrame(nextProduct, nextTime) {
      this.frameProduct = nextProduct;
      this.frameTime = nextTime;
      this.frameRevision += 1;
      const revision = this.frameRevision;
      const visibleTiles = Object.values(this._tiles || {})
        .filter(({ coords, current, el } = {}) => (
          current !== false
          && coords
          && typeof el?.getContext === "function"
        ));

      // Leaflet's GridLayer.redraw() removes every old tile before it creates
      // the replacements. Even with a warmed cache that produces a brief
      // blank mosaic on Android WebView. Keep the visible canvases mounted and
      // prepare the whole next mosaic off-screen before painting it in one JS
      // turn instead. A layer without mounted tiles still needs the native
      // redraw path so Leaflet can create its initial grid.
      if (!visibleTiles.length) {
        this.redraw();
        return undefined;
      }

      this.fire?.("loading");
      const preparedFrame = Promise.allSettled(visibleTiles.map(({ coords, el }) => (
        prepareTile(coords, nextProduct, nextTime).promise.then((prepared) => ({
          coords,
          prepared,
          tile: el,
        }))
      )));

      return preparedFrame.then((results) => {
        if (disposed || revision !== this.frameRevision) return;

        const failed = results.filter(({ status }) => status === "rejected");
        if (failed.length) {
          failed.forEach(({ reason }) => {
            this.fire?.("tileerror", {
              coords: null,
              error: reason,
              // Do not retag or repaint the visible canvas: the previous
              // complete frame remains on screen when one tile fails.
              tile: { radarFrameTime: nextTime, radarHasEcho: false },
            });
          });
          this.fire?.("load");
          return;
        }

        let frameTiles;
        try {
          frameTiles = results.map(({ value }) => ({
            ...value,
            context: value.tile.getContext("2d"),
          }));
        } catch (error) {
          this.fire?.("tileerror", {
            coords: null,
            error,
            tile: { radarFrameTime: nextTime, radarHasEcho: false },
          });
          this.fire?.("load");
          return;
        }
        if (frameTiles.some(({ context }) => !context)) {
          this.fire?.("tileerror", {
            coords: null,
            error: new Error("Canvas radar non disponibile"),
            tile: { radarFrameTime: nextTime, radarHasEcho: false },
          });
          this.fire?.("load");
          return;
        }

        // These writes are synchronous, so the browser cannot paint a mixed
        // frame between two tiles.
        try {
          frameTiles.forEach(({ context, coords, prepared, tile }) => {
            const previousComposite = context.globalCompositeOperation;
            try {
              // `copy` replaces transparent pixels too, without clearing the
              // old frame first. A synchronous draw failure therefore cannot
              // leave this tile deliberately blank.
              context.globalCompositeOperation = "copy";
              context.drawImage(prepared, 0, 0, tileSize, tileSize);
            } finally {
              context.globalCompositeOperation = previousComposite || "source-over";
            }
            tile.radarFrameTime = nextTime;
            tile.radarHasEcho = prepared.radarHasEcho;
            this.fire?.("tileload", { coords, tile });
          });
        } catch (error) {
          this.fire?.("tileerror", {
            coords: null,
            error,
            tile: { radarFrameTime: nextTime, radarHasEcho: false },
          });
          this.fire?.("load");
          return;
        }
        this.fire?.("load");
      });
    },

    createTile(coords, done) {
      const canvas = globalThis.document.createElement("canvas");
      const frameTime = this.frameTime;
      const revision = this.frameRevision;

      canvas.height = tileSize;
      canvas.width = tileSize;
      canvas.radarFrameTime = frameTime;
      canvas.radarHasEcho = false;

      const isCurrent = () => !disposed && !canvas.radarCancelled
        && revision === this.frameRevision;
      if (!isDpcRadarTileAvailable(coords)) {
        globalThis.queueMicrotask(() => {
          if (isCurrent()) done(null, canvas);
        });
        return canvas;
      }
      const paint = (prepared) => {
        if (!isCurrent()) return;
        try {
          if (isDpcRadarTileAvailable(coords)) {
            const context = canvas.getContext("2d");
            if (!context) throw new Error("Canvas radar non disponibile");
            context.clearRect(0, 0, tileSize, tileSize);
            context.drawImage(prepared, 0, 0, tileSize, tileSize);
          }
          canvas.radarHasEcho = prepared.radarHasEcho;
          done(null, canvas);
        } catch (error) {
          done(error, canvas);
        }
      };
      prepareTile(coords, this.frameProduct, frameTime).promise.then(paint, (error) => {
        if (isCurrent()) done(error, canvas);
      });

      return canvas;
    },
  });

  return new RadarGridLayer({
    ...DPC_RADAR_SHARED_TILE_OPTIONS,
    ...layerOptions,
    tileSize,
  });
}
