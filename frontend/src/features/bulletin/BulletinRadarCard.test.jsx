import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { BulletinRadarCard } from "./BulletinRadarCard";

it("keeps the pilot radar shell visible before data and after a network error", () => {
  for (const model of [null, { available: false, unavailableLabel: "Radar non disponibile" }]) {
    const html = renderToStaticMarkup(<BulletinRadarCard model={model} persistent />);
    expect(html).toContain("Radar precipitazioni");
    expect(html).toContain("mf-bulletin-radar-window");
    expect(html).toContain('role="status"');
  }
  expect(renderToStaticMarkup(<BulletinRadarCard model={null} />)).toBe("");
});
import {
  RADAR_MAP_OPTIONS,
  RADAR_TILE_OPTIONS,
  RADAR_ZOOM,
  buildFrameTimes,
  isRadarFrameLive,
  subscribeToPlaybackInterruptions,
} from "./bulletinRadarPlayback";

function buildModel() {
  return {
    animationLabel: "Ultimi 90 minuti",
    available: true,
    copy: {
      eyebrow: "Osservazione in tempo reale",
      frameUnavailable: "Fotogramma radar non disponibile",
      live: "LIVE",
      mapLabel: "Mappa radar",
      noPrecipitation: "Nessuna precipitazione rilevata",
      pause: "Metti in pausa",
      pauseButton: "Pausa",
      play: "Anima gli ultimi 90 minuti",
      timelineEnd: "Ora",
      timelineLabel: "Sequenza radar degli ultimi 90 minuti",
      timelineStart: "90 min fa",
    },
    eyebrowLabel: "Osservazione in tempo reale",
    location: { lat: 45.9567, lon: 12.6605 },
    playLabel: "Anima gli ultimi 90 minuti",
    legend: {
      ariaLabel: "Scala dell'intensità della pioggia da 0 a 100 millimetri all'ora",
      label: "Intensità pioggia",
      labels: ["Debole", "Moderata", "Intensa", "Forte", "Molto forte"],
      max: 100,
      min: 0,
      unit: "mm/h",
    },
    product: {
      id: "rain",
      label: "Pioggia",
      layer: "radar:sri",
      periodMinutes: 5,
      productType: "SRI",
      style: "",
      time: "2026-08-03T07:10:00Z",
      unit: "mm/h",
    },
    sourceLabel: "Radar-DPC",
    sourceUrl: "https://example.test/radar",
    tiles: {
      baseUrl: "https://tiles.example.test",
      encoding: "red_channel_normalized",
      format: "webp",
      tileSize: 256,
      zoom: 7,
    },
    title: "Radar precipitazioni",
  };
}

