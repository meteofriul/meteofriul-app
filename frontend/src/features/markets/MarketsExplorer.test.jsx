// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MarketDetail, MarketsEntry, MarketsExplorer } from "./MarketsExplorer";
import { EventPreviewPanel, EventsView } from "../events/EventsView";
import { buildEventsViewModel } from "../events/eventsViewModel";
import { mergeMarketEvents } from "./marketsCatalog";
import historicalCatalogue from "../../data/markets/catalogue2026.json";
import candidateCatalogue from "../../data/markets/catalogueCandidate2026.json";

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
  it("shows AnticaMente's verified date and labels the habitual hours", async () => {
    const market = candidateCatalogue.markets.find(item => item.id === "M025");
    await act(async () => root.render(<MarketDetail market={market} now={new Date("2026-11-12T12:00:00Z")}
      catalogue={candidateCatalogue} />));
    const when = host.querySelectorAll(".mf-market-detail section")[1];
    expect(when.textContent).toContain("6 dicembre 2026");
    expect(when.textContent).toContain("Orario abituale: dall'alba al tramonto");
    expect(when.textContent).not.toContain("Prossima data da confermare");
  });
  it("distinguishes an unannounced edition from its habitual day and hours", async () => {
    const market = candidateCatalogue.markets.find(item => item.id === "M027");
    await act(async () => root.render(<MarketDetail market={market} now={new Date("2026-11-12T12:00:00Z")}
      catalogue={candidateCatalogue} />));
    const when = host.querySelectorAll(".mf-market-detail section")[1];
    expect([...when.querySelectorAll("p")].map(node => node.textContent)).toEqual([
      "Prima domenica di ogni mese.", "Prossima data non annunciata",
      "Orario abituale: dalla mattina al tardo pomeriggio",
    ]);
  });
  it("keeps published market copy free of repeated schedules and editorial notes", async () => {
    expect(candidateCatalogue.markets).toHaveLength(80);
    for (const market of candidateCatalogue.markets) {
      const cadence = market.cadence?.trim().replace(/[. ]+$/u, "").toLocaleLowerCase("it-IT");
      const note = market.scheduleNote?.trim().replace(/[. ]+$/u, "").toLocaleLowerCase("it-IT");
      expect(note && cadence && note === cadence, market.id).toBeFalsy();
      expect([market.cadence, market.hours, market.scheduleNote].join(" "), market.id)
        .not.toMatch(/weekdays=|per la pubblicazione|da riallineare|riattestat|pagina descrittiva|orario numerico da verificare/iu);
    }
    const torre = candidateCatalogue.markets.find(market => market.id === "R-PN-M007");
    await act(async () => root.render(<MarketDetail market={torre} now={now} catalogue={candidateCatalogue} />));
    const when = host.querySelectorAll(".mf-market-detail section")[1];
    expect(when.textContent.match(/giovedì mattina/giu)).toHaveLength(1);
    expect(when.textContent).not.toContain("07:30–12:30");
    expect(when.textContent).not.toContain("allestimento");
  });
  it("keeps the market detail concise without hiding a verified numeric time", async () => {
    const catalogue = { validThrough: "2027-02-07", dates: [], tombstones: [] };
    const market = {
      id: "R-UDA-M052", name: "Mercato settimanale di Cervignano del Friuli", comune: "Cervignano del Friuli",
      prov: "UD", group: "regular", quality: "Documentato", cadence: "Ogni giovedì mattina", hours: "Mattina",
      place: "Piazza Indipendenza", checked: "2026-11-08", scheduleNote: "Nei festivi verifica l'avviso comunale.",
    };
    await act(async () => root.render(<MarketDetail market={market} now={now} catalogue={catalogue} />));
    const when = host.querySelectorAll(".mf-market-detail section")[1];
    expect([...when.querySelectorAll("p")].map(node => node.textContent)).toEqual([
      "Ogni giovedì mattina", "Nei festivi verifica l'avviso comunale.",
    ]);
    await act(async () => root.render(<MarketDetail market={{ ...market, cadence: "Ogni sabato", hours: "08:30–12:30", scheduleNote: "Sede in viale Libertà." }} now={now} catalogue={catalogue} />));
    expect(when.textContent).toContain("08:30–12:30");
    expect(when.textContent).toContain("Il giorno abituale non conferma la singola apertura.");
  });
  it("shows published dates once when the verified start time is already in the note", async () => {
    const market = {
      id: "M-TEST", name: "Mercato agroalimentare", comune: "Mortegliano", prov: "UD",
      group: "occasional", kind: "agricultural", quality: "Documentato", checked: "2026-10-14",
      cadence: "Solo 25 e 26 ottobre 2026", hours: "Dalle 09:00 il 25 e 26 ottobre 2026; chiusura non indicata",
      scheduleNote: "Il programma conferma il mercato dalle 09:00; sede da verificare.",
    };
    const catalogue = { validThrough: "2026-12-31", tombstones: [], dates: [
      { marketId: market.id, date: "2026-10-25", status: "published" },
      { marketId: market.id, date: "2026-10-26", status: "published" },
    ] };
    await act(async () => root.render(<MarketDetail market={market} now={now} catalogue={catalogue} />));
    const when = host.querySelectorAll(".mf-market-detail section")[1];
    expect(when.querySelectorAll("time")).toHaveLength(2);
    expect(when.textContent).not.toContain(market.cadence);
    expect(when.textContent.match(/09:00/g)).toHaveLength(1);
    expect(host.querySelector(".mf-market-detail__kicker").textContent).toContain("Agricolo");
  });
  it("opens from Scopri and retains period, radius and list scroll when returning from detail", async () => {
    const open = vi.fn(), close = vi.fn(), viewEvent = vi.fn();
    await act(async () => root.render(<><MarketsEntry onOpen={open} />
      <MarketsExplorer request={{ key: 1 }} location={pn} radius={5} onClose={close} onViewEvent={viewEvent} catalogue={historicalCatalogue} /></>));
    await click(button("Esplora nella tua zona")); expect(open).toHaveBeenCalledOnce();
    expect(host.querySelector("dialog").open).toBe(true);
    expect(document.body.style.overflow).toBe("hidden");
    expect(host.querySelector("select")).toBeNull();
    expect(host.querySelector("#mf-markets-regular").parentElement.querySelector(".mf-markets-group__hint")?.textContent).toBe("Festivi: verifica la fonte");
    expect(host.querySelector("#mf-markets-occasional").parentElement.querySelector(".mf-markets-group__hint")).toBeNull();
    expect(host.querySelector(".mf-market-card").getAttribute("aria-label")).toContain("Scheda del mercato");
    expect(host.querySelector(".mf-market-card__visual").textContent).toMatch(/^[A-Z/]+OGNI$/);
    expect(host.querySelector(".mf-market-card__arrow").parentElement.children).toHaveLength(3);
    expect(host.querySelector(".mf-market-card__location").textContent).not.toContain("0 km");
    const list = host.querySelector(".mf-markets-content"); list.scrollTop = 120;
    await click([...host.querySelectorAll(".mf-market-card")].find(node => node.textContent.includes("La Soffitta")));
    expect(host.querySelector(".mf-market-detail").textContent).toContain("25 ottobre 2026");
    await click(button("Vedi appuntamento"));
    expect(viewEvent).toHaveBeenCalledWith({ marketId: "M035", date: "2026-10-25", radius: 5 });
    await click(host.querySelector(".mf-markets-header__back"));
    expect(host.querySelector(".mf-markets-context").textContent).toBe("Pordenone");
    expect(list.scrollTop).toBe(120);
    await click(button("Oggi"));
    expect(host.querySelector('[aria-pressed="true"]').textContent).toBe("Oggi");
    expect(host.querySelector('[role="status"]').textContent).toContain("Nessun appuntamento");
  });
  it("handles Escape as detail back, then close, and offers no false local results outside FVG", async () => {
    const close = vi.fn();
    await act(async () => root.render(<MarketsExplorer request={{ key: 2, marketId: "M001" }} location={pn} onClose={close} catalogue={historicalCatalogue} />));
    const dialog = host.querySelector("dialog");
    await act(async () => dialog.dispatchEvent(new Event("cancel", { bubbles: true, cancelable: true })));
    expect(host.querySelector(".mf-market-detail")).toBeNull(); expect(close).not.toHaveBeenCalled();
    await act(async () => dialog.dispatchEvent(new Event("cancel", { bubbles: true, cancelable: true })));
    expect(close).toHaveBeenCalledOnce();
    await act(async () => root.render(<MarketsExplorer request={{ key: 3 }} location={{ city: "Roma", regionCode: "IT-62" }} onClose={close} catalogue={historicalCatalogue} />));
    expect(host.querySelector(".mf-markets-empty").textContent).toContain("Seleziona una località");
    expect(host.querySelectorAll(".mf-market-card")).toHaveLength(0);
  });
  it("links an Event back to its market and keeps the catalogue accessible without market results", async () => {
    const items = mergeMarketEvents([], { location: pn, radius: 5, now, catalogue: historicalCatalogue });
    const model = buildEventsViewModel({ items }, { location: pn, now });
    const event = model.items.find(item => item.raw.market_id === "M035");
    const open = vi.fn();
    await act(async () => root.render(<EventPreviewPanel event={event} copy={model.copy} onClose={() => {}} onMarketOpen={open} catalogue={historicalCatalogue} />));
    await click(button("Scheda del mercato"));
    expect(open).toHaveBeenCalledWith("M035");
    await act(async () => root.render(<EventsView model={buildEventsViewModel({ items: [] })} onMarketsOpen={open} catalogue={historicalCatalogue} />));
    await click(button("Esplora nella tua zona")); expect(open).toHaveBeenLastCalledWith();
  });
  it("opens the requested edition and closes its preview", async () => {
    const model = buildEventsViewModel({ items: mergeMarketEvents([], { location: pn, radius: 5, now, catalogue: historicalCatalogue }) }, { location: pn, now });
    await act(async () => root.render(<EventsView model={model} marketEventRequest={{ marketId: "M035", date: "2026-10-25" }} catalogue={historicalCatalogue} />));
    expect(document.querySelector(".mf-event-preview__panel")?.textContent).toContain("La Soffitta in Piazza");
    await act(async () => document.querySelector(".mf-event-preview__close").click());
    expect(document.querySelector(".mf-event-preview__panel")).toBeNull();
  });
});

