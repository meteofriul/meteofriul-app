import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { getEventsViewCopy } from "../../copy/eventsViewCopy";
import { EventPreviewPanel } from "./EventsView";

describe("EventsView event preview", () => {
  it("shows event page and directions without Google Search or attendance actions", () => {
    const html = renderToStaticMarkup(
      <EventPreviewPanel
        copy={getEventsViewCopy("it")}
        event={{
          category: "cultura",
          categoryLabel: "Cultura",
          date: "dal 21 maggio al 6 settembre",
          dateChip: { accessibleLabel: "dal 21 maggio al 6 settembre" },
          raw: { event_city: "Codroipo", venue: "Villa Manin" },
          source: "TurismoFVG",
          title: "Nuda Veritas. Klimt",
          url: "https://www.turismofvg.it/eventi/klimt",
        }}
        onClose={() => {}}
      />,
    );

    expect(html).toContain('role="dialog"');
    expect(html).toContain("Nuda Veritas. Klimt");
    expect(html).not.toContain("mf-event-preview__date");
    expect(html).toContain("dal 21 maggio al 6 settembre");
    expect(html).toContain('class="mf-event-preview__monogram">N</span>');
    expect(html).toContain("Villa Manin · Codroipo");
    expect(html).toContain("Descrizione non disponibile per questo evento.");
    expect(html).toContain("Pagina dell&#x27;evento");
    expect(html).toContain("Indicazioni");
    expect(html).toContain("/maps/dir/");
    expect(html).not.toContain("Cerca su Google");
    expect(html).not.toContain("Ci vado");
    expect(html).not.toContain("google.com/search");
  });

  it("keeps the preview actions localized in Furlan", () => {
    const html = renderToStaticMarkup(
      <EventPreviewPanel
        copy={getEventsViewCopy("fur")}
        event={{
          category: "musica",
          categoryLabel: "Musiche",
          raw: { event_city: "Udin", venue: "Teatri Palamostre" },
          title: "Concert",
          url: "https://events.example.org/concert",
        }}
        onClose={() => {}}
      />,
    );

    expect(html).toContain("Pagjine dal eveniment");
    expect(html).toContain("Indicazions");
    expect(html).toContain("Nissune descrizion disponibile par chest eveniment.");
  });

  it("does not claim a description is missing while TurismoFVG is being checked", () => {
    const html = renderToStaticMarkup(
      <EventPreviewPanel
        copy={getEventsViewCopy("it")}
        descriptionPending
        event={{
          category: "musica",
          source: "TurismoFVG",
          title: "Armonie in città",
          url: "https://www.turismofvg.it/eventi/armonie-in-citta",
        }}
        onClose={() => {}}
      />,
    );

    expect(html).toContain("Caricamento descrizione…");
    expect(html).toContain("is-loading");
    expect(html).not.toContain("Descrizione non disponibile");
  });

  it("places excerpt attribution beside the text in the opened detail", () => {
    const html = renderToStaticMarkup(
      <EventPreviewPanel
        copy={getEventsViewCopy("it")}
        event={{
          category: "musica",
          categoryLabel: "Musica",
          raw: {
            description_excerpt: "Un breve estratto verificato dalla pagina ufficiale.",
            description_source_name: "Azalea",
            description_source_url: "https://www.azalea.it/eventi/prova/",
          },
          source: "Azalea",
          title: "Concerto",
        }}
        onClose={() => {}}
      />,
    );

    expect(html).toContain("Un breve estratto verificato dalla pagina ufficiale.");
    expect(html).toContain('class="mf-event-preview__attribution"');
    expect(html).toContain('href="https://www.azalea.it/eventi/prova/"');
    expect(html.match(/Fonte:/g)).toHaveLength(1);
  });

  it("shows the complete same-day programme in a scrollable preview with official links", () => {
    const html = renderToStaticMarkup(
      <EventPreviewPanel
        copy={getEventsViewCopy("it")}
        event={{
          category: "cultura", title: "Pordenonelegge 2026",
          raw: {
            display_mode: "umbrella",
            programme_sessions: [
              { title: "Primo incontro", start_date: "2026-09-17", time: "09:00",
                place: "Pordenone, Sala A", url: "https://www.pordenonelegge.it/eventi/primo" },
              { title: "Secondo incontro", start_date: "2026-09-17", time: "11:00",
                place: "Pordenone, Sala B", access_notes: "Riservato alle scuole",
                url: "https://www.pordenonelegge.it/eventi/secondo" },
            ],
          },
        }}
        onClose={() => {}}
      />,
    );
    expect(html).toContain('class="mf-event-preview__programme-scroll" role="region" tabindex="0"');
    expect(html).toContain("2 appuntamenti");
    expect(html).not.toContain("Descrizione non disponibile");
    expect(html.match(/giovedì 17 settembre/g)).toHaveLength(1);
    expect(html.indexOf("Primo incontro")).toBeLessThan(html.indexOf("Secondo incontro"));
    expect(html).toContain('href="https://www.pordenonelegge.it/eventi/primo"');
    expect(html).toContain("Riservato alle scuole");
  });

  it("distinguishes Cinema Muto festival dates from pre-opening and replay", () => {
    const html = renderToStaticMarkup(
      <EventPreviewPanel
        copy={getEventsViewCopy("it")}
        event={{
          category: "cultura", title: "Le Giornate del Cinema Muto 2026",
          raw: {
            source: "Le Giornate del Cinema Muto",
            programme_start_date: "2026-10-02",
            programme_end_date: "2026-10-11",
            programme_main_start_date: "2026-10-03",
            programme_main_end_date: "2026-10-10",
            programme_sessions: [
              { title: "Preapertura", start_date: "2026-10-02", time: "20:45",
                url: "https://www.giornatedelcinemamuto.it/calendario-021026/" },
            ],
          },
        }}
        onClose={() => {}}
      />,
    );
    expect(html).toContain("Festival: 3–10 ottobre 2026");
    expect(html).toContain("Preapertura");
  });
});
