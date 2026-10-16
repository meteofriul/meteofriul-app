import { describe, expect, it } from "vitest";

import { getSunCycle } from "./sunCycle";

describe("getSunCycle", () => {
  it("computes a realistic June sun cycle for central Friuli", () => {
    const cycle = getSunCycle({
      date: new Date("2026-06-24T12:00:00Z"),
      now: new Date("2026-06-24T10:00:00Z"),
    });

    expect(cycle.sunrise).toMatch(/^05:1\d$/);
    expect(cycle.sunset).toMatch(/^21:0\d$/);
    expect(cycle.daylight).toMatch(/^15h 4\d+m$/);
    expect(cycle.daylightProgress).toBeGreaterThan(35);
    expect(cycle.daylightProgress).toBeLessThan(55);
    expect(cycle.maxAltitudeDegrees).toBe(67);
  });
});