it("follows a linked edition arriving asynchronously and does not reopen it after dismissal", async () => {
  const request = { marketId: "M035", date: "2026-10-25" };
  const pending = buildEventsViewModel({ items: [], isRefreshing: true }, { location: pn, now });
  const ready = buildEventsViewModel({ items: mergeMarketEvents([], { location: pn, radius: 5, now, catalogue: historicalCatalogue }) }, { location: pn, now });
  await act(async () => root.render(<EventsView model={pending} marketEventRequest={request} catalogue={historicalCatalogue} />));
  expect(document.querySelector(".mf-event-preview__panel")).toBeNull();
  await act(async () => root.render(<EventsView model={ready} marketEventRequest={request} catalogue={historicalCatalogue} />));
  expect(document.querySelector(".mf-event-preview__panel")?.textContent).toContain("La Soffitta in Piazza");
  await act(async () => root.render(<EventsView model={buildEventsViewModel({ items: [] }, { location: pn, now })} marketEventRequest={request} catalogue={historicalCatalogue} />));
  expect(document.querySelector(".mf-event-preview__panel")).toBeNull();
  await act(async () => root.render(<EventsView model={ready} marketEventRequest={request} catalogue={historicalCatalogue} />));
  await act(async () => document.querySelector(".mf-event-preview__close").click());
  await act(async () => root.render(<EventsView model={{ ...ready }} marketEventRequest={request} catalogue={historicalCatalogue} />));
  expect(document.querySelector(".mf-event-preview__panel")).toBeNull();
});
