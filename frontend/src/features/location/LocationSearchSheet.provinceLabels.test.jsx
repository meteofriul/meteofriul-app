// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const runtime = vi.hoisted(() => ({ pilot: true, search: vi.fn(), verifiedSearch: vi.fn() }));

vi.mock("../../services/localWeatherPilot", async (importOriginal) => ({
  ...await importOriginal(),
  isDefinitiveAppExperience: () => runtime.pilot,
  isLocalWeatherPilot: () => runtime.pilot,
}));
vi.mock("../../services/locationSearch", async (importOriginal) => ({
  ...await importOriginal(),
  searchLocations: (...args) => runtime.search(...args),
  searchVerifiedMunicipalities: (...args) => runtime.verifiedSearch(...args),
}));

import { APP_RECENT_LOCATIONS_STORAGE_KEY } from "../../app/appLocation";
import { LocationSearchSheet } from "./LocationSearchSheet";

const vercelli = {
  name: "Vercelli",
  admin1: "Piemonte",
  country: "Italia",
  countryCode: "IT",
  province: "VC",
  provinceName: "Vercelli",
  latitude: 45.325,
  longitude: 8.424,
  provider: "nominatim_search",
  providerId: "vercelli-city",
};
let root;
let container;

beforeEach(() => {
  runtime.pilot = true;
  runtime.search.mockReset();
  runtime.verifiedSearch.mockReset();
  runtime.verifiedSearch.mockResolvedValue([]);
  vi.useFakeTimers();
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  vi.stubGlobal("fetch", vi.fn(() => { throw new Error("Unexpected network request"); }));
  vi.stubGlobal("requestAnimationFrame", (callback) => setTimeout(callback, 0));
  vi.stubGlobal("cancelAnimationFrame", (id) => clearTimeout(id));
  window.localStorage.clear();
  container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
});

afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

async function openSheet(language = "it", props = {}) {
  await act(async () => {
    root.render(<LocationSearchSheet isOpen language={language} {...props} />);
  });
  await act(async () => { await vi.advanceTimersByTimeAsync(0); });
  expect(container.querySelector("[role='dialog']")).toBeNull();
  expect(document.body.querySelector("[role='dialog']")).not.toBeNull();
}

async function searchFor(places, { query = "vercelli", language = "it", props = {} } = {}) {
  runtime.search.mockResolvedValue(places);
  await openSheet(language, props);
  const input = document.body.querySelector("input[type='search']");
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(input, query);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
  await act(async () => { await vi.advanceTimersByTimeAsync(220); });
  expect(runtime.search).toHaveBeenCalledWith(query);
  expect(globalThis.fetch).not.toHaveBeenCalled();
  return [...document.body.querySelectorAll(".mf-location-result__main")];
}

