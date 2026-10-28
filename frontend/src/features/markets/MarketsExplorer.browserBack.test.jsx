// @vitest-environment jsdom
import { act, useState } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MarketsExplorer } from "./MarketsExplorer";
import { EventsView } from "../events/EventsView";
import { buildEventsViewModel } from "../events/eventsViewModel";
import { mergeMarketEvents } from "./marketsCatalog";

vi.mock("@capacitor/core", async importOriginal => {
  const actual = await importOriginal();
  return { ...actual, Capacitor: { ...actual.Capacitor, isNativePlatform: () => false } };
});
vi.mock("../../services/localWeatherPilot", async importOriginal => ({
  ...await importOriginal(), isDefinitiveAppExperience: () => true,
}));

const ENTRY = "__mfBrowserDialog";
const location = { city: "Codroipo", regionCode: "IT-36" };
const now = new Date("2026-10-28T10:00:00Z");
let root, host;

function CatalogueVisit({ onClose }) {
  const [request, setRequest] = useState({ key: 1, marketId: "M053" });
  const [edition, setEdition] = useState(null);
  const model = buildEventsViewModel({ items: mergeMarketEvents([], { location, radius: 5, now }) }, { location, now });
  return <>
    <MarketsExplorer request={request} location={location}
      onClose={() => { setRequest(null); onClose?.(); }}
      onViewEvent={next => { setRequest(null); setEdition(next); }} />
    {edition ? <EventsView model={model} marketEventRequest={edition} /> : null}
  </>;
}

beforeEach(() => {
  // Keep actual history traversal asynchronous; freeze only the civil day.
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(now);
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  window.history.replaceState({ route: "discover" }, "", "/?tab=discover");
  HTMLDialogElement.prototype.showModal = function () { this.open = true; };
  HTMLDialogElement.prototype.close = function () { this.open = false; };
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
});

afterEach(async () => {
  await act(async () => root.unmount());
  await act(async () => vi.waitFor(() => expect(window.history.state?.[ENTRY]).toBeUndefined()));
  host.remove();
  document.body.style.overflow = "";
  vi.useRealTimers();
  vi.restoreAllMocks();
});

async function browserBack() {
  await act(async () => {
    const traversed = new Promise(resolve => window.addEventListener("popstate", resolve, { once: true }));
    window.history.back();
    await traversed;
  });
}

describe("market catalogue browser history", () => {
  it("closes the complete catalogue from a detail without leaving the application", async () => {
    const close = vi.fn();
    await act(async () => root.render(<CatalogueVisit onClose={close} />));
    expect(host.querySelector(".mf-market-detail")).not.toBeNull();
    expect(window.history.state?.[ENTRY]).toBeTruthy();
    await browserBack();
    expect(close).toHaveBeenCalledOnce();
    expect(host.querySelector("dialog")).toBeNull();
    expect(window.history.state).toEqual({ route: "discover" });
    expect(window.location.search).toBe("?tab=discover");
  });

  it("consumes the catalogue entry before opening the linked Event dialog", async () => {
    await act(async () => root.render(<CatalogueVisit />));
    const catalogueEntry = window.history.state[ENTRY];
    const viewEvent = [...host.querySelectorAll("button")].find(node => node.textContent.includes("Vedi appuntamento"));
    expect(viewEvent).toBeTruthy();
    await act(async () => viewEvent.click());
    await act(async () => vi.waitFor(() => {
      expect(window.history.state?.[ENTRY]).toBeTruthy();
      expect(window.history.state[ENTRY]).not.toBe(catalogueEntry);
    }));
    expect(host.querySelector("dialog")).toBeNull();
    expect(document.querySelector(".mf-event-preview__panel")?.textContent).toContain("Lo Scrigno del Doge");
    await browserBack();
    expect(document.querySelector(".mf-event-preview__panel")).toBeNull();
    expect(window.history.state).toEqual({ route: "discover" });
  });
});
