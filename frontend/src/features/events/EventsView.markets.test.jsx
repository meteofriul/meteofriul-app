// @vitest-environment jsdom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { EventsView } from "./EventsView";
import { buildEventsViewModel } from "./eventsViewModel";
import { getMarket, mergeMarketEvents } from "../markets/marketsCatalog";
import { fetchLocalEventDetail } from "../../services/eventsApi";

vi.mock("../../app/useBrowserDialogBack", () => ({ useBrowserDialogBack: () => {} }));
vi.mock("../../services/eventsApi", async (importOriginal) => ({
  ...await importOriginal(), fetchLocalEventDetail: vi.fn(),
}));

const now = new Date("2026-10-15T10:00:00Z");
const location = { city: "Pordenone", regionCode: "IT-36" };
const request = { marketId: "M035", date: "2026-10-25" };
const source = {
  title: "La Soffitta in Piazza", source: "TurismoFVG", category: "mercato",
  url: "https://www.turismofvg.it/eventi/la-soffitta-in-piazza",
  start_date: request.date, end_date: request.date, event_city: "Pordenone",
  venue: "Piazza XX Settembre", time: "09:00",
  description_excerpt: "Un appuntamento dedicato al riuso e agli oggetti del passato.",
  description_source_name: "TurismoFVG",
};

let host, root;
beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(now);
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  fetchLocalEventDetail.mockReset();
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
});
afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
  document.body.style.overflow = "";
  vi.useRealTimers();
});

async function renderSource(events, { day = now, state = {} } = {}) {
  const items = mergeMarketEvents(events, { location, radius: 5, now: day });
  const model = buildEventsViewModel({ items, ...state }, { location, now: day });
  await act(async () => root.render(<EventsView model={model} marketEventRequest={request} />));
}

describe("linked market preview and current Eventi contracts", () => {
  it("updates an already opened managed edition after relocation and closes it on withdrawal", async () => {
    const market = getMarket("M035");
    const catalogue = { schemaVersion: 2, validThrough: "2026-12-31", markets: [market], identities: [], tombstones: [],
      dates: [{ id: "edition-35", marketId: market.id, date: request.date, status: "published", source: market.url,
        venue: { id: "venue-1", place: "Piazza prima", directionsQuery: "Piazza prima, Pordenone" } }] };
    const renderCatalogue = async current => {
      const items = mergeMarketEvents([source], { location, radius: 5, now, catalogue: current });
      const model = buildEventsViewModel({ items }, { location, now });
      await act(async () => root.render(<EventsView model={model} catalogue={current} />));
    };
    await renderCatalogue(catalogue);
    const upcoming = [...host.querySelectorAll("button")].find(node => node.textContent.includes("Prossimi"));
    if (upcoming) await act(async () => upcoming.click());
    const card = host.querySelector(".mf-events-card__link");
    expect(card).not.toBeNull();
    await act(async () => card.click());
    expect(document.querySelector(".mf-event-preview__panel")?.textContent).toContain("Piazza prima");
    const moved = { ...catalogue, dates: [{ ...catalogue.dates[0], date: "2026-10-26", legacyDates: [request.date],
      venue: { id: "venue-2", place: "Piazza seconda", directionsQuery: "Piazza seconda, Pordenone" } }] };
    await renderCatalogue(moved);
    const preview = document.querySelector(".mf-event-preview__panel");
    expect(preview?.textContent).toContain("Piazza seconda");
    expect(preview?.textContent).not.toContain("Piazza prima");
    expect(fetchLocalEventDetail).not.toHaveBeenCalled();
    await renderCatalogue({ ...moved, markets: [], dates: [],
      identities: [{ marketId: market.id, name: market.name, comune: market.comune }], tombstones: [{ marketId: market.id, status: "archived" }] });
    expect(document.querySelector(".mf-event-preview__panel")).toBeNull();
  });

  it("updates a linked edition when its source refreshes the same URL and title", async () => {
    await renderSource([source]);
    expect(document.querySelector('[data-testid="event-preview-time"]').textContent).toContain("09:00");
    await renderSource([{ ...source, time: "11:30", venue: "Corso Vittorio Emanuele" }]);
    const preview = document.querySelector(".mf-event-preview__panel");
    expect(preview.querySelector('[data-testid="event-preview-time"]').textContent).toContain("11:30");
    expect(preview.textContent).toContain("Corso Vittorio Emanuele");
    expect(preview.textContent).not.toContain("Piazza XX Settembre");
  });

  it("does not let an older pending detail overwrite a refreshed source edition", async () => {
    let resolve;
    fetchLocalEventDetail.mockImplementationOnce(() => new Promise((done) => { resolve = done; }));
    await renderSource([{ ...source, description_excerpt: "" }]);
    expect(fetchLocalEventDetail).toHaveBeenCalledOnce();
    await renderSource([{ ...source, time: "11:30", description_excerpt: "Descrizione aggiornata della fonte." }]);
    await act(async () => resolve({ raw: { description_excerpt: "Descrizione precedente." } }));
    const preview = document.querySelector(".mf-event-preview__panel");
    expect(preview.textContent).toContain("Descrizione aggiornata della fonte.");
    expect(preview.textContent).not.toContain("Descrizione precedente.");
    expect(preview.textContent).not.toContain("Caricamento descrizione");
  });

  it("closes a requested edition cancelled by its source without recreating it locally", async () => {
    await renderSource([source]);
    expect(document.querySelector(".mf-event-preview__panel")).not.toBeNull();
    await renderSource([{ ...source, status: "cancelled" }]);
    expect(document.querySelector(".mf-event-preview__panel")).toBeNull();
    expect(host.textContent).toContain("L’appuntamento non è disponibile");
  });

  it("does not reopen a requested date after it has elapsed", async () => {
    await renderSource([source]);
    const following = new Date("2026-10-26T11:00:00Z");
    vi.setSystemTime(following);
    await renderSource([source], { day: following });
    expect(document.querySelector(".mf-event-preview__panel")).toBeNull();
    expect(host.textContent).toContain("L’appuntamento non è disponibile");
  });
});