describe("BulletinRadarCard", () => {
  it("renders one animated SRI view with the official quantitative scale", () => {
    const markup = renderToStaticMarkup(<BulletinRadarCard model={buildModel()} />);

    expect(markup).toContain("Radar precipitazioni");
    expect(markup).toContain("Ultimi 90 minuti");
    expect(markup).not.toContain("Dati radar non validati");
    expect(markup).toContain("Intensità pioggia");
    expect(markup).toContain("Sequenza radar degli ultimi 90 minuti");
    expect(markup).toContain('aria-valuetext="09:10"');
    expect(markup).toContain("90 min fa");
    expect(markup).toContain("Ora");
    expect(markup).toContain('type="range"');
    expect(markup).toContain("0–100 mm/h");
    expect(markup).toContain("Debole");
    expect(markup).toContain("Moderata");
    expect(markup).toContain("Intensa");
    expect(markup).toContain("Forte");
    expect(markup).toContain("Molto forte");
    expect(markup).not.toContain("Ultima ora");
    expect(markup).not.toContain("tablist");
    expect(markup).not.toContain("CC BY-SA 4.0");
    expect(markup).toContain("mf-bulletin-radar-map");
    expect(markup).not.toContain("fullscreen");
    expect(markup).not.toContain("aria-pressed");
    expect(markup).not.toContain("mf-bulletin-radar-floating-controls");
  });

  it("integrates play and the single timeline over the map only when requested", () => {
    const markup = renderToStaticMarkup(
      <BulletinRadarCard model={buildModel()} overlayControls />,
    );

    expect(markup).toContain("mf-bulletin-radar-card--overlay-controls");
    expect(markup).toContain("mf-bulletin-radar-window--overlay-controls");
    expect(markup).toContain("mf-bulletin-radar-floating-controls");
    expect(markup).toContain("mf-bulletin-radar-timeline--compact");
    expect(markup).toContain("mf-bulletin-radar-timestamp");
    expect(markup.match(/mf-bulletin-radar-timeline__ticks/g)).toHaveLength(1);
    expect(markup).toContain("--mf-radar-tick-segments:3");
    expect(markup.match(/mf-bulletin-radar-timeline__range/g)).toHaveLength(1);
    expect(markup.indexOf("mf-bulletin-radar-map")).toBeLessThan(
      markup.indexOf("mf-bulletin-radar-floating-controls"),
    );
    expect(markup.indexOf("mf-bulletin-radar-floating-controls")).toBeLessThan(
      markup.indexOf("mf-bulletin-radar-scale"),
    );
    expect(markup).toContain('aria-valuetext="09:10"');
    expect(markup).not.toContain("mf-bulletin-radar-timeline__labels");
    expect(markup).toContain('class="mf-bulletin-radar-timeline__compact-start">−90 min</span>');
    expect(markup).not.toContain(">90 min fa<");
    expect(markup).not.toContain(">Ora<");
    expect(markup).toContain("mf-bulletin-radar-scale--compact");
    expect(markup).not.toContain("Intensità pioggia");
    expect(markup).not.toContain("0–100 mm/h");
    expect(markup).toContain("Debole");
    expect(markup).not.toContain("Moderata");
    expect(markup).toContain("Molto forte");
  });

  it("labels only the loaded latest frame of a fresh sequence as live", () => {
    const latestFrame = {
      activeFrameIndex: 18,
      isStale: false,
      latestFrameIndex: 18,
    };

    expect(isRadarFrameLive({ ...latestFrame, layerStatus: "ready" })).toBe(true);
    expect(isRadarFrameLive({ ...latestFrame, layerStatus: "empty" })).toBe(true);
    expect(isRadarFrameLive({ ...latestFrame, layerStatus: "loading" })).toBe(false);
    expect(isRadarFrameLive({ ...latestFrame, layerStatus: "error" })).toBe(false);
    expect(isRadarFrameLive({ ...latestFrame, isStale: true, layerStatus: "ready" })).toBe(false);
    expect(isRadarFrameLive({
      ...latestFrame,
      activeFrameIndex: 17,
      layerStatus: "ready",
    })).toBe(false);
  });

  it("builds a complete 90-minute sequence from 19 five-minute frames", () => {
    const frames = buildFrameTimes(buildModel().product);

    expect(frames).toHaveLength(19);
    expect(frames[0]).toBe("2026-08-03T05:40:00.000Z");
    expect(frames.at(-1)).toBe("2026-08-03T07:10:00.000Z");
    expect(Date.parse(frames.at(-1)) - Date.parse(frames[0])).toBe(90 * 60 * 1000);
  });

  it("locks map and tile layers to the same regional zoom", () => {
    expect(RADAR_ZOOM).toBe(7);
    expect(RADAR_MAP_OPTIONS).toMatchObject({
      boxZoom: false,
      doubleClickZoom: false,
      dragging: false,
      keyboard: false,
      maxZoom: 7,
      minZoom: 7,
      scrollWheelZoom: false,
      touchZoom: false,
      zoomControl: false,
    });
    expect(RADAR_TILE_OPTIONS).toEqual({
      maxZoom: 7,
      minZoom: 7,
      noWrap: true,
      updateWhenZooming: false,
    });
  });

  it.each([
    ["touch movement", "document", "touchmove"],
    ["page scrolling", "document", "scroll"],
    ["mouse-wheel scrolling", "window", "wheel"],
  ])("stops playback on %s without blocking the gesture", (_label, targetName, eventName) => {
    const documentTarget = new EventTarget();
    const windowTarget = new EventTarget();
    const onInterrupt = vi.fn();
    const cleanup = subscribeToPlaybackInterruptions({
      documentTarget,
      onInterrupt,
      windowTarget,
    });
    const event = new Event(eventName, { cancelable: true });
    const target = targetName === "document" ? documentTarget : windowTarget;

    target.dispatchEvent(event);
    target.dispatchEvent(new Event(eventName, { cancelable: true }));

    expect(onInterrupt).toHaveBeenCalledTimes(1);
    expect(event.defaultPrevented).toBe(false);
    cleanup();
  });

  it("removes playback interruption listeners during cleanup", () => {
    const documentTarget = new EventTarget();
    const windowTarget = new EventTarget();
    const onInterrupt = vi.fn();
    const cleanup = subscribeToPlaybackInterruptions({
      documentTarget,
      onInterrupt,
      windowTarget,
    });

    cleanup();
    documentTarget.dispatchEvent(new Event("touchmove"));
    documentTarget.dispatchEvent(new Event("scroll"));
    windowTarget.dispatchEvent(new Event("wheel"));

    expect(onInterrupt).not.toHaveBeenCalled();
  });

  it("renders no card before data or error is known", () => {
    expect(renderToStaticMarkup(<BulletinRadarCard model={null} />)).toBe("");
  });

  it("keeps the last loop visible while declaring stale radar data", () => {
    const markup = renderToStaticMarkup(<BulletinRadarCard model={{
      ...buildModel(),
      animationLabel: "Rivedi 90 minuti",
      staleNotice: "Radar non aggiornato. Stai rivedendo l'ultima sequenza disponibile.",
    }} />);

    expect(markup).toContain("Radar non aggiornato");
    expect(markup).toContain("Rivedi 90 minuti");
  });

  it("renders a small unavailable state without affecting the bulletin", () => {
    const markup = renderToStaticMarkup(<BulletinRadarCard model={{
      available: false,
      title: "Radar precipitazioni",
      unavailableDetail: "Il Bollettino resta disponibile.",
      unavailableLabel: "Radar temporaneamente non disponibile",
    }} />);

    expect(markup).toContain("Radar temporaneamente non disponibile");
    expect(markup).toContain("<h2>Radar precipitazioni</h2>");
  });
});
