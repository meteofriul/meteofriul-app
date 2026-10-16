import { describe, expect, it } from "vitest";

import {
  getNativeReleaseIdentity,
  isNativeReleaseIdentityKnown,
  UNKNOWN_NATIVE_RELEASE_IDENTITY,
} from "./nativeReleaseIdentity";

describe("native release identity", () => {
  it("combines the public version and Android version code", () => {
    expect(getNativeReleaseIdentity({ version: "1.0.1", build: "300012" }))
      .toBe("1.0.1+300012");
  });

  it("keeps a legacy version usable when the native bridge omits the build", () => {
    expect(getNativeReleaseIdentity({ version: "1.0.0-private.4" }))
      .toBe("1.0.0-private.4");
  });

  it("fails closed when no native identity is available", () => {
    expect(getNativeReleaseIdentity()).toBe(UNKNOWN_NATIVE_RELEASE_IDENTITY);
    expect(isNativeReleaseIdentityKnown(UNKNOWN_NATIVE_RELEASE_IDENTITY)).toBe(false);
    expect(isNativeReleaseIdentityKnown(" ")).toBe(false);
  });

  it("accepts both current and legacy non-empty identities", () => {
    expect(isNativeReleaseIdentityKnown("1.0.1+300012")).toBe(true);
    expect(isNativeReleaseIdentityKnown("1.0.0-private.4")).toBe(true);
  });
});
