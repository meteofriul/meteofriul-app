// @vitest-environment jsdom

import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getLiveViewCopy } from "../../copy/liveViewCopy";
import { TerritoryImmersiveMap } from "./TerritoryImmersiveMap";

const harness = vi.hoisted(() => ({ map: null }));
vi.mock("leaflet", () => ({
  default: {
    circleMarker: () => ({ addTo() { return this; }, remove() {} }),
    map: vi.fn(() => {
      harness.map = {
        attributionControl: { setPrefix: vi.fn() },
        fitBounds: vi.fn(),
        getZoom: () => 8,
        invalidateSize: vi.fn(),
        latLngToContainerPoint: vi.fn(() => ({ x: 100, y: 100 })),
        on: vi.fn(),
        off: vi.fn(),
        remove: vi.fn(),
        setView: vi.fn(),
        setZoom: vi.fn(),
      };
      return harness.map;
    }),
  },
}));
vi.mock("./territoryBasemapLayer", () => ({ mountTerritoryBasemapLayer: () => () => {} }));
vi.mock("../../app/usePilotBackHandler", () => ({ usePilotBackHandler() {} }));

const EMPTY = Object.freeze([]);
const LOCATION = Object.freeze({ city: "Torino", lat: 45.07, lon: 7.68 });
const REPORT = Object.freeze({
  id: "test-rain",
  groupId: "test-rain",
  typeId: "rain",
  typeLabel: "Pioggia",
  place: "Torino",
  count: 1,
  countLabel: "1 segnalazione recente",
  createdAt: Date.now(),
  expiresAt: Date.now() + 3_600_000,
  lat: 45.07,
  lon: 7.68,
  sourceKeys: ["test-source"],
});
const MARKERS = Object.freeze([REPORT]);

