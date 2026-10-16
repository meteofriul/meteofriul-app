// @vitest-environment jsdom

import { act } from "react";
import { createRoot } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const leafletHarness = vi.hoisted(() => ({
  api: null,
  maps: [],
}));

const radarLayerHarness = vi.hoisted(() => ({
  create: vi.fn(),
}));

vi.mock("leaflet", () => {
  const createAddableLayer = () => ({
    addTo: vi.fn(function addTo() {
      return this;
    }),
  });
  const api = {
    circleMarker: vi.fn(createAddableLayer),
    imageOverlay: vi.fn(createAddableLayer),
    map: vi.fn((container) => {
      const listeners = new Map();
      const panes = new Map();
      const map = {
        attributionControl: { setPrefix: vi.fn() },
        container,
        createPane: vi.fn((name) => {
          const pane = { style: {} };
          panes.set(name, pane);
          return pane;
        }),
        fitBounds: vi.fn(),
        fire: vi.fn((events, payload) => {
          listeners.get(events)?.forEach((listener) => listener(payload));
          return map;
        }),
        getPane: vi.fn((name) => panes.get(name) || null),
        getZoom: vi.fn(() => 8),
        invalidateSize: vi.fn(),
        latLngToContainerPoint: vi.fn(([lat, lon]) => ({
          x: Math.round((Number(lon) - 11.7) * 100),
          y: Math.round((47 - Number(lat)) * 100),
        })),
        off: vi.fn((events, listener) => {
          events.split(" ").forEach((event) => listeners.get(event)?.delete(listener));
          return map;
        }),
        on: vi.fn((events, listener) => {
          events.split(" ").forEach((event) => {
            if (!listeners.has(event)) listeners.set(event, new Set());
            listeners.get(event).add(listener);
          });
          return map;
        }),
        remove: vi.fn(() => {
          container.classList.remove("leaflet-container");
        }),
        removeLayer: vi.fn(),
        setZoom: vi.fn(),
        setView: vi.fn(),
      };

      container.classList.add("leaflet-container");
      leafletHarness.maps.push(map);
      return map;
    }),
    tileLayer: vi.fn(createAddableLayer),
  };

  leafletHarness.api = api;
  return { default: api };
});

vi.mock("../bulletin/dpcRadarLeafletLayer", () => ({
  createDpcRadarGridLayer: (...args) => radarLayerHarness.create(...args),
}));

import { buildBulletinRadarViewModel } from "../bulletin/bulletinRadarViewModel";
import { createFallbackCommunityIdentitySnapshot } from "../community/communityIdentity";
import { LiveView } from "./LiveView";
import { buildLiveViewModel } from "./liveViewModel";
import * as localCommunityPilot from "../../services/localCommunityPilot";
import { getLiveViewCopy } from "../../copy/liveViewCopy";
import { TerritoryImmersiveMap } from "./TerritoryImmersiveMap";
import * as localWeatherPilot from "../../services/localWeatherPilot";
import * as liveApi from "../../services/liveApi";

const NOW = new Date("2026-09-15T15:00:00Z");
const EMPTY_EDIT_FIXTURE_ITEMS = Object.freeze([]);

function buildRadarModel() {
  return buildBulletinRadarViewModel({
    payload: {
      products: [{
        id: "rain",
        period_minutes: 5,
        product_type: "SRI",
        time: "2026-09-15T14:55:00Z",
      }],
      tiles: {
        base_url: "https://tiles.example.test",
        tile_size: 256,
      },
    },
    status: "fresh",
  }, { language: "it", now: NOW.getTime() });
}

function buildUnavailableRadarModel() {
  return buildBulletinRadarViewModel({ status: "error" }, {
    language: "it",
    now: NOW.getTime(),
  });
}

function buildOfficialAlert(tone = "orange") {
  const severe = tone === "red";
  return {
    action: {
      anchor: "official-alerts",
      tab: "bulletin",
      type: "tab-anchor",
    },
    area: "Friuli Venezia Giulia - pianura e costa",
    label: severe ? "Allerta rossa" : "Allerta arancione",
    meta: "Fonte: Protezione Civile FVG",
    risks: severe
      ? ["Rischio idrogeologico", "Temporali forti"]
      : ["Temporali forti", "Vento forte"],
    text: severe
      ? "Criticità elevata prevista nelle zone interessate."
      : "Criticità moderata prevista nelle zone interessate.",
    tone,
    validityLabel: "Valida dalle 14:00 alle 20:00",
  };
}

function buildModel({
  clustered = false,
  community = true,
  explicitIdentity = false,
  lignanoCluster = false,
  location = { city: "Pordenone", lat: 45.9567, lon: 12.6605 },
  manySources = false,
  mapEnabled = false,
  multiple = false,
} = {}) {
  const communitySourceKeys = manySources
    ? [
      "opaque-source-a",
      "opaque-source-b",
      "opaque-source-c",
      "opaque-source-d",
      "opaque-source-e",
    ]
    : ["opaque-source-a"];
  const communityGroup = {
    confirmations: { no: 0, yes: 2 },
    count: communitySourceKeys.length,
    createdAt: NOW.getTime() - 5 * 60_000,
    expiresAt: NOW.getTime() + 55 * 60_000,
    groupId: "group-rain:pordenone:1",
    id: "group-rain:pordenone:1",
    lat: 45.9567,
    lon: 12.6605,
    place: "Pordenone",
    identities: explicitIdentity ? [{
      identity: {
        alias: "Acuile di Pordenon",
        avatar: {
          angle: 135,
          palette_id: "cobalt",
          pattern_id: "halo",
          variant: 2,
        },
        subject_id: "acuile",
        version: 1,
      },
      source_key: "opaque-source-a",
    }] : undefined,
    sourceKeys: communitySourceKeys,
    typeId: "rain",
  };
  const secondCommunityGroup = {
    confirmations: { no: 1, yes: 1 },
    count: 2,
    createdAt: NOW.getTime() - 9 * 60_000,
    expiresAt: NOW.getTime() + 51 * 60_000,
    groupId: "group-wind:cordenons:2",
    id: "group-wind:cordenons:2",
    lat: 45.9836,
    lon: 12.7004,
    place: "Cordenons",
    sourceKeys: ["opaque-source-b", "opaque-source-c"],
    typeId: "wind",
  };
  const clusteredCommunityGroup = {
    confirmations: { no: 1, yes: 2 },
    count: 3,
    createdAt: NOW.getTime() - 9 * 60_000,
    expiresAt: NOW.getTime() + 51 * 60_000,
    groupId: "group-wind:pordenone:2",
    id: "group-wind:pordenone:2",
    lat: 45.9567,
    lon: 12.6605,
    place: "Pordenone",
    sourceKeys: ["opaque-source-b", "opaque-source-c", "opaque-source-d"],
    typeId: "wind",
  };
  const webcam = {
    area: "Centro",
    fallbackImageUrl: "/municipalities/photos/093037-photo.webp",
    group: "plain",
    id: "sacile-centro",
    imageUrl: "https://images.example.test/webcams/sacile-centro.jpg",
    lat: 45.9541,
    lon: 12.5027,
    mapEnabled,
    municipality: "Sacile",
    name: "Sacile - Centro",
    sourcePage: "https://example.test/webcam/sacile",
  };
  const extraWebcams = [
    {
      area: "Piancavallo",
      fallbackImageUrl: "/municipalities/photos/piancavallo.webp",
      group: "mountain",
      id: "piancavallo-centro",
      lat: 46.107,
      lon: 12.519,
      mapEnabled,
      municipality: "Aviano",
      name: "Piancavallo - Centro",
      sourcePage: "https://example.test/webcam/piancavallo",
      sortOrder: 1,
    },
    {
      area: "Tarvisio",
      fallbackImageUrl: "/municipalities/photos/tarvisio.webp",
      group: "mountain",
      id: "tarvisio-centro",
      lat: 46.505,
      lon: 13.579,
      mapEnabled,
      municipality: "Tarvisio",
      name: "Tarvisio - Centro",
      sourcePage: "https://example.test/webcam/tarvisio",
      sortOrder: 2,
    },
    {
      area: "Lignano Sabbiadoro",
      fallbackImageUrl: "/municipalities/photos/lignano.webp",
      group: "coast",
      id: "lignano-centro",
      lat: 45.689,
      lon: 13.145,
      mapEnabled,
      municipality: "Lignano Sabbiadoro",
      name: "Lignano - Centro",
      sourcePage: "https://example.test/webcam/lignano",
      sortOrder: 1,
    },
  ];
  const lignanoWebcams = [
    ["lignano-punta-faro", "Punta Faro", 45.697154, 13.152703],
    ["lignano-spiaggia-centrale", "Spiaggia centrale", 45.686905, 13.141473],
    ["lignano-piazza-fontana", "Piazza Fontana", 45.690668, 13.14519],
    ["lignano-pineta-pontile", "Pontile Pagoda", 45.667131, 13.112805],
    ["lignano-riviera", "Spiaggia Riviera", 45.667131, 13.112805],
  ].map(([id, title, lat, lon], index) => ({
    area: title,
    fallbackImageUrl: "/municipalities/photos/030049-photo.webp",
    group: "coast",
    id,
    imageUrl: `https://images.example.test/webcams/${id}.jpg`,
    health: index === 0 ? "offline" : "ok",
    lat,
    lon,
    mapClusterId: "lignano-sabbiadoro",
    mapClusterLabel: "Lignano Sabbiadoro",
    mapEnabled,
    mediaType: "snapshot",
    municipality: "Lignano Sabbiadoro",
    name: `Lignano Sabbiadoro - ${title}`,
    sortOrder: 20 + index,
    sourcePage: `https://example.test/webcam/${id}`,
  }));
  const communityGroups = community
    ? [
      communityGroup,
      ...(clustered ? [clusteredCommunityGroup] : []),
      ...(multiple ? [secondCommunityGroup] : []),
    ]
    : [];
  const webcams = [
    webcam,
    ...(multiple ? extraWebcams : []),
    ...(lignanoCluster ? lignanoWebcams : []),
  ];

  return buildLiveViewModel({
    community: {
      payload: {
        map_groups: communityGroups,
        reports: communityGroups,
      },
      status: "fresh",
    },
    webcams: {
      payload: { ok: true, webcams },
      status: "fresh",
    },
  }, {
    language: "it",
    location,
    now: NOW,
  });
}

function getLegacyFallbackAlias(sourceKey, place = "Pordenone") {
  return createFallbackCommunityIdentitySnapshot(sourceKey, place)?.alias;
}

function buildRadarLayer() {
  const listeners = new Map();
  const layer = {
    addTo: vi.fn(function addTo() {
      return this;
    }),
    off: vi.fn((event, listener) => {
      if (listeners.get(event) === listener) listeners.delete(event);
      return layer;
    }),
    on: vi.fn((event, listener) => {
      listeners.set(event, listener);
      return layer;
    }),
    setFrame: vi.fn(),
  };
  return { layer, listeners };
}

async function settleEffects() {
  await act(async () => {
    await Promise.resolve();
    await new Promise((resolve) => globalThis.setTimeout(resolve, 0));
  });
}

async function click(node) {
  expect(node).toBeTruthy();
  await act(async () => node.click());
  await settleEffects();
}

function stubAnimationFrames() {
  let nextId = 0;
  const frames = new Map();
  vi.stubGlobal("requestAnimationFrame", vi.fn((callback) => {
    const id = ++nextId;
    frames.set(id, callback);
    return id;
  }));
  vi.stubGlobal("cancelAnimationFrame", vi.fn((id) => frames.delete(id)));
  return frames;
}

