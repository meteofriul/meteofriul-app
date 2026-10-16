import { describe, expect, it } from "vitest";

import { getTemperatureSeverity } from "./temperatureSeverity";

describe("temperature severity", () => {
  it("classifies current temperature extremes", () => {
    expect(getTemperatureSeverity(35, "current")).toBe("extreme-hot");
    expect(getTemperatureSeverity(32, "current")).toBe("very-hot");
    expect(getTemperatureSeverity(28, "current")).toBe("hot");
    expect(getTemperatureSeverity(-6, "current")).toBe("freezing");
    expect(getTemperatureSeverity(-3, "current")).toBe("cold");
  });

  it("keeps mild temperatures neutral", () => {
    expect(getTemperatureSeverity(18, "current")).toBe("normal");
  });
});
