import { describe, expect, it } from "vitest";

import { FIXED_FVG_PLACES } from "../../data/fvgPlaces";
import { getLocalFvgLocationResults } from "../../services/locationSearch";
import { toAppLocation, toPlaceRecord } from "./locationPlaceRecords";
import { buildLocationSheetShortcuts, filterUniqueLocationPlaces, getLocationPlaceKey } from "./locationSheetLists";

describe("location sheet lists", () => {
  it("builds the same key for app locations and place records", () => {
    expect(getLocationPlaceKey({
      city: " Pordenone ",
      region: "Friuli Venezia Giulia",
    })).toBe(getLocationPlaceKey({
      name: "Pordenone",
      admin1: "Friuli Venezia Giulia",
    }));
  });

  it("removes the active location from visible lists", () => {
    const places = [
      { name: "Udine", admin1: "Friuli Venezia Giulia" },
      { name: "Pordenone", admin1: "Friuli Venezia Giulia" },
      { name: "Trieste", admin1: "Friuli Venezia Giulia" },
    ];

    expect(filterUniqueLocationPlaces(places, {
      activeLocation: { city: "Pordenone", region: "Friuli Venezia Giulia" },
    }).map((place) => place.name)).toEqual(["Udine", "Trieste"]);
  });

  it("deduplicates a list and excludes already visible places", () => {
    const places = [
      { name: "Udine", admin1: "Friuli Venezia Giulia" },
      { name: "Udine", admin1: "Friuli Venezia Giulia" },
      { name: "Pordenone", admin1: "Friuli Venezia Giulia" },
      { name: "Gorizia", admin1: "Friuli Venezia Giulia" },
    ];

    expect(filterUniqueLocationPlaces(places, {
      excludedPlaces: [{ name: "Pordenone", admin1: "Friuli Venezia Giulia" }],
    }).map((place) => place.name)).toEqual(["Udine", "Gorizia"]);
  });

  it("keeps same-name places distinct across regions and countries", () => {
    const places = [
      { name: "San Pietro", admin1: "Lazio", countryCode: "IT" },
      { name: "San Pietro", admin1: "Piemonte", countryCode: "IT" },
      { name: "San Pietro", admin1: "Lazio", countryCode: "VA" },
    ];

    expect(filterUniqueLocationPlaces(places)).toEqual(places);
  });

  it("keeps same-name places distinct inside the same region", () => {
    const places = [
      { name: "San Pietro", admin1: "Lazio", countryCode: "IT", latitude: 41.9, longitude: 12.4 },
      { name: "San Pietro", admin1: "Lazio", countryCode: "IT", latitude: 42.1, longitude: 12.8 },
    ];

    expect(filterUniqueLocationPlaces(places)).toEqual(places);
  });

  it("preserves national geocoder coordinates through a recent-location round trip", () => {
    const selected = toAppLocation({
      name: "Roma",
      admin1: "Lazio",
      countryCode: "IT",
      provider: "nominatim_search",
      providerId: "3169070",
      latitude: 41.9028,
      longitude: 12.4964,
    });
    const selectedAgain = toAppLocation(toPlaceRecord(selected));

    expect(selectedAgain).toMatchObject({
      city: "Roma",
      countryCode: "IT",
      provider: "nominatim_search",
      providerId: "3169070",
      lat: 41.9028,
      lon: 12.4964,
      dataPoint: {
        lat: 41.9028,
        lon: 12.4964,
        source: "nominatim_search",
      },
    });
  });

  it("does not assign FVG identity to records without a region", () => {
    expect(getLocationPlaceKey({ name: "Roma" })).toBe("name:roma|municipality:roma");
  });

  it("does not hide a verified municipality behind an older recent without ISTAT", () => {
    const oldRecent = {
      city: "Urbino", region: "Marche", countryCode: "IT",
      providerId: "city-urbino", lat: 43.725, lon: 12.636,
    };
    const verified = {
      name: "Urbino", admin1: "Marche", countryCode: "IT",
      providerId: "city-urbino", istatCode: "041067",
      latitude: 43.725, longitude: 12.636,
    };
    expect(filterUniqueLocationPlaces([verified], { activeLocation: oldRecent }))
      .toEqual([verified]);
  });
});

