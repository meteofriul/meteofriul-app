import { describe, expect, it, vi } from "vitest";

import searchSuccessFixture from "../../../contracts/runtime-api/v1/location/search-success.json";
import { isFvgLocation } from "../domain/scope/productScope";
import { toAppLocation } from "../features/location/locationPlaceRecords";
import {
  toPushRegistrationNationalManualMunicipality,
} from "./pushDeviceRegistration";

import {
  LocationSearchUnavailableError,
  getLocalFvgLocationResults,
  mergeLocationResults,
  mergeVerifiedMunicipalityResults,
  searchLocations,
  searchVerifiedMunicipalities,
} from "./locationSearch";

describe("location search", () => {
  it("deduplicates the same ISTAT municipality across differently named catalogues", () => {
    const local = getLocalFvgLocationResults("Udine");
    const udine = local.find((place) => place.istatCode === "030129");
    const remote = { ...udine, admin1: "Friuli-Venezia Giulia", providerId: "030129",
      provider: "national_icon2i_pilot_catalog", latitude: 46.06, longitude: 13.23 };
    const results = mergeLocationResults(local, [remote], { query: "Udine" });
    expect(results.filter((place) => place.istatCode === "030129")).toEqual([udine]);
    expect(mergeLocationResults([udine], [{ ...remote, istatCode: "030130" }])).toHaveLength(2);
  });
  it("finds local FVG places without calling the network", () => {
    const results = getLocalFvgLocationResults("tarv");

    expect(results[0]).toMatchObject({
      name: "Tarvisio",
      admin1: "Friuli Venezia Giulia",
      province: "UD",
      provinceName: "Udine",
      istatCode: "030117",
    });
  });

  it("finds merged municipalities from the local registry", () => {
    expect(getLocalFvgLocationResults("campolongo")[0]).toMatchObject({
      name: "Campolongo Tapogliano",
    });
    expect(getLocalFvgLocationResults("ragogna")[0]).toMatchObject({
      name: "Ragogna",
    });
    expect(getLocalFvgLocationResults("duino aurisina")[0]).toMatchObject({
      name: "Duino Aurisina",
    });
  });

  it("ranks capitals and main cities before secondary name matches while typing", () => {
    expect(getLocalFvgLocationResults("pord").slice(0, 3).map((item) => item.name)).toEqual([
      "Pordenone",
      "Pasiano di Pordenone",
      "Prata di Pordenone",
    ]);
    expect(getLocalFvgLocationResults("udi")[0]).toMatchObject({ name: "Udine" });
    expect(getLocalFvgLocationResults("go")[0]).toMatchObject({ name: "Gorizia" });
  });

  it("finds municipalities by their approved FUR name", () => {
    expect(getLocalFvgLocationResults("pordenon")[0]).toMatchObject({
      name: "Pordenone",
      istatCode: "093033",
    });
    expect(getLocalFvgLocationResults("gurize")[0]).toMatchObject({
      name: "Gorizia",
      istatCode: "031007",
    });
  });

  it("supports province code search with the province capital first", () => {
    const results = getLocalFvgLocationResults("pn");

    expect(results[0]).toMatchObject({ name: "Pordenone" });
    expect(results).toEqual(expect.arrayContaining([
      expect.objectContaining({ province: "PN" }),
    ]));
  });

  it("keeps every province-code search anchored to its capital", () => {
    expect(getLocalFvgLocationResults("ud")[0]).toMatchObject({ name: "Udine" });
    expect(getLocalFvgLocationResults("pn")[0]).toMatchObject({ name: "Pordenone" });
    expect(getLocalFvgLocationResults("go")[0]).toMatchObject({ name: "Gorizia" });
    expect(getLocalFvgLocationResults("ts")[0]).toMatchObject({ name: "Trieste" });
  });

  it("keeps national results and removes duplicate FVG records when remote data is merged", () => {
    const results = mergeLocationResults(
      [{ name: "Udine", admin1: "Friuli Venezia Giulia", latitude: 46.0693, longitude: 13.2372 }],
      [
        { name: "Udine", admin1: "Friuli Venezia Giulia", latitude: 46.0693, longitude: 13.2372 },
        { name: "Venezia", admin1: "Veneto", latitude: 45.4408, longitude: 12.3155 },
        { name: "Palmanova", admin1: "Friuli Venezia Giulia", latitude: 45.9064, longitude: 13.3097 },
      ],
    );

    expect(results.map((item) => item.name)).toEqual(["Udine", "Venezia", "Palmanova"]);
    expect(results.find((item) => item.name === "Venezia")).toMatchObject({
      admin1: "Veneto",
      countryCode: "IT",
    });
  });

  it("retains country and region identity without assigning FVG to national records", () => {
    const results = mergeLocationResults([], [
      {
        name: "Roma",
        admin1: "Lazio",
        region_code: "IT-62",
        country: "Italia",
        country_code: "IT",
        latitude: 41.8933,
        longitude: 12.4829,
      },
      {
        name: "Localita senza regione",
        latitude: 44,
        longitude: 11,
      },
    ]);

    expect(results[0]).toMatchObject({
      name: "Roma",
      admin1: "Lazio",
      regionCode: "IT-62",
      country: "Italia",
      countryCode: "IT",
    });
    expect(results[1]).toMatchObject({
      name: "Localita senza regione",
      admin1: "",
      countryCode: "IT",
    });
  });

  it("does not collapse same-name places from different regions or countries", () => {
    const results = mergeLocationResults([], [
      { name: "San Pietro", admin1: "Lazio", countryCode: "IT", latitude: 41.9, longitude: 12.4 },
      { name: "San Pietro", admin1: "Piemonte", countryCode: "IT", latitude: 45.1, longitude: 7.7 },
      { name: "San Pietro", admin1: "Lazio", countryCode: "VA", latitude: 41.9, longitude: 12.45 },
    ]);

    expect(results).toHaveLength(3);
  });

  it("does not collapse same-name places in one region when coordinates differ", () => {
    const results = mergeLocationResults([], [
      { name: "San Pietro", admin1: "Lazio", countryCode: "IT", latitude: 41.9, longitude: 12.4 },
      { name: "San Pietro", admin1: "Lazio", countryCode: "IT", latitude: 42.1, longitude: 12.8 },
    ]);

    expect(results).toHaveLength(2);
  });

  it("uses query ranking when local and backend results are merged", () => {
    const results = mergeLocationResults(
      [{ name: "Pordenone", admin1: "Friuli Venezia Giulia", latitude: 45.9567, longitude: 12.6605 }],
      [
        { name: "Pasiano di Pordenone", admin1: "Friuli Venezia Giulia", latitude: 45.8497, longitude: 12.6272 },
        { name: "Prata di Pordenone", admin1: "Friuli Venezia Giulia", latitude: 45.8917, longitude: 12.5881 },
      ],
      { query: "pord" },
    );

    expect(results.map((item) => item.name)).toEqual([
      "Pordenone",
      "Pasiano di Pordenone",
      "Prata di Pordenone",
    ]);
  });

  it("returns national backend matches outside FVG", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue([
        {
          name: "Roma",
          admin1: "Lazio",
          latitude: 41.8933,
          longitude: 12.4829,
          population: 2748109,
          country: "Italia",
          countryCode: "IT",
          provider: "nominatim_search",
          providerId: "123456",
        },
      ]),
    });

    const results = await searchLocations("roma", { apiBase: "/api", fetchImpl });

    expect(results[0]).toMatchObject({
      name: "Roma",
      admin1: "Lazio",
      country: "Italia",
      countryCode: "IT",
      provider: "nominatim_search",
      providerId: "123456",
    });
    expect(fetchImpl).toHaveBeenCalledWith("/api/location/search?q=roma");
  });

  it("uses the verified loopback catalog only for the guarded national pilot", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue({
        schema_version: 1,
        kind: "meteofriul.weather.icon.national.local_pilot_search",
        contract: "weather/v2/icon2i",
        status: "experimental_local_pilot_only",
        query: "urbi",
        results: [
          {
            name: "Urbino",
            province: "PU",
            province_name: "Pesaro e Urbino",
            region_name: "Marche",
            region_iso: "IT-57",
            latitude: 43.7252,
            longitude: 12.6378,
            istat_code: "041067",
          },
        ],
      }),
    });

    const results = await searchLocations("urbi", {
      apiBase: "https://published.invalid/api",
      fetchImpl,
      nationalPilot: true,
      nationalApiBase: "http://127.0.0.1:8782",
    });

    expect(results[0]).toMatchObject({
      name: "Urbino",
      admin1: "Marche",
      regionCode: "IT-57",
      province: "PU",
      provinceName: "Pesaro e Urbino",
      istatCode: "041067",
      countryCode: "IT",
      provider: "national_icon2i_pilot_catalog",
    });
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    expect(fetchImpl).toHaveBeenCalledWith(
      "http://127.0.0.1:8782/weather/v2/icon2i/search.json?q=urbi",
    );
  });

  it("fails closed to the bundled FVG places when the national pilot search is unavailable", async () => {
    const fetchImpl = vi.fn().mockRejectedValue(new Error("loopback unavailable"));

    const localResults = await searchLocations("pord", {
      apiBase: "https://published.invalid/api",
      fetchImpl,
      nationalPilot: true,
      nationalApiBase: "http://127.0.0.1:8782",
    });
    await expect(searchLocations("torino", {
      apiBase: "https://published.invalid/api",
      fetchImpl,
      nationalPilot: true,
      nationalApiBase: "http://127.0.0.1:8782",
    })).rejects.toBeInstanceOf(LocationSearchUnavailableError);

    expect(localResults[0]).toMatchObject({ name: "Pordenone", istatCode: "093033" });
    expect(fetchImpl).toHaveBeenCalledTimes(2);
  });

  it("rejects an unverified national pilot response instead of consulting the published API", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue({ results: [{ name: "Urbino" }] }),
    });

    await expect(searchLocations("urbino", {
      apiBase: "https://published.invalid/api",
      fetchImpl,
      nationalPilot: true,
      nationalApiBase: "http://127.0.0.1:8782",
    })).rejects.toBeInstanceOf(LocationSearchUnavailableError);

    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });

  it("uses backend results when available and falls back locally on failure", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue(searchSuccessFixture),
    });

    const pordenoneResults = await searchLocations("pord", { apiBase: "/api", fetchImpl });

    expect(pordenoneResults).toEqual(expect.arrayContaining([
      expect.objectContaining({ name: "Pordenone", istatCode: "093033" }),
    ]));
    expect(fetchImpl).toHaveBeenCalledWith("/api/location/search?q=pord");

    const pordenoneFallbackResults = await searchLocations("pord", {
      apiBase: "/api",
      fetchImpl: vi.fn().mockRejectedValue(new Error("offline")),
    });

    expect(pordenoneFallbackResults).toEqual(expect.arrayContaining([
      expect.objectContaining({ name: "Pordenone" }),
    ]));
  });

  it("surfaces a national outage when no local result can answer", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({ ok: false, status: 503 });

    await expect(searchLocations("torino", { apiBase: "/api", fetchImpl }))
      .rejects.toBeInstanceOf(LocationSearchUnavailableError);
  });
});

