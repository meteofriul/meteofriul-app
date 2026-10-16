import { describe, expect, it } from "vitest";

import { getLocationCacheKey, getLocationCacheKeyFromCity } from "./locationCacheKey";

describe("location cache key", () => {
  it("normalizes city names with the legacy city-only marker", () => {
    expect(getLocationCacheKey({ city: "  Udine  " })).toBe("udine|city|city");
    expect(getLocationCacheKeyFromCity("Pordenone")).toBe("pordenone|city|city");
  });

  it("keeps coordinate precision aligned with the current app cache key", () => {
    expect(getLocationCacheKey({ city: "Cordenons", lat: 45.983612, lon: 12.700381 })).toBe(
      "cordenons|45.9836|12.7004",
    );
  });

  it("separates localities inside the same municipality", () => {
    const municipality = { istatCode: "093022", name: "Fontanafredda" };
    const vigonovo = getLocationCacheKey({
      city: "Fontanafredda",
      displayName: "Vigonovo",
      locality: { id: "irdat:vigonovo", name: "Vigonovo" },
      municipality,
      lat: 45.9892,
      lon: 12.5473,
    });
    const talmasson = getLocationCacheKey({
      city: "Fontanafredda",
      displayName: "Talmasson",
      locality: { id: "irdat:talmasson", name: "Talmasson" },
      municipality,
      lat: 45.9892,
      lon: 12.5473,
    });

    expect(vigonovo).not.toBe(talmasson);
  });

  it("separates same-name places by region and country even without coordinates", () => {
    const italianLazio = getLocationCacheKey({
      city: "San Pietro",
      region: "Lazio",
      countryCode: "IT",
    });
    const italianPiemonte = getLocationCacheKey({
      city: "San Pietro",
      region: "Piemonte",
      countryCode: "IT",
    });
    const vaticanLazio = getLocationCacheKey({
      city: "San Pietro",
      region: "Lazio",
      countryCode: "VA",
    });

    expect(italianLazio).not.toBe(italianPiemonte);
    expect(italianLazio).not.toBe(vaticanLazio);
  });

  it("normalizes the Italian country name and the legacy FVG country inference", () => {
    const legacy = getLocationCacheKey({ city: "Udine", region: "Friuli Venezia Giulia" });
    const current = getLocationCacheKey({
      city: "Udine",
      region: "Friuli Venezia Giulia",
      country: "Italia",
    });

    expect(legacy).toBe(current);
  });
});
