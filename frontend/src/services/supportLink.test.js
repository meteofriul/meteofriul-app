import { describe, expect, it, vi } from "vitest";

import {
  DEFAULT_SUPPORT_URL,
  getConfiguredSupportUrl,
  normalizeSupportUrl,
  openSupportUrl,
} from "./supportLink";

const ANDROID_RUNTIME = {
  getPlatform: () => "android",
  isNativePlatform: () => true,
};

describe("Ko-fi support adapter", () => {
  it("ships the approved public Ko-fi destination without credentials", () => {
    expect(DEFAULT_SUPPORT_URL).toBe("https://ko-fi.com/meteofriul");
    expect(getConfiguredSupportUrl("")).toBe(DEFAULT_SUPPORT_URL);
  });

  it("allows only official HTTPS Ko-fi hosts", () => {
    expect(normalizeSupportUrl("https://ko-fi.com/meteofriul")).toBe(
      "https://ko-fi.com/meteofriul",
    );
    expect(normalizeSupportUrl("https://www.ko-fi.com/meteofriul")).toBe(
      "https://www.ko-fi.com/meteofriul",
    );
    expect(normalizeSupportUrl("http://ko-fi.com/meteofriul")).toBeNull();
    expect(normalizeSupportUrl("https://ko-fi.com.example.org/meteofriul")).toBeNull();
    expect(normalizeSupportUrl("https://example.org/support")).toBeNull();
  });

  it("opens Ko-fi through the Android external intent adapter", async () => {
    const appLauncher = {
      openUrl: vi.fn().mockResolvedValue({ completed: true }),
    };
    const windowLike = { open: vi.fn() };

    await expect(openSupportUrl("https://ko-fi.com/meteofriul", {
      appLauncher,
      capacitor: ANDROID_RUNTIME,
      windowLike,
    })).resolves.toMatchObject({
      mode: "android_external",
      ok: true,
    });

    expect(appLauncher.openUrl).toHaveBeenCalledWith({
      url: "https://ko-fi.com/meteofriul",
    });
    expect(windowLike.open).not.toHaveBeenCalled();
  });

  it("keeps invalid or missing destinations disabled", async () => {
    const appLauncher = { openUrl: vi.fn() };

    await expect(openSupportUrl("", {
      appLauncher,
      capacitor: ANDROID_RUNTIME,
    })).resolves.toEqual({
      ok: false,
      reason: "invalid_support_url",
    });
    expect(appLauncher.openUrl).not.toHaveBeenCalled();
  });

  it("uses a normal new browser tab on the web", async () => {
    const windowLike = { open: vi.fn().mockReturnValue({}) };

    await expect(openSupportUrl("https://ko-fi.com/meteofriul", {
      capacitor: { getPlatform: () => "web", isNativePlatform: () => false },
      windowLike,
    })).resolves.toMatchObject({
      mode: "web_external",
      ok: true,
    });
    expect(windowLike.open).toHaveBeenCalledWith(
      "https://ko-fi.com/meteofriul",
      "_blank",
      "noopener,noreferrer",
    );
  });
});
