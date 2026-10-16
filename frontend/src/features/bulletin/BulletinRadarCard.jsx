import {
  CircleAlert,
  ExternalLink,
  Palette,
  Pause,
  Play,
  Radar,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import {
  RADAR_FRAME_WINDOW_MINUTES,
  RADAR_MAP_OPTIONS,
  RADAR_TILE_OPTIONS,
  RADAR_ZOOM,
  buildFrameTimes,
  isRadarFrameLive,
  subscribeToPlaybackInterruptions,
} from "./bulletinRadarPlayback";
import {
  getRadarFrameStatus,
} from "./radarDpcV2Tiles";
import { createDpcRadarGridLayer } from "./dpcRadarLeafletLayer";

const FVG_BOUNDS = [[45.55, 12.25], [46.75, 13.95]];
const COMPACT_TIMELINE_TICK_INTERVAL_MINUTES = 30;
const COMPACT_TIMELINE_TICK_SEGMENTS = Math.max(
  1,
  Math.floor(RADAR_FRAME_WINDOW_MINUTES / COMPACT_TIMELINE_TICK_INTERVAL_MINUTES),
);
const COMPACT_TIMELINE_TICK_COUNT = COMPACT_TIMELINE_TICK_SEGMENTS - 1;

function RadarMap({ activeTime, copy, location, onLayerStatusChange, product, tiles }) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const overlayRef = useRef(null);
  const activeTimeRef = useRef(activeTime);
  const layerTimeoutRef = useRef(null);
  const frameHadEchoRef = useRef(false);
  const loadHadErrorRef = useRef(false);
  const statusCallbackRef = useRef(onLayerStatusChange);
  const productRef = useRef(product);
  const tileBaseUrl = tiles.baseUrl;
  const tileSize = Number(tiles.tileSize) || 256;

  useEffect(() => {
    activeTimeRef.current = activeTime;
    productRef.current = product;
  }, [activeTime, product]);

  useEffect(() => {
    statusCallbackRef.current = onLayerStatusChange;
  }, [onLayerStatusChange]);

  useEffect(() => {
    let cancelled = false;

    async function mountMap() {
      const leafletModule = await import("leaflet");
      if (cancelled || !containerRef.current || mapRef.current) return;

      const L = leafletModule.default || leafletModule;
      const map = L.map(containerRef.current, { ...RADAR_MAP_OPTIONS });

      L.imageOverlay("/maps/fvg-blue-marble.jpg", [[44, 10], [48, 16]], {
        pane: "tilePane",
        className: "mf-radar-satellite-base",
        interactive: false,
        attribution: 'Sfondo: <a href="https://science.nasa.gov/earth/earth-observatory/collections/blue-marble/" target="_blank" rel="noopener noreferrer">NASA Earth Observatory</a>',
      }).addTo(map);

      const overlay = createDpcRadarGridLayer(L, {
        layerOptions: RADAR_TILE_OPTIONS,
        product: productRef.current,
        tileBaseUrl,
        tileSize,
        time: activeTimeRef.current,
      });

      const clearLayerTimeout = () => {
        globalThis.window?.clearTimeout(layerTimeoutRef.current);
        layerTimeoutRef.current = null;
      };
      const startLayerTimeout = () => {
        clearLayerTimeout();
        layerTimeoutRef.current = globalThis.window?.setTimeout(() => {
          statusCallbackRef.current?.("error");
        }, 12000);
      };

      overlay.on("loading", () => {
        frameHadEchoRef.current = false;
        loadHadErrorRef.current = false;
        statusCallbackRef.current?.("loading");
        startLayerTimeout();
      });
      overlay.on("tileerror", ({ tile }) => {
        if (tile?.radarFrameTime === activeTimeRef.current) {
          loadHadErrorRef.current = true;
        }
      });
      overlay.on("tileload", ({ tile }) => {
        if (tile?.radarFrameTime === activeTimeRef.current && tile?.radarHasEcho) {
          frameHadEchoRef.current = true;
        }
      });
      overlay.on("load", () => {
        clearLayerTimeout();
        statusCallbackRef.current?.(getRadarFrameStatus({
          hadEcho: frameHadEchoRef.current,
          hadError: loadHadErrorRef.current,
        }));
      });
      statusCallbackRef.current?.("loading");
      startLayerTimeout();
      overlay.addTo(map);

      if (location) {
        L.circleMarker([location.lat, location.lon], {
          color: "#ffffff",
          fillColor: "#0073cf",
          fillOpacity: 1,
          opacity: 1,
          radius: 6,
          weight: 3,
        }).addTo(map);
      }

      map.fitBounds(FVG_BOUNDS, {
        animate: false,
        maxZoom: RADAR_ZOOM,
        padding: [10, 10],
      });
      mapRef.current = map;
      overlayRef.current = overlay;
    }

    mountMap();

    return () => {
      cancelled = true;
      globalThis.window?.clearTimeout(layerTimeoutRef.current);
      layerTimeoutRef.current = null;
      overlayRef.current = null;
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, [copy.mapLabel, location, tileBaseUrl, tileSize]);

  useEffect(() => {
    if (!overlayRef.current) return;

    globalThis.window?.clearTimeout(layerTimeoutRef.current);
    layerTimeoutRef.current = globalThis.window?.setTimeout(() => {
      statusCallbackRef.current?.("error");
    }, 12000);
    statusCallbackRef.current?.("loading");
    overlayRef.current?.setFrame(product, activeTime);
  }, [activeTime, product]);

  return <div aria-label={copy.mapLabel} className="mf-bulletin-radar-map" ref={containerRef} role="img" />;
}

export function BulletinRadarCard({
  language = "it",
  model,
  overlayControls = false,
  persistent = false,
}) {
  const [frameIndex, setFrameIndex] = useState(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [layerStatus, setLayerStatus] = useState("loading");
  const activeProduct = model?.product;
  const frameTimes = useMemo(() => buildFrameTimes(activeProduct), [activeProduct]);
  const latestFrameIndex = Math.max(frameTimes.length - 1, 0);
  const activeFrameIndex = frameIndex === null
    ? latestFrameIndex
    : Math.min(frameIndex, latestFrameIndex);
  const activeTime = frameTimes[activeFrameIndex] || activeProduct?.time || "";
  const timelineProgress = latestFrameIndex > 0
    ? (activeFrameIndex / latestFrameIndex) * 100
    : 100;

  useEffect(() => {
    if (!isPlaying || frameTimes.length < 2 || layerStatus === "loading") {
      return undefined;
    }

    const timeoutId = globalThis.window?.setTimeout(() => {
      setLayerStatus("loading");
      setFrameIndex((current) => ((current ?? latestFrameIndex) + 1) % frameTimes.length);
    }, layerStatus === "error" ? 400 : 700);

    return () => globalThis.window?.clearTimeout(timeoutId);
  }, [frameTimes.length, isPlaying, latestFrameIndex, layerStatus]);

  useEffect(() => {
    if (!isPlaying) return undefined;

    return subscribeToPlaybackInterruptions({
      onInterrupt: () => setIsPlaying(false),
    });
  }, [isPlaying]);

  if (persistent && !model?.available) {
    const title = language === "fur" ? "Radar des precipitazions" : "Radar precipitazioni";
    return <section
      aria-label={title}
      className={`mf-bulletin-radar-card ${overlayControls ? "mf-bulletin-radar-card--overlay-controls" : ""}`.trim()}
    >
      <header className="mf-bulletin-radar-card__header"><div>
        <span className="mf-bulletin-radar-card__eyebrow"><Radar aria-hidden="true" size={15} />{language === "fur" ? "Osservazion in timp reâl" : "Osservazione in tempo reale"}</span>
        <h2>{title}</h2>
      </div></header>
      <div className={`mf-bulletin-radar-window mf-bulletin-radar-window--pending ${overlayControls ? "mf-bulletin-radar-window--overlay-controls" : ""}`.trim()}>
        <p role="status">{model?.unavailableLabel || (language === "fur" ? "Daûr a cjariâ i dâts radar…" : "Caricamento dati radar…")}</p>
      </div>
      {overlayControls ? null : <div className="mf-bulletin-radar-controls-placeholder" aria-hidden="true" />}
    </section>;
  }
  if (!model) return null;

  if (!model.available) {
    return (
      <section aria-label={model.title} className="mf-bulletin-radar-card mf-bulletin-radar-card--unavailable">
        <Radar aria-hidden="true" size={22} strokeWidth={2.2} />
        <div>
          <h2>{model.title}</h2>
          <p role="status">{model.unavailableLabel}</p>
        </div>
      </section>
    );
  }

  const activeFrameLabel = new Intl.DateTimeFormat("it-IT", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Europe/Rome",
  }).format(new Date(activeTime));
  const isLiveFrame = isRadarFrameLive({
    activeFrameIndex,
    isStale: model.isStale,
    latestFrameIndex,
    layerStatus,
  });
  const activeFrameAccessibleLabel = overlayControls && isLiveFrame
    ? `${activeFrameLabel} · ${model.copy.live}`
    : activeFrameLabel;
  const playControl = (
    <button
      aria-label={isPlaying ? model.copy.pause : model.playLabel}
      className="mf-bulletin-radar-play"
      onClick={() => setIsPlaying((current) => !current)}
      title={isPlaying ? model.copy.pause : model.playLabel}
      type="button"
    >
      {isPlaying ? <Pause aria-hidden="true" size={18} fill="currentColor" /> : <Play aria-hidden="true" size={18} fill="currentColor" />}
      <span>{isPlaying ? model.copy.pauseButton : model.animationLabel}</span>
    </button>
  );
  const timelineRange = (
    <input
      aria-label={model.copy.timelineLabel}
      aria-valuetext={activeFrameAccessibleLabel}
      className="mf-bulletin-radar-timeline__range"
      max={latestFrameIndex}
      min="0"
      onChange={(event) => {
        const nextFrameIndex = Number(event.currentTarget.value);
        setIsPlaying(false);
        setLayerStatus("loading");
        setFrameIndex(nextFrameIndex === latestFrameIndex ? null : nextFrameIndex);
      }}
      style={{ "--mf-radar-progress": `${timelineProgress}%` }}
      type="range"
      value={activeFrameIndex}
    />
  );
  const timelineControl = overlayControls ? (
    <div className="mf-bulletin-radar-timeline mf-bulletin-radar-timeline--compact">
      <span aria-hidden="true" className="mf-bulletin-radar-timeline__compact-start">
        −{RADAR_FRAME_WINDOW_MINUTES} min
      </span>
      <div className="mf-bulletin-radar-timeline__track">
        {timelineRange}
        <span
          aria-hidden="true"
          className="mf-bulletin-radar-timeline__ticks"
          style={{ "--mf-radar-tick-segments": COMPACT_TIMELINE_TICK_SEGMENTS }}
        >
          {Array.from({ length: COMPACT_TIMELINE_TICK_COUNT }, (_, tickIndex) => (
            <span key={tickIndex} />
          ))}
        </span>
      </div>
      <div aria-hidden="true" className="mf-bulletin-radar-timestamp">
        <strong>{activeFrameLabel}</strong>
        {isLiveFrame ? (
          <span className="mf-bulletin-radar-live">
            <span className="mf-bulletin-radar-live__dot" />
            {model.copy.live}
          </span>
        ) : null}
      </div>
    </div>
  ) : (
    <div className="mf-bulletin-radar-timeline">
      {timelineRange}
      <div aria-hidden="true" className="mf-bulletin-radar-timeline__labels">
        <span>{model.copy.timelineStart}</span>
        <strong>{activeFrameLabel}</strong>
        <span>{model.copy.timelineEnd}</span>
      </div>
    </div>
  );

  return (
    <section
      aria-labelledby="bulletin-radar-title"
      className={`mf-bulletin-radar-card ${overlayControls ? "mf-bulletin-radar-card--overlay-controls" : ""}`.trim()}
    >
      <header className="mf-bulletin-radar-card__header">
        <div>
          <span className="mf-bulletin-radar-card__eyebrow">
            <Radar aria-hidden="true" size={15} strokeWidth={2.3} />
            {model.eyebrowLabel}
          </span>
          <h2 id="bulletin-radar-title">{model.title}</h2>
        </div>
      </header>

      {model.staleNotice ? (
        <div className="mf-bulletin-radar-stale" role="status">
          <CircleAlert aria-hidden="true" size={16} strokeWidth={2.2} />
          <span>{model.staleNotice}</span>
        </div>
      ) : null}

      <div className={`mf-bulletin-radar-window ${overlayControls ? "mf-bulletin-radar-window--overlay-controls" : ""}`.trim()}>
        <RadarMap
          activeTime={activeTime}
          copy={model.copy}
          location={model.location}
          onLayerStatusChange={setLayerStatus}
          product={activeProduct}
          tiles={model.tiles}
        />
        {layerStatus === "error" ? (
          <span className="mf-bulletin-radar-frame-status" role="status">
            <CircleAlert aria-hidden="true" size={16} strokeWidth={2.2} />
            {model.copy.frameUnavailable}
          </span>
        ) : null}
        {layerStatus === "empty" ? (
          <span className="mf-bulletin-radar-frame-status" role="status">
            {model.copy.noPrecipitation}
          </span>
        ) : null}
        {overlayControls ? (
          <div className="mf-bulletin-radar-floating-controls">
            {playControl}
            {timelineControl}
          </div>
        ) : playControl}
      </div>

      {overlayControls ? null : timelineControl}

      <div
        aria-label={model.legend.ariaLabel}
        className={`mf-bulletin-radar-scale ${overlayControls ? "mf-bulletin-radar-scale--compact" : ""}`.trim()}
        role="img"
      >
        {overlayControls ? null : (
          <div className="mf-bulletin-radar-scale__header">
            <span>
              <Palette aria-hidden="true" size={15} strokeWidth={2.2} />
              {model.legend.label}
            </span>
            <strong>{model.legend.min}&ndash;{model.legend.max} {model.legend.unit}</strong>
          </div>
        )}
        <span aria-hidden="true" className="mf-bulletin-radar-scale__bar" />
        <div aria-hidden="true" className="mf-bulletin-radar-scale__labels">
          {(overlayControls
            ? [model.legend.labels[0], model.legend.labels.at(-1)]
            : model.legend.labels
          ).map((label) => <span key={label}>{label}</span>)}
        </div>
      </div>

      <footer className="mf-bulletin-radar-card__footer">
        <span className="mf-bulletin-radar-card__credits">
          {model.sourceUrl ? (
            <a href={model.sourceUrl} rel="noreferrer" target="_blank">
              {model.sourceLabel}
              <ExternalLink aria-hidden="true" size={13} strokeWidth={2.2} />
            </a>
          ) : <span>{model.sourceLabel}</span>}
        </span>
      </footer>
    </section>
  );
}
