import { describe, expect, it } from "vitest";

import {
  createFallbackCommunityIdentitySnapshot,
  normalizePublicCommunityIdentitySnapshot,
} from "../community/communityIdentity";
import { buildLiveViewModel } from "./liveViewModel";

const RAIN_IDENTITY_WIRE = {
  alias: "Clâf di Pordenon",
  avatar: {
    angle: 135,
    palette_id: "sky",
    pattern_id: "diagonal",
    variant: 2,
  },
  subject_id: "claf",
  version: 1,
};

function buildDataState() {
  return {
    community: {
      status: "fresh",
      payload: {
        max_distance_km: 5,
        map_groups: [
          {
            confirmations: { no: 0, yes: 3 },
            count: 2,
            createdAt: Date.parse("2026-08-03T10:21:00Z"),
            expiresAt: Date.parse("2026-08-03T11:21:00Z"),
            groupId: "group-rain:pordenone:1",
            id: "group-rain:pordenone:1",
            lat: 45.9569,
            lon: 12.6605,
            place: "Pordenone",
            source_keys: ["opaque-source-a"],
            typeId: "rain",
            x: 42,
            y: 61,
          },
        ],
        reports: [
          {
            createdAt: Date.parse("2026-08-03T10:20:00Z"),
            expiresAt: Date.parse("2026-08-03T11:20:00Z"),
            groupId: "group-rain:pordenone:1",
            id: "report-1",
            lat: 45.9569,
            lon: 12.6605,
            place: "Pordenone",
            source_key: "opaque-source-a",
            typeId: "rain",
          },
        ],
      },
    },
    webcams: {
      status: "fresh",
      payload: {
        ok: true,
        source_url: "F:/private/webcams.json",
        webcams: [
          {
            area: "Sacile",
            group: "plain",
            health: "ok",
            id: "sacile",
            imageUrl: "https://images.example.test/sacile.jpg",
            name: "Sacile",
            provider: "Protezione Civile FVG",
            sourcePage: "https://www.osmer.fvg.it/webcam_img.php?ln=it",
          },
          {
            area: "Piancavallo",
            group: "mountain",
            health: "degraded",
            id: "piancavallo-nevelandia",
            imageUrl: "https://images.example.test/piancavallo.jpg",
            name: "Piancavallo",
            provider: "OSMER",
            sourcePage: "https://www.osmer.fvg.it/webcam_img.php?ln=it",
          },
          {
            area: "Grado",
            group: "coast",
            health: "ok",
            id: "grado-spiaggia",
            imageUrl: "https://images.example.test/grado.jpg",
            name: "Grado",
            provider: "OSMER",
            sourcePage: "https://www.osmer.fvg.it/webcam_img.php?ln=it",
          },
        ],
      },
    },
  };
}