describe("TerritoryImmersiveMap visible reports acknowledgement", () => {
  let root;
  let container;
  let frames;
  let nextFrame;
  let props;
  let visibility;
  let rect;
  let observerCallback;
  let externalModal;

  beforeEach(() => {
    globalThis.IS_REACT_ACT_ENVIRONMENT = true;
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
    frames = new Map();
    nextFrame = 1;
    visibility = "visible";
    rect = { width: 400, height: 600, left: 20, top: 100, right: 420, bottom: 700 };
    externalModal = null;
    vi.spyOn(document, "visibilityState", "get").mockImplementation(() => visibility);
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(() => rect);
    vi.stubGlobal("requestAnimationFrame", (callback) => {
      const id = nextFrame++;
      frames.set(id, callback);
      return id;
    });
    vi.stubGlobal("cancelAnimationFrame", (id) => frames.delete(id));
    vi.stubGlobal("IntersectionObserver", class {
      constructor(callback) { observerCallback = callback; }
      observe() {}
      disconnect() {}
    });
    props = {
      communityAvailability: "ready",
      communityCopy: getLiveViewCopy("it"),
      inline: true,
      location: LOCATION,
      markers: MARKERS,
      reportItems: MARKERS,
      mapWebcams: EMPTY,
      webcamList: EMPTY,
      webcamGroups: EMPTY,
      onReportsViewed: vi.fn(),
    };
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    container.remove();
    externalModal?.remove();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    delete globalThis.IS_REACT_ACT_ENVIRONMENT;
  });

  async function render(overrides = {}) {
    props = { ...props, ...overrides };
    await act(async () => {
      root.render(<TerritoryImmersiveMap {...props} />);
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
  }

  async function paint() {
    await act(async () => {
      const callbacks = [...frames.values()];
      frames.clear();
      callbacks.forEach((callback) => callback());
    });
  }

  async function click(selector) {
    await act(async () => container.querySelector(selector).click());
  }

  it("waits for the positioned map and the next frame before acknowledging", async () => {
    await render();
    expect(harness.map.setView).toHaveBeenCalled();
    expect(harness.map.latLngToContainerPoint).toHaveBeenCalledWith([REPORT.lat, REPORT.lon]);
    expect(props.onReportsViewed).not.toHaveBeenCalled();
    props.onReportsViewed.mockImplementation(() => {
      const marker = container.querySelector(".mf-live-community-map__marker");
      expect(marker.style.left).toBe("100px");
      expect(marker.style.top).toBe("100px");
    });
    await paint();
    expect(props.onReportsViewed).toHaveBeenCalledTimes(1);
    expect(props.onReportsViewed).toHaveBeenCalledWith();
  });

  it.each(["loading", "error", "stale"])("does not acknowledge %s data", async (status) => {
    await render({ communityAvailability: status });
    await paint();
    expect(props.onReportsViewed).not.toHaveBeenCalled();
    await render({ communityAvailability: "ready" });
    await paint();
    expect(props.onReportsViewed).toHaveBeenCalledTimes(1);
  });

  it("waits while the document is hidden and acknowledges on return", async () => {
    visibility = "hidden";
    await render();
    await paint();
    expect(props.onReportsViewed).not.toHaveBeenCalled();
    visibility = "visible";
    document.dispatchEvent(new Event("visibilitychange"));
    await paint();
    expect(props.onReportsViewed).toHaveBeenCalledTimes(1);
  });

  it("cancels a queued acknowledgement when the app goes to the background", async () => {
    await render();
    visibility = "hidden";
    document.dispatchEvent(new Event("visibilitychange"));
    await paint();
    expect(props.onReportsViewed).not.toHaveBeenCalled();
  });

  it("does not acknowledge an offscreen map until it enters the viewport", async () => {
    rect = { ...rect, top: 2000, bottom: 2600 };
    await render();
    await paint();
    expect(props.onReportsViewed).not.toHaveBeenCalled();
    rect = { ...rect, top: 100, bottom: 700 };
    observerCallback();
    await paint();
    expect(props.onReportsViewed).toHaveBeenCalledTimes(1);
  });

  it("does not acknowledge behind a report form and resumes after closing it", async () => {
    await render({ reportOpen: true });
    await paint();
    expect(props.onReportsViewed).not.toHaveBeenCalled();
    await render({ reportOpen: false });
    await paint();
    expect(props.onReportsViewed).toHaveBeenCalledTimes(1);
  });

  it("acknowledges after an external onboarding modal is removed without a map rerender", async () => {
    externalModal = document.createElement("div");
    externalModal.innerHTML = '<section role="dialog" aria-modal="true">Onboarding</section>';
    document.body.append(externalModal);
    await render();
    await paint();
    expect(props.onReportsViewed).not.toHaveBeenCalled();
    await act(async () => externalModal.remove());
    await paint();
    expect(props.onReportsViewed).toHaveBeenCalledTimes(1);
  });

  it.each(["aria-modal", "open"])("rechecks when an external dialog closes through its %s attribute", async (attribute) => {
    externalModal = document.createElement(attribute === "open" ? "dialog" : "section");
    externalModal.setAttribute(attribute, attribute === "open" ? "" : "true");
    document.body.append(externalModal);
    await render();
    await paint();
    expect(props.onReportsViewed).not.toHaveBeenCalled();
    await act(async () => externalModal.removeAttribute(attribute));
    await paint();
    expect(props.onReportsViewed).toHaveBeenCalledTimes(1);
  });

  it("does not acknowledge in the reports list and resumes on the map tab", async () => {
    await render();
    await click('[role="tab"]:nth-child(2)');
    await paint();
    expect(props.onReportsViewed).not.toHaveBeenCalled();
    await click('[role="tab"]:first-child');
    await paint();
    expect(props.onReportsViewed).toHaveBeenCalledTimes(1);
  });

  it("does not acknowledge reports arriving beneath an open detail popup", async () => {
    await render();
    await paint();
    props.onReportsViewed.mockClear();
    await click(".mf-live-community-map__marker");
    await render({ markers: [...MARKERS] });
    await paint();
    expect(props.onReportsViewed).not.toHaveBeenCalled();
    await click('.mf-territory-map__report-close');
    await paint();
    expect(props.onReportsViewed).toHaveBeenCalledTimes(1);
  });

  it("acknowledges newly rendered reports while the map remains visible", async () => {
    await render();
    await paint();
    props.onReportsViewed.mockClear();
    await render({ markers: [...MARKERS] });
    await paint();
    expect(props.onReportsViewed).toHaveBeenCalledTimes(1);
  });

  it("cancels acknowledgement on unmount", async () => {
    await render();
    await act(async () => root.render(null));
    await paint();
    expect(props.onReportsViewed).not.toHaveBeenCalled();
  });
});
