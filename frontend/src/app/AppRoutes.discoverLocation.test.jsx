// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const runtime = vi.hoisted(() => ({ pilot: true }));

vi.mock("../services/localWeatherPilot", async (importOriginal) => ({
  ...await importOriginal(),
  isDefinitiveAppExperience: () => runtime.pilot,
  isLocalWeatherPilot: () => runtime.pilot,
  getLocalWeatherPilotTestNow: () => null,
}));

import { AppRoutes } from "./AppRoutes";
import { DEFAULT_APP_LOCATION } from "./appLocation";
import { getUiShellCopy } from "./uiShellCopy";

const editorialPordenone = {
  city: "Pordenone",
  countryCode: "IT",
  region: "Friuli Venezia Giulia",
  istatCode: "093033",
  lat: 45.9567,
  lon: 12.6605,
  source: "manual_search",
  municipality: { name: "Pordenone", istatCode: "093033", province: "PN" },
};
const gpsUdine = {
  city: "Udine",
  countryCode: "IT",
  region: "Friuli Venezia Giulia",
  istatCode: "030129",
  lat: 46.0633,
  lon: 13.2357,
  source: "browser_geolocation",
  municipality: { name: "Udine", istatCode: "030129", province: "UD", source: "istat_boundaries" },
  resolution: { status: "municipality_only", municipalityResolved: true, boundaryDistanceM: 400 },
  dataPoint: { lat: 46.0633, lon: 13.2357, source: "municipality_catalog" },
  positionAccuracyM: 18,
  positionCapturedAt: "2026-09-20T10:00:00.000Z",
};
const gpsVerona = {
  city: "Verona",
  countryCode: "IT",
  region: "Veneto",
  regionCode: "IT-34",
  insideFvg: false,
  lat: 45.4384,
  lon: 10.9916,
  source: "browser_geolocation",
  municipality: null,
  resolution: { status: "external_place", municipalityResolved: false },
  dataPoint: { lat: 45.4384, lon: 10.9916, source: "nominatim_place" },
  positionAccuracyM: 18,
  positionCapturedAt: "2026-09-20T10:00:00.000Z",
};
const manualUdine = {
  city: "Udine",
  countryCode: "IT",
  region: "Friuli Venezia Giulia",
  istatCode: "030129",
  lat: 46.0633,
  lon: 13.2357,
  source: "manual_search",
  municipality: { name: "Udine", istatCode: "030129", province: "UD" },
};
const manualVerona = {
  city: "Verona",
  countryCode: "IT",
  region: "Veneto",
  regionCode: "IT-34",
  insideFvg: false,
  lat: 45.4384,
  lon: 10.9916,
  source: "manual_search",
};

let root;
let container;

