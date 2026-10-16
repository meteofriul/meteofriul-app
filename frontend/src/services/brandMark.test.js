import { describe, expect, it } from "vitest";
import { getDefinitiveBrandMark } from "./brandMark";

describe("TEST branding isolation", () => {
  it("uses the orange mark only for the native localPilot build", () => {
    expect(getDefinitiveBrandMark({ MODE: "android-local-pilot" })).toBe("/brand/pilot-test-orange-v1/mark.svg");
    for (const mode of ["android", "cloudflare", "local-pilot", "test"]) {
      expect(getDefinitiveBrandMark({ MODE: mode })).toBe("/brand/pilot-r4/meteo-eventi-friul-mark-192.png");
    }
  });
});
