import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

function read(relativeUrl) {
  return readFileSync(new URL(relativeUrl, import.meta.url), "utf8");
}

function declarationsFor(source, selector) {
  const escapedSelector = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return source.match(new RegExp(`^${escapedSelector}\\s*\\{([^}]+)\\}`, "m"))?.[1] || "";
}

describe("balanced app canvas chrome", () => {
  it("uses content tokens for copy outside cards while reserving shell tokens for the header", () => {
    const live = read("../features/live/live.css");
    const layout = read("./layout/layout.css");
    const settings = read("../features/settings/settings.css");
    const discover = read("../features/discover/discover.css");
    const almanac = read("../features/almanac/almanac.css");
    const forecast = read("../features/weather/weatherForecast.css");

    expect(declarationsFor(live, ".mf-live-location-context strong"))
      .toContain("color: var(--mf-page-ink)");
    expect(declarationsFor(live, ".mf-live-location-context svg"))
      .toContain("color: var(--mf-page-accent)");
    expect(declarationsFor(layout, ".mf-location-context__text strong"))
      .toContain("color: var(--mf-page-ink)");
    expect(declarationsFor(settings, ".mf-settings-topbar > strong"))
      .toContain("color: var(--mf-page-ink)");
    expect(declarationsFor(discover, ".mf-discover-calendar-heading > h2"))
      .toContain("color: var(--mf-page-ink)");
    expect(declarationsFor(discover, ".mf-discover-view--editorial > .mf-discover-section > h2,\n.mf-discover-view--editorial .mf-discover-calendar-heading > h2"))
      .toContain("color: var(--mf-page-ink)");
    expect(declarationsFor(almanac, ".mf-almanac-date-strip span"))
      .toContain("color: var(--mf-page-muted)");
    expect(declarationsFor(forecast, ".mf-weather-forecast-header__location strong"))
      .toContain("color: var(--mf-page-ink)");
  });

  it("aligns browser, PWA and Android chrome with the navy canvas", () => {
    const index = read("../../index.html");
    const manifest = read("../../public/manifest.webmanifest");
    const base = read("./base.css");
    const androidColors = read("../../android/app/src/main/res/values/colors.xml");
    const mainActivity = read(
      "../../android/app/src/main/java/com/meteofriul/app/MainActivity.java",
    );
    const systemBars = read(
      "../../android/app/src/main/java/com/meteofriul/app/MeteoSystemBarsPlugin.java",
    );
    const productionConfig = JSON.parse(read("../../capacitor.config.json"));
    const pilotConfig = JSON.parse(
      read("../../android/app/src/localPilot/assets/capacitor.config.json"),
    );

    expect(index).toContain('<meta name="theme-color" content="#091D3D" />');
    expect(manifest).toContain('"theme_color": "#091D3D"');
    expect(androidColors).toContain('<color name="system_status_bar_light">#091D3D</color>');
    expect(androidColors).toContain('<color name="system_navigation_bar_light">#091D3D</color>');
    expect(androidColors).toContain('<bool name="system_bars_use_dark_icons">false</bool>');
    expect(productionConfig.plugins.SystemBars.insetsHandling).toBe("disable");
    expect(pilotConfig.plugins.SystemBars.insetsHandling).toBe("disable");
    expect(base).toContain(
      "--mf-safe-area-inset-top: var(--safe-area-inset-top, env(safe-area-inset-top, 0px))",
    );
    expect(mainActivity).toContain(
      "WindowCompat.enableEdgeToEdge(getWindow())",
    );
    expect(productionConfig.plugins.SystemBars.style).toBe("DARK");
    expect(systemBars).not.toMatch(/\bset(?:StatusBarColor|NavigationBarColor|NavigationBarDividerColor|StatusBarContrastEnforced)\s*\(/);
    expect(systemBars).toContain("new ColorProtection(WindowInsetsCompat.Side.TOP, statusBarColor)");
    expect(systemBars).toContain("new ColorProtection(WindowInsetsCompat.Side.BOTTOM, navigationBarColor)");
    expect(systemBars).toContain("ViewCompat.setOnApplyWindowInsetsListener");
    expect(systemBars).toContain("--safe-area-inset-top");
    expect(systemBars).toContain("controller.setAppearanceLightStatusBars(false)");
    expect(systemBars).toContain("controller.setAppearanceLightNavigationBars(false)");
  });
});
