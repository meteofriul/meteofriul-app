import { describe, expect, it } from "vitest";

import {
  buildColocatedWebcamMarkerOffsets,
  buildWebcamPlaceGroups,
} from "./webcamPlaceGroups";

const LIGNANO_CAMERAS = [
  {
    id: "lignano-punta-faro",
    lat: 45.697,
    lon: 13.153,
    mapClusterId: "lignano",
    mapClusterLabel: "Lignano Sabbiadoro",
    name: "Lignano Sabbiadoro - Punta Faro",
    place: "Lignano Sabbiadoro",
    sortOrder: 10,
  },
  {
    id: "lignano-terrazza-mare",
    lat: 45.689,
    lon: 13.142,
    mapClusterId: "lignano",
    mapClusterLabel: "Lignano Sabbiadoro",
    name: "Lignano Sabbiadoro - Terrazza a Mare",
    place: "Lignano Sabbiadoro",
    sortOrder: 20,
  },
];

describe("webcam place groups", () => {
  it("groups only cameras that explicitly share a mapClusterId", () => {
    const groups = buildWebcamPlaceGroups([
      ...LIGNANO_CAMERAS,
      {
        id: "trieste-miramare",
        lat: 45.703,
        lon: 13.712,
        name: "Trieste - Miramare",
        place: "Trieste",
        sortOrder: 30,
      },
      {
        id: "trieste-borsa",
        lat: 45.65,
        lon: 13.771,
        name: "Trieste - Piazza della Borsa",
        place: "Trieste",
        sortOrder: 40,
      },
    ]);

    expect(groups).toHaveLength(3);
    expect(groups[0]).toMatchObject({
      count: 2,
      id: "cluster:lignano",
      isCluster: true,
      label: "Lignano Sabbiadoro",
      mapClusterId: "lignano",
    });
    expect(groups.slice(1).map((group) => group.id)).toEqual([
      "camera:trieste-miramare",
      "camera:trieste-borsa",
    ]);
    expect(groups.slice(1).every((group) => group.isCluster === false)).toBe(true);
  });

  it("uses mapClusterLabel then place and computes a deterministic centroid", () => {
    const forward = buildWebcamPlaceGroups(LIGNANO_CAMERAS)[0];
    const reversed = buildWebcamPlaceGroups([...LIGNANO_CAMERAS].reverse())[0];

    expect(forward).toEqual(reversed);
    expect(forward.label).toBe("Lignano Sabbiadoro");
    expect(forward.cameras.map((camera) => camera.id)).toEqual([
      "lignano-punta-faro",
      "lignano-terrazza-mare",
    ]);
    expect(forward.lat).toBeCloseTo((45.697 + 45.689) / 2, 8);
    expect(forward.lon).toBeCloseTo((13.153 + 13.142) / 2, 8);

    const placeFallback = buildWebcamPlaceGroups(LIGNANO_CAMERAS.map((camera) => ({
      ...camera,
      mapClusterLabel: "",
    })))[0];
    expect(placeFallback.label).toBe("Lignano Sabbiadoro");
  });

  it("clusters the two Monte Grisa views while keeping Lanterna independent", () => {
    const groups = buildWebcamPlaceGroups([
      {
        id: "cisar-monte-grisa-sud-est",
        lat: 45.711,
        lon: 13.764,
        mapClusterId: "trieste-monte-grisa",
        mapClusterLabel: "Monte Grisa",
        name: "Monte Grisa - Sud-est",
        place: "Trieste",
        sortOrder: 10,
      },
      {
        id: "cisar-monte-grisa-sud-ovest",
        lat: 45.711,
        lon: 13.764,
        mapClusterId: "trieste-monte-grisa",
        mapClusterLabel: "Monte Grisa",
        name: "Monte Grisa - Sud-ovest",
        place: "Trieste",
        sortOrder: 11,
      },
      {
        id: "cisar-lanterna-nord",
        lat: 45.64,
        lon: 13.758,
        name: "Lanterna - Nord",
        place: "Trieste",
        sortOrder: 12,
      },
    ]);

    expect(groups).toHaveLength(2);
    expect(groups[0]).toMatchObject({
      count: 2,
      id: "cluster:trieste-monte-grisa",
      isCluster: true,
      label: "Monte Grisa",
      mapClusterId: "trieste-monte-grisa",
    });
    expect(groups[0].cameras.map((camera) => camera.id)).toEqual([
      "cisar-monte-grisa-sud-est",
      "cisar-monte-grisa-sud-ovest",
    ]);
    expect(groups[1]).toMatchObject({
      count: 1,
      id: "camera:cisar-lanterna-nord",
      isCluster: false,
      label: "Trieste",
      mapClusterId: "",
    });
  });

  it("ignores incomplete coordinates and sorts cameras and groups by sortOrder", () => {
    const groups = buildWebcamPlaceGroups([
      {
        ...LIGNANO_CAMERAS[1],
        lat: null,
        lon: null,
        sortOrder: 40,
      },
      {
        ...LIGNANO_CAMERAS[0],
        sortOrder: 20,
      },
      {
        id: "grado",
        lat: 45.678,
        lon: 13.421,
        name: "Grado",
        place: "Grado",
        sortOrder: 10,
      },
    ]);

    expect(groups.map((group) => group.id)).toEqual([
      "camera:grado",
      "cluster:lignano",
    ]);
    expect(groups[1].cameras.map((camera) => camera.sortOrder)).toEqual([20, 40]);
    expect(groups[1].lat).toBe(LIGNANO_CAMERAS[0].lat);
    expect(groups[1].lon).toBe(LIGNANO_CAMERAS[0].lon);
  });

  it("returns an empty collection for invalid input", () => {
    expect(buildWebcamPlaceGroups()).toEqual([]);
    expect(buildWebcamPlaceGroups(null)).toEqual([]);
  });
});

describe("co-located webcam marker offsets", () => {
  it("separates identical coordinates without mutating geographic data", () => {
    const cameras = [
      {
        id: "monte-grisa-sud-est",
        lat: 45.711,
        lon: 13.764,
        sortOrder: 2,
      },
      {
        id: "monte-grisa-sud-ovest",
        lat: 45.711,
        lon: 13.764,
        sortOrder: 1,
      },
      {
        id: "lanterna-nord",
        lat: 45.64,
        lon: 13.758,
        sortOrder: 3,
      },
    ];
    const original = structuredClone(cameras);
    const offsets = buildColocatedWebcamMarkerOffsets(cameras);

    expect(cameras).toEqual(original);
    expect(offsets).toEqual({
      "monte-grisa-sud-est": { x: 20, y: 0 },
      "monte-grisa-sud-ovest": { x: -20, y: 0 },
    });
    expect(offsets["lanterna-nord"]).toBeUndefined();
  });

  it("is deterministic and ignores invalid input", () => {
    const cameras = [
      { id: "b", lat: 45.711, lon: 13.764, sortOrder: 2 },
      { id: "a", lat: 45.711, lon: 13.764, sortOrder: 1 },
    ];

    expect(buildColocatedWebcamMarkerOffsets(cameras))
      .toEqual(buildColocatedWebcamMarkerOffsets([...cameras].reverse()));
    expect(buildColocatedWebcamMarkerOffsets()).toEqual({});
    expect(buildColocatedWebcamMarkerOffsets(null)).toEqual({});
  });
});
