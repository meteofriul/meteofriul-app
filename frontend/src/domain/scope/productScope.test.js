import { describe, expect, it } from "vitest";

import {
  COMMUNITY_REGION_NOT_ENABLED_CODE,
  getTerritoryKind,
  isFvgLocation,
  resolveProductScope,
} from "./productScope";

describe("product scope", () => {
  it("recognizes FVG from canonical region identity", () => {
    expect(isFvgLocation({ regionCode: "IT-36", city: "Pordenone" })).toBe(true);
    expect(isFvgLocation({ region: "Friuli Venezia Giulia", city: "Udine" })).toBe(true);
    expect(isFvgLocation({ istatCode: "093033", city: "Pordenone" })).toBe(true);
  });

  it("does not infer FVG from a city name when the region says otherwise", () => {
    expect(isFvgLocation({
      city: "Pordenone",
      countryCode: "IT",
      region: "Lazio",
      lat: 41.9,
      lon: 12.5,
    })).toBe(false);
  });

  it("keeps national weather planned while restricting FVG-only sources", () => {
    const scope = resolveProductScope({
      city: "Roma",
      countryCode: "IT",
      region: "Lazio",
      lat: 41.9028,
      lon: 12.4964,
    });

    expect(scope.territory).toBe("italy");
    expect(scope.sources.forecast).toMatchObject({
      provider: "icon-2i",
      status: "planned",
    });
    expect(scope.sources.icon2i.status).toBe("planned");
    expect(scope.sources.radar.status).toBe("enabled");
    expect(scope.sources.nationalAlerts.status).toBe("enabled");
    expect(scope.sources.osmer.status).toBe("unsupported");
    expect(scope.sources.webcams.status).toBe("unsupported");
    expect(scope.sources.events.status).toBe("unsupported");
    expect(scope.community).toMatchObject({
      read: true,
      write: false,
      reasonCode: COMMUNITY_REGION_NOT_ENABLED_CODE,
    });
    expect(scope.editorial).toMatchObject({
      followsWeatherLocation: false,
      regionCode: "IT-36",
    });
  });

  it("enables OSMER and community writes for the FVG pilot", () => {
    const scope = resolveProductScope({ city: "Udine", region: "Friuli Venezia Giulia" });

    expect(scope.sources.forecast).toMatchObject({
      provider: "icon-2i",
      status: "enabled",
    });
    expect(scope.sources.icon2i.status).toBe("enabled");
    expect(scope.sources.osmer.status).toBe("enabled");
    expect(scope.sources.webcams.status).toBe("enabled");
    expect(scope.sources.events.status).toBe("enabled");
    expect(scope.community.write).toBe(true);
  });

  it("enables national forecasts only behind the explicit pilot capability", () => {
    const scope = resolveProductScope({
      city: "Urbino", countryCode: "IT", regionCode: "IT-57",
    }, { nationalForecastEnabled: true });

    expect(scope.sources.forecast.status).toBe("enabled");
    expect(scope.sources.icon2i.status).toBe("enabled");
    expect(scope.sources.events.status).toBe("unsupported");
    expect(scope.sources.osmer.status).toBe("unsupported");
  });

  it("classifies incomplete places conservatively", () => {
    expect(getTerritoryKind({ city: "Località senza regione" })).toBe("unknown");
    expect(getTerritoryKind({ lat: 46.0569, lon: 14.5058 })).toBe("unknown");
    expect(getTerritoryKind({
      city: "Lubiana",
      countryCode: "SI",
      region: "Osrednjeslovenska",
      lat: 46.0569,
      lon: 14.5058,
    })).toBe("unknown");

    const scope = resolveProductScope({
      city: "Lubiana",
      countryCode: "SI",
      region: "Osrednjeslovenska",
      lat: 46.0569,
      lon: 14.5058,
    });
    expect(scope.sources.forecast.status).toBe("unsupported");
    expect(scope.sources.icon2i.status).toBe("unsupported");
    expect(scope.sources.radar.status).toBe("unsupported");
    expect(scope.sources.nationalAlerts.status).toBe("unsupported");
    expect(scope.community.read).toBe(false);
  });

  it("accepts an explicit Italian ISO region code without guessing from coordinates", () => {
    expect(getTerritoryKind({ city: "Roma", regionCode: "IT-62" })).toBe("italy");
  });
});
