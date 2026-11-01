// @vitest-environment jsdom
import { act, useState } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../services/localWeatherPilot", async original => ({
  ...await original(), isDefinitiveAppExperience: () => true,
  isLocalWeatherPilot: () => true, getLocalWeatherPilotTestNow: () => null,
}));
vi.mock("../features/events/eventsDataController", async original => ({
  ...await original(), readInitialEventsData: () => null,
  loadEventsData: vi.fn(async () => ({ items: [], status: "fresh", isRefreshing: false })),
}));
import { AppRoutes } from "./AppRoutes";
import { DEFAULT_APP_LOCATION } from "./appLocation";
import { getUiShellCopy } from "./uiShellCopy";
import { loadEventsData } from "../features/events/eventsDataController";
import { getMarket } from "../features/markets/marketsCatalog";
import { readEventsRadiusPreference, writeEventsRadiusPreference } from "./eventsRadiusPreference";

const pn = { city: "Pordenone", countryCode: "IT", regionCode: "IT-36", source: "manual_search", istatCode: "093033", lat: 45.9567, lon: 12.6605 };
const ud = { city: "Udine", countryCode: "IT", regionCode: "IT-36", source: "manual_search", istatCode: "030129", lat: 46.0633, lon: 13.2357 };
let host, root;
function App({ location = pn, radius, ...props }) {
  const [tab, setTab] = useState("discover");
  const [eventsRadius, setEventsRadius] = useState(() => radius ?? readEventsRadiusPreference());
  return <><nav><button onClick={() => setTab("discover")}>Vai a Scopri</button><button onClick={() => setTab("events")}>Vai a Eventi</button><button onClick={() => setTab("settings")}>Vai a Impostazioni</button></nav>
    <AppRoutes activeTab={tab} activeLocation={location} editorialContext={{ focusLocation: pn }}
      eventsRadius={eventsRadius} onEventsRadiusChange={value => setEventsRadius(writeEventsRadiusPreference(value))}
      copy={getUiShellCopy("it")} language="it" onNavigate={setTab} {...props} /></>;
}
const button = (text, scope = document) => [...scope.querySelectorAll("button")].find(node => node.textContent.includes(text));
const click = async node => act(async () => node.click());
beforeEach(() => {
  vi.useFakeTimers(); vi.setSystemTime(new Date("2026-10-15T10:00:00Z"));
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  vi.stubGlobal("fetch", vi.fn(() => { throw new Error("Unexpected network request"); }));
  HTMLDialogElement.prototype.showModal = function () { this.open = true; };
  HTMLDialogElement.prototype.close = function () { this.open = false; };
  localStorage.clear(); vi.mocked(loadEventsData).mockClear();
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
});
afterEach(async () => {
  await act(async () => root.unmount()); host.remove();
  vi.useRealTimers(); vi.unstubAllGlobals();
});
describe("Scopri / market catalogue / Events integration", () => {
  it("uses the same remote edition and shared radius in the catalogue and Events and reacts to withdrawal", async () => {
    const market = { ...getMarket("M035"), name: "La Soffitta aggiornata" };
    let remote = { schemaVersion: 2, revision: 1, snapshotId: "markets-1", expiresAt: "2026-12-31T23:00:00Z",
      validThrough: "2026-12-31", markets: [market], identities: [{ marketId: market.id, name: market.name, comune: market.comune }],
      tombstones: [], dates: [{ id: "edition-shared", marketId: market.id, date: "2026-10-25", status: "published", source: market.url,
        venue: { id: "venue-shared", place: "Sede confermata dal pannello", directionsQuery: "Pordenone" } }] };
    vi.mocked(fetch).mockImplementation(async () => ({ ok: true, json: async () => remote }));
    await act(async () => root.render(<App radius={5} />));
    await click(button("Esplora nella tua zona"));
    expect(host.querySelectorAll(".mf-market-card")).toHaveLength(1);
    await click(button("La Soffitta aggiornata", host));
    expect(host.querySelector(".mf-market-detail").textContent).toContain("Sede confermata dal pannello");
    await click(button("Vedi appuntamento"));
    expect(document.querySelector(".mf-event-preview__panel")?.textContent).toContain("Sede confermata dal pannello");
    expect(vi.mocked(loadEventsData).mock.lastCall[0]).toMatchObject({ city: "Pordenone", eventsRadius: 5 });
    expect(vi.mocked(fetch).mock.calls.some(([url]) => url.endsWith("/api/markets/catalogue"))).toBe(true);
    remote = { ...remote, revision: 2, snapshotId: "markets-2", markets: [], dates: [], tombstones: [{ marketId: market.id, status: "archived" }] };
    await act(async () => window.dispatchEvent(new Event("online")));
    expect(document.querySelector(".mf-event-preview__panel")).toBeNull();
    expect(host.textContent).toContain("L’appuntamento non è disponibile");
  });

  it("changes radius only in Settings, keeps it on location change and restores it after reopening", async () => {
    await act(async () => root.render(<App />));
    await click(button("Esplora nella tua zona"));
    expect(host.querySelector(".mf-markets-context").textContent).toBe("Comune di riferimentoPordenone");
    expect(button("Impostazioni", host.querySelector(".mf-markets-dialog"))).toBeUndefined();
    await click(host.querySelector('[aria-label="Chiudi catalogo"]'));
    await click(button("Vai a Impostazioni"));
    expect(host.querySelector(".mf-markets-dialog")).toBeNull();
    const select = host.querySelector(".mf-settings-search-radius select");
    expect(select.value).toBe("20");
    expect([...select.options].map(option => Number(option.value))).toEqual([5, 10, 15, 20, 25, 30, 35, 40, 45, 50]);
    await act(async () => { select.value = "5"; select.dispatchEvent(new Event("change", { bubbles: true })); });
    await click(button("Vai a Eventi"));
    expect(vi.mocked(loadEventsData).mock.lastCall[0]).toMatchObject({ city: "Pordenone", eventsRadius: 5 });
    expect(host.querySelector(".mf-events-radius-context")).toBeNull();
    expect(button("Impostazioni", host.querySelector(".mf-events-view"))).toBeUndefined();
    expect(host.querySelector("select")).toBeNull();
    await act(async () => root.render(<App location={ud} />));
    expect(vi.mocked(loadEventsData).mock.lastCall[0]).toMatchObject({ city: "Udine", eventsRadius: 5 });
    await click(button("Esplora nella tua zona"));
    expect(host.querySelector(".mf-markets-radius-context")).toBeNull();
    await act(async () => root.unmount());
    root = createRoot(host);
    await act(async () => root.render(<App />));
    await click(button("Vai a Eventi"));
    expect(vi.mocked(loadEventsData).mock.lastCall[0]).toMatchObject({ eventsRadius: 5 });
    await click(button("Vai a Impostazioni"));
    expect(host.querySelector(".mf-settings-search-radius select").value).toBe("5");
  });
  it("opens a specific edition with the selected radius, links back, and consumes the navigation request", async () => {
    await act(async () => root.render(<App radius={50} />));
    expect(host.querySelector("dialog")).toBeNull();
    await click(button("Esplora nella tua zona"));
    expect(host.querySelector(".mf-markets-context select")).toBeNull();
    expect(host.querySelector(".mf-markets-radius-context")).toBeNull();
    await click(button("La Soffitta in Piazza", host));
    await click(button("Vedi appuntamento"));
    expect(document.querySelector(".mf-event-preview__panel")?.textContent).toContain("La Soffitta in Piazza");
    expect(host.querySelector(".mf-markets-dialog")).toBeNull();
    expect(vi.mocked(loadEventsData).mock.lastCall[0]).toEqual(expect.objectContaining({ city: "Pordenone", eventsRadius: 50 }));
    await click(button("Scheda del mercato", document.querySelector(".mf-event-preview__panel")));
    expect(document.querySelector(".mf-event-preview__panel")).toBeNull();
    expect(host.querySelector(".mf-market-detail")?.textContent).toContain("La Soffitta in Piazza");
    await click(host.querySelector('[aria-label="Chiudi catalogo"]'));
    await click(button("Vai a Scopri"));
    await click(button("Vai a Eventi"));
    expect(document.querySelector(".mf-event-preview__panel")).toBeNull();
    expect(document.body.style.overflow).not.toBe("hidden");
  });
  it("uses the real municipality, closes stale detail on location change and never substitutes the editorial city", async () => {
    await act(async () => root.render(<App location={ud} />));
    await click(button("Esplora nella tua zona"));
    expect(host.querySelector(".mf-markets-context strong").textContent).toBe("Udine");
    await act(async () => root.render(<App location={pn} />));
    expect(host.querySelector("dialog")).toBeNull();
    await click(button("Esplora nella tua zona"));
    expect(host.querySelector(".mf-markets-context strong").textContent).toBe("Pordenone");
    await act(async () => root.render(<App location={DEFAULT_APP_LOCATION} />));
    await click(button("Esplora nella tua zona"));
    expect(host.querySelectorAll(".mf-market-card")).toHaveLength(0);
    expect(host.querySelector(".mf-markets-empty")).not.toBeNull();
  });
});
