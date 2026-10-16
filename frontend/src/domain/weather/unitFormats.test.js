import { describe, expect, it } from "vitest";

import {
  formatTemperature,
  formatWindSpeed,
  getTemperatureUnitLabel,
  getWindUnitLabel,
  normalizeUnitSystem,
} from "./unitFormats";

describe("unit formats", () => {
  it("normalizes unsupported unit systems to metric", () => {
    expect(normalizeUnitSystem("imperial")).toBe("imperial");
    expect(normalizeUnitSystem("unknown")).toBe("metric");
  });

  it("formats values separately from unit labels", () => {
    expect(formatTemperature(12.4)).toBe("12");
    expect(formatWindSpeed(18.6)).toBe("19");
    expect(getTemperatureUnitLabel()).toMatch(/C$/);
    expect(getWindUnitLabel()).toBe("km/h");
  });
});
