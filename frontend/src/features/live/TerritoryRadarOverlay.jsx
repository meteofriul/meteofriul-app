import { CircleAlert, Info, Pause, Play } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import {
  buildFrameTimes,
  isRadarFrameLive,
  subscribeToPlaybackInterruptions,
} from "../bulletin/bulletinRadarPlayback";
import { createDpcRadarGridLayer } from "../bulletin/dpcRadarLeafletLayer";
import { getRadarFrameStatus } from "../bulletin/radarDpcV2Tiles";

const RADAR_LAYER_TIMEOUT_MS = 12_000;
const RADAR_PANE_NAME = "mf-territory-radar-pane";
const RADAR_FRAME_DURATION_MS = 700;
const RADAR_RETRY_DELAY_MS = 1_500;
const RADAR_OUTAGE_RETRY_DELAY_MS = 10_000;
const RADAR_OUTAGE_FAILURE_THRESHOLD = 3;

const FALLBACK_COPY = Object.freeze({
  frameUnavailable: "Radar momentaneamente non disponibile",
  hideLegend: "Nascondi la legenda radar",
  live: "LIVE",
  noPrecipitation: "Nessuna precipitazione rilevata",
  pause: "Metti in pausa",
  pauseButton: "Pausa",
  play: "Anima gli ultimi 90 minuti",
  showLegend: "Mostra la legenda radar",
  timelineLabel: "Sequenza radar degli ultimi 90 minuti",
  unavailable: "Radar temporaneamente non disponibile",
  waiting: "Radar in attesa del prossimo fotogramma",
});

function formatFrameTime(value) {
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return "--:--";

  return new Intl.DateTimeFormat("it-IT", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Europe/Rome",
  }).format(date);
}

function ensureRadarPane(map) {
  if (!map?.createPane) return {};

  try {
    const pane = map.getPane?.(RADAR_PANE_NAME) || map.createPane(RADAR_PANE_NAME);
    if (pane?.style) {
      pane.style.zIndex = "325";
      pane.style.pointerEvents = "none";
    }
    return { pane: RADAR_PANE_NAME };
  } catch {
    return {};
  }
}

function removeRadarLayer(map, layer) {
  if (!layer) return;

  try {
    if (typeof map?.removeLayer === "function") {
      map.removeLayer(layer);
      return;
    }
    layer.remove?.();
  } catch {
    // The map may already be disposing during a route or portal transition.
  }
}

/**
 * Pilot-only DPC radar layer for the shared territory Leaflet map.
 *
 * The parent owns both the Leaflet map and the layer toggle. This component
 * owns only radar frame playback, the DPC grid layer lifecycle, and its
 * user-facing status. It deliberately never mutates the basemap or other
 * territory layers.
 */
