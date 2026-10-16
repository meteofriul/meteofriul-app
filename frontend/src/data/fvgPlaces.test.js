import { describe, expect, it } from "vitest";

import { FIXED_FVG_PLACES, FVG_PLACES_SOURCE } from "./fvgPlaces";

describe("FVG places registry", () => {
  const places = Object.values(FIXED_FVG_PLACES);

  it("contains the complete ISTAT FVG municipality set", () => {
    expect(FVG_PLACES_SOURCE.count).toBe(215);
    expect(places).toHaveLength(FVG_PLACES_SOURCE.count);
    expect(Object.keys(FIXED_FVG_PLACES)).toHaveLength(FVG_PLACES_SOURCE.count);
  });

  it("keeps municipality names unique", () => {
    const names = places.map((place) => place.name);

    expect(new Set(names).size).toBe(names.length);
  });

  it("keeps coordinates finite for every municipality", () => {
    const invalid = places.filter((place) => (
      place.admin1 !== "Friuli Venezia Giulia" ||
      !Number.isFinite(Number(place.latitude)) ||
      !Number.isFinite(Number(place.longitude))
    ));

    expect(invalid).toEqual([]);
  });

  it("includes merged or previously missing municipalities with source notes", () => {
    expect(FIXED_FVG_PLACES["ragogna"]).toMatchObject({
      name: "Ragogna",
      coordinateSource: "open_meteo_components",
    });
    expect(FIXED_FVG_PLACES["duino-aurisina"]).toMatchObject({
      name: "Duino Aurisina",
      coordinateSource: "open_meteo_alias",
    });
    expect(FIXED_FVG_PLACES["campolongo-tapogliano"]).toMatchObject({
      name: "Campolongo Tapogliano",
      coordinateSource: "open_meteo_components",
    });
  });

  it("does not contain mojibake in place names", () => {
    const corrupted = places.filter((place) => /Ã|Â/.test(place.name));

    expect(corrupted).toEqual([]);
    expect(FIXED_FVG_PLACES["doberd\u00f2-del-lago"].name).toBe("Doberd\u00f2 del Lago");
  });

  it("keeps the province capitals in the registry", () => {
    expect(FIXED_FVG_PLACES.udine).toMatchObject({ name: "Udine", province: "UD" });
    expect(FIXED_FVG_PLACES.pordenone).toMatchObject({ name: "Pordenone", province: "PN" });
    expect(FIXED_FVG_PLACES.trieste).toMatchObject({ name: "Trieste", province: "TS" });
    expect(FIXED_FVG_PLACES.gorizia).toMatchObject({ name: "Gorizia", province: "GO" });
  });
});