describe("pilot unified territory map integration", () => {
  let container;
  let root;

  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(NOW);
    globalThis.IS_REACT_ACT_ENVIRONMENT = true;
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
    leafletHarness.maps.length = 0;
    leafletHarness.api?.map.mockClear();
    leafletHarness.api?.tileLayer.mockClear();
    leafletHarness.api?.imageOverlay.mockClear();
    leafletHarness.api?.circleMarker.mockClear();
    radarLayerHarness.create.mockReset();
    radarLayerHarness.create.mockImplementation(() => buildRadarLayer().layer);
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    container.remove();
    document.body.replaceChildren();
    vi.useRealTimers();
    vi.restoreAllMocks();
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    delete globalThis.IS_REACT_ACT_ENVIRONMENT;
  });

  async function renderPilot({
    modelOptions = {},
    radarModel = buildRadarModel(),
    ...props
  } = {}) {
    await act(async () => {
      root.render(
        <LiveView
          compactLayout
          model={buildModel(modelOptions)}
          radarModel={radarModel}
          {...props}
        />,
      );
    });
    await settleEffects();
  }

  function getWorkspace() {
    return container.querySelector(
      ".mf-live-community-map-layer--inline.mf-live-territory-workspace",
    );
  }

  it("uses real 48-hour records in TEST while preserving compact, expandable and live-detail UX", async () => {
    vi.spyOn(localCommunityPilot, "isLocalCommunityPilot").mockReturnValue(true);
    vi.spyOn(localCommunityPilot, "isLocalCommunityDevelopmentRuntime").mockReturnValue(true);
    vi.spyOn(liveApi, "getPersistentLiveReportClientId").mockReturnValue("test-reader");
    vi.spyOn(liveApi, "fetchCommunityHistory").mockResolvedValue({ reports: [{
      id: "old-observation", typeId: "wind", place: "Pordenone", mine: true, point: true,
      count: 3, confirmations: { yes: 4, no: 1 },
      status: "expired", createdAt: NOW.getTime() - 7_200_000, expiresAt: NOW.getTime() - 3_600_000,
    }], next_cursor: null });
    await renderPilot({ modelOptions: { multiple: true }, onReportSubmit: vi.fn(),
      onReportConfirm: vi.fn(), reportingEnabled: true });
    const workspace = getWorkspace();
    expect(liveApi.fetchCommunityHistory).not.toHaveBeenCalled();
    await click(workspace.querySelector('[data-territory-tab="reports"]'));
    const dock = workspace.querySelector(".mf-territory-map__dock");
    const list = dock.querySelector(".mf-territory-map__browse-list");
    expect(list.querySelectorAll(".mf-territory-map__browse-item")).toHaveLength(1);
    expect(dock.querySelector(".mf-community-history-navigation")).toBeNull();
    expect(dock.textContent).toContain("Ultime 48 ore");
    await click(dock.querySelector(".mf-recent-list-toggle"));
    expect(dock.classList.contains("mf-territory-map__dock--expanded")).toBe(true);
    const historyRow = list.querySelector('[data-history-id="old-observation"]');
    expect(historyRow.textContent).toContain("1 punto ottenuto");
    expect(historyRow.textContent).toContain("3 segnalazioni");
    expect(historyRow.textContent).toContain("2 ore fa");
    expect(list.textContent).toContain("Hai visto le segnalazioni delle ultime 48 ore.");
    const windRow = [...list.querySelectorAll("button:not([data-history-id])")]
      .find((button) => button.textContent.includes("Vento forte"));
    expect(windRow.textContent).toContain("Attiva");
    expect(list.textContent).not.toContain("Non c’è più");
    expect(list.querySelector(".mf-territory-map__browse-denial-status")).toBeNull();
    await click(windRow);
    const detail = workspace.querySelector(".mf-territory-map__detail-layer");
    expect(detail).toBeTruthy();
    expect(detail.querySelector(".mf-live-community-map__confirm-button--no")?.textContent)
      .toContain("Non c’è più");
    expect(detail.querySelector(".mf-live-community-map__confirm-button--no .mf-live-community-map__confirm-count")?.textContent)
      .toBe("1");
    await click(workspace.querySelector(".mf-territory-map__report-close"));
    expect(dock.classList.contains("mf-territory-map__dock--expanded")).toBe(true);
    await click(historyRow);
    const historyDetail = workspace.querySelector(".mf-community-history-detail");
    expect(historyDetail.textContent).toContain("Non si può più votare");
    expect([...historyDetail.querySelectorAll("dd")].map((node) => node.textContent)).toEqual(["4", "1"]);
    expect(historyDetail.querySelectorAll("button")).toHaveLength(1); // Close only; no voting actions.
    await click(historyDetail.querySelector("button"));
    expect(dock.classList.contains("mf-territory-map__dock--expanded")).toBe(true);
    await click(dock.querySelector(".mf-territory-map__dock-grabber"));
    expect(list.querySelectorAll(".mf-territory-map__browse-item")).toHaveLength(1);
  });

  it("opens the real history without active reports and automatically loads more at the scroll boundary", async () => {
    vi.spyOn(localCommunityPilot, "isLocalCommunityPilot").mockReturnValue(true);
    vi.spyOn(localCommunityPilot, "isLocalCommunityDevelopmentRuntime").mockReturnValue(true);
    vi.spyOn(liveApi, "getPersistentLiveReportClientId").mockReturnValue("test-reader");
    const row = { id: "first", typeId: "rain", place: "Pordenone", status: "expired",
      createdAt: NOW.getTime() - 7_200_000, expiresAt: NOW.getTime() - 3_600_000 };
    const cursor = { id: row.id, createdAt: row.createdAt };
    vi.spyOn(liveApi, "fetchCommunityHistory").mockResolvedValueOnce({ reports: [row], next_cursor: cursor })
      .mockResolvedValueOnce({ reports: [{ ...row, id: "second", createdAt: row.createdAt - 1000 }], next_cursor: null });
    await renderPilot({ modelOptions: { community: false } });
    const workspace = getWorkspace();
    await click(workspace.querySelector('[data-territory-tab="reports"]'));
    expect(workspace.querySelector(".mf-territory-map--reports-empty")).toBeNull();
    expect(workspace.textContent).not.toContain("Mostra altre");
    await click(workspace.querySelector(".mf-recent-list-toggle"));
    await act(async () => workspace.querySelector(".mf-territory-map__browse-list")
      .dispatchEvent(new Event("scroll", { bubbles: true })));
    expect(liveApi.fetchCommunityHistory.mock.calls[1][0].cursor).toEqual(cursor);
    expect(workspace.querySelectorAll("button[data-history-id]")).toHaveLength(2);
  });

  it("opens an owned report editor directly and closes the map detail without restoring marker focus", async () => {
    vi.spyOn(localCommunityPilot, "isLocalCommunityPilot").mockReturnValue(true);
    const ownReport = {
      correctionUntil: NOW.getTime() + 300_000,
      createdAt: NOW.getTime(),
      expiresAt: NOW.getTime() + 3_600_000,
      groupId: "owned-rain",
      reportId: "owned-report-rain",
      replacementAvailable: true,
      revision: 1,
      typeId: "rain",
    };
    const marker = {
      ...ownReport,
      confirmations: { yes: 0, no: 0 },
      count: 1,
      countLabel: "1 segnalazione recente",
      id: ownReport.groupId,
      lat: 45.9567,
      lon: 12.6605,
      place: "Pordenone",
      sourceKeys: ["owned-source"],
      timeLabel: "Adesso",
      typeLabel: "Pioggia",
    };
    const actions = {
      onCorrect: vi.fn(),
      onEdit: vi.fn(),
      onReplace: vi.fn(),
      onUpdate: vi.fn(),
      onWithdraw: vi.fn(),
    };
    await act(async () => root.render(
      <TerritoryImmersiveMap
        {...actions}
        communityCopy={getLiveViewCopy("it")}
        inline
        mapWebcams={EMPTY_EDIT_FIXTURE_ITEMS}
        markers={[marker]}
        personalState={{ reports: [ownReport] }}
        reportItems={EMPTY_EDIT_FIXTURE_ITEMS}
        webcamGroups={EMPTY_EDIT_FIXTURE_ITEMS}
        webcamList={EMPTY_EDIT_FIXTURE_ITEMS}
        webcamsEnabled={false}
      />,
    ));
    await settleEffects();
    const trigger = container.querySelector(".mf-live-community-map__marker");
    await click(trigger);
    const restoreFocus = vi.spyOn(trigger, "focus");
    const editor = container.querySelector(".mf-live-community-own-report__manage");
    expect(editor?.textContent).toBe("Aggiorna o modifica");
    await click(editor);

    expect(actions.onEdit).toHaveBeenCalledExactlyOnceWith(ownReport);
    expect(container.querySelector(".mf-territory-map__report-detail")).toBeNull();
    expect(restoreFocus).not.toHaveBeenCalled();
    for (const [name, callback] of Object.entries(actions)) {
      if (name !== "onEdit") expect(callback).not.toHaveBeenCalled();
    }
  });

  it("never exposes direct report editing for ownership inferred without a stored receipt", async () => {
    vi.spyOn(localCommunityPilot, "isLocalCommunityPilot").mockReturnValue(true);
    const onEdit = vi.fn();
    const marker = {
      count: 1,
      countLabel: "1 segnalazione recente",
      createdAt: NOW.getTime(),
      expiresAt: NOW.getTime() + 3_600_000,
      groupId: "inferred-rain",
      id: "inferred-rain",
      lat: 45.9567,
      lon: 12.6605,
      place: "Pordenone",
      sourceKeys: ["inferred-source"],
      timeLabel: "Adesso",
      typeId: "rain",
      typeLabel: "Pioggia",
    };
    await act(async () => root.render(
      <TerritoryImmersiveMap
        communityCopy={getLiveViewCopy("it")}
        inferredOwnGroupIds={[marker.groupId]}
        inline
        mapWebcams={EMPTY_EDIT_FIXTURE_ITEMS}
        markers={[marker]}
        onEdit={onEdit}
        personalState={{ reports: [] }}
        reportItems={EMPTY_EDIT_FIXTURE_ITEMS}
        webcamGroups={EMPTY_EDIT_FIXTURE_ITEMS}
        webcamList={EMPTY_EDIT_FIXTURE_ITEMS}
        webcamsEnabled={false}
      />,
    ));
    await settleEffects();
    await click(container.querySelector(".mf-live-community-map__marker"));

    expect(container.textContent).toContain("La tua segnalazione");
    expect(container.querySelector(".mf-live-community-own-report__manage")).toBeNull();
    expect(onEdit).not.toHaveBeenCalled();
  });

  it("projects rapid map events once per frame using the final viewport position", async () => {
    await renderPilot();
    const map = leafletHarness.maps[0];
    const marker = getWorkspace().querySelector(".mf-live-community-map__marker");
    const frames = stubAnimationFrames();
    map.latLngToContainerPoint.mockClear();

    await act(async () => {
      for (let eventIndex = 0; eventIndex < 4; eventIndex += 1) {
        map.fire("move").fire("zoom").fire("resize");
      }
    });
    expect(frames.size).toBe(1);
    expect(map.latLngToContainerPoint).not.toHaveBeenCalled();

    map.latLngToContainerPoint.mockReturnValue({ x: 321, y: 123 });
    const firstFrame = [...frames.values()][0];
    frames.clear();
    await act(async () => firstFrame());
    // One pass over the report, webcam and webcam place group.
    expect(map.latLngToContainerPoint).toHaveBeenCalledTimes(3);
    expect(marker.style.left).toBe("321px");
    expect(marker.style.top).toBe("123px");

    await act(async () => map.fire("move"));
    expect(frames.size).toBe(1);
    map.latLngToContainerPoint.mockReturnValue({ x: 450, y: 200 });
    const finalFrame = [...frames.values()][0];
    frames.clear();
    await act(async () => finalFrame());
    expect(map.latLngToContainerPoint).toHaveBeenCalledTimes(6);
    expect(marker.style.left).toBe("450px");
    expect(marker.style.top).toBe("200px");
  });

  it("cancels stale marker projections after data changes and map disposal", async () => {
    await renderPilot();
    const map = leafletHarness.maps[0];
    const frames = stubAnimationFrames();
    await act(async () => map.fire("move"));
    const [oldFrameId, oldFrame] = [...frames.entries()][0];

    await renderPilot({ modelOptions: { multiple: true } });
    expect(globalThis.cancelAnimationFrame).toHaveBeenCalledWith(oldFrameId);
    expect(frames.has(oldFrameId)).toBe(false);
    map.latLngToContainerPoint.mockClear();
    await act(async () => oldFrame());
    expect(map.latLngToContainerPoint).not.toHaveBeenCalled();

    await act(async () => map.fire("resize"));
    const [pendingFrameId, pendingFrame] = [...frames.entries()].at(-1);
    await act(async () => root.render(null));
    expect(globalThis.cancelAnimationFrame).toHaveBeenCalledWith(pendingFrameId);
    expect(frames.has(pendingFrameId)).toBe(false);
    await act(async () => {
      pendingFrame();
      map.fire("move").fire("zoom").fire("resize");
    });
    expect(map.latLngToContainerPoint).not.toHaveBeenCalled();
    expect(frames.size).toBe(0);
  });

  it("still projects map events when animation frames are unavailable", async () => {
    await renderPilot();
    const map = leafletHarness.maps[0];
    vi.stubGlobal("requestAnimationFrame", undefined);
    map.latLngToContainerPoint.mockClear();
    map.latLngToContainerPoint.mockReturnValue({ x: 250, y: 150 });

    await act(async () => map.fire("move"));

    expect(map.latLngToContainerPoint).toHaveBeenCalledTimes(3);
    const marker = getWorkspace().querySelector(".mf-live-community-map__marker");
    expect(marker.style.left).toBe("250px");
    expect(marker.style.top).toBe("150px");
  });

  it("keeps the inline map available when there are zero recent community reports", async () => {
    await renderPilot({ modelOptions: { community: false } });
    const workspace = getWorkspace();

    expect(workspace).toBeTruthy();
    expect(workspace.classList.contains("mf-live-community-map-layer--pilot")).toBe(true);
    expect(workspace.querySelector(".mf-live-community-map--immersive")).toBeNull();
    expect(workspace.querySelector(".mf-live-community-map-toggle")).toBeNull();
    expect(workspace.querySelector(".mf-live-community-map__canvas.leaflet-container"))
      .toBeTruthy();

    const reportsTab = [...workspace.querySelectorAll(".mf-territory-map__navigation button")]
      .find((button) => button.textContent.includes("Segnalazioni"));
    await click(reportsTab);

    expect(workspace.querySelector(".mf-territory-map--reports-empty")).toBeTruthy();
    expect(workspace.querySelector(".mf-territory-map__browse-sheet")?.textContent)
      .toContain("Nessuna segnalazione recente");
  });

  it("swaps the CARTO basemap from light to dark without recreating Leaflet", async () => {
    vi.stubEnv("VITE_TERRITORY_CARTO_API_KEY", "test-key");

    await renderPilot({ theme: "light" });
    const map = leafletHarness.maps[0];
    const lightLayer = leafletHarness.api.tileLayer.mock.results.at(-1).value;
    expect(leafletHarness.api.tileLayer.mock.calls.at(-1)[0]).toContain("/light_all/");

    await renderPilot({ theme: "dark" });

    expect(leafletHarness.api.map).toHaveBeenCalledTimes(1);
    expect(leafletHarness.api.tileLayer.mock.calls.at(-1)[0]).toContain("/dark_all/");
    expect(map.removeLayer).toHaveBeenCalledWith(lightLayer);
    expect(getWorkspace().querySelector(".mf-live-community-map__canvas.leaflet-container"))
      .toBeTruthy();
  });

  it("leaves the beta hierarchy and legacy map free of pilot unified controls", () => {
    const markup = renderToStaticMarkup(
      <LiveView
        compactLayout={false}
        model={buildModel()}
        radarModel={buildRadarModel()}
      />,
    );
    const radarIndex = markup.indexOf("mf-bulletin-radar-card");
    const webcamIndex = markup.indexOf("mf-live-card--webcam");
    const communityIndex = markup.indexOf("mf-live-card--community");

    expect(radarIndex).toBeGreaterThanOrEqual(0);
    expect(webcamIndex).toBeGreaterThan(radarIndex);
    expect(communityIndex).toBeGreaterThan(webcamIndex);
    expect(markup).toContain('class="mf-live-community-map"');
    expect(markup).not.toContain("mf-territory-map__floating-controls");
    expect(markup).not.toContain("mf-territory-map__navigation");
    expect(markup).not.toContain("mf-live-community-map-layer--inline");
    expect(markup).not.toContain("mf-territory-map__report-action");
  });

  it("renders one always-inline Leaflet canvas with a grabbed dock and the report action last", async () => {
    await renderPilot({
      onReportSubmit: vi.fn(),
      reportingEnabled: true,
    });
    const workspace = getWorkspace();
    const dock = workspace.querySelector(".mf-territory-map__dock");
    const grabber = dock.querySelector(".mf-territory-map__dock-grabber");
    const navigation = dock.querySelector(".mf-territory-map__navigation");
    const reportAction = dock.querySelector(".mf-territory-map__report-action");

    expect(workspace).toBeTruthy();
    expect(container.querySelectorAll(".leaflet-container")).toHaveLength(1);
    expect(document.body.querySelectorAll(".leaflet-container")).toHaveLength(1);
    expect(workspace.querySelectorAll(".mf-live-community-map__canvas.leaflet-container"))
      .toHaveLength(1);
    expect(document.body.querySelector(".mf-bulletin-radar-map")).toBeNull();
    expect(container.querySelector(".mf-live-card--community")).toBeNull();
    expect(container.querySelector(".mf-live-card--webcam")).toBeNull();
    expect(grabber).toBeTruthy();
    expect(grabber.getAttribute("aria-hidden")).toBe("true");
    expect(navigation).toBeTruthy();
    expect(reportAction?.textContent).toContain("Segnala meteo");
    expect(reportAction?.disabled).toBe(false);
    expect([...dock.children]).toEqual([grabber, navigation, reportAction]);
    expect(dock.lastElementChild).toBe(reportAction);
    expect([...navigation.querySelectorAll("button > span")].map((label) => label.textContent))
      .toEqual(["Mappa", "Segnalazioni", "Webcam"]);
    expect(navigation.querySelectorAll("button svg, button em")).toHaveLength(0);

    const radar = workspace.querySelector('button[aria-label="Radar"]');
    const webcams = workspace.querySelector(".mf-territory-map__control--webcam");
    const center = workspace.querySelector('button[aria-label="Centra la mappa sulla località selezionata"]');

    expect(radar?.getAttribute("aria-pressed")).toBe("false");
    expect(radar?.disabled).toBe(false);
    expect(webcams?.hasAttribute("aria-pressed")).toBe(false);
    expect(webcams?.getAttribute("aria-expanded")).toBe("false");
    expect(webcams?.disabled).toBe(false);
    expect(center?.hasAttribute("aria-pressed")).toBe(false);
    expect(center?.disabled).toBe(false);

    const reportMarker = workspace.querySelector(".mf-live-community-map__marker");
    const reportMarkerIcon = reportMarker?.querySelector("svg");
    expect(reportMarkerIcon?.getAttribute("width")).toBe("22");
    expect(reportMarkerIcon?.getAttribute("height")).toBe("22");
    expect(reportMarkerIcon?.getAttribute("stroke-width")).toBe("2.45");
    expect(reportMarkerIcon?.classList.contains("lucide-cloud-rain")).toBe(true);

    const map = leafletHarness.maps[0];
    expect(map.fitBounds).not.toHaveBeenCalled();
    expect(map.setView).toHaveBeenCalledWith(
      [45.9567, 12.6605],
      8.5,
      { animate: false },
    );
    expect(leafletHarness.api.map).toHaveBeenCalledWith(
      expect.any(HTMLElement),
      expect.objectContaining({
        maxBounds: [[35.1, 6.2], [47.6, 19]],
        minZoom: 5,
        scrollWheelZoom: true,
        zoomSnap: 0.5,
      }),
    );
    expect(map.setZoom).not.toHaveBeenCalled();
  });

  it("opens the national territory map around the selected Roma coordinates", async () => {
    await renderPilot({
      modelOptions: {
        location: {
          city: "Roma",
          countryCode: "IT",
          lat: 41.8933,
          lon: 12.4829,
          region: "Lazio",
        },
      },
    });

    const map = leafletHarness.maps[0];
    expect(map.fitBounds).not.toHaveBeenCalled();
    expect(map.setView).toHaveBeenCalledWith(
      [41.8933, 12.4829],
      8.5,
      { animate: false },
    );
  });

  it("uses the FVG editorial bounds only when selected coordinates are unavailable", async () => {
    await renderPilot({ modelOptions: { location: null } });

    const map = leafletHarness.maps[0];
    expect(map.fitBounds).toHaveBeenCalledWith(
      [[45.55, 12.25], [46.75, 13.95]],
      {
        paddingBottomRight: [24, 156],
        paddingTopLeft: [24, 96],
      },
    );
    expect(map.setZoom).toHaveBeenCalledWith(8.5, { animate: false });
    expect(map.setView).not.toHaveBeenCalled();
  });

  it("keeps the floating pilot controls icon-only and exposes their dedicated contracts", async () => {
    await renderPilot({ modelOptions: { multiple: true } });
    const workspace = getWorkspace();
    const controls = workspace.querySelector(".mf-territory-map__floating-controls");
    const radar = controls.querySelector(".mf-territory-map__control--radar");
    const webcams = controls.querySelector(".mf-territory-map__control--webcam");
    const gps = controls.querySelector(".mf-territory-map__control--gps");

    expect(radar).toBeTruthy();
    expect(webcams).toBeTruthy();
    expect(gps).toBeTruthy();
    expect([...controls.querySelectorAll(":scope > button")]).toEqual([
      radar,
      webcams,
      gps,
    ]);
    [radar, webcams, gps].forEach((control) => {
      expect(control.querySelector("svg")).toBeTruthy();
      expect(control.querySelector("span, em")).toBeNull();
      expect(control.textContent.trim()).toBe("");
    });
    const windMarker = [...workspace.querySelectorAll(".mf-live-community-map__marker")]
      .find((marker) => marker.getAttribute("aria-label")?.includes("Vento forte"));
    expect(windMarker?.querySelector(":scope > span")?.textContent).toBe("2");
  });

  it("expands a grouped municipality marker into an accessible fan and closes it consistently", async () => {
    await renderPilot({ modelOptions: { clustered: true } });
    const workspace = getWorkspace();
    const cluster = workspace.querySelector(".mf-territory-map__cluster");
    const clusterTrigger = cluster?.querySelector(".mf-territory-map__cluster-toggle");

    expect(cluster).toBeTruthy();
    expect(clusterTrigger).toBeTruthy();
    expect(clusterTrigger.getAttribute("aria-label")).toContain(
      "Più fenomeni · Pordenone",
    );
    expect(clusterTrigger.getAttribute("aria-expanded")).toBe("false");
    expect(clusterTrigger.querySelector(":scope > span")?.textContent).toBe("2");
    expect(clusterTrigger.querySelector(".lucide-radio")).toBeTruthy();

    const fanId = clusterTrigger.getAttribute("aria-controls");
    expect(fanId).toBeTruthy();
    clusterTrigger.focus();
    await click(clusterTrigger);

    const fan = workspace.querySelector(`#${fanId}`);
    expect(clusterTrigger.getAttribute("aria-expanded")).toBe("true");
    expect(cluster.classList.contains("is-open")).toBe(true);
    expect(clusterTrigger.querySelector(".lucide-x")).toBeTruthy();
    expect(fan?.getAttribute("role")).toBe("group");
    expect(fan?.getAttribute("aria-label")).toContain("Pordenone");

    const petals = [...fan.querySelectorAll(".mf-territory-map__cluster-petal")];
    expect(petals).toHaveLength(2);
    expect(petals.map((petal) => petal.getAttribute("aria-label"))).toEqual([
      expect.stringContaining("Pioggia · Pordenone"),
      expect.stringContaining("Vento forte · Pordenone"),
    ]);

    await click(clusterTrigger);
    expect(clusterTrigger.getAttribute("aria-expanded")).toBe("false");
    expect(cluster.classList.contains("is-open")).toBe(false);
    expect(workspace.querySelector(`#${fanId}`)).toBeNull();

    clusterTrigger.focus();
    await click(clusterTrigger);
    await act(async () => {
      document.dispatchEvent(new KeyboardEvent("keydown", { bubbles: true, key: "Escape" }));
    });
    await settleEffects();
    await act(async () => {
      await new Promise((resolve) => globalThis.requestAnimationFrame(resolve));
    });

    expect(workspace.querySelector(`#${fanId}`)).toBeNull();
    expect(clusterTrigger.getAttribute("aria-expanded")).toBe("false");
    expect(document.activeElement).toBe(clusterTrigger);

    await click(clusterTrigger);
    await click(workspace.querySelector(".mf-territory-map__cluster-backdrop"));

    expect(workspace.querySelector(`#${fanId}`)).toBeNull();
    expect(clusterTrigger.getAttribute("aria-expanded")).toBe("false");
  });

  it("selects one fan phenomenon and opens only its single-event detail", async () => {
    await renderPilot({
      modelOptions: { clustered: true },
      onReportConfirm: vi.fn(),
      reportingEnabled: true,
    });
    const workspace = getWorkspace();
    const clusterTrigger = workspace.querySelector(
      ".mf-territory-map__cluster-toggle",
    );
    await click(clusterTrigger);

    const windPetal = [...workspace.querySelectorAll(".mf-territory-map__cluster-petal")]
      .find((petal) => petal.getAttribute("aria-label")?.includes("Vento forte"));
    expect(windPetal?.getAttribute("aria-label")).toContain(
      "Vento forte · Pordenone",
    );
    await click(windPetal);

    expect(workspace.querySelector(".mf-territory-map__cluster-fan")).toBeNull();
    expect(clusterTrigger.getAttribute("aria-expanded")).toBe("false");
    const detail = workspace.querySelector(
      '.mf-territory-map__report-detail[role="dialog"]',
    );
    expect(detail).toBeTruthy();
    expect(detail.getAttribute("aria-label")).toContain("Vento forte · Pordenone");
    expect(detail.getAttribute("aria-label")).not.toContain("Più fenomeni");
    expect(detail.querySelector(".mf-territory-map__report-primary-heading strong")?.textContent)
      .toBe("Vento forte");
    expect(detail.querySelectorAll(".mf-live-community-map__phenomenon")).toHaveLength(1);
    const identities = detail.querySelector(".mf-territory-map__report-community-identities");
    ["opaque-source-b", "opaque-source-c", "opaque-source-d"].forEach((sourceKey) => {
      expect(identities.textContent).toContain(getLegacyFallbackAlias(sourceKey));
      expect(identities.textContent).not.toContain(sourceKey);
    });
    expect(identities.querySelectorAll(".mf-community-avatar")).toHaveLength(3);
  });

  it("zooms an explicit webcam cluster into accessible individual markers", async () => {
    await renderPilot({
      modelOptions: {
        community: false,
        lignanoCluster: true,
        mapEnabled: true,
      },
    });
    const workspace = getWorkspace();
    await click(workspace.querySelector(".mf-territory-map__control--webcam"));

    const cluster = workspace.querySelector(".mf-territory-map__webcam-cluster");
    const trigger = cluster?.querySelector(".mf-territory-map__webcam-cluster-toggle");
    const map = leafletHarness.maps[0];
    expect(cluster).toBeTruthy();
    expect(trigger?.getAttribute("aria-label")).toContain("Lignano Sabbiadoro · 5 webcam");
    expect(trigger?.hasAttribute("aria-expanded")).toBe(false);
    expect(trigger?.querySelector(":scope > span")?.textContent).toBe("5");
    expect(trigger?.classList.contains("is-health-not-ok")).toBe(true);
    expect(workspace.querySelectorAll(".mf-territory-map__webcam-cluster")).toHaveLength(1);

    trigger.focus();
    await click(trigger);
    expect(map.setView).toHaveBeenLastCalledWith(
      [expect.any(Number), expect.any(Number)],
      12,
      { animate: true },
    );
    expect(workspace.querySelector(".mf-territory-map__webcam-cluster")).toBeNull();
    const lignanoMarkers = [...workspace.querySelectorAll("[data-webcam-id]")]
      .filter((marker) => marker.dataset.webcamId.startsWith("lignano-"));
    expect(lignanoMarkers).toHaveLength(5);
    expect(lignanoMarkers.map((marker) => marker.getAttribute("aria-label"))).toEqual([
      expect.stringContaining("Punta Faro"),
      expect.stringContaining("Spiaggia centrale"),
      expect.stringContaining("Piazza Fontana"),
      expect.stringContaining("Pontile Pagoda"),
      expect.stringContaining("Spiaggia Riviera"),
    ]);
    const puntaFaro = lignanoMarkers.find(
      (marker) => marker.dataset.webcamId === "lignano-punta-faro",
    );
    expect(puntaFaro.classList.contains("is-health-not-ok")).toBe(true);
    expect(puntaFaro.getAttribute("aria-label")).toContain("Fonte non raggiungibile");

    const colocatedMarkers = lignanoMarkers.filter((marker) => [
      "lignano-pineta-pontile",
      "lignano-riviera",
    ].includes(marker.dataset.webcamId));
    expect(new Set(colocatedMarkers.map((marker) => marker.style.marginLeft)).size).toBe(2);

    await act(async () => {
      await new Promise((resolve) => globalThis.requestAnimationFrame(resolve));
    });
    expect(document.activeElement?.dataset.webcamId).toBe("lignano-punta-faro");

    const piazzaFontana = lignanoMarkers.find(
      (marker) => marker.dataset.webcamId === "lignano-piazza-fontana",
    );
    await click(piazzaFontana);
    const detail = workspace.querySelector('.mf-territory-map__webcam-detail[role="dialog"]');
    expect(detail).toBeTruthy();
    expect(detail.querySelector(".mf-live-community-map__detail-heading strong")?.textContent)
      .toBe("Piazza Fontana");
    expect(detail.querySelector(".mf-live-community-map__detail-heading span")?.textContent)
      .toContain("Lignano Sabbiadoro");

  });

  it("keeps Webcam mode and its expanded browse panel open after a blank map click", async () => {
    await renderPilot({
      modelOptions: { community: false, lignanoCluster: true, mapEnabled: true },
    });
    const workspace = getWorkspace();
    const map = leafletHarness.maps[0];
    const webcamControl = workspace.querySelector(".mf-territory-map__control--webcam");
    await click(webcamControl);
    await click(workspace.querySelector(".mf-territory-map__browse-toggle"));
    const coastGroup = [...workspace.querySelectorAll(".mf-territory-map__webcam-groups button")]
      .find((button) => button.textContent.includes("Costa"));
    await click(coastGroup);

    await click(workspace.querySelector(".mf-territory-map__browse-item--webcam"));
    expect(workspace.querySelector('.mf-territory-map__webcam-detail[role="dialog"]'))
      .toBeTruthy();

    await click(workspace.querySelector(".mf-territory-map__detail-layer"));

    const webcamTab = workspace.querySelector('[data-territory-tab="webcams"]');
    const mapTab = workspace.querySelector('[data-territory-tab="map"]');
    expect(workspace.querySelector('.mf-territory-map__webcam-detail[role="dialog"]'))
      .toBeNull();
    expect(webcamControl.getAttribute("aria-expanded")).toBe("true");
    expect(webcamTab.getAttribute("aria-selected")).toBe("true");
    expect(mapTab.getAttribute("aria-selected")).toBe("false");
    expect(workspace.querySelector(".mf-territory-map--panel-expanded")).toBeTruthy();
    expect(workspace.querySelector(".mf-territory-map__webcam-markers")).toBeTruthy();

    await act(async () => map.fire("click"));
    await settleEffects();

    expect(webcamControl.getAttribute("aria-expanded")).toBe("true");
    expect(webcamTab.getAttribute("aria-selected")).toBe("true");
    expect(workspace.querySelector(".mf-territory-map__webcam-markers")).toBeTruthy();
  });

  it("creates a stable visual fallback for a legacy source without exposing its key", async () => {
    vi.spyOn(localCommunityPilot, "isLocalCommunityPilot").mockReturnValue(true);
    await renderPilot({ onReportConfirm: vi.fn(), reportingEnabled: true });
    const workspace = getWorkspace();
    const rainMarker = [...workspace.querySelectorAll(".mf-live-community-map__marker")]
      .find((marker) => marker.getAttribute("aria-label")?.includes("Pioggia"));

    await click(rainMarker);

    const detail = workspace.querySelector(".mf-territory-map__report-detail");
    const identities = detail.querySelector(".mf-territory-map__report-community-identities");
    const expectedIdentity = createFallbackCommunityIdentitySnapshot(
      "opaque-source-a",
      "Pordenone",
    );
    const avatar = identities.querySelector(".mf-community-avatar");

    expect(detail.classList.contains("mf-territory-map__report-detail--pilot")).toBe(true);
    expect(detail.querySelector(".mf-territory-map__report-community-status-main")).toBeNull();
    expect(detail.querySelector(".mf-territory-map__report-community-status-dot")).toBeNull();
    expect(detail.textContent).not.toContain("Riferito al Comune");
    expect(detail.textContent).not.toContain("segnalazione recente");
    expect(detail.querySelector(".mf-live-community-map__confirm-button--yes")?.getAttribute("aria-label"))
      .toBe("Confermo. Conferme: 2");
    expect(detail.querySelector(".mf-live-community-map__confirm-button--no")?.getAttribute("aria-label"))
      .toBe("Non c’è più. Non c’è più: 0");
    expect(identities).toBeTruthy();
    expect(identities.querySelector(".mf-territory-map__report-community-identities-label")?.textContent)
      .toBe("Sentinella Meteo:");
    expect(identities.textContent).toContain(expectedIdentity.alias);
    expect(identities.textContent.split(expectedIdentity.alias)).toHaveLength(2);
    expect(identities.querySelector("button, [aria-expanded], [role='list'], .mf-territory-map__report-community-chevron"))
      .toBeNull();
    expect(avatar?.getAttribute("data-subject")).toBe(expectedIdentity.subjectId);
    expect(avatar?.getAttribute("data-palette")).toBe(expectedIdentity.avatar.paletteId);
    expect(detail.querySelector(".mf-territory-map__report-author")).toBeNull();
    expect(detail.textContent).not.toContain("opaque-source-a");
  });

  it("renders the immutable alias and generated avatar supplied by the report snapshot", async () => {
    vi.spyOn(localCommunityPilot, "isLocalCommunityPilot").mockReturnValue(true);
    await renderPilot({
      modelOptions: { explicitIdentity: true },
      onReportConfirm: vi.fn(),
      reportingEnabled: true,
    });
    const workspace = getWorkspace();
    const rainMarker = [...workspace.querySelectorAll(".mf-live-community-map__marker")]
      .find((marker) => marker.getAttribute("aria-label")?.includes("Pioggia"));

    await click(rainMarker);

    const detail = workspace.querySelector(".mf-territory-map__report-detail");
    const identities = detail.querySelector(".mf-territory-map__report-community-identities");
    const avatar = identities.querySelector(".mf-community-avatar");

    expect(identities.textContent).toContain("Acuile di Pordenon");
    expect(identities.textContent.split("Acuile di Pordenon")).toHaveLength(2);
    expect(identities.querySelectorAll(".mf-community-avatar")).toHaveLength(1);
    expect(identities.querySelector(".mf-territory-map__report-community-single")).toBeTruthy();
    expect(identities.querySelector("button, [aria-expanded], [role='list'], .mf-territory-map__report-community-chevron"))
      .toBeNull();
    expect(avatar?.getAttribute("data-subject")).toBe("acuile");
    expect(avatar?.getAttribute("data-palette")).toBe("cobalt");
    expect(avatar?.getAttribute("data-pattern")).toBe("halo");
    expect(avatar?.style.height).toBe("40px");
    expect(avatar?.style.width).toBe("40px");
    expect(detail.textContent).not.toContain("opaque-source-a");
  });

  it("localizes the fixed single-sentinel identity in Friulian without an expandable duplicate", async () => {
    vi.spyOn(localCommunityPilot, "isLocalCommunityPilot").mockReturnValue(true);
    await renderPilot({
      language: "fur",
      modelOptions: { explicitIdentity: true },
      onReportConfirm: vi.fn(),
      reportingEnabled: true,
    });
    const workspace = getWorkspace();
    const rainMarker = [...workspace.querySelectorAll(".mf-live-community-map__marker")]
      .find(marker => marker.getAttribute("aria-label")?.includes("Pioggia"));
    await click(rainMarker);

    const identities = workspace.querySelector(".mf-territory-map__report-community-identities");
    expect(identities.querySelector(".mf-territory-map__report-community-identities-label")?.textContent)
      .toBe("Sentinele Meteo:");
    expect(identities.querySelectorAll(".mf-community-avatar")).toHaveLength(1);
    expect(identities.textContent.split("Acuile di Pordenon")).toHaveLength(2);
    expect(identities.querySelector("button, [aria-expanded], [role='list'], .mf-territory-map__report-community-chevron"))
      .toBeNull();
  });

  it("keeps the shared non-pilot inline single identity expandable", async () => {
    vi.spyOn(localCommunityPilot, "isLocalCommunityPilot").mockReturnValue(false);
    vi.spyOn(localWeatherPilot, "isDefinitiveAppExperience").mockReturnValue(false);
    await renderPilot({ modelOptions: { explicitIdentity: true } });
    const workspace = getWorkspace();
    const rainMarker = [...workspace.querySelectorAll(".mf-live-community-map__marker")]
      .find(marker => marker.getAttribute("aria-label")?.includes("Pioggia"));
    await click(rainMarker);

    const detail = workspace.querySelector(".mf-territory-map__report-detail");
    const identities = detail.querySelector(".mf-territory-map__report-community-identities");
    const toggle = identities.querySelector(".mf-territory-map__report-community-toggle");
    const list = identities.querySelector(".mf-territory-map__report-community-list");
    expect(detail.classList.contains("mf-territory-map__report-detail--pilot")).toBe(false);
    expect(detail.querySelector(".mf-territory-map__report-community-status-main")).toBeTruthy();
    expect(detail.textContent).toContain("Riferito al Comune");
    expect(detail.querySelector(".mf-live-community-map__confirm--compact")).toBeNull();
    expect(identities.querySelector(".mf-territory-map__report-community-identities-label")?.textContent)
      .toBe("Sentinelle Meteo:");
    expect(identities.querySelector(".mf-territory-map__report-community-single")).toBeNull();
    expect(toggle.getAttribute("aria-expanded")).toBe("false");
    expect(list.hidden).toBe(true);
    await click(toggle);
    expect(toggle.getAttribute("aria-expanded")).toBe("true");
    expect(list.hidden).toBe(false);
    expect(list.querySelectorAll('[role="listitem"]')).toHaveLength(1);
  });

  it("keeps the redesigned report card in the definitive app outside the community pilot", async () => {
    vi.spyOn(localCommunityPilot, "isLocalCommunityPilot").mockReturnValue(false);
    vi.spyOn(localWeatherPilot, "isDefinitiveAppExperience").mockReturnValue(true);
    await renderPilot({
      modelOptions: { multiple: true },
      onReportConfirm: vi.fn(),
      reportingEnabled: true,
    });
    const workspace = getWorkspace();
    const windMarker = [...workspace.querySelectorAll(".mf-live-community-map__marker")]
      .find((marker) => marker.getAttribute("aria-label")?.includes("Vento forte"));

    await click(windMarker);

    const detail = workspace.querySelector(".mf-territory-map__report-detail");
    expect(detail.classList.contains("mf-territory-map__report-detail--pilot")).toBe(true);
    expect(detail.querySelector(".mf-territory-map__report-community-status-main")).toBeNull();
    expect(detail.textContent).not.toContain("Riferito al Comune");
    expect(detail.textContent).not.toContain("segnalazioni recenti");
    expect(detail.querySelector(".mf-live-community-map__confirm-button--yes")?.textContent)
      .toContain("Confermo");
    expect(detail.querySelector(".mf-live-community-map__confirm-button--no")?.textContent)
      .toContain("Non c’è più");
  });

  it("keeps original reports distinct from confirmation and denial vote counts", async () => {
    await renderPilot({
      modelOptions: { multiple: true },
      onReportConfirm: vi.fn(),
      reportingEnabled: true,
    });
    const workspace = getWorkspace();
    const windMarker = [...workspace.querySelectorAll(".mf-live-community-map__marker")]
      .find((marker) => marker.getAttribute("aria-label")?.includes("Vento forte"));

    await click(windMarker);

    const detail = workspace.querySelector(".mf-territory-map__report-detail");
    const identities = detail.querySelector(".mf-territory-map__report-community-identities");
    const status = detail.querySelector(".mf-territory-map__report-community-status");

    expect(identities).toBeTruthy();
    expect(identities.textContent).toContain(getLegacyFallbackAlias("opaque-source-b", "Cordenons"));
    expect(identities.textContent).toContain(getLegacyFallbackAlias("opaque-source-c", "Cordenons"));
    expect(identities.querySelector(".mf-territory-map__report-community-summary")?.textContent)
      .toContain("e un’altra");
    expect(status.textContent).toContain("2 segnalazioni recenti");
    expect(status.textContent).toContain("Riferito al Comune");
    expect(detail.querySelector(".mf-live-community-map__confirm-button--yes")?.textContent)
      .toContain("Confermo");
    expect(detail.querySelector(".mf-live-community-map__confirm-button--yes .mf-live-community-map__confirm-count")?.textContent)
      .toBe("1");
    expect(detail.querySelector(".mf-live-community-map__confirm-button--no")?.textContent)
      .toContain("Non c’è più");
    expect(detail.querySelector(".mf-live-community-map__confirm-button--no .mf-live-community-map__confirm-count")?.textContent)
      .toBe("1");
    expect(detail.textContent).not.toContain("Fonti anonime");
    expect(detail.textContent).not.toContain("opaque-source-b");
    expect(detail.textContent).not.toContain("opaque-source-c");
  });

  it("shows a three-avatar sentinel cluster and expands the complete source list", async () => {
    vi.spyOn(localCommunityPilot, "isLocalCommunityPilot").mockReturnValue(true);
    await renderPilot({
      modelOptions: { manySources: true },
      onReportConfirm: vi.fn(),
      reportingEnabled: true,
    });
    const workspace = getWorkspace();
    const rainMarker = [...workspace.querySelectorAll(".mf-live-community-map__marker")]
      .find((marker) => marker.getAttribute("aria-label")?.includes("Pioggia"));

    await click(rainMarker);

    const detail = workspace.querySelector(".mf-territory-map__report-detail");
    const identities = detail.querySelector(".mf-territory-map__report-community-identities");
    const sourceKeys = [
      "opaque-source-a",
      "opaque-source-b",
      "opaque-source-c",
      "opaque-source-d",
      "opaque-source-e",
    ];
    const aliases = sourceKeys.map((sourceKey) => getLegacyFallbackAlias(sourceKey));
    const label = identities.querySelector(".mf-territory-map__report-community-identities-label");
    const toggle = identities.querySelector(".mf-territory-map__report-community-toggle");
    const stack = identities.querySelector(".mf-territory-map__report-community-avatar-stack");
    const summary = identities.querySelector(".mf-territory-map__report-community-summary");
    const list = identities.querySelector(".mf-territory-map__report-community-list");

    expect(label?.textContent).toBe("Sentinelle Meteo:");
    expect(summary?.textContent).toBe(`${aliases[0]} e altri 4`);
    expect(stack?.querySelectorAll(".mf-community-avatar")).toHaveLength(3);
    expect(identities.querySelectorAll(".mf-community-avatar")).toHaveLength(3);
    expect(toggle?.getAttribute("aria-expanded")).toBe("false");
    expect(toggle?.getAttribute("aria-controls")).toBe(list?.id);
    expect(toggle?.getAttribute("aria-label")).toBe(
      `Mostra tutte le Sentinelle Meteo: ${aliases[0]} e altri 4`,
    );
    expect(list?.hidden).toBe(true);
    expect(list?.getAttribute("role")).toBe("list");
    expect(list?.querySelectorAll('[role="listitem"]')).toHaveLength(5);
    aliases.forEach((alias) => expect(list?.textContent).toContain(alias));

    await click(toggle);

    expect(toggle?.getAttribute("aria-expanded")).toBe("true");
    expect(toggle?.getAttribute("aria-label")).toBe(
      `Nascondi le Sentinelle Meteo: ${aliases[0]} e altri 4`,
    );
    expect(list?.hidden).toBe(false);
    expect(identities.textContent).not.toContain("opaque-source-");
    expect(detail.querySelector(".mf-territory-map__report-community-status-main")).toBeNull();
    expect(detail.querySelector(".mf-territory-map__report-community-status")?.textContent)
      .not.toContain("5 segnalazioni recenti");
    expect(detail.getAttribute("aria-label")).toContain("5 segnalazioni recenti");
  });

  it("localizes the sentinel cluster in Friulian", async () => {
    vi.spyOn(localCommunityPilot, "isLocalCommunityPilot").mockReturnValue(true);
    await renderPilot({
      language: "fur",
      modelOptions: { manySources: true },
      onReportConfirm: vi.fn(),
      reportingEnabled: true,
    });
    const workspace = getWorkspace();
    const rainMarker = [...workspace.querySelectorAll(".mf-live-community-map__marker")]
      .find((marker) => marker.getAttribute("aria-label")?.includes("Pioggia"));

    await click(rainMarker);

    const identities = workspace.querySelector(".mf-territory-map__report-community-identities");
    const firstAlias = getLegacyFallbackAlias("opaque-source-a");
    expect(identities?.querySelector(".mf-territory-map__report-community-identities-label")?.textContent)
      .toBe("Sentinelis Meteo:");
    expect(identities?.querySelector(".mf-territory-map__report-community-summary")?.textContent)
      .toBe(`${firstAlias} e altris 4`);
    expect(identities?.querySelector(".mf-territory-map__report-community-toggle")?.getAttribute("aria-label"))
      .toBe(`Mostre dutis lis sentinelis Meteo: ${firstAlias} e altris 4`);
  });

  it.each([
    ["orange", "Allerta arancione"],
    ["red", "Allerta rossa"],
  ])("shows the conditional %s official alert first and opens its concise details", async (
    tone,
    label,
  ) => {
    const onOfficialAlertOpen = vi.fn();
    await renderPilot({
      officialAlert: buildOfficialAlert(tone),
      onOfficialAlertOpen,
    });
    const workspace = getWorkspace();
    const controls = workspace.querySelector(".mf-territory-map__floating-controls");
    const alertControl = controls.querySelector(".mf-territory-map__control--alert");

    expect(alertControl).toBeTruthy();
    expect(alertControl).toBe(controls.firstElementChild);
    expect(alertControl.getAttribute("aria-label")).toContain(label);
    expect(alertControl.getAttribute("data-alert-tone")).toBe(tone);
    expect(alertControl.querySelector("svg")).toBeTruthy();
    expect(alertControl.querySelector("span, em")).toBeNull();
    expect(alertControl.textContent.trim()).toBe("");

    await click(alertControl);

    const detail = workspace.querySelector(
      '.mf-territory-map__alert-detail[role="dialog"]',
    );
    expect(detail).toBeTruthy();
    expect(detail.textContent).toContain(label);
    expect(detail.textContent).toContain("Livello");
    expect(detail.textContent).toContain("Validità");
    expect(detail.textContent).toContain("Valida dalle 14:00 alle 20:00");
    expect(detail.textContent).toContain("Area");
    expect(detail.textContent).toContain("Friuli Venezia Giulia - pianura e costa");
    expect(detail.textContent).toContain("Rischio");
    expect(detail.textContent).toContain(buildOfficialAlert(tone).risks[0]);
    expect(detail.textContent).toContain("Fonte");
    expect(detail.textContent).toContain("Protezione Civile FVG");

    const detailsAction = [...detail.querySelectorAll("button")]
      .find((button) => button.textContent.trim() === "Apri i dettagli ufficiali");
    await click(detailsAction);

    expect(onOfficialAlertOpen).toHaveBeenCalledTimes(1);
  });

  it.each([
    [null, "nessuna"],
    [{ ...buildOfficialAlert("orange"), label: "Allerta gialla", tone: "yellow" }, "gialla"],
  ])("does not render the official alert control for %s presentation", async (officialAlert) => {
    await renderPilot({ officialAlert });

    expect(getWorkspace().querySelector(".mf-territory-map__control--alert")).toBeNull();
  });

  it("shows candidate webcam pins when the Webcam tab opens even before editorial map approval", async () => {
    await renderPilot({ modelOptions: { community: false, mapEnabled: false } });
    const workspace = getWorkspace();

    expect(workspace.querySelector(".mf-territory-map__webcam-marker")).toBeNull();
    const webcamListTab = [...workspace.querySelectorAll(".mf-territory-map__navigation button")]
      .find((button) => button.textContent.includes("Webcam"));
    await click(webcamListTab);

    const markers = workspace.querySelectorAll(".mf-territory-map__webcam-marker");
    expect(webcamListTab.getAttribute("aria-selected")).toBe("true");
    expect(markers).toHaveLength(1);
    expect(markers[0].getAttribute("aria-label")).toContain("Sacile - Centro");
    expect(markers[0].getAttribute("aria-label")).not.toContain("Posizione dichiarata");
    expect(workspace.querySelector(".mf-territory-map--webcams-open")).toBeTruthy();
    expect(workspace.querySelector(".mf-territory-map__browse-sheet")).toBeTruthy();
    expect(workspace.querySelectorAll(".mf-territory-map__browse-list > button"))
      .toHaveLength(0);
    expect(workspace.querySelector(".mf-territory-map__browse-list")?.hidden)
      .toBe(true);
    expect(workspace.querySelector(".mf-territory-map__webcam-groups")?.textContent)
      .toContain("Vicino");
    expect(workspace.querySelector(".mf-territory-map__browse-toggle")?.textContent)
      .toContain("Vedi tutte");
    expect(workspace.querySelector('[role="status"]')?.textContent || "")
      .not.toContain("Le posizioni delle webcam saranno verificate");
  });

  it("does not trap focus in the inline dock and unwinds detail, full list, preview, then map", async () => {
    await renderPilot({
      modelOptions: { community: true, multiple: true },
      onReportSubmit: vi.fn(),
      reportingEnabled: true,
    });
    const workspace = getWorkspace();
    const canvas = workspace.querySelector(".mf-live-community-map__canvas.leaflet-container");
    const dock = workspace.querySelector(".mf-territory-map__dock");
    const reportAction = dock.querySelector(".mf-territory-map__report-action");
    const reportListTab = [...workspace.querySelectorAll(".mf-territory-map__navigation button")]
      .find((button) => button.textContent.includes("Segnalazioni"));
    await click(reportListTab);

    let sheet = workspace.querySelector(".mf-territory-map__browse-sheet");
    expect(sheet).toBeTruthy();
    expect(workspace.querySelector(".mf-territory-map--reports-empty")).toBeNull();
    expect(sheet.classList.contains("mf-territory-map__browse-sheet--compact")).toBe(true);
    expect(sheet.querySelector(".lucide-info")).toBeNull();
    expect(sheet.querySelectorAll(".mf-territory-map__browse-list > button")).toHaveLength(1);
    expect(dock.querySelector(".mf-territory-map__dock-grabber.is-interactive")).toBeNull();
    const viewAll = [...sheet.querySelectorAll("button")]
      .find((button) => button.textContent.trim().includes("Vedi tutte"));
    expect(viewAll).toBeTruthy();
    expect(viewAll?.getAttribute("aria-expanded")).toBe("false");
    expect(dock.lastElementChild).toBe(reportAction);

    reportAction.focus();
    const tabEvent = new KeyboardEvent("keydown", {
      bubbles: true,
      cancelable: true,
      key: "Tab",
    });
    await act(async () => {
      reportAction.dispatchEvent(tabEvent);
    });
    expect(tabEvent.defaultPrevented).toBe(false);
    expect(document.activeElement).toBe(reportAction);

    await click(viewAll);
    sheet = workspace.querySelector(".mf-territory-map__browse-sheet");
    expect(sheet.querySelectorAll(".mf-territory-map__browse-list > button")).toHaveLength(2);
    expect(sheet.textContent).toContain("Mostra meno");
    expect(viewAll.getAttribute("aria-expanded")).toBe("true");
    expect(workspace.querySelector(".mf-territory-map--panel-expanded")).toBeTruthy();
    expect(dock.querySelector(".mf-territory-map__dock-grabber.is-interactive"))
      .toBeTruthy();
    expect(dock.lastElementChild).toBe(reportAction);

    const firstReport = sheet.querySelector(".mf-territory-map__browse-list > button");
    await click(firstReport);
    expect(workspace.querySelector(".mf-territory-map__report-detail")).toBeTruthy();
    expect(workspace.querySelector(".mf-live-community-map__canvas")).toBe(canvas);

    await act(async () => {
      document.dispatchEvent(new KeyboardEvent("keydown", {
        bubbles: true,
        key: "Escape",
      }));
    });
    await settleEffects();

    expect(workspace.querySelector(".mf-territory-map__report-detail")).toBeNull();
    sheet = workspace.querySelector(".mf-territory-map__browse-sheet");
    expect(sheet.querySelectorAll(".mf-territory-map__browse-list > button")).toHaveLength(2);
    expect(workspace.querySelector(".mf-live-community-map__canvas")).toBe(canvas);

    await act(async () => {
      document.dispatchEvent(new KeyboardEvent("keydown", { bubbles: true, key: "Escape" }));
    });
    await settleEffects();

    sheet = workspace.querySelector(".mf-territory-map__browse-sheet");
    expect(sheet.querySelectorAll(".mf-territory-map__browse-list > button")).toHaveLength(1);
    expect(sheet.textContent).toContain("Vedi tutte");
    expect(workspace.querySelector(".mf-territory-map--panel-expanded")).toBeNull();
    expect(dock.querySelector(".mf-territory-map__dock-grabber.is-interactive")).toBeNull();

    await act(async () => {
      document.dispatchEvent(new KeyboardEvent("keydown", { bubbles: true, key: "Escape" }));
    });
    await settleEffects();

    expect(workspace.querySelector(".mf-territory-map__browse-sheet")).toBeNull();
    expect(getWorkspace()).toBe(workspace);
    expect(workspace.querySelector(".mf-live-community-map__canvas.leaflet-container")).toBe(canvas);
  });

  it("keeps the expanded report sheet and compact CTA stable behind the detail overlay", async () => {
    await renderPilot({
      modelOptions: { community: true, multiple: true },
      onReportSubmit: vi.fn(),
      reportingEnabled: true,
    });
    const workspace = getWorkspace();
    const inlineMap = workspace.querySelector(".mf-territory-map--inline");
    const dock = workspace.querySelector(".mf-territory-map__dock");
    const reportAction = dock.querySelector(".mf-territory-map__report-action");
    const reportsTab = [...dock.querySelectorAll(".mf-territory-map__navigation button")]
      .find((button) => button.textContent.includes("Segnalazioni"));
    await click(reportsTab);

    const sheet = dock.querySelector(".mf-territory-map__browse-sheet");
    const viewAll = [...sheet.querySelectorAll("button")]
      .find((button) => button.textContent.trim().includes("Vedi tutte"));
    await click(viewAll);

    const expandedDockClassName = dock.className;
    const firstReport = sheet.querySelector(".mf-territory-map__browse-list > button");
    await click(firstReport);

    const detailLayer = inlineMap.querySelector(":scope > .mf-territory-map__detail-layer");
    expect(detailLayer).toBeTruthy();
    expect(detailLayer.parentElement).toBe(inlineMap);
    expect(detailLayer.contains(dock)).toBe(false);
    expect(dock.contains(detailLayer)).toBe(false);
    expect(dock.getAttribute("aria-hidden")).toBe("true");
    expect(dock.hasAttribute("inert")).toBe(true);
    expect(dock.className).toBe(expandedDockClassName);
    expect(dock.querySelector(".mf-territory-map__browse-sheet")).toBe(sheet);
    expect(sheet.querySelectorAll(".mf-territory-map__browse-list > button")).toHaveLength(2);
    expect(dock.querySelector(".mf-territory-map__report-action")).toBe(reportAction);
    expect(dock.lastElementChild).toBe(reportAction);
    expect(reportAction.textContent).toContain("Segnala meteo");
    expect(detailLayer.textContent).not.toContain("Segnala meteo");

    const closeDetail = detailLayer.querySelector(".mf-territory-map__report-close");
    expect(closeDetail).toBeTruthy();
    expect(closeDetail.getAttribute("aria-label")).toBe("Chiudi dettaglio segnalazione");
    await click(closeDetail);

    expect(inlineMap.querySelector(".mf-territory-map__detail-layer")).toBeNull();
    expect(dock.hasAttribute("inert")).toBe(false);
    expect(dock.hasAttribute("aria-hidden")).toBe(false);
    expect(dock.querySelector(".mf-territory-map__browse-sheet")).toBe(sheet);
    expect(sheet.querySelectorAll(".mf-territory-map__browse-list > button")).toHaveLength(2);
    expect(dock.querySelector(".mf-territory-map__report-action")).toBe(reportAction);
    expect(dock.lastElementChild).toBe(reportAction);
  });

  it("keeps the inline report card to one compact community-status indicator", async () => {
    await renderPilot({
      modelOptions: { community: true, multiple: true },
      onReportConfirm: vi.fn(),
      reportingEnabled: true,
    });
    const workspace = getWorkspace();
    const windMarker = [...workspace.querySelectorAll(".mf-live-community-map__marker")]
      .find((marker) => marker.getAttribute("aria-label")?.includes("Vento forte"));

    await click(windMarker);

    const detail = workspace.querySelector(".mf-territory-map__report-detail");
    expect(detail).toBeTruthy();
    expect(detail.querySelector(".mf-territory-map__report-community-status")?.textContent)
      .toContain("2 segnalazioni recenti");
    expect(detail.querySelector(".mf-live-community-map__confirmation-summary")).toBeNull();
    expect(detail.querySelector(".mf-live-community-map__denial-status")).toBeNull();
    expect(detail.querySelector(".mf-live-community-map__denial-explanation")).toBeNull();
    expect(detail.textContent).not.toContain("parere contrario");
    expect(detail.querySelector(".mf-live-community-map__confirmation-summary--mixed"))
      .toBeNull();
  });

  it("keeps webcam area filters compact until Vedi tutte opens the selected area", async () => {
    const frames = stubAnimationFrames();
    const flushFrames = async () => {
      const pending = [...frames.values()];
      frames.clear();
      await act(async () => pending.forEach((frame) => frame()));
    };
    await renderPilot({ modelOptions: { community: true, multiple: true } });
    await flushFrames();
    const workspace = getWorkspace();
    const canvas = workspace.querySelector(".mf-live-community-map__canvas.leaflet-container");
    const dock = workspace.querySelector(".mf-territory-map__dock");
    const reportAction = dock.querySelector(".mf-territory-map__report-action");
    const webcamsTab = [...workspace.querySelectorAll(".mf-territory-map__navigation button")]
      .find((button) => button.textContent.includes("Webcam"));
    await click(webcamsTab);
    await flushFrames();

    let sheet = workspace.querySelector(".mf-territory-map__browse-sheet");
    expect(sheet.classList.contains("mf-territory-map__browse-sheet--compact"))
      .toBe(true);
    expect(sheet.querySelectorAll(".mf-territory-map__webcam-groups button")).toHaveLength(4);
    expect(sheet.querySelector(".mf-territory-map__browse-list")?.hidden).toBe(true);
    expect(sheet.querySelectorAll(".mf-territory-map__browse-list > button")).toHaveLength(0);
    expect(workspace.querySelectorAll(".mf-territory-map__webcam-marker")).toHaveLength(4);
    expect(reportAction).toBeTruthy();
    expect(dock.querySelector(".mf-territory-map__report-action")).toBeNull();
    expect(dock.lastElementChild).toBe(sheet);
    expect(dock.querySelector(".mf-territory-map__dock-grabber.is-interactive")).toBeNull();

    let groupPills = [...sheet.querySelectorAll(".mf-territory-map__webcam-groups button")];
    expect(groupPills.map((button) => button.textContent.replace(/\d+/g, "").trim()))
      .toEqual(["Vicino", "Montagna", "Pianura", "Costa"]);
    expect(groupPills[0].getAttribute("aria-pressed")).toBe("true");

    const mountain = groupPills.find((button) => button.textContent.includes("Montagna"));
    await click(mountain);
    await flushFrames();

    sheet = workspace.querySelector(".mf-territory-map__browse-sheet");
    groupPills = [...sheet.querySelectorAll(".mf-territory-map__webcam-groups button")];
    expect(groupPills.find((button) => button.textContent.includes("Montagna"))
      ?.getAttribute("aria-pressed")).toBe("true");
    expect(sheet.classList.contains("mf-territory-map__browse-sheet--compact"))
      .toBe(true);
    expect(sheet.querySelector(".mf-territory-map__browse-list")?.hidden).toBe(true);
    expect(sheet.querySelectorAll(".mf-territory-map__browse-list > button")).toHaveLength(0);
    expect(workspace.querySelector(".mf-territory-map--panel-expanded")).toBeNull();
    let markerLabels = [...workspace.querySelectorAll(".mf-territory-map__webcam-marker")]
      .map((marker) => marker.getAttribute("aria-label"));
    expect(markerLabels).toHaveLength(2);
    expect(markerLabels.some((label) => label.includes("Piancavallo - Centro"))).toBe(true);
    expect(markerLabels.some((label) => label.includes("Tarvisio - Centro"))).toBe(true);
    expect(markerLabels.some((label) => label.includes("Sacile - Centro"))).toBe(false);

    const viewAll = [...sheet.querySelectorAll("button")]
      .find((button) => button.textContent.includes("Vedi tutte"));
    expect(viewAll).toBeTruthy();
    const map = leafletHarness.maps[0];
    const fitBoundsCount = map.fitBounds.mock.calls.length;
    const setViewCount = map.setView.mock.calls.length;
    const invalidateSizeCount = map.invalidateSize.mock.calls.length;
    await click(viewAll);
    await flushFrames();
    expect(map.invalidateSize.mock.calls.length).toBeGreaterThan(invalidateSizeCount);
    expect(map.fitBounds).toHaveBeenCalledTimes(fitBoundsCount);
    expect(map.setView).toHaveBeenCalledTimes(setViewCount);

    sheet = workspace.querySelector(".mf-territory-map__browse-sheet");
    expect(sheet.querySelector(".mf-territory-map__browse-list")?.hidden).toBe(false);
    expect(sheet.querySelectorAll(".mf-territory-map__browse-list > button")).toHaveLength(2);
    expect(sheet.textContent).toContain("Piancavallo - Centro");
    expect(sheet.textContent).toContain("Tarvisio - Centro");
    expect(workspace.querySelectorAll(".mf-territory-map__webcam-marker")).toHaveLength(2);
    expect(workspace.querySelector(".mf-territory-map--panel-expanded")).toBeTruthy();

    const grabber = dock.querySelector(".mf-territory-map__dock-grabber.is-interactive");
    expect(grabber?.disabled).toBe(false);
    await act(async () => {
      grabber.dispatchEvent(new MouseEvent("pointerdown", {
        bubbles: true,
        clientX: 20,
        clientY: 40,
      }));
      grabber.dispatchEvent(new MouseEvent("pointerup", {
        bubbles: true,
        clientX: 20,
        clientY: 120,
      }));
    });
    await settleEffects();
    expect(workspace.querySelector(".mf-territory-map--panel-expanded")).toBeNull();
    expect(sheet.classList.contains("mf-territory-map__browse-sheet--compact"))
      .toBe(true);
    expect(sheet.querySelectorAll(".mf-territory-map__webcam-groups button")).toHaveLength(4);
    expect(sheet.querySelector(".mf-territory-map__browse-list")?.hidden).toBe(true);
    expect(sheet.querySelectorAll(".mf-territory-map__browse-list > button")).toHaveLength(0);

    await click(sheet.querySelector(".mf-territory-map__browse-toggle"));

    sheet = workspace.querySelector(".mf-territory-map__browse-sheet");
    expect([...sheet.querySelectorAll(".mf-territory-map__webcam-groups button")]
      .find((button) => button.textContent.includes("Montagna"))
      ?.getAttribute("aria-pressed")).toBe("true");
    expect(sheet.querySelector(".mf-territory-map__browse-list")?.textContent)
      .toContain("Piancavallo - Centro");
    expect(sheet.querySelector(".mf-territory-map__browse-list")?.textContent)
      .not.toContain("Sacile - Centro");
    expect(sheet.querySelectorAll(".mf-territory-map__browse-list > button")).toHaveLength(2);
    expect(sheet.textContent).toContain("Piancavallo - Centro");
    expect(sheet.textContent).toContain("Tarvisio - Centro");
    expect([...sheet.querySelectorAll("button")]
      .some((button) => button.textContent.includes("Mostra meno"))).toBe(true);
    expect(workspace.querySelector(".mf-territory-map--panel-expanded")).toBeTruthy();
    markerLabels = [...workspace.querySelectorAll(".mf-territory-map__webcam-marker")]
      .map((marker) => marker.getAttribute("aria-label"));
    expect(markerLabels).toHaveLength(2);
    expect(markerLabels.some((label) => label.includes("Piancavallo - Centro"))).toBe(true);
    expect(markerLabels.some((label) => label.includes("Tarvisio - Centro"))).toBe(true);
    expect(markerLabels.some((label) => label.includes("Sacile - Centro"))).toBe(false);
    expect(workspace.querySelector(".mf-live-community-map__canvas")).toBe(canvas);
    expect(dock.querySelector(".mf-territory-map__report-action")).toBeNull();
    expect(dock.lastElementChild).toBe(sheet);
  });

  it("uses the latest webcam frame in the list thumbnail and falls back to its territorial image", async () => {
    await renderPilot({ modelOptions: { community: false, multiple: true } });
    const workspace = getWorkspace();
    const webcamsTab = [...workspace.querySelectorAll(".mf-territory-map__navigation button")]
      .find((button) => button.textContent.includes("Webcam"));
    await click(webcamsTab);
    await click(workspace.querySelector(".mf-territory-map__browse-toggle"));

    const sacileRow = [...workspace.querySelectorAll(".mf-territory-map__browse-item--webcam")]
      .find((button) => button.textContent.includes("Sacile - Centro"));
    const thumbnail = sacileRow?.querySelector(".mf-territory-map__webcam-thumbnail");
    let image = thumbnail?.querySelector("img");

    expect(thumbnail).toBeTruthy();
    expect(thumbnail.getAttribute("aria-hidden")).toBe("true");
    expect(image?.getAttribute("alt")).toBe("");
    expect(image?.getAttribute("loading")).toBe("lazy");
    expect(image?.getAttribute("src"))
      .toBe("https://images.example.test/webcams/sacile-centro.jpg");

    await act(async () => {
      image.dispatchEvent(new Event("error"));
    });
    await settleEffects();

    image = thumbnail.querySelector("img");
    expect(image?.getAttribute("src"))
      .toBe("/municipalities/photos/093037-photo.webp");
  });

  it("highlights a webcam pin from the list and opens its detail without leaving the Webcam tab", async () => {
    await renderPilot({ modelOptions: { community: true, multiple: true } });
    const workspace = getWorkspace();
    const webcamsTab = [...workspace.querySelectorAll(".mf-territory-map__navigation button")]
      .find((button) => button.textContent.includes("Webcam"));
    await click(webcamsTab);
    await click(workspace.querySelector(".mf-territory-map__browse-toggle"));

    const sacileRow = [...workspace.querySelectorAll(".mf-territory-map__browse-item--webcam")]
      .find((button) => button.textContent.includes("Sacile - Centro"));
    const sacileMarker = [...workspace.querySelectorAll(".mf-territory-map__webcam-marker")]
      .find((marker) => marker.getAttribute("aria-label")?.includes("Sacile - Centro"));

    await act(async () => sacileRow.focus());
    await settleEffects();
    expect(sacileMarker.classList.contains("is-highlighted")).toBe(true);

    await act(async () => sacileRow.blur());
    await settleEffects();
    expect(sacileMarker.classList.contains("is-highlighted")).toBe(false);

    await act(async () => {
      sacileRow.dispatchEvent(new Event("pointerover", { bubbles: true }));
    });
    await settleEffects();
    expect(sacileMarker.classList.contains("is-highlighted")).toBe(true);

    await act(async () => {
      sacileRow.dispatchEvent(new Event("pointerout", { bubbles: true }));
    });
    await settleEffects();
    expect(sacileMarker.classList.contains("is-highlighted")).toBe(false);

    await click(sacileMarker);

    const detail = workspace.querySelector('.mf-territory-map__webcam-detail[role="dialog"]');
    const detailLayer = workspace.querySelector(":scope .mf-territory-map__detail-layer");
    expect(detail).toBeTruthy();
    expect(detail.getAttribute("aria-modal")).toBe("true");
    expect(detailLayer?.contains(detail)).toBe(true);
    expect(detail.querySelector(".mf-live-community-map__detail-heading strong")?.textContent)
      .toBe("Centro");
    expect(detail.querySelector(".mf-live-community-map__detail-heading span")?.textContent)
      .toContain("Sacile");
    expect(detail.querySelector(".mf-live-community-map__detail-heading span")?.textContent)
      .not.toContain("Centro");
    expect(detail.textContent).not.toContain("Posizione dichiarata");
    expect(webcamsTab.getAttribute("aria-selected")).toBe("true");
    expect(workspace.querySelector(".mf-territory-map--webcams-open")).toBeTruthy();
  });

  it("toggles radar independently without removing community markers", async () => {
    await renderPilot({
      modelOptions: { community: true, mapEnabled: true },
      onReportSubmit: vi.fn(),
      reportingEnabled: true,
    });
    const workspace = getWorkspace();
    const inlineMap = workspace.querySelector(".mf-territory-map--inline");
    const canvas = workspace.querySelector(".mf-live-community-map__canvas");
    const dock = workspace.querySelector(".mf-territory-map__dock");
    const navigation = dock.querySelector(".mf-territory-map__navigation");
    const radar = workspace.querySelector('button[aria-label="Radar"]');
    const radarLayerCallsBeforeToggle = radarLayerHarness.create.mock.calls.length;

    expect(workspace.querySelectorAll(".mf-live-community-map__marker")).toHaveLength(1);
    expect(workspace.querySelector(".mf-territory-map__webcam-markers")).toBeNull();
    await click(radar);

    expect(radar.getAttribute("aria-pressed")).toBe("true");
    expect(workspace.querySelectorAll(".mf-live-community-map__marker")).toHaveLength(1);
    const overlay = workspace.querySelector(".mf-territory-radar-overlay");
    expect(overlay).toBeTruthy();
    expect(inlineMap.classList.contains("mf-territory-map--radar-active")).toBe(true);
    expect(dock.classList.contains("mf-territory-map__dock--radar")).toBe(true);
    const radarGrabber = dock.querySelector(".mf-territory-map__dock-grabber");
    expect(radarGrabber?.tagName).toBe("SPAN");
    expect(radarGrabber?.getAttribute("aria-hidden")).toBe("true");
    expect(radarGrabber?.getAttribute("tabindex")).toBeNull();
    expect(overlay.parentElement).toBe(dock);
    expect(dock.querySelector(".mf-territory-map__report-action")).toBeNull();
    expect([...dock.children]).toEqual([radarGrabber, overlay, navigation]);
    expect(workspace.querySelector(".mf-live-community-map__canvas")).toBe(canvas);
    expect(workspace.querySelector(".mf-territory-map__webcam-markers")).toBeNull();
    expect(radarLayerHarness.create).toHaveBeenCalledTimes(radarLayerCallsBeforeToggle + 1);

    await click(radar);

    expect(radar.getAttribute("aria-pressed")).toBe("false");
    expect(workspace.querySelector(".mf-territory-radar-overlay")).toBeNull();
    expect(inlineMap.classList.contains("mf-territory-map--radar-active")).toBe(false);
    expect(dock.classList.contains("mf-territory-map__dock--radar")).toBe(false);
    const restoredGrabber = dock.querySelector(".mf-territory-map__dock-grabber");
    const restoredReportAction = dock.querySelector(".mf-territory-map__report-action");
    expect(restoredGrabber?.getAttribute("aria-hidden")).toBe("true");
    expect(restoredReportAction?.textContent).toContain("Segnala meteo");
    expect(restoredReportAction?.disabled).toBe(false);
    expect([...dock.children]).toEqual([restoredGrabber, navigation, restoredReportAction]);
    expect(workspace.querySelector(".mf-live-community-map__canvas")).toBe(canvas);
    expect(workspace.querySelectorAll(".mf-live-community-map__marker")).toHaveLength(1);

    await click(radar);
    const reportsTab = [...navigation.querySelectorAll("button")]
      .find((button) => button.textContent.includes("Segnalazioni"));
    await click(reportsTab);

    expect(radar.getAttribute("aria-pressed")).toBe("false");
    expect(workspace.querySelector(".mf-territory-radar-overlay")).toBeNull();
    expect(inlineMap.classList.contains("mf-territory-map--radar-active")).toBe(false);
    expect(dock.classList.contains("mf-territory-map__dock--radar")).toBe(false);
    expect(reportsTab.getAttribute("aria-selected")).toBe("true");
    expect(dock.querySelector(".mf-territory-map__browse-sheet")).toBeTruthy();
  });

  it("toggles the Webcam browse tab from the floating control", async () => {
    await renderPilot({
      modelOptions: { community: true, mapEnabled: true, multiple: true },
    });
    const workspace = getWorkspace();
    const webcamControl = workspace.querySelector(
      ".mf-territory-map__control--webcam",
    );

    await click(webcamControl);

    const webcamTab = [...workspace.querySelectorAll('[role="tab"]')]
      .find((tab) => tab.textContent.includes("Webcam"));
    expect(webcamTab).toBeTruthy();
    expect(webcamTab.getAttribute("aria-selected")).toBe("true");
    expect(workspace.querySelector(".mf-territory-map__browse-sheet")?.textContent)
      .toContain("Vedi tutte");
    expect(workspace.querySelector(".mf-territory-map__browse-sheet")?.textContent)
      .toContain("Vicino");
    expect(workspace.querySelectorAll(".mf-territory-map__browse-list > button"))
      .toHaveLength(0);
    expect(workspace.querySelector(".mf-territory-map__webcam-markers")).toBeTruthy();

    await click(webcamControl);

    const mapTab = [...workspace.querySelectorAll('[role="tab"]')]
      .find((tab) => tab.textContent.includes("Mappa"));
    expect(mapTab.getAttribute("aria-selected")).toBe("true");
    expect(webcamControl.getAttribute("aria-expanded")).toBe("false");
    expect(workspace.querySelector(".mf-territory-map__browse-sheet")).toBeNull();
    expect(workspace.querySelector(".mf-territory-map__webcam-markers")).toBeNull();
  });

  it("keeps GPS as a momentary centering action rather than a toggle", async () => {
    await renderPilot();
    const workspace = getWorkspace();
    const gps = workspace.querySelector(".mf-territory-map__control--gps");
    const map = leafletHarness.maps[0];
    const setViewCallsBeforeTap = map.setView.mock.calls.length;

    expect(gps).toBeTruthy();
    expect(gps.hasAttribute("aria-pressed")).toBe(false);

    await click(gps);

    expect(gps.hasAttribute("aria-pressed")).toBe(false);
    expect(map.setView).toHaveBeenCalledTimes(setViewCallsBeforeTap + 1);
    expect(map.setView).toHaveBeenLastCalledWith(
      [45.9567, 12.6605],
      10,
      { animate: true },
    );
  });

  it("keeps an unavailable radar visibly disabled without affecting community markers", async () => {
    await renderPilot({
      modelOptions: { community: true },
      radarModel: buildUnavailableRadarModel(),
    });
    const workspace = getWorkspace();
    const radar = workspace.querySelector(
      'button[aria-label="Radar temporaneamente non disponibile"]',
    );

    expect(radar).toBeTruthy();
    expect(radar.disabled).toBe(true);
    expect(radar.getAttribute("aria-pressed")).toBe("false");
    expect(workspace.querySelector(".mf-territory-radar-overlay--unavailable")).toBeNull();
    expect(workspace.querySelectorAll(".mf-live-community-map__marker")).toHaveLength(1);
    expect(radarLayerHarness.create).not.toHaveBeenCalled();
  });

  it("keeps the regional reporting rollout explanation visible while radar is active", async () => {
    const message = "Le segnalazioni partecipative non sono ancora attive in questa regione.";
    await renderPilot({
      onReportSubmit: vi.fn(),
      reportingEnabled: false,
      reportingUnavailableText: message,
    });
    const workspace = getWorkspace();

    await click(workspace.querySelector('button[aria-label="Radar"]'));

    const unavailable = workspace.querySelector(".mf-territory-map__report-unavailable");
    expect(unavailable?.textContent).toBe(message);
    expect(workspace.querySelector(".mf-territory-map--radar-active")).toBeTruthy();
  });

  it("keeps the same Leaflet map mounted while switching internal sections", async () => {
    await renderPilot({ modelOptions: { community: true } });
    const workspace = getWorkspace();
    const canvas = workspace.querySelector(".mf-live-community-map__canvas.leaflet-container");
    const map = leafletHarness.maps[0];
    const tabs = [...workspace.querySelectorAll(".mf-territory-map__navigation button")];
    const reportsTab = tabs.find((button) => button.textContent.includes("Segnalazioni"));
    const webcamsTab = tabs.find((button) => button.textContent.includes("Webcam"));
    const mapTab = tabs.find((button) => button.textContent.includes("Mappa"));

    await click(reportsTab);
    expect(workspace.querySelector(".mf-territory-map__browse-sheet")).toBeTruthy();
    expect(workspace.querySelector(".mf-live-community-map__canvas")).toBe(canvas);

    await click(webcamsTab);
    expect(workspace.querySelector(".mf-territory-map__browse-sheet")?.textContent)
      .toContain("Vicino");
    expect(workspace.querySelectorAll(".mf-territory-map__browse-list > button"))
      .toHaveLength(0);
    expect(workspace.querySelector(".mf-live-community-map__canvas")).toBe(canvas);

    await click(mapTab);
    expect(workspace.querySelector(".mf-territory-map__browse-sheet")).toBeNull();
    expect(workspace.querySelector(".mf-live-community-map__canvas")).toBe(canvas);
    expect(leafletHarness.api.map).toHaveBeenCalledTimes(1);
    expect(map.fitBounds).not.toHaveBeenCalled();
    expect(map.setZoom).not.toHaveBeenCalled();
    expect(map.remove).not.toHaveBeenCalled();
  });
});
