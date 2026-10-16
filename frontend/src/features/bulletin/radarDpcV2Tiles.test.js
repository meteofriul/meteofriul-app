import { describe, expect, it } from "vitest";

import {
  buildDpcRadarTileUrl,
  colorizeSriRadarPixels,
  getRadarFrameStatus,
  getSriRadarColor,
} from "./radarDpcV2Tiles";

describe("Radar-DPC V2 tiles", () => {
  it("builds the UTC WebP path used by the official SRI service", () => {
    expect(buildDpcRadarTileUrl({
      baseUrl: "https://tiles.example.test/",
      coords: { x: 68, y: 45, z: 7 },
      productType: "sri",
      time: "2026-08-17T16:25:00Z",
    })).toBe(
      "https://tiles.example.test/SRI/2026/08/17/1625/7/68/45/sri.webp",
    );
  });

  it("rejects invalid frame times and tile coordinates", () => {
    expect(() => buildDpcRadarTileUrl({
      baseUrl: "https://tiles.example.test",
      coords: { x: 68.5, y: 45, z: 7 },
      time: "2026-08-17T16:25:00Z",
    })).toThrow("Coordinate tile radar non valide");

    expect(() => buildDpcRadarTileUrl({
      baseUrl: "https://tiles.example.test",
      coords: { x: 68, y: 45, z: 7 },
      time: "not-a-date",
    })).toThrow("Orario radar non valido");
  });

  it("reproduces the official SRI palette and transparency threshold", () => {
    expect(getSriRadarColor(0).alpha).toBe(0);
    expect(getSriRadarColor(1)).toMatchObject({
      alpha: 1,
      blue: 0.8,
      green: 0,
      red: 0.6,
    });

    const pixels = new Uint8ClampedArray([
      0, 0, 0, 255,
      128, 0, 0, 255,
      255, 0, 0, 0,
    ]);

    expect(colorizeSriRadarPixels(pixels)).toEqual({
      echoPixelCount: 1,
      hasEcho: true,
    });
    expect(Array.from(pixels.slice(0, 4))).toEqual([0, 0, 0, 0]);
    expect(pixels[7]).toBeGreaterThan(0);
    expect(Array.from(pixels.slice(4, 7))).not.toEqual([128, 0, 0]);
    expect(Array.from(pixels.slice(8, 12))).toEqual([0, 0, 0, 0]);
  });

  it("recognizes a valid tile with no precipitation echoes", () => {
    const pixels = new Uint8ClampedArray([
      0, 0, 0, 255,
      0, 0, 0, 255,
    ]);

    expect(colorizeSriRadarPixels(pixels)).toEqual({
      echoPixelCount: 0,
      hasEcho: false,
    });
    expect(Array.from(pixels)).toEqual([0, 0, 0, 0, 0, 0, 0, 0]);
  });

  it("preserves the exact palette bytes for every intensity and source alpha", () => {
    const pixels = new Uint8ClampedArray(256 * 256 * 4);
    const expected = new Uint8ClampedArray(pixels.length);
    let expectedEchoes = 0;
    for (let intensity = 0; intensity < 256; intensity += 1) {
      const color = getSriRadarColor(intensity / 255);
      for (let sourceByte = 0; sourceByte < 256; sourceByte += 1) {
        const index = (intensity * 256 + sourceByte) * 4;
        pixels.set([intensity, 37, 211, sourceByte], index);
        const sourceAlpha = sourceByte / 255;
        if (sourceAlpha < 0.005 || intensity === 0) continue;
        const alpha = color.alpha * sourceAlpha;
        if (alpha < 0.01) {
          expected.set([intensity, 37, 211, 0], index);
        } else {
          expected.set([
            Math.round(color.red * 255),
            Math.round(color.green * 255),
            Math.round(color.blue * 255),
            Math.round(alpha * 255),
          ], index);
          expectedEchoes += 1;
        }
      }
    }

    expect(colorizeSriRadarPixels(pixels)).toEqual({
      echoPixelCount: expectedEchoes,
      hasEcho: true,
    });
    expect(pixels).toEqual(expected);
  });

  it("distinguishes loaded, empty and missing radar frames", () => {
    expect(getRadarFrameStatus({ hadEcho: true })).toBe("ready");
    expect(getRadarFrameStatus()).toBe("empty");
    expect(getRadarFrameStatus({ hadEcho: true, hadError: true })).toBe("error");
  });
});