describe("pilot location shortcuts", () => {
  const capitalNames = ["Udine", "Trieste", "Gorizia", "Pordenone"];

  it.each(["udine", "trieste", "gorizia", "pordenone"])("keeps all four capitals in a fixed order with %s active", activeKey => {
    const { quickPlaces } = buildLocationSheetShortcuts({
      activeLocation: toAppLocation(FIXED_FVG_PLACES[activeKey]),
      pilot: true,
    });
    expect(quickPlaces.map(place => place.name)).toEqual(capitalNames);
    expect(quickPlaces.map(place => place.istatCode)).toEqual(["030129", "032006", "031007", "093033"]);
    expect(quickPlaces.some(place => place.name === "Tarvisio")).toBe(false);
  });

  it("deduplicates capital recents against the fixed shortcuts without modifying stored records", () => {
    const recentPlaces = Object.freeze([
      Object.freeze({ ...FIXED_FVG_PLACES.udine }),
      Object.freeze({ ...FIXED_FVG_PLACES.udine }),
      Object.freeze({ ...FIXED_FVG_PLACES.pordenone }),
      Object.freeze({ ...FIXED_FVG_PLACES.tarvisio }),
    ]);
    const before = JSON.stringify(recentPlaces);
    const result = buildLocationSheetShortcuts({
      activeLocation: toAppLocation(FIXED_FVG_PLACES.gorizia), recentPlaces, pilot: true,
    });
    expect(result.quickPlaces.map(place => place.name)).toEqual(capitalNames);
    expect(result.visibleRecentPlaces.map(place => place.name)).toEqual(["Tarvisio"]);
    expect(JSON.stringify(recentPlaces)).toBe(before);
    expect(result.visibleRecentPlaces[0]).toBe(recentPlaces[3]);
  });

  it("does not repeat a legacy capital recent without an ISTAT code", () => {
    const result = buildLocationSheetShortcuts({
      activeLocation: toAppLocation(FIXED_FVG_PLACES.udine),
      recentPlaces: [{ name: "Pordenone", admin1: "Friuli Venezia Giulia" }],
      pilot: true,
    });
    expect(result.quickPlaces.map(place => place.name)).toEqual(capitalNames);
    expect(result.visibleRecentPlaces).toEqual([]);
  });

  it("retains a distinct settlement within a shortcut municipality", () => {
    const torre = { name: "Torre", city: "Pordenone", admin1: "Friuli Venezia Giulia",
      locality: { id: "locality:torre", name: "Torre" },
      municipality: { istatCode: "093033", name: "Pordenone" } };
    const result = buildLocationSheetShortcuts({ recentPlaces: [torre], pilot: true });
    expect(result.visibleRecentPlaces).toEqual([torre]);
    expect(result.quickPlaces.map(place => place.name)).toEqual(capitalNames);
  });

  it("keeps Tarvisio available through the local search catalog", () => {
    expect(getLocalFvgLocationResults("Tarvisio")[0]).toMatchObject({
      name: "Tarvisio", province: "UD", istatCode: "030117",
    });
  });

  it("preserves the default beta list and exclusion of the active municipality", () => {
    expect(buildLocationSheetShortcuts().quickPlaces.map(place => place.name))
      .toEqual(["Udine", "Pordenone", "Trieste", "Gorizia", "Tarvisio"]);
    const result = buildLocationSheetShortcuts({ activeLocation: toAppLocation(FIXED_FVG_PLACES.pordenone) });
    expect(result.quickPlaces.map(place => place.name)).toEqual(["Udine", "Trieste", "Gorizia", "Tarvisio"]);
  });

  it("preserves beta recents priority instead of moving capitals back to shortcuts", () => {
    const result = buildLocationSheetShortcuts({
      activeLocation: toAppLocation(FIXED_FVG_PLACES.pordenone),
      recentPlaces: [FIXED_FVG_PLACES.trieste, FIXED_FVG_PLACES.trieste],
    });
    expect(result.visibleRecentPlaces.map(place => place.name)).toEqual(["Trieste"]);
    expect(result.quickPlaces.map(place => place.name)).toEqual(["Udine", "Gorizia", "Tarvisio"]);
  });
});