describe("live view model", () => {
  it("orders community activity by recency before distance", () => {
    const dataState = buildDataState();
    dataState.community.payload.map_groups = [
      {
        count: 1,
        createdAt: Date.parse("2026-08-03T10:20:00Z"),
        expiresAt: Date.parse("2026-08-03T11:20:00Z"),
        groupId: "nearer-older",
        id: "nearer-older",
        lat: 45.9567,
        lon: 12.6605,
        place: "Pordenone",
        typeId: "rain",
      },
      {
        count: 1,
        createdAt: Date.parse("2026-08-03T10:24:00Z"),
        expiresAt: Date.parse("2026-08-03T11:24:00Z"),
        groupId: "farther-newer",
        id: "farther-newer",
        lat: 45.98,
        lon: 12.7,
        place: "Cordenons",
        typeId: "wind",
      },
    ];
    const model = buildLiveViewModel(dataState, {
      location: { city: "Pordenone", lat: 45.9567, lon: 12.6605 },
      now: new Date("2026-08-03T10:25:00Z"),
    });

    expect(model.community.items.map((item) => item.groupId)).toEqual([
      "farther-newer",
      "nearer-older",
    ]);
  });

  it("prioritizes cameras around the selected location without exposing backend paths", () => {
    const model = buildLiveViewModel(buildDataState(), {
      language: "it",
      location: { city: "Pordenone", lat: 45.9567, lon: 12.6605 },
      now: new Date("2026-08-03T10:25:00Z"),
    });

    expect(model.title).toBe("Territorio");
    expect(model.locationLabel).toBe("Pordenone");
    expect(model.locationPoint).toEqual({ lat: 45.9567, lon: 12.6605 });
    expect(model.webcams.groups.map((group) => group.id)).toEqual([
      "nearby",
      "mountain",
      "plain",
      "coast",
    ]);
    expect(model.webcams.groups[0].cameras[0]).toMatchObject({
      id: "sacile",
      place: "Sacile",
    });
    expect(model.webcams.mapCandidates).toHaveLength(3);
    expect(model.webcams.mapItems).toEqual([]);
    expect(JSON.stringify(model)).not.toContain("F:/private");
  });

  it("selects nearby localities without cutting an explicit multi-camera place cluster", () => {
    const dataState = buildDataState();
    const lignano = Array.from({ length: 5 }, (_, index) => ({
      group: "coast",
      id: `lignano-${index + 1}`,
      imageUrl: `https://images.example.test/lignano-${index + 1}.jpg`,
      lat: 45.8 + index * 0.001,
      lon: 12.8 + index * 0.001,
      mapClusterId: "lignano-sabbiadoro",
      mapClusterLabel: "Lignano Sabbiadoro",
      municipality: "Lignano Sabbiadoro",
      name: `Lignano ${index + 1}`,
      sortOrder: index + 1,
      sourcePage: `https://example.test/webcam/lignano-${index + 1}`,
    }));
    const otherPlaces = Array.from({ length: 5 }, (_, index) => ({
      group: "plain",
      id: `place-${index + 1}`,
      imageUrl: `https://images.example.test/place-${index + 1}.jpg`,
      lat: 45.81 + index * 0.08,
      lon: 12.81 + index * 0.08,
      municipality: `Località ${index + 1}`,
      name: `Località ${index + 1}`,
      sortOrder: 20 + index,
      sourcePage: `https://example.test/webcam/place-${index + 1}`,
    }));
    dataState.webcams.payload.webcams = [...lignano, ...otherPlaces];

    const model = buildLiveViewModel(dataState, {
      location: { city: "Pordenone", lat: 45.8, lon: 12.8 },
    });
    const nearby = model.webcams.groups.find((group) => group.id === "nearby");
    const nearbyIds = nearby.cameras.map((camera) => camera.id);

    expect(nearbyIds.filter((id) => id.startsWith("lignano-"))).toEqual([
      "lignano-1",
      "lignano-2",
      "lignano-3",
      "lignano-4",
      "lignano-5",
    ]);
    expect(new Set(nearby.cameras.map((camera) => camera.mapClusterId || camera.id)).size)
      .toBe(5);
    expect(nearbyIds).not.toContain("place-5");
  });

  it("does not reinterpret cached FVG webcams as nearby national webcams", () => {
    const model = buildLiveViewModel(buildDataState(), {
      language: "it",
      location: { city: "Roma", countryCode: "IT", lat: 41.9028, lon: 12.4964 },
      webcamsEnabled: false,
    });

    expect(model.locationLabel).toBe("Roma");
    expect(model.webcams).toMatchObject({
      available: false,
      emptyBody: "Le webcam editoriali sono disponibili soltanto in Friuli Venezia Giulia.",
      emptyTitle: "Webcam non disponibili in quest’area",
      groups: [],
      mapCandidates: [],
      mapItems: [],
      status: { id: "unsupported" },
      supported: false,
    });
    expect(JSON.stringify(model.webcams)).not.toContain("Sacile");
    expect(JSON.stringify(model.webcams)).not.toContain("Piancavallo");
  });

  it("falls back to municipality coordinates when stored coordinates are null", () => {
    const model = buildLiveViewModel(buildDataState(), {
      location: { city: "Pordenone", lat: null, lon: null },
    });

    expect(model.webcams.groups[0].id).toBe("nearby");
    expect(model.webcams.groups[0].cameras[0].id).toBe("sacile");
    expect(model.webcams.groups[0].cameras[0].distanceKm).toBeLessThan(20);
  });

  it("adds municipality fallback coordinates to the pilot map without changing beta nearby ranking", () => {
    const dataState = buildDataState();
    dataState.webcams.payload.webcams = [{
      fallbackImageUrl: "/municipalities/photos/030129-photo.webp",
      group: "plain",
      id: "new-udine-camera",
      mapEnabled: true,
      municipality: "Udine",
      name: "Udine - Centro",
      sourcePage: "https://example.test/webcam/udine",
    }];

    const model = buildLiveViewModel(dataState, {
      location: { city: "Udine", lat: 46.0635, lon: 13.2358 },
    });
    const camera = model.webcams.mapItems[0];

    expect(camera).toMatchObject({
      id: "new-udine-camera",
      mapEnabled: true,
      positionIsApproximate: true,
      positionPrecision: "municipality",
    });
    expect(Number.isFinite(camera.lat)).toBe(true);
    expect(Number.isFinite(camera.lon)).toBe(true);
    expect(camera.distanceKm).toBeNull();
    expect(model.webcams.groups.some((group) => group.id === "nearby")).toBe(false);
  });

  it("preserves declared camera coordinates for the map and distance ranking", () => {
    const dataState = buildDataState();
    const camera = dataState.webcams.payload.webcams.find(
      (item) => item.id === "piancavallo-nevelandia",
    );
    camera.lat = 45.9568;
    camera.lon = 12.6606;
    camera.mapEnabled = true;

    const model = buildLiveViewModel(dataState, {
      location: { city: "Pordenone", lat: 45.9567, lon: 12.6605 },
    });
    const nearbyCamera = model.webcams.groups[0].cameras[0];

    expect(nearbyCamera.id).toBe("piancavallo-nevelandia");
    expect(nearbyCamera.distanceKm).toBeLessThan(0.1);
    expect(nearbyCamera.distanceLabel).toBe("0 km");
    expect(nearbyCamera).toMatchObject({
      lat: 45.9568,
      lon: 12.6606,
      positionIsApproximate: false,
      positionPrecision: "declared",
    });
    expect(model.webcams.mapItems.find((item) => item.id === nearbyCamera.id)).toBe(nearbyCamera);
  });

  it("marks municipality-centre fallback distances as approximate", () => {
    const dataState = buildDataState();
    dataState.webcams.payload.webcams.find(
      (camera) => camera.id === "piancavallo-nevelandia",
    ).map_enabled = true;
    const model = buildLiveViewModel(dataState, {
      location: { city: "Pordenone", lat: 45.9567, lon: 12.6605 },
    });
    const piancavallo = model.webcams.groups
      .flatMap((group) => group.cameras)
      .find((camera) => camera.id === "piancavallo-nevelandia");

    expect(piancavallo.distanceLabel).toMatch(/^~/);
    expect(piancavallo).toMatchObject({
      lat: 46.07056,
      lon: 12.59472,
      positionIsApproximate: true,
      positionPrecision: "municipality",
    });
    expect(model.webcams.mapItems.find((item) => item.id === piancavallo.id)).toBe(piancavallo);
  });

  it("keeps source checks separate from authentic snapshot capture times", () => {
    const dataState = buildDataState();
    dataState.webcams.payload.webcams = [{
      area: "Centro",
      captured_at: "2026-08-03T10:20:00Z",
      checkedAt: "2026-08-03T10:24:00Z",
      fallbackImageUrl: "/municipalities/photos/093033-photo.webp",
      group: "plain",
      health: "ok",
      id: "pordenone-snapshot",
      imageUrl: "https://images.example.test/pordenone.jpg",
      lat: 45.9567,
      lon: 12.6605,
      mapEnabled: true,
      mediaType: "snapshot",
      municipality: "Pordenone",
      name: "Pordenone - Centro",
      sourcePage: "https://example.test/webcam/pordenone",
    }];

    const model = buildLiveViewModel(dataState, {
      location: { city: "Pordenone", lat: 45.9567, lon: 12.6605 },
    });
    const camera = model.webcams.mapItems[0];

    expect(camera).toMatchObject({
      capturedAt: "2026-08-03T10:20:00Z",
      checkedAt: "2026-08-03T10:24:00Z",
      mediaMode: "snapshot",
      mediaType: "snapshot",
    });
    expect(camera.capturedAt).not.toBe(camera.checkedAt);
  });

  it("does not invent a capture time from the source check", () => {
    const dataState = buildDataState();
    dataState.webcams.payload.webcams[0].checked_at = "2026-08-03T10:24:00Z";

    const model = buildLiveViewModel(dataState, {
      location: { city: "Sacile", lat: 45.9541, lon: 12.5027 },
    });
    const camera = model.webcams.mapCandidates.find((item) => item.id === "sacile");

    expect(camera.checkedAt).toBe("2026-08-03T10:24:00Z");
    expect(camera.capturedAt).toBe("");
  });

  it("normalizes player, fallback and source-only map modes without changing carousel eligibility", () => {
    const dataState = buildDataState();
    dataState.webcams.payload.webcams = [
      {
        fallbackImageUrl: "/municipalities/photos/030099-photo.webp",
        group: "plain",
        id: "san-daniele-centro",
        mapEnabled: true,
        mediaType: "iframe",
        municipality: "San Daniele del Friuli",
        name: "San Daniele del Friuli - Centro",
        playerUrl: "https://sandanieledelfriuli.panomax.com/",
        sourcePage: "https://sandanieledelfriuli.panomax.com/",
      },
      {
        fallbackImageUrl: "/municipalities/photos/030043-photo.webp",
        group: "plain",
        id: "gemona-centro",
        map_enabled: true,
        municipality: "Gemona del Friuli",
        name: "Gemona - Centro",
        sourcePage: "https://example.test/webcam/gemona",
      },
      {
        group: "plain",
        id: "pordenone-source-only",
        map_status: "map_ready",
        municipality: "Pordenone",
        name: "Pordenone - Fonte",
        sourcePage: "https://example.test/webcam/pordenone",
      },
    ];

    const model = buildLiveViewModel(dataState, {
      location: { city: "Pordenone", lat: 45.9567, lon: 12.6605 },
    });

    expect(model.webcams.mapItems.map(({ id, mediaMode }) => [id, mediaMode])).toEqual([
      ["san-daniele-centro", "player"],
      ["gemona-centro", "fallback"],
      ["pordenone-source-only", "source"],
    ]);
    const carouselIds = model.webcams.groups
      .filter((group) => group.id !== "nearby")
      .flatMap((group) => group.cameras.map((camera) => camera.id));
    expect(carouselIds).toEqual(["san-daniele-centro", "gemona-centro"]);
  });

  it("keeps a static territorial photo and external link when no webcam frame is embedded", () => {
    const dataState = buildDataState();
    dataState.webcams.payload.webcams = [{
      area: "Piazza Italia",
      fallbackImageUrl: "/municipalities/photos/093025-photo.webp",
      group: "plain",
      health: "ok",
      id: "maniago-centro",
      lat: 46.1706,
      lon: 12.7078,
      municipality: "Maniago",
      name: "Maniago - Piazza Italia",
      sourcePage: "https://example.test/webcam/maniago",
    }];

    const model = buildLiveViewModel(dataState, {
      location: { city: "Maniago", lat: 46.1706, lon: 12.7078 },
    });
    const camera = model.webcams.groups[0].cameras[0];

    expect(camera).toMatchObject({
      fallbackImageUrl: "/municipalities/photos/093025-photo.webp",
      imageUrl: "",
      locationLabel: "Maniago - Piazza Italia",
      name: "Maniago - Piazza Italia",
      provider: "Fonte esterna",
      sourceUrl: "https://example.test/webcam/maniago",
    });
    expect(camera.distanceKm).toBe(0);
    expect(camera.distanceLabel).toBe("0 km");
  });

  it.each([
    ["mediaType", "photo"],
    ["media_type", "static"],
  ])("recognizes %s as a static-media declaration", (field, value) => {
    const dataState = buildDataState();
    dataState.webcams.payload.webcams = [{
      area: "Centro",
      group: "plain",
      health: "ok",
      id: `static-${field}`,
      imageUrl: "https://images.example.test/static-photo.jpg",
      lat: 45.9567,
      lon: 12.6605,
      municipality: "Pordenone",
      name: "Pordenone - Centro",
      [field]: value,
    }];

    const model = buildLiveViewModel(dataState, {
      location: { city: "Pordenone", lat: 45.9567, lon: 12.6605 },
    });
    const camera = model.webcams.groups[0].cameras[0];

    expect(camera).toMatchObject({
      fallbackImageUrl: "https://images.example.test/static-photo.jpg",
      imageUrl: "",
    });
  });

  it("exposes only a reviewed Panomax iframe player", () => {
    const dataState = buildDataState();
    dataState.webcams.payload.webcams = [{
      area: "Centro",
      fallbackImageUrl: "/municipalities/photos/030099-photo.webp",
      group: "plain",
      health: "ok",
      id: "san-daniele-centro",
      mediaType: "iframe",
      municipality: "San Daniele del Friuli",
      name: "San Daniele del Friuli - Centro",
      playerUrl: "https://sandanieledelfriuli.panomax.com/",
    }];

    const model = buildLiveViewModel(dataState, {
      location: { city: "San Daniele del Friuli", lat: 46.1572, lon: 13.0095 },
    });
    const camera = model.webcams.groups[0].cameras[0];

    expect(camera).toMatchObject({
      mediaType: "iframe",
      playerUrl: "https://sandanieledelfriuli.panomax.com/",
    });
  });

  it("drops an unreviewed iframe player while keeping the territorial fallback", () => {
    const dataState = buildDataState();
    dataState.webcams.payload.webcams = [{
      fallbackImageUrl: "/municipalities/photos/093037-photo.webp",
      group: "plain",
      id: "sacile",
      mediaType: "iframe",
      name: "Sacile",
      playerUrl: "https://video.example.test/embed/sacile",
    }];

    const model = buildLiveViewModel(dataState, {
      location: { city: "Sacile", lat: 45.9541, lon: 12.5027 },
    });
    const camera = model.webcams.groups[0].cameras[0];

    expect(camera).toMatchObject({
      fallbackImageUrl: "/municipalities/photos/093037-photo.webp",
      mediaType: "",
      playerUrl: "",
    });
  });

  it("canonicalizes punctuation-only location variants without losing the distance", () => {
    const dataState = buildDataState();
    dataState.webcams.payload.webcams = [{
      area: "Piazza Italia",
      fallbackImageUrl: "/municipalities/photos/093025-photo.webp",
      group: "plain",
      health: "ok",
      id: "maniago-punctuation",
      lat: 46.1706,
      lon: 12.7078,
      municipality: "Maniago",
      name: "Maniago / Piazza Italia",
    }];

    const model = buildLiveViewModel(dataState, {
      location: { city: "Maniago", lat: 46.1706, lon: 12.7078 },
    });
    const camera = model.webcams.groups[0].cameras[0];

    expect(camera.locationLabel).toBe("Maniago / Piazza Italia");
    expect(camera.locationLabel).toBe(camera.name);
    expect(camera.distanceLabel).toBe("0 km");
  });

  it("removes a shorter area already contained in the municipality", () => {
    const dataState = buildDataState();
    dataState.webcams.payload.webcams = [{
      area: "Lignano",
      fallbackImageUrl: "/municipalities/photos/030049-photo.webp",
      group: "coast",
      health: "ok",
      id: "lignano-punta-faro",
      lat: 45.697154,
      lon: 13.152703,
      municipality: "Lignano Sabbiadoro",
      name: "Lignano Sabbiadoro - Punta Faro",
    }];

    const model = buildLiveViewModel(dataState, {
      location: { city: "Pordenone", lat: 45.9567, lon: 12.6605 },
    });
    const camera = model.webcams.groups.flatMap((group) => group.cameras)[0];

    expect(camera.locationLabel).toBe("Lignano Sabbiadoro");
  });

  it("uses the locality in visible labels without losing coordinate ranking", () => {
    const model = buildLiveViewModel(buildDataState(), {
      language: "it",
      location: {
        city: "Fontanafredda",
        displayName: "Vigonovo",
        locality: { id: "irdat:vigonovo", name: "Vigonovo" },
        municipality: { istatCode: "093022", name: "Fontanafredda" },
        lat: 45.9892,
        lon: 12.5473,
      },
    });

    expect(model.locationLabel).toBe("Vigonovo");
    expect(model.webcams.groups.find((group) => group.id === "nearby")?.place).toBe("Vigonovo");
  });

  it("keeps per-camera health separate from the endpoint state", () => {
    const model = buildLiveViewModel(buildDataState(), {
      location: { city: "Pordenone" },
    });
    const mountain = model.webcams.groups.find((group) => group.id === "mountain");

    expect(model.webcams.status).toMatchObject({ label: "Fonte attiva", tone: "ok" });
    expect(mountain.cameras[0].health).toMatchObject({
      label: "Fonte instabile",
      tone: "neutral",
    });
    expect(mountain.cameras[0].locationLabel).toBe("Aviano · Piancavallo");
  });

  it("normalizes nearby community reports and their lifetime", () => {
    const dataState = buildDataState();
    dataState.community.ageMs = 90_000;
    dataState.community.payload.generated_at = "2026-08-03T10:24:00Z";
    const model = buildLiveViewModel(dataState, {
      location: { city: "Pordenone", lat: 45.9567, lon: 12.6605 },
      now: new Date("2026-08-03T10:25:00Z"),
    });

    expect(model.community.items).toHaveLength(1);
    expect(model.community.items[0]).toMatchObject({
      count: 2,
      countLabel: "2 segnalazioni",
      confirmations: { no: 0, yes: 3 },
      groupId: "group-rain:pordenone:1",
      id: "group-rain:pordenone:1",
      place: "Pordenone",
      sourceKey: "opaque-source-a",
      sourceKeys: ["opaque-source-a"],
      timeLabel: "4 min fa",
      typeId: "rain",
      typeLabel: "Pioggia",
    });
    expect(model.community.items[0].contributions).toEqual([
      expect.objectContaining({
        id: "report-1",
        sourceKey: "opaque-source-a",
        sourceKeys: ["opaque-source-a"],
      }),
    ]);
    expect(model.community.markers[0]).toMatchObject({
      confirmations: { no: 0, yes: 3 },
      count: 2,
      countLabel: "2 segnalazioni",
      groupId: "group-rain:pordenone:1",
      lat: 45.9569,
      lon: 12.6605,
      sourceKey: "opaque-source-a",
      sourceKeys: ["opaque-source-a"],
      typeId: "rain",
    });
    expect(model.community.reportOptions.some((item) => item.id === "storm")).toBe(true);
    expect(model.community.maxDistanceKm).toBe(5);
    expect(model.community.reportLocations).toHaveLength(215);
    expect(model.community.sourceAgeMs).toBe(90_000);
    expect(model.community.sourceUpdatedAt).toBe("2026-08-03T10:24:00Z");
  });

  it("uses the latest server update for recency while retaining origin and revision", () => {
    const dataState = buildDataState();
    dataState.community.payload.map_groups = [];
    dataState.community.payload.reports = [
      {
        ...dataState.community.payload.reports[0],
        createdAt: Date.parse("2026-08-03T09:30:00Z"),
        expiresAt: Date.parse("2026-08-03T11:59:00Z"),
        revision: 2,
        updatedAt: Date.parse("2026-08-03T10:24:00Z"),
      },
      {
        createdAt: Date.parse("2026-08-03T10:20:00Z"),
        expiresAt: Date.parse("2026-08-03T11:20:00Z"),
        groupId: "group-wind:cordenons:1",
        id: "report-2",
        lat: 45.98,
        lon: 12.7,
        place: "Cordenons",
        revision: 1,
        typeId: "wind",
      },
    ];

    const model = buildLiveViewModel(dataState, {
      location: { city: "Pordenone", lat: 45.9567, lon: 12.6605 },
      now: new Date("2026-08-03T10:25:00Z"),
    });

    expect(model.community.items.map((item) => item.groupId)).toEqual([
      "group-rain:pordenone:1",
      "group-wind:cordenons:1",
    ]);
    expect(model.community.items[0]).toMatchObject({
      createdAt: Date.parse("2026-08-03T10:24:00Z"),
      originalCreatedAt: Date.parse("2026-08-03T09:30:00Z"),
      revision: 2,
      timeLabel: "1 min fa",
    });
    expect(model.community.items[0].contributions[0]).toMatchObject({
      createdAt: Date.parse("2026-08-03T10:24:00Z"),
      originalCreatedAt: Date.parse("2026-08-03T09:30:00Z"),
      revision: 2,
      timeLabel: "1 min fa",
    });
    expect(model.community.markers[0]).toMatchObject({
      createdAt: Date.parse("2026-08-03T10:24:00Z"),
      revision: 2,
      timeLabel: "1 min fa",
    });
  });

  it("normalizes immutable identities and backfills every legacy source consistently", () => {
    const dataState = buildDataState();
    dataState.community.payload.map_groups[0].source_keys = [
      "opaque-source-a",
      "opaque-source-legacy",
    ];
    dataState.community.payload.map_groups[0].identities = [
      { identity: RAIN_IDENTITY_WIRE, sourceKey: "opaque-source-a" },
      { identity: null, sourceKey: "opaque-source-legacy" },
    ];
    dataState.community.payload.map_groups[0].identity = RAIN_IDENTITY_WIRE;
    dataState.community.payload.map_groups[0].sourceKey = "opaque-source-a";
    dataState.community.payload.reports[0].identity = RAIN_IDENTITY_WIRE;

    const model = buildLiveViewModel(dataState, {
      location: { city: "Pordenone", lat: 45.9567, lon: 12.6605 },
      now: new Date("2026-08-03T10:25:00Z"),
    });
    const normalizedIdentity = normalizePublicCommunityIdentitySnapshot(RAIN_IDENTITY_WIRE);
    const expectedIdentities = [
      { identity: normalizedIdentity, sourceKey: "opaque-source-a" },
      {
        identity: createFallbackCommunityIdentitySnapshot(
          "opaque-source-legacy",
          "Pordenone",
        ),
        sourceKey: "opaque-source-legacy",
      },
    ];

    expect(model.community.items[0]).toMatchObject({
      identities: expectedIdentities,
      identity: normalizedIdentity,
      sourceKey: "",
      sourceKeys: ["opaque-source-a", "opaque-source-legacy"],
    });
    expect(model.community.markers[0]).toMatchObject({
      identities: expectedIdentities,
      identity: normalizedIdentity,
      sourceKey: "",
      sourceKeys: ["opaque-source-a", "opaque-source-legacy"],
    });
    expect(model.community.items[0].contributions[0]).toMatchObject({
      identities: [{ identity: normalizedIdentity, sourceKey: "opaque-source-a" }],
      identity: normalizedIdentity,
    });
    expect(Object.isFrozen(model.community.items[0].identity)).toBe(true);
    expect(Object.isFrozen(model.community.items[0].identity.avatar)).toBe(true);
  });

  it("derives grouped identities from report snapshots when map groups are unavailable", () => {
    const dataState = buildDataState();
    dataState.community.payload.map_groups = [];
    dataState.community.payload.reports[0].identity = RAIN_IDENTITY_WIRE;
    dataState.community.payload.reports.push({
      createdAt: Date.parse("2026-08-03T10:22:00Z"),
      expiresAt: Date.parse("2026-08-03T11:22:00Z"),
      groupId: "group-rain:pordenone:1",
      id: "report-2",
      lat: 45.9569,
      lon: 12.6605,
      place: "Pordenone",
      source_key: "opaque-source-b",
      typeId: "rain",
    });

    const model = buildLiveViewModel(dataState, {
      location: { city: "Pordenone", lat: 45.9567, lon: 12.6605 },
      now: new Date("2026-08-03T10:25:00Z"),
    });
    const item = model.community.items[0];

    expect(item.sourceKeys).toEqual(["opaque-source-a", "opaque-source-b"]);
    expect(item.identities).toEqual([
      {
        identity: normalizePublicCommunityIdentitySnapshot(RAIN_IDENTITY_WIRE),
        sourceKey: "opaque-source-a",
      },
      {
        identity: createFallbackCommunityIdentitySnapshot("opaque-source-b", "Pordenone"),
        sourceKey: "opaque-source-b",
      },
    ]);
    expect(model.community.markers[0].identities).toEqual(item.identities);
  });

  it("groups the list at the same group level as the map when map groups are absent", () => {
    const dataState = buildDataState();
    dataState.community.payload.map_groups = [];
    dataState.community.payload.reports.push({
      createdAt: Date.parse("2026-08-03T10:22:00Z"),
      expiresAt: Date.parse("2026-08-03T11:22:00Z"),
      groupId: "group-rain:pordenone:1",
      id: "report-2",
      lat: 45.9569,
      lon: 12.6605,
      place: "Pordenone",
      source_key: "opaque-source-b",
      typeId: "rain",
    });

    const model = buildLiveViewModel(dataState, {
      location: { city: "Pordenone", lat: 45.9567, lon: 12.6605 },
      now: new Date("2026-08-03T10:25:00Z"),
    });

    expect(model.community.items).toHaveLength(1);
    expect(model.community.items[0]).toMatchObject({
      count: 2,
      countLabel: "2 segnalazioni",
      groupId: "group-rain:pordenone:1",
      id: "group-rain:pordenone:1",
      sourceKey: "",
      sourceKeys: ["opaque-source-a", "opaque-source-b"],
    });
    expect(model.community.markers[0].phenomena).toHaveLength(1);
    expect(model.community.markers[0].phenomena[0].sourceKeys).toEqual([
      "opaque-source-a",
      "opaque-source-b",
    ]);
    expect(model.community.markers[0].phenomena[0].contributions.map((item) => item.id))
      .toEqual(["report-2", "report-1"]);
  });

  it("aggregates different phenomena into one municipality marker without losing report counts", () => {
    const dataState = buildDataState();
    dataState.community.payload.map_groups.push({
      confirmations: { no: 1, yes: 2 },
      count: 3,
      createdAt: Date.parse("2026-08-03T10:23:00Z"),
      expiresAt: Date.parse("2026-08-03T11:23:00Z"),
      groupId: "group-wind:pordenone:1",
      id: "group-wind:pordenone:1",
      lat: 45.9569,
      lon: 12.6605,
      place: "Pordenone",
      typeId: "wind",
      x: 42,
      y: 61,
    });

    const model = buildLiveViewModel(dataState, {
      location: { city: "Pordenone", lat: 45.9567, lon: 12.6605 },
      now: new Date("2026-08-03T10:25:00Z"),
    });

    expect(model.community.markers).toHaveLength(1);
    expect(model.community.markers[0]).toMatchObject({
      confirmations: { no: 1, yes: 5 },
      count: 5,
      countLabel: "5 segnalazioni",
      place: "Pordenone",
      typeId: "multiple",
      typeLabel: "Più fenomeni",
    });
    expect(model.community.markers[0].phenomena.map((item) => item.typeId)).toEqual([
      "wind",
      "rain",
    ]);
  });

  it("localizes the functional contract in Friulian", () => {
    const model = buildLiveViewModel(buildDataState(), {
      language: "fur",
      location: { city: "Pordenone" },
    });

    expect(model.title).toBe("Teritori");
    expect(model.locationLabel).toBe("Pordenon");
    expect(model.locationPlace).toBe("Pordenone");
    expect(model.webcams.groups.map((group) => group.label)).toEqual([
      "Dongje",
      "Mont",
      "Planure",
      "Cueste",
    ]);
    expect(model.community.reportOptions.find((item) => item.id === "rain")?.label).toBe("Pluie");
  });

  it("returns honest empty states while the endpoints are unavailable", () => {
    const model = buildLiveViewModel({
      community: { status: "error", payload: null },
      webcams: { status: "error", payload: null },
    });

    expect(model.webcams.available).toBe(false);
    expect(model.webcams.status).toMatchObject({ tone: "offline" });
    expect(model.community.items).toEqual([]);
    expect(model.community.markers).toEqual([]);
  });
});