describe("verified ISTAT municipality search", () => {
  const urbino = {
    name: "Urbino", admin1: "Marche", latitude: 43.72, longitude: 12.64,
    province: "PU", provinceName: "Pesaro e Urbino", istatCode: "041067",
    country: "Italia", countryCode: "IT",
    provider: "istat_municipality_catalog", providerId: "041067",
  };

  it("requests the separate verified catalog and rejects records without a real identity or point", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true, json: vi.fn().mockResolvedValue([urbino]),
    });
    await expect(searchVerifiedMunicipalities("Urbino", { apiBase: "/api", fetchImpl }))
      .resolves.toMatchObject([{ istatCode: "041067", province: "PU" }]);
    expect(fetchImpl).toHaveBeenCalledWith("/api/location/municipalities/search?q=Urbino");

    fetchImpl.mockResolvedValue({
      ok: true, json: vi.fn().mockResolvedValue([{ ...urbino, latitude: null }]),
    });
    await expect(searchVerifiedMunicipalities("Urbino", { apiBase: "/api", fetchImpl }))
      .rejects.toThrow("verified_municipality_search_invalid");
  });

  it("retains an exact geocoder weather point while adding the checked ISTAT identity", () => {
    const [result] = mergeVerifiedMunicipalityResults([{
      name: "Urbino", admin1: "Marche", latitude: 43.725, longitude: 12.636,
      province: "PU", provider: "nominatim_search", providerId: "city-urbino",
    }], [urbino], { query: "urbino" });
    expect(result).toMatchObject({
      name: "Urbino", istatCode: "041067", latitude: 43.725,
      longitude: 12.636, provider: "nominatim_search",
    });
  });

  it("uses the catalog point when the geocoder is unavailable", () => {
    expect(mergeVerifiedMunicipalityResults([], [urbino], { query: "urbino" }))
      .toMatchObject([urbino]);
  });

  it("keeps same-name municipalities in different provinces distinct", () => {
    const results = mergeVerifiedMunicipalityResults([], [
      { ...urbino, name: "Castro", admin1: "Lombardia", province: "BG", istatCode: "016065", providerId: "016065" },
      { ...urbino, name: "Castro", admin1: "Puglia", province: "LE", istatCode: "075096", providerId: "075096" },
    ], { query: "castro" });
    expect(results.map(({ istatCode }) => istatCode)).toEqual(["016065", "075096"]);
  });

  it("preserves the existing FVG identity and does not assign an ISTAT to unrelated geocoder rows", () => {
    const pordenone = getLocalFvgLocationResults("pordenone")[0];
    const unrelated = {
      name: "Urbino", admin1: "Marche", province: "PU",
      latitude: 43.725, longitude: 12.636, providerId: "city-urbino",
    };
    const results = mergeVerifiedMunicipalityResults([pordenone, unrelated], [{
      ...urbino, name: "Pordenone", admin1: "Friuli Venezia Giulia",
      province: "PN", istatCode: "093033", providerId: "093033",
    }], { query: "pordenone" });
    expect(results.find(({ name }) => name === "Pordenone").istatCode).toBe("093033");
    expect(results.find(({ name }) => name === "Urbino").istatCode).toBe("");
  });

  it("routes a catalog-backed FVG selection regionally, never as a national subscription", () => {
    const [place] = mergeVerifiedMunicipalityResults([], [{
      ...urbino, name: "Pordenone", admin1: "Friuli Venezia Giulia",
      province: "PN", istatCode: "093033", providerId: "093033",
    }], { query: "pordenone" });
    const selected = toAppLocation(place);
    expect(isFvgLocation(selected)).toBe(true);
    expect(toPushRegistrationNationalManualMunicipality(selected)).toBeNull();
  });
});
