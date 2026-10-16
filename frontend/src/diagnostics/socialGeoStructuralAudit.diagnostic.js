import { describe, expect, it, vi } from "vitest";

import {
  getDeviceAppLocationUpdatePlan,
  haveDeviceCoordinatesChanged,
  requestDeviceCoordinates,
} from "../services/deviceLocation";

// Opt-in red tests for confirmed social/location/push audit findings.
// The filename deliberately does not match Vitest's ordinary *.test.* glob.
describe("open social/location structural contracts at revision 3f517a8", () => {
  it("promotes cumulative movement once it exceeds the visible 500 m baseline", () => {
    const initialVisibleLocation = { lat: 46, lon: 13 };
    const fixes = [
      { lat: 46.003, lon: 13 },
      { lat: 46.006, lon: 13 },
    ];
    let latestEvidenceLocation = initialVisibleLocation;
    let visibleLocation = initialVisibleLocation;

    for (const fix of fixes) {
      // This models App.jsx:841-874: the ref/storage baseline advances even
      // when React's visible location is deliberately not updated.
      const plan = getDeviceAppLocationUpdatePlan(
        latestEvidenceLocation,
        fix,
        { placeChanged: false },
      );
      latestEvidenceLocation = fix;
      if (plan.shouldUpdateVisibleLocation) visibleLocation = fix;
    }

    expect(haveDeviceCoordinatesChanged(initialVisibleLocation, latestEvidenceLocation)).toBe(true);
    expect(visibleLocation).toEqual(latestEvidenceLocation);
  });

  it("rejects a browser geolocation timestamp beyond the accepted future skew", async () => {
    const now = Date.parse("2026-09-12T12:00:00.000Z");
    const geolocation = {
      getCurrentPosition: vi.fn((onSuccess) => onSuccess({
        coords: {
          accuracy: 12,
          latitude: 46.0625,
          longitude: 13.2342,
        },
        timestamp: now + 24 * 60 * 60 * 1000,
      })),
    };

    const result = await requestDeviceCoordinates({
      geolocation,
      now: () => now,
      preferCapacitor: false,
      preferNative: false,
    });

    expect(result).toMatchObject({
      ok: false,
      reason: "missing_quality",
    });
  });
});