describe("pilot location-search province labels", () => {
  it("puts the available province abbreviation in the title, not the secondary region/country line", async () => {
    const rows = await searchFor([vercelli]);
    expect(rows).toHaveLength(1);
    expect(rows[0].querySelector("strong").textContent).toBe("Vercelli (VC)");
    expect(rows[0].querySelector("small").textContent).toBe("Piemonte · Italia");
  });

  it("uses the actual province name when no abbreviation is provided", async () => {
    const [row] = await searchFor([{ ...vercelli, province: "" }]);
    expect(row.querySelector("strong").textContent).toBe("Vercelli (Vercelli)");
    expect(row.querySelector("small").textContent).toBe("Piemonte · Italia");
  });

  it("does not derive a missing province from the municipality name or region", async () => {
    const [row] = await searchFor([{ ...vercelli, province: "", provinceName: "" }]);
    expect(row.querySelector("strong").textContent).toBe("Vercelli");
    expect(row.querySelector("small").textContent).toBe("Piemonte · Italia");
  });

  it.each([
    ["region only", { name: "Località senza provincia", admin1: "Piemonte" }, "Piemonte"],
    ["country only", { name: "Località senza provincia", country: "Francia", countryCode: "FR" }, "Francia"],
    ["known Italian country code", { name: "Località senza provincia", countryCode: "IT" }, "Italia"],
    ["no territorial metadata", { name: "Località senza provincia" }, ""],
  ])("uses only the available secondary territorial context: %s", async (_label, place, secondary) => {
    const [row] = await searchFor([place], { query: "località" });
    expect(row.querySelector("strong").textContent).toBe("Località senza provincia");
    expect(row.querySelector("small")?.textContent || "").toBe(secondary);
    expect(row.textContent).not.toContain("Friuli Venezia Giulia");
  });

  it("keeps two same-name places in different provinces separately labelled", async () => {
    const rows = await searchFor([
      { ...vercelli, name: "San Pietro", providerId: "place-vc" },
      { ...vercelli, name: "San Pietro", province: "NO", provinceName: "Novara", latitude: 45.446, longitude: 8.621, providerId: "place-no" },
    ], { query: "san pietro" });
    expect(rows.map((row) => row.querySelector("strong").textContent)).toEqual([
      "San Pietro (VC)", "San Pietro (NO)",
    ]);
  });

  it("selects a catalog-verified national municipality with its exact ISTAT code", async () => {
    const onLocationSelect = vi.fn().mockResolvedValue(undefined);
    runtime.verifiedSearch.mockResolvedValue([{
      name: "Urbino", admin1: "Marche", province: "PU", provinceName: "Pesaro e Urbino",
      country: "Italia", countryCode: "IT", latitude: 43.72, longitude: 12.64,
      istatCode: "041067", provider: "istat_municipality_catalog", providerId: "041067",
    }]);
    const [row] = await searchFor([{
      name: "Urbino", admin1: "Marche", province: "PU", countryCode: "IT",
      latitude: 43.725, longitude: 12.636, provider: "nominatim_search",
      providerId: "city-urbino",
    }], { query: "urbino", props: { onLocationSelect } });
    expect(row.querySelector("strong").textContent).toBe("Urbino (PU)");
    await act(async () => row.click());
    expect(onLocationSelect).toHaveBeenCalledWith(expect.objectContaining({
      city: "Urbino", source: "manual", lat: 43.725,
      municipality: expect.objectContaining({ istatCode: "041067", name: "Urbino" }),
    }));
  });

  it("preserves the FUR place name while adding its province abbreviation", async () => {
    const [row] = await searchFor([{
      name: "Udine", admin1: "Friuli Venezia Giulia", istatCode: "030129",
      province: "UD", provinceName: "Udine", countryCode: "IT",
      latitude: 46.0633, longitude: 13.2357,
    }], { query: "udin", language: "fur" });
    expect(row.querySelector("strong").textContent).toBe("Udin (UD)");
    expect(row.querySelector("small").textContent).not.toContain("Udine");
  });

  it("reads nested municipality province from a recent settlement and retains its municipality subtitle", async () => {
    window.localStorage.setItem(APP_RECENT_LOCATIONS_STORAGE_KEY, JSON.stringify([{
      city: "Fontanafredda",
      displayName: "Vigonovo",
      region: "Friuli Venezia Giulia",
      countryCode: "IT",
      lat: 45.9892,
      lon: 12.5473,
      source: "manual_recent",
      locality: { id: "irdat:vigonovo", name: "Vigonovo", kind: "settlement" },
      municipality: { name: "Fontanafredda", istatCode: "093022", province: "PN", provinceName: "Pordenone" },
    }]));
    await openSheet();
    const row = [...document.body.querySelectorAll(".mf-location-result__main")]
      .find((entry) => entry.querySelector("strong").textContent.startsWith("Vigonovo"));
    expect(row).toBeDefined();
    expect(row.querySelector("strong").textContent).toBe("Vigonovo (PN)");
    expect(row.querySelector("small").textContent).toBe("Comune di Fontanafredda");
    expect(runtime.search).not.toHaveBeenCalled();
  });

  it("leaves the legacy beta title and province subtitle unchanged", async () => {
    runtime.pilot = false;
    const [row] = await searchFor([vercelli]);
    expect(row.querySelector("strong").textContent).toBe("Vercelli");
    expect(row.querySelector("small").textContent).toBe("Vercelli · VC");
  });
});
