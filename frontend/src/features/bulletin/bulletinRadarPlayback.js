export const RADAR_FRAME_WINDOW_MINUTES = 90;

export const RADAR_ZOOM = 7;

export const RADAR_MAP_OPTIONS = Object.freeze({
  attributionControl: true,
  boxZoom: false,
  doubleClickZoom: false,
  dragging: false,
  keyboard: false,
  maxZoom: RADAR_ZOOM,
  minZoom: RADAR_ZOOM,
  scrollWheelZoom: false,
  tapHold: false,
  touchZoom: false,
  zoomControl: false,
});

export const RADAR_TILE_OPTIONS = Object.freeze({
  maxZoom: RADAR_ZOOM,
  minZoom: RADAR_ZOOM,
  noWrap: true,
  updateWhenZooming: false,
});

export function isRadarFrameLive({
  activeFrameIndex,
  isStale,
  latestFrameIndex,
  layerStatus,
}) {
  return activeFrameIndex === latestFrameIndex
    && !isStale
    && (layerStatus === "ready" || layerStatus === "empty");
}

export function subscribeToPlaybackInterruptions({
  documentTarget = globalThis.document,
  onInterrupt,
  windowTarget = globalThis.window,
} = {}) {
  if (typeof onInterrupt !== "function") return () => {};

  let interrupted = false;
  const captureOptions = { capture: true, passive: true };
  const passiveOptions = { passive: true };
  const interruptOnce = () => {
    if (interrupted) return;
    interrupted = true;
    onInterrupt();
  };

  documentTarget?.addEventListener?.("scroll", interruptOnce, captureOptions);
  documentTarget?.addEventListener?.("touchmove", interruptOnce, captureOptions);
  windowTarget?.addEventListener?.("wheel", interruptOnce, passiveOptions);

  return () => {
    documentTarget?.removeEventListener?.("scroll", interruptOnce, captureOptions);
    documentTarget?.removeEventListener?.("touchmove", interruptOnce, captureOptions);
    windowTarget?.removeEventListener?.("wheel", interruptOnce, passiveOptions);
  };
}

export function buildFrameTimes(product) {
  const latest = new Date(product?.time || "").getTime();
  if (!Number.isFinite(latest)) return [];

  const stepMinutes = Math.max(1, Number(product?.periodMinutes) || 5);
  const frameCount = Math.floor(RADAR_FRAME_WINDOW_MINUTES / stepMinutes) + 1;

  return Array.from({ length: frameCount }, (_, index) => (
    new Date(latest - (frameCount - index - 1) * stepMinutes * 60 * 1000).toISOString()
  ));
}
