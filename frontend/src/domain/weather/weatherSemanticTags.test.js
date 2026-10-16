import { describe, expect, it } from "vitest";

import { getWeatherSemanticTagContext, normalizeWeatherText } from "./weatherSemanticTags";

describe("weather semantic tags", () => {
  it("normalizes weather text for tag matching", () => {
    expect(normalizeWeatherText("  Pioggia D\u00e9bole  ")).toBe("  pioggia debole  ");
  });

  it("exposes the semantic context from normalized weather", () => {
    const context = getWeatherSemanticTagContext({ condition: "Pioggia debole", weathercode: 61 });

    expect(context.semantic.key).toBe("drizzle");
    expect(context.hasPrimarySemantic).toBe(true);
    expect(context.hasWindOverlay).toBe(false);
  });
});
