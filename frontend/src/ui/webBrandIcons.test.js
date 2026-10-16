import { existsSync, readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

const WEB_FAVICON_VERSION = "mf-r4-20260927";
const WEB_PWA_ICON_VERSION = "mf-r5-20260927";

function read(relativeUrl) {
  return readFileSync(new URL(relativeUrl, import.meta.url));
}

function readText(relativeUrl) {
  return read(relativeUrl).toString("utf8");
}

function pngMetadata(relativeUrl) {
  const source = read(relativeUrl);
  expect(source.subarray(0, 8).toString("hex")).toBe("89504e470d0a1a0a");
  return {
    colorType: source.readUInt8(25),
    height: source.readUInt32BE(20),
    width: source.readUInt32BE(16),
  };
}

describe("versioned Web and PWA brand icons", () => {
  it("uses the current favicon and the padded R5 Home Screen icon", () => {
    const index = readText("../../index.html");

    expect(index).toContain(`/favicon-${WEB_FAVICON_VERSION}.ico`);
    expect(index).toContain(`/favicon-${WEB_FAVICON_VERSION}-64.png`);
    expect(index).toContain(`/favicon-${WEB_FAVICON_VERSION}-32.png`);
    expect(index).toContain(`/apple-touch-icon-${WEB_PWA_ICON_VERSION}.png`);
    expect(index).toContain("html, body { background-color: #061A2E; }");
    expect(index).not.toContain("favicon-082026");
    expect(index).not.toContain("apple-touch-icon-082026");
    expect(existsSync(new URL("../../public/favicon-082026.ico", import.meta.url))).toBe(false);
    expect(existsSync(new URL("../../public/apple-touch-icon-082026.png", import.meta.url))).toBe(false);
    expect(existsSync(new URL("../../public/branding/icon_launcher_082026.png", import.meta.url))).toBe(false);
    expect(existsSync(new URL("../../public/branding/icon_launcher_082026-512.png", import.meta.url))).toBe(false);
    expect(existsSync(new URL("../../public/branding/web-notification-icon_082026-192.png", import.meta.url))).toBe(false);
  });

  it("publishes installable any and maskable icons at both required sizes", () => {
    const manifest = JSON.parse(readText("../../public/manifest.webmanifest"));

    expect(manifest.icons).toEqual([
      {
        src: `/branding/icon_launcher_any_${WEB_PWA_ICON_VERSION}-192.png`,
        sizes: "192x192",
        type: "image/png",
        purpose: "any",
      },
      {
        src: `/branding/icon_launcher_any_${WEB_PWA_ICON_VERSION}-512.png`,
        sizes: "512x512",
        type: "image/png",
        purpose: "any",
      },
      {
        src: `/branding/icon_launcher_maskable_${WEB_PWA_ICON_VERSION}-192.png`,
        sizes: "192x192",
        type: "image/png",
        purpose: "maskable",
      },
      {
        src: `/branding/icon_launcher_maskable_${WEB_PWA_ICON_VERSION}-512.png`,
        sizes: "512x512",
        type: "image/png",
        purpose: "maskable",
      },
    ]);
  });

  it("keeps the declared dimensions and opaque install surfaces", () => {
    expect(pngMetadata(`../../public/favicon-${WEB_FAVICON_VERSION}-32.png`))
      .toEqual({ colorType: 6, height: 32, width: 32 });
    expect(pngMetadata(`../../public/favicon-${WEB_FAVICON_VERSION}-64.png`))
      .toEqual({ colorType: 6, height: 64, width: 64 });
    expect(pngMetadata(`../../public/apple-touch-icon-${WEB_PWA_ICON_VERSION}.png`))
      .toEqual({ colorType: 2, height: 180, width: 180 });
    expect(pngMetadata(`../../public/branding/icon_launcher_any_${WEB_PWA_ICON_VERSION}-192.png`))
      .toEqual({ colorType: 6, height: 192, width: 192 });
    expect(pngMetadata(`../../public/branding/icon_launcher_any_${WEB_PWA_ICON_VERSION}-512.png`))
      .toEqual({ colorType: 6, height: 512, width: 512 });
    expect(pngMetadata(`../../public/branding/icon_launcher_maskable_${WEB_PWA_ICON_VERSION}-192.png`))
      .toEqual({ colorType: 2, height: 192, width: 192 });
    expect(pngMetadata(`../../public/branding/icon_launcher_maskable_${WEB_PWA_ICON_VERSION}-512.png`))
      .toEqual({ colorType: 2, height: 512, width: 512 });
  });

  it("matches the approved Android splash geometry and background color", () => {
    const manifest = JSON.parse(readText("../../public/manifest.webmanifest"));
    const androidColors = readText("../../android/app/src/main/res/values/colors.xml");
    const androidSplash = read("../../android/app/src/main/res/drawable-nodpi/splash_logo.png");
    const pwaAny512 = read(`../../public/branding/icon_launcher_any_${WEB_PWA_ICON_VERSION}-512.png`);

    expect(manifest.background_color).toBe("#061A2E");
    expect(androidColors).toContain('<color name="splash_background">#061A2E</color>');
    expect(pwaAny512).toEqual(androidSplash);
  });

  it("packages the favicon as a multi-resolution ICO", () => {
    const favicon = read(`../../public/favicon-${WEB_FAVICON_VERSION}.ico`);

    expect(favicon.subarray(0, 4).toString("hex")).toBe("00000100");
    expect(favicon.readUInt16LE(4)).toBe(4);
  });
});
