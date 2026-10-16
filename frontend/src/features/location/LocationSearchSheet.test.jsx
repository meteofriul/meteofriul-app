import { describe, expect, it } from "vitest";

import { toAppLocation, toPlaceRecord } from "./locationPlaceRecords";

describe("LocationSearchSheet location records", () => {
  it("builds a canonical municipality record for a manual municipality result", () => {
    expect(toAppLocation({
      name: "Pordenone",
      admin1: "Friuli Venezia Giulia",
      province: "PN",
      provinceName: "Pordenone",
      istatCode: "093033",
      latitude: 45.9567,
      longitude: 12.6605,
    })).toMatchObject({
      city: "Pordenone",
      displayName: "Pordenone",
      locality: { kind: "municipality", name: "Pordenone" },
      municipality: { istatCode: "093033", name: "Pordenone" },
      source: "manual",
    });
  });

  it("preserves national territory identity and never invents an FVG region", () => {
    const rome = toAppLocation({
      name: "Roma",
      admin1: "Lazio",
      regionCode: "IT-62",
      country: "Italia",
      countryCode: "IT",
      provider: "nominatim_search",
      providerId: "3169070",
      latitude: 41.8933,
      longitude: 12.4829,
    });

    expect(rome).toMatchObject({
      city: "Roma",
      region: "Lazio",
      regionCode: "IT-62",
      country: "Italia",
      countryCode: "IT",
      provider: "nominatim_search",
      providerId: "3169070",
    });
    expect(toPlaceRecord(rome)).toMatchObject({
      name: "Roma",
      admin1: "Lazio",
      regionCode: "IT-62",
      country: "Italia",
      countryCode: "IT",
      provider: "nominatim_search",
      providerId: "3169070",
    });
    expect(toAppLocation({ name: "Localita senza regione" }).region).toBe("");
  });

  it("preserves Vigonovo and its Fontanafredda municipality when selected from recent places", () => {
    const storedLocation = {
      city: "Fontanafredda",
      displayName: "Vigonovo",
      region: "Friuli Venezia Giulia",
      lat: 45.9892108,
      lon: 12.5473156,
      source: "android_current_location",
      positionAccuracyM: 12,
      positionCapturedAt: "2026-08-16T10:00:00.000Z",
      locality: {
        id: "irdat:vigonovo",
        name: "Vigonovo",
        kind: "settlement",
        source: "rafvg_irdat_5000",
        datasetVersion: "2006",
      },
      municipality: {
        istatCode: "093022",
        name: "Fontanafredda",
        province: "PN",
        provinceName: "Pordenone",
        source: "istat_boundaries",
        datasetVersion: "2026-01-01",
      },
      resolution: {
        status: "resolved",
        municipalityResolved: true,
        localityCorroborated: true,
      },
    };

    const selectedLocation = toAppLocation(toPlaceRecord(storedLocation));

    expect(selectedLocation).toMatchObject({
      city: "Fontanafredda",
      displayName: "Vigonovo",
      lat: 45.9892108,
      lon: 12.5473156,
      locality: { id: "irdat:vigonovo", name: "Vigonovo" },
      municipality: { istatCode: "093022", name: "Fontanafredda" },
      source: "manual_recent",
    });
    expect(selectedLocation).not.toHaveProperty("positionAccuracyM");
    expect(selectedLocation).not.toHaveProperty("positionCapturedAt");
  });
});
