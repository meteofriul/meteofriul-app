// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MarketsEntry, MarketsExplorer } from "./MarketsExplorer";
import { EventPreviewPanel, EventsView } from "../events/EventsView";
import { buildEventsViewModel } from "../events/eventsViewModel";
import { mergeMarketEvents } from "./marketsCatalog";

vi.mock("../../services/localWeatherPilot", async importOriginal => ({
  ...await importOriginal(), isDefinitiveAppExperience: () => true,
}));
let root, host;
const pn = { city: "Pordenone", regionCode: "IT-36" };
const now = new Date("2026-10-15T10:00:00Z");
const button = label => [...host.querySelectorAll("button")].find(node => node.textContent.includes(label));
beforeEach(() => {
  vi.useFakeTimers(); vi.setSystemTime(now);
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  HTMLDialogElement.prototype.showModal = function () { this.open = true; };
  HTMLDialogElement.prototype.close = function () { this.open = false; };
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
});
afterEach(async () => {
  await act(async () => root.unmount());
  host.remove(); document.body.style.overflow = ""; vi.useRealTimers();
});
async function click(node) { await act(async () => node.click()); }
describe("market navigation", () => {
  it("opens from Scopri and retains period, radius and list scroll when returning from detail", async () => {
    const open = vi.fn(), close = vi.fn(), viewEvent = vi.fn();
    await act(async () => root.render(<><MarketsEntry onOpen={open} />
      <MarketsExplorer request={{ key: 1 }} location={pn} radius={5} onClose={close} onViewEvent={viewEvent} /></>));
    await click(button("Esplora nella tua zona")); expect(open).toHaveBeenCalledOnce();
    expect(host.querySelector("dialog").open).toBe(true);
    expect(document.body.style.overflow).toBe("hidden");
    expect(host.querySelector("select")).toBeNull();
    const list = host.querySelector(".mf-markets-content"); list.scrollTop = 120;
    await click([...host.querySelectorAll(".mf-market-card")].find(node => node.textContent.includes("La Soffitta")));
    expect(host.querySelector(".mf-market-detail").textContent).toContain("25 ottobre 2026");
    await click(button("Vedi appuntamento"));
    expect(viewEvent).toHaveBeenCalledWith({ marketId: "M035", date: "2026-10-25", radius: 5 });
    await click(button("Torna al catalogo"));
    expect(host.querySelector(".mf-markets-context").textContent).toBe("Comune di riferimentoPordenone");
    expect(list.scrollTop).toBe(120);
    await click(button("Oggi"));
    expect(host.querySelector('[aria-pressed="true"]').textContent).toBe("Oggi");
    expect(host.querySelector('[role="status"]').textContent).toContain("Nessun appuntamento");
  });
  it("handles Escape as detail back, then close, and offers no false local results outside FVG", async () => {
    const close = vi.fn();
    await act(async () => root.render(<MarketsExplorer request={{ key: 2, marketId: "M001" }} location={pn} onClose={close} />));
    const dialog = host.querySelector("dialog");
    await act(async () => dialog.dispatchEvent(new Event("cancel", { bubbles: true, cancelable: true })));
    expect(host.querySelector(".mf-market-detail")).toBeNull(); expect(close).not.toHaveBeenCalled();
    await act(async () => dialog.dispatchEvent(new Event("cancel", { bubbles: true, cancelable: true })));
    expect(close).toHaveBeenCalledOnce();
    await act(async () => root.render(<MarketsExplorer request={{ key: 3 }} location={{ city: "Roma", regionCode: "IT-62" }} onClose={close} />));
    expect(host.querySelector(".mf-markets-empty").textContent).toContain("Seleziona una località");
    expect(host.querySelectorAll(".mf-market-card")).toHaveLength(0);
  });
  it("links an Event back to its market and keeps the catalogue accessible without market results", async () => {
    const items = mergeMarketEvents([], { location: pn, radius: 5, now });
    const model = buildEventsViewModel({ items }, { location: pn, now });
    const event = model.items.find(item => item.raw.market_id === "M035");
    const open = vi.fn();
    await act(async () => root.render(<EventPreviewPanel event={event} copy={model.copy} onClose={() => {}} onMarketOpen={open} />));
    await click(button("Scheda del mercato"));
    expect(open).toHaveBeenCalledWith("M035");
    await act(async () => root.render(<EventsView model={buildEventsViewModel({ items: [] })} onMarketsOpen={open} />));
    await click(button("Esplora nella tua zona")); expect(open).toHaveBeenLastCalledWith();
  });
  it("opens the requested edition and closes its preview", async () => {
    const model = buildEventsViewModel({ items: mergeMarketEvents([], { location: pn, radius: 5, now }) }, { location: pn, now });
    await act(async () => root.render(<EventsView model={model} marketEventRequest={{ marketId: "M035", date: "2026-10-25" }} />));
    expect(document.querySelector(".mf-event-preview__panel")?.textContent).toContain("La Soffitta in Piazza");
    await act(async () => document.querySelector(".mf-event-preview__close").click());
    expect(document.querySelector(".mf-event-preview__panel")).toBeNull();
  });
});

it("follows a linked edition arriving asynchronously and does not reopen it after dismissal", async () => {
  const request = { marketId: "M035", date: "2026-10-25" };
  const pending = buildEventsViewModel({ items: [], isRefreshing: true }, { location: pn, now });
  const ready = buildEventsViewModel({ items: mergeMarketEvents([], { location: pn, radius: 5, now }) }, { location: pn, now });
  await act(async () => root.render(<EventsView model={pending} marketEventRequest={request} />));
  expect(document.querySelector(".mf-event-preview__panel")).toBeNull();
  await act(async () => root.render(<EventsView model={ready} marketEventRequest={request} />));
  expect(document.querySelector(".mf-event-preview__panel")?.textContent).toContain("La Soffitta in Piazza");
  await act(async () => root.render(<EventsView model={buildEventsViewModel({ items: [] }, { location: pn, now })} marketEventRequest={request} />));
  expect(document.querySelector(".mf-event-preview__panel")).toBeNull();
  await act(async () => root.render(<EventsView model={ready} marketEventRequest={request} />));
  await act(async () => document.querySelector(".mf-event-preview__close").click());
  await act(async () => root.render(<EventsView model={{ ...ready }} marketEventRequest={request} />));
  expect(document.querySelector(".mf-event-preview__panel")).toBeNull();
});
