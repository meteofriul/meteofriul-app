import { describe, expect, it } from "vitest";

import placeNamesArchive from "../../data/fvgPlaceNamesFur.json";
import {
  getLocationDisplayName,
  getLocationSearchNames,
  getMunicipalityDisplayName,
} from "./locationDisplayName";

describe("locationDisplayName", () => {
  it("uses the approved FUR name without changing the canonical location", () => {
    const location = { city: "Pordenone", istatCode: "093033" };

    expect(getLocationDisplayName(location, "fur")).toBe("Pordenon");
    expect(getLocationDisplayName(location, "it")).toBe("Pordenone");
    expect(location.city).toBe("Pordenone");
  });

  it("supports lookup by canonical Italian name when the ISTAT code is unavailable", () => {
    expect(getLocationDisplayName("Udine", "fur")).toBe("Udin");
    expect(getLocationDisplayName({ city: "Gorizia" }, "fur")).toBe("Gurize");
    expect(getLocationDisplayName({ city: "Trieste" }, "fur")).toBe("Triest");
  });

  it("keeps the approved spelling when the two languages share the same name", () => {
    expect(getLocationDisplayName({ city: "Porcia", istatCode: "093032" }, "fur")).toBe("Porcia");
  });

  it("uses the official ARLeF form for Palazzolo dello Stella", () => {
    expect(getLocationDisplayName({
      city: "Palazzolo dello Stella",
      istatCode: "030069",
    }, "fur")).toBe("Palaçûl");
  });

  it("keeps unknown places unchanged", () => {
    expect(getLocationDisplayName({ city: "Localita sconosciuta" }, "fur")).toBe("Localita sconosciuta");
  });

  it("does not translate a locality with the municipality ISTAT code", () => {
    const location = {
      city: "Fontanafredda",
      displayName: "Vigonovo",
      locality: { id: "irdat:vigonovo", name: "Vigonovo" },
      municipality: { istatCode: "093022", name: "Fontanafredda" },
    };

    expect(getLocationDisplayName(location, "it")).toBe("Vigonovo");
    expect(getLocationDisplayName(location, "fur")).toBe("Vigonovo");
    expect(getMunicipalityDisplayName(location, "it")).toBe("Fontanafredda");
    expect(getMunicipalityDisplayName(location, "fur")).toBe("Fontanefrede");
  });

  it("exposes both names for local search", () => {
    expect(getLocationSearchNames({ name: "Pordenone", istatCode: "093033" })).toEqual([
      "Pordenone",
      "Pordenon",
    ]);
  });

  it("covers every municipality with an approved FUR display name", () => {
    expect(placeNamesArchive.coverage).toEqual({ municipalities: 215, furApproved: 215 });
    expect(placeNamesArchive.names).toHaveLength(215);
    expect(new Set(placeNamesArchive.names.map((item) => item.istatCode)).size).toBe(215);
    expect(placeNamesArchive.names.every((item) => item.it && item.fur)).toBe(true);
  });
});
