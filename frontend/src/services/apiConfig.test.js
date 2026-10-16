import { describe, expect, it } from "vitest";

import {
  API_BASE,
  isAndroidCapacitorRuntime,
  normalizeAndroidApiBase,
  resolveApiBase,
} from "./apiConfig";

describe("API config", () => {
  it("defaults browser builds to the Vite proxy path", () => {
    expect(API_BASE).toBe("/api");
    expect(resolveApiBase({ nativeAndroid: false })).toBe("/api");
  });

  it("fails closed when Android has no explicit endpoint", () => {
    expect(() => resolveApiBase({ nativeAndroid: true })).toThrow(
      "android_api_base_must_be_absolute_https",
    );
  });

  it("accepts only absolute HTTPS Android endpoints and removes one trailing slash", () => {
    expect(normalizeAndroidApiBase("https://api.example.test/v1/")).toBe(
      "https://api.example.test/v1",
    );
    expect(() => normalizeAndroidApiBase("/api")).toThrow(
      "android_api_base_must_be_absolute_https",
    );
    expect(() => normalizeAndroidApiBase("http://api.example.test/api")).toThrow(
      "android_api_base_must_be_absolute_https",
    );
    expect(() => normalizeAndroidApiBase("https://user:secret@example.test/api")).toThrow(
      "android_api_base_must_be_absolute_https",
    );
    expect(() => normalizeAndroidApiBase("https://api.example.test/api?unsafe=1")).toThrow(
      "android_api_base_must_be_absolute_https",
    );
  });

  it("fails closed instead of falling back when an Android override is unsafe", () => {
    expect(() => resolveApiBase({
      configuredApiBase: "/api",
      nativeAndroid: true,
    })).toThrow("android_api_base_must_be_absolute_https");
  });

  it("detects only a native Android Capacitor runtime", () => {
    expect(isAndroidCapacitorRuntime({
      getPlatform: () => "android",
      isNativePlatform: () => true,
    })).toBe(true);
    expect(isAndroidCapacitorRuntime({
      getPlatform: () => "web",
      isNativePlatform: () => false,
    })).toBe(false);
  });
});