beforeEach(() => {
  runtime.pilot = true;
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-09-20T10:01:00.000Z"));
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  vi.stubGlobal("fetch", vi.fn(() => { throw new Error("Unexpected network request"); }));
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

async function renderDiscover(props = {}) {
  await act(async () => {
    root.render(<AppRoutes
      activeTab="discover"
      activeLocation={editorialPordenone}
      editorialContext={{ focusLocation: editorialPordenone }}
      copy={getUiShellCopy("it")}
      language="it"
      {...props}
    />);
  });
}

function expectNoMunicipalityCard() {
  expect(container.querySelector(".mf-discover-card--municipality")).toBeNull();
  expect(container.textContent).not.toContain("Comune individuato");
  expect(container.textContent).not.toContain("Comune selezionato");
  expect(container.textContent).not.toContain("Comune del giorno");
  expect(container.querySelector("#discover-why-title")).not.toBeNull();
  expect(globalThis.fetch).not.toHaveBeenCalled();
}

function expectMunicipalityCard(city, title) {
  const card = container.querySelector(`#discover-card-municipality-profile-${city.toLowerCase()}`);
  expect(card).not.toBeNull();
  expect(card.textContent).toContain(city);
  expect(container.querySelectorAll(".mf-discover-card--municipality")).toHaveLength(1);
  const otherCity = city === "Udine" ? "pordenone" : "udine";
  expect(container.querySelector(`#discover-card-municipality-profile-${otherCity}`)).toBeNull();
  expect(container.querySelector("#discover-focus-title").textContent).toBe(title);
  expect(globalThis.fetch).not.toHaveBeenCalled();
}

describe("AppRoutes real DiscoverView municipality provenance", () => {
  it("shows a saved manual Pordenone preference as selected without GPS", async () => {
    await renderDiscover();
    expectMunicipalityCard("Pordenone", "Comune selezionato");
  });

  it.each(["manual", "manual_recent", "manual_search", undefined])(
    "uses actual manual Udine rather than editorial Pordenone for source=%s",
    async (source) => {
      await renderDiscover({ activeLocation: { ...manualUdine, source } });
      expectMunicipalityCard("Udine", "Comune selezionato");
    },
  );

  it("does not substitute editorial Pordenone for a manual selection in Verona", async () => {
    await renderDiscover({ activeLocation: manualVerona });
    expectNoMunicipalityCard();
  });

  it("does not substitute editorial Pordenone for a successful GPS result in Verona", async () => {
    await renderDiscover({ autoLocationEnabled: true, deviceLocationStatus: { status: "success", location: gpsVerona } });
    expectNoMunicipalityCard();
  });

  it("shows GPS Udine even when both selected and editorial locations are Pordenone", async () => {
    await renderDiscover({ autoLocationEnabled: true, deviceLocationStatus: { status: "success", location: gpsUdine } });
    expectMunicipalityCard("Udine", "Comune individuato");
  });

  it.each(["idle", "denied", "error", "last_known"])(
    "keeps a genuine manual selection labelled selected when GPS is %s",
    async (status) => {
      await renderDiscover({ autoLocationEnabled: true, deviceLocationStatus: { status, location: gpsUdine } });
      expectMunicipalityCard("Pordenone", "Comune selezionato");
    },
  );

  it.each([gpsUdine, gpsVerona])("ignores a retained GPS snapshot when automatic mode is disabled ($city)", async (location) => {
    await renderDiscover({ autoLocationEnabled: false, deviceLocationStatus: { status: "success", location } });
    expectMunicipalityCard("Pordenone", "Comune selezionato");
  });

  it.each([
    ["missing active location with an editorial fallback", { activeLocation: undefined }],
    ["null active location with an editorial fallback", { activeLocation: null }],
    ["default placeholder", { activeLocation: DEFAULT_APP_LOCATION }],
    ["stored GPS with automatic mode disabled", { activeLocation: gpsUdine, autoLocationEnabled: false, deviceLocationStatus: { status: "success", location: gpsUdine } }],
    ["stored GPS while the runtime is idle", { activeLocation: gpsUdine, autoLocationEnabled: true, deviceLocationStatus: { status: "idle", location: gpsUdine } }],
    ["stored GPS after permission revocation", { activeLocation: gpsUdine, autoLocationEnabled: true, deviceLocationStatus: { status: "denied", location: gpsUdine } }],
    ["success without resolved location", { activeLocation: gpsUdine, autoLocationEnabled: true, deviceLocationStatus: { status: "success", city: "Udine" } }],
    ["manual location labelled as success", { autoLocationEnabled: true, deviceLocationStatus: { status: "success", location: { ...gpsUdine, source: "manual_search" } } }],
  ])("hides the pilot municipality card for %s", async (_label, props) => {
    await renderDiscover(props);
    expectNoMunicipalityCard();
  });

  it("updates manual Pordenone to Verona to Udine without stale editorial municipality cards", async () => {
    await renderDiscover();
    expectMunicipalityCard("Pordenone", "Comune selezionato");
    await renderDiscover({ activeLocation: manualVerona });
    expectNoMunicipalityCard();
    await renderDiscover({ activeLocation: manualUdine });
    expectMunicipalityCard("Udine", "Comune selezionato");
  });

  it("changes municipality and label with GPS results and mode changes while the selected route remains the same", async () => {
    await renderDiscover();
    expectMunicipalityCard("Pordenone", "Comune selezionato");
    await renderDiscover({ autoLocationEnabled: true, deviceLocationStatus: { status: "success", location: gpsUdine } });
    expectMunicipalityCard("Udine", "Comune individuato");
    await renderDiscover({ autoLocationEnabled: true, deviceLocationStatus: { status: "success", location: gpsVerona } });
    expectNoMunicipalityCard();
    await renderDiscover({ autoLocationEnabled: true, deviceLocationStatus: { status: "success", location: gpsUdine } });
    expectMunicipalityCard("Udine", "Comune individuato");
    await renderDiscover({ autoLocationEnabled: false, deviceLocationStatus: { status: "success", location: gpsUdine } });
    expectMunicipalityCard("Pordenone", "Comune selezionato");
    await renderDiscover({ autoLocationEnabled: true, deviceLocationStatus: { status: "success", location: gpsUdine } });
    expectMunicipalityCard("Udine", "Comune individuato");
    await renderDiscover({ autoLocationEnabled: true, deviceLocationStatus: { status: "denied", location: gpsUdine } });
    expectMunicipalityCard("Pordenone", "Comune selezionato");
  });

  it("preserves the editorial Comune del giorno in the non-pilot app", async () => {
    runtime.pilot = false;
    await renderDiscover({ activeLocation: manualVerona, autoLocationEnabled: true, deviceLocationStatus: { status: "success", location: gpsVerona } });
    expectMunicipalityCard("Pordenone", "Comune del giorno");
    expect(container.textContent).not.toContain("Comune individuato");
    expect(container.textContent).not.toContain("Comune selezionato");
  });
});
