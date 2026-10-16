import { describe, expect, it } from "vitest";

import {
  APP_ROUTE_IDS,
  APP_TABS,
  WEATHER_SECTION_ROUTE_IDS,
  getPrimaryTabId,
} from "./appConfig";

describe("app navigation configuration", () => {
  it("exposes the four primary destinations in their visual order", () => {
    expect(APP_TABS.map((tab) => tab.id)).toEqual([
      "home",
      "weather",
      "events",
      "discover",
    ]);
  });

  it("keeps bulletin and live as addressable weather routes", () => {
    expect(WEATHER_SECTION_ROUTE_IDS).toEqual(["weather", "bulletin", "live"]);
    expect(APP_ROUTE_IDS).toEqual(expect.arrayContaining([
      "weather",
      "bulletin",
      "live",
      "almanac",
      "settings",
    ]));
  });

  it("highlights Meteo for every internal weather route", () => {
    expect(getPrimaryTabId("weather")).toBe("weather");
    expect(getPrimaryTabId("bulletin")).toBe("weather");
    expect(getPrimaryTabId("live")).toBe("weather");
    expect(getPrimaryTabId("events")).toBe("events");
    expect(getPrimaryTabId("settings")).toBe("home");
  });
});