export function TerritoryRadarOverlay({
  enabled = false,
  id,
  leaflet = null,
  map = null,
  radarModel = null,
}) {
  const [frameIndex, setFrameIndex] = useState(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [layerStatus, setLayerStatus] = useState("loading");
  const [legendOpen, setLegendOpen] = useState(false);
  const [displayedTime, setDisplayedTime] = useState("");
  const [isRecovering, setIsRecovering] = useState(false);
  const [retryRevision, setRetryRevision] = useState(0);
  const overlayRef = useRef(null);
  const overlayFrameRef = useRef("");
  const activeTimeRef = useRef("");
  const layerTimeoutRef = useRef(null);
  const frameHadEchoRef = useRef(false);
  const frameHadErrorRef = useRef(false);
  const pendingFrameRef = useRef("");
  const frameDisplayedAtRef = useRef(0);
  const loadedFrameRef = useRef(null);
  const frameLifecycleRef = useRef(null);
  const mapZoomingRef = useRef(false);
  const playbackInterruptedRef = useRef(false);
  const failedFrameRef = useRef({ time: "", retries: 0 });
  const consecutiveFailuresRef = useRef(0);
  const handledFailureRef = useRef("");

  const product = radarModel?.product;
  const copy = { ...FALLBACK_COPY, ...(radarModel?.copy || {}) };
  const frameTimes = useMemo(() => buildFrameTimes(product), [product]);
  const latestFrameIndex = Math.max(frameTimes.length - 1, 0);
  const activeFrameIndex = frameIndex === null
    ? latestFrameIndex
    : Math.min(frameIndex, latestFrameIndex);
  const activeTime = frameTimes[activeFrameIndex] || product?.time || "";
  const displayedFrameIndex = frameTimes.indexOf(displayedTime);
  const timelineFrameIndex = isPlaying
    ? displayedFrameIndex >= 0 ? displayedFrameIndex : latestFrameIndex
    : activeFrameIndex;
  const timelineProgress = latestFrameIndex > 0
    ? (timelineFrameIndex / latestFrameIndex) * 100
    : 100;
  const isAvailable = Boolean(
    radarModel?.available
    && product
    && radarModel?.tiles?.baseUrl
    && frameTimes.length,
  );

  useEffect(() => {
    activeTimeRef.current = activeTime;
  }, [activeTime]);

  useEffect(() => {
    if (!enabled || !map?.on) return undefined;

    const interruptForZoom = () => {
      mapZoomingRef.current = true;
      playbackInterruptedRef.current = true;
      setIsPlaying(false);
    };
    const finishZoom = () => {
      mapZoomingRef.current = false;
    };

    map.on("zoomstart", interruptForZoom);
    map.on("zoom", interruptForZoom);
    map.on("zoomend", finishZoom);
    return () => {
      mapZoomingRef.current = false;
      playbackInterruptedRef.current = true;
      map.off?.("zoomstart", interruptForZoom);
      map.off?.("zoom", interruptForZoom);
      map.off?.("zoomend", finishZoom);
    };
  }, [enabled, map]);

  useEffect(() => {
    if (!enabled || !isAvailable || !map || !leaflet) return undefined;

    const L = leaflet.default || leaflet;
    let disposed = false;
    let overlay = null;

    const clearLayerTimeout = () => {
      globalThis.window?.clearTimeout(layerTimeoutRef.current);
      layerTimeoutRef.current = null;
    };
    const startLayerTimeout = () => {
      clearLayerTimeout();
      layerTimeoutRef.current = globalThis.window?.setTimeout(() => {
        if (!disposed) {
          setIsRecovering(true);
          setLayerStatus("error");
        }
      }, RADAR_LAYER_TIMEOUT_MS);
    };
    const onLoading = () => {
      pendingFrameRef.current = overlay?.frameTime || activeTimeRef.current;
      if (pendingFrameRef.current !== activeTimeRef.current) return;
      frameHadEchoRef.current = false;
      frameHadErrorRef.current = false;
      setLayerStatus("loading");
      startLayerTimeout();
    };
    const onTileError = ({ tile } = {}) => {
      if (tile?.radarFrameTime === (overlay?.frameTime || activeTimeRef.current)) {
        frameHadErrorRef.current = true;
      }
    };
    const onTileLoad = ({ tile } = {}) => {
      if (tile?.radarFrameTime === (overlay?.frameTime || activeTimeRef.current) && tile?.radarHasEcho) {
        frameHadEchoRef.current = true;
      }
    };
    const onLoad = () => {
      if (pendingFrameRef.current !== activeTimeRef.current) return;
      if (overlayFrameRef.current !== `${product.productType || ""}|${activeTimeRef.current}`) return;
      clearLayerTimeout();
      const status = getRadarFrameStatus({
        hadEcho: frameHadEchoRef.current,
        hadError: frameHadErrorRef.current,
      });
      if (status !== "error") {
        setDisplayedTime(activeTimeRef.current);
        frameDisplayedAtRef.current = globalThis.performance.now();
        loadedFrameRef.current = { key: overlayFrameRef.current, status };
        failedFrameRef.current = { time: "", retries: 0 };
        consecutiveFailuresRef.current = 0;
        handledFailureRef.current = "";
      }
      setIsRecovering(status === "error");
      setLayerStatus(status);
    };
    frameLifecycleRef.current = {
      loading: () => {
        setLayerStatus("loading");
        startLayerTimeout();
      },
      error: () => {
        clearLayerTimeout();
        setIsRecovering(true);
        setLayerStatus("error");
      },
      restore: (status) => {
        clearLayerTimeout();
        if (status === "ready" || status === "empty") {
          setIsRecovering(false);
          failedFrameRef.current = { time: "", retries: 0 };
          consecutiveFailuresRef.current = 0;
          handledFailureRef.current = "";
        }
        setLayerStatus(status);
      },
    };

    try {
      overlay = createDpcRadarGridLayer(L, {
        layerOptions: ensureRadarPane(map),
        product,
        tileBaseUrl: radarModel.tiles.baseUrl,
        tileSize: Number(radarModel.tiles.tileSize) || 256,
        time: activeTimeRef.current,
      });
      overlay.on("loading", onLoading);
      overlay.on("tileerror", onTileError);
      overlay.on("tileload", onTileLoad);
      overlay.on("load", onLoad);
      overlayRef.current = overlay;
      overlayFrameRef.current = `${product.productType || ""}|${activeTimeRef.current}`;
      pendingFrameRef.current = activeTimeRef.current;
      onLoading();
      overlay.addTo(map);
    } catch {
      clearLayerTimeout();
      globalThis.window?.setTimeout(() => {
        if (!disposed) {
          setIsRecovering(true);
          setLayerStatus("error");
        }
      }, 0);
    }

    return () => {
      disposed = true;
      frameLifecycleRef.current = null;
      clearLayerTimeout();
      overlay?.off?.("loading", onLoading);
      overlay?.off?.("tileerror", onTileError);
      overlay?.off?.("tileload", onTileLoad);
      overlay?.off?.("load", onLoad);
      removeRadarLayer(map, overlay);
      if (overlayRef.current === overlay) {
        overlayRef.current = null;
        overlayFrameRef.current = "";
        loadedFrameRef.current = null;
      }
    };
  }, [enabled, isAvailable, leaflet, map, product, radarModel?.tiles?.baseUrl, radarModel?.tiles?.tileSize]);

  useEffect(() => {
    if (!enabled || !overlayRef.current || !product || !activeTime) return undefined;

    const nextFrameKey = `${product.productType || ""}|${activeTime}`;
    if (overlayFrameRef.current === nextFrameKey && loadedFrameRef.current?.key === nextFrameKey) {
      pendingFrameRef.current = activeTime;
      frameLifecycleRef.current?.restore(loadedFrameRef.current.status);
      return undefined;
    }
    if (overlayFrameRef.current === nextFrameKey && retryRevision === 0) return undefined;

    let cancelled = false;
    const overlay = overlayRef.current;
    pendingFrameRef.current = activeTime;
    frameLifecycleRef.current?.loading();
    // Preserve the previous image and its timestamp until every visible tile
    // for the requested frame is prepared. Playback normally warms this cache.
    Promise.resolve(overlay.prefetchFrame?.(product, activeTime)).then(() => {
      if (cancelled || overlayRef.current !== overlay) return;
      frameHadEchoRef.current = false;
      frameHadErrorRef.current = false;
      overlayFrameRef.current = nextFrameKey;
      overlay.setFrame(product, activeTime);
    }, () => {
      if (!cancelled && overlayRef.current === overlay) frameLifecycleRef.current?.error();
    });
    return () => { cancelled = true; };
  }, [activeTime, enabled, product, retryRevision]);

  useEffect(() => {
    if (
      !enabled || !isPlaying || !product || frameTimes.length < 2
      || !["ready", "empty"].includes(layerStatus) || displayedTime !== activeTime
    ) return;
    const nextTime = frameTimes[(activeFrameIndex + 1) % frameTimes.length];
    // Exactly one following frame is prefetched, even while the current frame
    // is being displayed. The layer bounds retained prepared tiles in memory.
    overlayRef.current?.prefetchFrame?.(product, nextTime).catch(() => {});
  }, [activeFrameIndex, activeTime, displayedTime, enabled, frameTimes, isPlaying, layerStatus, product]);

  useEffect(() => {
    if (
      !enabled || !isPlaying || frameTimes.length < 2
      || !["ready", "empty"].includes(layerStatus) || displayedTime !== activeTime
      || mapZoomingRef.current || playbackInterruptedRef.current
    ) {
      return undefined;
    }

    const elapsed = globalThis.performance.now() - frameDisplayedAtRef.current;
    const remaining = Math.max(0, RADAR_FRAME_DURATION_MS - elapsed);
    const timeoutId = globalThis.window?.setTimeout(() => {
      if (mapZoomingRef.current || playbackInterruptedRef.current) return;
      setLayerStatus("loading");
      setFrameIndex((current) => ((current ?? latestFrameIndex) + 1) % frameTimes.length);
    }, remaining);

    return () => globalThis.window?.clearTimeout(timeoutId);
  }, [activeTime, displayedTime, enabled, frameTimes.length, isPlaying, latestFrameIndex, layerStatus]);

  useEffect(() => {
    if (
      !enabled || !isPlaying || frameTimes.length < 2 || layerStatus !== "error"
      || mapZoomingRef.current || playbackInterruptedRef.current
    ) return undefined;

    const failure = failedFrameRef.current;
    if (failure.time !== activeTime) {
      failure.time = activeTime;
      failure.retries = 0;
    }
    const failureKey = `${activeTime}|${retryRevision}`;
    if (handledFailureRef.current !== failureKey) {
      handledFailureRef.current = failureKey;
      consecutiveFailuresRef.current += 1;
    }
    const shouldRetry = failure.retries === 0;
    const delay = consecutiveFailuresRef.current >= RADAR_OUTAGE_FAILURE_THRESHOLD
      ? RADAR_OUTAGE_RETRY_DELAY_MS
      : RADAR_RETRY_DELAY_MS;
    const timeoutId = globalThis.window?.setTimeout(() => {
      if (mapZoomingRef.current || playbackInterruptedRef.current) return;
      setLayerStatus("loading");
      if (shouldRetry) {
        failure.retries = 1;
        setRetryRevision((current) => current + 1);
      } else {
        failedFrameRef.current = { time: "", retries: 0 };
        const next = (activeFrameIndex + 1) % frameTimes.length;
        // A cached image that is already on screen is not a recovered frame.
        // Keep searching after an outage instead of restarting a fast loop.
        const target = next === displayedFrameIndex
          ? (next + 1) % frameTimes.length
          : next;
        if (target === activeFrameIndex) setRetryRevision((current) => current + 1);
        else setFrameIndex(target);
      }
    }, delay);

    return () => globalThis.window?.clearTimeout(timeoutId);
  }, [activeFrameIndex, activeTime, displayedFrameIndex, enabled, frameTimes.length, isPlaying, latestFrameIndex, layerStatus, retryRevision]);

  useEffect(() => {
    if (!enabled || !isPlaying) return undefined;
    return subscribeToPlaybackInterruptions({
      onInterrupt: () => {
        playbackInterruptedRef.current = true;
        setIsPlaying(false);
      },
    });
  }, [enabled, isPlaying]);

  if (!enabled) return null;

  if (!isAvailable) {
    return (
      <section
        aria-label={radarModel?.title || "Radar precipitazioni"}
        className="mf-territory-radar-overlay mf-territory-radar-overlay--unavailable"
        id={id}
      >
        <p className="mf-territory-radar-status" role="status">
          <CircleAlert aria-hidden="true" size={16} strokeWidth={2.2} />
          <span>{radarModel?.unavailableLabel || copy.unavailable}</span>
        </p>
      </section>
    );
  }

  const activeFrameLabel = formatFrameTime(displayedTime || (isPlaying ? "" : activeTime));
  const liveFrame = isRadarFrameLive({
    activeFrameIndex,
    isStale: radarModel.isStale,
    latestFrameIndex,
    layerStatus: displayedTime && displayedTime !== activeTime ? "loading" : layerStatus,
  });
  const activeFrameAccessibleLabel = liveFrame
    ? `${activeFrameLabel} · ${copy.live}`
    : activeFrameLabel;
  const waitingForFrame = isPlaying && (
    layerStatus === "error"
    || (layerStatus === "loading" && isRecovering)
  );
  let frameStatusMessage = "";
  if (waitingForFrame) frameStatusMessage = copy.waiting;
  else if (layerStatus === "error") frameStatusMessage = copy.frameUnavailable;
  else if (layerStatus === "empty") frameStatusMessage = copy.noPrecipitation;
  const freshnessMessage = radarModel.staleNotice || "";
  const legendId = `${id || "territory-radar"}-legend`;
  const hasLegend = Boolean(radarModel.legend?.labels?.length);

  return (
    <section
      aria-busy={layerStatus === "loading"}
      aria-label={radarModel.title || "Radar precipitazioni"}
      className="mf-territory-radar-overlay"
      id={id}
    >
      <div className="mf-territory-radar-player">
        <button
          aria-label={isPlaying ? copy.pause : radarModel.playLabel || copy.play}
          className="mf-territory-radar-play"
          onClick={() => setIsPlaying((current) => {
            const next = !current;
            playbackInterruptedRef.current = !next;
            if (next) {
              frameDisplayedAtRef.current = globalThis.performance.now();
              failedFrameRef.current = { time: "", retries: 0 };
              consecutiveFailuresRef.current = 0;
              handledFailureRef.current = "";
            }
            return next;
          })}
          title={isPlaying ? copy.pause : radarModel.playLabel || copy.play}
          type="button"
        >
          {isPlaying
            ? <Pause aria-hidden="true" fill="currentColor" size={18} />
            : <Play aria-hidden="true" fill="currentColor" size={18} />}
          <span>{isPlaying ? copy.pauseButton : radarModel.animationLabel}</span>
        </button>

        <div className="mf-territory-radar-timeline">
          <input
            aria-label={copy.timelineLabel}
            aria-valuetext={activeFrameAccessibleLabel}
            className="mf-territory-radar-timeline-range"
            max={latestFrameIndex}
            min="0"
            onChange={(event) => {
              const nextFrameIndex = Number(event.currentTarget.value);
              playbackInterruptedRef.current = true;
              setIsPlaying(false);
              setLayerStatus("loading");
              setFrameIndex(nextFrameIndex === latestFrameIndex ? null : nextFrameIndex);
            }}
            style={{ "--mf-territory-radar-progress": `${timelineProgress}%` }}
            type="range"
            value={timelineFrameIndex}
          />
        </div>

        <span aria-hidden="true" className="mf-territory-radar-timestamp">
          <strong>{activeFrameLabel}</strong>
          <span className="mf-territory-radar-live">{liveFrame ? `● ${copy.live}` : ""}</span>
        </span>

        {hasLegend ? (
          <button
            aria-controls={legendId}
            aria-expanded={legendOpen}
            aria-label={legendOpen ? copy.hideLegend : copy.showLegend}
            className="mf-territory-radar-info"
            onClick={() => setLegendOpen((current) => !current)}
            title={legendOpen ? copy.hideLegend : copy.showLegend}
            type="button"
          >
            <Info aria-hidden="true" size={17} strokeWidth={2.2} />
          </button>
        ) : null}
      </div>

      {hasLegend && legendOpen ? (
        <div
          aria-label={radarModel.legend.ariaLabel}
          className="mf-territory-radar-scale"
          id={legendId}
          role="img"
        >
          <span aria-hidden="true" className="mf-territory-radar-scale-bar" />
          <span aria-hidden="true" className="mf-territory-radar-scale-labels">
            <span>{radarModel.legend.labels[0]}</span>
            <span>{radarModel.legend.labels.at(-1)}</span>
          </span>
        </div>
      ) : null}

        <div className="mf-territory-radar-statuses" role="status">
            <p
              aria-hidden={frameStatusMessage ? undefined : true}
              className="mf-territory-radar-status mf-territory-radar-status--frame"
            >
              {layerStatus === "error"
                ? <CircleAlert aria-hidden="true" size={15} strokeWidth={2.2} />
                : null}
              <span>{frameStatusMessage}</span>
            </p>
          {freshnessMessage ? (
            <p className="mf-territory-radar-status mf-territory-radar-status--freshness">
              <span>{freshnessMessage}</span>
            </p>
          ) : null}
        </div>
    </section>
  );
}
