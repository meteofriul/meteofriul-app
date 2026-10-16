import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { EventCard, EventPreviewPanel, EventsView } from "./EventsView";
import { buildEventsViewModel } from "./eventsViewModel";

vi.mock("../../services/localWeatherPilot", async (importOriginal) => ({
  ...await importOriginal(),
  isDefinitiveAppExperience: () => true,
}));

const promotionCampaign = {
  advertiserDailyCap: 3,
  advertiserId: "sponsor",
  campaignDailyCap: 3,
  ctaLabel: "Scopri ora",
  enabled: true,
  id: "event-promotion",
  placements: ["events"],
  placementAssignments: {
    events: { cardNumber: 1, mode: "rotation" },
  },
  text: "Descrizione promozionale.",
  title: "Attività locale",
  url: "https://example.test/",
};

describe("filtered event heading count", () => {
  it("shows the number of appointments on one programme card", () => {
    const model = buildEventsViewModel({ items: [{
      title: "Pordenonelegge 2026", source: "Pordenonelegge",
      start_date: "2026-09-16", end_date: "2026-09-20",
      display_mode: "umbrella", programme_city: "Pordenone",
      active_session_count: 2, programme_sessions: [
        { title: "Primo", start_date: "2026-09-17", time: "09:00" },
        { title: "Secondo", start_date: "2026-09-17", time: "11:00" },
      ],
    }] }, { location: { city: "Pordenone" }, now: new Date(2026, 8, 16, 12) });
    const html = renderToStaticMarkup(
      <EventCard copy={model.copy} event={model.items[0]} onOpen={() => {}} />,
    );
    expect(html).toContain("2 appuntamenti");
    expect(html).toContain("is-programme");
  });

  it("keeps available descriptions out of the list and shows them in the detail", () => {
    const model = buildEventsViewModel({ items: [{ title: "Workshop", date: "7 settembre 2026", description: "Laboratorio di espressione corporea.", event_city: "Pordenone" }] }, { now: new Date(2026, 8, 7, 12) });
    const listHtml = renderToStaticMarkup(<EventsView model={model} />);
    const detailHtml = renderToStaticMarkup(
      <EventPreviewPanel copy={model.copy} event={model.items[0]} onClose={() => {}} />,
    );

    expect(model.items[0].excerpt).toBe("Laboratorio di espressione corporea.");
    expect(listHtml).not.toContain('class="mf-events-card__excerpt"');
    expect(listHtml).not.toContain("Laboratorio di espressione corporea.");
    expect(detailHtml).toContain('class="mf-event-preview__description"');
    expect(detailHtml).toContain("Laboratorio di espressione corporea.");
  });
  it("renders an end-only exhibition with the official deadline wording", () => {
    const model = buildEventsViewModel({ items: [{
      title: "Memorie riflesse", source: "TurismoFVG",
      url: "https://www.turismofvg.it/eventi/mostra-memorie-riflesse",
      event_city: "Gemona del Friuli", start_date: null,
      end_date: "2027-01-07", schedule_kind: "end_only",
      date_label: "Fino al 7 gennaio 2027",
    }] }, { now: new Date(2026, 9, 5, 12) });
    const cardHtml = renderToStaticMarkup(
      <EventCard copy={model.copy} event={model.items[0]} onOpen={() => {}} />,
    );
    const previewHtml = renderToStaticMarkup(
      <EventPreviewPanel copy={model.copy} event={model.items[0]} onClose={() => {}} />,
    );
    expect(cardHtml).toContain("Fino al 7 gennaio 2027");
    expect(previewHtml).toContain("Fino al 7 gennaio 2027");
    expect(cardHtml).not.toContain("dal 7 gennaio");
  });
  it("counts grouped cards rather than the server catalog total", () => {
    const item = { title: "Festa", date: "7 settembre 2026", event_city: "Porcia", url: "https://example.org/festa" };
    const model = buildEventsViewModel({ total: 583, items: [{ ...item, time: "18:00" }, { ...item, time: "21:00" }] }, { now: new Date(2026, 8, 7, 12) });
    const html = renderToStaticMarkup(<EventsView model={model} />);
    expect(html).toContain('aria-label="1 eventi" class="mf-events-title-count"');
    expect(html).not.toContain('aria-label="583 eventi"');
  });
  it("shows zero when there are no matching cards even if total is nonzero", () => {
    const model = buildEventsViewModel({ total: 583, items: [] });
    expect(renderToStaticMarkup(<EventsView model={model} />)).toContain('aria-label="0 eventi" class="mf-events-title-count"');
  });
  it("keeps the semantic heading but removes its visible row and count in compact mode", () => {
    const model = buildEventsViewModel({
      items: [{ title: "Festa", date: "7 settembre 2026", event_city: "Porcia" }],
    }, { now: new Date(2026, 8, 7, 12) });
    const html = renderToStaticMarkup(<EventsView model={model} titleMode="hidden" />);

    expect(html).toContain('class="mf-tab-page__title--hidden"');
    expect(html).not.toContain("mf-tab-page__title-row");
    expect(html).not.toContain("mf-events-title-count");
    expect(html).toContain("Festa");
    expect(html).not.toContain("mf-events-change");
    expect(html).not.toContain(">Cambia<");
  });

  it("reuses the compact Meteo navigation and keeps category colour decorative", () => {
    const now = new Date(2026, 8, 17, 12);
    const todayItems = Array.from({ length: 10 }, (_, index) => ({
      category: index % 2 ? "musica" : "cultura",
      date: "17 settembre 2026",
      event_city: "Pordenone",
      id: `today-${index}`,
      title: `Evento di oggi ${index}`,
      url: `https://example.org/today-${index}`,
    }));
    const model = buildEventsViewModel({
      items: [
        ...todayItems,
        {
          category: "sagra",
          date: "19 settembre 2026",
          event_city: "Pordenone",
          id: "weekend-sagra",
          title: "Sagra del weekend",
          url: "https://example.org/weekend-sagra",
        },
      ],
    }, { location: { city: "Pordenone" }, now });
    const html = renderToStaticMarkup(<EventsView model={model} />);

    expect(html).toContain('class="mf-location-context mf-route-location-context"');
    expect(html).toContain('<strong>Pordenone</strong>');
    expect(html).not.toContain("Vicino a");
    expect(html).toContain(
      'class="mf-events-time-tabs mf-weather-section-nav mf-weather-section-nav--compact"',
    );
    expect(html).toContain(
      'aria-label="Oggi 9+" aria-pressed="true" class="mf-weather-section-nav__item is-active"',
    );
    expect(html).toContain('class="mf-events-time-tabs__count">9+</strong>');
    expect(html).toContain(
      'aria-pressed="true" class="mf-events-filter mf-events-filter--all is-active"',
    );
    expect(html).toContain('class="mf-events-filter mf-events-filter--cultura"');
    expect(html).toContain('aria-hidden="true" class="mf-events-filter__dot"');
    expect(html.match(/class="mf-events-filter__dot"/g)).toHaveLength(3);
  });

  it("shows the category tag only in the mixed event list", () => {
    const model = buildEventsViewModel({
      items: [{
        category: "musica",
        date: "17 settembre 2026",
        event_city: "Pordenone",
        id: "jazz-river",
        source: "TurismoFVG",
        title: "Jazz River",
      }],
    }, { now: new Date(2026, 8, 17, 12) });
    const event = model.items[0];
    const mixedHtml = renderToStaticMarkup(
      <EventCard copy={model.copy} event={event} onOpen={() => {}} showCategoryLabel />,
    );
    const categoryHtml = renderToStaticMarkup(
      <EventCard copy={model.copy} event={event} onOpen={() => {}} showCategoryLabel={false} />,
    );
    const noSourceHtml = renderToStaticMarkup(
      <EventCard
        copy={model.copy}
        event={{ ...event, source: "" }}
        onOpen={() => {}}
        showCategoryLabel
      />,
    );

    expect(mixedHtml).toContain('class="mf-events-card__source">TurismoFVG</span>');
    expect(mixedHtml).toContain('class="mf-events-card__badge-separator">•</span>');
    expect(mixedHtml).toContain('class="mf-events-category mf-events-category--musica"');
    expect(categoryHtml).toContain('class="mf-events-card__source">TurismoFVG</span>');
    expect(categoryHtml).not.toContain("mf-events-card__badge-separator");
    expect(categoryHtml).not.toContain("mf-events-category--musica");
    expect(noSourceHtml).toContain("mf-events-category--musica");
    expect(noSourceHtml).not.toContain("mf-events-card__badge-separator");
  });

  it("can hide source labels from definitive cards without hiding their categories", () => {
    const model = buildEventsViewModel({
      items: [{
        category: "musica",
        date: "17 settembre 2026",
        event_city: "Pordenone",
        id: "jazz-river",
        source: "TurismoFVG",
        title: "Jazz River",
      }],
    }, { now: new Date(2026, 8, 17, 12) });
    const html = renderToStaticMarkup(<EventsView model={model} showCardSource={false} />);

    expect(html).not.toContain('class="mf-events-card__source"');
    expect(html).not.toContain("mf-events-card__badge-separator");
    expect(html).toContain("mf-events-category--musica");
  });

  it("places the sponsor after the third organic event", () => {
    const model = buildEventsViewModel({
      items: Array.from({ length: 4 }, (_, index) => ({
        category: "cultura",
        date: "17 settembre 2026",
        event_city: "Pordenone",
        id: `event-${index + 1}`,
        title: `Evento organico ${index + 1}`,
        url: `https://example.test/event-${index + 1}`,
      })),
    }, { now: new Date(2026, 8, 17, 12) });
    const html = renderToStaticMarkup(
      <EventsView model={model} promotionCampaigns={[promotionCampaign]} />,
    );
    const sponsorPosition = html.indexOf('data-promotion-placement="events"');

    expect(sponsorPosition).toBeGreaterThan(html.indexOf("Evento organico 3"));
    expect(sponsorPosition).toBeLessThan(html.indexOf("Evento organico 4"));
  });
});
